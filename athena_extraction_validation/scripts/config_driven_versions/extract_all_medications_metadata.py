#!/usr/bin/env python3
"""
Extract ALL Medications with Complete Metadata from Patient Configuration

This script extracts all medication records from patient_medications and joins with:
1. medication_request - ⭐ TEMPORAL FIELDS (validity_period_start/end for stop dates)
2. medication_request_note - Clinical notes with dose adjustments
3. medication_request_reason_code - Treatment indications
4. medication_request_based_on - Care plan linkages
5. medication_form_coding - Form codes via medication_id
6. medication_ingredient - Ingredient strengths via medication_id
7. care_plan - Protocol details
8. care_plan_category - ONCOLOGY TREATMENT classification
9. care_plan_addresses - Diagnosis linkage
10. care_plan_activity - Activity status

KEY ADDITIONS:
- ⭐ validity_period_end: Individual medication stop dates (not just care plan dates)
- ⭐ course_of_therapy_type_text: Treatment strategy (continuous/acute/seasonal)
- ⭐ dispense_request durations: Expected supply duration for each medication
- ⭐ prior_prescription_display: Tracks medication switches/changes

Output: medications.csv with 44 columns including complete temporal and clinical context
"""

import boto3
import pandas as pd
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def execute_athena_query(athena_client, query, description, database, output_location):
    """
    Execute Athena query and wait for completion
    
    Args:
        athena_client: Boto3 Athena client
        query: SQL query string
        description: Description for logging
        database: Database name
        output_location: S3 output location
        
    Returns:
        Query execution ID
    """
    logger.info(f"Executing query: {description}")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location}
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


def build_comprehensive_query(database, patient_id):
    """
    Build comprehensive query joining all 9 medication tables
    
    Args:
        database: Database name
        patient_id: Patient FHIR ID
        
    Returns:
        SQL query string
    """
    query = f"""
    WITH medication_notes AS (
        -- Aggregate multiple notes per medication
        SELECT 
            medication_request_id,
            LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_text) as note_text_aggregated
        FROM {database}.medication_request_note
        GROUP BY medication_request_id
    ),
    medication_reasons AS (
        -- Aggregate multiple reason codes per medication
        SELECT 
            medication_request_id,
            LISTAGG(reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
        FROM {database}.medication_request_reason_code
        GROUP BY medication_request_id
    ),
    medication_forms AS (
        -- Get form coding via medication_id
        SELECT 
            medication_id,
            LISTAGG(DISTINCT form_coding_code, ' | ') WITHIN GROUP (ORDER BY form_coding_code) as form_coding_codes,
            LISTAGG(DISTINCT form_coding_display, ' | ') WITHIN GROUP (ORDER BY form_coding_display) as form_coding_displays
        FROM {database}.medication_form_coding
        GROUP BY medication_id
    ),
    medication_ingredients AS (
        -- Get ingredient strengths via medication_id
        SELECT 
            medication_id,
            LISTAGG(DISTINCT CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit, ' | ') 
                WITHIN GROUP (ORDER BY CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit) as ingredient_strengths
        FROM {database}.medication_ingredient
        WHERE ingredient_strength_numerator_value IS NOT NULL
        GROUP BY medication_id
    ),
    care_plan_categories AS (
        -- Aggregate care plan categories (3 per plan)
        SELECT 
            care_plan_id,
            LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as categories_aggregated
        FROM {database}.care_plan_category
        GROUP BY care_plan_id
    ),
    care_plan_conditions AS (
        -- Aggregate care plan addresses (2 per plan)
        SELECT 
            care_plan_id,
            LISTAGG(DISTINCT addresses_display, ' | ') WITHIN GROUP (ORDER BY addresses_display) as addresses_aggregated
        FROM {database}.care_plan_addresses
        GROUP BY care_plan_id
    )
    
    SELECT 
        -- Patient info
        pm.patient_id as patient_fhir_id,
        
        -- ========================================
        -- ALL FIELDS FROM patient_medications VIEW (10 fields)
        -- ========================================
        pm.medication_request_id,
        pm.medication_id,
        pm.medication_name,
        pm.form_text as medication_form,
        pm.rx_norm_codes,
        pm.authored_on as medication_start_date,
        pm.requester_name,
        pm.status as medication_status,
        pm.encounter_display,
        
        -- ========================================
        -- TEMPORAL FIELDS FROM medication_request TABLE
        -- ========================================
        mr.dispense_request_validity_period_start as validity_period_start,
        mr.dispense_request_validity_period_end as validity_period_end,  -- ⭐ CRITICAL: Individual medication stop date
        
        -- ========================================
        -- STATUS & PRIORITY FROM medication_request TABLE
        -- ========================================
        mr.status_reason_text,
        mr.priority,
        mr.intent as medication_intent,
        mr.do_not_perform,
        
        -- ========================================
        -- TREATMENT STRATEGY CONTEXT FROM medication_request TABLE
        -- ========================================
        mr.course_of_therapy_type_text,  -- e.g., "continuous", "acute", "seasonal"
        mr.dispense_request_initial_fill_duration_value,
        mr.dispense_request_initial_fill_duration_unit,
        mr.dispense_request_expected_supply_duration_value,
        mr.dispense_request_expected_supply_duration_unit,
        mr.dispense_request_number_of_repeats_allowed,
        
        -- ========================================
        -- TREATMENT CHANGES FROM medication_request TABLE
        -- ========================================
        mr.substitution_allowed_boolean,
        mr.substitution_reason_text,
        mr.prior_prescription_display,  -- Tracks medication changes/switches
        
        -- ========================================
        -- AGGREGATED METADATA FROM CHILD TABLES
        -- ========================================
        -- Aggregated notes (dose adjustments, clinical trial status)
        mn.note_text_aggregated as clinical_notes,
        
        -- Aggregated reason codes (chemotherapy encounter, indications)
        mrr.reason_code_text_aggregated as reason_codes,
        
        -- Care plan linkage
        mrb.based_on_reference as care_plan_reference,
        mrb.based_on_display as care_plan_display,
        
        -- Form coding details (via medication_id)
        mf.form_coding_codes,
        mf.form_coding_displays,
        
        -- Ingredient details (via medication_id)
        mi.ingredient_strengths,
        
        -- ========================================
        -- CARE PLAN PROTOCOL DETAILS
        -- ========================================
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
        
    FROM {database}.patient_medications pm
    
    -- ⭐ NEW: Join to medication_request for temporal and clinical context fields
    LEFT JOIN {database}.medication_request mr
        ON pm.medication_request_id = mr.id
    
    -- Join medication request notes
    LEFT JOIN medication_notes mn
        ON pm.medication_request_id = mn.medication_request_id
    
    -- Join medication request reason codes
    LEFT JOIN medication_reasons mrr
        ON pm.medication_request_id = mrr.medication_request_id
    
    -- Join care plan linkage
    LEFT JOIN {database}.medication_request_based_on mrb
        ON pm.medication_request_id = mrb.medication_request_id
    
    -- Join form coding via medication_id (points to Medication resource)
    LEFT JOIN medication_forms mf
        ON pm.medication_id = mf.medication_id
    
    -- Join ingredient details via medication_id (points to Medication resource)
    LEFT JOIN medication_ingredients mi
        ON pm.medication_id = mi.medication_id
    
    -- Join care plan (protocol level)
    LEFT JOIN {database}.care_plan cp
        ON mrb.based_on_reference = cp.id
    
    -- Join care plan categories
    LEFT JOIN care_plan_categories cpc
        ON cp.id = cpc.care_plan_id
    
    -- Join care plan diagnoses
    LEFT JOIN care_plan_conditions cpcon
        ON cp.id = cpcon.care_plan_id
    
    -- Join care plan activity
    LEFT JOIN {database}.care_plan_activity cpa
        ON cp.id = cpa.care_plan_id
    
    WHERE pm.patient_id = '{patient_id}'
    
    ORDER BY pm.authored_on DESC, pm.medication_name
    """
    
    return query


def main():
    """Main execution function"""
    start_time = datetime.now()
    
    # Load patient configuration
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    # Set configuration variables
    PATIENT_ID = config['fhir_id']
    DATABASE = config['database']
    AWS_PROFILE = config['aws_profile']
    AWS_REGION = 'us-east-1'
    OUTPUT_LOCATION = config['s3_output']
    OUTPUT_DIR = Path(config['output_dir'])
    OUTPUT_FILE = OUTPUT_DIR / 'medications.csv'
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE MEDICATION EXTRACTION")
    logger.info("=" * 80)
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
        query = build_comprehensive_query(DATABASE, PATIENT_ID)
        
        logger.info("")
        logger.info("Query joins:")
        logger.info("  1. patient_medications (base table - 10 fields)")
        logger.info("  2. ⭐ medication_request (temporal + clinical context - 14 NEW fields)")
        logger.info("  3. medication_request_note (clinical notes)")
        logger.info("  4. medication_request_reason_code (indications)")
        logger.info("  5. medication_request_based_on (care plan links)")
        logger.info("  6. medication_form_coding (form details)")
        logger.info("  7. medication_ingredient (ingredient strengths)")
        logger.info("  8. care_plan (protocol details)")
        logger.info("  9. care_plan_category (ONCOLOGY TREATMENT)")
        logger.info(" 10. care_plan_addresses (diagnosis linkage)")
        logger.info(" 11. care_plan_activity (activity status)")
        logger.info("")
        
        # Execute query
        query_id = execute_athena_query(
            athena, 
            query, 
            "Extract all medications with complete metadata",
            DATABASE,
            OUTPUT_LOCATION
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
