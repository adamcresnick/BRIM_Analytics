-- ============================================================================
-- RADIATION EPISODES - STRATEGY B: CARE PLAN PERIODS
-- ============================================================================
-- Purpose: Create episodes from care plan period boundaries
-- Coverage: ~568 patients with radiation care plans
-- Reliability: MEDIUM-HIGH - Clinical treatment plan boundaries
-- Testing Stage: 1B
-- ============================================================================

WITH strategy_b_careplan_episodes AS (
    SELECT
        patient_fhir_id,
        care_plan_id as episode_id,
        'care_plan_period' as episode_detection_method,

        -- Episode temporal boundaries from care plan periods
        MIN(cp_period_start) as episode_start_datetime,
        MAX(cp_period_end) as episode_end_datetime,
        CAST(MIN(cp_period_start) AS DATE) as episode_start_date,
        CAST(MAX(cp_period_end) AS DATE) as episode_end_date,

        -- Date source tracking
        'cp_period_start' as episode_start_date_source,
        'cp_period_end' as episode_end_date_source,

        -- Care plan metadata
        MAX(cp_title) as cp_title,
        MAX(cp_status) as cp_status,
        MAX(cp_intent) as cp_intent,

        -- Extract site info from care plan title if possible
        MAX(cp_title) as radiation_sites_summary,

        -- Data availability flags
        CAST(0 AS BOOLEAN) as has_structured_dose,
        CAST(0 AS BOOLEAN) as has_structured_field,
        CAST(0 AS BOOLEAN) as has_structured_site,
        CAST(MAX(cp_period_start) IS NOT NULL AND MAX(cp_period_end) IS NOT NULL AS BOOLEAN) as has_episode_dates,

        -- Source-specific dates for transparency
        CAST(NULL AS TIMESTAMP(3)) as obs_start_date,
        CAST(NULL AS TIMESTAMP(3)) as obs_stop_date,
        MIN(cp_period_start) as cp_start_date,
        MAX(cp_period_end) as cp_end_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_first_date,
        CAST(NULL AS TIMESTAMP(3)) as apt_last_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_earliest_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_latest_date,

        -- No dose data for Strategy B
        CAST(NULL AS DOUBLE) as total_dose_cgy,
        CAST(NULL AS DOUBLE) as avg_dose_cgy,
        CAST(NULL AS DOUBLE) as min_dose_cgy,
        CAST(NULL AS DOUBLE) as max_dose_cgy,
        CAST(0 AS INTEGER) as num_dose_records,
        CAST(0 AS INTEGER) as num_unique_fields,
        CAST(0 AS INTEGER) as num_unique_sites,
        CAST(NULL AS VARCHAR) as radiation_fields,
        CAST(NULL AS VARCHAR) as radiation_site_codes

    FROM fhir_prd_db.v_radiation_care_plan_hierarchy
    WHERE cp_period_start IS NOT NULL AND cp_period_end IS NOT NULL
    GROUP BY patient_fhir_id, care_plan_id
)

SELECT
    *,
    -- Calculate episode duration
    DATE_DIFF('day', episode_start_date, episode_end_date) as episode_duration_days
FROM strategy_b_careplan_episodes
ORDER BY patient_fhir_id, episode_start_datetime;
