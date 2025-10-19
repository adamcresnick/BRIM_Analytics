# V_UNIFIED_PATIENT_TIMELINE Deployment Guide

**Date**: 2025-10-19
**Status**: Ready for Athena Deployment

---

## Overview

The `v_unified_patient_timeline` view consolidates ALL temporal patient events from 13 FHIR data sources into a single queryable view with 3-layer provenance tracking.

**Error Fixed**: ✅ Converted all `JSON_OBJECT` calls to Presto-compatible `MAP` syntax (26 conversions across 13 UNION blocks)

---

## Deployment Steps

### Step 1: Deploy Prerequisite Views

**File**: `V_UNIFIED_TIMELINE_PREREQUISITES.sql`

These views normalize column names from prefixed views to non-prefixed names:

1. **v_diagnoses** - Normalizes v_problem_list_diagnoses (removes pld_ prefix)
2. **v_radiation_summary** - Aggregates radiation courses from v_radiation_treatments

**Athena Commands**:
```sql
-- Navigate to: AWS Athena Console → Query Editor
-- Database: fhir_prd_db
-- Run entire V_UNIFIED_TIMELINE_PREREQUISITES.sql file
```

**Validation**:
```sql
-- Verify v_diagnoses exists
SELECT COUNT(*) as diagnosis_count,
       COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_diagnoses;

-- Verify v_radiation_summary exists
SELECT COUNT(*) as course_count,
       COUNT(DISTINCT patient_id) as patient_count
FROM fhir_prd_db.v_radiation_summary;
```

---

### Step 2: Deploy Unified Patient Timeline

**File**: `V_UNIFIED_PATIENT_TIMELINE.sql`

This view integrates 13 event sources with Presto-compatible JSON syntax.

**Athena Commands**:
```sql
-- Run entire V_UNIFIED_PATIENT_TIMELINE.sql file
```

**Expected Runtime**: 2-5 minutes (depending on data volume)

---

### Step 3: Validate Deployment

**Test Query 1: Event Type Distribution**
```sql
SELECT
    event_type,
    event_category,
    COUNT(*) as event_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    MIN(event_date) as earliest_event,
    MAX(event_date) as latest_event
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY event_type, event_category
ORDER BY event_count DESC;
```

**Expected Output**:
| event_type | event_category | event_count | patient_count |
|------------|----------------|-------------|---------------|
| Measurement | Growth | ~150,000+ | ~2,000+ |
| Encounter | Outpatient Visit | ~50,000+ | ~2,000+ |
| Medication | Chemotherapy | ~20,000+ | ~1,500+ |
| Imaging | Surveillance Imaging | ~15,000+ | ~2,000+ |
| ... | ... | ... | ... |

---

**Test Query 2: Patient-Specific Timeline (Example: e4BwD8ZYDBccepXcJ.Ilo3w3)**
```sql
SELECT
    event_date,
    event_type,
    event_category,
    event_description,
    source_view,
    age_at_event_years
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY event_date;
```

**Expected Output**: ~4,126 events spanning 2018-06-04 (diagnosis) through 2024+

---

**Test Query 3: Coverage Verification**
```sql
-- Verify all 13 event sources are present
SELECT
    source_view,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY source_view, event_type
ORDER BY source_view, event_type;
```

**Expected Sources** (13 total):
1. v_diagnoses (Diagnosis events)
2. v_procedures (Procedure events)
3. v_imaging (Imaging events)
4. v_medications (Medication events)
5. v_encounters (Encounter events)
6. v_molecular_tests (Molecular Test events)
7. v_radiation_summary (Radiation Course events)
8. v_radiation_treatment_appointments (Radiation Fraction events)
9. v_measurements (Measurement events)
10. v_ophthalmology_assessments (Assessment events - Ophthalmology)
11. v_audiology_assessments (Assessment events - Audiology)
12. v_autologous_stem_cell_transplant (Procedure events - Transplant)
13. v_autologous_stem_cell_collection (Procedure events - Collection)
14. v_imaging_corticosteroid_use (Medication events - Corticosteroid Imaging)

---

**Test Query 4: Provenance Tracking Verification**
```sql
-- Verify extraction context is queryable
SELECT
    event_type,
    JSON_EXTRACT_SCALAR(extraction_context, '$.source_view') as source_view_from_json,
    JSON_EXTRACT_SCALAR(extraction_context, '$.requires_free_text_extraction') as needs_extraction,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type,
    JSON_EXTRACT_SCALAR(extraction_context, '$.source_view'),
    JSON_EXTRACT_SCALAR(extraction_context, '$.requires_free_text_extraction')
ORDER BY event_type;
```

---

## Troubleshooting

### Error: "Table does not exist"

**Symptom**: `Table 'fhir_prd_db.v_diagnoses' does not exist`

**Solution**: Run Step 1 first (V_UNIFIED_TIMELINE_PREREQUISITES.sql)

---

### Error: "JSON_OBJECT syntax error"

**Symptom**: `line X:Y: mismatched input ','`

**Solution**: This was fixed in the current version. Ensure you're using V_UNIFIED_PATIENT_TIMELINE.sql dated 2025-10-19 or later.

---

### Error: "Column not found"

**Symptom**: `Column 'pld_diagnosis_name' cannot be resolved`

**Potential Causes**:
1. v_problem_list_diagnoses view doesn't exist
2. Column names in v_problem_list_diagnoses have changed

**Solution**: Verify base views exist:
```sql
SHOW VIEWS IN fhir_prd_db LIKE 'v_%';
DESCRIBE fhir_prd_db.v_problem_list_diagnoses;
```

---

## Architecture Summary

### Data Flow
```
FHIR Raw Tables → Athena Base Views (prefixed columns) → Normalized Views → Unified Timeline
                     ↓                                       ↓                    ↓
              v_problem_list_diagnoses              v_diagnoses         v_unified_patient_timeline
                (pld_ prefix)                    (no prefix)           (13 sources, MAP JSON)
```

### Provenance Layers

**Layer 1**: `source_view` column
- Which Athena view the event came from
- Example: 'v_imaging', 'v_procedures'

**Layer 2**: `source_domain` column
- FHIR resource type
- Example: 'DiagnosticReport', 'Procedure', 'Condition'

**Layer 3**: `extraction_context` JSON
- Detailed provenance metadata
- Free-text extraction requirements
- Document URLs for binary files
```json
{
  "source_view": "v_imaging",
  "source_table": "diagnostic_report",
  "has_structured_code": "false",
  "requires_free_text_extraction": "true",
  "free_text_fields": "[report_conclusion, result_display]"
}
```

---

## Query Examples for Agents

**Agent Query 1: Get temporal context around an event**
```sql
-- Get all events within 30 days of a specific imaging study
WITH target_event AS (
    SELECT event_date
    FROM fhir_prd_db.v_unified_patient_timeline
    WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
      AND event_id = 'img_DiagnosticReport123'
)
SELECT
    upt.event_date,
    upt.event_type,
    upt.event_description,
    DATE_DIFF('day', te.event_date, upt.event_date) as days_from_target
FROM fhir_prd_db.v_unified_patient_timeline upt
CROSS JOIN target_event te
WHERE upt.patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND upt.event_date BETWEEN DATE_ADD('day', -30, te.event_date)
                         AND DATE_ADD('day', 30, te.event_date)
ORDER BY upt.event_date;
```

**Agent Query 2: Find events requiring free-text extraction**
```sql
SELECT
    event_id,
    event_type,
    event_description,
    event_date,
    source_view,
    JSON_EXTRACT_SCALAR(extraction_context, '$.free_text_fields') as fields_to_extract,
    JSON_EXTRACT_SCALAR(event_metadata, '$.report_conclusion') as report_text
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND JSON_EXTRACT_SCALAR(extraction_context, '$.requires_free_text_extraction') = 'true'
ORDER BY event_date;
```

**Agent Query 3: Progression event context**
```sql
-- Get comprehensive context for a potential progression event
WITH progression_event AS (
    SELECT * FROM fhir_prd_db.v_unified_patient_timeline
    WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
      AND event_date = DATE '2018-08-03'
      AND event_type = 'Imaging'
)
SELECT
    'PRIOR_TREATMENT' as context_type,
    upt.event_date,
    upt.event_type,
    upt.event_description
FROM fhir_prd_db.v_unified_patient_timeline upt, progression_event pe
WHERE upt.patient_fhir_id = pe.patient_fhir_id
  AND upt.event_date < pe.event_date
  AND upt.event_category IN ('Chemotherapy', 'Targeted Therapy', 'Radiation Therapy')
  AND upt.event_date >= DATE_ADD('day', -180, pe.event_date)

UNION ALL

SELECT
    'PRIOR_IMAGING' as context_type,
    upt.event_date,
    upt.event_type,
    upt.event_description
FROM fhir_prd_db.v_unified_patient_timeline upt, progression_event pe
WHERE upt.patient_fhir_id = pe.patient_fhir_id
  AND upt.event_date < pe.event_date
  AND upt.event_type = 'Imaging'
  AND upt.event_date >= DATE_ADD('day', -90, pe.event_date)

ORDER BY event_date;
```

---

## Performance Notes

- **View Type**: Non-materialized view (query-time execution)
- **Query Performance**: Moderate (13 UNION ALL blocks)
- **Recommended Usage**:
  - For per-patient queries: FAST (typically <5 seconds)
  - For full-cohort aggregations: Consider materializing results to S3/Parquet
  - For Python agent queries: Use patient_fhir_id filter to minimize scan size

---

## Next Steps

After successful deployment:

1. **Create DuckDB instance** - Load timeline into DuckDB for fast Python agent queries
   - See: `TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md`

2. **Deploy downstream views**:
   - `v_patient_disease_phases.sql` - Disease phase labeling
   - `v_progression_detection.sql` - Multi-signal progression detection

3. **Integrate with extraction agents** - Use TimelineQueryInterface for contextualized data extraction

---

## Change Log

**2025-10-19**:
- ✅ Fixed JSON_OBJECT syntax errors (converted to MAP)
- ✅ Created V_UNIFIED_TIMELINE_PREREQUISITES.sql
- ✅ All 13 event sources integrated with provenance tracking
- ✅ Addressed CRITICAL, HIGH, and MODERATE priority gaps

**Previous Version Issues**:
- ❌ JSON_OBJECT syntax incompatible with Presto/Athena
- ❌ Referenced non-existent views (v_diagnoses, v_radiation_summary)
