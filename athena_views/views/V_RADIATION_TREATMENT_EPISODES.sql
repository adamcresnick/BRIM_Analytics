-- ================================================================================
-- V_RADIATION_TREATMENT_EPISODES
-- ================================================================================
-- Purpose: Group radiation treatments into logical episodes for analysis
--
-- Episode Construction Strategy (adapted for radiation data):
--   - PRIMARY GROUPING: course_id (100% coverage - each course is one episode)
--   - DATES: Use cp_first_start_date/cp_last_end_date (64.8% coverage) as fallback
--            since obs_start_date/obs_stop_date have 0% coverage
--   - One row per episode (course), aggregating treatment details
--
-- Key Differences from Chemotherapy Episodes:
--   - Chemotherapy: Groups by encounter (medications given during same encounter)
--   - Radiation: Groups by course_id (explicit radiation course numbering from ELECT)
--
-- Data Quality Notes:
--   - Excellent: 97%+ coverage for dose, field, site details
--   - Limited: 0% obs date coverage, 64.8% care plan date coverage
--   - Strategy: Accept that ~35% of episodes will have NULL dates
--
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_episodes AS

SELECT
    -- ========================================================================
    -- EPISODE IDENTIFIERS
    -- ========================================================================
    course_id as episode_id,
    patient_fhir_id,

    -- Episode type classification
    CASE
        WHEN COUNT(CASE WHEN obs_dose_value IS NOT NULL THEN 1 END) > 0 THEN 'STRUCTURED_ELECT'
        WHEN COUNT(CASE WHEN sr_status IS NOT NULL THEN 1 END) > 0 THEN 'SERVICE_REQUEST_BASED'
        ELSE 'UNGROUPED'
    END as episode_data_type,

    -- ========================================================================
    -- EPISODE TEMPORAL BOUNDARIES
    -- ========================================================================
    -- Use care plan dates as best available (obs dates are 0% populated)
    MIN(cp_first_start_date) as episode_start_date,
    MIN(CAST(cp_first_start_date AS TIMESTAMP)) as episode_start_datetime,
    MAX(cp_last_end_date) as episode_end_date,
    MAX(CAST(cp_last_end_date AS TIMESTAMP)) as episode_end_datetime,

    -- Episode duration (in days, NULL if dates missing)
    DATE_DIFF('day',
        MIN(cp_first_start_date),
        MAX(cp_last_end_date)
    ) as episode_duration_days,

    -- ========================================================================
    -- DOSE SUMMARY (97% coverage)
    -- ========================================================================
    SUM(obs_dose_value) as total_dose_cgy,
    AVG(obs_dose_value) as avg_dose_cgy,
    MIN(obs_dose_value) as min_dose_cgy,
    MAX(obs_dose_value) as max_dose_cgy,
    COUNT(CASE WHEN obs_dose_value IS NOT NULL THEN 1 END) as num_dose_records,

    -- ========================================================================
    -- RADIATION SITES/FIELDS (97% coverage)
    -- ========================================================================
    COUNT(DISTINCT obs_radiation_field) as num_unique_fields,
    COUNT(DISTINCT obs_radiation_site_code) as num_unique_sites,
    ARRAY_JOIN(ARRAY_AGG(DISTINCT obs_radiation_field), ', ') as radiation_fields,
    ARRAY_JOIN(ARRAY_AGG(DISTINCT CAST(obs_radiation_site_code AS VARCHAR)), ', ') as radiation_site_codes,

    -- ========================================================================
    -- APPOINTMENT SUMMARY (0% in current data, but keep for future)
    -- ========================================================================
    MAX(apt_total_appointments) as total_appointments,
    MAX(apt_fulfilled_appointments) as fulfilled_appointments,
    MAX(apt_cancelled_appointments) as cancelled_appointments,
    MIN(apt_first_appointment_date) as first_appointment_date,
    MAX(apt_last_appointment_date) as last_appointment_date,

    -- ========================================================================
    -- DATA SOURCE COUNTS
    -- ========================================================================
    COUNT(DISTINCT CASE WHEN obs_dose_value IS NOT NULL THEN course_id END) as num_observations,
    COUNT(DISTINCT CASE WHEN sr_status IS NOT NULL THEN course_id END) as num_service_requests,
    MAX(cp_total_care_plans) as num_care_plans,

    -- ========================================================================
    -- DATA AVAILABILITY FLAGS
    -- ========================================================================
    CAST(MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_dose_data,
    CAST(MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_field_data,
    CAST(MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_site_data,
    CAST(MAX(CASE WHEN cp_first_start_date IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_episode_dates,
    CAST(MAX(CASE WHEN apt_total_appointments > 0 THEN 1 ELSE 0 END) AS BOOLEAN) as has_appointments,

    -- Data completeness indicator (dose + field + site + dates)
    CASE
        WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN cp_first_start_date IS NOT NULL THEN 1 ELSE 0 END) = 1
        THEN true
        ELSE false
    END as has_complete_structured_data,

    -- ========================================================================
    -- CARE PLAN METADATA (for context)
    -- ========================================================================
    MAX(cp_titles) as episode_care_plan_titles,
    MAX(cp_statuses) as episode_care_plan_statuses,

    -- ========================================================================
    -- SERVICE REQUEST METADATA (for context)
    -- ========================================================================
    ARRAY_JOIN(ARRAY_AGG(DISTINCT sr_code_text), ' | ') as episode_service_request_codes,

    -- ========================================================================
    -- DATA QUALITY SCORE (0.0 to 1.0)
    -- ========================================================================
    -- Weighted by importance: dates (30%), dose (25%), field (25%), site (20%)
    CAST((
        (CASE WHEN MAX(CASE WHEN cp_first_start_date IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.30 ELSE 0.0 END) +
        (CASE WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.25 ELSE 0.0 END) +
        (CASE WHEN MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.25 ELSE 0.0 END) +
        (CASE WHEN MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.20 ELSE 0.0 END)
    ) AS DOUBLE) as episode_data_quality_score,

    -- Data quality tier (for filtering/prioritization)
    CASE
        WHEN CAST((
            (CASE WHEN MAX(CASE WHEN cp_first_start_date IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.30 ELSE 0.0 END) +
            (CASE WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.20 ELSE 0.0 END)
        ) AS DOUBLE) >= 0.80 THEN 'HIGH'
        WHEN CAST((
            (CASE WHEN MAX(CASE WHEN cp_first_start_date IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.30 ELSE 0.0 END) +
            (CASE WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) = 1 THEN 0.20 ELSE 0.0 END)
        ) AS DOUBLE) >= 0.50 THEN 'MEDIUM'
        ELSE 'LOW'
    END as data_quality_tier,

    -- ========================================================================
    -- RECOMMENDED ANALYSIS STRATEGY
    -- ========================================================================
    CASE
        -- Best case: Have all structured data (dose, field, site) + dates
        WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN cp_first_start_date IS NOT NULL THEN 1 ELSE 0 END) = 1
        THEN 'DIRECT_ANALYSIS_READY'

        -- Good case: Have treatment details but missing dates
        WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1
             AND MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1
        THEN 'ANALYSIS_READY_NO_DATES'

        -- Moderate case: Have some data but incomplete
        WHEN MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) = 1
             OR MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) = 1
        THEN 'PARTIAL_DATA_AVAILABLE'

        ELSE 'INSUFFICIENT_DATA'
    END as recommended_analysis_approach

FROM fhir_prd_db.v_radiation_treatments

WHERE course_id IS NOT NULL  -- Only episodes with course IDs

GROUP BY
    course_id,
    patient_fhir_id

ORDER BY
    episode_data_quality_score DESC,
    patient_fhir_id,
    episode_id;

-- ================================================================================
-- USAGE NOTES
-- ================================================================================
-- This view creates one row per radiation episode (course).
--
-- Key Characteristics of Radiation Episodes (vs Chemotherapy):
--   1. Grouping: By course_id (not encounter) - radiation courses are explicitly numbered
--   2. Dates: From care plans (64.8% coverage) - obs dates unavailable (0% coverage)
--   3. Details: Excellent coverage for dose/field/site (97%+)
--
-- Filtering Recommendations:
--   - For temporal analysis: WHERE has_episode_dates = true (64.8% of episodes)
--   - For dose analysis: WHERE has_dose_data = true (97% of episodes)
--   - For high quality: WHERE data_quality_tier = 'HIGH' or data_quality_score >= 0.8
--
-- ================================================================================
-- EXAMPLE QUERIES
-- ================================================================================
--
-- Example 1: Episodes ready for full analysis (dates + treatment details)
-- SELECT * FROM v_radiation_treatment_episodes
-- WHERE recommended_analysis_approach = 'DIRECT_ANALYSIS_READY';
--
-- Example 2: Episodes with treatment details but no dates
-- SELECT * FROM v_radiation_treatment_episodes
-- WHERE recommended_analysis_approach = 'ANALYSIS_READY_NO_DATES';
--
-- Example 3: Patient-level radiation summary
-- SELECT
--     patient_fhir_id,
--     COUNT(*) as total_episodes,
--     SUM(total_dose_cgy) as cumulative_dose_cgy,
--     MIN(episode_start_date) as first_radiation_date,
--     MAX(episode_end_date) as last_radiation_date,
--     AVG(episode_data_quality_score) as avg_data_quality
-- FROM v_radiation_treatment_episodes
-- GROUP BY patient_fhir_id;
--
-- Example 4: Data quality distribution
-- SELECT
--     data_quality_tier,
--     COUNT(*) as episode_count,
--     AVG(episode_duration_days) as avg_duration_days,
--     AVG(total_dose_cgy) as avg_total_dose,
--     SUM(CASE WHEN has_episode_dates THEN 1 ELSE 0 END) as episodes_with_dates
-- FROM v_radiation_treatment_episodes
-- GROUP BY data_quality_tier
-- ORDER BY
--     CASE data_quality_tier
--         WHEN 'HIGH' THEN 1
--         WHEN 'MEDIUM' THEN 2
--         WHEN 'LOW' THEN 3
--     END;
--
-- ================================================================================
-- END OF v_radiation_treatment_episodes
-- ================================================================================
