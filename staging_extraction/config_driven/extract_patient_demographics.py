#!/usr/bin/env python3
"""
Extract Patient Demographics from patient_access table (Config-Driven)

Creates a staging file with patient demographics from patient_access materialized view.
⚠️ EXCLUDES MRN for PHI protection - only includes FHIR ID and non-identifying demographics.

KEY FEATURES:
- Config-driven patient identification via patient_config.json
- Extracts from patient_access materialized view
- NO MRN included in output (PHI protection)
- Includes: id, gender, birth_date, race, ethnicity, language, deceased status
- Age calculation from birth_date
- Single-row output per patient

TABLES USED:
- fhir_prd_db.patient_access: Materialized view with patient demographics

OUTPUT COLUMNS:
1. patient_fhir_id - Patient FHIR identifier
2. pd_gender - Patient gender (male/female/other/unknown)
3. pd_birth_date - Date of birth (YYYY-MM-DD)
4. pd_age_years - Current age in years
5. pd_race - Patient race
6. pd_ethnicity - Patient ethnicity

Usage:
    python3 extract_patient_demographics.py <config_path> <output_dir>
    
Example:
    python3 extract_patient_demographics.py ../../patient_config.json ../../staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/
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
        max_attempts = 30
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(1)
            attempt += 1
            
            result = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = result['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                logger.info(f"Query succeeded after {attempt} seconds")
                return query_id
            elif status in ['FAILED', 'CANCELLED']:
                reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                logger.error(f"Query failed: {reason}")
                raise Exception(f"Query {status}: {reason}")
        
        raise Exception(f"Query timeout after {max_attempts} seconds")
        
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
        
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Retrieved {len(df)} rows with {len(columns)} columns")
        
        return df
        
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}")
        raise


def calculate_age_years(birth_date):
    """Calculate age in years from birth date"""
    if not birth_date or pd.isna(birth_date) or birth_date == '':
        return None
    
    try:
        birth = datetime.strptime(birth_date, '%Y-%m-%d')
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age
    except:
        return None


def build_demographics_query(database, patient_id):
    """
    Build SQL query for patient demographics
    
    ⚠️ EXCLUDES mrn column for PHI protection
    
    Args:
        database: Database name
        patient_id: Patient FHIR ID
        
    Returns:
        SQL query string
    """
    
    query = f"""
    SELECT 
        id as patient_fhir_id,
        gender as pd_gender,
        birth_date as pd_birth_date,
        race as pd_race,
        ethnicity as pd_ethnicity
    FROM {database}.patient_access
    WHERE id = '{patient_id}'
    LIMIT 1
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


def extract_demographics(config_path, output_dir):
    """
    Main extraction function for patient demographics
    
    Args:
        config_path: Path to patient_config.json
        output_dir: Directory for output CSV
        
    Returns:
        Path to generated CSV file
    """
    logger.info("="*80)
    logger.info("PATIENT DEMOGRAPHICS EXTRACTION - Config-Driven Version")
    logger.info("="*80)
    
    # Load configuration
    config = load_patient_config(config_path)
    patient_id = config['patient_id']
    birth_date = config.get('birth_date', '')
    
    # AWS Configuration
    aws_profile = '343218191717_AWSAdministratorAccess'
    database = 'fhir_prd_db'
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
    logger.info("EXECUTING DEMOGRAPHICS QUERY")
    logger.info("="*80)
    
    query = build_demographics_query(database, patient_id)
    query_id = execute_athena_query(
        athena_client, 
        query, 
        "Extract patient demographics",
        database,
        s3_output
    )
    
    # Get results
    df = get_query_results(athena_client, query_id)
    
    if len(df) == 0:
        logger.warning("⚠️  No demographics found for patient")
        return None
    
    # Add calculated age
    if birth_date:
        df['pd_age_years'] = calculate_age_years(birth_date)
    else:
        df['pd_age_years'] = df['pd_birth_date'].apply(calculate_age_years)
    
    # Reorder columns to put age after birth_date
    cols = ['patient_fhir_id', 'pd_gender', 'pd_birth_date', 'pd_age_years', 
            'pd_race', 'pd_ethnicity']
    df = df[cols]
    
    # Save output
    output_path = Path(output_dir) / 'patient_demographics.csv'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    
    logger.info("\n" + "="*80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*80)
    logger.info(f"✓ Output saved to: {output_path}")
    logger.info(f"✓ Total rows: {len(df)}")
    logger.info(f"✓ Total columns: {len(df.columns)}")
    
    # Log demographics summary (NO MRN)
    logger.info(f"\n📊 Demographics Summary:")
    logger.info(f"   Gender: {df['pd_gender'].iloc[0]}")
    logger.info(f"   Age: {df['pd_age_years'].iloc[0]} years")
    logger.info(f"   Race: {df['pd_race'].iloc[0]}")
    logger.info(f"   Ethnicity: {df['pd_ethnicity'].iloc[0]}")
    
    logger.info(f"\n✅ SUCCESS: Demographics extracted to {output_path}")
    
    return output_path


def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: python3 extract_patient_demographics.py <config_path> <output_dir>")
        print("\nExample:")
        print("  python3 extract_patient_demographics.py ../../patient_config.json ../../staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/")
        sys.exit(1)
    
    config_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    try:
        extract_demographics(config_path, output_dir)
    except Exception as e:
        logger.error(f"❌ Extraction failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
