"""
Institution Tracker for V4.1 Patient Timeline Abstraction

Schema-first approach to institution tracking - prioritizes structured FHIR data
over LLM extraction (85% structured, 12% metadata, 3% text).

Based on INSTITUTION_SCHEMA_FIELDS_MAPPING.md documentation.

Key Sources:
- procedure_performer.performer_actor_display (surgery institutions)
- diagnostic_report_performer.performer_display (imaging institutions)
- observation_performer.performer_display (lab/molecular test institutions)
- document_reference.custodian_display (external document institutions)
- encounter.hospitalization_origin_display (referring institutions)
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

# Import V4 feature object
from lib.feature_object import FeatureObject, SourceRecord, Adjudication

logger = logging.getLogger(__name__)


@dataclass
class InstitutionFeature:
    """
    Healthcare institution providing care

    Confidence tiers:
    - HIGH: From structured FHIR performer/custodian fields (85% of cases)
    - MEDIUM: From metadata inference (12% of cases)
    - LOW: From text extraction (3% of cases)
    """
    institution_name: str
    institution_type: str  # "primary_treating", "referring", "external_specialty", "diagnostic", "unknown"
    event_type: str  # "surgery", "imaging", "chemotherapy", "radiation", "molecular_testing", "pathology"
    event_id: Optional[str] = None  # FHIR resource ID
    event_date: Optional[str] = None
    confidence: str = "HIGH"  # "HIGH", "MEDIUM", "LOW"
    source_field: Optional[str] = None  # e.g., "procedure_performer.performer_actor_display"
    extraction_method: str = "structured_fhir"  # "structured_fhir", "metadata_inference", "text_extraction"
    extracted_at: Optional[str] = None
    is_external: bool = False  # True if not the primary treating institution

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class InstitutionTracker:
    """
    Tracks institutions providing care across patient timeline

    Uses schema-first approach:
    1. TIER 1 (PRIMARY): Structured FHIR fields - 85% coverage, HIGH confidence
    2. TIER 2 (SECONDARY): Metadata inference - 12% coverage, MEDIUM confidence
    3. TIER 3 (TERTIARY): Text extraction - 3% coverage, LOW confidence
    """

    def __init__(self, primary_institution: str = "Children's Hospital of Philadelphia"):
        """
        Initialize institution tracker

        Args:
            primary_institution: Name of primary treating institution for external detection
        """
        self.primary_institution = primary_institution
        logger.info(f"✅ Initialized InstitutionTracker (primary: {primary_institution})")

    def extract_from_procedure(
        self,
        procedure_data: Dict[str, Any]
    ) -> Optional[InstitutionFeature]:
        """
        Extract institution from procedure record (TIER 1: Structured FHIR)

        Uses procedure_performer.performer_actor_display field

        Args:
            procedure_data: Row from v_procedures_tumor with pp_performer_actor_display

        Returns:
            InstitutionFeature or None
        """
        # Check if performer_actor_display exists
        institution_name = procedure_data.get('pp_performer_actor_display')

        if not institution_name or institution_name.strip() == '':
            return None

        # Determine if external
        is_external = not self._is_primary_institution(institution_name)

        # Create feature
        return InstitutionFeature(
            institution_name=institution_name,
            institution_type="external_specialty" if is_external else "primary_treating",
            event_type="surgery",
            event_id=procedure_data.get('proc_id'),
            event_date=procedure_data.get('proc_performed_date_time'),
            confidence="HIGH",
            source_field="procedure_performer.performer_actor_display",
            extraction_method="structured_fhir",
            extracted_at=datetime.now().isoformat(),
            is_external=is_external
        )

    def extract_from_imaging(
        self,
        imaging_data: Dict[str, Any]
    ) -> Optional[InstitutionFeature]:
        """
        Extract institution from diagnostic report (TIER 1: Structured FHIR)

        Uses diagnostic_report_performer.performer_display field

        Args:
            imaging_data: Row from v_imaging with performer_display

        Returns:
            InstitutionFeature or None
        """
        institution_name = imaging_data.get('performer_display')

        if not institution_name or institution_name.strip() == '':
            return None

        is_external = not self._is_primary_institution(institution_name)

        return InstitutionFeature(
            institution_name=institution_name,
            institution_type="diagnostic" if is_external else "primary_treating",
            event_type="imaging",
            event_id=imaging_data.get('diagnostic_report_id'),
            event_date=imaging_data.get('imaging_date'),
            confidence="HIGH",
            source_field="diagnostic_report_performer.performer_display",
            extraction_method="structured_fhir",
            extracted_at=datetime.now().isoformat(),
            is_external=is_external
        )

    def extract_from_document_reference(
        self,
        docref_data: Dict[str, Any]
    ) -> Optional[InstitutionFeature]:
        """
        Extract institution from document reference (TIER 1: Structured FHIR)

        Uses document_reference.custodian_display field to identify external documents

        Args:
            docref_data: Row from document_reference with custodian_display

        Returns:
            InstitutionFeature or None
        """
        institution_name = docref_data.get('custodian_display')

        if not institution_name or institution_name.strip() == '':
            return None

        # Custodian indicates the institution that created/owns the document
        is_external = not self._is_primary_institution(institution_name)

        # Infer event type from document type
        doc_type = docref_data.get('dr_type_text', '').lower()
        event_type = self._infer_event_type_from_doc_type(doc_type)

        return InstitutionFeature(
            institution_name=institution_name,
            institution_type="external_specialty" if is_external else "primary_treating",
            event_type=event_type,
            event_id=docref_data.get('document_reference_id'),
            event_date=docref_data.get('period_start'),
            confidence="HIGH",
            source_field="document_reference.custodian_display",
            extraction_method="structured_fhir",
            extracted_at=datetime.now().isoformat(),
            is_external=is_external
        )

    def extract_from_encounter(
        self,
        encounter_data: Dict[str, Any]
    ) -> Optional[InstitutionFeature]:
        """
        Extract referring institution from encounter (TIER 1: Structured FHIR)

        Uses encounter.hospitalization_origin_display field

        Args:
            encounter_data: Row from encounter with hospitalization_origin_display

        Returns:
            InstitutionFeature or None
        """
        referring_institution = encounter_data.get('hospitalization_origin_display')

        if not referring_institution or referring_institution.strip() == '':
            return None

        return InstitutionFeature(
            institution_name=referring_institution,
            institution_type="referring",
            event_type="referral",
            event_id=encounter_data.get('encounter_id'),
            event_date=encounter_data.get('period_start'),
            confidence="HIGH",
            source_field="encounter.hospitalization_origin_display",
            extraction_method="structured_fhir",
            extracted_at=datetime.now().isoformat(),
            is_external=True  # Referring institutions are by definition external
        )

    def extract_from_metadata(
        self,
        doc_type: str,
        document_id: str
    ) -> Optional[InstitutionFeature]:
        """
        Infer institution from document metadata (TIER 2: Metadata Inference)

        Used when structured fields are NULL but document type suggests external origin

        Args:
            doc_type: Document type text (e.g., "Outside Records")
            document_id: Document reference ID

        Returns:
            InstitutionFeature or None
        """
        if not doc_type:
            return None

        # Check if document type indicates external origin
        doc_type_lower = doc_type.lower()
        external_indicators = ['outside', 'external', 'referring', 'transferred']

        is_external_doc = any(indicator in doc_type_lower for indicator in external_indicators)

        if not is_external_doc:
            return None

        # Create feature with MEDIUM confidence
        return InstitutionFeature(
            institution_name="External Institution (Unknown)",
            institution_type="external_specialty",
            event_type="unknown",
            event_id=document_id,
            event_date=None,
            confidence="MEDIUM",
            source_field="document_reference.dr_type_text",
            extraction_method="metadata_inference",
            extracted_at=datetime.now().isoformat(),
            is_external=True
        )

    def create_institution_feature_object(
        self,
        institution_features: List[InstitutionFeature],
        adjudication_logic: Optional[str] = None
    ) -> FeatureObject:
        """
        Create a FeatureObject from multiple InstitutionFeature instances

        This allows tracking institutions across timeline events with provenance.

        Args:
            institution_features: List of InstitutionFeature from different events
            adjudication_logic: Optional explanation of adjudication

        Returns:
            FeatureObject with institution data
        """
        if not institution_features:
            return FeatureObject(
                feature_name="institution",
                value=None,
                sources=[],
                adjudication=None
            )

        # Create source records
        sources = []
        for feat in institution_features:
            source = SourceRecord(
                source_type=f"institution_{feat.event_type}",
                source_id=feat.event_id,
                extracted_value={
                    "institution_name": feat.institution_name,
                    "institution_type": feat.institution_type,
                    "event_type": feat.event_type,
                    "is_external": feat.is_external
                },
                extraction_method=feat.extraction_method,
                confidence=feat.confidence,
                extracted_at=feat.extracted_at,
                metadata={
                    "source_field": feat.source_field,
                    "event_date": feat.event_date
                }
            )
            sources.append(source)

        # Identify primary treating institution (most common non-external)
        primary_institutions = [f for f in institution_features if not f.is_external]
        if primary_institutions:
            primary_name = primary_institutions[0].institution_name
        else:
            primary_name = self.primary_institution

        # Identify external institutions
        external_institutions = [f for f in institution_features if f.is_external]

        # Create adjudication
        adjudication_obj = Adjudication(
            adjudicated_value={
                "primary_treating_institution": primary_name,
                "external_institutions": [f.institution_name for f in external_institutions],
                "total_institutions": len(set(f.institution_name for f in institution_features))
            },
            logic=adjudication_logic or f"Identified {len(primary_institutions)} primary and {len(external_institutions)} external institutions",
            confidence="HIGH" if primary_institutions else "MEDIUM",
            conflicting_sources=[],
            adjudicated_at=datetime.now().isoformat()
        )

        # Create FeatureObject
        return FeatureObject(
            feature_name="institution",
            value={
                "primary_treating_institution": primary_name,
                "external_institutions": [f.institution_name for f in external_institutions],
                "institutions_by_event": {f.event_id: f.institution_name for f in institution_features if f.event_id}
            },
            sources=sources,
            adjudication=adjudication_obj,
            v3_flat_value=primary_name  # Backward compatibility
        )

    def _is_primary_institution(self, institution_name: str) -> bool:
        """Check if institution name matches primary treating institution"""
        if not institution_name:
            return False
        return self.primary_institution.lower() in institution_name.lower()

    def _infer_event_type_from_doc_type(self, doc_type: str) -> str:
        """Infer event type from document type text"""
        if not doc_type:
            return "unknown"

        doc_type_lower = doc_type.lower()

        if any(term in doc_type_lower for term in ['operative', 'surgery', 'surgical']):
            return "surgery"
        elif any(term in doc_type_lower for term in ['imaging', 'mri', 'ct', 'pet', 'radiology']):
            return "imaging"
        elif any(term in doc_type_lower for term in ['pathology', 'biopsy', 'histology']):
            return "pathology"
        elif any(term in doc_type_lower for term in ['radiation', 'radiotherapy', 'rt']):
            return "radiation"
        elif any(term in doc_type_lower for term in ['chemotherapy', 'chemo', 'treatment']):
            return "chemotherapy"
        elif any(term in doc_type_lower for term in ['molecular', 'genetic', 'genomic']):
            return "molecular_testing"
        else:
            return "unknown"


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize tracker
    tracker = InstitutionTracker(primary_institution="Children's Hospital of Philadelphia")

    # Test with sample procedure data
    procedure_data = {
        'proc_id': 'Procedure/surgery_001',
        'pp_performer_actor_display': 'Penn State Hershey Medical Center',
        'proc_performed_date_time': '2017-09-25'
    }

    institution_feature = tracker.extract_from_procedure(procedure_data)

    if institution_feature:
        print("\n=== Extracted Institution (from Surgery) ===")
        print(f"Institution: {institution_feature.institution_name}")
        print(f"Type: {institution_feature.institution_type}")
        print(f"Event Type: {institution_feature.event_type}")
        print(f"Is External: {institution_feature.is_external}")
        print(f"Confidence: {institution_feature.confidence}")
        print(f"Source Field: {institution_feature.source_field}")

        # Create FeatureObject
        feature_obj = tracker.create_institution_feature_object([institution_feature])
        print(f"\n=== FeatureObject ===")
        print(f"Feature Name: {feature_obj.feature_name}")
        print(f"Primary Institution: {feature_obj.value['primary_treating_institution']}")
        print(f"External Institutions: {feature_obj.value['external_institutions']}")
        print(f"Number of Sources: {len(feature_obj.sources)}")
