-- ================================================================================
-- V_RADIATION_TREATMENT_EPISODES (COMPREHENSIVE)
-- ================================================================================
-- Purpose: Group radiation treatments into logical episodes leveraging ALL 5 radiation views
--
-- Data Sources Integrated:
--   1. v_radiation_treatments - Treatment details (dose, field, site, course_id)
--   2. v_radiation_care_plan_hierarchy - Care plan relationships and dates
--   3. v_radiation_documents - Document availability for NLP extraction
--   4. v_radiation_treatment_appointments - Appointment timing and fulfillment
--   5. v_radiation_summary - NOT USED (0 records currently)
--
-- Episode Construction Strategy:
--   - PRIMARY GROUPING: course_id from v_radiation_treatments
--   - DATES: Best available from treatments, care plans, appointments, documents
--   - ENRICHMENT: Document counts, appointment counts, care plan hierarchy
--   - One row per radiation episode (course) with comprehensive metadata
--
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_episodes AS

WITH
-- Base: Treatment episodes grouped by course
treatment_episodes AS (
    SELECT
        patient_fhir_id,
        course_id as episode_id,

        -- Episode classification
        CASE
            WHEN COUNT(CASE WHEN obs_dose_value IS NOT NULL THEN 1 END) > 0 THEN 'STRUCTURED_ELECT'
            WHEN COUNT(CASE WHEN sr_status IS NOT NULL THEN 1 END) > 0 THEN 'SERVICE_REQUEST_BASED'
            ELSE 'UNGROUPED'
        END as episode_data_type,

        -- Treatment details (aggregated)
        SUM(obs_dose_value) as total_dose_cgy,
        AVG(obs_dose_value) as avg_dose_cgy,
        MIN(obs_dose_value) as min_dose_cgy,
        MAX(obs_dose_value) as max_dose_cgy,
        COUNT(CASE WHEN obs_dose_value IS NOT NULL THEN 1 END) as num_dose_records,

        COUNT(DISTINCT obs_radiation_field) as num_unique_fields,
        COUNT(DISTINCT obs_radiation_site_code) as num_unique_sites,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT obs_radiation_field), ', ') as radiation_fields,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT CAST(obs_radiation_site_code AS VARCHAR)), ', ') as radiation_site_codes,

        -- Date sources from treatments
        MIN(best_treatment_start_date) as treatment_start_date,
        MAX(best_treatment_stop_date) as treatment_stop_date,
        MIN(obs_start_date) as obs_start_date,
        MAX(obs_stop_date) as obs_stop_date,
        MIN(cp_first_start_date) as cp_start_date_from_treatments,
        MAX(cp_last_end_date) as cp_end_date_from_treatments,

        -- Availability flags from treatments
        CAST(MAX(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_dose_data,
        CAST(MAX(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_field_data,
        CAST(MAX(CASE WHEN obs_radiation_site_code IS NOT NULL THEN 1 ELSE 0 END) AS BOOLEAN) as has_site_data,

        -- Summary counts from treatments
        MAX(cp_total_care_plans) as cp_count_from_treatments,
        MAX(apt_total_appointments) as apt_count_from_treatments,
        MAX(apt_fulfilled_appointments) as apt_fulfilled_from_treatments,
        MAX(apt_cancelled_appointments) as apt_cancelled_from_treatments,

        -- Service request metadata
        ARRAY_JOIN(ARRAY_AGG(DISTINCT sr_code_text), ' | ') as service_request_codes,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT sr_status), ' | ') as service_request_statuses

    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NOT NULL
    GROUP BY patient_fhir_id, course_id
),

-- Enrichment: Care plan hierarchy (direct linkage to patient)
care_plan_enrichment AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT care_plan_id) as total_radiation_care_plans,
        MIN(cp_period_start) as earliest_care_plan_start,
        MAX(cp_period_end) as latest_care_plan_end,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT care_plan_id), ' | ') as care_plan_ids
    FROM fhir_prd_db.v_radiation_care_plan_hierarchy
    GROUP BY patient_fhir_id
),

-- Enrichment: Document availability for NLP extraction
document_enrichment AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT document_id) as total_radiation_documents,
        COUNT(DISTINCT CASE WHEN extraction_priority = 1 THEN document_id END) as high_priority_documents,
        COUNT(DISTINCT CASE WHEN extraction_priority = 2 THEN document_id END) as medium_priority_documents,
        COUNT(DISTINCT CASE WHEN document_category = 'Treatment Summary' THEN document_id END) as treatment_summary_documents,
        COUNT(DISTINCT CASE WHEN document_category = 'Consultation' THEN document_id END) as consultation_documents,
        MIN(doc_date) as earliest_document_date,
        MAX(doc_date) as latest_document_date,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT document_category), ' | ') as document_categories
    FROM fhir_prd_db.v_radiation_documents
    GROUP BY patient_fhir_id
),

-- Enrichment: Appointment timing (direct linkage to patient)
appointment_enrichment AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT appointment_id) as total_radiation_appointments,
        COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) as fulfilled_appointments,
        COUNT(DISTINCT CASE WHEN appointment_status = 'cancelled' THEN appointment_id END) as cancelled_appointments,
        COUNT(DISTINCT CASE WHEN appointment_status = 'noshow' THEN appointment_id END) as noshow_appointments,
        MIN(appointment_start) as earliest_appointment_date,
        MAX(appointment_start) as latest_appointment_date,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT appointment_status), ' | ') as appointment_statuses
    FROM fhir_prd_db.v_radiation_treatment_appointments
    GROUP BY patient_fhir_id
)

-- Final assembly: Join all enrichments to treatment episodes
SELECT
    -- ========================================================================
    -- EPISODE IDENTIFIERS
    -- ========================================================================
    te.episode_id,
    te.patient_fhir_id,
    te.episode_data_type,

    -- ========================================================================
    -- EPISODE TEMPORAL BOUNDARIES (BEST AVAILABLE)
    -- ========================================================================
    -- Priority: 1) treatment dates, 2) care plan dates, 3) appointment dates, 4) document dates
    COALESCE(
        te.treatment_start_date,
        te.obs_start_date,
        cpe.earliest_care_plan_start,
        ae.earliest_appointment_date,
        de.earliest_document_date
    ) as episode_start_date,

    CAST(COALESCE(
        te.treatment_start_date,
        te.obs_start_date,
        cpe.earliest_care_plan_start,
        ae.earliest_appointment_date,
        de.earliest_document_date
    ) AS TIMESTAMP) as episode_start_datetime,

    COALESCE(
        te.treatment_stop_date,
        te.obs_stop_date,
        cpe.latest_care_plan_end,
        ae.latest_appointment_date,
        de.latest_document_date
    ) as episode_end_date,

    CAST(COALESCE(
        te.treatment_stop_date,
        te.obs_stop_date,
        cpe.latest_care_plan_end,
        ae.latest_appointment_date,
        de.latest_document_date
    ) AS TIMESTAMP) as episode_end_datetime,

    -- Episode duration (in days, NULL if dates missing)
    DATE_DIFF('day',
        COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date),
        COALESCE(te.treatment_stop_date, te.obs_stop_date, cpe.latest_care_plan_end, ae.latest_appointment_date, de.latest_document_date)
    ) as episode_duration_days,

    -- Date source tracking
    CASE
        WHEN te.treatment_start_date IS NOT NULL THEN 'best_treatment_start_date'
        WHEN te.obs_start_date IS NOT NULL THEN 'obs_start_date'
        WHEN cpe.earliest_care_plan_start IS NOT NULL THEN 'care_plan_start'
        WHEN ae.earliest_appointment_date IS NOT NULL THEN 'appointment_start'
        WHEN de.earliest_document_date IS NOT NULL THEN 'document_date'
        ELSE NULL
    END as episode_start_date_source,

    CASE
        WHEN te.treatment_stop_date IS NOT NULL THEN 'best_treatment_stop_date'
        WHEN te.obs_stop_date IS NOT NULL THEN 'obs_stop_date'
        WHEN cpe.latest_care_plan_end IS NOT NULL THEN 'care_plan_end'
        WHEN ae.latest_appointment_date IS NOT NULL THEN 'appointment_end'
        WHEN de.latest_document_date IS NOT NULL THEN 'document_date'
        ELSE NULL
    END as episode_end_date_source,

    -- ========================================================================
    -- DOSE SUMMARY (from v_radiation_treatments)
    -- ========================================================================
    te.total_dose_cgy,
    te.avg_dose_cgy,
    te.min_dose_cgy,
    te.max_dose_cgy,
    te.num_dose_records,

    -- ========================================================================
    -- RADIATION SITES/FIELDS (from v_radiation_treatments)
    -- ========================================================================
    te.num_unique_fields,
    te.num_unique_sites,
    te.radiation_fields,
    te.radiation_site_codes,

    -- ========================================================================
    -- CARE PLAN METADATA (from v_radiation_care_plan_hierarchy)
    -- ========================================================================
    COALESCE(cpe.total_radiation_care_plans, 0) as num_care_plans,
    cpe.care_plan_ids,
    cpe.earliest_care_plan_start,
    cpe.latest_care_plan_end,

    -- ========================================================================
    -- DOCUMENT METADATA (from v_radiation_documents)
    -- ========================================================================
    COALESCE(de.total_radiation_documents, 0) as num_documents,
    COALESCE(de.high_priority_documents, 0) as num_high_priority_documents,
    COALESCE(de.medium_priority_documents, 0) as num_medium_priority_documents,
    COALESCE(de.treatment_summary_documents, 0) as num_treatment_summaries,
    COALESCE(de.consultation_documents, 0) as num_consultations,
    de.document_categories,
    de.earliest_document_date,
    de.latest_document_date,

    -- ========================================================================
    -- APPOINTMENT METADATA (from v_radiation_treatment_appointments)
    -- ========================================================================
    COALESCE(ae.total_radiation_appointments, 0) as num_appointments,
    COALESCE(ae.fulfilled_appointments, 0) as num_fulfilled_appointments,
    COALESCE(ae.cancelled_appointments, 0) as num_cancelled_appointments,
    COALESCE(ae.noshow_appointments, 0) as num_noshow_appointments,
    ae.appointment_statuses,
    ae.earliest_appointment_date,
    ae.latest_appointment_date,

    -- ========================================================================
    -- SERVICE REQUEST METADATA (from v_radiation_treatments)
    -- ========================================================================
    te.service_request_codes,
    te.service_request_statuses,

    -- ========================================================================
    -- DATA AVAILABILITY FLAGS
    -- ========================================================================
    te.has_dose_data,
    te.has_field_data,
    te.has_site_data,
    CAST(COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL AS BOOLEAN) as has_episode_dates,
    CAST(COALESCE(cpe.total_radiation_care_plans, 0) > 0 AS BOOLEAN) as has_care_plans,
    CAST(COALESCE(de.total_radiation_documents, 0) > 0 AS BOOLEAN) as has_documents,
    CAST(COALESCE(ae.total_radiation_appointments, 0) > 0 AS BOOLEAN) as has_appointments,

    -- Data completeness indicator (dose + field + site + dates)
    CASE
        WHEN te.has_dose_data
             AND te.has_field_data
             AND te.has_site_data
             AND COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL
        THEN true
        ELSE false
    END as has_complete_structured_data,

    -- ========================================================================
    -- DATA QUALITY SCORE (0.0 to 1.0)
    -- ========================================================================
    -- Weighted: dates (25%), dose (20%), field (20%), site (15%), documents (10%), care plans (10%)
    CAST((
        (CASE WHEN COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL THEN 0.25 ELSE 0.0 END) +
        (CASE WHEN te.has_dose_data THEN 0.20 ELSE 0.0 END) +
        (CASE WHEN te.has_field_data THEN 0.20 ELSE 0.0 END) +
        (CASE WHEN te.has_site_data THEN 0.15 ELSE 0.0 END) +
        (CASE WHEN COALESCE(de.total_radiation_documents, 0) > 0 THEN 0.10 ELSE 0.0 END) +
        (CASE WHEN COALESCE(cpe.total_radiation_care_plans, 0) > 0 THEN 0.10 ELSE 0.0 END)
    ) AS DOUBLE) as episode_data_quality_score,

    -- Data quality tier (for filtering/prioritization)
    CASE
        WHEN CAST((
            (CASE WHEN COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN te.has_dose_data THEN 0.20 ELSE 0.0 END) +
            (CASE WHEN te.has_field_data THEN 0.20 ELSE 0.0 END) +
            (CASE WHEN te.has_site_data THEN 0.15 ELSE 0.0 END) +
            (CASE WHEN COALESCE(de.total_radiation_documents, 0) > 0 THEN 0.10 ELSE 0.0 END) +
            (CASE WHEN COALESCE(cpe.total_radiation_care_plans, 0) > 0 THEN 0.10 ELSE 0.0 END)
        ) AS DOUBLE) >= 0.80 THEN 'HIGH'
        WHEN CAST((
            (CASE WHEN COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN te.has_dose_data THEN 0.20 ELSE 0.0 END) +
            (CASE WHEN te.has_field_data THEN 0.20 ELSE 0.0 END) +
            (CASE WHEN te.has_site_data THEN 0.15 ELSE 0.0 END) +
            (CASE WHEN COALESCE(de.total_radiation_documents, 0) > 0 THEN 0.10 ELSE 0.0 END) +
            (CASE WHEN COALESCE(cpe.total_radiation_care_plans, 0) > 0 THEN 0.10 ELSE 0.0 END)
        ) AS DOUBLE) >= 0.50 THEN 'MEDIUM'
        ELSE 'LOW'
    END as data_quality_tier,

    -- ========================================================================
    -- RECOMMENDED ANALYSIS STRATEGY
    -- ========================================================================
    CASE
        -- Best case: Have all structured data (dose, field, site) + dates + documents
        WHEN te.has_dose_data
             AND te.has_field_data
             AND te.has_site_data
             AND COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL
             AND COALESCE(de.total_radiation_documents, 0) > 0
        THEN 'DIRECT_ANALYSIS_WITH_VALIDATION'

        -- Good case: Have all structured data + dates (no documents for validation)
        WHEN te.has_dose_data
             AND te.has_field_data
             AND te.has_site_data
             AND COALESCE(te.treatment_start_date, te.obs_start_date, cpe.earliest_care_plan_start, ae.earliest_appointment_date, de.earliest_document_date) IS NOT NULL
        THEN 'DIRECT_ANALYSIS_READY'

        -- Moderate case: Have treatment details but missing dates
        WHEN te.has_dose_data
             AND te.has_field_data
        THEN 'ANALYSIS_READY_NO_DATES'

        -- Document-based case: Have documents but limited structured data
        WHEN COALESCE(de.high_priority_documents, 0) > 0
        THEN 'DOCUMENT_EXTRACTION_RECOMMENDED'

        -- Partial case: Have some data but incomplete
        WHEN te.has_dose_data
             OR te.has_field_data
             OR COALESCE(de.total_radiation_documents, 0) > 0
        THEN 'PARTIAL_DATA_AVAILABLE'

        ELSE 'INSUFFICIENT_DATA'
    END as recommended_analysis_approach

FROM treatment_episodes te
LEFT JOIN care_plan_enrichment cpe ON te.patient_fhir_id = cpe.patient_fhir_id
LEFT JOIN document_enrichment de ON te.patient_fhir_id = de.patient_fhir_id
LEFT JOIN appointment_enrichment ae ON te.patient_fhir_id = ae.patient_fhir_id

ORDER BY
    episode_data_quality_score DESC,
    patient_fhir_id,
    episode_id;

-- ================================================================================
-- USAGE NOTES
-- ================================================================================
-- This comprehensive view creates one row per radiation episode (course),
-- enriched with data from ALL 5 radiation views.
--
-- Key Enhancements vs Simple Episode View:
--   1. Multi-source date fallback (treatments → care plans → appointments → documents)
--   2. Document availability metrics for NLP extraction prioritization
--   3. Care plan hierarchy integration
--   4. Appointment fulfillment tracking
--   5. Date source tracking for transparency
--
-- Filtering Recommendations:
--   - For complete analysis: WHERE recommended_analysis_approach = 'DIRECT_ANALYSIS_WITH_VALIDATION'
--   - For structured-only analysis: WHERE recommended_analysis_approach = 'DIRECT_ANALYSIS_READY'
--   - For document extraction candidates: WHERE recommended_analysis_approach = 'DOCUMENT_EXTRACTION_RECOMMENDED'
--   - For high quality: WHERE data_quality_tier = 'HIGH' or episode_data_quality_score >= 0.8
--
-- ================================================================================
