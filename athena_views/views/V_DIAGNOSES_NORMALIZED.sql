-- ================================================================================
-- V_DIAGNOSES - NORMALIZED DIAGNOSIS VIEW
-- ================================================================================
-- Purpose: Create normalized v_diagnoses view that consolidates all diagnosis sources
--          with consistent column naming (no prefixes) for use in v_unified_patient_timeline
--
-- Sources:
--   - v_problem_list_diagnoses (primary diagnosis source with pld_ prefix)
--   - v_hydrocephalus_diagnosis (hydrocephalus-specific diagnoses)
--
-- This view removes the pld_ prefix and provides consistent naming across diagnosis sources
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_diagnoses AS
SELECT
    patient_fhir_id,
    pld_condition_id as condition_id,
    pld_diagnosis_name as diagnosis_name,
    pld_clinical_status as clinical_status_text,
    pld_onset_date as onset_date_time,
    age_at_onset_days,
    pld_abatement_date as abatement_date_time,
    pld_recorded_date as recorded_date,
    age_at_recorded_days,
    pld_icd10_code as icd10_code,
    pld_icd10_display as icd10_display,
    CAST(pld_snomed_code AS BIGINT) as snomed_code,
    pld_snomed_display as snomed_display
FROM fhir_prd_db.v_problem_list_diagnoses

UNION ALL

-- Add hydrocephalus diagnoses if they exist
SELECT
    patient_fhir_id,
    hd_condition_id as condition_id,
    hd_diagnosis_name as diagnosis_name,
    hd_clinical_status as clinical_status_text,
    hd_onset_date as onset_date_time,
    age_at_onset_days,
    hd_abatement_date as abatement_date_time,
    hd_recorded_date as recorded_date,
    age_at_recorded_days,
    hd_icd10_code as icd10_code,
    hd_icd10_display as icd10_display,
    CAST(hd_snomed_code AS BIGINT) as snomed_code,
    hd_snomed_display as snomed_display
FROM fhir_prd_db.v_hydrocephalus_diagnosis
WHERE hd_condition_id NOT IN (
    SELECT pld_condition_id FROM fhir_prd_db.v_problem_list_diagnoses
);
