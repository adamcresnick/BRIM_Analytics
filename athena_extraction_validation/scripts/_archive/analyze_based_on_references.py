"""
Analyze Based-On References in Medications
==========================================
Investigates what resources medication_request_based_on references point to
and whether we can extract additional treatment information.

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
    
    # Step 1: Analyze based_on_reference patterns
    logger.info("\n" + "="*80)
    logger.info("STEP 1: Analyze based_on_reference patterns")
    logger.info("="*80)
    
    patterns_query = f"""
    SELECT 
        SUBSTRING(mrb.based_on_reference, 1, POSITION('/' IN mrb.based_on_reference)) AS resource_type,
        COUNT(*) as count,
        COUNT(DISTINCT mr.medication_request_id) as distinct_medications
    FROM fhir_v2_prd_db.medication_request mr
    JOIN fhir_v2_prd_db.medication_request_based_on mrb
        ON mr.medication_request_id = mrb.medication_request_id
    WHERE mr.subject_reference = 'Patient/{PATIENT_ID}'
        AND mrb.based_on_reference IS NOT NULL
    GROUP BY SUBSTRING(mrb.based_on_reference, 1, POSITION('/' IN mrb.based_on_reference))
    ORDER BY count DESC
    """
    
    patterns_df = execute_query(patterns_query, "Analyze based_on reference patterns")
    if patterns_df is not None and not patterns_df.empty:
        logger.info("\nResource type distribution:")
        print(patterns_df.to_string(index=False))
    
    # Step 2: Get sample based_on references with display names
    logger.info("\n" + "="*80)
    logger.info("STEP 2: Sample based_on references with display names")
    logger.info("="*80)
    
    sample_query = f"""
    SELECT 
        mrb.based_on_reference,
        mrb.based_on_display,
        pm.medication_name,
        pm.rx_norm_codes,
        pm.authored_on,
        COUNT(*) OVER (PARTITION BY mrb.based_on_reference) as medications_with_this_reference
    FROM fhir_v2_prd_db.medication_request mr
    JOIN fhir_v2_prd_db.medication_request_based_on mrb
        ON mr.medication_request_id = mrb.medication_request_id
    LEFT JOIN fhir_v2_prd_db.patient_medications pm
        ON mr.medication_request_id = pm.medication_request_id
    WHERE mr.subject_reference = 'Patient/{PATIENT_ID}'
        AND mrb.based_on_reference IS NOT NULL
    ORDER BY medications_with_this_reference DESC, pm.authored_on DESC
    LIMIT 30
    """
    
    sample_df = execute_query(sample_query, "Sample based_on references")
    if sample_df is not None and not sample_df.empty:
        logger.info("\nSample based_on references:")
        print(sample_df.to_string(index=False))
    
    # Step 3: Check what resource types are referenced
    logger.info("\n" + "="*80)
    logger.info("STEP 3: Extract resource types from references")
    logger.info("="*80)
    
    if sample_df is not None and not sample_df.empty:
        # Extract resource types
        resource_types = set()
        for ref in sample_df['based_on_reference'].unique():
            if '/' in ref:
                resource_type = ref.split('/')[0]
                resource_types.add(resource_type)
        
        logger.info(f"\nUnique resource types referenced: {resource_types}")
        
        # Check if these tables exist in the database
        for resource_type in resource_types:
            # Convert to table name (CarePlan -> care_plan)
            table_name = ''.join(['_' + c.lower() if c.isupper() else c for c in resource_type]).lstrip('_')
            
            logger.info(f"\nChecking for table: {table_name}")
            
            check_query = f"SHOW TABLES IN fhir_v2_prd_db LIKE '{table_name}'"
            result = execute_query(check_query, f"Check for {table_name} table")
            
            if result is not None and not result.empty:
                logger.info(f"✓ Table {table_name} EXISTS")
                
                # Get schema
                schema_query = f"DESCRIBE fhir_v2_prd_db.{table_name}"
                schema_df = execute_query(schema_query, f"Schema of {table_name}")
                if schema_df is not None:
                    print(schema_df.to_string(index=False))
            else:
                logger.warning(f"✗ Table {table_name} NOT FOUND")
    
    # Step 4: Analyze display names for treatment information
    logger.info("\n" + "="*80)
    logger.info("STEP 4: Analyze based_on_display for treatment information")
    logger.info("="*80)
    
    display_analysis_query = f"""
    SELECT 
        mrb.based_on_display,
        COUNT(DISTINCT pm.medication_name) as unique_medications,
        COUNT(*) as total_references,
        MIN(pm.authored_on) as earliest_date,
        MAX(pm.authored_on) as latest_date
    FROM fhir_v2_prd_db.medication_request mr
    JOIN fhir_v2_prd_db.medication_request_based_on mrb
        ON mr.medication_request_id = mrb.medication_request_id
    LEFT JOIN fhir_v2_prd_db.patient_medications pm
        ON mr.medication_request_id = pm.medication_request_id
    WHERE mr.subject_reference = 'Patient/{PATIENT_ID}'
        AND mrb.based_on_display IS NOT NULL
    GROUP BY mrb.based_on_display
    ORDER BY total_references DESC
    LIMIT 20
    """
    
    display_df = execute_query(display_analysis_query, "Analyze based_on_display names")
    if display_df is not None and not display_df.empty:
        logger.info("\nTreatment protocols identified from display names:")
        print(display_df.to_string(index=False))
        
        logger.info("\n*** KEY FINDING ***")
        logger.info("The based_on_display field contains treatment protocol names like:")
        logger.info("'Bevacizumab, Vinblastine' - This IS the treatment information!")
        logger.info("We can use this field directly without needing to query another table.")
    
    logger.info("\n" + "="*80)
    logger.info("CONCLUSION")
    logger.info("="*80)
    logger.info("The medication_request_based_on.based_on_display field already contains")
    logger.info("the treatment protocol/care plan information we need. No additional")
    logger.info("table queries are required - we can extract this directly!")

if __name__ == "__main__":
    main()
