"""
Data Validation Report for Patient e4BwD8ZYDBccepXcJ.Ilo3w3
===========================================================
Systematic validation of available data sources
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataValidator:
    """Validate and document available data for a patient"""

    def __init__(self, staging_path: str, patient_id: str):
        self.staging_path = Path(staging_path)
        self.patient_id = patient_id
        self.patient_path = self.staging_path / f"patient_{patient_id}"
        self.validation_report = {}

    def validate_all_sources(self):
        """Run complete validation of all data sources"""
        logger.info(f"="*80)
        logger.info(f"DATA VALIDATION REPORT FOR PATIENT {self.patient_id}")
        logger.info(f"="*80)
        logger.info(f"Staging Path: {self.patient_path}")
        logger.info(f"Report Generated: {datetime.now()}")
        logger.info("")

        # Check if patient directory exists
        if not self.patient_path.exists():
            logger.error(f"Patient directory not found: {self.patient_path}")
            return self.validation_report

        # Validate each data source
        self._validate_procedures()
        self._validate_binary_files()
        self._validate_imaging()
        self._validate_diagnoses()
        self._validate_medications()
        self._validate_measurements()
        self._validate_encounters()
        self._validate_radiation()
        self._validate_appointments()

        # Generate summary
        self._generate_summary()

        return self.validation_report

    def _validate_procedures(self):
        """Validate procedures.csv"""
        file_path = self.patient_path / "procedures.csv"
        logger.info(f"\n{'='*60}")
        logger.info("PROCEDURES VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['procedures'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} records")

            # Check for date columns
            if 'procedure_date' in df.columns:
                df['procedure_date'] = pd.to_datetime(df['procedure_date'], errors='coerce')
                date_range = f"{df['procedure_date'].min()} to {df['procedure_date'].max()}"
                logger.info(f"  Date range: {date_range}")

            # Check for surgical procedures
            surgical_keywords = ['craniotomy', 'craniectomy', 'resection', 'ventriculostomy',
                               'debulking', 'biopsy', 'shunt']

            surgical_count = 0
            if 'proc_code_text' in df.columns:
                pattern = '|'.join(surgical_keywords)
                surgical_mask = df['proc_code_text'].str.contains(pattern, case=False, na=False)
                surgical_count = surgical_mask.sum()
                logger.info(f"  Surgical procedures found: {surgical_count}")

                if surgical_count > 0:
                    surgical_procs = df[surgical_mask]
                    logger.info("  Surgical procedure types:")
                    for _, row in surgical_procs.iterrows():
                        proc_date = row.get('procedure_date', 'N/A')
                        proc_text = row.get('proc_code_text', 'N/A')
                        logger.info(f"    - {proc_date}: {proc_text}")

            # Check for specific columns
            important_columns = ['procedure_fhir_id', 'proc_status', 'proc_code_text',
                                'procedure_date', 'age_at_procedure_days']
            missing_columns = [col for col in important_columns if col not in df.columns]

            if missing_columns:
                logger.warning(f"  Missing columns: {missing_columns}")

            self.validation_report['procedures'] = {
                'exists': True,
                'record_count': len(df),
                'surgical_count': surgical_count,
                'date_range': date_range if 'procedure_date' in df.columns else None,
                'columns': list(df.columns)
            }

        except Exception as e:
            logger.error(f"Error reading procedures file: {e}")
            self.validation_report['procedures'] = {'exists': True, 'error': str(e)}

    def _validate_binary_files(self):
        """Validate binary_files.csv"""
        file_path = self.patient_path / "binary_files.csv"
        logger.info(f"\n{'='*60}")
        logger.info("BINARY FILES VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['binary_files'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} documents")

            # Document type distribution
            if 'dr_type_text' in df.columns:
                doc_types = df['dr_type_text'].value_counts()
                logger.info("  Document type distribution:")
                for dtype, count in doc_types.head(10).items():
                    logger.info(f"    - {dtype}: {count}")

            # Check for operative notes
            op_note_count = 0
            if 'dr_type_text' in df.columns:
                op_notes = df[df['dr_type_text'].str.contains('OP Note|Operative', case=False, na=False)]
                op_note_count = len(op_notes)
                logger.info(f"\n  Operative notes found: {op_note_count}")

                if op_note_count > 0 and 'dr_date' in op_notes.columns:
                    op_notes['dr_date'] = pd.to_datetime(op_notes['dr_date'], errors='coerce')
                    unique_op_dates = op_notes['dr_date'].dt.date.dropna().unique()
                    logger.info(f"  Unique operative note dates: {len(unique_op_dates)}")
                    for date in sorted(unique_op_dates)[:10]:
                        count = len(op_notes[op_notes['dr_date'].dt.date == date])
                        logger.info(f"    - {date}: {count} notes")

            self.validation_report['binary_files'] = {
                'exists': True,
                'document_count': len(df),
                'operative_note_count': op_note_count,
                'document_types': doc_types.to_dict() if 'dr_type_text' in df.columns else {}
            }

        except Exception as e:
            logger.error(f"Error reading binary files: {e}")
            self.validation_report['binary_files'] = {'exists': True, 'error': str(e)}

    def _validate_imaging(self):
        """Validate imaging.csv"""
        file_path = self.patient_path / "imaging.csv"
        logger.info(f"\n{'='*60}")
        logger.info("IMAGING VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['imaging'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} studies")

            # Date range
            if 'imaging_date' in df.columns:
                df['imaging_date'] = pd.to_datetime(df['imaging_date'], errors='coerce')
                date_range = f"{df['imaging_date'].min()} to {df['imaging_date'].max()}"
                logger.info(f"  Date range: {date_range}")

            # Modality distribution
            if 'imaging_modality' in df.columns:
                modalities = df['imaging_modality'].value_counts()
                logger.info("  Imaging modalities:")
                for mod, count in modalities.items():
                    logger.info(f"    - {mod}: {count}")

            # Check for progression keywords in reports
            progression_count = 0
            if 'result_information' in df.columns:
                progression_keywords = ['progression', 'progressive', 'interval increase',
                                       'growing', 'enlarged', 'new enhancement']
                pattern = '|'.join(progression_keywords)
                prog_mask = df['result_information'].str.contains(pattern, case=False, na=False)
                progression_count = prog_mask.sum()
                logger.info(f"\n  Studies with progression keywords: {progression_count}")

            self.validation_report['imaging'] = {
                'exists': True,
                'study_count': len(df),
                'progression_mentions': progression_count,
                'date_range': date_range if 'imaging_date' in df.columns else None,
                'modalities': modalities.to_dict() if 'imaging_modality' in df.columns else {}
            }

        except Exception as e:
            logger.error(f"Error reading imaging file: {e}")
            self.validation_report['imaging'] = {'exists': True, 'error': str(e)}

    def _validate_diagnoses(self):
        """Validate diagnoses.csv"""
        file_path = self.patient_path / "diagnoses.csv"
        logger.info(f"\n{'='*60}")
        logger.info("DIAGNOSES VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['diagnoses'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} diagnoses")

            # Check for brain tumor diagnoses
            brain_tumor_count = 0
            if 'icd10_code' in df.columns:
                brain_codes = ['C71', 'D43', 'D33']
                brain_tumors = df[df['icd10_code'].str.startswith(tuple(brain_codes), na=False)]
                brain_tumor_count = len(brain_tumors)
                logger.info(f"  Brain tumor diagnoses: {brain_tumor_count}")

                if brain_tumor_count > 0 and 'diagnosis_name' in brain_tumors.columns:
                    logger.info("  Brain tumor types:")
                    for name in brain_tumors['diagnosis_name'].unique()[:5]:
                        logger.info(f"    - {name}")

            # Check for metastasis
            metastasis_count = 0
            if 'icd10_code' in df.columns:
                met_codes = ['C79', 'C78']
                metastases = df[df['icd10_code'].str.startswith(tuple(met_codes), na=False)]
                metastasis_count = len(metastases)
                logger.info(f"  Metastasis diagnoses: {metastasis_count}")

            self.validation_report['diagnoses'] = {
                'exists': True,
                'diagnosis_count': len(df),
                'brain_tumor_count': brain_tumor_count,
                'metastasis_count': metastasis_count
            }

        except Exception as e:
            logger.error(f"Error reading diagnoses file: {e}")
            self.validation_report['diagnoses'] = {'exists': True, 'error': str(e)}

    def _validate_medications(self):
        """Validate medications.csv"""
        file_path = self.patient_path / "medications.csv"
        logger.info(f"\n{'='*60}")
        logger.info("MEDICATIONS VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['medications'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} medications")

            # Check for chemotherapy
            chemo_count = 0
            if 'medication_name' in df.columns:
                chemo_keywords = ['temozolomide', 'carboplatin', 'vincristine',
                                'lomustine', 'bevacizumab']
                pattern = '|'.join(chemo_keywords)
                chemo_meds = df[df['medication_name'].str.contains(pattern, case=False, na=False)]
                chemo_count = len(chemo_meds)
                logger.info(f"  Chemotherapy medications: {chemo_count}")

                if chemo_count > 0:
                    logger.info("  Chemotherapy agents:")
                    for med in chemo_meds['medication_name'].unique()[:5]:
                        logger.info(f"    - {med}")

            self.validation_report['medications'] = {
                'exists': True,
                'medication_count': len(df),
                'chemotherapy_count': chemo_count
            }

        except Exception as e:
            logger.error(f"Error reading medications file: {e}")
            self.validation_report['medications'] = {'exists': True, 'error': str(e)}

    def _validate_measurements(self):
        """Validate measurements.csv"""
        file_path = self.patient_path / "measurements.csv"
        logger.info(f"\n{'='*60}")
        logger.info("MEASUREMENTS VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['measurements'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} measurements")

            # Measurement types
            if 'obs_measurement_type' in df.columns:
                meas_types = df['obs_measurement_type'].value_counts()
                logger.info("  Measurement types (top 10):")
                for mtype, count in meas_types.head(10).items():
                    logger.info(f"    - {mtype}: {count}")

            self.validation_report['measurements'] = {
                'exists': True,
                'measurement_count': len(df),
                'measurement_types': meas_types.head(10).to_dict() if 'obs_measurement_type' in df.columns else {}
            }

        except Exception as e:
            logger.error(f"Error reading measurements file: {e}")
            self.validation_report['measurements'] = {'exists': True, 'error': str(e)}

    def _validate_encounters(self):
        """Validate encounters.csv"""
        file_path = self.patient_path / "encounters.csv"
        logger.info(f"\n{'='*60}")
        logger.info("ENCOUNTERS VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['encounters'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} encounters")

            # Service types
            if 'service_type_text' in df.columns:
                service_types = df['service_type_text'].value_counts()
                logger.info("  Service types (top 10):")
                for stype, count in service_types.head(10).items():
                    logger.info(f"    - {stype}: {count}")

            # Check for surgical encounters
            surgical_count = 0
            if 'service_type_text' in df.columns:
                surgical_encounters = df[df['service_type_text'].str.contains(
                    'surg|neuro', case=False, na=False)]
                surgical_count = len(surgical_encounters)
                logger.info(f"\n  Surgical/Neurosurgery encounters: {surgical_count}")

            self.validation_report['encounters'] = {
                'exists': True,
                'encounter_count': len(df),
                'surgical_encounter_count': surgical_count
            }

        except Exception as e:
            logger.error(f"Error reading encounters file: {e}")
            self.validation_report['encounters'] = {'exists': True, 'error': str(e)}

    def _validate_radiation(self):
        """Validate radiation files"""
        logger.info(f"\n{'='*60}")
        logger.info("RADIATION DATA VALIDATION")
        logger.info(f"{'='*60}")

        # Check radiation_data_summary
        summary_file = self.patient_path / "radiation_data_summary.csv"
        if summary_file.exists():
            try:
                df = pd.read_csv(summary_file)
                logger.info(f"✓ Radiation summary exists")

                if not df.empty:
                    row = df.iloc[0]
                    logger.info(f"  Radiation therapy received: {row.get('radiation_therapy_received', 'N/A')}")
                    logger.info(f"  Number of courses: {row.get('num_treatment_courses', 'N/A')}")
                    logger.info(f"  Number of appointments: {row.get('num_radiation_appointments', 'N/A')}")

                    self.validation_report['radiation'] = {
                        'exists': True,
                        'therapy_received': row.get('radiation_therapy_received', 'N/A'),
                        'num_courses': row.get('num_treatment_courses', 0)
                    }
            except Exception as e:
                logger.error(f"Error reading radiation summary: {e}")
        else:
            logger.warning("Radiation summary file not found")
            self.validation_report['radiation'] = {'exists': False}

    def _validate_appointments(self):
        """Validate appointments.csv"""
        file_path = self.patient_path / "appointments.csv"
        logger.info(f"\n{'='*60}")
        logger.info("APPOINTMENTS VALIDATION")
        logger.info(f"{'='*60}")

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            self.validation_report['appointments'] = {'exists': False}
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"✓ File exists: {len(df)} appointments")

            # Date range
            if 'appointment_date' in df.columns:
                df['appointment_date'] = pd.to_datetime(df['appointment_date'], errors='coerce')
                date_range = f"{df['appointment_date'].min()} to {df['appointment_date'].max()}"
                logger.info(f"  Date range: {date_range}")

            self.validation_report['appointments'] = {
                'exists': True,
                'appointment_count': len(df),
                'date_range': date_range if 'appointment_date' in df.columns else None
            }

        except Exception as e:
            logger.error(f"Error reading appointments file: {e}")
            self.validation_report['appointments'] = {'exists': True, 'error': str(e)}

    def _generate_summary(self):
        """Generate validation summary"""
        logger.info(f"\n{'='*80}")
        logger.info("VALIDATION SUMMARY")
        logger.info(f"{'='*80}")

        # Count available sources
        available = sum(1 for k, v in self.validation_report.items()
                       if isinstance(v, dict) and v.get('exists', False))
        total = len(self.validation_report)

        logger.info(f"Data sources available: {available}/{total}")

        # Key findings
        logger.info("\nKEY FINDINGS:")

        # Surgical procedures
        if 'procedures' in self.validation_report and self.validation_report['procedures'].get('exists'):
            surgical_count = self.validation_report['procedures'].get('surgical_count', 0)
            logger.info(f"  - Surgical procedures in procedures table: {surgical_count}")

        # Operative notes
        if 'binary_files' in self.validation_report and self.validation_report['binary_files'].get('exists'):
            op_note_count = self.validation_report['binary_files'].get('operative_note_count', 0)
            logger.info(f"  - Operative notes in binary files: {op_note_count}")

        # Imaging with progression
        if 'imaging' in self.validation_report and self.validation_report['imaging'].get('exists'):
            prog_count = self.validation_report['imaging'].get('progression_mentions', 0)
            logger.info(f"  - Imaging studies with progression keywords: {prog_count}")

        # Brain tumor diagnoses
        if 'diagnoses' in self.validation_report and self.validation_report['diagnoses'].get('exists'):
            brain_count = self.validation_report['diagnoses'].get('brain_tumor_count', 0)
            logger.info(f"  - Brain tumor diagnoses: {brain_count}")

        # Radiation therapy
        if 'radiation' in self.validation_report and self.validation_report['radiation'].get('exists'):
            rad_received = self.validation_report['radiation'].get('therapy_received', 'N/A')
            logger.info(f"  - Radiation therapy received: {rad_received}")


if __name__ == "__main__":
    # Run validation
    staging_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files"
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    validator = DataValidator(staging_path, patient_id)
    report = validator.validate_all_sources()

    # Save report to JSON
    import json
    output_path = Path(__file__).parent / f"validation_report_{patient_id}.json"
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"\nValidation report saved to: {output_path}")