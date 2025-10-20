#!/usr/bin/env python3
"""
Load Radiology Reports into Source Documents Table

Extracts radiology report text from v_imaging and stores in source_documents table
for agent-based extraction workflow.
"""

import sys
import boto3
import time
import pandas as pd
import duckdb
import json
from datetime import datetime

# AWS Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
AWS_REGION = 'us-east-1'
ATHENA_DATABASE = 'fhir_prd_db'
ATHENA_OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'

# DuckDB Configuration
DUCKDB_PATH = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/data/timeline.duckdb"

# Test patient
TEST_PATIENT_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"

def execute_athena_query(query, database=ATHENA_DATABASE):
    """Execute Athena query and return results as pandas DataFrame"""
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    athena_client = session.client('athena')

    # Start query execution
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
    )

    query_execution_id = response['QueryExecutionId']
    print(f"Started Athena query: {query_execution_id}")

    # Wait for query to complete
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            print(f"Query succeeded!")
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            raise Exception(f"Query {status}: {reason}")

        print(f"Query status: {status}... waiting")
        time.sleep(2)

    # Get results
    results = []
    columns = None
    paginator = athena_client.get_paginator('get_query_results')

    for page_num, page in enumerate(paginator.paginate(QueryExecutionId=query_execution_id)):
        rows = page['ResultSet']['Rows']

        # First page, first row contains column names
        if page_num == 0 and rows:
            columns = [col.get('VarCharValue', '') for col in rows[0]['Data']]
            rows = rows[1:]  # Skip header row

        # Extract data rows
        for row in rows:
            row_data = []
            for col in row['Data']:
                value = col.get('VarCharValue')
                row_data.append(value)
            results.append(row_data)

    # Create DataFrame
    df = pd.DataFrame(results, columns=columns)

    print(f"Retrieved {len(df)} rows")
    return df


def load_radiology_reports_for_patient(patient_id):
    """
    Load radiology reports from v_imaging for specific patient

    Returns DataFrame with:
    - imaging_procedure_id (for document_id construction)
    - patient_fhir_id
    - imaging_date
    - imaging_modality
    - imaging_procedure
    - report_conclusion (full text)
    - result_information (additional text)
    - report_status
    - diagnostic_report_id
    """
    print(f"\n{'='*80}")
    print(f"Loading radiology reports for patient: {patient_id}")
    print(f"{'='*80}\n")

    query = f"""
    SELECT
        patient_fhir_id,
        imaging_procedure_id,
        imaging_date,
        imaging_modality,
        imaging_procedure,
        report_conclusion,
        result_information,
        result_display,
        report_status,
        diagnostic_report_id
    FROM {ATHENA_DATABASE}.v_imaging
    WHERE patient_fhir_id = '{patient_id}'
    ORDER BY imaging_date DESC
    """

    df = execute_athena_query(query)

    # Combine report_conclusion and result_information into single document_text
    # Prefer result_information (which has the detailed reports), fall back to report_conclusion
    df['document_text'] = df.apply(
        lambda row: (row['result_information'] or row['report_conclusion'] or '').strip(),
        axis=1
    )

    df['char_count'] = df['document_text'].apply(len)

    print(f"\nRadiology report statistics:")
    print(f"  Total imaging events: {len(df)}")
    print(f"  With report text: {(df['char_count'] > 0).sum()}")
    print(f"  With substantial text (>100 chars): {(df['char_count'] > 100).sum()}")
    print(f"  Average length: {df['char_count'].mean():.0f} chars")
    print(f"  Max length: {df['char_count'].max()} chars")

    return df


def insert_reports_into_duckdb(df, conn, patient_id):
    """Insert radiology reports into source_documents table"""

    print(f"\n{'='*80}")
    print(f"Inserting radiology reports into source_documents table")
    print(f"{'='*80}\n")

    inserted_count = 0

    for idx, row in df.iterrows():
        # Skip empty reports
        if not row['document_text'] or len(row['document_text']) == 0:
            continue

        # Construct document_id
        document_id = f"rad_report_{row['imaging_procedure_id']}"

        # Construct metadata JSON
        metadata = {
            'imaging_modality': row['imaging_modality'],
            'imaging_procedure': row['imaging_procedure'],
            'report_status': row['report_status'],
            'result_display': row['result_display']
        }
        metadata_json = json.dumps(metadata)

        # Find corresponding event_id in timeline
        event_id_result = conn.execute("""
            SELECT event_id FROM events
            WHERE patient_id = ?
            AND source_view = 'v_imaging'
            AND source_id = ?
            LIMIT 1
        """, [patient_id, row['imaging_procedure_id']]).fetchone()

        source_event_id = event_id_result[0] if event_id_result else None

        # Insert into source_documents
        conn.execute("""
            INSERT OR REPLACE INTO source_documents (
                document_id,
                patient_id,
                document_type,
                document_date,
                source_event_id,
                source_view,
                source_domain,
                source_id,
                document_text,
                char_count,
                metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            document_id,
            patient_id,
            'radiology_report',
            pd.to_datetime(row['imaging_date']) if pd.notna(row['imaging_date']) else None,
            source_event_id,
            'v_imaging',
            'DiagnosticReport',
            row['imaging_procedure_id'],
            row['document_text'],
            int(row['char_count']) if pd.notna(row['char_count']) else 0,
            metadata_json
        ])

        inserted_count += 1

        if inserted_count % 50 == 0:
            print(f"  Inserted {inserted_count} reports...")

    print(f"✓ Inserted {inserted_count} radiology reports")

    # Verify insertion
    result = conn.execute("""
        SELECT COUNT(*) as count FROM source_documents
        WHERE patient_id = ? AND document_type = 'radiology_report'
    """, [patient_id]).fetchone()

    print(f"✓ Verified {result[0]} radiology reports in database")

    return inserted_count


def main():
    print("=" * 80)
    print("LOAD RADIOLOGY REPORTS INTO SOURCE DOCUMENTS")
    print(f"Patient: {TEST_PATIENT_ID}")
    print("=" * 80)
    print()

    # Load reports from Athena
    df = load_radiology_reports_for_patient(TEST_PATIENT_ID)

    # Connect to DuckDB
    conn = duckdb.connect(DUCKDB_PATH)

    # Insert into source_documents table
    inserted = insert_reports_into_duckdb(df, conn, TEST_PATIENT_ID)

    # Show summary
    print(f"\n{'='*80}")
    print("RADIOLOGY REPORTS SUMMARY")
    print(f"{'='*80}\n")

    summary = conn.execute("""
        SELECT
            COUNT(*) as total_reports,
            MIN(char_count) as min_length,
            AVG(char_count) as avg_length,
            MAX(char_count) as max_length,
            SUM(CASE WHEN char_count > 1000 THEN 1 ELSE 0 END) as substantial_reports
        FROM source_documents
        WHERE patient_id = ? AND document_type = 'radiology_report'
    """, [TEST_PATIENT_ID]).fetchdf()

    print(summary.to_string(index=False))

    # Sample reports
    print(f"\n{'='*80}")
    print("SAMPLE REPORTS (Most Recent)")
    print(f"{'='*80}\n")

    samples = conn.execute("""
        SELECT
            document_id,
            document_date,
            char_count,
            SUBSTR(document_text, 1, 150) || '...' as preview
        FROM source_documents
        WHERE patient_id = ? AND document_type = 'radiology_report'
        AND char_count > 100
        ORDER BY document_date DESC
        LIMIT 3
    """, [TEST_PATIENT_ID]).fetchdf()

    for idx, row in samples.iterrows():
        print(f"Document: {row['document_id']}")
        print(f"Date: {row['document_date']}")
        print(f"Length: {row['char_count']} chars")
        print(f"Preview: {row['preview']}")
        print()

    conn.close()

    print("=" * 80)
    print("✅ RADIOLOGY REPORTS LOADED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()
