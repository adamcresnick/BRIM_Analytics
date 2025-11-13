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
from lib.llm_prompt_wrapper import LLMPromptWrapper, ClinicalContext

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
        self.llm_wrapper = LLMPromptWrapper()
        logger.info("✅ DiagnosticEvidenceAggregator initialized (V5.3 with LLM prompt wrapper)")

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
        logger.info("   [Tier 2B] Extracting from narrative sources (MedGemma)...")
        evidence.extend(self._extract_from_imaging_reports(patient_fhir_id))
        evidence.extend(self._extract_from_clinical_notes(patient_fhir_id))
        evidence.extend(self._extract_from_discharge_summaries(patient_fhir_id))

        logger.info(f"   → Tier 2B complete: {len(evidence)} total evidence items after narrative extraction")

        # Tier 2C (Investigation Engine): Alternative sources if gaps found
        if len(evidence) < 2:
            logger.warning(f"   ⚠️  Insufficient evidence ({len(evidence)} items), attempting Tier 2C...")
            evidence.extend(self._investigation_engine_search_alternatives(patient_fhir_id))
        else:
            logger.info(f"   → Tier 2C not needed: Sufficient evidence already collected ({len(evidence)} items)")

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

    def _extract_from_imaging_reports(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from imaging reports (radiology reports).

        Tier 2B: MedGemma-based extraction from narrative radiology impressions.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from imaging reports
        """
        query = f"""
        SELECT DISTINCT
            report_date,
            report_type,
            impression,
            findings
        FROM v_imaging_reports
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND (impression IS NOT NULL OR findings IS NOT NULL)
        ORDER BY report_date DESC
        LIMIT 50
        """

        try:
            results = self.query_athena(query, "Querying v_imaging_reports for diagnosis evidence", suppress_output=True)

            if not results:
                logger.info("      → No imaging reports found")
                return []

            evidence = []

            # Import MedGemma for narrative extraction
            try:
                from agents.medgemma_agent import MedGemmaAgent
                medgemma = MedGemmaAgent(model='gemma2:27b')
            except Exception as e:
                logger.warning(f"      ⚠️  Could not initialize MedGemma, skipping imaging reports: {e}")
                return []

            # Process each imaging report
            for record in results:
                impression = record.get('impression', '')
                findings = record.get('findings', '')
                report_text = f"{impression}\n{findings}".strip()

                if not report_text:
                    continue

                # Use MedGemma to extract diagnosis mentions
                extraction_prompt = f"""You are a clinical NLP system. Extract any CNS tumor diagnosis mentions from this radiology report.

RADIOLOGY REPORT:
{report_text[:2000]}

Return ONLY a JSON object with this structure:
{{
    "diagnosis_found": true/false,
    "diagnosis": "the diagnosis text if found, or null",
    "confidence": 0.0-1.0
}}

If no CNS tumor diagnosis is mentioned, set diagnosis_found to false and diagnosis to null."""

                try:
                    response = medgemma.query(extraction_prompt, temperature=0.1)
                    import json
                    extraction = json.loads(response)

                    if extraction.get('diagnosis_found') and extraction.get('diagnosis'):
                        # Parse date
                        date_str = record.get('report_date')
                        date_obj = None
                        if date_str:
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            except:
                                pass

                        evidence.append(DiagnosisEvidence(
                            diagnosis=extraction['diagnosis'],
                            source=EvidenceSource.IMAGING_REPORTS,
                            confidence=extraction.get('confidence', 0.70),
                            date=date_obj,
                            raw_data=record,
                            extraction_method='medgemma'
                        ))

                except Exception as e:
                    logger.debug(f"      Could not extract from imaging report: {e}")
                    continue

            logger.info(f"      → Found {len(evidence)} imaging report diagnosis mentions")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from imaging reports: {e}")
            return []

    def _extract_from_clinical_notes(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from clinical notes (progress notes, oncology notes).

        Tier 2B: MedGemma-based extraction from narrative clinical documentation.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from clinical notes
        """
        query = f"""
        SELECT DISTINCT
            note_date,
            note_type,
            note_text
        FROM v_clinical_notes
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND note_text IS NOT NULL
          AND (LOWER(note_type) LIKE '%oncology%'
               OR LOWER(note_type) LIKE '%progress%'
               OR LOWER(note_type) LIKE '%consult%')
        ORDER BY note_date DESC
        LIMIT 30
        """

        try:
            results = self.query_athena(query, "Querying v_clinical_notes for diagnosis evidence", suppress_output=True)

            if not results:
                logger.info("      → No clinical notes found")
                return []

            evidence = []

            # Import MedGemma for narrative extraction
            try:
                from agents.medgemma_agent import MedGemmaAgent
                medgemma = MedGemmaAgent(model='gemma2:27b')
            except Exception as e:
                logger.warning(f"      ⚠️  Could not initialize MedGemma, skipping clinical notes: {e}")
                return []

            # Process each clinical note
            for record in results:
                note_text = record.get('note_text', '').strip()

                if not note_text:
                    continue

                # Use MedGemma to extract diagnosis mentions
                extraction_prompt = f"""You are a clinical NLP system. Extract any CNS tumor diagnosis mentions from this clinical note.

CLINICAL NOTE:
{note_text[:2000]}

Return ONLY a JSON object with this structure:
{{
    "diagnosis_found": true/false,
    "diagnosis": "the diagnosis text if found, or null",
    "confidence": 0.0-1.0
}}

If no CNS tumor diagnosis is mentioned, set diagnosis_found to false and diagnosis to null."""

                try:
                    response = medgemma.query(extraction_prompt, temperature=0.1)
                    import json
                    extraction = json.loads(response)

                    if extraction.get('diagnosis_found') and extraction.get('diagnosis'):
                        # Parse date
                        date_str = record.get('note_date')
                        date_obj = None
                        if date_str:
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            except:
                                pass

                        # Determine source type based on note type
                        note_type = record.get('note_type', '').lower()
                        if 'oncology' in note_type:
                            source = EvidenceSource.ONCOLOGY_NOTES
                        elif 'radiation' in note_type:
                            source = EvidenceSource.RADIATION_ONCOLOGY
                        else:
                            source = EvidenceSource.PROGRESS_NOTES

                        evidence.append(DiagnosisEvidence(
                            diagnosis=extraction['diagnosis'],
                            source=source,
                            confidence=extraction.get('confidence', 0.65),
                            date=date_obj,
                            raw_data=record,
                            extraction_method='medgemma'
                        ))

                except Exception as e:
                    logger.debug(f"      Could not extract from clinical note: {e}")
                    continue

            logger.info(f"      → Found {len(evidence)} clinical note diagnosis mentions")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from clinical notes: {e}")
            return []

    def _extract_from_discharge_summaries(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from discharge summaries.

        Tier 2B: MedGemma-based extraction from discharge documentation.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from discharge summaries
        """
        query = f"""
        SELECT DISTINCT
            discharge_date,
            admission_diagnosis,
            discharge_diagnosis,
            summary_text
        FROM v_encounters
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND encounter_class = 'inpatient'
          AND (admission_diagnosis IS NOT NULL
               OR discharge_diagnosis IS NOT NULL
               OR summary_text IS NOT NULL)
        ORDER BY discharge_date DESC
        LIMIT 20
        """

        try:
            results = self.query_athena(query, "Querying v_encounters for discharge diagnosis evidence", suppress_output=True)

            if not results:
                logger.info("      → No discharge summaries found")
                return []

            evidence = []

            # Import MedGemma for narrative extraction
            try:
                from agents.medgemma_agent import MedGemmaAgent
                medgemma = MedGemmaAgent(model='gemma2:27b')
            except Exception as e:
                logger.warning(f"      ⚠️  Could not initialize MedGemma, skipping discharge summaries: {e}")
                return []

            # Process each discharge record
            for record in results:
                admission_dx = record.get('admission_diagnosis', '')
                discharge_dx = record.get('discharge_diagnosis', '')
                summary_text = record.get('summary_text', '')
                combined_text = f"{admission_dx}\n{discharge_dx}\n{summary_text}".strip()

                if not combined_text:
                    continue

                # Use MedGemma to extract diagnosis mentions
                extraction_prompt = f"""You are a clinical NLP system. Extract the primary CNS tumor diagnosis from this discharge summary.

DISCHARGE INFORMATION:
{combined_text[:2000]}

Return ONLY a JSON object with this structure:
{{
    "diagnosis_found": true/false,
    "diagnosis": "the diagnosis text if found, or null",
    "confidence": 0.0-1.0
}}

If no CNS tumor diagnosis is mentioned, set diagnosis_found to false and diagnosis to null."""

                try:
                    response = medgemma.query(extraction_prompt, temperature=0.1)
                    import json
                    extraction = json.loads(response)

                    if extraction.get('diagnosis_found') and extraction.get('diagnosis'):
                        # Parse date
                        date_str = record.get('discharge_date')
                        date_obj = None
                        if date_str:
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            except:
                                pass

                        evidence.append(DiagnosisEvidence(
                            diagnosis=extraction['diagnosis'],
                            source=EvidenceSource.DISCHARGE_SUMMARIES,
                            confidence=extraction.get('confidence', 0.75),
                            date=date_obj,
                            raw_data=record,
                            extraction_method='medgemma'
                        ))

                except Exception as e:
                    logger.debug(f"      Could not extract from discharge summary: {e}")
                    continue

            logger.info(f"      → Found {len(evidence)} discharge summary diagnosis mentions")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from discharge summaries: {e}")
            return []

    def _investigation_engine_search_alternatives(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Use Investigation Engine to search alternative sources when insufficient evidence.

        Tier 2C: Fallback mechanism triggered when <2 evidence sources found.

        This method uses the Investigation Engine's comprehensive search capabilities
        to find diagnosis evidence in less common sources (treatment protocols,
        radiation oncology notes, etc.).

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from alternative sources
        """
        logger.info("      [Tier 2C - Investigation Engine] Searching alternative sources...")

        evidence = []

        # Try radiation oncology records
        try:
            query = f"""
            SELECT DISTINCT
                treatment_date,
                treatment_site,
                diagnosis_code,
                diagnosis_description
            FROM v_radiation_oncology
            WHERE patient_fhir_id = '{patient_fhir_id}'
              AND diagnosis_description IS NOT NULL
            ORDER BY treatment_date DESC
            LIMIT 20
            """

            results = self.query_athena(query, "Searching radiation oncology records for diagnosis", suppress_output=True)

            for record in results:
                diagnosis_desc = record.get('diagnosis_description', '')

                # Check if this is a CNS tumor diagnosis
                cns_keywords = ['glioma', 'glioblastoma', 'astrocytoma', 'ependymoma',
                               'medulloblastoma', 'brain', 'cns', 'tumor', 'neoplasm']

                if any(keyword in diagnosis_desc.lower() for keyword in cns_keywords):
                    # Parse date
                    date_str = record.get('treatment_date')
                    date_obj = None
                    if date_str:
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        except:
                            pass

                    evidence.append(DiagnosisEvidence(
                        diagnosis=diagnosis_desc,
                        source=EvidenceSource.RADIATION_ONCOLOGY,
                        confidence=0.80,  # Radiation treatment requires confirmed diagnosis
                        date=date_obj,
                        raw_data=record,
                        extraction_method='investigation_engine'
                    ))

            if evidence:
                logger.info(f"      → Investigation Engine found {len(evidence)} radiation oncology evidence items")

        except Exception as e:
            logger.debug(f"      Investigation Engine: No radiation oncology data available: {e}")

        # Try treatment/chemotherapy protocols
        try:
            query = f"""
            SELECT DISTINCT
                medication_date,
                medication_name,
                reason_for_use
            FROM v_medications
            WHERE patient_fhir_id = '{patient_fhir_id}'
              AND reason_for_use IS NOT NULL
              AND (LOWER(medication_name) LIKE '%chemo%'
                   OR LOWER(medication_name) LIKE '%temozolomide%'
                   OR LOWER(medication_name) LIKE '%bevacizumab%'
                   OR LOWER(medication_name) LIKE '%lomustine%')
            ORDER BY medication_date DESC
            LIMIT 20
            """

            results = self.query_athena(query, "Searching chemotherapy protocols for diagnosis", suppress_output=True)

            for record in results:
                reason = record.get('reason_for_use', '')

                # Check if reason mentions CNS tumor
                cns_keywords = ['glioma', 'glioblastoma', 'astrocytoma', 'ependymoma',
                               'medulloblastoma', 'brain', 'cns', 'tumor', 'neoplasm']

                if any(keyword in reason.lower() for keyword in cns_keywords):
                    # Parse date
                    date_str = record.get('medication_date')
                    date_obj = None
                    if date_str:
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        except:
                            pass

                    evidence.append(DiagnosisEvidence(
                        diagnosis=reason,
                        source=EvidenceSource.TREATMENT_PROTOCOLS,
                        confidence=0.75,  # Treatment indication confidence
                        date=date_obj,
                        raw_data=record,
                        extraction_method='investigation_engine'
                    ))

            if evidence:
                logger.info(f"      → Investigation Engine found {len(evidence)} treatment protocol evidence items")

        except Exception as e:
            logger.debug(f"      Investigation Engine: No treatment protocol data available: {e}")

        if not evidence:
            logger.warning("      ⚠️  Investigation Engine: No additional evidence found in alternative sources")
        else:
            logger.info(f"      ✅ Investigation Engine complete: Found {len(evidence)} additional evidence items")

        return evidence

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
