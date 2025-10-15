"""
Unified Multi-Source Extraction Workflow Orchestrator
=====================================================
Integrates all 5 phases of the strategic extraction workflow:
Phase 1: Structured Data Harvesting
Phase 2: Event Timeline Construction
Phase 3: Intelligent Binary Selection
Phase 4: Contextual BRIM Extraction
Phase 5: Cross-Source Validation
"""

import sys
import json
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import argparse

# Import all phase modules
sys.path.append(str(Path(__file__).parent))

from phase2_timeline_builder import ClinicalTimelineBuilder as TimelineBuilder
from phase3_intelligent_document_selector import IntelligentDocumentSelector
from phase4_contextual_brim_extraction import ContextualBRIMExtractor
from phase5_cross_source_validation import CrossSourceValidator
from comprehensive_chemotherapy_identifier import ComprehensiveChemotherapyIdentifier as ChemotherapyIdentifier
from tumor_surgery_classifier import TumorSurgeryClassifier
from enhanced_clinical_prioritization import EnhancedClinicalPrioritization as ClinicalPrioritizer
from enhanced_diagnosis_extraction import BrainTumorDiagnosisExtractor as DiagnosisExtractor
from molecular_diagnosis_integration import MolecularDiagnosisIntegration as MolecularIntegrator
from problem_list_analyzer import ProblemListAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UnifiedWorkflowOrchestrator:
    """
    Orchestrates the complete multi-source extraction workflow
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize orchestrator with configuration

        Args:
            config_path: Path to workflow configuration file
        """
        self.config = self._load_config(config_path)
        self.staging_base = Path(self.config['paths']['staging_base'])
        self.binary_base = Path(self.config['paths']['binary_base'])
        self.brim_base = Path(self.config['paths']['brim_base'])
        self.output_base = Path(self.config['paths']['output_base'])
        self.output_base.mkdir(exist_ok=True, parents=True)

        # Initialize components
        self._initialize_components()

    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load or create default configuration"""
        if config_path and config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default configuration
            return {
                'paths': {
                    'staging_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files',
                    'binary_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/binary_files',
                    'brim_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction',
                    'output_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs'
                },
                'workflow': {
                    'max_documents_per_patient': 100,
                    'parallel_processing': False,
                    'checkpoint_frequency': 5,
                    'enable_phase_1': True,
                    'enable_phase_2': True,
                    'enable_phase_3': True,
                    'enable_phase_4': True,
                    'enable_phase_5': True
                },
                'modules': {
                    'chemotherapy_identification': True,
                    'tumor_surgery_classification': True,
                    'radiation_analysis': True,
                    'imaging_prioritization': True,
                    'molecular_integration': True,
                    'problem_list_analysis': True
                }
            }

    def _initialize_components(self):
        """Initialize all workflow components"""
        logger.info("Initializing workflow components...")

        # Phase 2 components
        structured_features = {}  # Will be populated per patient
        self.timeline_builder = TimelineBuilder(self.staging_base, structured_features)
        self.chemo_identifier = ChemotherapyIdentifier(self.staging_base)
        self.surgery_classifier = TumorSurgeryClassifier()
        self.clinical_prioritizer = ClinicalPrioritizer(self.staging_base)
        self.diagnosis_extractor = DiagnosisExtractor()
        self.molecular_integrator = MolecularIntegrator()
        self.problem_analyzer = ProblemListAnalyzer()

        # Phase 3-5 components
        self.document_selector = IntelligentDocumentSelector(self.staging_base, self.binary_base)
        self.brim_extractor = ContextualBRIMExtractor(self.staging_base, self.brim_base)
        self.validator = CrossSourceValidator(self.staging_base)

        logger.info("All components initialized successfully")

    def discover_patients(self) -> List[str]:
        """Automatically discover all patients in staging directory"""
        patients = []
        for patient_dir in self.staging_base.glob("patient_*"):
            if patient_dir.is_dir():
                patient_id = patient_dir.name.replace("patient_", "")
                patients.append(patient_id)

        logger.info(f"Discovered {len(patients)} patients in staging directory")
        return sorted(patients)

    def process_patient(self, patient_id: str) -> Dict:
        """
        Process a single patient through all workflow phases

        Args:
            patient_id: Patient identifier

        Returns:
            Complete patient results dictionary
        """
        logger.info("="*80)
        logger.info(f"PROCESSING PATIENT: {patient_id}")
        logger.info("="*80)

        patient_results = {
            'patient_id': patient_id,
            'processing_start': datetime.now().isoformat(),
            'phases': {}
        }

        try:
            # Phase 1: Structured Data Harvesting (handled by staging files)
            if self.config['workflow']['enable_phase_1']:
                logger.info("\n" + "="*60)
                logger.info("PHASE 1: STRUCTURED DATA HARVESTING")
                logger.info("="*60)
                phase1_results = self._execute_phase1(patient_id)
                patient_results['phases']['phase1'] = phase1_results

            # Phase 2: Event Timeline Construction
            if self.config['workflow']['enable_phase_2']:
                logger.info("\n" + "="*60)
                logger.info("PHASE 2: EVENT TIMELINE CONSTRUCTION")
                logger.info("="*60)
                phase2_results = self._execute_phase2(patient_id)
                patient_results['phases']['phase2'] = phase2_results

            # Phase 3: Intelligent Binary Selection
            if self.config['workflow']['enable_phase_3']:
                logger.info("\n" + "="*60)
                logger.info("PHASE 3: INTELLIGENT BINARY SELECTION")
                logger.info("="*60)
                timeline = phase2_results.get('integrated_timeline', {})
                phase3_results = self._execute_phase3(patient_id, timeline)
                patient_results['phases']['phase3'] = phase3_results

            # Phase 4: Contextual BRIM Extraction
            if self.config['workflow']['enable_phase_4']:
                logger.info("\n" + "="*60)
                logger.info("PHASE 4: CONTEXTUAL BRIM EXTRACTION")
                logger.info("="*60)
                selected_docs = phase3_results.get('selected_documents')
                timeline = phase2_results.get('integrated_timeline', {})
                phase4_results = self._execute_phase4(patient_id, timeline, selected_docs)
                patient_results['phases']['phase4'] = phase4_results

            # Phase 5: Cross-Source Validation
            if self.config['workflow']['enable_phase_5']:
                logger.info("\n" + "="*60)
                logger.info("PHASE 5: CROSS-SOURCE VALIDATION")
                logger.info("="*60)
                brim_results = phase4_results.get('extraction_results', {})
                timeline = phase2_results.get('integrated_timeline', {})
                phase5_results = self._execute_phase5(patient_id, brim_results, timeline)
                patient_results['phases']['phase5'] = phase5_results

            patient_results['processing_end'] = datetime.now().isoformat()
            patient_results['status'] = 'completed'

            # Generate comprehensive patient report
            self._generate_patient_report(patient_results)

        except Exception as e:
            logger.error(f"Error processing patient {patient_id}: {str(e)}")
            patient_results['status'] = 'failed'
            patient_results['error'] = str(e)

        return patient_results

    def _execute_phase1(self, patient_id: str) -> Dict:
        """Phase 1: Verify structured data availability"""
        patient_path = self.staging_base / f"patient_{patient_id}"

        results = {
            'phase': 'structured_data_harvesting',
            'patient_path': str(patient_path),
            'data_sources': {}
        }

        # Check for required data sources
        required_sources = [
            'procedures', 'diagnoses', 'medications', 'imaging',
            'encounters', 'molecular_tests_metadata', 'problem_list'
        ]

        for source in required_sources:
            file_path = patient_path / f"{source}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                results['data_sources'][source] = {
                    'exists': True,
                    'record_count': len(df),
                    'columns': list(df.columns)[:10]  # First 10 columns
                }
                logger.info(f"  ✓ {source}: {len(df)} records")
            else:
                results['data_sources'][source] = {'exists': False}
                logger.warning(f"  ✗ {source}: Not found")

        results['sources_found'] = sum(1 for s in results['data_sources'].values() if s.get('exists'))
        results['sources_total'] = len(required_sources)

        return results

    def _execute_phase2(self, patient_id: str) -> Dict:
        """Phase 2: Build integrated clinical timeline"""
        patient_path = self.staging_base / f"patient_{patient_id}"

        # Initialize results
        results = {
            'phase': 'timeline_construction',
            'components': {}
        }

        # 1. Extract diagnosis information
        if self.config['modules']['tumor_surgery_classification']:
            diagnosis_info = self.diagnosis_extractor.extract_diagnosis(patient_path)
            results['components']['diagnosis'] = {
                'date': diagnosis_info.get('diagnosis_date'),
                'age': diagnosis_info.get('age_at_diagnosis'),
                'surgery_type': diagnosis_info.get('initial_surgery', {}).get('type')
            }
            logger.info(f"  Diagnosis: {diagnosis_info.get('diagnosis_date')} (age {diagnosis_info.get('age_at_diagnosis'):.1f})")

        # 2. Classify tumor surgeries
        if self.config['modules']['tumor_surgery_classification']:
            procedures_file = patient_path / 'procedures.csv'
            if procedures_file.exists():
                procedures_df = pd.read_csv(procedures_file)
                tumor_surgeries = self.surgery_classifier.classify_procedures(procedures_df)
                results['components']['tumor_surgeries'] = len(tumor_surgeries)
                logger.info(f"  Tumor surgeries: {len(tumor_surgeries)}")

        # 3. Identify chemotherapy
        if self.config['modules']['chemotherapy_identification']:
            chemo_data = self.chemo_identifier.identify_chemotherapy(patient_id)
            if chemo_data is not None:
                results['components']['chemotherapy'] = {
                    'medications_identified': len(chemo_data),
                    'treatment_periods': self.chemo_identifier.extract_treatment_periods(chemo_data)
                }
                logger.info(f"  Chemotherapy: {len(chemo_data)} medications")

        # 4. Integrate molecular testing
        if self.config['modules']['molecular_integration']:
            molecular_file = patient_path / 'molecular_tests_metadata.csv'
            if molecular_file.exists():
                molecular_df = pd.read_csv(molecular_file)
                molecular_info = self.molecular_integrator._create_integrated_diagnosis(
                    diagnosis_info,
                    molecular_df,
                    {}
                )
                results['components']['molecular_tests'] = molecular_info.get('molecular_testing', {})
                logger.info(f"  Molecular tests: {molecular_info.get('molecular_testing', {}).get('tests_performed', 0)}")

        # 5. Analyze problem list
        if self.config['modules']['problem_list_analysis']:
            problem_file = patient_path / 'problem_list.csv'
            if problem_file.exists():
                problem_df = pd.read_csv(problem_file)
                problem_analysis = self.problem_analyzer.analyze_problems(problem_df)
                results['components']['problems'] = problem_analysis['summary']
                logger.info(f"  Problem list: {problem_analysis['summary']['total_problems']} problems")

        # Build integrated timeline
        integrated_timeline = self.timeline_builder.build_timeline(patient_id)
        results['integrated_timeline'] = integrated_timeline

        # Save timeline
        timeline_file = self.output_base / f"integrated_timeline_{patient_id}.json"
        with open(timeline_file, 'w') as f:
            json.dump(integrated_timeline, f, indent=2, default=str)

        logger.info(f"  Timeline saved: {timeline_file.name}")

        return results

    def _execute_phase3(self, patient_id: str, clinical_timeline: Dict) -> Dict:
        """Phase 3: Select priority documents for extraction"""
        results = {
            'phase': 'document_selection'
        }

        # Select priority documents
        max_docs = self.config['workflow']['max_documents_per_patient']
        priority_docs = self.document_selector.select_priority_documents(
            patient_id,
            clinical_timeline,
            max_documents=max_docs
        )

        if not priority_docs.empty:
            results['selected_documents'] = priority_docs
            results['document_count'] = len(priority_docs)

            # Export for BRIM
            self.document_selector.export_for_brim(priority_docs, self.output_base)

            # Document type distribution
            if 'document_type' in priority_docs.columns:
                results['type_distribution'] = priority_docs['document_type'].value_counts().to_dict()

            logger.info(f"  Selected {len(priority_docs)} priority documents")
            for doc_type, count in results.get('type_distribution', {}).items():
                logger.info(f"    - {doc_type}: {count}")
        else:
            results['selected_documents'] = pd.DataFrame()
            results['document_count'] = 0
            logger.warning("  No documents selected")

        return results

    def _execute_phase4(self, patient_id: str, clinical_timeline: Dict,
                       selected_documents: pd.DataFrame) -> Dict:
        """Phase 4: Execute contextual BRIM extraction"""
        results = {
            'phase': 'brim_extraction'
        }

        if selected_documents is None or selected_documents.empty:
            logger.warning("  No documents available for BRIM extraction")
            results['extraction_results'] = {}
            return results

        # Create contextual configuration
        config = self.brim_extractor.create_contextual_config(
            patient_id,
            clinical_timeline,
            selected_documents
        )

        # Execute extraction
        extraction_results = self.brim_extractor.execute_brim_extraction(config, patient_id)
        results['extraction_results'] = extraction_results

        # Generate extraction report
        report = self.brim_extractor.generate_extraction_report(extraction_results)
        results['report_generated'] = True

        # Log summary
        stats = extraction_results.get('statistics', {})
        logger.info(f"  Variables extracted: {stats.get('extractions_successful', 0)}/{stats.get('total_variables', 0)}")
        logger.info(f"  Success rate: {stats.get('success_rate', 0):.1%}")

        return results

    def _execute_phase5(self, patient_id: str, brim_results: Dict,
                       clinical_timeline: Dict) -> Dict:
        """Phase 5: Validate extractions against structured data"""
        results = {
            'phase': 'validation'
        }

        # Run validation
        validation_report = self.validator.validate_extraction_results(
            patient_id,
            brim_results,
            clinical_timeline
        )
        results['validation_report'] = validation_report

        # Generate summary
        summary = self.validator.generate_validation_summary(validation_report)
        results['summary_generated'] = True

        # Log key metrics
        metrics = validation_report.get('metrics', {})
        logger.info(f"  Overall accuracy: {metrics.get('accuracy', 0):.1%}")
        logger.info(f"  Validation coverage: {metrics.get('validation_coverage', 0):.1%}")
        logger.info(f"  Discrepancy rate: {metrics.get('discrepancy_rate', 0):.1%}")

        # Log critical discrepancies
        critical = [d for d in validation_report.get('discrepancies', [])
                   if d.get('severity') == 'critical']
        if critical:
            logger.warning(f"  ⚠️  Critical discrepancies: {len(critical)}")

        return results

    def _generate_patient_report(self, patient_results: Dict):
        """Generate comprehensive patient processing report"""
        report = []
        report.append("="*80)
        report.append("UNIFIED WORKFLOW EXECUTION REPORT")
        report.append("="*80)
        report.append(f"\nPatient ID: {patient_results['patient_id']}")
        report.append(f"Processing Start: {patient_results['processing_start']}")
        report.append(f"Processing End: {patient_results.get('processing_end', 'N/A')}")
        report.append(f"Status: {patient_results.get('status', 'unknown').upper()}")

        # Phase summaries
        for phase_num in range(1, 6):
            phase_key = f'phase{phase_num}'
            if phase_key in patient_results.get('phases', {}):
                phase_data = patient_results['phases'][phase_key]
                report.append(f"\n{'='*60}")
                report.append(f"PHASE {phase_num}: {phase_data.get('phase', '').upper().replace('_', ' ')}")
                report.append("="*60)

                if phase_num == 1:
                    # Structured data summary
                    sources = phase_data.get('data_sources', {})
                    report.append(f"Data Sources: {phase_data.get('sources_found', 0)}/{phase_data.get('sources_total', 0)} found")
                    for source, info in sources.items():
                        if info.get('exists'):
                            report.append(f"  ✓ {source}: {info.get('record_count', 0)} records")

                elif phase_num == 2:
                    # Timeline summary
                    components = phase_data.get('components', {})
                    if 'diagnosis' in components:
                        diag = components['diagnosis']
                        report.append(f"Diagnosis Date: {diag.get('date', 'N/A')}")
                        report.append(f"Age at Diagnosis: {diag.get('age', 'N/A')}")
                    if 'chemotherapy' in components:
                        chemo = components['chemotherapy']
                        report.append(f"Chemotherapy Medications: {chemo.get('medications_identified', 0)}")

                elif phase_num == 3:
                    # Document selection summary
                    report.append(f"Documents Selected: {phase_data.get('document_count', 0)}")
                    if 'type_distribution' in phase_data:
                        report.append("Document Types:")
                        for doc_type, count in phase_data['type_distribution'].items():
                            report.append(f"  - {doc_type}: {count}")

                elif phase_num == 4:
                    # BRIM extraction summary
                    if 'extraction_results' in phase_data:
                        stats = phase_data['extraction_results'].get('statistics', {})
                        report.append(f"Variables Extracted: {stats.get('extractions_successful', 0)}/{stats.get('total_variables', 0)}")
                        report.append(f"Success Rate: {stats.get('success_rate', 0):.1%}")

                elif phase_num == 5:
                    # Validation summary
                    if 'validation_report' in phase_data:
                        metrics = phase_data['validation_report'].get('metrics', {})
                        report.append(f"Overall Accuracy: {metrics.get('accuracy', 0):.1%}")
                        report.append(f"Validation Coverage: {metrics.get('validation_coverage', 0):.1%}")
                        report.append(f"Discrepancy Rate: {metrics.get('discrepancy_rate', 0):.1%}")

        report.append("\n" + "="*80)
        report.append("END OF REPORT")
        report.append("="*80)

        report_text = "\n".join(report)

        # Save report
        report_path = self.output_base / f"workflow_report_{patient_results['patient_id']}.txt"
        with open(report_path, 'w') as f:
            f.write(report_text)

        # Also save JSON results
        json_path = self.output_base / f"workflow_results_{patient_results['patient_id']}.json"
        with open(json_path, 'w') as f:
            json.dump(patient_results, f, indent=2, default=str)

        logger.info(f"\nReports saved:")
        logger.info(f"  Text: {report_path.name}")
        logger.info(f"  JSON: {json_path.name}")

    def process_cohort(self, patient_list: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Process entire cohort or subset of patients

        Args:
            patient_list: Optional list of patient IDs to process

        Returns:
            Summary DataFrame with results for all patients
        """
        if patient_list is None:
            patient_list = self.discover_patients()

        logger.info("\n" + "="*80)
        logger.info(f"PROCESSING COHORT: {len(patient_list)} patients")
        logger.info("="*80)

        cohort_results = []

        for idx, patient_id in enumerate(patient_list, 1):
            logger.info(f"\n[{idx}/{len(patient_list)}] Processing patient: {patient_id}")

            try:
                patient_results = self.process_patient(patient_id)
                cohort_results.append(patient_results)

                # Checkpoint
                if idx % self.config['workflow']['checkpoint_frequency'] == 0:
                    self._save_checkpoint(cohort_results)
                    logger.info(f"Checkpoint saved at patient {idx}")

            except Exception as e:
                logger.error(f"Failed to process patient {patient_id}: {str(e)}")
                cohort_results.append({
                    'patient_id': patient_id,
                    'status': 'failed',
                    'error': str(e)
                })

        # Generate cohort summary
        summary_df = self._generate_cohort_summary(cohort_results)

        # Save final results
        self._save_cohort_results(cohort_results, summary_df)

        return summary_df

    def _save_checkpoint(self, results: List[Dict]):
        """Save processing checkpoint"""
        checkpoint_path = self.output_base / f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(checkpoint_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

    def _generate_cohort_summary(self, cohort_results: List[Dict]) -> pd.DataFrame:
        """Generate summary statistics for cohort"""
        summary_data = []

        for patient_result in cohort_results:
            patient_summary = {
                'patient_id': patient_result['patient_id'],
                'status': patient_result.get('status', 'unknown')
            }

            # Extract key metrics from each phase
            phases = patient_result.get('phases', {})

            # Phase 2 metrics
            if 'phase2' in phases:
                components = phases['phase2'].get('components', {})
                if 'diagnosis' in components:
                    patient_summary['diagnosis_date'] = components['diagnosis'].get('date')
                    patient_summary['age_at_diagnosis'] = components['diagnosis'].get('age')
                if 'chemotherapy' in components:
                    patient_summary['chemo_medications'] = components['chemotherapy'].get('medications_identified', 0)

            # Phase 3 metrics
            if 'phase3' in phases:
                patient_summary['documents_selected'] = phases['phase3'].get('document_count', 0)

            # Phase 4 metrics
            if 'phase4' in phases and 'extraction_results' in phases['phase4']:
                stats = phases['phase4']['extraction_results'].get('statistics', {})
                patient_summary['brim_success_rate'] = stats.get('success_rate', 0)

            # Phase 5 metrics
            if 'phase5' in phases and 'validation_report' in phases['phase5']:
                metrics = phases['phase5']['validation_report'].get('metrics', {})
                patient_summary['validation_accuracy'] = metrics.get('accuracy', 0)

            summary_data.append(patient_summary)

        summary_df = pd.DataFrame(summary_data)

        # Calculate cohort statistics
        logger.info("\n" + "="*60)
        logger.info("COHORT SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Patients: {len(summary_df)}")
        logger.info(f"Successfully Processed: {(summary_df['status'] == 'completed').sum()}")
        logger.info(f"Failed: {(summary_df['status'] == 'failed').sum()}")

        if 'brim_success_rate' in summary_df.columns:
            logger.info(f"Mean BRIM Success Rate: {summary_df['brim_success_rate'].mean():.1%}")

        if 'validation_accuracy' in summary_df.columns:
            logger.info(f"Mean Validation Accuracy: {summary_df['validation_accuracy'].mean():.1%}")

        return summary_df

    def _save_cohort_results(self, cohort_results: List[Dict], summary_df: pd.DataFrame):
        """Save final cohort results"""
        # Save detailed results
        results_path = self.output_base / f"cohort_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_path, 'w') as f:
            json.dump(cohort_results, f, indent=2, default=str)

        # Save summary CSV
        summary_path = self.output_base / f"cohort_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        summary_df.to_csv(summary_path, index=False)

        logger.info(f"\nCohort results saved:")
        logger.info(f"  Detailed: {results_path.name}")
        logger.info(f"  Summary: {summary_path.name}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Unified Multi-Source Extraction Workflow')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--patient', type=str, help='Process single patient ID')
    parser.add_argument('--cohort', action='store_true', help='Process entire cohort')
    parser.add_argument('--list-patients', action='store_true', help='List available patients')

    args = parser.parse_args()

    # Initialize orchestrator
    config_path = Path(args.config) if args.config else None
    orchestrator = UnifiedWorkflowOrchestrator(config_path)

    if args.list_patients:
        # List available patients
        patients = orchestrator.discover_patients()
        print(f"\nAvailable patients ({len(patients)}):")
        for p in patients:
            print(f"  - {p}")

    elif args.patient:
        # Process single patient
        results = orchestrator.process_patient(args.patient)
        print(f"\nProcessing complete for patient {args.patient}")
        print(f"Status: {results.get('status', 'unknown')}")

    elif args.cohort:
        # Process entire cohort
        summary_df = orchestrator.process_cohort()
        print(f"\nCohort processing complete")
        print(f"Patients processed: {len(summary_df)}")

    else:
        # Default: process test patient
        test_patient = "e4BwD8ZYDBccepXcJ.Ilo3w3"
        print(f"\nProcessing test patient: {test_patient}")
        results = orchestrator.process_patient(test_patient)
        print(f"Status: {results.get('status', 'unknown')}")


if __name__ == "__main__":
    main()