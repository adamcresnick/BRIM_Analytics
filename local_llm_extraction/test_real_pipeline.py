#!/usr/bin/env python3
"""Test the full pipeline with real LLM extraction"""

import logging
from pathlib import Path
from form_extractors.integrated_pipeline_extractor import IntegratedPipelineExtractor
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Suppress verbose loggers
for logger_name in ['boto3', 'botocore', 's3transfer', 'urllib3']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

print('\n' + '='*70)
print('TESTING FULL PIPELINE WITH REAL LLM EXTRACTION')
print('='*70)

# Initialize pipeline with correct paths from validated configuration
staging_base = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/scripts/config_driven_versions/staging_files')
patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

# Use the binary files metadata from athena_extraction_validation
binary_files_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files/ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv')

# Use the CBTN REDCap data dictionary
data_dictionary_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction/Dictionary/CBTN_DataDictionary_2025-10-15.csv')

# Check if paths exist
if not staging_base.exists():
    print(f"ERROR: Staging base not found: {staging_base}")
if not binary_files_path.exists():
    print(f"ERROR: Binary files not found: {binary_files_path}")

pipeline = IntegratedPipelineExtractor(staging_base, binary_files_path, data_dictionary_path)

# Run pipeline for one event to test
result = pipeline.extract_patient_comprehensive(
    patient_id='e4BwD8ZYDBccepXcJ.Ilo3w3',
    birth_date='2005-05-13'
)

print('\n' + '='*70)
print('PIPELINE RESULTS SUMMARY')
print('='*70)

# Check events for Phase 4 results
if 'events' in result and result['events']:
    event = result['events'][0]
    print(f'\nEvent: {event.get("event_type")} on {event.get("event_date")}')

    # Document selection efficiency
    if 'document_stats' in event:
        stats = event['document_stats']
        print(f'\nPhase 3 - Document Selection:')
        print(f'  Total documents selected: {stats.get("total_documents")}')
        print(f'  (Out of 22,127 available documents)')
        print(f'  Efficiency: {stats.get("total_documents") / 22127 * 100:.1f}% of documents used')

        print(f'\n  Documents by type:')
        for doc_type, count in stats.get('documents_by_type', {}).items():
            if count > 0:
                print(f'    - {doc_type}: {count}')

    # LLM extraction results
    if 'extracted_variables' in event:
        extracted = event['extracted_variables']
        print(f'\nPhase 4 - LLM Extraction:')
        print(f'  Variables attempted: {len(extracted)}')

        # Count successful extractions
        populated = []
        for var, res in extracted.items():
            if isinstance(res, dict):
                val = res.get('value')
                if val and val not in ['Unable to extract', 'Not found', 'Unavailable', None]:
                    populated.append((var, res))

        if populated:
            print(f'  ✓ Successfully extracted: {len(populated)}/{len(extracted)} variables')

            print(f'\n  Extracted values:')
            for var, res in populated:
                print(f'\n    {var}:')
                print(f'      Value: {res.get("value")}')
                print(f'      Confidence: {res.get("confidence", 0):.2f}')
                if res.get('fallback_used'):
                    print(f'      Source: Fallback extraction')
                if res.get('source'):
                    print(f'      Source: {res.get("source")}')
        else:
            print(f'  ✗ No variables successfully extracted')
            print('\n  Extraction attempts:')
            for var in list(extracted.keys())[:5]:
                val = extracted[var]
                if isinstance(val, dict):
                    print(f'    - {var}: {val.get("value", "No value")} (confidence: {val.get("confidence", 0)})')
                else:
                    print(f'    - {var}: {val}')

    # Check extraction metadata
    if 'extraction_metadata' in event:
        meta = event['extraction_metadata']
        print(f'\n  Extraction Metadata:')
        print(f'    Fallback triggered: {meta.get("fallback_triggered", False)}')
        avg_conf = meta.get("average_confidence")
        if avg_conf:
            print(f'    Average confidence: {avg_conf:.2f}')
else:
    print('No events found in output')

# Check for Phase 5 validation
if 'events' in result and result['events']:
    event = result['events'][0]
    if 'validation_report' in event:
        print('\nPhase 5 - Validation: Present')
    else:
        print('\nPhase 5 - Validation: Not found in output')

# Save for inspection
with open('pipeline_test_real_llm.json', 'w') as f:
    json.dump(result, f, indent=2, default=str)
print(f'\nFull results saved to pipeline_test_real_llm.json')

print('\n' + '='*70)
print('TEST COMPLETE')
print('='*70)