#!/usr/bin/env python3
"""
EOR Orchestrator - Adjudicates Extent of Resection from Multiple Sources

This module implements the Orchestrator agent that adjudicates conflicting
extent of resection (EOR) assessments from operative notes and post-op imaging.

The orchestrator:
  1. Receives EOR from operative note (surgeon's assessment)
  2. Receives EOR from post-op imaging (radiologist's volumetric assessment)
  3. Applies adjudication logic to determine final EOR
  4. Assembles additional evidence if needed (subsequent imaging, etc.)
  5. Returns FeatureObject with full provenance and adjudication record

Adjudication Logic:
  - If both agree → High confidence, use agreed value
  - If imaging is HIGH confidence and differs → Favor imaging (objective)
  - If imaging is MEDIUM/LOW and differs → Favor operative note (surgeon saw tumor directly)
  - If difference is >= 2 categories (e.g., GTR vs STR) → Requires manual review
  - If no imaging available → Use operative note only (flag for review)

Usage:
    from lib.eor_orchestrator import EOROrchestrator
    from lib.feature_object import FeatureObject

    orchestrator = EOROrchestrator(medgemma_agent, binary_agent)

    # Operative note says "STR", imaging says "NTR"
    eor_feature = orchestrator.adjudicate_eor(
        operative_note_eor="STR",
        operative_note_source_id="Binary/abc123",
        operative_note_text="Sonopet was used to debulk...",
        operative_note_confidence="MEDIUM",
        postop_imaging_eor="NTR",
        postop_imaging_source_id="DiagnosticReport/def456",
        postop_imaging_text="Minimal residual enhancement...",
        postop_imaging_confidence="HIGH",
        surgery_date="2017-09-27",
        patient_id="eQSB0y3q..."
    )

    # Returns FeatureObject with adjudication
"""

import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta

from lib.feature_object import FeatureObject, SourceType, ConfidenceLevel

logger = logging.getLogger(__name__)


class EOROrchestrator:
    """
    Orchestrates extent of resection adjudication from multiple sources.

    Attributes:
        medgemma_agent: MedGemmaAgent for extracting from additional documents if needed
        binary_agent: BinaryFileAgent for fetching additional imaging reports if needed
    """

    # EOR categories in order of completeness (for calculating differences)
    EOR_HIERARCHY = {
        'GTR': 4,      # Gross Total Resection (complete)
        'NTR': 3,      # Near Total Resection (>95%)
        'STR': 2,      # Subtotal Resection (50-95%)
        'BIOPSY': 1,   # Biopsy only (<10%)
        'UNCLEAR': 0   # Cannot determine
    }

    def __init__(self, medgemma_agent=None, binary_agent=None):
        """
        Initialize orchestrator with optional agents for additional evidence gathering.

        Args:
            medgemma_agent: MedGemmaAgent for AI extraction (optional)
            binary_agent: BinaryFileAgent for fetching documents (optional)
        """
        self.medgemma_agent = medgemma_agent
        self.binary_agent = binary_agent

    def adjudicate_eor(self,
                       operative_note_eor: Optional[str] = None,
                       operative_note_source_id: Optional[str] = None,
                       operative_note_text: Optional[str] = None,
                       operative_note_confidence: str = "MEDIUM",
                       postop_imaging_eor: Optional[str] = None,
                       postop_imaging_source_id: Optional[str] = None,
                       postop_imaging_text: Optional[str] = None,
                       postop_imaging_confidence: str = "MEDIUM",
                       surgery_date: Optional[str] = None,
                       patient_id: Optional[str] = None) -> FeatureObject:
        """
        Adjudicate EOR from operative note and post-op imaging.

        Args:
            operative_note_eor: EOR from operative note (GTR, NTR, STR, BIOPSY, UNCLEAR)
            operative_note_source_id: FHIR Binary ID for operative note
            operative_note_text: Surgeon's assessment text snippet
            operative_note_confidence: Extraction confidence from operative note
            postop_imaging_eor: EOR from post-op imaging (GTR, NTR, STR, BIOPSY, UNCLEAR)
            postop_imaging_source_id: FHIR resource ID for imaging report
            postop_imaging_text: Radiologist's assessment text snippet
            postop_imaging_confidence: Extraction confidence from imaging
            surgery_date: Date of surgery (for gathering additional evidence if needed)
            patient_id: Patient ID (for gathering additional evidence if needed)

        Returns:
            FeatureObject with adjudicated EOR and full provenance
        """
        # Case 1: Only operative note available
        if operative_note_eor and not postop_imaging_eor:
            return self._create_single_source_eor(
                value=operative_note_eor,
                source_type=SourceType.OPERATIVE_NOTE,
                source_id=operative_note_source_id,
                raw_text=operative_note_text,
                confidence=operative_note_confidence,
                rationale="No post-op imaging available - using operative note only",
                requires_review=(operative_note_confidence != ConfidenceLevel.HIGH or operative_note_eor == 'UNCLEAR')
            )

        # Case 2: Only imaging available (rare - no operative note found)
        if postop_imaging_eor and not operative_note_eor:
            return self._create_single_source_eor(
                value=postop_imaging_eor,
                source_type=SourceType.POSTOP_IMAGING,
                source_id=postop_imaging_source_id,
                raw_text=postop_imaging_text,
                confidence=postop_imaging_confidence,
                rationale="No operative note available - using post-op imaging only",
                requires_review=True  # Always review if no operative note
            )

        # Case 3: Both sources available
        if operative_note_eor and postop_imaging_eor:
            return self._adjudicate_multi_source_eor(
                operative_note_eor=operative_note_eor,
                operative_note_source_id=operative_note_source_id,
                operative_note_text=operative_note_text,
                operative_note_confidence=operative_note_confidence,
                postop_imaging_eor=postop_imaging_eor,
                postop_imaging_source_id=postop_imaging_source_id,
                postop_imaging_text=postop_imaging_text,
                postop_imaging_confidence=postop_imaging_confidence,
                surgery_date=surgery_date,
                patient_id=patient_id
            )

        # Case 4: No sources available (shouldn't happen, but handle gracefully)
        logger.warning("No EOR sources available - creating UNCLEAR feature")
        return FeatureObject.from_single_source(
            value="UNCLEAR",
            source_type=SourceType.OTHER,
            extracted_value="UNCLEAR",
            extraction_method="default",
            confidence=ConfidenceLevel.LOW,
            raw_text="No EOR sources available"
        )

    def _create_single_source_eor(self,
                                   value: str,
                                   source_type: str,
                                   source_id: Optional[str],
                                   raw_text: Optional[str],
                                   confidence: str,
                                   rationale: str,
                                   requires_review: bool) -> FeatureObject:
        """
        Create FeatureObject for single-source EOR (with adjudication note).

        Args:
            value: EOR value
            source_type: Type of source
            source_id: FHIR resource ID
            raw_text: Text snippet
            confidence: Extraction confidence
            rationale: Explanation for using single source
            requires_review: Whether manual review needed

        Returns:
            FeatureObject with single source and adjudication note
        """
        feature = FeatureObject.from_single_source(
            value=value,
            source_type=source_type,
            source_id=source_id,
            extracted_value=value,
            extraction_method="medgemma",
            confidence=confidence,
            raw_text=raw_text
        )

        # Add adjudication note explaining single source
        feature.adjudicate(
            final_value=value,
            method="single_source_available",
            rationale=rationale,
            adjudicated_by="eor_orchestrator",
            requires_manual_review=requires_review
        )

        return feature

    def _adjudicate_multi_source_eor(self,
                                     operative_note_eor: str,
                                     operative_note_source_id: str,
                                     operative_note_text: str,
                                     operative_note_confidence: str,
                                     postop_imaging_eor: str,
                                     postop_imaging_source_id: str,
                                     postop_imaging_text: str,
                                     postop_imaging_confidence: str,
                                     surgery_date: Optional[str],
                                     patient_id: Optional[str]) -> FeatureObject:
        """
        Adjudicate EOR when both operative note and imaging available.

        Args:
            operative_note_eor: EOR from operative note
            operative_note_source_id: Operative note resource ID
            operative_note_text: Surgeon's assessment text
            operative_note_confidence: Operative note extraction confidence
            postop_imaging_eor: EOR from imaging
            postop_imaging_source_id: Imaging resource ID
            postop_imaging_text: Radiologist's assessment text
            postop_imaging_confidence: Imaging extraction confidence
            surgery_date: Surgery date
            patient_id: Patient ID

        Returns:
            FeatureObject with both sources and adjudication
        """
        # Create feature with both sources
        feature = FeatureObject.from_single_source(
            value=operative_note_eor,  # Temporary - will be adjudicated
            source_type=SourceType.OPERATIVE_NOTE,
            source_id=operative_note_source_id,
            extracted_value=operative_note_eor,
            extraction_method="medgemma",
            confidence=operative_note_confidence,
            raw_text=operative_note_text
        )

        feature.add_source(
            source_type=SourceType.POSTOP_IMAGING,
            source_id=postop_imaging_source_id,
            extracted_value=postop_imaging_eor,
            extraction_method="medgemma",
            confidence=postop_imaging_confidence,
            raw_text=postop_imaging_text
        )

        # Apply adjudication logic
        final_value, method, rationale, requires_review = self._apply_adjudication_logic(
            operative_note_eor=operative_note_eor,
            operative_note_confidence=operative_note_confidence,
            postop_imaging_eor=postop_imaging_eor,
            postop_imaging_confidence=postop_imaging_confidence
        )

        # Adjudicate
        feature.adjudicate(
            final_value=final_value,
            method=method,
            rationale=rationale,
            adjudicated_by="eor_orchestrator",
            requires_manual_review=requires_review
        )

        logger.info(f"📊 EOR Adjudication: Op Note={operative_note_eor} (conf={operative_note_confidence}), "
                   f"Imaging={postop_imaging_eor} (conf={postop_imaging_confidence}) → Final={final_value} "
                   f"[{method}] {' ⚠️  REVIEW' if requires_review else ''}")

        return feature

    def _apply_adjudication_logic(self,
                                  operative_note_eor: str,
                                  operative_note_confidence: str,
                                  postop_imaging_eor: str,
                                  postop_imaging_confidence: str) -> Tuple[str, str, str, bool]:
        """
        Apply adjudication logic to determine final EOR.

        Returns:
            Tuple of (final_value, method, rationale, requires_manual_review)
        """
        # Normalize to uppercase
        op_eor = operative_note_eor.upper()
        img_eor = postop_imaging_eor.upper()
        op_conf = operative_note_confidence.upper()
        img_conf = postop_imaging_confidence.upper()

        # Rule 1: Agreement between sources → High confidence
        if op_eor == img_eor:
            return (
                op_eor,
                "sources_agree",
                f"Operative note and post-op imaging both report {op_eor}",
                False  # No review needed when sources agree
            )

        # Rule 2: Either source is UNCLEAR → Use the clearer one
        if op_eor == 'UNCLEAR' and img_eor != 'UNCLEAR':
            return (
                img_eor,
                "operative_note_unclear",
                f"Operative note unclear, using post-op imaging assessment: {img_eor}",
                img_conf != ConfidenceLevel.HIGH  # Review if imaging not HIGH confidence
            )

        if img_eor == 'UNCLEAR' and op_eor != 'UNCLEAR':
            return (
                op_eor,
                "imaging_unclear",
                f"Post-op imaging unclear, using operative note assessment: {op_eor}",
                op_conf != ConfidenceLevel.HIGH  # Review if op note not HIGH confidence
            )

        if op_eor == 'UNCLEAR' and img_eor == 'UNCLEAR':
            return (
                'UNCLEAR',
                "both_unclear",
                "Both operative note and post-op imaging assessments are unclear",
                True  # Definitely needs review
            )

        # Rule 3: Calculate EOR difference (for flagging large discrepancies)
        op_level = self.EOR_HIERARCHY.get(op_eor, 0)
        img_level = self.EOR_HIERARCHY.get(img_eor, 0)
        difference = abs(op_level - img_level)

        # Rule 4: Imaging is HIGH confidence and differs → Favor imaging (objective volumetric assessment)
        if img_conf == ConfidenceLevel.HIGH and difference == 1:
            return (
                img_eor,
                "favor_imaging_high_confidence",
                f"Post-op imaging provides objective volumetric assessment with HIGH confidence. "
                f"Imaging reports {img_eor} vs operative note {op_eor}. Favoring imaging but flagging for review "
                f"due to discrepancy.",
                True  # Always review when sources disagree, even with HIGH confidence imaging
            )

        # Rule 5: Large discrepancy (>= 2 categories) → Requires manual review, favor imaging if HIGH confidence
        if difference >= 2:
            if img_conf == ConfidenceLevel.HIGH:
                return (
                    img_eor,
                    "large_discrepancy_favor_imaging",
                    f"Large discrepancy: Operative note reports {op_eor}, imaging reports {img_eor}. "
                    f"Favoring HIGH confidence imaging but REQUIRES MANUAL REVIEW due to significant discrepancy.",
                    True
                )
            else:
                return (
                    op_eor,
                    "large_discrepancy_favor_operative",
                    f"Large discrepancy: Operative note reports {op_eor}, imaging reports {img_eor}. "
                    f"Imaging confidence not HIGH, favoring operative note but REQUIRES MANUAL REVIEW.",
                    True
                )

        # Rule 6: Small discrepancy (1 category), MEDIUM/LOW imaging confidence → Favor operative note
        # Rationale: Surgeon directly visualized tumor during resection
        if img_conf in [ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]:
            return (
                op_eor,
                "favor_operative_note_imaging_not_high",
                f"Post-op imaging confidence is {img_conf} (not HIGH). Surgeon's direct visualization "
                f"during resection is more reliable. Operative note reports {op_eor} vs imaging {img_eor}. "
                f"Favoring operative note but flagging for review.",
                True  # Review due to discrepancy
            )

        # Default: Favor imaging (shouldn't reach here, but handle gracefully)
        return (
            img_eor,
            "default_favor_imaging",
            f"Adjudication logic defaulting to imaging assessment ({img_eor}) due to objective nature, "
            f"but REQUIRES MANUAL REVIEW. Operative note: {op_eor}",
            True
        )

    def gather_additional_imaging(self,
                                  patient_id: str,
                                  surgery_date: str,
                                  days_after_surgery: int = 90) -> List[Dict]:
        """
        Gather additional imaging reports after surgery for additional evidence.

        Args:
            patient_id: Patient ID
            surgery_date: Date of surgery (YYYY-MM-DD)
            days_after_surgery: Number of days after surgery to search (default 90)

        Returns:
            List of imaging report dictionaries with extracted EOR assessments

        Note: This method requires self.medgemma_agent and self.binary_agent to be set.
        """
        if not self.medgemma_agent or not self.binary_agent:
            logger.warning("Cannot gather additional imaging - agents not initialized")
            return []

        logger.info(f"🔍 Gathering additional imaging reports for {patient_id} after {surgery_date}")

        # TODO: Implement additional imaging search
        # This would:
        # 1. Query v_imaging for reports within days_after_surgery of surgery_date
        # 2. Extract EOR assessment from each report using MedGemma
        # 3. Return list of assessments for orchestrator to consider

        # Placeholder for now
        return []
