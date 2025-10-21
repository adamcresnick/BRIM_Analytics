#!/usr/bin/env python3
"""
Find a suitable test patient in Athena with enough data for testing
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
    print("Finding suitable test patients in fhir_prd_db...")
    print("="*80)

    # Find patients with multiple data types
    query = """
    WITH patient_data_counts AS (
        SELECT
            patient_fhir_id,
            COUNT(DISTINCT CASE WHEN dr_type_text = 'Progress Note' THEN document_reference_id END) as progress_notes,
            COUNT(DISTINCT CASE WHEN dr_category_text = 'Radiology' THEN document_reference_id END) as imaging_reports,
            COUNT(DISTINCT CASE WHEN dr_type_text = 'Operative Note' THEN document_reference_id END) as operative_notes
        FROM fhir_prd_db.v_binary_files
        GROUP BY patient_fhir_id
    )
    SELECT
        patient_fhir_id,
        progress_notes,
        imaging_reports,
        operative_notes,
        (progress_notes + imaging_reports + operative_notes) as total_docs
    FROM patient_data_counts
    WHERE progress_notes > 2
      AND imaging_reports > 0
    ORDER BY total_docs DESC
    LIMIT 5
    """

    print("\nFinding patients with diverse document types...")
    results = query_athena(query)

    if not results:
        print("No suitable patients found")
        return

    print(f"\nFound {len(results)} suitable test patients:")
    print()
    for i, row in enumerate(results, 1):
        print(f"{i}. {row['patient_fhir_id']}")
        print(f"   Progress notes: {row['progress_notes']}")
        print(f"   Imaging reports: {row['imaging_reports']}")
        print(f"   Operative notes: {row['operative_notes']}")
        print(f"   Total documents: {row['total_docs']}")
        print()

    print("="*80)
    print("RECOMMENDATION:")
    print(f"Use: {results[0]['patient_fhir_id']}")
    print("This patient has the most diverse document collection for testing.")

if __name__ == '__main__':
    main()
