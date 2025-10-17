#!/usr/bin/env python3
"""
Run the Complete Integrated Pipeline
=====================================
This executes the full 5-phase extraction pipeline we defined,
with all components properly integrated as documented.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import sys

# Add to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from form_extractors.integrated_pipeline_extractor import IntegratedPipelineExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_full_pipeline():
    """
    Run the complete integrated pipeline with all 5 phases.
    This is the actual implementation we built, not a test.
    """
    logger.info("\n" + "="*80)
    logger.info("RUNNING COMPLETE INTEGRATED PIPELINE")
    logger.info("All 5 phases with comprehensive enrichment")
    logger.info("="*80)

    # Configuration
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"  # Patient with known post-op imaging discrepancy
    birth_date = "2005-02-15"  # Corrected birth date based on age calculations

    # Paths
    staging_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files"
    binary_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/binary_files"
    dictionary_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction/Dictionary/CBTN_DataDictionary_2025-10-15.csv"

    logger.info(f"\n📋 PATIENT INFORMATION:")
    logger.info(f"   Patient ID: {patient_id}")
    logger.info(f"   Birth Date: {birth_date}")
    logger.info(f"   Staging Path: {staging_path}")

    try:
        # =========================================================
        # INITIALIZE THE INTEGRATED PIPELINE
        # =========================================================
        logger.info("\n🚀 INITIALIZING INTEGRATED PIPELINE...")

        pipeline = IntegratedPipelineExtractor(
            staging_base_path=staging_path,
            binary_files_path=binary_path,
            data_dictionary_path=dictionary_path,
            ollama_model="gemma2:27b"
        )

        logger.info("✓ Pipeline initialized with all components:")
        logger.info("   - Phase 1: Structured Data Harvester")
        logger.info("   - Phase 2: Clinical Timeline Builder")
        logger.info("   - Phase 3: Three-tier Document Selector")
        logger.info("   - Phase 4: Query-enabled LLM Extractor")
        logger.info("   - Phase 5: Cross-source Validator")
        logger.info("   - Query Engine for validation")
        logger.info("   - Service Request Integration")
        logger.info("   - Molecular Diagnosis Integration")
        logger.info("   - Problem List Analyzer")
        logger.info("   - Chemotherapy Identifier (5-strategy)")
        logger.info("   - Surgery Classifier")
        logger.info("   - REDCap Terminology Mapper")

        # =========================================================
        # RUN THE COMPLETE EXTRACTION
        # =========================================================
        logger.info("\n📊 EXECUTING COMPREHENSIVE EXTRACTION...")
        logger.info("="*60)

        # This single call orchestrates ALL 5 phases
        results = pipeline.extract_patient_comprehensive(
            patient_id=patient_id,
            birth_date=birth_date
        )

        # =========================================================
        # DISPLAY RESULTS
        # =========================================================
        logger.info("\n" + "="*80)
        logger.info("EXTRACTION RESULTS")
        logger.info("="*80)

        # Overall statistics
        logger.info("\n📈 EXTRACTION STATISTICS:")
        quality_metrics = results.get('quality_metrics', {})
        logger.info(f"   Extraction completeness: {quality_metrics.get('extraction_completeness', 0)*100:.1f}%")
        logger.info(f"   Fallback trigger rate: {quality_metrics.get('fallback_trigger_rate', 0)*100:.1f}%")
        logger.info(f"   Imaging validation rate: {quality_metrics.get('imaging_validation_rate', 0)*100:.1f}%")
        logger.info(f"   Discrepancy rate: {quality_metrics.get('discrepancy_rate', 0)*100:.1f}%")
        logger.info(f"   Average confidence: {quality_metrics.get('average_confidence', 0):.2f}")

        # Structured features summary
        structured = results.get('structured_features', {})
        logger.info("\n📋 STRUCTURED FEATURES EXTRACTED:")
        logger.info(f"   Total surgeries: {structured.get('total_surgeries', 0)}")
        logger.info(f"   Chemotherapy drugs: {len(structured.get('chemotherapy_drugs', []))}")
        logger.info(f"   Molecular markers: {len(structured.get('molecular_markers', []))}")
        logger.info(f"   Problem list items: {structured.get('total_problems', 0)}")
        logger.info(f"   Has post-op validation: {structured.get('has_postop_imaging_validation', False)}")

        # Clinical timeline summary
        timeline = results.get('clinical_timeline', [])
        logger.info("\n📅 CLINICAL TIMELINE:")
        logger.info(f"   Total events: {len(timeline)}")
        surgical_events = [e for e in timeline if e.get('event_type') == 'surgery']
        logger.info(f"   Surgical events: {len(surgical_events)}")

        # Process each surgical event's extraction
        events = results.get('events', [])
        logger.info("\n🔍 EVENT-BASED EXTRACTION RESULTS:")

        for idx, event in enumerate(events, 1):
            logger.info(f"\n   EVENT {idx}:")
            logger.info(f"      Date: {event.get('event_date', 'Unknown')}")
            logger.info(f"      Type: {event.get('event_type', 'Unknown')}")

            # Check for critical extent of resection
            extracted_vars = event.get('extracted_variables', {})
            if 'extent_of_tumor_resection' in extracted_vars:
                extent_data = extracted_vars['extent_of_tumor_resection']
                logger.info(f"\n      🎯 EXTENT OF RESECTION:")
                logger.info(f"         Value: {extent_data.get('value')}")
                logger.info(f"         Confidence: {extent_data.get('confidence', 0):.2f}")
                logger.info(f"         Validation: {extent_data.get('validation', 'None')}")

                # Check for discrepancy
                if extent_data.get('discrepancy'):
                    logger.warning(f"         ⚠️ DISCREPANCY DETECTED!")
                    logger.warning(f"         Original: {extent_data.get('original_value')}")
                    logger.warning(f"         Override reason: {extent_data.get('override_reason')}")

            # Document statistics
            doc_stats = event.get('document_stats', {})
            logger.info(f"\n      📄 DOCUMENTS:")
            logger.info(f"         Total documents: {doc_stats.get('total_documents', 0)}")
            doc_types = doc_stats.get('documents_by_type', {})
            if doc_types:
                for doc_type, count in list(doc_types.items())[:3]:
                    logger.info(f"         - {doc_type}: {count}")

            # Extraction metadata
            metadata = event.get('extraction_metadata', {})
            if metadata.get('fallback_triggered'):
                logger.info(f"         ⟲ Fallback used for recovery")
            if metadata.get('imaging_validation'):
                logger.info(f"         ✓ Post-op imaging validation performed")

        # Static forms summary
        forms = results.get('forms', {})
        logger.info("\n📝 STATIC FORMS EXTRACTED:")
        for form_name, form_data in forms.items():
            logger.info(f"   {form_name}: {len(form_data) if isinstance(form_data, dict) else 'Extracted'}")

        # Timing
        duration = results.get('extraction_duration_seconds', 0)
        logger.info(f"\n⏱️ EXTRACTION DURATION: {duration:.1f} seconds")

        # =========================================================
        # SAVE RESULTS
        # =========================================================
        output_path = Path(f"extraction_results_{patient_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(output_path, 'w') as f:
            # Convert any datetime objects and numpy types to JSON-serializable formats
            def json_serial(obj):
                import numpy as np
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif isinstance(obj, (np.integer, np.int64)):
                    return int(obj)
                elif isinstance(obj, (np.floating, np.float64)):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                raise TypeError(f"Type {type(obj)} not serializable")

            json.dump(results, f, indent=2, default=json_serial)

        logger.info(f"\n💾 RESULTS SAVED TO: {output_path}")

        # =========================================================
        # KEY FINDINGS
        # =========================================================
        logger.info("\n" + "="*80)
        logger.info("KEY FINDINGS")
        logger.info("="*80)

        # Check if post-op imaging validation occurred
        if any(e.get('extracted_variables', {}).get('extent_of_tumor_resection', {}).get('discrepancy')
               for e in events):
            logger.info("\n🔴 CRITICAL FINDING: Post-operative imaging override detected!")
            logger.info("   This validates our key discovery about operative note inaccuracy.")

        # Check fallback usage
        fallback_count = sum(1 for e in events
                           if e.get('extraction_metadata', {}).get('fallback_triggered'))
        if fallback_count > 0:
            logger.info(f"\n🔄 STRATEGIC FALLBACK: Used in {fallback_count} events for recovery")

        # Check multi-source validation
        high_confidence = [v for e in events
                         for v in e.get('extracted_variables', {}).values()
                         if v.get('confidence', 0) > 0.8]
        logger.info(f"\n✅ HIGH CONFIDENCE: {len(high_confidence)} variables with confidence > 0.8")

        logger.info("\n" + "="*80)
        logger.info("🎉 PIPELINE EXECUTION COMPLETE!")
        logger.info("="*80)

        return results

    except Exception as e:
        logger.error(f"\n❌ PIPELINE EXECUTION FAILED: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


if __name__ == "__main__":
    # Run the complete pipeline
    results = run_full_pipeline()

    if results:
        logger.info("\n✨ Success! The integrated pipeline executed successfully.")
        logger.info("Review the results above for critical findings and validation outcomes.")
    else:
        logger.info("\n⚠️ Pipeline execution encountered errors. Check logs for details.")