#!/usr/bin/env python3
"""
Verify medication-proximate progress notes with oncology filtering applied
"""
import boto3
import time

PATIENT_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
DATABASE = 'fhir_prd_db'
S3_OUTPUT = 's3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/athena-queries/'

# Medication dates from timeline
MEDICATION_DATES = [
    '2021-05-20', '2021-08-25', '2021-11-11', '2021-11-21',
    '2022-01-09', '2022-02-28', '2022-05-12', '2022-09-07', '2022-11-03',
    '2023-04-14', '2023-06-20', '2023-08-10', '2023-12-06',
    '2024-01-02', '2024-02-02', '2024-06-04', '2024-07-09'
]

# Build query with oncology filtering criteria
query = f"""
WITH medication_dates AS (
    SELECT DATE('{MEDICATION_DATES[0]}') as med_date
"""
for date in MEDICATION_DATES[1:]:
    query += f"    UNION ALL SELECT DATE('{date}')\n"

query += f"""),
all_progress_notes AS (
    SELECT
        DATE(dr_date) as note_date,
        dr_type_text,
        dr_category_text,
        dr_description,
        document_reference_id
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
),
oncology_filtered AS (
    SELECT
        note_date,
        dr_type_text,
        dr_description
    FROM all_progress_notes
    WHERE
        -- Exclude non-oncology notes (telephone, nursing, etc.)
        LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%telephone%'
        AND LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%phone%'
        AND LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%nurse%'
        AND LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%social work%'
        AND LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%nutrition%'
        AND LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%pharmacy%'
        AND LOWER(COALESCE(dr_type_text, '') || ' ' || COALESCE(dr_description, ''))
        NOT LIKE '%lab results only%'
        AND (
            -- Include if oncology-specific
            LOWER(dr_type_text) LIKE '%oncology%'
            OR LOWER(dr_type_text) LIKE '%hematology%'
            OR LOWER(dr_type_text) LIKE '%progress note%'
            OR LOWER(COALESCE(dr_description, '')) LIKE '%oncology%'
            OR LOWER(COALESCE(dr_description, '')) LIKE '%chemotherapy%'
            OR LOWER(COALESCE(dr_description, '')) LIKE '%tumor%'
            OR LOWER(COALESCE(dr_description, '')) LIKE '%cancer%'
        )
)
SELECT
    m.med_date,
    o.note_date,
    DATE_DIFF('day', m.med_date, o.note_date) as days_difference,
    o.dr_type_text,
    o.dr_description
FROM medication_dates m
LEFT JOIN oncology_filtered o
    ON ABS(DATE_DIFF('day', m.med_date, o.note_date)) <= 7
ORDER BY m.med_date, o.note_date
"""

print("Querying Athena with oncology filtering...")
print("="*80)

client = boto3.client('athena', region_name='us-east-1')

response = client.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': DATABASE},
    ResultConfiguration={'OutputLocation': S3_OUTPUT}
)

query_execution_id = response['QueryExecutionId']
print(f"Query execution ID: {query_execution_id}")
print("Waiting for results...")

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

results = client.get_query_results(QueryExecutionId=query_execution_id)
rows = results['ResultSet']['Rows']

print(f"\n✅ Query completed")
print("="*80)
print(f"{'Med Date':<15} | {'Note Date':<15} | {'Days':<5} | Type / Description")
print("-"*80)

matches = 0
for row in rows[1:]:  # Skip header
    values = [col.get('VarCharValue', 'NULL') for col in row['Data']]
    if values[1] != 'NULL':
        matches += 1
        type_desc = f"{values[3][:30]}"
        print(f"{values[0]:<15} | {values[1]:<15} | {values[2]:<5} | {type_desc}")

print("="*80)

if matches > 0:
    print(f"\n✅ FOUND {matches} ONCOLOGY progress notes within ±7 days of medication dates!")
    print("This means the prioritizer SHOULD find post-medication-change notes.")
else:
    print("\n❌ NO ONCOLOGY progress notes found within ±7 days")
    print("This confirms: post-medication-change = 0 is CORRECT")
