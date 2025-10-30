-- ============================================================================
-- VIEW: v_pathology_diagnostics
-- ============================================================================
-- Purpose: Comprehensive surgery-anchored pathology diagnostics for tumor patients
--
-- Design Philosophy: SURGERY-ANCHORED, FEATURE-AGNOSTIC, NLP-READY
--   - Anchors to confirmed tumor surgeries from v_procedures_tumor
--   - Captures pathology from surgical specimens only (±7 days of surgery)
--   - NO hardcoded molecular features (works across all WHO classifications)
--   - Uses FHIR resource types and standard codes for generic categorization
--   - Result values preserved as-is for downstream analysis
--   - Includes URLs to binary reports for NLP workflows
--
-- Data Sources (4 surgery-linked sources):
--   1. observation (linked to surgical specimens via specimen_reference)
--      - Includes Pathology Surgical, Genomics Interpretation, Pathology Gross, etc.
--      - Contains free text results in value_string field
--   2. diagnostic_report (surgical encounters, ±30 days, includes presented_form URLs)
--   3. document_reference (pathology documents, ±60 days, includes content URLs)
--   4. condition (problem_list ICD-10/SNOMED diagnoses, ±180 days, patient-level)
--
-- NOTE: molecular_tests data is NOT included to avoid duplication with observations.
--       Use v_molecular_tests as a separate curated view for molecular testing data.
--
-- Temporal Windows:
--   - Surgical specimens: ±7 days from surgery date
--   - Observations: Linked via specimen_reference (no temporal constraint)
--   - Diagnostic reports: ±30 days from surgery date
--   - Documents: ±60 days from surgery date
--   - Problem list diagnoses: ±180 days from surgery date
--
-- Created: 2025-10-30
-- Last Modified: 2025-10-30
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_pathology_diagnostics AS

WITH oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),

-- ============================================================================
-- CTE 1: Tumor Surgeries (anchor point from validated v_procedures_tumor)
-- ============================================================================
tumor_surgeries AS (
    SELECT
        patient_fhir_id,
        procedure_fhir_id,
        proc_performed_date_time as surgery_datetime,
        CAST(proc_performed_date_time AS DATE) as surgery_date,
        proc_code_text as surgery_name,
        surgery_type,
        pbs_body_site_text as surgical_site,
        cpt_code as surgery_cpt,
        proc_encounter_reference as surgery_encounter
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = TRUE
      AND is_likely_performed = TRUE
),

-- ============================================================================
-- CTE 2: Surgical Specimens (linked to tumor surgeries by patient + date)
-- ============================================================================
surgical_specimens AS (
    SELECT DISTINCT
        ts.patient_fhir_id,
        ts.procedure_fhir_id,
        ts.surgery_datetime,
        ts.surgery_date,
        ts.surgery_encounter,
        s.id as specimen_id,
        s.type_text as specimen_type,
        s.collection_body_site_text as specimen_site,
        CAST(TRY(from_iso8601_timestamp(s.collection_collected_date_time)) AS TIMESTAMP(3)) as collection_datetime,
        TRY(CAST(CAST(s.collection_collected_date_time AS VARCHAR) AS DATE)) as collection_date
    FROM tumor_surgeries ts
    INNER JOIN fhir_prd_db.specimen s
        ON ts.patient_fhir_id = REPLACE(s.subject_reference, 'Patient/', '')
        AND ABS(DATE_DIFF('day',
            ts.surgery_date,
            TRY(CAST(CAST(s.collection_collected_date_time AS VARCHAR) AS DATE))
        )) <= 7  -- Within 7 days of surgery
    WHERE s.id IS NOT NULL
),

-- ============================================================================
-- CTE 3: Surgical Pathology Observations (linked via specimen_reference)
-- ============================================================================
-- NOTE: This CTE captures genomics/molecular data from observations table.
--       The separate v_molecular_tests view provides an alternate curated view
--       with aggregated components from the molecular_tests materialized table.
-- ============================================================================
surgical_pathology_observations AS (
    SELECT
        REPLACE(o.subject_reference, 'Patient/', '') as patient_fhir_id,
        'surgical_pathology_observation' as diagnostic_source,
        o.id as source_id,
        CAST(TRY(from_iso8601_timestamp(o.effective_date_time)) AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(o.effective_date_time AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Observation identification
        o.code_text as diagnostic_name,
        occ.code_coding_code as code,
        oid_obs.masterfile_code as coding_system_code,
        oid_obs.description as coding_system_name,

        -- Component (use code_coding_display for detailed component name)
        COALESCE(occ.code_coding_display, o.code_text) as component_name,

        -- Result value (value_string contains free text pathology results!)
        o.value_string as result_value,

        -- Test metadata
        'Surgical Pathology Lab' as test_lab,

        -- Specimen information (from observation.specimen_display and linked specimen resource)
        COALESCE(s.type_text, o.specimen_display) as specimen_types,
        s.collection_body_site_text as specimen_sites,
        CAST(TRY(from_iso8601_timestamp(s.collection_collected_date_time)) AS TIMESTAMP(3)) as specimen_collection_datetime,

        -- Procedure linkage (link via specimen → service_request → encounter → procedure)
        p.id as linked_procedure_id,
        p.code_text as linked_procedure_name,
        CAST(TRY(from_iso8601_timestamp(p.performed_date_time)) AS TIMESTAMP(3)) as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(o.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Generic categorization (LOINC/resource-based, no hardcoded features)
        CASE
            -- Use LOINC codes for categorization
            WHEN occ.code_coding_code IN ('24419-4') THEN 'Gross_Observation'
            WHEN occ.code_coding_code IN ('34574-4') THEN 'Final_Diagnosis'
            WHEN occ.code_coding_code IN ('11526-1') THEN 'Pathology_Study'

            -- Use observation code_text patterns for categorization
            WHEN LOWER(o.code_text) LIKE '%gross%' THEN 'Gross_Observation'
            WHEN LOWER(o.code_text) LIKE '%final%diagnosis%' THEN 'Final_Diagnosis'
            WHEN LOWER(o.code_text) LIKE '%genomics%interpretation%' THEN 'Genomics_Interpretation'
            WHEN LOWER(o.code_text) LIKE '%genomics%method%' THEN 'Genomics_Method'

            -- Use observation category if available
            WHEN oc.category_text = 'Laboratory' THEN 'Laboratory_Observation'
            WHEN oc.category_text = 'Imaging' THEN 'Imaging_Observation'

            -- Generic fallback
            ELSE 'Clinical_Observation'
        END as diagnostic_category,

        -- Metadata
        o.status as test_status,
        NULL as test_orderer,
        CAST(NULL AS BIGINT) as component_count

    FROM fhir_prd_db.observation o

    -- Join to specimen resource via specimen_reference
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(o.specimen_reference, 'Specimen/', '') = s.id

    -- Link specimen → service_request → procedure (to get surgery context)
    LEFT JOIN fhir_prd_db.service_request_specimen srs
        ON s.id = REPLACE(srs.specimen_reference, 'Specimen/', '')
    LEFT JOIN fhir_prd_db.service_request sr
        ON srs.service_request_id = sr.id
    LEFT JOIN fhir_prd_db.procedure p
        ON REPLACE(sr.encounter_reference, 'Encounter/', '') = REPLACE(p.encounter_reference, 'Encounter/', '')
        AND p.code_text LIKE '%SURGICAL%'

    -- Join to observation metadata tables
    LEFT JOIN fhir_prd_db.observation_code_coding occ
        ON o.id = occ.observation_id
    LEFT JOIN fhir_prd_db.observation_category oc
        ON o.id = oc.observation_id
    LEFT JOIN oid_reference oid_obs
        ON occ.code_coding_system = oid_obs.oid_uri

    -- FILTER to confirmed tumor surgery patients only
    INNER JOIN tumor_surgeries ts
        ON REPLACE(o.subject_reference, 'Patient/', '') = ts.patient_fhir_id

    WHERE o.subject_reference IS NOT NULL
      AND o.id IS NOT NULL
      AND o.specimen_reference IS NOT NULL  -- Require specimen linkage
      AND o.value_string IS NOT NULL  -- Require free text results
      -- Filter to pathology-related observations
      AND (
          LOWER(o.code_text) LIKE '%pathology%'
          OR LOWER(o.code_text) LIKE '%surgical%consult%'
          OR LOWER(o.code_text) LIKE '%genomics%'
          OR LOWER(o.code_text) LIKE '%autopsy%'
          OR LOWER(o.code_text) LIKE '%neuropathology%'
          OR LOWER(o.code_text) LIKE '%brain%gross%'
          OR LOWER(o.code_text) LIKE '%brain%final%'
          OR LOWER(occ.code_coding_display) LIKE '%pathology%'
          OR occ.code_coding_code IN ('24419-4', '34574-4', '11526-1')  -- LOINC pathology codes
      )
),

-- ============================================================================
-- CTE 5: Surgical Pathology Reports (from surgical encounters)
-- ============================================================================
surgical_pathology_narratives AS (
    SELECT
        ts.patient_fhir_id,
        'surgical_pathology_report' as diagnostic_source,
        dr.id as source_id,
        CAST(TRY(from_iso8601_timestamp(dr.effective_date_time)) AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(dr.effective_date_time AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Report identification
        dr.code_text as diagnostic_name,
        drcc.code_coding_code as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Component
        dr.code_text as component_name,

        -- Narrative content (preserved as-is for downstream analysis)
        -- Include BOTH conclusion AND URL to full report for NLP workflows
        CASE
            WHEN dr.conclusion IS NOT NULL AND drpf.presented_form_url IS NOT NULL
                THEN dr.conclusion || ' | URL: ' || drpf.presented_form_url
            WHEN dr.conclusion IS NOT NULL
                THEN dr.conclusion
            WHEN drpf.presented_form_url IS NOT NULL
                THEN 'Full report at: ' || drpf.presented_form_url
            ELSE NULL
        END as result_value,

        -- Test metadata
        'Pathology Report' as test_lab,

        -- Specimen information (from surgical_specimens if linked)
        ss.specimen_type as specimen_types,
        ss.specimen_site as specimen_sites,
        ss.collection_datetime as specimen_collection_datetime,

        -- Procedure linkage (from tumor_surgeries)
        ts.procedure_fhir_id as linked_procedure_id,
        ts.surgery_name as linked_procedure_name,
        ts.surgery_datetime as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(dr.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Generic categorization (resource type-based, no hardcoded features)
        CASE
            WHEN drcc.code_coding_code IN ('24419-4', '34574-4', '11526-1') THEN 'Pathology_Report'
            WHEN LOWER(dr.code_text) LIKE '%pathology%' THEN 'Pathology_Report'
            WHEN LOWER(dr.code_text) LIKE '%surgical%' THEN 'Surgical_Report'
            ELSE 'Diagnostic_Report'
        END as diagnostic_category,

        -- Metadata
        dr.status as test_status,
        NULL as test_orderer,
        CAST(NULL AS BIGINT) as component_count

    FROM tumor_surgeries ts
    INNER JOIN fhir_prd_db.diagnostic_report dr
        ON ts.patient_fhir_id = REPLACE(dr.subject_reference, 'Patient/', '')
        -- Temporal window: ±60 days from surgery (wider than specimens)
        AND ABS(DATE_DIFF('day', ts.surgery_date, TRY(CAST(CAST(dr.effective_date_time AS VARCHAR) AS DATE)))) <= 60

    -- Join for code information
    LEFT JOIN fhir_prd_db.diagnostic_report_code_coding drcc
        ON dr.id = drcc.diagnostic_report_id

    -- Join for presented_form URL (for NLP workflows on binary reports)
    LEFT JOIN fhir_prd_db.diagnostic_report_presented_form drpf
        ON dr.id = drpf.diagnostic_report_id

    -- LEFT JOIN to surgical_specimens (if available for specimen details)
    LEFT JOIN surgical_specimens ss
        ON ts.patient_fhir_id = ss.patient_fhir_id
        AND ABS(DATE_DIFF('day',
            TRY(CAST(CAST(dr.effective_date_time AS VARCHAR) AS DATE)),
            ss.surgery_date
        )) <= 7

    WHERE dr.subject_reference IS NOT NULL
      AND (dr.conclusion IS NOT NULL OR drpf.presented_form_url IS NOT NULL)
      -- Filter to pathology-related reports
      AND (
          LOWER(dr.code_text) LIKE '%pathology%'
          OR LOWER(dr.code_text) LIKE '%surgical%'
          OR LOWER(dr.code_text) LIKE '%biopsy%'
          OR LOWER(dr.code_text) LIKE '%specimen%'
          OR drcc.code_coding_code IN ('24419-4', '34574-4', '11526-1')  -- LOINC pathology codes
      )
      -- Exclude reports already captured in molecular_tests
      AND NOT EXISTS (
          SELECT 1 FROM fhir_prd_db.molecular_tests mt
          WHERE mt.result_diagnostic_report_id = dr.id
      )
),

-- ============================================================================
-- CTE 6: Pathology Document References (for NLP workflows, including send-outs)
-- ============================================================================
-- NOTE: Captures ALL document_reference resources linked to surgical encounters
--       for NLP processing. Includes send-out pathology analyses, external reports, etc.
-- ============================================================================
pathology_document_references AS (
    SELECT
        ts.patient_fhir_id,
        'pathology_document' as diagnostic_source,
        dref.id as source_id,
        CAST(TRY(from_iso8601_timestamp(dref.date)) AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(dref.date AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Document identification
        dref.description as diagnostic_name,
        NULL as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Component
        dref.type_text as component_name,

        -- Document URL for NLP workflows (CRITICAL for send-out analyses)
        CASE
            WHEN drefc.content_attachment_url IS NOT NULL
                THEN 'Document: ' || drefc.content_attachment_url ||
                     ' | Type: ' || COALESCE(drefc.content_attachment_content_type, 'unknown') ||
                     ' | Title: ' || COALESCE(drefc.content_attachment_title, dref.description)
            ELSE dref.description
        END as result_value,

        -- Test metadata
        'Document Repository' as test_lab,

        -- Specimen information (try to link via surgical_specimens if available)
        ss.specimen_type as specimen_types,
        ss.specimen_site as specimen_sites,
        ss.collection_datetime as specimen_collection_datetime,

        -- Procedure linkage (from tumor_surgeries)
        ts.procedure_fhir_id as linked_procedure_id,
        ts.surgery_name as linked_procedure_name,
        ts.surgery_datetime as linked_procedure_datetime,

        -- Encounter linkage (via document_reference_context_encounter)
        drce.context_encounter_reference as encounter_id,

        -- Generic categorization
        CASE
            WHEN drefc.content_attachment_content_type LIKE '%pdf%' THEN 'PDF_Document'
            WHEN drefc.content_attachment_content_type LIKE '%image%' THEN 'Image_Document'
            WHEN drefc.content_attachment_content_type LIKE '%text%' THEN 'Text_Document'
            ELSE 'Document_Reference'
        END as diagnostic_category,

        -- Metadata
        dref.doc_status as test_status,
        NULL as test_orderer,
        CAST(NULL AS BIGINT) as component_count

    FROM tumor_surgeries ts
    INNER JOIN fhir_prd_db.document_reference dref
        ON ts.patient_fhir_id = REPLACE(dref.subject_reference, 'Patient/', '')
        -- NO temporal window - send-out analyses can occur months/years after surgery

    -- Join for document content/URL (REQUIRED for NLP processing)
    LEFT JOIN fhir_prd_db.document_reference_content drefc
        ON dref.id = drefc.document_reference_id

    -- Join for encounter linkage
    LEFT JOIN fhir_prd_db.document_reference_context_encounter drce
        ON dref.id = drce.document_reference_id

    -- LEFT JOIN to surgical_specimens (if available)
    LEFT JOIN surgical_specimens ss
        ON ts.patient_fhir_id = ss.patient_fhir_id
        AND ABS(DATE_DIFF('day',
            TRY(CAST(CAST(dref.date AS VARCHAR) AS DATE)),
            ss.surgery_date
        )) <= 7

    WHERE dref.subject_reference IS NOT NULL
      AND (dref.description IS NOT NULL OR drefc.content_attachment_url IS NOT NULL)
      -- Capture ALL pathology/diagnostic documents (not just keyword-filtered)
      -- Include send-out analyses which may not have "pathology" in description
      AND (
          LOWER(dref.description) LIKE '%pathology%'
          OR LOWER(dref.description) LIKE '%surgical%'
          OR LOWER(dref.description) LIKE '%biopsy%'
          OR LOWER(dref.description) LIKE '%specimen%'
          OR LOWER(dref.description) LIKE '%diagnostic%'
          OR LOWER(dref.description) LIKE '%genomic%'
          OR LOWER(dref.description) LIKE '%molecular%'
          OR LOWER(dref.type_text) LIKE '%pathology%'
          OR LOWER(dref.type_text) LIKE '%surgical%'
          OR LOWER(dref.type_text) LIKE '%diagnostic%'
          OR drefc.content_attachment_url IS NOT NULL  -- Capture ALL documents with URLs
      )
),

-- ============================================================================
-- CTE 7: Problem List Diagnoses (patient-level ICD-10/SNOMED codes)
-- ============================================================================
problem_list_diagnoses AS (
    SELECT
        ts.patient_fhir_id,
        'problem_list_diagnosis' as diagnostic_source,
        c.id as source_id,
        CAST(TRY(from_iso8601_timestamp(c.onset_date_time)) AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(c.onset_date_time AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Diagnosis identification
        c.code_text as diagnostic_name,
        cc.code_coding_code as code,  -- ICD-10 or SNOMED code
        NULL as coding_system_code,
        cc.code_coding_system as coding_system_name,  -- Will be ICD-10 or SNOMED URI

        -- Component (condition category)
        COALESCE(ccat.category_text, 'Unknown') as component_name,

        -- Result value (combine code display and verification status)
        CASE
            WHEN cc.code_coding_display IS NOT NULL AND c.verification_status_text IS NOT NULL
                THEN cc.code_coding_display || ' | Status: ' || c.verification_status_text
            WHEN cc.code_coding_display IS NOT NULL
                THEN cc.code_coding_display
            ELSE c.code_text
        END as result_value,

        -- Test metadata
        'Problem List' as test_lab,

        -- No specimen for problem list diagnoses (patient-level, not specimen-level)
        NULL as specimen_types,
        NULL as specimen_sites,
        NULL as specimen_collection_datetime,

        -- Procedure linkage (to surgery)
        ts.procedure_fhir_id as linked_procedure_id,
        ts.surgery_name as linked_procedure_name,
        ts.surgery_datetime as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(c.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Generic categorization based on ICD-10/SNOMED code
        CASE
            WHEN cc.code_coding_system LIKE '%icd-10%' THEN 'ICD10_Diagnosis'
            WHEN cc.code_coding_system LIKE '%snomed%' THEN 'SNOMED_Diagnosis'
            WHEN ccat.category_text = 'problem-list-item' THEN 'Problem_List_Item'
            WHEN ccat.category_text = 'encounter-diagnosis' THEN 'Encounter_Diagnosis'
            ELSE 'Clinical_Diagnosis'
        END as diagnostic_category,

        -- Metadata
        c.clinical_status_text as test_status,
        c.recorder_display as test_orderer,
        CAST(NULL AS BIGINT) as component_count

    FROM tumor_surgeries ts
    INNER JOIN fhir_prd_db.condition c
        ON ts.patient_fhir_id = REPLACE(c.subject_reference, 'Patient/', '')
        -- Link diagnoses within ±180 days of surgery (may predate or follow surgery)
        AND ABS(DATE_DIFF('day', ts.surgery_date, TRY(CAST(CAST(c.onset_date_time AS VARCHAR) AS DATE)))) <= 180

    -- Join for ICD-10/SNOMED codes
    LEFT JOIN fhir_prd_db.condition_code_coding cc
        ON c.id = cc.condition_id

    -- Join for condition category (problem-list-item vs encounter-diagnosis)
    LEFT JOIN fhir_prd_db.condition_category ccat
        ON c.id = ccat.condition_id

    WHERE c.subject_reference IS NOT NULL
      AND c.id IS NOT NULL

      -- Filter to CNS/brain tumor-related diagnoses
      AND (
          -- ICD-10 C-codes for brain tumors (C70-C72, C79.3x)
          cc.code_coding_code LIKE 'C70%'
          OR cc.code_coding_code LIKE 'C71%'
          OR cc.code_coding_code LIKE 'C72%'
          OR cc.code_coding_code LIKE 'C79.3%'

          -- ICD-10 D-codes for benign brain tumors (D32-D33, D43)
          OR cc.code_coding_code LIKE 'D32%'
          OR cc.code_coding_code LIKE 'D33%'
          OR cc.code_coding_code LIKE 'D43%'

          -- SNOMED codes for brain/CNS neoplasms
          OR LOWER(c.code_text) LIKE '%brain%tumor%'
          OR LOWER(c.code_text) LIKE '%brain%neoplasm%'
          OR LOWER(c.code_text) LIKE '%glioma%'
          OR LOWER(c.code_text) LIKE '%glioblastoma%'
          OR LOWER(c.code_text) LIKE '%medulloblastoma%'
          OR LOWER(c.code_text) LIKE '%ependymoma%'
          OR LOWER(c.code_text) LIKE '%astrocytoma%'
          OR LOWER(c.code_text) LIKE '%oligodendroglioma%'
          OR LOWER(c.code_text) LIKE '%craniopharyngioma%'
          OR LOWER(c.code_text) LIKE '%meningioma%'
          OR LOWER(c.code_text) LIKE '%cns%tumor%'
          OR LOWER(c.code_text) LIKE '%central nervous system%neoplasm%'
      )
),

-- ============================================================================
-- CTE 6: Unified Pathology Diagnostics
-- ============================================================================
-- NOTE: Removed molecular_diagnostics to avoid duplication with observations.
--       Use v_molecular_tests as a separate curated molecular testing view.
-- ============================================================================
unified_diagnostics AS (
    SELECT * FROM surgical_pathology_observations
    UNION ALL
    SELECT * FROM surgical_pathology_narratives
    UNION ALL
    SELECT * FROM pathology_document_references
    UNION ALL
    SELECT * FROM problem_list_diagnoses
)

-- ============================================================================
-- FINAL SELECT: All surgery-linked pathology diagnostics
-- ============================================================================
SELECT
    ud.patient_fhir_id,
    ud.diagnostic_source,
    ud.source_id,
    ud.diagnostic_datetime,
    ud.diagnostic_date,

    -- Diagnostic details (preserved as-is, no interpretation)
    ud.diagnostic_name,
    ud.code,
    ud.coding_system_code,
    ud.coding_system_name,
    ud.component_name,
    ud.result_value,  -- Raw result value for downstream analysis
    ud.diagnostic_category,  -- Generic category based on FHIR resource type

    -- Specimen details
    ud.specimen_types,
    ud.specimen_sites,
    ud.specimen_collection_datetime,

    -- Test metadata
    ud.test_lab,
    ud.test_status,
    ud.test_orderer,
    ud.component_count,

    -- Procedure linkage
    ud.linked_procedure_id,
    ud.linked_procedure_name,
    ud.linked_procedure_datetime,
    TRY(DATE_DIFF('day', CAST(ud.linked_procedure_datetime AS DATE), ud.diagnostic_date)) as days_from_procedure,

    -- Encounter
    ud.encounter_id

FROM unified_diagnostics ud

WHERE ud.patient_fhir_id IS NOT NULL

ORDER BY ud.patient_fhir_id, ud.diagnostic_datetime, ud.diagnostic_category;
