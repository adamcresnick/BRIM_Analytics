#!/usr/bin/env python3
"""
Investigate the medication_request → medication join to fix RxNorm code matching.
"""

import boto3
import time
import pandas as pd

def run_query(athena, query, description):
    """Run Athena query and return results."""
    print(f"\n{description}")
    print("=" * 80)

    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
    )

    query_id = response['QueryExecutionId']

    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        time.sleep(2)

    if status == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
        return results
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ Query FAILED: {reason}")
        return None

def main():
    print("=" * 80)
    print("MEDICATION_REQUEST → MEDICATION JOIN INVESTIGATION")
    print("=" * 80)

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Query 1: Check medication_reference_reference format
    query1 = """
    SELECT
        CASE
            WHEN medication_reference_reference LIKE 'Medication/%' THEN 'Prefixed (Medication/)'
            WHEN medication_reference_reference LIKE 'urn:uuid:%' THEN 'URN format'
            WHEN medication_reference_reference IS NULL THEN 'NULL'
            ELSE 'Direct ID'
        END as reference_format,
        COUNT(*) as count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
    FROM fhir_prd_db.medication_request
    WHERE status IN ('active', 'completed', 'on-hold', 'stopped')
    GROUP BY 1
    ORDER BY count DESC
    """

    results1 = run_query(athena, query1, "Query 1: medication_reference_reference format analysis")

    if results1 and len(results1['ResultSet']['Rows']) > 1:
        print(f"\n{'Format':<30} {'Count':<15} {'Percentage':<15}")
        print("-" * 60)
        for row in results1['ResultSet']['Rows'][1:]:
            format_type = row['Data'][0].get('VarCharValue', '')
            count = row['Data'][1].get('VarCharValue', '0')
            pct = row['Data'][2].get('VarCharValue', '0')
            print(f"{format_type:<30} {count:<15} {float(pct):.1f}%")

    # Query 2: Sample medication_reference_reference values
    query2 = """
    SELECT
        medication_reference_reference,
        medication_reference_display
    FROM fhir_prd_db.medication_request
    WHERE status IN ('active', 'completed', 'on-hold', 'stopped')
        AND medication_reference_reference IS NOT NULL
    LIMIT 10
    """

    results2 = run_query(athena, query2, "Query 2: Sample medication_reference_reference values")

    if results2 and len(results2['ResultSet']['Rows']) > 1:
        print(f"\nSample values:")
        for row in results2['ResultSet']['Rows'][1:]:
            ref = row['Data'][0].get('VarCharValue', '')
            display = row['Data'][1].get('VarCharValue', '')
            print(f"  Reference: {ref}")
            print(f"  Display: {display}")
            print()

    # Query 3: Test different join approaches
    query3 = """
    WITH join_test AS (
        SELECT
            'Direct match' as join_method,
            COUNT(DISTINCT mr.id) as medication_requests,
            COUNT(DISTINCT mr.subject_reference) as patients
        FROM fhir_prd_db.medication_request mr
        INNER JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
        WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')

        UNION ALL

        SELECT
            'SUBSTRING(12)' as join_method,
            COUNT(DISTINCT mr.id) as medication_requests,
            COUNT(DISTINCT mr.subject_reference) as patients
        FROM fhir_prd_db.medication_request mr
        INNER JOIN fhir_prd_db.medication m
            ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
        WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')

        UNION ALL

        SELECT
            'SUBSTRING(13)' as join_method,
            COUNT(DISTINCT mr.id) as medication_requests,
            COUNT(DISTINCT mr.subject_reference) as patients
        FROM fhir_prd_db.medication_request mr
        INNER JOIN fhir_prd_db.medication m
            ON m.id = SUBSTRING(mr.medication_reference_reference, 13)
        WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    )
    SELECT * FROM join_test
    ORDER BY medication_requests DESC
    """

    results3 = run_query(athena, query3, "Query 3: Testing different join approaches")

    if results3 and len(results3['ResultSet']['Rows']) > 1:
        print(f"\n{'Join Method':<20} {'Medication Requests':<25} {'Patients':<15}")
        print("-" * 60)
        for row in results3['ResultSet']['Rows'][1:]:
            method = row['Data'][0].get('VarCharValue', '')
            requests = row['Data'][1].get('VarCharValue', '0')
            patients = row['Data'][2].get('VarCharValue', '0')
            print(f"{method:<20} {requests:<25} {patients:<15}")

    # Query 4: Test corticosteroid capture with correct join
    query4 = """
    SELECT
        'Direct match + RxNorm codes' as approach,
        COUNT(DISTINCT mr.id) as medication_requests,
        COUNT(DISTINCT mr.subject_reference) as patients
    FROM fhir_prd_db.medication_request mr
    INNER JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')
        AND mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
    """

    results4 = run_query(athena, query4, "Query 4: Corticosteroid capture with CORRECT join")

    if results4 and len(results4['ResultSet']['Rows']) > 1:
        row = results4['ResultSet']['Rows'][1]['Data']
        approach = row[0].get('VarCharValue', '')
        requests = row[1].get('VarCharValue', '0')
        patients = row[2].get('VarCharValue', '0')
        print(f"\n✅ {approach}:")
        print(f"   Medication requests: {requests}")
        print(f"   Patients: {patients}")

    # Query 5: Compare with text matching
    query5 = """
    SELECT
        COUNT(DISTINCT mr.id) as medication_requests,
        COUNT(DISTINCT mr.subject_reference) as patients
    FROM fhir_prd_db.medication_request mr
    WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')
        AND (
            LOWER(mr.medication_reference_display) LIKE '%dexamethasone%'
            OR LOWER(mr.medication_reference_display) LIKE '%prednisone%'
            OR LOWER(mr.medication_reference_display) LIKE '%methylprednisolone%'
            OR LOWER(mr.medication_reference_display) LIKE '%hydrocortisone%'
            OR LOWER(mr.medication_reference_display) LIKE '%prednisolone%'
        )
    """

    results5 = run_query(athena, query5, "Query 5: Corticosteroid capture via TEXT MATCHING")

    if results5 and len(results5['ResultSet']['Rows']) > 1:
        row = results5['ResultSet']['Rows'][1]['Data']
        requests = row[0].get('VarCharValue', '0')
        patients = row[1].get('VarCharValue', '0')
        print(f"\n✅ Text matching approach:")
        print(f"   Medication requests: {requests}")
        print(f"   Patients: {patients}")

    # Summary
    print("\n" + "=" * 80)
    print("FINDINGS & RECOMMENDATIONS")
    print("=" * 80)

if __name__ == '__main__':
    main()
