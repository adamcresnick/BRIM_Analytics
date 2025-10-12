#!/usr/bin/env python3
"""
Search appointment service types, specialties, and categories for radiation-related appointments
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
print('SEARCHING APPOINTMENT SUBTABLES FOR RADIATION-RELATED SERVICE TYPES')
print('='*80)

patient_list = "','".join(patient_ids)

# Query appointment service types, specialties, and categories
query = f"""
SELECT DISTINCT
    a.id as appointment_id,
    ap.participant_actor_reference as patient_id,
    a.start,
    a.status,
    ast.service_type_coding_display,
    ast.service_type_coding_code,
    ast.service_type_coding_system,
    asc.service_category_coding_display,
    asc.service_category_coding_code,
    asp.specialty_coding_display,
    asp.specialty_coding_code
FROM {database}.appointment a
JOIN {database}.appointment_participant ap ON a.id = ap.appointment_id
LEFT JOIN {database}.appointment_service_type ast ON a.id = ast.appointment_id
LEFT JOIN {database}.appointment_service_category asc ON a.id = asc.appointment_id
LEFT JOIN {database}.appointment_specialty asp ON a.id = asp.appointment_id
WHERE ap.participant_actor_reference IN ('{patient_list}')
  AND (
    LOWER(ast.service_type_coding_display) LIKE '%radiation%'
    OR LOWER(ast.service_type_coding_display) LIKE '%oncolog%'
    OR LOWER(ast.service_type_coding_display) LIKE '%radiotherapy%'
    OR LOWER(asc.service_category_coding_display) LIKE '%radiation%'
    OR LOWER(asc.service_category_coding_display) LIKE '%oncolog%'
    OR LOWER(asp.specialty_coding_display) LIKE '%radiation%'
    OR LOWER(asp.specialty_coding_display) LIKE '%oncolog%'
  )
ORDER BY a.start DESC
LIMIT 200
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
            print(f'\n✅ Found {len(df)} radiation-related appointments!')
            
            print('\nBreakdown by patient:')
            for patient_id in patient_ids:
                patient_data = df[df['patient_id'] == patient_id]
                patient_name = 'C1277724' if 'Ilo3w3' in patient_id else 'eXdoUrDdY4gkdnZEs6uTeq'
                print(f'  {patient_name}: {len(patient_data)} appointments')
            
            print(f'\nService Type Display values:')
            if 'service_type_coding_display' in df.columns:
                print(df['service_type_coding_display'].value_counts().to_string())
            
            print(f'\n\nService Category Display values:')
            if 'service_category_coding_display' in df.columns:
                print(df['service_category_coding_display'].value_counts().to_string())
            
            print(f'\n\nSpecialty Display values:')
            if 'specialty_coding_display' in df.columns:
                print(df['specialty_coding_display'].value_counts().to_string())
            
            print(f'\n\nSample appointments:')
            display_cols = ['patient_id', 'start', 'service_type_coding_display', 'specialty_coding_display', 'status']
            display_cols = [c for c in display_cols if c in df.columns]
            print(df[display_cols].head(20).to_string(index=False, max_colwidth=50))
            
            # Save results
            output_file = 'reports/radiation_appointment_service_types_search.csv'
            df.to_csv(output_file, index=False)
            print(f'\n✅ Saved results to: {output_file}')
            
        else:
            print('\n❌ No radiation-related appointments found in service type/specialty fields')
            
    elif state == 'FAILED':
        error = status_result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f'\n❌ Query failed: {error}')
        
except Exception as e:
    print(f'\n❌ Exception: {str(e)}')
    import traceback
    traceback.print_exc()

print('\n' + '='*80)
