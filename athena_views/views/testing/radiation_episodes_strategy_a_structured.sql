-- ============================================================================
-- RADIATION EPISODES - STRATEGY A: STRUCTURED COURSE ID
-- ============================================================================
-- Purpose: Create episodes from explicit course_id in v_radiation_treatments
-- Coverage: ~90 patients with ELECT structured observations
-- Reliability: HIGH - Explicit course identifier from structured data
-- Testing Stage: 1A
-- ============================================================================

WITH strategy_a_structured_episodes AS (
    SELECT
        patient_fhir_id,
        course_id as episode_id,
        'structured_course_id' as episode_detection_method,

        -- Episode temporal boundaries from structured observations
        MIN(obs_start_date) as episode_start_datetime,
        MAX(obs_stop_date) as episode_end_datetime,
        CAST(MIN(obs_start_date) AS DATE) as episode_start_date,
        CAST(MAX(obs_stop_date) AS DATE) as episode_end_date,

        -- Date source tracking
        'obs_start_date' as episode_start_date_source,
        'obs_stop_date' as episode_end_date_source,

        -- Treatment details (aggregated across course)
        SUM(obs_dose_value) as total_dose_cgy,
        AVG(obs_dose_value) as avg_dose_cgy,
        MIN(obs_dose_value) as min_dose_cgy,
        MAX(obs_dose_value) as max_dose_cgy,
        COUNT(CASE WHEN obs_dose_value IS NOT NULL THEN 1 END) as num_dose_records,

        -- Radiation fields and sites
        COUNT(DISTINCT obs_radiation_field) as num_unique_fields,
        COUNT(DISTINCT obs_radiation_site_code) as num_unique_sites,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT obs_radiation_field), ', ') as radiation_fields,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT CAST(obs_radiation_site_code AS VARCHAR)), ', ') as radiation_site_codes,

        -- Data availability flags
        CAST(MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_structured_dose,
        CAST(MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_structured_field,
        CAST(MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_structured_site,
        CAST(1 AS BOOLEAN) as has_episode_dates, -- Strategy A always has dates

        -- Source-specific dates for transparency
        MIN(obs_start_date) as obs_start_date,
        MAX(obs_stop_date) as obs_stop_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_start_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_end_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_first_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_last_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_earliest_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_latest_date

    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NOT NULL
    GROUP BY patient_fhir_id, course_id
)

SELECT
    *,
    -- Calculate episode duration
    DATE_DIFF('day', episode_start_date, episode_end_date) as episode_duration_days
FROM strategy_a_structured_episodes
ORDER BY patient_fhir_id, episode_start_datetime;

-- ============================================================================
-- STAGE 1A TESTING QUERY
-- ============================================================================
-- Run this to validate Strategy A coverage and quality
/*
SELECT
    'Strategy A: Structured Course ID' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT episode_id) as total_episodes,
    ROUND(CAST(COUNT(DISTINCT episode_id) AS DOUBLE) / COUNT(DISTINCT patient_fhir_id), 2) as avg_episodes_per_patient,
    COUNT(DISTINCT CASE WHEN has_structured_dose THEN episode_id END) as episodes_with_dose,
    COUNT(DISTINCT CASE WHEN has_structured_field THEN episode_id END) as episodes_with_field,
    COUNT(DISTINCT CASE WHEN has_structured_site THEN episode_id END) as episodes_with_site,
    COUNT(DISTINCT CASE WHEN has_episode_dates THEN episode_id END) as episodes_with_dates,
    ROUND(AVG(total_dose_cgy), 1) as avg_total_dose_cgy,
    ROUND(AVG(episode_duration_days), 1) as avg_duration_days
FROM (
    -- Insert Strategy A query here
)
*/
