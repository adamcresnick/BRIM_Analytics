"""
Progress Note Prioritization for Clinical Event Context

Prioritizes progress notes based on clinical significance:
1. Notes immediately after surgeries (±7 days)
2. Notes immediately after imaging events (±7 days)
3. Notes after chemotherapy changes (start/stop drug)
4. Final progress note available

This reduces the number of progress notes to review while capturing
the most clinically relevant disease state assessments.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PrioritizedNote:
    """A progress note with priority context"""
    note: Dict[str, Any]
    priority_reason: str
    related_event_id: Optional[str] = None
    related_event_type: Optional[str] = None
    related_event_date: Optional[datetime] = None
    days_from_event: Optional[int] = None


class ProgressNotePrioritizer:
    """
    Prioritizes progress notes based on proximity to key clinical events.

    Strategy:
    - Post-surgery notes: Capture disease state assessment after intervention
    - Post-imaging notes: Capture clinical interpretation of imaging findings
    - Post-chemo-change notes: Capture treatment response assessment
    - Final note: Capture most recent disease state
    """

    def __init__(
        self,
        post_event_window_days: int = 7,
        include_final_note: bool = True
    ):
        """
        Initialize prioritizer

        Args:
            post_event_window_days: Days after event to look for notes (default 7)
            include_final_note: Always include most recent note (default True)
        """
        self.post_event_window_days = post_event_window_days
        self.include_final_note = include_final_note

    def prioritize_notes(
        self,
        progress_notes: List[Dict[str, Any]],
        surgeries: List[Dict[str, Any]],
        imaging_events: List[Dict[str, Any]],
        medication_changes: Optional[List[Dict[str, Any]]] = None
    ) -> List[PrioritizedNote]:
        """
        Prioritize progress notes based on clinical events

        Args:
            progress_notes: List of progress note records (from v_binary_files)
            surgeries: List of surgery records (from v_procedures_tumor)
            imaging_events: List of imaging records (from v_imaging)
            medication_changes: Optional list of medication change events

        Returns:
            List of PrioritizedNote objects, sorted by date
        """
        prioritized = []
        note_ids_seen = set()

        # Parse dates for all notes
        notes_with_dates = []
        for note in progress_notes:
            try:
                note_date = self._parse_date(note.get('dr_date'))
                if note_date:
                    notes_with_dates.append((note, note_date))
            except Exception as e:
                logger.warning(f"Could not parse note date: {e}")
                continue

        # Sort notes by date
        notes_with_dates.sort(key=lambda x: x[1])

        logger.info(f"Prioritizing {len(notes_with_dates)} progress notes based on clinical events")

        # 1. Notes after surgeries
        for surgery in surgeries:
            try:
                surgery_date = self._parse_date(surgery.get('proc_performed_date_time'))
                if not surgery_date:
                    continue

                # Find first note after surgery (within window)
                post_surgery_note = self._find_first_note_after_event(
                    notes_with_dates,
                    surgery_date,
                    self.post_event_window_days
                )

                if post_surgery_note and post_surgery_note['note'].get('document_reference_id') not in note_ids_seen:
                    prioritized.append(PrioritizedNote(
                        note=post_surgery_note['note'],
                        priority_reason="post_surgery",
                        related_event_id=surgery.get('procedure_fhir_id'),
                        related_event_type="surgery",
                        related_event_date=surgery_date,
                        days_from_event=post_surgery_note['days_from_event']
                    ))
                    note_ids_seen.add(post_surgery_note['note'].get('document_reference_id'))
                    logger.debug(f"Added post-surgery note: {post_surgery_note['days_from_event']} days after surgery")

            except Exception as e:
                logger.warning(f"Error processing surgery for note prioritization: {e}")
                continue

        # 2. Notes after imaging events
        for imaging in imaging_events:
            try:
                imaging_date = self._parse_date(imaging.get('imaging_date'))
                if not imaging_date:
                    continue

                # Find first note after imaging (within window)
                post_imaging_note = self._find_first_note_after_event(
                    notes_with_dates,
                    imaging_date,
                    self.post_event_window_days
                )

                if post_imaging_note and post_imaging_note['note'].get('document_reference_id') not in note_ids_seen:
                    prioritized.append(PrioritizedNote(
                        note=post_imaging_note['note'],
                        priority_reason="post_imaging",
                        related_event_id=imaging.get('diagnostic_report_id'),
                        related_event_type="imaging",
                        related_event_date=imaging_date,
                        days_from_event=post_imaging_note['days_from_event']
                    ))
                    note_ids_seen.add(post_imaging_note['note'].get('document_reference_id'))
                    logger.debug(f"Added post-imaging note: {post_imaging_note['days_from_event']} days after imaging")

            except Exception as e:
                logger.warning(f"Error processing imaging for note prioritization: {e}")
                continue

        # 3. Notes around medication changes (if provided)
        # Include notes both BEFORE and AFTER medication start
        if medication_changes:
            for med_change in medication_changes:
                try:
                    change_date = self._parse_date(med_change.get('change_date'))
                    if not change_date:
                        continue

                    # Find last note BEFORE medication change (baseline)
                    pre_med_change_note = self._find_last_note_before_event(
                        notes_with_dates,
                        change_date,
                        self.post_event_window_days
                    )

                    if pre_med_change_note and pre_med_change_note['note'].get('document_reference_id') not in note_ids_seen:
                        prioritized.append(PrioritizedNote(
                            note=pre_med_change_note['note'],
                            priority_reason="pre_medication_change",
                            related_event_id=med_change.get('medication_id'),
                            related_event_type="medication_change",
                            related_event_date=change_date,
                            days_from_event=pre_med_change_note['days_from_event']
                        ))
                        note_ids_seen.add(pre_med_change_note['note'].get('document_reference_id'))
                        logger.debug(f"Added pre-medication-change note: {abs(pre_med_change_note['days_from_event'])} days before change")

                    # Find first note AFTER medication change (response assessment)
                    post_med_change_note = self._find_first_note_after_event(
                        notes_with_dates,
                        change_date,
                        self.post_event_window_days
                    )

                    if post_med_change_note and post_med_change_note['note'].get('document_reference_id') not in note_ids_seen:
                        prioritized.append(PrioritizedNote(
                            note=post_med_change_note['note'],
                            priority_reason="post_medication_change",
                            related_event_id=med_change.get('medication_id'),
                            related_event_type="medication_change",
                            related_event_date=change_date,
                            days_from_event=post_med_change_note['days_from_event']
                        ))
                        note_ids_seen.add(post_med_change_note['note'].get('document_reference_id'))
                        logger.debug(f"Added post-medication-change note: {post_med_change_note['days_from_event']} days after change")

                except Exception as e:
                    logger.warning(f"Error processing medication change for note prioritization: {e}")
                    continue

        # 4. Always include final progress note (most recent)
        if self.include_final_note and notes_with_dates:
            final_note = notes_with_dates[-1][0]  # Last note chronologically

            if final_note.get('document_reference_id') not in note_ids_seen:
                prioritized.append(PrioritizedNote(
                    note=final_note,
                    priority_reason="final_note",
                    related_event_id=None,
                    related_event_type=None,
                    related_event_date=None,
                    days_from_event=None
                ))
                note_ids_seen.add(final_note.get('document_reference_id'))
                logger.debug(f"Added final progress note: {notes_with_dates[-1][1]}")

        # Sort by date
        prioritized.sort(key=lambda x: self._parse_date(x.note.get('dr_date')))

        logger.info(f"Prioritized {len(prioritized)} progress notes from {len(progress_notes)} total notes")
        logger.info(f"  Post-surgery: {sum(1 for p in prioritized if p.priority_reason == 'post_surgery')}")
        logger.info(f"  Post-imaging: {sum(1 for p in prioritized if p.priority_reason == 'post_imaging')}")
        logger.info(f"  Post-medication-change: {sum(1 for p in prioritized if p.priority_reason == 'post_medication_change')}")
        logger.info(f"  Final note: {sum(1 for p in prioritized if p.priority_reason == 'final_note')}")

        return prioritized

    def _find_first_note_after_event(
        self,
        notes_with_dates: List[tuple],
        event_date: datetime,
        window_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find first progress note after an event (within window)

        Args:
            notes_with_dates: List of (note, date) tuples sorted by date
            event_date: Date of clinical event
            window_days: Days after event to search

        Returns:
            Dictionary with 'note' and 'days_from_event', or None
        """
        window_end = event_date + timedelta(days=window_days)

        for note, note_date in notes_with_dates:
            # Note must be AFTER event and within window
            if event_date < note_date <= window_end:
                days_from_event = (note_date - event_date).days
                return {
                    'note': note,
                    'days_from_event': days_from_event
                }

        return None

    def _find_last_note_before_event(
        self,
        notes_with_dates: List[tuple],
        event_date: datetime,
        window_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find last progress note before an event (within window)

        Args:
            notes_with_dates: List of (note, date) tuples sorted by date
            event_date: Date of clinical event
            window_days: Days before event to search

        Returns:
            Dictionary with 'note' and 'days_from_event' (negative), or None
        """
        window_start = event_date - timedelta(days=window_days)

        # Search backwards from event date
        for note, note_date in reversed(notes_with_dates):
            # Note must be BEFORE event and within window
            if window_start <= note_date < event_date:
                days_from_event = (note_date - event_date).days  # Will be negative
                return {
                    'note': note,
                    'days_from_event': days_from_event
                }

        return None

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date from various formats"""
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except:
                try:
                    # Try common formats
                    return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                except:
                    try:
                        return datetime.strptime(date_value, '%Y-%m-%d')
                    except:
                        return None

        return None


def get_prioritization_summary(prioritized_notes: List[PrioritizedNote]) -> Dict[str, Any]:
    """
    Generate summary statistics for prioritized notes

    Args:
        prioritized_notes: List of PrioritizedNote objects

    Returns:
        Dictionary with summary statistics
    """
    by_reason = {}
    for note in prioritized_notes:
        reason = note.priority_reason
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append(note)

    return {
        'total_prioritized': len(prioritized_notes),
        'by_priority_reason': {
            reason: len(notes) for reason, notes in by_reason.items()
        },
        'date_range': {
            'earliest': min(
                (n.note.get('dr_date') for n in prioritized_notes if n.note.get('dr_date')),
                default=None
            ),
            'latest': max(
                (n.note.get('dr_date') for n in prioritized_notes if n.note.get('dr_date')),
                default=None
            )
        },
        'avg_days_from_event': sum(
            n.days_from_event for n in prioritized_notes if n.days_from_event is not None
        ) / max(sum(1 for n in prioritized_notes if n.days_from_event is not None), 1)
    }


# CLI for testing
if __name__ == "__main__":
    import sys
    import json

    # Example usage
    print("Progress Note Prioritization Utility")
    print("=" * 50)
    print()
    print("This utility prioritizes progress notes based on clinical events:")
    print("  1. Notes after surgeries (±7 days)")
    print("  2. Notes after imaging (±7 days)")
    print("  3. Notes after medication changes (±7 days)")
    print("  4. Final progress note")
    print()
    print("Usage:")
    print("  from utils.progress_note_prioritization import ProgressNotePrioritizer")
    print()
    print("  prioritizer = ProgressNotePrioritizer()")
    print("  prioritized = prioritizer.prioritize_notes(")
    print("      progress_notes=all_notes,")
    print("      surgeries=surgery_records,")
    print("      imaging_events=imaging_records")
    print("  )")
