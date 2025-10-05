#!/usr/bin/env python3
"""
Sample a few "Pathology study" documents to check if they're surgical pathology or lab results.
"""

import boto3
import csv
import html
import re

# Configuration
AWS_PROFILE = "343218191717_AWSAdministratorAccess"
AWS_REGION = "us-east-1"
S3_BUCKET = "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline"
S3_PREFIX = "prd/source/Binary/"

# Initialize AWS clients
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
s3 = session.client('s3')

# Read annotated binaries
csv.field_size_limit(10000000)
with open('pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files_annotated.csv', 'r') as f:
    reader = csv.DictReader(f)
    docs = list(reader)

# Get pathology documents
pathology_docs = [d for d in docs if 'pathology' in d['document_type'].lower()]

print("="*80)
print("SAMPLING PATHOLOGY STUDY DOCUMENTS")
print("="*80)
print()

# Sample: 2021-03-18 (after 2nd surgery), 2024-09-09 (recent), 2022-06-06 (mid-range)
sample_dates = ['2021-03-18', '2024-09-09', '2022-06-06']

for sample_date in sample_dates:
    matching = [d for d in pathology_docs if d['document_date'].startswith(sample_date)]
    if matching:
        doc = matching[0]

        print(f"\nSample: {sample_date}")
        print("-" * 80)
        print(f"Document Reference ID: {doc['document_reference_id'][:50]}...")
        print(f"Binary ID: {doc['binary_id']}")
        print(f"Content Type: {doc['content_type']}")

        # Extract binary ID and fetch from S3
        binary_id = doc['binary_id'].replace('Binary/', '')
        s3_key = f"{S3_PREFIX}{binary_id.replace('.', '_')}"

        try:
            print(f"Fetching from S3: {s3_key[:80]}...")
            response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
            content = response['Body'].read()

            # Decode content
            if doc['content_type'] == 'text/html':
                text = content.decode('utf-8', errors='ignore')
                # Strip HTML tags for preview
                text_clean = re.sub(r'<[^>]+>', '', text)
                text_clean = html.unescape(text_clean)
                text_clean = re.sub(r'\s+', ' ', text_clean).strip()

                print(f"\nContent Preview (first 1000 chars):")
                print(text_clean[:1000])

                # Search for key indicators
                print("\n\nKey Indicators:")
                indicators = {
                    'SURGICAL PATHOLOGY': 'surgical pathology' in text.lower() or 'surgical path' in text.lower(),
                    'TISSUE/SPECIMEN': 'specimen' in text.lower() or 'tissue' in text.lower(),
                    'DIAGNOSIS': 'diagnosis:' in text.lower() or 'final diagnosis' in text.lower(),
                    'MICROSCOPIC': 'microscopic' in text.lower() or 'histology' in text.lower(),
                    'MOLECULAR/NGS': 'ngs' in text.lower() or 'next generation sequencing' in text.lower() or 'molecular' in text.lower(),
                    'LAB VALUES': 'wbc' in text.lower() or 'hemoglobin' in text.lower() or 'platelet' in text.lower(),
                    'CHEMISTRY': 'sodium' in text.lower() or 'potassium' in text.lower() or 'glucose' in text.lower()
                }

                for indicator, found in indicators.items():
                    status = "✅ FOUND" if found else "   ---"
                    print(f"  {status} | {indicator}")

            else:
                print(f"Content type {doc['content_type']} - binary preview not supported")
                print(f"Content size: {len(content)} bytes")

        except Exception as e:
            print(f"ERROR fetching document: {e}")

        print()

print()
print("="*80)
print("ANALYSIS COMPLETE")
print("="*80)
