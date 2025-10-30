-- ============================================================================
-- ANALYZE NON-OR PROCEDURES IN v_procedures_tumor
-- ============================================================================
-- Find procedures in v_procedures_tumor that are NOT in surgical_procedures
-- to confirm non-OR cases are included
-- ============================================================================

WITH vpt_only_procedures AS (
    SELECT
        vpt.patient_fhir_id,
        vpt.procedure_fhir_id,
        vpt.proc_code_text,
        vpt.cpt_code,
        vpt.proc_status,
        vpt.procedure_date,
        vpt.is_tumor_surgery,
        vpt.surgery_type,
        vpt.proc_category_text,
        vpt.epic_code
    FROM fhir_prd_db.v_procedures_tumor vpt
    LEFT JOIN fhir_prd_db.surgical_procedures sp
        ON vpt.patient_fhir_id = sp.patient_id
        AND vpt.procedure_fhir_id = sp.procedure_id
    WHERE sp.procedure_id IS NULL  -- Not in surgical_procedures
),

category_summary AS (
    SELECT
        proc_category_text,
        COUNT(*) as procedure_count,
        COUNT(DISTINCT patient_fhir_id) as patient_count,
        COUNT(CASE WHEN is_tumor_surgery THEN 1 END) as tumor_surgery_count
    FROM vpt_only_procedures
    WHERE proc_category_text IS NOT NULL
    GROUP BY proc_category_text
    ORDER BY procedure_count DESC
    LIMIT 20
),

status_summary AS (
    SELECT
        proc_status,
        COUNT(*) as procedure_count,
        COUNT(DISTINCT patient_fhir_id) as patient_count
    FROM vpt_only_procedures
    GROUP BY proc_status
    ORDER BY procedure_count DESC
),

tumor_surgery_summary AS (
    SELECT
        is_tumor_surgery,
        COUNT(*) as procedure_count,
        COUNT(DISTINCT patient_fhir_id) as patient_count
    FROM vpt_only_procedures
    GROUP BY is_tumor_surgery
)

SELECT 'CATEGORY_SUMMARY' as analysis_type,
       proc_category_text as metric1,
       CAST(procedure_count AS VARCHAR) as metric2,
       CAST(patient_count AS VARCHAR) as metric3,
       CAST(tumor_surgery_count AS VARCHAR) as metric4
FROM category_summary

UNION ALL

SELECT 'STATUS_SUMMARY' as analysis_type,
       proc_status as metric1,
       CAST(procedure_count AS VARCHAR) as metric2,
       CAST(patient_count AS VARCHAR) as metric3,
       CAST(NULL AS VARCHAR) as metric4
FROM status_summary

UNION ALL

SELECT 'TUMOR_SURGERY_SUMMARY' as analysis_type,
       CAST(is_tumor_surgery AS VARCHAR) as metric1,
       CAST(procedure_count AS VARCHAR) as metric2,
       CAST(patient_count AS VARCHAR) as metric3,
       CAST(NULL AS VARCHAR) as metric4
FROM tumor_surgery_summary

UNION ALL

SELECT 'TOTAL_NON_OR' as analysis_type,
       'total_procedures' as metric1,
       CAST(COUNT(*) AS VARCHAR) as metric2,
       CAST(COUNT(DISTINCT patient_fhir_id) AS VARCHAR) as metric3,
       CAST(NULL AS VARCHAR) as metric4
FROM vpt_only_procedures;
