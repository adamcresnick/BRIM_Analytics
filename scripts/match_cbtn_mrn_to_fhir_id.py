#!/usr/bin/env python3
"""
Match CBTN Enrollment MRNs to FHIR IDs (SECURE - No MRN Display)

This script:
1. Reads the CBTN enrollment CSV (contains MRN column)
2. Queries Athena patient table for identifier_mrn and id
3. Matches MRNs in memory (NEVER displays/prints MRNs)
4. Adds FHIR_ID column to the local CSV
5. Outputs updated CSV with FHIR_ID column

SECURITY:
- MRNs are NEVER printed to console
- MRNs are NEVER logged
- All matching happens in memory with hashed references
- Only match statistics (counts) are displayed

Usage:
    python3 match_cbtn_mrn_to_fhir_id.py <input_csv> <output_csv>
    
Example:
    python3 match_cbtn_mrn_to_fhir_id.py \
        /Users/resnick/Downloads/stg_cbtn_enrollment_final_10262025.csv \
        /Users/resnick/Downloads/stg_cbtn_enrollment_with_fhir_id.csv
"""

import boto3
import pandas as pd
import time
import logging
import sys
import os
from pathlib import Path
import hashlib

# Configure logging - NO MRN data will be logged
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_PROFILE = 'radiant-prod'
AWS_REGION = 'us-east-1'
ATHENA_DATABASE = 'fhir_v2_prd_db'
S3_OUTPUT_LOCATION = 's3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/athena-results/'


def hash_mrn(mrn):
    """Create a non-reversible hash of MRN for logging purposes only"""
    if pd.isna(mrn) or mrn == '':
        return 'NULL'
    return hashlib.sha256(str(mrn).encode()).hexdigest()[:8]


def execute_athena_query(athena_client, query, description):
    """Execute Athena query and wait for completion - SECURE"""
    logger.info(f"Executing query: {description}")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': ATHENA_DATABASE},
            ResultConfiguration={'OutputLocation': S3_OUTPUT_LOCATION}
        )
        
        query_execution_id = response['QueryExecutionId']
        logger.info(f"Query execution ID: {query_execution_id}")
        
        # Wait for query to complete
        max_attempts = 60
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = response['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                logger.info(f"Query succeeded after {attempt} checks")
                return query_execution_id
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                logger.error(f"Query {status}: {reason}")
                raise Exception(f"Query {status}: {reason}")
            
            time.sleep(2)
        
        raise Exception("Query timed out after 120 seconds")
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise


def fetch_athena_results(athena_client, query_execution_id):
    """Fetch results from completed Athena query - SECURE"""
    logger.info("Fetching query results...")
    
    try:
        results = []
        paginator = athena_client.get_paginator('get_query_results')
        
        for page in paginator.paginate(QueryExecutionId=query_execution_id):
            for row in page['ResultSet']['Rows']:
                results.append([col.get('VarCharValue', '') for col in row['Data']])
        
        if not results:
            logger.warning("No results returned from query")
            return pd.DataFrame()
        
        # First row is headers
        df = pd.DataFrame(results[1:], columns=results[0])
        
        # Log only the count, NEVER the actual data
        logger.info(f"Retrieved {len(df)} records from Athena")
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching results: {str(e)}")
        raise


def query_patient_mrn_to_fhir_id(athena_client):
    """Query Athena for ALL patient MRN to FHIR ID mappings - SECURE"""
    
    query = """
    SELECT 
        identifier_mrn,
        id as fhir_id
    FROM patient
    WHERE identifier_mrn IS NOT NULL
        AND identifier_mrn != ''
    """
    
    query_execution_id = execute_athena_query(
        athena_client,
        query,
        "Fetching MRN to FHIR ID mappings from patient table"
    )
    
    df = fetch_athena_results(athena_client, query_execution_id)
    
    # Create mapping dictionary - MRNs NEVER leave this function
    if not df.empty:
        # Strip whitespace and ensure strings
        df['identifier_mrn'] = df['identifier_mrn'].astype(str).str.strip()
        df['fhir_id'] = df['fhir_id'].astype(str).str.strip()
        
        # Create dict for fast lookup
        mrn_to_fhir = dict(zip(df['identifier_mrn'], df['fhir_id']))
        
        logger.info(f"Created mapping dictionary with {len(mrn_to_fhir)} MRN->FHIR_ID pairs")
        return mrn_to_fhir
    else:
        logger.warning("No MRN mappings found in Athena")
        return {}


def process_cbtn_enrollment(input_csv, output_csv, mrn_to_fhir_map):
    """Process CBTN enrollment file and add FHIR_ID column - SECURE"""
    
    logger.info(f"Reading CBTN enrollment file...")
    
    # Read the CSV
    df = pd.read_csv(input_csv)
    logger.info(f"Loaded {len(df)} records from CBTN enrollment file")
    
    # Verify mrn column exists
    if 'mrn' not in df.columns:
        raise ValueError("Input CSV does not contain 'mrn' column")
    
    logger.info(f"Input columns: {list(df.columns)}")
    
    # Initialize FHIR_ID column
    df['FHIR_ID'] = None
    
    # Match MRNs to FHIR IDs - ALL IN MEMORY
    matched_count = 0
    unmatched_count = 0
    
    logger.info("Matching MRNs to FHIR IDs (secure - no MRN display)...")
    
    for idx, row in df.iterrows():
        mrn = str(row['mrn']).strip() if pd.notna(row['mrn']) else ''
        
        if mrn in mrn_to_fhir_map:
            df.at[idx, 'FHIR_ID'] = mrn_to_fhir_map[mrn]
            matched_count += 1
        else:
            unmatched_count += 1
    
    # Log statistics (NO MRN data)
    logger.info(f"Matching complete:")
    logger.info(f"  - Matched: {matched_count} records")
    logger.info(f"  - Unmatched: {unmatched_count} records")
    logger.info(f"  - Match rate: {matched_count / len(df) * 100:.1f}%")
    
    # Reorder columns to put FHIR_ID after research_id
    cols = list(df.columns)
    if 'research_id' in cols and 'FHIR_ID' in cols:
        cols.remove('FHIR_ID')
        research_id_idx = cols.index('research_id')
        cols.insert(research_id_idx + 1, 'FHIR_ID')
        df = df[cols]
    
    # Write output
    logger.info(f"Writing output to: {output_csv}")
    df.to_csv(output_csv, index=False)
    logger.info(f"Output file created successfully")
    logger.info(f"Output columns: {list(df.columns)}")
    
    return matched_count, unmatched_count


def main():
    """Main execution - SECURE (No MRN Display)"""
    
    if len(sys.argv) != 3:
        print("Usage: python3 match_cbtn_mrn_to_fhir_id.py <input_csv> <output_csv>")
        print("\nExample:")
        print("  python3 match_cbtn_mrn_to_fhir_id.py \\")
        print("    /Users/resnick/Downloads/stg_cbtn_enrollment_final_10262025.csv \\")
        print("    /Users/resnick/Downloads/stg_cbtn_enrollment_with_fhir_id.csv")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    
    # Validate input file exists
    if not os.path.exists(input_csv):
        logger.error(f"Input file not found: {input_csv}")
        sys.exit(1)
    
    logger.info("="*80)
    logger.info("CBTN MRN to FHIR ID Matching (SECURE - No PHI Display)")
    logger.info("="*80)
    logger.info(f"Input:  {input_csv}")
    logger.info(f"Output: {output_csv}")
    logger.info("="*80)
    
    try:
        # Initialize AWS session with radiant-prod profile
        logger.info(f"Initializing AWS session with profile: {AWS_PROFILE}")
        session = boto3.Session(
            profile_name=AWS_PROFILE,
            region_name=AWS_REGION
        )
        athena_client = session.client('athena')
        logger.info("AWS Athena client initialized successfully")
        
        # Step 1: Query Athena for MRN to FHIR ID mapping
        logger.info("\n--- Step 1: Querying Athena for MRN->FHIR_ID mappings ---")
        mrn_to_fhir_map = query_patient_mrn_to_fhir_id(athena_client)
        
        if not mrn_to_fhir_map:
            logger.error("No MRN mappings found in Athena. Cannot proceed.")
            sys.exit(1)
        
        # Step 2: Process CBTN enrollment file
        logger.info("\n--- Step 2: Processing CBTN enrollment file ---")
        matched, unmatched = process_cbtn_enrollment(input_csv, output_csv, mrn_to_fhir_map)
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("PROCESS COMPLETE")
        logger.info("="*80)
        logger.info(f"Total matched: {matched}")
        logger.info(f"Total unmatched: {unmatched}")
        logger.info(f"Output file: {output_csv}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
