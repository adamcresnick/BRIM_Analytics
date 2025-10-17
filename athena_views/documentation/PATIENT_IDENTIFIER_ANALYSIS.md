# Patient Identifier Column Analysis

**Date**: 2025-10-17
**Purpose**: Document patient identifier columns across all 15 Athena views

---

## Summary

All 15 views now have patient identifier columns. The naming is intentionally **inconsistent** to match the Python extraction scripts exactly:

- **12 views** use `patient_fhir_id`
- **3 views** use different names matching their Python script output:
  - `v_procedures`: `proc_subject_reference`
  - `v_imaging`: `patient_id`
  - `v_measurements`: `patient_id`

## Detailed View-by-View Analysis

### ✅ Views Using `patient_fhir_id` (12 views)

| View | Patient Column | Source Column | Line |
|------|---------------|---------------|------|
| v_patient_demographics | patient_fhir_id | pa.id | 24 |
| v_problem_list_diagnoses | patient_fhir_id | pld.patient_id | 44 |
| v_medications | patient_fhir_id | pm.patient_id | 240 |
| v_encounters | patient_fhir_id | e.subject_reference | 455 |
| v_binary_files | patient_fhir_id | dr.subject_reference | 589 |
| v_molecular_tests | patient_fhir_id | mt.patient_id | 685 |
| v_radiation_treatment_appointments | patient_fhir_id | ap.participant_actor_reference | 714 |
| v_radiation_treatment_courses | patient_fhir_id | sr.subject_reference | 752 |
| v_radiation_care_plan_notes | patient_fhir_id | cp.subject_reference | 783 |
| v_radiation_care_plan_hierarchy | patient_fhir_id | cp.subject_reference | 808 |
| v_radiation_service_request_notes | patient_fhir_id | sr.subject_reference | 833 |
| v_radiation_service_request_rt_history | patient_fhir_id | sr.subject_reference | 860 |

### ✅ Views Using Alternative Patient Identifiers (3 views)

#### 1. v_procedures
- **Patient Column**: `proc_subject_reference`
- **Source**: `p.subject_reference as proc_subject_reference` (line 120)
- **Reason**: Python script outputs `proc_subject_reference` to match column prefixing convention
- **Python Script**: `extract_all_procedures_metadata.py` line 86
  ```python
  p.subject_reference as proc_subject_reference,
  ```

#### 2. v_imaging
- **Patient Column**: `patient_id`
- **Source**: `ci.patient_id` (line 332, NOT aliased)
- **Reason**: Python script outputs `patient_id` because `radiology_imaging_mri` table uses `patient_id`
- **Python Script**: `extract_all_imaging_metadata.py` line 163
  ```python
  patient_id,
  ```

#### 3. v_measurements
- **Patient Column**: `patient_id`
- **Source**: `subject_reference as patient_id` (in UNION ALL branches)
- **Reason**: Python script outputs `patient_id` to simplify UNION of observation/lab_test tables
- **Python Script**: `extract_all_measurements_metadata.py` line 140
  ```python
  subject_reference as patient_id,
  ```

---

## Validation Query Compatibility

All views can be filtered by patient using appropriate column names:

### Standard Query (12 views)
```sql
SELECT * FROM fhir_prd_db.v_patient_demographics
WHERE patient_fhir_id = 'Patient/xyz';
```

### Procedures Query
```sql
SELECT * FROM fhir_prd_db.v_procedures
WHERE proc_subject_reference = 'Patient/xyz';
```

### Imaging Query
```sql
SELECT * FROM fhir_prd_db.v_imaging
WHERE patient_id = 'Patient/xyz';
```

### Measurements Query
```sql
SELECT * FROM fhir_prd_db.v_measurements
WHERE patient_id = 'Patient/xyz';
```

---

## Multi-View Patient Query

To query all views for a specific patient, use CASE-based filtering:

```sql
-- Get all patient data across views
WITH patient_demographics AS (
    SELECT * FROM v_patient_demographics
    WHERE patient_fhir_id = 'Patient/xyz'
),
patient_procedures AS (
    SELECT * FROM v_procedures
    WHERE proc_subject_reference = 'Patient/xyz'
),
patient_imaging AS (
    SELECT * FROM v_imaging
    WHERE patient_id = 'Patient/xyz'
),
patient_measurements AS (
    SELECT * FROM v_measurements
    WHERE patient_id = 'Patient/xyz'
)
-- ... join or UNION as needed
```

---

## Key Findings

### ✅ All Views Have Patient Identifiers
Every view can be filtered by patient - no views are missing patient identifiers.

### ✅ Naming Matches Python Scripts
The "inconsistent" naming is intentional and correct:
- v_procedures uses `proc_` prefix for all procedure table columns (including subject_reference)
- v_imaging uses `patient_id` because the source table `radiology_imaging_mri` uses that column name
- v_measurements uses `patient_id` to simplify UNION ALL across observation/lab_test tables

### ✅ All Views Tested and Working
All 15 views have been tested and successfully query data.

### Recent Fix: v_radiation_treatment_appointments
Originally missing patient identifier. Fixed by:
1. Reading Python script to identify JOIN pattern
2. Adding JOIN to `appointment_participant` table
3. Filtering for `participant_actor_reference LIKE 'Patient/%'`
4. Aliasing as `patient_fhir_id`

---

## Design Rationale

The Python extraction scripts follow a **column prefixing strategy** for data provenance:
- `proc_` prefix for procedure table columns
- `pcc_` prefix for procedure_code_coding table columns
- `imaging_` prefix for imaging-specific columns
- etc.

The Athena views replicate this exact strategy to ensure:
1. Views produce identical CSV output as Python scripts
2. Column names self-document their source table
3. Multiple tables can be merged without column name conflicts

**Example**: v_procedures includes both:
- `proc_subject_reference` (from procedure table)
- `pcc_code_coding_system` (from procedure_code_coding table)

This prefixing prevents ambiguity when joining or analyzing data.

---

## Recommendations

### For Querying Multiple Views
Create a patient identifier mapping helper:

```python
VIEW_PATIENT_COLUMNS = {
    'v_patient_demographics': 'patient_fhir_id',
    'v_problem_list_diagnoses': 'patient_fhir_id',
    'v_procedures': 'proc_subject_reference',  # Note: different!
    'v_medications': 'patient_fhir_id',
    'v_imaging': 'patient_id',  # Note: different!
    'v_encounters': 'patient_fhir_id',
    'v_measurements': 'patient_id',  # Note: different!
    'v_binary_files': 'patient_fhir_id',
    'v_molecular_tests': 'patient_fhir_id',
    'v_radiation_treatment_appointments': 'patient_fhir_id',
    'v_radiation_treatment_courses': 'patient_fhir_id',
    'v_radiation_care_plan_notes': 'patient_fhir_id',
    'v_radiation_care_plan_hierarchy': 'patient_fhir_id',
    'v_radiation_service_request_notes': 'patient_fhir_id',
    'v_radiation_service_request_rt_history': 'patient_fhir_id',
}

def query_view_for_patient(view_name, patient_id):
    patient_col = VIEW_PATIENT_COLUMNS[view_name]
    return f"SELECT * FROM {view_name} WHERE {patient_col} = '{patient_id}'"
```

### For Data Analysis
When merging views, use explicit column names:
```python
# Good - explicit about which patient column
merged = procedures_df.merge(
    imaging_df,
    left_on='proc_subject_reference',
    right_on='patient_id',
    how='inner'
)

# Bad - assumes both use same column name
# merged = procedures_df.merge(imaging_df, on='patient_fhir_id')  # Will fail!
```

---

## Status

✅ **All 15 views validated with patient identifiers**
✅ **All naming matches Python extraction scripts**
✅ **All views tested and working**

**No action required** - views are correct as-is.
