#!/usr/bin/env python3
"""
Configure BRIM Project Variables and Decisions via Web UI API

This script attempts to configure variables and decisions by reverse-engineering
the web UI's API calls. This is a workaround until BRIM provides official API endpoints.

Usage:
    python scripts/configure_brim_project_web_api.py \
        --project-id 17 \
        --variables pilot_output/brim_csvs_final/variables.csv \
        --decisions pilot_output/brim_csvs_final/decisions.csv \
        --api-url https://brim.radiant-tst.d3b.io \
        --api-token YOUR_TOKEN

Note: This may not work if the web UI uses different authentication or endpoints.
      You may need to inspect browser network traffic to find the correct endpoints.
"""

import argparse
import csv
import json
import requests
import sys
from pathlib import Path


def load_csv_to_dict_list(filepath):
    """Load CSV file into list of dictionaries."""
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)


def configure_variables_json_api(base_url, api_token, project_id, variables_csv):
    """
    Attempt to configure variables via JSON API.
    This tries several possible endpoint patterns.
    """
    variables = load_csv_to_dict_list(variables_csv)
    
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    # Convert CSV rows to JSON format
    variables_json = []
    for var in variables:
        variables_json.append({
            'variable_name': var['variable_name'],
            'instruction': var['instruction'],
            'prompt_template': var.get('prompt_template', ''),
            'aggregation_instruction': var.get('aggregation_instruction', ''),
            'aggregation_prompt_template': var.get('aggregation_prompt_template', ''),
            'variable_type': var['variable_type'],
            'scope': var['scope'],
            'option_definitions': var.get('option_definitions', ''),
            'aggregation_option_definitions': var.get('aggregation_option_definitions', ''),
            'only_use_true_value_in_aggregation': var.get('only_use_true_value_in_aggregation', ''),
            'default_value_for_empty_response': var.get('default_value_for_empty_response', '')
        })
    
    # Try different possible endpoints
    endpoints = [
        f"{base_url}/api/v1/projects/{project_id}/variables",
        f"{base_url}/api/v1/projects/{project_id}/config/variables",
        f"{base_url}/api/v1/variables",
        f"{base_url}/projects/{project_id}/variables",
    ]
    
    for endpoint in endpoints:
        print(f"Trying endpoint: {endpoint}")
        try:
            response = requests.post(endpoint, headers=headers, json={'variables': variables_json})
            if response.status_code in [200, 201]:
                print(f"✅ Success! Variables configured via {endpoint}")
                return True
            else:
                print(f"   Status {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")
    
    return False


def configure_decisions_json_api(base_url, api_token, project_id, decisions_csv):
    """
    Attempt to configure decisions via JSON API.
    """
    decisions = load_csv_to_dict_list(decisions_csv)
    
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    # Convert CSV rows to JSON format
    decisions_json = []
    for dec in decisions:
        decisions_json.append({
            'decision_name': dec['decision_name'],
            'decision_type': dec['decision_type'],
            'decision_options': dec.get('decision_options', ''),
            'dependencies': dec.get('dependencies', ''),
            'instruction': dec.get('instruction', ''),
            'prompt_template': dec.get('prompt_template', '')
        })
    
    # Try different possible endpoints
    endpoints = [
        f"{base_url}/api/v1/projects/{project_id}/decisions",
        f"{base_url}/api/v1/projects/{project_id}/config/decisions",
        f"{base_url}/api/v1/decisions",
        f"{base_url}/projects/{project_id}/decisions",
    ]
    
    for endpoint in endpoints:
        print(f"Trying endpoint: {endpoint}")
        try:
            response = requests.post(endpoint, headers=headers, json={'decisions': decisions_json})
            if response.status_code in [200, 201]:
                print(f"✅ Success! Decisions configured via {endpoint}")
                return True
            else:
                print(f"   Status {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")
    
    return False


def main():
    parser = argparse.ArgumentParser(description='Configure BRIM project variables and decisions')
    parser.add_argument('--project-id', type=int, required=True, help='BRIM project ID')
    parser.add_argument('--variables', required=True, help='Path to variables.csv')
    parser.add_argument('--decisions', required=True, help='Path to decisions.csv')
    parser.add_argument('--api-url', required=True, help='BRIM API base URL')
    parser.add_argument('--api-token', required=True, help='API token')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("BRIM Project Configuration via Web UI API (Experimental)")
    print("=" * 80)
    print(f"Project ID: {args.project_id}")
    print(f"API URL: {args.api_url}")
    print()
    
    # Configure variables
    print("Configuring variables...")
    if configure_variables_json_api(args.api_url, args.api_token, args.project_id, args.variables):
        print("✅ Variables configured\n")
    else:
        print("❌ Failed to configure variables via API")
        print("   Manual configuration required via web UI")
        print()
    
    # Configure decisions
    print("Configuring decisions...")
    if configure_decisions_json_api(args.api_url, args.api_token, args.project_id, args.decisions):
        print("✅ Decisions configured\n")
    else:
        print("❌ Failed to configure decisions via API")
        print("   Manual configuration required via web UI")
        print()
    
    print("=" * 80)
    print("Configuration attempt complete")
    print("If configuration failed, you need to:")
    print("1. Go to https://brim.radiant-tst.d3b.io")
    print(f"2. Open project {args.project_id}")
    print("3. Upload variables.csv via web UI")
    print("4. Upload decisions.csv via web UI")
    print("=" * 80)


if __name__ == '__main__':
    main()
