#!/usr/bin/env python3
"""
Timeline-Focused Treatment Response Abstraction

This script uses v_patient_clinical_journey_timeline to intelligently target
binary documents for deep NLP extraction where free-text fields are insufficient.

ORCHESTRATION ARCHITECTURE:
- Claude (this script): Orchestrating agent that queries timeline, identifies gaps, prioritizes documents
- MedGemma: Specialized medical extraction agent for NLP tasks

KEY DIFFERENCES FROM run_full_multi_source_abstraction.py:
1. Timeline-guided: Queries v_patient_clinical_journey_timeline FIRST to identify gaps
2. Targeted extraction: Only extracts documents with missing/ambiguous information
3. Response-focused: Prioritizes imaging with progression flags or unclear response
4. Treatment validation: Confirms radiation doses, chemo regimens from binary sources

EXTRACTION PRIORITIES (Claude determines, MedGemma executes):
1. HIGH PRIORITY (always extract):
   - Imaging with progression_flag = 'progression_suspected' BUT free_text_content lacks detail
   - Imaging with response_flag IS NULL (needs deeper assessment)
   - Surgeries with resection_extent_from_text = 'unspecified_extent'
   - Radiation episodes with non-standard doses (needs protocol confirmation)
   - Chemo episodes with unspecified regimen names

2. MEDIUM PRIORITY (extract if time permits):
   - Early post-treatment imaging (baseline assessments)
   - Imaging during active treatment phase
   - Progress notes near medication changes

3. LOW PRIORITY (skip unless comprehensive mode):
   - Surveillance imaging with clear stable_disease flags
   - Visits without clinical significance

Author: Claude (orchestrator) + MedGemma (extractor)
Created: 2025-10-30
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
from typing import Dict, List, Any, Optional, Tuple
import base64

# Add parent directory to path
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def query_athena(query: str, description: str, profile: str = 'radiant-prod') -> List[Dict[str, Any]]:
    """Execute Athena query and return results"""
    if description:
        print(f"  {description}...", end='', flush=True)

    session = boto3.Session(profile_name=profile)
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
            if description:
                print(f" ❌ FAILED: {reason}")
            return []
        time.sleep(1)

    # Get results
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

        if header is None:
            if len(results['ResultSet']['Rows']) <= 1:
                if description:
                    print(f" ✅ 0 records")
                return []
            header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            result_rows = results['ResultSet']['Rows'][1:]
        else:
            result_rows = results['ResultSet']['Rows']

        for row in result_rows:
            row_dict = {}
            for i, col in enumerate(row['Data']):
                row_dict[header[i]] = col.get('VarCharValue', '')
            rows.append(row_dict)

        next_token = results.get('NextToken')
        if not next_token:
            break

    if description:
        print(f" ✅ {len(rows)} records")
    return rows


class TimelineFocusedExtractor:
    """
    Claude orchestrating agent that uses timeline to guide MedGemma extraction.
    """

    def __init__(self, patient_id: str, aws_profile: str = 'radiant-prod'):
        self.patient_id = patient_id
        self.athena_patient_id = patient_id.replace('Patient/', '')
        self.aws_profile = aws_profile

        # Initialize MedGemma extraction agent
        self.medgemma = MedGemmaAgent(model_name="gemma2:27b")
        self.binary_agent = BinaryFileAgent()
        self.doc_cache = DocumentTextCache(db_path="data/document_text_cache.duckdb")

        # Timeline data
        self.timeline_events = []
        self.extraction_targets = []

        logger.info(f"Initialized TimelineFocusedExtractor for patient {patient_id}")

    def load_patient_timeline(self) -> bool:
        """
        STEP 1 (Claude): Query Athena views to build unified patient timeline.

        Uses the following Athena views (NOT DuckDB):
        - v_pathology_diagnostics (diagnosis with molecular markers)
        - v_procedures_tumor (surgical procedures)
        - v_chemo_treatment_episodes (chemotherapy episodes)
        - v_radiation_episode_enrichment (radiation episodes)
        - v_imaging (imaging studies with report conclusions)
        - v_visits_unified (clinical visits)

        Constructs timeline on-the-fly from these sources.
        """
        print("\n" + "="*80)
        print("STEP 1: CLAUDE LOADS PATIENT TIMELINE FROM ATHENA VIEWS")
        print("="*80)
        print()

        timeline_events = []

        # 1A. Query v_pathology_diagnostics for diagnosis events
        print("  1A. Querying v_pathology_diagnostics...")
        diagnosis_query = f"""
        SELECT
            diagnostic_date as event_date,
            diagnostic_source as event_subtype,
            diagnostic_name,
            component_name as molecular_marker,
            result_value as molecular_result,
            extraction_priority,
            document_category,
            days_from_surgery,
            source_id as event_id,
            'diagnosis' as event_type,
            'v_pathology_diagnostics' as source_view
        FROM fhir_prd_db.v_pathology_diagnostics
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY diagnostic_date
        """
        diagnosis_events = query_athena(diagnosis_query, None)
        timeline_events.extend(diagnosis_events)
        print(f"    {len(diagnosis_events)} diagnosis events")

        # 1B. Query v_procedures_tumor for surgery events
        print("  1B. Querying v_procedures_tumor...")
        surgery_query = f"""
        SELECT
            CAST(proc_performed_date_time AS DATE) as event_date,
            proc_performed_date_time as event_datetime,
            surgery_type as event_subtype,
            proc_code_text as event_description,
            surgery_extent,
            proc_outcome_text as free_text_content,
            procedure_fhir_id as event_id,
            'surgery' as event_type,
            'v_procedures_tumor' as source_view
        FROM fhir_prd_db.v_procedures_tumor
        WHERE patient_fhir_id = '{self.athena_patient_id}'
            AND is_tumor_surgery = true
        ORDER BY proc_performed_date_time
        """
        surgery_events = query_athena(surgery_query, None)
        timeline_events.extend(surgery_events)
        print(f"    {len(surgery_events)} surgery events")

        # 1C. Query v_chemo_treatment_episodes for chemotherapy episodes
        print("  1C. Querying v_chemo_treatment_episodes...")
        chemo_query = f"""
        SELECT
            CAST(episode_start_datetime AS DATE) as event_date,
            episode_start_datetime as event_datetime,
            'treatment_initiation' as event_subtype,
            chemo_preferred_name as event_description,
            episode_id,
            medication_count,
            episode_duration_days,
            'chemo_episode_start' as event_type,
            'v_chemo_treatment_episodes' as source_view
        FROM fhir_prd_db.v_chemo_treatment_episodes
        WHERE patient_fhir_id = '{self.athena_patient_id}'

        UNION ALL

        SELECT
            CAST(episode_end_datetime AS DATE) as event_date,
            episode_end_datetime as event_datetime,
            'treatment_completion' as event_subtype,
            chemo_preferred_name as event_description,
            episode_id,
            medication_count,
            episode_duration_days,
            'chemo_episode_end' as event_type,
            'v_chemo_treatment_episodes' as source_view
        FROM fhir_prd_db.v_chemo_treatment_episodes
        WHERE patient_fhir_id = '{self.athena_patient_id}'

        ORDER BY event_date
        """
        chemo_events = query_athena(chemo_query, None)
        timeline_events.extend(chemo_events)
        print(f"    {len(chemo_events)} chemotherapy events")

        # 1D. Query v_radiation_episode_enrichment for radiation episodes
        print("  1D. Querying v_radiation_episode_enrichment...")
        radiation_query = f"""
        SELECT
            episode_start_date as event_date,
            CAST(episode_start_date AS TIMESTAMP) as event_datetime,
            'treatment_initiation' as event_subtype,
            CONCAT('Radiation: ', CAST(total_dose_cgy AS VARCHAR), ' cGy') as event_description,
            episode_id,
            total_dose_cgy,
            num_unique_fields,
            'radiation_episode_start' as event_type,
            'v_radiation_episode_enrichment' as source_view
        FROM fhir_prd_db.v_radiation_episode_enrichment
        WHERE patient_fhir_id = '{self.athena_patient_id}'

        UNION ALL

        SELECT
            episode_end_date as event_date,
            CAST(episode_end_date AS TIMESTAMP) as event_datetime,
            'treatment_completion' as event_subtype,
            CONCAT('Radiation completed: ', CAST(total_dose_cgy AS VARCHAR), ' cGy') as event_description,
            episode_id,
            total_dose_cgy,
            num_unique_fields,
            'radiation_episode_end' as event_type,
            'v_radiation_episode_enrichment' as source_view
        FROM fhir_prd_db.v_radiation_episode_enrichment
        WHERE patient_fhir_id = '{self.athena_patient_id}'

        ORDER BY event_date
        """
        radiation_events = query_athena(radiation_query, None)
        timeline_events.extend(radiation_events)
        print(f"    {len(radiation_events)} radiation events")

        # 1E. Query v_imaging for imaging events
        print("  1E. Querying v_imaging...")
        imaging_query = f"""
        SELECT
            imaging_date as event_date,
            CAST(imaging_date AS TIMESTAMP) as event_datetime,
            imaging_modality as event_subtype,
            imaging_procedure as event_description,
            report_conclusion as free_text_content,
            imaging_id as event_id,
            'imaging' as event_type,
            'v_imaging' as source_view
        FROM fhir_prd_db.v_imaging
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY imaging_date
        """
        imaging_events = query_athena(imaging_query, None)
        timeline_events.extend(imaging_events)
        print(f"    {len(imaging_events)} imaging events")

        # 1F. Query v_visits_unified for visit events
        print("  1F. Querying v_visits_unified...")
        visit_query = f"""
        SELECT
            visit_date as event_date,
            CAST(visit_date AS TIMESTAMP) as event_datetime,
            visit_type as event_subtype,
            CONCAT(visit_type, ' (', appointment_status, ')') as event_description,
            visit_id as event_id,
            'visit' as event_type,
            'v_visits_unified' as source_view
        FROM fhir_prd_db.v_visits_unified
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY visit_date
        """
        visit_events = query_athena(visit_query, None)
        timeline_events.extend(visit_events)
        print(f"    {len(visit_events)} visit events")

        # Sort all events by date
        timeline_events.sort(key=lambda e: e.get('event_date', ''))
        self.timeline_events = timeline_events

        if not self.timeline_events:
            print("  ❌ No timeline events found for patient")
            return False

        # Summary statistics
        event_type_counts = {}
        for event in self.timeline_events:
            event_type = event.get('event_type', 'unknown')
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

        print(f"\n  ✅ Constructed unified timeline with {len(self.timeline_events)} events")
        print(f"  Event breakdown:")
        for event_type, count in sorted(event_type_counts.items()):
            print(f"    - {event_type}: {count}")

        # Patient context from diagnosis events
        diagnosis_events_list = [e for e in self.timeline_events if e.get('event_type') == 'diagnosis']
        if diagnosis_events_list:
            first_diagnosis = diagnosis_events_list[0]
            print(f"\n  Patient context:")
            print(f"    Diagnosis: {first_diagnosis.get('diagnostic_name', 'Unknown')}")
            print(f"    Molecular marker: {first_diagnosis.get('molecular_marker', 'Not specified')}")

        return True

    def identify_extraction_targets(self) -> List[Dict[str, Any]]:
        """
        STEP 2 (Claude): Analyze timeline to identify documents needing binary extraction.

        DECISION LOGIC (Claude's role):
        - High priority: progression_flag set but free_text is vague
        - High priority: response_flag is NULL (needs assessment)
        - High priority: resection_extent = 'unspecified_extent'
        - Medium priority: early post-treatment imaging
        - Skip: events with sufficient free text information
        """
        print("\n" + "="*80)
        print("STEP 2: CLAUDE IDENTIFIES EXTRACTION TARGETS")
        print("="*80)
        print()

        targets = []

        # RULE 1: Imaging with progression flag but insufficient detail
        progression_events = [e for e in self.timeline_events
                             if e.get('progression_flag') and e['event_type'] == 'imaging']

        for event in progression_events:
            free_text = event.get('free_text_content', '')
            # If free text is short (<50 chars) or generic, needs deeper extraction
            if not free_text or len(free_text) < 50:
                targets.append({
                    'target_type': 'imaging_progression_clarification',
                    'priority': 'HIGH',
                    'event_id': event['event_id'],
                    'event_date': event['event_date'],
                    'event_description': event['event_description'],
                    'progression_flag': event['progression_flag'],
                    'reason': f"Progression suspected but free text insufficient ({len(free_text)} chars)",
                    'source_view': event['source_view']
                })

        print(f"  HIGH PRIORITY: {len([t for t in targets if t['priority'] == 'HIGH'])} imaging reports with progression need clarification")

        # RULE 2: Imaging without response assessment (response_flag IS NULL)
        unclear_response = [e for e in self.timeline_events
                           if e['event_type'] == 'imaging'
                           and not e.get('response_flag')
                           and not e.get('progression_flag')
                           and e.get('imaging_phase') not in ['pre_op_baseline', None]]

        for event in unclear_response:
            targets.append({
                'target_type': 'imaging_response_assessment',
                'priority': 'HIGH',
                'event_id': event['event_id'],
                'event_date': event['event_date'],
                'event_description': event['event_description'],
                'imaging_phase': event.get('imaging_phase'),
                'reason': 'Response status unclear from free text',
                'source_view': event['source_view']
            })

        print(f"  HIGH PRIORITY: {len([t for t in targets if t['target_type'] == 'imaging_response_assessment'])} imaging reports need response assessment")

        # RULE 3: Surgeries with unspecified extent of resection
        unclear_eor = [e for e in self.timeline_events
                      if e['event_type'] == 'surgery'
                      and e.get('resection_extent_from_text') == 'unspecified_extent']

        for event in unclear_eor:
            targets.append({
                'target_type': 'surgery_eor_clarification',
                'priority': 'HIGH',
                'event_id': event['event_id'],
                'event_date': event['event_date'],
                'event_description': event['event_description'],
                'reason': 'Extent of resection not specified in procedure outcome',
                'source_view': event['source_view']
            })

        print(f"  HIGH PRIORITY: {len([t for t in targets if t['target_type'] == 'surgery_eor_clarification'])} surgeries need EOR clarification")

        # RULE 4: Early post-treatment imaging (medium priority - baseline assessment)
        baseline_imaging = [e for e in self.timeline_events
                           if e['event_type'] == 'imaging'
                           and e.get('imaging_phase') in ['immediate_post_op', 'early_post_radiation']
                           and e['event_id'] not in [t['event_id'] for t in targets]]

        for event in baseline_imaging[:5]:  # Limit to 5 baseline studies
            targets.append({
                'target_type': 'baseline_imaging_assessment',
                'priority': 'MEDIUM',
                'event_id': event['event_id'],
                'event_date': event['event_date'],
                'event_description': event['event_description'],
                'imaging_phase': event['imaging_phase'],
                'reason': 'Baseline post-treatment assessment',
                'source_view': event['source_view']
            })

        print(f"  MEDIUM PRIORITY: {len([t for t in targets if t['priority'] == 'MEDIUM'])} baseline imaging studies")

        # Sort by priority and date
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        targets.sort(key=lambda t: (priority_order[t['priority']], t['event_date']))

        self.extraction_targets = targets

        print(f"\n  📋 TOTAL EXTRACTION TARGETS: {len(targets)}")
        print(f"     HIGH priority: {len([t for t in targets if t['priority'] == 'HIGH'])}")
        print(f"     MEDIUM priority: {len([t for t in targets if t['priority'] == 'MEDIUM'])}")

        return targets

    def extract_target_documents(self, max_extractions: int = 20) -> List[Dict[str, Any]]:
        """
        STEP 3 (Claude orchestrates MedGemma): Extract binary documents for identified targets.

        Claude's role: Query v_binary_files, manage extraction flow, build prompts
        MedGemma's role: Extract structured data from unstructured reports
        """
        print("\n" + "="*80)
        print("STEP 3: CLAUDE ORCHESTRATES MEDGEMMA EXTRACTION")
        print("="*80)
        print()

        if not self.extraction_targets:
            print("  No extraction targets identified")
            return []

        extractions = []
        targets_to_process = self.extraction_targets[:max_extractions]

        print(f"  Processing {len(targets_to_process)} extraction targets (max: {max_extractions})")
        print()

        for idx, target in enumerate(targets_to_process, 1):
            try:
                print(f"[{idx}/{len(targets_to_process)}] {target['target_type']} ({target['priority']})")
                print(f"  Event: {target['event_description'][:80]}...")
                print(f"  Date: {target['event_date']}")
                print(f"  Reason: {target['reason']}")

                # Query v_binary_files for this event
                if target['target_type'].startswith('imaging'):
                    # Find imaging report binary
                    binary_query = f"""
                    SELECT
                        document_reference_id,
                        binary_id,
                        content_type,
                        dr_date
                    FROM fhir_prd_db.v_binary_files
                    WHERE patient_fhir_id = '{self.athena_patient_id}'
                        AND (
                            LOWER(dr_category_text) LIKE '%imaging%'
                            OR LOWER(dr_category_text) LIKE '%radiology%'
                        )
                        AND DATE(dr_date) = DATE '{target['event_date']}'
                        AND content_type IN ('application/pdf', 'text/html', 'text/plain')
                    LIMIT 1
                    """
                elif target['target_type'] == 'surgery_eor_clarification':
                    # Find operative note binary
                    binary_query = f"""
                    SELECT
                        document_reference_id,
                        binary_id,
                        content_type,
                        dr_date,
                        dr_type_text
                    FROM fhir_prd_db.v_binary_files
                    WHERE patient_fhir_id = '{self.athena_patient_id}'
                        AND (
                            dr_type_text LIKE 'OP Note%'
                            OR dr_type_text = 'Operative Record'
                        )
                        AND DATE(dr_context_period_start) = DATE '{target['event_date']}'
                        AND content_type IN ('application/pdf', 'text/html', 'text/plain')
                    LIMIT 1
                    """
                else:
                    print(f"  ⚠️  Unknown target type: {target['target_type']}")
                    continue

                binaries = query_athena(binary_query, None)

                if not binaries:
                    print(f"  ⚠️  No binary document found for this event")
                    continue

                binary_doc = binaries[0]
                doc_id = binary_doc['document_reference_id']
                binary_id = binary_doc['binary_id']

                # Check cache
                cached_doc = self.doc_cache.get_cached_document(doc_id)
                if cached_doc:
                    extracted_text = cached_doc.extracted_text
                    print(f"  ✓ Using cached text")
                else:
                    # Extract text from binary (Claude manages this)
                    extracted_text, error = self.binary_agent.extract_text_from_binary(
                        binary_id=binary_id,
                        patient_fhir_id=self.patient_id,
                        content_type=binary_doc.get('content_type'),
                        document_reference_id=doc_id
                    )

                    if error:
                        print(f"  ❌ Failed to extract: {error}")
                        continue

                    # Cache
                    extraction_method = "html_beautifulsoup" if "html" in binary_doc.get('content_type', '') else \
                                       "pdf_pymupdf" if "pdf" in binary_doc.get('content_type', '') else "text_plain"

                    self.doc_cache.cache_document_from_binary(
                        document_id=doc_id,
                        patient_fhir_id=self.patient_id,
                        extracted_text=extracted_text,
                        extraction_method=extraction_method,
                        binary_id=binary_id,
                        document_date=binary_doc['dr_date'],
                        content_type=binary_doc.get('content_type'),
                        document_type=target['target_type']
                    )

                # Build prompt and invoke MedGemma (Claude orchestrates)
                if target['target_type'].startswith('imaging'):
                    report = {
                        'diagnostic_report_id': doc_id,
                        'imaging_date': target['event_date'],
                        'radiology_report_text': extracted_text,
                        'document_text': extracted_text
                    }
                    context = {'patient_id': self.patient_id, 'surgical_history': []}

                    # Extract tumor status using MedGemma
                    tumor_status_prompt = build_tumor_status_extraction_prompt(report, context)
                    result = self.medgemma.extract(tumor_status_prompt, "tumor_status")

                    if result.success:
                        print(f"  ✅ MedGemma extracted: {result.extracted_data.get('overall_status', 'Unknown')}")
                        extractions.append({
                            'target': target,
                            'document_id': doc_id,
                            'extraction': result.extracted_data,
                            'confidence': result.confidence
                        })
                    else:
                        print(f"  ❌ MedGemma extraction failed: {result.error}")

                elif target['target_type'] == 'surgery_eor_clarification':
                    operative_report = {
                        'note_text': extracted_text,
                        'document_text': extracted_text,
                        'procedure_date': target['event_date'],
                        'surgery_date': target['event_date']
                    }
                    context = {'patient_id': self.patient_id, 'surgical_history': []}

                    # Extract EOR using MedGemma
                    eor_prompt = build_operative_report_eor_extraction_prompt(operative_report, context)
                    result = self.medgemma.extract(eor_prompt, "operative_report_eor")

                    if result.success:
                        print(f"  ✅ MedGemma extracted EOR: {result.extracted_data.get('extent_of_resection', 'Unknown')}")
                        extractions.append({
                            'target': target,
                            'document_id': doc_id,
                            'extraction': result.extracted_data,
                            'confidence': result.confidence
                        })
                    else:
                        print(f"  ❌ MedGemma extraction failed: {result.error}")

                print()

            except Exception as e:
                logger.error(f"Failed to process target {target['event_id']}: {e}", exc_info=True)
                print(f"  ❌ Error: {e}")
                print()

        print(f"  ✅ Completed {len(extractions)} extractions")
        return extractions

    def generate_summary(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        STEP 4 (Claude): Generate summary of timeline-focused extraction results.
        """
        print("\n" + "="*80)
        print("STEP 4: CLAUDE GENERATES SUMMARY")
        print("="*80)
        print()

        summary = {
            'patient_id': self.patient_id,
            'timestamp': datetime.now().isoformat(),
            'timeline_events_count': len(self.timeline_events),
            'extraction_targets_identified': len(self.extraction_targets),
            'extractions_completed': len(extractions),
            'extraction_success_rate': len(extractions) / len(self.extraction_targets) if self.extraction_targets else 0,
            'extractions': extractions
        }

        # Breakdown by target type
        target_type_counts = {}
        for target in self.extraction_targets:
            target_type = target['target_type']
            target_type_counts[target_type] = target_type_counts.get(target_type, 0) + 1

        summary['targets_by_type'] = target_type_counts

        # Extraction findings
        findings = []
        for extraction in extractions:
            target = extraction['target']
            result = extraction['extraction']

            if target['target_type'].startswith('imaging'):
                status = result.get('overall_status') or result.get('tumor_status', 'Unknown')
                findings.append({
                    'date': target['event_date'],
                    'type': 'imaging',
                    'finding': status,
                    'confidence': extraction['confidence']
                })
            elif target['target_type'] == 'surgery_eor_clarification':
                eor = result.get('extent_of_resection', 'Unknown')
                findings.append({
                    'date': target['event_date'],
                    'type': 'surgery',
                    'finding': eor,
                    'confidence': extraction['confidence']
                })

        summary['key_findings'] = findings

        print(f"  Timeline events reviewed: {len(self.timeline_events)}")
        print(f"  Extraction targets identified: {len(self.extraction_targets)}")
        print(f"  Successful extractions: {len(extractions)}")
        print(f"  Success rate: {summary['extraction_success_rate']*100:.1f}%")
        print()

        print("  Key findings:")
        for finding in findings[:10]:
            print(f"    {finding['date']}: {finding['type']} - {finding['finding']} (confidence: {finding['confidence']:.2f})")

        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Timeline-focused treatment response abstraction (Claude orchestrates MedGemma)'
    )
    parser.add_argument(
        '--patient-id',
        type=str,
        required=True,
        help='Patient FHIR ID to process'
    )
    parser.add_argument(
        '--max-extractions',
        type=int,
        default=20,
        help='Maximum number of documents to extract (default: 20)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/timeline_focused_abstractions',
        help='Output directory for results'
    )

    args = parser.parse_args()

    print("="*80)
    print("TIMELINE-FOCUSED TREATMENT RESPONSE ABSTRACTION")
    print("="*80)
    print()
    print("Architecture:")
    print("  CLAUDE (this script): Orchestrating agent")
    print("    - Queries v_patient_clinical_journey_timeline")
    print("    - Identifies gaps needing binary extraction")
    print("    - Prioritizes documents by clinical significance")
    print("    - Manages extraction workflow")
    print()
    print("  MEDGEMMA: Specialized medical extraction agent")
    print("    - Extracts structured data from unstructured reports")
    print("    - Assesses tumor status, EOR, treatment response")
    print()
    print(f"Patient: {args.patient_id}")
    print(f"Max extractions: {args.max_extractions}")
    print("="*80)
    print()

    # Initialize extractor (Claude orchestrator)
    extractor = TimelineFocusedExtractor(args.patient_id)

    # STEP 1: Claude loads timeline
    if not extractor.load_patient_timeline():
        print("\n❌ Failed to load patient timeline")
        return 1

    # STEP 2: Claude identifies extraction targets
    targets = extractor.identify_extraction_targets()

    if not targets:
        print("\n✅ No extraction targets identified - timeline has sufficient information")
        return 0

    # STEP 3: Claude orchestrates MedGemma extraction
    extractions = extractor.extract_target_documents(max_extractions=args.max_extractions)

    # STEP 4: Claude generates summary
    summary = extractor.generate_summary(extractions)

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_patient_id = args.patient_id.replace('/', '_')
    output_path = output_dir / f"{safe_patient_id}_timeline_focused_{timestamp}.json"

    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*80)
    print("TIMELINE-FOCUSED ABSTRACTION COMPLETE")
    print("="*80)
    print()
    print(f"✅ Results saved: {output_path}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
