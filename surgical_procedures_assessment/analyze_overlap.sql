-- ============================================================================
-- PATIENT AND CPT CODE OVERLAP ANALYSIS
-- ============================================================================

WITH patient_overlap AS (
    SELECT
        COUNT(DISTINCT vpt.patient_fhir_id) as vpt_only_patients,
        COUNT(DISTINCT sp.patient_id) as sp_only_patients,
        COUNT(DISTINCT CASE
            WHEN sp.patient_id IS NOT NULL THEN vpt.patient_fhir_id
        END) as overlap_patients
    FROM fhir_prd_db.v_procedures_tumor vpt
    FULL OUTER JOIN fhir_prd_db.surgical_procedures sp
        ON vpt.patient_fhir_id = sp.patient_id
),

cpt_overlap AS (
    SELECT
        COUNT(DISTINCT vpt.cpt_code) as vpt_unique_cpt,
        COUNT(DISTINCT sp.cpt_code) as sp_unique_cpt,
        COUNT(DISTINCT CASE
            WHEN sp.cpt_code IS NOT NULL AND vpt.cpt_code IS NOT NULL
            THEN vpt.cpt_code
        END) as overlap_cpt_codes
    FROM (SELECT DISTINCT cpt_code FROM fhir_prd_db.v_procedures_tumor WHERE cpt_code IS NOT NULL) vpt
    FULL OUTER JOIN (SELECT DISTINCT cpt_code FROM fhir_prd_db.surgical_procedures WHERE cpt_code IS NOT NULL) sp
        ON vpt.cpt_code = sp.cpt_code
),

top_cpt_vpt AS (
    SELECT
        cpt_code,
        proc_code_text,
        COUNT(*) as procedure_count,
        COUNT(DISTINCT patient_fhir_id) as patient_count
    FROM fhir_prd_db.v_procedures_tumor
    WHERE cpt_code IS NOT NULL
      AND is_tumor_surgery = true
    GROUP BY cpt_code, proc_code_text
    ORDER BY procedure_count DESC
    LIMIT 10
),

top_cpt_sp AS (
    SELECT
        cpt_code,
        procedure_display,
        COUNT(*) as procedure_count,
        COUNT(DISTINCT patient_id) as patient_count
    FROM fhir_prd_db.surgical_procedures
    WHERE cpt_code IS NOT NULL
    GROUP BY cpt_code, procedure_display
    ORDER BY procedure_count DESC
    LIMIT 10
)

SELECT
    'PATIENT_OVERLAP' as analysis_type,
    CAST(po.vpt_only_patients AS VARCHAR) as metric1,
    CAST(po.sp_only_patients AS VARCHAR) as metric2,
    CAST(po.overlap_patients AS VARCHAR) as metric3,
    CAST(NULL AS VARCHAR) as metric4,
    CAST(NULL AS VARCHAR) as metric5
FROM patient_overlap po

UNION ALL

SELECT
    'CPT_OVERLAP' as analysis_type,
    CAST(co.vpt_unique_cpt AS VARCHAR) as metric1,
    CAST(co.sp_unique_cpt AS VARCHAR) as metric2,
    CAST(co.overlap_cpt_codes AS VARCHAR) as metric3,
    CAST(NULL AS VARCHAR) as metric4,
    CAST(NULL AS VARCHAR) as metric5
FROM cpt_overlap co

UNION ALL

SELECT
    'TOP_CPT_VPT' as analysis_type,
    vpt.cpt_code as metric1,
    vpt.proc_code_text as metric2,
    CAST(vpt.procedure_count AS VARCHAR) as metric3,
    CAST(vpt.patient_count AS VARCHAR) as metric4,
    CAST(NULL AS VARCHAR) as metric5
FROM top_cpt_vpt vpt

UNION ALL

SELECT
    'TOP_CPT_SP' as analysis_type,
    sp.cpt_code as metric1,
    sp.procedure_display as metric2,
    CAST(sp.procedure_count AS VARCHAR) as metric3,
    CAST(sp.patient_count AS VARCHAR) as metric4,
    CAST(NULL AS VARCHAR) as metric5
FROM top_cpt_sp sp;
