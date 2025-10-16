"""
PHASE 1: Enhanced Structured Data Harvesting with Event Waypoints
==================================================================
Creates concrete staging file waypoints anchored by dates that are present
across all staging files to enable event-based extraction.

Key Features:
1. Identifies tumor surgeries and classifies event types (5=Initial, 7=Recurrence, 8=Progressive)
2. Creates date-anchored waypoints for temporal alignment across all staging files
3. Links imaging, pathology, and service requests to surgical events
4. Establishes post-operative validation windows (24-72h for imaging)
5. Generates structured features for downstream phases

Author: RADIANT PCA Analytics Team
Enhanced: January 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from pathlib import Path
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedStructuredDataHarvester:
    """
    Phase 1: Enhanced extraction with event waypoints and date anchors
    """

    # Tumor surgery keywords from our validated approach
    TUMOR_SURGERY_KEYWORDS = [
        'craniotomy', 'craniectomy', 'resection', 'excision',
        'debulking', 'tumor', 'neoplasm', 'mass', 'lesion',
        'biopsy', 'stereotactic'
    ]

    # Non-tumor procedures to exclude
    NON_TUMOR_PROCEDURES = [
        'shunt', 'ventriculoperitoneal', 'vp shunt',
        'external ventricular drain', 'evd',
        'wound', 'infection', 'hematoma evacuation'
    ]

    def __init__(self, staging_path: str):
        self.staging_path = Path(staging_path)
        self.extracted_features = {}
        self.data_sources = {}
        self.event_waypoints = []
        self.surgical_events = []

    def harvest_for_patient(self, patient_id: str, birth_date: str) -> Dict[str, Any]:
        """
        Main entry point - creates waypoints and extracts structured features

        Returns:
            Dictionary containing:
            - structured_features: All extracted features
            - event_waypoints: Date-anchored events for temporal alignment
            - surgical_events: Classified tumor surgeries
            - diagnostic_cascade: Service requests linked to events
        """
        logger.info(f"PHASE 1: Enhanced structured harvesting for patient {patient_id}")

        self.patient_id = patient_id
        self.birth_date = pd.to_datetime(birth_date).tz_localize('UTC')
        self.patient_path = self.staging_path / f"patient_{patient_id}"

        # Load all staging files
        self._load_all_staging_files()

        # CRITICAL STEP 1: Identify and classify tumor surgeries
        surgical_events = self._identify_tumor_surgeries()
        self.surgical_events = surgical_events

        # CRITICAL STEP 2: Create event waypoints anchored by dates
        waypoints = self._create_event_waypoints(surgical_events)
        self.event_waypoints = waypoints

        # CRITICAL STEP 3: Link imaging for post-op validation (24-72h window)
        imaging_links = self._link_imaging_to_surgeries(surgical_events)

        # CRITICAL STEP 4: Link service requests for diagnostic cascade
        service_cascade = self._map_service_request_cascade(surgical_events)

        # CRITICAL STEP 5: Extract pathology from observations and molecular tests
        pathology_data = self._extract_pathology_data()

        # Extract standard structured features
        features = {}
        features.update(self._extract_surgical_procedures(surgical_events))
        features.update(self._extract_diagnoses())
        features.update(self._extract_medications())
        features.update(self._extract_radiation())
        features.update(self._extract_imaging_progression())
        features.update(self._extract_measurements())

        # Add enhanced event-based features
        features['surgical_events'] = surgical_events
        features['imaging_validation'] = imaging_links
        features['service_cascade'] = service_cascade
        features['pathology_data'] = pathology_data

        # Calculate derived features
        derived = self._calculate_derived_features(features)
        features.update(derived)

        logger.info(f"PHASE 1 Complete: {len(features)} features, {len(waypoints)} waypoints")

        # Return comprehensive result
        return {
            'structured_features': features,
            'event_waypoints': waypoints,
            'surgical_events': surgical_events,
            'diagnostic_cascade': service_cascade,
            'patient_id': patient_id,
            'birth_date': birth_date
        }

    def _load_all_staging_files(self):
        """Load all staging files with proper date parsing"""
        logger.info("Loading all staging files...")

        # CRITICAL: Check for extent_of_resection staging files first (validated waypoints)
        extent_path = self.staging_path / 'brim_workflows_individual_fields' / 'extent_of_resection' / 'staging_files' / self.patient_id

        # Check for surgery events staging file (has validated event classifications)
        surgery_events_file = extent_path / f'surgery_events_staging_{self.patient_id}.csv'
        if surgery_events_file.exists():
            logger.info(f"  Found extent_of_resection surgery events staging file")
            surgery_df = pd.read_csv(surgery_events_file)
            surgery_df['surgery_date'] = pd.to_datetime(surgery_df['surgery_date'], errors='coerce', utc=True)
            surgery_df['surgery_datetime'] = pd.to_datetime(surgery_df['surgery_datetime'], errors='coerce', utc=True)
            self.data_sources['surgery_events_staging'] = surgery_df
            logger.info(f"  Loaded surgery_events_staging: {len(surgery_df)} events from extent_of_resection")

        # Check for patient event-based data dictionary (complete waypoints)
        event_dict_file = extent_path / f'patient_event_based_data_dictionary.csv'
        if event_dict_file.exists():
            event_dict_df = pd.read_csv(event_dict_file)
            event_dict_df['Surgery_Date'] = pd.to_datetime(event_dict_df['Surgery_Date'], errors='coerce', utc=True)
            self.data_sources['event_dictionary'] = event_dict_df
            logger.info(f"  Loaded event_dictionary: {len(event_dict_df)} waypoints from extent_of_resection")

        # Core staging files with their date columns
        staging_config = {
            'procedures': ['proc_performed_date_time', 'procedure_date'],
            'diagnoses': ['onset_date_time', 'recorded_date'],
            'medications': ['medication_start_date', 'med_date_given_start'],
            'imaging': ['imaging_date', 'study_date'],
            'encounters': ['encounter_date', 'period_start'],
            'appointments': ['start_date', 'appointment_date'],
            'measurements': ['measurement_date', 'effective_date_time'],
            'binary_files': ['dr_date', 'document_date'],
            # Radiation files
            'radiation_treatment_courses': ['start_date', 'end_date'],
            'radiation_treatment_appointments': ['appointment_date'],
            'radiation_care_plan_hierarchy': ['care_plan_period_start'],
            'radiation_service_request_notes': ['note_time'],
            'radiation_data_summary': ['first_radiation_date'],
            # Molecular and problem list
            'molecular_tests_metadata': ['result_datetime'],
            'problem_list_diagnoses': ['onset_date_time', 'recorded_date']
        }

        # Load staging files from config_driven_versions location
        # Handle potential patient ID truncation (e.g., removing 'w3' suffix)
        truncated_id = self.patient_id[:-2] if self.patient_id.endswith('w3') else self.patient_id

        # Primary path: config_driven_versions location (where actual staging files are)
        config_path = self.staging_path / 'athena_extraction_validation' / 'scripts' / 'config_driven_versions' / 'staging_files' / f'patient_{truncated_id}'

        # Fallback path: original patient path
        original_path = self.patient_path

        for source, date_cols in staging_config.items():
            # Try config_driven_versions location first
            file_path = config_path / f"{source}.csv"
            source_location = "config_driven_versions"

            # If not found, try original patient path
            if not file_path.exists():
                file_path = original_path / f"{source}.csv"
                source_location = "original"

            # If still not found with full ID, try without 'w3' suffix
            if not file_path.exists() and self.patient_id != truncated_id:
                file_path = self.staging_path / 'athena_extraction_validation' / 'scripts' / 'config_driven_versions' / 'staging_files' / f'patient_{self.patient_id}' / f"{source}.csv"
                if file_path.exists():
                    source_location = "config_driven_versions_full_id"

            if file_path.exists():
                df = pd.read_csv(file_path)
                # Parse all date columns
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                self.data_sources[source] = df
                logger.info(f"  Loaded {source}: {len(df)} records from {source_location}")
            else:
                self.data_sources[source] = pd.DataFrame()
                logger.debug(f"  {source} not found in any location")

    def _identify_tumor_surgeries(self) -> List[Dict]:
        """
        Identify tumor-specific surgeries and classify event types

        Event Type Classification:
        - 5: Initial CNS Tumor (first surgery)
        - 7: Recurrence (after GTR/NTR)
        - 8: Progressive (after STR/partial/biopsy)
        """
        logger.info("Identifying tumor surgeries...")

        # PRIORITY 1: Use validated surgery_events_staging if available
        if 'surgery_events_staging' in self.data_sources and not self.data_sources['surgery_events_staging'].empty:
            logger.info("  Using validated surgery events from extent_of_resection staging")
            surgery_df = self.data_sources['surgery_events_staging']

            surgeries = []
            for idx, row in surgery_df.iterrows():
                surgery = {
                    'procedure_fhir_id': row.get('procedure_fhir_id', ''),
                    'surgery_date': row['surgery_date'],
                    'age_at_surgery_days': int(row.get('age_at_surgery_days', 0)),
                    'code_text': row.get('code_text', ''),
                    'event_type': row.get('event_type', 5),  # Default to Initial
                    'event_type_label': row.get('event_label', 'Initial CNS Tumor'),
                    'event_number': row.get('event_number', idx + 1),
                    'op_note_linked': row.get('linkage_status') == 'LINKED',
                    'op_note_id': row.get('op_note_id', ''),
                    's3_key': row.get('op_note_s3_key', '')
                }
                surgeries.append(surgery)

            logger.info(f"  Found {len(surgeries)} validated surgical events")
            return surgeries

        # FALLBACK: Process from procedures table if no staging file
        if 'procedures' not in self.data_sources or self.data_sources['procedures'].empty:
            return []

        procs = self.data_sources['procedures'].copy()

        # Filter for tumor surgeries
        tumor_surgeries = []

        for idx, proc in procs.iterrows():
            proc_text = str(proc.get('proc_code_text', '')).lower()

            # Skip non-tumor procedures
            if any(exclude in proc_text for exclude in self.NON_TUMOR_PROCEDURES):
                continue

            # Identify tumor surgeries
            if any(keyword in proc_text for keyword in self.TUMOR_SURGERY_KEYWORDS):
                # Get surgery date
                surgery_date = proc.get('proc_performed_date_time')
                if pd.isna(surgery_date):
                    surgery_date = proc.get('procedure_date')
                if pd.isna(surgery_date):
                    continue

                # Calculate age at surgery
                age_days = (surgery_date - self.birth_date).days

                tumor_surgeries.append({
                    'procedure_fhir_id': proc.get('procedure_fhir_id', ''),
                    'surgery_date': surgery_date,
                    'age_at_surgery_days': age_days,
                    'procedure_text': proc.get('proc_code_text', ''),
                    'encounter_id': proc.get('encounter_reference', ''),
                    'performer': proc.get('performer_actor_display', '')
                })

        # Sort by date
        tumor_surgeries.sort(key=lambda x: x['surgery_date'])

        # Classify event types
        for i, surgery in enumerate(tumor_surgeries):
            if i == 0:
                # First surgery is Initial CNS Tumor
                surgery['event_type'] = 5
                surgery['event_type_label'] = 'Initial CNS Tumor'
                surgery['event_number'] = 1
            else:
                # For subsequent surgeries, we need extent from previous
                # Conservative default: Progressive (would check extent in production)
                surgery['event_type'] = 8
                surgery['event_type_label'] = 'Progressive'
                surgery['event_number'] = i + 1

        logger.info(f"  Identified {len(tumor_surgeries)} tumor surgeries")
        return tumor_surgeries

    def _create_event_waypoints(self, surgical_events: List[Dict]) -> List[Dict]:
        """
        Create date-anchored waypoints that exist across staging files

        Waypoints include:
        - Surgical events with classification
        - Pre-operative window (30 days before)
        - Post-operative validation window (24-72 hours after)
        - Treatment planning window (3-30 days after)
        """
        logger.info("Creating event waypoints...")

        waypoints = []

        for surgery in surgical_events:
            surgery_date = surgery['surgery_date']

            # Create waypoint for surgery
            waypoint = {
                'waypoint_type': 'surgery',
                'event_number': surgery['event_number'],
                'event_date': surgery_date,
                'event_type': surgery['event_type'],
                'event_label': surgery['event_type_label'],
                'age_at_event_days': surgery['age_at_surgery_days'],
                # Define critical windows
                'preop_window_start': surgery_date - timedelta(days=30),
                'preop_window_end': surgery_date,
                'postop_validation_start': surgery_date + timedelta(hours=24),
                'postop_validation_end': surgery_date + timedelta(hours=72),
                'treatment_planning_start': surgery_date + timedelta(days=3),
                'treatment_planning_end': surgery_date + timedelta(days=30),
                # Link to source data
                'procedure_id': surgery.get('procedure_fhir_id', ''),
                'procedure_text': surgery.get('code_text', '')
            }

            waypoints.append(waypoint)

        logger.info(f"  Created {len(waypoints)} waypoints")
        return waypoints

    def _link_imaging_to_surgeries(self, surgical_events: List[Dict]) -> Dict:
        """
        Link imaging studies to surgical events, especially post-op validation

        CRITICAL: Post-op MRI within 24-72 hours is GOLD STANDARD for extent
        """
        logger.info("Linking imaging to surgical events...")

        if 'imaging' not in self.data_sources or self.data_sources['imaging'].empty:
            return {}

        imaging = self.data_sources['imaging'].copy()
        imaging_links = {}

        for surgery in surgical_events:
            surgery_date = surgery['surgery_date']
            event_num = surgery['event_number']

            # Find pre-op imaging (30 days before)
            preop_start = surgery_date - timedelta(days=30)
            preop_imaging = imaging[
                (imaging['imaging_date'] >= preop_start) &
                (imaging['imaging_date'] < surgery_date)
            ]

            # Find CRITICAL post-op imaging (24-72 hours)
            postop_start = surgery_date + timedelta(hours=24)
            postop_end = surgery_date + timedelta(hours=72)
            postop_validation = imaging[
                (imaging['imaging_date'] >= postop_start) &
                (imaging['imaging_date'] <= postop_end)
            ]

            # Find extended post-op (up to 30 days)
            extended_postop = imaging[
                (imaging['imaging_date'] > surgery_date) &
                (imaging['imaging_date'] <= surgery_date + timedelta(days=30))
            ]

            imaging_links[f'event_{event_num}'] = {
                'surgery_date': surgery_date.isoformat(),
                'preop_imaging_count': len(preop_imaging),
                'postop_validation_count': len(postop_validation),
                'has_gold_standard_validation': len(postop_validation) > 0,
                'extended_postop_count': len(extended_postop),
                'postop_validation_studies': postop_validation.to_dict('records') if len(postop_validation) > 0 else []
            }

            if len(postop_validation) > 0:
                logger.info(f"  ✓ Event {event_num}: Found {len(postop_validation)} post-op validation imaging")
            else:
                logger.warning(f"  ⚠ Event {event_num}: NO post-op validation imaging (24-72h)")

        return imaging_links

    def _map_service_request_cascade(self, surgical_events: List[Dict]) -> Dict:
        """
        Map service requests to surgical events for diagnostic cascade

        Service requests contain:
        - Pre-operative diagnostic workup
        - Post-operative validation orders
        - Pathology requests
        - Molecular testing orders
        """
        logger.info("Mapping service request cascade...")

        # Check for service request files
        service_files = [
            'radiation_service_request_notes',
            'radiation_service_request_rt_history'
        ]

        cascade = {}

        for file_name in service_files:
            if file_name in self.data_sources and not self.data_sources[file_name].empty:
                df = self.data_sources[file_name]

                for surgery in surgical_events:
                    surgery_date = surgery['surgery_date']
                    event_num = surgery['event_number']

                    # Pre-op window (30 days)
                    preop_requests = df[
                        (df.get('note_time', df.columns[0]) >= surgery_date - timedelta(days=30)) &
                        (df.get('note_time', df.columns[0]) < surgery_date)
                    ] if 'note_time' in df.columns else pd.DataFrame()

                    # Post-op window (30 days)
                    postop_requests = df[
                        (df.get('note_time', df.columns[0]) > surgery_date) &
                        (df.get('note_time', df.columns[0]) <= surgery_date + timedelta(days=30))
                    ] if 'note_time' in df.columns else pd.DataFrame()

                    cascade[f'event_{event_num}'] = {
                        'preop_requests': len(preop_requests),
                        'postop_requests': len(postop_requests)
                    }

        return cascade

    def _extract_pathology_data(self) -> Dict:
        """
        Extract pathology from molecular tests and observations

        Sources:
        - molecular_tests_metadata.csv
        - problem_list_diagnoses.csv
        - Observations with pathology LOINC codes
        """
        logger.info("Extracting pathology data...")

        pathology = {}

        # Molecular tests
        if 'molecular_tests_metadata' in self.data_sources and not self.data_sources['molecular_tests_metadata'].empty:
            mol_tests = self.data_sources['molecular_tests_metadata']
            pathology['molecular_tests_count'] = len(mol_tests)
            pathology['molecular_test_types'] = mol_tests.get('lab_test_name', pd.Series()).unique().tolist()

            # Link to surgeries by date
            for surgery in self.surgical_events:
                surgery_date = surgery['surgery_date']
                # Find molecular tests within 30 days of surgery
                related_tests = mol_tests[
                    (mol_tests.get('result_datetime', pd.Series()) >= surgery_date - timedelta(days=30)) &
                    (mol_tests.get('result_datetime', pd.Series()) <= surgery_date + timedelta(days=30))
                ] if 'result_datetime' in mol_tests.columns else pd.DataFrame()

                if not related_tests.empty:
                    pathology[f'event_{surgery["event_number"]}_molecular'] = len(related_tests)

        # Problem list diagnoses
        if 'problem_list_diagnoses' in self.data_sources:
            prob_list = self.data_sources['problem_list_diagnoses']

            # Brain tumor codes
            brain_tumor_codes = ['C71', 'D43', 'D33']
            brain_tumors = prob_list[
                prob_list.get('icd10_code', pd.Series()).str.startswith(tuple(brain_tumor_codes), na=False)
            ] if 'icd10_code' in prob_list.columns else pd.DataFrame()

            pathology['brain_tumor_diagnoses'] = len(brain_tumors)
            if not brain_tumors.empty and 'diagnosis_name' in brain_tumors.columns:
                pathology['tumor_types'] = brain_tumors['diagnosis_name'].unique().tolist()

        return pathology

    def _extract_surgical_procedures(self, surgical_events: List[Dict]) -> Dict:
        """Extract surgical procedure features from classified events"""
        features = {}

        if surgical_events:
            features['has_surgery'] = 'Yes'
            features['total_surgeries'] = len(surgical_events)
            features['tumor_surgeries'] = len(surgical_events)

            # First surgery
            first = surgical_events[0]
            features['first_surgery_date'] = first['surgery_date'].isoformat()
            features['age_at_first_surgery_days'] = first['age_at_surgery_days']
            features['first_surgery_event_type'] = first['event_type']

            # Multiple surgeries
            if len(surgical_events) > 1:
                features['has_multiple_surgeries'] = 'Yes'
                last = surgical_events[-1]
                features['last_surgery_date'] = last['surgery_date'].isoformat()
                features['days_between_first_last_surgery'] = (
                    last['surgery_date'] - first['surgery_date']
                ).days
            else:
                features['has_multiple_surgeries'] = 'No'

            # Event type distribution
            event_types = [s['event_type'] for s in surgical_events]
            features['initial_surgeries'] = event_types.count(5)
            features['recurrence_surgeries'] = event_types.count(7)
            features['progressive_surgeries'] = event_types.count(8)

        else:
            features['has_surgery'] = 'No'
            features['total_surgeries'] = 0
            features['tumor_surgeries'] = 0

        return features

    def _extract_diagnoses(self) -> Dict:
        """Extract diagnosis features"""
        features = {}

        if 'diagnoses' not in self.data_sources or self.data_sources['diagnoses'].empty:
            return features

        diag = self.data_sources['diagnoses']

        # Brain tumor diagnoses
        brain_tumor_codes = ['C71', 'D43', 'D33']

        if 'icd10_code' in diag.columns:
            brain_tumors = diag[
                diag['icd10_code'].str.startswith(tuple(brain_tumor_codes), na=False)
            ]

            if not brain_tumors.empty:
                features['has_brain_tumor_diagnosis'] = 'Yes'
                features['brain_tumor_count'] = len(brain_tumors)

                # First diagnosis
                if 'recorded_date' in brain_tumors.columns:
                    first_diag = brain_tumors.sort_values('recorded_date').iloc[0]
                    features['first_diagnosis_date'] = first_diag['recorded_date'].isoformat()
                    features['age_at_diagnosis_days'] = (
                        first_diag['recorded_date'] - self.birth_date
                    ).days

                # Diagnosis names
                if 'diagnosis_name' in brain_tumors.columns:
                    features['brain_tumor_diagnoses'] = brain_tumors['diagnosis_name'].unique().tolist()
            else:
                features['has_brain_tumor_diagnosis'] = 'No'

        # Metastasis
        metastasis_codes = ['C79', 'C78']
        if 'icd10_code' in diag.columns:
            metastases = diag[
                diag['icd10_code'].str.startswith(tuple(metastasis_codes), na=False)
            ]
            features['has_metastasis_diagnosis'] = 'Yes' if not metastases.empty else 'No'

        return features

    def _extract_medications(self) -> Dict:
        """Extract medication features focusing on chemotherapy"""
        features = {}

        if 'medications' not in self.data_sources or self.data_sources['medications'].empty:
            features['has_chemotherapy'] = 'No'
            return features

        meds = self.data_sources['medications']

        # Chemotherapy keywords (from validated patient data)
        chemo_keywords = [
            'bevacizumab', 'avastin', 'selumetinib', 'koselugo',
            'temozolomide', 'carboplatin', 'vincristine', 'lomustine',
            'irinotecan', 'etoposide', 'dabrafenib', 'trametinib'
        ]

        if 'medication_name' in meds.columns:
            chemo_pattern = '|'.join(chemo_keywords)
            has_chemo = meds['medication_name'].str.contains(
                chemo_pattern, case=False, na=False
            ).any()

            features['has_chemotherapy'] = 'Yes' if has_chemo else 'No'

            if has_chemo:
                chemo_meds = meds[
                    meds['medication_name'].str.contains(chemo_pattern, case=False, na=False)
                ]
                features['chemotherapy_agents'] = chemo_meds['medication_name'].unique().tolist()

                # First chemotherapy date
                date_col = 'medication_start_date' if 'medication_start_date' in chemo_meds.columns else 'med_date_given_start'
                if date_col in chemo_meds.columns:
                    first_chemo = chemo_meds.sort_values(date_col).iloc[0]
                    if pd.notna(first_chemo[date_col]):
                        features['first_chemotherapy_date'] = first_chemo[date_col].isoformat()
                        features['age_at_first_chemotherapy_days'] = (
                            first_chemo[date_col] - self.birth_date
                        ).days

            # Specific agents
            features['has_bevacizumab'] = 'Yes' if meds['medication_name'].str.contains(
                'bevacizumab|avastin', case=False, na=False
            ).any() else 'No'

            features['has_selumetinib'] = 'Yes' if meds['medication_name'].str.contains(
                'selumetinib|koselugo', case=False, na=False
            ).any() else 'No'

        return features

    def _extract_radiation(self) -> Dict:
        """Extract radiation therapy features"""
        features = {}

        # Check radiation files
        if 'radiation_treatment_courses' in self.data_sources:
            rt_courses = self.data_sources['radiation_treatment_courses']
            if not rt_courses.empty:
                features['has_radiation_therapy'] = 'Yes'
                features['radiation_course_count'] = len(rt_courses)

                if 'start_date' in rt_courses.columns:
                    first_rt = rt_courses.sort_values('start_date').iloc[0]
                    if pd.notna(first_rt['start_date']):
                        features['first_radiation_date'] = first_rt['start_date'].isoformat()
                        features['age_at_first_radiation_days'] = (
                            first_rt['start_date'] - self.birth_date
                        ).days
            else:
                features['has_radiation_therapy'] = 'No'
                features['radiation_course_count'] = 0
        else:
            features['has_radiation_therapy'] = 'No'
            features['radiation_course_count'] = 0

        # Radiation appointments (fractions)
        if 'radiation_treatment_appointments' in self.data_sources:
            rt_appts = self.data_sources['radiation_treatment_appointments']
            features['radiation_fraction_count'] = len(rt_appts)

        return features

    def _extract_imaging_progression(self) -> Dict:
        """Extract imaging progression indicators"""
        features = {}

        if 'imaging' not in self.data_sources or self.data_sources['imaging'].empty:
            return features

        imaging = self.data_sources['imaging']

        # Look for progression keywords in findings
        progression_keywords = ['progression', 'recurrence', 'increased', 'growing', 'worsening']
        improvement_keywords = ['decreased', 'stable', 'improved', 'response', 'smaller']

        if 'findings' in imaging.columns:
            prog_pattern = '|'.join(progression_keywords)
            has_prog = imaging['findings'].str.contains(
                prog_pattern, case=False, na=False
            ).any()
            features['has_progression_imaging'] = 'Yes' if has_prog else 'No'

            if has_prog:
                prog_studies = imaging[
                    imaging['findings'].str.contains(prog_pattern, case=False, na=False)
                ]
                features['progression_event_count'] = len(prog_studies)

                if 'imaging_date' in prog_studies.columns:
                    first_prog = prog_studies.sort_values('imaging_date').iloc[0]
                    features['first_progression_date'] = first_prog['imaging_date'].isoformat()

            # Improvement
            imp_pattern = '|'.join(improvement_keywords)
            has_imp = imaging['findings'].str.contains(
                imp_pattern, case=False, na=False
            ).any()
            features['has_improvement_imaging'] = 'Yes' if has_imp else 'No'

            if has_imp:
                imp_studies = imaging[
                    imaging['findings'].str.contains(imp_pattern, case=False, na=False)
                ]
                features['improvement_event_count'] = len(imp_studies)

        return features

    def _extract_measurements(self) -> Dict:
        """Extract tumor measurement features"""
        features = {}

        if 'measurements' not in self.data_sources or self.data_sources['measurements'].empty:
            return features

        meas = self.data_sources['measurements']

        # Tumor size measurements
        tumor_keywords = ['tumor', 'lesion', 'mass', 'enhancement']

        if 'obs_coding_display' in meas.columns:
            tumor_pattern = '|'.join(tumor_keywords)
            tumor_meas = meas[
                meas['obs_coding_display'].str.contains(tumor_pattern, case=False, na=False)
            ]

            if not tumor_meas.empty:
                features['has_tumor_measurements'] = 'Yes'
                features['tumor_measurement_count'] = len(tumor_meas)

                # Get numeric values
                value_col = 'obs_value_quantity_value' if 'obs_value_quantity_value' in tumor_meas.columns else 'measurement_value'
                if value_col in tumor_meas.columns:
                    numeric_vals = pd.to_numeric(tumor_meas[value_col], errors='coerce').dropna()
                    if not numeric_vals.empty:
                        features['max_tumor_size_mm'] = float(numeric_vals.max())
                        features['min_tumor_size_mm'] = float(numeric_vals.min())

        return features

    def _calculate_derived_features(self, features: Dict) -> Dict:
        """Calculate derived features from extracted data"""
        derived = {}

        # Treatment modalities
        modalities = []
        if features.get('has_surgery') == 'Yes':
            modalities.append('Surgery')
        if features.get('has_radiation_therapy') == 'Yes':
            modalities.append('Radiation')
        if features.get('has_chemotherapy') == 'Yes':
            modalities.append('Chemotherapy')

        derived['treatment_modalities'] = modalities
        derived['treatment_modality_count'] = len(modalities)

        # Time from diagnosis to treatment
        if 'first_diagnosis_date' in features and 'first_surgery_date' in features:
            diag_date = pd.to_datetime(features['first_diagnosis_date'])
            surg_date = pd.to_datetime(features['first_surgery_date'])
            derived['days_diagnosis_to_surgery'] = (surg_date - diag_date).days

        # Post-op validation coverage
        if 'imaging_validation' in features:
            total_surgeries = len(features.get('surgical_events', []))
            validated = sum(
                1 for k, v in features['imaging_validation'].items()
                if v.get('has_gold_standard_validation', False)
            )
            derived['postop_validation_coverage'] = f"{validated}/{total_surgeries}"
            derived['postop_validation_percentage'] = (validated / total_surgeries * 100) if total_surgeries > 0 else 0

        return derived

    def save_waypoints(self, output_path: str):
        """Save event waypoints to CSV for downstream processing"""
        if self.event_waypoints:
            waypoints_df = pd.DataFrame(self.event_waypoints)
            waypoints_df.to_csv(output_path, index=False)
            logger.info(f"Saved {len(waypoints_df)} waypoints to {output_path}")

    def save_surgical_events(self, output_path: str):
        """Save surgical events to CSV for downstream processing"""
        if self.surgical_events:
            events_df = pd.DataFrame(self.surgical_events)
            events_df.to_csv(output_path, index=False)
            logger.info(f"Saved {len(events_df)} surgical events to {output_path}")