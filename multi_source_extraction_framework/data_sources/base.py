"""
Base classes for data source interfaces
Enables transition from CSV files to MCP server
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime


class DataSourceInterface(ABC):
    """
    Abstract interface for data sources
    Implementations can be CSV files, MCP server, or direct database
    """

    @abstractmethod
    def get_procedures(self,
                      patient_id: str,
                      date_range: Optional[Tuple[datetime, datetime]] = None,
                      procedure_types: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Retrieve procedures data

        Args:
            patient_id: Patient identifier
            date_range: Optional tuple of (start_date, end_date)
            procedure_types: Optional list of procedure types to filter

        Returns:
            DataFrame with procedure records
        """
        pass

    @abstractmethod
    def get_imaging(self,
                   patient_id: str,
                   date_range: Optional[Tuple[datetime, datetime]] = None,
                   modalities: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Retrieve imaging data

        Args:
            patient_id: Patient identifier
            date_range: Optional date range filter
            modalities: Optional list of imaging modalities (MR, CT, etc.)

        Returns:
            DataFrame with imaging studies
        """
        pass

    @abstractmethod
    def get_binary_files(self,
                        patient_id: str,
                        document_types: Optional[List[str]] = None,
                        date_range: Optional[Tuple[datetime, datetime]] = None) -> pd.DataFrame:
        """
        Retrieve binary file metadata

        Args:
            patient_id: Patient identifier
            document_types: Optional list of document types to filter
            date_range: Optional date range filter

        Returns:
            DataFrame with binary file metadata
        """
        pass

    @abstractmethod
    def get_binary_content(self, binary_id: str) -> str:
        """
        Retrieve actual content of a binary file

        Args:
            binary_id: Binary file identifier

        Returns:
            Content of the binary file as string
        """
        pass

    @abstractmethod
    def get_measurements(self,
                        patient_id: str,
                        measurement_types: Optional[List[str]] = None,
                        date_range: Optional[Tuple[datetime, datetime]] = None) -> pd.DataFrame:
        """
        Retrieve measurements/observations

        Args:
            patient_id: Patient identifier
            measurement_types: Optional list of measurement types
            date_range: Optional date range filter

        Returns:
            DataFrame with measurements
        """
        pass

    @abstractmethod
    def get_medications(self,
                       patient_id: str,
                       date_range: Optional[Tuple[datetime, datetime]] = None,
                       medication_names: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Retrieve medications data

        Args:
            patient_id: Patient identifier
            date_range: Optional date range filter
            medication_names: Optional list of medication names to filter

        Returns:
            DataFrame with medication records
        """
        pass

    @abstractmethod
    def get_diagnoses(self,
                     patient_id: str,
                     date_range: Optional[Tuple[datetime, datetime]] = None,
                     icd_codes: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Retrieve diagnoses data

        Args:
            patient_id: Patient identifier
            date_range: Optional date range filter
            icd_codes: Optional list of ICD codes to filter

        Returns:
            DataFrame with diagnosis records
        """
        pass

    @abstractmethod
    def get_encounters(self,
                      patient_id: str,
                      date_range: Optional[Tuple[datetime, datetime]] = None,
                      encounter_types: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Retrieve encounters data

        Args:
            patient_id: Patient identifier
            date_range: Optional date range filter
            encounter_types: Optional list of encounter types

        Returns:
            DataFrame with encounter records
        """
        pass

    @abstractmethod
    def get_radiation(self,
                     patient_id: str,
                     date_range: Optional[Tuple[datetime, datetime]] = None) -> Dict[str, pd.DataFrame]:
        """
        Retrieve radiation therapy data

        Args:
            patient_id: Patient identifier
            date_range: Optional date range filter

        Returns:
            Dictionary with radiation-related DataFrames
        """
        pass

    # Utility methods
    def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """
        Get high-level patient summary

        Args:
            patient_id: Patient identifier

        Returns:
            Dictionary with patient summary information
        """
        summary = {
            'patient_id': patient_id,
            'total_procedures': len(self.get_procedures(patient_id)),
            'total_imaging': len(self.get_imaging(patient_id)),
            'total_encounters': len(self.get_encounters(patient_id)),
            'total_diagnoses': len(self.get_diagnoses(patient_id))
        }

        # Get date ranges
        procedures = self.get_procedures(patient_id)
        if not procedures.empty and 'procedure_date' in procedures.columns:
            summary['first_procedure'] = procedures['procedure_date'].min()
            summary['last_procedure'] = procedures['procedure_date'].max()

        return summary

    def search_documents(self,
                        patient_id: str,
                        search_terms: List[str],
                        document_types: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Search for documents containing specific terms

        Args:
            patient_id: Patient identifier
            search_terms: List of terms to search for
            document_types: Optional document type filter

        Returns:
            DataFrame with matching documents
        """
        # Default implementation - can be overridden
        binary_files = self.get_binary_files(patient_id, document_types)
        matches = []

        for _, file_info in binary_files.iterrows():
            try:
                content = self.get_binary_content(file_info['binary_id'])
                content_lower = content.lower()

                if any(term.lower() in content_lower for term in search_terms):
                    matches.append(file_info)
            except Exception:
                continue

        return pd.DataFrame(matches) if matches else pd.DataFrame()