-- ================================================================================
-- RE-RUN THESE 3 VIEWS TO STANDARDIZE patient_fhir_id COLUMN
-- ================================================================================
-- Date: 2025-10-17
-- Purpose: Standardize all views to use 'patient_fhir_id' as common index column
--
-- Changed views:
--   1. v_procedures (was: proc_subject_reference)
--   2. v_imaging (was: patient_id)
--   3. v_measurements (was: patient_id)
--
-- All now use: patient_fhir_id
-- ================================================================================

-- ================================================================================
-- 1. v_procedures - STANDARDIZED
-- ================================================================================
-- CHANGE: Added patient_fhir_id as first column (kept proc_subject_reference for backward compatibility)

CREATE OR REPLACE VIEW fhir_prd_db.v_procedures AS
WITH procedure_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_system,
        pcc.code_coding_code,
        pcc.code_coding_display,
        CASE
            WHEN LOWER(pcc.code_coding_display) LIKE '%craniotomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%excision%'
                OR LOWER(pcc.code_coding_display) LIKE '%biopsy%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgery%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgical%'
                OR LOWER(pcc.code_coding_display) LIKE '%anesthesia%'
                OR LOWER(pcc.code_coding_display) LIKE '%anes%'
                OR LOWER(pcc.code_coding_display) LIKE '%oper%'
            THEN true
            ELSE false
        END as is_surgical_keyword
    FROM fhir_prd_db.procedure_code_coding pcc
),
procedure_dates AS (
    SELECT
        p.id as procedure_id,
        COALESCE(
            TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)),
            TRY(CAST(SUBSTR(p.performed_period_start, 1, 10) AS DATE))
        ) as procedure_date
    FROM fhir_prd_db.procedure p
)
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_fhir_id,

    -- Main procedure fields (proc_ prefix)
    p.status as proc_status,
    p.performed_date_time as proc_performed_date_time,
    p.performed_period_start as proc_performed_period_start,
    p.performed_period_end as proc_performed_period_end,
    p.performed_string as proc_performed_string,
    p.performed_age_value as proc_performed_age_value,
    p.performed_age_unit as proc_performed_age_unit,
    p.code_text as proc_code_text,
    p.category_text as proc_category_text,
    p.subject_reference as proc_subject_reference,
    p.encounter_reference as proc_encounter_reference,
    p.encounter_display as proc_encounter_display,
    p.location_reference as proc_location_reference,
    p.location_display as proc_location_display,
    p.outcome_text as proc_outcome_text,
    p.recorder_reference as proc_recorder_reference,
    p.recorder_display as proc_recorder_display,
    p.asserter_reference as proc_asserter_reference,
    p.asserter_display as proc_asserter_display,
    p.status_reason_text as proc_status_reason_text,

    -- Procedure date (calculated)
    pd.procedure_date,

    -- Age at procedure (calculated if patient birth_date available)
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        pd.procedure_date)) as age_at_procedure_days,

    -- Procedure code fields (pcc_ prefix)
    pc.code_coding_system as pcc_code_coding_system,
    pc.code_coding_code as pcc_code_coding_code,
    pc.code_coding_display as pcc_code_coding_display,
    pc.is_surgical_keyword,

    -- Procedure location fields (pl_ prefix)
    pl.location_name as pl_location_name,
    pl.location_address_line_1 as pl_location_address_line_1,
    pl.location_address_line_2 as pl_location_address_line_2,
    pl.location_address_city as pl_location_address_city,
    pl.location_address_state as pl_location_address_state,
    pl.location_address_zip as pl_location_address_zip,
    pl.location_address_country as pl_location_address_country,
    pl.location_address_full as pl_location_address_full

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN fhir_prd_db.procedure_location pl ON p.id = pl.procedure_id
LEFT JOIN fhir_prd_db.patient_access pa ON p.subject_reference = pa.id
WHERE p.subject_reference IS NOT NULL;

-- ================================================================================
-- 2. v_imaging - STANDARDIZED
-- ================================================================================
-- CHANGE: Renamed patient_id to patient_fhir_id (first column)

CREATE OR REPLACE VIEW fhir_prd_db.v_imaging AS
WITH report_categories AS (
    SELECT
        diagnostic_report_id,
        LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as category_text
    FROM fhir_prd_db.diagnostic_report_category
    GROUP BY diagnostic_report_id
),
mri_imaging AS (
    SELECT
        mri.patient_id,
        mri.imaging_procedure_id,
        mri.result_datetime as imaging_date,
        mri.imaging_procedure,
        mri.result_diagnostic_report_id,
        'MRI' as imaging_modality,
        results.value_string as result_information,
        results.result_display
    FROM fhir_prd_db.radiology_imaging_mri mri
    LEFT JOIN fhir_prd_db.radiology_imaging_mri_results results
        ON mri.imaging_procedure_id = results.imaging_procedure_id
),
other_imaging AS (
    SELECT
        ri.patient_id,
        ri.imaging_procedure_id,
        ri.result_datetime as imaging_date,
        ri.imaging_procedure,
        ri.result_diagnostic_report_id,
        COALESCE(ri.imaging_procedure, 'Unknown') as imaging_modality,
        CAST(NULL AS VARCHAR) as result_information,
        CAST(NULL AS VARCHAR) as result_display
    FROM fhir_prd_db.radiology_imaging ri
),
combined_imaging AS (
    SELECT * FROM mri_imaging
    UNION ALL
    SELECT * FROM other_imaging
)
SELECT
    ci.patient_id as patient_fhir_id,
    ci.patient_id as patient_mrn,  -- Using FHIR ID
    ci.imaging_procedure_id,
    ci.imaging_date,
    ci.imaging_procedure,
    ci.result_diagnostic_report_id,
    ci.imaging_modality,
    ci.result_information,
    ci.result_display,

    -- Diagnostic report fields
    dr.id as diagnostic_report_id,
    dr.status as report_status,
    dr.conclusion as report_conclusion,
    dr.issued as report_issued,
    dr.effective_period_start as report_effective_period_start,
    dr.effective_period_stop as report_effective_period_stop,
    rc.category_text,

    -- Age at imaging
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(ci.imaging_date, 1, 10) AS DATE)))) as age_at_imaging_days

FROM combined_imaging ci
LEFT JOIN fhir_prd_db.diagnostic_report dr ON ci.result_diagnostic_report_id = dr.id
LEFT JOIN report_categories rc ON dr.id = rc.diagnostic_report_id
LEFT JOIN fhir_prd_db.patient_access pa ON ci.patient_id = pa.id
WHERE ci.patient_id IS NOT NULL
ORDER BY ci.patient_id, ci.imaging_date;

-- ================================================================================
-- 3. v_measurements - STANDARDIZED
-- ================================================================================
-- CHANGE: Renamed patient_id to patient_fhir_id throughout all CTEs

CREATE OR REPLACE VIEW fhir_prd_db.v_measurements AS
WITH observations AS (
    SELECT
        subject_reference as patient_fhir_id,
        id as obs_observation_id,
        code_text as obs_measurement_type,
        value_quantity_value as obs_measurement_value,
        value_quantity_unit as obs_measurement_unit,
        effective_date_time as obs_measurement_date,
        issued as obs_issued,
        status as obs_status,
        encounter_reference as obs_encounter_reference,
        'observation' as source_table,
        CAST(NULL AS VARCHAR) as lt_test_id,
        CAST(NULL AS VARCHAR) as lt_measurement_type,
        CAST(NULL AS VARCHAR) as lt_measurement_date,
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
        CAST(NULL AS VARCHAR) as obs_measurement_date,
        CAST(NULL AS VARCHAR) as obs_issued,
        CAST(NULL AS VARCHAR) as obs_status,
        CAST(NULL AS VARCHAR) as obs_encounter_reference,
        'lab_tests' as source_table,
        lt.test_id as lt_test_id,
        lt.lab_test_name as lt_measurement_type,
        lt.result_datetime as lt_measurement_date,
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
    combined.*,
    pa.birth_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(COALESCE(obs_measurement_date, lt_measurement_date), 1, 10) AS DATE))) as age_at_measurement_days,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(COALESCE(obs_measurement_date, lt_measurement_date), 1, 10) AS DATE)) / 365.25) as age_at_measurement_years
FROM (
    SELECT * FROM observations
    UNION ALL
    SELECT * FROM lab_tests_with_results
) combined
LEFT JOIN fhir_prd_db.patient_access pa ON combined.patient_fhir_id = pa.id
ORDER BY combined.patient_fhir_id, COALESCE(obs_measurement_date, lt_measurement_date);

-- ================================================================================
-- VERIFICATION QUERIES
-- ================================================================================
-- Run these to verify the changes worked:

-- Check v_procedures has patient_fhir_id
SELECT patient_fhir_id, procedure_fhir_id
FROM fhir_prd_db.v_procedures
LIMIT 5;

-- Check v_imaging has patient_fhir_id
SELECT patient_fhir_id, imaging_procedure_id
FROM fhir_prd_db.v_imaging
LIMIT 5;

-- Check v_measurements has patient_fhir_id
SELECT patient_fhir_id, source_table, obs_observation_id, lt_test_id
FROM fhir_prd_db.v_measurements
LIMIT 5;
