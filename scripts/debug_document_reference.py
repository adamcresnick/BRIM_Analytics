#!/usr/bin/env python3
"""Debug script to check DocumentReference and Binary structure."""

import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
s3 = session.client('s3', region_name='us-east-1')

# Get first DocumentReference file
response = s3.list_objects_v2(
    Bucket='radiant-prd-343218191717-us-east-1-prd-ehr-pipeline',
    Prefix='prd/ndjson/DocumentReference/',
    MaxKeys=10
)

files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.ndjson')]

for file_key in files[:5]:
    sql = """SELECT * FROM S3Object[*] s WHERE s.subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%' LIMIT 1"""
    
    try:
        result = s3.select_object_content(
            Bucket='radiant-prd-343218191717-us-east-1-prd-ehr-pipeline',
            Key=file_key,
            ExpressionType='SQL',
            Expression=sql,
            InputSerialization={'JSON': {'Type': 'LINES'}},
            OutputSerialization={'JSON': {'RecordDelimiter': '\n'}}
        )
        
        for event in result['Payload']:
            if 'Records' in event:
                payload = event['Records']['Payload'].decode('utf-8')
                if payload.strip():
                    doc = json.loads(payload.strip())
                    print("\n" + "="*70)
                    print("DOCUMENT REFERENCE FOUND:")
                    print("="*70)
                    print(f"ID: {doc.get('id')}")
                    print(f"Date: {doc.get('date')}")
                    print(f"Type: {doc.get('type', {}).get('text')}")
                    
                    content = doc.get('content', [])
                    if content:
                        attachment = content[0].get('attachment', {})
                        binary_url = attachment.get('url', '')
                        print(f"\nBinary URL: {binary_url}")
                        
                        if '/Binary/' in binary_url:
                            binary_id = binary_url.split('/Binary/')[-1]
                            print(f"Binary ID: {binary_id}")
                    
                    # Show full structure
                    print("\nFull structure:")
                    print(json.dumps(doc, indent=2)[:1000])
                    exit(0)
    except:
        continue

print("No documents found")
