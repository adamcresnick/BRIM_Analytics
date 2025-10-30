-- ============================================================================
-- RADIATION EPISODES - STRATEGY C: OBSERVATION TEMPORAL WINDOWING
-- ============================================================================
-- Purpose: Create episodes from observation temporal clustering (14-day gap)
-- Pattern: Follows chemotherapy medication_episodes temporal windowing approach
-- Coverage: Patients with radiation observations but NO structured course_id
-- Reliability: MEDIUM - Heuristic based on gap threshold
-- Testing Stage: 1C
-- ============================================================================

WITH radiation_observations_with_dates AS (
    SELECT
        patient_fhir_id,
        observation_id,

        -- Use observation effective date or issued date as primary timestamp
        COALESCE(
            obs_effective_date,
            obs_issued_date,
            obs_start_date
        ) as obs_datetime,

        -- Keep dose/field/site data for aggregation
        obs_dose_value,
        obs_dose_unit,
        obs_radiation_field,
        obs_radiation_site_code,
        obs_start_date,
        obs_stop_date,
        obs_status

    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NULL  -- Exclude patients already covered by Strategy A
      AND COALESCE(obs_effective_date, obs_issued_date, obs_start_date) IS NOT NULL
),

observation_gaps AS (
    SELECT
        patient_fhir_id,
        observation_id,
        obs_datetime,
        obs_dose_value,
        obs_dose_unit,
        obs_radiation_field,
        obs_radiation_site_code,
        obs_start_date,
        obs_stop_date,

        -- Mark new episode when gap > 14 days from previous observation
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

strategy_c_observation_episodes AS (
    SELECT
        patient_fhir_id,
        episode_number,
        patient_fhir_id || '_obs_episode_' || CAST(episode_number AS VARCHAR) as episode_id,
        'observation_temporal_window' as episode_detection_method,

        -- Episode temporal boundaries from observations
        MIN(obs_datetime) as episode_start_datetime,
        MAX(obs_datetime) as episode_end_datetime,
        CAST(MIN(obs_datetime) AS DATE) as episode_start_date,
        CAST(MAX(obs_datetime) AS DATE) as episode_end_date,

        -- Date source tracking
        'observation_effective_date' as episode_start_date_source,
        'observation_effective_date' as episode_end_date_source,

        -- Observation counts (similar to appointment fractions)
        COUNT(DISTINCT observation_id) as num_observations,

        -- Dose aggregation
        SUM(obs_dose_value) as total_dose_cgy,
        AVG(obs_dose_value) as avg_dose_cgy,
        MIN(obs_dose_value) as min_dose_cgy,
        MAX(obs_dose_value) as max_dose_cgy,
        COUNT(DISTINCT CASE WHEN obs_dose_value IS NOT NULL THEN observation_id END) as num_dose_records,

        -- Field/site aggregation
        COUNT(DISTINCT obs_radiation_field) as num_unique_fields,
        COUNT(DISTINCT obs_radiation_site_code) as num_unique_sites,
        LISTAGG(DISTINCT obs_radiation_field, ', ') WITHIN GROUP (ORDER BY obs_radiation_field) as radiation_fields,
        LISTAGG(DISTINCT CAST(obs_radiation_site_code AS VARCHAR), ', ')
            WITHIN GROUP (ORDER BY obs_radiation_site_code) as radiation_site_codes,

        -- Observation IDs for linking
        ARRAY_AGG(observation_id ORDER BY obs_datetime) as constituent_observation_ids,

        -- Data availability flags
        CAST(1 AS BOOLEAN) as has_structured_dose,
        CAST(1 AS BOOLEAN) as has_structured_field,
        CAST(1 AS BOOLEAN) as has_structured_site,
        CAST(1 AS BOOLEAN) as has_episode_dates,
        CAST(0 AS BOOLEAN) as has_appointments,

        -- Source-specific dates for transparency
        MIN(obs_start_date) as obs_first_start_date,
        MAX(obs_stop_date) as obs_last_stop_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_start_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_end_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_first_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_last_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_earliest_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_latest_date

    FROM observation_gaps
    GROUP BY patient_fhir_id, episode_number
)

SELECT
    *,
    -- Calculate episode duration
    DATE_DIFF('day', episode_start_date, episode_end_date) as episode_duration_days,

    -- Generate radiation sites summary (human-readable)
    CASE
        WHEN radiation_site_codes LIKE '%1%' THEN 'Cranial'
        WHEN radiation_site_codes LIKE '%8%' THEN 'Craniospinal'
        WHEN radiation_site_codes LIKE '%9%' THEN 'Whole Ventricular'
        WHEN radiation_site_codes LIKE '%6%' THEN 'Other Site'
        ELSE 'Unspecified'
    END as radiation_sites_summary

FROM strategy_c_observation_episodes
ORDER BY patient_fhir_id, episode_start_datetime;
