-- ============================================================================
-- VIEW: v_procedures_tumor (ENHANCED VERSION)
-- ============================================================================
-- Purpose: Add annotation columns to help filter and categorize procedures
-- New Columns Added:
--   1. epic_or_log_id - Direct Epic OR Log case ID from procedure_identifier
--   2. in_surgical_procedures_table - Boolean flag if procedure exists in surgical_procedures table
--   3. proc_category_annotation - Categorization of proc_category_text
--   4. procedure_source_type - HIGH LEVEL: OR_CASE, SURGICAL_HISTORY, PROCEDURE_ORDER, OTHER
--   5. is_likely_performed - Boolean based on status and category (excludes orders/history)
-- ============================================================================
-- Based on: DATETIME_STANDARDIZED_VIEWS.sql lines 2569-3032
-- Enhancement Date: 2025-10-29
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_procedures_tumor AS
WITH
-- [EXISTING CTEs from DATETIME_STANDARDIZED_VIEWS.sql]
-- NOTE: Include all the existing CTEs here (cpt_classifications, epic_classifications, etc.)
-- For brevity, showing only the modification to the final SELECT

-- ============================================================================
-- NEW CTE: Epic OR Log Identifier
-- ============================================================================
epic_or_identifiers AS (
    SELECT
        procedure_id,
        identifier_value as epic_or_log_id
    FROM fhir_prd_db.procedure_identifier
    WHERE identifier_type_text = 'ORL'
),

-- ============================================================================
-- NEW CTE: Surgical Procedures Table Linkage
-- ============================================================================
surgical_procedures_link AS (
    SELECT DISTINCT
        procedure_id,
        epic_case_orlog_id,
        mrn,
        TRUE as in_surgical_procedures_table
    FROM fhir_prd_db.surgical_procedures
),

-- ... [All existing CTEs from original view] ...

-- ============================================================================
-- FINAL SELECT WITH NEW ANNOTATION COLUMNS
-- ============================================================================
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_fhir_id,

    p.status as proc_status,
    TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) as proc_performed_date_time,
    TRY(CAST(p.performed_period_start AS TIMESTAMP(3))) as proc_performed_period_start,
    TRY(CAST(p.performed_period_end AS TIMESTAMP(3))) as proc_performed_period_end,
    TRY(CAST(p.performed_string AS TIMESTAMP(3))) as proc_performed_string,
    TRY(CAST(p.performed_age_value AS TIMESTAMP(3))) as proc_performed_age_value,
    TRY(CAST(p.performed_age_unit AS TIMESTAMP(3))) as proc_performed_age_unit,
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

    pd.procedure_date,

    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        pd.procedure_date)) as age_at_procedure_days,

    pc.code_coding_system as pcc_code_coding_system,
    pc.code_coding_code as pcc_code_coding_code,
    pc.code_coding_display as pcc_code_coding_display,
    pc.is_surgical_keyword,

    cc.procedure_classification,
    cc.cpt_classification,
    cc.cpt_code,
    cc.cpt_type,
    cc.epic_category,
    cc.epic_code,
    cc.keyword_classification,
    cc.is_tumor_surgery,
    cc.is_excluded_procedure,
    cc.surgery_type,
    cc.classification_confidence,

    cc.has_tumor_reason,
    cc.has_exclude_reason,
    cc.has_tumor_body_site,
    cc.has_exclude_body_site,
    cc.validation_reason_code,
    cc.validation_body_site,

    pcat.category_coding_display as pcat_category_coding_display,
    pbs.body_site_text as pbs_body_site_text,
    pp.performer_actor_display as pp_performer_actor_display,
    pp.performer_function_text as pp_performer_function_text,

    -- ========================================================================
    -- NEW ANNOTATION COLUMNS
    -- ========================================================================

    -- Epic OR Log ID from procedure_identifier table
    epi.epic_or_log_id,

    -- Flag if procedure exists in surgical_procedures table
    COALESCE(spl.in_surgical_procedures_table, FALSE) as in_surgical_procedures_table,

    -- MRN and Epic case ID from surgical_procedures (if linked)
    spl.mrn as surgical_procedures_mrn,
    spl.epic_case_orlog_id as surgical_procedures_epic_case_id,

    -- Categorize proc_category_text for easier filtering
    CASE
        WHEN p.category_text = 'Ordered Procedures' THEN 'PROCEDURE_ORDER'
        WHEN p.category_text = 'Surgical History' THEN 'SURGICAL_HISTORY'
        WHEN p.category_text = 'Surgical Procedures' THEN 'SURGICAL_PROCEDURE'
        WHEN p.category_text IS NULL THEN 'UNCATEGORIZED'
        ELSE 'OTHER_CATEGORY'
    END as proc_category_annotation,

    -- High-level source type classification
    CASE
        WHEN epi.epic_or_log_id IS NOT NULL THEN 'OR_CASE'
        WHEN spl.in_surgical_procedures_table THEN 'OR_CASE'
        WHEN p.category_text = 'Surgical History' THEN 'SURGICAL_HISTORY'
        WHEN p.category_text = 'Ordered Procedures' THEN 'PROCEDURE_ORDER'
        WHEN p.category_text = 'Surgical Procedures' AND p.status = 'completed' THEN 'COMPLETED_SURGICAL'
        WHEN p.status = 'not-done' THEN 'NOT_DONE'
        ELSE 'OTHER'
    END as procedure_source_type,

    -- Flag for likely performed procedures (excludes orders, history, not-done)
    CASE
        WHEN p.category_text IN ('Ordered Procedures') THEN FALSE
        WHEN p.status = 'not-done' THEN FALSE
        WHEN p.status = 'entered-in-error' THEN FALSE
        WHEN p.status = 'completed' THEN TRUE
        WHEN epi.epic_or_log_id IS NOT NULL THEN TRUE
        WHEN spl.in_surgical_procedures_table THEN TRUE
        ELSE FALSE
    END as is_likely_performed,

    -- Annotation for status
    CASE
        WHEN p.status = 'completed' THEN 'COMPLETED'
        WHEN p.status = 'not-done' THEN 'NOT_DONE'
        WHEN p.status = 'entered-in-error' THEN 'ERROR'
        WHEN p.status = 'in-progress' THEN 'IN_PROGRESS'
        WHEN p.status = 'on-hold' THEN 'ON_HOLD'
        WHEN p.status = 'stopped' THEN 'STOPPED'
        WHEN p.status = 'unknown' THEN 'UNKNOWN'
        ELSE 'OTHER_STATUS'
    END as proc_status_annotation,

    -- Data quality flag: Has minimum required data for analysis
    CASE
        WHEN pd.procedure_date IS NOT NULL
            AND p.status = 'completed'
            AND pc.code_coding_code IS NOT NULL
        THEN TRUE
        ELSE FALSE
    END as has_minimum_data_quality

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN fhir_prd_db.patient pa ON p.subject_reference = CONCAT('Patient/', pa.id)
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN combined_classification cc ON p.id = cc.procedure_id
LEFT JOIN fhir_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
LEFT JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id

-- NEW JOINS
LEFT JOIN epic_or_identifiers epi ON p.id = epi.procedure_id
LEFT JOIN surgical_procedures_link spl ON p.id = spl.procedure_id

ORDER BY p.subject_reference, pd.procedure_date;
