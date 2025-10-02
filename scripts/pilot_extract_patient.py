#!/usr/bin/env python3
"""
PILOT: Extract FHIR Bundle for Patient e4BwD8ZYDBccepXcJ.Ilo3w3
Combines raw FHIR resources from Athena with clinical notes from S3
"""

import os
import sys
import json
import boto3
import base64
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from pyathena import connect
from pyathena.pandas.cursor import PandasCursor

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()

class PatientFHIRExtractor:
    """Extract complete FHIR Bundle for a patient from raw Athena tables."""
    
    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.aws_profile = os.getenv('AWS_PROFILE')
        self.athena_db = os.getenv('ATHENA_DATABASE')
        self.s3_staging = os.getenv('ATHENA_S3_STAGING')
        self.s3_bucket = os.getenv('S3_NDJSON_BUCKET')
        self.s3_prefix = os.getenv('S3_NDJSON_PREFIX')
        self.binary_links_path = os.getenv('S3_BINARY_LINKS')
        
        # Initialize AWS session (force fresh credentials)
        import botocore.session
        botocore_session = botocore.session.get_session()
        botocore_session.get_credentials()
        
        self.session = boto3.Session(profile_name=self.aws_profile)
        self.s3_client = self.session.client('s3', region_name='us-east-1')
        
        # Initialize Athena connection
        self.conn = connect(
            s3_staging_dir=self.s3_staging,
            region_name='us-east-1',
            cursor_class=PandasCursor,
            profile_name=self.aws_profile
        )
        
        # Load binary links
        self.binary_links = self._load_binary_links()
        
    def _load_binary_links(self):
        """Load binary resource download links from S3."""
        print(f"📥 Loading binary links from {self.binary_links_path}")
        try:
            bucket, key = self.binary_links_path.replace('s3://', '').split('/', 1)
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            links = json.loads(response['Body'].read())
            print(f"✅ Loaded {len(links)} binary links")
            return links
        except Exception as e:
            print(f"⚠️  Could not load binary links: {e}")
            return {}
    
    def query_athena(self, sql):
        """Execute Athena query and return DataFrame."""
        print(f"🔍 Querying: {sql[:100]}...")
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            df = cursor.as_pandas()
            print(f"✅ Retrieved {len(df)} rows")
            return df
        except Exception as e:
            print(f"❌ Query failed: {e}")
            return pd.DataFrame()
    
    def extract_patient(self):
        """Extract Patient resource."""
        print(f"\n🧑 Extracting Patient: {self.patient_id}")
        
        sql = f"""
        SELECT 
            id,
            identifier,
            name,
            birthDate,
            gender,
            deceasedBoolean,
            deceasedDateTime,
            address,
            telecom
        FROM {self.athena_db}.patient
        WHERE id = '{self.patient_id}'
        """
        
        df = self.query_athena(sql)
        if df.empty:
            print("❌ Patient not found!")
            return None
        
        # Convert to FHIR resource (Athena returns nested structures as JSON strings)
        patient_data = df.iloc[0].to_dict()
        
        # Parse JSON strings back to objects
        for field in ['identifier', 'name', 'address', 'telecom']:
            if field in patient_data and patient_data[field]:
                try:
                    patient_data[field] = json.loads(patient_data[field])
                except:
                    pass
        
        resource = {
            "resourceType": "Patient",
            **{k: v for k, v in patient_data.items() if v is not None and v != ''}
        }
        
        print(f"✅ Patient: {patient_data.get('gender')}, DOB: {patient_data.get('birthDate')}")
        return resource
    
    def extract_conditions(self):
        """Extract Condition resources (diagnoses)."""
        print(f"\n🔬 Extracting Conditions")
        
        sql = f"""
        SELECT 
            id,
            clinicalStatus,
            verificationStatus,
            category,
            severity,
            code,
            bodySite,
            subject,
            onsetDateTime,
            recordedDate,
            note
        FROM {self.athena_db}.condition
        WHERE subject.reference LIKE '%{self.patient_id}%'
        ORDER BY recordedDate DESC
        """
        
        df = self.query_athena(sql)
        conditions = []
        
        for idx, row in df.iterrows():
            resource = {"resourceType": "Condition"}
            for col, val in row.items():
                if val is not None and val != '':
                    # Parse nested JSON structures
                    if col in ['code', 'bodySite', 'category', 'clinicalStatus', 'verificationStatus']:
                        try:
                            resource[col] = json.loads(val) if isinstance(val, str) else val
                        except:
                            resource[col] = val
                    else:
                        resource[col] = val
            
            conditions.append(resource)
        
        print(f"✅ Found {len(conditions)} conditions")
        return conditions
    
    def extract_procedures(self):
        """Extract Procedure resources (surgeries)."""
        print(f"\n⚕️  Extracting Procedures")
        
        sql = f"""
        SELECT 
            id,
            status,
            code,
            subject,
            performedDateTime,
            performedPeriod,
            bodySite,
            performer,
            reasonCode,
            note
        FROM {self.athena_db}.procedure
        WHERE subject.reference LIKE '%{self.patient_id}%'
        ORDER BY performedDateTime DESC
        """
        
        df = self.query_athena(sql)
        procedures = []
        
        for idx, row in df.iterrows():
            resource = {"resourceType": "Procedure"}
            for col, val in row.items():
                if val is not None and val != '':
                    # Parse nested structures
                    if col in ['code', 'bodySite', 'performer', 'reasonCode', 'performedPeriod']:
                        try:
                            resource[col] = json.loads(val) if isinstance(val, str) else val
                        except:
                            resource[col] = val
                    else:
                        resource[col] = val
            
            procedures.append(resource)
        
        print(f"✅ Found {len(procedures)} procedures")
        return procedures
    
    def extract_medication_requests(self):
        """Extract MedicationRequest resources."""
        print(f"\n💊 Extracting MedicationRequests")
        
        sql = f"""
        SELECT 
            id,
            status,
            intent,
            medicationCodeableConcept,
            subject,
            authoredOn,
            dosageInstruction,
            note
        FROM {self.athena_db}.medicationrequest
        WHERE subject.reference LIKE '%{self.patient_id}%'
        ORDER BY authoredOn DESC
        LIMIT 100
        """
        
        df = self.query_athena(sql)
        medications = []
        
        for idx, row in df.iterrows():
            resource = {"resourceType": "MedicationRequest"}
            for col, val in row.items():
                if val is not None and val != '':
                    # Parse nested structures
                    if col in ['medicationCodeableConcept', 'dosageInstruction']:
                        try:
                            resource[col] = json.loads(val) if isinstance(val, str) else val
                        except:
                            resource[col] = val
                    else:
                        resource[col] = val
            
            medications.append(resource)
        
        print(f"✅ Found {len(medications)} medication requests")
        return medications
    
    def extract_observations(self):
        """Extract Observation resources (labs, vitals, molecular tests)."""
        print(f"\n🔬 Extracting Observations")
        
        sql = f"""
        SELECT 
            id,
            status,
            category,
            code,
            subject,
            effectiveDateTime,
            valueQuantity,
            valueString,
            interpretation,
            note
        FROM {self.athena_db}.observation
        WHERE subject.reference LIKE '%{self.patient_id}%'
        ORDER BY effectiveDateTime DESC
        LIMIT 200
        """
        
        df = self.query_athena(sql)
        observations = []
        
        for idx, row in df.iterrows():
            resource = {"resourceType": "Observation"}
            for col, val in row.items():
                if val is not None and val != '':
                    # Parse nested structures
                    if col in ['category', 'code', 'valueQuantity', 'interpretation']:
                        try:
                            resource[col] = json.loads(val) if isinstance(val, str) else val
                        except:
                            resource[col] = val
                    else:
                        resource[col] = val
            
            observations.append(resource)
        
        print(f"✅ Found {len(observations)} observations")
        return observations
    
    def extract_encounters(self):
        """Extract Encounter resources."""
        print(f"\n🏥 Extracting Encounters")
        
        sql = f"""
        SELECT 
            id,
            status,
            class,
            type,
            subject,
            period,
            reasonCode,
            hospitalization
        FROM {self.athena_db}.encounter
        WHERE subject.reference LIKE '%{self.patient_id}%'
        ORDER BY period DESC
        LIMIT 100
        """
        
        df = self.query_athena(sql)
        encounters = []
        
        for idx, row in df.iterrows():
            resource = {"resourceType": "Encounter"}
            for col, val in row.items():
                if val is not None and val != '':
                    # Parse nested structures
                    if col in ['class', 'type', 'reasonCode', 'period', 'hospitalization']:
                        try:
                            resource[col] = json.loads(val) if isinstance(val, str) else val
                        except:
                            resource[col] = val
                    else:
                        resource[col] = val
            
            encounters.append(resource)
        
        print(f"✅ Found {len(encounters)} encounters")
        return encounters
    
    def assemble_bundle(self):
        """Assemble complete FHIR Bundle."""
        print(f"\n📦 Assembling FHIR Bundle for {self.patient_id}")
        
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "entry": []
        }
        
        # Extract all resources
        patient = self.extract_patient()
        if patient:
            bundle['entry'].append({"resource": patient})
        
        conditions = self.extract_conditions()
        for condition in conditions:
            bundle['entry'].append({"resource": condition})
        
        procedures = self.extract_procedures()
        for procedure in procedures:
            bundle['entry'].append({"resource": procedure})
        
        medications = self.extract_medication_requests()
        for med in medications:
            bundle['entry'].append({"resource": med})
        
        observations = self.extract_observations()
        for obs in observations:
            bundle['entry'].append({"resource": obs})
        
        encounters = self.extract_encounters()
        for enc in encounters:
            bundle['entry'].append({"resource": enc})
        
        print(f"\n✅ Bundle complete: {len(bundle['entry'])} resources")
        return bundle
    
    def save_bundle(self, bundle, output_path):
        """Save FHIR Bundle to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(bundle, f, indent=2)
        
        print(f"💾 Saved bundle to: {output_path}")
        
        # Calculate size
        size_kb = output_path.stat().st_size / 1024
        print(f"📊 Bundle size: {size_kb:.1f} KB")
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        with open(output_path, 'r') as f:
            content = f.read()
            estimated_tokens = len(content) / 4
            print(f"🔢 Estimated tokens: {estimated_tokens:,.0f}")


def main():
    parser = argparse.ArgumentParser(description='Extract FHIR Bundle for patient')
    parser.add_argument('--patient-id', default=os.getenv('PILOT_PATIENT_ID'),
                        help='Patient ID to extract')
    parser.add_argument('--output-dir', default='./pilot_output',
                        help='Output directory for bundle JSON')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🚀 FHIR BUNDLE EXTRACTION PILOT")
    print("=" * 70)
    print(f"Patient ID: {args.patient_id}")
    print(f"Output Dir: {args.output_dir}")
    print("=" * 70)
    
    # Extract
    extractor = PatientFHIRExtractor(args.patient_id)
    bundle = extractor.assemble_bundle()
    
    # Save
    output_path = Path(args.output_dir) / f'fhir_bundle_{args.patient_id}.json'
    extractor.save_bundle(bundle, output_path)
    
    print("\n" + "=" * 70)
    print("✅ EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"1. Review bundle: {output_path}")
    print(f"2. Run: python scripts/pilot_generate_brim_csvs.py")
    print("=" * 70)


if __name__ == '__main__':
    main()
