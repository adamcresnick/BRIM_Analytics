#!/usr/bin/env python3
"""
Validation Script: Surgery Event vs Operative Note Coverage
============================================================
Purpose: Assess whether every tumor surgery event has an operative note identified
Date: 2025-10-22

This script validates the operative note matching logic by:
1. Querying all tumor surgeries for a patient
2. Querying all operative notes for a patient
3. Attempting to match each surgery to an operative note using three strategies:
   - STRATEGY 1: Exact date match on dr_context_period_start (PREFERRED)
   - STRATEGY 2: ±3 day window on dr_context_period_start (FALLBACK)
   - STRATEGY 3: ±7 day window on dr_date (LAST RESORT)
4. Reporting gaps and coverage statistics

Usage:
    python3 validate_surgery_operative_note_coverage.py --patient-id <patient_fhir_id>
    python3 validate_surgery_operative_note_coverage.py --all-patients
"""

import sys
import os
import argparse
from datetime import datetime
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.athena_client import query_athena

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def validate_patient_coverage(patient_fhir_id: str) -> dict:
    """
    Validate operative note coverage for a single patient.

    Returns dict with:
        - surgeries: list of surgery events
        - operative_notes: list of operative note documents
        - matches: list of successful matches
        - unmatched: list of unmatched surgeries
        - coverage_pct: percentage of surgeries with operative notes
    """

    logger.info("="*80)
    logger.info(f"VALIDATING PATIENT: {patient_fhir_id}")
    logger.info("="*80)

    # Query 1: Get all tumor surgeries
    surgery_query = f"""
    SELECT
        procedure_fhir_id,
        procedure_date,
        surgery_type,
        proc_code_text,
        cpt_code
    FROM fhir_prd_db.v_procedures_tumor
    WHERE patient_fhir_id = '{patient_fhir_id}'
        AND is_tumor_surgery = true
    ORDER BY procedure_date
    """

    surgeries = query_athena(surgery_query, None)
    logger.info(f"\n✅ Found {len(surgeries)} tumor surgeries")

    if not surgeries:
        logger.info("   No tumor surgeries found for this patient")
        return {
            'surgeries': [],
            'operative_notes': [],
            'matches': [],
            'unmatched': [],
            'coverage_pct': 0.0
        }

    # Query 2: Get all operative notes
    opnote_query = f"""
    SELECT
        document_reference_id,
        dr_type_text,
        dr_date,
        dr_context_period_start,
        dr_category_text,
        content_type
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_fhir_id}'
        AND (
            dr_type_text LIKE 'OP Note%'
            OR dr_type_text = 'Operative Record'
            OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
        )
    ORDER BY dr_context_period_start
    """

    operative_notes = query_athena(opnote_query, None)
    logger.info(f"✅ Found {len(operative_notes)} operative note documents\n")

    # Match each surgery to an operative note
    matches = []
    unmatched = []

    logger.info("="*80)
    logger.info("MATCHING SURGERIES TO OPERATIVE NOTES")
    logger.info("="*80)

    for i, surgery in enumerate(surgeries, 1):
        surg_date = surgery['procedure_date'].split()[0] if ' ' in surgery['procedure_date'] else surgery['procedure_date']
        surg_type = surgery.get('surgery_type', 'unknown')

        logger.info(f"\n{i}. Surgery Date: {surg_date}")
        logger.info(f"   Type: {surg_type}")
        logger.info(f"   CPT: {surgery.get('cpt_code', 'N/A')}")

        # STRATEGY 1: Exact date match on dr_context_period_start
        exact_match_query = f"""
        SELECT
            document_reference_id,
            dr_type_text,
            dr_context_period_start,
            0 as days_diff,
            'exact_context_period' as match_strategy
        FROM fhir_prd_db.v_binary_files
        WHERE patient_fhir_id = '{patient_fhir_id}'
            AND (
                dr_type_text LIKE 'OP Note%'
                OR dr_type_text = 'Operative Record'
                OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
            )
            AND DATE(dr_context_period_start) = DATE '{surg_date}'
        ORDER BY
            CASE
                WHEN dr_type_text LIKE '%Complete%' THEN 1
                WHEN dr_type_text = 'Anesthesia Postprocedure Evaluation' THEN 2
                WHEN dr_type_text LIKE '%Brief%' THEN 3
                ELSE 4
            END
        LIMIT 1
        """

        exact_matches = query_athena(exact_match_query, None)

        if exact_matches and len(exact_matches) > 0:
            match = exact_matches[0]
            logger.info(f"   ✅ EXACT MATCH: {match['dr_type_text']}")
            logger.info(f"      Context period: {match['dr_context_period_start']}")
            matches.append({
                'surgery': surgery,
                'operative_note': match,
                'match_strategy': 'exact_context_period'
            })
            continue

        # STRATEGY 2: ±3 day window on dr_context_period_start
        near_match_query = f"""
        SELECT
            document_reference_id,
            dr_type_text,
            dr_context_period_start,
            DATE_DIFF('day', DATE(dr_context_period_start), DATE '{surg_date}') as days_diff,
            'near_context_period' as match_strategy
        FROM fhir_prd_db.v_binary_files
        WHERE patient_fhir_id = '{patient_fhir_id}'
            AND (
                dr_type_text LIKE 'OP Note%'
                OR dr_type_text = 'Operative Record'
                OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
            )
            AND dr_context_period_start IS NOT NULL
            AND ABS(DATE_DIFF('day', DATE(dr_context_period_start), DATE '{surg_date}')) <= 3
        ORDER BY
            ABS(DATE_DIFF('day', DATE(dr_context_period_start), DATE '{surg_date}'))
        LIMIT 1
        """

        near_matches = query_athena(near_match_query, None)

        if near_matches and len(near_matches) > 0:
            match = near_matches[0]
            logger.info(f"   ⚠️  NEAR MATCH (±3 days): {match['dr_type_text']}")
            logger.info(f"      Context period: {match['dr_context_period_start']}")
            logger.info(f"      Days diff: {match.get('days_diff', 'N/A')}")
            matches.append({
                'surgery': surgery,
                'operative_note': match,
                'match_strategy': 'near_context_period'
            })
            continue

        # STRATEGY 3: ±7 day window on dr_date (last resort)
        dr_date_match_query = f"""
        SELECT
            document_reference_id,
            dr_type_text,
            dr_date,
            dr_context_period_start,
            DATE_DIFF('day', DATE(dr_date), DATE '{surg_date}') as days_diff,
            'dr_date_window' as match_strategy
        FROM fhir_prd_db.v_binary_files
        WHERE patient_fhir_id = '{patient_fhir_id}'
            AND (
                dr_type_text LIKE 'OP Note%'
                OR dr_type_text = 'Operative Record'
                OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
            )
            AND dr_date IS NOT NULL
            AND ABS(DATE_DIFF('day', DATE(dr_date), DATE '{surg_date}')) <= 7
        ORDER BY
            ABS(DATE_DIFF('day', DATE(dr_date), DATE '{surg_date}'))
        LIMIT 1
        """

        dr_date_matches = query_athena(dr_date_match_query, None)

        if dr_date_matches and len(dr_date_matches) > 0:
            match = dr_date_matches[0]
            logger.info(f"   ⚠️  DR_DATE MATCH (±7 days): {match['dr_type_text']}")
            logger.info(f"      Document date: {match.get('dr_date', 'N/A')}")
            logger.info(f"      Context period: {match.get('dr_context_period_start', 'N/A')}")
            logger.info(f"      Days diff: {match.get('days_diff', 'N/A')}")
            matches.append({
                'surgery': surgery,
                'operative_note': match,
                'match_strategy': 'dr_date_window'
            })
            continue

        # No match found
        logger.info(f"   ❌ NO MATCH FOUND")
        unmatched.append(surgery)

    # Calculate coverage
    coverage_pct = (len(matches) / len(surgeries) * 100) if surgeries else 0.0

    # Summary
    logger.info("\n" + "="*80)
    logger.info("COVERAGE SUMMARY")
    logger.info("="*80)
    logger.info(f"Total surgeries: {len(surgeries)}")
    logger.info(f"Matched: {len(matches)} ({coverage_pct:.1f}%)")
    logger.info(f"Unmatched: {len(unmatched)}")

    if matches:
        logger.info("\nMatch strategy breakdown:")
        strategies = {}
        for match in matches:
            strat = match['match_strategy']
            strategies[strat] = strategies.get(strat, 0) + 1
        for strat, count in sorted(strategies.items()):
            logger.info(f"  {strat}: {count}")

    if unmatched:
        logger.info("\n" + "="*80)
        logger.info(f"UNMATCHED SURGERIES ({len(unmatched)})")
        logger.info("="*80)
        logger.info(f"Total operative notes available: {len(operative_notes)}")
        if operative_notes:
            contexts = [n.get('dr_context_period_start') for n in operative_notes if n.get('dr_context_period_start')]
            if contexts:
                logger.info(f"Context period date range: {min(contexts)} to {max(contexts)}")

    return {
        'surgeries': surgeries,
        'operative_notes': operative_notes,
        'matches': matches,
        'unmatched': unmatched,
        'coverage_pct': coverage_pct
    }


def main():
    parser = argparse.ArgumentParser(
        description='Validate operative note coverage for tumor surgeries'
    )
    parser.add_argument(
        '--patient-id',
        type=str,
        help='Patient FHIR ID (without "Patient/" prefix)'
    )
    parser.add_argument(
        '--all-patients',
        action='store_true',
        help='Validate all patients with tumor surgeries'
    )

    args = parser.parse_args()

    if not args.patient_id and not args.all_patients:
        parser.print_help()
        sys.exit(1)

    if args.patient_id:
        result = validate_patient_coverage(args.patient_id)
        logger.info("\n" + "="*80)
        logger.info(f"FINAL COVERAGE: {result['coverage_pct']:.1f}%")
        logger.info("="*80)

    elif args.all_patients:
        logger.info("Querying all patients with tumor surgeries...")

        all_patients_query = """
        SELECT DISTINCT patient_fhir_id
        FROM fhir_prd_db.v_procedures_tumor
        WHERE is_tumor_surgery = true
        ORDER BY patient_fhir_id
        """

        patients = query_athena(all_patients_query, "Querying all patients")
        logger.info(f"Found {len(patients)} patients with tumor surgeries\n")

        all_results = []
        for i, patient in enumerate(patients, 1):
            patient_id = patient['patient_fhir_id']
            logger.info(f"\n{'='*80}")
            logger.info(f"PATIENT {i}/{len(patients)}")
            logger.info(f"{'='*80}")

            result = validate_patient_coverage(patient_id)
            all_results.append({
                'patient_id': patient_id,
                **result
            })

        # Overall summary
        total_surgeries = sum(len(r['surgeries']) for r in all_results)
        total_matched = sum(len(r['matches']) for r in all_results)
        overall_coverage = (total_matched / total_surgeries * 100) if total_surgeries > 0 else 0.0

        logger.info("\n" + "="*80)
        logger.info("OVERALL COHORT SUMMARY")
        logger.info("="*80)
        logger.info(f"Total patients: {len(all_results)}")
        logger.info(f"Total surgeries: {total_surgeries}")
        logger.info(f"Total matched: {total_matched}")
        logger.info(f"Overall coverage: {overall_coverage:.1f}%")

        # Patients with gaps
        patients_with_gaps = [r for r in all_results if len(r['unmatched']) > 0]
        if patients_with_gaps:
            logger.info(f"\nPatients with gaps: {len(patients_with_gaps)}")
            for r in patients_with_gaps:
                logger.info(f"  {r['patient_id']}: {len(r['unmatched'])} unmatched surgeries")


if __name__ == '__main__':
    main()
