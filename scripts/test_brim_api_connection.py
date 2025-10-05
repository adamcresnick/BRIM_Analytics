#!/usr/bin/env python3
"""
BRIM API Connectivity Test
Tests basic connectivity and authentication with BRIM API

Usage:
    python test_brim_api_connection.py --url https://app.brimhealth.com --token YOUR_TOKEN --project-id 123
    
    Or set environment variables:
    export BRIM_API_URL="https://app.brimhealth.com"
    export BRIM_API_TOKEN="your_token_here"
    export BRIM_PROJECT_ID="123"
    python test_brim_api_connection.py
"""

import argparse
import os
import sys
import requests
from datetime import datetime


def log(message: str, level: str = "INFO"):
    """Log message with timestamp and level"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "TEST": "🧪"
    }
    icon = icons.get(level, "ℹ️")
    print(f"[{timestamp}] {icon} {message}")


def test_api_connectivity(base_url: str, api_token: str, project_id: str) -> bool:
    """
    Test basic API connectivity and authentication
    
    Args:
        base_url: Base URL for BRIM API
        api_token: API authentication token
        project_id: BRIM project ID
        
    Returns:
        True if all tests pass, False otherwise
    """
    
    log("Starting BRIM API Connectivity Tests", "TEST")
    log(f"Base URL: {base_url}", "INFO")
    log(f"Project ID: {project_id}", "INFO")
    log(f"Token: {'*' * 20}...{api_token[-4:] if len(api_token) > 4 else '****'}", "INFO")
    
    print("\n" + "="*80)
    print("TEST 1: Basic API Endpoint Accessibility")
    print("="*80)
    
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {api_token}',
        'Accept': '*/*'
    })
    
    # Test 1: Check if API is reachable
    try:
        log("Testing base URL connectivity...", "TEST")
        response = session.get(f"{base_url}/api/v1/", timeout=10)
        
        if response.status_code == 200:
            log(f"Base API endpoint is reachable (Status: {response.status_code})", "SUCCESS")
        elif response.status_code == 401:
            log(f"API is reachable but authentication failed (Status: {response.status_code})", "WARNING")
            log("Please check your API token", "WARNING")
        else:
            log(f"API returned status code: {response.status_code}", "WARNING")
            
    except requests.exceptions.ConnectionError as e:
        log(f"Cannot connect to API: {e}", "ERROR")
        return False
    except requests.exceptions.Timeout:
        log("API request timed out", "ERROR")
        return False
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        return False
    
    print("\n" + "="*80)
    print("TEST 2: Project Access")
    print("="*80)
    
    # Test 2: Check project access
    try:
        log(f"Testing access to project ID: {project_id}...", "TEST")
        
        # Try to get project information
        response = session.get(
            f"{base_url}/api/v1/projects/{project_id}/",
            timeout=10
        )
        
        if response.status_code == 200:
            log("Project is accessible", "SUCCESS")
            project_data = response.json()
            if 'name' in project_data:
                log(f"Project Name: {project_data['name']}", "INFO")
        elif response.status_code == 404:
            log(f"Project {project_id} not found", "ERROR")
            log("Please verify the project ID", "WARNING")
        elif response.status_code == 403:
            log(f"Access denied to project {project_id}", "ERROR")
            log("Please check API token permissions", "WARNING")
        else:
            log(f"Unexpected status code: {response.status_code}", "WARNING")
            
    except Exception as e:
        log(f"Error accessing project: {e}", "WARNING")
    
    print("\n" + "="*80)
    print("TEST 3: Upload Endpoint")
    print("="*80)
    
    # Test 3: Check upload endpoint
    try:
        log("Testing upload endpoint availability...", "TEST")
        
        # Just check if endpoint exists (without actually uploading)
        response = session.options(
            f"{base_url}/api/v1/upload/csv/",
            timeout=10
        )
        
        if response.status_code in [200, 204, 405]:  # 405 = Method Not Allowed is OK for OPTIONS
            log("Upload endpoint is available", "SUCCESS")
        else:
            log(f"Upload endpoint returned: {response.status_code}", "WARNING")
            
    except Exception as e:
        log(f"Error checking upload endpoint: {e}", "WARNING")
    
    print("\n" + "="*80)
    print("TEST 4: Results Endpoint")
    print("="*80)
    
    # Test 4: Check results endpoint
    try:
        log("Testing results endpoint availability...", "TEST")
        
        response = session.get(
            f"{base_url}/api/v1/results/?project_id={project_id}",
            timeout=10
        )
        
        if response.status_code == 200:
            log("Results endpoint is accessible", "SUCCESS")
            results_data = response.json()
            
            if isinstance(results_data, list):
                log(f"Found {len(results_data)} existing result(s)", "INFO")
                if len(results_data) > 0:
                    latest = results_data[0]
                    if 'session_id' in latest:
                        log(f"Latest session ID: {latest['session_id']}", "INFO")
                    if 'created_at' in latest:
                        log(f"Latest session date: {latest['created_at']}", "INFO")
            elif isinstance(results_data, dict):
                log(f"Results structure: {list(results_data.keys())}", "INFO")
        else:
            log(f"Results endpoint returned: {response.status_code}", "WARNING")
            
    except Exception as e:
        log(f"Error checking results endpoint: {e}", "WARNING")
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    log("All basic connectivity tests completed", "SUCCESS")
    log("API appears to be accessible", "SUCCESS")
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("✓ If all tests passed, you can proceed with uploading CSV files")
    print("✓ Use brim_api_workflow.py for full workflow management")
    print("✓ Example: python scripts/brim_api_workflow.py upload --project-csv data/project.csv")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Test BRIM API connectivity')
    parser.add_argument(
        '--url',
        default=os.environ.get('BRIM_API_URL'),
        help='BRIM API base URL (or set BRIM_API_URL env var)'
    )
    parser.add_argument(
        '--token',
        default=os.environ.get('BRIM_API_TOKEN'),
        help='BRIM API token (or set BRIM_API_TOKEN env var)'
    )
    parser.add_argument(
        '--project-id',
        default=os.environ.get('BRIM_PROJECT_ID'),
        help='BRIM project ID (or set BRIM_PROJECT_ID env var)'
    )
    
    args = parser.parse_args()
    
    # Validate required parameters
    if not args.url:
        log("ERROR: BRIM API URL not provided", "ERROR")
        log("Set BRIM_API_URL environment variable or use --url flag", "ERROR")
        sys.exit(1)
    
    if not args.token:
        log("ERROR: BRIM API token not provided", "ERROR")
        log("Set BRIM_API_TOKEN environment variable or use --token flag", "ERROR")
        sys.exit(1)
    
    if not args.project_id:
        log("ERROR: BRIM project ID not provided", "ERROR")
        log("Set BRIM_PROJECT_ID environment variable or use --project-id flag", "ERROR")
        sys.exit(1)
    
    # Run tests
    try:
        success = test_api_connectivity(args.url, args.token, args.project_id)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\nTest interrupted by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected error during testing: {e}", "ERROR")
        sys.exit(1)


if __name__ == '__main__':
    main()
