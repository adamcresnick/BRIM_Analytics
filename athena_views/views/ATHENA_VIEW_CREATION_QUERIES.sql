-- ================================================================================
-- ATHENA VIEW CREATION QUERIES
-- ================================================================================
-- Purpose: Create materialized views for all patients in fhir_prd_db that
--          replicate the output of the config-driven extraction scripts
--
-- Database: fhir_prd_db
-- Date: 2025-10-16
--
-- USAGE: Copy and paste each CREATE VIEW statement into Athena console
--        Run views in the order listed below (some views depend on others)
-- ================================================================================

-- ================================================================================
-- 1. PATIENT DEMOGRAPHICS VIEW
-- ================================================================================
-- Source: extract_patient_demographics.py
-- Output: patient_demographics.csv
-- Description: Core demographics for all patients (NO MRN for PHI protection)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT
    pa.id as patient_fhir_id,
    pa.gender as pd_gender,
    pa.race as pd_race,
    pa.ethnicity as pd_ethnicity,
    pa.birth_date as pd_birth_date,
    DATE_DIFF('year', DATE(pa.birth_date), CURRENT_DATE) as pd_age_years
FROM fhir_prd_db.patient_access pa
WHERE pa.id IS NOT NULL;

-- ================================================================================
-- 2. PROBLEM LIST DIAGNOSES VIEW
-- ================================================================================
-- Source: extract_problem_list_diagnoses.py
-- Output: problem_list_diagnoses.csv
-- Description: All diagnoses from problem_list_diagnoses materialized view
-- Columns use 'pld_' prefix for problem_list_diagnoses
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_problem_list_diagnoses AS
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id as pld_condition_id,
    pld.diagnosis_name as pld_diagnosis_name,
    pld.clinical_status_text as pld_clinical_status,
    pld.onset_date_time as pld_onset_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.onset_date_time, 1, 10) AS DATE))) as age_at_onset_days,
    pld.abatement_date_time as pld_abatement_date,
    pld.recorded_date as pld_recorded_date,
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

-- ================================================================================
-- 3. PROCEDURES VIEW
-- ================================================================================
-- Source: extract_all_procedures_metadata.py
-- Output: procedures.csv
-- Description: All procedures with column prefixing (proc_, pcc_, pcat_, pbs_, pp_, prc_, ppr_)
-- Complex multi-table JOIN with surgical keyword detection
-- ================================================================================

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

    -- Procedure category (pcat_ prefix)
    pcat.category_coding_display as pcat_category_coding_display,

    -- Body site (pbs_ prefix)
    pbs.body_site_text as pbs_body_site_text,

    -- Performer (pp_ prefix)
    pp.performer_actor_display as pp_performer_actor_display,
    pp.performer_function_text as pp_performer_function_text,

    -- Reason code (prc_ prefix)
    prc.reason_code_text as prc_reason_code_text,

    -- Report reference (ppr_ prefix)
    ppr.report_reference as ppr_report_reference,
    ppr.report_display as ppr_report_display

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN fhir_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
LEFT JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id
LEFT JOIN fhir_prd_db.procedure_reason_code prc ON p.id = prc.procedure_id
LEFT JOIN fhir_prd_db.procedure_report pr ON p.id = pr.procedure_id
LEFT JOIN (
    SELECT procedure_id,
           report_reference,
           report_display,
           ROW_NUMBER() OVER (PARTITION BY procedure_id ORDER BY report_reference) as rn
    FROM fhir_prd_db.procedure_report
) ppr ON p.id = ppr.procedure_id AND ppr.rn = 1
LEFT JOIN fhir_prd_db.patient_access pa ON p.subject_reference = pa.id
WHERE p.subject_reference IS NOT NULL
ORDER BY p.subject_reference, pd.procedure_date;

-- ================================================================================
-- 4. MEDICATIONS VIEW
-- ================================================================================
-- Source: extract_all_medications_metadata.py
-- Output: medications.csv
-- Description: Comprehensive medication data joining 9 tables
-- Uses aggregation (LISTAGG) for multi-valued fields
-- Columns use mr_, mrn_, mrr_, mrb_, mf_, mi_, cp_, cpc_, cpcon_, cpa_ prefixes
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_medications AS
WITH medication_notes AS (
    SELECT
        medication_request_id,
        LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_text) as note_text_aggregated
    FROM fhir_prd_db.medication_request_note
    GROUP BY medication_request_id
),
medication_reasons AS (
    SELECT
        medication_request_id,
        LISTAGG(reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
    FROM fhir_prd_db.medication_request_reason_code
    GROUP BY medication_request_id
),
medication_forms AS (
    SELECT
        medication_id,
        LISTAGG(DISTINCT form_coding_code, ' | ') WITHIN GROUP (ORDER BY form_coding_code) as form_coding_codes,
        LISTAGG(DISTINCT form_coding_display, ' | ') WITHIN GROUP (ORDER BY form_coding_display) as form_coding_displays
    FROM fhir_prd_db.medication_form_coding
    GROUP BY medication_id
),
medication_ingredients AS (
    SELECT
        medication_id,
        LISTAGG(DISTINCT CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit, ' | ')
            WITHIN GROUP (ORDER BY CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit) as ingredient_strengths
    FROM fhir_prd_db.medication_ingredient
    WHERE ingredient_strength_numerator_value IS NOT NULL
    GROUP BY medication_id
),
care_plan_categories AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as categories_aggregated
    FROM fhir_prd_db.care_plan_category
    GROUP BY care_plan_id
),
care_plan_conditions AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT addresses_display, ' | ') WITHIN GROUP (ORDER BY addresses_display) as addresses_aggregated
    FROM fhir_prd_db.care_plan_addresses
    GROUP BY care_plan_id
)
SELECT
    -- Patient info
    pm.patient_id as patient_fhir_id,

    -- Patient_medications view fields (no prefix for backward compatibility)
    pm.medication_request_id,
    pm.medication_id,
    pm.medication_name,
    pm.form_text as medication_form,
    pm.rx_norm_codes,
    pm.authored_on as medication_start_date,
    pm.requester_name,
    pm.status as medication_status,
    pm.encounter_display,

    -- Medication_request fields (mr_ prefix) - matched to working Python script
    mr.dispense_request_validity_period_start as mr_validity_period_start,
    mr.dispense_request_validity_period_end as mr_validity_period_end,
    mr.authored_on as mr_authored_on,
    mr.status as mr_status,
    mr.status_reason_text as mr_status_reason_text,
    mr.priority as mr_priority,
    mr.intent as mr_intent,
    mr.do_not_perform as mr_do_not_perform,
    mr.course_of_therapy_type_text as mr_course_of_therapy_type_text,
    mr.dispense_request_initial_fill_duration_value as mr_dispense_initial_fill_duration_value,
    mr.dispense_request_initial_fill_duration_unit as mr_dispense_initial_fill_duration_unit,
    mr.dispense_request_expected_supply_duration_value as mr_dispense_expected_supply_duration_value,
    mr.dispense_request_expected_supply_duration_unit as mr_dispense_expected_supply_duration_unit,
    mr.dispense_request_number_of_repeats_allowed as mr_dispense_number_of_repeats_allowed,
    mr.substitution_allowed_boolean as mr_substitution_allowed_boolean,
    mr.substitution_reason_text as mr_substitution_reason_text,
    mr.prior_prescription_display as mr_prior_prescription_display,

    -- Aggregated notes (mrn_ prefix)
    mrn.note_text_aggregated as mrn_note_text_aggregated,

    -- Aggregated reason codes (mrr_ prefix)
    mrr.reason_code_text_aggregated as mrr_reason_code_text_aggregated,

    -- Based-on references (mrb_ prefix - care plan linkage)
    mrb.based_on_reference as mrb_care_plan_reference,
    mrb.based_on_display as mrb_care_plan_display,

    -- Form coding (mf_ prefix)
    mf.form_coding_codes as mf_form_coding_codes,
    mf.form_coding_displays as mf_form_coding_displays,

    -- Ingredients (mi_ prefix)
    mi.ingredient_strengths as mi_ingredient_strengths,

    -- Care plan info (cp_ prefix) - linked via based_on
    cp.id as cp_id,
    cp.title as cp_title,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.created as cp_created,
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end,
    cp.author_display as cp_author_display,

    -- Care plan categories (cpc_ prefix)
    cpc.categories_aggregated as cpc_categories_aggregated,

    -- Care plan conditions (cpcon_ prefix)
    cpcon.addresses_aggregated as cpcon_addresses_aggregated,

    -- Care plan activity (cpa_ prefix)
    cpa.activity_detail_status as cpa_activity_detail_status

FROM fhir_prd_db.patient_medications pm
LEFT JOIN fhir_prd_db.medication_request mr ON pm.medication_request_id = mr.id
LEFT JOIN medication_notes mrn ON mr.id = mrn.medication_request_id
LEFT JOIN medication_reasons mrr ON mr.id = mrr.medication_request_id
LEFT JOIN fhir_prd_db.medication_request_based_on mrb ON mr.id = mrb.medication_request_id
LEFT JOIN medication_forms mf ON pm.medication_id = mf.medication_id
LEFT JOIN medication_ingredients mi ON pm.medication_id = mi.medication_id
LEFT JOIN fhir_prd_db.care_plan cp ON mrb.based_on_reference = cp.id
LEFT JOIN care_plan_categories cpc ON cp.id = cpc.care_plan_id
LEFT JOIN care_plan_conditions cpcon ON cp.id = cpcon.care_plan_id
LEFT JOIN fhir_prd_db.care_plan_activity cpa ON cp.id = cpa.care_plan_id
WHERE pm.patient_id IS NOT NULL
ORDER BY pm.patient_id, pm.authored_on;

-- ================================================================================
-- 5. IMAGING VIEW
-- ================================================================================
-- Source: extract_all_imaging_metadata.py
-- Output: imaging.csv
-- Description: MRI and other imaging studies with diagnostic reports
-- Columns use imaging_ prefix
-- ================================================================================

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

    -- Age calculations
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(ci.imaging_date, 1, 10) AS DATE))) as age_at_imaging_days,
    TRY(DATE_DIFF('year',
        DATE(pa.birth_date),
        CAST(SUBSTR(ci.imaging_date, 1, 10) AS DATE))) as age_at_imaging_years

FROM combined_imaging ci
LEFT JOIN fhir_prd_db.diagnostic_report dr
    ON ci.result_diagnostic_report_id = dr.id
LEFT JOIN report_categories rc
    ON dr.id = rc.diagnostic_report_id
LEFT JOIN fhir_prd_db.patient_access pa
    ON ci.patient_id = pa.id
WHERE ci.patient_id IS NOT NULL
ORDER BY ci.patient_id, ci.imaging_date DESC;

-- ================================================================================
-- 6. ENCOUNTERS VIEW
-- ================================================================================
-- Source: extract_all_encounters_metadata.py
-- Output: encounters.csv
-- Description: All encounters with types, reasons, and diagnoses
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_encounters AS
WITH encounter_types_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT type_text, ' | ') WITHIN GROUP (ORDER BY type_text) as type_text_aggregated
    FROM fhir_prd_db.encounter_type
    GROUP BY encounter_id
),
encounter_reasons_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
    FROM fhir_prd_db.encounter_reason_code
    GROUP BY encounter_id
),
encounter_diagnoses_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT diagnosis_condition_reference, ' | ') WITHIN GROUP (ORDER BY diagnosis_condition_reference) as diagnosis_references_aggregated
    FROM fhir_prd_db.encounter_diagnosis
    GROUP BY encounter_id
)
SELECT
    e.id as encounter_fhir_id,
    TRY(CAST(SUBSTR(e.period_start, 1, 10) AS DATE)) as encounter_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(e.period_start, 1, 10) AS DATE)))) as age_at_encounter_days,
    e.status,
    e.class_code,
    e.class_display,
    e.service_type_text,
    e.priority_text,
    e.period_start,
    e.period_end,
    e.length_value,
    e.length_unit,
    e.service_provider_display,
    e.part_of_reference,
    e.subject_reference as patient_fhir_id,

    -- Aggregated subtables
    et.type_text_aggregated,
    er.reason_code_text_aggregated,
    ed.diagnosis_references_aggregated

FROM fhir_prd_db.encounter e
LEFT JOIN encounter_types_agg et ON e.id = et.encounter_id
LEFT JOIN encounter_reasons_agg er ON e.id = er.encounter_id
LEFT JOIN encounter_diagnoses_agg ed ON e.id = ed.encounter_id
LEFT JOIN fhir_prd_db.patient_access pa ON e.subject_reference = pa.id
WHERE e.subject_reference IS NOT NULL
ORDER BY e.subject_reference, e.period_start;

-- ================================================================================
-- 7. MEASUREMENTS VIEW
-- ================================================================================
-- Source: extract_all_measurements_metadata.py
-- Output: measurements.csv
-- Description: Lab results and vital signs observations
-- ================================================================================

-- Python script combines observation + lab_tests + lab_test_results
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
-- 8. BINARY FILES (DOCUMENT REFERENCE) VIEW
-- ================================================================================
-- Source: extract_all_binary_files_metadata.py
-- Output: binary_files.csv
-- Description: All document references with metadata (22K+ docs per patient typical)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_binary_files AS
WITH document_contexts AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT context_encounter_reference, ' | ')
            WITHIN GROUP (ORDER BY context_encounter_reference) as encounter_references
    FROM fhir_prd_db.document_reference_context_encounter
    GROUP BY document_reference_id
),
document_categories AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT category_text, ' | ')
            WITHIN GROUP (ORDER BY category_text) as category_text
    FROM fhir_prd_db.document_reference_category
    GROUP BY document_reference_id
)
SELECT
    dr.id as document_reference_id,
    dr.subject_reference as patient_fhir_id,
    dr.status as dr_status,
    dr.doc_status as dr_doc_status,
    dr.type_text as dr_type_text,
    dcat.category_text as dr_category_text,
    dr.date as dr_date,
    dr.description as dr_description,
    dr.context_period_start as dr_context_period_start,
    dr.context_period_end as dr_context_period_end,
    dr.context_facility_type_text as dr_facility_type,
    dr.context_practice_setting_text as dr_practice_setting,
    dc.encounter_references as dr_encounter_references,

    -- Age at document date
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(dr.date, 1, 10) AS DATE)))) as age_at_document_days

FROM fhir_prd_db.document_reference dr
LEFT JOIN document_contexts dc ON dr.id = dc.document_reference_id
LEFT JOIN document_categories dcat ON dr.id = dcat.document_reference_id
LEFT JOIN fhir_prd_db.patient_access pa ON dr.subject_reference = pa.id
WHERE dr.subject_reference IS NOT NULL
ORDER BY dr.subject_reference, dr.date DESC;

-- ================================================================================
-- 9. MOLECULAR TESTS METADATA VIEW
-- ================================================================================
-- Source: extract_all_molecular_tests_metadata.py
-- Output: molecular_tests_metadata.csv
-- Description: Molecular/genetic test results from diagnostic_report
-- Columns use mt_ prefix
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_molecular_tests AS
WITH aggregated_results AS (
    SELECT
        test_id,
        dgd_id,
        COUNT(*) as component_count,
        SUM(LENGTH(COALESCE(test_result_narrative, ''))) as total_narrative_chars,
        LISTAGG(DISTINCT test_component, '; ')
            WITHIN GROUP (ORDER BY test_component) as components_list
    FROM fhir_prd_db.molecular_test_results
    GROUP BY test_id, dgd_id
),
specimen_linkage AS (
    SELECT DISTINCT
        ar.test_id,
        ar.dgd_id,
        sri.service_request_id,
        sr.encounter_reference,
        REPLACE(sr.encounter_reference, 'Encounter/', '') AS encounter_id,
        s.id as specimen_id,
        s.type_text as specimen_type,
        s.collection_collected_date_time as specimen_collection_date,
        s.collection_body_site_text as specimen_body_site,
        s.accession_identifier_value as specimen_accession
    FROM aggregated_results ar
    LEFT JOIN fhir_prd_db.service_request_identifier sri
        ON ar.dgd_id = sri.identifier_value
    LEFT JOIN fhir_prd_db.service_request sr
        ON sri.service_request_id = sr.id
    LEFT JOIN fhir_prd_db.service_request_specimen srs
        ON sr.id = srs.service_request_id
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(srs.specimen_reference, 'Specimen/', '') = s.id
),
procedure_linkage AS (
    SELECT
        sl.test_id,
        MIN(p.id) AS procedure_id,
        MIN(p.code_text) AS procedure_name,
        MIN(p.performed_date_time) AS procedure_date,
        MIN(p.status) AS procedure_status
    FROM specimen_linkage sl
    LEFT JOIN fhir_prd_db.procedure p
        ON sl.encounter_id = REPLACE(p.encounter_reference, 'Encounter/', '')
        AND p.code_text LIKE '%SURGICAL%'
    WHERE sl.encounter_id IS NOT NULL
    GROUP BY sl.test_id
)
SELECT
    mt.patient_id as patient_fhir_id,
    mt.test_id as mt_test_id,
    SUBSTR(mt.result_datetime, 1, 10) as mt_test_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(mt.result_datetime, 1, 10) AS DATE)))) as age_at_test_days,
    mt.lab_test_name as mt_lab_test_name,
    mt.lab_test_status as mt_test_status,
    mt.lab_test_requester as mt_test_requester,
    COALESCE(ar.component_count, 0) as mtr_component_count,
    COALESCE(ar.total_narrative_chars, 0) as mtr_total_narrative_chars,
    COALESCE(ar.components_list, 'None') as mtr_components_list,
    sl.specimen_id as mt_specimen_id,
    sl.specimen_type as mt_specimen_type,
    SUBSTR(sl.specimen_collection_date, 1, 10) as mt_specimen_collection_date,
    sl.specimen_body_site as mt_specimen_body_site,
    sl.specimen_accession as mt_specimen_accession,
    sl.encounter_id as mt_encounter_id,
    pl.procedure_id as mt_procedure_id,
    pl.procedure_name as mt_procedure_name,
    SUBSTR(pl.procedure_date, 1, 10) as mt_procedure_date,
    pl.procedure_status as mt_procedure_status
FROM fhir_prd_db.molecular_tests mt
LEFT JOIN aggregated_results ar ON mt.test_id = ar.test_id
LEFT JOIN specimen_linkage sl ON mt.test_id = sl.test_id
LEFT JOIN procedure_linkage pl ON mt.test_id = pl.test_id
LEFT JOIN fhir_prd_db.patient_access pa ON mt.patient_id = pa.id
WHERE mt.patient_id IS NOT NULL
ORDER BY mt.result_datetime, mt.test_id;

-- ================================================================================
-- 10. RADIATION TREATMENT APPOINTMENTS VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 1 of 7)
-- Output: radiation_treatment_appointments.csv
-- Description: Radiation oncology appointments
-- NOTE: Athena views don't support complex WHERE clauses with multiple LIKE/OR.
--       Filter for radiation terms when querying this view.
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_appointments AS
SELECT DISTINCT
    ap.participant_actor_reference as patient_fhir_id,
    a.id as appointment_id,
    a.status as appointment_status,
    a.appointment_type_text,
    a.priority,
    a.description,
    a.start as appointment_start,
    a."end" as appointment_end,
    a.minutes_duration,
    a.created,
    a.comment as appointment_comment,
    a.patient_instruction
FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference LIKE 'Patient/%'
ORDER BY a.start;

-- ================================================================================
-- 11. RADIATION TREATMENT COURSES VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 2 of 7)
-- Output: radiation_treatment_courses.csv
-- Description: Radiation therapy courses from service_request
-- Columns use sr_ prefix
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_courses AS
SELECT
    sr.subject_reference as patient_fhir_id,
    sr.id as course_id,
    sr.status as sr_status,
    sr.intent as sr_intent,
    sr.code_text as sr_code_text,
    sr.quantity_quantity_value as sr_quantity_value,
    sr.quantity_quantity_unit as sr_quantity_unit,
    sr.occurrence_date_time as sr_occurrence_date_time,
    sr.occurrence_period_start as sr_occurrence_period_start,
    sr.occurrence_period_end as sr_occurrence_period_end,
    sr.authored_on as sr_authored_on,
    sr.requester_display as sr_requester_display,
    sr.performer_type_text as sr_performer_type_text,
    sr.patient_instruction as sr_patient_instruction
FROM fhir_prd_db.service_request sr
WHERE sr.subject_reference IS NOT NULL
  AND (LOWER(sr.code_text) LIKE '%radiation%'
       OR LOWER(sr.patient_instruction) LIKE '%radiation%')
ORDER BY sr.subject_reference, sr.occurrence_period_start;

-- ================================================================================
-- 12. RADIATION CARE PLAN NOTES VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 3 of 7)
-- Output: radiation_care_plan_notes.csv
-- Description: Care plan narrative notes for radiation therapy
-- Columns use cp_, cpn_ prefixes
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_care_plan_notes AS
SELECT
    cp.subject_reference as patient_fhir_id,
    cpn.care_plan_id,
    cpn.note_text as cpn_note_text,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.title as cp_title,
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end
FROM fhir_prd_db.care_plan_note cpn
INNER JOIN fhir_prd_db.care_plan cp ON cpn.care_plan_id = cp.id
WHERE cp.subject_reference IS NOT NULL
  AND LOWER(cpn.note_text) LIKE '%radiation%'
ORDER BY cp.period_start;

-- ================================================================================
-- 13. RADIATION CARE PLAN HIERARCHY VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 4 of 7)
-- Output: radiation_care_plan_hierarchy.csv
-- Description: Care plan activity/output linkages for radiation
-- Columns use cp_, cppo_ prefixes
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_care_plan_hierarchy AS
SELECT
    cp.subject_reference as patient_fhir_id,
    cppo.care_plan_id,
    cppo.part_of_reference as cppo_part_of_reference,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.title as cp_title,
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end
FROM fhir_prd_db.care_plan_part_of cppo
INNER JOIN fhir_prd_db.care_plan cp ON cppo.care_plan_id = cp.id
WHERE cp.subject_reference IS NOT NULL
  AND (LOWER(cp.title) LIKE '%radiation%'
       OR LOWER(cppo.part_of_reference) LIKE '%radiation%')
ORDER BY cp.period_start;

-- ================================================================================
-- 14. RADIATION SERVICE REQUEST NOTES VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 5 of 7)
-- Output: radiation_service_request_notes.csv
-- Description: Service request narrative notes for radiation orders
-- Columns use sr_, srn_ prefixes
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_service_request_notes AS
SELECT
    sr.subject_reference as patient_fhir_id,
    sr.id as service_request_id,
    sr.intent as sr_intent,
    sr.status as sr_status,
    sr.authored_on as sr_authored_on,
    sr.occurrence_date_time as sr_occurrence_date_time,
    sr.occurrence_period_start as sr_occurrence_period_start,
    sr.occurrence_period_end as sr_occurrence_period_end,
    srn.note_text as srn_note_text,
    srn.note_time as srn_note_time
FROM fhir_prd_db.service_request_note srn
INNER JOIN fhir_prd_db.service_request sr ON srn.service_request_id = sr.id
WHERE sr.subject_reference IS NOT NULL
  AND LOWER(srn.note_text) LIKE '%radiation%'
ORDER BY COALESCE(srn.note_time, sr.occurrence_date_time, sr.occurrence_period_start, sr.authored_on);

-- ================================================================================
-- 15. RADIATION SERVICE REQUEST RT HISTORY VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 6 of 7)
-- Output: radiation_service_request_rt_history.csv
-- Description: Service request reason codes for RT treatment history
-- Columns use sr_, srrc_ prefixes
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_service_request_rt_history AS
SELECT
    sr.subject_reference as patient_fhir_id,
    sr.id as sr_id,
    sr.status as sr_status,
    sr.code_text as sr_code_text,
    sr.authored_on as sr_authored_on,
    srrc.reason_code_coding as srrc_reason_code_coding,
    srrc.reason_code_text as srrc_reason_code_text
FROM fhir_prd_db.service_request sr
INNER JOIN fhir_prd_db.service_request_reason_code srrc ON sr.id = srrc.service_request_id
WHERE sr.subject_reference IS NOT NULL
  AND (LOWER(sr.code_text) LIKE '%radiation%'
       OR LOWER(srrc.reason_code_text) LIKE '%radiation%')
ORDER BY sr.subject_reference, sr.authored_on;

-- ================================================================================
-- END OF VIEW DEFINITIONS
-- ================================================================================

-- VERIFICATION QUERIES (Run these to test views)
-- ================================================================================

-- Test 1: Count patients in each view
SELECT 'v_patient_demographics' as view_name, COUNT(DISTINCT patient_fhir_id) as patient_count FROM fhir_prd_db.v_patient_demographics
UNION ALL
SELECT 'v_problem_list_diagnoses', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_problem_list_diagnoses
UNION ALL
SELECT 'v_procedures', COUNT(DISTINCT proc_subject_reference) FROM fhir_prd_db.v_procedures
UNION ALL
SELECT 'v_medications', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_medications
UNION ALL
SELECT 'v_imaging', COUNT(DISTINCT patient_id) FROM fhir_prd_db.v_imaging
UNION ALL
SELECT 'v_encounters', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_encounters
UNION ALL
SELECT 'v_measurements', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_measurements
UNION ALL
SELECT 'v_binary_files', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_binary_files
UNION ALL
SELECT 'v_molecular_tests', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_molecular_tests;

-- Test 2: Sample single patient data (replace with actual patient ID)
SELECT * FROM fhir_prd_db.v_patient_demographics WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT * FROM fhir_prd_db.v_procedures WHERE proc_subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3' LIMIT 10;
SELECT * FROM fhir_prd_db.v_imaging WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3' LIMIT 10;

-- Test 3: Row count per view (for single patient)
SELECT COUNT(*) as demographics_rows FROM fhir_prd_db.v_patient_demographics WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as diagnosis_rows FROM fhir_prd_db.v_problem_list_diagnoses WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as procedure_rows FROM fhir_prd_db.v_procedures WHERE proc_subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as medication_rows FROM fhir_prd_db.v_medications WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as imaging_rows FROM fhir_prd_db.v_imaging WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as encounter_rows FROM fhir_prd_db.v_encounters WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as measurement_rows FROM fhir_prd_db.v_measurements WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as binary_file_rows FROM fhir_prd_db.v_binary_files WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
