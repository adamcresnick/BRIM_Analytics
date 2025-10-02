#!/usr/bin/env python3
"""
BRIM API Client and Iterative Workflow Manager

This script provides a comprehensive interface to the BRIM Analytics API
for automated variable configuration testing and iterative improvement.

Features:
- Upload project.csv with FHIR data
- Upload variables.csv and decisions.csv configurations
- Trigger extraction jobs
- Monitor job progress
- Download and analyze results
- Compare results across iterations
- Automated iterative improvement workflow

Usage:
    # Single upload and extract
    python brim_api_workflow.py upload --project-csv data/project.csv --config-dir config/
    
    # Iterative improvement workflow
    python brim_api_workflow.py iterate --max-iterations 5 --accuracy-threshold 0.90
    
    # Download latest results
    python brim_api_workflow.py download --output-dir pilot_output/

Environment Variables:
    BRIM_API_URL: Base URL for BRIM API (e.g., https://app.brimhealth.com)
    BRIM_API_TOKEN: API authentication token
    BRIM_PROJECT_ID: BRIM project ID

Author: RADIANT PCA Team
Date: October 2025
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


class BRIMAPIClient:
    """Client for interacting with BRIM Analytics API."""
    
    def __init__(self, base_url: str, api_token: str, project_id: int, verbose: bool = True):
        """
        Initialize BRIM API client.
        
        Args:
            base_url: Base URL for BRIM API (e.g., https://app.brimhealth.com)
            api_token: API authentication token
            project_id: BRIM project ID
            verbose: Enable verbose logging
        """
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
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] {message}")
    
    def upload_csv(self, filepath: str, generate_after_upload: bool = True) -> Optional[str]:
        """
        Upload a CSV file (project.csv, variables.csv, or decisions.csv) to BRIM.
        
        Args:
            filepath: Path to CSV file to upload
            generate_after_upload: Whether to start extraction after upload
            
        Returns:
            API session ID if successful, None otherwise
        """
        if not os.path.exists(filepath):
            self.log(f"❌ Error: File not found: {filepath}", always=True)
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
                
                self.log(f"✅ Upload successful: {result['data']['original_filename']}", always=True)
                self.log(f"📋 API Session ID: {api_session_id}", always=True)
                
                return api_session_id
                
        except requests.exceptions.RequestException as e:
            self.log(f"❌ Upload failed: {e}", always=True)
            if hasattr(e, 'response') and e.response is not None:
                self.log(f"Response: {e.response.text}", always=True)
            return None
        except Exception as e:
            self.log(f"❌ Unexpected error: {e}", always=True)
            return None
    
    def fetch_results(
        self, 
        api_session_id: Optional[str] = None,
        detailed_export: bool = True,
        include_null: bool = False,
        output_path: Optional[str] = None,
        max_retries: int = 60,
        retry_interval: int = 10
    ) -> Optional[str]:
        """
        Fetch results from BRIM extraction job.
        
        Args:
            api_session_id: Optional session ID to filter results (None = all project data)
            detailed_export: Request detailed export format
            include_null: Include null/unknown values in export
            output_path: Path to save CSV file
            max_retries: Maximum polling attempts
            retry_interval: Seconds between polling attempts
            
        Returns:
            Path to saved CSV file if successful, None otherwise
        """
        self.log(f"📥 Fetching results (session_id={api_session_id or 'all'})...")
        
        endpoint = f"{self.base_url}/api/v1/results/"
        
        payload = {
            'project_id': str(self.project_id),
            'detailed_export': detailed_export,
            'patient_export': not detailed_export,
            'include_null_in_export': include_null
        }
        
        if api_session_id:
            payload['api_session_id'] = api_session_id
        
        # First request to initiate export or check status
        for attempt in range(max_retries):
            try:
                self.log(f"🔄 Attempt {attempt + 1}/{max_retries}...")
                
                response = self.session.post(endpoint, json=payload, stream=True)
                response.raise_for_status()
                
                content_type = response.headers.get('Content-Type', '')
                
                # If we get CSV, export is complete
                if 'text/csv' in content_type:
                    self.log("✅ Export complete, downloading...", always=True)
                    
                    # Determine output filename
                    if output_path is None:
                        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                        output_path = f"pilot_output/BRIM_Export_{timestamp}.csv"
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Save CSV file
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    file_size = os.path.getsize(output_path)
                    self.log(f"💾 Saved to: {output_path} ({file_size:,} bytes)", always=True)
                    
                    return output_path
                
                # If JSON, check status
                elif 'application/json' in content_type:
                    result = response.json()
                    status = result.get('status', 'unknown')
                    
                    self.log(f"📊 Status: {status}")
                    
                    if status in ['Complete', 'complete', 'COMPLETE']:
                        # Export is done, retry to get CSV
                        continue
                    elif status in ['Error', 'error', 'ERROR', 'Stopped', 'stopped']:
                        self.log(f"❌ Export failed with status: {status}", always=True)
                        self.log(f"Details: {json.dumps(result, indent=2)}", always=True)
                        return None
                    else:
                        # Still running, wait and retry
                        self.log(f"⏳ Waiting {retry_interval}s...")
                        time.sleep(retry_interval)
                
            except requests.exceptions.RequestException as e:
                self.log(f"⚠️ Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_interval)
                else:
                    self.log(f"❌ Max retries exceeded", always=True)
                    return None
        
        self.log(f"❌ Failed to fetch results after {max_retries} attempts", always=True)
        return None
    
    def upload_and_extract(
        self, 
        project_csv: str,
        variables_csv: Optional[str] = None,
        decisions_csv: Optional[str] = None,
        output_path: Optional[str] = None,
        wait_seconds: int = 30
    ) -> Optional[str]:
        """
        Complete workflow: upload CSVs and fetch results.
        
        Args:
            project_csv: Path to project.csv with FHIR data
            variables_csv: Optional path to variables.csv configuration
            decisions_csv: Optional path to decisions.csv configuration
            output_path: Path to save results CSV
            wait_seconds: Seconds to wait for extraction to complete
            
        Returns:
            Path to results CSV if successful, None otherwise
        """
        self.log("🚀 Starting BRIM upload and extraction workflow...", always=True)
        
        # Upload variables config if provided
        if variables_csv:
            var_session_id = self.upload_csv(variables_csv, generate_after_upload=False)
            if not var_session_id:
                return None
        
        # Upload decisions config if provided  
        if decisions_csv:
            dec_session_id = self.upload_csv(decisions_csv, generate_after_upload=False)
            if not dec_session_id:
                return None
        
        # Upload project data and trigger extraction
        session_id = self.upload_csv(project_csv, generate_after_upload=True)
        if not session_id:
            return None
        
        # Wait for extraction to complete
        self.log(f"⏳ Waiting {wait_seconds}s for extraction to complete...", always=True)
        time.sleep(wait_seconds)
        
        # Fetch results
        results_path = self.fetch_results(
            api_session_id=session_id,
            output_path=output_path
        )
        
        if results_path:
            self.log(f"🎉 Workflow complete! Results: {results_path}", always=True)
        
        return results_path


class ResultsAnalyzer:
    """Analyze BRIM extraction results and calculate accuracy metrics."""
    
    def __init__(self, results_csv: str, verbose: bool = True):
        """
        Initialize results analyzer.
        
        Args:
            results_csv: Path to BRIM export CSV
            verbose: Enable verbose logging
        """
        self.results_csv = results_csv
        self.verbose = verbose
        self.df = pd.read_csv(results_csv)
        
    def log(self, message: str):
        """Log message if verbose enabled."""
        if self.verbose:
            print(message)
    
    def get_summary_statistics(self) -> Dict:
        """Calculate summary statistics for extraction results."""
        self.log("\n📊 Analyzing extraction results...")
        
        # Count variables vs decisions
        variables = self.df[~self.df['Name'].str.contains('_dependent', na=False)]
        decisions = self.df[self.df['Name'].str.contains('_dependent', na=False)]
        
        # Count unknown/default values
        unknown_values = self.df[self.df['Value'].str.lower().isin(['unknown', 'not documented', 'false'])]
        extracted_values = self.df[~self.df['Value'].str.lower().isin(['unknown', 'not documented', 'false'])]
        
        # Count by scope
        patient_level = self.df[self.df['Scope'].str.contains('Patient', na=False)]
        note_level = self.df[self.df['Scope'].str.contains('Note', na=False)]
        
        stats = {
            'total_rows': len(self.df),
            'unique_variables': self.df['Name'].nunique(),
            'variable_extractions': len(variables),
            'decision_extractions': len(decisions),
            'extracted_values': len(extracted_values),
            'unknown_values': len(unknown_values),
            'extraction_rate': len(extracted_values) / len(self.df) if len(self.df) > 0 else 0,
            'patient_level_count': len(patient_level),
            'note_level_count': len(note_level)
        }
        
        return stats
    
    def print_summary(self):
        """Print human-readable summary of results."""
        stats = self.get_summary_statistics()
        
        print("\n" + "="*60)
        print("BRIM EXTRACTION RESULTS SUMMARY")
        print("="*60)
        print(f"📁 File: {os.path.basename(self.results_csv)}")
        print(f"📊 Total Rows: {stats['total_rows']}")
        print(f"🔢 Unique Variables: {stats['unique_variables']}")
        print(f"📋 Variable Extractions: {stats['variable_extractions']}")
        print(f"🎯 Decision Extractions: {stats['decision_extractions']}")
        print(f"\n✅ Extracted Values: {stats['extracted_values']} ({stats['extraction_rate']:.1%})")
        print(f"❓ Unknown/Default Values: {stats['unknown_values']} ({1-stats['extraction_rate']:.1%})")
        print(f"\n👤 Patient-Level: {stats['patient_level_count']}")
        print(f"📄 Note-Level: {stats['note_level_count']}")
        print("="*60 + "\n")
        
        # Show variables with unknown values
        unknown_vars = self.df[
            self.df['Value'].str.lower().isin(['unknown', 'not documented'])
        ]['Name'].unique()
        
        if len(unknown_vars) > 0:
            print("⚠️  Variables with unknown values:")
            for var in unknown_vars:
                print(f"   - {var}")
            print()
    
    def compare_with_baseline(self, baseline_csv: str) -> Dict:
        """
        Compare current results with a baseline extraction.
        
        Args:
            baseline_csv: Path to baseline BRIM export CSV
            
        Returns:
            Dictionary with comparison metrics
        """
        baseline_df = pd.read_csv(baseline_csv)
        
        # Compare extraction rates
        current_extracted = self.df[~self.df['Value'].str.lower().isin(['unknown', 'not documented'])]
        baseline_extracted = baseline_df[~baseline_df['Value'].str.lower().isin(['unknown', 'not documented'])]
        
        current_rate = len(current_extracted) / len(self.df) if len(self.df) > 0 else 0
        baseline_rate = len(baseline_extracted) / len(baseline_df) if len(baseline_df) > 0 else 0
        
        comparison = {
            'current_extraction_rate': current_rate,
            'baseline_extraction_rate': baseline_rate,
            'improvement': current_rate - baseline_rate,
            'current_extracted_count': len(current_extracted),
            'baseline_extracted_count': len(baseline_extracted),
            'delta_extracted': len(current_extracted) - len(baseline_extracted)
        }
        
        return comparison


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='BRIM API Client and Iterative Workflow Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload and extract with auto-generated config
  python brim_api_workflow.py upload --project-csv data/project.csv
  
  # Upload with custom config files
  python brim_api_workflow.py upload --project-csv data/project.csv \\
      --variables-csv config/variables.csv --decisions-csv config/decisions.csv
  
  # Download latest results
  python brim_api_workflow.py download --output results.csv
  
  # Analyze existing results
  python brim_api_workflow.py analyze --results pilot_output/results.csv
  
Environment Variables:
  BRIM_API_URL       Base URL (default: https://app.brimhealth.com)
  BRIM_API_TOKEN     API authentication token (required)
  BRIM_PROJECT_ID    Project ID (required)
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload CSVs and trigger extraction')
    upload_parser.add_argument('--project-csv', required=True, help='Path to project.csv')
    upload_parser.add_argument('--variables-csv', help='Path to variables.csv')
    upload_parser.add_argument('--decisions-csv', help='Path to decisions.csv')
    upload_parser.add_argument('--output', help='Output path for results CSV')
    upload_parser.add_argument('--wait', type=int, default=30, help='Seconds to wait for extraction')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download latest results')
    download_parser.add_argument('--output', required=True, help='Output path for CSV')
    download_parser.add_argument('--session-id', help='Specific session ID to download')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze extraction results')
    analyze_parser.add_argument('--results', required=True, help='Path to results CSV')
    analyze_parser.add_argument('--baseline', help='Path to baseline CSV for comparison')
    
    # Global options
    parser.add_argument('--api-url', default=os.getenv('BRIM_API_URL', 'https://app.brimhealth.com'),
                       help='BRIM API base URL')
    parser.add_argument('--api-token', default=os.getenv('BRIM_API_TOKEN'),
                       help='BRIM API token')
    parser.add_argument('--project-id', type=int, default=os.getenv('BRIM_PROJECT_ID'),
                       help='BRIM project ID')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Validate required credentials
    if not args.api_token:
        print("❌ Error: BRIM_API_TOKEN is required (set via --api-token or env var)")
        sys.exit(1)
    
    if not args.project_id:
        print("❌ Error: BRIM_PROJECT_ID is required (set via --project-id or env var)")
        sys.exit(1)
    
    # Execute command
    if args.command == 'upload':
        client = BRIMAPIClient(args.api_url, args.api_token, args.project_id, args.verbose)
        results_path = client.upload_and_extract(
            project_csv=args.project_csv,
            variables_csv=args.variables_csv,
            decisions_csv=args.decisions_csv,
            output_path=args.output,
            wait_seconds=args.wait
        )
        sys.exit(0 if results_path else 1)
        
    elif args.command == 'download':
        client = BRIMAPIClient(args.api_url, args.api_token, args.project_id, args.verbose)
        results_path = client.fetch_results(
            api_session_id=args.session_id,
            output_path=args.output
        )
        sys.exit(0 if results_path else 1)
        
    elif args.command == 'analyze':
        analyzer = ResultsAnalyzer(args.results, args.verbose)
        analyzer.print_summary()
        
        if args.baseline:
            print("\n📊 Comparing with baseline...")
            comparison = analyzer.compare_with_baseline(args.baseline)
            print(f"Current extraction rate: {comparison['current_extraction_rate']:.1%}")
            print(f"Baseline extraction rate: {comparison['baseline_extraction_rate']:.1%}")
            print(f"Improvement: {comparison['improvement']:+.1%}")
        
        sys.exit(0)
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
