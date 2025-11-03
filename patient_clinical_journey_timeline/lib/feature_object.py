#!/usr/bin/env python3
"""
FeatureObject - Multi-Source Clinical Feature with Provenance Tracking

This module implements the FeatureObject pattern for storing clinical features
with full provenance tracking, multi-source support, and adjudication capabilities.

Design:
  - Every clinical feature (EOR, tumor site, dose, etc.) is a FeatureObject
  - Each FeatureObject stores ALL sources that contributed to the feature
  - When sources conflict, adjudication logic determines final value
  - Complete audit trail for every extracted feature

Usage:
    from lib.feature_object import FeatureObject, SourceRecord, Adjudication

    # Create feature from single source
    eor = FeatureObject.from_single_source(
        value="STR",
        source_type="operative_note",
        source_id="Binary/abc123",
        extracted_value="STR",
        extraction_method="medgemma",
        confidence="MEDIUM",
        raw_text="Sonopet was used to debulk..."
    )

    # Add conflicting source
    eor.add_source(
        source_type="postop_imaging",
        source_id="DiagnosticReport/def456",
        extracted_value="NTR",
        extraction_method="medgemma",
        confidence="HIGH",
        raw_text="Minimal residual enhancement..."
    )

    # Adjudicate conflict
    eor.adjudicate(
        final_value="STR",
        method="favor_imaging_if_high_confidence",
        rationale="Imaging HIGH confidence but surgeon assessment more reliable for residual tumor",
        adjudicated_by="orchestrator_agent",
        requires_manual_review=True
    )

    # Serialize to JSON
    eor_dict = eor.to_dict()
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List, Dict
from datetime import datetime
from enum import Enum


class ConfidenceLevel(str, Enum):
    """Extraction confidence levels"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class SourceType(str, Enum):
    """Types of data sources for feature extraction"""
    OPERATIVE_NOTE = "operative_note"
    POSTOP_IMAGING = "postop_imaging"
    DISCHARGE_SUMMARY = "discharge_summary"
    PROGRESS_NOTE = "progress_note"
    PATHOLOGY_REPORT = "pathology_report"
    RADIATION_SUMMARY = "radiation_summary"
    CHEMOTHERAPY_ORDER = "chemotherapy_order"
    STRUCTURED_DATA = "structured_data"
    MOLECULAR_TEST_RESULT = "molecular_test_result"
    CONSULTATION_NOTE = "consultation_note"
    OTHER = "other"


@dataclass
class SourceRecord:
    """
    Records provenance for a single data source that contributed to a feature.

    Attributes:
        source_type: Type of source (operative_note, postop_imaging, etc.)
        source_id: FHIR resource ID or structured data table reference
        extracted_value: Raw value extracted from this source
        extraction_method: How value was extracted (medgemma, regex, structured, etc.)
        confidence: Extraction confidence level
        raw_text: Original text snippet from source (for audit trail)
        extracted_at: Timestamp of extraction
    """
    source_type: str
    extracted_value: Any
    extraction_method: str
    confidence: str
    source_id: Optional[str] = None
    raw_text: Optional[str] = None
    extracted_at: Optional[str] = None

    def __post_init__(self):
        """Set timestamp if not provided"""
        if self.extracted_at is None:
            self.extracted_at = datetime.utcnow().isoformat() + 'Z'

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Adjudication:
    """
    Records the adjudication process when multiple sources conflict.

    Attributes:
        final_value: The adjudicated/final value chosen
        adjudication_method: Algorithm or rule used to adjudicate
        rationale: Human-readable explanation of why final_value was chosen
        adjudicated_by: Agent or process that performed adjudication
        adjudicated_at: Timestamp of adjudication
        requires_manual_review: Flag indicating human review needed
    """
    final_value: Any
    adjudication_method: str
    rationale: str
    adjudicated_by: str
    adjudicated_at: Optional[str] = None
    requires_manual_review: bool = False

    def __post_init__(self):
        """Set timestamp if not provided"""
        if self.adjudicated_at is None:
            self.adjudicated_at = datetime.utcnow().isoformat() + 'Z'

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class FeatureObject:
    """
    Multi-source clinical feature with full provenance tracking.

    This is the core data structure for representing any clinical feature
    (extent of resection, tumor site, radiation dose, etc.) with:
      - Current/final value
      - ALL sources that contributed to the feature
      - Adjudication record if sources conflicted

    Attributes:
        value: Current/final value of the feature
        sources: List of all sources that contributed to this feature
        adjudication: Adjudication record if sources conflicted (optional)
    """
    value: Any
    sources: List[SourceRecord] = field(default_factory=list)
    adjudication: Optional[Adjudication] = None

    @classmethod
    def from_single_source(cls,
                          value: Any,
                          source_type: str,
                          extracted_value: Any,
                          extraction_method: str,
                          confidence: str,
                          source_id: Optional[str] = None,
                          raw_text: Optional[str] = None) -> 'FeatureObject':
        """
        Create FeatureObject from a single source (most common case).

        Args:
            value: Initial value for the feature
            source_type: Type of source (operative_note, postop_imaging, etc.)
            extracted_value: Raw value extracted from source
            extraction_method: How value was extracted (medgemma, regex, etc.)
            confidence: Extraction confidence (HIGH, MEDIUM, LOW)
            source_id: FHIR resource ID or table reference (optional)
            raw_text: Original text snippet (optional)

        Returns:
            FeatureObject with single source
        """
        source = SourceRecord(
            source_type=source_type,
            source_id=source_id,
            extracted_value=extracted_value,
            extraction_method=extraction_method,
            confidence=confidence,
            raw_text=raw_text
        )
        return cls(value=value, sources=[source])

    def add_source(self,
                   source_type: str,
                   extracted_value: Any,
                   extraction_method: str,
                   confidence: str,
                   source_id: Optional[str] = None,
                   raw_text: Optional[str] = None) -> None:
        """
        Add another source to this feature (e.g., post-op imaging after operative note).

        Args:
            source_type: Type of source
            extracted_value: Raw value extracted from this source
            extraction_method: How value was extracted
            confidence: Extraction confidence
            source_id: FHIR resource ID or table reference (optional)
            raw_text: Original text snippet (optional)
        """
        source = SourceRecord(
            source_type=source_type,
            source_id=source_id,
            extracted_value=extracted_value,
            extraction_method=extraction_method,
            confidence=confidence,
            raw_text=raw_text
        )
        self.sources.append(source)

    def has_conflict(self) -> bool:
        """
        Check if sources have conflicting values.

        Returns:
            True if any source has a different extracted_value than others
        """
        if len(self.sources) <= 1:
            return False

        values = {str(s.extracted_value) for s in self.sources}
        return len(values) > 1

    def adjudicate(self,
                   final_value: Any,
                   method: str,
                   rationale: str,
                   adjudicated_by: str,
                   requires_manual_review: bool = False) -> None:
        """
        Adjudicate conflicting sources and set final value.

        Args:
            final_value: The adjudicated/final value chosen
            method: Algorithm or rule used (e.g., "favor_imaging_if_high_confidence")
            rationale: Explanation of why final_value was chosen
            adjudicated_by: Agent or process that performed adjudication
            requires_manual_review: Flag for human review needed
        """
        self.adjudication = Adjudication(
            final_value=final_value,
            adjudication_method=method,
            rationale=rationale,
            adjudicated_by=adjudicated_by,
            requires_manual_review=requires_manual_review
        )
        self.value = final_value

    def to_dict(self) -> Dict:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with 'value', 'sources', and optionally 'adjudication'
        """
        result = {
            'value': self.value,
            'sources': [s.to_dict() for s in self.sources]
        }
        if self.adjudication:
            result['adjudication'] = self.adjudication.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> 'FeatureObject':
        """
        Create FeatureObject from dictionary (for deserialization).

        Args:
            data: Dictionary with 'value', 'sources', and optionally 'adjudication'

        Returns:
            FeatureObject instance
        """
        sources = [SourceRecord(**s) for s in data.get('sources', [])]
        adjudication = None
        if 'adjudication' in data:
            adjudication = Adjudication(**data['adjudication'])

        return cls(
            value=data['value'],
            sources=sources,
            adjudication=adjudication
        )

    def __repr__(self) -> str:
        """Human-readable representation"""
        conflict_str = " [CONFLICT]" if self.has_conflict() else ""
        adj_str = " [ADJUDICATED]" if self.adjudication else ""
        return f"FeatureObject(value={self.value}, sources={len(self.sources)}){conflict_str}{adj_str}"


# Convenience functions for common patterns

def create_structured_feature(value: Any,
                              table_reference: str,
                              field_name: str) -> FeatureObject:
    """
    Create FeatureObject from structured data (SQL query result).

    Args:
        value: Field value from database
        table_reference: Table/view name (e.g., "v_procedures_tumor")
        field_name: Column name (e.g., "procedure_date")

    Returns:
        FeatureObject with structured_data source
    """
    return FeatureObject.from_single_source(
        value=value,
        source_type=SourceType.STRUCTURED_DATA,
        source_id=f"{table_reference}.{field_name}",
        extracted_value=value,
        extraction_method="sql_query",
        confidence=ConfidenceLevel.HIGH
    )


def create_extracted_feature(value: Any,
                             source_type: str,
                             source_id: str,
                             raw_text: str,
                             confidence: str = "MEDIUM") -> FeatureObject:
    """
    Create FeatureObject from AI extraction (MedGemma).

    Args:
        value: Extracted value
        source_type: Type of source document (operative_note, postop_imaging, etc.)
        source_id: FHIR Binary resource ID
        raw_text: Original text snippet from which value was extracted
        confidence: Extraction confidence (default MEDIUM)

    Returns:
        FeatureObject with medgemma extraction source
    """
    return FeatureObject.from_single_source(
        value=value,
        source_type=source_type,
        source_id=source_id,
        extracted_value=value,
        extraction_method="medgemma",
        confidence=confidence,
        raw_text=raw_text
    )
