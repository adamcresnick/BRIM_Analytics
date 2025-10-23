"""
Radiation Therapy JSON Builder
================================
Queries Athena views and builds comprehensive radiation JSON for Agent 2 extraction.

Uses the following Athena views:
- v_radiation_summary: High-level summary of all radiation treatments
- v_radiation_treatments: Detailed treatment courses with dosing
- v_radiation_documents: Supporting documents (treatment summaries, consults)
- v_radiation_care_plan_hierarchy: Care plan structure
- v_radiation_treatment_appointments: Individual treatment fractions/appointments
"""

import boto3
import pandas as pd
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RadiationJSONBuilder:
    """Build comprehensive radiation therapy JSON from Athena views"""

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

    def get_radiation_summary(self, patient_fhir_id: str) -> Optional[Dict]:
        """Query v_radiation_summary for patient"""
        logger.info(f"Querying radiation summary for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present (Athena views store IDs without prefix)
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_radiation_summary
            WHERE patient_fhir_id = '{athena_patient_id}'
        """

        results = self.query_athena(query)
        return results[0] if results else None

    def get_radiation_treatments(self, patient_fhir_id: str) -> List[Dict]:
        """Query v_radiation_treatments for patient"""
        logger.info(f"Querying radiation treatments for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_radiation_treatments
            WHERE patient_fhir_id = '{athena_patient_id}'
            ORDER BY treatment_start_date
        """

        return self.query_athena(query)

    def get_radiation_documents(self, patient_fhir_id: str) -> List[Dict]:
        """Query v_radiation_documents for patient"""
        logger.info(f"Querying radiation documents for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_radiation_documents
            WHERE patient_fhir_id = '{athena_patient_id}'
            ORDER BY document_date
        """

        return self.query_athena(query)

    def get_radiation_care_plans(self, patient_fhir_id: str) -> List[Dict]:
        """Query v_radiation_care_plan_hierarchy for patient"""
        logger.info(f"Querying radiation care plans for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_radiation_care_plan_hierarchy
            WHERE patient_fhir_id = '{athena_patient_id}'
            ORDER BY period_start
        """

        return self.query_athena(query)

    def get_radiation_appointments(self, patient_fhir_id: str) -> List[Dict]:
        """Query v_radiation_treatment_appointments for patient"""
        logger.info(f"Querying radiation appointments for {patient_fhir_id}...")

        # Strip "Patient/" prefix if present
        athena_patient_id = patient_fhir_id.replace('Patient/', '')

        query = f"""
            SELECT *
            FROM v_radiation_treatment_appointments
            WHERE patient_fhir_id = '{athena_patient_id}'
            ORDER BY appointment_date
        """

        return self.query_athena(query)

    def build_comprehensive_json(self, patient_fhir_id: str) -> Dict:
        """
        Build comprehensive radiation JSON for Agent 2

        Returns JSON structure following RADIATION_EXTRACTION_INTEGRATION_DESIGN.md
        """
        logger.info(f"Building comprehensive radiation JSON for {patient_fhir_id}")

        # Query all radiation data sources
        summary = self.get_radiation_summary(patient_fhir_id)
        treatments = self.get_radiation_treatments(patient_fhir_id)
        documents = self.get_radiation_documents(patient_fhir_id)
        care_plans = self.get_radiation_care_plans(patient_fhir_id)
        appointments = self.get_radiation_appointments(patient_fhir_id)

        # Check if patient has radiation data
        if not summary and not treatments:
            logger.info(f"No radiation data found for {patient_fhir_id}")
            return {
                'patient_id': patient_fhir_id,
                'has_radiation_data': False,
                'radiation_summary': None,
                'treatment_courses': [],
                'supporting_documents': [],
                'care_plans': [],
                'appointments': []
            }

        # Build comprehensive JSON
        radiation_json = {
            'patient_id': patient_fhir_id,
            'has_radiation_data': True,
            'extraction_timestamp': datetime.now().isoformat(),

            # Summary data from v_radiation_summary
            'radiation_summary': summary,

            # Treatment courses from v_radiation_treatments
            'treatment_courses': treatments,
            'total_courses': len(treatments),

            # Supporting documents for validation
            'supporting_documents': {
                'treatment_summaries': [
                    d for d in documents
                    if 'treatment summary' in d.get('document_type', '').lower()
                ],
                'radiation_consults': [
                    d for d in documents
                    if 'consult' in d.get('document_type', '').lower()
                ],
                'treatment_plans': [
                    d for d in documents
                    if 'plan' in d.get('document_type', '').lower()
                ],
                'other_documents': [
                    d for d in documents
                    if 'plan' not in d.get('document_type', '').lower()
                    and 'consult' not in d.get('document_type', '').lower()
                    and 'summary' not in d.get('document_type', '').lower()
                ]
            },
            'total_supporting_documents': len(documents),

            # Care plans
            'care_plans': care_plans,
            'total_care_plans': len(care_plans),

            # Individual appointments/fractions
            'appointments': appointments,
            'total_appointments': len(appointments),

            # Data quality indicators
            'data_quality': {
                'has_summary_data': summary is not None,
                'has_treatment_details': len(treatments) > 0,
                'has_supporting_documents': len(documents) > 0,
                'has_care_plans': len(care_plans) > 0,
                'has_appointment_records': len(appointments) > 0,
                'completeness_score': sum([
                    1 if summary else 0,
                    1 if len(treatments) > 0 else 0,
                    1 if len(documents) > 0 else 0,
                    1 if len(care_plans) > 0 else 0,
                    1 if len(appointments) > 0 else 0
                ]) / 5.0
            }
        }

        logger.info(f"Radiation JSON built successfully:")
        logger.info(f"  - {len(treatments)} treatment courses")
        logger.info(f"  - {len(documents)} supporting documents")
        logger.info(f"  - {len(care_plans)} care plans")
        logger.info(f"  - {len(appointments)} appointments")
        logger.info(f"  - Completeness score: {radiation_json['data_quality']['completeness_score']:.1%}")

        return radiation_json


def main():
    """Test the radiation JSON builder"""
    import argparse

    parser = argparse.ArgumentParser(description='Build radiation therapy JSON from Athena views')
    parser.add_argument('--patient-id', required=True, help='Patient FHIR ID (with or without Patient/ prefix)')
    parser.add_argument('--output', help='Output JSON file path')
    parser.add_argument('--profile', default='radiant-prod', help='AWS profile name')

    args = parser.parse_args()

    # Ensure patient ID has proper format
    patient_id = args.patient_id if args.patient_id.startswith('Patient/') else f'Patient/{args.patient_id}'

    # Build JSON
    builder = RadiationJSONBuilder(aws_profile=args.profile)
    radiation_json = builder.build_comprehensive_json(patient_id)

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(radiation_json, f, indent=2)
        print(f"\n✅ Radiation JSON saved to {args.output}")
    else:
        print(json.dumps(radiation_json, indent=2))


if __name__ == '__main__':
    main()
