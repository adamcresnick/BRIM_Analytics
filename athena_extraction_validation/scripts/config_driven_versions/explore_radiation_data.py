#!/usr/bin/env python3
"""
Explore Athena database for radiation treatment and consultation data

This script searches for:
1. Procedures with radiation-related CPT/HCPCS codes
2. ServiceRequests for radiation oncology
3. CarePlans mentioning radiation
4. Encounters with radiation oncology departments
5. Medications related to radiation (radiosensitizers)
6. DocumentReferences mentioning radiation
"""

import boto3
import pandas as pd
import json
from pathlib import Path

def execute_athena_query(athena_client, database, s3_output, query, description):
    """Execute Athena query and return results"""
    print(f"\n{'='*80}")
    print(f"🔍 {description}")
    print(f"{'='*80}")
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': s3_output}
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait for completion
        import time
        for _ in range(60):
            status_response = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = status_response['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                error = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                print(f"❌ Query failed: {error}")
                return pd.DataFrame()
            time.sleep(1)
        
        # Get results
        results = athena_client.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
        
        if not results['ResultSet']['Rows']:
            print(f"⚠️  No results found")
            return pd.DataFrame()
        
        # Parse results
        columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
        data = []
        for row in results['ResultSet']['Rows'][1:]:
            data.append([col.get('VarCharValue', '') for col in row['Data']])
        
        df = pd.DataFrame(data, columns=columns)
        print(f"✅ Found {len(df)} records")
        
        return df
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return pd.DataFrame()


def main():
    # Load config
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    patient_id = config['fhir_id']
    database = config['database']
    aws_profile = config['aws_profile']
    s3_output = config['s3_output']
    
    print("\n" + "="*80)
    print("RADIATION TREATMENT DATA EXPLORATION")
    print("="*80)
    print(f"Patient FHIR ID: {patient_id}")
    print(f"Database: {database}")
    
    # Initialize AWS
    session = boto3.Session(profile_name=aws_profile)
    athena = session.client('athena', region_name='us-east-1')
    
    # 1. Search Procedures for radiation-related CPT codes
    query_1 = f"""
    SELECT 
        p.id as procedure_id,
        p.code_text as procedure_name,
        p.code_coding_code as cpt_code,
        p.performed_date_time,
        p.category_text,
        p.status
    FROM procedure p
    WHERE p.patient_id = '{patient_id}'
    AND (
        LOWER(p.code_text) LIKE '%radiation%'
        OR LOWER(p.code_text) LIKE '%radiotherapy%'
        OR LOWER(p.code_text) LIKE '%brachytherapy%'
        OR LOWER(p.code_text) LIKE '%radiosurgery%'
        OR LOWER(p.category_text) LIKE '%radiation%'
        OR LOWER(p.category_text) LIKE '%oncology%'
    )
    ORDER BY p.performed_date_time DESC
    """
    
    df_procedures = execute_athena_query(
        athena, database, s3_output, query_1,
        "Strategy 1: Radiation-related Procedures"
    )
    
    if not df_procedures.empty:
        print("\nFound procedures:")
        print(df_procedures[['procedure_name', 'cpt_code', 'performed_date_time']].to_string())
    
    # 2. Search ServiceRequest for radiation oncology referrals
    query_2 = f"""
    SELECT 
        sr.id as service_request_id,
        sr.code_text as service_name,
        sr.intent,
        sr.status,
        sr.authored_on,
        sr.performer_type_text as specialty,
        sr.category_text
    FROM service_request sr
    WHERE sr.patient_id = '{patient_id}'
    AND (
        LOWER(sr.code_text) LIKE '%radiation%'
        OR LOWER(sr.performer_type_text) LIKE '%radiation%'
        OR LOWER(sr.performer_type_text) LIKE '%oncology%'
        OR LOWER(sr.category_text) LIKE '%radiation%'
    )
    ORDER BY sr.authored_on DESC
    """
    
    df_service_requests = execute_athena_query(
        athena, database, s3_output, query_2,
        "Strategy 2: Radiation Oncology Service Requests"
    )
    
    if not df_service_requests.empty:
        print("\nFound service requests:")
        print(df_service_requests[['service_name', 'specialty', 'authored_on']].to_string())
    
    # 3. Check Encounters for radiation oncology visits
    query_3 = f"""
    SELECT 
        e.id as encounter_id,
        e.class_code,
        e.type_text,
        e.service_type_text,
        e.period_start,
        e.period_end
    FROM encounter e
    WHERE e.patient_id = '{patient_id}'
    AND (
        LOWER(e.type_text) LIKE '%radiation%'
        OR LOWER(e.service_type_text) LIKE '%radiation%'
        OR LOWER(e.service_type_text) LIKE '%oncology%'
    )
    ORDER BY e.period_start DESC
    """
    
    df_encounters = execute_athena_query(
        athena, database, s3_output, query_3,
        "Strategy 3: Radiation Oncology Encounters"
    )
    
    if not df_encounters.empty:
        print("\nFound encounters:")
        print(df_encounters[['type_text', 'service_type_text', 'period_start']].to_string())
    
    # 4. Check CarePlans for radiation treatment
    query_4 = f"""
    SELECT 
        cp.id as care_plan_id,
        cp.title,
        cp.description,
        cp.intent,
        cp.status,
        cp.period_start,
        cp.period_end,
        cp.category_text
    FROM care_plan cp
    WHERE cp.patient_id = '{patient_id}'
    AND (
        LOWER(cp.title) LIKE '%radiation%'
        OR LOWER(cp.description) LIKE '%radiation%'
        OR LOWER(cp.category_text) LIKE '%radiation%'
    )
    ORDER BY cp.period_start DESC
    """
    
    df_care_plans = execute_athena_query(
        athena, database, s3_output, query_4,
        "Strategy 4: Radiation Treatment Care Plans"
    )
    
    if not df_care_plans.empty:
        print("\nFound care plans:")
        print(df_care_plans[['title', 'period_start', 'status']].to_string())
    
    # 5. Check all available tables
    query_5 = """
    SHOW TABLES
    """
    
    df_tables = execute_athena_query(
        athena, database, s3_output, query_5,
        "Strategy 5: Available Tables in Database"
    )
    
    if not df_tables.empty:
        radiation_tables = df_tables[df_tables.iloc[:, 0].str.contains('radiation|oncology|therapy', case=False, na=False)]
        if not radiation_tables.empty:
            print("\nRadiation/oncology-related tables:")
            print(radiation_tables.to_string(index=False))
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Radiation Procedures: {len(df_procedures)}")
    print(f"Radiation Service Requests: {len(df_service_requests)}")
    print(f"Radiation Encounters: {len(df_encounters)}")
    print(f"Radiation Care Plans: {len(df_care_plans)}")
    print(f"\nTotal radiation-related records: {len(df_procedures) + len(df_service_requests) + len(df_encounters) + len(df_care_plans)}")
    
    if len(df_procedures) + len(df_service_requests) + len(df_encounters) + len(df_care_plans) == 0:
        print("\n⚠️  No radiation treatment data found for this patient")
        print("\nNext steps:")
        print("1. Check DocumentReferences for radiation oncology consultation notes")
        print("2. Look for CPT codes: 77xxx (radiation therapy), 79xxx (radioisotope therapy)")
        print("3. Check Observations for treatment planning measurements")
        print("4. Review medications for radiosensitizers (cisplatin, temozolomide)")


if __name__ == '__main__':
    main()
