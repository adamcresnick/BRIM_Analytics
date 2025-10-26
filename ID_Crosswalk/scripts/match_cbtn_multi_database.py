#!/usr/bin/env python3
"""
Match CBTN Enrollment to FHIR IDs - Generic Multi-Database (SECURE)

This script uses a GENERIC matching strategy across ALL databases:

MATCHING STRATEGY (Applied to ALL databases):
1. Try MRN exact match FIRST
2. If MRN fails, fall back to DOB + Name matching:
   - DOB + Exact name match (first + last)
   - DOB + Last name + First initial
   - DOB + First name + Last initial
   - DOB only with single candidate (flagged for VERIFY)

SUPPORTED DATABASES:
- CHOP: fhir_v2_prd_db (default)
- UCSF: fhir_v2_ucsf_prd_db (default)
- Extensible to additional databases via command-line args

SECURITY:
- MRNs, DOBs, and names are NEVER printed to console
- All matching happens in memory
- Only match statistics are displayed

Usage:
    python3 match_cbtn_multi_database.py <input_csv> <output_csv> [OPTIONS]
    
Example:
    python3 match_cbtn_multi_database.py \
        /Users/resnick/Downloads/stg_cbtn_enrollment_final_10262025.csv \
        /Users/resnick/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv \
        --chop-database fhir_v2_prd_db \
        --ucsf-database fhir_v2_ucsf_prd_db
"""

import boto3
import pandas as pd
import time
import logging
import sys
import os
import argparse
from pathlib import Path
import hashlib
import re
from datetime import datetime

# Configure logging - NO PHI will be logged
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_PROFILE = 'radiant-prod'
AWS_REGION = 'us-east-1'
CHOP_DATABASE = 'fhir_v2_prd_db'
S3_OUTPUT_LOCATION = 's3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/athena-results/'


def execute_athena_query(athena_client, query, description, database):
    """Execute Athena query and wait for completion - SECURE"""
    logger.info(f"Executing query: {description}")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
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


def query_patient_data(athena_client, database, database_label):
    """
    Query patient database for both MRN and demographics (DOB + names) - SECURE
    
    Returns: (mrn_to_fhir_dict, demographics_df)
    """
    
    query = """
    SELECT 
        id as fhir_id,
        identifier_mrn,
        birth_date,
        given_name,
        family_name
    FROM patient
    WHERE id IS NOT NULL
    """
    
    query_execution_id = execute_athena_query(
        athena_client,
        query,
        f"Fetching patient data (MRN + demographics) from {database_label}",
        database
    )
    
    df = fetch_athena_results(athena_client, query_execution_id)
    
    if df.empty:
        logger.warning(f"No patient data found in {database_label}")
        return {}, pd.DataFrame()
    
    # Clean and normalize all fields
    df['fhir_id'] = df['fhir_id'].astype(str).str.strip()
    df['identifier_mrn'] = df['identifier_mrn'].astype(str).str.strip()
    df['birth_date'] = df['birth_date'].astype(str).str.strip()
    df['given_name'] = df['given_name'].astype(str).str.strip().str.lower()
    df['family_name'] = df['family_name'].astype(str).str.strip().str.lower()
    
    logger.info(f"Retrieved {len(df)} patient records from {database_label}")
    
    # Create MRN mapping (only for non-empty MRNs)
    mrn_df = df[(df['identifier_mrn'].notna()) & (df['identifier_mrn'] != '') & (df['identifier_mrn'] != 'nan')]
    mrn_to_fhir = dict(zip(mrn_df['identifier_mrn'], mrn_df['fhir_id']))
    
    if mrn_to_fhir:
        logger.info(f"  MRN mappings: {len(mrn_to_fhir)} records")
        lengths = mrn_df['identifier_mrn'].str.len()
        logger.info(f"  MRN length distribution:")
        for length, count in lengths.value_counts().sort_index().head(5).items():
            logger.info(f"    Length {length}: {count} records")
    
    # Create demographics dataframe (only for records with DOB)
    demo_df = df[(df['birth_date'].notna()) & (df['birth_date'] != '') & (df['birth_date'] != 'nan')]
    logger.info(f"  Demographics records with DOB: {len(demo_df)} records")
    if not demo_df.empty:
        logger.info(f"  Birth dates range: {demo_df['birth_date'].min()} to {demo_df['birth_date'].max()}")
    
    return mrn_to_fhir, demo_df





def normalize_name(name):
    """Normalize name for matching - SECURE"""
    if pd.isna(name) or name == '':
        return ''
    
    name = str(name).strip().lower()
    # Remove special characters, keep only alphanumeric
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def match_by_dob_and_name(cbtn_row, demo_df, match_stats, stat_prefix='', institution_valid=True):
    """
    Match a CBTN record to FHIR ID using birth_date + name validation - SECURE
    Generic function works for any database.
    
    Args:
        cbtn_row: CBTN enrollment record
        demo_df: Demographics dataframe from Athena
        match_stats: Statistics dictionary
        stat_prefix: Prefix for stats keys (e.g., 'chop_', 'ucsf_')
        institution_valid: If False, DOB-only matches will be rejected
    
    Returns: (fhir_id, match_type) or (None, None)
    """
    # Get CBTN data
    cbtn_dob = str(cbtn_row.get('dob', '')).strip()
    cbtn_first = normalize_name(cbtn_row.get('first_name', ''))
    cbtn_last = normalize_name(cbtn_row.get('last_name', ''))
    
    if not cbtn_dob or cbtn_dob == 'nan':
        match_stats[f'{stat_prefix}no_dob'] += 1
        return None, None
    
    # Find candidates with matching DOB
    candidates = demo_df[demo_df['birth_date'] == cbtn_dob]
    
    if len(candidates) == 0:
        match_stats[f'{stat_prefix}no_dob_match'] += 1
        return None, None
    
    # Match strategy 1: Exact first + last name match
    for idx, row in candidates.iterrows():
        db_first = normalize_name(row['given_name'])
        db_last = normalize_name(row['family_name'])
        
        if cbtn_first == db_first and cbtn_last == db_last:
            match_stats[f'{stat_prefix}dob_exact_name'] += 1
            return row['fhir_id'], f'{stat_prefix}dob_exact_name'
    
    # Match strategy 2: Last name match + first name initial
    if cbtn_first and cbtn_last:
        cbtn_first_initial = cbtn_first[0]
        
        for idx, row in candidates.iterrows():
            db_first = normalize_name(row['given_name'])
            db_last = normalize_name(row['family_name'])
            
            if cbtn_last == db_last and db_first and db_first[0] == cbtn_first_initial:
                match_stats[f'{stat_prefix}dob_last_initial'] += 1
                return row['fhir_id'], f'{stat_prefix}dob_last_initial'
    
    # Match strategy 3: First name match + last name initial
    if cbtn_first and cbtn_last:
        cbtn_last_initial = cbtn_last[0]
        
        for idx, row in candidates.iterrows():
            db_first = normalize_name(row['given_name'])
            db_last = normalize_name(row['family_name'])
            
            if cbtn_first == db_first and db_last and db_last[0] == cbtn_last_initial:
                match_stats[f'{stat_prefix}dob_first_initial'] += 1
                return row['fhir_id'], f'{stat_prefix}dob_first_initial'
    
    # If we have DOB match but no name match
    if len(candidates) == 1:
        # Single candidate - might be a name variation
        # BUT only accept if institution matches database
        if institution_valid:
            match_stats[f'{stat_prefix}dob_only_single'] += 1
            # Return with lower confidence flag
            return candidates.iloc[0]['fhir_id'], f'{stat_prefix}dob_only_single_VERIFY'
        else:
            # Institution doesn't match - reject this match
            match_stats[f'{stat_prefix}dob_only_rejected_institution'] += 1
            return None, None
    else:
        match_stats[f'{stat_prefix}dob_multiple_no_name'] += 1
        return None, None


def process_cbtn_enrollment_generic(input_csv, output_csv, db_configs):
    """
    Process CBTN enrollment file with generic multi-database matching - SECURE
    
    Args:
        db_configs: List of tuples (database_label, mrn_map, demo_df, institution_name)
                   institution_name is the exact organization_name value from CSV that should match
    """
    
    logger.info(f"Reading CBTN enrollment file...")
    
    # Read the CSV
    df = pd.read_csv(input_csv)
    logger.info(f"Loaded {len(df)} records from CBTN enrollment file")
    
    # Verify required columns
    required_cols = ['mrn', 'dob', 'first_name', 'last_name', 'organization_name']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Input CSV missing required columns: {missing_cols}")
    
    logger.info(f"Input columns: {list(df.columns)}")
    
    # Initialize new columns
    df['FHIR_ID'] = None
    df['match_strategy'] = None
    df['match_database'] = None
    
    # Match statistics - dynamically create keys
    stats = {
        'total_unmatched': 0,
        'mrn_total': 0,
        'dob_total': 0
    }
    
    # Add database-specific stat keys
    for db_label, _, _, _ in db_configs:
        stats[f'{db_label}_mrn_exact'] = 0
        stats[f'{db_label}_dob_exact_name'] = 0
        stats[f'{db_label}_dob_last_initial'] = 0
        stats[f'{db_label}_dob_first_initial'] = 0
        stats[f'{db_label}_dob_only_single'] = 0
        stats[f'{db_label}_dob_only_rejected_institution'] = 0
        stats[f'{db_label}_dob_multiple_no_name'] = 0
        stats[f'{db_label}_no_dob'] = 0
        stats[f'{db_label}_no_dob_match'] = 0
    
    logger.info("\nMatching records to FHIR IDs with generic strategy (secure - no PHI display)...")
    logger.info("Strategy: Try MRN first, fall back to DOB+Name for all databases")
    logger.info("Security: DOB-only matches ONLY accepted when institution matches database")
    
    for idx, row in df.iterrows():
        enrollment_mrn = str(row['mrn']).strip() if pd.notna(row['mrn']) else ''
        enrollment_org = str(row['organization_name']).strip() if pd.notna(row['organization_name']) else ''
        matched = False
        
        # Try each database in order
        for db_label, mrn_map, demo_df, expected_org in db_configs:
            if matched:
                break
            
            # Check if institution matches this database
            institution_matches = (enrollment_org == expected_org)
            
            # Strategy 1: Try MRN exact match first
            if enrollment_mrn and enrollment_mrn in mrn_map:
                df.at[idx, 'FHIR_ID'] = mrn_map[enrollment_mrn]
                df.at[idx, 'match_strategy'] = f'{db_label}_mrn_exact'
                df.at[idx, 'match_database'] = db_label
                stats[f'{db_label}_mrn_exact'] += 1
                stats['mrn_total'] += 1
                matched = True
                continue
            
            # Strategy 2: Fall back to DOB + name matching
            if not demo_df.empty:
                fhir_id, match_type = match_by_dob_and_name(
                    row, demo_df, stats, 
                    stat_prefix=f'{db_label}_',
                    institution_valid=institution_matches
                )
                
                if fhir_id:
                    df.at[idx, 'FHIR_ID'] = fhir_id
                    df.at[idx, 'match_strategy'] = match_type
                    df.at[idx, 'match_database'] = db_label
                    stats['dob_total'] += 1
                    matched = True
    
    # Calculate totals
    stats['total_unmatched'] = len(df[df['FHIR_ID'].isna()])
    total_matched = len(df[df['FHIR_ID'].notna()])
    
    # Log statistics (NO PHI data)
    logger.info(f"\n{'='*80}")
    logger.info("Matching Complete - Strategy Breakdown:")
    logger.info(f"{'='*80}")
    
    for db_label, _, _, _ in db_configs:
        logger.info(f"\n{db_label.upper()} Database:")
        logger.info(f"  MRN exact match: {stats[f'{db_label}_mrn_exact']} records")
        logger.info(f"  DOB + Exact name match: {stats[f'{db_label}_dob_exact_name']} records")
        logger.info(f"  DOB + Last name + First initial: {stats[f'{db_label}_dob_last_initial']} records")
        logger.info(f"  DOB + First name + Last initial: {stats[f'{db_label}_dob_first_initial']} records")
        logger.info(f"  DOB only (single candidate - VERIFY): {stats[f'{db_label}_dob_only_single']} records")
        logger.info(f"  DOB only REJECTED (institution mismatch): {stats[f'{db_label}_dob_only_rejected_institution']} records")
        logger.info(f"  DOB match but multiple candidates: {stats[f'{db_label}_dob_multiple_no_name']} records")
        logger.info(f"  No DOB in CBTN record: {stats[f'{db_label}_no_dob']} records")
        logger.info(f"  DOB not found in database: {stats[f'{db_label}_no_dob_match']} records")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"OVERALL TOTALS:")
    logger.info(f"  Total matched by MRN: {stats['mrn_total']} records")
    logger.info(f"  Total matched by DOB+Name: {stats['dob_total']} records")
    logger.info(f"  {'-'*76}")
    logger.info(f"  Total matched: {total_matched} records ({total_matched/len(df)*100:.1f}%)")
    logger.info(f"  Total unmatched: {stats['total_unmatched']} records ({stats['total_unmatched']/len(df)*100:.1f}%)")
    logger.info(f"{'='*80}")
    
    # Reorder columns
    cols = list(df.columns)
    if 'research_id' in cols and 'FHIR_ID' in cols:
        cols.remove('FHIR_ID')
        cols.remove('match_strategy')
        cols.remove('match_database')
        research_id_idx = cols.index('research_id')
        cols.insert(research_id_idx + 1, 'FHIR_ID')
        cols.insert(research_id_idx + 2, 'match_strategy')
        cols.insert(research_id_idx + 3, 'match_database')
        df = df[cols]
    
    # Write output
    logger.info(f"\nWriting output to: {output_csv}")
    df.to_csv(output_csv, index=False)
    logger.info(f"Output file created successfully")
    
    return stats


def main():
    """Main execution - SECURE (No PHI Display)"""
    
    parser = argparse.ArgumentParser(
        description='Match CBTN enrollment to FHIR IDs across multiple databases (SECURE - Generic MRN+DOB strategy)'
    )
    parser.add_argument('input_csv', help='Input CBTN enrollment CSV file')
    parser.add_argument('output_csv', help='Output CSV file with FHIR_ID column')
    parser.add_argument('--chop-database', default='fhir_v2_prd_db', 
                       help='CHOP Athena database name (default: fhir_v2_prd_db)')
    parser.add_argument('--ucsf-database', default='fhir_v2_ucsf_prd_db', 
                       help='UCSF Athena database name (default: fhir_v2_ucsf_prd_db)')
    parser.add_argument('--skip-ucsf', action='store_true',
                       help='Skip UCSF matching (CHOP only)')
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.exists(args.input_csv):
        logger.error(f"Input file not found: {args.input_csv}")
        sys.exit(1)
    
    logger.info("="*80)
    logger.info("CBTN Generic Multi-Database FHIR ID Matching (SECURE - No PHI Display)")
    logger.info("Strategy: Try MRN first, fall back to DOB+Name for ALL databases")
    logger.info("="*80)
    logger.info(f"Input:  {args.input_csv}")
    logger.info(f"Output: {args.output_csv}")
    logger.info(f"CHOP Database: {args.chop_database}")
    logger.info(f"UCSF Database: {args.ucsf_database}")
    logger.info(f"Skip UCSF: {args.skip_ucsf}")
    logger.info("="*80)
    
    try:
        # Initialize AWS session
        logger.info(f"\nInitializing AWS session with profile: {AWS_PROFILE}")
        session = boto3.Session(
            profile_name=AWS_PROFILE,
            region_name=AWS_REGION
        )
        athena_client = session.client('athena')
        logger.info("AWS Athena client initialized successfully")
        
        # Prepare database configurations
        db_configs = []
        
        # Step 1: Query CHOP database
        logger.info("\n" + "="*80)
        logger.info(f"Step 1: Querying CHOP database ({args.chop_database})")
        logger.info("="*80)
        chop_mrn_map, chop_demo_df = query_patient_data(athena_client, args.chop_database, 'chop')
        db_configs.append(('chop', chop_mrn_map, chop_demo_df, "The Children's Hospital of Philadelphia"))
        
        # Step 2: Query UCSF database (if not skipped)
        if not args.skip_ucsf:
            logger.info("\n" + "="*80)
            logger.info(f"Step 2: Querying UCSF database ({args.ucsf_database})")
            logger.info("="*80)
            try:
                ucsf_mrn_map, ucsf_demo_df = query_patient_data(athena_client, args.ucsf_database, 'ucsf')
                db_configs.append(('ucsf', ucsf_mrn_map, ucsf_demo_df, "UCSF Benioff Children's Hospital"))
            except Exception as e:
                logger.warning(f"Failed to query UCSF database: {str(e)}")
                logger.warning("Continuing with CHOP matching only...")
        else:
            logger.info("\nStep 2: Skipping UCSF database (--skip-ucsf flag set)")
        
        # Step 3: Process CBTN enrollment file with generic matching
        logger.info("\n" + "="*80)
        logger.info("Step 3: Processing CBTN enrollment file with generic matching")
        logger.info("="*80)
        stats = process_cbtn_enrollment_generic(
            args.input_csv, 
            args.output_csv, 
            db_configs
        )
        
        # Final summary
        total_matched = stats['mrn_total'] + stats['dob_total']
        
        logger.info("\n" + "="*80)
        logger.info("PROCESS COMPLETE")
        logger.info("="*80)
        logger.info(f"Total matched by MRN: {stats['mrn_total']}")
        logger.info(f"Total matched by DOB+Name: {stats['dob_total']}")
        logger.info(f"Total matched: {total_matched}")
        logger.info(f"Total unmatched: {stats['total_unmatched']}")
        logger.info(f"Output file: {args.output_csv}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
