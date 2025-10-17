"""
CSV-based data source implementation for staging files
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
import logging

from .base import DataSourceInterface

logger = logging.getLogger(__name__)


class CSVDataSource(DataSourceInterface):
    """
    Implementation for current CSV staging files
    Directory structure expected:
    staging_path/
        patient_{patient_id}/
            procedures.csv
            imaging.csv
            binary_files.csv
            measurements.csv
            medications.csv
            diagnoses.csv
            encounters.csv
            radiation_*.csv
    """

    def __init__(self, staging_base_path: str):
        """
        Initialize CSV data source

        Args:
            staging_base_path: Base path to staging files directory
        """
        self.base_path = Path(staging_base_path)
        logger.info(f"Initialized CSV data source at {self.base_path}")

    def _get_patient_path(self, patient_id: str) -> Path:
        """
        Construct patient-specific staging path

        Args:
            patient_id: Patient identifier (FHIR ID)

        Returns:
            Path to patient's staging directory
        """
        # Handle different patient ID formats
        # Remove dots and special characters for folder name
        clean_id = patient_id.replace('.', '').replace('_', '')
        patient_folder = f"patient_{clean_id}"
        return self.base_path / patient_folder

    def _load_csv_with_dates(self,
                            path: Path,
                            date_columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Load CSV with automatic date parsing

        Args:
            path: Path to CSV file
            date_columns: Columns to parse as dates

        Returns:
            DataFrame with parsed dates
        """
        if not path.exists():
            logger.warning(f"File not found: {path}")
            return pd.DataFrame()

        df = pd.read_csv(path)

        # Parse date columns
        if date_columns:
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

        return df

    def _apply_date_filter(self,
                          df: pd.DataFrame,
                          date_column: str,
                          date_range: Optional[Tuple[datetime, datetime]]) -> pd.DataFrame:
        """
        Apply date range filter to DataFrame

        Args:
            df: DataFrame to filter
            date_column: Name of date column
            date_range: Optional tuple of (start_date, end_date)

        Returns:
            Filtered DataFrame
        """
        if date_range and date_column in df.columns:
            # Ensure column is datetime
            if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
                df[date_column] = pd.to_datetime(df[date_column], errors='coerce')

            # Apply filter
            mask = (df[date_column] >= date_range[0]) & (df[date_column] <= date_range[1])
            return df[mask]

        return df

    def get_procedures(self,
                      patient_id: str,
                      date_range: Optional[Tuple[datetime, datetime]] = None,
                      procedure_types: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve procedures data from CSV"""
        path = self._get_patient_path(patient_id) / "procedures.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['procedure_date', 'performed_date_time', 'performed_period_start', 'performed_period_end']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'procedure_date', date_range)

        if procedure_types and 'code_text' in df.columns:
            # Filter by procedure types
            pattern = '|'.join(procedure_types)
            df = df[df['code_text'].str.contains(pattern, case=False, na=False)]

        # Add surgical flag if not present
        if not df.empty and 'is_surgical' not in df.columns:
            surgical_keywords = ['surgery', 'resection', 'craniotomy', 'ventriculostomy',
                               'debulking', 'biopsy', 'excision', 'removal']
            pattern = '|'.join(surgical_keywords)
            df['is_surgical'] = df['code_text'].str.contains(pattern, case=False, na=False)

        return df

    def get_imaging(self,
                   patient_id: str,
                   date_range: Optional[Tuple[datetime, datetime]] = None,
                   modalities: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve imaging data from CSV"""
        path = self._get_patient_path(patient_id) / "imaging.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['imaging_date']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'imaging_date', date_range)

        if modalities and 'imaging_modality' in df.columns:
            df = df[df['imaging_modality'].isin(modalities)]

        return df

    def get_binary_files(self,
                        patient_id: str,
                        document_types: Optional[List[str]] = None,
                        date_range: Optional[Tuple[datetime, datetime]] = None) -> pd.DataFrame:
        """Retrieve binary file metadata from CSV"""
        path = self._get_patient_path(patient_id) / "binary_files.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['document_date', 'context_period_start', 'context_period_end']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'document_date', date_range)

        if document_types and 'document_type' in df.columns:
            # Use contains for flexible matching
            pattern = '|'.join(document_types)
            df = df[df['document_type'].str.contains(pattern, case=False, na=False)]

        return df

    def get_binary_content(self, binary_id: str) -> str:
        """
        Retrieve actual content of a binary file

        Note: For CSV implementation, this would need to fetch from S3
        or local file system based on binary_id
        """
        # TODO: Implement S3 retrieval or local file reading
        logger.warning(f"Binary content retrieval not implemented for CSV source: {binary_id}")
        return ""

    def get_measurements(self,
                        patient_id: str,
                        measurement_types: Optional[List[str]] = None,
                        date_range: Optional[Tuple[datetime, datetime]] = None) -> pd.DataFrame:
        """Retrieve measurements from CSV"""
        path = self._get_patient_path(patient_id) / "measurements.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['measurement_date']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'measurement_date', date_range)

        if measurement_types and 'measurement_type' in df.columns:
            df = df[df['measurement_type'].isin(measurement_types)]

        return df

    def get_medications(self,
                       patient_id: str,
                       date_range: Optional[Tuple[datetime, datetime]] = None,
                       medication_names: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve medications from CSV"""
        path = self._get_patient_path(patient_id) / "medications.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['medication_start_date', 'validity_period_start', 'validity_period_end']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'medication_start_date', date_range)

        if medication_names and 'medication_name' in df.columns:
            pattern = '|'.join(medication_names)
            df = df[df['medication_name'].str.contains(pattern, case=False, na=False)]

        return df

    def get_diagnoses(self,
                     patient_id: str,
                     date_range: Optional[Tuple[datetime, datetime]] = None,
                     icd_codes: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve diagnoses from CSV"""
        path = self._get_patient_path(patient_id) / "diagnoses.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['onset_date_time', 'abatement_date_time', 'recorded_date']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'recorded_date', date_range)

        if icd_codes and 'icd10_code' in df.columns:
            df = df[df['icd10_code'].isin(icd_codes)]

        return df

    def get_encounters(self,
                      patient_id: str,
                      date_range: Optional[Tuple[datetime, datetime]] = None,
                      encounter_types: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve encounters from CSV"""
        path = self._get_patient_path(patient_id) / "encounters.csv"

        df = self._load_csv_with_dates(
            path,
            date_columns=['encounter_date', 'period_start', 'period_end']
        )

        # Apply filters
        df = self._apply_date_filter(df, 'encounter_date', date_range)

        if encounter_types and 'type_text' in df.columns:
            pattern = '|'.join(encounter_types)
            df = df[df['type_text'].str.contains(pattern, case=False, na=False)]

        return df

    def get_radiation(self,
                     patient_id: str,
                     date_range: Optional[Tuple[datetime, datetime]] = None) -> Dict[str, pd.DataFrame]:
        """Retrieve radiation therapy data from multiple CSV files"""
        patient_path = self._get_patient_path(patient_id)
        radiation_data = {}

        # List of expected radiation CSV files
        radiation_files = [
            'radiation_treatment_courses.csv',
            'radiation_treatment_appointments.csv',
            'radiation_care_plan_hierarchy.csv',
            'radiation_care_plan_notes.csv',
            'radiation_service_request_notes.csv',
            'radiation_service_request_rt_history.csv',
            'radiation_data_summary.csv'
        ]

        for file_name in radiation_files:
            path = patient_path / file_name
            if path.exists():
                df = self._load_csv_with_dates(path)

                # Apply date filter if applicable
                for date_col in ['treatment_date', 'appointment_date', 'created_date']:
                    if date_col in df.columns:
                        df = self._apply_date_filter(df, date_col, date_range)
                        break

                key = file_name.replace('.csv', '')
                radiation_data[key] = df

        return radiation_data

    def get_patient_info(self, patient_id: str) -> Dict[str, Any]:
        """
        Get basic patient information

        Args:
            patient_id: Patient identifier

        Returns:
            Dictionary with patient info
        """
        info = {
            'patient_id': patient_id,
            'data_available': False
        }

        patient_path = self._get_patient_path(patient_id)
        if patient_path.exists():
            info['data_available'] = True

            # Try to get birth date from any available source
            procedures = self.get_procedures(patient_id)
            if not procedures.empty and 'age_at_procedure_days' in procedures.columns:
                # Calculate birth date from procedure date and age
                if 'procedure_date' in procedures.columns:
                    first_proc = procedures.iloc[0]
                    proc_date = pd.to_datetime(first_proc['procedure_date'])
                    age_days = first_proc['age_at_procedure_days']
                    info['calculated_birth_date'] = proc_date - pd.Timedelta(days=age_days)

        return info