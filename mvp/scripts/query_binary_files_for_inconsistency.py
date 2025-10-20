#!/usr/bin/env python3
"""
Query v_binary_files via Athena to find imaging PDFs for temporal inconsistency resolution

This script demonstrates Agent 1 gathering additional sources from v_binary_files
to provide multi-source context for Agent 2 re-review.
"""

import boto3
import time
import json
from datetime import datetime, timedelta
from pathlib import Path


def execute_athena_query(query: str, database: str = 'fhir_prd_db') -> list:
    """Execute Athena query and return results"""
    import os
    os.environ['AWS_PROFILE'] = 'radiant-prod'

    session = boto3.Session(profile_name='radiant-prod')
    client = session.client('athena', region_name='us-east-1')

    # Start query execution
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )

    query_execution_id = response['QueryExecutionId']
    print(f"Query execution ID: {query_execution_id}")

    # Wait for query to complete
    while True:
        query_status = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = query_status['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            raise Exception(f"Query {status}: {reason}")

        time.sleep(2)

    # Get results
    results = []
    paginator = client.get_paginator('get_query_results')

    for page in paginator.paginate(QueryExecutionId=query_execution_id):
        # Skip header row
        rows = page['ResultSet']['Rows'][1:] if results == [] else page['ResultSet']['Rows']

        for row in rows:
            results.append([col.get('VarCharValue', '') for col in row['Data']])

    return results


def query_binary_files_for_temporal_inconsistency(
    patient_id: str,
    event1_date: str,  # '2018-05-27'
    event2_date: str,  # '2018-05-29'
    days_window: int = 7
):
    """
    Query v_binary_files for imaging PDFs near the temporal inconsistency dates
    """
    print("="*80)
    print("QUERYING v_binary_files FOR TEMPORAL INCONSISTENCY")
    print("="*80)
    print(f"\nPatient: {patient_id}")
    print(f"Event 1 date: {event1_date}")
    print(f"Event 2 date: {event2_date}")
    print(f"Search window: ±{days_window} days\n")

    # Calculate date range
    event1_dt = datetime.strptime(event1_date, '%Y-%m-%d')
    event2_dt = datetime.strptime(event2_date, '%Y-%m-%d')

    start_date = (event1_dt - timedelta(days=days_window)).strftime('%Y-%m-%d')
    end_date = (event2_dt + timedelta(days=days_window)).strftime('%Y-%m-%d')

    print(f"Date range: {start_date} to {end_date}\n")

    # Build query (using actual v_binary_files column names)
    query = f"""
    SELECT
        document_reference_id,
        binary_id,
        content_type,
        content_size_bytes,
        content_title,
        dr_date,
        dr_type_text,
        dr_category_text,
        dr_description,
        dr_status,
        dr_doc_status,
        dr_context_period_start,
        dr_context_period_end,
        dr_facility_type,
        age_at_document_days
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
        AND content_type = 'application/pdf'
        AND dr_date >= TIMESTAMP '{start_date}'
        AND dr_date <= TIMESTAMP '{end_date}'
    ORDER BY dr_date
    """

    print("Executing Athena query...\n")
    print("Query:")
    print("-" * 80)
    print(query)
    print("-" * 80)
    print()

    # Execute query
    try:
        results = execute_athena_query(query)

        print(f"\n✅ Query completed successfully")
        print(f"Found {len(results)} binary files\n")

        # Parse results
        binary_files = []
        for row in results:
            binary_files.append({
                'document_reference_id': row[0],
                'binary_id': row[1],
                'content_type': row[2],
                'content_size_bytes': int(row[3]) if row[3] else 0,
                'content_title': row[4],
                'dr_date': row[5],
                'dr_type_text': row[6],
                'dr_category_text': row[7],
                'dr_description': row[8],
                'dr_status': row[9],
                'dr_doc_status': row[10],
                'dr_context_period_start': row[11],
                'dr_context_period_end': row[12],
                'dr_facility_type': row[13],
                'age_at_document_days': int(row[14]) if row[14] else None
            })

        # Display results
        print("Binary Files Found:")
        print("=" * 80)

        for i, file in enumerate(binary_files, 1):
            print(f"\n{i}. {file['content_title'] or 'Untitled'}")
            print(f"   Binary ID: {file['binary_id']}")
            print(f"   Document Reference: {file['document_reference_id']}")
            print(f"   Type: {file['content_type']}")
            print(f"   Size: {file['content_size_bytes']:,} bytes")
            print(f"   Document Date: {file['dr_date']}")
            print(f"   Category: {file['dr_category_text']}")
            print(f"   Type: {file['dr_type_text']}")
            print(f"   Description: {file['dr_description']}")
            print(f"   Age at Document: {file['age_at_document_days']} days")

        # Save results
        output_path = Path("data/qa_reports") / f"{patient_id}_binary_files_temporal_inconsistency.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(binary_files, f, indent=2)

        print(f"\n\n✅ Saved results to: {output_path}")

        return binary_files

    except Exception as e:
        print(f"\n❌ Query failed: {str(e)}")
        return []


def main():
    """Main execution"""
    # Patient and event details from temporal inconsistency
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    event1_date = "2018-05-27"  # Increased
    event2_date = "2018-05-29"  # Decreased

    binary_files = query_binary_files_for_temporal_inconsistency(
        patient_id=patient_id,
        event1_date=event1_date,
        event2_date=event2_date,
        days_window=7
    )

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\nAgent 1 (Claude) will:")
    print(f"  1. Extract text from {len(binary_files)} PDFs using BinaryFileAgent + PyMuPDF")
    print("  2. Build multi-source prompt with imaging text + PDFs")
    print("  3. Query Agent 2 (MedGemma) for re-review")
    print("  4. Adjudicate based on Agent 2's multi-source assessment")
    print()


if __name__ == "__main__":
    main()
