WITH radiation_appointments_from_v_appointments AS (
    SELECT
        rta.patient_fhir_id,
        va.appointment_fhir_id as appointment_id,
        TRY(CAST(va.appt_start AS TIMESTAMP(3))) as appointment_start,
        va.appt_status as appointment_status
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
strategy_c_episodes AS (
    SELECT
        patient_fhir_id,
        episode_number,
        patient_fhir_id || '_apt_episode_' || CAST(episode_number AS VARCHAR) as episode_id,
        CAST(MIN(appointment_start) AS DATE) as episode_start_date,
        CAST(MAX(appointment_start) AS DATE) as episode_end_date,
        COUNT(DISTINCT appointment_id) as num_fractions,
        DATE_DIFF('day', CAST(MIN(appointment_start) AS DATE), CAST(MAX(appointment_start) AS DATE)) as episode_duration_days
    FROM appointment_gaps
    GROUP BY patient_fhir_id, episode_number
)
SELECT
    'Strategy C: Appointment Temporal Window (v_appointments)' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT episode_id) as total_episodes,
    ROUND(CAST(COUNT(DISTINCT episode_id) AS DOUBLE) / NULLIF(COUNT(DISTINCT patient_fhir_id), 0), 2) as avg_episodes_per_patient,
    ROUND(AVG(num_fractions), 1) as avg_fractions_per_episode,
    ROUND(AVG(episode_duration_days), 1) as avg_duration_days,
    ROUND(MIN(episode_duration_days), 1) as min_duration_days,
    ROUND(MAX(episode_duration_days), 1) as max_duration_days,
    COUNT(DISTINCT CASE
        WHEN patient_fhir_id NOT IN (
            SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_radiation_treatments WHERE course_id IS NOT NULL
        ) THEN patient_fhir_id
    END) as incremental_patients_vs_strategy_a
FROM strategy_c_episodes
