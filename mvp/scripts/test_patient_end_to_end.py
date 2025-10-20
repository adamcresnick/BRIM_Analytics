#!/usr/bin/env python3
"""
End-to-End Patient Workflow Test with Real Data

Tests complete Agent 1 ↔ Agent 2 workflow for patient e4BwD8ZYDBccepXcJ.Ilo3w3
using real data from Athena.

Workflow:
1. Query all data sources (imaging, procedures, progress notes)
2. Filter progress notes to oncology-specific
3. Send extraction requests to Agent 2 (simulated with prompts)
4. Perform Agent 1 EOR adjudication
5. Classify event types
6. Generate patient QA report
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
import boto3
import time
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.progress_note_filters import filter_oncology_notes, get_note_filtering_stats
from agents.extraction_prompts import (
    build_operative_report_eor_extraction_prompt,
    build_progress_note_disease_state_prompt,
    build_tumor_status_extraction_prompt
)
from agents.eor_adjudicator import EORAdjudicator, EORSource


def query_athena(query: str, description: str) -> List[Dict[str, Any]]:
    """Execute Athena query and return results"""
    print(f"  Executing: {description}")

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
    print(f"  Query ID: {query_id}")

    # Wait for completion
    while True:
        status_response = client.get_query_execution(QueryExecutionId=query_id)
        status = status_response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"  ❌ Query {status}: {reason}")
            return []

        time.sleep(2)

    # Get results
    results = client.get_query_results(QueryExecutionId=query_id)

    if len(results['ResultSet']['Rows']) <= 1:
        print(f"  ✅ No results")
        return []

    # Parse results
    header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
    rows = []

    for row in results['ResultSet']['Rows'][1:]:
        row_dict = {}
        for i, col in enumerate(row['Data']):
            row_dict[header[i]] = col.get('VarCharValue', '')
        rows.append(row_dict)

    print(f"  ✅ Found {len(rows)} records")
    return rows


def main():
    """Run end-to-end patient workflow test"""

    print("="*80)
    print("END-TO-END PATIENT WORKFLOW TEST WITH REAL DATA")
    print("="*80)
    print()
    print("Patient: e4BwD8ZYDBccepXcJ.Ilo3w3")
    print("Testing complete Agent 1 ↔ Agent 2 workflow")
    print()
    print("="*80)
    print()

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # =========================================================================
    # PHASE 1: QUERY ALL DATA SOURCES
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 1: AGENT 1 QUERIES ALL DATA SOURCES")
    print("="*80 + "\n")

    # Query 1: Imaging text reports from v_imaging
    print("1. Querying v_imaging for text reports...")
    imaging_query = f"""
    SELECT
        diagnostic_report_id,
        imaging_date,
        report_conclusion,
        imaging_modality
    FROM fhir_prd_db.v_imaging
    WHERE patient_fhir_id = '{patient_id}'
        AND imaging_date >= TIMESTAMP '2018-01-01'
        AND imaging_date <= TIMESTAMP '2018-12-31'
    ORDER BY imaging_date
    """

    imaging_reports = query_athena(imaging_query, "v_imaging text reports")
    print()

    # Query 2: Imaging PDFs from v_binary_files
    print("2. Querying v_binary_files for imaging PDFs...")
    pdf_query = f"""
    SELECT
        document_reference_id,
        binary_id,
        dr_date,
        dr_category_text,
        dr_type_text,
        dr_description,
        content_title,
        content_size_bytes
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
        AND content_type = 'application/pdf'
        AND dr_category_text = 'Imaging Result'
        AND dr_date >= TIMESTAMP '2018-01-01'
        AND dr_date <= TIMESTAMP '2018-12-31'
    ORDER BY dr_date
    """

    imaging_pdfs = query_athena(pdf_query, "Imaging PDFs")
    print()

    # Query 3: Operative reports from v_procedures_tumor
    print("3. Querying v_procedures_tumor for surgical procedures...")
    procedures_query = f"""
    SELECT
        procedure_fhir_id,
        proc_performed_date_time,
        proc_code_text,
        proc_outcome_text,
        pbs_body_site_text,
        surgery_type,
        is_tumor_surgery
    FROM fhir_prd_db.v_procedures_tumor
    WHERE patient_fhir_id = '{patient_id}'
        AND proc_performed_date_time >= TIMESTAMP '2018-01-01'
        AND proc_performed_date_time <= TIMESTAMP '2018-12-31'
        AND is_tumor_surgery = true
    ORDER BY proc_performed_date_time
    """

    procedures = query_athena(procedures_query, "Tumor surgeries")
    print()

    # Query 4: Progress notes from v_binary_files
    print("4. Querying v_binary_files for progress notes...")
    notes_query = f"""
    SELECT
        document_reference_id,
        dr_date,
        dr_category_text,
        dr_type_text,
        dr_description,
        content_title
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
        AND dr_category_text IN ('Clinical Note', 'Correspondence')
        AND dr_date >= TIMESTAMP '2018-04-01'
        AND dr_date <= TIMESTAMP '2018-07-31'
    ORDER BY dr_date
    """

    progress_notes_raw = query_athena(notes_query, "Progress notes (Apr-Jul 2018)")
    print()

    # =========================================================================
    # PHASE 2: FILTER PROGRESS NOTES
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 2: AGENT 1 FILTERS PROGRESS NOTES TO ONCOLOGY-SPECIFIC")
    print("="*80 + "\n")

    progress_notes = filter_oncology_notes(progress_notes_raw)
    stats = get_note_filtering_stats(progress_notes_raw)

    print(f"Total notes: {stats['total_notes']}")
    print(f"Oncology notes: {stats['oncology_notes']} ({stats['oncology_percentage']}%)")
    print(f"Excluded notes: {stats['excluded_notes']}")
    print(f"Exclusion reasons: {stats['exclusion_reasons']}")
    print()

    # =========================================================================
    # PHASE 3: GENERATE AGENT 2 EXTRACTION PROMPTS
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 3: AGENT 1 GENERATES EXTRACTION PROMPTS FOR AGENT 2")
    print("="*80 + "\n")

    extraction_prompts = []

    # Extract tumor status from imaging reports
    print(f"Generating {len(imaging_reports)} tumor_status extraction prompts...")
    for report in imaging_reports[:5]:  # First 5 for demo
        prompt = build_tumor_status_extraction_prompt(
            report={
                'document_text': report.get('report_conclusion', ''),
                'document_date': report.get('imaging_date', 'Unknown'),
                'metadata': {'imaging_modality': report.get('imaging_modality', 'Unknown')}
            },
            context={'events_before': [], 'events_after': []}
        )
        extraction_prompts.append({
            'source_type': 'imaging_text',
            'source_id': report.get('diagnostic_report_id'),
            'extraction_type': 'tumor_status',
            'prompt_length': len(prompt),
            'prompt': prompt
        })

    print(f"  ✅ Generated {len([p for p in extraction_prompts if p['extraction_type'] == 'tumor_status'])} tumor_status prompts")
    print()

    # Extract EOR from operative reports (if available)
    if procedures:
        print(f"Generating {len(procedures)} EOR extraction prompts from operative reports...")
        for proc in procedures:
            # In production, would fetch actual operative note text
            # For now, use procedure metadata
            prompt = build_operative_report_eor_extraction_prompt(
                operative_report={
                    'note_text': f"Procedure: {proc.get('proc_code_text', '')}. Outcome: {proc.get('proc_outcome_text', '')}",
                    'procedure_date': proc.get('proc_performed_date_time', 'Unknown'),
                    'proc_code_text': proc.get('proc_code_text', 'Unknown')
                },
                context={}
            )
            extraction_prompts.append({
                'source_type': 'operative_report',
                'source_id': proc.get('procedure_fhir_id'),
                'extraction_type': 'extent_of_resection',
                'prompt_length': len(prompt),
                'prompt': prompt
            })

        print(f"  ✅ Generated {len([p for p in extraction_prompts if p['extraction_type'] == 'extent_of_resection'])} EOR prompts")
        print()

    # Validate disease state from progress notes
    if progress_notes:
        print(f"Generating {min(len(progress_notes), 5)} disease state validation prompts...")
        for note in progress_notes[:5]:  # First 5 for demo
            # In production, would fetch actual note text
            prompt = build_progress_note_disease_state_prompt(
                progress_note={
                    'note_text': f"Type: {note.get('dr_type_text', '')}. Title: {note.get('content_title', '')}",
                    'dr_date': note.get('dr_date', 'Unknown'),
                    'dr_type_text': note.get('dr_type_text', 'Unknown')
                },
                context={}
            )
            extraction_prompts.append({
                'source_type': 'progress_note',
                'source_id': note.get('document_reference_id'),
                'extraction_type': 'clinical_disease_status',
                'prompt_length': len(prompt),
                'prompt': prompt
            })

        print(f"  ✅ Generated {len([p for p in extraction_prompts if p['extraction_type'] == 'clinical_disease_status'])} disease state prompts")
        print()

    print(f"TOTAL EXTRACTION PROMPTS: {len(extraction_prompts)}")
    print()

    # =========================================================================
    # PHASE 4: SIMULATE AGENT 2 RESPONSES
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 4: AGENT 2 EXTRACTION RESPONSES (SIMULATED)")
    print("="*80 + "\n")

    print("In production, Agent 1 would:")
    print("  1. Send each prompt to MedGemma via Ollama")
    print("  2. Receive structured JSON responses")
    print("  3. Store extractions with confidence scores")
    print()

    # Simulate Agent 2 responses based on existing extraction results
    agent2_responses = {
        'tumor_status_extractions': [],
        'eor_extractions': [],
        'disease_state_validations': []
    }

    # Try to load existing imaging extraction results
    try:
        existing_results_path = Path("data/imaging_extraction_20251019_225055.json")
        if existing_results_path.exists():
            with open(existing_results_path, 'r') as f:
                existing_data = json.load(f)

            print(f"✅ Loaded {len(existing_data.get('extractions', []))} existing tumor_status extractions")

            # Filter to this patient
            patient_extractions = [
                e for e in existing_data.get('extractions', [])
                if e.get('patient_id') == patient_id
            ]

            print(f"✅ Found {len(patient_extractions)} extractions for patient {patient_id}")
            agent2_responses['tumor_status_extractions'] = patient_extractions
            print()
    except Exception as e:
        print(f"⚠️  Could not load existing results: {e}")
        print()

    # Simulate EOR extractions from procedures
    if procedures:
        print(f"Simulating EOR extractions from {len(procedures)} operative reports...")
        for proc in procedures:
            # Simulate Agent 2 response
            agent2_responses['eor_extractions'].append({
                'procedure_id': proc.get('procedure_fhir_id'),
                'procedure_date': proc.get('proc_performed_date_time'),
                'extent_of_resection': 'Unknown',  # Would come from actual note text
                'confidence': 0.0,
                'note': 'Simulated - requires actual operative note text'
            })
        print(f"  ✅ Simulated {len(agent2_responses['eor_extractions'])} EOR extractions")
        print()

    # =========================================================================
    # PHASE 5: AGENT 1 EOR ADJUDICATION
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 5: AGENT 1 PERFORMS EOR ADJUDICATION")
    print("="*80 + "\n")

    if procedures and agent2_responses['eor_extractions']:
        print("Agent 1 would adjudicate EOR from:")
        print("  - Operative report (gold standard)")
        print("  - Post-operative imaging (if available)")
        print()

        for i, proc in enumerate(procedures):
            print(f"Procedure {i+1}: {proc.get('proc_performed_date_time')}")
            print(f"  Type: {proc.get('proc_code_text')}")
            print(f"  Surgery Type: {proc.get('surgery_type')}")
            print(f"  Body Site: {proc.get('pbs_body_site_text')}")
            print()

            # In production: Agent 1 would create EORSource objects and adjudicate
            # For now, just show the framework
            print(f"  Agent 1 adjudication would:")
            print(f"    1. Collect EOR from operative note (Agent 2 extraction)")
            print(f"    2. Collect EOR from post-op imaging within 72 hours")
            print(f"    3. Apply source hierarchy (operative > imaging)")
            print(f"    4. Generate EORAdjudication with final EOR")
            print()
    else:
        print("⚠️  No procedures found for EOR adjudication")
        print()

    # =========================================================================
    # PHASE 6: AGENT 1 EVENT TYPE CLASSIFICATION
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 6: AGENT 1 CLASSIFIES EVENT TYPES")
    print("="*80 + "\n")

    if agent2_responses['tumor_status_extractions']:
        print("Agent 1 analyzes surgical history and tumor progression...")
        print()

        print(f"Total tumor events: {len(agent2_responses['tumor_status_extractions'])}")
        print(f"Surgical procedures: {len(procedures)}")
        print()

        print("Classification logic:")
        print("  - First event → Initial CNS Tumor")
        print("  - Growth after GTR → Recurrence")
        print("  - Growth after Partial → Progressive")
        print("  - New location → Second Malignancy")
        print()

        # Show first few events
        for i, event in enumerate(agent2_responses['tumor_status_extractions'][:5]):
            print(f"Event {i+1}: {event.get('event_date', 'Unknown')}")
            print(f"  Tumor Status: {event.get('tumor_status', 'Unknown')}")
            print(f"  Confidence: {event.get('confidence', 0.0)}")
            if i == 0:
                print(f"  → Classification: Initial CNS Tumor (first event)")
            print()

    # =========================================================================
    # PHASE 7: GENERATE PATIENT QA REPORT
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 7: AGENT 1 GENERATES PATIENT QA REPORT")
    print("="*80 + "\n")

    qa_report = {
        'patient_id': patient_id,
        'test_date': datetime.now().isoformat(),
        'workflow': 'end_to_end_test',
        'data_sources': {
            'imaging_text_reports': len(imaging_reports),
            'imaging_pdfs': len(imaging_pdfs),
            'surgical_procedures': len(procedures),
            'progress_notes_raw': len(progress_notes_raw),
            'progress_notes_filtered': len(progress_notes)
        },
        'extraction_prompts_generated': {
            'tumor_status': len([p for p in extraction_prompts if p['extraction_type'] == 'tumor_status']),
            'extent_of_resection': len([p for p in extraction_prompts if p['extraction_type'] == 'extent_of_resection']),
            'clinical_disease_status': len([p for p in extraction_prompts if p['extraction_type'] == 'clinical_disease_status']),
            'total': len(extraction_prompts)
        },
        'agent2_responses': {
            'tumor_status_extractions': len(agent2_responses['tumor_status_extractions']),
            'eor_extractions': len(agent2_responses['eor_extractions']),
            'disease_state_validations': len(agent2_responses['disease_state_validations'])
        },
        'progress_note_filtering': stats
    }

    # Save report
    output_dir = Path("data/qa_reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / f"{patient_id}_end_to_end_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, 'w') as f:
        json.dump(qa_report, f, indent=2)

    print(f"✅ Patient QA report saved: {report_path}")
    print()

    print("QA REPORT SUMMARY:")
    print("-" * 80)
    print(json.dumps(qa_report, indent=2))
    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*80)
    print("END-TO-END WORKFLOW TEST COMPLETE")
    print("="*80 + "\n")

    print("✅ COMPLETED PHASES:")
    print(f"  1. Queried all data sources ({sum(qa_report['data_sources'].values())} total records)")
    print(f"  2. Filtered progress notes ({qa_report['progress_note_filtering']['oncology_percentage']}% oncology-specific)")
    print(f"  3. Generated {qa_report['extraction_prompts_generated']['total']} extraction prompts for Agent 2")
    print(f"  4. Simulated Agent 2 responses ({len(agent2_responses['tumor_status_extractions'])} tumor_status)")
    print(f"  5. Demonstrated EOR adjudication framework")
    print(f"  6. Demonstrated event type classification framework")
    print(f"  7. Generated patient QA report")
    print()

    print("📝 NEXT STEPS FOR FULL PRODUCTION:")
    print("  1. Connect to MedGemma via Ollama")
    print("  2. Fetch actual operative note text from v_binary_files")
    print("  3. Fetch actual progress note text from v_binary_files")
    print("  4. Send prompts to Agent 2 and parse JSON responses")
    print("  5. Perform actual EOR adjudication with multiple sources")
    print("  6. Classify all event types based on timeline")
    print("  7. Resolve all temporal inconsistencies")
    print()


if __name__ == "__main__":
    main()
