#!/usr/bin/env python3
"""
Comprehensive search for ALL corticosteroids in the medication database.

Strategy:
1. Search by known RxNorm codes (from RxClass API - ATC H02AB and H02AA)
2. Search by generic drug names (text matching)
3. Search by brand names (common U.S. brands)
4. Cross-reference with RxNorm to validate
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
    print("COMPREHENSIVE CORTICOSTEROID SEARCH")
    print("=" * 80)
    print("\nSearching medication database for ALL corticosteroids...")

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Query 1: Search by ALL known corticosteroid RxNorm codes
    # Source: RxClass API - ATC H02AB (Glucocorticoids) and H02AA (Mineralocorticoids)
    query_rxnorm = """
    SELECT
        mcc.code_coding_code as rxnorm_code,
        mcc.code_coding_display as drug_name,
        COUNT(DISTINCT mr.subject_reference) as patients,
        COUNT(DISTINCT mr.id) as medication_requests
    FROM fhir_prd_db.medication_request mr
    INNER JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code IN (
        -- GLUCOCORTICOIDS (ATC H02AB)
        '3264',    -- dexamethasone
        '8640',    -- prednisone
        '8638',    -- prednisolone
        '6902',    -- methylprednisolone
        '5492',    -- hydrocortisone
        '1514',    -- betamethasone
        '10759',   -- triamcinolone
        '2878',    -- cortisone
        '22396',   -- deflazacort
        '7910',    -- paramethasone
        '29523',   -- meprednisone
        '4463',    -- fluocortolone
        '55681',   -- rimexolone
        '12473',   -- prednylidene
        '21285',   -- cloprednol
        '21660',   -- cortivazol
        '2669799', -- vamorolone

        -- MINERALOCORTICOIDS (ATC H02AA)
        '4452',    -- fludrocortisone
        '3256',    -- desoxycorticosterone
        '1312358'  -- aldosterone
    )
    AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    GROUP BY mcc.code_coding_code, mcc.code_coding_display
    ORDER BY medication_requests DESC
    """

    results_rxnorm = run_query(athena, query_rxnorm, "Query 1: Search by Known RxNorm Codes")

    print("\n" + "=" * 80)
    print("RESULTS: Corticosteroids Found by RxNorm Code")
    print("=" * 80)

    total_patients_rxnorm = set()
    total_requests_rxnorm = 0
    found_rxnorm_codes = []

    if results_rxnorm and len(results_rxnorm['ResultSet']['Rows']) > 1:
        print(f"\n{'RxNorm':<10} {'Drug Name':<40} {'Patients':<12} {'Requests':<12}")
        print("-" * 80)

        for row in results_rxnorm['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', 'N/A')
            patients = int(row['Data'][2].get('VarCharValue', '0'))
            requests = int(row['Data'][3].get('VarCharValue', '0'))
            print(f"{rxnorm:<10} {drug[:38]:<40} {patients:<12,} {requests:<12,}")
            total_requests_rxnorm += requests
            found_rxnorm_codes.append(rxnorm)

        print("-" * 80)
        print(f"TOTAL RxNorm matches: {len(found_rxnorm_codes)} unique codes, {total_requests_rxnorm:,} requests")
    else:
        print("No corticosteroids found by RxNorm code")

    # Query 2: Text matching for corticosteroid names
    query_text = """
    SELECT
        mr.medication_reference_display as medication_display,
        m.code_text as medication_code_text,
        COUNT(DISTINCT mr.subject_reference) as patients,
        COUNT(DISTINCT mr.id) as medication_requests
    FROM fhir_prd_db.medication_request mr
    LEFT JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    WHERE (
        -- Common corticosteroids
        LOWER(mr.medication_reference_display) LIKE '%dexamethasone%'
        OR LOWER(mr.medication_reference_display) LIKE '%prednisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%prednisolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%methylprednisolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%hydrocortisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%betamethasone%'
        OR LOWER(mr.medication_reference_display) LIKE '%triamcinolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%cortisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%fludrocortisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%deflazacort%'

        -- Less common
        OR LOWER(mr.medication_reference_display) LIKE '%paramethasone%'
        OR LOWER(mr.medication_reference_display) LIKE '%meprednisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%fluocortolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%rimexolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%cortivazol%'
        OR LOWER(mr.medication_reference_display) LIKE '%vamorolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%desoxycorticosterone%'

        -- Common brand names
        OR LOWER(mr.medication_reference_display) LIKE '%decadron%'
        OR LOWER(mr.medication_reference_display) LIKE '%medrol%'
        OR LOWER(mr.medication_reference_display) LIKE '%solu-medrol%'
        OR LOWER(mr.medication_reference_display) LIKE '%solu-cortef%'
        OR LOWER(mr.medication_reference_display) LIKE '%kenalog%'
        OR LOWER(mr.medication_reference_display) LIKE '%celestone%'
        OR LOWER(mr.medication_reference_display) LIKE '%cortef%'
        OR LOWER(mr.medication_reference_display) LIKE '%deltasone%'
        OR LOWER(mr.medication_reference_display) LIKE '%rayos%'
        OR LOWER(mr.medication_reference_display) LIKE '%millipred%'
        OR LOWER(mr.medication_reference_display) LIKE '%orapred%'
        OR LOWER(mr.medication_reference_display) LIKE '%emflaza%'

        -- Alternative spellings/forms
        OR LOWER(mr.medication_reference_display) LIKE '%corticosteroid%'
        OR LOWER(mr.medication_reference_display) LIKE '%glucocorticoid%'
    )
    AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    GROUP BY mr.medication_reference_display, m.code_text
    ORDER BY medication_requests DESC
    LIMIT 50
    """

    results_text = run_query(athena, query_text, "Query 2: Text Matching for Corticosteroids")

    print("\n" + "=" * 80)
    print("RESULTS: Corticosteroids Found by Text Matching (Top 50)")
    print("=" * 80)

    if results_text and len(results_text['ResultSet']['Rows']) > 1:
        print(f"\n{'Medication Display':<60} {'Patients':<12} {'Requests':<12}")
        print("-" * 90)

        for row in results_text['ResultSet']['Rows'][1:]:
            display = row['Data'][0].get('VarCharValue', 'N/A')
            patients = int(row['Data'][2].get('VarCharValue', '0'))
            requests = int(row['Data'][3].get('VarCharValue', '0'))
            print(f"{display[:58]:<60} {patients:<12,} {requests:<12,}")
    else:
        print("No corticosteroids found by text matching")

    # Query 3: Find RxNorm codes NOT in our list that match corticosteroid text patterns
    query_missing = """
    WITH text_matched_medications AS (
        SELECT DISTINCT
            mr.id as medication_request_id,
            m.id as medication_id
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
        WHERE (
            LOWER(mr.medication_reference_display) LIKE '%dexamethasone%'
            OR LOWER(mr.medication_reference_display) LIKE '%prednisone%'
            OR LOWER(mr.medication_reference_display) LIKE '%prednisolone%'
            OR LOWER(mr.medication_reference_display) LIKE '%methylprednisolone%'
            OR LOWER(mr.medication_reference_display) LIKE '%hydrocortisone%'
            OR LOWER(mr.medication_reference_display) LIKE '%betamethasone%'
            OR LOWER(mr.medication_reference_display) LIKE '%triamcinolone%'
            OR LOWER(mr.medication_reference_display) LIKE '%cortisone%'
            OR LOWER(mr.medication_reference_display) LIKE '%fludrocortisone%'
            OR LOWER(mr.medication_reference_display) LIKE '%deflazacort%'
            OR LOWER(mr.medication_reference_display) LIKE '%decadron%'
            OR LOWER(mr.medication_reference_display) LIKE '%medrol%'
            OR LOWER(mr.medication_reference_display) LIKE '%solu-medrol%'
            OR LOWER(mr.medication_reference_display) LIKE '%solu-cortef%'
            OR LOWER(mr.medication_reference_display) LIKE '%kenalog%'
        )
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    )
    SELECT
        mcc.code_coding_code as rxnorm_code,
        mcc.code_coding_display as drug_name,
        COUNT(DISTINCT tmm.medication_request_id) as medication_requests
    FROM text_matched_medications tmm
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = tmm.medication_id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code NOT IN (
        '3264', '8640', '8638', '6902', '5492', '1514', '10759',
        '2878', '22396', '7910', '29523', '4463', '55681',
        '12473', '21285', '21660', '2669799',
        '4452', '3256', '1312358'
    )
    GROUP BY mcc.code_coding_code, mcc.code_coding_display
    ORDER BY medication_requests DESC
    LIMIT 20
    """

    results_missing = run_query(athena, query_missing, "Query 3: RxNorm Codes NOT in Our List (but match text patterns)")

    print("\n" + "=" * 80)
    print("RESULTS: Potential Missing RxNorm Codes")
    print("=" * 80)

    if results_missing and len(results_missing['ResultSet']['Rows']) > 1:
        print(f"\n{'RxNorm':<10} {'Drug Name':<50} {'Requests':<12}")
        print("-" * 80)

        for row in results_missing['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', 'N/A')
            requests = int(row['Data'][2].get('VarCharValue', '0'))
            print(f"{rxnorm:<10} {drug[:48]:<50} {requests:<12,}")
    else:
        print("✅ No missing RxNorm codes - our list is comprehensive!")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n✅ RxNorm Codes Found in Data: {len(found_rxnorm_codes)}")
    print(f"   Total medication requests: {total_requests_rxnorm:,}")
    print(f"\n📋 RxNorm Codes Found:")
    for code in found_rxnorm_codes:
        print(f"   - {code}")

if __name__ == '__main__':
    main()
