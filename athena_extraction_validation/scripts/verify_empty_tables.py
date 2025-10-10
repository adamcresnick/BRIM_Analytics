#!/usr/bin/env python3
"""
Verify if medication_form_coding and medication_ingredient tables exist
and check if they're empty for ALL patients or just C1277724
"""

import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

def run_query(query, description):
    print(f"\n{description}")
    print("="*80)
    
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_v2_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
    )
    
    query_id = response['QueryExecutionId']
    
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(0.5)
    
    if state == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_id)
        rows = results['ResultSet']['Rows']
        
        if len(rows) > 1:
            # Get column names
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            # Get first data row
            data = [col.get('VarCharValue', 'NULL') for col in rows[1]['Data']]
            
            for col, val in zip(columns, data):
                print(f"  {col}: {val}")
            return True
        else:
            print("  ✗ No data returned")
            return False
    else:
        error = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"  ✗ Query failed: {error}")
        return False

# Test 1: Check if tables exist by describing them
print("\n" + "#"*80)
print("# VERIFYING medication_form_coding TABLE")
print("#"*80)

describe_form = "DESCRIBE fhir_v2_prd_db.medication_form_coding"
run_query(describe_form, "Table Structure:")

# Test 2: Check total row count
count_form = "SELECT COUNT(*) as total_rows FROM fhir_v2_prd_db.medication_form_coding"
run_query(count_form, "Total Rows in Table (all patients):")

# Test 3: Check if there are ANY records for any patient
sample_form = "SELECT * FROM fhir_v2_prd_db.medication_form_coding LIMIT 1"
run_query(sample_form, "Sample Row (any patient):")

print("\n" + "#"*80)
print("# VERIFYING medication_ingredient TABLE")
print("#"*80)

describe_ingredient = "DESCRIBE fhir_v2_prd_db.medication_ingredient"
run_query(describe_ingredient, "Table Structure:")

count_ingredient = "SELECT COUNT(*) as total_rows FROM fhir_v2_prd_db.medication_ingredient"
run_query(count_ingredient, "Total Rows in Table (all patients):")

sample_ingredient = "SELECT * FROM fhir_v2_prd_db.medication_ingredient LIMIT 1"
run_query(sample_ingredient, "Sample Row (any patient):")

print("\n" + "#"*80)
print("# SUMMARY")
print("#"*80)
print("\nConclusion:")
print("- If DESCRIBE succeeds: Table exists")
print("- If COUNT returns 0: Table is completely empty (all patients)")
print("- If COUNT > 0 but C1277724 has 0: Data exists but not for this patient")
print("- If DESCRIBE fails: Table doesn't exist")
