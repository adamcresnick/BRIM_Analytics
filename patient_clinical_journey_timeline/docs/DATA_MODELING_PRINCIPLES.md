# Data Modeling Principles - Patient Clinical Journey Timeline

## Document Purpose
This document captures the core data modeling principles and architectural patterns used throughout the Patient Clinical Journey Timeline system. It serves as a reference for understanding how we structure, track, and validate clinical data across the pipeline.

---

## Core Data Modeling Philosophy

### 1. **Multi-Layer Architecture with Provenance**

We use a **three-layer architecture** that separates concerns while maintaining full provenance tracking:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Core Event Metadata (Immutable)                   │
│  - Source: Structured FHIR data from Athena views          │
│  - Contains: event_type, event_date, source_record_id      │
│  - Immutable once created from structured data             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Clinical Features (Mutable, Multi-Source)         │
│  - Source: AI extraction (MedGemma) + manual adjudication  │
│  - Contains: extent_of_resection, tumor_location, etc.     │
│  - Each feature tracks ALL sources with confidence scores  │
│  - Supports adjudication when sources conflict             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Relationships & Context (Computed)                │
│  - Source: Post-processing algorithms                       │
│  - Contains: treatment_ordinality, timing_context          │
│  - Explicit parent-child relationships                     │
│  - WHO 2021 protocol alignment indicators                  │
└─────────────────────────────────────────────────────────────┘
```

**Key Principle**: Each layer builds on the previous, with clear separation of concerns and full traceability.

---

## 2. **FeatureObject Pattern: Multi-Source Provenance**

Every extracted clinical feature uses the **FeatureObject** pattern to track multiple sources:

```python
{
  "extent_of_resection": {
    "value": "STR",  # Final adjudicated value
    "sources": [
      {
        "source_type": "binary_document",
        "source_id": "DocumentReference/xyz",
        "extracted_value": "STR",
        "extraction_method": "medgemma",
        "confidence": "HIGH",
        "extracted_at": "2025-11-04T10:00:00Z"
      },
      {
        "source_type": "structured_fhir",
        "source_id": "Procedure/abc",
        "extracted_value": "Subtotal resection",
        "extraction_method": "fhir_field_mapping",
        "confidence": "MEDIUM",
        "extracted_at": "2025-11-04T09:00:00Z"
      }
    ],
    "adjudication": {
      "method": "confidence_weighted",
      "rationale": "Binary document extraction had higher confidence"
    }
  }
}
```

**Why This Matters**:
- **Transparency**: Every value can be traced back to its original source(s)
- **Adjudication Support**: When sources conflict, we can see all perspectives
- **Quality Assurance**: Confidence scores enable filtering by extraction reliability
- **Audit Trail**: Full history of when and how each value was determined

---

## 3. **Date Handling: Normalization at Source**

**Problem**: Clinical systems produce mixed date formats:
- Date-only: `"2018-08-07"`
- DateTime: `"2018-08-07T14:30:00Z"`
- Partial: `"2018-08"` (month/year only)

**Solution**: Normalize dates as early as possible in the pipeline:

```python
# MedGemma Agent: Normalize immediately after extraction
def _normalize_dates(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert date-only strings to ISO datetime format"""
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    for key, value in data.items():
        if isinstance(value, str) and date_pattern.match(value):
            data[key] = f"{value}T00:00:00"  # Athena-compatible format

    return data
```

**Key Principles**:
1. **Normalize at extraction point** - Don't propagate inconsistent formats
2. **Preserve precision** - Date-only becomes midnight (`T00:00:00`), not arbitrary time
3. **Document assumptions** - Midnight implies "date only, time unknown"
4. **Athena compatibility** - Use ISO 8601 format for TIMESTAMP operations

---

## 4. **Treatment Ordinality: Explicit Sequencing**

We explicitly track treatment sequences rather than inferring them:

```python
{
  "event_type": "surgery",
  "event_date": "2017-09-27",
  "treatment_ordinality": {
    "surgery_number": 1,           # First surgery
    "surgery_label": "Initial resection",
    "timing_context": "upfront"    # Before any other treatment
  }
}

{
  "event_type": "chemotherapy_start",
  "event_date": "2017-10-05",
  "treatment_ordinality": {
    "line_number": 1,              # First-line chemotherapy
    "line_label": "1st-line",
    "timing_context": "adjuvant",  # After surgery, per WHO protocol
    "relative_to_surgery": 8       # Days after surgery #1
  }
}
```

**Why Explicit Ordinality Matters**:
- **WHO 2021 Protocol Validation**: Can verify "adjuvant chemo after surgery" requirements
- **Temporal Reasoning**: Understand treatment sequences without date arithmetic
- **Outcome Analysis**: Compare outcomes by treatment line (1st vs 2nd-line chemo)
- **Quality Metrics**: Track adherence to standard-of-care treatment sequences

---

## 5. **Binary Document Tracking: Full Lifecycle**

We track the complete lifecycle of binary document processing:

```python
{
  "extraction_report": {
    "binary_fetch_stats": {
      "attempted": 7,          # Total documents we tried to fetch
      "successful": 5,         # Successfully extracted text
      "success_rate": 0.714,   # 71.4% success rate
      "fetched": [
        {
          "binary_id": "Binary/xyz",
          "content_type": "image/tiff",
          "extraction_method": "aws_textract_ocr",
          "text_length": 1481,
          "timestamp": "2025-11-04T12:00:15Z",
          "success": true
        },
        {
          "binary_id": "Binary/abc",
          "content_type": "application/pdf",
          "extraction_method": "pdfplumber",
          "error": "Corrupted PDF header",
          "timestamp": "2025-11-04T12:00:30Z",
          "success": false
        }
      ]
    }
  }
}
```

**Key Tracking Points**:
1. **Attempted fetches** - Total documents we tried to process
2. **Successful extractions** - Documents where we got usable text
3. **Failure reasons** - Why specific documents failed (OCR error, missing file, etc.)
4. **Success rate** - Overall pipeline health metric

**Why This Matters**:
- **Pipeline Observability**: Know exactly what's working and what's failing
- **Error Diagnosis**: Trace failures to specific documents and error types
- **Performance Metrics**: Track extraction efficiency over time
- **Cost Monitoring**: AWS Textract calls are billable - track usage

---

## 6. **Gap Identification: Structured Deficit Tracking**

We explicitly track **what clinical data is missing** and **where we should look for it**:

```python
{
  "extraction_gaps": [
    {
      "gap_id": "gap_surgery_20170927_eor",
      "gap_type": "missing_eor",              # Extent of resection missing
      "event_id": "evt_20170927_surgery_001",
      "event_date": "2017-09-27",
      "priority": "HIGH",                      # EOR is critical for outcomes
      "recommended_documents": [
        {
          "doc_type": "operative_note",
          "tier": 1,
          "search_strategy": "encounter_based",
          "found": true,
          "document_id": "DocumentReference/xyz"
        },
        {
          "doc_type": "postop_clinical_note",
          "tier": 2,
          "search_strategy": "temporal_fallback",
          "found": false
        }
      ]
    }
  ]
}
```

**Key Principles**:
1. **Explicit gaps** - Don't silently skip missing data
2. **Prioritized extraction** - HIGH priority gaps get processed first
3. **Multi-tier search** - Try multiple document types in priority order
4. **Success tracking** - Record whether each search strategy succeeded

---

## 7. **Schema Tracking: Query Audit Trail**

We track every Athena view query to understand data flow:

```python
{
  "extraction_report": {
    "schemas_queried": [
      {
        "schema_name": "v_pathology_diagnostics",
        "query_timestamp": "2025-11-04T11:36:58Z",
        "row_count": 21675,
        "fields": ["patient_fhir_id", "diagnostic_date", "diagnostic_name", "result_value"],
        "query_duration_ms": 8234
      },
      {
        "schema_name": "v_procedures_tumor",
        "query_timestamp": "2025-11-04T11:47:14Z",
        "row_count": 3,
        "fields": ["procedure_fhir_id", "proc_performed_date_time", "surgery_type"],
        "query_duration_ms": 120
      }
    ],
    "total_schemas_queried": 6
  }
}
```

**Why Track Schema Queries**:
- **Performance Analysis**: Identify slow queries (v_pathology takes 8+ seconds)
- **Data Lineage**: Know exactly which Athena views contributed to the timeline
- **Debugging**: When data looks wrong, trace back to the source query
- **Cost Monitoring**: Athena charges by data scanned - track query volumes

---

## 8. **WHO 2021 Protocol Validation: Evidence-Based QA**

We validate actual patient care against WHO 2021 evidence-based protocols:

```python
{
  "protocol_validations": [
    {
      "diagnosis": "Astrocytoma, IDH-mutant, CNS WHO grade 3",
      "patient_age": 20,
      "expected_protocol": {
        "surgery": "Maximal safe resection recommended",
        "radiation": "Radiation therapy typically recommended after surgery",
        "chemotherapy": "TMZ chemotherapy often used with radiation"
      },
      "actual_care": {
        "surgery": {
          "performed": true,
          "date": "2017-09-27",
          "eor": "STR",
          "adherence": "PARTIAL",  # STR instead of GTR
          "note": "Subtotal resection performed (not maximal)"
        },
        "radiation": {
          "performed": true,
          "start_date": "2017-11-02",
          "timing": "adjuvant",
          "adherence": "COMPLIANT"
        },
        "chemotherapy": {
          "performed": true,
          "start_date": "2017-10-05",
          "timing": "concurrent_with_radiation",
          "adherence": "COMPLIANT"
        }
      },
      "validation_timestamp": "2025-11-04T12:08:04Z",
      "confidence": 0.8
    }
  ]
}
```

**Key Validation Dimensions**:
1. **Expected vs Actual**: What WHO recommends vs what patient received
2. **Timing Validation**: Was treatment sequenced correctly per protocol?
3. **Adherence Scoring**: COMPLIANT, PARTIAL, NON_COMPLIANT, UNKNOWN
4. **Clinical Context**: Age-appropriate dosing, contraindications noted

---

## 9. **Extraction Validation: Two-Agent Quality Control**

We use a **two-agent validation pattern** to ensure extraction quality:

### Agent 1: Extraction Agent (MedGemma)
Extracts clinical features from documents

### Agent 2: Validation Agent (Python Logic)
Validates extracted data for:
- **Required fields present**: All mandatory fields extracted
- **Data type correctness**: Numeric values are numbers, dates are dates
- **Value plausibility**: Dose in reasonable range (0-10000 cGy)
- **Semantic consistency**: EOR value is valid (GTR/NTR/STR/Biopsy)

```python
def _validate_extraction_result(self, result, gap_type):
    errors = []

    # Check required fields
    required = required_fields.get(gap_type, [])
    for field in required:
        if field not in result or result[field] is None:
            errors.append(f"Missing required field: {field}")

    # Semantic validation
    if gap_type == 'missing_radiation_dose':
        dose = result.get('total_dose_cgy')
        if dose and (dose < 0 or dose > 10000):
            errors.append(f"Dose out of range: {dose} cGy")

    return len(errors) == 0, errors
```

**When Validation Fails**:
- **Agent 1 is asked to retry** with specific guidance about missing/invalid fields
- **Up to 3 attempts** before marking extraction as failed
- **All attempts logged** for quality analysis

---

## 10. **Data Type Standards**

### Dates and Times
- **Storage Format**: ISO 8601 with timezone (`"2017-09-27T14:30:00Z"`)
- **Date-Only**: Append `T00:00:00` for Athena compatibility
- **Partial Dates**: Store as string with precision note (`"2018-Q1"` with `precision: "quarter"`)

### Confidence Scores
- **Scale**: String enum: `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"UNKNOWN"`
- **Interpretation**:
  - `HIGH`: Structured FHIR field or validated extraction
  - `MEDIUM`: AI extraction without validation
  - `LOW`: Inferred or ambiguous source
  - `UNKNOWN`: Confidence not assessed

### Clinical Values
- **Extent of Resection**: Enum: `"GTR"`, `"NTR"`, `"STR"`, `"Biopsy"`, `null`
- **Radiation Dose**: Integer (cGy), range 0-10000
- **Drug Names**: Standardized names + generic alternatives tracked
- **Laterality**: Enum: `"Left"`, `"Right"`, `"Bilateral"`, `"Midline"`, `null`

---

## 11. **Error Handling Philosophy**

### Fail Loudly, Track Everything
```python
# BAD: Silent failures
if extraction_failed:
    return None  # Data lost, no trace

# GOOD: Explicit tracking
if extraction_failed:
    self._track_binary_fetch(
        binary_id=binary_id,
        success=False,
        metadata={'error': str(error), 'retry_count': attempts}
    )
    return None
```

### Athena Query Failures
```python
# Log query failures with full context
if status == 'FAILED':
    reason = status_response['Status']['StateChangeReason']
    logger.error(f"Query failed for '{description}': {reason}")
    logger.error(f"Failed query ID: {query_id}")  # Can inspect in AWS Console
    return []
```

**Key Principles**:
1. **Never silently fail** - Every error should be logged
2. **Context is critical** - Log what, why, and where it failed
3. **Enable debugging** - Provide query IDs, document IDs for investigation
4. **Track metrics** - Failed extractions affect success_rate metric

---

## 12. **Future-Proofing: Extensibility Patterns**

### Adding New Clinical Features
To add a new clinical feature (e.g., `ki67_index`):

1. **Define in FeatureObject** - No schema change needed
2. **Add extraction prompt** - Update MedGemma prompts
3. **Add validation logic** - Define acceptable range/values
4. **Track provenance** - Automatically captured by FeatureObject pattern

### Adding New Event Types
To add a new event type (e.g., `clinical_trial_enrollment`):

1. **Define in timeline_events** - Add to event_type enum
2. **Create gap detection** - Identify where this data should exist
3. **Add document search** - Define document types to search
4. **Define ordinality** - How does it fit in treatment sequence?

---

## Summary: Why These Patterns Matter

1. **Reproducibility**: Full provenance means we can trace any value to its source
2. **Quality Assurance**: Validation layers catch bad extractions before they corrupt the timeline
3. **Auditability**: Clinicians can see why the system made each determination
4. **Extensibility**: Adding new features doesn't require schema changes
5. **Debugging**: Comprehensive logging enables rapid problem diagnosis
6. **Research Value**: Multi-source data with confidence scores supports outcome studies

---

## Related Documentation

- [TIMELINE_DATA_MODEL_V4.md](./TIMELINE_DATA_MODEL_V4.md) - Full schema specification
- [V4.2_TWO_AGENT_ENHANCEMENTS.md](./V4.2_TWO_AGENT_ENHANCEMENTS.md) - Two-agent validation pattern
- [SYSTEM_ARCHITECTURE_V4.4.md](./SYSTEM_ARCHITECTURE_V4.4.md) - Overall system architecture
- [WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md](./WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md) - Protocol validation approach

---

**Last Updated**: 2025-11-04
**Version**: V4.5
**Author**: RADIANT_PCA Team
