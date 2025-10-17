-- ================================================================================
-- DATE/TIME STANDARDIZATION EXAMPLE
-- ================================================================================
-- Purpose: Show how to implement hybrid date/datetime approach
-- Example: v_measurements (most complex - UNION of two sources)
-- ================================================================================

-- BEFORE: Mixed date formats in output
-- obs_measurement_date: "2025-01-24T09:02:00Z" (ISO 8601 with time)
-- lt_measurement_date: "2010-08-05T16:00:00Z" (ISO 8601 with time)
-- Python scripts must handle both formats

-- AFTER: Consistent date format + separate datetime column
-- measurement_date: "2025-01-24" (always YYYY-MM-DD)
-- measurement_datetime: "2025-01-24T09:02:00Z" (always full ISO 8601)
-- Python scripts can rely on consistent format

CREATE OR REPLACE VIEW fhir_prd_db.v_measurements AS
WITH observations AS (
    SELECT
        subject_reference as patient_fhir_id,
        id as obs_observation_id,
        code_text as obs_measurement_type,
        value_quantity_value as obs_measurement_value,
        value_quantity_unit as obs_measurement_unit,

        -- NEW: Add date-only column (consistent format)
        SUBSTR(effective_date_time, 1, 10) as measurement_date,

        -- NEW: Keep full datetime (for precise ordering)
        effective_date_time as measurement_datetime,

        -- DEPRECATED: Keep old column for backward compatibility
        effective_date_time as obs_measurement_date,

        issued as obs_issued,
        SUBSTR(issued, 1, 10) as obs_issued_date,  -- NEW: date-only

        status as obs_status,
        encounter_reference as obs_encounter_reference,
        'observation' as source_table,

        -- NULL columns for lab_tests (needed for UNION)
        CAST(NULL AS VARCHAR) as lt_test_id,
        CAST(NULL AS VARCHAR) as lt_measurement_type,
        CAST(NULL AS VARCHAR) as lt_measurement_date,  -- DEPRECATED
        CAST(NULL AS VARCHAR) as lt_status,
        CAST(NULL AS VARCHAR) as lt_result_diagnostic_report_id,
        CAST(NULL AS VARCHAR) as lt_lab_test_requester,
        CAST(NULL AS VARCHAR) as ltr_test_component,
        CAST(NULL AS VARCHAR) as ltr_value_string,
        CAST(NULL AS VARCHAR) as ltr_measurement_value,
        CAST(NULL AS VARCHAR) as ltr_measurement_unit,
        CAST(NULL AS VARCHAR) as ltr_value_codeable_concept_text,
        CAST(NULL AS VARCHAR) as ltr_value_range_low_value,
        CAST(NULL AS VARCHAR) as ltr_value_range_low_unit,
        CAST(NULL AS VARCHAR) as ltr_value_range_high_value,
        CAST(NULL AS VARCHAR) as ltr_value_range_high_unit,
        CAST(NULL AS VARCHAR) as ltr_value_boolean,
        CAST(NULL AS VARCHAR) as ltr_value_integer
    FROM fhir_prd_db.observation
    WHERE subject_reference IS NOT NULL
),
lab_tests_with_results AS (
    SELECT
        lt.patient_id as patient_fhir_id,
        CAST(NULL AS VARCHAR) as obs_observation_id,
        CAST(NULL AS VARCHAR) as obs_measurement_type,
        CAST(NULL AS VARCHAR) as obs_measurement_value,
        CAST(NULL AS VARCHAR) as obs_measurement_unit,

        -- NEW: Add date-only column (consistent format)
        SUBSTR(lt.result_datetime, 1, 10) as measurement_date,

        -- NEW: Keep full datetime (for precise ordering)
        lt.result_datetime as measurement_datetime,

        -- DEPRECATED: Keep old column for backward compatibility
        CAST(NULL AS VARCHAR) as obs_measurement_date,

        CAST(NULL AS VARCHAR) as obs_issued,
        CAST(NULL AS VARCHAR) as obs_issued_date,  -- NEW

        CAST(NULL AS VARCHAR) as obs_status,
        CAST(NULL AS VARCHAR) as obs_encounter_reference,
        'lab_tests' as source_table,

        lt.test_id as lt_test_id,
        lt.lab_test_name as lt_measurement_type,
        lt.result_datetime as lt_measurement_date,  -- DEPRECATED
        lt.lab_test_status as lt_status,
        lt.result_diagnostic_report_id as lt_result_diagnostic_report_id,
        lt.lab_test_requester as lt_lab_test_requester,
        ltr.test_component as ltr_test_component,
        ltr.value_string as ltr_value_string,
        ltr.value_quantity_value as ltr_measurement_value,
        ltr.value_quantity_unit as ltr_measurement_unit,
        ltr.value_codeable_concept_text as ltr_value_codeable_concept_text,
        ltr.value_range_low_value as ltr_value_range_low_value,
        ltr.value_range_low_unit as ltr_value_range_low_unit,
        ltr.value_range_high_value as ltr_value_range_high_value,
        ltr.value_range_high_unit as ltr_value_range_high_unit,
        ltr.value_boolean as ltr_value_boolean,
        ltr.value_integer as ltr_value_integer
    FROM fhir_prd_db.lab_tests lt
    LEFT JOIN fhir_prd_db.lab_test_results ltr ON lt.test_id = ltr.test_id
    WHERE lt.patient_id IS NOT NULL
)
SELECT
    combined.patient_fhir_id,

    -- NEW STANDARDIZED COLUMNS (use these going forward)
    combined.measurement_date,      -- YYYY-MM-DD (for filtering, joining)
    combined.measurement_datetime,  -- YYYY-MM-DDTHH:MM:SSZ (for ordering, timezone)

    -- Source-specific columns
    combined.obs_observation_id,
    combined.obs_measurement_type,
    combined.obs_measurement_value,
    combined.obs_measurement_unit,
    combined.obs_measurement_date,  -- DEPRECATED: use measurement_datetime instead
    combined.obs_issued,
    combined.obs_issued_date,       -- NEW: date-only
    combined.obs_status,
    combined.obs_encounter_reference,

    combined.lt_test_id,
    combined.lt_measurement_type,
    combined.lt_measurement_date,   -- DEPRECATED: use measurement_datetime instead
    combined.lt_status,
    combined.lt_result_diagnostic_report_id,
    combined.lt_lab_test_requester,

    combined.source_table,

    -- Lab test result components
    combined.ltr_test_component,
    combined.ltr_value_string,
    combined.ltr_measurement_value,
    combined.ltr_measurement_unit,
    combined.ltr_value_codeable_concept_text,
    combined.ltr_value_range_low_value,
    combined.ltr_value_range_low_unit,
    combined.ltr_value_range_high_value,
    combined.ltr_value_range_high_unit,
    combined.ltr_value_boolean,
    combined.ltr_value_integer,

    -- Patient demographics
    pa.birth_date,

    -- Age calculations (use standardized measurement_date)
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(combined.measurement_date AS DATE)))) as age_at_measurement_days,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(combined.measurement_date AS DATE))) / 365.25) as age_at_measurement_years

FROM (
    SELECT * FROM observations
    UNION ALL
    SELECT * FROM lab_tests_with_results
) combined
LEFT JOIN fhir_prd_db.patient_access pa ON combined.patient_fhir_id = pa.id
ORDER BY combined.patient_fhir_id, combined.measurement_datetime;  -- Use datetime for precise ordering

-- ================================================================================
-- USAGE EXAMPLES
-- ================================================================================

-- Example 1: Filter by date (use measurement_date)
SELECT *
FROM fhir_prd_db.v_measurements
WHERE measurement_date >= '2025-01-01'
  AND measurement_date < '2025-02-01'
  AND patient_fhir_id = 'Patient/xyz';

-- Example 2: Order by precise time (use measurement_datetime)
SELECT measurement_date, measurement_datetime, obs_measurement_type, obs_measurement_value
FROM fhir_prd_db.v_measurements
WHERE patient_fhir_id = 'Patient/xyz'
  AND measurement_date = '2025-01-24'
ORDER BY measurement_datetime;  -- Precise ordering within the day

-- Example 3: Age calculation (automatically uses measurement_date)
SELECT
    patient_fhir_id,
    measurement_date,
    age_at_measurement_days,
    age_at_measurement_years
FROM fhir_prd_db.v_measurements
WHERE patient_fhir_id = 'Patient/xyz'
LIMIT 10;

-- Example 4: Python integration
-- ```python
-- import pandas as pd
--
-- df = athena.query("SELECT * FROM v_measurements WHERE patient_fhir_id = 'Patient/xyz'")
--
-- # Date column is always YYYY-MM-DD - easy to parse
-- df['measurement_date'] = pd.to_datetime(df['measurement_date'], format='%Y-%m-%d')
--
-- # Datetime column is always ISO 8601 - also easy to parse
-- df['measurement_datetime'] = pd.to_datetime(df['measurement_datetime'], format='ISO8601', utc=True)
--
-- # No more mixed formats!
-- ```

-- ================================================================================
-- BENEFITS OF THIS APPROACH
-- ================================================================================

-- 1. CONSISTENT DATE FORMAT
--    Before: Mixed "2025-01-24T09:02:00Z" and "2010-08-05T16:00:00Z"
--    After: Always "2025-01-24" in measurement_date column

-- 2. PRECISION WHEN NEEDED
--    measurement_datetime preserves full ISO 8601 for:
--    - Ordering events within same day
--    - Timezone conversions
--    - Time-series analysis

-- 3. BACKWARD COMPATIBLE
--    Kept obs_measurement_date and lt_measurement_date columns
--    Existing queries still work (deprecated but functional)

-- 4. CLEAR NAMING CONVENTION
--    *_date columns: YYYY-MM-DD (for filtering/joining)
--    *_datetime columns: YYYY-MM-DDTHH:MM:SSZ (for precision/ordering)

-- 5. SIMPLIFIED AGE CALCULATIONS
--    No more COALESCE(obs_measurement_date, lt_measurement_date)
--    Just use measurement_date!

-- ================================================================================
-- MIGRATION PATH
-- ================================================================================

-- Phase 1: Add new columns (this SQL)
--   - Existing queries continue working
--   - New columns available for testing

-- Phase 2: Update Python scripts to use new columns
--   - Change from obs_measurement_date → measurement_date
--   - Change from lt_measurement_date → measurement_datetime (if precision needed)

-- Phase 3: Deprecate old columns (future)
--   - After all scripts updated, remove obs_measurement_date and lt_measurement_date
--   - For now, keep for backward compatibility
