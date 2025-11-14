#!/usr/bin/env python3
"""
Phase 0.4: Multi-Source Consistency Reviewer

Reviews all diagnostic evidence for consistency and flags concerns for human review.
This is NOT a pass/fail gate - it's a flagging and documentation layer.

Part of Phase 0 WHO 2021 Nomenclature Standardization redesign.

Usage:
    from lib.phase0_consistency_reviewer import ConsistencyReviewer

    reviewer = ConsistencyReviewer(medgemma_agent)
    review = reviewer.review_consistency(
        primary_diagnosis=phase0_2_output,
        who_translation=phase0_3_output,
        diagnostic_evidence=evidence_list
    )
"""

import logging
import json
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ConsistencyReviewer:
    """
    Phase 0.4: Review multi-source diagnostic evidence for consistency.

    Flags concerns for human review rather than failing.
    Reviews:
    - Cross-source consistency
    - Molecular-diagnosis coherence
    - Clinical plausibility
    - Evidence completeness
    """

    def __init__(self, medgemma_agent):
        """
        Initialize consistency reviewer.

        Args:
            medgemma_agent: MedGemma agent for reasoning tasks
        """
        self.medgemma_agent = medgemma_agent
        logger.info("✅ V5.6: Phase 0.4 Consistency Reviewer initialized")

    def review_consistency(
        self,
        primary_diagnosis: Dict[str, Any],
        who_translation: Dict[str, Any],
        diagnostic_evidence: List[Any],
        patient_age: int = None
    ) -> Dict[str, Any]:
        """
        Review all diagnostic evidence for consistency.

        Args:
            primary_diagnosis: Output from Phase 0.2
            who_translation: Output from Phase 0.3
            diagnostic_evidence: List of DiagnosisEvidence from Phase 0.1
            patient_age: Patient age if available (for plausibility checks)

        Returns:
            Dict with:
                - consistency_assessment: consistent / minor_discrepancies / significant_concerns
                - flags_for_review: List of flag objects
                - source_concordance: Agreement analysis
                - evidence_summary: Quality assessment
                - confidence_assessment: Final confidence with rationale
                - review_recommendation: no_review_needed / suggested_review / urgent_review
        """
        logger.info("   [Phase 0.4] Reviewing multi-source consistency and flagging concerns...")

        # Extract key information
        diagnosis = who_translation.get('who_2021_diagnosis', 'Unknown')
        markers = who_translation.get('key_markers', 'None')
        evidence_level = who_translation.get('evidence_level', 'unknown')
        source_concordance = primary_diagnosis.get('source_concordance', {})

        # V5.6: Extract temporal diagnostic events from Phase 0.2
        temporal_events_detected = primary_diagnosis.get('temporal_diagnostic_events_detected', False)
        temporal_events = primary_diagnosis.get('temporal_diagnostic_events', [])

        # Build review prompt
        review_prompt = f"""You are a clinical quality assurance specialist reviewing diagnostic evidence for consistency.

**YOUR ROLE:**
Review ALL diagnostic evidence and flag any concerns for human review.
This is NOT a pass/fail gate - you are documenting consistency and flagging issues.

**PRIMARY DIAGNOSIS (Phase 0.2):**
{json.dumps(primary_diagnosis, indent=2)}

**WHO 2021 TRANSLATION (Phase 0.3):**
{json.dumps(who_translation, indent=2)}

**ALL DIAGNOSTIC EVIDENCE (Phase 0.1):**
{self._format_evidence_for_review(diagnostic_evidence)}

**PATIENT AGE:** {patient_age if patient_age else 'Not documented'}

**TEMPORAL DIAGNOSTIC EVENTS (Phase 0.2):**
Temporal events detected: {temporal_events_detected}
{json.dumps(temporal_events, indent=2) if temporal_events else 'No temporal diagnostic changes identified'}

**REVIEW TASKS:**

1. **Cross-Source Consistency:**
   - Do genomics, pathology, clinical notes agree on the diagnosis?
   - Are there contradictions worth noting?
   - Is concordance expected or is there unusual discordance?

2. **Molecular-Diagnosis Coherence:**
   - Do the molecular markers fit the diagnosis?
   - Examples of COHERENT pairings:
     - PTCH1 mutation + medulloblastoma = ✓ (SHH pathway marker)
     - IDH mutation + astrocytoma = ✓
     - 1p/19q codeletion + oligodendroglioma = ✓
   - Examples of INCOHERENT pairings (FLAG):
     - PTCH1 mutation + glioblastoma = ✗ (wrong tumor family)
     - IDH mutation + medulloblastoma = ✗ (doesn't occur in embryonal tumors)
     - BRAF V600E + medulloblastoma = ? (unusual, flag for review)

3. **Clinical Plausibility:**
   - Age-diagnosis fit:
     - Pediatric (0-18): Medulloblastoma, ATRT, ependymoma common; GBM rare
     - Adult (>40): Glioblastoma common; medulloblastoma rare
   - Flags for unusual combinations (not impossible, just warrant review)

4. **Evidence Completeness:**
   - Is this based on full pathology or just clinical notes?
   - Are critical molecular markers documented?
   - Is evidence quality appropriate for confidence level?

5. **Temporal Diagnostic Changes:**
   - Were multiple diagnoses identified across different time points?
   - Are temporal events (recurrence, progression, second primary) clinically plausible?
   - Do temporal changes align with expected disease trajectories?

**OUTPUT FORMAT:**

Return this JSON:

{{
  "consistency_assessment": "consistent / minor_discrepancies / significant_concerns",

  "flags_for_review": [
    {{
      "flag_type": "molecular_diagnosis_mismatch / unusual_marker / age_diagnosis_mismatch / source_discordance / limited_evidence / other",
      "severity": "low / medium / high",
      "description": "Clear description of the concern",
      "recommendation": "What should be reviewed or considered"
    }}
  ],

  "source_concordance": {{
    "genomics_pathology_agreement": true/false/unknown,
    "clinical_pathology_agreement": true/false/unknown,
    "contradictions_noted": ["List any contradictions"],
    "concordance_notes": "Brief explanation"
  }},

  "evidence_summary": {{
    "molecular_evidence": "complete / partial / absent / conflicting - brief description",
    "histologic_evidence": "documented / not_documented / brief description",
    "clinical_evidence": "strong / moderate / minimal / brief description",
    "overall_quality": "high / moderate / low"
  }},

  "confidence_assessment": {{
    "final_confidence": "high / moderate / low",
    "confidence_rationale": "Why this confidence level based on evidence and consistency",
    "confidence_limitations": "What factors limit confidence (if any)"
  }},

  "temporal_changes_noted": true/false,
  "temporal_changes_assessment": "If temporal_changes_noted is true, explain whether temporal events are clinically plausible and aligned with disease trajectory. If false, state 'No temporal diagnostic changes identified.'",

  "review_recommendation": "no_review_needed / suggested_review / urgent_review",
  "review_rationale": "Why this recommendation"
}}

**FLAG SEVERITY GUIDELINES:**
- LOW: Minor inconsistencies, documentation gaps, typical for historical data
- MEDIUM: Unusual combinations warranting expert review, source discordance
- HIGH: Major contradictions, impossible marker combinations, critical data conflicts

**EXAMPLES:**

Example 1 - Everything Concordant:
{{
  "consistency_assessment": "consistent",
  "flags_for_review": [],
  "review_recommendation": "no_review_needed"
}}

Example 2 - Molecular Mismatch (HIGH severity):
{{
  "consistency_assessment": "significant_concerns",
  "flags_for_review": [
    {{
      "flag_type": "molecular_diagnosis_mismatch",
      "severity": "high",
      "description": "Diagnosis is glioblastoma but PTCH1 mutation detected. PTCH1 is characteristic of medulloblastoma (SHH pathway), not glioblastoma.",
      "recommendation": "Urgent review - possible misclassification or data entry error"
    }}
  ],
  "review_recommendation": "urgent_review"
}}

Example 3 - Limited Evidence (LOW severity):
{{
  "consistency_assessment": "consistent",
  "flags_for_review": [
    {{
      "flag_type": "limited_evidence",
      "severity": "low",
      "description": "Diagnosis based on problem list only - no pathology or molecular reports available",
      "recommendation": "Classification confidence limited by absence of pathology data"
    }}
  ],
  "review_recommendation": "no_review_needed"
}}

**IMPORTANT:** Return ONLY the JSON object, no additional text.
"""

        try:
            # Use MedGemma for consistency review
            result = self.medgemma_agent.extract(review_prompt, temperature=0.1)

            # Parse JSON response
            review = json.loads(result.raw_response)

            # Log results
            assessment = review.get('consistency_assessment', 'unknown')
            flags = review.get('flags_for_review', [])
            recommendation = review.get('review_recommendation', 'unknown')
            temporal_changes = review.get('temporal_changes_noted', False)

            logger.info(f"      Consistency assessment: {assessment}")
            logger.info(f"      Temporal changes noted: {temporal_changes}")
            logger.info(f"      Flags raised: {len(flags)}")
            if flags:
                for flag in flags:
                    severity = flag.get('severity', 'unknown')
                    flag_type = flag.get('flag_type', 'unknown')
                    logger.info(f"        [{severity.upper()}] {flag_type}: {flag.get('description', '')[:100]}")
            logger.info(f"      Review recommendation: {recommendation}")

            # Add audit trail
            review['raw_review'] = result.raw_response
            review['review_timestamp'] = datetime.now().isoformat()

            return review

        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Phase 0.4 JSON parse error: {e}")
            logger.error(f"      Response preview: {result.raw_response[:500]}")
            return {
                "consistency_assessment": "error",
                "flags_for_review": [
                    {
                        "flag_type": "review_error",
                        "severity": "high",
                        "description": f"Consistency review failed: {str(e)}",
                        "recommendation": "Manual review required"
                    }
                ],
                "review_recommendation": "urgent_review",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"   ❌ Phase 0.4 review error: {e}")
            return {
                "consistency_assessment": "error",
                "flags_for_review": [
                    {
                        "flag_type": "review_error",
                        "severity": "high",
                        "description": f"Consistency review failed: {str(e)}",
                        "recommendation": "Manual review required"
                    }
                ],
                "review_recommendation": "urgent_review",
                "error": str(e)
            }

    def _format_evidence_for_review(self, evidence_list: List[Any]) -> str:
        """
        Format diagnostic evidence for review prompt.

        Args:
            evidence_list: List of DiagnosisEvidence objects

        Returns:
            Formatted string
        """
        if not evidence_list:
            return "No diagnostic evidence available"

        output = []
        output.append(f"Total evidence items: {len(evidence_list)}")
        output.append("")

        # Group by source type
        by_source = {}
        for evidence in evidence_list:
            source_name = evidence.source.name
            if source_name not in by_source:
                by_source[source_name] = []
            by_source[source_name].append(evidence)

        for source_name, items in by_source.items():
            output.append(f"From {source_name} ({len(items)} items):")
            for item in items[:5]:  # Limit to 5 per source
                output.append(f"  - {item.diagnosis} (confidence: {item.confidence:.2f}, date: {item.date.strftime('%Y-%m-%d') if item.date else 'unknown'})")
            if len(items) > 5:
                output.append(f"  ... and {len(items) - 5} more")
            output.append("")

        return "\n".join(output)
