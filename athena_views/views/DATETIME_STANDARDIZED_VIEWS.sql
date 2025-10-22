-- ================================================================================
-- DATETIME STANDARDIZED ATHENA VIEWS
-- ================================================================================
-- Purpose: Standardize all VARCHAR datetime columns to proper temporal types
-- Date: 2025-10-19
--
-- CRITICAL CHANGES:
--   - VARCHAR datetime columns → TRY(CAST(... AS TIMESTAMP(3)))
--   - Graceful error handling with TRY() wrapper
--   - ALL other logic preserved 100% from original views
--
-- Source Analysis: /tmp/athena_views_datetime_analysis.json
-- Total Views: 24
-- Total VARCHAR Datetime Columns Converted: 102
--
-- DEPLOYMENT:
--   1. Review this file carefully before deployment
--   2. Test on development environment first
--   3. Deploy to production Athena
--   4. Validate data types and query results
-- ================================================================================


-- ================================================================================

-- VIEW: v_radiation_treatments
-- DATETIME STANDARDIZATION: 14 columns converted from VARCHAR
-- CHANGES:
--   - obs_start_date: VARCHAR → TIMESTAMP(3)
--   - obs_stop_date: VARCHAR → TIMESTAMP(3)
--   - obs_effective_date: VARCHAR → TIMESTAMP(3)
--   - obs_issued_date: VARCHAR → TIMESTAMP(3)
--   - sr_occurrence_date_time: VARCHAR → TIMESTAMP(3)
--   - sr_occurrence_period_start: VARCHAR → TIMESTAMP(3)
--   - sr_occurrence_period_end: VARCHAR → TIMESTAMP(3)
--   - sr_authored_on: VARCHAR → TIMESTAMP(3)
--   - apt_first_appointment_date: VARCHAR → TIMESTAMP(3)
--   - apt_last_appointment_date: VARCHAR → TIMESTAMP(3)
--   - cp_first_start_date: VARCHAR → TIMESTAMP(3)
--   - cp_last_end_date: VARCHAR → TIMESTAMP(3)
--   - best_treatment_start_date: VARCHAR → TIMESTAMP(3)
--   - best_treatment_stop_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
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
        TRY(CAST(osd.start_date_value AS TIMESTAMP(3))) as obs_start_date,
        TRY(CAST(ost.stop_date_value AS TIMESTAMP(3))) as obs_stop_date,

        -- Metadata (obs_ prefix)
        od.observation_status as obs_status,
        TRY(CAST(od.observation_effective_date AS TIMESTAMP(3))) as obs_effective_date,
        TRY(CAST(od.observation_issued_date AS TIMESTAMP(3))) as obs_issued_date,
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
        TRY(CAST(sr.occurrence_date_time AS TIMESTAMP(3))) as sr_occurrence_date_time,
        TRY(CAST(sr.occurrence_period_start AS TIMESTAMP(3))) as sr_occurrence_period_start,
        TRY(CAST(sr.occurrence_period_end AS TIMESTAMP(3))) as sr_occurrence_period_end,
        TRY(CAST(sr.authored_on AS TIMESTAMP(3))) as sr_authored_on,
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
        TRY(CAST(MIN(a.start) AS TIMESTAMP(3))) as first_appointment_date,
        TRY(CAST(MAX(a.start) AS TIMESTAMP(3))) as last_appointment_date,
        TRY(CAST(MIN(CASE WHEN a.status = 'fulfilled' THEN a.start END) AS TIMESTAMP(3))) as first_fulfilled_appointment,
        TRY(CAST(MAX(CASE WHEN a.status = 'fulfilled' THEN a.start END) AS TIMESTAMP(3))) as last_fulfilled_appointment
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
        TRY(CAST(MIN(cp.period_start) AS TIMESTAMP(3))) as first_care_plan_start,
        TRY(CAST(MAX(cp.period_end) AS TIMESTAMP(3))) as last_care_plan_end
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


-- ################################################################################
-- ################################################################################
-- 12. v_radiation_documents - DOCUMENT REFERENCES FOR NLP EXTRACTION
-- ################################################################################
-- ################################################################################
-- Copy everything from CREATE OR REPLACE VIEW to the semicolon ending this view


-- VIEW: v_concomitant_medications
-- DATETIME STANDARDIZATION: 8 columns converted from VARCHAR
-- CHANGES:
--   - chemo_start_datetime: VARCHAR → TIMESTAMP(3)
--   - chemo_stop_datetime: VARCHAR → TIMESTAMP(3)
--   - chemo_authored_datetime: VARCHAR → TIMESTAMP(3)
--   - conmed_start_datetime: VARCHAR → TIMESTAMP(3)
--   - conmed_stop_datetime: VARCHAR → TIMESTAMP(3)
--   - conmed_authored_datetime: VARCHAR → TIMESTAMP(3)
--   - overlap_start_datetime: VARCHAR → TIMESTAMP(3)
--   - overlap_stop_datetime: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_concomitant_medications AS
WITH
-- ================================================================================
-- Step 0: Get timing bounds from dosage instruction sub-schema
-- ================================================================================
medication_timing_bounds AS (
    SELECT
        medication_request_id,
        MIN(dosage_instruction_timing_repeat_bounds_period_start) as earliest_bounds_start,
        MAX(dosage_instruction_timing_repeat_bounds_period_end) as latest_bounds_end
    FROM fhir_prd_db.medication_request_dosage_instruction
    WHERE dosage_instruction_timing_repeat_bounds_period_start IS NOT NULL
       OR dosage_instruction_timing_repeat_bounds_period_end IS NOT NULL
    GROUP BY medication_request_id
),

-- ================================================================================
-- Step 1: Get chemotherapy medications and time windows from v_medications
-- ================================================================================
-- This ensures we use the SAME chemotherapy definition as the Python
-- ChemotherapyFilter and timeline database
-- ================================================================================
chemotherapy_agents AS (
    SELECT
        patient_fhir_id,
        medication_request_id as medication_fhir_id,
        medication_name,
        rx_norm_codes as rxnorm_cui,
        medication_status as status,
        mr_intent as intent,

        -- Use the standardized datetime fields from v_medications
        medication_start_date as start_datetime,
        mr_validity_period_end as stop_datetime,
        mr_authored_on as authored_datetime,

        -- Date source for quality tracking
        CASE
            WHEN mr_validity_period_start IS NOT NULL THEN 'timing_bounds'
            WHEN mr_validity_period_end IS NOT NULL THEN 'dispense_period'
            WHEN mr_authored_on IS NOT NULL THEN 'authored_on'
            ELSE 'missing'
        END as date_source

    FROM fhir_prd_db.v_medications
    -- This WHERE clause is CRITICAL - it limits to only chemotherapy medications
    -- that have already been filtered by the ChemotherapyFilter logic
    WHERE 1=1
        -- v_medications is already filtered to chemotherapy by the Python code
        -- that populates the timeline, so we don't need additional filtering here
        -- Just ensure we have valid time windows
        AND medication_start_date IS NOT NULL
),

-- ================================================================================
-- Step 2: Get ALL medications (unfiltered) with their time windows
-- ================================================================================
-- This CTE pulls from raw medication_request table to get EVERYTHING,
-- including supportive care, antibiotics, etc. that were filtered out
-- ================================================================================
all_medications AS (
    SELECT
        mr.subject_reference as patient_fhir_id,
        mr.id as medication_fhir_id,
        mcc.code_coding_code as rxnorm_cui,
        mcc.code_coding_display as medication_name,
        mr.status,
        mr.intent,

        -- Standardized start date (prefer timing bounds, fallback to authored_on)
        CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.earliest_bounds_start) = 10
                    THEN mtb.earliest_bounds_start || 'T00:00:00Z'
                    ELSE mtb.earliest_bounds_start
                END
            WHEN LENGTH(mr.authored_on) = 10
                THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END as start_datetime,

        -- Standardized stop date (prefer timing bounds, fallback to dispense validity period)
        CASE
            WHEN mtb.latest_bounds_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.latest_bounds_end) = 10
                    THEN mtb.latest_bounds_end || 'T00:00:00Z'
                    ELSE mtb.latest_bounds_end
                END
            WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mr.dispense_request_validity_period_end) = 10
                    THEN mr.dispense_request_validity_period_end || 'T00:00:00Z'
                    ELSE mr.dispense_request_validity_period_end
                END
            ELSE NULL
        END as stop_datetime,

        -- Authored date (order date)
        CASE
            WHEN LENGTH(mr.authored_on) = 10
            THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END as authored_datetime,

        -- Date source for quality tracking
        CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN 'timing_bounds'
            WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN 'dispense_period'
            WHEN mr.authored_on IS NOT NULL THEN 'authored_on'
            ELSE 'missing'
        END as date_source,

        -- Categorize medication by RxNorm code
        -- This helps identify what TYPE of concomitant medication it is
        CASE
            -- Antiemetics (nausea/vomiting prevention)
            WHEN mcc.code_coding_code IN ('26225', '4896', '288635', '135', '7533', '51272')
                THEN 'antiemetic'
            -- Corticosteroids (reduce swelling, prevent allergic reactions)
            WHEN mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
                THEN 'corticosteroid'
            -- Growth factors (stimulate blood cell production)
            WHEN mcc.code_coding_code IN ('105585', '358810', '4716', '139825')
                THEN 'growth_factor'
            -- Anticonvulsants (seizure prevention)
            WHEN mcc.code_coding_code IN ('35766', '11118', '6470', '2002', '8134', '114477')
                THEN 'anticonvulsant'
            -- Antimicrobials (infection prevention/treatment)
            WHEN mcc.code_coding_code IN ('161', '10831', '1043', '7454', '374056', '203')
                THEN 'antimicrobial'
            -- Proton pump inhibitors / GI protection
            WHEN mcc.code_coding_code IN ('7646', '29046', '40790', '8163')
                THEN 'gi_protection'
            -- Pain management
            WHEN mcc.code_coding_code IN ('7804', '7052', '5489', '6754', '237')
                THEN 'analgesic'
            -- H2 blockers
            WHEN mcc.code_coding_code IN ('8772', '10156', '4278')
                THEN 'h2_blocker'
            WHEN LOWER(mcc.code_coding_display) LIKE '%ondansetron%' OR LOWER(m.code_text) LIKE '%zofran%' THEN 'antiemetic'
            WHEN LOWER(mcc.code_coding_display) LIKE '%dexamethasone%' OR LOWER(m.code_text) LIKE '%prednisone%' THEN 'corticosteroid'
            WHEN LOWER(mcc.code_coding_display) LIKE '%filgrastim%' OR LOWER(m.code_text) LIKE '%neupogen%' THEN 'growth_factor'
            WHEN LOWER(mcc.code_coding_display) LIKE '%levetiracetam%' OR LOWER(m.code_text) LIKE '%keppra%' THEN 'anticonvulsant'
            ELSE 'other'
        END as medication_category

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN medication_timing_bounds mtb ON mr.id = mtb.medication_request_id
    LEFT JOIN fhir_prd_db.medication m ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')
        -- NO FILTERING OF DRUG TYPE HERE - we want ALL medications
)

-- ================================================================================
-- Step 3: Calculate temporal overlaps between chemotherapy and concomitant meds
-- ================================================================================
SELECT
    -- Patient identifier
    ca.patient_fhir_id,

    -- ============================================================================
    -- CHEMOTHERAPY AGENT DETAILS
    -- ============================================================================
    ca.medication_fhir_id as chemo_medication_fhir_id,
    ca.rxnorm_cui as chemo_rxnorm_cui,
    ca.medication_name as chemo_medication_name,
    ca.status as chemo_status,
    ca.intent as chemo_intent,

    -- Chemotherapy time window
    -- Chemotherapy time window
    TRY(CAST(ca.start_datetime AS TIMESTAMP(3))) as chemo_start_datetime,
    TRY(CAST(ca.stop_datetime AS TIMESTAMP(3))) as chemo_stop_datetime,
    TRY(CAST(ca.authored_datetime AS TIMESTAMP(3))) as chemo_authored_datetime,

    -- Chemotherapy duration in days
    CASE
        WHEN ca.stop_datetime IS NOT NULL AND ca.start_datetime IS NOT NULL
        THEN DATE_DIFF('day',
            CAST(SUBSTR(ca.start_datetime, 1, 10) AS DATE),
            CAST(SUBSTR(ca.stop_datetime, 1, 10) AS DATE))
        ELSE NULL
    END as chemo_duration_days,

    ca.date_source as chemo_date_source,
    CASE WHEN ca.rxnorm_cui IS NOT NULL THEN true ELSE false END as has_chemo_rxnorm,

    -- ============================================================================
    -- CONCOMITANT MEDICATION DETAILS
    -- ============================================================================
    am.medication_fhir_id as conmed_medication_fhir_id,
    am.rxnorm_cui as conmed_rxnorm_cui,
    am.medication_name as conmed_medication_name,
    am.status as conmed_status,
    am.intent as conmed_intent,

    -- Conmed time window
    -- Conmed time window
    TRY(CAST(am.start_datetime AS TIMESTAMP(3))) as conmed_start_datetime,
    TRY(CAST(am.stop_datetime AS TIMESTAMP(3))) as conmed_stop_datetime,
    TRY(CAST(am.authored_datetime AS TIMESTAMP(3))) as conmed_authored_datetime,

    -- Conmed duration in days
    CASE
        WHEN am.stop_datetime IS NOT NULL AND am.start_datetime IS NOT NULL
        THEN DATE_DIFF('day',
            CAST(SUBSTR(am.start_datetime, 1, 10) AS DATE),
            CAST(SUBSTR(am.stop_datetime, 1, 10) AS DATE))
        ELSE NULL
    END as conmed_duration_days,

    am.date_source as conmed_date_source,
    CASE WHEN am.rxnorm_cui IS NOT NULL THEN true ELSE false END as has_conmed_rxnorm,

    -- Conmed categorization
    am.medication_category as conmed_category,

    -- ============================================================================
    -- TEMPORAL OVERLAP DETAILS
    -- ============================================================================

    -- Overlap start (later of the two start dates)
    TRY(CAST(CASE
        WHEN ca.start_datetime >= am.start_datetime THEN ca.start_datetime
        ELSE am.start_datetime
    END AS TIMESTAMP(3))) as overlap_start_datetime,
    -- Overlap stop (earlier of the two stop dates, or NULL if either is NULL)
    TRY(CAST(CASE
        WHEN ca.stop_datetime IS NULL OR am.stop_datetime IS NULL THEN NULL
        WHEN ca.stop_datetime <= am.stop_datetime THEN ca.stop_datetime
        ELSE am.stop_datetime
    END AS TIMESTAMP(3))) as overlap_stop_datetime,

    -- Overlap duration in days
    CASE
        WHEN ca.stop_datetime IS NOT NULL AND am.stop_datetime IS NOT NULL
            AND ca.start_datetime IS NOT NULL AND am.start_datetime IS NOT NULL
        THEN DATE_DIFF('day',
            CAST(SUBSTR(GREATEST(ca.start_datetime, am.start_datetime), 1, 10) AS DATE),
            CAST(SUBSTR(LEAST(ca.stop_datetime, am.stop_datetime), 1, 10) AS DATE))
        ELSE NULL
    END as overlap_duration_days,

    -- Overlap type classification
    CASE
        -- Conmed entirely during chemo window
        WHEN am.start_datetime >= ca.start_datetime
            AND (am.stop_datetime IS NULL OR (ca.stop_datetime IS NOT NULL AND am.stop_datetime <= ca.stop_datetime))
            THEN 'during_chemo'
        -- Conmed started during chemo but may extend beyond
        WHEN am.start_datetime >= ca.start_datetime
            AND (ca.stop_datetime IS NULL OR am.start_datetime <= ca.stop_datetime)
            THEN 'started_during_chemo'
        -- Conmed stopped during chemo but started before
        WHEN am.stop_datetime IS NOT NULL
            AND ca.stop_datetime IS NOT NULL
            AND am.stop_datetime >= ca.start_datetime
            AND am.stop_datetime <= ca.stop_datetime
            THEN 'stopped_during_chemo'
        -- Conmed spans entire chemo period
        WHEN am.start_datetime <= ca.start_datetime
            AND (am.stop_datetime IS NULL OR (ca.stop_datetime IS NOT NULL AND am.stop_datetime >= ca.stop_datetime))
            THEN 'spans_chemo'
        ELSE 'partial_overlap'
    END as overlap_type,

    -- Data quality indicators
    CASE
        WHEN ca.date_source = 'timing_bounds' AND am.date_source = 'timing_bounds' THEN 'high'
        WHEN ca.date_source = 'timing_bounds' OR am.date_source = 'timing_bounds' THEN 'medium'
        WHEN ca.date_source = 'dispense_period' AND am.date_source = 'dispense_period' THEN 'medium'
        ELSE 'low'
    END as date_quality

FROM chemotherapy_agents ca
INNER JOIN all_medications am
    ON ca.patient_fhir_id = am.patient_fhir_id
    -- CRITICAL: Exclude the chemotherapy medication itself from concomitant list
    AND ca.medication_fhir_id != am.medication_fhir_id
WHERE
    -- Temporal overlap condition: periods must overlap
    -- Condition 1: conmed starts during chemo
    (
        am.start_datetime >= ca.start_datetime
        AND (ca.stop_datetime IS NULL OR am.start_datetime <= ca.stop_datetime)
    )
    -- Condition 2: conmed stops during chemo
    OR (
        am.stop_datetime IS NOT NULL
        AND ca.stop_datetime IS NOT NULL
        AND am.stop_datetime >= ca.start_datetime
        AND am.stop_datetime <= ca.stop_datetime
    )
    -- Condition 3: conmed spans entire chemo period
    OR (
        am.start_datetime <= ca.start_datetime
        AND (am.stop_datetime IS NULL OR (ca.stop_datetime IS NOT NULL AND am.stop_datetime >= ca.stop_datetime))
    )


-- VIEW: v_hydrocephalus_diagnosis
-- DATETIME STANDARDIZATION: 9 columns converted from VARCHAR
-- CHANGES:
--   - cond_abatement_datetime: VARCHAR → TIMESTAMP(3)
--   - cond_onset_datetime: VARCHAR → TIMESTAMP(3)
--   - cond_onset_period_end: VARCHAR → TIMESTAMP(3)
--   - cond_onset_period_start: VARCHAR → TIMESTAMP(3)
--   - cond_recorded_date: VARCHAR → TIMESTAMP(3)
--   - hydro_event_date: VARCHAR → TIMESTAMP(3)
--   - img_first_date: VARCHAR → TIMESTAMP(3)
--   - img_most_recent_date: VARCHAR → TIMESTAMP(3)
--   - sr_first_order_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_hydrocephalus_diagnosis AS
WITH
-- All hydrocephalus conditions from condition table (5,735 records vs 427 in problem_list)
hydro_conditions AS (
    SELECT
        c.id as condition_id,
        c.subject_reference as patient_fhir_id,
        ccc.code_coding_code as icd10_code,
        ccc.code_coding_display as diagnosis_display,
        ccc.code_coding_system as code_system,
        c.code_text as condition_text,
        c.onset_date_time,
        c.onset_period_start,
        c.onset_period_end,
        c.abatement_date_time,
        c.recorded_date,
        c.clinical_status_text,
        c.verification_status_text,

        -- Hydrocephalus type classification from ICD-10
        CASE
            WHEN ccc.code_coding_code LIKE 'G91.0%' THEN 'Communicating'
            WHEN ccc.code_coding_code LIKE 'G91.1%' THEN 'Obstructive'
            WHEN ccc.code_coding_code LIKE 'G91.2%' THEN 'Normal-pressure'
            WHEN ccc.code_coding_code LIKE 'G91.3%' THEN 'Post-traumatic'
            WHEN ccc.code_coding_code LIKE 'G91.8%' THEN 'Other'
            WHEN ccc.code_coding_code LIKE 'G91.9%' THEN 'Unspecified'
            WHEN ccc.code_coding_code LIKE 'Q03%' THEN 'Congenital'
            ELSE 'Unclassified'
        END as hydrocephalus_type

    FROM fhir_prd_db.condition c
    INNER JOIN fhir_prd_db.condition_code_coding ccc
        ON c.id = ccc.condition_id
    WHERE (
        ccc.code_coding_code LIKE 'G91%'
        OR ccc.code_coding_code LIKE 'Q03%'
        OR LOWER(ccc.code_coding_display) LIKE '%hydroceph%'
    )
),

-- Diagnosis category classification (Problem List, Encounter, Admission, etc.)
condition_categories AS (
    SELECT
        cc.condition_id,
        LISTAGG(DISTINCT cc.category_text, ' | ') WITHIN GROUP (ORDER BY cc.category_text) as category_types,

        -- Is this an active/current condition?
        MAX(CASE
            WHEN cc.category_text IN ('Problem List Item', 'Encounter Diagnosis', 'Admission Diagnosis') THEN true
            ELSE false
        END) as is_active_diagnosis,

        -- Individual category flags
        MAX(CASE WHEN cc.category_text = 'Problem List Item' THEN true ELSE false END) as is_problem_list,
        MAX(CASE WHEN cc.category_text = 'Encounter Diagnosis' THEN true ELSE false END) as is_encounter_diagnosis,
        MAX(CASE WHEN cc.category_text = 'Admission Diagnosis' THEN true ELSE false END) as is_admission_diagnosis,
        MAX(CASE WHEN cc.category_text = 'Discharge Diagnosis' THEN true ELSE false END) as is_discharge_diagnosis,
        MAX(CASE WHEN cc.category_text = 'Medical History' THEN true ELSE false END) as is_medical_history

    FROM fhir_prd_db.condition_category cc
    WHERE cc.condition_id IN (SELECT condition_id FROM hydro_conditions)
    GROUP BY cc.condition_id
),

-- Imaging studies documenting hydrocephalus
hydro_imaging AS (
    SELECT
        dr.subject_reference as patient_fhir_id,
        dr.id as report_id,
        dr.code_text as study_type,
        dr.effective_date_time as imaging_date,
        dr.conclusion,

        -- Imaging modality classification
        CASE
            WHEN LOWER(dr.code_text) LIKE '%ct%'
                 OR LOWER(dr.code_text) LIKE '%computed%tomography%' THEN 'CT'
            WHEN LOWER(dr.code_text) LIKE '%mri%'
                 OR LOWER(dr.code_text) LIKE '%magnetic%resonance%' THEN 'MRI'
            WHEN LOWER(dr.code_text) LIKE '%ultrasound%' THEN 'Ultrasound'
            ELSE 'Other'
        END as imaging_modality

    FROM fhir_prd_db.diagnostic_report dr
    WHERE dr.subject_reference IS NOT NULL
      AND (
          LOWER(dr.code_text) LIKE '%brain%'
          OR LOWER(dr.code_text) LIKE '%head%'
          OR LOWER(dr.code_text) LIKE '%cranial%'
      )
      AND (
          LOWER(dr.conclusion) LIKE '%hydroceph%'
          OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
          OR LOWER(dr.conclusion) LIKE '%enlarged%ventricle%'
          OR LOWER(dr.conclusion) LIKE '%ventricular%dilation%'
      )
),

-- Aggregate imaging per patient
imaging_summary AS (
    SELECT
        patient_fhir_id,
        LISTAGG(DISTINCT imaging_modality, ' | ') WITHIN GROUP (ORDER BY imaging_modality) as imaging_modalities,
        COUNT(DISTINCT report_id) as total_imaging_studies,
        COUNT(DISTINCT CASE WHEN imaging_modality = 'CT' THEN report_id END) as ct_studies,
        COUNT(DISTINCT CASE WHEN imaging_modality = 'MRI' THEN report_id END) as mri_studies,
        COUNT(DISTINCT CASE WHEN imaging_modality = 'Ultrasound' THEN report_id END) as ultrasound_studies,
        MIN(imaging_date) as first_imaging_date,
        MAX(imaging_date) as most_recent_imaging_date
    FROM hydro_imaging
    GROUP BY patient_fhir_id
),

-- Service requests for hydrocephalus imaging (validates diagnosis method)
imaging_orders AS (
    SELECT
        sr.subject_reference as patient_fhir_id,
        COUNT(DISTINCT sr.id) as total_imaging_orders,
        COUNT(DISTINCT CASE WHEN LOWER(sr.code_text) LIKE '%ct%' THEN sr.id END) as ct_orders,
        COUNT(DISTINCT CASE WHEN LOWER(sr.code_text) LIKE '%mri%' THEN sr.id END) as mri_orders,
        MIN(sr.occurrence_date_time) as first_order_date

    FROM fhir_prd_db.service_request sr
    INNER JOIN fhir_prd_db.service_request_reason_code src
        ON sr.id = src.service_request_id
    WHERE (
        LOWER(sr.code_text) LIKE '%ct%'
        OR LOWER(sr.code_text) LIKE '%mri%'
        OR LOWER(sr.code_text) LIKE '%ultrasound%'
    )
    AND (
        LOWER(src.reason_code_text) LIKE '%hydroceph%'
        OR LOWER(src.reason_code_text) LIKE '%ventriculomegaly%'
        OR LOWER(src.reason_code_text) LIKE '%increased%intracranial%pressure%'
    )
    GROUP BY sr.subject_reference
)

-- Main SELECT: Combine all diagnosis data
SELECT
    -- Patient identifier
    hc.patient_fhir_id,

    -- Condition fields (cond_ prefix)
    hc.condition_id as cond_id,
    hc.icd10_code as cond_icd10_code,
    hc.diagnosis_display as cond_diagnosis_display,
    hc.condition_text as cond_text,
    hc.code_system as cond_code_system,
    hc.hydrocephalus_type as cond_hydro_type,
    hc.clinical_status_text as cond_clinical_status,
    hc.verification_status_text as cond_verification_status,

    -- All date fields
    TRY(CAST(hc.onset_date_time AS TIMESTAMP(3))) as cond_onset_datetime,
    TRY(CAST(hc.onset_period_start AS TIMESTAMP(3))) as cond_onset_period_start,
    TRY(CAST(hc.onset_period_end AS TIMESTAMP(3))) as cond_onset_period_end,
    TRY(CAST(hc.abatement_date_time AS TIMESTAMP(3))) as cond_abatement_datetime,
    TRY(CAST(hc.recorded_date AS TIMESTAMP(3))) as cond_recorded_date,

    -- Diagnosis category fields (cat_ prefix)
    cc.category_types as cat_all_categories,
    cc.is_active_diagnosis as cat_is_active,
    cc.is_problem_list as cat_is_problem_list,
    cc.is_encounter_diagnosis as cat_is_encounter_dx,
    cc.is_admission_diagnosis as cat_is_admission_dx,
    cc.is_discharge_diagnosis as cat_is_discharge_dx,
    cc.is_medical_history as cat_is_medical_history,

    -- Imaging summary fields (img_ prefix)
    img.imaging_modalities as img_modalities,
    img.total_imaging_studies as img_total_studies,
    img.ct_studies as img_ct_count,
    img.mri_studies as img_mri_count,
    img.ultrasound_studies as img_ultrasound_count,
    TRY(CAST(img.first_imaging_date AS TIMESTAMP(3))) as img_first_date,
    TRY(CAST(img.most_recent_imaging_date AS TIMESTAMP(3))) as img_most_recent_date,

    -- Service request fields (sr_ prefix)
    io.total_imaging_orders as sr_total_orders,
    io.ct_orders as sr_ct_orders,
    io.mri_orders as sr_mri_orders,
    TRY(CAST(io.first_order_date AS TIMESTAMP(3))) as sr_first_order_date,

    -- ============================================================================
    -- CBTN FIELD MAPPINGS
    -- ============================================================================

    -- hydro_yn (always true for this view)
    true as hydro_yn,

    -- hydro_event_date (onset date)
    TRY(CAST(COALESCE(hc.onset_date_time, hc.onset_period_start, hc.recorded_date) AS TIMESTAMP(3))) as hydro_event_date,

    -- hydro_method_diagnosed (CT, MRI, Clinical, Other)
    CASE
        WHEN img.ct_studies > 0 AND img.mri_studies > 0 THEN 'CT and MRI'
        WHEN img.ct_studies > 0 THEN 'CT'
        WHEN img.mri_studies > 0 THEN 'MRI'
        WHEN img.ultrasound_studies > 0 THEN 'Ultrasound'
        WHEN img.total_imaging_studies > 0 THEN 'Imaging (Other)'
        ELSE 'Clinical'
    END as hydro_method_diagnosed,

    -- medical_conditions_present_at_event(11) - Hydrocephalus checkbox
    CASE
        WHEN cc.is_active_diagnosis = true THEN true
        WHEN hc.clinical_status_text = 'active' THEN true
        ELSE false
    END as medical_condition_hydrocephalus_present,

    -- ============================================================================
    -- DATA QUALITY INDICATORS
    -- ============================================================================

    CASE WHEN hc.icd10_code IS NOT NULL THEN true ELSE false END as has_icd10_code,
    CASE WHEN hc.onset_date_time IS NOT NULL OR hc.onset_period_start IS NOT NULL THEN true ELSE false END as has_onset_date,
    CASE WHEN img.total_imaging_studies > 0 THEN true ELSE false END as has_imaging_documentation,
    CASE WHEN io.total_imaging_orders > 0 THEN true ELSE false END as has_imaging_orders,
    CASE WHEN hc.verification_status_text = 'confirmed' THEN true ELSE false END as is_confirmed_diagnosis,
    CASE WHEN cc.is_problem_list = true THEN true ELSE false END as on_problem_list

FROM hydro_conditions hc
LEFT JOIN condition_categories cc ON hc.condition_id = cc.condition_id
LEFT JOIN imaging_summary img ON hc.patient_fhir_id = img.patient_fhir_id
LEFT JOIN imaging_orders io ON hc.patient_fhir_id = io.patient_fhir_id

ORDER BY hc.patient_fhir_id, hc.onset_date_time;

-- ================================================================================
-- VIEW: v_autologous_stem_cell_transplant
-- DATETIME STANDARDIZATION: 7 columns converted from VARCHAR
-- CHANGES:
--   - cd34_collection_datetime: VARCHAR → TIMESTAMP(3)
--   - cond_onset_datetime: VARCHAR → TIMESTAMP(3)
--   - cond_recorded_datetime: VARCHAR → TIMESTAMP(3)
--   - obs_transplant_datetime: VARCHAR → TIMESTAMP(3)
--   - proc_performed_datetime: VARCHAR → TIMESTAMP(3)
--   - proc_period_start: VARCHAR → TIMESTAMP(3)
--   - transplant_datetime: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_transplant AS
WITH
-- 1. Transplant status from condition table (HIGHEST YIELD: 1,981 records)
transplant_conditions AS (
    SELECT
        c.subject_reference as patient_fhir_id,
        c.id as condition_id,
        ccc.code_coding_code as icd10_code,
        ccc.code_coding_display as diagnosis,

        -- Standardized dates (append T00:00:00Z if date-only)
        CASE
            WHEN LENGTH(c.onset_date_time) = 10 THEN c.onset_date_time || 'T00:00:00Z'
            ELSE c.onset_date_time
        END as condition_onset,
        CASE
            WHEN LENGTH(c.recorded_date) = 10 THEN c.recorded_date || 'T00:00:00Z'
            ELSE c.recorded_date
        END as recorded_date,

        -- Autologous flag from ICD-10 codes
        CASE
            WHEN ccc.code_coding_code = '108631000119101' THEN true  -- History of autologous BMT
            WHEN ccc.code_coding_code = '848081' THEN true           -- History of autologous SCT
            WHEN LOWER(ccc.code_coding_display) LIKE '%autologous%' THEN true
            ELSE false
        END as confirmed_autologous,

        -- Confidence level
        CASE
            WHEN ccc.code_coding_code IN ('108631000119101', '848081') THEN 'high'
            WHEN LOWER(ccc.code_coding_display) LIKE '%autologous%' THEN 'medium'
            ELSE 'low'
        END as confidence_level,

        'condition' as data_source

    FROM fhir_prd_db.condition c
    INNER JOIN fhir_prd_db.condition_code_coding ccc
        ON c.id = ccc.condition_id
    WHERE ccc.code_coding_code IN ('Z94.84', 'Z94.81', '108631000119101', '848081', 'V42.82', 'V42.81')
       OR LOWER(ccc.code_coding_display) LIKE '%stem%cell%transplant%'
),

-- 2. Transplant procedures (19 records, 17 patients)
transplant_procedures AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        p.id as procedure_id,
        p.code_text as procedure_description,
        pcc.code_coding_code as cpt_code,

        -- Standardized dates
        CASE
            WHEN LENGTH(p.performed_date_time) = 10 THEN p.performed_date_time || 'T00:00:00Z'
            ELSE p.performed_date_time
        END as procedure_date,
        CASE
            WHEN LENGTH(p.performed_period_start) = 10 THEN p.performed_period_start || 'T00:00:00Z'
            ELSE p.performed_period_start
        END as performed_period_start,

        -- Autologous flag from CPT codes or text
        CASE
            WHEN LOWER(p.code_text) LIKE '%autologous%' THEN true
            WHEN pcc.code_coding_code = '38241' THEN true  -- Autologous CPT
            ELSE false
        END as confirmed_autologous,

        -- Confidence level
        CASE
            WHEN pcc.code_coding_code = '38241' THEN 'high'
            WHEN LOWER(p.code_text) LIKE '%autologous%' THEN 'medium'
            ELSE 'low'
        END as confidence_level,

        'procedure' as data_source

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pcc
        ON p.id = pcc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%stem%cell%'
        OR LOWER(p.code_text) LIKE '%autologous%'
        OR LOWER(p.code_text) LIKE '%bone%marrow%transplant%'
        OR pcc.code_coding_code IN ('38241', '38240')
    )
    AND p.status = 'completed'
),

-- 3. Transplant date from observations (359 exact dates)
transplant_dates_obs AS (
    SELECT
        o.subject_reference as patient_fhir_id,

        -- Standardized dates
        CASE
            WHEN LENGTH(o.effective_date_time) = 10 THEN o.effective_date_time || 'T00:00:00Z'
            ELSE o.effective_date_time
        END as transplant_date,
        o.value_string as transplant_date_value,

        'observation' as data_source

    FROM fhir_prd_db.observation o
    WHERE LOWER(o.code_text) LIKE '%hematopoietic%stem%cell%transplant%transplant%date%'
       OR LOWER(o.code_text) LIKE '%stem%cell%transplant%date%'
),

-- 4. CD34+ counts (validates stem cell collection/engraftment)
cd34_counts AS (
    SELECT
        o.subject_reference as patient_fhir_id,

        -- Standardized dates
        CASE
            WHEN LENGTH(o.effective_date_time) = 10 THEN o.effective_date_time || 'T00:00:00Z'
            ELSE o.effective_date_time
        END as collection_date,
        o.value_quantity_value as cd34_count,
        o.value_quantity_unit as unit,

        'cd34_count' as data_source

    FROM fhir_prd_db.observation o
    WHERE LOWER(o.code_text) LIKE '%cd34%'
)

-- MAIN SELECT: Combine all data sources
SELECT
    COALESCE(tc.patient_fhir_id, tp.patient_fhir_id, tdo.patient_fhir_id, cd34.patient_fhir_id) as patient_fhir_id,

    -- Condition data (transplant status)
    tc.condition_id as cond_id,
    tc.icd10_code as cond_icd10_code,
    tc.diagnosis as cond_transplant_status,
    TRY(CAST(tc.condition_onset AS TIMESTAMP(3))) as cond_onset_datetime,
    TRY(CAST(tc.recorded_date AS TIMESTAMP(3))) as cond_recorded_datetime,
    tc.confirmed_autologous as cond_autologous_flag,
    tc.confidence_level as cond_confidence,

    -- Procedure data
    tp.procedure_id as proc_id,
    tp.procedure_description as proc_description,
    tp.cpt_code as proc_cpt_code,
    TRY(CAST(tp.procedure_date AS TIMESTAMP(3))) as proc_performed_datetime,
    TRY(CAST(tp.performed_period_start AS TIMESTAMP(3))) as proc_period_start,
    tp.confirmed_autologous as proc_autologous_flag,
    tp.confidence_level as proc_confidence,

    -- Transplant date from observation
    TRY(CAST(tdo.transplant_date AS TIMESTAMP(3))) as obs_transplant_datetime,
    tdo.transplant_date_value as obs_transplant_value,

    -- CD34 count data (validates stem cell collection)
    TRY(CAST(cd34.collection_date AS TIMESTAMP(3))) as cd34_collection_datetime,
    cd34.cd34_count as cd34_count_value,
    cd34.unit as cd34_unit,

    -- Best available transplant date
    TRY(CAST(COALESCE(tp.procedure_date, tdo.transplant_date, tc.condition_onset) AS TIMESTAMP(3))) as transplant_datetime,

    -- Confirmed autologous flag (HIGH confidence)
    CASE
        WHEN tc.confirmed_autologous = true OR tp.confirmed_autologous = true THEN true
        ELSE false
    END as confirmed_autologous,

    -- Overall confidence level
    CASE
        WHEN tc.confidence_level = 'high' OR tp.confidence_level = 'high' THEN 'high'
        WHEN tc.confidence_level = 'medium' OR tp.confidence_level = 'medium' THEN 'medium'
        ELSE 'low'
    END as overall_confidence,

    -- Data sources present (for validation)
    CASE WHEN tc.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_condition_data,
    CASE WHEN tp.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_procedure_data,
    CASE WHEN tdo.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_transplant_date_obs,
    CASE WHEN cd34.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_cd34_data,

    -- Data quality score (0-4 based on sources present)
    (CASE WHEN tc.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN tp.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN tdo.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN cd34.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END) as data_completeness_score

FROM transplant_conditions tc
FULL OUTER JOIN transplant_procedures tp
    ON tc.patient_fhir_id = tp.patient_fhir_id
FULL OUTER JOIN transplant_dates_obs tdo
    ON COALESCE(tc.patient_fhir_id, tp.patient_fhir_id) = tdo.patient_fhir_id
FULL OUTER JOIN cd34_counts cd34
    ON COALESCE(tc.patient_fhir_id, tp.patient_fhir_id, tdo.patient_fhir_id) = cd34.patient_fhir_id

WHERE COALESCE(tc.patient_fhir_id, tp.patient_fhir_id, tdo.patient_fhir_id, cd34.patient_fhir_id) IS NOT NULL

ORDER BY patient_fhir_id, transplant_datetime;

-- ================================================================================
-- VIEW: v_medications
-- DATETIME STANDARDIZATION: 7 columns converted from VARCHAR
-- CHANGES:
--   - cp_created: VARCHAR → TIMESTAMP(3)
--   - cp_period_end: VARCHAR → TIMESTAMP(3)
--   - cp_period_start: VARCHAR → TIMESTAMP(3)
--   - medication_start_date: VARCHAR → TIMESTAMP(3)
--   - mr_authored_on: VARCHAR → TIMESTAMP(3)
--   - mr_validity_period_end: VARCHAR → TIMESTAMP(3)
--   - mr_validity_period_start: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_medications AS
WITH medication_notes AS (
    SELECT
        medication_request_id,
        LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_text) as note_text_aggregated
    FROM fhir_prd_db.medication_request_note
    GROUP BY medication_request_id
),
medication_reasons AS (
    SELECT
        medication_request_id,
        LISTAGG(reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
    FROM fhir_prd_db.medication_request_reason_code
    GROUP BY medication_request_id
),
medication_forms AS (
    SELECT
        medication_id,
        LISTAGG(DISTINCT form_coding_code, ' | ') WITHIN GROUP (ORDER BY form_coding_code) as form_coding_codes,
        LISTAGG(DISTINCT form_coding_display, ' | ') WITHIN GROUP (ORDER BY form_coding_display) as form_coding_displays
    FROM fhir_prd_db.medication_form_coding
    GROUP BY medication_id
),
medication_ingredients AS (
    SELECT
        medication_id,
        LISTAGG(DISTINCT CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit, ' | ')
            WITHIN GROUP (ORDER BY CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit) as ingredient_strengths
    FROM fhir_prd_db.medication_ingredient
    WHERE ingredient_strength_numerator_value IS NOT NULL
    GROUP BY medication_id
),
medication_dosage_instructions AS (
    SELECT
        medication_request_id,
        -- Route information (CRITICAL for chemotherapy analysis)
        LISTAGG(DISTINCT dosage_instruction_route_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_route_text) as route_text_aggregated,
        -- Method (e.g., IV push, IV drip)
        LISTAGG(DISTINCT dosage_instruction_method_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_method_text) as method_text_aggregated,
        -- Full dosage instruction text
        LISTAGG(dosage_instruction_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_sequence) as dosage_text_aggregated,
        -- Site (e.g., port, peripheral line)
        LISTAGG(DISTINCT dosage_instruction_site_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_site_text) as site_text_aggregated,
        -- Patient instructions
        LISTAGG(DISTINCT dosage_instruction_patient_instruction, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_patient_instruction) as patient_instruction_aggregated,
        -- Timing information
        LISTAGG(DISTINCT dosage_instruction_timing_code_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_timing_code_text) as timing_code_aggregated
    FROM fhir_prd_db.medication_request_dosage_instruction
    GROUP BY medication_request_id
),
care_plan_categories AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as categories_aggregated
    FROM fhir_prd_db.care_plan_category
    GROUP BY care_plan_id
),
care_plan_conditions AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT addresses_display, ' | ') WITHIN GROUP (ORDER BY addresses_display) as addresses_aggregated
    FROM fhir_prd_db.care_plan_addresses
    GROUP BY care_plan_id
),
medication_based_on AS (
    -- Aggregate multiple care plans per medication to prevent JOIN explosion
    SELECT
        medication_request_id,
        LISTAGG(DISTINCT based_on_reference, ' | ') WITHIN GROUP (ORDER BY based_on_reference) AS based_on_references,
        LISTAGG(DISTINCT based_on_display, ' | ') WITHIN GROUP (ORDER BY based_on_display) AS based_on_displays,
        MIN(based_on_reference) AS primary_care_plan_id  -- pick one for downstream joins
    FROM fhir_prd_db.medication_request_based_on
    GROUP BY medication_request_id
),
care_plan_activity_agg AS (
    -- Aggregate multiple activities per care plan to prevent JOIN explosion
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT activity_detail_status, ' | ')
            WITHIN GROUP (ORDER BY activity_detail_status) AS activity_detail_statuses,
        LISTAGG(DISTINCT activity_detail_description, ' | ')
            WITHIN GROUP (ORDER BY activity_detail_description) AS activity_detail_descriptions
    FROM fhir_prd_db.care_plan_activity
    GROUP BY care_plan_id
)
SELECT
    -- Patient info
    pm.patient_id as patient_fhir_id,

    -- Patient_medications view fields (no prefix for backward compatibility)
    pm.medication_request_id,
    pm.medication_id,
    pm.medication_name,
    pm.form_text as medication_form,
    pm.rx_norm_codes,
    TRY(CAST(pm.authored_on AS TIMESTAMP(3))) as medication_start_date,
    pm.requester_name,
    pm.status as medication_status,
    pm.encounter_display,

    -- Medication_request fields (mr_ prefix) - matched to working Python script
    TRY(CAST(mr.dispense_request_validity_period_start AS TIMESTAMP(3))) as mr_validity_period_start,
    TRY(CAST(mr.dispense_request_validity_period_end AS TIMESTAMP(3))) as mr_validity_period_end,
    TRY(CAST(mr.authored_on AS TIMESTAMP(3))) as mr_authored_on,
    mr.status as mr_status,
    mr.status_reason_text as mr_status_reason_text,
    mr.priority as mr_priority,
    mr.intent as mr_intent,
    mr.do_not_perform as mr_do_not_perform,
    mr.course_of_therapy_type_text as mr_course_of_therapy_type_text,
    mr.dispense_request_initial_fill_duration_value as mr_dispense_initial_fill_duration_value,
    mr.dispense_request_initial_fill_duration_unit as mr_dispense_initial_fill_duration_unit,
    mr.dispense_request_expected_supply_duration_value as mr_dispense_expected_supply_duration_value,
    mr.dispense_request_expected_supply_duration_unit as mr_dispense_expected_supply_duration_unit,
    mr.dispense_request_number_of_repeats_allowed as mr_dispense_number_of_repeats_allowed,
    mr.substitution_allowed_boolean as mr_substitution_allowed_boolean,
    mr.substitution_reason_text as mr_substitution_reason_text,
    mr.prior_prescription_display as mr_prior_prescription_display,

    -- Aggregated notes (mrn_ prefix)
    mrn.note_text_aggregated as mrn_note_text_aggregated,

    -- Aggregated reason codes (mrr_ prefix)
    mrr.reason_code_text_aggregated as mrr_reason_code_text_aggregated,

    -- Based-on references (mrb_ prefix - care plan linkage) - AGGREGATED
    mrb.based_on_references as mrb_care_plan_references,
    mrb.based_on_displays as mrb_care_plan_displays,
    mrb.primary_care_plan_id as mrb_primary_care_plan_id,

    -- Dosage instruction fields (mrdi_ prefix) - CRITICAL FOR ROUTE ANALYSIS
    mrdi.route_text_aggregated as mrdi_route_text,
    mrdi.method_text_aggregated as mrdi_method_text,
    mrdi.dosage_text_aggregated as mrdi_dosage_text,
    mrdi.site_text_aggregated as mrdi_site_text,
    mrdi.patient_instruction_aggregated as mrdi_patient_instruction,
    mrdi.timing_code_aggregated as mrdi_timing_code,

    -- Form coding (mf_ prefix)
    mf.form_coding_codes as mf_form_coding_codes,
    mf.form_coding_displays as mf_form_coding_displays,

    -- Ingredients (mi_ prefix)
    mi.ingredient_strengths as mi_ingredient_strengths,

    -- Care plan info (cp_ prefix) - linked via based_on
    cp.id as cp_id,
    cp.title as cp_title,
    cp.status as cp_status,
    cp.intent as cp_intent,
    TRY(CAST(cp.created AS TIMESTAMP(3))) as cp_created,
    TRY(CAST(cp.period_start AS TIMESTAMP(3))) as cp_period_start,
    TRY(CAST(cp.period_end AS TIMESTAMP(3))) as cp_period_end,
    cp.author_display as cp_author_display,

    -- Care plan categories (cpc_ prefix)
    cpc.categories_aggregated as cpc_categories_aggregated,

    -- Care plan conditions (cpcon_ prefix)
    cpcon.addresses_aggregated as cpcon_addresses_aggregated,

    -- Care plan activity (cpa_ prefix) - AGGREGATED
    cpa.activity_detail_statuses as cpa_activity_detail_statuses,
    cpa.activity_detail_descriptions as cpa_activity_detail_descriptions

FROM fhir_prd_db.patient_medications pm
LEFT JOIN fhir_prd_db.medication_request mr ON pm.medication_request_id = mr.id
LEFT JOIN medication_notes mrn ON mr.id = mrn.medication_request_id
LEFT JOIN medication_reasons mrr ON mr.id = mrr.medication_request_id
LEFT JOIN medication_based_on mrb ON mr.id = mrb.medication_request_id  -- AGGREGATED CTE
LEFT JOIN medication_dosage_instructions mrdi ON mr.id = mrdi.medication_request_id
LEFT JOIN medication_forms mf ON pm.medication_id = mf.medication_id
LEFT JOIN medication_ingredients mi ON pm.medication_id = mi.medication_id
LEFT JOIN fhir_prd_db.care_plan cp ON mrb.primary_care_plan_id = cp.id  -- Use primary_care_plan_id
LEFT JOIN care_plan_categories cpc ON cp.id = cpc.care_plan_id
LEFT JOIN care_plan_conditions cpcon ON cp.id = cpcon.care_plan_id
LEFT JOIN care_plan_activity_agg cpa ON cp.id = cpa.care_plan_id  -- AGGREGATED CTE
WHERE pm.patient_id IS NOT NULL
ORDER BY pm.patient_id, pm.authored_on;

-- ================================================================================
-- VIEW: v_procedures_tumor
-- DATETIME STANDARDIZATION: 6 columns converted from VARCHAR
-- CHANGES:
--   - proc_performed_age_unit: VARCHAR → TIMESTAMP(3)
--   - proc_performed_age_value: VARCHAR → TIMESTAMP(3)
--   - proc_performed_date_time: VARCHAR → TIMESTAMP(3)
--   - proc_performed_period_end: VARCHAR → TIMESTAMP(3)
--   - proc_performed_period_start: VARCHAR → TIMESTAMP(3)
--   - proc_performed_string: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_procedures_tumor AS
WITH
cpt_classifications AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as cpt_code,
        pcc.code_coding_display as cpt_display,

        CASE
            -- TIER 1: DIRECT TUMOR RESECTION
            WHEN pcc.code_coding_code IN (
                '61500',  -- Craniectomy tumor/lesion skull
                '61510',  -- Craniotomy bone flap brain tumor supratentorial
                '61512',  -- Craniotomy bone flap meningioma supratentorial
                '61516',  -- Craniotomy bone flap cyst fenestration supratentorial
                '61518',  -- Craniotomy brain tumor infratentorial/posterior fossa
                '61519',  -- Craniotomy meningioma infratentorial
                '61520',  -- Craniotomy tumor cerebellopontine angle
                '61521',  -- Craniotomy tumor midline skull base
                '61524',  -- Craniotomy infratentorial cyst excision/fenestration
                '61545',  -- Craniotomy excision craniopharyngioma
                '61546',  -- Craniotomy hypophysectomy/excision pituitary tumor
                '61548'   -- Hypophysectomy/excision pituitary tumor transsphenoidal
            ) THEN 'craniotomy_tumor_resection'

            WHEN pcc.code_coding_code IN (
                '61750',  -- Stereotactic biopsy aspiration intracranial
                '61751',  -- Stereotactic biopsy excision burr hole intracranial
                '61781',  -- Stereotactic computer assisted cranial intradural
                '61782',  -- Stereotactic computer assisted extradural cranial
                '61783'   -- Stereotactic computer assisted spinal
            ) THEN 'stereotactic_tumor_procedure'

            WHEN pcc.code_coding_code IN (
                '62164',  -- Neuroendoscopy intracranial brain tumor excision
                '62165'   -- Neuroendoscopy intracranial pituitary tumor excision
            ) THEN 'neuroendoscopy_tumor'

            WHEN pcc.code_coding_code = '61140'
                THEN 'open_brain_biopsy'

            WHEN pcc.code_coding_code IN (
                '61580',  -- Craniofacial anterior cranial fossa
                '61584',  -- Orbitocranial anterior cranial fossa
                '61592',  -- Orbitocranial middle cranial fossa temporal lobe
                '61600',  -- Resection/excision lesion base anterior cranial fossa extradural
                '61601',  -- Resection/excision lesion base anterior cranial fossa intradural
                '61607'   -- Resection/excision lesion parasellar sinus/cavernous sinus
            ) THEN 'skull_base_tumor'

            -- TIER 2: TUMOR-RELATED SUPPORT PROCEDURES
            WHEN pcc.code_coding_code IN (
                '62201',  -- Ventriculocisternostomy 3rd ventricle endoscopic
                '62200'   -- Ventriculocisternostomy 3rd ventricle
            ) THEN 'tumor_related_csf_management'

            WHEN pcc.code_coding_code IN (
                '61210',  -- Burr hole implant ventricular catheter/device
                '61215'   -- Insertion subcutaneous reservoir pump/infusion ventricular
            ) THEN 'tumor_related_device_implant'

            -- TIER 3: EXPLORATORY/DIAGNOSTIC
            WHEN pcc.code_coding_code IN (
                '61304',  -- Craniectomy/craniotomy exploration supratentorial
                '61305'   -- Craniectomy/craniotomy exploration infratentorial
            ) THEN 'exploratory_craniotomy'

            WHEN pcc.code_coding_code = '64999'
                THEN 'unlisted_nervous_system'

            -- EXCLUSIONS: NON-TUMOR PROCEDURES
            WHEN pcc.code_coding_code IN (
                '62220',  -- Creation shunt ventriculo-atrial
                '62223',  -- Creation shunt ventriculo-peritoneal
                '62225',  -- Replacement/irrigation ventricular catheter
                '62230',  -- Replacement/revision CSF shunt valve/catheter
                '62256',  -- Removal complete CSF shunt system
                '62192'   -- Creation shunt subarachnoid/subdural-peritoneal
            ) THEN 'exclude_vp_shunt'

            WHEN pcc.code_coding_code IN (
                '64615',  -- Chemodenervation for headache
                '64642',  -- Chemodenervation one extremity 1-4 muscles
                '64643',  -- Chemodenervation one extremity additional 1-4 muscles
                '64644',  -- Chemodenervation one extremity 5+ muscles
                '64645',  -- Chemodenervation one extremity additional 5+ muscles
                '64646',  -- Chemodenervation trunk muscle 1-5 muscles
                '64647',  -- Chemodenervation trunk muscle 6+ muscles
                '64400',  -- Injection anesthetic trigeminal nerve
                '64405',  -- Injection anesthetic greater occipital nerve
                '64450',  -- Injection anesthetic other peripheral nerve
                '64614',  -- Chemodenervation extremity/trunk muscle
                '64616'   -- Chemodenervation muscle neck unilateral
            ) THEN 'exclude_spasticity_pain'

            WHEN pcc.code_coding_code IN (
                '62270',  -- Spinal puncture lumbar diagnostic
                '62272',  -- Spinal puncture therapeutic
                '62328'   -- Diagnostic lumbar puncture with fluoro/CT
            ) THEN 'exclude_diagnostic_procedure'

            WHEN pcc.code_coding_code IN (
                '61154',  -- Burr hole evacuation/drainage hematoma
                '61156'   -- Burr hole aspiration hematoma/cyst brain
            ) THEN 'exclude_burr_hole_trauma'

            WHEN pcc.code_coding_code IN (
                '61312',  -- Craniectomy hematoma supratentorial
                '61313',  -- Craniectomy hematoma supratentorial intradural
                '61314',  -- Craniectomy hematoma infratentorial
                '61315',  -- Craniectomy hematoma infratentorial intradural
                '61320',  -- Craniectomy/craniotomy drainage abscess supratentorial
                '61321'   -- Craniectomy/craniotomy drainage abscess infratentorial
            ) THEN 'exclude_trauma_abscess'

            WHEN pcc.code_coding_code IN (
                '62161',  -- Neuroendoscopy dissection adhesions/fenestration
                '62162',  -- Neuroendoscopy fenestration cyst
                '62163'   -- Neuroendoscopy retrieval foreign body
            ) THEN 'exclude_neuroendoscopy_nontumor'

            ELSE NULL
        END as cpt_classification,

        CASE
            WHEN pcc.code_coding_code IN (
                '61500', '61510', '61512', '61516', '61518', '61519', '61520', '61521', '61524',
                '61545', '61546', '61548', '61750', '61751', '61781', '61782', '61783',
                '62164', '62165', '61140', '61580', '61584', '61592', '61600', '61601', '61607'
            ) THEN 'definite_tumor'
            WHEN pcc.code_coding_code IN ('62201', '62200', '61210', '61215') THEN 'tumor_support'
            WHEN pcc.code_coding_code IN ('61304', '61305', '64999') THEN 'ambiguous'
            WHEN pcc.code_coding_code IN (
                '62220', '62223', '62225', '62230', '62256', '62192',
                '64615', '64642', '64643', '64644', '64645', '64646', '64647',
                '64400', '64405', '64450', '64614', '64616',
                '62270', '62272', '62328',
                '61154', '61156', '61312', '61313', '61314', '61315', '61320', '61321',
                '62161', '62162', '62163'
            ) THEN 'exclude'
            ELSE NULL
        END as classification_type

    FROM fhir_prd_db.procedure_code_coding pcc
    WHERE pcc.code_coding_system = 'http://www.ama-assn.org/go/cpt'
),

epic_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as epic_code,
        pcc.code_coding_display as epic_display,
        CASE
            WHEN pcc.code_coding_code = '129807' THEN 'neurosurgery_request'
            WHEN pcc.code_coding_code = '85313' THEN 'general_surgery_request'
            ELSE NULL
        END as epic_category
    FROM fhir_prd_db.procedure_code_coding pcc
    WHERE pcc.code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'
),

procedure_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_system,
        pcc.code_coding_code,
        pcc.code_coding_display,

        CASE
            WHEN LOWER(pcc.code_coding_display) LIKE '%craniotomy%tumor%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%tumor%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniotomy%mass%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniotomy%lesion%'
                OR LOWER(pcc.code_coding_display) LIKE '%brain tumor resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%tumor resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%mass excision%'
                OR LOWER(pcc.code_coding_display) LIKE '%stereotactic biopsy%'
                OR LOWER(pcc.code_coding_display) LIKE '%brain biopsy%'
                OR LOWER(pcc.code_coding_display) LIKE '%navigational procedure%brain%'
                OR LOWER(pcc.code_coding_display) LIKE '%gross total resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%endonasal tumor%'
                OR LOWER(pcc.code_coding_display) LIKE '%transsphenoidal%'
            THEN 'keyword_tumor_specific'
            WHEN LOWER(pcc.code_coding_display) LIKE '%shunt%'
                OR LOWER(pcc.code_coding_display) LIKE '%ventriculoperitoneal%'
                OR LOWER(pcc.code_coding_display) LIKE '%vp shunt%'
                OR LOWER(pcc.code_coding_display) LIKE '%chemodenervation%'
                OR LOWER(pcc.code_coding_display) LIKE '%botox%'
                OR LOWER(pcc.code_coding_display) LIKE '%injection%nerve%'
                OR LOWER(pcc.code_coding_display) LIKE '%nerve block%'
                OR LOWER(pcc.code_coding_display) LIKE '%lumbar puncture%'
                OR LOWER(pcc.code_coding_display) LIKE '%spinal tap%'
            THEN 'keyword_exclude'
            WHEN LOWER(pcc.code_coding_display) LIKE '%craniotomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgery%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgical%'
            THEN 'keyword_surgical_generic'

            ELSE NULL
        END as keyword_classification,

        CASE
            WHEN LOWER(pcc.code_coding_display) LIKE '%craniotomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%excision%'
                OR LOWER(pcc.code_coding_display) LIKE '%biopsy%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgery%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgical%'
                OR LOWER(pcc.code_coding_display) LIKE '%anesthesia%'
                OR LOWER(pcc.code_coding_display) LIKE '%anes%'
                OR LOWER(pcc.code_coding_display) LIKE '%oper%'
            THEN true
            ELSE false
        END as is_surgical_keyword

    FROM fhir_prd_db.procedure_code_coding pcc
),

procedure_dates AS (
    SELECT
        p.id as procedure_id,
        COALESCE(
            TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)),
            TRY(CAST(SUBSTR(p.performed_period_start, 1, 10) AS DATE))
        ) as procedure_date
    FROM fhir_prd_db.procedure p
),

procedure_validation AS (
    SELECT
        p.id as procedure_id,

        CASE
            WHEN LOWER(prc.reason_code_text) LIKE '%tumor%'
                OR LOWER(prc.reason_code_text) LIKE '%mass%'
                OR LOWER(prc.reason_code_text) LIKE '%neoplasm%'
                OR LOWER(prc.reason_code_text) LIKE '%cancer%'
                OR LOWER(prc.reason_code_text) LIKE '%glioma%'
                OR LOWER(prc.reason_code_text) LIKE '%astrocytoma%'
                OR LOWER(prc.reason_code_text) LIKE '%ependymoma%'
                OR LOWER(prc.reason_code_text) LIKE '%medulloblastoma%'
                OR LOWER(prc.reason_code_text) LIKE '%craniopharyngioma%'
                OR LOWER(prc.reason_code_text) LIKE '%meningioma%'
                OR LOWER(prc.reason_code_text) LIKE '%lesion%'
                OR LOWER(prc.reason_code_text) LIKE '%germinoma%'
                OR LOWER(prc.reason_code_text) LIKE '%teratoma%'
            THEN true
            ELSE false
        END as has_tumor_reason,

        CASE
            WHEN LOWER(prc.reason_code_text) LIKE '%spasticity%'
                OR LOWER(prc.reason_code_text) LIKE '%migraine%'
                OR LOWER(prc.reason_code_text) LIKE '%shunt malfunction%'
                OR LOWER(prc.reason_code_text) LIKE '%dystonia%'
                OR LOWER(prc.reason_code_text) LIKE '%hematoma%'
                OR LOWER(prc.reason_code_text) LIKE '%hemorrhage%'
                OR LOWER(prc.reason_code_text) LIKE '%trauma%'
            THEN true
            ELSE false
        END as has_exclude_reason,

        CASE
            WHEN pbs.body_site_text IN ('Brain', 'Skull', 'Nares', 'Nose', 'Temporal', 'Orbit')
            THEN true
            ELSE false
        END as has_tumor_body_site,

        CASE
            WHEN pbs.body_site_text IN ('Arm', 'Leg', 'Hand', 'Thigh', 'Shoulder',
                                         'Arm Lower', 'Arm Upper', 'Foot', 'Ankle')
            THEN true
            ELSE false
        END as has_exclude_body_site,

        prc.reason_code_text,
        pbs.body_site_text

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_reason_code prc ON p.id = prc.procedure_id
    LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
),

combined_classification AS (
    SELECT
        p.id as procedure_id,

        cpt.cpt_classification,
        cpt.cpt_code,
        cpt.classification_type as cpt_type,
        epic.epic_category,
        epic.epic_code,
        pc.keyword_classification,

        pv.has_tumor_reason,
        pv.has_exclude_reason,
        pv.has_tumor_body_site,
        pv.has_exclude_body_site,
        pv.reason_code_text as validation_reason_code,
        pv.body_site_text as validation_body_site,

        COALESCE(
            cpt.cpt_classification,
            epic.epic_category,
            pc.keyword_classification,
            'unclassified'
        ) as procedure_classification,

        CASE
            WHEN pv.has_exclude_reason = true OR pv.has_exclude_body_site = true THEN false
            WHEN cpt.classification_type = 'definite_tumor' THEN true
            WHEN cpt.classification_type = 'tumor_support' THEN true
            WHEN cpt.classification_type = 'ambiguous'
                AND (pv.has_tumor_reason = true OR pv.has_tumor_body_site = true) THEN true
            WHEN cpt.classification_type IS NULL
                AND pc.keyword_classification = 'keyword_tumor_specific' THEN true

            ELSE false
        END as is_tumor_surgery,

        CASE
            WHEN pv.has_exclude_reason = true OR pv.has_exclude_body_site = true THEN true
            WHEN cpt.classification_type = 'exclude' THEN true
            WHEN pc.keyword_classification = 'keyword_exclude' THEN true

            ELSE false
        END as is_excluded_procedure,

        CASE
            WHEN cpt.cpt_classification LIKE '%biopsy%' THEN 'biopsy'
            WHEN cpt.cpt_classification = 'stereotactic_tumor_procedure' THEN 'stereotactic_procedure'
            WHEN cpt.cpt_classification LIKE '%craniotomy%' THEN 'craniotomy'
            WHEN cpt.cpt_classification LIKE '%craniectomy%' THEN 'craniectomy'
            WHEN cpt.cpt_classification = 'neuroendoscopy_tumor' THEN 'neuroendoscopy'
            WHEN cpt.cpt_classification = 'skull_base_tumor' THEN 'skull_base'
            WHEN cpt.cpt_classification = 'tumor_related_csf_management' THEN 'csf_management'
            WHEN cpt.cpt_classification = 'tumor_related_device_implant' THEN 'device_implant'
            WHEN cpt.cpt_classification = 'exploratory_craniotomy' THEN 'exploratory'
            WHEN pc.keyword_classification = 'keyword_tumor_specific' THEN 'tumor_procedure'
            WHEN pc.keyword_classification = 'keyword_surgical_generic' THEN 'surgical_generic'
            ELSE 'unknown'
        END as surgery_type,

        CASE
            WHEN pv.has_exclude_reason = true OR pv.has_exclude_body_site = true THEN 0
            WHEN cpt.classification_type = 'definite_tumor'
                AND pv.has_tumor_reason = true
                AND pv.has_tumor_body_site = true THEN 100
            WHEN cpt.classification_type = 'definite_tumor'
                AND pv.has_tumor_reason = true THEN 95
            WHEN cpt.classification_type = 'definite_tumor'
                AND pv.has_tumor_body_site = true THEN 95
            WHEN cpt.classification_type = 'definite_tumor'
                AND epic.epic_category = 'neurosurgery_request' THEN 95
            WHEN cpt.classification_type = 'definite_tumor' THEN 90
            WHEN cpt.classification_type = 'tumor_support'
                AND pv.has_tumor_reason = true
                AND pv.has_tumor_body_site = true THEN 90
            WHEN cpt.classification_type = 'tumor_support'
                AND pv.has_tumor_reason = true THEN 85
            WHEN cpt.classification_type = 'tumor_support'
                AND pv.has_tumor_body_site = true THEN 85
            WHEN cpt.classification_type = 'tumor_support'
                AND epic.epic_category = 'neurosurgery_request' THEN 80
            WHEN cpt.classification_type = 'tumor_support' THEN 75
            WHEN cpt.classification_type = 'ambiguous'
                AND pv.has_tumor_reason = true
                AND pv.has_tumor_body_site = true THEN 70
            WHEN cpt.classification_type = 'ambiguous'
                AND pv.has_tumor_reason = true THEN 65
            WHEN cpt.classification_type = 'ambiguous'
                AND pv.has_tumor_body_site = true THEN 60
            WHEN cpt.classification_type = 'ambiguous' THEN 50
            WHEN pc.keyword_classification = 'keyword_tumor_specific'
                AND pv.has_tumor_reason = true THEN 75
            WHEN pc.keyword_classification = 'keyword_tumor_specific'
                AND pv.has_tumor_body_site = true THEN 70
            WHEN pc.keyword_classification = 'keyword_tumor_specific' THEN 65
            WHEN pc.keyword_classification = 'keyword_surgical_generic' THEN 40
            WHEN cpt.classification_type = 'exclude' THEN 0
            WHEN pc.keyword_classification = 'keyword_exclude' THEN 0
            WHEN cpt.cpt_classification IS NULL
                AND pc.keyword_classification IS NULL THEN 30
            ELSE 30
        END as classification_confidence

    FROM fhir_prd_db.procedure p
    LEFT JOIN cpt_classifications cpt ON p.id = cpt.procedure_id
    LEFT JOIN epic_codes epic ON p.id = epic.procedure_id
    LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
    LEFT JOIN procedure_validation pv ON p.id = pv.procedure_id
)

SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_fhir_id,

    p.status as proc_status,
    TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) as proc_performed_date_time,
    TRY(CAST(p.performed_period_start AS TIMESTAMP(3))) as proc_performed_period_start,
    TRY(CAST(p.performed_period_end AS TIMESTAMP(3))) as proc_performed_period_end,
    TRY(CAST(p.performed_string AS TIMESTAMP(3))) as proc_performed_string,
    TRY(CAST(p.performed_age_value AS TIMESTAMP(3))) as proc_performed_age_value,
    TRY(CAST(p.performed_age_unit AS TIMESTAMP(3))) as proc_performed_age_unit,
    p.code_text as proc_code_text,
    p.category_text as proc_category_text,
    p.subject_reference as proc_subject_reference,
    p.encounter_reference as proc_encounter_reference,
    p.encounter_display as proc_encounter_display,
    p.location_reference as proc_location_reference,
    p.location_display as proc_location_display,
    p.outcome_text as proc_outcome_text,
    p.recorder_reference as proc_recorder_reference,
    p.recorder_display as proc_recorder_display,
    p.asserter_reference as proc_asserter_reference,
    p.asserter_display as proc_asserter_display,
    p.status_reason_text as proc_status_reason_text,

    pd.procedure_date,

    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        pd.procedure_date)) as age_at_procedure_days,

    pc.code_coding_system as pcc_code_coding_system,
    pc.code_coding_code as pcc_code_coding_code,
    pc.code_coding_display as pcc_code_coding_display,
    pc.is_surgical_keyword,

    cc.procedure_classification,
    cc.cpt_classification,
    cc.cpt_code,
    cc.cpt_type,
    cc.epic_category,
    cc.epic_code,
    cc.keyword_classification,
    cc.is_tumor_surgery,
    cc.is_excluded_procedure,
    cc.surgery_type,
    cc.classification_confidence,

    cc.has_tumor_reason,
    cc.has_exclude_reason,
    cc.has_tumor_body_site,
    cc.has_exclude_body_site,
    cc.validation_reason_code,
    cc.validation_body_site,

    pcat.category_coding_display as pcat_category_coding_display,
    pbs.body_site_text as pbs_body_site_text,
    pp.performer_actor_display as pp_performer_actor_display,
    pp.performer_function_text as pp_performer_function_text

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN fhir_prd_db.patient pa ON p.subject_reference = CONCAT('Patient/', pa.id)
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN combined_classification cc ON p.id = cc.procedure_id
LEFT JOIN fhir_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
LEFT JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id
ORDER BY p.subject_reference, pd.procedure_date;

-- ================================================================================
-- VIEW: v_hydrocephalus_procedures
-- DATETIME STANDARDIZATION: 6 columns converted from VARCHAR
-- CHANGES:
--   - enc_end: VARCHAR → TIMESTAMP(3)
--   - enc_start: VARCHAR → TIMESTAMP(3)
--   - hydro_event_date: VARCHAR → TIMESTAMP(3)
--   - proc_performed_datetime: VARCHAR → TIMESTAMP(3)
--   - proc_period_end: VARCHAR → TIMESTAMP(3)
--   - proc_period_start: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_hydrocephalus_procedures AS
WITH
-- Primary shunt procedures (1,196 procedures)
shunt_procedures AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        p.id as procedure_id,
        p.code_text,
        p.status as proc_status,

        -- ALL DATE FIELDS (standardized)
        TRY(CAST(CASE
            WHEN LENGTH(p.performed_date_time) = 10 THEN p.performed_date_time || 'T00:00:00Z'
            ELSE p.performed_date_time
        END AS TIMESTAMP(3))) as proc_performed_datetime,
        TRY(CAST(CASE
            WHEN LENGTH(p.performed_period_start) = 10 THEN p.performed_period_start || 'T00:00:00Z'
            ELSE p.performed_period_start
        END AS TIMESTAMP(3))) as proc_period_start,
        TRY(CAST(CASE
            WHEN LENGTH(p.performed_period_end) = 10 THEN p.performed_period_end || 'T00:00:00Z'
            ELSE p.performed_period_end
        END AS TIMESTAMP(3))) as proc_period_end,

        p.category_text as proc_category_text,
        p.outcome_text as proc_outcome_text,
        p.location_display as proc_location,
        p.encounter_reference as proc_encounter_ref,

        -- Shunt type classification
        CASE
            WHEN LOWER(p.code_text) LIKE '%ventriculoperitoneal%'
                 OR LOWER(p.code_text) LIKE '%vp%shunt%'
                 OR LOWER(p.code_text) LIKE '%v-p%shunt%'
                 OR LOWER(p.code_text) LIKE '%vps%' THEN 'VPS'
            WHEN LOWER(p.code_text) LIKE '%endoscopic%third%ventriculostomy%'
                 OR LOWER(p.code_text) LIKE '%etv%' THEN 'ETV'
            WHEN LOWER(p.code_text) LIKE '%external%ventricular%drain%'
                 OR LOWER(p.code_text) LIKE '%evd%'
                 OR LOWER(p.code_text) LIKE '%temporary%' THEN 'EVD'
            WHEN LOWER(p.code_text) LIKE '%ventriculoatrial%'
                 OR LOWER(p.code_text) LIKE '%va%shunt%' THEN 'VA Shunt'
            WHEN LOWER(p.code_text) LIKE '%ventriculopleural%' THEN 'Ventriculopleural'
            ELSE 'Other'
        END as shunt_type,

        -- Procedure category
        CASE
            WHEN LOWER(p.code_text) LIKE '%placement%'
                 OR LOWER(p.code_text) LIKE '%insertion%'
                 OR LOWER(p.code_text) LIKE '%creation%' THEN 'Placement'
            WHEN LOWER(p.code_text) LIKE '%revision%'
                 OR LOWER(p.code_text) LIKE '%replacement%' THEN 'Revision'
            WHEN LOWER(p.code_text) LIKE '%removal%'
                 OR LOWER(p.code_text) LIKE '%explant%' THEN 'Removal'
            WHEN LOWER(p.code_text) LIKE '%reprogram%' THEN 'Reprogramming'
            WHEN LOWER(p.code_text) LIKE '%evd%'
                 OR LOWER(p.code_text) LIKE '%temporary%' THEN 'Temporary EVD'
            WHEN LOWER(p.code_text) LIKE '%etv%'
                 OR LOWER(p.code_text) LIKE '%ventriculostomy%' THEN 'ETV'
            ELSE 'Other'
        END as procedure_category

    FROM fhir_prd_db.procedure p
    WHERE p.subject_reference IS NOT NULL
      AND (
          LOWER(p.code_text) LIKE '%shunt%'
          OR LOWER(p.code_text) LIKE '%ventriculostomy%'
          OR LOWER(p.code_text) LIKE '%ventricular%drain%'
          OR LOWER(p.code_text) LIKE '%csf%diversion%'
      )
),

-- Procedure reason codes 
procedure_reasons AS (
    SELECT
        prc.procedure_id,
        LISTAGG(prc.reason_code_text, ' | ') WITHIN GROUP (ORDER BY prc.reason_code_text) as reasons_text,
        LISTAGG(DISTINCT prc.reason_code_coding, ' | ') WITHIN GROUP (ORDER BY prc.reason_code_coding) as reason_codes,

        -- Confirmed hydrocephalus indication
        MAX(CASE
            WHEN LOWER(prc.reason_code_text) LIKE '%hydroceph%' THEN true
            WHEN LOWER(prc.reason_code_text) LIKE '%increased%intracranial%pressure%' THEN true
            WHEN LOWER(prc.reason_code_text) LIKE '%ventriculomegaly%' THEN true
            WHEN prc.reason_code_coding LIKE '%G91%' THEN true
            WHEN prc.reason_code_coding LIKE '%Q03%' THEN true
            ELSE false
        END) as confirmed_hydrocephalus

    FROM fhir_prd_db.procedure_reason_code prc
    WHERE prc.procedure_id IN (SELECT procedure_id FROM shunt_procedures)
    GROUP BY prc.procedure_id
),

-- Procedure body sites 
procedure_body_sites AS (
    SELECT
        pbs.procedure_id,
        LISTAGG(pbs.body_site_text, ' | ') WITHIN GROUP (ORDER BY pbs.body_site_text) as body_sites_text,
        LISTAGG(DISTINCT pbs.body_site_coding, ' | ') WITHIN GROUP (ORDER BY pbs.body_site_coding) as body_site_codes,

        -- Anatomical location flags
        MAX(CASE WHEN LOWER(pbs.body_site_text) LIKE '%lateral%ventricle%' THEN true ELSE false END) as lateral_ventricle,
        MAX(CASE WHEN LOWER(pbs.body_site_text) LIKE '%third%ventricle%' THEN true ELSE false END) as third_ventricle,
        MAX(CASE WHEN LOWER(pbs.body_site_text) LIKE '%fourth%ventricle%' THEN true ELSE false END) as fourth_ventricle,
        MAX(CASE WHEN LOWER(pbs.body_site_text) LIKE '%periton%' THEN true ELSE false END) as peritoneum,
        MAX(CASE WHEN LOWER(pbs.body_site_text) LIKE '%atri%' THEN true ELSE false END) as atrium

    FROM fhir_prd_db.procedure_body_site pbs
    WHERE pbs.procedure_id IN (SELECT procedure_id FROM shunt_procedures)
    GROUP BY pbs.procedure_id
),

-- Procedure performers (surgeon documentation)
procedure_performers AS (
    SELECT
        pp.procedure_id,
        LISTAGG(pp.performer_actor_display, ' | ') WITHIN GROUP (ORDER BY pp.performer_actor_display) as performers,
        LISTAGG(DISTINCT pp.performer_function_text, ' | ') WITHIN GROUP (ORDER BY pp.performer_function_text) as performer_roles,

        -- Surgeon flag
        MAX(CASE
            WHEN LOWER(pp.performer_function_text) LIKE '%surg%' THEN true
            WHEN LOWER(pp.performer_actor_display) LIKE '%surg%' THEN true
            ELSE false
        END) as has_surgeon

    FROM fhir_prd_db.procedure_performer pp
    WHERE pp.procedure_id IN (SELECT procedure_id FROM shunt_procedures)
    GROUP BY pp.procedure_id
),

-- Procedure notes (programmable valve detection)
procedure_notes AS (
    SELECT
        pn.procedure_id,
        LISTAGG(pn.note_text, ' | ') WITHIN GROUP (ORDER BY pn.note_time) as notes_text,

        -- Programmable valve mentions
        MAX(CASE
            WHEN LOWER(pn.note_text) LIKE '%programmable%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%strata%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%hakim%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%polaris%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%progav%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%codman%certas%' THEN true
            ELSE false
        END) as mentions_programmable

    FROM fhir_prd_db.procedure_note pn
    WHERE pn.procedure_id IN (SELECT procedure_id FROM shunt_procedures)
    GROUP BY pn.procedure_id
),

-- Shunt devices from procedure_focal_device (programmable valve detection)
shunt_devices AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        pfd.procedure_id,
        pfd.focal_device_manipulated_display as device_name,
        pfd.focal_device_action_text as device_action,

        -- Programmable valve detection
        CASE
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%programmable%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%strata%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%hakim%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%polaris%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%progav%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%medtronic%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%codman%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%sophysa%' THEN true
            WHEN LOWER(pfd.focal_device_manipulated_display) LIKE '%aesculap%' THEN true
            ELSE false
        END as is_programmable

    FROM fhir_prd_db.procedure_focal_device pfd
    INNER JOIN fhir_prd_db.procedure p ON pfd.procedure_id = p.id
    WHERE pfd.procedure_id IN (SELECT procedure_id FROM shunt_procedures)
      AND (
          LOWER(pfd.focal_device_manipulated_display) LIKE '%shunt%'
          OR LOWER(pfd.focal_device_manipulated_display) LIKE '%ventriculo%'
          OR LOWER(pfd.focal_device_manipulated_display) LIKE '%valve%'
      )
),

-- Aggregate devices per patient
patient_devices AS (
    SELECT
        patient_fhir_id,
        COUNT(*) as total_devices,
        MAX(is_programmable) as has_programmable,
        LISTAGG(DISTINCT device_name, ' | ') WITHIN GROUP (ORDER BY device_name) as device_names,
        LISTAGG(DISTINCT device_action, ' | ') WITHIN GROUP (ORDER BY device_action) as device_actions
    FROM shunt_devices
    GROUP BY patient_fhir_id
),

-- Encounter linkage (hospitalization context)
procedure_encounters AS (
    SELECT
        p.id as procedure_id,
        e.id as encounter_id,
        e.class_code as encounter_class,
        e.service_type_text as encounter_type,

        -- Standardized dates
        CASE
            WHEN LENGTH(e.period_start) = 10 THEN e.period_start || 'T00:00:00Z'
            ELSE e.period_start
        END as encounter_start,
        CASE
            WHEN LENGTH(e.period_end) = 10 THEN e.period_end || 'T00:00:00Z'
            ELSE e.period_end
        END as encounter_end,

        -- Hospitalization flags
        CASE WHEN e.class_code = 'IMP' THEN true ELSE false END as was_inpatient,
        CASE WHEN e.class_code = 'EMER' THEN true ELSE false END as was_emergency

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.encounter e
        ON p.encounter_reference = CONCAT('Encounter/', e.id)
        OR (
            p.subject_reference = e.subject_reference
            AND p.performed_period_start >= e.period_start
            AND p.performed_period_start <= e.period_end
        )
    WHERE p.id IN (SELECT procedure_id FROM shunt_procedures)
),

-- Medications for hydrocephalus
patient_medications AS (
    SELECT
        mr.subject_reference as patient_fhir_id,
        COUNT(DISTINCT mr.id) as total_medications,

        -- Non-surgical management flags
        MAX(CASE WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%acetazol%' THEN true ELSE false END) as has_acetazolamide,
        MAX(CASE
            WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%dexameth%'
                 OR LOWER(mr.medication_codeable_concept_text) LIKE '%prednis%'
                 OR LOWER(mr.medication_codeable_concept_text) LIKE '%methylpred%' THEN true
            ELSE false
        END) as has_steroids,
        MAX(CASE
            WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%furosemide%'
                 OR LOWER(mr.medication_codeable_concept_text) LIKE '%mannitol%' THEN true
            ELSE false
        END) as has_diuretic,

        LISTAGG(DISTINCT mr.medication_codeable_concept_text, ' | ') WITHIN GROUP (ORDER BY mr.medication_codeable_concept_text) as medication_names

    FROM fhir_prd_db.medication_request mr
    INNER JOIN fhir_prd_db.medication_request_reason_code mrc
        ON mr.id = mrc.medication_request_id
    WHERE (
        LOWER(mrc.reason_code_text) LIKE '%hydroceph%'
        OR LOWER(mrc.reason_code_text) LIKE '%intracranial%pressure%'
        OR LOWER(mrc.reason_code_text) LIKE '%ventriculomegaly%'
    )
    GROUP BY mr.subject_reference
)

-- Main SELECT: Combine all procedure data
SELECT
    -- Patient identifier
    sp.patient_fhir_id,

    -- Procedure fields (proc_ prefix)
    sp.procedure_id as proc_id,
    sp.code_text as proc_code_text,
    sp.proc_status,
    sp.proc_performed_datetime,
    sp.proc_period_start,
    sp.proc_period_end,
    sp.proc_category_text,
    sp.proc_outcome_text,
    sp.proc_location,
    sp.proc_encounter_ref,

    -- Shunt classification
    sp.shunt_type as proc_shunt_type,
    sp.procedure_category as proc_category,

    -- Procedure reason codes (prc_ prefix)
    pr.reasons_text as prc_reasons,
    pr.reason_codes as prc_codes,
    pr.confirmed_hydrocephalus as prc_confirmed_hydro,

    -- Body sites (pbs_ prefix)
    pbs.body_sites_text as pbs_sites,
    pbs.body_site_codes as pbs_codes,
    pbs.lateral_ventricle as pbs_lateral_ventricle,
    pbs.third_ventricle as pbs_third_ventricle,
    pbs.fourth_ventricle as pbs_fourth_ventricle,
    pbs.peritoneum as pbs_peritoneum,
    pbs.atrium as pbs_atrium,

    -- Performers (pp_ prefix)
    perf.performers as pp_performers,
    perf.performer_roles as pp_roles,
    perf.has_surgeon as pp_has_surgeon,

    -- Procedure notes (pn_ prefix)
    pn.notes_text as pn_notes,
    pn.mentions_programmable as pn_mentions_programmable,

    -- Device information (dev_ prefix)
    pd.total_devices as dev_total,
    pd.has_programmable as dev_has_programmable,
    pd.device_names as dev_names,
    pd.device_actions as dev_actions,

    -- Encounter linkage (enc_ prefix)
    pe.encounter_id as enc_id,
    pe.encounter_class as enc_class,
    pe.encounter_type as enc_type,
    TRY(CAST(pe.encounter_start AS TIMESTAMP(3))) as enc_start,
    TRY(CAST(pe.encounter_end AS TIMESTAMP(3))) as enc_end,
    pe.was_inpatient as enc_was_inpatient,
    pe.was_emergency as enc_was_emergency,

    -- Medications (med_ prefix)
    pm.total_medications as med_total,
    pm.has_acetazolamide as med_acetazolamide,
    pm.has_steroids as med_steroids,
    pm.has_diuretic as med_diuretic,
    pm.medication_names as med_names,

    -- ============================================================================
    -- CBTN FIELD MAPPINGS
    -- ============================================================================

    -- shunt_required (diagnosis form) - shunt type
    sp.shunt_type as shunt_required,

    -- hydro_surgical_management (hydrocephalus_details form)
    sp.procedure_category as hydro_surgical_management,

    -- hydro_shunt_programmable (from device OR notes)
    COALESCE(pd.has_programmable, pn.mentions_programmable, false) as hydro_shunt_programmable,

    -- hydro_intervention (checkbox: Surgical, Medical, Hospitalization)
    CASE
        WHEN pe.was_inpatient = true THEN 'Hospitalization'
        WHEN sp.procedure_category IN ('Placement', 'Revision', 'ETV', 'Temporary EVD', 'Removal') THEN 'Surgical'
        WHEN sp.procedure_category = 'Reprogramming' THEN 'Medical'
        ELSE 'Surgical'
    END as hydro_intervention_type,

    -- Individual intervention flags
    CASE WHEN sp.procedure_category IN ('Placement', 'Revision', 'ETV', 'Temporary EVD', 'Removal') THEN true ELSE false END as intervention_surgical,
    CASE WHEN sp.procedure_category = 'Reprogramming' THEN true ELSE false END as intervention_medical,
    CASE WHEN pe.was_inpatient = true THEN true ELSE false END as intervention_hospitalization,

    -- hydro_nonsurg_management (checkbox: Acetazolamide, Steroids)
    pm.has_acetazolamide as nonsurg_acetazolamide,
    pm.has_steroids as nonsurg_steroids,
    pm.has_diuretic as nonsurg_diuretic,

    -- hydro_event_date (procedure date)
    TRY(CAST(COALESCE(sp.proc_performed_datetime, sp.proc_period_start) AS TIMESTAMP(3))) as hydro_event_date,

    -- ============================================================================
    -- DATA QUALITY INDICATORS
    -- ============================================================================

    CASE WHEN sp.proc_performed_datetime IS NOT NULL OR sp.proc_period_start IS NOT NULL THEN true ELSE false END as has_procedure_date,
    CASE WHEN pn.notes_text IS NOT NULL THEN true ELSE false END as has_procedure_notes,
    CASE WHEN pd.total_devices > 0 THEN true ELSE false END as has_device_record,
    CASE WHEN sp.proc_status = 'completed' THEN true ELSE false END as is_completed,
    CASE WHEN pr.confirmed_hydrocephalus = true THEN true ELSE false END as validated_by_reason_code,
    CASE WHEN pbs.body_sites_text IS NOT NULL THEN true ELSE false END as has_body_site_documentation,
    CASE WHEN perf.has_surgeon = true THEN true ELSE false END as has_surgeon_documented,
    CASE WHEN pe.encounter_id IS NOT NULL THEN true ELSE false END as linked_to_encounter,
    CASE WHEN pm.total_medications > 0 THEN true ELSE false END as has_nonsurgical_treatment

FROM shunt_procedures sp
LEFT JOIN procedure_reasons pr ON sp.procedure_id = pr.procedure_id
LEFT JOIN procedure_body_sites pbs ON sp.procedure_id = pbs.procedure_id
LEFT JOIN procedure_performers perf ON sp.procedure_id = perf.procedure_id
LEFT JOIN procedure_notes pn ON sp.procedure_id = pn.procedure_id
LEFT JOIN patient_devices pd ON sp.patient_fhir_id = pd.patient_fhir_id
LEFT JOIN procedure_encounters pe ON sp.procedure_id = pe.procedure_id
LEFT JOIN patient_medications pm ON sp.patient_fhir_id = pm.patient_fhir_id

ORDER BY sp.patient_fhir_id, sp.proc_period_start;

-- ================================================================================
-- VIEW: v_autologous_stem_cell_collection
-- DATETIME STANDARDIZATION: 5 columns converted from VARCHAR
-- CHANGES:
--   - cd34_measurement_datetime: VARCHAR → TIMESTAMP(3)
--   - collection_datetime: VARCHAR → TIMESTAMP(3)
--   - mobilization_start_datetime: VARCHAR → TIMESTAMP(3)
--   - mobilization_stop_datetime: VARCHAR → TIMESTAMP(3)
--   - quality_measurement_datetime: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_collection AS

WITH collection_procedures AS (
    -- Identify autologous stem cell collection procedures
    SELECT DISTINCT
        p.subject_reference as patient_fhir_id,
        p.id as procedure_fhir_id,
        p.code_text as procedure_description,

        -- Standardize collection date
        TRY(CAST(CASE
            WHEN LENGTH(p.performed_date_time) = 10
            THEN p.performed_date_time || 'T00:00:00Z'
            ELSE p.performed_date_time
        END AS TIMESTAMP(3))) as collection_datetime,

        -- Extract method from coding
        COALESCE(pc.code_coding_display, p.code_text) as collection_method,
        pc.code_coding_code as collection_cpt_code,

        p.status as procedure_status,
        p.outcome_text as procedure_outcome

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pc
        ON pc.procedure_id = p.id
        AND pc.code_coding_system LIKE '%cpt%'

    WHERE (
        -- CPT code for apheresis/stem cell collection
        pc.code_coding_code IN ('38231', '38232', '38241')

        -- Text matching for collection procedures
        OR LOWER(p.code_text) LIKE '%apheresis%'
        OR LOWER(p.code_text) LIKE '%stem cell%collection%'
        OR LOWER(p.code_text) LIKE '%stem cell%harvest%'
        OR LOWER(p.code_text) LIKE '%peripheral blood%progenitor%'
        OR LOWER(p.code_text) LIKE '%pbsc%collection%'
        OR LOWER(p.code_text) LIKE '%marrow%harvest%'
    )
    AND p.status IN ('completed', 'in-progress', 'preparation')
),

cd34_counts AS (
    -- Extract CD34+ cell counts from observations
    SELECT DISTINCT
        o.subject_reference as patient_fhir_id,
        o.id as observation_fhir_id,

        -- Standardize measurement date
        TRY(CAST(CASE
            WHEN LENGTH(o.effective_date_time) = 10
            THEN o.effective_date_time || 'T00:00:00Z'
            ELSE o.effective_date_time
        END AS TIMESTAMP(3))) as measurement_datetime,

        o.code_text as measurement_type,
        o.value_quantity_value as cd34_count,
        o.value_quantity_unit as cd34_unit,

        -- Categorize CD34 source
        CASE
            WHEN LOWER(o.code_text) LIKE '%apheresis%' THEN 'apheresis_product'
            WHEN LOWER(o.code_text) LIKE '%marrow%' THEN 'marrow_product'
            WHEN LOWER(o.code_text) LIKE '%peripheral%blood%' THEN 'peripheral_blood'
            WHEN LOWER(o.code_text) LIKE '%pbsc%' THEN 'peripheral_blood'
            ELSE 'unspecified'
        END as cd34_source,

        -- Calculate adequacy (≥5×10⁶/kg is adequate)
        CASE
            WHEN o.value_quantity_value IS NOT NULL THEN
                CASE
                    WHEN LOWER(o.value_quantity_unit) LIKE '%10%6%kg%'
                         OR LOWER(o.value_quantity_unit) LIKE '%million%kg%' THEN
                        CASE
                            WHEN CAST(o.value_quantity_value AS DOUBLE) >= 5.0 THEN 'adequate'
                            WHEN CAST(o.value_quantity_value AS DOUBLE) >= 2.0 THEN 'minimal'
                            ELSE 'inadequate'
                        END
                    ELSE 'unit_unclear'
                END
            ELSE NULL
        END as cd34_adequacy

    FROM fhir_prd_db.observation o

    WHERE LOWER(o.code_text) LIKE '%cd34%'
      AND (
        LOWER(o.code_text) LIKE '%apheresis%'
        OR LOWER(o.code_text) LIKE '%marrow%'
        OR LOWER(o.code_text) LIKE '%collection%'
        OR LOWER(o.code_text) LIKE '%harvest%'
        OR LOWER(o.code_text) LIKE '%stem%cell%'
        OR LOWER(o.code_text) LIKE '%pbsc%'
        OR LOWER(o.code_text) LIKE '%progenitor%'
      )
      AND o.value_quantity_value IS NOT NULL
),

mobilization_timing_bounds AS (
    -- Aggregate timing bounds for mobilization medications
    SELECT
        medication_request_id,
        MIN(dosage_instruction_timing_repeat_bounds_period_start) as earliest_bounds_start,
        MAX(dosage_instruction_timing_repeat_bounds_period_end) as latest_bounds_end
    FROM fhir_prd_db.medication_request_dosage_instruction
    WHERE dosage_instruction_timing_repeat_bounds_period_start IS NOT NULL
       OR dosage_instruction_timing_repeat_bounds_period_end IS NOT NULL
    GROUP BY medication_request_id
),

mobilization_agents AS (
    -- Identify mobilization medications (G-CSF, Plerixafor)
    SELECT DISTINCT
        mr.subject_reference as patient_fhir_id,
        mr.id as medication_request_fhir_id,

        -- Standardize start date
        TRY(CAST(CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.earliest_bounds_start) = 10
                    THEN mtb.earliest_bounds_start || 'T00:00:00Z'
                    ELSE mtb.earliest_bounds_start
                END
            WHEN LENGTH(mr.authored_on) = 10
                THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END AS TIMESTAMP(3))) as mobilization_start_datetime,

        -- Standardize end date
        TRY(CAST(CASE
            WHEN mtb.latest_bounds_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.latest_bounds_end) = 10
                    THEN mtb.latest_bounds_end || 'T00:00:00Z'
                    ELSE mtb.latest_bounds_end
                END
            WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mr.dispense_request_validity_period_end) = 10
                    THEN mr.dispense_request_validity_period_end || 'T00:00:00Z'
                    ELSE mr.dispense_request_validity_period_end
                END
            ELSE NULL
        END AS TIMESTAMP(3))) as mobilization_stop_datetime,

        COALESCE(m.code_text, mr.medication_reference_display) as medication_name,
        mcc.code_coding_code as rxnorm_code,
        mcc.code_coding_display as rxnorm_display,

        -- Categorize mobilization agent
        CASE
            WHEN mcc.code_coding_code IN ('105585', '139825') THEN 'filgrastim'
            WHEN mcc.code_coding_code = '358810' THEN 'pegfilgrastim'
            WHEN mcc.code_coding_code = '847232' THEN 'plerixafor'
            WHEN LOWER(m.code_text) LIKE '%filgrastim%' THEN 'filgrastim'
            WHEN LOWER(m.code_text) LIKE '%neupogen%' THEN 'filgrastim'
            WHEN LOWER(m.code_text) LIKE '%neulasta%' THEN 'pegfilgrastim'
            WHEN LOWER(m.code_text) LIKE '%plerixafor%' THEN 'plerixafor'
            WHEN LOWER(m.code_text) LIKE '%mozobil%' THEN 'plerixafor'
            ELSE 'other_mobilization'
        END as mobilization_agent_type,

        mr.status as medication_status

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN mobilization_timing_bounds mtb ON mr.id = mtb.medication_request_id
    LEFT JOIN fhir_prd_db.medication m
        ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'

    WHERE (
        -- RxNorm codes for mobilization agents
        mcc.code_coding_code IN (
            '105585',  -- Filgrastim
            '139825',  -- Filgrastim biosimilar
            '358810',  -- Pegfilgrastim
            '847232'   -- Plerixafor
        )

        -- Text matching for G-CSF and mobilization agents
        OR LOWER(m.code_text) LIKE '%filgrastim%'
        OR LOWER(m.code_text) LIKE '%neupogen%'
        OR LOWER(m.code_text) LIKE '%neulasta%'
        OR LOWER(m.code_text) LIKE '%plerixafor%'
        OR LOWER(m.code_text) LIKE '%mozobil%'
        OR LOWER(mr.medication_reference_display) LIKE '%filgrastim%'
        OR LOWER(mr.medication_reference_display) LIKE '%neupogen%'
        OR LOWER(mr.medication_reference_display) LIKE '%plerixafor%'
    )
    AND mr.status IN ('active', 'completed', 'stopped')
),

product_quality AS (
    -- Extract product quality and viability metrics
    SELECT DISTINCT
        o.subject_reference as patient_fhir_id,
        o.id as observation_fhir_id,

        TRY(CAST(CASE
            WHEN LENGTH(o.effective_date_time) = 10
            THEN o.effective_date_time || 'T00:00:00Z'
            ELSE o.effective_date_time
        END AS TIMESTAMP(3))) as measurement_datetime,

        o.code_text as quality_metric,
        o.value_quantity_value as metric_value,
        o.value_quantity_unit as metric_unit,
        o.value_string as metric_value_text,

        -- Categorize quality metrics
        CASE
            WHEN LOWER(o.code_text) LIKE '%viability%' THEN 'viability'
            WHEN LOWER(o.code_text) LIKE '%volume%' THEN 'volume'
            WHEN LOWER(o.code_text) LIKE '%tnc%' OR LOWER(o.code_text) LIKE '%total%nucleated%' THEN 'total_nucleated_cells'
            WHEN LOWER(o.code_text) LIKE '%sterility%' THEN 'sterility'
            WHEN LOWER(o.code_text) LIKE '%contamination%' THEN 'contamination'
            ELSE 'other_quality'
        END as quality_metric_type

    FROM fhir_prd_db.observation o

    WHERE (
        (LOWER(o.code_text) LIKE '%stem%cell%' OR LOWER(o.code_text) LIKE '%apheresis%')
        AND (
            LOWER(o.code_text) LIKE '%viability%'
            OR LOWER(o.code_text) LIKE '%volume%'
            OR LOWER(o.code_text) LIKE '%tnc%'
            OR LOWER(o.code_text) LIKE '%total%nucleated%'
            OR LOWER(o.code_text) LIKE '%sterility%'
            OR LOWER(o.code_text) LIKE '%contamination%'
            OR LOWER(o.code_text) LIKE '%quality%'
        )
    )
)

-- Main query: Combine all collection data sources
SELECT DISTINCT
    -- Patient identifier
    COALESCE(
        cp.patient_fhir_id,
        cd34.patient_fhir_id,
        ma.patient_fhir_id,
        pq.patient_fhir_id
    ) as patient_fhir_id,

    -- Collection procedure details
    cp.procedure_fhir_id as collection_procedure_fhir_id,
    cp.collection_datetime,
    cp.collection_method,
    cp.collection_cpt_code,
    cp.procedure_status as collection_status,
    cp.procedure_outcome as collection_outcome,

    -- CD34+ cell count metrics
    cd34.observation_fhir_id as cd34_observation_fhir_id,
    TRY(CAST(cd34.measurement_datetime AS TIMESTAMP(3))) as cd34_measurement_datetime,
    cd34.cd34_count,
    cd34.cd34_unit,
    cd34.cd34_source,
    cd34.cd34_adequacy,

    -- Mobilization agent details
    ma.medication_request_fhir_id as mobilization_medication_fhir_id,
    ma.medication_name as mobilization_agent_name,
    ma.rxnorm_code as mobilization_rxnorm_code,
    ma.mobilization_agent_type,
    ma.mobilization_start_datetime,
    ma.mobilization_stop_datetime,
    ma.medication_status as mobilization_status,

    -- Calculate days from mobilization start to collection
    CASE
        WHEN ma.mobilization_start_datetime IS NOT NULL
             AND cp.collection_datetime IS NOT NULL THEN
            DATE_DIFF('day',
                DATE(CAST(ma.mobilization_start_datetime AS TIMESTAMP)),
                DATE(CAST(cp.collection_datetime AS TIMESTAMP))
            )
        ELSE NULL
    END as days_from_mobilization_to_collection,

    -- Product quality metrics
    pq.observation_fhir_id as quality_observation_fhir_id,
    pq.quality_metric,
    pq.quality_metric_type,
    pq.metric_value,
    pq.metric_unit,
    pq.metric_value_text,
    TRY(CAST(pq.measurement_datetime AS TIMESTAMP(3))) as quality_measurement_datetime,

    -- Data completeness indicator
    CASE
        WHEN cp.procedure_fhir_id IS NOT NULL
             AND cd34.observation_fhir_id IS NOT NULL
             AND ma.medication_request_fhir_id IS NOT NULL THEN 'complete'
        WHEN cp.procedure_fhir_id IS NOT NULL
             AND cd34.observation_fhir_id IS NOT NULL THEN 'missing_mobilization'
        WHEN cp.procedure_fhir_id IS NOT NULL
             AND ma.medication_request_fhir_id IS NOT NULL THEN 'missing_cd34'
        WHEN cp.procedure_fhir_id IS NOT NULL THEN 'procedure_only'
        ELSE 'incomplete'
    END as data_completeness

FROM collection_procedures cp
FULL OUTER JOIN cd34_counts cd34
    ON cp.patient_fhir_id = cd34.patient_fhir_id
    AND ABS(DATE_DIFF('day',
        DATE(CAST(cp.collection_datetime AS TIMESTAMP)),
        DATE(CAST(cd34.measurement_datetime AS TIMESTAMP))
    )) <= 7  -- CD34 measured within 7 days of collection
FULL OUTER JOIN mobilization_agents ma
    ON COALESCE(cp.patient_fhir_id, cd34.patient_fhir_id) = ma.patient_fhir_id
    AND ma.mobilization_start_datetime <= COALESCE(cp.collection_datetime, cd34.measurement_datetime)
    AND DATE_DIFF('day',
        DATE(CAST(ma.mobilization_start_datetime AS TIMESTAMP)),
        DATE(CAST(COALESCE(cp.collection_datetime, cd34.measurement_datetime) AS TIMESTAMP))
    ) <= 21  -- Mobilization within 21 days before collection
LEFT JOIN product_quality pq
    ON COALESCE(cp.patient_fhir_id, cd34.patient_fhir_id, ma.patient_fhir_id) = pq.patient_fhir_id
    AND ABS(DATE_DIFF('day',
        DATE(CAST(COALESCE(cp.collection_datetime, cd34.measurement_datetime) AS TIMESTAMP)),
        DATE(CAST(pq.measurement_datetime AS TIMESTAMP))
    )) <= 7  -- Quality metrics within 7 days of collection

ORDER BY
    patient_fhir_id,
    collection_datetime,
    mobilization_start_datetime,
    cd34_measurement_datetime;

-- ================================================================================
-- VIEW: v_visits_unified
-- DATETIME STANDARDIZATION: 4 columns converted from VARCHAR
-- CHANGES:
--   - appointment_end: VARCHAR → TIMESTAMP(3)
--   - appointment_start: VARCHAR → TIMESTAMP(3)
--   - encounter_end: VARCHAR → TIMESTAMP(3)
--   - encounter_start: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_visits_unified AS
WITH appointment_encounter_links AS (
    -- Map appointments to their corresponding encounters
    SELECT DISTINCT
        SUBSTRING(ea.appointment_reference, 13) as appointment_id,  -- Remove "Appointment/" prefix
        ea.encounter_id,
        e.status as encounter_status,
        CAST(FROM_ISO8601_TIMESTAMP(e.period_start) AS TIMESTAMP(3)) as encounter_start,
        CAST(FROM_ISO8601_TIMESTAMP(e.period_end) AS TIMESTAMP(3)) as encounter_end
    FROM fhir_prd_db.encounter_appointment ea
    LEFT JOIN fhir_prd_db.encounter e ON ea.encounter_id = e.id
),
appointments_with_encounters AS (
    SELECT
        CAST(a.id AS VARCHAR) as appointment_fhir_id,
        CAST(ap.participant_actor_reference AS VARCHAR) as patient_fhir_id,

        -- Appointment details (explicit casts for UNION compatibility)
        CAST(a.status AS VARCHAR) as appointment_status,
        CAST(a.appointment_type_text AS VARCHAR) as appointment_type_text,
        TRY(CAST(CAST(a.start AS VARCHAR) AS TIMESTAMP(3))) as appointment_start,
        TRY(CAST(CAST(a."end" AS VARCHAR) AS TIMESTAMP(3))) as appointment_end,
        CAST(a.minutes_duration AS VARCHAR) as appointment_duration_minutes,
        CAST(a.cancelation_reason_text AS VARCHAR) as cancelation_reason_text,
        CAST(a.description AS VARCHAR) as appointment_description,

        -- Linked encounter details (already TIMESTAMP from CTE, just cast again for consistency)
        CAST(ael.encounter_id AS VARCHAR) as encounter_id,
        CAST(ael.encounter_status AS VARCHAR) as encounter_status,
        ael.encounter_start,
        ael.encounter_end,

        -- Visit type classification
        CASE
            WHEN a.status = 'fulfilled' AND ael.encounter_id IS NOT NULL THEN 'completed_scheduled'
            WHEN a.status = 'fulfilled' AND ael.encounter_id IS NULL THEN 'completed_no_encounter'
            WHEN a.status = 'noshow' THEN 'no_show'
            WHEN a.status = 'cancelled' THEN 'cancelled'
            WHEN a.status IN ('booked', 'pending', 'proposed') THEN 'future_scheduled'
            ELSE 'other'
        END as visit_type,

        -- Completion flags
        CASE WHEN a.status = 'fulfilled' THEN true ELSE false END as appointment_completed,
        CASE WHEN ael.encounter_id IS NOT NULL THEN true ELSE false END as encounter_occurred,

        -- Source indicator
        'appointment' as source

    FROM fhir_prd_db.appointment a
    JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
    LEFT JOIN appointment_encounter_links ael ON a.id = ael.appointment_id
    WHERE ap.participant_actor_reference LIKE 'Patient/%'
),
encounters_without_appointments AS (
    -- Find encounters that don't have a linked appointment (walk-ins, emergency, etc.)
    SELECT
        CAST(NULL AS VARCHAR) as appointment_fhir_id,
        CAST(e.subject_reference AS VARCHAR) as patient_fhir_id,

        -- Appointment details (NULL for walk-ins) - types must match appointments_with_encounters
        CAST(NULL AS VARCHAR) as appointment_status,
        CAST(NULL AS VARCHAR) as appointment_type_text,
        TRY(CAST(CAST(NULL AS VARCHAR) AS TIMESTAMP(3))) as appointment_start,
        TRY(CAST(CAST(NULL AS VARCHAR) AS TIMESTAMP(3))) as appointment_end,
        CAST(NULL AS VARCHAR) as appointment_duration_minutes,
        CAST(NULL AS VARCHAR) as cancelation_reason_text,
        CAST(NULL AS VARCHAR) as appointment_description,

        -- Encounter details
        CAST(e.id AS VARCHAR) as encounter_id,
        CAST(e.status AS VARCHAR) as encounter_status,
        CAST(FROM_ISO8601_TIMESTAMP(e.period_start) AS TIMESTAMP(3)) as encounter_start,
        CAST(FROM_ISO8601_TIMESTAMP(e.period_end) AS TIMESTAMP(3)) as encounter_end,

        -- Visit type
        'walk_in_unscheduled' as visit_type,

        -- Completion flags
        CAST(false AS BOOLEAN) as appointment_completed,
        CAST(true AS BOOLEAN) as encounter_occurred,

        -- Source indicator
        'encounter' as source

    FROM fhir_prd_db.encounter e
    WHERE e.subject_reference IS NOT NULL
      AND e.id NOT IN (
          SELECT encounter_id
          FROM fhir_prd_db.encounter_appointment
          WHERE encounter_id IS NOT NULL
      )
),
combined_visits AS (
    SELECT * FROM appointments_with_encounters
    UNION ALL
    SELECT * FROM encounters_without_appointments
),
deduplicated_visits AS (
    -- Assign canonical visit_id and use ROW_NUMBER to pick primary row
    SELECT
        *,
        -- Canonical visit key (prefer encounter_id, fallback to appointment_id with suffix)
        COALESCE(encounter_id, appointment_fhir_id || '_appt') as visit_id,
        -- Use ROW_NUMBER to pick primary row when multiple linkages exist
        ROW_NUMBER() OVER (
            PARTITION BY patient_fhir_id, COALESCE(encounter_id, appointment_fhir_id || '_appt')
            ORDER BY
                CASE WHEN encounter_id IS NOT NULL THEN 1 ELSE 2 END,  -- Prefer rows with encounters
                CASE WHEN appointment_fhir_id IS NOT NULL THEN 1 ELSE 2 END,  -- Then with appointments
                COALESCE(appointment_start, encounter_start) DESC  -- Then most recent
        ) as row_rank
    FROM combined_visits
)
-- Combine both appointment-based and walk-in encounters
SELECT
    dv.patient_fhir_id,

    -- Visit identifiers
    dv.visit_id,
    dv.appointment_fhir_id,
    dv.encounter_id,

    -- Visit classification
    dv.visit_type,
    dv.appointment_completed,
    dv.encounter_occurred,
    dv.source,

    -- Appointment details
    dv.appointment_status,
    dv.appointment_type_text,
    dv.appointment_start,
    dv.appointment_end,
    dv.appointment_duration_minutes,
    dv.cancelation_reason_text,
    dv.appointment_description,

    -- Encounter details
    dv.encounter_status,
    dv.encounter_start,
    dv.encounter_end,

    -- Calculate age at visit (use appointment or encounter date)
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        DATE(COALESCE(dv.appointment_start, dv.encounter_start)))) as age_at_visit_days,

    -- Visit date (earliest of appointment or encounter)
    DATE(COALESCE(dv.appointment_start, dv.encounter_start)) as visit_date

FROM deduplicated_visits dv
LEFT JOIN fhir_prd_db.patient_access pa ON dv.patient_fhir_id = pa.id
WHERE dv.row_rank = 1  -- Only keep primary row per visit

ORDER BY dv.patient_fhir_id, visit_date, dv.appointment_start, dv.encounter_start;

-- ================================================================================
-- VIEW: v_imaging
-- DATETIME STANDARDIZATION: 4 columns converted from VARCHAR
-- CHANGES:
--   - imaging_date: VARCHAR → TIMESTAMP(3)
--   - report_effective_period_start: VARCHAR → TIMESTAMP(3)
--   - report_effective_period_stop: VARCHAR → TIMESTAMP(3)
--   - report_issued: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_imaging AS
WITH report_categories AS (
    SELECT
        diagnostic_report_id,
        LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as category_text
    FROM fhir_prd_db.diagnostic_report_category
    GROUP BY diagnostic_report_id
),
mri_imaging AS (
    -- Aggregate MRI results to prevent JOIN explosion (one row per MRI study)
    SELECT
        mri.patient_id,
        mri.imaging_procedure_id,
        CAST(FROM_ISO8601_TIMESTAMP(mri.result_datetime) AS TIMESTAMP(3)) as imaging_date,
        mri.imaging_procedure,
        mri.result_diagnostic_report_id,
        'MRI' as imaging_modality,
        -- Aggregate multiple result components into single field
        LISTAGG(DISTINCT results.value_string, ' | ') WITHIN GROUP (ORDER BY results.value_string) as result_information,
        LISTAGG(DISTINCT results.result_display, ' | ') WITHIN GROUP (ORDER BY results.result_display) as result_display
    FROM fhir_prd_db.radiology_imaging_mri mri
    LEFT JOIN fhir_prd_db.radiology_imaging_mri_results results
        ON mri.imaging_procedure_id = results.imaging_procedure_id
    GROUP BY mri.patient_id, mri.imaging_procedure_id, mri.result_datetime,
             mri.imaging_procedure, mri.result_diagnostic_report_id
),
other_imaging AS (
    -- Exclude MRIs that are already in mri_imaging to prevent duplicates from UNION
    SELECT
        ri.patient_id,
        ri.imaging_procedure_id,
        CAST(FROM_ISO8601_TIMESTAMP(ri.result_datetime) AS TIMESTAMP(3)) as imaging_date,
        ri.imaging_procedure,
        ri.result_diagnostic_report_id,
        COALESCE(ri.imaging_procedure, 'Unknown') as imaging_modality,
        CAST(NULL AS VARCHAR) as result_information,
        CAST(NULL AS VARCHAR) as result_display
    FROM fhir_prd_db.radiology_imaging ri
    LEFT JOIN fhir_prd_db.radiology_imaging_mri mri
        ON ri.imaging_procedure_id = mri.imaging_procedure_id
    WHERE mri.imaging_procedure_id IS NULL  -- Exclude MRIs already in mri_imaging
),
combined_imaging AS (
    SELECT * FROM mri_imaging
    UNION ALL
    SELECT * FROM other_imaging
)
SELECT
    ci.patient_id as patient_fhir_id,
    ci.patient_id as patient_mrn,  -- Using FHIR ID
    ci.imaging_procedure_id,
    ci.imaging_date,
    ci.imaging_procedure,
    ci.result_diagnostic_report_id,
    ci.imaging_modality,
    ci.result_information,
    ci.result_display,

    -- Diagnostic report fields
    dr.id as diagnostic_report_id,
    dr.status as report_status,
    dr.conclusion as report_conclusion,
    TRY(CAST(dr.issued AS TIMESTAMP(3))) as report_issued,
    TRY(CAST(dr.effective_period_start AS TIMESTAMP(3))) as report_effective_period_start,
    TRY(CAST(dr.effective_period_stop AS TIMESTAMP(3))) as report_effective_period_stop,
    rc.category_text,

    -- Age calculations
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        DATE(ci.imaging_date))) as age_at_imaging_days,
    TRY(DATE_DIFF('year',
        DATE(pa.birth_date),
        DATE(ci.imaging_date))) as age_at_imaging_years

FROM combined_imaging ci
LEFT JOIN fhir_prd_db.diagnostic_report dr
    ON ci.result_diagnostic_report_id = dr.id
LEFT JOIN report_categories rc
    ON dr.id = rc.diagnostic_report_id
LEFT JOIN fhir_prd_db.patient_access pa
    ON ci.patient_id = pa.id
WHERE ci.patient_id IS NOT NULL
ORDER BY ci.patient_id, ci.imaging_date DESC;

-- ================================================================================
-- VIEW: v_measurements
-- DATETIME STANDARDIZATION: 4 columns converted from VARCHAR
-- CHANGES:
--   - lt_measurement_date: VARCHAR → TIMESTAMP(3)
--   - obs_issued: VARCHAR → TIMESTAMP(3)
--   - obs_measurement_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_measurements AS
WITH observations AS (
    SELECT
        subject_reference as patient_fhir_id,
        id as obs_observation_id,
        code_text as obs_measurement_type,
        value_quantity_value as obs_measurement_value,
        value_quantity_unit as obs_measurement_unit,
        TRY(CAST(effective_date_time AS TIMESTAMP(3))) as obs_measurement_date,
        TRY(CAST(issued AS TIMESTAMP(3))) as obs_issued,
        status as obs_status,
        encounter_reference as obs_encounter_reference,
        'observation' as source_table,
        CAST(NULL AS VARCHAR) as lt_test_id,
        CAST(NULL AS VARCHAR) as lt_measurement_type,
        TRY(CAST(CAST(NULL AS VARCHAR) AS TIMESTAMP(3))) as lt_measurement_date,
        CAST(NULL AS VARCHAR) as lt_status,
        CAST(NULL AS VARCHAR) as lt_result_diagnostic_report_id,
        CAST(NULL AS VARCHAR) as lt_lab_test_requester,
        CAST(NULL AS VARCHAR) as ltr_test_component,
        CAST(NULL AS VARCHAR) as ltr_value_string,
        CAST(NULL AS VARCHAR) as ltr_measurement_value,
        CAST(NULL AS VARCHAR) as ltr_measurement_unit,
        CAST(NULL AS VARCHAR) as ltr_value_codeable_concept_text,
        CAST(NULL AS VARCHAR) as ltr_value_range_low_value,
        CAST(NULL AS VARCHAR) as ltr_value_range_low_unit,
        CAST(NULL AS VARCHAR) as ltr_value_range_high_value,
        CAST(NULL AS VARCHAR) as ltr_value_range_high_unit,
        CAST(NULL AS VARCHAR) as ltr_value_boolean,
        CAST(NULL AS VARCHAR) as ltr_value_integer,
        CAST(NULL AS VARCHAR) as ltr_components_json,
        CAST(NULL AS VARCHAR) as ltr_components_list,
        CAST(NULL AS VARCHAR) as ltr_components_with_values
    FROM fhir_prd_db.observation
    WHERE subject_reference IS NOT NULL
),
lab_tests_aggregated AS (
    -- Aggregate lab test components to prevent JOIN explosion (one row per test)
    SELECT
        lt.patient_id,
        lt.test_id,
        lt.lab_test_name,
        lt.result_datetime,
        lt.lab_test_status,
        lt.result_diagnostic_report_id,
        lt.lab_test_requester,
        -- Aggregate components using LISTAGG (Athena doesn't support json_arrayagg)
        -- Cannot use DISTINCT with complex ORDER BY, so remove DISTINCT
        LISTAGG(ltr.test_component, ' | ')
            WITHIN GROUP (ORDER BY ltr.test_component) AS components_list,
        LISTAGG(
            CONCAT(ltr.test_component, ': ', COALESCE(CAST(ltr.value_quantity_value AS VARCHAR), ltr.value_string), ' ', COALESCE(ltr.value_quantity_unit, '')),
            ' | '
        ) WITHIN GROUP (ORDER BY ltr.test_component) AS components_with_values
    FROM fhir_prd_db.lab_tests lt
    LEFT JOIN fhir_prd_db.lab_test_results ltr
           ON lt.test_id = ltr.test_id
    WHERE lt.patient_id IS NOT NULL
    GROUP BY lt.patient_id, lt.test_id, lt.lab_test_name, lt.result_datetime,
             lt.lab_test_status, lt.result_diagnostic_report_id, lt.lab_test_requester
),
lab_tests_with_results AS (
    SELECT
        lta.patient_id as patient_fhir_id,
        CAST(NULL AS VARCHAR) as obs_observation_id,
        CAST(NULL AS VARCHAR) as obs_measurement_type,
        CAST(NULL AS VARCHAR) as obs_measurement_value,
        CAST(NULL AS VARCHAR) as obs_measurement_unit,
        TRY(CAST(CAST(NULL AS VARCHAR) AS TIMESTAMP(3))) as obs_measurement_date,
        TRY(CAST(CAST(NULL AS VARCHAR) AS TIMESTAMP(3))) as obs_issued,
        CAST(NULL AS VARCHAR) as obs_status,
        CAST(NULL AS VARCHAR) as obs_encounter_reference,
        'lab_tests' as source_table,
        lta.test_id as lt_test_id,
        lta.lab_test_name as lt_measurement_type,
        CAST(FROM_ISO8601_TIMESTAMP(lta.result_datetime) AS TIMESTAMP(3)) as lt_measurement_date,
        lta.lab_test_status as lt_status,
        lta.result_diagnostic_report_id as lt_result_diagnostic_report_id,
        lta.lab_test_requester as lt_lab_test_requester,
        lta.components_list as ltr_components_list,
        lta.components_with_values as ltr_components_with_values,
        -- Legacy single-value fields set to NULL (components are aggregated now)
        CAST(NULL AS VARCHAR) as ltr_test_component,
        CAST(NULL AS VARCHAR) as ltr_components_json,
        CAST(NULL AS VARCHAR) as ltr_value_string,
        CAST(NULL AS VARCHAR) as ltr_measurement_value,
        CAST(NULL AS VARCHAR) as ltr_measurement_unit,
        CAST(NULL AS VARCHAR) as ltr_value_codeable_concept_text,
        CAST(NULL AS VARCHAR) as ltr_value_range_low_value,
        CAST(NULL AS VARCHAR) as ltr_value_range_low_unit,
        CAST(NULL AS VARCHAR) as ltr_value_range_high_value,
        CAST(NULL AS VARCHAR) as ltr_value_range_high_unit,
        CAST(NULL AS VARCHAR) as ltr_value_boolean,
        CAST(NULL AS VARCHAR) as ltr_value_integer
    FROM lab_tests_aggregated lta
)
SELECT
    combined.*,
    pa.birth_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        DATE(COALESCE(obs_measurement_date, lt_measurement_date)))) as age_at_measurement_days,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        DATE(COALESCE(obs_measurement_date, lt_measurement_date))) / 365.25) as age_at_measurement_years
FROM (
    SELECT * FROM observations
    UNION ALL
    SELECT * FROM lab_tests_with_results
) combined
LEFT JOIN fhir_prd_db.patient_access pa ON combined.patient_fhir_id = pa.id
ORDER BY combined.patient_fhir_id, COALESCE(obs_measurement_date, lt_measurement_date);

-- ================================================================================
-- VIEW: v_molecular_tests
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - mt_procedure_date: VARCHAR → TIMESTAMP(3)
--   - mt_specimen_collection_date: VARCHAR → TIMESTAMP(3)
--   - mt_test_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_molecular_tests AS
WITH aggregated_results AS (
    SELECT
        test_id,
        dgd_id,
        COUNT(*) as component_count,
        SUM(LENGTH(COALESCE(test_result_narrative, ''))) as total_narrative_chars,
        LISTAGG(DISTINCT test_component, '; ')
            WITHIN GROUP (ORDER BY test_component) as components_list
    FROM fhir_prd_db.molecular_test_results
    GROUP BY test_id, dgd_id
),
specimen_linkage AS (
    -- Aggregate multiple specimens per test to prevent JOIN explosion
    SELECT
        ar.test_id,
        MIN(ar.dgd_id) AS dgd_id,
        MIN(sri.service_request_id) AS service_request_id,
        MIN(sr.encounter_reference) AS encounter_reference,
        MIN(REPLACE(sr.encounter_reference, 'Encounter/', '')) AS encounter_id,
        MIN(s.id) AS specimen_id,
        LISTAGG(DISTINCT s.type_text, ' | ') WITHIN GROUP (ORDER BY s.type_text) AS specimen_types,
        LISTAGG(DISTINCT s.collection_body_site_text, ' | ') WITHIN GROUP (ORDER BY s.collection_body_site_text) AS specimen_sites,
        MIN(s.collection_collected_date_time) AS specimen_collection_date,
        MIN(s.accession_identifier_value) AS specimen_accession,
        -- Aggregate all specimen IDs (Athena doesn't support json_arrayagg)
        LISTAGG(DISTINCT s.id, ' | ') WITHIN GROUP (ORDER BY s.id) AS specimen_ids
    FROM aggregated_results ar
    LEFT JOIN fhir_prd_db.service_request_identifier sri
        ON ar.dgd_id = sri.identifier_value
    LEFT JOIN fhir_prd_db.service_request sr
        ON sri.service_request_id = sr.id
    LEFT JOIN fhir_prd_db.service_request_specimen srs
        ON sr.id = srs.service_request_id
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(srs.specimen_reference, 'Specimen/', '') = s.id
    GROUP BY ar.test_id
),
procedure_linkage AS (
    SELECT
        sl.test_id,
        MIN(p.id) AS procedure_id,
        MIN(p.code_text) AS procedure_name,
        MIN(p.performed_date_time) AS procedure_date,
        MIN(p.status) AS procedure_status
    FROM specimen_linkage sl
    LEFT JOIN fhir_prd_db.procedure p
        ON sl.encounter_id = REPLACE(p.encounter_reference, 'Encounter/', '')
        AND p.code_text LIKE '%SURGICAL%'
    WHERE sl.encounter_id IS NOT NULL
    GROUP BY sl.test_id
)
SELECT
    mt.patient_id as patient_fhir_id,
    mt.test_id as mt_test_id,
    CAST(FROM_ISO8601_TIMESTAMP(mt.result_datetime) AS DATE) as mt_test_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(FROM_ISO8601_TIMESTAMP(mt.result_datetime) AS DATE))) as age_at_test_days,
    mt.lab_test_name as mt_lab_test_name,
    mt.lab_test_status as mt_test_status,
    mt.lab_test_requester as mt_test_requester,
    COALESCE(ar.component_count, 0) as mtr_component_count,
    COALESCE(ar.total_narrative_chars, 0) as mtr_total_narrative_chars,
    COALESCE(ar.components_list, 'None') as mtr_components_list,
    sl.specimen_id as mt_specimen_id,
    sl.specimen_ids as mt_specimen_ids,
    sl.specimen_types as mt_specimen_types,
    sl.specimen_sites as mt_specimen_sites,
    TRY(CAST(SUBSTR(sl.specimen_collection_date, 1, 10) AS TIMESTAMP(3))) as mt_specimen_collection_date,
    sl.specimen_accession as mt_specimen_accession,
    sl.encounter_id as mt_encounter_id,
    pl.procedure_id as mt_procedure_id,
    pl.procedure_name as mt_procedure_name,
    TRY(CAST(SUBSTR(pl.procedure_date, 1, 10) AS TIMESTAMP(3))) as mt_procedure_date,
    pl.procedure_status as mt_procedure_status
FROM fhir_prd_db.molecular_tests mt
LEFT JOIN aggregated_results ar ON mt.test_id = ar.test_id
LEFT JOIN specimen_linkage sl ON mt.test_id = sl.test_id
LEFT JOIN procedure_linkage pl ON mt.test_id = pl.test_id
LEFT JOIN fhir_prd_db.patient_access pa ON mt.patient_id = pa.id
WHERE mt.patient_id IS NOT NULL
ORDER BY mt.result_datetime, mt.test_id;

-- ================================================================================
-- VIEW: v_imaging_corticosteroid_use
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - medication_start_datetime: VARCHAR → TIMESTAMP(3)
--   - medication_stop_datetime: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_imaging_corticosteroid_use AS

WITH medication_timing_bounds AS (
    -- Aggregate timing bounds from dosage instruction sub-schema
    SELECT
        medication_request_id,
        MIN(dosage_instruction_timing_repeat_bounds_period_start) as earliest_bounds_start,
        MAX(dosage_instruction_timing_repeat_bounds_period_end) as latest_bounds_end
    FROM fhir_prd_db.medication_request_dosage_instruction
    WHERE dosage_instruction_timing_repeat_bounds_period_start IS NOT NULL
       OR dosage_instruction_timing_repeat_bounds_period_end IS NOT NULL
    GROUP BY medication_request_id
),

corticosteroid_medications AS (
    -- Identify all corticosteroid medications (systemic use)
    SELECT DISTINCT
        mr.id as medication_request_fhir_id,
        mr.subject_reference as patient_fhir_id,

        -- Medication identification
        COALESCE(m.code_text, mr.medication_reference_display) as medication_name,
        mcc.code_coding_code as rxnorm_cui,
        mcc.code_coding_display as rxnorm_display,

        -- Standardized generic name (maps to RxNorm ingredient level)
        CASE
            -- High priority glucocorticoids
            WHEN mcc.code_coding_code = '3264'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%dexamethasone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%decadron%'
                THEN 'dexamethasone'
            WHEN mcc.code_coding_code = '8640'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prednisone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%deltasone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%rayos%'
                THEN 'prednisone'
            WHEN mcc.code_coding_code = '8638'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prednisolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%orapred%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prelone%'
                THEN 'prednisolone'
            WHEN mcc.code_coding_code = '6902'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%methylprednisolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%medrol%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%solu-medrol%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%solumedrol%'
                THEN 'methylprednisolone'
            WHEN mcc.code_coding_code = '5492'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%hydrocortisone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cortef%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%solu-cortef%'
                THEN 'hydrocortisone'
            WHEN mcc.code_coding_code IN ('1514', '1347')  -- Both CUIs found in data
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%betamethasone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%celestone%'
                THEN 'betamethasone'
            WHEN mcc.code_coding_code = '10759'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%triamcinolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%kenalog%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%aristospan%'
                THEN 'triamcinolone'

            -- Medium priority glucocorticoids
            WHEN mcc.code_coding_code = '2878'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cortisone%'
                THEN 'cortisone'
            WHEN mcc.code_coding_code = '22396'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%deflazacort%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%emflaza%'
                THEN 'deflazacort'
            WHEN mcc.code_coding_code = '7910'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%paramethasone%'
                THEN 'paramethasone'
            WHEN mcc.code_coding_code = '29523'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%meprednisone%'
                THEN 'meprednisone'
            WHEN mcc.code_coding_code = '4463'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%fluocortolone%'
                THEN 'fluocortolone'
            WHEN mcc.code_coding_code = '55681'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%rimexolone%'
                THEN 'rimexolone'

            -- Lower priority glucocorticoids (rare)
            WHEN mcc.code_coding_code = '12473'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prednylidene%'
                THEN 'prednylidene'
            WHEN mcc.code_coding_code = '21285'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cloprednol%'
                THEN 'cloprednol'
            WHEN mcc.code_coding_code = '21660'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cortivazol%'
                THEN 'cortivazol'
            WHEN mcc.code_coding_code = '2669799'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%vamorolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%agamree%'
                THEN 'vamorolone'

            -- Mineralocorticoids
            WHEN mcc.code_coding_code = '4452'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%fludrocortisone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%florinef%'
                THEN 'fludrocortisone'
            WHEN mcc.code_coding_code = '3256'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%desoxycorticosterone%'
                THEN 'desoxycorticosterone'
            WHEN mcc.code_coding_code = '1312358'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%aldosterone%'
                THEN 'aldosterone'

            ELSE 'other_corticosteroid'
        END as corticosteroid_generic_name,

        -- Detection method
        CASE
            WHEN mcc.code_coding_code IS NOT NULL THEN 'rxnorm_cui'
            ELSE 'text_match'
        END as detection_method,

        -- Temporal fields - hierarchical date selection
        TRY(CAST(CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.earliest_bounds_start) = 10
                    THEN mtb.earliest_bounds_start || 'T00:00:00Z'
                    ELSE mtb.earliest_bounds_start
                END
            WHEN LENGTH(mr.authored_on) = 10
                THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END AS TIMESTAMP(3))) as medication_start_datetime,

        TRY(CAST(CASE
            WHEN mtb.latest_bounds_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.latest_bounds_end) = 10
                    THEN mtb.latest_bounds_end || 'T00:00:00Z'
                    ELSE mtb.latest_bounds_end
                END
            WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mr.dispense_request_validity_period_end) = 10
                    THEN mr.dispense_request_validity_period_end || 'T00:00:00Z'
                    ELSE mr.dispense_request_validity_period_end
                END
            ELSE NULL
        END AS TIMESTAMP(3))) as medication_stop_datetime,

        mr.status as medication_status

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN medication_timing_bounds mtb ON mr.id = mtb.medication_request_id
    LEFT JOIN fhir_prd_db.medication m
        ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'

    WHERE (
        -- ====================================================================
        -- COMPLETE RxNorm CUI List from RxClass API (ATC H02AB + H02AA)
        -- Source: https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json
        -- Query Date: 2025-10-18
        -- Total: 20 corticosteroid ingredients (TTY=IN)
        -- ====================================================================

        -- GLUCOCORTICOIDS (ATC H02AB) - 17 ingredients
        mcc.code_coding_code IN (
            -- High Priority (Common in neuro-oncology)
            '3264',    -- dexamethasone *** MOST COMMON ***
            '8640',    -- prednisone
            '8638',    -- prednisolone
            '6902',    -- methylprednisolone
            '5492',    -- hydrocortisone
            '1514',    -- betamethasone (NOTE: API shows 1514, not 1347)
            '10759',   -- triamcinolone

            -- Medium Priority (Less common but systemic)
            '2878',    -- cortisone
            '22396',   -- deflazacort
            '7910',    -- paramethasone
            '29523',   -- meprednisone
            '4463',    -- fluocortolone
            '55681',   -- rimexolone

            -- Lower Priority (Rare/specialized)
            '12473',   -- prednylidene
            '21285',   -- cloprednol
            '21660',   -- cortivazol
            '2669799'  -- vamorolone (newest - approved 2020 for Duchenne MD)
        )

        -- MINERALOCORTICOIDS (ATC H02AA) - 3 ingredients
        OR mcc.code_coding_code IN (
            '4452',    -- fludrocortisone (most common mineralocorticoid)
            '3256',    -- desoxycorticosterone
            '1312358'  -- aldosterone
        )

        -- ====================================================================
        -- TEXT MATCHING (Fallback for medications without RxNorm codes)
        -- ====================================================================

        -- Generic names (most common)
        OR LOWER(m.code_text) LIKE '%dexamethasone%'
        OR LOWER(m.code_text) LIKE '%prednisone%'
        OR LOWER(m.code_text) LIKE '%prednisolone%'
        OR LOWER(m.code_text) LIKE '%methylprednisolone%'
        OR LOWER(m.code_text) LIKE '%hydrocortisone%'
        OR LOWER(m.code_text) LIKE '%betamethasone%'
        OR LOWER(m.code_text) LIKE '%triamcinolone%'
        OR LOWER(m.code_text) LIKE '%cortisone%'
        OR LOWER(m.code_text) LIKE '%fludrocortisone%'
        OR LOWER(m.code_text) LIKE '%deflazacort%'

        -- Generic names (less common)
        OR LOWER(m.code_text) LIKE '%paramethasone%'
        OR LOWER(m.code_text) LIKE '%meprednisone%'
        OR LOWER(m.code_text) LIKE '%fluocortolone%'
        OR LOWER(m.code_text) LIKE '%rimexolone%'
        OR LOWER(m.code_text) LIKE '%prednylidene%'
        OR LOWER(m.code_text) LIKE '%cloprednol%'
        OR LOWER(m.code_text) LIKE '%cortivazol%'
        OR LOWER(m.code_text) LIKE '%vamorolone%'
        OR LOWER(m.code_text) LIKE '%desoxycorticosterone%'
        OR LOWER(m.code_text) LIKE '%aldosterone%'

        -- Brand names (high priority)
        OR LOWER(m.code_text) LIKE '%decadron%'
        OR LOWER(m.code_text) LIKE '%medrol%'
        OR LOWER(m.code_text) LIKE '%solu-medrol%'
        OR LOWER(m.code_text) LIKE '%solumedrol%'
        OR LOWER(m.code_text) LIKE '%deltasone%'
        OR LOWER(m.code_text) LIKE '%rayos%'
        OR LOWER(m.code_text) LIKE '%orapred%'
        OR LOWER(m.code_text) LIKE '%prelone%'
        OR LOWER(m.code_text) LIKE '%cortef%'
        OR LOWER(m.code_text) LIKE '%solu-cortef%'
        OR LOWER(m.code_text) LIKE '%celestone%'
        OR LOWER(m.code_text) LIKE '%kenalog%'
        OR LOWER(m.code_text) LIKE '%aristospan%'
        OR LOWER(m.code_text) LIKE '%florinef%'
        OR LOWER(m.code_text) LIKE '%emflaza%'
        OR LOWER(m.code_text) LIKE '%agamree%'  -- vamorolone brand

        -- Same patterns for medication_reference_display
        OR LOWER(mr.medication_reference_display) LIKE '%dexamethasone%'
        OR LOWER(mr.medication_reference_display) LIKE '%decadron%'
        OR LOWER(mr.medication_reference_display) LIKE '%prednisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%prednisolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%methylprednisolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%medrol%'
        OR LOWER(mr.medication_reference_display) LIKE '%solu-medrol%'
        OR LOWER(mr.medication_reference_display) LIKE '%hydrocortisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%cortef%'
        OR LOWER(mr.medication_reference_display) LIKE '%betamethasone%'
        OR LOWER(mr.medication_reference_display) LIKE '%celestone%'
        OR LOWER(mr.medication_reference_display) LIKE '%triamcinolone%'
        OR LOWER(mr.medication_reference_display) LIKE '%kenalog%'
        OR LOWER(mr.medication_reference_display) LIKE '%fludrocortisone%'
        OR LOWER(mr.medication_reference_display) LIKE '%florinef%'
        OR LOWER(mr.medication_reference_display) LIKE '%deflazacort%'
        OR LOWER(mr.medication_reference_display) LIKE '%emflaza%'
    )
    AND mr.status IN ('active', 'completed', 'stopped', 'on-hold')
),

imaging_corticosteroid_matches AS (
    -- Match imaging studies to corticosteroid medications
    SELECT
        img.patient_fhir_id,
        img.imaging_procedure_id,
        img.imaging_date,
        img.imaging_modality,
        img.imaging_procedure,

        cm.medication_request_fhir_id,
        cm.medication_name,
        cm.rxnorm_cui,
        cm.rxnorm_display,
        cm.corticosteroid_generic_name,
        cm.detection_method,
        cm.medication_start_datetime,
        cm.medication_stop_datetime,
        cm.medication_status,

        -- Calculate temporal relationship
        DATE_DIFF('day',
            DATE(CAST(cm.medication_start_datetime AS TIMESTAMP)),
            DATE(CAST(img.imaging_date AS TIMESTAMP))
        ) as days_from_med_start_to_imaging,

        CASE
            WHEN cm.medication_stop_datetime IS NOT NULL THEN
                DATE_DIFF('day',
                    DATE(CAST(img.imaging_date AS TIMESTAMP)),
                    DATE(CAST(cm.medication_stop_datetime AS TIMESTAMP))
                )
            ELSE NULL
        END as days_from_imaging_to_med_stop,

        -- Temporal relationship categories
        CASE
            WHEN DATE(CAST(img.imaging_date AS TIMESTAMP))
                 BETWEEN DATE(CAST(cm.medication_start_datetime AS TIMESTAMP))
                     AND COALESCE(DATE(CAST(cm.medication_stop_datetime AS TIMESTAMP)),
                                  DATE(CAST(img.imaging_date AS TIMESTAMP)))
                THEN 'exact_date_match'
            WHEN DATE(CAST(img.imaging_date AS TIMESTAMP))
                 BETWEEN DATE(CAST(cm.medication_start_datetime AS TIMESTAMP)) - INTERVAL '7' DAY
                     AND COALESCE(DATE(CAST(cm.medication_stop_datetime AS TIMESTAMP)) + INTERVAL '7' DAY,
                                  DATE(CAST(img.imaging_date AS TIMESTAMP)) + INTERVAL '7' DAY)
                THEN 'within_7day_window'
            WHEN DATE(CAST(img.imaging_date AS TIMESTAMP))
                 BETWEEN DATE(CAST(cm.medication_start_datetime AS TIMESTAMP)) - INTERVAL '14' DAY
                     AND COALESCE(DATE(CAST(cm.medication_stop_datetime AS TIMESTAMP)) + INTERVAL '14' DAY,
                                  DATE(CAST(img.imaging_date AS TIMESTAMP)) + INTERVAL '14' DAY)
                THEN 'within_14day_window'
            ELSE 'outside_window'
        END as temporal_relationship

    FROM fhir_prd_db.v_imaging img
    LEFT JOIN corticosteroid_medications cm
        ON img.patient_fhir_id = cm.patient_fhir_id
        -- Apply temporal filter: medication active within ±14 days of imaging
        AND DATE(CAST(img.imaging_date AS TIMESTAMP))
            BETWEEN DATE(CAST(cm.medication_start_datetime AS TIMESTAMP)) - INTERVAL '14' DAY
                AND COALESCE(DATE(CAST(cm.medication_stop_datetime AS TIMESTAMP)) + INTERVAL '14' DAY,
                             DATE(CAST(img.imaging_date AS TIMESTAMP)) + INTERVAL '14' DAY)
),

corticosteroid_counts AS (
    -- Count concurrent corticosteroids per imaging study
    SELECT
        imaging_procedure_id,
        COUNT(DISTINCT corticosteroid_generic_name) as total_corticosteroids_count,
        LISTAGG(DISTINCT corticosteroid_generic_name, '; ')
            WITHIN GROUP (ORDER BY corticosteroid_generic_name) as corticosteroid_list
    FROM imaging_corticosteroid_matches
    WHERE temporal_relationship IN ('exact_date_match', 'within_7day_window', 'within_14day_window')
    GROUP BY imaging_procedure_id
)

-- Main query
SELECT
    icm.patient_fhir_id,
    icm.imaging_procedure_id,
    icm.imaging_date,
    icm.imaging_modality,
    icm.imaging_procedure,

    -- Corticosteroid exposure flag
    CASE
        WHEN icm.medication_request_fhir_id IS NOT NULL
             AND icm.temporal_relationship IN ('exact_date_match', 'within_7day_window')
            THEN true
        ELSE false
    END as on_corticosteroid,

    -- Corticosteroid details
    icm.medication_request_fhir_id as corticosteroid_medication_fhir_id,
    icm.medication_name as corticosteroid_name,
    icm.rxnorm_cui as corticosteroid_rxnorm_cui,
    icm.rxnorm_display as corticosteroid_rxnorm_display,
    icm.corticosteroid_generic_name,
    icm.detection_method,

    -- Temporal details
    icm.medication_start_datetime,
    icm.medication_stop_datetime,
    icm.days_from_med_start_to_imaging,
    icm.days_from_imaging_to_med_stop,
    icm.temporal_relationship,
    icm.medication_status,

    -- Aggregated counts
    COALESCE(cc.total_corticosteroids_count, 0) as total_corticosteroids_count,
    cc.corticosteroid_list

FROM imaging_corticosteroid_matches icm
LEFT JOIN corticosteroid_counts cc
    ON icm.imaging_procedure_id = cc.imaging_procedure_id

ORDER BY icm.patient_fhir_id, icm.imaging_date DESC, icm.corticosteroid_generic_name;

-- ================================================================================
-- VIEW: v_problem_list_diagnoses
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - pld_abatement_date: VARCHAR → TIMESTAMP(3)
--   - pld_onset_date: VARCHAR → TIMESTAMP(3)
--   - pld_recorded_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_problem_list_diagnoses AS
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id as pld_condition_id,
    pld.diagnosis_name as pld_diagnosis_name,
    pld.clinical_status_text as pld_clinical_status,
    TRY(CAST(CASE
        WHEN LENGTH(pld.onset_date_time) = 10 THEN pld.onset_date_time || 'T00:00:00Z'
        ELSE pld.onset_date_time
    END AS TIMESTAMP(3))) as pld_onset_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.onset_date_time, 1, 10) AS DATE))) as age_at_onset_days,
    TRY(CAST(CASE
        WHEN LENGTH(pld.abatement_date_time) = 10 THEN pld.abatement_date_time || 'T00:00:00Z'
        ELSE pld.abatement_date_time
    END AS TIMESTAMP(3))) as pld_abatement_date,
    TRY(CAST(CASE
        WHEN LENGTH(pld.recorded_date) = 10 THEN pld.recorded_date || 'T00:00:00Z'
        ELSE pld.recorded_date
    END AS TIMESTAMP(3))) as pld_recorded_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.recorded_date, 1, 10) AS DATE))) as age_at_recorded_days,
    pld.icd10_code as pld_icd10_code,
    pld.icd10_display as pld_icd10_display,
    pld.snomed_code as pld_snomed_code,
    pld.snomed_display as pld_snomed_display
FROM fhir_prd_db.problem_list_diagnoses pld
LEFT JOIN fhir_prd_db.patient_access pa ON pld.patient_id = pa.id
WHERE pld.patient_id IS NOT NULL
ORDER BY pld.patient_id, pld.recorded_date;

-- ================================================================================
-- VIEW: v_radiation_documents
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - doc_context_period_end: VARCHAR → TIMESTAMP(3)
--   - doc_context_period_start: VARCHAR → TIMESTAMP(3)
--   - doc_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
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
    TRY(CAST(dr.date AS TIMESTAMP(3))) as doc_date,
    dr.status as doc_status,
    dr.doc_status as doc_doc_status,
    TRY(CAST(dr.context_period_start AS TIMESTAMP(3))) as doc_context_period_start,
    TRY(CAST(dr.context_period_end AS TIMESTAMP(3))) as doc_context_period_end,
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
-- VIEW: v_radiation_treatment_appointments
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - appointment_start: VARCHAR → TIMESTAMP(3)
--   - appointment_end: VARCHAR → TIMESTAMP(3)
--   - created: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

-- ================================================================================
-- VIEW: v_radiation_treatment_appointments - FIXED VERSION
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - appointment_start: VARCHAR → TIMESTAMP(3)
--   - appointment_end: VARCHAR → TIMESTAMP(3)
--   - created: VARCHAR → TIMESTAMP(3)
-- FIXES APPLIED (2025-10-21):
--   - Original view returned ALL appointments for ALL patients with no filtering
--   - Added multi-layer radiation-specific filtering:
--     1. Explicit radiation service types
--     2. Explicit radiation appointment types
--     3. Patient restriction to known radiation patients
--     4. Keyword filtering on radiation-related text
--     5. Temporal matching with treatment date windows
--   - Added radiation_identification_method for provenance tracking
-- PRESERVED: All original columns plus new filtering and provenance fields
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
    TRY(CAST(a.start AS TIMESTAMP(3))) as appointment_start,
    TRY(CAST(a."end" AS TIMESTAMP(3))) as appointment_end,
    a.minutes_duration,
    TRY(CAST(a.created AS TIMESTAMP(3))) as created,
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

/*
-- ================================================================================
-- 11-15. ORIGINAL RADIATION VIEWS (COMMENTED OUT - REPLACED BY CONSOLIDATED VIEWS)
-- ================================================================================
-- Date Deprecated: October 18, 2025
-- Reason: Replaced by v_radiation_treatments (consolidated) and v_radiation_documents
-- These views are preserved below for reference but commented out
-- Original views did not include observation-based structured dose/site data
-- ================================================================================

-- ================================================================================
-- VIEW: v_binary_files
-- DATETIME STANDARDIZATION: 3 columns converted from VARCHAR
-- CHANGES:
--   - dr_context_period_end: VARCHAR → TIMESTAMP(3)
--   - dr_context_period_start: VARCHAR → TIMESTAMP(3)
--   - dr_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_binary_files AS
WITH document_contexts AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT context_encounter_reference, ' | ')
            WITHIN GROUP (ORDER BY context_encounter_reference) as encounter_references,
        LISTAGG(DISTINCT context_encounter_display, ' | ')
            WITHIN GROUP (ORDER BY context_encounter_display) as encounter_displays
    FROM fhir_prd_db.document_reference_context_encounter
    GROUP BY document_reference_id
),
document_categories AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT category_text, ' | ')
            WITHIN GROUP (ORDER BY category_text) as category_text
    FROM fhir_prd_db.document_reference_category
    GROUP BY document_reference_id
),
document_type_coding AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT type_coding_system, ' | ')
            WITHIN GROUP (ORDER BY type_coding_system) as type_coding_systems,
        LISTAGG(DISTINCT type_coding_code, ' | ')
            WITHIN GROUP (ORDER BY type_coding_code) as type_coding_codes,
        LISTAGG(DISTINCT type_coding_display, ' | ')
            WITHIN GROUP (ORDER BY type_coding_display) as type_coding_displays
    FROM fhir_prd_db.document_reference_type_coding
    GROUP BY document_reference_id
)
SELECT
    dr.id as document_reference_id,
    dr.subject_reference as patient_fhir_id,
    dr.status as dr_status,
    dr.doc_status as dr_doc_status,
    dr.type_text as dr_type_text,
    dcat.category_text as dr_category_text,
    TRY(CAST(FROM_ISO8601_TIMESTAMP(NULLIF(dr.date, '')) AS TIMESTAMP(3))) as dr_date,
    dr.description as dr_description,
    TRY(CAST(FROM_ISO8601_TIMESTAMP(NULLIF(dr.context_period_start, '')) AS TIMESTAMP(3))) as dr_context_period_start,
    TRY(CAST(FROM_ISO8601_TIMESTAMP(NULLIF(dr.context_period_end, '')) AS TIMESTAMP(3))) as dr_context_period_end,
    dr.context_facility_type_text as dr_facility_type,
    dr.context_practice_setting_text as dr_practice_setting,
    dr.authenticator_display as dr_authenticator,
    dr.custodian_display as dr_custodian,
    denc.encounter_references as dr_encounter_references,
    denc.encounter_displays as dr_encounter_displays,

    dtc.type_coding_systems as dr_type_coding_systems,
    dtc.type_coding_codes as dr_type_coding_codes,
    dtc.type_coding_displays as dr_type_coding_displays,

    dcont.content_attachment_url as binary_id,
    dcont.content_attachment_content_type as content_type,
    dcont.content_attachment_size as content_size_bytes,
    dcont.content_attachment_title as content_title,
    dcont.content_format_display as content_format,

    TRY(DATE_DIFF('day', DATE(pa.birth_date), DATE(FROM_ISO8601_TIMESTAMP(NULLIF(dr.date, ''))))) as age_at_document_days

FROM fhir_prd_db.document_reference dr
LEFT JOIN document_contexts denc ON dr.id = denc.document_reference_id
LEFT JOIN document_categories dcat ON dr.id = dcat.document_reference_id
LEFT JOIN document_type_coding dtc ON dr.id = dtc.document_reference_id
LEFT JOIN fhir_prd_db.document_reference_content dcont ON dr.id = dcont.document_reference_id
LEFT JOIN fhir_prd_db.patient pa ON dr.subject_reference = CONCAT('Patient/', pa.id)
WHERE dr.subject_reference IS NOT NULL
ORDER BY dr.subject_reference, dr.date DESC;

-- ================================================================================
-- VIEW: v_encounters
-- DATETIME STANDARDIZATION: 2 columns converted from VARCHAR
-- CHANGES:
--   - period_start: VARCHAR → TIMESTAMP(3)
--   - period_end: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_encounters AS
WITH encounter_types_agg AS (
    SELECT
        encounter_id,
        LISTAGG(type_coding, '; ') WITHIN GROUP (ORDER BY type_coding) as type_coding,
        LISTAGG(type_text, '; ') WITHIN GROUP (ORDER BY type_text) as type_text
    FROM (
        SELECT DISTINCT encounter_id, type_coding, type_text
        FROM fhir_prd_db.encounter_type
    )
    GROUP BY encounter_id
),
encounter_reasons_agg AS (
    SELECT
        encounter_id,
        LISTAGG(reason_code_coding, '; ') WITHIN GROUP (ORDER BY reason_code_coding) as reason_code_coding,
        LISTAGG(reason_code_text, '; ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text
    FROM (
        SELECT DISTINCT encounter_id, reason_code_coding, reason_code_text
        FROM fhir_prd_db.encounter_reason_code
    )
    GROUP BY encounter_id
),
encounter_diagnoses_agg AS (
    SELECT
        encounter_id,
        LISTAGG(diagnosis_condition_reference, '; ') WITHIN GROUP (ORDER BY diagnosis_condition_reference) as diagnosis_condition_reference,
        LISTAGG(diagnosis_condition_display, '; ') WITHIN GROUP (ORDER BY diagnosis_condition_display) as diagnosis_condition_display,
        LISTAGG(diagnosis_use_coding, '; ') WITHIN GROUP (ORDER BY diagnosis_use_coding) as diagnosis_use_coding,
        LISTAGG(diagnosis_rank_str, '; ') WITHIN GROUP (ORDER BY diagnosis_rank_str) as diagnosis_rank
    FROM (
        SELECT DISTINCT
            encounter_id,
            diagnosis_condition_reference,
            diagnosis_condition_display,
            diagnosis_use_coding,
            CAST(diagnosis_rank AS VARCHAR) as diagnosis_rank_str
        FROM fhir_prd_db.encounter_diagnosis
    )
    GROUP BY encounter_id
),
encounter_appointments_agg AS (
    SELECT
        encounter_id,
        LISTAGG(appointment_reference, '; ') WITHIN GROUP (ORDER BY appointment_reference) as appointment_reference
    FROM (
        SELECT DISTINCT encounter_id, appointment_reference
        FROM fhir_prd_db.encounter_appointment
    )
    GROUP BY encounter_id
),
encounter_service_type_coding_agg AS (
    SELECT
        encounter_id,
        LISTAGG(service_type_coding_display, '; ') WITHIN GROUP (ORDER BY service_type_coding_display) as service_type_coding_display_detail
    FROM (
        SELECT DISTINCT encounter_id, service_type_coding_display
        FROM fhir_prd_db.encounter_service_type_coding
    )
    GROUP BY encounter_id
),
encounter_locations_agg AS (
    SELECT
        encounter_id,
        LISTAGG(location_location_reference, '; ') WITHIN GROUP (ORDER BY location_location_reference) as location_location_reference,
        LISTAGG(location_status, '; ') WITHIN GROUP (ORDER BY location_status) as location_status
    FROM (
        SELECT DISTINCT encounter_id, location_location_reference, location_status
        FROM fhir_prd_db.encounter_location
    )
    GROUP BY encounter_id
)
SELECT
    e.id as encounter_fhir_id,
    TRY(CAST(SUBSTR(e.period_start, 1, 10) AS DATE)) as encounter_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(e.period_start, 1, 10) AS DATE)))) as age_at_encounter_days,
    e.status,
    e.class_code,
    e.class_display,
    e.service_type_text,
    e.priority_text,
    TRY(CAST(e.period_start AS TIMESTAMP(3))) as period_start,
    TRY(CAST(e.period_end AS TIMESTAMP(3))) as period_end,
    e.length_value,
    e.length_unit,
    e.service_provider_display,
    e.part_of_reference,
    e.subject_reference as patient_fhir_id,

    -- Aggregated subtables (matching Python CSV output)
    et.type_coding,
    et.type_text,
    er.reason_code_coding,
    er.reason_code_text,
    ed.diagnosis_condition_reference,
    ed.diagnosis_condition_display,
    ed.diagnosis_use_coding,
    ed.diagnosis_rank,
    ea.appointment_reference,
    estc.service_type_coding_display_detail,
    el.location_location_reference,
    el.location_status,

    -- Patient type classification (matches Python logic)
    CASE
        WHEN LOWER(e.class_display) LIKE '%inpatient%' OR e.class_code = 'IMP' THEN 'Inpatient'
        WHEN LOWER(e.class_display) LIKE '%outpatient%' OR e.class_code = 'AMB'
             OR LOWER(e.class_display) LIKE '%appointment%' THEN 'Outpatient'
        ELSE 'Unknown'
    END as patient_type

FROM fhir_prd_db.encounter e
LEFT JOIN encounter_types_agg et ON e.id = et.encounter_id
LEFT JOIN encounter_reasons_agg er ON e.id = er.encounter_id
LEFT JOIN encounter_diagnoses_agg ed ON e.id = ed.encounter_id
LEFT JOIN encounter_appointments_agg ea ON e.id = ea.encounter_id
LEFT JOIN encounter_service_type_coding_agg estc ON e.id = estc.encounter_id
LEFT JOIN encounter_locations_agg el ON e.id = el.encounter_id
LEFT JOIN fhir_prd_db.patient_access pa ON e.subject_reference = pa.id
WHERE e.subject_reference IS NOT NULL
ORDER BY e.subject_reference, e.period_start;

-- ================================================================================
-- VIEW: v_radiation_care_plan_hierarchy
-- DATETIME STANDARDIZATION: 2 columns converted from VARCHAR
-- CHANGES:
--   - cp_period_end: VARCHAR → TIMESTAMP(3)
--   - cp_period_start: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_care_plan_hierarchy AS
SELECT
    cp.subject_reference as patient_fhir_id,
    cppo.care_plan_id,
    cppo.part_of_reference as cppo_part_of_reference,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.title as cp_title,
    TRY(CAST(cp.period_start AS TIMESTAMP(3))) as cp_period_start,
    TRY(CAST(cp.period_end AS TIMESTAMP(3))) as cp_period_end
FROM fhir_prd_db.care_plan_part_of cppo
INNER JOIN fhir_prd_db.care_plan cp ON cppo.care_plan_id = cp.id
WHERE cp.subject_reference IS NOT NULL
  AND (LOWER(cp.title) LIKE '%radiation%'
       OR LOWER(cppo.part_of_reference) LIKE '%radiation%')
ORDER BY cp.period_start;

-- ================================================================================
-- VIEW: v_audiology_assessments
-- DATETIME STANDARDIZATION: 10 VARCHAR datetime columns → TIMESTAMP(3)
-- CHANGES: Wrapped full_datetime columns in all CTEs with TRY(CAST(... AS TIMESTAMP(3)))
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_audiology_assessments AS
WITH
  audiogram_thresholds AS (
   SELECT o.id observation_fhir_id, SUBSTRING(o.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) assessment_date, (CASE WHEN (LOWER(o.code_text) LIKE '%left ear%') THEN 'left' WHEN (LOWER(o.code_text) LIKE '%right ear%') THEN 'right' END) ear_side, (CASE WHEN (LOWER(o.code_text) LIKE '%1000%hz%') THEN 1000 WHEN (LOWER(o.code_text) LIKE '%2000%hz%') THEN 2000 WHEN (LOWER(o.code_text) LIKE '%4000%hz%') THEN 4000 WHEN (LOWER(o.code_text) LIKE '%6000%hz%') THEN 6000 WHEN (LOWER(o.code_text) LIKE '%8000%hz%') THEN 8000 WHEN (LOWER(o.code_text) LIKE '%500%hz%') THEN 500 WHEN (LOWER(o.code_text) LIKE '%250%hz%') THEN 250 END) frequency_hz, o.value_quantity_value threshold_db, o.value_quantity_unit threshold_unit, o.code_text test_name, 'audiogram_threshold' assessment_category, 'observation' source_table, o.status observation_status, TRY(CAST(o.effective_date_time AS TIMESTAMP(3))) full_datetime FROM fhir_prd_db.observation o WHERE ((LOWER(o.code_text) LIKE '%ear%hz%') AND ((LOWER(o.code_text) LIKE '%1000%') OR (LOWER(o.code_text) LIKE '%2000%') OR (LOWER(o.code_text) LIKE '%4000%') OR (LOWER(o.code_text) LIKE '%6000%') OR (LOWER(o.code_text) LIKE '%8000%') OR (LOWER(o.code_text) LIKE '%500%') OR (LOWER(o.code_text) LIKE '%250%')))
), hearing_aid_status AS (
   SELECT o.id observation_fhir_id, SUBSTRING(o.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) assessment_date, o.code_text assessment_name, (CASE WHEN (LOWER(o.code_text) LIKE '%hearing aid ear%') THEN 'hearing_aid_laterality' WHEN (LOWER(o.code_text) LIKE '%hearing aid%') THEN 'hearing_aid_required' END) assessment_category, 'observation' source_table, oc.component_value_string laterality_value, (CASE WHEN (LOWER(oc.component_value_string) LIKE '%both%ear%') THEN 'Bilateral' WHEN (LOWER(oc.component_value_string) LIKE '%right%ear%') THEN 'Right' WHEN (LOWER(oc.component_value_string) LIKE '%left%ear%') THEN 'Left' WHEN ((LOWER(o.code_text) LIKE '%hearing aid%') AND (oc.component_code_text IS NOT NULL)) THEN 'Yes' END) standardized_value, o.status observation_status, TRY(CAST(o.effective_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.observation o LEFT JOIN fhir_prd_db.observation_component oc ON (o.id = oc.observation_id)) WHERE (LOWER(o.code_text) LIKE '%hearing aid%')
), hearing_loss_observations AS (
   SELECT o.id observation_fhir_id, SUBSTRING(o.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) assessment_date, o.code_text assessment_name, (CASE WHEN (LOWER(o.code_text) LIKE '%laterality%') THEN 'hearing_loss_laterality' WHEN (LOWER(o.code_text) LIKE '%hearing loss type%') THEN 'hearing_loss_type' WHEN (LOWER(o.code_text) LIKE '%sensorineural%') THEN 'hearing_loss_type' WHEN (LOWER(o.code_text) LIKE '%conductive%') THEN 'hearing_loss_type' WHEN (LOWER(o.code_text) LIKE '%hearing loss%') THEN 'hearing_loss_symptom' END) assessment_category, 'observation' source_table, (CASE WHEN (LOWER(o.code_text) LIKE '%sensorineural%') THEN 'Sensorineural' WHEN (LOWER(o.code_text) LIKE '%conductive%') THEN 'Conductive' WHEN (LOWER(o.code_text) LIKE '%mixed%') THEN 'Mixed' END) hearing_loss_type, (CASE WHEN (LOWER(oc.component_value_string) LIKE '%both%ear%') THEN 'Bilateral' WHEN (LOWER(oc.component_value_string) LIKE '%right%ear%') THEN 'Right' WHEN (LOWER(oc.component_value_string) LIKE '%left%ear%') THEN 'Left' END) laterality, oc.component_value_string raw_value, o.status observation_status, TRY(CAST(o.effective_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.observation o LEFT JOIN fhir_prd_db.observation_component oc ON (o.id = oc.observation_id)) WHERE (((LOWER(o.code_text) LIKE '%hearing loss%') OR (LOWER(o.code_text) LIKE '%sensorineural%') OR (LOWER(o.code_text) LIKE '%conductive%') OR (LOWER(o.code_text) LIKE '%hard of hearing%')) AND (NOT (LOWER(o.code_text) LIKE '%ear%hz%')))
), hearing_tests_other AS (
   SELECT o.id observation_fhir_id, SUBSTRING(o.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) assessment_date, o.code_text assessment_name, (CASE WHEN (LOWER(o.code_text) LIKE '%hearing reception threshold%') THEN 'hearing_reception_threshold' WHEN (LOWER(o.code_text) LIKE '%hearing screen%result%') THEN 'hearing_screen_result' WHEN (LOWER(o.code_text) LIKE '%hearing%intact%') THEN 'hearing_exam_normal' WHEN (LOWER(o.code_text) LIKE '%vision and hearing%') THEN 'hearing_status_general' END) assessment_category, 'observation' source_table, o.value_quantity_value numeric_value, o.value_quantity_unit value_unit, oc.component_value_string text_value, o.status observation_status, TRY(CAST(o.effective_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.observation o LEFT JOIN fhir_prd_db.observation_component oc ON (o.id = oc.observation_id)) WHERE (((LOWER(o.code_text) LIKE '%hearing reception threshold%') OR (LOWER(o.code_text) LIKE '%hearing screen%') OR (LOWER(o.code_text) LIKE '%hearing%intact%') OR ((LOWER(o.code_text) LIKE '%vision and hearing%') AND (LOWER(o.code_text) LIKE '%hearing%'))) AND (NOT (LOWER(o.code_text) LIKE '%ear%hz%')))
), hearing_loss_diagnoses AS (
   SELECT c.id condition_fhir_id, SUBSTRING(c.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(c.onset_date_time, 1, 10) AS DATE)) diagnosis_date, c.code_text diagnosis_name, (CASE WHEN (LOWER(c.code_text) LIKE '%ototoxic%') THEN 'ototoxic_hearing_loss' WHEN (LOWER(c.code_text) LIKE '%ototoxicity monitoring%') THEN 'ototoxicity_monitoring' WHEN (LOWER(c.code_text) LIKE '%sensorineural%') THEN 'sensorineural_hearing_loss' WHEN (LOWER(c.code_text) LIKE '%conductive%') THEN 'conductive_hearing_loss' WHEN (LOWER(c.code_text) LIKE '%mixed%') THEN 'mixed_hearing_loss' WHEN (LOWER(c.code_text) LIKE '%deaf%') THEN 'deafness' ELSE 'hearing_loss_unspecified' END) diagnosis_category, 'condition' source_table, (CASE WHEN (LOWER(c.code_text) LIKE '%sensorineural%') THEN 'Sensorineural' WHEN (LOWER(c.code_text) LIKE '%conductive%') THEN 'Conductive' WHEN (LOWER(c.code_text) LIKE '%mixed%') THEN 'Mixed' WHEN (LOWER(c.code_text) LIKE '%ototoxic%') THEN 'Ototoxic (Sensorineural)' END) hearing_loss_type, (CASE WHEN ((LOWER(c.code_text) LIKE '%bilateral%') OR (LOWER(c.code_text) LIKE '%both ears%')) THEN 'Bilateral' WHEN ((LOWER(c.code_text) LIKE '%unilateral%') AND (LOWER(c.code_text) LIKE '%left%')) THEN 'Left' WHEN ((LOWER(c.code_text) LIKE '%unilateral%') AND (LOWER(c.code_text) LIKE '%right%')) THEN 'Right' WHEN (LOWER(c.code_text) LIKE '%left ear%') THEN 'Left' WHEN (LOWER(c.code_text) LIKE '%right ear%') THEN 'Right' WHEN (LOWER(c.code_text) LIKE '%asymmetrical%') THEN 'Bilateral (asymmetric)' END) laterality, (CASE WHEN (LOWER(c.code_text) LIKE '%ototoxic%') THEN true ELSE false END) is_ototoxic, ccs.clinical_status_coding_code condition_status, TRY(CAST(c.onset_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.condition c LEFT JOIN fhir_prd_db.condition_clinical_status_coding ccs ON (c.id = ccs.condition_id)) WHERE ((LOWER(c.code_text) LIKE '%hearing loss%') OR (LOWER(c.code_text) LIKE '%deaf%') OR (LOWER(c.code_text) LIKE '%ototoxic%') OR (LOWER(c.code_text) LIKE '%ototoxicity%'))
), audiology_procedures AS (
   SELECT p.id procedure_fhir_id, SUBSTRING(p.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) assessment_date, p.code_text procedure_name, (CASE WHEN (LOWER(p.code_text) LIKE '%audiometric screening%') THEN 'audiometric_screening' WHEN (LOWER(p.code_text) LIKE '%pure tone audiometry%') THEN 'pure_tone_audiometry' WHEN ((LOWER(p.code_text) LIKE '%speech%audiometry%') OR (LOWER(p.code_text) LIKE '%speech threshold%')) THEN 'speech_audiometry' WHEN (LOWER(p.code_text) LIKE '%air%bone%') THEN 'air_bone_audiometry' WHEN (LOWER(p.code_text) LIKE '%comprehensive hearing%') THEN 'comprehensive_hearing_test' WHEN (LOWER(p.code_text) LIKE '%hearing aid check%') THEN 'hearing_aid_check' WHEN ((LOWER(p.code_text) LIKE '%abr%') OR (LOWER(p.code_text) LIKE '%auditory brainstem%')) THEN 'abr_test' WHEN (LOWER(p.code_text) LIKE '%tympanometry%') THEN 'tympanometry' ELSE 'other_audiology_procedure' END) procedure_category, 'procedure' source_table, p.status procedure_status, pc.code_coding_code cpt_code, pc.code_coding_display cpt_description, TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.procedure p LEFT JOIN fhir_prd_db.procedure_code_coding pc ON (p.id = pc.procedure_id)) WHERE ((LOWER(p.code_text) LIKE '%audiolog%') OR (LOWER(p.code_text) LIKE '%audiometr%') OR (LOWER(p.code_text) LIKE '%hearing%') OR (LOWER(p.code_text) LIKE '%abr%'))
), audiology_orders AS (
   SELECT sr.id service_request_fhir_id, SUBSTRING(sr.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(sr.authored_on, 1, 10) AS DATE)) order_date, sr.code_text order_name, (CASE WHEN (LOWER(sr.code_text) LIKE '%audiolog%') THEN 'audiology_order' WHEN (LOWER(sr.code_text) LIKE '%audiometr%') THEN 'audiometry_order' WHEN (LOWER(sr.code_text) LIKE '%hearing%') THEN 'hearing_test_order' END) order_category, 'service_request' source_table, sr.status order_status, sr.intent order_intent, TRY(CAST(sr.authored_on AS TIMESTAMP(3))) order_datetime FROM fhir_prd_db.service_request sr WHERE ((LOWER(sr.code_text) LIKE '%audiolog%') OR (LOWER(sr.code_text) LIKE '%audiometr%') OR (LOWER(sr.code_text) LIKE '%hearing%'))
), audiology_reports AS (
   SELECT dr.id diagnostic_report_fhir_id, SUBSTRING(dr.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(dr.effective_date_time, 1, 10) AS DATE)) report_date, dr.code_text report_name, (CASE WHEN (LOWER(dr.code_text) LIKE '%audiolog%') THEN 'audiology_report' WHEN (LOWER(dr.code_text) LIKE '%audiometr%') THEN 'audiometry_report' WHEN (LOWER(dr.code_text) LIKE '%hearing%') THEN 'hearing_test_report' END) report_category, 'diagnostic_report' source_table, dr.status report_status, TRY(CAST(dr.effective_date_time AS TIMESTAMP(3))) report_datetime FROM fhir_prd_db.diagnostic_report dr WHERE ((LOWER(dr.code_text) LIKE '%audiolog%') OR (LOWER(dr.code_text) LIKE '%audiometr%') OR (LOWER(dr.code_text) LIKE '%hearing%'))
), audiology_documents AS (
   SELECT dref.id document_reference_fhir_id, SUBSTRING(dref.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(dref.date, 1, 10) AS DATE)) document_date, dref.description document_description, dref.type_text document_type, (CASE WHEN (LOWER(dref.type_text) LIKE '%audiologic assessment%') THEN 'audiologic_assessment_document' WHEN (LOWER(dref.description) LIKE '%audiolog%evaluation%') THEN 'audiology_evaluation_document' WHEN (LOWER(dref.description) LIKE '%audiometr%') THEN 'audiometry_document' WHEN (LOWER(dref.description) LIKE '%hearing%') THEN 'hearing_test_document' ELSE 'audiology_other_document' END) document_category, 'document_reference' source_table, dref.status document_status, TRY(CAST(dref.date AS TIMESTAMP(3))) document_datetime, dc.content_attachment_url file_url, dc.content_attachment_content_type file_type FROM (fhir_prd_db.document_reference dref LEFT JOIN fhir_prd_db.document_reference_content dc ON (dref.id = dc.document_reference_id)) WHERE ((LOWER(dref.description) LIKE '%audiolog%') OR (LOWER(dref.type_text) LIKE '%audiolog%') OR (LOWER(dref.description) LIKE '%hearing%') OR (LOWER(dref.type_text) LIKE '%hearing%'))
)
SELECT 'audiogram' data_type, observation_fhir_id record_fhir_id, patient_fhir_id, assessment_date, test_name assessment_description, assessment_category, source_table, observation_status record_status, ear_side, frequency_hz, threshold_db, threshold_unit, null hearing_loss_type, null laterality, null is_ototoxic, null cpt_code, null cpt_description, null order_intent, null file_url, null file_type, full_datetime FROM audiogram_thresholds
UNION ALL SELECT 'hearing_aid' data_type, observation_fhir_id record_fhir_id, patient_fhir_id, assessment_date, assessment_name assessment_description, assessment_category, source_table, observation_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, null hearing_loss_type, standardized_value laterality, null is_ototoxic, null cpt_code, null cpt_description, null order_intent, null file_url, null file_type, full_datetime FROM hearing_aid_status
UNION ALL SELECT 'hearing_loss_observation' data_type, observation_fhir_id record_fhir_id, patient_fhir_id, assessment_date, assessment_name assessment_description, assessment_category, source_table, observation_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, hearing_loss_type, laterality, null is_ototoxic, null cpt_code, null cpt_description, null order_intent, null file_url, null file_type, full_datetime FROM hearing_loss_observations
UNION ALL SELECT 'hearing_test' data_type, observation_fhir_id record_fhir_id, patient_fhir_id, assessment_date, assessment_name assessment_description, assessment_category, source_table, observation_status record_status, null ear_side, null frequency_hz, CAST(numeric_value AS VARCHAR) threshold_db, value_unit threshold_unit, null hearing_loss_type, null laterality, null is_ototoxic, null cpt_code, null cpt_description, null order_intent, null file_url, null file_type, full_datetime FROM hearing_tests_other
UNION ALL SELECT 'diagnosis' data_type, condition_fhir_id record_fhir_id, patient_fhir_id, diagnosis_date assessment_date, diagnosis_name assessment_description, diagnosis_category assessment_category, source_table, condition_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, hearing_loss_type, laterality, is_ototoxic, null cpt_code, null cpt_description, null order_intent, null file_url, null file_type, full_datetime FROM hearing_loss_diagnoses
UNION ALL SELECT 'procedure' data_type, procedure_fhir_id record_fhir_id, patient_fhir_id, assessment_date, procedure_name assessment_description, procedure_category assessment_category, source_table, procedure_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, null hearing_loss_type, null laterality, null is_ototoxic, cpt_code, cpt_description, null order_intent, null file_url, null file_type, full_datetime FROM audiology_procedures
UNION ALL SELECT 'order' data_type, service_request_fhir_id record_fhir_id, patient_fhir_id, order_date assessment_date, order_name assessment_description, order_category assessment_category, source_table, order_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, null hearing_loss_type, null laterality, null is_ototoxic, null cpt_code, null cpt_description, order_intent, null file_url, null file_type, order_datetime full_datetime FROM audiology_orders
UNION ALL SELECT 'report' data_type, diagnostic_report_fhir_id record_fhir_id, patient_fhir_id, report_date assessment_date, report_name assessment_description, report_category assessment_category, source_table, report_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, null hearing_loss_type, null laterality, null is_ototoxic, null cpt_code, null cpt_description, null order_intent, null file_url, null file_type, report_datetime full_datetime FROM audiology_reports
UNION ALL SELECT 'document' data_type, document_reference_fhir_id record_fhir_id, patient_fhir_id, document_date assessment_date, document_description assessment_description, document_category assessment_category, source_table, document_status record_status, null ear_side, null frequency_hz, null threshold_db, null threshold_unit, null hearing_loss_type, null laterality, null is_ototoxic, null cpt_code, null cpt_description, null order_intent, file_url, file_type, document_datetime full_datetime FROM audiology_documents;

-- ================================================================================
-- VIEW: v_ophthalmology_assessments
-- DATETIME STANDARDIZATION: 9 VARCHAR datetime columns → TIMESTAMP(3)
-- CHANGES: Wrapped full_datetime columns in all CTEs with TRY(CAST(... AS TIMESTAMP(3)))
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_ophthalmology_assessments AS
WITH visual_acuity_obs AS (SELECT o.id observation_fhir_id, SUBSTRING(o.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) assessment_date, o.code_text assessment_name, 'visual_acuity' assessment_category, 'observation' source_table, o.value_quantity_value numeric_value, o.value_quantity_unit value_unit, o.value_string text_value, oc.component_code_text component_name, oc.component_value_quantity_value component_numeric_value, oc.component_value_quantity_unit component_unit, o.status observation_status, TRY(CAST(o.effective_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.observation o LEFT JOIN fhir_prd_db.observation_component oc ON (o.id = oc.observation_id)) WHERE ((LOWER(o.code_text) LIKE '%visual%acuity%') OR (LOWER(o.code_text) LIKE '%snellen%') OR (LOWER(o.code_text) LIKE '%logmar%') OR (LOWER(o.code_text) LIKE '%etdrs%') OR (LOWER(o.code_text) LIKE '%hotv%') OR (LOWER(o.code_text) LIKE '%lea%') OR (LOWER(o.code_text) LIKE '%vision%screening%') OR (LOWER(o.code_text) LIKE '%bcva%'))), fundus_optic_disc_obs AS (SELECT o.id observation_fhir_id, SUBSTRING(o.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) assessment_date, o.code_text assessment_name, (CASE WHEN (LOWER(o.code_text) LIKE '%papilledema%') THEN 'optic_disc_papilledema' WHEN ((LOWER(o.code_text) LIKE '%optic%disc%') OR (LOWER(o.code_text) LIKE '%fundus%disc%')) THEN 'optic_disc_exam' WHEN (LOWER(o.code_text) LIKE '%fundus%macula%') THEN 'fundus_macula' WHEN (LOWER(o.code_text) LIKE '%fundus%vessel%') THEN 'fundus_vessels' WHEN (LOWER(o.code_text) LIKE '%fundus%vitreous%') THEN 'fundus_vitreous' WHEN (LOWER(o.code_text) LIKE '%fundus%periphery%') THEN 'fundus_periphery' ELSE 'fundus_other' END) assessment_category, 'observation' source_table, o.value_quantity_value numeric_value, o.value_quantity_unit value_unit, o.value_string text_value, oc.component_code_text component_name, oc.component_value_quantity_value component_numeric_value, oc.component_value_quantity_unit component_unit, o.status observation_status, TRY(CAST(o.effective_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.observation o LEFT JOIN fhir_prd_db.observation_component oc ON (o.id = oc.observation_id)) WHERE (((LOWER(o.code_text) LIKE '%fundus%') OR (LOWER(o.code_text) LIKE '%optic%disc%') OR (LOWER(o.code_text) LIKE '%papilledema%') OR (LOWER(o.code_text) LIKE '%optic%pallor%') OR (LOWER(o.code_text) LIKE '%optic%atrophy%') OR (LOWER(o.code_text) LIKE '%cup%disc%')) AND (NOT (LOWER(o.code_text) LIKE '%visual%acuity%')))), visual_field_procedures AS (SELECT p.id procedure_fhir_id, SUBSTRING(p.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) assessment_date, p.code_text assessment_name, 'visual_field' assessment_category, 'procedure' source_table, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, p.status procedure_status, pc.code_coding_code cpt_code, pc.code_coding_display cpt_description, TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.procedure p LEFT JOIN fhir_prd_db.procedure_code_coding pc ON (p.id = pc.procedure_id)) WHERE ((LOWER(p.code_text) LIKE '%visual%field%') OR (LOWER(p.code_text) LIKE '%perimetry%') OR (LOWER(p.code_text) LIKE '%goldmann%') OR (LOWER(p.code_text) LIKE '%humphrey%') OR (pc.code_coding_code IN ('92081', '92082', '92083')))), oct_procedures AS (SELECT p.id procedure_fhir_id, SUBSTRING(p.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) assessment_date, p.code_text assessment_name, (CASE WHEN (LOWER(p.code_text) LIKE '%optic%nerve%') THEN 'oct_optic_nerve' WHEN (LOWER(p.code_text) LIKE '%retina%') THEN 'oct_retina' WHEN (LOWER(p.code_text) LIKE '%macula%') THEN 'oct_macula' ELSE 'oct_unspecified' END) assessment_category, 'procedure' source_table, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, p.status procedure_status, pc.code_coding_code cpt_code, pc.code_coding_display cpt_description, TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.procedure p LEFT JOIN fhir_prd_db.procedure_code_coding pc ON (p.id = pc.procedure_id)) WHERE ((LOWER(p.code_text) LIKE '%oct%') OR (LOWER(p.code_text) LIKE '%optical%coherence%') OR (LOWER(p.code_text) LIKE '%rnfl%') OR (LOWER(p.code_text) LIKE '%ganglion%cell%') OR (pc.code_coding_code IN ('92133', '92134', '92133.999', '92134.999')))), fundus_photo_procedures AS (SELECT p.id procedure_fhir_id, SUBSTRING(p.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) assessment_date, p.code_text assessment_name, 'fundus_photography' assessment_category, 'procedure' source_table, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, p.status procedure_status, pc.code_coding_code cpt_code, pc.code_coding_display cpt_description, TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.procedure p LEFT JOIN fhir_prd_db.procedure_code_coding pc ON (p.id = pc.procedure_id)) WHERE ((LOWER(p.code_text) LIKE '%fundus%photo%') OR (LOWER(p.code_text) LIKE '%fundus%imaging%') OR (LOWER(p.code_text) LIKE '%retinal%photo%') OR (pc.code_coding_code IN ('92250', '92225', '92226', '92227', '92228')))), ophthal_exam_procedures AS (SELECT p.id procedure_fhir_id, SUBSTRING(p.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) assessment_date, p.code_text assessment_name, 'ophthalmology_exam' assessment_category, 'procedure' source_table, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, p.status procedure_status, pc.code_coding_code cpt_code, pc.code_coding_display cpt_description, TRY(CAST(p.performed_date_time AS TIMESTAMP(3))) full_datetime FROM (fhir_prd_db.procedure p LEFT JOIN fhir_prd_db.procedure_code_coding pc ON (p.id = pc.procedure_id)) WHERE ((LOWER(p.code_text) LIKE '%ophthal%exam%') OR (LOWER(p.code_text) LIKE '%eye%exam%anes%') OR (LOWER(p.code_text) LIKE '%optic%nerve%decompression%') OR (LOWER(p.code_text) LIKE '%optic%glioma%') OR (pc.code_coding_code IN ('92002', '92004', '92012', '92014', '92018')))), ophthalmology_orders AS (SELECT sr.id service_request_fhir_id, SUBSTRING(sr.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(sr.authored_on, 1, 10) AS DATE)) order_date, sr.code_text order_name, (CASE WHEN (LOWER(sr.code_text) LIKE '%visual%field%') THEN 'visual_field_order' WHEN (LOWER(sr.code_text) LIKE '%oct%optic%') THEN 'oct_optic_nerve_order' WHEN (LOWER(sr.code_text) LIKE '%oct%retina%') THEN 'oct_retina_order' WHEN (LOWER(sr.code_text) LIKE '%ophthal%') THEN 'ophthalmology_order' ELSE 'other_eye_order' END) order_category, 'service_request' source_table, sr.status order_status, sr.intent order_intent, TRY(CAST(sr.authored_on AS TIMESTAMP(3))) order_datetime FROM fhir_prd_db.service_request sr WHERE (((LOWER(sr.code_text) LIKE '%ophthal%') OR (LOWER(sr.code_text) LIKE '%visual%field%') OR (LOWER(sr.code_text) LIKE '%oct%') OR (LOWER(sr.code_text) LIKE '%optic%') OR (LOWER(sr.code_text) LIKE '%eye%exam%')) AND (NOT ((LOWER(sr.code_text) LIKE '%poct%') OR (LOWER(sr.code_text) LIKE '%glucose%'))))), ophthalmology_reports AS (SELECT dr.id diagnostic_report_fhir_id, SUBSTRING(dr.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(dr.effective_date_time, 1, 10) AS DATE)) report_date, dr.code_text report_name, (CASE WHEN (LOWER(dr.code_text) LIKE '%visual%field%') THEN 'visual_field_report' WHEN (LOWER(dr.code_text) LIKE '%oct%optic%') THEN 'oct_optic_nerve_report' WHEN (LOWER(dr.code_text) LIKE '%oct%retina%') THEN 'oct_retina_report' WHEN (LOWER(dr.code_text) LIKE '%fundus%') THEN 'fundus_report' WHEN (LOWER(dr.code_text) LIKE '%vision%screening%') THEN 'vision_screening_report' ELSE 'other_eye_report' END) report_category, 'diagnostic_report' source_table, dr.status report_status, TRY(CAST(dr.effective_date_time AS TIMESTAMP(3))) report_datetime FROM fhir_prd_db.diagnostic_report dr WHERE (((LOWER(dr.code_text) LIKE '%ophthal%') OR (LOWER(dr.code_text) LIKE '%visual%field%') OR (LOWER(dr.code_text) LIKE '%oct%') OR (LOWER(dr.code_text) LIKE '%fundus%') OR (LOWER(dr.code_text) LIKE '%eye%') OR (LOWER(dr.code_text) LIKE '%vision%screening%')) AND (NOT ((LOWER(dr.code_text) LIKE '%poct%') OR (LOWER(dr.code_text) LIKE '%glucose%'))))), ophthalmology_documents AS (SELECT dref.id document_reference_fhir_id, SUBSTRING(dref.subject_reference, 9) patient_fhir_id, TRY(CAST(SUBSTR(dref.date, 1, 10) AS DATE)) document_date, dref.description document_description, dref.type_text document_type, (CASE WHEN (LOWER(dref.description) LIKE '%oct%') THEN 'oct_document' WHEN ((LOWER(dref.description) LIKE '%visual%field%') OR (LOWER(dref.description) LIKE '%goldman%')) THEN 'visual_field_document' WHEN (LOWER(dref.description) LIKE '%fundus%') THEN 'fundus_document' WHEN (LOWER(dref.description) LIKE '%ophthal%consult%') THEN 'ophthalmology_consult' WHEN (LOWER(dref.type_text) LIKE '%ophthal%') THEN 'ophthalmology_other' ELSE 'eye_related_document' END) document_category, 'document_reference' source_table, dref.status document_status, TRY(CAST(dref.date AS TIMESTAMP(3))) document_datetime, dc.content_attachment_url file_url, dc.content_attachment_content_type file_type FROM (fhir_prd_db.document_reference dref LEFT JOIN fhir_prd_db.document_reference_content dc ON (dref.id = dc.document_reference_id)) WHERE (((LOWER(dref.description) LIKE '%ophthal%') OR (LOWER(dref.description) LIKE '%visual%field%') OR (LOWER(dref.description) LIKE '%oct%') OR (LOWER(dref.description) LIKE '%fundus%') OR (LOWER(dref.description) LIKE '%eye%exam%') OR (LOWER(dref.type_text) LIKE '%ophthal%') OR (LOWER(dref.description) LIKE '%goldman%')) AND (NOT (LOWER(dref.description) LIKE '%octreotide%')))), all_assessments AS (SELECT observation_fhir_id record_fhir_id, patient_fhir_id, assessment_date, assessment_name assessment_description, assessment_category, source_table, observation_status record_status, null cpt_code, null cpt_description, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, null order_intent, null file_url, null file_type, full_datetime FROM visual_acuity_obs UNION ALL SELECT observation_fhir_id, patient_fhir_id, assessment_date, assessment_name, assessment_category, source_table, observation_status, null, null, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, null, null, null, full_datetime FROM fundus_optic_disc_obs UNION ALL SELECT procedure_fhir_id, patient_fhir_id, assessment_date, assessment_name, assessment_category, source_table, procedure_status, cpt_code, cpt_description, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, null, null, null, full_datetime FROM visual_field_procedures UNION ALL SELECT procedure_fhir_id, patient_fhir_id, assessment_date, assessment_name, assessment_category, source_table, procedure_status, cpt_code, cpt_description, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, null, null, null, full_datetime FROM oct_procedures UNION ALL SELECT procedure_fhir_id, patient_fhir_id, assessment_date, assessment_name, assessment_category, source_table, procedure_status, cpt_code, cpt_description, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, null, null, null, full_datetime FROM fundus_photo_procedures UNION ALL SELECT procedure_fhir_id, patient_fhir_id, assessment_date, assessment_name, assessment_category, source_table, procedure_status, cpt_code, cpt_description, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, null, null, null, full_datetime FROM ophthal_exam_procedures), all_orders AS (SELECT service_request_fhir_id record_fhir_id, patient_fhir_id, order_date assessment_date, order_name assessment_description, order_category assessment_category, source_table, order_status record_status, null cpt_code, null cpt_description, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, order_intent, null file_url, null file_type, order_datetime full_datetime FROM ophthalmology_orders), all_reports AS (SELECT diagnostic_report_fhir_id record_fhir_id, patient_fhir_id, report_date assessment_date, report_name assessment_description, report_category assessment_category, source_table, report_status record_status, null cpt_code, null cpt_description, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, null order_intent, null file_url, null file_type, report_datetime full_datetime FROM ophthalmology_reports), all_documents AS (SELECT document_reference_fhir_id record_fhir_id, patient_fhir_id, document_date assessment_date, document_description assessment_description, document_category assessment_category, source_table, document_status record_status, null cpt_code, null cpt_description, null numeric_value, null value_unit, null text_value, null component_name, null component_numeric_value, null component_unit, null order_intent, file_url, file_type, document_datetime full_datetime FROM ophthalmology_documents)
SELECT record_fhir_id, patient_fhir_id, assessment_date, assessment_description, assessment_category, source_table, record_status, cpt_code, cpt_description, numeric_value, value_unit, text_value, component_name, component_numeric_value, component_unit, order_intent, file_url, file_type, full_datetime FROM (SELECT * FROM all_assessments UNION ALL SELECT * FROM all_orders UNION ALL SELECT * FROM all_reports UNION ALL SELECT * FROM all_documents);

-- ================================================================================
-- VIEW: v_patient_demographics
-- DATETIME STANDARDIZATION: 1 columns converted from VARCHAR
-- CHANGES:
--   - pd_birth_date: VARCHAR → TIMESTAMP(3)
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT
    pa.id as patient_fhir_id,
    pa.gender as pd_gender,
    pa.race as pd_race,
    pa.ethnicity as pd_ethnicity,
    TRY(CAST(CASE
        WHEN LENGTH(pa.birth_date) = 10 THEN pa.birth_date || 'T00:00:00Z'
        ELSE pa.birth_date
    END AS TIMESTAMP(3))) as pd_birth_date,
    DATE_DIFF('year', DATE(pa.birth_date), CURRENT_DATE) as pd_age_years
FROM fhir_prd_db.patient_access pa
WHERE pa.id IS NOT NULL;

-- ================================================================================
-- VIEW: v_diagnoses
-- DATETIME STANDARDIZATION: 0 columns converted from VARCHAR
-- PRESERVED: All JOINs, WHERE clauses, aggregations, and business logic
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_diagnoses AS
SELECT
    patient_fhir_id,
    pld_condition_id as condition_id,
    pld_diagnosis_name as diagnosis_name,
    pld_clinical_status as clinical_status_text,
    CAST(pld_onset_date AS TIMESTAMP) as onset_date_time,
    age_at_onset_days,
    CAST(pld_abatement_date AS TIMESTAMP) as abatement_date_time,
    CAST(pld_recorded_date AS TIMESTAMP) as recorded_date,
    age_at_recorded_days,
    pld_icd10_code as icd10_code,
    pld_icd10_display as icd10_display,
    TRY_CAST(pld_snomed_code AS BIGINT) as snomed_code,
    pld_snomed_display as snomed_display
FROM fhir_prd_db.v_problem_list_diagnoses;

-- Note: v_hydrocephalus_diagnosis is a subset of v_problem_list_diagnoses
-- We only pull from problem_list_diagnoses to avoid duplicates

-- ================================================================================
-- VIEW: v_radiation_summary - REDESIGNED AS DATA AVAILABILITY SUMMARY
-- DATETIME STANDARDIZATION: Multiple TIMESTAMP(3) columns (dates from each source)
-- REDESIGN DATE: 2025-10-21
-- REDESIGN REASON:
--   - Original view was empty (0 records) because it required structured ELECT data
--   - Only 91/684 patients have structured data, 593 patients (87%) were excluded
--   - New approach: Inventory what data exists across ALL sources instead of
--     trying to aggregate non-existent structured data
-- DATA SOURCES TRACKED:
--   1. Structured ELECT intake forms (observation table) - 91 patients
--   2. Radiation documents (treatment summaries, consults) - 684 patients
--   3. Care plans (radiation treatment plans) - 568 patients
--   4. Appointments (radiation oncology appointments)
--   5. Service requests (radiation treatment orders)
-- OUTPUT: One row per patient with data availability flags + counts + quality scores
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_summary AS
WITH

-- ============================================================================
-- CTE 1: Patients with ELECT structured data (observation-based)
-- ============================================================================
patients_with_structured_data AS (
    SELECT DISTINCT
        patient_fhir_id,
        COUNT(DISTINCT course_id) as num_structured_courses,
        MIN(obs_start_date) as earliest_structured_start,
        MAX(obs_stop_date) as latest_structured_end,
        SUM(CASE WHEN obs_dose_value IS NOT NULL THEN 1 ELSE 0 END) as num_dose_records,
        SUM(CASE WHEN obs_radiation_field IS NOT NULL THEN 1 ELSE 0 END) as num_site_records,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT obs_radiation_field), ', ') as radiation_fields_observed
    FROM fhir_prd_db.v_radiation_treatments
    WHERE data_source_primary = 'observation'
    GROUP BY patient_fhir_id
),

-- ============================================================================
-- CTE 2: Patients with radiation documents
-- ============================================================================
patients_with_documents AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT document_id) as num_radiation_documents,
        MIN(doc_date) as earliest_document_date,
        MAX(doc_date) as latest_document_date,
        -- Count by priority/type
        SUM(CASE WHEN extraction_priority = 1 THEN 1 ELSE 0 END) as num_treatment_summaries,
        SUM(CASE WHEN extraction_priority = 2 THEN 1 ELSE 0 END) as num_consults,
        SUM(CASE WHEN extraction_priority >= 3 THEN 1 ELSE 0 END) as num_other_documents,
        -- Document categories
        ARRAY_JOIN(ARRAY_SORT(ARRAY_AGG(DISTINCT document_category)), ', ') as document_types
    FROM fhir_prd_db.v_radiation_documents
    GROUP BY patient_fhir_id
),

-- ============================================================================
-- CTE 3: Patients with radiation care plans
-- ============================================================================
patients_with_care_plans AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT care_plan_id) as num_care_plans,
        MIN(cp_period_start) as earliest_care_plan_start,
        MAX(cp_period_end) as latest_care_plan_end,
        ARRAY_JOIN(ARRAY_SORT(ARRAY_AGG(DISTINCT cp_status)), ', ') as care_plan_statuses,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT SUBSTR(cp_title, 1, 50)), ' | ') as care_plan_titles_sample
    FROM fhir_prd_db.v_radiation_care_plan_hierarchy
    GROUP BY patient_fhir_id
),

-- ============================================================================
-- CTE 4: Patients with radiation appointments
-- ============================================================================
patients_with_appointments AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT appointment_id) as num_appointments,
        SUM(CASE WHEN appointment_status = 'fulfilled' THEN 1 ELSE 0 END) as num_fulfilled_appointments,
        SUM(CASE WHEN appointment_status = 'cancelled' THEN 1 ELSE 0 END) as num_cancelled_appointments,
        MIN(appointment_start) as earliest_appointment,
        MAX(appointment_start) as latest_appointment
    FROM fhir_prd_db.v_radiation_treatment_appointments
    GROUP BY patient_fhir_id
),

-- ============================================================================
-- CTE 5: Patients with service requests (treatment orders)
-- ============================================================================
patients_with_service_requests AS (
    SELECT DISTINCT
        patient_fhir_id,
        COUNT(DISTINCT course_id) as num_service_requests,
        MIN(sr_occurrence_period_start) as earliest_sr_start,
        MAX(sr_occurrence_period_end) as latest_sr_end,
        ARRAY_JOIN(ARRAY_AGG(DISTINCT sr_code_text), ' | ') as service_request_codes
    FROM fhir_prd_db.v_radiation_treatments
    WHERE data_source_primary = 'service_request'
    GROUP BY patient_fhir_id
),

-- ============================================================================
-- CTE 6: Patients with ELECT radiation history flag (even without detailed data)
-- ============================================================================
patients_with_radiation_flag AS (
    SELECT DISTINCT SUBSTRING(subject_reference, 9) as patient_fhir_id
    FROM fhir_prd_db.observation
    WHERE code_text = 'ELECT - INTAKE FORM - TREATMENT HISTORY - RADIATION'
),

-- ============================================================================
-- CTE 7: Combine all patients who have ANY radiation data or radiation flag
-- ============================================================================
all_radiation_patients AS (
    SELECT DISTINCT patient_fhir_id FROM patients_with_structured_data
    UNION
    SELECT DISTINCT patient_fhir_id FROM patients_with_documents
    UNION
    SELECT DISTINCT patient_fhir_id FROM patients_with_care_plans
    UNION
    SELECT DISTINCT patient_fhir_id FROM patients_with_appointments
    UNION
    SELECT DISTINCT patient_fhir_id FROM patients_with_service_requests
    UNION
    SELECT DISTINCT patient_fhir_id FROM patients_with_radiation_flag
)

-- ============================================================================
-- MAIN SELECT: Data availability summary for each patient
-- ============================================================================
SELECT
    arp.patient_fhir_id as patient_fhir_id,

    -- ========================================================================
    -- DATA AVAILABILITY FLAGS (Boolean indicators)
    -- ========================================================================
    CASE WHEN prf.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_radiation_history_flag,
    CASE WHEN psd.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_structured_elect_data,
    CASE WHEN pd.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_radiation_documents,
    CASE WHEN pcp.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_care_plans,
    CASE WHEN pa.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_appointments,
    CASE WHEN psr.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_service_requests,

    -- ========================================================================
    -- DATA SOURCE COUNTS
    -- ========================================================================
    COALESCE(psd.num_structured_courses, 0) as num_structured_courses,
    COALESCE(pd.num_radiation_documents, 0) as num_radiation_documents,
    COALESCE(pcp.num_care_plans, 0) as num_care_plans,
    COALESCE(pa.num_appointments, 0) as num_appointments,
    COALESCE(psr.num_service_requests, 0) as num_service_requests,

    -- ========================================================================
    -- DOCUMENT BREAKDOWN (Priority-based counts)
    -- ========================================================================
    COALESCE(pd.num_treatment_summaries, 0) as num_treatment_summaries,
    COALESCE(pd.num_consults, 0) as num_consults,
    COALESCE(pd.num_other_documents, 0) as num_other_radiation_documents,

    -- ========================================================================
    -- APPOINTMENT BREAKDOWN
    -- ========================================================================
    COALESCE(pa.num_fulfilled_appointments, 0) as num_fulfilled_appointments,
    COALESCE(pa.num_cancelled_appointments, 0) as num_cancelled_appointments,

    -- ========================================================================
    -- TEMPORAL COVERAGE (Date ranges from each source)
    -- ========================================================================
    psd.earliest_structured_start as structured_data_earliest_date,
    psd.latest_structured_end as structured_data_latest_date,
    pd.earliest_document_date as documents_earliest_date,
    pd.latest_document_date as documents_latest_date,
    pcp.earliest_care_plan_start as care_plan_earliest_date,
    pcp.latest_care_plan_end as care_plan_latest_date,
    pa.earliest_appointment as appointments_earliest_date,
    pa.latest_appointment as appointments_latest_date,
    psr.earliest_sr_start as service_request_earliest_date,
    psr.latest_sr_end as service_request_latest_date,

    -- ========================================================================
    -- BEST AVAILABLE DATE RANGE (Across all sources)
    -- ========================================================================
    LEAST(
        psd.earliest_structured_start,
        pd.earliest_document_date,
        pcp.earliest_care_plan_start,
        pa.earliest_appointment,
        psr.earliest_sr_start
    ) as radiation_treatment_earliest_date,

    GREATEST(
        psd.latest_structured_end,
        pd.latest_document_date,
        pcp.latest_care_plan_end,
        pa.latest_appointment,
        psr.latest_sr_end
    ) as radiation_treatment_latest_date,

    -- ========================================================================
    -- STRUCTURED DATA DETAILS (When available)
    -- ========================================================================
    psd.num_dose_records,
    psd.num_site_records,
    psd.radiation_fields_observed,

    -- ========================================================================
    -- METADATA SAMPLES (For review/validation)
    -- ========================================================================
    pd.document_types as radiation_document_categories,
    pcp.care_plan_statuses,
    pcp.care_plan_titles_sample,
    psr.service_request_codes,

    -- ========================================================================
    -- DATA QUALITY / COMPLETENESS SCORE
    -- ========================================================================
    -- Score from 0-5 based on number of data sources available
    (
        CAST(CASE WHEN psd.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS INTEGER) +
        CAST(CASE WHEN pd.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS INTEGER) +
        CAST(CASE WHEN pcp.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS INTEGER) +
        CAST(CASE WHEN pa.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS INTEGER) +
        CAST(CASE WHEN psr.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS INTEGER)
    ) as num_data_sources_available,

    -- Normalized data quality score (0.0 to 1.0)
    CAST((
        CAST(CASE WHEN psd.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) +
        CAST(CASE WHEN pd.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) +
        CAST(CASE WHEN pcp.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) +
        CAST(CASE WHEN pa.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE) +
        CAST(CASE WHEN psr.patient_fhir_id IS NOT NULL THEN 1 ELSE 0 END AS DOUBLE)
    ) / 5.0 AS DOUBLE) as data_completeness_score,

    -- ========================================================================
    -- RECOMMENDED EXTRACTION STRATEGY
    -- ========================================================================
    CASE
        -- Best case: Have structured data + documents
        WHEN psd.patient_fhir_id IS NOT NULL AND pd.patient_fhir_id IS NOT NULL
            THEN 'structured_primary_with_document_validation'

        -- Good case: Have treatment summaries/consults (priority 1-2 documents)
        WHEN pd.num_treatment_summaries > 0 OR pd.num_consults > 0
            THEN 'document_based_high_priority'

        -- Moderate case: Have documents but lower priority
        WHEN pd.patient_fhir_id IS NOT NULL
            THEN 'document_based_standard'

        -- Structured only (no documents for validation)
        WHEN psd.patient_fhir_id IS NOT NULL
            THEN 'structured_only_no_validation'

        -- Limited data: Only care plans or appointments
        WHEN pcp.patient_fhir_id IS NOT NULL OR pa.patient_fhir_id IS NOT NULL
            THEN 'metadata_only_limited_extraction'

        ELSE 'insufficient_data'
    END as recommended_extraction_strategy

FROM all_radiation_patients arp
LEFT JOIN patients_with_radiation_flag prf ON arp.patient_fhir_id = prf.patient_fhir_id
LEFT JOIN patients_with_structured_data psd ON arp.patient_fhir_id = psd.patient_fhir_id
LEFT JOIN patients_with_documents pd ON arp.patient_fhir_id = pd.patient_fhir_id
LEFT JOIN patients_with_care_plans pcp ON arp.patient_fhir_id = pcp.patient_fhir_id
LEFT JOIN patients_with_appointments pa ON arp.patient_fhir_id = pa.patient_fhir_id
LEFT JOIN patients_with_service_requests psr ON arp.patient_fhir_id = psr.patient_fhir_id

ORDER BY
    num_data_sources_available DESC,
    radiation_treatment_earliest_date;
