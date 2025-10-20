"""
Agent 1 Multi-Source Extent of Resection (EOR) Adjudication

Agent 1 responsibility: Reconcile EOR assessments from multiple sources:
1. Operative report (GOLD STANDARD)
2. Post-operative imaging (within 72 hours)
3. Surgeon's procedure notes

Adjudication hierarchy:
- Operative report > Post-op imaging > Intraoperative assessment
- If discrepancy, Agent 1 queries Agent 2 for clarification
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EORSource:
    """Single source of EOR assessment"""
    source_type: str  # 'operative_report', 'postop_imaging', 'procedure_note'
    source_id: str
    source_date: datetime
    eor: str  # 'Gross Total Resection', 'Near Total Resection', 'Partial Resection', 'Biopsy Only'
    confidence: float
    evidence: str
    extracted_by: str  # 'agent2', 'structured_data'


@dataclass
class EORAdjudication:
    """Result of multi-source EOR adjudication"""
    procedure_id: str
    procedure_date: datetime
    final_eor: str
    confidence: float
    primary_source: str  # Which source was used for final determination
    sources_assessed: List[EORSource]
    agreement: str  # 'full_agreement', 'partial_agreement', 'discrepancy'
    discrepancy_notes: Optional[str]
    agent2_queries: List[Dict[str, Any]]  # Queries sent to Agent 2 for clarification
    adjudication_reasoning: str


class EORAdjudicator:
    """
    Agent 1 adjudicator for multi-source EOR reconciliation.
    """

    # Source hierarchy (higher priority first)
    SOURCE_HIERARCHY = [
        'operative_report',
        'postop_imaging',
        'procedure_note'
    ]

    # EOR categories and their equivalences
    EOR_EQUIVALENTS = {
        'Gross Total Resection': {'GTR', 'Gross Total Resection', 'Complete resection'},
        'Near Total Resection': {'Near Total Resection', 'Subtotal', 'STR', '90-99%'},
        'Partial Resection': {'Partial Resection', 'Partial', 'Debulking'},
        'Biopsy Only': {'Biopsy Only', 'Biopsy', 'Stereotactic biopsy'}
    }

    def __init__(self, medgemma_agent=None):
        """
        Args:
            medgemma_agent: Optional Agent 2 interface for clarification queries
        """
        self.agent2 = medgemma_agent
        self.agent2_queries = []

    def adjudicate_eor(
        self,
        procedure_id: str,
        procedure_date: datetime,
        eor_sources: List[EORSource]
    ) -> EORAdjudication:
        """
        Adjudicate EOR from multiple sources.

        Args:
            procedure_id: Procedure FHIR ID
            procedure_date: Date of surgery
            eor_sources: List of EOR assessments from different sources

        Returns:
            EORAdjudication with final EOR determination
        """
        logger.info(f"Adjudicating EOR for procedure {procedure_id} with {len(eor_sources)} sources")

        if not eor_sources:
            return EORAdjudication(
                procedure_id=procedure_id,
                procedure_date=procedure_date,
                final_eor='Unknown',
                confidence=0.0,
                primary_source='none',
                sources_assessed=[],
                agreement='no_sources',
                discrepancy_notes='No EOR sources available',
                agent2_queries=[],
                adjudication_reasoning='No sources provided for EOR assessment'
            )

        # Sort sources by hierarchy
        sorted_sources = self._sort_by_hierarchy(eor_sources)

        # Check for agreement across sources
        agreement_status, discrepancy_notes = self._assess_agreement(sorted_sources)

        # Select primary source (highest priority with highest confidence)
        primary_source = sorted_sources[0]

        # If discrepancy, may query Agent 2 for clarification
        agent2_queries = []
        if agreement_status == 'discrepancy' and self.agent2:
            agent2_queries = self._query_agent2_for_clarification(
                procedure_id,
                sorted_sources
            )

        # Determine final EOR
        final_eor, reasoning = self._determine_final_eor(
            sorted_sources,
            agreement_status,
            agent2_queries
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            primary_source,
            agreement_status,
            len(sorted_sources)
        )

        return EORAdjudication(
            procedure_id=procedure_id,
            procedure_date=procedure_date,
            final_eor=final_eor,
            confidence=confidence,
            primary_source=primary_source.source_type,
            sources_assessed=sorted_sources,
            agreement=agreement_status,
            discrepancy_notes=discrepancy_notes,
            agent2_queries=agent2_queries,
            adjudication_reasoning=reasoning
        )

    def _sort_by_hierarchy(self, sources: List[EORSource]) -> List[EORSource]:
        """Sort sources by priority hierarchy."""
        def priority_key(source):
            try:
                hierarchy_rank = self.SOURCE_HIERARCHY.index(source.source_type)
            except ValueError:
                hierarchy_rank = 999  # Unknown source type goes last

            # Within same source type, prioritize higher confidence
            return (hierarchy_rank, -source.confidence)

        return sorted(sources, key=priority_key)

    def _assess_agreement(self, sources: List[EORSource]) -> tuple[str, Optional[str]]:
        """
        Assess level of agreement across sources.

        Returns:
            (agreement_status, discrepancy_notes)
        """
        if len(sources) == 1:
            return ('single_source', None)

        # Normalize EOR values to canonical forms
        normalized_eors = [self._normalize_eor(s.eor) for s in sources]

        # Check for full agreement
        if len(set(normalized_eors)) == 1:
            return ('full_agreement', None)

        # Check for partial agreement (e.g., GTR vs Near Total)
        if self._is_partial_agreement(normalized_eors):
            discrepancy = f"Partial agreement: {', '.join([f'{s.source_type}={s.eor}' for s in sources])}"
            return ('partial_agreement', discrepancy)

        # Full discrepancy
        discrepancy = f"Discrepancy: {', '.join([f'{s.source_type}={s.eor}' for s in sources])}"
        return ('discrepancy', discrepancy)

    def _normalize_eor(self, eor: str) -> str:
        """Normalize EOR to canonical category."""
        for canonical, equivalents in self.EOR_EQUIVALENTS.items():
            if eor in equivalents or eor == canonical:
                return canonical
        return eor  # Return as-is if no match

    def _is_partial_agreement(self, normalized_eors: List[str]) -> bool:
        """
        Check if EORs represent partial agreement.

        Partial agreement cases:
        - GTR vs Near Total (both high resection)
        - Near Total vs Partial (both incomplete)
        """
        eor_set = set(normalized_eors)

        partial_agreement_sets = [
            {'Gross Total Resection', 'Near Total Resection'},
            {'Near Total Resection', 'Partial Resection'}
        ]

        return eor_set in partial_agreement_sets

    def _query_agent2_for_clarification(
        self,
        procedure_id: str,
        sources: List[EORSource]
    ) -> List[Dict[str, Any]]:
        """
        Query Agent 2 for clarification when discrepancy exists.

        Returns:
            List of Agent 2 query/response pairs
        """
        if not self.agent2:
            return []

        queries = []

        # Example query to Agent 2
        query = {
            'query_type': 'eor_discrepancy_clarification',
            'procedure_id': procedure_id,
            'discrepancy': f"Operative report says '{sources[0].eor}' but imaging shows '{sources[1].eor}'",
            'request': 'Please re-review both sources and explain which EOR is more reliable and why'
        }

        # Placeholder for actual Agent 2 interaction
        # In production: response = self.agent2.query(query)
        response = {
            'agent2_response': 'Placeholder - would query Agent 2 via Ollama',
            'timestamp': datetime.now().isoformat()
        }

        queries.append({'query': query, 'response': response})
        self.agent2_queries.append(queries[-1])

        return queries

    def _determine_final_eor(
        self,
        sources: List[EORSource],
        agreement_status: str,
        agent2_queries: List[Dict[str, Any]]
    ) -> tuple[str, str]:
        """
        Determine final EOR and reasoning.

        Returns:
            (final_eor, reasoning)
        """
        primary_source = sources[0]

        if agreement_status == 'full_agreement':
            return (
                primary_source.eor,
                f"All {len(sources)} sources agree: {primary_source.eor}"
            )

        if agreement_status == 'partial_agreement':
            # Use highest priority source
            return (
                primary_source.eor,
                f"Partial agreement across sources. Using {primary_source.source_type} as primary source (highest priority)."
            )

        if agreement_status == 'discrepancy':
            # Use operative report if available, otherwise highest priority
            operative_report_source = next(
                (s for s in sources if s.source_type == 'operative_report'),
                None
            )

            if operative_report_source:
                return (
                    operative_report_source.eor,
                    f"Discrepancy detected. Using operative report (gold standard): {operative_report_source.eor}"
                )
            else:
                return (
                    primary_source.eor,
                    f"Discrepancy detected without operative report. Using {primary_source.source_type}: {primary_source.eor}"
                )

        # Single source
        return (
            primary_source.eor,
            f"Single source available: {primary_source.source_type}"
        )

    def _calculate_confidence(
        self,
        primary_source: EORSource,
        agreement_status: str,
        num_sources: int
    ) -> float:
        """
        Calculate confidence in final EOR determination.

        Higher confidence when:
        - Multiple sources agree
        - Operative report available
        - High source confidence
        """
        base_confidence = primary_source.confidence

        # Boost for agreement
        if agreement_status == 'full_agreement':
            base_confidence = min(1.0, base_confidence + 0.1 * (num_sources - 1))
        elif agreement_status == 'partial_agreement':
            base_confidence = min(1.0, base_confidence + 0.05 * (num_sources - 1))

        # Boost for operative report
        if primary_source.source_type == 'operative_report':
            base_confidence = min(1.0, base_confidence + 0.05)

        # Penalty for discrepancy
        if agreement_status == 'discrepancy':
            base_confidence *= 0.85

        return round(base_confidence, 2)

    def generate_adjudication_report(self, adjudication: EORAdjudication) -> str:
        """
        Generate human-readable adjudication report.

        Args:
            adjudication: EORAdjudication result

        Returns:
            Markdown-formatted report
        """
        report = f"""## EOR Adjudication Report

**Procedure:** {adjudication.procedure_id}
**Date:** {adjudication.procedure_date.strftime('%Y-%m-%d')}

### Final Determination
- **EOR:** {adjudication.final_eor}
- **Confidence:** {adjudication.confidence:.2f}
- **Primary Source:** {adjudication.primary_source}

### Sources Assessed ({len(adjudication.sources_assessed)})

"""

        for i, source in enumerate(adjudication.sources_assessed, 1):
            report += f"{i}. **{source.source_type}** ({source.source_date.strftime('%Y-%m-%d')})\n"
            report += f"   - EOR: {source.eor}\n"
            report += f"   - Confidence: {source.confidence:.2f}\n"
            report += f"   - Evidence: {source.evidence[:100]}...\n\n"

        report += f"""### Agreement Analysis
- **Status:** {adjudication.agreement}
"""

        if adjudication.discrepancy_notes:
            report += f"- **Notes:** {adjudication.discrepancy_notes}\n"

        report += f"\n### Adjudication Reasoning\n{adjudication.adjudication_reasoning}\n"

        if adjudication.agent2_queries:
            report += f"\n### Agent 2 Clarification Queries ({len(adjudication.agent2_queries)})\n"
            for i, q in enumerate(adjudication.agent2_queries, 1):
                report += f"{i}. Query: {q['query'].get('request', 'N/A')}\n"

        return report
