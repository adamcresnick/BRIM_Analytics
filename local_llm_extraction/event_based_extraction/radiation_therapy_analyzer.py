"""
Radiation Therapy Data Analysis and Extraction Strategy
========================================================
Comprehensive approach to handling complex radiation therapy data
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RadiationTherapyAnalyzer:
    """
    Analyze and extract meaningful radiation therapy data from multiple tables
    for prioritized abstraction
    """

    RADIATION_TABLES = [
        'radiation_care_plan_hierarchy',
        'radiation_care_plan_notes',
        'radiation_treatment_courses',
        'radiation_treatment_appointments',
        'radiation_service_request_notes',
        'radiation_service_request_rt_history',
        'radiation_data_summary'
    ]

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)

    def analyze_radiation_data(self, patient_id: str) -> Dict[str, pd.DataFrame]:
        """
        Load and analyze all radiation therapy tables for a patient
        """
        patient_path = self.staging_path / f"patient_{patient_id}"
        results = {}

        logger.info(f"Analyzing radiation therapy data for patient {patient_id}")

        # Load each radiation table
        for table_name in self.RADIATION_TABLES:
            file_path = patient_path / f"{table_name}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                results[table_name] = df
                logger.info(f"  Loaded {table_name}: {len(df)} records")
            else:
                logger.warning(f"  Missing {table_name}")
                results[table_name] = pd.DataFrame()

        return results

    def extract_treatment_courses(self, radiation_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Extract and consolidate radiation treatment courses

        Returns DataFrame with:
        - course_id
        - treatment_site
        - start_date
        - end_date
        - total_dose
        - fractions
        - treatment_intent (curative/palliative)
        - treatment_technique
        """
        logger.info("Extracting radiation treatment courses...")

        courses_list = []

        # Process treatment courses table
        if 'radiation_treatment_courses' in radiation_data and not radiation_data['radiation_treatment_courses'].empty:
            courses_df = radiation_data['radiation_treatment_courses']

            for idx, row in courses_df.iterrows():
                course = {
                    'course_id': row.get('course_id', f'course_{idx}'),
                    'treatment_site': row.get('treatment_site', ''),
                    'start_date': pd.to_datetime(row.get('start_date'), utc=True, errors='coerce'),
                    'end_date': pd.to_datetime(row.get('end_date'), utc=True, errors='coerce'),
                    'total_dose': row.get('total_dose', np.nan),
                    'fractions': row.get('fractions', np.nan),
                    'treatment_intent': self._determine_treatment_intent(row),
                    'treatment_technique': row.get('technique', ''),
                    'status': row.get('status', '')
                }
                courses_list.append(course)

        # Process care plan hierarchy for additional details
        if 'radiation_care_plan_hierarchy' in radiation_data and not radiation_data['radiation_care_plan_hierarchy'].empty:
            hierarchy_df = radiation_data['radiation_care_plan_hierarchy']

            # Extract radiation-specific care plans
            radiation_plans = hierarchy_df[
                hierarchy_df['care_plan_title'].str.contains('radiation|RT|XRT', case=False, na=False)
            ] if 'care_plan_title' in hierarchy_df.columns else pd.DataFrame()

            for idx, plan in radiation_plans.iterrows():
                course = {
                    'course_id': f'plan_{plan.get("care_plan_id", idx)}',
                    'treatment_site': self._extract_treatment_site(plan),
                    'start_date': pd.to_datetime(plan.get('period_start'), utc=True, errors='coerce'),
                    'end_date': pd.to_datetime(plan.get('period_end'), utc=True, errors='coerce'),
                    'treatment_intent': plan.get('intent', ''),
                    'care_plan_title': plan.get('care_plan_title', ''),
                    'status': plan.get('status', '')
                }
                courses_list.append(course)

        courses_df = pd.DataFrame(courses_list)

        if not courses_df.empty:
            # Remove duplicates
            courses_df = courses_df.drop_duplicates(subset=['start_date', 'treatment_site'], keep='first')

            # Calculate duration (handle potential timezone mismatches)
            if 'start_date' in courses_df.columns and 'end_date' in courses_df.columns:
                # Ensure both columns are timezone-aware
                courses_df['start_date'] = pd.to_datetime(courses_df['start_date'], utc=True, errors='coerce')
                courses_df['end_date'] = pd.to_datetime(courses_df['end_date'], utc=True, errors='coerce')

                # Calculate duration only where both dates are valid
                valid_dates = courses_df['start_date'].notna() & courses_df['end_date'].notna()
                courses_df.loc[valid_dates, 'duration_days'] = (
                    courses_df.loc[valid_dates, 'end_date'] - courses_df.loc[valid_dates, 'start_date']
                ).dt.days

            # Sort by start date
            courses_df = courses_df.sort_values('start_date')

        logger.info(f"  Extracted {len(courses_df)} radiation courses")

        return courses_df

    def extract_radiation_appointments(self, radiation_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Extract individual radiation treatment appointments/fractions
        """
        logger.info("Extracting radiation appointments...")

        appointments = []

        if 'radiation_treatment_appointments' in radiation_data and not radiation_data['radiation_treatment_appointments'].empty:
            appts_df = radiation_data['radiation_treatment_appointments']

            # Parse appointment dates
            if 'appointment_date' in appts_df.columns:
                appts_df['appointment_date'] = pd.to_datetime(appts_df['appointment_date'], utc=True, errors='coerce')
            elif 'date' in appts_df.columns:
                appts_df['appointment_date'] = pd.to_datetime(appts_df['date'], utc=True, errors='coerce')

            # Add appointment context
            appts_df['appointment_type'] = 'treatment_fraction'

            # Identify simulation/planning appointments
            if 'appointment_type' in appts_df.columns:
                sim_mask = appts_df['appointment_type'].str.contains('sim|plan', case=False, na=False)
                appts_df.loc[sim_mask, 'appointment_type'] = 'simulation_planning'

            appointments = appts_df

        logger.info(f"  Found {len(appointments)} radiation appointments")

        return pd.DataFrame(appointments)

    def identify_priority_radiation_notes(self, radiation_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Identify high-priority radiation notes for abstraction

        Priority levels:
        1. Treatment planning notes
        2. Simulation notes
        3. Treatment completion summaries
        4. Toxicity/side effect notes
        """
        priority_notes = []

        # Process care plan notes
        if 'radiation_care_plan_notes' in radiation_data and not radiation_data['radiation_care_plan_notes'].empty:
            notes_df = radiation_data['radiation_care_plan_notes']

            for idx, note in notes_df.iterrows():
                note_text = str(note.get('note_text', '')).lower()

                priority = 'low'
                note_type = 'general'

                # Check for high-priority content
                if any(term in note_text for term in ['treatment plan', 'planning', 'dose prescription']):
                    priority = 'high'
                    note_type = 'treatment_planning'
                elif any(term in note_text for term in ['simulation', 'sim note', 'ct sim']):
                    priority = 'high'
                    note_type = 'simulation'
                elif any(term in note_text for term in ['completion', 'final', 'summary']):
                    priority = 'high'
                    note_type = 'completion_summary'
                elif any(term in note_text for term in ['toxicity', 'side effect', 'adverse']):
                    priority = 'medium'
                    note_type = 'toxicity'

                priority_notes.append({
                    'note_id': note.get('note_id', idx),
                    'note_date': pd.to_datetime(note.get('note_date'), utc=True, errors='coerce'),
                    'note_type': note_type,
                    'priority': priority,
                    'note_preview': note_text[:200] if len(note_text) > 200 else note_text
                })

        # Process service request notes
        if 'radiation_service_request_notes' in radiation_data and not radiation_data['radiation_service_request_notes'].empty:
            sr_notes = radiation_data['radiation_service_request_notes']

            for idx, note in sr_notes.iterrows():
                priority_notes.append({
                    'note_id': f"sr_{note.get('service_request_id', idx)}",
                    'note_date': pd.to_datetime(note.get('authored_on'), utc=True, errors='coerce'),
                    'note_type': 'service_request',
                    'priority': 'medium',
                    'note_preview': str(note.get('code_text', ''))[:200]
                })

        notes_df = pd.DataFrame(priority_notes)

        if not notes_df.empty:
            notes_df = notes_df.sort_values('note_date')

            priority_counts = notes_df['priority'].value_counts()
            logger.info("  Note priorities:")
            for priority, count in priority_counts.items():
                logger.info(f"    {priority}: {count}")

        return notes_df

    def create_radiation_timeline(self, courses_df: pd.DataFrame, appointments_df: pd.DataFrame) -> Dict:
        """
        Create comprehensive radiation treatment timeline
        """
        timeline = {
            'total_courses': len(courses_df),
            'total_fractions': len(appointments_df[appointments_df['appointment_type'] == 'treatment_fraction']) if not appointments_df.empty else 0,
            'courses': []
        }

        for idx, course in courses_df.iterrows():
            course_info = {
                'course_number': idx + 1,
                'treatment_site': course.get('treatment_site', 'Unknown'),
                'start_date': course['start_date'].isoformat() if pd.notna(course['start_date']) else None,
                'end_date': course['end_date'].isoformat() if pd.notna(course['end_date']) else None,
                'duration_days': int(course['duration_days']) if pd.notna(course['duration_days']) else None,
                'total_dose': float(course['total_dose']) if pd.notna(course['total_dose']) else None,
                'fractions': int(course['fractions']) if pd.notna(course['fractions']) else None,
                'treatment_intent': course.get('treatment_intent', ''),
                'status': course.get('status', '')
            }

            # Find appointments for this course (within date range)
            if not appointments_df.empty and pd.notna(course['start_date']) and pd.notna(course['end_date']):
                course_appts = appointments_df[
                    (appointments_df['appointment_date'] >= course['start_date']) &
                    (appointments_df['appointment_date'] <= course['end_date'])
                ]
                course_info['actual_fractions'] = len(course_appts)

            timeline['courses'].append(course_info)

        # Calculate overall treatment span
        if not courses_df.empty:
            timeline['first_treatment'] = courses_df['start_date'].min().isoformat() if pd.notna(courses_df['start_date'].min()) else None
            timeline['last_treatment'] = courses_df['end_date'].max().isoformat() if pd.notna(courses_df['end_date'].max()) else None

            if timeline['first_treatment'] and timeline['last_treatment']:
                span = courses_df['end_date'].max() - courses_df['start_date'].min()
                timeline['total_treatment_span_days'] = span.days

        return timeline

    def _determine_treatment_intent(self, row: pd.Series) -> str:
        """Determine treatment intent from available data"""
        text_fields = ['intent', 'description', 'notes']
        combined_text = ' '.join([str(row.get(field, '')) for field in text_fields]).lower()

        if any(term in combined_text for term in ['curative', 'definitive', 'radical']):
            return 'curative'
        elif any(term in combined_text for term in ['palliative', 'symptom', 'pain']):
            return 'palliative'
        elif any(term in combined_text for term in ['prophylactic', 'preventive']):
            return 'prophylactic'
        else:
            return 'unknown'

    def _extract_treatment_site(self, row: pd.Series) -> str:
        """Extract treatment site from care plan or notes"""
        text = str(row.get('care_plan_title', '')) + ' ' + str(row.get('description', ''))

        # Common brain tumor sites
        sites = ['brain', 'spine', 'cranial', 'posterior fossa', 'supratentorial',
                 'brainstem', 'cerebellum', 'temporal', 'frontal', 'parietal', 'occipital']

        for site in sites:
            if site in text.lower():
                return site.title()

        return 'CNS'

    def process_patient(self, patient_id: str) -> Dict:
        """Process all radiation therapy data for a patient"""

        # Load all radiation data
        radiation_data = self.analyze_radiation_data(patient_id)

        # Extract structured information
        courses = self.extract_treatment_courses(radiation_data)
        appointments = self.extract_radiation_appointments(radiation_data)
        priority_notes = self.identify_priority_radiation_notes(radiation_data)

        # Create timeline
        timeline = self.create_radiation_timeline(courses, appointments)

        return {
            'courses': courses,
            'appointments': appointments,
            'priority_notes': priority_notes,
            'timeline': timeline,
            'raw_data': radiation_data
        }


if __name__ == "__main__":
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    analyzer = RadiationTherapyAnalyzer(staging_path)

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    results = analyzer.process_patient(patient_id)

    # Save results
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
    output_path.mkdir(exist_ok=True)

    # Save courses
    if not results['courses'].empty:
        results['courses'].to_csv(output_path / f"radiation_courses_{patient_id}.csv", index=False)
        print(f"\nRadiation courses saved: {len(results['courses'])} courses")
        print("\nRadiation Course Summary:")
        print(results['courses'][['treatment_site', 'start_date', 'end_date', 'duration_days', 'treatment_intent']].to_string())

    # Save priority notes
    if not results['priority_notes'].empty:
        results['priority_notes'].to_csv(output_path / f"radiation_priority_notes_{patient_id}.csv", index=False)
        print(f"\nPriority radiation notes saved: {len(results['priority_notes'])} notes")

    # Save timeline
    with open(output_path / f"radiation_timeline_{patient_id}.json", 'w') as f:
        json.dump(results['timeline'], f, indent=2)

    print(f"\nRadiation Timeline:")
    print(f"  Total courses: {results['timeline']['total_courses']}")
    print(f"  Total fractions: {results['timeline']['total_fractions']}")
    if 'total_treatment_span_days' in results['timeline']:
        print(f"  Total treatment span: {results['timeline']['total_treatment_span_days']} days")