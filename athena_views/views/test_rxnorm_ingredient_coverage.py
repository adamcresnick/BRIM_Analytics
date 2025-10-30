#!/usr/bin/env python3
"""
Test if RxNorm ingredient codes capture ALL formulations automatically.

RxNorm has a hierarchy where formulations (SCDs) link to ingredients (IN).
We need to verify that matching on ingredient codes automatically captures formulations.
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
    print("TEST: Do Ingredient Codes Capture Formulations?")
    print("=" * 80)

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Test 1: Direct match on ingredient code 3264 (dexamethasone)
    query_ingredient = """
    SELECT
        COUNT(DISTINCT mr.id) as medication_requests,
        COUNT(DISTINCT mr.subject_reference) as patients
    FROM fhir_prd_db.medication_request mr
    INNER JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code = '3264'
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    """

    results_ingredient = run_query(athena, query_ingredient, "Test 1: Ingredient Code 3264 (dexamethasone)")

    if results_ingredient:
        row = results_ingredient['ResultSet']['Rows'][1]['Data']
        requests_ingredient = int(row[0].get('VarCharValue', '0'))
        patients_ingredient = int(row[1].get('VarCharValue', '0'))
        print(f"\n✅ Ingredient code 3264:")
        print(f"   Medication requests: {requests_ingredient:,}")
        print(f"   Patients: {patients_ingredient:,}")

    # Test 2: Formulation codes (1116927, 1812194, 48933)
    query_formulations = """
    SELECT
        COUNT(DISTINCT mr.id) as medication_requests,
        COUNT(DISTINCT mr.subject_reference) as patients
    FROM fhir_prd_db.medication_request mr
    INNER JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code IN ('1116927', '1812194', '48933')
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    """

    results_formulations = run_query(athena, query_formulations, "Test 2: Formulation Codes (1116927, 1812194, 48933)")

    if results_formulations:
        row = results_formulations['ResultSet']['Rows'][1]['Data']
        requests_formulations = int(row[0].get('VarCharValue', '0'))
        patients_formulations = int(row[1].get('VarCharValue', '0'))
        print(f"\n✅ Formulation codes:")
        print(f"   Medication requests: {requests_formulations:,}")
        print(f"   Patients: {patients_formulations:,}")

    # Test 3: Combined (ingredient + formulations)
    query_combined = """
    SELECT
        COUNT(DISTINCT mr.id) as medication_requests,
        COUNT(DISTINCT mr.subject_reference) as patients
    FROM fhir_prd_db.medication_request mr
    INNER JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code IN ('3264', '1116927', '1812194', '48933')
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    """

    results_combined = run_query(athena, query_combined, "Test 3: Combined (ingredient + formulations)")

    if results_combined:
        row = results_combined['ResultSet']['Rows'][1]['Data']
        requests_combined = int(row[0].get('VarCharValue', '0'))
        patients_combined = int(row[1].get('VarCharValue', '0'))
        print(f"\n✅ Combined codes:")
        print(f"   Medication requests: {requests_combined:,}")
        print(f"   Patients: {patients_combined:,}")

    # Analysis
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    if results_ingredient and results_formulations and results_combined:
        print(f"\nIngredient alone: {requests_ingredient:,} requests")
        print(f"Formulations alone: {requests_formulations:,} requests")
        print(f"Combined: {requests_combined:,} requests")

        if requests_combined > requests_ingredient:
            additional = requests_combined - requests_ingredient
            print(f"\n⚠️  FORMULATIONS CAPTURE ADDITIONAL DATA!")
            print(f"   Additional requests from formulations: {additional:,} ({additional/requests_combined*100:.1f}%)")
            print(f"\n📋 RECOMMENDATION: Include BOTH ingredient AND formulation codes")
        else:
            print(f"\n✅ INGREDIENT CODE CAPTURES ALL FORMULATIONS")
            print(f"   No additional data from explicit formulation codes")
            print(f"\n📋 RECOMMENDATION: Ingredient codes are sufficient")

if __name__ == '__main__':
    main()
