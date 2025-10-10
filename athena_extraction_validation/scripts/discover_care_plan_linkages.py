"""
Discover Care Plan Linkages from Medications
===========================================
Investigates care plan IDs referenced in medication_request_based_on table
and queries care_plan table for treatment details.

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
    logger.info(f"Query: {query}")
    
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
    logger.info("STEP 1: Check if care_plan table exists")
    logger.info("="*80)
    
    check_table_query = """
    SHOW TABLES IN fhir_v2_prd_db LIKE 'care_plan%'
    """
    
    tables_df = execute_query(check_table_query, "List care_plan tables")
    if tables_df is not None and not tables_df.empty:
        logger.info(f"\nFound {len(tables_df)} care_plan table(s):")
        print(tables_df.to_string(index=False))
    else:
        logger.warning("No care_plan tables found!")
        return
    
    # Step 2: Get sample of care plan IDs from medication_request_based_on
    logger.info("\n" + "="*80)
    logger.info("STEP 2: Extract care plan IDs from medication_request_based_on")
    logger.info("="*80)
    
    get_care_plan_ids_query = f"""
    SELECT DISTINCT
        mrb.based_on_reference,
        mrb.based_on_display,
        COUNT(*) as medication_count
    FROM fhir_v2_prd_db.medication_request mr
    JOIN fhir_v2_prd_db.medication_request_based_on mrb
        ON mr.medication_request_id = mrb.medication_request_id
    WHERE mr.subject_reference = 'Patient/{PATIENT_ID}'
        AND mrb.based_on_reference IS NOT NULL
        AND mrb.based_on_reference LIKE 'CarePlan/%'
    GROUP BY mrb.based_on_reference, mrb.based_on_display
    ORDER BY medication_count DESC
    LIMIT 20
    """
    
    care_plan_ids_df = execute_query(get_care_plan_ids_query, "Get care plan IDs from medications")
    if care_plan_ids_df is not None and not care_plan_ids_df.empty:
        logger.info(f"\nFound {len(care_plan_ids_df)} care plan references:")
        print(care_plan_ids_df.to_string(index=False))
        
        # Extract care plan IDs (remove 'CarePlan/' prefix)
        care_plan_ids = [ref.replace('CarePlan/', '') for ref in care_plan_ids_df['based_on_reference'].tolist()]
        logger.info(f"\nCare Plan IDs to query: {care_plan_ids[:5]}")  # Show first 5
    else:
        logger.warning("No care plan references found in medications!")
        return
    
    # Step 3: Check schema of care_plan table
    logger.info("\n" + "="*80)
    logger.info("STEP 3: Check care_plan table schema")
    logger.info("="*80)
    
    describe_query = "DESCRIBE fhir_v2_prd_db.care_plan"
    schema_df = execute_query(describe_query, "Describe care_plan table")
    if schema_df is not None and not schema_df.empty:
        logger.info("\ncare_plan table columns:")
        print(schema_df.to_string(index=False))
    
    # Step 4: Query care_plan table for patient's care plans
    logger.info("\n" + "="*80)
    logger.info("STEP 4: Query care_plan table for patient's care plans")
    logger.info("="*80)
    
    # First try with patient_id
    care_plan_query = f"""
    SELECT 
        care_plan_id,
        title,
        description,
        status,
        intent,
        category,
        subject_reference,
        period_start,
        period_end,
        created,
        author_display
    FROM fhir_v2_prd_db.care_plan
    WHERE subject_reference = 'Patient/{PATIENT_ID}'
    LIMIT 100
    """
    
    care_plans_df = execute_query(care_plan_query, "Get patient's care plans")
    if care_plans_df is not None and not care_plans_df.empty:
        logger.info(f"\nFound {len(care_plans_df)} care plan(s) for patient:")
        print(care_plans_df.to_string(index=False))
        
        # Step 5: Get detailed care plan information for specific IDs
        logger.info("\n" + "="*80)
        logger.info("STEP 5: Get detailed care plan information")
        logger.info("="*80)
        
        # Query specific care plans that medications reference
        care_plan_ids_str = "','".join(care_plan_ids[:5])  # First 5 IDs
        detail_query = f"""
        SELECT 
            cp.care_plan_id,
            cp.title,
            cp.description,
            cp.status,
            cp.intent,
            cp.period_start,
            cp.period_end,
            cp.created,
            cp.author_display
        FROM fhir_v2_prd_db.care_plan cp
        WHERE cp.care_plan_id IN ('{care_plan_ids_str}')
        """
        
        detail_df = execute_query(detail_query, "Get detailed care plan info")
        if detail_df is not None and not detail_df.empty:
            logger.info(f"\nDetailed care plan information:")
            print(detail_df.to_string(index=False))
        else:
            logger.warning("Could not retrieve detailed care plan information")
    else:
        logger.warning("No care plans found for patient!")
    
    # Step 6: Check for care_plan activity/detail tables
    logger.info("\n" + "="*80)
    logger.info("STEP 6: Check for care_plan activity/detail tables")
    logger.info("="*80)
    
    activity_tables_query = """
    SHOW TABLES IN fhir_v2_prd_db LIKE 'care_plan_%'
    """
    
    activity_tables_df = execute_query(activity_tables_query, "List care_plan related tables")
    if activity_tables_df is not None and not activity_tables_df.empty:
        logger.info(f"\nFound {len(activity_tables_df)} care_plan related table(s):")
        print(activity_tables_df.to_string(index=False))
        
        # Check if there's a care_plan_activity table
        for table_name in activity_tables_df.iloc[:, 0]:  # First column has table names
            if 'activity' in table_name.lower():
                logger.info(f"\n*** Found activity table: {table_name} ***")
                
                # Describe it
                describe_activity_query = f"DESCRIBE fhir_v2_prd_db.{table_name}"
                activity_schema_df = execute_query(describe_activity_query, f"Describe {table_name}")
                if activity_schema_df is not None:
                    print(activity_schema_df.to_string(index=False))
                
                # Get sample data
                sample_activity_query = f"""
                SELECT *
                FROM fhir_v2_prd_db.{table_name}
                LIMIT 10
                """
                activity_sample_df = execute_query(sample_activity_query, f"Sample data from {table_name}")
                if activity_sample_df is not None:
                    print(activity_sample_df.to_string(index=False))
    
    logger.info("\n" + "="*80)
    logger.info("DISCOVERY COMPLETE")
    logger.info("="*80)

if __name__ == "__main__":
    main()
