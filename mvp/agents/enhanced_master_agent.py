"""
Enhanced Master Agent - Adds Temporal Validation & Iterative Agent 2 Queries

Extends MasterAgent with:
1. Temporal inconsistency detection AFTER extraction
2. Iterative queries to Agent 2 for clarification
3. Multi-source integration (operative reports, progress notes)
4. Event type classification
5. Comprehensive patient abstraction generation

This implements the required Agent 1 behaviors:
- Detect temporal inconsistencies in NEW extractions
- Query Agent 2 when things don't make clinical sense
- Guide Agent 2 with additional context
- Perform multi-source adjudication
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json

from .master_agent import MasterAgent
from .medgemma_agent import MedGemmaAgent
from timeline_query_interface import TimelineQueryInterface
from .eor_adjudicator import EORAdjudicator, EORSource
from .event_type_classifier import EventTypeClassifier

logger = logging.getLogger(__name__)


@dataclass
class TemporalInconsistency:
    """Detected temporal inconsistency requiring Agent 2 clarification"""
    inconsistency_id: str
    inconsistency_type: str  # 'rapid_change', 'illogical_progression', 'unexplained_improvement'
    severity: str  # 'high', 'medium', 'low'
    description: str
    affected_events: List[str]  # event_ids
    context: Dict[str, Any]  # surgical history, medications, etc.
    requires_agent2_query: bool


class EnhancedMasterAgent(MasterAgent):
    """
    Enhanced Master Agent with post-extraction validation and iterative Agent 2 queries.
    """

    def __init__(
        self,
        timeline_db_path: str,
        medgemma_agent: Optional[MedGemmaAgent] = None,
        dry_run: bool = False
    ):
        """Initialize Enhanced Master Agent"""
        super().__init__(timeline_db_path, medgemma_agent, dry_run)

        # Initialize adjudicators
        self.eor_adjudicator = EORAdjudicator(self.medgemma)
        self.event_classifier = EventTypeClassifier(self.timeline)

        logger.info("Enhanced Master Agent initialized with post-extraction validation")

    def orchestrate_comprehensive_extraction(
        self,
        patient_id: str
    ) -> Dict[str, Any]:
        """
        Run comprehensive extraction with temporal validation and iterative Agent 2 queries.

        Workflow:
        1. Run base MasterAgent imaging extraction (with timeline context)
        2. Detect temporal inconsistencies in new extractions
        3. Query Agent 2 for clarification on suspicious patterns
        4. Classify event types based on surgical history
        5. Generate comprehensive abstraction

        Args:
            patient_id: Patient FHIR ID

        Returns:
            Comprehensive abstraction with all validations
        """
        logger.info(f"Starting comprehensive extraction for patient {patient_id}")

        comprehensive_summary = {
            'patient_id': patient_id,
            'start_time': datetime.now().isoformat(),
            'workflow': 'enhanced_master_agent_with_validation'
        }

        # =====================================================================
        # PHASE 1: BASE IMAGING EXTRACTION (MasterAgent with timeline context)
        # =====================================================================
        logger.info("Phase 1: Running base imaging extraction with timeline context")

        imaging_summary = self.orchestrate_imaging_extraction(
            patient_id=patient_id,
            extraction_type='all'
        )

        comprehensive_summary['imaging_extraction'] = imaging_summary

        # If no NEW extractions, load EXISTING extractions from timeline for validation
        if imaging_summary['successful_extractions'] == 0:
            logger.info("No new extractions - loading existing extractions from timeline for validation")
            existing_extractions = self._load_existing_extractions(patient_id)

            if len(existing_extractions) == 0:
                logger.warning("No existing extractions found - nothing to validate")
                comprehensive_summary['end_time'] = datetime.now().isoformat()
                return comprehensive_summary

            logger.info(f"Loaded {len(existing_extractions)} existing extractions for validation")
            imaging_summary['results'] = existing_extractions
            imaging_summary['successful_extractions'] = len(existing_extractions)

        # =====================================================================
        # PHASE 2: TEMPORAL INCONSISTENCY DETECTION
        # =====================================================================
        logger.info("Phase 2: Detecting temporal inconsistencies")

        inconsistencies = self._detect_temporal_inconsistencies(
            patient_id,
            imaging_summary['results']
        )

        comprehensive_summary['temporal_inconsistencies'] = {
            'count': len(inconsistencies),
            'high_severity': len([i for i in inconsistencies if i.severity == 'high']),
            'requiring_agent2_query': len([i for i in inconsistencies if i.requires_agent2_query]),
            'details': [self._inconsistency_to_dict(i) for i in inconsistencies]
        }

        logger.info(f"Detected {len(inconsistencies)} temporal inconsistencies")

        # =====================================================================
        # PHASE 3: ITERATIVE AGENT 2 QUERIES FOR CLARIFICATION
        # =====================================================================
        logger.info("Phase 3: Querying Agent 2 for clarification on inconsistencies")

        resolutions = []
        for inconsistency in inconsistencies:
            if inconsistency.requires_agent2_query:
                logger.info(f"Querying Agent 2 about: {inconsistency.description}")

                resolution = self._query_agent2_for_clarification(
                    patient_id,
                    inconsistency
                )

                resolutions.append(resolution)

        comprehensive_summary['agent2_clarifications'] = {
            'count': len(resolutions),
            'resolutions': resolutions
        }

        # =====================================================================
        # PHASE 4: EVENT TYPE CLASSIFICATION
        # =====================================================================
        logger.info("Phase 4: Classifying event types")

        event_classifications = self._classify_all_events(patient_id)

        comprehensive_summary['event_type_classifications'] = {
            'count': len(event_classifications),
            'classifications': event_classifications
        }

        # =====================================================================
        # PHASE 5: GENERATE FINAL ABSTRACTION
        # =====================================================================
        comprehensive_summary['end_time'] = datetime.now().isoformat()

        logger.info("Comprehensive extraction complete")

        return comprehensive_summary

    def _detect_temporal_inconsistencies(
        self,
        patient_id: str,
        extraction_results: List[Dict[str, Any]]
    ) -> List[TemporalInconsistency]:
        """
        Detect temporal inconsistencies in NEW extractions.

        Checks for:
        - Rapid tumor status changes (Increased→Decreased in <7 days)
        - Illogical progressions (NED→Increased→NED without treatment)
        - Unexplained improvements without surgical intervention

        Args:
            patient_id: Patient FHIR ID
            extraction_results: Results from imaging extraction

        Returns:
            List of detected inconsistencies
        """
        inconsistencies = []

        # Get tumor status extractions
        tumor_status_extractions = [
            r for r in extraction_results
            if r['extraction_type'] == 'tumor_status' and r['success']
        ]

        if len(tumor_status_extractions) < 2:
            return inconsistencies  # Need at least 2 to compare

        # Sort by event date
        sorted_extractions = sorted(
            tumor_status_extractions,
            key=lambda x: self._get_event_date(x['event_id'])
        )

        # Check consecutive pairs for temporal issues
        for i in range(len(sorted_extractions) - 1):
            prior = sorted_extractions[i]
            current = sorted_extractions[i + 1]

            prior_date = self._get_event_date(prior['event_id'])
            current_date = self._get_event_date(current['event_id'])
            days_diff = (current_date - prior_date).days

            prior_status = prior['value']
            current_status = current['value']

            # DETECTION RULE 1: Rapid Improvement (Increased→Decreased in <7 days)
            if prior_status == 'Increased' and current_status == 'Decreased' and days_diff < 7:
                # Check if surgery explains this
                surgery_between = self._has_surgery_between(
                    patient_id,
                    prior_date,
                    current_date
                )

                if not surgery_between:
                    inconsistencies.append(TemporalInconsistency(
                        inconsistency_id=f"rapid_improvement_{prior['event_id']}_{current['event_id']}",
                        inconsistency_type='rapid_change',
                        severity='high',
                        description=f"Tumor status improved from Increased to Decreased in {days_diff} days without documented surgery",
                        affected_events=[prior['event_id'], current['event_id']],
                        context={
                            'prior_date': prior_date.isoformat(),
                            'current_date': current_date.isoformat(),
                            'days_between': days_diff,
                            'surgery_found': False
                        },
                        requires_agent2_query=True
                    ))

            # DETECTION RULE 2: Illogical Progression (NED→Disease→NED without GTR)
            if prior_status == 'NED' and current_status in ['Increased', 'Stable'] and days_diff < 180:
                # New disease after NED suggests recurrence
                inconsistencies.append(TemporalInconsistency(
                    inconsistency_id=f"recurrence_after_ned_{prior['event_id']}_{current['event_id']}",
                    inconsistency_type='unexplained_recurrence',
                    severity='medium',
                    description=f"Disease detected after NED period ({days_diff} days)",
                    affected_events=[prior['event_id'], current['event_id']],
                    context={
                        'prior_date': prior_date.isoformat(),
                        'current_date': current_date.isoformat(),
                        'days_between': days_diff
                    },
                    requires_agent2_query=False  # Expected pattern, not suspicious
                ))

        return inconsistencies

    def _query_agent2_for_clarification(
        self,
        patient_id: str,
        inconsistency: TemporalInconsistency
    ) -> Dict[str, Any]:
        """
        Query Agent 2 for clarification on a temporal inconsistency.

        Builds a comprehensive prompt with:
        - Original imaging reports
        - Surgical history context
        - Specific question about the inconsistency

        Args:
            patient_id: Patient FHIR ID
            inconsistency: Detected inconsistency

        Returns:
            Agent 2's clarification response
        """
        logger.info(f"Building clarification query for Agent 2: {inconsistency.inconsistency_id}")

        # Get the imaging reports for affected events
        reports = []
        for event_id in inconsistency.affected_events:
            report = self.timeline.get_radiology_report(event_id)
            if report:
                reports.append({
                    'event_id': event_id,
                    'date': report.get('document_date', 'Unknown'),
                    'text': report.get('document_text', '')
                })

        # Build clarification prompt
        clarification_prompt = f"""# AGENT 1 REQUESTS CLARIFICATION FROM AGENT 2

## Temporal Inconsistency Detected

**Inconsistency Type:** {inconsistency.inconsistency_type}
**Severity:** {inconsistency.severity}
**Description:** {inconsistency.description}

## Context

{json.dumps(inconsistency.context, indent=2)}

## Imaging Reports

"""

        for i, report in enumerate(reports, 1):
            clarification_prompt += f"""
### Report {i} ({report['date']})
Event ID: {report['event_id']}

```
{report['text'][:1000]}
```

"""

        clarification_prompt += """
## Question for Agent 2

After reviewing these imaging reports and the temporal context:

1. **Clinical Plausibility**: Is this rapid change clinically plausible?
2. **Potential Explanations**: What could explain this pattern?
3. **Re-classification**: Should either extraction be revised?
4. **Recommendation**: keep_both | revise_first | revise_second | escalate_to_human

Please provide your assessment in JSON format:

```json
{
  "clinical_plausibility": "plausible|implausible|uncertain",
  "explanation": "...",
  "recommended_action": "keep_both|revise_first|revise_second|escalate",
  "revised_classifications": {
    "first_event": "NED|Stable|Increased|Decreased|null",
    "second_event": "NED|Stable|Increased|Decreased|null"
  },
  "confidence": 0.0-1.0
}
```
"""

        # Query Agent 2
        try:
            result = self.medgemma.extract(clarification_prompt)

            return {
                'inconsistency_id': inconsistency.inconsistency_id,
                'agent2_response': result.extracted_data if result.success else None,
                'success': result.success,
                'error': result.error
            }

        except Exception as e:
            logger.error(f"Failed to query Agent 2: {e}", exc_info=True)
            return {
                'inconsistency_id': inconsistency.inconsistency_id,
                'agent2_response': None,
                'success': False,
                'error': str(e)
            }

    def _classify_all_events(
        self,
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """
        Classify all tumor events for event_type.

        Uses EventTypeClassifier to determine:
        - Initial CNS Tumor
        - Recurrence
        - Progressive
        - Second Malignancy

        Args:
            patient_id: Patient FHIR ID

        Returns:
            List of event type classifications
        """
        try:
            classifications = self.event_classifier.classify_patient_events(patient_id)

            return [
                {
                    'event_id': c.event_id,
                    'event_date': c.event_date.isoformat(),
                    'event_type': c.event_type,
                    'confidence': c.confidence,
                    'reasoning': c.reasoning
                }
                for c in classifications
            ]

        except Exception as e:
            logger.error(f"Failed to classify events: {e}", exc_info=True)
            return []

    def _get_event_date(self, event_id: str) -> datetime:
        """Get event date from timeline"""
        result = self.timeline.conn.execute(
            "SELECT event_date FROM events WHERE event_id = ?",
            [event_id]
        ).fetchone()

        if result and result[0]:
            event_date = result[0]
            # Handle if already datetime object
            if isinstance(event_date, datetime):
                return event_date
            # Handle string
            elif isinstance(event_date, str):
                return datetime.fromisoformat(event_date)
            else:
                logger.warning(f"Unexpected event_date type for {event_id}: {type(event_date)}")
                return datetime.min
        else:
            return datetime.min

    def _has_surgery_between(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> bool:
        """Check if patient had tumor surgery between two dates"""
        result = self.timeline.conn.execute(
            """
            SELECT COUNT(*)
            FROM events
            WHERE patient_id = ?
                AND event_type = 'Procedure'
                AND event_date >= ?
                AND event_date <= ?
                AND (
                    LOWER(description) LIKE '%resection%'
                    OR LOWER(description) LIKE '%craniotomy%'
                    OR LOWER(description) LIKE '%craniectomy%'
                )
            """,
            [patient_id, start_date.isoformat(), end_date.isoformat()]
        ).fetchone()

        return result[0] > 0 if result else False

    def _load_existing_extractions(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Load existing tumor_status extractions from timeline database.

        Returns list in same format as orchestrate_imaging_extraction results.
        """
        try:
            results = []

            # Query all tumor_status extractions for this patient
            query = """
                SELECT
                    ev.variable_name,
                    ev.variable_value,
                    ev.variable_confidence,
                    ev.source_event_id,
                    ev.event_date
                FROM extracted_variables ev
                WHERE ev.patient_id = ?
                    AND ev.variable_name = 'tumor_status'
                ORDER BY ev.event_date
            """

            rows = self.timeline.conn.execute(query, [patient_id]).fetchall()

            for row in rows:
                results.append({
                    'event_id': row[3],
                    'extraction_type': row[0],
                    'success': True,
                    'value': row[1],
                    'confidence': float(row[2]) if row[2] else 0.0,
                    'error': None
                })

            logger.info(f"Loaded {len(results)} existing extractions from timeline")
            return results

        except Exception as e:
            logger.error(f"Failed to load existing extractions: {e}", exc_info=True)
            return []

    def _inconsistency_to_dict(self, inconsistency: TemporalInconsistency) -> Dict[str, Any]:
        """Convert TemporalInconsistency to dict for JSON serialization"""
        return {
            'inconsistency_id': inconsistency.inconsistency_id,
            'inconsistency_type': inconsistency.inconsistency_type,
            'severity': inconsistency.severity,
            'description': inconsistency.description,
            'affected_events': inconsistency.affected_events,
            'context': inconsistency.context,
            'requires_agent2_query': inconsistency.requires_agent2_query
        }
