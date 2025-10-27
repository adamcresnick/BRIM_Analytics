#!/usr/bin/env python3
"""
Direct deployment of v_autologous_stem_cell_collection with mobilization agent fixes.
"""

import boto3
import time
import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'
VIEW_NAME = 'v_autologous_stem_cell_collection'

def extract_view_clean(view_name):
    """Extract view definition cleanly by finding exact boundaries."""
    with open(MASTER_FILE, 'r') as f:
        content = f.read()

    # Find the CREATE statement for this specific view
    view_pattern = f'CREATE OR REPLACE VIEW fhir_prd_db.{view_name} AS'
    view_start = content.find(view_pattern)

    if view_start == -1:
        raise ValueError(f"View {view_name} not found in {MASTER_FILE}")

    # Find the next "-- VIEW:" comment marker (this marks the start of the next view)
    next_marker = content.find('\n-- VIEW:', view_start + len(view_pattern))

    if next_marker == -1:
        # This is the last view in the file
        view_def = content[view_start:]
    else:
        # Extract up to (but not including) the next view marker
        view_def = content[view_start:next_marker]

    # Clean up the view definition
    view_def = view_def.rstrip()

    # Remove any trailing comment lines that start with "--"
    lines = view_def.split('\n')
    while lines and lines[-1].strip().startswith('--'):
        lines.pop()

    view_def = '\n'.join(lines).rstrip()

    # Ensure it ends with a semicolon
    if not view_def.endswith(';'):
        view_def += ';'

    return view_def

def deploy_to_athena(view_def):
    """Deploy view definition to Athena."""
    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    print(f"Deploying {VIEW_NAME} to Athena...")
    print(f"View definition length: {len(view_def):,} characters")

    # Execute the CREATE VIEW statement
    response = athena.start_query_execution(
        QueryString=view_def,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
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
        return True
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"\n❌ {VIEW_NAME} deployment FAILED:")
        print(f"   {reason}")
        return False

def verify_deployment():
    """Verify the view works with a simple query."""
    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    print(f"\nVerifying {VIEW_NAME} deployment...")

    query = f"""
    SELECT COUNT(*) as total_records
    FROM fhir_prd_db.{VIEW_NAME}
    LIMIT 10
    """

    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )

    query_id = response['QueryExecutionId']

    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        time.sleep(2)

    if status == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_id)
        count = results['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
        print(f"✅ Verification passed! Total records: {count}")
        return True
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ Verification FAILED: {reason}")
        return False

if __name__ == '__main__':
    print("=" * 80)
    print(f"DEPLOYING {VIEW_NAME}")
    print("=" * 80)
    print("\nFixes included:")
    print("  ❌ REMOVED incorrect RxNorm codes:")
    print("     - 105585 (methotrexate, NOT Filgrastim)")
    print("     - 139825 (insulin, NOT Filgrastim biosimilar)")
    print("     - 847232 (insulin, NOT Plerixafor)")
    print()
    print("  ✅ ADDED correct ingredient codes:")
    print("     - 68442 (Filgrastim)")
    print("     - 338036 (Pegfilgrastim)")
    print("     - 733003 (Plerixafor)")
    print()
    print("  ✅ ADDED major formulation codes:")
    print("     - 1649944, 1649963 (filgrastim - 2,860 requests)")
    print("     - 727539 (pegfilgrastim - 2,303 requests)")
    print("     - 828700 (plerixafor - 107 requests)")
    print()
    print("  ✅ ADDED comprehensive brand names:")
    print("     - Filgrastim: Neupogen, Granix, Zarxio, Nivestim")
    print("     - Pegfilgrastim: Neulasta, Fulphila, Udenyca, Ziextenzo, Nyvepria")
    print("     - Plerixafor: Mozobil")
    print()
    print("=" * 80)
    print()

    try:
        # Extract view definition
        print("Step 1: Extracting view from master file...")
        view_def = extract_view_clean(VIEW_NAME)
        print(f"✓ Extracted {len(view_def):,} characters")

        # Deploy to Athena
        print("\nStep 2: Deploying to Athena...")
        if deploy_to_athena(view_def):
            # Verify deployment
            print("\nStep 3: Verifying deployment...")
            if verify_deployment():
                print("\n" + "=" * 80)
                print("✅ DEPLOYMENT COMPLETE AND VERIFIED")
                print("=" * 80)
            else:
                print("\n⚠️  Deployment succeeded but verification failed")
        else:
            print("\n❌ Deployment failed")
            exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
