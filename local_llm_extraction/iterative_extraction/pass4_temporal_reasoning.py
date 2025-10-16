"""
Pass 4: Temporal Reasoning and Clinical Plausibility
Validate extracted values against clinical timeline
"""
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
from .extraction_result import PassResult, ExtractionResult
import pandas as pd

logger = logging.getLogger(__name__)

class TemporalReasoner:
    """Apply temporal reasoning and clinical plausibility checks"""

    def __init__(self, phase1_data: Dict, phase2_timeline: List, patient_age_at_event: int):
        self.phase1_data = phase1_data or {}
        self.phase2_timeline = phase2_timeline or []
        self.patient_age = patient_age_at_event  # Age in days

    def validate(self, variable: str, event_date: str, extraction_result: ExtractionResult) -> PassResult:
        """
        Apply temporal reasoning to validate extraction
        """
        result = PassResult(pass_number=4, method='temporal_reasoning')

        value = extraction_result.final_value or extraction_result.get_all_candidates()[0].value if extraction_result.get_all_candidates() else None

        if not value or value in ['Not found', 'No confident extractions']:
            result.add_note("No value to validate")
            result.confidence_adjustment = 1.0
            return result

        # Parse event date
        try:
            event_dt = pd.to_datetime(event_date)
        except:
            logger.error(f"Could not parse event date: {event_date}")
            result.confidence_adjustment = 1.0
            return result

        # Route to variable-specific temporal validation
        validators = {
            'extent_of_tumor_resection': self._validate_extent_temporal,
            'histopathology': self._validate_histology_temporal,
            'tumor_location': self._validate_location_temporal,
            'who_grade': self._validate_grade_temporal,
            'surgery_type': self._validate_surgery_type_temporal
        }

        validator = validators.get(variable, self._validate_generic)
        result = validator(value, event_dt, result)

        return result

    def _validate_extent_temporal(self, value: str, event_dt: datetime, result: PassResult) -> PassResult:
        """Validate extent of resection against temporal patterns"""

        # Check surgical pattern
        surgeries_within_30days = [e for e in self.phase2_timeline
                                   if e.event_type == 'surgical'
                                   and abs((e.event_date - event_dt).days) <= 30]

        if len(surgeries_within_30days) > 2:
            if value == 'GTR':
                result.add_flag('unlikely_gtr', f'{len(surgeries_within_30days)} surgeries in 30 days suggests incomplete resection')
                result.confidence_adjustment = 0.6
                result.add_note(f"GTR unlikely: {len(surgeries_within_30days)} surgeries within 30 days")
            elif value in ['STR', 'Partial']:
                result.add_flag('consistent_with_multiple_surgeries', True)
                result.confidence_adjustment = 1.1
                result.add_note(f"STR/Partial consistent with {len(surgeries_within_30days)} surgeries")

        # Check for post-op radiation (suggests residual tumor)
        radiation_within_90days = [e for e in self.phase2_timeline
                                   if 'radiation' in str(e.event_type).lower()
                                   and (e.event_date - event_dt).days > 0
                                   and (e.event_date - event_dt).days <= 90]

        if radiation_within_90days:
            if value == 'GTR':
                result.add_flag('radiation_suggests_residual', 'Post-op radiation rare after GTR')
                result.confidence_adjustment = 0.7
                result.add_note("Post-op radiation within 90 days suggests residual tumor")
            elif value in ['STR', 'Partial']:
                result.add_flag('radiation_consistent', 'Post-op radiation consistent with incomplete resection')
                result.confidence_adjustment = 1.1

        # Check for post-op chemotherapy (suggests residual or high-grade)
        chemo_within_60days = [e for e in self.phase2_timeline
                              if 'chemo' in str(e.event_type).lower()
                              and (e.event_date - event_dt).days > 0
                              and (e.event_date - event_dt).days <= 60]

        if chemo_within_60days:
            if value == 'GTR':
                result.add_note("Early post-op chemotherapy unusual for GTR (unless high-grade tumor)")
            elif value in ['STR', 'Partial', 'Biopsy only']:
                result.add_flag('chemo_consistent', 'Post-op chemotherapy consistent with residual')
                result.confidence_adjustment = 1.05

        return result

    def _validate_histology_temporal(self, value: str, event_dt: datetime, result: PassResult) -> PassResult:
        """Validate histopathology against temporal patterns"""

        # Check for diagnosis progression (transformation)
        prior_diagnoses = [e for e in self.phase2_timeline
                          if e.event_type == 'diagnosis'
                          and e.event_date < event_dt]

        if value and 'glioblastoma' in value.lower():
            # GBM is Grade IV - check if patient had prior low-grade diagnosis
            has_prior_low_grade = any(
                'grade i' in str(e.description).lower() or
                'pilocytic' in str(e.description).lower() or
                'grade ii' in str(e.description).lower()
                for e in prior_diagnoses
            )

            if has_prior_low_grade:
                # Check time gap
                earliest_low_grade = min([e.event_date for e in prior_diagnoses
                                         if 'grade i' in str(e.description).lower() or
                                         'pilocytic' in str(e.description).lower()])
                years_gap = (event_dt - earliest_low_grade).days / 365.25

                if years_gap >= 2:
                    result.add_flag('tumor_transformation', f'Likely transformation from low-grade after {years_gap:.1f} years')
                    result.add_note(f"Clinical pattern consistent with malignant transformation")
                    result.confidence_adjustment = 1.1

        # Age-appropriate histology check
        age_years = self.patient_age / 365.25

        if age_years < 18:  # Pediatric
            pediatric_tumors = ['pilocytic astrocytoma', 'medulloblastoma', 'ependymoma',
                              'atrt', 'craniopharyngioma', 'dipg']

            if any(tumor in value.lower() for tumor in pediatric_tumors):
                result.add_flag('age_appropriate', f'Tumor type common in pediatric patients')
                result.confidence_adjustment = 1.05
            elif 'glioblastoma' in value.lower():
                result.add_flag('age_unusual', 'GBM less common in pediatrics (but can occur in adolescents)')
                if age_years < 10:
                    result.confidence_adjustment = 0.9

        return result

    def _validate_location_temporal(self, value: str, event_dt: datetime, result: PassResult) -> PassResult:
        """Validate tumor location against temporal patterns"""

        # Check consistency across imaging studies
        imaging_events = [e for e in self.phase2_timeline
                         if 'imaging' in str(e.event_type).lower()
                         and e.event_date <= event_dt]

        if imaging_events:
            # In real implementation, would parse imaging findings for anatomical mentions
            # For now, just note that imaging history exists
            result.add_note(f"{len(imaging_events)} imaging studies available for location validation")

        # Check if location is consistent with surgical approach
        if 'cerebellum' in value.lower() or 'posterior fossa' in value.lower():
            # Check for suboccipital craniotomy mentions
            surgery_events = [e for e in self.phase2_timeline
                            if e.event_type == 'surgical'
                            and abs((e.event_date - event_dt).days) <= 1]

            for surg in surgery_events:
                if 'suboccipital' in str(surg.description).lower() or 'posterior fossa' in str(surg.description).lower():
                    result.add_flag('surgical_approach_consistent', 'Suboccipital approach confirms posterior fossa location')
                    result.confidence_adjustment = 1.15

        # Location should not change over time (unless metastatic)
        # This would require more sophisticated tracking in real implementation
        result.add_note("Location consistency check across timeline - not yet implemented")

        return result

    def _validate_grade_temporal(self, value: str, event_dt: datetime, result: PassResult) -> PassResult:
        """Validate WHO grade against temporal patterns"""

        # Check for grade progression
        prior_events = [e for e in self.phase2_timeline
                       if e.event_date < event_dt]

        if value in ['Grade III', 'Grade IV']:
            # High grade - check for prior low-grade diagnosis
            has_prior_low_grade = any('grade i' in str(e.description).lower() or
                                     'grade ii' in str(e.description).lower()
                                     for e in prior_events)

            if has_prior_low_grade:
                result.add_flag('grade_progression', 'Progression from low-grade to high-grade')
                result.add_note("Malignant transformation pattern detected")

        # Check if grade matches treatment intensity
        radiation_events = [e for e in self.phase2_timeline
                           if 'radiation' in str(e.event_type).lower()
                           and (e.event_date - event_dt).days >= 0
                           and (e.event_date - event_dt).days <= 90]

        chemo_events = [e for e in self.phase2_timeline
                       if 'chemo' in str(e.event_type).lower()
                       and (e.event_date - event_dt).days >= 0
                       and (e.event_date - event_dt).days <= 90]

        if value in ['Grade I', 'Grade II']:
            if radiation_events or chemo_events:
                result.add_note("Low-grade tumor with aggressive treatment - may indicate high-risk features")
        elif value in ['Grade III', 'Grade IV']:
            if not radiation_events and not chemo_events:
                # Check if this is within observation period
                recent_surgeries = [e for e in self.phase2_timeline
                                  if e.event_type == 'surgical'
                                  and (e.event_date - event_dt).days > 0
                                  and (e.event_date - event_dt).days <= 180]

                if not recent_surgeries:
                    result.add_flag('treatment_mismatch', 'High-grade tumor without adjuvant therapy (unusual)')

        return result

    def _validate_surgery_type_temporal(self, value: str, event_dt: datetime, result: PassResult) -> PassResult:
        """Validate surgery type against temporal patterns"""

        # Check for shunt procedures associated with hydrocephalus
        if 'shunt' in value.lower() or 'ventriculostomy' in value.lower():
            # Look for prior imaging showing hydrocephalus
            result.add_note("Shunt procedure - check for hydrocephalus in imaging")

        # Check for staged procedures
        surgeries_within_7days = [e for e in self.phase2_timeline
                                 if e.event_type == 'surgical'
                                 and abs((e.event_date - event_dt).days) <= 7
                                 and e.event_date != event_dt]

        if surgeries_within_7days:
            result.add_flag('staged_procedure', f'Part of staged surgery series ({len(surgeries_within_7days) + 1} surgeries in 7 days)')
            result.add_note(f"Staged surgical approach - {len(surgeries_within_7days) + 1} procedures within a week")

        return result

    def _validate_generic(self, value: str, event_dt: datetime, result: PassResult) -> PassResult:
        """Generic temporal validation"""
        result.add_note("No specific temporal validation rules for this variable")
        result.confidence_adjustment = 1.0
        return result
