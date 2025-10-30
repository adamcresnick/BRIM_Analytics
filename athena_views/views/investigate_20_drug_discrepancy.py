#!/usr/bin/env python3
"""
Investigate why 20-drug list shows FEWER results than 5-drug list.
This is unexpected - the 20-drug list should be a superset.
"""

import boto3
import time

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
    print(f"Query ID: {query_id}")

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
    print("INVESTIGATING 20-DRUG DISCREPANCY")
    print("=" * 80)
    print("\nWhy does the 20-drug list show FEWER results than the 5-drug list?")
    print("The 20-drug list should be a superset of the 5-drug list.")

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Query 1: Check if 5-drug codes are in 20-drug list
    print("\n" + "=" * 80)
    print("VERIFICATION: Are all 5 drugs included in the 20-drug list?")
    print("=" * 80)

    five_drugs = ['3264', '8640', '6902', '5492', '4850']
    twenty_drugs = [
        '3264', '8640', '8638', '6902', '5492', '1514', '10759',
        '2878', '22396', '7910', '29523', '4463', '55681',
        '12473', '21285', '21660', '2669799',
        '4452', '3256', '1312358'
    ]

    print(f"\n5-drug list: {five_drugs}")
    print(f"20-drug list: {twenty_drugs}")

    all_in_list = all(drug in twenty_drugs for drug in five_drugs)
    print(f"\n✅ All 5 drugs in 20-drug list: {all_in_list}")

    if not all_in_list:
        missing = [drug for drug in five_drugs if drug not in twenty_drugs]
        print(f"⚠️  Missing from 20-drug list: {missing}")

    # Query 2: Count for each individual drug in 5-drug list
    query_individual = """
    SELECT
        mcc.code_coding_code as rxnorm_code,
        mcc.code_coding_display as drug_name,
        COUNT(DISTINCT mr.subject_reference) as patients,
        COUNT(DISTINCT mr.id) as medication_requests
    FROM fhir_prd_db.medication_request mr
    LEFT JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    GROUP BY mcc.code_coding_code, mcc.code_coding_display
    ORDER BY medication_requests DESC
    """

    results = run_query(athena, query_individual, "Query: Individual Drug Coverage (5-drug list)")

    if results and len(results['ResultSet']['Rows']) > 1:
        print(f"\nDrug Breakdown:")
        print(f"{'RxNorm':<10} {'Drug Name':<40} {'Patients':<12} {'Requests':<12}")
        print("-" * 80)

        total_patients = set()
        total_requests = 0

        for row in results['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', 'N/A')
            patients = int(row['Data'][2].get('VarCharValue', '0'))
            requests = int(row['Data'][3].get('VarCharValue', '0'))
            print(f"{rxnorm:<10} {drug[:38]:<40} {patients:<12,} {requests:<12,}")
            total_requests += requests

        print("-" * 80)
        print(f"Note: Patient counts may overlap (same patient can receive multiple drugs)")

    # Query 3: Check if 20-drug query has additional WHERE conditions
    print("\n" + "=" * 80)
    print("HYPOTHESIS: Does the 20-drug query have different filtering logic?")
    print("=" * 80)
    print("\nLet me check the actual v_imaging_corticosteroid_use view definition...")

    # Query 4: Test if it's an IN clause issue (too many values?)
    query_split = """
    WITH five_drugs AS (
        SELECT DISTINCT
            mr.subject_reference as patient_fhir_id,
            mr.id as medication_request_id
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
        LEFT JOIN fhir_prd_db.medication_code_coding mcc
            ON mcc.medication_id = m.id
            AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        WHERE mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
            AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    ),
    additional_drugs AS (
        SELECT DISTINCT
            mr.subject_reference as patient_fhir_id,
            mr.id as medication_request_id
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
        LEFT JOIN fhir_prd_db.medication_code_coding mcc
            ON mcc.medication_id = m.id
            AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        WHERE mcc.code_coding_code IN (
            '8638', '1514', '10759', '2878', '22396', '7910',
            '29523', '4463', '55681', '12473', '21285', '21660',
            '2669799', '4452', '3256', '1312358'
        )
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    ),
    combined AS (
        SELECT patient_fhir_id, medication_request_id FROM five_drugs
        UNION
        SELECT patient_fhir_id, medication_request_id FROM additional_drugs
    )
    SELECT
        COUNT(DISTINCT patient_fhir_id) as patients,
        COUNT(DISTINCT medication_request_id) as medication_requests
    FROM combined
    """

    results_split = run_query(athena, query_split, "Query: Split approach (5-drug + 15-drug UNION)")

    if results_split:
        row = results_split['ResultSet']['Rows'][1]['Data']
        patients = int(row[0].get('VarCharValue', '0'))
        requests = int(row[1].get('VarCharValue', '0'))
        print(f"\n✅ Split UNION approach:")
        print(f"   Patients: {patients:,}")
        print(f"   Medication requests: {requests:,}")

    # Query 5: Test with all 20 in single IN clause again
    query_all_20 = """
    SELECT
        COUNT(DISTINCT mr.subject_reference) as patients,
        COUNT(DISTINCT mr.id) as medication_requests
    FROM fhir_prd_db.medication_request mr
    LEFT JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code IN (
        '3264', '8640', '8638', '6902', '5492', '1514', '10759',
        '2878', '22396', '7910', '29523', '4463', '55681',
        '12473', '21285', '21660', '2669799',
        '4452', '3256', '1312358'
    )
    AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    """

    results_20 = run_query(athena, query_all_20, "Query: All 20 drugs in single IN clause")

    if results_20:
        row = results_20['ResultSet']['Rows'][1]['Data']
        patients = int(row[0].get('VarCharValue', '0'))
        requests = int(row[1].get('VarCharValue', '0'))
        print(f"\n✅ Single IN clause with all 20 drugs:")
        print(f"   Patients: {patients:,}")
        print(f"   Medication requests: {requests:,}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY & DIAGNOSIS")
    print("=" * 80)
    print("\nPossible explanations for discrepancy:")
    print("1. CTEs with DISTINCT may introduce unexpected behavior")
    print("2. Query execution order may affect results")
    print("3. Check if previous test used different CTE structure")

if __name__ == '__main__':
    main()
