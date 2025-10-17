#!/usr/bin/env python3
"""
Extract ALL measurements (anthropometric and lab data) for patient C1277724

Creates a staging file integrating observation and lab_test data.

This is a STAGING file following the documented approach from:
- MEASUREMENTS_IMPLEMENTATION_GUIDE.md
- Gold standard: measurements.csv (height, weight, head circumference)

Strategy:
1. Query observation table for anthropometric measurements (height, weight, head circumference)
2. Query lab_tests + lab_test_results for laboratory measurements
3. Combine and calculate age_at_measurement from birth_date
4. Extract all measurements - filter/categorize in separate script if needed

Key Tables:
- observation: Vital signs, anthropometric measurements
- lab_tests: Laboratory test metadata (421 tests for C1277724)
- lab_test_results: Laboratory test results/values
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

class MeasurementsExtractor:
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
        logger.info("📊 MEASUREMENTS METADATA EXTRACTOR")
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
    
    def extract_anthropometric_observations(self):
        """
        Extract anthropometric measurements from observation table
        
        Per MEASUREMENTS_IMPLEMENTATION_GUIDE.md:
        - Height: code_text LIKE '%height%' OR '%length%'
        - Weight: code_text LIKE '%weight%' (exclude birth/discharge weight)
        - Head Circumference: code_text LIKE '%head circumference%' OR '%ofc%'
        
        CRITICAL: observation table uses subject_reference = 'FHIR_ID' 
        (WITHOUT 'Patient/' prefix, unlike other tables)
        """
        logger.info("\n📊 STEP 1: Extracting Anthropometric Observations")
        logger.info("-" * 80)
        
        query = f"""
        SELECT 
            subject_reference as patient_id,
            
            -- observation table (obs_ prefix)
            id as obs_observation_id,
            code_text as obs_measurement_type,
            value_quantity_value as obs_measurement_value,
            value_quantity_unit as obs_measurement_unit,
            effective_datetime as obs_measurement_date,
            issued as obs_issued,
            status as obs_status,
            encounter_reference as obs_encounter_reference,
            'observation' as source_table
        FROM observation
        WHERE subject_reference = '{self.patient_fhir_id}'
        AND status = 'final'
        AND (
            LOWER(code_text) LIKE '%height%'
            OR LOWER(code_text) LIKE '%length%'
            OR (LOWER(code_text) LIKE '%weight%' 
                AND LOWER(code_text) NOT LIKE '%birth%'
                AND LOWER(code_text) NOT LIKE '%discharge%')
            OR LOWER(code_text) LIKE '%head circumference%'
            OR LOWER(code_text) LIKE '%head circ%'
            OR LOWER(code_text) LIKE '%ofc%'
        )
        ORDER BY effective_datetime DESC
        """
        
        df = self.execute_query(query, "Querying observation table for anthropometric data")
        return df
    
    def extract_lab_tests(self):
        """
        Extract laboratory tests from lab_tests table
        
        Per documentation: 421 lab tests exist for C1277724
        Tables: lab_tests (metadata) + lab_test_results (values)
        """
        logger.info("\n📊 STEP 2: Extracting Laboratory Tests")
        logger.info("-" * 80)
        
        query = f"""
        SELECT 
            patient_id,
            
            -- lab_tests table (lt_ prefix)
            test_id as lt_test_id,
            lab_test_name as lt_measurement_type,
            result_datetime as lt_measurement_date,
            lab_test_status as lt_status,
            result_diagnostic_report_id as lt_result_diagnostic_report_id,
            lab_test_requester as lt_lab_test_requester,
            'lab_tests' as source_table
        FROM lab_tests
        WHERE patient_id = '{self.patient_fhir_id}'
        ORDER BY result_datetime DESC
        """
        
        df = self.execute_query(query, "Querying lab_tests table")
        return df
    
    def extract_lab_test_results(self):
        """
        Extract laboratory test results/values from lab_test_results table
        
        Contains: test_component, value_string, value_quantity_value, value_quantity_unit,
        value_range (reference ranges), value_codeable_concept_text, value_boolean, value_integer
        """
        logger.info("\n📊 STEP 3: Extracting Laboratory Test Results")
        logger.info("-" * 80)
        
        query = f"""
        SELECT 
            ltr.test_id as lt_test_id,
            
            -- lab_test_results table (ltr_ prefix)
            ltr.test_component as ltr_test_component,
            ltr.value_string as ltr_value_string,
            ltr.value_quantity_value as ltr_measurement_value,
            ltr.value_quantity_unit as ltr_measurement_unit,
            ltr.value_codeable_concept_text as ltr_value_codeable_concept_text,
            ltr.value_range_low_value as ltr_value_range_low_value,
            ltr.value_range_low_unit as ltr_value_range_low_unit,
            ltr.value_range_high_value as ltr_value_range_high_value,
            ltr.value_range_high_unit as ltr_value_range_high_unit,
            ltr.value_boolean as ltr_value_boolean,
            ltr.value_integer as ltr_value_integer
        FROM lab_test_results ltr
        WHERE ltr.test_id IN (
            SELECT test_id 
            FROM lab_tests 
            WHERE patient_id = '{self.patient_fhir_id}'
        )
        """
        
        df = self.execute_query(query, "Querying lab_test_results table")
        return df
    
    def merge_all_data(self, observations_df, lab_tests_df, lab_results_df):
        """Merge all measurement data into comprehensive staging file"""
        logger.info("\n🔄 STEP 4: Merging All Measurement Data")
        logger.info("-" * 80)
        
        # Merge lab tests with results
        if not lab_tests_df.empty and not lab_results_df.empty:
            lab_merged = lab_tests_df.merge(
                lab_results_df,
                on='lt_test_id',
                how='left'
            )
            logger.info(f"  ✅ Merged lab results ({len(lab_merged)} lab test records)")
            
            # For labs, use measurement values from results where available
            lab_merged['ltr_measurement_value'] = lab_merged['ltr_measurement_value'].fillna('')
            lab_merged['ltr_measurement_unit'] = lab_merged['ltr_measurement_unit'].fillna('')
        else:
            lab_merged = lab_tests_df.copy() if not lab_tests_df.empty else pd.DataFrame()
        
        # Combine observations and lab tests
        if not observations_df.empty and not lab_merged.empty:
            # Ensure consistent columns
            all_cols = set(observations_df.columns) | set(lab_merged.columns)
            for col in all_cols:
                if col not in observations_df.columns:
                    observations_df[col] = ''
                if col not in lab_merged.columns:
                    lab_merged[col] = ''
            
            merged_df = pd.concat([observations_df, lab_merged], ignore_index=True)
            logger.info(f"  ✅ Combined observations and labs ({len(merged_df)} total records)")
        elif not observations_df.empty:
            merged_df = observations_df
            logger.info(f"  ✅ Using observations only ({len(merged_df)} records)")
        elif not lab_merged.empty:
            merged_df = lab_merged
            logger.info(f"  ✅ Using lab tests only ({len(merged_df)} records)")
        else:
            logger.error("  ❌ No measurement data to merge!")
            return pd.DataFrame()
        
        # Calculate age at measurement if birth_date provided
        # Use combined date field from either obs_measurement_date or lt_measurement_date
        if self.birth_date:
            try:
                birth_dt = pd.to_datetime(self.birth_date).tz_localize(None)
                
                # Combine date fields from both sources
                merged_df['measurement_date'] = merged_df.get('obs_measurement_date', '').fillna('') + merged_df.get('lt_measurement_date', '').fillna('')
                merged_df['measurement_date'] = merged_df['measurement_date'].replace('', pd.NA)
                
                merged_df['measurement_date_dt'] = pd.to_datetime(merged_df['measurement_date'], errors='coerce').dt.tz_localize(None)
                merged_df['age_at_measurement_days'] = (merged_df['measurement_date_dt'] - birth_dt).dt.days
                merged_df['age_at_measurement_years'] = merged_df['age_at_measurement_days'] / 365.25
                merged_df = merged_df.drop('measurement_date_dt', axis=1)
                logger.info(f"  ✅ Calculated age at measurement")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not calculate age: {str(e)}")
        
        # Sort by combined measurement date
        if 'measurement_date' in merged_df.columns:
            merged_df = merged_df.sort_values('measurement_date', ascending=False)
        
        return merged_df
    
    def generate_summary(self, df):
        """Generate summary statistics"""
        logger.info("\n" + "="*80)
        logger.info("MEASUREMENTS EXTRACTION SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\nTotal measurements extracted: {len(df)}")
        
        if len(df) > 0:
            # Source breakdown
            if 'source_table' in df.columns:
                logger.info("\nData Sources:")
                for source, count in df['source_table'].value_counts().items():
                    logger.info(f"  {source}: {count}")
            
            # Measurement type breakdown (top 20) - check both sources
            logger.info("\nTop 20 Measurement Types:")
            if 'obs_measurement_type' in df.columns:
                obs_types = df[df['obs_measurement_type'].notna()]['obs_measurement_type'].value_counts().head(10)
                if not obs_types.empty:
                    logger.info("  From observations:")
                    for mtype, count in obs_types.items():
                        logger.info(f"    {mtype}: {count}")
            if 'lt_measurement_type' in df.columns:
                lt_types = df[df['lt_measurement_type'].notna()]['lt_measurement_type'].value_counts().head(10)
                if not lt_types.empty:
                    logger.info("  From lab tests:")
                    for mtype, count in lt_types.items():
                        logger.info(f"    {mtype}: {count}")
            
            # Status breakdown - check both sources
            logger.info("\nMeasurement Status:")
            if 'obs_status' in df.columns:
                obs_status = df[df['obs_status'].notna()]['obs_status'].value_counts()
                if not obs_status.empty:
                    logger.info("  From observations:")
                    for status, count in obs_status.items():
                        logger.info(f"    {status}: {count}")
            if 'lt_status' in df.columns:
                lt_status = df[df['lt_status'].notna()]['lt_status'].value_counts()
                if not lt_status.empty:
                    logger.info("  From lab tests:")
                    for status, count in lt_status.items():
                        logger.info(f"    {status}: {count}")
            
            # Date range
            if 'measurement_date' in df.columns:
                measurement_dates = pd.to_datetime(df['measurement_date'], errors='coerce').dropna()
                if len(measurement_dates) > 0:
                    logger.info(f"\nTemporal Coverage:")
                    logger.info(f"  First measurement: {measurement_dates.min()}")
                    logger.info(f"  Last measurement: {measurement_dates.max()}")
                    logger.info(f"  Span: {(measurement_dates.max() - measurement_dates.min()).days} days")
            
            # Age range
            if 'age_at_measurement_years' in df.columns:
                ages = df['age_at_measurement_years'].dropna()
                if len(ages) > 0:
                    logger.info(f"\nAge at Measurement:")
                    logger.info(f"  Min: {ages.min():.1f} years")
                    logger.info(f"  Max: {ages.max():.1f} years")
                    logger.info(f"  Mean: {ages.mean():.1f} years")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Output saved to: {self.output_dir}/measurements.csv")
        logger.info(f"{'='*80}\n")


def main():
    """Main execution"""
    start_time = datetime.now()
    
    # Load patient configuration
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    logger.info("Starting measurements metadata extraction...")
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize extractor
    extractor = MeasurementsExtractor(patient_config=config)
    
    # Ensure output directory exists
    extractor.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract anthropometric observations
    observations_df = extractor.extract_anthropometric_observations()
    
    # Extract lab tests
    lab_tests_df = extractor.extract_lab_tests()
    
    # Extract lab test results
    lab_results_df = extractor.extract_lab_test_results()
    
    if observations_df.empty and lab_tests_df.empty:
        logger.error("No measurements found! Exiting.")
        return 1
    
    # Merge all data
    final_df = extractor.merge_all_data(observations_df, lab_tests_df, lab_results_df)
    
    if final_df.empty:
        logger.error("No data after merging! Exiting.")
        return 1
    
    # Save to CSV
    output_file = extractor.output_dir / 'measurements.csv'
    final_df.to_csv(output_file, index=False)
    logger.info(f"\n✅ Saved {len(final_df)} measurements to {output_file}")
    
    # Generate summary
    extractor.generate_summary(final_df)
    
    # Execution time
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Total execution time: {duration:.1f} seconds")
    
    return 0


if __name__ == '__main__':
    exit(main())
