#!/usr/bin/env python3
"""
Comprehensive assessment of all service_request tables in fhir_prd_db.
Similar to care_plan table assessment.
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

# All service_request tables discovered
SERVICE_REQUEST_TABLES = [
    'service_request',                      # Parent table
    'service_request_based_on',
    'service_request_body_site',
    'service_request_category',
    'service_request_code_coding',
    'service_request_contained',
    'service_request_identifier',
    'service_request_instantiates_uri',
    'service_request_insurance',
    'service_request_location_code',
    'service_request_location_reference',
    'service_request_note',                 # HIGH PRIORITY - may have RT notes
    'service_request_order_detail',
    'service_request_performer',
    'service_request_performer_type_coding',
    'service_request_reason_code',          # HIGH PRIORITY - may have RT reason codes
    'service_request_reason_reference',     # HIGH PRIORITY - may reference RT conditions
    'service_request_relevant_history',
    'service_request_replaces',
    'service_request_specimen',
    'service_request_supporting_info',      # HIGH PRIORITY - may have RT protocols
]

athena = boto3.client('athena', region_name='us-east-1')
DATABASE = 'fhir_prd_db'
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
            return None, reason
        
        result = athena.get_query_results(QueryExecutionId=query_id)
        return result, None
    except Exception as e:
        return None, str(e)

def get_table_schema(table_name):
    """Get column names for a table to determine if it's parent or child."""
    query = f"DESCRIBE {DATABASE}.{table_name}"
    result, error = execute_query(query)
    
    if not result:
        return []
    
    columns = []
    for row in result['ResultSet']['Rows'][1:10]:  # First few columns
        if len(row['Data']) > 0:
            col_info = row['Data'][0]['VarCharValue']
            col_name = col_info.split('\t')[0] if '\t' in col_info else col_info
            columns.append(col_name)
    
    return columns

def check_parent_table(table_name, patient_ids):
    """Check parent table (has subject_reference)."""
    patient_list = "', '".join(patient_ids)
    
    # NOTE: service_request uses subject_reference (no 'Patient/' prefix)
    query = f"SELECT COUNT(*) as total FROM {DATABASE}.{table_name} WHERE subject_reference IN ('{patient_list}')"
    
    result, error = execute_query(query)
    if result and len(result['ResultSet']['Rows']) > 1:
        count = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
        return count, True, None
    
    return 0, False, "Query failed or no subject_reference column"

def check_child_table(table_name, patient_ids):
    """Check child table (needs JOIN to parent service_request)."""
    patient_list = "', '".join(patient_ids)
    
    # NOTE: service_request uses subject_reference (no 'Patient/' prefix)
    query = f"""
    SELECT COUNT(*) as total
    FROM {DATABASE}.{table_name} child
    JOIN {DATABASE}.service_request parent ON child.service_request_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result, error = execute_query(query)
    if result and len(result['ResultSet']['Rows']) > 1:
        count = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
        return count, True, None
    
    return 0, False, "JOIN failed"

def check_table_for_patients(table_name, patient_ids):
    """Check if table has records for test patients. Returns total count only."""
    
    print(f"\nChecking: {table_name}")
    
    # Get schema to determine if parent or child
    columns = get_table_schema(table_name)
    
    if not columns:
        print(f"  ⚠️  Could not get schema")
        return 0, False, "Schema query failed"
    
    is_parent = any(col in columns for col in ['subject_patient_id', 'subject_reference'])
    
    if is_parent or table_name == 'service_request':
        # Parent table - query directly
        count, success, error = check_parent_table(table_name, patient_ids)
    else:
        # Child table - needs JOIN
        count, success, error = check_child_table(table_name, patient_ids)
    
    if not success:
        print(f"  ❌ Query failed: {error}")
        return 0, False
    
    if count > 0:
        print(f"  ✅ {count} records found across {len(patient_ids)} test patients")
        return count, True
    else:
        print(f"  ❌ 0 records")
        return 0, True

def main():
    print(f"""
{'='*80}
SERVICE REQUEST COMPREHENSIVE TABLE ASSESSMENT
Database: {DATABASE}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

Testing {len(TEST_PATIENTS)} patients (anonymized)
Checking ALL {len(SERVICE_REQUEST_TABLES)} service_request tables
NO PATIENT IDs WILL BE DISPLAYED - only aggregated counts
{'='*80}
""")
    
    results = {}
    for table in SERVICE_REQUEST_TABLES:
        priority = ""
        if table in ['service_request_note', 'service_request_reason_code', 
                     'service_request_reason_reference', 'service_request_supporting_info']:
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
        if table in ['service_request_note', 'service_request_reason_code', 
                     'service_request_reason_reference', 'service_request_supporting_info']:
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
    print(f"  - Tables with data: {len(found_tables)}/{len(SERVICE_REQUEST_TABLES)}")
    print(f"  - Empty tables: {len(empty_tables)}/{len(SERVICE_REQUEST_TABLES)}")
    print(f"  - Failed queries: {len(failed_tables)}/{len(SERVICE_REQUEST_TABLES)}")
    print(f"{'='*80}")
    
    if found_tables:
        print("\n🎯 TABLES WITH DATA (need detailed analysis):")
        for table, count in found_tables:
            print(f"   - {table}: {count} records")
            if table in ['service_request_note', 'service_request_reason_code', 
                         'service_request_reason_reference', 'service_request_supporting_info']:
                print(f"     → HIGH PRIORITY for radiation treatment data")
    
    if empty_tables:
        print(f"\n❌ CONFIRMED EMPTY TABLES ({len(empty_tables)} tables):")
        for table in empty_tables[:10]:  # Show first 10
            print(f"   - {table}")
        if len(empty_tables) > 10:
            print(f"   ... and {len(empty_tables) - 10} more")
    
    if failed_tables:
        print("\n⚠️  FAILED QUERIES (may need manual investigation):")
        for table in failed_tables:
            print(f"   - {table}")
    
    print(f"\n{'='*80}")
    print("COMPARISON WITH PREVIOUS RADIATION INVESTIGATION:")
    print(f"{'='*80}")
    print("Previous check: service_request + service_request_code_coding")
    print(f"Current check: ALL {len(SERVICE_REQUEST_TABLES)} service_request tables")
    print(f"Previously missed: {len(SERVICE_REQUEST_TABLES) - 2} tables")
    
    if found_tables:
        print(f"\n📊 NEW DATA SOURCES DISCOVERED:")
        new_sources = [t for t, c in found_tables if t not in ['service_request', 'service_request_code_coding']]
        if new_sources:
            for table in new_sources:
                info = results[table]
                print(f"   ✅ {table}: {info['count']} records")
        else:
            print("   (No new data sources beyond originally checked tables)")

if __name__ == "__main__":
    main()
