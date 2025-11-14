#!/usr/bin/env python3
"""
Diagnostic Evidence Aggregator - Phase 0.1 - V5.6

V5.6 CHANGES:
- Removed disabled v_clinical_notes and v_encounters methods
- Removed Tier 2C (Investigation Engine fallback)
- Changed pathology extraction to MedGemma reasoning (not keywords)
- Changed problem list extraction to MedGemma reasoning (not keywords)
- Removed genomics-only filter from v_pathology_diagnostics
- Added MedGemma agent parameter to __init__()
- Tier 2 binary pathology enhancement integrated at Phase 0 level
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Callable, Optional, Any
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
    ONCOLOGY_NOTES = 5           # Specialist documentation (not queried in V5.6)
    RADIATION_ONCOLOGY = 6       # Treatment planning (not queried in V5.6)
    DISCHARGE_SUMMARIES = 7      # Admission/discharge diagnoses (not queried in V5.6)
    PROGRESS_NOTES = 8           # Ongoing references (not queried in V5.6)
    TREATMENT_PROTOCOLS = 9      # Protocol requirements (not queried in V5.6)


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
    extraction_method: str  # 'keyword_fallback', 'medgemma_reasoning', 'medgemma_structured'

    def __post_init__(self):
        """Validate confidence is in range 0-1."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


class DiagnosticEvidenceAggregator:
    """
    Aggregates diagnosis evidence from multiple sources across care journey.

    V5.6 Architecture:
    - Tier 1 (Structured + Narrative MedGemma): Pathology (all types), problem lists, imaging
    - Tier 2 (Binary Pathology): Fallback to v_binary_files if Tier 1 insufficient (handled at Phase 0 level)

    Attributes:
        query_athena: Function to query Athena database
        medgemma_agent: MedGemma agent for reasoning-based extraction
    """

    def __init__(self, query_athena: Callable, medgemma_agent: Optional[Any] = None):
        """
        Initialize aggregator with Athena query function and optional MedGemma agent.

        Args:
            query_athena: Function with signature query_athena(query_string, description)
                         Returns list of dicts
            medgemma_agent: Optional MedGemma agent for reasoning-based extraction
        """
        self.query_athena = query_athena
        self.medgemma_agent = medgemma_agent
        self.llm_wrapper = LLMPromptWrapper(medgemma_agent=medgemma_agent)  # V5.6: Pass medgemma for summarization

        if medgemma_agent:
            logger.info("✅ DiagnosticEvidenceAggregator initialized (V5.6 with MedGemma reasoning)")
        else:
            logger.info("✅ DiagnosticEvidenceAggregator initialized (V5.6, MedGemma unavailable - will use keyword extraction)")

    def aggregate_all_evidence(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Collect ALL diagnosis mentions across entire care journey.

        V5.6: Uses MedGemma reasoning for ALL extractions (pathology, problem lists, imaging).

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence objects sorted by clinical authority (highest first)
        """
        logger.info("="*80)
        logger.info("PHASE 0.1: MULTI-SOURCE DIAGNOSTIC EVIDENCE AGGREGATION (V5.6)")
        logger.info("="*80)
        logger.info(f"   Patient: {patient_fhir_id}")

        evidence = []

        # Tier 1: MedGemma reasoning-based extraction from all sources
        logger.info("   [Tier 1] Extracting with MedGemma reasoning...")
        evidence.extend(self._extract_from_pathology(patient_fhir_id))  # V5.6: NOW uses MedGemma
        evidence.extend(self._extract_from_problem_lists(patient_fhir_id))  # V5.6: NOW uses MedGemma
        evidence.extend(self._extract_from_imaging_reports(patient_fhir_id))  # Already used MedGemma

        logger.info(f"   → Tier 1 complete: {len(evidence)} evidence items collected")

        # Sort by clinical authority (highest authority first)
        evidence.sort(key=lambda e: e.source.value)

        logger.info(f"   ✅ Phase 0.1 complete: {len(evidence)} total evidence items collected")
        logger.info("="*80)

        return evidence

    def _extract_from_pathology(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from pathology reports (v_pathology_diagnostics).

        V5.6 Tier 1: MedGemma reasoning-based extraction from ALL pathology text
        (molecular + surgical/histological). NO genomics-only filter.

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
            diagnostic_category,
            component_name,
            result_value,
            test_lab
        FROM v_pathology_diagnostics
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND result_value IS NOT NULL
          AND result_value != ''
        ORDER BY diagnostic_date DESC NULLS LAST
        """

        try:
            results = self.query_athena(query, "Querying v_pathology_diagnostics for ALL pathology (molecular + surgical)", suppress_output=True)

            if not results:
                logger.info("      → No pathology reports found")
                return []

            logger.info(f"      → Found {len(results)} pathology records with free text")

            # V5.6: Use MedGemma reasoning if available, otherwise fall back to keywords
            if not self.medgemma_agent:
                logger.warning("      ⚠️  MedGemma not available, falling back to keyword extraction")
                return self._extract_from_pathology_keywords(results)

            evidence = []

            # Process each pathology record with MedGemma (ALL records, no limits)
            for idx, record in enumerate(results):
                result_text = record.get('result_value', '').strip()
                diagnostic_name = record.get('diagnostic_name', '')
                diagnostic_category = record.get('diagnostic_category', '')

                if not result_text:
                    continue

                # V5.6: Use structured prompt wrapper
                context = ClinicalContext(
                    patient_id=patient_fhir_id,
                    phase='PHASE_0_TIER_1_PATHOLOGY',
                    evidence_summary=f"{diagnostic_category} - {diagnostic_name}"
                )

                wrapped_prompt = self.llm_wrapper.wrap_extraction_prompt(
                    task_description="Extract primary CNS tumor diagnosis from pathology report (molecular OR surgical/histological)",
                    document_text=f"PATHOLOGY REPORT:\n{diagnostic_name}\n\n{result_text}",
                    expected_schema=self.llm_wrapper.create_diagnosis_extraction_schema(),
                    context=context,
                    max_document_length=4000
                )

                try:
                    response = self.medgemma_agent.query(wrapped_prompt, temperature=0.1)

                    # V5.6: Validate response
                    is_valid, extraction, error = self.llm_wrapper.validate_response(
                        response,
                        self.llm_wrapper.create_diagnosis_extraction_schema()
                    )

                    if not is_valid:
                        logger.debug(f"      Invalid LLM response for record {idx+1}: {error}")
                        continue

                    if extraction.get('diagnosis_found') and extraction.get('diagnosis'):
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
                        llm_confidence = extraction.get('confidence', 0.85)

                        if 'surgical' in source_type or 'final' in diagnostic_category.lower():
                            base_confidence = 0.95  # Surgical pathology is gold standard
                            source = EvidenceSource.SURGICAL_PATHOLOGY
                        elif 'molecular' in diagnostic_category.lower() or 'genomic' in diagnostic_category.lower():
                            base_confidence = 0.90  # Molecular testing is highly reliable
                            source = EvidenceSource.MOLECULAR_TESTING
                        else:
                            base_confidence = 0.85  # Other pathology sources
                            source = EvidenceSource.SURGICAL_PATHOLOGY

                        # Combine base confidence with LLM extraction confidence
                        final_confidence = min(base_confidence, llm_confidence)

                        evidence.append(DiagnosisEvidence(
                            diagnosis=extraction['diagnosis'],
                            source=source,
                            confidence=final_confidence,
                            date=date_obj,
                            raw_data=record,
                            extraction_method='medgemma_reasoning'  # V5.6 marker
                        ))

                except Exception as e:
                    logger.debug(f"      Could not extract from pathology record {idx+1}: {e}")
                    continue

            logger.info(f"      → Extracted {len(evidence)} diagnoses from pathology via MedGemma reasoning")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from pathology: {e}")
            return []

    def _extract_from_pathology_keywords(self, results: List[Dict]) -> List[DiagnosisEvidence]:
        """
        Fallback keyword-based extraction when MedGemma unavailable.

        Args:
            results: Query results from v_pathology_diagnostics

        Returns:
            List of DiagnosisEvidence from keyword extraction
        """
        evidence = []

        diagnosis_keywords = [
            'tumor', 'neoplasm', 'malignant', 'cancer', 'carcinoma',
            'glioma', 'glioblastoma', 'astrocytoma', 'ependymoma', 'medulloblastoma',
            'grade', 'who', 'histology', 'pathology', 'biopsy', 'resection'
        ]

        for record in results:
            diagnostic_name = record.get('diagnostic_name', '').lower()

            is_diagnosis = any(keyword in diagnostic_name for keyword in diagnosis_keywords)

            if is_diagnosis:
                date_str = record.get('diagnostic_date')
                date_obj = None
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    except:
                        pass

                source_type = record.get('diagnostic_source', '').lower()
                if 'surgical' in source_type or 'pathology' in source_type:
                    confidence = 0.95
                else:
                    confidence = 0.85

                evidence.append(DiagnosisEvidence(
                    diagnosis=record.get('diagnostic_name', ''),
                    source=EvidenceSource.SURGICAL_PATHOLOGY,
                    confidence=confidence,
                    date=date_obj,
                    raw_data=record,
                    extraction_method='keyword_fallback'
                ))

        logger.info(f"      → Found {len(evidence)} diagnoses from pathology via keyword fallback")
        return evidence

    def _extract_from_problem_lists(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from problem/condition lists (v_problem_list_diagnoses).

        V5.6 Tier 1: MedGemma reasoning-based extraction (changed from keywords).

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
        FROM v_problem_list_diagnoses
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND condition_display_name IS NOT NULL
          AND condition_display_name != ''
        ORDER BY onset_date DESC NULLS LAST, recorded_date DESC NULLS LAST
        """

        try:
            results = self.query_athena(query, "Querying v_problem_list_diagnoses for problem list evidence", suppress_output=True)

            if not results:
                logger.info("      → No problem list diagnoses found")
                return []

            logger.info(f"      → Found {len(results)} problem list entries")

            # V5.6: Use MedGemma reasoning if available
            if not self.medgemma_agent:
                logger.warning("      ⚠️  MedGemma not available, falling back to keyword extraction")
                return self._extract_from_problem_lists_keywords(results)

            evidence = []

            # Group similar diagnoses to reduce redundant Med Gemma calls
            unique_diagnoses = {}
            for record in results:
                dx_name = record.get('condition_display_name', '').strip()
                if dx_name and dx_name not in unique_diagnoses:
                    unique_diagnoses[dx_name] = record

            # Process each unique diagnosis with MedGemma
            for idx, (dx_name, record) in enumerate(list(unique_diagnoses.items())[:15]):  # Limit to 15

                # V5.6: Use structured prompt wrapper
                context = ClinicalContext(
                    patient_id=patient_fhir_id,
                    phase='PHASE_0_TIER_1_PROBLEM_LIST',
                    evidence_summary=f"Problem list diagnosis: {dx_name}"
                )

                wrapped_prompt = self.llm_wrapper.wrap_extraction_prompt(
                    task_description="Extract CNS tumor diagnosis from problem list entry",
                    document_text=f"PROBLEM LIST DIAGNOSIS:\n{dx_name}\n\nClinical Status: {record.get('clinical_status', 'unknown')}\nVerification Status: {record.get('verification_status', 'unknown')}",
                    expected_schema=self.llm_wrapper.create_diagnosis_extraction_schema(),
                    context=context,
                    max_document_length=1000
                )

                try:
                    response = self.medgemma_agent.query(wrapped_prompt, temperature=0.1)

                    # V5.6: Validate response
                    is_valid, extraction, error = self.llm_wrapper.validate_response(
                        response,
                        self.llm_wrapper.create_diagnosis_extraction_schema()
                    )

                    if not is_valid:
                        logger.debug(f"      Invalid LLM response for problem list {idx+1}: {error}")
                        continue

                    if extraction.get('diagnosis_found') and extraction.get('diagnosis'):
                        # Parse date (prefer onset_date, fallback to recorded_date)
                        date_str = record.get('onset_date') or record.get('recorded_date')
                        date_obj = None
                        if date_str:
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            except:
                                pass

                        # Confidence based on verification status
                        verification = record.get('verification_status', '').lower()
                        clinical_status = record.get('clinical_status', '').lower()
                        llm_confidence = extraction.get('confidence', 0.75)

                        if 'confirmed' in verification and 'active' in clinical_status:
                            base_confidence = 0.85
                        elif 'confirmed' in verification:
                            base_confidence = 0.80
                        else:
                            base_confidence = 0.70

                        final_confidence = min(base_confidence, llm_confidence)

                        evidence.append(DiagnosisEvidence(
                            diagnosis=extraction['diagnosis'],
                            source=EvidenceSource.PROBLEM_LIST,
                            confidence=final_confidence,
                            date=date_obj,
                            raw_data=record,
                            extraction_method='medgemma_reasoning'  # V5.6 marker
                        ))

                except Exception as e:
                    logger.debug(f"      Could not extract from problem list {idx+1}: {e}")
                    continue

            logger.info(f"      → Extracted {len(evidence)} diagnoses from problem lists via MedGemma reasoning")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from problem lists: {e}")
            return []

    def _extract_from_problem_lists_keywords(self, results: List[Dict]) -> List[DiagnosisEvidence]:
        """
        Fallback keyword-based extraction for problem lists when MedGemma unavailable.

        Args:
            results: Query results from v_problem_list_diagnoses

        Returns:
            List of DiagnosisEvidence from keyword extraction
        """
        evidence = []

        diagnosis_keywords = [
            'tumor', 'neoplasm', 'malignant', 'cancer',
            'glioma', 'glioblastoma', 'astrocytoma', 'ependymoma', 'medulloblastoma',
            'brain', 'cns', 'central nervous system'
        ]

        for record in results:
            condition_name = record.get('condition_display_name', '').lower()

            is_cns_diagnosis = any(keyword in condition_name for keyword in diagnosis_keywords)

            if is_cns_diagnosis:
                date_str = record.get('onset_date') or record.get('recorded_date')
                date_obj = None
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    except:
                        pass

                verification = record.get('verification_status', '').lower()
                if 'confirmed' in verification:
                    confidence = 0.80
                else:
                    confidence = 0.70

                evidence.append(DiagnosisEvidence(
                    diagnosis=record.get('condition_display_name', ''),
                    source=EvidenceSource.PROBLEM_LIST,
                    confidence=confidence,
                    date=date_obj,
                    raw_data=record,
                    extraction_method='keyword_fallback'
                ))

        logger.info(f"      → Found {len(evidence)} diagnoses from problem lists via keyword fallback")
        return evidence

    def _extract_from_imaging_reports(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Extract diagnosis from imaging reports (radiology reports).

        V5.6 Tier 1: MedGemma-based extraction from narrative radiology impressions.
        NOW uses self.medgemma_agent instead of local instantiation.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            List of DiagnosisEvidence from imaging reports
        """
        query = f"""
        SELECT DISTINCT
            study_date as report_date,
            study_description as report_type,
            result_information
        FROM v_imaging
        WHERE patient_fhir_id = '{patient_fhir_id}'
          AND result_information IS NOT NULL
          AND TRIM(result_information) != ''
        ORDER BY study_date DESC
        """

        try:
            results = self.query_athena(query, "Querying v_imaging for diagnosis evidence", suppress_output=True)

            if not results:
                logger.info("      → No imaging reports found")
                return []

            # V5.6: Use self.medgemma_agent if available
            if not self.medgemma_agent:
                logger.warning("      ⚠️  MedGemma not available, skipping imaging reports")
                return []

            evidence = []

            # Process each imaging report
            for record in results:
                report_text = record.get('result_information', '').strip()

                if not report_text:
                    continue

                # V5.6: Use structured prompt wrapper
                context = ClinicalContext(
                    patient_id=patient_fhir_id,
                    phase='PHASE_0_TIER_1_IMAGING',
                    evidence_summary=f"Extracting from imaging report dated {record.get('report_date')}"
                )

                wrapped_prompt = self.llm_wrapper.wrap_extraction_prompt(
                    task_description="Extract CNS tumor diagnosis from radiology report impression/findings",
                    document_text=report_text,
                    expected_schema=self.llm_wrapper.create_diagnosis_extraction_schema(),
                    context=context,
                    max_document_length=4000
                )

                try:
                    response = self.medgemma_agent.query(wrapped_prompt, temperature=0.1)

                    # V5.6: Validate response
                    is_valid, extraction, error = self.llm_wrapper.validate_response(
                        response,
                        self.llm_wrapper.create_diagnosis_extraction_schema()
                    )

                    if not is_valid:
                        logger.debug(f"      Invalid LLM response: {error}")
                        continue

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
                            extraction_method='medgemma_reasoning'  # V5.6 marker
                        ))

                except Exception as e:
                    logger.debug(f"      Could not extract from imaging report: {e}")
                    continue

            logger.info(f"      → Extracted {len(evidence)} diagnoses from imaging via MedGemma reasoning")
            return evidence

        except Exception as e:
            logger.error(f"      ❌ Error extracting from imaging reports: {e}")
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
            Most common diagnosis string, or None if no evidence
        """
        if not evidence_list:
            return None

        # Filter to high-confidence evidence (>0.7)
        high_conf = [e for e in evidence_list if e.confidence > 0.7]

        if not high_conf:
            return None

        # Count diagnosis occurrences
        diagnosis_counts = {}
        for evidence in high_conf:
            dx = evidence.diagnosis.lower().strip()
            diagnosis_counts[dx] = diagnosis_counts.get(dx, 0) + 1

        # Return most common
        if diagnosis_counts:
            most_common = max(diagnosis_counts.items(), key=lambda x: x[1])
            return most_common[0]

        return None
