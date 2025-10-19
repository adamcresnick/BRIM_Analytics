#!/usr/bin/env python3
"""
Test hydrocephalus and shunt queries against Athena
Executes assessment queries and documents findings
"""

import boto3
import time
import yaml
from pathlib import Path

# Load Athena configuration
config_path = Path(__file__).parent / 'config' / 'athena_connection.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Create session with profile
session = boto3.Session(profile_name=config['aws']['profile'])
athena_client = session.client('athena', region_name=config['aws']['region'])

def execute_query(query, query_name):
    """Execute Athena query and return results"""
    print(f"\n{'='*80}")
    print(f"Executing: {query_name}")
    print(f"{'='*80}")

    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': config['athena']['database']},
        ResultConfiguration={'OutputLocation': config['athena']['output_location']}
    )

    query_execution_id = response['QueryExecutionId']
    print(f"Query ID: {query_execution_id}")

    # Wait for query to complete
    while True:
        result = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = result['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(2)

    if status == 'FAILED':
        error = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        print(f"❌ Query failed: {error}")
        return None

    if status == 'CANCELLED':
        print(f"⚠️ Query cancelled")
        return None

    # Get results
    results = athena_client.get_query_results(QueryExecutionId=query_execution_id)

    # Parse results
    rows = results['ResultSet']['Rows']
    if len(rows) == 0:
        print("✅ Query succeeded - No results")
        return []

    # Extract headers
    headers = [col['VarCharValue'] for col in rows[0]['Data']]

    # Extract data rows
    data_rows = []
    for row in rows[1:]:
        data_row = {}
        for i, col in enumerate(row['Data']):
            data_row[headers[i]] = col.get('VarCharValue', '')
        data_rows.append(data_row)

    print(f"✅ Query succeeded - {len(data_rows)} rows returned")
    return data_rows


# ================================================================================
# QUERY 6: COHORT-WIDE ASSESSMENT
# ================================================================================

cohort_query = """
-- Count of patients with hydrocephalus conditions
SELECT
    'Hydrocephalus Conditions' as data_type,
    COUNT(DISTINCT c.subject_reference) as patient_count,
    COUNT(c.id) as record_count
FROM fhir_prd_db.condition c
WHERE c.subject_reference IS NOT NULL
  AND (
      LOWER(c.code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(c.code_coding, 'G91\\\\.')
      OR REGEXP_LIKE(c.code_coding, 'Q03\\\\.')
  )

UNION ALL

-- Count of patients with shunt procedures
SELECT
    'Shunt Procedures' as data_type,
    COUNT(DISTINCT p.subject_reference) as patient_count,
    COUNT(p.id) as record_count
FROM fhir_prd_db.procedure p
WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
  )

UNION ALL

-- Count of patients with shunt devices
SELECT
    'Shunt Devices' as data_type,
    COUNT(DISTINCT d.patient_reference) as patient_count,
    COUNT(d.id) as record_count
FROM fhir_prd_db.device d
WHERE d.patient_reference IS NOT NULL
  AND (
      LOWER(d.type_text) LIKE '%shunt%'
      OR LOWER(d.device_name) LIKE '%ventriculo%'
  )

UNION ALL

-- Count of patients with hydrocephalus imaging findings
SELECT
    'Hydrocephalus Imaging' as data_type,
    COUNT(DISTINCT dr.subject_reference) as patient_count,
    COUNT(dr.id) as record_count
FROM fhir_prd_db.diagnostic_report dr
WHERE dr.subject_reference IS NOT NULL
  AND (
      LOWER(dr.conclusion) LIKE '%hydroceph%'
      OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
  )
"""

print("\n" + "="*80)
print("HYDROCEPHALUS DATA ASSESSMENT - COHORT-WIDE COVERAGE")
print("="*80)

cohort_results = execute_query(cohort_query, "Cohort-Wide Assessment")

if cohort_results:
    print("\n📊 Coverage Summary:")
    print("-" * 80)
    for row in cohort_results:
        print(f"{row['data_type']:30} | {row['patient_count']:>5} patients | {row['record_count']:>6} records")
    print("-" * 80)


# ================================================================================
# QUERY 1: HYDROCEPHALUS CONDITIONS (TEST PATIENTS)
# ================================================================================

conditions_query = """
SELECT
    c.subject_reference as patient_fhir_id,
    c.id as condition_id,
    c.code_text,
    c.code_coding,
    c.clinical_status,
    c.onset_date_time,
    c.recorded_date,

    CASE
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\\\.0') THEN 'Communicating hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\\\.1') THEN 'Obstructive hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\\\.2') THEN 'Normal-pressure hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\\\.3') THEN 'Post-traumatic hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\\\.8') THEN 'Other hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\\\.9') THEN 'Hydrocephalus, unspecified'
        WHEN REGEXP_LIKE(c.code_coding, 'Q03\\\\.') THEN 'Congenital hydrocephalus'
        ELSE 'Hydrocephalus (text match)'
    END as hydrocephalus_type

FROM fhir_prd_db.condition c
WHERE c.subject_reference IS NOT NULL
  AND (
      LOWER(c.code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(c.code_coding, 'G91\\\\.')
      OR REGEXP_LIKE(c.code_coding, 'Q03\\\\.')
  )
  AND c.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY c.subject_reference, c.onset_date_time
"""

condition_results = execute_query(conditions_query, "Hydrocephalus Conditions - Test Patients")

if condition_results:
    print("\n📋 Hydrocephalus Conditions Found:")
    print("-" * 80)
    for row in condition_results:
        patient_id = row['patient_fhir_id'].split('/')[-1][:20]
        print(f"Patient: {patient_id}")
        print(f"  Type: {row['hydrocephalus_type']}")
        print(f"  Code: {row['code_text'][:60]}")
        print(f"  ICD-10: {row['code_coding']}")
        print(f"  Onset: {row['onset_date_time']}")
        print()


# ================================================================================
# QUERY 2: SHUNT PROCEDURES (TEST PATIENTS)
# ================================================================================

procedures_query = """
SELECT
    p.subject_reference as patient_fhir_id,
    p.code_text,
    p.code_coding,
    p.status,
    p.performed_period_start,

    CASE
        WHEN LOWER(p.code_text) LIKE '%ventriculoperitoneal%'
             OR LOWER(p.code_text) LIKE '%vp%shunt%'
             OR LOWER(p.code_text) LIKE '%vps%' THEN 'VPS'
        WHEN LOWER(p.code_text) LIKE '%endoscopic%third%ventriculostomy%'
             OR LOWER(p.code_text) LIKE '%etv%' THEN 'ETV'
        WHEN LOWER(p.code_text) LIKE '%external%ventricular%drain%'
             OR LOWER(p.code_text) LIKE '%evd%' THEN 'EVD'
        ELSE 'Other Shunt'
    END as shunt_type,

    CASE
        WHEN LOWER(p.code_text) LIKE '%placement%'
             OR LOWER(p.code_text) LIKE '%insertion%' THEN 'Initial Placement'
        WHEN LOWER(p.code_text) LIKE '%revision%'
             OR LOWER(p.code_text) LIKE '%replacement%' THEN 'Revision'
        WHEN LOWER(p.code_text) LIKE '%reprogram%' THEN 'Reprogramming'
        ELSE 'Unknown Category'
    END as procedure_category

FROM fhir_prd_db.procedure p
WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
  )
  AND p.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY p.subject_reference, p.performed_period_start
"""

procedure_results = execute_query(procedures_query, "Shunt Procedures - Test Patients")

if procedure_results:
    print("\n🏥 Shunt Procedures Found:")
    print("-" * 80)
    for row in procedure_results:
        patient_id = row['patient_fhir_id'].split('/')[-1][:20]
        print(f"Patient: {patient_id}")
        print(f"  Type: {row['shunt_type']}")
        print(f"  Category: {row['procedure_category']}")
        print(f"  Procedure: {row['code_text'][:60]}")
        print(f"  Date: {row['performed_period_start']}")
        print()


# ================================================================================
# SUMMARY
# ================================================================================

print("\n" + "="*80)
print("ASSESSMENT COMPLETE")
print("="*80)
print("\nNext steps:")
print("1. Review coverage statistics")
print("2. Examine sample records for data quality")
print("3. Design consolidated views based on available data")
print("4. Identify fields requiring NLP extraction")
