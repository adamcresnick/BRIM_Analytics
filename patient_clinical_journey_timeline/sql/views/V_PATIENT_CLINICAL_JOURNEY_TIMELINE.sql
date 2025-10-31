-- =====================================================================================
-- View: v_patient_clinical_journey_timeline
-- Description: Unified patient clinical journey timeline integrating diagnosis,
--              procedures, treatments, imaging, and visits with WHO 2021-informed
--              treatment response assessment
--
-- Data Sources:
--   - v_pathology_diagnostics (diagnosis with molecular markers)
--   - v_procedures_tumor (surgical procedures)
--   - v_chemo_treatment_episodes (chemotherapy episodes)
--   - v_radiation_episode_enrichment (radiation episodes)
--   - v_imaging (imaging studies with free text conclusions)
--   - v_visits_unified (clinical visits)
--
-- Key Features:
--   - Chronological event sequencing per patient
--   - Surgery-anchored temporal metrics (days_from_initial_surgery)
--   - Treatment phase classification (pre-op → surgery → adjuvant → active → surveillance)
--   - Response assessment from imaging report free text (progression/response flags)
--   - Treatment episode linkage for imaging studies
--   - Progression-free survival (PFS) calculation
--
-- Author: Claude (WHO 2021 CNS Tumor Classification Framework)
-- Created: 2025-10-30
-- =====================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_clinical_journey_timeline AS

-- ============================================================================
-- STEP 1: Identify index surgery (temporal anchor for each patient)
-- ============================================================================
WITH patient_index_surgery AS (
    SELECT
        patient_fhir_id,
        MIN(proc_performed_date_time) as initial_surgery_datetime,
        CAST(MIN(proc_performed_date_time) AS DATE) as initial_surgery_date
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = true
        AND surgery_type IN ('resection', 'biopsy', 'debulking')
    GROUP BY patient_fhir_id
),

-- ============================================================================
-- STEP 2: Free Text Pattern Matching for Response Assessment
-- ============================================================================

-- Progression indicators from imaging report conclusions
progression_patterns AS (
    SELECT
        patient_fhir_id,
        imaging_date,
        imaging_id,
        report_conclusion,
        CASE
            WHEN LOWER(report_conclusion) SIMILAR TO '%(increas|enlarg|expan|grow|worsen|progress|new enhanc|new lesion)%'
                THEN 'progression_suspected'
            WHEN LOWER(report_conclusion) SIMILAR TO '%(recur|new tumor|new mass)%'
                THEN 'recurrence_suspected'
            ELSE NULL
        END as progression_flag
    FROM fhir_prd_db.v_imaging
    WHERE report_conclusion IS NOT NULL
),

-- Response indicators from imaging report conclusions
response_patterns AS (
    SELECT
        patient_fhir_id,
        imaging_date,
        imaging_id,
        report_conclusion,
        CASE
            WHEN LOWER(report_conclusion) SIMILAR TO '%(decreas|reduc|shrink|smaller|improv|resolv)%'
                THEN 'response_suspected'
            WHEN LOWER(report_conclusion) SIMILAR TO '%(stable|unchanged|no change|no significant change)%'
                THEN 'stable_disease'
            WHEN LOWER(report_conclusion) SIMILAR TO '%(no evidence|no residual|complete respon)%'
                THEN 'complete_response_suspected'
            ELSE NULL
        END as response_flag
    FROM fhir_prd_db.v_imaging
    WHERE report_conclusion IS NOT NULL
),

-- Surgical outcome assessment from procedure outcome text
surgical_outcome_assessment AS (
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        proc_performed_date_time,
        proc_outcome_text,
        CASE
            WHEN LOWER(COALESCE(proc_outcome_text, '')) SIMILAR TO '%(gross total|complete resection|gtr|100%)%'
                THEN 'GTR'
            WHEN LOWER(COALESCE(proc_outcome_text, '')) SIMILAR TO '%(subtotal|near total|ntr|90%|95%)%'
                THEN 'STR'
            WHEN LOWER(COALESCE(proc_outcome_text, '')) SIMILAR TO '%(partial|incomplete)%'
                THEN 'partial_resection'
            WHEN LOWER(COALESCE(proc_outcome_text, '')) SIMILAR TO '%(biopsy only)%'
                THEN 'biopsy'
            ELSE 'unspecified_extent'
        END as resection_extent_from_text,
        CASE
            WHEN LOWER(COALESCE(proc_outcome_text, '')) SIMILAR TO '%(residual|remaining tumor|left behind)%'
                THEN true
            ELSE false
        END as residual_tumor_mentioned
    FROM fhir_prd_db.v_procedures_tumor
    WHERE proc_outcome_text IS NOT NULL
),

-- ============================================================================
-- STEP 3: Normalize All Events to Common Schema
-- ============================================================================

-- Diagnosis Events
diagnosis_events AS (
    SELECT
        pd.patient_fhir_id,
        CAST(pd.diagnostic_date AS DATE) as event_date,
        TRY_CAST(pd.diagnostic_date AS TIMESTAMP) as event_datetime,
        'diagnosis' as event_type,
        pd.diagnostic_source as event_subtype,
        CONCAT(
            COALESCE(pd.diagnostic_name, 'Unknown diagnosis'),
            CASE WHEN pd.component_name IS NOT NULL
                 THEN ' - ' || pd.component_name || ': ' || COALESCE(pd.result_value, 'N/A')
                 ELSE ''
            END
        ) as event_description,
        CAST(pd.source_id AS VARCHAR) as event_id,
        'v_pathology_diagnostics' as source_view,
        NULL as episode_id,
        pd.days_from_surgery,
        CAST(pd.extraction_priority AS DOUBLE) as priority_score,
        pd.diagnostic_category as event_category,
        pd.document_category,
        NULL as free_text_content
    FROM fhir_prd_db.v_pathology_diagnostics pd
),

-- Surgery Events
surgery_events AS (
    SELECT
        pt.patient_fhir_id,
        CAST(pt.proc_performed_date_time AS DATE) as event_date,
        pt.proc_performed_date_time as event_datetime,
        'surgery' as event_type,
        pt.surgery_type as event_subtype,
        CONCAT(
            COALESCE(pt.proc_code_text, 'Surgical procedure'),
            ' (', COALESCE(pt.surgery_extent, 'extent unknown'),
            CASE WHEN pt.is_tumor_surgery THEN ', tumor surgery' ELSE '' END,
            ')'
        ) as event_description,
        pt.procedure_fhir_id as event_id,
        'v_procedures_tumor' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, CAST(pt.proc_performed_date_time AS DATE)) as days_from_surgery,
        NULL as priority_score,
        pt.procedure_category as event_category,
        NULL as document_category,
        pt.proc_outcome_text as free_text_content
    FROM fhir_prd_db.v_procedures_tumor pt
    LEFT JOIN patient_index_surgery pis ON pt.patient_fhir_id = pis.patient_fhir_id
    WHERE pt.is_tumor_surgery = true OR pt.surgery_type IS NOT NULL
),

-- Chemotherapy Episode Start Events
chemo_start_events AS (
    SELECT
        ce.patient_fhir_id,
        CAST(ce.episode_start_datetime AS DATE) as event_date,
        ce.episode_start_datetime as event_datetime,
        'chemo_episode_start' as event_type,
        'treatment_initiation' as event_subtype,
        CONCAT(
            'Chemotherapy started: ', COALESCE(ce.chemo_preferred_name, 'unspecified regimen'),
            ' (', CAST(ce.medication_count AS VARCHAR), ' medications, ',
            CAST(ce.episode_duration_days AS VARCHAR), ' days)'
        ) as event_description,
        ce.episode_id as event_id,
        'v_chemo_treatment_episodes' as source_view,
        ce.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, CAST(ce.episode_start_datetime AS DATE)) as days_from_surgery,
        NULL as priority_score,
        ce.chemo_drug_category as event_category,
        NULL as document_category,
        NULL as free_text_content
    FROM fhir_prd_db.v_chemo_treatment_episodes ce
    LEFT JOIN patient_index_surgery pis ON ce.patient_fhir_id = pis.patient_fhir_id
),

-- Chemotherapy Episode End Events
chemo_end_events AS (
    SELECT
        ce.patient_fhir_id,
        CAST(ce.episode_end_datetime AS DATE) as event_date,
        ce.episode_end_datetime as event_datetime,
        'chemo_episode_end' as event_type,
        'treatment_completion' as event_subtype,
        CONCAT(
            'Chemotherapy completed: ', COALESCE(ce.chemo_preferred_name, 'unspecified regimen'),
            CASE WHEN ce.total_episode_dose IS NOT NULL
                 THEN ' (total dose: ' || CAST(ce.total_episode_dose AS VARCHAR) || ' ' ||
                      COALESCE(ce.total_episode_dose_unit, 'units') || ')'
                 ELSE ''
            END
        ) as event_description,
        ce.episode_id as event_id,
        'v_chemo_treatment_episodes' as source_view,
        ce.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, CAST(ce.episode_end_datetime AS DATE)) as days_from_surgery,
        NULL as priority_score,
        ce.chemo_drug_category as event_category,
        NULL as document_category,
        NULL as free_text_content
    FROM fhir_prd_db.v_chemo_treatment_episodes ce
    LEFT JOIN patient_index_surgery pis ON ce.patient_fhir_id = pis.patient_fhir_id
),

-- Radiation Episode Start Events
radiation_start_events AS (
    SELECT
        re.patient_fhir_id,
        re.episode_start_date as event_date,
        CAST(re.episode_start_date AS TIMESTAMP) as event_datetime,
        'radiation_episode_start' as event_type,
        'treatment_initiation' as event_subtype,
        CONCAT(
            'Radiation started: ', CAST(re.total_dose_cgy AS VARCHAR), ' cGy planned',
            ' (', CAST(re.num_unique_fields AS VARCHAR), ' fields)'
        ) as event_description,
        re.episode_id as event_id,
        'v_radiation_episode_enrichment' as source_view,
        re.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, re.episode_start_date) as days_from_surgery,
        re.enrichment_score as priority_score,
        re.radiation_fields as event_category,
        NULL as document_category,
        NULL as free_text_content
    FROM fhir_prd_db.v_radiation_episode_enrichment re
    LEFT JOIN patient_index_surgery pis ON re.patient_fhir_id = pis.patient_fhir_id
),

-- Radiation Episode End Events
radiation_end_events AS (
    SELECT
        re.patient_fhir_id,
        re.episode_end_date as event_date,
        CAST(re.episode_end_date AS TIMESTAMP) as event_datetime,
        'radiation_episode_end' as event_type,
        'treatment_completion' as event_subtype,
        CONCAT(
            'Radiation completed: ', CAST(re.total_dose_cgy AS VARCHAR), ' cGy delivered',
            ' in ', CAST(DATE_DIFF('day', re.episode_start_date, re.episode_end_date) AS VARCHAR), ' days'
        ) as event_description,
        re.episode_id as event_id,
        'v_radiation_episode_enrichment' as source_view,
        re.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, re.episode_end_date) as days_from_surgery,
        re.enrichment_score as priority_score,
        re.radiation_fields as event_category,
        NULL as document_category,
        NULL as free_text_content
    FROM fhir_prd_db.v_radiation_episode_enrichment re
    LEFT JOIN patient_index_surgery pis ON re.patient_fhir_id = pis.patient_fhir_id
),

-- Imaging Events (with response assessment)
imaging_events AS (
    SELECT
        im.patient_fhir_id,
        im.imaging_date as event_date,
        CAST(im.imaging_date AS TIMESTAMP) as event_datetime,
        'imaging' as event_type,
        im.imaging_modality as event_subtype,
        CONCAT(
            COALESCE(im.imaging_procedure, 'Imaging study'),
            CASE WHEN im.report_conclusion IS NOT NULL
                 THEN ' - ' || im.report_conclusion
                 ELSE ''
            END,
            CASE
                WHEN prog.progression_flag IS NOT NULL
                    THEN ' [' || prog.progression_flag || ']'
                WHEN resp.response_flag IS NOT NULL
                    THEN ' [' || resp.response_flag || ']'
                ELSE ''
            END
        ) as event_description,
        im.imaging_id as event_id,
        'v_imaging' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, im.imaging_date) as days_from_surgery,
        NULL as priority_score,
        im.imaging_modality as event_category,
        NULL as document_category,
        im.report_conclusion as free_text_content
    FROM fhir_prd_db.v_imaging im
    LEFT JOIN patient_index_surgery pis ON im.patient_fhir_id = pis.patient_fhir_id
    LEFT JOIN progression_patterns prog
        ON im.patient_fhir_id = prog.patient_fhir_id
        AND im.imaging_date = prog.imaging_date
        AND im.imaging_id = prog.imaging_id
    LEFT JOIN response_patterns resp
        ON im.patient_fhir_id = resp.patient_fhir_id
        AND im.imaging_date = resp.imaging_date
        AND im.imaging_id = resp.imaging_id
),

-- Visit Events
visit_events AS (
    SELECT
        vu.patient_fhir_id,
        vu.visit_date as event_date,
        CAST(vu.visit_date AS TIMESTAMP) as event_datetime,
        'visit' as event_type,
        vu.visit_type as event_subtype,
        CONCAT(
            COALESCE(vu.visit_type, 'Clinical visit'),
            ' (', COALESCE(vu.appointment_status, 'status unknown'),
            ', ', COALESCE(vu.encounter_status, 'encounter status unknown'), ')'
        ) as event_description,
        vu.visit_id as event_id,
        'v_visits_unified' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, vu.visit_date) as days_from_surgery,
        NULL as priority_score,
        vu.visit_type as event_category,
        NULL as document_category,
        vu.appointment_description as free_text_content
    FROM fhir_prd_db.v_visits_unified vu
    LEFT JOIN patient_index_surgery pis ON vu.patient_fhir_id = pis.patient_fhir_id
),

-- ============================================================================
-- STEP 4: Union All Events into Unified Timeline
-- ============================================================================
unified_timeline AS (
    SELECT * FROM diagnosis_events
    UNION ALL
    SELECT * FROM surgery_events
    UNION ALL
    SELECT * FROM chemo_start_events
    UNION ALL
    SELECT * FROM chemo_end_events
    UNION ALL
    SELECT * FROM radiation_start_events
    UNION ALL
    SELECT * FROM radiation_end_events
    UNION ALL
    SELECT * FROM imaging_events
    UNION ALL
    SELECT * FROM visit_events
),

-- ============================================================================
-- STEP 5: Add Sequence Numbering and Phase Classification
-- ============================================================================
timeline_sequenced AS (
    SELECT
        ut.*,
        ROW_NUMBER() OVER (
            PARTITION BY ut.patient_fhir_id
            ORDER BY ut.event_date, ut.event_datetime, ut.event_type
        ) as event_sequence_number,

        -- Classify temporal phase relative to initial surgery
        CASE
            WHEN ut.days_from_surgery < 0 THEN 'pre_surgery'
            WHEN ut.days_from_surgery = 0 THEN 'surgery_day'
            WHEN ut.days_from_surgery BETWEEN 1 AND 30 THEN 'early_post_op'
            WHEN ut.days_from_surgery BETWEEN 31 AND 90 THEN 'adjuvant_treatment_window'
            WHEN ut.days_from_surgery BETWEEN 91 AND 365 THEN 'active_treatment_phase'
            WHEN ut.days_from_surgery > 365 THEN 'surveillance_phase'
            ELSE 'unknown_phase'
        END as treatment_phase,

        -- Calculate time to next event
        LEAD(ut.event_date) OVER (
            PARTITION BY ut.patient_fhir_id
            ORDER BY ut.event_date, ut.event_datetime
        ) as next_event_date,

        DATE_DIFF('day',
            ut.event_date,
            LEAD(ut.event_date) OVER (
                PARTITION BY ut.patient_fhir_id
                ORDER BY ut.event_date, ut.event_datetime
            )
        ) as days_to_next_event

    FROM unified_timeline ut
),

-- ============================================================================
-- STEP 6: Imaging Treatment Linkage (link imaging to nearest treatment episode)
-- ============================================================================
imaging_treatment_linkage AS (
    SELECT
        im.patient_fhir_id,
        im.event_date as imaging_date,
        im.event_id as imaging_id,
        prog.progression_flag,
        resp.response_flag,

        -- Find nearest radiation episode
        (SELECT episode_id
         FROM fhir_prd_db.v_radiation_episode_enrichment re
         WHERE re.patient_fhir_id = im.patient_fhir_id
           AND im.event_date BETWEEN
                DATE_ADD('day', -30, re.episode_start_date) AND
                DATE_ADD('day', 90, re.episode_end_date)
         ORDER BY ABS(DATE_DIFF('day', im.event_date, re.episode_end_date))
         LIMIT 1
        ) as nearest_radiation_episode_id,

        -- Find nearest chemo episode
        (SELECT episode_id
         FROM fhir_prd_db.v_chemo_treatment_episodes ce
         WHERE ce.patient_fhir_id = im.patient_fhir_id
           AND im.event_date BETWEEN
                DATE_ADD('day', -30, CAST(ce.episode_start_datetime AS DATE)) AND
                DATE_ADD('day', 90, CAST(ce.episode_end_datetime AS DATE))
         ORDER BY ABS(DATE_DIFF('day', im.event_date, CAST(ce.episode_end_datetime AS DATE)))
         LIMIT 1
        ) as nearest_chemo_episode_id,

        -- Classify imaging timing
        CASE
            WHEN im.days_from_surgery BETWEEN -7 AND 2
                THEN 'pre_op_baseline'
            WHEN im.days_from_surgery BETWEEN 0 AND 2
                THEN 'immediate_post_op'
            WHEN EXISTS (
                SELECT 1 FROM fhir_prd_db.v_radiation_episode_enrichment re
                WHERE re.patient_fhir_id = im.patient_fhir_id
                  AND im.event_date BETWEEN re.episode_start_date AND re.episode_end_date
            ) THEN 'during_radiation'
            WHEN EXISTS (
                SELECT 1 FROM fhir_prd_db.v_radiation_episode_enrichment re
                WHERE re.patient_fhir_id = im.patient_fhir_id
                  AND im.event_date BETWEEN
                      DATE_ADD('day', 1, re.episode_end_date) AND
                      DATE_ADD('day', 60, re.episode_end_date)
            ) THEN 'early_post_radiation'
            WHEN EXISTS (
                SELECT 1 FROM fhir_prd_db.v_chemo_treatment_episodes ce
                WHERE ce.patient_fhir_id = im.patient_fhir_id
                  AND im.event_date BETWEEN
                      CAST(ce.episode_start_datetime AS DATE) AND
                      CAST(ce.episode_end_datetime AS DATE)
            ) THEN 'during_chemo'
            WHEN im.days_from_surgery > 365
                THEN 'long_term_surveillance'
            ELSE 'surveillance'
        END as imaging_phase

    FROM imaging_events im
    LEFT JOIN progression_patterns prog
        ON im.patient_fhir_id = prog.patient_fhir_id
        AND im.event_date = prog.imaging_date
        AND im.event_id = prog.imaging_id
    LEFT JOIN response_patterns resp
        ON im.patient_fhir_id = resp.patient_fhir_id
        AND im.event_date = resp.imaging_date
        AND im.event_id = resp.imaging_id
),

-- ============================================================================
-- STEP 7: Calculate Progression-Free Survival (PFS)
-- ============================================================================
time_to_progression AS (
    SELECT
        patient_fhir_id,
        MIN(imaging_date) as first_progression_date,
        MIN(DATE_DIFF('day',
            (SELECT initial_surgery_date FROM patient_index_surgery pis WHERE pis.patient_fhir_id = itl.patient_fhir_id),
            imaging_date
        )) as days_to_progression
    FROM imaging_treatment_linkage itl
    WHERE progression_flag IN ('progression_suspected', 'recurrence_suspected')
    GROUP BY patient_fhir_id
),

pfs_analysis AS (
    SELECT
        pis.patient_fhir_id,
        pis.initial_surgery_date,

        -- Latest treatment completion
        GREATEST(
            COALESCE(MAX(CAST(ce.episode_end_datetime AS DATE)), pis.initial_surgery_date),
            COALESCE(MAX(re.episode_end_date), pis.initial_surgery_date)
        ) as treatment_completion_date,

        ttp.first_progression_date,
        ttp.days_to_progression,

        -- PFS from treatment completion to progression
        DATE_DIFF('day',
            GREATEST(
                COALESCE(MAX(CAST(ce.episode_end_datetime AS DATE)), pis.initial_surgery_date),
                COALESCE(MAX(re.episode_end_date), pis.initial_surgery_date)
            ),
            ttp.first_progression_date
        ) as pfs_days_from_treatment_completion,

        -- Flag if progressed
        CASE WHEN ttp.first_progression_date IS NOT NULL THEN true ELSE false END as progressed

    FROM patient_index_surgery pis
    LEFT JOIN fhir_prd_db.v_chemo_treatment_episodes ce
        ON pis.patient_fhir_id = ce.patient_fhir_id
    LEFT JOIN fhir_prd_db.v_radiation_episode_enrichment re
        ON pis.patient_fhir_id = re.patient_fhir_id
    LEFT JOIN time_to_progression ttp
        ON pis.patient_fhir_id = ttp.patient_fhir_id
    GROUP BY pis.patient_fhir_id, pis.initial_surgery_date, ttp.first_progression_date, ttp.days_to_progression
),

-- ============================================================================
-- STEP 8: Get Patient Diagnosis Context (highest priority diagnosis)
-- ============================================================================
patient_diagnosis_context AS (
    SELECT DISTINCT
        patient_fhir_id,
        FIRST_VALUE(diagnostic_name) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY COALESCE(extraction_priority, 999), diagnostic_date
        ) as diagnostic_name,
        FIRST_VALUE(diagnostic_category) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY COALESCE(extraction_priority, 999), diagnostic_date
        ) as diagnostic_category,
        FIRST_VALUE(component_name) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY COALESCE(extraction_priority, 999), diagnostic_date
        ) as component_name,
        FIRST_VALUE(result_value) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY COALESCE(extraction_priority, 999), diagnostic_date
        ) as result_value
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE extraction_priority IS NOT NULL
)

-- ============================================================================
-- FINAL SELECT: Assemble Complete Timeline with All Context
-- ============================================================================
SELECT
    -- Patient identifiers
    ts.patient_fhir_id,
    ts.event_sequence_number,

    -- Temporal fields
    ts.event_date,
    ts.event_datetime,
    ts.days_from_surgery as days_from_initial_surgery,
    ts.treatment_phase,
    ts.days_to_next_event,

    -- Event classification
    ts.event_type,
    ts.event_subtype,
    ts.event_description,
    ts.event_category,

    -- Source tracking
    ts.event_id,
    ts.source_view,
    ts.episode_id,

    -- Priority/Quality
    ts.priority_score,
    ts.document_category,
    ts.free_text_content,

    -- Diagnosis context (from v_pathology_diagnostics)
    pdc.diagnostic_name as patient_diagnosis,
    pdc.diagnostic_category as diagnosis_category,
    pdc.component_name as molecular_marker,
    pdc.result_value as molecular_result,

    -- Response assessment (for imaging events)
    itl.progression_flag,
    itl.response_flag,
    itl.imaging_phase,
    itl.nearest_radiation_episode_id as linked_radiation_episode,
    itl.nearest_chemo_episode_id as linked_chemo_episode,

    -- Surgical outcome (for surgery events)
    soa.resection_extent_from_text,
    soa.residual_tumor_mentioned,

    -- PFS metrics (patient-level, repeated for all events)
    pfs.days_to_progression as patient_days_to_progression,
    pfs.pfs_days_from_treatment_completion as patient_pfs_from_treatment,
    pfs.progressed as patient_has_progressed

FROM timeline_sequenced ts

-- Join diagnosis context
LEFT JOIN patient_diagnosis_context pdc
    ON ts.patient_fhir_id = pdc.patient_fhir_id

-- Join imaging treatment linkage (only for imaging events)
LEFT JOIN imaging_treatment_linkage itl
    ON ts.event_id = itl.imaging_id
    AND ts.source_view = 'v_imaging'

-- Join surgical outcome assessment (only for surgery events)
LEFT JOIN surgical_outcome_assessment soa
    ON ts.event_id = soa.procedure_fhir_id
    AND ts.source_view = 'v_procedures_tumor'

-- Join PFS analysis (patient-level metrics)
LEFT JOIN pfs_analysis pfs
    ON ts.patient_fhir_id = pfs.patient_fhir_id

ORDER BY ts.patient_fhir_id, ts.event_sequence_number;
