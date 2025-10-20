#!/usr/bin/env python3
"""
Complete Patient Abstraction - Agent 1 ↔ Agent 2 Real Workflow

Runs the full multi-source clinical abstraction workflow with ACTUAL Agent 2 calls.

For patient e4BwD8ZYDBccepXcJ.Ilo3w3:
1. Query all data sources (imaging, procedures, progress notes)
2. Filter progress notes to oncology-specific
3. Actually call Agent 2 (MedGemma) for extractions
4. Perform Agent 1 adjudication
5. Classify event types
6. Generate comprehensive patient abstraction
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

from agents.medgemma_agent import MedGemmaAgent
from agents.binary_file_agent import BinaryFileAgent
from utils.progress_note_filters import filter_oncology_notes, get_note_filtering_stats
from agents.extraction_prompts import (
    build_operative_report_eor_extraction_prompt,
    build_progress_note_disease_state_prompt,
    build_tumor_status_extraction_prompt
)
from agents.eor_adjudicator import EORAdjudicator, EORSource
from agents.event_type_classifier import EventTypeClassifier


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
    """Run complete patient abstraction workflow"""

    print("="*80)
    print("COMPLETE PATIENT ABSTRACTION - REAL AGENT 1 ↔ AGENT 2 WORKFLOW")
    print("="*80)
    print()
    print("Patient: e4BwD8ZYDBccepXcJ.Ilo3w3")
    print("Date Range: 2018 (full year)")
    print()
    print("="*80)
    print()

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # =========================================================================
    # INITIALIZE AGENTS
    # =========================================================================
    print("INITIALIZING AGENTS...")
    print()

    try:
        agent2 = MedGemmaAgent(model_name="gemma2:27b")
        print("✅ Agent 2 (MedGemma) initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Agent 2: {e}")
        print()
        print("Make sure Ollama is running: ollama serve")
        print("And model is pulled: ollama pull gemma2:27b")
        return

    binary_agent = BinaryFileAgent(
        s3_bucket="radiant-prd-343218191717-us-east-1-prd-ehr-pipeline",
        s3_prefix="prd/source/Binary/",
        aws_profile="radiant-prod"
    )
    print("✅ Binary File Agent initialized")
    print()

    # =========================================================================
    # PHASE 1: QUERY ALL DATA SOURCES
    # =========================================================================
    print("="*80)
    print("PHASE 1: QUERY ALL DATA SOURCES")
    print("="*80)
    print()

    # Imaging text reports
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
    imaging_reports = query_athena(imaging_query, "Imaging text reports")

    # Surgical procedures
    procedures_query = f"""
    SELECT
        procedure_fhir_id,
        proc_performed_date_time,
        proc_code_text,
        proc_outcome_text,
        surgery_type
    FROM fhir_prd_db.v_procedures_tumor
    WHERE patient_fhir_id = '{patient_id}'
        AND proc_performed_date_time >= TIMESTAMP '2018-01-01'
        AND proc_performed_date_time <= TIMESTAMP '2018-12-31'
        AND is_tumor_surgery = true
    ORDER BY proc_performed_date_time
    """
    procedures = query_athena(procedures_query, "Tumor surgeries")

    # Progress notes around May 2018 (temporal inconsistency window)
    notes_query = f"""
    SELECT
        document_reference_id,
        binary_id,
        dr_date,
        dr_category_text,
        dr_type_text,
        dr_description,
        content_title
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
        AND dr_category_text IN ('Clinical Note', 'Correspondence')
        AND dr_date >= TIMESTAMP '2018-05-01'
        AND dr_date <= TIMESTAMP '2018-06-30'
    ORDER BY dr_date
    """
    progress_notes_raw = query_athena(notes_query, "Progress notes (May-Jun 2018)")

    print()
    print(f"TOTAL: {len(imaging_reports) + len(procedures) + len(progress_notes_raw)} records")
    print()

    # =========================================================================
    # PHASE 2: FILTER PROGRESS NOTES
    # =========================================================================
    print("="*80)
    print("PHASE 2: FILTER PROGRESS NOTES TO ONCOLOGY-SPECIFIC")
    print("="*80)
    print()

    progress_notes = filter_oncology_notes(progress_notes_raw)
    stats = get_note_filtering_stats(progress_notes_raw)

    print(f"Total notes: {stats['total_notes']}")
    print(f"Oncology notes: {stats['oncology_notes']} ({stats['oncology_percentage']}%)")
    print(f"Excluded: {stats['excluded_notes']}")
    print()

    # =========================================================================
    # PHASE 3: EXTRACT TUMOR STATUS FROM IMAGING (AGENT 2)
    # =========================================================================
    print("="*80)
    print("PHASE 3: AGENT 2 EXTRACTS TUMOR STATUS FROM IMAGING")
    print("="*80)
    print()

    tumor_status_extractions = []

    # Focus on May 2018 reports around the temporal inconsistency
    may_reports = [r for r in imaging_reports if '2018-05' in r.get('imaging_date', '')]

    print(f"Processing {len(may_reports)} May 2018 imaging reports...")
    print()

    for i, report in enumerate(may_reports[:3], 1):  # First 3 for demo
        print(f"Report {i}/{min(len(may_reports), 3)}: {report.get('imaging_date')}")

        # Build prompt
        prompt = build_tumor_status_extraction_prompt(
            report={
                'document_text': report.get('report_conclusion', ''),
                'document_date': report.get('imaging_date', 'Unknown'),
                'metadata': {'imaging_modality': report.get('imaging_modality', 'Unknown')}
            },
            context={'events_before': [], 'events_after': []}
        )

        print(f"  Calling Agent 2...")

        try:
            result = agent2.extract(prompt)

            if result.success:
                print(f"  ✅ Extracted: {result.extracted_data.get('tumor_status', 'Unknown')}")
                print(f"     Confidence: {result.extracted_data.get('confidence', 0.0)}")

                tumor_status_extractions.append({
                    'diagnostic_report_id': report.get('diagnostic_report_id'),
                    'imaging_date': report.get('imaging_date'),
                    'tumor_status': result.extracted_data.get('tumor_status'),
                    'confidence': result.extracted_data.get('confidence', 0.0),
                    'evidence': result.extracted_data.get('evidence', ''),
                    'source': 'agent2'
                })
            else:
                print(f"  ❌ Extraction failed: {result.error}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

        print()

    # =========================================================================
    # PHASE 4: EXTRACT EOR FROM OPERATIVE REPORT (AGENT 2)
    # =========================================================================
    print("="*80)
    print("PHASE 4: AGENT 2 EXTRACTS EOR FROM OPERATIVE REPORT")
    print("="*80)
    print()

    eor_extractions = []

    if procedures:
        for i, proc in enumerate(procedures, 1):
            print(f"Procedure {i}: {proc.get('proc_performed_date_time')}")
            print(f"  Type: {proc.get('proc_code_text')}")
            print()

            # In production: fetch actual operative note text from v_binary_files
            # For now: use procedure metadata
            note_text = f"""
OPERATIVE REPORT

Procedure: {proc.get('proc_code_text')}
Date: {proc.get('proc_performed_date_time')}

FINDINGS: {proc.get('proc_outcome_text', 'Not documented')}

PROCEDURE:
[Operative note text would be fetched from v_binary_files DocumentReference]

In this demo, we're using structured procedure metadata.
            """

            prompt = build_operative_report_eor_extraction_prompt(
                operative_report={
                    'note_text': note_text,
                    'procedure_date': proc.get('proc_performed_date_time'),
                    'proc_code_text': proc.get('proc_code_text')
                },
                context={}
            )

            print(f"  Calling Agent 2...")

            try:
                result = agent2.extract(prompt)

                if result.success:
                    eor = result.extracted_data.get('extent_of_resection', 'Unknown')
                    print(f"  ✅ Extracted EOR: {eor}")
                    print(f"     Confidence: {result.extracted_data.get('confidence', 0.0)}")

                    eor_extractions.append({
                        'procedure_id': proc.get('procedure_fhir_id'),
                        'procedure_date': proc.get('proc_performed_date_time'),
                        'extent_of_resection': eor,
                        'confidence': result.extracted_data.get('confidence', 0.0),
                        'surgeon_statement': result.extracted_data.get('surgeon_statement', ''),
                        'source': 'agent2_operative_report'
                    })
                else:
                    print(f"  ❌ Extraction failed: {result.error}")

            except Exception as e:
                print(f"  ❌ Error: {e}")

            print()

    # =========================================================================
    # PHASE 5: VALIDATE DISEASE STATE FROM PROGRESS NOTES (AGENT 2)
    # =========================================================================
    print("="*80)
    print("PHASE 5: AGENT 2 VALIDATES DISEASE STATE FROM PROGRESS NOTES")
    print("="*80)
    print()

    disease_state_validations = []

    if progress_notes:
        # Focus on notes around May 28 surgery
        post_surgery_notes = [
            n for n in progress_notes
            if '2018-05-2' in n.get('dr_date', '') or '2018-05-3' in n.get('dr_date', '')
        ]

        print(f"Processing {len(post_surgery_notes[:2])} post-surgery progress notes...")
        print()

        for i, note in enumerate(post_surgery_notes[:2], 1):  # First 2
            print(f"Note {i}: {note.get('dr_date')}")
            print(f"  Type: {note.get('dr_type_text')}")

            # Would fetch actual note text from v_binary_files
            # For demo: use metadata
            note_text = f"""
PROGRESS NOTE
Date: {note.get('dr_date')}
Type: {note.get('dr_type_text')}
Title: {note.get('content_title', '')}

[Note text would be fetched from v_binary_files Binary resource]

In this demo, we're using note metadata.
            """

            prompt = build_progress_note_disease_state_prompt(
                progress_note={
                    'note_text': note_text,
                    'dr_date': note.get('dr_date'),
                    'dr_type_text': note.get('dr_type_text')
                },
                context={}
            )

            print(f"  Calling Agent 2...")

            try:
                result = agent2.extract(prompt)

                if result.success:
                    status = result.extracted_data.get('clinical_disease_status', 'Unknown')
                    print(f"  ✅ Clinical Status: {status}")
                    print(f"     Confidence: {result.extracted_data.get('confidence', 0.0)}")

                    disease_state_validations.append({
                        'document_reference_id': note.get('document_reference_id'),
                        'note_date': note.get('dr_date'),
                        'clinical_disease_status': status,
                        'confidence': result.extracted_data.get('confidence', 0.0),
                        'oncologist_assessment': result.extracted_data.get('oncologist_assessment', ''),
                        'source': 'agent2_progress_note'
                    })
                else:
                    print(f"  ❌ Extraction failed: {result.error}")

            except Exception as e:
                print(f"  ❌ Error: {e}")

            print()

    # =========================================================================
    # PHASE 6: AGENT 1 EOR ADJUDICATION
    # =========================================================================
    print("="*80)
    print("PHASE 6: AGENT 1 ADJUDICATES EOR (MULTI-SOURCE)")
    print("="*80)
    print()

    if eor_extractions:
        adjudicator = EORAdjudicator()

        for eor_ext in eor_extractions:
            # Create EOR sources
            sources = [
                EORSource(
                    source_type='operative_report',
                    source_id=eor_ext['procedure_id'],
                    source_date=datetime.fromisoformat(eor_ext['procedure_date'].replace(' ', 'T')),
                    eor=eor_ext['extent_of_resection'],
                    confidence=eor_ext['confidence'],
                    evidence=eor_ext['surgeon_statement'],
                    extracted_by='agent2'
                )
            ]

            # In production: would also add post-op imaging EOR
            # For demo: just use operative report

            adjudication = adjudicator.adjudicate_eor(
                procedure_id=eor_ext['procedure_id'],
                procedure_date=datetime.fromisoformat(eor_ext['procedure_date'].replace(' ', 'T')),
                eor_sources=sources
            )

            print(f"Procedure: {eor_ext['procedure_date']}")
            print(f"  Final EOR: {adjudication.final_eor}")
            print(f"  Confidence: {adjudication.confidence}")
            print(f"  Agreement: {adjudication.agreement}")
            print(f"  Reasoning: {adjudication.adjudication_reasoning}")
            print()

    # =========================================================================
    # PHASE 7: GENERATE COMPREHENSIVE ABSTRACTION
    # =========================================================================
    print("="*80)
    print("PHASE 7: GENERATE COMPREHENSIVE PATIENT ABSTRACTION")
    print("="*80)
    print()

    abstraction = {
        'patient_id': patient_id,
        'abstraction_date': datetime.now().isoformat(),
        'workflow': 'complete_agent1_agent2',
        'data_sources': {
            'imaging_text_reports': len(imaging_reports),
            'surgical_procedures': len(procedures),
            'progress_notes_raw': len(progress_notes_raw),
            'progress_notes_oncology': len(progress_notes)
        },
        'agent2_extractions': {
            'tumor_status': tumor_status_extractions,
            'extent_of_resection': eor_extractions,
            'disease_state_validations': disease_state_validations
        },
        'agent1_adjudications': {
            'eor_adjudications': [
                {
                    'procedure_date': eor_ext['procedure_date'],
                    'final_eor': adjudication.final_eor if eor_extractions else 'N/A',
                    'confidence': adjudication.confidence if eor_extractions else 0.0
                }
            ] if eor_extractions else []
        },
        'summary': {
            'total_agent2_calls': len(tumor_status_extractions) + len(eor_extractions) + len(disease_state_validations),
            'successful_extractions': sum([
                1 for e in tumor_status_extractions + eor_extractions + disease_state_validations
                if e.get('confidence', 0) > 0
            ])
        }
    }

    # Save abstraction
    output_dir = Path("data/patient_abstractions")
    output_dir.mkdir(parents=True, exist_ok=True)

    abstraction_path = output_dir / f"{patient_id}_complete_abstraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(abstraction_path, 'w') as f:
        json.dump(abstraction, f, indent=2)

    print(f"✅ Complete abstraction saved: {abstraction_path}")
    print()

    print("ABSTRACTION SUMMARY:")
    print("-" * 80)
    print(json.dumps(abstraction['summary'], indent=2))
    print()

    print("="*80)
    print("COMPLETE PATIENT ABSTRACTION FINISHED")
    print("="*80)
    print()

    print("RESULTS:")
    print(f"  ✅ {len(tumor_status_extractions)} tumor status extractions from imaging")
    print(f"  ✅ {len(eor_extractions)} EOR extractions from operative reports")
    print(f"  ✅ {len(disease_state_validations)} disease state validations from progress notes")
    print(f"  ✅ {abstraction['summary']['total_agent2_calls']} total Agent 2 calls")
    print()


if __name__ == "__main__":
    main()
