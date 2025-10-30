-- ============================================================================
-- VIEW: v_pathology_diagnostics
-- ============================================================================
-- PURPOSE: Comprehensive pathology and diagnostic information for tumor assessment
--
-- COMBINES:
--   1. Molecular testing (from molecular_tests/molecular_test_results)
--   2. Surgical pathology observations (histology, grade, IHC)
--   3. Procedure-linked pathology (frozen section, biopsies)
--   4. Specimen-linked diagnostics
--   5. ALL narrative text from diagnostic reports (conclusion, full report)
--   6. ALL care plan descriptions (complete narrative capture)
--   7. ALL procedure notes and outcomes (complete narrative capture)
--
-- AUGMENTS: problem_list_diagnoses with detailed pathology findings
--
-- USE CASE: Complete diagnostic profile for tumor characterization beyond
--           diagnosis codes alone
--
-- DESIGN PHILOSOPHY: **INCLUSIVE, NOT EXCLUSIVE**
--   - Captures ALL narrative text from relevant FHIR resources
--   - Does NOT filter based on keyword patterns (too restrictive, loses data)
--   - Pattern matching used ONLY for molecular marker EXTRACTION (adds value)
--   - Pattern matching NOT used for filtering (which would exclude important data)
--   - Downstream analysts can filter results as needed for specific use cases
--
-- DATETIME STANDARDIZATION: All datetime fields cast to TIMESTAMP(3)
-- OID DECODING: Included for observation and procedure coding systems
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_pathology_diagnostics AS

WITH
-- ============================================================================
-- CTE 1: OID Reference for Decoding
-- ============================================================================
oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),

-- ============================================================================
-- CTE 2: Molecular Testing Results (from materialized tables)
-- ============================================================================
molecular_diagnostics AS (
    SELECT
        mt.patient_id as patient_fhir_id,
        'molecular_test' as diagnostic_source,
        mt.test_id as source_id,
        CAST(mt.result_datetime AS TIMESTAMP(3)) as diagnostic_datetime,
        CAST(mt.result_datetime AS DATE) as diagnostic_date,

        -- Test identification
        mt.lab_test_name as diagnostic_name,
        NULL as code,  -- No coding for molecular tests (Epic-specific)
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Test details from molecular_test_results
        mtr.test_component as component_name,
        mtr.test_result_narrative as result_value,

        -- Test metadata
        mt.dgd_id as test_identifier,
        'DGD' as test_lab,  -- Division of Genomic Diagnostics

        -- Specimen information from v_molecular_tests
        vmt.mt_specimen_types as specimen_types,
        vmt.mt_specimen_sites as specimen_sites,
        vmt.mt_specimen_collection_date as specimen_collection_datetime,

        -- Procedure linkage
        vmt.mt_procedure_id as linked_procedure_id,
        vmt.mt_procedure_name as linked_procedure_name,
        vmt.mt_procedure_date as linked_procedure_datetime,

        -- Encounter linkage
        vmt.mt_encounter_id as encounter_id,

        -- Classification
        CASE
            WHEN LOWER(mtr.test_component) LIKE '%idh%' THEN 'IDH_Mutation'
            WHEN LOWER(mtr.test_component) LIKE '%mgmt%' THEN 'MGMT_Methylation'
            WHEN LOWER(mtr.test_component) LIKE '%1p%19q%' OR LOWER(mtr.test_component) LIKE '%codeletion%' THEN '1p19q_Codeletion'
            WHEN LOWER(mtr.test_component) LIKE '%braf%' THEN 'BRAF_Mutation'
            WHEN LOWER(mtr.test_component) LIKE '%tp53%' OR LOWER(mtr.test_component) LIKE '%p53%' THEN 'TP53_Mutation'
            WHEN LOWER(mtr.test_component) LIKE '%h3%' OR LOWER(mtr.test_component) LIKE '%k27%' THEN 'H3_K27M_Mutation'
            WHEN LOWER(mtr.test_component) LIKE '%tert%' THEN 'TERT_Promoter'
            WHEN LOWER(mtr.test_component) LIKE '%atrx%' THEN 'ATRX_Loss'
            WHEN LOWER(mtr.test_component) LIKE '%egfr%' THEN 'EGFR_Mutation'
            WHEN LOWER(mtr.test_component) LIKE '%ki-67%' OR LOWER(mtr.test_component) LIKE '%ki67%' OR LOWER(mtr.test_component) LIKE '%proliferation%' THEN 'Ki67_Proliferation'
            ELSE 'Other_Molecular'
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

    WHERE mt.patient_id IS NOT NULL
),

-- ============================================================================
-- CTE 3: Pathology Observations (histology, IHC, grade)
-- ============================================================================
pathology_observations AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        'pathology_observation' as diagnostic_source,
        o.id as source_id,
        CAST(o.effective_date_time AS TIMESTAMP(3)) as diagnostic_datetime,
        CAST(o.effective_date_time AS DATE) as diagnostic_date,

        -- Observation identification
        o.code_text as diagnostic_name,
        occ.code_coding_code as code,
        oid_obs.masterfile_code as coding_system_code,
        oid_obs.description as coding_system_name,

        -- Component name (if part of panel)
        o.code_text as component_name,

        -- Result values
        COALESCE(o.value_string, o.value_codeable_concept_text, oi.interpretation_text) as result_value,

        -- Test metadata
        NULL as test_identifier,
        'Clinical Lab' as test_lab,

        -- Specimen information
        s.type_text as specimen_types,
        s.collection_body_site_text as specimen_sites,
        CAST(s.collection_collected_date_time AS TIMESTAMP(3)) as specimen_collection_datetime,

        -- Procedure linkage (find procedures in same encounter)
        p.id as linked_procedure_id,
        p.code_text as linked_procedure_name,
        CAST(p.performed_date_time AS TIMESTAMP(3)) as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(o.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Classification
        CASE
            WHEN LOWER(o.code_text) LIKE '%idh%' THEN 'IDH_Mutation'
            WHEN LOWER(o.code_text) LIKE '%mgmt%' THEN 'MGMT_Methylation'
            WHEN LOWER(o.code_text) LIKE '%1p%19q%' OR LOWER(o.code_text) LIKE '%codeletion%' THEN '1p19q_Codeletion'
            WHEN LOWER(o.code_text) LIKE '%braf%' THEN 'BRAF_Mutation'
            WHEN LOWER(o.code_text) LIKE '%tp53%' OR LOWER(o.code_text) LIKE '%p53%' THEN 'TP53_Mutation'
            WHEN LOWER(o.code_text) LIKE '%h3%' OR LOWER(o.code_text) LIKE '%k27%' THEN 'H3_K27M_Mutation'
            WHEN LOWER(o.code_text) LIKE '%ki-67%' OR LOWER(o.code_text) LIKE '%ki67%' OR LOWER(o.code_text) LIKE '%proliferation%' THEN 'Ki67_Proliferation'
            WHEN LOWER(o.code_text) LIKE '%who grade%' OR LOWER(o.code_text) LIKE '%tumor grade%' OR LOWER(o.code_text) LIKE '%histologic grade%' THEN 'WHO_Grade'
            WHEN LOWER(o.code_text) LIKE '%histology%' OR LOWER(o.code_text) LIKE '%histologic type%' THEN 'Histology'
            WHEN LOWER(o.code_text) LIKE '%gfap%' THEN 'IHC_GFAP'
            WHEN LOWER(o.code_text) LIKE '%olig2%' THEN 'IHC_OLIG2'
            WHEN LOWER(o.code_text) LIKE '%synaptophysin%' THEN 'IHC_Synaptophysin'
            WHEN LOWER(o.code_text) LIKE '%neun%' THEN 'IHC_NeuN'
            WHEN LOWER(o.code_text) LIKE '%immunohistochemistry%' OR LOWER(o.code_text) LIKE '%ihc%' THEN 'IHC_Other'
            ELSE 'Other_Pathology'
        END as diagnostic_category,

        -- Metadata
        o.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_code_coding occ
        ON o.id = occ.observation_id
    LEFT JOIN fhir_prd_db.observation_interpretation oi
        ON o.id = oi.observation_id
    LEFT JOIN oid_reference oid_obs
        ON occ.code_coding_system = oid_obs.oid_uri
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(o.specimen_reference, 'Specimen/', '') = s.id
    LEFT JOIN fhir_prd_db.procedure p
        ON REPLACE(o.encounter_reference, 'Encounter/', '') = REPLACE(p.encounter_reference, 'Encounter/', '')
        AND o.subject_reference = p.subject_reference
        AND (LOWER(p.code_text) LIKE '%surgical%'
            OR LOWER(p.code_text) LIKE '%resection%'
            OR LOWER(p.code_text) LIKE '%biopsy%'
            OR LOWER(p.code_text) LIKE '%craniotomy%')

    WHERE
        -- Filter to pathology-related observations
        (LOWER(o.code_text) LIKE '%pathology%'
        OR LOWER(o.code_text) LIKE '%histology%'
        OR LOWER(o.code_text) LIKE '%histologic%'
        OR LOWER(o.code_text) LIKE '%who grade%'
        OR LOWER(o.code_text) LIKE '%tumor grade%'
        OR LOWER(o.code_text) LIKE '%idh%'
        OR LOWER(o.code_text) LIKE '%mgmt%'
        OR LOWER(o.code_text) LIKE '%1p%19q%'
        OR LOWER(o.code_text) LIKE '%chromosome%'
        OR LOWER(o.code_text) LIKE '%molecular%'
        OR LOWER(o.code_text) LIKE '%genetic%'
        OR LOWER(o.code_text) LIKE '%mutation%'
        OR LOWER(o.code_text) LIKE '%methylation%'
        OR LOWER(o.code_text) LIKE '%immunohistochemistry%'
        OR LOWER(o.code_text) LIKE '%ihc%'
        OR LOWER(o.code_text) LIKE '%ki-67%'
        OR LOWER(o.code_text) LIKE '%ki67%'
        OR LOWER(o.code_text) LIKE '%gfap%'
        OR LOWER(o.code_text) LIKE '%olig2%'
        OR LOWER(o.code_text) LIKE '%braf%'
        OR LOWER(o.code_text) LIKE '%tp53%'
        OR LOWER(o.code_text) LIKE '%p53%'
        OR LOWER(o.code_text) LIKE '%h3%k27%'
        OR LOWER(o.code_text) LIKE '%tert%'
        OR LOWER(o.code_text) LIKE '%atrx%'
        OR LOWER(o.code_text) LIKE '%egfr%')

        AND o.subject_reference IS NOT NULL
),

-- ============================================================================
-- CTE 4: Pathology Procedures (biopsies, frozen sections, specimen processing)
-- ============================================================================
pathology_procedures AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        'pathology_procedure' as diagnostic_source,
        p.id as source_id,
        CAST(p.performed_date_time AS TIMESTAMP(3)) as diagnostic_datetime,
        CAST(p.performed_date_time AS DATE) as diagnostic_date,

        -- Procedure identification
        p.code_text as diagnostic_name,
        pcc.code_coding_code as code,
        oid_proc.masterfile_code as coding_system_code,
        oid_proc.description as coding_system_name,

        -- Component name
        p.code_text as component_name,

        -- Result/outcome
        p.outcome_text as result_value,

        -- Test metadata
        NULL as test_identifier,
        'Pathology Lab' as test_lab,

        -- Specimen information (linked through encounter)
        s.type_text as specimen_types,
        s.collection_body_site_text as specimen_sites,
        CAST(s.collection_collected_date_time AS TIMESTAMP(3)) as specimen_collection_datetime,

        -- Self-reference for procedures
        p.id as linked_procedure_id,
        p.code_text as linked_procedure_name,
        CAST(p.performed_date_time AS TIMESTAMP(3)) as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(p.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Classification
        CASE
            WHEN LOWER(p.code_text) LIKE '%frozen section%' THEN 'Frozen_Section'
            WHEN LOWER(p.code_text) LIKE '%biopsy%' AND LOWER(p.code_text) LIKE '%brain%' THEN 'Brain_Biopsy'
            WHEN LOWER(p.code_text) LIKE '%biopsy%' THEN 'Biopsy_Other'
            WHEN LOWER(p.code_text) LIKE '%surgical pathology%' THEN 'Surgical_Pathology'
            WHEN LOWER(p.code_text) LIKE '%specimen%' THEN 'Specimen_Processing'
            WHEN pcc.code_coding_code BETWEEN '88300' AND '88309' THEN 'Surgical_Pathology'
            WHEN pcc.code_coding_code BETWEEN '88331' AND '88334' THEN 'Frozen_Section'
            WHEN pcc.code_coding_code IN ('61140', '61750', '61751', '62269') THEN 'CNS_Biopsy'
            ELSE 'Other_Procedure'
        END as diagnostic_category,

        -- Metadata
        p.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pcc
        ON p.id = pcc.procedure_id
    LEFT JOIN oid_reference oid_proc
        ON pcc.code_coding_system = oid_proc.oid_uri
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(p.encounter_reference, 'Encounter/', '') = REPLACE(s.subject_reference, 'Patient/', '')
        -- Linking specimens to procedures via encounter is approximate

    WHERE
        -- Filter to pathology-related procedures
        (LOWER(p.code_text) LIKE '%biopsy%'
        OR LOWER(p.code_text) LIKE '%pathology%'
        OR LOWER(p.code_text) LIKE '%frozen section%'
        OR LOWER(p.code_text) LIKE '%frozen%'
        OR LOWER(p.code_text) LIKE '%specimen%'
        OR LOWER(p.code_text) LIKE '%tissue exam%'

        -- Pathology CPT codes
        OR pcc.code_coding_code BETWEEN '88000' AND '88099'  -- Pathology consultation
        OR pcc.code_coding_code BETWEEN '88300' AND '88399'  -- Surgical pathology
        OR pcc.code_coding_code BETWEEN '88400' AND '88499'  -- In vivo procedures

        -- Brain biopsy CPT codes
        OR pcc.code_coding_code IN ('61140', '61750', '61751', '62269'))

        AND p.subject_reference IS NOT NULL
),

-- ============================================================================
-- CTE 5: Pathology Narrative Reports (free-text from FHIR resources)
-- ============================================================================
pathology_narratives AS (
    SELECT
        dr.subject_reference as patient_fhir_id,
        'pathology_narrative' as diagnostic_source,
        dr.id as source_id,
        CAST(dr.effective_date_time AS TIMESTAMP(3)) as diagnostic_datetime,
        CAST(dr.effective_date_time AS DATE) as diagnostic_date,

        -- Report identification
        dr.code_text as diagnostic_name,
        drcc.code_coding_code as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Narrative content (primary value)
        dr.conclusion as result_value,

        -- Component name
        dr.code_text as component_name,

        -- Specimen information (if linked)
        s.type_text as specimen_types,
        s.collection_body_site_text as specimen_sites,
        CAST(s.collection_collected_date_time AS TIMESTAMP(3)) as specimen_collection_datetime,

        -- Procedure linkage (via encounter or based_on)
        p.id as linked_procedure_id,
        p.code_text as linked_procedure_name,
        CAST(p.performed_date_time AS TIMESTAMP(3)) as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(dr.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Test identifier (from based_on service request)
        sri.identifier_value as test_identifier,
        'Pathology Report' as test_lab,

        -- Classification based on report type
        CASE
            WHEN LOWER(dr.code_text) LIKE '%surgical pathology%' THEN 'Surgical_Pathology_Report'
            WHEN LOWER(dr.code_text) LIKE '%frozen section%' THEN 'Frozen_Section_Report'
            WHEN LOWER(dr.code_text) LIKE '%cytology%' THEN 'Cytology_Report'
            WHEN LOWER(dr.code_text) LIKE '%molecular%' OR LOWER(dr.code_text) LIKE '%genomic%' THEN 'Molecular_Report'
            WHEN LOWER(dr.code_text) LIKE '%immunohistochemistry%' OR LOWER(dr.code_text) LIKE '%ihc%' THEN 'IHC_Report'
            ELSE 'Pathology_Report_Other'
        END as diagnostic_category,

        -- Metadata
        dr.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM fhir_prd_db.diagnostic_report dr
    LEFT JOIN fhir_prd_db.diagnostic_report_code_coding drcc
        ON dr.id = drcc.diagnostic_report_id
    LEFT JOIN fhir_prd_db.diagnostic_report_based_on drbo
        ON dr.id = drbo.diagnostic_report_id
    LEFT JOIN fhir_prd_db.service_request sr
        ON REPLACE(drbo.based_on_reference, 'ServiceRequest/', '') = sr.id
    LEFT JOIN fhir_prd_db.service_request_identifier sri
        ON sr.id = sri.service_request_id
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(dr.subject_reference, 'Patient/', '') = REPLACE(s.subject_reference, 'Patient/', '')
        AND ABS(DATE_DIFF('day', CAST(dr.effective_date_time AS DATE), CAST(s.collection_collected_date_time AS DATE))) <= 30
    LEFT JOIN fhir_prd_db.procedure p
        ON REPLACE(dr.encounter_reference, 'Encounter/', '') = REPLACE(p.encounter_reference, 'Encounter/', '')
        AND dr.subject_reference = p.subject_reference
        AND (LOWER(p.code_text) LIKE '%surgical%'
            OR LOWER(p.code_text) LIKE '%resection%'
            OR LOWER(p.code_text) LIKE '%biopsy%'
            OR LOWER(p.code_text) LIKE '%craniotomy%')

    WHERE
        -- Include ALL diagnostic reports with narrative content
        -- (do not filter by keywords - capture everything, let pattern matching extract markers)
        dr.subject_reference IS NOT NULL
        AND dr.conclusion IS NOT NULL

        -- Exclude reports already captured in molecular_tests to avoid duplication
        AND NOT EXISTS (
            SELECT 1 FROM fhir_prd_db.molecular_tests mt
            WHERE mt.result_diagnostic_report_id = dr.id
        )
),

-- ============================================================================
-- CTE 6: Care Plan Pathology Notes (narrative findings in care plans)
-- ============================================================================
care_plan_pathology_notes AS (
    SELECT
        cp.subject_reference as patient_fhir_id,
        'care_plan_pathology_note' as diagnostic_source,
        cp.id as source_id,
        CAST(cp.created AS TIMESTAMP(3)) as diagnostic_datetime,
        CAST(cp.created AS DATE) as diagnostic_date,

        -- Care plan identification
        cp.title as diagnostic_name,
        NULL as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Narrative content
        cp.description as result_value,

        -- Component
        cp.title as component_name,

        -- No specimen info from care plans
        NULL as specimen_types,
        NULL as specimen_sites,
        NULL as specimen_collection_datetime,

        -- No direct procedure link
        NULL as linked_procedure_id,
        NULL as linked_procedure_name,
        NULL as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(cp.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Test identifier
        NULL as test_identifier,
        'Care Plan' as test_lab,

        -- Classification
        'Care_Plan_Pathology' as diagnostic_category,

        -- Metadata
        cp.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM fhir_prd_db.care_plan cp

    WHERE
        -- Include ALL care plans with description text
        -- (do not filter by keywords - capture everything)
        cp.subject_reference IS NOT NULL
        AND cp.description IS NOT NULL
),

-- ============================================================================
-- CTE 7: Procedure Notes with Pathology Content
-- ============================================================================
procedure_pathology_notes AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        'procedure_pathology_note' as diagnostic_source,
        p.id as source_id,
        CAST(p.performed_date_time AS TIMESTAMP(3)) as diagnostic_datetime,
        CAST(p.performed_date_time AS DATE) as diagnostic_date,

        -- Procedure identification
        p.code_text as diagnostic_name,
        NULL as code,
        NULL as coding_system_code,
        NULL as coding_system_name,

        -- Narrative content from procedure notes
        COALESCE(pn.note_text, p.outcome_text) as result_value,

        -- Component
        p.code_text as component_name,

        -- No specimen info
        NULL as specimen_types,
        NULL as specimen_sites,
        NULL as specimen_collection_datetime,

        -- Self-reference
        p.id as linked_procedure_id,
        p.code_text as linked_procedure_name,
        CAST(p.performed_date_time AS TIMESTAMP(3)) as linked_procedure_datetime,

        -- Encounter linkage
        REPLACE(p.encounter_reference, 'Encounter/', '') as encounter_id,

        -- Test identifier
        NULL as test_identifier,
        'Procedure Note' as test_lab,

        -- Classification
        'Procedure_Pathology_Note' as diagnostic_category,

        -- Metadata
        p.status as test_status,
        NULL as test_orderer,
        NULL as component_count

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_note pn
        ON p.id = pn.procedure_id

    WHERE
        -- Include ALL procedures with notes/outcome text
        -- (do not filter by keywords - capture everything)
        p.subject_reference IS NOT NULL
        AND (pn.note_text IS NOT NULL OR p.outcome_text IS NOT NULL)
),

-- ============================================================================
-- CTE 8: Unified Pathology Diagnostics
-- ============================================================================
unified_diagnostics AS (
    SELECT * FROM molecular_diagnostics
    UNION ALL
    SELECT * FROM pathology_observations
    UNION ALL
    SELECT * FROM pathology_procedures
    UNION ALL
    SELECT * FROM pathology_narratives
    UNION ALL
    SELECT * FROM care_plan_pathology_notes
    UNION ALL
    SELECT * FROM procedure_pathology_notes
)

-- ============================================================================
-- FINAL SELECT: All pathology diagnostics with enrichment
-- ============================================================================
SELECT
    ud.patient_fhir_id,
    ud.diagnostic_source,
    ud.source_id,
    ud.diagnostic_datetime,
    ud.diagnostic_date,

    -- Age at diagnostic test
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        ud.diagnostic_date)) as age_at_diagnostic_days,
    TRY(DATE_DIFF('year',
        DATE(pa.birth_date),
        ud.diagnostic_date)) as age_at_diagnostic_years,

    -- Diagnostic identification
    ud.diagnostic_name,
    ud.component_name,
    ud.result_value,
    ud.diagnostic_category,

    -- Coding system information
    ud.coding_system_code,
    ud.coding_system_name,

    -- Specimen information
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

    -- Days between procedure and diagnostic test
    TRY(DATE_DIFF('day',
        CAST(ud.linked_procedure_datetime AS DATE),
        ud.diagnostic_date)) as days_from_procedure,

    -- Encounter linkage
    ud.encounter_id,

    -- Patient demographics
    pa.mrn as patient_mrn,
    pa.birth_date as patient_birth_date,
    pa.gender as patient_gender

FROM unified_diagnostics ud
LEFT JOIN fhir_prd_db.patient_access pa
    ON ud.patient_fhir_id = pa.id

WHERE ud.patient_fhir_id IS NOT NULL

ORDER BY ud.patient_fhir_id, ud.diagnostic_datetime, ud.diagnostic_category;
