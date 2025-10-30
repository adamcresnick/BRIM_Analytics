#!/usr/bin/env python3
"""
Empirically test corticosteroid coverage: 5-drug vs 20-drug approach.
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
    print("CORTICOSTEROID COVERAGE ANALYSIS")
    print("=" * 80)
    print("\nComparing 5-drug vs 20-drug corticosteroid identification")

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Query 1: Count using 5-drug approach (current v_concomitant_medications)
    query_5_drugs = """
    WITH corticosteroids_5_drugs AS (
        SELECT DISTINCT
            mr.subject_reference as patient_fhir_id,
            mr.id as medication_request_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as drug_name
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
        LEFT JOIN fhir_prd_db.medication_code_coding mcc
            ON mcc.medication_id = m.id
            AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        WHERE mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
            AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    )
    SELECT
        COUNT(DISTINCT patient_fhir_id) as patients,
        COUNT(DISTINCT medication_request_id) as medication_requests,
        COUNT(DISTINCT rxnorm_code) as distinct_rxnorm_codes
    FROM corticosteroids_5_drugs
    """

    results_5 = run_query(athena, query_5_drugs, "Query 1: 5-Drug Approach (Current v_concomitant_medications)")

    if results_5:
        row = results_5['ResultSet']['Rows'][1]['Data']
        patients_5 = row[0].get('VarCharValue', '0')
        med_requests_5 = row[1].get('VarCharValue', '0')
        rxnorm_5 = row[2].get('VarCharValue', '0')
        print(f"\n✅ 5-Drug Approach:")
        print(f"   Patients: {patients_5}")
        print(f"   Medication requests: {med_requests_5}")
        print(f"   Distinct RxNorm codes found: {rxnorm_5}")

    # Query 2: Count using 20-drug approach (v_imaging_corticosteroid_use)
    query_20_drugs = """
    WITH corticosteroids_20_drugs AS (
        SELECT DISTINCT
            mr.subject_reference as patient_fhir_id,
            mr.id as medication_request_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as drug_name
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
        LEFT JOIN fhir_prd_db.medication_code_coding mcc
            ON mcc.medication_id = m.id
            AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        WHERE mcc.code_coding_code IN (
            -- High Priority (Current 5 + 2 more)
            '3264', '8640', '8638', '6902', '5492', '1514', '10759',
            -- Medium Priority
            '2878', '22396', '7910', '29523', '4463', '55681',
            -- Lower Priority
            '12473', '21285', '21660', '2669799',
            -- Mineralocorticoids
            '4452', '3256', '1312358'
        )
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    )
    SELECT
        COUNT(DISTINCT patient_fhir_id) as patients,
        COUNT(DISTINCT medication_request_id) as medication_requests,
        COUNT(DISTINCT rxnorm_code) as distinct_rxnorm_codes
    FROM corticosteroids_20_drugs
    """

    results_20 = run_query(athena, query_20_drugs, "Query 2: 20-Drug Approach (v_imaging_corticosteroid_use)")

    if results_20:
        row = results_20['ResultSet']['Rows'][1]['Data']
        patients_20 = row[0].get('VarCharValue', '0')
        med_requests_20 = row[1].get('VarCharValue', '0')
        rxnorm_20 = row[2].get('VarCharValue', '0')
        print(f"\n✅ 20-Drug Approach:")
        print(f"   Patients: {patients_20}")
        print(f"   Medication requests: {med_requests_20}")
        print(f"   Distinct RxNorm codes found: {rxnorm_20}")

    # Query 3: Which drugs are we MISSING with 5-drug approach?
    query_missed = """
    WITH corticosteroids_5_drugs AS (
        SELECT DISTINCT
            mr.id as medication_request_id
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
        LEFT JOIN fhir_prd_db.medication_code_coding mcc
            ON mcc.medication_id = m.id
            AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        WHERE mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
            AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    ),
    corticosteroids_20_drugs AS (
        SELECT DISTINCT
            mr.id as medication_request_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as drug_name
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
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
    )
    SELECT
        c20.rxnorm_code,
        c20.drug_name,
        COUNT(DISTINCT c20.medication_request_id) as missed_requests
    FROM corticosteroids_20_drugs c20
    LEFT JOIN corticosteroids_5_drugs c5
        ON c20.medication_request_id = c5.medication_request_id
    WHERE c5.medication_request_id IS NULL
    GROUP BY c20.rxnorm_code, c20.drug_name
    ORDER BY missed_requests DESC
    """

    results_missed = run_query(athena, query_missed, "Query 3: Drugs MISSED by 5-Drug Approach")

    if results_missed and len(results_missed['ResultSet']['Rows']) > 1:
        print(f"\n⚠️ Drugs Missed by 5-Drug Approach:")
        print(f"{'RxNorm Code':<15} {'Drug Name':<40} {'Missed Requests':<20}")
        print("-" * 80)

        total_missed = 0
        for row in results_missed['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', '')
            count = row['Data'][2].get('VarCharValue', '0')
            print(f"{rxnorm:<15} {drug:<40} {count:<20}")
            total_missed += int(count)

        print("-" * 80)
        print(f"{'TOTAL':<55} {total_missed:<20}")
    else:
        print("\n✅ No drugs missed - 5-drug approach captures everything!")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if results_5 and results_20:
        patients_diff = int(patients_20) - int(patients_5)
        requests_diff = int(med_requests_20) - int(med_requests_5)

        print(f"\n5-Drug Approach (Current):")
        print(f"  - Patients: {patients_5}")
        print(f"  - Medication requests: {med_requests_5}")

        print(f"\n20-Drug Approach (Comprehensive):")
        print(f"  - Patients: {patients_20}")
        print(f"  - Medication requests: {med_requests_20}")

        print(f"\nDifference (What we're missing):")
        print(f"  - Additional patients: {patients_diff} ({patients_diff/int(patients_5)*100:.1f}% increase)")
        print(f"  - Additional medication requests: {requests_diff} ({requests_diff/int(med_requests_5)*100:.1f}% increase)")

        if patients_diff > 0 or requests_diff > 0:
            print(f"\n⚠️ RECOMMENDATION: Expand to 20-drug approach")
            print(f"   - Captures {patients_diff} additional patients")
            print(f"   - Captures {requests_diff} additional corticosteroid administrations")
        else:
            print(f"\n✅ CONCLUSION: 5-drug approach is sufficient")
            print(f"   - No additional patients or requests captured by 20-drug approach")

if __name__ == '__main__':
    main()
