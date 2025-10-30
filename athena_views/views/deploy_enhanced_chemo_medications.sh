#!/bin/bash

# Deploy enhanced v_chemo_medications (with CarePlan metadata)
# Date: 2025-10-28
# Changes: Added 24 new fields including cp_period_start and cp_period_end

set -e

cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views

echo "======================================================================"
echo "DEPLOYING ENHANCED v_chemo_medications"
echo "======================================================================"
echo ""
echo "Enhancements included:"
echo "  ✅ Added primary_care_plan_id to medication_based_on CTE"
echo "  ✅ Added 3 new CarePlan CTEs (categories, conditions, activities)"
echo "  ✅ Added 24 new fields:"
echo "     - 12 additional MedicationRequest metadata fields"
echo "     - 12 CarePlan fields (including cp_period_start, cp_period_end)"
echo "  ✅ Added 4 new CarePlan JOINs"
echo ""
echo "======================================================================"
echo ""

# Extract v_chemo_medications from master file
python3 << 'EOF'
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'
VIEW_NAME = 'v_chemo_medications'

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

    # Clean up - remove trailing whitespace and any extra semicolons
    view_def = view_def.rstrip()

    # Remove duplicate semicolons at end
    while view_def.endswith(';;'):
        view_def = view_def[:-1]

    # Ensure ends with single semicolon
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

VIEW_NAME = 'v_chemo_medications'

session = boto3.Session(profile_name='radiant-prod')
athena = session.client('athena', region_name='us-east-1')

print(f"Deploying {VIEW_NAME}...")

# Read view definition
with open(f'{VIEW_NAME}.sql', 'r') as f:
    view_def = f.read()

print(f"View SQL length: {len(view_def):,} characters")

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

# Verify deployment with test query
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

# Test query to verify new CarePlan fields exist
query = """
SELECT
    COUNT(*) as total_medications,
    COUNT(DISTINCT patient_fhir_id) as total_patients,
    COUNT(DISTINCT cp_id) as total_careplans,
    SUM(CASE WHEN cp_period_start IS NOT NULL THEN 1 ELSE 0 END) as meds_with_careplan_start,
    SUM(CASE WHEN cp_period_end IS NOT NULL THEN 1 ELSE 0 END) as meds_with_careplan_end
FROM fhir_prd_db.v_chemo_medications
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

    row = results['ResultSet']['Rows'][1]
    total_meds = row['Data'][0].get('VarCharValue', '0')
    total_patients = row['Data'][1].get('VarCharValue', '0')
    total_careplans = row['Data'][2].get('VarCharValue', '0')
    meds_with_start = row['Data'][3].get('VarCharValue', '0')
    meds_with_end = row['Data'][4].get('VarCharValue', '0')

    print(f"Total medications:            {int(total_meds):>10,}")
    print(f"Total patients:               {int(total_patients):>10,}")
    print(f"Total CarePlans referenced:   {int(total_careplans):>10,}")
    print(f"Meds with cp_period_start:    {int(meds_with_start):>10,}")
    print(f"Meds with cp_period_end:      {int(meds_with_end):>10,}")

    if int(total_careplans) > 0:
        careplan_coverage = (int(meds_with_start) / int(total_meds)) * 100
        print(f"\nCarePlan coverage: {careplan_coverage:.1f}% of medications")
        print("\n✅ New CarePlan fields successfully deployed!")
    else:
        print("\n⚠️  No CarePlans found - this is expected if medications aren't linked to treatment protocols")

else:
    reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
    print(f"❌ Verification FAILED: {reason}")

EOF

echo ""
echo "======================================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================================"
