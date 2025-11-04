"""
Tumor Location Extractor for V4.1 Patient Timeline Abstraction

This module extracts tumor location and laterality from clinical documents,
mapping them to the CBTN anatomical ontology with UBERON cross-references.

Features:
- Multi-source location extraction (imaging, operative notes, path reports)
- Temporal tracking (initial, progression, metastasis)
- Laterality detection (bilateral, left, right, midline)
- Integration with existing mvp/utils/brain_location_normalizer.py
- FeatureObject pattern for complete provenance tracking
"""

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from mvp.utils.brain_location_normalizer import BrainTumorLocationNormalizer, NormalizedLocation

# Import V4 feature object
from lib.feature_object import FeatureObject, SourceRecord, Adjudication

logger = logging.getLogger(__name__)


@dataclass
class LateralityFeature:
    """
    Tumor laterality/sidedness

    Values: "bilateral", "left", "right", "midline", "unknown"
    """
    value: str
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    source_type: str  # "imaging", "operative_note", "pathology", "clinical_note"
    source_id: Optional[str] = None
    extraction_method: str = "rule_based"
    extracted_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class TumorLocationFeature:
    """
    Tumor anatomical location with CBTN ontology mapping

    Supports multiple concurrent locations (e.g., butterfly glioma spanning both hemispheres)
    """
    locations: List[str]  # CBTN labels (e.g., "Frontal Lobe", "Corpus Callosum")
    cbtn_codes: List[int]  # CBTN codes
    uberon_ids: List[str]  # UBERON ontology IDs
    laterality: Optional[LateralityFeature] = None
    confidence: str = "HIGH"  # Overall confidence for location extraction
    source_type: str = ""  # "preop_imaging", "postop_imaging", "operative_note", "pathology"
    source_id: Optional[str] = None
    extraction_method: str = "brain_location_normalizer"
    extracted_at: Optional[str] = None
    raw_text: Optional[str] = None  # Original text mentioning location
    progression_status: Optional[str] = None  # "initial", "progression", "recurrence", "metastasis"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "locations": self.locations,
            "cbtn_codes": self.cbtn_codes,
            "uberon_ids": self.uberon_ids,
            "confidence": self.confidence,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "extraction_method": self.extraction_method,
            "extracted_at": self.extracted_at,
            "raw_text": self.raw_text,
            "progression_status": self.progression_status
        }
        if self.laterality:
            result["laterality"] = self.laterality.to_dict()
        return result


class TumorLocationExtractor:
    """
    Extracts tumor location and laterality from clinical text

    Uses brain_location_normalizer.py for CBTN ontology mapping
    Adds laterality detection and FeatureObject integration
    """

    def __init__(self, ontology_path: Optional[str] = None):
        """
        Initialize the location extractor

        Args:
            ontology_path: Path to brain_tumor_location_ontology_v4.1.json
        """
        # Set default path if not provided
        if ontology_path is None:
            ontology_path = os.path.join(
                os.path.dirname(__file__),
                "brain_tumor_location_ontology_v4.1.json"
            )

        self.ontology_path = ontology_path
        self.normalizer = BrainTumorLocationNormalizer(
            mapping_path=Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/utils/brain_tumor_location_ontology.json")
        )

        # Load extended ontology for new codes 25-32
        with open(ontology_path, 'r') as f:
            self.extended_ontology = json.load(f)

        # Create lookup maps for CBTN codes -> UBERON IDs and labels
        self.cbtn_to_uberon = {}
        self.cbtn_to_label = {}
        for loc in self.extended_ontology['tumor_location']:
            code = loc['cbtn_code']
            self.cbtn_to_label[code] = loc['cbtn_label']
            self.cbtn_to_uberon[code] = [node['id'] for node in loc['ontology_nodes']]

        logger.info(f"✅ Initialized TumorLocationExtractor with {len(self.cbtn_to_label)} CBTN codes")

    def extract_location_from_text(
        self,
        text: str,
        source_type: str,
        source_id: Optional[str] = None,
        min_confidence: float = 0.55,
        progression_status: Optional[str] = None
    ) -> Optional[TumorLocationFeature]:
        """
        Extract tumor location from free text

        Args:
            text: Clinical text (imaging report, operative note, etc.)
            source_type: Type of document ("preop_imaging", "operative_note", etc.)
            source_id: FHIR resource ID
            min_confidence: Minimum confidence threshold for location matching
            progression_status: "initial", "progression", "recurrence", "metastasis"

        Returns:
            TumorLocationFeature or None if no location found
        """
        if not text or len(text.strip()) < 10:
            return None

        # Use brain_location_normalizer for extraction
        normalized_locs = self.normalizer.normalise_text(
            text,
            min_confidence=min_confidence,
            top_n=5  # Allow multiple locations for tumors spanning multiple regions
        )

        if not normalized_locs:
            logger.debug(f"No locations found in text: {text[:100]}...")
            return None

        # Extract CBTN codes, labels, and UBERON IDs
        cbtn_codes = [loc.cbtn_code for loc in normalized_locs]
        cbtn_labels = [self.cbtn_to_label.get(loc.cbtn_code, f"Code {loc.cbtn_code}")
                       for loc in normalized_locs]
        uberon_ids = []
        for code in cbtn_codes:
            uberon_ids.extend(self.cbtn_to_uberon.get(code, []))

        # Determine overall confidence (use highest from normalized locations)
        max_confidence_score = max(loc.confidence for loc in normalized_locs)
        if max_confidence_score >= 0.85:
            confidence = "HIGH"
        elif max_confidence_score >= 0.65:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Extract laterality
        laterality = self.extract_laterality(text, source_type, source_id)

        # Create feature
        feature = TumorLocationFeature(
            locations=cbtn_labels,
            cbtn_codes=cbtn_codes,
            uberon_ids=uberon_ids,
            laterality=laterality,
            confidence=confidence,
            source_type=source_type,
            source_id=source_id,
            extraction_method="brain_location_normalizer",
            extracted_at=datetime.now().isoformat(),
            raw_text=text[:200],  # Store snippet for provenance
            progression_status=progression_status
        )

        logger.info(f"📍 Extracted location: {cbtn_labels} (codes: {cbtn_codes}) from {source_type}")

        return feature

    def extract_laterality(
        self,
        text: str,
        source_type: str,
        source_id: Optional[str] = None
    ) -> Optional[LateralityFeature]:
        """
        Extract tumor laterality from text using rule-based patterns

        Args:
            text: Clinical text
            source_type: Type of document
            source_id: FHIR resource ID

        Returns:
            LateralityFeature or None
        """
        if not text:
            return None

        text_lower = text.lower()

        # Priority order: bilateral > midline > left > right
        # This prevents false positives from "left midline" being classified as just "left"

        # Check for bilateral
        bilateral_patterns = [
            r'\bbilateral\b',
            r'\bbihemispheric\b',
            r'\binvolv(?:ing|es|ed) both hemispheres\b',
            r'\bcross(?:ing|es|ed) midline\b',
            r'\bbutterfly\b'  # butterfly glioma
        ]
        for pattern in bilateral_patterns:
            if re.search(pattern, text_lower):
                return LateralityFeature(
                    value="bilateral",
                    confidence="HIGH",
                    source_type=source_type,
                    source_id=source_id,
                    extraction_method="rule_based",
                    extracted_at=datetime.now().isoformat()
                )

        # Check for midline
        midline_patterns = [
            r'\bmidline\b',
            r'\bmid-line\b',
            r'\bcentral\b.*\b(?:third ventricle|pineal|corpus callosum|hypothalamus)\b',
            r'\b(?:third ventricle|pineal|corpus callosum|hypothalamus)\b.*\bcentral\b'
        ]
        for pattern in midline_patterns:
            if re.search(pattern, text_lower):
                return LateralityFeature(
                    value="midline",
                    confidence="HIGH",
                    source_type=source_type,
                    source_id=source_id,
                    extraction_method="rule_based",
                    extracted_at=datetime.now().isoformat()
                )

        # Check for left
        left_patterns = [
            r'\bleft\s+(?:frontal|temporal|parietal|occipital|hemisphere|cerebellum)',
            r'(?:frontal|temporal|parietal|occipital|hemisphere|cerebellum)\s+left\b',
            r'\bL\s+(?:frontal|temporal|parietal|occipital)\b'
        ]
        for pattern in left_patterns:
            if re.search(pattern, text_lower):
                return LateralityFeature(
                    value="left",
                    confidence="HIGH",
                    source_type=source_type,
                    source_id=source_id,
                    extraction_method="rule_based",
                    extracted_at=datetime.now().isoformat()
                )

        # Check for right
        right_patterns = [
            r'\bright\s+(?:frontal|temporal|parietal|occipital|hemisphere|cerebellum)',
            r'(?:frontal|temporal|parietal|occipital|hemisphere|cerebellum)\s+right\b',
            r'\bR\s+(?:frontal|temporal|parietal|occipital)\b'
        ]
        for pattern in right_patterns:
            if re.search(pattern, text_lower):
                return LateralityFeature(
                    value="right",
                    confidence="HIGH",
                    source_type=source_type,
                    source_id=source_id,
                    extraction_method="rule_based",
                    extracted_at=datetime.now().isoformat()
                )

        # No laterality detected
        return LateralityFeature(
            value="unknown",
            confidence="LOW",
            source_type=source_type,
            source_id=source_id,
            extraction_method="rule_based",
            extracted_at=datetime.now().isoformat()
        )

    def create_location_feature_object(
        self,
        location_features: List[TumorLocationFeature],
        adjudication_logic: Optional[str] = None
    ) -> FeatureObject:
        """
        Create a FeatureObject from multiple TumorLocationFeature instances

        This allows tracking location changes over time with complete provenance.

        Args:
            location_features: List of TumorLocationFeature from different sources/times
            adjudication_logic: Optional explanation of how location was adjudicated

        Returns:
            FeatureObject with tumor_location data
        """
        if not location_features:
            return FeatureObject(
                feature_name="tumor_location",
                value=None,
                sources=[],
                adjudication=None
            )

        # Use the most recent location as the canonical value
        latest_feature = location_features[-1]

        # Create source records for each feature
        sources = []
        for feat in location_features:
            source = SourceRecord(
                source_type=feat.source_type,
                source_id=feat.source_id,
                extracted_value={
                    "locations": feat.locations,
                    "cbtn_codes": feat.cbtn_codes,
                    "uberon_ids": feat.uberon_ids,
                    "laterality": feat.laterality.to_dict() if feat.laterality else None,
                    "progression_status": feat.progression_status
                },
                extraction_method=feat.extraction_method,
                confidence=feat.confidence,
                extracted_at=feat.extracted_at,
                metadata={
                    "raw_text": feat.raw_text
                }
            )
            sources.append(source)

        # Create adjudication if multiple sources
        adjudication_obj = None
        if len(location_features) > 1:
            adjudication_obj = Adjudication(
                adjudicated_value={
                    "locations": latest_feature.locations,
                    "cbtn_codes": latest_feature.cbtn_codes,
                    "uberon_ids": latest_feature.uberon_ids,
                    "laterality": latest_feature.laterality.to_dict() if latest_feature.laterality else None
                },
                logic=adjudication_logic or "Most recent location used as canonical value",
                confidence="HIGH" if latest_feature.confidence == "HIGH" else "MEDIUM",
                conflicting_sources=[],  # Could implement conflict detection
                adjudicated_at=datetime.now().isoformat()
            )

        # Create FeatureObject
        return FeatureObject(
            feature_name="tumor_location",
            value={
                "locations": latest_feature.locations,
                "cbtn_codes": latest_feature.cbtn_codes,
                "uberon_ids": latest_feature.uberon_ids,
                "laterality": latest_feature.laterality.to_dict() if latest_feature.laterality else None
            },
            sources=sources,
            adjudication=adjudication_obj,
            v3_flat_value=", ".join(latest_feature.locations)  # Backward compatibility
        )


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize extractor
    extractor = TumorLocationExtractor()

    # Test with sample text
    sample_text = """
    MRI Brain: There is a large heterogeneous mass in the right frontal lobe extending
    across the corpus callosum to involve the left frontal lobe. The tumor measures
    approximately 6.5 x 5.2 x 4.8 cm. There is significant mass effect with midline shift.
    Findings consistent with butterfly glioblastoma.
    """

    # Extract location
    location_feature = extractor.extract_location_from_text(
        text=sample_text,
        source_type="preop_imaging",
        source_id="DiagnosticReport/imaging_001",
        progression_status="initial"
    )

    if location_feature:
        print("\n=== Extracted Tumor Location ===")
        print(f"Locations: {location_feature.locations}")
        print(f"CBTN Codes: {location_feature.cbtn_codes}")
        print(f"UBERON IDs: {location_feature.uberon_ids}")
        print(f"Laterality: {location_feature.laterality.value if location_feature.laterality else 'Unknown'}")
        print(f"Confidence: {location_feature.confidence}")
        print(f"Progression Status: {location_feature.progression_status}")

        # Create FeatureObject
        feature_obj = extractor.create_location_feature_object([location_feature])
        print(f"\n=== FeatureObject ===")
        print(f"Feature Name: {feature_obj.feature_name}")
        print(f"Value: {feature_obj.value}")
        print(f"Number of Sources: {len(feature_obj.sources)}")
        print(f"V3 Flat Value: {feature_obj.v3_flat_value}")
