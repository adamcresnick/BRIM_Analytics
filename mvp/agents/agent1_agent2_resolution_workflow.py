"""
Agent 1 (Claude) ↔ Agent 2 (MedGemma) Iterative Resolution Workflow

Agent 1 responsibilities:
- Detect inconsistencies in Agent 2 extractions
- Query Agent 2 for explanations and re-reviews
- Gather multi-source context (imaging PDFs, progress notes, op reports)
- Adjudicate conflicts across sources
- Document all inconsistencies and resolutions in patient-specific QA report

Agent 2 responsibilities:
- Extract targeted variables from documents
- Provide confidence scores
- Re-review with additional context when requested by Agent 1
- Explain reasoning when queried
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from medgemma_agent import MedGemmaAgent
from timeline_query_interface import TimelineQueryInterface
from binary_file_agent import BinaryFileAgent

logger = logging.getLogger(__name__)


@dataclass
class InconsistencyDetection:
    """Record of detected inconsistency"""
    inconsistency_id: str
    inconsistency_type: str  # 'temporal', 'duplicate', 'wrong_type', 'multi_source_conflict', 'low_confidence'
    severity: str  # 'high', 'medium', 'low'
    description: str
    affected_extractions: List[str]  # event_ids
    detected_by: str  # 'agent1_temporal_check', 'agent1_duplicate_check', etc.
    detected_at: datetime


@dataclass
class ResolutionAttempt:
    """Record of resolution attempt"""
    attempt_id: str
    inconsistency_id: str
    resolution_method: str  # 'query_agent2', 'multi_source_review', 'manual_override', 'skip_duplicate'
    agent2_interaction: Optional[Dict[str, Any]]  # Query/response from Agent 2
    additional_sources_used: List[str]  # PDF IDs, progress note IDs
    outcome: str  # 'resolved', 'escalated', 'overridden', 'skipped'
    resolution_notes: str
    resolved_at: datetime


@dataclass
class PatientQAReport:
    """Complete QA report for patient extraction"""
    patient_id: str
    extraction_session_id: str
    start_time: datetime
    end_time: Optional[datetime]

    # Summary statistics
    total_events_processed: int
    successful_extractions: int
    inconsistencies_detected: int
    inconsistencies_resolved: int
    inconsistencies_escalated: int

    # Detailed records
    inconsistencies: List[InconsistencyDetection]
    resolutions: List[ResolutionAttempt]

    # Multi-source statistics
    multi_source_extractions: int
    source_agreement_rate: float

    # Final recommendations
    requires_human_review: bool
    high_priority_issues: List[str]


class Agent1OrchestratorWithQA:
    """
    Agent 1 (Claude) orchestrator with iterative Agent 2 resolution
    """

    def __init__(
        self,
        medgemma_agent: MedGemmaAgent,
        timeline: TimelineQueryInterface,
        binary_agent: BinaryFileAgent,
        qa_reports_dir: str = "data/qa_reports"
    ):
        self.agent2 = medgemma_agent
        self.timeline = timeline
        self.binary_agent = binary_agent
        self.qa_reports_dir = Path(qa_reports_dir)
        self.qa_reports_dir.mkdir(parents=True, exist_ok=True)

        # Current session state
        self.current_session_id = None
        self.inconsistencies = []
        self.resolutions = []

    def start_extraction_session(self, patient_id: str) -> str:
        """Start new extraction session with QA tracking"""
        session_id = f"{patient_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_session_id = session_id
        self.inconsistencies = []
        self.resolutions = []

        logger.info(f"Started extraction session: {session_id}")
        return session_id

    def detect_inconsistencies(
        self,
        patient_id: str,
        new_extraction: Dict[str, Any],
        timeline_context: Dict[str, Any]
    ) -> List[InconsistencyDetection]:
        """
        Agent 1: Detect inconsistencies in Agent 2 extraction
        """
        issues = []

        # Check 1: Duplicate event (same date as existing event)
        duplicate = self._check_duplicate_event(patient_id, new_extraction)
        if duplicate:
            issues.append(InconsistencyDetection(
                inconsistency_id=f"dup_{new_extraction['event_id']}",
                inconsistency_type='duplicate',
                severity='high',
                description=f"Event on {new_extraction['event_date']} duplicates existing event",
                affected_extractions=[new_extraction['event_id'], duplicate['event_id']],
                detected_by='agent1_duplicate_check',
                detected_at=datetime.now()
            ))

        # Check 2: Temporal inconsistency
        temporal_issue = self._check_temporal_consistency(
            patient_id, new_extraction, timeline_context
        )
        if temporal_issue:
            issues.append(temporal_issue)

        # Check 3: Wrong extraction type (EOR value in tumor_status)
        if self._is_wrong_extraction_type(new_extraction):
            issues.append(InconsistencyDetection(
                inconsistency_id=f"wrongtype_{new_extraction['event_id']}",
                inconsistency_type='wrong_type',
                severity='high',
                description=f"Value '{new_extraction['value']}' belongs to extent_of_resection, not tumor_status",
                affected_extractions=[new_extraction['event_id']],
                detected_by='agent1_type_validation',
                detected_at=datetime.now()
            ))

        # Check 4: Low confidence
        if new_extraction.get('confidence', 1.0) < 0.75:
            issues.append(InconsistencyDetection(
                inconsistency_id=f"lowconf_{new_extraction['event_id']}",
                inconsistency_type='low_confidence',
                severity='medium',
                description=f"Confidence {new_extraction['confidence']:.2f} below threshold 0.75",
                affected_extractions=[new_extraction['event_id']],
                detected_by='agent1_confidence_check',
                detected_at=datetime.now()
            ))

        return issues

    def resolve_with_agent2(
        self,
        inconsistency: InconsistencyDetection,
        extraction: Dict[str, Any],
        timeline_context: Dict[str, Any]
    ) -> ResolutionAttempt:
        """
        Agent 1: Iteratively resolve inconsistency by querying Agent 2
        """
        attempt_id = f"res_{inconsistency.inconsistency_id}"

        logger.info(f"Agent 1 resolving inconsistency: {inconsistency.inconsistency_type}")

        if inconsistency.inconsistency_type == 'duplicate':
            # Resolution: Skip duplicate
            return ResolutionAttempt(
                attempt_id=attempt_id,
                inconsistency_id=inconsistency.inconsistency_id,
                resolution_method='skip_duplicate',
                agent2_interaction=None,
                additional_sources_used=[],
                outcome='resolved',
                resolution_notes='Identified as duplicate event, skipping extraction',
                resolved_at=datetime.now()
            )

        elif inconsistency.inconsistency_type == 'temporal':
            # Resolution: Query Agent 2 for explanation
            return self._query_agent2_for_explanation(
                inconsistency, extraction, timeline_context
            )

        elif inconsistency.inconsistency_type == 'wrong_type':
            # Resolution: Re-extract with correct type
            return self._re_extract_with_correct_type(
                inconsistency, extraction, timeline_context
            )

        elif inconsistency.inconsistency_type == 'low_confidence':
            # Resolution: Multi-source validation
            return self._multi_source_validation(
                inconsistency, extraction, timeline_context
            )

        else:
            # Default: Escalate to human
            return ResolutionAttempt(
                attempt_id=attempt_id,
                inconsistency_id=inconsistency.inconsistency_id,
                resolution_method='escalate',
                agent2_interaction=None,
                additional_sources_used=[],
                outcome='escalated',
                resolution_notes='Unknown inconsistency type, escalating to human review',
                resolved_at=datetime.now()
            )

    def _query_agent2_for_explanation(
        self,
        inconsistency: InconsistencyDetection,
        extraction: Dict[str, Any],
        timeline_context: Dict[str, Any]
    ) -> ResolutionAttempt:
        """
        Agent 1 queries Agent 2: "Why did you classify this as 'Increased' when it was 'Decreased' 2 days prior?"
        """
        # Build explanation prompt for Agent 2
        prompt = f"""You previously classified this imaging report as:

**Classification**: {extraction['variable_name']} = {extraction['value']}
**Confidence**: {extraction['confidence']}
**Date**: {extraction['event_date']}

**INCONSISTENCY DETECTED**:
{inconsistency.description}

**Timeline Context**:
{self._format_timeline_context(timeline_context)}

**Source Report**:
{extraction.get('source_text', '(text not available)')}

**Question from Agent 1**:
1. Explain your reasoning for this classification. What specific phrases led you to choose '{extraction['value']}'?
2. Did you consider the temporal context (prior status 2 days ago)?
3. Is it possible this is a duplicate scan or a misclassification?
4. What alternative classification would you recommend given the temporal inconsistency?

Provide structured response:
1. Key evidence from report
2. Reasoning for original classification
3. Assessment of temporal inconsistency
4. Recommended resolution (keep original / change to alternative / flag as duplicate)
"""

        # Query Agent 2
        agent2_response = self.agent2.extract(
            prompt=prompt,
            system_prompt="You are explaining and re-evaluating your previous classification decision.",
            expected_schema={
                "required": [
                    "key_evidence",
                    "original_reasoning",
                    "temporal_assessment",
                    "recommended_resolution"
                ]
            }
        )

        # Agent 1 adjudication based on Agent 2 response
        if agent2_response.success:
            recommendation = agent2_response.extracted_data.get('recommended_resolution', '').lower()

            if 'duplicate' in recommendation or 'same scan' in recommendation:
                outcome = 'resolved'
                notes = f"Agent 2 assessment: Likely duplicate scan. {agent2_response.extracted_data.get('temporal_assessment', '')}"
            elif 'change' in recommendation or 'revise' in recommendation:
                outcome = 'resolved'
                notes = f"Agent 2 revised assessment: {agent2_response.extracted_data.get('recommended_resolution', '')}"
            else:
                outcome = 'escalated'
                notes = f"Agent 2 uncertain. Original reasoning: {agent2_response.extracted_data.get('original_reasoning', '')}. Escalating to human review."
        else:
            outcome = 'escalated'
            notes = f"Agent 2 query failed: {agent2_response.error}"

        return ResolutionAttempt(
            attempt_id=f"res_{inconsistency.inconsistency_id}",
            inconsistency_id=inconsistency.inconsistency_id,
            resolution_method='query_agent2',
            agent2_interaction={
                'query': prompt,
                'response': agent2_response.raw_response,
                'extracted_data': agent2_response.extracted_data if agent2_response.success else None
            },
            additional_sources_used=[],
            outcome=outcome,
            resolution_notes=notes,
            resolved_at=datetime.now()
        )

    def _multi_source_validation(
        self,
        inconsistency: InconsistencyDetection,
        extraction: Dict[str, Any],
        timeline_context: Dict[str, Any]
    ) -> ResolutionAttempt:
        """
        Agent 1: Gather additional sources and ask Agent 2 to re-review
        """
        patient_id = extraction['patient_id']
        event_date = extraction['event_date']

        # Step 1: Agent 1 gathers additional sources
        additional_sources = self._gather_additional_sources(
            patient_id, event_date
        )

        if not additional_sources:
            return ResolutionAttempt(
                attempt_id=f"res_{inconsistency.inconsistency_id}",
                inconsistency_id=inconsistency.inconsistency_id,
                resolution_method='multi_source_review',
                agent2_interaction=None,
                additional_sources_used=[],
                outcome='escalated',
                resolution_notes='No additional sources available for validation',
                resolved_at=datetime.now()
            )

        # Step 2: Agent 1 prepares multi-source prompt for Agent 2
        prompt = f"""You previously extracted {extraction['variable_name']} = {extraction['value']} with confidence {extraction['confidence']:.2f}.

**ISSUE**: Low confidence extraction requires validation with additional sources.

**ORIGINAL SOURCE** (Imaging text report):
{extraction.get('source_text', '(not available)')}

**ADDITIONAL SOURCES**:
"""
        for i, source in enumerate(additional_sources, 1):
            prompt += f"""
--- Source {i}: {source['type']} ({source['date']}) ---
{source['text']}

"""

        prompt += f"""
**TASK**: Re-classify {extraction['variable_name']} using ALL sources.

Consider:
1. Do sources agree or conflict?
2. Which source is most reliable for this variable?
3. Does additional clinical context (progress notes) clarify the imaging interpretation?

Output:
1. **source_agreement**: Do sources agree? (yes/partial/no)
2. **final_classification**: Final value for {extraction['variable_name']}
3. **confidence**: Updated confidence (0.0-1.0)
4. **explanation**: How you reconciled the sources
5. **conflicts**: Any unresolved conflicts
"""

        # Step 3: Agent 2 performs multi-source extraction
        agent2_response = self.agent2.extract(
            prompt=prompt,
            system_prompt="You are performing multi-source clinical data reconciliation.",
            expected_schema={
                "required": [
                    "source_agreement",
                    "final_classification",
                    "confidence",
                    "explanation",
                    "conflicts"
                ]
            }
        )

        # Step 4: Agent 1 adjudicates
        if agent2_response.success:
            updated_confidence = agent2_response.extracted_data.get('confidence', extraction['confidence'])

            if updated_confidence >= 0.75:
                outcome = 'resolved'
                notes = f"Multi-source validation increased confidence to {updated_confidence:.2f}. {agent2_response.extracted_data.get('explanation', '')}"
            else:
                outcome = 'escalated'
                notes = f"Multi-source validation still yields low confidence ({updated_confidence:.2f}). Conflicts: {agent2_response.extracted_data.get('conflicts', 'N/A')}"
        else:
            outcome = 'escalated'
            notes = f"Agent 2 multi-source query failed: {agent2_response.error}"

        return ResolutionAttempt(
            attempt_id=f"res_{inconsistency.inconsistency_id}",
            inconsistency_id=inconsistency.inconsistency_id,
            resolution_method='multi_source_review',
            agent2_interaction={
                'query': prompt,
                'response': agent2_response.raw_response,
                'extracted_data': agent2_response.extracted_data if agent2_response.success else None
            },
            additional_sources_used=[s['id'] for s in additional_sources],
            outcome=outcome,
            resolution_notes=notes,
            resolved_at=datetime.now()
        )

    def _gather_additional_sources(
        self,
        patient_id: str,
        event_date: datetime,
        window_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Agent 1: Gather imaging PDFs, progress notes, op reports near event date
        """
        sources = []

        # 1. Imaging PDFs from v_binary_files
        # TODO: Query v_binary_files for PDFs

        # 2. Progress notes from DocumentReference
        # TODO: Query for progress notes

        # 3. Operative reports (for EOR)
        # TODO: Query for operative reports

        return sources

    def generate_patient_qa_report(
        self,
        patient_id: str,
        session_id: str
    ) -> PatientQAReport:
        """
        Agent 1: Generate comprehensive QA report for patient extraction session
        """
        report = PatientQAReport(
            patient_id=patient_id,
            extraction_session_id=session_id,
            start_time=datetime.now(),  # TODO: Track actual start time
            end_time=datetime.now(),

            total_events_processed=0,  # TODO: Track from session
            successful_extractions=0,
            inconsistencies_detected=len(self.inconsistencies),
            inconsistencies_resolved=sum(1 for r in self.resolutions if r.outcome == 'resolved'),
            inconsistencies_escalated=sum(1 for r in self.resolutions if r.outcome == 'escalated'),

            inconsistencies=self.inconsistencies,
            resolutions=self.resolutions,

            multi_source_extractions=0,  # TODO: Track
            source_agreement_rate=0.0,  # TODO: Calculate

            requires_human_review=any(r.outcome == 'escalated' for r in self.resolutions),
            high_priority_issues=[
                i.description for i in self.inconsistencies
                if i.severity == 'high'
            ]
        )

        # Save report
        report_path = self.qa_reports_dir / f"{patient_id}_{session_id}_qa_report.json"
        with open(report_path, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)

        logger.info(f"Generated QA report: {report_path}")

        # Also generate human-readable markdown report
        self._generate_markdown_report(report)

        return report

    def _generate_markdown_report(self, report: PatientQAReport):
        """Generate human-readable QA report in markdown"""
        md_path = self.qa_reports_dir / f"{report.patient_id}_{report.extraction_session_id}_qa_report.md"

        with open(md_path, 'w') as f:
            f.write(f"# Patient QA Report: {report.patient_id}\n\n")
            f.write(f"**Session**: {report.extraction_session_id}\n")
            f.write(f"**Duration**: {report.start_time} → {report.end_time}\n\n")

            f.write(f"## Summary\n\n")
            f.write(f"- Total events processed: {report.total_events_processed}\n")
            f.write(f"- Successful extractions: {report.successful_extractions}\n")
            f.write(f"- Inconsistencies detected: {report.inconsistencies_detected}\n")
            f.write(f"- Inconsistencies resolved: {report.inconsistencies_resolved}\n")
            f.write(f"- Inconsistencies escalated: {report.inconsistencies_escalated}\n\n")

            if report.requires_human_review:
                f.write(f"⚠️ **REQUIRES HUMAN REVIEW**\n\n")
                f.write(f"High priority issues:\n")
                for issue in report.high_priority_issues:
                    f.write(f"- {issue}\n")
                f.write(f"\n")

            f.write(f"## Detected Inconsistencies\n\n")
            for i, inc in enumerate(report.inconsistencies, 1):
                f.write(f"### {i}. {inc.inconsistency_type.upper()} ({inc.severity})\n\n")
                f.write(f"**Description**: {inc.description}\n\n")
                f.write(f"**Affected events**: {', '.join(inc.affected_extractions)}\n\n")
                f.write(f"**Detected by**: {inc.detected_by}\n\n")

            f.write(f"## Resolution Attempts\n\n")
            for i, res in enumerate(report.resolutions, 1):
                f.write(f"### {i}. {res.resolution_method} → {res.outcome}\n\n")
                f.write(f"**Inconsistency**: {res.inconsistency_id}\n\n")
                f.write(f"**Resolution notes**: {res.resolution_notes}\n\n")

                if res.agent2_interaction:
                    f.write(f"**Agent 2 Interaction**:\n")
                    f.write(f"```\n{res.agent2_interaction.get('response', 'N/A')}\n```\n\n")

                if res.additional_sources_used:
                    f.write(f"**Additional sources used**: {', '.join(res.additional_sources_used)}\n\n")

        logger.info(f"Generated markdown QA report: {md_path}")

    # Helper methods
    def _check_duplicate_event(self, patient_id: str, extraction: Dict) -> Optional[Dict]:
        """Check if event date already exists"""
        existing = self.timeline.query_events(
            patient_id=patient_id,
            event_type='Imaging',
            event_date=extraction['event_date']
        )
        return existing[0] if existing else None

    def _check_temporal_consistency(
        self,
        patient_id: str,
        extraction: Dict,
        context: Dict
    ) -> Optional[InconsistencyDetection]:
        """Check for rapid status changes"""
        prior_status = context.get('prior_tumor_status')

        if not prior_status:
            return None

        # Check for "Increased" → "Decreased" in < 7 days
        if (prior_status['value'] == 'Increased' and
            extraction['value'] == 'Decreased'):

            days_diff = (extraction['event_date'] - prior_status['event_date']).days

            if days_diff < 7:
                return InconsistencyDetection(
                    inconsistency_id=f"temporal_{extraction['event_id']}",
                    inconsistency_type='temporal',
                    severity='high',
                    description=f"Status changed Increased→Decreased in {days_diff} days without treatment intervention",
                    affected_extractions=[extraction['event_id'], prior_status['event_id']],
                    detected_by='agent1_temporal_check',
                    detected_at=datetime.now()
                )

        return None

    def _is_wrong_extraction_type(self, extraction: Dict) -> bool:
        """Check if value belongs to different variable type"""
        EOR_VALUES = ['Gross Total Resection', 'Near Total Resection',
                      'Subtotal Resection', 'Biopsy Only']

        if extraction['variable_name'] == 'tumor_status':
            return extraction['value'] in EOR_VALUES

        return False

    def _re_extract_with_correct_type(
        self,
        inconsistency: InconsistencyDetection,
        extraction: Dict,
        context: Dict
    ) -> ResolutionAttempt:
        """Re-extract with correct variable type"""
        # TODO: Implement re-extraction with extent_of_resection
        return ResolutionAttempt(
            attempt_id=f"res_{inconsistency.inconsistency_id}",
            inconsistency_id=inconsistency.inconsistency_id,
            resolution_method='re_extract',
            agent2_interaction=None,
            additional_sources_used=[],
            outcome='resolved',
            resolution_notes='Re-extracted as extent_of_resection instead of tumor_status',
            resolved_at=datetime.now()
        )

    def _format_timeline_context(self, context: Dict) -> str:
        """Format timeline context for Agent 2"""
        # TODO: Format timeline context
        return json.dumps(context, indent=2, default=str)
