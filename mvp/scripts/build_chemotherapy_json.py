"""
Chemotherapy JSON Builder
==========================
Queries Athena views and builds comprehensive chemotherapy JSON for Agent 2 extraction.

Uses the following Athena views:
- v_chemo_medications: All chemotherapy medication orders with comprehensive date coverage
- v_concomitant_medications: Temporal overlap analysis with other medications
- v_chemotherapy_drugs: Reference table of comprehensive chemotherapy drug index
- v_chemotherapy_regimens: Standard chemotherapy protocol/regimen definitions

Implements the comprehensive chemotherapy extraction workflow from:
CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md
"""

import boto3
import pandas as pd
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChemotherapyJSONBuilder:
    """Build comprehensive chemotherapy JSON from Athena views"""

    def __init__(self, aws_profile: str = 'radiant-prod'):
        self.aws_profile = aws_profile
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena_client = self.session.client('athena', region_name='us-east-1')
        self.database = 'fhir_prd_db'
        self.output_location = 's3://radiant-prd-343218191717-us-east-1-prd-athena-results/'

    def query_athena(self, query: str) -> List[Dict]:
        """Execute Athena query and return results as list of dicts"""
        import time

        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.output_location}
        )

        query_execution_id = response['QueryExecutionId']

        # Wait for query completion
        max_wait = 300  # 5 minutes
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait:
            response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = response['QueryExecution']['Status']['State']

            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Athena query failed: {reason}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        if elapsed >= max_wait:
            raise Exception("Athena query timeout")

        # Get results
        results = []
        paginator = self.athena_client.get_paginator('get_query_results')

        for page in paginator.paginate(QueryExecutionId=query_execution_id):
            rows = page['ResultSet']['Rows']

            if not results:  # First page - extract headers
                headers = [col['VarCharValue'] for col in rows[0]['Data']]
                rows = rows[1:]  # Skip header row

            for row in rows:
                result = {}
                for i, col in enumerate(row['Data']):
                    result[headers[i]] = col.get('VarCharValue', '')
                results.append(result)

        return results

    def get_chemo_medications(self, patient_fhir_id: str) -> List[Dict]:
        """Query v_chemo_medications for patient"""
        logger.info(f"Querying chemotherapy medications for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present (Athena views store IDs without prefix)
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_chemo_medications
            WHERE patient_fhir_id = '{athena_patient_id}'
            ORDER BY medication_start_date
        """

        return self.query_athena(query)

    def get_concomitant_medications(self, patient_fhir_id: str,
                                   chemo_start_date: str,
                                   chemo_end_date: str) -> List[Dict]:
        """Query v_concomitant_medications for medications during chemotherapy"""
        logger.info(f"Querying concomitant medications for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_concomitant_medications
            WHERE patient_fhir_id = '{athena_patient_id}'
                AND chemo_medication_start_date >= DATE '{chemo_start_date}'
                AND chemo_medication_start_date <= DATE '{chemo_end_date}'
            ORDER BY concomitant_medication_start_date
            LIMIT 1000
        """

        return self.query_athena(query)

    def group_into_courses(self, medications: List[Dict]) -> List[List[Dict]]:
        """
        Group medications into treatment courses using ±90 day rule

        Medications within 90 days are considered part of same course
        """
        if not medications:
            return []

        # Sort by start date
        sorted_meds = sorted(medications, key=lambda x: x.get('medication_start_date', ''))

        courses = []
        current_course = [sorted_meds[0]]

        for med in sorted_meds[1:]:
            try:
                current_date = datetime.fromisoformat(med.get('medication_start_date', '').split()[0])
                last_date = datetime.fromisoformat(current_course[-1].get('medication_start_date', '').split()[0])

                # Strip timezone info to ensure both are naive (avoid offset-naive vs offset-aware error)
                if current_date.tzinfo is not None:
                    current_date = current_date.replace(tzinfo=None)
                if last_date.tzinfo is not None:
                    last_date = last_date.replace(tzinfo=None)

                # If within 90 days, add to current course
                if (current_date - last_date).days <= 90:
                    current_course.append(med)
                else:
                    # Start new course
                    courses.append(current_course)
                    current_course = [med]
            except:
                # If date parsing fails, continue current course
                current_course.append(med)

        # Add final course
        if current_course:
            courses.append(current_course)

        return courses

    def get_binary_files_for_course(self, patient_fhir_id: str,
                                   course_start: str,
                                   course_end: str) -> Dict[str, List[Dict]]:
        """
        Get binary files relevant to this course using timing windows from design doc:
        - Infusion records: ±3 days
        - Progress notes: ±14 days
        - Treatment plans: 30 days before start
        """
        # Strip "Patient/" prefix if present
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        binary_files = {
            'infusion_records': [],
            'progress_notes': [],
            'treatment_plans': []
        }

        # Infusion records (±3 days)
        infusion_query = f"""
            SELECT *
            FROM v_binary_files
            WHERE patient_fhir_id = '{athena_patient_id}'
                AND (
                    dr_type_text LIKE '%Infusion%'
                    OR dr_type_text LIKE '%Administration%'
                )
                AND ABS(DATE_DIFF('day', DATE(dr_date), DATE '{course_start}')) <= 3
            ORDER BY dr_date
        """

        try:
            binary_files['infusion_records'] = self.query_athena(infusion_query)
        except:
            pass

        # Progress notes (±14 days)
        notes_query = f"""
            SELECT *
            FROM v_binary_files
            WHERE patient_fhir_id = '{athena_patient_id}'
                AND dr_category_text LIKE '%Progress Note%'
                AND ABS(DATE_DIFF('day', DATE(dr_date), DATE '{course_start}')) <= 14
            ORDER BY dr_date
            LIMIT 50
        """

        try:
            binary_files['progress_notes'] = self.query_athena(notes_query)
        except:
            pass

        # Treatment plans (30 days before)
        plans_query = f"""
            SELECT *
            FROM v_binary_files
            WHERE patient_fhir_id = '{athena_patient_id}'
                AND (
                    dr_type_text LIKE '%Treatment Plan%'
                    OR dr_type_text LIKE '%Oncology%'
                    OR dr_category_text LIKE '%Care Plan%'
                )
                AND DATE(dr_date) <= DATE '{course_start}'
                AND DATE_DIFF('day', DATE(dr_date), DATE '{course_start}') <= 30
            ORDER BY dr_date DESC
            LIMIT 20
        """

        try:
            binary_files['treatment_plans'] = self.query_athena(plans_query)
        except:
            pass

        return binary_files

    def build_comprehensive_json(self, patient_fhir_id: str) -> Dict:
        """
        Build comprehensive chemotherapy JSON for Agent 2

        Returns JSON structure following CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md
        """
        logger.info(f"Building comprehensive chemotherapy JSON for {patient_fhir_id}")

        # Query chemotherapy medications
        medications = self.get_chemo_medications(patient_fhir_id)

        if not medications:
            logger.info(f"No chemotherapy data found for {patient_fhir_id}")
            return {
                'patient_id': patient_fhir_id,
                'has_chemotherapy_data': False,
                'total_medication_orders': 0,
                'treatment_courses': [],
                'medications_summary': {}
            }

        # Group into courses
        courses = self.group_into_courses(medications)

        # Build course details
        course_details = []
        for i, course_meds in enumerate(courses, 1):
            course_start = min(m.get('medication_start_date', '') for m in course_meds if m.get('medication_start_date'))
            course_end = max(m.get('medication_end_date', m.get('medication_start_date', ''))
                           for m in course_meds
                           if m.get('medication_end_date') or m.get('medication_start_date'))

            # Get unique drugs in this course
            unique_drugs = list(set(m.get('medication_name', '') for m in course_meds if m.get('medication_name')))

            # Get binary files for validation
            binary_files = self.get_binary_files_for_course(
                patient_fhir_id,
                course_start.split()[0] if course_start else '',
                course_end.split()[0] if course_end else ''
            )

            # Calculate data quality metrics
            binary_confirmation = {
                'infusion_records': len(binary_files['infusion_records']),
                'progress_notes_mentions': len(binary_files['progress_notes']),
                'treatment_plans': len(binary_files['treatment_plans']),
                'confirmed': len(binary_files['infusion_records']) > 0 or len(binary_files['progress_notes']) > 0
            }

            # Calculate duration with timezone-naive datetimes
            duration_days = None
            if course_start and course_end:
                try:
                    start_dt = datetime.fromisoformat(course_start.split()[0])
                    end_dt = datetime.fromisoformat(course_end.split()[0])
                    # Strip timezone info to ensure both are naive
                    if start_dt.tzinfo is not None:
                        start_dt = start_dt.replace(tzinfo=None)
                    if end_dt.tzinfo is not None:
                        end_dt = end_dt.replace(tzinfo=None)
                    duration_days = (end_dt - start_dt).days
                except:
                    pass

            course_detail = {
                'course_id': f'course_{i}',
                'course_number': i,
                'start_date': course_start,
                'end_date': course_end,
                'duration_days': duration_days,
                'medications': course_meds,
                'unique_drugs': unique_drugs,
                'total_orders': len(course_meds),
                'binary_file_confirmation': binary_confirmation,
                'supporting_documents': binary_files
            }

            course_details.append(course_detail)

        # Build comprehensive JSON
        chemo_json = {
            'patient_id': patient_fhir_id,
            'has_chemotherapy_data': True,
            'extraction_timestamp': datetime.now().isoformat(),

            # Summary statistics
            'medications_summary': {
                'total_medication_orders': len(medications),
                'unique_drugs': list(set(m.get('medication_name', '') for m in medications if m.get('medication_name'))),
                'date_range': {
                    'first_chemo': min(m.get('medication_start_date', '') for m in medications if m.get('medication_start_date')),
                    'last_chemo': max(m.get('medication_end_date', m.get('medication_start_date', ''))
                                    for m in medications
                                    if m.get('medication_end_date') or m.get('medication_start_date'))
                },
                'data_completeness': {
                    'with_start_date': sum(1 for m in medications if m.get('medication_start_date')),
                    'with_end_date': sum(1 for m in medications if m.get('medication_end_date')),
                    'with_dosage': sum(1 for m in medications if m.get('medication_dosage_text')),
                    'with_route': sum(1 for m in medications if m.get('medication_route'))
                }
            },

            # Treatment courses
            'treatment_courses': course_details,
            'total_courses': len(courses),

            # All medications (for reference)
            'all_medications': medications,

            # Data quality indicators
            'data_quality': {
                'date_coverage_percentage': (sum(1 for m in medications if m.get('medication_start_date')) /
                                            len(medications) * 100) if medications else 0,
                'has_binary_confirmation': any(c['binary_file_confirmation']['confirmed']
                                              for c in course_details),
                'courses_with_confirmation': sum(1 for c in course_details
                                                if c['binary_file_confirmation']['confirmed']),
                'total_supporting_documents': sum(
                    c['binary_file_confirmation']['infusion_records'] +
                    c['binary_file_confirmation']['progress_notes_mentions'] +
                    c['binary_file_confirmation']['treatment_plans']
                    for c in course_details
                )
            }
        }

        logger.info(f"Chemotherapy JSON built successfully:")
        logger.info(f"  - {len(medications)} total medication orders")
        logger.info(f"  - {len(courses)} treatment courses")
        logger.info(f"  - {len(chemo_json['medications_summary']['unique_drugs'])} unique drugs")
        logger.info(f"  - {chemo_json['data_quality']['date_coverage_percentage']:.1f}% date coverage")
        logger.info(f"  - {chemo_json['data_quality']['courses_with_confirmation']}/{len(courses)} courses with binary confirmation")

        return chemo_json


def main():
    """Test the chemotherapy JSON builder"""
    import argparse

    parser = argparse.ArgumentParser(description='Build chemotherapy JSON from Athena views')
    parser.add_argument('--patient-id', required=True, help='Patient FHIR ID (with or without Patient/ prefix)')
    parser.add_argument('--output', help='Output JSON file path')
    parser.add_argument('--profile', default='radiant-prod', help='AWS profile name')

    args = parser.parse_args()

    # Ensure patient ID has proper format
    patient_id = args.patient_id if args.patient_id.startswith('Patient/') else f'Patient/{args.patient_id}'

    # Build JSON
    builder = ChemotherapyJSONBuilder(aws_profile=args.profile)
    chemo_json = builder.build_comprehensive_json(patient_id)

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(chemo_json, f, indent=2)
        print(f"\n✅ Chemotherapy JSON saved to {args.output}")
    else:
        print(json.dumps(chemo_json, indent=2))


if __name__ == '__main__':
    main()
