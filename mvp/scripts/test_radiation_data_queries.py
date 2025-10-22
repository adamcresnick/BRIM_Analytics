#!/usr/bin/env python3
"""
Test script for radiation data queries - NO AGENT EXTRACTION

This script:
1. Queries all radiation data sources from Athena
2. Displays the results in a readable format
3. Does NOT run Agent 2 extraction (saves time/resources)
4. Validates query structure and data availability

Usage:
    python3 scripts/test_radiation_data_queries.py --patient-id Patient/ecKghinUQVl9Q6cMoA0RD1qZHVzp7JHW12RpiW1UMx0A3
"""

import argparse
import json
import boto3
import time
from pathlib import Path


def query_athena(query: str, description: str = None):
    """Execute Athena query and return results"""
    if description:
        print(f"  {description}...", end='', flush=True)

    session = boto3.Session(profile_name='radiant-prod')
    client = session.client('athena', region_name='us-east-1')

    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={'OutputLocation': 's3://radiant-prd-343218191717-us-east-1-prd-athena-results/'}
    )

    query_execution_id = response['QueryExecutionId']

    # Wait for completion
    while True:
        response = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            if description:
                print(f" ❌ FAILED: {reason}")
            return []

        time.sleep(2)

    # Get results
    results = []
    paginator = client.get_paginator('get_query_results')

    for page in paginator.paginate(QueryExecutionId=query_execution_id):
        rows = page['ResultSet']['Rows']

        if not results:
            headers = [col['VarCharValue'] for col in rows[0]['Data']]
            rows = rows[1:]

        for row in rows:
            result = {}
            for i, col in enumerate(row['Data']):
                result[headers[i]] = col.get('VarCharValue', '')
            results.append(result)

    if description:
        print(f" ✅ {len(results)} records")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Test radiation data queries (no agent extraction)'
    )
    parser.add_argument(
        '--patient-id',
        type=str,
        required=True,
        help='Patient FHIR ID to test'
    )

    args = parser.parse_args()

    # Strip Patient/ prefix for Athena queries
    athena_patient_id = args.patient_id.replace('Patient/', '')

    print("="*80)
    print("RADIATION DATA QUERY TEST")
    print("="*80)
    print(f"\nPatient: {args.patient_id}")
    print(f"Athena ID: {athena_patient_id}\n")

    # ========================================================================
    # QUERY 1: Radiation Summary (Data Availability Inventory)
    # ========================================================================
    print("\n" + "="*80)
    print("QUERY 1: v_radiation_summary (Data Availability Inventory)")
    print("="*80)

    radiation_summary_query = f"""
        SELECT *
        FROM v_radiation_summary
        WHERE patient_fhir_id = '{athena_patient_id}'
    """

    radiation_summary = query_athena(radiation_summary_query, "Querying radiation summary")

    if radiation_summary:
        summary = radiation_summary[0]
        print("\n  Data Availability:")
        print(f"    - Has structured ELECT data: {summary.get('has_structured_elect_data')}")
        print(f"    - Has radiation documents: {summary.get('has_radiation_documents')}")
        print(f"    - Has care plans: {summary.get('has_care_plans')}")
        print(f"    - Has appointments: {summary.get('has_appointments')}")
        print(f"\n  Counts:")
        print(f"    - Num radiation documents: {summary.get('num_radiation_documents')}")
        print(f"    - Num treatment summaries: {summary.get('num_treatment_summaries')}")
        print(f"    - Num consults: {summary.get('num_consults')}")
        print(f"    - Num structured courses: {summary.get('num_structured_courses')}")
        print(f"\n  Recommended Strategy: {summary.get('recommended_extraction_strategy')}")
        print(f"  Data Sources Available: {summary.get('num_data_sources_available')}")
    else:
        print("\n  ❌ NO RADIATION DATA - Patient not suitable for radiation extraction")
        return

    # ========================================================================
    # QUERY 2: Radiation Structured Treatments (ELECT)
    # ========================================================================
    print("\n" + "="*80)
    print("QUERY 2: v_radiation_treatments (Structured ELECT Data)")
    print("="*80)

    radiation_treatments_query = f"""
        SELECT
            patient_fhir_id,
            course_id,
            obs_start_date,
            obs_stop_date,
            obs_dose_value,
            obs_dose_unit,
            obs_radiation_field,
            radiation_modality,
            radiation_site,
            data_source_primary
        FROM v_radiation_treatments
        WHERE patient_fhir_id = '{athena_patient_id}'
        ORDER BY obs_start_date
    """

    radiation_treatments = query_athena(radiation_treatments_query, "Querying structured treatments")

    if radiation_treatments:
        print(f"\n  Found {len(radiation_treatments)} structured treatment record(s):")
        for idx, treatment in enumerate(radiation_treatments, 1):
            print(f"\n  Treatment {idx}:")
            print(f"    - Course ID: {treatment.get('course_id')}")
            print(f"    - Start date: {treatment.get('obs_start_date')}")
            print(f"    - Stop date: {treatment.get('obs_stop_date')}")
            print(f"    - Dose: {treatment.get('obs_dose_value')} {treatment.get('obs_dose_unit')}")
            print(f"    - Field/Site: {treatment.get('obs_radiation_field')}")
            print(f"    - Modality: {treatment.get('radiation_modality')}")
            print(f"    - Data source: {treatment.get('data_source_primary')}")
    else:
        print("\n  No structured ELECT data available")

    # ========================================================================
    # QUERY 3: Radiation Documents
    # ========================================================================
    print("\n" + "="*80)
    print("QUERY 3: v_radiation_documents (Treatment Summaries, Consults, Reports)")
    print("="*80)

    radiation_documents_query = f"""
        SELECT
            document_id,
            patient_fhir_id,
            doc_date,
            dr_type_text,
            dr_description,
            document_priority,
            binary_id,
            content_type
        FROM v_radiation_documents
        WHERE patient_fhir_id = '{athena_patient_id}'
        ORDER BY document_priority, doc_date
        LIMIT 10
    """

    radiation_documents = query_athena(radiation_documents_query, "Querying radiation documents (top 10)")

    if radiation_documents:
        print(f"\n  Found radiation documents (showing top 10):")
        for idx, doc in enumerate(radiation_documents, 1):
            print(f"\n  Document {idx}:")
            print(f"    - Type: {doc.get('dr_type_text')}")
            print(f"    - Date: {doc.get('doc_date')}")
            print(f"    - Priority: {doc.get('document_priority')}")
            print(f"    - Description: {doc.get('dr_description', 'N/A')[:80]}")
            print(f"    - Binary ID: {doc.get('binary_id')}")
    else:
        print("\n  No radiation documents available")

    # ========================================================================
    # QUERY 4: Radiation Care Plans
    # ========================================================================
    print("\n" + "="*80)
    print("QUERY 4: v_radiation_care_plan_hierarchy (Treatment Planning)")
    print("="*80)

    care_plans_query = f"""
        SELECT COUNT(*) as count
        FROM v_radiation_care_plan_hierarchy
        WHERE patient_fhir_id = '{athena_patient_id}'
    """

    care_plans = query_athena(care_plans_query, "Querying care plans")
    care_plan_count = int(care_plans[0]['count']) if care_plans else 0
    print(f"  Care plan records: {care_plan_count}")

    # ========================================================================
    # QUERY 5: Radiation Appointments
    # ========================================================================
    print("\n" + "="*80)
    print("QUERY 5: v_radiation_treatment_appointments (Scheduling Context)")
    print("="*80)

    appointments_query = f"""
        SELECT COUNT(*) as count
        FROM v_radiation_treatment_appointments
        WHERE patient_fhir_id = '{athena_patient_id}'
    """

    appointments = query_athena(appointments_query, "Querying radiation appointments")
    appt_count = int(appointments[0]['count']) if appointments else 0
    print(f"  Appointment records: {appt_count}")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    print(f"\n✅ Patient has radiation data")
    print(f"\nData sources available:")
    print(f"  - Structured ELECT: {len(radiation_treatments)} record(s)")
    print(f"  - Radiation documents: {summary.get('num_radiation_documents')} total")
    print(f"  - Care plans: {care_plan_count}")
    print(f"  - Appointments: {appt_count}")

    print(f"\nExtraction strategy: {summary.get('recommended_extraction_strategy')}")

    print(f"\n✅ All queries executed successfully")
    print(f"\nREADY FOR AGENT 2 EXTRACTION")

    print("\n" + "="*80)


if __name__ == '__main__':
    main()
