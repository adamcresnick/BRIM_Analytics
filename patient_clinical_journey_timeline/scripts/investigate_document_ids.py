#!/usr/bin/env python3
"""
V4.6.1: Investigate Document ID Format Mismatch

This script queries Athena to understand:
1. What IDs does v_radiation_documents return? (document_id vs docc_attachment_url)
2. What format does BinaryFileAgent expect?
3. Are there operative notes for Patient 9's surgeries?
"""

import sys
import boto3
from typing import List, Dict, Any

def query_athena(query: str, description: str = None) -> List[Dict[str, Any]]:
    """Execute Athena query and return results"""
    if description:
        print(f"\n{description}...")

    session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
    client = session.client('athena')

    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )

    query_execution_id = response['QueryExecutionId']

    # Wait for query to complete
    import time
    while True:
        response = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)

    if status != 'SUCCEEDED':
        print(f"  ❌ Query failed: {status}")
        return []

    # Get results
    results = []
    response = client.get_query_results(QueryExecutionId=query_execution_id)

    # Get column names from first row
    columns = [col['Label'] for col in response['ResultSet']['ResultSetMetadata']['ColumnInfo']]

    # Skip header row and process data
    for row in response['ResultSet']['Rows'][1:]:
        values = [field.get('VarCharValue', '') for field in row['Data']]
        results.append(dict(zip(columns, values)))

    print(f"  ✅ Found {len(results)} records")
    return results


def main():
    patient_id = 'ekrJf9m27ER1umcVah.rRqC.9hDY9ch91PfbuGjUHko03'

    print("="*80)
    print("V4.6.1: DOCUMENT ID FORMAT INVESTIGATION")
    print("="*80)

    # 1. Check v_radiation_documents ID structure
    print("\n1. RADIATION DOCUMENTS - ID Structure")
    print("-" * 80)
    query = f"""
    SELECT
        document_id,
        docc_attachment_url as binary_id,
        doc_type_text,
        doc_date,
        extraction_priority
    FROM fhir_prd_db.v_radiation_documents
    WHERE patient_fhir_id = '{patient_id}'
    ORDER BY extraction_priority ASC, doc_date DESC
    LIMIT 5
    """

    radiation_docs = query_athena(query, "Querying v_radiation_documents")
    for i, doc in enumerate(radiation_docs, 1):
        print(f"\n  Doc {i}:")
        print(f"    document_id: {doc.get('document_id', 'NULL')}")
        print(f"    binary_id:   {doc.get('binary_id', 'NULL')}")
        print(f"    doc_type:    {doc.get('doc_type_text', 'NULL')}")
        print(f"    priority:    {doc.get('extraction_priority', 'NULL')}")

    # 2. Check for operative notes
    print("\n\n2. OPERATIVE NOTES - Document Discovery")
    print("-" * 80)

    # Get surgery dates first
    surgery_query = f"""
    SELECT
        procedure_id,
        procedure_date,
        procedure_type
    FROM fhir_prd_db.v_procedures
    WHERE patient_fhir_id = '{patient_id}'
      AND (LOWER(procedure_type) LIKE '%resection%'
           OR LOWER(procedure_type) LIKE '%biopsy%'
           OR LOWER(procedure_type) LIKE '%craniotomy%')
    ORDER BY procedure_date
    """

    surgeries = query_athena(surgery_query, "Finding surgeries for Patient 9")

    for i, surg in enumerate(surgeries, 1):
        surg_date = surg.get('procedure_date', '')
        print(f"\n  Surgery {i}: {surg_date} - {surg.get('procedure_type', 'Unknown')}")

        # Look for operative notes around this date
        doc_query = f"""
        SELECT
            dr.document_reference_id,
            dr.docc_attachment_url,
            dr.dr_type_text,
            dr.dr_date,
            dr.encounter_id
        FROM fhir_prd_db.v_document_reference_enriched dr
        WHERE dr.patient_fhir_id = '{patient_id}'
          AND (
              LOWER(dr.dr_type_text) LIKE '%operative%'
              OR LOWER(dr.dr_type_text) LIKE '%procedure%'
              OR LOWER(dr.dr_type_text) LIKE '%surgery%'
              OR LOWER(dr.dr_type_text) LIKE '%op note%'
          )
          AND ABS(DATE_DIFF('day', CAST(dr.dr_date AS DATE), CAST(TIMESTAMP '{surg_date}' AS DATE))) <= 7
        LIMIT 5
        """

        operative_notes = query_athena(doc_query, f"    Looking for operative notes ±7 days from {surg_date}")

        if operative_notes:
            for j, note in enumerate(operative_notes, 1):
                print(f"      Note {j}: {note.get('dr_type_text', 'Unknown')} ({note.get('dr_date', 'No date')})")
                print(f"        document_reference_id: {note.get('document_reference_id', 'NULL')}")
                print(f"        binary (attachment):   {note.get('docc_attachment_url', 'NULL')}")
        else:
            print(f"      ⚠️  No operative notes found")

            # Try broader search - any clinical note
            broad_query = f"""
            SELECT
                dr.document_reference_id,
                dr.docc_attachment_url,
                dr.dr_type_text,
                dr.dr_date
            FROM fhir_prd_db.v_document_reference_enriched dr
            WHERE dr.patient_fhir_id = '{patient_id}'
              AND ABS(DATE_DIFF('day', CAST(dr.dr_date AS DATE), CAST(TIMESTAMP '{surg_date}' AS DATE))) <= 7
            ORDER BY ABS(DATE_DIFF('day', CAST(dr.dr_date AS DATE), CAST(TIMESTAMP '{surg_date}' AS DATE))) ASC
            LIMIT 3
            """

            any_notes = query_athena(broad_query, f"    Broadening search to ANY document ±7 days")
            for j, note in enumerate(any_notes, 1):
                print(f"      Doc {j}: {note.get('dr_type_text', 'Unknown')} ({note.get('dr_date', 'No date')})")
                print(f"        Has binary: {'YES' if note.get('docc_attachment_url') else 'NO'}")

    # 3. Check progress notes for treatment end dates
    print("\n\n3. PROGRESS NOTES - Treatment End Date Discovery")
    print("-" * 80)

    # Get chemotherapy regimens
    chemo_query = f"""
    SELECT
        medication_request_id,
        medication_name,
        start_date,
        end_date
    FROM fhir_prd_db.v_chemotherapy_regimens
    WHERE patient_fhir_id = '{patient_id}'
    ORDER BY start_date
    LIMIT 3
    """

    chemo_regimens = query_athena(chemo_query, "Finding chemotherapy regimens")

    for i, regimen in enumerate(chemo_regimens, 1):
        start_date = regimen.get('start_date', '')
        end_date = regimen.get('end_date', 'NULL')
        med_name = regimen.get('medication_name', 'Unknown')

        print(f"\n  Regimen {i}: {med_name}")
        print(f"    Start: {start_date}")
        print(f"    End:   {end_date}")

        if not end_date or end_date == 'NULL':
            # Look for progress notes mentioning completion
            notes_query = f"""
            SELECT
                dr.dr_type_text,
                dr.dr_date,
                dr.docc_attachment_url
            FROM fhir_prd_db.v_document_reference_enriched dr
            WHERE dr.patient_fhir_id = '{patient_id}'
              AND dr.dr_date >= TIMESTAMP '{start_date}'
              AND (
                  LOWER(dr.dr_type_text) LIKE '%progress%'
                  OR LOWER(dr.dr_type_text) LIKE '%clinic%'
                  OR LOWER(dr.dr_type_text) LIKE '%visit%'
              )
            ORDER BY dr.dr_date ASC
            LIMIT 5
            """

            progress_notes = query_athena(notes_query, f"    Looking for progress notes after {start_date}")

            if progress_notes:
                print(f"      Found {len(progress_notes)} progress notes - could contain completion info")
                for j, note in enumerate(progress_notes[:2], 1):
                    print(f"        {j}. {note.get('dr_type_text', 'Unknown')} ({note.get('dr_date', 'No date')})")

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
