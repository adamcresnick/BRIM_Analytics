-- ============================================================================
-- TEST: Episode Enrichment Coverage and Quality
-- ============================================================================

WITH enrichment_summary AS (
    SELECT
        episode_detection_method,

        -- Episode counts
        COUNT(*) as total_episodes,
        COUNT(DISTINCT patient_fhir_id) as total_patients,

        -- Appointment enrichment
        SUM(CASE WHEN has_appointment_enrichment THEN 1 ELSE 0 END) as episodes_with_appointments,
        ROUND(AVG(total_appointments), 1) as avg_appointments_per_episode,
        ROUND(AVG(appointment_fulfillment_rate_pct), 1) as avg_fulfillment_rate,

        -- Appointment by phase
        ROUND(AVG(pre_treatment_appointments), 1) as avg_pre_treatment,
        ROUND(AVG(during_treatment_appointments), 1) as avg_during_treatment,
        ROUND(AVG(post_treatment_appointments), 1) as avg_post_treatment,
        ROUND(AVG(early_followup_appointments), 1) as avg_early_followup,

        -- Care plan enrichment
        SUM(CASE WHEN has_care_plan_enrichment THEN 1 ELSE 0 END) as episodes_with_care_plans,
        ROUND(AVG(total_care_plans), 1) as avg_care_plans_per_episode,
        SUM(care_plans_with_dates) as total_care_plans_with_dates,

        -- Enrichment scores
        ROUND(AVG(enrichment_score), 1) as avg_enrichment_score,

        -- Data completeness tiers
        SUM(CASE WHEN data_completeness_tier = 'COMPLETE' THEN 1 ELSE 0 END) as tier_complete,
        SUM(CASE WHEN data_completeness_tier = 'GOOD' THEN 1 ELSE 0 END) as tier_good,
        SUM(CASE WHEN data_completeness_tier = 'PARTIAL' THEN 1 ELSE 0 END) as tier_partial,
        SUM(CASE WHEN data_completeness_tier = 'MINIMAL' THEN 1 ELSE 0 END) as tier_minimal,

        -- Treatment phase coverage
        SUM(CASE WHEN treatment_phase_coverage = 'FULL_CONTINUUM' THEN 1 ELSE 0 END) as full_continuum,
        SUM(CASE WHEN treatment_phase_coverage = 'TREATMENT_PLUS_ONE' THEN 1 ELSE 0 END) as treatment_plus_one,
        SUM(CASE WHEN treatment_phase_coverage = 'TREATMENT_ONLY' THEN 1 ELSE 0 END) as treatment_only,
        SUM(CASE WHEN treatment_phase_coverage = 'CONSULTATION_ONLY' THEN 1 ELSE 0 END) as consultation_only,
        SUM(CASE WHEN treatment_phase_coverage = 'NO_APPOINTMENTS' THEN 1 ELSE 0 END) as no_appointments

    FROM fhir_prd_db.v_radiation_episode_enrichment
    GROUP BY episode_detection_method
)

SELECT
    episode_detection_method,
    total_episodes,
    total_patients,
    episodes_with_appointments,
    avg_appointments_per_episode,
    avg_fulfillment_rate,
    avg_pre_treatment,
    avg_during_treatment,
    avg_post_treatment,
    avg_early_followup,
    episodes_with_care_plans,
    avg_care_plans_per_episode,
    total_care_plans_with_dates,
    avg_enrichment_score,
    tier_complete,
    tier_good,
    tier_partial,
    tier_minimal,
    full_continuum,
    treatment_plus_one,
    treatment_only,
    consultation_only,
    no_appointments
FROM enrichment_summary

UNION ALL

SELECT
    'TOTAL' as episode_detection_method,
    SUM(total_episodes) as total_episodes,
    SUM(total_patients) as total_patients,
    SUM(episodes_with_appointments) as episodes_with_appointments,
    ROUND(AVG(avg_appointments_per_episode), 1) as avg_appointments_per_episode,
    ROUND(AVG(avg_fulfillment_rate), 1) as avg_fulfillment_rate,
    ROUND(AVG(avg_pre_treatment), 1) as avg_pre_treatment,
    ROUND(AVG(avg_during_treatment), 1) as avg_during_treatment,
    ROUND(AVG(avg_post_treatment), 1) as avg_post_treatment,
    ROUND(AVG(avg_early_followup), 1) as avg_early_followup,
    SUM(episodes_with_care_plans) as episodes_with_care_plans,
    ROUND(AVG(avg_care_plans_per_episode), 1) as avg_care_plans_per_episode,
    SUM(total_care_plans_with_dates) as total_care_plans_with_dates,
    ROUND(AVG(avg_enrichment_score), 1) as avg_enrichment_score,
    SUM(tier_complete) as tier_complete,
    SUM(tier_good) as tier_good,
    SUM(tier_partial) as tier_partial,
    SUM(tier_minimal) as tier_minimal,
    SUM(full_continuum) as full_continuum,
    SUM(treatment_plus_one) as treatment_plus_one,
    SUM(treatment_only) as treatment_only,
    SUM(consultation_only) as consultation_only,
    SUM(no_appointments) as no_appointments
FROM enrichment_summary

ORDER BY
    CASE episode_detection_method
        WHEN 'structured_course_id' THEN 1
        WHEN 'document_temporal_cluster' THEN 2
        WHEN 'TOTAL' THEN 3
    END;
