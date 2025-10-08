#!/usr/bin/env python3
"""
Extract Molecular Tests Data from Athena

Purpose:
  Comprehensively extract all molecular test information from Athena tables:
  - molecular_tests: Test metadata (who, what, when)
  - molecular_test_results: Test result components and narratives
  
Output CSVs:
  1. molecular_tests_metadata.csv: Test-level information (100% structured)
  2. molecular_results_for_brim.csv: Narratives for BRIM processing
  
Usage:
  # Single patient
  python3 scripts/extract_molecular_tests.py \
    --patient-ids e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --output-dir outputs/molecular/
  
  # Multiple patients
  python3 scripts/extract_molecular_tests.py \
    --patient-ids-file patient_list.txt \
    --output-dir outputs/molecular/

Security:
  - No MRN in queries or output
  - PHI-protected narrative handling
  - Background execution safe
"""

import argparse
import boto3
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
import time
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MolecularTestsExtractor:
    """Extract comprehensive molecular test data from Athena"""
    
    # Map Athena test names to standard assay nomenclature
    ASSAY_MAPPINGS = {
        'Comprehensive Solid Tumor Panel': 'WGS',
        'Comprehensive Solid Tumor Panel T/N Pair': 'WGS',
        'Tumor Panel Normal Paired': 'WGS',
        'Solid Tumor Panel': 'WGS',
        'Foundation Medicine': 'Targeted Panel',
        'Caris': 'Targeted Panel',
        'Tempus': 'WGS',
        'RNA Sequencing': 'RNA-Seq',
        'Whole Exome': 'WES',
    }
    
    def __init__(self, aws_profile: str, database: str):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena_client = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
    
    def execute_query(self, query: str, description: str) -> list:
        """Execute Athena query and return results as list of dicts"""
        logger.info(f"Executing: {description}")
        
        try:
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for completion
            while True:
                status_response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = status_response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                time.sleep(1)
            
            if status != 'SUCCEEDED':
                error_msg = status_response['QueryExecution']['Status'].get(
                    'StateChangeReason', 'Unknown error'
                )
                logger.error(f"Query failed: {error_msg}")
                return []
            
            # Get results
            results = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=1000
            )
            
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:
                logger.warning(f"No data rows for: {description}")
                return []
            
            # Parse results
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            data = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    value = col.get('VarCharValue', None)
                    row_data[columns[i]] = value
                data.append(row_data)
            
            logger.info(f"  ✓ Retrieved {len(data)} rows")
            return data
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return []
    
    def get_patient_birth_dates(self, patient_ids: list) -> dict:
        """Get birth dates for age calculations"""
        if not patient_ids:
            return {}
        
        patient_list = "', '".join(patient_ids)
        query = f"""
        SELECT id, birth_date
        FROM {self.database}.patient_access
        WHERE id IN ('{patient_list}')
        """
        
        results = self.execute_query(query, f"Get birth dates for {len(patient_ids)} patients")
        return {r['id']: r['birth_date'] for r in results if r.get('birth_date')}
    
    def map_to_standard_assay(self, lab_test_name: str) -> str:
        """Map Athena test name to standard assay nomenclature"""
        if not lab_test_name:
            return 'Unknown'
        
        # Check exact matches first
        for athena_name, standard_name in self.ASSAY_MAPPINGS.items():
            if athena_name.lower() in lab_test_name.lower():
                return standard_name
        
        # Check for common keywords
        lab_test_lower = lab_test_name.lower()
        if 'rna' in lab_test_lower or 'transcriptome' in lab_test_lower:
            return 'RNA-Seq'
        elif 'exome' in lab_test_lower:
            return 'WES'
        elif 'panel' in lab_test_lower or 'solid tumor' in lab_test_lower:
            return 'Targeted Panel'
        elif 'genome' in lab_test_lower or 'wgs' in lab_test_lower:
            return 'WGS'
        
        return 'Other'
    
    def infer_assay_type(self, lab_test_requester: str) -> str:
        """Infer if test is research or clinical based on requester"""
        if not lab_test_requester:
            return 'Unknown'
        
        requester_lower = lab_test_requester.lower()
        
        # Research indicators
        research_keywords = ['research', 'study', 'protocol', 'cbtn', 'cavatica']
        if any(kw in requester_lower for kw in research_keywords):
            return 'research'
        
        # Clinical indicators (default)
        return 'clinical'
    
    def extract_molecular_tests_for_patient(self, patient_fhir_id: str, birth_date: str) -> dict:
        """Extract all molecular test data for a single patient"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"PATIENT: {patient_fhir_id}")
        logger.info(f"{'='*60}")
        
        # Query molecular_tests with results (PHI PROTECTED - no MRN)
        query = f"""
        SELECT 
            mt.patient_id,
            mt.test_id,
            mt.result_datetime,
            mt.lab_test_name,
            mt.lab_test_status,
            mt.lab_test_requester,
            mtr.test_component,
            LENGTH(mtr.test_result_narrative) as narrative_length
        FROM {self.database}.molecular_tests mt
        LEFT JOIN {self.database}.molecular_test_results mtr 
            ON mt.test_id = mtr.test_id
        WHERE mt.patient_id = '{patient_fhir_id}'
        ORDER BY mt.result_datetime, mt.test_id
        """
        
        results = self.execute_query(query, "Query molecular tests with results")
        
        if not results:
            logger.warning(f"No molecular tests found for {patient_fhir_id}")
            return {'tests': [], 'narratives': []}
        
        logger.info(f"Found {len(results)} test result entries")
        
        # Parse birth date for age calculation
        birth_datetime = None
        if birth_date:
            try:
                birth_datetime = datetime.strptime(birth_date, '%Y-%m-%d')
            except:
                logger.warning(f"Invalid birth date format: {birth_date}")
        
        # Group by test_id
        tests_by_id = {}
        narrative_entries = []
        
        for row in results:
            test_id = row['test_id']
            
            if test_id not in tests_by_id:
                # Calculate age at test
                age_at_test_days = None
                if birth_datetime and row.get('result_datetime'):
                    try:
                        test_date = datetime.strptime(row['result_datetime'][:10], '%Y-%m-%d')
                        age_at_test_days = (test_date - birth_datetime).days
                    except:
                        pass
                
                # Map to standard assay
                standard_assay = self.map_to_standard_assay(row.get('lab_test_name', ''))
                assay_type = self.infer_assay_type(row.get('lab_test_requester', ''))
                
                tests_by_id[test_id] = {
                    'patient_fhir_id': patient_fhir_id,
                    'test_id': test_id,
                    'test_date': row.get('result_datetime', '')[:10] if row.get('result_datetime') else '',
                    'age_at_test_days': age_at_test_days,
                    'lab_test_name': row.get('lab_test_name', ''),
                    'standard_assay': standard_assay,
                    'assay_type': assay_type,
                    'test_status': row.get('lab_test_status', ''),
                    'test_requester': row.get('lab_test_requester', ''),
                    'component_count': 0,
                    'total_narrative_chars': 0,
                    'components': []
                }
            
            # Add component info
            if row.get('test_component'):
                tests_by_id[test_id]['components'].append(row['test_component'])
                tests_by_id[test_id]['component_count'] += 1
                
                # Track narrative length
                narrative_len = int(row.get('narrative_length', 0) or 0)
                tests_by_id[test_id]['total_narrative_chars'] += narrative_len
                
                # Store narrative metadata for BRIM
                if narrative_len > 0:
                    narrative_entries.append({
                        'patient_fhir_id': patient_fhir_id,
                        'test_id': test_id,
                        'test_date': tests_by_id[test_id]['test_date'],
                        'test_component': row['test_component'],
                        'narrative_length': narrative_len,
                        'requires_brim': 'Yes' if narrative_len > 100 else 'No'
                    })
        
        # Convert to list and add component summary
        tests = []
        for test_data in tests_by_id.values():
            test_data['components_list'] = '; '.join(test_data['components']) if test_data['components'] else 'None'
            del test_data['components']
            tests.append(test_data)
        
        logger.info(f"✓ Extracted {len(tests)} unique molecular tests")
        logger.info(f"✓ Found {len(narrative_entries)} narrative components for BRIM")
        
        return {
            'tests': tests,
            'narratives': narrative_entries
        }
    
    def extract_batch(self, patient_ids: list, output_dir: str):
        """Extract molecular tests for batch of patients"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"MOLECULAR TESTS EXTRACTION: {len(patient_ids)} patients")
        logger.info(f"{'='*60}\n")
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get birth dates
        logger.info("Step 1: Retrieving patient birth dates...")
        birth_dates = self.get_patient_birth_dates(patient_ids)
        logger.info(f"  ✓ Retrieved {len(birth_dates)} birth dates\n")
        
        # Extract for each patient
        all_tests = []
        all_narratives = []
        
        for patient_id in patient_ids:
            birth_date = birth_dates.get(patient_id, '')
            if not birth_date:
                logger.warning(f"No birth date found for {patient_id}, skipping")
                continue
            
            result = self.extract_molecular_tests_for_patient(patient_id, birth_date)
            all_tests.extend(result['tests'])
            all_narratives.extend(result['narratives'])
        
        # Create DataFrames
        tests_df = pd.DataFrame(all_tests) if all_tests else pd.DataFrame()
        narratives_df = pd.DataFrame(all_narratives) if all_narratives else pd.DataFrame()
        
        # Save outputs
        tests_output = Path(output_dir) / 'molecular_tests_metadata.csv'
        narratives_output = Path(output_dir) / 'molecular_narratives_for_brim.csv'
        
        logger.info(f"\n{'='*60}")
        logger.info(f"EXTRACTION COMPLETE")
        logger.info(f"{'='*60}")
        
        if not tests_df.empty:
            tests_df.to_csv(tests_output, index=False)
            logger.info(f"✓ Test metadata saved: {tests_output}")
            logger.info(f"  Rows: {len(tests_df)}, Columns: {len(tests_df.columns)}")
            logger.info(f"  Unique patients: {tests_df['patient_fhir_id'].nunique()}")
            logger.info(f"  Tests by assay:")
            for assay, count in tests_df['standard_assay'].value_counts().items():
                logger.info(f"    {assay}: {count}")
        else:
            logger.warning("No molecular tests found")
        
        if not narratives_df.empty:
            narratives_df.to_csv(narratives_output, index=False)
            logger.info(f"\n✓ BRIM narratives saved: {narratives_output}")
            logger.info(f"  Rows: {len(narratives_df)}, Columns: {len(narratives_df.columns)}")
            logger.info(f"  Total narrative characters: {narratives_df['narrative_length'].sum():,}")
            logger.info(f"  Narratives requiring BRIM: {(narratives_df['requires_brim'] == 'Yes').sum()}")
        
        return tests_df, narratives_df


def main():
    parser = argparse.ArgumentParser(
        description='Extract comprehensive molecular tests data from Athena'
    )
    parser.add_argument('--patient-ids', nargs='+',
                       help='List of patient FHIR IDs')
    parser.add_argument('--patient-ids-file',
                       help='File containing patient FHIR IDs (one per line)')
    parser.add_argument('--output-dir', required=True,
                       help='Output directory for CSV files')
    parser.add_argument('--aws-profile', default='343218191717_AWSAdministratorAccess',
                       help='AWS profile name')
    parser.add_argument('--database', default='fhir_v2_prd_db',
                       help='Athena database name')
    
    args = parser.parse_args()
    
    # Get patient IDs
    patient_ids = []
    if args.patient_ids:
        patient_ids = args.patient_ids
    elif args.patient_ids_file:
        with open(args.patient_ids_file, 'r') as f:
            patient_ids = [line.strip() for line in f if line.strip()]
    else:
        print("Error: Must provide --patient-ids or --patient-ids-file")
        sys.exit(1)
    
    logger.info(f"Extracting molecular tests for {len(patient_ids)} patients")
    
    # Extract
    extractor = MolecularTestsExtractor(args.aws_profile, args.database)
    extractor.extract_batch(patient_ids, args.output_dir)


if __name__ == '__main__':
    main()
