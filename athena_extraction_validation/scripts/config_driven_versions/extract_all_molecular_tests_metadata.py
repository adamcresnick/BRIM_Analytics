#!/usr/bin/env python3
"""
Extract ALL Molecular Tests with Complete Metadata from Patient Configuration

This script extracts all molecular test records and joins with:
1. molecular_tests - Test metadata (who, what, when)
2. molecular_test_results - Test result components and narratives + dgd_id for linkage
3. specimen - Specimen details (type, collection date, body site) via service_request
4. encounter - Hospital encounter context
5. procedure - Surgical procedures (likely tissue source) in same encounter

KEY FEATURES:
- Config-driven patient identification via patient_config.json
- Complete test metadata from molecular_tests table
- Aggregated result metrics (component count, narrative length, component list)
- Age at test calculation from birth_date
- Specimen traceability (type, collection date, body site, accession)
- Procedure linkage (earliest surgical procedure in same encounter)
- Encounter linkage (hospital encounter context)

LINKAGE PATH:
  molecular_test_results.dgd_id 
  → service_request_identifier.identifier_value
  → service_request (specimen_reference + encounter_reference)
  → specimen (collection details)
  → procedure (via encounter_reference)

Output: molecular_tests_metadata.csv with comprehensive test + specimen + procedure information
"""

import boto3
import pandas as pd
import time
import json
import logging
from pathlib import Path
from datetime import datetime

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


def build_comprehensive_query(database, patient_id, birth_date=''):
    """
    Build comprehensive SQL query for molecular tests with specimen and result metadata
    
    Joins:
    - molecular_tests: Test metadata
    - molecular_test_results: Component-level results (aggregated) + dgd_id for specimen linkage
    - service_request: Links to specimen and encounter via dgd_id
    - specimen: Specimen details (type, collection date, body site)
    - procedure: Surgical procedures in same encounter
    
    Args:
        database: Database name
        patient_id: Patient FHIR ID
        birth_date: Patient birth date (YYYY-MM-DD) for age calculation
        
    Returns:
        SQL query string with complete molecular test metadata including specimen and procedure linkage
    """
    
    # Calculate age at test in SQL
    age_calculation = f"""
    date_diff('day', 
              date_parse('{birth_date}', '%Y-%m-%d'),
              date_parse(substr(mt.result_datetime, 1, 10), '%Y-%m-%d')
    ) as age_at_test_days
    """ if birth_date else "NULL as age_at_test_days"
    
    query = f"""
    WITH aggregated_results AS (
        -- Aggregate multiple result components per test
        SELECT 
            test_id,
            dgd_id,
            COUNT(*) as component_count,
            SUM(LENGTH(COALESCE(test_result_narrative, ''))) as total_narrative_chars,
            ARRAY_JOIN(
                ARRAY_AGG(
                    DISTINCT COALESCE(test_component, 'Unknown')
                ), 
                '; '
            ) as components_list
        FROM {database}.molecular_test_results
        WHERE test_id IN (
            SELECT test_id 
            FROM {database}.molecular_tests 
            WHERE patient_id = '{patient_id}'
        )
        GROUP BY test_id, dgd_id
    ),
    
    specimen_linkage AS (
        -- Link molecular tests to specimens via service_request
        SELECT DISTINCT
            ar.test_id,
            ar.dgd_id,
            sri.service_request_id,
            sr.encounter_reference,
            REPLACE(sr.encounter_reference, 'Encounter/', '') AS encounter_id,
            REPLACE(srs.specimen_reference, 'Specimen/', '') AS specimen_id,
            s.type_text AS specimen_type,
            s.collection_collected_date_time AS specimen_collection_date,
            s.collection_body_site_text AS specimen_body_site,
            s.accession_identifier_value AS specimen_accession
        FROM aggregated_results ar
        LEFT JOIN fhir_prd_db.service_request_identifier sri 
            ON ar.dgd_id = sri.identifier_value
        LEFT JOIN fhir_prd_db.service_request sr 
            ON sri.service_request_id = sr.id
        LEFT JOIN fhir_prd_db.service_request_specimen srs 
            ON sr.id = srs.service_request_id
        LEFT JOIN fhir_prd_db.specimen s 
            ON REPLACE(srs.specimen_reference, 'Specimen/', '') = s.id
    ),
    
    procedure_linkage AS (
        -- Get earliest surgical procedure per encounter (likely tissue collection)
        SELECT 
            sl.test_id,
            MIN(p.id) AS procedure_id,
            MIN(p.code_text) AS procedure_name,
            MIN(p.performed_date_time) AS procedure_date,
            MIN(p.status) AS procedure_status
        FROM specimen_linkage sl
        LEFT JOIN fhir_prd_db.procedure p 
            ON sl.encounter_id = REPLACE(p.encounter_reference, 'Encounter/', '')
            AND p.subject_reference LIKE '%{patient_id}%'
            AND p.code_text LIKE '%SURGICAL%'
        WHERE sl.encounter_id IS NOT NULL
        GROUP BY sl.test_id
    )
    
    SELECT 
        -- Patient context (no MRN for PHI protection)
        '{patient_id}' as patient_fhir_id,
        
        -- Test identification
        mt.test_id as mt_test_id,
        
        -- Temporal fields
        substr(mt.result_datetime, 1, 10) as mt_test_date,
        {age_calculation},
        
        -- Test metadata from molecular_tests
        mt.lab_test_name as mt_lab_test_name,
        mt.lab_test_status as mt_test_status,
        mt.lab_test_requester as mt_test_requester,
        
        -- Aggregated result metadata
        COALESCE(ar.component_count, 0) as mtr_component_count,
        COALESCE(ar.total_narrative_chars, 0) as mtr_total_narrative_chars,
        COALESCE(ar.components_list, 'None') as mtr_components_list,
        
        -- Specimen linkage fields (NEW)
        sl.specimen_id as mt_specimen_id,
        sl.specimen_type as mt_specimen_type,
        substr(sl.specimen_collection_date, 1, 10) as mt_specimen_collection_date,
        sl.specimen_body_site as mt_specimen_body_site,
        sl.specimen_accession as mt_specimen_accession,
        
        -- Encounter linkage (NEW)
        sl.encounter_id as mt_encounter_id,
        
        -- Procedure linkage fields (NEW)
        pl.procedure_id as mt_procedure_id,
        pl.procedure_name as mt_procedure_name,
        substr(pl.procedure_date, 1, 10) as mt_procedure_date,
        pl.procedure_status as mt_procedure_status
        
    FROM {database}.molecular_tests mt
    LEFT JOIN aggregated_results ar ON mt.test_id = ar.test_id
    LEFT JOIN specimen_linkage sl ON mt.test_id = sl.test_id
    LEFT JOIN procedure_linkage pl ON mt.test_id = pl.test_id
    WHERE mt.patient_id = '{patient_id}'
    ORDER BY mt.result_datetime, mt.test_id
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


def extract_molecular_tests(config_path, output_dir):
    """
    Main extraction function for molecular tests
    
    Args:
        config_path: Path to patient_config.json
        output_dir: Directory for output CSV
        
    Returns:
        Path to generated CSV file
    """
    logger.info("="*80)
    logger.info("MOLECULAR TESTS METADATA EXTRACTION - Config-Driven Version")
    logger.info("="*80)
    
    # Load configuration
    config = load_patient_config(config_path)
    patient_id = config['patient_id']
    birth_date = config.get('birth_date', '')
    
    # AWS configuration
    aws_profile = config.get('aws_profile', '343218191717_AWSAdministratorAccess')
    database = config.get('database', 'fhir_v2_prd_db')
    region = config.get('region', 'us-east-1')
    output_bucket = config.get('output_bucket', 'aws-athena-query-results-343218191717-us-east-1')
    
    output_location = f's3://{output_bucket}/'
    
    logger.info(f"\nConfiguration:")
    logger.info(f"  Patient ID: {patient_id}")
    logger.info(f"  Birth Date: {birth_date}")
    logger.info(f"  AWS Profile: {aws_profile}")
    logger.info(f"  Database: {database}")
    logger.info(f"  Region: {region}")
    
    # Initialize AWS clients
    session = boto3.Session(profile_name=aws_profile)
    athena_client = session.client('athena', region_name=region)
    
    # Build and execute query
    query = build_comprehensive_query(database, patient_id, birth_date)
    
    logger.info("\n" + "="*80)
    logger.info("EXECUTING MOLECULAR TESTS QUERY")
    logger.info("="*80)
    
    query_id = execute_athena_query(
        athena_client,
        query,
        "Extract molecular tests metadata",
        database,
        output_location
    )
    
    # Get results
    df = get_query_results(athena_client, query_id)
    
    # Post-process: Add derived fields
    # Save output
    output_path = Path(output_dir) / 'molecular_tests_metadata.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    
    logger.info("\n" + "="*80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*80)
    logger.info(f"✓ Output saved to: {output_path}")
    logger.info(f"✓ Total rows: {len(df)}")
    logger.info(f"✓ Total columns: {len(df.columns)}")
    
    if len(df) > 0:
        logger.info(f"✓ Date range: {df['mt_test_date'].min()} to {df['mt_test_date'].max()}")
        total_chars = int(df['mtr_total_narrative_chars'].sum())
        logger.info(f"✓ Total narrative characters: {total_chars:,}")
    
    logger.info("\nColumn List:")
    for i, col in enumerate(df.columns, 1):
        logger.info(f"  {i:2d}. {col}")
    
    return output_path


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python3 extract_all_molecular_tests_metadata.py <config_path> <output_dir>")
        print("\nExample:")
        print("  python3 scripts/config_driven_versions/extract_all_molecular_tests_metadata.py \\")
        print("    patient_config.json \\")
        print("    staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/")
        sys.exit(1)
    
    config_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    try:
        output_file = extract_molecular_tests(config_path, output_dir)
        logger.info(f"\n✅ SUCCESS: Molecular tests extracted to {output_file}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
