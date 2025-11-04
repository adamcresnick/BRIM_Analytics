"""
Clinical Event Data Models for Patient Timeline Abstraction

This module provides standardized dataclass-based event models for the Patient Timeline
Abstraction workflow, replacing the previous dictionary-based approach.

Version: V4.2
Created: 2025-11-03
Author: RADIANT PCA Engineering Team

Key Features:
- Type-safe event models with validation
- Standardized field naming across event types
- Support for V4.1 clinical features (location, institution)
- Support for V2 cross-resource annotation
- Support for V4.2 tumor measurements and treatment response
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from enum import Enum


class EventType(Enum):
    """Enumeration of supported clinical event types"""
    DIAGNOSIS = "diagnosis"
    SURGERY = "surgery"
    CHEMOTHERAPY = "chemotherapy"
    RADIATION = "radiation"
    IMAGING = "imaging"
    PATHOLOGY = "pathology"
    TREATMENT = "treatment"
    MOLECULAR_TEST = "molecular_test"
    CLINICAL_ASSESSMENT = "clinical_assessment"


class ImagingModality(Enum):
    """Standard imaging modality types"""
    MRI = "MRI"
    CT = "CT"
    PET = "PET"
    XRAY = "X-ray"
    ULTRASOUND = "Ultrasound"
    OTHER = "Other"


class TreatmentCategory(Enum):
    """Treatment response assessment categories"""
    COMPLETE_RESPONSE = "CR"        # Complete Response
    PARTIAL_RESPONSE = "PR"         # Partial Response
    STABLE_DISEASE = "SD"           # Stable Disease
    PROGRESSIVE_DISEASE = "PD"      # Progressive Disease
    NOT_EVALUABLE = "NE"            # Not Evaluable
    IMPROVED = "improved"           # Qualitative improved
    STABLE = "stable"               # Qualitative stable
    WORSE = "worse"                 # Qualitative worse


# ============================================================================
# TUMOR MEASUREMENT MODELS (V4.2)
# ============================================================================

@dataclass
class TumorMeasurement:
    """
    Represents a single tumor measurement from imaging or clinical assessment

    Supports three measurement types:
    1. Bidimensional (RANO standard): longest × perpendicular diameter
    2. Volumetric: total volume in mm³
    3. Qualitative: descriptive assessment

    V4.2 Enhancement - Foundation for V5.0 RANO criteria
    """
    # REQUIRED FIELDS
    lesion_id: str                          # Unique identifier for this lesion (e.g., "target_1", "non_target_1")
    location: str                           # Anatomical location
    measurement_type: str                   # "bidimensional", "volumetric", "qualitative"

    # BIDIMENSIONAL MEASUREMENTS (RANO standard)
    longest_diameter_mm: Optional[float] = None
    perpendicular_diameter_mm: Optional[float] = None
    cross_sectional_area_mm2: Optional[float] = None  # Auto-calculated in to_dict()

    # VOLUMETRIC MEASUREMENTS
    volume_mm3: Optional[float] = None

    # QUALITATIVE ASSESSMENT
    qualitative_assessment: Optional[str] = None  # "stable", "increased", "decreased", "new lesion", "present", "absent"

    # METADATA
    extracted_from_text: Optional[str] = None     # Source text from which measurement was extracted
    confidence: str = "HIGH"                      # Extraction confidence: HIGH, MEDIUM, LOW
    extraction_method: str = "llm_extraction"     # "structured_fhir", "llm_extraction", "manual"
    source_id: Optional[str] = None               # FHIR resource ID
    extracted_at: Optional[str] = None            # ISO 8601 timestamp of extraction

    def validate(self) -> List[str]:
        """
        Validate measurement consistency

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate measurement_type
        if self.measurement_type not in ["bidimensional", "volumetric", "qualitative"]:
            errors.append(f"Invalid measurement_type: {self.measurement_type}")

        # Type-specific validation
        if self.measurement_type == "bidimensional":
            if not self.longest_diameter_mm or not self.perpendicular_diameter_mm:
                errors.append("Bidimensional measurements require both diameters")
            elif self.longest_diameter_mm < self.perpendicular_diameter_mm:
                errors.append("Longest diameter must be >= perpendicular diameter")

        elif self.measurement_type == "volumetric":
            if not self.volume_mm3:
                errors.append("Volumetric measurements require volume_mm3")

        elif self.measurement_type == "qualitative":
            if not self.qualitative_assessment:
                errors.append("Qualitative measurements require qualitative_assessment")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary, excluding None values
        Auto-calculates cross_sectional_area_mm2 if bidimensional diameters present
        """
        result = {k: v for k, v in asdict(self).items() if v is not None}

        # Auto-calculate cross-sectional area for bidimensional measurements
        if (self.measurement_type == "bidimensional" and
            self.longest_diameter_mm is not None and
            self.perpendicular_diameter_mm is not None):
            result['cross_sectional_area_mm2'] = (
                self.longest_diameter_mm * self.perpendicular_diameter_mm
            )

        return result


@dataclass
class TreatmentResponse:
    """
    Represents treatment response assessment

    V4.2 Enhancement - Basic qualitative response tracking
    V5.0 will add full RANO criteria support

    Supports both simplified qualitative assessment (V4.2) and
    full RANO classification with measurements (V5.0).
    """
    # REQUIRED FIELDS
    response_category: str                  # TreatmentCategory enum value ("CR", "PR", "SD", "PD" or "improved", "stable", "worse")
    assessment_method: str                  # "rano_criteria", "qualitative", "investigator_assessment"

    # RANO CRITERIA FIELDS (V5.0)
    sum_of_products: Optional[float] = None         # Sum of cross-sectional areas (mm²)
    percent_change: Optional[float] = None          # % change from baseline or nadir
    new_lesions: Optional[bool] = None              # New lesions detected

    # CONTEXT FIELDS
    baseline_study_id: Optional[str] = None         # Reference imaging study FHIR ID
    prior_study_id: Optional[str] = None            # Comparison imaging study FHIR ID
    days_since_treatment_start: Optional[int] = None  # Days since most recent treatment

    # QUALITATIVE FIELDS (V4.2 - if measurements unavailable)
    qualitative_description: Optional[str] = None   # Free-text description from report
    clinical_context: Optional[str] = None          # "post-surgery", "during-chemo", "post-radiation"

    # METADATA
    confidence: str = "MEDIUM"                      # Extraction confidence: HIGH, MEDIUM, LOW
    extraction_method: str = "llm_extraction"       # "rano_criteria", "llm_extraction", "structured_fhir"
    source_id: Optional[str] = None                 # FHIR resource ID
    extracted_from_text: Optional[str] = None       # Source text snippet
    extracted_at: Optional[str] = None              # ISO 8601 timestamp of extraction

    def validate(self) -> List[str]:
        """Validate response assessment"""
        errors = []

        # Validate response_category
        valid_categories = [cat.value for cat in TreatmentCategory]
        if self.response_category not in valid_categories:
            errors.append(f"Invalid response_category: {self.response_category}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


# ============================================================================
# CLINICAL EVENT BASE CLASS AND HIERARCHY (V4.2)
# ============================================================================

@dataclass
class ClinicalEvent:
    """
    Base class for all timeline events

    Standardizes core fields across all event types while allowing
    type-specific extensions via optional fields.

    V4.2 Enhancement - Replaces dictionary-based events
    """
    # REQUIRED FIELDS (all events must have these)
    event_type: str                                 # EventType enum value
    event_date: str                                 # ISO 8601 date string (YYYY-MM-DD)
    stage: int                                      # Pipeline stage number (0-6)
    source: str                                     # Source view/table name

    # OPTIONAL COMMON FIELDS
    description: Optional[str] = None

    # V4.1 CLINICAL FEATURES
    clinical_features: Optional[Dict[str, Any]] = None  # institution, tumor_location

    # V2 CROSS-RESOURCE ANNOTATION
    v2_annotation: Optional[Dict[str, Any]] = None      # specimen_id, encounter_id, etc.

    # V4.2 TUMOR MEASUREMENTS (for imaging/pathology events)
    tumor_measurements: Optional[List[Dict[str, Any]]] = None

    # V4.2 TREATMENT RESPONSE (for imaging events)
    treatment_response: Optional[Dict[str, Any]] = None

    # EVENT-TYPE SPECIFIC FIELDS
    # Surgery events
    surgery_type: Optional[str] = None
    surgery_number: Optional[int] = None                    # V4: Treatment ordinality (surgery #1, #2, etc.)
    surgery_label: Optional[str] = None                     # V4: e.g., "Initial resection (surgery #1)"
    proc_performed_datetime: Optional[str] = None
    extent_of_resection: Optional[str] = None               # Simple string: "GTR", "STR", "BIOPSY"
    extent_of_resection_v4: Optional[Dict[str, Any]] = None # V4: FeatureObject with multi-source provenance

    # Chemotherapy events
    chemotherapy: Optional[str] = None                      # Legacy field
    line_number: Optional[int] = None                       # V4: Treatment line #
    treatment_intent: Optional[str] = None
    regimen_summary: Optional[str] = None
    drug_list: Optional[List[str]] = None

    # Radiation events
    radiation_type: Optional[str] = None                    # Legacy field
    course_number: Optional[int] = None                     # V4: Radiation course #
    total_dose: Optional[float] = None
    dose_unit: Optional[str] = None
    fractions: Optional[int] = None

    # Imaging events
    imaging_modality: Optional[str] = None
    report_conclusion: Optional[str] = None
    result_information: Optional[str] = None                # V2: Preferred field (not report_conclusion)
    result_diagnostic_report_id: Optional[str] = None       # V2: Binary content ID
    diagnostic_report_id: Optional[str] = None

    # Pathology events
    specimen_type: Optional[str] = None
    collection_method: Optional[str] = None

    # Treatment events (general)
    treatment_type: Optional[str] = None
    treatment_agent: Optional[str] = None

    # Molecular test events
    test_name: Optional[str] = None
    result_value: Optional[str] = None

    # Diagnosis events
    diagnosis_code: Optional[str] = None
    diagnosis_text: Optional[str] = None
    who_2021_classification: Optional[Dict[str, Any]] = None  # V4: WHO classification result

    def validate(self) -> List[str]:
        """
        Validate event consistency

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate event_type
        valid_types = [et.value for et in EventType]
        if self.event_type not in valid_types:
            errors.append(f"Invalid event_type: {self.event_type}")

        # Validate stage
        if not 0 <= self.stage <= 6:
            errors.append(f"Invalid stage: {self.stage} (must be 0-6)")

        # Validate event_date format
        try:
            datetime.fromisoformat(self.event_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            errors.append(f"Invalid event_date format: {self.event_date} (must be ISO 8601)")

        # Type-specific validation
        if self.event_type == EventType.SURGERY.value:
            if not self.surgery_type:
                errors.append("Surgery events require surgery_type")

        elif self.event_type == EventType.IMAGING.value:
            if not self.imaging_modality:
                errors.append("Imaging events require imaging_modality")

        elif self.event_type == EventType.PATHOLOGY.value:
            if not self.specimen_type:
                errors.append("Pathology events require specimen_type")

        elif self.event_type == "chemotherapy":
            # Chemotherapy events should have line_number (V4 ordinality)
            if self.line_number is not None and self.line_number < 1:
                errors.append("line_number must be >= 1")

        elif self.event_type == "radiation":
            # Radiation events should have course_number (V4 ordinality)
            if self.course_number is not None and self.course_number < 1:
                errors.append("course_number must be >= 1")

        # Validate tumor measurements if present
        if self.tumor_measurements:
            for idx, tm_dict in enumerate(self.tumor_measurements):
                tm = TumorMeasurement(**tm_dict)
                tm_errors = tm.validate()
                if tm_errors:
                    errors.extend([f"Measurement {idx}: {err}" for err in tm_errors])

        # Validate treatment response if present
        if self.treatment_response:
            tr = TreatmentResponse(**self.treatment_response)
            tr_errors = tr.validate()
            if tr_errors:
                errors.extend([f"Response: {err}" for err in tr_errors])

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary, excluding None values

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClinicalEvent':
        """
        Create ClinicalEvent from dictionary

        Args:
            data: Dictionary with event fields

        Returns:
            ClinicalEvent instance
        """
        return cls(**data)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_surgery_event(
    event_date: str,
    surgery_type: str,
    source: str = "v_procedures_tumor",
    description: Optional[str] = None,
    clinical_features: Optional[Dict[str, Any]] = None,
    v2_annotation: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ClinicalEvent:
    """
    Factory function to create standardized surgery events

    Args:
        event_date: ISO 8601 date string
        surgery_type: Type of surgery
        source: Source view name
        description: Event description
        clinical_features: V4.1 features (institution, location)
        v2_annotation: V2 cross-resource annotation
        **kwargs: Additional event fields

    Returns:
        ClinicalEvent for surgery
    """
    return ClinicalEvent(
        event_type=EventType.SURGERY.value,
        event_date=event_date,
        stage=2,
        source=source,
        surgery_type=surgery_type,
        description=description,
        clinical_features=clinical_features,
        v2_annotation=v2_annotation,
        **kwargs
    )


def create_imaging_event(
    event_date: str,
    imaging_modality: str,
    source: str = "v_imaging",
    description: Optional[str] = None,
    report_conclusion: Optional[str] = None,
    tumor_measurements: Optional[List[TumorMeasurement]] = None,
    treatment_response: Optional[TreatmentResponse] = None,
    clinical_features: Optional[Dict[str, Any]] = None,
    v2_annotation: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ClinicalEvent:
    """
    Factory function to create standardized imaging events

    Args:
        event_date: ISO 8601 date string
        imaging_modality: Type of imaging (MRI, CT, etc.)
        source: Source view name
        description: Event description
        report_conclusion: Radiology report conclusion
        tumor_measurements: List of TumorMeasurement objects (V4.2)
        treatment_response: TreatmentResponse object (V4.2)
        clinical_features: V4.1 features (institution, location)
        v2_annotation: V2 cross-resource annotation
        **kwargs: Additional event fields

    Returns:
        ClinicalEvent for imaging
    """
    # Convert TumorMeasurement objects to dicts
    tm_dicts = None
    if tumor_measurements:
        tm_dicts = [tm.to_dict() for tm in tumor_measurements]

    # Convert TreatmentResponse object to dict
    tr_dict = None
    if treatment_response:
        tr_dict = treatment_response.to_dict()

    return ClinicalEvent(
        event_type=EventType.IMAGING.value,
        event_date=event_date,
        stage=2,
        source=source,
        imaging_modality=imaging_modality,
        description=description,
        report_conclusion=report_conclusion,
        tumor_measurements=tm_dicts,
        treatment_response=tr_dict,
        clinical_features=clinical_features,
        v2_annotation=v2_annotation,
        **kwargs
    )


def create_pathology_event(
    event_date: str,
    specimen_type: str,
    source: str = "v_pathology_diagnostics",
    description: Optional[str] = None,
    clinical_features: Optional[Dict[str, Any]] = None,
    v2_annotation: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ClinicalEvent:
    """
    Factory function to create standardized pathology events

    Args:
        event_date: ISO 8601 date string
        specimen_type: Type of specimen
        source: Source view name
        description: Event description
        clinical_features: V4.1 features (institution, location)
        v2_annotation: V2 cross-resource annotation
        **kwargs: Additional event fields

    Returns:
        ClinicalEvent for pathology
    """
    return ClinicalEvent(
        event_type=EventType.PATHOLOGY.value,
        event_date=event_date,
        stage=2,
        source=source,
        specimen_type=specimen_type,
        description=description,
        clinical_features=clinical_features,
        v2_annotation=v2_annotation,
        **kwargs
    )


# ============================================================================
# LEGACY COMPATIBILITY HELPERS
# ============================================================================

def dict_to_clinical_event(event_dict: Dict[str, Any]) -> ClinicalEvent:
    """
    Convert legacy dictionary-based event to ClinicalEvent

    Supports backward compatibility during V4.2 migration

    Args:
        event_dict: Legacy event dictionary

    Returns:
        ClinicalEvent instance
    """
    return ClinicalEvent.from_dict(event_dict)


def clinical_event_to_dict(event: ClinicalEvent) -> Dict[str, Any]:
    """
    Convert ClinicalEvent to dictionary

    Args:
        event: ClinicalEvent instance

    Returns:
        Dictionary representation
    """
    return event.to_dict()
