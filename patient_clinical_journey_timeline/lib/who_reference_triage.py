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

        logger.info(f"🔍 WHO Triage: age={age}, markers={list(markers.keys())}, location={location}")

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
        embryonal_markers = ['SMARCB1', 'SMARCA4', 'MYC', 'MYCN']
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

        # 6. Age-based default triage
        if age and age < 18:
            logger.info("  → Pediatric-type diffuse gliomas (age < 18, default)")
            return 'pediatric_diffuse_gliomas'
        elif age and age >= 40:
            logger.info("  → Adult-type diffuse gliomas (age >= 40, default)")
            return 'adult_diffuse_gliomas'

        # 7. Default to adult gliomas if no clear triage
        logger.warning("  → Adult-type diffuse gliomas (DEFAULT - no clear triage factors)")
        return 'adult_diffuse_gliomas'

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
