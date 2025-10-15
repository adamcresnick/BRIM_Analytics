"""
Automated Cohort Processing Pipeline
=====================================
Processes entire RADIANT PCA cohort without individual patient configurations
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging
import json
import yaml
from datetime import datetime
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback

from enhanced_clinical_prioritization import process_patient_enhanced

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CohortProcessor:
    """
    Automated cohort-wide processing without individual patient YAMLs
    """

    def __init__(self, staging_base_path: Path, output_base_path: Path, config_path: Optional[Path] = None):
        """
        Initialize cohort processor

        Args:
            staging_base_path: Base directory containing all patient staging directories
            output_base_path: Base directory for all outputs
            config_path: Optional path to cohort configuration (uses defaults if not provided)
        """
        self.staging_base = Path(staging_base_path)
        self.output_base = Path(output_base_path)

        # Load or create configuration
        if config_path and config_path.exists():
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = self._get_default_config()

        # Create output directories
        self.output_base.mkdir(exist_ok=True)
        (self.output_base / "patient_results").mkdir(exist_ok=True)
        (self.output_base / "cohort_summaries").mkdir(exist_ok=True)

    def _get_default_config(self) -> Dict:
        """Get default configuration for cohort processing"""
        return {
            'framework_version': '2.0',
            'imaging_prioritization': {
                'pre_surgery_days': 30,
                'post_surgery_days': 90,
                'chemo_change_window_days': 30,
                'radiation_planning_window_days': 14
            },
            'processing': {
                'batch_size': 10,
                'parallel': False,
                'max_workers': 4,
                'checkpoint_frequency': 5
            },
            'output_formats': ['csv', 'json'],
            'modules': {
                'surgery_classification': True,
                'chemotherapy_identification': True,
                'radiation_analysis': True,
                'imaging_prioritization': True,
                'survival_tracking': True
            }
        }

    def discover_patients(self) -> List[str]:
        """
        Automatically discover all patients in staging directory

        Returns:
            List of patient IDs found
        """
        patients = []

        # Find all directories starting with "patient_"
        for patient_dir in self.staging_base.glob("patient_*"):
            if patient_dir.is_dir():
                # Extract patient ID from directory name
                patient_id = patient_dir.name.replace("patient_", "")
                patients.append(patient_id)

        logger.info(f"Discovered {len(patients)} patients in {self.staging_base}")
        return sorted(patients)

    def process_single_patient(self, patient_id: str) -> Dict:
        """
        Process a single patient with full framework

        Args:
            patient_id: Patient identifier

        Returns:
            Processing results dictionary
        """
        logger.info(f"Processing patient: {patient_id}")

        patient_output_dir = self.output_base / "patient_results" / f"patient_{patient_id}"
        patient_output_dir.mkdir(exist_ok=True)

        try:
            # Run enhanced processing pipeline
            results = process_patient_enhanced(
                patient_id,
                self.staging_base,
                patient_output_dir
            )

            # Add processing metadata
            results['processing_timestamp'] = datetime.now().isoformat()
            results['processing_status'] = 'success'

            # Save patient summary
            summary_file = patient_output_dir / f"processing_summary_{patient_id}.json"
            with open(summary_file, 'w') as f:
                json.dump(results, f, indent=2)

            logger.info(f"Successfully processed patient {patient_id}")

        except Exception as e:
            logger.error(f"Error processing patient {patient_id}: {str(e)}")
            results = {
                'patient_id': patient_id,
                'processing_status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc(),
                'processing_timestamp': datetime.now().isoformat()
            }

        return results

    def process_cohort(self, patient_list: Optional[List[str]] = None,
                      parallel: bool = False) -> pd.DataFrame:
        """
        Process entire cohort or subset of patients

        Args:
            patient_list: Optional list of specific patients to process (None = all)
            parallel: Whether to use parallel processing

        Returns:
            DataFrame with cohort summary
        """
        # Get patient list
        if patient_list is None:
            patient_list = self.discover_patients()

        if not patient_list:
            logger.warning("No patients found to process")
            return pd.DataFrame()

        logger.info(f"Starting cohort processing for {len(patient_list)} patients")

        # Process patients
        all_results = []

        if parallel and len(patient_list) > 1:
            # Parallel processing
            max_workers = self.config['processing'].get('max_workers', 4)
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_patient = {
                    executor.submit(self.process_single_patient, patient_id): patient_id
                    for patient_id in patient_list
                }

                for future in as_completed(future_to_patient):
                    patient_id = future_to_patient[future]
                    try:
                        result = future.result()
                        all_results.append(result)
                    except Exception as e:
                        logger.error(f"Failed to process {patient_id}: {e}")
                        all_results.append({
                            'patient_id': patient_id,
                            'processing_status': 'failed',
                            'error': str(e)
                        })

        else:
            # Sequential processing with checkpoints
            checkpoint_freq = self.config['processing'].get('checkpoint_frequency', 5)

            for idx, patient_id in enumerate(patient_list, 1):
                result = self.process_single_patient(patient_id)
                all_results.append(result)

                # Checkpoint
                if idx % checkpoint_freq == 0:
                    self._save_checkpoint(all_results, idx, len(patient_list))

        # Create cohort summary
        cohort_summary = self._create_cohort_summary(all_results)

        # Save final results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = self.output_base / "cohort_summaries" / f"cohort_summary_{timestamp}.csv"
        cohort_summary.to_csv(summary_file, index=False)

        logger.info(f"Cohort processing complete. Summary saved to {summary_file}")

        return cohort_summary

    def _save_checkpoint(self, results: List[Dict], current: int, total: int):
        """Save processing checkpoint"""
        checkpoint_file = self.output_base / "cohort_summaries" / "checkpoint_latest.json"
        checkpoint_data = {
            'progress': f"{current}/{total}",
            'timestamp': datetime.now().isoformat(),
            'processed_patients': [r['patient_id'] for r in results],
            'results': results
        }
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        logger.info(f"Checkpoint saved: {current}/{total} patients processed")

    def _create_cohort_summary(self, results: List[Dict]) -> pd.DataFrame:
        """
        Create summary DataFrame from all patient results
        """
        summary_rows = []

        for result in results:
            row = {
                'patient_id': result.get('patient_id'),
                'processing_status': result.get('processing_status'),
                'processing_timestamp': result.get('processing_timestamp')
            }

            # Add imaging summary if available
            if 'imaging_priority_summary' in result and result['imaging_priority_summary']:
                img_summary = result['imaging_priority_summary']
                row.update({
                    'total_imaging': img_summary.get('total_imaging', 0),
                    'critical_imaging': img_summary.get('critical_priority', 0),
                    'high_priority_imaging': img_summary.get('high_priority', 0),
                    'chemo_change_imaging': img_summary.get('chemotherapy_change_imaging', 0)
                })

            # Add survival endpoints if available
            if 'survival_endpoints' in result and result['survival_endpoints']:
                endpoints = result['survival_endpoints']
                row.update({
                    'vital_status': endpoints.get('vital_status'),
                    'last_known_alive': endpoints.get('last_known_alive'),
                    'last_clinical_contact': endpoints.get('last_clinical_contact'),
                    'death_date': endpoints.get('death_date')
                })

            # Add treatment counts
            row['chemotherapy_changes'] = result.get('chemotherapy_changes', 0)

            summary_rows.append(row)

        return pd.DataFrame(summary_rows)

    def generate_cohort_report(self, cohort_summary: pd.DataFrame) -> Dict:
        """
        Generate comprehensive cohort report
        """
        report = {
            'cohort_size': len(cohort_summary),
            'processing_success_rate': (cohort_summary['processing_status'] == 'success').mean() * 100,
            'vital_status': cohort_summary['vital_status'].value_counts().to_dict() if 'vital_status' in cohort_summary else {},
            'imaging_statistics': {},
            'treatment_statistics': {}
        }

        # Imaging statistics
        if 'total_imaging' in cohort_summary:
            report['imaging_statistics'] = {
                'median_total_imaging': cohort_summary['total_imaging'].median(),
                'median_critical_imaging': cohort_summary['critical_imaging'].median(),
                'total_critical_across_cohort': cohort_summary['critical_imaging'].sum()
            }

        # Treatment statistics
        if 'chemotherapy_changes' in cohort_summary:
            report['treatment_statistics'] = {
                'median_chemo_changes': cohort_summary['chemotherapy_changes'].median(),
                'patients_with_chemo': (cohort_summary['chemotherapy_changes'] > 0).sum()
            }

        # Save report
        report_file = self.output_base / "cohort_summaries" / "cohort_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        return report


def main():
    """
    Command-line interface for cohort processing
    """
    parser = argparse.ArgumentParser(description='Process RADIANT PCA cohort')
    parser.add_argument('staging_path', type=Path,
                       help='Path to staging directory with patient folders')
    parser.add_argument('output_path', type=Path,
                       help='Path for output files')
    parser.add_argument('--config', type=Path, default=None,
                       help='Path to configuration YAML (optional)')
    parser.add_argument('--patients', nargs='+', default=None,
                       help='Specific patient IDs to process (default: all)')
    parser.add_argument('--parallel', action='store_true',
                       help='Enable parallel processing')
    parser.add_argument('--test', action='store_true',
                       help='Test mode - process first 3 patients only')

    args = parser.parse_args()

    # Initialize processor
    processor = CohortProcessor(args.staging_path, args.output_path, args.config)

    # Get patient list
    if args.test:
        all_patients = processor.discover_patients()
        patient_list = all_patients[:3] if len(all_patients) >= 3 else all_patients
        logger.info(f"TEST MODE: Processing {len(patient_list)} patients")
    else:
        patient_list = args.patients

    # Process cohort
    cohort_summary = processor.process_cohort(patient_list, args.parallel)

    # Generate report
    if not cohort_summary.empty:
        report = processor.generate_cohort_report(cohort_summary)

        print("\n" + "="*80)
        print("COHORT PROCESSING COMPLETE")
        print("="*80)
        print(f"\nProcessed: {report['cohort_size']} patients")
        print(f"Success rate: {report['processing_success_rate']:.1f}%")

        if report['imaging_statistics']:
            print(f"\nImaging Statistics:")
            print(f"  Median imaging per patient: {report['imaging_statistics']['median_total_imaging']:.0f}")
            print(f"  Median critical imaging: {report['imaging_statistics']['median_critical_imaging']:.0f}")
            print(f"  Total critical imaging across cohort: {report['imaging_statistics']['total_critical_across_cohort']:.0f}")

        if report['vital_status']:
            print(f"\nVital Status:")
            for status, count in report['vital_status'].items():
                print(f"  {status}: {count}")


if __name__ == "__main__":
    # Example usage without command line
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")

    processor = CohortProcessor(staging_path, output_path)

    # Discover and show available patients
    patients = processor.discover_patients()
    print(f"\nFound {len(patients)} patients")
    print(f"First 5 patients: {patients[:5]}")

    # Process first patient as demo
    if patients:
        print(f"\nDemo: Processing first patient ({patients[0]})")
        result = processor.process_single_patient(patients[0])
        print(f"Result: {result.get('processing_status')}")