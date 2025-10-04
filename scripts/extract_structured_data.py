#!/usr/bin/env python3
"""
Extract Structured Clinical Data from Athena Materialized Views

This script queries specific fields from FHIR resources to pre-populate
ground truth data for BRIM CSV generation.

Database Strategy:
- fhir_v2_prd_db: condition, procedure, medication_request, observation, encounter
- fhir_v1_prd_db: document_reference (v2 incomplete for documents)

Output: structured_data_{patient_id}.json with pre-populated fields:
- diagnosis_date (from condition.onset_date_time)
- surgeries (from procedure.performed_date_time with CPT codes)
- molecular_markers (from observation.value_string)
- treatment_dates (from medication_request.authored_on)

Usage:
    python scripts/extract_structured_data.py \
        --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
        --output pilot_output/structured_data.json
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import boto3
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StructuredDataExtractor:
    """Extract structured clinical data from Athena FHIR databases"""
    
    def __init__(
        self,
        aws_profile: str = '343218191717_AWSAdministratorAccess',
        v2_database: str = 'fhir_v2_prd_db',
        v1_database: str = 'fhir_v1_prd_db',
        s3_output_location: str = 's3://aws-athena-query-results-343218191717-us-east-1/'
    ):
        """
        Initialize extractor with dual database access.
        
        Args:
            aws_profile: AWS profile for authentication
            v2_database: Database for condition, procedure, medication, observation (complete)
            v1_database: Database for document_reference (v2 incomplete)
            s3_output_location: S3 location for Athena query results
        """
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena_client = self.session.client('athena', region_name='us-east-1')
        self.s3_client = self.session.client('s3', region_name='us-east-1')
        self.v2_database = v2_database
        self.v1_database = v1_database
        self.s3_output_location = s3_output_location
        
        logger.info(f"Initialized with v2_db={v2_database}, v1_db={v1_database}")
    
    def query_and_fetch(self, query: str, database: str) -> pd.DataFrame:
        """Execute Athena query and return results as DataFrame"""
        logger.info(f"Executing query on {database}:\n{query[:200]}...")
        
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': self.s3_output_location}
        )
        
        query_execution_id = response['QueryExecutionId']
        
        # Wait for query to complete
        while True:
            response = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            status = response['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise RuntimeError(f"Query {status}: {reason}")
            
            time.sleep(2)
        
        # Fetch results
        results = self.athena_client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=1000
        )
        
        # Parse into DataFrame
        columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        rows = []
        for row in results['ResultSet']['Rows'][1:]:  # Skip header
            rows.append([field.get('VarCharValue', None) for field in row['Data']])
        
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Query returned {len(df)} rows")
        
        return df
    
    def extract_diagnosis_date(self, patient_fhir_id: str) -> Optional[str]:
        """Extract diagnosis date from problem_list_diagnoses materialized view
        
        Schema reference: data/materialized_view_schema.csv
        - problem_list_diagnoses.onset_date_time (column 6)
        - problem_list_diagnoses.diagnosis_name (column 4)
        - problem_list_diagnoses.patient_id (column 1) - NOTE: uses patient_id not subject_reference
        - problem_list_diagnoses.icd10_code (column 9)
        """
        
        query = f"""
        SELECT 
            onset_date_time,
            diagnosis_name,
            icd10_code,
            clinical_status_text
        FROM {self.v2_database}.problem_list_diagnoses
        WHERE patient_id = '{patient_fhir_id}'
            AND (
                LOWER(diagnosis_name) LIKE '%astrocytoma%'
                OR LOWER(diagnosis_name) LIKE '%glioma%'
                OR LOWER(diagnosis_name) LIKE '%brain%'
                OR LOWER(diagnosis_name) LIKE '%tumor%'
            )
            AND onset_date_time IS NOT NULL
        ORDER BY onset_date_time
        LIMIT 1
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        if not df.empty and df.iloc[0]['onset_date_time']:
            diagnosis_date = df.iloc[0]['onset_date_time']
            diagnosis_name = df.iloc[0]['diagnosis_name']
            icd10 = df.iloc[0]['icd10_code']
            logger.info(f"✅ Found diagnosis date: {diagnosis_date} ({diagnosis_name}, ICD-10: {icd10})")
            return diagnosis_date
        
        logger.warning("⚠️  No diagnosis date found")
        return None
    
    def extract_surgeries(self, patient_fhir_id: str) -> List[Dict]:
        """Extract TUMOR RESECTION surgery dates and details from procedure table
        
        Schema reference: data/materialized_view_schema.csv
        Per COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md:
        - procedure.subject_reference does NOT include 'Patient/' prefix
        - procedure.performed_date_time (column 13)
        - procedure.code_text (column 6)
        - procedure.status (column 3)
        - procedure_code_coding.code_coding_code (CPT codes)
        - procedure_code_coding.code_coding_display
        
        IMPORTANT: This extracts ONLY tumor resection procedures, NOT all procedures.
        CPT code filtering:
        - 61500-61576: Excision/resection of brain tumor (supratentorial, infratentorial)
        - EXCLUDES: 62201 (CSF shunt/ETV - hydrocephalus management, NOT tumor surgery)
        - EXCLUDES: 61304-61315 (biopsy only - not resection)
        """
        
        # TUMOR RESECTION CPT codes only (excludes shunts, biopsies, diagnostic procedures)
        TUMOR_RESECTION_CPTS = [
            '61500', '61501', '61510', '61512', '61514', '61516',  # Supratentorial tumor resection
            '61518', '61519', '61520', '61521', '61524', '61526',  # Infratentorial/posterior fossa tumor resection
            '61530', '61531', '61536', '61537', '61538', '61539',  # Additional tumor resection codes
            '61545', '61546', '61548', '61550', '61552',           # Transsphenoidal/skull base approaches
        ]
        
        query = f"""
        SELECT 
            p.id as procedure_id,
            CASE 
                WHEN p.performed_date_time IS NOT NULL AND p.performed_date_time != '' THEN p.performed_date_time
                WHEN p.performed_period_start IS NOT NULL AND p.performed_period_start != '' THEN SUBSTR(p.performed_period_start, 1, 10)
                ELSE NULL
            END as surgery_date,
            p.performed_date_time,
            p.performed_period_start,
            p.code_text,
            p.status,
            pcc.code_coding_code as cpt_code,
            pcc.code_coding_display as cpt_display
        FROM {self.v2_database}.procedure p
        LEFT JOIN {self.v2_database}.procedure_code_coding pcc 
            ON p.id = pcc.procedure_id
        WHERE p.subject_reference = '{patient_fhir_id}'
            AND p.status = 'completed'
            AND (
                p.performed_date_time IS NOT NULL 
                OR p.performed_period_start IS NOT NULL
            )
            AND (
                pcc.code_coding_code IN {tuple(TUMOR_RESECTION_CPTS)}
                OR (
                    pcc.code_coding_code BETWEEN '61500' AND '61576'
                    AND pcc.code_coding_code NOT IN ('62201', '62223')  -- Exclude shunts
                )
                OR (
                    LOWER(pcc.code_coding_display) LIKE '%tumor resection%'
                    OR LOWER(pcc.code_coding_display) LIKE '%excision%tumor%'
                    OR LOWER(pcc.code_coding_display) LIKE '%brain tumor%'
                )
            )
            AND pcc.code_coding_code NOT IN ('62201', '62223', '61304', '61305', '61312', '61313', '61314', '61315')
        ORDER BY surgery_date
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        surgeries = []
        for _, row in df.iterrows():
            # Skip if CPT code is a shunt or biopsy (defensive check)
            cpt_code = row['cpt_code']
            if cpt_code in ['62201', '62223', '61304', '61305', '61312', '61313', '61314', '61315']:
                logger.info(f"⏭️  Skipping non-resection procedure: {cpt_code} ({row['cpt_display']})")
                continue
            
            # Use the COALESCE'd surgery_date field
            surgery_date = row['surgery_date']
            if not surgery_date or str(surgery_date).strip() == '' or str(surgery_date) == 'nan':
                logger.info(f"⏭️  Skipping procedure without date: {cpt_code} ({row['cpt_display']})")
                continue
            
            # Extract just the date part (YYYY-MM-DD) from timestamp
            date_str = str(surgery_date).split('T')[0] if 'T' in str(surgery_date) else str(surgery_date)
            
            surgeries.append({
                'date': date_str,
                'cpt_code': row['cpt_code'],
                'cpt_display': row['cpt_display'],
                'description': row['code_text']
            })
        
        logger.info(f"✅ Found {len(surgeries)} TUMOR RESECTION surgeries (filtered from query results)")
        logger.info(f"   NOTE: Excludes shunts (62201), biopsies (61304-61315), and other non-resection procedures")
        return surgeries
    
    def extract_molecular_markers(self, patient_fhir_id: str) -> Dict[str, str]:
        """Extract molecular markers from molecular_tests + molecular_test_results materialized views
        
        Schema reference: data/materialized_view_schema.csv
        - molecular_tests.patient_id (column 1) - NOTE: uses patient_id not subject_reference
        - molecular_tests.dgd_id (column 2) - DGD genomics identifier
        - molecular_tests.lab_test_name (column 3)
        - molecular_tests.result_datetime (column 6)
        - molecular_test_results.test_result_narrative (column 4)
        - molecular_test_results.test_component (column 5)
        """
        
        query = f"""
        SELECT 
            mt.dgd_id,
            mt.lab_test_name,
            mt.result_datetime,
            mtr.test_result_narrative,
            mtr.test_component
        FROM {self.v2_database}.molecular_tests mt
        LEFT JOIN {self.v2_database}.molecular_test_results mtr 
            ON mt.test_id = mtr.test_id
        WHERE mt.patient_id = '{patient_fhir_id}'
            AND mtr.test_result_narrative IS NOT NULL
        ORDER BY mt.result_datetime DESC
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        markers = {}
        for _, row in df.iterrows():
            narrative = row['test_result_narrative']
            component = row.get('test_component', '')
            
            # Parse common markers
            if 'BRAF' in narrative.upper() or 'BRAF' in component.upper():
                markers['BRAF'] = narrative
            if 'IDH' in narrative.upper() or 'IDH' in component.upper():
                markers['IDH1'] = narrative
            if 'MGMT' in narrative.upper() or 'MGMT' in component.upper():
                markers['MGMT'] = narrative
            if 'EGFR' in narrative.upper() or 'EGFR' in component.upper():
                markers['EGFR'] = narrative
        
        # FALLBACK: If no molecular markers found in materialized view, try raw observation table
        if not markers:
            logger.info("⚠️  No molecular markers in molecular_tests view, trying observation table...")
            
            fallback_query = f"""
            SELECT 
                o.code_text,
                o.value_string,
                o.value_codeable_concept_text,
                o.effective_datetime
            FROM {self.v2_database}.observation o
            WHERE o.subject_reference = '{patient_fhir_id}'
                AND (
                    o.code_text = 'Genomics Interpretation'
                    OR LOWER(o.code_text) LIKE '%molecular%'
                    OR LOWER(o.code_text) LIKE '%genomic%'
                    OR LOWER(o.value_string) LIKE '%braf%'
                    OR LOWER(o.value_string) LIKE '%idh%'
                    OR LOWER(o.value_string) LIKE '%mgmt%'
                    OR LOWER(o.value_string) LIKE '%egfr%'
                )
            ORDER BY o.effective_datetime DESC
            """
            
            df_fallback = self.query_and_fetch(fallback_query, self.v2_database)
            
            for _, row in df_fallback.iterrows():
                value = row.get('value_string') or row.get('value_codeable_concept_text', '')
                if not value:
                    continue
                    
                # Parse common markers from fallback
                if 'BRAF' in value.upper():
                    markers['BRAF'] = value
                if 'IDH' in value.upper():
                    markers['IDH1'] = value
                if 'MGMT' in value.upper():
                    markers['MGMT'] = value
                if 'EGFR' in value.upper():
                    markers['EGFR'] = value
        
        logger.info(f"✅ Found {len(markers)} molecular markers")
        return markers
    
    def extract_treatment_start_dates(self, patient_fhir_id: str) -> List[Dict]:
        """Extract treatment start dates from patient_medications materialized view
        
        Searches for chemotherapy agents including:
        - Alkylating agents (temozolomide, lomustine, cyclophosphamide, procarbazine)
        - Platinum compounds (carboplatin, cisplatin)
        - Vinca alkaloids (vincristine, vinblastine)
        - Topoisomerase inhibitors (etoposide, irinotecan)
        - Targeted therapies (bevacizumab, selumetinib, dabrafenib, trametinib)
        
        Schema reference: data/materialized_view_schema.csv
        - patient_medications.patient_id (column 1) - NOTE: uses patient_id not subject_reference
        - patient_medications.medication_name (column 2)
        - patient_medications.rx_norm_codes (column 3) - Already has RxNorm codes aggregated
        - patient_medications.authored_on (column 4)
        - patient_medications.status (column 5)
        """
        
        # Comprehensive chemotherapy keyword list
        # Gold standard for C1277724 includes: vinblastine, bevacizumab, selumetinib
        chemo_keywords = [
            # Alkylating agents
            'temozolomide', 'temodar', 'tmz',
            'lomustine', 'ccnu', 'ceenu', 'gleostine',
            'cyclophosphamide', 'cytoxan', 'neosar',
            'procarbazine', 'matulane',
            'carmustine', 'bcnu', 'gliadel',
            
            # Platinum compounds
            'carboplatin', 'paraplatin',
            'cisplatin', 'platinol',
            
            # Vinca alkaloids (CRITICAL - gold standard has these)
            'vincristine', 'oncovin', 'marqibo',
            'vinblastine', 'velban',  # ← CRITICAL: Gold standard has this
            
            # Topoisomerase inhibitors
            'etoposide', 'vepesid', 'toposar', 'etopophos',
            'irinotecan', 'camptosar', 'onivyde',
            'topotecan', 'hycamtin',
            
            # Antimetabolites
            'methotrexate', 'trexall', 'otrexup', 'rasuvo',
            '6-mercaptopurine', '6mp', 'purinethol',
            'thioguanine', '6-thioguanine',
            
            # Targeted therapies (CRITICAL - gold standard has these)
            'bevacizumab', 'avastin',  # ← Already captured
            'selumetinib', 'koselugo',  # ← CRITICAL: Gold standard has this
            'dabrafenib', 'tafinlar',
            'trametinib', 'mekinist',
            'vemurafenib', 'zelboraf',
            'everolimus', 'afinitor',
            
            # Immunotherapy
            'nivolumab', 'opdivo',
            'pembrolizumab', 'keytruda',
            'ipilimumab', 'yervoy',
            
            # Other
            'radiation', 'radiotherapy',
            'chemotherapy', 'chemo',
        ]
        
        # Build SQL OR conditions for all keywords
        conditions = ' OR '.join([f"LOWER(medication_name) LIKE '%{keyword}%'" for keyword in chemo_keywords])
        
        query = f"""
        SELECT 
            medication_name as medication,
            rx_norm_codes,
            authored_on as start_date,
            status
        FROM {self.v2_database}.patient_medications
        WHERE patient_id = '{patient_fhir_id}'
            AND status IN ('active', 'completed')
            AND ({conditions})
        ORDER BY authored_on
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        treatments = []
        for _, row in df.iterrows():
            treatments.append({
                'medication': row['medication'],
                'rx_norm_codes': row['rx_norm_codes'],
                'start_date': row['start_date'],
                'status': row['status']
            })
        
        logger.info(f"✅ Found {len(treatments)} treatment records")
        return treatments
    
    def extract_concomitant_medications(self, patient_fhir_id: str) -> List[Dict]:
        """Extract ALL medications (concomitant medications) from patient_medications view
        
        This extracts all medications regardless of type (not just chemotherapy).
        Includes supportive care medications, anti-epileptics, steroids, etc.
        
        Returns medications that are NOT chemotherapy agents (those are in treatments).
        """
        logger.info("\n--- Extracting Concomitant Medications (Non-Chemo) ---")
        
        # Keywords for chemotherapy (to EXCLUDE)
        chemo_keywords = [
            'temozolomide', 'temodar', 'lomustine', 'ccnu', 'cyclophosphamide', 'cytoxan',
            'procarbazine', 'carmustine', 'bcnu', 'carboplatin', 'cisplatin',
            'vincristine', 'vinblastine', 'etoposide', 'irinotecan', 'topotecan',
            'methotrexate', 'bevacizumab', 'avastin', 'selumetinib', 'koselugo',
            'dabrafenib', 'trametinib', 'vemurafenib', 'everolimus',
            'nivolumab', 'pembrolizumab', 'ipilimumab'
        ]
        
        # Build exclusion conditions
        exclusions = ' AND '.join([f"LOWER(medication_name) NOT LIKE '%{keyword}%'" for keyword in chemo_keywords])
        
        query = f"""
        SELECT 
            medication_name as medication,
            rx_norm_codes,
            authored_on as start_date,
            status
        FROM {self.v2_database}.patient_medications
        WHERE patient_id = '{patient_fhir_id}'
            AND status IN ('active', 'completed')
            AND ({exclusions})
        ORDER BY authored_on
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        conmeds = []
        for _, row in df.iterrows():
            conmeds.append({
                'medication': row['medication'],
                'rx_norm_codes': row['rx_norm_codes'],
                'start_date': row['start_date'],
                'status': row['status']
            })
        
        logger.info(f"✅ Found {len(conmeds)} concomitant medication records")
        return conmeds
    
    def extract_patient_gender(self, patient_fhir_id: str) -> Optional[str]:
        """
        Extract patient gender from Patient resource.
        
        Returns: male, female, other, unknown, or None
        """
        logger.info("\n--- Extracting Patient Gender ---")
        
        query = f"""
        SELECT gender
        FROM {self.v2_database}.patient
        WHERE id = '{patient_fhir_id}'
        LIMIT 1
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        if df.empty or df['gender'].isna().all():
            logger.warning("⚠️  No gender found in Patient resource")
            return None
        
        gender = df['gender'].iloc[0]
        logger.info(f"✅ Gender: {gender}")
        return gender
    
    def extract_date_of_birth(self, patient_fhir_id: str) -> Optional[str]:
        """
        Extract date of birth from Patient resource.
        
        Returns: YYYY-MM-DD or None
        """
        logger.info("\n--- Extracting Date of Birth ---")
        
        query = f"""
        SELECT birth_date
        FROM {self.v2_database}.patient
        WHERE id = '{patient_fhir_id}'
        LIMIT 1
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        if df.empty or df['birth_date'].isna().all():
            logger.warning("⚠️  No birth_date found in Patient resource")
            return None
        
        birth_date = df['birth_date'].iloc[0]
        
        # Handle different date formats
        if birth_date and len(str(birth_date)) >= 10:
            birth_date = str(birth_date)[:10]  # Extract YYYY-MM-DD
            logger.info(f"✅ Date of Birth: {birth_date}")
            return birth_date
        
        logger.warning(f"⚠️  Invalid birth_date format: {birth_date}")
        return None
    
    def extract_radiation_therapy(self, patient_fhir_id: str) -> bool:
        """
        Check if patient received radiation therapy from procedure table.
        
        Radiation CPT codes:
        - 77261-77263: Radiation treatment planning
        - 77295-77370: Radiation dosimetry and simulation
        - 77401-77499: External beam radiation therapy
        - 77427-77432: Treatment management
        
        Returns: True if radiation found, False otherwise
        """
        logger.info("\n--- Extracting Radiation Therapy Status ---")
        
        query = f"""
        SELECT COUNT(*) as radiation_count
        FROM {self.v2_database}.procedure p
        LEFT JOIN {self.v2_database}.procedure_code_coding pcc 
            ON p.id = pcc.procedure_id
        WHERE p.subject_reference = '{patient_fhir_id}'
            AND p.status = 'completed'
            AND (
                (pcc.code_coding_code BETWEEN '77261' AND '77499')
                OR LOWER(pcc.code_coding_display) LIKE '%radiation%'
                OR LOWER(pcc.code_coding_display) LIKE '%radiotherapy%'
                OR LOWER(p.code_text) LIKE '%radiation%'
                OR LOWER(p.code_text) LIKE '%radiotherapy%'
            )
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        if df.empty:
            logger.warning("⚠️  Query returned no results")
            return False
        
        radiation_count = int(df['radiation_count'].iloc[0])
        
        if radiation_count > 0:
            logger.info(f"✅ Radiation therapy FOUND: {radiation_count} procedure(s)")
            return True
        else:
            logger.info("❌ No radiation therapy found")
            return False
    
    def extract_primary_diagnosis(self, patient_fhir_id: str) -> Optional[str]:
        """
        Extract primary diagnosis text (with WHO grade if present).
        
        Returns: Full diagnosis name from problem_list_diagnoses
        """
        logger.info("\n--- Extracting Primary Diagnosis ---")
        
        query = f"""
        SELECT 
            diagnosis_name,
            icd10_code,
            onset_date_time
        FROM {self.v2_database}.problem_list_diagnoses
        WHERE patient_id = '{patient_fhir_id}'
            AND (
                LOWER(diagnosis_name) LIKE '%astrocytoma%'
                OR LOWER(diagnosis_name) LIKE '%glioma%'
                OR LOWER(diagnosis_name) LIKE '%brain%tumor%'
                OR LOWER(diagnosis_name) LIKE '%neoplasm%brain%'
                OR LOWER(diagnosis_name) LIKE '%tumor%'
            )
        ORDER BY onset_date_time
        LIMIT 1
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        if df.empty:
            logger.warning("⚠️  No primary diagnosis found")
            return None
        
        diagnosis = df['diagnosis_name'].iloc[0]
        icd10 = df['icd10_code'].iloc[0] if 'icd10_code' in df.columns else None
        
        logger.info(f"✅ Primary Diagnosis: {diagnosis}")
        if icd10:
            logger.info(f"   ICD-10: {icd10}")
        
        return diagnosis
    
    def extract_imaging_clinical(self, patient_fhir_id: str, date_of_birth: str = '2005-05-13') -> List[Dict]:
        """
        Extract imaging clinical data from radiology materialized views.
        
        Based on: IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md
        
        NOTE: Placeholder for imaging extraction. Full implementation with corticosteroid
        mapping requires complex multi-table queries. Can be added in future iteration.
        
        For now, imaging data will be extracted from NARRATIVE radiology reports via BRIM.
        """
        logger.info("\n--- Extracting Imaging Clinical Data ---")
        logger.info("⚠️  Imaging extraction is a placeholder - using NARRATIVE approach via BRIM")
        logger.info("   Full structured imaging extraction with corticosteroids requires dedicated workflow")
        logger.info("   See: IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md")
        
        # Placeholder - return empty list for now
        # Full implementation would query radiology_imaging_mri + radiology_imaging_mri_results
        # with corticosteroid matching from patient_medications
        
        return []
    
    def extract_all(self, patient_fhir_id: str) -> Dict:
        """Extract all structured data for a patient"""
        
        logger.info(f"\n{'='*70}")
        logger.info(f"EXTRACTING STRUCTURED DATA FOR PATIENT: {patient_fhir_id}")
        logger.info(f"{'='*70}\n")
        
        # PHASE 1: Essential Demographics
        patient_gender = self.extract_patient_gender(patient_fhir_id)
        date_of_birth = self.extract_date_of_birth(patient_fhir_id)
        
        # PHASE 1: Clinical Data
        primary_diagnosis = self.extract_primary_diagnosis(patient_fhir_id)
        diagnosis_date = self.extract_diagnosis_date(patient_fhir_id)
        surgeries = self.extract_surgeries(patient_fhir_id)
        radiation_therapy = self.extract_radiation_therapy(patient_fhir_id)
        
        # Existing: Molecular & Treatment
        molecular_markers = self.extract_molecular_markers(patient_fhir_id)
        treatments = self.extract_treatment_start_dates(patient_fhir_id)
        concomitant_medications = self.extract_concomitant_medications(patient_fhir_id)
        
        # NEW: Imaging Clinical Data
        imaging_clinical = self.extract_imaging_clinical(patient_fhir_id, date_of_birth or '2005-05-13')
        
        structured_data = {
            'patient_fhir_id': patient_fhir_id,
            'extraction_timestamp': datetime.now().isoformat(),
            
            # Demographics (NEW)
            'patient_gender': patient_gender,
            'date_of_birth': date_of_birth,
            
            # Diagnosis (ENHANCED)
            'primary_diagnosis': primary_diagnosis,
            'diagnosis_date': diagnosis_date,
            
            # Procedures
            'surgeries': surgeries,
            'radiation_therapy': radiation_therapy,  # NEW
            
            # Molecular & Treatment
            'molecular_markers': molecular_markers,
            'treatments': treatments,  # Chemotherapy agents
            'concomitant_medications': concomitant_medications,  # NEW - All other medications
            
            # Imaging Clinical (NEW)
            'imaging_clinical': imaging_clinical  # NEW - Imaging with corticosteroids and clinical status
        }
        
        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("EXTRACTION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Demographics:")
        logger.info(f"  - Gender: {patient_gender}")
        logger.info(f"  - Date of Birth: {date_of_birth}")
        logger.info(f"\nDiagnosis:")
        logger.info(f"  - Primary: {primary_diagnosis}")
        logger.info(f"  - Date: {diagnosis_date}")
        logger.info(f"\nProcedures:")
        logger.info(f"  - Surgeries: {len(surgeries)}")
        logger.info(f"  - Radiation: {radiation_therapy}")
        logger.info(f"\nMolecular & Treatment:")
        logger.info(f"  - Molecular Markers: {len(molecular_markers)}")
        logger.info(f"  - Chemotherapy Records: {len(treatments)}")
        logger.info(f"  - Concomitant Medications: {len(concomitant_medications)}")
        logger.info(f"\nImaging Clinical:")
        logger.info(f"  - Imaging Events: {len(imaging_clinical)} (placeholder - using NARRATIVE approach)")
        logger.info(f"{'='*70}\n")
        
        return structured_data


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description='Extract structured clinical data from Athena FHIR databases'
    )
    parser.add_argument(
        '--patient-fhir-id',
        required=True,
        help='Patient FHIR ID (e.g., e4BwD8ZYDBccepXcJ.Ilo3w3)'
    )
    parser.add_argument(
        '--output',
        default='./pilot_output/structured_data.json',
        help='Output JSON file path (default: pilot_output/structured_data.json)'
    )
    parser.add_argument(
        '--aws-profile',
        default='343218191717_AWSAdministratorAccess',
        help='AWS profile name'
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract structured data
    extractor = StructuredDataExtractor(aws_profile=args.aws_profile)
    structured_data = extractor.extract_all(args.patient_fhir_id)
    
    # Save to file
    with open(output_path, 'w') as f:
        json.dump(structured_data, f, indent=2)
    
    logger.info(f"\n✅ Structured data saved to: {output_path}")
    
    # Show sample
    logger.info("\nSample output:")
    logger.info(json.dumps(structured_data, indent=2)[:500] + "...")


if __name__ == '__main__':
    main()
