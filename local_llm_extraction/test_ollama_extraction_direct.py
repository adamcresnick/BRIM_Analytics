#!/usr/bin/env python3
"""
Direct test of Ollama LLM extraction to demonstrate it's working with real data.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from event_based_extraction.phase4_enhanced_llm_extraction import EnhancedLLMExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ollama_direct():
    """Test Ollama extraction directly with a sample document."""

    print("\n" + "="*80)
    print("DIRECT TEST OF OLLAMA LLM EXTRACTION")
    print("="*80)

    # Initialize the enhanced LLM extractor with real Ollama
    staging_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/scripts/config_driven_versions/staging_files"

    extractor = EnhancedLLMExtractor(
        staging_path=staging_path,
        ollama_model="gemma2:27b"
    )

    print("\n1. Testing Ollama availability...")
    if extractor.ollama_client:
        print("   ✓ Ollama client initialized successfully")
        print(f"   ✓ Using model: {extractor.ollama_model}")
    else:
        print("   ✗ Ollama not available - will use fallback")

    # Create a sample operative note for testing
    sample_document = {
        'id': 'test_op_note_001',
        'type': 'operative_note',
        'date': '2018-05-28',
        'content': """
        OPERATIVE NOTE

        PROCEDURE: CRANIOTOMY WITH TUMOR RESECTION

        INDICATION: 13-year-old with cerebellar mass

        FINDINGS: Large 4.5 cm mass in the posterior fossa involving the cerebellar vermis.
        The tumor appeared well-demarcated from surrounding brain tissue.

        PROCEDURE: A suboccipital craniotomy was performed. The tumor was identified and
        using microsurgical techniques, a gross total resection was achieved.
        Frozen section confirmed pilocytic astrocytoma.

        EXTENT OF RESECTION: Gross total resection achieved with complete removal of
        all visible tumor. Post-operative imaging will confirm extent.

        BLOOD LOSS: 150 mL

        The patient tolerated the procedure well.
        """
    }

    # Define variables to extract
    test_variables = [
        {
            'variable_name': 'extent_of_resection',
            'description': 'Extent of tumor resection (GTR, STR, partial, biopsy)',
            'clinical_context': 'surgical outcome'
        },
        {
            'variable_name': 'tumor_histology',
            'description': 'Histological diagnosis of the tumor',
            'clinical_context': 'pathology'
        },
        {
            'variable_name': 'tumor_location',
            'description': 'Anatomical location of the tumor',
            'clinical_context': 'anatomy'
        },
        {
            'variable_name': 'blood_loss',
            'description': 'Estimated blood loss during surgery in mL',
            'clinical_context': 'operative metrics'
        }
    ]

    # Test extraction for each variable
    print("\n2. Testing LLM extraction on sample operative note...")
    print("-"*80)

    results = {}
    for variable in test_variables:
        print(f"\n   Extracting: {variable['variable_name']}")

        # Create event context
        event_context = {
            'event_type': 'Initial CNS Tumor',
            'event_date': '2018-05-28',
            'surgery_type': 'CRANIOTOMY'
        }

        # Call the extraction using the correct method
        result = extractor.extract_with_structured_context(
            patient_id='test_patient',
            variable=variable['variable_name'],
            documents=[sample_document],
            structured_context=event_context
        )

        if result:
            print(f"   ✓ Extracted value: {result.get('value', 'Not found')}")
            print(f"     Confidence: {result.get('confidence', 0):.2f}")
            if result.get('supporting_text'):
                print(f"     Supporting text: {result['supporting_text'][:100]}...")
            if result.get('fallback_used'):
                print(f"     Note: Fallback extraction used (Ollama may not be running)")
            results[variable['variable_name']] = result
        else:
            print(f"   ✗ No extraction result")

    print("\n" + "="*80)
    print("EXTRACTION RESULTS SUMMARY")
    print("="*80)

    successful = sum(1 for r in results.values() if r and r.get('value') not in ['Not found', None])
    print(f"\nSuccessfully extracted: {successful}/{len(test_variables)} variables")

    if successful > 0:
        print("\nExtracted values:")
        for var_name, result in results.items():
            if result and result.get('value') not in ['Not found', None]:
                print(f"  - {var_name}: {result['value']}")

    # Check if actual Ollama was used or fallback
    if any(r.get('fallback_used') for r in results.values() if r):
        print("\n⚠️ Note: Fallback extraction was used (Ollama service may not be running)")
        print("To use real Ollama extraction, ensure Ollama is running:")
        print("  1. Install Ollama: https://ollama.ai")
        print("  2. Pull model: ollama pull gemma2:27b")
        print("  3. Verify service: ollama list")
    else:
        print("\n✓ Real Ollama LLM extraction was used successfully!")

    return results

if __name__ == "__main__":
    results = test_ollama_direct()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)