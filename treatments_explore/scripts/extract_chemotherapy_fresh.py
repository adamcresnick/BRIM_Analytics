"""
Fresh extraction of chemotherapy data from Athena v_chemo_medications view
to verify if combo-strings still appear in the current deployed view.
"""

import boto3
import pandas as pd
import time
from datetime import datetime

# AWS Configuration
AWS_REGION = 'us-east-1'
AWS_PROFILE = 'radiant-prod'
DATABASE = 'fhir_prd_db'
OUTPUT_LOCATION = 's3://brim-analytics-query-results/athena/'

def run_athena_query(query, session):
    """Execute Athena query and wait for completion"""
    athena = session.client('athena', region_name=AWS_REGION)
    
    print(f"Executing query...")
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': DATABASE},
        ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
    )
    
    query_id = response['QueryExecutionId']
    print(f"Query ID: {query_id}")
    
    # Wait for query to complete
    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        print(f"Query status: {status}...")
        time.sleep(5)
    
    if status != 'SUCCEEDED':
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        raise Exception(f"Query failed with status {status}: {reason}")
    
    print(f"Query completed successfully!")
    
    # Get results
    print("Fetching results...")
    results_response = athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
    
    # Get column names from metadata
    columns = [col['Name'] for col in results_response['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    
    # Get first page of data
    rows = []
    for row in results_response['ResultSet']['Rows'][1:]:  # Skip header
        rows.append([col.get('VarCharValue', None) for col in row['Data']])
    
    # Get remaining pages
    while 'NextToken' in results_response:
        results_response = athena.get_query_results(
            QueryExecutionId=query_id,
            NextToken=results_response['NextToken'],
            MaxResults=1000
        )
        for row in results_response['ResultSet']['Rows']:
            rows.append([col.get('VarCharValue', None) for col in row['Data']])
        print(f"Fetched {len(rows)} rows so far...")
    
    return pd.DataFrame(rows, columns=columns)

def main():
    print("="*80)
    print("FRESH CHEMOTHERAPY DATA EXTRACTION FROM ATHENA")
    print("="*80)
    print(f"Started at: {datetime.now()}")
    print()
    
    # Create boto3 session with profile
    session = boto3.Session(profile_name=AWS_PROFILE)
    
    # Query to extract all chemotherapy medications
    query = """
    SELECT 
        patient_fhir_id,
        chemo_preferred_name,
        chemo_therapeutic_normalized,
        chemo_drug_category,
        medication_start_date,
        medication_stop_date,
        medication_rxnorm_code,
        rxnorm_match_type,
        medication_name
    FROM fhir_prd_db.v_chemo_medications
    ORDER BY patient_fhir_id, medication_start_date
    """
    
    print("Query:")
    print(query)
    print()
    
    # Execute query
    df = run_athena_query(query, session)
    
    print(f"\nExtracted {len(df):,} records")
    print(f"Unique patients: {df['patient_fhir_id'].nunique():,}")
    
    # Check for combo-strings
    print("\n" + "="*80)
    print("CHECKING FOR COMBO-STRINGS")
    print("="*80)
    
    combo_mask = df['chemo_preferred_name'].str.contains(',|and', case=False, na=False)
    combo_df = df[combo_mask]
    
    print(f"\nRecords with combo-strings: {len(combo_df):,} ({100*len(combo_df)/len(df):.1f}%)")
    
    if len(combo_df) > 0:
        print("\n🚨 COMBO-STRINGS FOUND!")
        print("\nUnique combo-strings:")
        combo_strings = combo_df['chemo_preferred_name'].value_counts()
        for combo, count in combo_strings.head(15).items():
            patients = combo_df[combo_df['chemo_preferred_name'] == combo]['patient_fhir_id'].nunique()
            print(f"  [{count} records, {patients} patients] {combo}")
    else:
        print("\n✅ NO COMBO-STRINGS FOUND - View logic is working correctly")
    
    # Save to CSV
    output_file = 'data/chemotherapy_fresh_extraction.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✅ Saved to: {output_file}")
    print(f"\nCompleted at: {datetime.now()}")

if __name__ == '__main__':
    main()
