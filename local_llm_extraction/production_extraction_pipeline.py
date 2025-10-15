#!/usr/bin/env python3
"""
Production extraction pipeline for all RADIANT PCA patients
Implements multi-source extraction with post-operative imaging validation
"""

import pandas as pd
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import concurrent.futures
from typing import Dict, List, Optional, Tuple
import argparse
import sys
import os

# Import our extraction modules
sys.path.append(str(Path(__file__).parent))
from event_based_extraction.enhanced_extraction_with_fallback import EnhancedEventExtractor
from extract_extent_from_postop_imaging import extract_extent_from_postop_imaging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extraction_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionExtractionPipeline:
    """
    Production-ready extraction pipeline for RADIANT PCA patients
    """

    def __init__(self, patient_list_path: str, output_dir: str = None):
        """
        Initialize pipeline

        Args:
            patient_list_path: Path to CSV with patient IDs
            output_dir: Output directory for results
        """
        self.patient_list = self._load_patient_list(patient_list_path)
        self.extractor = EnhancedEventExtractor()

        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.output_dir = Path(f'./outputs/production_run_{timestamp}')

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.patient_dir = self.output_dir / 'patient_extractions'
        self.patient_dir.mkdir(exist_ok=True)

        self.validation_dir = self.output_dir / 'validation_reports'
        self.validation_dir.mkdir(exist_ok=True)

        self.redcap_dir = self.output_dir / 'redcap_import'
        self.redcap_dir.mkdir(exist_ok=True)

        # Track statistics
        self.stats = {
            'total_patients': 0,
            'successful': 0,
            'failed': 0,
            'discrepancies_found': 0,
            'variables_extracted': {},
            'confidence_scores': []
        }

    def _load_patient_list(self, path: str) -> pd.DataFrame:
        """Load and validate patient list"""
        try:
            df = pd.read_csv(path)
            if 'patient_id' not in df.columns:
                raise ValueError("patient_id column not found in patient list")
            logger.info(f"Loaded {len(df)} patients from {path}")
            return df
        except Exception as e:
            logger.error(f"Failed to load patient list: {e}")
            raise

    def process_patient(self, patient_id: str) -> Dict:
        """
        Complete extraction for single patient

        Args:
            patient_id: Patient identifier

        Returns:
            Dictionary with extraction results
        """
        logger.info(f"Processing patient {patient_id}")
        self.stats['total_patients'] += 1

        try:
            # Get patient events from procedures table
            events = self._get_patient_events(patient_id)

            if not events:
                logger.warning(f"No surgical events found for patient {patient_id}")
                return {
                    'patient_id': patient_id,
                    'extraction_timestamp': datetime.now().isoformat(),
                    'status': 'no_events',
                    'events': []
                }

            results = {
                'patient_id': patient_id,
                'extraction_timestamp': datetime.now().isoformat(),
                'status': 'success',
                'events': []
            }

            # Process each event
            for idx, event in enumerate(events, 1):
                logger.info(f"Processing event {idx}/{len(events)} for patient {patient_id}")
                event_result = self.process_event(patient_id, event)
                results['events'].append(event_result)

                # Update statistics
                self._update_stats(event_result)

            # Save patient results
            self._save_patient_results(patient_id, results)

            self.stats['successful'] += 1
            return results

        except Exception as e:
            logger.error(f"Failed to process patient {patient_id}: {e}")
            self.stats['failed'] += 1

            error_result = {
                'patient_id': patient_id,
                'extraction_timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }

            # Save error result
            self._save_patient_results(patient_id, error_result)
            return error_result

    def _get_patient_events(self, patient_id: str) -> List[Dict]:
        """Get surgical events for patient"""
        try:
            staging_dir = Path(f'/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files/patient_{patient_id}')
            procedures_file = staging_dir / 'procedures.csv'

            if not procedures_file.exists():
                logger.warning(f"No procedures file for patient {patient_id}")
                return []

            procedures_df = pd.read_csv(procedures_file)

            # Filter for CNS tumor surgeries
            surgery_codes = ['61510', '61512', '61518', '61519', '61520']
            surgeries = procedures_df[
                procedures_df['procedure_source_value'].astype(str).isin(surgery_codes)
            ]

            if surgeries.empty:
                return []

            # Convert to list of events
            events = []
            for _, row in surgeries.iterrows():
                events.append({
                    'surgery_date': row['procedure_date'],
                    'procedure_code': row['procedure_source_value'],
                    'procedure_name': row.get('procedure_source_name', 'CNS tumor surgery')
                })

            return sorted(events, key=lambda x: x['surgery_date'])

        except Exception as e:
            logger.error(f"Failed to get events for {patient_id}: {e}")
            return []

    def process_event(self, patient_id: str, event: Dict) -> Dict:
        """
        Extract all variables for single surgical event

        Args:
            patient_id: Patient identifier
            event: Event dictionary with surgery_date

        Returns:
            Dictionary with extracted variables
        """
        event_date = event['surgery_date']
        logger.info(f"Extracting for event on {event_date}")

        try:
            # Primary extraction with fallback
            primary_results = self.extractor.extract_for_event(
                patient_id,
                event_date,
                include_fallback=True
            )

            # Post-op imaging validation for extent of resection
            validation_performed = False
            discrepancy_found = False

            if 'extent_of_tumor_resection' in primary_results:
                logger.info("Validating extent of resection with post-op imaging")
                postop_extent = extract_extent_from_postop_imaging(patient_id, event_date)

                if postop_extent:
                    validation_performed = True
                    original_value = primary_results['extent_of_tumor_resection'].get('value')
                    postop_value = postop_extent.get('consensus_extent')

                    if original_value != postop_value:
                        discrepancy_found = True
                        self.stats['discrepancies_found'] += 1

                        logger.warning(
                            f"DISCREPANCY: Operative note: {original_value} "
                            f"vs Post-op imaging: {postop_value}"
                        )

                        # Override with post-op imaging (gold standard)
                        primary_results['extent_of_tumor_resection'] = {
                            'value': postop_value,
                            'confidence': 0.95,
                            'source': 'post_operative_imaging',
                            'original_value': original_value,
                            'override_reason': 'Post-op MRI is gold standard for extent',
                            'supporting_evidence': postop_extent.get('all_extractions', [])
                        }

            return {
                'event_date': event_date,
                'event_type': 'CNS tumor surgery',
                'procedure': event.get('procedure_name'),
                'extracted_variables': primary_results,
                'validation': {
                    'post_op_imaging_checked': validation_performed,
                    'discrepancy_found': discrepancy_found,
                    'timestamp': datetime.now().isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Failed to process event {event_date}: {e}")
            return {
                'event_date': event_date,
                'error': str(e),
                'extracted_variables': {}
            }

    def _update_stats(self, event_result: Dict):
        """Update running statistics"""
        for var_name, var_data in event_result.get('extracted_variables', {}).items():
            if var_name not in self.stats['variables_extracted']:
                self.stats['variables_extracted'][var_name] = {
                    'total': 0,
                    'available': 0,
                    'unavailable': 0,
                    'confidence_sum': 0
                }

            self.stats['variables_extracted'][var_name]['total'] += 1

            if var_data.get('value') and var_data['value'] != 'Unavailable':
                self.stats['variables_extracted'][var_name]['available'] += 1
            else:
                self.stats['variables_extracted'][var_name]['unavailable'] += 1

            confidence = var_data.get('confidence', 0)
            self.stats['variables_extracted'][var_name]['confidence_sum'] += confidence
            self.stats['confidence_scores'].append(confidence)

    def _save_patient_results(self, patient_id: str, results: Dict):
        """Save patient extraction results"""
        output_file = self.patient_dir / f'patient_{patient_id}.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Saved results to {output_file}")

    def run_batch_extraction(self, max_workers: int = 4) -> Dict:
        """
        Process all patients in parallel

        Args:
            max_workers: Maximum number of parallel workers

        Returns:
            Summary dictionary
        """
        logger.info(f"Starting batch extraction with {max_workers} workers")
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_patient = {
                executor.submit(self.process_patient, row['patient_id']): row['patient_id']
                for _, row in self.patient_list.iterrows()
            }

            for future in concurrent.futures.as_completed(future_to_patient):
                patient_id = future_to_patient[future]
                try:
                    result = future.result(timeout=300)  # 5 min timeout
                    results.append(result)
                    logger.info(f"Completed {patient_id} ({len(results)}/{len(self.patient_list)})")
                except Exception as e:
                    logger.error(f"Patient {patient_id} failed: {e}")
                    results.append({
                        'patient_id': patient_id,
                        'status': 'timeout',
                        'error': str(e)
                    })

        # Generate summary report
        summary = self.generate_summary_report(results)

        # Generate REDCap import file
        self.generate_redcap_import(results)

        return summary

    def generate_summary_report(self, results: List[Dict]) -> Dict:
        """Generate extraction summary statistics"""
        summary = {
            'run_timestamp': datetime.now().isoformat(),
            'total_patients': len(results),
            'successful': sum(1 for r in results if r.get('status') == 'success'),
            'failed': sum(1 for r in results if r.get('status') == 'error'),
            'no_events': sum(1 for r in results if r.get('status') == 'no_events'),
            'discrepancies_found': self.stats['discrepancies_found'],
            'variables_summary': {},
            'confidence_statistics': {}
        }

        # Calculate variable-level statistics
        for var_name, var_stats in self.stats['variables_extracted'].items():
            if var_stats['total'] > 0:
                summary['variables_summary'][var_name] = {
                    'total_extractions': var_stats['total'],
                    'successful': var_stats['available'],
                    'unavailable': var_stats['unavailable'],
                    'success_rate': var_stats['available'] / var_stats['total'],
                    'avg_confidence': var_stats['confidence_sum'] / var_stats['total']
                }

        # Calculate confidence statistics
        if self.stats['confidence_scores']:
            scores = self.stats['confidence_scores']
            summary['confidence_statistics'] = {
                'mean': sum(scores) / len(scores),
                'median': sorted(scores)[len(scores) // 2],
                'min': min(scores),
                'max': max(scores),
                'below_0.7': sum(1 for s in scores if s < 0.7) / len(scores)
            }

        # Save summary
        summary_file = self.output_dir / 'extraction_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        # Print summary
        print("\n" + "=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        print(f"Total patients: {summary['total_patients']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"No events: {summary['no_events']}")
        print(f"Discrepancies found: {summary['discrepancies_found']}")

        if summary.get('confidence_statistics'):
            print(f"\nConfidence scores:")
            print(f"  Mean: {summary['confidence_statistics']['mean']:.3f}")
            print(f"  Median: {summary['confidence_statistics']['median']:.3f}")
            print(f"  Below 0.7: {summary['confidence_statistics']['below_0.7']:.1%}")

        print("\nVariable extraction rates:")
        for var_name, var_stats in summary.get('variables_summary', {}).items():
            print(f"  {var_name}: {var_stats['success_rate']:.1%} success rate")

        logger.info(f"Summary saved to {summary_file}")
        return summary

    def generate_redcap_import(self, results: List[Dict]):
        """Generate REDCap import file"""
        redcap_records = []

        # Load data dictionary mappings
        dictionary_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction/Dictionary/radiology_op_note_data_dictionary.csv')
        if dictionary_path.exists():
            data_dict = pd.read_csv(dictionary_path)
            # Create mapping for each variable
            mappings = self._create_dictionary_mappings(data_dict)
        else:
            logger.warning("Data dictionary not found, using raw values")
            mappings = {}

        for patient_result in results:
            if patient_result.get('status') != 'success':
                continue

            patient_id = patient_result['patient_id']

            for event_idx, event in enumerate(patient_result.get('events', []), 1):
                record = {
                    'record_id': f"{patient_id}_event{event_idx}",
                    'event_name': f"surgery_{event_idx}_arm_1",
                    'surgery_date': event.get('event_date')
                }

                # Add extracted variables
                for var_name, var_data in event.get('extracted_variables', {}).items():
                    value = var_data.get('value')

                    # Map to dictionary code if available
                    if var_name in mappings and value in mappings[var_name]:
                        record[var_name] = mappings[var_name][value]
                    else:
                        record[var_name] = value

                    # Add confidence score
                    record[f"{var_name}_confidence"] = var_data.get('confidence', 0)

                # Handle checkbox fields (multiple values)
                for field in ['tumor_location', 'metastasis_location']:
                    if field in record and isinstance(record[field], list):
                        record[field] = '|'.join(map(str, record[field]))

                redcap_records.append(record)

        # Save as CSV
        if redcap_records:
            df = pd.DataFrame(redcap_records)
            output_file = self.redcap_dir / 'redcap_import.csv'
            df.to_csv(output_file, index=False)
            logger.info(f"REDCap import file saved to {output_file}")
        else:
            logger.warning("No records to export for REDCap")

    def _create_dictionary_mappings(self, data_dict: pd.DataFrame) -> Dict:
        """Create value-to-code mappings from data dictionary"""
        mappings = {}

        # Example mappings (customize based on actual dictionary)
        mappings['extent_of_tumor_resection'] = {
            'Gross total resection': 1,
            'Near-total resection': 1,
            'Subtotal resection': 2,
            'Partial resection': 2,
            'Biopsy only': 3,
            'Unavailable': 4
        }

        return mappings


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='RADIANT PCA Production Extraction Pipeline'
    )
    parser.add_argument(
        'patient_list',
        help='Path to CSV file with patient IDs'
    )
    parser.add_argument(
        '--output-dir',
        help='Output directory for results',
        default=None
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    parser.add_argument(
        '--single-patient',
        help='Extract single patient only',
        default=None
    )

    args = parser.parse_args()

    # Initialize pipeline
    pipeline = ProductionExtractionPipeline(
        patient_list_path=args.patient_list,
        output_dir=args.output_dir
    )

    # Run extraction
    if args.single_patient:
        # Single patient mode
        result = pipeline.process_patient(args.single_patient)
        print(f"\nExtraction complete for patient {args.single_patient}")
        print(f"Results saved to {pipeline.output_dir}")
    else:
        # Batch mode
        summary = pipeline.run_batch_extraction(max_workers=args.workers)
        print(f"\nExtraction complete. Results saved to {pipeline.output_dir}")

    return 0


if __name__ == '__main__':
    sys.exit(main())