#!/usr/bin/env python3
"""
Extract Problem List Diagnoses from problem_list_diagnoses table (Config-Driven)

Creates a staging file with all diagnosis/condition data from problem_list_diagnoses materialized view.
⚠️ EXCLUDES MRN for PHI protection - only includes FHIR ID and diagnosis data.

KEY FEATURES:
- Config-driven patient identification via patient_config.json
- Extracts from problem_list_diagnoses materialized view
- NO MRN included in output (PHI protection)
- Complete diagnosis metadata (codes, dates, status)
- Age at diagnosis calculation from birth_date
- Sorted by recorded_date for temporal analysis

TABLES USED:
- fhir_v2_prd_db.problem_list_diagnoses: Materialized view with diagnosis data from condition table

OUTPUT COLUMNS:
1. patient_fhir_id - Patient FHIR identifier
2. pld_condition_id - Condition/diagnosis FHIR ID
3. pld_diagnosis_name - Human-readable diagnosis name
4. pld_clinical_status - Clinical status (active, resolved, etc.)
5. pld_onset_date - Date diagnosis first noted
6. age_at_onset_days - Age at onset in days
7. pld_abatement_date - Date diagnosis resolved/abated
8. pld_recorded_date - Date diagnosis was recorded
9. age_at_recorded_days - Age when recorded in days
10. pld_icd10_code - ICD-10 diagnosis code
11. pld_icd10_display - ICD-10 code display text
12. pld_snomed_code - SNOMED CT concept code
13. pld_snomed_display - SNOMED CT display text

Usage:
    python3 extract_problem_list_diagnoses.py <config_path> <output_dir>
    
Example:
    python3 extract_problem_list_diagnoses.py ../../patient_config.json ../../staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/
"""

import boto3
import pandas as pd
import time
import json
import logging
from datetime import datetime
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def execute_athena_query(athena_client, query, description, database, output_location):
    """Execute Athena query and wait for completion"""
    logger.info(f"Executing query: {description}")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location}
        )
        
        query_id = response['QueryExecutionId']
        logger.info(f"Query ID: {query_id}")
        
        # Wait for query completion
        max_attempts = 60
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(2)
            attempt += 1
            
            result = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = result['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                logger.info(f"Query succeeded after {attempt * 2} seconds")
                return query_id
            elif status in ['FAILED', 'CANCELLED']:
                reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                logger.error(f"Query failed: {reason}")
                raise Exception(f"Query {status}: {reason}")
        
        raise Exception(f"Query timeout after {max_attempts * 2} seconds")
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise


def get_query_results(athena_client, query_id):
    """Retrieve query results and convert to DataFrame"""
    logger.info(f"Retrieving results for query {query_id}")
    
    try:
        results = athena_client.get_query_results(QueryExecutionId=query_id)
        
        # Extract column names
        columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        
        # Extract data rows (skip header row)
        rows = []
        for row in results['ResultSet']['Rows'][1:]:
            rows.append([col.get('VarCharValue', '') for col in row['Data']])
        
        # Handle pagination if needed
        while 'NextToken' in results:
            results = athena_client.get_query_results(
                QueryExecutionId=query_id,
                NextToken=results['NextToken']
            )
            for row in results['ResultSet']['Rows']:
                rows.append([col.get('VarCharValue', '') for col in row['Data']])
        
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Retrieved {len(df)} rows with {len(columns)} columns")
        
        return df
        
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}")
        raise


def build_problem_list_query(database, patient_id, birth_date=''):
    """
    Build SQL query for problem list diagnoses
    
    ⚠️ EXCLUDES mrn column for PHI protection
    
    Args:
        database: Database name
        patient_id: Patient FHIR ID
        birth_date: Patient birth date for age calculations (YYYY-MM-DD)
        
    Returns:
        SQL query string
    """
    
    # Age calculation SQL - use TRY to handle empty/invalid dates
    if birth_date:
        age_onset_calc = f"TRY(date_diff('day', date('{birth_date}'), CAST(substr(onset_date_time, 1, 10) AS date)))"
        age_recorded_calc = f"TRY(date_diff('day', date('{birth_date}'), CAST(substr(recorded_date, 1, 10) AS date)))"
    else:
        age_onset_calc = "NULL"
        age_recorded_calc = "NULL"
    
    query = f"""
    SELECT 
        patient_id as patient_fhir_id,
        condition_id as pld_condition_id,
        diagnosis_name as pld_diagnosis_name,
        clinical_status_text as pld_clinical_status,
        substr(onset_date_time, 1, 10) as pld_onset_date,
        {age_onset_calc} as age_at_onset_days,
        substr(abatement_date_time, 1, 10) as pld_abatement_date,
        substr(recorded_date, 1, 10) as pld_recorded_date,
        {age_recorded_calc} as age_at_recorded_days,
        icd10_code as pld_icd10_code,
        icd10_display as pld_icd10_display,
        snomed_code as pld_snomed_code,
        snomed_display as pld_snomed_display
    FROM {database}.problem_list_diagnoses
    WHERE patient_id = '{patient_id}'
    ORDER BY recorded_date, onset_date_time
    """
    
    return query


def load_patient_config(config_path):
    """Load patient configuration from JSON"""
    logger.info(f"Loading patient configuration from {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        logger.info(f"Configuration loaded successfully")
        logger.info(f"  Patient ID: {config.get('patient_id', 'NOT FOUND')}")
        logger.info(f"  Birth Date: {config.get('birth_date', 'NOT FOUND')}")
        
        return config
        
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {str(e)}")
        raise


def extract_problem_list_diagnoses(config_path, output_dir):
    """
    Main extraction function for problem list diagnoses
    
    Args:
        config_path: Path to patient_config.json
        output_dir: Directory for output CSV
        
    Returns:
        Path to generated CSV file
    """
    logger.info("="*80)
    logger.info("PROBLEM LIST DIAGNOSES EXTRACTION - Config-Driven Version")
    logger.info("="*80)
    
    # Load configuration
    config = load_patient_config(config_path)
    patient_id = config['patient_id']
    birth_date = config.get('birth_date', '')
    
    # AWS Configuration
    aws_profile = '343218191717_AWSAdministratorAccess'
    database = 'fhir_v2_prd_db'
    s3_output = 's3://aws-athena-query-results-343218191717-us-east-1/'
    region = 'us-east-1'
    
    logger.info(f"\nConfiguration:")
    logger.info(f"  Patient ID: {patient_id}")
    logger.info(f"  Birth Date: {birth_date}")
    logger.info(f"  AWS Profile: {aws_profile}")
    logger.info(f"  Database: {database}")
    logger.info(f"  Region: {region}")
    
    # Initialize AWS session
    session = boto3.Session(profile_name=aws_profile)
    athena_client = session.client('athena', region_name=region)
    
    # Build and execute query
    logger.info("\n" + "="*80)
    logger.info("EXECUTING PROBLEM LIST QUERY")
    logger.info("="*80)
    
    query = build_problem_list_query(database, patient_id, birth_date)
    query_id = execute_athena_query(
        athena_client, 
        query, 
        "Extract problem list diagnoses",
        database,
        s3_output
    )
    
    # Get results
    df = get_query_results(athena_client, query_id)
    
    if len(df) == 0:
        logger.warning("⚠️  No diagnoses found for patient")
        # Create empty file with headers
        df = pd.DataFrame(columns=[
            'patient_fhir_id', 'pld_condition_id', 'pld_diagnosis_name',
            'pld_clinical_status',
            'pld_onset_date', 'age_at_onset_days', 'pld_abatement_date',
            'pld_recorded_date', 'age_at_recorded_days',
            'pld_icd10_code', 'pld_icd10_display',
            'pld_snomed_code', 'pld_snomed_display'
        ])
    
    # Save output
    output_path = Path(output_dir) / 'problem_list_diagnoses.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    
    logger.info("\n" + "="*80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*80)
    logger.info(f"✓ Output saved to: {output_path}")
    logger.info(f"✓ Total rows: {len(df)}")
    logger.info(f"✓ Total columns: {len(df.columns)}")
    
    if len(df) > 0:
        logger.info(f"\n📊 Diagnosis Summary:")
        logger.info(f"   Total diagnoses: {len(df)}")
        logger.info(f"   Date range: {df['pld_recorded_date'].min()} to {df['pld_recorded_date'].max()}")
        logger.info(f"   Active diagnoses: {len(df[df['pld_clinical_status'] == 'active'])}")
        
        # Show top diagnosis codes
        if 'pld_icd10_code' in df.columns:
            top_codes = df['pld_icd10_code'].value_counts().head(5)
            if len(top_codes) > 0:
                logger.info(f"\n   Top ICD-10 codes:")
                for code, count in top_codes.items():
                    logger.info(f"     {code}: {count}")
    
    logger.info(f"\n✅ SUCCESS: Problem list extracted to {output_path}")
    
    return output_path


def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: python3 extract_problem_list_diagnoses.py <config_path> <output_dir>")
        print("\nExample:")
        print("  python3 extract_problem_list_diagnoses.py ../../patient_config.json ../../staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/")
        sys.exit(1)
    
    config_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    try:
        extract_problem_list_diagnoses(config_path, output_dir)
    except Exception as e:
        logger.error(f"❌ Extraction failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
