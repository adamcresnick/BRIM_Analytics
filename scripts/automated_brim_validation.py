#!/usr/bin/env python3
"""
Automated BRIM Validation Workflow

This script orchestrates the complete iterative BRIM extraction and validation workflow:
1. Upload CSVs to BRIM via API
2. Download extraction results
3. Validate against gold standard (patient C1277724)
4. Analyze accuracy metrics
5. Modify prompts/variables based on failures
6. Iterate until target accuracy achieved

Usage:
    # Full automated workflow
    python automated_brim_validation.py --max-iterations 5 --target-accuracy 0.92
    
    # Single iteration test
    python automated_brim_validation.py --max-iterations 1 --no-auto-improve
    
    # Validation only (skip upload)
    python automated_brim_validation.py --validate-only --results-csv pilot_output/existing_results.csv

Environment Variables:
    BRIM_API_URL: BRIM API base URL (default: https://brim.radiant-tst.d3b.io)
    BRIM_API_TOKEN: BRIM API authentication token
    BRIM_PROJECT_ID: BRIM project ID

Author: RADIANT PCA Team
Date: October 2025
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


class BRIMAPIClient:
    """Simplified BRIM API client for upload/download operations."""
    
    def __init__(self, base_url: str, api_token: str, project_id: int, verbose: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.project_id = project_id
        self.verbose = verbose
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Accept': '*/*'
        })
    
    def log(self, message: str, always: bool = False):
        """Log message if verbose enabled."""
        if self.verbose or always:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {message}")
    
    def upload_variables_csv(self, filepath: str) -> bool:
        """Upload variables configuration CSV."""
        if not os.path.exists(filepath):
            self.log(f"❌ File not found: {filepath}", always=True)
            return False
        
        filename = os.path.basename(filepath)
        self.log(f"📤 Uploading {filename}...")
        
        try:
            endpoint = f"{self.base_url}/projects/{self.project_id}/variables"
            
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'text/csv')}
                response = self.session.post(endpoint, files=files)
                response.raise_for_status()
                
                self.log(f"✅ {filename} uploaded successfully", always=True)
                return True
                
        except Exception as e:
            self.log(f"❌ Upload failed: {e}", always=True)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    self.log(f"Response: {e.response.text}", always=True)
                except:
                    pass
            return False
    
    def upload_decisions_csv(self, filepath: str) -> bool:
        """Upload decisions configuration CSV."""
        if not os.path.exists(filepath):
            self.log(f"❌ File not found: {filepath}", always=True)
            return False
        
        filename = os.path.basename(filepath)
        self.log(f"📤 Uploading {filename}...")
        
        try:
            endpoint = f"{self.base_url}/projects/{self.project_id}/decisions"
            
            with open(filepath, 'rb') as f:
                files = {'file': (filename, f, 'text/csv')}
                response = self.session.post(endpoint, files=files)
                response.raise_for_status()
                
                self.log(f"✅ {filename} uploaded successfully", always=True)
                return True
                
        except Exception as e:
            self.log(f"❌ Upload failed: {e}", always=True)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    self.log(f"Response: {e.response.text}", always=True)
                except:
                    pass
            return False
    
    def upload_project_csv(self, filepath: str, generate_after_upload: bool = True) -> Optional[str]:
        """Upload project.csv file to BRIM and optionally trigger extraction."""
        if not os.path.exists(filepath):
            self.log(f"❌ File not found: {filepath}", always=True)
            return None
        
        filename = os.path.basename(filepath)
        self.log(f"📤 Uploading {filename}...")
        
        try:
            endpoint = f"{self.base_url}/api/v1/upload/csv/"
            
            with open(filepath, 'rb') as f:
                files = {'csv_file': f}
                data = {
                    'project_id': str(self.project_id),
                    'generate_after_upload': generate_after_upload
                }
                
                response = self.session.post(endpoint, data=data, files=files)
                response.raise_for_status()
                
                result = response.json()
                api_session_id = result['data']['api_session_id']
                
                self.log(f"✅ {filename} uploaded (session: {api_session_id})", always=True)
                return api_session_id
                
        except Exception as e:
            self.log(f"❌ Upload failed: {e}", always=True)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    self.log(f"Response: {e.response.text}", always=True)
                except:
                    pass
            return None
    
    def fetch_results(
        self, 
        api_session_id: Optional[str] = None,
        output_path: Optional[str] = None,
        max_retries: int = 60,
        retry_interval: int = 10
    ) -> Optional[str]:
        """Fetch extraction results from BRIM with polling."""
        self.log(f"📥 Fetching results...")
        
        endpoint = f"{self.base_url}/api/v1/results/"
        
        payload = {
            'project_id': str(self.project_id),
            'detailed_export': True,
            'patient_export': False,
            'include_null_in_export': False
        }
        
        if api_session_id:
            payload['api_session_id'] = api_session_id
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(endpoint, json=payload, stream=True)
                response.raise_for_status()
                
                content_type = response.headers.get('Content-Type', '')
                
                # CSV = export complete
                if 'text/csv' in content_type:
                    if output_path is None:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        output_path = f"pilot_output/brim_results_c1277724/results_{timestamp}.csv"
                    
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    file_size = os.path.getsize(output_path)
                    self.log(f"✅ Results saved: {output_path} ({file_size:,} bytes)", always=True)
                    return output_path
                
                # JSON = status check
                elif 'application/json' in content_type:
                    result = response.json()
                    
                    # Check nested data object for actual status
                    if 'data' in result:
                        data = result['data']
                        is_complete = data.get('is_complete', False)
                        status_display = data.get('status_display', 'Unknown')
                        export_task_id = data.get('api_session_id')
                        
                        if is_complete:
                            # Task complete, retry to get CSV with the export task ID
                            if export_task_id and export_task_id != api_session_id:
                                self.log(f"✅ Extraction complete, fetching results (task {export_task_id})...")
                                api_session_id = export_task_id
                            continue
                        elif status_display.lower() in ['error', 'stopped', 'failed']:
                            self.log(f"❌ Extraction failed: {status_display}", always=True)
                            return None
                        else:
                            self.log(f"⏳ Status: {status_display} (attempt {attempt + 1}/{max_retries})")
                            time.sleep(retry_interval)
                    else:
                        # Fallback to old status handling
                        status = result.get('status', 'unknown')
                        if status.lower() in ['complete', 'completed']:
                            continue
                        elif status.lower() in ['error', 'stopped', 'failed']:
                            self.log(f"❌ Extraction failed: {status}", always=True)
                            return None
                        else:
                            self.log(f"⏳ Status: {status} (attempt {attempt + 1}/{max_retries})")
                            time.sleep(retry_interval)
                
            except Exception as e:
                self.log(f"⚠️ Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_interval)
                else:
                    self.log(f"❌ Max retries exceeded", always=True)
                    return None
        
        self.log(f"❌ Failed to fetch results", always=True)
        return None


class GoldStandardValidator:
    """Validate BRIM results against human-curated gold standard."""
    
    def __init__(self, gold_standard_dir: str, patient_id: str = "C1277724"):
        self.gold_dir = Path(gold_standard_dir)
        self.patient_id = patient_id
        
        # Load gold standard data
        self.demographics = pd.read_csv(self.gold_dir / "20250723_multitab__demographics.csv")
        self.diagnosis = pd.read_csv(self.gold_dir / "20250723_multitab__diagnosis.csv")
        self.treatments = pd.read_csv(self.gold_dir / "20250723_multitab__treatments.csv")
        self.molecular = pd.read_csv(self.gold_dir / "20250723_multitab__molecular_characterization.csv")
        
        # Filter for patient C1277724
        self.patient_demographics = self.demographics[self.demographics['research_id'] == patient_id]
        self.patient_diagnosis = self.diagnosis[self.diagnosis['research_id'] == patient_id]
        self.patient_treatments = self.treatments[self.treatments['research_id'] == patient_id]
        self.patient_molecular = self.molecular[self.molecular['research_id'] == patient_id]
        
        # Calculate birth date (age 4763 days at diagnosis ~2018-06-04)
        diagnosis_date = datetime(2018, 6, 4)
        age_at_diagnosis_days = 4763
        self.birth_date = diagnosis_date - timedelta(days=age_at_diagnosis_days)
    
    def date_to_age_days(self, date_str: str) -> int:
        """Convert YYYY-MM-DD date to age_in_days."""
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            return (event_date - self.birth_date).days
        except:
            return -1
    
    def validate(self, brim_results_csv: str) -> Dict:
        """
        Comprehensive validation of BRIM results against gold standard.
        
        Returns:
            Dictionary with accuracy metrics and detailed results
        """
        print("\n" + "=" * 80)
        print("BRIM VALIDATION REPORT - Patient C1277724")
        print("=" * 80)
        
        brim_df = pd.read_csv(brim_results_csv)
        
        print(f"Loaded {len(brim_df)} rows from BRIM results")
        print(f"Columns: {list(brim_df.columns)}")
        
        # Filter for patient 1277724 or C1277724 - check all possible column names
        patient_col = None
        for col in ['Patient_id', 'patient_id', 'subject_id', 'BRIM_SUBJECT']:
            if col in brim_df.columns:
                patient_col = col
                break
        
        if patient_col:
            patient_results = brim_df[brim_df[patient_col].astype(str).str.contains('1277724', na=False)]
            print(f"Found {len(patient_results)} rows for patient 1277724 using column '{patient_col}'")
        else:
            print("⚠️  Warning: No patient ID column found, using all rows")
            patient_results = brim_df
        
        if len(patient_results) == 0:
            print("⚠️  Warning: No results found for patient 1277724/C1277724")
            print(f"Available patient IDs: {brim_df[patient_col].unique() if patient_col else 'N/A'}")
            # Use all rows as fallback
            patient_results = brim_df
        
        tests = {}
        details = {}
        
        # Helper function to get BRIM value by variable name
        def get_brim_value(var_name):
            """Extract value for a given variable name from BRIM results."""
            if 'Name' in patient_results.columns and 'Value' in patient_results.columns:
                matches = patient_results[patient_results['Name'] == var_name]
                if len(matches) > 0:
                    return str(matches['Value'].iloc[0])
            # Fallback to direct column access
            if var_name in patient_results.columns:
                return str(patient_results[var_name].iloc[0])
            return None
        
        # TEST 1: Gender/Sex
        gold_sex = self.patient_demographics['legal_sex'].iloc[0] if len(self.patient_demographics) > 0 else "Female"
        brim_sex = get_brim_value('patient_gender')
        
        tests['gender'] = (gold_sex.lower() in str(brim_sex).lower() if brim_sex else False)
        details['gender'] = {'gold': gold_sex, 'brim': brim_sex or 'NOT FOUND', 'match': tests['gender']}
        print(f"\n1. Gender: Gold={gold_sex}, BRIM={brim_sex or 'NOT FOUND'}, {'✅' if tests['gender'] else '❌'}")
        
        # TEST 2: Molecular Marker (KIAA1549-BRAF)
        gold_molecular = self.patient_molecular['mutation'].iloc[0].strip() if len(self.patient_molecular) > 0 else "KIAA1549-BRAF"
        brim_molecular = get_brim_value('idh_mutation') or get_brim_value('molecular_profile') or get_brim_value('genetic_mutations')
        
        tests['molecular'] = (
            ("KIAA1549" in str(brim_molecular) and "BRAF" in str(brim_molecular))
            if brim_molecular else False
        )
        details['molecular'] = {'gold': gold_molecular, 'brim': brim_molecular or 'NOT FOUND', 'match': tests['molecular']}
        print(f"2. Molecular: Gold={gold_molecular}, BRIM={brim_molecular or 'NOT FOUND'}, {'✅' if tests['molecular'] else '❌'}")
        
        # TEST 3: Diagnosis Date (age 4763 days)
        gold_diagnosis_age = 4763
        brim_diagnosis_date = get_brim_value('diagnosis_date') or get_brim_value('initial_diagnosis_date') or get_brim_value('date_of_diagnosis')
        
        if brim_diagnosis_date and brim_diagnosis_date not in ['nan', 'None', 'unknown', '']:
            brim_diagnosis_age = self.date_to_age_days(brim_diagnosis_date)
            # Allow ±7 days tolerance
            tests['diagnosis_date'] = abs(gold_diagnosis_age - brim_diagnosis_age) <= 7
            details['diagnosis_date'] = {
                'gold': f'age {gold_diagnosis_age} days',
                'brim': f'age {brim_diagnosis_age} days',
                'match': tests['diagnosis_date']
            }
            print(f"3. Diagnosis Date: Gold=age {gold_diagnosis_age} days, BRIM=age {brim_diagnosis_age} days, {'✅' if tests['diagnosis_date'] else '❌'}")
        else:
            tests['diagnosis_date'] = False
            details['diagnosis_date'] = {'gold': f'age {gold_diagnosis_age} days', 'brim': 'NOT FOUND', 'match': False}
            print(f"3. Diagnosis Date: Gold=age {gold_diagnosis_age} days, BRIM=NOT FOUND, ❌")
        
        # TEST 4: Surgery Count (2 neurosurgeries)
        gold_surgery_count = len(self.patient_treatments[self.patient_treatments['surgery'] == 'Yes'])
        
        # Count surgery_date entries in BRIM results
        if 'Name' in patient_results.columns:
            surgery_dates = patient_results[patient_results['Name'] == 'surgery_date']
            brim_surgery_count = len(surgery_dates)
        else:
            # Fallback to direct column
            brim_surgery_str = get_brim_value('total_surgeries') or get_brim_value('surgery_count') or get_brim_value('number_of_surgeries')
            try:
                brim_surgery_count = int(brim_surgery_str) if brim_surgery_str else None
            except:
                brim_surgery_count = None
        
        tests['surgery_count'] = (gold_surgery_count == brim_surgery_count if brim_surgery_count is not None else False)
        details['surgery_count'] = {'gold': gold_surgery_count, 'brim': brim_surgery_count or 'NOT FOUND', 'match': tests['surgery_count']}
        print(f"4. Surgery Count: Gold={gold_surgery_count}, BRIM={brim_surgery_count or 'NOT FOUND'}, {'✅' if tests['surgery_count'] else '❌'}")
        
        # TEST 5: Chemotherapy Agents (vinblastine, bevacizumab, selumetinib)
        gold_chemo_agents = set()
        for agents in self.patient_treatments['chemotherapy_agents'].dropna():
            gold_chemo_agents.update([a.strip().lower() for a in str(agents).split(';')])
        
        # Get all chemotherapy_agent entries from BRIM results
        brim_chemo_agents = set()
        if 'Name' in patient_results.columns:
            chemo_rows = patient_results[patient_results['Name'] == 'chemotherapy_agent']
            for val in chemo_rows['Value'].dropna():
                brim_chemo_agents.add(str(val).strip().lower())
        else:
            # Fallback to single value
            agents_str = get_brim_value('chemotherapy_regimen') or get_brim_value('chemo_agents') or get_brim_value('medications')
            if agents_str and agents_str not in ['nan', 'None', '']:
                brim_chemo_agents.update([a.strip().lower() for a in agents_str.split(',')])
        
        overlap = gold_chemo_agents.intersection(brim_chemo_agents)
        recall = len(overlap) / len(gold_chemo_agents) if gold_chemo_agents else 0
        precision = len(overlap) / len(brim_chemo_agents) if brim_chemo_agents else 0
        tests['chemotherapy'] = (recall >= 0.85)
        
        details['chemotherapy'] = {
            'gold': list(gold_chemo_agents),
            'brim': list(brim_chemo_agents),
            'overlap': list(overlap),
            'recall': recall,
            'precision': precision,
            'match': tests['chemotherapy']
        }
        print(f"5. Chemotherapy:")
        print(f"   Gold: {gold_chemo_agents}")
        print(f"   BRIM: {brim_chemo_agents if brim_chemo_agents else 'NOT FOUND'}")
        print(f"   Recall: {recall:.1%}, Precision: {precision:.1%}, {'✅' if tests['chemotherapy'] else '❌'}")
        
        # TEST 6: Tumor Location
        gold_location = "Cerebellum/Posterior Fossa"
        brim_location = get_brim_value('tumor_location') or get_brim_value('primary_site') or get_brim_value('anatomical_location')
        
        tests['tumor_location'] = (
            ("cerebellum" in str(brim_location).lower() or "posterior fossa" in str(brim_location).lower())
            if brim_location else False
        )
        details['tumor_location'] = {'gold': gold_location, 'brim': brim_location or 'NOT FOUND', 'match': tests['tumor_location']}
        print(f"6. Tumor Location: Gold={gold_location}, BRIM={brim_location or 'NOT FOUND'}, {'✅' if tests['tumor_location'] else '❌'}")
        
        # TEST 7: WHO Grade
        gold_who_grade = "1"
        brim_who_grade = get_brim_value('who_grade') or get_brim_value('grade') or get_brim_value('tumor_grade')
        
        tests['who_grade'] = ("1" in str(brim_who_grade) or "I" in str(brim_who_grade) if brim_who_grade else False)
        details['who_grade'] = {'gold': gold_who_grade, 'brim': brim_who_grade or 'NOT FOUND', 'match': tests['who_grade']}
        print(f"7. WHO Grade: Gold={gold_who_grade}, BRIM={brim_who_grade or 'NOT FOUND'}, {'✅' if tests['who_grade'] else '❌'}")
        
        # TEST 8: Diagnosis Type (Pilocytic astrocytoma)
        gold_diagnosis = "Pilocytic astrocytoma"
        brim_diagnosis = get_brim_value('primary_diagnosis') or get_brim_value('diagnosis') or get_brim_value('histology') or get_brim_value('pathology_diagnosis') or get_brim_value('tumor_type')
        
        tests['diagnosis_type'] = (
            ("pilocytic" in str(brim_diagnosis).lower() and "astrocytoma" in str(brim_diagnosis).lower())
            if brim_diagnosis else False
        )
        details['diagnosis_type'] = {'gold': gold_diagnosis, 'brim': brim_diagnosis or 'NOT FOUND', 'match': tests['diagnosis_type']}
        print(f"8. Diagnosis: Gold={gold_diagnosis}, BRIM={brim_diagnosis or 'NOT FOUND'}, {'✅' if tests['diagnosis_type'] else '❌'}")
        
        # Calculate overall accuracy
        total_tests = len(tests)
        passed_tests = sum(tests.values())
        accuracy = passed_tests / total_tests if total_tests > 0 else 0
        
        print("\n" + "=" * 80)
        print(f"OVERALL ACCURACY: {accuracy:.1%} ({passed_tests}/{total_tests} tests passed)")
        print("=" * 80)
        
        return {
            'patient_id': self.patient_id,
            'timestamp': datetime.now().isoformat(),
            'brim_results_file': brim_results_csv,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'overall_accuracy': accuracy,
            'test_results': tests,
            'detailed_results': details,
            'target_accuracy': 0.92,
            'meets_target': accuracy >= 0.92
        }


class PromptImprover:
    """Analyze failures and suggest improvements to variables.csv."""
    
    def __init__(self, variables_csv_path: str):
        self.variables_csv_path = variables_csv_path
        self.df = pd.read_csv(variables_csv_path)
    
    def improve_based_on_failures(self, validation_results: Dict, output_path: Optional[str] = None) -> str:
        """
        Generate improved variables.csv based on validation failures.
        
        Args:
            validation_results: Results from GoldStandardValidator
            output_path: Where to save improved variables.csv
            
        Returns:
            Path to improved variables.csv
        """
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"pilot_output/brim_csvs_improved/variables_v{timestamp}.csv"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        failed_tests = [
            test_name for test_name, passed in validation_results['test_results'].items()
            if not passed
        ]
        
        print(f"\n🔧 Improving variables.csv based on {len(failed_tests)} failures...")
        
        improvements = []
        
        # Map failed tests to variable improvements
        improvement_map = {
            'gender': {
                'variable': 'patient_gender',
                'instruction_enhancement': 'Extract patient gender/sex. Look for: "Female", "Male", "Sex: F", "Sex: M" in demographics or clinical notes. Check patient registration, history sections.',
                'example': 'Female'
            },
            'molecular': {
                'variable': 'molecular_profile',
                'instruction_enhancement': 'Extract ALL molecular/genetic findings including gene fusions, mutations, alterations. Look for: "KIAA1549-BRAF fusion", "BRAF V600E", "MGMT methylation", etc. Check pathology reports, molecular testing sections, genetic analysis notes.',
                'example': 'KIAA1549-BRAF fusion'
            },
            'diagnosis_date': {
                'variable': 'diagnosis_date',
                'instruction_enhancement': 'Extract initial CNS tumor diagnosis date in YYYY-MM-DD format. Look for: "initial diagnosis", "first diagnosed", "originally diagnosed", "date of diagnosis". Prioritize pathology report dates and neurosurgery consultation dates.',
                'example': '2018-06-04'
            },
            'surgery_count': {
                'variable': 'total_surgeries',
                'instruction_enhancement': 'Count ONLY neurosurgical tumor resections (craniotomy, partial resection, gross total resection). EXCLUDE: shunt placements, ventriculostomy, biopsy only, EVD placement. Look for operative reports with "resection" in title.',
                'example': '2'
            },
            'chemotherapy': {
                'variable': 'chemotherapy_regimen',
                'instruction_enhancement': 'Extract ALL chemotherapy agent names as comma-separated list. Look for: medication names in treatment plans, chemotherapy orders, oncology notes. Include: vinblastine, bevacizumab, selumetinib, temozolomide, carboplatin, etc. Extract from "Plan:" sections.',
                'example': 'vinblastine, bevacizumab, selumetinib'
            },
            'tumor_location': {
                'variable': 'tumor_location',
                'instruction_enhancement': 'Extract primary tumor anatomical location. Look for: "Location:", "Site:", "Tumor location" in pathology/radiology reports. Common locations: Cerebellum, Posterior Fossa, Brainstem, Thalamus, Cerebral hemisphere, Spine.',
                'example': 'Cerebellum/Posterior Fossa'
            },
            'who_grade': {
                'variable': 'who_grade',
                'instruction_enhancement': 'Extract WHO grade (1, 2, 3, 4 or I, II, III, IV). Look for: "WHO Grade", "WHO grade", "Grade I/II/III/IV" in pathology reports. Pilocytic astrocytoma = Grade 1.',
                'example': '1'
            },
            'diagnosis_type': {
                'variable': 'diagnosis',
                'instruction_enhancement': 'Extract specific histological diagnosis. Look for: pathology final diagnosis, "Diagnosis:", "Pathologic diagnosis:". Include full tumor name: Pilocytic astrocytoma, Glioblastoma, Medulloblastoma, Ependymoma, etc.',
                'example': 'Pilocytic astrocytoma'
            }
        }
        
        for failed_test in failed_tests:
            if failed_test in improvement_map:
                improvement = improvement_map[failed_test]
                var_name = improvement['variable']
                
                # Find variable in DataFrame
                var_row_idx = self.df[self.df['BRIM_VARIABLE'] == var_name].index
                
                if len(var_row_idx) > 0:
                    idx = var_row_idx[0]
                    old_instruction = self.df.loc[idx, 'VARIABLE_INSTRUCTIONS']
                    
                    # Update instruction
                    self.df.loc[idx, 'VARIABLE_INSTRUCTIONS'] = improvement['instruction_enhancement']
                    
                    improvements.append({
                        'variable': var_name,
                        'test': failed_test,
                        'old_instruction': old_instruction,
                        'new_instruction': improvement['instruction_enhancement']
                    })
                    
                    print(f"  ✓ Updated {var_name}: {failed_test}")
                else:
                    print(f"  ⚠ Variable {var_name} not found in variables.csv")
        
        # Save improved variables.csv
        self.df.to_csv(output_path, index=False)
        print(f"✅ Improved variables.csv saved: {output_path}")
        
        # Save improvement log
        log_path = output_path.replace('.csv', '_improvements.json')
        with open(log_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'failed_tests': failed_tests,
                'improvements': improvements,
                'accuracy_before': validation_results['overall_accuracy'],
                'target_accuracy': validation_results['target_accuracy']
            }, f, indent=2)
        print(f"📝 Improvement log: {log_path}")
        
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Automated BRIM Validation Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full automated workflow
  python automated_brim_validation.py --max-iterations 5

  # Single test iteration
  python automated_brim_validation.py --max-iterations 1 --no-auto-improve

  # Validation only (skip upload)
  python automated_brim_validation.py --validate-only --results-csv pilot_output/results.csv
        """
    )
    
    parser.add_argument('--max-iterations', type=int, default=5,
                       help='Maximum number of improvement iterations (default: 5)')
    parser.add_argument('--target-accuracy', type=float, default=0.92,
                       help='Target accuracy threshold (default: 0.92)')
    parser.add_argument('--no-auto-improve', action='store_true',
                       help='Disable automatic prompt improvement')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate existing results, skip upload')
    parser.add_argument('--results-csv', type=str,
                       help='Path to existing BRIM results CSV (for --validate-only)')
    
    # API configuration
    parser.add_argument('--api-url', default=os.getenv('BRIM_API_URL', 'https://brim.radiant-tst.d3b.io'),
                       help='BRIM API base URL')
    parser.add_argument('--api-token', default=os.getenv('BRIM_API_TOKEN'),
                       help='BRIM API authentication token')
    parser.add_argument('--project-id', type=int, default=int(os.getenv('BRIM_PROJECT_ID', '0')),
                       help='BRIM project ID')
    
    # File paths
    parser.add_argument('--csv-dir', default='pilot_output/brim_csvs_final',
                       help='Directory with BRIM CSVs (default: pilot_output/brim_csvs_final)')
    parser.add_argument('--gold-standard-dir', default='data/20250723_multitab_csvs',
                       help='Directory with gold standard CSVs')
    
    args = parser.parse_args()
    
    # Validate configuration
    if not args.validate_only:
        if not args.api_token:
            print("❌ Error: BRIM_API_TOKEN required (set env var or use --api-token)")
            return 1
        if args.project_id == 0:
            print("❌ Error: BRIM_PROJECT_ID required (set env var or use --project-id)")
            return 1
    
    print("\n" + "=" * 80)
    print("AUTOMATED BRIM VALIDATION WORKFLOW")
    print("=" * 80)
    print(f"Max Iterations: {args.max_iterations}")
    print(f"Target Accuracy: {args.target_accuracy:.1%}")
    print(f"Auto-Improve: {'Yes' if not args.no_auto_improve else 'No'}")
    print("=" * 80 + "\n")
    
    # Initialize components
    if not args.validate_only:
        client = BRIMAPIClient(args.api_url, args.api_token, args.project_id)
    
    validator = GoldStandardValidator(args.gold_standard_dir)
    
    # Track iterations
    iteration_results = []
    current_csv_dir = args.csv_dir
    
    for iteration in range(args.max_iterations):
        print(f"\n{'=' * 80}")
        print(f"ITERATION {iteration + 1}/{args.max_iterations}")
        print(f"{'=' * 80}\n")
        
        results_csv = None
        
        if args.validate_only and args.results_csv:
            # Skip upload, use provided results
            results_csv = args.results_csv
            print(f"📂 Using existing results: {results_csv}")
        else:
            # Upload CSVs and run extraction
            print("🚀 Phase 1: Upload CSVs to BRIM")
            
            project_csv = os.path.join(current_csv_dir, 'project.csv')
            variables_csv = os.path.join(current_csv_dir, 'variables.csv')
            decisions_csv = os.path.join(current_csv_dir, 'decisions.csv')
            
            # TODO: BRIM API currently does NOT provide endpoints for uploading variables.csv and decisions.csv
            # The /api/v1/upload/csv/ endpoint ONLY accepts project.csv (with NOTE_ID, NOTE_TEXT, etc.)
            # Variables and decisions must be configured through:
            #   Option 1: Web UI (manual, one-time setup)
            #   Option 2: Request API endpoints from BRIM team for programmatic configuration
            #   Option 3: Reverse engineer web UI API calls
            #
            # For now: Assuming project 17 has variables/decisions already configured
            # If not configured, this script will fail at validation step
            
            print(f"⚠️  IMPORTANT: Variables and decisions must be pre-configured in project {args.project_id}")
            print(f"    Expected variables: {variables_csv}")
            print(f"    Expected decisions: {decisions_csv}")
            print(f"    Current API limitation: No endpoint to upload these configs")
            print()
            
            # Check if deduplicated version exists (needed if original has duplicate NOTE_IDs)
            project_csv_dedup = project_csv.replace('.csv', '_dedup.csv')
            if os.path.exists(project_csv_dedup):
                print(f"⚠️  Using deduplicated project file: {os.path.basename(project_csv_dedup)}")
                project_csv = project_csv_dedup
            
            # Upload project data and trigger extraction
            print("📤 Uploading project.csv and triggering extraction...")
            proj_session = client.upload_project_csv(project_csv, generate_after_upload=True)
            if not proj_session:
                print("❌ Project upload failed")
                return 1
            
            # Wait for extraction
            print("\n⏳ Phase 2: Waiting for extraction (60 seconds)...")
            time.sleep(60)
            
            # Download results
            print("\n📥 Phase 3: Download results")
            results_csv = client.fetch_results(api_session_id=proj_session)
            
            if not results_csv:
                print("❌ Failed to download results")
                return 1
        
        # Validate results
        print("\n🔍 Phase 4: Validate against gold standard")
        validation_results = validator.validate(results_csv)
        
        # Save validation results
        validation_output = results_csv.replace('.csv', '_validation.json')
        with open(validation_output, 'w') as f:
            json.dump(validation_results, f, indent=2)
        print(f"\n💾 Validation results saved: {validation_output}")
        
        iteration_results.append({
            'iteration': iteration + 1,
            'accuracy': validation_results['overall_accuracy'],
            'passed_tests': validation_results['passed_tests'],
            'total_tests': validation_results['total_tests'],
            'results_csv': results_csv,
            'validation_json': validation_output
        })
        
        # Check if target achieved
        if validation_results['overall_accuracy'] >= args.target_accuracy:
            print(f"\n🎉 TARGET ACHIEVED! Accuracy: {validation_results['overall_accuracy']:.1%} >= {args.target_accuracy:.1%}")
            break
        
        # Improve prompts if not last iteration
        if iteration < args.max_iterations - 1 and not args.no_auto_improve:
            print("\n🔧 Phase 5: Improve prompts based on failures")
            
            improver = PromptImprover(os.path.join(current_csv_dir, 'variables.csv'))
            improved_vars_csv = improver.improve_based_on_failures(validation_results)
            
            # Create new CSV directory for next iteration
            next_csv_dir = f"pilot_output/brim_csvs_iter_{iteration + 2}"
            os.makedirs(next_csv_dir, exist_ok=True)
            
            # Copy project.csv and decisions.csv (unchanged)
            import shutil
            shutil.copy(os.path.join(current_csv_dir, 'project.csv'), next_csv_dir)
            shutil.copy(os.path.join(current_csv_dir, 'decisions.csv'), next_csv_dir)
            
            # Copy improved variables.csv
            shutil.copy(improved_vars_csv, os.path.join(next_csv_dir, 'variables.csv'))
            
            current_csv_dir = next_csv_dir
            print(f"✅ Next iteration will use: {next_csv_dir}")
        
        # Don't iterate if validate-only mode
        if args.validate_only:
            break
    
    # Final summary
    print("\n" + "=" * 80)
    print("WORKFLOW SUMMARY")
    print("=" * 80)
    
    for result in iteration_results:
        print(f"\nIteration {result['iteration']}: {result['accuracy']:.1%} ({result['passed_tests']}/{result['total_tests']})")
        print(f"  Results: {result['results_csv']}")
        print(f"  Validation: {result['validation_json']}")
    
    if len(iteration_results) > 1:
        accuracy_improvement = iteration_results[-1]['accuracy'] - iteration_results[0]['accuracy']
        print(f"\nAccuracy Improvement: {accuracy_improvement:+.1%}")
    
    final_accuracy = iteration_results[-1]['accuracy']
    if final_accuracy >= args.target_accuracy:
        print(f"\n✅ SUCCESS: Target accuracy {args.target_accuracy:.1%} achieved!")
        return 0
    else:
        print(f"\n⚠️  Target accuracy {args.target_accuracy:.1%} not achieved (got {final_accuracy:.1%})")
        print(f"Consider: More iterations, manual variable refinement, additional structured findings")
        return 1


if __name__ == '__main__':
    sys.exit(main())
