#!/usr/bin/env python3
"""
Quick test script to verify BRIM API connectivity and functionality
"""

import requests
import json
import sys

# BRIM API Configuration
BRIM_API_URL = "https://brim.radiant-tst.d3b.io"
BRIM_API_TOKEN = "t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj"
BRIM_PROJECT_TOKEN = "1SBNge25Wlg7hQJi1OgdLI_JBfu76GgG6aoETrgXgvjnm1VH"
BRIM_PROJECT_ID = 17
BRIM_USER_EMAIL = "resnick@chop.edu"

def test_api_connection():
    """Test basic API connectivity"""
    print("=" * 80)
    print("BRIM API Connectivity Test")
    print("=" * 80)
    
    headers = {
        "Authorization": f"Bearer {BRIM_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Test 1: Check API health/version
    print("\n1. Testing API Health Check...")
    try:
        # Try to list projects (this should work if authenticated)
        response = requests.get(
            f"{BRIM_API_URL}/api/v1/projects/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ API Connection Successful!")
            print(f"   Status Code: {response.status_code}")
            projects = response.json()
            print(f"   Found {len(projects.get('results', []))} projects")
            
            # Show project details if any exist
            if projects.get('results'):
                print("\n   Available Projects:")
                for project in projects['results'][:3]:  # Show first 3
                    print(f"   - {project.get('name')} (ID: {project.get('id')})")
            
            return True
        else:
            print(f"   ❌ API Connection Failed")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Connection Error: {str(e)}")
        return False

def test_upload_endpoint():
    """Test CSV upload endpoint availability"""
    print("\n2. Testing CSV Upload Endpoint...")
    
    headers = {
        "Authorization": f"Bearer {BRIM_API_TOKEN}",
    }
    
    try:
        # Test OPTIONS request to see what's available
        response = requests.options(
            f"{BRIM_API_URL}/api/v1/upload/csv/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            print("   ✅ Upload Endpoint Available")
            print(f"   Allowed Methods: {response.headers.get('Allow', 'Not specified')}")
            return True
        else:
            print(f"   ⚠️  Endpoint responded with status: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def test_results_endpoint():
    """Test results download endpoint"""
    print("\n3. Testing Results Endpoint...")
    
    headers = {
        "Authorization": f"Bearer {BRIM_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Test getting results (may return empty if no recent extractions)
        response = requests.get(
            f"{BRIM_API_URL}/api/v1/results/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ Results Endpoint Available")
            results = response.json()
            
            if isinstance(results, list):
                print(f"   Found {len(results)} recent results")
            elif isinstance(results, dict) and 'results' in results:
                print(f"   Found {len(results['results'])} recent results")
            else:
                print("   Results endpoint accessible (no recent extractions)")
            
            return True
        else:
            print(f"   ⚠️  Status Code: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def main():
    """Run all API tests"""
    print("\nStarting BRIM API Tests...\n")
    
    tests_passed = 0
    tests_total = 3
    
    # Run tests
    if test_api_connection():
        tests_passed += 1
    
    if test_upload_endpoint():
        tests_passed += 1
    
    if test_results_endpoint():
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Test Summary: {tests_passed}/{tests_total} tests passed")
    print("=" * 80)
    
    if tests_passed == tests_total:
        print("\n✅ All API tests passed! Ready to proceed with BRIM integration.")
        return 0
    elif tests_passed > 0:
        print("\n⚠️  Some tests passed. API is partially accessible.")
        return 1
    else:
        print("\n❌ All tests failed. Please check:")
        print("   - API token is correct")
        print("   - Network connectivity")
        print("   - BRIM API endpoint URL")
        return 2

if __name__ == "__main__":
    sys.exit(main())
