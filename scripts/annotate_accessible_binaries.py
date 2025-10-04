#!/usr/bin/env python3
"""
Enhance accessible_binary_files.csv with additional annotations.
Reads existing CSV and adds type_coding_display, content_type, and category_text columns.

CRITICAL FIXES IMPLEMENTED:
1. Full batching: Processes ALL documents in batches of 1,000 (no limits)
2. Multiple values: Documents with multiple content types/categories stored as semicolon-separated lists
   Example: "text/html; text/rtf" for documents with both HTML and RTF versions
3. No preferences: ALL annotations captured without filtering or prioritization
4. Proper JOIN handling: Each annotation type queried separately with batching to handle Athena query limits

USAGE:
  python3 annotate_accessible_binaries.py

INPUT:
  accessible_binary_files.csv (from query_accessible_binaries.py)

OUTPUT:
  accessible_binary_files_annotated.csv with 3 additional columns:
    - type_coding_display: Document type coding display name(s)
    - content_type: MIME type(s) from content_attachment_content_type
    - category_text: Document category/categories

RUNTIME: ~10-15 minutes for ~4,000 documents (12 Athena queries total)
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
    
    # Batch size for queries (Athena has query length limits)
    BATCH_SIZE = 1000
    total_batches = (len(doc_ref_ids) + BATCH_SIZE - 1) // BATCH_SIZE
    
    # Query for type_coding_display (with batching)
    print(f"Step 2: Querying type_coding_display...")
    print(f"  Processing {len(doc_ref_ids)} documents in {total_batches} batches of {BATCH_SIZE}")
    type_coding_map = {}
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ref_ids))
        batch_ids = doc_ref_ids[start_idx:end_idx]
        
        print(f"  Batch {batch_num + 1}/{total_batches}: Processing documents {start_idx + 1}-{end_idx}...")
        type_coding_query = f"""
        SELECT 
            document_reference_id,
            type_coding_display
        FROM fhir_v1_prd_db.document_reference_type_coding
        WHERE document_reference_id IN ({','.join("'" + id + "'" for id in batch_ids)})
        """
        type_coding_results = run_athena_query(type_coding_query)
        # Handle multiple type codings per document - store all as comma-separated list
        for row in type_coding_results:
            doc_id, type_coding = row[0], row[1]
            if doc_id in type_coding_map:
                # Document has multiple type codings - append to list
                existing_types = type_coding_map[doc_id].split('; ')
                if type_coding not in existing_types:
                    type_coding_map[doc_id] = type_coding_map[doc_id] + '; ' + type_coding
            else:
                type_coding_map[doc_id] = type_coding
    
    print(f"  ✅ Retrieved {len(type_coding_map)} type_coding_display values")
    print()
    
    # Query for content_type (from document_reference_content) - with batching
    print(f"Step 3: Querying content_type...")
    print(f"  Processing {len(doc_ref_ids)} documents in {total_batches} batches of {BATCH_SIZE}")
    content_type_map = {}
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ref_ids))
        batch_ids = doc_ref_ids[start_idx:end_idx]
        
        print(f"  Batch {batch_num + 1}/{total_batches}: Processing documents {start_idx + 1}-{end_idx}...")
        content_type_query = f"""
        SELECT 
            document_reference_id,
            content_attachment_content_type
        FROM fhir_v1_prd_db.document_reference_content
        WHERE document_reference_id IN ({','.join("'" + id + "'" for id in batch_ids)})
        """
        content_type_results = run_athena_query(content_type_query)
        # Handle multiple content types per document - store all as comma-separated list
        for row in content_type_results:
            doc_id, content_type = row[0], row[1]
            if doc_id in content_type_map:
                # Document has multiple content types - append to list
                existing_types = content_type_map[doc_id].split('; ')
                if content_type not in existing_types:
                    content_type_map[doc_id] = content_type_map[doc_id] + '; ' + content_type
            else:
                content_type_map[doc_id] = content_type
    
    print(f"  ✅ Retrieved {len(content_type_map)} content_type values")
    print()
    
    # Query for category_text (with batching)
    print(f"Step 4: Querying category_text...")
    print(f"  Processing {len(doc_ref_ids)} documents in {total_batches} batches of {BATCH_SIZE}")
    category_map = {}
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(doc_ref_ids))
        batch_ids = doc_ref_ids[start_idx:end_idx]
        
        print(f"  Batch {batch_num + 1}/{total_batches}: Processing documents {start_idx + 1}-{end_idx}...")
        category_query = f"""
        SELECT 
            document_reference_id,
            category_text
        FROM fhir_v1_prd_db.document_reference_category
        WHERE document_reference_id IN ({','.join("'" + id + "'" for id in batch_ids)})
        """
        category_results = run_athena_query(category_query)
        # Handle multiple categories per document - store all as comma-separated list
        for row in category_results:
            doc_id, category = row[0], row[1]
            if doc_id in category_map:
                # Document has multiple categories - append to list
                existing_cats = category_map[doc_id].split('; ')
                if category not in existing_cats:
                    category_map[doc_id] = category_map[doc_id] + '; ' + category
            else:
                category_map[doc_id] = category
    
    print(f"  ✅ Retrieved {len(category_map)} category_text values")
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
