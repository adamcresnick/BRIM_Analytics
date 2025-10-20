-- ================================================================================
-- FIX: v_binary_files - ISO 8601 Date Parsing Issue
-- ================================================================================
--
-- ISSUE: All dr_date, dr_context_period_start, dr_context_period_end columns
--        were returning NULL because TRY(CAST(... AS TIMESTAMP(3))) fails on
--        ISO 8601 formatted strings like "2018-06-03T10:27:29Z"
--
-- ROOT CAUSE: Athena TRY(CAST()) does not handle ISO 8601 timezone format
--
-- SOLUTION: Use from_iso8601_timestamp() function before casting to TIMESTAMP(3)
--
-- IMPACT:
--   - ALL binary files (PDFs, images, etc.) had NULL dates
--   - Made temporal linking to imaging events impossible
--   - Agent 1 multi-source validation could not find PDFs near events
--
-- FIX APPLIED:
--   - dr_date: TRY(CAST(dr.date AS TIMESTAMP(3)))
--              → CAST(from_iso8601_timestamp(dr.date) AS TIMESTAMP(3))
--   - dr_context_period_start: Similar fix
--   - dr_context_period_end: Similar fix
--   - age_at_document_days: Updated to use from_iso8601_timestamp()
--
-- TESTING:
--   Before: SELECT COUNT(*) FROM v_binary_files WHERE dr_date IS NOT NULL → 0
--   After:  SELECT COUNT(*) FROM v_binary_files WHERE dr_date IS NOT NULL → ~thousands
--
-- DATE: 2025-10-19
-- AUTHOR: Agent 1 (Claude) - Multi-source resolution workflow
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_binary_files AS
WITH document_contexts AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT context_encounter_reference, ' | ')
            WITHIN GROUP (ORDER BY context_encounter_reference) as encounter_references,
        LISTAGG(DISTINCT context_encounter_display, ' | ')
            WITHIN GROUP (ORDER BY context_encounter_display) as encounter_displays
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
),
document_type_coding AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT type_coding_system, ' | ')
            WITHIN GROUP (ORDER BY type_coding_system) as type_coding_systems,
        LISTAGG(DISTINCT type_coding_code, ' | ')
            WITHIN GROUP (ORDER BY type_coding_code) as type_coding_codes,
        LISTAGG(DISTINCT type_coding_display, ' | ')
            WITHIN GROUP (ORDER BY type_coding_display) as type_coding_displays
    FROM fhir_prd_db.document_reference_type_coding
    GROUP BY document_reference_id
)
SELECT
    dr.id as document_reference_id,
    dr.subject_reference as patient_fhir_id,
    dr.status as dr_status,
    dr.doc_status as dr_doc_status,
    dr.type_text as dr_type_text,
    dcat.category_text as dr_category_text,

    -- *** FIXED: Use from_iso8601_timestamp() with NULL handling for empty strings ***
    CASE WHEN dr.date IS NOT NULL AND dr.date != '' THEN CAST(from_iso8601_timestamp(dr.date) AS TIMESTAMP(3)) ELSE NULL END as dr_date,

    dr.description as dr_description,

    -- *** FIXED: Context period dates with NULL handling ***
    CASE WHEN dr.context_period_start IS NOT NULL AND dr.context_period_start != '' THEN CAST(from_iso8601_timestamp(dr.context_period_start) AS TIMESTAMP(3)) ELSE NULL END as dr_context_period_start,
    CASE WHEN dr.context_period_end IS NOT NULL AND dr.context_period_end != '' THEN CAST(from_iso8601_timestamp(dr.context_period_end) AS TIMESTAMP(3)) ELSE NULL END as dr_context_period_end,

    dr.context_facility_type_text as dr_facility_type,
    dr.context_practice_setting_text as dr_practice_setting,
    dr.authenticator_display as dr_authenticator,
    dr.custodian_display as dr_custodian,
    denc.encounter_references as dr_encounter_references,
    denc.encounter_displays as dr_encounter_displays,

    dtc.type_coding_systems as dr_type_coding_systems,
    dtc.type_coding_codes as dr_type_coding_codes,
    dtc.type_coding_displays as dr_type_coding_displays,

    dcont.content_attachment_url as binary_id,
    dcont.content_attachment_content_type as content_type,
    dcont.content_attachment_size as content_size_bytes,
    dcont.content_attachment_title as content_title,
    dcont.content_format_display as content_format,

    -- *** FIXED: Age calculation using from_iso8601_timestamp() ***
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        DATE(from_iso8601_timestamp(dr.date)))) as age_at_document_days

FROM fhir_prd_db.document_reference dr
LEFT JOIN document_contexts denc ON dr.id = denc.document_reference_id
LEFT JOIN document_categories dcat ON dr.id = dcat.document_reference_id
LEFT JOIN document_type_coding dtc ON dr.id = dtc.document_reference_id
LEFT JOIN fhir_prd_db.document_reference_content dcont ON dr.id = dcont.document_reference_id
LEFT JOIN fhir_prd_db.patient pa ON dr.subject_reference = CONCAT('Patient/', pa.id)
WHERE dr.subject_reference IS NOT NULL
ORDER BY dr.subject_reference, dr.date DESC;

-- ================================================================================
-- VERIFICATION QUERIES
-- ================================================================================

-- 1. Check that dates are now populated
-- SELECT
--     COUNT(*) as total_binary_files,
--     COUNT(dr_date) as files_with_dr_date,
--     COUNT(dr_context_period_start) as files_with_context_start,
--     COUNT(dr_context_period_end) as files_with_context_end,
--     ROUND(100.0 * COUNT(dr_date) / COUNT(*), 2) as pct_with_dr_date
-- FROM fhir_prd_db.v_binary_files;

-- 2. Check date ranges for patient e4BwD8ZYDBccepXcJ.Ilo3w3
-- SELECT
--     patient_fhir_id,
--     MIN(dr_date) as earliest_date,
--     MAX(dr_date) as latest_date,
--     COUNT(*) as total_files,
--     COUNT(DISTINCT dr_category_text) as categories
-- FROM fhir_prd_db.v_binary_files
-- WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
-- GROUP BY patient_fhir_id;

-- 3. Sample imaging PDFs with dates for temporal linking test
-- SELECT
--     document_reference_id,
--     dr_date,
--     dr_category_text,
--     dr_type_text,
--     content_title
-- FROM fhir_prd_db.v_binary_files
-- WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
--     AND content_type = 'application/pdf'
--     AND dr_category_text = 'Imaging Result'
--     AND dr_date BETWEEN TIMESTAMP '2018-05-20' AND TIMESTAMP '2018-06-05'
-- ORDER BY dr_date;

-- ================================================================================
