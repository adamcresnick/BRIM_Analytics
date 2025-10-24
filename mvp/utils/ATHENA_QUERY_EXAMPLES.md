# Athena Query Examples

Common Athena query patterns for RADIANT FHIR database views.

**Database**: `fhir_prd_db`
**Schema Reference**: [Athena_Schema.csv](Athena_Schema.csv)

---

## Table of Contents

1. [Patient Demographics](#patient-demographics)
2. [Imaging Studies](#imaging-studies)
3. [Procedures and Surgeries](#procedures-and-surgeries)
4. [Operative Notes and Binary Files](#operative-notes-and-binary-files)
5. [Radiation Therapy](#radiation-therapy)
6. [Chemotherapy Medications](#chemotherapy-medications)
7. [Progress Notes](#progress-notes)
8. [Diagnoses](#diagnoses)
9. [Encounters](#encounters)
10. [Cohort Analysis](#cohort-analysis)

---

## Patient Demographics

### Get all patients in cohort
```sql
SELECT DISTINCT patient_fhir_id
FROM fhir_prd_db.v_procedures_tumor
WHERE is_tumor_surgery = true
ORDER BY patient_fhir_id;
```

### Count patients by tumor surgery status
```sql
SELECT
    is_tumor_surgery,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_procedures_tumor
GROUP BY is_tumor_surgery;
```

---

## Imaging Studies

### Get all imaging studies for a patient
```sql
SELECT
    imaging_study_fhir_id,
    imaging_date,
    modality,
    body_site_text,
    procedure_code_text,
    number_of_series,
    number_of_instances,
    imaging_status,
    age_at_imaging_days
FROM fhir_prd_db.v_imaging
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY imaging_date;
```

### Get imaging studies by modality
```sql
SELECT
    imaging_date,
    modality,
    body_site_text,
    procedure_code_text
FROM fhir_prd_db.v_imaging
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND modality IN ('MR', 'CT', 'PT')
ORDER BY imaging_date;
```

### Find imaging reports (from DocumentReferences)
```sql
SELECT
    document_reference_id,
    dr_date,
    dr_type_text,
    dr_category_text,
    dr_description,
    binary_id,
    content_type
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND (
        dr_category_text LIKE '%Radiology%'
        OR dr_type_text LIKE '%Radiology%'
        OR dr_type_text LIKE '%Imaging%'
    )
ORDER BY dr_date;
```

### Count imaging studies by year
```sql
SELECT
    YEAR(imaging_date) as year,
    modality,
    COUNT(*) as study_count
FROM fhir_prd_db.v_imaging
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
GROUP BY YEAR(imaging_date), modality
ORDER BY year, modality;
```

---

## Procedures and Surgeries

### Get all tumor surgeries for a patient
```sql
SELECT
    procedure_fhir_id,
    procedure_date,
    procedure_code_text,
    procedure_category,
    is_tumor_surgery,
    is_tumor_resection,
    procedure_status,
    age_at_procedure_days
FROM fhir_prd_db.v_procedures_tumor
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND is_tumor_surgery = true
ORDER BY procedure_date;
```

### Get tumor surgeries with specific categories
```sql
SELECT
    procedure_date,
    procedure_code_text,
    procedure_category,
    is_tumor_resection,
    is_csf_management,
    is_intrathecal_chemo,
    is_central_line,
    is_biopsy
FROM fhir_prd_db.v_procedures_tumor
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY procedure_date;
```

### Count surgeries by category
```sql
SELECT
    procedure_category,
    COUNT(*) as procedure_count
FROM fhir_prd_db.v_procedures_tumor
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
GROUP BY procedure_category
ORDER BY procedure_count DESC;
```

---

## Operative Notes and Binary Files

### Find operative notes for a patient
```sql
SELECT
    document_reference_id,
    dr_date,
    dr_type_text,
    dr_context_period_start,
    dr_description,
    binary_id,
    content_type,
    content_size_bytes
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND (
        dr_type_text LIKE 'OP Note%'
        OR dr_type_text = 'Operative Record'
        OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
    )
ORDER BY dr_context_period_start;
```

### Match operative notes to surgeries (exact date match)
```sql
SELECT
    p.procedure_date,
    p.procedure_code_text,
    b.document_reference_id,
    b.dr_type_text,
    b.dr_context_period_start,
    b.binary_id
FROM fhir_prd_db.v_procedures_tumor p
LEFT JOIN fhir_prd_db.v_binary_files b
    ON p.patient_fhir_id = b.patient_fhir_id
    AND DATE(p.procedure_date) = DATE(b.dr_context_period_start)
    AND (
        b.dr_type_text LIKE 'OP Note%'
        OR b.dr_type_text = 'Operative Record'
    )
WHERE p.patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND p.is_tumor_surgery = true
ORDER BY p.procedure_date;
```

### Match operative notes to surgeries (±7 days)
```sql
SELECT
    p.procedure_date,
    p.procedure_code_text,
    b.dr_context_period_start,
    b.dr_type_text,
    ABS(DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start))) as days_diff
FROM fhir_prd_db.v_procedures_tumor p
LEFT JOIN fhir_prd_db.v_binary_files b
    ON p.patient_fhir_id = b.patient_fhir_id
    AND ABS(DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start))) <= 7
    AND (
        b.dr_type_text LIKE 'OP Note%'
        OR b.dr_type_text = 'Operative Record'
    )
WHERE p.patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND p.is_tumor_surgery = true
ORDER BY p.procedure_date, days_diff;
```

### Get all document types for a patient
```sql
SELECT
    dr_type_text,
    COUNT(*) as count
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
GROUP BY dr_type_text
ORDER BY count DESC;
```

---

## Radiation Therapy

### Get radiation summary for a patient
```sql
SELECT
    radiation_course_number,
    course_start_date,
    course_end_date,
    duration_days,
    total_dose_cgy,
    fraction_count,
    modality,
    technique,
    target_site,
    target_site_category,
    is_proton,
    is_photon
FROM fhir_prd_db.v_radiation_summary
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY radiation_course_number;
```

### Get radiation treatment details
```sql
SELECT
    treatment_date,
    dose_cgy,
    fraction_number,
    modality,
    technique,
    target_site
FROM fhir_prd_db.v_radiation_treatments
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY treatment_date;
```

### Get radiation care plan hierarchy
```sql
SELECT
    care_plan_fhir_id,
    care_plan_title,
    care_plan_intent,
    care_plan_status,
    period_start,
    period_end,
    parent_care_plan_id,
    hierarchy_level
FROM fhir_prd_db.v_radiation_care_plan_hierarchy
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY period_start;
```

### Count radiation courses by modality
```sql
SELECT
    modality,
    COUNT(*) as course_count,
    SUM(total_dose_cgy) as total_dose,
    SUM(fraction_count) as total_fractions
FROM fhir_prd_db.v_radiation_summary
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
GROUP BY modality;
```

---

## Chemotherapy Medications

### Get all chemotherapy medications for a patient
```sql
SELECT
    medication_fhir_id,
    medication_name,
    rxnorm_cui,
    medication_status,
    intent,
    start_datetime,
    stop_datetime,
    duration_days,
    route_of_administration,
    dose_value,
    dose_unit
FROM fhir_prd_db.v_chemo_medications
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY start_datetime;
```

### Get chemo medications with specific intent
```sql
SELECT
    medication_name,
    start_datetime,
    stop_datetime,
    duration_days,
    intent,
    medication_status
FROM fhir_prd_db.v_chemo_medications
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND intent IN ('order', 'plan', 'proposal')
ORDER BY start_datetime;
```

### Find concomitant medications with chemotherapy
```sql
SELECT
    chemo_medication_name,
    chemo_start_datetime,
    chemo_stop_datetime,
    conmed_medication_name,
    conmed_category,
    overlap_start_datetime,
    overlap_stop_datetime,
    overlap_duration_days
FROM fhir_prd_db.v_concomitant_medications
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY overlap_start_datetime;
```

---

## Progress Notes

### Get progress notes for a patient
```sql
SELECT
    document_reference_id,
    dr_date,
    dr_context_period_start,
    dr_type_text,
    dr_category_text,
    dr_description,
    binary_id
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND (
        dr_type_text LIKE '%Progress Note%'
        OR dr_type_text LIKE '%Clinical Note%'
        OR dr_type_text = 'Consultation Note'
    )
ORDER BY dr_context_period_start;
```

### Find progress notes near surgeries (±30 days)
```sql
SELECT
    p.procedure_date,
    p.procedure_code_text,
    b.dr_context_period_start,
    b.dr_type_text,
    b.dr_description,
    DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start)) as days_from_surgery
FROM fhir_prd_db.v_procedures_tumor p
CROSS JOIN fhir_prd_db.v_binary_files b
WHERE p.patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND b.patient_fhir_id = p.patient_fhir_id
    AND p.is_tumor_surgery = true
    AND b.dr_type_text LIKE '%Progress Note%'
    AND ABS(DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start))) <= 30
ORDER BY p.procedure_date, days_from_surgery;
```

---

## Diagnoses

### Get all diagnoses for a patient
```sql
SELECT
    condition_id,
    diagnosis_name,
    clinical_status_text,
    onset_date_time,
    recorded_date,
    icd10_code,
    icd10_display,
    snomed_code,
    snomed_display
FROM fhir_prd_db.v_diagnoses
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY onset_date_time;
```

### Find tumor-related diagnoses
```sql
SELECT
    diagnosis_name,
    onset_date_time,
    icd10_code,
    clinical_status_text
FROM fhir_prd_db.v_diagnoses
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND (
        diagnosis_name LIKE '%tumor%'
        OR diagnosis_name LIKE '%neoplasm%'
        OR diagnosis_name LIKE '%cancer%'
        OR icd10_code LIKE 'C%'
        OR icd10_code LIKE 'D%'
    )
ORDER BY onset_date_time;
```

---

## Encounters

### Get all encounters for a patient
```sql
SELECT
    encounter_fhir_id,
    encounter_date,
    status,
    class_code,
    class_display,
    service_type_text,
    period_start,
    period_end,
    length_value,
    length_unit
FROM fhir_prd_db.v_encounters
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
ORDER BY encounter_date;
```

### Find inpatient encounters
```sql
SELECT
    encounter_date,
    class_display,
    service_type_text,
    period_start,
    period_end,
    length_value,
    length_unit
FROM fhir_prd_db.v_encounters
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND (
        class_code = 'IMP'
        OR class_display LIKE '%Inpatient%'
    )
ORDER BY encounter_date;
```

---

## Cohort Analysis

### Count patients with radiation therapy
```sql
SELECT COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_radiation_summary;
```

### Count patients with chemotherapy
```sql
SELECT COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_chemo_medications;
```

### Operative note coverage by patient
```sql
SELECT
    p.patient_fhir_id,
    COUNT(DISTINCT p.procedure_fhir_id) as surgery_count,
    COUNT(DISTINCT b.document_reference_id) as opnote_count,
    CAST(COUNT(DISTINCT b.document_reference_id) AS DOUBLE) / NULLIF(COUNT(DISTINCT p.procedure_fhir_id), 0) as coverage_ratio
FROM fhir_prd_db.v_procedures_tumor p
LEFT JOIN fhir_prd_db.v_binary_files b
    ON p.patient_fhir_id = b.patient_fhir_id
    AND ABS(DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start))) <= 7
    AND (
        b.dr_type_text LIKE 'OP Note%'
        OR b.dr_type_text = 'Operative Record'
    )
WHERE p.is_tumor_surgery = true
GROUP BY p.patient_fhir_id
ORDER BY coverage_ratio DESC;
```

### Patients with complete data (imaging + surgery + radiation + chemo)
```sql
WITH patient_data AS (
    SELECT DISTINCT patient_fhir_id, 'imaging' as data_type
    FROM fhir_prd_db.v_imaging

    UNION

    SELECT DISTINCT patient_fhir_id, 'surgery' as data_type
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = true

    UNION

    SELECT DISTINCT patient_fhir_id, 'radiation' as data_type
    FROM fhir_prd_db.v_radiation_summary

    UNION

    SELECT DISTINCT patient_fhir_id, 'chemo' as data_type
    FROM fhir_prd_db.v_chemo_medications
)
SELECT
    patient_fhir_id,
    COUNT(DISTINCT data_type) as data_type_count,
    ARRAY_AGG(DISTINCT data_type) as available_data_types
FROM patient_data
GROUP BY patient_fhir_id
HAVING COUNT(DISTINCT data_type) = 4
ORDER BY patient_fhir_id;
```

### Find patients suitable for extraction (has surgery + imaging + radiation)
```sql
WITH imaging_patients AS (
    SELECT DISTINCT patient_fhir_id
    FROM fhir_prd_db.v_binary_files
    WHERE (
        dr_category_text LIKE '%Radiology%'
        OR dr_type_text LIKE '%Radiology%'
        OR dr_type_text LIKE '%Imaging%'
    )
),
surgery_patients AS (
    SELECT DISTINCT patient_fhir_id
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = true
),
radiation_patients AS (
    SELECT DISTINCT patient_fhir_id
    FROM fhir_prd_db.v_radiation_summary
)
SELECT
    s.patient_fhir_id,
    COUNT(DISTINCT p.procedure_fhir_id) as surgery_count,
    COUNT(DISTINCT i.document_reference_id) as imaging_count,
    COUNT(DISTINCT r.radiation_course_number) as radiation_course_count
FROM surgery_patients s
INNER JOIN imaging_patients i ON s.patient_fhir_id = i.patient_fhir_id
INNER JOIN radiation_patients r ON s.patient_fhir_id = r.patient_fhir_id
LEFT JOIN fhir_prd_db.v_procedures_tumor p
    ON s.patient_fhir_id = p.patient_fhir_id
    AND p.is_tumor_surgery = true
LEFT JOIN fhir_prd_db.v_binary_files i_docs
    ON i.patient_fhir_id = i_docs.patient_fhir_id
    AND (
        i_docs.dr_category_text LIKE '%Radiology%'
        OR i_docs.dr_type_text LIKE '%Radiology%'
    )
LEFT JOIN fhir_prd_db.v_radiation_summary r_summary
    ON r.patient_fhir_id = r_summary.patient_fhir_id
GROUP BY s.patient_fhir_id
ORDER BY surgery_count DESC, imaging_count DESC;
```

---

## Performance Tips

1. **Always filter by patient_fhir_id first** - This is the most selective filter
2. **Use DATE() for date comparisons** - Ensures proper type handling
3. **Use LIMIT for testing** - Add `LIMIT 10` when developing queries
4. **Index-friendly patterns**:
   - Use `=` instead of `LIKE` when possible
   - Use `IN` for multiple exact matches
   - Use `>=` and `<=` for date ranges instead of `BETWEEN`

### Example: Efficient date range query
```sql
-- Good (index-friendly)
SELECT *
FROM fhir_prd_db.v_imaging
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND imaging_date >= DATE '2020-01-01'
    AND imaging_date <= DATE '2023-12-31';

-- Less efficient
SELECT *
FROM fhir_prd_db.v_imaging
WHERE patient_fhir_id = 'Patient/YOUR_PATIENT_ID'
    AND imaging_date BETWEEN DATE '2020-01-01' AND DATE '2023-12-31';
```

---

## Common Joins

### Surgery + Operative Note
```sql
FROM fhir_prd_db.v_procedures_tumor p
LEFT JOIN fhir_prd_db.v_binary_files b
    ON p.patient_fhir_id = b.patient_fhir_id
    AND DATE(p.procedure_date) = DATE(b.dr_context_period_start)
```

### Surgery + Imaging (within ±30 days)
```sql
FROM fhir_prd_db.v_procedures_tumor p
LEFT JOIN fhir_prd_db.v_imaging i
    ON p.patient_fhir_id = i.patient_fhir_id
    AND ABS(DATE_DIFF('day', DATE(p.procedure_date), i.imaging_date)) <= 30
```

### Patient + All Data Sources
```sql
FROM fhir_prd_db.v_procedures_tumor p
LEFT JOIN fhir_prd_db.v_imaging i
    ON p.patient_fhir_id = i.patient_fhir_id
LEFT JOIN fhir_prd_db.v_radiation_summary r
    ON p.patient_fhir_id = r.patient_fhir_id
LEFT JOIN fhir_prd_db.v_chemo_medications c
    ON p.patient_fhir_id = c.patient_fhir_id
```

---

## Date Functions

```sql
-- Extract date parts
YEAR(imaging_date)
MONTH(imaging_date)
DAY(imaging_date)

-- Date difference
DATE_DIFF('day', date1, date2)
DATE_DIFF('month', date1, date2)
DATE_DIFF('year', date1, date2)

-- Date arithmetic
DATE_ADD('day', 7, imaging_date)
DATE_ADD('month', 1, imaging_date)

-- Convert timestamp to date
DATE(dr_context_period_start)
CAST(dr_date AS DATE)

-- Format dates
DATE_FORMAT(imaging_date, '%Y-%m-%d')
```

---

## Useful WHERE Clause Patterns

### Document type filters
```sql
-- Operative notes
WHERE (
    dr_type_text LIKE 'OP Note%'
    OR dr_type_text = 'Operative Record'
    OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
)

-- Progress notes
WHERE (
    dr_type_text LIKE '%Progress Note%'
    OR dr_type_text LIKE '%Clinical Note%'
    OR dr_type_text = 'Consultation Note'
)

-- Imaging reports
WHERE (
    dr_category_text LIKE '%Radiology%'
    OR dr_type_text LIKE '%Radiology%'
    OR dr_type_text LIKE '%Imaging%'
)
```

### Procedure category filters
```sql
-- Tumor resections only
WHERE is_tumor_resection = true

-- Any tumor surgery
WHERE is_tumor_surgery = true

-- CSF management procedures
WHERE is_csf_management = true

-- Biopsies
WHERE is_biopsy = true
```

### Status filters
```sql
-- Active/completed only
WHERE clinical_status_text IN ('active', 'completed')

-- Exclude entered-in-error
WHERE status != 'entered-in-error'
```

---

## Need Help?

For specific query requirements, refer to:
- **Schema Reference**: [Athena_Schema.csv](Athena_Schema.csv)
- **Extraction Script**: [run_full_multi_source_abstraction.py](../scripts/run_full_multi_source_abstraction.py)
- **View Documentation**: Check with data team for view definitions and update frequency
