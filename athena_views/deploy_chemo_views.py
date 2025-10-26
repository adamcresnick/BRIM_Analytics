#!/usr/bin/env python3
"""
Deploy chemotherapy views to Athena
"""
import boto3
import time
import sys
from pathlib import Path

def deploy_view(athena_client, sql_file_path, view_name):
    """Deploy a single view to Athena"""
    print(f"Deploying {view_name}...")

    # Read SQL file
    with open(sql_file_path, 'r') as f:
        query_string = f.read()

    # Start query execution
    response = athena_client.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={
            'Database': 'fhir_prd_db'
        },
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )

    query_id = response['QueryExecutionId']
    print(f"{view_name} query ID: {query_id}")

    # Wait for completion
    print(f"Waiting for {view_name} to complete...")
    for i in range(120):  # Wait up to 10 minutes
        response = athena_client.get_query_execution(QueryExecutionId=query_id)
        status = response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            print(f"{view_name} deployed successfully!")
            return True
        elif status in ['FAILED', 'CANCELLED']:
            print(f"{view_name} deployment failed with status: {status}")
            if 'StateChangeReason' in response['QueryExecution']['Status']:
                print(f"Error: {response['QueryExecution']['Status']['StateChangeReason']}")
            return False
        else:
            if i % 6 == 0:  # Print status every 30 seconds
                print(f"Status: {status} - waiting...")
            time.sleep(5)

    print(f"{view_name} deployment timed out")
    return False

def main():
    """Main deployment function"""
    print("Deploying chemotherapy views to Athena...")

    # Create Athena client
    session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
    athena_client = session.client('athena')

    # Deploy views in order
    views = [
        ('views/V_CHEMOTHERAPY_DRUGS.sql', 'V_CHEMOTHERAPY_DRUGS'),
        ('views/V_CHEMO_MEDICATIONS.sql', 'V_CHEMO_MEDICATIONS')
    ]

    success = True
    for sql_file, view_name in views:
        if not Path(sql_file).exists():
            print(f"Error: SQL file {sql_file} not found")
            sys.exit(1)

        if not deploy_view(athena_client, sql_file, view_name):
            success = False
            break

    if success:
        print("\nAll chemotherapy views deployed successfully!")
    else:
        print("\nDeployment failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()