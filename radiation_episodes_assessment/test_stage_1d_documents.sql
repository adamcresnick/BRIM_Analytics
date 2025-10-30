-- ============================================================================
-- TEST: Strategy D - Document Temporal Clustering
-- ============================================================================
-- Purpose: Validate document-based episode detection for patients without
--          structured observations (course_id)
-- Expected: ~478 patients with dated documents (excluding Strategy A patients)
-- ============================================================================

WITH documents_with_dates AS (
    SELECT
        patient_fhir_id,
        document_id,
        doc_date,
        doc_type_text,
        extraction_priority,
        document_category
    FROM fhir_prd_db.v_radiation_documents
    WHERE doc_date IS NOT NULL
),

-- Exclude patients already covered by Strategy A (structured observations)
patients_needing_document_episodes AS (
    SELECT DISTINCT patient_fhir_id
    FROM documents_with_dates
    WHERE patient_fhir_id NOT IN (
        SELECT DISTINCT patient_fhir_id
        FROM fhir_prd_db.v_radiation_treatments
        WHERE course_id IS NOT NULL
    )
),

-- Filter to only documents for patients needing episodes
filtered_documents AS (
    SELECT d.*
    FROM documents_with_dates d
    INNER JOIN patients_needing_document_episodes p
        ON d.patient_fhir_id = p.patient_fhir_id
),

-- Calculate gaps between consecutive documents per patient
document_with_prev AS (
    SELECT
        patient_fhir_id,
        document_id,
        doc_date,
        doc_type_text,
        extraction_priority,
        document_category,
        LAG(CAST(doc_date AS DATE))
            OVER (PARTITION BY patient_fhir_id ORDER BY doc_date) as prev_doc_date
    FROM filtered_documents
),

-- Mark new episodes when gap > 30 days
document_with_gap_flag AS (
    SELECT
        patient_fhir_id,
        document_id,
        doc_date,
        doc_type_text,
        extraction_priority,
        document_category,
        prev_doc_date,
        CASE
            WHEN prev_doc_date IS NULL THEN 1  -- First document = episode 1
            WHEN DATE_DIFF('day', prev_doc_date, CAST(doc_date AS DATE)) > 30 THEN 1  -- Gap > 30 days = new episode
            ELSE 0  -- Continue current episode
        END as is_new_episode
    FROM document_with_prev
),

-- Assign episode numbers using cumulative sum
document_with_episode AS (
    SELECT
        patient_fhir_id,
        document_id,
        doc_date,
        doc_type_text,
        extraction_priority,
        document_category,
        SUM(is_new_episode) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY doc_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) as episode_number
    FROM document_with_gap_flag
),

-- Aggregate documents into episodes
strategy_d_episodes AS (
    SELECT
        patient_fhir_id,
        episode_number,
        MIN(doc_date) as episode_start_date,
        MAX(doc_date) as episode_end_date,
        COUNT(DISTINCT document_id) as num_documents,
        MIN(extraction_priority) as highest_priority_available,
        COUNT(DISTINCT CASE WHEN extraction_priority = 1 THEN document_id END) as priority_1_docs,
        COUNT(DISTINCT CASE WHEN extraction_priority = 2 THEN document_id END) as priority_2_docs,
        COUNT(DISTINCT CASE WHEN extraction_priority = 3 THEN document_id END) as priority_3_docs,
        COUNT(DISTINCT CASE WHEN extraction_priority = 4 THEN document_id END) as priority_4_docs,
        COUNT(DISTINCT CASE WHEN extraction_priority = 5 THEN document_id END) as priority_5_docs
    FROM document_with_episode
    GROUP BY patient_fhir_id, episode_number
)

-- Summary statistics
SELECT
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(*) as total_episodes,
    ROUND(AVG(CAST(episode_count AS DOUBLE)), 2) as avg_episodes_per_patient,
    ROUND(AVG(CAST(num_documents AS DOUBLE)), 1) as avg_documents_per_episode,
    ROUND(AVG(CAST(episode_duration_days AS DOUBLE)), 1) as avg_episode_duration_days,

    -- NLP Priority Distribution
    SUM(priority_1_docs) as total_priority_1_docs,
    SUM(priority_2_docs) as total_priority_2_docs,
    SUM(priority_3_docs) as total_priority_3_docs,
    SUM(priority_4_docs) as total_priority_4_docs,
    SUM(priority_5_docs) as total_priority_5_docs,

    -- Episodes by highest priority available
    COUNT(CASE WHEN highest_priority_available = 1 THEN 1 END) as episodes_with_priority_1,
    COUNT(CASE WHEN highest_priority_available = 2 THEN 1 END) as episodes_with_priority_2,
    COUNT(CASE WHEN highest_priority_available = 3 THEN 1 END) as episodes_with_priority_3,
    COUNT(CASE WHEN highest_priority_available = 4 THEN 1 END) as episodes_with_priority_4,
    COUNT(CASE WHEN highest_priority_available = 5 THEN 1 END) as episodes_with_priority_5

FROM (
    SELECT
        patient_fhir_id,
        episode_number,
        num_documents,
        highest_priority_available,
        priority_1_docs,
        priority_2_docs,
        priority_3_docs,
        priority_4_docs,
        priority_5_docs,
        DATE_DIFF('day', episode_start_date, episode_end_date) as episode_duration_days,
        COUNT(*) OVER (PARTITION BY patient_fhir_id) as episode_count
    FROM strategy_d_episodes
);
