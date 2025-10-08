#!/usr/bin/env python3
"""
Validate Encounters CSV Extraction Against Gold Standard

Based on validated patterns from:
- COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md
- COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md
- extract_diagnosis.py (working extraction script)

Tables Used:
  - problem_list_diagnoses: Cancer diagnosis events
  - encounter: Patient encounters/visits
  - patient_access: Birth dates for age calculations
"""

import argparse
import boto3
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import List, Dict, Optional
import hashlib

class EncountersValidator:
    """Validate encounters extraction against gold standard"""
    
    def __init__(self, aws_profile: str, database: str):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
        
        # Patient C1277724 details
        self.patient_research_id = "C1277724"
        self.patient_fhir_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
        self.birth_date = datetime.strptime('2005-05-13', '%Y-%m-%d')
        
    def execute_query(self, query: str, description: str = "") -> List[Dict]:
        """Execute Athena query and return results"""
        print(f"  Executing: {description}...", end='', flush=True)
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Poll for completion
            max_attempts = 60
            for attempt in range(max_attempts):
                status_response = self.athena.get_query_execution(QueryExecutionId=query_execution_id)
                status = status_response['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    print(f" ✗ ({reason})")
                    return []
                
                time.sleep(1)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_execution_id)
            
            if not results.get('ResultSet', {}).get('Rows') or len(results['ResultSet']['Rows']) <= 1:
                print(f" ✓ (0 rows)")
                return []
            
            rows = results['ResultSet']['Rows']
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            
            data_rows = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    row_data[columns[i]] = col.get('VarCharValue', None)
                data_rows.append(row_data)
            
            print(f" ✓ ({len(data_rows)} rows)")
            return data_rows
            
        except Exception as e:
            print(f" ✗ ({str(e)})")
            return []
    
    def extract_encounters_from_athena(self) -> list:
        """Extract encounter data from Athena using validated patterns"""
        
        print(f"\n{'='*60}")
        print("🔍 EXTRACTING FROM ATHENA")
        print(f"{'='*60}\n")
        
        # Step 1: Get diagnosis events from SURGICAL PROCEDURES
        # Based on COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md (VALIDATED)
        # Diagnosis events = surgery dates (clinical action dates, not problem_list dates)
        print("📋 Step 1: Query surgical procedures for diagnosis events")
        surgery_query = f"""
        SELECT 
            p.id,
            p.performed_date_time,
            pcc.code_coding_code as cpt_code,
            pcc.code_coding_display as procedure_name
        FROM {self.database}.procedure p
        JOIN {self.database}.procedure_code_coding pcc 
            ON p.id = pcc.procedure_id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
            AND p.performed_date_time IS NOT NULL
            AND (
                pcc.code_coding_code IN (
                    '61500', '61501', '61510', '61512', '61514', '61516',
                    '61518', '61519', '61520', '61521', '61524', '61526',
                    '62201', '62223',
                    '61304', '61305', '61312', '61313', '61314', '61315'
                )
                OR LOWER(pcc.code_coding_display) LIKE '%craniotomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%tumor resection%'
            )
        ORDER BY p.performed_date_time
        """
        
        surgeries = self.execute_query(surgery_query, "Query surgical procedures")
        print(f"  📊 Found {len(surgeries)} surgical procedures")
        
        # Create diagnosis_dates mapping with event IDs (using surgery dates as events)
        diagnosis_dates = {}
        for surgery in surgeries:
            surgery_date = surgery.get('performed_date_time', '')[:10]
            if surgery_date:
                # Generate event ID using same pattern as gold standard
                event_hash = hashlib.md5(f"{self.patient_fhir_id}_{surgery_date}".encode()).hexdigest()[:8].upper()
                if surgery_date not in diagnosis_dates:  # Avoid duplicates from multiple CPT codes
                    diagnosis_dates[surgery_date] = {
                        'event_id': f"ET_{event_hash}",
                        'details': surgery.get('procedure_name', '')
                    }
                    print(f"  ✅ Diagnosis Event: {surgery_date} (Surgery: {surgery.get('cpt_code', 'N/A')})")
        
        print(f"  📊 Identified {len(diagnosis_dates)} diagnosis events\n")
        
        # Step 2: Query encounters 
        # Pattern from COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md (VALIDATED)
        print("📋 Step 2: Query cancer-relevant encounters")
        
        # Get first cancer diagnosis date for filtering
        first_cancer_date = None
        if diagnosis_dates:
            first_cancer_date = sorted(diagnosis_dates.keys())[0]
        
        encounter_query = f"""
        SELECT 
            id,
            subject_reference,
            period_start,
            period_end,
            status,
            class_display,
            service_type_text
        FROM {self.database}.encounter
        WHERE subject_reference LIKE '%{self.patient_fhir_id}%'
            AND period_start IS NOT NULL
            AND status IN ('finished', 'in-progress')
            AND (
                class_display IN ('Appointment', 'HOV')
                OR (class_display = 'Support OP Encounter' 
                    AND service_type_text LIKE '%oncology%')
            )
            {f"AND period_start >= '{first_cancer_date}'" if first_cancer_date else ''}
        ORDER BY period_start
        """
        
        encounters = self.execute_query(encounter_query, "Query encounters")
        print(f"  📊 Found {len(encounters)} encounters")
        if encounters:
            print(f"     {encounters[0].get('period_start', '')[:10]}: {encounters[0].get('class_display', '')}")
            print(f"     {encounters[1].get('period_start', '')[:10]}: {encounters[1].get('class_display', '')}") if len(encounters) > 1 else None
            print(f"     {encounters[2].get('period_start', '')[:10]}: {encounters[2].get('class_display', '')}") if len(encounters) > 2 else None
        print()
        
        # Step 3: Build encounter events with calculated fields
        print("📋 Step 3: Building encounter events\n")
        
        encounter_events = []
        
        for enc in encounters:
            enc_date = enc.get('period_start', '')[:10]
            if not enc_date:
                continue
            
            enc_datetime = datetime.strptime(enc_date, '%Y-%m-%d')
            
            # Calculate age at encounter
            age_at_encounter = (enc_datetime - self.birth_date).days
            
            # Link to closest prior diagnosis event
            linked_event_id = None
            orig_event_date = None
            for diag_date, event_info in sorted(diagnosis_dates.items()):
                if diag_date <= enc_date:
                    linked_event_id = event_info['event_id']
                    orig_event_date = diag_date
            
            # Calculate months since diagnosis for visit classification
            update_which_visit = "Initial"
            if orig_event_date:
                orig_datetime = datetime.strptime(orig_event_date, '%Y-%m-%d')
                months_diff = round((enc_datetime - orig_datetime).days / 30.44)
                
                # Classify visit type (±2 month tolerance)
                visit_types = {
                    6: "6 Month Update",
                    12: "12 Month Update",
                    18: "18 Month Update",
                    24: "24 Month Update",
                    36: "36 Month Update"
                }
                
                for target_months, visit_name in visit_types.items():
                    if abs(months_diff - target_months) <= 2:
                        update_which_visit = visit_name
                        break
            
            # Calculate orig_event_date (for ordering)
            orig_event_date_days = None
            if orig_event_date:
                orig_dt = datetime.strptime(orig_event_date, '%Y-%m-%d')
                orig_event_date_days = (orig_dt - self.birth_date).days
            
            encounter_events.append({
                'research_id': self.patient_research_id,
                'event_id': linked_event_id,
                'age_at_encounter': age_at_encounter,
                'clinical_status': "Alive",  # Default unless deceased
                'follow_up_visit_status': "Complete",  # If status='finished'
                'update_which_visit': update_which_visit,
                'tumor_status': None,  # Requires BRIM
                'orig_event_date_for_update_ordering_only': orig_event_date_days
            })
        
        print(f"  ✅ Built {len(encounter_events)} encounter events\n")
        
        return encounter_events
    
    def load_gold_standard(self, gold_standard_path: str) -> pd.DataFrame:
        """Load gold standard encounters CSV"""
        print(f"{'='*60}")
        print("📁 LOADING GOLD STANDARD")
        print(f"{'='*60}\n")
        
        df = pd.read_csv(gold_standard_path)
        print(f"  Total encounter records: {len(df)}")
        
        # Filter for test patient
        patient_df = df[df['research_id'] == self.patient_research_id]
        print(f"  Found {len(patient_df)} records for {self.patient_research_id}\n")
        
        # Show event distribution
        event_counts = patient_df['event_id'].value_counts()
        print(f"  📊 Unique diagnosis events: {len(event_counts)}")
        for event_id, count in event_counts.items():
            print(f"     {event_id}: {count} encounters")
        print()
        
        return patient_df
    
    def validate(self, extracted: list, gold_standard: pd.DataFrame):
        """Compare extracted data against gold standard"""
        print(f"{'='*60}")
        print("🔍 FIELD-BY-FIELD COMPARISON")
        print(f"{'='*60}\n")
        
        # Convert extracted to DataFrame
        extracted_df = pd.DataFrame(extracted)
        
        # Fields to validate
        structured_fields = [
            'age_at_encounter',
            'clinical_status',
            'follow_up_visit_status',
            'update_which_visit',
            'orig_event_date_for_update_ordering_only'
        ]
        
        narrative_fields = ['tumor_status']
        
        results = {}
        total_matched = 0
        total_fields = 0
        
        print(f"  📊 STRUCTURED FIELDS (Athena-extractable):")
        for field in structured_fields:
            if field not in extracted_df.columns:
                print(f"    ❌ {field}: Field not extracted")
                results[field] = {'accuracy': 0.0, 'matched': 0, 'total': 0}
                continue
            
            gold_values = gold_standard[field].tolist()
            extracted_values = extracted_df[field].tolist()
            
            # Compare (handle nulls and type mismatches)
            matches = 0
            comparisons = min(len(gold_values), len(extracted_values))
            
            for i in range(comparisons):
                gold_val = str(gold_values[i]) if pd.notna(gold_values[i]) else None
                ext_val = str(extracted_values[i]) if pd.notna(extracted_values[i]) else None
                
                if gold_val == ext_val:
                    matches += 1
            
            accuracy = (matches / comparisons * 100) if comparisons > 0 else 0
            
            if accuracy == 100:
                print(f"    ✅ {field}: {accuracy:.1f}% ({matches}/{comparisons})")
            elif accuracy >= 50:
                print(f"    ⚠️  {field}: {accuracy:.1f}% ({matches}/{comparisons})")
            else:
                print(f"    ❌ {field}: {accuracy:.1f}% ({matches}/{comparisons})")
            
            results[field] = {
                'accuracy': accuracy,
                'matched': matches,
                'total': comparisons
            }
            
            total_matched += matches
            total_fields += comparisons
        
        print(f"\n  📊 NARRATIVE FIELDS (BRIM required):")
        for field in narrative_fields:
            print(f"    ⏭️  {field}: Extraction not attempted (requires clinical notes)")
        
        # Calculate overall accuracy
        overall_accuracy = (total_matched / total_fields * 100) if total_fields > 0 else 0
        
        print(f"\n{'='*60}")
        print("📊 VALIDATION METRICS")
        print(f"{'='*60}\n")
        print(f"  Structured Accuracy: {overall_accuracy:.1f}%")
        print(f"  Structured Matched: {total_matched}/{total_fields}")
        print(f"  Narrative Fields: {len(narrative_fields)} (not attempted)")
        
        # Write report
        report_path = Path('athena_extraction_validation/reports/encounters_validation.md')
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write(f"# Encounters Validation Report\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"## Overall Metrics\n")
            f.write(f"- **Structured Accuracy**: {overall_accuracy:.1f}%\n")
            f.write(f"- **Records Compared**: {len(gold_standard)}\n\n")
            f.write(f"## Field-by-Field Results\n\n")
            
            for field, metrics in results.items():
                f.write(f"### {field}\n")
                f.write(f"- Accuracy: {metrics['accuracy']:.1f}%\n")
                f.write(f"- Matched: {metrics['matched']}/{metrics['total']}\n\n")
        
        print(f"\n📄 Report written to: {report_path}")
        
        if overall_accuracy >= 80:
            print("✅ VALIDATION PASSED")
            return True
        else:
            print("⚠️ VALIDATION NEEDS IMPROVEMENT")
            return False


def main():
    parser = argparse.ArgumentParser(description='Validate Encounters CSV Extraction')
    parser.add_argument('--aws-profile', default='343218191717_AWSAdministratorAccess',
                       help='AWS profile name')
    parser.add_argument('--database', default='fhir_v2_prd_db',
                       help='Athena database name')
    parser.add_argument('--gold-standard',
                       default='data/20250723_multitab_csvs/20250723_multitab__encounters.csv',
                       help='Path to gold standard encounters CSV')
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = EncountersValidator(args.aws_profile, args.database)
    
    # Print configuration
    print(f"{'='*60}")
    print("ENCOUNTERS CSV VALIDATION")
    print(f"{'='*60}\n")
    print(f"Patient: {validator.patient_research_id}")
    print(f"FHIR ID: {validator.patient_fhir_id}")
    print(f"Birth Date: {validator.birth_date.strftime('%Y-%m-%d')}")
    print(f"Database: {args.database}")
    print(f"Gold Standard: {args.gold_standard}")
    print(f"{'='*60}")
    
    # Extract from Athena
    extracted = validator.extract_encounters_from_athena()
    
    # Load gold standard
    gold_standard = validator.load_gold_standard(args.gold_standard)
    
    # Validate
    success = validator.validate(extracted, gold_standard)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
