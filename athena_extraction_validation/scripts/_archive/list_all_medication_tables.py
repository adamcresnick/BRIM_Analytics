#!/usr/bin/env python3
"""
Direct test to find medication tables
"""

import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

# Try to list ALL tables
query = "SHOW TABLES IN fhir_v2_prd_db"

print("Fetching all tables in fhir_v2_prd_db...")
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
    time.sleep(1)

if state == 'SUCCEEDED':
    results = athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
    tables = [row['Data'][0]['VarCharValue'] for row in results['ResultSet']['Rows'][1:]]
    
    # Filter for medication-related
    med_tables = [t for t in tables if 'medication' in t.lower()]
    
    print(f"\nFound {len(med_tables)} medication-related tables:")
    for t in sorted(med_tables):
        print(f"  - {t}")
else:
    print(f"Failed: {state}")
