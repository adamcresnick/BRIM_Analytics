#!/usr/bin/env python3
"""
Match CBTN Enrollment MRNs to FHIR IDs with Leading Zero Normalization (SECURE)

This script improves upon the basic matching by:
1. Trying multiple MRN formats with leading zero padding (7, 8, 9, 10 digits)
2. Handling non-numeric MRN prefixes (e.g., ME, PI)
3. Case-insensitive matching
4. Comprehensive match reporting by strategy

SECURITY:
- MRNs are NEVER printed to console
- MRNs are NEVER logged
- All matching happens in memory
- Only match statistics are displayed

Usage:
    python3 match_cbtn_mrn_to_fhir_id_with_padding.py <input_csv> <output_csv>
    
Example:
    python3 match_cbtn_mrn_to_fhir_id_with_padding.py \
        /Users/resnick/Downloads/stg_cbtn_enrollment_final_10262025.csv \
        /Users/resnick/Downloads/stg_cbtn_enrollment_with_fhir_id_padded.csv
"""

import boto3
import pandas as pd
import time
import logging
import sys
import os
from pathlib import Path
import hashlib
import re

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
    
    # Create multiple mapping dictionaries for different formats
    if not df.empty:
        # Strip whitespace and ensure strings
        df['identifier_mrn'] = df['identifier_mrn'].astype(str).str.strip()
        df['fhir_id'] = df['fhir_id'].astype(str).str.strip()
        
        # Create primary dict (exact match)
        mrn_to_fhir = dict(zip(df['identifier_mrn'], df['fhir_id']))
        
        # Create case-insensitive dict
        mrn_to_fhir_lower = {k.lower(): v for k, v in mrn_to_fhir.items()}
        
        # Analyze MRN patterns in Athena
        lengths = df['identifier_mrn'].str.len()
        logger.info(f"Athena MRN length distribution:")
        for length, count in lengths.value_counts().sort_index().head(10).items():
            logger.info(f"  Length {length}: {count} records")
        
        numeric_count = df['identifier_mrn'].str.match(r'^\d+$').sum()
        logger.info(f"  Purely numeric MRNs in Athena: {numeric_count}")
        
        logger.info(f"Created mapping dictionary with {len(mrn_to_fhir)} MRN->FHIR_ID pairs")
        return mrn_to_fhir, mrn_to_fhir_lower, df
    else:
        logger.warning("No MRN mappings found in Athena")
        return {}, {}, pd.DataFrame()


def normalize_mrn_variants(mrn_str):
    """
    Generate multiple MRN format variants for matching - SECURE
    
    Returns list of variants to try:
    1. Original value (exact match)
    2. Stripped/cleaned value
    3. Uppercase version
    4. If numeric: padded to 7, 8, 9, 10 digits with leading zeros
    """
    variants = []
    
    if pd.isna(mrn_str) or mrn_str == '':
        return variants
    
    mrn_str = str(mrn_str).strip()
    
    # Add original
    variants.append(mrn_str)
    
    # Add uppercase
    if mrn_str.upper() != mrn_str:
        variants.append(mrn_str.upper())
    
    # Add lowercase
    if mrn_str.lower() != mrn_str:
        variants.append(mrn_str.lower())
    
    # If purely numeric, try padding
    if re.match(r'^\d+$', mrn_str):
        current_len = len(mrn_str)
        # Try padding to common MRN lengths (7, 8, 9, 10 digits)
        for target_len in [7, 8, 9, 10]:
            if current_len < target_len:
                padded = mrn_str.zfill(target_len)
                variants.append(padded)
    
    return variants


def process_cbtn_enrollment(input_csv, output_csv, mrn_to_fhir_map, mrn_to_fhir_lower, athena_df):
    """Process CBTN enrollment file with multi-strategy matching - SECURE"""
    
    logger.info(f"Reading CBTN enrollment file...")
    
    # Read the CSV
    df = pd.read_csv(input_csv)
    logger.info(f"Loaded {len(df)} records from CBTN enrollment file")
    
    # Verify mrn column exists
    if 'mrn' not in df.columns:
        raise ValueError("Input CSV does not contain 'mrn' column")
    
    logger.info(f"Input columns: {list(df.columns)}")
    
    # Initialize columns
    df['FHIR_ID'] = None
    df['match_strategy'] = None
    
    # Match statistics
    stats = {
        'exact': 0,
        'case_insensitive': 0,
        'padded_7': 0,
        'padded_8': 0,
        'padded_9': 0,
        'padded_10': 0,
        'unmatched': 0
    }
    
    logger.info("Matching MRNs to FHIR IDs with multi-strategy approach (secure - no MRN display)...")
    
    for idx, row in df.iterrows():
        mrn_original = str(row['mrn']).strip() if pd.notna(row['mrn']) else ''
        
        if not mrn_original:
            stats['unmatched'] += 1
            continue
        
        matched = False
        
        # Strategy 1: Exact match
        if mrn_original in mrn_to_fhir_map:
            df.at[idx, 'FHIR_ID'] = mrn_to_fhir_map[mrn_original]
            df.at[idx, 'match_strategy'] = 'exact'
            stats['exact'] += 1
            matched = True
        
        # Strategy 2: Case-insensitive match
        elif not matched and mrn_original.lower() in mrn_to_fhir_lower:
            df.at[idx, 'FHIR_ID'] = mrn_to_fhir_lower[mrn_original.lower()]
            df.at[idx, 'match_strategy'] = 'case_insensitive'
            stats['case_insensitive'] += 1
            matched = True
        
        # Strategy 3: Try padding variants
        if not matched and re.match(r'^\d+$', mrn_original):
            current_len = len(mrn_original)
            
            for target_len in [7, 8, 9, 10]:
                if current_len < target_len:
                    padded = mrn_original.zfill(target_len)
                    
                    if padded in mrn_to_fhir_map:
                        df.at[idx, 'FHIR_ID'] = mrn_to_fhir_map[padded]
                        df.at[idx, 'match_strategy'] = f'padded_{target_len}'
                        stats[f'padded_{target_len}'] += 1
                        matched = True
                        break
        
        if not matched:
            stats['unmatched'] += 1
    
    # Calculate totals
    total_matched = sum([v for k, v in stats.items() if k != 'unmatched'])
    
    # Log statistics (NO MRN data)
    logger.info(f"\nMatching complete - Strategy breakdown:")
    logger.info(f"  Exact match: {stats['exact']} records")
    logger.info(f"  Case-insensitive: {stats['case_insensitive']} records")
    logger.info(f"  Padded to 7 digits: {stats['padded_7']} records")
    logger.info(f"  Padded to 8 digits: {stats['padded_8']} records")
    logger.info(f"  Padded to 9 digits: {stats['padded_9']} records")
    logger.info(f"  Padded to 10 digits: {stats['padded_10']} records")
    logger.info(f"  -" * 40)
    logger.info(f"  Total matched: {total_matched} records")
    logger.info(f"  Unmatched: {stats['unmatched']} records")
    logger.info(f"  Match rate: {total_matched / len(df) * 100:.1f}%")
    
    # Improvement calculation
    logger.info(f"\nPadding strategies added: {stats['padded_7'] + stats['padded_8'] + stats['padded_9'] + stats['padded_10']} matches")
    
    # Reorder columns to put FHIR_ID after research_id
    cols = list(df.columns)
    if 'research_id' in cols and 'FHIR_ID' in cols:
        cols.remove('FHIR_ID')
        cols.remove('match_strategy')
        research_id_idx = cols.index('research_id')
        cols.insert(research_id_idx + 1, 'FHIR_ID')
        cols.insert(research_id_idx + 2, 'match_strategy')
        df = df[cols]
    
    # Write output
    logger.info(f"\nWriting output to: {output_csv}")
    df.to_csv(output_csv, index=False)
    logger.info(f"Output file created successfully")
    
    return stats


def main():
    """Main execution - SECURE (No MRN Display)"""
    
    if len(sys.argv) != 3:
        print("Usage: python3 match_cbtn_mrn_to_fhir_id_with_padding.py <input_csv> <output_csv>")
        print("\nExample:")
        print("  python3 match_cbtn_mrn_to_fhir_id_with_padding.py \\")
        print("    /Users/resnick/Downloads/stg_cbtn_enrollment_final_10262025.csv \\")
        print("    /Users/resnick/Downloads/stg_cbtn_enrollment_with_fhir_id_padded.csv")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    
    # Validate input file exists
    if not os.path.exists(input_csv):
        logger.error(f"Input file not found: {input_csv}")
        sys.exit(1)
    
    logger.info("="*80)
    logger.info("CBTN MRN to FHIR ID Matching with Leading Zero Normalization")
    logger.info("(SECURE - No PHI Display)")
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
        mrn_to_fhir_map, mrn_to_fhir_lower, athena_df = query_patient_mrn_to_fhir_id(athena_client)
        
        if not mrn_to_fhir_map:
            logger.error("No MRN mappings found in Athena. Cannot proceed.")
            sys.exit(1)
        
        # Step 2: Process CBTN enrollment file with multi-strategy matching
        logger.info("\n--- Step 2: Processing CBTN enrollment file ---")
        stats = process_cbtn_enrollment(input_csv, output_csv, mrn_to_fhir_map, mrn_to_fhir_lower, athena_df)
        
        # Summary
        total_matched = sum([v for k, v in stats.items() if k != 'unmatched'])
        logger.info("\n" + "="*80)
        logger.info("PROCESS COMPLETE")
        logger.info("="*80)
        logger.info(f"Total matched: {total_matched}")
        logger.info(f"Total unmatched: {stats['unmatched']}")
        logger.info(f"Output file: {output_csv}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
