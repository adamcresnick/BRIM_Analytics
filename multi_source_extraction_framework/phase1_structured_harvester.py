"""
PHASE 1: Structured Data Harvesting
====================================
Direct extraction from Athena structured tables
Pre-populate known values (procedures, measurements, diagnoses)
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StructuredDataHarvester:
    """
    Phase 1: Extract all directly available structured features from Athena
    """

    def __init__(self, staging_path: str):
        self.staging_path = Path(staging_path)
        self.extracted_features = {}
        self.data_sources = {}

    def harvest_for_patient(self, patient_id: str, birth_date: str) -> Dict[str, Any]:
        """
        Main entry point for Phase 1 - harvest all structured data

        Args:
            patient_id: Patient FHIR ID
            birth_date: Patient birth date (YYYY-MM-DD)

        Returns:
            Dictionary of extracted structured features
        """
        logger.info(f"PHASE 1: Starting structured data harvesting for patient {patient_id}")

        self.patient_id = patient_id
        # Make birth_date timezone-aware (UTC) to match data
        self.birth_date = pd.to_datetime(birth_date).tz_localize('UTC')
        self.patient_path = self._get_patient_path(patient_id)

        # Load all structured data sources
        self._load_data_sources()

        # Extract features from each source
        features = {}

        # 1. Extract surgical procedures
        surgical_features = self._extract_surgical_procedures()
        features.update(surgical_features)

        # 2. Extract diagnoses
        diagnosis_features = self._extract_diagnoses()
        features.update(diagnosis_features)

        # 3. Extract measurements
        measurement_features = self._extract_measurements()
        features.update(measurement_features)

        # 4. Extract medications
        medication_features = self._extract_medications()
        features.update(medication_features)

        # 5. Extract radiation therapy
        radiation_features = self._extract_radiation()
        features.update(radiation_features)

        # 6. Extract imaging progression events
        imaging_features = self._extract_imaging_progression()
        features.update(imaging_features)

        # 7. Calculate derived features
        derived_features = self._calculate_derived_features(features)
        features.update(derived_features)

        logger.info(f"PHASE 1 Complete: Extracted {len(features)} structured features")

        self.extracted_features = features
        return features

    def _get_patient_path(self, patient_id: str) -> Path:
        """Get patient-specific staging directory"""
        # Keep the patient ID as-is (with dots preserved)
        return self.staging_path / f"patient_{patient_id}"

    def _load_data_sources(self):
        """Load all available structured data sources"""
        logger.info("Loading structured data sources...")

        # Define data sources with their date columns (validated column names)
        sources = {
            'procedures': ['proc_performed_date_time', 'procedure_date'],
            'diagnoses': ['onset_date_time', 'recorded_date'],
            'measurements': ['measurement_date'],
            'medications': ['medication_start_date', 'med_date_given_start', 'med_date_given_end'],
            'encounters': ['encounter_date'],
            'imaging': ['imaging_date'],
            'binary_files': ['dr_date']
        }

        for source, date_cols in sources.items():
            file_path = self.patient_path / f"{source}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                # Parse date columns and normalize timezones
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                self.data_sources[source] = df
                logger.info(f"  Loaded {source}: {len(df)} records")
            else:
                self.data_sources[source] = pd.DataFrame()
                logger.warning(f"  {source} not found")

    def _extract_surgical_procedures(self) -> Dict[str, Any]:
        """Extract surgical procedure features"""
        features = {}

        if 'procedures' not in self.data_sources or self.data_sources['procedures'].empty:
            features['has_surgery'] = 'No'
            features['total_surgeries'] = 0
            return features

        procs_df = self.data_sources['procedures'].copy()

        # Check if is_surgical_keyword column exists
        if 'is_surgical_keyword' in procs_df.columns:
            # Use existing is_surgical_keyword column (converted to boolean)
            procs_df['is_surgical'] = procs_df['is_surgical_keyword'].astype(str).str.lower() == 'true'
        elif 'proc_code_text' in procs_df.columns:
            # Fallback: Identify surgical procedures by keywords
            surgical_keywords = [
                'craniotomy', 'craniectomy', 'resection', 'debulking',
                'ventriculostomy', 'shunt', 'biopsy', 'excision', 'removal',
                'surgery', 'surgical', 'operation'
            ]
            pattern = '|'.join(surgical_keywords)
            procs_df['is_surgical'] = procs_df['proc_code_text'].str.contains(
                pattern, case=False, na=False
            )
        else:
            features['has_surgery'] = 'No'
            features['total_surgeries'] = 0
            return features

        surgical_procs = procs_df[procs_df['is_surgical']]

        if not surgical_procs.empty:
            features['has_surgery'] = 'Yes'
            features['total_surgeries'] = len(surgical_procs)

            # Determine date column to use
            date_col = None
            if 'proc_performed_date_time' in surgical_procs.columns:
                date_col = 'proc_performed_date_time'
            elif 'procedure_date' in surgical_procs.columns:
                date_col = 'procedure_date'

            if date_col:
                # Sort by date
                surgical_procs = surgical_procs.sort_values(date_col)

                # First surgery
                first_surgery = surgical_procs.iloc[0]
                first_date = first_surgery[date_col]
                if pd.notna(first_date):
                    features['first_surgery_date'] = first_date.isoformat()
                    features['age_at_first_surgery_days'] = (
                        first_date - self.birth_date
                    ).days

                # Last surgery (if multiple)
                if len(surgical_procs) > 1:
                    last_surgery = surgical_procs.iloc[-1]
                    last_date = last_surgery[date_col]
                    if pd.notna(last_date):
                        features['last_surgery_date'] = last_date.isoformat()
                        features['age_at_last_surgery_days'] = (
                            last_date - self.birth_date
                        ).days

                # List all surgery dates
                surgery_dates = surgical_procs[date_col].dropna()
                if len(surgery_dates) > 0:
                    features['surgery_dates'] = [str(d.date()) for d in surgery_dates.unique()]

            # Surgery types
            if 'proc_code_text' in surgical_procs.columns:
                features['surgery_types'] = surgical_procs['proc_code_text'].dropna().unique().tolist()
        else:
            features['has_surgery'] = 'No'
            features['total_surgeries'] = 0

        return features

    def _extract_diagnoses(self) -> Dict[str, Any]:
        """Extract diagnosis features"""
        features = {}

        if 'diagnoses' not in self.data_sources or self.data_sources['diagnoses'].empty:
            return features

        diag_df = self.data_sources['diagnoses']

        # Brain tumor diagnoses
        brain_tumor_codes = ['C71', 'D43', 'D33']  # Malignant, uncertain, benign brain tumors

        if 'icd10_code' in diag_df.columns:
            # Find brain tumor diagnoses
            brain_tumors = diag_df[
                diag_df['icd10_code'].str.startswith(tuple(brain_tumor_codes), na=False)
            ]

            if not brain_tumors.empty:
                features['has_brain_tumor_diagnosis'] = 'Yes'
                features['brain_tumor_count'] = len(brain_tumors)

                # Get first diagnosis date
                if 'recorded_date' in brain_tumors.columns:
                    first_diagnosis = brain_tumors.sort_values('recorded_date').iloc[0]
                    features['first_diagnosis_date'] = first_diagnosis['recorded_date'].isoformat()
                    features['age_at_diagnosis_days'] = (
                        first_diagnosis['recorded_date'] - self.birth_date
                    ).days

                # Diagnosis names
                if 'diagnosis_name' in brain_tumors.columns:
                    features['brain_tumor_diagnoses'] = brain_tumors['diagnosis_name'].unique().tolist()
            else:
                features['has_brain_tumor_diagnosis'] = 'No'

        # Metastasis diagnoses
        metastasis_codes = ['C79', 'C78']  # Secondary malignant neoplasms

        if 'icd10_code' in diag_df.columns:
            metastases = diag_df[
                diag_df['icd10_code'].str.startswith(tuple(metastasis_codes), na=False)
            ]

            features['has_metastasis_diagnosis'] = 'Yes' if not metastases.empty else 'No'
            if not metastases.empty:
                features['metastasis_sites'] = metastases['diagnosis_name'].unique().tolist()

        return features

    def _extract_measurements(self) -> Dict[str, Any]:
        """Extract measurement features"""
        features = {}

        if 'measurements' not in self.data_sources or self.data_sources['measurements'].empty:
            return features

        meas_df = self.data_sources['measurements']

        # Tumor measurements - check multiple possible column names
        tumor_keywords = ['tumor', 'lesion', 'mass', 'enhancement']

        # Try different column names for measurement type
        type_col = None
        if 'obs_code_text' in meas_df.columns:
            type_col = 'obs_code_text'
        elif 'obs_measurement_type' in meas_df.columns:
            type_col = 'obs_measurement_type'
        elif 'measurement_type' in meas_df.columns:
            type_col = 'measurement_type'

        if type_col:
            # Find tumor-related measurements
            pattern = '|'.join(tumor_keywords)
            tumor_measurements = meas_df[
                meas_df[type_col].astype(str).str.contains(pattern, case=False, na=False)
            ]

            if not tumor_measurements.empty:
                features['has_tumor_measurements'] = 'Yes'
                features['tumor_measurement_count'] = len(tumor_measurements)

                # Get size measurements if available - try different column names
                value_col = None
                if 'obs_value_quantity_value' in tumor_measurements.columns:
                    value_col = 'obs_value_quantity_value'
                elif 'obs_measurement_value' in tumor_measurements.columns:
                    value_col = 'obs_measurement_value'
                elif 'measurement_value' in tumor_measurements.columns:
                    value_col = 'measurement_value'

                if value_col:
                    # Extract numeric values
                    numeric_values = pd.to_numeric(
                        tumor_measurements[value_col],
                        errors='coerce'
                    ).dropna()

                    if not numeric_values.empty:
                        features['max_tumor_size_mm'] = float(numeric_values.max())
                        features['min_tumor_size_mm'] = float(numeric_values.min())

        return features

    def _extract_medications(self) -> Dict[str, Any]:
        """Extract medication features"""
        features = {}

        if 'medications' not in self.data_sources or self.data_sources['medications'].empty:
            features['has_chemotherapy'] = 'No'
            features['has_immunotherapy'] = 'No'
            features['has_bevacizumab'] = 'No'
            features['has_selumetinib'] = 'No'
            return features

        meds_df = self.data_sources['medications']

        # Chemotherapy and targeted therapy medications
        chemo_keywords = [
            'bevacizumab', 'avastin',  # Anti-VEGF (found 72 records in this patient)
            'selumetinib', 'koselugo',  # MEK inhibitor (found 22 records in this patient)
            'temozolomide', 'temodar',  # Alkylating agent
            'carboplatin', 'vincristine', 'lomustine',  # Traditional chemo
            'irinotecan', 'etoposide', 'cyclophosphamide',  # Additional chemo
            'dabrafenib', 'tafinlar',  # BRAF inhibitor
            'trametinib', 'mekinist',  # MEK inhibitor
            'everolimus', 'afinitor'  # mTOR inhibitor
        ]

        # Immunotherapy medications
        immuno_keywords = [
            'pembrolizumab', 'nivolumab', 'ipilimumab', 'atezolizumab'
        ]

        if 'medication_name' in meds_df.columns:
            # Check for chemotherapy
            chemo_pattern = '|'.join(chemo_keywords)
            has_chemo = meds_df['medication_name'].str.contains(
                chemo_pattern, case=False, na=False
            ).any()

            features['has_chemotherapy'] = 'Yes' if has_chemo else 'No'

            if has_chemo:
                chemo_meds = meds_df[
                    meds_df['medication_name'].str.contains(chemo_pattern, case=False, na=False)
                ]
                features['chemotherapy_agents'] = chemo_meds['medication_name'].dropna().unique().tolist()

                # Check for medication start date column
                date_col = None
                if 'medication_start_date' in chemo_meds.columns:
                    date_col = 'medication_start_date'
                elif 'med_date_given_start' in chemo_meds.columns:
                    date_col = 'med_date_given_start'

                if date_col:
                    chemo_with_date = chemo_meds[chemo_meds[date_col].notna()].sort_values(date_col)
                    if not chemo_with_date.empty:
                        first_chemo = chemo_with_date.iloc[0]
                        features['first_chemotherapy_date'] = first_chemo[date_col].isoformat()
                        features['age_at_first_chemotherapy_days'] = (
                            first_chemo[date_col] - self.birth_date
                        ).days

            # Specific check for bevacizumab
            has_bev = meds_df['medication_name'].str.contains(
                'bevacizumab|avastin', case=False, na=False
            ).any()
            features['has_bevacizumab'] = 'Yes' if has_bev else 'No'

            # Specific check for selumetinib (MEK inhibitor)
            has_sel = meds_df['medication_name'].str.contains(
                'selumetinib|koselugo', case=False, na=False
            ).any()
            features['has_selumetinib'] = 'Yes' if has_sel else 'No'

            # Check for immunotherapy
            immuno_pattern = '|'.join(immuno_keywords)
            has_immuno = meds_df['medication_name'].str.contains(
                immuno_pattern, case=False, na=False
            ).any()

            features['has_immunotherapy'] = 'Yes' if has_immuno else 'No'

            if has_immuno:
                immuno_meds = meds_df[
                    meds_df['medication_name'].str.contains(immuno_pattern, case=False, na=False)
                ]
                features['immunotherapy_agents'] = immuno_meds['medication_name'].dropna().unique().tolist()

        return features

    def _extract_radiation(self) -> Dict[str, Any]:
        """Extract radiation therapy features"""
        features = {}

        # Check for radiation files
        radiation_files = [
            'radiation_treatment_courses.csv',
            'radiation_treatment_appointments.csv',
            'radiation_data_summary.csv'
        ]

        has_radiation = False

        for file_name in radiation_files:
            file_path = self.patient_path / file_name
            if file_path.exists():
                df = pd.read_csv(file_path)
                if not df.empty:
                    has_radiation = True

                    # Extract radiation details
                    if file_name == 'radiation_treatment_courses.csv':
                        features['radiation_course_count'] = len(df)

                        # Get treatment dates
                        if 'start_date' in df.columns:
                            df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce', utc=True)
                            first_radiation = df.sort_values('start_date').iloc[0]
                            if pd.notna(first_radiation['start_date']):
                                features['first_radiation_date'] = first_radiation['start_date'].isoformat()
                                features['age_at_first_radiation_days'] = (
                                    first_radiation['start_date'] - self.birth_date
                                ).days

                    elif file_name == 'radiation_treatment_appointments.csv':
                        features['radiation_fraction_count'] = len(df)

        features['has_radiation_therapy'] = 'Yes' if has_radiation else 'No'

        return features

    def _extract_imaging_progression(self) -> Dict[str, Any]:
        """Extract progression events from imaging reports"""
        features = {}

        if 'imaging' not in self.data_sources or self.data_sources['imaging'].empty:
            features['has_progression_imaging'] = 'No'
            return features

        imaging_df = self.data_sources['imaging']

        # Keywords indicating progression
        progression_keywords = [
            'progression', 'progressing', 'progressive', 'increased', 'enlargement',
            'worsening', 'new lesion', 'new enhancement', 'disease progression'
        ]

        # Keywords indicating improvement/stable
        improvement_keywords = [
            'improvement', 'reduction', 'decreased', 'stable', 'no progression',
            'no evidence of progression', 'non-progressing'
        ]

        # Check in result_information column
        if 'result_information' in imaging_df.columns:
            progression_pattern = '|'.join(progression_keywords)
            improvement_pattern = '|'.join(improvement_keywords)

            # Find reports with progression mentions
            progression_reports = imaging_df[
                imaging_df['result_information'].astype(str).str.contains(
                    progression_pattern, case=False, na=False
                )
            ]

            # Find reports with improvement mentions
            improvement_reports = imaging_df[
                imaging_df['result_information'].astype(str).str.contains(
                    improvement_pattern, case=False, na=False
                )
            ]

            features['has_progression_imaging'] = 'Yes' if not progression_reports.empty else 'No'
            features['has_improvement_imaging'] = 'Yes' if not improvement_reports.empty else 'No'

            if not progression_reports.empty and 'imaging_date' in progression_reports.columns:
                # Get earliest progression date
                progression_dates = progression_reports['imaging_date'].dropna().sort_values()
                if len(progression_dates) > 0:
                    first_progression_date = progression_dates.iloc[0]
                    features['first_progression_imaging_date'] = first_progression_date.isoformat()
                    features['age_at_first_progression_days'] = (
                        first_progression_date - self.birth_date
                    ).days
                    features['progression_event_count'] = len(progression_dates)

            if not improvement_reports.empty and 'imaging_date' in improvement_reports.columns:
                improvement_dates = improvement_reports['imaging_date'].dropna()
                if len(improvement_dates) > 0:
                    features['improvement_event_count'] = len(improvement_dates)

        return features

    def _calculate_derived_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate derived features from extracted data"""
        derived = {}

        # Treatment modality combinations
        treatments = []
        if features.get('has_surgery') == 'Yes':
            treatments.append('Surgery')
        if features.get('has_radiation_therapy') == 'Yes':
            treatments.append('Radiation')
        if features.get('has_chemotherapy') == 'Yes':
            treatments.append('Chemotherapy')
        if features.get('has_immunotherapy') == 'Yes':
            treatments.append('Immunotherapy')

        derived['treatment_modalities'] = treatments
        derived['treatment_modality_count'] = len(treatments)

        # Time between diagnosis and first treatment
        if 'first_diagnosis_date' in features:
            diagnosis_date = pd.to_datetime(features['first_diagnosis_date'])

            treatment_dates = []
            if 'first_surgery_date' in features:
                treatment_dates.append(pd.to_datetime(features['first_surgery_date']))
            if 'first_radiation_date' in features:
                treatment_dates.append(pd.to_datetime(features['first_radiation_date']))
            if 'first_chemotherapy_date' in features:
                treatment_dates.append(pd.to_datetime(features['first_chemotherapy_date']))

            if treatment_dates:
                first_treatment = min(treatment_dates)
                derived['days_diagnosis_to_treatment'] = (first_treatment - diagnosis_date).days

        # Multiple surgery indicator
        if features.get('total_surgeries', 0) > 1:
            derived['has_multiple_surgeries'] = 'Yes'

            # Time between surgeries
            if 'surgery_dates' in features and len(features['surgery_dates']) > 1:
                dates = sorted([pd.to_datetime(d) for d in features['surgery_dates']])
                derived['days_between_first_last_surgery'] = (dates[-1] - dates[0]).days
        else:
            derived['has_multiple_surgeries'] = 'No'

        return derived

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of extracted structured features"""
        summary = {
            'patient_id': self.patient_id,
            'total_features_extracted': len(self.extracted_features),
            'data_sources_available': list(self.data_sources.keys()),
            'feature_categories': {
                'surgical': sum(1 for k in self.extracted_features if 'surg' in k.lower()),
                'diagnosis': sum(1 for k in self.extracted_features if 'diagnosis' in k.lower()),
                'treatment': sum(1 for k in self.extracted_features if any(
                    t in k.lower() for t in ['chemo', 'radiation', 'immuno']
                )),
                'measurements': sum(1 for k in self.extracted_features if 'measurement' in k.lower())
            }
        }
        return summary


if __name__ == "__main__":
    import json

    # Example usage with correct staging path
    staging_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files"

    harvester = StructuredDataHarvester(staging_path)

    # Extract for test patient
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    birth_date = "2005-05-13"

    features = harvester.harvest_for_patient(
        patient_id=patient_id,
        birth_date=birth_date
    )

    # Print results
    print("\n" + "="*80)
    print("PHASE 1 RESULTS: Structured Data Harvesting")
    print("="*80)

    for key, value in sorted(features.items()):
        print(f"{key}: {value}")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    summary = harvester.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")

    # Save to outputs directory
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"phase1_structured_features_{patient_id}.json"
    with open(output_file, 'w') as f:
        json.dump(features, f, indent=2, default=str)

    print(f"\n\nFeatures saved to: {output_file}")