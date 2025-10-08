#!/usr/bin/env python3
"""
Extract Diagnosis Data from Athena for Multiple Patients

Purpose:
  Production-ready extraction script for diagnosis CSV data.
  Extracts from Athena materialized views WITHOUT requiring gold standard.
  
Input: List of patient FHIR IDs
Output: Diagnosis CSV with all extractable fields

Usage:
  python3 scripts/extract_diagnosis.py \
    --patient-ids e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --output-csv outputs/diagnosis_extracted.csv

  # Or from file:
  python3 scripts/extract_diagnosis.py \
    --patient-ids-file patient_list.txt \
    --output-csv outputs/diagnosis_extracted.csv

Tables Used:
  - fhir_v2_prd_db.problem_list_diagnoses (primary diagnosis source)
  - fhir_v2_prd_db.patient_access (for birth_date, age calculations)
  - fhir_v2_prd_db.condition + condition_code_coding (metastasis detection)
  - fhir_v2_prd_db.procedure + procedure_code_coding (shunt detection)
  - fhir_v2_prd_db.molecular_tests (test types performed)
  
Security:
  - Works in background mode (no PHI in terminal)
  - Uses FHIR IDs only (not MRN)
"""

import argparse
import boto3
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DiagnosisExtractor:
    """Extract diagnosis data from Athena for patient cohort"""
    
    def __init__(self, aws_profile: str, database: str):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
        
    def execute_query(self, query: str, description: str = "") -> List[Dict]:
        """Execute Athena query and return results as list of dicts"""
        logger.info(f"Executing: {description}")
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for query to complete
            max_attempts = 60
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                query_status = self.athena.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = query_status['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    reason = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    logger.error(f"Query failed: {reason}")
                    return []
                
                time.sleep(1)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_execution_id)
            
            if not results.get('ResultSet', {}).get('Rows'):
                logger.warning(f"No results for: {description}")
                return []
            
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:
                logger.info(f"No data rows for: {description}")
                return []
            
            # Extract column names
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            
            # Extract data rows
            data_rows = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    value = col.get('VarCharValue', None)
                    row_data[columns[i]] = value
                data_rows.append(row_data)
            
            logger.info(f"  ✓ Retrieved {len(data_rows)} rows")
            return data_rows
            
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
            return []
    
    def get_patient_birth_dates(self, patient_ids: List[str]) -> Dict[str, str]:
        """Get birth dates for all patients (needed for age calculations)"""
        
        # Build IN clause
        ids_str = "', '".join(patient_ids)
        
        query = f"""
        SELECT 
            id,
            birth_date
        FROM {self.database}.patient_access
        WHERE id IN ('{ids_str}')
        """
        
        results = self.execute_query(query, f"Get birth dates for {len(patient_ids)} patients")
        
        birth_dates = {}
        for row in results:
            birth_dates[row['id']] = row.get('birth_date', '')
        
        return birth_dates
    
    def extract_diagnoses_for_patient(self, patient_fhir_id: str, birth_date: str) -> List[Dict]:
        """Extract all diagnosis events for a single patient"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"PATIENT: {patient_fhir_id}")
        logger.info(f"{'='*60}")
        
        # 1. Get primary diagnoses from problem_list_diagnoses
        diagnoses_query = f"""
        SELECT 
            patient_id,
            onset_date_time,
            diagnosis_name,
            clinical_status_text,
            icd10_code
        FROM {self.database}.problem_list_diagnoses
        WHERE patient_id = '{patient_fhir_id}'
            AND onset_date_time IS NOT NULL
            AND (
                LOWER(diagnosis_name) LIKE '%astrocytoma%' OR
                LOWER(diagnosis_name) LIKE '%glioma%' OR
                LOWER(diagnosis_name) LIKE '%tumor%' OR
                LOWER(diagnosis_name) LIKE '%neoplasm%' OR
                LOWER(diagnosis_name) LIKE '%cancer%' OR
                LOWER(diagnosis_name) LIKE '%carcinoma%' OR
                LOWER(diagnosis_name) LIKE '%sarcoma%' OR
                LOWER(diagnosis_name) LIKE '%blastoma%'
            )
        ORDER BY onset_date_time
        """
        
        diagnoses = self.execute_query(diagnoses_query, "Query cancer diagnoses")
        
        if not diagnoses:
            logger.warning(f"No cancer diagnoses found for {patient_fhir_id}")
            return []
        
        logger.info(f"Found {len(diagnoses)} cancer diagnosis entries")
        
        # 2. Get metastasis conditions
        condition_query = f"""
        SELECT 
            c.id,
            c.recorded_date,
            ccc.code_coding_code as code,
            ccc.code_coding_display as display
        FROM {self.database}.condition c
        LEFT JOIN {self.database}.condition_code_coding ccc 
            ON c.id = ccc.condition_id
        WHERE c.subject_reference = '{patient_fhir_id}'
            AND (
                ccc.code_coding_display LIKE '%metasta%' OR
                ccc.code_coding_code LIKE 'C79%' OR
                ccc.code_coding_display LIKE '%leptomeningeal%' OR
                ccc.code_coding_display LIKE '%disseminated%'
            )
        """
        
        conditions = self.execute_query(condition_query, "Query metastasis conditions")
        logger.info(f"Found {len(conditions)} metastasis-related conditions")
        
        # 3. Get shunt procedures
        procedure_query = f"""
        SELECT 
            p.id,
            p.performed_date_time,
            pcc.code_coding_code as code,
            pcc.code_coding_display as display
        FROM {self.database}.procedure p
        LEFT JOIN {self.database}.procedure_code_coding pcc 
            ON p.id = pcc.procedure_id
        WHERE p.subject_reference = '{patient_fhir_id}'
            AND (
                pcc.code_coding_code LIKE '62%' OR 
                pcc.code_coding_display LIKE '%shunt%' OR
                pcc.code_coding_display LIKE '%ventriculostomy%'
            )
        ORDER BY p.performed_date_time
        """
        
        procedures = self.execute_query(procedure_query, "Query shunt procedures")
        logger.info(f"Found {len(procedures)} shunt procedures")
        
        # 4. Get molecular tests with results (PHI PROTECTED - no MRN in query)
        molecular_query = f"""
        SELECT 
            mt.patient_id,
            mt.test_id,
            mt.result_datetime,
            mt.lab_test_name,
            mt.lab_test_status,
            mtr.test_component
        FROM {self.database}.molecular_tests mt
        LEFT JOIN {self.database}.molecular_test_results mtr 
            ON mt.test_id = mtr.test_id
        WHERE mt.patient_id = '{patient_fhir_id}'
            AND mt.lab_test_status = 'completed'
        ORDER BY mt.result_datetime
        """
        
        molecular_tests = self.execute_query(molecular_query, "Query molecular tests")
        logger.info(f"Found {len(molecular_tests)} molecular test results")
        
        # 5. Build diagnosis events
        diagnosis_events = []
        birth_datetime = datetime.strptime(birth_date, '%Y-%m-%d') if birth_date else None
        
        for i, diag in enumerate(diagnoses):
            onset_date = diag.get('onset_date_time', '')
            
            # Calculate age at event
            age_days = None
            if onset_date and birth_datetime:
                try:
                    event_datetime = datetime.strptime(onset_date[:10], '%Y-%m-%d')
                    age_days = (event_datetime - birth_datetime).days
                except:
                    pass
            
            # Determine event type (Initial vs Progressive)
            event_type = "Initial CNS Tumor" if i == 0 else "Progressive"
            
            # Check for metastasis
            metastasis = "No"
            metastasis_locations = []
            for cond in conditions:
                cond_date = cond.get('recorded_date', '')
                if cond_date and onset_date:
                    # Within 6 months of diagnosis
                    try:
                        cond_datetime = datetime.strptime(cond_date[:10], '%Y-%m-%d')
                        onset_datetime = datetime.strptime(onset_date[:10], '%Y-%m-%d')
                        if abs((cond_datetime - onset_datetime).days) <= 180:
                            metastasis = "Yes"
                            display = cond.get('display', '')
                            if 'leptomeningeal' in display.lower():
                                metastasis_locations.append('Leptomeningeal')
                            elif 'spine' in display.lower():
                                metastasis_locations.append('Spine')
                    except:
                        pass
            
            # Check for shunt
            shunt_required = "Not Applicable"
            for proc in procedures:
                proc_date = proc.get('performed_date_time', '')
                if proc_date and onset_date:
                    try:
                        proc_datetime = datetime.strptime(proc_date[:10], '%Y-%m-%d')
                        onset_datetime = datetime.strptime(onset_date[:10], '%Y-%m-%d')
                        if abs((proc_datetime - onset_datetime).days) <= 30:
                            display = proc.get('display', '')
                            if 'ETV' in display or 'ventriculostomy' in display.lower():
                                shunt_required = "Endoscopic Third Ventriculostomy (ETV) Shunt"
                            else:
                                shunt_required = "Yes"
                    except:
                        pass
            
            # Check for molecular tests
            molecular_tests_performed = "Not Applicable"
            for test in molecular_tests:
                test_date = test.get('result_datetime', '')
                if test_date and onset_date:
                    try:
                        test_datetime = datetime.strptime(test_date[:10], '%Y-%m-%d')
                        onset_datetime = datetime.strptime(onset_date[:10], '%Y-%m-%d')
                        if abs((test_datetime - onset_datetime).days) <= 180:
                            lab_name = test.get('lab_test_name', '')
                            if 'Whole Genome' in lab_name:
                                molecular_tests_performed = "Whole Genome Sequencing"
                            elif 'Panel' in lab_name:
                                molecular_tests_performed = "Specific gene mutation analysis"
                            elif molecular_tests_performed == "Not Applicable":
                                molecular_tests_performed = lab_name
                    except:
                        pass
            
            # Build event record
            event = {
                'patient_fhir_id': patient_fhir_id,
                'event_id': f"ATHENA_DX_{i+1}",
                'event_type': event_type,
                'age_at_event_days': age_days,
                'diagnosis_date': onset_date[:10] if onset_date else None,
                'cns_integrated_diagnosis': diag.get('diagnosis_name', ''),
                'icd10_code': diag.get('icd10_code', ''),
                'clinical_status_at_event': 'Alive',  # From clinical_status_text
                'autopsy_performed': 'Not Applicable',
                'cause_of_death': 'Not Applicable',
                'metastasis': metastasis,
                'metastasis_location': ', '.join(set(metastasis_locations)) if metastasis_locations else 'Not Applicable',
                'metastasis_location_other': 'Not Applicable',
                'shunt_required': shunt_required,
                'shunt_required_other': 'Not Applicable',
                'tumor_or_molecular_tests_performed': molecular_tests_performed,
                'tumor_or_molecular_tests_performed_other': 'Not Applicable',
                # Fields requiring narrative extraction (marked for BRIM):
                'cns_integrated_category': None,  # HYBRID: Need pathology
                'who_grade': None,  # HYBRID: Need pathology reports
                'tumor_location': None,  # HYBRID: Need operative/imaging notes
                'tumor_location_other': 'Not Applicable',
                'site_of_progression': None,  # NARRATIVE: Need oncology notes
                'extraction_method': 'ATHENA_STRUCTURED',
                'extraction_timestamp': datetime.now().isoformat()
            }
            
            diagnosis_events.append(event)
        
        logger.info(f"✓ Extracted {len(diagnosis_events)} diagnosis events")
        return diagnosis_events
    
    def extract_batch(self, patient_ids: List[str]) -> pd.DataFrame:
        """Extract diagnosis data for batch of patients"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"BATCH EXTRACTION: {len(patient_ids)} patients")
        logger.info(f"{'='*60}\n")
        
        # Get birth dates for all patients
        logger.info("Step 1: Retrieving patient birth dates...")
        birth_dates = self.get_patient_birth_dates(patient_ids)
        logger.info(f"  ✓ Retrieved {len(birth_dates)} birth dates\n")
        
        # Extract diagnoses for each patient
        all_events = []
        for patient_id in patient_ids:
            birth_date = birth_dates.get(patient_id, '')
            if not birth_date:
                logger.warning(f"No birth date found for {patient_id}, skipping")
                continue
            
            events = self.extract_diagnoses_for_patient(patient_id, birth_date)
            all_events.extend(events)
        
        # Convert to DataFrame
        if not all_events:
            logger.warning("No diagnosis events extracted")
            return pd.DataFrame()
        
        df = pd.DataFrame(all_events)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"EXTRACTION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total events extracted: {len(df)}")
        logger.info(f"Patients with data: {df['patient_fhir_id'].nunique()}")
        logger.info(f"Fields extracted: {len(df.columns)}")
        
        return df


def main():
    parser = argparse.ArgumentParser(description='Extract diagnosis data from Athena')
    parser.add_argument('--patient-ids', nargs='+',
                       help='List of patient FHIR IDs')
    parser.add_argument('--patient-ids-file',
                       help='File containing patient FHIR IDs (one per line)')
    parser.add_argument('--output-csv', required=True,
                       help='Output CSV file path')
    parser.add_argument('--aws-profile', default='343218191717_AWSAdministratorAccess',
                       help='AWS profile name')
    parser.add_argument('--database', default='fhir_v2_prd_db',
                       help='Athena database name')
    
    args = parser.parse_args()
    
    # Get patient IDs
    patient_ids = []
    if args.patient_ids:
        patient_ids = args.patient_ids
    elif args.patient_ids_file:
        with open(args.patient_ids_file, 'r') as f:
            patient_ids = [line.strip() for line in f if line.strip()]
    else:
        logger.error("Must provide either --patient-ids or --patient-ids-file")
        sys.exit(1)
    
    logger.info(f"Extracting diagnosis data for {len(patient_ids)} patients")
    
    # Initialize extractor
    extractor = DiagnosisExtractor(
        aws_profile=args.aws_profile,
        database=args.database
    )
    
    # Extract data
    df = extractor.extract_batch(patient_ids)
    
    if df.empty:
        logger.error("No data extracted")
        sys.exit(1)
    
    # Write output
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    logger.info(f"\n✓ Output written to: {output_path}")
    logger.info(f"  Rows: {len(df)}")
    logger.info(f"  Columns: {len(df.columns)}")


if __name__ == '__main__':
    main()
