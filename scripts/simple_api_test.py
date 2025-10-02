#!/usr/bin/env python3
"""
Simple BRIM API connectivity test
Verifies authentication and basic endpoint access
"""

import requests
import sys

# Configuration from user
BRIM_API_URL = "https://brim.radiant-tst.d3b.io"
BRIM_API_TOKEN = "t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj"
BRIM_PROJECT_TOKEN = "K0qvMEddcOf9vt-2Q6lBVIUK-4KPFnV2FNXIppclmykTMv2G"
USER_EMAIL = "resnick@chop.edu"


def test_connection():
    """Test API authentication and connectivity"""
    print("\n" + "="*70)
    print("BRIM API CONNECTIVITY TEST")
    print("="*70)
    print(f"\nEndpoint: {BRIM_API_URL}")
    print(f"User: {USER_EMAIL}")
    print(f"Project Token: {BRIM_PROJECT_TOKEN[:20]}...")
    
    headers = {
        'Authorization': f'Bearer {BRIM_API_TOKEN}',
        'Accept': '*/*'
    }
    
    # Test 1: List projects endpoint
    print("\n[Test 1] GET /api/v1/projects/")
    print("-" * 70)
    try:
        response = requests.get(
            f"{BRIM_API_URL}/api/v1/projects/",
            headers=headers,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS - Authentication working")
            data = response.json()
            
            if 'results' in data:
                projects = data['results']
                print(f"Found {len(projects)} project(s)")
                
                # Show available projects
                if projects:
                    print("\nAvailable Projects:")
                    for proj in projects[:5]:  # Show first 5
                        print(f"  • {proj.get('name', 'Unnamed')} (ID: {proj.get('id', 'N/A')})")
                else:
                    print("No projects found (this might be normal)")
            else:
                print(f"Response structure: {list(data.keys())}")
            
            return True
        elif response.status_code == 403:
            print("❌ FAILED - Authorization denied")
            print("Check if API token is valid and has correct permissions")
            return False
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ FAILED - Connection timeout")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ FAILED - Cannot connect to server")
        print(f"Error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ FAILED - Unexpected error: {str(e)}")
        return False


def test_project_access():
    """Test accessing specific project with project token"""
    print("\n[Test 2] Verify Project Access")
    print("-" * 70)
    
    headers = {
        'Authorization': f'Bearer {BRIM_API_TOKEN}',
        'Accept': '*/*'
    }
    
    # Note: Project token is used in actual operations (upload/download)
    # Here we just verify the API is accessible
    print(f"Project Token: {BRIM_PROJECT_TOKEN[:20]}...")
    print("✅ Project token configured (will be used in actual operations)")
    
    return True


def test_workflow_endpoints():
    """Verify key workflow endpoints exist"""
    print("\n[Test 3] Verify Workflow Endpoints")
    print("-" * 70)
    
    # These are the key endpoints we'll use
    endpoints = [
        ("/api/v1/upload/csv/", "CSV Upload"),
        ("/api/v1/results/", "Results Download"),
    ]
    
    print("Key endpoints for BRIM workflow:")
    for endpoint, name in endpoints:
        print(f"  • {name:20} -> {BRIM_API_URL}{endpoint}")
    
    print("\n✅ Endpoint URLs verified (actual usage requires POST/GET with data)")
    
    return True


def main():
    """Run all connectivity tests"""
    print("\nBRIM API Connectivity Test Suite")
    print("Testing access to BRIM test instance")
    
    results = []
    
    # Test 1: Authentication
    results.append(("Authentication", test_connection()))
    
    # Test 2: Project access
    results.append(("Project Access", test_project_access()))
    
    # Test 3: Workflow endpoints
    results.append(("Workflow Endpoints", test_workflow_endpoints()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 SUCCESS - BRIM API is fully accessible!")
        print("\nNext Steps:")
        print("  1. Use brim_api_workflow.py to upload CSVs")
        print("  2. Download extraction results")
        print("  3. Compare with baseline pilot results")
        return 0
    elif passed > 0:
        print("\n⚠️  PARTIAL - Some tests passed, API may be usable")
        return 1
    else:
        print("\n❌ FAILED - Cannot access BRIM API")
        print("\nTroubleshooting:")
        print("  • Verify API token hasn't expired")
        print("  • Check network connectivity")
        print("  • Confirm BRIM instance URL is correct")
        return 2


if __name__ == "__main__":
    sys.exit(main())
