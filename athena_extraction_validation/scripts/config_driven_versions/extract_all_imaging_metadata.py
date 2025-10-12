#!/usr/bin/env python3
"""
Extract ALL imaging studies with comprehensive metadata from patient configuration for patient C1277724

Creates a staging file integrating radiology materialized views.

This is a STAGING file following the documented approach from:
- IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md
- POST_IMPLEMENTATION_REVIEW_IMAGING_CORTICOSTEROIDS.md  
- ATHENA_IMAGING_QUERY.md

Strategy:
1. Query radiology_imaging_mri for MRI procedures (structured metadata)
2. JOIN radiology_imaging_mri_results for narrative text
3. Query radiology_imaging for other modalities (CT, X-ray, etc.)
4. Calculate age_at_imaging from birth_date
5. Extract all imaging - filter/align corticosteroids in separate script

Key Learning: Use simple queries, avoid complex nested subqueries due to Athena limitations
"""

import boto3
import pandas as pd
import time
import logging
import json
from datetime import datetime
from pathlib import Path
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImagingExtractor:
    def __init__(self, patient_config: dict):
        """Initialize AWS Athena connection from patient configuration"""
        # Load from config
        self.patient_fhir_id = patient_config['fhir_id']
        self.output_dir = Path(patient_config['output_dir'])
        self.database = patient_config['database']
        self.s3_output = patient_config['s3_output']
        
        if patient_config.get('birth_date'):
            self.birth_date = patient_config['birth_date']
        else:
            self.birth_date = None
        
        aws_profile = patient_config['aws_profile']
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        
        logger.info("="*80)
        logger.info("📊 IMAGING STUDIES METADATA EXTRACTOR")
        logger.info("="*80)
        logger.info(f"Patient FHIR ID: {self.patient_fhir_id}")
        if self.birth_date:
            logger.info(f"Birth Date: {self.birth_date}")
        logger.info(f"Output Directory: {self.output_dir}")
        logger.info(f"Database: {self.database}")
        logger.info("="*80 + "\n")
    
    def execute_query(self, query: str, description: str) -> pd.DataFrame:
        """Execute Athena query and return results as DataFrame"""
        logger.info(f"\n📋 {description}")
        logger.info(f"  Starting query execution...")
        
        start_time = time.time()
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.s3_output}
            )
            
            query_id = response['QueryExecutionId']
            
            # Wait for query completion
            while True:
                status_response = self.athena.get_query_execution(QueryExecutionId=query_id)
                status = status_response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                time.sleep(0.5)
            
            if status != 'SUCCEEDED':
                error_msg = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                logger.error(f"  ❌ Query failed: {error_msg}")
                return pd.DataFrame()
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
            
            # Parse results
            if not results['ResultSet']['Rows']:
                logger.info(f"  ⚠️  No results returned")
                return pd.DataFrame()
            
            # Extract column names
            columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            
            # Extract data rows
            data = []
            for row in results['ResultSet']['Rows'][1:]:
                data.append([col.get('VarCharValue', '') for col in row['Data']])
            
            df = pd.DataFrame(data, columns=columns)
            
            duration = time.time() - start_time
            logger.info(f"  ✅ Returned {len(df)} rows in {duration:.1f} seconds")
            
            return df
            
        except Exception as e:
            logger.error(f"  ❌ Query execution error: {str(e)}")
            return pd.DataFrame()
    
    def discover_imaging_tables(self):
        """Discover all imaging-related tables in the database"""
        logger.info("\n🔍 STEP 1: Discovering Imaging Tables")
        logger.info("-" * 80)
        
        query = f"""
        SHOW TABLES IN {self.database}
        """
        
        df = self.execute_query(query, "Listing all tables")
        
        if df.empty:
            logger.warning("No tables found!")
            return []
        
        # Filter for imaging-related tables
        imaging_patterns = ['imaging', 'diagnostic_report', 'observation']
        imaging_tables = [table for table in df.iloc[:, 0] if any(pattern in table.lower() for pattern in imaging_patterns)]
        
        logger.info(f"\n📊 Found {len(imaging_tables)} imaging-related tables:")
        for table in imaging_tables:
            logger.info(f"  - {table}")
        
        return imaging_tables
    
    def extract_mri_imaging(self):
        """
        Extract MRI imaging from radiology_imaging_mri table
        
        Based on IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md:
        - Primary table: radiology_imaging_mri
        - Key fields: patient_id, imaging_procedure_id, result_datetime, imaging_procedure
        - Linkage: result_diagnostic_report_id → radiology_imaging_mri_results
        """
        logger.info("\n📊 STEP 2: Extracting MRI Imaging")
        logger.info("-" * 80)
        
        # Use patient_id (FHIR ID) as documented in implementation guide
        query = f"""
        SELECT 
            patient_id,
            '{self.patient_fhir_id}' as patient_mrn,
            imaging_procedure_id,
            result_datetime as imaging_date,
            imaging_procedure,
            result_diagnostic_report_id,
            'MRI' as imaging_modality
        FROM radiology_imaging_mri
        WHERE patient_id = '{self.patient_fhir_id}'
        ORDER BY result_datetime DESC
        """
        
        df = self.execute_query(query, "Querying radiology_imaging_mri table")
        return df
    
    def extract_mri_results(self):
        """
        Extract MRI results/narratives from radiology_imaging_mri_results table
        
        Per POST_IMPLEMENTATION_REVIEW_IMAGING_CORTICOSTEROIDS.md:
        - Contains result_information (narrative text with clinical impressions)
        - Contains result_display (result type)
        - JOIN via imaging_procedure_id (NOT diagnostic_report_id as initially assumed)
        - Avoid nested subqueries - use patient_id directly in simpler query
        """
        logger.info("\n📊 STEP 3: Extracting MRI Results/Narratives")
        logger.info("-" * 80)
        
        # Simplified query - get all results, will JOIN in Python to avoid SQL complexity
        query = f"""
        SELECT DISTINCT
            results.imaging_procedure_id,
            results.result_information,
            results.result_display
        FROM radiology_imaging_mri_results results
        WHERE EXISTS (
            SELECT 1
            FROM radiology_imaging_mri mri
            WHERE mri.imaging_procedure_id = results.imaging_procedure_id
            AND mri.patient_id = '{self.patient_fhir_id}'
        )
        """
        
        df = self.execute_query(query, "Querying radiology_imaging_mri_results table")
        return df
    
    def extract_other_imaging(self):
        """
        Extract non-MRI imaging from radiology_imaging table
        
        Per IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md:
        - Table: radiology_imaging (other modalities - CT, X-ray, ultrasound)
        - Same structure as radiology_imaging_mri
        - Use patient_id for filtering
        """
        logger.info("\n📊 STEP 4: Extracting Other Imaging (CT, X-ray, etc.)")
        logger.info("-" * 80)
        
        query = f"""
        SELECT 
            patient_id,
            '{self.patient_fhir_id}' as patient_mrn,
            imaging_procedure_id,
            result_datetime as imaging_date,
            imaging_procedure,
            result_diagnostic_report_id,
            COALESCE(imaging_procedure, 'Unknown') as imaging_modality
        FROM radiology_imaging
        WHERE patient_id = '{self.patient_fhir_id}'
        ORDER BY result_datetime DESC
        """
        
        df = self.execute_query(query, "Querying radiology_imaging table")
        return df
    
    def extract_diagnostic_reports(self):
        """Extract diagnostic reports (radiology reports) by report_id"""
        logger.info("\n📊 STEP 5: Extracting Diagnostic Reports")
        logger.info("-" * 80)
        
        query = f"""
        SELECT DISTINCT
            dr.id as diagnostic_report_id,
            dr.status as report_status,
            dr.category_text,
            dr.code_text as report_type,
            dr.subject_reference,
            dr.encounter_reference,
            dr.effective_date_time as report_date,
            dr.issued,
            dr.conclusion as report_conclusion
        FROM diagnostic_report dr
        WHERE dr.id IN (
            SELECT DISTINCT result_diagnostic_report_id 
            FROM radiology_imaging_mri 
            WHERE patient_id = '{self.patient_fhir_id}'
            AND result_diagnostic_report_id IS NOT NULL
            UNION
            SELECT DISTINCT result_diagnostic_report_id 
            FROM radiology_imaging 
            WHERE patient_id = '{self.patient_fhir_id}'
            AND result_diagnostic_report_id IS NOT NULL
        )
        """
        
        df = self.execute_query(query, "Querying diagnostic_report table")
        return df
    
    def merge_all_data(self, mri_df, mri_results_df, other_imaging_df, reports_df):
        """Merge all imaging data into comprehensive staging file"""
        logger.info("\n� STEP 6: Merging All Imaging Data")
        logger.info("-" * 80)
        
        # Merge MRI with results
        if not mri_df.empty and not mri_results_df.empty:
            mri_merged = mri_df.merge(
                mri_results_df,
                on='imaging_procedure_id',
                how='left'
            )
            logger.info(f"  ✅ Merged MRI results ({len(mri_merged)} MRI records)")
        else:
            mri_merged = mri_df.copy() if not mri_df.empty else pd.DataFrame()
        
        # Combine MRI and other imaging
        if not mri_merged.empty and not other_imaging_df.empty:
            # Ensure consistent columns
            all_cols = set(mri_merged.columns) | set(other_imaging_df.columns)
            for col in all_cols:
                if col not in mri_merged.columns:
                    mri_merged[col] = ''
                if col not in other_imaging_df.columns:
                    other_imaging_df[col] = ''
            
            merged_df = pd.concat([mri_merged, other_imaging_df], ignore_index=True)
            logger.info(f"  ✅ Combined MRI and other imaging ({len(merged_df)} total records)")
        elif not mri_merged.empty:
            merged_df = mri_merged
            logger.info(f"  ✅ Using MRI only ({len(merged_df)} records)")
        elif not other_imaging_df.empty:
            merged_df = other_imaging_df
            logger.info(f"  ✅ Using other imaging only ({len(merged_df)} records)")
        else:
            logger.error("  ❌ No imaging data to merge!")
            return pd.DataFrame()
        
        # Merge diagnostic reports
        if not reports_df.empty:
            merged_df = merged_df.merge(
                reports_df[['diagnostic_report_id', 'report_status', 'report_conclusion']],
                left_on='result_diagnostic_report_id',
                right_on='diagnostic_report_id',
                how='left'
            )
            logger.info(f"  ✅ Merged diagnostic reports ({len(reports_df)} reports)")
        
        # Calculate age at imaging
        try:
            birth_dt = pd.to_datetime(self.birth_date).tz_localize(None)  # Remove timezone
            merged_df['imaging_date_dt'] = pd.to_datetime(merged_df['imaging_date'], errors='coerce').dt.tz_localize(None)
            merged_df['age_at_imaging_days'] = (merged_df['imaging_date_dt'] - birth_dt).dt.days
            merged_df['age_at_imaging_years'] = merged_df['age_at_imaging_days'] / 365.25
            merged_df = merged_df.drop('imaging_date_dt', axis=1)
            logger.info(f"  ✅ Calculated age at imaging")
        except Exception as e:
            logger.warning(f"  ⚠️  Could not calculate age: {str(e)}")
        
        return merged_df
    
    def generate_summary(self, df):
        """Generate summary statistics"""
        logger.info("\n" + "="*80)
        logger.info("IMAGING EXTRACTION SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\nTotal imaging studies extracted: {len(df)}")
        
        if len(df) > 0:
            # Modality breakdown
            if 'imaging_modality' in df.columns:
                logger.info("\nImaging Modalities:")
                for modality, count in df['imaging_modality'].value_counts().items():
                    logger.info(f"  {modality}: {count}")
            
            # Procedure breakdown (top 10)
            if 'imaging_procedure' in df.columns:
                logger.info("\nTop 10 Imaging Procedures:")
                for procedure, count in df['imaging_procedure'].value_counts().head(10).items():
                    logger.info(f"  {procedure}: {count}")
            
            # Report status
            if 'report_status' in df.columns:
                logger.info("\nDiagnostic Report Status:")
                for status, count in df['report_status'].value_counts().items():
                    logger.info(f"  {status}: {count}")
            
            # Date range
            if 'imaging_date' in df.columns:
                imaging_dates = pd.to_datetime(df['imaging_date'], errors='coerce').dropna()
                if len(imaging_dates) > 0:
                    logger.info(f"\nTemporal Coverage:")
                    logger.info(f"  First imaging: {imaging_dates.min()}")
                    logger.info(f"  Last imaging: {imaging_dates.max()}")
                    logger.info(f"  Span: {(imaging_dates.max() - imaging_dates.min()).days} days")
            
            # Age range
            if 'age_at_imaging_years' in df.columns:
                ages = df['age_at_imaging_years'].dropna()
                if len(ages) > 0:
                    logger.info(f"\nAge at Imaging:")
                    logger.info(f"  Min: {ages.min():.1f} years")
                    logger.info(f"  Max: {ages.max():.1f} years")
                    logger.info(f"  Mean: {ages.mean():.1f} years")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Output saved to: {self.output_dir / 'imaging.csv'}")
        logger.info(f"{'='*80}\n")


def main():
    """Main execution"""
    # Load patient configuration
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    start_time = datetime.now()
    
    logger.info("Starting imaging metadata extraction...")
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize extractor
    extractor = ImagingExtractor(patient_config=config)
    
    # Discover imaging tables
    imaging_tables = extractor.discover_imaging_tables()
    
    # Extract MRI imaging
    mri_df = extractor.extract_mri_imaging()
    
    # Extract MRI results
    mri_results_df = extractor.extract_mri_results()
    
    # Extract other imaging (CT, X-ray, etc.)
    other_imaging_df = extractor.extract_other_imaging()
    
    if mri_df.empty and other_imaging_df.empty:
        logger.error("No imaging studies found! Exiting.")
        return 1
    
    # Extract diagnostic reports
    reports_df = extractor.extract_diagnostic_reports()
    
    # Merge all data
    final_df = extractor.merge_all_data(mri_df, mri_results_df, other_imaging_df, reports_df)
    
    if final_df.empty:
        logger.error("No data after merging! Exiting.")
        return 1
    
    # Save to CSV
    final_df.to_csv(extractor.output_dir / "imaging.csv", index=False)
    logger.info(f"\n✅ Saved {len(final_df)} imaging studies to {extractor.output_dir / "imaging.csv"}")
    
    # Generate summary
    extractor.generate_summary(final_df)
    
    # Execution time
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Total execution time: {duration:.1f} seconds")
    
    return 0


if __name__ == '__main__':
    exit(main())
