#!/usr/bin/env python3
"""
Test PDF processing pipeline independently
Tests: Binary extraction -> Text extraction -> Document caching -> MedGemma prompting
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from agents.binary_file_agent import BinaryFileAgent
from agents.medgemma_agent import MedGemmaAgent
from utils.document_text_cache import DocumentTextCache

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_pdf_processing():
    """Test the complete PDF processing pipeline"""

    print("="*80)
    print("PDF PROCESSING TEST")
    print("="*80)

    # Initialize agents
    print("\n1. Initializing agents...")
    binary_agent = BinaryFileAgent()
    medgemma_agent = MedGemmaAgent()
    doc_cache = DocumentTextCache(db_path="data/document_text_cache.duckdb")
    print("✅ Agents initialized")

    # Test PDF from the workflow that failed
    test_pdf = {
        'binary_id': 'Binary/e5YPzl7xeW22hxwtmbX_4O_U6IShXznnCV9uDwmfCWr03',
        'document_reference_id': 'test_doc_1',
        'dr_date': '2018-05-28 00:00:00',
        'dr_type_text': 'Imaging Report',
        'dr_category_text': 'Radiology',
        'content_type': 'application/pdf',
        'patient_fhir_id': 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    }

    print(f"\n2. Testing PDF extraction...")
    print(f"   Binary ID: {test_pdf['binary_id']}")

    try:
        # Extract text from binary
        extracted_text, error = binary_agent.extract_text_from_binary(
            binary_id=test_pdf['binary_id'],
            patient_fhir_id=test_pdf['patient_fhir_id'],
            content_type=test_pdf['content_type'],
            document_reference_id=test_pdf['document_reference_id']
        )

        if error:
            print(f"❌ Extraction error: {error}")
            return False

        if extracted_text:
            print(f"✅ Text extracted: {len(extracted_text)} chars")
            print(f"   Preview: {extracted_text[:200]}...")
        else:
            print("❌ No text extracted")
            return False

    except Exception as e:
        print(f"❌ Binary extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n3. Testing document caching...")
    try:
        # Create cached document
        from utils.document_text_cache import CachedDocument
        import hashlib
        from datetime import datetime

        cached_doc = CachedDocument(
            document_id=test_pdf['document_reference_id'],
            patient_fhir_id=test_pdf['patient_fhir_id'],
            binary_id=test_pdf['binary_id'],
            document_type='imaging_report',
            document_date=test_pdf['dr_date'],
            content_type=test_pdf['content_type'],
            dr_type_text=test_pdf.get('dr_type_text'),
            dr_category_text=test_pdf.get('dr_category_text'),
            dr_description=None,
            extracted_text=extracted_text,
            text_length=len(extracted_text),
            text_hash=hashlib.sha256(extracted_text.encode()).hexdigest(),
            extraction_timestamp=datetime.now(),
            extraction_method='binary_file_agent',
            extraction_version='1.0',
            extractor_agent='BinaryFileAgent',
            s3_bucket=None,
            s3_key=None,
            s3_last_modified=None,
            extraction_success=True,
            extraction_error=None,
            age_at_document_days=None,
            additional_metadata=None
        )

        success = doc_cache.cache_document(cached_doc)
        if success:
            print("✅ Document cached successfully")
        else:
            print("⚠️  Document already in cache (this is OK)")

    except Exception as e:
        print(f"❌ Document caching failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n4. Testing MedGemma prompt generation...")
    try:
        # Test the function that was failing
        from agents.extraction_prompts import build_imaging_classification_prompt

        # Build report dict (matching imaging text report structure)
        report = {
            'diagnostic_report_id': test_pdf['document_reference_id'],
            'imaging_date': test_pdf['dr_date'],
            'report_conclusion': extracted_text,  # PDF text goes in report_conclusion
            'patient_fhir_id': test_pdf['patient_fhir_id']
        }

        # Build context with minimal surgical history
        context = {
            'patient_id': test_pdf['patient_fhir_id'],
            'surgical_history': [],
            'report_date': test_pdf['dr_date']
        }

        # Try calling with both arguments
        print("   Testing build_imaging_classification_prompt()...")
        prompt = build_imaging_classification_prompt(report, context)
        print(f"✅ Prompt generated: {len(prompt)} chars")
        print(f"   Preview: {prompt[:200]}...")

    except Exception as e:
        print(f"❌ Prompt generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n5. Testing MedGemma extraction (optional - requires Ollama)...")
    try:
        # Try a simple extraction using the prompt we just built
        result = medgemma_agent.extract(prompt, "imaging_classification")

        if result and result.success:
            print(f"✅ MedGemma extraction succeeded")
            print(f"   Classification: {result.extracted_data.get('imaging_type', 'unknown')}")
            print(f"   Confidence: {result.confidence}")
        else:
            error_msg = result.error if result else "No result returned"
            print(f"⚠️  MedGemma extraction failed: {error_msg}")
            print("   (This is OK if Ollama is not running)")

    except Exception as e:
        print(f"⚠️  MedGemma extraction failed: {e}")
        print("   (This is OK if Ollama is not running)")

    print("\n" + "="*80)
    print("PDF PROCESSING TEST COMPLETE")
    print("="*80)
    return True

if __name__ == "__main__":
    success = test_pdf_processing()
    sys.exit(0 if success else 1)
