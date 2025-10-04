#!/usr/bin/env python3
"""
Enhance accessible_binary_files.csv with additional annotations.
Reads existing CSV and adds type_coding_display, content_type, and category_text columns.
"""

import boto3
import time
import csv
import sys

# Configuration
AWS_PROFILE = "343218191717_AWSAdministratorAccess"
AWS_REGION = "us-east-1"
ATHENA_DATABASE = "fhir_v1_prd_db"
S3_OUTPUT = "s3://aws-athena-query-results-343218191717-us-east-1/"

# File paths
INPUT_FILE = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files.csv'
OUTPUT_FILE = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files_annotated.csv'

# Initialize AWS clients
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
athena = session.client('athena')

def run_athena_query(query):
    """Execute Athena query and wait for results."""
    print(f"Executing Athena query...")
    
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': ATHENA_DATABASE},
        ResultConfiguration={'OutputLocation': S3_OUTPUT}
    )
    
    query_execution_id = response['QueryExecutionId']
    print(f"Query execution ID: {query_execution_id}")
    
    # Wait for query to complete
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = response['QueryExecution']['Status']['State']
        
        if state == 'SUCCEEDED':
            print("Query succeeded!")
            break
        elif state in ['FAILED', 'CANCELLED']:
            reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"Query {state}: {reason}")
            sys.exit(1)
        else:
            print(f"Query state: {state}, waiting...")
            time.sleep(2)
    
    # Get results
    results = []
    next_token = None
    
    while True:
        if next_token:
            response = athena.get_query_results(
                QueryExecutionId=query_execution_id,
                NextToken=next_token
            )
        else:
            response = athena.get_query_results(QueryExecutionId=query_execution_id)
        
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

def main():
    print("="*80)
    print("ENHANCE ACCESSIBLE BINARY FILES WITH ANNOTATIONS")
    print("="*80)
    print()
    
    # Read existing accessible_binary_files.csv
    print(f"Step 1: Reading existing file...")
    print(f"  Input: {INPUT_FILE}")
    
    with open(INPUT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        existing_docs = list(reader)
    
    print(f"  Found {len(existing_docs)} accessible documents")
    print()
    
    # Extract all document_reference_ids
    doc_ref_ids = [doc['document_reference_id'] for doc in existing_docs]
    
    # Query for type_coding_display
    print(f"Step 2: Querying type_coding_display...")
    type_coding_query = f"""
    SELECT 
        document_reference_id,
        type_coding_display
    FROM fhir_v1_prd_db.document_reference_type_coding
    WHERE document_reference_id IN ({','.join("'" + id + "'" for id in doc_ref_ids[:1000])})
    """
    # Note: Athena has query length limits, so we might need to batch this
    type_coding_results = run_athena_query(type_coding_query)
    type_coding_map = {row[0]: row[1] for row in type_coding_results}
    print(f"  Retrieved {len(type_coding_map)} type_coding_display values")
    print()
    
    # Query for content_type (from document_reference_content)
    print(f"Step 3: Querying content_type...")
    content_type_query = f"""
    SELECT 
        document_reference_id,
        content_attachment_content_type
    FROM fhir_v1_prd_db.document_reference_content
    WHERE document_reference_id IN ({','.join("'" + id + "'" for id in doc_ref_ids[:1000])})
    """
    content_type_results = run_athena_query(content_type_query)
    content_type_map = {row[0]: row[1] for row in content_type_results}
    print(f"  Retrieved {len(content_type_map)} content_type values")
    print()
    
    # Query for category_text
    print(f"Step 4: Querying category_text...")
    category_query = f"""
    SELECT 
        document_reference_id,
        category_text
    FROM fhir_v1_prd_db.document_reference_category
    WHERE document_reference_id IN ({','.join("'" + id + "'" for id in doc_ref_ids[:1000])})
    """
    category_results = run_athena_query(category_query)
    category_map = {row[0]: row[1] for row in category_results}
    print(f"  Retrieved {len(category_map)} category_text values")
    print()
    
    # Enhance existing docs with new columns
    print(f"Step 5: Adding annotations to documents...")
    for doc in existing_docs:
        doc_ref_id = doc['document_reference_id']
        doc['type_coding_display'] = type_coding_map.get(doc_ref_id, '')
        doc['content_type'] = content_type_map.get(doc_ref_id, '')
        doc['category_text'] = category_map.get(doc_ref_id, '')
    
    # Write enhanced CSV
    print(f"Step 6: Writing annotated file...")
    print(f"  Output: {OUTPUT_FILE}")
    
    fieldnames = [
        'document_reference_id',
        'document_type',
        'document_type_code',
        'type_coding_display',
        'document_date',
        'binary_id',
        'content_type',
        'category_text',
        'description',
        'context_start',
        'context_end',
        's3_available'
    ]
    
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_docs)
    
    print(f"✅ Created: {OUTPUT_FILE}")
    print(f"   ({len(existing_docs)} documents with 3 additional annotation columns)")
    print()
    
    # Show sample
    print("Sample annotations:")
    for i, doc in enumerate(existing_docs[:5], 1):
        print(f"\n{i}. {doc['document_type']}")
        print(f"   type_coding_display: {doc['type_coding_display']}")
        print(f"   content_type: {doc['content_type']}")
        print(f"   category_text: {doc['category_text']}")
    
    print()
    print("="*80)
    print("COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
