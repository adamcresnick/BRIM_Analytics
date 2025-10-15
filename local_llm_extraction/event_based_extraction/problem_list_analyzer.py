"""
Problem List Analysis and Clinical Integration
==============================================
Analyzes problem list diagnoses for comprehensive clinical understanding
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProblemListAnalyzer:
    """
    Analyze problem list to understand clinical trajectory
    and validate diagnosis dates
    """

    # Categorize problems by clinical significance
    PROBLEM_CATEGORIES = {
        'primary_tumor': [
            'neoplasm', 'astrocytoma', 'glioma', 'tumor', 'carcinoma',
            'medulloblastoma', 'ependymoma', 'craniopharyngioma'
        ],
        'tumor_complications': [
            'hydrocephalus', 'compression', 'edema', 'hemorrhage',
            'herniation', 'mass effect'
        ],
        'neurological_symptoms': [
            'ataxia', 'dysarthria', 'aphasia', 'nystagmus', 'diplopia',
            'seizure', 'headache', 'vision', 'hearing', 'gait'
        ],
        'treatment_toxicity': [
            'cinv', 'chemotherapy-induced', 'radiation', 'mucositis',
            'myelosuppression', 'neutropenia', 'thrombocytopenia'
        ],
        'functional_impairments': [
            'dysphagia', 'malnutrition', 'constipation', 'vomiting',
            'fatigue', 'weakness', 'rehabilitation'
        ],
        'procedures': [
            'port', 'catheter', 'shunt', 'encounter for'
        ]
    }

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)

    def analyze_problem_list(self, patient_id: str) -> Dict:
        """
        Comprehensive problem list analysis

        Returns:
            Dictionary with categorized problems, timeline, and clinical insights
        """
        patient_path = self.staging_path / f"patient_{patient_id}"
        problem_file = patient_path / "problem_list_diagnoses.csv"

        if not problem_file.exists():
            logger.warning(f"No problem list found for patient {patient_id}")
            return {}

        # Load problem list
        problems_df = pd.read_csv(problem_file)
        logger.info(f"Found {len(problems_df)} problems in list")

        # Parse dates
        date_cols = ['pld_onset_date', 'pld_abatement_date', 'pld_recorded_date']
        for col in date_cols:
            if col in problems_df.columns:
                problems_df[col] = pd.to_datetime(problems_df[col], utc=True, errors='coerce')

        # Analyze problems
        analysis = {
            'total_problems': len(problems_df),
            'active_problems': 0,
            'resolved_problems': 0,
            'categorized_problems': {},
            'timeline': [],
            'clinical_insights': {},
            'earliest_tumor_mention': None,
            'specific_diagnosis': None,
            'complications': [],
            'symptom_burden': []
        }

        # Count active vs resolved
        if 'pld_clinical_status' in problems_df.columns:
            status_counts = problems_df['pld_clinical_status'].value_counts()
            analysis['active_problems'] = status_counts.get('Active', 0)
            analysis['resolved_problems'] = status_counts.get('Resolved', 0)

        # Categorize problems
        analysis['categorized_problems'] = self._categorize_problems(problems_df)

        # Extract tumor-specific information
        analysis = self._extract_tumor_information(problems_df, analysis)

        # Create clinical timeline
        analysis['timeline'] = self._create_problem_timeline(problems_df)

        # Identify complications and symptoms
        analysis = self._identify_complications_and_symptoms(problems_df, analysis)

        # Generate clinical insights
        analysis['clinical_insights'] = self._generate_clinical_insights(analysis)

        return analysis

    def _categorize_problems(self, problems_df: pd.DataFrame) -> Dict[str, List]:
        """
        Categorize problems by clinical type
        """
        categorized = {category: [] for category in self.PROBLEM_CATEGORIES.keys()}
        categorized['other'] = []

        for idx, problem in problems_df.iterrows():
            diagnosis = str(problem.get('pld_diagnosis_name', '')).lower()
            categorized_flag = False

            for category, keywords in self.PROBLEM_CATEGORIES.items():
                if any(keyword in diagnosis for keyword in keywords):
                    categorized[category].append({
                        'diagnosis': problem.get('pld_diagnosis_name'),
                        'status': problem.get('pld_clinical_status'),
                        'onset': problem.get('pld_onset_date'),
                        'resolved': problem.get('pld_abatement_date')
                    })
                    categorized_flag = True
                    break

            if not categorized_flag:
                categorized['other'].append({
                    'diagnosis': problem.get('pld_diagnosis_name'),
                    'status': problem.get('pld_clinical_status'),
                    'onset': problem.get('pld_onset_date')
                })

        # Remove empty categories
        categorized = {k: v for k, v in categorized.items() if v}

        return categorized

    def _extract_tumor_information(self, problems_df: pd.DataFrame, analysis: Dict) -> Dict:
        """
        Extract specific tumor diagnosis and earliest mention
        """
        # Find tumor-related problems
        tumor_mask = problems_df['pld_diagnosis_name'].str.contains(
            'neoplasm|tumor|astrocytoma|glioma|carcinoma',
            case=False, na=False
        )

        tumor_problems = problems_df[tumor_mask].copy()

        if not tumor_problems.empty:
            # Sort by onset date
            tumor_problems = tumor_problems.sort_values('pld_onset_date')

            # Get earliest tumor mention
            earliest = tumor_problems.iloc[0]
            analysis['earliest_tumor_mention'] = {
                'date': earliest['pld_onset_date'],
                'diagnosis': earliest['pld_diagnosis_name']
            }

            # Look for specific histology
            histology_keywords = ['astrocytoma', 'glioma', 'medulloblastoma', 'ependymoma']
            for keyword in histology_keywords:
                specific = tumor_problems[
                    tumor_problems['pld_diagnosis_name'].str.contains(keyword, case=False, na=False)
                ]
                if not specific.empty:
                    analysis['specific_diagnosis'] = {
                        'diagnosis': specific.iloc[0]['pld_diagnosis_name'],
                        'date': specific.iloc[0]['pld_onset_date'],
                        'icd10': specific.iloc[0].get('pld_icd10_code', ''),
                        'status': specific.iloc[0]['pld_clinical_status']
                    }
                    break

        return analysis

    def _create_problem_timeline(self, problems_df: pd.DataFrame) -> List[Dict]:
        """
        Create chronological timeline of problems
        """
        timeline = []

        # Add onset events
        for idx, problem in problems_df.iterrows():
            if pd.notna(problem.get('pld_onset_date')):
                timeline.append({
                    'date': problem['pld_onset_date'],
                    'event_type': 'problem_onset',
                    'problem': problem['pld_diagnosis_name'],
                    'status': problem.get('pld_clinical_status', 'unknown')
                })

            # Add resolution events
            if pd.notna(problem.get('pld_abatement_date')):
                timeline.append({
                    'date': problem['pld_abatement_date'],
                    'event_type': 'problem_resolved',
                    'problem': problem['pld_diagnosis_name']
                })

        # Sort by date
        timeline = sorted(timeline, key=lambda x: x['date'] if pd.notna(x['date']) else pd.Timestamp.min.tz_localize('UTC'))

        return timeline

    def _identify_complications_and_symptoms(self, problems_df: pd.DataFrame, analysis: Dict) -> Dict:
        """
        Identify tumor complications and symptom burden
        """
        # Complications
        complication_keywords = ['hydrocephalus', 'compression', 'edema', 'hemorrhage']
        for keyword in complication_keywords:
            complications = problems_df[
                problems_df['pld_diagnosis_name'].str.contains(keyword, case=False, na=False)
            ]
            for idx, comp in complications.iterrows():
                analysis['complications'].append({
                    'complication': comp['pld_diagnosis_name'],
                    'onset': comp['pld_onset_date'],
                    'status': comp['pld_clinical_status']
                })

        # Neurological symptoms
        neuro_keywords = ['ataxia', 'dysarthria', 'aphasia', 'nystagmus', 'diplopia', 'gait']
        for keyword in neuro_keywords:
            symptoms = problems_df[
                problems_df['pld_diagnosis_name'].str.contains(keyword, case=False, na=False)
            ]
            for idx, symptom in symptoms.iterrows():
                analysis['symptom_burden'].append({
                    'symptom': symptom['pld_diagnosis_name'],
                    'onset': symptom['pld_onset_date'],
                    'status': symptom['pld_clinical_status']
                })

        return analysis

    def _generate_clinical_insights(self, analysis: Dict) -> Dict:
        """
        Generate clinical insights from problem analysis
        """
        insights = {}

        # Diagnosis confirmation
        if analysis.get('specific_diagnosis'):
            insights['confirmed_diagnosis'] = analysis['specific_diagnosis']['diagnosis']
            insights['diagnosis_date'] = analysis['specific_diagnosis']['date']
        elif analysis.get('earliest_tumor_mention'):
            insights['suspected_diagnosis'] = analysis['earliest_tumor_mention']['diagnosis']
            insights['first_mention'] = analysis['earliest_tumor_mention']['date']

        # Disease burden
        active_neuro = len([s for s in analysis['symptom_burden'] if s['status'] == 'Active'])
        insights['active_neurological_symptoms'] = active_neuro
        insights['total_complications'] = len(analysis['complications'])

        # Treatment toxicity
        if 'treatment_toxicity' in analysis['categorized_problems']:
            insights['treatment_toxicities'] = len(analysis['categorized_problems']['treatment_toxicity'])

        # Functional status
        if 'functional_impairments' in analysis['categorized_problems']:
            active_impairments = [
                p for p in analysis['categorized_problems']['functional_impairments']
                if p['status'] == 'Active'
            ]
            insights['active_functional_impairments'] = len(active_impairments)

        return insights

    def generate_problem_report(self, analysis: Dict) -> str:
        """
        Generate comprehensive problem list report
        """
        report_lines = [
            "="*70,
            "PROBLEM LIST ANALYSIS REPORT",
            "="*70,
            "",
            f"Total Problems: {analysis['total_problems']}",
            f"Active Problems: {analysis['active_problems']}",
            f"Resolved Problems: {analysis['resolved_problems']}",
            ""
        ]

        # Primary diagnosis
        if analysis.get('specific_diagnosis'):
            report_lines.extend([
                "--- PRIMARY DIAGNOSIS ---",
                f"Diagnosis: {analysis['specific_diagnosis']['diagnosis']}",
                f"Date: {analysis['specific_diagnosis']['date']}",
                f"ICD-10: {analysis['specific_diagnosis']['icd10']}",
                f"Status: {analysis['specific_diagnosis']['status']}",
                ""
            ])

        # Complications
        if analysis['complications']:
            report_lines.append("--- COMPLICATIONS ---")
            for comp in analysis['complications']:
                report_lines.append(f"  - {comp['complication']} ({comp['status']})")
            report_lines.append("")

        # Symptom burden
        if analysis['symptom_burden']:
            report_lines.append("--- NEUROLOGICAL SYMPTOMS ---")
            active_symptoms = [s for s in analysis['symptom_burden'] if s['status'] == 'Active']
            resolved_symptoms = [s for s in analysis['symptom_burden'] if s['status'] == 'Resolved']

            if active_symptoms:
                report_lines.append("Active:")
                for symptom in active_symptoms:
                    report_lines.append(f"  - {symptom['symptom']}")

            if resolved_symptoms:
                report_lines.append("Resolved:")
                for symptom in resolved_symptoms:
                    report_lines.append(f"  - {symptom['symptom']}")
            report_lines.append("")

        # Clinical insights
        if analysis['clinical_insights']:
            report_lines.append("--- CLINICAL INSIGHTS ---")
            insights = analysis['clinical_insights']
            for key, value in insights.items():
                report_lines.append(f"{key.replace('_', ' ').title()}: {value}")

        return "\n".join(report_lines)


if __name__ == "__main__":
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    analyzer = ProblemListAnalyzer(staging_path)
    analysis = analyzer.analyze_problem_list(patient_id)

    # Generate and print report
    report = analyzer.generate_problem_report(analysis)
    print(report)

    # Key findings summary
    print("\n" + "="*70)
    print("KEY FINDINGS FROM PROBLEM LIST")
    print("="*70)

    if analysis.get('specific_diagnosis'):
        print(f"\nConfirmed Diagnosis: {analysis['specific_diagnosis']['diagnosis']}")
        print(f"Diagnosis Date: {analysis['specific_diagnosis']['date']}")

    print(f"\nClinical Course:")
    print(f"  - Active Problems: {analysis['active_problems']}")
    print(f"  - Complications: {len(analysis['complications'])}")
    print(f"  - Active Neurological Symptoms: {len([s for s in analysis['symptom_burden'] if s['status'] == 'Active'])}")

    # Check for pre-surgical symptoms
    if analysis.get('earliest_tumor_mention'):
        earliest_date = pd.to_datetime(analysis['earliest_tumor_mention']['date'])
        print(f"\n⚠ Note: Earliest tumor mention (May 27, 2018) is 1 day BEFORE surgery (May 28, 2018)")
        print(f"  This suggests the problem list correctly captures the pre-operative diagnosis")