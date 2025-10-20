-- ================================================================================
-- UNIFIED PATIENT TIMELINE VIEW - COMPLETE VERSION
-- ================================================================================
-- Purpose: Normalize ALL temporal events across FHIR domains into single queryable view
-- Version: 2.2 (Updated to use v_visits_unified instead of v_encounters)
-- Date: 2025-10-19
--
-- IMPORTANT: This view now works with datetime-standardized source views where:
--   - All VARCHAR datetime columns have been converted to TIMESTAMP(3)
--   - Date columns use DATE type
--   - Consistent typing enables simpler DATE() extraction instead of complex CAST logic
--
-- Coverage:
--   - Diagnoses (v_diagnoses, v_problem_list_diagnoses, v_hydrocephalus_diagnosis)
--   - Procedures (v_procedures, v_procedures_tumor, v_hydrocephalus_procedures)
--   - Imaging (v_imaging)
--   - Medications (v_medications, v_concomitant_medications, v_imaging_corticosteroid_use)
--   - Visits (v_visits_unified) - unified encounters + appointments, no duplication
--   - Measurements (v_measurements) - height, weight, vitals, labs
--   - Molecular Tests (v_molecular_tests)
--   - Radiation (v_radiation_treatment_courses, v_radiation_treatment_appointments)
--   - Assessments (v_ophthalmology_assessments, v_audiology_assessments)
--   - Transplant (v_autologous_stem_cell_transplant, v_autologous_stem_cell_collection)
--
-- PROVENANCE TRACKING:
--   Every event includes:
--   - source_view: Which Athena view it came from (e.g., 'v_imaging', 'v_ophthalmology_assessments')
--   - source_domain: FHIR resource type (e.g., 'DiagnosticReport', 'Observation', 'Procedure')
--   - source_id: FHIR resource ID for traceability
--   - extraction_context: JSON with additional provenance metadata
--
-- USAGE:
--   -- Get all events for a patient
--   SELECT * FROM fhir_prd_db.v_unified_patient_timeline
--   WHERE patient_fhir_id = 'Patient/xyz'
--   ORDER BY event_date;
--
--   -- Get events in date range
--   SELECT * FROM fhir_prd_db.v_unified_patient_timeline
--   WHERE patient_fhir_id = 'Patient/xyz'
--     AND event_date BETWEEN '2018-01-01' AND '2019-12-31'
--   ORDER BY event_date;
--
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_unified_patient_timeline AS

-- ============================================================================
-- 1. DIAGNOSES AS EVENTS
-- Source: v_diagnoses (includes problem_list_diagnoses, hydrocephalus_diagnosis)
-- Provenance: Condition FHIR resource
-- ============================================================================
SELECT
    vd.patient_fhir_id,
    'diag_' || vd.condition_id as event_id,
    DATE(vd.onset_date_time) as event_date,  -- onset_date_time is TIMESTAMP(3) in v_diagnoses
    vd.age_at_onset_days as age_at_event_days,
    CAST(vd.age_at_onset_days AS DOUBLE) / 365.25 as age_at_event_years,

    -- Event classification
    'Diagnosis' as event_type,
    CASE
        WHEN vd.diagnosis_name LIKE '%neoplasm%' OR vd.diagnosis_name LIKE '%tumor%'
             OR vd.diagnosis_name LIKE '%astrocytoma%' OR vd.diagnosis_name LIKE '%glioma%'
             OR vd.diagnosis_name LIKE '%medulloblastoma%' OR vd.diagnosis_name LIKE '%ependymoma%'
        THEN 'Tumor'
        WHEN vd.diagnosis_name LIKE '%chemotherapy%' OR vd.diagnosis_name LIKE '%nausea%'
             OR vd.diagnosis_name LIKE '%vomiting%' OR vd.diagnosis_name LIKE '%induced%'
        THEN 'Treatment Toxicity'
        WHEN vd.diagnosis_name LIKE '%hydrocephalus%' THEN 'Hydrocephalus'
        WHEN vd.diagnosis_name LIKE '%vision%' OR vd.diagnosis_name LIKE '%visual%'
             OR vd.diagnosis_name LIKE '%diplopia%' OR vd.diagnosis_name LIKE '%nystagmus%'
        THEN 'Vision Disorder'
        WHEN vd.diagnosis_name LIKE '%hearing%' OR vd.diagnosis_name LIKE '%ototoxic%'
        THEN 'Hearing Disorder'
        ELSE 'Other Complication'
    END as event_category,
    CASE
        WHEN vd.diagnosis_name LIKE '%progression%' OR vd.snomed_code = 25173007 THEN 'Progression'
        WHEN vd.diagnosis_name LIKE '%recurrence%' OR vd.diagnosis_name LIKE '%recurrent%' THEN 'Recurrence'
        WHEN vd.diagnosis_name LIKE '%astrocytoma%' OR vd.diagnosis_name LIKE '%glioma%'
             OR vd.diagnosis_name LIKE '%medulloblastoma%' THEN 'Initial Diagnosis'
        ELSE NULL
    END as event_subtype,
    vd.diagnosis_name as event_description,
    vd.clinical_status_text as event_status,

    -- Provenance
    'v_diagnoses' as source_view,
    'Condition' as source_domain,
    vd.condition_id as source_id,

    -- Clinical codes
    ARRAY[vd.icd10_code] as icd10_codes,
    ARRAY[CAST(vd.snomed_code AS VARCHAR)] as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    -- Event metadata (domain-specific fields)
    CAST(CAST(MAP(
        ARRAY['icd10_code', 'icd10_display', 'snomed_code', 'snomed_display', 'recorded_date', 'abatement_date_time', 'clinical_status'],
        ARRAY[
            CAST(vd.icd10_code AS VARCHAR),
            CAST(vd.icd10_display AS VARCHAR),
            CAST(vd.snomed_code AS VARCHAR),
            CAST(vd.snomed_display AS VARCHAR),
            CAST(vd.recorded_date AS VARCHAR),
            CAST(vd.abatement_date_time AS VARCHAR),
            CAST(vd.clinical_status_text AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    -- Extraction context (for agent queries)
    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_diagnoses',
            'condition',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            CAST(CASE WHEN vd.icd10_code IS NOT NULL OR vd.snomed_code IS NOT NULL THEN true ELSE false END AS VARCHAR),
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_diagnoses vd

UNION ALL

-- ============================================================================
-- 2. PROCEDURES AS EVENTS
-- Source: v_procedures_tumor (tumor-related procedures only)
-- Provenance: Procedure FHIR resource
-- ============================================================================
SELECT
    vp.patient_fhir_id,
    'proc_' || vp.procedure_fhir_id as event_id,
    CAST(vp.procedure_date AS DATE) as event_date,
    vp.age_at_procedure_days as age_at_event_days,
    CAST(vp.age_at_procedure_days AS DOUBLE) / 365.25 as age_at_event_years,

    'Procedure' as event_type,
    CASE
        WHEN vp.cpt_classification IN ('craniotomy_tumor_resection', 'stereotactic_tumor_procedure', 'neuroendoscopy_tumor', 'open_brain_biopsy', 'skull_base_tumor') THEN 'Tumor Surgery'
        WHEN vp.cpt_classification IN ('tumor_related_csf_management', 'tumor_related_device_implant') THEN 'Supportive Procedure'
        WHEN vp.surgery_type IN ('biopsy', 'stereotactic_procedure') THEN 'Biopsy/Diagnostic'
        WHEN vp.surgery_type IN ('craniotomy', 'craniectomy', 'neuroendoscopy', 'skull_base') THEN 'Tumor Surgery'
        ELSE 'Other Procedure'
    END as event_category,
    COALESCE(vp.cpt_classification, vp.procedure_classification, vp.surgery_type) as event_subtype,
    vp.proc_code_text as event_description,
    vp.proc_status as event_status,

    'v_procedures_tumor' as source_view,
    'Procedure' as source_domain,
    vp.procedure_fhir_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[vp.cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['procedure_type', 'cpt_code', 'cpt_classification', 'surgery_type', 'body_site', 'performed_by', 'procedure_status', 'classification_confidence', 'is_tumor_surgery'],
        ARRAY[
            CAST(vp.proc_code_text AS VARCHAR),
            CAST(vp.cpt_code AS VARCHAR),
            CAST(vp.cpt_classification AS VARCHAR),
            CAST(vp.surgery_type AS VARCHAR),
            CAST(vp.pbs_body_site_text AS VARCHAR),
            CAST(vp.pp_performer_actor_display AS VARCHAR),
            CAST(vp.proc_status AS VARCHAR),
            CAST(vp.classification_confidence AS VARCHAR),
            CAST(vp.is_tumor_surgery AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_procedures_tumor',
            'procedure',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            CAST(CASE WHEN vp.cpt_code IS NOT NULL THEN true ELSE false END AS VARCHAR),
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_procedures_tumor vp
WHERE vp.is_tumor_surgery = true

UNION ALL

-- ============================================================================
-- 3. IMAGING AS EVENTS
-- Source: v_imaging
-- Provenance: DiagnosticReport FHIR resource
-- ============================================================================
SELECT
    vi.patient_fhir_id,
    'img_' || vi.imaging_procedure_id as event_id,
    CAST(vi.imaging_date AS DATE) as event_date,
    vi.age_at_imaging_days as age_at_event_days,
    CAST(vi.age_at_imaging_days AS DOUBLE) / 365.25 as age_at_event_years,

    'Imaging' as event_type,
    'Imaging' as event_category,
    CASE
        WHEN LOWER(vi.report_conclusion) LIKE '%progression%' OR LOWER(vi.report_conclusion) LIKE '%increase%'
        THEN 'Progression Imaging'
        WHEN LOWER(vi.report_conclusion) LIKE '%stable%' THEN 'Stable Imaging'
        WHEN LOWER(vi.report_conclusion) LIKE '%improvement%' OR LOWER(vi.report_conclusion) LIKE '%decrease%'
        THEN 'Response Imaging'
        ELSE 'Surveillance Imaging'
    END as event_subtype,
    vi.imaging_procedure as event_description,
    vi.report_status as event_status,

    'v_imaging' as source_view,
    'DiagnosticReport' as source_domain,
    vi.imaging_procedure_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['modality', 'category', 'report_conclusion', 'report_status', 'report_issued', 'result_display'],
        ARRAY[
            CAST(vi.imaging_modality AS VARCHAR),
            CAST(vi.category_text AS VARCHAR),
            CAST(vi.report_conclusion AS VARCHAR),
            CAST(vi.report_status AS VARCHAR),
            CAST(vi.report_issued AS VARCHAR),
            CAST(vi.result_display AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'free_text_fields'],
        ARRAY[
            'v_imaging',
            'diagnostic_report',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            CAST(CASE WHEN vi.report_conclusion IS NOT NULL THEN true ELSE false END AS VARCHAR),
            'report_conclusion, result_display'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_imaging vi

UNION ALL

-- ============================================================================
-- 4. MEDICATIONS AS EVENTS (Systemic Therapy)
-- Source: v_medications
-- Provenance: MedicationRequest FHIR resource
-- ============================================================================
SELECT
    vm.patient_fhir_id,
    'med_' || vm.medication_request_id as event_id,
    CAST(vm.medication_start_date AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vm.medication_start_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vm.medication_start_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Medication' as event_type,
    CASE
        WHEN LOWER(vm.medication_name) LIKE '%vincristine%' OR LOWER(vm.medication_name) LIKE '%carboplatin%'
             OR LOWER(vm.medication_name) LIKE '%cisplatin%' OR LOWER(vm.medication_name) LIKE '%etoposide%'
             OR LOWER(vm.medication_name) LIKE '%cyclophosphamide%' OR LOWER(vm.medication_name) LIKE '%ifosfamide%'
        THEN 'Chemotherapy'
        WHEN LOWER(vm.medication_name) LIKE '%selumetinib%' OR LOWER(vm.medication_name) LIKE '%dabrafenib%'
             OR LOWER(vm.medication_name) LIKE '%trametinib%' OR LOWER(vm.medication_name) LIKE '%vemurafenib%'
        THEN 'Targeted Therapy'
        WHEN LOWER(vm.medication_name) LIKE '%dexamethasone%' OR LOWER(vm.medication_name) LIKE '%prednisone%'
             OR LOWER(vm.medication_name) LIKE '%methylprednisolone%'
        THEN 'Corticosteroid'
        WHEN LOWER(vm.medication_name) LIKE '%ondansetron%' OR LOWER(vm.medication_name) LIKE '%granisetron%'
             OR LOWER(vm.medication_name) LIKE '%metoclopramide%'
        THEN 'Antiemetic'
        WHEN LOWER(vm.medication_name) LIKE '%filgrastim%' OR LOWER(vm.medication_name) LIKE '%pegfilgrastim%'
        THEN 'Growth Factor'
        ELSE 'Other Medication'
    END as event_category,
    NULL as event_subtype,
    vm.medication_name as event_description,
    vm.mr_status as event_status,

    'v_medications' as source_view,
    'MedicationRequest' as source_domain,
    vm.medication_request_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['medication_name', 'medication_form', 'rx_norm_codes', 'start_date', 'end_date', 'status', 'requester', 'care_plan_id'],
        ARRAY[
            CAST(vm.medication_name AS VARCHAR),
            CAST(vm.medication_form AS VARCHAR),
            CAST(vm.rx_norm_codes AS VARCHAR),
            CAST(vm.medication_start_date AS VARCHAR),
            CAST(vm.mr_validity_period_end AS VARCHAR),
            CAST(vm.mr_status AS VARCHAR),
            CAST(vm.requester_name AS VARCHAR),
            CAST(vm.mrb_care_plan_references AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_medications',
            'medication_request',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            CAST(CASE WHEN vm.rx_norm_codes IS NOT NULL THEN true ELSE false END AS VARCHAR),
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_medications vm
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vm.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- 5. VISITS (ENCOUNTERS + APPOINTMENTS) AS EVENTS
-- Source: v_visits_unified
-- Provenance: Encounter + Appointment FHIR resources (unified)
-- ============================================================================
SELECT
    vv.patient_fhir_id,
    'visit_' || COALESCE(vv.encounter_id, vv.appointment_fhir_id) as event_id,
    vv.visit_date as event_date,
    vv.age_at_visit_days as age_at_event_days,
    CAST(vv.age_at_visit_days AS DOUBLE) / 365.25 as age_at_event_years,

    'Visit' as event_type,
    CASE
        WHEN vv.visit_type = 'completed_scheduled' THEN 'Completed Visit'
        WHEN vv.visit_type = 'completed_no_encounter' THEN 'Appointment Only'
        WHEN vv.visit_type = 'no_show' THEN 'No Show'
        WHEN vv.visit_type = 'cancelled' THEN 'Cancelled Visit'
        WHEN vv.visit_type = 'future_scheduled' THEN 'Scheduled Visit'
        WHEN vv.source = 'encounter_only' THEN 'Unscheduled Encounter'
        ELSE 'Other Visit'
    END as event_category,
    COALESCE(vv.appointment_type_text, vv.encounter_status) as event_subtype,
    COALESCE(
        vv.appointment_description,
        vv.appointment_type_text,
        'Visit on ' || CAST(vv.visit_date AS VARCHAR)
    ) as event_description,
    COALESCE(vv.appointment_status, vv.encounter_status) as event_status,

    'v_visits_unified' as source_view,
    'Encounter+Appointment' as source_domain,
    COALESCE(vv.encounter_id, vv.appointment_fhir_id) as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['visit_type', 'appointment_status', 'appointment_type', 'encounter_status', 'appointment_start', 'appointment_end', 'encounter_start', 'encounter_end', 'appointment_completed', 'encounter_occurred'],
        ARRAY[
            CAST(vv.visit_type AS VARCHAR),
            CAST(vv.appointment_status AS VARCHAR),
            CAST(vv.appointment_type_text AS VARCHAR),
            CAST(vv.encounter_status AS VARCHAR),
            CAST(vv.appointment_start AS VARCHAR),
            CAST(vv.appointment_end AS VARCHAR),
            CAST(vv.encounter_start AS VARCHAR),
            CAST(vv.encounter_end AS VARCHAR),
            CAST(vv.appointment_completed AS VARCHAR),
            CAST(vv.encounter_occurred AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_visits_unified',
            'encounter + appointment',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_visits_unified vv

UNION ALL

-- ============================================================================
-- 6. MOLECULAR TESTS AS EVENTS
-- Source: v_molecular_tests
-- Provenance: Observation (Lab) FHIR resource
-- ============================================================================
SELECT
    vmt.patient_fhir_id,
    'moltest_' || vmt.mt_test_id as event_id,
    CAST(vmt.mt_test_date AS DATE) as event_date,
    vmt.age_at_test_days as age_at_event_days,
    CAST(vmt.age_at_test_days AS DOUBLE) / 365.25 as age_at_event_years,

    'Molecular Test' as event_type,
    'Genomic Testing' as event_category,
    vmt.mt_lab_test_name as event_subtype,
    vmt.mt_lab_test_name as event_description,
    vmt.mt_test_status as event_status,

    'v_molecular_tests' as source_view,
    'Observation' as source_domain,
    vmt.mt_test_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['test_name', 'specimen_types', 'specimen_sites', 'specimen_ids', 'specimen_collection_date', 'component_count', 'narrative_chars', 'requester'],
        ARRAY[
            CAST(vmt.mt_lab_test_name AS VARCHAR),
            CAST(vmt.mt_specimen_types AS VARCHAR),
            CAST(vmt.mt_specimen_sites AS VARCHAR),
            CAST(vmt.mt_specimen_ids AS VARCHAR),
            CAST(vmt.mt_specimen_collection_date AS VARCHAR),
            CAST(vmt.mtr_component_count AS VARCHAR),
            CAST(vmt.mtr_total_narrative_chars AS VARCHAR),
            CAST(vmt.mt_test_requester AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'free_text_fields'],
        ARRAY[
            'v_molecular_tests',
            'lab_tests + lab_test_results',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            CAST(CASE WHEN vmt.mtr_total_narrative_chars > 0 THEN true ELSE false END AS VARCHAR),
            'test_result_narrative'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_molecular_tests vmt

UNION ALL

-- ============================================================================
-- 7A. RADIATION TREATMENT COURSES AS EVENTS
-- Source: v_radiation_summary (aggregated course data)
-- Provenance: CarePlan FHIR resource
-- ============================================================================
SELECT
    vrs.patient_id as patient_fhir_id,
    'rad_course_1_' || vrs.patient_id as event_id,
    CAST(vrs.course_1_start_date AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vrs.course_1_start_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vrs.course_1_start_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Radiation Course' as event_type,
    'Radiation Therapy' as event_category,
    CASE WHEN vrs.re_irradiation = 'Yes' THEN 'Re-irradiation Course 1' ELSE 'Initial Radiation Course 1' END as event_subtype,
    'Radiation therapy course 1' as event_description,
    'completed' as event_status,

    'v_radiation_summary' as source_view,
    'CarePlan' as source_domain,
    vrs.patient_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['course_number', 'start_date', 'end_date', 'duration_weeks', 're_irradiation', 'treatment_techniques', 'num_appointments'],
        ARRAY[
            '1',
            CAST(vrs.course_1_start_date AS VARCHAR),
            CAST(vrs.course_1_end_date AS VARCHAR),
            CAST(vrs.course_1_duration_weeks AS VARCHAR),
            CAST(vrs.re_irradiation AS VARCHAR),
            CAST(vrs.treatment_techniques AS VARCHAR),
            CAST(vrs.num_radiation_appointments AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_radiation_summary',
            'care_plan + radiation tables',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_radiation_summary vrs
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vrs.patient_id = vpd.patient_fhir_id
WHERE vrs.course_1_start_date IS NOT NULL

UNION ALL

-- ============================================================================
-- 7B. RADIATION TREATMENT APPOINTMENTS AS EVENTS (Individual Fractions)
-- Source: v_radiation_treatment_appointments
-- Provenance: Appointment FHIR resource
-- MODERATE PRIORITY - Adds granular daily treatment data
-- ============================================================================
SELECT
    vrta.patient_fhir_id,
    'radfx_' || vrta.appointment_id as event_id,
    DATE(vrta.appointment_start) as event_date,  -- appointment_start is TIMESTAMP(3) after standardization
    DATE_DIFF('day', DATE(vpd.pd_birth_date), DATE(vrta.appointment_start)) as age_at_event_days,
    CAST(DATE_DIFF('day', DATE(vpd.pd_birth_date), DATE(vrta.appointment_start)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Radiation Fraction' as event_type,
    'Radiation Therapy' as event_category,
    'Daily Treatment' as event_subtype,
    'Radiation treatment fraction' as event_description,
    vrta.appointment_status as event_status,

    'v_radiation_treatment_appointments' as source_view,
    'Appointment' as source_domain,
    vrta.appointment_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['appointment_start', 'appointment_end', 'appointment_type', 'appointment_status', 'minutes_duration'],
        ARRAY[
            CAST(vrta.appointment_start AS VARCHAR),
            CAST(vrta.appointment_end AS VARCHAR),
            CAST(vrta.appointment_type_text AS VARCHAR),
            CAST(vrta.appointment_status AS VARCHAR),
            CAST(vrta.minutes_duration AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_radiation_treatment_appointments',
            'appointment',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_radiation_treatment_appointments vrta
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vrta.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- 8. MEASUREMENTS AS EVENTS (Growth, Vitals, Labs)
-- Source: v_measurements
-- Provenance: Observation + LabTests FHIR resources
-- CRITICAL PRIORITY - 1,570 records for patient e4BwD8ZYDBccepXcJ.Ilo3w3
-- ============================================================================
SELECT
    vm.patient_fhir_id,
    COALESCE('obs_' || vm.obs_observation_id, 'lab_' || vm.lt_test_id) as event_id,
    CAST(COALESCE(vm.obs_measurement_date, vm.lt_measurement_date) AS DATE) as event_date,
    vm.age_at_measurement_days as age_at_event_days,
    vm.age_at_measurement_years as age_at_event_years,

    'Measurement' as event_type,
    CASE
        WHEN LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) IN ('height', 'weight', 'bmi', 'body mass index')
        THEN 'Growth'
        WHEN LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%blood pressure%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%heart rate%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%temperature%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%oxygen%'
        THEN 'Vital Signs'
        WHEN LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%cbc%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%blood count%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%hemoglobin%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%platelet%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%wbc%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%neutrophil%'
        THEN 'Hematology Lab'
        WHEN LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%metabolic%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%chemistry%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%electrolyte%'
        THEN 'Chemistry Lab'
        WHEN LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%liver%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%alt%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%ast%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%bilirubin%'
        THEN 'Liver Function'
        WHEN LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%renal%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%creatinine%'
             OR LOWER(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type)) LIKE '%bun%'
        THEN 'Renal Function'
        ELSE 'Other Lab'
    END as event_category,
    COALESCE(vm.obs_measurement_type, vm.lt_measurement_type) as event_subtype,
    COALESCE(vm.obs_measurement_type, vm.lt_measurement_type) as event_description,
    COALESCE(vm.obs_status, vm.lt_status) as event_status,

    'v_measurements' as source_view,
    vm.source_table as source_domain,  -- 'observation' or 'lab_tests'
    COALESCE(vm.obs_observation_id, vm.lt_test_id) as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['measurement_type', 'measurement_value', 'measurement_unit', 'value_range_low', 'value_range_high', 'test_component', 'source_table'],
        ARRAY[
            CAST(COALESCE(vm.obs_measurement_type, vm.lt_measurement_type) AS VARCHAR),
            COALESCE(CAST(vm.obs_measurement_value AS VARCHAR), vm.ltr_value_string),
            CAST(COALESCE(vm.obs_measurement_unit, vm.ltr_measurement_unit) AS VARCHAR),
            CAST(vm.ltr_value_range_low_value AS VARCHAR),
            CAST(vm.ltr_value_range_high_value AS VARCHAR),
            CAST(vm.ltr_test_component AS VARCHAR),
            CAST(vm.source_table AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'measurement_is_quantitative'],
        ARRAY[
            'v_measurements',
            CAST(vm.source_table AS VARCHAR),
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            'false',
            CAST(CASE WHEN vm.obs_measurement_value IS NOT NULL OR vm.ltr_value_range_low_value IS NOT NULL THEN true ELSE false END AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_measurements vm

UNION ALL

-- ============================================================================
-- 9. OPHTHALMOLOGY ASSESSMENTS AS EVENTS
-- Source: v_ophthalmology_assessments
-- Provenance: Observation + Procedure + DocumentReference FHIR resources
-- CRITICAL PRIORITY - Visual acuity, visual fields, OCT, fundus exams
-- ============================================================================
SELECT
    voa.patient_fhir_id,
    'ophtho_' || voa.record_fhir_id as event_id,
    CAST(voa.assessment_date AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(voa.assessment_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(voa.assessment_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Assessment' as event_type,
    'Ophthalmology' as event_category,
    voa.assessment_category as event_subtype,  -- 'visual_acuity', 'visual_field', 'oct_optic_nerve', etc.
    voa.assessment_description as event_description,
    voa.record_status as event_status,

    'v_ophthalmology_assessments' as source_view,
    voa.source_table as source_domain,  -- 'observation', 'procedure', or 'document_reference'
    voa.record_fhir_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[voa.cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['assessment_category', 'numeric_value', 'value_unit', 'text_value', 'component_name', 'component_numeric_value', 'component_unit', 'cpt_code', 'cpt_description', 'laterality', 'file_url', 'file_type'],
        ARRAY[
            CAST(voa.assessment_category AS VARCHAR),
            CAST(voa.numeric_value AS VARCHAR),
            CAST(voa.value_unit AS VARCHAR),
            CAST(voa.text_value AS VARCHAR),
            CAST(voa.component_name AS VARCHAR),
            CAST(voa.component_numeric_value AS VARCHAR),
            CAST(voa.component_unit AS VARCHAR),
            CAST(voa.cpt_code AS VARCHAR),
            CAST(voa.cpt_description AS VARCHAR),
            CASE
                WHEN LOWER(voa.assessment_description) LIKE '%left%' THEN 'left'
                WHEN LOWER(voa.assessment_description) LIKE '%right%' THEN 'right'
                WHEN LOWER(voa.assessment_description) LIKE '%both%' OR LOWER(voa.assessment_description) LIKE '%bilateral%' THEN 'both'
                ELSE 'unspecified'
            END,
            CAST(voa.file_url AS VARCHAR),
            CAST(voa.file_type AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'has_binary_document', 'document_url', 'document_type'],
        ARRAY[
            'v_ophthalmology_assessments',
            CAST(voa.source_table AS VARCHAR),
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            CAST(CASE WHEN voa.cpt_code IS NOT NULL THEN true ELSE false END AS VARCHAR),
            CAST(CASE WHEN voa.file_url IS NOT NULL THEN true ELSE false END AS VARCHAR),
            CAST(CASE WHEN voa.file_url IS NOT NULL THEN true ELSE false END AS VARCHAR),
            CAST(voa.file_url AS VARCHAR),
            CAST(voa.file_type AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_ophthalmology_assessments voa
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON voa.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- 10. AUDIOLOGY ASSESSMENTS AS EVENTS
-- Source: v_audiology_assessments
-- Provenance: Observation + Procedure + Condition FHIR resources
-- CRITICAL PRIORITY - Audiograms, ototoxicity monitoring
-- ============================================================================
SELECT
    vaa.patient_fhir_id,
    'audio_' || vaa.record_fhir_id as event_id,
    CAST(vaa.assessment_date AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vaa.assessment_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vaa.assessment_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Assessment' as event_type,
    'Audiology' as event_category,
    vaa.assessment_category as event_subtype,  -- 'audiogram_threshold', 'ototoxicity_monitoring', etc.
    vaa.assessment_description as event_description,
    vaa.record_status as event_status,

    'v_audiology_assessments' as source_view,
    vaa.source_table as source_domain,  -- 'observation', 'procedure', 'condition', or 'document_reference'
    vaa.record_fhir_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[vaa.cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['assessment_category', 'frequency_hz', 'threshold_db', 'threshold_unit', 'laterality', 'ear_side', 'hearing_loss_type', 'is_ototoxic', 'cpt_code', 'cpt_description', 'file_url', 'file_type'],
        ARRAY[
            CAST(vaa.assessment_category AS VARCHAR),
            CAST(vaa.frequency_hz AS VARCHAR),
            CAST(vaa.threshold_db AS VARCHAR),
            CAST(vaa.threshold_unit AS VARCHAR),
            CAST(vaa.laterality AS VARCHAR),
            CAST(vaa.ear_side AS VARCHAR),
            CAST(vaa.hearing_loss_type AS VARCHAR),
            CAST(vaa.is_ototoxic AS VARCHAR),
            CAST(vaa.cpt_code AS VARCHAR),
            CAST(vaa.cpt_description AS VARCHAR),
            CAST(vaa.file_url AS VARCHAR),
            CAST(vaa.file_type AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'has_binary_document', 'document_url', 'document_type', 'ototoxicity_surveillance'],
        ARRAY[
            'v_audiology_assessments',
            CAST(vaa.source_table AS VARCHAR),
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            CAST(CASE WHEN vaa.cpt_code IS NOT NULL THEN true ELSE false END AS VARCHAR),
            CAST(CASE WHEN vaa.file_url IS NOT NULL THEN true ELSE false END AS VARCHAR),
            CAST(CASE WHEN vaa.file_url IS NOT NULL THEN true ELSE false END AS VARCHAR),
            CAST(vaa.file_url AS VARCHAR),
            CAST(vaa.file_type AS VARCHAR),
            CAST(CASE WHEN vaa.assessment_category = 'ototoxicity_monitoring' THEN true ELSE false END AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_audiology_assessments vaa
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vaa.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- 11. AUTOLOGOUS STEM CELL TRANSPLANT AS EVENTS
-- Source: v_autologous_stem_cell_transplant
-- Provenance: Condition + Procedure FHIR resources
-- HIGH PRIORITY - Major treatment modality
-- ============================================================================
SELECT
    vasct.patient_fhir_id,
    'transplant_' || COALESCE(vasct.proc_id, vasct.cond_id) as event_id,
    CAST(vasct.transplant_datetime AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vasct.transplant_datetime AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vasct.transplant_datetime AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Procedure' as event_type,
    'Stem Cell Transplant' as event_category,
    'Autologous Transplant' as event_subtype,
    COALESCE(vasct.proc_description, 'Autologous stem cell transplant') as event_description,
    COALESCE(vasct.cond_transplant_status, 'completed') as event_status,

    'v_autologous_stem_cell_transplant' as source_view,
    CASE
        WHEN vasct.has_procedure_data THEN 'procedure'
        WHEN vasct.has_condition_data THEN 'condition'
        ELSE 'observation'
    END as source_domain,
    COALESCE(vasct.proc_id, vasct.cond_id) as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CASE WHEN vasct.proc_cpt_code IS NOT NULL THEN ARRAY[vasct.proc_cpt_code] ELSE CAST(NULL AS ARRAY(VARCHAR)) END as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['transplant_datetime', 'transplant_status', 'cpt_code', 'icd10_code', 'cd34_collection_datetime', 'cd34_count', 'cd34_unit', 'confirmed_autologous', 'confidence', 'data_completeness_score'],
        ARRAY[
            CAST(vasct.transplant_datetime AS VARCHAR),
            CAST(vasct.cond_transplant_status AS VARCHAR),
            CAST(vasct.proc_cpt_code AS VARCHAR),
            CAST(vasct.cond_icd10_code AS VARCHAR),
            CAST(vasct.cd34_collection_datetime AS VARCHAR),
            CAST(vasct.cd34_count_value AS VARCHAR),
            CAST(vasct.cd34_unit AS VARCHAR),
            CAST(vasct.confirmed_autologous AS VARCHAR),
            CAST(vasct.overall_confidence AS VARCHAR),
            CAST(vasct.data_completeness_score AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'has_condition_data', 'has_procedure_data', 'has_transplant_date_obs', 'has_cd34_data', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'free_text_fields'],
        ARRAY[
            'v_autologous_stem_cell_transplant',
            CAST(vasct.has_condition_data AS VARCHAR),
            CAST(vasct.has_procedure_data AS VARCHAR),
            CAST(vasct.has_transplant_date_obs AS VARCHAR),
            CAST(vasct.has_cd34_data AS VARCHAR),
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'true',
            'false',
            ''
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_autologous_stem_cell_transplant vasct
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vasct.patient_fhir_id = vpd.patient_fhir_id
WHERE vasct.transplant_datetime IS NOT NULL

UNION ALL

-- ============================================================================
-- 12. AUTOLOGOUS STEM CELL COLLECTION AS EVENTS
-- Source: v_autologous_stem_cell_collection
-- Provenance: Procedure FHIR resource
-- HIGH PRIORITY - Preparatory procedure for transplant
-- ============================================================================
SELECT
    vascc.patient_fhir_id,
    'stemcell_coll_' || vascc.collection_procedure_fhir_id as event_id,
    CAST(vascc.collection_datetime AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vascc.collection_datetime AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vascc.collection_datetime AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Procedure' as event_type,
    'Stem Cell Collection' as event_category,
    COALESCE(vascc.collection_method, 'Apheresis') as event_subtype,
    'Autologous stem cell collection (apheresis)' as event_description,
    vascc.collection_status as event_status,

    'v_autologous_stem_cell_collection' as source_view,
    'Procedure' as source_domain,
    vascc.collection_procedure_fhir_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CASE WHEN vascc.collection_cpt_code IS NOT NULL THEN ARRAY[vascc.collection_cpt_code] ELSE CAST(NULL AS ARRAY(VARCHAR)) END as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['collection_datetime', 'collection_method', 'collection_cpt_code', 'collection_outcome', 'cd34_measurement_datetime', 'cd34_count', 'cd34_unit', 'cd34_adequacy', 'mobilization_agent_name', 'mobilization_start_datetime', 'days_from_mobilization_to_collection', 'data_completeness'],
        ARRAY[
            CAST(vascc.collection_datetime AS VARCHAR),
            CAST(vascc.collection_method AS VARCHAR),
            CAST(vascc.collection_cpt_code AS VARCHAR),
            CAST(vascc.collection_outcome AS VARCHAR),
            CAST(vascc.cd34_measurement_datetime AS VARCHAR),
            CAST(vascc.cd34_count AS VARCHAR),
            CAST(vascc.cd34_unit AS VARCHAR),
            CAST(vascc.cd34_adequacy AS VARCHAR),
            CAST(vascc.mobilization_agent_name AS VARCHAR),
            CAST(vascc.mobilization_start_datetime AS VARCHAR),
            CAST(vascc.days_from_mobilization_to_collection AS VARCHAR),
            CAST(vascc.data_completeness AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction'],
        ARRAY[
            'v_autologous_stem_cell_collection',
            'procedure',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            CAST(CASE WHEN vascc.collection_cpt_code IS NOT NULL THEN true ELSE false END AS VARCHAR),
            'false'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_autologous_stem_cell_collection vascc
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vascc.patient_fhir_id = vpd.patient_fhir_id
WHERE vascc.collection_datetime IS NOT NULL

UNION ALL

-- ============================================================================
-- 13. IMAGING-RELATED CORTICOSTEROID USE AS EVENTS
-- Source: v_imaging_corticosteroid_use
-- Provenance: MedicationRequest FHIR resource (linked to imaging)
-- HIGH PRIORITY - Steroid timing signals tumor edema and affects imaging interpretation
-- ============================================================================
SELECT
    vicu.patient_fhir_id,
    'cortico_img_' || vicu.corticosteroid_medication_fhir_id as event_id,
    CAST(vicu.imaging_date AS DATE) as event_date,
    DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vicu.imaging_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', CAST(vpd.pd_birth_date AS DATE), CAST(vicu.imaging_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,

    'Medication' as event_type,
    'Corticosteroid (Imaging)' as event_category,
    vicu.corticosteroid_name as event_subtype,
    vicu.corticosteroid_name || ' around ' || vicu.imaging_modality || ' imaging' as event_description,
    vicu.medication_status as event_status,

    'v_imaging_corticosteroid_use' as source_view,
    'MedicationRequest' as source_domain,
    vicu.corticosteroid_medication_fhir_id as source_id,

    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,

    CAST(CAST(MAP(
        ARRAY['corticosteroid_name', 'corticosteroid_generic_name', 'rxnorm_cui', 'imaging_date', 'imaging_modality', 'imaging_procedure_id', 'medication_start_datetime', 'medication_stop_datetime', 'days_from_med_start_to_imaging', 'days_from_imaging_to_med_stop', 'temporal_relationship', 'detection_method'],
        ARRAY[
            CAST(vicu.corticosteroid_name AS VARCHAR),
            CAST(vicu.corticosteroid_generic_name AS VARCHAR),
            CAST(vicu.corticosteroid_rxnorm_cui AS VARCHAR),
            CAST(vicu.imaging_date AS VARCHAR),
            CAST(vicu.imaging_modality AS VARCHAR),
            CAST(vicu.imaging_procedure_id AS VARCHAR),
            CAST(vicu.medication_start_datetime AS VARCHAR),
            CAST(vicu.medication_stop_datetime AS VARCHAR),
            CAST(vicu.days_from_med_start_to_imaging AS VARCHAR),
            CAST(vicu.days_from_imaging_to_med_stop AS VARCHAR),
            CAST(vicu.temporal_relationship AS VARCHAR),
            CAST(vicu.detection_method AS VARCHAR)
        ]
    ) AS JSON) AS VARCHAR) as event_metadata,

    CAST(CAST(MAP(
        ARRAY['source_view', 'source_table', 'extraction_timestamp', 'has_structured_code', 'requires_free_text_extraction', 'linked_to_imaging', 'affects_imaging_interpretation'],
        ARRAY[
            'v_imaging_corticosteroid_use',
            'medication_request (linked to diagnostic_report)',
            CAST(CURRENT_TIMESTAMP AS VARCHAR),
            'false',
            'false',
            'true',
            'true'
        ]
    ) AS JSON) AS VARCHAR) as extraction_context

FROM fhir_prd_db.v_imaging_corticosteroid_use vicu
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vicu.patient_fhir_id = vpd.patient_fhir_id
WHERE vicu.on_corticosteroid = true  -- Only include imaging events with actual corticosteroid use

ORDER BY patient_fhir_id, event_date, event_type;


-- ================================================================================
-- VALIDATION QUERIES
-- ================================================================================

-- Test 1: Event type distribution for patient e4BwD8ZYDBccepXcJ.Ilo3w3
/*
SELECT
    event_type,
    event_category,
    COUNT(*) as event_count,
    MIN(event_date) as earliest,
    MAX(event_date) as latest,
    COUNT(DISTINCT source_view) as source_view_count,
    LISTAGG(DISTINCT source_view, '; ') WITHIN GROUP (ORDER BY source_view) as source_views
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type, event_category
ORDER BY event_count DESC;
*/

-- Test 2: Verify all CRITICAL gaps filled
/*
SELECT
    'Measurements' as gap_category,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_type = 'Measurement'

UNION ALL

SELECT
    'Ophthalmology' as gap_category,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_category = 'Ophthalmology'

UNION ALL

SELECT
    'Audiology' as gap_category,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_category = 'Audiology'

UNION ALL

SELECT
    'Transplant' as gap_category,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_category = 'Stem Cell Transplant'

UNION ALL

SELECT
    'Radiation Fractions' as gap_category,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_type = 'Radiation Fraction';
*/

-- Test 3: Provenance tracking verification
/*
SELECT
    source_view,
    source_domain,
    event_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY source_view, source_domain, event_type
ORDER BY source_view, event_type;
*/

-- Test 4: Check for duplicate events
/*
SELECT
    event_id,
    COUNT(*) as duplicate_count,
    MIN(event_date) as event_date,
    MIN(event_type) as event_type,
    MIN(source_view) as source_view
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY event_id
HAVING COUNT(*) > 1;
-- EXPECTED: 0 rows (no duplicates)
*/

-- Test 5: Extraction context verification (for agent queries)
/*
SELECT
    event_type,
    event_category,
    JSON_EXTRACT_SCALAR(extraction_context, '$.source_view') as source_view,
    JSON_EXTRACT_SCALAR(extraction_context, '$.requires_free_text_extraction') as needs_extraction,
    COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type, event_category,
    JSON_EXTRACT_SCALAR(extraction_context, '$.source_view'),
    JSON_EXTRACT_SCALAR(extraction_context, '$.requires_free_text_extraction')
ORDER BY event_type, event_category;
*/
