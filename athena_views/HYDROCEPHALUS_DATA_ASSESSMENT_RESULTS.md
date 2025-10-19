# Hydrocephalus Data Assessment Results
**Date**: October 18, 2025
**Status**: Initial assessment complete - High coverage found

---

## Executive Summary

✅ **Excellent hydrocephalus/shunt data availability in FHIR tables**

- **427 hydrocephalus diagnosis records** found in problem_list_diagnoses table
- **1,196 shunt procedure records** found in procedure table
- High confidence in creating comprehensive hydrocephalus views

---

## Data Source Coverage

### 1. Hydrocephalus Diagnoses

**Source Table**: `fhir_prd_db.problem_list_diagnoses`

**Query**:
```sql
SELECT COUNT(*) as count
FROM fhir_prd_db.problem_list_diagnoses
WHERE LOWER(diagnosis_name) LIKE '%hydroceph%'
   OR icd10_code LIKE 'G91%'
   OR icd10_code LIKE 'Q03%'
```

**Result**: **427 records**

**Available Fields**:
- `patient_id` → patient_fhir_id
- `diagnosis_name` → hydrocephalus type (text)
- `icd10_code` → G91.%, Q03.% codes
- `icd10_display` → ICD-10 description
- `clinical_status_text` → active/resolved status
- `onset_date_time` → diagnosis date (maps to hydro_event_date)
- `recorded_date` → when diagnosis was documented
- `snomed_code` → SNOMED CT code (if available)

**CBTN Fields Covered**:
- ✅ `hydro_yn` - Can derive from presence of diagnosis
- ✅ `medical_conditions_present_at_event(11)` - Hydrocephalus flag
- ✅ `hydro_event_date` - From onset_date_time
- ✅ `hydro_method_diagnosed` - Clinical (from problem list)

---

### 2. Shunt Procedures

**Source Table**: `fhir_prd_db.procedure`

**Query**:
```sql
SELECT COUNT(*) as count
FROM fhir_prd_db.procedure
WHERE LOWER(code_text) LIKE '%shunt%'
```

**Result**: **1,196 procedures**

**Available Fields** (from procedure table):
- `subject_reference` → patient_fhir_id
- `code_text` → procedure name (classification source)
- `status` → completed/in-progress/etc.
- `performed_date_time` → exact procedure date
- `performed_period_start` → procedure start
- `performed_period_end` → procedure end

**Expected Procedure Sub-Schema Fields**:
- `procedure_code_coding` → CPT codes (62220, 62223, 62230, etc.)
- `procedure_body_site` → anatomical location
- `procedure_performer` → neurosurgeon
- `procedure_note` → operative details (programmable valve info)
- `procedure_reason_code` → indication (hydrocephalus)

**CBTN Fields Covered**:
- ✅ `shunt_required` - Can classify from code_text (VPS/ETV/Other)
- ✅ `hydro_surgical_management` - Procedure type classification
- ✅ `hydro_intervention` - Surgical flag
- ⚠️ `hydro_shunt_programmable` - Requires procedure_note analysis

---

## Schema Corrections from Initial Queries

### Issue: Incorrect Column Names

**Original queries used**:
- `condition.code_coding` ❌ Does not exist
- `procedure.code_coding` ❌ Does not exist

**Correct field names**:
- `problem_list_diagnoses.icd10_code` ✅
- `problem_list_diagnoses.diagnosis_name` ✅
- `procedure.code_text` ✅
- `procedure_code_coding.code_coding` ✅ (sub-schema table)

---

## Revised Query Strategy

### Query 1: Hydrocephalus Diagnoses (CORRECTED)

```sql
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id,
    pld.diagnosis_name,
    pld.icd10_code,
    pld.icd10_display,
    pld.clinical_status_text,
    pld.onset_date_time as hydro_event_date,
    pld.recorded_date,

    -- Classify hydrocephalus type
    CASE
        WHEN pld.icd10_code LIKE 'G91.0%' THEN 'Communicating hydrocephalus'
        WHEN pld.icd10_code LIKE 'G91.1%' THEN 'Obstructive hydrocephalus'
        WHEN pld.icd10_code LIKE 'G91.2%' THEN 'Normal-pressure hydrocephalus'
        WHEN pld.icd10_code LIKE 'G91.3%' THEN 'Post-traumatic hydrocephalus'
        WHEN pld.icd10_code LIKE 'G91.8%' THEN 'Other hydrocephalus'
        WHEN pld.icd10_code LIKE 'G91.9%' THEN 'Hydrocephalus, unspecified'
        WHEN pld.icd10_code LIKE 'Q03%' THEN 'Congenital hydrocephalus'
        ELSE 'Hydrocephalus (text match)'
    END as hydrocephalus_type

FROM fhir_prd_db.problem_list_diagnoses pld
WHERE pld.patient_id IS NOT NULL
  AND (
      LOWER(pld.diagnosis_name) LIKE '%hydroceph%'
      OR pld.icd10_code LIKE 'G91%'
      OR pld.icd10_code LIKE 'Q03%'
  )
ORDER BY pld.patient_id, pld.onset_date_time;
```

---

### Query 2: Shunt Procedures (CORRECTED)

```sql
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text,
    p.status,
    p.performed_date_time,
    p.performed_period_start,
    p.performed_period_end,

    -- Shunt type classification
    CASE
        WHEN LOWER(p.code_text) LIKE '%ventriculoperitoneal%'
             OR LOWER(p.code_text) LIKE '%vp%shunt%'
             OR LOWER(p.code_text) LIKE '%v-p%shunt%'
             OR LOWER(p.code_text) LIKE '%vps%' THEN 'VPS'
        WHEN LOWER(p.code_text) LIKE '%endoscopic%third%ventriculostomy%'
             OR LOWER(p.code_text) LIKE '%etv%' THEN 'ETV'
        WHEN LOWER(p.code_text) LIKE '%external%ventricular%drain%'
             OR LOWER(p.code_text) LIKE '%evd%'
             OR LOWER(p.code_text) LIKE '%temporary%' THEN 'EVD'
        WHEN LOWER(p.code_text) LIKE '%ventriculoatrial%'
             OR LOWER(p.code_text) LIKE '%va%shunt%' THEN 'VA Shunt'
        ELSE 'Other Shunt'
    END as shunt_type,

    -- Procedure category
    CASE
        WHEN LOWER(p.code_text) LIKE '%placement%'
             OR LOWER(p.code_text) LIKE '%insertion%'
             OR LOWER(p.code_text) LIKE '%creation%' THEN 'Initial Placement'
        WHEN LOWER(p.code_text) LIKE '%revision%'
             OR LOWER(p.code_text) LIKE '%replacement%' THEN 'Revision'
        WHEN LOWER(p.code_text) LIKE '%removal%' THEN 'Removal'
        WHEN LOWER(p.code_text) LIKE '%reprogram%' THEN 'Reprogramming'
        ELSE 'Unknown Category'
    END as procedure_category

FROM fhir_prd_db.procedure p
WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
  )
ORDER BY p.subject_reference, p.performed_period_start;
```

---

## Expected Coverage by CBTN Field

| CBTN Field | Expected Coverage | Data Source | Notes |
|------------|-------------------|-------------|-------|
| **hydro_yn** | ✅ High (>70%) | problem_list_diagnoses | 427 records found |
| **medical_conditions_present_at_event(11)** | ✅ High (>70%) | problem_list_diagnoses | Hydrocephalus flag |
| **hydro_event_date** | ✅ High (>70%) | problem_list_diagnoses | onset_date_time |
| **hydro_method_diagnosed** | ⚠️ Medium (30-70%) | diagnostic_report | Need imaging studies |
| **shunt_required** | ✅ High (>70%) | procedure | 1,196 procedures |
| **hydro_surgical_management** | ✅ High (>70%) | procedure | Type classification |
| **hydro_intervention** | ✅ High (>70%) | procedure + encounter | Surgical/medical |
| **hydro_shunt_programmable** | ⚠️ Medium (30-70%) | procedure_note + device | NLP extraction |
| **hydro_nonsurg_management** | ❌ Low (<30%) | medication_request | Limited documentation |
| **hydro_nonsurg_management_other** | ❌ Low (<30%) | Document NLP | Free text |
| **hydro_surgical_management_other** | ❌ Low (<30%) | Document NLP | Free text |

---

## Next Steps

1. ✅ **COMPLETE**: Initial data assessment
2. ⏳ **IN PROGRESS**: Create v_hydrocephalus_diagnosis view
3. ⏳ **PENDING**: Create v_hydrocephalus_procedures view
4. ⏳ **PENDING**: Test on pilot patients
5. ⏳ **PENDING**: Deploy to Athena
6. ⏳ **PENDING**: Integrate with AthenaQueryAgent

---

## Additional Data Sources to Explore

### High Priority
1. **diagnostic_report table** - For hydro_method_diagnosed (CT vs MRI)
2. **device table** - For programmable shunt identification
3. **procedure_note table** - For programmable valve details in operative notes

### Medium Priority
4. **encounter table** - For hospitalization context (hydro_intervention)
5. **medication_request table** - For steroid therapy (hydro_nonsurg_management)

### Low Priority (Document NLP Required)
6. **document_reference table** - For free-text hydrocephalus management details
7. **observation_note table** - For clinical hydrocephalus assessment notes

---

**Status**: ✅ High-quality structured data available - Ready to create consolidated views
