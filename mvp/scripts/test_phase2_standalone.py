#!/usr/bin/env python3
"""
Test Phase 2 Extraction Standalone

Purpose: Test Phase 2 extraction (imaging PDFs, operative reports, progress notes)
         without repeating Phase 1 queries. Loads data from Phase 1 checkpoint.

Usage:
    python3 scripts/test_phase2_standalone.py --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 --checkpoint-dir data/patient_abstractions/20251020_121536

This allows rapid iteration on Phase 2 extraction logic without rerunning
expensive Athena queries from Phase 1.
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.medgemma_agent import MedGemmaAgent
from agents.binary_file_agent import BinaryFileAgent
from utils.document_text_cache import DocumentTextCache
from agents.extraction_prompts import (
    build_imaging_classification_prompt,
    build_tumor_status_extraction_prompt,
    build_operative_report_eor_extraction_prompt,
    build_progress_note_disease_state_prompt
)


def load_checkpoint(checkpoint_dir: Path, checkpoint_name: str = "data_query"):
    """Load Phase 1 checkpoint data"""
    checkpoint_file = checkpoint_dir / f"checkpoint_{checkpoint_name}.json"

    if not checkpoint_file.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_file}")

    with open(checkpoint_file, 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Test Phase 2 extraction standalone")
    parser.add_argument('--patient-id', required=True, help='Patient FHIR ID')
    parser.add_argument('--checkpoint-dir', required=True, help='Directory containing Phase 1 checkpoint')
    parser.add_argument('--phase', choices=['2b', '2c', '2d', 'all'], default='all',
                       help='Which Phase 2 sub-phase to test (default: all)')
    args = parser.parse_args()

    checkpoint_dir = Path(args.checkpoint_dir)

    print("=" * 80)
    print("PHASE 2 STANDALONE TEST")
    print("=" * 80)
    print(f"Patient: {args.patient_id}")
    print(f"Checkpoint: {checkpoint_dir}")
    print(f"Testing: Phase {args.phase}")
    print()

    # Load Phase 1 data
    print("Loading Phase 1 checkpoint...")
    checkpoint_data = load_checkpoint(checkpoint_dir, "data_query")

    imaging_text_reports = checkpoint_data.get('imaging_text_reports', [])
    imaging_pdfs = checkpoint_data.get('imaging_pdfs', [])
    operative_reports = checkpoint_data.get('operative_reports', [])
    prioritized_notes = checkpoint_data.get('prioritized_notes', [])

    print(f"✅ Loaded:")
    print(f"   - {len(imaging_text_reports)} imaging text reports (Phase 2A - already extracted)")
    print(f"   - {len(imaging_pdfs)} imaging PDFs (Phase 2B)")
    print(f"   - {len(operative_reports)} operative reports (Phase 2C)")
    print(f"   - {len(prioritized_notes)} prioritized progress notes (Phase 2D)")
    print()

    # Initialize agents
    print("Initializing agents...")
    medgemma = MedGemmaAgent()
    binary_agent = BinaryFileAgent()
    doc_cache = DocumentTextCache(db_path="data/document_text_cache.duckdb")
    print("✅ Agents initialized")
    print()

    # Phase 2B: Imaging PDFs
    if args.phase in ['2b', 'all'] and imaging_pdfs:
        print("=" * 80)
        print(f"PHASE 2B: EXTRACTING FROM {len(imaging_pdfs)} IMAGING PDFs")
        print("=" * 80)

        for idx, pdf_doc in enumerate(imaging_pdfs[:3], 1):  # Test first 3
            doc_id = pdf_doc['document_reference_id']
            binary_id = pdf_doc['binary_id']
            doc_date = pdf_doc['dr_date']

            print(f"\n[{idx}/3] {doc_id} ({doc_date})")

            # Check cache first
            cached_doc = doc_cache.get_cached_document(doc_id)
            if cached_doc:
                print(f"  ✅ Found in cache (SHA256: {cached_doc.content_hash[:16]}...)")
                extracted_text = cached_doc.extracted_text
            else:
                # Extract text from PDF
                print(f"  📄 Extracting from S3...")
                extracted_text, error = binary_agent.extract_text_from_binary(
                    binary_id,
                    args.patient_id
                )

                if error:
                    print(f"  ❌ Extraction failed: {error}")
                    continue

                print(f"  ✅ Extracted {len(extracted_text)} characters")

                # Cache it
                doc_cache.cache_document_from_binary(
                    document_id=doc_id,
                    binary_id=binary_id,
                    patient_id=args.patient_id,
                    content_type=pdf_doc.get('content_type', 'application/pdf'),
                    extracted_text=extracted_text,
                    dr_date=doc_date,
                    dr_type_text=pdf_doc.get('dr_type_text'),
                    dr_category_text=pdf_doc.get('dr_category_text')
                )
                print(f"  💾 Cached")

            # Extract with MedGemma
            print(f"  🤖 Extracting with MedGemma...")
            classification_prompt = build_imaging_classification_prompt(extracted_text)
            classification_result = medgemma.extract(classification_prompt, "imaging_classification")

            tumor_status_prompt = build_tumor_status_extraction_prompt(extracted_text)
            tumor_status_result = medgemma.extract(tumor_status_prompt, "tumor_status")

            print(f"    Classification: {classification_result.get('imaging_classification', 'N/A')}")
            print(f"    Tumor Status: {tumor_status_result.get('tumor_status', 'N/A')}")

    # Phase 2C: Operative Reports
    if args.phase in ['2c', 'all'] and operative_reports:
        print("\n" + "=" * 80)
        print(f"PHASE 2C: EXTRACTING FROM {len(operative_reports)} OPERATIVE REPORTS")
        print("=" * 80)

        for idx, proc in enumerate(operative_reports[:2], 1):  # Test first 2
            proc_id = proc['procedure_fhir_id']
            proc_date = proc['proc_performed_date_time']
            surgery_type = proc.get('surgery_type', 'Unknown')

            print(f"\n[{idx}/2] {proc_id} - {surgery_type} ({proc_date})")
            print(f"  🔍 Would query for operative note within ±7 days of {proc_date}")
            print(f"  (Skipping actual query - this is just structure test)")

    # Phase 2D: Prioritized Progress Notes
    if args.phase in ['2d', 'all'] and prioritized_notes:
        print("\n" + "=" * 80)
        print(f"PHASE 2D: EXTRACTING FROM {len(prioritized_notes)} PRIORITIZED PROGRESS NOTES")
        print("=" * 80)

        for idx, pn_dict in enumerate(prioritized_notes[:2], 1):  # Test first 2
            note = pn_dict['note']
            priority_reason = pn_dict['priority_reason']

            doc_id = note['document_reference_id']
            binary_id = note['binary_id']
            doc_date = note['dr_date']

            print(f"\n[{idx}/2] {doc_id} ({doc_date})")
            print(f"  Priority: {priority_reason}")

            # Check cache
            cached_doc = doc_cache.get_cached_document(doc_id)
            if cached_doc:
                print(f"  ✅ Found in cache")
                extracted_text = cached_doc.extracted_text
            else:
                print(f"  📄 Extracting from S3...")
                extracted_text, error = binary_agent.extract_text_from_binary(
                    binary_id,
                    args.patient_id,
                    content_type=note.get('content_type', 'application/pdf')
                )

                if error:
                    print(f"  ❌ Extraction failed: {error}")
                    continue

                print(f"  ✅ Extracted {len(extracted_text)} characters")

                # Cache it
                doc_cache.cache_document_from_binary(
                    document_id=doc_id,
                    binary_id=binary_id,
                    patient_id=args.patient_id,
                    content_type=note.get('content_type', 'application/pdf'),
                    extracted_text=extracted_text,
                    dr_date=doc_date,
                    dr_type_text=note.get('dr_type_text'),
                    dr_category_text=note.get('dr_category_text')
                )

            # Extract disease state with MedGemma
            print(f"  🤖 Extracting disease state...")
            disease_state_prompt = build_progress_note_disease_state_prompt(extracted_text)
            disease_state_result = medgemma.extract(disease_state_prompt, "progress_note_disease_state")

            print(f"    Disease state: {disease_state_result.get('disease_state', 'N/A')}")

    print("\n" + "=" * 80)
    print("PHASE 2 STANDALONE TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
