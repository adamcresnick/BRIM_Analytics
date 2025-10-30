-- ============================================================================
-- ANALYSIS: Brain Tumor Surgeries in v_procedures_tumor NOT in surgical_procedures
-- ============================================================================
-- PURPOSE: Identify tumor surgeries that v_procedures_tumor found but are
--          missing from surgical_procedures table, to help augment the
--          surgical_procedures extraction logic
--
-- BACKGROUND:
--   v_procedures_tumor: 4,169 tumor surgeries (comprehensive FHIR-based)
--   surgical_procedures: 3,204 tumor surgeries (Epic OR log filtered)
--   GAP: ~965 potential tumor surgeries missing from surgical_procedures
--
-- USE CASE:
--   Analyst can review these "missed" cases to determine if they should be
--   included in surgical_procedures and update the extraction logic accordingly
-- ============================================================================

WITH
-- Get all tumor surgeries from v_procedures_tumor
tumor_surgeries_procedures AS (
    SELECT
        patient_fhir_id,
        procedure_fhir_id,
        procedure_date,
        proc_code_text,
        proc_category_text,
        proc_status,

        -- Coding system info
        pcc_coding_system_code,
        pcc_coding_system_name,
        pcc_code_coding_code as code,
        pcc_code_coding_display as code_display,

        -- Classification details
        procedure_classification,
        cpt_classification,
        classification_confidence,
        is_tumor_surgery,

        -- NEW: OID decoding and linkage columns
        epic_or_log_id,
        in_surgical_procedures_table,
        procedure_source_type,
        is_likely_performed,
        proc_status_annotation,
        category_coding_code

    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = TRUE
),

-- Get summary of what's in surgical_procedures
surgical_procedures_summary AS (
    SELECT
        procedure_id,
        epic_case_orlog_id,
        mrn,
        procedure_date,
        procedure_name,
        is_tumor_related
    FROM fhir_prd_db.surgical_procedures
    WHERE is_tumor_related = TRUE
)

-- ============================================================================
-- MAIN QUERY: Tumor surgeries NOT in surgical_procedures
-- ============================================================================
SELECT
    -- ========================================================================
    -- PATIENT & PROCEDURE IDENTIFIERS
    -- ========================================================================
    tsp.patient_fhir_id,
    tsp.procedure_fhir_id,
    tsp.procedure_date,
    EXTRACT(YEAR FROM tsp.procedure_date) as procedure_year,

    -- ========================================================================
    -- PROCEDURE DETAILS
    -- ========================================================================
    tsp.proc_code_text as procedure_description,
    tsp.code as procedure_code,
    tsp.code_display as procedure_code_display,

    -- ========================================================================
    -- CODING SYSTEM (helps identify why it might be missing)
    -- ========================================================================
    tsp.pcc_coding_system_code as coding_system,
    tsp.pcc_coding_system_name,
    CASE
        WHEN tsp.pcc_coding_system_code = 'CPT' THEN 'Standard CPT code'
        WHEN tsp.pcc_coding_system_code = 'EAP' THEN 'Epic Procedure Masterfile code'
        WHEN tsp.pcc_coding_system_code = 'LOINC' THEN 'LOINC laboratory code'
        WHEN tsp.pcc_coding_system_code = 'CDT-2' THEN 'Dental procedure code'
        WHEN tsp.pcc_coding_system_code = 'HCPCS' THEN 'CMS billing code'
        ELSE 'Other coding system'
    END as coding_system_explanation,

    -- ========================================================================
    -- CLASSIFICATION (shows how v_procedures_tumor identified it as tumor surgery)
    -- ========================================================================
    tsp.cpt_classification,
    tsp.procedure_classification,
    tsp.classification_confidence,
    CASE
        WHEN tsp.classification_confidence >= 90 THEN 'High Confidence (90-100)'
        WHEN tsp.classification_confidence >= 70 THEN 'Medium-High Confidence (70-89)'
        WHEN tsp.classification_confidence >= 50 THEN 'Medium Confidence (50-69)'
        ELSE 'Lower Confidence (<50)'
    END as confidence_level,

    -- ========================================================================
    -- STATUS & CATEGORY (helps identify why surgical_procedures might have excluded it)
    -- ========================================================================
    tsp.proc_status,
    tsp.proc_status_annotation,
    tsp.proc_category_text as epic_category,
    tsp.procedure_source_type,
    tsp.is_likely_performed,

    -- ========================================================================
    -- EPIC OR LOG LINKAGE (critical for surgical_procedures inclusion)
    -- ========================================================================
    tsp.epic_or_log_id,
    tsp.in_surgical_procedures_table,
    CASE
        WHEN tsp.epic_or_log_id IS NULL THEN 'NO OR LOG ID - Not an Epic OR case'
        WHEN tsp.in_surgical_procedures_table THEN 'ERROR: Has OR Log but still in results?'
        ELSE 'Has OR Log but not in surgical_procedures - INVESTIGATE'
    END as or_log_status,

    -- ========================================================================
    -- SNOMED CATEGORY (surgical_procedures filters on SNOMED code 387713003)
    -- ========================================================================
    tsp.category_coding_code as snomed_category_code,
    CASE
        WHEN tsp.category_coding_code = '387713003' THEN 'Has SNOMED Surgical Procedure code'
        WHEN tsp.category_coding_code IS NULL THEN 'Missing SNOMED category code'
        ELSE 'Has different SNOMED code: ' || tsp.category_coding_code
    END as snomed_status,

    -- ========================================================================
    -- WHY IT'S MISSING: Root Cause Analysis
    -- ========================================================================
    CASE
        WHEN tsp.in_surgical_procedures_table THEN
            'ERROR: This should not appear in results (already in surgical_procedures)'

        WHEN tsp.epic_or_log_id IS NULL AND tsp.proc_category_text = 'Ordered Procedures' THEN
            'PROCEDURE ORDER - Not an actual surgery, just an order/requisition'

        WHEN tsp.epic_or_log_id IS NULL AND tsp.proc_category_text = 'Surgical History' THEN
            'SURGICAL HISTORY - External/historical procedure, not a CHOP OR case'

        WHEN tsp.epic_or_log_id IS NULL AND tsp.proc_status = 'not-done' THEN
            'NOT PERFORMED - Procedure was not completed'

        WHEN tsp.epic_or_log_id IS NULL THEN
            'NO EPIC OR LOG - Not tracked in Epic OR log (possibly outpatient, external, or documentation-only)'

        WHEN tsp.proc_status != 'completed' THEN
            'STATUS NOT COMPLETED - surgical_procedures filters to status=completed only'

        WHEN tsp.category_coding_code IS NULL THEN
            'MISSING SNOMED CATEGORY - surgical_procedures requires SNOMED code 387713003'

        WHEN tsp.category_coding_code != '387713003' THEN
            'DIFFERENT SNOMED CATEGORY - surgical_procedures filters to 387713003 (surgical procedure) only'

        ELSE
            'UNKNOWN - Has OR Log, completed status, correct SNOMED - needs investigation'
    END as reason_missing_from_surgical_procedures,

    -- ========================================================================
    -- RECOMMENDATION: Should this be added to surgical_procedures?
    -- ========================================================================
    CASE
        WHEN tsp.in_surgical_procedures_table THEN
            'Already included'

        -- Definitely should NOT be added (procedure orders, history, not done)
        WHEN tsp.proc_category_text = 'Ordered Procedures' THEN
            '❌ DO NOT ADD - This is a procedure order, not an actual surgery'

        WHEN tsp.proc_category_text = 'Surgical History' AND tsp.is_likely_performed = FALSE THEN
            '❌ DO NOT ADD - Historical/external procedure, not performed at CHOP'

        WHEN tsp.proc_status = 'not-done' THEN
            '❌ DO NOT ADD - Procedure was not performed'

        WHEN tsp.is_likely_performed = FALSE THEN
            '❌ DO NOT ADD - Marked as not performed'

        -- Possibly should be added (has OR log but missing from surgical_procedures)
        WHEN tsp.epic_or_log_id IS NOT NULL AND tsp.proc_status = 'completed' THEN
            '✅ REVIEW TO ADD - Has Epic OR Log and completed status, should be in surgical_procedures'

        -- Edge cases that need review
        WHEN tsp.proc_category_text = 'Surgical History' AND tsp.is_likely_performed = TRUE THEN
            '⚡ REVIEW - Surgical history but marked as performed, verify if CHOP OR case'

        WHEN tsp.classification_confidence >= 90 AND tsp.proc_status = 'completed' THEN
            '⚡ REVIEW - High confidence tumor surgery, completed status, but no OR log'

        ELSE
            '⚠️ NEEDS INVESTIGATION - Review case details'
    END as recommendation

FROM tumor_surgeries_procedures tsp

-- FILTER: Only procedures NOT in surgical_procedures
WHERE tsp.in_surgical_procedures_table = FALSE

ORDER BY
    -- Sort by recommendation priority
    CASE
        WHEN tsp.epic_or_log_id IS NOT NULL AND tsp.proc_status = 'completed' THEN 1  -- High priority
        WHEN tsp.classification_confidence >= 90 AND tsp.proc_status = 'completed' THEN 2
        WHEN tsp.proc_category_text = 'Surgical History' AND tsp.is_likely_performed = TRUE THEN 3
        WHEN tsp.proc_category_text = 'Ordered Procedures' THEN 99  -- Low priority (don't add)
        ELSE 50
    END,
    tsp.procedure_date DESC,
    tsp.patient_fhir_id;


-- ============================================================================
-- SUMMARY STATISTICS: How many tumor surgeries are missing and why?
-- ============================================================================
-- Uncomment this section to see summary counts:
/*
WITH missing_summary AS (
    SELECT
        CASE
            WHEN tsp.proc_category_text = 'Ordered Procedures' THEN 'Procedure Orders (Do Not Add)'
            WHEN tsp.proc_category_text = 'Surgical History' THEN 'Surgical History (External/Historical)'
            WHEN tsp.epic_or_log_id IS NOT NULL THEN 'Has Epic OR Log (Should Review)'
            WHEN tsp.proc_status != 'completed' THEN 'Not Completed Status'
            WHEN tsp.category_coding_code != '387713003' THEN 'Missing/Wrong SNOMED Category'
            ELSE 'Other'
        END as missing_category,

        COUNT(*) as procedure_count,
        COUNT(DISTINCT tsp.patient_fhir_id) as patient_count,
        MIN(tsp.procedure_date) as earliest_date,
        MAX(tsp.procedure_date) as latest_date

    FROM fhir_prd_db.v_procedures_tumor tsp
    WHERE tsp.is_tumor_surgery = TRUE
        AND tsp.in_surgical_procedures_table = FALSE
    GROUP BY 1
)
SELECT
    missing_category,
    procedure_count,
    patient_count,
    earliest_date,
    latest_date,
    ROUND(100.0 * procedure_count / SUM(procedure_count) OVER (), 1) as pct_of_missing
FROM missing_summary
ORDER BY procedure_count DESC;
*/
