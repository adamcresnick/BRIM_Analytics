-- ============================================================================
-- RADIATION EPISODE APPOINTMENT ENRICHMENT (Revised Strategy C)
-- ============================================================================
-- Purpose: Link appointments to episodes for metadata enrichment
-- Approach: Join v_appointments to episodes based on temporal proximity
-- Use Case: Enrich episodes with appointment counts, fulfillment rates, visit types
--
-- Key Insight: Appointments are clinic visits/consultations, NOT daily fractions
-- Therefore: Use for metadata enrichment, NOT episode detection
-- ============================================================================

WITH episode_base AS (
    -- Get episodes from Strategy A (structured course_id)
    SELECT
        patient_fhir_id,
        course_id as episode_id,
        MIN(obs_start_date) as episode_start_date,
        MAX(obs_stop_date) as episode_end_date
    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NOT NULL
    GROUP BY patient_fhir_id, course_id
),

appointments_with_dates AS (
    -- Get radiation appointments with full dates from v_appointments
    SELECT
        rta.patient_fhir_id,
        va.appointment_fhir_id as appointment_id,
        CAST(va.appointment_date AS DATE) as appointment_date,
        TRY(CAST(va.appt_start AS TIMESTAMP(3))) as appointment_start,
        TRY(CAST(va.appt_end AS TIMESTAMP(3))) as appointment_end,
        va.appt_status as appointment_status,
        va.appt_appointment_type_text as appointment_type,
        va.appt_description as description,
        va.appt_comment as comment,
        va.appt_cancelation_reason_text as cancelation_reason
    FROM fhir_prd_db.v_radiation_treatment_appointments rta
    INNER JOIN fhir_prd_db.v_appointments va
        ON rta.appointment_id = va.appointment_fhir_id
),

appointment_episode_linkage AS (
    -- Link appointments to episodes based on temporal proximity
    -- Appointment is linked to episode if it falls within episode dates ± 30 day window
    SELECT
        eb.patient_fhir_id,
        eb.episode_id,
        eb.episode_start_date,
        eb.episode_end_date,

        awd.appointment_id,
        awd.appointment_date,
        awd.appointment_start,
        awd.appointment_end,
        awd.appointment_status,
        awd.appointment_type,
        awd.description,
        awd.comment,
        awd.cancelation_reason,

        -- Calculate temporal relationship to episode
        DATE_DIFF('day', awd.appointment_date, eb.episode_start_date) as days_before_episode_start,
        DATE_DIFF('day', eb.episode_end_date, awd.appointment_date) as days_after_episode_end,

        -- Classify appointment timing relative to episode
        CASE
            WHEN awd.appointment_date < eb.episode_start_date
                AND DATE_DIFF('day', awd.appointment_date, eb.episode_start_date) <= 30
                THEN 'pre_treatment'
            WHEN awd.appointment_date BETWEEN eb.episode_start_date AND eb.episode_end_date
                THEN 'during_treatment'
            WHEN awd.appointment_date > eb.episode_end_date
                AND DATE_DIFF('day', eb.episode_end_date, awd.appointment_date) <= 30
                THEN 'post_treatment'
            WHEN awd.appointment_date > eb.episode_end_date
                AND DATE_DIFF('day', eb.episode_end_date, awd.appointment_date) <= 90
                THEN 'early_followup'
            WHEN awd.appointment_date > eb.episode_end_date
                AND DATE_DIFF('day', eb.episode_end_date, awd.appointment_date) <= 365
                THEN 'late_followup'
            ELSE 'unrelated'
        END as appointment_phase

    FROM episode_base eb
    INNER JOIN appointments_with_dates awd
        ON eb.patient_fhir_id = awd.patient_fhir_id
    WHERE
        -- Only link appointments within ±1 year of episode
        awd.appointment_date BETWEEN DATE_ADD('day', -365, eb.episode_start_date)
                                 AND DATE_ADD('day', 365, eb.episode_end_date)
)

SELECT
    patient_fhir_id,
    episode_id,

    -- Episode temporal boundaries
    episode_start_date,
    episode_end_date,

    -- Appointment counts by phase
    COUNT(DISTINCT appointment_id) as total_appointments,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'pre_treatment' THEN appointment_id END) as pre_treatment_appointments,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'during_treatment' THEN appointment_id END) as during_treatment_appointments,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'post_treatment' THEN appointment_id END) as post_treatment_appointments,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'early_followup' THEN appointment_id END) as early_followup_appointments,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'late_followup' THEN appointment_id END) as late_followup_appointments,

    -- Appointment status counts
    COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) as fulfilled_appointments,
    COUNT(DISTINCT CASE WHEN appointment_status = 'booked' THEN appointment_id END) as booked_appointments,
    COUNT(DISTINCT CASE WHEN appointment_status = 'cancelled' THEN appointment_id END) as cancelled_appointments,
    COUNT(DISTINCT CASE WHEN appointment_status = 'noshow' THEN appointment_id END) as noshow_appointments,

    -- Fulfillment rate
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) AS DOUBLE) /
        NULLIF(COUNT(DISTINCT appointment_id), 0) * 100,
        1
    ) as appointment_fulfillment_rate_pct,

    -- Appointment types (aggregated)
    ARRAY_AGG(DISTINCT appointment_type) FILTER (WHERE appointment_type IS NOT NULL) as appointment_types,

    -- First and last appointment dates
    MIN(appointment_date) as first_appointment_date,
    MAX(appointment_date) as last_appointment_date,

    -- Appointment IDs for linking
    ARRAY_AGG(appointment_id ORDER BY appointment_date) as linked_appointment_ids

FROM appointment_episode_linkage
WHERE appointment_phase != 'unrelated'
GROUP BY
    patient_fhir_id,
    episode_id,
    episode_start_date,
    episode_end_date
ORDER BY patient_fhir_id, episode_start_date;
