-- =====================================================================================
-- View: v_patient_treatment_response_summary
-- Description: Patient-level treatment response summary aggregating imaging findings
--              across treatment phases to classify overall response
--
-- Data Sources:
--   - v_patient_clinical_journey_timeline (main timeline view)
--   - v_pathology_diagnostics (diagnosis context)
--   - v_procedures_tumor (surgical outcomes)
--
-- Key Features:
--   - Overall response classification per patient (PD/PR/CR/SD)
--   - Latest imaging status by treatment phase
--   - Progression-free survival metrics
--   - Treatment history summary
--   - Molecular marker context
--
-- Author: Claude (WHO 2021 CNS Tumor Classification Framework)
-- Created: 2025-10-30
-- =====================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_treatment_response_summary AS

WITH latest_imaging_per_phase AS (
    SELECT
        patient_fhir_id,
        imaging_phase,
        MAX(event_date) as latest_imaging_date,
        FIRST_VALUE(progression_flag) OVER (
            PARTITION BY patient_fhir_id, imaging_phase
            ORDER BY event_date DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) as latest_progression_flag,
        FIRST_VALUE(response_flag) OVER (
            PARTITION BY patient_fhir_id, imaging_phase
            ORDER BY event_date DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) as latest_response_flag,
        FIRST_VALUE(free_text_content) OVER (
            PARTITION BY patient_fhir_id, imaging_phase
            ORDER BY event_date DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) as latest_report_conclusion
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE event_type = 'imaging'
        AND imaging_phase IS NOT NULL
    GROUP BY patient_fhir_id, imaging_phase, event_date, progression_flag, response_flag, free_text_content
),

patient_treatment_summary AS (
    SELECT
        patient_fhir_id,
        patient_diagnosis,
        molecular_marker,

        -- Count treatment episodes
        COUNT(DISTINCT CASE WHEN event_type = 'chemo_episode_start' THEN episode_id END) as chemo_episode_count,
        COUNT(DISTINCT CASE WHEN event_type = 'radiation_episode_start' THEN episode_id END) as radiation_episode_count,

        -- Surgical outcome
        MAX(CASE WHEN event_type = 'surgery' THEN resection_extent_from_text END) as initial_resection_extent,

        -- PFS metrics
        MAX(patient_days_to_progression) as days_to_progression,
        MAX(patient_pfs_from_treatment) as pfs_days_from_treatment_completion,
        MAX(CASE WHEN patient_has_progressed = true THEN 1 ELSE 0 END) as progressed

    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    GROUP BY patient_fhir_id, patient_diagnosis, molecular_marker
)

SELECT
    pts.patient_fhir_id,
    pts.patient_diagnosis,
    pts.molecular_marker,

    -- Surgical outcome
    pts.initial_resection_extent,

    -- Treatment history
    pts.chemo_episode_count,
    pts.radiation_episode_count,

    -- Latest imaging by phase
    MAX(CASE WHEN li.imaging_phase = 'immediate_post_op' THEN li.latest_response_flag END) as post_op_imaging_status,
    MAX(CASE WHEN li.imaging_phase = 'early_post_radiation' THEN li.latest_response_flag END) as post_radiation_imaging_status,
    MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) as surveillance_imaging_status,

    -- Latest imaging date per phase (for reference)
    MAX(CASE WHEN li.imaging_phase = 'immediate_post_op' THEN li.latest_imaging_date END) as post_op_imaging_date,
    MAX(CASE WHEN li.imaging_phase = 'early_post_radiation' THEN li.latest_imaging_date END) as post_radiation_imaging_date,
    MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_imaging_date END) as surveillance_imaging_date,

    -- Progression status
    CASE WHEN pts.progressed = 1 THEN true ELSE false END as progressed,
    pts.days_to_progression,
    pts.pfs_days_from_treatment_completion,

    -- Overall response assessment (RANO-inspired classification)
    CASE
        WHEN pts.progressed = 1 THEN 'Progressive Disease'
        WHEN MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) = 'response_suspected'
            THEN 'Partial Response'
        WHEN MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) = 'complete_response_suspected'
            THEN 'Complete Response'
        WHEN MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) = 'stable_disease'
            THEN 'Stable Disease'
        WHEN MAX(CASE WHEN li.imaging_phase IN ('immediate_post_op', 'early_post_radiation') THEN li.latest_response_flag END) = 'response_suspected'
            THEN 'Early Response'
        WHEN MAX(CASE WHEN li.imaging_phase IN ('immediate_post_op', 'early_post_radiation') THEN li.latest_response_flag END) = 'stable_disease'
            THEN 'Early Stable Disease'
        ELSE 'Insufficient Data'
    END as overall_response_classification

FROM patient_treatment_summary pts
LEFT JOIN latest_imaging_per_phase li
    ON pts.patient_fhir_id = li.patient_fhir_id

GROUP BY
    pts.patient_fhir_id,
    pts.patient_diagnosis,
    pts.molecular_marker,
    pts.initial_resection_extent,
    pts.chemo_episode_count,
    pts.radiation_episode_count,
    pts.progressed,
    pts.days_to_progression,
    pts.pfs_days_from_treatment_completion

ORDER BY pts.patient_fhir_id;
