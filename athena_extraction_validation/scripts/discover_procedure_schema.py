#!/usr/bin/env python3
"""
Discover and document all procedure-related tables and their structures in FHIR database
Similar to encounters schema discovery
"""

import boto3
import pandas as pd
import time
from datetime import datetime
from pathlib import Path

class ProcedureSchemaDiscovery:
    def __init__(self, aws_profile: str, database: str):
        """Initialize AWS Athena connection"""
        try:
            self.session = boto3.Session(profile_name=aws_profile)
            self.athena = self.session.client('athena', region_name='us-east-1')
            self.database = database
            self.s3_output = 's3://aws-athena-query-results-343218191717-us-east-1/'
            
            print(f"\n{'='*80}")
            print(f"📊 PROCEDURE TABLES SCHEMA DISCOVERY")
            print(f"{'='*80}")
            print(f"Database: {self.database}")
            print(f"AWS Profile: {aws_profile}")
            print(f"{'='*80}\n")
        except Exception as e:
            print(f"❌ AWS Authentication Error: {str(e)}")
            print(f"\nPlease run: aws sso login --profile {aws_profile}")
            raise
    
    def execute_query(self, query: str, description: str) -> list:
        """Execute Athena query and return results"""
        print(f"🔍 {description}...", end=' ', flush=True)
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.s3_output}
            )
            
            query_id = response['QueryExecutionId']
            
            # Wait for query completion
            for _ in range(60):
                status = self.athena.get_query_execution(QueryExecutionId=query_id)
                state = status['QueryExecution']['Status']['State']
                
                if state == 'SUCCEEDED':
                    break
                elif state in ['FAILED', 'CANCELLED']:
                    reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    print(f"✗ Query {state}: {reason}")
                    return []
                
                time.sleep(2)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
            
            # Parse results
            data_rows = []
            if len(results['ResultSet']['Rows']) > 1:
                columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
                
                for row in results['ResultSet']['Rows'][1:]:
                    row_data = {}
                    for i, col in enumerate(columns):
                        value = row['Data'][i].get('VarCharValue', '') if i < len(row['Data']) else ''
                        row_data[col] = value
                    data_rows.append(row_data)
            
            print(f"✓ ({len(data_rows)} rows)")
            return data_rows
            
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            return []
    
    def discover_procedure_tables(self):
        """Find all procedure-related tables"""
        print(f"\n{'='*80}")
        print("📋 STEP 1: DISCOVERING PROCEDURE TABLES")
        print(f"{'='*80}\n")
        
        query = "SHOW TABLES IN fhir_v2_prd_db"
        
        all_tables = self.execute_query(query, "Fetching all tables")
        
        if not all_tables:
            print("❌ No tables found!")
            return []
        
        # Print first row to see column structure
        if all_tables:
            print(f"\n🔍 Column names: {list(all_tables[0].keys())}")
        
        # Filter for procedure-related tables (handle different column names)
        # Athena SHOW TABLES returns 'tab_name' or column 0 without name
        if all_tables and list(all_tables[0].keys()):
            col_name = list(all_tables[0].keys())[0]  # Get first column name
            procedure_tables = [t[col_name] for t in all_tables if 'procedure' in str(t[col_name]).lower()]
        else:
            procedure_tables = []
        
        procedure_tables.sort()
        
        print(f"\n📊 Found {len(procedure_tables)} procedure-related tables:\n")
        for i, table in enumerate(procedure_tables, 1):
            print(f"  {i:2}. {table}")
        
        return procedure_tables
    
    def get_table_structure(self, table_name: str):
        """Get column structure for a specific table"""
        print(f"\n{'='*80}")
        print(f"📋 ANALYZING TABLE: {table_name}")
        print(f"{'='*80}\n")
        
        query = f"SELECT * FROM {self.database}.{table_name} LIMIT 1"
        
        results = self.execute_query(query, f"Query {table_name} structure")
        
        if results:
            print(f"\n  Columns ({len(results[0])} total):")
            for i, col_name in enumerate(results[0].keys(), 1):
                print(f"    {i:2}. {col_name}")
            return results[0].keys()
        else:
            print(f"  ⚠️ No sample data available")
            return []
    
    def query_patient_procedures(self, patient_fhir_id: str):
        """Query all procedures for patient C1277724"""
        print(f"\n{'='*80}")
        print(f"📋 PATIENT PROCEDURES: {patient_fhir_id}")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            p.id as procedure_fhir_id,
            p.status,
            p.performed_date_time,
            p.performed_period_start,
            p.performed_period_end,
            p.code_text,
            p.subject_reference,
            p.encounter_reference,
            p.location_reference
        FROM {self.database}.procedure p
        WHERE p.subject_reference = '{patient_fhir_id}'
        ORDER BY p.performed_date_time
        """
        
        procedures = self.execute_query(query, "Query patient procedures")
        
        if procedures:
            df = pd.DataFrame(procedures)
            print(f"\n📊 Found {len(df)} procedures for patient")
            print(f"\n  Date range: {df['performed_date_time'].min()} to {df['performed_date_time'].max()}")
            print(f"\n  Status breakdown:")
            print(df['status'].value_counts().to_string())
            
            # Count procedures with dates
            with_dates = df['performed_date_time'].notna().sum()
            print(f"\n  Procedures with dates: {with_dates}/{len(df)} ({with_dates/len(df)*100:.1f}%)")
            
            return df
        else:
            print("  ⚠️ No procedures found")
            return pd.DataFrame()
    
    def query_procedure_codes(self, patient_fhir_id: str):
        """Query procedure codes and descriptions"""
        print(f"\n{'='*80}")
        print(f"📋 PROCEDURE CODES FOR PATIENT")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            pcc.procedure_id,
            pcc.code_coding_system,
            pcc.code_coding_code,
            pcc.code_coding_display,
            p.performed_date_time,
            p.status
        FROM {self.database}.procedure_code_coding pcc
        JOIN {self.database}.procedure p ON pcc.procedure_id = p.id
        WHERE p.subject_reference = '{patient_fhir_id}'
        ORDER BY p.performed_date_time
        """
        
        codes = self.execute_query(query, "Query procedure codes")
        
        if codes:
            df = pd.DataFrame(codes)
            print(f"\n📊 Found {len(df)} procedure code records")
            print(f"\n  Code system breakdown:")
            print(df['code_coding_system'].value_counts().to_string())
            print(f"\n  Top 10 procedures:")
            print(df['code_coding_display'].value_counts().head(10).to_string())
            
            # Identify surgical procedures
            surgical_keywords = ['craniotomy', 'craniectomy', 'resection', 'excision', 'biopsy', 'surgery']
            df['is_surgical'] = df['code_coding_display'].str.lower().str.contains('|'.join(surgical_keywords), na=False)
            surgical_count = df['is_surgical'].sum()
            print(f"\n  Surgical procedures: {surgical_count}/{len(df)} ({surgical_count/len(df)*100:.1f}%)")
            
            return df
        else:
            print("  ⚠️ No procedure codes found")
            return pd.DataFrame()

def main():
    """Main execution"""
    try:
        discovery = ProcedureSchemaDiscovery(
            aws_profile='343218191717_AWSAdministratorAccess',
            database='fhir_v2_prd_db'
        )
        
        # Step 1: Discover all procedure tables
        procedure_tables = discovery.discover_procedure_tables()
        
        if not procedure_tables:
            print("\n❌ No procedure tables found or AWS authentication failed")
            print("Please run: aws sso login --profile 343218191717_AWSAdministratorAccess")
            return
        
        # Step 2: Get structure of each table
        table_structures = {}
        for table in procedure_tables[:10]:  # First 10 tables
            columns = discovery.get_table_structure(table)
            if columns:
                table_structures[table] = list(columns)
        
        # Step 3: Query patient procedures
        patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        procedures_df = discovery.query_patient_procedures(patient_fhir_id)
        
        # Step 4: Query procedure codes
        codes_df = discovery.query_procedure_codes(patient_fhir_id)
        
        # Summary
        print(f"\n{'='*80}")
        print("✅ DISCOVERY COMPLETE")
        print(f"{'='*80}\n")
        print(f"📊 Summary:")
        print(f"  - {len(procedure_tables)} procedure tables found")
        print(f"  - {len(table_structures)} table structures analyzed")
        print(f"  - {len(procedures_df)} procedures found for patient")
        print(f"  - {len(codes_df)} procedure codes found")
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Run: aws sso login --profile 343218191717_AWSAdministratorAccess")
        print("2. Verify browser opens for authentication")
        print("3. Complete authentication in browser")
        print("4. Re-run this script")

if __name__ == '__main__':
    main()
