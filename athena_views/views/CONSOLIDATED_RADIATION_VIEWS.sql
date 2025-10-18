-- ================================================================================
-- CONSOLIDATED RADIATION VIEWS
-- ================================================================================
-- Purpose: Replace existing fragmented radiation views with comprehensive consolidated views
-- Created: October 18, 2025
--
-- This file contains:
-- 1. v_radiation_treatments - Primary consolidated view (all treatment data)
-- 2. v_radiation_documents - Document references for NLP extraction
--
-- Prefix Strategy (Field Provenance):
-- - obs_* = observation table (ELECT intake forms - STRUCTURED dose/site)
-- - obsc_* = observation_component table (dose/site values)
-- - sr_* = service_request table (treatment courses)
-- - apt_* = appointment table (scheduling)
-- - cp_* = care_plan table (treatment plans)
-- - doc_* = document_reference table (clinical documents)
-- ================================================================================

-- ================================================================================
-- 1. v_radiation_treatments - CONSOLIDATED PRIMARY VIEW
-- ================================================================================
-- Combines ALL radiation treatment data sources with field provenance
-- Data sources (in priority order):
--   1. Observation (ELECT intake forms) - structured dose/site/dates
--   2. Service Request - treatment course metadata
--   3. Appointment - scheduling context
--   4. Care Plan - treatment plan linkage
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatments AS
WITH
-- ================================================================================
-- CTE 1: Observation-based radiation data (ELECT intake forms)
-- Source: observation + observation_component tables
-- Coverage: ~90 patients with structured dose, site, dates
-- ================================================================================
observation_dose AS (
    SELECT
        o.id as observation_id,
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as course_line,
        CAST(oc.component_value_quantity_value AS DOUBLE) as dose_value,
        COALESCE(oc.component_value_quantity_unit, 'cGy') as dose_unit,
        o.status as observation_status,
        o.effective_date_time as observation_effective_date,
        o.issued as observation_issued_date,
        o.code_text as observation_code_text
    FROM fhir_prd_db.observation o
    JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - DOSE'
      AND oc.component_value_quantity_value IS NOT NULL
),
observation_field AS (
    SELECT
        o.id as observation_id,
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as course_line,
        oc.component_value_string as field_value,
        o.effective_date_time as observation_effective_date
    FROM fhir_prd_db.observation o
    JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - FIELD'
      AND oc.component_value_string IS NOT NULL
),
observation_start_date AS (
    SELECT
        o.id as observation_id,
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as course_line,
        o.effective_date_time as start_date_value,
        o.issued as observation_issued_date
    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - START DATE'
),
observation_stop_date AS (
    SELECT
        o.id as observation_id,
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as course_line,
        o.effective_date_time as stop_date_value,
        o.issued as observation_issued_date
    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - STOP DATE'
),
observation_comments AS (
    SELECT
        o.id as observation_id,
        o.subject_reference as patient_fhir_id,
        LISTAGG(obn.note_text, ' | ') WITHIN GROUP (ORDER BY obn.note_time) as comments_aggregated,
        LISTAGG(obn.note_author_string, ' | ') WITHIN GROUP (ORDER BY obn.note_time) as comment_authors
    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_note obn ON o.id = obn.observation_id
    WHERE o.code_text LIKE 'ELECT - INTAKE FORM - RADIATION TABLE%'
    GROUP BY o.id, o.subject_reference
),
-- Combine all observation components into single record per course
observation_consolidated AS (
    SELECT
        COALESCE(od.patient_fhir_id, of.patient_fhir_id, osd.patient_fhir_id, ost.patient_fhir_id) as patient_fhir_id,
        COALESCE(od.observation_id, of.observation_id, osd.observation_id, ost.observation_id) as observation_id,
        COALESCE(od.course_line, of.course_line, osd.course_line, ost.course_line) as course_line,

        -- Dose fields (obs_ prefix)
        od.dose_value as obs_dose_value,
        od.dose_unit as obs_dose_unit,

        -- Field/site fields (obs_ prefix)
        of.field_value as obs_radiation_field,

        -- Map field to CBTN radiation_site codes (obs_ prefix)
        CASE
            WHEN LOWER(of.field_value) LIKE '%cranial%'
                 AND LOWER(of.field_value) NOT LIKE '%craniospinal%' THEN 1
            WHEN LOWER(of.field_value) LIKE '%craniospinal%' THEN 8
            WHEN LOWER(of.field_value) LIKE '%whole%ventricular%' THEN 9
            WHEN of.field_value IS NOT NULL THEN 6
            ELSE NULL
        END as obs_radiation_site_code,

        -- Dates (obs_ prefix)
        osd.start_date_value as obs_start_date,
        ost.stop_date_value as obs_stop_date,

        -- Metadata (obs_ prefix)
        od.observation_status as obs_status,
        od.observation_effective_date as obs_effective_date,
        od.observation_issued_date as obs_issued_date,
        od.observation_code_text as obs_code_text,

        -- Comments (obsc_ prefix for component-level data)
        oc.comments_aggregated as obsc_comments,
        oc.comment_authors as obsc_comment_authors,

        -- Data source flag
        'observation' as data_source_primary

    FROM observation_dose od
    FULL OUTER JOIN observation_field of
        ON od.patient_fhir_id = of.patient_fhir_id
        AND od.course_line = of.course_line
    FULL OUTER JOIN observation_start_date osd
        ON COALESCE(od.patient_fhir_id, of.patient_fhir_id) = osd.patient_fhir_id
        AND COALESCE(od.course_line, of.course_line) = osd.course_line
    FULL OUTER JOIN observation_stop_date ost
        ON COALESCE(od.patient_fhir_id, of.patient_fhir_id, osd.patient_fhir_id) = ost.patient_fhir_id
        AND COALESCE(od.course_line, of.course_line, osd.course_line) = ost.course_line
    LEFT JOIN observation_comments oc
        ON COALESCE(od.observation_id, of.observation_id, osd.observation_id, ost.observation_id) = oc.observation_id
),

-- ================================================================================
-- CTE 2: Service Request radiation courses
-- Source: service_request table
-- Coverage: 3 records, 1 patient (very limited)
-- ================================================================================
service_request_courses AS (
    SELECT
        sr.subject_reference as patient_fhir_id,
        sr.id as service_request_id,

        -- Service request fields (sr_ prefix - PRESERVE ALL ORIGINAL FIELDS)
        sr.status as sr_status,
        sr.intent as sr_intent,
        sr.code_text as sr_code_text,
        sr.quantity_quantity_value as sr_quantity_value,
        sr.quantity_quantity_unit as sr_quantity_unit,
        sr.quantity_ratio_numerator_value as sr_quantity_ratio_numerator_value,
        sr.quantity_ratio_numerator_unit as sr_quantity_ratio_numerator_unit,
        sr.quantity_ratio_denominator_value as sr_quantity_ratio_denominator_value,
        sr.quantity_ratio_denominator_unit as sr_quantity_ratio_denominator_unit,
        sr.occurrence_date_time as sr_occurrence_date_time,
        sr.occurrence_period_start as sr_occurrence_period_start,
        sr.occurrence_period_end as sr_occurrence_period_end,
        sr.authored_on as sr_authored_on,
        sr.requester_reference as sr_requester_reference,
        sr.requester_display as sr_requester_display,
        sr.performer_type_text as sr_performer_type_text,
        sr.patient_instruction as sr_patient_instruction,
        sr.priority as sr_priority,
        sr.do_not_perform as sr_do_not_perform,

        -- Data source flag
        'service_request' as data_source_primary

    FROM fhir_prd_db.service_request sr
    WHERE sr.subject_reference IS NOT NULL
      AND (LOWER(sr.code_text) LIKE '%radiation%'
           OR LOWER(sr.patient_instruction) LIKE '%radiation%')
),

-- ================================================================================
-- CTE 3: Service Request sub-schemas (notes, reason codes, body sites)
-- Source: service_request_* tables
-- ================================================================================
service_request_notes AS (
    SELECT
        srn.service_request_id,
        LISTAGG(srn.note_text, ' | ') WITHIN GROUP (ORDER BY srn.note_time) as note_text_aggregated,
        LISTAGG(srn.note_author_reference_display, ' | ') WITHIN GROUP (ORDER BY srn.note_time) as note_authors
    FROM fhir_prd_db.service_request_note srn
    WHERE srn.service_request_id IN (
        SELECT id FROM fhir_prd_db.service_request sr
        WHERE LOWER(sr.code_text) LIKE '%radiation%' OR LOWER(sr.patient_instruction) LIKE '%radiation%'
    )
    GROUP BY srn.service_request_id
),
service_request_reason_codes AS (
    SELECT
        srrc.service_request_id,
        LISTAGG(srrc.reason_code_text, ' | ') WITHIN GROUP (ORDER BY srrc.reason_code_text) as reason_code_text_aggregated,
        LISTAGG(srrc.reason_code_coding, ' | ') WITHIN GROUP (ORDER BY srrc.reason_code_text) as reason_code_coding_aggregated
    FROM fhir_prd_db.service_request_reason_code srrc
    WHERE srrc.service_request_id IN (
        SELECT id FROM fhir_prd_db.service_request sr
        WHERE LOWER(sr.code_text) LIKE '%radiation%' OR LOWER(sr.patient_instruction) LIKE '%radiation%'
    )
    GROUP BY srrc.service_request_id
),
service_request_body_sites AS (
    SELECT
        srbs.service_request_id,
        LISTAGG(srbs.body_site_text, ' | ') WITHIN GROUP (ORDER BY srbs.body_site_text) as body_site_text_aggregated,
        LISTAGG(srbs.body_site_coding, ' | ') WITHIN GROUP (ORDER BY srbs.body_site_text) as body_site_coding_aggregated
    FROM fhir_prd_db.service_request_body_site srbs
    WHERE srbs.service_request_id IN (
        SELECT id FROM fhir_prd_db.service_request sr
        WHERE LOWER(sr.code_text) LIKE '%radiation%' OR LOWER(sr.patient_instruction) LIKE '%radiation%'
    )
    GROUP BY srbs.service_request_id
),

-- ================================================================================
-- CTE 4: Appointment data (scheduling context)
-- Source: appointment + appointment_participant tables
-- Coverage: 331,796 appointments, 1,855 patients
-- ================================================================================
appointment_summary AS (
    SELECT
        ap.participant_actor_reference as patient_fhir_id,
        COUNT(DISTINCT a.id) as total_appointments,
        COUNT(DISTINCT CASE WHEN a.status = 'fulfilled' THEN a.id END) as fulfilled_appointments,
        COUNT(DISTINCT CASE WHEN a.status = 'cancelled' THEN a.id END) as cancelled_appointments,
        COUNT(DISTINCT CASE WHEN a.status = 'noshow' THEN a.id END) as noshow_appointments,
        MIN(a.start) as first_appointment_date,
        MAX(a.start) as last_appointment_date,
        MIN(CASE WHEN a.status = 'fulfilled' THEN a.start END) as first_fulfilled_appointment,
        MAX(CASE WHEN a.status = 'fulfilled' THEN a.start END) as last_fulfilled_appointment
    FROM fhir_prd_db.appointment a
    JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
    WHERE ap.participant_actor_reference LIKE 'Patient/%'
      AND ap.participant_actor_reference IN (
          -- Only include appointments for patients with radiation courses or observations
          SELECT DISTINCT subject_reference FROM fhir_prd_db.service_request
          WHERE LOWER(code_text) LIKE '%radiation%'
          UNION
          SELECT DISTINCT subject_reference FROM fhir_prd_db.observation
          WHERE code_text LIKE 'ELECT - INTAKE FORM - RADIATION%'
      )
    GROUP BY ap.participant_actor_reference
),

-- ================================================================================
-- CTE 5: Care Plan data (treatment plan context)
-- Source: care_plan + care_plan_part_of tables
-- Coverage: 18,189 records, 568 patients
-- ================================================================================
care_plan_summary AS (
    SELECT
        cp.subject_reference as patient_fhir_id,
        COUNT(DISTINCT cp.id) as total_care_plans,
        LISTAGG(DISTINCT cp.title, ' | ') WITHIN GROUP (ORDER BY cp.title) as care_plan_titles,
        LISTAGG(DISTINCT cp.status, ' | ') WITHIN GROUP (ORDER BY cp.status) as care_plan_statuses,
        MIN(cp.period_start) as first_care_plan_start,
        MAX(cp.period_end) as last_care_plan_end
    FROM fhir_prd_db.care_plan cp
    WHERE cp.subject_reference IS NOT NULL
      AND (LOWER(cp.title) LIKE '%radiation%')
    GROUP BY cp.subject_reference
)

-- ================================================================================
-- MAIN SELECT: Combine all sources with field provenance
-- ================================================================================
SELECT
    -- Patient identifier
    COALESCE(oc.patient_fhir_id, src.patient_fhir_id, apt.patient_fhir_id, cps.patient_fhir_id) as patient_fhir_id,

    -- Primary data source indicator
    COALESCE(oc.data_source_primary, src.data_source_primary) as data_source_primary,

    -- Course identifier (composite key)
    COALESCE(oc.observation_id, src.service_request_id) as course_id,
    oc.course_line as obs_course_line_number,

    -- ============================================================================
    -- OBSERVATION FIELDS (obs_ prefix) - STRUCTURED DOSE/SITE DATA
    -- Source: observation + observation_component tables (ELECT intake forms)
    -- ============================================================================
    oc.obs_dose_value,
    oc.obs_dose_unit,
    oc.obs_radiation_field,
    oc.obs_radiation_site_code,
    oc.obs_start_date,
    oc.obs_stop_date,
    oc.obs_status,
    oc.obs_effective_date,
    oc.obs_issued_date,
    oc.obs_code_text,

    -- Observation component comments (obsc_ prefix)
    oc.obsc_comments,
    oc.obsc_comment_authors,

    -- ============================================================================
    -- SERVICE REQUEST FIELDS (sr_ prefix) - TREATMENT COURSE METADATA
    -- Source: service_request table
    -- ============================================================================
    src.sr_status,
    src.sr_intent,
    src.sr_code_text,
    src.sr_quantity_value,
    src.sr_quantity_unit,
    src.sr_quantity_ratio_numerator_value,
    src.sr_quantity_ratio_numerator_unit,
    src.sr_quantity_ratio_denominator_value,
    src.sr_quantity_ratio_denominator_unit,
    src.sr_occurrence_date_time,
    src.sr_occurrence_period_start,
    src.sr_occurrence_period_end,
    src.sr_authored_on,
    src.sr_requester_reference,
    src.sr_requester_display,
    src.sr_performer_type_text,
    src.sr_patient_instruction,
    src.sr_priority,
    src.sr_do_not_perform,

    -- Service request sub-schema fields (srn_, srrc_, srbs_ prefixes)
    srn.note_text_aggregated as srn_note_text,
    srn.note_authors as srn_note_authors,
    srrc.reason_code_text_aggregated as srrc_reason_code_text,
    srrc.reason_code_coding_aggregated as srrc_reason_code_coding,
    srbs.body_site_text_aggregated as srbs_body_site_text,
    srbs.body_site_coding_aggregated as srbs_body_site_coding,

    -- ============================================================================
    -- APPOINTMENT FIELDS (apt_ prefix) - SCHEDULING CONTEXT
    -- Source: appointment + appointment_participant tables
    -- ============================================================================
    apt.total_appointments as apt_total_appointments,
    apt.fulfilled_appointments as apt_fulfilled_appointments,
    apt.cancelled_appointments as apt_cancelled_appointments,
    apt.noshow_appointments as apt_noshow_appointments,
    apt.first_appointment_date as apt_first_appointment_date,
    apt.last_appointment_date as apt_last_appointment_date,
    apt.first_fulfilled_appointment as apt_first_fulfilled_appointment,
    apt.last_fulfilled_appointment as apt_last_fulfilled_appointment,

    -- ============================================================================
    -- CARE PLAN FIELDS (cp_ prefix) - TREATMENT PLAN CONTEXT
    -- Source: care_plan + care_plan_part_of tables
    -- ============================================================================
    cps.total_care_plans as cp_total_care_plans,
    cps.care_plan_titles as cp_titles,
    cps.care_plan_statuses as cp_statuses,
    cps.first_care_plan_start as cp_first_start_date,
    cps.last_care_plan_end as cp_last_end_date,

    -- ============================================================================
    -- DERIVED/COMPUTED FIELDS
    -- ============================================================================

    -- Best available treatment dates (prioritize observation over service_request)
    COALESCE(oc.obs_start_date, src.sr_occurrence_period_start, apt.first_fulfilled_appointment) as best_treatment_start_date,
    COALESCE(oc.obs_stop_date, src.sr_occurrence_period_end, apt.last_fulfilled_appointment) as best_treatment_stop_date,

    -- Data completeness indicators
    CASE WHEN oc.obs_dose_value IS NOT NULL THEN true ELSE false END as has_structured_dose,
    CASE WHEN oc.obs_radiation_field IS NOT NULL THEN true ELSE false END as has_structured_site,
    CASE WHEN oc.obs_start_date IS NOT NULL OR src.sr_occurrence_period_start IS NOT NULL THEN true ELSE false END as has_treatment_dates,
    CASE WHEN apt.total_appointments > 0 THEN true ELSE false END as has_appointments,
    CASE WHEN cps.total_care_plans > 0 THEN true ELSE false END as has_care_plan,

    -- Data quality score (0-1)
    (
        CAST(CASE WHEN oc.obs_dose_value IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) * 0.3 +
        CAST(CASE WHEN oc.obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) * 0.3 +
        CAST(CASE WHEN oc.obs_start_date IS NOT NULL OR src.sr_occurrence_period_start IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) * 0.2 +
        CAST(CASE WHEN apt.total_appointments > 0 THEN 1 ELSE 0 END AS DOUBLE) * 0.1 +
        CAST(CASE WHEN cps.total_care_plans > 0 THEN 1 ELSE 0 END AS DOUBLE) * 0.1
    ) as data_quality_score

FROM observation_consolidated oc
FULL OUTER JOIN service_request_courses src
    ON oc.patient_fhir_id = src.patient_fhir_id
LEFT JOIN service_request_notes srn ON src.service_request_id = srn.service_request_id
LEFT JOIN service_request_reason_codes srrc ON src.service_request_id = srrc.service_request_id
LEFT JOIN service_request_body_sites srbs ON src.service_request_id = srbs.service_request_id
LEFT JOIN appointment_summary apt
    ON COALESCE(oc.patient_fhir_id, src.patient_fhir_id) = apt.patient_fhir_id
LEFT JOIN care_plan_summary cps
    ON COALESCE(oc.patient_fhir_id, src.patient_fhir_id) = cps.patient_fhir_id
WHERE COALESCE(oc.patient_fhir_id, src.patient_fhir_id, apt.patient_fhir_id, cps.patient_fhir_id) IS NOT NULL

ORDER BY patient_fhir_id, obs_course_line_number, best_treatment_start_date;


-- ================================================================================
-- 2. v_radiation_documents - DOCUMENT REFERENCES FOR NLP EXTRACTION
-- ================================================================================
-- Consolidates document_reference records with priority scoring
-- Replaces need to query multiple note views separately
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_documents AS
WITH
-- Aggregate document categories
document_categories AS (
    SELECT
        document_reference_id,
        LISTAGG(category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as category_text_aggregated,
        LISTAGG(category_coding, ' | ') WITHIN GROUP (ORDER BY category_coding) as category_coding_aggregated
    FROM (
        SELECT DISTINCT document_reference_id, category_text, category_coding
        FROM fhir_prd_db.document_reference_category
    )
    GROUP BY document_reference_id
),

-- Aggregate document authors
document_authors AS (
    SELECT
        document_reference_id,
        LISTAGG(author_reference, ' | ') WITHIN GROUP (ORDER BY author_reference) as author_references_aggregated,
        LISTAGG(author_display, ' | ') WITHIN GROUP (ORDER BY author_display) as author_displays_aggregated
    FROM (
        SELECT DISTINCT document_reference_id, author_reference, author_display
        FROM fhir_prd_db.document_reference_author
    )
    GROUP BY document_reference_id
),

-- Get document content (take first if multiple)
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

SELECT
    dr.subject_reference as patient_fhir_id,
    dr.id as document_id,

    -- Document metadata (doc_ prefix)
    dr.type_text as doc_type_text,
    dr.description as doc_description,
    dr.date as doc_date,
    dr.status as doc_status,
    dr.doc_status as doc_doc_status,
    dr.context_period_start as doc_context_period_start,
    dr.context_period_end as doc_context_period_end,
    dr.context_facility_type_text as doc_facility_type,
    dr.context_practice_setting_text as doc_practice_setting,

    -- Document content (docc_ prefix)
    drc.content_type as docc_content_type,
    drc.attachment_url as docc_attachment_url,
    drc.attachment_title as docc_attachment_title,
    drc.attachment_creation as docc_attachment_creation,
    drc.attachment_size as docc_attachment_size,

    -- Document category (doct_ prefix)
    drcat.category_text_aggregated as doct_category_text,
    drcat.category_coding_aggregated as doct_category_coding,

    -- Document authors (doca_ prefix)
    dra.author_references_aggregated as doca_author_references,
    dra.author_displays_aggregated as doca_author_displays,

    -- Extraction priority classification
    CASE
        WHEN dr.type_text = 'Rad Onc Treatment Report' THEN 1
        WHEN dr.type_text = 'ONC RadOnc End of Treatment' THEN 1
        WHEN LOWER(dr.description) LIKE '%end of treatment%summary%' THEN 1
        WHEN LOWER(dr.description) LIKE '%treatment summary%report%' THEN 1

        WHEN dr.type_text = 'ONC RadOnc Consult' THEN 2
        WHEN LOWER(dr.description) LIKE '%consult%' AND LOWER(dr.description) LIKE '%rad%onc%' THEN 2
        WHEN LOWER(dr.description) LIKE '%initial%consultation%' THEN 2

        WHEN dr.type_text = 'ONC Outside Summaries' AND LOWER(dr.description) LIKE '%radiation%' THEN 3
        WHEN dr.type_text = 'Clinical Report-Consult' AND LOWER(dr.description) LIKE '%radiation%' THEN 3
        WHEN dr.type_text = 'External Misc Clinical' AND LOWER(dr.description) LIKE '%radiation%' THEN 3

        WHEN LOWER(dr.description) LIKE '%progress%note%' THEN 4
        WHEN LOWER(dr.description) LIKE '%social work%' THEN 4

        ELSE 5
    END as extraction_priority,

    -- Document category for extraction type
    CASE
        WHEN dr.type_text IN ('Rad Onc Treatment Report', 'ONC RadOnc End of Treatment')
             OR LOWER(dr.description) LIKE '%end of treatment%' THEN 'Treatment Summary'
        WHEN dr.type_text = 'ONC RadOnc Consult'
             OR LOWER(dr.description) LIKE '%consult%' THEN 'Consultation'
        WHEN LOWER(dr.description) LIKE '%progress%note%' THEN 'Progress Note'
        WHEN LOWER(dr.description) LIKE '%social work%' THEN 'Social Work Note'
        WHEN dr.type_text = 'ONC Outside Summaries' THEN 'Outside Summary'
        ELSE 'Other'
    END as document_category

FROM fhir_prd_db.document_reference dr
LEFT JOIN document_content drc ON dr.id = drc.document_reference_id
LEFT JOIN document_categories drcat ON dr.id = drcat.document_reference_id
LEFT JOIN document_authors dra ON dr.id = dra.document_reference_id

WHERE dr.subject_reference IS NOT NULL
  AND (LOWER(dr.type_text) LIKE '%radiation%'
       OR LOWER(dr.type_text) LIKE '%rad%onc%'
       OR LOWER(dr.description) LIKE '%radiation%'
       OR LOWER(dr.description) LIKE '%rad%onc%')

ORDER BY dr.subject_reference, extraction_priority, dr.date DESC;

-- ================================================================================
-- END OF CONSOLIDATED RADIATION VIEWS
-- ================================================================================
