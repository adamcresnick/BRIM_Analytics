#!/usr/bin/env python3
"""
Query all DocumentReferences for patient C1277724 and verify S3 Binary availability.
Creates accessible_binary_files.csv with only S3-available documents.
"""

import boto3
import time
import csv
import sys
from datetime import datetime

# Configuration
PATIENT_FHIR_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"
AWS_PROFILE = "343218191717_AWSAdministratorAccess"
AWS_REGION = "us-east-1"
ATHENA_DATABASE = "fhir_v1_prd_db"
S3_OUTPUT = "s3://aws-athena-query-results-343218191717-us-east-1/"
S3_BUCKET = "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline"
S3_PREFIX = "prd/source/Binary/"

# Initialize AWS clients
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
athena = session.client('athena')
s3 = session.client('s3')

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

def check_s3_availability(binary_id):
    """Check if Binary file exists in S3."""
    if not binary_id or binary_id == 'Binary/':
        return False
    
    # Extract ID from Binary/xxx format
    if binary_id.startswith('Binary/'):
        binary_id = binary_id.replace('Binary/', '')
    
    # Apply period-to-underscore bug fix
    s3_key = f"{S3_PREFIX}{binary_id.replace('.', '_')}"
    
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except:
        return False

def main():
    print("="*80)
    print("ACCESSIBLE BINARY FILES QUERY - Patient C1277724")
    print("="*80)
    print(f"Patient FHIR ID: {PATIENT_FHIR_ID}")
    print(f"Database: {ATHENA_DATABASE}")
    print(f"S3 Bucket: {S3_BUCKET}")
    print(f"S3 Prefix: {S3_PREFIX}")
    print()
    
    # Query all DocumentReferences with Binary IDs
    query = f"""
    SELECT 
        dr.id as document_reference_id,
        dr.type_text as document_type,
        drtc.type_coding_display as type_coding_display,
        dr.date as document_date,
        drc.content_attachment_url as binary_id,
        drc.content_attachment_content_type as content_type,
        drcat.category_text as category_text,
        dr.description as document_description,
        dr.context_period_start as context_start,
        dr.context_period_end as context_end
    FROM fhir_v1_prd_db.document_reference dr
    INNER JOIN fhir_v1_prd_db.document_reference_content drc
        ON dr.id = drc.document_reference_id
    LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
        ON dr.id = drtc.document_reference_id
    LEFT JOIN fhir_v1_prd_db.document_reference_category drcat
        ON dr.id = drcat.document_reference_id
    WHERE dr.subject_reference = '{PATIENT_FHIR_ID}'
        AND drc.content_attachment_url IS NOT NULL
        AND drc.content_attachment_url != ''
        AND drc.content_attachment_url LIKE 'Binary/%'
    ORDER BY dr.date DESC;
    """
    
    print("Step 1: Querying all DocumentReferences...")
    results = run_athena_query(query)
    print(f"Found {len(results)} DocumentReferences with Binary IDs")
    print()
    
    # Check S3 availability for each
    print("Step 2: Checking S3 availability for each Binary...")
    accessible = []
    unavailable_count = 0
    
    for i, row in enumerate(results, 1):
        doc_ref_id, doc_type, type_coding_display, doc_date, binary_id, content_type, category_text, description, ctx_start, ctx_end = row
        
        if i % 100 == 0:
            print(f"  Checked {i}/{len(results)} documents...")
        
        is_available = check_s3_availability(binary_id)
        
        if is_available:
            accessible.append({
                'document_reference_id': doc_ref_id,
                'document_type': doc_type,
                'type_coding_display': type_coding_display,
                'document_date': doc_date,
                'binary_id': binary_id,
                'content_type': content_type,
                'category_text': category_text,
                'description': description,
                'context_start': ctx_start,
                'context_end': ctx_end,
                's3_available': 'Yes'
            })
        else:
            unavailable_count += 1
    
    print(f"  Checked all {len(results)} documents")
    print()
    
    # Summary
    print("="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    print(f"Total DocumentReferences queried: {len(results)}")
    print(f"S3-Available Binary files: {len(accessible)}")
    print(f"S3-Unavailable Binary files: {unavailable_count}")
    if len(results) > 0:
        print(f"Availability rate: {len(accessible)/len(results)*100:.1f}%")
    print()
    
    # Save to CSV
    output_file = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files.csv'
    
    print(f"Step 3: Writing accessible documents to CSV...")
    with open(output_file, 'w', newline='') as f:
        if accessible:
            writer = csv.DictWriter(f, fieldnames=accessible[0].keys())
            writer.writeheader()
            writer.writerows(accessible)
    
    print(f"✅ Created: {output_file}")
    print(f"   ({len(accessible)} S3-available documents)")
    print()
    
    # Show sample by document type
    if accessible:
        print("Document Type Distribution (S3-Available):")
        type_counts = {}
        for doc in accessible:
            doc_type = doc['document_type'] or 'Unknown'
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        
        for doc_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {doc_type}: {count}")
    
    print()
    print("="*80)
    print("COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
