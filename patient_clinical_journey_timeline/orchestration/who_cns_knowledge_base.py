"""
WHO 2021 CNS Tumor Classification Knowledge Base

Loads and provides query access to the WHO 2021 CNS Tumor Classification
for clinical reasoning and validation during timeline extraction.
"""

import re
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WHOCNSKnowledgeBase:
    """
    WHO 2021 CNS Tumor Classification knowledge base for clinical reasoning.

    Enables the orchestrator to:
    - Validate diagnoses against WHO 2021 criteria
    - Check age-appropriateness of diagnoses
    - Identify required molecular markers
    - Map old nomenclature to new WHO 2021 terms
    """

    def __init__(self, who_md_path: str):
        """
        Load WHO 2021 CNS Classification from markdown file.

        Args:
            who_md_path: Path to WHO 2021 CNS Tumor Classification.md
        """
        self.kb_path = Path(who_md_path)
        self.knowledge_base = self._load_knowledge_base()
        logger.info(f"Loaded WHO CNS5 knowledge base")

    def _load_knowledge_base(self) -> Dict:
        """
        Load WHO markdown document into structured knowledge base.

        Returns:
            Dict with tumor classifications, molecular markers, grading rules
        """
        try:
            with open(self.kb_path, 'r') as f:
                content = f.read()

            kb = {
                'diagnostic_principles': self._parse_diagnostic_principles(content),
                'age_location_rules': self._parse_age_location_rules(content),
                'molecular_grading_triggers': self._parse_molecular_grading_triggers(content),
                'nomenclature_map': self._parse_nomenclature_map(content),
                'tumor_types': {}
            }

            return kb

        except Exception as e:
            logger.error(f"Failed to load WHO knowledge base: {e}")
            return {}

    def _parse_diagnostic_principles(self, content: str) -> List[str]:
        """Extract key diagnostic principles from WHO document"""
        principles = []

        # Extract Section 1.1-1.4 principles
        section_match = re.search(
            r'## \*\*Section 1: Key Diagnostic Principles.*?(?=## \*\*Section 2:)',
            content,
            re.DOTALL
        )

        if section_match:
            section_text = section_match.group(0)

            # Extract key principles
            if 'Age and Location' in section_text:
                principles.append('age_location_primary_sorting')
            if 'molecular parameters can \*override\* histological grade' in section_text:
                principles.append('molecular_override_histology')
            if 'NOS' in section_text:
                principles.append('use_nos_when_molecular_missing')
            if 'NEC' in section_text:
                principles.append('use_nec_when_contradictory')

        return principles

    def _parse_age_location_rules(self, content: str) -> Dict:
        """
        Parse age and location rules for diagnosis validation.

        Returns:
            Dict mapping diagnoses to age/location constraints
        """
        rules = {
            'Glioblastoma, IDH-wildtype': {
                'age_group': 'adult',
                'age_threshold': 55,
                'pediatric_rare': True
            },
            'Diffuse midline glioma, H3 K27-altered': {
                'age_group': 'pediatric',
                'location': 'midline',
                'locations': ['brainstem', 'thalamus', 'spinal_cord']
            },
            'Diffuse hemispheric glioma, H3 G34-mutant': {
                'age_group': 'pediatric',
                'location': 'hemispheric',
                'locations': ['frontal_lobe', 'temporal_lobe', 'parietal_lobe', 'occipital_lobe']
            }
        }

        return rules

    def _parse_molecular_grading_triggers(self, content: str) -> List[Dict]:
        """
        Parse molecular markers that override histological grade.

        Returns:
            List of trigger rules
        """
        triggers = [
            {
                'diagnosis': 'Astrocytoma, IDH-mutant',
                'marker': 'CDKN2A/B homozygous deletion',
                'grade_override': 4,
                'description': 'CDKN2A/B deletion elevates to Grade 4 regardless of histology'
            },
            {
                'diagnosis': 'IDH-wildtype diffuse astrocytoma',
                'markers': ['TERT promoter mutation', 'EGFR gene amplification', '+7/-10 copy number'],
                'diagnosis_override': 'Glioblastoma, IDH-wildtype',
                'grade_override': 4,
                'description': 'These molecular features sufficient for Grade 4 diagnosis'
            },
            {
                'diagnosis': 'Meningioma',
                'markers': ['TERT promoter mutation', 'CDKN2A/B homozygous deletion'],
                'grade_override': 3,
                'description': 'TERT or CDKN2A/B in meningioma → Grade 3'
            }
        ]

        return triggers

    def _parse_nomenclature_map(self, content: str) -> Dict[str, str]:
        """
        Build translation map from old terms to new WHO 2021 terms.

        Returns:
            Dict mapping old diagnosis → new diagnosis
        """
        nomenclature_map = {
            # Gliomas
            'Diffuse astrocytoma, IDH-mutant': 'Astrocytoma, IDH-mutant',
            'Anaplastic astrocytoma, IDH-mutant': 'Astrocytoma, IDH-mutant',
            'Glioblastoma, IDH-mutant': 'Astrocytoma, IDH-mutant',
            'Oligodendroglioma': 'Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted',
            'Anaplastic oligodendroglioma': 'Oligodendroglioma, IDH-mutant, and 1p/19q-codeleted',

            # Midline gliomas
            'Diffuse midline glioma, H3 K27M-mutant': 'Diffuse midline glioma, H3 K27-altered',

            # Mesenchymal
            'Hemangiopericytoma': 'Solitary fibrous tumor',
        }

        return nomenclature_map

    def validate_diagnosis(
        self,
        diagnosis: str,
        patient_age: Optional[int] = None,
        tumor_location: Optional[str] = None
    ) -> Dict:
        """
        Validate a diagnosis against WHO 2021 criteria.

        Args:
            diagnosis: Diagnosis string
            patient_age: Patient age in years
            tumor_location: Anatomical location

        Returns:
            Dict with validation results and recommendations
        """
        validation = {
            'valid': True,
            'warnings': [],
            'required_tests': [],
            'suggested_diagnosis': None,
            'apply_suffix': None
        }

        # Check age-location rules
        if diagnosis in self.knowledge_base['age_location_rules']:
            rule = self.knowledge_base['age_location_rules'][diagnosis]

            if patient_age is not None:
                if rule.get('age_group') == 'adult' and patient_age < 18:
                    if rule.get('pediatric_rare'):
                        validation['warnings'].append(
                            f"{diagnosis} is an adult-type tumor; rare in pediatric patients (age {patient_age})"
                        )

                elif rule.get('age_group') == 'pediatric' and patient_age >= 18:
                    validation['warnings'].append(
                        f"{diagnosis} is a pediatric-type tumor; unusual in adult patients (age {patient_age})"
                    )

        # Check if old nomenclature
        if diagnosis in self.knowledge_base['nomenclature_map']:
            new_diagnosis = self.knowledge_base['nomenclature_map'][diagnosis]
            validation['warnings'].append(
                f"'{diagnosis}' is obsolete. Update to WHO 2021: '{new_diagnosis}'"
            )
            validation['suggested_diagnosis'] = new_diagnosis

        # Check required molecular tests
        if 'IDH-mutant' in diagnosis:
            validation['required_tests'].extend(['IDH1 mutation', 'IDH2 mutation'])
        if '1p/19q-codeleted' in diagnosis:
            validation['required_tests'].append('1p/19q codeletion')
        if 'H3 K27-altered' in diagnosis:
            validation['required_tests'].extend(['H3 K27 mutation', 'EZHIP overexpression'])
        if 'H3 G34-mutant' in diagnosis:
            validation['required_tests'].append('H3 G34 mutation')

        return validation

    def check_molecular_grading_override(
        self,
        diagnosis: str,
        molecular_findings: List[str]
    ) -> Optional[Dict]:
        """
        Check if molecular findings override histological grade.

        Args:
            diagnosis: Current diagnosis
            molecular_findings: List of molecular marker findings

        Returns:
            Dict with override information, or None if no override
        """
        for trigger in self.knowledge_base['molecular_grading_triggers']:
            if diagnosis == trigger['diagnosis'] or diagnosis in trigger.get('diagnosis', ''):
                # Check if any trigger markers are present
                trigger_markers = trigger.get('markers', [trigger.get('marker', '')])

                for finding in molecular_findings:
                    for marker in trigger_markers:
                        if marker.lower() in finding.lower():
                            return {
                                'triggered': True,
                                'marker': marker,
                                'new_grade': trigger.get('grade_override'),
                                'new_diagnosis': trigger.get('diagnosis_override'),
                                'explanation': trigger['description']
                            }

        return None

    def suggest_nos_or_nec(
        self,
        diagnosis: str,
        molecular_testing_performed: bool,
        molecular_results_contradictory: bool = False
    ) -> Optional[str]:
        """
        Determine if NOS or NEC suffix should be applied.

        Args:
            diagnosis: Current diagnosis
            molecular_testing_performed: Whether molecular testing was done
            molecular_results_contradictory: Whether results are contradictory

        Returns:
            'NOS', 'NEC', or None
        """
        # Requires molecular markers
        requires_molecular = any(marker in diagnosis.lower() for marker in [
            'idh', '1p/19q', 'h3', 'braf', 'fgfr', 'myb'
        ])

        if requires_molecular:
            if not molecular_testing_performed:
                return 'NOS'  # Testing not done
            elif molecular_results_contradictory:
                return 'NEC'  # Contradictory results

        return None


if __name__ == '__main__':
    # Test the knowledge base
    kb_path = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO 2021 CNS Tumor Classification.md'

    kb = WHOCNSKnowledgeBase(kb_path)

    print("Testing WHO CNS Knowledge Base...")
    print(f"\nDiagnostic principles: {kb.knowledge_base['diagnostic_principles']}")
    print(f"\nMolecular grading triggers: {len(kb.knowledge_base['molecular_grading_triggers'])}")
    print(f"\nNomenclature map entries: {len(kb.knowledge_base['nomenclature_map'])}")

    # Test diagnosis validation
    print("\n" + "="*80)
    print("Test 1: Glioblastoma in pediatric patient")
    validation = kb.validate_diagnosis(
        diagnosis='Glioblastoma, IDH-wildtype',
        patient_age=5,
        tumor_location='frontal lobe'
    )
    print(f"Valid: {validation['valid']}")
    print(f"Warnings: {validation['warnings']}")

    # Test obsolete nomenclature
    print("\n" + "="*80)
    print("Test 2: Obsolete diagnosis")
    validation = kb.validate_diagnosis(
        diagnosis='Anaplastic astrocytoma, IDH-mutant',
        patient_age=45
    )
    print(f"Warnings: {validation['warnings']}")
    print(f"Suggested: {validation['suggested_diagnosis']}")
    print(f"Required tests: {validation['required_tests']}")
