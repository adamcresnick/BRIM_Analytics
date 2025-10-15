"""
Enhanced Clinical Event Prioritization Framework
=================================================
Comprehensive imaging prioritization including treatment changes
and survival endpoint tracking for standardized cohort processing
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import logging
from datetime import datetime, timedelta
import json
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedClinicalPrioritization:
    """
    Enhanced framework for clinical event prioritization with:
    - Imaging at chemotherapy change points
    - Last contact tracking for survival
    - Standardized configuration for cohort processing
    """

    # Standardized windows for imaging prioritization (configurable)
    DEFAULT_CONFIG = {
        'imaging_windows': {
            'pre_surgery_days': 30,
            'post_surgery_days': 90,
            'chemo_change_window_days': 30,
            'radiation_planning_window_days': 14,
            'progression_assessment_days': 90
        },
        'priority_levels': {
            'critical': ['pre_operative', 'post_operative', 'treatment_change', 'progression_suspected'],
            'high': ['chemo_response', 'radiation_planning', 'new_symptoms'],
            'medium': ['surveillance_mri', 'treatment_monitoring'],
            'low': ['routine_surveillance', 'other']
        },
        'survival_endpoints': {
            'track_last_contact': True,
            'track_last_imaging': True,
            'track_last_treatment': True,
            'track_last_lab': True
        }
    }

    def __init__(self, staging_path: Path, config: Optional[Dict] = None):
        self.staging_path = Path(staging_path)
        self.config = config if config else self.DEFAULT_CONFIG

    def identify_chemotherapy_changes(self, chemo_df: pd.DataFrame) -> List[Dict]:
        """
        Identify chemotherapy change points that require imaging assessment

        Returns list of change events with dates and types:
        - New drug started
        - Drug discontinued
        - Regimen change
        """
        changes = []

        if chemo_df.empty:
            return changes

        # Ensure dates are parsed
        date_cols = ['start_date', 'end_date', 'medication_start_date', 'cp_period_start']
        for col in date_cols:
            if col in chemo_df.columns:
                chemo_df[col] = pd.to_datetime(chemo_df[col], utc=True, errors='coerce')

        # Group by drug to find starts and stops
        if 'drug_name' in chemo_df.columns:
            for drug in chemo_df['drug_name'].unique():
                drug_records = chemo_df[chemo_df['drug_name'] == drug].copy()

                # Find start dates
                start_col = None
                for col in ['start_date', 'medication_start_date', 'cp_period_start']:
                    if col in drug_records.columns and drug_records[col].notna().any():
                        start_col = col
                        break

                if start_col:
                    starts = drug_records[drug_records[start_col].notna()][start_col].unique()
                    for start_date in starts:
                        changes.append({
                            'date': pd.to_datetime(start_date, utc=True),
                            'event_type': 'chemo_start',
                            'drug': drug,
                            'change_type': 'new_drug_started'
                        })

                # Find end dates
                end_col = None
                for col in ['end_date', 'cp_period_end', 'mr_validity_period_end']:
                    if col in drug_records.columns and drug_records[col].notna().any():
                        end_col = col
                        break

                if end_col:
                    ends = drug_records[drug_records[end_col].notna()][end_col].unique()
                    for end_date in ends:
                        changes.append({
                            'date': pd.to_datetime(end_date, utc=True),
                            'event_type': 'chemo_end',
                            'drug': drug,
                            'change_type': 'drug_discontinued'
                        })

        # Sort by date
        changes = sorted(changes, key=lambda x: x['date'] if pd.notna(x['date']) else pd.Timestamp.min.tz_localize('UTC'))

        # Identify regimen changes (multiple drugs starting/stopping within 7 days)
        if len(changes) > 1:
            for i in range(len(changes) - 1):
                if pd.notna(changes[i]['date']) and pd.notna(changes[i+1]['date']):
                    days_between = abs((changes[i+1]['date'] - changes[i]['date']).days)
                    if days_between <= 7 and changes[i]['drug'] != changes[i+1]['drug']:
                        # Mark as regimen change
                        changes[i]['change_type'] = 'regimen_change'
                        changes[i+1]['change_type'] = 'regimen_change'

        logger.info(f"Identified {len(changes)} chemotherapy change points")
        return changes

    def prioritize_imaging_enhanced(self, imaging_df: pd.DataFrame,
                                   tumor_surgeries: pd.DataFrame,
                                   chemo_changes: List[Dict],
                                   radiation_courses: pd.DataFrame) -> pd.DataFrame:
        """
        Enhanced imaging prioritization including treatment changes
        """
        if imaging_df.empty:
            return imaging_df

        # Ensure imaging dates are parsed
        if 'imaging_date' not in imaging_df.columns:
            if 'di_study_date_time' in imaging_df.columns:
                imaging_df['imaging_date'] = pd.to_datetime(imaging_df['di_study_date_time'], utc=True, errors='coerce')
            elif 'study_date' in imaging_df.columns:
                imaging_df['imaging_date'] = pd.to_datetime(imaging_df['study_date'], utc=True, errors='coerce')
        else:
            imaging_df['imaging_date'] = pd.to_datetime(imaging_df['imaging_date'], utc=True, errors='coerce')

        # Initialize priority columns
        imaging_df['clinical_context'] = 'surveillance'
        imaging_df['priority_score'] = 0
        imaging_df['priority_reasons'] = ''

        window = self.config['imaging_windows']

        # 1. Surgery-related imaging (highest priority)
        for idx, surgery in tumor_surgeries.iterrows():
            if pd.isna(surgery.get('proc_date')):
                continue

            surgery_date = surgery['proc_date']

            # Pre-operative
            pre_op_mask = (
                (imaging_df['imaging_date'] >= surgery_date - timedelta(days=window['pre_surgery_days'])) &
                (imaging_df['imaging_date'] < surgery_date)
            )
            imaging_df.loc[pre_op_mask, 'clinical_context'] = 'pre_operative'
            imaging_df.loc[pre_op_mask, 'priority_score'] += 10
            imaging_df.loc[pre_op_mask, 'priority_reasons'] += 'pre-operative planning;'

            # Post-operative
            post_op_mask = (
                (imaging_df['imaging_date'] > surgery_date) &
                (imaging_df['imaging_date'] <= surgery_date + timedelta(days=window['post_surgery_days']))
            )
            imaging_df.loc[post_op_mask, 'clinical_context'] = 'post_operative'
            imaging_df.loc[post_op_mask, 'priority_score'] += 10
            imaging_df.loc[post_op_mask, 'priority_reasons'] += 'extent of resection assessment;'

        # 2. Chemotherapy change imaging (high priority)
        for change in chemo_changes:
            if pd.isna(change['date']):
                continue

            change_date = change['date']
            window_days = window['chemo_change_window_days']

            # Imaging within window of chemotherapy change
            chemo_change_mask = (
                (imaging_df['imaging_date'] >= change_date - timedelta(days=window_days)) &
                (imaging_df['imaging_date'] <= change_date + timedelta(days=window_days))
            )

            if chemo_change_mask.any():
                imaging_df.loc[chemo_change_mask, 'priority_score'] += 8

                if change['change_type'] == 'new_drug_started':
                    imaging_df.loc[chemo_change_mask, 'clinical_context'] = 'treatment_baseline'
                    imaging_df.loc[chemo_change_mask, 'priority_reasons'] += f'baseline for {change["drug"]};'
                elif change['change_type'] == 'drug_discontinued':
                    imaging_df.loc[chemo_change_mask, 'clinical_context'] = 'treatment_response'
                    imaging_df.loc[chemo_change_mask, 'priority_reasons'] += f'response assessment for {change["drug"]};'
                elif change['change_type'] == 'regimen_change':
                    imaging_df.loc[chemo_change_mask, 'clinical_context'] = 'progression_assessment'
                    imaging_df.loc[chemo_change_mask, 'priority_score'] += 2  # Extra priority
                    imaging_df.loc[chemo_change_mask, 'priority_reasons'] += 'possible progression/regimen change;'

        # 3. Radiation planning imaging
        if not radiation_courses.empty:
            for idx, course in radiation_courses.iterrows():
                if pd.notna(course.get('start_date')):
                    rad_start = course['start_date']

                    # Planning imaging (2 weeks before radiation)
                    planning_mask = (
                        (imaging_df['imaging_date'] >= rad_start - timedelta(days=window['radiation_planning_window_days'])) &
                        (imaging_df['imaging_date'] < rad_start)
                    )
                    imaging_df.loc[planning_mask, 'clinical_context'] = 'radiation_planning'
                    imaging_df.loc[planning_mask, 'priority_score'] += 7
                    imaging_df.loc[planning_mask, 'priority_reasons'] += 'radiation treatment planning;'

        # 4. MRI studies get bonus priority during surveillance
        if 'imaging_modality' in imaging_df.columns:
            mri_mask = imaging_df['imaging_modality'].str.upper().eq('MR')
            surveillance_mask = imaging_df['clinical_context'] == 'surveillance'
            imaging_df.loc[mri_mask & surveillance_mask, 'priority_score'] += 3
            imaging_df.loc[mri_mask & surveillance_mask, 'priority_reasons'] += 'MRI surveillance;'

        # Assign final priority levels based on scores
        imaging_df['abstraction_priority'] = 'low'
        imaging_df.loc[imaging_df['priority_score'] >= 10, 'abstraction_priority'] = 'critical'
        imaging_df.loc[(imaging_df['priority_score'] >= 7) & (imaging_df['priority_score'] < 10), 'abstraction_priority'] = 'high'
        imaging_df.loc[(imaging_df['priority_score'] >= 3) & (imaging_df['priority_score'] < 7), 'abstraction_priority'] = 'medium'

        # Log summary
        priority_summary = imaging_df['abstraction_priority'].value_counts()
        logger.info("Enhanced imaging prioritization:")
        for priority, count in priority_summary.items():
            logger.info(f"  {priority}: {count}")

        context_summary = imaging_df['clinical_context'].value_counts()
        logger.info("Clinical contexts identified:")
        for context, count in context_summary.items():
            logger.info(f"  {context}: {count}")

        return imaging_df

    def extract_survival_endpoints(self, patient_id: str) -> Dict:
        """
        Extract last contact dates, vital status, and demographics for survival calculations

        Returns:
        - date_of_birth: Patient's birth date
        - age_at_diagnosis: Age when first diagnosed
        - last_clinical_contact: Last appointment/visit
        - last_imaging: Last imaging study
        - last_treatment: Last treatment administration
        - last_lab: Last laboratory result
        - vital_status: If available
        """
        patient_path = self.staging_path / f"patient_{patient_id}"
        endpoints = {
            'patient_id': patient_id,
            'date_of_birth': None,
            'age_at_diagnosis': None,
            'diagnosis_date': None,
            'last_clinical_contact': None,
            'last_imaging': None,
            'last_treatment': None,
            'last_lab': None,
            'vital_status': 'unknown',
            'death_date': None
        }

        # Check for patient config file for birth date
        config_file = self.staging_path.parent / "patient_config.json"
        if config_file.exists():
            import json
            with open(config_file, 'r') as f:
                config = json.load(f)
                if 'birth_date' in config:
                    endpoints['date_of_birth'] = config['birth_date']

        # Check encounters/appointments
        encounters_file = patient_path / "encounters.csv"
        if encounters_file.exists():
            encounters = pd.read_csv(encounters_file)
            date_cols = ['encounter_date', 'period_start', 'period_end']
            for col in date_cols:
                if col in encounters.columns:
                    dates = pd.to_datetime(encounters[col], utc=True, errors='coerce')
                    if dates.notna().any():
                        max_date = dates.max()
                        if endpoints['last_clinical_contact'] is None or max_date > endpoints['last_clinical_contact']:
                            endpoints['last_clinical_contact'] = max_date

        # Check imaging
        imaging_file = patient_path / "imaging.csv"
        if imaging_file.exists():
            imaging = pd.read_csv(imaging_file)
            if 'imaging_date' in imaging.columns:
                dates = pd.to_datetime(imaging['imaging_date'], utc=True, errors='coerce')
                if dates.notna().any():
                    endpoints['last_imaging'] = dates.max()

        # Check medications (last treatment)
        meds_file = patient_path / "medications.csv"
        if meds_file.exists():
            meds = pd.read_csv(meds_file)
            date_cols = ['medication_start_date', 'medication_end_date', 'cp_period_end']
            for col in date_cols:
                if col in meds.columns:
                    dates = pd.to_datetime(meds[col], utc=True, errors='coerce')
                    if dates.notna().any():
                        max_date = dates.max()
                        if endpoints['last_treatment'] is None or max_date > endpoints['last_treatment']:
                            endpoints['last_treatment'] = max_date

        # Check observations/labs
        obs_file = patient_path / "observations.csv"
        if obs_file.exists():
            obs = pd.read_csv(obs_file)
            if 'observation_date' in obs.columns:
                dates = pd.to_datetime(obs['observation_date'], utc=True, errors='coerce')
                if dates.notna().any():
                    endpoints['last_lab'] = dates.max()

        # Check vital status
        patient_file = patient_path / "patient_demographics.csv"
        if patient_file.exists():
            demographics = pd.read_csv(patient_file)
            if not demographics.empty:
                if 'deceased_boolean' in demographics.columns:
                    if demographics['deceased_boolean'].iloc[0]:
                        endpoints['vital_status'] = 'deceased'
                        if 'deceased_date_time' in demographics.columns:
                            endpoints['death_date'] = pd.to_datetime(
                                demographics['deceased_date_time'].iloc[0],
                                utc=True,
                                errors='coerce'
                            )
                else:
                    endpoints['vital_status'] = 'alive'

        # Get diagnosis date from diagnoses file
        diagnoses_file = patient_path / "diagnoses.csv"
        if diagnoses_file.exists():
            diagnoses = pd.read_csv(diagnoses_file)
            # Look for brain tumor diagnoses - use onset_date_time or recorded_date
            date_col = None
            if 'onset_date_time' in diagnoses.columns:
                date_col = 'onset_date_time'
            elif 'recorded_date' in diagnoses.columns:
                date_col = 'recorded_date'

            if date_col:
                dates = pd.to_datetime(diagnoses[date_col], utc=True, errors='coerce')
                if dates.notna().any():
                    endpoints['diagnosis_date'] = dates.min()  # Earliest diagnosis

        # Calculate age at diagnosis if we have both dates
        if endpoints['date_of_birth'] and endpoints['diagnosis_date']:
            birth_date = pd.to_datetime(endpoints['date_of_birth'], utc=True)
            diagnosis_date = pd.to_datetime(endpoints['diagnosis_date'], utc=True) if isinstance(endpoints['diagnosis_date'], str) else endpoints['diagnosis_date']
            if pd.notna(birth_date) and pd.notna(diagnosis_date):
                age_days = (diagnosis_date - birth_date).days
                endpoints['age_at_diagnosis'] = round(age_days / 365.25, 1)  # Age in years

        # Determine overall last contact
        contact_dates = [
            endpoints['last_clinical_contact'],
            endpoints['last_imaging'],
            endpoints['last_treatment'],
            endpoints['last_lab']
        ]
        valid_dates = [d for d in contact_dates if pd.notna(d)]
        if valid_dates:
            endpoints['last_known_alive'] = max(valid_dates)

            # Calculate current age or age at death
            if endpoints['date_of_birth']:
                birth_date = pd.to_datetime(endpoints['date_of_birth'], utc=True)
                if endpoints['death_date']:
                    end_date = pd.to_datetime(endpoints['death_date'], utc=True) if isinstance(endpoints['death_date'], str) else endpoints['death_date']
                else:
                    end_date = endpoints['last_known_alive'] if isinstance(endpoints['last_known_alive'], pd.Timestamp) else pd.to_datetime(endpoints['last_known_alive'], utc=True)

                if pd.notna(birth_date) and pd.notna(end_date):
                    age_days = (end_date - birth_date).days
                    endpoints['current_age_or_age_at_death'] = round(age_days / 365.25, 1)

        # Convert timestamps to strings for serialization
        for key in endpoints:
            if isinstance(endpoints[key], pd.Timestamp):
                endpoints[key] = endpoints[key].isoformat()

        logger.info(f"Extracted survival endpoints for {patient_id}")
        if endpoints.get('last_known_alive'):
            logger.info(f"  Last known alive: {endpoints['last_known_alive']}")

        return endpoints

    def create_standardized_config(self, output_path: Path) -> Path:
        """
        Create standardized configuration file for cohort processing
        """
        config = {
            'framework_version': '2.0',
            'created_date': datetime.now().isoformat(),
            'modules': {
                'tumor_surgery_classification': {
                    'enabled': True,
                    'indicators': {
                        'resection_terms': ['resection', 'excision', 'removal', 'debulking', 'craniotomy'],
                        'biopsy_terms': ['biopsy', 'stereotactic biopsy', 'needle biopsy'],
                        'exclude_terms': ['shunt', 'ventriculoperitoneal', 'wound', 'infection']
                    }
                },
                'chemotherapy_identification': {
                    'enabled': True,
                    'strategies': ['rxnorm', 'product_mapping', 'name_pattern', 'care_plan', 'reason_codes'],
                    'reference_files': {
                        'drugs': 'drugs.csv',
                        'drug_alias': 'drug_alias.csv',
                        'rxnorm_map': 'rxnorm_code_map.csv'
                    }
                },
                'radiation_analysis': {
                    'enabled': True,
                    'tables': [
                        'radiation_care_plan_hierarchy',
                        'radiation_treatment_courses',
                        'radiation_treatment_appointments'
                    ]
                },
                'imaging_prioritization': {
                    'enabled': True,
                    'windows': self.config['imaging_windows'],
                    'priority_levels': self.config['priority_levels']
                },
                'survival_tracking': {
                    'enabled': True,
                    'endpoints': self.config['survival_endpoints']
                }
            },
            'output_formats': ['csv', 'json'],
            'cohort_processing': {
                'batch_size': 10,
                'parallel_processing': False,
                'checkpoint_frequency': 5
            }
        }

        config_file = output_path / 'cohort_processing_config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Standardized configuration saved to {config_file}")
        return config_file


def process_patient_enhanced(patient_id: str, staging_path: Path, output_path: Path) -> Dict:
    """
    Process a patient with enhanced prioritization
    """
    from tumor_surgery_classifier import TumorSurgeryClassifier
    from radiation_therapy_analyzer import RadiationTherapyAnalyzer
    from comprehensive_chemotherapy_identifier import ComprehensiveChemotherapyIdentifier

    enhancer = EnhancedClinicalPrioritization(staging_path)

    # Get surgery data
    surgery_classifier = TumorSurgeryClassifier(staging_path)
    surgery_results = surgery_classifier.process_patient(patient_id)

    # Get chemotherapy data
    patient_path = staging_path / f"patient_{patient_id}"
    meds_file = patient_path / "medications.csv"
    chemo_identifier = ComprehensiveChemotherapyIdentifier()

    chemo_df = pd.DataFrame()
    chemo_changes = []

    if meds_file.exists():
        meds_df = pd.read_csv(meds_file)
        chemo_df, _ = chemo_identifier.identify_chemotherapy(meds_df)
        periods_df = chemo_identifier.extract_treatment_periods(chemo_df)
        chemo_changes = enhancer.identify_chemotherapy_changes(periods_df)

    # Get radiation data
    radiation_analyzer = RadiationTherapyAnalyzer(staging_path)
    radiation_results = radiation_analyzer.process_patient(patient_id)

    # Enhanced imaging prioritization
    imaging_enhanced = pd.DataFrame()
    if 'imaging_with_context' in surgery_results and not surgery_results['imaging_with_context'].empty:
        imaging_enhanced = enhancer.prioritize_imaging_enhanced(
            surgery_results['imaging_with_context'],
            surgery_results.get('tumor_surgeries', pd.DataFrame()),
            chemo_changes,
            radiation_results.get('courses', pd.DataFrame())
        )

    # Extract survival endpoints
    survival_endpoints = enhancer.extract_survival_endpoints(patient_id)

    # Save results
    output_path = Path(output_path)
    output_path.mkdir(exist_ok=True)

    # Save enhanced imaging
    if not imaging_enhanced.empty:
        imaging_enhanced.to_csv(output_path / f"imaging_enhanced_priority_{patient_id}.csv", index=False)

        # Create priority summary
        critical_imaging = imaging_enhanced[imaging_enhanced['abstraction_priority'] == 'critical']
        high_imaging = imaging_enhanced[imaging_enhanced['abstraction_priority'] == 'high']

        priority_summary = {
            'total_imaging': len(imaging_enhanced),
            'critical_priority': len(critical_imaging),
            'high_priority': len(high_imaging),
            'chemotherapy_change_imaging': len(imaging_enhanced[imaging_enhanced['clinical_context'].str.contains('treatment', na=False)]),
            'contexts': imaging_enhanced['clinical_context'].value_counts().to_dict()
        }
    else:
        priority_summary = {}

    # Save survival endpoints
    with open(output_path / f"survival_endpoints_{patient_id}.json", 'w') as f:
        json.dump(survival_endpoints, f, indent=2)

    # Create standardized config
    config_file = enhancer.create_standardized_config(output_path)

    return {
        'patient_id': patient_id,
        'imaging_priority_summary': priority_summary,
        'chemotherapy_changes': len(chemo_changes),
        'survival_endpoints': survival_endpoints,
        'config_file': str(config_file)
    }


if __name__ == "__main__":
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    results = process_patient_enhanced(patient_id, staging_path, output_path)

    print("\n" + "="*80)
    print("ENHANCED CLINICAL PRIORITIZATION RESULTS")
    print("="*80)

    print(f"\nPatient: {patient_id}")

    if results['imaging_priority_summary']:
        summary = results['imaging_priority_summary']
        print(f"\nImaging Prioritization:")
        print(f"  Total Studies: {summary.get('total_imaging', 0)}")
        print(f"  Critical Priority: {summary.get('critical_priority', 0)}")
        print(f"  High Priority: {summary.get('high_priority', 0)}")
        print(f"  Treatment Change Imaging: {summary.get('chemotherapy_change_imaging', 0)}")

        if 'contexts' in summary:
            print("\n  Clinical Contexts:")
            for context, count in summary['contexts'].items():
                print(f"    {context}: {count}")

    print(f"\nChemotherapy Changes Identified: {results['chemotherapy_changes']}")

    endpoints = results['survival_endpoints']
    print(f"\nSurvival Endpoints:")
    print(f"  Vital Status: {endpoints.get('vital_status', 'unknown')}")
    print(f"  Last Known Alive: {endpoints.get('last_known_alive', 'unknown')}")
    print(f"  Last Clinical Contact: {endpoints.get('last_clinical_contact', 'unknown')}")
    print(f"  Last Imaging: {endpoints.get('last_imaging', 'unknown')}")
    print(f"  Last Treatment: {endpoints.get('last_treatment', 'unknown')}")

    print(f"\nStandardized Config: {results['config_file']}")