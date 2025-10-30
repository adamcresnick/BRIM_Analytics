WITH radiation_observations_with_dates AS (
    SELECT
        patient_fhir_id,
        observation_id,
        COALESCE(
            obs_effective_date,
            obs_issued_date,
            obs_start_date
        ) as obs_datetime,
        obs_dose_value,
        obs_radiation_field,
        obs_radiation_site_code
    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NULL
      AND COALESCE(obs_effective_date, obs_issued_date, obs_start_date) IS NOT NULL
),
observation_gaps AS (
    SELECT
        patient_fhir_id,
        observation_id,
        obs_datetime,
        obs_dose_value,
        obs_radiation_field,
        obs_radiation_site_code,
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(CAST(obs_datetime AS DATE))
                    OVER (PARTITION BY patient_fhir_id ORDER BY obs_datetime),
                CAST(obs_datetime AS DATE)
            ) > 14 THEN 1
            ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY obs_datetime) as episode_number
    FROM radiation_observations_with_dates
),
strategy_c_episodes AS (
    SELECT
        patient_fhir_id,
        episode_number,
        patient_fhir_id || '_obs_episode_' || CAST(episode_number AS VARCHAR) as episode_id,
        CAST(MIN(obs_datetime) AS DATE) as episode_start_date,
        CAST(MAX(obs_datetime) AS DATE) as episode_end_date,
        COUNT(DISTINCT observation_id) as num_observations,
        DATE_DIFF('day', CAST(MIN(obs_datetime) AS DATE), CAST(MAX(obs_datetime) AS DATE)) as episode_duration_days,
        SUM(obs_dose_value) as total_dose_cgy,
        COUNT(DISTINCT obs_radiation_field) as num_unique_fields,
        COUNT(DISTINCT obs_radiation_site_code) as num_unique_sites
    FROM observation_gaps
    GROUP BY patient_fhir_id, episode_number
)
SELECT
    'Strategy C: Observation Temporal Window' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT episode_id) as total_episodes,
    ROUND(CAST(COUNT(DISTINCT episode_id) AS DOUBLE) / NULLIF(COUNT(DISTINCT patient_fhir_id), 0), 2) as avg_episodes_per_patient,
    ROUND(AVG(num_observations), 1) as avg_observations_per_episode,
    ROUND(AVG(total_dose_cgy), 1) as avg_total_dose_cgy,
    ROUND(AVG(episode_duration_days), 1) as avg_duration_days,
    ROUND(MIN(episode_duration_days), 1) as min_duration_days,
    ROUND(MAX(episode_duration_days), 1) as max_duration_days,
    COUNT(DISTINCT CASE
        WHEN patient_fhir_id NOT IN (
            SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_radiation_treatments WHERE course_id IS NOT NULL
        ) THEN patient_fhir_id
    END) as incremental_patients_vs_strategy_a
FROM strategy_c_episodes
