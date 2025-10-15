"""
Integrated Clinical Timeline Builder
=====================================
Combines surgeries, imaging, treatments (chemo/radiation) into unified timeline
for BRIM extraction prioritization
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import json

# Import our analyzers
from tumor_surgery_classifier import TumorSurgeryClassifier
from radiation_therapy_analyzer import RadiationTherapyAnalyzer
from comprehensive_chemotherapy_identifier import ComprehensiveChemotherapyIdentifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedClinicalTimeline:
    """Build comprehensive timeline integrating all clinical events"""

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)
        self.surgery_classifier = TumorSurgeryClassifier(staging_path)
        self.radiation_analyzer = RadiationTherapyAnalyzer(staging_path)
        self.chemo_identifier = ComprehensiveChemotherapyIdentifier()

    def build_timeline(self, patient_id: str) -> Dict:
        """
        Build integrated timeline for patient

        Returns dictionary with:
        - chronological_events: All events in time order
        - treatment_phases: Defined treatment periods
        - priority_documents: Documents requiring abstraction
        - summary_statistics: Key metrics
        """
        logger.info(f"Building integrated timeline for patient {patient_id}")

        # Collect all events
        events = []

        # 1. SURGERIES
        surgery_results = self.surgery_classifier.process_patient(patient_id)
        if not surgery_results['tumor_surgeries'].empty:
            for idx, surgery in surgery_results['tumor_surgeries'].iterrows():
                if pd.notna(surgery.get('proc_date')):
                    events.append({
                        'date': surgery['proc_date'],
                        'event_type': 'surgery',
                        'subtype': surgery.get('surgery_type', 'resection'),
                        'description': surgery.get('proc_code_text', 'Surgical procedure'),
                        'preliminary_classification': surgery.get('preliminary_event_type', ''),
                        'requires_operative_note': surgery.get('requires_operative_note', False),
                        'priority': 'high'
                    })

        # 2. CHEMOTHERAPY
        patient_path = self.staging_path / f"patient_{patient_id}"
        meds_file = patient_path / "medications.csv"
        if meds_file.exists():
            meds_df = pd.read_csv(meds_file)
            chemo_df, _ = self.chemo_identifier.identify_chemotherapy(meds_df)
            periods_df = self.chemo_identifier.extract_treatment_periods(chemo_df)

            for idx, period in periods_df.iterrows():
                if pd.notna(period.get('start_date')):
                    events.append({
                        'date': period['start_date'],
                        'event_type': 'chemotherapy_start',
                        'subtype': period.get('treatment_phase', 'treatment'),
                        'description': f"{period.get('drug_name', 'Chemotherapy')} started",
                        'duration_days': period.get('duration_days', 0),
                        'priority': 'high'
                    })

                if pd.notna(period.get('end_date')):
                    events.append({
                        'date': period['end_date'],
                        'event_type': 'chemotherapy_end',
                        'subtype': period.get('treatment_phase', 'treatment'),
                        'description': f"{period.get('drug_name', 'Chemotherapy')} completed",
                        'priority': 'medium'
                    })

        # 3. RADIATION
        radiation_results = self.radiation_analyzer.process_patient(patient_id)
        if not radiation_results['courses'].empty:
            for idx, course in radiation_results['courses'].iterrows():
                if pd.notna(course.get('start_date')):
                    events.append({
                        'date': course['start_date'],
                        'event_type': 'radiation_start',
                        'subtype': course.get('treatment_intent', 'treatment'),
                        'description': f"Radiation to {course.get('treatment_site', 'CNS')} started",
                        'total_dose': course.get('total_dose'),
                        'fractions': course.get('fractions'),
                        'priority': 'high'
                    })

                if pd.notna(course.get('end_date')):
                    events.append({
                        'date': course['end_date'],
                        'event_type': 'radiation_end',
                        'subtype': course.get('treatment_intent', 'treatment'),
                        'description': f"Radiation to {course.get('treatment_site', 'CNS')} completed",
                        'priority': 'medium'
                    })

        # 4. KEY IMAGING
        if not surgery_results['imaging_with_context'].empty:
            priority_imaging = surgery_results['imaging_with_context'][
                surgery_results['imaging_with_context']['abstraction_priority'] == 'high'
            ]

            for idx, img in priority_imaging.iterrows():
                if pd.notna(img.get('imaging_date')):
                    events.append({
                        'date': img['imaging_date'],
                        'event_type': 'imaging',
                        'subtype': img.get('imaging_context', 'surveillance'),
                        'description': f"{img.get('imaging_modality', 'Imaging')} - {img.get('imaging_context', '')}",
                        'days_from_surgery': img.get('days_from_surgery'),
                        'priority': 'high' if img.get('imaging_context') in ['pre_operative', 'post_operative'] else 'medium'
                    })

        # Sort events chronologically
        events_df = pd.DataFrame(events)
        if not events_df.empty:
            events_df = events_df.sort_values('date')
            events_df['date_str'] = events_df['date'].dt.strftime('%Y-%m-%d')

        # Define treatment phases
        treatment_phases = self._define_treatment_phases(events_df)

        # Identify priority documents for abstraction
        priority_documents = self._identify_priority_documents(
            surgery_results,
            radiation_results,
            events_df
        )

        # Calculate summary statistics
        summary = self._calculate_summary_statistics(
            events_df,
            surgery_results,
            radiation_results,
            periods_df if 'periods_df' in locals() else pd.DataFrame()
        )

        return {
            'chronological_events': events_df.to_dict('records') if not events_df.empty else [],
            'treatment_phases': treatment_phases,
            'priority_documents': priority_documents,
            'summary_statistics': summary
        }

    def _define_treatment_phases(self, events_df: pd.DataFrame) -> List[Dict]:
        """Define distinct treatment phases based on events"""
        phases = []

        if events_df.empty:
            return phases

        # Find initial surgery
        surgeries = events_df[events_df['event_type'] == 'surgery']
        if not surgeries.empty:
            initial_surgery = surgeries.iloc[0]
            phases.append({
                'phase': 'initial_treatment',
                'start_date': initial_surgery['date_str'],
                'description': 'Initial surgical resection and diagnosis'
            })

        # Find chemotherapy phases
        chemo_starts = events_df[events_df['event_type'] == 'chemotherapy_start']
        for idx, chemo in chemo_starts.iterrows():
            chemo_end = events_df[
                (events_df['event_type'] == 'chemotherapy_end') &
                (events_df['date'] > chemo['date'])
            ]

            phase = {
                'phase': 'chemotherapy',
                'start_date': chemo['date_str'],
                'end_date': chemo_end.iloc[0]['date_str'] if not chemo_end.empty else None,
                'description': chemo['description']
            }
            phases.append(phase)

        # Find radiation phases
        rad_starts = events_df[events_df['event_type'] == 'radiation_start']
        for idx, rad in rad_starts.iterrows():
            rad_end = events_df[
                (events_df['event_type'] == 'radiation_end') &
                (events_df['date'] > rad['date'])
            ]

            phase = {
                'phase': 'radiation',
                'start_date': rad['date_str'],
                'end_date': rad_end.iloc[0]['date_str'] if not rad_end.empty else None,
                'description': rad['description']
            }
            phases.append(phase)

        return phases

    def _identify_priority_documents(self, surgery_results: Dict,
                                    radiation_results: Dict,
                                    events_df: pd.DataFrame) -> Dict:
        """Identify priority documents for BRIM extraction"""

        priority_docs = {
            'operative_notes': [],
            'imaging_reports': [],
            'radiation_plans': [],
            'pathology_reports': []
        }

        # Operative notes for tumor surgeries
        if not surgery_results['tumor_surgeries'].empty:
            for idx, surgery in surgery_results['tumor_surgeries'].iterrows():
                if surgery.get('requires_operative_note'):
                    priority_docs['operative_notes'].append({
                        'date': surgery['proc_date'].isoformat() if pd.notna(surgery['proc_date']) else None,
                        'procedure': surgery.get('proc_code_text', ''),
                        'classification_needed': surgery.get('preliminary_event_type', ''),
                        'priority': 'critical'
                    })

        # High-priority imaging reports
        if 'imaging_with_context' in surgery_results and not surgery_results['imaging_with_context'].empty:
            priority_imaging = surgery_results['imaging_with_context'][
                surgery_results['imaging_with_context']['abstraction_priority'] == 'high'
            ]

            for idx, img in priority_imaging.head(10).iterrows():  # Top 10 priority
                priority_docs['imaging_reports'].append({
                    'date': img['imaging_date'].isoformat() if pd.notna(img['imaging_date']) else None,
                    'modality': img.get('imaging_modality', 'Unknown'),
                    'context': img.get('imaging_context', ''),
                    'days_from_surgery': img.get('days_from_surgery'),
                    'priority': 'high'
                })

        # Radiation treatment plans
        if not radiation_results['priority_notes'].empty:
            high_priority_notes = radiation_results['priority_notes'][
                radiation_results['priority_notes']['priority'] == 'high'
            ]

            for idx, note in high_priority_notes.head(5).iterrows():
                priority_docs['radiation_plans'].append({
                    'date': note['note_date'].isoformat() if pd.notna(note['note_date']) else None,
                    'note_type': note.get('note_type', ''),
                    'priority': 'high'
                })

        return priority_docs

    def _calculate_summary_statistics(self, events_df: pd.DataFrame,
                                     surgery_results: Dict,
                                     radiation_results: Dict,
                                     chemo_periods_df: pd.DataFrame) -> Dict:
        """Calculate summary statistics for the timeline"""

        summary = {
            'total_events': len(events_df) if not events_df.empty else 0,
            'tumor_surgeries': len(surgery_results['tumor_surgeries']) if 'tumor_surgeries' in surgery_results else 0,
            'chemotherapy_courses': len(chemo_periods_df) if not chemo_periods_df.empty else 0,
            'radiation_courses': radiation_results['timeline']['total_courses'] if 'timeline' in radiation_results else 0,
            'radiation_fractions': radiation_results['timeline']['total_fractions'] if 'timeline' in radiation_results else 0,
            'priority_imaging_studies': 0,
            'treatment_span_days': 0
        }

        # Count priority imaging
        if 'imaging_with_context' in surgery_results and not surgery_results['imaging_with_context'].empty:
            summary['priority_imaging_studies'] = len(
                surgery_results['imaging_with_context'][
                    surgery_results['imaging_with_context']['abstraction_priority'] == 'high'
                ]
            )

        # Calculate overall treatment span
        if not events_df.empty:
            first_event = events_df['date'].min()
            last_event = events_df['date'].max()
            if pd.notna(first_event) and pd.notna(last_event):
                summary['treatment_span_days'] = (last_event - first_event).days
                summary['first_event_date'] = first_event.isoformat()
                summary['last_event_date'] = last_event.isoformat()

        return summary

    def save_timeline(self, patient_id: str, timeline: Dict, output_path: Path):
        """Save the integrated timeline to file"""
        output_path = Path(output_path)
        output_path.mkdir(exist_ok=True)

        # Save JSON timeline
        timeline_file = output_path / f"integrated_timeline_{patient_id}.json"
        with open(timeline_file, 'w') as f:
            # Convert any datetime objects to strings for JSON serialization
            timeline_serializable = self._make_json_serializable(timeline)
            json.dump(timeline_serializable, f, indent=2)

        logger.info(f"Integrated timeline saved to {timeline_file}")

        # Save events CSV
        if timeline['chronological_events']:
            events_df = pd.DataFrame(timeline['chronological_events'])
            events_df.to_csv(output_path / f"clinical_events_{patient_id}.csv", index=False)

        return timeline_file

    def _make_json_serializable(self, obj):
        """Convert datetime objects to strings for JSON serialization"""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif pd.isna(obj):
            return None
        else:
            return obj


if __name__ == "__main__":
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    builder = IntegratedClinicalTimeline(staging_path)

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    timeline = builder.build_timeline(patient_id)

    # Save results
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
    timeline_file = builder.save_timeline(patient_id, timeline, output_path)

    # Print summary
    print("\n" + "="*80)
    print("INTEGRATED CLINICAL TIMELINE SUMMARY")
    print("="*80)

    summary = timeline['summary_statistics']
    print(f"\nTotal Clinical Events: {summary['total_events']}")
    print(f"  - Tumor Surgeries: {summary['tumor_surgeries']}")
    print(f"  - Chemotherapy Courses: {summary['chemotherapy_courses']}")
    print(f"  - Radiation Courses: {summary['radiation_courses']} ({summary['radiation_fractions']} fractions)")
    print(f"  - Priority Imaging Studies: {summary['priority_imaging_studies']}")

    if 'first_event_date' in summary:
        print(f"\nTreatment Timeline:")
        print(f"  First Event: {summary['first_event_date']}")
        print(f"  Last Event: {summary['last_event_date']}")
        print(f"  Total Span: {summary['treatment_span_days']} days")

    print(f"\nTreatment Phases Identified: {len(timeline['treatment_phases'])}")
    for phase in timeline['treatment_phases']:
        print(f"  - {phase['phase']}: {phase.get('start_date', 'Unknown')} - {phase['description']}")

    priority_docs = timeline['priority_documents']
    print(f"\nPriority Documents for Abstraction:")
    print(f"  - Operative Notes: {len(priority_docs['operative_notes'])}")
    print(f"  - Imaging Reports: {len(priority_docs['imaging_reports'])}")
    print(f"  - Radiation Plans: {len(priority_docs['radiation_plans'])}")

    print(f"\nTimeline saved to: {timeline_file}")