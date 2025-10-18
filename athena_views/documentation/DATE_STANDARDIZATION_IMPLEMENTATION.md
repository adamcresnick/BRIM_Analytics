# Date Standardization - Simple Implementation

**Time Required**: 15-30 minutes
**Views to Update**: 2-3 views
**Change**: Add one CASE statement per date column

---

## The Problem (Simplified)

Your FHIR data has **two date formats**:
- **ISO 8601**: `2025-01-24T09:02:00Z` (most tables) ✅
- **Date-only**: `2012-10-19` (a few tables) ❌

This causes issues in Python when parsing dates.

---

## The Solution (One Line of SQL)

Convert date-only to ISO 8601 by adding midnight UTC:

```sql
CASE
    WHEN LENGTH(date_column) = 10 THEN date_column || 'T00:00:00Z'
    ELSE date_column
END as standardized_column
```

**Result**: `2012-10-19` → `2012-10-19T00:00:00Z`

---

## Implementation

### Step 1: Update v_patient_demographics (1 column)

**Current**:
```sql
pa.birth_date as pd_birth_date,  -- "2005-05-06"
```

**Fixed**:
```sql
CASE
    WHEN LENGTH(pa.birth_date) = 10 THEN pa.birth_date || 'T00:00:00Z'
    ELSE pa.birth_date
END as pd_birth_date,  -- "2005-05-06T00:00:00Z"
```

### Step 2: Update v_problem_list_diagnoses (3 columns)

**Current**:
```sql
pld.onset_date_time as pld_onset_date,       -- "2012-10-19"
pld.abatement_date_time as pld_abatement_date,
pld.recorded_date as pld_recorded_date,
```

**Fixed**:
```sql
CASE
    WHEN LENGTH(pld.onset_date_time) = 10 THEN pld.onset_date_time || 'T00:00:00Z'
    ELSE pld.onset_date_time
END as pld_onset_date,  -- "2012-10-19T00:00:00Z"

CASE
    WHEN LENGTH(pld.abatement_date_time) = 10 THEN pld.abatement_date_time || 'T00:00:00Z'
    ELSE pld.abatement_date_time
END as pld_abatement_date,

CASE
    WHEN LENGTH(pld.recorded_date) = 10 THEN pld.recorded_date || 'T00:00:00Z'
    ELSE pld.recorded_date
END as pld_recorded_date,
```

### Step 3: Done! (Optional: v_molecular_tests if you want)

All other 12 views already return ISO 8601 format - no changes needed!

---

## Complete Updated Views

### v_patient_demographics (Complete SQL)

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT
    pa.id as patient_fhir_id,
    pa.gender as pd_gender,
    pa.race as pd_race,
    pa.ethnicity as pd_ethnicity,

    -- FIX: Standardize birth_date to ISO 8601
    CASE
        WHEN LENGTH(pa.birth_date) = 10 THEN pa.birth_date || 'T00:00:00Z'
        ELSE pa.birth_date
    END as pd_birth_date,

    DATE_DIFF('year', DATE(pa.birth_date), CURRENT_DATE) as pd_age_years
FROM fhir_prd_db.patient_access pa
WHERE pa.id IS NOT NULL;
```

### v_problem_list_diagnoses (Complete SQL)

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_problem_list_diagnoses AS
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id as pld_condition_id,
    pld.diagnosis_name as pld_diagnosis_name,
    pld.clinical_status_text as pld_clinical_status,

    -- FIX: Standardize dates to ISO 8601
    CASE
        WHEN LENGTH(pld.onset_date_time) = 10 THEN pld.onset_date_time || 'T00:00:00Z'
        ELSE pld.onset_date_time
    END as pld_onset_date,

    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.onset_date_time, 1, 10) AS DATE))) as age_at_onset_days,

    CASE
        WHEN LENGTH(pld.abatement_date_time) = 10 THEN pld.abatement_date_time || 'T00:00:00Z'
        ELSE pld.abatement_date_time
    END as pld_abatement_date,

    CASE
        WHEN LENGTH(pld.recorded_date) = 10 THEN pld.recorded_date || 'T00:00:00Z'
        ELSE pld.recorded_date
    END as pld_recorded_date,

    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.recorded_date, 1, 10) AS DATE))) as age_at_recorded_days,
    pld.icd10_code as pld_icd10_code,
    pld.icd10_display as pld_icd10_display,
    pld.snomed_code as pld_snomed_code,
    pld.snomed_display as pld_snomed_display
FROM fhir_prd_db.problem_list_diagnoses pld
LEFT JOIN fhir_prd_db.patient_access pa ON pld.patient_id = pa.id
WHERE pld.patient_id IS NOT NULL
ORDER BY pld.patient_id, pld.recorded_date;
```

---

## How to Deploy

### Option 1: AWS Athena Console (Recommended)
1. Copy the SQL from above
2. Open AWS Athena Console
3. Paste and run `CREATE OR REPLACE VIEW ...`
4. Done! (takes ~2 seconds per view)

### Option 2: Python Script
```python
import boto3

session = boto3.Session(profile_name='343218191717_AWSAdministratorAccess')
athena = session.client('athena', region_name='us-east-1')

# Read SQL from file
with open('view_definition.sql', 'r') as f:
    sql = f.read()

# Execute
response = athena.start_query_execution(
    QueryString=sql,
    QueryExecutionContext={'Database': 'fhir_prd_db'},
    ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
)
```

---

## Verification

Test that dates are now standardized:

```sql
-- Test v_patient_demographics
SELECT patient_fhir_id, pd_birth_date
FROM fhir_prd_db.v_patient_demographics
LIMIT 5;

-- Expected output: "2005-05-06T00:00:00Z" (not "2005-05-06")

-- Test v_problem_list_diagnoses
SELECT patient_fhir_id, pld_onset_date, pld_recorded_date
FROM fhir_prd_db.v_problem_list_diagnoses
LIMIT 5;

-- Expected output: "2012-10-19T00:00:00Z" (not "2012-10-19")
```

---

## Python Benefit

**Before** (mixed formats):
```python
# Slow, unpredictable
df['date'] = pd.to_datetime(df['date'], errors='coerce')
```

**After** (all ISO 8601):
```python
# Fast, reliable!
df['date'] = pd.to_datetime(df['date'], format='ISO8601', utc=True)
```

---

## Summary

**Total effort**: 15-30 minutes
**Views to change**: 2 views
**Columns to change**: 4 columns total
**SQL pattern**: Add one CASE statement per column
**Result**: All dates now ISO 8601 format with timezone

---

## Why This is Better Than My Original Proposal

My original proposal (hybrid approach with both `*_date` and `*_datetime` columns) was **over-engineered**:
- ❌ Would have added 30+ new columns
- ❌ Would have taken 4-6 hours
- ❌ More complexity

This simple approach:
- ✅ Changes only 4 columns
- ✅ Takes 15-30 minutes
- ✅ Simpler, cleaner result
- ✅ All dates in one consistent format

**You were right** - this is much simpler! 🎯
