#!/usr/bin/env python3
"""
Search for radiation treatment service requests/orders in FHIR database
"""

import boto3
import time
import pandas as pd

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

database = 'fhir_v2_prd_db'
s3_output = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Both patient FHIR IDs
patient_ids = [
    'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',  # C1277724
    'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3'  # New patient
]

print('='*80)
print('SEARCHING SERVICE_REQUEST TABLE FOR RADIATION ORDERS')
print('='*80)

# Search for radiation-related service requests
patient_list = "','".join(patient_ids)
query = f"""
SELECT DISTINCT
    sr.subject_reference as patient_id,
    sr.code_text,
    sr.status,
    sr.intent,
    sr.priority,
    sr.occurrence_date_time,
    sr.id as service_request_fhir_id
FROM {database}.service_request sr
WHERE sr.subject_reference IN ('{patient_list}')
  AND (
    LOWER(sr.code_text) LIKE '%radiation%'
    OR LOWER(sr.code_text) LIKE '%radiotherapy%'
    OR LOWER(sr.code_text) LIKE '%proton%'
    OR LOWER(sr.code_text) LIKE '%photon%'
    OR LOWER(sr.code_text) LIKE '%beam%'
    OR LOWER(sr.code_text) LIKE '%brachytherapy%'
    OR LOWER(sr.code_text) LIKE '%imrt%'
    OR LOWER(sr.code_text) LIKE '%xrt%'
    OR LOWER(sr.code_text) LIKE '%oncolog%'
  )
ORDER BY sr.occurrence_date_time DESC
LIMIT 100
"""

print('\nExecuting query...')
try:
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': s3_output}
    )
    
    query_id = response['QueryExecutionId']
    for _ in range(60):
        status_result = athena.get_query_execution(QueryExecutionId=query_id)
        state = status_result['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)
    
    if state == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
        
        if len(results['ResultSet']['Rows']) > 1:
            # Convert to DataFrame
            columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            data = []
            for row in results['ResultSet']['Rows'][1:]:  # Skip header
                data.append([col.get('VarCharValue', '') for col in row['Data']])
            
            df = pd.DataFrame(data, columns=columns)
            print(f'\n✅ Found {len(df)} radiation-related service requests!')
            
            print('\nBreakdown by patient:')
            for patient_id in patient_ids:
                patient_data = df[df['patient_id'] == patient_id]
                patient_name = 'C1277724' if 'Ilo3w3' in patient_id else 'eXdoUrDdY4gkdnZEs6uTeq'
                print(f'  {patient_name}: {len(patient_data)} service requests')
            
            print(f'\nSample service requests:')
            display_cols = [c for c in ['patient_id', 'occurrence_date_time', 'code_text', 'status', 'intent'] if c in df.columns]
            print(df[display_cols].head(10).to_string(index=False))
            
            print(f'\n\nUnique service request types:')
            print(df['code_text'].value_counts().head(20).to_string())
            
            # Save results
            output_file = 'reports/radiation_service_requests_search.csv'
            df.to_csv(output_file, index=False)
            print(f'\n✅ Saved results to: {output_file}')
            
        else:
            print('\n❌ No radiation-related service requests found')
            
    elif state == 'FAILED':
        error = status_result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f'\n❌ Query failed: {error}')
        
except Exception as e:
    print(f'\n❌ Exception: {str(e)}')
    import traceback
    traceback.print_exc()

print('\n' + '='*80)
