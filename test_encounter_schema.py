#!/usr/bin/env python3
"""Quick test to find encounter table schema"""
import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')
database = 'fhir_v2_prd_db'
output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'

query = "SELECT * FROM fhir_v2_prd_db.encounter LIMIT 1"

response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': database},
    ResultConfiguration={'OutputLocation': output_location}
)

query_id = response['QueryExecutionId']

while True:
    status = athena.get_query_execution(QueryExecutionId=query_id)
    state = status['QueryExecution']['Status']['State']
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break
    time.sleep(1)

if state == 'SUCCEEDED':
    results = athena.get_query_results(QueryExecutionId=query_id)
    columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
    print("Encounter table columns:")
    for i, col in enumerate(columns, 1):
        print(f"  {i}. {col}")
else:
    print(f"Query failed: {status['QueryExecution']['Status']}")
