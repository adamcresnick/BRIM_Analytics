CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_summary AS
WITH radiation_courses AS (
    SELECT
        patient_fhir_id,
        obs_start_date as start_date,
        obs_stop_date as stop_date,
        obs_radiation_field as radiation_field,
        obs_dose_value as dose_value,
        obs_dose_unit as dose_unit,
        TRY_CAST(REGEXP_EXTRACT(obs_course_line_number, '[0-9]+', 0) AS INTEGER) as course_number,
        obs_status,
        obs_effective_date
    FROM fhir_prd_db.v_radiation_treatments
    WHERE obs_start_date IS NOT NULL
),
course_1_data AS (
    SELECT
        patient_fhir_id,
        MIN(DATE(start_date)) as course_1_start_date,
        MAX(DATE(stop_date)) as course_1_end_date,
        CAST(DATE_DIFF('day',
            MIN(DATE(start_date)),
            MAX(DATE(stop_date))
        ) / 7.0 AS DOUBLE) as course_1_duration_weeks,
        LISTAGG(DISTINCT radiation_field, ', ') WITHIN GROUP (ORDER BY radiation_field) as treatment_techniques,
        COUNT(DISTINCT obs_effective_date) as num_observations
    FROM radiation_courses
    WHERE course_number = 1 OR course_number IS NULL
    GROUP BY patient_fhir_id
),
re_irradiation_check AS (
    SELECT
        patient_fhir_id,
        CASE
            WHEN MAX(course_number) > 1 THEN 'Yes'
            WHEN COUNT(DISTINCT course_number) > 1 THEN 'Yes'
            ELSE 'No'
        END as re_irradiation
    FROM radiation_courses
    GROUP BY patient_fhir_id
),
appointment_counts AS (
    SELECT
        patient_fhir_id,
        COUNT(*) as num_radiation_appointments
    FROM fhir_prd_db.v_radiation_treatment_appointments
    GROUP BY patient_fhir_id
)
SELECT
    c1.patient_fhir_id,
    c1.course_1_start_date,
    c1.course_1_end_date,
    c1.course_1_duration_weeks,
    COALESCE(ri.re_irradiation, 'No') as re_irradiation,
    c1.treatment_techniques,
    COALESCE(ac.num_radiation_appointments, 0) as num_radiation_appointments
FROM course_1_data c1
LEFT JOIN re_irradiation_check ri ON c1.patient_fhir_id = ri.patient_fhir_id
LEFT JOIN appointment_counts ac ON c1.patient_fhir_id = ac.patient_fhir_id
WHERE c1.course_1_start_date IS NOT NULL
