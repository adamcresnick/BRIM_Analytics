#!/usr/bin/env python3
"""
V4.6.1: Comprehensive Operative Note Investigation

Query ALL relevant Athena tables to find operative notes for Patient 9's surgeries.
"""

import sys
sys.path.insert(0, '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline')

from scripts.patient_timeline_abstraction_V3 import query_athena

def main():
    patient_id = 'ekrJf9m27ER1umcVah.rRqC.9hDY9ch91PfbuGjUHko03'

    print("="*80)
    print("V4.6.1: OPERATIVE NOTE COMPREHENSIVE INVESTIGATION")
    print("="*80)

    # 1. Get surgery dates
    print("\n1. SURGERIES FOR PATIENT 9")
    print("-" * 80)

    surgery_query = f"""
    SELECT
        procedure_id,
        procedure_date,
        procedure_type,
        encounter_id
    FROM fhir_prd_db.v_procedures_tumor
    WHERE patient_fhir_id = '{patient_id}'
      AND (LOWER(procedure_type) LIKE '%resection%'
           OR LOWER(procedure_type) LIKE '%biopsy%'
           OR LOWER(procedure_type) LIKE '%craniotomy%'
           OR LOWER(procedure_type) LIKE '%surgery%')
    ORDER BY procedure_date
    """

    surgeries = query_athena(surgery_query, "Querying v_procedures for surgeries")

    if not surgeries:
        print("  ❌ No surgeries found")
        return

    for i, surg in enumerate(surgeries, 1):
        surg_date = surg.get('procedure_date', '')
        surg_type = surg.get('procedure_type', 'Unknown')
        encounter = surg.get('encounter_id', 'None')

        print(f"\n{'='*80}")
        print(f"SURGERY {i}: {surg_date}")
        print(f"  Type: {surg_type}")
        print(f"  Encounter: {encounter}")
        print(f"{'='*80}")

        # 2. Try v_document_reference_enriched with encounter
        if encounter and encounter != 'None':
            print(f"\n  Strategy 1: v_document_reference_enriched by ENCOUNTER")
            enc_query = f"""
            SELECT
                document_reference_id,
                docc_attachment_url,
                dr_type_text,
                dr_date,
                content_type
            FROM fhir_prd_db.v_document_reference_enriched
            WHERE patient_fhir_id = '{patient_id}'
              AND encounter_id = '{encounter}'
              AND (
                  LOWER(dr_type_text) LIKE '%operative%'
                  OR LOWER(dr_type_text) LIKE '%op note%'
                  OR LOWER(dr_type_text) LIKE '%procedure%'
                  OR LOWER(dr_type_text) LIKE '%surgery%'
              )
            LIMIT 5
            """

            enc_docs = query_athena(enc_query, f"    Encounter-based search")
            if enc_docs:
                for doc in enc_docs:
                    print(f"      ✅ {doc.get('dr_type_text', 'Unknown')} ({doc.get('dr_date', 'No date')})")
                    print(f"         Binary: {doc.get('docc_attachment_url', 'NULL')}")
            else:
                print("      ❌ No operative notes found via encounter")

        # 3. Try v_document_reference_enriched temporal search
        print(f"\n  Strategy 2: v_document_reference_enriched by DATE (±7 days)")
        temporal_query = f"""
        SELECT
            document_reference_id,
            docc_attachment_url,
            dr_type_text,
            dr_date,
            content_type,
            ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE(TIMESTAMP '{surg_date}'))) as days_diff
        FROM fhir_prd_db.v_document_reference_enriched
        WHERE patient_fhir_id = '{patient_id}'
          AND (
              LOWER(dr_type_text) LIKE '%operative%'
              OR LOWER(dr_type_text) LIKE '%op note%'
              OR LOWER(dr_type_text) LIKE '%procedure%'
              OR LOWER(dr_type_text) LIKE '%surgery%'
          )
          AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE(TIMESTAMP '{surg_date}'))) <= 7
        ORDER BY ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE(TIMESTAMP '{surg_date}'))) ASC
        LIMIT 5
        """

        temporal_docs = query_athena(temporal_query, f"    Temporal search (±7 days)")
        if temporal_docs:
            for doc in temporal_docs:
                print(f"      ✅ {doc.get('dr_type_text', 'Unknown')} ({doc.get('dr_date', 'No date')}, {doc.get('days_diff', '?')} days diff)")
                print(f"         Binary: {doc.get('docc_attachment_url', 'NULL')}")
        else:
            print("      ❌ No operative notes found via temporal search")

        # 4. Check source table: document_reference
        print(f"\n  Strategy 3: SOURCE TABLE document_reference (±7 days)")
        source_query = f"""
        SELECT
            id as document_reference_id,
            type_text as dr_type_text,
            date as dr_date,
            content_type
        FROM fhir_prd_db.document_reference
        WHERE subject = '{patient_id}'
          AND (
              LOWER(type_text) LIKE '%operative%'
              OR LOWER(type_text) LIKE '%op note%'
              OR LOWER(type_text) LIKE '%procedure%'
              OR LOWER(type_text) LIKE '%surgery%'
          )
          AND ABS(DATE_DIFF('day', CAST(date AS DATE), DATE(TIMESTAMP '{surg_date}'))) <= 7
        ORDER BY ABS(DATE_DIFF('day', CAST(date AS DATE), DATE(TIMESTAMP '{surg_date}'))) ASC
        LIMIT 5
        """

        source_docs = query_athena(source_query, f"    Source table search")
        if source_docs:
            for doc in source_docs:
                print(f"      ✅ {doc.get('dr_type_text', 'Unknown')} ({doc.get('dr_date', 'No date')})")
                print(f"         Content type: {doc.get('content_type', 'NULL')}")
        else:
            print("      ❌ No operative notes found in source table")

        # 5. Broad search - ANY clinical note around surgery
        print(f"\n  Strategy 4: ANY DOCUMENT TYPE (±3 days) - Broadest search")
        broad_query = f"""
        SELECT
            document_reference_id,
            docc_attachment_url,
            dr_type_text,
            dr_date,
            content_type,
            ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE(TIMESTAMP '{surg_date}'))) as days_diff
        FROM fhir_prd_db.v_document_reference_enriched
        WHERE patient_fhir_id = '{patient_id}'
          AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE(TIMESTAMP '{surg_date}'))) <= 3
          AND docc_attachment_url IS NOT NULL
        ORDER BY ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE(TIMESTAMP '{surg_date}'))) ASC
        LIMIT 10
        """

        broad_docs = query_athena(broad_query, f"    Broad search (any document)")
        if broad_docs:
            print(f"      Found {len(broad_docs)} documents with binaries:")
            for doc in broad_docs:
                print(f"      • {doc.get('dr_type_text', 'Unknown')} ({doc.get('dr_date', 'No date')}, {doc.get('days_diff', '?')} days)")
        else:
            print("      ❌ No documents found at all")

        print()

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
