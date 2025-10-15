"""
Tumor-Specific Surgery Classification Framework
===============================================
Identifies and classifies tumor-related surgical events for BRIM prioritization
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TumorSurgeryClassifier:
    """Classify surgical procedures as tumor-specific and assign surgical event types"""

    # Tumor surgery keywords/codes
    TUMOR_SURGERY_INDICATORS = {
        'resection_terms': [
            'resection', 'excision', 'removal', 'debulking',
            'craniotomy', 'craniectomy', 'gross total', 'subtotal',
            'tumor', 'mass', 'lesion', 'neoplasm'
        ],
        'biopsy_terms': [
            'biopsy', 'stereotactic biopsy', 'needle biopsy',
            'tissue sampling', 'diagnostic sampling'
        ],
        'specific_procedures': [
            'transsphenoidal', 'endoscopic', 'laser ablation',
            'tumor resection', 'mass excision', 'lesion removal'
        ],
        'operative_note_required': [
            'craniotomy', 'craniectomy', 'stereotactic',
            'endoscopic', 'transsphenoidal'
        ]
    }

    # Non-tumor procedures to exclude
    NON_TUMOR_PROCEDURES = [
        'shunt', 'ventriculoperitoneal', 'vp shunt',
        'external ventricular drain', 'evd',
        'wound', 'infection', 'hematoma evacuation',
        'angiography', 'embolization'
    ]

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)

    def classify_procedures(self, procedures_df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify procedures as tumor-specific and assign event types

        Returns DataFrame with additional columns:
        - is_tumor_surgery: Boolean
        - surgery_type: biopsy_only, resection, other
        - requires_operative_note: Boolean
        - surgery_event_type: initial, progressive, recurrence (needs operative note for final determination)
        """
        logger.info("Classifying surgical procedures...")

        # Create classification columns
        procedures_df['is_tumor_surgery'] = False
        procedures_df['surgery_type'] = 'other'
        procedures_df['requires_operative_note'] = False
        procedures_df['preliminary_event_type'] = 'unknown'

        # Check each procedure
        for idx, row in procedures_df.iterrows():
            proc_text = str(row.get('proc_code_text', '')).lower()
            proc_desc = str(row.get('proc_description', '')).lower()
            combined_text = f"{proc_text} {proc_desc}"

            # Check for non-tumor procedures (exclude these)
            is_non_tumor = any(term in combined_text for term in self.NON_TUMOR_PROCEDURES)
            if is_non_tumor:
                continue

            # Check for tumor surgery indicators
            is_resection = any(term in combined_text for term in self.TUMOR_SURGERY_INDICATORS['resection_terms'])
            is_biopsy = any(term in combined_text for term in self.TUMOR_SURGERY_INDICATORS['biopsy_terms'])
            is_specific = any(term in combined_text for term in self.TUMOR_SURGERY_INDICATORS['specific_procedures'])

            if is_resection or is_biopsy or is_specific:
                procedures_df.at[idx, 'is_tumor_surgery'] = True

                # Determine surgery type
                if is_biopsy and not is_resection:
                    procedures_df.at[idx, 'surgery_type'] = 'biopsy_only'
                elif is_resection:
                    procedures_df.at[idx, 'surgery_type'] = 'resection'
                else:
                    procedures_df.at[idx, 'surgery_type'] = 'tumor_procedure'

                # Check if operative note required
                requires_note = any(term in combined_text for term in self.TUMOR_SURGERY_INDICATORS['operative_note_required'])
                procedures_df.at[idx, 'requires_operative_note'] = requires_note

        # Filter to tumor surgeries only
        tumor_surgeries = procedures_df[procedures_df['is_tumor_surgery']].copy()

        # Sort by date to assign preliminary event types
        if 'proc_performed_date_time' in tumor_surgeries.columns:
            tumor_surgeries['proc_date'] = pd.to_datetime(tumor_surgeries['proc_performed_date_time'], utc=True, errors='coerce')
            tumor_surgeries = tumor_surgeries.sort_values('proc_date')

            # Assign preliminary event types based on chronology
            if len(tumor_surgeries) > 0:
                # First surgery is likely initial
                tumor_surgeries.iloc[0, tumor_surgeries.columns.get_loc('preliminary_event_type')] = 'initial_surgery'

                # Subsequent surgeries need operative notes to determine if progressive/recurrence
                for i in range(1, len(tumor_surgeries)):
                    tumor_surgeries.iloc[i, tumor_surgeries.columns.get_loc('preliminary_event_type')] = 'requires_operative_note_review'

        logger.info(f"  Identified {len(tumor_surgeries)} tumor-specific surgeries from {len(procedures_df)} total procedures")

        return tumor_surgeries

    def map_imaging_to_surgeries(self, tumor_surgeries: pd.DataFrame, imaging_df: pd.DataFrame) -> pd.DataFrame:
        """
        Map imaging events to surgical timeline

        Categories:
        - Pre-operative (within 30 days before surgery)
        - Post-operative (within 90 days after surgery)
        - Surveillance (between surgeries or treatments)
        - Treatment monitoring (during chemo/radiation)
        """
        logger.info("Mapping imaging events to surgical timeline...")

        # Parse imaging dates
        if 'imaging_date' not in imaging_df.columns:
            if 'di_study_date_time' in imaging_df.columns:
                imaging_df['imaging_date'] = pd.to_datetime(imaging_df['di_study_date_time'], utc=True, errors='coerce')
            elif 'study_date' in imaging_df.columns:
                imaging_df['imaging_date'] = pd.to_datetime(imaging_df['study_date'], utc=True, errors='coerce')
            else:
                logger.warning("No imaging date column found")
                return imaging_df
        else:
            # Ensure existing imaging_date is datetime
            imaging_df['imaging_date'] = pd.to_datetime(imaging_df['imaging_date'], utc=True, errors='coerce')

        imaging_df['imaging_context'] = 'surveillance'
        imaging_df['associated_surgery_date'] = pd.NaT
        imaging_df['days_from_surgery'] = np.nan

        # For each surgery, find related imaging
        for idx, surgery in tumor_surgeries.iterrows():
            if pd.isna(surgery.get('proc_date')):
                continue

            surgery_date = surgery['proc_date']

            # Pre-operative imaging (30 days before)
            pre_op_mask = (
                (imaging_df['imaging_date'] >= surgery_date - timedelta(days=30)) &
                (imaging_df['imaging_date'] < surgery_date)
            )
            imaging_df.loc[pre_op_mask, 'imaging_context'] = 'pre_operative'
            imaging_df.loc[pre_op_mask, 'associated_surgery_date'] = surgery_date
            imaging_df.loc[pre_op_mask, 'days_from_surgery'] = (imaging_df.loc[pre_op_mask, 'imaging_date'] - surgery_date).dt.days

            # Post-operative imaging (90 days after)
            post_op_mask = (
                (imaging_df['imaging_date'] > surgery_date) &
                (imaging_df['imaging_date'] <= surgery_date + timedelta(days=90))
            )
            imaging_df.loc[post_op_mask, 'imaging_context'] = 'post_operative'
            imaging_df.loc[post_op_mask, 'associated_surgery_date'] = surgery_date
            imaging_df.loc[post_op_mask, 'days_from_surgery'] = (imaging_df.loc[post_op_mask, 'imaging_date'] - surgery_date).dt.days

        # Count imaging by context
        context_counts = imaging_df['imaging_context'].value_counts()
        logger.info(f"  Imaging context mapping:")
        for context, count in context_counts.items():
            logger.info(f"    {context}: {count}")

        return imaging_df

    def identify_priority_imaging(self, imaging_df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify high-priority imaging for abstraction

        Priority levels:
        1. Pre-operative (defines extent of disease)
        2. Post-operative (assesses extent of resection)
        3. Progression/recurrence detection
        4. Treatment response assessment
        """
        imaging_df['abstraction_priority'] = 'low'

        # High priority: pre and post-operative
        high_priority_mask = imaging_df['imaging_context'].isin(['pre_operative', 'post_operative'])
        imaging_df.loc[high_priority_mask, 'abstraction_priority'] = 'high'

        # Medium priority: specific modalities during surveillance
        if 'di_modality' in imaging_df.columns:
            mri_surveillance = (
                (imaging_df['imaging_context'] == 'surveillance') &
                (imaging_df['di_modality'].str.upper() == 'MR')
            )
            imaging_df.loc[mri_surveillance, 'abstraction_priority'] = 'medium'

        priority_counts = imaging_df['abstraction_priority'].value_counts()
        logger.info(f"  Imaging abstraction priorities:")
        for priority, count in priority_counts.items():
            logger.info(f"    {priority}: {count}")

        return imaging_df

    def process_patient(self, patient_id: str) -> Dict[str, pd.DataFrame]:
        """Process a single patient's surgical and imaging data"""

        patient_path = self.staging_path / f"patient_{patient_id}"

        results = {}

        # Load procedures
        procedures_file = patient_path / "procedures.csv"
        if procedures_file.exists():
            procedures_df = pd.read_csv(procedures_file)
            tumor_surgeries = self.classify_procedures(procedures_df)
            results['tumor_surgeries'] = tumor_surgeries
        else:
            logger.warning(f"No procedures file for patient {patient_id}")
            results['tumor_surgeries'] = pd.DataFrame()

        # Load imaging
        imaging_file = patient_path / "imaging.csv"
        if imaging_file.exists():
            imaging_df = pd.read_csv(imaging_file)

            if not results['tumor_surgeries'].empty:
                imaging_df = self.map_imaging_to_surgeries(results['tumor_surgeries'], imaging_df)
                imaging_df = self.identify_priority_imaging(imaging_df)

            results['imaging_with_context'] = imaging_df
        else:
            logger.warning(f"No imaging file for patient {patient_id}")
            results['imaging_with_context'] = pd.DataFrame()

        return results


if __name__ == "__main__":
    # Test with our patient
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    classifier = TumorSurgeryClassifier(staging_path)

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    results = classifier.process_patient(patient_id)

    # Save results
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
    output_path.mkdir(exist_ok=True)

    if not results['tumor_surgeries'].empty:
        results['tumor_surgeries'].to_csv(output_path / f"tumor_surgeries_{patient_id}.csv", index=False)
        print(f"\nTumor surgeries saved: {len(results['tumor_surgeries'])} procedures")

        # Show summary
        print("\nTumor Surgery Summary:")
        print(results['tumor_surgeries'][['proc_date', 'surgery_type', 'preliminary_event_type', 'proc_code_text']].to_string())

    if not results['imaging_with_context'].empty:
        results['imaging_with_context'].to_csv(output_path / f"imaging_with_context_{patient_id}.csv", index=False)
        print(f"\nImaging with context saved: {len(results['imaging_with_context'])} studies")

        # Show priority imaging
        priority_imaging = results['imaging_with_context'][results['imaging_with_context']['abstraction_priority'] == 'high']
        if not priority_imaging.empty:
            print(f"\nHigh Priority Imaging ({len(priority_imaging)} studies):")
            print(priority_imaging[['imaging_date', 'imaging_context', 'di_modality', 'di_description']].head(10).to_string())