#!/usr/bin/env python3
"""
Quick verification script to check what data exists in Athena for a patient
"""
import boto3
import time
import sys

def query_athena(query):
    """Run query against Athena and return results"""
    session = boto3.Session(profile_name='radiant-prod')
    client = session.client('athena')

    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )
    query_id = response['QueryExecutionId']

    # Wait for completion
    while True:
        status = client.get_query_execution(QueryExecutionId=query_id)
        state = status['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)

    if state != 'SUCCEEDED':
        print(f"Query failed: {state}")
        return []

    # Get results with pagination
    rows = []
    next_token = None
    header = None

    while True:
        if next_token:
            results = client.get_query_results(QueryExecutionId=query_id, NextToken=next_token)
        else:
            results = client.get_query_results(QueryExecutionId=query_id)

        if header is None:
            if len(results['ResultSet']['Rows']) <= 1:
                return []
            header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            result_rows = results['ResultSet']['Rows'][1:]
        else:
            result_rows = results['ResultSet']['Rows']

        for row in result_rows:
            row_dict = {}
            for i, col in enumerate(row['Data']):
                row_dict[header[i]] = col.get('VarCharValue', '')
            rows.append(row_dict)

        next_token = results.get('NextToken')
        if not next_token:
            break

    return rows

def main():
    patient_id = sys.argv[1] if len(sys.argv) > 1 else 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'

    print(f"Checking data in Athena fhir_prd_db for: {patient_id}")
    print("="*80)

    # Check v_imaging
    print("\n1. v_imaging (imaging text reports):")
    query = f"SELECT COUNT(*) as count FROM fhir_prd_db.v_imaging WHERE patient_fhir_id = '{patient_id}'"
    results = query_athena(query)
    count = results[0]['count'] if results else 0
    print(f"   Count: {count}")

    # Check v_binary_files for imaging PDFs
    print("\n2. v_binary_files (imaging PDFs):")
    query = f"""
        SELECT COUNT(*) as count
        FROM fhir_prd_db.v_binary_files
        WHERE patient_fhir_id = '{patient_id}'
          AND dr_category_text = 'Radiology'
          AND content_type = 'application/pdf'
    """
    results = query_athena(query)
    count = results[0]['count'] if results else 0
    print(f"   Count: {count}")

    # Check v_procedures_tumor
    print("\n3. v_procedures_tumor (operative reports):")
    query = f"SELECT COUNT(*) as count FROM fhir_prd_db.v_procedures_tumor WHERE patient_fhir_id = '{patient_id}'"
    results = query_athena(query)
    count = results[0]['count'] if results else 0
    print(f"   Count: {count}")

    # Check v_binary_files for progress notes
    print("\n4. v_binary_files (all progress notes):")
    query = f"""
        SELECT COUNT(*) as count
        FROM fhir_prd_db.v_binary_files
        WHERE patient_fhir_id = '{patient_id}'
          AND dr_type_text = 'Progress Note'
    """
    results = query_athena(query)
    count = results[0]['count'] if results else 0
    print(f"   Count: {count}")

    # Check timeline database
    print("\n5. Local timeline database:")
    import duckdb
    conn = duckdb.connect('data/timeline.duckdb', read_only=True)

    # Get patient_id from timeline (without "Patient/" prefix)
    timeline_patient_id = patient_id.replace('Patient/', '')

    meds = conn.execute(f"""
        SELECT COUNT(*) as count
        FROM events
        WHERE patient_id = ? AND event_type = 'Medication'
    """, [timeline_patient_id]).fetchone()[0]
    print(f"   Medication events: {meds}")

    procedures = conn.execute(f"""
        SELECT COUNT(*) as count
        FROM events
        WHERE patient_id = ? AND event_type = 'Procedure'
    """, [timeline_patient_id]).fetchone()[0]
    print(f"   Procedure events: {procedures}")

    conn.close()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("If all Athena counts are 0, this patient doesn't exist in fhir_prd_db.")
    print("The timeline database may contain synthetic or test data.")
    print("Try using a real patient FHIR ID from production.")

if __name__ == '__main__':
    main()
