#!/usr/bin/env python3
"""
Run Imaging Extraction Pipeline

Orchestrates multi-agent extraction workflow for radiology reports.
Extracts imaging classification, extent of resection, and tumor status.

Usage:
    # Extract all types for test patient
    python3 scripts/run_imaging_extraction.py

    # Dry run (don't save to database)
    python3 scripts/run_imaging_extraction.py --dry-run

    # Extract specific type only
    python3 scripts/run_imaging_extraction.py --extraction-type imaging_classification

    # Different patient
    python3 scripts/run_imaging_extraction.py --patient-id Patient/xyz
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import MasterAgent, MedGemmaAgent
from timeline_query_interface import TimelineQueryInterface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test patient ID from summary
TEST_PATIENT_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'


def main():
    parser = argparse.ArgumentParser(description='Run imaging extraction pipeline')
    parser.add_argument(
        '--patient-id',
        type=str,
        default=TEST_PATIENT_ID,
        help='Patient FHIR ID to process'
    )
    parser.add_argument(
        '--extraction-type',
        type=str,
        choices=['all', 'imaging_classification', 'extent_of_resection', 'tumor_status'],
        default='all',
        help='Type of extraction to run'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run extraction but don\'t save results to database'
    )
    parser.add_argument(
        '--timeline-db',
        type=str,
        default='data/timeline.duckdb',
        help='Path to timeline DuckDB database'
    )
    parser.add_argument(
        '--ollama-url',
        type=str,
        default='http://localhost:11434',
        help='Ollama API URL'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("IMAGING EXTRACTION PIPELINE")
    print("=" * 80)
    print(f"Patient ID: {args.patient_id}")
    print(f"Extraction type: {args.extraction_type}")
    print(f"Dry run: {args.dry_run}")
    print(f"Timeline DB: {args.timeline_db}")
    print(f"Ollama URL: {args.ollama_url}")
    print("=" * 80)
    print()

    # Verify timeline database exists
    timeline_path = Path(args.timeline_db)
    if not timeline_path.exists():
        logger.error(f"Timeline database not found: {timeline_path}")
        print(f"\n❌ ERROR: Timeline database not found at {timeline_path}")
        print("Run scripts/build_timeline_database.py first")
        return 1

    # Initialize agents
    try:
        logger.info("Initializing MedGemma agent...")
        medgemma = MedGemmaAgent(
            model_name="gemma2:27b",
            ollama_url=args.ollama_url,
            temperature=0.1
        )
        logger.info("✓ MedGemma agent initialized")

        logger.info("Initializing Master agent...")
        master = MasterAgent(
            timeline_db_path=str(timeline_path),
            medgemma_agent=medgemma,
            dry_run=args.dry_run
        )
        logger.info("✓ Master agent initialized")

    except ConnectionError as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        print(f"\n❌ ERROR: Cannot connect to Ollama at {args.ollama_url}")
        print("\nMake sure Ollama is running:")
        print("  1. Start Ollama: ollama serve")
        print("  2. Pull MedGemma: ollama pull gemma2:27b")
        return 1

    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        return 1

    # Run extraction
    try:
        print("\n" + "=" * 80)
        print("STARTING EXTRACTION")
        print("=" * 80)
        print()

        summary = master.orchestrate_imaging_extraction(
            patient_id=args.patient_id,
            extraction_type=args.extraction_type
        )

        # Print results
        print("\n" + "=" * 80)
        print("EXTRACTION RESULTS")
        print("=" * 80)
        print()
        print(f"Patient: {summary['patient_id']}")
        print(f"Extraction type: {summary['extraction_type']}")
        print(f"Duration: {summary['start_time']} → {summary['end_time']}")
        print()
        print(f"Imaging events processed: {summary['imaging_events_processed']}")
        print(f"✓ Successful extractions: {summary['successful_extractions']}")
        print(f"✗ Failed extractions: {summary['failed_extractions']}")
        print()

        # Show sample results
        if summary['results']:
            print("Sample results:")
            for result in summary['results'][:5]:  # Show first 5
                status = "✓" if result['success'] else "✗"
                extraction_type = result.get('extraction_type', 'Unknown')
                value = result.get('value', 'N/A')
                confidence = result.get('confidence', 0.0)

                print(f"  {status} {result['event_id']}")
                print(f"     Type: {extraction_type}")
                print(f"     Value: {value}")
                print(f"     Confidence: {confidence:.2f}")

                if result.get('error'):
                    print(f"     Error: {result['error']}")
                print()

        # Save detailed results to file
        output_dir = Path('data/extraction_results')
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"imaging_extraction_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"Detailed results saved to: {output_file}")

        print("\n" + "=" * 80)
        print("✅ EXTRACTION PIPELINE COMPLETE")
        print("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        print(f"\n❌ EXTRACTION FAILED: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
