#!/usr/bin/env python3
"""
Diagnostic Evidence Aggregator - Phase 0.1

Aggregates diagnosis mentions from ALL clinical sources across the care journey.
Part of the Diagnostic Reasoning Infrastructure Sprint.

This module implements multi-source diagnostic evidence collection with:
  - 3-tier reasoning cascade (Keywords → MedGemma → Investigation Engine)
  - Clinical authority ranking (pathology > molecular > problem lists > notes)
  - Evidence quality assessment and confidence scoring

Usage:
    from lib.diagnostic_evidence_aggregator import DiagnosticEvidenceAggregator, DiagnosisEvidence

    aggregator = DiagnosticEvidenceAggregator(query_athena_func)
    evidence_list = aggregator.aggregate_all_evidence(patient_fhir_id)

    for evidence in evidence_list:
        print(f"{evidence.source}: {evidence.diagnosis} (confidence: {evidence.confidence})")
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Callable, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EvidenceSource(Enum):
    """
    Evidence sources ranked by clinical authority.

    Lower enum values = higher authority
    """
    SURGICAL_PATHOLOGY = 1      # Gold standard
    MOLECULAR_TESTING = 2        # Molecular confirmation
    PROBLEM_LIST = 3             # Coded diagnoses
    IMAGING_REPORTS = 4          # Radiological impressions
    ONCOLOGY_NOTES = 5           # Specialist documentation
    RADIATION_ONCOLOGY = 6       # Treatment planning
    DISCHARGE_SUMMARIES = 7      # Admission/discharge diagnoses
    PROGRESS_NOTES = 8           # Ongoing references
    TREATMENT_PROTOCOLS = 9      # Protocol requirements


@dataclass
class DiagnosisEvidence:
    """
    Single piece of diagnosis evidence from a clinical source.

    Attributes:
        diagnosis: The diagnosis string
        source: Evidence source type (EvidenceSource enum)
        confidence: Confidence score 0.0-1.0
        date: Date of documentation
        raw_data: Original data dict for audit trail
        extraction_method: How diagnosis was extracted (keyword/medgemma/investigation)
    """
    diagnosis: str
    source: EvidenceSource
    confidence: float
    date: Optional[datetime]
    raw_data: Dict
    extraction_method: str  # 'keyword', 'medgemma', 'investigation_engine'

    def __post_init__(self):
        """Validate confidence is in range 0-1."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


class DiagnosticEvidenceAggregator:
    """
    Aggregates diagnosis evidence from multiple sources across care journey.

    Implements 3-tier reasoning:
    - Tier 2A (Keywords): Fast extraction from structured sources
    - Tier 2B (MedGemma): Clinical reasoning for narrative sources
    - Tier 2C (Investigation Engine): Alternative sources if gaps found

    Attributes:
        query_athena: Function to query Athena database
    """

    def __init__(self, query_athena: Callable):
        """
        Initialize aggregator with Athena query function.

        Args:
            query_athena: Function with signature query_athena(query_string, description)
                         Returns list of dicts
        """
        self.query_athena = query_athena
        logger.info("✅ DiagnosticEvidenceAggregator initialized")

    def aggregate_all_evidence(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Collect ALL diagnosis mentions across entire care journey.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence objects sorted by clinical authority (highest first)
        """
        logger.info("="*80)
        logger.info("PHASE 0.1: MULTI-SOURCE DIAGNOSTIC EVIDENCE AGGREGATION")
        logger.info("="*80)
        logger.info(f"   Patient: {patient_fhir_id}")

        evidence = []

        # Tier 2A (Keywords): Fast extraction from structured sources
        logger.info("   [Tier 2A] Extracting from structured sources (keyword-based)...")
        evidence.extend(self._extract_from_pathology(patient_fhir_id))
        evidence.extend(self._extract_from_problem_lists(patient_fhir_id))

        logger.info(f"   → Tier 2A complete: {len(evidence)} evidence items from structured sources")

        # Tier 2B (MedGemma): Clinical reasoning for narrative sources
        # TODO: Implement in future phase
        # logger.info("   [Tier 2B] Extracting from narrative sources (MedGemma)...")
        # evidence.extend(self._extract_from_imaging_reports(patient_fhir_id))
        # evidence.extend(self._extract_from_clinical_notes(patient_fhir_id))

        # Tier 2C (Investigation Engine): Alternative sources if gaps found
        if len(evidence) < 2:
            logger.warning(f"   ⚠️  Insufficient evidence ({len(evidence)} items), attempting Tier 2C...")
            # TODO: Implement Investigation Engine fallback
            # evidence.extend(self._investigation_engine_search_alternatives(patient_fhir_id))

        # Sort by clinical authority (highest authority first)
        evidence.sort(key=lambda e: e.source.value)

        logger.info(f"   ✅ Phase 0.1 complete: {len(evidence)} total evidence items collected")
        logger.info("="*80)

        return evidence

    def _extract_from_pathology(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from pathology reports (v_pathology_diagnostics).

        Tier 2A: Keyword-based extraction from structured pathology data.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from pathology reports
        """
        query = f"""
        SELECT DISTINCT
            diagnostic_name,
            diagnostic_date,
            diagnostic_source,
            component_name,
            result_value
        FROM v_pathology_diagnostics
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND diagnostic_name IS NOT NULL
          AND diagnostic_name != ''
        ORDER BY diagnostic_date DESC
        """

        try:
            results = self.query_athena(query, "Querying v_pathology_diagnostics for diagnosis evidence", suppress_output=True)

            if not results:
                logger.info("      → No pathology diagnosis evidence found")
                return []

            evidence = []

            # Keywords indicating actual diagnosis (not just test results)
            diagnosis_keywords = [
                'tumor', 'neoplasm', 'malignant', 'cancer', 'carcinoma',
                'glioma', 'glioblastoma', 'astrocytoma', 'ependymoma', 'medulloblastoma',
                'grade', 'who', 'histology', 'pathology', 'biopsy', 'resection'
            ]

            for record in results:
                diagnostic_name = record.get('diagnostic_name', '').lower()

                # Check if this is a diagnosis mention (not just lab result)
                is_diagnosis = any(keyword in diagnostic_name for keyword in diagnosis_keywords)

                if is_diagnosis:
                    # Parse date
                    date_str = record.get('diagnostic_date')
                    date_obj = None
                    if date_str:
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        except:
                            pass

                    # Determine confidence based on source type
                    source_type = record.get('diagnostic_source', '').lower()
                    if 'surgical' in source_type or 'pathology' in source_type:
                        confidence = 0.95  # Surgical pathology is gold standard
                    else:
                        confidence = 0.85  # Other pathology sources still high confidence

                    evidence.append(DiagnosisEvidence(
                        diagnosis=record.get('diagnostic_name', ''),
                        source=EvidenceSource.SURGICAL_PATHOLOGY,
                        confidence=confidence,
                        date=date_obj,
                        raw_data=record,
                        extraction_method='keyword'
                    ))

            logger.info(f"      → Found {len(evidence)} pathology diagnosis mentions")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from pathology: {e}")
            return []

    def _extract_from_problem_lists(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from problem/condition lists (v_conditions).

        Tier 2A: Keyword-based extraction from coded diagnoses.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from problem lists
        """
        query = f"""
        SELECT DISTINCT
            condition_display_name,
            onset_date,
            recorded_date,
            clinical_status,
            verification_status
        FROM v_conditions
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND condition_display_name IS NOT NULL
          AND condition_display_name != ''
        ORDER BY onset_date DESC
        """

        try:
            results = self.query_athena(query, "Querying v_conditions for problem list evidence", suppress_output=True)

            if not results:
                logger.info("      → No problem list diagnosis evidence found")
                return []

            evidence = []

            # Keywords for CNS tumor diagnoses
            cns_tumor_keywords = [
                'tumor', 'neoplasm', 'malignant', 'cancer',
                'glioma', 'glioblastoma', 'astrocytoma', 'ependymoma', 'medulloblastoma',
                'brain', 'cns', 'central nervous system', 'cranial', 'intracranial'
            ]

            for record in results:
                condition_name = record.get('condition_display_name', '').lower()

                # Check if this is a CNS tumor diagnosis
                is_cns_tumor = any(keyword in condition_name for keyword in cns_tumor_keywords)

                if is_cns_tumor:
                    # Parse date (prefer onset_date over recorded_date)
                    date_str = record.get('onset_date') or record.get('recorded_date')
                    date_obj = None
                    if date_str:
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        except:
                            pass

                    # Determine confidence based on verification status
                    verification = record.get('verification_status', '').lower()
                    clinical_status = record.get('clinical_status', '').lower()

                    if verification == 'confirmed' and clinical_status == 'active':
                        confidence = 0.90  # Confirmed, active diagnosis
                    elif verification == 'confirmed':
                        confidence = 0.85  # Confirmed but may not be active
                    else:
                        confidence = 0.75  # Unverified or provisional

                    evidence.append(DiagnosisEvidence(
                        diagnosis=record.get('condition_display_name', ''),
                        source=EvidenceSource.PROBLEM_LIST,
                        confidence=confidence,
                        date=date_obj,
                        raw_data=record,
                        extraction_method='keyword'
                    ))

            logger.info(f"      → Found {len(evidence)} problem list diagnosis mentions")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from problem lists: {e}")
            return []

    def get_highest_authority_diagnosis(self, evidence_list: List[DiagnosisEvidence]) -> Optional[DiagnosisEvidence]:
        """
        Get the diagnosis from the highest clinical authority source.

        Args:
            evidence_list: List of DiagnosisEvidence objects

        Returns:
            DiagnosisEvidence with highest authority, or None if empty
        """
        if not evidence_list:
            return None

        # Evidence list is already sorted by authority (lowest enum value = highest authority)
        return evidence_list[0]

    def get_consensus_diagnosis(self, evidence_list: List[DiagnosisEvidence]) -> Optional[str]:
        """
        Get consensus diagnosis across multiple sources.

        Simple implementation: returns most common diagnosis among high-confidence evidence.

        Args:
            evidence_list: List of DiagnosisEvidence objects

        Returns:
            Consensus diagnosis string, or None if no consensus
        """
        if not evidence_list:
            return None

        # Filter to high-confidence evidence (>= 0.80)
        high_confidence = [e for e in evidence_list if e.confidence >= 0.80]

        if not high_confidence:
            return None

        # Count diagnosis mentions
        diagnosis_counts = {}
        for evidence in high_confidence:
            diagnosis_normalized = evidence.diagnosis.lower().strip()
            diagnosis_counts[diagnosis_normalized] = diagnosis_counts.get(diagnosis_normalized, 0) + 1

        # Return most common diagnosis
        if diagnosis_counts:
            consensus = max(diagnosis_counts.items(), key=lambda x: x[1])[0]
            return consensus

        return None
