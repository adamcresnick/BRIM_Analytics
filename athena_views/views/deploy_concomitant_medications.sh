#!/bin/bash

# Deploy v_concomitant_medications with corticosteroid fixes
# FIXES:
# 1. Remove glucose (4850) from corticosteroid list
# 2. Add all 20 corticosteroid RxNorm ingredient codes
# 3. Add comprehensive text matching fallback

set -e

echo "======================================================================"
echo "DEPLOYING v_concomitant_medications (Corticosteroid Fixes)"
echo "======================================================================"
echo ""
echo "Fixes included:"
echo "  1. ❌ Remove RxNorm 4850 (glucose - NOT a corticosteroid!)"
echo "  2. ✅ Add all 20 corticosteroid RxNorm ingredient codes"
echo "  3. ✅ Add comprehensive text matching for brands/generics"
echo ""
echo "Expected impact:"
echo "  - Remove 22,060 glucose administrations from corticosteroid count"
echo "  - Add comprehensive corticosteroid coverage (8 found in data)"
echo ""
echo "======================================================================"
echo ""

cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views

# Extract v_concomitant_medications from master file
python3 << 'EOF'
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'
VIEW_NAME = 'v_concomitant_medications'

def extract_view(view_name):
    """Extract a single view definition from master file."""
    with open(MASTER_FILE, 'r') as f:
        content = f.read()

    # Find view start
    view_start = content.find(f'CREATE OR REPLACE VIEW fhir_prd_db.{view_name}')
    if view_start == -1:
        raise ValueError(f"View {view_name} not found")

    # Find next CREATE statement or end of file
    next_view = content.find('CREATE OR REPLACE VIEW', view_start + 10)
    if next_view == -1:
        view_def = content[view_start:]
    else:
        view_def = content[view_start:next_view]

    # Clean up trailing whitespace
    view_def = view_def.rstrip() + ';'

    return view_def

# Extract view
print(f"Extracting {VIEW_NAME} from {MASTER_FILE}...")
view_def = extract_view(VIEW_NAME)

# Save to individual file
output_file = f'{VIEW_NAME}.sql'
with open(output_file, 'w') as f:
    f.write(view_def)

print(f"✓ Extracted {VIEW_NAME} ({len(view_def):,} characters)")
print(f"✓ Saved to {output_file}")

EOF

# Deploy to Athena
echo ""
echo "======================================================================"
echo "DEPLOYING TO ATHENA"
echo "======================================================================"
echo ""

python3 << 'EOF'
import boto3
import time

VIEW_NAME = 'v_concomitant_medications'

session = boto3.Session(profile_name='radiant-prod')
athena = session.client('athena', region_name='us-east-1')

print(f"Deploying {VIEW_NAME}...")

# Read view definition
with open(f'{VIEW_NAME}.sql', 'r') as f:
    view_def = f.read()

# Execute in Athena
response = athena.start_query_execution(
    QueryString=view_def,
    QueryExecutionContext={'Database': 'fhir_prd_db'},
    ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
)

query_id = response['QueryExecutionId']
print(f"Query ID: {query_id}")

# Wait for completion
while True:
    result = athena.get_query_execution(QueryExecutionId=query_id)
    status = result['QueryExecution']['Status']['State']

    if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break

    print(f"Status: {status}...")
    time.sleep(2)

if status == 'SUCCEEDED':
    print(f"\n✅ {VIEW_NAME} deployed successfully!")
else:
    reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    print(f"\n❌ {VIEW_NAME} deployment FAILED: {reason}")
    exit(1)

EOF

# Verify deployment
echo ""
echo "======================================================================"
echo "VERIFYING DEPLOYMENT"
echo "======================================================================"
echo ""

python3 << 'EOF'
import boto3
import time

session = boto3.Session(profile_name='radiant-prod')
athena = session.client('athena', region_name='us-east-1')

# Test query to verify corticosteroid categorization
query = """
SELECT
    medication_category,
    COUNT(DISTINCT patient_fhir_id) as patients,
    COUNT(DISTINCT medication_request_fhir_id) as medication_requests
FROM fhir_prd_db.v_concomitant_medications
WHERE medication_category = 'corticosteroid'
GROUP BY medication_category
"""

print("Running verification query...")
response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': 'fhir_prd_db'},
    ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
)

query_id = response['QueryExecutionId']
print(f"Query ID: {query_id}")

while True:
    result = athena.get_query_execution(QueryExecutionId=query_id)
    status = result['QueryExecution']['Status']['State']

    if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break

    print(f"Status: {status}...")
    time.sleep(2)

if status == 'SUCCEEDED':
    results = athena.get_query_results(QueryExecutionId=query_id)

    print(f"\n✅ Verification Results:")
    print("=" * 80)

    if len(results['ResultSet']['Rows']) > 1:
        row = results['ResultSet']['Rows'][1]['Data']
        category = row[0].get('VarCharValue', '')
        patients = row[1].get('VarCharValue', '0')
        requests = row[2].get('VarCharValue', '0')

        print(f"Category: {category}")
        print(f"Patients: {patients}")
        print(f"Medication requests: {requests}")

        requests_int = int(requests)
        print(f"\n📊 Analysis:")
        if requests_int < 50000:
            print(f"   ✅ Good! Requests ({requests_int:,}) is < 50,000")
            print(f"   ✅ Glucose (22,060 requests) appears to be removed")
        else:
            print(f"   ⚠️  Warning: Requests ({requests_int:,}) is still high")
            print(f"   ⚠️  Glucose may still be included")
    else:
        print("No corticosteroid records found")
else:
    reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    print(f"❌ Verification FAILED: {reason}")

EOF

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
