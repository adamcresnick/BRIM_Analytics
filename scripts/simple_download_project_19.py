#!/usr/bin/env python3
"""
Simple script to download results from Project 19
Uses the exact working API pattern from upload_file_via_api_example.py
"""

import requests
import os
import sys
from datetime import datetime

# Configuration from .env
API_URL = "https://brim.radiant-tst.d3b.io"
API_TOKEN = "t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj"
PROJECT_ID = 19

def download_results(output_path="pilot_output/iteration_2_results/extractions.csv"):
    """
    Download results from BRIM project using the documented working API pattern.
    
    This follows the exact pattern from:
    - docs/upload_file_via_api_example.py
    - scripts/brim_api_workflow.py fetch_results()
    """
    
    print("\n" + "="*70)
    print(f"📥 Downloading Results from Project {PROJECT_ID}")
    print("="*70)
    print(f"🌐 API URL: {API_URL}")
    print(f"📁 Output: {output_path}")
    print()
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Prepare headers (same as upload_file_via_api_example.py)
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "*/*"
    }
    
    # Prepare payload (same as brim_api_workflow.py fetch_results())
    endpoint = f"{API_URL.rstrip('/')}/api/v1/results/"
    payload = {
        'project_id': str(PROJECT_ID),
        'detailed_export': True,
        'patient_export': False,
        'include_null_in_export': False
    }
    
    print(f"🔗 Endpoint: {endpoint}")
    print(f"📦 Payload: {payload}")
    print()
    
    try:
        print("📤 Sending request...")
        response = requests.post(endpoint, headers=headers, json=payload, stream=True)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        print()
        
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '')
        
        # If we get CSV, export is complete
        if 'text/csv' in content_type:
            print("✅ Export ready! Downloading CSV...")
            
            # Save CSV file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(output_path)
            print(f"💾 Saved to: {output_path}")
            print(f"📊 File size: {file_size:,} bytes")
            print()
            print("="*70)
            print("✅ SUCCESS: Results downloaded!")
            print("="*70)
            return True
            
        # If JSON, check status
        elif 'application/json' in content_type:
            result = response.json()
            print("📋 Response JSON:")
            print(result)
            print()
            
            # Check the 'data' object for actual status
            data = result.get('data', {})
            is_complete = data.get('is_complete', False)
            status_display = data.get('status_display', 'unknown')
            api_session_id = data.get('api_session_id', 'unknown')
            
            print(f"📊 Status Display: {status_display}")
            print(f"📋 API Session ID: {api_session_id}")
            print(f"✅ Complete: {is_complete}")
            print()
            
            if is_complete:
                print("✅ Export is complete! Try again to download CSV.")
                return False
            elif status_display in ['Running', 'Pending', 'In Progress']:
                print("⏳ Export still running. Wait and try again.")
                message = data.get('message', 'No message')
                print(f"   Message: {message}")
                return False
            else:
                print(f"⚠️ Unexpected status: {status_display}")
                return False
        else:
            print(f"⚠️ Unexpected content type: {content_type}")
            print("Response text:")
            print(response.text[:500])
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response text: {e.response.text[:500]}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n🚀 BRIM Project 19 Results Downloader")
    print("Using documented working API pattern from:")
    print("  - docs/upload_file_via_api_example.py")
    print("  - scripts/brim_api_workflow.py")
    
    success = download_results()
    
    if success:
        print("\n✅ Next steps:")
        print("   1. Run validation: python3 scripts/automated_brim_validation.py")
        print("   2. Compare iterations")
    else:
        print("\n⚠️ Download not complete yet.")
        print("   If extraction is still running, wait a few minutes and try again.")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
