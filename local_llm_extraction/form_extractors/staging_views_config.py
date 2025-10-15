"""
Comprehensive configuration for all Athena staging views and materialized tables.
This defines the complete schema and structure of available data sources for extraction.
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ViewConfiguration:
    """Configuration for a single staging view/table."""
    name: str
    primary_key: List[str]
    date_columns: List[str]
    key_columns: List[str]
    description: str
    extraction_relevance: Dict[str, Any] = field(default_factory=dict)

class StagingViewsConfiguration:
    """Complete configuration for all Athena staging views."""

    STAGING_VIEWS = {
        'procedures': ViewConfiguration(
            name='procedures',
            primary_key=['procedure_id'],
            date_columns=['proc_performed_date_time', 'procedure_date'],
            key_columns=['procedure_id', 'proc_code', 'proc_code_text', 'is_surgical_keyword'],
            description='All procedures including surgeries, biopsies, and interventions',
            extraction_relevance={
                'extent_of_resection': 'PRIMARY',
                'surgery_date': 'PRIMARY',
                'surgery_type': 'PRIMARY',
                'complications': 'SECONDARY'
            }
        ),

        'diagnoses': ViewConfiguration(
            name='diagnoses',
            primary_key=['diagnosis_id'],
            date_columns=['onset_date_time', 'recorded_date'],
            key_columns=['diagnosis_id', 'icd10_code', 'diagnosis_name', 'status'],
            description='ICD-10 diagnosis codes and clinical problems',
            extraction_relevance={
                'who_cns5_diagnosis': 'PRIMARY',
                'tumor_grade': 'PRIMARY',
                'metastasis': 'PRIMARY',
                'comorbidities': 'SECONDARY'
            }
        ),

        'medications': ViewConfiguration(
            name='medications',
            primary_key=['medication_id'],
            date_columns=['medication_start_date', 'med_date_given_start', 'med_date_given_end'],
            key_columns=[
                'medication_id', 'medication_name', 'rxnorm_code',
                'ingredient_rxnorm', 'product_rxnorm', 'is_chemotherapy',
                'dosage', 'route', 'frequency'
            ],
            description='All medications including chemotherapy and supportive care',
            extraction_relevance={
                'chemotherapy_drugs': 'PRIMARY',
                'concomitant_medications': 'PRIMARY',
                'steroid_use': 'SECONDARY',
                'anticonvulsants': 'SECONDARY'
            }
        ),

        'imaging': ViewConfiguration(
            name='imaging',
            primary_key=['imaging_id'],
            date_columns=['imaging_date', 'study_date'],
            key_columns=[
                'imaging_id', 'modality', 'body_site', 'contrast',
                'findings', 'impression', 'is_postop_72hr'
            ],
            description='Imaging studies including MRI, CT, and PET scans',
            extraction_relevance={
                'extent_of_resection': 'CRITICAL',  # Post-op imaging is gold standard
                'tumor_location': 'PRIMARY',
                'tumor_size': 'PRIMARY',
                'progression': 'PRIMARY',
                'residual_tumor': 'PRIMARY'
            }
        ),

        'measurements': ViewConfiguration(
            name='measurements',
            primary_key=['measurement_id'],
            date_columns=['measurement_date'],
            key_columns=[
                'measurement_id', 'measurement_name', 'value_numeric',
                'unit', 'reference_range'
            ],
            description='Clinical measurements and tumor dimensions',
            extraction_relevance={
                'tumor_volume': 'PRIMARY',
                'kps_score': 'PRIMARY',
                'lansky_score': 'PRIMARY'
            }
        ),

        'binary_files': ViewConfiguration(
            name='binary_files',
            primary_key=['file_id'],
            date_columns=['dr_date', 'document_date'],
            key_columns=[
                'file_id', 'file_name', 'document_type', 's3_path',
                'file_size', 'is_priority'
            ],
            description='References to binary documents in S3',
            extraction_relevance={
                'ALL': 'SOURCE_DOCUMENTS'
            }
        ),

        'encounters': ViewConfiguration(
            name='encounters',
            primary_key=['encounter_id'],
            date_columns=['encounter_date', 'admit_date', 'discharge_date'],
            key_columns=[
                'encounter_id', 'encounter_type', 'department',
                'provider_specialty', 'chief_complaint'
            ],
            description='Clinical encounters and visits',
            extraction_relevance={
                'hospitalization': 'PRIMARY',
                'follow_up': 'SECONDARY'
            }
        ),

        'appointments': ViewConfiguration(
            name='appointments',
            primary_key=['appointment_id'],
            date_columns=['appointment_date', 'scheduled_date'],
            key_columns=[
                'appointment_id', 'appointment_type', 'department',
                'provider', 'status'
            ],
            description='Scheduled and completed appointments',
            extraction_relevance={
                'follow_up_schedule': 'SECONDARY'
            }
        ),

        'radiation_treatment_courses': ViewConfiguration(
            name='radiation_treatment_courses',
            primary_key=['course_id'],
            date_columns=['start_date', 'end_date'],
            key_columns=[
                'course_id', 'treatment_site', 'total_dose_gy',
                'fractions', 'technique', 'intent'
            ],
            description='Radiation therapy courses and parameters',
            extraction_relevance={
                'radiation_therapy': 'PRIMARY',
                'radiation_dose': 'PRIMARY',
                'radiation_site': 'PRIMARY',
                'radiation_technique': 'PRIMARY'
            }
        ),

        'radiation_data_summary': ViewConfiguration(
            name='radiation_data_summary',
            primary_key=['summary_id'],
            date_columns=['treatment_date'],
            key_columns=[
                'summary_id', 'site', 'dose_per_fraction', 'total_dose',
                'boost', 'concurrent_chemo'
            ],
            description='Summarized radiation therapy data',
            extraction_relevance={
                'radiation_summary': 'PRIMARY'
            }
        )
    }

    # Materialized views combining multiple sources
    MATERIALIZED_VIEWS = {
        'surgery_events': {
            'description': 'Consolidated surgical events with classifications',
            'source_tables': ['procedures', 'encounters', 'binary_files'],
            'key_fields': [
                'surgery_date', 'surgery_type', 'extent_of_resection',
                'operative_note_id', 'pathology_report_id'
            ],
            'extraction_relevance': {
                'extent_of_resection': 'GOLD_STANDARD',
                'surgery_classification': 'PRIMARY'
            }
        },

        'chemotherapy_timeline': {
            'description': 'Longitudinal chemotherapy exposure timeline',
            'source_tables': ['medications', 'encounters'],
            'key_fields': [
                'drug_name', 'start_date', 'end_date', 'cumulative_dose',
                'line_of_therapy', 'response'
            ],
            'extraction_relevance': {
                'chemotherapy_lines': 'PRIMARY',
                'treatment_response': 'PRIMARY'
            }
        },

        'molecular_profile': {
            'description': 'Integrated molecular test results',
            'source_tables': ['measurements', 'binary_files'],
            'key_fields': [
                'test_date', 'test_type', 'gene', 'alteration',
                'variant_allele_frequency', 'clinical_significance'
            ],
            'extraction_relevance': {
                'molecular_alterations': 'PRIMARY',
                'targeted_therapy_eligibility': 'PRIMARY'
            }
        },

        'clinical_timeline': {
            'description': 'Complete patient clinical timeline',
            'source_tables': ['ALL'],
            'key_fields': [
                'event_date', 'event_type', 'event_category',
                'event_description', 'source_document'
            ],
            'extraction_relevance': {
                'ALL': 'CONTEXTUAL'
            }
        },

        'imaging_progression': {
            'description': 'Imaging-based progression events',
            'source_tables': ['imaging', 'measurements'],
            'key_fields': [
                'progression_date', 'progression_type', 'recist_criteria',
                'site_of_progression', 'prior_baseline'
            ],
            'extraction_relevance': {
                'progression_date': 'PRIMARY',
                'progression_site': 'PRIMARY',
                'recurrence': 'PRIMARY'
            }
        }
    }

    # Query functions available to LLM
    QUERY_FUNCTIONS = {
        'QUERY_SURGERY_DATES': {
            'description': 'Get all surgery dates for patient',
            'returns': 'List[Dict[date, type, extent]]',
            'source': 'procedures',
            'filters': ['is_surgical_keyword = true']
        },

        'QUERY_DIAGNOSIS': {
            'description': 'Get primary diagnosis and date',
            'returns': 'Dict[diagnosis, icd10_code, date]',
            'source': 'diagnoses',
            'filters': ['brain tumor codes: C71, D43, D33']
        },

        'QUERY_MEDICATIONS': {
            'description': 'Verify patient received specific medication',
            'parameters': ['drug_name'],
            'returns': 'List[Dict[medication, start_date, end_date]]',
            'source': 'medications'
        },

        'QUERY_MOLECULAR_TESTS': {
            'description': 'Get molecular test results',
            'returns': 'List[Dict[test, date, result]]',
            'source': 'molecular_profile'
        },

        'QUERY_IMAGING_ON_DATE': {
            'description': 'Get imaging near specific date',
            'parameters': ['date', 'tolerance_days'],
            'returns': 'List[Dict[study, findings, impression]]',
            'source': 'imaging'
        },

        'QUERY_POSTOP_IMAGING': {
            'description': 'Get post-operative imaging within 72 hours',
            'parameters': ['surgery_date'],
            'returns': 'Dict[extent, residual, complications]',
            'source': 'imaging',
            'filters': ['is_postop_72hr = true'],
            'critical': True
        },

        'QUERY_PROBLEM_LIST': {
            'description': 'Get active clinical problems',
            'returns': 'List[Dict[problem, status, onset_date]]',
            'source': 'diagnoses',
            'filters': ['status = active']
        },

        'QUERY_ENCOUNTERS_RANGE': {
            'description': 'Get encounters in date range',
            'parameters': ['start_date', 'end_date'],
            'returns': 'List[Dict[date, type, department]]',
            'source': 'encounters'
        },

        'VERIFY_DATE_PROXIMITY': {
            'description': 'Check if dates are within tolerance',
            'parameters': ['date1', 'date2', 'tolerance_days'],
            'returns': 'bool',
            'source': 'COMPUTED'
        },

        'QUERY_CHEMOTHERAPY_EXPOSURE': {
            'description': 'Check chemotherapy drugs received',
            'returns': 'List[Dict[drug, dates, line_of_therapy]]',
            'source': 'chemotherapy_timeline'
        },

        'QUERY_RADIATION_DETAILS': {
            'description': 'Get radiation therapy details',
            'returns': 'Dict[site, dose, fractions, technique]',
            'source': 'radiation_treatment_courses'
        }
    }

    @classmethod
    def get_view_config(cls, view_name: str) -> ViewConfiguration:
        """Get configuration for a specific view."""
        if view_name in cls.STAGING_VIEWS:
            return cls.STAGING_VIEWS[view_name]
        raise ValueError(f"Unknown view: {view_name}")

    @classmethod
    def get_date_columns(cls, view_name: str) -> List[str]:
        """Get date columns for a view."""
        config = cls.get_view_config(view_name)
        return config.date_columns

    @classmethod
    def get_primary_views_for_variable(cls, variable_name: str) -> List[str]:
        """Get views most relevant for extracting a specific variable."""
        relevant_views = []

        for view_name, config in cls.STAGING_VIEWS.items():
            if variable_name in config.extraction_relevance:
                relevance = config.extraction_relevance[variable_name]
                if relevance in ['PRIMARY', 'CRITICAL', 'GOLD_STANDARD']:
                    relevant_views.append(view_name)

        return relevant_views

    @classmethod
    def get_critical_validations(cls) -> Dict[str, str]:
        """Get critical validation requirements."""
        return {
            'extent_of_resection': 'QUERY_POSTOP_IMAGING',
            'chemotherapy_drugs': 'QUERY_CHEMOTHERAPY_EXPOSURE',
            'molecular_alterations': 'QUERY_MOLECULAR_TESTS',
            'progression_date': 'QUERY_IMAGING_ON_DATE',
            'radiation_dose': 'QUERY_RADIATION_DETAILS'
        }

    @classmethod
    def get_staging_schema(cls) -> Dict[str, Any]:
        """Get complete schema for all staging views."""
        schema = {}
        for view_name, config in cls.STAGING_VIEWS.items():
            schema[view_name] = {
                'primary_key': config.primary_key,
                'date_columns': config.date_columns,
                'key_columns': config.key_columns,
                'description': config.description
            }
        return schema

# Configuration for form-specific extraction requirements
FORM_EXTRACTION_CONFIG = {
    'diagnosis_form': {
        'required_views': ['diagnoses', 'imaging', 'binary_files'],
        'required_queries': ['QUERY_DIAGNOSIS', 'QUERY_MOLECULAR_TESTS'],
        'variables': [
            'who_cns5_diagnosis', 'tumor_grade', 'tumor_location',
            'metastasis', 'molecular_alterations'
        ]
    },

    'treatment_form': {
        'required_views': ['procedures', 'imaging', 'binary_files'],
        'required_queries': ['QUERY_SURGERY_DATES', 'QUERY_POSTOP_IMAGING'],
        'critical_validation': 'extent_of_resection',
        'variables': [
            'extent_of_resection', 'surgery_date', 'surgery_type',
            'residual_tumor', 'complications'
        ]
    },

    'chemotherapy_form': {
        'required_views': ['medications', 'chemotherapy_timeline'],
        'required_queries': ['QUERY_CHEMOTHERAPY_EXPOSURE', 'QUERY_MEDICATIONS'],
        'variables': [
            'chemotherapy_drugs', 'start_date', 'end_date',
            'best_response', 'toxicity'
        ]
    },

    'radiation_form': {
        'required_views': ['radiation_treatment_courses', 'radiation_data_summary'],
        'required_queries': ['QUERY_RADIATION_DETAILS'],
        'variables': [
            'radiation_site', 'total_dose', 'fractions',
            'technique', 'concurrent_chemo'
        ]
    },

    'demographics_form': {
        'required_views': ['encounters', 'diagnoses'],
        'variables': [
            'legal_sex', 'race', 'ethnicity', 'vital_status'
        ]
    },

    'medical_history_form': {
        'required_views': ['diagnoses', 'measurements', 'molecular_profile'],
        'required_queries': ['QUERY_PROBLEM_LIST', 'QUERY_MOLECULAR_TESTS'],
        'variables': [
            'family_history', 'cancer_predisposition',
            'germline_testing', 'comorbidities'
        ]
    },

    'concomitant_medications_form': {
        'required_views': ['medications'],
        'required_queries': ['QUERY_MEDICATIONS'],
        'variables': [
            'medication_name', 'start_date', 'end_date',
            'indication', 'route'
        ]
    },

    'imaging_form': {
        'required_views': ['imaging', 'imaging_progression', 'measurements'],
        'required_queries': ['QUERY_IMAGING_ON_DATE'],
        'variables': [
            'imaging_date', 'modality', 'tumor_size',
            'progression_status', 'new_lesions'
        ]
    },

    'outcome_form': {
        'required_views': ['encounters', 'diagnoses', 'imaging_progression'],
        'variables': [
            'vital_status', 'date_of_death', 'cause_of_death',
            'progression_free_survival', 'overall_survival'
        ]
    }
}

def get_required_staging_files(forms: List[str]) -> List[str]:
    """Get all required staging files for specified forms."""
    required_views = set()

    for form in forms:
        if form in FORM_EXTRACTION_CONFIG:
            config = FORM_EXTRACTION_CONFIG[form]
            required_views.update(config['required_views'])

    return list(required_views)

def get_critical_queries(form: str) -> List[str]:
    """Get critical query functions for a form."""
    if form in FORM_EXTRACTION_CONFIG:
        return FORM_EXTRACTION_CONFIG[form].get('required_queries', [])
    return []

def validate_staging_directory(patient_dir: str) -> Dict[str, bool]:
    """Validate that all required staging files exist."""
    from pathlib import Path

    patient_path = Path(patient_dir)
    validation = {}

    for view_name in StagingViewsConfiguration.STAGING_VIEWS:
        file_path = patient_path / f"{view_name}.csv"
        validation[view_name] = file_path.exists()

    return validation