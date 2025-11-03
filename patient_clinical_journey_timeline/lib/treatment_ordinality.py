#!/usr/bin/env python3
"""
Treatment Ordinality Post-Processing - Phase 2.5

This module implements post-processing logic to assign treatment ordinality
labels to timeline events after the initial timeline is constructed (Phase 2).

Treatment ordinality includes:
  - Surgery #1, #2, #3 (chronological order)
  - 1st-line chemotherapy, 2nd-line, 3rd-line (based on change_in_therapy_reason)
  - Radiation course #1, #2, #3 (chronological radiation episodes)
  - Timing labels: upfront, adjuvant, salvage, recurrence

This enables queries like:
  - "What was the first-line chemotherapy?"
  - "Did patient receive re-resection?"
  - "What was the salvage therapy after progression?"

Usage:
    from lib.treatment_ordinality import TreatmentOrdinalityProcessor

    processor = TreatmentOrdinalityProcessor(timeline_events)
    processor.assign_all_ordinality()

    # Timeline events now have 'relationships' field with:
    # - ordinality.surgery_number
    # - ordinality.treatment_line
    # - ordinality.radiation_course_number
    # - timing_context
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TreatmentOrdinalityProcessor:
    """
    Post-processes timeline to assign treatment ordinality labels.

    Attributes:
        timeline_events: List of timeline event dictionaries (modified in place)
    """

    def __init__(self, timeline_events: List[Dict]):
        """
        Initialize processor with timeline events.

        Args:
            timeline_events: List of event dictionaries (will be modified in place)
        """
        self.timeline_events = timeline_events

    def assign_all_ordinality(self) -> None:
        """
        Assign ordinality to all treatment events in timeline.

        This is the main entry point - calls all sub-methods to assign:
          - Surgery ordinality
          - Chemotherapy line ordinality
          - Radiation course ordinality
          - Timing context labels
        """
        logger.info("🔢 Assigning treatment ordinality to timeline events...")

        # Assign surgery ordinality
        self._assign_surgery_ordinality()

        # Assign chemotherapy line ordinality
        self._assign_chemotherapy_ordinality()

        # Assign radiation course ordinality
        self._assign_radiation_ordinality()

        # Assign timing context (upfront, adjuvant, salvage, etc.)
        self._assign_timing_context()

        logger.info("✅ Treatment ordinality assigned to all events")

    def _assign_surgery_ordinality(self) -> None:
        """
        Assign surgery_number to all surgery events (chronological order).

        Adds to each surgery event:
          relationships.ordinality.surgery_number = 1, 2, 3, ...
          relationships.ordinality.surgery_label = "Initial resection", "Re-resection #2", etc.
        """
        # Find all surgery events
        surgery_events = [e for e in self.timeline_events if e.get('event_type') == 'surgery']

        # Sort by date
        surgery_events.sort(key=lambda x: x.get('event_date', ''))

        # Assign ordinality
        for i, event in enumerate(surgery_events, 1):
            if 'relationships' not in event:
                event['relationships'] = {}
            if 'ordinality' not in event['relationships']:
                event['relationships']['ordinality'] = {}

            event['relationships']['ordinality']['surgery_number'] = i

            # Generate label
            if i == 1:
                label = "Initial resection"
            else:
                label = f"Re-resection #{i}"

            event['relationships']['ordinality']['surgery_label'] = label

        logger.info(f"  📊 Assigned surgery ordinality to {len(surgery_events)} surgeries")

    def _assign_chemotherapy_ordinality(self) -> None:
        """
        Assign treatment_line to chemotherapy episodes.

        Uses change_in_therapy_reason to detect line changes:
          - "disease_progression" → New line
          - "unacceptable_toxicity" → New line
          - "planned_protocol_change" → Same line (continuation)
          - null/missing → Continuation of previous line

        Adds to each chemo_start event:
          relationships.ordinality.treatment_line = 1, 2, 3, ...
          relationships.ordinality.line_label = "First-line", "Second-line", etc.
          relationships.ordinality.reason_for_change = "progression" | "toxicity" | null
        """
        # Find all chemo_start events
        chemo_events = [e for e in self.timeline_events
                       if e.get('event_type') == 'chemo_start']

        # Sort by date
        chemo_events.sort(key=lambda x: x.get('event_date', ''))

        current_line = 1
        for i, event in enumerate(chemo_events):
            # Check for line change reasons
            change_reason = event.get('change_in_therapy_reason')

            # Increment line if this is a change due to progression/toxicity
            if i > 0 and change_reason in ['disease_progression', 'unacceptable_toxicity']:
                current_line += 1

            # Assign ordinality
            if 'relationships' not in event:
                event['relationships'] = {}
            if 'ordinality' not in event['relationships']:
                event['relationships']['ordinality'] = {}

            event['relationships']['ordinality']['treatment_line'] = current_line

            # Generate label
            line_labels = {
                1: "First-line",
                2: "Second-line",
                3: "Third-line",
                4: "Fourth-line",
                5: "Fifth-line"
            }
            label = line_labels.get(current_line, f"{current_line}th-line")
            event['relationships']['ordinality']['line_label'] = label

            # Record reason for change (if applicable)
            if change_reason:
                event['relationships']['ordinality']['reason_for_change'] = {
                    'disease_progression': 'progression',
                    'unacceptable_toxicity': 'toxicity',
                    'completed_planned_treatment': 'protocol_completion',
                    'patient_preference': 'patient_choice'
                }.get(change_reason, change_reason)

        logger.info(f"  📊 Assigned chemotherapy lines to {len(chemo_events)} episodes ({current_line} lines total)")

    def _assign_radiation_ordinality(self) -> None:
        """
        Assign radiation_course_number to radiation episodes.

        Groups radiation_start/radiation_end events into courses and assigns:
          relationships.ordinality.radiation_course_number = 1, 2, 3, ...
          relationships.ordinality.course_label = "Initial radiation", "Re-irradiation #2", etc.
        """
        # Find all radiation_start events
        radiation_events = [e for e in self.timeline_events
                           if e.get('event_type') in ['radiation_start', 'radiation_end']]

        # Sort by date
        radiation_events.sort(key=lambda x: x.get('event_date', ''))

        # Group into courses (radiation_start + radiation_end pairs)
        course_number = 0
        in_course = False

        for event in radiation_events:
            if event.get('event_type') == 'radiation_start':
                course_number += 1
                in_course = True

            if in_course:
                # Assign ordinality to both start and end events
                if 'relationships' not in event:
                    event['relationships'] = {}
                if 'ordinality' not in event['relationships']:
                    event['relationships']['ordinality'] = {}

                event['relationships']['ordinality']['radiation_course_number'] = course_number

                # Generate label
                if course_number == 1:
                    label = "Initial radiation"
                else:
                    label = f"Re-irradiation #{course_number}"

                event['relationships']['ordinality']['course_label'] = label

            if event.get('event_type') == 'radiation_end':
                in_course = False

        logger.info(f"  📊 Assigned radiation courses to {len(radiation_events)} events ({course_number} courses total)")

    def _assign_timing_context(self) -> None:
        """
        Assign timing context labels to treatment events.

        Timing context:
          - upfront: Treatment before first surgery
          - adjuvant: Treatment after complete resection (GTR/NTR)
          - salvage: Treatment after progression/recurrence
          - concurrent: Treatment happening during same timeframe as another modality
          - maintenance: Ongoing treatment after initial therapy

        This provides clinical context for treatment intent.
        """
        # Find key milestone events
        first_surgery = None
        first_progression = None
        # Null-safe sorting: None values go to end
        for event in sorted(self.timeline_events, key=lambda x: (x.get('event_date') is None, x.get('event_date', ''))):
            if event.get('event_type') == 'surgery' and not first_surgery:
                first_surgery = event
            if event.get('diagnosis_interpretation') == 'progression' and not first_progression:
                first_progression = event

        # Assign timing context to chemotherapy
        for event in self.timeline_events:
            if event.get('event_type') == 'chemo_start':
                timing = self._determine_chemo_timing(event, first_surgery, first_progression)
                if timing:
                    if 'relationships' not in event:
                        event['relationships'] = {}
                    event['relationships']['timing_context'] = timing

            # Assign timing context to radiation
            if event.get('event_type') == 'radiation_start':
                timing = self._determine_radiation_timing(event, first_surgery, first_progression)
                if timing:
                    if 'relationships' not in event:
                        event['relationships'] = {}
                    event['relationships']['timing_context'] = timing

        logger.info("  📊 Assigned timing context to treatment events")

    def _determine_chemo_timing(self,
                                chemo_event: Dict,
                                first_surgery: Optional[Dict],
                                first_progression: Optional[Dict]) -> Optional[str]:
        """
        Determine timing context for chemotherapy event.

        Args:
            chemo_event: Chemotherapy start event
            first_surgery: First surgery event (if any)
            first_progression: First progression event (if any)

        Returns:
            Timing context string or None
        """
        chemo_date = chemo_event.get('event_date')
        if not chemo_date:
            return None

        # Check if before first surgery
        if first_surgery and chemo_date < first_surgery.get('event_date', ''):
            return "upfront"

        # Check if after progression
        if first_progression and chemo_date > first_progression.get('event_date', ''):
            return "salvage"

        # Check change reason
        change_reason = chemo_event.get('change_in_therapy_reason')
        if change_reason == 'disease_progression':
            return "salvage"

        # Check if treatment line > 1
        treatment_line = chemo_event.get('relationships', {}).get('ordinality', {}).get('treatment_line')
        if treatment_line and treatment_line > 1:
            return "salvage"

        # Default to adjuvant if after surgery
        if first_surgery and chemo_date > first_surgery.get('event_date', ''):
            return "adjuvant"

        return None

    def _determine_radiation_timing(self,
                                    radiation_event: Dict,
                                    first_surgery: Optional[Dict],
                                    first_progression: Optional[Dict]) -> Optional[str]:
        """
        Determine timing context for radiation event.

        Args:
            radiation_event: Radiation start event
            first_surgery: First surgery event (if any)
            first_progression: First progression event (if any)

        Returns:
            Timing context string or None
        """
        rad_date = radiation_event.get('event_date')
        if not rad_date:
            return None

        # Check if before first surgery
        if first_surgery and rad_date < first_surgery.get('event_date', ''):
            return "upfront"

        # Check if after progression
        if first_progression and rad_date > first_progression.get('event_date', ''):
            return "salvage"

        # Check radiation course number
        course_number = radiation_event.get('relationships', {}).get('ordinality', {}).get('radiation_course_number')
        if course_number and course_number > 1:
            return "salvage"

        # Default to adjuvant if after surgery
        if first_surgery and rad_date > first_surgery.get('event_date', ''):
            return "adjuvant"

        return None

    def get_treatment_summary(self) -> Dict:
        """
        Generate summary of treatment ordinality for the patient.

        Returns:
            Dictionary with summary statistics:
              - total_surgeries
              - total_chemo_lines
              - total_radiation_courses
              - upfront_treatments
              - salvage_treatments
        """
        summary = {
            'total_surgeries': 0,
            'total_chemo_lines': 0,
            'total_radiation_courses': 0,
            'upfront_treatments': 0,
            'adjuvant_treatments': 0,
            'salvage_treatments': 0
        }

        # Count surgeries
        surgeries = [e for e in self.timeline_events if e.get('event_type') == 'surgery']
        summary['total_surgeries'] = len(surgeries)

        # Count chemo lines (max line number)
        chemo_lines = [e.get('relationships', {}).get('ordinality', {}).get('treatment_line', 0)
                      for e in self.timeline_events if e.get('event_type') == 'chemo_start']
        summary['total_chemo_lines'] = max(chemo_lines) if chemo_lines else 0

        # Count radiation courses (max course number)
        rad_courses = [e.get('relationships', {}).get('ordinality', {}).get('radiation_course_number', 0)
                      for e in self.timeline_events if e.get('event_type') == 'radiation_start']
        summary['total_radiation_courses'] = max(rad_courses) if rad_courses else 0

        # Count timing contexts
        for event in self.timeline_events:
            timing = event.get('relationships', {}).get('timing_context')
            if timing == 'upfront':
                summary['upfront_treatments'] += 1
            elif timing == 'adjuvant':
                summary['adjuvant_treatments'] += 1
            elif timing == 'salvage':
                summary['salvage_treatments'] += 1

        return summary
