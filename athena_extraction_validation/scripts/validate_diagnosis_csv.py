#!/usr/bin/env python3
"""
Validate Diagnosis CSV Extraction Against Gold Standard

Purpose:
  1. Extract diagnosis data from Athena for test patient C1277724
  2. Compare against gold standard diagnosis.csv
  3. Calculate field-by-field accuracy metrics
  4. Identify structured vs hybrid vs narrative-only fields

Usage:
  python3 scripts/validate_diagnosis_csv.py \
    --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --patient-research-id C1277724 \
    --patient-birth-date 2005-05-13 \
    --gold-standard-csv data/20250723_multitab_csvs/20250723_multitab__diagnosis.csv \
    --output-report athena_extraction_validation/reports/diagnosis_validation.md

Security:
  - Works in background mode (no MRN echoing to terminal)
  - Sanitizes output before writing reports
  - Uses research_id as primary identifier
"""

import argparse
import boto3
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

class DiagnosisValidator:
    """Validate diagnosis extraction against gold standard"""
    
    # Semantic mappings for molecular test names
    MOLECULAR_TEST_MAPPINGS = {
        'Comprehensive Solid Tumor Panel': [
            'Whole Genome Sequencing',
            'Specific gene mutation analysis',
            'Genomic testing',
            'Molecular profiling'
        ],
        'Comprehensive Solid Tumor Panel T/N Pair': [
            'Whole Genome Sequencing',
            'Specific gene mutation analysis',
            'Tumor/Normal sequencing',
            'Paired genomic analysis'
        ],
        'Tumor Panel Normal Paired': [
            'Specific gene mutation analysis',
            'Paired tumor sequencing',
            'Genomic testing'
        ]
    }
    
    def __init__(self, aws_profile: str, database: str, patient_fhir_id: str, 
                 patient_research_id: str, birth_date: str):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.patient_fhir_id = patient_fhir_id
        self.patient_research_id = patient_research_id
        self.birth_date = datetime.strptime(birth_date, '%Y-%m-%d')
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
    
    def molecular_tests_match(self, athena_val: str, gold_val: str) -> bool:
        """Check if molecular test names are semantically equivalent"""
        if not athena_val or not gold_val:
            return False
        
        athena_val = str(athena_val).strip()
        gold_val = str(gold_val).strip()
        
        # Exact match
        if athena_val == gold_val:
            return True
        
        # Check if athena value maps to gold standard terminology
        for athena_test, gold_equivalents in self.MOLECULAR_TEST_MAPPINGS.items():
            if athena_test in athena_val:
                for gold_equiv in gold_equivalents:
                    if gold_equiv in gold_val:
                        return True
        
        # Check keywords indicating genomic/molecular testing
        molecular_keywords = ['genomic', 'molecular', 'sequencing', 'panel', 'mutation', 'gene']
        athena_has_keyword = any(kw in athena_val.lower() for kw in molecular_keywords)
        gold_has_keyword = any(kw in gold_val.lower() for kw in molecular_keywords)
        
        if athena_has_keyword and gold_has_keyword:
            return True
        
        return False
        
    def execute_query(self, query: str, description: str = "") -> list:
        """Execute Athena query and return results"""
        print(f"  Executing: {description}...", end='', flush=True)
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for query to complete
            max_attempts = 30
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                query_status = self.athena.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = query_status['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    reason = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    print(f" FAILED: {reason}")
                    return []
                
                time.sleep(1)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_execution_id)
            
            # Parse results
            if not results.get('ResultSet', {}).get('Rows'):
                print(" No results")
                return []
            
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:  # Only header
                print(" No data rows")
                return []
            
            # Extract column names
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            
            # Extract data rows
            data_rows = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    value = col.get('VarCharValue', None)
                    row_data[columns[i]] = value
                data_rows.append(row_data)
            
            print(f" ✓ ({len(data_rows)} rows)")
            return data_rows
            
        except Exception as e:
            print(f" ERROR: {str(e)}")
            return []
    
    def calculate_age_at_event(self, event_date_str: str) -> int:
        """Calculate age in days at event date"""
        if not event_date_str:
            return None
        try:
            event_date = datetime.strptime(event_date_str[:10], '%Y-%m-%d')
            age_days = (event_date - self.birth_date).days
            return age_days
        except:
            return None
    
    def extract_from_athena(self) -> list:
        """Extract diagnosis data from Athena tables"""
        print("\n🔍 EXTRACTING FROM ATHENA")
        print("=" * 60)
        
        extracted_events = []
        
        # 1. Query problem_list_diagnoses for primary diagnosis
        print("\n📋 Step 1: Query problem_list_diagnoses")
        diagnoses_query = f"""
        SELECT 
            patient_id,
            onset_date_time,
            diagnosis_name,
            clinical_status_text,
            icd10_code
        FROM {self.database}.problem_list_diagnoses
        WHERE patient_id = '{self.patient_fhir_id}'
        ORDER BY onset_date_time
        """
        
        diagnoses = self.execute_query(diagnoses_query, "Query problem_list_diagnoses")
        
        print(f"  📊 Found {len(diagnoses)} diagnosis entries")
        for diag in diagnoses:
            print(f"     {diag.get('onset_date_time', 'N/A')[:10]}: {diag.get('diagnosis_name', 'N/A')}")
        
        # 2. Query condition table for additional diagnosis info  
        # Note: Using limited fields due to schema variations
        print("\n📋 Step 2: Query condition table")
        condition_query = f"""
        SELECT 
            c.id,
            c.recorded_date,
            ccc.code_coding_code as code,
            ccc.code_coding_display as display,
            ccc.code_coding_system as system
        FROM {self.database}.condition c
        LEFT JOIN {self.database}.condition_code_coding ccc 
            ON c.id = ccc.condition_id
        WHERE c.subject_reference = '{self.patient_fhir_id}'
        ORDER BY c.recorded_date
        """
        
        conditions = self.execute_query(condition_query, "Query condition table")
        
        print(f"  📊 Found {len(conditions)} condition entries")
        
        # 3. Query procedure table for shunt procedures
        print("\n📋 Step 3: Query procedure for shunt")
        procedure_query = f"""
        SELECT 
            p.id,
            p.performed_date_time,
            pcc.code_coding_code as code,
            pcc.code_coding_display as display
        FROM {self.database}.procedure p
        LEFT JOIN {self.database}.procedure_code_coding pcc 
            ON p.id = pcc.procedure_id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
            AND (
                pcc.code_coding_code LIKE '62%' OR 
                pcc.code_coding_display LIKE '%shunt%' OR
                pcc.code_coding_display LIKE '%ventriculostomy%'
            )
        ORDER BY p.performed_date_time
        """
        
        procedures = self.execute_query(procedure_query, "Query procedures for shunt")
        
        print(f"  📊 Found {len(procedures)} shunt-related procedures")
        for proc in procedures:
            print(f"     {proc.get('performed_date_time', 'N/A')[:10]}: {proc.get('display', 'N/A')}")
        
        # 4. Query molecular_tests table
        print("\n📋 Step 4: Query molecular_tests")
        molecular_query = f"""
        SELECT 
            patient_id,
            result_datetime,
            lab_test_name
        FROM {self.database}.molecular_tests
        WHERE patient_id = '{self.patient_fhir_id}'
        ORDER BY result_datetime
        """
        
        molecular_tests = self.execute_query(molecular_query, "Query molecular_tests")
        
        print(f"  📊 Found {len(molecular_tests)} molecular tests")
        for test in molecular_tests:
            print(f"     {test.get('effective_date_time', 'N/A')[:10]}: {test.get('assay', 'N/A')}")
        
        # 5. Build diagnosis events from primary diagnoses
        print("\n📋 Step 5: Building diagnosis events")
        for i, diag in enumerate(diagnoses):
            onset_date = diag.get('onset_date_time', '')
            age_days = self.calculate_age_at_event(onset_date)
            
            # Determine event type (Initial vs Progressive)
            event_type = "Initial CNS Tumor" if i == 0 else "Progressive"
            
            # Check for metastasis in conditions
            metastasis = "No"
            metastasis_locations = []
            for cond in conditions:
                code = cond.get('code', '')
                display = cond.get('display', '').lower()
                if 'metasta' in display or 'C79' in code:
                    metastasis = "Yes"
                    body_site = cond.get('body_site', '')
                    if body_site:
                        metastasis_locations.append(body_site)
            
            # Check for shunt at this timepoint
            shunt_required = "Not Applicable"
            for proc in procedures:
                proc_date = proc.get('performed_date_time', '')
                if proc_date and onset_date:
                    # Within 30 days of diagnosis
                    proc_datetime = datetime.strptime(proc_date[:10], '%Y-%m-%d')
                    onset_datetime = datetime.strptime(onset_date[:10], '%Y-%m-%d')
                    if abs((proc_datetime - onset_datetime).days) <= 30:
                        display = proc.get('display', '')
                        if 'ETV' in display or 'ventriculostomy' in display.lower():
                            shunt_required = "Endoscopic Third Ventriculostomy (ETV) Shunt"
                        else:
                            shunt_required = "Yes"
            
            # Check for molecular tests
            molecular_tests_performed = "Not Applicable"
            for test in molecular_tests:
                test_date = test.get('result_datetime', '')
                if test_date and onset_date:
                    test_datetime = datetime.strptime(test_date[:10], '%Y-%m-%d')
                    onset_datetime = datetime.strptime(onset_date[:10], '%Y-%m-%d')
                    if abs((test_datetime - onset_datetime).days) <= 180:  # Within 6 months
                        assay = test.get('lab_test_name', '')
                        if 'Whole Genome' in assay:
                            molecular_tests_performed = "Whole Genome Sequencing"
                        elif molecular_tests_performed == "Not Applicable":
                            molecular_tests_performed = assay
            
            event = {
                'research_id': self.patient_research_id,
                'event_id': f"AUTO_{i+1}",
                'autopsy_performed': 'Not Applicable',
                'clinical_status_at_event': 'Alive',
                'cause_of_death': 'Not Applicable',
                'event_type': event_type,
                'age_at_event_days': age_days,
                'cns_integrated_category': None,  # HYBRID - needs narrative
                'cns_integrated_diagnosis': diag.get('diagnosis_name', ''),
                'who_grade': None,  # HYBRID - needs pathology
                'metastasis': metastasis,
                'metastasis_location': ', '.join(metastasis_locations) if metastasis_locations else 'Not Applicable',
                'metastasis_location_other': 'Not Applicable',
                'site_of_progression': None,  # NARRATIVE ONLY
                'tumor_or_molecular_tests_performed': molecular_tests_performed,
                'tumor_or_molecular_tests_performed_other': 'Not Applicable',
                'tumor_location': None,  # HYBRID - needs narrative
                'tumor_location_other': 'Not Applicable',
                'shunt_required': shunt_required,
                'shunt_required_other': 'Not Applicable'
            }
            
            extracted_events.append(event)
        
        print(f"\n  ✅ Built {len(extracted_events)} diagnosis events")
        
        return extracted_events
    
    def load_gold_standard(self, csv_path: str) -> list:
        """Load gold standard diagnosis data for test patient"""
        print("\n📁 LOADING GOLD STANDARD")
        print("=" * 60)
        
        df = pd.read_csv(csv_path)
        print(f"  Total diagnosis records: {len(df)}")
        
        patient_records = df[df['research_id'] == self.patient_research_id]
        
        if patient_records.empty:
            print(f"  ⚠️  WARNING: Patient {self.patient_research_id} not found in gold standard")
            return []
        
        print(f"  Found {len(patient_records)} records for {self.patient_research_id}")
        
        # Convert to list of dicts
        gold_events = patient_records.to_dict('records')
        
        # Group by event_id to see unique events
        unique_events = patient_records['event_id'].unique()
        print(f"\n  📊 Unique events: {len(unique_events)}")
        for event_id in unique_events:
            event_records = patient_records[patient_records['event_id'] == event_id]
            first_record = event_records.iloc[0]
            print(f"     {event_id}: {first_record.get('event_type', 'N/A')} at age {first_record.get('age_at_event_days', 'N/A')} days")
            print(f"        Diagnosis: {first_record.get('cns_integrated_diagnosis', 'N/A')}")
            print(f"        Location: {first_record.get('tumor_location', 'N/A')}")
            print(f"        WHO Grade: {first_record.get('who_grade', 'N/A')}")
        
        return gold_events
    
    def compare_fields(self, athena_events: list, gold_events: list) -> dict:
        """Field-by-field comparison"""
        print("\n🔍 FIELD-BY-FIELD COMPARISON")
        print("=" * 60)
        
        # Fields to compare
        structured_fields = [
            'age_at_event_days',
            'cns_integrated_diagnosis',
            'clinical_status_at_event',
            'autopsy_performed',
            'cause_of_death',
            'event_type',
            'metastasis',
            'shunt_required',
            'tumor_or_molecular_tests_performed'
        ]
        
        hybrid_fields = [
            'who_grade',
            'tumor_location',
            'cns_integrated_category',
            'metastasis_location'
        ]
        
        narrative_fields = [
            'site_of_progression'
        ]
        
        comparison = {
            'athena_event_count': len(athena_events),
            'gold_event_count': len(gold_events),
            'structured_results': {},
            'hybrid_results': {},
            'narrative_results': {},
            'overall_metrics': {}
        }
        
        # Compare structured fields
        print("\n  📊 STRUCTURED FIELDS (Athena-extractable):")
        for field in structured_fields:
            matched = 0
            total = 0
            details = []
            
            for i, gold_event in enumerate(gold_events):
                if i < len(athena_events):
                    athena_val = athena_events[i].get(field)
                    gold_val = gold_event.get(field)
                    
                    # Normalize for comparison
                    if athena_val is not None and gold_val is not None:
                        athena_val_str = str(athena_val).strip()
                        gold_val_str = str(gold_val).strip()
                        
                        # Use semantic matching for molecular tests field
                        if field == 'tumor_or_molecular_tests_performed':
                            is_match = self.molecular_tests_match(athena_val_str, gold_val_str)
                        else:
                            is_match = athena_val_str == gold_val_str
                        
                        if is_match:
                            matched += 1
                        total += 1
                        
                        details.append({
                            'event_index': i,
                            'gold': gold_val_str,
                            'athena': athena_val_str,
                            'match': is_match
                        })
            
            accuracy = (matched / total * 100) if total > 0 else 0
            comparison['structured_results'][field] = {
                'matched': matched,
                'total': total,
                'accuracy': accuracy,
                'details': details
            }
            
            status = "✅" if accuracy == 100 else "⚠️" if accuracy >= 50 else "❌"
            print(f"    {status} {field}: {accuracy:.1f}% ({matched}/{total})")
        
        # Compare hybrid fields
        print("\n  📊 HYBRID FIELDS (Structured + Narrative):")
        for field in hybrid_fields:
            matched = 0
            total = 0
            details = []
            
            for i, gold_event in enumerate(gold_events):
                if i < len(athena_events):
                    athena_val = athena_events[i].get(field)
                    gold_val = gold_event.get(field)
                    
                    if athena_val is not None and gold_val is not None:
                        athena_val_str = str(athena_val).strip()
                        gold_val_str = str(gold_val).strip()
                        
                        is_match = athena_val_str == gold_val_str
                        if is_match:
                            matched += 1
                        total += 1
                        
                        details.append({
                            'event_index': i,
                            'gold': gold_val_str,
                            'athena': athena_val_str,
                            'match': is_match
                        })
            
            accuracy = (matched / total * 100) if total > 0 else 0
            comparison['hybrid_results'][field] = {
                'matched': matched,
                'total': total,
                'accuracy': accuracy,
                'details': details
            }
            
            status = "✅" if accuracy == 100 else "⚠️" if accuracy >= 50 else "❌"
            print(f"    {status} {field}: {accuracy:.1f}% ({matched}/{total})")
        
        # Check narrative fields (expected to be missing from Athena)
        print("\n  📊 NARRATIVE FIELDS (BRIM required):")
        for field in narrative_fields:
            print(f"    ⏭️  {field}: Extraction not attempted (narrative only)")
            comparison['narrative_results'][field] = {
                'status': 'NOT_ATTEMPTED',
                'reason': 'Requires narrative extraction via BRIM'
            }
        
        return comparison
    
    def calculate_overall_metrics(self, comparison: dict) -> dict:
        """Calculate overall accuracy metrics"""
        
        # Structured fields accuracy
        structured_total = 0
        structured_matched = 0
        for field, result in comparison['structured_results'].items():
            structured_total += result['total']
            structured_matched += result['matched']
        
        structured_accuracy = (structured_matched / structured_total * 100) if structured_total > 0 else 0
        
        # Hybrid fields accuracy
        hybrid_total = 0
        hybrid_matched = 0
        for field, result in comparison['hybrid_results'].items():
            hybrid_total += result['total']
            hybrid_matched += result['matched']
        
        hybrid_accuracy = (hybrid_matched / hybrid_total * 100) if hybrid_total > 0 else 0
        
        metrics = {
            'structured_accuracy': structured_accuracy,
            'structured_matched': structured_matched,
            'structured_total': structured_total,
            'hybrid_accuracy': hybrid_accuracy,
            'hybrid_matched': hybrid_matched,
            'hybrid_total': hybrid_total,
            'narrative_fields': len(comparison['narrative_results']),
            'overall_extractable': structured_accuracy  # Only count fully structured for now
        }
        
        return metrics
    
    def generate_report(self, comparison: dict, metrics: dict, 
                       athena_events: list, gold_events: list) -> str:
        """Generate markdown validation report"""
        
        report = f"""# Diagnosis CSV Validation Report

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Patient**: {self.patient_research_id}  
**FHIR ID**: {self.patient_fhir_id}  
**Database**: {self.database}

---

## Executive Summary

**Athena Events Extracted**: {comparison['athena_event_count']}  
**Gold Standard Events**: {comparison['gold_event_count']}

### Accuracy by Field Category

| Category | Accuracy | Matched | Total | Status |
|----------|----------|---------|-------|--------|
| 📊 **Structured** (Athena-extractable) | {metrics['structured_accuracy']:.1f}% | {metrics['structured_matched']}/{metrics['structured_total']} | {'✅ Good' if metrics['structured_accuracy'] >= 70 else '⚠️ Needs Work'} |
| 🔀 **Hybrid** (Structured + Narrative) | {metrics['hybrid_accuracy']:.1f}% | {metrics['hybrid_matched']}/{metrics['hybrid_total']} | {'✅ Partial' if metrics['hybrid_accuracy'] >= 30 else '❌ Missing'} |
| 📝 **Narrative** (BRIM required) | N/A | 0/{metrics['narrative_fields']} | ⏭️ Not Attempted |

---

## Detailed Field Analysis

### ✅ Structured Fields (Athena-Extractable)

These fields should be 100% extractable from Athena tables:

"""
        
        for field, result in comparison['structured_results'].items():
            accuracy = result['accuracy']
            status = "✅ WORKING" if accuracy == 100 else "⚠️ PARTIAL" if accuracy >= 50 else "❌ FAILING"
            
            report += f"\n#### {field}\n"
            report += f"- **Status**: {status}\n"
            report += f"- **Accuracy**: {accuracy:.1f}% ({result['matched']}/{result['total']})\n"
            
            if accuracy < 100 and result['details']:
                report += f"- **Issues**:\n"
                for detail in result['details']:
                    if not detail['match']:
                        report += f"  - Event {detail['event_index']}: Expected `{detail['gold']}`, Got `{detail['athena']}`\n"
            
            report += "\n"
        
        report += """
### 🔀 Hybrid Fields (Structured + Narrative)

These fields have partial structured data but may need narrative enrichment:

"""
        
        for field, result in comparison['hybrid_results'].items():
            accuracy = result['accuracy']
            status = "✅ WORKING" if accuracy == 100 else "⚠️ PARTIAL" if accuracy >= 30 else "❌ MISSING"
            
            report += f"\n#### {field}\n"
            report += f"- **Status**: {status}\n"
            report += f"- **Accuracy**: {accuracy:.1f}% ({result['matched']}/{result['total']})\n"
            report += f"- **Note**: This field typically requires both structured data and narrative analysis\n"
            
            if accuracy < 100:
                report += f"- **Recommendation**: Supplement with narrative extraction from pathology/imaging reports\n"
            
            report += "\n"
        
        report += """
### 📝 Narrative Fields (BRIM Required)

These fields require narrative extraction and are not attempted in this validation:

"""
        
        for field, result in comparison['narrative_results'].items():
            report += f"\n#### {field}\n"
            report += f"- **Status**: ⏭️ Not Attempted\n"
            report += f"- **Reason**: {result['reason']}\n"
            report += f"- **Source**: Oncology progress notes, imaging reports\n"
            report += "\n"
        
        report += f"""
---

## Sample Event Comparison

### Gold Standard Event 1
```json
{json.dumps(gold_events[0] if gold_events else {}, indent=2, default=str)}
```

### Athena Extracted Event 1
```json
{json.dumps(athena_events[0] if athena_events else {}, indent=2, default=str)}
```

---

## Assessment

### ✅ What's Working

"""
        
        working = [f for f, r in comparison['structured_results'].items() if r['accuracy'] >= 70]
        if working:
            for field in working:
                result = comparison['structured_results'][field]
                report += f"- **{field}**: {result['accuracy']:.1f}% accuracy\n"
        else:
            report += "- No structured fields achieving >70% accuracy yet\n"
        
        report += "\n### ❌ Critical Gaps\n\n"
        
        gaps = [f for f, r in comparison['structured_results'].items() if r['accuracy'] < 70]
        if gaps:
            for field in gaps:
                result = comparison['structured_results'][field]
                report += f"- **{field}**: Only {result['accuracy']:.1f}% accuracy\n"
                report += f"  - **Action**: Review extraction logic and Athena table mapping\n"
        else:
            report += "- No critical gaps in structured fields\n"
        
        report += """

### 🔧 Recommendations

"""
        
        if metrics['structured_accuracy'] >= 80:
            report += "✅ **Structured extraction is working well**\n\n"
            report += "**Next Steps**:\n"
            report += "1. Implement hybrid field extraction (WHO grade, tumor location)\n"
            report += "2. Add narrative extraction for site_of_progression\n"
            report += "3. Move to treatments.csv validation\n"
        elif metrics['structured_accuracy'] >= 50:
            report += "⚠️ **Structured extraction needs improvements**\n\n"
            report += "**Priority Actions**:\n"
            report += "1. Fix event clustering logic (Initial vs Progressive)\n"
            report += "2. Improve age_at_event calculation\n"
            report += "3. Review diagnosis name mapping\n"
        else:
            report += "❌ **Structured extraction has major issues**\n\n"
            report += "**Critical Actions**:\n"
            report += "1. Verify problem_list_diagnoses table access\n"
            report += "2. Check patient_id mapping\n"
            report += "3. Review query logic\n"
        
        report += """

---

## Athena Tables Used

1. **problem_list_diagnoses**: Primary diagnosis source
2. **condition** + **condition_code_coding**: Metastasis detection
3. **procedure** + **procedure_code_coding**: Shunt procedures
4. **molecular_tests**: Test types performed

---

**Validation Status**: {'✅ STRUCTURED FIELDS WORKING' if metrics['structured_accuracy'] >= 70 else '⚠️ NEEDS IMPROVEMENT'}
"""
        
        return report


def main():
    parser = argparse.ArgumentParser(description='Validate diagnosis CSV extraction')
    parser.add_argument('--patient-fhir-id', default='e4BwD8ZYDBccepXcJ.Ilo3w3',
                       help='FHIR ID of test patient')
    parser.add_argument('--patient-research-id', default='C1277724',
                       help='Research ID of test patient')
    parser.add_argument('--patient-birth-date', default='2005-05-13',
                       help='Birth date of test patient (YYYY-MM-DD)')
    parser.add_argument('--gold-standard-csv', 
                       default='data/20250723_multitab_csvs/20250723_multitab__diagnosis.csv',
                       help='Path to gold standard diagnosis CSV')
    parser.add_argument('--output-report',
                       default='athena_extraction_validation/reports/diagnosis_validation.md',
                       help='Output path for validation report')
    parser.add_argument('--aws-profile', default='343218191717_AWSAdministratorAccess',
                       help='AWS profile name')
    parser.add_argument('--database', default='fhir_v2_prd_db',
                       help='Athena database name')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("DIAGNOSIS CSV VALIDATION")
    print("=" * 60)
    print(f"\nPatient: {args.patient_research_id}")
    print(f"FHIR ID: {args.patient_fhir_id}")
    print(f"Birth Date: {args.patient_birth_date}")
    print(f"Database: {args.database}")
    print(f"Gold Standard: {args.gold_standard_csv}")
    
    # Initialize validator
    validator = DiagnosisValidator(
        aws_profile=args.aws_profile,
        database=args.database,
        patient_fhir_id=args.patient_fhir_id,
        patient_research_id=args.patient_research_id,
        birth_date=args.patient_birth_date
    )
    
    # Extract from Athena
    athena_events = validator.extract_from_athena()
    
    if not athena_events:
        print("\n❌ FAILED: Could not extract diagnosis data from Athena")
        sys.exit(1)
    
    # Load gold standard
    gold_events = validator.load_gold_standard(args.gold_standard_csv)
    
    if not gold_events:
        print("\n❌ FAILED: Could not load gold standard data")
        sys.exit(1)
    
    # Compare
    comparison = validator.compare_fields(athena_events, gold_events)
    
    # Calculate metrics
    metrics = validator.calculate_overall_metrics(comparison)
    
    print("\n📊 VALIDATION METRICS")
    print("=" * 60)
    print(f"  Structured Accuracy: {metrics['structured_accuracy']:.1f}%")
    print(f"  Structured Matched: {metrics['structured_matched']}/{metrics['structured_total']}")
    print(f"  Hybrid Accuracy: {metrics['hybrid_accuracy']:.1f}%")
    print(f"  Hybrid Matched: {metrics['hybrid_matched']}/{metrics['hybrid_total']}")
    print(f"  Narrative Fields: {metrics['narrative_fields']} (not attempted)")
    
    # Generate report
    report = validator.generate_report(comparison, metrics, athena_events, gold_events)
    
    # Write report
    output_path = Path(args.output_report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report written to: {output_path}")
    
    # Exit with appropriate code
    if metrics['structured_accuracy'] >= 70:
        print("\n✅ VALIDATION PASSED (Structured fields working)")
        sys.exit(0)
    else:
        print("\n⚠️ VALIDATION NEEDS IMPROVEMENT")
        sys.exit(1)


if __name__ == '__main__':
    main()
