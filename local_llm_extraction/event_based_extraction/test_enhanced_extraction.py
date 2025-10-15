#!/usr/bin/env python3
"""
Test version of enhanced extraction - processes just Event 2 which had missing variables
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from enhanced_extraction_with_fallback import *

def test_event_2_extraction():
    """
    Test extraction for Event 2 which had unavailable variables
    """
    staging_dir = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files')
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Initialize pipeline
    pipeline = EnhancedExtractionPipeline(staging_dir)

    # Load binary metadata
    binary_path = staging_dir / f'patient_{patient_id}' / 'binary_files.csv'
    binary_metadata = pd.read_csv(binary_path)
    print(f"Loaded {len(binary_metadata)} binary document references")

    # Define Event 2 (Progressive surgery)
    event_2 = {
        'date': '2021-03-10',
        'procedure': 'CRANIEC TREPHINE BONE FLP BRAIN TUMOR SUPRTENTOR',
        'type': 'Progressive'
    }

    print(f"\nProcessing Event 2: {event_2['date']} ({event_2['type']})")
    print("This event previously had unavailable extent_of_resection and tumor_location")
    print("-" * 80)

    # Extract with fallback strategies
    results = pipeline.extract_surgical_event(patient_id, event_2, binary_metadata)

    # Print detailed results
    print("\n" + "="*80)
    print("EXTRACTION RESULTS WITH MULTI-SOURCE EVIDENCE")
    print("="*80)

    print(f"\nMetadata:")
    print(f"  Primary documents: {results['extraction_metadata']['primary_documents_retrieved']}")
    print(f"  Fallback documents: {results['extraction_metadata'].get('fallback_documents_retrieved', 0)}")
    print(f"  Total LLM calls: {results['extraction_metadata']['total_llm_calls']}")

    print(f"\nExtracted Variables:")
    for var, extraction in results['extractions'].items():
        print(f"\n{var}:")
        print(f"  Value: {extraction['value']}")
        print(f"  Confidence: {extraction['confidence']}")
        print(f"  Evidence count: {extraction.get('evidence_count', 0)} documents")

        if 'sources' in extraction:
            print(f"  Sources: {', '.join(extraction['sources'][:3])}")

        if 'agreement_ratio' in extraction:
            print(f"  Agreement ratio: {extraction['agreement_ratio']}")

        if 'all_values' in extraction and len(extraction['all_values']) > 1:
            print(f"  All extracted values: {extraction['all_values'][:3]}")

    # Save test results
    output_path = Path('event_2_enhanced_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✓ Full results saved to: {output_path.absolute()}")

    # Show comparison with previous extraction
    print("\n" + "="*80)
    print("COMPARISON WITH PREVIOUS EXTRACTION")
    print("="*80)
    print("Previous extraction (single source):")
    print("  - extent_of_tumor_resection: Unavailable")
    print("  - tumor_location: Unavailable")
    print("\nNew extraction (multi-source with fallback):")
    print(f"  - extent_of_tumor_resection: {results['extractions'].get('extent_of_tumor_resection', {}).get('value', 'N/A')}")
    print(f"  - tumor_location: {results['extractions'].get('tumor_location', {}).get('value', 'N/A')}")

if __name__ == '__main__':
    test_event_2_extraction()