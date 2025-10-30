#!/bin/bash

# Deploy medication join fixes for v_autologous_stem_cell_collection and v_imaging_corticosteroid_use
# This fixes the broken SUBSTRING joins that prevented RxNorm code matching

set -e

echo "======================================================================"
echo "DEPLOYING MEDICATION JOIN FIXES"
echo "======================================================================"
echo ""
echo "Views to update:"
echo "  1. v_autologous_stem_cell_collection (line 3018)"
echo "  2. v_imaging_corticosteroid_use (line 3827)"
echo ""
echo "Fix: Replace SUBSTRING(mr.medication_reference_reference, 12)"
echo "     with direct match: mr.medication_reference_reference"
echo ""
echo "Expected impact:"
echo "  - v_imaging_corticosteroid_use: +37% corticosteroid coverage"
echo "  - v_autologous_stem_cell_collection: Enable RxNorm matching"
echo ""
echo "======================================================================"
echo ""

cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views

# Extract view definitions from master file
python3 << 'EOF'
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'

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

# Extract views
print("Extracting view definitions...")

views = [
    'v_autologous_stem_cell_collection',
    'v_imaging_corticosteroid_use'
]

for view_name in views:
    view_def = extract_view(view_name)

    # Save to individual file
    output_file = f'{view_name}.sql'
    with open(output_file, 'w') as f:
        f.write(view_def)

    print(f"  ✓ Extracted {view_name} ({len(view_def)} chars)")

print("\n✅ View definitions extracted successfully")
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

session = boto3.Session(profile_name='radiant-prod')
athena = session.client('athena', region_name='us-east-1')

views = [
    'v_autologous_stem_cell_collection',
    'v_imaging_corticosteroid_use'
]

def deploy_view(view_name):
    """Deploy a view to Athena."""
    print(f"\n{'='*80}")
    print(f"Deploying {view_name}...")
    print(f"{'='*80}")

    # Read view definition
    with open(f'{view_name}.sql', 'r') as f:
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
        print(f"✅ {view_name} deployed successfully!")
        return True
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ {view_name} deployment FAILED: {reason}")
        return False

# Deploy all views
success_count = 0
for view_name in views:
    if deploy_view(view_name):
        success_count += 1

print(f"\n{'='*80}")
print("DEPLOYMENT SUMMARY")
print(f"{'='*80}")
print(f"Successfully deployed: {success_count}/{len(views)} views")

if success_count == len(views):
    print("\n✅ ALL VIEWS DEPLOYED SUCCESSFULLY")
else:
    print(f"\n⚠️  {len(views) - success_count} views failed to deploy")

EOF

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
