"""
Master Orchestrator Agent
==========================
Coordinates multi-agent data abstraction workflow.
Enforces data dictionary constraints and manages agent dialogue.

Author: RADIANT PCA Project
Date: October 17, 2025
Branch: feature/multi-agent-framework
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
from enum import Enum

from .athena_query_agent import AthenaQueryAgent


class FieldCategory(Enum):
    """Field classification categories"""
    STRUCTURED_ONLY = "structured_only"  # Direct Athena query
    HYBRID = "hybrid"  # Athena validation + document extraction
    DOCUMENT_ONLY = "document_only"  # Document extraction only


class ExtractionStrategy(Enum):
    """Extraction strategies per field category"""
    DIRECT_QUERY = "direct_query"  # Query Athena and return
    QUERY_THEN_EXTRACT = "query_then_extract"  # Validate with Athena, extract from docs
    DOCUMENT_EXTRACTION = "document_extraction"  # Extract from documents only


class MasterOrchestrator:
    """
    Master Orchestrator Agent (Claude Sonnet 4.5)

    Responsibilities:
    - Classifies fields into STRUCTURED_ONLY, HYBRID, DOCUMENT_ONLY
    - Plans extraction strategy per field
    - Coordinates Athena Query Agent + Medical Reasoning Agent
    - Adjudicates conflicts between sources
    - Validates against data dictionary constraints
    - Produces final abstracted output with confidence scores
    """

    def __init__(
        self,
        athena_agent: AthenaQueryAgent,
        data_dictionary: Optional[Dict[str, Any]] = None,
        field_mappings: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Master Orchestrator.

        Args:
            athena_agent: AthenaQueryAgent instance
            data_dictionary: CBTN data dictionary (345 fields)
            field_mappings: Field → Athena view mappings
        """
        self.athena_agent = athena_agent
        self.data_dictionary = data_dictionary or {}
        self.field_mappings = field_mappings or self._default_field_mappings()

        # Dialogue history for audit trail
        self.dialogue_history = []

        # Extraction results cache
        self.extraction_cache = {}

    def _default_field_mappings(self) -> Dict[str, Any]:
        """
        Default field mappings for CBTN data dictionary.
        Maps field names to Athena views and extraction strategies.
        """
        return {
            # ==========================================================================
            # STRUCTURED_ONLY FIELDS (30% - Direct Athena query)
            # ==========================================================================
            'patient_gender': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'demographics',
                'athena_column': 'pd_gender',
                'confidence': 1.0
            },
            'date_of_birth': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'demographics',
                'athena_column': 'pd_birth_date',
                'confidence': 1.0
            },
            'race': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'demographics',
                'athena_column': 'pd_race',
                'confidence': 1.0
            },
            'ethnicity': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'demographics',
                'athena_column': 'pd_ethnicity',
                'confidence': 1.0
            },
            'chemotherapy_agent': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'medications',
                'athena_column': 'medication_name',
                'confidence': 1.0,
                'scope': 'many_per_patient'  # Multiple medications
            },
            'chemotherapy_start_date': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'medications',
                'athena_column': 'medication_start_date',
                'confidence': 1.0,
                'scope': 'many_per_patient'
            },
            'chemotherapy_status': {
                'category': FieldCategory.STRUCTURED_ONLY,
                'strategy': ExtractionStrategy.DIRECT_QUERY,
                'athena_view': 'medications',
                'athena_column': 'mr_status',
                'confidence': 1.0,
                'scope': 'many_per_patient'
            },

            # ==========================================================================
            # HYBRID FIELDS (50% - Athena validation + document extraction)
            # ==========================================================================
            'primary_diagnosis': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'diagnoses',
                'athena_columns': ['pld_diagnosis_name', 'pld_icd10_code', 'pld_snomed_code'],
                'document_types': ['pathology_report', 'clinical_note'],
                'validation_rules': {
                    'icd10_match': True,
                    'snomed_match': True
                },
                'confidence_calculation': {
                    'pathology_report': 0.95,
                    'icd10_match': 0.85,
                    'problem_list_only': 0.70
                }
            },
            'diagnosis_date': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'diagnoses',
                'athena_columns': ['pld_onset_date', 'pld_recorded_date'],
                'document_types': ['pathology_report', 'clinical_note', 'operative_note'],
                'validation_rules': {
                    'date_proximity': 30  # days tolerance
                },
                'confidence_calculation': {
                    'athena_validated_document': 0.90,
                    'document_only': 0.70
                }
            },
            'who_grade': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'diagnoses',
                'athena_columns': ['pld_diagnosis_name'],  # Grade may be in diagnosis name
                'document_types': ['pathology_report'],
                'validation_rules': {
                    'dropdown_match': ['1', '2', '3', '4', 'No grade specified']
                },
                'confidence_calculation': {
                    'pathology_report': 0.95,
                    'clinical_note': 0.80
                }
            },
            'tumor_location': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'procedures',
                'athena_columns': ['pbs_body_site_text'],
                'document_types': ['operative_note', 'imaging_report', 'pathology_report'],
                'validation_rules': {
                    'dropdown_match': [
                        'Frontal Lobe', 'Parietal Lobe', 'Temporal Lobe', 'Occipital Lobe',
                        'Cerebellum', 'Brain Stem', 'Pituitary', 'Pineal', 'Ventricles',
                        'Corpus Callosum', 'Thalamus', 'Hypothalamus', 'Basal Ganglia',
                        'Spinal Cord', 'Optic Pathway', 'Cerebellopontine Angle',
                        'Supratentorial', 'Infratentorial', 'Intraventricular',
                        'Posterior Fossa', 'Multifocal', 'Other', 'Unknown', 'Not Reported'
                    ]
                },
                'confidence_calculation': {
                    'operative_note': 0.95,
                    'imaging_report': 0.90,
                    'body_site_match': 0.85
                }
            },
            'extent_of_resection': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'procedures',
                'athena_columns': ['procedure_date', 'is_surgical_keyword'],
                'document_types': ['operative_note', 'pathology_report'],
                'validation_rules': {
                    'date_proximity': 7,  # days
                    'dropdown_match': [
                        'Gross total resection',
                        'Near total resection',
                        'Subtotal resection',
                        'Partial resection',
                        'Biopsy only'
                    ]
                },
                'confidence_calculation': {
                    'athena_validated_document': 0.95,
                    'document_only': 0.70,
                    'conflict': 0.40
                },
                'scope': 'many_per_patient'  # Multiple surgeries
            },
            'surgery_date': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'procedures',
                'athena_columns': ['procedure_date', 'is_surgical_keyword'],
                'document_types': ['operative_note'],
                'validation_rules': {
                    'date_proximity': 0  # Exact match expected
                },
                'confidence_calculation': {
                    'exact_match': 0.95,
                    'within_7_days': 0.80
                },
                'scope': 'many_per_patient'
            },
            'surgery_type': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'procedures',
                'athena_columns': ['proc_code_text', 'procedure_date'],
                'document_types': ['operative_note', 'clinical_note'],
                'validation_rules': {
                    'dropdown_match': [
                        'Initial CNS Tumor Surgery',
                        'Second Malignancy Surgery',
                        'Progressive',
                        'Recurrence',
                        'Deceased'
                    ]
                },
                'confidence_calculation': {
                    'operative_note': 0.90,
                    'clinical_note': 0.75
                },
                'scope': 'many_per_patient'
            },
            'radiation_dose': {
                'category': FieldCategory.HYBRID,
                'strategy': ExtractionStrategy.QUERY_THEN_EXTRACT,
                'athena_view': 'radiation_courses',
                'athena_columns': ['sr_quantity_value', 'sr_quantity_unit'],
                'document_types': ['radiation_oncology_note', 'treatment_plan'],
                'validation_rules': {
                    'numeric_tolerance': 0.1  # 10% tolerance
                },
                'confidence_calculation': {
                    'athena_validated_document': 0.90,
                    'document_only': 0.70
                }
            },

            # ==========================================================================
            # DOCUMENT_ONLY FIELDS (20% - Free-text extraction)
            # ==========================================================================
            'clinical_status': {
                'category': FieldCategory.DOCUMENT_ONLY,
                'strategy': ExtractionStrategy.DOCUMENT_EXTRACTION,
                'document_types': ['progress_note', 'oncology_note'],
                'extraction_instruction': 'Extract disease status: Stable/Progressive/Recurrent/No Evidence of Disease',
                'validation_rules': {
                    'dropdown_match': ['Stable', 'Progressive', 'Recurrent', 'No Evidence of Disease', 'Unknown']
                },
                'confidence': 0.75,
                'scope': 'many_per_patient'  # Longitudinal tracking
            },
            'imaging_findings': {
                'category': FieldCategory.DOCUMENT_ONLY,
                'strategy': ExtractionStrategy.DOCUMENT_EXTRACTION,
                'document_types': ['radiology_report'],
                'extraction_instruction': 'Extract impression section (max 500 characters)',
                'confidence': 0.70,
                'scope': 'many_per_patient'
            },
            'tumor_size': {
                'category': FieldCategory.DOCUMENT_ONLY,
                'strategy': ExtractionStrategy.DOCUMENT_EXTRACTION,
                'document_types': ['radiology_report', 'pathology_report'],
                'extraction_instruction': 'Extract tumor dimensions in cm (e.g., "3.5 x 2.1 x 2.8 cm")',
                'confidence': 0.75,
                'scope': 'many_per_patient'
            },
            'pathology_notes': {
                'category': FieldCategory.DOCUMENT_ONLY,
                'strategy': ExtractionStrategy.DOCUMENT_EXTRACTION,
                'document_types': ['pathology_report'],
                'extraction_instruction': 'Extract pathology findings narrative',
                'confidence': 0.70
            }
        }

    def classify_field(self, field_name: str) -> Tuple[FieldCategory, Dict[str, Any]]:
        """
        Classify field into STRUCTURED_ONLY, HYBRID, or DOCUMENT_ONLY.

        Args:
            field_name: Field name from data dictionary

        Returns:
            Tuple of (FieldCategory, field_config)
        """
        if field_name not in self.field_mappings:
            # Default to DOCUMENT_ONLY if unknown
            return FieldCategory.DOCUMENT_ONLY, {
                'strategy': ExtractionStrategy.DOCUMENT_EXTRACTION,
                'confidence': 0.60
            }

        field_config = self.field_mappings[field_name]
        category = field_config['category']

        self._log_dialogue(
            agent='MasterOrchestrator',
            action='classify_field',
            message=f"Field '{field_name}' classified as {category.value}"
        )

        return category, field_config

    def extract_field(
        self,
        patient_fhir_id: str,
        field_name: str,
        field_definition: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract a single field for a patient.

        Args:
            patient_fhir_id: Patient FHIR ID
            field_name: Field name to extract
            field_definition: Optional field definition from data dictionary

        Returns:
            Dict containing extraction result with confidence score
        """
        # Check cache
        cache_key = f"{patient_fhir_id}_{field_name}"
        if cache_key in self.extraction_cache:
            return self.extraction_cache[cache_key]

        # Classify field
        category, field_config = self.classify_field(field_name)

        # Execute extraction strategy
        if category == FieldCategory.STRUCTURED_ONLY:
            result = self._extract_structured_field(patient_fhir_id, field_name, field_config)
        elif category == FieldCategory.HYBRID:
            result = self._extract_hybrid_field(patient_fhir_id, field_name, field_config)
        else:  # DOCUMENT_ONLY
            result = self._extract_document_field(patient_fhir_id, field_name, field_config)

        # Cache result
        self.extraction_cache[cache_key] = result

        return result

    def _extract_structured_field(
        self,
        patient_fhir_id: str,
        field_name: str,
        field_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract STRUCTURED_ONLY field directly from Athena.

        Args:
            patient_fhir_id: Patient FHIR ID
            field_name: Field name
            field_config: Field configuration

        Returns:
            Extraction result with confidence 1.0
        """
        self._log_dialogue(
            agent='MasterOrchestrator',
            action='extract_structured_field',
            message=f"Querying Athena for '{field_name}'"
        )

        view_name = field_config['athena_view']
        column_name = field_config['athena_column']

        # Query Athena
        if view_name == 'demographics':
            data = self.athena_agent.query_patient_demographics(patient_fhir_id)
        elif view_name == 'diagnoses':
            data = self.athena_agent.query_diagnoses(patient_fhir_id)
        elif view_name == 'procedures':
            data = self.athena_agent.query_procedures(patient_fhir_id)
        elif view_name == 'medications':
            # Special handling for chemotherapy agents - use filtered query
            if field_name == 'chemotherapy_agent':
                data = self.athena_agent.query_chemotherapy_medications(patient_fhir_id)
            else:
                data = self.athena_agent.query_medications(patient_fhir_id)
        else:
            data = None

        # Extract value
        if data is None:
            value = None
            confidence = 0.0
            status = 'no_data'
        elif isinstance(data, list):
            # Many per patient (e.g., medications, procedures)
            value = [item.get(column_name) for item in data if column_name in item]
            confidence = 1.0 if value else 0.0
            status = 'structured' if value else 'no_data'
        else:
            # Single value (e.g., demographics)
            value = data.get(column_name)
            confidence = 1.0 if value else 0.0
            status = 'structured' if value else 'no_data'

        self._log_dialogue(
            agent='AthenaQueryAgent',
            action='query_result',
            message=f"Retrieved {field_name}: {value}"
        )

        return {
            'field': field_name,
            'value': value,
            'confidence': confidence,
            'source': f'athena.{view_name}.{column_name}',
            'validation_status': status,
            'category': 'STRUCTURED_ONLY'
        }

    def _extract_hybrid_field(
        self,
        patient_fhir_id: str,
        field_name: str,
        field_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract HYBRID field using Athena validation + document extraction.

        Args:
            patient_fhir_id: Patient FHIR ID
            field_name: Field name
            field_config: Field configuration

        Returns:
            Extraction result with validation-based confidence
        """
        self._log_dialogue(
            agent='MasterOrchestrator',
            action='extract_hybrid_field',
            message=f"Using HYBRID strategy for '{field_name}'"
        )

        # Step 1: Query Athena for validation data
        view_name = field_config['athena_view']
        columns = field_config['athena_columns']

        if view_name == 'procedures':
            validation_data = self.athena_agent.query_procedures(patient_fhir_id)
        elif view_name == 'diagnoses':
            validation_data = self.athena_agent.query_diagnoses(patient_fhir_id)
        elif view_name == 'radiation_courses':
            validation_data = self.athena_agent.query_radiation_courses(patient_fhir_id)
        else:
            validation_data = []

        self._log_dialogue(
            agent='AthenaQueryAgent',
            action='validation_query',
            message=f"Found {len(validation_data)} records in {view_name}"
        )

        # Step 2: Extract from documents (placeholder - needs Medical Reasoning Agent)
        # For now, return Athena data as fallback
        document_extraction = {
            'value': None,
            'source_doc': None,
            'extraction_method': 'needs_medical_reasoning_agent'
        }

        # Step 3: Cross-validate (placeholder)
        validation_result = self._validate_extraction(
            athena_data=validation_data,
            document_data=document_extraction,
            validation_rules=field_config.get('validation_rules', {})
        )

        # Step 4: Calculate confidence
        confidence_rules = field_config.get('confidence_calculation', {})
        if validation_result['status'] == 'validated':
            confidence = confidence_rules.get('athena_validated_document', 0.95)
        elif validation_result['status'] == 'partial_match':
            confidence = confidence_rules.get('document_only', 0.70)
        else:
            confidence = confidence_rules.get('conflict', 0.40)

        return {
            'field': field_name,
            'value': validation_data if validation_data else None,
            'confidence': confidence,
            'athena_source': f'{view_name}.{columns}',
            'document_source': document_extraction['source_doc'],
            'validation_status': validation_result['status'],
            'category': 'HYBRID',
            'needs_implementation': 'medical_reasoning_agent'
        }

    def _extract_document_field(
        self,
        patient_fhir_id: str,
        field_name: str,
        field_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract DOCUMENT_ONLY field from clinical documents.

        Args:
            patient_fhir_id: Patient FHIR ID
            field_name: Field name
            field_config: Field configuration

        Returns:
            Extraction result (placeholder - needs Medical Reasoning Agent)
        """
        self._log_dialogue(
            agent='MasterOrchestrator',
            action='extract_document_field',
            message=f"Using DOCUMENT_ONLY strategy for '{field_name}'"
        )

        # Placeholder - needs Medical Reasoning Agent implementation
        return {
            'field': field_name,
            'value': None,
            'confidence': field_config.get('confidence', 0.70),
            'source': 'document_extraction',
            'validation_status': 'no_validation_available',
            'category': 'DOCUMENT_ONLY',
            'needs_implementation': 'medical_reasoning_agent'
        }

    def _validate_extraction(
        self,
        athena_data: List[Dict[str, Any]],
        document_data: Dict[str, Any],
        validation_rules: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Cross-validate Athena data vs. document extraction.

        Args:
            athena_data: Data from Athena query
            document_data: Data extracted from documents
            validation_rules: Validation rules to apply

        Returns:
            Validation result
        """
        # Placeholder validation logic
        if athena_data and document_data.get('value'):
            return {'status': 'validated'}
        elif athena_data or document_data.get('value'):
            return {'status': 'partial_match'}
        else:
            return {'status': 'no_data'}

    def extract_all_fields(
        self,
        patient_fhir_id: str,
        field_list: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract all fields for a patient.

        Args:
            patient_fhir_id: Patient FHIR ID
            field_list: Optional list of field names to extract (default: all)

        Returns:
            Dict containing all extractions
        """
        if field_list is None:
            field_list = list(self.field_mappings.keys())

        results = {}
        for field_name in field_list:
            results[field_name] = self.extract_field(patient_fhir_id, field_name)

        return {
            'patient_fhir_id': patient_fhir_id,
            'extraction_timestamp': datetime.now().isoformat(),
            'fields_extracted': len(results),
            'results': results,
            'dialogue_history': self.dialogue_history
        }

    def _log_dialogue(self, agent: str, action: str, message: str):
        """Log agent dialogue for audit trail."""
        self.dialogue_history.append({
            'timestamp': datetime.now().isoformat(),
            'agent': agent,
            'action': action,
            'message': message
        })

    def get_extraction_summary(self, patient_fhir_id: str) -> Dict[str, Any]:
        """
        Get summary of extractions for a patient.

        Args:
            patient_fhir_id: Patient FHIR ID

        Returns:
            Summary statistics
        """
        extractions = {k: v for k, v in self.extraction_cache.items() if k.startswith(patient_fhir_id)}

        high_confidence = sum(1 for v in extractions.values() if v['confidence'] >= 0.85)
        medium_confidence = sum(1 for v in extractions.values() if 0.60 <= v['confidence'] < 0.85)
        low_confidence = sum(1 for v in extractions.values() if v['confidence'] < 0.60)

        return {
            'patient_fhir_id': patient_fhir_id,
            'total_fields': len(extractions),
            'high_confidence': high_confidence,
            'medium_confidence': medium_confidence,
            'low_confidence': low_confidence,
            'confidence_distribution': {
                'high (0.85-1.0)': f"{high_confidence / len(extractions) * 100:.1f}%" if extractions else "0%",
                'medium (0.60-0.84)': f"{medium_confidence / len(extractions) * 100:.1f}%" if extractions else "0%",
                'low (< 0.60)': f"{low_confidence / len(extractions) * 100:.1f}%" if extractions else "0%"
            }
        }


# ==================================================================================
# EXAMPLE USAGE
# ==================================================================================

if __name__ == '__main__':
    # Initialize agents
    athena_agent = AthenaQueryAgent(
        database='fhir_prd_db',
        output_location='s3://your-athena-results-bucket/',
        region='us-east-1'
    )

    orchestrator = MasterOrchestrator(athena_agent=athena_agent)

    # Test patient
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Extract STRUCTURED_ONLY field
    print("=== STRUCTURED_ONLY: patient_gender ===")
    gender = orchestrator.extract_field(patient_id, 'patient_gender')
    print(json.dumps(gender, indent=2))

    # Extract HYBRID field
    print("\n=== HYBRID: extent_of_resection ===")
    resection = orchestrator.extract_field(patient_id, 'extent_of_resection')
    print(json.dumps(resection, indent=2))

    # Extract all fields
    print("\n=== EXTRACT ALL FIELDS ===")
    test_fields = ['patient_gender', 'date_of_birth', 'race', 'ethnicity', 'chemotherapy_agent']
    all_results = orchestrator.extract_all_fields(patient_id, field_list=test_fields)
    print(json.dumps(all_results, indent=2))

    # Get summary
    print("\n=== EXTRACTION SUMMARY ===")
    summary = orchestrator.get_extraction_summary(patient_id)
    print(json.dumps(summary, indent=2))
