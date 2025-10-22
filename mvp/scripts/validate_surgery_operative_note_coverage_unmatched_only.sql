-- ============================================================================
-- VALIDATION QUERY: Identify Unmatched Surgeries (29 cases)
-- ============================================================================
-- Purpose: Investigate the 29 tumor surgeries without matching operative notes
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
    SELECT procedure_fhir_id FROM exact_matches
    UNION
    SELECT procedure_fhir_id FROM near_matches
    UNION
    SELECT procedure_fhir_id FROM dr_date_matches
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
-- Also get date range info
unmatched_with_note_check AS (
    SELECT
        u.procedure_fhir_id,
        u.patient_fhir_id,
        u.procedure_date,
        u.surgery_type,
        u.proc_code_text,
        u.cpt_code,
        COUNT(DISTINCT o.document_reference_id) as total_op_notes_for_patient,
        MIN(DATE(o.dr_context_period_start)) as earliest_op_note_date,
        MAX(DATE(o.dr_context_period_start)) as latest_op_note_date,
        MIN(ABS(DATE_DIFF('day', DATE(o.dr_context_period_start), DATE(u.procedure_date)))) as min_days_to_closest_note
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
-- OUTPUT: Detailed analysis of 29 unmatched surgeries
-- ============================================================================

SELECT
    u.patient_fhir_id,
    u.procedure_fhir_id,
    u.procedure_date,
    u.surgery_type,
    u.proc_code_text,
    u.cpt_code,
    u.total_op_notes_for_patient,
    u.earliest_op_note_date,
    u.latest_op_note_date,
    u.min_days_to_closest_note,
    CASE
        WHEN u.total_op_notes_for_patient = 0 THEN 'No operative notes exist for patient'
        WHEN u.procedure_date < u.earliest_op_note_date THEN
            'Surgery before earliest note (by ' ||
            CAST(DATE_DIFF('day', DATE(u.procedure_date), u.earliest_op_note_date) AS VARCHAR) ||
            ' days)'
        WHEN u.procedure_date > u.latest_op_note_date THEN
            'Surgery after latest note (by ' ||
            CAST(DATE_DIFF('day', u.latest_op_note_date, DATE(u.procedure_date)) AS VARCHAR) ||
            ' days)'
        ELSE
            'Notes exist but no match within ±7 days (closest: ' ||
            CAST(u.min_days_to_closest_note AS VARCHAR) ||
            ' days away)'
    END as gap_reason
FROM unmatched_with_note_check u
ORDER BY
    CASE
        WHEN u.total_op_notes_for_patient = 0 THEN 1
        WHEN u.procedure_date < u.earliest_op_note_date THEN 2
        WHEN u.procedure_date > u.latest_op_note_date THEN 3
        ELSE 4
    END,
    u.patient_fhir_id,
    u.procedure_date;
