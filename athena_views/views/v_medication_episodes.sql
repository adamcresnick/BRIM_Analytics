-- ============================================================================
-- VIEW: v_medication_episodes
-- PURPOSE: Group individual medication administrations into treatment episodes
-- DATE: 2025-10-28
--
-- APPROACH: Temporal windowing (gap-based episode detection)
-- - Gap > 21 days between same medication → new episode
-- - Groups by patient + medication name
-- - Provides episode-level spans for layered timeline visualization
--
-- USE CASE: Layered timeline showing treatment episode spans overlaying
--           individual medication administration events
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_medication_episodes AS
WITH

-- ============================================================================
-- Step 1: Get all chemotherapy medications with start/stop dates
-- ============================================================================
medications_with_dates AS (
    SELECT
        patient_fhir_id,
        medication_request_fhir_id,
        chemo_preferred_name as medication_name,
        chemo_drug_category,

        -- Parse dates
        TRY(FROM_ISO8601_TIMESTAMP(medication_start_date)) as med_start,
        TRY(FROM_ISO8601_TIMESTAMP(medication_stop_date)) as med_stop,

        -- Fallback: if no stop date, use start date + 1 day (single administration)
        COALESCE(
            TRY(FROM_ISO8601_TIMESTAMP(medication_stop_date)),
            DATE_ADD('day', 1, TRY(FROM_ISO8601_TIMESTAMP(medication_start_date)))
        ) as med_stop_adjusted,

        medication_status,
        encounter_fhir_id,

        -- CarePlan fields (for future when data is available)
        cp_id,
        cp_title,
        cp_period_start,
        cp_period_end

    FROM fhir_prd_db.v_chemo_medications
    WHERE medication_start_date IS NOT NULL
),

-- ============================================================================
-- Step 2: Detect episode boundaries using temporal gaps
-- Gap > 21 days = new episode (allows for typical chemo cycle gaps)
-- ============================================================================
medications_with_episode_markers AS (
    SELECT
        *,
        -- Calculate days since previous medication administration
        DATE_DIFF('day',
            LAG(med_stop_adjusted) OVER (
                PARTITION BY patient_fhir_id, medication_name
                ORDER BY med_start
            ),
            med_start
        ) as days_since_last_med,

        -- Mark new episode when gap > 21 days
        CASE
            WHEN LAG(med_stop_adjusted) OVER (
                PARTITION BY patient_fhir_id, medication_name
                ORDER BY med_start
            ) IS NULL THEN 1  -- First medication = episode 1
            WHEN DATE_DIFF('day',
                LAG(med_stop_adjusted) OVER (
                    PARTITION BY patient_fhir_id, medication_name
                    ORDER BY med_start
                ),
                med_start
            ) > 21 THEN 1  -- Gap > 21 days = new episode
            ELSE 0  -- Continue current episode
        END as is_new_episode
    FROM medications_with_dates
),

-- ============================================================================
-- Step 3: Assign episode numbers
-- ============================================================================
medications_with_episode_numbers AS (
    SELECT
        *,
        -- Running sum of episode markers creates episode number
        SUM(is_new_episode) OVER (
            PARTITION BY patient_fhir_id, medication_name
            ORDER BY med_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) as episode_number
    FROM medications_with_episode_markers
),

-- ============================================================================
-- Step 4: Aggregate medications into episodes
-- ============================================================================
medication_episodes AS (
    SELECT
        patient_fhir_id,
        medication_name,
        episode_number,

        -- Episode ID
        patient_fhir_id || '_' ||
        REPLACE(medication_name, ' ', '_') || '_ep' ||
        CAST(episode_number AS VARCHAR) as episode_id,

        -- Episode boundaries
        MIN(med_start) as episode_start_date,
        MAX(med_stop_adjusted) as episode_end_date,

        -- Episode duration
        DATE_DIFF('day', MIN(med_start), MAX(med_stop_adjusted)) as episode_duration_days,

        -- Medication counts
        COUNT(DISTINCT medication_request_fhir_id) as total_administrations,
        COUNT(DISTINCT encounter_fhir_id) as total_encounters,

        -- Episode metadata
        MAX(chemo_drug_category) as drug_category,
        MAX(medication_status) as latest_status,

        -- Aggregated medication IDs for drill-down
        ARRAY_AGG(medication_request_fhir_id ORDER BY med_start) as medication_request_ids,
        ARRAY_AGG(CAST(med_start AS VARCHAR) ORDER BY med_start) as administration_dates,

        -- CarePlan linkage (for future when available)
        MAX(cp_id) as careplan_id,
        MAX(cp_title) as careplan_title,

        -- Episode grouping method
        'temporal_window_21day_gap' as episode_grouping_method

    FROM medications_with_episode_numbers
    GROUP BY patient_fhir_id, medication_name, episode_number
)

-- ============================================================================
-- Final SELECT: Return all episode information
-- ============================================================================
SELECT
    -- Patient identifier
    patient_fhir_id,

    -- Episode identifiers
    episode_id,
    episode_number,

    -- Medication information
    medication_name,
    drug_category,

    -- Episode temporal boundaries (for timeline span visualization)
    episode_start_date,
    episode_end_date,
    episode_duration_days,

    -- Episode statistics
    total_administrations,
    total_encounters,

    -- Episode status
    latest_status,

    -- Aggregated references (for drill-down to individual medications)
    medication_request_ids,
    administration_dates,

    -- CarePlan linkage (NULL for now, will populate when data available)
    careplan_id,
    careplan_title,

    -- Provenance
    episode_grouping_method,

    -- Age at episode (calculated from patient birth date if needed)
    CAST(NULL AS DOUBLE) as age_at_episode_start_years

FROM medication_episodes
ORDER BY patient_fhir_id, episode_start_date, medication_name;

-- ============================================================================
-- USAGE EXAMPLE: Query episodes for layered timeline
-- ============================================================================
/*
SELECT
    patient_fhir_id,
    medication_name,
    episode_start_date,
    episode_end_date,
    total_administrations,
    episode_duration_days
FROM fhir_prd_db.v_medication_episodes
WHERE patient_fhir_id = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY episode_start_date;
*/

-- ============================================================================
-- VALIDATION QUERY: Episode quality metrics
-- ============================================================================
/*
SELECT
    medication_name,
    COUNT(DISTINCT episode_id) as total_episodes,
    COUNT(DISTINCT patient_fhir_id) as total_patients,
    ROUND(AVG(episode_duration_days), 1) as avg_episode_duration_days,
    ROUND(AVG(total_administrations), 1) as avg_administrations_per_episode,
    MIN(episode_duration_days) as min_duration,
    MAX(episode_duration_days) as max_duration
FROM fhir_prd_db.v_medication_episodes
GROUP BY medication_name
ORDER BY total_episodes DESC
LIMIT 20;
*/
