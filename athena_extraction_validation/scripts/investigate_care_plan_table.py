"""
Investigate Care Plan Table and Treatment Information
====================================================
Checks if fhir_v2_prd_db.care_plan table exists and whether it contains
additional treatment information for the care plans referenced in medications.

Patient: C1277724 (e4BwD8ZYDBccepXcJ.Ilo3w3)
"""

import boto3
import pandas as pd
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = 'us-east-1'
DATABASE = 'fhir_v2_prd_db'
OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'
PATIENT_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

# Initialize Athena client
session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess', region_name=AWS_REGION)
athena_client = session.client('athena')

def execute_query(query, description):
    """Execute Athena query and return results"""
    logger.info(f"Executing: {description}")
    logger.info(f"Query: {query[:200]}...")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
        )
        
        query_execution_id = response['QueryExecutionId']
        
        # Wait for query to complete
        max_attempts = 30
        attempt = 0
        while attempt < max_attempts:
            result = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = result['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                logger.error(f"Query failed: {reason}")
                return None
            
            time.sleep(2)
            attempt += 1
        
        # Get results
        results = athena_client.get_query_results(QueryExecutionId=query_execution_id)
        
        # Parse results
        rows = results['ResultSet']['Rows']
        if len(rows) <= 1:
            logger.warning(f"No data returned for {description}")
            return None
        
        # Extract headers and data
        headers = [col['VarCharValue'] for col in rows[0]['Data']]
        data = []
        for row in rows[1:]:
            data.append([col.get('VarCharValue', '') for col in row['Data']])
        
        df = pd.DataFrame(data, columns=headers)
        logger.info(f"Retrieved {len(df)} rows")
        return df
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return None

def main():
    """Main execution flow"""
    
    # Step 1: Check if care_plan table exists
    logger.info("\n" + "="*80)
    logger.info("STEP 1: Check if fhir_v2_prd_db.care_plan table exists")
    logger.info("="*80)
    
    check_table_query = "SHOW TABLES IN fhir_v2_prd_db LIKE 'care_plan'"
    
    tables_df = execute_query(check_table_query, "Check for care_plan table")
    
    if tables_df is None or tables_df.empty:
        logger.warning("✗ care_plan table NOT FOUND in fhir_v2_prd_db")
        logger.info("Checking for similar tables...")
        
        similar_query = "SHOW TABLES IN fhir_v2_prd_db LIKE 'care%'"
        similar_df = execute_query(similar_query, "Check for care* tables")
        if similar_df is not None and not similar_df.empty:
            logger.info(f"Found {len(similar_df)} tables starting with 'care':")
            print(similar_df.to_string(index=False))
        
        logger.info("\n" + "="*80)
        logger.info("CONCLUSION: Cannot query care_plan table - it doesn't exist")
        logger.info("="*80)
        logger.info("The medication_request_based_on.based_on_display field is the")
        logger.info("only treatment protocol information available. No need to join")
        logger.info("to a separate care_plan table.")
        return
    
    logger.info("✓ care_plan table EXISTS!")
    print(tables_df.to_string(index=False))
    
    # Step 2: Get care_plan table schema
    logger.info("\n" + "="*80)
    logger.info("STEP 2: Get care_plan table schema")
    logger.info("="*80)
    
    schema_query = "DESCRIBE fhir_v2_prd_db.care_plan"
    schema_df = execute_query(schema_query, "Get care_plan schema")
    if schema_df is not None and not schema_df.empty:
        logger.info("\ncare_plan table columns:")
        print(schema_df.to_string(index=False))
    
    # Step 3: Extract care plan IDs from medication_request_based_on
    logger.info("\n" + "="*80)
    logger.info("STEP 3: Extract care plan IDs from medication_request_based_on")
    logger.info("="*80)
    
    get_care_plan_ids_query = f"""
    SELECT DISTINCT
        mrb.based_on_reference,
        mrb.based_on_display
    FROM fhir_v2_prd_db.patient_medications pm
    JOIN fhir_v2_prd_db.medication_request_based_on mrb
        ON pm.medication_request_id = mrb.medication_request_id
    WHERE pm.patient_id = '{PATIENT_ID}'
        AND mrb.based_on_reference IS NOT NULL
        AND mrb.based_on_reference LIKE 'CarePlan/%'
    LIMIT 20
    """
    
    care_plan_refs_df = execute_query(get_care_plan_ids_query, "Get care plan references from medications")
    if care_plan_refs_df is not None and not care_plan_refs_df.empty:
        logger.info(f"\nFound {len(care_plan_refs_df)} care plan reference(s):")
        print(care_plan_refs_df.to_string(index=False))
        
        # Extract care plan IDs (remove 'CarePlan/' prefix)
        care_plan_ids = [ref.replace('CarePlan/', '') for ref in care_plan_refs_df['based_on_reference'].tolist()]
        logger.info(f"\nCare Plan IDs: {care_plan_ids}")
    else:
        logger.warning("No care plan references found in medications!")
        return
    
    # Step 4: Query care_plan table for these IDs
    logger.info("\n" + "="*80)
    logger.info("STEP 4: Query care_plan table for treatment details")
    logger.info("="*80)
    
    # Build query for specific care plan IDs
    care_plan_ids_str = "','".join(care_plan_ids)
    
    care_plan_query = f"""
    SELECT *
    FROM fhir_v2_prd_db.care_plan
    WHERE care_plan_id IN ('{care_plan_ids_str}')
    """
    
    care_plans_df = execute_query(care_plan_query, "Get care plan details")
    if care_plans_df is not None and not care_plans_df.empty:
        logger.info(f"\n*** FOUND {len(care_plans_df)} care plan(s) with additional details! ***")
        print(care_plans_df.to_string(index=False))
        
        # List all columns with non-null values
        logger.info("\nColumns with data:")
        for col in care_plans_df.columns:
            non_null = care_plans_df[col].notna().sum()
            if non_null > 0:
                logger.info(f"  - {col}: {non_null}/{len(care_plans_df)} records have data")
        
        logger.info("\n" + "="*80)
        logger.info("RECOMMENDATION: Include care_plan table in extraction")
        logger.info("="*80)
        logger.info("The care_plan table contains additional treatment information")
        logger.info("that should be joined to medications for comprehensive metadata.")
    else:
        logger.warning("No care plans found in care_plan table for these IDs")
        logger.info("\nPossible reasons:")
        logger.info("1. Care plan IDs in based_on_reference don't match care_plan.care_plan_id")
        logger.info("2. Care plans are in a different table")
        logger.info("3. Display name is the only information available")
        
        # Try querying care_plan table for this patient directly
        logger.info("\n" + "="*80)
        logger.info("STEP 5: Try querying care_plan by patient")
        logger.info("="*80)
        
        patient_care_plans_query = f"""
        SELECT *
        FROM fhir_v2_prd_db.care_plan
        WHERE subject_reference = 'Patient/{PATIENT_ID}'
        LIMIT 10
        """
        
        patient_plans_df = execute_query(patient_care_plans_query, "Get patient's care plans")
        if patient_plans_df is not None and not patient_plans_df.empty:
            logger.info(f"\n*** Found {len(patient_plans_df)} care plan(s) for patient! ***")
            print(patient_plans_df.to_string(index=False))
        else:
            logger.warning("No care plans found for patient in care_plan table")

if __name__ == "__main__":
    main()
