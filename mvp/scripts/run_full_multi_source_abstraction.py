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
import subprocess

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
    build_tumor_status_extraction_prompt,
    build_tumor_location_extraction_prompt
)
from utils.brain_location_normalizer import BrainTumorLocationNormalizer
from agents.eor_adjudicator import EORAdjudicator, EORSource
from agents.event_type_classifier import EventTypeClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_and_refresh_aws_sso_token(profile_name: str = 'radiant-prod') -> bool:
    """
    Check if AWS SSO token is valid and refresh if expired.

    Args:
        profile_name: AWS profile name to check/refresh

    Returns:
        True if token is valid or successfully refreshed, False otherwise
    """
    try:
        # Try to create a session and client - this will fail if token is expired
        session = boto3.Session(profile_name=profile_name)
        sts = session.client('sts')
        sts.get_caller_identity()
        logger.info(f"AWS SSO token for profile '{profile_name}' is valid")
        return True
    except Exception as e:
        error_msg = str(e)
        if 'Token has expired' in error_msg or 'sso' in error_msg.lower():
            logger.warning(f"AWS SSO token expired. Attempting to refresh...")
            print(f"\n⚠️  AWS SSO token expired. Running 'aws sso login --profile {profile_name}'...")
            print("This will open a browser window for authentication.\n")

            try:
                # Run aws sso login command
                result = subprocess.run(
                    ['aws', 'sso', 'login', '--profile', profile_name],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout for user to complete login
                )

                if result.returncode == 0:
                    logger.info(f"AWS SSO token refreshed successfully for profile '{profile_name}'")
                    print(f"✅ AWS SSO token refreshed successfully\n")
                    return True
                else:
                    logger.error(f"Failed to refresh AWS SSO token: {result.stderr}")
                    print(f"❌ Failed to refresh AWS SSO token: {result.stderr}\n")
                    return False

            except subprocess.TimeoutExpired:
                logger.error("AWS SSO login timed out after 5 minutes")
                print("❌ AWS SSO login timed out. Please run 'aws sso login --profile radiant-prod' manually.\n")
                return False
            except FileNotFoundError:
                logger.error("AWS CLI not found. Please install AWS CLI.")
                print("❌ AWS CLI not found. Please install AWS CLI.\n")
                return False
            except Exception as refresh_error:
                logger.error(f"Error during AWS SSO refresh: {refresh_error}")
                print(f"❌ Error during AWS SSO refresh: {refresh_error}\n")
                return False
        else:
            logger.error(f"AWS session error (not SSO-related): {e}")
            raise


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

    # Check and refresh AWS SSO token if needed
    if not check_and_refresh_aws_sso_token('radiant-prod'):
        logger.error("Cannot proceed without valid AWS SSO token")
        print("\n❌ Cannot proceed without valid AWS SSO token.")
        print("Please run 'aws sso login --profile radiant-prod' manually and try again.\n")
        sys.exit(1)

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

        # Initialize BrainTumorLocationNormalizer
        location_normalizer = BrainTumorLocationNormalizer()
        print("✅ Tumor location normalizer initialized")

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
        # Sanitize patient_id for filename (replace / with _)
        safe_patient_id = args.patient_id.replace('/', '_')
        checkpoint_path = output_dir / f"{safe_patient_id}_checkpoint.json"
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

        # Strip "Patient/" prefix for Athena queries (views store IDs without prefix)
        athena_patient_id = args.patient_id.replace('Patient/', '')

        # 1A: Imaging text reports
        print("1A. Imaging text reports (v_imaging):")
        imaging_text_query = f"""
            SELECT
                diagnostic_report_id,
                imaging_date,
                imaging_modality,
                result_information as radiology_report_text,
                report_conclusion,
                patient_fhir_id
            FROM v_imaging
            WHERE patient_fhir_id = '{athena_patient_id}'
                AND result_information IS NOT NULL
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
            WHERE patient_fhir_id = '{athena_patient_id}'
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
                procedure_date,
                proc_code_text,
                surgery_type,
                patient_fhir_id
            FROM v_procedures_tumor
            WHERE patient_fhir_id = '{athena_patient_id}'
                AND is_tumor_surgery = true
            ORDER BY procedure_date
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
            WHERE patient_fhir_id = '{athena_patient_id}'
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

        # Build surgical history from Athena operative_reports (no timeline needed)
        surgical_history = [
            (op['procedure_fhir_id'], op['procedure_date'], op.get('surgery_type', 'Unknown'))
            for op in operative_reports
            if op.get('procedure_date')
        ]

        # Helper function to build timeline context for each document
        def build_timeline_context(current_date_str: str) -> Dict:
            """
            Build events_before and events_after context for a given date.
            Uses in-memory data from imaging_text_reports and surgical_history.
            """
            from datetime import datetime, timedelta

            try:
                current_date = datetime.fromisoformat(str(current_date_str).replace(' ', 'T'))
            except (ValueError, AttributeError):
                return {'events_before': [], 'events_after': []}

            events_before = []
            events_after = []

            # Add imaging events
            for img in imaging_text_reports:
                try:
                    img_date_str = img.get('imaging_date')
                    if not img_date_str:
                        continue
                    img_date = datetime.fromisoformat(str(img_date_str).replace(' ', 'T'))
                    days_diff = (current_date - img_date).days

                    # Only include events within ±180 days
                    if abs(days_diff) > 180:
                        continue

                    event = {
                        'event_type': 'Imaging',
                        'event_category': img.get('imaging_modality', 'MRI Brain'),
                        'event_date': img_date_str.split(' ')[0],
                        'days_diff': -days_diff,  # Negative if before, positive if after
                        'description': f"{img.get('imaging_modality', 'MRI')}"
                    }

                    if days_diff > 0:  # Before current date
                        events_before.append(event)
                    elif days_diff < 0:  # After current date
                        events_after.append(event)

                except (ValueError, AttributeError):
                    continue

            # Add procedure events
            for proc_id, proc_date_str, surgery_type in surgical_history:
                try:
                    proc_date = datetime.fromisoformat(str(proc_date_str).replace(' ', 'T'))
                    days_diff = (current_date - proc_date).days

                    # Only include procedures within ±180 days
                    if abs(days_diff) > 180:
                        continue

                    event = {
                        'event_type': 'Procedure',
                        'event_category': 'Surgery',
                        'event_date': proc_date_str.split(' ')[0] if ' ' in str(proc_date_str) else str(proc_date_str),
                        'days_diff': -days_diff,  # Negative if before, positive if after
                        'description': surgery_type
                    }

                    if days_diff > 0:  # Before current date
                        events_before.append(event)
                    elif days_diff < 0:  # After current date
                        events_after.append(event)

                except (ValueError, AttributeError):
                    continue

            # Sort by proximity to current date
            events_before.sort(key=lambda x: abs(x['days_diff']))
            events_after.sort(key=lambda x: abs(x['days_diff']))

            return {
                'events_before': events_before,
                'events_after': events_after
            }

        # 2A: Extract from imaging text reports
        print(f"2A. Extracting from {len(imaging_text_reports)} imaging text reports...")
        for i, report in enumerate(imaging_text_reports, 1):
            report_id = report.get('diagnostic_report_id', 'unknown')
            report_date = report.get('imaging_date', 'unknown')
            print(f"  [{i}/{len(imaging_text_reports)}] {report_id[:30]}... ({report_date})")

            # Build timeline context with events before/after this report
            timeline_events = build_timeline_context(report_date)

            # Pass entire report dict to prompts - they will extract what they need
            context = {
                'patient_id': args.patient_id,
                'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
                'report_date': report_date,
                'events_before': timeline_events['events_before'],
                'events_after': timeline_events['events_after']
            }

            # Imaging classification
            classification_prompt = build_imaging_classification_prompt(report, context)
            classification_result = medgemma.extract(classification_prompt)
            print(f"    Classification: {classification_result.extracted_data.get('imaging_type', 'unknown')}")

            # Tumor status
            tumor_status_prompt = build_tumor_status_extraction_prompt(report, context)
            tumor_status_result = medgemma.extract(tumor_status_prompt)
            print(f"    Tumor status: {tumor_status_result.extracted_data.get('tumor_status', 'unknown')}")

            # Tumor location
            location_prompt = build_tumor_location_extraction_prompt(report, context)
            location_result = medgemma.extract(location_prompt, "tumor_location")

            # Normalize location to CBTN codes
            normalized_locations = []
            if location_result.success and location_result.extracted_data:
                primary_location = location_result.extracted_data.get('primary_location', '')
                if primary_location and primary_location != 'Not specified':
                    normalized = location_normalizer.normalise_label(primary_location)
                    if normalized:
                        normalized_locations.append({
                            'type': 'primary',
                            'free_text': primary_location,
                            'cbtn_code': normalized.cbtn_code,
                            'cbtn_label': normalized.cbtn_label,
                            'confidence': normalized.confidence,
                            'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label} for node in normalized.ontology_nodes]
                        })

            location_display = location_result.extracted_data.get('primary_location', 'Not extracted') if location_result.success else 'Error'
            print(f"    Location: {location_display}")

            all_extractions.append({
                'source': 'imaging_text',
                'source_id': report_id,
                'date': report_date,
                'classification': classification_result.extracted_data if classification_result.success else {'error': classification_result.error},
                'tumor_status': tumor_status_result.extracted_data if tumor_status_result.success else {'error': tumor_status_result.error},
                'tumor_location': location_result.extracted_data if location_result.success else {'error': location_result.error},
                'tumor_location_normalized': normalized_locations,
                'classification_confidence': classification_result.confidence,
                'tumor_status_confidence': tumor_status_result.confidence,
                'tumor_location_confidence': location_result.confidence
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
                extracted_text, error = binary_agent.extract_text_from_binary(
                    binary_id=binary_id,
                    patient_fhir_id=args.patient_id,
                    content_type=pdf_doc.get('content_type'),
                    document_reference_id=doc_id
                )
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
                'radiology_report_text': extracted_text,  # Full extracted PDF text
                'document_text': extracted_text,  # Alias for compatibility
                'patient_fhir_id': args.patient_id
            }

            # Build timeline context with events before/after this report
            timeline_events = build_timeline_context(doc_date)

            # Build context with surgical history and timeline
            context = {
                'patient_id': args.patient_id,
                'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
                'report_date': doc_date,
                'events_before': timeline_events['events_before'],
                'events_after': timeline_events['events_after']
            }

            # Extract classification and tumor status using MedGemma
            classification_prompt = build_imaging_classification_prompt(report, context)
            classification_result = medgemma.extract(classification_prompt, "imaging_classification")

            tumor_status_prompt = build_tumor_status_extraction_prompt(report, context)
            tumor_status_result = medgemma.extract(tumor_status_prompt, "tumor_status")

            # Tumor location
            location_prompt = build_tumor_location_extraction_prompt(report, context)
            location_result = medgemma.extract(location_prompt, "tumor_location")

            # Normalize location to CBTN codes
            normalized_locations = []
            if location_result.success and location_result.extracted_data:
                primary_location = location_result.extracted_data.get('primary_location', '')
                if primary_location and primary_location != 'Not specified':
                    normalized = location_normalizer.normalise_label(primary_location)
                    if normalized:
                        normalized_locations.append({
                            'type': 'primary',
                            'free_text': primary_location,
                            'cbtn_code': normalized.cbtn_code,
                            'cbtn_label': normalized.cbtn_label,
                            'confidence': normalized.confidence,
                            'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label}
                                            for node in normalized.ontology_nodes]
                        })

                # Also normalize additional locations if present
                additional_locs = location_result.extracted_data.get('all_locations_mentioned', [])
                for loc_text in additional_locs:
                    if loc_text and loc_text != primary_location and loc_text != 'Not specified':
                        normalized = location_normalizer.normalise_label(loc_text)
                        if normalized:
                            normalized_locations.append({
                                'type': 'additional',
                                'free_text': loc_text,
                                'cbtn_code': normalized.cbtn_code,
                                'cbtn_label': normalized.cbtn_label,
                                'confidence': normalized.confidence,
                                'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label}
                                                for node in normalized.ontology_nodes]
                            })

            location_display = location_result.extracted_data.get('primary_location', 'Not extracted') if location_result.success else 'Error'

            print(f"  [{idx}/{len(imaging_pdfs)}] {doc_id[:30]}... ({doc_date})")
            print(f"    Classification: {classification_result.extracted_data.get('imaging_type', 'unknown')}")
            print(f"    Tumor status: {tumor_status_result.extracted_data.get('overall_status', 'Unknown')}")
            print(f"    Location: {location_display}")

            all_extractions.append({
                'source': 'imaging_pdf',
                'source_id': doc_id,
                'date': doc_date,
                'classification': classification_result.extracted_data if classification_result.success else {'error': classification_result.error},
                'tumor_status': tumor_status_result.extracted_data if tumor_status_result.success else {'error': tumor_status_result.error},
                'tumor_location': location_result.extracted_data if location_result.success else {'error': location_result.error},
                'tumor_location_normalized': normalized_locations,
                'classification_confidence': classification_result.confidence,
                'tumor_status_confidence': tumor_status_result.confidence,
                'tumor_location_confidence': location_result.confidence
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
            proc_date = surgery['procedure_date']
            surgery_type = surgery.get('surgery_type', 'unknown')

            print(f"  [{idx}/{len(operative_reports)}] {proc_id[:30]}... ({proc_date}) - {surgery_type}")

            # Skip procedures with missing date
            if not proc_date or (isinstance(proc_date, str) and proc_date.strip() == ''):
                print(f"    ⚠️  Skipping procedure with missing date")
                continue

            # Query for operative note DocumentReference linked to this procedure
            # Search for notes created around the time of surgery (±7 days)
            proc_date_str = proc_date.split()[0] if isinstance(proc_date, str) and ' ' in proc_date else str(proc_date)

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

                # Build operative report dict
                operative_report = {
                    'note_text': extracted_text,
                    'document_text': extracted_text,
                    'procedure_date': proc_date,
                    'surgery_date': proc_date,
                    'proc_code_text': surgery['proc_code_text'],
                    'surgery_type': surgery_type,
                    'procedure_fhir_id': proc_id,
                    'operative_note_id': doc_id
                }

                # Build timeline context
                timeline_events = build_timeline_context(proc_date)
                context = {
                    'patient_id': args.patient_id,
                    'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
                    'report_date': proc_date,
                    'events_before': timeline_events['events_before'],
                    'events_after': timeline_events['events_after']
                }

                # Extract EOR using MedGemma
                eor_prompt = build_operative_report_eor_extraction_prompt(operative_report, context)
                eor_result = medgemma.extract(eor_prompt, "operative_report_eor")

                # Tumor location
                location_prompt = build_tumor_location_extraction_prompt(operative_report, context)
                location_result = medgemma.extract(location_prompt, "tumor_location")

                # Normalize location to CBTN codes
                normalized_locations = []
                if location_result.success and location_result.extracted_data:
                    primary_location = location_result.extracted_data.get('primary_location', '')
                    if primary_location and primary_location != 'Not specified':
                        normalized = location_normalizer.normalise_label(primary_location)
                        if normalized:
                            normalized_locations.append({
                                'type': 'primary',
                                'free_text': primary_location,
                                'cbtn_code': normalized.cbtn_code,
                                'cbtn_label': normalized.cbtn_label,
                                'confidence': normalized.confidence,
                                'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label}
                                                for node in normalized.ontology_nodes]
                            })

                    # Also normalize additional locations if present
                    additional_locs = location_result.extracted_data.get('all_locations_mentioned', [])
                    for loc_text in additional_locs:
                        if loc_text and loc_text != primary_location and loc_text != 'Not specified':
                            normalized = location_normalizer.normalise_label(loc_text)
                            if normalized:
                                normalized_locations.append({
                                    'type': 'additional',
                                    'free_text': loc_text,
                                    'cbtn_code': normalized.cbtn_code,
                                    'cbtn_label': normalized.cbtn_label,
                                    'confidence': normalized.confidence,
                                    'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label}
                                                    for node in normalized.ontology_nodes]
                                })

                location_display = location_result.extracted_data.get('primary_location', 'Not extracted') if location_result.success else 'Error'

                print(f"    EOR: {eor_result.extracted_data.get('extent_of_resection', 'Unknown')}")
                print(f"    Location: {location_display}")
                print(f"    Operative note: {doc_id[:30]}... ({doc_date})")

                all_extractions.append({
                    'source': 'operative_report',
                    'source_id': proc_id,
                    'operative_note_id': doc_id,
                    'surgery_date': proc_date,
                    'surgery_type': surgery_type,
                    'eor': eor_result.extracted_data if eor_result.success else {'error': eor_result.error},
                    'tumor_location': location_result.extracted_data if location_result.success else {'error': location_result.error},
                    'tumor_location_normalized': normalized_locations,
                    'confidence': eor_result.confidence,
                    'tumor_location_confidence': location_result.confidence
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
                extracted_text, error = binary_agent.extract_text_from_binary(
                    binary_id=binary_id,
                    patient_fhir_id=args.patient_id,
                    content_type=content_type,
                    document_reference_id=doc_id
                )
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

            # Build progress note dict
            progress_note = {
                'note_text': extracted_text,
                'document_text': extracted_text,
                'dr_date': doc_date,
                'document_date': doc_date,
                'dr_type_text': note.get('dr_type_text'),
                'document_reference_id': doc_id,
                'priority_reason': priority_reason
            }

            # Build timeline context
            timeline_events = build_timeline_context(doc_date)
            context = {
                'patient_id': args.patient_id,
                'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
                'report_date': doc_date,
                'events_before': timeline_events['events_before'],
                'events_after': timeline_events['events_after']
            }

            # Extract disease state using MedGemma
            disease_state_prompt = build_progress_note_disease_state_prompt(progress_note, context)
            disease_state_result = medgemma.extract(disease_state_prompt, "progress_note_disease_state")

            # Tumor location
            location_prompt = build_tumor_location_extraction_prompt(progress_note, context)
            location_result = medgemma.extract(location_prompt, "tumor_location")

            # Normalize location to CBTN codes
            normalized_locations = []
            if location_result.success and location_result.extracted_data:
                primary_location = location_result.extracted_data.get('primary_location', '')
                if primary_location and primary_location != 'Not specified':
                    normalized = location_normalizer.normalise_label(primary_location)
                    if normalized:
                        normalized_locations.append({
                            'type': 'primary',
                            'free_text': primary_location,
                            'cbtn_code': normalized.cbtn_code,
                            'cbtn_label': normalized.cbtn_label,
                            'confidence': normalized.confidence,
                            'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label}
                                            for node in normalized.ontology_nodes]
                        })

                # Also normalize additional locations if present
                additional_locs = location_result.extracted_data.get('all_locations_mentioned', [])
                for loc_text in additional_locs:
                    if loc_text and loc_text != primary_location and loc_text != 'Not specified':
                        normalized = location_normalizer.normalise_label(loc_text)
                        if normalized:
                            normalized_locations.append({
                                'type': 'additional',
                                'free_text': loc_text,
                                'cbtn_code': normalized.cbtn_code,
                                'cbtn_label': normalized.cbtn_label,
                                'confidence': normalized.confidence,
                                'ontology_ids': [{'source': node.source, 'id': node.id, 'label': node.label}
                                                for node in normalized.ontology_nodes]
                            })

            location_display = location_result.extracted_data.get('primary_location', 'Not extracted') if location_result.success else 'Error'

            print(f"  [{idx}/{len(prioritized_notes)}] {doc_id[:30]}... ({doc_date})")
            print(f"    Priority: {priority_reason}")
            print(f"    Disease state: {disease_state_result.extracted_data.get('disease_status', 'Unknown')}")
            print(f"    Location: {location_display}")

            all_extractions.append({
                'source': 'progress_note',
                'source_id': doc_id,
                'date': doc_date,
                'priority_reason': priority_reason,
                'disease_state': disease_state_result.extracted_data if disease_state_result.success else {'error': disease_state_result.error},
                'tumor_location': location_result.extracted_data if location_result.success else {'error': location_result.error},
                'tumor_location_normalized': normalized_locations,
                'confidence': disease_state_result.confidence,
                'tumor_location_confidence': location_result.confidence
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

        # Build list of tumor status extractions from imaging for temporal analysis
        imaging_extractions = []
        for extraction in all_extractions:
            if extraction['source'] in ['imaging_text', 'imaging_pdf']:
                tumor_status = None
                if 'tumor_status' in extraction:
                    ts = extraction['tumor_status']
                    if isinstance(ts, dict) and not ts.get('error'):
                        tumor_status = ts.get('overall_status') or ts.get('tumor_status')

                if tumor_status:
                    imaging_extractions.append({
                        'source_id': extraction['source_id'],
                        'date': extraction['date'],
                        'tumor_status': tumor_status,
                        'confidence': extraction.get('tumor_status_confidence', 0.0)
                    })

        # Sort by date
        imaging_extractions.sort(key=lambda x: x['date'] if x['date'] else '')

        # Detect inconsistencies in consecutive pairs
        for i in range(len(imaging_extractions) - 1):
            prior = imaging_extractions[i]
            current = imaging_extractions[i + 1]

            try:
                prior_date = datetime.fromisoformat(str(prior['date']))
                current_date = datetime.fromisoformat(str(current['date']))
                days_diff = (current_date - prior_date).days

                prior_status = prior['tumor_status']
                current_status = current['tumor_status']

                # RULE 1: Rapid improvement (Increased→Decreased in <14 days without surgery)
                if prior_status == 'Increased' and current_status == 'Decreased' and days_diff < 14:
                    # Check if surgery explains this
                    surgery_between = any(
                        ext for ext in all_extractions
                        if ext['source'] == 'operative_report'
                        and prior_date <= datetime.fromisoformat(str(ext.get('surgery_date', ''))) <= current_date
                    ) if all_extractions else False

                    if not surgery_between:
                        inconsistencies.append({
                            'inconsistency_id': f"rapid_improvement_{prior['source_id']}_{current['source_id']}",
                            'type': 'rapid_improvement',
                            'severity': 'high',
                            'description': f"Tumor status improved from Increased to Decreased in {days_diff} days without documented surgery",
                            'prior_date': str(prior_date.date()),
                            'current_date': str(current_date.date()),
                            'days_between': days_diff,
                            'prior_status': prior_status,
                            'current_status': current_status,
                            'requires_agent2_query': True
                        })

                # RULE 2: Unexplained progression (NED→Increased in <90 days)
                if prior_status == 'NED' and current_status == 'Increased' and days_diff < 90:
                    inconsistencies.append({
                        'inconsistency_id': f"unexpected_progression_{prior['source_id']}_{current['source_id']}",
                        'type': 'unexpected_progression',
                        'severity': 'medium',
                        'description': f"Disease detected {days_diff} days after NED (possible recurrence)",
                        'prior_date': str(prior_date.date()),
                        'current_date': str(current_date.date()),
                        'days_between': days_diff,
                        'prior_status': prior_status,
                        'current_status': current_status,
                        'requires_agent2_query': False  # Expected pattern
                    })

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to compare dates for inconsistency detection: {e}")
                continue

        print(f"  Detected {len(inconsistencies)} temporal inconsistencies")
        if inconsistencies:
            high_severity = [i for i in inconsistencies if i['severity'] == 'high']
            medium_severity = [i for i in inconsistencies if i['severity'] == 'medium']
            print(f"    High severity: {len(high_severity)}")
            print(f"    Medium severity: {len(medium_severity)}")

            # Show samples
            for inc in inconsistencies[:3]:
                print(f"    - {inc['type']}: {inc['description']}")
        print()

        comprehensive_summary['phases']['temporal_inconsistencies'] = {
            'count': len(inconsistencies),
            'high_severity': len([i for i in inconsistencies if i['severity'] == 'high']),
            'requiring_agent2_query': len([i for i in inconsistencies if i.get('requires_agent2_query')]),
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

        # Query Agent 2 for clarification on high-severity inconsistencies
        high_severity_inc = [i for i in inconsistencies if i.get('requires_agent2_query')]

        for inc in high_severity_inc:
            try:
                # Build clarification prompt
                clarification_prompt = f'''# AGENT 1 REQUESTS CLARIFICATION FROM AGENT 2

## Temporal Inconsistency Detected

**Type:** {inc['type']}
**Severity:** {inc['severity']}
**Description:** {inc['description']}

## Timeline
- **{inc['prior_date']}**: {inc['prior_status']}
- **{inc['current_date']}**: {inc['current_status']}
- **Days between**: {inc['days_between']}

## Question for Agent 2

After reviewing the timeline above:

1. **Clinical Plausibility**: Is this rapid change clinically plausible?
2. **Potential Explanations**: What could explain this pattern?
3. **Recommendation**: Should either extraction be revised?

Provide recommendation: keep_both | revise_first | revise_second | escalate_to_human
'''

                # Query Agent 2
                result = medgemma.extract(clarification_prompt, "temporal_inconsistency_clarification")

                clarifications.append({
                    'inconsistency_id': inc['inconsistency_id'],
                    'type': inc['type'],
                    'agent2_response': result.extracted_data if result.success else None,
                    'success': result.success,
                    'confidence': result.confidence,
                    'error': result.error if not result.success else None
                })

                if result.success:
                    print(f"    ✅ {inc['type']}: {result.extracted_data.get('recommended_action', 'N/A')}")
                else:
                    print(f"    ❌ {inc['type']}: Failed to get clarification")

            except Exception as e:
                logger.error(f"Failed to query Agent 2 for {inc['inconsistency_id']}: {e}")
                clarifications.append({
                    'inconsistency_id': inc['inconsistency_id'],
                    'success': False,
                    'error': str(e)
                })

        print(f"  {len(clarifications)} Agent 2 queries sent")
        if clarifications:
            successful = len([c for c in clarifications if c.get('success')])
            print(f"    Successful: {successful}/{len(clarifications)}")
        print()

        comprehensive_summary['phases']['agent_feedback'] = {
            'queries_sent': len(clarifications),
            'successful_clarifications': len([c for c in clarifications if c.get('success')]),
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

        # Group operative reports with their post-op imaging (within 72 hours)
        operative_reports = [e for e in all_extractions if e['source'] == 'operative_report']

        for op_report in operative_reports:
            try:
                surgery_date_str = op_report.get('surgery_date')
                if not surgery_date_str:
                    continue

                surgery_date = datetime.fromisoformat(str(surgery_date_str))
                proc_id = op_report['source_id']

                # Get EOR from operative report
                operative_eor = None
                if 'eor' in op_report and isinstance(op_report['eor'], dict):
                    eor_data = op_report['eor']
                    if not eor_data.get('error'):
                        operative_eor = eor_data.get('extent_of_resection')

                if not operative_eor or operative_eor == 'Unknown':
                    continue  # Skip if no EOR extracted

                # Find post-op imaging within 72 hours
                postop_imaging = []
                for ext in all_extractions:
                    if ext['source'] in ['imaging_text', 'imaging_pdf']:
                        try:
                            img_date = datetime.fromisoformat(str(ext['date']))
                            hours_diff = (img_date - surgery_date).total_seconds() / 3600

                            # Post-op imaging: 0-72 hours after surgery
                            if 0 <= hours_diff <= 72:
                                # Check if imaging mentions resection/EOR
                                classification = ext.get('classification', {})
                                if isinstance(classification, dict) and not classification.get('error'):
                                    imaging_type = classification.get('imaging_type', '').lower()
                                    # Look for post-op assessment keywords
                                    if any(keyword in imaging_type for keyword in ['post', 'operative', 'resection', 'surgical']):
                                        postop_imaging.append({
                                            'imaging_id': ext['source_id'],
                                            'imaging_date': ext['date'],
                                            'hours_after_surgery': round(hours_diff, 1),
                                            'tumor_status': ext.get('tumor_status', {}).get('overall_status'),
                                            'imaging_type': imaging_type
                                        })
                        except (ValueError, TypeError):
                            continue

                # Only adjudicate if we have both sources
                if postop_imaging:
                    # Build EOR sources for adjudicator
                    sources = [
                        EORSource(
                            source_type='operative_report',
                            source_id=proc_id,
                            source_date=surgery_date,
                            eor=operative_eor,
                            confidence=op_report.get('confidence', 0.85),
                            evidence=f"Operative report from {surgery_date.date()}",
                            extracted_by='agent2_medgemma'
                        )
                    ]

                    # Infer EOR from post-op imaging tumor status
                    for img in postop_imaging:
                        tumor_status = img.get('tumor_status')
                        inferred_eor = 'Unknown'

                        # Inference rules
                        if tumor_status == 'NED' or tumor_status == 'Decreased':
                            inferred_eor = 'Gross Total Resection'
                        elif tumor_status == 'Stable':
                            inferred_eor = 'Near Total Resection'
                        elif tumor_status == 'Increased':
                            inferred_eor = 'Partial Resection'

                        if inferred_eor != 'Unknown':
                            sources.append(
                                EORSource(
                                    source_type='postop_imaging',
                                    source_id=img['imaging_id'],
                                    source_date=datetime.fromisoformat(img['imaging_date']),
                                    eor=inferred_eor,
                                    confidence=0.70,  # Lower confidence for inferred EOR
                                    evidence=f"Post-op imaging ({img['hours_after_surgery']}h after surgery) shows {tumor_status}",
                                    extracted_by='agent2_medgemma'
                                )
                            )

                    # Adjudicate
                    adjudication = eor_adjudicator.adjudicate_eor(proc_id, surgery_date, sources)

                    eor_adjudications.append({
                        'procedure_id': proc_id,
                        'surgery_date': str(surgery_date.date()),
                        'final_eor': adjudication.final_eor,
                        'confidence': adjudication.confidence,
                        'primary_source': adjudication.primary_source,
                        'agreement_status': adjudication.agreement,
                        'sources_count': len(sources),
                        'operative_report_eor': operative_eor,
                        'postop_imaging_count': len(postop_imaging),
                        'discrepancy_notes': adjudication.discrepancy_notes,
                        'reasoning': adjudication.adjudication_reasoning
                    })

                    print(f"    Procedure {proc_id[:20]}... ({surgery_date.date()})")
                    print(f"      Operative: {operative_eor}")
                    print(f"      Final: {adjudication.final_eor} (confidence: {adjudication.confidence:.2f})")
                    if adjudication.agreement == 'discrepancy':
                        print(f"      ⚠️  Discrepancy: {adjudication.discrepancy_notes}")

            except Exception as e:
                logger.error(f"Failed to adjudicate EOR for {proc_id}: {e}")
                continue

        print(f"  {len(eor_adjudications)} EOR adjudications completed")
        if eor_adjudications:
            agreements = len([a for a in eor_adjudications if a['agreement_status'] == 'full_agreement'])
            discrepancies = len([a for a in eor_adjudications if a['agreement_status'] == 'discrepancy'])
            print(f"    Full agreement: {agreements}")
            print(f"    Discrepancies: {discrepancies}")
        print()

        comprehensive_summary['phases']['eor_adjudication'] = {
            'count': len(eor_adjudications),
            'full_agreement': len([a for a in eor_adjudications if a['agreement_status'] == 'full_agreement']),
            'discrepancies': len([a for a in eor_adjudications if a['agreement_status'] == 'discrepancy']),
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
            # Write extractions to timeline first so classifier can access them
            workflow_logger.log_info("Writing tumor status extractions to timeline for event classification")

            for ext in all_extractions:
                if ext['source'] in ['imaging_text', 'imaging_pdf']:
                    if 'tumor_status' in ext and isinstance(ext['tumor_status'], dict):
                        ts_data = ext['tumor_status']
                        if not ts_data.get('error'):
                            tumor_status = ts_data.get('overall_status') or ts_data.get('tumor_status')
                            if tumor_status and tumor_status != 'Unknown':
                                try:
                                    # Write to timeline so event_classifier can query it
                                    timeline.conn.execute('''
                                        INSERT OR IGNORE INTO extracted_variables
                                        (patient_id, source_event_id, variable_name, variable_value, variable_confidence, extraction_date)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    ''', [
                                        args.patient_id,
                                        ext['source_id'],
                                        'tumor_status',
                                        tumor_status,
                                        ext.get('tumor_status_confidence', 0.0),
                                        datetime.now().isoformat()
                                    ])
                                except Exception as e:
                                    logger.warning(f"Failed to write tumor_status to timeline: {e}")

            timeline.conn.commit()

            # Write EOR extractions to timeline
            for ext in all_extractions:
                if ext['source'] == 'operative_report' and 'eor' in ext:
                    if isinstance(ext['eor'], dict) and not ext['eor'].get('error'):
                        eor_value = ext['eor'].get('extent_of_resection')
                        if eor_value and eor_value != 'Unknown':
                            try:
                                timeline.conn.execute('''
                                    INSERT OR IGNORE INTO extracted_variables
                                    (patient_id, source_event_id, variable_name, variable_value, variable_confidence, extraction_date)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', [
                                    args.patient_id,
                                    ext['source_id'],
                                    'extent_of_resection',
                                    eor_value,
                                    ext.get('confidence', 0.0),
                                    datetime.now().isoformat()
                                ])
                            except Exception as e:
                                logger.warning(f"Failed to write EOR to timeline: {e}")

            timeline.conn.commit()

            # Now classify events
            event_classifications_raw = event_classifier.classify_patient_events(args.patient_id)

            # Convert to dict format
            event_classifications = []
            for cls in event_classifications_raw:
                event_classifications.append({
                    'event_id': cls.event_id,
                    'event_date': cls.event_date.isoformat() if isinstance(cls.event_date, datetime) else str(cls.event_date),
                    'event_type': cls.event_type,
                    'confidence': cls.confidence,
                    'reasoning': cls.reasoning,
                    'supporting_evidence': cls.supporting_evidence
                })

            print(f"  ✅ Classified {len(event_classifications)} events")

            # Show sample with counts by type
            type_counts = {}
            for cls in event_classifications:
                event_type = cls['event_type']
                type_counts[event_type] = type_counts.get(event_type, 0) + 1

            for event_type, count in sorted(type_counts.items()):
                print(f"    {event_type}: {count}")

            # Show samples
            for cls in event_classifications[:3]:
                print(f"    - {cls['event_date']}: {cls['event_type']} (confidence: {cls['confidence']:.2f})")

            comprehensive_summary['phases']['event_classification'] = {
                'count': len(event_classifications),
                'by_type': type_counts,
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

        # Sanitize patient_id for filename
        safe_patient_id = args.patient_id.replace('/', '_')
        abstraction_path = output_dir / f"{safe_patient_id}_comprehensive.json"
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

            # Sanitize patient_id for filename
            safe_patient_id = args.patient_id.replace('/', '_')
            emergency_path = output_dir / f"{safe_patient_id}_PARTIAL.json"
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
