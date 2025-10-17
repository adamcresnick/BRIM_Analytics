# Patient Identifier Standardization Summary

**Date**: 2025-10-17
**Change**: All 15 views now use `patient_fhir_id` as the common patient identifier column

---

## Views That Need to Be Re-Run

If you previously ran these views, you **MUST re-run** these 3 views:

### 1. ✅ v_procedures
- **Before**: Used `proc_subject_reference` as patient identifier
- **After**: Uses `patient_fhir_id` (first column) + keeps `proc_subject_reference` for backward compatibility
- **Location**: Lines 75-191 in ATHENA_VIEW_CREATION_QUERIES.sql
- **SQL to re-run**: See RERUN_STANDARDIZED_VIEWS.sql lines 16-118

### 2. ✅ v_imaging
- **Before**: Used `patient_id` as patient identifier
- **After**: Uses `patient_fhir_id` (first column)
- **Location**: Lines 332-413 in ATHENA_VIEW_CREATION_QUERIES.sql
- **SQL to re-run**: See RERUN_STANDARDIZED_VIEWS.sql lines 120-203

### 3. ✅ v_measurements
- **Before**: Used `patient_id` as patient identifier
- **After**: Uses `patient_fhir_id` throughout all CTEs
- **Location**: Lines 479-561 in ATHENA_VIEW_CREATION_QUERIES.sql
- **SQL to re-run**: See RERUN_STANDARDIZED_VIEWS.sql lines 205-309

---

## Views That DO NOT Need to Be Re-Run

These 12 views already used `patient_fhir_id` and have **NOT changed**:

1. ✅ v_patient_demographics
2. ✅ v_problem_list_diagnoses
3. ✅ v_medications
4. ✅ v_encounters
5. ✅ v_binary_files
6. ✅ v_molecular_tests
7. ✅ v_radiation_treatment_appointments
8. ✅ v_radiation_treatment_courses
9. ✅ v_radiation_care_plan_notes
10. ✅ v_radiation_care_plan_hierarchy
11. ✅ v_radiation_service_request_notes
12. ✅ v_radiation_service_request_rt_history

**No action needed** for these views.

---

## How to Re-Run

### Option 1: Copy from RERUN_STANDARDIZED_VIEWS.sql (Recommended)
```bash
# Open the file
open RERUN_STANDARDIZED_VIEWS.sql

# Copy and paste each CREATE VIEW statement into Athena Console
# Run them one at a time
```

### Option 2: Use AWS CLI
```bash
# Navigate to the directory
cd staging_extraction

# Run each view (example for v_procedures)
aws athena start-query-execution \
  --query-string "$(grep -A 200 'v_procedures' RERUN_STANDARDIZED_VIEWS.sql | head -103)" \
  --query-execution-context Database=fhir_prd_db \
  --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
  --profile 343218191717_AWSAdministratorAccess
```

### Option 3: Python Script
```python
import boto3

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

# Read SQL file
with open('RERUN_STANDARDIZED_VIEWS.sql', 'r') as f:
    sql = f.read()

# Extract individual CREATE VIEW statements
# Split on "CREATE OR REPLACE VIEW" and run each one
# (Implementation left to user)
```

---

## Verification

After re-running the 3 views, verify with these queries:

```sql
-- 1. Check v_procedures
SELECT patient_fhir_id, procedure_fhir_id
FROM fhir_prd_db.v_procedures
LIMIT 5;

-- 2. Check v_imaging
SELECT patient_fhir_id, imaging_procedure_id
FROM fhir_prd_db.v_imaging
LIMIT 5;

-- 3. Check v_measurements
SELECT patient_fhir_id, source_table
FROM fhir_prd_db.v_measurements
LIMIT 5;
```

All three queries should return rows with `patient_fhir_id` as the first column.

---

## Benefits of Standardization

### Before (Inconsistent)
```python
# Had to remember different column names
procedures_df = query("SELECT * FROM v_procedures WHERE proc_subject_reference = 'Patient/xyz'")
imaging_df = query("SELECT * FROM v_imaging WHERE patient_id = 'Patient/xyz'")
measurements_df = query("SELECT * FROM v_measurements WHERE patient_id = 'Patient/xyz'")
```

### After (Consistent)
```python
# Same column name for all views!
procedures_df = query("SELECT * FROM v_procedures WHERE patient_fhir_id = 'Patient/xyz'")
imaging_df = query("SELECT * FROM v_imaging WHERE patient_fhir_id = 'Patient/xyz'")
measurements_df = query("SELECT * FROM v_measurements WHERE patient_fhir_id = 'Patient/xyz'")
```

### Easier Joins
```python
# Can now use consistent column names
merged = procedures_df.merge(
    imaging_df,
    on='patient_fhir_id',  # Same column name!
    how='inner'
)
```

### Simpler Query Generation
```python
def query_view_for_patient(view_name, patient_id):
    # Works for ALL 15 views now
    return f"SELECT * FROM {view_name} WHERE patient_fhir_id = '{patient_id}'"
```

---

## Summary

✅ **Action Required**: Re-run 3 views (v_procedures, v_imaging, v_measurements)
✅ **No Action**: 12 other views already correct
✅ **Benefit**: All 15 views now use `patient_fhir_id` as common index

**Next Step**: Copy the SQL from [RERUN_STANDARDIZED_VIEWS.sql](RERUN_STANDARDIZED_VIEWS.sql) and run in Athena Console.
