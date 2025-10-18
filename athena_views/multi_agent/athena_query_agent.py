"""
Athena Query Agent
==================
Executes patient-specific SQL queries against 15 Athena views.
Provides structured data for validation and cross-source verification.

Author: RADIANT PCA Project
Date: October 17, 2025
Branch: feature/multi-agent-framework
"""

import boto3
import time
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime, timedelta


class AthenaQueryAgent:
    """
    SQL query engine for AWS Athena.
    Executes patient-specific queries against 15 standardized FHIR views.
    """

    def __init__(
        self,
        database: str = 'fhir_prd_db',
        output_location: str = 's3://aws-athena-query-results-us-east-1-YOUR_BUCKET/',
        region: str = 'us-east-1'
    ):
        """
        Initialize Athena Query Agent.

        Args:
            database: Athena database name (default: fhir_prd_db)
            output_location: S3 bucket for query results
            region: AWS region
        """
        self.database = database
        self.output_location = output_location
        self.region = region
        self.client = boto3.client('athena', region_name=region)

        # View definitions (15 standardized views)
        self.views = {
            'demographics': 'v_patient_demographics',
            'diagnoses': 'v_problem_list_diagnoses',
            'procedures': 'v_procedures',
            'medications': 'v_medications',
            'imaging': 'v_imaging',
            'encounters': 'v_encounters',
            'measurements': 'v_measurements',
            'binary_files': 'v_binary_files',
            'molecular_tests': 'v_molecular_tests',
            'radiation_appointments': 'v_radiation_treatment_appointments',
            'radiation_courses': 'v_radiation_treatment_courses',
            'radiation_care_plan_notes': 'v_radiation_care_plan_notes',
            'radiation_care_plan_hierarchy': 'v_radiation_care_plan_hierarchy',
            'radiation_service_request_notes': 'v_radiation_service_request_notes',
            'radiation_rt_history': 'v_radiation_service_request_rt_history'
        }

    def execute_query(self, query: str, max_wait_time: int = 300) -> pd.DataFrame:
        """
        Execute Athena SQL query and return results as DataFrame.

        Args:
            query: SQL query string
            max_wait_time: Maximum wait time in seconds (default: 300)

        Returns:
            pd.DataFrame: Query results
        """
        # Start query execution
        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.output_location}
        )

        query_execution_id = response['QueryExecutionId']

        # Wait for query to complete
        start_time = time.time()
        while True:
            if time.time() - start_time > max_wait_time:
                raise TimeoutError(f"Query execution exceeded {max_wait_time} seconds")

            response = self.client.get_query_execution(
                QueryExecutionId=query_execution_id
            )

            state = response['QueryExecution']['Status']['State']

            if state == 'SUCCEEDED':
                break
            elif state in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise RuntimeError(f"Query {state}: {reason}")

            time.sleep(1)

        # Get query results
        result = self.client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=1000  # Adjust as needed
        )

        # Parse results into DataFrame
        columns = [col['Label'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        rows = []

        for row in result['ResultSet']['Rows'][1:]:  # Skip header row
            rows.append([field.get('VarCharValue', None) for field in row['Data']])

        df = pd.DataFrame(rows, columns=columns)
        return df

    # ==================================================================================
    # CORE CLINICAL VIEWS (9 queries)
    # ==================================================================================

    def query_patient_demographics(self, patient_fhir_id: str) -> Dict[str, Any]:
        """
        Query patient demographics.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            Dict with gender, birth_date, race, ethnicity, age_years
        """
        query = f"""
        SELECT
            patient_fhir_id,
            pd_gender,
            pd_birth_date,
            pd_race,
            pd_ethnicity,
            pd_age_years
        FROM {self.database}.{self.views['demographics']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        df = self.execute_query(query)

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def query_diagnoses(
        self,
        patient_fhir_id: str,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Query problem list diagnoses.

        Args:
            patient_fhir_id: Patient FHIR ID
            date_range: Optional (start_date, end_date) tuple (ISO 8601 format)

        Returns:
            List of diagnosis records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            pld_condition_id,
            pld_diagnosis_name,
            pld_clinical_status,
            pld_onset_date,
            pld_recorded_date,
            age_at_onset_days,
            age_at_recorded_days,
            pld_icd10_code,
            pld_icd10_display,
            pld_snomed_code,
            pld_snomed_display
        FROM {self.database}.{self.views['diagnoses']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if date_range:
            start_date, end_date = date_range
            query += f"""
            AND pld_onset_date >= '{start_date}'
            AND pld_onset_date <= '{end_date}'
            """

        query += " ORDER BY pld_onset_date"

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_procedures(
        self,
        patient_fhir_id: str,
        procedure_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query procedures (surgeries, biopsies, etc.).

        Args:
            patient_fhir_id: Patient FHIR ID
            procedure_type: Optional filter ('surgical', 'biopsy', 'all')

        Returns:
            List of procedure records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            procedure_fhir_id,
            proc_performed_date_time,
            proc_performed_period_start,
            proc_code_text,
            procedure_date,
            age_at_procedure_days,
            pcc_code_coding_code,
            pcc_code_coding_display,
            is_surgical_keyword,
            pbs_body_site_text,
            pp_performer_actor_display
        FROM {self.database}.{self.views['procedures']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if procedure_type == 'surgical':
            query += " AND is_surgical_keyword = true"
        elif procedure_type == 'biopsy':
            query += " AND LOWER(proc_code_text) LIKE '%biopsy%'"

        query += " ORDER BY procedure_date"

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_medications(
        self,
        patient_fhir_id: str,
        medication_name: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Query medications.

        Args:
            patient_fhir_id: Patient FHIR ID
            medication_name: Optional medication name filter (partial match)
            date_range: Optional (start_date, end_date) tuple

        Returns:
            List of medication records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            medication_request_id,
            medication_id,
            medication_name,
            medication_form,
            rx_norm_codes,
            medication_start_date,
            mr_validity_period_start,
            mr_validity_period_end,
            mr_status,
            requester_name,
            encounter_display
        FROM {self.database}.{self.views['medications']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if medication_name:
            query += f" AND LOWER(medication_name) LIKE '%{medication_name.lower()}%'"

        if date_range:
            start_date, end_date = date_range
            query += f"""
            AND medication_start_date >= '{start_date}'
            AND medication_start_date <= '{end_date}'
            """

        query += " ORDER BY medication_start_date"

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_imaging(
        self,
        patient_fhir_id: str,
        modality: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Query imaging studies (MRI, CT, etc.).

        Args:
            patient_fhir_id: Patient FHIR ID
            modality: Optional modality filter ('MRI', 'CT', 'PET')
            date_range: Optional (start_date, end_date) tuple

        Returns:
            List of imaging records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            imaging_procedure_id,
            imaging_date,
            imaging_procedure,
            imaging_modality,
            result_information,
            result_display,
            diagnostic_report_id,
            report_status,
            report_conclusion,
            report_issued,
            category_text,
            age_at_imaging_days,
            age_at_imaging_years
        FROM {self.database}.{self.views['imaging']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if modality:
            query += f" AND LOWER(imaging_modality) LIKE '%{modality.lower()}%'"

        if date_range:
            start_date, end_date = date_range
            query += f"""
            AND imaging_date >= '{start_date}'
            AND imaging_date <= '{end_date}'
            """

        query += " ORDER BY imaging_date DESC"

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_encounters(
        self,
        patient_fhir_id: str,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Query patient encounters.

        Args:
            patient_fhir_id: Patient FHIR ID
            date_range: Optional (start_date, end_date) tuple

        Returns:
            List of encounter records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            encounter_fhir_id,
            encounter_date,
            age_at_encounter_days,
            status,
            class_code,
            class_display,
            service_type_text,
            period_start,
            period_end,
            length_value,
            length_unit,
            type_text_aggregated,
            reason_code_text_aggregated,
            diagnosis_references_aggregated
        FROM {self.database}.{self.views['encounters']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if date_range:
            start_date, end_date = date_range
            query += f"""
            AND period_start >= '{start_date}'
            AND period_start <= '{end_date}'
            """

        query += " ORDER BY period_start"

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_measurements(
        self,
        patient_fhir_id: str,
        measurement_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query lab results and vital signs.

        Args:
            patient_fhir_id: Patient FHIR ID
            measurement_type: Optional measurement type filter

        Returns:
            List of measurement records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            source_table,
            obs_observation_id,
            obs_measurement_type,
            obs_measurement_value,
            obs_measurement_unit,
            obs_measurement_date,
            obs_status,
            lt_test_id,
            lt_measurement_type,
            lt_measurement_date,
            lt_status,
            ltr_measurement_value,
            ltr_measurement_unit,
            age_at_measurement_days
        FROM {self.database}.{self.views['measurements']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if measurement_type:
            query += f"""
            AND (LOWER(obs_measurement_type) LIKE '%{measurement_type.lower()}%'
                 OR LOWER(lt_measurement_type) LIKE '%{measurement_type.lower()}%')
            """

        query += " ORDER BY COALESCE(obs_measurement_date, lt_measurement_date)"

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_binary_files(
        self,
        patient_fhir_id: str,
        doc_type: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Query document references (for targeted document retrieval).

        Args:
            patient_fhir_id: Patient FHIR ID
            doc_type: Optional document type filter
            date_range: Optional (start_date, end_date) tuple

        Returns:
            List of document reference records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            document_reference_id,
            dr_status,
            dr_type_text,
            dr_category_text,
            dr_date,
            dr_description,
            dr_context_period_start,
            dr_context_period_end,
            age_at_document_days
        FROM {self.database}.{self.views['binary_files']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        """

        if doc_type:
            query += f" AND LOWER(dr_type_text) LIKE '%{doc_type.lower()}%'"

        if date_range:
            start_date, end_date = date_range
            query += f"""
            AND dr_date >= '{start_date}'
            AND dr_date <= '{end_date}'
            """

        query += " ORDER BY dr_date DESC LIMIT 100"  # Limit to avoid overwhelming results

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_molecular_tests(
        self,
        patient_fhir_id: str
    ) -> List[Dict[str, Any]]:
        """
        Query molecular/genetic test results.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of molecular test records
        """
        query = f"""
        SELECT
            patient_fhir_id,
            mt_test_id,
            mt_test_date,
            age_at_test_days,
            mt_lab_test_name,
            mt_test_status,
            mtr_component_count,
            mtr_components_list,
            mt_specimen_type,
            mt_specimen_collection_date,
            mt_specimen_body_site,
            mt_procedure_id,
            mt_procedure_name,
            mt_procedure_date
        FROM {self.database}.{self.views['molecular_tests']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        ORDER BY mt_test_date
        """

        df = self.execute_query(query)
        return df.to_dict('records')

    # ==================================================================================
    # RADIATION ONCOLOGY VIEWS (6 queries)
    # ==================================================================================

    def query_radiation_appointments(
        self,
        patient_fhir_id: str
    ) -> List[Dict[str, Any]]:
        """Query radiation treatment appointments."""
        query = f"""
        SELECT *
        FROM {self.database}.{self.views['radiation_appointments']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        ORDER BY appointment_start
        """

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_radiation_courses(
        self,
        patient_fhir_id: str
    ) -> List[Dict[str, Any]]:
        """Query radiation treatment courses."""
        query = f"""
        SELECT *
        FROM {self.database}.{self.views['radiation_courses']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        ORDER BY sr_occurrence_period_start
        """

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_radiation_care_plans(
        self,
        patient_fhir_id: str
    ) -> List[Dict[str, Any]]:
        """Query radiation care plan notes."""
        query = f"""
        SELECT *
        FROM {self.database}.{self.views['radiation_care_plan_notes']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        ORDER BY cp_period_start
        """

        df = self.execute_query(query)
        return df.to_dict('records')

    def query_radiation_service_requests(
        self,
        patient_fhir_id: str
    ) -> List[Dict[str, Any]]:
        """Query radiation service request notes."""
        query = f"""
        SELECT *
        FROM {self.database}.{self.views['radiation_service_request_notes']}
        WHERE patient_fhir_id = '{patient_fhir_id}'
        ORDER BY sr_authored_on
        """

        df = self.execute_query(query)
        return df.to_dict('records')

    # ==================================================================================
    # CONVENIENCE METHODS
    # ==================================================================================

    def query_all_patient_data(
        self,
        patient_fhir_id: str
    ) -> Dict[str, Any]:
        """
        Query all available data for a patient.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            Dict containing all data from 15 views
        """
        return {
            'demographics': self.query_patient_demographics(patient_fhir_id),
            'diagnoses': self.query_diagnoses(patient_fhir_id),
            'procedures': self.query_procedures(patient_fhir_id),
            'medications': self.query_medications(patient_fhir_id),
            'imaging': self.query_imaging(patient_fhir_id),
            'encounters': self.query_encounters(patient_fhir_id),
            'measurements': self.query_measurements(patient_fhir_id),
            'molecular_tests': self.query_molecular_tests(patient_fhir_id),
            'radiation_appointments': self.query_radiation_appointments(patient_fhir_id),
            'radiation_courses': self.query_radiation_courses(patient_fhir_id),
            'radiation_care_plans': self.query_radiation_care_plans(patient_fhir_id),
            'radiation_service_requests': self.query_radiation_service_requests(patient_fhir_id)
        }

    def verify_date_proximity(
        self,
        date1: str,
        date2: str,
        tolerance_days: int = 7
    ) -> bool:
        """
        Verify if two dates are within tolerance window.

        Args:
            date1: First date (ISO 8601 format)
            date2: Second date (ISO 8601 format)
            tolerance_days: Tolerance in days

        Returns:
            True if dates are within tolerance, False otherwise
        """
        try:
            d1 = datetime.fromisoformat(date1.replace('Z', '+00:00'))
            d2 = datetime.fromisoformat(date2.replace('Z', '+00:00'))
            diff = abs((d1 - d2).days)
            return diff <= tolerance_days
        except (ValueError, AttributeError):
            return False

    def get_patient_timeline(
        self,
        patient_fhir_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get chronological timeline of all events for a patient.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of events sorted by date
        """
        timeline = []

        # Get demographics
        demographics = self.query_patient_demographics(patient_fhir_id)
        if demographics:
            timeline.append({
                'date': demographics['pd_birth_date'],
                'event_type': 'birth',
                'description': f"Birth (DOB: {demographics['pd_birth_date']})"
            })

        # Get diagnoses
        diagnoses = self.query_diagnoses(patient_fhir_id)
        for dx in diagnoses:
            timeline.append({
                'date': dx['pld_onset_date'],
                'event_type': 'diagnosis',
                'description': f"Diagnosis: {dx['pld_diagnosis_name']}"
            })

        # Get procedures
        procedures = self.query_procedures(patient_fhir_id)
        for proc in procedures:
            timeline.append({
                'date': proc['procedure_date'],
                'event_type': 'procedure',
                'description': f"Procedure: {proc['proc_code_text']}"
            })

        # Get medications
        medications = self.query_medications(patient_fhir_id)
        for med in medications:
            timeline.append({
                'date': med['medication_start_date'],
                'event_type': 'medication',
                'description': f"Medication: {med['medication_name']}"
            })

        # Sort by date
        timeline.sort(key=lambda x: x['date'] if x['date'] else '9999-12-31')

        return timeline


# ==================================================================================
# EXAMPLE USAGE
# ==================================================================================

if __name__ == '__main__':
    # Initialize agent
    agent = AthenaQueryAgent(
        database='fhir_prd_db',
        output_location='s3://your-athena-results-bucket/',
        region='us-east-1'
    )

    # Test patient
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Query demographics
    print("=== DEMOGRAPHICS ===")
    demographics = agent.query_patient_demographics(patient_id)
    print(demographics)

    # Query surgeries
    print("\n=== SURGERIES ===")
    surgeries = agent.query_procedures(patient_id, procedure_type='surgical')
    for surgery in surgeries:
        print(f"{surgery['procedure_date']}: {surgery['proc_code_text']}")

    # Query medications
    print("\n=== MEDICATIONS ===")
    medications = agent.query_medications(patient_id)
    print(f"Total medications: {len(medications)}")

    # Query molecular tests
    print("\n=== MOLECULAR TESTS ===")
    molecular = agent.query_molecular_tests(patient_id)
    for test in molecular:
        print(f"{test['mt_test_date']}: {test['mt_lab_test_name']}")
        print(f"  Components: {test['mtr_components_list']}")

    # Get patient timeline
    print("\n=== PATIENT TIMELINE ===")
    timeline = agent.get_patient_timeline(patient_id)
    for event in timeline[:10]:  # First 10 events
        print(f"{event['date']}: {event['event_type']} - {event['description']}")
