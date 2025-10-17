"""
Data models for the Multi-Source Extraction Framework
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class EventType(Enum):
    """Clinical event types"""
    INITIAL_DIAGNOSIS = "initial_diagnosis"
    SURGERY = "surgery"
    PROGRESSION = "progression"
    RECURRENCE = "recurrence"
    TREATMENT = "treatment"
    RADIATION = "radiation"
    CHEMOTHERAPY = "chemotherapy"
    IMAGING = "imaging"
    LAB = "lab"
    DECEASED = "deceased"


class DataSource(Enum):
    """Available data sources"""
    ATHENA_STRUCTURED = "athena_structured"
    ATHENA_UNSTRUCTURED = "athena_unstructured"
    BINARY_NOTES = "binary_notes"
    CALCULATED = "calculated"


class ExtractionLogic(Enum):
    """Extraction logic types"""
    DIRECT = "direct"  # Direct mapping from structured data
    LLM_EXTRACTION = "llm_extraction"  # Requires LLM processing
    CALCULATION = "calculation"  # Calculated from other fields
    AGGREGATION = "aggregation"  # Aggregated from multiple sources


@dataclass
class ClinicalEvent:
    """Represents a clinical event in the patient timeline"""
    event_id: str
    event_type: EventType
    event_date: datetime
    age_at_event_days: int
    encounter_id: Optional[str] = None
    procedure_codes: List[str] = field(default_factory=list)
    diagnosis_codes: List[str] = field(default_factory=list)
    binary_references: List[str] = field(default_factory=list)
    measurements: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Link to other events
    parent_event_id: Optional[str] = None
    child_event_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'event_date': self.event_date.isoformat(),
            'age_at_event_days': self.age_at_event_days,
            'encounter_id': self.encounter_id,
            'procedure_codes': self.procedure_codes,
            'diagnosis_codes': self.diagnosis_codes,
            'binary_references': self.binary_references,
            'measurements': self.measurements,
            'metadata': self.metadata,
            'parent_event_id': self.parent_event_id,
            'child_event_ids': self.child_event_ids
        }


@dataclass
class ExtractionTarget:
    """Defines a feature to be extracted"""
    variable_name: str
    data_dictionary_field: str
    field_type: str  # 'text', 'radio', 'checkbox', 'calculated'
    source_priority: List[DataSource]
    extraction_logic: ExtractionLogic
    required_context: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    event_scope: Optional[str] = None  # 'per_event', 'per_patient', 'per_encounter'

    # Data dictionary metadata
    choices: Optional[Dict[str, str]] = None  # Code to label mapping
    field_note: Optional[str] = None
    required: bool = False

    def get_code_for_value(self, value: str) -> Optional[str]:
        """Map value to data dictionary code"""
        if self.choices:
            for code, label in self.choices.items():
                if label.lower() == value.lower():
                    return code
        return None


@dataclass
class ExtractionResult:
    """Result of extracting a single feature"""
    variable_name: str
    value: Any
    source: DataSource
    confidence: float = 1.0
    event_id: Optional[str] = None
    extraction_timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Validation and provenance
    validated: bool = False
    validation_errors: List[str] = field(default_factory=list)
    source_documents: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'variable_name': self.variable_name,
            'value': self.value,
            'source': self.source.value,
            'confidence': self.confidence,
            'event_id': self.event_id,
            'extraction_timestamp': self.extraction_timestamp.isoformat(),
            'validated': self.validated,
            'validation_errors': self.validation_errors,
            'source_documents': self.source_documents,
            'metadata': self.metadata
        }


@dataclass
class PatientContext:
    """Patient context for extraction"""
    patient_id: str
    birth_date: datetime
    death_date: Optional[datetime] = None
    mrn: Optional[str] = None

    # Key dates for reference
    diagnosis_date: Optional[datetime] = None
    last_encounter_date: Optional[datetime] = None

    # Cached data
    timeline: List[ClinicalEvent] = field(default_factory=list)
    extracted_features: Dict[str, ExtractionResult] = field(default_factory=dict)

    def calculate_age_at_date(self, date: datetime) -> int:
        """Calculate age in days at given date"""
        return (date - self.birth_date).days


@dataclass
class ExtractionConfig:
    """Configuration for extraction run"""
    # Data sources
    staging_path: str
    mcp_connection: Optional[str] = None
    use_mcp: bool = False

    # Extraction parameters
    extraction_targets: List[ExtractionTarget] = field(default_factory=list)
    llm_model: str = "gemma2:27b"
    llm_temperature: float = 0.0

    # Performance settings
    batch_size: int = 10
    max_concurrent_extractions: int = 5
    cache_enabled: bool = True

    # Output settings
    output_format: str = "event_based"  # 'event_based', 'patient_summary', 'both'
    output_path: Optional[str] = None

    # Validation settings
    enable_validation: bool = True
    validation_threshold: float = 0.8
    require_manual_review: List[str] = field(default_factory=list)