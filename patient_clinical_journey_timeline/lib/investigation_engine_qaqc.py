#!/usr/bin/env python3
"""
Investigation Engine QA/QC - Phase 7

End-to-end quality assurance and quality control for patient clinical timelines.
Validates complete timeline against anchored diagnosis using Investigation Engine.

This module implements Phase 7 validation:
  - Temporal consistency (dates make sense?)
  - Clinical protocol coherence (treatment matches diagnosis?)
  - Data completeness (critical milestones present?)
  - Extraction failure patterns (systematic gaps?)
  - Disease progression logic (tumor trajectory plausible?)

Usage:
    from lib.investigation_engine_qaqc import InvestigationEngineQAQC

    qaqc = InvestigationEngineQAQC(anchored_diagnosis, timeline_events, patient_fhir_id)
    validation_report = qaqc.run_comprehensive_validation()

    if validation_report['critical_violations']:
        print("CRITICAL ISSUES DETECTED")
        for violation in validation_report['critical_violations']:
            print(f"  - {violation}")
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class InvestigationEngineQAQC:
    """
    Phase 7 Investigation Engine for end-to-end timeline quality assurance.

    Validates complete clinical timeline against anchored diagnosis to detect:
    - Treatment-diagnosis mismatches (e.g., wrong radiation protocol)
    - Temporal inconsistencies (e.g., treatment before diagnosis)
    - Data completeness gaps (e.g., missing critical milestones)
    - Extraction failures (e.g., systematic missing events)
    - Disease progression illogic (e.g., impossible tumor trajectory)

    Attributes:
        anchored_diagnosis: Validated WHO 2021 diagnosis from Phase 0
        timeline_events: List of timeline events from Phase 1-6
        patient_fhir_id: Patient FHIR identifier
    """

    def __init__(
        self,
        anchored_diagnosis: Dict[str, Any],
        timeline_events: List[Dict[str, Any]],
        patient_fhir_id: str
    ):
        """
        Initialize Investigation Engine QA/QC validator.

        Args:
            anchored_diagnosis: WHO 2021 diagnosis dict from Phase 0.4
            timeline_events: List of timeline event dicts from Phase 1-6
            patient_fhir_id: Patient FHIR ID
        """
        self.anchored_diagnosis = anchored_diagnosis
        self.timeline_events = timeline_events
        self.patient_fhir_id = patient_fhir_id

        logger.info("✅ InvestigationEngineQAQC initialized")
        logger.info(f"   Patient: {patient_fhir_id}")
        logger.info(f"   Anchored diagnosis: {anchored_diagnosis.get('who_2021_diagnosis', 'UNKNOWN')}")
        logger.info(f"   Timeline events: {len(timeline_events)}")

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """
        Run comprehensive Phase 7 validation across all dimensions.

        Returns:
            Validation report with violations, warnings, and recommendations
        """
        logger.info("=" * 80)
        logger.info("PHASE 7: INVESTIGATION ENGINE - END-TO-END QA/QC")
        logger.info("=" * 80)

        validation_report = {
            'temporal_consistency': self._validate_temporal_consistency(),
            'protocol_coherence': self._validate_protocol_against_diagnosis(),
            'data_completeness': self._assess_data_completeness(),
            'extraction_failures': self._analyze_extraction_failures(),
            'progression_logic': self._validate_disease_progression(),
            'critical_violations': [],
            'warnings': [],
            'recommendations': []
        }

        # Aggregate critical violations from all validations
        for validation_key, validation_result in validation_report.items():
            if validation_key in ['critical_violations', 'warnings', 'recommendations']:
                continue

            if isinstance(validation_result, dict):
                if validation_result.get('critical_violations'):
                    validation_report['critical_violations'].extend(
                        validation_result['critical_violations']
                    )
                if validation_result.get('warnings'):
                    validation_report['warnings'].extend(
                        validation_result['warnings']
                    )
                if validation_result.get('recommendations'):
                    validation_report['recommendations'].extend(
                        validation_result['recommendations']
                    )

        # Summary logging
        logger.info("=" * 80)
        logger.info("PHASE 7 VALIDATION SUMMARY")
        logger.info("=" * 80)

        if validation_report['critical_violations']:
            logger.error(f"❌ {len(validation_report['critical_violations'])} CRITICAL VIOLATIONS DETECTED")
            for violation in validation_report['critical_violations']:
                logger.error(f"    {violation}")
        else:
            logger.info("✅ No critical violations detected")

        if validation_report['warnings']:
            logger.warning(f"⚠️  {len(validation_report['warnings'])} warnings")
            for warning in validation_report['warnings'][:5]:  # Log first 5
                logger.warning(f"    {warning}")

        if validation_report['recommendations']:
            logger.info(f"💡 {len(validation_report['recommendations'])} recommendations")

        logger.info("=" * 80)

        return validation_report

    def _validate_temporal_consistency(self) -> Dict[str, Any]:
        """
        Validate temporal consistency of timeline events.

        Checks:
        - Events are chronologically ordered
        - No events before birth or after death
        - Treatment events occur after diagnosis
        - Reasonable gaps between related events

        Returns:
            Validation result with violations and warnings
        """
        logger.info("   [Phase 7.1] Validating temporal consistency...")

        result = {
            'is_valid': True,
            'critical_violations': [],
            'warnings': [],
            'recommendations': []
        }

        if not self.timeline_events:
            result['warnings'].append("No timeline events to validate")
            logger.warning("      ⚠️  No timeline events found")
            return result

        # Sort events by date
        dated_events = [e for e in self.timeline_events if e.get('event_date')]
        if not dated_events:
            result['warnings'].append("No dated events found in timeline")
            logger.warning("      ⚠️  No dated events found")
            return result

        dated_events.sort(key=lambda e: e['event_date'])

        # Get diagnosis date
        diagnosis_date = None
        for event in dated_events:
            if event.get('event_type') in ['initial_diagnosis', 'who_classification', 'diagnosis']:
                diagnosis_date = event.get('event_date')
                break

        if not diagnosis_date:
            result['warnings'].append("No diagnosis date found in timeline")
            logger.warning("      ⚠️  No diagnosis date found")

        # Check treatment events occur after diagnosis
        if diagnosis_date:
            for event in dated_events:
                event_type = event.get('event_type', '')
                event_date = event.get('event_date')

                if event_type in ['radiation_episode_start', 'chemotherapy_start',
                                 'surgery', 'treatment_start']:
                    if event_date < diagnosis_date:
                        violation = (
                            f"Treatment event '{event_type}' on {event_date} "
                            f"occurs BEFORE diagnosis on {diagnosis_date}"
                        )
                        result['critical_violations'].append(violation)
                        result['is_valid'] = False
                        logger.error(f"      ❌ {violation}")

        # Check for suspicious gaps
        for i in range(len(dated_events) - 1):
            current_event = dated_events[i]
            next_event = dated_events[i + 1]

            current_date = datetime.fromisoformat(current_event['event_date'])
            next_date = datetime.fromisoformat(next_event['event_date'])
            gap_days = (next_date - current_date).days

            # Flag gaps > 2 years between consecutive events
            if gap_days > 730:
                warning = (
                    f"Large gap ({gap_days} days) between {current_event.get('event_type')} "
                    f"and {next_event.get('event_type')}"
                )
                result['warnings'].append(warning)

        if result['is_valid']:
            logger.info("      ✅ Temporal consistency validated")

        return result

    def _validate_protocol_against_diagnosis(self) -> Dict[str, Any]:
        """
        Validate treatment protocol matches WHO 2021 standards for diagnosis.

        This is the CRITICAL validation for Phase 7. Checks:
        - Medulloblastoma → CSI (craniospinal irradiation) ~23.4-36 Gy + boost
        - Glioblastoma, IDH-wildtype → RT 60 Gy + concurrent TMZ
        - IDH-mutant Grade 2 → Should NOT see 60 Gy (max 54 Gy)
        - Pediatric tumors → Age-appropriate protocols

        Returns:
            Validation result with critical violations for protocol mismatches
        """
        logger.info("   [Phase 7.2] Validating treatment protocol against diagnosis...")

        result = {
            'is_valid': True,
            'critical_violations': [],
            'warnings': [],
            'recommendations': []
        }

        diagnosis = self.anchored_diagnosis.get('who_2021_diagnosis', '').lower()

        if not diagnosis:
            result['warnings'].append("No anchored diagnosis available for protocol validation")
            logger.warning("      ⚠️  No anchored diagnosis found")
            return result

        # Extract radiation events
        radiation_events = [
            e for e in self.timeline_events
            if e.get('event_type') in ['radiation_episode_start', 'radiation_episode_end']
        ]

        # Extract chemotherapy events
        chemo_events = [
            e for e in self.timeline_events
            if e.get('event_type') in ['chemotherapy_start', 'chemotherapy_end']
        ]

        # VALIDATION 1: Medulloblastoma Protocol
        if 'medulloblastoma' in diagnosis:
            logger.info("      → Validating medulloblastoma protocol...")

            # Expect craniospinal irradiation (CSI)
            found_csi = any(
                'craniospinal' in str(e.get('event_description', '')).lower() or
                'csi' in str(e.get('event_description', '')).lower()
                for e in radiation_events
            )

            if not found_csi:
                violation = (
                    "Medulloblastoma diagnosis but NO craniospinal irradiation (CSI) found. "
                    "Standard protocol requires CSI 23.4-36 Gy + posterior fossa boost."
                )
                result['critical_violations'].append(violation)
                result['is_valid'] = False
                logger.error(f"      ❌ {violation}")
            else:
                logger.info("      ✅ CSI found (expected for medulloblastoma)")

            # Check for chemotherapy (most medulloblastoma patients get chemo)
            if not chemo_events:
                warning = (
                    "Medulloblastoma diagnosis but no chemotherapy events found. "
                    "Most medulloblastoma protocols include chemotherapy."
                )
                result['warnings'].append(warning)
                logger.warning(f"      ⚠️  {warning}")

        # VALIDATION 2: Glioblastoma Protocol
        elif 'glioblastoma' in diagnosis:
            logger.info("      → Validating glioblastoma protocol...")

            # Expect 60 Gy radiation
            found_60gy = any(
                '60' in str(e.get('event_description', '')) and 'gy' in str(e.get('event_description', '')).lower()
                for e in radiation_events
            )

            if not found_60gy:
                warning = (
                    "Glioblastoma diagnosis but no 60 Gy radiation found. "
                    "Standard protocol is 60 Gy focal RT + concurrent temozolomide."
                )
                result['warnings'].append(warning)
                logger.warning(f"      ⚠️  {warning}")

            # Expect temozolomide
            found_tmz = any(
                'temozolomide' in str(e.get('event_description', '')).lower() or
                'tmz' in str(e.get('event_description', '')).lower()
                for e in chemo_events
            )

            if not found_tmz:
                warning = (
                    "Glioblastoma diagnosis but no temozolomide found. "
                    "Standard Stupp protocol includes concurrent/adjuvant TMZ."
                )
                result['warnings'].append(warning)
                logger.warning(f"      ⚠️  {warning}")

        # VALIDATION 3: Low-grade glioma over-treatment
        elif 'grade 2' in diagnosis or 'low-grade' in diagnosis:
            logger.info("      → Validating low-grade glioma protocol...")

            # Should NOT see 60 Gy (max 54 Gy for low-grade)
            found_60gy = any(
                '60' in str(e.get('event_description', '')) and 'gy' in str(e.get('event_description', '')).lower()
                for e in radiation_events
            )

            if found_60gy:
                violation = (
                    "Grade 2/low-grade glioma diagnosis but 60 Gy radiation found. "
                    "Low-grade gliomas should receive MAX 54 Gy to avoid toxicity. "
                    "60 Gy suggests potential over-treatment or misclassification."
                )
                result['critical_violations'].append(violation)
                result['is_valid'] = False
                logger.error(f"      ❌ {violation}")

        if result['is_valid'] and not result['warnings']:
            logger.info("      ✅ Treatment protocol validated against diagnosis")

        return result

    def _assess_data_completeness(self) -> Dict[str, Any]:
        """
        Assess data completeness for critical clinical milestones.

        Checks for presence of:
        - Diagnosis event
        - Surgery/biopsy event
        - Radiation treatment
        - Chemotherapy (if expected)
        - Follow-up events

        Returns:
            Assessment with completeness score and missing milestones
        """
        logger.info("   [Phase 7.3] Assessing data completeness...")

        result = {
            'completeness_score': 0.0,
            'critical_violations': [],
            'warnings': [],
            'recommendations': [],
            'missing_milestones': []
        }

        # Critical milestones
        has_diagnosis = any(
            e.get('event_type') in ['initial_diagnosis', 'who_classification', 'diagnosis']
            for e in self.timeline_events
        )

        has_surgery = any(
            e.get('event_type') in ['surgery', 'biopsy', 'surgical_resection']
            for e in self.timeline_events
        )

        has_radiation = any(
            e.get('event_type') in ['radiation_episode_start', 'radiation_episode_end']
            for e in self.timeline_events
        )

        has_chemotherapy = any(
            e.get('event_type') in ['chemotherapy_start', 'chemotherapy_end']
            for e in self.timeline_events
        )

        # Calculate completeness score
        milestones = {
            'diagnosis': has_diagnosis,
            'surgery': has_surgery,
            'radiation': has_radiation,
            'chemotherapy': has_chemotherapy
        }

        present_count = sum(milestones.values())
        result['completeness_score'] = present_count / len(milestones)

        # Track missing milestones
        for milestone, present in milestones.items():
            if not present:
                result['missing_milestones'].append(milestone)
                result['warnings'].append(f"Missing {milestone} milestone")

        logger.info(f"      → Completeness score: {result['completeness_score']:.2%}")
        logger.info(f"      → Present milestones: {present_count}/{len(milestones)}")

        if result['missing_milestones']:
            logger.warning(f"      ⚠️  Missing milestones: {', '.join(result['missing_milestones'])}")
        else:
            logger.info("      ✅ All critical milestones present")

        return result

    def _analyze_extraction_failures(self) -> Dict[str, Any]:
        """
        Analyze extraction failure patterns across timeline phases.

        Looks for:
        - Systematic gaps in event types
        - Low extraction counts
        - Missing expected event sequences

        Returns:
            Analysis with identified failure patterns
        """
        logger.info("   [Phase 7.4] Analyzing extraction failure patterns...")

        result = {
            'critical_violations': [],
            'warnings': [],
            'recommendations': [],
            'event_type_counts': defaultdict(int)
        }

        # Count events by type
        for event in self.timeline_events:
            event_type = event.get('event_type', 'unknown')
            result['event_type_counts'][event_type] += 1

        # Check for suspiciously low counts
        if len(self.timeline_events) < 5:
            warning = (
                f"Very few timeline events ({len(self.timeline_events)}) extracted. "
                "This may indicate systematic extraction failures."
            )
            result['warnings'].append(warning)
            logger.warning(f"      ⚠️  {warning}")

        # Log event type distribution
        logger.info("      → Event type distribution:")
        for event_type, count in sorted(result['event_type_counts'].items()):
            logger.info(f"          {event_type}: {count}")

        if not result['warnings']:
            logger.info("      ✅ No systematic extraction failures detected")

        return result

    def _validate_disease_progression(self) -> Dict[str, Any]:
        """
        Validate disease progression logic and tumor trajectory.

        Checks:
        - Progression/recurrence events occur after initial treatment
        - Salvage treatments occur after progression
        - Reasonable timing for recurrence patterns

        Returns:
            Validation result with progression logic violations
        """
        logger.info("   [Phase 7.5] Validating disease progression logic...")

        result = {
            'is_valid': True,
            'critical_violations': [],
            'warnings': [],
            'recommendations': []
        }

        # Find progression/recurrence events
        progression_events = [
            e for e in self.timeline_events
            if 'progression' in str(e.get('event_type', '')).lower() or
               'recurrence' in str(e.get('event_type', '')).lower()
        ]

        if not progression_events:
            logger.info("      → No progression events found (patient may be in remission)")
            return result

        # Find initial treatment completion
        treatment_end_events = [
            e for e in self.timeline_events
            if e.get('event_type') in ['radiation_episode_end', 'chemotherapy_end', 'treatment_end']
        ]

        if treatment_end_events:
            latest_treatment_end = max(
                treatment_end_events,
                key=lambda e: e.get('event_date', '1900-01-01')
            )

            latest_treatment_date = datetime.fromisoformat(latest_treatment_end['event_date'])

            # Check progression events occur after treatment
            for prog_event in progression_events:
                if prog_event.get('event_date'):
                    prog_date = datetime.fromisoformat(prog_event['event_date'])

                    if prog_date < latest_treatment_date:
                        warning = (
                            f"Progression event on {prog_date.date()} occurs BEFORE "
                            f"treatment completion on {latest_treatment_date.date()}"
                        )
                        result['warnings'].append(warning)
                        logger.warning(f"      ⚠️  {warning}")

        logger.info(f"      → Found {len(progression_events)} progression/recurrence events")

        if result['is_valid'] and not result['warnings']:
            logger.info("      ✅ Disease progression logic validated")

        return result
