#!/usr/bin/env python3
"""
Test 5-drug vs 20-drug corticosteroid coverage WITH CORRECT JOIN.

This version uses the FIXED join: m.id = mr.medication_reference_reference
(not the broken SUBSTRING version)
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
    print("CORTICOSTEROID COVERAGE COMPARISON: 5-drug vs 20-drug")
    print("=" * 80)
    print("\nUsing CORRECTED join: m.id = mr.medication_reference_reference")
    print("(Previous tests used broken SUBSTRING join)")

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Query 1: 5-drug approach (v_concomitant_medications list)
    query_5_drugs = """
    WITH corticosteroids_5_drugs AS (
        SELECT DISTINCT
            mr.subject_reference as patient_fhir_id,
            mr.id as medication_request_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as drug_name
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
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

    results_5 = run_query(athena, query_5_drugs, "Query 1: 5-Drug Approach (v_concomitant_medications)")

    patients_5 = 0
    med_requests_5 = 0
    rxnorm_5 = 0

    if results_5:
        row = results_5['ResultSet']['Rows'][1]['Data']
        patients_5 = int(row[0].get('VarCharValue', '0'))
        med_requests_5 = int(row[1].get('VarCharValue', '0'))
        rxnorm_5 = int(row[2].get('VarCharValue', '0'))
        print(f"\n✅ 5-Drug Approach:")
        print(f"   Patients: {patients_5:,}")
        print(f"   Medication requests: {med_requests_5:,}")
        print(f"   Distinct RxNorm codes found: {rxnorm_5}")

    # Query 2: 20-drug approach (v_imaging_corticosteroid_use list)
    query_20_drugs = """
    WITH corticosteroids_20_drugs AS (
        SELECT DISTINCT
            mr.subject_reference as patient_fhir_id,
            mr.id as medication_request_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as drug_name
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
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

    patients_20 = 0
    med_requests_20 = 0
    rxnorm_20 = 0

    if results_20:
        row = results_20['ResultSet']['Rows'][1]['Data']
        patients_20 = int(row[0].get('VarCharValue', '0'))
        med_requests_20 = int(row[1].get('VarCharValue', '0'))
        rxnorm_20 = int(row[2].get('VarCharValue', '0'))
        print(f"\n✅ 20-Drug Approach:")
        print(f"   Patients: {patients_20:,}")
        print(f"   Medication requests: {med_requests_20:,}")
        print(f"   Distinct RxNorm codes found: {rxnorm_20}")

    # Query 3: What drugs are we MISSING with 5-drug approach?
    query_missed = """
    WITH corticosteroids_5_drugs AS (
        SELECT DISTINCT
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
    corticosteroids_20_drugs AS (
        SELECT DISTINCT
            mr.id as medication_request_id,
            mr.subject_reference as patient_fhir_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as drug_name
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
    )
    SELECT
        c20.rxnorm_code,
        c20.drug_name,
        COUNT(DISTINCT c20.medication_request_id) as missed_requests,
        COUNT(DISTINCT c20.patient_fhir_id) as missed_patients
    FROM corticosteroids_20_drugs c20
    LEFT JOIN corticosteroids_5_drugs c5
        ON c20.medication_request_id = c5.medication_request_id
    WHERE c5.medication_request_id IS NULL
    GROUP BY c20.rxnorm_code, c20.drug_name
    ORDER BY missed_requests DESC
    """

    results_missed = run_query(athena, query_missed, "Query 3: Drugs MISSED by 5-Drug Approach")

    total_missed_requests = 0
    total_missed_patients = 0

    if results_missed and len(results_missed['ResultSet']['Rows']) > 1:
        print(f"\n⚠️  Drugs Missed by 5-Drug Approach:")
        print(f"{'RxNorm':<10} {'Drug Name':<40} {'Requests':<12} {'Patients':<12}")
        print("-" * 80)

        for row in results_missed['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', '')
            requests = int(row['Data'][2].get('VarCharValue', '0'))
            patients = int(row['Data'][3].get('VarCharValue', '0'))
            print(f"{rxnorm:<10} {drug[:38]:<40} {requests:<12,} {patients:<12,}")
            total_missed_requests += requests
            total_missed_patients += patients

        print("-" * 80)
        print(f"{'TOTAL':<50} {total_missed_requests:<12,} {total_missed_patients:<12,}")
    else:
        print("\n✅ No drugs missed - 5-drug approach captures everything!")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if results_5 and results_20:
        patients_diff = patients_20 - patients_5
        requests_diff = med_requests_20 - med_requests_5

        print(f"\n5-Drug Approach (Current v_concomitant_medications):")
        print(f"  - Patients: {patients_5:,}")
        print(f"  - Medication requests: {med_requests_5:,}")
        print(f"  - RxNorm codes in list: 5")
        print(f"  - RxNorm codes actually found in data: {rxnorm_5}")

        print(f"\n20-Drug Approach (Current v_imaging_corticosteroid_use):")
        print(f"  - Patients: {patients_20:,}")
        print(f"  - Medication requests: {med_requests_20:,}")
        print(f"  - RxNorm codes in list: 20")
        print(f"  - RxNorm codes actually found in data: {rxnorm_20}")

        print(f"\nDifference (What 5-drug approach is missing):")
        print(f"  - Additional patients: {patients_diff:,} ({patients_diff/patients_5*100:.1f}% increase)" if patients_5 > 0 else "  - Additional patients: N/A")
        print(f"  - Additional medication requests: {requests_diff:,} ({requests_diff/med_requests_5*100:.1f}% increase)" if med_requests_5 > 0 else "  - Additional medication requests: N/A")

        print(f"\n" + "=" * 80)
        print("RECOMMENDATION")
        print("=" * 80)

        if patients_diff > 0 or requests_diff > 0:
            print(f"\n⚠️  EXPAND TO 20-DRUG APPROACH")
            print(f"\n   Rationale:")
            print(f"   - Captures {patients_diff:,} additional patients with corticosteroids")
            print(f"   - Captures {requests_diff:,} additional corticosteroid administrations")
            print(f"   - {rxnorm_20 - rxnorm_5} additional RxNorm codes found in data")
            print(f"\n   Action:")
            print(f"   - Update v_concomitant_medications to include all 20 drugs")
            print(f"   - This ensures comprehensive corticosteroid capture")
        else:
            print(f"\n✅ KEEP 5-DRUG APPROACH")
            print(f"\n   Rationale:")
            print(f"   - No additional patients or requests captured by 20-drug approach")
            print(f"   - 5-drug list is sufficient for current data")

if __name__ == '__main__':
    main()
