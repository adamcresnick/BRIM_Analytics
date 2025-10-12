#!/usr/bin/env python3
"""
Check the 9 care_plan tables we missed in our initial radiation exploration.
Now using fhir_prd_db (upgraded database with identical structure).
NO PATIENT ID LEAKAGE - only aggregated counts.
"""

import boto3
import time
from datetime import datetime

# Test patients (2 with radiation, 2 without)
TEST_PATIENTS = [
    'eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3',  # Has RT
    'emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3',  # Has RT
    'eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',  # No RT
    'enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3'   # No RT
]

# Tables we MISSED in original exploration
MISSING_TABLES = [
    'care_plan_care_team',
    'care_plan_contributor',
    'care_plan_identifier',
    'care_plan_instantiates_canonical',
    'care_plan_instantiates_uri',
    'care_plan_note',                    # HIGH PRIORITY - could have RT notes
    'care_plan_part_of',                 # HIGH PRIORITY - could link to RT plans
    'care_plan_replaces',
    'care_plan_supporting_info'          # HIGH PRIORITY - could reference RT protocols
]

athena = boto3.client('athena', region_name='us-east-1')
DATABASE = 'fhir_prd_db'  # UPGRADED DATABASE
OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'

def execute_query(query_string):
    """Execute Athena query and wait for results."""
    try:
        response = athena.start_query_execution(
            QueryString=query_string,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
        )
        query_id = response['QueryExecutionId']
        
        # Wait for completion
        max_wait = 30
        elapsed = 0
        while elapsed < max_wait:
            status = athena.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(1)
            elapsed += 1
        
        if state != 'SUCCEEDED':
            reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"    Query failed: {reason}")
            return None
        
        result = athena.get_query_results(QueryExecutionId=query_id)
        return result
    except Exception as e:
        print(f"    Error: {str(e)}")
        return None

def check_table_for_patients(table_name, patient_ids):
    """Check if table has records for any test patients. Returns total count only."""
    patient_list = "', '".join(patient_ids)
    
    # Child tables need JOIN to parent care_plan table
    # care_plan uses subject_reference (not subject_patient_id) for patient ID
    # Query returns ONLY total count, NO patient IDs
    query = f"""
    SELECT COUNT(*) as total_records
    FROM {DATABASE}.{table_name} child
    JOIN {DATABASE}.care_plan parent ON child.care_plan_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    print(f"\nChecking: {table_name}")
    
    result = execute_query(query)
    if not result:
        print(f"  ❌ Query failed or table doesn't exist")
        return 0, False
    
    rows = result['ResultSet']['Rows']
    if len(rows) <= 1:  # Only header
        print(f"  ❌ 0 records")
        return 0, True
    
    # Get total count (NO patient IDs returned)
    total = int(rows[1]['Data'][0]['VarCharValue'])
    
    if total > 0:
        print(f"  ✅ {total} records found across {len(patient_ids)} test patients")
        return total, True
    else:
        print(f"  ❌ 0 records")
        return 0, True

def main():
    print(f"""
{'='*80}
CARE PLAN MISSING TABLES CHECK
Database: {DATABASE} (UPGRADED from fhir_v2_prd_db)
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

Testing {len(TEST_PATIENTS)} patients (anonymized)
Checking 9 care_plan tables we missed in original radiation exploration
NO PATIENT IDs WILL BE DISPLAYED - only aggregated counts
{'='*80}
""")
    
    results = {}
    for table in MISSING_TABLES:
        priority = ""
        if table in ['care_plan_note', 'care_plan_part_of', 'care_plan_supporting_info']:
            priority = " ⚠️ HIGH PRIORITY"
        
        print(f"{priority}")
        count, success = check_table_for_patients(table, TEST_PATIENTS)
        results[table] = {'count': count, 'success': success}
        time.sleep(1)  # Rate limiting
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    found_tables = []
    empty_tables = []
    failed_tables = []
    
    for table, info in results.items():
        priority = ""
        if table in ['care_plan_note', 'care_plan_part_of', 'care_plan_supporting_info']:
            priority = " ⚠️ HIGH PRIORITY"
        
        if not info['success']:
            print(f"  ⚠️  {table}: QUERY FAILED{priority}")
            failed_tables.append(table)
        elif info['count'] > 0:
            print(f"  ✅ {table}: {info['count']} records{priority}")
            found_tables.append((table, info['count']))
        else:
            print(f"  ❌ {table}: 0 records{priority}")
            empty_tables.append(table)
    
    print(f"\n{'='*80}")
    print(f"Results:")
    print(f"  - Tables with data: {len(found_tables)}/{len(MISSING_TABLES)}")
    print(f"  - Empty tables: {len(empty_tables)}/{len(MISSING_TABLES)}")
    print(f"  - Failed queries: {len(failed_tables)}/{len(MISSING_TABLES)}")
    print(f"{'='*80}")
    
    if found_tables:
        print("\n🎯 TABLES WITH DATA (need detailed analysis):")
        for table, count in found_tables:
            print(f"   - {table}: {count} records")
            print(f"     → Should extract and analyze for radiation treatment data")
    
    if empty_tables:
        print("\n❌ CONFIRMED EMPTY TABLES (no further action needed):")
        for table in empty_tables:
            print(f"   - {table}")
    
    if failed_tables:
        print("\n⚠️  FAILED QUERIES (may need manual investigation):")
        for table in failed_tables:
            print(f"   - {table}")

if __name__ == "__main__":
    main()
