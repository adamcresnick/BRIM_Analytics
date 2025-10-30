#!/bin/bash

# Deploy v_unified_patient_timeline (Version 2.3 - Streamlined)
# CHANGES:
# - Removed 6 specialized/summary views (354 lines)
# - Streamlined from 14 sources to 8 core clinical event sources
# - Updated documentation to Version 2.3

set -e

echo "======================================================================"
echo "DEPLOYING v_unified_patient_timeline (Version 2.3 - Streamlined)"
echo "======================================================================"
echo ""
echo "Changes included:"
echo "  ✅ Removed v_radiation_summary (patient-level summary)"
echo "  ✅ Removed v_ophthalmology_assessments (specialized)"
echo "  ✅ Removed v_audiology_assessments (specialized)"
echo "  ✅ Removed v_autologous_stem_cell_transplant (patient-level)"
echo "  ✅ Removed v_autologous_stem_cell_collection (specialized)"
echo "  ✅ Removed v_imaging_corticosteroid_use (derived relationship)"
echo ""
echo "Remaining sources (8 core event types):"
echo "  - v_diagnoses"
echo "  - v_procedures_tumor"
echo "  - v_imaging"
echo "  - v_chemo_medications"
echo "  - v_visits_unified"
echo "  - v_measurements"
echo "  - v_molecular_tests"
echo "  - v_radiation_treatment_appointments"
echo ""
echo "======================================================================"
echo ""

cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views

# Extract v_unified_patient_timeline from master file
python3 << 'EOF'
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'
VIEW_NAME = 'v_unified_patient_timeline'

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

VIEW_NAME = 'v_unified_patient_timeline'

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

# Test query to verify timeline structure
query = """
SELECT
    source_view,
    COUNT(*) as event_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY source_view
ORDER BY event_count DESC
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
    print(f"{'Source View':<40} {'Events':>15} {'Patients':>15}")
    print("=" * 80)

    total_events = 0
    source_count = 0

    for i, row in enumerate(results['ResultSet']['Rows'][1:]):  # Skip header
        source = row['Data'][0].get('VarCharValue', 'NULL')
        events = row['Data'][1].get('VarCharValue', '0')
        patients = row['Data'][2].get('VarCharValue', '0')

        print(f"{source:<40} {int(events):>15,} {int(patients):>15,}")
        total_events += int(events)
        source_count += 1

    print("=" * 80)
    print(f"{'TOTAL':<40} {total_events:>15,}")
    print(f"Total source views: {source_count}")
    print("")

    if source_count == 8:
        print("✅ Correct! Timeline now has 8 core event sources")
    else:
        print(f"⚠️  Warning: Expected 8 sources, found {source_count}")

    # Check that removed views are NOT present
    removed_views = [
        'v_radiation_summary',
        'v_ophthalmology_assessments',
        'v_audiology_assessments',
        'v_autologous_stem_cell_transplant',
        'v_autologous_stem_cell_collection',
        'v_imaging_corticosteroid_use'
    ]

    sources_found = [row['Data'][0].get('VarCharValue', '') for row in results['ResultSet']['Rows'][1:]]

    print("\n📋 Removed views verification:")
    all_removed = True
    for view in removed_views:
        if view in sources_found:
            print(f"   ❌ {view} - STILL PRESENT (should be removed!)")
            all_removed = False
        else:
            print(f"   ✅ {view} - confirmed removed")

    if all_removed:
        print("\n✅ All 6 views successfully removed from timeline!")

else:
    reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    print(f"❌ Verification FAILED: {reason}")

EOF

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
