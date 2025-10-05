#!/usr/bin/env python3
"""
Query actual imaging data from Athena for patient C1277724
Replaces estimated data with real imaging procedures from fhir_v2_prd_db
"""

import os
import sys
import boto3
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from pyathena import connect
from pyathena.pandas.cursor import PandasCursor

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()

def main():
    """Query imaging data from Athena materialized views."""
    
    # Configuration
    patient_fhir_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    patient_mrn = "C1277724"
    aws_profile = '343218191717_AWSAdministratorAccess'
    athena_db = 'fhir_v2_prd_db'
    s3_staging = 's3://aws-athena-query-results-343218191717-us-east-1/'
    
    print(f"\n🔍 Querying Imaging Data for Patient {patient_mrn} ({patient_fhir_id})")
    print(f"📝 Using AWS Profile: {aws_profile}")
    print("=" * 80)
    
    # Initialize Athena connection with explicit profile
    try:
        # Force credential refresh by creating new session
        import botocore.session
        botocore_session = botocore.session.get_session()
        botocore_session.get_credentials()
        
        conn = connect(
            s3_staging_dir=s3_staging,
            region_name='us-east-1',
            cursor_class=PandasCursor,
            profile_name=aws_profile,
            work_group='primary'
        )
        print("✅ Athena connection established")
    except Exception as e:
        print(f"❌ Failed to connect to Athena: {e}")
        return
    
    # Query radiology_imaging_mri table (MRI Brain specific)
    print(f"\n📊 Querying radiology_imaging_mri table...")
    
    mri_query = f"""
    SELECT 
        patient_id,
        imaging_procedure,
        result_datetime,
        result_diagnostic_report_id
    FROM {athena_db}.radiology_imaging_mri
    WHERE patient_id = '{patient_fhir_id}'
    ORDER BY result_datetime
    """
    
    try:
        cursor = conn.cursor()
        cursor.execute(mri_query)
        mri_df = cursor.as_pandas()
        
        if not mri_df.empty:
            print(f"✅ Found {len(mri_df)} MRI studies")
            print("\nMRI Studies:")
            print(mri_df.to_string(index=False))
            
            # Create patient_imaging.csv
            output_df = pd.DataFrame({
                'patient_fhir_id': mri_df['patient_id'],
                'imaging_type': mri_df['imaging_procedure'],
                'imaging_date': pd.to_datetime(mri_df['result_datetime']).dt.strftime('%Y-%m-%d'),
                'diagnostic_report_id': mri_df['result_diagnostic_report_id']
            })
            
            output_path = Path(__file__).parent.parent / 'pilot_output' / 'brim_csvs_iteration_3c_phase3a_v2' / 'patient_imaging.csv'
            output_df.to_csv(output_path, index=False)
            print(f"\n✅ Created {output_path}")
            print(f"   {len(output_df)} imaging studies")
            
        else:
            print("⚠️  No MRI studies found in radiology_imaging_mri table")
            
    except Exception as e:
        print(f"❌ MRI query failed: {e}")
    
    # Also try general radiology_imaging table
    print(f"\n📊 Querying general radiology_imaging table...")
    
    general_query = f"""
    SELECT 
        patient_id,
        imaging_procedure,
        result_datetime,
        result_diagnostic_report_id
    FROM {athena_db}.radiology_imaging
    WHERE patient_id = '{patient_fhir_id}'
        AND (
            imaging_procedure LIKE '%MRI%Brain%'
            OR imaging_procedure LIKE '%Brain%MRI%'
            OR imaging_procedure LIKE '%MRI%Head%'
        )
    ORDER BY result_datetime
    """
    
    try:
        cursor = conn.cursor()
        cursor.execute(general_query)
        general_df = cursor.as_pandas()
        
        if not general_df.empty:
            print(f"✅ Found {len(general_df)} imaging studies in general table")
            print("\nGeneral Imaging Studies:")
            print(general_df.to_string(index=False))
        else:
            print("⚠️  No imaging studies found in general radiology_imaging table")
            
    except Exception as e:
        print(f"❌ General imaging query failed: {e}")
    
    # Close connection
    conn.close()
    print("\n" + "=" * 80)
    print("✅ Query complete")

if __name__ == '__main__':
    main()
