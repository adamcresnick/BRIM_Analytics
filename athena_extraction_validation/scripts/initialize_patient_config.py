#!/usr/bin/env python3
"""
Initialize patient_config.json with demographics from FHIR patient table.

This script queries the FHIR patient table to retrieve:
- FHIR ID
- Birth date
- Gender

Usage:
    python3 initialize_patient_config.py <patient_fhir_id>
    
Example:
    python3 initialize_patient_config.py e4BwD8ZYDBccepXcJ.Ilo3w3
"""

import sys
import json
import boto3
import time
from pathlib import Path
from datetime import datetime

# Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
REGION = 'us-east-1'
DATABASE = 'fhir_v2_prd_db'
S3_OUTPUT = 's3://aws-athena-query-results-343218191717-us-east-1/'


def query_patient_demographics(patient_fhir_id):
    """
    Query the patient table for demographics.
    
    Args:
        patient_fhir_id: FHIR ID of the patient
        
    Returns:
        dict with id, birth_date, gender or None if not found
    """
    print(f"\n{'='*80}")
    print(f"QUERYING PATIENT DEMOGRAPHICS FROM FHIR")
    print(f"{'='*80}\n")
    
    # Initialize Athena client
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    athena = session.client('athena')
    
    query = f"""
    SELECT id, birth_date, gender 
    FROM {DATABASE}.patient 
    WHERE id = '{patient_fhir_id}'
    LIMIT 1
    """
    
    print(f"Patient FHIR ID: {patient_fhir_id}")
    print(f"Database: {DATABASE}")
    print(f"Executing query...")
    
    # Execute query
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': DATABASE},
        ResultConfiguration={'OutputLocation': S3_OUTPUT}
    )
    
    query_id = response['QueryExecutionId']
    print(f"Query ID: {query_id}")
    
    # Wait for query to complete
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status['QueryExecution']['Status']['State']
        
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)
    
    if state == 'FAILED':
        reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        print(f"❌ Query failed: {reason}")
        return None
    elif state == 'CANCELLED':
        print(f"❌ Query was cancelled")
        return None
    
    # Get results
    results = athena.get_query_results(QueryExecutionId=query_id)
    rows = results['ResultSet']['Rows']
    
    if len(rows) < 2:  # First row is header
        print(f"❌ No patient found with ID: {patient_fhir_id}")
        return None
    
    # Parse results (skip header row)
    data_row = rows[1]['Data']
    demographics = {
        'id': data_row[0].get('VarCharValue'),
        'birth_date': data_row[1].get('VarCharValue'),
        'gender': data_row[2].get('VarCharValue')
    }
    
    print(f"\n✅ Patient found:")
    print(f"   FHIR ID: {demographics['id']}")
    print(f"   Birth Date: {demographics['birth_date']}")
    print(f"   Gender: {demographics['gender']}")
    
    return demographics


def create_patient_config(demographics):
    """
    Create patient_config.json from demographics.
    
    Args:
        demographics: dict with id, birth_date, gender
    """
    # Extract short ID for directory name
    # Use the full ID if no hyphen, don't truncate based on character count
    short_id = demographics['id'].split('-')[0] if '-' in demographics['id'] else demographics['id']
    
    # Get absolute path to staging_files directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent  # athena_extraction_validation directory
    staging_dir = project_root / 'staging_files' / f'patient_{short_id}'
    
    config = {
        "fhir_id": demographics['id'],
        "birth_date": demographics['birth_date'],
        "gender": demographics['gender'],
        "output_dir": str(staging_dir),  # Use absolute path
        "database": DATABASE,
        "aws_profile": AWS_PROFILE,
        "s3_output": S3_OUTPUT
    }
    
    # Get path to athena_extraction_validation directory
    script_dir = Path(__file__).parent
    config_file = script_dir.parent / 'patient_config.json'
    
    # Write config file
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Created config file: {config_file}")
    print(f"\nConfig contents:")
    print(json.dumps(config, indent=2))
    
    return config_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 initialize_patient_config.py <patient_fhir_id>")
        print("\nExample:")
        print("  python3 initialize_patient_config.py e4BwD8ZYDBccepXcJ.Ilo3w3")
        sys.exit(1)
    
    patient_fhir_id = sys.argv[1]
    
    # Query demographics
    demographics = query_patient_demographics(patient_fhir_id)
    
    if not demographics:
        print("\n❌ Failed to retrieve patient demographics")
        sys.exit(1)
    
    # Create config
    config_file = create_patient_config(demographics)
    
    print(f"\n{'='*80}")
    print(f"NEXT STEPS")
    print(f"{'='*80}\n")
    print(f"1. Review the config file: {config_file}")
    print(f"2. Run config-driven extraction scripts:")
    print(f"   cd scripts/config_driven_versions")
    print(f"   python3 extract_all_encounters_metadata.py")
    print(f"   python3 extract_all_medications_metadata.py")
    print(f"   python3 extract_all_procedures_metadata.py")
    print(f"   python3 extract_all_imaging_metadata.py")
    print(f"   python3 extract_all_laboratory_metadata.py")
    print(f"   python3 extract_diagnoses.py")
    print(f"   python3 extract_surgical_history.py")
    print(f"   python3 extract_radiation_data.py")
    print(f"\n3. Check output: staging_files/patient_{patient_fhir_id.split('-')[0] if '-' in patient_fhir_id else patient_fhir_id[:22]}/")
    

if __name__ == '__main__':
    main()
