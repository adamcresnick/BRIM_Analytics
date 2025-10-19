# Hydrocephalus Data Assessment - Ready to Execute
**Date**: October 18, 2025
**Status**: Queries ready for Athena execution

---

## Files Created

1. **[HYDROCEPHALUS_SHUNT_DATA_DICTIONARY_ANALYSIS.md](HYDROCEPHALUS_SHUNT_DATA_DICTIONARY_ANALYSIS.md)** - Complete analysis of 11 CBTN fields with FHIR mapping strategy
2. **[HYDROCEPHALUS_DATA_ASSESSMENT_QUERIES.sql](HYDROCEPHALUS_DATA_ASSESSMENT_QUERIES.sql)** - 7 assessment queries ready to execute
3. **test_hydrocephalus_queries.py** - Python script (requires AWS SSO login)

---

## Quick Start: Execute in Athena

### Step 1: Cohort-Wide Coverage Assessment

**Run this first to understand overall data availability:**

```sql
-- Count of patients with hydrocephalus conditions
SELECT
    'Hydrocephalus Conditions' as data_type,
    COUNT(DISTINCT c.subject_reference) as patient_count,
    COUNT(c.id) as record_count
FROM fhir_prd_db.condition c
WHERE c.subject_reference IS NOT NULL
  AND (
      LOWER(c.code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(c.code_coding, 'G91\\.')
      OR REGEXP_LIKE(c.code_coding, 'Q03\\.')
  )

UNION ALL

-- Count of patients with shunt procedures
SELECT
    'Shunt Procedures' as data_type,
    COUNT(DISTINCT p.subject_reference) as patient_count,
    COUNT(p.id) as record_count
FROM fhir_prd_db.procedure p
WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
  )

UNION ALL

-- Count of patients with shunt devices
SELECT
    'Shunt Devices' as data_type,
    COUNT(DISTINCT d.patient_reference) as patient_count,
    COUNT(d.id) as record_count
FROM fhir_prd_db.device d
WHERE d.patient_reference IS NOT NULL
  AND (
      LOWER(d.type_text) LIKE '%shunt%'
      OR LOWER(d.device_name) LIKE '%ventriculo%'
  )

UNION ALL

-- Count of patients with hydrocephalus imaging findings
SELECT
    'Hydrocephalus Imaging' as data_type,
    COUNT(DISTINCT dr.subject_reference) as patient_count,
    COUNT(dr.id) as record_count
FROM fhir_prd_db.diagnostic_report dr
WHERE dr.subject_reference IS NOT NULL
  AND (
      LOWER(dr.conclusion) LIKE '%hydroceph%'
      OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
  );
```

**Expected Output**: 4 rows showing patient counts and record counts for each data type

---

### Step 2: Test Patient Detailed Assessment

**Test for hydrocephalus conditions:**

```sql
SELECT
    c.subject_reference as patient_fhir_id,
    c.id as condition_id,
    c.code_text,
    c.code_coding,
    c.clinical_status,
    c.onset_date_time,
    c.recorded_date,

    CASE
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.0') THEN 'Communicating hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.1') THEN 'Obstructive hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.2') THEN 'Normal-pressure hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.3') THEN 'Post-traumatic hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.8') THEN 'Other hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.9') THEN 'Hydrocephalus, unspecified'
        WHEN REGEXP_LIKE(c.code_coding, 'Q03\\.') THEN 'Congenital hydrocephalus'
        ELSE 'Hydrocephalus (text match)'
    END as hydrocephalus_type

FROM fhir_prd_db.condition c
WHERE c.subject_reference IS NOT NULL
  AND (
      LOWER(c.code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(c.code_coding, 'G91\\.')
      OR REGEXP_LIKE(c.code_coding, 'Q03\\.')
  )
  AND c.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY c.subject_reference, c.onset_date_time;
```

**Test for shunt procedures:**

```sql
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text,
    p.code_coding,
    p.status,
    p.performed_period_start,

    CASE
        WHEN LOWER(p.code_text) LIKE '%ventriculoperitoneal%'
             OR LOWER(p.code_text) LIKE '%vp%shunt%'
             OR LOWER(p.code_text) LIKE '%vps%' THEN 'VPS'
        WHEN LOWER(p.code_text) LIKE '%endoscopic%third%ventriculostomy%'
             OR LOWER(p.code_text) LIKE '%etv%' THEN 'ETV'
        WHEN LOWER(p.code_text) LIKE '%external%ventricular%drain%'
             OR LOWER(p.code_text) LIKE '%evd%' THEN 'EVD'
        ELSE 'Other Shunt'
    END as shunt_type,

    CASE
        WHEN LOWER(p.code_text) LIKE '%placement%'
             OR LOWER(p.code_text) LIKE '%insertion%' THEN 'Initial Placement'
        WHEN LOWER(p.code_text) LIKE '%revision%'
             OR LOWER(p.code_text) LIKE '%replacement%' THEN 'Revision'
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
  AND p.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY p.subject_reference, p.performed_period_start;
```

---

## CBTN Fields Mapped to Queries

| CBTN Field | Query | Expected Coverage |
|------------|-------|-------------------|
| hydro_yn | Query 1 (Conditions) | High (>70%) |
| medical_conditions_present_at_event(11) | Query 1 (Conditions) | High (>70%) |
| shunt_required | Query 2 (Procedures) | High (>70%) |
| hydro_surgical_management | Query 2 (Procedures) | High (>70%) |
| hydro_event_date | Query 1 (Conditions) onset_date | High (>70%) |
| hydro_method_diagnosed | Query 4 (Imaging) | Medium (30-70%) |
| hydro_shunt_programmable | Query 3 (Devices) + Query 7 (Notes) | Medium (30-70%) |
| hydro_intervention | Query 2 (Procedures) + Encounters | Medium (30-70%) |
| hydro_nonsurg_management | Query 5 (Medications) | Low (<30%) |
| hydro_nonsurg_management_other | Document NLP | Low (<30%) |
| hydro_surgical_management_other | Document NLP | Low (<30%) |

---

## Next Steps After Query Execution

1. **Document results** in a new file: `HYDROCEPHALUS_DATA_ASSESSMENT_RESULTS.md`
2. **Create consolidated views** based on actual data availability
3. **Identify NLP extraction needs** for low-coverage fields
4. **Design v_hydrocephalus_diagnosis view**
5. **Design v_hydrocephalus_procedures view**

---

## All Assessment Queries Available

The complete set of 7 queries is in: **[HYDROCEPHALUS_DATA_ASSESSMENT_QUERIES.sql](HYDROCEPHALUS_DATA_ASSESSMENT_QUERIES.sql)**

1. Query 1: Hydrocephalus Conditions
2. Query 2: Shunt Procedures
3. Query 3: Programmable Shunt Devices
4. Query 4: Imaging Studies for Hydrocephalus Diagnosis
5. Query 5: Medical Management - Steroids
6. Query 6: Cohort-Wide Assessment (START HERE)
7. Query 7: Detailed Procedure Notes

---

## Analysis Documentation

Comprehensive field analysis with ICD-10 codes, CPT codes, and device manufacturers:
**[HYDROCEPHALUS_SHUNT_DATA_DICTIONARY_ANALYSIS.md](HYDROCEPHALUS_SHUNT_DATA_DICTIONARY_ANALYSIS.md)**

Includes:
- 11 CBTN data dictionary fields documented
- 8 FHIR source tables mapped
- 5 structured query patterns designed
- Expected ICD-10 codes (G91.%, Q03.%)
- Expected CPT codes (62220, 62223, 62230, 62252, etc.)
- Programmable shunt brands (Medtronic Strata, Codman Hakim, etc.)

---

**Status**: ✅ Ready for execution - AWS SSO login required for Python script, or execute SQL directly in Athena console
