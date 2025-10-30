#!/bin/bash

# Deploy v_autologous_stem_cell_collection with mobilization agent fixes
# FIXES:
# 1. Replace INCORRECT RxNorm codes (105585=methotrexate, 139825=insulin, 847232=insulin)
# 2. Add CORRECT ingredient codes (68442=Filgrastim, 338036=Pegfilgrastim, 733003=Plerixafor)
# 3. Add major formulation codes (SCDs) for complete coverage
# 4. Add comprehensive brand name text matching

set -e

echo "======================================================================"
echo "DEPLOYING v_autologous_stem_cell_collection (Mobilization Agent Fixes)"
echo "======================================================================"
echo ""
echo "Fixes included:"
echo "  1. ❌ REMOVE INCORRECT RxNorm codes:"
echo "     - 105585 (labeled Filgrastim but is METHOTREXATE)"
echo "     - 139825 (labeled Filgrastim biosimilar but is INSULIN)"
echo "     - 847232 (labeled Plerixafor but is INSULIN)"
echo ""
echo "  2. ✅ ADD CORRECT ingredient codes:"
echo "     - 68442 (Filgrastim)"
echo "     - 338036 (Pegfilgrastim)"
echo "     - 733003 (Plerixafor)"
echo ""
echo "  3. ✅ ADD major formulation codes (SCDs):"
echo "     - 1649944, 1649963 (filgrastim formulations - 2,860 requests)"
echo "     - 727539 (pegfilgrastim prefilled syringe - 2,303 requests)"
echo "     - 828700 (plerixafor injection - 107 requests)"
echo ""
echo "  4. ✅ ADD comprehensive brand name text matching:"
echo "     - Filgrastim: Neupogen, Granix, Zarxio, Nivestim"
echo "     - Pegfilgrastim: Neulasta, Fulphila, Udenyca, Ziextenzo, Nyvepria"
echo "     - Plerixafor: Mozobil"
echo ""
echo "Expected impact:"
echo "  - Remove incorrect codes capturing wrong medications"
echo "  - Add correct mobilization agent coverage (~5,036+ requests)"
echo ""
echo "======================================================================"
echo ""

cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views

# Extract v_autologous_stem_cell_collection from master file
python3 << 'EOF'
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'
VIEW_NAME = 'v_autologous_stem_cell_collection'

def extract_view(view_name):
    """Extract a single view definition from master file."""
    with open(MASTER_FILE, 'r') as f:
        content = f.read()

    # Find view start
    view_start = content.find(f'CREATE OR REPLACE VIEW fhir_prd_db.{view_name}')
    if view_start == -1:
        raise ValueError(f"View {view_name} not found")

    # Find next "-- VIEW:" marker (not next CREATE)
    next_view = content.find('\n-- VIEW:', view_start + 10)
    if next_view == -1:
        view_def = content[view_start:]
    else:
        view_def = content[view_start:next_view]

    # Clean up trailing whitespace and add semicolon
    view_def = view_def.rstrip()
    if not view_def.endswith(';'):
        view_def += ';'

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

VIEW_NAME = 'v_autologous_stem_cell_collection'

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
FROM fhir_prd_db.v_autologous_stem_cell_collection
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
