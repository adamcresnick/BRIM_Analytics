-- ============================================================================
-- RADIATION EPISODES - STRATEGY C: APPOINTMENT TEMPORAL WINDOWING (REVISED)
-- ============================================================================
-- Purpose: Create episodes from appointment temporal clustering (14-day gap)
-- Coverage: ~610 patients with radiation appointments (5,416 total appointments)
-- Reliability: MEDIUM - Heuristic based on gap threshold
-- Testing Stage: 1C
-- Data Source: v_appointments (has 100% date coverage vs 0% in v_radiation_treatment_appointments)
-- Key Fix: Use v_appointments instead of v_radiation_treatment_appointments for dates
-- ============================================================================

WITH radiation_appointments_from_v_appointments AS (
    -- Use v_appointments which has full date coverage (100% vs 0% in v_radiation_treatment_appointments)
    SELECT
        rta.patient_fhir_id,
        va.appointment_fhir_id as appointment_id,
        TRY(CAST(va.appt_start AS TIMESTAMP(3))) as appointment_start,
        TRY(CAST(va.appt_end AS TIMESTAMP(3))) as appointment_end,
        va.appt_status as appointment_status,
        va.appt_appointment_type_text as appointment_type_text,
        va.appt_description as description
    FROM fhir_prd_db.v_radiation_treatment_appointments rta
    INNER JOIN fhir_prd_db.v_appointments va
        ON rta.appointment_id = va.appointment_fhir_id
    WHERE va.appt_status IN ('booked', 'fulfilled')
      AND va.appt_start IS NOT NULL
),

appointment_gaps AS (
    SELECT
        patient_fhir_id,
        appointment_id,
        appointment_start,
        appointment_end,
        appointment_status,

        -- Mark new episode when gap > 14 days from previous appointment
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(CAST(appointment_start AS DATE))
                    OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start),
                CAST(appointment_start AS DATE)
            ) > 14 THEN 1
            ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start) as episode_number
    FROM radiation_appointments_from_v_appointments
),

strategy_c_appointment_episodes AS (
    SELECT
        patient_fhir_id,
        episode_number,
        patient_fhir_id || '_apt_episode_' || CAST(episode_number AS VARCHAR) as episode_id,
        'appointment_temporal_window' as episode_detection_method,

        -- Episode temporal boundaries from appointments
        MIN(appointment_start) as episode_start_datetime,
        MAX(appointment_start) as episode_end_datetime,
        CAST(MIN(appointment_start) AS DATE) as episode_start_date,
        CAST(MAX(appointment_start) AS DATE) as episode_end_date,

        -- Date source tracking
        'appointment_start' as episode_start_date_source,
        'appointment_start' as episode_end_date_source,

        -- Appointment counts
        COUNT(DISTINCT appointment_id) as num_fractions,
        COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) as num_fulfilled_fractions,
        COUNT(DISTINCT CASE WHEN appointment_status = 'booked' THEN appointment_id END) as num_booked_fractions,

        -- Fraction completion rate
        CAST(COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) AS DOUBLE) /
            NULLIF(COUNT(DISTINCT appointment_id), 0) as fraction_completion_rate,

        -- Appointment IDs for linking
        ARRAY_AGG(appointment_id ORDER BY appointment_start) as constituent_appointment_ids,

        -- Data availability flags
        CAST(0 AS BOOLEAN) as has_structured_dose,
        CAST(0 AS BOOLEAN) as has_structured_field,
        CAST(0 AS BOOLEAN) as has_structured_site,
        CAST(1 AS BOOLEAN) as has_episode_dates,
        CAST(1 AS BOOLEAN) as has_appointments,

        -- Source-specific dates for transparency
        CAST(NULL AS TIMESTAMP(3)) as obs_start_date,
        CAST(NULL AS TIMESTAMP(3)) as obs_stop_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_start_date,
        CAST(NULL AS TIMESTAMP(3)) as cp_end_date,
        MIN(appointment_start) as apt_first_date,
        MAX(appointment_start) as apt_last_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_earliest_date,
        CAST(NULL AS TIMESTAMP(3)) as doc_latest_date,

        -- No dose/site data for Strategy C
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

    FROM appointment_gaps
    GROUP BY patient_fhir_id, episode_number
)

SELECT
    *,
    -- Calculate episode duration
    DATE_DIFF('day', episode_start_date, episode_end_date) as episode_duration_days
FROM strategy_c_appointment_episodes
ORDER BY patient_fhir_id, episode_start_datetime;
