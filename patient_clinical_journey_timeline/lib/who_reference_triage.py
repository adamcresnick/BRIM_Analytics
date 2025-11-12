#!/usr/bin/env python3
"""
WHO Reference Triage - Two-Stage Selective Retrieval

This module implements intelligent triage to select only the relevant section
of the WHO 2021 CNS Tumor Classification reference for a specific patient.

Instead of loading the full 1510-line reference (100K+ chars), we:
  1. Analyze Stage 1 extracted findings (age, IDH status, molecular markers)
  2. Determine which WHO section is most relevant
  3. Load only preamble + that section (~100-200 lines vs 1000+)

Benefits:
  - 5-10x less context usage
  - Better classification accuracy (focused reference)
  - Scales to all tumor types without context overflow

WHO Reference Structure (line numbers):
  - Lines 1-70: Preamble (diagnostic principles, workflow)
  - Lines 71-200: Adult-type diffuse gliomas
  - Lines 201-350: Pediatric-type diffuse gliomas
  - Lines 351-500: Ependymomas
  - Lines 501-650: Embryonal tumors
  - Lines 651-800: Other gliomas
  - Lines 801+: Other tumor types

Usage:
    from lib.who_reference_triage import WHOReferenceTriage

    triage = WHOReferenceTriage(WHO_2021_REFERENCE_PATH)

    # Analyze Stage 1 findings
    section = triage.identify_relevant_section(stage1_findings)

    # Load only relevant section
    relevant_reference = triage.load_selective_reference(section)
"""

import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class WHOReferenceTriage:
    """
    Triages patient to relevant WHO 2021 CNS classification section.

    Attributes:
        reference_path: Path to WHO 2021 CNS Tumor Classification.md
    """

    # WHO Reference section line ranges (approximate)
    SECTION_RANGES = {
        'preamble': (1, 70),
        'adult_diffuse_gliomas': (71, 200),
        'pediatric_diffuse_gliomas': (201, 350),
        'ependymomas': (351, 500),
        'embryonal_tumors': (501, 650),
        'other_gliomas': (651, 800),
        'meningiomas': (801, 950),
        'other_tumors': (951, 1510)
    }

    def __init__(self, reference_path: Path):
        """
        Initialize triage with WHO reference path.

        Args:
            reference_path: Path to WHO 2021 CNS Tumor Classification.md
        """
        self.reference_path = Path(reference_path)
        if not self.reference_path.exists():
            logger.error(f"WHO reference not found: {reference_path}")

    def identify_relevant_section(self, stage1_findings: Dict) -> str:
        """
        Analyze Stage 1 findings to identify relevant WHO section.

        Args:
            stage1_findings: Dictionary from Stage 1 extraction with:
                - molecular_markers: List of marker dicts
                - histology_findings: List of histology dicts
                - tumor_location: String (if available)
                - patient_age_at_diagnosis: Integer (if available)

        Returns:
            Section key (e.g., "adult_diffuse_gliomas", "pediatric_diffuse_gliomas")
        """
        # Extract key triage factors
        age = stage1_findings.get('patient_age_at_diagnosis')
        markers = {m.get('marker_name'): m for m in stage1_findings.get('molecular_markers', [])}
        histology = stage1_findings.get('histology_findings', [])
        location = (stage1_findings.get('tumor_location') or '').lower()

        logger.info(f"🔍 WHO Triage: age={str(age) if age is not None else ''}, markers={list(markers.keys())}, location={location}")

        # Triage logic (in priority order)

        # 1. IDH status is the primary discriminator for gliomas
        if 'IDH1' in markers or 'IDH2' in markers:
            idh_status = markers.get('IDH1', markers.get('IDH2', {})).get('status', '')

            if idh_status == 'POSITIVE':
                # IDH-mutant gliomas
                # Check for 1p/19q codeletion (oligodendroglioma)
                has_1p19q = '1p/19q' in markers or any('1p' in m or '19q' in m for m in markers.keys())

                if has_1p19q:
                    logger.info("  → Adult-type diffuse gliomas (IDH-mutant, likely oligodendroglioma)")
                    return 'adult_diffuse_gliomas'

                # Check for ATRX/TP53 (astrocytoma)
                has_atrx = 'ATRX' in markers
                has_tp53 = 'TP53' in markers

                if has_atrx or has_tp53:
                    logger.info("  → Adult-type diffuse gliomas (IDH-mutant astrocytoma)")
                    return 'adult_diffuse_gliomas'

                # Default IDH-mutant → adult gliomas
                logger.info("  → Adult-type diffuse gliomas (IDH-mutant)")
                return 'adult_diffuse_gliomas'

            elif idh_status == 'NEGATIVE':
                # IDH-wildtype gliomas
                # Check age to discriminate adult vs pediatric
                if age and age < 18:
                    logger.info("  → Pediatric-type diffuse gliomas (IDH-wildtype, age < 18)")
                    return 'pediatric_diffuse_gliomas'
                else:
                    logger.info("  → Adult-type diffuse gliomas (IDH-wildtype glioblastoma likely)")
                    return 'adult_diffuse_gliomas'

        # 2. Check for H3 mutations (pediatric high-grade gliomas)
        if 'H3-3A' in markers or 'H3F3A' in markers or 'HIST1H3B' in markers:
            logger.info("  → Pediatric-type diffuse gliomas (H3-mutant)")
            return 'pediatric_diffuse_gliomas'

        # 3. Check for BRAF V600E (pediatric low-grade gliomas)
        if 'BRAF' in markers:
            braf_details = markers['BRAF'].get('details', '').upper()
            if 'V600E' in braf_details:
                logger.info("  → Pediatric-type diffuse gliomas (BRAF V600E)")
                return 'pediatric_diffuse_gliomas'

        # 4. Check for ependymoma markers (location-based)
        ependymoma_keywords = ['ependymoma', 'ependymal']
        if any(keyword in location for keyword in ependymoma_keywords):
            logger.info("  → Ependymomas (location-based)")
            return 'ependymomas'

        # Check histology for ependymoma
        for h in histology:
            finding = h.get('finding', '').lower()
            if any(keyword in finding for keyword in ependymoma_keywords):
                logger.info("  → Ependymomas (histology-based)")
                return 'ependymomas'

        # 5. Check for embryonal tumor markers
        embryonal_markers = ['SMARCB1', 'SMARCA4', 'MYC', 'MYCN', 'APC', 'CTNNB1']
        # APC and CTNNB1 are WNT pathway markers for medulloblastoma
        if any(m in markers for m in embryonal_markers):
            logger.info("  → Embryonal tumors (molecular markers)")
            return 'embryonal_tumors'

        # Check histology for embryonal tumors
        embryonal_keywords = ['medulloblastoma', 'atypical teratoid', 'pnet', 'embryonal']
        for h in histology:
            finding = h.get('finding', '').lower()
            if any(keyword in finding for keyword in embryonal_keywords):
                logger.info("  → Embryonal tumors (histology-based)")
                return 'embryonal_tumors'

        # Check problem list diagnoses for embryonal tumors (NEW - Bug #8 fix)
        problem_diagnoses = stage1_findings.get('problem_list_diagnoses', [])
        for prob in problem_diagnoses:
            diagnosis = prob.get('diagnosis', '').lower()
            if any(keyword in diagnosis for keyword in embryonal_keywords):
                logger.info(f"  → Embryonal tumors (problem list diagnosis: '{prob.get('diagnosis', '')}')")
                return 'embryonal_tumors'

        # 6. Age-based default triage
        if age and age < 18:
            logger.info("  → Pediatric-type diffuse gliomas (age < 18, default)")
            return 'pediatric_diffuse_gliomas'
        elif age and age >= 40:
            logger.info("  → Adult-type diffuse gliomas (age >= 40, default)")
            return 'adult_diffuse_gliomas'

        # 7. Tier 2B: MedGemma clinical reasoning for ambiguous cases
        logger.info("  → Tier 2A did not produce clear match, attempting Tier 2B (MedGemma reasoning)")
        triage_decision = self._medgemma_clinical_triage(stage1_findings)

        # Determine which section to validate with Tier 2C
        section_to_validate = None

        if triage_decision and triage_decision.get('confidence', 0) >= 0.7:
            section_to_validate = triage_decision['section']
            confidence = triage_decision['confidence']
            reasoning = triage_decision.get('reasoning', '')
            logger.info(f"  → Tier 2B: {section_to_validate} (confidence: {confidence:.2f})")
            logger.info(f"      Reasoning: {reasoning[:150]}...")
        else:
            # Tier 2B failed, use default for validation
            section_to_validate = 'adult_diffuse_gliomas'
            logger.warning("  → Tier 2B did not produce confident result, using default for Tier 2C validation")

        # 8. Tier 2C: Investigation Engine validation of triage decision
        validation = self._investigation_engine_validate_triage(section_to_validate, stage1_findings)

        if validation['conflicts_detected']:
            logger.warning(f"  ⚠️  Tier 2C detected conflict: {validation['reason']}")
            logger.info(f"  → Tier 2C: Correcting to '{validation['corrected_section']}' (confidence: {validation['confidence']:.2f})")
            return validation['corrected_section']

        # Return validated section
        return section_to_validate

    def load_selective_reference(self, section_key: str) -> str:
        """
        Load preamble + specific section from WHO reference.

        Args:
            section_key: Section key from identify_relevant_section()

        Returns:
            Combined preamble + section text (much smaller than full reference)
        """
        if not self.reference_path.exists():
            logger.error(f"WHO reference not found: {self.reference_path}")
            return ""

        # Read full reference
        with open(self.reference_path, 'r') as f:
            lines = f.readlines()

        # Extract preamble
        preamble_start, preamble_end = self.SECTION_RANGES['preamble']
        preamble = ''.join(lines[preamble_start - 1:preamble_end])

        # Extract relevant section
        if section_key not in self.SECTION_RANGES:
            logger.warning(f"Unknown section key: {section_key}, using full reference")
            return ''.join(lines)

        section_start, section_end = self.SECTION_RANGES[section_key]
        section = ''.join(lines[section_start - 1:section_end])

        # Combine preamble + section
        combined = f"""
================================================================================
WHO 2021 CNS TUMOR CLASSIFICATION REFERENCE (SELECTIVE RETRIEVAL)
================================================================================

SECTION: {section_key.replace('_', ' ').title()}

================================================================================
PREAMBLE: DIAGNOSTIC PRINCIPLES
================================================================================

{preamble}

================================================================================
RELEVANT CLASSIFICATION SECTION
================================================================================

{section}
"""

        logger.info(f"📖 Loaded WHO reference: preamble ({preamble_end - preamble_start + 1} lines) + "
                   f"{section_key} ({section_end - section_start + 1} lines) = "
                   f"{preamble_end - preamble_start + section_end - section_start + 2} total lines "
                   f"({len(combined)} chars)")

        return combined

    def get_section_info(self, section_key: str) -> Dict:
        """
        Get metadata about a WHO reference section.

        Args:
            section_key: Section key (e.g., "adult_diffuse_gliomas")

        Returns:
            Dictionary with section metadata
        """
        if section_key not in self.SECTION_RANGES:
            return {}

        start, end = self.SECTION_RANGES[section_key]
        return {
            'section_key': section_key,
            'section_name': section_key.replace('_', ' ').title(),
            'line_range': f"{start}-{end}",
            'total_lines': end - start + 1
        }

    def estimate_context_savings(self, section_key: str) -> Dict:
        """
        Estimate context window savings from selective retrieval.

        Args:
            section_key: Section key for selective loading

        Returns:
            Dictionary with savings statistics
        """
        preamble_lines = self.SECTION_RANGES['preamble'][1] - self.SECTION_RANGES['preamble'][0] + 1
        section_lines = self.SECTION_RANGES[section_key][1] - self.SECTION_RANGES[section_key][0] + 1
        selective_total = preamble_lines + section_lines

        full_total = 1510  # Approximate full reference lines

        savings_pct = ((full_total - selective_total) / full_total) * 100

        return {
            'preamble_lines': preamble_lines,
            'section_lines': section_lines,
            'selective_total_lines': selective_total,
            'full_reference_lines': full_total,
            'lines_saved': full_total - selective_total,
            'savings_percentage': round(savings_pct, 1)
        }

    def _medgemma_clinical_triage(self, stage1_findings: Dict) -> Optional[Dict]:
        """
        Tier 2B: Use MedGemma to reason about which WHO section is most relevant.

        This is called when Tier 2A rule-based matching doesn't produce a clear match.
        Uses LLM to make clinical reasoning about triage based on all available evidence.

        Args:
            stage1_findings: Dictionary from Stage 1 extraction

        Returns:
            Dictionary with keys:
                - section: WHO section key
                - confidence: Float 0-1
                - reasoning: String explaining the triage decision

        Returns None if MedGemma is not available or encounters an error.
        """
        try:
            # Import MedGemmaAgent (lazy import to avoid circular dependency)
            from agents.medgemma_agent import MedGemmaAgent

            medgemma = MedGemmaAgent(model='gemma2:27b')

            # Prepare clinical context for triage
            age = stage1_findings.get('patient_age_at_diagnosis')
            markers = stage1_findings.get('molecular_markers', [])
            histology = stage1_findings.get('histology_findings', [])
            location = stage1_findings.get('tumor_location', 'Unknown')
            problem_diagnoses = stage1_findings.get('problem_list_diagnoses', [])

            # Build clinical summary
            clinical_summary = f"""
Patient Age: {age if age is not None else 'Unknown'}
Tumor Location: {location}

Molecular Markers ({len(markers)} found):
"""
            for m in markers:
                marker_name = m.get('marker_name', 'Unknown')
                status = m.get('status', 'Unknown')
                details = m.get('details', '')
                clinical_summary += f"  - {marker_name}: {status}"
                if details:
                    clinical_summary += f" ({details[:100]})"
                clinical_summary += "\n"

            if histology:
                clinical_summary += f"\nHistology Findings ({len(histology)} found):\n"
                for h in histology:
                    finding = h.get('finding', 'Unknown')
                    clinical_summary += f"  - {finding[:150]}\n"

            if problem_diagnoses:
                clinical_summary += f"\nProblem List Diagnoses ({len(problem_diagnoses)} found):\n"
                for p in problem_diagnoses:
                    diagnosis = p.get('diagnosis', 'Unknown')
                    clinical_summary += f"  - {diagnosis[:150]}\n"

            # Construct triage prompt
            triage_prompt = f"""You are a neuropathologist expert in WHO 2021 CNS Tumor Classification.

Given the following clinical findings, determine which WHO 2021 CNS tumor classification section is MOST relevant for this patient.

CLINICAL FINDINGS:
{clinical_summary}

WHO 2021 CLASSIFICATION SECTIONS:
1. adult_diffuse_gliomas - Adult-type diffuse gliomas (IDH-mutant/wildtype glioblastoma, astrocytoma, oligodendroglioma)
2. pediatric_diffuse_gliomas - Pediatric-type diffuse gliomas (H3-mutant, BRAF-mutant, IDH-wildtype pediatric gliomas)
3. ependymomas - Ependymal tumors (supratentorial, posterior fossa, spinal)
4. embryonal_tumors - Embryonal tumors (medulloblastoma WNT/SHH/Group 3/4, atypical teratoid/rhabdoid tumor, PNET)
5. other_gliomas - Circumscribed astrocytic gliomas, glioneuronal tumors
6. meningiomas - Meningeal tumors
7. other_tumors - All other CNS tumors

TASK:
Based on the clinical findings above, determine the MOST appropriate WHO section.

IMPORTANT CLINICAL REASONING RULES:
- APC, CTNNB1 (beta-catenin), WNT pathway markers → embryonal_tumors (medulloblastoma WNT-activated)
- SMARCB1, SMARCA4 loss → embryonal_tumors (atypical teratoid/rhabdoid tumor)
- MYC, MYCN amplification → embryonal_tumors (medulloblastoma)
- IDH1/IDH2 mutation → adult_diffuse_gliomas (unless age < 18)
- H3F3A, HIST1H3B mutation → pediatric_diffuse_gliomas
- BRAF V600E → pediatric_diffuse_gliomas (low-grade glioma)
- Age < 18 + IDH-wildtype → pediatric_diffuse_gliomas
- Age >= 40 + IDH-wildtype → adult_diffuse_gliomas
- Problem list diagnoses mentioning "medulloblastoma" → embryonal_tumors

Return ONLY a JSON object with this exact structure:
{{
    "section": "<section_key from list above>",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<1-2 sentence clinical reasoning for this triage decision>"
}}

DO NOT include any other text, explanations, or markdown formatting. Return ONLY the JSON object."""

            logger.info("  🧠 Tier 2B: Querying MedGemma for clinical triage reasoning...")

            # Query MedGemma
            response = medgemma.query(triage_prompt, temperature=0.1)

            if not response:
                logger.warning("  ⚠️  Tier 2B: MedGemma returned empty response")
                return None

            # Parse JSON response
            import json
            import re

            # Try to extract JSON from response (handle cases where model adds extra text)
            json_match = re.search(r'\{[^{}]*"section"[^{}]*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)

            try:
                triage_result = json.loads(response)
            except json.JSONDecodeError as e:
                logger.warning(f"  ⚠️  Tier 2B: Failed to parse MedGemma JSON response: {e}")
                logger.warning(f"       Response was: {response[:200]}")
                return None

            # Validate response structure
            if 'section' not in triage_result or 'confidence' not in triage_result:
                logger.warning(f"  ⚠️  Tier 2B: MedGemma response missing required fields")
                return None

            # Validate section key
            section = triage_result['section']
            if section not in self.SECTION_RANGES:
                logger.warning(f"  ⚠️  Tier 2B: MedGemma returned invalid section: {section}")
                return None

            return triage_result

        except ImportError:
            logger.warning("  ⚠️  Tier 2B: MedGemmaAgent not available")
            return None
        except Exception as e:
            logger.error(f"  ❌ Tier 2B: Error in MedGemma triage: {e}")
            return None

    def _investigation_engine_validate_triage(
        self,
        triage_section: str,
        stage1_findings: Dict
    ) -> Dict:
        """
        Tier 2C: Use Investigation Engine to validate triage decision against evidence.

        This is the final validation layer that detects conflicts between the triage
        decision and clinical evidence (molecular markers, problem list diagnoses).

        Args:
            triage_section: WHO section from Tier 2A or Tier 2B
            stage1_findings: Dictionary from Stage 1 extraction

        Returns:
            Dictionary with keys:
                - conflicts_detected: Boolean
                - reason: String explaining conflict (if any)
                - corrected_section: Suggested WHO section (if conflict detected)
                - confidence: Float 0-1
        """
        logger.info(f"  🔍 Tier 2C: Validating triage decision '{triage_section}'...")

        validation_result = {
            'conflicts_detected': False,
            'reason': None,
            'corrected_section': triage_section,
            'confidence': 1.0
        }

        markers = stage1_findings.get('molecular_markers', [])
        problem_diagnoses = stage1_findings.get('problem_list_diagnoses', [])

        # Extract marker names for easier checking
        marker_names = [m.get('marker_name', '').upper() for m in markers]

        # ===========================================
        # CONFLICT CHECK 1: Embryonal Markers + Non-Embryonal Section
        # ===========================================
        embryonal_markers = ['APC', 'CTNNB1', 'WNT', 'SHH', 'SMARCB1', 'SMARCA4',
                             'MYC', 'MYCN', 'PTCH1', 'SMO', 'SUFU']

        has_embryonal_markers = any(marker in marker_names for marker in embryonal_markers)

        if has_embryonal_markers and triage_section != 'embryonal_tumors':
            conflict_markers = [m for m in embryonal_markers if m in marker_names]
            logger.warning(f"  ⚠️  Tier 2C CONFLICT: Found embryonal markers {conflict_markers} "
                         f"but triage selected '{triage_section}'")

            validation_result['conflicts_detected'] = True
            validation_result['reason'] = (
                f"Molecular markers {conflict_markers} are specific to embryonal tumors "
                f"but triage selected '{triage_section}'. This is a biological conflict."
            )
            validation_result['corrected_section'] = 'embryonal_tumors'
            validation_result['confidence'] = 0.95
            logger.info(f"  → Tier 2C: Correcting triage to 'embryonal_tumors' (confidence: 0.95)")
            return validation_result

        # ===========================================
        # CONFLICT CHECK 2: Problem List Diagnoses + Mismatched Section
        # ===========================================
        for prob in problem_diagnoses:
            diagnosis_text = prob.get('diagnosis', '').lower()

            # Check for medulloblastoma in problem list
            if 'medulloblastoma' in diagnosis_text and triage_section != 'embryonal_tumors':
                logger.warning(f"  ⚠️  Tier 2C CONFLICT: Problem list contains '{prob.get('diagnosis', '')}' "
                             f"but triage selected '{triage_section}'")

                validation_result['conflicts_detected'] = True
                validation_result['reason'] = (
                    f"Problem list diagnosis '{prob.get('diagnosis', '')}' indicates medulloblastoma "
                    f"(embryonal tumor) but triage selected '{triage_section}'. This is a clinical conflict."
                )
                validation_result['corrected_section'] = 'embryonal_tumors'
                validation_result['confidence'] = 0.90
                logger.info(f"  → Tier 2C: Correcting triage to 'embryonal_tumors' (confidence: 0.90)")
                return validation_result

            # Check for glioblastoma in problem list
            if 'glioblastoma' in diagnosis_text and triage_section not in ['adult_diffuse_gliomas', 'pediatric_diffuse_gliomas']:
                logger.warning(f"  ⚠️  Tier 2C CONFLICT: Problem list contains '{prob.get('diagnosis', '')}' "
                             f"but triage selected '{triage_section}'")

                validation_result['conflicts_detected'] = True
                validation_result['reason'] = (
                    f"Problem list diagnosis '{prob.get('diagnosis', '')}' indicates glioblastoma "
                    f"but triage selected '{triage_section}'. This is a clinical conflict."
                )
                validation_result['corrected_section'] = 'adult_diffuse_gliomas'
                validation_result['confidence'] = 0.85
                logger.info(f"  → Tier 2C: Correcting triage to 'adult_diffuse_gliomas' (confidence: 0.85)")
                return validation_result

            # Check for ependymoma in problem list
            if 'ependymoma' in diagnosis_text and triage_section != 'ependymomas':
                logger.warning(f"  ⚠️  Tier 2C CONFLICT: Problem list contains '{prob.get('diagnosis', '')}' "
                             f"but triage selected '{triage_section}'")

                validation_result['conflicts_detected'] = True
                validation_result['reason'] = (
                    f"Problem list diagnosis '{prob.get('diagnosis', '')}' indicates ependymoma "
                    f"but triage selected '{triage_section}'. This is a clinical conflict."
                )
                validation_result['corrected_section'] = 'ependymomas'
                validation_result['confidence'] = 0.90
                logger.info(f"  → Tier 2C: Correcting triage to 'ependymomas' (confidence: 0.90)")
                return validation_result

        # ===========================================
        # NO CONFLICTS DETECTED
        # ===========================================
        logger.info(f"  ✅ Tier 2C: No conflicts detected, triage decision '{triage_section}' validated")
        return validation_result
