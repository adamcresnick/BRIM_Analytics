#!/usr/bin/env python3
"""
Extract Structured Clinical Data from Athena Materialized Views

This script queries specific fields from FHIR resources to pre-populate
ground truth data for BRIM CSV generation.

Database Strategy:
- fhir_v2_prd_db: condition, procedure, medication_request, observation, encounter
- fhir_v1_prd_db: document_reference (v2 incomplete for documents)

Output: structured_data_{patient_id}.json with pre-populated fields:
- diagnosis_date (from condition.onset_date_time)
- surgeries (from procedure.performed_date_time with CPT codes)
- molecular_markers (from observation.value_string)
- treatment_dates (from medication_request.authored_on)

Usage:
    python scripts/extract_structured_data.py \
        --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
        --output pilot_output/structured_data.json
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import boto3
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StructuredDataExtractor:
    """Extract structured clinical data from Athena FHIR databases"""
    
    def __init__(
        self,
        aws_profile: str = '343218191717_AWSAdministratorAccess',
        v2_database: str = 'fhir_v2_prd_db',
        v1_database: str = 'fhir_v1_prd_db',
        s3_output_location: str = 's3://aws-athena-query-results-343218191717-us-east-1/'
    ):
        """
        Initialize extractor with dual database access.
        
        Args:
            aws_profile: AWS profile for authentication
            v2_database: Database for condition, procedure, medication, observation (complete)
            v1_database: Database for document_reference (v2 incomplete)
            s3_output_location: S3 location for Athena query results
        """
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena_client = self.session.client('athena', region_name='us-east-1')
        self.s3_client = self.session.client('s3', region_name='us-east-1')
        self.v2_database = v2_database
        self.v1_database = v1_database
        self.s3_output_location = s3_output_location
        
        logger.info(f"Initialized with v2_db={v2_database}, v1_db={v1_database}")
    
    def query_and_fetch(self, query: str, database: str) -> pd.DataFrame:
        """Execute Athena query and return results as DataFrame"""
        logger.info(f"Executing query on {database}:\n{query[:200]}...")
        
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': self.s3_output_location}
        )
        
        query_execution_id = response['QueryExecutionId']
        
        # Wait for query to complete
        while True:
            response = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            status = response['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise RuntimeError(f"Query {status}: {reason}")
            
            time.sleep(2)
        
        # Fetch results
        results = self.athena_client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=1000
        )
        
        # Parse into DataFrame
        columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        rows = []
        for row in results['ResultSet']['Rows'][1:]:  # Skip header
            rows.append([field.get('VarCharValue', None) for field in row['Data']])
        
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Query returned {len(df)} rows")
        
        return df
    
    def extract_diagnosis_date(self, patient_fhir_id: str) -> Optional[str]:
        """Extract diagnosis date from condition.onset_date_time"""
        
        query = f"""
        SELECT 
            onset_date_time,
            code_text,
            clinical_status,
            verification_status
        FROM {self.v2_database}.condition
        WHERE subject_reference = 'Patient/{patient_fhir_id}'
            AND (
                LOWER(code_text) LIKE '%astrocytoma%'
                OR LOWER(code_text) LIKE '%glioma%'
                OR LOWER(code_text) LIKE '%brain%'
            )
            AND verification_status = 'confirmed'
        ORDER BY onset_date_time
        LIMIT 1
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        if not df.empty and df.iloc[0]['onset_date_time']:
            diagnosis_date = df.iloc[0]['onset_date_time']
            logger.info(f"✅ Found diagnosis date: {diagnosis_date}")
            return diagnosis_date
        
        logger.warning("⚠️  No diagnosis date found")
        return None
    
    def extract_surgeries(self, patient_fhir_id: str) -> List[Dict]:
        """Extract surgery dates and details from procedure table"""
        
        query = f"""
        SELECT 
            p.id as procedure_id,
            p.performed_date_time,
            p.code_text,
            p.status,
            pcc.code_coding_code as cpt_code,
            pcc.code_coding_display as cpt_display
        FROM {self.v2_database}.procedure p
        LEFT JOIN {self.v2_database}.procedure_code_coding pcc 
            ON p.id = pcc.procedure_id
        WHERE p.subject_reference = 'Patient/{patient_fhir_id}'
            AND p.status = 'completed'
            AND (
                pcc.code_coding_code IN ('61510', '61512', '61518', '61520', '61521', '61526')
                OR LOWER(p.code_text) LIKE '%craniotomy%'
                OR LOWER(p.code_text) LIKE '%resection%'
            )
        ORDER BY p.performed_date_time
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        surgeries = []
        for _, row in df.iterrows():
            surgeries.append({
                'date': row['performed_date_time'],
                'cpt_code': row['cpt_code'],
                'cpt_display': row['cpt_display'],
                'description': row['code_text']
            })
        
        logger.info(f"✅ Found {len(surgeries)} surgeries")
        return surgeries
    
    def extract_molecular_markers(self, patient_fhir_id: str) -> Dict[str, str]:
        """Extract molecular markers from observation.value_string"""
        
        query = f"""
        SELECT 
            code_text,
            value_string,
            effective_datetime
        FROM {self.v2_database}.observation
        WHERE subject_reference = 'Patient/{patient_fhir_id}'
            AND code_text = 'Genomics Interpretation'
            AND value_string IS NOT NULL
        ORDER BY effective_datetime DESC
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        markers = {}
        for _, row in df.iterrows():
            value_string = row['value_string']
            
            # Parse common markers
            if 'BRAF' in value_string.upper():
                markers['BRAF'] = value_string
            if 'IDH' in value_string.upper():
                markers['IDH1'] = value_string
            if 'MGMT' in value_string.upper():
                markers['MGMT'] = value_string
            if 'EGFR' in value_string.upper():
                markers['EGFR'] = value_string
        
        logger.info(f"✅ Found {len(markers)} molecular markers")
        return markers
    
    def extract_treatment_start_dates(self, patient_fhir_id: str) -> List[Dict]:
        """Extract treatment start dates from medication_request"""
        
        query = f"""
        SELECT 
            medication_codeable_concept_text as medication,
            authored_on as start_date,
            status,
            intent
        FROM {self.v2_database}.medication_request
        WHERE subject_reference = 'Patient/{patient_fhir_id}'
            AND status IN ('active', 'completed')
            AND intent = 'order'
            AND (
                LOWER(medication_codeable_concept_text) LIKE '%temozolomide%'
                OR LOWER(medication_codeable_concept_text) LIKE '%radiation%'
                OR LOWER(medication_codeable_concept_text) LIKE '%bevacizumab%'
            )
        ORDER BY authored_on
        """
        
        df = self.query_and_fetch(query, self.v2_database)
        
        treatments = []
        for _, row in df.iterrows():
            treatments.append({
                'medication': row['medication'],
                'start_date': row['start_date'],
                'status': row['status']
            })
        
        logger.info(f"✅ Found {len(treatments)} treatment records")
        return treatments
    
    def extract_all(self, patient_fhir_id: str) -> Dict:
        """Extract all structured data for a patient"""
        
        logger.info(f"\n{'='*70}")
        logger.info(f"EXTRACTING STRUCTURED DATA FOR PATIENT: {patient_fhir_id}")
        logger.info(f"{'='*70}\n")
        
        structured_data = {
            'patient_fhir_id': patient_fhir_id,
            'extraction_timestamp': datetime.now().isoformat(),
            'diagnosis_date': self.extract_diagnosis_date(patient_fhir_id),
            'surgeries': self.extract_surgeries(patient_fhir_id),
            'molecular_markers': self.extract_molecular_markers(patient_fhir_id),
            'treatments': self.extract_treatment_start_dates(patient_fhir_id)
        }
        
        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("EXTRACTION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Diagnosis Date: {structured_data['diagnosis_date']}")
        logger.info(f"Surgeries: {len(structured_data['surgeries'])}")
        logger.info(f"Molecular Markers: {len(structured_data['molecular_markers'])}")
        logger.info(f"Treatment Records: {len(structured_data['treatments'])}")
        logger.info(f"{'='*70}\n")
        
        return structured_data


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description='Extract structured clinical data from Athena FHIR databases'
    )
    parser.add_argument(
        '--patient-fhir-id',
        required=True,
        help='Patient FHIR ID (e.g., e4BwD8ZYDBccepXcJ.Ilo3w3)'
    )
    parser.add_argument(
        '--output',
        default='./pilot_output/structured_data.json',
        help='Output JSON file path (default: pilot_output/structured_data.json)'
    )
    parser.add_argument(
        '--aws-profile',
        default='343218191717_AWSAdministratorAccess',
        help='AWS profile name'
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract structured data
    extractor = StructuredDataExtractor(aws_profile=args.aws_profile)
    structured_data = extractor.extract_all(args.patient_fhir_id)
    
    # Save to file
    with open(output_path, 'w') as f:
        json.dump(structured_data, f, indent=2)
    
    logger.info(f"\n✅ Structured data saved to: {output_path}")
    
    # Show sample
    logger.info("\nSample output:")
    logger.info(json.dumps(structured_data, indent=2)[:500] + "...")


if __name__ == '__main__':
    main()
