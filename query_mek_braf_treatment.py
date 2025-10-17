#!/usr/bin/env python3
"""
Query Medications for MEK and BRAF Inhibitor Treatment
Checks if specific patients have been treated with targeted therapies

Usage:
    python query_mek_braf_treatment.py
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
DATABASE = 'fhir_prd_db'  # Change to fhir_v2_prd_db if needed
OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Target patients
PATIENT_IDS = [
    'eMs2NnGm924T3P.-WlJNbGSyTbwC0mH.Uy9GHFKhgUq83',
    'e8jvrF5IozRmfwySdwoRVwz02sJVXqC2b0q7DVAmDDcQ3',
    'ePCcDRUsjiniYE3.EIVUejNqzdu1ovhebX.tYYcTI25w3'
]


def execute_athena_query(athena_client, query, description):
    """Execute Athena query and wait for completion"""
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
    """Retrieve query results and convert to DataFrame"""
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


def build_mek_braf_query():
    """Build query to check for MEK and BRAF inhibitor treatment"""
    
    patient_list = "', '".join(PATIENT_IDS)
    
    query = f"""
WITH target_patients AS (
    SELECT '{PATIENT_IDS[0]}' as patient_id
    UNION ALL
    SELECT '{PATIENT_IDS[1]}'
    UNION ALL
    SELECT '{PATIENT_IDS[2]}'
),
mek_braf_medications AS (
    SELECT
        pm.patient_id,
        pm.medication_name,
        pm.rx_norm_codes,
        pm.authored_on as medication_start_date,
        pm.status as medication_status,
        mr.dispense_request_validity_period_start,
        mr.dispense_request_validity_period_end,
        mr.course_of_therapy_type_text,
        CASE
            -- MEK Inhibitors
            WHEN LOWER(pm.medication_name) LIKE '%trametinib%' THEN 'MEK Inhibitor - Trametinib (Mekinist)'
            WHEN LOWER(pm.medication_name) LIKE '%mekinist%' THEN 'MEK Inhibitor - Trametinib (Mekinist)'
            WHEN LOWER(pm.medication_name) LIKE '%cobimetinib%' THEN 'MEK Inhibitor - Cobimetinib (Cotellic)'
            WHEN LOWER(pm.medication_name) LIKE '%cotellic%' THEN 'MEK Inhibitor - Cobimetinib (Cotellic)'
            WHEN LOWER(pm.medication_name) LIKE '%binimetinib%' THEN 'MEK Inhibitor - Binimetinib (Mektovi)'
            WHEN LOWER(pm.medication_name) LIKE '%mektovi%' THEN 'MEK Inhibitor - Binimetinib (Mektovi)'
            WHEN LOWER(pm.medication_name) LIKE '%selumetinib%' THEN 'MEK Inhibitor - Selumetinib (Koselugo)'
            WHEN LOWER(pm.medication_name) LIKE '%koselugo%' THEN 'MEK Inhibitor - Selumetinib (Koselugo)'
            -- BRAF Inhibitors
            WHEN LOWER(pm.medication_name) LIKE '%dabrafenib%' THEN 'BRAF Inhibitor - Dabrafenib (Tafinlar)'
            WHEN LOWER(pm.medication_name) LIKE '%tafinlar%' THEN 'BRAF Inhibitor - Dabrafenib (Tafinlar)'
            WHEN LOWER(pm.medication_name) LIKE '%vemurafenib%' THEN 'BRAF Inhibitor - Vemurafenib (Zelboraf)'
            WHEN LOWER(pm.medication_name) LIKE '%zelboraf%' THEN 'BRAF Inhibitor - Vemurafenib (Zelboraf)'
            WHEN LOWER(pm.medication_name) LIKE '%encorafenib%' THEN 'BRAF Inhibitor - Encorafenib (Braftovi)'
            WHEN LOWER(pm.medication_name) LIKE '%braftovi%' THEN 'BRAF Inhibitor - Encorafenib (Braftovi)'
            ELSE 'Unknown'
        END as inhibitor_class
    FROM {DATABASE}.patient_medications pm
    LEFT JOIN {DATABASE}.medication_request mr ON pm.medication_request_id = mr.id
    WHERE pm.patient_id IN (SELECT patient_id FROM target_patients)
        AND (
            -- MEK Inhibitors
            LOWER(pm.medication_name) LIKE '%trametinib%'
            OR LOWER(pm.medication_name) LIKE '%mekinist%'
            OR LOWER(pm.medication_name) LIKE '%cobimetinib%'
            OR LOWER(pm.medication_name) LIKE '%cotellic%'
            OR LOWER(pm.medication_name) LIKE '%binimetinib%'
            OR LOWER(pm.medication_name) LIKE '%mektovi%'
            OR LOWER(pm.medication_name) LIKE '%selumetinib%'
            OR LOWER(pm.medication_name) LIKE '%koselugo%'
            -- BRAF Inhibitors
            OR LOWER(pm.medication_name) LIKE '%dabrafenib%'
            OR LOWER(pm.medication_name) LIKE '%tafinlar%'
            OR LOWER(pm.medication_name) LIKE '%vemurafenib%'
            OR LOWER(pm.medication_name) LIKE '%zelboraf%'
            OR LOWER(pm.medication_name) LIKE '%encorafenib%'
            OR LOWER(pm.medication_name) LIKE '%braftovi%'
        )
)
SELECT
    tp.patient_id,
    CASE 
        WHEN COUNT(mbm.patient_id) > 0 THEN 'YES - Treated with MEK/BRAF Inhibitors'
        ELSE 'NO - No MEK/BRAF Inhibitors Found'
    END as treatment_status,
    COUNT(mbm.patient_id) as num_prescriptions,
    LISTAGG(DISTINCT mbm.inhibitor_class, '; ') WITHIN GROUP (ORDER BY mbm.inhibitor_class) as inhibitor_types,
    LISTAGG(DISTINCT mbm.medication_name, '; ') WITHIN GROUP (ORDER BY mbm.medication_name) as medication_names,
    MIN(mbm.medication_start_date) as first_prescription_date,
    MAX(mbm.medication_start_date) as last_prescription_date
FROM target_patients tp
LEFT JOIN mek_braf_medications mbm ON tp.patient_id = mbm.patient_id
GROUP BY tp.patient_id
ORDER BY tp.patient_id
"""
    
    return query


def build_detailed_query():
    """Build query to get detailed medication records"""
    
    patient_list = "', '".join(PATIENT_IDS)
    
    query = f"""
SELECT
    pm.patient_id,
    pm.medication_name,
    pm.rx_norm_codes,
    pm.authored_on as medication_start_date,
    pm.status as medication_status,
    mr.dispense_request_validity_period_start,
    mr.dispense_request_validity_period_end,
    mr.course_of_therapy_type_text,
    CASE
        -- MEK Inhibitors
        WHEN LOWER(pm.medication_name) LIKE '%trametinib%' THEN 'MEK Inhibitor - Trametinib (Mekinist)'
        WHEN LOWER(pm.medication_name) LIKE '%mekinist%' THEN 'MEK Inhibitor - Trametinib (Mekinist)'
        WHEN LOWER(pm.medication_name) LIKE '%cobimetinib%' THEN 'MEK Inhibitor - Cobimetinib (Cotellic)'
        WHEN LOWER(pm.medication_name) LIKE '%cotellic%' THEN 'MEK Inhibitor - Cobimetinib (Cotellic)'
        WHEN LOWER(pm.medication_name) LIKE '%binimetinib%' THEN 'MEK Inhibitor - Binimetinib (Mektovi)'
        WHEN LOWER(pm.medication_name) LIKE '%mektovi%' THEN 'MEK Inhibitor - Binimetinib (Mektovi)'
        WHEN LOWER(pm.medication_name) LIKE '%selumetinib%' THEN 'MEK Inhibitor - Selumetinib (Koselugo)'
        WHEN LOWER(pm.medication_name) LIKE '%koselugo%' THEN 'MEK Inhibitor - Selumetinib (Koselugo)'
        -- BRAF Inhibitors
        WHEN LOWER(pm.medication_name) LIKE '%dabrafenib%' THEN 'BRAF Inhibitor - Dabrafenib (Tafinlar)'
        WHEN LOWER(pm.medication_name) LIKE '%tafinlar%' THEN 'BRAF Inhibitor - Dabrafenib (Tafinlar)'
        WHEN LOWER(pm.medication_name) LIKE '%vemurafenib%' THEN 'BRAF Inhibitor - Vemurafenib (Zelboraf)'
        WHEN LOWER(pm.medication_name) LIKE '%zelboraf%' THEN 'BRAF Inhibitor - Vemurafenib (Zelboraf)'
        WHEN LOWER(pm.medication_name) LIKE '%encorafenib%' THEN 'BRAF Inhibitor - Encorafenib (Braftovi)'
        WHEN LOWER(pm.medication_name) LIKE '%braftovi%' THEN 'BRAF Inhibitor - Encorafenib (Braftovi)'
        ELSE 'Unknown'
    END as inhibitor_class
FROM {DATABASE}.patient_medications pm
LEFT JOIN {DATABASE}.medication_request mr ON pm.medication_request_id = mr.id
WHERE pm.patient_id IN ('{patient_list}')
    AND (
        -- MEK Inhibitors
        LOWER(pm.medication_name) LIKE '%trametinib%'
        OR LOWER(pm.medication_name) LIKE '%mekinist%'
        OR LOWER(pm.medication_name) LIKE '%cobimetinib%'
        OR LOWER(pm.medication_name) LIKE '%cotellic%'
        OR LOWER(pm.medication_name) LIKE '%binimetinib%'
        OR LOWER(pm.medication_name) LIKE '%mektovi%'
        OR LOWER(pm.medication_name) LIKE '%selumetinib%'
        OR LOWER(pm.medication_name) LIKE '%koselugo%'
        -- BRAF Inhibitors
        OR LOWER(pm.medication_name) LIKE '%dabrafenib%'
        OR LOWER(pm.medication_name) LIKE '%tafinlar%'
        OR LOWER(pm.medication_name) LIKE '%vemurafenib%'
        OR LOWER(pm.medication_name) LIKE '%zelboraf%'
        OR LOWER(pm.medication_name) LIKE '%encorafenib%'
        OR LOWER(pm.medication_name) LIKE '%braftovi%'
    )
ORDER BY pm.patient_id, pm.authored_on
"""
    
    return query


def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("MEK/BRAF Inhibitor Treatment Query")
    logger.info("=" * 80)
    logger.info(f"Database: {DATABASE}")
    logger.info(f"Number of patients: {len(PATIENT_IDS)}")
    logger.info("")
    
    # Initialize AWS session
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        athena_client = session.client('athena')
        logger.info("✓ AWS session initialized")
    except Exception as e:
        logger.error(f"Failed to initialize AWS session: {str(e)}")
        logger.error("Make sure you're logged in with: aws sso login --profile 343218191717_AWSAdministratorAccess")
        return
    
    # Execute summary query
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY: Checking for MEK/BRAF Inhibitor Treatment")
    logger.info("=" * 80)
    
    summary_query = build_mek_braf_query()
    query_id = execute_athena_query(athena_client, summary_query, "MEK/BRAF Treatment Summary")
    summary_df = get_query_results(athena_client, query_id)
    
    print("\n" + "=" * 80)
    print("RESULTS: MEK/BRAF Inhibitor Treatment Status")
    print("=" * 80)
    print(summary_df.to_string(index=False))
    
    # Check if any patients have treatments
    has_treatments = (summary_df['num_prescriptions'].astype(int) > 0).any()
    
    if has_treatments:
        # Execute detailed query
        logger.info("\n" + "=" * 80)
        logger.info("DETAILED: Getting medication records")
        logger.info("=" * 80)
        
        detailed_query = build_detailed_query()
        query_id = execute_athena_query(athena_client, detailed_query, "Detailed Medication Records")
        detailed_df = get_query_results(athena_client, query_id)
        
        print("\n" + "=" * 80)
        print("DETAILED MEDICATION RECORDS")
        print("=" * 80)
        print(detailed_df.to_string(index=False))
        
        # Save results
        output_file = f'mek_braf_treatment_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        detailed_df.to_csv(output_file, index=False)
        logger.info(f"\n✓ Detailed results saved to: {output_file}")
    else:
        logger.info("\nNo MEK or BRAF inhibitor treatments found for any of the patients.")
    
    logger.info("\n" + "=" * 80)
    logger.info("Query Complete")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
