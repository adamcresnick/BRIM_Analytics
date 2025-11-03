# Tumor Location Integration with V4 Patient Timeline

**Status**: Design specification for V4.1 enhancement
**Last Updated**: 2025-11-03
**Purpose**: Integrate CBTN tumor location ontology with V4 FeatureObject pattern for comprehensive anatomical tracking

---

## Executive Summary

This document specifies the integration of the **CBTN (Children's Brain Tumor Network) anatomical ontology** with the V4 patient timeline abstraction system. Tumor location will be captured as a **FeatureObject** with complete provenance tracking, supporting:

1. **Multi-source location extraction** (imaging reports, operative notes, pathology reports)
2. **Temporal location tracking** (initial tumor vs progression vs metastasis)
3. **Laterality capture** (bilateral, left, right, midline)
4. **UBERON ontology mapping** for research interoperability
5. **WHO 2021 integration** for location-specific diagnoses (e.g., diffuse midline glioma)

---

## 1. Enhanced CBTN Ontology with Missing Locations

### Locations Already Mapped in Existing CBTN Ontology

| Your Term | CBTN Code | CBTN Label | Status |
|-----------|-----------|------------|--------|
| Frontal | 1 | Frontal Lobe | ✅ MAPPED |
| Temporal | 2 | Temporal Lobe | ✅ MAPPED |
| Parietal | 3 | Parietal Lobe | ✅ MAPPED |
| Occipital | 4 | Occipital Lobe | ✅ MAPPED |
| Thalamus | 5 | Thalamus | ✅ MAPPED |
| intraventricular, Lateral ventricle, Third ventricle, Fourth ventricle | 6 | Ventricles | ✅ MAPPED |
| Hypothalamus | 7 | Suprasellar/Hypothalamic/Pituitary | ✅ MAPPED |
| Cerebellum, Cerebellar hemisphere, Cerebellar vermis, Cerebellar peduncle | 8 | Cerebellum/Posterior Fossa | ✅ MAPPED |
| Medulla | 9 | Brain Stem-Medulla | ✅ MAPPED |
| Midbrain | 10 | Brain Stem-Midbrain/Tectum | ✅ MAPPED |
| Pons | 11 | Brain Stem-Pons | ✅ MAPPED |
| Cervical, Spinal cord (C1 and below) | 12 | Spinal Cord-Cervical | ✅ MAPPED |
| Thoracic | 13 | Spinal Cord-Thoracic | ✅ MAPPED |
| Lumbar, Cauda equina, Conus | 14 | Spinal Cord-Lumbar/Thecal Sac | ✅ MAPPED |
| Optic chiasm, Optic nerve | 15 | Optic Pathway | ✅ MAPPED |
| Pineal | 19 | Pineal Gland | ✅ MAPPED |
| Basal ganglia | 20 | Basal Ganglia | ✅ MAPPED |
| falx, tentorium, Leptomeningeal | 22 | Meninges/Dura | ✅ MAPPED |
| skull base | 23 | Skull | ✅ MAPPED |

### New Locations to Add (10 locations)

The following locations need to be added to the ontology:

#### **NEW CBTN Code 25: Corpus Callosum**
```json
{
  "cbtn_code": 25,
  "cbtn_label": "Corpus Callosum",
  "ontology_nodes": [
    {"id": "UBERON:0002336", "label": "corpus callosum"}
  ],
  "preferred_synonyms": [
    "corpus callosum",
    "callosal",
    "genu of corpus callosum",
    "body of corpus callosum",
    "splenium of corpus callosum",
    "genu",
    "splenium",
    "rostrum of corpus callosum",
    "interhemispheric commissure"
  ],
  "notes": "Major white matter tract connecting cerebral hemispheres. Often involved in butterfly glioblastomas."
}
```

#### **NEW CBTN Code 26: Aqueduct of Sylvius**
```json
{
  "cbtn_code": 26,
  "cbtn_label": "Aqueduct of Sylvius",
  "ontology_nodes": [
    {"id": "UBERON:0002290", "label": "cerebral aqueduct"}
  ],
  "preferred_synonyms": [
    "aqueduct of sylvius",
    "cerebral aqueduct",
    "sylvian aqueduct",
    "aqueductal",
    "periaqueductal",
    "aqueduct stenosis"
  ],
  "notes": "Narrow channel connecting third and fourth ventricles. Stenosis causes hydrocephalus. Already partially covered in CBTN code 6 (ventricles) but deserves specific code for tectal gliomas."
}
```

#### **NEW CBTN Code 27: Cavernous Sinus**
```json
{
  "cbtn_code": 27,
  "cbtn_label": "Cavernous Sinus",
  "ontology_nodes": [
    {"id": "UBERON:0003712", "label": "cavernous sinus"}
  ],
  "preferred_synonyms": [
    "cavernous sinus",
    "parasellar",
    "parasellar region",
    "cavernous",
    "lateral sellar"
  ],
  "notes": "Venous sinus lateral to sella turcica. Contains cranial nerves III, IV, V1, V2, VI. Often invaded by pituitary adenomas or meningiomas."
}
```

#### **NEW CBTN Code 28: Cisterna Magna**
```json
{
  "cbtn_code": 28,
  "cbtn_label": "Cisterna Magna",
  "ontology_nodes": [
    {"id": "UBERON:0004682", "label": "cisterna magna"}
  ],
  "preferred_synonyms": [
    "cisterna magna",
    "cerebellomedullary cistern",
    "posterior cistern",
    "cistern"
  ],
  "notes": "CSF cistern between cerebellum and medulla. Anatomical landmark for posterior fossa tumors."
}
```

#### **NEW CBTN Code 29: Cerebral Spinal Axis (Disseminated)**
```json
{
  "cbtn_code": 29,
  "cbtn_label": "Cerebral Spinal Axis (Disseminated)",
  "ontology_nodes": [
    {"id": "UBERON:0001017", "label": "central nervous system"}
  ],
  "preferred_synonyms": [
    "cerebral spinal access",
    "cerebrospinal axis",
    "cns disseminated",
    "leptomeningeal dissemination",
    "drop metastases",
    "spinal drop mets",
    "neuraxis dissemination"
  ],
  "notes": "Use when tumor has disseminated throughout CNS. Common in medulloblastoma, germinoma, ependymoma. Record specific sites separately."
}
```

#### **NEW CBTN Code 30: Convexity (Cerebral Convexity)**
```json
{
  "cbtn_code": 30,
  "cbtn_label": "Convexity",
  "ontology_nodes": [
    {"id": "UBERON:0002737", "label": "cerebral hemisphere"}
  ],
  "preferred_synonyms": [
    "convexity",
    "cerebral convexity",
    "hemispheric convexity",
    "cortical surface",
    "superficial cortex"
  ],
  "notes": "Outer curved surface of cerebral hemispheres. Common site for extraaxial lesions (meningiomas). Distinguish from lobe-specific involvement."
}
```

#### **NEW CBTN Code 31: Dorsal Exophytic Brainstem**
```json
{
  "cbtn_code": 31,
  "cbtn_label": "Dorsal Exophytic Brainstem",
  "ontology_nodes": [
    {"id": "UBERON:0002308", "label": "brainstem"}
  ],
  "preferred_synonyms": [
    "dorsal exophytic brainstem",
    "dorsal exophytic",
    "exophytic brainstem",
    "dorsally exophytic",
    "fourth ventricular exophytic"
  ],
  "notes": "Brainstem gliomas with exophytic growth into fourth ventricle. Better prognosis than infiltrative diffuse midline glioma. Potentially resectable."
}
```

#### **NEW CBTN Code 32: Brainstem NOS**
```json
{
  "cbtn_code": 32,
  "cbtn_label": "Brainstem NOS",
  "ontology_nodes": [
    {"id": "UBERON:0002308", "label": "brainstem"}
  ],
  "preferred_synonyms": [
    "brainstem",
    "brain stem",
    "brainstem nos",
    "infratentorial brain stem"
  ],
  "notes": "Use when brainstem involved but specific region (pons/midbrain/medulla) not specified. Prefer specific codes (9, 10, 11) when possible."
}
```

#### **Update CBTN Code 17: Other Locations NOS**
Add new preferred synonyms:
```json
{
  "cbtn_code": 17,
  "cbtn_label": "Other locations NOS",
  "ontology_nodes": [],
  "preferred_synonyms": [
    "other",
    "other location",
    "nos",
    "not otherwise specified",
    "unspecified location"
  ],
  "notes": "Retain raw mention for future ontology expansion."
}
```

### Mapping Summary

**Total NEW locations to add**: 8 (codes 25-32)
**Locations already covered**: 32 (via existing CBTN codes with synonym additions)

| Status | Count | Codes |
|--------|-------|-------|
| ✅ Already mapped | 32 | 1-6, 7-23 |
| 🆕 New codes needed | 8 | 25-32 |
| **TOTAL COVERAGE** | **40/40** | **100%** |

---

## 2. Laterality Support

### New Laterality Enum

Add laterality as a separate field (not part of location):

```python
@dataclass
class Laterality:
    """Tumor laterality/sidedness"""
    value: str  # "bilateral", "left", "right", "midline", "unknown"
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    source: str  # "imaging", "operative_note", "pathology"
    source_id: Optional[str] = None
    extracted_at: Optional[str] = None
```

### Laterality Rules

1. **Bilateral**: Tumor crosses midline or involves both hemispheres
2. **Left**: Tumor primarily left hemisphere (even if minimal right involvement)
3. **Right**: Tumor primarily right hemisphere (even if minimal left involvement)
4. **Midline**: Tumor primarily midline structures (corpus callosum, pineal, thalamus, brainstem, ventricles)
5. **Unknown**: Laterality not documented

### Integration with FeatureObject

Laterality is stored SEPARATELY from tumor_location (not part of location ontology):

```json
{
  "clinical_features": {
    "tumor_location": {
      "value": ["Frontal Lobe", "Corpus Callosum"],  // Can be multiple locations
      "sources": [ /* ... */ ],
      "adjudication": { /* ... */ }
    },
    "tumor_laterality": {
      "value": "bilateral",
      "confidence": "HIGH",
      "source": "imaging",
      "source_id": "DiagnosticReport/imaging_20170925",
      "extracted_at": "2025-11-03T10:00:00Z"
    }
  }
}
```

---

## 3. V4 Data Model Integration

### Location as FeatureObject (Layer 2: Clinical Features)

Tumor location follows the V4 FeatureObject pattern with **multi-source support**:

```python
from lib.feature_object import FeatureObject, SourceRecord
from lib.brain_location_normalizer import BrainTumorLocationNormalizer

# Example: Extract tumor location from imaging report
normalizer = BrainTumorLocationNormalizer()
text = "MRI shows heterogeneous mass in the right frontal lobe extending into corpus callosum"

# Normalize to CBTN codes
locations = normalizer.normalise_text(text, min_confidence=0.60, top_n=5)
# Returns: [
#   NormalizedLocation(cbtn_code=1, cbtn_label='Frontal Lobe', confidence=1.0),
#   NormalizedLocation(cbtn_code=25, cbtn_label='Corpus Callosum', confidence=1.0)
# ]

# Create FeatureObject for tumor location
location_feature = FeatureObject.from_single_source(
    value=[loc.cbtn_label for loc in locations],  # List of locations
    source_type="imaging",
    extracted_value=[loc.cbtn_label for loc in locations],
    extraction_method="brain_location_normalizer",
    confidence="HIGH",
    source_id="DiagnosticReport/imaging_20170925",
    raw_text=text
)

# Add CBTN codes and UBERON IDs as metadata
location_feature.metadata = {
    "cbtn_codes": [loc.cbtn_code for loc in locations],
    "uberon_ids": [node.id for loc in locations for node in loc.ontology_nodes],
    "matched_synonyms": [loc.matched_synonym for loc in locations]
}
```

### Multi-Source Location Tracking

Tumor location can change over time (initial tumor → progression → metastasis):

```json
{
  "event_type": "diagnosis",
  "event_date": "2017-09-27",
  "clinical_features": {
    "tumor_location": {
      "value": ["Right Frontal Lobe"],
      "sources": [
        {
          "source_type": "preop_imaging",
          "source_id": "DiagnosticReport/imaging_20170925",
          "extracted_value": ["Right Frontal Lobe"],
          "extraction_method": "brain_location_normalizer",
          "confidence": "HIGH",
          "raw_text": "Large heterogeneous mass in right frontal lobe...",
          "extracted_at": "2025-11-03T10:00:00Z",
          "metadata": {
            "cbtn_codes": [1],
            "uberon_ids": ["UBERON:0001870"]
          }
        }
      ],
      "adjudication": null
    },
    "tumor_laterality": {
      "value": "right",
      "confidence": "HIGH",
      "source": "imaging",
      "source_id": "DiagnosticReport/imaging_20170925"
    }
  }
}
```

### Progression with New Location

When tumor progresses to new anatomical site:

```json
{
  "event_type": "imaging",
  "event_date": "2018-04-15",
  "imaging_purpose": "progression_assessment",
  "clinical_features": {
    "tumor_location": {
      "value": ["Right Frontal Lobe", "Corpus Callosum", "Left Frontal Lobe"],
      "sources": [
        {
          "source_type": "surveillance_imaging",
          "source_id": "DiagnosticReport/imaging_20180415",
          "extracted_value": ["Right Frontal Lobe", "Corpus Callosum", "Left Frontal Lobe"],
          "extraction_method": "brain_location_normalizer",
          "confidence": "HIGH",
          "raw_text": "Tumor has progressed across corpus callosum with new left frontal involvement...",
          "extracted_at": "2025-11-03T11:00:00Z",
          "metadata": {
            "cbtn_codes": [1, 25, 1],
            "uberon_ids": ["UBERON:0001870", "UBERON:0002336", "UBERON:0001870"],
            "progression_status": "NEW_LOCATION"
          }
        }
      ],
      "adjudication": null
    },
    "tumor_laterality": {
      "value": "bilateral",  // Changed from "right"
      "confidence": "HIGH",
      "source": "imaging",
      "source_id": "DiagnosticReport/imaging_20180415"
    }
  }
}
```

### Surgery Event with Location Confirmation

Operative notes confirm/update location:

```json
{
  "event_type": "surgery",
  "event_date": "2018-04-20",
  "clinical_features": {
    "tumor_location": {
      "value": ["Right Frontal Lobe", "Corpus Callosum"],
      "sources": [
        {
          "source_type": "preop_imaging",
          "source_id": "DiagnosticReport/imaging_20180415",
          "extracted_value": ["Right Frontal Lobe", "Corpus Callosum", "Left Frontal Lobe"],
          "extraction_method": "brain_location_normalizer",
          "confidence": "HIGH",
          "extracted_at": "2025-11-03T11:00:00Z"
        },
        {
          "source_type": "operative_note",
          "source_id": "Binary/operative_20180420",
          "extracted_value": ["Right Frontal Lobe", "Corpus Callosum"],
          "extraction_method": "medgemma_llm",
          "confidence": "HIGH",
          "raw_text": "Right frontal craniotomy. Tumor involves right frontal white matter and extends into corpus callosum. Left frontal involvement minimal...",
          "extracted_at": "2025-11-03T12:00:00Z"
        }
      ],
      "adjudication": {
        "final_value": ["Right Frontal Lobe", "Corpus Callosum"],
        "adjudication_method": "operative_note_primary_for_resected_locations",
        "rationale": "Operative note provides direct visualization. Left frontal involvement on imaging was minimal and not surgically addressed.",
        "adjudicated_by": "location_adjudicator_v1",
        "adjudicated_at": "2025-11-03T12:05:00Z",
        "requires_manual_review": false
      }
    },
    "tumor_laterality": {
      "value": "right",
      "confidence": "HIGH",
      "source": "operative_note",
      "source_id": "Binary/operative_20180420"
    }
  }
}
```

---

## 4. Integration Points in V4 Pipeline

### Phase 0: WHO Classification (Lines 1090-1250)

Location is CRITICAL for WHO 2021 classification:

```python
# Examples of location-specific diagnoses:
# - "Diffuse midline glioma, H3 K27-altered" → REQUIRES midline location (thalamus, pons, midbrain)
# - "Diffuse hemispheric glioma, H3 G34-mutant" → REQUIRES hemispheric (cortical) location
# - "Spinal ependymoma, MYCN-amplified" → REQUIRES spinal cord location

from lib.brain_location_normalizer import BrainTumorLocationNormalizer

# Extract tumor location from pathology/imaging
normalizer = BrainTumorLocationNormalizer()
pathology_text = self.pathology_data.get('diagnostic_text', '')
imaging_text = self.imaging_data[0].get('report_conclusion', '') if self.imaging_data else ''

# Normalize locations
path_locations = normalizer.normalise_text(pathology_text, min_confidence=0.60)
img_locations = normalizer.normalise_text(imaging_text, min_confidence=0.60)

# Check for midline locations (for DMG diagnosis validation)
midline_cbtn_codes = [5, 6, 7, 9, 10, 11, 19, 26, 32]  # Thalamus, ventricles, hypothalamus, brainstem, pineal, aqueduct
is_midline = any(loc.cbtn_code in midline_cbtn_codes for loc in path_locations + img_locations)

# Pass to WHO classification
who_classification = self._generate_who_classification(
    molecular_findings=molecular_markers,
    tumor_location=path_locations[0].cbtn_label if path_locations else None,
    is_midline=is_midline,
    patient_age=self.patient_demographics.get('age')
)
```

### Phase 2: Timeline Construction (Lines 1400-1870)

Add location extraction to diagnosis and imaging events:

```python
def _construct_timeline_from_structured_data(self):
    """Construct timeline and extract tumor locations"""

    normalizer = BrainTumorLocationNormalizer()

    # Extract location from diagnosis events
    for event in self.timeline_events:
        if event['event_type'] == 'diagnosis':
            # Try to get location from pathology
            path_text = event.get('pathology_text', '')
            if path_text:
                locations = normalizer.normalise_text(path_text, min_confidence=0.60)
                if locations:
                    event['tumor_location_raw'] = locations[0].cbtn_label
                    event['tumor_location_cbtn'] = locations[0].cbtn_code
                    event['tumor_location_uberon'] = [n.id for n in locations[0].ontology_nodes]

        elif event['event_type'] == 'imaging':
            # Try to get location from imaging conclusion
            img_text = event.get('report_conclusion', '')
            if img_text:
                locations = normalizer.normalise_text(img_text, min_confidence=0.60, top_n=3)
                if locations:
                    event['tumor_location_raw'] = [loc.cbtn_label for loc in locations]
                    event['tumor_location_cbtn'] = [loc.cbtn_code for loc in locations]
```

### Phase 3: Gap Identification (Lines 1910-2430)

Add gap types for missing location:

```python
# NEW gap type: missing_tumor_location
if event['event_type'] in ['diagnosis', 'surgery', 'imaging']:
    if not event.get('tumor_location_raw'):
        gap = {
            'gap_type': 'missing_tumor_location',
            'event_type': event['event_type'],
            'event_date': event['event_date'],
            'priority': 'HIGH' if event['event_type'] in ['diagnosis', 'surgery'] else 'MEDIUM',
            'extraction_source': 'imaging' if event['event_type'] == 'imaging' else 'operative_note',
            'medgemma_target': event.get('diagnostic_report_id') or event.get('procedure_id'),
            'prompt_template': 'tumor_location_extraction'
        }
        self.extraction_gaps.append(gap)
```

### Phase 4: MedGemma Extraction (Lines 2430-3300)

Add location extraction to prompts:

```python
# Enhanced prompt for tumor location extraction
TUMOR_LOCATION_PROMPT = """
Extract the primary tumor location(s) from this clinical document.

INSTRUCTIONS:
1. Extract ALL anatomical locations mentioned for the tumor
2. Use specific anatomical terms (not vague descriptors like "large" or "extensive")
3. Include laterality if mentioned (left, right, bilateral, midline)
4. For multi-focal tumors, list all locations
5. For progression, note NEW locations vs original locations

VALID ANATOMICAL TERMS:
{cbtn_location_list}

LATERALITY OPTIONS:
- bilateral (crosses midline or both hemispheres)
- left (primarily left hemisphere)
- right (primarily right hemisphere)
- midline (corpus callosum, pineal, thalamus, brainstem, ventricles)
- unknown (not specified)

DOCUMENT:
{document_text}

Return JSON:
{{
  "tumor_locations": ["location1", "location2", ...],
  "laterality": "bilateral|left|right|midline|unknown",
  "confidence": "HIGH|MEDIUM|LOW",
  "extraction_method": "explicit|inferred",
  "progression_status": "initial|stable|progression_same_location|progression_new_location"
}}
"""

# Generate CBTN location list for prompt
cbtn_location_list = "\n".join([
    f"- {loc['cbtn_label']} (synonyms: {', '.join(loc['preferred_synonyms'][:5])})"
    for loc in self.ontology_data['tumor_location']
])

# Use in MedGemma extraction
result = self.medgemma_agent.extract(
    prompt=TUMOR_LOCATION_PROMPT.format(
        cbtn_location_list=cbtn_location_list,
        document_text=document_text
    )
)
```

### Phase 4: Integration with FeatureObject (Lines 3300-3600)

Convert extracted locations to FeatureObject:

```python
elif gap_type == 'missing_tumor_location':
    from lib.feature_object import FeatureObject
    from lib.brain_location_normalizer import BrainTumorLocationNormalizer

    normalizer = BrainTumorLocationNormalizer()

    # Get extracted locations (list of strings)
    extracted_locations = extraction_data.get('tumor_locations', [])
    laterality = extraction_data.get('laterality', 'unknown')
    confidence = extraction_data.get('confidence', 'UNKNOWN')

    # Normalize to CBTN codes
    normalized_locations = []
    for loc_text in extracted_locations:
        matches = normalizer.normalise_label(loc_text)
        if matches:
            normalized_locations.append(matches)

    if not normalized_locations:
        logger.warning(f"Could not normalize locations: {extracted_locations}")
        continue

    # Check if event already has location data (from previous extraction)
    existing_location_feature = event.get('tumor_location_v4')

    if existing_location_feature and isinstance(existing_location_feature, dict):
        # MULTI-SOURCE SCENARIO: We have location from another source
        feature = FeatureObject(
            value=existing_location_feature['value'],
            sources=existing_location_feature.get('sources', [])
        )
        feature.add_source(
            source_type=gap.get('extraction_source', 'unknown'),
            extracted_value=[loc.cbtn_label for loc in normalized_locations],
            extraction_method='medgemma_llm',
            confidence=confidence,
            source_id=gap.get('medgemma_target'),
            raw_text=document_text[:200]
        )

        # Check for conflict (different locations from different sources)
        if feature.has_conflict():
            # Adjudicate: Operative note > post-op imaging > pre-op imaging > pathology
            source_priority = {
                'operative_note': 4,
                'postop_imaging': 3,
                'preop_imaging': 2,
                'pathology': 1
            }

            best_source = max(feature.sources, key=lambda s: source_priority.get(s.source_type, 0))
            feature.adjudicate(
                final_value=best_source.extracted_value,
                method='source_priority_operative_note_first',
                rationale=f"Operative note provides direct visualization, prioritized over imaging",
                adjudicated_by='location_adjudicator_v1',
                requires_manual_review=False
            )

        # Store V4 FeatureObject with CBTN codes
        event['tumor_location_v4'] = feature.to_dict()
        event['tumor_location_v4']['metadata'] = {
            'cbtn_codes': [loc.cbtn_code for loc in normalized_locations],
            'uberon_ids': [node.id for loc in normalized_locations for node in loc.ontology_nodes]
        }
        event['tumor_location'] = feature.value  # V3 backward compatibility
    else:
        # SINGLE-SOURCE SCENARIO: First location extraction for this event
        feature = FeatureObject.from_single_source(
            value=[loc.cbtn_label for loc in normalized_locations],
            source_type=gap.get('extraction_source', 'unknown'),
            extracted_value=[loc.cbtn_label for loc in normalized_locations],
            extraction_method='medgemma_llm',
            confidence=confidence,
            source_id=gap.get('medgemma_target'),
            raw_text=document_text[:200]
        )

        # Store V4 FeatureObject with CBTN codes
        event['tumor_location_v4'] = feature.to_dict()
        event['tumor_location_v4']['metadata'] = {
            'cbtn_codes': [loc.cbtn_code for loc in normalized_locations],
            'uberon_ids': [node.id for loc in normalized_locations for node in loc.ontology_nodes]
        }
        event['tumor_location'] = [loc.cbtn_label for loc in normalized_locations]  # V3 backward compatibility

    # Store laterality separately
    event['tumor_laterality'] = {
        'value': laterality,
        'confidence': confidence,
        'source': gap.get('extraction_source'),
        'source_id': gap.get('medgemma_target'),
        'extracted_at': datetime.utcnow().isoformat() + 'Z'
    }

    logger.info(f"Merged tumor location for {event_date}: {[loc.cbtn_label for loc in normalized_locations]} ({laterality})")
    event_merged = True
    break
```

---

## 5. Example Output Artifacts

### Diagnosis Event with Location
```json
{
  "event_id": "evt_20170927_diagnosis_001",
  "event_type": "diagnosis",
  "event_date": "2017-09-27",
  "stage": 1,

  "source": {
    "primary_source": "v_pathology_diagnostics",
    "source_record_id": "path_12345"
  },

  "clinical_features": {
    "tumor_location": {
      "value": ["Right Frontal Lobe"],
      "sources": [
        {
          "source_type": "pathology",
          "source_id": "Observation/path_20170927",
          "extracted_value": ["Right Frontal Lobe"],
          "extraction_method": "brain_location_normalizer",
          "confidence": "HIGH",
          "raw_text": "Specimen labeled 'right frontal tumor'...",
          "extracted_at": "2025-11-03T10:00:00Z"
        }
      ],
      "adjudication": null,
      "metadata": {
        "cbtn_codes": [1],
        "uberon_ids": ["UBERON:0001870"],
        "matched_synonyms": ["right frontal"]
      }
    },

    "tumor_laterality": {
      "value": "right",
      "confidence": "HIGH",
      "source": "pathology",
      "source_id": "Observation/path_20170927",
      "extracted_at": "2025-11-03T10:00:00Z"
    }
  },

  "relationships": {
    "ordinality": {
      "diagnosis_number": 1,
      "diagnosis_label": "Initial diagnosis"
    },
    "related_events": {
      "preop_imaging": ["evt_20170925_imaging_001"],
      "surgery": ["evt_20170927_surgery_001"]
    }
  },

  "tumor_location": "Right Frontal Lobe",  // V3 backward compatibility
  "description": "Astrocytoma, IDH-mutant, CNS WHO grade 3"
}
```

### Progression Imaging with New Location
```json
{
  "event_id": "evt_20180415_imaging_010",
  "event_type": "imaging",
  "event_date": "2018-04-15",
  "stage": 3,

  "clinical_features": {
    "tumor_location": {
      "value": ["Right Frontal Lobe", "Corpus Callosum", "Left Frontal Lobe"],
      "sources": [
        {
          "source_type": "surveillance_imaging",
          "source_id": "DiagnosticReport/imaging_20180415",
          "extracted_value": ["Right Frontal Lobe", "Corpus Callosum", "Left Frontal Lobe"],
          "extraction_method": "medgemma_llm",
          "confidence": "HIGH",
          "raw_text": "Tumor has progressed across corpus callosum with new left frontal involvement...",
          "extracted_at": "2025-11-03T11:00:00Z"
        }
      ],
      "adjudication": null,
      "metadata": {
        "cbtn_codes": [1, 25, 1],
        "uberon_ids": ["UBERON:0001870", "UBERON:0002336", "UBERON:0001870"],
        "progression_status": "NEW_LOCATION",
        "new_locations": ["Corpus Callosum", "Left Frontal Lobe"]
      }
    },

    "tumor_laterality": {
      "value": "bilateral",
      "confidence": "HIGH",
      "source": "imaging",
      "source_id": "DiagnosticReport/imaging_20180415",
      "extracted_at": "2025-11-03T11:00:00Z"
    },

    "rano_assessment": {
      "value": "PD",  // Progressive Disease
      "sources": [ /* ... */ ]
    }
  },

  "relationships": {
    "imaging_context": {
      "imaging_purpose": "progression_assessment",
      "days_from_prior_imaging": 180,
      "days_from_diagnosis": 566
    }
  }
}
```

---

## 6. Implementation Plan

### Phase 1: Update Ontology (1-2 hours)
1. ✅ Map user-provided locations to existing CBTN codes
2. 🆕 Add 8 new CBTN codes (25-32) to `brain_tumor_location_ontology.json`
3. 🆕 Add laterality synonyms to existing codes
4. ✅ Verify UBERON ID mappings

### Phase 2: Enhance Location Normalizer (2-3 hours)
1. 🆕 Add laterality extraction to `BrainTumorLocationNormalizer`
2. 🆕 Add multi-location support (return list instead of single)
3. 🆕 Add progression detection (NEW_LOCATION vs stable)
4. ✅ Test with sample clinical texts

### Phase 3: V4 Integration (4-6 hours)
1. 🆕 Add tumor location extraction to Phase 0 (WHO classification)
2. 🆕 Add tumor location extraction to Phase 2 (timeline construction)
3. 🆕 Add `missing_tumor_location` gap type to Phase 3
4. 🆕 Add tumor location extraction prompts to Phase 4
5. 🆕 Implement FeatureObject integration for tumor location
6. 🆕 Add adjudication logic (operative note > imaging > pathology)

### Phase 4: Testing & Validation (3-4 hours)
1. 🆕 Test with patient eQSB0y3q (known right frontal location)
2. 🆕 Test with midline DMG patient (pons/thalamus)
3. 🆕 Test with progression patient (NEW_LOCATION detection)
4. 🆕 Validate CBTN code mappings
5. 🆕 Validate multi-source adjudication

---

## 7. Usage Examples

### Example 1: Extract Location from Imaging Report
```python
from lib.brain_location_normalizer import BrainTumorLocationNormalizer

normalizer = BrainTumorLocationNormalizer()

text = "MRI Brain shows heterogeneous mass in right frontal lobe extending into corpus callosum with minimal left frontal edema"

locations = normalizer.normalise_text(text, min_confidence=0.60, top_n=5)

for loc in locations:
    print(f"Location: {loc.cbtn_label} (CBTN: {loc.cbtn_code})")
    print(f"  Confidence: {loc.confidence}")
    print(f"  Matched: {loc.matched_synonym}")
    print(f"  UBERON: {', '.join([n.id for n in loc.ontology_nodes])}")

# Output:
# Location: Frontal Lobe (CBTN: 1)
#   Confidence: 1.0
#   Matched: frontal lobe
#   UBERON: UBERON:0001870
# Location: Corpus Callosum (CBTN: 25)
#   Confidence: 1.0
#   Matched: corpus callosum
#   UBERON: UBERON:0002336
```

### Example 2: WHO Classification with Location Validation
```python
# DMG diagnosis REQUIRES midline location
who_diagnosis = "Diffuse midline glioma, H3 K27-altered"
molecular_markers = ["H3F3A_K27M"]

# Extract location from imaging
imaging_text = "Tumor centered in pons with extension to midbrain"
locations = normalizer.normalise_text(imaging_text)

# Validate midline location
midline_codes = [5, 6, 7, 9, 10, 11, 19, 26, 32]
is_midline = any(loc.cbtn_code in midline_codes for loc in locations)

if "midline glioma" in who_diagnosis and not is_midline:
    logger.warning(f"⚠️  WHO diagnosis says 'midline glioma' but location is {locations[0].cbtn_label}")
    logger.warning(f"   Expected midline locations: thalamus, hypothalamus, pons, midbrain, medulla, pineal")
```

### Example 3: Track Location Over Time
```python
# Initial diagnosis (2017-09-27)
initial_locations = ["Right Frontal Lobe"]

# Progression imaging (2018-04-15)
progression_locations = ["Right Frontal Lobe", "Corpus Callosum", "Left Frontal Lobe"]

# Detect new locations
new_locations = [loc for loc in progression_locations if loc not in initial_locations]
print(f"New locations at progression: {new_locations}")
# Output: New locations at progression: ['Corpus Callosum', 'Left Frontal Lobe']

# Update laterality
initial_laterality = "right"
progression_laterality = "bilateral"
print(f"Laterality change: {initial_laterality} → {progression_laterality}")
```

---

## 8. Benefits of This Integration

1. **Research Interoperability**: UBERON ontology mappings enable cross-study analysis
2. **WHO 2021 Compliance**: Location-specific diagnoses (DMG, spinal ependymoma) properly validated
3. **Temporal Tracking**: Captures tumor progression to new anatomical sites
4. **Multi-Source Validation**: Operative notes confirm imaging-based locations
5. **Complete Provenance**: Every location has source attribution and confidence
6. **Query Optimization**: CBTN codes enable efficient location-based queries
7. **Clinical Decision Support**: Laterality informs surgical planning

---

## 9. Next Steps

1. **Update ontology file** with 8 new CBTN codes (25-32)
2. **Enhance brain_location_normalizer.py** with laterality support
3. **Integrate into V4 pipeline** (Phase 0, 2, 3, 4)
4. **Test with real patients** (right frontal, pons DMG, progression cases)
5. **Document extraction prompts** for tumor location
6. **Create adjudication rules** for conflicting locations

---

**Status**: Design specification ready for implementation
**Estimated Implementation Time**: 10-15 hours
**Dependencies**: V4 FeatureObject pattern (already implemented)
**Priority**: HIGH (enables WHO 2021 location-specific diagnoses)
