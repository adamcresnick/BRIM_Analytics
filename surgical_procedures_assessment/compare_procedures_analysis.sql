-- ============================================================================
-- COMPREHENSIVE PROCEDURE COMPARISON ANALYSIS
-- ============================================================================
-- Compare v_procedures_tumor (view) vs surgical_procedures (new table)
-- ============================================================================

WITH v_procedures_tumor_summary AS (
    SELECT
        -- Row counts
        COUNT(*) as total_procedures,
        COUNT(DISTINCT patient_fhir_id) as total_patients,

        -- Surgical classification from v_procedures_tumor
        COUNT(CASE WHEN is_tumor_surgery THEN 1 END) as tumor_surgeries,
        COUNT(CASE WHEN is_surgical_keyword THEN 1 END) as surgical_keyword_matches,
        COUNT(CASE WHEN is_excluded_procedure THEN 1 END) as excluded_procedures,

        -- Surgery types
        COUNT(CASE WHEN surgery_type = 'Resection' THEN 1 END) as resections,
        COUNT(CASE WHEN surgery_type = 'Biopsy' THEN 1 END) as biopsies,
        COUNT(CASE WHEN surgery_type = 'Shunt' THEN 1 END) as shunts,
        COUNT(CASE WHEN surgery_type = 'Other Tumor Surgery' THEN 1 END) as other_tumor_surgery,

        -- Classification methods
        COUNT(CASE WHEN procedure_classification = 'Surgical' THEN 1 END) as classified_surgical,
        COUNT(CASE WHEN cpt_classification = 'Surgical' THEN 1 END) as cpt_surgical,

        -- Date availability
        COUNT(proc_performed_date_time) as has_datetime,
        COUNT(proc_performed_period_start) as has_period_start,
        COUNT(procedure_date) as has_procedure_date,

        -- CPT codes
        COUNT(DISTINCT cpt_code) as unique_cpt_codes,
        COUNT(cpt_code) as procedures_with_cpt,

        -- Epic data
        COUNT(DISTINCT epic_code) as unique_epic_codes,
        COUNT(epic_code) as procedures_with_epic

    FROM fhir_prd_db.v_procedures_tumor
),

surgical_procedures_summary AS (
    SELECT
        -- Row counts
        COUNT(*) as total_procedures,
        COUNT(DISTINCT patient_id) as total_patients,

        -- Status distribution
        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_procedures,
        COUNT(CASE WHEN status = 'preparation' THEN 1 END) as preparation_procedures,
        COUNT(CASE WHEN status = 'in-progress' THEN 1 END) as inprogress_procedures,

        -- Date availability
        COUNT(performed_period_start) as has_period_start,
        COUNT(performed_period_end) as has_period_end,

        -- CPT codes
        COUNT(DISTINCT cpt_code) as unique_cpt_codes,
        COUNT(cpt_code) as procedures_with_cpt,

        -- Epic case IDs
        COUNT(DISTINCT epic_case_orlog_id) as unique_epic_cases,
        COUNT(epic_case_orlog_id) as procedures_with_epic_case,

        -- MRN availability
        COUNT(DISTINCT mrn) as unique_mrns,

        -- Performer data
        COUNT(performer) as has_performer

    FROM fhir_prd_db.surgical_procedures
)

SELECT
    'v_procedures_tumor' as source,
    vpt.total_procedures,
    vpt.total_patients,
    vpt.tumor_surgeries,
    vpt.surgical_keyword_matches,
    vpt.excluded_procedures,
    vpt.resections,
    vpt.biopsies,
    vpt.shunts,
    vpt.other_tumor_surgery,
    vpt.classified_surgical,
    vpt.cpt_surgical,
    vpt.has_datetime,
    vpt.has_period_start,
    vpt.has_procedure_date,
    vpt.unique_cpt_codes,
    vpt.procedures_with_cpt,
    vpt.unique_epic_codes,
    vpt.procedures_with_epic,
    CAST(NULL AS BIGINT) as completed_procedures,
    CAST(NULL AS BIGINT) as unique_epic_cases,
    CAST(NULL AS BIGINT) as unique_mrns,
    CAST(NULL AS BIGINT) as has_performer
FROM v_procedures_tumor_summary vpt

UNION ALL

SELECT
    'surgical_procedures' as source,
    sp.total_procedures,
    sp.total_patients,
    CAST(NULL AS BIGINT) as tumor_surgeries,
    CAST(NULL AS BIGINT) as surgical_keyword_matches,
    CAST(NULL AS BIGINT) as excluded_procedures,
    CAST(NULL AS BIGINT) as resections,
    CAST(NULL AS BIGINT) as biopsies,
    CAST(NULL AS BIGINT) as shunts,
    CAST(NULL AS BIGINT) as other_tumor_surgery,
    CAST(NULL AS BIGINT) as classified_surgical,
    CAST(NULL AS BIGINT) as cpt_surgical,
    CAST(NULL AS BIGINT) as has_datetime,
    sp.has_period_start,
    CAST(NULL AS BIGINT) as has_procedure_date,
    sp.unique_cpt_codes,
    sp.procedures_with_cpt,
    CAST(NULL AS BIGINT) as unique_epic_codes,
    CAST(NULL AS BIGINT) as procedures_with_epic,
    sp.completed_procedures,
    sp.unique_epic_cases,
    sp.unique_mrns,
    sp.has_performer
FROM surgical_procedures_summary sp;
