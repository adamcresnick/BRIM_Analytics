WITH strategy_a_episodes AS (
    SELECT
        patient_fhir_id,
        course_id as episode_id,
        'structured_course_id' as episode_detection_method,
        MIN(obs_start_date) as episode_start_datetime,
        MAX(obs_stop_date) as episode_end_datetime,
        CAST(MIN(obs_start_date) AS DATE) as episode_start_date,
        CAST(MAX(obs_stop_date) AS DATE) as episode_end_date,
        SUM(obs_dose_value) as total_dose_cgy,
        COUNT(CASE WHEN obs_dose_value IS NOT NULL THEN 1 END) as num_dose_records,
        CAST(MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_structured_dose,
        CAST(MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_structured_field,
        CAST(MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_structured_site,
        DATE_DIFF('day', CAST(MIN(obs_start_date) AS DATE), CAST(MAX(obs_stop_date) AS DATE)) as episode_duration_days
    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NOT NULL
    GROUP BY patient_fhir_id, course_id
)
SELECT
    'Strategy A: Structured Course ID' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT episode_id) as total_episodes,
    ROUND(CAST(COUNT(DISTINCT episode_id) AS DOUBLE) / NULLIF(COUNT(DISTINCT patient_fhir_id), 0), 2) as avg_episodes_per_patient,
    COUNT(DISTINCT CASE WHEN has_structured_dose THEN episode_id END) as episodes_with_dose,
    COUNT(DISTINCT CASE WHEN has_structured_field THEN episode_id END) as episodes_with_field,
    COUNT(DISTINCT CASE WHEN has_structured_site THEN episode_id END) as episodes_with_site,
    COUNT(DISTINCT CASE WHEN episode_start_date IS NOT NULL THEN episode_id END) as episodes_with_dates,
    ROUND(AVG(total_dose_cgy), 1) as avg_total_dose_cgy,
    ROUND(MIN(total_dose_cgy), 1) as min_total_dose_cgy,
    ROUND(MAX(total_dose_cgy), 1) as max_total_dose_cgy,
    ROUND(AVG(episode_duration_days), 1) as avg_duration_days,
    ROUND(MIN(episode_duration_days), 1) as min_duration_days,
    ROUND(MAX(episode_duration_days), 1) as max_duration_days,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN has_structured_dose THEN episode_id END) / NULLIF(COUNT(DISTINCT episode_id), 0), 1) as pct_with_dose,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN has_structured_field THEN episode_id END) / NULLIF(COUNT(DISTINCT episode_id), 0), 1) as pct_with_field,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN has_structured_site THEN episode_id END) / NULLIF(COUNT(DISTINCT episode_id), 0), 1) as pct_with_site
FROM strategy_a_episodes
