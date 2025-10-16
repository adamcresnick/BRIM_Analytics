"""
Phase 4: Iterative LLM Extraction with Multi-Pass Clinical Reasoning
===================================================================
4-Pass extraction framework:
  Pass 1: Document-based LLM extraction
  Pass 2: Structured data interrogation (when Pass 1 fails)
  Pass 3: Cross-source validation
  Pass 4: Temporal reasoning and clinical plausibility
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import sys
import pandas as pd

# Add parent directory to path for iterative_extraction imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from iterative_extraction.extraction_result import Candidate, PassResult, ExtractionResult
from iterative_extraction.pass2_structured_query import StructuredDataQuerier
from iterative_extraction.pass3_cross_validation import CrossSourceValidator
from iterative_extraction.pass4_temporal_reasoning import TemporalReasoner
from .phase4_enhanced_llm_extraction import EnhancedLLMExtractor

logger = logging.getLogger(__name__)

class IterativeLLMExtractor:
    """
    Iterative extraction with multi-pass clinical reasoning
    Combines document extraction with structured data interrogation and validation
    """

    def __init__(self, staging_path: Path, ollama_model: str = "gemma2:27b"):
        # Initialize the base enhanced LLM extractor (Pass 1)
        self.enhanced_extractor = EnhancedLLMExtractor(staging_path, ollama_model)

        # Initialize pass components
        self.structured_querier = None  # Will be initialized when phase data is set
        self.cross_validator = CrossSourceValidator()
        self.temporal_reasoner = None  # Will be initialized per event

        # Store phase data
        self.phase1_data = {}
        self.phase2_timeline = []
        self.data_sources = {}

    def set_phase_data(self, phase1_data: Dict, phase2_timeline: List, data_sources: Dict):
        """Set data from previous phases"""
        self.phase1_data = phase1_data or {}
        self.phase2_timeline = phase2_timeline or []
        self.data_sources = data_sources or {}

        # Initialize enhanced extractor with phase data
        self.enhanced_extractor.set_phase_data(phase1_data, phase2_timeline, [])

        # Initialize structured querier
        self.structured_querier = StructuredDataQuerier(
            phase1_data, phase2_timeline, data_sources
        )

        logger.info(f"Iterative extractor initialized - P1: {len(phase1_data)} items, P2: {len(phase2_timeline)} events")

    def extract_with_iteration(self, variable: str, documents: List[Dict],
                               patient_id: str, event_date: str,
                               patient_age_days: int) -> ExtractionResult:
        """
        Main extraction method with 4-pass iterative approach
        """
        result = ExtractionResult(
            variable=variable,
            patient_id=patient_id,
            event_date=event_date
        )

        logger.info(f"\n{'='*60}")
        logger.info(f"ITERATIVE EXTRACTION: {variable}")
        logger.info(f"Event: {event_date}, Patient: {patient_id}")
        logger.info(f"Documents available: {len(documents)}")
        logger.info(f"{'='*60}")

        # Initialize temporal reasoner for this event
        self.temporal_reasoner = TemporalReasoner(
            self.phase1_data,
            self.phase2_timeline,
            patient_age_days
        )

        # PASS 1: Document-based LLM extraction
        logger.info("\n--- PASS 1: DOCUMENT-BASED LLM EXTRACTION ---")
        pass1_result = self._pass1_document_extraction(variable, documents, patient_id)
        result.add_pass(1, pass1_result)

        # PASS 2: Structured data interrogation (if Pass 1 failed or low confidence)
        if pass1_result.confidence < 0.7 or not pass1_result.value or pass1_result.value == "Not found":
            logger.info("\n--- PASS 2: STRUCTURED DATA INTERROGATION ---")
            logger.info(f"Pass 1 confidence ({pass1_result.confidence:.2f}) < 0.7 or no value found")

            # Build surgical context for this event
            surgical_context = self._build_surgical_context(event_date)

            pass2_result = self.structured_querier.query_for_variable(
                variable, event_date, pass1_result, surgical_context=surgical_context
            )
            result.add_pass(2, pass2_result)

            # Merge candidates from both passes
            result.merge_passes([pass1_result, pass2_result])

            logger.info(f"Pass 2 found {len(pass2_result.candidates)} candidates from structured data")
        else:
            logger.info(f"\n--- PASS 2: SKIPPED (Pass 1 confidence {pass1_result.confidence:.2f} >= 0.7) ---")

        # PASS 3: Cross-source validation
        logger.info("\n--- PASS 3: CROSS-SOURCE VALIDATION ---")
        pass3_result = self.cross_validator.validate(variable, result)
        result.add_pass(3, pass3_result)

        # Update result value from cross-validation if better
        if pass3_result.value and pass3_result.confidence > result.final_confidence:
            result.final_value = pass3_result.value
            result.final_confidence = pass3_result.confidence

        logger.info(f"Cross-validation result: {pass3_result.value} (confidence: {pass3_result.confidence:.2f})")

        # PASS 4: Temporal reasoning and clinical plausibility
        logger.info("\n--- PASS 4: TEMPORAL REASONING ---")
        pass4_result = self.temporal_reasoner.validate(variable, event_date, result)
        result.add_pass(4, pass4_result)

        # Apply confidence adjustment from temporal reasoning
        if result.final_confidence > 0:
            original_conf = result.final_confidence
            result.final_confidence *= pass4_result.confidence_adjustment
            logger.info(f"Temporal adjustment: {original_conf:.2f} × {pass4_result.confidence_adjustment:.2f} = {result.final_confidence:.2f}")

        # Finalize the result
        result.finalize()

        logger.info(f"\n{'='*60}")
        logger.info(f"FINAL RESULT: {result.final_value}")
        logger.info(f"Confidence: {result.final_confidence:.2f}")
        logger.info(f"Manual review needed: {result.needs_manual_review}")
        logger.info(f"Reasoning chain: {len(result.reasoning_chain)} steps")
        logger.info(f"{'='*60}\n")

        return result

    def _pass1_document_extraction(self, variable: str, documents: List[Dict],
                                   patient_id: str) -> PassResult:
        """
        Pass 1: Extract from documents using LLM
        """
        pass1_result = PassResult(pass_number=1, method='document_llm')

        if not documents:
            pass1_result.add_note("No documents provided for extraction")
            return pass1_result

        # Build structured context from Phase 1 & 2 data
        structured_context = self._build_structured_context_for_llm(variable)

        # Use the enhanced extractor for document-based extraction
        # This calls the existing extract_with_structured_context method
        extraction_results = self.enhanced_extractor.extract_with_structured_context(
            patient_id=patient_id,
            variable=variable,
            documents=documents,
            structured_context=structured_context
        )

        # Convert to Pass 1 result format
        if extraction_results and 'extractions' in extraction_results:
            for ext in extraction_results['extractions']:
                if ext.get('extraction'):
                    value = ext['extraction'].get('value')
                    conf = ext['extraction'].get('confidence', 0.0)
                    supporting = ext['extraction'].get('supporting_text', '')

                    if value and value != "Not found" and conf > 0:
                        pass1_result.add_candidate(
                            value=value,
                            confidence=conf,
                            source=f"Document {ext.get('document_id', 'unknown')}",
                            source_type='document',
                            supporting_text=supporting
                        )

        # Set result value from best candidate
        if pass1_result.candidates:
            best = max(pass1_result.candidates, key=lambda c: c.confidence)
            pass1_result.value = best.value
            pass1_result.confidence = best.confidence
            pass1_result.sources = [c.source for c in pass1_result.candidates]
            logger.info(f"Pass 1: Extracted {pass1_result.value} from {len(pass1_result.candidates)} documents (confidence: {pass1_result.confidence:.2f})")
        else:
            pass1_result.value = "Not found"
            pass1_result.confidence = 0.0
            logger.info("Pass 1: No extractions from documents")

        return pass1_result

    def _build_surgical_context(self, event_date: str) -> Dict:
        """
        Build surgical context for Pass 2 queries.
        Includes prior surgeries, treatments, and disease trajectory.
        """
        try:
            event_dt = pd.to_datetime(event_date)
        except:
            return {}

        context = {
            'surgery_number': 1,
            'prior_surgeries': [],
            'prior_treatments': []
        }

        # Find prior surgical events
        prior_surgeries = [e for e in self.phase2_timeline
                          if e.event_type == 'surgical'
                          and e.event_date < event_dt]

        if prior_surgeries:
            context['surgery_number'] = len(prior_surgeries) + 1
            context['prior_surgeries'] = [
                {
                    'date': str(s.event_date.date()),
                    'description': getattr(s, 'description', ''),
                    'extent': None  # Would need to be extracted
                }
                for s in prior_surgeries
            ]

        # Find prior treatments (radiation, chemo)
        prior_treatments = []

        # Check for radiation events
        radiation_events = [e for e in self.phase2_timeline
                          if 'radiation' in str(e.event_type).lower()
                          and e.event_date < event_dt]

        for rad in radiation_events:
            prior_treatments.append({
                'type': 'radiation',
                'date': str(rad.event_date.date()),
                'description': getattr(rad, 'description', '')
            })

        # Check for chemotherapy (from medications data)
        if 'medications' in self.data_sources:
            meds = self.data_sources['medications']
            chemo_keywords = ['chemotherapy', 'vincristine', 'carboplatin', 'temozolomide', 'cyclophosphamide']

            for _, med in meds.iterrows():
                med_date = pd.to_datetime(med.get('medication_start_date', med.get('med_date_given_start')))
                if med_date and med_date < event_dt:
                    med_name = str(med.get('medication_name', med.get('med_name', ''))).lower()
                    if any(kw in med_name for kw in chemo_keywords):
                        prior_treatments.append({
                            'type': 'chemotherapy',
                            'date': str(med_date.date()),
                            'medication': med_name
                        })

        context['prior_treatments'] = prior_treatments

        logger.info(f"Built surgical context: Surgery #{context['surgery_number']}, "
                   f"{len(context['prior_surgeries'])} prior surgeries, "
                   f"{len(context['prior_treatments'])} prior treatments")

        return context

    def _build_structured_context_for_llm(self, variable: str) -> Dict:
        """
        Build comprehensive structured context from Phase 1 & 2 data for LLM prompts.
        This includes:
        1. Phase 1 structured data (diagnoses, procedures, medications, imaging, molecular tests)
        2. Phase 2 timeline data (events, dates, sequences)
        3. Schema information about available structured data sources
        """
        context = {}

        # ==================================================================
        # PHASE 1: STRUCTURED DATA FROM MATERIALIZED VIEWS
        # ==================================================================

        # Core patient demographics
        if 'patient_birth_date' in self.phase1_data:
            context['birth_date'] = str(self.phase1_data['patient_birth_date'])
        if 'patient_gender' in self.phase1_data:
            context['gender'] = self.phase1_data['patient_gender']
        if 'patient_race' in self.phase1_data:
            context['race'] = self.phase1_data['patient_race']

        # Diagnosis information
        if 'diagnosis_date' in self.phase1_data:
            context['diagnosis_date'] = str(self.phase1_data['diagnosis_date'])
        if 'diagnosis_histology' in self.phase1_data:
            context['diagnosis_histology'] = self.phase1_data['diagnosis_histology']
        if 'brain_tumor_diagnosis' in self.phase1_data:
            context['brain_tumor_diagnosis'] = self.phase1_data['brain_tumor_diagnosis']

        # Surgery information
        surgical_events = [e for e in self.phase2_timeline
                          if e.event_type in ['surgery', 'surgical']]
        if surgical_events:
            context['surgery_dates'] = [str(s.event_date.date()) for s in surgical_events]
            context['surgery_count'] = len(surgical_events)
            context['initial_surgery'] = str(surgical_events[0].event_date.date())

            # Surgery types if available
            surgery_types = [getattr(s, 'surgery_type', 'Unknown') for s in surgical_events]
            context['surgery_types'] = surgery_types

        # Treatment information
        if 'has_chemotherapy' in self.phase1_data:
            context['has_chemotherapy'] = self.phase1_data['has_chemotherapy']
        if 'has_radiation_therapy' in self.phase1_data:
            context['has_radiation'] = self.phase1_data['has_radiation_therapy']
        if 'chemotherapy_drugs' in self.phase1_data:
            context['chemotherapy_drugs'] = self.phase1_data['chemotherapy_drugs']

        # Molecular testing information
        if 'molecular_tests' in self.phase1_data:
            mol_tests = self.phase1_data['molecular_tests']
            context['has_molecular_testing'] = True
            context['molecular_markers'] = mol_tests if isinstance(mol_tests, list) else [mol_tests]

        # ==================================================================
        # PHASE 2: TIMELINE CONTEXT
        # ==================================================================

        # Event counts by type
        event_types = {}
        for event in self.phase2_timeline:
            event_type = event.event_type
            event_types[event_type] = event_types.get(event_type, 0) + 1
        context['event_counts'] = event_types

        # Key event dates
        context['timeline_span_days'] = None
        if len(self.phase2_timeline) >= 2:
            dates = [e.event_date for e in self.phase2_timeline if hasattr(e, 'event_date')]
            if dates:
                context['timeline_span_days'] = (max(dates) - min(dates)).days

        # ==================================================================
        # STRUCTURED DATA SCHEMA INFORMATION
        # ==================================================================

        context['available_structured_sources'] = {
            'description': 'The following structured data sources (materialized views) are available for validation and adjudication',
            'sources': [
                {
                    'name': 'imaging',
                    'description': 'Imaging studies with findings in result_information field',
                    'key_fields': ['imaging_date', 'modality', 'result_information', 'result_display'],
                    'use_for': 'Tumor location, extent of resection validation via post-op imaging'
                },
                {
                    'name': 'procedures',
                    'description': 'Surgical and diagnostic procedures',
                    'key_fields': ['proc_performed_date_time', 'proc_code_text', 'pcc_code_coding_code'],
                    'use_for': 'Surgery dates, procedure types, surgical approach'
                },
                {
                    'name': 'diagnoses',
                    'description': 'ICD-10 coded diagnoses with hierarchy',
                    'key_fields': ['diagnosis_name', 'icd10_code', 'icd10_display', 'onset_date_time'],
                    'source_hierarchy': 'Pathology (0.90) > ICD-10 (0.70) > Problem list (0.50)',
                    'use_for': 'Histopathology, WHO grade, tumor type validation'
                },
                {
                    'name': 'molecular_tests_metadata',
                    'description': 'Molecular test results (NOT binary files - structured text fields)',
                    'key_fields': ['lab_test_name', 'result_datetime', 'result_value', 'interpretation'],
                    'use_for': 'BRAF status, IDH mutations, H3K27M, methylation status',
                    'note': 'Results are in structured fields, not separate PDF reports'
                },
                {
                    'name': 'medications',
                    'description': 'Medication administrations and prescriptions',
                    'key_fields': ['medication_name', 'medication_start_date', 'med_route'],
                    'use_for': 'Chemotherapy regimens, supportive medications'
                },
                {
                    'name': 'problem_list_diagnoses',
                    'description': 'Active problem list (lower confidence than coded diagnoses)',
                    'key_fields': ['diagnosis_name', 'problem_text', 'recorded_date'],
                    'confidence': 0.50,
                    'use_for': 'Diagnosis validation (lowest tier)'
                }
            ],
            'validation_instructions': 'When you extract data from binary documents, you can request validation against these structured sources. For example, if you extract "glioblastoma" from a pathology report, note that this can be validated against the diagnoses materialized view with ICD-10 codes.'
        }

        # ==================================================================
        # VARIABLE-SPECIFIC CONTEXT ENRICHMENT
        # ==================================================================

        # Add variable-specific hints about which structured sources to reference
        if variable in ['extent_of_tumor_resection', 'extent_of_resection']:
            context['validation_hint'] = 'CRITICAL: Post-op imaging (24-72h) in imaging.result_information field is GOLD STANDARD (0.95 confidence) and should override operative note findings (0.75 confidence)'

        elif variable == 'tumor_location':
            context['validation_hint'] = 'Imaging findings in imaging.result_information field contain anatomical descriptions. Cross-reference with procedure location from procedures.proc_code_text'

        elif variable in ['histopathology', 'tumor_histology']:
            context['validation_hint'] = 'Validate against diagnoses.diagnosis_name with ICD-10 codes. Pathology-sourced diagnoses have 0.90 confidence.'

        elif variable == 'molecular_testing':
            context['validation_hint'] = 'Molecular test results are in molecular_tests_metadata.result_value field (structured text), NOT separate binary reports'

        elif variable == 'who_grade':
            context['validation_hint'] = 'WHO grade often encoded in diagnoses.diagnosis_name. Look for "Grade I/II/III/IV" or tumor-type indicators (glioblastoma=IV, pilocytic=I)'

        logger.info(f"Built structured context for LLM: {len(context)} top-level keys")
        logger.info(f"  - Surgery dates: {context.get('surgery_count', 0)} surgeries")
        logger.info(f"  - Molecular tests: {context.get('has_molecular_testing', False)}")
        logger.info(f"  - Available structured sources: {len(context.get('available_structured_sources', {}).get('sources', []))}")

        return context

    def extract_from_documents(self, variable: str, documents: List[Dict],
                              patient_id: str, event_date: str = None,
                              patient_age_days: int = None) -> Dict:
        """
        Public interface - extract with full iterative logic
        """
        if event_date and patient_age_days is not None:
            # Full iterative extraction
            result = self.extract_with_iteration(
                variable, documents, patient_id, event_date, patient_age_days
            )
            return result.to_dict()
        else:
            # Fallback to simple extraction
            logger.warning("event_date or patient_age_days not provided - using simple extraction")
            return self.enhanced_extractor.extract_from_documents(variable, documents, patient_id)
