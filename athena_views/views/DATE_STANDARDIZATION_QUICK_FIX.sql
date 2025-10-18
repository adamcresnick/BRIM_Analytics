-- ================================================================================
-- DATE STANDARDIZATION - SIMPLE QUICK FIX
-- ================================================================================
-- Purpose: Standardize all dates to ISO 8601 format with timezone
-- Time to implement: ~30 minutes for all views
-- ================================================================================

-- PROBLEM: Mixed date formats
--   - ISO 8601: "2025-01-24T09:02:00Z"
--   - Date-only: "2012-10-19"

-- SOLUTION: Convert date-only to ISO 8601 by adding midnight UTC
--   - "2012-10-19" → "2012-10-19T00:00:00Z"

-- ================================================================================
-- EXAMPLE 1: v_problem_list_diagnoses (BEFORE)
-- ================================================================================

-- BEFORE: Date-only format
CREATE OR REPLACE VIEW fhir_prd_db.v_problem_list_diagnoses AS
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id as pld_condition_id,
    pld.diagnosis_name as pld_diagnosis_name,
    pld.clinical_status_text as pld_clinical_status,
    pld.onset_date_time as pld_onset_date,                    -- "2012-10-19"
    pld.abatement_date_time as pld_abatement_date,            -- "2012-10-19"
    pld.recorded_date as pld_recorded_date,                   -- "2012-10-19"
    ...
FROM fhir_prd_db.problem_list_diagnoses pld;

-- ================================================================================
-- EXAMPLE 1: v_problem_list_diagnoses (AFTER - FIXED)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_problem_list_diagnoses AS
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id as pld_condition_id,
    pld.diagnosis_name as pld_diagnosis_name,
    pld.clinical_status_text as pld_clinical_status,

    -- FIX: Standardize to ISO 8601
    CASE
        WHEN LENGTH(pld.onset_date_time) = 10
        THEN pld.onset_date_time || 'T00:00:00Z'
        ELSE pld.onset_date_time
    END as pld_onset_date,                                     -- "2012-10-19T00:00:00Z"

    CASE
        WHEN LENGTH(pld.abatement_date_time) = 10
        THEN pld.abatement_date_time || 'T00:00:00Z'
        ELSE pld.abatement_date_time
    END as pld_abatement_date,

    CASE
        WHEN LENGTH(pld.recorded_date) = 10
        THEN pld.recorded_date || 'T00:00:00Z'
        ELSE pld.recorded_date
    END as pld_recorded_date,

    -- Age calculations still work (SUBSTR extracts date portion)
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.onset_date_time, 1, 10) AS DATE))) as age_at_onset_days,
    ...
FROM fhir_prd_db.problem_list_diagnoses pld
LEFT JOIN fhir_prd_db.patient_access pa ON pld.patient_id = pa.id;

-- ================================================================================
-- EXAMPLE 2: v_patient_demographics (BEFORE)
-- ================================================================================

-- BEFORE: Date-only birth_date
CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT
    pa.id as patient_fhir_id,
    pa.birth_date as pd_birth_date,                           -- "2005-05-06"
    ...
FROM fhir_prd_db.patient_access pa;

-- ================================================================================
-- EXAMPLE 2: v_patient_demographics (AFTER - FIXED)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT
    pa.id as patient_fhir_id,

    -- FIX: Standardize birth_date to ISO 8601
    CASE
        WHEN LENGTH(pa.birth_date) = 10
        THEN pa.birth_date || 'T00:00:00Z'
        ELSE pa.birth_date
    END as pd_birth_date,                                      -- "2005-05-06T00:00:00Z"

    pa.gender as pd_gender,
    pa.race as pd_race,
    pa.ethnicity as pd_ethnicity,
    DATE_DIFF('year', DATE(pa.birth_date), CURRENT_DATE) as pd_age_years
FROM fhir_prd_db.patient_access pa;

-- ================================================================================
-- REUSABLE FUNCTION PATTERN
-- ================================================================================

-- You can create a simple pattern for all date columns:

-- Pattern:
CASE
    WHEN LENGTH(source_column) = 10 THEN source_column || 'T00:00:00Z'
    ELSE source_column
END as output_column_name

-- Example usage:
CASE WHEN LENGTH(pld.onset_date_time) = 10 THEN pld.onset_date_time || 'T00:00:00Z' ELSE pld.onset_date_time END as pld_onset_date

-- ================================================================================
-- VIEWS THAT NEED THIS FIX (4 total)
-- ================================================================================

-- 1. v_patient_demographics
--    - pd_birth_date (currently "YYYY-MM-DD")

-- 2. v_problem_list_diagnoses
--    - pld_onset_date (currently "YYYY-MM-DD")
--    - pld_abatement_date (currently "YYYY-MM-DD")
--    - pld_recorded_date (currently "YYYY-MM-DD")

-- 3. v_encounters
--    - Already has encounter_date (YYYY-MM-DD) for filtering
--    - period_start and period_end already ISO 8601
--    - No changes needed

-- 4. v_molecular_tests
--    - mt_test_date (currently extracted with SUBSTR - already "YYYY-MM-DD")
--    - mt_specimen_collection_date (currently extracted with SUBSTR)
--    - mt_procedure_date (currently extracted with SUBSTR)
--    - These are intentionally date-only for consistency
--    - Could convert source columns if needed

-- All other views (11 views) already return ISO 8601 format!

-- ================================================================================
-- ACTUAL WORK REQUIRED
-- ================================================================================

-- Step 1: Update v_patient_demographics (1 column)
-- Step 2: Update v_problem_list_diagnoses (3 columns)
-- Step 3: Optionally update v_molecular_tests (3 columns)

-- Total: ~5-9 columns to update
-- Time: ~15-30 minutes

-- ================================================================================
-- BENEFITS OF THIS APPROACH
-- ================================================================================

-- 1. SIMPLE: Just add 'T00:00:00Z' to date-only strings
-- 2. FAST: One-line change per column
-- 3. CONSISTENT: All dates now ISO 8601 with timezone
-- 4. NO BREAKING CHANGES: Age calculations still work (SUBSTR extracts date)
-- 5. PYTHON FRIENDLY: pandas.to_datetime() handles ISO 8601 perfectly

-- ================================================================================
-- PYTHON BENEFIT
-- ================================================================================

-- Before (mixed formats):
-- df['date_column'] = pd.to_datetime(df['date_column'], errors='coerce')  # Slow, unreliable

-- After (all ISO 8601):
-- df['date_column'] = pd.to_datetime(df['date_column'], format='ISO8601', utc=True)  # Fast, reliable!

-- ================================================================================
-- VERIFICATION
-- ================================================================================

-- Test that it works:
SELECT
    CASE WHEN LENGTH('2012-10-19') = 10 THEN '2012-10-19' || 'T00:00:00Z' ELSE '2012-10-19' END as test1,
    CASE WHEN LENGTH('2025-01-24T09:02:00Z') = 10 THEN '2025-01-24T09:02:00Z' || 'T00:00:00Z' ELSE '2025-01-24T09:02:00Z' END as test2;

-- Result:
-- test1: "2012-10-19T00:00:00Z"  ✅ (converted)
-- test2: "2025-01-24T09:02:00Z"  ✅ (unchanged)
