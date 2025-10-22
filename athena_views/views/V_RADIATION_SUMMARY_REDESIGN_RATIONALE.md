# v_radiation_summary - Redesign Rationale

## Problem Statement

The original `v_radiation_summary` view was **completely empty (0 records)** because it required:
1. Structured ELECT intake form data (only 91 patients out of 684 with radiation data)
2. Non-NULL `obs_start_date` values
3. Successfully parsed course numbers

This meant **593 patients (87%) with radiation data were excluded** from the summary.

## Root Cause Analysis

The original design assumed radiation data would be captured in structured ELECT intake forms, but in reality:

| Data Source | Patients | Coverage | Primary Use |
|-------------|----------|----------|-------------|
| **ELECT Intake Forms** | 91 | 13% | Structured dose/site/dates |
| **Radiation Documents** | 684 | 100% | Treatment summaries, consults, reports |
| **Care Plans** | 568 | 83% | Treatment planning |
| **Appointments** | Unknown | ? | Scheduling context |
| **Service Requests** | 1 | <1% | Treatment orders |

**Conclusion:** Documents are the primary data source for radiation information, not structured forms.

## Redesign Solution

Instead of trying to aggregate radiation treatment details (which don't exist in structured form), the new `v_radiation_summary` serves as a **data availability inventory**.

### New Purpose

**Answer the question:** "For each patient with radiation data, which sources contain information?"

### Key Features

#### 1. **Data Availability Flags** (Boolean indicators)
```sql
- has_structured_elect_data (true/false)
- has_radiation_documents (true/false)
- has_care_plans (true/false)
- has_appointments (true/false)
- has_service_requests (true/false)
```

#### 2. **Source Counts**
```sql
- num_structured_courses
- num_radiation_documents (total: 4,144)
- num_care_plans (total: 18,189)
- num_appointments
- num_service_requests
```

#### 3. **Document Breakdown** (Priority-based)
```sql
- num_treatment_summaries (priority 1)
- num_consults (priority 2)
- num_other_radiation_documents (priority 3-5)
```

#### 4. **Temporal Coverage** (Date ranges from each source)
```sql
- structured_data_earliest/latest_date
- documents_earliest/latest_date
- care_plan_earliest/latest_date
- appointments_earliest/latest_date
- service_request_earliest/latest_date
- radiation_treatment_earliest_date (BEST across all sources)
- radiation_treatment_latest_date (BEST across all sources)
```

#### 5. **Data Quality Metrics**
```sql
- num_data_sources_available (0-5)
- data_completeness_score (0.0-1.0)
```

#### 6. **Recommended Extraction Strategy**
Suggests the best approach for extracting radiation data:

| Strategy | When to Use |
|----------|-------------|
| `structured_primary_with_document_validation` | Have both ELECT data + documents (best case) |
| `document_based_high_priority` | Have treatment summaries or consults |
| `document_based_standard` | Have other radiation documents |
| `structured_only_no_validation` | Only ELECT data (no documents) |
| `metadata_only_limited_extraction` | Only care plans/appointments |
| `insufficient_data` | No usable sources |

## Expected Impact

### Before Redesign
- **Records in view:** 0
- **Patient coverage:** 0%
- **Utility:** None (empty table)
- **Use case:** Failed - cannot identify which patients have radiation data

### After Redesign
- **Records in view:** 684+ patients
- **Patient coverage:** 100% of patients with ANY radiation data
- **Utility:** High - identifies data sources and extraction strategy
- **Use cases:**
  1. Identify patients ready for document-based extraction
  2. Prioritize patients with high-quality multi-source data
  3. Track data completeness across the cohort
  4. Guide abstraction workflow design

## Example Queries

### 1. Find patients ready for document extraction
```sql
SELECT patient_id, num_radiation_documents, num_treatment_summaries, num_consults
FROM v_radiation_summary
WHERE has_radiation_documents = true
ORDER BY num_treatment_summaries DESC, num_consults DESC;
```

### 2. Patients with highest data quality
```sql
SELECT patient_id, num_data_sources_available, data_completeness_score,
       recommended_extraction_strategy
FROM v_radiation_summary
WHERE num_data_sources_available >= 3
ORDER BY data_completeness_score DESC;
```

### 3. Distribution of extraction strategies
```sql
SELECT
    recommended_extraction_strategy,
    COUNT(*) as num_patients,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct_of_cohort
FROM v_radiation_summary
GROUP BY recommended_extraction_strategy
ORDER BY num_patients DESC;
```

### 4. Temporal coverage analysis
```sql
SELECT
    patient_id,
    radiation_treatment_earliest_date,
    radiation_treatment_latest_date,
    DATE_DIFF('day',
              CAST(radiation_treatment_earliest_date AS DATE),
              CAST(radiation_treatment_latest_date AS DATE)) as treatment_span_days
FROM v_radiation_summary
WHERE radiation_treatment_earliest_date IS NOT NULL
ORDER BY treatment_span_days DESC;
```

## Integration with Abstraction Workflow

This redesigned view directly supports the document-first radiation abstraction strategy:

### Phase 1: Query radiation summary
```python
radiation_summary = query_athena(f"""
    SELECT * FROM v_radiation_summary
    WHERE patient_id = '{patient_id}'
""")

if not radiation_summary['has_radiation_documents']:
    print("No radiation documents - skip radiation extraction")
    return
```

### Phase 2: Prioritize high-value documents
```python
if radiation_summary['num_treatment_summaries'] > 0:
    # Extract from treatment summaries first (highest priority)
    extract_from_treatment_summaries()

if radiation_summary['num_consults'] > 0:
    # Extract from consults (second priority)
    extract_from_consults()
```

### Phase 3: Validate with structured data when available
```python
if radiation_summary['has_structured_elect_data']:
    # Cross-validate document extractions against ELECT data
    validate_extractions_against_structured_data()
```

## Deployment Steps

1. **Test the new view** on sample patients
2. **Deploy to Athena** (replaces existing v_radiation_summary)
3. **Update dependent queries/views** if any reference the old schema
4. **Document the change** in view changelog

## Backward Compatibility

⚠️ **BREAKING CHANGE** - The new schema is completely different from the original:

### Old Schema (7 columns)
```
- patient_id
- course_1_start_date
- course_1_end_date
- course_1_duration_weeks
- re_irradiation
- treatment_techniques
- num_radiation_appointments
```

### New Schema (40+ columns)
See V_RADIATION_SUMMARY_REDESIGNED.sql for full schema

**Migration:** Any queries using the old schema will need to be rewritten.

## Future Enhancements

Once radiation extraction workflow is implemented:

1. Add `has_nlp_extractions` flag
2. Add `num_courses_extracted` from NLP
3. Add `extraction_quality_score` based on NLP confidence
4. Compare `structured_data_*` vs `nlp_extracted_*` for validation

## Summary

The redesigned `v_radiation_summary` transforms from a **failed aggregation view** (0 records) to a **useful data inventory** (684+ patients) that:

1. ✅ Shows which data sources are available for each patient
2. ✅ Recommends the best extraction strategy
3. ✅ Provides temporal coverage across all sources
4. ✅ Supports document-first abstraction workflow
5. ✅ Tracks data completeness and quality

This aligns with the existing EOR/tumor status abstraction pattern where **documents are the primary source** and structured data (when available) provides validation.
