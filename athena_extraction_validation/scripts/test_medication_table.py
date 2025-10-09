#!/usr/bin/env python3
"""
Quick test to verify medication_request table exists and has data
"""

import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

query = """
SELECT COUNT(*) as count
FROM fhir_v2_prd_db.medication_request
WHERE subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

print("Testing medication_request table...")
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
    count = results['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
    print(f"✓ medication_request table exists!")
    print(f"✓ Found {count} medication records for patient C1277724")
else:
    print(f"✗ Query failed: {state}")
