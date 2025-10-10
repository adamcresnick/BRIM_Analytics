#!/usr/bin/env python3
"""
Test joining medication_form_coding and medication_ingredient
to patient medications via medication_id
"""

import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

def run_query(query, description):
    print(f"\n{description}")
    print("="*80)
    print(f"Query:\n{query}\n")
    
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
        time.sleep(0.5)
    
    if state == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_id, MaxResults=10)
        rows = results['ResultSet']['Rows']
        
        if len(rows) > 1:
            # Get column names
            columns = [col.get('VarCharValue', '') for col in rows[0]['Data']]
            print(f"✓ Found {len(rows)-1} rows")
            print(f"\nColumns: {', '.join(columns)}")
            
            # Show first 3 data rows
            for i, row in enumerate(rows[1:4], 1):
                print(f"\nRow {i}:")
                data = [col.get('VarCharValue', 'NULL') for col in row['Data']]
                for col, val in zip(columns, data):
                    # Truncate long values
                    display_val = val[:80] + '...' if val and len(val) > 80 else val
                    print(f"  {col:40s}: {display_val}")
            return len(rows) - 1
        else:
            print("  ✗ No data returned")
            return 0
    else:
        error = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"  ✗ Query failed: {error}")
        return 0

patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

print("\n" + "#"*80)
print("# TEST 1: Get medication_id from patient_medications")
print("#"*80)

test1 = f"""
SELECT 
    pm.medication_display,
    pm.medication_reference
FROM fhir_v2_prd_db.patient_medications pm
WHERE pm.patient_id = '{patient_id}'
LIMIT 5
"""

count1 = run_query(test1, "Sample medications with medication_reference:")

print("\n" + "#"*80)
print("# TEST 2: Join to medication_form_coding via medication_reference")
print("#"*80)

test2 = f"""
SELECT 
    pm.medication_display,
    mfc.form_coding_code,
    mfc.form_coding_display
FROM fhir_v2_prd_db.patient_medications pm
LEFT JOIN fhir_v2_prd_db.medication_form_coding mfc
    ON pm.medication_reference = mfc.medication_id
WHERE pm.patient_id = '{patient_id}'
    AND mfc.form_coding_display IS NOT NULL
LIMIT 10
"""

count2 = run_query(test2, "Medications with form coding (tablet/solution/injection):")

print("\n" + "#"*80)
print("# TEST 3: Join to medication_ingredient via medication_reference")
print("#"*80)

test3 = f"""
SELECT 
    pm.medication_display,
    mi.ingredient_strength_numerator_value,
    mi.ingredient_strength_numerator_unit,
    mi.ingredient_strength_denominator_value,
    mi.ingredient_strength_denominator_unit
FROM fhir_v2_prd_db.patient_medications pm
LEFT JOIN fhir_v2_prd_db.medication_ingredient mi
    ON pm.medication_reference = mi.medication_id
WHERE pm.patient_id = '{patient_id}'
    AND mi.ingredient_strength_numerator_value IS NOT NULL
LIMIT 10
"""

count3 = run_query(test3, "Medications with ingredient strength:")

print("\n" + "#"*80)
print("# SUMMARY")
print("#"*80)
print(f"\n✓ medication_form_coding: {count2} medications with form data")
print(f"✓ medication_ingredient: {count3} medications with strength data")
print(f"\nConclusion: These tables CAN be joined via medication_reference = medication_id")
print(f"Should include in extraction script for complete medication details")
