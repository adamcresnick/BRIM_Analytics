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
-- Data Sources (5 surgery-linked sources):
--   1. molecular_tests/molecular_test_results (DGD lab, within 1 year of surgery)
--   2. observation (linked to surgical specimens via specimen_reference)
--   3. diagnostic_report (surgical encounters, ±30 days, includes presented_form URLs)
--   4. document_reference (pathology documents, ±60 days, includes content URLs)
--   5. condition (problem_list ICD-10/SNOMED diagnoses, ±180 days, patient-level)
--
-- Temporal Windows:
--   - Surgical specimens: ±7 days from surgery date
--   - Molecular tests: ±365 days from surgery date
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
        TRY(CAST(s.collection_collected_date_time AS TIMESTAMP(3))) as collection_datetime,
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
-- CTE 3: Molecular Diagnostics (from molecular_tests, surgery-linked)
-- ============================================================================
molecular_diagnostics AS (
    SELECT
        mt.patient_id as patient_fhir_id,
        'molecular_test' as diagnostic_source,
        mt.test_id as source_id,
        CAST(mt.result_datetime AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(mt.result_datetime AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Test identification
        mt.lab_test_name as diagnostic_name,
        NULL as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Test details
        mtr.test_component as component_name,
        mtr.test_result_narrative as result_value,

        -- Test metadata
        mt.dgd_id as test_identifier,
        'DGD' as test_lab,

        -- Specimen information
        vmt.mt_specimen_types as specimen_types,
        vmt.mt_specimen_sites as specimen_sites,
        vmt.mt_specimen_collection_date as specimen_collection_datetime,

        -- Procedure linkage
        vmt.mt_procedure_id as linked_procedure_id,
        vmt.mt_procedure_name as linked_procedure_name,
        vmt.mt_procedure_date as linked_procedure_datetime,

        -- Encounter linkage
        vmt.mt_encounter_id as encounter_id,

        -- Generic categorization (LOINC-based, no hardcoded features)
        CASE
            WHEN occ.code_coding_code IN ('24419-4', '34574-4', '11526-1') THEN 'Pathology_Report'
            WHEN LOWER(mt.lab_test_name) LIKE '%panel%' OR LOWER(mt.lab_test_name) LIKE '%profile%' THEN 'Test_Panel'
            WHEN LOWER(mt.lab_test_name) LIKE '%sequencing%' THEN 'Sequencing'
            ELSE 'Molecular_Test'
        END as diagnostic_category,

        -- Metadata
        mt.lab_test_status as test_status,
        mt.lab_test_requester as test_orderer,
        vmt.mtr_component_count as component_count

    FROM fhir_prd_db.molecular_tests mt
    INNER JOIN fhir_prd_db.molecular_test_results mtr
        ON mt.test_id = mtr.test_id
    LEFT JOIN fhir_prd_db.v_molecular_tests vmt
        ON mt.test_id = vmt.mt_test_id

    -- ANCHOR to tumor surgeries (within 1 year)
    INNER JOIN tumor_surgeries ts
        ON mt.patient_id = ts.patient_fhir_id
        AND ABS(DATE_DIFF('day', ts.surgery_date, TRY(CAST(CAST(mt.result_datetime AS VARCHAR) AS DATE)))) <= 365

    -- Join to observation_code_coding for LOINC codes (if available)
    LEFT JOIN fhir_prd_db.observation_code_coding occ
        ON mt.test_id = occ.observation_id

    WHERE mt.patient_id IS NOT NULL
),

-- ============================================================================
-- CTE 4: Surgical Pathology Observations (from surgical specimens ONLY)
-- ============================================================================
surgical_pathology_observations AS (
    SELECT
        ss.patient_fhir_id,
        'surgical_pathology_observation' as diagnostic_source,
        o.id as source_id,
        CAST(o.effective_date_time AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(o.effective_date_time AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Observation identification
        o.code_text as diagnostic_name,
        occ.code_coding_code as code,
        oid_obs.masterfile_code as coding_system_code,
        oid_obs.description as coding_system_name,

        -- Component
        o.code_text as component_name,

        -- Result value (preserved as-is)
        COALESCE(o.value_string, o.value_codeable_concept_text, oi.interpretation_text) as result_value,

        -- Test metadata
        NULL as test_identifier,
        'Surgical Pathology Lab' as test_lab,

        -- Specimen information
        ss.specimen_type as specimen_types,
        ss.specimen_site as specimen_sites,
        ss.collection_datetime as specimen_collection_datetime,

        -- Procedure linkage
        ss.procedure_fhir_id as linked_procedure_id,
        NULL as linked_procedure_name,
        ss.surgery_datetime as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(o.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Generic categorization (LOINC/resource-based, no hardcoded features)
        CASE
            -- Use LOINC codes for categorization
            WHEN occ.code_coding_code IN ('24419-4') THEN 'Gross_Observation'
            WHEN occ.code_coding_code IN ('34574-4') THEN 'Final_Diagnosis'
            WHEN occ.code_coding_code IN ('11526-1') THEN 'Pathology_Study'

            -- Use observation category if available
            WHEN oc.category_text = 'Laboratory' THEN 'Laboratory_Observation'
            WHEN oc.category_text = 'Imaging' THEN 'Imaging_Observation'

            -- Generic fallback
            ELSE 'Clinical_Observation'
        END as diagnostic_category,

        -- Metadata
        o.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM surgical_specimens ss
    INNER JOIN fhir_prd_db.observation o
        ON REPLACE(o.specimen_reference, 'Specimen/', '') = ss.specimen_id

    -- Join to observation tables for metadata
    LEFT JOIN fhir_prd_db.observation_code_coding occ
        ON o.id = occ.observation_id
    LEFT JOIN fhir_prd_db.observation_interpretation oi
        ON o.id = oi.observation_id
    LEFT JOIN fhir_prd_db.observation_category oc
        ON o.id = oc.observation_id
    LEFT JOIN oid_reference oid_obs
        ON occ.code_coding_system = oid_obs.oid_uri

    WHERE o.subject_reference IS NOT NULL
      AND o.id IS NOT NULL
),

-- ============================================================================
-- CTE 5: Surgical Pathology Reports (from surgical encounters)
-- ============================================================================
surgical_pathology_narratives AS (
    SELECT
        ss.patient_fhir_id,
        'surgical_pathology_report' as diagnostic_source,
        dr.id as source_id,
        CAST(dr.effective_date_time AS TIMESTAMP(3)) as diagnostic_datetime,
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
        NULL as test_identifier,
        'Pathology Report' as test_lab,

        -- Specimen information
        ss.specimen_type as specimen_types,
        ss.specimen_site as specimen_sites,
        ss.collection_datetime as specimen_collection_datetime,

        -- Procedure linkage
        ss.procedure_fhir_id as linked_procedure_id,
        NULL as linked_procedure_name,
        ss.surgery_datetime as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(dr.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Generic categorization (resource type-based, no hardcoded features)
        CASE
            WHEN dr.resource_type = 'DiagnosticReport' THEN 'Diagnostic_Report'
            WHEN drcc.code_coding_code IN ('24419-4', '34574-4', '11526-1') THEN 'Pathology_Report'
            ELSE 'Clinical_Report'
        END as diagnostic_category,

        -- Metadata
        dr.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM surgical_specimens ss
    INNER JOIN fhir_prd_db.diagnostic_report dr
        ON ss.patient_fhir_id = REPLACE(dr.subject_reference, 'Patient/', '')
        AND ABS(DATE_DIFF('day', ss.surgery_date, TRY(CAST(CAST(dr.effective_date_time AS VARCHAR) AS DATE)))) <= 30

    -- Join for code information
    LEFT JOIN fhir_prd_db.diagnostic_report_code_coding drcc
        ON dr.id = drcc.diagnostic_report_id

    -- Join for presented_form URL (for NLP workflows on binary reports)
    LEFT JOIN fhir_prd_db.diagnostic_report_presented_form drpf
        ON dr.id = drpf.diagnostic_report_id

    WHERE dr.subject_reference IS NOT NULL
      AND (dr.conclusion IS NOT NULL OR drpf.presented_form_url IS NOT NULL)

      -- Exclude reports already captured in molecular_tests
      AND NOT EXISTS (
          SELECT 1 FROM fhir_prd_db.molecular_tests mt
          WHERE mt.result_diagnostic_report_id = dr.id
      )
),

-- ============================================================================
-- CTE 6: Pathology Document References (for NLP workflows)
-- ============================================================================
pathology_document_references AS (
    SELECT
        ss.patient_fhir_id,
        'pathology_document' as diagnostic_source,
        dref.id as source_id,
        CAST(dref.date AS TIMESTAMP(3)) as diagnostic_datetime,
        TRY(CAST(CAST(dref.date AS VARCHAR) AS DATE)) as diagnostic_date,

        -- Document identification
        dref.description as diagnostic_name,
        NULL as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Component
        dref.type_text as component_name,

        -- Document URL for NLP workflows
        CASE
            WHEN drefc.content_attachment_url IS NOT NULL
                THEN 'Document: ' || drefc.content_attachment_url ||
                     ' | Type: ' || COALESCE(drefc.content_attachment_content_type, 'unknown') ||
                     ' | Title: ' || COALESCE(drefc.content_attachment_title, dref.description)
            ELSE dref.description
        END as result_value,

        -- Test metadata
        NULL as test_identifier,
        'Document Repository' as test_lab,

        -- Specimen information
        ss.specimen_type as specimen_types,
        ss.specimen_site as specimen_sites,
        ss.collection_datetime as specimen_collection_datetime,

        -- Procedure linkage
        ss.procedure_fhir_id as linked_procedure_id,
        NULL as linked_procedure_name,
        ss.surgery_datetime as linked_procedure_datetime,

        -- Encounter linkage (would require additional JOIN to document_reference_context_encounter)
        NULL as encounter_id,

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
        NULL as component_count

    FROM surgical_specimens ss
    INNER JOIN fhir_prd_db.document_reference dref
        ON ss.patient_fhir_id = REPLACE(dref.subject_reference, 'Patient/', '')
        AND ABS(DATE_DIFF('day', ss.surgery_date, TRY(CAST(CAST(dref.date AS VARCHAR) AS DATE)))) <= 60

    -- Join for document content/URL
    LEFT JOIN fhir_prd_db.document_reference_content drefc
        ON dref.id = drefc.document_reference_id

    WHERE dref.subject_reference IS NOT NULL
      AND (dref.description IS NOT NULL OR drefc.content_attachment_url IS NOT NULL)

      -- Filter to pathology-related documents
      AND (
          LOWER(dref.description) LIKE '%pathology%'
          OR LOWER(dref.description) LIKE '%surgical%'
          OR LOWER(dref.description) LIKE '%biopsy%'
          OR LOWER(dref.description) LIKE '%specimen%'
          OR LOWER(dref.type_text) LIKE '%pathology%'
          OR LOWER(dref.type_text) LIKE '%surgical%'
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
        TRY(CAST(c.onset_date_time AS TIMESTAMP(3))) as diagnostic_datetime,
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
        NULL as test_identifier,
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
        NULL as component_count

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
-- CTE 8: Unified Pathology Diagnostics
-- ============================================================================
unified_diagnostics AS (
    SELECT * FROM molecular_diagnostics
    UNION ALL
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
    ud.test_identifier,
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
