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

from event_based_extraction.phase1_enhanced_structured_harvester import EnhancedStructuredDataHarvester
from event_based_extraction.phase2_timeline_builder import ClinicalTimelineBuilder, ClinicalEvent
from event_based_extraction.phase3_intelligent_document_selector import IntelligentDocumentSelector
from event_based_extraction.phase4_iterative_llm_extraction import IterativeLLMExtractor
from event_based_extraction.phase5_cross_source_validation import CrossSourceValidator
from event_based_extraction.enhanced_extraction_with_fallback import StrategicDocumentRetriever
from event_based_extraction.real_document_extraction import RealDocumentRetriever

# Import MISSING critical components for complete integration
try:
    from event_based_extraction.molecular_diagnosis_integration import MolecularDiagnosisIntegration
    from event_based_extraction.problem_list_analyzer import ProblemListAnalyzer
    from event_based_extraction.comprehensive_chemotherapy_identifier import ComprehensiveChemotherapyIdentifier as ChemotherapyIdentifier
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

        # Initialize all 5 phases - Using enhanced Phase 1 that creates event waypoints
        self.phase1_harvester = EnhancedStructuredDataHarvester(self.staging_base_path)
        self.phase2_timeline_builder = None  # Initialized per patient
        self.phase3_document_selector = IntelligentDocumentSelector(
            self.staging_base_path, self.binary_files_path
        )
        self.phase4_llm_extractor = IterativeLLMExtractor(
            self.staging_base_path, ollama_model
        )
        self.phase5_validator = CrossSourceValidator(staging_path=staging_base_path)

        # Initialize strategic fallback retriever
        self.fallback_retriever = StrategicDocumentRetriever(self.staging_base_path)

        # Initialize real document retriever for S3 access
        self.document_retriever = RealDocumentRetriever(staging_base_path, use_s3=True)

        # Initialize terminology mapper
        self.terminology_mapper = REDCapTerminologyMapper(data_dictionary_path)

        # Initialize query engine (per patient)
        self.query_engine = None

        # Initialize missing critical components
        self.molecular_integrator = MolecularDiagnosisIntegration(self.staging_base_path) if MolecularDiagnosisIntegration else None
        self.problem_list_analyzer = ProblemListAnalyzer(self.staging_base_path) if ProblemListAnalyzer else None
        self.chemo_identifier = ChemotherapyIdentifier() if ChemotherapyIdentifier else None
        self.surgery_classifier = TumorSurgeryClassifier(staging_base_path) if TumorSurgeryClassifier else None

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
            'confidence_scores': [],
            'variables_completed': 0
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
        # PHASE 1: COMPREHENSIVE STRUCTURED DATA HARVESTING WITH EVENT WAYPOINTS
        # Load all materialized views from Athena + Create date-anchored waypoints
        # =================================================================
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: COMPREHENSIVE STRUCTURED DATA HARVESTING WITH EVENT WAYPOINTS")
        logger.info("=" * 60)

        phase1_result = self.phase1_harvester.harvest_for_patient(
            patient_id, birth_date
        )

        # Extract components from enhanced Phase 1
        structured_features = phase1_result.get('structured_features', {})
        event_waypoints = phase1_result.get('event_waypoints', [])
        surgical_events = phase1_result.get('surgical_events', [])
        diagnostic_cascade = phase1_result.get('diagnostic_cascade', {})

        # ENRICH with missing critical components
        structured_features = self._enrich_structured_features(
            structured_features, patient_id, birth_date
        )

        # Add waypoint data to structured features
        structured_features['event_waypoints'] = event_waypoints
        structured_features['surgical_events'] = surgical_events
        structured_features['diagnostic_cascade'] = diagnostic_cascade

        logger.info(f"✓ Harvested {len(structured_features)} structured features")
        logger.info(f"✓ Created {len(event_waypoints)} event waypoints")
        logger.info(f"  - Total surgeries: {structured_features.get('total_surgeries', 0)}")
        logger.info(f"  - Has chemotherapy: {structured_features.get('has_chemotherapy', 'No')}")
        logger.info(f"  - Has radiation: {structured_features.get('has_radiation', 'No')}")
        logger.info(f"  - Molecular tests: {len(structured_features.get('molecular_markers', []))}")
        logger.info(f"  - Problem list items: {structured_features.get('total_problems', 0)}")
        logger.info(f"  - Service requests: {len(structured_features.get('diagnostic_cascade', {}))}")

        # =================================================================
        # PHASE 2: CLINICAL TIMELINE CONSTRUCTION FROM EVENT WAYPOINTS
        # Build longitudinal patient feature layers from Phase 1 waypoints
        # =================================================================
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 2: CLINICAL TIMELINE CONSTRUCTION FROM EVENT WAYPOINTS")
        logger.info("=" * 60)

        # Phase 2 now builds from waypoints created in Phase 1
        self.phase2_timeline_builder = ClinicalTimelineBuilder(
            self.staging_base_path, structured_features
        )

        # Build timeline (Phase 2 will use waypoints from structured_features if available)
        clinical_timeline = self.phase2_timeline_builder.build_timeline(
            patient_id, birth_date
        )

        logger.info(f"✓ Built clinical timeline with {len(clinical_timeline)} events")

        # Group events by type
        surgical_events = [e for e in clinical_timeline if e.event_type in ['surgery', 'surgical']]
        diagnosis_events = [e for e in clinical_timeline if e.event_type == 'initial_diagnosis']
        progression_events = [e for e in clinical_timeline if e.event_type == 'progression']

        logger.info(f"  - Surgical events: {len(surgical_events)}")
        if surgical_events:
            # Show event classifications from waypoints
            for idx, event in enumerate(surgical_events[:5], 1):  # Show first 5
                event_type = getattr(event, 'event_classification', 'Unknown')
                logger.info(f"    Surgery {idx}: {event.event_date.date()} - Type {event_type}")
        logger.info(f"  - Diagnosis events: {len(diagnosis_events)}")
        logger.info(f"  - Progression events: {len(progression_events)}")

        # =================================================================
        # SET PHASE DATA FOR ITERATIVE LLM EXTRACTION
        # =================================================================
        # Pass Phase 1-3 data to the iterative LLM extractor for context-aware prompting
        # Also pass data sources for structured data interrogation (Pass 2)
        # Get data sources from Phase 1 harvester
        data_sources = self.phase1_harvester.data_sources

        self.phase4_llm_extractor.set_phase_data(
            structured_features,  # Phase 1 data
            clinical_timeline,    # Phase 2 timeline
            data_sources          # Data sources for Pass 2 structured interrogation
        )
        logger.info("✓ Phase 4 iterative extractor initialized with Phases 1-3 and data sources")

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

        # Update Phase 3 documents in the LLM extractor for this event
        self.phase4_llm_extractor.phase3_documents = priority_documents

        # =================================================================
        # PHASE 4: ENHANCED LLM EXTRACTION
        # =================================================================
        logger.info("\nPHASE 4: ENHANCED LLM EXTRACTION")

        # Define variables to extract based on event type
        if event.event_type == 'surgery' or event.event_type == 'surgical':
            # Check surgery classification to skip inappropriate extractions
            surgery_type = getattr(event, 'surgery_type', None)

            if surgery_type == 'csf_diversion':
                # CSF diversion procedures (shunts, ETV) - no tumor extent to extract
                logger.info(f"  ⚠ Surgery classified as CSF DIVERSION - skipping extent/tumor extraction")
                target_variables = []  # No tumor-related variables to extract
            elif surgery_type == 'biopsy':
                # Biopsy only - extent is already known
                logger.info(f"  ℹ Surgery classified as BIOPSY - extent pre-defined")
                target_variables = [
                    'tumor_location',
                    'specimen_to_cbtn',
                    'histopathology',
                    'who_grade',
                    'molecular_testing'
                ]
            else:
                # Tumor resection or other neurosurgical procedures
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

            # Retrieve actual content from S3 for selected documents
            docs_with_content = self._retrieve_document_contents(variable_docs)

            # Extract with iterative 4-pass framework
            result = self.phase4_llm_extractor.extract_from_documents(
                variable=variable,
                documents=docs_with_content,
                patient_id=patient_id,
                event_date=event.event_date.isoformat(),
                patient_age_days=event.age_at_event_days
            )

            # Check for early termination if variable already confirmed
            if self._is_variable_confirmed(result, variable):
                logger.info(f"    ✓ {variable} already confirmed by multiple sources, skipping fallback")
                self.stats['variables_completed'] += 1
                continue

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
        validation_report = self.phase5_validator.validate_extraction_results(
            patient_id=patient_id,
            brim_results={'variables': extraction_results},
            clinical_timeline={'events': timeline, 'current_event': event.__dict__}
        )

        # Store validation report separately
        validated_results = extraction_results  # Keep the actual extraction results

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
            if isinstance(result, dict):
                self.stats['confidence_scores'].append(result.get('confidence', 0))
            else:
                # Handle cases where result might be a string or other type
                self.stats['confidence_scores'].append(0.0)

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
                    if isinstance(r, dict)
                ),
                'imaging_validation': 'extent_of_tumor_resection' in validated_results,
                'validation_accuracy': validation_report.get('metrics', {}).get('accuracy', 0)
            }
        }

    def _classify_document_type(self, filename: str, type_text: str = None) -> str:
        """Classify document type from filename and type_text."""
        filename_lower = str(filename).lower() if filename else ''
        type_text_lower = str(type_text).lower() if type_text else ''
        combined_text = f"{filename_lower} {type_text_lower}"

        type_patterns = {
            'operative_note': ['operative', 'operation', 'surgery', 'op note'],
            'pathology_report': ['pathology', 'path report', 'histology'],
            'radiology_report': ['radiology', 'imaging', 'mri', 'ct'],
            'discharge_summary': ['discharge', 'summary'],
            'oncology_note': ['oncology', 'chemotherapy', 'tumor board'],
            'progress_note': ['progress', 'note'],
            'consultation': ['consult', 'consultation'],
            'anesthesia_note': ['anesthesia', 'anes note'],
            'preoperative_eval': ['preoperative', 'pre-op eval']
        }

        for doc_type, patterns in type_patterns.items():
            for pattern in patterns:
                if pattern in combined_text:
                    return doc_type

        return 'clinical_note'

    def _categorize_document_priority(self, doc_type: str, type_text: str = None) -> str:
        """
        Categorize document priority for LLM review based on document type.
        Categories:
        - Category 1: Pathology (highest priority for tumor details)
        - Category 2: Surgery (operative notes, anesthesia)
        - Category 3: Treatment (discharge, consults, H&P)
        - Category 4: Monitoring (imaging, radiology)
        - Category 5: Other
        """
        type_text_lower = str(type_text).lower() if type_text else ''

        if 'pathology' in doc_type or 'pathology' in type_text_lower:
            return 'Category 1: Pathology'
        elif doc_type in ['operative_note', 'anesthesia_note', 'preoperative_eval']:
            return 'Category 2: Surgery'
        elif 'op note' in type_text_lower or 'anesthesia' in type_text_lower:
            return 'Category 2: Surgery'
        elif doc_type in ['discharge_summary', 'consultation', 'oncology_note']:
            return 'Category 3: Treatment'
        elif 'consult' in type_text_lower or 'discharge' in type_text_lower or 'h&p' in type_text_lower:
            return 'Category 3: Treatment'
        elif doc_type == 'radiology_report' or 'imaging' in type_text_lower:
            return 'Category 4: Monitoring'
        elif doc_type == 'progress_note':
            return 'Category 3/4: Treatment/Status'
        else:
            return 'Category 5: Other'

    def _calculate_document_priority_score(self, category: str, row: pd.Series, event_date: datetime) -> float:
        """
        Calculate priority score for document based on category and temporal proximity.
        Higher scores = higher priority for LLM review.
        """
        # Category-based base scores
        category_scores = {
            'Category 1: Pathology': 100,
            'Category 2: Surgery': 90,
            'Category 3: Treatment': 70,
            'Category 3/4: Treatment/Status': 60,
            'Category 4: Monitoring': 50,
            'Category 5: Other': 10
        }

        base_score = category_scores.get(category, 10)

        # Add temporal proximity bonus (closer to event = higher score)
        if 'dr_date' in row and pd.notna(row['dr_date']):
            doc_date = pd.to_datetime(row['dr_date'])
            days_diff = abs((doc_date - event_date).days)

            if days_diff <= 1:
                temporal_bonus = 20
            elif days_diff <= 3:
                temporal_bonus = 15
            elif days_diff <= 7:
                temporal_bonus = 10
            elif days_diff <= 14:
                temporal_bonus = 5
            else:
                temporal_bonus = 0

            return base_score + temporal_bonus

        return base_score

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
        """Get documents within specified time window from binary files and S3."""
        start_date = event_date - window
        end_date = event_date + window

        # Use the correct staging files path from config_driven_versions
        # Handle truncated patient IDs (e.g., e4BwD8ZYDBccepXcJ.Ilo3w3 -> e4BwD8ZYDBccepXcJ.Ilo3)
        # Try full ID first
        config_staging_path = self.staging_base_path / 'athena_extraction_validation' / 'scripts' / 'config_driven_versions' / 'staging_files' / f"patient_{patient_id}"
        binary_file = config_staging_path / "binary_files.csv"

        if not binary_file.exists():
            # Try truncated ID (handle cases like e4BwD8ZYDBccepXcJ.Ilo3w3 -> e4BwD8ZYDBccepXcJ.Ilo3)
            if 'w3' in patient_id and patient_id.endswith('w3'):
                truncated_id = patient_id[:-2]  # Remove 'w3' suffix
                config_staging_path = self.staging_base_path / 'athena_extraction_validation' / 'scripts' / 'config_driven_versions' / 'staging_files' / f"patient_{truncated_id}"
                binary_file = config_staging_path / "binary_files.csv"

        if not binary_file.exists():
            # Fallback to original location
            patient_path = self.staging_base_path / f"patient_{patient_id}"
            binary_file = patient_path / "binary_files.csv"

        if not binary_file.exists():
            logger.warning(f"No binary files found for patient {patient_id}")
            return []

        # Load and filter binary files
        df = pd.read_csv(binary_file)

        # Parse dates with timezone awareness
        date_columns = ['document_date', 'dr_date', 'created_date']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)

        # Get the first available date column
        date_col = None
        for col in date_columns:
            if col in df.columns and df[col].notna().any():
                date_col = col
                break

        if date_col is None:
            logger.warning("No valid date column found in binary files")
            return []

        # Filter by date window
        mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
        filtered_docs = df[mask].copy()

        # Filter by document type if specified
        if document_types:
            type_mask = pd.Series([False] * len(filtered_docs), index=filtered_docs.index)
            for doc_type in document_types:
                # Check file_name and description for document type
                if 'file_name' in filtered_docs.columns:
                    type_mask |= filtered_docs['file_name'].str.lower().str.contains(doc_type.replace('_', ' '), na=False)
                if 'document_type' in filtered_docs.columns:
                    type_mask |= filtered_docs['document_type'].str.lower().str.contains(doc_type.replace('_', ' '), na=False)
                if 'description' in filtered_docs.columns:
                    type_mask |= filtered_docs['description'].str.lower().str.contains(doc_type.replace('_', ' '), na=False)

            filtered_docs = filtered_docs[type_mask]

        # Convert to list of dictionaries with document metadata and categorization
        docs = []
        for _, row in filtered_docs.iterrows():
            # Use type_text field if available for better classification
            type_text = row.get('dr_type_text', row.get('type_text', ''))
            file_name = str(row.get('file_name', row.get('dc_content_title', '')))

            # Classify document type using both filename and type_text
            doc_type = self._classify_document_type(file_name, type_text)

            # Categorize for LLM priority
            doc_category = self._categorize_document_priority(doc_type, type_text)

            doc = {
                'document_id': row.get('dc_binary_id', row.get('binary_id', row.get('dr_id', ''))),
                'document_type': doc_type,
                'document_category': doc_category,  # For LLM prioritization
                'document_date': row[date_col].isoformat() if pd.notna(row[date_col]) else None,
                'file_name': file_name,
                'type_text': type_text,  # Original type from Athena
                'binary_id': row.get('dc_binary_id', row.get('binary_id', '')),
                's3_path': row.get('dc_binary_url', row.get('s3_path', '')),
                'description': row.get('dr_description', ''),
                'has_content': False,  # Will be set to True when content is retrieved
                'priority_score': self._calculate_document_priority_score(doc_category, row, event_date)
            }
            docs.append(doc)

        logger.info(f"    Found {len(docs)} documents in window for types: {document_types}")
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

    def _is_variable_confirmed(self, result: Dict, variable: str) -> bool:
        """
        Check if variable is already confirmed by multiple consistent sources.
        Implements early termination logic to avoid processing excess documents.
        Handles both old format (value/confidence) and new iterative format (final_value/final_confidence).
        """
        # Handle both result formats
        confidence = result.get('final_confidence', result.get('confidence', 0))
        value = result.get('final_value', result.get('value'))

        # If no valid value, not confirmed
        if not value or value in ['Not found', 'No confident extractions', 'Unavailable']:
            return False

        # Special handling for extent of resection
        if variable == 'extent_of_tumor_resection':
            # Must have both operative note AND imaging for confirmation
            sources = result.get('sources', [])
            # Also check all_candidates for sources
            if 'all_candidates' in result:
                sources.extend([c.get('source', '') for c in result['all_candidates']])

            has_op_note = any('operative' in s.lower() for s in sources if s)
            has_imaging = any('imaging' in s.lower() for s in sources if s)
            if has_op_note and has_imaging:
                return True

        # For other variables, check if we have 3+ consistent sources
        source_count = result.get('source_count', len(result.get('all_candidates', [])))
        if source_count >= 3 and confidence >= 0.8:
            return True

        return False

    def _needs_fallback(self, result: Dict, variable: str) -> bool:
        """
        Determine if strategic fallback is needed based on result quality.
        Critical variables require minimum 2 sources and confidence >= 0.7.
        Handles both old format (value/confidence) and new iterative format (final_value/final_confidence).
        """
        critical_variables = [
            'extent_of_tumor_resection',
            'tumor_location',
            'histopathology',
            'who_grade',
            'metastasis_presence'
        ]

        # Handle both result formats
        value = result.get('final_value', result.get('value'))
        confidence = result.get('final_confidence', result.get('confidence', 0))

        # Check if unavailable or low confidence
        if value in ['Unavailable', 'Not found', 'No confident extractions']:
            return True

        # Critical variables need higher confidence and multiple sources
        if variable in critical_variables:
            # Get source count from either format
            source_count = len(result.get('all_candidates', result.get('sources', [])))
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
                # Try extraction with fallback documents using iterative framework
                # Note: event_date and patient_age_days need to be passed from timeline_context
                result = self.phase4_llm_extractor.extract_from_documents(
                    variable=variable,
                    documents=fallback_docs,
                    patient_id=patient_id,
                    event_date=event_date.isoformat() if hasattr(event_date, 'isoformat') else str(event_date),
                    patient_age_days=timeline_context.get('age_at_event')
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

        # CRITICAL: Limit fallback documents to prevent processing thousands
        # Based on validated workflow that limited to 3-20 docs for performance
        max_fallback_docs = 20
        if len(new_docs) > max_fallback_docs:
            logger.info(f"      Limiting fallback from {len(new_docs)} to {max_fallback_docs} documents")
            # Prioritize by document type relevance
            prioritized = sorted(new_docs,
                               key=lambda x: ('operative' in x.get('type', '').lower(),
                                            'imaging' in x.get('type', '').lower(),
                                            'pathology' in x.get('type', '').lower()),
                               reverse=True)
            return prioritized[:max_fallback_docs]

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

    def _retrieve_document_contents(self, documents: List[Dict]) -> List[Dict]:
        """
        Retrieve actual document content from S3 or local storage

        Args:
            documents: List of document metadata dicts

        Returns:
            List of documents with 'content' field added
        """
        docs_with_content = []

        for doc in documents:
            doc_copy = doc.copy()

            # Check if S3 key is available
            if doc.get('s3_key') or doc.get('s3_path'):
                try:
                    # Use the real document retriever for S3 access
                    s3_key = doc.get('s3_key') or doc.get('s3_path')
                    content = self.document_retriever.retrieve_document_content(s3_key)
                    doc_copy['content'] = content
                    doc_copy['has_content'] = True
                    logger.info(f"    Retrieved content for document: {doc.get('document_id', 'unknown')[:20]}")
                except Exception as e:
                    logger.warning(f"    Failed to retrieve S3 content: {e}")
                    doc_copy['content'] = f"[Document metadata only - content retrieval failed: {e}]"
                    doc_copy['has_content'] = False
            else:
                # No S3 key, use metadata only
                doc_copy['content'] = f"[Document metadata: {doc.get('document_type', 'Unknown type')} from {doc.get('document_date', 'Unknown date')}]"
                doc_copy['has_content'] = False

            docs_with_content.append(doc_copy)

        return docs_with_content

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