#!/usr/bin/env python3
"""
Patient Clinical Journey Timeline Abstraction with Molecular Context

This script implements Claude-orchestrated, MedGemma-assisted abstraction using
the NEW v_patient_clinical_journey_timeline and v_pathology_diagnostics schemas.

KEY DIFFERENCES from legacy run_full_multi_source_abstraction.py:
1. Queries v_patient_clinical_journey_timeline VIEW (not DuckDB timeline database)
2. Queries v_pathology_diagnostics with extraction_priority field
3. Constructs timeline on-the-fly from 6 individual Athena views
4. Molecular-aware extraction prioritization using WHO 2021 framework
5. Uses v_radiation_episode_enrichment (experimental view with appointment metadata)

Architecture:
- Claude: Orchestrates workflow, validates protocols, detects inconsistencies
- MedGemma: Extracts from binary documents when structured data insufficient
- Athena Views: Single source of truth for all clinical data
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
import boto3
import time
from typing import Dict, List, Any, Optional, Tuple
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_aws_sso_token(profile_name: str = 'radiant-prod') -> bool:
    """Check if AWS SSO token is valid"""
    try:
        session = boto3.Session(profile_name=profile_name)
        sts = session.client('sts')
        sts.get_caller_identity()
        logger.info(f"AWS SSO token for '{profile_name}' is valid")
        return True
    except Exception as e:
        logger.error(f"AWS SSO token invalid: {e}")
        return False


def query_athena(query: str, description: str = None, profile: str = 'radiant-prod') -> List[Dict[str, Any]]:
    """Execute Athena query and return results as list of dicts"""
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

    # Get results with pagination
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
                if description:
                    print(f" ✅ 0 records")
                return []
            header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            result_rows = results['ResultSet']['Rows'][1:]
        else:
            result_rows = results['ResultSet']['Rows']

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

    if description:
        print(f" ✅ {len(rows)} records")
    return rows


class PatientTimelineAbstraction:
    """
    Main orchestration class for patient timeline abstraction.

    This implements the TWO-AGENT architecture:
    - Agent 1 (Claude/this class): Orchestrates, validates, contextualizes
    - Agent 2 (MedGemma): Extracts from binaries when needed
    """

    def __init__(self, patient_id: str, output_dir: Path):
        self.patient_id = patient_id
        self.athena_patient_id = patient_id.replace('Patient/', '')
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Timeline data structures
        self.molecular_profile = {}
        self.timeline_events = []
        self.protocol_validations = []
        self.extraction_gaps = []

        logger.info(f"Initialized PatientTimelineAbstraction for {patient_id}")

    def run(self) -> Dict[str, Any]:
        """Execute full timeline abstraction workflow"""

        abstraction_summary = {
            'patient_id': self.patient_id,
            'timestamp': datetime.now().isoformat(),
            'output_dir': str(self.output_dir),
            'phases': {}
        }

        # ================================================================
        # PHASE 0: MOLECULAR PROFILING (WHO 2021 CLASSIFICATION)
        # ================================================================
        print("="*80)
        print("PHASE 0: MOLECULAR PROFILING & WHO 2021 CLASSIFICATION")
        print("="*80)
        print()

        molecular_data = self._phase0_molecular_profiling()
        abstraction_summary['phases']['molecular_profiling'] = molecular_data
        abstraction_summary['molecular_profile'] = self.molecular_profile

        # ================================================================
        # PHASE 1: LOAD PATIENT TIMELINE FROM NEW VIEWS
        # ================================================================
        print("="*80)
        print("PHASE 1: LOAD PATIENT CLINICAL JOURNEY TIMELINE")
        print("="*80)
        print()

        timeline_data = self._phase1_load_timeline()
        abstraction_summary['phases']['timeline_loading'] = timeline_data

        # ================================================================
        # PHASE 2: PROTOCOL VALIDATION (MOLECULAR-INFORMED)
        # ================================================================
        print("="*80)
        print("PHASE 2: MOLECULAR-INFORMED PROTOCOL VALIDATION")
        print("="*80)
        print()

        protocol_data = self._phase2_protocol_validation()
        abstraction_summary['phases']['protocol_validation'] = protocol_data
        abstraction_summary['protocol_validations'] = self.protocol_validations

        # ================================================================
        # PHASE 3: IDENTIFY EXTRACTION GAPS (BINARY NLP NEEDED)
        # ================================================================
        print("="*80)
        print("PHASE 3: IDENTIFY EXTRACTION GAPS FOR MEDGEMMA")
        print("="*80)
        print()

        gap_data = self._phase3_identify_extraction_gaps()
        abstraction_summary['phases']['extraction_gaps'] = gap_data
        abstraction_summary['extraction_gaps'] = self.extraction_gaps

        # ================================================================
        # PHASE 4: GENERATE CLINICAL SUMMARY REPORT
        # ================================================================
        print("="*80)
        print("PHASE 4: GENERATE CLINICAL SUMMARY")
        print("="*80)
        print()

        clinical_summary = self._phase4_generate_clinical_summary()
        abstraction_summary['clinical_summary'] = clinical_summary

        # Save final abstraction
        safe_patient_id = self.patient_id.replace('/', '_')
        output_file = self.output_dir / f"{safe_patient_id}_timeline_abstraction.json"
        with open(output_file, 'w') as f:
            json.dump(abstraction_summary, f, indent=2)

        print()
        print(f"✅ Abstraction saved: {output_file}")

        return abstraction_summary

    def _phase0_molecular_profiling(self) -> Dict[str, Any]:
        """
        PHASE 0: Query v_pathology_diagnostics for molecular markers
        and perform WHO 2021 classification
        """
        print("0A. Querying molecular markers from v_pathology_diagnostics...")

        molecular_query = f"""
        SELECT
            patient_fhir_id,
            diagnostic_date,
            diagnostic_name,
            diagnostic_source,
            component_name,
            result_value,
            extraction_priority,
            document_category,
            days_from_surgery,
            linked_procedure_name,
            linked_procedure_datetime
        FROM fhir_prd_db.v_pathology_diagnostics
        WHERE patient_fhir_id = '{self.athena_patient_id}'
            AND component_name IS NOT NULL
        ORDER BY diagnostic_date, extraction_priority
        """

        molecular_markers = query_athena(molecular_query, "Querying molecular markers")

        # Build molecular profile
        self.molecular_profile = {
            'patient_id': self.patient_id,
            'markers': {},
            'who_2021_classification': None,
            'clinical_significance': None,
            'expected_prognosis': None,
            'recommended_protocols': {},
            'all_markers_raw': molecular_markers
        }

        # Categorize markers
        marker_categories = {}
        for marker in molecular_markers:
            component = marker.get('component_name', '').lower()
            result = marker.get('result_value', '')

            # Categorize by marker type
            if 'h3 k27' in component or 'h3k27' in component:
                marker_categories['H3_K27'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'h3 g34' in component or 'h3g34' in component:
                marker_categories['H3_G34'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'idh' in component:
                marker_categories['IDH'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'braf' in component:
                marker_categories['BRAF'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'mycn' in component:
                marker_categories['MYCN'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'tp53' in component:
                marker_categories['TP53'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'smarcb1' in component or 'ini-1' in component or 'ini1' in component:
                marker_categories['SMARCB1'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}
            elif 'ctnnb1' in component or 'wnt' in component:
                marker_categories['CTNNB1_WNT'] = {'name': marker['component_name'], 'value': result, 'date': marker.get('diagnostic_date')}

        self.molecular_profile['markers'] = marker_categories

        # WHO 2021 classification logic
        if 'H3_K27' in marker_categories:
            h3_k27_value = marker_categories['H3_K27']['value'].lower()
            if 'altered' in h3_k27_value or 'mutant' in h3_k27_value or 'positive' in h3_k27_value:
                self.molecular_profile['who_2021_classification'] = 'H3 K27-altered Diffuse Midline Glioma'
                self.molecular_profile['clinical_significance'] = 'CRITICAL: Uniformly fatal, median survival 9-11 months'
                self.molecular_profile['expected_prognosis'] = 'POOR: Expect progression within 6-12 months post-treatment'
                self.molecular_profile['recommended_protocols'] = {
                    'radiation': '54 Gy focal radiation',
                    'chemotherapy': 'Concurrent temozolomide or clinical trial',
                    'surveillance': 'MRI every 2-3 months'
                }

        elif 'BRAF' in marker_categories:
            braf_value = marker_categories['BRAF']['value'].lower()
            if 'v600e' in braf_value:
                self.molecular_profile['who_2021_classification'] = 'BRAF V600E-mutant Low-Grade Glioma'
                self.molecular_profile['clinical_significance'] = 'ACTIONABLE: Targeted therapy available'
                self.molecular_profile['expected_prognosis'] = 'FAVORABLE: Long-term survival with targeted therapy'
                self.molecular_profile['recommended_protocols'] = {
                    'first_line': 'Dabrafenib + Trametinib',
                    'radiation': 'Often deferred, 50.4-54 Gy if needed',
                    'surveillance': 'MRI every 3-4 months'
                }

        elif 'MYCN' in marker_categories:
            mycn_value = marker_categories['MYCN']['value'].lower()
            if 'amplif' in mycn_value:
                self.molecular_profile['who_2021_classification'] = 'MYCN-amplified Medulloblastoma Group 3'
                self.molecular_profile['clinical_significance'] = 'HIGH RISK: Aggressive tumor'
                self.molecular_profile['expected_prognosis'] = 'GUARDED: 50-60% 5-year survival with aggressive therapy'
                self.molecular_profile['recommended_protocols'] = {
                    'radiation': '54 Gy craniospinal + posterior fossa boost',
                    'chemotherapy': 'High-dose cisplatin/cyclophosphamide/vincristine',
                    'surveillance': 'MRI brain/spine every 3 months'
                }

        elif 'IDH' in marker_categories:
            idh_value = marker_categories['IDH']['value'].lower()
            if 'mutant' in idh_value:
                self.molecular_profile['who_2021_classification'] = 'IDH-mutant Glioma'
                self.molecular_profile['clinical_significance'] = 'FAVORABLE: Better prognosis than IDH-wildtype'
                self.molecular_profile['expected_prognosis'] = 'INTERMEDIATE: Median survival 5-10 years depending on grade'
            elif 'wildtype' in idh_value:
                self.molecular_profile['who_2021_classification'] = 'IDH-wildtype Glioblastoma'
                self.molecular_profile['clinical_significance'] = 'POOR PROGNOSIS: Aggressive tumor'
                self.molecular_profile['expected_prognosis'] = 'POOR: Median survival 12-18 months'
                self.molecular_profile['recommended_protocols'] = {
                    'radiation': '60 Gy focal radiation',
                    'chemotherapy': 'Concurrent + adjuvant temozolomide (Stupp protocol)',
                    'surveillance': 'MRI every 2-3 months'
                }

        elif 'SMARCB1' in marker_categories:
            smarcb1_value = marker_categories['SMARCB1']['value'].lower()
            if 'deficient' in smarcb1_value or 'loss' in smarcb1_value or 'deleted' in smarcb1_value:
                self.molecular_profile['who_2021_classification'] = 'SMARCB1-deficient Atypical Teratoid Rhabdoid Tumor'
                self.molecular_profile['clinical_significance'] = 'CRITICAL: Highly aggressive embryonal tumor'
                self.molecular_profile['expected_prognosis'] = 'VERY POOR: Median survival 12-18 months'

        print(f"  Molecular markers detected: {len(marker_categories)}")
        if self.molecular_profile['who_2021_classification']:
            print(f"  WHO 2021 classification: {self.molecular_profile['who_2021_classification']}")
            print(f"  Clinical significance: {self.molecular_profile['clinical_significance']}")
        else:
            print(f"  ⚠️  No WHO 2021 classification determined")

        print()

        return {
            'markers_count': len(marker_categories),
            'who_2021_classification': self.molecular_profile['who_2021_classification'],
            'clinical_significance': self.molecular_profile['clinical_significance']
        }

    def _phase1_load_timeline(self) -> Dict[str, Any]:
        """
        PHASE 1: Query v_patient_clinical_journey_timeline to get full timeline

        NOTE: We query the VIEW directly, not construct from individual sources.
        The view already performs the UNION of all 8 event types.
        """
        print("1A. Querying v_patient_clinical_journey_timeline...")

        # Check if view exists (it may not be deployed yet)
        try:
            timeline_query = f"""
            SELECT
                patient_fhir_id,
                event_sequence_number,
                event_date,
                event_datetime,
                event_type,
                event_subtype,
                description,
                days_from_surgery,
                treatment_phase,

                -- Diagnosis-specific fields
                diagnostic_name,
                molecular_marker,

                -- Surgery-specific fields
                surgery_type,

                -- Treatment-specific fields
                medication_name,
                radiation_dose_cgy,
                radiation_field,

                -- Imaging-specific fields
                imaging_modality,
                report_conclusion,
                progression_flag,

                -- Visit-specific fields
                visit_type

            FROM fhir_prd_db.v_patient_clinical_journey_timeline
            WHERE patient_fhir_id = '{self.athena_patient_id}'
            ORDER BY event_sequence_number
            """

            timeline_events = query_athena(timeline_query, "Querying unified timeline")

            if timeline_events:
                self.timeline_events = timeline_events
                print(f"  ✅ Loaded {len(timeline_events)} timeline events from VIEW")
                return {
                    'source': 'v_patient_clinical_journey_timeline',
                    'event_count': len(timeline_events),
                    'status': 'success'
                }

        except Exception as e:
            logger.warning(f"v_patient_clinical_journey_timeline view not available: {e}")
            print(f"  ⚠️  View not deployed, constructing timeline from individual sources...")

        # FALLBACK: Construct timeline from individual views (if unified view not deployed)
        print("1B. Constructing timeline from individual Athena views...")

        # Query each source view
        sources = {
            'pathology': self._query_pathology(),
            'procedures': self._query_procedures(),
            'chemotherapy': self._query_chemotherapy(),
            'radiation': self._query_radiation(),
            'imaging': self._query_imaging(),
            'visits': self._query_visits()
        }

        # Union all events
        all_events = []
        for source_name, events in sources.items():
            all_events.extend(events)

        # Sort by date
        all_events.sort(key=lambda x: (x.get('event_date', ''), x.get('event_datetime', '')))

        # Add sequence numbers
        for i, event in enumerate(all_events, 1):
            event['event_sequence_number'] = i

        self.timeline_events = all_events

        print(f"  ✅ Constructed timeline: {len(all_events)} events from {len(sources)} sources")

        return {
            'source': 'constructed_from_individual_views',
            'event_count': len(all_events),
            'sources': {k: len(v) for k, v in sources.items()},
            'status': 'success'
        }

    def _query_pathology(self) -> List[Dict]:
        """Query v_pathology_diagnostics for diagnosis events"""
        query = f"""
        SELECT
            patient_fhir_id,
            diagnostic_date,
            diagnostic_name,
            component_name,
            result_value,
            extraction_priority,
            document_category
        FROM fhir_prd_db.v_pathology_diagnostics
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY diagnostic_date
        """
        rows = query_athena(query, "Querying pathology diagnostics")

        events = []
        for row in rows:
            events.append({
                'event_type': 'diagnosis',
                'event_date': row.get('diagnostic_date'),
                'event_datetime': row.get('diagnostic_date'),
                'description': row.get('diagnostic_name'),
                'diagnostic_name': row.get('diagnostic_name'),
                'molecular_marker': row.get('component_name'),
                'molecular_result': row.get('result_value'),
                'extraction_priority': row.get('extraction_priority'),
                'document_category': row.get('document_category')
            })

        return events

    def _query_procedures(self) -> List[Dict]:
        """Query v_procedures_tumor for surgery events"""
        query = f"""
        SELECT
            patient_fhir_id,
            proc_performed_date_time,
            surgery_type,
            proc_code_text
        FROM fhir_prd_db.v_procedures_tumor
        WHERE patient_fhir_id = '{self.athena_patient_id}'
            AND is_tumor_surgery = true
        ORDER BY proc_performed_date_time
        """
        rows = query_athena(query, "Querying tumor procedures")

        events = []
        for row in rows:
            events.append({
                'event_type': 'surgery',
                'event_date': row.get('proc_performed_date_time', '').split()[0] if row.get('proc_performed_date_time') else '',
                'event_datetime': row.get('proc_performed_date_time'),
                'description': row.get('proc_code_text'),
                'surgery_type': row.get('surgery_type')
            })

        return events

    def _query_chemotherapy(self) -> List[Dict]:
        """Query v_chemo_treatment_episodes for chemotherapy events"""
        query = f"""
        SELECT
            patient_fhir_id,
            episode_start_date,
            episode_end_date,
            episode_medication_names
        FROM fhir_prd_db.v_chemo_treatment_episodes
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY episode_start_date
        """
        rows = query_athena(query, "Querying chemotherapy episodes")

        events = []
        for row in rows:
            # Chemo start event
            events.append({
                'event_type': 'chemotherapy_start',
                'event_date': row.get('episode_start_date'),
                'event_datetime': row.get('episode_start_date'),
                'description': f"Chemotherapy started: {row.get('episode_medication_names', '')}",
                'medication_name': row.get('episode_medication_names')
            })

            # Chemo end event (if ended)
            if row.get('episode_end_date'):
                events.append({
                    'event_type': 'chemotherapy_end',
                    'event_date': row.get('episode_end_date'),
                    'event_datetime': row.get('episode_end_date'),
                    'description': f"Chemotherapy ended: {row.get('episode_medication_names', '')}",
                    'medication_name': row.get('episode_medication_names')
                })

        return events

    def _query_radiation(self) -> List[Dict]:
        """Query v_radiation_episode_enrichment for radiation events"""
        query = f"""
        SELECT
            patient_fhir_id,
            radiation_start_date,
            radiation_end_date,
            total_dose_cgy,
            radiation_field
        FROM fhir_prd_db.v_radiation_episode_enrichment
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY radiation_start_date
        """
        rows = query_athena(query, "Querying radiation episodes")

        events = []
        for row in rows:
            # Radiation start event
            events.append({
                'event_type': 'radiation_start',
                'event_date': row.get('radiation_start_date'),
                'event_datetime': row.get('radiation_start_date'),
                'description': f"Radiation started: {row.get('total_dose_cgy', '')} cGy to {row.get('radiation_field', '')}",
                'radiation_dose_cgy': row.get('total_dose_cgy'),
                'radiation_field': row.get('radiation_field')
            })

            # Radiation end event (if ended)
            if row.get('radiation_end_date'):
                events.append({
                    'event_type': 'radiation_end',
                    'event_date': row.get('radiation_end_date'),
                    'event_datetime': row.get('radiation_end_date'),
                    'description': f"Radiation completed: {row.get('total_dose_cgy', '')} cGy",
                    'radiation_dose_cgy': row.get('total_dose_cgy')
                })

        return events

    def _query_imaging(self) -> List[Dict]:
        """Query v_imaging for imaging events"""
        query = f"""
        SELECT
            patient_fhir_id,
            imaging_date,
            imaging_modality,
            report_conclusion
        FROM fhir_prd_db.v_imaging
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY imaging_date
        """
        rows = query_athena(query, "Querying imaging studies")

        events = []
        for row in rows:
            # Simple progression detection from report conclusion
            conclusion = row.get('report_conclusion', '').lower()
            progression_flag = None
            if any(kw in conclusion for kw in ['increas', 'enlarg', 'expan', 'grow', 'worsen', 'progress']):
                progression_flag = 'progression_suspected'
            elif any(kw in conclusion for kw in ['decreas', 'shrink', 'improv', 'respon']):
                progression_flag = 'response_suspected'
            elif any(kw in conclusion for kw in ['stable', 'unchanged', 'no change']):
                progression_flag = 'stable_disease'

            events.append({
                'event_type': 'imaging',
                'event_date': row.get('imaging_date'),
                'event_datetime': row.get('imaging_date'),
                'description': f"{row.get('imaging_modality', '')} imaging",
                'imaging_modality': row.get('imaging_modality'),
                'report_conclusion': row.get('report_conclusion'),
                'progression_flag': progression_flag
            })

        return events

    def _query_visits(self) -> List[Dict]:
        """Query v_visits_unified for visit events"""
        query = f"""
        SELECT
            patient_fhir_id,
            visit_date,
            visit_type
        FROM fhir_prd_db.v_visits_unified
        WHERE patient_fhir_id = '{self.athena_patient_id}'
        ORDER BY visit_date
        """
        rows = query_athena(query, "Querying clinical visits")

        events = []
        for row in rows:
            events.append({
                'event_type': 'visit',
                'event_date': row.get('visit_date'),
                'event_datetime': row.get('visit_date'),
                'description': f"{row.get('visit_type', '')} visit",
                'visit_type': row.get('visit_type')
            })

        return events

    def _phase2_protocol_validation(self) -> Dict[str, Any]:
        """
        PHASE 2: Validate treatments against WHO 2021 molecular-specific protocols
        """
        who_2021_dx = self.molecular_profile.get('who_2021_classification')

        if not who_2021_dx:
            print("  ⚠️  No molecular classification - skipping protocol validation")
            return {'status': 'skipped', 'reason': 'no_molecular_classification'}

        print(f"  Validating protocols for: {who_2021_dx}")

        # Validate radiation protocol
        radiation_validation = self._validate_radiation_protocol()
        if radiation_validation:
            self.protocol_validations.append(radiation_validation)

        # Validate chemotherapy protocol
        chemo_validation = self._validate_chemotherapy_protocol()
        if chemo_validation:
            self.protocol_validations.append(chemo_validation)

        print(f"  ✅ {len(self.protocol_validations)} protocol validations performed")
        print()

        return {
            'status': 'completed',
            'validation_count': len(self.protocol_validations),
            'validations': self.protocol_validations
        }

    def _validate_radiation_protocol(self) -> Optional[Dict]:
        """Validate radiation dose/field against molecular-specific protocol"""
        who_2021_dx = self.molecular_profile.get('who_2021_classification', '')

        # Find radiation events
        radiation_events = [e for e in self.timeline_events if e.get('event_type') == 'radiation_start']

        if not radiation_events:
            return {
                'protocol_type': 'radiation',
                'status': 'MISSING',
                'message': 'No radiation treatment found',
                'severity': 'warning'
            }

        # Get radiation dose
        radiation_event = radiation_events[0]  # First radiation course
        dose_cgy = radiation_event.get('radiation_dose_cgy')

        if not dose_cgy:
            return {
                'protocol_type': 'radiation',
                'status': 'INCOMPLETE_DATA',
                'message': 'Radiation dose not recorded',
                'severity': 'warning'
            }

        try:
            dose_cgy = float(dose_cgy)
        except (ValueError, TypeError):
            return None

        # Expected dose by molecular subtype
        expected_dose = None
        tolerance = 200  # ±200 cGy tolerance

        if 'H3 K27-altered' in who_2021_dx:
            expected_dose = 5400  # 54 Gy for DMG
        elif 'BRAF V600E' in who_2021_dx:
            expected_dose = None  # Often deferred for LGG with targeted therapy
        elif 'IDH-wildtype' in who_2021_dx:
            expected_dose = 6000  # 60 Gy for GBM
        elif 'Medulloblastoma' in who_2021_dx and 'WNT' in who_2021_dx:
            expected_dose = 2340  # De-escalated for WNT MB
        elif 'Medulloblastoma' in who_2021_dx:
            expected_dose = 5400  # Standard for MB
        elif 'Ependymoma' in who_2021_dx:
            expected_dose = 5940  # 59.4 Gy for ependymoma

        if expected_dose is None:
            return {
                'protocol_type': 'radiation',
                'status': 'NO_STANDARD_PROTOCOL',
                'actual_dose_cgy': dose_cgy,
                'severity': 'info'
            }

        # Check adherence
        if abs(dose_cgy - expected_dose) <= tolerance:
            status = 'ADHERENT'
            severity = 'info'
            message = f"Radiation dose {dose_cgy} cGy within protocol range ({expected_dose}±{tolerance} cGy)"
        elif dose_cgy < expected_dose - tolerance:
            status = 'UNDERDOSED'
            severity = 'critical'
            message = f"Radiation underdosed: {dose_cgy} cGy < {expected_dose - tolerance} cGy (may compromise local control)"
        else:
            status = 'OVERDOSED'
            severity = 'warning'
            message = f"Radiation overdosed: {dose_cgy} cGy > {expected_dose + tolerance} cGy (increased toxicity risk)"

        return {
            'protocol_type': 'radiation',
            'status': status,
            'actual_dose_cgy': dose_cgy,
            'expected_dose_cgy': expected_dose,
            'tolerance_cgy': tolerance,
            'message': message,
            'severity': severity
        }

    def _validate_chemotherapy_protocol(self) -> Optional[Dict]:
        """Validate chemotherapy regimen against molecular-specific protocol"""
        who_2021_dx = self.molecular_profile.get('who_2021_classification', '')

        # Find chemo events
        chemo_events = [e for e in self.timeline_events if e.get('event_type') == 'chemotherapy_start']

        if not chemo_events:
            return {
                'protocol_type': 'chemotherapy',
                'status': 'MISSING',
                'message': 'No chemotherapy treatment found',
                'severity': 'warning'
            }

        # Check for molecular-specific recommendations
        validation = {'protocol_type': 'chemotherapy', 'medications': []}

        for chemo in chemo_events:
            meds = chemo.get('medication_name', '').lower()
            validation['medications'].append(meds)

        # BRAF V600E: Should receive targeted therapy
        if 'BRAF V600E' in who_2021_dx:
            has_dabrafenib = any('dabrafenib' in med for med in validation['medications'])
            has_trametinib = any('trametinib' in med for med in validation['medications'])

            if has_dabrafenib and has_trametinib:
                validation['status'] = 'OPTIMAL'
                validation['message'] = 'Receiving BRAF/MEK targeted therapy (dabrafenib + trametinib) - optimal for BRAF V600E'
                validation['severity'] = 'info'
            else:
                validation['status'] = 'SUBOPTIMAL'
                validation['message'] = 'BRAF V600E mutation detected - recommend dabrafenib + trametinib targeted therapy'
                validation['severity'] = 'warning'

            return validation

        # MYCN-amplified: Should receive high-dose protocol
        if 'MYCN-amplified' in who_2021_dx:
            has_cisplatin = any('cisplatin' in med for med in validation['medications'])
            has_cyclophosphamide = any('cyclophosphamide' in med for med in validation['medications'])

            if has_cisplatin and has_cyclophosphamide:
                validation['status'] = 'ADHERENT'
                validation['message'] = 'High-dose chemotherapy regimen for MYCN-amplified medulloblastoma'
                validation['severity'] = 'info'
            else:
                validation['status'] = 'REVIEW_RECOMMENDED'
                validation['message'] = 'MYCN-amplified medulloblastoma requires high-dose cisplatin/cyclophosphamide protocol'
                validation['severity'] = 'warning'

            return validation

        # Default
        validation['status'] = 'NO_SPECIFIC_RECOMMENDATION'
        validation['severity'] = 'info'
        return validation

    def _phase3_identify_extraction_gaps(self) -> Dict[str, Any]:
        """
        PHASE 3: Identify gaps where MedGemma binary extraction would be valuable

        Uses extraction_priority from v_pathology_diagnostics to identify:
        - Priority 1-2 documents that likely need binary extraction
        - Events with missing key fields (EOR, detailed treatment response, etc.)
        """
        print("  Analyzing timeline for extraction gaps...")

        gaps = []

        # Gap 1: High-priority pathology documents
        pathology_events = [e for e in self.timeline_events if e.get('event_type') == 'diagnosis']
        high_priority_path = [e for e in pathology_events if e.get('extraction_priority') in ['1', '2', 1, 2]]

        if high_priority_path:
            for event in high_priority_path:
                gaps.append({
                    'gap_type': 'high_priority_pathology',
                    'event_date': event.get('event_date'),
                    'extraction_priority': event.get('extraction_priority'),
                    'document_category': event.get('document_category'),
                    'reason': 'Priority 1-2 pathology document may contain additional molecular findings',
                    'recommended_action': 'Extract full text from DocumentReference, review for molecular markers'
                })

        # Gap 2: Surgeries without linked operative notes
        surgery_events = [e for e in self.timeline_events if e.get('event_type') == 'surgery']

        for surgery in surgery_events:
            # Check if we have EOR information (would be in description or separate field)
            if not surgery.get('extent_of_resection'):
                gaps.append({
                    'gap_type': 'missing_eor',
                    'event_date': surgery.get('event_date'),
                    'surgery_type': surgery.get('surgery_type'),
                    'reason': 'Extent of resection not documented in structured data',
                    'recommended_action': 'Extract from operative note binary (v_binary_files, date-matched)'
                })

        # Gap 3: Imaging without detailed response assessment
        imaging_events = [e for e in self.timeline_events if e.get('event_type') == 'imaging']

        for imaging in imaging_events:
            if not imaging.get('progression_flag') and imaging.get('report_conclusion'):
                gaps.append({
                    'gap_type': 'ambiguous_imaging_response',
                    'event_date': imaging.get('event_date'),
                    'imaging_modality': imaging.get('imaging_modality'),
                    'reason': 'Report conclusion exists but no clear progression/response classification',
                    'recommended_action': 'Extract detailed tumor measurements from imaging PDF, classify response'
                })

        self.extraction_gaps = gaps

        print(f"  ✅ Identified {len(gaps)} extraction opportunities")

        # Breakdown by gap type
        gap_types = {}
        for gap in gaps:
            gap_type = gap['gap_type']
            gap_types[gap_type] = gap_types.get(gap_type, 0) + 1

        for gap_type, count in sorted(gap_types.items()):
            print(f"    - {gap_type}: {count}")

        print()

        return {
            'total_gaps': len(gaps),
            'gaps_by_type': gap_types,
            'gaps': gaps
        }

    def _phase4_generate_clinical_summary(self) -> Dict[str, Any]:
        """
        PHASE 4: Generate clinical summary with molecular context
        """
        print("  Generating clinical summary...")

        summary = {
            'patient_id': self.patient_id,
            'molecular_diagnosis': self.molecular_profile.get('who_2021_classification'),
            'prognosis': self.molecular_profile.get('expected_prognosis'),
            'timeline_summary': {},
            'protocol_adherence': {},
            'recommendations': []
        }

        # Timeline summary
        summary['timeline_summary'] = {
            'total_events': len(self.timeline_events),
            'event_types': self._count_event_types(),
            'timeline_span_days': self._calculate_timeline_span()
        }

        # Protocol adherence summary
        protocol_status = {}
        for validation in self.protocol_validations:
            protocol_type = validation.get('protocol_type')
            status = validation.get('status')
            protocol_status[protocol_type] = {
                'status': status,
                'severity': validation.get('severity'),
                'message': validation.get('message')
            }

        summary['protocol_adherence'] = protocol_status

        # Recommendations
        recommendations = []

        # Recommendation 1: CRITICAL protocol deviations
        for validation in self.protocol_validations:
            if validation.get('severity') == 'critical':
                recommendations.append({
                    'priority': 'URGENT',
                    'recommendation': f"PROTOCOL DEVIATION: {validation.get('message')}"
                })

        # Recommendation 2: Binary extraction for gaps
        if self.extraction_gaps:
            high_priority_gaps = [g for g in self.extraction_gaps if 'high_priority' in g.get('gap_type', '')]
            if high_priority_gaps:
                recommendations.append({
                    'priority': 'HIGH',
                    'recommendation': f"Extract {len(high_priority_gaps)} high-priority documents with MedGemma for additional molecular findings"
                })

        # Recommendation 3: Molecular-specific surveillance
        if self.molecular_profile.get('who_2021_classification'):
            recommended_protocols = self.molecular_profile.get('recommended_protocols', {})
            surveillance = recommended_protocols.get('surveillance')
            if surveillance:
                recommendations.append({
                    'priority': 'STANDARD',
                    'recommendation': f"Surveillance: {surveillance}"
                })

        summary['recommendations'] = recommendations

        print(f"  ✅ Summary generated with {len(recommendations)} recommendations")
        print()

        return summary

    def _count_event_types(self) -> Dict[str, int]:
        """Count events by type"""
        counts = {}
        for event in self.timeline_events:
            event_type = event.get('event_type', 'unknown')
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts

    def _calculate_timeline_span(self) -> Optional[int]:
        """Calculate days from first to last event"""
        if not self.timeline_events:
            return None

        dates = [e.get('event_date') for e in self.timeline_events if e.get('event_date')]
        if len(dates) < 2:
            return None

        try:
            first_date = datetime.fromisoformat(min(dates).split()[0])
            last_date = datetime.fromisoformat(max(dates).split()[0])
            return (last_date - first_date).days
        except:
            return None


def main():
    parser = argparse.ArgumentParser(
        description='Patient Clinical Journey Timeline Abstraction with Molecular Context'
    )
    parser.add_argument(
        '--patient-id',
        type=str,
        required=True,
        help='Patient FHIR ID (with or without "Patient/" prefix)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for abstraction results'
    )

    args = parser.parse_args()

    # Check AWS SSO token
    if not check_aws_sso_token():
        print("\n❌ AWS SSO token invalid. Run: aws sso login --profile radiant-prod\n")
        sys.exit(1)

    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*80)
    print("PATIENT CLINICAL JOURNEY TIMELINE ABSTRACTION")
    print("="*80)
    print()
    print(f"Patient: {args.patient_id}")
    print(f"Output: {output_dir}")
    print()
    print("="*80)
    print()

    # Run abstraction
    abstractor = PatientTimelineAbstraction(args.patient_id, output_dir)
    abstraction_summary = abstractor.run()

    print()
    print("="*80)
    print("ABSTRACTION COMPLETE")
    print("="*80)
    print()

    # Print summary
    print("SUMMARY:")
    print(f"  Molecular diagnosis: {abstraction_summary.get('molecular_profile', {}).get('who_2021_classification', 'Not determined')}")
    print(f"  Timeline events: {len(abstraction_summary.get('phases', {}).get('timeline_loading', {}).get('event_count', 0))}")
    print(f"  Protocol validations: {len(abstraction_summary.get('protocol_validations', []))}")
    print(f"  Extraction gaps: {len(abstraction_summary.get('extraction_gaps', []))}")

    recommendations = abstraction_summary.get('clinical_summary', {}).get('recommendations', [])
    if recommendations:
        print()
        print("RECOMMENDATIONS:")
        for rec in recommendations:
            print(f"  [{rec.get('priority')}] {rec.get('recommendation')}")

    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
