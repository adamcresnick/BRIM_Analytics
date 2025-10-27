#!/usr/bin/env python3
"""
Comprehensive search for ALL mobilization agents and G-CSF medications.

Strategy:
1. Check current RxNorm codes in views
2. Search RxNav for all related formulations and brand names
3. Search database empirically for any G-CSF/mobilization medications
4. Identify gaps and provide recommendations
"""

import boto3
import time
import requests

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

def lookup_rxnorm(rxcui):
    """Look up RxNorm details from RxNav API."""
    try:
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/properties.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'properties' in data:
                return data['properties']
        return None
    except Exception as e:
        print(f"Error looking up {rxcui}: {e}")
        return None

def main():
    print("=" * 80)
    print("COMPREHENSIVE MOBILIZATION AGENT & G-CSF SEARCH")
    print("=" * 80)

    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Corrected RxNorm codes in views (ingredient codes)
    current_codes = {
        '68442': 'Filgrastim',
        '338036': 'Pegfilgrastim',
        '733003': 'Plerixafor'
    }

    print("\n" + "=" * 80)
    print("STEP 1: Verify Current RxNorm Codes")
    print("=" * 80)

    for rxcui, name in current_codes.items():
        props = lookup_rxnorm(rxcui)
        if props:
            print(f"\n✅ {rxcui} ({name}):")
            print(f"   Official name: {props.get('name', 'N/A')}")
            print(f"   TTY: {props.get('tty', 'N/A')}")
        time.sleep(0.5)  # Rate limit

    # Query 1: Search database for current codes
    query_current = """
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
    WHERE mcc.code_coding_code IN ('68442', '338036', '733003')
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    GROUP BY mcc.code_coding_code, mcc.code_coding_display
    ORDER BY medication_requests DESC
    """

    results_current = run_query(athena, query_current, "Query 1: Current RxNorm Codes in Database")

    print("\n" + "=" * 80)
    print("RESULTS: Current Codes Found in Data")
    print("=" * 80)

    if results_current and len(results_current['ResultSet']['Rows']) > 1:
        print(f"\n{'RxNorm':<10} {'Drug Name':<40} {'Patients':<12} {'Requests':<12}")
        print("-" * 80)

        for row in results_current['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', 'N/A')
            patients = int(row['Data'][2].get('VarCharValue', '0'))
            requests = int(row['Data'][3].get('VarCharValue', '0'))
            print(f"{rxnorm:<10} {drug[:38]:<40} {patients:<12,} {requests:<12,}")
    else:
        print("⚠️  No current codes found in data")

    # Query 2: Text search for G-CSF and mobilization agents
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
        -- G-CSF agents
        LOWER(mr.medication_reference_display) LIKE '%filgrastim%'
        OR LOWER(mr.medication_reference_display) LIKE '%neupogen%'
        OR LOWER(mr.medication_reference_display) LIKE '%granix%'
        OR LOWER(mr.medication_reference_display) LIKE '%zarxio%'
        OR LOWER(mr.medication_reference_display) LIKE '%nivestim%'
        OR LOWER(mr.medication_reference_display) LIKE '%grastofil%'
        OR LOWER(mr.medication_reference_display) LIKE '%pegfilgrastim%'
        OR LOWER(mr.medication_reference_display) LIKE '%neulasta%'
        OR LOWER(mr.medication_reference_display) LIKE '%fulphila%'
        OR LOWER(mr.medication_reference_display) LIKE '%udenyca%'
        OR LOWER(mr.medication_reference_display) LIKE '%ziextenzo%'
        OR LOWER(mr.medication_reference_display) LIKE '%nyvepria%'
        OR LOWER(mr.medication_reference_display) LIKE '%stimufend%'

        -- Mobilization agents
        OR LOWER(mr.medication_reference_display) LIKE '%plerixafor%'
        OR LOWER(mr.medication_reference_display) LIKE '%mozobil%'

        -- Long-acting G-CSF
        OR LOWER(mr.medication_reference_display) LIKE '%lipegfilgrastim%'
        OR LOWER(mr.medication_reference_display) LIKE '%lonquex%'

        -- Other G-CSF
        OR LOWER(mr.medication_reference_display) LIKE '%lenograstim%'
        OR LOWER(mr.medication_reference_display) LIKE '%granocyte%'

        -- Generic terms
        OR LOWER(mr.medication_reference_display) LIKE '%g-csf%'
        OR LOWER(mr.medication_reference_display) LIKE '%gcsf%'
        OR LOWER(mr.medication_reference_display) LIKE '%granulocyte%colony%'
    )
    AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    GROUP BY mr.medication_reference_display, m.code_text
    ORDER BY medication_requests DESC
    LIMIT 50
    """

    results_text = run_query(athena, query_text, "Query 2: Text Search for G-CSF/Mobilization Agents")

    print("\n" + "=" * 80)
    print("RESULTS: G-CSF/Mobilization Agents Found by Text (Top 50)")
    print("=" * 80)

    if results_text and len(results_text['ResultSet']['Rows']) > 1:
        print(f"\n{'Medication Display':<60} {'Patients':<12} {'Requests':<12}")
        print("-" * 90)

        for row in results_text['ResultSet']['Rows'][1:]:
            display = row['Data'][0].get('VarCharValue', 'N/A')
            patients = int(row['Data'][2].get('VarCharValue', '0'))
            requests = int(row['Data'][3].get('VarCharValue', '0'))
            print(f"{display[:58]:<60} {patients:<12,} {requests:<12,}")

    # Query 3: Find RxNorm codes NOT in our current list
    query_missing = """
    WITH text_matched AS (
        SELECT DISTINCT
            mr.id as medication_request_id,
            m.id as medication_id
        FROM fhir_prd_db.medication_request mr
        LEFT JOIN fhir_prd_db.medication m
            ON m.id = mr.medication_reference_reference
        WHERE (
            LOWER(mr.medication_reference_display) LIKE '%filgrastim%'
            OR LOWER(mr.medication_reference_display) LIKE '%pegfilgrastim%'
            OR LOWER(mr.medication_reference_display) LIKE '%plerixafor%'
            OR LOWER(mr.medication_reference_display) LIKE '%neupogen%'
            OR LOWER(mr.medication_reference_display) LIKE '%neulasta%'
            OR LOWER(mr.medication_reference_display) LIKE '%mozobil%'
            OR LOWER(mr.medication_reference_display) LIKE '%granix%'
            OR LOWER(mr.medication_reference_display) LIKE '%zarxio%'
            OR LOWER(mr.medication_reference_display) LIKE '%fulphila%'
            OR LOWER(mr.medication_reference_display) LIKE '%udenyca%'
            OR LOWER(mr.medication_reference_display) LIKE '%g-csf%'
        )
        AND mr.status IN ('active', 'completed', 'on-hold', 'stopped')
    )
    SELECT
        mcc.code_coding_code as rxnorm_code,
        mcc.code_coding_display as drug_name,
        COUNT(DISTINCT tm.medication_request_id) as medication_requests
    FROM text_matched tm
    INNER JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = tm.medication_id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mcc.code_coding_code NOT IN ('68442', '338036', '733003')
    GROUP BY mcc.code_coding_code, mcc.code_coding_display
    ORDER BY medication_requests DESC
    LIMIT 30
    """

    results_missing = run_query(athena, query_missing, "Query 3: RxNorm Codes NOT in Current List")

    print("\n" + "=" * 80)
    print("RESULTS: Potentially Missing RxNorm Codes")
    print("=" * 80)

    missing_codes = []
    if results_missing and len(results_missing['ResultSet']['Rows']) > 1:
        print(f"\n{'RxNorm':<15} {'Drug Name':<50} {'Requests':<12}")
        print("-" * 80)

        for row in results_missing['ResultSet']['Rows'][1:]:
            rxnorm = row['Data'][0].get('VarCharValue', '')
            drug = row['Data'][1].get('VarCharValue', 'N/A')
            requests = int(row['Data'][2].get('VarCharValue', '0'))
            print(f"{rxnorm:<15} {drug[:48]:<50} {requests:<12,}")
            missing_codes.append((rxnorm, drug, requests))
    else:
        print("✅ No missing RxNorm codes - current list is comprehensive!")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)

    print(f"\n📋 Corrected RxNorm Codes in Views:")
    print(f"   • 68442 - Filgrastim (ingredient)")
    print(f"   • 338036 - Pegfilgrastim (ingredient)")
    print(f"   • 733003 - Plerixafor (ingredient)")

    if missing_codes:
        print(f"\n⚠️  Found {len(missing_codes)} additional RxNorm codes in data")
        print(f"\n🔍 Looking up details for top missing codes...")

        for rxnorm, drug, requests in missing_codes[:10]:
            print(f"\n   {rxnorm} ({requests:,} requests):")
            props = lookup_rxnorm(rxnorm)
            if props:
                print(f"      Name: {props.get('name', 'N/A')}")
                print(f"      TTY: {props.get('tty', 'N/A')}")
            time.sleep(0.5)
    else:
        print(f"\n✅ No missing codes found - current list captures all G-CSF/mobilization agents")

    print(f"\n📋 Recommended Brand Names to Add:")
    print(f"   Filgrastim brands: Neupogen, Granix, Zarxio (biosimilar), Nivestim")
    print(f"   Pegfilgrastim brands: Neulasta, Fulphila, Udenyca, Ziextenzo, Nyvepria")
    print(f"   Plerixafor brands: Mozobil")

if __name__ == '__main__':
    main()
