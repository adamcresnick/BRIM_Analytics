"""
Structured Data Query Engine for LLM-enabled extraction.
Allows the LLM to actively query structured data during extraction process.
This is the KEY INNOVATION that prevents hallucination and ensures accuracy.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .staging_views_config import StagingViewsConfiguration

logger = logging.getLogger(__name__)


class StructuredDataQueryEngine:
    """
    Query engine that provides structured data access to the LLM during extraction.
    This allows the LLM to validate facts against ground truth data.
    """

    def __init__(self, staging_path: str, patient_id: str):
        """
        Initialize query engine with patient staging data.

        Args:
            staging_path: Path to staging files directory
            patient_id: Patient FHIR ID
        """
        self.staging_path = Path(staging_path)
        self.patient_id = patient_id
        self.patient_path = self.staging_path / f"patient_{patient_id}"

        # Cache loaded data
        self.data_cache = {}

        # Load available views
        self._load_available_views()

        # Track query history for audit
        self.query_history = []

    def _load_available_views(self):
        """Identify which staging views are available for this patient."""
        self.available_views = {}

        for view_name in StagingViewsConfiguration.STAGING_VIEWS:
            file_path = self.patient_path / f"{view_name}.csv"
            if file_path.exists():
                self.available_views[view_name] = file_path
                logger.info(f"✓ Found staging view: {view_name}")
            else:
                logger.warning(f"✗ Missing staging view: {view_name}")

    def _load_view(self, view_name: str) -> pd.DataFrame:
        """Load a staging view (with caching)."""
        if view_name in self.data_cache:
            return self.data_cache[view_name]

        if view_name not in self.available_views:
            logger.error(f"View {view_name} not available")
            return pd.DataFrame()

        try:
            df = pd.read_csv(self.available_views[view_name])

            # Parse date columns
            config = StagingViewsConfiguration.get_view_config(view_name)
            for date_col in config.date_columns:
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

            self.data_cache[view_name] = df
            return df

        except Exception as e:
            logger.error(f"Failed to load view {view_name}: {str(e)}")
            return pd.DataFrame()

    # ============================================
    # QUERY FUNCTIONS AVAILABLE TO LLM
    # ============================================

    def QUERY_SURGERY_DATES(self) -> List[Dict[str, Any]]:
        """
        Get all surgery dates for the patient.

        Returns:
            List of surgery events with dates, types, and extents
        """
        query_id = f"QUERY_SURGERY_DATES_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        procs_df = self._load_view('procedures')
        if procs_df.empty:
            return []

        # Filter for surgical procedures
        if 'is_surgical_keyword' in procs_df.columns:
            surgical = procs_df[procs_df['is_surgical_keyword'].astype(str).str.lower() == 'true']
        elif 'proc_code_text' in procs_df.columns:
            surgical_keywords = ['craniotomy', 'resection', 'biopsy', 'debulking', 'excision']
            pattern = '|'.join(surgical_keywords)
            surgical = procs_df[procs_df['proc_code_text'].str.contains(pattern, case=False, na=False)]
        else:
            return []

        results = []
        for _, row in surgical.iterrows():
            # Get date
            surgery_date = None
            for date_col in ['proc_performed_date_time', 'procedure_date']:
                if date_col in row and pd.notna(row[date_col]):
                    surgery_date = pd.to_datetime(row[date_col])
                    break

            if surgery_date:
                results.append({
                    'date': surgery_date.strftime('%Y-%m-%d'),
                    'type': row.get('proc_code_text', 'Unknown'),
                    'procedure_id': row.get('procedure_id', ''),
                    'query_id': query_id
                })

        logger.info(f"QUERY_SURGERY_DATES: Found {len(results)} surgeries")
        return sorted(results, key=lambda x: x['date'])

    def QUERY_DIAGNOSIS(self) -> Dict[str, Any]:
        """
        Get primary brain tumor diagnosis and date.

        Returns:
            Primary diagnosis information
        """
        query_id = f"QUERY_DIAGNOSIS_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        diag_df = self._load_view('diagnoses')
        if diag_df.empty:
            return {}

        # Brain tumor ICD-10 codes
        brain_tumor_codes = ['C71', 'D43', 'D33']

        # Filter for brain tumors
        if 'icd10_code' in diag_df.columns:
            brain_tumors = diag_df[
                diag_df['icd10_code'].str.startswith(tuple(brain_tumor_codes), na=False)
            ]

            if not brain_tumors.empty:
                # Get first diagnosis
                brain_tumors = brain_tumors.sort_values('recorded_date', na_position='last')
                first_diagnosis = brain_tumors.iloc[0]

                result = {
                    'diagnosis': first_diagnosis.get('diagnosis_name', 'Unknown'),
                    'icd10_code': first_diagnosis.get('icd10_code', ''),
                    'date': pd.to_datetime(first_diagnosis.get('recorded_date')).strftime('%Y-%m-%d')
                    if pd.notna(first_diagnosis.get('recorded_date')) else None,
                    'query_id': query_id
                }

                logger.info(f"QUERY_DIAGNOSIS: {result['diagnosis']}")
                return result

        return {}

    def QUERY_MEDICATIONS(self, drug_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Verify patient received specific medication or get all medications.

        Args:
            drug_name: Optional specific drug to search for

        Returns:
            List of medication exposures
        """
        query_id = f"QUERY_MEDICATIONS_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        meds_df = self._load_view('medications')
        if meds_df.empty:
            return []

        # Filter by drug name if provided
        if drug_name:
            meds_df = meds_df[
                meds_df['medication_name'].str.contains(drug_name, case=False, na=False)
            ]

        results = []
        for _, row in meds_df.iterrows():
            # Get dates
            start_date = None
            end_date = None

            for col in ['medication_start_date', 'med_date_given_start']:
                if col in row and pd.notna(row[col]):
                    start_date = pd.to_datetime(row[col])
                    break

            for col in ['medication_end_date', 'med_date_given_end']:
                if col in row and pd.notna(row[col]):
                    end_date = pd.to_datetime(row[col])
                    break

            results.append({
                'medication': row.get('medication_name', 'Unknown'),
                'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
                'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
                'is_chemotherapy': row.get('is_chemotherapy', False),
                'query_id': query_id
            })

        logger.info(f"QUERY_MEDICATIONS: Found {len(results)} medications")
        return results

    def QUERY_MOLECULAR_TESTS(self) -> List[Dict[str, Any]]:
        """
        Get molecular test results and dates.

        Returns:
            List of molecular test results
        """
        query_id = f"QUERY_MOLECULAR_TESTS_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        # Try to load molecular tests if available
        results = []

        # Check measurements for molecular markers
        meas_df = self._load_view('measurements')
        if not meas_df.empty and 'measurement_name' in meas_df.columns:
            molecular_keywords = ['BRAF', 'KIAA1549', 'fusion', 'mutation', 'amplification']
            pattern = '|'.join(molecular_keywords)

            molecular = meas_df[
                meas_df['measurement_name'].str.contains(pattern, case=False, na=False)
            ]

            for _, row in molecular.iterrows():
                results.append({
                    'test': row.get('measurement_name', 'Unknown'),
                    'date': pd.to_datetime(row.get('measurement_date')).strftime('%Y-%m-%d')
                    if pd.notna(row.get('measurement_date')) else None,
                    'result': row.get('value_text', row.get('value_numeric', 'Unknown')),
                    'query_id': query_id
                })

        logger.info(f"QUERY_MOLECULAR_TESTS: Found {len(results)} tests")
        return results

    def QUERY_IMAGING_ON_DATE(self, target_date: str, tolerance_days: int = 7) -> List[Dict[str, Any]]:
        """
        Get imaging studies near a specific date.

        Args:
            target_date: Target date (YYYY-MM-DD)
            tolerance_days: Days before/after to search

        Returns:
            List of imaging studies within window
        """
        query_id = f"QUERY_IMAGING_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        imaging_df = self._load_view('imaging')
        if imaging_df.empty:
            return []

        target = pd.to_datetime(target_date)
        results = []

        for _, row in imaging_df.iterrows():
            # Get imaging date
            img_date = None
            for col in ['imaging_date', 'study_date']:
                if col in row and pd.notna(row[col]):
                    img_date = pd.to_datetime(row[col])
                    break

            if img_date:
                days_diff = abs((img_date - target).days)
                if days_diff <= tolerance_days:
                    results.append({
                        'study_date': img_date.strftime('%Y-%m-%d'),
                        'modality': row.get('modality', 'Unknown'),
                        'findings': row.get('findings', ''),
                        'impression': row.get('impression', ''),
                        'days_from_target': days_diff,
                        'query_id': query_id
                    })

        results = sorted(results, key=lambda x: x['days_from_target'])
        logger.info(f"QUERY_IMAGING_ON_DATE: Found {len(results)} studies near {target_date}")
        return results

    def QUERY_POSTOP_IMAGING(self, surgery_date: str) -> Optional[Dict[str, Any]]:
        """
        CRITICAL: Get post-operative imaging within 72 hours of surgery.
        This is the GOLD STANDARD for extent of resection.

        Args:
            surgery_date: Date of surgery (YYYY-MM-DD)

        Returns:
            Post-op imaging findings including extent assessment
        """
        query_id = f"QUERY_POSTOP_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        imaging_df = self._load_view('imaging')
        if imaging_df.empty:
            return None

        surgery = pd.to_datetime(surgery_date)
        postop_window = timedelta(hours=72)

        # Find imaging within 72 hours post-surgery
        for _, row in imaging_df.iterrows():
            img_date = None
            for col in ['imaging_date', 'study_date']:
                if col in row and pd.notna(row[col]):
                    img_date = pd.to_datetime(row[col])
                    break

            if img_date:
                # Ensure both dates are timezone-naive for comparison
                if surgery.tzinfo is not None and img_date.tzinfo is None:
                    img_date = img_date.replace(tzinfo=surgery.tzinfo)
                elif surgery.tzinfo is None and img_date.tzinfo is not None:
                    img_date = img_date.replace(tzinfo=None)

                time_diff = img_date - surgery
                if timedelta(0) <= time_diff <= postop_window:
                    # Check for MRI specifically
                    if 'modality' in row and 'MRI' in str(row.get('modality', '')):
                        # Extract extent from findings/impression
                        findings = str(row.get('findings', '')) + ' ' + str(row.get('impression', ''))

                        extent = self._extract_extent_from_text(findings)

                        result = {
                            'imaging_date': img_date.strftime('%Y-%m-%d'),
                            'hours_post_surgery': int(time_diff.total_seconds() / 3600),
                            'modality': 'MRI',
                            'extent': extent,
                            'residual_tumor': 'residual' in findings.lower(),
                            'findings_text': findings[:500],
                            'query_id': query_id,
                            'validation_status': 'GOLD_STANDARD'
                        }

                        logger.info(f"QUERY_POSTOP_IMAGING: Found MRI at {result['hours_post_surgery']}h post-op")
                        return result

        logger.warning(f"QUERY_POSTOP_IMAGING: No post-op imaging found within 72h of {surgery_date}")
        return None

    def _extract_extent_from_text(self, text: str) -> str:
        """Extract extent of resection from imaging text."""
        text_lower = text.lower()

        extent_mappings = {
            'gross total': 'Gross total resection',
            'gtr': 'Gross total resection',
            'near total': 'Near total resection',
            'ntr': 'Near total resection',
            'subtotal': 'Subtotal resection',
            'str': 'Subtotal resection',
            'partial': 'Partial resection',
            'biopsy': 'Biopsy only',
            'no residual': 'Gross total resection',
            'complete resection': 'Gross total resection'
        }

        for keyword, extent in extent_mappings.items():
            if keyword in text_lower:
                return extent

        # Check for residual tumor
        if 'residual' in text_lower:
            if 'minimal' in text_lower:
                return 'Near total resection'
            else:
                return 'Subtotal resection'

        return 'Unable to determine'

    def QUERY_PROBLEM_LIST(self) -> List[Dict[str, Any]]:
        """
        Get active clinical problems from problem list.

        Returns:
            List of active problems
        """
        query_id = f"QUERY_PROBLEMS_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        diag_df = self._load_view('diagnoses')
        if diag_df.empty:
            return []

        # Filter for active problems
        if 'status' in diag_df.columns:
            active = diag_df[diag_df['status'].str.lower() == 'active']
        else:
            active = diag_df

        results = []
        for _, row in active.iterrows():
            results.append({
                'problem': row.get('diagnosis_name', 'Unknown'),
                'icd10_code': row.get('icd10_code', ''),
                'status': row.get('status', 'active'),
                'onset_date': pd.to_datetime(row.get('onset_date_time')).strftime('%Y-%m-%d')
                if pd.notna(row.get('onset_date_time')) else None,
                'query_id': query_id
            })

        logger.info(f"QUERY_PROBLEM_LIST: Found {len(results)} active problems")
        return results

    def QUERY_ENCOUNTERS_RANGE(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get encounters within a date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of encounters in range
        """
        query_id = f"QUERY_ENCOUNTERS_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        enc_df = self._load_view('encounters')
        if enc_df.empty:
            return []

        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        results = []

        for _, row in enc_df.iterrows():
            enc_date = pd.to_datetime(row.get('encounter_date'))
            if enc_date and start <= enc_date <= end:
                results.append({
                    'date': enc_date.strftime('%Y-%m-%d'),
                    'type': row.get('encounter_type', 'Unknown'),
                    'department': row.get('department', ''),
                    'provider_specialty': row.get('provider_specialty', ''),
                    'query_id': query_id
                })

        results = sorted(results, key=lambda x: x['date'])
        logger.info(f"QUERY_ENCOUNTERS_RANGE: Found {len(results)} encounters between {start_date} and {end_date}")
        return results

    def VERIFY_DATE_PROXIMITY(self, date1: str, date2: str, tolerance_days: int = 7) -> bool:
        """
        Check if two dates are within tolerance.

        Args:
            date1: First date (YYYY-MM-DD)
            date2: Second date (YYYY-MM-DD)
            tolerance_days: Maximum days apart

        Returns:
            True if dates are within tolerance
        """
        query_id = f"VERIFY_DATES_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        d1 = pd.to_datetime(date1)
        d2 = pd.to_datetime(date2)

        days_apart = abs((d1 - d2).days)
        result = days_apart <= tolerance_days

        logger.info(f"VERIFY_DATE_PROXIMITY: {date1} vs {date2} = {days_apart} days apart (tolerance={tolerance_days})")
        return result

    def QUERY_CHEMOTHERAPY_EXPOSURE(self) -> List[Dict[str, Any]]:
        """
        Get chemotherapy drug exposures with line of therapy.

        Returns:
            List of chemotherapy regimens
        """
        query_id = f"QUERY_CHEMO_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        meds_df = self._load_view('medications')
        if meds_df.empty:
            return []

        # Filter for chemotherapy
        if 'is_chemotherapy' in meds_df.columns:
            chemo_df = meds_df[meds_df['is_chemotherapy'] == True]
        else:
            # Use known chemo drugs
            chemo_drugs = [
                'bevacizumab', 'carboplatin', 'vincristine', 'temozolomide',
                'lomustine', 'etoposide', 'irinotecan', 'vinblastine'
            ]
            pattern = '|'.join(chemo_drugs)
            chemo_df = meds_df[
                meds_df['medication_name'].str.contains(pattern, case=False, na=False)
            ]

        # Group by drug and dates to identify regimens
        results = []
        for drug_name in chemo_df['medication_name'].unique():
            drug_rows = chemo_df[chemo_df['medication_name'] == drug_name]
            drug_rows = drug_rows.sort_values('medication_start_date')

            results.append({
                'drug': drug_name,
                'start_date': pd.to_datetime(drug_rows.iloc[0]['medication_start_date']).strftime('%Y-%m-%d')
                if pd.notna(drug_rows.iloc[0]['medication_start_date']) else None,
                'exposures': len(drug_rows),
                'query_id': query_id
            })

        logger.info(f"QUERY_CHEMOTHERAPY_EXPOSURE: Found {len(results)} chemotherapy drugs")
        return results

    def QUERY_RADIATION_DETAILS(self) -> Optional[Dict[str, Any]]:
        """
        Get radiation therapy details.

        Returns:
            Radiation therapy parameters
        """
        query_id = f"QUERY_RADIATION_{datetime.now().isoformat()}"
        self.query_history.append(query_id)

        # Check for radiation treatment courses
        rad_df = self._load_view('radiation_treatment_courses')
        if not rad_df.empty and len(rad_df) > 0:
            # Get most recent course
            course = rad_df.iloc[0]

            result = {
                'site': course.get('treatment_site', 'Unknown'),
                'total_dose_gy': course.get('total_dose_gy', None),
                'fractions': course.get('fractions', None),
                'technique': course.get('technique', ''),
                'start_date': pd.to_datetime(course.get('start_date')).strftime('%Y-%m-%d')
                if pd.notna(course.get('start_date')) else None,
                'query_id': query_id
            }

            logger.info(f"QUERY_RADIATION_DETAILS: Found radiation to {result['site']}")
            return result

        return None

    def get_query_history(self) -> List[str]:
        """Get history of all queries executed."""
        return self.query_history

    def clear_cache(self):
        """Clear cached data."""
        self.data_cache = {}
        logger.info("Cleared data cache")