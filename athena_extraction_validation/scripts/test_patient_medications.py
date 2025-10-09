#!/usr/bin/env python3
"""
Test patient_medications table
"""

import boto3
import time

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

queries = [
    ("patient_medications with patient_id", """
        SELECT COUNT(*) as count
        FROM fhir_v2_prd_db.patient_medications
        WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    """),
    ("patient_medications sample rows", """
        SELECT *
        FROM fhir_v2_prd_db.patient_medications
        WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        LIMIT 5
    """),
]

for name, query in queries:
    print(f"\nTesting {name}...")
    try:
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': 'fhir_v2_prd_db'},
            ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
        )
        
        query_id = response['QueryExecutionId']
        
        while True:
            status = athena.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(1)
        
        if state == 'SUCCEEDED':
            results = athena.get_query_results(QueryExecutionId=query_id)
            rows = results['ResultSet']['Rows']
            
            if "COUNT" in name:
                count = rows[1]['Data'][0]['VarCharValue']
                print(f"  ✓ Found {count} records")
            else:
                print(f"  ✓ Retrieved {len(rows)-1} sample rows")
                if len(rows) > 1:
                    # Show column names
                    cols = [col.get('VarCharValue', '') for col in rows[0]['Data']]
                    print(f"  Columns ({len(cols)}): {', '.join(cols[:10])}...")
        else:
            print(f"  ✗ Failed")
    except Exception as e:
        print(f"  ✗ Error: {str(e)[:100]}")
