#!/usr/bin/env python3
"""
Extract Comprehensive Metadata for Binary Files

This script pulls ALL available metadata elements for each accessible binary file from FHIR HealthLake.
Queries each table separately and then combines results to avoid complex JOINs.

Based on the successful pattern from annotate_accessible_binaries.py

Author: BRIM Analytics Team
Date: October 5, 2025
"""

import boto3
import pandas as pd
import time
import sys
import os

# AWS Configuration
AWS_PROFILE = "343218191717_AWSAdministratorAccess"
ATHENA_DATABASE = "fhir_v1_prd_db"
ATHENA_OUTPUT_LOCATION = "s3://fhir-v1-athena-results-prd/query-results/"
PATIENT_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"

# Input/Output paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
INPUT_FILE = os.path.join(PROJECT_ROOT, "pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files_annotated.csv")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files_comprehensive_metadata.csv")


def get_boto3_session():
    """Initialize boto3 session with AWS profile"""
    return boto3.Session(profile_name=AWS_PROFILE)


def run_athena_query(query, session):
    """Execute Athena query and wait for results."""
    athena_client = session.client('athena', region_name='us-east-1')

    print(f"Executing Athena query...")

    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': ATHENA_DATABASE},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
    )

    query_execution_id = response['QueryExecutionId']
    print(f"Query execution ID: {query_execution_id}")

    # Wait for query to complete
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        state = response['QueryExecution']['Status']['State']

        if state == 'SUCCEEDED':
            print("Query succeeded!")
            break
        elif state in ['FAILED', 'CANCELLED']:
            reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"Query {state}: {reason}")
            raise Exception(f"Query failed: {reason}")
        else:
            print(f"Query state: {state}, waiting...")
            time.sleep(2)

    # Get results
    results = []
    next_token = None

    while True:
        if next_token:
            response = athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                NextToken=next_token
            )
        else:
            response = athena_client.get_query_results(QueryExecutionId=query_execution_id)

        # Parse results (skip header row)
        rows = response['ResultSet']['Rows']
        if not results:  # First batch includes header
            rows = rows[1:]

        for row in rows:
            values = [col.get('VarCharValue', '') for col in row['Data']]
            results.append(values)

        next_token = response.get('NextToken')
        if not next_token:
            break

    return results


def query_document_reference_fields(doc_ids, session):
    """Query core document_reference table for main metadata fields"""
    BATCH_SIZE = 1000
    total_batches = (len(doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n{'='*80}")
    print("QUERYING DOCUMENT_REFERENCE TABLE (Core Metadata)")
    print(f"{'='*80}")

    all_results = []

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ids))
        batch_ids = doc_ids[start_idx:end_idx]

        print(f"\nBatch {batch_num + 1}/{total_batches}: Processing {len(batch_ids)} documents...")

        id_list = "', '".join(batch_ids)
        query = f"""
        SELECT
            id,
            subject_reference,
            status,
            date,
            doc_status,
            type_text,
            description,
            context_period_start,
            context_period_end,
            context_facility_type_text,
            context_practice_setting_text,
            context_source_patient_info_reference,
            context_source_patient_info_type,
            context_source_patient_info_display
        FROM fhir_v1_prd_db.document_reference
        WHERE id IN ('{id_list}')
        """

        results = run_athena_query(query, session)
        all_results.extend(results)

    # Convert to DataFrame
    columns = [
        'document_reference_id', 'subject_reference', 'status', 'date',
        'doc_status', 'type_text', 'description',
        'context_period_start', 'context_period_end',
        'context_facility_type_text', 'context_practice_setting_text',
        'context_source_patient_info_reference', 'context_source_patient_info_type',
        'context_source_patient_info_display'
    ]

    df = pd.DataFrame(all_results, columns=columns)
    print(f"\n✅ Retrieved {len(df)} document_reference records")
    return df


def query_type_coding(doc_ids, session):
    """Query document_reference_type_coding table"""
    BATCH_SIZE = 1000
    total_batches = (len(doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n{'='*80}")
    print("QUERYING DOCUMENT_REFERENCE_TYPE_CODING TABLE")
    print(f"{'='*80}")

    type_coding_map = {}

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ids))
        batch_ids = doc_ids[start_idx:end_idx]

        print(f"\nBatch {batch_num + 1}/{total_batches}: Processing {len(batch_ids)} documents...")

        id_list = "', '".join(batch_ids)
        query = f"""
        SELECT
            document_reference_id,
            type_coding_system,
            type_coding_code,
            type_coding_display
        FROM fhir_v1_prd_db.document_reference_type_coding
        WHERE document_reference_id IN ('{id_list}')
        """

        results = run_athena_query(query, session)

        for row in results:
            doc_id = row[0]
            if doc_id not in type_coding_map:
                type_coding_map[doc_id] = {
                    'type_coding_system': [],
                    'type_coding_code': [],
                    'type_coding_display': []
                }
            type_coding_map[doc_id]['type_coding_system'].append(row[1])
            type_coding_map[doc_id]['type_coding_code'].append(row[2])
            type_coding_map[doc_id]['type_coding_display'].append(row[3])

    # Convert lists to semicolon-separated strings
    for doc_id in type_coding_map:
        type_coding_map[doc_id]['type_coding_system'] = '; '.join(filter(None, type_coding_map[doc_id]['type_coding_system']))
        type_coding_map[doc_id]['type_coding_code'] = '; '.join(filter(None, type_coding_map[doc_id]['type_coding_code']))
        type_coding_map[doc_id]['type_coding_display'] = '; '.join(filter(None, type_coding_map[doc_id]['type_coding_display']))

    print(f"\n✅ Retrieved type coding for {len(type_coding_map)} documents")
    return type_coding_map


def query_content(doc_ids, session):
    """Query document_reference_content table"""
    BATCH_SIZE = 1000
    total_batches = (len(doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n{'='*80}")
    print("QUERYING DOCUMENT_REFERENCE_CONTENT TABLE")
    print(f"{'='*80}")

    content_map = {}

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ids))
        batch_ids = doc_ids[start_idx:end_idx]

        print(f"\nBatch {batch_num + 1}/{total_batches}: Processing {len(batch_ids)} documents...")

        id_list = "', '".join(batch_ids)
        query = f"""
        SELECT
            document_reference_id,
            content_attachment_content_type,
            content_attachment_url,
            content_attachment_creation,
            content_attachment_title,
            content_format_code,
            content_format_display,
            content_format_system
        FROM fhir_v1_prd_db.document_reference_content
        WHERE document_reference_id IN ('{id_list}')
        """

        results = run_athena_query(query, session)

        for row in results:
            doc_id = row[0]
            if doc_id not in content_map:
                content_map[doc_id] = {
                    'content_attachment_content_type': [],
                    'content_attachment_url': [],
                    'content_attachment_creation': [],
                    'content_attachment_title': [],
                    'content_format_code': [],
                    'content_format_display': [],
                    'content_format_system': []
                }
            content_map[doc_id]['content_attachment_content_type'].append(row[1])
            content_map[doc_id]['content_attachment_url'].append(row[2])
            content_map[doc_id]['content_attachment_creation'].append(row[3])
            content_map[doc_id]['content_attachment_title'].append(row[4])
            content_map[doc_id]['content_format_code'].append(row[5])
            content_map[doc_id]['content_format_display'].append(row[6])
            content_map[doc_id]['content_format_system'].append(row[7])

    # Convert lists to semicolon-separated strings
    for doc_id in content_map:
        for key in content_map[doc_id]:
            content_map[doc_id][key] = '; '.join(filter(None, content_map[doc_id][key]))

    print(f"\n✅ Retrieved content metadata for {len(content_map)} documents")
    return content_map


def query_category(doc_ids, session):
    """Query document_reference_category table"""
    BATCH_SIZE = 1000
    total_batches = (len(doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n{'='*80}")
    print("QUERYING DOCUMENT_REFERENCE_CATEGORY TABLE")
    print(f"{'='*80}")

    category_map = {}

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ids))
        batch_ids = doc_ids[start_idx:end_idx]

        print(f"\nBatch {batch_num + 1}/{total_batches}: Processing {len(batch_ids)} documents...")

        id_list = "', '".join(batch_ids)
        query = f"""
        SELECT
            document_reference_id,
            category_text
        FROM fhir_v1_prd_db.document_reference_category
        WHERE document_reference_id IN ('{id_list}')
        """

        results = run_athena_query(query, session)

        for row in results:
            doc_id = row[0]
            if doc_id not in category_map:
                category_map[doc_id] = {'category_text': []}
            category_map[doc_id]['category_text'].append(row[1])

    # Convert lists to semicolon-separated strings
    for doc_id in category_map:
        for key in category_map[doc_id]:
            category_map[doc_id][key] = '; '.join(filter(None, category_map[doc_id][key]))

    print(f"\n✅ Retrieved category metadata for {len(category_map)} documents")
    return category_map


def query_context_encounter(doc_ids, session):
    """Query document_reference_context_encounter table"""
    BATCH_SIZE = 1000
    total_batches = (len(doc_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n{'='*80}")
    print("QUERYING DOCUMENT_REFERENCE_CONTEXT_ENCOUNTER TABLE")
    print(f"{'='*80}")

    encounter_map = {}

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ids))
        batch_ids = doc_ids[start_idx:end_idx]

        print(f"\nBatch {batch_num + 1}/{total_batches}: Processing {len(batch_ids)} documents...")

        id_list = "', '".join(batch_ids)
        query = f"""
        SELECT
            document_reference_id,
            context_encounter_reference
        FROM fhir_v1_prd_db.document_reference_context_encounter
        WHERE document_reference_id IN ('{id_list}')
        """

        results = run_athena_query(query, session)

        for row in results:
            doc_id = row[0]
            if doc_id not in encounter_map:
                encounter_map[doc_id] = []
            encounter_map[doc_id].append(row[1])

    # Convert lists to semicolon-separated strings
    for doc_id in encounter_map:
        encounter_map[doc_id] = '; '.join(filter(None, encounter_map[doc_id]))

    print(f"\n✅ Retrieved encounter references for {len(encounter_map)} documents")
    return encounter_map


def main():
    print("=" * 80)
    print("COMPREHENSIVE METADATA EXTRACTION FOR ACCESSIBLE BINARY FILES")
    print("=" * 80)

    # Load accessible binary files
    print(f"\nLoading accessible binary files from: {INPUT_FILE}")
    accessible_df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(accessible_df)} accessible binary files")

    # Get unique document reference IDs
    document_ids = accessible_df['document_reference_id'].unique().tolist()
    print(f"Unique document reference IDs: {len(document_ids)}")

    # Initialize session
    session = get_boto3_session()

    # Query each table separately
    doc_ref_df = query_document_reference_fields(document_ids, session)
    type_coding_map = query_type_coding(document_ids, session)
    content_map = query_content(document_ids, session)
    category_map = query_category(document_ids, session)
    encounter_map = query_context_encounter(document_ids, session)

    # Combine all metadata into main dataframe
    print(f"\n{'='*80}")
    print("COMBINING ALL METADATA")
    print(f"{'='*80}")

    # Add type coding fields
    doc_ref_df['type_coding_system'] = doc_ref_df['document_reference_id'].map(
        lambda x: type_coding_map.get(x, {}).get('type_coding_system', ''))
    doc_ref_df['type_coding_code'] = doc_ref_df['document_reference_id'].map(
        lambda x: type_coding_map.get(x, {}).get('type_coding_code', ''))
    doc_ref_df['type_coding_display'] = doc_ref_df['document_reference_id'].map(
        lambda x: type_coding_map.get(x, {}).get('type_coding_display', ''))

    # Add content fields
    doc_ref_df['content_attachment_content_type'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_attachment_content_type', ''))
    doc_ref_df['content_attachment_url'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_attachment_url', ''))
    doc_ref_df['content_attachment_creation'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_attachment_creation', ''))
    doc_ref_df['content_attachment_title'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_attachment_title', ''))
    doc_ref_df['content_format_code'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_format_code', ''))
    doc_ref_df['content_format_display'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_format_display', ''))
    doc_ref_df['content_format_system'] = doc_ref_df['document_reference_id'].map(
        lambda x: content_map.get(x, {}).get('content_format_system', ''))

    # Add category fields
    doc_ref_df['category_text'] = doc_ref_df['document_reference_id'].map(
        lambda x: category_map.get(x, {}).get('category_text', ''))

    # Add encounter reference
    doc_ref_df['context_encounter_reference'] = doc_ref_df['document_reference_id'].map(
        lambda x: encounter_map.get(x, ''))

    print(f"Combined metadata: {len(doc_ref_df)} rows, {len(doc_ref_df.columns)} columns")

    # Display sample
    print("\n" + "=" * 80)
    print("SAMPLE METADATA (first 3 rows):")
    print("=" * 80)
    print(doc_ref_df.head(3).to_string())

    # Save to CSV
    print(f"\nSaving comprehensive metadata to: {OUTPUT_FILE}")
    doc_ref_df.to_csv(OUTPUT_FILE, index=False)

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE!")
    print("=" * 80)
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Total rows: {len(doc_ref_df)}")
    print(f"Total columns: {len(doc_ref_df.columns)}")

    # Display metadata field availability summary
    print("\n" + "=" * 80)
    print("METADATA FIELD AVAILABILITY SUMMARY:")
    print("=" * 80)

    for col in doc_ref_df.columns:
        non_null = doc_ref_df[col].notna().sum()
        non_empty = (doc_ref_df[col] != '').sum()
        pct = (non_empty / len(doc_ref_df)) * 100
        print(f"  {col:50s}: {non_empty:5d} ({pct:5.1f}%)")

    # Display unique practice settings found
    if 'context_practice_setting_text' in doc_ref_df.columns:
        practice_settings = doc_ref_df['context_practice_setting_text'].dropna()
        practice_settings = practice_settings[practice_settings != ''].unique()
        if len(practice_settings) > 0:
            print("\n" + "=" * 80)
            print("UNIQUE PRACTICE SETTINGS FOUND:")
            print("=" * 80)
            for setting in sorted(practice_settings):
                count = len(doc_ref_df[doc_ref_df['context_practice_setting_text'] == setting])
                print(f"  {setting:50s}: {count:5d} documents")


if __name__ == "__main__":
    main()
