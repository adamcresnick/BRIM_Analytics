# How v_unified_patient_timeline is Constructed

## Overview

`v_unified_patient_timeline` is a **massive UNION ALL view** in Athena that consolidates **13 different FHIR data sources** into a single, chronologically-ordered patient timeline. It's the foundational view that feeds the DuckDB timeline database.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              v_unified_patient_timeline (Athena View)            │
│                                                                   │
│  UNION ALL of 13 different source views:                        │
│  1. Diagnoses      8. Measurements                               │
│  2. Procedures     9. Ophthalmology                              │
│  3. Imaging        10. Audiology                                 │
│  4. Medications    11. Transplants                               │
│  5. Visits         12. Stem Cell Collection                      │
│  6. Molecular Tests 13. Corticosteroids                          │
│  7. Radiation                                                    │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         Each source normalized to common schema:                 │
│         - event_id (unique identifier)                           │
│         - event_date (chronological ordering)                    │
│         - event_type ('Diagnosis', 'Procedure', etc.)            │
│         - event_category (sub-classification)                    │
│         - source_view (provenance tracking)                      │
│         - source_domain (FHIR resource type)                     │
│         - event_metadata (JSON with domain-specific fields)      │
│         - extraction_context (JSON for agent queries)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Locations

| File | Purpose |
|------|---------|
| [V_UNIFIED_PATIENT_TIMELINE.sql](athena_views/views/V_UNIFIED_PATIENT_TIMELINE.sql) | Main UNION ALL view (1,096 lines) |
| [V_UNIFIED_TIMELINE_PREREQUISITES.sql](athena_views/views/V_UNIFIED_TIMELINE_PREREQUISITES.sql) | Creates prerequisite views (`v_diagnoses`, `v_radiation_summary`) |

---

## Prerequisite Views

Before `v_unified_patient_timeline` can be created, two normalized views must exist:

### 1. v_diagnoses
**Created from**: `v_problem_list_diagnoses`
**Purpose**: Remove `pld_` column prefixes for consistent naming
**SQL**:
```sql
CREATE OR REPLACE VIEW v_diagnoses AS
SELECT
    patient_fhir_id,
    pld_condition_id as condition_id,
    pld_diagnosis_name as diagnosis_name,
    pld_clinical_status as clinical_status_text,
    pld_onset_date as onset_date_time,  -- TIMESTAMP(3)
    pld_icd10_code as icd10_code,
    pld_snomed_code as snomed_code
FROM v_problem_list_diagnoses
```

### 2. v_radiation_summary
**Created from**: `v_radiation_treatments`
**Purpose**: Aggregate radiation treatments into course-level summary
**Logic**:
- Groups radiation treatments by `course_number`
- Computes course 1 start/end dates
- Calculates duration in weeks
- Detects re-irradiation (>1 course)
- Counts radiation appointments

---

## Unified Schema - Common Columns

Every event in the timeline has these standardized columns:

| Column | Type | Description |
|--------|------|-------------|
| **patient_fhir_id** | VARCHAR | Patient identifier (without 'Patient/' prefix) |
| **event_id** | VARCHAR | Unique event ID (prefixed: 'diag_', 'proc_', 'img_', 'med_', etc.) |
| **event_date** | DATE | Event occurrence date (for chronological ordering) |
| **age_at_event_days** | INTEGER | Patient age in days at event |
| **age_at_event_years** | DECIMAL(5,2) | Patient age in years at event |
| **event_type** | VARCHAR | Event classification ('Diagnosis', 'Procedure', 'Imaging', 'Medication', 'Visit', 'Measurement', 'Assessment', 'Molecular Test', 'Radiation Course', 'Radiation Fraction') |
| **event_category** | VARCHAR | Sub-classification (e.g., 'Tumor' for diagnosis, 'Surgery' for procedure) |
| **event_subtype** | VARCHAR | Further classification (optional) |
| **event_description** | TEXT | Human-readable description |
| **event_status** | VARCHAR | Status ('active', 'completed', 'cancelled', etc.) |
| **source_view** | VARCHAR | Origin Athena view (e.g., 'v_diagnoses', 'v_imaging') |
| **source_domain** | VARCHAR | FHIR resource type ('Condition', 'Procedure', 'DiagnosticReport', etc.) |
| **source_id** | VARCHAR | Original FHIR resource ID (for traceability) |
| **icd10_codes** | ARRAY(VARCHAR) | ICD-10 codes |
| **snomed_codes** | ARRAY(VARCHAR) | SNOMED CT codes |
| **cpt_codes** | ARRAY(VARCHAR) | CPT procedure codes |
| **loinc_codes** | ARRAY(VARCHAR) | LOINC lab codes |
| **event_metadata** | JSON (as VARCHAR) | Domain-specific fields (varies by event type) |
| **extraction_context** | JSON (as VARCHAR) | Agent query hints (requires_free_text_extraction, free_text_fields, etc.) |

---

## 13 Source Data Streams

### 1. **Diagnoses** (v_diagnoses)
**FHIR Resource**: Condition
**Event ID**: `diag_<condition_id>`
**Event Date**: `onset_date_time`
**Event Category Logic**:
- **Tumor**: Diagnosis name contains 'neoplasm', 'tumor', 'astrocytoma', 'glioma', 'medulloblastoma', 'ependymoma'
- **Treatment Toxicity**: Contains 'chemotherapy', 'nausea', 'vomiting', 'induced'
- **Hydrocephalus**: Contains 'hydrocephalus'
- **Vision Disorder**: Contains 'vision', 'visual', 'diplopia', 'nystagmus'
- **Hearing Disorder**: Contains 'hearing', 'ototoxic'
- **Other Complication**: Everything else

**Event Subtype Logic**:
- **Progression**: Contains 'progression' OR SNOMED = 25173007
- **Recurrence**: Contains 'recurrence' or 'recurrent'
- **Initial Diagnosis**: Contains 'astrocytoma', 'glioma', 'medulloblastoma'

**Typical Volume**: ~50-100 diagnoses per patient

---

### 2. **Procedures** (v_procedures_tumor)
**FHIR Resource**: Procedure
**Event ID**: `proc_<procedure_fhir_id>`
**Event Date**: `procedure_date`
**Event Category Logic**:
- **Tumor Surgery**: cpt_classification IN ('craniotomy_tumor_resection', 'stereotactic_tumor_procedure', 'neuroendoscopy_tumor', 'open_brain_biopsy', 'skull_base_tumor') OR surgery_type IN ('craniotomy', 'craniectomy', 'neuroendoscopy', 'skull_base')
- **Supportive Procedure**: cpt_classification IN ('tumor_related_csf_management', 'tumor_related_device_implant')
- **Biopsy/Diagnostic**: surgery_type IN ('biopsy', 'stereotactic_procedure')
- **Other Procedure**: Everything else

**Filter**: `WHERE is_tumor_surgery = true`

**Typical Volume**: ~10-15 surgeries per patient

---

### 3. **Imaging** (v_imaging)
**FHIR Resource**: DiagnosticReport
**Event ID**: `img_<imaging_procedure_id>`
**Event Date**: `imaging_date`
**Event Category**: Always 'Imaging'
**Event Subtype Logic** (based on report_conclusion):
- **Progression Imaging**: Contains 'progression' or 'increase'
- **Stable Imaging**: Contains 'stable'
- **Response Imaging**: Contains 'improvement' or 'decrease'
- **Surveillance Imaging**: Everything else

**Extraction Context**: `requires_free_text_extraction: true` if `report_conclusion` exists

**Typical Volume**: ~250-300 imaging studies per patient

---

### 4. **Medications** (v_medications)
**FHIR Resource**: MedicationRequest
**Event ID**: `med_<medication_request_id>`
**Event Date**: `medication_start_date`
**Event Category Logic** (keyword matching on medication_name):
- **Chemotherapy**: Contains 'vincristine', 'carboplatin', 'cisplatin', 'etoposide', 'cyclophosphamide', 'ifosfamide'
- **Targeted Therapy**: Contains 'selumetinib', 'dabrafenib', 'trametinib', 'vemurafenib'
- **Corticosteroid**: Contains 'dexamethasone', 'prednisone', 'methylprednisolone'
- **Antiemetic**: Contains 'ondansetron', 'granisetron', 'metoclopramide'
- **Growth Factor**: Contains 'filgrastim', 'pegfilgrastim'
- **Other Medication**: Everything else

**Note**: This is a simple keyword-based classification. **ChemotherapyFilter** is applied during DuckDB timeline build to correct categorization using comprehensive drug reference lists.

**Typical Volume**: ~1,000-1,500 medication orders per patient

---

### 5. **Visits** (v_visits_unified)
**FHIR Resource**: Encounter + Appointment (unified, no duplication)
**Event ID**: `visit_<encounter_id OR appointment_fhir_id>`
**Event Date**: `visit_date`
**Event Category Logic**:
- **Completed Visit**: visit_type = 'completed_scheduled'
- **Appointment Only**: visit_type = 'completed_no_encounter'
- **No Show**: visit_type = 'no_show'
- **Cancelled Visit**: visit_type = 'cancelled'
- **Scheduled Visit**: visit_type = 'future_scheduled'
- **Unscheduled Encounter**: source = 'encounter_only'
- **Other Visit**: Everything else

**Typical Volume**: ~100-200 visits per patient

---

### 6. **Molecular Tests** (v_molecular_tests)
**FHIR Resource**: Observation (Lab)
**Event ID**: `moltest_<mt_test_id>`
**Event Date**: `mt_test_date`
**Event Category**: Always 'Genomic Testing'
**Event Subtype**: `mt_lab_test_name` (e.g., "NGS Panel", "BRAF V600E Mutation Analysis")

**Extraction Context**: `requires_free_text_extraction: true` if `mtr_total_narrative_chars > 0`

**Typical Volume**: ~5-20 molecular tests per patient

---

### 7A. **Radiation Courses** (v_radiation_summary)
**FHIR Resource**: CarePlan (aggregated)
**Event ID**: `rad_course_1_<patient_fhir_id>`
**Event Date**: `course_1_start_date`
**Event Category**: Always 'Radiation Therapy'
**Event Subtype**:
- **Re-irradiation Course 1**: If `re_irradiation = 'Yes'`
- **Initial Radiation Course 1**: Otherwise

**Metadata Includes**:
- course_1_start_date, course_1_end_date
- course_1_duration_weeks
- treatment_techniques
- num_radiation_appointments

**Typical Volume**: 0-2 courses per patient (most have 0-1)

---

### 7B. **Radiation Fractions** (v_radiation_treatment_appointments)
**FHIR Resource**: Appointment
**Event ID**: `radfx_<appointment_id>`
**Event Date**: `appointment_start`
**Event Category**: Always 'Radiation Therapy'
**Event Subtype**: Always 'Daily Treatment'

**Purpose**: Granular daily radiation treatment data

**Typical Volume**: 0 (if no radiation) or 20-30 fractions per course

---

### 8. **Measurements** (v_measurements)
**FHIR Resource**: Observation + LabTests
**Event ID**: `obs_<observation_id>` OR `lab_<test_id>`
**Event Date**: `obs_measurement_date` OR `lt_measurement_date`
**Event Category Logic** (keyword matching on measurement_type):
- **Growth**: 'height', 'weight', 'bmi', 'body mass index'
- **Vital Signs**: 'blood pressure', 'heart rate', 'temperature', 'oxygen'
- **Hematology Lab**: 'cbc', 'blood count', 'hemoglobin', 'platelet', 'wbc', 'neutrophil'
- **Chemistry Lab**: 'metabolic', 'chemistry', 'electrolyte'
- **Liver Function**: 'liver', 'alt', 'ast', 'bilirubin'
- **Renal Function**: 'renal', 'creatinine', 'bun'
- **Other Lab**: Everything else

**Typical Volume**: ~1,000-1,500 measurements per patient

---

### 9. **Ophthalmology Assessments** (v_ophthalmology_assessments)
**FHIR Resource**: Observation + Procedure + DocumentReference
**Event ID**: `ophtho_<record_fhir_id>`
**Event Date**: `assessment_date`
**Event Category**: Always 'Ophthalmology'
**Event Subtype**: `assessment_category` (e.g., 'visual_acuity', 'visual_field', 'oct_optic_nerve', 'fundus_exam')

**Extraction Context**: `requires_free_text_extraction: true` if `file_url IS NOT NULL`

**Typical Volume**: ~20-50 assessments per patient (if applicable)

---

### 10. **Audiology Assessments** (v_audiology_assessments)
**FHIR Resource**: Observation + Procedure + Condition + DocumentReference
**Event ID**: `audio_<record_fhir_id>`
**Event Date**: `assessment_date`
**Event Category**: Always 'Audiology'
**Event Subtype**: `assessment_category` (e.g., 'audiogram_threshold', 'ototoxicity_monitoring', 'hearing_test')

**Extraction Context**: `ototoxicity_surveillance: true` if `assessment_category = 'ototoxicity_monitoring'`

**Typical Volume**: ~10-30 assessments per patient (if applicable)

---

### 11. **Autologous Stem Cell Transplant** (v_autologous_stem_cell_transplant)
**FHIR Resource**: Condition + Procedure
**Event ID**: `transplant_<proc_id OR cond_id>`
**Event Date**: `transplant_datetime`
**Event Category**: Always 'Stem Cell Transplant'
**Event Subtype**: Always 'Autologous Transplant'

**Filter**: `WHERE transplant_datetime IS NOT NULL`

**Typical Volume**: 0-1 per patient (rare)

---

### 12. **Autologous Stem Cell Collection** (v_autologous_stem_cell_collection)
**FHIR Resource**: Procedure
**Event ID**: `stemcell_coll_<collection_procedure_fhir_id>`
**Event Date**: `collection_datetime`
**Event Category**: Always 'Stem Cell Collection'
**Event Subtype**: `collection_method` (default: 'Apheresis')

**Filter**: `WHERE collection_datetime IS NOT NULL`

**Typical Volume**: 0-1 per patient (rare)

---

### 13. **Imaging-Related Corticosteroids** (v_imaging_corticosteroid_use)
**FHIR Resource**: MedicationRequest (linked to DiagnosticReport)
**Event ID**: `cortico_img_<corticosteroid_medication_fhir_id>`
**Event Date**: `imaging_date` (not medication date!)
**Event Category**: Always 'Corticosteroid (Imaging)'
**Event Subtype**: `corticosteroid_name`

**Purpose**: Track steroid use around imaging dates (signals tumor edema, affects interpretation)

**Filter**: `WHERE on_corticosteroid = true`

**Extraction Context**: `affects_imaging_interpretation: true`

**Typical Volume**: ~10-30 imaging-corticosteroid pairs per patient

---

## Key Design Decisions

### 1. **UNION ALL, not UNION**
- Uses `UNION ALL` to preserve all events (no deduplication)
- Event IDs are prefixed by source (`diag_`, `proc_`, `img_`, etc.) to ensure uniqueness
- Duplicates across sources are intentional (e.g., same medication in multiple contexts)

### 2. **Date Standardization**
- All source views use **TIMESTAMP(3)** for datetime columns (standardized 2025-10-19)
- Timeline extracts **DATE only** via `DATE(timestamp_column)` or `CAST(date_column AS DATE)`
- Age calculations use `DATE_DIFF('day', birth_date, event_date)`

### 3. **Provenance Tracking**
Every event includes:
- **source_view**: Which Athena view it came from
- **source_domain**: FHIR resource type
- **source_id**: Original FHIR resource ID
- Purpose: Enables tracing back to source data for validation

### 4. **JSON Metadata**
Two JSON columns per event:
- **event_metadata**: Domain-specific fields (varies by event type)
  - Example (Imaging): `{"modality": "MRI Brain", "report_conclusion": "Stable disease"}`
  - Example (Procedure): `{"cpt_code": "61510", "surgery_type": "craniotomy"}`

- **extraction_context**: Hints for agent-based extraction
  - `requires_free_text_extraction`: true/false
  - `free_text_fields`: List of fields needing NLP extraction
  - `has_binary_document`: true/false (PDF/images available)
  - `affects_imaging_interpretation`: true/false (for corticosteroids)

### 5. **Event Category Classification**
- Uses **keyword matching on text fields** (medication_name, diagnosis_name, etc.)
- **NOT** authoritative for medications - ChemotherapyFilter applied during DuckDB build
- Ophthalmology/Audiology use structured `assessment_category` field

### 6. **Age Calculation**
- Joins `v_patient_demographics` for birth_date when needed
- Formula: `DATE_DIFF('day', birth_date, event_date)` for days
- Formula: `DATE_DIFF('day', birth_date, event_date) / 365.25` for years

### 7. **Final Ordering**
```sql
ORDER BY patient_fhir_id, event_date, event_type
```
- Chronologically sorted within each patient
- Secondary sort by event_type for same-day events

---

## Query Performance Considerations

### Indexes (Implicit via Source Views)
- All source views have patient_fhir_id indexed
- Date columns indexed in most source views
- Timeline view itself is not materialized (on-demand query)

### Query Pattern for Extraction
```sql
SELECT * FROM v_unified_patient_timeline
WHERE patient_fhir_id = '<patient_id>'
ORDER BY event_date
```
**Performance**: ~1-5 seconds for typical patient (1,700+ events)

### Why Not Materialized?
- Source data changes frequently (new imaging, new medications)
- Materialized view would require constant refresh
- On-demand query acceptable for single-patient extraction

---

## Data Flow: Athena → DuckDB

```
┌────────────────────────────────────────────────┐
│  Athena: v_unified_patient_timeline            │
│  (Virtual view, not materialized)              │
│  - 13 UNION ALL branches                       │
│  - ~1,700 events per patient                   │
│  - JSON metadata + extraction context          │
└────────────────┬───────────────────────────────┘
                 │
                 │ Query via build_timeline_database.py
                 │
                 ▼
┌────────────────────────────────────────────────┐
│  Python: Timeline Construction                 │
│  - Export events for patient                   │
│  - Apply ChemotherapyFilter (correct meds)     │
│  - Compute milestones (first diagnosis, etc.)  │
│  - Compute temporal context (disease phase)    │
└────────────────┬───────────────────────────────┘
                 │
                 │ Load into DuckDB
                 │
                 ▼
┌────────────────────────────────────────────────┐
│  DuckDB: timeline.duckdb                       │
│  - patients table (milestones)                 │
│  - events table (timeline)                     │
│  - extracted_variables table (LLM outputs)     │
└────────────────────────────────────────────────┘
```

---

## Example Event Records

### Diagnosis Event
```sql
event_id: 'diag_Condition_12345'
event_date: '2018-03-15'
event_type: 'Diagnosis'
event_category: 'Tumor'
event_subtype: 'Initial Diagnosis'
event_description: 'Pilocytic astrocytoma'
source_view: 'v_diagnoses'
source_domain: 'Condition'
event_metadata: {
  "icd10_code": "D33.1",
  "snomed_code": "254938000",
  "clinical_status": "active"
}
```

### Imaging Event
```sql
event_id: 'img_DiagnosticReport_67890'
event_date: '2018-06-20'
event_type: 'Imaging'
event_category: 'Imaging'
event_subtype: 'Stable Imaging'
event_description: 'MRI Brain with and without contrast'
source_view: 'v_imaging'
source_domain: 'DiagnosticReport'
event_metadata: {
  "modality": "MRI Brain",
  "report_conclusion": "Stable disease, no progression"
}
extraction_context: {
  "requires_free_text_extraction": "true",
  "free_text_fields": "report_conclusion, result_display"
}
```

### Medication Event
```sql
event_id: 'med_MedicationRequest_54321'
event_date: '2018-07-01'
event_type: 'Medication'
event_category: 'Chemotherapy'  -- Initial classification (may be corrected by ChemotherapyFilter)
event_subtype: null
event_description: 'Vincristine sulfate'
source_view: 'v_medications'
source_domain: 'MedicationRequest'
event_metadata: {
  "medication_name": "Vincristine sulfate",
  "rx_norm_codes": "11124",
  "start_date": "2018-07-01",
  "status": "active"
}
```

---

## Validation Queries

### Test 1: Event type distribution
```sql
SELECT
    event_type,
    event_category,
    COUNT(*) as event_count,
    MIN(event_date) as earliest,
    MAX(event_date) as latest
FROM v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type, event_category
ORDER BY event_count DESC;
```

### Test 2: Check for duplicates
```sql
SELECT event_id, COUNT(*) as duplicate_count
FROM v_unified_patient_timeline
GROUP BY event_id
HAVING COUNT(*) > 1;
-- Expected: 0 rows (no duplicates)
```

### Test 3: Provenance verification
```sql
SELECT
    source_view,
    source_domain,
    event_type,
    COUNT(*) as event_count
FROM v_unified_patient_timeline
GROUP BY source_view, source_domain, event_type
ORDER BY source_view;
```

---

## Summary

**v_unified_patient_timeline** is:
- ✅ A **single queryable view** consolidating 13 FHIR data sources
- ✅ **~1,700 events per patient** (typical pediatric cancer patient)
- ✅ **Chronologically ordered** by event_date
- ✅ **Standardized schema** (common columns across all event types)
- ✅ **Provenance tracked** (source_view, source_domain, source_id)
- ✅ **JSON metadata** for domain-specific fields
- ✅ **Agent-ready** with extraction_context hints
- ✅ **Not materialized** - on-demand query from source views
- ✅ Built via **UNION ALL** of 13 SELECT statements (1,096 lines of SQL)

This view is the **foundation** of the entire patient timeline - everything downstream (DuckDB load, temporal context computation, LLM extraction) starts here.
