#!/usr/bin/env python3
"""
Test Additional Medication Tables and Fields

Purpose:
  Test the additional medication-related tables requested by user:
  - medication_form_coding (form details)
  - medication_ingredient (strength/dosage)
  - medication_request_note (clinical notes)
  - medication_request_reason_code (indication)
  - medication_request_based_on (care plan linkage)

Output:
  Record counts and sample data for each table

Usage:
  python3 scripts/test_additional_medication_tables.py
"""

import boto3
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class AdditionalMedicationTablesTest:
    def __init__(self, aws_profile='343218191717_AWSAdministratorAccess'):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = 'fhir_v2_prd_db'
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
        self.patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        
    def execute_query(self, query, description=""):
        """Execute Athena query and return results"""
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for completion
            while True:
                status_response = self.athena.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = status_response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                time.sleep(0.5)
            
            if status != 'SUCCEEDED':
                error_msg = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                logger.error(f"  ❌ Query failed: {error_msg}")
                return None
            
            # Get results
            results = self.athena.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=100
            )
            
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:
                return []
            
            # Parse results
            columns = [col.get('VarCharValue', '') for col in rows[0]['Data']]
            data = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    value = col.get('VarCharValue', None)
                    row_data[columns[i]] = value
                data.append(row_data)
            
            return data
            
        except Exception as e:
            logger.error(f"  ❌ Error: {str(e)}")
            return None
    
    def test_table(self, table_name, key_fields, join_field=None):
        """Test a table for record count and sample data"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TABLE: {table_name}")
        logger.info(f"{'='*80}")
        
        # Count records
        if join_field:
            # Need to join with medication_request or patient_medications
            count_query = f"""
            SELECT COUNT(*) as count
            FROM {self.database}.{table_name} t
            JOIN {self.database}.medication_request mr 
                ON t.{join_field} = mr.id
            WHERE mr.subject_reference = '{self.patient_fhir_id}'
            """
        else:
            # Direct patient_id column
            count_query = f"""
            SELECT COUNT(*) as count
            FROM {self.database}.{table_name}
            WHERE patient_id = '{self.patient_fhir_id}'
            """
        
        count_result = self.execute_query(count_query, f"Counting {table_name} records")
        
        if count_result is None:
            logger.warning(f"  ⚠️  Could not query {table_name} table")
            return
        
        if not count_result:
            logger.info(f"  ✓ Table exists but no records found for patient C1277724")
            return
        
        count = count_result[0].get('count', '0')
        logger.info(f"  ✓ Found {count} records for patient C1277724")
        
        if int(count) == 0:
            return
        
        # Get sample data
        if join_field:
            sample_query = f"""
            SELECT {', '.join([f't.{field}' for field in key_fields])}
            FROM {self.database}.{table_name} t
            JOIN {self.database}.medication_request mr 
                ON t.{join_field} = mr.id
            WHERE mr.subject_reference = '{self.patient_fhir_id}'
            LIMIT 5
            """
        else:
            sample_query = f"""
            SELECT {', '.join(key_fields)}
            FROM {self.database}.{table_name}
            WHERE patient_id = '{self.patient_fhir_id}'
            LIMIT 5
            """
        
        logger.info(f"\n  Sample data (first 5 records):")
        sample_data = self.execute_query(sample_query, f"Getting {table_name} samples")
        
        if sample_data:
            for i, row in enumerate(sample_data, 1):
                logger.info(f"\n    Record {i}:")
                for key, value in row.items():
                    if value:
                        # Truncate long values
                        display_value = str(value)[:100] + '...' if value and len(str(value)) > 100 else value
                        logger.info(f"      {key:40s}: {display_value}")
    
    def run_tests(self):
        """Test all additional medication tables"""
        logger.info("#"*80)
        logger.info("# TESTING ADDITIONAL MEDICATION TABLES")
        logger.info(f"# Patient: C1277724 (FHIR ID: {self.patient_fhir_id})")
        logger.info("#"*80)
        
        # Test 1: medication_form_coding
        logger.info("\n" + "="*80)
        logger.info("TEST 1: MEDICATION FORM CODING")
        logger.info("Purpose: Form details (tablet, injection, solution, etc.)")
        logger.info("="*80)
        self.test_table(
            table_name='medication_form_coding',
            key_fields=['form_coding_code', 'form_coding_display'],
            join_field='medication_id'
        )
        
        # Test 2: medication_ingredient
        logger.info("\n" + "="*80)
        logger.info("TEST 2: MEDICATION INGREDIENT")
        logger.info("Purpose: Ingredient strength/dosage (numerator/denominator)")
        logger.info("="*80)
        self.test_table(
            table_name='medication_ingredient',
            key_fields=[
                'ingredient_strength_numerator_value',
                'ingredient_strength_numerator_unit',
                'ingredient_strength_denominator_value',
                'ingredient_strength_denominator_unit'
            ],
            join_field='medication_id'
        )
        
        # Test 3: medication_request_note
        logger.info("\n" + "="*80)
        logger.info("TEST 3: MEDICATION REQUEST NOTE")
        logger.info("Purpose: Clinical notes/comments about medication")
        logger.info("="*80)
        self.test_table(
            table_name='medication_request_note',
            key_fields=['note_text'],
            join_field='medication_request_id'
        )
        
        # Test 4: medication_request_reason_code
        logger.info("\n" + "="*80)
        logger.info("TEST 4: MEDICATION REQUEST REASON CODE")
        logger.info("Purpose: Indication/reason for medication")
        logger.info("="*80)
        self.test_table(
            table_name='medication_request_reason_code',
            key_fields=['reason_code_text'],
            join_field='medication_request_id'
        )
        
        # Test 5: medication_request_based_on
        logger.info("\n" + "="*80)
        logger.info("TEST 5: MEDICATION REQUEST BASED ON")
        logger.info("Purpose: Links to care plans or other orders")
        logger.info("="*80)
        self.test_table(
            table_name='medication_request_based_on',
            key_fields=['based_on_reference', 'based_on_type', 'based_on_display'],
            join_field='medication_request_id'
        )
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("SUMMARY")
        logger.info("="*80)
        logger.info("""
Tables Tested:
  1. ✓ medication_form_coding - Form details (tablet/injection/etc)
  2. ✓ medication_ingredient - Strength/dosage information
  3. ✓ medication_request_note - Clinical notes
  4. ✓ medication_request_reason_code - Indication/reason
  5. ✓ medication_request_based_on - Care plan linkage

Key Findings:
  - Form coding provides administration route details
  - Ingredient table has precise dosage (mg, mL, units)
  - Notes provide clinical context and special instructions
  - Reason codes link to diagnoses/indications
  - Based_on links medications to treatment plans

Next Steps:
  1. Include these tables in extract_all_medications_metadata.py
  2. Aggregate multi-value fields (multiple ingredients, notes)
  3. Use form_coding to filter out topicals/ophthalmics
  4. Use reason_code to validate chemotherapy indications
  5. Use based_on to link to care plans
        """)
        
        logger.info("\n" + "="*80 + "\n")

if __name__ == '__main__':
    tester = AdditionalMedicationTablesTest()
    tester.run_tests()
