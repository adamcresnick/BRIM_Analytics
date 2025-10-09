#!/usr/bin/env python3
import boto3, time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

query = """
SELECT COUNT(*) as count
FROM fhir_v2_prd_db.patient_medications
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': 'fhir_v2_prd_db'},
    ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
)

while True:
    status = athena.get_query_execution(QueryExecutionId=response['QueryExecutionId'])
    state = status['QueryExecution']['Status']['State']
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break
    time.sleep(1)

if state == 'SUCCEEDED':
    results = athena.get_query_results(QueryExecutionId=response['QueryExecutionId'])
    count = results['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
    print(f"✓ patient_medications: {count} records for C1277724")
