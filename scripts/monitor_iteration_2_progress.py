#!/usr/bin/env python3
"""
Monitor BRIM Project 19 Extraction Progress
Polls API, downloads results, runs validation, compares to iteration 1
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_19_KEY = "ruoUS2kf1o_2JXhoqsl2SpBShwC4pC73yoohjjUpkfxrEfAY"
BASE_URL = "https://brim.radiant-tst.d3b.io/api/v1"
POLL_INTERVAL = 30  # seconds
TIMEOUT = 1800  # 30 minutes

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "pilot_output"
ITERATION_2_DIR = OUTPUT_DIR / "iteration_2_results"

# API Token from environment
API_TOKEN = os.getenv("BRIM_API_TOKEN", "t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj")

class BRIMMonitor:
    def __init__(self, project_key, api_token):
        self.project_key = project_key
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.base_url = BASE_URL
        
    def get_project_status(self):
        """Get current project status"""
        url = f"{self.base_url}/projects/{self.project_key}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting project status: {e}")
            return None
    
    def get_extraction_jobs(self):
        """Get list of extraction jobs for project"""
        url = f"{self.base_url}/projects/{self.project_key}/jobs"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting extraction jobs: {e}")
            return None
    
    def get_job_status(self, job_id):
        """Get status of specific extraction job"""
        url = f"{self.base_url}/jobs/{job_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting job status: {e}")
            return None
    
    def download_extractions(self, output_path):
        """Download extractions.csv"""
        url = f"{self.base_url}/projects/{self.project_key}/extractions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Downloaded extractions to: {output_path}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading extractions: {e}")
            return False
    
    def download_decisions(self, output_path):
        """Download decisions.csv"""
        url = f"{self.base_url}/projects/{self.project_key}/decisions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Downloaded decisions to: {output_path}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading decisions: {e}")
            return False
    
    def monitor_extraction(self, poll_interval=30, timeout=1800):
        """
        Monitor extraction progress until complete
        
        Args:
            poll_interval: Seconds between status checks (default 30s)
            timeout: Maximum time to wait in seconds (default 1800s = 30 min)
        """
        print(f"\n🔍 Monitoring Project 19 Extraction")
        print(f"{'='*70}")
        print(f"Project Key: {self.project_key}")
        print(f"Poll Interval: {poll_interval}s")
        print(f"Timeout: {timeout}s ({timeout//60} minutes)")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        last_status = None
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > timeout:
                print(f"\n⚠️  Timeout reached ({timeout}s)")
                print(f"   Extraction may still be running - check manually")
                return False
            
            # Get latest job status
            jobs = self.get_extraction_jobs()
            
            if not jobs:
                print(f"⏳ [{int(elapsed)}s] No jobs found yet - waiting for extraction to start...")
                time.sleep(poll_interval)
                continue
            
            # Get most recent job
            latest_job = sorted(jobs, key=lambda j: j.get('created_at', ''), reverse=True)[0]
            job_id = latest_job.get('id')
            status = latest_job.get('status', 'unknown')
            progress = latest_job.get('progress', 0)
            
            # Print status if changed
            if status != last_status:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Status: {status}")
                if status == 'running':
                    print(f"   Job ID: {job_id}")
                    print(f"   Progress: {progress}%")
                last_status = status
            
            # Check completion
            if status == 'completed':
                print(f"\n✅ Extraction COMPLETE!")
                print(f"   Total time: {int(elapsed)}s ({elapsed//60:.1f} minutes)")
                print(f"   Job ID: {job_id}")
                return True
            
            elif status == 'failed':
                print(f"\n❌ Extraction FAILED!")
                print(f"   Job ID: {job_id}")
                error = latest_job.get('error_message', 'No error message')
                print(f"   Error: {error}")
                return False
            
            # Continue monitoring
            if status == 'running' and progress != getattr(self, '_last_progress', None):
                print(f"   Progress: {progress}%")
                self._last_progress = progress
            
            time.sleep(poll_interval)

def run_validation(extractions_path, decisions_path):
    """Run automated validation against gold standard"""
    print(f"\n🧪 Running Validation")
    print(f"{'='*70}")
    
    gold_standard_dir = "/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/data/20250723_multitab_csvs"
    validation_output = ITERATION_2_DIR / "validation_results.json"
    
    cmd = f"""python3 scripts/automated_brim_validation.py \
  --extractions {extractions_path} \
  --decisions {decisions_path} \
  --gold-standard-dir {gold_standard_dir} \
  --output {validation_output}"""
    
    print(f"Command: {cmd}\n")
    
    exit_code = os.system(cmd)
    
    if exit_code == 0:
        print(f"✅ Validation complete: {validation_output}")
        return validation_output
    else:
        print(f"❌ Validation failed with exit code: {exit_code}")
        return None

def compare_iterations(iteration_2_validation, iteration_1_validation):
    """Compare iteration 2 vs iteration 1 results"""
    print(f"\n📊 Comparing Iteration 2 vs Iteration 1")
    print(f"{'='*70}")
    
    # Load validation results
    with open(iteration_2_validation, 'r') as f:
        iter2_results = json.load(f)
    
    with open(iteration_1_validation, 'r') as f:
        iter1_results = json.load(f)
    
    # Compare overall accuracy
    iter1_accuracy = iter1_results.get('overall_accuracy', 0)
    iter2_accuracy = iter2_results.get('overall_accuracy', 0)
    improvement = iter2_accuracy - iter1_accuracy
    
    print(f"\n📈 Overall Accuracy")
    print(f"   Iteration 1: {iter1_accuracy:.1f}%")
    print(f"   Iteration 2: {iter2_accuracy:.1f}%")
    print(f"   Improvement: {improvement:+.1f}%")
    
    # Compare individual variables
    print(f"\n📋 Variable-Level Comparison")
    print(f"{'Variable':<25} {'Iter 1':<12} {'Iter 2':<12} {'Change':<10}")
    print(f"{'-'*70}")
    
    iter1_tests = {t['variable_name']: t for t in iter1_results.get('test_results', [])}
    iter2_tests = {t['variable_name']: t for t in iter2_results.get('test_results', [])}
    
    all_variables = sorted(set(iter1_tests.keys()) | set(iter2_tests.keys()))
    
    for var in all_variables:
        iter1_pass = iter1_tests.get(var, {}).get('passed', False)
        iter2_pass = iter2_tests.get(var, {}).get('passed', False)
        
        iter1_status = "✅ PASS" if iter1_pass else "❌ FAIL"
        iter2_status = "✅ PASS" if iter2_pass else "❌ FAIL"
        
        if iter1_pass == iter2_pass:
            change = "=" if iter1_pass else "="
        elif iter2_pass:
            change = "⬆️ FIXED"
        else:
            change = "⬇️ REGRESSED"
        
        print(f"{var:<25} {iter1_status:<12} {iter2_status:<12} {change:<10}")
    
    # Key improvements
    print(f"\n🎯 Key Improvements")
    
    fixed_vars = [var for var in all_variables 
                  if not iter1_tests.get(var, {}).get('passed', False) 
                  and iter2_tests.get(var, {}).get('passed', False)]
    
    if fixed_vars:
        print(f"   Fixed variables ({len(fixed_vars)}):")
        for var in fixed_vars:
            iter1_val = iter1_tests[var].get('extracted_value', 'N/A')
            iter2_val = iter2_tests[var].get('extracted_value', 'N/A')
            gold_val = iter2_tests[var].get('expected_value', 'N/A')
            print(f"      • {var}: {iter1_val} → {iter2_val} (expected: {gold_val})")
    else:
        print(f"   No new variables fixed")
    
    # Regressions
    regressed_vars = [var for var in all_variables 
                      if iter1_tests.get(var, {}).get('passed', False) 
                      and not iter2_tests.get(var, {}).get('passed', False)]
    
    if regressed_vars:
        print(f"\n⚠️  Regressions ({len(regressed_vars)}):")
        for var in regressed_vars:
            print(f"      • {var}")
    else:
        print(f"\n✅ No regressions detected")
    
    # Create comparison report
    comparison_report = {
        'iteration_1': {
            'accuracy': iter1_accuracy,
            'passed': sum(1 for t in iter1_tests.values() if t.get('passed', False)),
            'failed': sum(1 for t in iter1_tests.values() if not t.get('passed', False))
        },
        'iteration_2': {
            'accuracy': iter2_accuracy,
            'passed': sum(1 for t in iter2_tests.values() if t.get('passed', False)),
            'failed': sum(1 for t in iter2_tests.values() if not t.get('passed', False))
        },
        'improvement': improvement,
        'fixed_variables': fixed_vars,
        'regressed_variables': regressed_vars,
        'timestamp': datetime.now().isoformat()
    }
    
    report_path = ITERATION_2_DIR / "comparison_report.json"
    with open(report_path, 'w') as f:
        json.dump(comparison_report, f, indent=2)
    
    print(f"\n📄 Comparison report saved: {report_path}")
    
    return comparison_report

def main():
    """Main monitoring workflow"""
    print(f"\n{'='*70}")
    print(f"🚀 BRIM Project 19 Monitoring - Iteration 2")
    print(f"{'='*70}")
    
    # Check for API token
    if not API_TOKEN:
        print(f"\n⚠️  WARNING: BRIM_API_TOKEN environment variable not set")
        print(f"   Some API operations may fail")
        print(f"   Set with: export BRIM_API_TOKEN='your_token_here'")
    
    # Initialize monitor
    monitor = BRIMMonitor(PROJECT_19_KEY, API_TOKEN)
    
    # Check project status
    print(f"\n📋 Checking Project Status...")
    project_status = monitor.get_project_status()
    
    if project_status:
        print(f"✅ Project found: {project_status.get('name', 'Project 19')}")
        print(f"   Status: {project_status.get('status', 'unknown')}")
    else:
        print(f"⚠️  Could not retrieve project status (may need API token)")
    
    # Monitor extraction
    print(f"\n⏳ Waiting for extraction to start...")
    print(f"   (User will upload CSVs and trigger extraction)")
    print(f"   Monitoring will begin automatically...")
    
    success = monitor.monitor_extraction(poll_interval=30, timeout=1800)
    
    if not success:
        print(f"\n❌ Extraction monitoring failed or timed out")
        print(f"   Check project 19 manually at: https://app.brimhealth.com")
        return 1
    
    # Download results
    print(f"\n📥 Downloading Results...")
    
    extractions_path = ITERATION_2_DIR / "extractions.csv"
    decisions_path = ITERATION_2_DIR / "decisions.csv"
    
    extractions_ok = monitor.download_extractions(extractions_path)
    decisions_ok = monitor.download_decisions(decisions_path)
    
    if not (extractions_ok and decisions_ok):
        print(f"\n❌ Failed to download results")
        return 1
    
    # Run validation
    validation_path = run_validation(extractions_path, decisions_path)
    
    if not validation_path:
        print(f"\n❌ Validation failed")
        return 1
    
    # Compare to iteration 1
    iteration_1_validation = OUTPUT_DIR / "iteration_1_validation_results.json"
    
    if iteration_1_validation.exists():
        compare_iterations(validation_path, iteration_1_validation)
    else:
        print(f"\n⚠️  Iteration 1 validation results not found: {iteration_1_validation}")
        print(f"   Skipping comparison")
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"✅ MONITORING COMPLETE")
    print(f"{'='*70}")
    print(f"\n📁 Generated Files:")
    print(f"   • {extractions_path}")
    print(f"   • {decisions_path}")
    print(f"   • {validation_path}")
    print(f"   • {ITERATION_2_DIR / 'comparison_report.json'}")
    
    print(f"\n📊 Next Steps:")
    print(f"   1. Review validation results: {validation_path}")
    print(f"   2. Review comparison report: {ITERATION_2_DIR / 'comparison_report.json'}")
    print(f"   3. Analyze failed tests (if any)")
    print(f"   4. Plan iteration 3 improvements (if needed)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
