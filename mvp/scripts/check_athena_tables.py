#!/usr/bin/env python3
"""
Check if Athena tables have any data at all
"""
import boto3
import time

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
    print("Checking Athena tables in fhir_prd_db...")
    print("="*80)

    tables = [
        ('v_binary_files', 'SELECT COUNT(*) as count, COUNT(DISTINCT patient_fhir_id) as patients FROM fhir_prd_db.v_binary_files'),
        ('v_imaging', 'SELECT COUNT(*) as count, COUNT(DISTINCT patient_fhir_id) as patients FROM fhir_prd_db.v_imaging'),
        ('v_procedures_tumor', 'SELECT COUNT(*) as count, COUNT(DISTINCT patient_fhir_id) as patients FROM fhir_prd_db.v_procedures_tumor'),
        ('v_medications', 'SELECT COUNT(*) as count, COUNT(DISTINCT patient_fhir_id) as patients FROM fhir_prd_db.v_medications'),
    ]

    for table_name, query in tables:
        print(f"\n{table_name}:")
        results = query_athena(query)
        if results:
            print(f"  Total records: {results[0]['count']}")
            print(f"  Unique patients: {results[0]['patients']}")
        else:
            print("  No results or query failed")

    # Get sample patients from v_binary_files
    print("\n" + "="*80)
    print("Sample patients from v_binary_files:")
    query = """
    SELECT patient_fhir_id, COUNT(*) as doc_count
    FROM fhir_prd_db.v_binary_files
    GROUP BY patient_fhir_id
    ORDER BY doc_count DESC
    LIMIT 5
    """
    results = query_athena(query)
    if results:
        for row in results:
            print(f"  {row['patient_fhir_id']}: {row['doc_count']} documents")
    else:
        print("  No patients found")

if __name__ == '__main__':
    main()
