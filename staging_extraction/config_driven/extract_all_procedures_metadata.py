#!/usr/bin/env python3
"""
Extract ALL procedures with comprehensive metadata from patient configuration

Creates a staging file with:
- procedure_fhir_id (for linkage to other resources)
- Date and timing information
- Age at procedure
- Procedure types and categories
- CPT/HCPCS codes
- Body sites (anatomical locations)
- Performers (surgeons, providers)
- Reasons for procedures
- Related encounters and reports

This is a STAGING file - we extract everything first, then filter later.
"""

import boto3
import pandas as pd
import time
import json
from datetime import datetime
from pathlib import Path

class AllProceduresExtractor:
    def __init__(self, aws_profile: str, database: str, patient_config: dict):
        """Initialize AWS Athena connection and patient information"""
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.s3_output = 's3://aws-athena-query-results-343218191717-us-east-1/'
        
        # Load patient details from config
        self.patient_fhir_id = patient_config['fhir_id']
        self.output_dir = Path(patient_config['output_dir'])
        
        # Parse birth date if provided (optional)
        if patient_config.get('birth_date'):
            self.birth_date = datetime.strptime(patient_config['birth_date'], '%Y-%m-%d')
        else:
            self.birth_date = None
        
        print(f"\n{'='*80}")
        print(f"📋 ALL PROCEDURES METADATA EXTRACTOR")
        print(f"{'='*80}")
        print(f"Patient FHIR ID: {self.patient_fhir_id}")
        if self.birth_date:
            print(f"Birth Date: {self.birth_date.strftime('%Y-%m-%d')}")
        print(f"Output Directory: {self.output_dir}")
        print(f"Database: {self.database}")
        print(f"{'='*80}\n")
    
    def execute_query(self, query: str, description: str) -> pd.DataFrame:
        """Execute Athena query and return results as DataFrame"""
        print(f"📋 {description.upper()}")
        print(f"  Query: {query[:100]}..." if len(query) > 100 else f"  Query: {query}")
        
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
                    print(f"  ✗ Query {state}: {reason}\n")
                    return pd.DataFrame()
                
                time.sleep(2)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
            
            # Parse to DataFrame
            data_rows = []
            if len(results['ResultSet']['Rows']) > 1:
                columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
                
                for row in results['ResultSet']['Rows'][1:]:
                    row_data = {}
                    for i, col in enumerate(columns):
                        value = row['Data'][i].get('VarCharValue', '') if i < len(row['Data']) else ''
                        row_data[col] = value if value else None
                    data_rows.append(row_data)
            
            df = pd.DataFrame(data_rows)
            print(f"  ✓ ({len(df)} rows)\n")
            return df
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}\n")
            return pd.DataFrame()
    
    def extract_main_procedures(self) -> pd.DataFrame:
        """Extract main procedure records"""
        query = f"""
        SELECT 
            p.id as procedure_fhir_id,
            
            -- procedure table (proc_ prefix)
            p.status as proc_status,
            p.performed_date_time as proc_performed_date_time,
            p.performed_period_start as proc_performed_period_start,
            p.performed_period_end as proc_performed_period_end,
            p.performed_string as proc_performed_string,
            p.performed_age_value as proc_performed_age_value,
            p.performed_age_unit as proc_performed_age_unit,
            p.code_text as proc_code_text,
            p.category_text as proc_category_text,
            p.subject_reference as proc_subject_reference,
            p.encounter_reference as proc_encounter_reference,
            p.encounter_display as proc_encounter_display,
            p.location_reference as proc_location_reference,
            p.location_display as proc_location_display,
            p.outcome_text as proc_outcome_text,
            p.recorder_reference as proc_recorder_reference,
            p.recorder_display as proc_recorder_display,
            p.asserter_reference as proc_asserter_reference,
            p.asserter_display as proc_asserter_display,
            p.status_reason_text as proc_status_reason_text
        FROM {self.database}.procedure p
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        ORDER BY p.performed_date_time
        """
        
        df = self.execute_query(query, "EXTRACTING MAIN PROCEDURES TABLE")
        
        if not df.empty:
            print(f"  📊 Procedure Status Breakdown:")
            print(df['proc_status'].value_counts().to_string(index=True))
            print()
            
            # Date range
            df_with_dates = df[df['proc_performed_date_time'].notna()]
            if not df_with_dates.empty:
                print(f"  📅 Date Range: {df_with_dates['proc_performed_date_time'].min()} to {df_with_dates['proc_performed_date_time'].max()}")
                print()
        
        return df
    
    def extract_procedure_codes(self) -> pd.DataFrame:
        """Extract CPT/HCPCS procedure codes"""
        query = f"""
        SELECT 
            pcc.procedure_id as procedure_fhir_id,
            
            -- procedure_code_coding table (pcc_ prefix)
            pcc.code_coding_system as pcc_code_coding_system,
            pcc.code_coding_code as pcc_code_coding_code,
            pcc.code_coding_display as pcc_code_coding_display
        FROM {self.database}.procedure_code_coding pcc
        JOIN {self.database}.procedure p ON pcc.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        ORDER BY pcc.code_coding_code
        """
        
        df = self.execute_query(query, "EXTRACTING PROCEDURE CODES (CPT/HCPCS)")
        
        if not df.empty:
            print(f"  📊 Code System Breakdown:")
            print(df['pcc_code_coding_system'].value_counts().to_string(index=True))
            print()
            
            # Check for surgical keywords
            surgical_keywords = ['craniotomy', 'craniectomy', 'resection', 'excision', 'biopsy', 
                               'surgery', 'surgical', 'anesthesia', 'anes', 'oper']
            df['is_surgical_keyword'] = df['pcc_code_coding_display'].str.lower().str.contains(
                '|'.join(surgical_keywords), na=False
            )
            surgical_count = df['is_surgical_keyword'].sum()
            print(f"  🔪 Potential Surgical Procedures (by keyword): {surgical_count}/{len(df)}")
            print()
        
        return df
    
    def extract_procedure_categories(self) -> pd.DataFrame:
        """Extract procedure categories"""
        query = f"""
        SELECT 
            pcat.procedure_id as procedure_fhir_id,
            
            -- procedure_category_coding table (pcat_ prefix)
            pcat.category_coding_system as pcat_category_coding_system,
            pcat.category_coding_code as pcat_category_coding_code,
            pcat.category_coding_display as pcat_category_coding_display
        FROM {self.database}.procedure_category_coding pcat
        JOIN {self.database}.procedure p ON pcat.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        """
        
        return self.execute_query(query, "EXTRACTING PROCEDURE CATEGORIES")
    
    def extract_procedure_body_sites(self) -> pd.DataFrame:
        """Extract anatomical body sites for procedures"""
        query = f"""
        SELECT 
            pbs.procedure_id as procedure_fhir_id,
            
            -- procedure_body_site table (pbs_ prefix)
            pbs.body_site_coding as pbs_body_site_coding,
            pbs.body_site_text as pbs_body_site_text
        FROM {self.database}.procedure_body_site pbs
        JOIN {self.database}.procedure p ON pbs.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        """
        
        return self.execute_query(query, "EXTRACTING PROCEDURE BODY SITES")
    
    def extract_procedure_performers(self) -> pd.DataFrame:
        """Extract procedure performers (surgeons, providers)"""
        query = f"""
        SELECT 
            pp.procedure_id as procedure_fhir_id,
            
            -- procedure_performer table (pp_ prefix)
            pp.performer_function_text as pp_performer_function_text,
            pp.performer_actor_reference as pp_performer_actor_reference,
            pp.performer_actor_type as pp_performer_actor_type,
            pp.performer_actor_display as pp_performer_actor_display,
            pp.performer_on_behalf_of_reference as pp_performer_on_behalf_of_reference,
            pp.performer_on_behalf_of_display as pp_performer_on_behalf_of_display
        FROM {self.database}.procedure_performer pp
        JOIN {self.database}.procedure p ON pp.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        """
        
        df = self.execute_query(query, "EXTRACTING PROCEDURE PERFORMERS")
        
        if not df.empty:
            print(f"  👨‍⚕️ Performer Types:")
            print(df['pp_performer_actor_type'].value_counts().to_string(index=True))
            print()
        
        return df
    
    def extract_procedure_reasons(self) -> pd.DataFrame:
        """Extract reasons/indications for procedures"""
        query = f"""
        SELECT 
            prc.procedure_id as procedure_fhir_id,
            
            -- procedure_reason_code table (prc_ prefix)
            prc.reason_code_coding as prc_reason_code_coding,
            prc.reason_code_text as prc_reason_code_text
        FROM {self.database}.procedure_reason_code prc
        JOIN {self.database}.procedure p ON prc.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        """
        
        return self.execute_query(query, "EXTRACTING PROCEDURE REASONS")
    
    def extract_procedure_reports(self) -> pd.DataFrame:
        """Extract procedure reports (operative notes, etc.)"""
        query = f"""
        SELECT 
            pr.procedure_id as procedure_fhir_id,
            
            -- procedure_report table (ppr_ prefix)
            pr.report_reference as ppr_report_reference,
            pr.report_type as ppr_report_type,
            pr.report_display as ppr_report_display
        FROM {self.database}.procedure_report pr
        JOIN {self.database}.procedure p ON pr.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        """
        
        return self.execute_query(query, "EXTRACTING PROCEDURE REPORTS")
    
    def calculate_age_at_procedure(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate age in days at time of procedure"""
        if 'proc_performed_date_time' in df.columns:
            df['procedure_date'] = pd.to_datetime(df['proc_performed_date_time'], errors='coerce').dt.date
            df['age_at_procedure_days'] = df['procedure_date'].apply(
                lambda x: (x - self.birth_date.date()).days if pd.notna(x) else None
            )
        return df
    
    def merge_and_export(self, procedures_df: pd.DataFrame, codes_df: pd.DataFrame,
                        categories_df: pd.DataFrame, body_sites_df: pd.DataFrame,
                        performers_df: pd.DataFrame, reasons_df: pd.DataFrame,
                        reports_df: pd.DataFrame) -> pd.DataFrame:
        """Merge all procedure data and export to CSV"""
        print(f"{'='*80}")
        print("🔗 MERGING ALL DATA")
        print(f"{'='*80}\n")
        
        # Start with main procedures
        merged = procedures_df.copy()
        
        # Calculate age
        merged = self.calculate_age_at_procedure(merged)
        
        # Merge codes (can be multiple per procedure)
        if not codes_df.empty:
            # Aggregate multiple codes into pipe-separated lists
            codes_agg = codes_df.groupby('procedure_fhir_id').agg({
                'pcc_code_coding_system': lambda x: ' | '.join(x.astype(str).unique()),
                'pcc_code_coding_code': lambda x: ' | '.join(x.astype(str).unique()),
                'pcc_code_coding_display': lambda x: ' | '.join(x.astype(str).unique()),
                'is_surgical_keyword': 'max'  # True if ANY code has surgical keyword
            }).reset_index()
            
            merged = merged.merge(codes_agg, on='procedure_fhir_id', how='left', suffixes=('', '_codes'))
            print(f"  ✓ Merged procedure codes: {len(codes_agg)} unique procedures with codes")
        
        # Merge categories
        if not categories_df.empty:
            categories_agg = categories_df.groupby('procedure_fhir_id').agg({
                'pcat_category_coding_display': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None
            }).reset_index()
            merged = merged.merge(categories_agg, on='procedure_fhir_id', how='left', suffixes=('', '_cat'))
            print(f"  ✓ Merged categories: {len(categories_agg)} procedures with categories")
        
        # Merge body sites
        if not body_sites_df.empty:
            body_sites_agg = body_sites_df.groupby('procedure_fhir_id').agg({
                'pbs_body_site_text': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None
            }).reset_index()
            merged = merged.merge(body_sites_agg, on='procedure_fhir_id', how='left')
            print(f"  ✓ Merged body sites: {len(body_sites_agg)} procedures with body sites")
        
        # Merge performers
        if not performers_df.empty:
            performers_agg = performers_df.groupby('procedure_fhir_id').agg({
                'pp_performer_actor_display': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None,
                'pp_performer_function_text': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None
            }).reset_index()
            merged = merged.merge(performers_agg, on='procedure_fhir_id', how='left')
            print(f"  ✓ Merged performers: {len(performers_agg)} procedures with performers")
        
        # Merge reasons
        if not reasons_df.empty:
            reasons_agg = reasons_df.groupby('procedure_fhir_id').agg({
                'prc_reason_code_text': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None
            }).reset_index()
            merged = merged.merge(reasons_agg, on='procedure_fhir_id', how='left')
            print(f"  ✓ Merged reasons: {len(reasons_agg)} procedures with reasons")
        
        # Merge reports
        if not reports_df.empty:
            reports_agg = reports_df.groupby('procedure_fhir_id').agg({
                'ppr_report_reference': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None,
                'ppr_report_display': lambda x: ' | '.join(x.dropna().astype(str).unique()) if len(x.dropna()) > 0 else None
            }).reset_index()
            merged = merged.merge(reports_agg, on='procedure_fhir_id', how='left')
            print(f"  ✓ Merged reports: {len(reports_agg)} procedures with operative reports")
        
        print(f"\n  ✓ Total merged procedures: {len(merged)} rows")
        print(f"  ✓ Total columns: {len(merged.columns)}")
        
        # Export to CSV
        output_file = self.output_dir / 'procedures.csv'
        
        merged.to_csv(output_file, index=False)
        print(f"\n  ✓ Saved to: {output_file}")
        print(f"  ✓ File size: {output_file.stat().st_size / 1024:.1f} KB\n")
        
        return merged

def main():
    """Main execution"""
    try:
        # Load patient configuration
        config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
        with open(config_file) as f:
            config = json.load(f)
        
        extractor = AllProceduresExtractor(
            aws_profile=config['aws_profile'],
            database=config['database'],
            patient_config=config
        )
        
        # Ensure output directory exists
        extractor.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract from all procedure tables
        procedures_df = extractor.extract_main_procedures()
        codes_df = extractor.extract_procedure_codes()
        categories_df = extractor.extract_procedure_categories()
        body_sites_df = extractor.extract_procedure_body_sites()
        performers_df = extractor.extract_procedure_performers()
        reasons_df = extractor.extract_procedure_reasons()
        reports_df = extractor.extract_procedure_reports()
        
        # Merge and export
        if not procedures_df.empty:
            merged_df = extractor.merge_and_export(
                procedures_df, codes_df, categories_df, body_sites_df,
                performers_df, reasons_df, reports_df
            )
            
            # Summary
            print(f"{'='*80}")
            print("✅ EXTRACTION COMPLETE")
            print(f"{'='*80}\n")
            print(f"📊 Procedures Staging File Summary:")
            print(f"  - Total procedures: {len(merged_df)}")
            print(f"  - Columns: {len(merged_df.columns)}")
            print(f"  - Date range: {merged_df['procedure_date'].min()} to {merged_df['procedure_date'].max()}")
            
            if 'is_surgical_keyword' in merged_df.columns:
                surgical = merged_df['is_surgical_keyword'].sum()
                print(f"  - Potential surgical procedures: {surgical}/{len(merged_df)}")
            
            print(f"\n  Output: {extractor.output_dir}/procedures.csv")
            print(f"\n{'='*80}\n")
        else:
            print("\n❌ No procedures found\n")
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
