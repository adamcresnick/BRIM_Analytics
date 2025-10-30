WITH strategy_b_episodes AS (
    SELECT
        patient_fhir_id,
        care_plan_id as episode_id,
        'care_plan_period' as episode_detection_method,
        MIN(cp_period_start) as episode_start_datetime,
        MAX(cp_period_end) as episode_end_datetime,
        CAST(MIN(cp_period_start) AS DATE) as episode_start_date,
        CAST(MAX(cp_period_end) AS DATE) as episode_end_date,
        DATE_DIFF('day', CAST(MIN(cp_period_start) AS DATE), CAST(MAX(cp_period_end) AS DATE)) as episode_duration_days
    FROM fhir_prd_db.v_radiation_care_plan_hierarchy
    WHERE cp_period_start IS NOT NULL AND cp_period_end IS NOT NULL
    GROUP BY patient_fhir_id, care_plan_id
)
SELECT
    'Strategy B: Care Plan Periods' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT episode_id) as total_episodes,
    ROUND(CAST(COUNT(DISTINCT episode_id) AS DOUBLE) / NULLIF(COUNT(DISTINCT patient_fhir_id), 0), 2) as avg_episodes_per_patient,
    COUNT(DISTINCT CASE WHEN episode_start_date IS NOT NULL THEN episode_id END) as episodes_with_dates,
    ROUND(AVG(episode_duration_days), 1) as avg_duration_days,
    ROUND(MIN(episode_duration_days), 1) as min_duration_days,
    ROUND(MAX(episode_duration_days), 1) as max_duration_days,
    COUNT(DISTINCT CASE
        WHEN patient_fhir_id NOT IN (
            SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_radiation_treatments WHERE course_id IS NOT NULL
        ) THEN patient_fhir_id
    END) as incremental_patients_vs_strategy_a
FROM strategy_b_episodes
