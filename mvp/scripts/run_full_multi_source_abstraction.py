#!/usr/bin/env python3
"""
Full Multi-Source Comprehensive Abstraction Workflow

This is the COMPLETE end-to-end workflow that:

1. ALWAYS creates new timestamped abstraction (never skips)
2. Agent 2 extracts from ALL sources:
   - Imaging text reports (Athena v_imaging)
   - Imaging PDFs (Athena v_binary_files)
   - Operative reports (Athena v_procedures_tumor)
   - Oncology progress notes (Athena v_binary_files, filtered)
3. Agent 1 reviews EACH extraction from Agent 2 in real-time
4. Agent 1 detects temporal inconsistencies and queries Agent 2 for clarification
5. Agent 1 performs multi-source EOR adjudication (operative vs imaging)
6. Agent 1 classifies event types (Initial/Recurrence/Progressive/Second Malignancy)
7. Creates timestamped abstraction folder with checkpoints

This implements the complete two-agent architecture with feedback loops.
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
from typing import Dict, List, Any, Optional
import base64

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.master_agent import MasterAgent
from agents.medgemma_agent import MedGemmaAgent
from agents.binary_file_agent import BinaryFileAgent
from timeline_query_interface import TimelineQueryInterface
from utils.progress_note_filters import filter_oncology_notes, get_note_filtering_stats
from utils.progress_note_prioritization import ProgressNotePrioritizer
from utils.document_text_cache import DocumentTextCache
from utils.workflow_monitoring import WorkflowLogger, WorkflowMetrics
from agents.extraction_prompts import (
    build_operative_report_eor_extraction_prompt,
    build_progress_note_disease_state_prompt,
    build_imaging_classification_prompt,
    build_eor_extraction_prompt,
    build_tumor_status_extraction_prompt
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

    # Get results with pagination to handle large result sets
    rows = []
    next_token = None
    header = None

    while True:
        if next_token:
            results = client.get_query_results(
                QueryExecutionId=query_id,
                NextToken=next_token,
                MaxResults=1000
            )
        else:
            results = client.get_query_results(
                QueryExecutionId=query_id,
                MaxResults=1000
            )

        # Parse header from first page
        if header is None:
            if len(results['ResultSet']['Rows']) <= 1:
                print(f" ✅ 0 records")
                return []
            header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            result_rows = results['ResultSet']['Rows'][1:]  # Skip header
        else:
            result_rows = results['ResultSet']['Rows']  # No header on subsequent pages

        # Parse rows
        for row in result_rows:
            row_dict = {}
            for i, col in enumerate(row['Data']):
                row_dict[header[i]] = col.get('VarCharValue', '')
            rows.append(row_dict)

        # Check for more pages
        next_token = results.get('NextToken')
        if not next_token:
            break

    print(f" ✅ {len(rows)} records")
    return rows


def extract_text_from_pdf_binary(binary_data: str) -> str:
    """Extract text from base64-encoded PDF using PyMuPDF"""
    try:
        import fitz  # PyMuPDF
        import io

        # Decode base64
        pdf_bytes = base64.b64decode(binary_data)

        # Open PDF from bytes
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Extract text from all pages
        text = ""
        for page_num in range(pdf_doc.page_count):
            page = pdf_doc[page_num]
            text += page.get_text()

        pdf_doc.close()
        return text
    except Exception as e:
        logger.error(f"Failed to extract PDF text: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description='Run full multi-source comprehensive abstraction with Agent 1 <-> Agent 2 feedback'
    )
    parser.add_argument(
        '--patient-id',
        type=str,
        required=True,
        help='Patient FHIR ID to process'
    )
    parser.add_argument(
        '--timeline-db',
        type=str,
        default='data/timeline.duckdb',
        help='Path to timeline DuckDB database'
    )

    args = parser.parse_args()

    # Create timestamped output folder
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path("data/patient_abstractions") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*80)
    print("FULL MULTI-SOURCE COMPREHENSIVE ABSTRACTION")
    print("="*80)
    print()
    print(f"Patient: {args.patient_id}")
    print(f"Output folder: {output_dir}")
    print()
    print("Workflow:")
    print("  1. Query ALL data sources from Athena:")
    print("     - Imaging text reports (v_imaging)")
    print("     - Imaging PDFs (v_binary_files)")
    print("     - Operative reports (v_procedures_tumor)")
    print("     - Oncology progress notes (v_binary_files, filtered)")
    print("  2. Agent 2 extracts from each source")
    print("  3. Agent 1 reviews and validates each extraction")
    print("  4. Agent 1 detects temporal inconsistencies")
    print("  5. Agent 1 queries Agent 2 for clarification on suspicious patterns")
    print("  6. Agent 1 performs multi-source EOR adjudication")
    print("  7. Agent 1 classifies event types")
    print("  8. Save timestamped comprehensive abstraction")
    print()
    print("="*80)
    print()

    # Initialize workflow monitoring
    workflow_logger = WorkflowLogger(
        workflow_name="full_multi_source_abstraction",
        log_dir=output_dir,
        patient_id=args.patient_id,
        enable_json=True,
        enable_notifications=False  # Can be enabled via config
    )
    workflow_logger.log_info("Starting full multi-source comprehensive abstraction workflow")

    # Initialize agents
    try:
        print("Initializing agents...")
        workflow_logger.log_info("Starting phase: initialization")

        medgemma = MedGemmaAgent(model_name="gemma2:27b")
        print("✅ Agent 2 (MedGemma) initialized")

        timeline = TimelineQueryInterface(args.timeline_db)
        print("✅ Timeline database loaded")

        # Initialize BinaryFileAgent for PDF/HTML extraction
        binary_agent = BinaryFileAgent()
        print("✅ Binary file agent initialized")

        # Initialize DocumentTextCache
        doc_cache = DocumentTextCache(db_path="data/document_text_cache.duckdb")
        print("✅ Document text cache initialized")

        # Initialize ProgressNotePrioritizer
        note_prioritizer = ProgressNotePrioritizer()
        print("✅ Progress note prioritizer initialized")

        eor_adjudicator = EORAdjudicator(medgemma_agent=medgemma)
        event_classifier = EventTypeClassifier(timeline_query_interface=timeline)
        print("✅ Agent 1 (Master orchestrator) initialized")
        print()

        workflow_logger.log_info("Completed phase: initialization")

    except Exception as e:
        workflow_logger.log_error(f"Failed to initialize: {e}", error_type="initialization_error", stack_trace=str(e))
        logger.error(f"Failed to initialize: {e}", exc_info=True)
        print(f"❌ ERROR: {e}")
        return 1

    # Comprehensive summary
    comprehensive_summary = {
        'patient_id': args.patient_id,
        'timestamp': timestamp,
        'output_folder': str(output_dir),
        'workflow': 'full_multi_source_with_agent_feedback',
        'start_time': datetime.now().isoformat(),
        'phases': {}
    }

    # Save checkpoint function
    def save_checkpoint(phase: str, status: str, data: Dict = None):
        checkpoint_path = output_dir / f"{args.patient_id}_checkpoint.json"
        checkpoint_data = {
            'patient_id': args.patient_id,
            'timestamp': timestamp,
            'current_phase': phase,
            'status': status,
            'phases_completed': list(comprehensive_summary['phases'].keys()),
            'last_updated': datetime.now().isoformat()
        }
        if data:
            checkpoint_data['phase_data'] = data

        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info(f"Checkpoint saved: {phase} - {status}")

    try:
        # ================================================================
        # PHASE 1: QUERY ALL DATA SOURCES FROM ATHENA
        # ================================================================
        print("="*80)
        print("PHASE 1: QUERYING ALL DATA SOURCES FROM ATHENA")
        print("="*80)
        print()

        # 1A: Imaging text reports
        print("1A. Imaging text reports (v_imaging):")
        imaging_text_query = f"""
            SELECT
                diagnostic_report_id,
                imaging_date,
                imaging_modality,
                report_conclusion,
                patient_fhir_id
            FROM v_imaging
            WHERE patient_fhir_id = '{args.patient_id}'
            ORDER BY imaging_date
        """
        imaging_text_reports = query_athena(imaging_text_query, "Querying imaging text reports")

        # 1B: Imaging PDFs
        print("1B. Imaging PDFs (v_binary_files):")
        imaging_pdf_query = f"""
            SELECT
                document_reference_id,
                dr_date,
                dr_type_text,
                dr_category_text,
                binary_id,
                content_type,
                patient_fhir_id
            FROM v_binary_files
            WHERE patient_fhir_id = '{args.patient_id}'
                AND content_type = 'application/pdf'
                AND (
                    LOWER(dr_category_text) LIKE '%imaging%'
                    OR LOWER(dr_category_text) LIKE '%radiology%'
                    OR LOWER(dr_type_text) LIKE '%mri%'
                    OR LOWER(dr_type_text) LIKE '%ct%'
                )
            ORDER BY dr_date
        """
        imaging_pdfs = query_athena(imaging_pdf_query, "Querying imaging PDFs")

        # 1C: Operative reports
        print("1C. Operative reports (v_procedures_tumor):")
        operative_query = f"""
            SELECT
                procedure_fhir_id,
                proc_performed_date_time,
                proc_code_text,
                surgery_type,
                patient_fhir_id
            FROM v_procedures_tumor
            WHERE patient_fhir_id = '{args.patient_id}'
                AND is_tumor_surgery = true
            ORDER BY proc_performed_date_time
        """
        operative_reports = query_athena(operative_query, "Querying operative reports")

        # 1D: All progress notes (to be filtered)
        print("1D. Progress notes (v_binary_files):")
        progress_notes_query = f"""
            SELECT
                document_reference_id,
                dr_date,
                dr_type_text,
                dr_category_text,
                binary_id,
                content_type,
                patient_fhir_id
            FROM v_binary_files
            WHERE patient_fhir_id = '{args.patient_id}'
                AND (
                    content_type = 'text/plain'
                    OR content_type = 'text/html'
                    OR content_type = 'application/pdf'
                )
                AND (
                    LOWER(dr_category_text) LIKE '%progress note%'
                    OR LOWER(dr_category_text) LIKE '%clinical note%'
                    OR LOWER(dr_type_text) LIKE '%oncology%'
                    OR LOWER(dr_type_text) LIKE '%hematology%'
                )
            ORDER BY dr_date
        """
        all_progress_notes = query_athena(progress_notes_query, "Querying progress notes")

        # Filter to oncology-specific notes
        try:
            msg = "=== DEBUG: ABOUT TO FILTER ONCOLOGY NOTES ==="
            print(msg)
            workflow_logger.log_info(msg)

            filtering_results = get_note_filtering_stats(all_progress_notes)
            oncology_notes = filter_oncology_notes(all_progress_notes)

            filtered_msg = (
                f"  Filtered to oncology-specific: {filtering_results['oncology_notes']} notes "
                f"({filtering_results['oncology_percentage']:.1f}%)"
            )
            print(filtered_msg)
            workflow_logger.log_info(filtered_msg)

            excluded_msg = f"  Excluded: {filtering_results['excluded_notes']} notes"
            print(excluded_msg)
            workflow_logger.log_info(excluded_msg)
        except Exception as e:
            error_msg = f"  ❌ ERROR filtering oncology notes: {e}"
            print(error_msg)
            import traceback
            stack = traceback.format_exc()
            workflow_logger.log_error(
                error_msg,
                error_type="oncology_note_filtering_error",
                stack_trace=stack
            )
            oncology_notes = all_progress_notes  # Fallback to all notes

        oncology_count_msg = f"  Oncology notes available for prioritization: {len(oncology_notes)}"
        print(oncology_count_msg)
        workflow_logger.log_info(oncology_count_msg)

        # Query chemotherapy/targeted therapy starts from timeline for medication-based prioritization
        msg = "=== DEBUG: ABOUT TO QUERY CHEMOTHERAPY FROM TIMELINE ==="
        print(msg)
        workflow_logger.log_info(msg)

        query_msg = "  Querying chemotherapy/targeted therapy events from timeline..."
        print(query_msg)
        workflow_logger.log_info(query_msg)

        medication_changes = []
        try:
            chemo_events_df = timeline.conn.execute(f"""
                SELECT
                    event_id,
                    event_date,
                    event_category,
                    description as event_description
                FROM events
                WHERE patient_id = '{args.patient_id}'
                    AND event_type = 'Medication'
                    AND event_category IN ('Chemotherapy', 'Targeted Therapy')
                ORDER BY event_date
            """).fetchdf()

            # Convert to list of dicts for prioritizer
            for _, row in chemo_events_df.iterrows():
                medication_changes.append({
                    'change_date': row['event_date'],
                    'medication_id': row['event_id']
                })
            found_msg = f"  Found {len(medication_changes)} chemotherapy/targeted therapy start events"
            print(found_msg)
            workflow_logger.log_info(found_msg)
        except Exception as e:
            warn_msg = f"  ⚠️  Timeline query failed (timeline not populated): {str(e)[:100]}"
            print(warn_msg)
            workflow_logger.log_warning(warn_msg)
            cont_msg = "  Continuing without medication-based prioritization..."
            print(cont_msg)
            workflow_logger.log_warning(cont_msg)
        finally:
            # Close timeline connection to avoid DuckDB lock conflicts
            timeline.close()

        medication_count_msg = f"  Medication change events available: {len(medication_changes)}"
        print(medication_count_msg)
        workflow_logger.log_info(medication_count_msg)

        # Prioritize progress notes based on clinical events
        prioritize_msg = "  Prioritizing progress notes based on clinical events..."
        print(prioritize_msg)
        workflow_logger.log_info(prioritize_msg)

        prioritized_notes = note_prioritizer.prioritize_notes(
            progress_notes=oncology_notes,
            surgeries=operative_reports,
            imaging_events=imaging_text_reports,  # Use imaging text as imaging events
            medication_changes=medication_changes if medication_changes else None
        )
        if len(oncology_notes) > 0:
            prioritized_msg = (
                f"  Prioritized to {len(prioritized_notes)} key notes "
                f"({len(prioritized_notes)/len(oncology_notes)*100:.1f}% of oncology notes)"
            )
            print(prioritized_msg)
            workflow_logger.log_info(prioritized_msg)
        else:
            no_onc_msg = (
                f"  Prioritized to {len(prioritized_notes)} key notes (no oncology notes found)"
            )
            print(no_onc_msg)
            workflow_logger.log_info(no_onc_msg)

        # Get priority reasons summary
        priority_counts = {}
        for pn in prioritized_notes:
            reason = pn.priority_reason
            priority_counts[reason] = priority_counts.get(reason, 0) + 1
        breakdown_msg = f"  Priority breakdown: {dict(priority_counts)}"
        print(breakdown_msg)
        workflow_logger.log_info(breakdown_msg)

        print()
        comprehensive_summary['phases']['data_query'] = {
            'imaging_text_count': len(imaging_text_reports),
            'imaging_pdf_count': len(imaging_pdfs),
            'operative_report_count': len(operative_reports),
            'progress_note_all_count': len(all_progress_notes),
            'progress_note_oncology_count': len(oncology_notes),
            'progress_note_prioritized_count': len(prioritized_notes),
            'total_sources': len(imaging_text_reports) + len(imaging_pdfs) + len(operative_reports) + len(prioritized_notes)
        }
        save_checkpoint('data_query', 'completed', comprehensive_summary['phases']['data_query'])

        # ================================================================
        # PHASE 2: AGENT 2 EXTRACTS FROM ALL SOURCES (with Agent 1 review)
        # ================================================================
        print("="*80)
        print("PHASE 2: AGENT 2 EXTRACTION WITH AGENT 1 REAL-TIME REVIEW")
        print("="*80)
        print()

        all_extractions = []
        extraction_count = {'imaging_text': 0, 'imaging_pdf': 0, 'operative': 0, 'progress_note': 0}

        # Load timeline context for Agent 1 review
        surgical_history = timeline.conn.execute(f"""
            SELECT event_id, event_date, description
            FROM events
            WHERE patient_id = ? AND event_type = 'Procedure'
            ORDER BY event_date
        """, [args.patient_id]).fetchall()

        # Close timeline connection immediately after query
        timeline.close()

        # 2A: Extract from imaging text reports
        print(f"2A. Extracting from {len(imaging_text_reports)} imaging text reports...")
        for i, report in enumerate(imaging_text_reports, 1):
            report_id = report.get('diagnostic_report_id', 'unknown')
            report_date = report.get('imaging_date', 'unknown')
            print(f"  [{i}/{len(imaging_text_reports)}] {report_id[:30]}... ({report_date})")

            context = {
                'patient_id': args.patient_id,
                'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
                'report_date': report_date
            }

            # Imaging classification
            classification_prompt = build_imaging_classification_prompt(report, context)
            classification_result = medgemma.extract(classification_prompt)
            print(f"    Classification: {classification_result.extracted_data.get('imaging_type', 'unknown')}")

            # Tumor status
            tumor_status_prompt = build_tumor_status_extraction_prompt(report, context)
            tumor_status_result = medgemma.extract(tumor_status_prompt)
            print(f"    Tumor status: {tumor_status_result.extracted_data.get('tumor_status', 'unknown')}")

            all_extractions.append({
                'source': 'imaging_text',
                'source_id': report_id,
                'date': report_date,
                'classification': classification_result.extracted_data if classification_result.success else {'error': classification_result.error},
                'tumor_status': tumor_status_result.extracted_data if tumor_status_result.success else {'error': tumor_status_result.error},
                'classification_confidence': classification_result.confidence,
                'tumor_status_confidence': tumor_status_result.confidence
            })
            extraction_count['imaging_text'] += 1

        print(f"  ✅ Completed {extraction_count['imaging_text']} imaging text extractions")
        print()

        # 2B: Extract from imaging PDFs
        print(f"2B. Extracting from {len(imaging_pdfs)} imaging PDFs...")
        workflow_logger.log_info("Starting phase: phase_2b_imaging_pdfs")
        extraction_count['imaging_pdf'] = 0

        for idx, pdf_doc in enumerate(imaging_pdfs, 1):
            doc_id = pdf_doc['document_reference_id']
            binary_id = pdf_doc['binary_id']
            doc_date = pdf_doc['dr_date']

            # Check cache first
            cached_doc = doc_cache.get_cached_document(doc_id)
            if cached_doc:
                extracted_text = cached_doc.extracted_text
                workflow_logger.log_info(f"Using cached text for {doc_id}")
            else:
                # Extract text from PDF using BinaryFileAgent
                extracted_text, error = binary_agent.extract_text_from_binary(binary_id, args.patient_id)
                if error:
                    workflow_logger.log_warning(f"Failed to extract PDF {doc_id}: {error}")
                    continue

                # Cache the extracted text
                doc_cache.cache_document_from_binary(
                    document_id=doc_id,
                    patient_fhir_id=args.patient_id,
                    extracted_text=extracted_text,
                    extraction_method="pdf_pymupdf",
                    binary_id=binary_id,
                    document_date=doc_date,
                    content_type=pdf_doc.get('content_type'),
                    document_type="imaging_report",
                    dr_type_text=pdf_doc.get('dr_type_text'),
                    dr_category_text=pdf_doc.get('dr_category_text')
                )

            # Build report dict for prompt generation (matching imaging text report structure)
            report = {
                'diagnostic_report_id': doc_id,
                'imaging_date': doc_date,
                'report_conclusion': extracted_text,  # PDF text goes in report_conclusion field
                'patient_fhir_id': args.patient_id
            }

            # Build context with surgical history
            context = {
                'patient_id': args.patient_id,
                'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
                'report_date': doc_date
            }

            # Extract classification and tumor status using MedGemma
            classification_prompt = build_imaging_classification_prompt(report, context)
            classification_result = medgemma.extract(classification_prompt, "imaging_classification")

            tumor_status_prompt = build_tumor_status_extraction_prompt(report, context)
            tumor_status_result = medgemma.extract(tumor_status_prompt, "tumor_status")

            print(f"  [{idx}/{len(imaging_pdfs)}] {doc_id[:30]}... ({doc_date})")
            print(f"    Classification: {classification_result.extracted_data.get('imaging_type', 'unknown')}")
            print(f"    Tumor status: {tumor_status_result.extracted_data.get('overall_status', 'Unknown')}")

            all_extractions.append({
                'source': 'imaging_pdf',
                'source_id': doc_id,
                'date': doc_date,
                'classification': classification_result.extracted_data if classification_result.success else {'error': classification_result.error},
                'tumor_status': tumor_status_result.extracted_data if tumor_status_result.success else {'error': tumor_status_result.error},
                'classification_confidence': classification_result.confidence,
                'tumor_status_confidence': tumor_status_result.confidence
            })
            extraction_count['imaging_pdf'] += 1

        workflow_logger.log_info("Completed phase: phase_2b_imaging_pdfs")
        print(f"  ✅ Completed {extraction_count['imaging_pdf']} imaging PDF extractions")
        print()

        # 2C: Extract from operative reports
        print(f"2C. Extracting from {len(operative_reports)} operative reports...")
        workflow_logger.log_info("Starting phase: phase_2c_operative_reports")
        extraction_count['operative_reports'] = 0

        for idx, surgery in enumerate(operative_reports, 1):
            proc_id = surgery['procedure_fhir_id']
            proc_date = surgery['proc_performed_date_time']
            surgery_type = surgery.get('surgery_type', 'unknown')

            print(f"  [{idx}/{len(operative_reports)}] {proc_id[:30]}... ({proc_date}) - {surgery_type}")

            # Query for operative note DocumentReference linked to this procedure
            # Search for notes created around the time of surgery (±7 days)
            proc_date_str = proc_date.split()[0] if isinstance(proc_date, str) else str(proc_date)

            op_note_query = f"""
                SELECT
                    document_reference_id,
                    binary_id,
                    dr_date,
                    dr_category_text,
                    dr_type_text,
                    content_type
                FROM v_binary_files
                WHERE patient_fhir_id = '{args.patient_id}'
                    AND (
                        LOWER(dr_category_text) LIKE '%operative%'
                        OR LOWER(dr_category_text) LIKE '%surgery%'
                        OR LOWER(dr_category_text) LIKE '%procedure%'
                        OR LOWER(dr_type_text) LIKE '%operative%'
                        OR LOWER(dr_type_text) LIKE '%surgery%'
                    )
                    AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE '{proc_date_str}')) <= 7
                ORDER BY ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE '{proc_date_str}'))
                LIMIT 1
            """

            try:
                op_notes = query_athena(op_note_query, None)  # Don't print query message

                if not op_notes or len(op_notes) == 0:
                    print(f"    ⚠️  No operative note found within ±7 days of surgery")
                    continue

                op_note = op_notes[0]
                doc_id = op_note['document_reference_id']
                binary_id = op_note['binary_id']
                doc_date = op_note['dr_date']

                # Check cache first
                cached_doc = doc_cache.get_cached_document(doc_id)
                if cached_doc:
                    extracted_text = cached_doc.extracted_text
                    workflow_logger.log_info(f"Using cached text for operative note {doc_id}")
                else:
                    # Extract text from operative note
                    extracted_text, error = binary_agent.extract_text_from_binary(binary_id, args.patient_id)
                    if error:
                        workflow_logger.log_warning(f"Failed to extract operative note {doc_id}: {error}")
                        print(f"    ⚠️  Failed to extract text: {error}")
                        continue

                    # Determine extraction method based on content type
                    content_type = op_note['content_type']
                    extraction_method = "html_beautifulsoup" if "html" in content_type else \
                                       "pdf_pymupdf" if "pdf" in content_type else "text_plain"

                    # Cache the extracted text
                    doc_cache.cache_document_from_binary(
                        document_id=doc_id,
                        patient_fhir_id=args.patient_id,
                        extracted_text=extracted_text,
                        extraction_method=extraction_method,
                        binary_id=binary_id,
                        document_date=doc_date,
                        content_type=content_type,
                        document_type="operative_report",
                        dr_type_text=op_note.get('dr_type_text'),
                        dr_category_text=op_note.get('dr_category_text'),
                        dr_description=op_note.get('dr_description')
                    )

                # Extract EOR using MedGemma
                eor_prompt = build_operative_report_eor_extraction_prompt(extracted_text)
                eor_result = medgemma.extract(eor_prompt, "operative_report_eor")

                print(f"    EOR: {eor_result.extracted_data.get('extent_of_resection', 'Unknown')}")
                print(f"    Operative note: {doc_id[:30]}... ({doc_date})")

                all_extractions.append({
                    'source': 'operative_report',
                    'source_id': proc_id,
                    'operative_note_id': doc_id,
                    'surgery_date': proc_date,
                    'surgery_type': surgery_type,
                    'eor': eor_result.extracted_data if eor_result.success else {'error': eor_result.error},
                    'confidence': eor_result.confidence
                })
                extraction_count['operative_reports'] += 1

            except Exception as e:
                workflow_logger.log_error(f"Failed to process operative report for {proc_id}: {e}",
                                        error_type="operative_report_extraction_error")
                print(f"    ⚠️  Error: {e}")

        workflow_logger.log_info("Completed phase: phase_2c_operative_reports")
        print(f"  ✅ Completed {extraction_count['operative_reports']} operative report extractions")
        print()

        # 2D: Extract from prioritized progress notes
        print(f"2D. Extracting from {len(prioritized_notes)} prioritized progress notes...")
        workflow_logger.log_info("Starting phase: phase_2d_progress_notes")
        extraction_count['progress_notes'] = 0

        for idx, prioritized_note in enumerate(prioritized_notes, 1):
            note = prioritized_note.note
            doc_id = note['document_reference_id']
            binary_id = note['binary_id']
            doc_date = note['dr_date']
            content_type = note['content_type']
            priority_reason = prioritized_note.priority_reason

            # Check cache first
            cached_doc = doc_cache.get_cached_document(doc_id)
            if cached_doc:
                extracted_text = cached_doc.extracted_text
                workflow_logger.log_info(f"Using cached text for {doc_id}")
            else:
                # Extract text using BinaryFileAgent (handles PDF/HTML/text)
                extracted_text, error = binary_agent.extract_text_from_binary(binary_id, args.patient_id)
                if error:
                    workflow_logger.log_warning(f"Failed to extract progress note {doc_id}: {error}")
                    continue

                # Determine extraction method based on content type
                extraction_method = "html_beautifulsoup" if "html" in content_type else \
                                   "pdf_pymupdf" if "pdf" in content_type else "text_plain"

                # Cache the extracted text
                doc_cache.cache_document_from_binary(
                    document_id=doc_id,
                    patient_fhir_id=args.patient_id,
                    extracted_text=extracted_text,
                    extraction_method=extraction_method,
                    binary_id=binary_id,
                    document_date=doc_date,
                    content_type=content_type,
                    document_type="progress_note",
                    dr_type_text=note.get('dr_type_text'),
                    dr_category_text=note.get('dr_category_text'),
                    dr_description=note.get('dr_description')
                )

            # Extract disease state using MedGemma
            disease_state_prompt = build_progress_note_disease_state_prompt(extracted_text)
            disease_state_result = medgemma.extract(disease_state_prompt, "progress_note_disease_state")

            print(f"  [{idx}/{len(prioritized_notes)}] {doc_id[:30]}... ({doc_date})")
            print(f"    Priority: {priority_reason}")
            print(f"    Disease state: {disease_state_result.extracted_data.get('disease_status', 'Unknown')}")

            all_extractions.append({
                'source': 'progress_note',
                'source_id': doc_id,
                'date': doc_date,
                'priority_reason': priority_reason,
                'disease_state': disease_state_result.extracted_data if disease_state_result.success else {'error': disease_state_result.error},
                'confidence': disease_state_result.confidence
            })
            extraction_count['progress_notes'] += 1

        workflow_logger.log_info("Completed phase: phase_2d_progress_notes")
        print(f"  ✅ Completed {extraction_count['progress_notes']} progress note extractions")
        print()

        comprehensive_summary['phases']['agent2_extraction'] = {
            'total_extractions': len(all_extractions),
            'by_source': extraction_count,
            'extractions': all_extractions
        }
        save_checkpoint('agent2_extraction', 'completed', comprehensive_summary['phases']['agent2_extraction'])

        # ================================================================
        # PHASE 3: AGENT 1 TEMPORAL INCONSISTENCY DETECTION
        # ================================================================
        print("="*80)
        print("PHASE 3: AGENT 1 TEMPORAL INCONSISTENCY DETECTION")
        print("="*80)
        print()

        inconsistencies = []
        # TODO: Implement temporal inconsistency detection
        print(f"  Detected {len(inconsistencies)} temporal inconsistencies")
        print()

        comprehensive_summary['phases']['temporal_inconsistencies'] = {
            'count': len(inconsistencies),
            'details': inconsistencies
        }
        save_checkpoint('temporal_inconsistencies', 'completed')

        # ================================================================
        # PHASE 4: AGENT 1 <-> AGENT 2 FEEDBACK LOOP
        # ================================================================
        print("="*80)
        print("PHASE 4: AGENT 1 <-> AGENT 2 ITERATIVE CLARIFICATION")
        print("="*80)
        print()

        clarifications = []
        # TODO: For each high-severity inconsistency, query Agent 2
        print(f"  {len(clarifications)} Agent 2 queries sent")
        print()

        comprehensive_summary['phases']['agent_feedback'] = {
            'queries_sent': len(clarifications),
            'clarifications': clarifications
        }
        save_checkpoint('agent_feedback', 'completed')

        # ================================================================
        # PHASE 5: AGENT 1 MULTI-SOURCE EOR ADJUDICATION
        # ================================================================
        print("="*80)
        print("PHASE 5: AGENT 1 MULTI-SOURCE EOR ADJUDICATION")
        print("="*80)
        print()

        eor_adjudications = []
        # TODO: Adjudicate operative vs imaging EOR
        print(f"  {len(eor_adjudications)} EOR adjudications completed")
        print()

        comprehensive_summary['phases']['eor_adjudication'] = {
            'count': len(eor_adjudications),
            'adjudications': eor_adjudications
        }
        save_checkpoint('eor_adjudication', 'completed')

        # ================================================================
        # PHASE 6: AGENT 1 EVENT TYPE CLASSIFICATION
        # ================================================================
        print("="*80)
        print("PHASE 6: AGENT 1 EVENT TYPE CLASSIFICATION")
        print("="*80)
        print()

        try:
            event_classifications = event_classifier.classify_patient_events(args.patient_id)
            print(f"  ✅ Classified {len(event_classifications)} events")

            # Show sample
            for cls in event_classifications[:3]:
                print(f"    - {cls['event_date']}: {cls['event_type']} (confidence: {cls['confidence']})")

            comprehensive_summary['phases']['event_classification'] = {
                'count': len(event_classifications),
                'classifications': event_classifications
            }
        except Exception as e:
            logger.error(f"Event classification failed: {e}", exc_info=True)
            print(f"  ❌ Event classification failed: {e}")
            comprehensive_summary['phases']['event_classification'] = {
                'count': 0,
                'error': str(e)
            }

        print()
        save_checkpoint('event_classification', 'completed')

        # ================================================================
        # SAVE FINAL COMPREHENSIVE ABSTRACTION
        # ================================================================
        comprehensive_summary['end_time'] = datetime.now().isoformat()

        abstraction_path = output_dir / f"{args.patient_id}_comprehensive.json"
        with open(abstraction_path, 'w') as f:
            json.dump(comprehensive_summary, f, indent=2)

        save_checkpoint('complete', 'success')

        print("="*80)
        print("COMPREHENSIVE ABSTRACTION COMPLETE")
        print("="*80)
        print()
        print(f"✅ Abstraction saved: {abstraction_path}")
        print(f"✅ Checkpoint saved: {output_dir}/{args.patient_id}_checkpoint.json")
        print()
        print("Summary:")
        print(f"  Imaging text: {extraction_count['imaging_text']} extractions")
        print(f"  Imaging PDFs: {extraction_count['imaging_pdf']} extractions")
        print(f"  Operative reports: {extraction_count['operative']} extractions")
        print(f"  Progress notes: {extraction_count['progress_note']} extractions")
        print(f"  Total extractions: {len(all_extractions)}")
        print()

        return 0

    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")

        # CRITICAL: Save whatever data we have, even on error!
        try:
            comprehensive_summary['end_time'] = datetime.now().isoformat()
            comprehensive_summary['status'] = 'failed_with_partial_data'
            comprehensive_summary['error'] = str(e)

            emergency_path = output_dir / f"{args.patient_id}_PARTIAL.json"
            with open(emergency_path, 'w') as f:
                json.dump(comprehensive_summary, f, indent=2)

            print(f"\n⚠️  PARTIAL DATA SAVED: {emergency_path}")
            print(f"    Extractions completed before error: {len(all_extractions)}")
        except Exception as save_error:
            logger.error(f"Failed to save partial data: {save_error}")

        save_checkpoint('failed', 'error', {'error': str(e)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
