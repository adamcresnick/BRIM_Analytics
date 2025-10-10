#!/usr/bin/env python3
"""
Extract ALL Medications with Complete Metadata for Patient C1277724

This script extracts all 1,001 medication records from patient_medications and joins with:
1. medication_request_note - Clinical notes with dose adjustments (104 records)
2. medication_request_reason_code - Treatment indications (335 records)  
3. medication_request_based_on - Care plan linkages (276 records)
4. medication_form_coding - Form codes via medication_id (666K rows)
5. medication_ingredient - Ingredient strengths via medication_id (771K rows)
6. care_plan - Protocol details (4 care plans)
7. care_plan_category - ONCOLOGY TREATMENT classification (12 records)
8. care_plan_addresses - Diagnosis linkage (8 records)
9. care_plan_activity - Activity status (4 records)

Output: ALL_MEDICATIONS_METADATA_C1277724.csv with 29+ columns
Expected: 1,001 medications with enriched metadata
"""

import boto3
import pandas as pd
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
AWS_REGION = 'us-east-1'
DATABASE = 'fhir_v2_prd_db'
OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Patient Configuration
PATIENT_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'  # C1277724
PATIENT_MRN = 'C1277724'

# Output Configuration
OUTPUT_DIR = 'staging_files'
OUTPUT_FILE = f'{OUTPUT_DIR}/ALL_MEDICATIONS_METADATA_{PATIENT_MRN}.csv'


def execute_athena_query(athena_client, query, description):
    """
    Execute Athena query and wait for completion
    
    Args:
        athena_client: Boto3 Athena client
        query: SQL query string
        description: Description for logging
        
    Returns:
        Query execution ID
    """
    logger.info(f"Executing query: {description}")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
        )
        
        query_id = response['QueryExecutionId']
        logger.info(f"Query ID: {query_id}")
        
        # Wait for query completion
        max_attempts = 60
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(2)
            attempt += 1
            
            result = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = result['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                logger.info(f"Query succeeded after {attempt * 2} seconds")
                return query_id
            elif status in ['FAILED', 'CANCELLED']:
                reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                logger.error(f"Query failed: {reason}")
                raise Exception(f"Query {status}: {reason}")
        
        raise Exception(f"Query timeout after {max_attempts * 2} seconds")
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise


def get_query_results(athena_client, query_id):
    """
    Retrieve query results and convert to DataFrame
    
    Args:
        athena_client: Boto3 Athena client
        query_id: Query execution ID
        
    Returns:
        Pandas DataFrame with results
    """
    logger.info(f"Retrieving results for query {query_id}")
    
    try:
        results = athena_client.get_query_results(QueryExecutionId=query_id)
        
        # Extract column names
        columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        
        # Extract data rows (skip header row)
        rows = []
        for row in results['ResultSet']['Rows'][1:]:
            rows.append([col.get('VarCharValue', '') for col in row['Data']])
        
        # Handle pagination if needed
        while 'NextToken' in results:
            results = athena_client.get_query_results(
                QueryExecutionId=query_id,
                NextToken=results['NextToken']
            )
            for row in results['ResultSet']['Rows']:
                rows.append([col.get('VarCharValue', '') for col in row['Data']])
        
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Retrieved {len(df)} rows with {len(columns)} columns")
        
        return df
        
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}")
        raise


def build_comprehensive_query():
    """
    Build comprehensive query joining all 9 medication tables
    
    Returns:
        SQL query string
    """
    query = f"""
    WITH medication_notes AS (
        -- Aggregate multiple notes per medication
        SELECT 
            medication_request_id,
            LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_text) as note_text_aggregated
        FROM {DATABASE}.medication_request_note
        GROUP BY medication_request_id
    ),
    medication_reasons AS (
        -- Aggregate multiple reason codes per medication
        SELECT 
            medication_request_id,
            LISTAGG(reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
        FROM {DATABASE}.medication_request_reason_code
        GROUP BY medication_request_id
    ),
    medication_forms AS (
        -- Get form coding via medication_id
        SELECT 
            medication_id,
            LISTAGG(DISTINCT form_coding_code, ' | ') WITHIN GROUP (ORDER BY form_coding_code) as form_coding_codes,
            LISTAGG(DISTINCT form_coding_display, ' | ') WITHIN GROUP (ORDER BY form_coding_display) as form_coding_displays
        FROM {DATABASE}.medication_form_coding
        GROUP BY medication_id
    ),
    medication_ingredients AS (
        -- Get ingredient strengths via medication_id
        SELECT 
            medication_id,
            LISTAGG(DISTINCT CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit, ' | ') 
                WITHIN GROUP (ORDER BY CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit) as ingredient_strengths
        FROM {DATABASE}.medication_ingredient
        WHERE ingredient_strength_numerator_value IS NOT NULL
        GROUP BY medication_id
    ),
    care_plan_categories AS (
        -- Aggregate care plan categories (3 per plan)
        SELECT 
            care_plan_id,
            LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as categories_aggregated
        FROM {DATABASE}.care_plan_category
        GROUP BY care_plan_id
    ),
    care_plan_conditions AS (
        -- Aggregate care plan addresses (2 per plan)
        SELECT 
            care_plan_id,
            LISTAGG(DISTINCT addresses_display, ' | ') WITHIN GROUP (ORDER BY addresses_display) as addresses_aggregated
        FROM {DATABASE}.care_plan_addresses
        GROUP BY care_plan_id
    )
    
    SELECT 
        -- Patient info
        '{PATIENT_MRN}' as patient_mrn,
        pm.patient_id as patient_fhir_id,
        
        -- Medication request basic info  
        pm.medication_request_id,
        pm.medication_id,
        pm.status as medication_status,
        pm.authored_on,
        
        -- Medication details (actual column names from patient_medications)
        pm.medication_name,
        pm.rx_norm_codes,
        pm.form_text as medication_form,
        
        -- Requester and encounter
        pm.requester_name,
        pm.encounter_display,
        
        -- Aggregated notes (dose adjustments, clinical trial status)
        mn.note_text_aggregated as clinical_notes,
        
        -- Aggregated reason codes (chemotherapy encounter, indications)
        mr.reason_code_text_aggregated as reason_codes,
        
        -- Care plan linkage
        mrb.based_on_reference as care_plan_reference,
        mrb.based_on_display as care_plan_display,
        
        -- Form coding details (via medication_id)
        mf.form_coding_codes,
        mf.form_coding_displays,
        
        -- Ingredient details (via medication_id)
        mi.ingredient_strengths,
        
        -- Care plan protocol details
        cp.id as care_plan_id,
        cp.title as care_plan_title,
        cp.status as care_plan_status,
        cp.intent as care_plan_intent,
        cp.period_start as care_plan_period_start,
        cp.period_end as care_plan_period_end,
        cp.created as care_plan_created,
        cp.author_display as care_plan_author,
        
        -- Care plan categories (ONCOLOGY TREATMENT classification)
        cpc.categories_aggregated as care_plan_categories,
        
        -- Care plan conditions (diagnosis linkage)
        cpcon.addresses_aggregated as care_plan_diagnoses,
        
        -- Care plan activity status
        cpa.activity_detail_status as care_plan_activity_status
        
    FROM {DATABASE}.patient_medications pm
    
    -- Join medication request notes
    LEFT JOIN medication_notes mn
        ON pm.medication_request_id = mn.medication_request_id
    
    -- Join medication request reason codes
    LEFT JOIN medication_reasons mr
        ON pm.medication_request_id = mr.medication_request_id
    
    -- Join care plan linkage
    LEFT JOIN {DATABASE}.medication_request_based_on mrb
        ON pm.medication_request_id = mrb.medication_request_id
    
    -- Join form coding via medication_id (points to Medication resource)
    LEFT JOIN medication_forms mf
        ON pm.medication_id = mf.medication_id
    
    -- Join ingredient details via medication_id (points to Medication resource)
    LEFT JOIN medication_ingredients mi
        ON pm.medication_id = mi.medication_id
    
    -- Join care plan (protocol level)
    LEFT JOIN {DATABASE}.care_plan cp
        ON mrb.based_on_reference = cp.id
    
    -- Join care plan categories
    LEFT JOIN care_plan_categories cpc
        ON cp.id = cpc.care_plan_id
    
    -- Join care plan diagnoses
    LEFT JOIN care_plan_conditions cpcon
        ON cp.id = cpcon.care_plan_id
    
    -- Join care plan activity
    LEFT JOIN {DATABASE}.care_plan_activity cpa
        ON cp.id = cpa.care_plan_id
    
    WHERE pm.patient_id = '{PATIENT_ID}'
    
    ORDER BY pm.authored_on DESC, pm.medication_name
    """
    
    return query


def main():
    """Main execution function"""
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE MEDICATION EXTRACTION - Patient C1277724")
    logger.info("=" * 80)
    logger.info(f"Patient MRN: {PATIENT_MRN}")
    logger.info(f"Patient FHIR ID: {PATIENT_ID}")
    logger.info(f"Output file: {OUTPUT_FILE}")
    logger.info("")
    
    try:
        # Initialize AWS session
        logger.info("Initializing AWS session...")
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        athena = session.client('athena')
        
        # Build and execute query
        logger.info("")
        logger.info("Building comprehensive query with 9 table joins...")
        query = build_comprehensive_query()
        
        logger.info("")
        logger.info("Query joins:")
        logger.info("  1. patient_medications (base table)")
        logger.info("  2. medication_request_note (clinical notes)")
        logger.info("  3. medication_request_reason_code (indications)")
        logger.info("  4. medication_request_based_on (care plan links)")
        logger.info("  5. medication_form_coding (form details)")
        logger.info("  6. medication_ingredient (ingredient strengths)")
        logger.info("  7. care_plan (protocol details)")
        logger.info("  8. care_plan_category (ONCOLOGY TREATMENT)")
        logger.info("  9. care_plan_addresses (diagnosis linkage)")
        logger.info(" 10. care_plan_activity (activity status)")
        logger.info("")
        
        # Execute query
        query_id = execute_athena_query(
            athena, 
            query, 
            "Extract all medications with complete metadata"
        )
        
        # Get results
        df = get_query_results(athena, query_id)
        
        # Log summary statistics
        logger.info("")
        logger.info("=" * 80)
        logger.info("EXTRACTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total medications extracted: {len(df)}")
        logger.info(f"Total columns: {len(df.columns)}")
        logger.info("")
        
        # Count medications with different metadata types
        logger.info("Metadata Coverage:")
        logger.info(f"  With clinical notes: {df['clinical_notes'].notna().sum()} ({df['clinical_notes'].notna().sum() / len(df) * 100:.1f}%)")
        logger.info(f"  With reason codes: {df['reason_codes'].notna().sum()} ({df['reason_codes'].notna().sum() / len(df) * 100:.1f}%)")
        logger.info(f"  With care plan linkage: {df['care_plan_id'].notna().sum()} ({df['care_plan_id'].notna().sum() / len(df) * 100:.1f}%)")
        logger.info(f"  With form coding: {df['form_coding_codes'].notna().sum()} ({df['form_coding_codes'].notna().sum() / len(df) * 100:.1f}%)")
        logger.info(f"  With ingredient strengths: {df['ingredient_strengths'].notna().sum()} ({df['ingredient_strengths'].notna().sum() / len(df) * 100:.1f}%)")
        logger.info("")
        
        # Care plan statistics
        care_plan_count = df['care_plan_id'].nunique()
        logger.info(f"Unique care plans: {care_plan_count}")
        if care_plan_count > 0:
            logger.info("Care plan distribution:")
            for title, count in df[df['care_plan_title'].notna()]['care_plan_title'].value_counts().items():
                logger.info(f"  '{title}': {count} medications")
        logger.info("")
        
        # Top medications
        logger.info("Top 10 medications by frequency:")
        for med, count in df['medication_name'].value_counts().head(10).items():
            logger.info(f"  {med}: {count} orders")
        logger.info("")
        
        # Create output directory if needed
        import os
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Save to CSV
        logger.info(f"Saving to {OUTPUT_FILE}...")
        df.to_csv(OUTPUT_FILE, index=False)
        logger.info(f"Successfully saved {len(df)} medications to CSV")
        
        # Log column list
        logger.info("")
        logger.info("Columns in output file:")
        for i, col in enumerate(df.columns, 1):
            logger.info(f"  {i:2d}. {col}")
        
        # Execution time
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"EXTRACTION COMPLETE - Duration: {duration:.1f} seconds")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("EXTRACTION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit(main())
