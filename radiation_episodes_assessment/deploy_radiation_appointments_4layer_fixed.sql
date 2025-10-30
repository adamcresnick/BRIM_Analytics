-- ================================================================================
-- v_radiation_treatment_appointments - CORRECTED 4-LAYER VERSION
-- ================================================================================
-- Fix: Restore Layer 4 (temporal matching) with proper VARCHAR-to-TIMESTAMP casting
-- Investigation findings:
-- - Layers 1 & 2: 0% matches (confirmed correct - no radiation keywords in metadata)
-- - Layer 3: 535 appointments with "radiation" in comment field
-- - appointment.start: VARCHAR type in ISO 8601 format
-- - Proper casting: TRY_CAST(a.start AS TIMESTAMP)
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
-- Radiation treatment date ranges for temporal matching (Layer 4)
-- ============================================================================
radiation_treatment_dates AS (
    SELECT
        patient_fhir_id,
        -- Use structured observation dates (obs_start_date, obs_stop_date)
        TRY_CAST(obs_start_date AS TIMESTAMP) as treatment_start,
        TRY_CAST(DATE_ADD('day', 30, CAST(obs_stop_date AS DATE)) AS TIMESTAMP) as treatment_end_plus_30,
        -- Use service request dates as fallback
        TRY_CAST(sr_occurrence_period_start AS TIMESTAMP) as sr_start,
        TRY_CAST(DATE_ADD('day', 30, CAST(sr_occurrence_period_end AS DATE)) AS TIMESTAMP) as sr_end_plus_30
    FROM fhir_prd_db.v_radiation_treatments
    WHERE obs_start_date IS NOT NULL
       OR sr_occurrence_period_start IS NOT NULL
),

-- ============================================================================
-- Appointment service types that indicate radiation oncology (Layer 1)
-- ============================================================================
radiation_service_types AS (
    SELECT DISTINCT
        appointment_id,
        service_type_text
    FROM fhir_prd_db.appointment_service_type
    WHERE service_type_text IS NOT NULL
      AND (
          LOWER(service_type_text) LIKE '%radiation%'
          OR LOWER(service_type_text) LIKE '%radiotherapy%'
          OR LOWER(service_type_text) LIKE '%rad%onc%'
          OR LOWER(service_type_text) LIKE '%radonc%'
          OR LOWER(service_type_text) LIKE '%radionc%'
          OR LOWER(service_type_text) LIKE '%xrt%'
          OR LOWER(service_type_text) LIKE '%imrt%'
          OR LOWER(service_type_text) LIKE '%vmat%'
          OR LOWER(service_type_text) LIKE '%igrt%'
          OR LOWER(service_type_text) LIKE '%sbrt%'
          OR LOWER(service_type_text) LIKE '%brachytherapy%'
      )
),

-- ============================================================================
-- Appointment types that indicate radiation treatment (Layer 2)
-- ============================================================================
radiation_appointment_types AS (
    SELECT DISTINCT
        appointment_id,
        appointment_type_coding_display
    FROM fhir_prd_db.appointment_appointment_type_coding
    WHERE appointment_type_coding_display IS NOT NULL
      AND (
          LOWER(appointment_type_coding_display) LIKE '%radiation%'
          OR LOWER(appointment_type_coding_display) LIKE '%radiotherapy%'
          OR LOWER(appointment_type_coding_display) LIKE '%rad%onc%'
          OR LOWER(appointment_type_coding_display) LIKE '%radonc%'
          OR LOWER(appointment_type_coding_display) LIKE '%radionc%'
          OR LOWER(appointment_type_coding_display) LIKE '%xrt%'
          OR LOWER(appointment_type_coding_display) LIKE '%imrt%'
          OR LOWER(appointment_type_coding_display) LIKE '%vmat%'
      )
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
    TRY_CAST(a.start AS TIMESTAMP) as appointment_start,
    TRY_CAST(a."end" AS TIMESTAMP) as appointment_end,
    a.minutes_duration,
    a.created,
    a.comment as appointment_comment,
    a.patient_instruction,

    -- Add provenance: How was this identified as radiation-related?
    CASE
        WHEN rst.appointment_id IS NOT NULL THEN 'service_type_radiation'
        WHEN rat.appointment_id IS NOT NULL THEN 'appointment_type_radiation'
        WHEN rp.patient_fhir_id IS NOT NULL
             AND (LOWER(a.comment) LIKE '%radiation%'
                  OR LOWER(a.description) LIKE '%radiation%'
                  OR LOWER(a.patient_instruction) LIKE '%radiation%')
             THEN 'patient_with_radiation_data_and_radiation_keyword'
        WHEN rp.patient_fhir_id IS NOT NULL
             AND rtd.patient_fhir_id IS NOT NULL
             THEN 'patient_with_radiation_data_temporal_match'
        ELSE 'unknown'
    END as radiation_identification_method,

    -- Service type details
    rst.service_type_text as radiation_service_type,
    rat.appointment_type_coding_display as radiation_appointment_type

FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id

-- Join to radiation-specific filters (at least one must match)
LEFT JOIN radiation_service_types rst ON a.id = rst.appointment_id
LEFT JOIN radiation_appointment_types rat ON a.id = rat.appointment_id
LEFT JOIN radiation_patients rp ON ap.participant_actor_reference = CONCAT('Patient/', rp.patient_fhir_id)
LEFT JOIN radiation_treatment_dates rtd
    ON ap.participant_actor_reference = CONCAT('Patient/', rtd.patient_fhir_id)
    AND TRY_CAST(a.start AS TIMESTAMP) IS NOT NULL
    AND (
        -- Check against observation dates
        (rtd.treatment_start IS NOT NULL
         AND rtd.treatment_end_plus_30 IS NOT NULL
         AND TRY_CAST(a.start AS TIMESTAMP) >= rtd.treatment_start
         AND TRY_CAST(a.start AS TIMESTAMP) <= rtd.treatment_end_plus_30)
        OR
        -- Check against service request dates
        (rtd.sr_start IS NOT NULL
         AND rtd.sr_end_plus_30 IS NOT NULL
         AND TRY_CAST(a.start AS TIMESTAMP) >= rtd.sr_start
         AND TRY_CAST(a.start AS TIMESTAMP) <= rtd.sr_end_plus_30)
    )

WHERE ap.participant_actor_reference LIKE 'Patient/%'
  AND (
      -- Layer 1: Explicit radiation service type
      rst.appointment_id IS NOT NULL

      -- Layer 2: Explicit radiation appointment type
      OR rat.appointment_id IS NOT NULL

      -- Layer 3: Patient has radiation data AND appointment mentions radiation
      OR (rp.patient_fhir_id IS NOT NULL
          AND (LOWER(a.comment) LIKE '%radiation%'
               OR LOWER(a.comment) LIKE '%rad%onc%'
               OR LOWER(a.comment) LIKE '%radiotherapy%'
               OR LOWER(a.description) LIKE '%radiation%'
               OR LOWER(a.description) LIKE '%rad%onc%'
               OR LOWER(a.description) LIKE '%radiotherapy%'
               OR LOWER(a.patient_instruction) LIKE '%radiation%'))

      -- Layer 4: Patient has radiation data + appointment during treatment window
      OR (rp.patient_fhir_id IS NOT NULL
          AND rtd.patient_fhir_id IS NOT NULL)
  )

ORDER BY ap.participant_actor_reference, TRY_CAST(a.start AS TIMESTAMP);
