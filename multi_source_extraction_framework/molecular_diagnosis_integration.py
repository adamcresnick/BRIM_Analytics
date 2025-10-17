"""
Molecular Testing and Surgical Specimen Integration
=====================================================
Links molecular tests to surgical specimens for comprehensive diagnosis
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import json

from enhanced_diagnosis_extraction import BrainTumorDiagnosisExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MolecularDiagnosisIntegration:
    """
    Integrate molecular testing data with surgical diagnosis
    Links specimens collected at surgery to molecular test results
    """

    # Key molecular markers for brain tumors
    BRAIN_TUMOR_MARKERS = {
        'glioma': [
            'IDH1', 'IDH2', 'TP53', 'ATRX', 'TERT', '1p/19q',
            'MGMT', 'EGFR', 'CDKN2A', 'CDKN2B', 'PTEN'
        ],
        'medulloblastoma': [
            'WNT', 'SHH', 'Group3', 'Group4', 'MYC', 'MYCN',
            'TP53', 'PTCH1', 'SUFU', 'SMO'
        ],
        'ependymoma': [
            'RELA', 'YAP1', 'PFA', 'PFB', 'C11orf95'
        ],
        'low_grade_glioma': [
            'BRAF V600E', 'BRAF fusion', 'KIAA1549',
            'FGFR1', 'MYB', 'MYBL1', 'NF1'
        ],
        'h3k27m_dmg': [
            'H3F3A', 'HIST1H3B', 'H3K27M', 'ACVR1'
        ]
    }

    # Standard assay types
    ASSAY_PRIORITIES = {
        'WGS': 1,  # Whole Genome Sequencing
        'WES': 2,  # Whole Exome Sequencing
        'RNA-seq': 3,
        'Panel': 4,
        'FISH': 5,
        'IHC': 6,
        'PCR': 7,
        'Methylation': 8
    }

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)
        self.diagnosis_extractor = BrainTumorDiagnosisExtractor()

    def extract_molecular_diagnosis(self, patient_id: str) -> Dict:
        """
        Extract comprehensive molecular diagnosis information

        Returns:
            Dictionary with surgical diagnosis, molecular tests, and integrated timeline
        """
        patient_path = self.staging_path / f"patient_{patient_id}"

        # Get surgical diagnosis first
        surgical_diagnosis = self.diagnosis_extractor.extract_diagnosis_info(patient_id, self.staging_path)

        # Extract molecular testing data
        molecular_data = self._extract_molecular_tests(patient_path)

        # Link molecular tests to surgeries
        linked_tests = self._link_tests_to_surgeries(
            molecular_data,
            surgical_diagnosis.get('initial_surgery_date')
        )

        # Identify diagnostic molecular tests
        diagnostic_tests = self._identify_diagnostic_tests(linked_tests)

        # Extract molecular markers
        molecular_markers = self._extract_molecular_markers(diagnostic_tests)

        # Create integrated diagnosis
        integrated_diagnosis = self._create_integrated_diagnosis(
            surgical_diagnosis,
            diagnostic_tests,
            molecular_markers
        )

        return integrated_diagnosis

    def _extract_molecular_tests(self, patient_path: Path) -> pd.DataFrame:
        """
        Extract molecular test data from metadata file
        """
        molecular_file = patient_path / "molecular_tests_metadata.csv"

        if not molecular_file.exists():
            logger.warning(f"No molecular tests metadata found")
            return pd.DataFrame()

        molecular_df = pd.read_csv(molecular_file)

        # Parse dates
        date_cols = ['mt_test_date', 'mt_specimen_collection_date', 'mt_procedure_date']
        for col in date_cols:
            if col in molecular_df.columns:
                molecular_df[col] = pd.to_datetime(molecular_df[col], utc=True, errors='coerce')

        logger.info(f"Found {len(molecular_df)} molecular tests")

        return molecular_df

    def _link_tests_to_surgeries(self, molecular_df: pd.DataFrame,
                                 surgery_date: Optional[pd.Timestamp]) -> pd.DataFrame:
        """
        Link molecular tests to surgical procedures based on specimen collection

        Key linkages:
        - Tests performed on surgical specimens (same day as surgery)
        - Tests on specimens collected within days of surgery
        - Follow-up tests on banked specimens
        """
        if molecular_df.empty:
            return molecular_df

        molecular_df['linked_to_surgery'] = False
        molecular_df['days_from_surgery'] = np.nan
        molecular_df['specimen_source'] = 'unknown'

        if surgery_date and pd.notna(surgery_date):
            # Check specimen collection dates
            if 'mt_specimen_collection_date' in molecular_df.columns:
                days_diff = (molecular_df['mt_specimen_collection_date'] - surgery_date).dt.days

                # Same day collection = surgical specimen
                surgical_specimen_mask = days_diff.abs() <= 1  # Within 1 day
                molecular_df.loc[surgical_specimen_mask, 'linked_to_surgery'] = True
                molecular_df.loc[surgical_specimen_mask, 'specimen_source'] = 'surgical'
                molecular_df.loc[surgical_specimen_mask, 'days_from_surgery'] = days_diff[surgical_specimen_mask]

            # Check procedure dates as fallback
            elif 'mt_procedure_date' in molecular_df.columns:
                days_diff = (molecular_df['mt_procedure_date'] - surgery_date).dt.days
                surgical_specimen_mask = days_diff.abs() <= 1
                molecular_df.loc[surgical_specimen_mask, 'linked_to_surgery'] = True
                molecular_df.loc[surgical_specimen_mask, 'specimen_source'] = 'surgical'
                molecular_df.loc[surgical_specimen_mask, 'days_from_surgery'] = days_diff[surgical_specimen_mask]

        # Identify recurrence specimens (later surgeries)
        if 'mt_procedure_name' in molecular_df.columns:
            recurrence_mask = molecular_df['mt_procedure_name'].str.contains(
                'recurrence|progressive|second|revision',
                case=False, na=False
            )
            molecular_df.loc[recurrence_mask, 'specimen_source'] = 'recurrence'

        linked_count = molecular_df['linked_to_surgery'].sum()
        logger.info(f"  Linked {linked_count} tests to surgical specimens")

        return molecular_df

    def _identify_diagnostic_tests(self, molecular_df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify molecular tests used for diagnosis

        Priority:
        1. Tests on initial surgical specimens
        2. Comprehensive panels (WGS/WES)
        3. Tumor-specific panels
        """
        if molecular_df.empty:
            return molecular_df

        molecular_df['is_diagnostic'] = False
        molecular_df['diagnostic_priority'] = 999

        # Mark surgical specimen tests as diagnostic
        surgical_mask = molecular_df['specimen_source'] == 'surgical'
        molecular_df.loc[surgical_mask, 'is_diagnostic'] = True

        # Prioritize by assay type
        if 'mt_assay_type' in molecular_df.columns:
            for assay, priority in self.ASSAY_PRIORITIES.items():
                assay_mask = molecular_df['mt_assay_type'].str.contains(assay, case=False, na=False)
                molecular_df.loc[assay_mask, 'diagnostic_priority'] = priority

        # Prioritize comprehensive panels
        if 'mt_lab_test_name' in molecular_df.columns:
            comprehensive_mask = molecular_df['mt_lab_test_name'].str.contains(
                'comprehensive|whole genome|whole exome|tumor panel',
                case=False, na=False
            )
            molecular_df.loc[comprehensive_mask & surgical_mask, 'diagnostic_priority'] -= 1

        # Sort by priority
        molecular_df = molecular_df.sort_values(['diagnostic_priority', 'mt_test_date'])

        diagnostic_count = molecular_df['is_diagnostic'].sum()
        logger.info(f"  Identified {diagnostic_count} diagnostic molecular tests")

        return molecular_df

    def _extract_molecular_markers(self, molecular_df: pd.DataFrame) -> Dict[str, List]:
        """
        Extract molecular markers and alterations from test results

        Returns:
            Dictionary of detected molecular markers by category
        """
        markers = {
            'detected_markers': [],
            'tumor_classification': None,
            'who_grade': None,
            'molecular_subtype': None
        }

        if molecular_df.empty:
            return markers

        # Look for markers in test components
        if 'mtr_components_list' in molecular_df.columns:
            diagnostic_tests = molecular_df[molecular_df['is_diagnostic'] == True]

            for idx, test in diagnostic_tests.iterrows():
                components = str(test.get('mtr_components_list', ''))

                # Check for known brain tumor markers
                for tumor_type, marker_list in self.BRAIN_TUMOR_MARKERS.items():
                    for marker in marker_list:
                        if marker.lower() in components.lower():
                            markers['detected_markers'].append({
                                'marker': marker,
                                'tumor_type': tumor_type,
                                'test_date': test.get('mt_test_date'),
                                'assay_type': test.get('mt_assay_type')
                            })

        # Deduplicate markers
        unique_markers = {}
        for marker_info in markers['detected_markers']:
            marker_name = marker_info['marker']
            if marker_name not in unique_markers:
                unique_markers[marker_name] = marker_info

        markers['detected_markers'] = list(unique_markers.values())
        markers['total_markers'] = len(unique_markers)

        logger.info(f"  Extracted {markers['total_markers']} molecular markers")

        return markers

    def _create_integrated_diagnosis(self, surgical_diagnosis: Dict,
                                    diagnostic_tests: pd.DataFrame,
                                    molecular_markers: Dict) -> Dict:
        """
        Create integrated diagnosis combining surgical and molecular data
        """
        integrated = {
            'patient_id': surgical_diagnosis.get('patient_id'),
            'diagnosis_date': surgical_diagnosis.get('diagnosis_date'),
            'diagnosis_type': surgical_diagnosis.get('diagnosis_type'),
            'age_at_diagnosis': surgical_diagnosis.get('age_at_diagnosis'),
            'initial_surgery': {
                'date': surgical_diagnosis.get('initial_surgery_date'),
                'type': surgical_diagnosis.get('initial_surgery_type')
            },
            'molecular_testing': {
                'tests_performed': len(diagnostic_tests) if not diagnostic_tests.empty else 0,
                'diagnostic_tests': 0,
                'test_dates': [],
                'test_names': [],
                'test_details': []
            },
            'molecular_markers': molecular_markers,
            'integrated_diagnosis': None
        }

        # Add molecular test details
        if not diagnostic_tests.empty:
            diagnostic_only = diagnostic_tests[diagnostic_tests['is_diagnostic'] == True]
            integrated['molecular_testing']['diagnostic_tests'] = len(diagnostic_only)

            # Get unique test dates and names
            if 'mt_test_date' in diagnostic_tests.columns:
                test_dates = diagnostic_tests['mt_test_date'].dropna().unique()
                integrated['molecular_testing']['test_dates'] = [
                    pd.to_datetime(d).isoformat() for d in test_dates
                ]

            # Get test names
            if 'mt_lab_test_name' in diagnostic_tests.columns:
                test_names = diagnostic_tests['mt_lab_test_name'].dropna().unique()
                integrated['molecular_testing']['test_names'] = list(test_names)

            # Create detailed test information including linkage to surgery
            for idx, test in diagnostic_tests.iterrows():
                test_detail = {
                    'test_name': test.get('mt_lab_test_name', 'Unknown'),
                    'test_date': pd.to_datetime(test.get('mt_test_date')).isoformat() if pd.notna(test.get('mt_test_date')) else None,
                    'linked_to_surgery': test.get('linked_to_surgery', False),
                    'specimen_source': test.get('specimen_source', 'unknown'),
                    'days_from_surgery': int(test.get('days_from_surgery')) if pd.notna(test.get('days_from_surgery')) else None,
                    'is_diagnostic': test.get('is_diagnostic', False)
                }
                integrated['molecular_testing']['test_details'].append(test_detail)

        # Create integrated diagnosis string
        if integrated['initial_surgery']['date']:
            diagnosis_components = []

            # Add surgical component
            surgery_type = integrated['initial_surgery']['type']
            diagnosis_components.append(f"Surgical {surgery_type}")

            # Add molecular component
            if integrated['molecular_testing']['diagnostic_tests'] > 0:
                diagnosis_components.append(f"{integrated['molecular_testing']['diagnostic_tests']} molecular tests")

            # Add marker information
            if molecular_markers['total_markers'] > 0:
                diagnosis_components.append(f"{molecular_markers['total_markers']} markers detected")

            integrated['integrated_diagnosis'] = " with ".join(diagnosis_components)

        return integrated

    def generate_diagnosis_report(self, integrated_diagnosis: Dict) -> str:
        """
        Generate comprehensive diagnosis report
        """
        report_lines = [
            "="*70,
            "INTEGRATED BRAIN TUMOR DIAGNOSIS REPORT",
            "="*70,
            "",
            f"Patient ID: {integrated_diagnosis.get('patient_id', 'Unknown')}",
            f"Diagnosis Date: {integrated_diagnosis.get('diagnosis_date', 'Unknown')}",
            f"Age at Diagnosis: {integrated_diagnosis.get('age_at_diagnosis', 'Unknown')} years",
            "",
            "--- SURGICAL DIAGNOSIS ---"
        ]

        surgery = integrated_diagnosis['initial_surgery']
        if surgery['date']:
            report_lines.append(f"Initial Surgery: {surgery['date']}")
            report_lines.append(f"Surgery Type: {surgery['type']}")
        else:
            report_lines.append("No surgical diagnosis found")

        report_lines.extend([
            "",
            "--- MOLECULAR TESTING ---"
        ])

        mol_testing = integrated_diagnosis['molecular_testing']
        report_lines.append(f"Total Tests: {mol_testing['tests_performed']}")
        report_lines.append(f"Diagnostic Tests: {mol_testing['diagnostic_tests']}")

        if mol_testing.get('test_names'):
            report_lines.append(f"Test Names: {', '.join(mol_testing['test_names'])}")

        if mol_testing.get('test_dates'):
            report_lines.append(f"Test Dates: {', '.join([str(d)[:10] for d in mol_testing['test_dates']])}")

        # Show detailed test linkage to surgery
        if mol_testing.get('test_details'):
            report_lines.append("\nTest Details:")
            for test in mol_testing['test_details']:
                report_lines.append(f"  - {test['test_name']} ({test['test_date'][:10] if test['test_date'] else 'No date'})")
                if test['linked_to_surgery']:
                    report_lines.append(f"    → Linked to surgery (Day {test['days_from_surgery']})")
                report_lines.append(f"    → Specimen: {test['specimen_source']}")

        report_lines.extend([
            "",
            "--- MOLECULAR MARKERS ---"
        ])

        markers = integrated_diagnosis['molecular_markers']
        if markers['detected_markers']:
            report_lines.append(f"Markers Detected: {markers['total_markers']}")
            for marker_info in markers['detected_markers'][:10]:  # Show first 10
                report_lines.append(f"  - {marker_info['marker']} ({marker_info['tumor_type']})")
        else:
            report_lines.append("No molecular markers extracted")

        report_lines.extend([
            "",
            "--- INTEGRATED DIAGNOSIS ---",
            integrated_diagnosis.get('integrated_diagnosis', 'Pending molecular results'),
            ""
        ])

        return "\n".join(report_lines)


def analyze_patient_molecular_diagnosis(patient_id: str, staging_path: Path):
    """
    Complete molecular diagnosis analysis for a patient
    """
    integrator = MolecularDiagnosisIntegration(staging_path)

    # Extract integrated diagnosis
    integrated_diagnosis = integrator.extract_molecular_diagnosis(patient_id)

    # Generate report
    report = integrator.generate_diagnosis_report(integrated_diagnosis)

    print(report)

    # Save results
    output_path = staging_path.parent.parent / "multi_source_extraction_framework" / "outputs"
    output_path.mkdir(exist_ok=True)

    # Save JSON
    output_file = output_path / f"molecular_diagnosis_{patient_id}.json"
    with open(output_file, 'w') as f:
        # Convert any pandas timestamps to strings
        def convert_timestamps(obj):
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_timestamps(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_timestamps(item) for item in obj]
            return obj

        json.dump(convert_timestamps(integrated_diagnosis), f, indent=2)

    logger.info(f"Molecular diagnosis saved to {output_file}")

    return integrated_diagnosis


if __name__ == "__main__":
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    integrated_diagnosis = analyze_patient_molecular_diagnosis(patient_id, staging_path)

    # Summary statistics
    print("\n" + "="*70)
    print("MOLECULAR TESTING SUMMARY")
    print("="*70)

    mol = integrated_diagnosis['molecular_testing']
    print(f"\nMolecular Tests at Diagnosis: {mol['diagnostic_tests']}")
    print(f"Test Names: {', '.join(mol.get('test_names', [])) if mol.get('test_names') else 'None'}")

    if integrated_diagnosis['molecular_markers']['detected_markers']:
        print(f"\nKey Finding: {mol['diagnostic_tests']} molecular tests performed on surgical specimen")
        print(f"Same-day testing: Specimen collected on {integrated_diagnosis['initial_surgery']['date']}")

    print("\nClinical Significance:")
    print("- Molecular testing linked directly to surgical specimen")
    print("- Enables precise tumor classification and targeted therapy selection")
    print("- Critical for risk stratification and prognosis")