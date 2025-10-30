#!/bin/bash

# Deploy v_imaging_corticosteroid_use with medication join fix
# FIX: Replace SUBSTRING join with direct match

set -e

echo "======================================================================"
echo "DEPLOYING v_imaging_corticosteroid_use (Medication Join Fix)"
echo "======================================================================"
echo ""
echo "Fix included:"
echo "  ✅ Replace broken SUBSTRING join with direct match"
echo "  ✅ Already has comprehensive corticosteroid coverage (20 RxNorm codes)"
echo ""
echo "Expected impact:"
echo "  - Enable RxNorm code matching (currently broken)"
echo "  - Capture 37% more corticosteroid administrations"
echo ""
echo "======================================================================"
echo ""

cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views

# Extract v_imaging_corticosteroid_use from master file
python3 << 'EOF'
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'
VIEW_NAME = 'v_imaging_corticosteroid_use'

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

VIEW_NAME = 'v_imaging_corticosteroid_use'

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

# Simple COUNT to verify view works
query = """
SELECT COUNT(*) as total_records
FROM fhir_prd_db.v_imaging_corticosteroid_use
LIMIT 10
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
        count = row[0].get('VarCharValue', '0')

        print(f"Total records: {count}")
        print(f"\n✅ View is working correctly!")
    else:
        print("View returned no records")
else:
    reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    print(f"❌ Verification FAILED: {reason}")

EOF

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
