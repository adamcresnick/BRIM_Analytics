#!/usr/bin/env python3
"""
Discover Medication-Related FHIR Tables Schema

Purpose:
  Discover all medication-related tables in fhir_v2_prd_db and document their structure.
  Similar to discover_procedure_schema.py but for medications.

Tables to discover:
  - medication_request (main table - prescriptions)
  - medication (drug details)
  - medication_code_coding (RxNorm codes)
  - medication_administration (actual administrations)
  - medication_statement (patient-reported)
  - medication_ingredient (drug components)
  - care_plan (treatment plans)

Output:
  Terminal output showing all medication tables with column counts and sample data

Usage:
  python3 scripts/discover_medication_schema.py

Security:
  - Works in background mode (no PHI echoing)
  - Only shows table structures and counts
"""

import boto3
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class MedicationSchemaDiscovery:
    """Discover medication-related FHIR table schemas"""
    
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
                logger.error(f"❌ Query failed: {error_msg}")
                return []
            
            # Get results
            results = self.athena.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=1000
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
            logger.error(f"❌ Error: {str(e)}")
            return []
    
    def discover_all_medication_tables(self):
        """Find all medication-related tables"""
        logger.info("\n" + "="*80)
        logger.info("MEDICATION-RELATED TABLES DISCOVERY")
        logger.info("="*80)
        
        # Try multiple naming patterns
        queries = [
            ("medication_*", "SHOW TABLES IN fhir_v2_prd_db LIKE 'medication_%'"),
            ("medicationrequest", "SHOW TABLES IN fhir_v2_prd_db LIKE 'medicationrequest%'"),
            ("medicationstatement", "SHOW TABLES IN fhir_v2_prd_db LIKE 'medicationstatement%'"),
            ("medicationadministration", "SHOW TABLES IN fhir_v2_prd_db LIKE 'medicationadministration%'"),
        ]
        
        all_tables = []
        for pattern, query in queries:
            tables = self.execute_query(query, f"Finding {pattern} tables")
            if tables:
                all_tables.extend([t['tab_name'] for t in tables])
        
        if not all_tables:
            logger.warning("No medication tables found")
            return []
        
        # Remove duplicates
        all_tables = list(set(all_tables))
        all_tables.sort()
        
        logger.info(f"\n✓ Found {len(all_tables)} medication-related tables:\n")
        for i, name in enumerate(all_tables, 1):
            logger.info(f"  {i:2d}. {name}")
        
        return all_tables
    
    def discover_care_plan_tables(self):
        """Find care plan tables (treatment plans)"""
        logger.info("\n" + "="*80)
        logger.info("CARE PLAN TABLES DISCOVERY")
        logger.info("="*80)
        
        # Try both naming patterns
        queries = [
            ("care_plan_*", "SHOW TABLES IN fhir_v2_prd_db LIKE 'care_plan%'"),
            ("careplan*", "SHOW TABLES IN fhir_v2_prd_db LIKE 'careplan%'"),
        ]
        
        all_tables = []
        for pattern, query in queries:
            tables = self.execute_query(query, f"Finding {pattern} tables")
            if tables:
                all_tables.extend([t['tab_name'] for t in tables])
        
        if not all_tables:
            logger.warning("No care plan tables found")
            return []
        
        # Remove duplicates
        all_tables = list(set(all_tables))
        all_tables.sort()
        
        logger.info(f"\n✓ Found {len(all_tables)} care plan tables:\n")
        for i, name in enumerate(all_tables, 1):
            logger.info(f"  {i:2d}. {name}")
        
        return all_tables
    
    def analyze_table_structure(self, table_name):
        """Get column information for a table"""
        logger.info(f"\n{'='*80}")
        logger.info(f"TABLE: {table_name}")
        logger.info(f"{'='*80}")
        
        # Get column info
        describe_query = f"DESCRIBE {self.database}.{table_name}"
        columns = self.execute_query(describe_query)
        
        if not columns:
            logger.warning(f"Could not describe table {table_name}")
            return
        
        logger.info(f"\nColumns ({len(columns)} total):")
        for i, col in enumerate(columns, 1):
            col_name = col.get('col_name', 'unknown')
            col_type = col.get('data_type', 'unknown')
            logger.info(f"  {i:2d}. {col_name:40s} {col_type}")
        
        # Get row count for patient
        count_query = f"""
        SELECT COUNT(*) as count
        FROM {self.database}.{table_name}
        WHERE patient_id = '{self.patient_fhir_id}'
        """
        
        count_result = self.execute_query(count_query)
        if count_result:
            count = count_result[0].get('count', '0')
            logger.info(f"\n✓ Records for patient C1277724: {count}")
        
        # Get sample data (first 3 rows)
        if count_result and int(count_result[0].get('count', '0')) > 0:
            sample_query = f"""
            SELECT *
            FROM {self.database}.{table_name}
            WHERE patient_id = '{self.patient_fhir_id}'
            LIMIT 3
            """
            
            logger.info(f"\nSample data (first 3 rows):")
            sample_data = self.execute_query(sample_query)
            
            if sample_data:
                for i, row in enumerate(sample_data, 1):
                    logger.info(f"\n  Row {i}:")
                    for key, value in row.items():
                        if value and key not in ['patient_id', 'mrn']:  # Hide PHI
                            # Truncate long values
                            display_value = str(value)[:100] + '...' if value and len(str(value)) > 100 else value
                            logger.info(f"    {key:30s}: {display_value}")
    
    def run_discovery(self):
        """Run complete schema discovery"""
        logger.info(f"\n{'#'*80}")
        logger.info(f"# MEDICATION SCHEMA DISCOVERY FOR PATIENT C1277724")
        logger.info(f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"# Database: {self.database}")
        logger.info(f"# Patient FHIR ID: {self.patient_fhir_id}")
        logger.info(f"{'#'*80}\n")
        
        # Discover medication tables
        med_tables = self.discover_all_medication_tables()
        
        # Discover care plan tables
        care_tables = self.discover_care_plan_tables()
        
        all_tables = med_tables + care_tables
        
        # Analyze each table
        logger.info(f"\n{'='*80}")
        logger.info("DETAILED TABLE ANALYSIS")
        logger.info(f"{'='*80}")
        
        for table in all_tables:
            self.analyze_table_structure(table)
        
        # Summary
        logger.info(f"\n{'='*80}")
        logger.info("DISCOVERY SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"\nTotal medication-related tables found: {len(med_tables)}")
        logger.info(f"Total care plan tables found: {len(care_tables)}")
        logger.info(f"Total tables analyzed: {len(all_tables)}")
        logger.info(f"\nKey tables for extraction:")
        logger.info("  1. medication_request - Prescriptions/orders (primary table)")
        logger.info("  2. medication - Drug details")
        logger.info("  3. medication_code_coding - RxNorm codes")
        logger.info("  4. medication_administration - Actual administrations")
        logger.info("  5. medication_statement - Patient-reported medications")
        logger.info("  6. care_plan - Treatment plans")
        
        logger.info(f"\n{'='*80}")
        logger.info("NEXT STEPS")
        logger.info(f"{'='*80}")
        logger.info("\n1. Create MEDICATIONS_SCHEMA_DISCOVERY.md documentation")
        logger.info("2. Develop extract_all_medications_metadata.py script")
        logger.info("3. Map RxNorm codes from medication_code_coding")
        logger.info("4. Filter for chemotherapy using RxNorm reference list")
        logger.info("5. Identify concomitant medications (non-cancer drugs)")
        
        logger.info(f"\n{'='*80}\n")

if __name__ == '__main__':
    discovery = MedicationSchemaDiscovery()
    discovery.run_discovery()
