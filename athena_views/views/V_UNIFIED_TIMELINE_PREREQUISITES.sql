-- ================================================================================
-- V_UNIFIED_PATIENT_TIMELINE - PREREQUISITE VIEWS
-- ================================================================================
-- Purpose: Create normalized alias views required by v_unified_patient_timeline
-- Version: 2.0 (Updated for datetime-standardized source views)
-- Date: 2025-10-19
--
-- IMPORTANT: This version works with datetime-standardized source views where:
--   - v_problem_list_diagnoses has TIMESTAMP(3) datetime columns
--   - v_radiation_treatments has TIMESTAMP(3) datetime columns
--   - No CAST needed - columns already have proper types
--
-- v_unified_patient_timeline references views with normalized column names (no prefixes)
-- but the actual Athena views use prefixes (pld_, proc_, obs_, etc.)
--
-- This file creates 2 missing alias/normalized views:
--   1. v_diagnoses - Normalizes v_problem_list_diagnoses (removes pld_ prefix)
--   2. v_radiation_summary - Aggregates radiation courses from v_radiation_treatments
--
-- DEPLOYMENT ORDER:
--   1. Run this file FIRST to create prerequisite views
--   2. Then run V_UNIFIED_PATIENT_TIMELINE.sql
-- ================================================================================

-- ================================================================================
-- 1. V_DIAGNOSES - NORMALIZED DIAGNOSIS VIEW
-- ================================================================================
-- Consolidates all diagnosis sources with consistent column naming (no prefixes)
-- Sources:
--   - v_problem_list_diagnoses (primary - uses pld_ prefix)
--   - v_hydrocephalus_diagnosis (supplementary - uses hd_ prefix)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_diagnoses AS
SELECT
    patient_fhir_id,
    pld_condition_id as condition_id,
    pld_diagnosis_name as diagnosis_name,
    pld_clinical_status as clinical_status_text,
    pld_onset_date as onset_date_time,  -- Already TIMESTAMP(3) after standardization
    age_at_onset_days,
    pld_abatement_date as abatement_date_time,  -- Already TIMESTAMP(3) after standardization
    pld_recorded_date as recorded_date,  -- Already TIMESTAMP(3) after standardization
    age_at_recorded_days,
    pld_icd10_code as icd10_code,
    pld_icd10_display as icd10_display,
    TRY_CAST(pld_snomed_code AS BIGINT) as snomed_code,
    pld_snomed_display as snomed_display
FROM fhir_prd_db.v_problem_list_diagnoses;

-- Note: v_hydrocephalus_diagnosis is a subset of v_problem_list_diagnoses
-- We only pull from problem_list_diagnoses to avoid duplicates

-- ================================================================================
-- 2. V_RADIATION_SUMMARY - COURSE-LEVEL RADIATION SUMMARY
-- ================================================================================
-- Aggregates radiation treatment data into per-patient course-level summary
-- Source: v_radiation_treatments (observation-based ELECT intake forms)
--
-- Fields expected by v_unified_patient_timeline:
--   - patient_id (patient_fhir_id)
--   - course_1_start_date
--   - course_1_end_date
--   - course_1_duration_weeks
--   - re_irradiation
--   - treatment_techniques
--   - num_radiation_appointments
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_summary AS
WITH radiation_courses AS (
    SELECT
        patient_fhir_id,
        obs_start_date as start_date,
        obs_stop_date as stop_date,
        obs_radiation_field as radiation_field,
        obs_dose_value as dose_value,
        obs_dose_unit as dose_unit,
        -- Extract course number from obs_course_line_number (e.g., "Course 1" → 1)
        TRY_CAST(REGEXP_EXTRACT(obs_course_line_number, '[0-9]+', 0) AS INTEGER) as course_number,
        obs_status,
        obs_effective_date
    FROM fhir_prd_db.v_radiation_treatments
    WHERE obs_start_date IS NOT NULL
),
course_1_data AS (
    SELECT
        patient_fhir_id,
        MIN(DATE(start_date)) as course_1_start_date,  -- start_date is TIMESTAMP(3) after standardization
        MAX(DATE(stop_date)) as course_1_end_date,  -- stop_date is TIMESTAMP(3) after standardization
        CAST(DATE_DIFF('day',
            MIN(DATE(start_date)),
            MAX(DATE(stop_date))
        ) / 7.0 AS DOUBLE) as course_1_duration_weeks,
        LISTAGG(DISTINCT radiation_field, ', ') WITHIN GROUP (ORDER BY radiation_field) as treatment_techniques,
        COUNT(DISTINCT obs_effective_date) as num_observations
    FROM radiation_courses
    WHERE course_number = 1 OR course_number IS NULL -- Handle cases where course number isn't parsed
    GROUP BY patient_fhir_id
),
re_irradiation_check AS (
    SELECT
        patient_fhir_id,
        CASE
            WHEN MAX(course_number) > 1 THEN 'Yes'
            WHEN COUNT(DISTINCT course_number) > 1 THEN 'Yes'
            ELSE 'No'
        END as re_irradiation
    FROM radiation_courses
    GROUP BY patient_fhir_id
),
appointment_counts AS (
    SELECT
        patient_fhir_id,
        COUNT(*) as num_radiation_appointments
    FROM fhir_prd_db.v_radiation_treatment_appointments
    GROUP BY patient_fhir_id
)
SELECT
    c1.patient_fhir_id as patient_id,  -- Note: unified timeline expects 'patient_id' not 'patient_fhir_id'
    c1.course_1_start_date,
    c1.course_1_end_date,
    c1.course_1_duration_weeks,
    COALESCE(ri.re_irradiation, 'No') as re_irradiation,
    c1.treatment_techniques,
    COALESCE(ac.num_radiation_appointments, 0) as num_radiation_appointments
FROM course_1_data c1
LEFT JOIN re_irradiation_check ri ON c1.patient_fhir_id = ri.patient_fhir_id
LEFT JOIN appointment_counts ac ON c1.patient_fhir_id = ac.patient_fhir_id
WHERE c1.course_1_start_date IS NOT NULL;

-- ================================================================================
-- VALIDATION QUERIES
-- ================================================================================
-- Run these queries after creating the views to verify data

-- Test 1: Verify v_diagnoses has data
/*
SELECT
    'v_diagnoses' as view_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    MIN(onset_date_time) as earliest_diagnosis,
    MAX(onset_date_time) as latest_diagnosis
FROM fhir_prd_db.v_diagnoses;
*/

-- Test 2: Verify v_radiation_summary has data
/*
SELECT
    'v_radiation_summary' as view_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT patient_id) as patient_count,
    MIN(course_1_start_date) as earliest_start,
    MAX(course_1_end_date) as latest_end
FROM fhir_prd_db.v_radiation_summary;
*/

-- Test 3: Check specific patient (e4BwD8ZYDBccepXcJ.Ilo3w3)
/*
SELECT * FROM fhir_prd_db.v_diagnoses
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY onset_date_time;

SELECT * FROM fhir_prd_db.v_radiation_summary
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
*/
