-- ============================================================================
-- TEST: Unified Episode View (Strategy A + Strategy D)
-- ============================================================================

WITH unified_test AS (
    SELECT
        episode_detection_method,
        COUNT(DISTINCT patient_fhir_id) as patients,
        COUNT(*) as episodes,
        ROUND(AVG(CAST(episode_duration_days AS DOUBLE)), 1) as avg_duration_days,

        -- Data availability
        SUM(CASE WHEN has_structured_dose THEN 1 ELSE 0 END) as episodes_with_dose,
        SUM(CASE WHEN has_documents THEN 1 ELSE 0 END) as episodes_with_docs,

        -- Dose statistics (Strategy A only)
        ROUND(AVG(total_dose_cgy), 1) as avg_total_dose,

        -- Document statistics (Strategy D only)
        ROUND(AVG(num_documents), 1) as avg_docs_per_episode,
        SUM(priority_1_docs) as total_priority_1_docs,
        SUM(priority_2_docs) as total_priority_2_docs,

        -- NLP priority distribution
        SUM(CASE WHEN nlp_extraction_priority LIKE '%HIGH%' THEN 1 ELSE 0 END) as high_priority_nlp,
        SUM(CASE WHEN nlp_extraction_priority LIKE '%MEDIUM%' THEN 1 ELSE 0 END) as medium_priority_nlp,
        SUM(CASE WHEN nlp_extraction_priority LIKE '%LOW%' THEN 1 ELSE 0 END) as low_priority_nlp

    FROM fhir_prd_db.v_radiation_treatment_episodes
    GROUP BY episode_detection_method
)

SELECT
    episode_detection_method,
    patients,
    episodes,
    avg_duration_days,
    episodes_with_dose,
    episodes_with_docs,
    avg_total_dose,
    avg_docs_per_episode,
    total_priority_1_docs,
    total_priority_2_docs,
    high_priority_nlp,
    medium_priority_nlp,
    low_priority_nlp
FROM unified_test

UNION ALL

SELECT
    'TOTAL' as episode_detection_method,
    SUM(patients) as patients,
    SUM(episodes) as episodes,
    ROUND(AVG(avg_duration_days), 1) as avg_duration_days,
    SUM(episodes_with_dose) as episodes_with_dose,
    SUM(episodes_with_docs) as episodes_with_docs,
    ROUND(AVG(avg_total_dose), 1) as avg_total_dose,
    ROUND(AVG(avg_docs_per_episode), 1) as avg_docs_per_episode,
    SUM(total_priority_1_docs) as total_priority_1_docs,
    SUM(total_priority_2_docs) as total_priority_2_docs,
    SUM(high_priority_nlp) as high_priority_nlp,
    SUM(medium_priority_nlp) as medium_priority_nlp,
    SUM(low_priority_nlp) as low_priority_nlp
FROM unified_test

ORDER BY
    CASE episode_detection_method
        WHEN 'structured_course_id' THEN 1
        WHEN 'document_temporal_cluster' THEN 2
        WHEN 'TOTAL' THEN 3
    END;
