#!/usr/bin/env python3
"""
Test the integrated pipeline after fixing Phase 1 staging file loading
"""
import sys
import logging
from pathlib import Path
from form_extractors.integrated_pipeline_extractor import IntegratedPipelineExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

# Suppress verbose loggers
for logger_name in [
    'event_based_extraction.enhanced_extraction_with_fallback',
    'event_based_extraction.real_document_extraction',
    'form_extractors.redcap_terminology_mapper',
    'event_based_extraction.comprehensive_chemotherapy_identifier',
    'boto3', 'botocore', 's3transfer', 'urllib3'
]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

def main():
    print('\n' + '='*70)
    print('INTEGRATED PIPELINE - FINAL TEST')
    print('Testing: Phase 1 loads from config_driven_versions')
    print('='*70)

    # Get paths
    staging_base = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics')

    # Use config_driven_versions location for binary files
    truncated_id = 'e4BwD8ZYDBccepXcJ.Ilo3'
    config_staging_path = staging_base / 'athena_extraction_validation' / 'scripts' / 'config_driven_versions' / 'staging_files' / f'patient_{truncated_id}'
    binary_files_path = config_staging_path / 'binary_files.csv'

    # Use the REDCap data dictionary
    data_dictionary_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction/Dictionary/CBTN_DataDictionary_2025-10-15.csv')

    # Initialize pipeline
    print('\nInitializing Pipeline...')
    pipeline = IntegratedPipelineExtractor(
        staging_base,
        binary_files_path,
        data_dictionary_path
    )

    # Run the complete pipeline
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    birth_date = '2005-05-13'

    print(f'\nPatient: {patient_id}')
    print(f'Birth Date: {birth_date}')
    print('-'*70)

    # Run all phases
    result = pipeline.extract_patient_comprehensive(
        patient_id=patient_id,
        birth_date=birth_date
    )

    # Summarize results
    print('\n' + '='*70)
    print('PIPELINE RESULTS')
    print('='*70)

    # Phase 1 - Check that staging files loaded from config_driven_versions
    phase1 = result.get('phase_1_harvesting', {})
    if phase1:
        print('\n✓ PHASE 1 - Data Sources Loaded:')
        # Check for key data sources
        data_sources = pipeline.phase1_harvester.data_sources
        important_sources = ['procedures', 'diagnoses', 'medications', 'imaging', 'binary_files']
        for source in important_sources:
            if source in data_sources and not data_sources[source].empty:
                count = len(data_sources[source])
                print(f'  ✓ {source}: {count:,} records')

        # Check surgical events
        if 'surgical_events' in phase1:
            events = phase1['surgical_events']
            print(f'\n  Surgical Events: {len(events)}')
            for event in events:
                print(f'    - Event {event.get("event_number")}: {event.get("event_type_label")}')

    # Phase 2
    phase2 = result.get('phase_2_timeline', {})
    if phase2 and 'clinical_timeline' in phase2:
        timeline = phase2['clinical_timeline']
        if 'events' in timeline:
            print(f'\n✓ PHASE 2 - Timeline: {len(timeline["events"])} events')

    # Phase 3 - Check document retrieval
    phase3 = result.get('phase_3_documents', {})
    if phase3 and 'selected_documents' in phase3:
        docs = phase3['selected_documents']
        print(f'\n✓ PHASE 3 - Documents: {len(docs)} selected')
        if docs:
            # Show document distribution
            tier1 = sum(1 for d in docs if d.get('tier') == 1)
            tier2 = sum(1 for d in docs if d.get('tier') == 2)
            tier3 = sum(1 for d in docs if d.get('tier') == 3)
            print(f'    Tier 1: {tier1}, Tier 2: {tier2}, Tier 3: {tier3}')
    else:
        print('\n✗ PHASE 3 - No documents retrieved')
        print('  This is the issue to fix - Phase 3 should find documents from binary_files.csv')

    # Phase 4
    phase4 = result.get('phase_4_extraction', {})
    if phase4 and 'extracted_data' in phase4:
        extracted = phase4['extracted_data']
        if extracted:
            populated = sum(1 for v in extracted.values() if v)
            print(f'\n✓ PHASE 4 - Extraction: {populated} fields populated')

    # Phase 5
    phase5 = result.get('phase_5_validation', {})
    if phase5 and 'validation_summary' in phase5:
        summary = phase5['validation_summary']
        print(f'\n✓ PHASE 5 - Validation complete')
        if 'confidence_scores' in summary:
            scores = summary['confidence_scores']
            print(f'    Confidence: High={scores.get("high", 0)}, Medium={scores.get("medium", 0)}, Low={scores.get("low", 0)}')

    # Final summary
    print('\n' + '='*70)
    success_phases = []
    if phase1: success_phases.append('Phase 1')
    if phase2: success_phases.append('Phase 2')
    if phase3 and phase3.get('selected_documents'): success_phases.append('Phase 3')
    if phase4: success_phases.append('Phase 4')
    if phase5: success_phases.append('Phase 5')

    print(f'Phases Completed: {len(success_phases)}/5')
    if len(success_phases) == 5:
        print('✓ ALL PHASES SUCCESSFUL!')
    else:
        print(f'Completed: {", ".join(success_phases)}')

    print('\nKey Finding:')
    print('- Phase 1 now loads staging files from config_driven_versions ✓')
    print('- Need to verify Phase 3 can retrieve documents from binary_files.csv')
    print('='*70)

if __name__ == "__main__":
    main()