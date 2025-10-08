#!/usr/bin/env python3
"""
Test script to verify molecular_tests and molecular_test_results queries
for patient C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)
"""

import boto3
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MolecularTestsVerifier:
    def __init__(self, aws_profile='343218191717_AWSAdministratorAccess'):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena_client = self.session.client('athena', region_name='us-east-1')
        self.database = 'fhir_v2_prd_db'
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
    
    def execute_query(self, query, description):
        """Execute Athena query and return results"""
        logger.info(f"\n{'='*60}")
        logger.info(f"QUERY: {description}")
        logger.info(f"{'='*60}")
        logger.info(f"SQL:\n{query}\n")
        
        try:
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for query to complete
            while True:
                status_response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = status_response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                time.sleep(1)
            
            if status != 'SUCCEEDED':
                error_msg = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                logger.error(f"Query failed: {error_msg}")
                return []
            
            # Get results
            results = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=100
            )
            
            # Parse results
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:
                logger.warning("No data rows returned (only header or empty)")
                return []
            
            # Get column names from first row
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            
            # Parse data rows
            data = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    value = col.get('VarCharValue', None)
                    row_data[columns[i]] = value
                data.append(row_data)
            
            logger.info(f"✓ Retrieved {len(data)} rows")
            return data
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return []
    
    def test_molecular_tests_queries(self):
        """Test both molecular_tests and molecular_test_results queries"""
        
        patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        
        print("\n" + "="*80)
        print("MOLECULAR TESTS VERIFICATION FOR PATIENT C1277724")
        print("="*80)
        
        # Query 1: molecular_tests table (NO MRN - PHI protected)
        query1 = f"""
        SELECT 
            patient_id,
            test_id,
            result_datetime,
            lab_test_name,
            lab_test_status
        FROM {self.database}.molecular_tests
        WHERE patient_id = '{patient_fhir_id}'
        ORDER BY result_datetime
        """
        
        results1 = self.execute_query(query1, "Query 1: molecular_tests table")
        
        if results1:
            print("\nMOLECULAR_TESTS RESULTS:")
            for i, row in enumerate(results1, 1):
                print(f"\nTest {i}:")
                for key, value in row.items():
                    print(f"  {key}: {value}")
        else:
            print("\n❌ MOLECULAR_TESTS: 0 ROWS RETURNED")
            print("   → Table is empty for this patient")
        
        # Query 2: molecular_tests joined with molecular_test_results (NO MRN - PHI protected)
        query2 = f"""
        SELECT 
            mt.patient_id,
            mt.test_id,
            mt.result_datetime,
            mt.lab_test_name,
            mt.lab_test_status,
            mtr.test_component,
            LENGTH(mtr.test_result_narrative) as narrative_length
        FROM {self.database}.molecular_tests mt
        LEFT JOIN {self.database}.molecular_test_results mtr 
            ON mt.test_id = mtr.test_id
        WHERE mt.patient_id = '{patient_fhir_id}'
        ORDER BY mt.result_datetime
        """
        
        results2 = self.execute_query(query2, "Query 2: molecular_tests + molecular_test_results (JOIN)")
        
        if results2:
            print("\nMOLECULAR_TESTS + MOLECULAR_TEST_RESULTS (JOINED) RESULTS:")
            for i, row in enumerate(results2, 1):
                print(f"\nTest {i} with Results:")
                for key, value in row.items():
                    # Redact narrative content, only show metadata
                    if key == 'narrative_length':
                        print(f"  {key}: {value} characters")
                    else:
                        print(f"  {key}: {value}")
        else:
            print("\n❌ JOINED QUERY: 0 ROWS RETURNED")
            print("   → No molecular test data available in either table")
        
        # Query 3: Check table structure (exclude MRN column from display)
        query3 = f"""
        SELECT patient_id, test_id, result_datetime, lab_test_name, lab_test_status
        FROM {self.database}.molecular_tests
        LIMIT 1
        """
        
        results3 = self.execute_query(query3, "Query 3: Check molecular_tests table structure")
        
        if results3:
            print("\nMOLECULAR_TESTS TABLE STRUCTURE:")
            print(f"Columns available: {list(results3[0].keys())} (MRN excluded from display)")
        else:
            print("\n⚠️ Table appears to be empty or structure check failed")
        
        # Query 4: Check molecular_test_results table (exclude MRN, redact narrative)
        query4 = f"""
        SELECT patient_id, test_id, test_component, LENGTH(test_result_narrative) as narrative_length
        FROM {self.database}.molecular_test_results
        LIMIT 1
        """
        
        results4 = self.execute_query(query4, "Query 4: Check molecular_test_results table structure")
        
        if results4:
            print("\nMOLECULAR_TEST_RESULTS TABLE STRUCTURE:")
            print(f"Columns available: {list(results4[0].keys())} (MRN excluded, narrative length only)")
        else:
            print("\n⚠️ molecular_test_results table appears to be empty")
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Patient FHIR ID: {patient_fhir_id}")
        print(f"Patient Research ID: C1277724")
        print(f"\nQUERIES EXECUTED:")
        print(f"  1. ✓ SELECT FROM molecular_tests WHERE patient_id = '{patient_fhir_id}'")
        print(f"     Result: {len(results1)} rows")
        print(f"  2. ✓ SELECT FROM molecular_tests LEFT JOIN molecular_test_results")
        print(f"     Result: {len(results2)} rows")
        print(f"  3. ✓ Check molecular_tests table structure")
        print(f"     Result: {'Found' if results3 else 'Empty'}")
        print(f"  4. ✓ Check molecular_test_results table structure")
        print(f"     Result: {'Found' if results4 else 'Empty'}")
        
        print(f"\nCONCLUSION:")
        if not results1 and not results2:
            print("  ❌ BOTH molecular_tests and molecular_test_results are EMPTY for C1277724")
            print("  → Gold standard shows 'Whole Genome Sequencing' performed")
            print("  → Data may be in alternative tables:")
            print("     • observation (with genomic LOINC codes)")
            print("     • diagnostic_report (molecular pathology)")
            print("     • procedure (genomic testing CPT codes 81xxx)")
            print("     • document_reference (pathology report narratives)")
        else:
            print("  ✓ Molecular test data found!")
            print(f"     {len(results1)} tests in molecular_tests table")
        
        print("\n" + "="*80)


if __name__ == '__main__':
    verifier = MolecularTestsVerifier()
    verifier.test_molecular_tests_queries()
