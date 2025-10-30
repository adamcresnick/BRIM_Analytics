-- ============================================================================
-- TEST: v_pathology_diagnostics NLP Prioritization Framework
-- ============================================================================
-- Purpose: Validate that extraction_priority and document_category fields are
--          correctly assigned to pathology documents for NLP workflow optimization
-- ============================================================================

-- ==========================================================================
-- TEST 1: Prioritization distribution by diagnostic source
-- ==========================================================================
-- Expected: diagnostic_report and pathology_document sources have priorities 1-5
--           observation and problem_list sources have NULL priorities

SELECT
    diagnostic_source,
    extraction_priority,
    COUNT(*) as record_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(DISTINCT document_category) as unique_categories
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY diagnostic_source, extraction_priority
ORDER BY diagnostic_source, extraction_priority;


-- ==========================================================================
-- TEST 2: Document category distribution by extraction priority
-- ==========================================================================
-- Verify that higher priority documents have appropriate categories

SELECT
    extraction_priority,
    document_category,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    ROUND(AVG(days_from_surgery), 1) as avg_days_from_surgery,
    MIN(days_from_surgery) as min_days_from_surgery,
    MAX(days_from_surgery) as max_days_from_surgery
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority IS NOT NULL
GROUP BY extraction_priority, document_category
ORDER BY extraction_priority, document_count DESC;


-- ==========================================================================
-- TEST 3: High-priority documents for NLP targeting
-- ==========================================================================
-- Identify documents with extraction_priority 1-2 (highest value for NLP)

SELECT
    diagnostic_source,
    extraction_priority,
    document_category,
    COUNT(*) as total_documents,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(CASE WHEN days_from_surgery <= 7 THEN 1 END) as documents_within_7_days,
    COUNT(CASE WHEN days_from_surgery <= 14 THEN 1 END) as documents_within_14_days,
    COUNT(CASE WHEN days_from_surgery <= 30 THEN 1 END) as documents_within_30_days
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority IN (1, 2)
GROUP BY diagnostic_source, extraction_priority, document_category
ORDER BY extraction_priority, total_documents DESC;


-- ==========================================================================
-- TEST 4: Temporal relevance analysis
-- ==========================================================================
-- Check days_from_surgery distribution by priority level

SELECT
    extraction_priority,
    diagnostic_source,
    COUNT(*) as document_count,
    ROUND(AVG(days_from_surgery), 1) as avg_days_from_surgery,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY days_from_surgery), 1) as p25_days,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY days_from_surgery), 1) as median_days,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY days_from_surgery), 1) as p75_days,
    MAX(days_from_surgery) as max_days_from_surgery
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority IS NOT NULL
GROUP BY extraction_priority, diagnostic_source
ORDER BY extraction_priority, diagnostic_source;


-- ==========================================================================
-- TEST 5: Patient-level NLP opportunity summary
-- ==========================================================================
-- Show which patients have high-priority documents available for NLP extraction

WITH patient_document_summary AS (
    SELECT
        patient_fhir_id,
        COUNT(CASE WHEN extraction_priority = 1 THEN 1 END) as priority_1_docs,
        COUNT(CASE WHEN extraction_priority = 2 THEN 1 END) as priority_2_docs,
        COUNT(CASE WHEN extraction_priority = 3 THEN 1 END) as priority_3_docs,
        COUNT(CASE WHEN extraction_priority = 4 THEN 1 END) as priority_4_docs,
        COUNT(CASE WHEN extraction_priority = 5 THEN 1 END) as priority_5_docs,
        COUNT(CASE WHEN extraction_priority IS NULL THEN 1 END) as structured_records,

        MIN(CASE WHEN extraction_priority IS NOT NULL THEN extraction_priority END) as highest_priority_available,

        -- Closest document to surgery
        MIN(CASE WHEN extraction_priority IS NOT NULL THEN days_from_surgery END) as closest_doc_days,

        -- Count of unique document categories available
        COUNT(DISTINCT document_category) as unique_doc_categories

    FROM fhir_prd_db.v_pathology_diagnostics
    GROUP BY patient_fhir_id
)

SELECT
    highest_priority_available,
    COUNT(*) as patient_count,

    -- Average documents per patient by priority
    ROUND(AVG(priority_1_docs), 1) as avg_priority_1_docs,
    ROUND(AVG(priority_2_docs), 1) as avg_priority_2_docs,
    ROUND(AVG(priority_3_docs), 1) as avg_priority_3_docs,
    ROUND(AVG(priority_4_docs), 1) as avg_priority_4_docs,
    ROUND(AVG(priority_5_docs), 1) as avg_priority_5_docs,

    -- Structured data availability
    ROUND(AVG(structured_records), 1) as avg_structured_records,

    -- Temporal metrics
    ROUND(AVG(closest_doc_days), 1) as avg_closest_doc_days,
    ROUND(AVG(unique_doc_categories), 1) as avg_unique_categories

FROM patient_document_summary
GROUP BY highest_priority_available
ORDER BY highest_priority_available;


-- ==========================================================================
-- TEST 6: Sample high-priority documents for quality review
-- ==========================================================================
-- Review actual document names/descriptions for each priority level

SELECT
    extraction_priority,
    document_category,
    diagnostic_source,
    diagnostic_name,
    days_from_surgery,
    LEFT(result_value, 150) as result_sample
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority IS NOT NULL
ORDER BY extraction_priority, days_from_surgery
LIMIT 100;


-- ==========================================================================
-- TEST 7: Molecular pathology document identification
-- ==========================================================================
-- Verify Priority 2 molecular/genomics documents are captured correctly

SELECT
    document_category,
    diagnostic_source,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    ARRAY_AGG(DISTINCT diagnostic_name)[1:10] as sample_document_names
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority = 2
  AND (document_category = 'Molecular Pathology Report'
       OR LOWER(diagnostic_name) LIKE '%molecular%'
       OR LOWER(diagnostic_name) LIKE '%genomic%')
GROUP BY document_category, diagnostic_source
ORDER BY document_count DESC;


-- ==========================================================================
-- TEST 8: Outside/send-out pathology summary identification
-- ==========================================================================
-- Verify Priority 3 outside summaries are captured correctly

SELECT
    document_category,
    diagnostic_source,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    ARRAY_AGG(DISTINCT diagnostic_name)[1:10] as sample_document_names
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority = 3
GROUP BY document_category, diagnostic_source
ORDER BY document_count DESC;


-- ==========================================================================
-- TEST 9: NLP extraction workflow priority targeting
-- ==========================================================================
-- Create a prioritized document list for NLP extraction workflows
-- Order by: priority level (1-5), then temporal proximity to surgery

WITH nlp_prioritized_documents AS (
    SELECT
        patient_fhir_id,
        diagnostic_source,
        source_id,
        extraction_priority,
        document_category,
        days_from_surgery,
        diagnostic_date,
        diagnostic_name,
        LEFT(result_value, 200) as result_preview,

        -- Composite priority score (lower = higher priority)
        -- Priority level * 1000 + days_from_surgery
        -- E.g., Priority 1 doc at 5 days = 1005
        --       Priority 2 doc at 10 days = 2010
        (extraction_priority * 1000) + days_from_surgery as composite_priority_score

    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE extraction_priority IS NOT NULL
)

SELECT
    patient_fhir_id,
    extraction_priority,
    document_category,
    days_from_surgery,
    composite_priority_score,
    diagnostic_date,
    diagnostic_name,
    result_preview
FROM nlp_prioritized_documents
ORDER BY composite_priority_score, patient_fhir_id
LIMIT 50;


-- ==========================================================================
-- TEST 10: Compare prioritization framework with radiation episodes
-- ==========================================================================
-- Validate that pathology prioritization follows similar patterns as radiation

SELECT
    'Pathology' as domain,
    extraction_priority,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients
FROM fhir_prd_db.v_pathology_diagnostics
WHERE extraction_priority IS NOT NULL
GROUP BY extraction_priority

UNION ALL

SELECT
    'Radiation' as domain,
    extraction_priority,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients
FROM fhir_prd_db.v_radiation_documents
WHERE extraction_priority IS NOT NULL
GROUP BY extraction_priority

ORDER BY domain, extraction_priority;


-- ==========================================================================
-- TEST 11: Structured vs unstructured data split
-- ==========================================================================
-- Verify that observations and conditions are correctly marked as structured
-- (extraction_priority = NULL) and documents are marked for NLP

SELECT
    CASE
        WHEN extraction_priority IS NOT NULL THEN 'Unstructured (NLP Target)'
        ELSE 'Structured (No NLP Needed)'
    END as data_type,
    diagnostic_source,
    COUNT(*) as record_count,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_total
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY
    CASE
        WHEN extraction_priority IS NOT NULL THEN 'Unstructured (NLP Target)'
        ELSE 'Structured (No NLP Needed)'
    END,
    diagnostic_source
ORDER BY data_type, record_count DESC;


-- ==========================================================================
-- TEST 12: Multi-surgery patients document prioritization
-- ==========================================================================
-- For patients with multiple surgeries, verify documents are correctly linked
-- to closest surgery and prioritized appropriately

WITH patient_surgery_counts AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT linked_procedure_id) as surgery_count
    FROM fhir_prd_db.v_pathology_diagnostics
    GROUP BY patient_fhir_id
    HAVING COUNT(DISTINCT linked_procedure_id) > 1
)

SELECT
    pd.patient_fhir_id,
    COUNT(DISTINCT pd.linked_procedure_id) as surgeries,
    COUNT(CASE WHEN pd.extraction_priority = 1 THEN 1 END) as priority_1_docs,
    COUNT(CASE WHEN pd.extraction_priority = 2 THEN 1 END) as priority_2_docs,
    COUNT(CASE WHEN pd.extraction_priority IS NOT NULL THEN 1 END) as total_nlp_docs,
    MIN(pd.days_from_surgery) as closest_doc_days,
    MAX(pd.days_from_surgery) as furthest_doc_days
FROM fhir_prd_db.v_pathology_diagnostics pd
INNER JOIN patient_surgery_counts psc
    ON pd.patient_fhir_id = psc.patient_fhir_id
WHERE pd.extraction_priority IS NOT NULL
GROUP BY pd.patient_fhir_id
ORDER BY total_nlp_docs DESC
LIMIT 20;
