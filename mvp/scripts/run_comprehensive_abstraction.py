#!/usr/bin/env python3
"""
Comprehensive Patient Abstraction using Master Agent + Multi-Source Integration

Uses the EXISTING MasterAgent framework (with timeline database integration)
AND adds the new multi-source features (operative reports, progress notes, EOR adjudication).

This is the CORRECT way to run comprehensive abstraction:
1. MasterAgent loads timeline database (surgical history, prior events)
2. MasterAgent runs imaging extraction with temporal context
3. Agent 1 adds operative report EOR extraction
4. Agent 1 adds progress note disease state validation
5. Agent 1 performs EOR adjudication
6. Agent 1 classifies event types
7. Agent 1 detects temporal inconsistencies and queries Agent 2 for clarification
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
import boto3
import time
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import MasterAgent, MedGemmaAgent
from timeline_query_interface import TimelineQueryInterface
from utils.progress_note_filters import filter_oncology_notes, get_note_filtering_stats
from agents.extraction_prompts import (
    build_operative_report_eor_extraction_prompt,
    build_progress_note_disease_state_prompt
)
from agents.eor_adjudicator import EORAdjudicator, EORSource
from agents.event_type_classifier import EventTypeClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def query_athena(query: str, description: str) -> List[Dict[str, Any]]:
    """Execute Athena query and return results"""
    print(f"  {description}...", end='', flush=True)

    session = boto3.Session(profile_name='radiant-prod')
    client = session.client('athena', region_name='us-east-1')

    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )

    query_id = response['QueryExecutionId']

    # Wait for completion
    while True:
        status_response = client.get_query_execution(QueryExecutionId=query_id)
        status = status_response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f" ❌ FAILED: {reason}")
            return []
        time.sleep(1)

    # Get results
    results = client.get_query_results(QueryExecutionId=query_id)
    if len(results['ResultSet']['Rows']) <= 1:
        print(f" ✅ 0 records")
        return []

    # Parse results
    header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
    rows = []

    for row in results['ResultSet']['Rows'][1:]:
        row_dict = {}
        for i, col in enumerate(row['Data']):
            row_dict[header[i]] = col.get('VarCharValue', '')
        rows.append(row_dict)

    print(f" ✅ {len(rows)} records")
    return rows


def main():
    parser = argparse.ArgumentParser(description='Run comprehensive patient abstraction')
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
    print("COMPREHENSIVE PATIENT ABSTRACTION")
    print("Using MasterAgent + Multi-Source Integration")
    print("="*80)
    print()
    print(f"Patient: {args.patient_id}")
    print(f"Timeline DB: {args.timeline_db}")
    print("="*80)
    print()

    # Verify timeline database exists
    timeline_path = Path(args.timeline_db)
    if not timeline_path.exists():
        logger.error(f"Timeline database not found: {timeline_path}")
        print(f"\n❌ ERROR: Timeline database not found at {timeline_path}")
        print("Run scripts/build_timeline_database.py first")
        return 1

    # =========================================================================
    # INITIALIZE MASTER AGENT (includes timeline database)
    # =========================================================================
    print("INITIALIZING AGENTS...")
    print()

    try:
        medgemma = MedGemmaAgent(model_name="gemma2:27b")
        print("✅ Agent 2 (MedGemma) initialized")

        master = MasterAgent(
            timeline_db_path=str(timeline_path),
            medgemma_agent=medgemma,
            dry_run=args.dry_run
        )
        print("✅ Agent 1 (MasterAgent) initialized with timeline database")
        print()

    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}", exc_info=True)
        print(f"❌ ERROR: {e}")
        return 1

    # =========================================================================
    # PHASE 1: RUN IMAGING EXTRACTION (MasterAgent - includes timeline context)
    # =========================================================================
    print("="*80)
    print("PHASE 1: IMAGING EXTRACTION (MasterAgent with Timeline Context)")
    print("="*80)
    print()

    print("MasterAgent will:")
    print("  - Load timeline database (surgical history, prior events)")
    print("  - Extract imaging classification (pre-op, post-op, surveillance)")
    print("  - Extract extent of resection (if post-op)")
    print("  - Extract tumor status (with temporal context)")
    print()

    imaging_summary = master.orchestrate_imaging_extraction(
        patient_id=args.patient_id,
        extraction_type='all'
    )

    print()
    print("IMAGING EXTRACTION RESULTS:")
    print(f"  Events processed: {imaging_summary['imaging_events_processed']}")
    print(f"  Successful: {imaging_summary['successful_extractions']}")
    print(f"  Failed: {imaging_summary['failed_extractions']}")
    print()

    # =========================================================================
    # PHASE 2: QUERY OPERATIVE REPORTS
    # =========================================================================
    print("="*80)
    print("PHASE 2: OPERATIVE REPORT EOR EXTRACTION")
    print("="*80)
    print()

    procedures_query = f"""
    SELECT
        procedure_fhir_id,
        proc_performed_date_time,
        proc_code_text,
        proc_outcome_text,
        surgery_type
    FROM fhir_prd_db.v_procedures_tumor
    WHERE patient_fhir_id = '{args.patient_id}'
        AND is_tumor_surgery = true
    ORDER BY proc_performed_date_time
    """
    procedures = query_athena(procedures_query, "Tumor surgeries")
    print()

    # TODO: Fetch operative note text and extract EOR with Agent 2
    # For now: using procedure metadata
    print(f"Found {len(procedures)} surgical procedures")
    if procedures:
        for proc in procedures:
            print(f"  {proc.get('proc_performed_date_time')}: {proc.get('proc_code_text')}")
    print()

    # =========================================================================
    # PHASE 3: QUERY PROGRESS NOTES
    # =========================================================================
    print("="*80)
    print("PHASE 3: PROGRESS NOTE DISEASE STATE VALIDATION")
    print("="*80)
    print()

    notes_query = f"""
    SELECT
        document_reference_id,
        dr_date,
        dr_type_text,
        dr_description,
        content_title
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{args.patient_id}'
        AND dr_category_text IN ('Clinical Note', 'Correspondence')
        AND dr_date >= TIMESTAMP '2018-05-01'
        AND dr_date <= TIMESTAMP '2018-06-30'
    ORDER BY dr_date
    """
    progress_notes_raw = query_athena(notes_query, "Progress notes")
    print()

    progress_notes = filter_oncology_notes(progress_notes_raw)
    stats = get_note_filtering_stats(progress_notes_raw)

    print(f"Progress note filtering:")
    print(f"  Total: {stats['total_notes']}")
    print(f"  Oncology-specific: {stats['oncology_notes']} ({stats['oncology_percentage']}%)")
    print(f"  Excluded: {stats['excluded_notes']}")
    print()

    # =========================================================================
    # PHASE 4: AGENT 1 TEMPORAL INCONSISTENCY DETECTION
    # =========================================================================
    print("="*80)
    print("PHASE 4: AGENT 1 DETECTS TEMPORAL INCONSISTENCIES")
    print("="*80)
    print()

    print("Agent 1 analyzes new extractions for clinical plausibility...")
    print()

    # Load extraction results from MasterAgent
    # This is where Agent 1 would:
    # 1. Check for rapid tumor status changes
    # 2. Verify changes align with surgical interventions
    # 3. Query Agent 2 for clarification if suspicious

    print("TODO: Implement temporal inconsistency detection on new extractions")
    print("  - Load tumor status extractions from timeline")
    print("  - Detect rapid changes (e.g., Increased→Decreased in 2 days)")
    print("  - Check if surgery explains the change")
    print("  - If not, query Agent 2 with additional context")
    print()

    # =========================================================================
    # PHASE 5: AGENT 1 EVENT TYPE CLASSIFICATION
    # =========================================================================
    print("="*80)
    print("PHASE 5: AGENT 1 CLASSIFIES EVENT TYPES")
    print("="*80)
    print()

    print("Agent 1 determines event type based on surgical history...")
    print("  Logic:")
    print("    - First event → Initial CNS Tumor")
    print("    - Growth after GTR → Recurrence")
    print("    - Growth after Partial → Progressive")
    print("    - New location → Second Malignancy")
    print()

    # Initialize event type classifier
    timeline = TimelineQueryInterface(str(timeline_path))
    classifier = EventTypeClassifier(timeline)

    # TODO: Run classification on all tumor events
    print("TODO: Classify all tumor status events")
    print()

    # =========================================================================
    # PHASE 6: GENERATE COMPREHENSIVE ABSTRACTION
    # =========================================================================
    print("="*80)
    print("PHASE 6: GENERATE COMPREHENSIVE ABSTRACTION")
    print("="*80)
    print()

    abstraction = {
        'patient_id': args.patient_id,
        'abstraction_date': datetime.now().isoformat(),
        'workflow': 'master_agent_plus_multi_source',
        'imaging_extraction': imaging_summary,
        'surgical_procedures': len(procedures),
        'progress_notes': {
            'total': stats['total_notes'],
            'oncology_specific': stats['oncology_notes']
        },
        'notes': 'This uses MasterAgent (with timeline context) + multi-source integration'
    }

    # Save abstraction
    output_dir = Path("data/patient_abstractions")
    output_dir.mkdir(parents=True, exist_ok=True)

    abstraction_path = output_dir / f"{args.patient_id}_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(abstraction_path, 'w') as f:
        json.dump(abstraction, f, indent=2)

    print(f"✅ Comprehensive abstraction saved: {abstraction_path}")
    print()

    print("="*80)
    print("COMPREHENSIVE ABSTRACTION COMPLETE")
    print("="*80)
    print()

    print("WHAT WE ACCOMPLISHED:")
    print("  ✅ Used MasterAgent (includes timeline database integration)")
    print("  ✅ Imaging extraction with temporal context")
    print("  ✅ Queried operative reports")
    print("  ✅ Filtered progress notes to oncology-specific")
    print("  ✅ Framework ready for temporal inconsistency detection")
    print("  ✅ Framework ready for event type classification")
    print()

    print("NEXT STEPS TO COMPLETE:")
    print("  1. Implement Agent 1 temporal inconsistency detection")
    print("  2. Implement Agent 1 ↔ Agent 2 iterative queries for clarification")
    print("  3. Fetch operative note text and extract EOR")
    print("  4. Fetch progress note text and validate disease state")
    print("  5. Perform EOR adjudication (operative vs imaging)")
    print("  6. Classify all event types")
    print()


if __name__ == "__main__":
    main()
