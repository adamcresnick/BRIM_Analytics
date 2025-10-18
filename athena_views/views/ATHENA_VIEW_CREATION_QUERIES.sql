-- ================================================================================
-- ATHENA VIEW CREATION QUERIES
-- ================================================================================
-- Purpose: Create materialized views for all patients in fhir_prd_db that
--          replicate the output of the config-driven extraction scripts
--
-- Database: fhir_prd_db
-- Date: 2025-10-16
--
-- USAGE: Copy and paste each CREATE VIEW statement into Athena console
--        Run views in the order listed below (some views depend on others)
-- ================================================================================

-- ================================================================================
-- 1. PATIENT DEMOGRAPHICS VIEW
-- ================================================================================
-- Source: extract_patient_demographics.py
-- Output: patient_demographics.csv
-- Description: Core demographics for all patients (NO MRN for PHI protection)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT
    pa.id as patient_fhir_id,
    pa.gender as pd_gender,
    pa.race as pd_race,
    pa.ethnicity as pd_ethnicity,
    CASE
        WHEN LENGTH(pa.birth_date) = 10 THEN pa.birth_date || 'T00:00:00Z'
        ELSE pa.birth_date
    END as pd_birth_date,
    DATE_DIFF('year', DATE(pa.birth_date), CURRENT_DATE) as pd_age_years
FROM fhir_prd_db.patient_access pa
WHERE pa.id IS NOT NULL;

-- ================================================================================
-- 2. PROBLEM LIST DIAGNOSES VIEW
-- ================================================================================
-- Source: extract_problem_list_diagnoses.py
-- Output: problem_list_diagnoses.csv
-- Description: All diagnoses from problem_list_diagnoses materialized view
-- Columns use 'pld_' prefix for problem_list_diagnoses
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_problem_list_diagnoses AS
SELECT
    pld.patient_id as patient_fhir_id,
    pld.condition_id as pld_condition_id,
    pld.diagnosis_name as pld_diagnosis_name,
    pld.clinical_status_text as pld_clinical_status,
    CASE
        WHEN LENGTH(pld.onset_date_time) = 10 THEN pld.onset_date_time || 'T00:00:00Z'
        ELSE pld.onset_date_time
    END as pld_onset_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(pld.onset_date_time, 1, 10) AS DATE))) as age_at_onset_days,
    CASE
        WHEN LENGTH(pld.abatement_date_time) = 10 THEN pld.abatement_date_time || 'T00:00:00Z'
        ELSE pld.abatement_date_time
    END as pld_abatement_date,
    CASE
        WHEN LENGTH(pld.recorded_date) = 10 THEN pld.recorded_date || 'T00:00:00Z'
        ELSE pld.recorded_date
    END as pld_recorded_date,
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
-- 3. PROCEDURES VIEW
-- ================================================================================
-- Source: extract_all_procedures_metadata.py
-- Output: procedures.csv
-- Description: All procedures with column prefixing (proc_, pcc_, pcat_, pbs_, pp_, prc_, ppr_)
-- Complex multi-table JOIN with surgical keyword detection
--
-- UPDATED: 2025-10-18 - Enhanced with CPT-based classification and sub-schema validation
-- Version: 2.0 (Production-ready with sub-schema validation)
-- See: PRODUCTION_READY_V_PROCEDURES_UPDATE.sql for full documentation
-- ================================================================================

-- ================================================================================
-- ORIGINAL V_PROCEDURES (KEYWORD-BASED) - COMMENTED OUT
-- ================================================================================
-- The original keyword-based approach has been replaced with CPT-based classification
-- Preserved here for reference and rollback capability
-- Precision: 40-50% → New approach: 90-95%
-- ================================================================================
/*
CREATE OR REPLACE VIEW fhir_prd_db.v_procedures AS
WITH procedure_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_system,
        pcc.code_coding_code,
        pcc.code_coding_display,
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
)
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_fhir_id,

    -- Main procedure fields (proc_ prefix)
    p.status as proc_status,
    p.performed_date_time as proc_performed_date_time,
    p.performed_period_start as proc_performed_period_start,
    p.performed_period_end as proc_performed_period_end,
    p.performed_string as proc_performed_string,
    p.performed_age_value as proc_performed_age_value,
    p.performed_age_unit as proc_performed_age_unit,
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

    -- Procedure date (calculated)
    pd.procedure_date,

    -- Age at procedure (calculated if patient birth_date available)
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        pd.procedure_date)) as age_at_procedure_days,

    -- Procedure code fields (pcc_ prefix)
    pc.code_coding_system as pcc_code_coding_system,
    pc.code_coding_code as pcc_code_coding_code,
    pc.code_coding_display as pcc_code_coding_display,
    pc.is_surgical_keyword,

    -- Procedure category (pcat_ prefix)
    pcat.category_coding_display as pcat_category_coding_display,

    -- Body site (pbs_ prefix)
    pbs.body_site_text as pbs_body_site_text,

    -- Performer (pp_ prefix)
    pp.performer_actor_display as pp_performer_actor_display,
    pp.performer_function_text as pp_performer_function_text,

    -- Reason code (prc_ prefix)
    prc.reason_code_text as prc_reason_code_text,

    -- Report reference (ppr_ prefix)
    ppr.report_reference as ppr_report_reference,
    ppr.report_display as ppr_report_display

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN fhir_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
LEFT JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id
LEFT JOIN fhir_prd_db.procedure_reason_code prc ON p.id = prc.procedure_id
LEFT JOIN fhir_prd_db.procedure_report pr ON p.id = pr.procedure_id
LEFT JOIN (
    SELECT procedure_id,
           report_reference,
           report_display,
           ROW_NUMBER() OVER (PARTITION BY procedure_id ORDER BY report_reference) as rn
    FROM fhir_prd_db.procedure_report
) ppr ON p.id = ppr.procedure_id AND ppr.rn = 1
LEFT JOIN fhir_prd_db.patient_access pa ON p.subject_reference = pa.id
WHERE p.subject_reference IS NOT NULL
ORDER BY p.subject_reference, pd.procedure_date;
*/
-- ================================================================================
-- END ORIGINAL V_PROCEDURES (COMMENTED OUT)
-- ================================================================================

-- ================================================================================
-- ENHANCED V_PROCEDURES (CPT-BASED WITH SUB-SCHEMA VALIDATION)
-- ================================================================================
-- Version: 2.0
-- Date: 2025-10-18
-- Improvements:
--   - CPT-based classification (79% coverage, 90-95% precision)
--   - Sub-schema validation (reason_code, body_site)
--   - Multi-tier confidence scoring (0-100)
--   - Backward compatible (all original columns preserved)
--
-- Full documentation: PRODUCTION_READY_V_PROCEDURES_UPDATE.sql
-- ================================================================================

-- Enhanced view SQL inserted below (from PRODUCTION_READY_V_PROCEDURES_UPDATE.sql)
CREATE OR REPLACE VIEW fhir_prd_db.v_procedures AS
WITH
cpt_classifications AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as cpt_code,
        pcc.code_coding_display as cpt_display,

        CASE
            -- ================================================================
            -- TIER 1: DIRECT TUMOR RESECTION (Definitive Include)
            -- ================================================================

            -- Craniotomy/Craniectomy for Tumor Resection (1,168 procedures)
            WHEN pcc.code_coding_code IN (
                '61500',  -- Craniectomy tumor/lesion skull (170 procedures)
                '61510',  -- Craniotomy bone flap brain tumor supratentorial (562 procedures)
                '61512',  -- Craniotomy bone flap meningioma supratentorial (8 procedures)
                '61516',  -- Craniotomy bone flap cyst fenestration supratentorial (11 procedures)
                '61518',  -- Craniotomy brain tumor infratentorial/posterior fossa (428 procedures)
                '61519',  -- Craniotomy meningioma infratentorial (0 procedures - keep for completeness)
                '61520',  -- Craniotomy tumor cerebellopontine angle (23 procedures)
                '61521',  -- Craniotomy tumor midline skull base (0 procedures - keep for completeness)
                '61524',  -- Craniotomy infratentorial cyst excision/fenestration (8 procedures)
                '61545',  -- Craniotomy excision craniopharyngioma (4 procedures)
                '61546',  -- Craniotomy hypophysectomy/excision pituitary tumor (0 procedures)
                '61548'   -- Hypophysectomy/excision pituitary tumor transsphenoidal (0 procedures)
            ) THEN 'craniotomy_tumor_resection'

            -- Stereotactic Procedures - CRITICAL ADDITION (1,493 procedures)
            WHEN pcc.code_coding_code IN (
                '61750',  -- Stereotactic biopsy aspiration intracranial (0 procedures - keep for completeness)
                '61751',  -- Stereotactic biopsy excision burr hole intracranial (59 procedures)
                '61781',  -- Stereotactic computer assisted cranial intradural (1,392 procedures) ← **MOST COMMON!**
                '61782',  -- Stereotactic computer assisted extradural cranial (26 procedures)
                '61783'   -- Stereotactic computer assisted spinal (16 procedures)
            ) THEN 'stereotactic_tumor_procedure'

            -- Neuroendoscopy with Tumor Excision (69 procedures)
            WHEN pcc.code_coding_code IN (
                '62164',  -- Neuroendoscopy intracranial brain tumor excision (65 procedures)
                '62165'   -- Neuroendoscopy intracranial pituitary tumor excision (4 procedures)
            ) THEN 'neuroendoscopy_tumor'

            -- Open Brain Biopsy (0 procedures but keep for completeness)
            WHEN pcc.code_coding_code = '61140'
                THEN 'open_brain_biopsy'

            -- Skull Base/Complex Tumor Approaches (91 procedures)
            WHEN pcc.code_coding_code IN (
                '61580',  -- Craniofacial anterior cranial fossa (5 procedures)
                '61584',  -- Orbitocranial anterior cranial fossa (4 procedures)
                '61592',  -- Orbitocranial middle cranial fossa temporal lobe (25 procedures)
                '61600',  -- Resection/excision lesion base anterior cranial fossa extradural (16 procedures)
                '61601',  -- Resection/excision lesion base anterior cranial fossa intradural (3 procedures)
                '61607'   -- Resection/excision lesion parasellar sinus/cavernous sinus (4 procedures)
            ) THEN 'skull_base_tumor'

            -- ================================================================
            -- TIER 2: TUMOR-RELATED SUPPORT PROCEDURES (Contextual Include)
            -- ================================================================
            -- These procedures have 70-80%+ overlap with tumor patients
            -- Should be included as tumor-related in pediatric brain tumor cohort
            -- ================================================================

            -- Third Ventriculostomy - 77.1% overlap with tumor patients (189 procedures)
            WHEN pcc.code_coding_code IN (
                '62201',  -- Ventriculocisternostomy 3rd ventricle endoscopic (189 procedures)
                '62200'   -- Ventriculocisternostomy 3rd ventricle (0 procedures)
            ) THEN 'tumor_related_csf_management'

            -- Ventricular Device Implantation - 81.2% overlap with tumor patients (362 procedures)
            -- Used for: ICP monitoring, EVD, Ommaya reservoir for chemotherapy
            WHEN pcc.code_coding_code IN (
                '61210',  -- Burr hole implant ventricular catheter/device (362 procedures)
                '61215'   -- Insertion subcutaneous reservoir pump/infusion ventricular (47 procedures)
            ) THEN 'tumor_related_device_implant'

            -- ================================================================
            -- TIER 3: EXPLORATORY/DIAGNOSTIC (Ambiguous - Need Context)
            -- ================================================================

            -- Exploratory Craniotomy - may be tumor or non-tumor (115 procedures)
            WHEN pcc.code_coding_code IN (
                '61304',  -- Craniectomy/craniotomy exploration supratentorial (79 procedures)
                '61305'   -- Craniectomy/craniotomy exploration infratentorial (36 procedures)
            ) THEN 'exploratory_craniotomy'

            -- Unlisted Nervous System Procedure - requires free-text review (477 procedures)
            WHEN pcc.code_coding_code = '64999'
                THEN 'unlisted_nervous_system'

            -- ================================================================
            -- EXCLUSIONS: NON-TUMOR PROCEDURES
            -- ================================================================

            -- VP Shunt Procedures - permanent CSF diversion, not tumor-specific (654 procedures)
            WHEN pcc.code_coding_code IN (
                '62220',  -- Creation shunt ventriculo-atrial (12 procedures)
                '62223',  -- Creation shunt ventriculo-peritoneal (307 procedures)
                '62225',  -- Replacement/irrigation ventricular catheter (232 procedures)
                '62230',  -- Replacement/revision CSF shunt valve/catheter (115 procedures)
                '62256',  -- Removal complete CSF shunt system (12 procedures)
                '62192'   -- Creation shunt subarachnoid/subdural-peritoneal (13 procedures)
            ) THEN 'exclude_vp_shunt'

            -- Spasticity/Pain Management - NOT tumor surgery (467 procedures)
            WHEN pcc.code_coding_code IN (
                '64615',  -- Chemodenervation for headache (62 procedures)
                '64642',  -- Chemodenervation one extremity 1-4 muscles (49 procedures)
                '64643',  -- Chemodenervation one extremity additional 1-4 muscles (63 procedures)
                '64644',  -- Chemodenervation one extremity 5+ muscles (70 procedures)
                '64645',  -- Chemodenervation one extremity additional 5+ muscles (26 procedures)
                '64646',  -- Chemodenervation trunk muscle 1-5 muscles (0 procedures)
                '64647',  -- Chemodenervation trunk muscle 6+ muscles (0 procedures)
                '64400',  -- Injection anesthetic trigeminal nerve (75 procedures)
                '64405',  -- Injection anesthetic greater occipital nerve (35 procedures)
                '64450',  -- Injection anesthetic other peripheral nerve (36 procedures)
                '64614',  -- Chemodenervation extremity/trunk muscle (51 procedures)
                '64616'   -- Chemodenervation muscle neck unilateral (4 procedures)
            ) THEN 'exclude_spasticity_pain'

            -- Diagnostic Procedures - NOT surgery (384 procedures)
            WHEN pcc.code_coding_code IN (
                '62270',  -- Spinal puncture lumbar diagnostic (354 procedures)
                '62272',  -- Spinal puncture therapeutic (30 procedures)
                '62328'   -- Diagnostic lumbar puncture with fluoro/CT (5 procedures)
            ) THEN 'exclude_diagnostic_procedure'

            -- Burr Holes for Hematoma/Trauma (11 procedures)
            WHEN pcc.code_coding_code IN (
                '61154',  -- Burr hole evacuation/drainage hematoma (11 procedures)
                '61156'   -- Burr hole aspiration hematoma/cyst brain (0 procedures)
            ) THEN 'exclude_burr_hole_trauma'

            -- Craniotomy for Hematoma/Abscess (21 procedures)
            WHEN pcc.code_coding_code IN (
                '61312',  -- Craniectomy hematoma supratentorial (5 procedures)
                '61313',  -- Craniectomy hematoma supratentorial intradural (0 procedures)
                '61314',  -- Craniectomy hematoma infratentorial (0 procedures)
                '61315',  -- Craniectomy hematoma infratentorial intradural (0 procedures)
                '61320',  -- Craniectomy/craniotomy drainage abscess supratentorial (8 procedures)
                '61321'   -- Craniectomy/craniotomy drainage abscess infratentorial (0 procedures)
            ) THEN 'exclude_trauma_abscess'

            -- Neuroendoscopy for Non-Tumor Indications (35 procedures)
            WHEN pcc.code_coding_code IN (
                '62161',  -- Neuroendoscopy dissection adhesions/fenestration (35 procedures)
                '62162',  -- Neuroendoscopy fenestration cyst (0 procedures)
                '62163'   -- Neuroendoscopy retrieval foreign body (0 procedures)
            ) THEN 'exclude_neuroendoscopy_nontumor'

            ELSE NULL
        END as cpt_classification,

        -- Classification type for easier filtering
        CASE
            WHEN pcc.code_coding_code IN (
                '61500', '61510', '61512', '61516', '61518', '61519', '61520', '61521', '61524',
                '61545', '61546', '61548', '61750', '61751', '61781', '61782', '61783',
                '62164', '62165', '61140', '61580', '61584', '61592', '61600', '61601', '61607'
            ) THEN 'definite_tumor'

            WHEN pcc.code_coding_code IN (
                '62201', '62200', '61210', '61215'
            ) THEN 'tumor_support'

            WHEN pcc.code_coding_code IN (
                '61304', '61305', '64999'
            ) THEN 'ambiguous'

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

-- ================================================================================
-- INSTITUTIONAL CODES (SUPPLEMENTARY - Epic URN codes)
-- ================================================================================
-- Used as confidence booster when present alongside CPT codes
-- ================================================================================
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

-- ================================================================================
-- ENHANCED KEYWORD CLASSIFICATION (FALLBACK for non-CPT codes)
-- ================================================================================
-- Used only when CPT code is not available
-- Refined patterns based on actual procedure text analysis
-- ================================================================================
procedure_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_system,
        pcc.code_coding_code,
        pcc.code_coding_display,

        -- Tumor-specific keywords (POSITIVE indicators)
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

            -- Non-tumor keywords (NEGATIVE indicators - exclude)
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

            -- Generic surgical keywords (AMBIGUOUS - low confidence)
            WHEN LOWER(pcc.code_coding_display) LIKE '%craniotomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgery%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgical%'
            THEN 'keyword_surgical_generic'

            ELSE NULL
        END as keyword_classification,

        -- BACKWARD COMPATIBILITY: Original is_surgical_keyword field
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

-- Procedure dates (unchanged from original)
procedure_dates AS (
    SELECT
        p.id as procedure_id,
        COALESCE(
            TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)),
            TRY(CAST(SUBSTR(p.performed_period_start, 1, 10) AS DATE))
        ) as procedure_date
    FROM fhir_prd_db.procedure p
),

-- ================================================================================
-- SUB-SCHEMA VALIDATION (Cross-validation from reason_code and body_site)
-- ================================================================================
-- Provides additional confidence boosts/penalties based on clinical context
-- Based on analysis of 40,252 procedures - see SUB_SCHEMA_VALIDATION_ANALYSIS.md
-- ================================================================================
procedure_validation AS (
    SELECT
        p.id as procedure_id,

        -- Reason code tumor indicators
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

        -- Reason code exclude indicators (non-tumor procedures)
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

        -- Body site tumor indicators (cranial anatomical sites)
        CASE
            WHEN pbs.body_site_text IN ('Brain', 'Skull', 'Nares', 'Nose', 'Temporal', 'Orbit')
            THEN true
            ELSE false
        END as has_tumor_body_site,

        -- Body site exclude indicators (peripheral/non-cranial sites)
        CASE
            WHEN pbs.body_site_text IN ('Arm', 'Leg', 'Hand', 'Thigh', 'Shoulder',
                                         'Arm Lower', 'Arm Upper', 'Foot', 'Ankle')
            THEN true
            ELSE false
        END as has_exclude_body_site,

        -- Raw values for output
        prc.reason_code_text,
        pbs.body_site_text

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_reason_code prc ON p.id = prc.procedure_id
    LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
),

-- ================================================================================
-- COMBINED MULTI-TIER CLASSIFICATION
-- ================================================================================
combined_classification AS (
    SELECT
        p.id as procedure_id,

        -- Individual tier results
        cpt.cpt_classification,
        cpt.cpt_code,
        cpt.classification_type as cpt_type,
        epic.epic_category,
        epic.epic_code,
        pc.keyword_classification,

        -- Sub-schema validation flags
        pv.has_tumor_reason,
        pv.has_exclude_reason,
        pv.has_tumor_body_site,
        pv.has_exclude_body_site,
        pv.reason_code_text as validation_reason_code,
        pv.body_site_text as validation_body_site,

        -- Final combined classification (prioritize CPT > Epic > Keywords)
        COALESCE(
            cpt.cpt_classification,
            epic.epic_category,
            pc.keyword_classification,
            'unclassified'
        ) as procedure_classification,

        -- Is this a tumor-related procedure? (with sub-schema validation)
        CASE
            -- Force exclude if sub-schema indicates non-tumor
            WHEN pv.has_exclude_reason = true OR pv.has_exclude_body_site = true THEN false

            -- Include if CPT indicates tumor
            WHEN cpt.classification_type = 'definite_tumor' THEN true
            WHEN cpt.classification_type = 'tumor_support' THEN true

            -- Include if ambiguous CPT but tumor reason/body site
            WHEN cpt.classification_type = 'ambiguous'
                AND (pv.has_tumor_reason = true OR pv.has_tumor_body_site = true) THEN true

            -- Include if keyword indicates tumor
            WHEN cpt.classification_type IS NULL
                AND pc.keyword_classification = 'keyword_tumor_specific' THEN true

            ELSE false
        END as is_tumor_surgery,

        -- Should this be excluded? (with sub-schema validation)
        CASE
            -- Force exclude if sub-schema indicates non-tumor
            WHEN pv.has_exclude_reason = true OR pv.has_exclude_body_site = true THEN true

            -- Exclude if CPT indicates exclude
            WHEN cpt.classification_type = 'exclude' THEN true
            WHEN pc.keyword_classification = 'keyword_exclude' THEN true

            ELSE false
        END as is_excluded_procedure,

        -- Surgery type categorization
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

        -- Confidence score (0-100) with sub-schema validation
        CASE
            -- ================================================================
            -- FORCE EXCLUDE: Sub-schema indicates non-tumor
            -- ================================================================
            WHEN pv.has_exclude_reason = true OR pv.has_exclude_body_site = true THEN 0

            -- ================================================================
            -- TIER 1: DEFINITE TUMOR CPT CODES (Base: 90-100)
            -- ================================================================

            -- Maximum confidence: CPT definite tumor + tumor reason + brain body site
            WHEN cpt.classification_type = 'definite_tumor'
                AND pv.has_tumor_reason = true
                AND pv.has_tumor_body_site = true THEN 100

            -- Very high: CPT definite tumor + tumor reason
            WHEN cpt.classification_type = 'definite_tumor'
                AND pv.has_tumor_reason = true THEN 95

            -- Very high: CPT definite tumor + brain body site
            WHEN cpt.classification_type = 'definite_tumor'
                AND pv.has_tumor_body_site = true THEN 95

            -- Very high: CPT definite tumor + Epic neurosurgery
            WHEN cpt.classification_type = 'definite_tumor'
                AND epic.epic_category = 'neurosurgery_request' THEN 95

            -- High: CPT definite tumor alone
            WHEN cpt.classification_type = 'definite_tumor' THEN 90

            -- ================================================================
            -- TIER 2: TUMOR SUPPORT CPT CODES (Base: 75-90)
            -- ================================================================

            -- Very high: CPT tumor support + tumor reason + brain body site
            WHEN cpt.classification_type = 'tumor_support'
                AND pv.has_tumor_reason = true
                AND pv.has_tumor_body_site = true THEN 90

            -- High: CPT tumor support + tumor reason
            WHEN cpt.classification_type = 'tumor_support'
                AND pv.has_tumor_reason = true THEN 85

            -- High: CPT tumor support + brain body site
            WHEN cpt.classification_type = 'tumor_support'
                AND pv.has_tumor_body_site = true THEN 85

            -- Medium-high: CPT tumor support + Epic neurosurgery
            WHEN cpt.classification_type = 'tumor_support'
                AND epic.epic_category = 'neurosurgery_request' THEN 80

            -- Medium-high: CPT tumor support alone
            WHEN cpt.classification_type = 'tumor_support' THEN 75

            -- ================================================================
            -- TIER 3: AMBIGUOUS CPT CODES (Base: 50-75)
            -- ================================================================

            -- Medium: Ambiguous CPT + tumor reason + brain body site
            WHEN cpt.classification_type = 'ambiguous'
                AND pv.has_tumor_reason = true
                AND pv.has_tumor_body_site = true THEN 70

            -- Medium: Ambiguous CPT + tumor reason
            WHEN cpt.classification_type = 'ambiguous'
                AND pv.has_tumor_reason = true THEN 65

            -- Medium: Ambiguous CPT + brain body site
            WHEN cpt.classification_type = 'ambiguous'
                AND pv.has_tumor_body_site = true THEN 60

            -- Low-medium: Ambiguous CPT alone
            WHEN cpt.classification_type = 'ambiguous' THEN 50

            -- ================================================================
            -- TIER 4: KEYWORD-BASED CLASSIFICATION (Base: 40-70)
            -- ================================================================

            -- Medium: Keyword tumor-specific + tumor reason
            WHEN pc.keyword_classification = 'keyword_tumor_specific'
                AND pv.has_tumor_reason = true THEN 75

            -- Medium: Keyword tumor-specific + brain body site
            WHEN pc.keyword_classification = 'keyword_tumor_specific'
                AND pv.has_tumor_body_site = true THEN 70

            -- Medium: Keyword tumor-specific alone
            WHEN pc.keyword_classification = 'keyword_tumor_specific' THEN 65

            -- Low: Generic surgical keywords
            WHEN pc.keyword_classification = 'keyword_surgical_generic' THEN 40

            -- ================================================================
            -- EXCLUSIONS AND UNCLASSIFIED
            -- ================================================================

            -- Exclude: CPT indicates non-tumor
            WHEN cpt.classification_type = 'exclude' THEN 0
            WHEN pc.keyword_classification = 'keyword_exclude' THEN 0

            -- Very low: Unclassified
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

-- ================================================================================
-- MAIN SELECT (Original columns + new classification fields)
-- ================================================================================
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_fhir_id,

    -- Main procedure fields (proc_ prefix) - UNCHANGED
    p.status as proc_status,
    p.performed_date_time as proc_performed_date_time,
    p.performed_period_start as proc_performed_period_start,
    p.performed_period_end as proc_performed_period_end,
    p.performed_string as proc_performed_string,
    p.performed_age_value as proc_performed_age_value,
    p.performed_age_unit as proc_performed_age_unit,
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

    -- Procedure date (calculated) - UNCHANGED
    pd.procedure_date,

    -- Age at procedure (calculated) - UNCHANGED
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        pd.procedure_date)) as age_at_procedure_days,

    -- Procedure code fields (pcc_ prefix) - UNCHANGED
    pc.code_coding_system as pcc_code_coding_system,
    pc.code_coding_code as pcc_code_coding_code,
    pc.code_coding_display as pcc_code_coding_display,
    pc.is_surgical_keyword,  -- BACKWARD COMPATIBILITY

    -- NEW CLASSIFICATION FIELDS
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

    -- NEW SUB-SCHEMA VALIDATION FIELDS
    cc.has_tumor_reason,
    cc.has_exclude_reason,
    cc.has_tumor_body_site,
    cc.has_exclude_body_site,
    cc.validation_reason_code,
    cc.validation_body_site,

    -- Procedure category (pcat_ prefix) - UNCHANGED
    pcat.category_coding_display as pcat_category_coding_display,

    -- Body site (pbs_ prefix) - UNCHANGED
    pbs.body_site_text as pbs_body_site_text,

    -- Performer (pp_ prefix) - UNCHANGED
    pp.performer_actor_display as pp_performer_actor_display,
    pp.performer_function_text as pp_performer_function_text,

    -- Reason code (prc_ prefix) - UNCHANGED

-- 4. MEDICATIONS VIEW
-- ================================================================================
-- Source: extract_all_medications_metadata.py
-- Output: medications.csv
-- Description: Comprehensive medication data joining 9 tables
-- Uses aggregation (LISTAGG) for multi-valued fields
-- Columns use mr_, mrn_, mrr_, mrb_, mf_, mi_, cp_, cpc_, cpcon_, cpa_, mrdi_ prefixes
-- ENHANCED: Added medication_request_dosage_instruction for route, method, timing
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
    pm.authored_on as medication_start_date,
    pm.requester_name,
    pm.status as medication_status,
    pm.encounter_display,

    -- Medication_request fields (mr_ prefix) - matched to working Python script
    mr.dispense_request_validity_period_start as mr_validity_period_start,
    mr.dispense_request_validity_period_end as mr_validity_period_end,
    mr.authored_on as mr_authored_on,
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

    -- Based-on references (mrb_ prefix - care plan linkage)
    mrb.based_on_reference as mrb_care_plan_reference,
    mrb.based_on_display as mrb_care_plan_display,

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
    cp.created as cp_created,
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end,
    cp.author_display as cp_author_display,

    -- Care plan categories (cpc_ prefix)
    cpc.categories_aggregated as cpc_categories_aggregated,

    -- Care plan conditions (cpcon_ prefix)
    cpcon.addresses_aggregated as cpcon_addresses_aggregated,

    -- Care plan activity (cpa_ prefix)
    cpa.activity_detail_status as cpa_activity_detail_status

FROM fhir_prd_db.patient_medications pm
LEFT JOIN fhir_prd_db.medication_request mr ON pm.medication_request_id = mr.id
LEFT JOIN medication_notes mrn ON mr.id = mrn.medication_request_id
LEFT JOIN medication_reasons mrr ON mr.id = mrr.medication_request_id
LEFT JOIN fhir_prd_db.medication_request_based_on mrb ON mr.id = mrb.medication_request_id
LEFT JOIN medication_dosage_instructions mrdi ON mr.id = mrdi.medication_request_id
LEFT JOIN medication_forms mf ON pm.medication_id = mf.medication_id
LEFT JOIN medication_ingredients mi ON pm.medication_id = mi.medication_id
LEFT JOIN fhir_prd_db.care_plan cp ON mrb.based_on_reference = cp.id
LEFT JOIN care_plan_categories cpc ON cp.id = cpc.care_plan_id
LEFT JOIN care_plan_conditions cpcon ON cp.id = cpcon.care_plan_id
LEFT JOIN fhir_prd_db.care_plan_activity cpa ON cp.id = cpa.care_plan_id
WHERE pm.patient_id IS NOT NULL
ORDER BY pm.patient_id, pm.authored_on;

-- ================================================================================
-- 5. IMAGING VIEW
-- ================================================================================
-- Source: extract_all_imaging_metadata.py
-- Output: imaging.csv
-- Description: MRI and other imaging studies with diagnostic reports
-- Columns use imaging_ prefix
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
    SELECT
        mri.patient_id,
        mri.imaging_procedure_id,
        mri.result_datetime as imaging_date,
        mri.imaging_procedure,
        mri.result_diagnostic_report_id,
        'MRI' as imaging_modality,
        results.value_string as result_information,
        results.result_display
    FROM fhir_prd_db.radiology_imaging_mri mri
    LEFT JOIN fhir_prd_db.radiology_imaging_mri_results results
        ON mri.imaging_procedure_id = results.imaging_procedure_id
),
other_imaging AS (
    SELECT
        ri.patient_id,
        ri.imaging_procedure_id,
        ri.result_datetime as imaging_date,
        ri.imaging_procedure,
        ri.result_diagnostic_report_id,
        COALESCE(ri.imaging_procedure, 'Unknown') as imaging_modality,
        CAST(NULL AS VARCHAR) as result_information,
        CAST(NULL AS VARCHAR) as result_display
    FROM fhir_prd_db.radiology_imaging ri
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
    dr.issued as report_issued,
    dr.effective_period_start as report_effective_period_start,
    dr.effective_period_stop as report_effective_period_stop,
    rc.category_text,

    -- Age calculations
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(ci.imaging_date, 1, 10) AS DATE))) as age_at_imaging_days,
    TRY(DATE_DIFF('year',
        DATE(pa.birth_date),
        CAST(SUBSTR(ci.imaging_date, 1, 10) AS DATE))) as age_at_imaging_years

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
-- 6. ENCOUNTERS VIEW
-- ================================================================================
-- Source: extract_all_encounters_metadata.py
-- Output: encounters.csv
-- Description: All encounters with types, reasons, and diagnoses
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_encounters AS
WITH encounter_types_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT type_text, ' | ') WITHIN GROUP (ORDER BY type_text) as type_text_aggregated
    FROM fhir_prd_db.encounter_type
    GROUP BY encounter_id
),
encounter_reasons_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
    FROM fhir_prd_db.encounter_reason_code
    GROUP BY encounter_id
),
encounter_diagnoses_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT diagnosis_condition_reference, ' | ') WITHIN GROUP (ORDER BY diagnosis_condition_reference) as diagnosis_references_aggregated
    FROM fhir_prd_db.encounter_diagnosis
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
    e.period_start,
    e.period_end,
    e.length_value,
    e.length_unit,
    e.service_provider_display,
    e.part_of_reference,
    e.subject_reference as patient_fhir_id,

    -- Aggregated subtables
    et.type_text_aggregated,
    er.reason_code_text_aggregated,
    ed.diagnosis_references_aggregated

FROM fhir_prd_db.encounter e
LEFT JOIN encounter_types_agg et ON e.id = et.encounter_id
LEFT JOIN encounter_reasons_agg er ON e.id = er.encounter_id
LEFT JOIN encounter_diagnoses_agg ed ON e.id = ed.encounter_id
LEFT JOIN fhir_prd_db.patient_access pa ON e.subject_reference = pa.id
WHERE e.subject_reference IS NOT NULL
ORDER BY e.subject_reference, e.period_start;

-- ================================================================================
-- 7. MEASUREMENTS VIEW
-- ================================================================================
-- Source: extract_all_measurements_metadata.py
-- Output: measurements.csv
-- Description: Lab results and vital signs observations
-- ================================================================================

-- Python script combines observation + lab_tests + lab_test_results
CREATE OR REPLACE VIEW fhir_prd_db.v_measurements AS
WITH observations AS (
    SELECT
        subject_reference as patient_fhir_id,
        id as obs_observation_id,
        code_text as obs_measurement_type,
        value_quantity_value as obs_measurement_value,
        value_quantity_unit as obs_measurement_unit,
        effective_date_time as obs_measurement_date,
        issued as obs_issued,
        status as obs_status,
        encounter_reference as obs_encounter_reference,
        'observation' as source_table,
        CAST(NULL AS VARCHAR) as lt_test_id,
        CAST(NULL AS VARCHAR) as lt_measurement_type,
        CAST(NULL AS VARCHAR) as lt_measurement_date,
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
        CAST(NULL AS VARCHAR) as ltr_value_integer
    FROM fhir_prd_db.observation
    WHERE subject_reference IS NOT NULL
),
lab_tests_with_results AS (
    SELECT
        lt.patient_id as patient_fhir_id,
        CAST(NULL AS VARCHAR) as obs_observation_id,
        CAST(NULL AS VARCHAR) as obs_measurement_type,
        CAST(NULL AS VARCHAR) as obs_measurement_value,
        CAST(NULL AS VARCHAR) as obs_measurement_unit,
        CAST(NULL AS VARCHAR) as obs_measurement_date,
        CAST(NULL AS VARCHAR) as obs_issued,
        CAST(NULL AS VARCHAR) as obs_status,
        CAST(NULL AS VARCHAR) as obs_encounter_reference,
        'lab_tests' as source_table,
        lt.test_id as lt_test_id,
        lt.lab_test_name as lt_measurement_type,
        lt.result_datetime as lt_measurement_date,
        lt.lab_test_status as lt_status,
        lt.result_diagnostic_report_id as lt_result_diagnostic_report_id,
        lt.lab_test_requester as lt_lab_test_requester,
        ltr.test_component as ltr_test_component,
        ltr.value_string as ltr_value_string,
        ltr.value_quantity_value as ltr_measurement_value,
        ltr.value_quantity_unit as ltr_measurement_unit,
        ltr.value_codeable_concept_text as ltr_value_codeable_concept_text,
        ltr.value_range_low_value as ltr_value_range_low_value,
        ltr.value_range_low_unit as ltr_value_range_low_unit,
        ltr.value_range_high_value as ltr_value_range_high_value,
        ltr.value_range_high_unit as ltr_value_range_high_unit,
        ltr.value_boolean as ltr_value_boolean,
        ltr.value_integer as ltr_value_integer
    FROM fhir_prd_db.lab_tests lt
    LEFT JOIN fhir_prd_db.lab_test_results ltr ON lt.test_id = ltr.test_id
    WHERE lt.patient_id IS NOT NULL
)
SELECT
    combined.*,
    pa.birth_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(COALESCE(obs_measurement_date, lt_measurement_date), 1, 10) AS DATE))) as age_at_measurement_days,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        CAST(SUBSTR(COALESCE(obs_measurement_date, lt_measurement_date), 1, 10) AS DATE)) / 365.25) as age_at_measurement_years
FROM (
    SELECT * FROM observations
    UNION ALL
    SELECT * FROM lab_tests_with_results
) combined
LEFT JOIN fhir_prd_db.patient_access pa ON combined.patient_fhir_id = pa.id
ORDER BY combined.patient_fhir_id, COALESCE(obs_measurement_date, lt_measurement_date);

-- ================================================================================
-- 8. BINARY FILES (DOCUMENT REFERENCE) VIEW
-- ================================================================================
-- Source: extract_all_binary_files_metadata.py
-- Output: binary_files.csv
-- Description: All document references with metadata (22K+ docs per patient typical)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_binary_files AS
WITH document_contexts AS (
    SELECT
        document_reference_id,
        LISTAGG(DISTINCT context_encounter_reference, ' | ')
            WITHIN GROUP (ORDER BY context_encounter_reference) as encounter_references
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
)
SELECT
    dr.id as document_reference_id,
    dr.subject_reference as patient_fhir_id,
    dr.status as dr_status,
    dr.doc_status as dr_doc_status,
    dr.type_text as dr_type_text,
    dcat.category_text as dr_category_text,
    dr.date as dr_date,
    dr.description as dr_description,
    dr.context_period_start as dr_context_period_start,
    dr.context_period_end as dr_context_period_end,
    dr.context_facility_type_text as dr_facility_type,
    dr.context_practice_setting_text as dr_practice_setting,
    dc.encounter_references as dr_encounter_references,

    -- Age at document date
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(dr.date, 1, 10) AS DATE)))) as age_at_document_days

FROM fhir_prd_db.document_reference dr
LEFT JOIN document_contexts dc ON dr.id = dc.document_reference_id
LEFT JOIN document_categories dcat ON dr.id = dcat.document_reference_id
LEFT JOIN fhir_prd_db.patient_access pa ON dr.subject_reference = pa.id
WHERE dr.subject_reference IS NOT NULL
ORDER BY dr.subject_reference, dr.date DESC;

-- ================================================================================
-- 9. MOLECULAR TESTS METADATA VIEW
-- ================================================================================
-- Source: extract_all_molecular_tests_metadata.py
-- Output: molecular_tests_metadata.csv
-- Description: Molecular/genetic test results from diagnostic_report
-- Columns use mt_ prefix
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
    SELECT DISTINCT
        ar.test_id,
        ar.dgd_id,
        sri.service_request_id,
        sr.encounter_reference,
        REPLACE(sr.encounter_reference, 'Encounter/', '') AS encounter_id,
        s.id as specimen_id,
        s.type_text as specimen_type,
        s.collection_collected_date_time as specimen_collection_date,
        s.collection_body_site_text as specimen_body_site,
        s.accession_identifier_value as specimen_accession
    FROM aggregated_results ar
    LEFT JOIN fhir_prd_db.service_request_identifier sri
        ON ar.dgd_id = sri.identifier_value
    LEFT JOIN fhir_prd_db.service_request sr
        ON sri.service_request_id = sr.id
    LEFT JOIN fhir_prd_db.service_request_specimen srs
        ON sr.id = srs.service_request_id
    LEFT JOIN fhir_prd_db.specimen s
        ON REPLACE(srs.specimen_reference, 'Specimen/', '') = s.id
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
    SUBSTR(mt.result_datetime, 1, 10) as mt_test_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(mt.result_datetime, 1, 10) AS DATE)))) as age_at_test_days,
    mt.lab_test_name as mt_lab_test_name,
    mt.lab_test_status as mt_test_status,
    mt.lab_test_requester as mt_test_requester,
    COALESCE(ar.component_count, 0) as mtr_component_count,
    COALESCE(ar.total_narrative_chars, 0) as mtr_total_narrative_chars,
    COALESCE(ar.components_list, 'None') as mtr_components_list,
    sl.specimen_id as mt_specimen_id,
    sl.specimen_type as mt_specimen_type,
    SUBSTR(sl.specimen_collection_date, 1, 10) as mt_specimen_collection_date,
    sl.specimen_body_site as mt_specimen_body_site,
    sl.specimen_accession as mt_specimen_accession,
    sl.encounter_id as mt_encounter_id,
    pl.procedure_id as mt_procedure_id,
    pl.procedure_name as mt_procedure_name,
    SUBSTR(pl.procedure_date, 1, 10) as mt_procedure_date,
    pl.procedure_status as mt_procedure_status
FROM fhir_prd_db.molecular_tests mt
LEFT JOIN aggregated_results ar ON mt.test_id = ar.test_id
LEFT JOIN specimen_linkage sl ON mt.test_id = sl.test_id
LEFT JOIN procedure_linkage pl ON mt.test_id = pl.test_id
LEFT JOIN fhir_prd_db.patient_access pa ON mt.patient_id = pa.id
WHERE mt.patient_id IS NOT NULL
ORDER BY mt.result_datetime, mt.test_id;

-- ================================================================================
-- 10. RADIATION TREATMENT APPOINTMENTS VIEW
-- ================================================================================
-- Source: extract_radiation_data.py (output file 1 of 7)
-- Output: radiation_treatment_appointments.csv
-- Description: Radiation oncology appointments
-- NOTE: Athena views don't support complex WHERE clauses with multiple LIKE/OR.
--       Filter for radiation terms when querying this view.
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_appointments AS
SELECT DISTINCT
    ap.participant_actor_reference as patient_fhir_id,
    a.id as appointment_id,
    a.status as appointment_status,
    a.appointment_type_text,
    a.priority,
    a.description,
    a.start as appointment_start,
    a."end" as appointment_end,
    a.minutes_duration,
    a.created,
    a.comment as appointment_comment,
    a.patient_instruction
FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference LIKE 'Patient/%'
ORDER BY a.start;

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
-- 11. RADIATION TREATMENT COURSES VIEW (ORIGINAL)
-- ================================================================================
-- REPLACED BY: v_radiation_treatments (see below)
-- LIMITATION: Only includes service_request data (3 records, 1 patient)
-- MISSING: Observation-based structured dose/site data (~90 patients)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatment_courses AS
SELECT
    sr.subject_reference as patient_fhir_id,
    sr.id as course_id,
    sr.status as sr_status,
    sr.intent as sr_intent,
    sr.code_text as sr_code_text,
    sr.quantity_quantity_value as sr_quantity_value,
    sr.quantity_quantity_unit as sr_quantity_unit,
    sr.occurrence_date_time as sr_occurrence_date_time,
    sr.occurrence_period_start as sr_occurrence_period_start,
    sr.occurrence_period_end as sr_occurrence_period_end,
    sr.authored_on as sr_authored_on,
    sr.requester_display as sr_requester_display,
    sr.performer_type_text as sr_performer_type_text,
    sr.patient_instruction as sr_patient_instruction
FROM fhir_prd_db.service_request sr
WHERE sr.subject_reference IS NOT NULL
  AND (LOWER(sr.code_text) LIKE '%radiation%'
       OR LOWER(sr.patient_instruction) LIKE '%radiation%')
ORDER BY sr.subject_reference, sr.occurrence_period_start;

-- ================================================================================
-- 12. RADIATION CARE PLAN NOTES VIEW (ORIGINAL)
-- ================================================================================
-- REPLACED BY: v_radiation_documents (see below)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_care_plan_notes AS
SELECT
    cp.subject_reference as patient_fhir_id,
    cpn.care_plan_id,
    cpn.note_text as cpn_note_text,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.title as cp_title,
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end
FROM fhir_prd_db.care_plan_note cpn
INNER JOIN fhir_prd_db.care_plan cp ON cpn.care_plan_id = cp.id
WHERE cp.subject_reference IS NOT NULL
  AND LOWER(cpn.note_text) LIKE '%radiation%'
ORDER BY cp.period_start;

-- ================================================================================
-- 13. RADIATION CARE PLAN HIERARCHY VIEW (ORIGINAL)
-- ================================================================================
-- STATUS: KEEP AS-IS (used for internal linkage queries)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_care_plan_hierarchy AS
SELECT
    cp.subject_reference as patient_fhir_id,
    cppo.care_plan_id,
    cppo.part_of_reference as cppo_part_of_reference,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.title as cp_title,
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end
FROM fhir_prd_db.care_plan_part_of cppo
INNER JOIN fhir_prd_db.care_plan cp ON cppo.care_plan_id = cp.id
WHERE cp.subject_reference IS NOT NULL
  AND (LOWER(cp.title) LIKE '%radiation%'
       OR LOWER(cppo.part_of_reference) LIKE '%radiation%')
ORDER BY cp.period_start;

-- ================================================================================
-- 14. RADIATION SERVICE REQUEST NOTES VIEW (ORIGINAL)
-- ================================================================================
-- REPLACED BY: v_radiation_documents (see below) and aggregated in v_radiation_treatments (srn_ fields)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_service_request_notes AS
SELECT
    sr.subject_reference as patient_fhir_id,
    sr.id as service_request_id,
    sr.intent as sr_intent,
    sr.status as sr_status,
    sr.authored_on as sr_authored_on,
    sr.occurrence_date_time as sr_occurrence_date_time,
    sr.occurrence_period_start as sr_occurrence_period_start,
    sr.occurrence_period_end as sr_occurrence_period_end,
    srn.note_text as srn_note_text,
    srn.note_time as srn_note_time
FROM fhir_prd_db.service_request_note srn
INNER JOIN fhir_prd_db.service_request sr ON srn.service_request_id = sr.id
WHERE sr.subject_reference IS NOT NULL
  AND LOWER(srn.note_text) LIKE '%radiation%'
ORDER BY COALESCE(srn.note_time, sr.occurrence_date_time, sr.occurrence_period_start, sr.authored_on);

-- ================================================================================
-- 15. RADIATION SERVICE REQUEST RT HISTORY VIEW (ORIGINAL)
-- ================================================================================
-- REPLACED BY: Aggregated in v_radiation_treatments (srrc_ fields)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_service_request_rt_history AS
SELECT
    sr.subject_reference as patient_fhir_id,
    sr.id as sr_id,
    sr.status as sr_status,
    sr.code_text as sr_code_text,
    sr.authored_on as sr_authored_on,
    srrc.reason_code_coding as srrc_reason_code_coding,
    srrc.reason_code_text as srrc_reason_code_text
FROM fhir_prd_db.service_request sr
INNER JOIN fhir_prd_db.service_request_reason_code srrc ON sr.id = srrc.service_request_id
WHERE sr.subject_reference IS NOT NULL
  AND (LOWER(sr.code_text) LIKE '%radiation%'
       OR LOWER(srrc.reason_code_text) LIKE '%radiation%')
ORDER BY sr.subject_reference, sr.authored_on;

-- END OF COMMENTED OUT ORIGINAL RADIATION VIEWS
*/

-- ================================================================================
-- 11-12. CONSOLIDATED RADIATION VIEWS (ENHANCED - REPLACES VIEWS 11-15 ABOVE)
-- ================================================================================
-- Created: October 18, 2025
-- Description: Consolidated radiation views with complete field provenance
-- Key Enhancements:
--   1. Includes observation-based structured dose/site data (~90 patients)
--   2. Preserves all original service_request fields
--   3. Aggregates appointment and care plan context
--   4. Clear field provenance via prefix strategy (obs_, sr_, apt_, cp_, doc_)
--   5. Data quality scoring and completeness flags
-- ================================================================================
-- IMPORTANT: Athena only allows ONE SQL statement at a time
-- Copy and paste each CREATE OR REPLACE VIEW statement separately
-- Execute in this order:
--   1. Execute v_radiation_treatments (lines 1591-1968)
--   2. Execute v_radiation_documents (lines 1982-2075)
-- ================================================================================

-- ================================================================================
-- 11. v_radiation_treatments - CONSOLIDATED PRIMARY VIEW
-- ================================================================================
-- Copy everything from CREATE OR REPLACE VIEW to the semicolon ending this view
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


-- ################################################################################
-- ################################################################################
-- 12. v_radiation_documents - DOCUMENT REFERENCES FOR NLP EXTRACTION
-- ################################################################################
-- ################################################################################
-- Copy everything from CREATE OR REPLACE VIEW to the semicolon ending this view
-- Execute this SECOND (after v_radiation_treatments completes successfully)
-- Consolidates document_reference records with priority scoring
-- Replaces need to query multiple note views separately
-- ################################################################################

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

-- VERIFICATION QUERIES (Run these to test views)
-- ================================================================================

-- Test 1: Count patients in each view
SELECT 'v_patient_demographics' as view_name, COUNT(DISTINCT patient_fhir_id) as patient_count FROM fhir_prd_db.v_patient_demographics
UNION ALL
SELECT 'v_problem_list_diagnoses', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_problem_list_diagnoses
UNION ALL
SELECT 'v_procedures', COUNT(DISTINCT proc_subject_reference) FROM fhir_prd_db.v_procedures
UNION ALL
SELECT 'v_medications', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_medications
UNION ALL
SELECT 'v_imaging', COUNT(DISTINCT patient_id) FROM fhir_prd_db.v_imaging
UNION ALL
SELECT 'v_encounters', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_encounters
UNION ALL
SELECT 'v_measurements', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_measurements
UNION ALL
SELECT 'v_binary_files', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_binary_files
UNION ALL
SELECT 'v_molecular_tests', COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_molecular_tests;

-- Test 2: Sample single patient data (replace with actual patient ID)
SELECT * FROM fhir_prd_db.v_patient_demographics WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT * FROM fhir_prd_db.v_procedures WHERE proc_subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3' LIMIT 10;
SELECT * FROM fhir_prd_db.v_imaging WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3' LIMIT 10;

-- Test 3: Row count per view (for single patient)
SELECT COUNT(*) as demographics_rows FROM fhir_prd_db.v_patient_demographics WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as diagnosis_rows FROM fhir_prd_db.v_problem_list_diagnoses WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as procedure_rows FROM fhir_prd_db.v_procedures WHERE proc_subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as medication_rows FROM fhir_prd_db.v_medications WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as imaging_rows FROM fhir_prd_db.v_imaging WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as encounter_rows FROM fhir_prd_db.v_encounters WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as measurement_rows FROM fhir_prd_db.v_measurements WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT COUNT(*) as binary_file_rows FROM fhir_prd_db.v_binary_files WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
