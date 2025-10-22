-- ================================================================================
-- v_radiation_treatment_appointments - FIXED VERSION
-- ================================================================================
-- Problem with original: Returned ALL appointments for ALL patients with no
-- radiation-specific filtering, leading to incorrect data (e.g., test patient
-- had 502 "radiation appointments" that were actually pediatric well-child visits)
--
-- Evidence of problem:
-- - Original view: 1,855 patients with appointments
-- - Actual radiation patients: 91 patients
-- - Overlap: 0 patients (complete mismatch)
--
-- Root cause: Original query:
--   SELECT * FROM appointment WHERE participant_actor_reference LIKE 'Patient/%'
--   (No radiation filtering whatsoever)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_appointments AS
WITH
-- ============================================================================
-- Patients who actually have radiation data (from any source)
-- ============================================================================
radiation_patients AS (
    -- Patients with structured ELECT data
    SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_radiation_treatments
    UNION
    -- Patients with radiation documents
    SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_radiation_documents
    UNION
    -- Patients with radiation care plans
    SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_radiation_care_plan_hierarchy
),

-- ============================================================================
-- Appointment service types that indicate radiation oncology
-- ============================================================================
radiation_service_types AS (
    SELECT DISTINCT
        appointment_id,
        service_type_coding_display
    FROM fhir_prd_db.appointment_service_type
    WHERE LOWER(service_type_coding_display) LIKE '%radiation%'
       OR LOWER(service_type_coding_display) LIKE '%rad%onc%'
       OR LOWER(service_type_coding_display) LIKE '%radiotherapy%'
),

-- ============================================================================
-- Appointment types that indicate radiation treatment
-- ============================================================================
radiation_appointment_types AS (
    SELECT DISTINCT
        appointment_id,
        appointment_type_coding_display
    FROM fhir_prd_db.appointment_appointment_type_coding
    WHERE LOWER(appointment_type_coding_display) LIKE '%radiation%'
       OR LOWER(appointment_type_coding_display) LIKE '%rad%onc%'
       OR LOWER(appointment_type_coding_display) LIKE '%radiotherapy%'
)

-- ============================================================================
-- Main query: Return appointments that are ACTUALLY radiation-related
-- ============================================================================
SELECT DISTINCT
    ap.participant_actor_reference as patient_fhir_id,
    a.id as appointment_id,
    a.status as appointment_status,
    a.appointment_type_text,
    a.priority,
    a.description,
    a.start as appointment_start,
    a."end" as appointment_end,
    a.minutes_duration,
    a.created,
    a.comment as appointment_comment,
    a.patient_instruction,

    -- Add provenance: How was this identified as radiation-related?
    CASE
        WHEN rst.appointment_id IS NOT NULL THEN 'service_type_radiation'
        WHEN rat.appointment_id IS NOT NULL THEN 'appointment_type_radiation'
        WHEN rp.patient_fhir_id IS NOT NULL
             AND (LOWER(a.comment) LIKE '%radiation%' OR LOWER(a.description) LIKE '%radiation%')
             THEN 'patient_with_radiation_data_and_radiation_keyword'
        WHEN rp.patient_fhir_id IS NOT NULL THEN 'patient_with_radiation_data_temporal_match'
        ELSE 'unknown'
    END as radiation_identification_method,

    -- Service type details
    rst.service_type_coding_display as radiation_service_type,
    rat.appointment_type_coding_display as radiation_appointment_type

FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id

-- Join to radiation-specific filters (at least one must match)
LEFT JOIN radiation_service_types rst ON a.id = rst.appointment_id
LEFT JOIN radiation_appointment_types rat ON a.id = rat.appointment_id
LEFT JOIN radiation_patients rp ON ap.participant_actor_reference = rp.patient_fhir_id

WHERE ap.participant_actor_reference LIKE 'Patient/%'
  AND (
      -- Explicit radiation service type
      rst.appointment_id IS NOT NULL

      -- Explicit radiation appointment type
      OR rat.appointment_id IS NOT NULL

      -- Patient has radiation data AND appointment mentions radiation
      OR (rp.patient_fhir_id IS NOT NULL
          AND (LOWER(a.comment) LIKE '%radiation%'
               OR LOWER(a.comment) LIKE '%rad%onc%'
               OR LOWER(a.description) LIKE '%radiation%'
               OR LOWER(a.description) LIKE '%rad%onc%'
               OR LOWER(a.patient_instruction) LIKE '%radiation%'))

      -- Conservative temporal match: Patient has radiation data + appointment during treatment window
      -- (This requires knowing the treatment dates, so we need a join to get best treatment dates)
      OR (rp.patient_fhir_id IS NOT NULL
          AND a.start IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM fhir_prd_db.v_radiation_treatments vrt
              WHERE vrt.patient_fhir_id = rp.patient_fhir_id
              AND (
                  -- Within structured treatment dates
                  (vrt.obs_start_date IS NOT NULL
                   AND vrt.obs_stop_date IS NOT NULL
                   AND a.start >= vrt.obs_start_date
                   AND a.start <= DATE_ADD('day', 30, vrt.obs_stop_date)) -- 30 day buffer
                  OR
                  -- Within service request treatment dates
                  (vrt.sr_occurrence_period_start IS NOT NULL
                   AND vrt.sr_occurrence_period_end IS NOT NULL
                   AND a.start >= vrt.sr_occurrence_period_start
                   AND a.start <= DATE_ADD('day', 30, vrt.sr_occurrence_period_end))
              )
          ))
  )

ORDER BY ap.participant_actor_reference, a.start;

-- ================================================================================
-- VALIDATION QUERIES
-- ================================================================================

-- Query 1: Verify NO general pediatric appointments (like in old view)
-- SELECT * FROM v_radiation_treatment_appointments
-- WHERE LOWER(appointment_comment) LIKE '%ear%check%'
--    OR LOWER(appointment_comment) LIKE '%well%child%'
--    OR LOWER(appointment_comment) LIKE '%fever%';
-- Expected: 0 records

-- Query 2: Count patients before/after fix
-- SELECT
--   (SELECT COUNT(DISTINCT patient_fhir_id) FROM v_radiation_treatment_appointments_OLD) as old_count,
--   (SELECT COUNT(DISTINCT patient_fhir_id) FROM v_radiation_treatment_appointments) as new_count,
--   (SELECT COUNT(DISTINCT patient_fhir_id) FROM v_radiation_treatments) as actual_radiation_patients;
-- Expected: new_count should be much closer to actual_radiation_patients

-- Query 3: Sample appointments to verify they're actually radiation-related
-- SELECT patient_fhir_id, appointment_comment, radiation_identification_method
-- FROM v_radiation_treatment_appointments
-- LIMIT 20;

-- ================================================================================
-- END OF v_radiation_treatment_appointments
-- ================================================================================
