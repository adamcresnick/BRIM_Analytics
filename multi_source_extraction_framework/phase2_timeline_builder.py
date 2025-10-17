"""
PHASE 2: Event Timeline Construction
=====================================
Build comprehensive clinical timeline
Cross-reference procedures with operative notes
Map progression events from imaging
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ClinicalEvent:
    """Represents a clinical event in the patient timeline"""
    event_id: str
    event_type: str  # 'initial_diagnosis', 'surgery', 'progression', 'recurrence', 'treatment'
    event_date: datetime
    age_at_event_days: int

    # Event details
    description: str = ""
    encounter_id: Optional[str] = None
    procedure_codes: List[str] = field(default_factory=list)
    diagnosis_codes: List[str] = field(default_factory=list)

    # Associated documents
    binary_references: List[str] = field(default_factory=list)
    imaging_references: List[str] = field(default_factory=list)

    # Measurements and metadata
    measurements: Dict[str, any] = field(default_factory=dict)
    metadata: Dict[str, any] = field(default_factory=dict)

    # Event relationships
    parent_event_id: Optional[str] = None
    related_events: List[str] = field(default_factory=list)


class ClinicalTimelineBuilder:
    """
    Phase 2: Build comprehensive clinical timeline from multiple sources
    """

    def __init__(self, staging_path: str, structured_features: Dict[str, any]):
        self.staging_path = Path(staging_path)
        self.structured_features = structured_features
        self.events = []
        self.data_sources = {}

    def build_timeline(self, patient_id: str, birth_date: str) -> List[ClinicalEvent]:
        """
        Main entry point for Phase 2 - build clinical timeline

        Args:
            patient_id: Patient FHIR ID
            birth_date: Patient birth date (YYYY-MM-DD)

        Returns:
            List of clinical events in chronological order
        """
        logger.info(f"PHASE 2: Building clinical timeline for patient {patient_id}")

        self.patient_id = patient_id
        self.birth_date = pd.to_datetime(birth_date, utc=True)
        self.patient_path = self._get_patient_path(patient_id)

        # Load all data sources
        self._load_data_sources()

        # Extract events from different sources
        events = []

        # 1. Extract surgical events
        surgical_events = self._extract_surgical_events()
        events.extend(surgical_events)
        logger.info(f"  Found {len(surgical_events)} surgical events")

        # 2. Extract progression events from imaging
        progression_events = self._extract_progression_events()
        events.extend(progression_events)
        logger.info(f"  Found {len(progression_events)} progression events")

        # 3. Extract diagnosis events
        diagnosis_events = self._extract_diagnosis_events()
        events.extend(diagnosis_events)
        logger.info(f"  Found {len(diagnosis_events)} diagnosis events")

        # 4. Extract treatment events
        treatment_events = self._extract_treatment_events()
        events.extend(treatment_events)
        logger.info(f"  Found {len(treatment_events)} treatment events")

        # 5. Deduplicate and link related events
        events = self._deduplicate_and_link_events(events)

        # 6. Sort chronologically
        events.sort(key=lambda x: x.event_date)

        # 7. Classify event types (initial vs progression vs recurrence)
        events = self._classify_event_types(events)

        logger.info(f"PHASE 2 Complete: Built timeline with {len(events)} events")

        self.events = events
        return events

    def _get_patient_path(self, patient_id: str) -> Path:
        """Get patient-specific staging directory"""
        # Use patient ID as-is, preserving dots
        return self.staging_path / f"patient_{patient_id}"

    def _load_data_sources(self):
        """Load all necessary data sources"""
        logger.info("Loading data sources for timeline construction...")

        # Load structured data with correct column names from validation
        sources_to_load = {
            'procedures': ['proc_performed_date_time', 'procedure_date'],
            'binary_files': ['dr_date', 'dc_context_period_start'],
            'imaging': ['imaging_date'],
            'diagnoses': ['cond_onset_date_time', 'cond_recorded_date'],
            'medications': ['med_date_given_start'],
            'encounters': ['enc_period_start'],
            'radiation_treatment_courses': ['start_date', 'end_date']
        }

        for source, date_cols in sources_to_load.items():
            file_path = self.patient_path / f"{source}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                self.data_sources[source] = df
            else:
                self.data_sources[source] = pd.DataFrame()

    def _extract_surgical_events(self) -> List[ClinicalEvent]:
        """Extract surgical events from procedures and operative notes"""
        events = []

        # Get procedures
        if 'procedures' in self.data_sources and not self.data_sources['procedures'].empty:
            procs_df = self.data_sources['procedures']

            # Identify surgical procedures
            surgical_keywords = [
                'craniotomy', 'craniectomy', 'resection', 'debulking',
                'ventriculostomy', 'shunt', 'biopsy', 'excision', 'removal'
            ]

            # Use validated column names
            if 'proc_code_text' in procs_df.columns:
                pattern = '|'.join(surgical_keywords)
                surgical_procs = procs_df[
                    procs_df['proc_code_text'].str.contains(pattern, case=False, na=False)
                ]
            elif 'is_surgical_keyword' in procs_df.columns:
                # Use pre-calculated surgical flag
                surgical_procs = procs_df[procs_df['is_surgical_keyword'] == True]
            else:
                surgical_procs = pd.DataFrame()

            # Group by date to handle same-day procedures
            if not surgical_procs.empty and 'proc_performed_date_time' in surgical_procs.columns:
                surgical_procs['proc_performed_date_time'] = pd.to_datetime(surgical_procs['proc_performed_date_time'], utc=True)
                for date, group in surgical_procs.groupby(surgical_procs['proc_performed_date_time'].dt.date):
                        # Find matching operative notes
                        binary_refs = self._find_matching_operative_notes(date)

                        # Calculate age (make sure event_date is timezone-aware)
                        event_date = pd.Timestamp(date, tz='UTC')
                        age_days = (event_date - self.birth_date).days

                        # Create event
                        event = ClinicalEvent(
                            event_id=f"surgery_{date.strftime('%Y%m%d')}",
                            event_type='surgery',
                            event_date=event_date,
                            age_at_event_days=age_days,
                            description=f"Surgical procedures: {', '.join(group['proc_code_text'].tolist())}",
                            encounter_id=group['proc_encounter_reference'].iloc[0] if 'proc_encounter_reference' in group else None,
                            procedure_codes=group['pcc_code_coding_code'].tolist() if 'pcc_code_coding_code' in group else [],
                            binary_references=binary_refs,
                            metadata={
                                'procedure_count': len(group),
                                'procedure_types': group['proc_code_text'].tolist()
                            }
                        )
                        events.append(event)

        # Also check for operative notes without matching procedures
        if 'binary_files' in self.data_sources and not self.data_sources['binary_files'].empty:
            op_notes = self.data_sources['binary_files'][
                self.data_sources['binary_files']['dr_type_text'].str.contains(
                    'OP Note|Operative', case=False, na=False
                )
            ]

            if not op_notes.empty and 'dr_date' in op_notes.columns:
                # Group by date
                op_notes['dr_date'] = pd.to_datetime(op_notes['dr_date'], utc=True)
                for date, notes_group in op_notes.groupby(op_notes['dr_date'].dt.date):
                    # Check if we already have a surgical event for this date
                    existing_dates = [e.event_date.date() for e in events]
                    if date not in existing_dates:
                        event_date = pd.Timestamp(date, tz='UTC')
                        age_days = (event_date - self.birth_date).days

                        event = ClinicalEvent(
                            event_id=f"surgery_{date.strftime('%Y%m%d')}",
                            event_type='surgery',
                            event_date=event_date,
                            age_at_event_days=age_days,
                            description=f"Surgical event from {len(notes_group)} operative notes",
                            binary_references=notes_group['dr_id'].tolist() if 'dr_id' in notes_group else [],
                            metadata={
                                'source': 'operative_notes_only',
                                'note_count': len(notes_group)
                            }
                        )
                        events.append(event)

        return events

    def _extract_progression_events(self) -> List[ClinicalEvent]:
        """Extract progression events from imaging reports"""
        events = []

        if 'imaging' not in self.data_sources or self.data_sources['imaging'].empty:
            return events

        imaging_df = self.data_sources['imaging']

        # Keywords indicating progression
        progression_keywords = [
            'progression', 'progressive', 'interval increase', 'growing',
            'enlarged', 'new enhancement', 'increased enhancement',
            'worsening', 'interval growth', 'expansion'
        ]

        # Keywords indicating recurrence
        recurrence_keywords = [
            'recurrence', 'recurrent', 'new lesion', 'new mass',
            'new enhancement at resection site'
        ]

        if 'result_information' in imaging_df.columns and 'imaging_date' in imaging_df.columns:
            for _, row in imaging_df.iterrows():
                result_text = str(row.get('result_information', '')).lower()

                event_type = None
                description = ""

                # Check for progression
                if any(keyword in result_text for keyword in progression_keywords):
                    event_type = 'progression'
                    description = "Progressive disease on imaging"

                # Check for recurrence
                elif any(keyword in result_text for keyword in recurrence_keywords):
                    event_type = 'recurrence'
                    description = "Recurrent disease on imaging"

                if event_type:
                    event_date = pd.to_datetime(row['imaging_date'], utc=True)
                    age_days = (event_date - self.birth_date).days

                    # Extract relevant snippet from report
                    snippet = self._extract_relevant_snippet(result_text, progression_keywords + recurrence_keywords)

                    event = ClinicalEvent(
                        event_id=f"{event_type}_{event_date.strftime('%Y%m%d')}_{row.get('imaging_procedure_id', '')}",
                        event_type=event_type,
                        event_date=event_date,
                        age_at_event_days=age_days,
                        description=description,
                        imaging_references=[row.get('imaging_procedure_id', '')],
                        metadata={
                            'imaging_modality': row.get('imaging_modality', ''),
                            'imaging_procedure': row.get('imaging_procedure', ''),
                            'result_snippet': snippet[:500]  # First 500 chars
                        }
                    )
                    events.append(event)

        return events

    def _extract_diagnosis_events(self) -> List[ClinicalEvent]:
        """Extract diagnosis events"""
        events = []

        if 'diagnoses' not in self.data_sources or self.data_sources['diagnoses'].empty:
            return events

        diag_df = self.data_sources['diagnoses']

        # Focus on brain tumor diagnoses
        brain_tumor_codes = ['C71', 'D43', 'D33']

        if 'icd10_code' in diag_df.columns:
            brain_tumors = diag_df[
                diag_df['icd10_code'].str.startswith(tuple(brain_tumor_codes), na=False)
            ]

            if not brain_tumors.empty and 'cond_recorded_date' in brain_tumors.columns:
                # Get first diagnosis as initial diagnosis event
                first_diagnosis = brain_tumors.sort_values('cond_recorded_date').iloc[0]
                event_date = pd.to_datetime(first_diagnosis['cond_recorded_date'], utc=True)
                age_days = (event_date - self.birth_date).days

                event = ClinicalEvent(
                    event_id=f"diagnosis_{event_date.strftime('%Y%m%d')}",
                    event_type='initial_diagnosis',
                    event_date=event_date,
                    age_at_event_days=age_days,
                    description=f"Initial brain tumor diagnosis: {first_diagnosis.get('diagnosis_name', '')}",
                    diagnosis_codes=[first_diagnosis.get('icd10_code', '')],
                    metadata={
                        'diagnosis_name': first_diagnosis.get('diagnosis_name', ''),
                        'clinical_status': first_diagnosis.get('clinical_status_text', '')
                    }
                )
                events.append(event)

        return events

    def _extract_treatment_events(self) -> List[ClinicalEvent]:
        """Extract treatment events (radiation, chemotherapy)"""
        events = []

        # Radiation therapy events
        if 'radiation_treatment_courses' in self.data_sources:
            rad_df = self.data_sources['radiation_treatment_courses']
            if not rad_df.empty and 'start_date' in rad_df.columns:
                for _, course in rad_df.iterrows():
                    event_date = course['start_date']
                    if pd.notna(event_date):
                        event_date = pd.to_datetime(event_date, utc=True)
                        age_days = (event_date - self.birth_date).days

                        event = ClinicalEvent(
                            event_id=f"radiation_{event_date.strftime('%Y%m%d')}",
                            event_type='treatment',
                            event_date=event_date,
                            age_at_event_days=age_days,
                            description="Radiation therapy course started",
                            metadata={
                                'treatment_type': 'radiation',
                                'end_date': course.get('end_date', ''),
                                'total_dose': course.get('total_dose_gy', '')
                            }
                        )
                        events.append(event)

        # Chemotherapy and targeted therapy events
        if 'medications' in self.data_sources:
            meds_df = self.data_sources['medications']
            # Include actual drugs found in this patient's data
            chemo_keywords = [
                'bevacizumab', 'avastin',  # Anti-VEGF
                'selumetinib', 'koselugo',  # MEK inhibitor
                'temozolomide', 'temodar',  # Alkylating agent
                'carboplatin', 'vincristine', 'lomustine',  # Traditional chemo
                'dabrafenib', 'trametinib',  # BRAF/MEK inhibitors
                'everolimus'  # mTOR inhibitor
            ]

            # Also track steroids separately as they're important for brain tumors
            steroid_keywords = ['dexamethasone', 'decadron', 'prednisone', 'methylprednisolone']

            if not meds_df.empty and 'medication_name' in meds_df.columns:
                pattern = '|'.join(chemo_keywords)
                chemo_meds = meds_df[
                    meds_df['medication_name'].str.contains(pattern, case=False, na=False)
                ]

                if not chemo_meds.empty and 'medication_start_date' in chemo_meds.columns:
                    # Group by start date
                    for date, group in chemo_meds.groupby('medication_start_date'):
                        if pd.notna(date):
                            date = pd.to_datetime(date, utc=True)
                            age_days = (date - self.birth_date).days

                            event = ClinicalEvent(
                                event_id=f"chemotherapy_{date.strftime('%Y%m%d')}",
                                event_type='treatment',
                                event_date=date,
                                age_at_event_days=age_days,
                                description=f"Chemotherapy started: {', '.join(group['medication_name'].tolist())}",
                                metadata={
                                    'treatment_type': 'chemotherapy',
                                    'medications': group['medication_name'].tolist()
                                }
                            )
                            events.append(event)

        return events

    def _find_matching_operative_notes(self, surgery_date: datetime) -> List[str]:
        """Find operative notes matching a surgery date"""
        binary_refs = []

        if 'binary_files' in self.data_sources and not self.data_sources['binary_files'].empty:
            op_notes = self.data_sources['binary_files'][
                self.data_sources['binary_files']['dr_type_text'].str.contains(
                    'OP Note|Operative', case=False, na=False
                )
            ]

            if not op_notes.empty and 'dr_date' in op_notes.columns:
                # Look for notes within 3 days of surgery
                surgery_date = pd.Timestamp(surgery_date)
                op_notes['dr_date'] = pd.to_datetime(op_notes['dr_date'], utc=True)
                date_matches = abs((op_notes['dr_date'] - surgery_date).dt.days) <= 3
                matching_notes = op_notes[date_matches]

                binary_refs = matching_notes['dr_id'].tolist() if 'dr_id' in matching_notes else []

        return binary_refs

    def _extract_relevant_snippet(self, text: str, keywords: List[str], context_chars: int = 100) -> str:
        """Extract relevant snippet from text around keywords"""
        text_lower = text.lower()

        for keyword in keywords:
            if keyword in text_lower:
                pos = text_lower.find(keyword)
                start = max(0, pos - context_chars)
                end = min(len(text), pos + len(keyword) + context_chars)
                return text[start:end]

        return text[:200]  # Return first 200 chars if no keyword found

    def _deduplicate_and_link_events(self, events: List[ClinicalEvent]) -> List[ClinicalEvent]:
        """Deduplicate events and link related ones"""
        # Group events by date and type
        event_dict = {}

        for event in events:
            key = (event.event_date.date(), event.event_type)

            if key not in event_dict:
                event_dict[key] = event
            else:
                # Merge information
                existing = event_dict[key]

                # Merge binary references
                existing.binary_references.extend(event.binary_references)
                existing.binary_references = list(set(existing.binary_references))

                # Merge imaging references
                existing.imaging_references.extend(event.imaging_references)
                existing.imaging_references = list(set(existing.imaging_references))

                # Update description if needed
                if event.description and event.description not in existing.description:
                    existing.description += f"; {event.description}"

                # Merge metadata
                existing.metadata.update(event.metadata)

        return list(event_dict.values())

    def _classify_event_types(self, events: List[ClinicalEvent]) -> List[ClinicalEvent]:
        """Classify events as initial vs progression vs recurrence"""
        if not events:
            return events

        # Find first surgery
        surgical_events = [e for e in events if e.event_type == 'surgery']

        if surgical_events:
            first_surgery = min(surgical_events, key=lambda x: x.event_date)

            # Check extent of resection from structured features
            has_gtr = self.structured_features.get('has_gross_total_resection', False)

            # Classify subsequent events
            for event in events:
                if event.event_date > first_surgery.event_date:
                    if event.event_type in ['progression', 'recurrence']:
                        # Already classified from imaging
                        continue
                    elif event.event_type == 'surgery':
                        # Classify based on previous surgery extent
                        if has_gtr:
                            event.metadata['classification'] = 'recurrence'
                        else:
                            event.metadata['classification'] = 'progression'

        return events

    def get_timeline_summary(self) -> Dict[str, any]:
        """Get summary of the clinical timeline"""
        summary = {
            'patient_id': self.patient_id,
            'total_events': len(self.events),
            'event_types': {}
        }

        # Count events by type
        for event in self.events:
            event_type = event.event_type
            if event_type not in summary['event_types']:
                summary['event_types'][event_type] = 0
            summary['event_types'][event_type] += 1

        # Date range
        if self.events:
            summary['first_event_date'] = min(e.event_date for e in self.events).isoformat()
            summary['last_event_date'] = max(e.event_date for e in self.events).isoformat()
            summary['timeline_duration_days'] = (
                max(e.event_date for e in self.events) - min(e.event_date for e in self.events)
            ).days

        # Key events
        surgical_events = [e for e in self.events if e.event_type == 'surgery']
        summary['total_surgeries'] = len(surgical_events)

        progression_events = [e for e in self.events if e.event_type == 'progression']
        summary['total_progressions'] = len(progression_events)

        return summary


if __name__ == "__main__":
    # Example usage - integrate with Phase 1
    from phase1_structured_harvester import StructuredDataHarvester

    staging_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files"

    # Phase 1: Harvest structured data
    harvester = StructuredDataHarvester(staging_path)
    structured_features = harvester.harvest_for_patient(
        patient_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
        birth_date="2005-05-13"
    )

    # Phase 2: Build timeline
    timeline_builder = ClinicalTimelineBuilder(staging_path, structured_features)
    timeline = timeline_builder.build_timeline(
        patient_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
        birth_date="2005-05-13"
    )

    # Print results
    print("\n" + "="*80)
    print("PHASE 2 RESULTS: Clinical Timeline")
    print("="*80)

    for event in timeline:
        print(f"\n{event.event_date.strftime('%Y-%m-%d')} (Day {event.age_at_event_days}): {event.event_type.upper()}")
        print(f"  Description: {event.description}")
        if event.binary_references:
            print(f"  Binary refs: {len(event.binary_references)} documents")
        if event.metadata:
            print(f"  Metadata: {event.metadata}")

    print("\n" + "="*80)
    print("TIMELINE SUMMARY")
    print("="*80)
    summary = timeline_builder.get_timeline_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")