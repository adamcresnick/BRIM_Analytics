"""
Enhanced Diagnosis Date Extraction for Brain Tumors
====================================================
Clinically accurate diagnosis date based on initial tumor surgery or MRI
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrainTumorDiagnosisExtractor:
    """
    Extract clinically meaningful diagnosis date for brain tumors

    Clinical Definition:
    - Primary: Date of initial brain tumor surgery (resection or biopsy)
    - Secondary: Date of diagnostic MRI if no surgery performed
    - Fallback: Earliest recorded diagnosis date
    """

    def extract_diagnosis_info(self, patient_id: str, staging_path: Path) -> Dict:
        """
        Extract comprehensive diagnosis information for a brain tumor patient

        Returns:
            Dictionary with:
            - diagnosis_date: Clinically defined diagnosis date
            - diagnosis_type: 'surgical', 'imaging', or 'clinical'
            - initial_surgery_date: Date of first tumor surgery
            - initial_surgery_type: Type of first surgery (resection/biopsy)
            - diagnostic_mri_date: Date of diagnostic MRI if applicable
        """
        patient_path = staging_path / f"patient_{patient_id}"

        diagnosis_info = {
            'diagnosis_date': None,
            'diagnosis_type': None,
            'initial_surgery_date': None,
            'initial_surgery_type': None,
            'diagnostic_mri_date': None,
            'clinical_diagnosis_date': None,
            'age_at_diagnosis': None
        }

        # 1. PRIORITY: Find initial brain tumor surgery
        surgery_date, surgery_type = self._find_initial_tumor_surgery(patient_path)
        if surgery_date:
            diagnosis_info['initial_surgery_date'] = surgery_date
            diagnosis_info['initial_surgery_type'] = surgery_type
            diagnosis_info['diagnosis_date'] = surgery_date
            diagnosis_info['diagnosis_type'] = 'surgical'
            logger.info(f"Diagnosis defined by initial surgery: {surgery_date}")

        # 2. SECONDARY: If no surgery, look for diagnostic imaging
        if not diagnosis_info['diagnosis_date']:
            mri_date = self._find_diagnostic_imaging(patient_path, surgery_date)
            if mri_date:
                diagnosis_info['diagnostic_mri_date'] = mri_date
                diagnosis_info['diagnosis_date'] = mri_date
                diagnosis_info['diagnosis_type'] = 'imaging'
                logger.info(f"Diagnosis defined by MRI (no surgery): {mri_date}")

        # 3. FALLBACK: Use clinical diagnosis date
        if not diagnosis_info['diagnosis_date']:
            clinical_date = self._find_clinical_diagnosis(patient_path)
            if clinical_date:
                diagnosis_info['clinical_diagnosis_date'] = clinical_date
                diagnosis_info['diagnosis_date'] = clinical_date
                diagnosis_info['diagnosis_type'] = 'clinical'
                logger.info(f"Diagnosis defined by clinical record: {clinical_date}")

        # Calculate age at diagnosis if birth date available
        diagnosis_info = self._calculate_age_at_diagnosis(diagnosis_info, patient_id, staging_path)

        return diagnosis_info

    def _find_initial_tumor_surgery(self, patient_path: Path) -> Tuple[Optional[pd.Timestamp], Optional[str]]:
        """
        Find the initial brain tumor surgery (resection or biopsy)

        Returns:
            Tuple of (surgery_date, surgery_type)
        """
        procedures_file = patient_path / "procedures.csv"
        if not procedures_file.exists():
            return None, None

        procedures = pd.read_csv(procedures_file)

        # Tumor surgery indicators
        resection_keywords = [
            'craniotomy', 'craniectomy', 'resection', 'excision',
            'removal', 'tumor', 'lesion', 'mass', 'debulking'
        ]

        biopsy_keywords = [
            'biopsy', 'stereotactic', 'needle', 'sampling'
        ]

        # Exclude non-tumor procedures
        exclude_keywords = [
            'shunt', 'ventriculoperitoneal', 'vp shunt', 'evd',
            'wound', 'infection', 'hematoma', 'angiography'
        ]

        # Parse procedure dates - check multiple possible date columns
        date_col = None
        for col in ['proc_performed_period_start', 'proc_performed_date_time', 'procedure_date']:
            if col in procedures.columns:
                date_col = col
                break

        if not date_col:
            logger.warning("No date column found in procedures")
            return None, None

        procedures[date_col] = pd.to_datetime(procedures[date_col], utc=True, errors='coerce')

        # Find tumor surgeries
        tumor_surgeries = []

        for idx, row in procedures.iterrows():
            if pd.isna(row[date_col]):
                continue

            proc_text = str(row.get('proc_code_text', '')).lower()
            proc_desc = str(row.get('proc_description', '')).lower()
            combined_text = f"{proc_text} {proc_desc}"

            # Skip non-tumor procedures
            if any(keyword in combined_text for keyword in exclude_keywords):
                continue

            # Check for tumor surgery
            is_resection = any(keyword in combined_text for keyword in resection_keywords)
            is_biopsy = any(keyword in combined_text for keyword in biopsy_keywords)

            if is_resection or is_biopsy:
                surgery_type = 'biopsy' if (is_biopsy and not is_resection) else 'resection'
                tumor_surgeries.append({
                    'date': row[date_col],
                    'type': surgery_type,
                    'description': row.get('proc_code_text', '')
                })

        if tumor_surgeries:
            # Return the earliest tumor surgery
            tumor_surgeries.sort(key=lambda x: x['date'])
            first_surgery = tumor_surgeries[0]
            logger.info(f"Found initial tumor surgery: {first_surgery['type']} on {first_surgery['date']}")
            return first_surgery['date'], first_surgery['type']

        return None, None

    def _find_diagnostic_imaging(self, patient_path: Path,
                                 exclude_after_surgery: Optional[pd.Timestamp]) -> Optional[pd.Timestamp]:
        """
        Find diagnostic MRI that established diagnosis (when no surgery performed)

        Args:
            exclude_after_surgery: If surgery exists, exclude imaging after surgery date

        Returns:
            Date of diagnostic imaging
        """
        imaging_file = patient_path / "imaging.csv"
        if not imaging_file.exists():
            return None

        imaging = pd.read_csv(imaging_file)

        # Parse imaging dates
        date_col = 'imaging_date' if 'imaging_date' in imaging.columns else None
        if not date_col:
            return None

        imaging[date_col] = pd.to_datetime(imaging[date_col], utc=True, errors='coerce')

        # Filter for MRI studies
        mri_studies = imaging
        if 'imaging_modality' in imaging.columns:
            mri_studies = imaging[imaging['imaging_modality'].str.upper().eq('MR')]

        # If surgery exists, we shouldn't use this method
        # (diagnosis would be surgical, not imaging-based)
        if exclude_after_surgery:
            return None

        # Find earliest MRI (diagnostic MRI for non-surgical cases)
        if not mri_studies.empty:
            valid_dates = mri_studies[date_col].dropna()
            if not valid_dates.empty:
                earliest_mri = valid_dates.min()
                logger.info(f"Found diagnostic MRI: {earliest_mri}")
                return earliest_mri

        return None

    def _find_clinical_diagnosis(self, patient_path: Path) -> Optional[pd.Timestamp]:
        """
        Find clinical diagnosis date from diagnoses file

        Returns:
            Earliest diagnosis date
        """
        diagnoses_file = patient_path / "diagnoses.csv"
        if not diagnoses_file.exists():
            return None

        diagnoses = pd.read_csv(diagnoses_file)

        # Look for brain tumor related diagnoses
        brain_tumor_keywords = [
            'glioma', 'astrocytoma', 'ependymoma', 'medulloblastoma',
            'brain tumor', 'brain neoplasm', 'intracranial', 'craniopharyngioma',
            'pnet', 'atrt', 'glioblastoma', 'pilocytic', 'optic pathway'
        ]

        # Find date column
        date_col = None
        if 'onset_date_time' in diagnoses.columns:
            date_col = 'onset_date_time'
        elif 'recorded_date' in diagnoses.columns:
            date_col = 'recorded_date'

        if not date_col:
            return None

        diagnoses[date_col] = pd.to_datetime(diagnoses[date_col], utc=True, errors='coerce')

        # Filter for brain tumor diagnoses
        brain_tumor_diagnoses = diagnoses
        if 'diagnosis_name' in diagnoses.columns or 'code_text' in diagnoses.columns:
            text_col = 'diagnosis_name' if 'diagnosis_name' in diagnoses.columns else 'code_text'

            # Find brain tumor related diagnoses
            mask = diagnoses[text_col].apply(
                lambda x: any(keyword in str(x).lower() for keyword in brain_tumor_keywords)
                if pd.notna(x) else False
            )
            brain_tumor_diagnoses = diagnoses[mask]

        # Return earliest diagnosis
        if not brain_tumor_diagnoses.empty:
            valid_dates = brain_tumor_diagnoses[date_col].dropna()
            if not valid_dates.empty:
                earliest = valid_dates.min()
                logger.info(f"Found clinical diagnosis date: {earliest}")
                return earliest

        # If no brain tumor specific, return earliest of any diagnosis
        valid_dates = diagnoses[date_col].dropna()
        if not valid_dates.empty:
            return valid_dates.min()

        return None

    def _calculate_age_at_diagnosis(self, diagnosis_info: Dict,
                                   patient_id: str, staging_path: Path) -> Dict:
        """
        Calculate age at diagnosis based on birth date
        """
        # Get birth date from config
        config_file = staging_path.parent / "patient_config.json"
        birth_date = None

        if config_file.exists():
            import json
            with open(config_file, 'r') as f:
                config = json.load(f)
                if 'birth_date' in config:
                    birth_date = pd.to_datetime(config['birth_date'], utc=True)

        if birth_date and diagnosis_info['diagnosis_date']:
            diagnosis_date = diagnosis_info['diagnosis_date']
            if isinstance(diagnosis_date, str):
                diagnosis_date = pd.to_datetime(diagnosis_date, utc=True)

            if pd.notna(birth_date) and pd.notna(diagnosis_date):
                age_days = (diagnosis_date - birth_date).days
                diagnosis_info['age_at_diagnosis'] = round(age_days / 365.25, 2)
                diagnosis_info['birth_date'] = birth_date.isoformat()

        return diagnosis_info


def compare_diagnosis_methods(patient_id: str, staging_path: Path):
    """
    Compare different methods of defining diagnosis date
    """
    extractor = BrainTumorDiagnosisExtractor()
    diagnosis_info = extractor.extract_diagnosis_info(patient_id, staging_path)

    print("\n" + "="*70)
    print("BRAIN TUMOR DIAGNOSIS DATE ANALYSIS")
    print("="*70)

    print(f"\nPatient ID: {patient_id}")
    print(f"Birth Date: {diagnosis_info.get('birth_date', 'Not found')}")

    print("\n--- Diagnosis Date Components ---")
    print(f"Initial Surgery Date: {diagnosis_info.get('initial_surgery_date', 'No surgery found')}")
    if diagnosis_info.get('initial_surgery_type'):
        print(f"  Surgery Type: {diagnosis_info['initial_surgery_type']}")

    print(f"Diagnostic MRI Date: {diagnosis_info.get('diagnostic_mri_date', 'No diagnostic MRI')}")
    print(f"Clinical Record Date: {diagnosis_info.get('clinical_diagnosis_date', 'No clinical record')}")

    print("\n--- FINAL DIAGNOSIS DETERMINATION ---")
    print(f"Diagnosis Date: {diagnosis_info['diagnosis_date']}")
    print(f"Diagnosis Type: {diagnosis_info['diagnosis_type']}")
    print(f"Age at Diagnosis: {diagnosis_info.get('age_at_diagnosis', 'Cannot calculate')} years")

    if diagnosis_info['diagnosis_type'] == 'surgical':
        print("\n✓ Diagnosis defined by initial tumor surgery (gold standard)")
    elif diagnosis_info['diagnosis_type'] == 'imaging':
        print("\n✓ Diagnosis defined by MRI (no surgery performed)")
    else:
        print("\n⚠ Using clinical diagnosis date (no surgery or diagnostic imaging found)")

    return diagnosis_info


if __name__ == "__main__":
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    diagnosis_info = compare_diagnosis_methods(patient_id, staging_path)

    # Compare with old method
    print("\n" + "="*70)
    print("COMPARISON WITH PREVIOUS METHOD")
    print("="*70)

    print("\nOld Method (earliest diagnosis record): May 19, 2006 → Age 1.0 years")
    print(f"New Method (initial surgery): {diagnosis_info['diagnosis_date']} → Age {diagnosis_info.get('age_at_diagnosis', 'N/A')} years")

    if diagnosis_info.get('initial_surgery_date'):
        surgery_date = pd.to_datetime(diagnosis_info['initial_surgery_date'])
        clinical_date = pd.to_datetime("2006-05-19", utc=True)
        days_diff = (surgery_date - clinical_date).days
        print(f"\nDifference: {days_diff} days between clinical record and actual surgery")