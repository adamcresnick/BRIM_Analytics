"""
Diagnosis Validator - Stage 3 Validation Layer

This module implements biological plausibility validation for WHO 2021 CNS tumor
classifications. It cross-validates diagnoses against molecular markers, histology,
and problem list diagnoses to catch biologically impossible combinations.

Purpose:
- Validate WHO classification against extracted molecular markers
- Detect biologically impossible marker-diagnosis combinations
- Cross-check against problem list diagnoses for conflicts
- Provide confidence adjustments based on evidence quality

Author: RADIANT Analytics Team
Date: 2025-01-12
Version: V5.1
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# Biological Plausibility Rules
# Format: (marker, diagnosis) -> violation reason
IMPOSSIBLE_COMBINATIONS = {
    ('APC', 'glioblastoma'): "APC mutations are specific to WNT-activated medulloblastoma and NEVER occur in glioblastoma",
    ('CTNNB1', 'glioblastoma'): "CTNNB1 (beta-catenin) mutations are WNT pathway markers specific to medulloblastoma",
    ('IDH1', 'medulloblastoma'): "IDH1 mutations are specific to gliomas and NEVER occur in medulloblastoma",
    ('IDH2', 'medulloblastoma'): "IDH2 mutations are specific to gliomas and NEVER occur in medulloblastoma",
    ('1p/19q', 'medulloblastoma'): "1p/19q codeletion is specific to oligodendrogliomas and never seen in medulloblastoma",
    ('1p/19q', 'medulloblastoma'): "1p/19q codeletion is oligodendroglioma-specific",
    ('H3 K27', 'medulloblastoma'): "H3 K27 mutations are specific to diffuse midline gliomas, not medulloblastoma",
    ('H3-3A', 'medulloblastoma'): "H3-3A mutations are specific to pediatric high-grade gliomas, not medulloblastoma",
    ('SMARCB1', 'glioblastoma'): "SMARCB1 loss is specific to atypical teratoid/rhabdoid tumors (ATRT), not glioblastoma",
    ('SMARCA4', 'glioblastoma'): "SMARCA4 loss is specific to ATRT, not glioblastoma",
    ('APC', 'astrocytoma'): "APC mutations are medulloblastoma-specific, not found in astrocytomas",
    ('APC', 'ependymoma'): "APC mutations are medulloblastoma-specific, not found in ependymomas",
    ('CTNNB1', 'astrocytoma'): "CTNNB1 mutations in CNS tumors are medulloblastoma-specific",
}

# Highly suspicious but not impossible combinations (warnings)
SUSPICIOUS_COMBINATIONS = {
    ('BRAF V600E', 'medulloblastoma'): "BRAF V600E is rare in medulloblastoma, more common in low-grade gliomas",
    ('EGFR', 'medulloblastoma'): "EGFR amplification is typical for glioblastoma, very rare in medulloblastoma",
    ('TP53', 'wnt medulloblastoma'): "TP53 mutations are uncommon in WNT-activated medulloblastoma (typically TP53 wild-type)",
}

# Diagnosis keywords for conflict detection
DIAGNOSIS_KEYWORDS = {
    'glioblastoma': ['glioblastoma', 'gbm', 'grade 4 astrocytoma', 'grade iv astrocytoma'],
    'astrocytoma': ['astrocytoma', 'diffuse astrocytic', 'astrocytic glioma'],
    'oligodendroglioma': ['oligodendroglioma', 'oligodendroglial'],
    'medulloblastoma': ['medulloblastoma', 'wnt', 'shh', 'group 3', 'group 4'],
    'ependymoma': ['ependymoma', 'ependymal'],
    'atrt': ['atypical teratoid', 'rhabdoid', 'atrt'],
    'dmg': ['diffuse midline glioma', 'dmg', 'dipg'],
}


class DiagnosisValidator:
    """
    Stage 3 validation layer that cross-validates WHO classification
    against molecular markers and problem list diagnoses.
    """

    def __init__(self):
        """Initialize the diagnosis validator"""
        self.impossible_combinations = IMPOSSIBLE_COMBINATIONS
        self.suspicious_combinations = SUSPICIOUS_COMBINATIONS
        self.diagnosis_keywords = DIAGNOSIS_KEYWORDS

    def validate_diagnosis(
        self,
        who_classification: Dict[str, Any],
        stage1_findings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 3: Cross-validate WHO classification against all evidence.

        Args:
            who_classification: WHO 2021 classification from Stage 2
            stage1_findings: Stage 1 extraction findings

        Returns:
            Validated diagnosis with validation metadata
        """
        logger.info("=" * 80)
        logger.info("STAGE 3: DIAGNOSIS VALIDATION")
        logger.info("=" * 80)

        diagnosis = who_classification.get('who_2021_diagnosis', '')
        markers = stage1_findings.get('molecular_markers', [])
        problem_diagnoses = stage1_findings.get('problem_list_diagnoses', [])

        validation_result = {
            'is_valid': True,
            'confidence': who_classification.get('confidence', 0.5),
            'violations': [],
            'warnings': [],
            'conflicts': []
        }

        # Check 1: Biological plausibility (critical violations)
        logger.info("   [Check 1] Biological plausibility...")
        violations = self._check_biological_plausibility(diagnosis, markers)
        if violations:
            validation_result['is_valid'] = False
            validation_result['violations'].extend(violations)
            validation_result['confidence'] = 0.1  # Very low confidence for violated diagnoses

            logger.error(f"   ❌ CRITICAL: Diagnosis '{diagnosis}' fails biological plausibility")
            for v in violations:
                logger.error(f"      {v}")
        else:
            logger.info("   ✅ No biological plausibility violations")

        # Check 2: Suspicious combinations (warnings, not failures)
        logger.info("   [Check 2] Checking for suspicious marker combinations...")
        warnings = self._check_suspicious_combinations(diagnosis, markers)
        if warnings:
            validation_result['warnings'].extend(warnings)
            validation_result['confidence'] *= 0.9  # Slight confidence penalty

            for w in warnings:
                logger.warning(f"   ⚠️  {w}")
        else:
            logger.info("   ✅ No suspicious combinations detected")

        # Check 3: Cross-check against problem list diagnoses
        logger.info("   [Check 3] Cross-checking against problem list diagnoses...")
        conflicts = self._check_problem_list_consistency(diagnosis, problem_diagnoses)
        if conflicts:
            validation_result['conflicts'].extend(conflicts)
            validation_result['confidence'] *= 0.8  # Moderate confidence penalty

            logger.warning(f"   ⚠️  Diagnosis conflicts with problem list:")
            for c in conflicts:
                logger.warning(f"      {c}")
        else:
            logger.info("   ✅ Consistent with problem list diagnoses")

        # Check 4: Marker-diagnosis consistency
        logger.info("   [Check 4] Marker-diagnosis consistency...")
        marker_support = self._check_marker_support(diagnosis, markers)
        if marker_support['has_contradictions']:
            validation_result['warnings'].extend(marker_support['contradictions'])
            logger.warning("   ⚠️  Some markers contradict the diagnosis")
        if marker_support['has_support']:
            logger.info(f"   ✅ Diagnosis supported by {len(marker_support['supporting_markers'])} markers")
        else:
            logger.warning("   ⚠️  No direct molecular marker support for diagnosis")
            validation_result['confidence'] *= 0.9

        # Final validation summary
        logger.info("=" * 80)
        logger.info(f"STAGE 3 VALIDATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"   Diagnosis: {diagnosis}")
        logger.info(f"   Valid: {validation_result['is_valid']}")
        # Handle both float and string confidence values
        conf_value = validation_result['confidence']
        if isinstance(conf_value, (int, float)):
            logger.info(f"   Confidence: {conf_value:.2f}")
        else:
            logger.info(f"   Confidence: {conf_value}")
        logger.info(f"   Violations: {len(validation_result['violations'])}")
        logger.info(f"   Warnings: {len(validation_result['warnings'])}")
        logger.info(f"   Conflicts: {len(validation_result['conflicts'])}")

        # Attach validation metadata to classification
        who_classification['validation'] = validation_result
        who_classification['confidence'] = validation_result['confidence']

        return who_classification

    def _check_biological_plausibility(
        self,
        diagnosis: str,
        markers: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Check for biologically impossible marker-diagnosis combinations.

        Returns:
            List of violation messages (empty if plausible)
        """
        violations = []
        diagnosis_lower = diagnosis.lower()

        for marker_dict in markers:
            marker_name = marker_dict.get('marker_name', '').upper()

            # Check each impossible combination
            for (forbidden_marker, forbidden_diagnosis), reason in self.impossible_combinations.items():
                forbidden_marker_upper = forbidden_marker.upper()
                forbidden_diagnosis_lower = forbidden_diagnosis.lower()

                # Check if this marker is forbidden for this diagnosis
                if marker_name == forbidden_marker_upper and forbidden_diagnosis_lower in diagnosis_lower:
                    violations.append(
                        f"IMPOSSIBLE: {marker_name} + {diagnosis} - {reason}"
                    )
                # Also check partial matches (e.g., "H3-3A" matches "H3 K27")
                elif forbidden_marker_upper in marker_name and forbidden_diagnosis_lower in diagnosis_lower:
                    violations.append(
                        f"IMPOSSIBLE: {marker_name} + {diagnosis} - {reason}"
                    )

        return violations

    def _check_suspicious_combinations(
        self,
        diagnosis: str,
        markers: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Check for suspicious (rare but not impossible) combinations.

        Returns:
            List of warning messages
        """
        warnings = []
        diagnosis_lower = diagnosis.lower()

        for marker_dict in markers:
            marker_name = marker_dict.get('marker_name', '').upper()
            marker_details = marker_dict.get('details', '').upper()

            # Check suspicious combinations
            for (suspicious_marker, suspicious_diagnosis), reason in self.suspicious_combinations.items():
                suspicious_marker_upper = suspicious_marker.upper()
                suspicious_diagnosis_lower = suspicious_diagnosis.lower()

                # Check marker name or details
                if (suspicious_marker_upper in marker_name or suspicious_marker_upper in marker_details) \
                   and suspicious_diagnosis_lower in diagnosis_lower:
                    warnings.append(
                        f"SUSPICIOUS: {marker_name} + {diagnosis} - {reason}"
                    )

        return warnings

    def _check_problem_list_consistency(
        self,
        who_diagnosis: str,
        problem_diagnoses: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Cross-check WHO diagnosis against problem list diagnoses.

        Returns:
            List of conflict messages
        """
        conflicts = []
        who_diag_lower = who_diagnosis.lower()

        # Identify which diagnosis category the WHO classification belongs to
        who_category = None
        for category, keywords in self.diagnosis_keywords.items():
            if any(kw in who_diag_lower for kw in keywords):
                who_category = category
                break

        # Check each problem list diagnosis
        for prob in problem_diagnoses:
            prob_diagnosis = prob.get('diagnosis', '').lower()

            # Identify category of problem list diagnosis
            prob_category = None
            for category, keywords in self.diagnosis_keywords.items():
                if any(kw in prob_diagnosis for kw in keywords):
                    prob_category = category
                    break

            # If both have categories and they differ, flag conflict
            if who_category and prob_category and who_category != prob_category:
                conflicts.append(
                    f"WHO diagnosis '{who_diagnosis}' ({who_category}) conflicts with "
                    f"problem list diagnosis '{prob.get('diagnosis', '')}' ({prob_category})"
                )

        return conflicts

    def _check_marker_support(
        self,
        diagnosis: str,
        markers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check if molecular markers support or contradict the diagnosis.

        Returns:
            Dict with supporting_markers, contradicting_markers, and flags
        """
        diagnosis_lower = diagnosis.lower()
        supporting_markers = []
        contradicting_markers = []

        # Define marker-diagnosis support relationships
        supportive_pairs = {
            'medulloblastoma': ['APC', 'CTNNB1', 'PTCH1', 'SMO', 'SUFU', 'MYC', 'MYCN', 'SMARCB1'],
            'glioblastoma': ['IDH1', 'IDH2', 'EGFR', 'TP53', 'PTEN', 'TERT', 'MGMT'],
            'astrocytoma': ['IDH1', 'IDH2', 'TP53', 'ATRX'],
            'oligodendroglioma': ['IDH1', 'IDH2', '1p/19q'],
            'ependymoma': ['C11orf95', 'RELA', 'YAP1', 'ZFTA'],
            'atrt': ['SMARCB1', 'SMARCA4'],
            'dmg': ['H3-3A', 'H3F3A', 'HIST1H3B', 'EZHIP'],
        }

        # Find diagnosis category
        for category, supported_markers in supportive_pairs.items():
            if category in diagnosis_lower:
                for marker_dict in markers:
                    marker_name = marker_dict.get('marker_name', '').upper()

                    # Check if marker supports this diagnosis
                    if any(sm.upper() in marker_name for sm in supported_markers):
                        supporting_markers.append(marker_name)

        # Check for contradictions (markers that support different diagnosis)
        for category, supported_markers in supportive_pairs.items():
            if category not in diagnosis_lower:  # Different category
                for marker_dict in markers:
                    marker_name = marker_dict.get('marker_name', '').upper()

                    if any(sm.upper() in marker_name for sm in supported_markers):
                        contradicting_markers.append(
                            f"{marker_name} typically indicates {category}, not {diagnosis}"
                        )

        return {
            'has_support': len(supporting_markers) > 0,
            'has_contradictions': len(contradicting_markers) > 0,
            'supporting_markers': supporting_markers,
            'contradictions': contradicting_markers
        }


def test_validator():
    """Test the diagnosis validator with sample data"""
    validator = DiagnosisValidator()

    # Test Case 1: APC + Glioblastoma (should fail)
    print("\n" + "=" * 80)
    print("TEST CASE 1: APC + Glioblastoma (SHOULD FAIL)")
    print("=" * 80)

    who_classification = {
        'who_2021_diagnosis': 'Glioblastoma, IDH-wildtype',
        'confidence': 0.85
    }

    stage1_findings = {
        'molecular_markers': [
            {'marker_name': 'APC', 'status': 'POSITIVE', 'details': 'c.2995C>T mutation'},
            {'marker_name': 'TP53', 'status': 'POSITIVE'}
        ],
        'problem_list_diagnoses': [
            {'diagnosis': 'WNT activated medulloblastoma'}
        ]
    }

    result = validator.validate_diagnosis(who_classification, stage1_findings)
    print(f"\nResult: Valid={result['validation']['is_valid']}, Confidence={result['confidence']:.2f}")
    print(f"Violations: {result['validation']['violations']}")
    print(f"Conflicts: {result['validation']['conflicts']}")

    # Test Case 2: APC + Medulloblastoma (should pass)
    print("\n" + "=" * 80)
    print("TEST CASE 2: APC + Medulloblastoma (SHOULD PASS)")
    print("=" * 80)

    who_classification2 = {
        'who_2021_diagnosis': 'Medulloblastoma, WNT-activated',
        'confidence': 0.90
    }

    result2 = validator.validate_diagnosis(who_classification2, stage1_findings)
    print(f"\nResult: Valid={result2['validation']['is_valid']}, Confidence={result2['confidence']:.2f}")
    print(f"Violations: {result2['validation']['violations']}")
    print(f"Conflicts: {result2['validation']['conflicts']}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_validator()
