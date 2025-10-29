-- ============================================================================
-- RADIATION EPISODES - STRATEGY D: DOCUMENT TEMPORAL CLUSTERING
-- ============================================================================
-- Purpose: Create episodes from document temporal clustering (30-day gap)
-- Pattern: Follows chemotherapy medication_episodes temporal windowing approach
-- Coverage: Patients with radiation documents but NO structured course_id
-- Reliability: MEDIUM - Heuristic based on gap threshold
-- Testing Stage: 1D
-- Date Source: document_reference.date (62.8% coverage = 478 patients with dated docs)
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
strategy_d_document_episodes AS (
    SELECT
        patient_fhir_id,
        episode_number,
        patient_fhir_id || '_doc_episode_' || CAST(episode_number AS VARCHAR) as episode_id,
        'document_temporal_cluster' as episode_detection_method,

        -- Episode temporal boundaries from documents
        MIN(doc_date) as episode_start_datetime,
        MAX(doc_date) as episode_end_datetime,
        CAST(MIN(doc_date) AS DATE) as episode_start_date,
        CAST(MAX(doc_date) AS DATE) as episode_end_date,

        -- Date source tracking
        'document_date' as episode_start_date_source,
        'document_date' as episode_end_date_source,

        -- Document counts
        COUNT(DISTINCT document_id) as num_documents,

        -- Document priority distribution (for NLP optimization)
        COUNT(DISTINCT CASE WHEN extraction_priority = 1 THEN document_id END) as priority_1_docs,  -- Treatment summaries
        COUNT(DISTINCT CASE WHEN extraction_priority = 2 THEN document_id END) as priority_2_docs,  -- Consultations
        COUNT(DISTINCT CASE WHEN extraction_priority = 3 THEN document_id END) as priority_3_docs,  -- Outside summaries
        COUNT(DISTINCT CASE WHEN extraction_priority = 4 THEN document_id END) as priority_4_docs,  -- Progress notes
        COUNT(DISTINCT CASE WHEN extraction_priority = 5 THEN document_id END) as priority_5_docs,  -- Other

        -- Highest priority document (lowest number = highest priority)
        MIN(extraction_priority) as highest_priority_available,

        -- Document categories
        LISTAGG(DISTINCT doc_type_text, ', ') WITHIN GROUP (ORDER BY extraction_priority) as document_types,
        LISTAGG(DISTINCT document_category, ', ') WITHIN GROUP (ORDER BY extraction_priority) as document_categories,

        -- Document IDs for linking
        ARRAY_AGG(document_id ORDER BY extraction_priority, doc_date) as constituent_document_ids,

        -- Data availability flags
        CAST(0 AS BOOLEAN) as has_structured_dose,
        CAST(0 AS BOOLEAN) as has_structured_field,
        CAST(0 AS BOOLEAN) as has_structured_site,
        CAST(1 AS BOOLEAN) as has_episode_dates,
        CAST(0 AS BOOLEAN) as has_appointments,
        CAST(1 AS BOOLEAN) as has_documents,

        -- Source-specific dates for transparency
        CAST(NULL AS TIMESTAMP(3)) as obs_start_date,
        CAST(NULL AS TIMESTAMP(3)) as obs_stop_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_start_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_end_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_first_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_last_date,
        MIN(doc_date) as doc_earliest_date,
        MAX(doc_date) as doc_latest_date,

        -- No dose/site data for Strategy D
        CAST(NULL AS DOUBLE) as total_dose_cgy,
        CAST(NULL AS DOUBLE) as avg_dose_cgy,
        CAST(NULL AS DOUBLE) as min_dose_cgy,
        CAST(NULL AS DOUBLE) as max_dose_cgy,
        CAST(0 AS INTEGER) as num_dose_records,
        CAST(0 AS INTEGER) as num_unique_fields,
        CAST(0 AS INTEGER) as num_unique_sites,
        CAST(NULL AS VARCHAR) as radiation_fields,
        CAST(NULL AS VARCHAR) as radiation_site_codes,
        CAST(NULL AS VARCHAR) as radiation_sites_summary

    FROM document_with_episode
    GROUP BY patient_fhir_id, episode_number
)

SELECT
    *,
    -- Calculate episode duration
    DATE_DIFF('day', episode_start_date, episode_end_date) as episode_duration_days,

    -- NLP extraction recommendation
    CASE
        WHEN highest_priority_available = 1 THEN 'HIGH - Treatment Summary Available'
        WHEN highest_priority_available = 2 THEN 'MEDIUM - Consultation Notes Available'
        WHEN highest_priority_available = 3 THEN 'MEDIUM - Outside Summary Available'
        WHEN highest_priority_available = 4 THEN 'LOW - Progress Notes Only'
        ELSE 'VERY LOW - Other Documents Only'
    END as nlp_extraction_priority

FROM strategy_d_document_episodes
ORDER BY patient_fhir_id, episode_start_datetime;
