-- ================================================================================
-- AGENT DATA ACCESS VIEWS
-- ================================================================================
-- Purpose: Provide structured access to free text documents for AI agents
-- Version: 1.0
-- Date: 2025-10-19
--
-- These views bridge structured FHIR data with unstructured clinical narratives
-- enabling agents to extract:
--   - Extent of Resection (from post-op MRI + operative notes)
--   - Tumor Status (from surveillance imaging + progress notes)
--   - Treatment Response (from clinical assessments)
--
-- AGENT WORKFLOW:
--   Agent 1 (Surgical Event Abstractor) → v_postop_imaging + v_operative_notes
--   Agent 2 (Tumor Status Abstractor) → v_imaging_with_reports + v_progress_notes
-- ================================================================================

-- ================================================================================
-- VIEW 1: v_imaging_with_reports
-- Purpose: Radiology reports with embedded free text for agent extraction
-- Use Case: Agent extraction of tumor status from surveillance MRIs
-- KEY: result_information column contains full radiology report text (avg 1500 chars)
-- ================================================================================
CREATE OR REPLACE VIEW fhir_prd_db.v_imaging_with_reports AS
SELECT
    -- Imaging event data (from v_imaging)
    vi.patient_fhir_id,
    vi.imaging_procedure_id,
    vi.imaging_date,
    vi.imaging_modality,
    vi.imaging_procedure,
    vi.category_text,
    vi.report_status,
    vi.report_issued,
    vi.age_at_imaging_days,
    CAST(vi.age_at_imaging_days AS DOUBLE) / 365.25 as age_at_imaging_years,

    -- FREE TEXT REPORT (THIS IS WHERE THE AGENT EXTRACTS FROM!)
    vi.result_information as radiology_report_text,  -- Full radiology report
    LENGTH(vi.result_information) as report_text_length,

    -- Structured fields (may have limited info)
    vi.report_conclusion,  -- Often NULL or brief summary
    vi.result_display,     -- Often NULL or brief

    -- Context flags for agent processing
    CASE
        WHEN vi.result_information IS NOT NULL AND LENGTH(vi.result_information) > 100
        THEN true ELSE false
    END as has_extractable_text,

    -- Priority for agent processing
    CASE
        WHEN LOWER(vi.imaging_modality) LIKE '%mri%brain%' THEN 'high'
        WHEN LOWER(vi.imaging_modality) LIKE '%mri%head%' THEN 'high'
        WHEN LOWER(vi.imaging_modality) LIKE '%mri%' THEN 'medium'
        WHEN LOWER(vi.imaging_modality) LIKE '%ct%brain%' THEN 'medium'
        ELSE 'low'
    END as extraction_priority,

    -- Agent processing metadata
    CAST(MAP(
        ARRAY['text_field', 'avg_expected_length', 'extraction_targets', 'document_type'],
        ARRAY[
            'result_information',
            '1500',
            'tumor_status|size_measurements|comparison|impression|clinical_indication',
            'radiology_report_embedded'
        ]
    ) AS JSON) as agent_context

FROM fhir_prd_db.v_imaging vi

WHERE vi.result_information IS NOT NULL  -- Only include reports with text
  AND (vi.imaging_modality LIKE '%MRI%'  -- Focus on MRI (primary modality for brain tumors)
   OR vi.imaging_modality LIKE '%CT%')   -- Include CT for completeness

ORDER BY vi.patient_fhir_id, vi.imaging_date;

-- ================================================================================
-- VIEW 2: v_postop_imaging
-- Purpose: Post-operative imaging for extent of resection (EOR) assessment
-- Use Case: Agent 1 extraction of EOR from post-op MRI reports
-- ================================================================================
CREATE OR REPLACE VIEW fhir_prd_db.v_postop_imaging AS
SELECT
    -- Surgical procedure context
    vp.patient_fhir_id,
    vp.procedure_fhir_id,
    vp.procedure_date,
    vp.proc_code_text as procedure_description,
    vp.surgery_type,
    vp.cpt_code,
    vp.cpt_classification,
    vp.is_tumor_surgery,
    vp.age_at_procedure_days,

    -- Post-operative imaging
    vir.imaging_procedure_id,
    vir.imaging_date,
    vir.imaging_modality,
    vir.imaging_procedure,
    vir.report_conclusion,
    vir.result_display,
    vir.document_reference_id,
    vir.binary_id,
    vir.document_description,
    vir.radiologist,

    -- Timing context
    DATE_DIFF('day', vp.procedure_date, vir.imaging_date) as days_post_op,
    DATE_DIFF('hour', CAST(vp.procedure_date AS TIMESTAMP(3)), vir.imaging_date) as hours_post_op,

    -- Surgery sequence (for determining initial vs. recurrence/progression)
    ROW_NUMBER() OVER (
        PARTITION BY vp.patient_fhir_id
        ORDER BY vp.procedure_date
    ) as surgery_number,

    -- Agent context
    CAST(MAP(
        ARRAY['assessment_purpose', 'extraction_target', 'clinical_context', 'requires_eor_extraction'],
        ARRAY[
            'extent_of_resection_assessment',
            'GTR|STR|Partial|Biopsy|Unknown',
            CAST('Post-op day ' || CAST(DATE_DIFF('day', vp.procedure_date, vir.imaging_date) AS VARCHAR) AS VARCHAR),
            'true'
        ]
    ) AS JSON) as agent_context

FROM fhir_prd_db.v_procedures_tumor vp
JOIN fhir_prd_db.v_imaging_with_reports vir
    ON vp.patient_fhir_id = vir.patient_fhir_id
    -- Post-op imaging window: procedure date to 7 days after
    AND vir.imaging_date BETWEEN vp.procedure_date AND DATE_ADD('day', 7, vp.procedure_date)

WHERE vp.is_tumor_surgery = true
    AND LOWER(vir.imaging_modality) LIKE '%mri%'  -- MRI is gold standard for post-op assessment

ORDER BY vp.patient_fhir_id, vp.procedure_date, vir.imaging_date;

-- ================================================================================
-- VIEW 3: v_progress_notes
-- Purpose: Clinical progress notes for tumor status narrative assessment
-- Use Case: Agent 2 cross-validation of imaging findings with clinical assessment
-- ================================================================================
CREATE OR REPLACE VIEW fhir_prd_db.v_progress_notes AS
SELECT
    -- Document identification
    bf.patient_fhir_id,
    bf.document_reference_id,
    bf.binary_id,
    bf.dr_date as note_date,
    bf.dr_description as note_description,
    bf.dr_type_text as note_type,
    bf.dr_status,
    bf.dr_encounter_references,
    bf.dr_authenticator as provider,
    bf.age_at_document_days,
    CAST(bf.age_at_document_days AS DOUBLE) / 365.25 as age_at_document_years,

    -- Linked visit context
    vv.visit_date,
    vv.visit_type,
    vv.appointment_type_text,
    vv.appointment_status,
    vv.encounter_status,
    vv.source as visit_source,

    -- Content metadata
    bf.content_type,
    bf.content_size_bytes,
    bf.content_title,

    -- Specialty context (inferred from description)
    CASE
        WHEN LOWER(bf.dr_description) LIKE '%oncol%' THEN 'oncology'
        WHEN LOWER(bf.dr_description) LIKE '%neurosurg%' THEN 'neurosurgery'
        WHEN LOWER(bf.dr_description) LIKE '%neuro-oncol%' THEN 'neuro-oncology'
        WHEN LOWER(bf.dr_description) LIKE '%radiation%' THEN 'radiation_oncology'
        ELSE 'general'
    END as specialty_context,

    -- Agent processing metadata
    CAST(MAP(
        ARRAY['document_type', 'requires_text_extraction', 'extraction_targets', 'extraction_priority'],
        ARRAY[
            'progress_note',
            'true',
            'tumor_status|treatment_response|plan_changes|progression_mentions',
            CAST(CASE
                WHEN LOWER(bf.dr_description) LIKE '%oncol%' THEN 'high'
                WHEN LOWER(bf.dr_description) LIKE '%neurosurg%' THEN 'high'
                ELSE 'medium'
            END AS VARCHAR)
        ]
    ) AS JSON) as agent_context

FROM fhir_prd_db.v_binary_files bf
LEFT JOIN fhir_prd_db.v_visits_unified vv
    ON bf.patient_fhir_id = vv.patient_fhir_id
    AND DATE(bf.dr_date) = vv.visit_date

WHERE bf.dr_type_text = 'Progress Notes'

ORDER BY bf.patient_fhir_id, bf.dr_date;

-- ================================================================================
-- VIEW 4: v_operative_reports
-- Purpose: Operative notes for EOR and procedure details
-- Use Case: Agent 1 extraction of surgical details and initial EOR assessment
-- ================================================================================
CREATE OR REPLACE VIEW fhir_prd_db.v_operative_reports AS
SELECT
    -- Document identification
    bf.patient_fhir_id,
    bf.document_reference_id,
    bf.binary_id,
    bf.dr_date as operative_date,
    bf.dr_description as report_description,
    bf.dr_type_text as report_type,
    bf.dr_authenticator as surgeon,
    bf.age_at_document_days,

    -- Linked procedure
    vp.procedure_fhir_id,
    vp.procedure_date,
    vp.proc_code_text,
    vp.surgery_type,
    vp.cpt_code,
    vp.cpt_classification,

    -- Content metadata
    bf.content_type,
    bf.content_size_bytes,
    bf.content_title,

    -- Agent processing metadata
    CAST(MAP(
        ARRAY['document_type', 'requires_text_extraction', 'extraction_targets'],
        ARRAY[
            'operative_report',
            'true',
            'extent_of_resection|surgical_approach|complications|pathology_findings'
        ]
    ) AS JSON) as agent_context

FROM fhir_prd_db.v_binary_files bf
LEFT JOIN fhir_prd_db.v_procedures_tumor vp
    ON bf.patient_fhir_id = vp.patient_fhir_id
    -- Match operative note to procedure within 7 days
    AND DATE(bf.dr_date) BETWEEN DATE_ADD('day', -1, vp.procedure_date)
                             AND DATE_ADD('day', 7, vp.procedure_date)

WHERE (LOWER(bf.dr_type_text) LIKE '%operative%'
    OR LOWER(bf.dr_description) LIKE '%operative note%'
    OR LOWER(bf.dr_description) LIKE '%op note%'
    OR LOWER(bf.dr_description) LIKE '%procedure note%')

ORDER BY bf.patient_fhir_id, bf.dr_date;

-- ================================================================================
-- USAGE NOTES FOR AGENTS
-- ================================================================================
--
-- AGENT 1 (Surgical Event Abstractor):
--   Input Views: v_postop_imaging, v_operative_reports
--   Extraction Task: Determine extent_of_resection from free text
--   Output: tumor_epochs table with EOR classifications
--
-- AGENT 2 (Tumor Status Abstractor):
--   Input Views: v_imaging_with_reports, v_progress_notes
--   Extraction Task: Extract tumor status (NED/Stable/Increased/Decreased)
--   Output: tumor_status_assessments table with longitudinal status
--
-- DOCUMENT TEXT RETRIEVAL:
--   - binary_id links to actual document content in S3/file storage
--   - Agents will need document retrieval service to fetch text
--   - content_type indicates format (PDF, text, etc.)
--
-- ================================================================================
