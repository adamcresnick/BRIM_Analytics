#!/usr/bin/env python3
"""
Deploy updated v_concomitant_medications view to Athena.

Updates:
- Uses v_chemo_medications instead of hardcoded drug list (2,968 drugs vs 18)
- Consistent with validated chemotherapy drug reference
- Includes therapeutic normalization
"""

import boto3
import time

def deploy_view(athena):
    """Deploy updated v_concomitant_medications view."""

    # Read view SQL from ATHENA_VIEW_CREATION_QUERIES.sql
    with open('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/ATHENA_VIEW_CREATION_QUERIES.sql', 'r') as f:
        full_sql = f.read()

    # Extract v_concomitant_medications view (lines 3834-4133)
    lines = full_sql.split('\n')
    view_sql = '\n'.join(lines[3833:4133])  # 0-indexed, so line 3834 is index 3833

    print("=" * 100)
    print("DEPLOYING v_concomitant_medications VIEW")
    print("=" * 100)
    print("\nView updates:")
    print("- ✅ Uses v_chemo_medications (968 patients, 2,968 drugs)")
    print("- ✅ Therapeutic normalization (brand→generic)")
    print("- ✅ Excludes supportive care medications")
    print("- ❌ OLD: Hardcoded 18 drug RxNorm codes")

    print("\nDeploying view to Athena...")

    response = athena.start_query_execution(
        QueryString=view_sql,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
    )

    query_id = response['QueryExecutionId']
    print(f"Started query: {query_id}")

    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        print(f"Status: {status}...")
        time.sleep(2)

    if status == 'SUCCEEDED':
        print("✅ View deployed successfully!")
        return True
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ Deployment FAILED: {reason}")
        return False

def test_view(athena):
    """Test the deployed view."""

    print("\n" + "=" * 100)
    print("TESTING v_concomitant_medications VIEW")
    print("=" * 100)

    test_query = """
    SELECT
        COUNT(*) as total_records,
        COUNT(DISTINCT patient_fhir_id) as distinct_patients,
        COUNT(DISTINCT chemo_medication_fhir_id) as distinct_chemo_meds,
        COUNT(DISTINCT conmed_medication_fhir_id) as distinct_conmeds
    FROM fhir_prd_db.v_concomitant_medications
    """

    print("\nRunning test query...")

    response = athena.start_query_execution(
        QueryString=test_query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
    )

    query_id = response['QueryExecutionId']

    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        print(f"Status: {status}...")
        time.sleep(2)

    if status == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_id)

        # Parse results
        row = results['ResultSet']['Rows'][1]['Data']
        total_records = row[0].get('VarCharValue', '0')
        distinct_patients = row[1].get('VarCharValue', '0')
        distinct_chemo_meds = row[2].get('VarCharValue', '0')
        distinct_conmeds = row[3].get('VarCharValue', '0')

        print(f"\n✅ View test successful!")
        print(f"   Total records: {total_records}")
        print(f"   Distinct patients: {distinct_patients}")
        print(f"   Distinct chemo medications: {distinct_chemo_meds}")
        print(f"   Distinct concomitant medications: {distinct_conmeds}")

        return True
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ Test FAILED: {reason}")
        return False

def main():
    """Main deployment function."""

    print("\n" + "=" * 100)
    print("v_concomitant_medications DEPLOYMENT SCRIPT")
    print("=" * 100)
    print("\nInitializing AWS session...")

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    print("✓ AWS session initialized\n")

    # Deploy view
    if not deploy_view(athena):
        print("\n❌ Deployment failed. Exiting.")
        return 1

    # Test view
    if not test_view(athena):
        print("\n❌ Testing failed. View may be deployed but not working correctly.")
        return 1

    print("\n" + "=" * 100)
    print("DEPLOYMENT COMPLETE")
    print("=" * 100)
    print("\n✅ v_concomitant_medications view successfully deployed and tested!")
    print("\nNext steps:")
    print("1. Query the view to analyze concomitant medication patterns")
    print("2. Compare with v_chemo_medications to ensure consistency")
    print("3. Document any new insights about supportive care medications")

    return 0

if __name__ == '__main__':
    exit(main())
