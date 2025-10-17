"""
Test script to demonstrate 4-pass iterative extraction with clinical reasoning
Bypasses S3 document retrieval to focus on extraction logic validation
"""
import sys
from pathlib import Path
import logging
import pandas as pd
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Paths
staging_base = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/scripts/config_driven_versions/staging_files')

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from iterative_extraction.extraction_result import ExtractionResult, PassResult, Candidate
from iterative_extraction.pass2_structured_query import StructuredDataQuerier
from iterative_extraction.pass3_cross_validation import CrossSourceValidator
from iterative_extraction.pass4_temporal_reasoning import TemporalReasoner

def create_sample_phase1_data():
    """Create sample Phase 1 structured data"""
    return {
        'surgical_events': [
            {'date': '2018-05-28', 'type': 'craniotomy'},
            {'date': '2018-06-04', 'type': 'shunt'},
            {'date': '2021-03-10', 'type': 'craniotomy'},
            {'date': '2021-03-15', 'type': 'craniotomy'},
        ],
        'has_chemotherapy': True,
        'has_radiation_therapy': True,
        'diagnosis_date': '2018-05-28',
        'molecular_tests': []
    }

def create_sample_phase2_timeline():
    """Create sample Phase 2 timeline"""
    return [
        {'date': pd.to_datetime('2018-05-28'), 'event_type': 'surgical', 'description': 'Craniotomy posterior fossa'},
        {'date': pd.to_datetime('2018-06-04'), 'event_type': 'surgical', 'description': 'VP shunt placement'},
        {'date': pd.to_datetime('2021-03-10'), 'event_type': 'surgical', 'description': 'Repeat resection'},
        {'date': pd.to_datetime('2021-03-15'), 'event_type': 'surgical', 'description': 'Debulking'},
        {'date': pd.to_datetime('2021-03-16'), 'event_type': 'surgical', 'description': 'Second look'},
        {'date': pd.to_datetime('2021-05-15'), 'event_type': 'chemotherapy', 'description': 'Started TMZ'},
        {'date': pd.to_datetime('2021-07-10'), 'event_type': 'radiation', 'description': 'Started focal radiation'},
    ]

def create_sample_data_sources():
    """Create sample data sources for structured interrogation"""
    # Sample procedures
    procedures = pd.DataFrame([
        {'proc_performed_date_time': pd.to_datetime('2018-05-28 10:00'),
         'proc_text': 'Suboccipital craniotomy for posterior fossa tumor resection. Subtotal resection achieved due to tumor adherence to brainstem.'},
        {'proc_performed_date_time': pd.to_datetime('2018-06-04 14:00'),
         'proc_text': 'VP shunt placement for post-operative hydrocephalus'},
        {'proc_performed_date_time': pd.to_datetime('2021-03-10 09:00'),
         'proc_text': 'Repeat craniotomy. Tumor recurrence. Partial resection.'},
    ])

    # Sample diagnoses
    diagnoses = pd.DataFrame([
        {'dx_date': pd.to_datetime('2018-05-28'), 'dx_text': 'Cerebellar tumor, posterior fossa mass', 'dx_code': 'C71.6'},
        {'dx_date': pd.to_datetime('2021-03-10'), 'dx_text': 'Recurrent glioblastoma, grade IV', 'dx_code': 'C71.6'},
    ])

    # Sample imaging
    imaging = pd.DataFrame([
        {'img_date': pd.to_datetime('2018-05-26'), 'img_modality': 'MRI',
         'img_findings': 'Large cerebellar mass in posterior fossa, enhancing lesion, approximately 4cm'},
        {'img_date': pd.to_datetime('2018-05-30'), 'img_modality': 'MRI',
         'img_findings': 'Post-operative imaging shows residual tumor in cerebellar vermis'},
        {'img_date': pd.to_datetime('2021-03-08'), 'img_modality': 'MRI',
         'img_findings': 'Tumor progression, new enhancement in cerebellum'},
    ])

    return {
        'procedures': procedures,
        'diagnoses': diagnoses,
        'imaging': imaging,
        'medications': pd.DataFrame(),
        'encounters': pd.DataFrame()
    }

def simulate_pass1_document_extraction():
    """
    Simulate Pass 1 - Document extraction that partially fails
    (mimics real scenario where documents exist but LLM struggles)
    """
    pass1 = PassResult(pass_number=1, method='document_llm')

    # Simulate that tumor_location was found but with low confidence
    pass1.add_candidate(
        value='Cerebellum',
        confidence=0.55,
        source='Clinical Note 2018-05-29',
        source_type='document',
        supporting_text='Patient with posterior fossa lesion...'
    )

    # extent_of_resection not found in Pass 1
    # (simulating the real issue where documents return "Not found")

    pass1.value = 'Cerebellum'  # Best candidate
    pass1.confidence = 0.55

    return pass1

def test_iterative_extraction():
    """
    Demonstrate 4-pass iterative extraction
    """
    logger.info("\n" + "="*80)
    logger.info("ITERATIVE EXTRACTION DEMONSTRATION")
    logger.info("="*80)

    # Setup
    phase1_data = create_sample_phase1_data()
    phase2_timeline = create_sample_phase2_timeline()
    data_sources = create_sample_data_sources()

    # Initialize components
    structured_querier = StructuredDataQuerier(phase1_data, phase2_timeline, data_sources)
    cross_validator = CrossSourceValidator()
    temporal_reasoner = TemporalReasoner(phase1_data, phase2_timeline, 4764)  # 13 years old = 4764 days

    # === TEST 1: Extent of Resection (document extraction fails, structured data succeeds) ===
    logger.info("\n" + "-"*80)
    logger.info("TEST 1: EXTENT OF RESECTION")
    logger.info("-"*80)

    result_extent = ExtractionResult(
        variable='extent_of_tumor_resection',
        patient_id='test_patient',
        event_date='2018-05-28'
    )

    # Pass 1: Failed (simulate)
    pass1_extent = PassResult(pass_number=1, method='document_llm')
    pass1_extent.value = "Not found"
    pass1_extent.confidence = 0.0
    result_extent.add_pass(1, pass1_extent)
    logger.info("Pass 1 (Document LLM): Not found")

    # Pass 2: Structured data interrogation
    pass2_extent = structured_querier.query_for_variable(
        'extent_of_tumor_resection',
        '2018-05-28',
        pass1_extent
    )
    result_extent.add_pass(2, pass2_extent)
    logger.info(f"Pass 2 (Structured Query): Found {len(pass2_extent.candidates)} candidates")
    for c in pass2_extent.candidates:
        logger.info(f"  - {c.value} (confidence: {c.confidence:.2f}, source: {c.source})")

    # Merge passes
    result_extent.merge_passes([pass1_extent, pass2_extent])

    # Pass 3: Cross-validation
    pass3_extent = cross_validator.validate('extent_of_tumor_resection', result_extent)
    result_extent.add_pass(3, pass3_extent)
    logger.info(f"Pass 3 (Cross-validation): {pass3_extent.value} (confidence: {pass3_extent.confidence:.2f})")

    # Pass 4: Temporal reasoning
    pass4_extent = temporal_reasoner.validate('extent_of_tumor_resection', '2018-05-28', result_extent)
    result_extent.add_pass(4, pass4_extent)
    logger.info(f"Pass 4 (Temporal): Adjustment factor = {pass4_extent.confidence_adjustment:.2f}")
    for flag_name, flag_value in pass4_extent.flags.items():
        logger.info(f"  Flag: {flag_name} = {flag_value}")

    # Finalize
    result_extent.finalize()
    logger.info(f"\nFINAL: {result_extent.final_value} (confidence: {result_extent.final_confidence:.2f})")
    logger.info(f"Manual review needed: {result_extent.needs_manual_review}")
    logger.info("\nReasoning Chain:")
    for step in result_extent.reasoning_chain:
        logger.info(f"  {step}")

    # === TEST 2: Tumor Location (document and structured data agree) ===
    logger.info("\n" + "-"*80)
    logger.info("TEST 2: TUMOR LOCATION")
    logger.info("-"*80)

    result_location = ExtractionResult(
        variable='tumor_location',
        patient_id='test_patient',
        event_date='2018-05-28'
    )

    # Pass 1: Found with medium confidence
    pass1_location = simulate_pass1_document_extraction()
    result_location.add_pass(1, pass1_location)
    logger.info(f"Pass 1 (Document LLM): {pass1_location.value} (confidence: {pass1_location.confidence:.2f})")

    # Pass 2: Structured data (confirms)
    pass2_location = structured_querier.query_for_variable(
        'tumor_location',
        '2018-05-28',
        pass1_location
    )
    result_location.add_pass(2, pass2_location)
    logger.info(f"Pass 2 (Structured Query): Found {len(pass2_location.candidates)} candidates")
    for c in pass2_location.candidates:
        logger.info(f"  - {c.value} (confidence: {c.confidence:.2f})")

    # Merge
    result_location.merge_passes([pass1_location, pass2_location])

    # Pass 3: Cross-validation (should boost confidence due to agreement)
    pass3_location = cross_validator.validate('tumor_location', result_location)
    result_location.add_pass(3, pass3_location)
    logger.info(f"Pass 3 (Cross-validation): {pass3_location.value} (confidence: {pass3_location.confidence:.2f})")

    # Pass 4: Temporal
    pass4_location = temporal_reasoner.validate('tumor_location', '2018-05-28', result_location)
    result_location.add_pass(4, pass4_location)
    logger.info(f"Pass 4 (Temporal): Adjustment = {pass4_location.confidence_adjustment:.2f}")

    # Finalize
    result_location.finalize()
    logger.info(f"\nFINAL: {result_location.final_value} (confidence: {result_location.final_confidence:.2f})")
    logger.info(f"Manual review needed: {result_location.needs_manual_review}")

    # === TEST 3: Histopathology (structured data finds transformation) ===
    logger.info("\n" + "-"*80)
    logger.info("TEST 3: HISTOPATHOLOGY (with transformation detection)")
    logger.info("-"*80)

    result_histo = ExtractionResult(
        variable='histopathology',
        patient_id='test_patient',
        event_date='2021-03-10'  # Recurrence event
    )

    # Pass 1: Not found
    pass1_histo = PassResult(pass_number=1, method='document_llm')
    pass1_histo.value = "Not found"
    pass1_histo.confidence = 0.0
    result_histo.add_pass(1, pass1_histo)

    # Pass 2: Structured data finds diagnosis
    pass2_histo = structured_querier.query_for_variable(
        'histopathology',
        '2021-03-10',
        pass1_histo
    )
    result_histo.add_pass(2, pass2_histo)
    logger.info(f"Pass 2: Found {len(pass2_histo.candidates)} candidates from diagnoses")
    for c in pass2_histo.candidates:
        logger.info(f"  - {c.value} (from {c.source})")

    result_histo.merge_passes([pass1_histo, pass2_histo])

    # Pass 3: Cross-validation
    pass3_histo = cross_validator.validate('histopathology', result_histo)
    result_histo.add_pass(3, pass3_histo)

    # Pass 4: Temporal reasoning (detects transformation)
    pass4_histo = temporal_reasoner.validate('histopathology', '2021-03-10', result_histo)
    result_histo.add_pass(4, pass4_histo)
    logger.info(f"Pass 4 Temporal Flags:")
    for flag_name, flag_value in pass4_histo.flags.items():
        logger.info(f"  {flag_name}: {flag_value}")

    result_histo.finalize()
    logger.info(f"\nFINAL: {result_histo.final_value} (confidence: {result_histo.final_confidence:.2f})")
    logger.info("\nReasoning Chain:")
    for step in result_histo.reasoning_chain:
        logger.info(f"  {step}")

    logger.info("\n" + "="*80)
    logger.info("DEMONSTRATION COMPLETE")
    logger.info("="*80)

    return result_extent, result_location, result_histo

if __name__ == "__main__":
    test_iterative_extraction()
