#!/usr/bin/env python3
"""
Extract ALL problem list diagnoses for patient from FHIR database

Creates a staging file with all diagnosis/condition data from problem_list_diagnoses table.

This is a STAGING file following the documented approach from:
- COMPREHENSIVE_PROBLEM_LIST_ANALYSIS.md
- CONDITIONS_PREDISPOSITIONS_COMPREHENSIVE_MAPPING.md

Strategy:
1. Query problem_list_diagnoses table for all patient diagnoses
2. Include all columns EXCEPT mrn (per privacy requirements)
3. Calculate age at diagnosis from birth_date
4. Sort by recorded_date for temporal analysis

Key Table:
- problem_list_diagnoses: Materialized view with diagnosis data from condition table
  Columns: patient_id, condition_id, diagnosis_name, clinical_status_text,
           onset_date_time, abatement_date_time, recorded_date,
           icd10_code, icd10_display, snomed_code, snomed_display
"""

import boto3
import pandas as pd
import time
import json
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiagnosesExtractor:
    def __init__(self, patient_config: dict):
        """Initialize AWS Athena connection"""
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
        logger.info("🏥 DIAGNOSES METADATA EXTRACTOR")
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
    
    def extract_diagnoses(self):
        """
        Extract all problem list diagnoses from problem_list_diagnoses table
        
        Includes:
        - condition_id: Unique identifier for the diagnosis
        - diagnosis_name: Human-readable diagnosis name
        - clinical_status_text: Status (Active, Resolved, Inactive, etc.)
        - onset_date_time: When diagnosis began
        - abatement_date_time: When diagnosis resolved (if applicable)
        - recorded_date: When diagnosis was recorded in system
        - icd10_code: ICD-10 diagnosis code
        - icd10_display: ICD-10 code description
        - snomed_code: SNOMED CT code
        - snomed_display: SNOMED CT description
        
        Excludes:
        - mrn: Medical Record Number (privacy requirement)
        """
        logger.info("\n📊 STEP 1: Extracting Problem List Diagnoses")
        logger.info("-" * 80)
        
        query = f"""
        SELECT 
            patient_id,
            condition_id,
            diagnosis_name,
            clinical_status_text,
            onset_date_time,
            abatement_date_time,
            recorded_date,
            icd10_code,
            icd10_display,
            snomed_code,
            snomed_display
        FROM problem_list_diagnoses
        WHERE patient_id = '{self.patient_fhir_id}'
        ORDER BY recorded_date DESC, onset_date_time DESC
        """
        
        df = self.execute_query(query, "Querying problem_list_diagnoses table")
        return df
    
    def calculate_ages(self, df):
        """Calculate age at diagnosis dates"""
        logger.info("\n🔄 STEP 2: Calculating Ages")
        logger.info("-" * 80)
        
        if self.birth_date:
            try:
                birth_dt = pd.to_datetime(self.birth_date).tz_localize(None)
                
                # Calculate age at onset
                if 'onset_date_time' in df.columns:
                    df['onset_date_dt'] = pd.to_datetime(df['onset_date_time'], errors='coerce').dt.tz_localize(None)
                    df['age_at_onset_days'] = (df['onset_date_dt'] - birth_dt).dt.days
                    df['age_at_onset_years'] = df['age_at_onset_days'] / 365.25
                    df = df.drop('onset_date_dt', axis=1)
                    logger.info(f"  ✅ Calculated age at onset")
                
                # Calculate age at abatement
                if 'abatement_date_time' in df.columns:
                    df['abatement_date_dt'] = pd.to_datetime(df['abatement_date_time'], errors='coerce').dt.tz_localize(None)
                    df['age_at_abatement_days'] = (df['abatement_date_dt'] - birth_dt).dt.days
                    df['age_at_abatement_years'] = df['age_at_abatement_days'] / 365.25
                    df = df.drop('abatement_date_dt', axis=1)
                    logger.info(f"  ✅ Calculated age at abatement")
                
                # Calculate age at recording
                if 'recorded_date' in df.columns:
                    df['recorded_date_dt'] = pd.to_datetime(df['recorded_date'], errors='coerce').dt.tz_localize(None)
                    df['age_at_recorded_days'] = (df['recorded_date_dt'] - birth_dt).dt.days
                    df['age_at_recorded_years'] = df['age_at_recorded_days'] / 365.25
                    df = df.drop('recorded_date_dt', axis=1)
                    logger.info(f"  ✅ Calculated age at recording")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not calculate ages: {str(e)}")
        
        return df
    
    def generate_summary(self, df):
        """Generate summary statistics"""
        logger.info("\n" + "="*80)
        logger.info("DIAGNOSES EXTRACTION SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\nTotal diagnoses extracted: {len(df)}")
        
        if len(df) > 0:
            # Clinical status breakdown
            if 'clinical_status_text' in df.columns:
                logger.info("\nClinical Status:")
                for status, count in df['clinical_status_text'].value_counts().items():
                    logger.info(f"  {status}: {count}")
            
            # Top diagnoses
            if 'diagnosis_name' in df.columns:
                logger.info(f"\nTop 10 Diagnoses:")
                for diag, count in df['diagnosis_name'].value_counts().head(10).items():
                    logger.info(f"  {diag}: {count}")
            
            # ICD-10 codes
            if 'icd10_code' in df.columns:
                icd10_with_codes = df['icd10_code'].notna().sum()
                logger.info(f"\nICD-10 Coding:")
                logger.info(f"  Diagnoses with ICD-10 codes: {icd10_with_codes} ({icd10_with_codes/len(df)*100:.1f}%)")
            
            # SNOMED codes
            if 'snomed_code' in df.columns:
                snomed_with_codes = df['snomed_code'].notna().sum()
                logger.info(f"\nSNOMED CT Coding:")
                logger.info(f"  Diagnoses with SNOMED codes: {snomed_with_codes} ({snomed_with_codes/len(df)*100:.1f}%)")
            
            # Date ranges
            if 'onset_date_time' in df.columns:
                onset_dates = pd.to_datetime(df['onset_date_time'], errors='coerce').dropna()
                if len(onset_dates) > 0:
                    logger.info(f"\nOnset Date Coverage:")
                    logger.info(f"  First onset: {onset_dates.min()}")
                    logger.info(f"  Last onset: {onset_dates.max()}")
                    logger.info(f"  Span: {(onset_dates.max() - onset_dates.min()).days} days")
            
            if 'recorded_date' in df.columns:
                recorded_dates = pd.to_datetime(df['recorded_date'], errors='coerce').dropna()
                if len(recorded_dates) > 0:
                    logger.info(f"\nRecorded Date Coverage:")
                    logger.info(f"  First recorded: {recorded_dates.min()}")
                    logger.info(f"  Last recorded: {recorded_dates.max()}")
                    logger.info(f"  Span: {(recorded_dates.max() - recorded_dates.min()).days} days")
            
            # Age ranges
            if 'age_at_onset_years' in df.columns:
                ages = df['age_at_onset_years'].dropna()
                if len(ages) > 0:
                    logger.info(f"\nAge at Diagnosis Onset:")
                    logger.info(f"  Min: {ages.min():.1f} years")
                    logger.info(f"  Max: {ages.max():.1f} years")
                    logger.info(f"  Mean: {ages.mean():.1f} years")
            
            # Active vs resolved
            if 'abatement_date_time' in df.columns:
                resolved_count = df['abatement_date_time'].notna().sum()
                active_count = df['abatement_date_time'].isna().sum()
                logger.info(f"\nDiagnosis Resolution:")
                logger.info(f"  Active (no abatement date): {active_count}")
                logger.info(f"  Resolved (has abatement date): {resolved_count}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Output saved to: {self.output_dir}/diagnoses.csv")
        logger.info(f"{'='*80}\n")


def main():
    """Main execution"""
    start_time = datetime.now()
    
    # Load patient configuration
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    logger.info("Starting diagnoses metadata extraction...")
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize extractor
    extractor = DiagnosesExtractor(patient_config=config)
    
    # Ensure output directory exists
    extractor.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract diagnoses
    diagnoses_df = extractor.extract_diagnoses()
    
    if diagnoses_df.empty:
        logger.error("No diagnoses found! Exiting.")
        return 1
    
    # Calculate ages
    final_df = extractor.calculate_ages(diagnoses_df)
    
    # Save to CSV
    output_file = extractor.output_dir / 'diagnoses.csv'
    final_df.to_csv(output_file, index=False)
    logger.info(f"\n✅ Saved {len(final_df)} diagnoses to {output_file}")
    
    # Generate summary
    extractor.generate_summary(final_df)
    
    # Execution time
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Total execution time: {duration:.1f} seconds")
    
    return 0


if __name__ == '__main__':
    exit(main())
