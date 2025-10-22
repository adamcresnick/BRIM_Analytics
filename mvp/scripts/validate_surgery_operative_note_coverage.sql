-- ============================================================================
-- VALIDATION QUERY: Surgery Event vs Operative Note Coverage
-- ============================================================================
-- Purpose: Assess whether every tumor surgery event has an operative note
-- Date: 2025-10-22
-- ============================================================================

WITH tumor_surgeries AS (
    -- Get all tumor surgery events from v_procedures_tumor
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        procedure_date,
        proc_code_text,
        surgery_type,
        cpt_code
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = true
        AND procedure_date IS NOT NULL
),

operative_notes AS (
    -- Get all operative note documents
    SELECT
        document_reference_id,
        patient_fhir_id,
        dr_date,
        dr_context_period_start,
        dr_type_text,
        dr_category_text,
        content_type
    FROM fhir_prd_db.v_binary_files
    WHERE (
        dr_type_text LIKE 'OP Note%'
        OR dr_type_text = 'Operative Record'
        OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
        OR LOWER(dr_category_text) LIKE '%operative%'
        OR LOWER(dr_category_text) LIKE '%surgery%'
    )
    AND dr_context_period_start IS NOT NULL
),

-- MATCHING STRATEGY 1: Exact date match on context_period_start (PREFERRED)
exact_matches AS (
    SELECT
        s.procedure_fhir_id,
        s.patient_fhir_id,
        s.procedure_date,
        s.surgery_type,
        o.document_reference_id,
        o.dr_type_text,
        o.dr_context_period_start,
        'exact_context_period' as match_type,
        DATE_DIFF('day',
            DATE(o.dr_context_period_start),
            DATE(s.procedure_date)
        ) as days_diff
    FROM tumor_surgeries s
    INNER JOIN operative_notes o
        ON s.patient_fhir_id = o.patient_fhir_id
        AND DATE(o.dr_context_period_start) = DATE(s.procedure_date)
),

-- MATCHING STRATEGY 2: ±3 day window on context_period_start (FALLBACK)
near_matches AS (
    SELECT
        s.procedure_fhir_id,
        s.patient_fhir_id,
        s.procedure_date,
        s.surgery_type,
        o.document_reference_id,
        o.dr_type_text,
        o.dr_context_period_start,
        'near_context_period' as match_type,
        DATE_DIFF('day',
            DATE(o.dr_context_period_start),
            DATE(s.procedure_date)
        ) as days_diff
    FROM tumor_surgeries s
    INNER JOIN operative_notes o
        ON s.patient_fhir_id = o.patient_fhir_id
        AND ABS(DATE_DIFF('day',
            DATE(o.dr_context_period_start),
            DATE(s.procedure_date)
        )) <= 3
    WHERE s.procedure_fhir_id NOT IN (
        SELECT procedure_fhir_id FROM exact_matches
    )
),

-- MATCHING STRATEGY 3: ±7 day window on dr_date (LAST RESORT)
dr_date_matches AS (
    SELECT
        s.procedure_fhir_id,
        s.patient_fhir_id,
        s.procedure_date,
        s.surgery_type,
        o.document_reference_id,
        o.dr_type_text,
        o.dr_date,
        'dr_date_window' as match_type,
        DATE_DIFF('day',
            DATE(o.dr_date),
            DATE(s.procedure_date)
        ) as days_diff
    FROM tumor_surgeries s
    INNER JOIN operative_notes o
        ON s.patient_fhir_id = o.patient_fhir_id
        AND o.dr_date IS NOT NULL
        AND ABS(DATE_DIFF('day',
            DATE(o.dr_date),
            DATE(s.procedure_date)
        )) <= 7
    WHERE s.procedure_fhir_id NOT IN (
        SELECT procedure_fhir_id FROM exact_matches
        UNION
        SELECT procedure_fhir_id FROM near_matches
    )
),

-- Combine all matches
all_matches AS (
    SELECT * FROM exact_matches
    UNION ALL
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        procedure_date,
        surgery_type,
        document_reference_id,
        dr_type_text,
        dr_context_period_start,
        match_type,
        days_diff
    FROM near_matches
    UNION ALL
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        procedure_date,
        surgery_type,
        document_reference_id,
        dr_type_text,
        dr_date as dr_context_period_start,
        match_type,
        days_diff
    FROM dr_date_matches
),

-- Identify surgeries WITHOUT operative notes
unmatched_surgeries AS (
    SELECT
        s.procedure_fhir_id,
        s.patient_fhir_id,
        s.procedure_date,
        s.surgery_type,
        s.proc_code_text,
        s.cpt_code
    FROM tumor_surgeries s
    WHERE s.procedure_fhir_id NOT IN (
        SELECT DISTINCT procedure_fhir_id FROM all_matches
    )
),

-- Count available operative notes for unmatched surgeries (any date)
unmatched_with_note_check AS (
    SELECT
        u.*,
        COUNT(DISTINCT o.document_reference_id) as total_op_notes_for_patient,
        MIN(DATE(o.dr_context_period_start)) as earliest_op_note_date,
        MAX(DATE(o.dr_context_period_start)) as latest_op_note_date
    FROM unmatched_surgeries u
    LEFT JOIN operative_notes o
        ON u.patient_fhir_id = o.patient_fhir_id
    GROUP BY
        u.procedure_fhir_id,
        u.patient_fhir_id,
        u.procedure_date,
        u.surgery_type,
        u.proc_code_text,
        u.cpt_code
)

-- ============================================================================
-- FINAL OUTPUT: Coverage Summary
-- ============================================================================

SELECT
    'COVERAGE SUMMARY' as report_section,
    COUNT(DISTINCT s.procedure_fhir_id) as total_tumor_surgeries,
    COUNT(DISTINCT m.procedure_fhir_id) as surgeries_with_operative_notes,
    COUNT(DISTINCT u.procedure_fhir_id) as surgeries_without_operative_notes,
    ROUND(
        100.0 * COUNT(DISTINCT m.procedure_fhir_id) /
        NULLIF(COUNT(DISTINCT s.procedure_fhir_id), 0),
        2
    ) as coverage_percentage
FROM tumor_surgeries s
LEFT JOIN all_matches m ON s.procedure_fhir_id = m.procedure_fhir_id
LEFT JOIN unmatched_surgeries u ON s.procedure_fhir_id = u.procedure_fhir_id

UNION ALL

-- Match type breakdown
SELECT
    'MATCH TYPE: ' || match_type as report_section,
    COUNT(DISTINCT procedure_fhir_id) as total_tumor_surgeries,
    COUNT(DISTINCT document_reference_id) as surgeries_with_operative_notes,
    0 as surgeries_without_operative_notes,
    0.0 as coverage_percentage
FROM all_matches
GROUP BY match_type

ORDER BY report_section;


-- ============================================================================
-- DETAILED OUTPUT: Matched Surgeries
-- ============================================================================

SELECT
    patient_fhir_id,
    procedure_date,
    surgery_type,
    match_type,
    dr_type_text as operative_note_type,
    days_diff as days_difference,
    dr_context_period_start as note_context_date
FROM all_matches
ORDER BY patient_fhir_id, procedure_date;


-- ============================================================================
-- DETAILED OUTPUT: Unmatched Surgeries (NO OPERATIVE NOTE FOUND)
-- ============================================================================

SELECT
    u.patient_fhir_id,
    u.procedure_date,
    u.surgery_type,
    u.proc_code_text,
    u.cpt_code,
    u.total_op_notes_for_patient,
    u.earliest_op_note_date,
    u.latest_op_note_date,
    CASE
        WHEN u.total_op_notes_for_patient = 0 THEN 'No operative notes for patient'
        WHEN u.procedure_date < u.earliest_op_note_date THEN 'Surgery before earliest note'
        WHEN u.procedure_date > u.latest_op_note_date THEN 'Surgery after latest note'
        ELSE 'Operative notes exist but dates do not match'
    END as gap_reason
FROM unmatched_with_note_check u
ORDER BY u.patient_fhir_id, u.procedure_date;
