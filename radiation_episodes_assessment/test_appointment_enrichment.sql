WITH episode_base AS (
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
    SELECT
        rta.patient_fhir_id,
        va.appointment_fhir_id as appointment_id,
        CAST(va.appointment_date AS DATE) as appointment_date,
        va.appt_status as appointment_status
    FROM fhir_prd_db.v_radiation_treatment_appointments rta
    INNER JOIN fhir_prd_db.v_appointments va
        ON rta.appointment_id = va.appointment_fhir_id
),
appointment_episode_linkage AS (
    SELECT
        eb.patient_fhir_id,
        eb.episode_id,
        awd.appointment_id,
        awd.appointment_date,
        awd.appointment_status,
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
            ELSE 'unrelated'
        END as appointment_phase
    FROM episode_base eb
    INNER JOIN appointments_with_dates awd
        ON eb.patient_fhir_id = awd.patient_fhir_id
    WHERE awd.appointment_date BETWEEN DATE_ADD('day', -365, eb.episode_start_date)
                                   AND DATE_ADD('day', 365, eb.episode_end_date)
)
SELECT
    COUNT(DISTINCT patient_fhir_id) as patients_with_appointments,
    COUNT(DISTINCT episode_id) as episodes_with_appointments,
    COUNT(DISTINCT appointment_id) as total_appointments_linked,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'pre_treatment' THEN appointment_id END) as pre_treatment_appts,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'during_treatment' THEN appointment_id END) as during_treatment_appts,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'post_treatment' THEN appointment_id END) as post_treatment_appts,
    COUNT(DISTINCT CASE WHEN appointment_phase = 'early_followup' THEN appointment_id END) as early_followup_appts,
    ROUND(AVG(CASE WHEN appointment_phase != 'unrelated' THEN 1.0 ELSE 0 END) * 100, 1) as pct_appointments_linked
FROM appointment_episode_linkage
