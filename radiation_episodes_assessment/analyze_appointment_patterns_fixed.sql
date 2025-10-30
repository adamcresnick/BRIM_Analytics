WITH radiation_appointments AS (
    SELECT
        rta.patient_fhir_id,
        va.appointment_fhir_id,
        TRY(CAST(va.appt_start AS TIMESTAMP(3))) as appointment_start,
        va.appt_appointment_type_text,
        va.appt_description
    FROM fhir_prd_db.v_radiation_treatment_appointments rta
    INNER JOIN fhir_prd_db.v_appointments va
        ON rta.appointment_id = va.appointment_fhir_id
    WHERE va.appt_start IS NOT NULL
),
appointment_with_gaps AS (
    SELECT
        patient_fhir_id,
        appointment_start,
        appt_appointment_type_text,
        DATE_DIFF('day',
            LAG(CAST(appointment_start AS DATE))
                OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start),
            CAST(appointment_start AS DATE)
        ) as days_since_prev_appointment
    FROM radiation_appointments
)
SELECT
    CASE
        WHEN days_since_prev_appointment IS NULL THEN 'First appointment'
        WHEN days_since_prev_appointment = 0 THEN 'Same day'
        WHEN days_since_prev_appointment = 1 THEN '1 day'
        WHEN days_since_prev_appointment BETWEEN 2 AND 3 THEN '2-3 days (weekend)'
        WHEN days_since_prev_appointment BETWEEN 4 AND 7 THEN '4-7 days (weekly)'
        WHEN days_since_prev_appointment BETWEEN 8 AND 14 THEN '8-14 days'
        WHEN days_since_prev_appointment BETWEEN 15 AND 30 THEN '15-30 days (monthly)'
        WHEN days_since_prev_appointment BETWEEN 31 AND 90 THEN '31-90 days'
        WHEN days_since_prev_appointment > 90 THEN '>90 days'
    END as gap_category,
    COUNT(*) as appointment_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM appointment_with_gaps), 2) as percentage
FROM appointment_with_gaps
GROUP BY 1
ORDER BY MIN(COALESCE(days_since_prev_appointment, 0))
