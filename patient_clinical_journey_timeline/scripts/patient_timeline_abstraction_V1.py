#!/usr/bin/env python3
"""
Patient Clinical Journey Timeline Abstraction - CORRECTED VERSION

This script implements the TWO-AGENT ITERATIVE WORKFLOW for patient timeline abstraction:

Claude (this script):
  - Queries 6 Athena views for structured data
  - Loads WHO 2021 molecular classifications (from previous work)
  - Constructs initial timeline from structured data
  - Identifies GAPS requiring binary extraction
  - PRIORITIZES extraction based on clinical significance
  - Validates protocols against WHO 2021 treatment paradigms
  - Generates final patient timeline artifact (JSON)

MedGemma (called when needed):
  - Extracts from binary documents (operative notes, radiation summaries, etc.)
  - Returns structured data to Claude for integration

Architecture:
  - NO SQL VIEWS CREATED (uses existing 6 Athena views)
  - Per-patient iterative workflow
  - Output: JSON artifact per patient

Data Sources:
  1. v_pathology_diagnostics (molecular markers, diagnoses)
  2. v_procedures_tumor (surgeries)
  3. v_chemo_treatment_episodes (chemotherapy episodes)
  4. v_radiation_episode_enrichment (radiation episodes with appointment metadata)
  5. v_imaging (imaging studies with free text report conclusions)
  6. v_visits_unified (clinical visits)

Reference Materials:
  - WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md (existing molecular classifications)
  - WHO 2021 Treatment Guide PDF (protocol validation)
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# WHO 2021 MOLECULAR CLASSIFICATIONS (from earlier work this evening)
# Source: WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md
WHO_2021_CLASSIFICATIONS = {
    'eDe7IanglsmBppe3htvO-QdYT26-v54aUqFAeTPQSJ6w3': {
        'who_2021_diagnosis': 'Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4',
        'molecular_subtype': 'H3 K27M+',
        'grade': 4,
        'key_markers': 'H3F3A K27M (IHC+), IDH1-R132H-, ATRX loss',
        'clinical_significance': 'CRITICAL: Uniformly fatal, median survival 9-11 months',
        'expected_prognosis': 'POOR: Expect progression within 6-12 months post-treatment',
        'recommended_protocols': {
            'radiation': '54 Gy focal radiation to pontine lesion',
            'chemotherapy': 'Concurrent temozolomide or clinical trial',
            'surveillance': 'MRI every 2-3 months'
        }
    },
    'eFkHu0Dr07HPadEPDpvudcQOsKqv2vvCvdg-a-r-8SVY3': {
        'who_2021_diagnosis': 'Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4',
        'molecular_subtype': 'H3 K27M+ (TIER 1A)',
        'grade': 4,
        'key_markers': 'H3F3A c.83A>T p.Lys28Met, TP53 c.524G>A p.Arg175His',
        'clinical_significance': 'CRITICAL: Uniformly fatal',
        'expected_prognosis': 'POOR',
        'recommended_protocols': {
            'radiation': '54 Gy focal radiation',
            'chemotherapy': 'Consider clinical trials',
            'surveillance': 'MRI every 2-3 months'
        }
    },
    'eIkYtPKrgCyQIt1zJXMux2cWyHHSSFeZg6zKSznsH7WM3': {
        'who_2021_diagnosis': 'Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4',
        'molecular_subtype': 'H3 K27M+ (molecular upgrade from grade 3 histology)',
        'grade': 4,
        'key_markers': 'H3F3A K27M (IHC+), PIK3R1 del, ATRX c.5494G>A, PPM1D c.1270G>T',
        'clinical_significance': 'CRITICAL: Molecular upgrade despite grade 3 histology',
        'expected_prognosis': 'POOR despite lower histologic grade',
        'recommended_protocols': {
            'radiation': '54 Gy focal radiation',
            'chemotherapy': 'Concurrent temozolomide',
            'surveillance': 'MRI every 2-3 months'
        }
    },
    'eXdEVvOs091o4-RCug2.5hA3': {
        'who_2021_diagnosis': 'Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4',
        'molecular_subtype': 'H3 K27M+, TP53 mutant, PDGFRA amplified',
        'grade': 4,
        'key_markers': 'H3F3A K27M, TP53 c.817C>T, PTPN11 c.1510A>G, PDGFRA amp',
        'clinical_significance': 'CRITICAL: PDGFRA amplification potentially targetable',
        'expected_prognosis': 'POOR',
        'recommended_protocols': {
            'radiation': '54 Gy focal radiation',
            'chemotherapy': 'Consider PDGFRA-targeted therapy',
            'surveillance': 'MRI every 2-3 months'
        }
    },
    'eUFS4hKO-grXh72WvK-5l0TFbD0sV2SMysYY5JpxOR-A3': {
        'who_2021_diagnosis': 'Diffuse hemispheric glioma, H3 G34-mutant, CNS WHO grade 4',
        'molecular_subtype': 'H3 G34R+ (newly recognized WHO 2021 entity)',
        'grade': 4,
        'key_markers': 'H3F3A c.103G>A p.Gly35Arg, TP53 c.586C>T, ATRX frameshift, NUDT15 c.415C>T',
        'clinical_significance': 'HIGH RISK: H3 G34-mutant hemispheric glioma',
        'expected_prognosis': 'POOR (similar to H3 K27M)',
        'recommended_protocols': {
            'radiation': '60 Gy focal radiation (hemispheric location)',
            'chemotherapy': 'Temozolomide-based regimen',
            'surveillance': 'MRI every 2-3 months'
        },
        'special_note': 'NUDT15 variant affects thiopurine metabolism (chemo dosing)'
    },
    'e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3': {
        'who_2021_diagnosis': 'Pineoblastoma, CNS WHO grade 4',
        'molecular_subtype': 'MYC/FOXR2-activated (provisional)',
        'grade': 4,
        'key_markers': 'MYCN amplification, TP53 c.722C>T, NF1 loss/LOH, KRAS G13D, MED12 c.130G>A',
        'clinical_significance': 'CRITICAL: High-risk embryonal tumor',
        'expected_prognosis': 'POOR: Grade 4 embryonal tumor',
        'recommended_protocols': {
            'radiation': '54 Gy craniospinal + posterior fossa boost',
            'chemotherapy': 'High-dose platinum-based (cisplatin/cyclophosphamide/etoposide)',
            'surveillance': 'MRI brain/spine every 3 months, CSF cytology'
        },
        'special_note': 'Embryonal tumor - CSF staging essential'
    },
    'eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83': {
        'who_2021_diagnosis': 'Astrocytoma, IDH-mutant, CNS WHO grade 3',
        'molecular_subtype': 'Adult-type, Lynch syndrome (MSH6 germline mutation)',
        'grade': 3,
        'key_markers': 'IDH1 c.395G>A p.Arg132His, ATRX c.1252C>T, DNMT3A c.2645G>A, MSH6 c.3863_3865dupAAT (germline), MET fusion',
        'clinical_significance': 'MODERATE: IDH-mutant favorable, but Lynch syndrome requires surveillance',
        'expected_prognosis': 'INTERMEDIATE: Median survival 3-5 years for grade 3 IDH-mutant',
        'recommended_protocols': {
            'radiation': '54 Gy focal radiation (if high-grade features)',
            'chemotherapy': 'Temozolomide-based regimen',
            'surveillance': 'MRI every 3-4 months, monitor for CDKN2A/B deletion (would upgrade to grade 4)'
        },
        'special_note': 'Lynch syndrome: genetic counseling required, surveillance for other cancers'
    },
    'eiZ8gIQ.xVzYybDaR2sW5E0z9yI5BQjDeWulBFer5T4g3': {
        'who_2021_diagnosis': 'Pending - insufficient data',
        'molecular_subtype': 'Unknown',
        'grade': None,
        'key_markers': 'Data extraction incomplete',
        'clinical_significance': 'UNKNOWN',
        'expected_prognosis': 'UNKNOWN',
        'recommended_protocols': {}
    },
    'ekrJf9m27ER1umcVah.rRqC.9hDY9ch91PfbuGjUHko03': {
        'who_2021_diagnosis': 'No data available',
        'molecular_subtype': 'Not in v_pathology_diagnostics',
        'grade': None,
        'key_markers': 'No pathology data found',
        'clinical_significance': 'UNKNOWN',
        'expected_prognosis': 'UNKNOWN',
        'recommended_protocols': {}
    }
}


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


class PatientTimelineAbstractor:
    """
    Implements the TWO-AGENT ITERATIVE workflow for patient timeline abstraction.

    This is NOT a SQL view - it's a per-patient orchestration framework that:
    1. Loads structured data from 6 Athena views
    2. Loads WHO 2021 molecular classification (from previous work)
    3. Constructs initial timeline
    4. Identifies gaps → prioritizes binary extraction
    5. Calls MedGemma for extraction (NOT IMPLEMENTED YET - placeholder)
    6. Integrates extractions into timeline
    7. Validates protocols against WHO 2021 treatment paradigms
    8. Generates final JSON artifact
    """

    def __init__(self, patient_id: str, output_dir: Path):
        self.patient_id = patient_id
        self.athena_patient_id = patient_id.replace('Patient/', '')
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load WHO 2021 classification for this patient
        self.who_2021_classification = WHO_2021_CLASSIFICATIONS.get(self.athena_patient_id, {})

        # Data structures
        self.timeline_events = []
        self.extraction_gaps = []
        self.binary_extractions = []  # MedGemma results
        self.protocol_validations = []

        logger.info(f"Initialized abstractor for {patient_id}")
        if self.who_2021_classification.get('who_2021_diagnosis'):
            logger.info(f"  WHO 2021: {self.who_2021_classification['who_2021_diagnosis']}")

    def run(self) -> Dict[str, Any]:
        """Execute full iterative timeline abstraction workflow"""

        print("="*80)
        print(f"PATIENT TIMELINE ABSTRACTION: {self.patient_id}")
        print("="*80)
        print(f"WHO 2021 Diagnosis: {self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')}")
        print("="*80)
        print()

        # PHASE 1: Load structured data from 6 Athena views
        print("PHASE 1: LOAD STRUCTURED DATA FROM ATHENA VIEWS")
        print("-"*80)
        self._phase1_load_structured_data()
        print()

        # PHASE 2: Construct initial timeline
        print("PHASE 2: CONSTRUCT INITIAL TIMELINE")
        print("-"*80)
        self._phase2_construct_initial_timeline()
        print()

        # PHASE 3: Identify extraction gaps
        print("PHASE 3: IDENTIFY GAPS REQUIRING BINARY EXTRACTION")
        print("-"*80)
        self._phase3_identify_extraction_gaps()
        print()

        # PHASE 4: Prioritize and extract from binaries (PLACEHOLDER - MedGemma integration)
        print("PHASE 4: PRIORITIZED BINARY EXTRACTION (PLACEHOLDER)")
        print("-"*80)
        self._phase4_extract_from_binaries_placeholder()
        print()

        # PHASE 5: Protocol validation
        print("PHASE 5: WHO 2021 PROTOCOL VALIDATION")
        print("-"*80)
        self._phase5_protocol_validation()
        print()

        # PHASE 6: Generate final artifact
        print("PHASE 6: GENERATE FINAL TIMELINE ARTIFACT")
        print("-"*80)
        artifact = self._phase6_generate_artifact()
        print()

        return artifact

    def _phase1_load_structured_data(self):
        """Phase 1: Query 6 Athena views for structured data"""

        # CORRECT COLUMN NAMES from schema review
        queries = {
            'pathology': f"""
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
            """,
            'procedures': f"""
                SELECT
                    patient_fhir_id,
                    proc_performed_date_time,
                    surgery_type,
                    proc_code_text
                FROM fhir_prd_db.v_procedures_tumor
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                    AND is_tumor_surgery = true
                ORDER BY proc_performed_date_time
            """,
            'chemotherapy': f"""
                SELECT
                    patient_fhir_id,
                    episode_start_datetime,
                    episode_end_datetime,
                    episode_drug_names
                FROM fhir_prd_db.v_chemo_treatment_episodes
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY episode_start_datetime
            """,
            'radiation': f"""
                SELECT
                    patient_fhir_id,
                    episode_start_date,
                    episode_end_date,
                    total_dose_cgy,
                    radiation_fields
                FROM fhir_prd_db.v_radiation_episode_enrichment
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY episode_start_date
            """,
            'imaging': f"""
                SELECT
                    patient_fhir_id,
                    imaging_date,
                    imaging_modality,
                    report_conclusion,
                    result_diagnostic_report_id,
                    diagnostic_report_id
                FROM fhir_prd_db.v_imaging
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY imaging_date
            """,
            'visits': f"""
                SELECT
                    patient_fhir_id,
                    visit_date,
                    visit_type
                FROM fhir_prd_db.v_visits_unified
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY visit_date
            """
        }

        self.structured_data = {}
        for source_name, query in queries.items():
            self.structured_data[source_name] = query_athena(query, f"Loading {source_name}")

        print(f"  ✅ Loaded structured data from 6 views:")
        for source, data in self.structured_data.items():
            print(f"     {source}: {len(data)} records")

    def _phase2_construct_initial_timeline(self):
        """
        Phase 2: Construct timeline using STEPWISE STAGED approach

        Follows user-specified ordering:
        1. Molecular diagnosis (WHO 2021) - already loaded in Phase 0
        2. Encounters/appointments (visits)
        3. Procedures (surgeries)
        4. Chemotherapy episodes
        5. Radiation episodes
        6. Imaging studies

        Each stage validates against WHO 2021 expected treatment paradigm
        """

        events = []

        # STAGE 0: Add molecular diagnosis as anchor event
        print("  Stage 0: Molecular diagnosis")
        if self.who_2021_classification.get('who_2021_diagnosis'):
            events.append({
                'event_type': 'molecular_diagnosis',
                'event_date': None,  # Molecular diagnosis is not temporally anchored initially
                'stage': 0,
                'source': 'WHO_2021_CLASSIFICATIONS',
                'description': f"Molecular diagnosis: {self.who_2021_classification['who_2021_diagnosis']}",
                'who_2021_diagnosis': self.who_2021_classification.get('who_2021_diagnosis'),
                'molecular_subtype': self.who_2021_classification.get('molecular_subtype'),
                'grade': self.who_2021_classification.get('grade'),
                'expected_protocols': self.who_2021_classification.get('recommended_protocols')
            })
            print(f"    ✅ WHO 2021: {self.who_2021_classification['who_2021_diagnosis']}")
        else:
            print(f"    ⚠️  No WHO 2021 classification available")

        # STAGE 1: Encounters/appointments (visits)
        print("  Stage 1: Encounters/appointments")
        visit_count = 0
        for record in self.structured_data.get('visits', []):
            events.append({
                'event_type': 'visit',
                'event_date': record.get('visit_date'),
                'stage': 1,
                'source': 'v_visits_unified',
                'description': f"{record.get('visit_type', '')} visit",
                'visit_type': record.get('visit_type')
            })
            visit_count += 1
        print(f"    ✅ Added {visit_count} encounters/appointments")

        # STAGE 2: Procedures (surgeries)
        print("  Stage 2: Procedures (surgeries)")
        surgery_count = 0
        for record in self.structured_data.get('procedures', []):
            events.append({
                'event_type': 'surgery',
                'event_date': record.get('proc_performed_date_time', '').split()[0] if record.get('proc_performed_date_time') else '',
                'stage': 2,
                'source': 'v_procedures_tumor',
                'description': record.get('proc_code_text'),
                'surgery_type': record.get('surgery_type'),
                'proc_performed_datetime': record.get('proc_performed_date_time')
            })
            surgery_count += 1
        print(f"    ✅ Added {surgery_count} surgical procedures")

        # Validate against expected paradigm
        if surgery_count == 0 and self.who_2021_classification.get('who_2021_diagnosis'):
            print(f"    ⚠️  WARNING: No surgeries found for patient with {self.who_2021_classification.get('who_2021_diagnosis')}")

        # STAGE 3: Chemotherapy episodes
        print("  Stage 3: Chemotherapy episodes")
        chemo_episode_count = 0
        for record in self.structured_data.get('chemotherapy', []):
            # Start event
            events.append({
                'event_type': 'chemotherapy_start',
                'event_date': record.get('episode_start_datetime', '').split()[0] if record.get('episode_start_datetime') else '',
                'stage': 3,
                'source': 'v_chemo_treatment_episodes',
                'description': f"Chemotherapy started: {record.get('episode_drug_names', '')}",
                'episode_drug_names': record.get('episode_drug_names'),
                'episode_start_datetime': record.get('episode_start_datetime'),
                'episode_end_datetime': record.get('episode_end_datetime')
            })
            # End event
            if record.get('episode_end_datetime'):
                events.append({
                    'event_type': 'chemotherapy_end',
                    'event_date': record.get('episode_end_datetime', '').split()[0] if record.get('episode_end_datetime') else '',
                    'stage': 3,
                    'source': 'v_chemo_treatment_episodes',
                    'description': f"Chemotherapy ended: {record.get('episode_drug_names', '')}",
                    'episode_drug_names': record.get('episode_drug_names')
                })
            chemo_episode_count += 1
        print(f"    ✅ Added {chemo_episode_count} chemotherapy episodes")

        # Validate against expected paradigm
        expected_chemo = self.who_2021_classification.get('recommended_protocols', {}).get('chemotherapy')
        if expected_chemo:
            print(f"    📋 Expected per WHO 2021: {expected_chemo}")
            if chemo_episode_count == 0:
                print(f"    ⚠️  WARNING: No chemotherapy episodes found, but WHO 2021 recommends: {expected_chemo}")

        # STAGE 4: Radiation episodes
        print("  Stage 4: Radiation episodes")
        radiation_episode_count = 0
        for record in self.structured_data.get('radiation', []):
            # Start event
            events.append({
                'event_type': 'radiation_start',
                'event_date': record.get('episode_start_date'),
                'stage': 4,
                'source': 'v_radiation_episode_enrichment',
                'description': f"Radiation started: {record.get('total_dose_cgy', '')} cGy",
                'total_dose_cgy': record.get('total_dose_cgy'),
                'radiation_fields': record.get('radiation_fields'),
                'episode_start_date': record.get('episode_start_date'),
                'episode_end_date': record.get('episode_end_date')
            })
            # End event
            if record.get('episode_end_date'):
                events.append({
                    'event_type': 'radiation_end',
                    'event_date': record.get('episode_end_date'),
                    'stage': 4,
                    'source': 'v_radiation_episode_enrichment',
                    'description': f"Radiation completed: {record.get('total_dose_cgy', '')} cGy",
                    'total_dose_cgy': record.get('total_dose_cgy')
                })
            radiation_episode_count += 1
        print(f"    ✅ Added {radiation_episode_count} radiation episodes")

        # Validate against expected paradigm
        expected_radiation = self.who_2021_classification.get('recommended_protocols', {}).get('radiation')
        if expected_radiation:
            print(f"    📋 Expected per WHO 2021: {expected_radiation}")
            if radiation_episode_count == 0:
                print(f"    ⚠️  WARNING: No radiation episodes found, but WHO 2021 recommends: {expected_radiation}")

        # STAGE 5: Imaging studies
        print("  Stage 5: Imaging studies")
        imaging_count = 0
        for record in self.structured_data.get('imaging', []):
            events.append({
                'event_type': 'imaging',
                'event_date': record.get('imaging_date'),
                'stage': 5,
                'source': 'v_imaging',
                'description': f"{record.get('imaging_modality', '')} imaging",
                'imaging_modality': record.get('imaging_modality'),
                'report_conclusion': record.get('report_conclusion'),
                'result_diagnostic_report_id': record.get('result_diagnostic_report_id'),
                'diagnostic_report_id': record.get('diagnostic_report_id')
            })
            imaging_count += 1
        print(f"    ✅ Added {imaging_count} imaging studies")

        # STAGE 6: Add pathology/diagnosis events (already integrated in Stage 0, but keep granular records)
        print("  Stage 6: Pathology events (granular)")
        pathology_count = 0
        for record in self.structured_data.get('pathology', []):
            events.append({
                'event_type': 'pathology_record',
                'event_date': record.get('diagnostic_date'),
                'stage': 6,
                'source': 'v_pathology_diagnostics',
                'description': record.get('diagnostic_name'),
                'component_name': record.get('component_name'),
                'result_value': record.get('result_value'),
                'extraction_priority': record.get('extraction_priority'),
                'document_category': record.get('document_category')
            })
            pathology_count += 1
        print(f"    ✅ Added {pathology_count} pathology records")

        # Sort chronologically (None dates go to end)
        events.sort(key=lambda x: (x.get('event_date') is None, x.get('event_date', '')))

        # Add sequence numbers
        for i, event in enumerate(events, 1):
            event['event_sequence'] = i

        self.timeline_events = events

        print(f"\n  ✅ Timeline construction complete: {len(events)} total events across 7 stages")
        print(f"     Stage 0: 1 molecular diagnosis anchor")
        print(f"     Stage 1: {visit_count} visits")
        print(f"     Stage 2: {surgery_count} surgeries")
        print(f"     Stage 3: {chemo_episode_count} chemotherapy episodes")
        print(f"     Stage 4: {radiation_episode_count} radiation episodes")
        print(f"     Stage 5: {imaging_count} imaging studies")
        print(f"     Stage 6: {pathology_count} pathology records")

    def _phase3_identify_extraction_gaps(self):
        """Phase 3: Identify gaps in structured data requiring binary extraction"""

        gaps = []

        # Gap type 1: Surgeries without EOR
        surgery_events = [e for e in self.timeline_events if e['event_type'] == 'surgery']
        for surgery in surgery_events:
            if not surgery.get('extent_of_resection'):
                gaps.append({
                    'gap_type': 'missing_eor',
                    'priority': 'HIGH',
                    'event_date': surgery.get('event_date'),
                    'surgery_type': surgery.get('surgery_type'),
                    'recommended_action': 'Extract EOR from operative note binary',
                    'clinical_significance': 'EOR is critical for prognosis and protocol validation'
                })

        # Gap type 2: Radiation without dose
        radiation_events = [e for e in self.timeline_events if e['event_type'] == 'radiation_start']
        for radiation in radiation_events:
            if not radiation.get('total_dose_cgy'):
                gaps.append({
                    'gap_type': 'missing_radiation_dose',
                    'priority': 'HIGH',
                    'event_date': radiation.get('event_date'),
                    'recommended_action': 'Extract dose from radiation summary PDF',
                    'clinical_significance': 'Dose validation against WHO 2021 protocols impossible without this'
                })

        # Gap type 3: Imaging without clear response assessment
        imaging_events = [e for e in self.timeline_events if e['event_type'] == 'imaging']
        for imaging in imaging_events:
            conclusion = imaging.get('report_conclusion', '')
            # Vague conclusion = NULL, empty, OR <50 characters
            if not conclusion or len(conclusion) < 50:
                # Get diagnostic report ID for MedGemma extraction
                diagnostic_report_id = imaging.get('diagnostic_report_id') or imaging.get('result_diagnostic_report_id')

                gaps.append({
                    'gap_type': 'vague_imaging_conclusion',
                    'priority': 'MEDIUM',
                    'event_date': imaging.get('event_date'),
                    'imaging_modality': imaging.get('imaging_modality'),
                    'diagnostic_report_id': diagnostic_report_id,
                    'recommended_action': 'Extract full radiology report for detailed tumor measurements',
                    'clinical_significance': 'Detailed measurements needed for RANO response assessment',
                    'medgemma_target': f'DiagnosticReport/{diagnostic_report_id}' if diagnostic_report_id else 'MISSING_REFERENCE'
                })

        self.extraction_gaps = gaps

        print(f"  ✅ Identified {len(gaps)} extraction opportunities")
        gap_counts = {}
        for gap in gaps:
            gap_type = gap['gap_type']
            gap_counts[gap_type] = gap_counts.get(gap_type, 0) + 1
        for gap_type, count in sorted(gap_counts.items()):
            print(f"     {gap_type}: {count}")

    def _phase4_extract_from_binaries_placeholder(self):
        """Phase 4: PLACEHOLDER for MedGemma binary extraction"""

        print("  ⚠️  MedGemma integration not yet implemented")
        print("  ⚠️  In production, this phase would:")
        print("     1. Prioritize gaps by clinical significance + WHO 2021 context")
        print("     2. Fetch binary documents from DocumentReference")
        print("     3. Call MedGemma for structured extraction")
        print("     4. Validate and integrate extractions into timeline")
        print("     5. Re-assess for remaining gaps (iterative)")

    def _phase5_protocol_validation(self):
        """Phase 5: Validate treatments against WHO 2021 protocols"""

        validations = []

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', '')
        recommended_protocols = self.who_2021_classification.get('recommended_protocols', {})

        # Validate radiation
        radiation_events = [e for e in self.timeline_events if e['event_type'] == 'radiation_start']
        if radiation_events and recommended_protocols.get('radiation'):
            for rad_event in radiation_events:
                dose = rad_event.get('total_dose_cgy')
                if dose:
                    try:
                        dose = float(dose)
                        # Extract expected dose from protocol string (e.g., "54 Gy" → 5400 cGy)
                        expected_gy = float(recommended_protocols['radiation'].split()[0])
                        expected_cgy = expected_gy * 100

                        if abs(dose - expected_cgy) <= 200:
                            validations.append({
                                'protocol_type': 'radiation',
                                'status': 'ADHERENT',
                                'actual_dose_cgy': dose,
                                'expected_dose_cgy': expected_cgy,
                                'message': f'Dose {dose} cGy within protocol range ({expected_cgy}±200 cGy)'
                            })
                        elif dose < expected_cgy - 200:
                            validations.append({
                                'protocol_type': 'radiation',
                                'status': 'UNDERDOSED',
                                'actual_dose_cgy': dose,
                                'expected_dose_cgy': expected_cgy,
                                'message': f'Dose {dose} cGy below protocol (expected {expected_cgy} cGy)',
                                'severity': 'CRITICAL'
                            })
                        else:
                            validations.append({
                                'protocol_type': 'radiation',
                                'status': 'OVERDOSED',
                                'actual_dose_cgy': dose,
                                'expected_dose_cgy': expected_cgy,
                                'message': f'Dose {dose} cGy above protocol (expected {expected_cgy} cGy)',
                                'severity': 'WARNING'
                            })
                    except (ValueError, IndexError):
                        pass

        self.protocol_validations = validations

        print(f"  ✅ Performed {len(validations)} protocol validations")

    def _phase6_generate_artifact(self):
        """Phase 6: Generate final JSON timeline artifact"""

        artifact = {
            'patient_id': self.patient_id,
            'abstraction_timestamp': datetime.now().isoformat(),
            'who_2021_classification': self.who_2021_classification,
            'timeline_construction_metadata': {
                'structured_data_sources': {k: len(v) for k, v in self.structured_data.items()},
                'total_timeline_events': len(self.timeline_events),
                'extraction_gaps_identified': len(self.extraction_gaps),
                'binary_extractions_performed': len(self.binary_extractions),
                'protocol_validations': len(self.protocol_validations)
            },
            'timeline_events': self.timeline_events,
            'extraction_gaps': self.extraction_gaps,
            'binary_extractions': self.binary_extractions,
            'protocol_validations': self.protocol_validations
        }

        # Save to file
        safe_patient_id = self.patient_id.replace('/', '_')
        output_file = self.output_dir / f"{safe_patient_id}_timeline_artifact.json"
        with open(output_file, 'w') as f:
            json.dump(artifact, f, indent=2)

        print(f"  ✅ Artifact saved: {output_file}")

        return artifact


def main():
    parser = argparse.ArgumentParser(
        description='Patient Clinical Journey Timeline Abstraction (Corrected)'
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
        help='Output directory for timeline artifacts'
    )

    args = parser.parse_args()

    # Check AWS SSO
    if not check_aws_sso_token():
        print("\n❌ AWS SSO token invalid. Run: aws sso login --profile radiant-prod\n")
        sys.exit(1)

    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(args.output_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run abstraction
    abstractor = PatientTimelineAbstractor(args.patient_id, output_dir)
    artifact = abstractor.run()

    print()
    print("="*80)
    print("ABSTRACTION COMPLETE")
    print("="*80)
    print(f"Timeline events: {artifact['timeline_construction_metadata']['total_timeline_events']}")
    print(f"Extraction gaps: {artifact['timeline_construction_metadata']['extraction_gaps_identified']}")
    print(f"Protocol validations: {artifact['timeline_construction_metadata']['protocol_validations']}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
