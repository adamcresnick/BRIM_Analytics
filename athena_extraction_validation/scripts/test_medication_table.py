#!/usr/bin/env python3
"""
Quick test to verify medication_request table exists and has data
"""

import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

# Test 1: medication_request with Patient/ prefix
query1 = """
SELECT COUNT(*) as count
FROM fhir_v2_prd_db.medication_request
WHERE subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

# Test 2: medication_request without prefix
query2 = """
SELECT COUNT(*) as count
FROM fhir_v2_prd_db.medication_request
WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

# Test 3: medication_request with patient_id column
query3 = """
SELECT COUNT(*) as count
FROM fhir_v2_prd_db.medication_request
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

# Test 4: medications table (plural)
query4 = """
SELECT COUNT(*) as count
FROM fhir_v2_prd_db.medications
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

queries = [
    ("medication_request (with Patient/ prefix)", query1),
    ("medication_request (without prefix)", query2),
    ("medication_request (patient_id column)", query3),
    ("medications table (patient_id column)", query4)
]

for name, query in queries:
    print(f"\nTesting {name}...")
    try:
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': 'fhir_v2_prd_db'},
            ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait
        while True:
            status = athena.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(1)
        
        if state == 'SUCCEEDED':
            results = athena.get_query_results(QueryExecutionId=query_id)
            if len(results['ResultSet']['Rows']) > 1:
                count = results['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
                print(f"  ✓ Table exists! Found {count} medication records")
            else:
                print(f"  ✓ Table exists but no data rows")
        else:
            error_msg = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"  ✗ Query failed: {error_msg[:100]}")
    except Exception as e:
        print(f"  ✗ Error: {str(e)[:100]}")

print("\n" + "="*60)
print("Testing complete!")
