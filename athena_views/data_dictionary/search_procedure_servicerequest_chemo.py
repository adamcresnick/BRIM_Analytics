#!/usr/bin/env python3
"""
Search Procedure and ServiceRequest tables for chemotherapy evidence in 89 manually-identified patients.
"""

import boto3
import time
import csv
import pandas as pd
from pathlib import Path

# List of 89 patients manually identified as having received chemo
PATIENT_IDS = [
    'uRsqtZYNv5Ls3YbMLQbKJGw3', 'LGN8mZV6R0Y1l.6.CG5V-FA3', '2IqG-LG2lY40qxXEwKNLf-A3',
    'Fb4AjG18gZUhNKVXrAKYQJw3', 'aJVP01i6Y5czlBjVzuZF0dw3', 'qwI.g9IXjAEEwsIXTXy4zQg3',
    'AsjsXhR3r7VwV8ywRdHQSfQ3', 'j.3nKi3Eue68LebN3uRoBZw3', 'KmHGhGVxPrQF9XpGohI.b.A3',
    'gPDLh7Rz5D1i9KrQOJwZQzQ3', 'dJx4F1Ie4n.B0u4.P9C3Rjw3', 'TRqKb.cSuSDOQRxIqyJ7QTA3',
    'XSxSxjKOjvVZisPeN7YC0ig3', 'TyvtbNL3TpjqtPmU8kLphtw3', '9SYm9c7KFYzBxugY.4D7tcg3',
    'g5yCz4mCSMHHnhyN1xAjGAg3', 'VnQDy3fW4u6Oa5Hbce5ZZZg3', '65ORbmkfDbp.u-Lg5Bxn36w3',
    'Wo3MHqBvVEt1FHiZlT9mTqA3', 'OIUhYREj5IfB1pJf8OQ6Zig3', 'zw5KVuCAjqeRqbMv.UtmMuA3',
    'w0Q3Fv7nvxPBOqgXRBmF1Rg3', 'pf8r2THr-rTJDHKdgM5TnRA3', 'TsAe1PQKDjlpzTNdnlKY2yg3',
    'C8uHH.W2Qvvb0BFE42rWNog3', 'PaZvWJaEb.Hkl4hMEZzklWA3', 'fGFsG5eCvvF0NvP8sEbx.hg3',
    '0fz9kQZ2mj1D5pSJtKQmRdw3', 'h1dCGn69FJWk71xL-4D0DVA3', 'Ke9Q2S43rX7mT9MRvtXWPkw3',
    'GH5Y.0SahVoHk73wVzNWUSg3', 'V1XkX6XZXhUoVtzX5oDdlRQ3', 'aCW8PQqYLlCDK2p3xkQqL5A3',
    'MWrgJCnCQLuwEewp3LKhzww3', '4scx87AqP4eOLRu2kEIZMKA3', '8jbDsEbbpfY2k1LKHJ9CdQg3',
    'ugHI3NfYkgU8ZkawzXGnP2w3', 'AJbZKKHgI0K2Lmtl2KLZnzA3', 'CAh7g-wL9gF73VggmTz-Vhg3',
    'qCnvJhDVUJywjD3sUj3xjHg3', 'lWv4J.fU7o78bKVsF9x79HA3', 'u3f-DjIv1a-GJnZLF6.iuVw3',
    'fhYjnrpEGKmV9mzttv0i2Eg3', 'U.vbV9ZWFK.M2CnWQdumKHg3', 'IVMWdBP3DobQCNGH.y0Zf4g3',
    'n5XpNGOaT7qHaEdStXPjqyw3', 'Pvi-pCZMhCv73YzGzL03RjA3', 'DpWIjMcaG5GmBjKt5R74weg3',
    'Z4GDNkHV6Ni2wlKQLyYtCbQ3', 'tJdhDx1fhcN0NW28h6bYeag3', 'z2EkQbCGGHdAF8dZ9u5IPGA3',
    'oVeVdD6BnB-5Bx-V0JtdjNw3', 'o30k-E7KtgL3iJYxWbnqNJQ3', 'Ou00z71.JkUhL2UMDJdWa1g3',
    'QmNfE6q8tgsgWJ1H2RFmzqQ3', 'VK6BL0lNJQV3UWAb0ZH9Yzg3', 'BDJEkFGXe7PJUI7RNbdqXCA3',
    'XF6PN1RTz3d8OAK5mOKfJaw3', 'cTpd6.Yxn8Jp08S2-2NVFTQ3', 'LBqI5SqWVi7Lsl42ZO6HL5A3',
    'hQTaIPTm.PZGz-X.L-RJ92w3', 'VTHZKzEd9QSDL12V.sLKpTw3', 'vbGdWq.5l04c8MWUmPkZEZg3',
    'eZoXazPa3nXxOYUwXF5nSjQ3', 'jUcx6B6RfFccIUlOEJsWkBg3', 'WjZ.iXUKlSYCwdN3G.2Sbdw3',
    'JFu1Sl4Pd3ZmjPiGp2F9ljQ3', '7YpAJQV2hZzvMSDTxcb5zOw3', 'u3HpwONYcjE-PYRz3SzqOGg3',
    'HtXXJqAeW6Uq5Qp5Xa7Dwvw3', 'GR53tGiCLQoHJ6iRIQWj7Gg3', '6WFRQcS5ZBRR9-YmpOJWtDQ3',
    'o9bnRBDlP5RcCqQpSmwuQIQ3', 'FxBioPSE9bP16mU0RQXkfXg3', 'nrHy6YCVkrgBWQvl5U9sIbQ3',
    'g9THKKmZ39f37kZOmYY.JCA3', 'Vg5v2KKTS6kxZe9jx17K-WQ3', 'YSKdxFCz6P06T4qNV73OIRA3',
    'V1zYSyJHUYhfPGZDa-jy7gw3', 'fCsALMdpJyLK7l.xnRPFdMQ3', 'xPx.mLNvdVbKn43OB9DDaEw3',
    'Wkqoue4K26ecIU-zTOwHbKw3', 'wm-N2-g2h4x2CbqkdWd1qNw3', 'bnqz4k4g93O4c2AmdFwHu.A3',
    'l.0E2STGQdOYsrYqB86ZMVw3', 'nIXBHpk-Fh1DH-oNDy8-3Ew3', 'oS9M7gUYaAu2q3JBKwgfh7g3',
    'lm7WwD1I2cICR-7a3rDKZLg3', 'vSz9R4sW6hS7XrvnQDN03gw3', 'nCZWxfKqUYk8mlDbNvQrqDg3'
]

def search_procedures(athena, patient_list):
    """Search procedure tables for chemotherapy evidence."""

    # Convert patient list to SQL IN clause
    patient_in_clause = "', '".join(patient_list)

    query = f"""
    WITH patient_procedures AS (
        SELECT
            p.subject_reference as patient_fhir_id,
            p.id as procedure_id,
            p.status,
            p.code_text,
            p.category_text,
            p.performed_date_time,
            p.performed_period_start,
            p.performed_string
        FROM fhir_prd_db.procedure p
        WHERE p.subject_reference IN ('{patient_in_clause}')
    ),
    procedure_codes AS (
        SELECT
            pc.procedure_id,
            pc.code_coding_system,
            pc.code_coding_code,
            pc.code_coding_display
        FROM fhir_prd_db.procedure_code_coding pc
        WHERE pc.procedure_id IN (SELECT procedure_id FROM patient_procedures)
    ),
    procedure_reasons AS (
        SELECT
            pr.procedure_id,
            pr.reason_code_text,
            pr.reason_code_coding
        FROM fhir_prd_db.procedure_reason_code pr
        WHERE pr.procedure_id IN (SELECT procedure_id FROM patient_procedures)
    )
    SELECT
        pp.patient_fhir_id,
        pp.procedure_id,
        pp.status,
        pp.code_text,
        pp.category_text,
        pp.performed_date_time,
        pc.code_coding_system,
        pc.code_coding_code,
        pc.code_coding_display,
        pr.reason_code_text
    FROM patient_procedures pp
    LEFT JOIN procedure_codes pc ON pp.procedure_id = pc.procedure_id
    LEFT JOIN procedure_reasons pr ON pp.procedure_id = pr.procedure_id
    WHERE
        -- Look for chemotherapy-related keywords
        LOWER(pp.code_text) LIKE '%chemo%'
        OR LOWER(pp.code_text) LIKE '%platin%'
        OR LOWER(pp.code_text) LIKE '%taxel%'
        OR LOWER(pp.code_text) LIKE '%rubicin%'
        OR LOWER(pp.code_text) LIKE '%vincr%'
        OR LOWER(pp.code_text) LIKE '%antineoplastic%'
        OR LOWER(pp.code_text) LIKE '%cytotoxic%'
        OR LOWER(pp.category_text) LIKE '%chemo%'
        OR LOWER(pp.category_text) LIKE '%oncolog%'
        OR LOWER(pc.code_coding_display) LIKE '%chemo%'
        OR LOWER(pc.code_coding_display) LIKE '%platin%'
        OR LOWER(pc.code_coding_display) LIKE '%taxel%'
        OR LOWER(pc.code_coding_display) LIKE '%rubicin%'
        OR LOWER(pc.code_coding_display) LIKE '%antineoplastic%'
        -- CPT codes for chemotherapy administration
        OR pc.code_coding_code IN ('96413', '96415', '96416', '96417', '96420', '96422', '96423', '96425')
        OR LOWER(pr.reason_code_text) LIKE '%chemo%'
        OR LOWER(pr.reason_code_text) LIKE '%cancer%'
        OR LOWER(pr.reason_code_text) LIKE '%neoplasm%'
    """

    print("Searching procedure tables for chemotherapy evidence...")
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
    )

    query_id = response['QueryExecutionId']
    print(f"Started query: {query_id}")

    return wait_for_query(athena, query_id)

def search_service_requests(athena, patient_list):
    """Search service_request tables for chemotherapy evidence."""

    patient_in_clause = "', '".join(patient_list)

    query = f"""
    WITH patient_service_requests AS (
        SELECT
            sr.subject_reference as patient_fhir_id,
            sr.id as service_request_id,
            sr.status,
            sr.intent,
            sr.code_text,
            sr.occurrence_date_time,
            sr.occurrence_period_start,
            sr.authored_on
        FROM fhir_prd_db.service_request sr
        WHERE sr.subject_reference IN ('{patient_in_clause}')
    ),
    service_request_codes AS (
        SELECT
            src.service_request_id,
            src.code_coding_system,
            src.code_coding_code,
            src.code_coding_display
        FROM fhir_prd_db.service_request_code_coding src
        WHERE src.service_request_id IN (SELECT service_request_id FROM patient_service_requests)
    ),
    service_request_reasons AS (
        SELECT
            srr.service_request_id,
            srr.reason_code_text,
            srr.reason_code_coding
        FROM fhir_prd_db.service_request_reason_code srr
        WHERE srr.service_request_id IN (SELECT service_request_id FROM patient_service_requests)
    )
    SELECT
        psr.patient_fhir_id,
        psr.service_request_id,
        psr.status,
        psr.intent,
        psr.code_text,
        psr.occurrence_date_time,
        psr.authored_on,
        src.code_coding_system,
        src.code_coding_code,
        src.code_coding_display,
        srr.reason_code_text
    FROM patient_service_requests psr
    LEFT JOIN service_request_codes src ON psr.service_request_id = src.service_request_id
    LEFT JOIN service_request_reasons srr ON psr.service_request_id = srr.service_request_id
    WHERE
        -- Look for chemotherapy-related keywords
        LOWER(psr.code_text) LIKE '%chemo%'
        OR LOWER(psr.code_text) LIKE '%platin%'
        OR LOWER(psr.code_text) LIKE '%taxel%'
        OR LOWER(psr.code_text) LIKE '%rubicin%'
        OR LOWER(psr.code_text) LIKE '%vincr%'
        OR LOWER(psr.code_text) LIKE '%antineoplastic%'
        OR LOWER(psr.code_text) LIKE '%cytotoxic%'
        OR LOWER(src.code_coding_display) LIKE '%chemo%'
        OR LOWER(src.code_coding_display) LIKE '%platin%'
        OR LOWER(src.code_coding_display) LIKE '%taxel%'
        OR LOWER(src.code_coding_display) LIKE '%rubicin%'
        OR LOWER(src.code_coding_display) LIKE '%antineoplastic%'
        -- HCPCS chemotherapy drug codes
        OR src.code_coding_code LIKE 'J9%'
        OR src.code_coding_code LIKE 'J8%'
        OR LOWER(srr.reason_code_text) LIKE '%chemo%'
        OR LOWER(srr.reason_code_text) LIKE '%cancer%'
        OR LOWER(srr.reason_code_text) LIKE '%neoplasm%'
    """

    print("Searching service_request tables for chemotherapy evidence...")
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
    )

    query_id = response['QueryExecutionId']
    print(f"Started query: {query_id}")

    return wait_for_query(athena, query_id)

def wait_for_query(athena, query_id):
    """Wait for query to complete and return results."""
    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        print(f"Status: {status}...")
        time.sleep(2)

    if status == 'SUCCEEDED':
        # Get results
        results = athena.get_query_results(QueryExecutionId=query_id)
        return results
    else:
        reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        print(f"❌ Query {status}: {reason}")
        return None

def parse_results(results, source_table):
    """Parse Athena results into list of dictionaries."""
    if not results:
        return []

    rows = results['ResultSet']['Rows']
    if len(rows) <= 1:
        return []

    # Get column names from first row
    columns = [col['VarCharValue'] for col in rows[0]['Data']]

    # Parse data rows
    data = []
    for row in rows[1:]:
        record = {'source_table': source_table}
        for i, col in enumerate(columns):
            value = row['Data'][i].get('VarCharValue', '') if i < len(row['Data']) else ''
            record[col] = value
        data.append(record)

    return data

def main():
    print("=" * 100)
    print("PROCEDURE AND SERVICE_REQUEST CHEMOTHERAPY EVIDENCE SEARCH")
    print("=" * 100)
    print(f"\nSearching for {len(PATIENT_IDS)} manually-identified chemotherapy patients...")

    # Initialize AWS session
    session = boto3.Session(profile_name='radiant-prod')
    athena = session.client('athena', region_name='us-east-1')

    # Search Procedure tables
    print("\n" + "=" * 100)
    print("SEARCHING PROCEDURE TABLES")
    print("=" * 100)
    procedure_results = search_procedures(athena, PATIENT_IDS)
    procedure_data = parse_results(procedure_results, 'procedure')
    print(f"✓ Found {len(procedure_data)} procedure records with chemotherapy evidence")

    # Search ServiceRequest tables
    print("\n" + "=" * 100)
    print("SEARCHING SERVICE_REQUEST TABLES")
    print("=" * 100)
    service_request_results = search_service_requests(athena, PATIENT_IDS)
    service_request_data = parse_results(service_request_results, 'service_request')
    print(f"✓ Found {len(service_request_data)} service_request records with chemotherapy evidence")

    # Combine all results
    all_data = procedure_data + service_request_data

    # Create summary by patient
    print("\n" + "=" * 100)
    print("PATIENT SUMMARY")
    print("=" * 100)

    patients_with_evidence = set()
    for record in all_data:
        patients_with_evidence.add(record['patient_fhir_id'])

    print(f"\nTotal patients searched: {len(PATIENT_IDS)}")
    print(f"Patients with chemotherapy evidence in Procedure/ServiceRequest: {len(patients_with_evidence)}")
    print(f"Patients without evidence: {len(PATIENT_IDS) - len(patients_with_evidence)}")

    # Save detailed results
    output_file = Path(__file__).parent / 'procedure_servicerequest_chemo_evidence.csv'
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(output_file, index=False)
        print(f"\n✓ Detailed evidence saved to: {output_file}")

        # Show sample
        print("\nSample records:")
        print(df.head(10).to_string())
    else:
        print(f"\n⚠ No chemotherapy evidence found in Procedure or ServiceRequest tables")
        # Still create empty file
        pd.DataFrame(columns=['source_table', 'patient_fhir_id']).to_csv(output_file, index=False)

    # Create patient-level summary
    summary_file = Path(__file__).parent / 'procedure_servicerequest_patient_summary.csv'
    summary_data = []

    for patient_id in PATIENT_IDS:
        patient_records = [r for r in all_data if r['patient_fhir_id'] == patient_id]
        procedure_count = len([r for r in patient_records if r['source_table'] == 'procedure'])
        service_request_count = len([r for r in patient_records if r['source_table'] == 'service_request'])

        has_evidence = len(patient_records) > 0

        summary_data.append({
            'patient_fhir_id': patient_id,
            'has_procedure_evidence': procedure_count > 0,
            'procedure_record_count': procedure_count,
            'has_service_request_evidence': service_request_count > 0,
            'service_request_record_count': service_request_count,
            'total_evidence_records': len(patient_records),
            'has_any_evidence': has_evidence
        })

    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(summary_file, index=False)
    print(f"\n✓ Patient summary saved to: {summary_file}")

    # Statistics
    print("\n" + "=" * 100)
    print("STATISTICS")
    print("=" * 100)
    print(f"Patients with Procedure evidence: {summary_df['has_procedure_evidence'].sum()}")
    print(f"Patients with ServiceRequest evidence: {summary_df['has_service_request_evidence'].sum()}")
    print(f"Patients with either evidence: {summary_df['has_any_evidence'].sum()}")
    print(f"Patients with no evidence: {(~summary_df['has_any_evidence']).sum()}")

if __name__ == '__main__':
    main()
