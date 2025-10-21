#!/usr/bin/env python3
"""
Check what document types a patient has in v_binary_files
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

    # Get results
    results = client.get_query_results(QueryExecutionId=query_id)

    if len(results['ResultSet']['Rows']) <= 1:
        return []

    header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
    rows = []
    for row in results['ResultSet']['Rows'][1:]:
        row_dict = {}
        for i, col in enumerate(row['Data']):
            row_dict[header[i]] = col.get('VarCharValue', '')
        rows.append(row_dict)

    return rows

def main():
    patient_id = sys.argv[1] if len(sys.argv) > 1 else 'Patient/emyObQrM-z8pczz8n9AslxxfGbN6yQhNRgZqMbMXAjjs3'

    print(f"Checking document types for: {patient_id}")
    print("="*80)

    # Try both with and without "Patient/" prefix
    patient_id_short = patient_id.replace('Patient/', '')

    # Get document type breakdown
    query = f"""
    SELECT
        dr_type_text,
        dr_category_text,
        content_type,
        COUNT(*) as count
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id IN ('{patient_id}', '{patient_id_short}')
    GROUP BY dr_type_text, dr_category_text, content_type
    ORDER BY count DESC
    LIMIT 20
    """

    print("\nDocument type breakdown:")
    results = query_athena(query)

    if not results:
        print("No documents found")
        return

    for row in results:
        dr_type = row.get('dr_type_text', 'NULL')
        dr_category = row.get('dr_category_text', 'NULL')
        content_type = row.get('content_type', 'NULL')
        count = row['count']
        print(f"  {count:>6} docs | Type: {dr_type[:30]:<30} | Category: {dr_category[:20]:<20} | Content: {content_type}")

if __name__ == '__main__':
    main()
