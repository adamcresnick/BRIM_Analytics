#!/usr/bin/env python3
"""
Verify that there are no progress notes within ±7 days of medication start dates
"""
import boto3
import time
from datetime import datetime, timedelta

# Medication dates from timeline database
MEDICATION_DATES = [
    '2021-05-20', '2021-08-25', '2021-11-11', '2021-11-21',
    '2022-01-09', '2022-02-28', '2022-05-12', '2022-09-07', '2022-11-03',
    '2023-04-14', '2023-06-20', '2023-08-10', '2023-12-06',
    '2024-01-02', '2024-02-02', '2024-06-04', '2024-07-09'
]

PATIENT_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
DATABASE = 'fhir_prd_db'
S3_OUTPUT = 's3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/athena-queries/'

# Build query to check for progress notes within ±7 days of each medication date
query = f"""
WITH medication_dates AS (
    SELECT DATE('{MEDICATION_DATES[0]}') as med_date
"""
for date in MEDICATION_DATES[1:]:
    query += f"    UNION ALL SELECT DATE('{date}')\n"

query += f"""
),
progress_notes AS (
    SELECT
        DATE(dr_date) as note_date
    FROM v_binary_files
    WHERE patient_fhir_id = '{PATIENT_ID}'
        AND (
            content_type = 'text/plain'
            OR content_type = 'text/html'
            OR content_type = 'application/pdf'
        )
        AND (
            LOWER(dr_category_text) LIKE '%progress note%'
            OR LOWER(dr_category_text) LIKE '%clinical note%'
            OR LOWER(dr_type_text) LIKE '%oncology%'
            OR LOWER(dr_type_text) LIKE '%hematology%'
        )
)
SELECT
    m.med_date,
    p.note_date,
    DATE_DIFF('day', m.med_date, p.note_date) as days_difference
FROM medication_dates m
LEFT JOIN progress_notes p
    ON ABS(DATE_DIFF('day', m.med_date, p.note_date)) <= 7
ORDER BY m.med_date, p.note_date
"""

print("Query to execute:")
print("="*80)
print(query)
print("="*80)

# Execute query
client = boto3.client('athena', region_name='us-east-1')

response = client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': DATABASE},
    ResultConfiguration={'OutputLocation': S3_OUTPUT}
)

query_execution_id = response['QueryExecutionId']
print(f"\nQuery execution ID: {query_execution_id}")
print("Waiting for query to complete...")

# Wait for query to complete
while True:
    response = client.get_query_execution(QueryExecutionId=query_execution_id)
    status = response['QueryExecution']['Status']['State']

    if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break
    time.sleep(1)

if status != 'SUCCEEDED':
    print(f"\n❌ Query {status}")
    if 'StateChangeReason' in response['QueryExecution']['Status']:
        print(f"Reason: {response['QueryExecution']['Status']['StateChangeReason']}")
    exit(1)

print(f"✅ Query completed successfully")

# Get results
results = client.get_query_results(QueryExecutionId=query_execution_id)

print(f"\nResults:")
print("="*80)

rows = results['ResultSet']['Rows']
headers = [col['VarCharValue'] for col in rows[0]['Data']]
print(f"{headers[0]:<15} | {headers[1]:<15} | {headers[2]}")
print("-"*80)

matches_found = False
for row in rows[1:]:  # Skip header
    values = [col.get('VarCharValue', 'NULL') for col in row['Data']]
    print(f"{values[0]:<15} | {values[1]:<15} | {values[2]}")
    if values[1] != 'NULL':
        matches_found = True

print("="*80)

if matches_found:
    print("\n✅ FOUND progress notes within ±7 days of medication dates")
else:
    print("\n❌ NO progress notes found within ±7 days of ANY medication date")
    print("This confirms the prioritizer result: post-medication-change = 0")
