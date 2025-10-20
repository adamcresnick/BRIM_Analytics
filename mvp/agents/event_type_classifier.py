"""
Agent 1 Event Type Classification

Agent 1 responsibility: Classify each tumor event as:
- Initial CNS Tumor
- Recurrence
- Progressive
- Second Malignancy

Logic:
- If previous surgery was Gross Total Resection and tumor re-grows → Recurrence
- If previous surgery was Partial Resection and tumor grows → Progressive
- If new tumor in different location → Second Malignancy
- First documented tumor event → Initial CNS Tumor
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EventTypeClassification:
    """Result of event type classification"""
    event_id: str
    event_date: datetime
    event_type: str  # 'Initial CNS Tumor', 'Recurrence', 'Progressive', 'Second Malignancy'
    confidence: float
    reasoning: str
    supporting_evidence: Dict[str, Any]


class EventTypeClassifier:
    """
    Agent 1 classifier for determining event type based on surgical history
    and tumor status progression.
    """

    def __init__(self, timeline_query_interface):
        """
        Args:
            timeline_query_interface: Interface to query DuckDB timeline
        """
        self.timeline = timeline_query_interface

    def classify_event(
        self,
        patient_id: str,
        event: Dict[str, Any],
        surgical_history: List[Dict[str, Any]],
        prior_tumor_events: List[Dict[str, Any]]
    ) -> EventTypeClassification:
        """
        Classify a tumor event based on surgical history and prior events.

        Args:
            patient_id: Patient FHIR ID
            event: Current tumor event with tumor_status and location
            surgical_history: List of prior surgical procedures with EOR
            prior_tumor_events: List of prior tumor events (chronological)

        Returns:
            EventTypeClassification with event_type determination
        """
        event_id = event.get('event_id')
        event_date = event.get('event_date')
        tumor_status = event.get('tumor_status')
        location = event.get('location', 'Unknown')

        logger.info(f"Classifying event {event_id} ({event_date}): tumor_status={tumor_status}")

        # Case 1: First tumor event → Initial CNS Tumor
        if not prior_tumor_events:
            return EventTypeClassification(
                event_id=event_id,
                event_date=event_date,
                event_type='Initial CNS Tumor',
                confidence=0.95,
                reasoning="First documented tumor event in patient timeline",
                supporting_evidence={
                    'prior_events_count': 0,
                    'prior_surgeries_count': len(surgical_history)
                }
            )

        # Case 2: New tumor in different location → Second Malignancy
        if self._is_new_location(location, prior_tumor_events):
            return EventTypeClassification(
                event_id=event_id,
                event_date=event_date,
                event_type='Second Malignancy',
                confidence=0.85,
                reasoning=f"New tumor location '{location}' distinct from prior events",
                supporting_evidence={
                    'current_location': location,
                    'prior_locations': [e.get('location') for e in prior_tumor_events]
                }
            )

        # Case 3: Tumor growth after surgery
        # Find most recent surgery before this event
        prior_surgery = self._get_most_recent_surgery_before(event_date, surgical_history)

        if prior_surgery:
            eor = prior_surgery.get('extent_of_resection', 'Unknown')
            surgery_date = prior_surgery.get('procedure_date')

            # Case 3a: Gross Total Resection → Recurrence
            if eor in ['Gross Total Resection', 'Near Total Resection', 'GTR']:
                if tumor_status in ['Increased', 'New_Malignancy']:
                    return EventTypeClassification(
                        event_id=event_id,
                        event_date=event_date,
                        event_type='Recurrence',
                        confidence=0.90,
                        reasoning=f"Tumor growth after {eor} on {surgery_date}",
                        supporting_evidence={
                            'prior_surgery_date': str(surgery_date),
                            'prior_surgery_eor': eor,
                            'current_tumor_status': tumor_status,
                            'days_since_surgery': (event_date - surgery_date).days
                        }
                    )

            # Case 3b: Partial Resection → Progressive
            elif eor in ['Partial Resection', 'Subtotal', 'STR']:
                if tumor_status in ['Increased']:
                    return EventTypeClassification(
                        event_id=event_id,
                        event_date=event_date,
                        event_type='Progressive',
                        confidence=0.90,
                        reasoning=f"Tumor progression after {eor} on {surgery_date}",
                        supporting_evidence={
                            'prior_surgery_date': str(surgery_date),
                            'prior_surgery_eor': eor,
                            'current_tumor_status': tumor_status,
                            'days_since_surgery': (event_date - surgery_date).days
                        }
                    )

        # Case 4: Biopsy only → Progressive (no resection, residual tumor growing)
        if prior_surgery and prior_surgery.get('extent_of_resection') == 'Biopsy Only':
            if tumor_status == 'Increased':
                return EventTypeClassification(
                    event_id=event_id,
                    event_date=event_date,
                    event_type='Progressive',
                    confidence=0.85,
                    reasoning="Tumor progression after biopsy only (no resection)",
                    supporting_evidence={
                        'prior_surgery_date': str(prior_surgery.get('procedure_date')),
                        'prior_surgery_eor': 'Biopsy Only',
                        'current_tumor_status': tumor_status
                    }
                )

        # Case 5: Progressive disease without clear surgery reference
        # If tumor status shows growth trajectory
        if tumor_status == 'Increased' and prior_tumor_events:
            # Check if prior events showed disease (not NED)
            prior_statuses = [e.get('tumor_status') for e in prior_tumor_events[-3:]]
            if any(s in ['Stable', 'Decreased', 'Increased'] for s in prior_statuses):
                return EventTypeClassification(
                    event_id=event_id,
                    event_date=event_date,
                    event_type='Progressive',
                    confidence=0.75,
                    reasoning="Tumor growth in context of ongoing disease surveillance",
                    supporting_evidence={
                        'prior_tumor_statuses': prior_statuses,
                        'current_tumor_status': tumor_status
                    }
                )

        # Case 6: NED → New disease → Recurrence
        if tumor_status in ['Increased', 'New_Malignancy']:
            # Check if prior events showed NED or stable disease
            recent_prior = prior_tumor_events[-1] if prior_tumor_events else None
            if recent_prior and recent_prior.get('tumor_status') == 'NED':
                return EventTypeClassification(
                    event_id=event_id,
                    event_date=event_date,
                    event_type='Recurrence',
                    confidence=0.80,
                    reasoning="New tumor growth after period of NED",
                    supporting_evidence={
                        'prior_event_status': 'NED',
                        'prior_event_date': str(recent_prior.get('event_date')),
                        'current_tumor_status': tumor_status
                    }
                )

        # Default: Unable to classify with confidence
        return EventTypeClassification(
            event_id=event_id,
            event_date=event_date,
            event_type='Progressive',  # Default assumption
            confidence=0.50,
            reasoning="Insufficient information for confident event type classification",
            supporting_evidence={
                'current_tumor_status': tumor_status,
                'prior_surgeries_count': len(surgical_history),
                'prior_events_count': len(prior_tumor_events)
            }
        )

    def _is_new_location(self, current_location: str, prior_events: List[Dict[str, Any]]) -> bool:
        """
        Determine if current tumor location is distinct from prior events.

        Args:
            current_location: Location description from current event
            prior_events: List of prior tumor events

        Returns:
            True if new/distinct location, False otherwise
        """
        if not current_location or current_location == 'Unknown':
            return False

        current_loc_lower = current_location.lower()

        # Get unique prior locations
        prior_locations = {
            e.get('location', '').lower()
            for e in prior_events
            if e.get('location') and e.get('location') != 'Unknown'
        }

        if not prior_locations:
            return False

        # Simple substring matching - could be enhanced with NLP
        for prior_loc in prior_locations:
            # If substantial overlap, likely same location
            if prior_loc in current_loc_lower or current_loc_lower in prior_loc:
                return False

        return True

    def _get_most_recent_surgery_before(
        self,
        event_date: datetime,
        surgical_history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get most recent surgery before the given event date.

        Args:
            event_date: Date of current tumor event
            surgical_history: List of surgical procedures (should be chronological)

        Returns:
            Most recent surgery dict or None
        """
        surgeries_before = [
            s for s in surgical_history
            if s.get('procedure_date') and s['procedure_date'] < event_date
        ]

        if not surgeries_before:
            return None

        # Return most recent (last in chronological list)
        return surgeries_before[-1]

    def classify_patient_events(
        self,
        patient_id: str
    ) -> List[EventTypeClassification]:
        """
        Classify all tumor events for a patient.

        Args:
            patient_id: Patient FHIR ID

        Returns:
            List of EventTypeClassification for all tumor events
        """
        # Query timeline for all tumor events (chronological)
        tumor_events_query = """
            SELECT DISTINCT
                e.event_id,
                e.event_date,
                ev.variable_value as tumor_status
            FROM events e
            JOIN extracted_variables ev ON e.event_id = ev.source_event_id
            WHERE e.patient_id = ?
                AND ev.variable_name = 'tumor_status'
            ORDER BY e.event_date
        """
        tumor_events_rows = self.timeline.conn.execute(tumor_events_query, [patient_id]).fetchall()
        tumor_events = [{'event_id': row[0], 'event_date': row[1], 'tumor_status': row[2]} for row in tumor_events_rows]

        # Query surgical history
        surgical_history_query = """
            SELECT DISTINCT
                e.event_id,
                e.event_date,
                e.description,
                ev.variable_value as eor
            FROM events e
            LEFT JOIN extracted_variables ev ON e.event_id = ev.source_event_id AND ev.variable_name = 'extent_of_resection'
            WHERE e.patient_id = ?
                AND e.event_type = 'Procedure'
                AND (
                    LOWER(e.description) LIKE '%resection%'
                    OR LOWER(e.description) LIKE '%craniotomy%'
                    OR LOWER(e.description) LIKE '%craniectomy%'
                )
            ORDER BY e.event_date
        """
        surgical_history_rows = self.timeline.conn.execute(surgical_history_query, [patient_id]).fetchall()
        surgical_history = [{'event_id': row[0], 'procedure_date': row[1], 'description': row[2], 'eor': row[3]} for row in surgical_history_rows]

        classifications = []
        for i, event in enumerate(tumor_events):
            # Only classify events with tumor status
            if not event.get('tumor_status'):
                continue

            prior_events = tumor_events[:i]  # All events before this one
            classification = self.classify_event(
                patient_id,
                event,
                surgical_history,
                prior_events
            )
            classifications.append(classification)

        return classifications
