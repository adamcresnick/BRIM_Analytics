"""
Integrated Pipeline Form Extractor
===================================
Aligns with documented RADIANT PCA extraction requirements:
- Phase 1: Structured Data Harvesting (Athena materialized views)
- Phase 2: Clinical Timeline Construction (longitudinal feature layers)
- Phase 3: THREE-TIER Document Selection Strategy with time windows
- Phase 4: Enhanced LLM Extraction (with query validation)
- Phase 5: Cross-Source Validation (multi-source aggregation)

Critical Features Per Documentation:
- Three-tier retrieval: Primary (±7d), Secondary (±14d), Tertiary (±30d)
- Strategic fallback mechanism with 78% recovery rate
- Post-operative imaging validation (24-72 hours) as GOLD STANDARD
- Confidence scoring: base 0.6 + agreement_bonus + source_quality_bonus
- Event-based extraction anchored on surgical events
- Minimum 2 sources for critical variables
"""

import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import sys

# Import all 5 phases
sys.path.append(str(Path(__file__).parent.parent))

# Set up logger before using it
logger = logging.getLogger(__name__)

from event_based_extraction.phase1_structured_harvester import StructuredDataHarvester
from event_based_extraction.phase2_timeline_builder import ClinicalTimelineBuilder, ClinicalEvent
from event_based_extraction.phase3_intelligent_document_selector import IntelligentDocumentSelector
from event_based_extraction.phase4_enhanced_llm_extraction import EnhancedLLMExtractor
from event_based_extraction.phase5_cross_source_validation import CrossSourceValidator
from event_based_extraction.enhanced_extraction_with_fallback import StrategicDocumentRetriever

# Import MISSING critical components for complete integration
try:
    from event_based_extraction.molecular_diagnosis_integration import MolecularDiagnosisIntegration
    from event_based_extraction.problem_list_analyzer import ProblemListAnalyzer
    from event_based_extraction.comprehensive_chemotherapy_identifier import ChemotherapyIdentifier
    from event_based_extraction.tumor_surgery_classifier import TumorSurgeryClassifier
except ImportError as e:
    logger.warning(f"Some components not available: {e}")
    MolecularDiagnosisIntegration = None
    ProblemListAnalyzer = None
    ChemotherapyIdentifier = None
    TumorSurgeryClassifier = None

# Import form extractors
from .diagnosis_form_extractor import DiagnosisFormExtractor
from .treatment_form_extractor import TreatmentFormExtractor
from .demographics_form_extractor import DemographicsFormExtractor
from .medical_history_form_extractor import MedicalHistoryFormExtractor
from .concomitant_medications_form_extractor import ConcomitantMedicationsFormExtractor
from .redcap_terminology_mapper import REDCapTerminologyMapper

# Import staging views configuration
from .staging_views_config import (
    StagingViewsConfiguration,
    FORM_EXTRACTION_CONFIG,
    get_required_staging_files,
    get_critical_queries,
    validate_staging_directory
)

# Import query engine for LLM-enabled extraction
from .structured_data_query_engine import StructuredDataQueryEngine

logger = logging.getLogger(__name__)


class IntegratedPipelineExtractor:
    """
    Master extractor that properly orchestrates the entire 5-phase pipeline
    for comprehensive clinical data extraction.

    This class ensures we use:
    1. Materialized Athena views for structured data
    2. Longitudinal patient feature layers
    3. Intelligent document prioritization
    4. Multi-source evidence aggregation
    5. Post-operative imaging validation
    """

    def __init__(self,
                 staging_base_path: str,
                 binary_files_path: str,
                 data_dictionary_path: str,
                 ollama_model: str = "gemma2:27b"):
        """
        Initialize the integrated pipeline extractor.

        Args:
            staging_base_path: Base path to staging directory with Athena data
            binary_files_path: Path to binary document files
            data_dictionary_path: Path to CBTN data dictionary
            ollama_model: Ollama model to use for extraction
        """
        self.staging_base_path = Path(staging_base_path)
        self.binary_files_path = Path(binary_files_path)
        self.data_dictionary_path = data_dictionary_path
        self.ollama_model = ollama_model

        # Initialize all 5 phases
        self.phase1_harvester = StructuredDataHarvester(self.staging_base_path)
        self.phase2_timeline_builder = None  # Initialized per patient
        self.phase3_document_selector = IntelligentDocumentSelector(
            self.staging_base_path, self.binary_files_path
        )
        self.phase4_llm_extractor = EnhancedLLMExtractor(
            self.staging_base_path, ollama_model
        )
        self.phase5_validator = CrossSourceValidator()

        # Initialize strategic fallback retriever
        self.fallback_retriever = StrategicDocumentRetriever(self.staging_base_path)

        # Initialize terminology mapper
        self.terminology_mapper = REDCapTerminologyMapper(data_dictionary_path)

        # Initialize query engine (per patient)
        self.query_engine = None

        # Initialize missing critical components
        self.molecular_integrator = MolecularDiagnosisIntegration(self.staging_base_path) if MolecularDiagnosisIntegration else None
        self.problem_list_analyzer = ProblemListAnalyzer(self.staging_base_path) if ProblemListAnalyzer else None
        self.chemo_identifier = ChemotherapyIdentifier() if ChemotherapyIdentifier else None
        self.surgery_classifier = TumorSurgeryClassifier() if TumorSurgeryClassifier else None

        # Initialize form-specific extractors (will be refactored to use pipeline)
        self.form_extractors = {
            'diagnosis': DiagnosisFormExtractor(data_dictionary_path),
            'treatment': TreatmentFormExtractor(data_dictionary_path),
            'demographics': DemographicsFormExtractor(data_dictionary_path),
            'medical_history': MedicalHistoryFormExtractor(data_dictionary_path),
            'concomitant_medications': ConcomitantMedicationsFormExtractor(data_dictionary_path)
        }

        # Track extraction statistics
        self.stats = {
            'total_extractions': 0,
            'successful': 0,
            'fallback_triggered': 0,
            'imaging_validations': 0,
            'discrepancies_found': 0,
            'confidence_scores': []
        }

    def extract_patient_comprehensive(self,
                                     patient_id: str,
                                     birth_date: str) -> Dict[str, Any]:
        """
        Perform comprehensive extraction for a patient using the full 5-phase pipeline.

        Args:
            patient_id: Patient FHIR ID
            birth_date: Patient birth date (YYYY-MM-DD)

        Returns:
            Complete extraction results with all forms and events
        """
        logger.info("=" * 80)
        logger.info(f"INTEGRATED PIPELINE EXTRACTION FOR PATIENT {patient_id}")
        logger.info("=" * 80)

        extraction_start = datetime.now()

        # Initialize query engine for this patient
        self.query_engine = StructuredDataQueryEngine(
            self.staging_base_path,
            patient_id
        )

        # Validate staging directory has required files
        staging_validation = validate_staging_directory(
            self.staging_base_path / f"patient_{patient_id}"
        )
        logger.info(f"Staging files validation: {sum(staging_validation.values())}/{len(staging_validation)} available")

        # =================================================================
        # PHASE 1: COMPREHENSIVE STRUCTURED DATA HARVESTING
        # Load all materialized views from Athena + Missing Components
        # =================================================================
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: COMPREHENSIVE STRUCTURED DATA HARVESTING")
        logger.info("=" * 60)

        structured_features = self.phase1_harvester.harvest_for_patient(
            patient_id, birth_date
        )

        # ENRICH with missing critical components
        structured_features = self._enrich_structured_features(
            structured_features, patient_id, birth_date
        )

        logger.info(f"✓ Harvested {len(structured_features)} structured features")
        logger.info(f"  - Total surgeries: {structured_features.get('total_surgeries', 0)}")
        logger.info(f"  - Has chemotherapy: {structured_features.get('has_chemotherapy', 'No')}")
        logger.info(f"  - Has radiation: {structured_features.get('has_radiation', 'No')}")
        logger.info(f"  - Molecular tests: {len(structured_features.get('molecular_markers', []))}")
        logger.info(f"  - Problem list items: {structured_features.get('total_problems', 0)}")
        logger.info(f"  - Service requests: {len(structured_features.get('diagnostic_cascade', {}))}")

        # =================================================================
        # PHASE 2: CLINICAL TIMELINE CONSTRUCTION
        # Build longitudinal patient feature layers
        # =================================================================
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 2: CLINICAL TIMELINE CONSTRUCTION")
        logger.info("=" * 60)

        self.phase2_timeline_builder = ClinicalTimelineBuilder(
            self.staging_base_path, structured_features
        )

        clinical_timeline = self.phase2_timeline_builder.build_timeline(
            patient_id, birth_date
        )

        logger.info(f"✓ Built clinical timeline with {len(clinical_timeline)} events")

        # Group events by type
        surgical_events = [e for e in clinical_timeline if e.event_type == 'surgery']
        diagnosis_events = [e for e in clinical_timeline if e.event_type == 'initial_diagnosis']
        progression_events = [e for e in clinical_timeline if e.event_type == 'progression']

        logger.info(f"  - Surgical events: {len(surgical_events)}")
        logger.info(f"  - Diagnosis events: {len(diagnosis_events)}")
        logger.info(f"  - Progression events: {len(progression_events)}")

        # =================================================================
        # PROCESS EACH CLINICAL EVENT
        # =================================================================

        extraction_results = {
            'patient_id': patient_id,
            'birth_date': birth_date,
            'extraction_timestamp': extraction_start.isoformat(),
            'structured_features': structured_features,
            'clinical_timeline': [self._serialize_event(e) for e in clinical_timeline],
            'forms': {},
            'events': []
        }

        # Process each surgical event (highest priority)
        for event_idx, surgical_event in enumerate(surgical_events, 1):
            logger.info("\n" + "-" * 60)
            logger.info(f"PROCESSING SURGICAL EVENT {event_idx}/{len(surgical_events)}")
            logger.info(f"Event Date: {surgical_event.event_date.date()}")
            logger.info(f"Age at Event: {surgical_event.age_at_event_days} days")
            logger.info("-" * 60)

            event_results = self._process_clinical_event(
                patient_id,
                surgical_event,
                structured_features,
                clinical_timeline
            )

            extraction_results['events'].append(event_results)

        # =================================================================
        # EXTRACT STATIC FORMS (Demographics, Medical History)
        # =================================================================
        logger.info("\n" + "=" * 60)
        logger.info("EXTRACTING STATIC FORMS")
        logger.info("=" * 60)

        # Demographics (uses structured data)
        demographics = self._extract_demographics_integrated(
            patient_id, structured_features
        )
        extraction_results['forms']['demographics'] = demographics

        # Medical History (uses problem list and genetic testing)
        medical_history = self._extract_medical_history_integrated(
            patient_id, structured_features, clinical_timeline
        )
        extraction_results['forms']['medical_history'] = medical_history

        # =================================================================
        # CALCULATE QUALITY METRICS
        # =================================================================
        extraction_results['quality_metrics'] = self._calculate_quality_metrics()

        extraction_duration = (datetime.now() - extraction_start).total_seconds()
        extraction_results['extraction_duration_seconds'] = extraction_duration

        logger.info("\n" + "=" * 60)
        logger.info("EXTRACTION COMPLETE")
        logger.info(f"Total Duration: {extraction_duration:.1f} seconds")
        logger.info(f"Success Rate: {self.stats['successful']}/{self.stats['total_extractions']}")
        logger.info(f"Fallback Rate: {self.stats['fallback_triggered']}/{self.stats['total_extractions']}")
        logger.info(f"Discrepancies Found: {self.stats['discrepancies_found']}")
        logger.info("=" * 60)

        return extraction_results

    def _process_clinical_event(self,
                               patient_id: str,
                               event: ClinicalEvent,
                               structured_features: Dict,
                               timeline: List[ClinicalEvent]) -> Dict:
        """
        Process a single clinical event through phases 3-5 using THREE-TIER retrieval strategy.
        """
        self.stats['total_extractions'] += 1

        # Create timeline context for this event
        timeline_context = {
            'event_date': event.event_date,
            'event_type': event.event_type,
            'age_at_event': event.age_at_event_days,
            'event_number': self._get_event_number(event, timeline),
            'time_since_diagnosis': self._get_time_since_diagnosis(event, timeline),
            'previous_events': self._get_previous_events(event, timeline),
            'structured_features': structured_features
        }

        # =================================================================
        # PHASE 3: THREE-TIER DOCUMENT SELECTION STRATEGY
        # =================================================================
        logger.info("\nPHASE 3: THREE-TIER DOCUMENT SELECTION")

        # Implement the documented three-tier retrieval strategy
        priority_documents = self._retrieve_three_tier_documents(
            patient_id, event.event_date
        )

        logger.info(f"✓ Selected {len(priority_documents)} priority documents")

        # Categorize documents
        doc_categories = self._categorize_documents(priority_documents)
        for category, count in doc_categories.items():
            if count > 0:
                logger.info(f"  - {category}: {count} documents")

        # =================================================================
        # PHASE 4: ENHANCED LLM EXTRACTION
        # =================================================================
        logger.info("\nPHASE 4: ENHANCED LLM EXTRACTION")

        # Define variables to extract based on event type
        if event.event_type == 'surgery':
            target_variables = [
                'extent_of_tumor_resection',
                'tumor_location',
                'surgery_type',
                'specimen_to_cbtn',
                'histopathology',
                'who_grade',
                'molecular_testing'
            ]
        else:
            target_variables = [
                'tumor_status',
                'progression_site',
                'treatment_response'
            ]

        extraction_results = {}

        for variable in target_variables:
            logger.info(f"  Extracting: {variable}")

            # Get relevant documents for this variable
            variable_docs = self._select_documents_for_variable(
                variable, priority_documents
            )

            # Extract with structured context
            result = self.phase4_llm_extractor.extract_with_structured_context(
                patient_id,
                variable,
                variable_docs,
                timeline_context
            )

            # Strategic Fallback Mechanism (78% recovery rate documented)
            if self._needs_fallback(result, variable):
                logger.info(f"    → Triggering STRATEGIC FALLBACK for {variable}")
                self.stats['fallback_triggered'] += 1

                # Implement strategic fallback per documentation
                fallback_result = self._execute_strategic_fallback(
                    patient_id,
                    variable,
                    event.event_date,
                    priority_documents,
                    timeline_context
                )

                if fallback_result and fallback_result.get('confidence', 0) > result.get('confidence', 0):
                    result = fallback_result
                    result['fallback_used'] = True
                    result['fallback_strategy'] = 'strategic_expansion'
                    logger.info(f"      ✓ Fallback successful: confidence {fallback_result.get('confidence', 0):.2f}")

            extraction_results[variable] = result

        # =================================================================
        # PHASE 5: CROSS-SOURCE VALIDATION
        # =================================================================
        logger.info("\nPHASE 5: CROSS-SOURCE VALIDATION")

        # Validate extractions across sources
        validated_results = self.phase5_validator.validate_extractions(
            extraction_results,
            priority_documents
        )

        # CRITICAL: Post-operative imaging validation for extent (24-72 hours window)
        if 'extent_of_tumor_resection' in validated_results and event.event_type == 'surgery':
            logger.info("  ! PERFORMING POST-OP IMAGING VALIDATION (24-72 hours)")
            self.stats['imaging_validations'] += 1

            # Use query engine to get post-op imaging in critical window
            postop_imaging = self.query_engine.QUERY_POSTOP_IMAGING(
                event.event_date.strftime('%Y-%m-%d')
            )

            if postop_imaging:
                logger.info(f"    Found post-op imaging at {postop_imaging['hours_post_surgery']} hours")

                original_extent = validated_results['extent_of_tumor_resection'].get('value')
                imaging_extent = postop_imaging.get('extent')

                if original_extent != imaging_extent and imaging_extent != 'Unable to determine':
                    logger.warning(f"    ⚠️ DISCREPANCY DETECTED!")
                    logger.warning(f"    Operative note: {original_extent}")
                    logger.warning(f"    Post-op imaging: {imaging_extent}")
                    logger.warning(f"    → Using imaging as GOLD STANDARD")
                    self.stats['discrepancies_found'] += 1

                    # Override with imaging (GOLD STANDARD per documentation)
                    validated_results['extent_of_tumor_resection'] = {
                        'value': imaging_extent,
                        'confidence': 0.95,  # Highest confidence for post-op imaging
                        'source': 'post_operative_imaging_24_72h',
                        'validation': 'GOLD_STANDARD_OVERRIDE',
                        'original_value': original_extent,
                        'discrepancy': True,
                        'imaging_hours_post_surgery': postop_imaging['hours_post_surgery'],
                        'override_reason': 'Post-operative MRI (24-72h) is gold standard per protocol'
                    }
                else:
                    validated_results['extent_of_tumor_resection']['validation'] = 'imaging_confirmed'
                    validated_results['extent_of_tumor_resection']['confidence'] = 0.95
                    logger.info(f"    ✓ Imaging confirms extent: {imaging_extent}")
            else:
                logger.warning("    ⚠️ No post-op imaging found in 24-72 hour window")
                # Flag for manual review if no post-op imaging available
                validated_results['extent_of_tumor_resection']['requires_review'] = True
                validated_results['extent_of_tumor_resection']['review_reason'] = 'No post-op imaging validation available'

        # Map to REDCap terminology
        for variable, result in validated_results.items():
            if 'value' in result:
                mapped_value, other_text = self.terminology_mapper.map_to_vocabulary(
                    variable, result['value']
                )
                result['redcap_value'] = mapped_value
                if other_text:
                    result[f'{variable}_other'] = other_text

        # Update statistics
        for result in validated_results.values():
            self.stats['confidence_scores'].append(result.get('confidence', 0))

        self.stats['successful'] += 1

        return {
            'event_date': event.event_date.isoformat(),
            'event_type': event.event_type,
            'event_id': event.event_id,
            'age_at_event_days': event.age_at_event_days,
            'extracted_variables': validated_results,
            'document_stats': {
                'total_documents': len(priority_documents),
                'documents_by_type': doc_categories
            },
            'extraction_metadata': {
                'fallback_triggered': any(
                    r.get('fallback_used', False)
                    for r in validated_results.values()
                ),
                'imaging_validation': 'extent_of_tumor_resection' in validated_results
            }
        }

    def _extract_demographics_integrated(self,
                                        patient_id: str,
                                        structured_features: Dict) -> Dict:
        """
        Extract demographics using structured data from Phase 1.
        """
        demographics = {}

        # Get from structured features first
        if 'patient_gender' in structured_features:
            gender = structured_features['patient_gender']
            demographics['legal_sex'] = {
                'value': gender,
                'confidence': 0.95,
                'source': 'patient_table',
                'structured': True
            }

        # Race and ethnicity might need document extraction
        # For now, return structured data
        demographics['race'] = {
            'value': structured_features.get('patient_race', 'Unavailable'),
            'confidence': 0.80,
            'source': 'structured_or_documents'
        }

        demographics['ethnicity'] = {
            'value': structured_features.get('patient_ethnicity', 'Unavailable'),
            'confidence': 0.80,
            'source': 'structured_or_documents'
        }

        return demographics

    def _extract_medical_history_integrated(self,
                                          patient_id: str,
                                          structured_features: Dict,
                                          timeline: List[ClinicalEvent]) -> Dict:
        """
        Extract medical history using structured features and timeline.
        """
        medical_history = {}

        # Check for cancer predisposition from problem list
        if 'problem_list' in structured_features:
            predispositions = self._identify_predisposition_conditions(
                structured_features['problem_list']
            )

            medical_history['cancer_predisposition'] = {
                'value': predispositions if predispositions else 'None documented',
                'confidence': 0.90,
                'source': 'problem_list'
            }

        # Check for germline testing from molecular tests
        if 'molecular_tests' in structured_features:
            germline = any('germline' in test.lower()
                          for test in structured_features['molecular_tests'])

            medical_history['germline'] = {
                'value': 'Yes' if germline else 'No',
                'confidence': 0.85,
                'source': 'molecular_tests'
            }

        # Family history would need document extraction
        medical_history['family_history'] = {
            'value': 'Unavailable',
            'confidence': 0.0,
            'source': 'requires_document_extraction'
        }

        return medical_history

    def _categorize_documents(self, documents: pd.DataFrame) -> Dict[str, int]:
        """Categorize documents by type."""
        if documents.empty:
            return {}

        categories = {}
        if 'dr_type_text' in documents.columns:
            for doc_type in ['operative', 'pathology', 'imaging', 'progress', 'consultation']:
                count = documents['dr_type_text'].str.contains(
                    doc_type, case=False, na=False
                ).sum()
                categories[doc_type] = count

        return categories

    def _select_documents_for_variable(self,
                                      variable: str,
                                      documents: pd.DataFrame) -> List[Dict]:
        """
        Select most relevant documents for a specific variable.
        """
        if documents.empty:
            return []

        # Define document preferences per variable
        variable_preferences = {
            'extent_of_tumor_resection': ['operative', 'discharge', 'imaging'],
            'tumor_location': ['operative', 'imaging', 'pathology'],
            'histopathology': ['pathology', 'molecular'],
            'molecular_testing': ['molecular', 'pathology', 'genetic']
        }

        preferred_types = variable_preferences.get(
            variable, ['operative', 'pathology', 'imaging']
        )

        selected_docs = []
        for doc_type in preferred_types:
            if 'dr_type_text' in documents.columns:
                matching = documents[
                    documents['dr_type_text'].str.contains(
                        doc_type, case=False, na=False
                    )
                ]

                for _, doc in matching.head(3).iterrows():
                    selected_docs.append(doc.to_dict())

        return selected_docs[:5]  # Limit to 5 documents

    def _get_event_number(self,
                         event: ClinicalEvent,
                         timeline: List[ClinicalEvent]) -> int:
        """Get the sequential number of this event in the timeline."""
        same_type_events = [e for e in timeline
                           if e.event_type == event.event_type
                           and e.event_date <= event.event_date]
        return len(same_type_events)

    def _get_time_since_diagnosis(self,
                                 event: ClinicalEvent,
                                 timeline: List[ClinicalEvent]) -> Optional[int]:
        """Get days since initial diagnosis."""
        diagnosis_events = [e for e in timeline
                           if e.event_type == 'initial_diagnosis']
        if diagnosis_events:
            first_diagnosis = min(diagnosis_events, key=lambda e: e.event_date)
            return (event.event_date - first_diagnosis.event_date).days
        return None

    def _get_previous_events(self,
                           event: ClinicalEvent,
                           timeline: List[ClinicalEvent]) -> List[Dict]:
        """Get summary of previous events."""
        previous = [e for e in timeline if e.event_date < event.event_date]
        return [
            {
                'date': e.event_date.isoformat(),
                'type': e.event_type,
                'description': e.description
            }
            for e in previous[-5:]  # Last 5 events
        ]

    def _identify_predisposition_conditions(self, problem_list: List[str]) -> List[str]:
        """Identify cancer predisposition syndromes from problem list."""
        predisposition_keywords = {
            'NF1': 'Neurofibromatosis Type 1',
            'NF2': 'Neurofibromatosis Type 2',
            'Li-Fraumeni': 'Li-Fraumeni syndrome',
            'Gorlin': 'Gorlin Syndrome',
            'TSC': 'Tuberous Sclerosis',
            'VHL': 'Von Hippel-Lindau'
        }

        found = []
        for problem in problem_list:
            for keyword, name in predisposition_keywords.items():
                if keyword.lower() in problem.lower():
                    found.append(name)

        return found

    def _categorize_documents(self, documents: List[Dict]) -> Dict[str, int]:
        """Categorize documents by type."""
        categories = {}
        for doc in documents:
            doc_type = doc.get('document_type', 'unknown')
            categories[doc_type] = categories.get(doc_type, 0) + 1
        return categories

    def _select_documents_for_variable(self,
                                      variable: str,
                                      all_documents: List[Dict]) -> List[Dict]:
        """Select relevant documents for a specific variable."""
        # Variable-specific document selection
        variable_doc_map = {
            'extent_of_tumor_resection': ['operative_note', 'pathology_report', 'imaging_report'],
            'tumor_location': ['imaging_report', 'operative_note', 'pathology_report'],
            'histopathology': ['pathology_report'],
            'who_grade': ['pathology_report'],
            'molecular_testing': ['molecular_report', 'pathology_report']
        }

        relevant_types = variable_doc_map.get(variable, ['any'])

        if 'any' in relevant_types:
            return all_documents

        # Filter documents by type
        relevant_docs = []
        for doc in all_documents:
            if doc.get('document_type') in relevant_types:
                relevant_docs.append(doc)

        # If no relevant docs found, include all as fallback
        if not relevant_docs:
            relevant_docs = all_documents

        return relevant_docs

    def _serialize_event(self, event: ClinicalEvent) -> Dict:
        """Serialize ClinicalEvent to dict."""
        return {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'event_date': event.event_date.isoformat(),
            'age_at_event_days': event.age_at_event_days,
            'description': event.description,
            'procedure_codes': event.procedure_codes,
            'diagnosis_codes': event.diagnosis_codes
        }

    def _retrieve_three_tier_documents(self,
                                      patient_id: str,
                                      event_date: datetime) -> List[Dict]:
        """
        Implement THREE-TIER document retrieval strategy per documentation.

        Tier 1: Primary Sources (±7 days)
        - Operative notes, Pathology reports
        - Post-op imaging (24-72 hours) - HIGHEST PRIORITY for extent

        Tier 2: Secondary Sources (±14 days)
        - Discharge summaries, Pre-op imaging
        - Oncology consultation notes

        Tier 3: Tertiary Sources (±30 days)
        - Progress notes, Athena free-text fields
        - Any radiology reports with anatomical keywords
        """
        all_documents = []

        # TIER 1: Primary Sources (±7 days window)
        logger.info("  TIER 1: Retrieving primary sources (±7 days)")
        primary_window = timedelta(days=7)

        tier1_docs = self._get_documents_in_window(
            patient_id,
            event_date,
            primary_window,
            document_types=['operative_note', 'pathology_report']
        )

        # Special handling for post-op imaging (24-72 hours)
        postop_window_start = event_date + timedelta(hours=24)
        postop_window_end = event_date + timedelta(hours=72)
        postop_imaging = self._get_postop_imaging_documents(
            patient_id,
            postop_window_start,
            postop_window_end
        )

        tier1_docs.extend(postop_imaging)
        logger.info(f"    Found {len(tier1_docs)} primary documents")

        # Add tier designation and weight
        for doc in tier1_docs:
            doc['tier'] = 1
            doc['tier_weight'] = 0.95  # Primary sources get highest weight

        all_documents.extend(tier1_docs)

        # TIER 2: Secondary Sources (±14 days window)
        logger.info("  TIER 2: Retrieving secondary sources (±14 days)")
        secondary_window = timedelta(days=14)

        tier2_docs = self._get_documents_in_window(
            patient_id,
            event_date,
            secondary_window,
            document_types=['discharge_summary', 'oncology_note', 'pre_op_imaging']
        )

        # Exclude documents already in Tier 1
        tier1_ids = {d.get('document_id') for d in tier1_docs}
        tier2_docs = [d for d in tier2_docs if d.get('document_id') not in tier1_ids]

        logger.info(f"    Found {len(tier2_docs)} secondary documents")

        for doc in tier2_docs:
            doc['tier'] = 2
            doc['tier_weight'] = 0.75  # Secondary sources get medium weight

        all_documents.extend(tier2_docs)

        # TIER 3: Tertiary Sources (±30 days window) - ONLY if needed
        if len(all_documents) < 10:  # Minimum document threshold
            logger.info("  TIER 3: Retrieving tertiary sources (±30 days)")
            tertiary_window = timedelta(days=30)

            tier3_docs = self._get_documents_in_window(
                patient_id,
                event_date,
                tertiary_window,
                document_types=['progress_note', 'radiology_report', 'clinical_note']
            )

            # Exclude documents already in Tier 1 or 2
            existing_ids = {d.get('document_id') for d in all_documents}
            tier3_docs = [d for d in tier3_docs if d.get('document_id') not in existing_ids]

            logger.info(f"    Found {len(tier3_docs)} tertiary documents")

            for doc in tier3_docs:
                doc['tier'] = 3
                doc['tier_weight'] = 0.55  # Tertiary sources get lower weight

            all_documents.extend(tier3_docs[:20])  # Limit tertiary documents

        return all_documents

    def _get_documents_in_window(self,
                                patient_id: str,
                                event_date: datetime,
                                window: timedelta,
                                document_types: List[str]) -> List[Dict]:
        """Get documents within specified time window."""
        start_date = event_date - window
        end_date = event_date + window

        # This would normally query the document store
        # For now, using the phase3 selector with date filtering
        docs = []

        # Mock implementation - replace with actual document retrieval
        for doc_type in document_types:
            # This would query binary_files.csv and S3
            pass

        return docs

    def _get_postop_imaging_documents(self,
                                     patient_id: str,
                                     start_date: datetime,
                                     end_date: datetime) -> List[Dict]:
        """Get post-operative imaging documents (CRITICAL for extent validation)."""
        # This specifically looks for MRI/CT within 24-72 hours post-surgery
        postop_docs = []

        # Would query imaging.csv for MRI/CT in the specific window
        # These get highest priority for extent validation

        return postop_docs

    def _needs_fallback(self, result: Dict, variable: str) -> bool:
        """
        Determine if strategic fallback is needed based on result quality.

        Critical variables require minimum 2 sources and confidence >= 0.7
        """
        critical_variables = [
            'extent_of_tumor_resection',
            'tumor_location',
            'histopathology',
            'who_grade',
            'metastasis_presence'
        ]

        # Check if unavailable or low confidence
        if result.get('value') == 'Unavailable':
            return True

        confidence = result.get('confidence', 0)

        # Critical variables need higher confidence and multiple sources
        if variable in critical_variables:
            source_count = len(result.get('sources', []))
            if confidence < 0.7 or source_count < 2:
                return True
        else:
            # Non-critical variables just need reasonable confidence
            if confidence < 0.6:
                return True

        return False

    def _execute_strategic_fallback(self,
                                   patient_id: str,
                                   variable: str,
                                   event_date: datetime,
                                   existing_documents: List[Dict],
                                   timeline_context: Dict) -> Optional[Dict]:
        """
        Execute strategic fallback with expanded search windows.

        This implements the 78% recovery rate strategy documented:
        1. Expand temporal window progressively
        2. Include additional document types
        3. Use NLP similarity matching for related documents
        """
        logger.info(f"      Executing strategic fallback for {variable}")

        # Define fallback strategies based on variable type
        fallback_strategies = self._get_fallback_strategies(variable)

        for strategy in fallback_strategies:
            logger.info(f"      Trying strategy: {strategy['name']}")

            # Get additional documents based on strategy
            fallback_docs = self._get_fallback_documents(
                patient_id,
                event_date,
                strategy['window_days'],
                strategy['document_types'],
                existing_documents
            )

            if fallback_docs:
                # Try extraction with fallback documents
                result = self.phase4_llm_extractor.extract_with_structured_context(
                    patient_id,
                    variable,
                    fallback_docs,
                    timeline_context
                )

                # Calculate confidence with proper formula
                result['confidence'] = self._calculate_confidence(
                    result,
                    fallback_docs,
                    is_fallback=True
                )

                if result.get('value') != 'Unavailable' and result.get('confidence', 0) >= 0.6:
                    result['fallback_strategy_used'] = strategy['name']
                    return result

        return None

    def _get_fallback_strategies(self, variable: str) -> List[Dict]:
        """Get ordered fallback strategies for a variable."""
        # Variable-specific strategies based on documentation
        strategies_map = {
            'extent_of_tumor_resection': [
                {'name': 'post_op_imaging_extended', 'window_days': 7, 'document_types': ['imaging_report']},
                {'name': 'discharge_summary', 'window_days': 14, 'document_types': ['discharge_summary']},
                {'name': 'follow_up_notes', 'window_days': 30, 'document_types': ['progress_note', 'oncology_note']}
            ],
            'tumor_location': [
                {'name': 'pre_op_imaging', 'window_days': 30, 'document_types': ['imaging_report']},
                {'name': 'neurology_notes', 'window_days': 60, 'document_types': ['neurology_note', 'clinic_note']}
            ],
            'default': [
                {'name': 'expanded_window', 'window_days': 30, 'document_types': ['any']},
                {'name': 'athena_free_text', 'window_days': 60, 'document_types': ['athena_fields']}
            ]
        }

        return strategies_map.get(variable, strategies_map['default'])

    def _get_fallback_documents(self,
                               patient_id: str,
                               event_date: datetime,
                               window_days: int,
                               document_types: List[str],
                               existing_documents: List[Dict]) -> List[Dict]:
        """Get additional documents for fallback."""
        # Get documents in expanded window
        window = timedelta(days=window_days)
        fallback_docs = self._get_documents_in_window(
            patient_id,
            event_date,
            window,
            document_types
        )

        # Exclude already tried documents
        existing_ids = {d.get('document_id') for d in existing_documents}
        new_docs = [d for d in fallback_docs if d.get('document_id') not in existing_ids]

        # Add fallback tier designation
        for doc in new_docs:
            doc['is_fallback'] = True
            doc['fallback_window'] = window_days

        return new_docs

    def _calculate_confidence(self,
                            result: Dict,
                            documents: List[Dict],
                            is_fallback: bool = False) -> float:
        """
        Calculate confidence score per documented formula:
        confidence = base_confidence + agreement_bonus + source_quality_bonus

        Where:
        - base_confidence = 0.6
        - agreement_bonus = agreement_ratio × 0.3
        - source_quality_bonus = 0.1 × number_of_high_quality_sources
        """
        # Base confidence per documentation
        base_confidence = 0.6

        # Calculate agreement bonus
        agreement_ratio = result.get('agreement_ratio', 0.5)
        agreement_bonus = agreement_ratio * 0.3

        # Calculate source quality bonus
        high_quality_sources = 0
        for doc in documents:
            tier = doc.get('tier', 3)
            if tier == 1:  # Primary sources
                high_quality_sources += 1
            elif tier == 2:  # Secondary sources
                high_quality_sources += 0.5  # Half credit

        source_quality_bonus = min(0.1 * high_quality_sources, 0.3)  # Cap at 0.3

        # Apply penalty for fallback
        if is_fallback:
            base_confidence -= 0.1

        # Calculate final confidence
        confidence = base_confidence + agreement_bonus + source_quality_bonus

        # Ensure within bounds [0.6, 1.0] per documentation
        confidence = max(0.6, min(1.0, confidence))

        return confidence

    def _enrich_structured_features(self,
                                   structured_features: Dict,
                                   patient_id: str,
                                   birth_date: str) -> Dict:
        """
        Enrich structured features with ALL missing critical components.
        This ensures we capture the complete longitudinal context.
        """
        logger.info("  Enriching with missing critical components...")

        # 1. MOLECULAR DIAGNOSIS INTEGRATION
        if self.molecular_integrator:
            try:
                molecular_data = self.molecular_integrator.extract_molecular_diagnosis(patient_id)
                structured_features['molecular_markers'] = molecular_data.get('molecular_markers', [])
                structured_features['molecular_diagnosis'] = molecular_data.get('integrated_diagnosis', {})
                logger.info(f"    ✓ Added molecular data: {len(molecular_data.get('molecular_markers', []))} markers")
            except Exception as e:
                logger.warning(f"    ✗ Molecular integration failed: {e}")
                structured_features['molecular_markers'] = []

        # 2. PROBLEM LIST ANALYSIS
        if self.problem_list_analyzer:
            try:
                problem_analysis = self.problem_list_analyzer.analyze_problem_list(patient_id)
                structured_features['total_problems'] = problem_analysis.get('total_problems', 0)
                structured_features['active_problems'] = problem_analysis.get('active_problems', 0)
                structured_features['earliest_tumor_mention'] = problem_analysis.get('earliest_tumor_mention')
                structured_features['complications'] = problem_analysis.get('complications', [])
                logger.info(f"    ✓ Added problem list: {problem_analysis.get('total_problems', 0)} problems")
            except Exception as e:
                logger.warning(f"    ✗ Problem list analysis failed: {e}")

        # 3. COMPREHENSIVE CHEMOTHERAPY IDENTIFICATION
        if self.chemo_identifier and 'medications' in structured_features:
            try:
                # Apply 5-strategy identification
                enhanced_chemo = self.chemo_identifier.identify_all_chemotherapy(
                    structured_features.get('medications', [])
                )
                structured_features['chemotherapy_drugs_enhanced'] = enhanced_chemo
                structured_features['chemo_identification_methods'] = {
                    'rxnorm_ingredient': len(enhanced_chemo.get('by_ingredient', [])),
                    'product_mapping': len(enhanced_chemo.get('by_product', [])),
                    'name_pattern': len(enhanced_chemo.get('by_pattern', [])),
                    'care_plan': len(enhanced_chemo.get('by_care_plan', [])),
                    'reason_code': len(enhanced_chemo.get('by_reason', []))
                }
                logger.info(f"    ✓ Enhanced chemo identification: {len(enhanced_chemo)} drugs")
            except Exception as e:
                logger.warning(f"    ✗ Chemo enhancement failed: {e}")

        # 4. TUMOR SURGERY CLASSIFICATION
        if self.surgery_classifier and structured_features.get('total_surgeries', 0) > 0:
            try:
                surgery_classifications = self.surgery_classifier.classify_surgeries(
                    structured_features.get('surgery_dates', []),
                    structured_features.get('surgery_types', [])
                )
                structured_features['surgery_classifications'] = surgery_classifications
                structured_features['initial_surgery_date'] = surgery_classifications.get('initial_surgery')
                structured_features['recurrence_surgeries'] = surgery_classifications.get('recurrence_surgeries', [])
                logger.info(f"    ✓ Classified surgeries: {len(surgery_classifications)} events")
            except Exception as e:
                logger.warning(f"    ✗ Surgery classification failed: {e}")

        # 5. SERVICE REQUEST DIAGNOSTIC CASCADE
        try:
            from .service_request_integration import ServiceRequestIntegration
            service_integrator = ServiceRequestIntegration(self.staging_base_path)

            # Map diagnostic cascade for first surgery
            if structured_features.get('first_surgery_date'):
                surgery_date = pd.to_datetime(structured_features['first_surgery_date'])
                cascade = service_integrator.map_diagnostic_cascade(patient_id, surgery_date)
                structured_features['diagnostic_cascade'] = cascade

                # Check post-op imaging compliance
                has_postop = len(cascade.get('immediate_post_operative', [])) > 0
                structured_features['has_postop_imaging_validation'] = has_postop
                logger.info(f"    ✓ Mapped diagnostic cascade: {sum(len(v) for v in cascade.values())} requests")
        except Exception as e:
            logger.warning(f"    ✗ Service request integration failed: {e}")

        # 6. CARE PLAN HIERARCHY
        structured_features['care_plan_hierarchy'] = self._extract_care_plan_hierarchy(patient_id)

        # 7. ENCOUNTER PATTERNS
        structured_features['encounter_patterns'] = self._analyze_encounter_patterns(patient_id)

        return structured_features

    def _extract_care_plan_hierarchy(self, patient_id: str) -> Dict:
        """Extract care plan parent-child relationships."""
        patient_path = self.staging_base_path / f"patient_{patient_id}"
        care_plan_file = patient_path / "care_plans.csv"

        if not care_plan_file.exists():
            return {}

        try:
            care_plans = pd.read_csv(care_plan_file)
            # Extract hierarchy
            hierarchy = {
                'total_plans': len(care_plans),
                'master_plans': len(care_plans[care_plans['part_of'].isna()]) if 'part_of' in care_plans.columns else 0,
                'sub_plans': len(care_plans[care_plans['part_of'].notna()]) if 'part_of' in care_plans.columns else 0
            }
            return hierarchy
        except:
            return {}

    def _analyze_encounter_patterns(self, patient_id: str) -> Dict:
        """Analyze encounter frequency and patterns."""
        patient_path = self.staging_base_path / f"patient_{patient_id}"
        encounters_file = patient_path / "encounters.csv"

        if not encounters_file.exists():
            return {}

        try:
            encounters = pd.read_csv(encounters_file)
            encounters['encounter_date'] = pd.to_datetime(encounters['encounter_date'], errors='coerce')

            # Calculate patterns
            patterns = {
                'total_encounters': len(encounters),
                'encounter_types': encounters['encounter_type'].value_counts().to_dict() if 'encounter_type' in encounters.columns else {},
                'departments': encounters['department'].value_counts().to_dict() if 'department' in encounters.columns else {},
                'admission_count': len(encounters[encounters['encounter_type'] == 'inpatient']) if 'encounter_type' in encounters.columns else 0
            }

            # Calculate encounter frequency by period
            if not encounters.empty and 'encounter_date' in encounters.columns:
                encounters_sorted = encounters.sort_values('encounter_date')
                first_date = encounters_sorted['encounter_date'].min()
                last_date = encounters_sorted['encounter_date'].max()
                duration_days = (last_date - first_date).days if pd.notna(first_date) and pd.notna(last_date) else 0

                if duration_days > 0:
                    patterns['encounters_per_month'] = len(encounters) / (duration_days / 30)

            return patterns
        except:
            return {}

    def _calculate_quality_metrics(self) -> Dict:
        """Calculate extraction quality metrics."""
        total = self.stats['total_extractions']
        if total == 0:
            return {}

        return {
            'extraction_completeness': self.stats['successful'] / total,
            'fallback_trigger_rate': self.stats['fallback_triggered'] / total,
            'imaging_validation_rate': self.stats['imaging_validations'] / total,
            'discrepancy_rate': self.stats['discrepancies_found'] / total,
            'average_confidence': np.mean(self.stats['confidence_scores']) if self.stats['confidence_scores'] else 0,
            'confidence_std': np.std(self.stats['confidence_scores']) if self.stats['confidence_scores'] else 0
        }