#!/usr/bin/env python3
"""
Patient Clinical Journey Timeline Abstraction - VERSION 2 (WITH REAL PHASE 4)

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

# Add parent directory to path for agent imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import agents for Phase 4
try:
    from agents import MedGemmaAgent, BinaryFileAgent, ExtractionResult
    AGENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import agents: {e}")
    AGENTS_AVAILABLE = False

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


def query_athena(query: str, description: str = None, profile: str = 'radiant-prod', suppress_output: bool = False) -> List[Dict[str, Any]]:
    """Execute Athena query and return results as list of dicts"""
    if description and not suppress_output:
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
            if description and not suppress_output:
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
                if description and not suppress_output:
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

    if description and not suppress_output:
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
    5. Calls MedGemma for extraction (REAL IMPLEMENTATION IN V2)
    6. Integrates extractions into timeline
    7. Validates protocols against WHO 2021 treatment paradigms
    8. Generates final JSON artifact
    """

    def __init__(self, patient_id: str, output_dir: Path, max_extractions: Optional[int] = None):
        self.patient_id = patient_id
        self.athena_patient_id = patient_id.replace('Patient/', '')
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Max extractions limit for testing
        self.max_extractions = max_extractions

        # Load WHO 2021 classification for this patient
        self.who_2021_classification = WHO_2021_CLASSIFICATIONS.get(self.athena_patient_id, {})

        # Data structures
        self.timeline_events = []
        self.extraction_gaps = []
        self.binary_extractions = []  # MedGemma results
        self.protocol_validations = []

        # Initialize agents for Phase 4
        self.medgemma_agent = None
        self.binary_agent = None

        if AGENTS_AVAILABLE and self._verify_medgemma_available():
            try:
                self.medgemma_agent = MedGemmaAgent(model_name="gemma2:27b", temperature=0.1)
                self.binary_agent = BinaryFileAgent(aws_profile="radiant-prod")
                logger.info("✅ MedGemma and BinaryFile agents initialized")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize agents: {e}")
                self.medgemma_agent = None
                self.binary_agent = None
        else:
            logger.warning("⚠️  Phase 4 (binary extraction) will be skipped - Ollama not available")

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

        # PHASE 4: Prioritize and extract from binaries (REAL MEDGEMMA INTEGRATION)
        print("PHASE 4: PRIORITIZED BINARY EXTRACTION WITH MEDGEMMA")
        print("-"*80)
        self._phase4_extract_from_binaries()
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

        # Gap type 1: Surgeries without EOR - query v_binary_files for operative notes
        surgery_events = [e for e in self.timeline_events if e['event_type'] == 'surgery']
        for surgery in surgery_events:
            if not surgery.get('extent_of_resection'):
                # Query v_binary_files for operative notes near this surgery date
                # Use event_date if available, otherwise extract date from proc_performed_datetime
                event_date = surgery.get('event_date')
                if not event_date or event_date == '':
                    # Extract date from proc_performed_datetime (format: "YYYY-MM-DD HH:MM:SS.SSS")
                    proc_dt = surgery.get('proc_performed_datetime', '')
                    if proc_dt and proc_dt != '':
                        event_date = proc_dt.split(' ')[0]  # Get date part only

                operative_note_binary = self._find_operative_note_binary(event_date)

                gaps.append({
                    'gap_type': 'missing_eor',
                    'priority': 'HIGHEST',  # Changed to HIGHEST - EOR is critical
                    'event_date': event_date,
                    'surgery_type': surgery.get('surgery_type'),
                    'proc_performed_datetime': surgery.get('proc_performed_datetime'),
                    'recommended_action': 'Extract EOR from operative note binary',
                    'clinical_significance': 'EOR is critical for prognosis and protocol validation',
                    'medgemma_target': operative_note_binary if operative_note_binary else None
                })

        # Gap type 2: Radiation without comprehensive dose details - query v_radiation_documents
        radiation_events = [e for e in self.timeline_events if e['event_type'] == 'radiation_start']
        for radiation in radiation_events:
            # Check if we're missing ANY critical radiation fields
            missing_fields = []
            if not radiation.get('total_dose_cgy'):
                missing_fields.append('total_dose_cgy')
            if not radiation.get('radiation_fields'):
                missing_fields.append('radiation_fields')

            # Always try to extract comprehensive radiation details
            if missing_fields or True:  # Always extract for radiation to get full details
                event_date = radiation.get('event_date')
                radiation_doc = self._find_radiation_document(event_date)

                gaps.append({
                    'gap_type': 'missing_radiation_details',
                    'priority': 'HIGHEST',  # Changed to HIGHEST - radiation details critical
                    'event_date': event_date,
                    'missing_fields': missing_fields,
                    'recommended_action': 'Extract comprehensive radiation details including craniospinal/focal doses',
                    'clinical_significance': 'Complete radiation dosimetry required for WHO 2021 protocol validation',
                    'medgemma_target': radiation_doc if radiation_doc else None
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

    def _find_operative_note_binary(self, surgery_date: str) -> Optional[str]:
        """
        Query v_binary_files to find operative notes for a surgery

        Args:
            surgery_date: Date of surgery (YYYY-MM-DD)

        Returns:
            Binary ID if found, None otherwise
        """
        if not surgery_date:
            return None

        try:
            # Query v_binary_files for operative notes within ±7 days of surgery
            query = f"""
            SELECT binary_id, dr_type_text, dr_date, dr_description
            FROM fhir_prd_db.v_binary_files
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND (dr_type_text = 'Operative Record'
                   OR dr_type_text = 'External Operative Note')
              AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE))) <= 7
            ORDER BY ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE)))
            LIMIT 1
            """

            results = query_athena(query, f"Finding operative note for surgery on {surgery_date}", suppress_output=True)

            if results:
                binary_id = results[0].get('binary_id')
                logger.info(f"Found operative note Binary/{binary_id} for surgery on {surgery_date}")
                return f"Binary/{binary_id}"
            else:
                logger.debug(f"No operative note found for surgery on {surgery_date}")
                return None

        except Exception as e:
            logger.error(f"Error querying operative notes for {surgery_date}: {e}")
            return None

    def _find_radiation_document(self, radiation_date: str) -> Optional[str]:
        """
        Query v_radiation_documents for radiation treatment documents

        NOTE: v_radiation_documents may include some false positives (e.g., ED visits mentioning
        radiation history), but we rely on:
        1. Document content validation (keyword checking) before extraction
        2. MedGemma's ability to recognize wrong document types
        3. Escalating search to alternative documents if primary fails validation

        This is the CORRECT approach - try v_radiation_documents first, then escalate if needed.

        Args:
            radiation_date: Date of radiation start (YYYY-MM-DD)

        Returns:
            DocumentReference ID if found, None otherwise
        """
        if not radiation_date:
            return None

        try:
            # Query v_radiation_documents for documents near radiation start
            query = f"""
            SELECT document_id, doc_type_text, doc_date, doc_description
            FROM fhir_prd_db.v_radiation_documents
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 30
            ORDER BY ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE)))
            LIMIT 1
            """

            results = query_athena(query, f"Finding radiation document for {radiation_date}", suppress_output=True)

            if results:
                doc_id = results[0].get('document_id')
                logger.info(f"Found radiation document {doc_id} for radiation on {radiation_date}")
                return f"DocumentReference/{doc_id}"
            else:
                logger.debug(f"No radiation document found for {radiation_date}")
                return None

        except Exception as e:
            logger.error(f"Error querying radiation documents for {radiation_date}: {e}")
            return None

    def _build_patient_document_inventory(self) -> Dict:
        """
        Build comprehensive inventory of ALL available documents for this patient
        Allows agent to make informed prioritization decisions based on what's actually available

        Returns:
            Dictionary with document types as keys and lists of documents as values
        """
        try:
            query = f"""
            SELECT
                binary_id,
                dr_type_text,
                dr_date,
                dr_description,
                content_type
            FROM fhir_prd_db.v_binary_files
            WHERE patient_fhir_id = '{self.athena_patient_id}'
            ORDER BY dr_date DESC
            """
            results = query_athena(query, f"Building document inventory for patient", suppress_output=True)

            inventory = {
                'operative_records': [],
                'discharge_summaries': [],
                'progress_notes': [],
                'imaging_reports': [],
                'pathology_reports': [],
                'consultation_notes': [],
                'radiation_documents': [],
                'treatment_plans': [],
                'other': []
            }

            for doc in results:
                doc_type = doc.get('dr_type_text', '').lower()

                if 'operative' in doc_type or 'op note' in doc_type:
                    inventory['operative_records'].append(doc)
                elif 'discharge' in doc_type:
                    inventory['discharge_summaries'].append(doc)
                elif 'progress' in doc_type:
                    inventory['progress_notes'].append(doc)
                elif 'imaging' in doc_type or 'radiology' in doc_type or 'diagnostic imaging' in doc_type:
                    inventory['imaging_reports'].append(doc)
                elif 'pathology' in doc_type:
                    inventory['pathology_reports'].append(doc)
                elif 'consultation' in doc_type or 'consult' in doc_type:
                    inventory['consultation_notes'].append(doc)
                elif 'rad onc' in doc_type or 'radiation' in doc_type:
                    inventory['radiation_documents'].append(doc)
                elif 'treatment plan' in doc_type:
                    inventory['treatment_plans'].append(doc)
                else:
                    inventory['other'].append(doc)

            logger.info(f"Document inventory: {sum(len(v) for v in inventory.values())} total documents")
            for key, docs in inventory.items():
                if docs:
                    logger.info(f"  {key}: {len(docs)} documents")

            return inventory

        except Exception as e:
            logger.error(f"Error building document inventory: {e}")
            return {}

    def _find_alternative_documents(self, gap: Dict, inventory: Dict) -> List[Dict]:
        """
        Find alternative documents based on gap type and patient-specific availability
        Returns prioritized list of candidate documents

        Args:
            gap: Extraction gap dictionary
            inventory: Patient document inventory from _build_patient_document_inventory()

        Returns:
            List of candidate documents sorted by priority and temporal proximity
        """
        gap_type = gap['gap_type']
        event_date = gap.get('event_date')
        candidates = []

        if gap_type == 'missing_eor':
            # TEMPORAL + TYPE APPROACH: No keyword filtering for surgery gaps

            # Priority 1: Operative records (ALL - temporal filtering will narrow)
            operative_records = inventory.get('operative_records', [])
            print(f"       🔍 Priority 1: Adding ALL {len(operative_records)} operative_records (no keyword filter)")
            for doc in operative_records:
                candidates.append({
                    'priority': 1,
                    'source_type': 'operative_record',
                    **doc
                })

            # Priority 2: Discharge summaries (ALL - temporal filtering will narrow)
            discharge_summaries = inventory.get('discharge_summaries', [])
            print(f"       🔍 Priority 2: Adding ALL {len(discharge_summaries)} discharge_summaries (no keyword filter)")
            for doc in discharge_summaries:
                candidates.append({
                    'priority': 2,
                    'source_type': 'discharge_summary',
                    **doc
                })

            # Priority 3: Progress notes (ALL - temporal filtering will narrow)
            progress_notes = inventory.get('progress_notes', [])
            print(f"       🔍 Priority 3: Adding ALL {len(progress_notes)} progress_notes (no keyword filter)")
            for doc in progress_notes:
                candidates.append({
                    'priority': 3,
                    'source_type': 'progress_note',
                    **doc
                })

            # Priority 4: Post-op imaging reports (ALL - temporal filtering will narrow)
            imaging_reports = inventory.get('imaging_reports', [])
            print(f"       🔍 Priority 4: Adding ALL {len(imaging_reports)} imaging_reports (no keyword filter)")
            for doc in imaging_reports:
                candidates.append({
                    'priority': 4,
                    'source_type': 'postop_imaging',
                    **doc
                })

            print(f"       📊 Total {len(candidates)} candidates before temporal filtering")

        elif gap_type == 'missing_radiation_details':
            # TEMPORAL + TYPE APPROACH: No keyword filtering - rely on document type + date proximity
            # Rationale: dr_description often NULL/empty; progress notes near radiation WILL mention it

            # Priority 1: Radiation-specific documents (ALL within temporal window)
            rad_docs = inventory.get('radiation_documents', [])
            print(f"       🔍 Priority 1: Adding ALL {len(rad_docs)} radiation_documents (no keyword filter)")
            for doc in rad_docs:
                candidates.append({
                    'priority': 1,
                    'source_type': 'radiation_document',
                    **doc
                })

            # Priority 2: Progress notes (ALL - temporal filtering will narrow down)
            progress_notes = inventory.get('progress_notes', [])
            print(f"       🔍 Priority 2: Adding ALL {len(progress_notes)} progress_notes (no keyword filter)")
            for doc in progress_notes:
                candidates.append({
                    'priority': 2,
                    'source_type': 'progress_note',
                    **doc
                })

            # Priority 3: Discharge summaries (ALL - temporal filtering will narrow down)
            discharge_summaries = inventory.get('discharge_summaries', [])
            print(f"       🔍 Priority 3: Adding ALL {len(discharge_summaries)} discharge_summaries (no keyword filter)")
            for doc in discharge_summaries:
                candidates.append({
                    'priority': 3,
                    'source_type': 'discharge_summary',
                    **doc
                })

            # Priority 4: Treatment plans (ALL - temporal filtering will narrow down)
            treatment_plans = inventory.get('treatment_plans', [])
            print(f"       🔍 Priority 4: Adding ALL {len(treatment_plans)} treatment_plans (no keyword filter)")
            for doc in treatment_plans:
                candidates.append({
                    'priority': 4,
                    'source_type': 'treatment_plan',
                    **doc
                })

            print(f"       📊 Total {len(candidates)} candidates before temporal filtering")

        elif gap_type == 'vague_imaging_conclusion':
            # For imaging, primary is already the imaging report
            # Look for clinical notes interpreting the imaging
            for doc in inventory.get('progress_notes', []):
                desc = doc.get('dr_description', '').lower()
                if any(kw in desc for kw in ['mri', 'imaging', 'scan', 'tumor']):
                    candidates.append({
                        'priority': 2,
                        'source_type': 'progress_note',
                        **doc
                    })

        # Calculate temporal distance from event
        if event_date:
            from dateutil.parser import parse
            event_dt = parse(event_date)
            for candidate in candidates:
                if candidate.get('dr_date'):
                    try:
                        doc_dt = parse(candidate['dr_date'])
                        days_diff = abs((doc_dt - event_dt).days)
                        candidate['days_from_event'] = days_diff
                    except:
                        candidate['days_from_event'] = 9999
                else:
                    candidate['days_from_event'] = 9999

        # Sort by priority, then temporal proximity
        candidates.sort(key=lambda x: (x.get('priority', 99), x.get('days_from_event', 9999)))

        return candidates

    def _try_alternative_documents(self, gap: Dict, missing_fields: List[str]) -> bool:
        """
        Try extracting from alternative documents when primary document fails

        Returns True if extraction successful from an alternative, False if all exhausted
        """
        # Build document inventory if not already done
        if not hasattr(self, '_document_inventory'):
            print(f"       📋 Building patient document inventory...")
            self._document_inventory = self._build_patient_document_inventory()

        # Find alternative candidates
        candidates = self._find_alternative_documents(gap, self._document_inventory)

        if not candidates:
            print(f"       ⚠️  No alternative documents available for {gap['gap_type']}")
            print(f"       📊 Inventory summary:")
            for key, docs in self._document_inventory.items():
                if docs:
                    print(f"          {key}: {len(docs)} documents")
            return False

        print(f"       📄 Found {len(candidates)} alternative document(s) to try")

        # Try each alternative
        max_alternatives = 5  # Limit to prevent infinite loops
        for i, candidate in enumerate(candidates[:max_alternatives]):
            print(f"       [{i+1}/{min(len(candidates), max_alternatives)}] Trying {candidate['source_type']} from {candidate.get('dr_date', 'unknown date')} ({candidate.get('days_from_event', '?')} days from event)")

            # Fetch alternative document
            binary_id = candidate.get('binary_id')
            if not binary_id:
                print(f"          ⚠️  No binary_id for this document")
                continue

            alt_text = self._fetch_binary_document(f"Binary/{binary_id}")
            if not alt_text:
                print(f"          ⚠️  Could not fetch document")
                continue

            print(f"          ✅ Fetched document ({len(alt_text)} chars)")

            # Validate alternative document content
            is_valid, reason = self._validate_document_content(alt_text, gap['gap_type'])
            if not is_valid:
                print(f"          ⚠️  Validation failed: {reason}")
                continue

            print(f"          ✅ Document validated: {reason}")

            # Generate prompt
            prompt = self._generate_medgemma_prompt(gap)
            full_prompt = f"{prompt}\n\nDOCUMENT TEXT:\n{alt_text}"

            # Extract from alternative
            try:
                result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

                if not result.success:
                    print(f"          ❌ Extraction failed: {result.error}")
                    continue

                # Validate extraction
                is_valid_result, still_missing = self._validate_extraction_result(result.extracted_data, gap['gap_type'])

                if is_valid_result:
                    print(f"          ✅ SUCCESSFUL extraction from alternative document!")
                    # Integrate into timeline
                    self._integrate_extraction_into_timeline(gap, result.extracted_data)
                    gap['status'] = 'RESOLVED'
                    gap['extraction_result'] = result.extracted_data
                    gap['extraction_source'] = candidate['source_type']
                    gap['extraction_document_date'] = candidate.get('dr_date')

                    self.binary_extractions.append({
                        'gap': gap,
                        'extraction_result': result.extracted_data,
                        'extraction_confidence': result.extracted_data.get('extraction_confidence', 'UNKNOWN'),
                        'source': 'alternative_document',
                        'source_type': candidate['source_type']
                    })

                    return True
                else:
                    print(f"          ⚠️  Still missing fields: {still_missing}")
                    # Continue to next alternative

            except Exception as e:
                print(f"          ❌ Extraction error: {e}")
                continue

        # All alternatives exhausted
        print(f"       ❌ Exhausted {min(len(candidates), max_alternatives)} alternative documents")
        gap['status'] = 'UNAVAILABLE_IN_RECORDS'
        return False

    def _verify_medgemma_available(self) -> bool:
        """Verify Ollama is running and gemma2:27b is available"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if "gemma2:27b" in model_names:
                logger.info("✅ MedGemma (gemma2:27b) is available via Ollama")
                return True
            else:
                logger.warning(f"⚠️  gemma2:27b not found. Available: {model_names}")
                logger.warning("Pull with: ollama pull gemma2:27b")
                return False
        except Exception as e:
            logger.warning(f"⚠️  Ollama not accessible: {e}")
            logger.warning("Start Ollama with: ollama serve")
            return False

    def _phase4_extract_from_binaries_placeholder(self):
        """Phase 4: PLACEHOLDER for MedGemma binary extraction"""

        print("  ⚠️  MedGemma integration not yet implemented")
        print("  ⚠️  In production, this phase would:")
        print("     1. Prioritize gaps by clinical significance + WHO 2021 context")
        print("     2. Fetch binary documents from DocumentReference")
        print("     3. Call MedGemma for structured extraction")
        print("     4. Validate and integrate extractions into timeline")
        print("     5. Re-assess for remaining gaps (iterative)")

    def _phase4_extract_from_binaries(self):
        """
        Phase 4: Real MedGemma extraction from binary documents
        """

        if not self.medgemma_agent or not self.binary_agent:
            print("  ⚠️  Ollama/MedGemma not available - skipping binary extraction")
            return

        # Prioritize gaps (HIGHEST → HIGH → MEDIUM)
        priority_map = {'HIGHEST': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        prioritized_gaps = sorted(
            self.extraction_gaps,
            key=lambda x: priority_map.get(x.get('priority', 'LOW'), 4)
        )

        # Apply max_extractions limit if set
        if self.max_extractions:
            prioritized_gaps = prioritized_gaps[:self.max_extractions]
            print(f"  ⚠️  Limiting to {self.max_extractions} extraction(s) for testing")

        print(f"  Extracting from {len(prioritized_gaps)} documents using MedGemma...")

        extracted_count = 0
        failed_count = 0

        for i, gap in enumerate(prioritized_gaps, 1):
            print(f"\n  [{i}/{len(prioritized_gaps)}] Processing {gap['gap_type']} (priority: {gap.get('priority')})")

            # STEP 1: Generate context-aware prompt
            try:
                prompt = self._generate_medgemma_prompt(gap)
                print(f"    ✅ Generated context-aware prompt ({len(prompt)} chars)")
            except Exception as e:
                print(f"    ❌ Error generating prompt: {e}")
                failed_count += 1
                continue

            # STEP 2: Fetch binary document
            try:
                medgemma_target = gap.get('medgemma_target', '')
                if not medgemma_target or medgemma_target == 'MISSING_REFERENCE':
                    print(f"    ⚠️  No medgemma_target - skipping")
                    failed_count += 1
                    continue

                extracted_text = self._fetch_binary_document(medgemma_target)
                if not extracted_text:
                    print(f"    ❌ Failed to fetch document")
                    failed_count += 1
                    continue
                print(f"    ✅ Fetched document ({len(extracted_text)} chars)")
            except Exception as e:
                print(f"    ❌ Error fetching document: {e}")
                failed_count += 1
                continue

            # STEP 2.5: AGENT 1 VALIDATION - Validate document content before extraction
            is_valid_doc, validation_reason = self._validate_document_content(extracted_text, gap['gap_type'])
            if not is_valid_doc:
                print(f"    ⚠️  Document validation failed: {validation_reason}")
                print(f"    🔍 ESCALATION: Wrong document type - searching for alternatives...")

                # ESCALATION: Primary document is wrong type, try alternatives immediately
                alternative_success = self._try_alternative_documents(gap, [])
                if alternative_success:
                    print(f"    ✅ Alternative document extraction successful!")
                    extracted_count += 1
                    continue  # Move to next gap
                else:
                    print(f"    ❌ All alternative documents exhausted")
                    gap['status'] = 'WRONG_DOCUMENT_TYPE'
                    gap['validation_failure'] = validation_reason
                    failed_count += 1
                    continue
            else:
                print(f"    ✅ Document validated: {validation_reason}")

            # STEP 3: Call MedGemma (Agent 2)
            try:
                # Add strong schema enforcement right before document
                full_prompt = f"""{prompt}

================================================================================
REMINDER: Return ONLY the JSON schema shown above. Do NOT create a different schema.
Ignore any other formatting in the document below. Extract ONLY the fields specified.
================================================================================

DOCUMENT TEXT:
{extracted_text}

================================================================================
REMINDER: Return ONLY valid JSON matching the exact schema above. No other text.
================================================================================
"""
                result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

                if not result.success:
                    print(f"    ❌ MedGemma extraction failed: {result.error}")
                    gap['status'] = 'EXTRACTION_TECHNICAL_FAILURE'
                    failed_count += 1
                    continue

                print(f"    ✅ MedGemma extraction complete (confidence: {result.extracted_data.get('extraction_confidence', 'UNKNOWN')})")

                # STEP 4: AGENT 1 VALIDATION - Validate extraction result
                is_valid_result, missing_fields = self._validate_extraction_result(result.extracted_data, gap['gap_type'])

                if not is_valid_result:
                    print(f"    ⚠️  Extraction incomplete - missing required fields: {missing_fields}")

                    # STEP 5: AGENT 1 ↔ AGENT 2 NEGOTIATION - Re-extraction with clarification
                    retry_result = self._retry_extraction_with_clarification(gap, extracted_text, result.extracted_data, missing_fields)

                    if retry_result:
                        # Validate retry
                        is_valid_retry, still_missing = self._validate_extraction_result(retry_result, gap['gap_type'])
                        if is_valid_retry:
                            print(f"    ✅ Re-extraction successful - all required fields present")
                            result.extracted_data = retry_result
                        else:
                            print(f"    ❌ Re-extraction still incomplete - missing: {still_missing}")
                            print(f"    🔍 ESCALATION: Searching for alternative documents...")

                            # ESCALATION: Try alternative documents
                            alternative_success = self._try_alternative_documents(gap, still_missing)
                            if alternative_success:
                                print(f"    ✅ Alternative document extraction successful!")
                                extracted_count += 1
                                continue  # Move to next gap
                            else:
                                print(f"    ❌ All alternative documents exhausted")
                                gap['status'] = 'INCOMPLETE_EXTRACTION'
                                gap['missing_fields'] = still_missing
                                gap['extraction_result'] = retry_result
                                failed_count += 1
                                continue
                    else:
                        print(f"    ❌ Re-extraction failed")
                        print(f"    🔍 ESCALATION: Searching for alternative documents...")

                        # ESCALATION: Try alternative documents
                        alternative_success = self._try_alternative_documents(gap, missing_fields)
                        if alternative_success:
                            print(f"    ✅ Alternative document extraction successful!")
                            extracted_count += 1
                            continue  # Move to next gap
                        else:
                            print(f"    ❌ All alternative documents exhausted")
                            gap['status'] = 'RE_EXTRACTION_FAILED'
                            gap['missing_fields'] = missing_fields
                            failed_count += 1
                            continue

                # STEP 6: Success - all validations passed
                print(f"    ✅ Extraction SUCCESSFUL - all required fields present")
                self._integrate_extraction_into_timeline(gap, result.extracted_data)
                gap['status'] = 'RESOLVED'
                gap['extraction_result'] = result.extracted_data
                self.binary_extractions.append({
                    'gap': gap,
                    'extraction_result': result.extracted_data,
                    'extraction_confidence': result.extracted_data.get('extraction_confidence', 'UNKNOWN')
                })
                extracted_count += 1

            except Exception as e:
                print(f"    ❌ MedGemma error: {e}")
                gap['status'] = 'EXTRACTION_ERROR'
                gap['error'] = str(e)
                failed_count += 1

        print(f"\n  ✅ Extracted from {extracted_count} documents")
        print(f"  ❌ {failed_count} failed or require manual review")

    def _generate_medgemma_prompt(self, gap: Dict) -> str:
        """Route to specialized prompt generator based on gap type"""
        gap_type = gap.get('gap_type')

        if gap_type == 'vague_imaging_conclusion':
            return self._generate_imaging_prompt(gap)
        elif gap_type == 'missing_eor':
            return self._generate_operative_note_prompt(gap)
        elif gap_type in ['missing_radiation_dose', 'missing_radiation_details']:
            return self._generate_radiation_summary_prompt(gap)
        else:
            # Default generic prompt
            return self._generate_generic_prompt(gap)

    def _generate_imaging_prompt(self, gap: Dict) -> str:
        """Generate context-aware prompt for imaging report extraction"""

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
        molecular_subtype = self.who_2021_classification.get('molecular_subtype', '')

        prompt = f"""CRITICAL: You MUST return ONLY valid JSON in the exact schema specified below. Do NOT include any explanatory text or narrative summaries. ONLY return the JSON object.

You are a medical AI extracting structured data from a radiology report.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Molecular Subtype: {molecular_subtype}
- Imaging Date: {gap.get('event_date')}
- Imaging Modality: {gap.get('imaging_modality')}

TASK:
Extract structured tumor measurements and response assessment from this radiology report.

OUTPUT FORMAT (JSON):
{{
  "lesions": [
    {{
      "location": "anatomic location",
      "current_dimensions_cm": {{"ap": <float or null>, "ml": <float or null>, "si": <float or null>}},
      "prior_dimensions_cm": {{"ap": <float or null>, "ml": <float or null>, "si": <float or null>}} or null,
      "percent_change": <float or null>,
      "enhancement_pattern": "description"
    }}
  ],
  "rano_assessment": {{
    "new_lesions": "yes" or "no" or "unclear",
    "rano_category": "CR" or "PR" or "SD" or "PD" or "INDETERMINATE"
  }},
  "radiologist_impression": "verbatim impression/conclusion",
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

FIELD-SPECIFIC INSTRUCTIONS:
1. **lesions**: Array of tumor lesions with measurements. Use empty array [] if:
   - No tumor present (complete response)
   - Report states "no measurable disease"
   - Measurements not provided

2. **location**: Anatomic location (e.g., "right frontal lobe", "left temporal region", "cerebellar vermis")

3. **current_dimensions_cm**: Tumor dimensions in centimeters
   - ap = anterior-posterior diameter
   - ml = medial-lateral diameter
   - si = superior-inferior diameter
   - Extract bidimensional measurements (two perpendicular diameters)
   - Use null for dimensions not reported

4. **prior_dimensions_cm**: Previous scan measurements if mentioned for comparison
   - Use null if no prior mentioned or if this is baseline scan

5. **percent_change**: Percentage change from prior scan
   - Calculate if current and prior both available: ((current - prior) / prior) × 100
   - Use null if cannot calculate

6. **enhancement_pattern**: Description of contrast enhancement (e.g., "ring-enhancing", "heterogeneous enhancement", "no enhancement")

7. **new_lesions**:
   - "yes" = new lesions identified
   - "no" = no new lesions
   - "unclear" = not mentioned

8. **rano_category**: Response Assessment in Neuro-Oncology criteria
   - "CR" (Complete Response) = disappearance of all enhancing tumor
   - "PR" (Partial Response) = ≥50% decrease in enhancing tumor
   - "SD" (Stable Disease) = does not qualify for CR, PR, or PD
   - "PD" (Progressive Disease) = ≥25% increase in enhancing tumor OR new lesions
   - "INDETERMINATE" = cannot determine or report doesn't assess response

HANDLING AMBIGUOUS LANGUAGE:
- "Stable compared to prior" → rano_category: "SD", extract prior measurements if given
- "Slight interval increase" → May be SD or PD depending on percentage (check if ≥25%)
- "Decreased size" → Calculate percent_change if possible; if ≥50% → PR, else SD
- "No significant change" → rano_category: "SD"
- "No evidence of tumor" → rano_category: "CR", lesions: []

EXTRACTION CONFIDENCE CRITERIA:
- HIGH: Explicit measurements provided, clear RANO category stated or easily inferred
- MEDIUM: Qualitative descriptions only ("stable", "decreased") without exact measurements
- LOW: Minimal description or conflicting information

EXAMPLES:
Example 1 - Measurable disease:
  Document: "Right frontal ring-enhancing lesion measures 2.3 x 1.8 cm, previously 3.1 x 2.4 cm. Decreased size consistent with partial response."
  Output: {{
    "lesions": [{{
      "location": "right frontal lobe",
      "current_dimensions_cm": {{"ap": 2.3, "ml": 1.8, "si": null}},
      "prior_dimensions_cm": {{"ap": 3.1, "ml": 2.4, "si": null}},
      "percent_change": -25.8,
      "enhancement_pattern": "ring-enhancing"
    }}],
    "rano_assessment": {{
      "new_lesions": "no",
      "rano_category": "SD"
    }},
    "extraction_confidence": "HIGH"
  }}

Example 2 - Complete response:
  Document: "No evidence of enhancing tumor. Post-surgical changes in right frontal region."
  Output: {{
    "lesions": [],
    "rano_assessment": {{
      "new_lesions": "no",
      "rano_category": "CR"
    }},
    "extraction_confidence": "HIGH"
  }}

CRITICAL VALIDATION:
- lesions and rano_assessment are REQUIRED fields (cannot be null)
- lesions can be empty array [] but cannot be null
- radiologist_impression should contain verbatim conclusion text
"""

        return prompt

    def _generate_operative_note_prompt(self, gap: Dict) -> str:
        """Generate prompt for extent of resection extraction"""

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')

        prompt = f"""CRITICAL: You MUST return ONLY valid JSON in the exact schema specified below. Do NOT include any explanatory text or clinical note formatting. ONLY return the JSON object.

You are a medical AI extracting extent of resection from an operative note.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Surgery Date: {gap.get('event_date')}
- Surgery Type: {gap.get('surgery_type')}

TASK:
Extract the extent of resection (EOR) from this operative note.

OUTPUT FORMAT - RETURN ONLY THIS JSON SCHEMA (no other text):
{{
  "extent_of_resection": "GTR" or "NTR" or "STR" or "BIOPSY" or "UNCLEAR",
  "percent_resection": <integer 0-100> or null,
  "surgeon_assessment": "verbatim surgeon's description of resection",
  "residual_tumor": "yes" or "no" or "unclear",
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

FIELD-SPECIFIC INSTRUCTIONS:
1. **extent_of_resection**: Categorize using these definitions:
   - "GTR" (Gross Total Resection) = >95% tumor removed, no visible residual on imaging or surgeon assessment
   - "NTR" (Near Total Resection) = 90-95% removed, minimal residual
   - "STR" (Subtotal Resection) = <90% removed, significant residual
   - "BIOPSY" = Biopsy only, no resection performed
   - "UNCLEAR" = Cannot determine from operative note

2. **percent_resection**: Extract if surgeon specifies percentage (e.g., "approximately 85% resection"). Use null if not mentioned.

3. **surgeon_assessment**: Extract the surgeon's EXACT words describing the resection. Look for phrases in the "Procedure Description" or "Impression" sections.

4. **residual_tumor**: Based on surgeon's assessment or postoperative imaging description:
   - "yes" = surgeon mentions residual tumor or visible tumor remaining
   - "no" = surgeon states gross total resection or no visible residual
   - "unclear" = not mentioned or ambiguous

INTERPRETATION GUIDE FOR AMBIGUOUS LANGUAGE:
- "Complete resection" → GTR
- "Gross total resection" → GTR
- "Near-complete resection" → NTR
- "Near-total resection" → NTR
- "Maximal safe resection" → Check for percentage; if >95% → GTR, if 90-95% → NTR, if <90% → STR
- "Subtotal resection" → STR
- "Partial resection" → STR
- "Debulking" → STR
- "Biopsy only" → BIOPSY

EXTRACTION CONFIDENCE CRITERIA:
- HIGH: Surgeon explicitly states EOR category or percentage
- MEDIUM: EOR inferred from descriptive language (e.g., "complete resection of visible tumor")
- LOW: Minimal description or conflicting information

EXAMPLES:
Example 1:
  Document: "Gross total resection achieved. No visible residual tumor. Estimate >95% removed."
  Output: {{
    "extent_of_resection": "GTR",
    "percent_resection": 95,
    "surgeon_assessment": "Gross total resection achieved. No visible residual tumor. Estimate >95% removed.",
    "residual_tumor": "no",
    "extraction_confidence": "HIGH"
  }}

Example 2:
  Document: "Maximal safe resection performed. Small amount of tumor left on eloquent cortex. Approximately 85% resection."
  Output: {{
    "extent_of_resection": "STR",
    "percent_resection": 85,
    "surgeon_assessment": "Maximal safe resection performed. Small amount of tumor left on eloquent cortex. Approximately 85% resection.",
    "residual_tumor": "yes",
    "extraction_confidence": "HIGH"
  }}

CRITICAL VALIDATION:
- extent_of_resection is REQUIRED (cannot be null)
- If truly unclear, use "UNCLEAR" but set extraction_confidence to "LOW"
- surgeon_assessment should contain verbatim text (REQUIRED field for validation)
"""

        return prompt

    def _generate_radiation_summary_prompt(self, gap: Dict) -> str:
        """Generate prompt for comprehensive radiation details extraction"""

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
        expected_radiation = self.who_2021_classification.get('recommended_protocols', {}).get('radiation', 'Unknown')

        prompt = f"""CRITICAL: You MUST return ONLY valid JSON in the exact schema specified below. Do NOT include any explanatory text, narrative summaries, or clinical note formatting. ONLY return the JSON object.

You are a medical AI extracting COMPREHENSIVE radiation treatment details from a radiation summary.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Expected Radiation per WHO 2021: {expected_radiation}
- Radiation Start Date: {gap.get('event_date')}

TASK:
Extract ALL radiation treatment details from this document, including dates, doses, fields, and any additional treatments.

OUTPUT FORMAT - RETURN ONLY THIS JSON SCHEMA (no other text):
{{
  "date_at_radiation_start": "YYYY-MM-DD",
  "date_at_radiation_stop": "YYYY-MM-DD",
  "completed_craniospinal_or_whole_ventricular_radiation_dose": <integer in cGy or null>,
  "completed_craniospinal_or_whole_ventricular_radiation_dose_unit": "cGy",
  "radiation_focal_or_boost_dose": <integer in cGy or null>,
  "completed_radiation_focal_or_boost_dose_unit": "cGy",
  "radiation_type": "focal" or "craniospinal" or "whole_ventricular" or "focal_with_boost" or "other",
  "any_other_radiation_treatments_not_captured": "description of any additional treatments or null",
  "total_dose_cgy": <integer>,
  "fractions": <integer>,
  "dose_per_fraction_cgy": <integer>,
  "radiation_fields": "description of all radiation fields",
  "target_volumes": ["list of all target volumes"],
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

FIELD-SPECIFIC INSTRUCTIONS:
1. **date_at_radiation_start**: First day of radiation treatment (format: YYYY-MM-DD, e.g., "2024-03-15")
2. **date_at_radiation_stop**: Last day of radiation treatment (format: YYYY-MM-DD)
3. **total_dose_cgy**: TOTAL cumulative radiation dose delivered in centiGray (cGy). Convert from Gy if needed: 54 Gy = 5400 cGy
4. **fractions**: Total number of radiation fractions/sessions
5. **dose_per_fraction_cgy**: Dose delivered per fraction in cGy (e.g., 180 cGy per fraction)
6. **radiation_type**:
   - "focal" = radiation to tumor bed only
   - "craniospinal" = radiation to entire brain and spine
   - "whole_ventricular" = radiation to entire ventricular system
   - "focal_with_boost" = craniospinal/whole ventricular followed by focal boost
   - "other" = any other pattern
7. **completed_craniospinal_or_whole_ventricular_radiation_dose**: If patient received craniospinal OR whole ventricular radiation, extract the dose here (in cGy). Use null if patient received focal-only radiation.
8. **radiation_focal_or_boost_dose**: If patient received focal or boost radiation, extract the dose here (in cGy). Use null if patient received craniospinal-only without boost.

UNIT CONVERSION RULES:
- 1 Gy = 100 cGy
- Example: "54 Gy in 30 fractions" = total_dose_cgy: 5400, fractions: 30, dose_per_fraction_cgy: 180

COMMON SCENARIOS - REAL EXAMPLES FROM RADIANT PCA:
Example 1 - Focal Proton Therapy Only (High-Grade Glioma):
  Document: "Patient received proton beam therapy to tumor bed. Total dose 59.4 Gy delivered in 33 fractions (1.8 Gy per fraction) from 04/18/2018 to 06/08/2018. Target: Right frontal tumor bed."
  Output: {{
    "date_at_radiation_start": "2018-04-18",
    "date_at_radiation_stop": "2018-06-08",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
    "radiation_focal_or_boost_dose": 5940,
    "radiation_type": "focal",
    "total_dose_cgy": 5940,
    "fractions": 33,
    "dose_per_fraction_cgy": 180,
    "radiation_fields": "tumor bed",
    "any_other_radiation_treatments_not_captured": null
  }}

Example 2 - CRITICAL: Craniospinal + Focal Boost (High-Risk Medulloblastoma):
  Document: "Proton therapy delivered per ACNS0126 protocol. Craniospinal irradiation to 23.4 Gy in 13 fractions (1.8 Gy/fx), completed 05/15/2023. Followed by posterior fossa boost to bring total posterior fossa dose to 54 Gy (additional 30.6 Gy in 17 fractions). Final treatment 06/02/2023."
  Output: {{
    "date_at_radiation_start": "2023-04-25",
    "date_at_radiation_stop": "2023-06-02",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": 2340,
    "radiation_focal_or_boost_dose": 5400,
    "radiation_type": "focal_with_boost",
    "total_dose_cgy": 5400,
    "fractions": 30,
    "dose_per_fraction_cgy": 180,
    "radiation_fields": "craniospinal axis and posterior fossa",
    "target_volumes": ["craniospinal axis", "posterior fossa"],
    "any_other_radiation_treatments_not_captured": "Sequential craniospinal irradiation (2340 cGy) followed by posterior fossa boost (3060 cGy additional) to total 5400 cGy per ACNS0126 protocol"
  }}

CRITICAL NOTE FOR CRANIOSPINAL + BOOST:
- completed_craniospinal_or_whole_ventricular_radiation_dose = dose to brain/spine only (e.g., 2340 cGy)
- radiation_focal_or_boost_dose = CUMULATIVE dose to tumor bed (e.g., 5400 cGy)
- Tumor bed receives: craniospinal dose + boost dose
- Example: 2340 cGy (CSI) + 3060 cGy (boost) = 5400 cGy total to posterior fossa

Example 3 - Standard Focal Photon Therapy:
  Document: "External beam radiation therapy 54 Gy in 30 fractions to left temporal lesion, treatment dates 02/10/2019 to 03/28/2019."
  Output: {{
    "date_at_radiation_start": "2019-02-10",
    "date_at_radiation_stop": "2019-03-28",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
    "radiation_focal_or_boost_dose": 5400,
    "radiation_type": "focal",
    "total_dose_cgy": 5400,
    "fractions": 30
  }}

EXTRACTION CONFIDENCE CRITERIA:
- HIGH: All dates and doses explicitly stated, no ambiguity
- MEDIUM: Most fields present but some require inference (e.g., stop date calculated from start + duration)
- LOW: Missing critical fields (e.g., no stop date, unclear total dose) or document quality poor

CRITICAL VALIDATION:
- total_dose_cgy is REQUIRED (cannot be null)
- date_at_radiation_start is REQUIRED (cannot be null)
- If you cannot find these fields, set extraction_confidence to "LOW" and provide your best estimate
- Use null only for truly absent information, not for information you're uncertain about
"""

        return prompt

    def _generate_generic_prompt(self, gap: Dict) -> str:
        """Generate generic extraction prompt"""

        prompt = f"""You are a medical AI extracting information from a clinical document.

GAP TYPE: {gap.get('gap_type')}
CLINICAL SIGNIFICANCE: {gap.get('clinical_significance')}

TASK:
Extract relevant structured information from this document.

OUTPUT FORMAT (JSON):
{{
  "extracted_data": {{}},
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}
"""

        return prompt

    def _fetch_binary_document(self, fhir_target: str) -> Optional[str]:
        """
        Fetch binary document from S3 and extract text

        CORRECT APPROACH (following MVP workflow):
        1. Query v_binary_files to find Binary IDs for DiagnosticReport or DocumentReference
        2. Fetch the Binary from S3 using BinaryFileAgent

        Args:
            fhir_target: FHIR target like "DiagnosticReport/12345" or "DocumentReference/abc" or "Binary/xyz"

        Returns:
            Extracted text or None
        """
        # Extract resource type and ID from FHIR target
        if '/' not in fhir_target:
            logger.warning(f"Invalid FHIR target format: {fhir_target}")
            return None

        resource_type, resource_id = fhir_target.split('/', 1)

        # For DiagnosticReport or DocumentReference, query v_binary_files to find associated Binary
        if resource_type in ['DiagnosticReport', 'DocumentReference']:
            try:
                # Query v_binary_files for this document reference
                query = f"""
                SELECT binary_id, content_type
                FROM fhir_prd_db.v_binary_files
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                  AND document_reference_id = '{resource_id}'
                LIMIT 1
                """

                results = query_athena(query, f"Finding Binary for {resource_type}/{resource_id}", suppress_output=True)

                if not results:
                    logger.warning(f"No Binary found for {fhir_target} in v_binary_files")
                    return None

                binary_id = results[0].get('binary_id')
                content_type = results[0].get('content_type', 'application/pdf')

                logger.info(f"Found Binary {binary_id} for {fhir_target}")

            except Exception as e:
                logger.error(f"Error querying v_binary_files for {fhir_target}: {e}")
                return None
        elif resource_type == 'Binary':
            # For direct Binary references, use as-is
            binary_id = fhir_target
            content_type = "application/pdf"
        else:
            logger.warning(f"Unknown resource type: {resource_type}")
            return None

        # Fetch using BinaryFileAgent
        try:
            extracted_text, error = self.binary_agent.extract_text_from_binary(
                binary_id=binary_id,
                patient_fhir_id=self.athena_patient_id,
                content_type=content_type
            )

            if error:
                logger.warning(f"Error extracting text from {binary_id}: {error}")
                return None

            return extracted_text

        except Exception as e:
            logger.error(f"Error fetching binary {binary_id}: {e}")
            return None

    def _validate_document_content(self, extracted_text: str, gap_type: str) -> Tuple[bool, str]:
        """
        Validate that document content matches expected gap type (Agent 1 validation)

        Args:
            extracted_text: The extracted text from binary
            gap_type: Type of gap (missing_eor, missing_radiation_details, etc.)

        Returns:
            Tuple of (is_valid, reason)
        """
        if not extracted_text or len(extracted_text) < 100:
            return False, "Document too short or empty"

        text_lower = extracted_text.lower()

        # Validation keywords by gap type
        validation_rules = {
            'missing_eor': {
                'required_keywords': ['surgery', 'operative', 'procedure', 'resection', 'excision'],
                'forbidden_keywords': ['radiation', 'chemotherapy'],
                'min_keywords': 2
            },
            'missing_radiation_details': {
                'required_keywords': ['radiation', 'dose', 'gy', 'cgy', 'treatment', 'field'],
                'forbidden_keywords': [],
                'min_keywords': 3
            },
            'vague_imaging_conclusion': {
                'required_keywords': ['imaging', 'mri', 'ct', 'scan', 'brain', 'tumor', 'mass'],
                'forbidden_keywords': [],
                'min_keywords': 2
            }
        }

        rules = validation_rules.get(gap_type)
        if not rules:
            return True, "No validation rules for this gap type"

        # Check for required keywords
        found_keywords = [kw for kw in rules['required_keywords'] if kw in text_lower]

        if len(found_keywords) < rules['min_keywords']:
            return False, f"Missing required keywords. Found: {found_keywords}, need at least {rules['min_keywords']}"

        # Check for forbidden keywords (indicates wrong document type)
        found_forbidden = [kw for kw in rules['forbidden_keywords'] if kw in text_lower]
        if found_forbidden:
            return False, f"Document contains forbidden keywords: {found_forbidden} (wrong document type)"

        return True, f"Document validated with keywords: {found_keywords}"

    def _validate_extraction_result(self, extraction_data: Dict, gap_type: str) -> Tuple[bool, List[str]]:
        """
        Validate that MedGemma extraction contains required fields (Agent 1 validation)

        Args:
            extraction_data: Extracted data from MedGemma
            gap_type: Type of gap

        Returns:
            Tuple of (is_valid, list of missing required fields)
        """
        # Define required fields by gap type
        required_fields = {
            'missing_eor': ['extent_of_resection', 'surgeon_assessment'],
            'missing_radiation_details': [
                'date_at_radiation_start',
                'total_dose_cgy',
                'radiation_type'
            ],
            'vague_imaging_conclusion': ['lesions', 'rano_assessment']
        }

        required = required_fields.get(gap_type, [])
        missing = []

        for field in required:
            if field not in extraction_data or extraction_data[field] is None or extraction_data[field] == "":
                missing.append(field)

        is_valid = len(missing) == 0
        return is_valid, missing

    def _retry_extraction_with_clarification(self, gap: Dict, extracted_text: str, first_result: Dict, missing_fields: List[str]) -> Optional[Dict]:
        """
        Agent 1 re-prompts Agent 2 (MedGemma) with clarification when extraction incomplete

        Args:
            gap: The extraction gap
            extracted_text: Original document text
            first_result: First extraction attempt result
            missing_fields: List of missing required fields

        Returns:
            Second extraction result or None
        """
        logger.info(f"Re-extraction attempt for {gap['gap_type']} - missing fields: {missing_fields}")
        print(f"    🔄 Re-extraction: First attempt missing {missing_fields}")

        # Field-specific guidance for re-extraction
        field_guidance = {
            'extent_of_resection': 'Look for phrases like "gross total resection", "subtotal resection", "biopsy only" in operative note',
            'surgeon_assessment': 'Extract verbatim text from surgeon describing the resection outcome (usually in procedure description or impression)',
            'date_at_radiation_start': 'Find the first date radiation was delivered (format: YYYY-MM-DD). May be in "Treatment Start" or "Course Start" section',
            'date_at_radiation_stop': 'Find the last date radiation was delivered (format: YYYY-MM-DD). May be calculated from start date + duration',
            'total_dose_cgy': 'Find total cumulative dose in cGy or Gy (convert: 1 Gy = 100 cGy). Look for phrases like "total dose", "cumulative dose"',
            'radiation_type': 'Determine if focal (tumor only), craniospinal (brain+spine), whole_ventricular, or focal_with_boost',
            'lesions': 'Extract array of tumor lesions with measurements. Use [] if no tumor present',
            'rano_assessment': 'Assess response using RANO criteria based on size change and new lesions'
        }

        # Build specific instructions for missing fields
        specific_instructions = []
        for field in missing_fields:
            guidance = field_guidance.get(field, f'Extract {field} from the document')
            specific_instructions.append(f"- {field}: {guidance}")

        # Build clarification prompt
        clarification = f"""
IMPORTANT: The first extraction attempt was incomplete.

MISSING REQUIRED FIELDS: {', '.join(missing_fields)}

Please re-extract from the same document, focusing specifically on finding these missing fields:
{chr(10).join(specific_instructions)}

INSTRUCTIONS:
1. Search the document carefully for each missing field
2. If a field is truly not present in the document, set it to null
3. If you set required fields to null, set extraction_confidence to "LOW"
4. Return ALL fields from the original schema, not just the missing ones
"""

        # Generate new prompt with clarification
        base_prompt = self._generate_medgemma_prompt(gap)
        clarified_prompt = base_prompt + "\n\n" + clarification
        full_prompt = f"{clarified_prompt}\n\nDOCUMENT TEXT:\n{extracted_text}"

        try:
            result = self.medgemma_agent.extract(full_prompt, temperature=0.1)
            if result.success:
                print(f"    ✅ Re-extraction complete")
                return result.extracted_data
            else:
                print(f"    ❌ Re-extraction failed: {result.error}")
                return None
        except Exception as e:
            logger.error(f"Re-extraction error: {e}")
            return None

    def _integrate_extraction_into_timeline(self, gap: Dict, extraction_data: Dict):
        """
        Integrate MedGemma extraction results into timeline events

        Args:
            gap: The gap that was filled
            extraction_data: The extracted data from MedGemma
        """
        # Find the corresponding timeline event and enrich it
        event_date = gap.get('event_date')
        gap_type = gap.get('gap_type')

        for event in self.timeline_events:
            if event.get('event_date') == event_date:
                # Add medgemma_extraction field to event
                if gap_type == 'vague_imaging_conclusion' and event.get('event_type') == 'imaging':
                    event['medgemma_extraction'] = extraction_data
                    break
                elif gap_type == 'missing_eor' and event.get('event_type') == 'surgery':
                    event['extent_of_resection'] = extraction_data.get('extent_of_resection')
                    event['medgemma_extraction'] = extraction_data
                    break
                elif gap_type == 'missing_radiation_dose' and event.get('event_type') == 'radiation_start':
                    event['total_dose_cgy'] = extraction_data.get('total_dose_cgy')
                    event['medgemma_extraction'] = extraction_data
                    break

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
        description='Patient Clinical Journey Timeline Abstraction V2 (with real Phase 4)'
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
    parser.add_argument(
        '--max-extractions',
        type=int,
        default=None,
        help='Maximum number of binary extractions to perform (for testing)'
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
    abstractor = PatientTimelineAbstractor(args.patient_id, output_dir, max_extractions=args.max_extractions)
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
