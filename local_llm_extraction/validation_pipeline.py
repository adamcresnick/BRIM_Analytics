#!/usr/bin/env python3
"""
Validation pipeline to check extraction quality and identify discrepancies
Implements comprehensive quality control for RADIANT PCA extractions
"""

import pandas as pd
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
import sys
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('validation_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExtractionValidator:
    """
    Comprehensive validation for extraction results
    """

    def __init__(self, extraction_dir: Path):
        """
        Initialize validator

        Args:
            extraction_dir: Directory containing extraction results
        """
        self.extraction_dir = Path(extraction_dir)
        self.validation_rules = self.load_validation_rules()
        self.issues = []
        self.warnings = []
        self.stats = defaultdict(int)

    def load_validation_rules(self) -> Dict:
        """Define validation rules for each variable"""
        return {
            'extent_of_tumor_resection': {
                'required_sources': ['post_op_imaging'],  # Must have post-op validation
                'priority_source': 'post_op_imaging',
                'valid_values': [
                    'Gross total resection',
                    'Near-total resection',
                    'Near-total resection (>95% or "near total debulking")',
                    'Subtotal resection',
                    'Partial resection',
                    'Biopsy only',
                    'Unavailable'
                ],
                'confidence_threshold': 0.7,
                'critical': True
            },
            'tumor_location': {
                'required_sources': ['operative_note', 'imaging'],
                'allow_multiple': True,
                'valid_regions': [
                    'frontal', 'temporal', 'parietal', 'occipital',
                    'cerebellum', 'brainstem', 'thalamus', 'ventricle',
                    'corpus callosum', 'pineal'
                ],
                'confidence_threshold': 0.65
            },
            'histopathology': {
                'required_sources': ['pathology_report'],
                'cross_validate': ['operative_note'],
                'who_grade_required': True,
                'confidence_threshold': 0.75,
                'critical': True
            },
            'who_grade': {
                'valid_values': ['I', 'II', 'III', 'IV', '1', '2', '3', '4'],
                'required_sources': ['pathology_report'],
                'confidence_threshold': 0.75
            },
            'metastasis_presence': {
                'valid_values': ['Yes', 'No', 'Unknown', 'Unavailable'],
                'confidence_threshold': 0.7
            }
        }

    def validate_patient(self, patient_file: Path) -> Dict:
        """
        Validate single patient extraction

        Args:
            patient_file: Path to patient JSON file

        Returns:
            Validation results dictionary
        """
        try:
            with open(patient_file) as f:
                patient_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {patient_file}: {e}")
            return {'error': str(e)}

        validation_results = {
            'patient_id': patient_data.get('patient_id'),
            'file': str(patient_file.name),
            'status': patient_data.get('status'),
            'issues': [],
            'warnings': [],
            'metrics': {}
        }

        # Skip if extraction failed
        if patient_data.get('status') == 'error':
            validation_results['skip_reason'] = 'extraction_error'
            return validation_results

        # Validate each event
        for event_idx, event in enumerate(patient_data.get('events', []), 1):
            event_issues = self._validate_event(event, event_idx)
            validation_results['issues'].extend(event_issues['issues'])
            validation_results['warnings'].extend(event_issues['warnings'])

        # Calculate metrics
        validation_results['metrics'] = self._calculate_patient_metrics(patient_data)

        # Determine overall validation status
        if validation_results['issues']:
            validation_results['validation_status'] = 'failed'
            self.stats['patients_failed'] += 1
        elif validation_results['warnings']:
            validation_results['validation_status'] = 'warning'
            self.stats['patients_warning'] += 1
        else:
            validation_results['validation_status'] = 'passed'
            self.stats['patients_passed'] += 1

        return validation_results

    def _validate_event(self, event: Dict, event_idx: int) -> Dict:
        """Validate single event extraction"""
        issues = []
        warnings = []

        event_date = event.get('event_date', 'unknown')
        extracted_vars = event.get('extracted_variables', {})

        for var_name, var_data in extracted_vars.items():
            if var_name not in self.validation_rules:
                continue

            rule = self.validation_rules[var_name]

            # Check required sources
            if 'required_sources' in rule:
                source = var_data.get('source', '')
                sources = var_data.get('sources', [source]) if source else []

                missing_required = []
                for req_source in rule['required_sources']:
                    if not any(req_source in str(s).lower() for s in sources):
                        missing_required.append(req_source)

                if missing_required and rule.get('critical'):
                    issues.append({
                        'event': f"Event {event_idx} ({event_date})",
                        'variable': var_name,
                        'type': 'missing_required_source',
                        'details': f"Missing required sources: {missing_required}"
                    })
                elif missing_required:
                    warnings.append({
                        'event': f"Event {event_idx} ({event_date})",
                        'variable': var_name,
                        'type': 'missing_source',
                        'details': f"Missing sources: {missing_required}"
                    })

            # Check valid values
            if 'valid_values' in rule:
                value = var_data.get('value')
                if value and value not in rule['valid_values']:
                    # Check for partial matches
                    partial_match = any(
                        valid in str(value) for valid in rule['valid_values']
                    )
                    if not partial_match:
                        issues.append({
                            'event': f"Event {event_idx} ({event_date})",
                            'variable': var_name,
                            'type': 'invalid_value',
                            'details': f"Invalid value: '{value}'"
                        })

            # Check confidence threshold
            confidence = var_data.get('confidence', 0)
            threshold = rule.get('confidence_threshold', 0.7)
            if confidence < threshold:
                if rule.get('critical'):
                    issues.append({
                        'event': f"Event {event_idx} ({event_date})",
                        'variable': var_name,
                        'type': 'low_confidence',
                        'details': f"Confidence {confidence:.2f} < {threshold}"
                    })
                else:
                    warnings.append({
                        'event': f"Event {event_idx} ({event_date})",
                        'variable': var_name,
                        'type': 'low_confidence',
                        'details': f"Confidence {confidence:.2f} < {threshold}"
                    })

            # Check for discrepancies
            if var_data.get('override_reason'):
                warnings.append({
                    'event': f"Event {event_idx} ({event_date})",
                    'variable': var_name,
                    'type': 'value_overridden',
                    'details': f"Original: {var_data.get('original_value')} → {var_data.get('value')}"
                })
                self.stats['overrides'] += 1

        # Check post-op validation for extent
        validation_info = event.get('validation', {})
        if 'extent_of_tumor_resection' in extracted_vars:
            if not validation_info.get('post_op_imaging_checked'):
                issues.append({
                    'event': f"Event {event_idx} ({event_date})",
                    'variable': 'extent_of_tumor_resection',
                    'type': 'missing_validation',
                    'details': 'Post-op imaging validation not performed'
                })

        return {'issues': issues, 'warnings': warnings}

    def _calculate_patient_metrics(self, patient_data: Dict) -> Dict:
        """Calculate quality metrics for patient"""
        metrics = {
            'total_events': len(patient_data.get('events', [])),
            'total_variables': 0,
            'available_variables': 0,
            'confidence_scores': [],
            'multi_source_vars': 0,
            'validated_extents': 0
        }

        for event in patient_data.get('events', []):
            for var_name, var_data in event.get('extracted_variables', {}).items():
                metrics['total_variables'] += 1

                if var_data.get('value') and var_data['value'] != 'Unavailable':
                    metrics['available_variables'] += 1

                confidence = var_data.get('confidence', 0)
                metrics['confidence_scores'].append(confidence)

                sources = var_data.get('sources', [])
                if len(sources) > 1:
                    metrics['multi_source_vars'] += 1

            if event.get('validation', {}).get('post_op_imaging_checked'):
                metrics['validated_extents'] += 1

        # Calculate summary statistics
        if metrics['confidence_scores']:
            metrics['avg_confidence'] = sum(metrics['confidence_scores']) / len(metrics['confidence_scores'])
            metrics['min_confidence'] = min(metrics['confidence_scores'])
        else:
            metrics['avg_confidence'] = 0
            metrics['min_confidence'] = 0

        if metrics['total_variables'] > 0:
            metrics['completeness'] = metrics['available_variables'] / metrics['total_variables']
        else:
            metrics['completeness'] = 0

        return metrics

    def run_validation(self) -> Dict:
        """
        Validate all patient extractions

        Returns:
            Summary dictionary
        """
        logger.info(f"Starting validation for {self.extraction_dir}")

        patient_files = list((self.extraction_dir / 'patient_extractions').glob('patient_*.json'))
        logger.info(f"Found {len(patient_files)} patient files to validate")

        results = []
        for patient_file in patient_files:
            logger.info(f"Validating {patient_file.name}")
            validation = self.validate_patient(patient_file)
            results.append(validation)

            # Collect overall issues
            self.issues.extend(validation.get('issues', []))
            self.warnings.extend(validation.get('warnings', []))

        # Generate summary
        summary = self.generate_validation_summary(results)

        # Save validation results
        self.save_validation_results(results, summary)

        return summary

    def generate_validation_summary(self, results: List[Dict]) -> Dict:
        """Generate validation summary statistics"""
        summary = {
            'validation_timestamp': datetime.now().isoformat(),
            'total_patients': len(results),
            'patients_passed': self.stats['patients_passed'],
            'patients_warning': self.stats['patients_warning'],
            'patients_failed': self.stats['patients_failed'],
            'total_issues': len(self.issues),
            'total_warnings': len(self.warnings),
            'total_overrides': self.stats['overrides'],
            'common_issues': self.analyze_common_issues(),
            'metrics_summary': self.calculate_overall_metrics(results)
        }

        return summary

    def analyze_common_issues(self) -> List[Dict]:
        """Identify most common validation issues"""
        issue_counts = defaultdict(int)

        for issue in self.issues + self.warnings:
            key = f"{issue['variable']}:{issue['type']}"
            issue_counts[key] += 1

        # Sort by frequency
        sorted_issues = sorted(
            issue_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return [
            {'issue': issue, 'count': count}
            for issue, count in sorted_issues
        ]

    def calculate_overall_metrics(self, results: List[Dict]) -> Dict:
        """Calculate overall quality metrics"""
        all_confidence = []
        all_completeness = []
        validated_extents = 0
        total_extents = 0

        for result in results:
            metrics = result.get('metrics', {})
            if metrics.get('confidence_scores'):
                all_confidence.extend(metrics['confidence_scores'])
            if 'completeness' in metrics:
                all_completeness.append(metrics['completeness'])
            validated_extents += metrics.get('validated_extents', 0)
            total_extents += metrics.get('total_events', 0)

        summary_metrics = {}

        if all_confidence:
            summary_metrics['overall_confidence'] = {
                'mean': sum(all_confidence) / len(all_confidence),
                'median': sorted(all_confidence)[len(all_confidence) // 2],
                'below_0.7': sum(1 for c in all_confidence if c < 0.7) / len(all_confidence)
            }

        if all_completeness:
            summary_metrics['overall_completeness'] = {
                'mean': sum(all_completeness) / len(all_completeness),
                'fully_complete': sum(1 for c in all_completeness if c == 1.0) / len(all_completeness)
            }

        if total_extents > 0:
            summary_metrics['post_op_validation_rate'] = validated_extents / total_extents

        return summary_metrics

    def save_validation_results(self, results: List[Dict], summary: Dict):
        """Save validation results and reports"""
        validation_dir = self.extraction_dir / 'validation_reports'
        validation_dir.mkdir(exist_ok=True)

        # Save detailed results
        results_file = validation_dir / 'validation_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved validation results to {results_file}")

        # Save summary
        summary_file = validation_dir / 'validation_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved validation summary to {summary_file}")

        # Save issues for review
        if self.issues:
            issues_file = validation_dir / 'validation_issues.json'
            with open(issues_file, 'w') as f:
                json.dump(self.issues, f, indent=2)
            logger.info(f"Saved {len(self.issues)} issues to {issues_file}")

        # Save warnings
        if self.warnings:
            warnings_file = validation_dir / 'validation_warnings.json'
            with open(warnings_file, 'w') as f:
                json.dump(self.warnings, f, indent=2)
            logger.info(f"Saved {len(self.warnings)} warnings to {warnings_file}")

        # Generate HTML report
        self.generate_html_report(summary, validation_dir)

    def generate_html_report(self, summary: Dict, output_dir: Path):
        """Generate human-readable HTML validation report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>RADIANT PCA Extraction Validation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .metric {{ margin: 10px 0; }}
        .pass {{ color: green; }}
        .warning {{ color: orange; }}
        .fail {{ color: red; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>RADIANT PCA Extraction Validation Report</h1>
    <p>Generated: {summary['validation_timestamp']}</p>

    <div class="summary">
        <h2>Summary</h2>
        <div class="metric">Total Patients: {summary['total_patients']}</div>
        <div class="metric pass">Passed: {summary['patients_passed']}</div>
        <div class="metric warning">Warnings: {summary['patients_warning']}</div>
        <div class="metric fail">Failed: {summary['patients_failed']}</div>
        <div class="metric">Total Issues: {summary['total_issues']}</div>
        <div class="metric">Total Warnings: {summary['total_warnings']}</div>
        <div class="metric">Value Overrides: {summary['total_overrides']}</div>
    </div>

    <h2>Quality Metrics</h2>
"""

        if 'metrics_summary' in summary:
            metrics = summary['metrics_summary']
            if 'overall_confidence' in metrics:
                conf = metrics['overall_confidence']
                html_content += f"""
    <div class="metric">
        Average Confidence: {conf['mean']:.3f}<br>
        Median Confidence: {conf['median']:.3f}<br>
        Below 0.7 Threshold: {conf['below_0.7']:.1%}
    </div>
"""

            if 'overall_completeness' in metrics:
                comp = metrics['overall_completeness']
                html_content += f"""
    <div class="metric">
        Average Completeness: {comp['mean']:.1%}<br>
        Fully Complete: {comp['fully_complete']:.1%}
    </div>
"""

            if 'post_op_validation_rate' in metrics:
                html_content += f"""
    <div class="metric">
        Post-Op Validation Rate: {metrics['post_op_validation_rate']:.1%}
    </div>
"""

        # Add common issues table
        if summary.get('common_issues'):
            html_content += """
    <h2>Most Common Issues</h2>
    <table>
        <tr><th>Issue Type</th><th>Count</th></tr>
"""
            for issue_info in summary['common_issues']:
                html_content += f"""
        <tr><td>{issue_info['issue']}</td><td>{issue_info['count']}</td></tr>
"""
            html_content += """
    </table>
"""

        html_content += """
</body>
</html>
"""

        # Save HTML report
        html_file = output_dir / 'validation_report.html'
        with open(html_file, 'w') as f:
            f.write(html_content)
        logger.info(f"Generated HTML report: {html_file}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='RADIANT PCA Extraction Validation Pipeline'
    )
    parser.add_argument(
        'extraction_dir',
        help='Directory containing extraction results'
    )
    parser.add_argument(
        '--output-format',
        choices=['json', 'html', 'both'],
        default='both',
        help='Output format for validation report'
    )

    args = parser.parse_args()

    # Initialize validator
    validator = ExtractionValidator(args.extraction_dir)

    # Run validation
    summary = validator.run_validation()

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total patients: {summary['total_patients']}")
    print(f"Passed: {summary['patients_passed']}")
    print(f"Warnings: {summary['patients_warning']}")
    print(f"Failed: {summary['patients_failed']}")
    print(f"\nTotal issues: {summary['total_issues']}")
    print(f"Total warnings: {summary['total_warnings']}")
    print(f"Value overrides: {summary['total_overrides']}")

    if summary.get('common_issues'):
        print("\nMost common issues:")
        for issue_info in summary['common_issues'][:5]:
            print(f"  {issue_info['issue']}: {issue_info['count']} occurrences")

    print(f"\nValidation reports saved to {validator.extraction_dir / 'validation_reports'}")

    return 0


if __name__ == '__main__':
    sys.exit(main())