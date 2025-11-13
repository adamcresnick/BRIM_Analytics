#!/usr/bin/env python3
"""
LLM Output Validator - V5.4

Validates LLM outputs (WHO section recommendations) against biological plausibility rules.
Raises coherence issues to Claude agent for intelligent decision-making rather than
automatically overriding results.

This validator integrates into Phase 0 multi-agent workflow:
1. MedGemma recommends WHO section
2. Validator checks biological coherence
3. If incoherent, raises issue to Claude agent with:
   - Specific biological concern
   - Alternative suggestions
   - Confidence levels
4. Claude agent makes final decision with full context

Usage:
    from lib.llm_output_validator import LLMOutputValidator, CoherenceIssue

    validator = LLMOutputValidator()

    # After MedGemma Phase 0.2 WHO section recommendation
    coherence_result = validator.validate_who_section_coherence(
        recommended_section=13,
        molecular_markers=['BRAF V600E', 'CDKN2A/B deletion'],
        diagnosis_text='posterior fossa tumor'
    )

    if not coherence_result.is_coherent:
        # Raise to Claude agent for decision
        logger.warning(f"⚠️ COHERENCE ISSUE: {coherence_result.issue.description}")
        logger.warning(f"   Suggestion: {coherence_result.issue.suggested_action}")

        # Claude agent reviews and decides whether to:
        # - Accept MedGemma recommendation despite warning
        # - Use suggested alternative section
        # - Request additional MedGemma analysis
"""

import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for coherence issues."""
    INFO = 1       # Minor inconsistency, likely acceptable
    WARNING = 2    # Moderate concern, review recommended
    CRITICAL = 3   # Major biological implausibility, strong review needed


@dataclass
class CoherenceIssue:
    """
    Biological coherence issue raised by validator.

    Attributes:
        severity: Issue severity level
        rule_violated: Name of validation rule that was violated
        description: Human-readable description of the issue
        biological_rationale: Why this is biologically implausible
        recommended_section: Suggested alternative WHO section (if applicable)
        recommended_subtype: Suggested subtype (if applicable)
        confidence: Confidence in this issue (0.0-1.0)
        suggested_action: What Claude agent should consider
    """
    severity: IssueSeverity
    rule_violated: str
    description: str
    biological_rationale: str
    recommended_section: Optional[int]
    recommended_subtype: Optional[str]
    confidence: float
    suggested_action: str


@dataclass
class CoherenceValidationResult:
    """
    Result of coherence validation.

    Attributes:
        is_coherent: Whether recommendation is biologically coherent
        confidence_score: Overall confidence in coherence (0.0-1.0, where 1.0 = fully coherent)
        issue: CoherenceIssue if incoherent, None if coherent
        rules_checked: List of validation rules that were checked
        metadata: Additional validation metadata
    """
    is_coherent: bool
    confidence_score: float
    issue: Optional[CoherenceIssue]
    rules_checked: List[str]
    metadata: Dict[str, Any]


class LLMOutputValidator:
    """
    Validator for LLM outputs with biological knowledge base.

    Checks WHO section recommendations against molecular marker patterns
    and raises issues to Claude agent for intelligent decision-making.
    """

    def __init__(self):
        """Initialize validator with biological validation rules."""
        self.validation_rules = self._load_validation_rules()
        logger.info(f"Initialized LLMOutputValidator with {len(self.validation_rules)} validation rules")

    def _load_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """
        Load biological validation rules.

        Returns:
            Dictionary mapping marker patterns to validation rules
        """
        return {
            # BRAF V600E mutation
            'BRAF V600E': {
                'valid_sections': {9, 11},  # Pediatric gliomas, Glioneuronal
                'invalid_sections': {10, 13},  # Medulloblastoma, Ependymoma
                'rationale': 'BRAF V600E mutation is rare in medulloblastoma and ependymoma. '
                           'Strongly associated with pediatric-type diffuse gliomas (Section 9) '
                           'and glioneuronal/neuronal tumors (Section 11).',
                'confidence': 0.95,
                'severity': IssueSeverity.CRITICAL
            },

            # WNT pathway activation
            'WNT pathway': {
                'valid_sections': {10},  # Only Medulloblastoma
                'required_subtype': 'WNT-activated',
                'invalid_sections': {2, 3, 4, 9, 11, 13},
                'rationale': 'WNT pathway activation is specific to WNT-activated medulloblastoma. '
                           'Not found in adult gliomas, pediatric gliomas, or ependymomas.',
                'confidence': 0.99,
                'severity': IssueSeverity.CRITICAL
            },

            # CTNNB1 mutation (beta-catenin)
            'CTNNB1': {
                'valid_sections': {10},  # WNT medulloblastoma
                'required_subtype': 'WNT-activated',
                'rationale': 'CTNNB1 mutations are hallmark of WNT-activated medulloblastoma.',
                'confidence': 0.99,
                'severity': IssueSeverity.CRITICAL
            },

            # IDH1/IDH2 mutations
            'IDH': {
                'valid_sections': {2, 3, 4},  # Adult-type diffuse gliomas
                'invalid_sections': {10, 13},  # Embryonal, Ependymal
                'rationale': 'IDH1/IDH2 mutations define adult-type diffuse gliomas. '
                           'Never found in embryonal tumors (medulloblastoma) or ependymomas.',
                'confidence': 0.99,
                'severity': IssueSeverity.CRITICAL
            },

            # 1p/19q codeletion
            '1p/19q': {
                'valid_sections': {3},  # Only Oligodendroglioma
                'invalid_sections': {2, 4, 10, 13},
                'rationale': '1p/19q codeletion is a defining marker for oligodendroglioma. '
                           'Not found in astrocytomas, embryonal, or ependymal tumors.',
                'confidence': 0.99,
                'severity': IssueSeverity.CRITICAL
            },

            # H3 K27-altered
            'H3 K27': {
                'valid_sections': {5, 12},  # Diffuse midline glioma, Paediatric hemispheric
                'invalid_sections': {10, 13},
                'rationale': 'H3 K27-altered (K27M) mutation is specific to diffuse midline glioma '
                           'and some paediatric-type hemispheric gliomas. Not found in '
                           'embryonal or ependymal tumors.',
                'confidence': 0.95,
                'severity': IssueSeverity.CRITICAL
            },

            # H3 G34-altered
            'H3 G34': {
                'valid_sections': {12},  # Paediatric-type hemispheric glioma
                'invalid_sections': {10, 13},
                'rationale': 'H3 G34-altered mutation specific to paediatric-type hemispheric '
                           'diffuse high-grade gliomas.',
                'confidence': 0.95,
                'severity': IssueSeverity.CRITICAL
            },

            # MYCN amplification
            'MYCN': {
                'valid_sections': {10},  # Medulloblastoma (any subtype, but esp. Group 3/4)
                'rationale': 'MYCN amplification most common in medulloblastoma (Group 3/4), '
                           'rare in other CNS tumors.',
                'confidence': 0.85,
                'severity': IssueSeverity.WARNING
            },

            # TP53 mutation
            'TP53': {
                'valid_sections': {2, 4, 9, 10, 12},  # Various gliomas and medulloblastoma
                'rationale': 'TP53 mutations found across multiple tumor types. '
                           'Common in astrocytomas, glioblastomas, some pediatric gliomas, '
                           'and medulloblastoma (SHH subtype with germline TP53).',
                'confidence': 0.70,
                'severity': IssueSeverity.INFO
            },

            # ATRX loss
            'ATRX': {
                'valid_sections': {2, 4, 9},  # Adult and pediatric gliomas
                'invalid_sections': {10, 13},  # Not in embryonal or ependymal
                'rationale': 'ATRX loss associated with astrocytic lineage gliomas. '
                           'Found in adult-type and pediatric-type gliomas, not embryonal tumors.',
                'confidence': 0.90,
                'severity': IssueSeverity.CRITICAL
            },

            # EGFR amplification
            'EGFR': {
                'valid_sections': {4},  # Glioblastoma, IDH-wildtype
                'rationale': 'EGFR amplification is hallmark of glioblastoma, IDH-wildtype. '
                           'Rare in other CNS tumors.',
                'confidence': 0.90,
                'severity': IssueSeverity.WARNING
            },

            # TERT promoter mutation
            'TERT': {
                'valid_sections': {3, 4},  # Oligodendroglioma, Glioblastoma
                'rationale': 'TERT promoter mutations common in oligodendroglioma (with 1p/19q) '
                           'and glioblastoma, IDH-wildtype.',
                'confidence': 0.85,
                'severity': IssueSeverity.WARNING
            },

            # MGMT promoter methylation
            'MGMT': {
                'valid_sections': {2, 3, 4},  # Adult-type diffuse gliomas
                'rationale': 'MGMT promoter methylation is prognostic marker in adult-type '
                           'diffuse gliomas. Common across astrocytoma, oligodendroglioma, '
                           'and glioblastoma.',
                'confidence': 0.75,
                'severity': IssueSeverity.INFO
            }
        }

    def validate_who_section_coherence(
        self,
        recommended_section: int,
        molecular_markers: List[str],
        diagnosis_text: Optional[str] = None
    ) -> CoherenceValidationResult:
        """
        Validate coherence of WHO section recommendation with molecular markers.

        Checks whether the recommended WHO section is biologically plausible
        given the molecular markers detected. Raises issues to Claude agent
        for intelligent decision-making.

        Args:
            recommended_section: WHO CNS5 section number recommended by MedGemma
            molecular_markers: List of molecular markers detected (e.g., ['BRAF V600E', 'CTNNB1 mutation'])
            diagnosis_text: Optional diagnosis text for additional context

        Returns:
            CoherenceValidationResult with validation outcome and any issues
        """
        logger.info(f"Validating WHO section {recommended_section} coherence with markers: {molecular_markers}")

        # Track rules checked
        rules_checked = []
        issues_found = []

        # Normalize markers for matching
        normalized_markers = self._normalize_markers(molecular_markers)

        # Check each detected marker against validation rules
        for marker, rule in self.validation_rules.items():
            # Check if this marker is present in the patient's markers
            if not self._marker_present(marker, normalized_markers):
                continue

            rules_checked.append(marker)

            # Check valid sections
            valid_sections = rule.get('valid_sections', set())
            invalid_sections = rule.get('invalid_sections', set())

            # Check if recommended section is explicitly invalid
            if invalid_sections and recommended_section in invalid_sections:
                issue = CoherenceIssue(
                    severity=rule['severity'],
                    rule_violated=marker,
                    description=f"Marker '{marker}' detected, but WHO Section {recommended_section} is biologically implausible",
                    biological_rationale=rule['rationale'],
                    recommended_section=list(valid_sections)[0] if valid_sections else None,
                    recommended_subtype=rule.get('required_subtype'),
                    confidence=rule['confidence'],
                    suggested_action=f"Consider WHO Section {list(valid_sections)} instead. "
                                   f"Review MedGemma reasoning or request additional analysis."
                )
                issues_found.append(issue)

            # Check if recommended section is missing from valid sections (less strict)
            elif valid_sections and recommended_section not in valid_sections:
                # Only raise issue if confidence is high
                if rule['confidence'] >= 0.90:
                    issue = CoherenceIssue(
                        severity=IssueSeverity.WARNING,
                        rule_violated=marker,
                        description=f"Marker '{marker}' strongly suggests WHO Section {list(valid_sections)}, "
                                  f"but Section {recommended_section} was recommended",
                        biological_rationale=rule['rationale'],
                        recommended_section=list(valid_sections)[0] if valid_sections else None,
                        recommended_subtype=rule.get('required_subtype'),
                        confidence=rule['confidence'],
                        suggested_action=f"Review whether Section {recommended_section} is appropriate, "
                                       f"or consider Section {list(valid_sections)}."
                    )
                    issues_found.append(issue)

        # Determine overall coherence
        if not issues_found:
            # No issues found - coherent
            return CoherenceValidationResult(
                is_coherent=True,
                confidence_score=1.0,
                issue=None,
                rules_checked=rules_checked,
                metadata={
                    'recommended_section': recommended_section,
                    'markers_validated': len(rules_checked),
                    'validation_passed': True
                }
            )
        else:
            # Issues found - return most severe issue
            most_severe_issue = max(issues_found, key=lambda i: (i.severity.value, i.confidence))

            # Calculate confidence score (inverse of most severe issue confidence)
            confidence_score = 1.0 - most_severe_issue.confidence

            return CoherenceValidationResult(
                is_coherent=False,
                confidence_score=confidence_score,
                issue=most_severe_issue,
                rules_checked=rules_checked,
                metadata={
                    'recommended_section': recommended_section,
                    'markers_validated': len(rules_checked),
                    'total_issues_found': len(issues_found),
                    'all_issues': issues_found,
                    'validation_passed': False
                }
            )

    def _normalize_markers(self, markers: List[str]) -> Set[str]:
        """
        Normalize marker names for matching.

        Args:
            markers: List of marker names

        Returns:
            Set of normalized marker names (uppercase, spaces removed)
        """
        normalized = set()
        for marker in markers:
            # Uppercase and remove extra spaces
            normalized.add(marker.upper().strip())
        return normalized

    def _marker_present(self, rule_marker: str, patient_markers: Set[str]) -> bool:
        """
        Check if rule marker is present in patient markers.

        Uses partial matching (e.g., "BRAF V600E" matches "BRAF V600E mutation").

        Args:
            rule_marker: Marker from validation rule
            patient_markers: Normalized patient markers

        Returns:
            True if marker present, False otherwise
        """
        rule_marker_normalized = rule_marker.upper()

        # Check for exact match or partial match
        for patient_marker in patient_markers:
            if rule_marker_normalized in patient_marker or patient_marker in rule_marker_normalized:
                return True

        return False

    def format_coherence_issue_for_agent(self, issue: CoherenceIssue) -> str:
        """
        Format coherence issue for presentation to Claude agent.

        Creates human-readable summary that Claude agent can use for
        decision-making within Phase 0 workflow.

        Args:
            issue: CoherenceIssue to format

        Returns:
            Formatted string for Claude agent
        """
        severity_emoji = {
            IssueSeverity.INFO: 'ℹ️',
            IssueSeverity.WARNING: '⚠️',
            IssueSeverity.CRITICAL: '🚨'
        }

        formatted = f"""
{severity_emoji[issue.severity]} COHERENCE ISSUE ({issue.severity.name})

Description: {issue.description}

Biological Rationale:
{issue.biological_rationale}

Rule Violated: {issue.rule_violated}
Confidence: {issue.confidence:.0%}

Suggested Action:
{issue.suggested_action}
"""

        if issue.recommended_section:
            formatted += f"\nRecommended Alternative: WHO Section {issue.recommended_section}"
            if issue.recommended_subtype:
                formatted += f" ({issue.recommended_subtype})"

        return formatted.strip()

    def get_validation_summary(self, result: CoherenceValidationResult) -> str:
        """
        Get human-readable validation summary.

        Args:
            result: CoherenceValidationResult

        Returns:
            Formatted summary string
        """
        if result.is_coherent:
            return f"✅ WHO Section {result.metadata['recommended_section']} is biologically coherent " \
                   f"with detected molecular markers ({result.metadata['markers_validated']} markers validated)."
        else:
            return f"⚠️ WHO Section {result.metadata['recommended_section']} has coherence issues. " \
                   f"See issue details for Claude agent review."
