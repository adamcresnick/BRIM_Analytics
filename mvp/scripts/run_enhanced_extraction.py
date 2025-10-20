#!/usr/bin/env python3
"""
Run Enhanced Extraction with Temporal Validation

Uses EnhancedMasterAgent which:
1. Runs base extraction with timeline context (MasterAgent)
2. Detects temporal inconsistencies in NEW extractions
3. Queries Agent 2 for clarification when suspicious
4. Classifies event types
5. Generates comprehensive abstraction

This is the COMPLETE workflow we designed.
"""

import sys
from pathlib import Path
import argparse
import logging
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.enhanced_master_agent import EnhancedMasterAgent
from agents.medgemma_agent import MedGemmaAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Run enhanced extraction with temporal validation')
    parser.add_argument(
        '--patient-id',
        type=str,
        default='e4BwD8ZYDBccepXcJ.Ilo3w3',
        help='Patient FHIR ID to process'
    )
    parser.add_argument(
        '--timeline-db',
        type=str,
        default='data/timeline.duckdb',
        help='Path to timeline DuckDB database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run extraction but don\'t save results to database'
    )

    args = parser.parse_args()

    print("="*80)
    print("ENHANCED EXTRACTION WITH TEMPORAL VALIDATION")
    print("="*80)
    print()
    print(f"Patient: {args.patient_id}")
    print(f"Timeline DB: {args.timeline_db}")
    print()
    print("Workflow:")
    print("  1. Base imaging extraction (MasterAgent with timeline context)")
    print("  2. Temporal inconsistency detection")
    print("  3. Iterative Agent 2 queries for clarification")
    print("  4. Event type classification")
    print("  5. Comprehensive abstraction generation")
    print()
    print("="*80)
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
        print("Initializing agents...")
        medgemma = MedGemmaAgent(model_name="gemma2:27b")
        print("✅ Agent 2 (MedGemma) initialized")

        enhanced_master = EnhancedMasterAgent(
            timeline_db_path=str(timeline_path),
            medgemma_agent=medgemma,
            dry_run=args.dry_run
        )
        print("✅ Agent 1 (Enhanced MasterAgent) initialized")
        print()

    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}", exc_info=True)
        print(f"❌ ERROR: {e}")
        return 1

    # Run comprehensive extraction
    try:
        print("="*80)
        print("STARTING ENHANCED EXTRACTION")
        print("="*80)
        print()

        comprehensive_summary = enhanced_master.orchestrate_comprehensive_extraction(
            patient_id=args.patient_id
        )

        # Print results
        print()
        print("="*80)
        print("EXTRACTION RESULTS")
        print("="*80)
        print()

        print(f"Patient: {comprehensive_summary['patient_id']}")
        print()

        # Phase 1: Imaging Extraction
        imaging = comprehensive_summary['imaging_extraction']
        print("PHASE 1: IMAGING EXTRACTION")
        print(f"  Events processed: {imaging['imaging_events_processed']}")
        print(f"  Successful: {imaging['successful_extractions']}")
        print(f"  Failed: {imaging['failed_extractions']}")
        print()

        # Phase 2: Temporal Inconsistencies
        temporal = comprehensive_summary.get('temporal_inconsistencies', {})
        print("PHASE 2: TEMPORAL INCONSISTENCIES")
        print(f"  Total detected: {temporal.get('count', 0)}")
        print(f"  High severity: {temporal.get('high_severity', 0)}")
        print(f"  Requiring Agent 2 query: {temporal.get('requiring_agent2_query', 0)}")

        if temporal.get('details'):
            print()
            print("  Inconsistencies:")
            for inc in temporal['details']:
                print(f"    - {inc['description']}")
                print(f"      Severity: {inc['severity']}")
                print(f"      Requires Agent 2: {inc['requires_agent2_query']}")
                print()

        # Phase 3: Agent 2 Clarifications
        clarifications = comprehensive_summary.get('agent2_clarifications', {})
        print("PHASE 3: AGENT 2 CLARIFICATIONS")
        print(f"  Queries sent: {clarifications.get('count', 0)}")

        if clarifications.get('resolutions'):
            print()
            print("  Resolutions:")
            for res in clarifications['resolutions']:
                if res['success']:
                    response = res.get('agent2_response', {})
                    print(f"    - {res['inconsistency_id']}")
                    print(f"      Plausibility: {response.get('clinical_plausibility', 'N/A')}")
                    print(f"      Action: {response.get('recommended_action', 'N/A')}")
                    print(f"      Confidence: {response.get('confidence', 0.0)}")
                else:
                    print(f"    - {res['inconsistency_id']}: FAILED - {res['error']}")
                print()

        # Phase 4: Event Classifications
        classifications = comprehensive_summary.get('event_type_classifications', {})
        print("PHASE 4: EVENT TYPE CLASSIFICATIONS")
        print(f"  Events classified: {classifications.get('count', 0)}")

        if classifications.get('classifications'):
            print()
            print("  Classifications:")
            for cls in classifications['classifications'][:5]:  # First 5
                print(f"    - {cls['event_date']}: {cls['event_type']}")
                print(f"      Confidence: {cls['confidence']}")
                print(f"      Reasoning: {cls['reasoning'][:80]}...")
                print()

        # Save comprehensive abstraction with timestamped folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path("data/patient_abstractions") / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

        abstraction_path = output_dir / f"{args.patient_id}_enhanced.json"

        with open(abstraction_path, 'w') as f:
            json.dump(comprehensive_summary, f, indent=2)

        # Save checkpoint (for resume capability)
        checkpoint_path = output_dir / f"{args.patient_id}_checkpoint.json"
        checkpoint_data = {
            'patient_id': args.patient_id,
            'timestamp': timestamp,
            'status': 'complete',
            'phases_completed': ['imaging', 'temporal', 'agent2_queries', 'event_classification']
        }
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        print()
        print(f"✅ Comprehensive abstraction saved: {abstraction_path}")
        print(f"✅ Checkpoint saved: {checkpoint_path}")
        print()

        print("="*80)
        print("ENHANCED EXTRACTION COMPLETE")
        print("="*80)
        print()

        return 0

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
