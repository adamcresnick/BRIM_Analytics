-- ================================================================================
-- RADIATION VIEWS - CRITICAL FIXES
-- ================================================================================
-- Date: 2025-10-29
-- Issue: v_radiation_summary patient ID extraction bug
-- Impact: 115 patients with radiation history flag have WRONG patient_fhir_id
-- ================================================================================

-- ISSUE IDENTIFIED:
-- Line 5042 in v_radiation_summary uses SUBSTRING(subject_reference, 9)
-- This assumes "Patient/" prefix exists (8 chars + 1 for '/')
-- But observation.subject_reference does NOT have "Patient/" prefix
-- Result: Patient IDs are truncated (e17wPSC... becomes PZalWWU...)

-- ================================================================================
-- FIX 1: v_radiation_summary - CRITICAL
-- ================================================================================

-- CHANGE LINE 5042 FROM:
--   SELECT DISTINCT SUBSTRING(subject_reference, 9) as patient_fhir_id

-- TO:
--   SELECT DISTINCT subject_reference as patient_fhir_id

-- FULL CORRECTED CTE:
patients_with_radiation_flag AS (
    SELECT DISTINCT subject_reference as patient_fhir_id
    FROM fhir_prd_db.observation
    WHERE code_text = 'ELECT - INTAKE FORM - TREATMENT HISTORY - RADIATION'
),

-- ================================================================================
-- FIX 2: v_radiation_documents - RECOMMENDED (Not Critical)
-- ================================================================================

-- CURRENT (Lines 4351-4361):
document_content AS (
    SELECT
        document_reference_id,
        MAX(content_attachment_content_type) as content_type,
        MAX(content_attachment_url) as attachment_url,
        MAX(content_attachment_title) as attachment_title,
        MAX(content_attachment_creation) as attachment_creation,
        MAX(content_attachment_size) as attachment_size
    FROM fhir_prd_db.document_reference_content
    GROUP BY document_reference_id
)

-- RECOMMENDED (Uses ROW_NUMBER for explicit selection):
document_content AS (
    SELECT 
        document_reference_id,
        content_type,
        attachment_url,
        attachment_title,
        attachment_creation,
        attachment_size
    FROM (
        SELECT
            document_reference_id,
            content_attachment_content_type as content_type,
            content_attachment_url as attachment_url,
            content_attachment_title as attachment_title,
            content_attachment_creation as attachment_creation,
            content_attachment_size as attachment_size,
            ROW_NUMBER() OVER (
                PARTITION BY document_reference_id 
                ORDER BY content_attachment_creation DESC NULLS LAST,
                         content_attachment_url
            ) as rn
        FROM fhir_prd_db.document_reference_content
    )
    WHERE rn = 1
)

-- ================================================================================
-- FIX 3: v_radiation_treatments - OPTIMIZATION (Not Critical)
-- ================================================================================

-- CURRENT (Lines 268-276):
WHERE ap.participant_actor_reference LIKE 'Patient/%'
  AND ap.participant_actor_reference IN (
      SELECT DISTINCT subject_reference FROM fhir_prd_db.service_request
      WHERE LOWER(code_text) LIKE '%radiation%'
      UNION
      SELECT DISTINCT subject_reference FROM fhir_prd_db.observation
      WHERE code_text LIKE 'ELECT - INTAKE FORM - RADIATION%'
  )

-- RECOMMENDED (Move to WITH clause for better performance):
WITH radiation_patients AS (
    SELECT DISTINCT subject_reference FROM fhir_prd_db.service_request
    WHERE LOWER(code_text) LIKE '%radiation%'
    UNION
    SELECT DISTINCT subject_reference FROM fhir_prd_db.observation
    WHERE code_text LIKE 'ELECT - INTAKE FORM - RADIATION%'
),
appointment_summary AS (
    SELECT
        ap.participant_actor_reference as patient_fhir_id,
        ...
    FROM fhir_prd_db.appointment a
    JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
    WHERE ap.participant_actor_reference LIKE 'Patient/%'
      AND ap.participant_actor_reference IN (SELECT subject_reference FROM radiation_patients)
    GROUP BY ap.participant_actor_reference
)

-- ================================================================================
-- DEPLOYMENT INSTRUCTIONS
-- ================================================================================

-- 1. Apply FIX 1 (CRITICAL - Must do immediately)
--    - Edit DATETIME_STANDARDIZED_VIEWS.sql line 5042
--    - Change: SUBSTRING(subject_reference, 9)
--    - To:     subject_reference
--    - Deploy v_radiation_summary

-- 2. Apply FIX 2 (RECOMMENDED - Can do in next iteration)
--    - Edit document_content CTE in v_radiation_documents
--    - Replace MAX() with ROW_NUMBER() approach
--    - Deploy v_radiation_documents

-- 3. Apply FIX 3 (OPTIMIZATION - Can do in next iteration)
--    - Move radiation_patients subquery to WITH clause
--    - Deploy v_radiation_treatments

-- ================================================================================
-- VALIDATION QUERIES
-- ================================================================================

-- After deploying FIX 1, run this to verify:
SELECT 
    COUNT(DISTINCT patient_fhir_id) as total_patients,
    MIN(LENGTH(patient_fhir_id)) as min_id_length,
    MAX(LENGTH(patient_fhir_id)) as max_id_length,
    AVG(LENGTH(patient_fhir_id)) as avg_id_length
FROM v_radiation_summary
WHERE has_radiation_history_flag = true;

-- Expected results:
-- total_patients: 115
-- min_id_length: 45
-- max_id_length: 45
-- avg_id_length: 45.0

-- If you see:
-- min_id_length: 37 (or anything < 45) -> FIX NOT APPLIED CORRECTLY

