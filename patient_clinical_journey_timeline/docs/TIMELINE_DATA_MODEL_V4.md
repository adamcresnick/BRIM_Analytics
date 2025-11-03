# Patient Timeline Data Model V4 - Design Specification

## Executive Summary

This document proposes an optimized data model for the Patient Clinical Journey Timeline that follows data science best practices for:
- **Separation of concerns** (core event metadata vs. clinical features vs. relationships)
- **Provenance tracking** (source attribution for every feature)
- **Extensibility** (easy to add new features without schema changes)
- **Relationship modeling** (explicit ordinality, parent-child relationships)
- **Adjudication support** (multiple sources for same feature with conflict resolution)

---

## Design Principles

### 1. **Three-Layer Architecture**
```
Layer 1: Core Event Metadata (immutable, from structured data)
Layer 2: Clinical Features (mutable, from AI extraction + adjudication)
Layer 3: Relationships & Context (computed, from post-processing)
```

### 2. **Feature Provenance**
Every extracted feature tracks:
- Source (operative_note, postop_imaging, progress_note)
- Extraction method (medgemma, regex, structured_field)
- Confidence score
- Timestamp of extraction

### 3. **Multi-Source Adjudication**
When multiple sources provide conflicting information:
- Store ALL sources
- Apply adjudication logic
- Track final determination + rationale

### 4. **Explicit Relationships**
- Treatment ordinality (surgery #1, 1st-line chemo)
- Parent-child relationships (postop imaging → surgery)
- WHO protocol alignment (upfront vs. salvage)

---

## Schema Design

### Root Timeline Structure

```json
{
  "patient_id": "string",
  "who_2021_classification": {...},
  "patient_demographics": {...},

  "timeline_events": [
    // Array of Event objects (see below)
  ],

  "relationships": {
    // Cross-event relationships
    "imaging_to_surgery_mapping": [...],
    "treatment_sequences": {...}
  },

  "extraction_report": {...},
  "protocol_validations": {...}
}
```

---

## Event Object Schema

### Core Structure (3 Layers)

```json
{
  // ========================================================================
  // LAYER 1: CORE EVENT METADATA (immutable, from structured data)
  // ========================================================================
  "event_id": "evt_20170927_surgery_001",  // Unique identifier
  "event_type": "surgery",  // Enum: surgery, chemotherapy_start/end, radiation_start/end, imaging, visit
  "event_date": "2017-09-27",  // Primary date for timeline sorting
  "event_datetime": "2017-09-27T14:30:00Z",  // Full ISO-8601 if available
  "event_sequence": 42,  // Global chronological sequence number
  "stage": 2,  // Pipeline stage that created this event (0-6)

  "source": {
    "primary_source": "v_procedures",  // Where core event came from
    "source_record_id": "proc_12345",  // FK to source table
    "source_timestamp": "2025-11-03T10:00:00Z"  // When extracted
  },

  // ========================================================================
  // LAYER 2: CLINICAL FEATURES (mutable, from extraction + adjudication)
  // ========================================================================
  "clinical_features": {
    // Each feature is a FeatureObject (see below)
    "extent_of_resection": {
      "value": "STR",
      "sources": [
        {
          "source_type": "operative_note",
          "source_id": "Binary/abc123",
          "extracted_value": "STR",
          "extraction_method": "medgemma",
          "confidence": "MEDIUM",
          "raw_text": "Sonopet was used to debulk part of the lesion...",
          "extracted_at": "2025-11-03T10:15:00Z"
        },
        {
          "source_type": "postop_imaging",
          "source_id": "DiagnosticReport/def456",
          "extracted_value": "NTR",  // CONFLICT with op note!
          "extraction_method": "medgemma",
          "confidence": "HIGH",
          "raw_text": "Minimal residual enhancement, approximately 5-10% residual tumor volume",
          "extracted_at": "2025-11-03T10:20:00Z"
        }
      ],
      "adjudication": {
        "final_value": "STR",
        "adjudication_method": "favor_imaging_if_high_confidence",
        "rationale": "Imaging provides objective volumetric assessment but confidence was not high enough to override surgeon assessment",
        "adjudicated_by": "orchestrator_agent",
        "adjudicated_at": "2025-11-03T10:25:00Z",
        "requires_manual_review": true
      }
    },

    "tumor_site": {
      "value": "right frontal lobe",
      "sources": [
        {
          "source_type": "operative_note",
          "source_id": "Binary/abc123",
          "extracted_value": "right frontal lobe",
          "extraction_method": "medgemma",
          "confidence": "HIGH",
          "extracted_at": "2025-11-03T10:15:00Z"
        }
      ],
      "adjudication": null  // Only one source, no adjudication needed
    }
  },

  // ========================================================================
  // LAYER 3: RELATIONSHIPS & CONTEXT (computed, from post-processing)
  // ========================================================================
  "relationships": {
    "ordinality": {
      "surgery_number": 1,
      "surgery_label": "Initial resection",
      "relative_to_diagnosis": "primary_surgery"
    },

    "related_events": {
      "postop_imaging": ["evt_20170929_imaging_005"],  // Event IDs
      "preop_imaging": ["evt_20170925_imaging_003"],
      "pathology_reports": ["evt_20170927_path_042"]
    },

    "protocol_context": {
      "who_expected": true,  // Is this surgery expected per WHO 2021?
      "timing_category": "upfront",  // upfront, re-resection, salvage
      "days_from_diagnosis": 0
    }
  },

  // ========================================================================
  // LEGACY/TYPE-SPECIFIC ATTRIBUTES (backward compatibility)
  // ========================================================================
  "surgery_type": "craniotomy",  // Kept for backward compatibility
  "proc_performed_datetime": "2017-09-27 14:30:00.000",
  "description": "Craniotomy with tumor resection"
}
```

---

## FeatureObject Schema

Every clinical feature follows this structure:

```json
{
  "value": "any",  // Final determined value
  "sources": [
    {
      "source_type": "operative_note | postop_imaging | progress_note | structured_field",
      "source_id": "string",  // Document/record ID
      "extracted_value": "any",  // What this source said
      "extraction_method": "medgemma | regex | structured_field | manual",
      "confidence": "HIGH | MEDIUM | LOW",
      "raw_text": "string",  // Exact text extracted from (for audit)
      "extracted_at": "ISO-8601 timestamp"
    }
  ],
  "adjudication": {
    "final_value": "any",  // Result of adjudication (may differ from .value)
    "adjudication_method": "string",  // Which logic was applied
    "rationale": "string",  // Why this value was chosen
    "adjudicated_by": "orchestrator_agent | manual_review",
    "adjudicated_at": "ISO-8601 timestamp",
    "requires_manual_review": boolean
  } | null
}
```

---

## Event Type-Specific Extensions

### Surgery Events

```json
{
  "event_type": "surgery",
  "clinical_features": {
    "extent_of_resection": FeatureObject,  // GTR, NTR, STR, BIOPSY
    "percent_resection": FeatureObject,  // 0-100
    "tumor_site": FeatureObject,
    "surgeon_assessment": FeatureObject,
    "residual_tumor": FeatureObject,  // yes, no, unclear
    "complications": FeatureObject  // Future: extract complications
  },
  "relationships": {
    "ordinality": {
      "surgery_number": 1,
      "surgery_label": "Initial resection | Re-resection | Salvage surgery",
      "relative_to_diagnosis": "primary_surgery | progression_surgery",
      "days_from_prior_surgery": 0 | number
    }
  }
}
```

### Chemotherapy Events

```json
{
  "event_type": "chemotherapy_start",
  "clinical_features": {
    "agent_names": FeatureObject,  // ["temozolomide"] or ["nivolumab"]
    "protocol_name": FeatureObject,  // "PNOC 007"
    "on_protocol_status": FeatureObject,  // "on_protocol" | "off_protocol" | "treated_like_protocol"
    "change_in_therapy_reason": FeatureObject,  // "progression" | "toxicity" | "completion"
    "dose": FeatureObject,  // Future: extract dosing
    "route": FeatureObject  // Future: oral, IV, intrathecal
  },
  "relationships": {
    "ordinality": {
      "treatment_line": 1,
      "treatment_line_label": "First-line chemotherapy",
      "reason_for_change_from_prior": null | "progression" | "toxicity" | "completion",
      "days_from_prior_line": 0 | number
    },
    "related_events": {
      "chemotherapy_end": "evt_20171019_chemoend_045",
      "response_imaging": ["evt_20171115_imaging_050"]
    }
  }
}
```

### Radiation Events

```json
{
  "event_type": "radiation_start",
  "clinical_features": {
    "radiation_type": FeatureObject,  // "focal" | "craniospinal" | "whole_ventricular"
    "total_dose_cgy": FeatureObject,
    "radiation_fields": FeatureObject,
    "fractionation": FeatureObject,  // Future: extract fractions
    "concurrent_chemotherapy": FeatureObject  // Future: identify concurrent therapy
  },
  "relationships": {
    "ordinality": {
      "radiation_course_number": 1,
      "radiation_course_label": "Upfront radiation | Re-irradiation",
      "radiation_context": "adjuvant" | "salvage" | "palliative",
      "days_from_surgery": 30
    },
    "related_events": {
      "radiation_end": "evt_20171220_radend_080",
      "simulation_imaging": ["evt_20171025_imaging_070"]
    }
  }
}
```

### Imaging Events

```json
{
  "event_type": "imaging",
  "clinical_features": {
    "rano_assessment": FeatureObject,  // CR, PR, SD, PD
    "tumor_measurements": FeatureObject,  // Structured lesion data
    "new_lesions": FeatureObject,  // yes, no
    "radiologist_impression": FeatureObject
  },
  "relationships": {
    "imaging_context": {
      "imaging_purpose": "baseline" | "postop" | "surveillance" | "response_assessment" | "progression",
      "days_from_surgery": null | number,
      "days_from_chemo_start": null | number,
      "days_from_prior_imaging": null | number
    },
    "related_events": {
      "associated_surgery": "evt_20170927_surgery_001",  // If postop imaging
      "prior_imaging_for_comparison": "evt_20170825_imaging_001"
    }
  }
}
```

---

## Relationships Schema

Cross-event relationships stored at timeline root level:

```json
{
  "relationships": {
    "imaging_to_surgery_mapping": [
      {
        "imaging_event_id": "evt_20170929_imaging_005",
        "imaging_type": "postop",
        "surgery_event_id": "evt_20170927_surgery_001",
        "days_after_surgery": 2,
        "provides_eor_evidence": true
      }
    ],

    "treatment_sequences": {
      "surgeries": [
        {
          "event_id": "evt_20170927_surgery_001",
          "surgery_number": 1,
          "surgery_context": "primary",
          "eor": "STR"
        }
      ],

      "chemotherapy_lines": [
        {
          "line_number": 1,
          "start_event_id": "evt_20171005_chemostart_030",
          "end_event_id": "evt_20171019_chemoend_045",
          "agents": ["temozolomide"],
          "protocol": "PNOC 007",
          "outcome": "progression",
          "duration_days": 14
        },
        {
          "line_number": 2,
          "start_event_id": "evt_20180405_chemostart_120",
          "end_event_id": "evt_20180410_chemoend_125",
          "agents": ["nivolumab"],
          "protocol": "off_protocol",
          "reason_for_change": "progression",
          "outcome": "progression",
          "duration_days": 5
        }
      ],

      "radiation_courses": [
        {
          "course_number": 1,
          "start_event_id": "evt_20171102_radstart_060",
          "end_event_id": "evt_20171220_radend_080",
          "radiation_context": "adjuvant",
          "days_from_surgery": 36,
          "institution": "external"  // If from TIFF
        }
      ]
    }
  }
}
```

---

## Benefits of This Model

### 1. **Clean Separation of Concerns**
- Core event data (Layer 1) never polluted with extracted features
- Clinical features (Layer 2) clearly separated from relationships (Layer 3)
- Easy to query "show me all structured vs. extracted data"

### 2. **Full Provenance Tracking**
- Every feature value traceable to source document
- Confidence scores at feature level (not just event level)
- Audit trail for adjudication decisions

### 3. **Multi-Source Support**
- Operative note says "STR", imaging says "NTR" → BOTH captured
- Orchestrator adjudicates conflict → Final value + rationale recorded
- Manual review flag if confidence low

### 4. **Explicit Ordinality**
```python
# Easy queries:
surgeries = [e for e in events if e['relationships']['ordinality']['surgery_number'] == 1]
second_line_chemo = [e for e in events if e['relationships']['ordinality']['treatment_line'] == 2]
```

### 5. **Extensibility**
Add new features without schema changes:
```python
event['clinical_features']['new_feature'] = FeatureObject(...)
```

### 6. **Relationship Queries**
```python
# Find postop imaging for surgery
surgery_id = "evt_20170927_surgery_001"
postop_imaging_ids = surgery['relationships']['related_events']['postop_imaging']
postop_images = [get_event(id) for id in postop_imaging_ids]
```

---

## Implementation Strategy

### Phase 1: Add Layer 2 & 3 to Existing Events (Non-Breaking)
- Keep existing flat attributes for backward compatibility
- Add `clinical_features` and `relationships` dicts
- Populate both old and new structures

### Phase 2: Migrate Extraction Logic
- Update `_integrate_extraction_into_timeline` to create FeatureObjects
- Add multi-source tracking
- Implement adjudication logic

### Phase 3: Add Treatment Ordinality (Phase 2.5)
- Compute surgery_number, treatment_line, radiation_course_number
- Populate `relationships.ordinality` for all events

### Phase 4: Deprecate Flat Attributes
- After validation period, remove flat attributes
- Keep only Layer 1, 2, 3 structure

---

## Example: Complete Surgery Event

```json
{
  "event_id": "evt_20170927_surgery_001",
  "event_type": "surgery",
  "event_date": "2017-09-27",
  "event_datetime": "2017-09-27T14:30:00Z",
  "event_sequence": 42,
  "stage": 2,

  "source": {
    "primary_source": "v_procedures",
    "source_record_id": "proc_12345",
    "source_timestamp": "2025-11-03T10:00:00Z"
  },

  "clinical_features": {
    "extent_of_resection": {
      "value": "STR",
      "sources": [
        {
          "source_type": "operative_note",
          "source_id": "Binary/fXLuketL2LH-2JH38J7G9Ll7iKY0kGnEwT-G0kks8cJY4",
          "extracted_value": "STR",
          "extraction_method": "medgemma",
          "confidence": "MEDIUM",
          "raw_text": "Sonopet was used to debulk part of the lesion and to send multiple biopsies.",
          "extracted_at": "2025-11-03T10:15:00Z"
        },
        {
          "source_type": "postop_imaging",
          "source_id": "DiagnosticReport/imaging_20170929",
          "extracted_value": "Minimal residual enhancement",
          "extraction_method": "medgemma",
          "confidence": "MEDIUM",
          "raw_text": "Post-operative changes with minimal residual enhancement in the surgical bed",
          "extracted_at": "2025-11-03T10:20:00Z"
        }
      ],
      "adjudication": {
        "final_value": "STR",
        "adjudication_method": "surgeon_assessment_primary_if_imaging_ambiguous",
        "rationale": "Imaging description 'minimal residual' is ambiguous (could be STR or NTR). Surgeon explicitly stated debulking with residual tumor. Final determination: STR.",
        "adjudicated_by": "orchestrator_agent",
        "adjudicated_at": "2025-11-03T10:25:00Z",
        "requires_manual_review": false
      }
    },

    "tumor_site": {
      "value": "right frontal lobe",
      "sources": [
        {
          "source_type": "operative_note",
          "source_id": "Binary/fXLuketL2LH-2JH38J7G9Ll7iKY0kGnEwT-G0kks8cJY4",
          "extracted_value": "right frontal lobe",
          "extraction_method": "medgemma",
          "confidence": "HIGH",
          "extracted_at": "2025-11-03T10:15:00Z"
        }
      ],
      "adjudication": null
    }
  },

  "relationships": {
    "ordinality": {
      "surgery_number": 1,
      "surgery_label": "Initial resection",
      "relative_to_diagnosis": "primary_surgery"
    },

    "related_events": {
      "postop_imaging": ["evt_20170929_imaging_005", "evt_20171010_imaging_008"],
      "preop_imaging": ["evt_20170925_imaging_003"],
      "pathology_reports": ["evt_20170927_path_042"]
    },

    "protocol_context": {
      "who_expected": true,
      "timing_category": "upfront",
      "days_from_diagnosis": 0
    }
  },

  "surgery_type": "craniotomy",
  "proc_performed_datetime": "2017-09-27 14:30:00.000",
  "description": "Craniotomy with tumor resection"
}
```

---

## Next Steps

1. **Review & Approve** this data model design
2. **Implement FeatureObject class** in Python with validation
3. **Update extraction logic** to create FeatureObjects
4. **Add adjudication module** for EOR conflicts
5. **Implement Phase 2.5** (treatment ordinality)
6. **Test with current patient** and validate backward compatibility

