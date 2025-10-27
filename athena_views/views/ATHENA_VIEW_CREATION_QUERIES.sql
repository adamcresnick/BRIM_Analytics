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
-- V_PROCEDURES_TUMOR - Tumor Surgery Classification View
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
-- 6A. ENCOUNTERS VIEW (ENHANCED)
-- ================================================================================
-- Source: extract_all_encounters_metadata.py
-- Output: encounters.csv
-- Description: All encounters with types, reasons, diagnoses, appointment links,
--              service type coding, and locations
-- Updated: 2025-10-18 - Added missing subtables to match Python extraction
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
    e.period_start,
    e.period_end,
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
-- 6B. APPOINTMENTS VIEW
-- ================================================================================
-- Source: extract_all_encounters_metadata.py
-- Output: appointments.csv
-- Description: All appointments with participant details
-- Created: 2025-10-18 - New view to match Python extraction
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_appointments AS
SELECT DISTINCT
    a.id as appointment_fhir_id,
    TRY(CAST(SUBSTR(a.start, 1, 10) AS DATE)) as appointment_date,
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(a.start, 1, 10) AS DATE)))) as age_at_appointment_days,

    -- Appointment fields (appt_ prefix matching Python output)
    a.id as appt_id,
    a.status as appt_status,
    a.appointment_type_text as appt_appointment_type_text,
    a.description as appt_description,
    a.start as appt_start,
    a."end" as appt_end,
    a.minutes_duration as appt_minutes_duration,
    a.created as appt_created,
    a.comment as appt_comment,
    a.patient_instruction as appt_patient_instruction,
    a.cancelation_reason_text as appt_cancelation_reason_text,
    a.priority as appt_priority,

    -- Participant fields (ap_ prefix matching Python output)
    ap.participant_actor_reference as ap_participant_actor_reference,
    ap.participant_actor_type as ap_participant_actor_type,
    ap.participant_required as ap_participant_required,
    ap.participant_status as ap_participant_status,
    ap.participant_period_start as ap_participant_period_start,
    ap.participant_period_end as ap_participant_period_end

FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
LEFT JOIN fhir_prd_db.patient_access pa
    ON ap.participant_actor_reference = CONCAT('Patient/', pa.id)
WHERE ap.participant_actor_reference LIKE 'Patient/%'
ORDER BY a.start;


-- ================================================================================
-- 6C. VISITS UNIFIED VIEW (APPOINTMENTS + ENCOUNTERS)
-- ================================================================================
-- Created: 2025-10-18
-- Purpose: Unified view showing both appointments and encounters with completion status
-- Description: Combines appointment scheduling with actual encounter occurrences
--              to enable analysis of scheduled vs walk-in visits, no-shows, etc.
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_visits_unified AS
WITH appointment_encounter_links AS (
    -- Map appointments to their corresponding encounters
    SELECT DISTINCT
        SUBSTRING(ea.appointment_reference, 13) as appointment_id,  -- Remove "Appointment/" prefix
        ea.encounter_id,
        e.status as encounter_status,
        e.period_start as encounter_start,
        e.period_end as encounter_end
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
        CAST(a.start AS VARCHAR) as appointment_start,
        CAST(a."end" AS VARCHAR) as appointment_end,
        CAST(a.minutes_duration AS VARCHAR) as appointment_duration_minutes,
        CAST(a.cancelation_reason_text AS VARCHAR) as cancelation_reason_text,
        CAST(a.description AS VARCHAR) as appointment_description,

        -- Linked encounter details
        CAST(ael.encounter_id AS VARCHAR) as encounter_id,
        CAST(ael.encounter_status AS VARCHAR) as encounter_status,
        CAST(ael.encounter_start AS VARCHAR) as encounter_start,
        CAST(ael.encounter_end AS VARCHAR) as encounter_end,

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
        CAST(NULL AS VARCHAR) as appointment_start,
        CAST(NULL AS VARCHAR) as appointment_end,
        CAST(NULL AS VARCHAR) as appointment_duration_minutes,
        CAST(NULL AS VARCHAR) as cancelation_reason_text,
        CAST(NULL AS VARCHAR) as appointment_description,

        -- Encounter details
        CAST(e.id AS VARCHAR) as encounter_id,
        CAST(e.status AS VARCHAR) as encounter_status,
        CAST(e.period_start AS VARCHAR) as encounter_start,
        CAST(e.period_end AS VARCHAR) as encounter_end,

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
)
-- Combine both appointment-based and walk-in encounters
SELECT
    patient_fhir_id,

    -- Visit identifiers
    appointment_fhir_id,
    encounter_id,

    -- Visit classification
    visit_type,
    appointment_completed,
    encounter_occurred,
    source,

    -- Appointment details
    appointment_status,
    appointment_type_text,
    appointment_start,
    appointment_end,
    appointment_duration_minutes,
    cancelation_reason_text,
    appointment_description,

    -- Encounter details
    encounter_status,
    encounter_start,
    encounter_end,

    -- Calculate age at visit (use appointment or encounter date)
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(COALESCE(appointment_start, encounter_start), 1, 10) AS DATE)))) as age_at_visit_days,

    -- Visit date (earliest of appointment or encounter)
    TRY(CAST(SUBSTR(COALESCE(appointment_start, encounter_start), 1, 10) AS DATE)) as visit_date

FROM (
    SELECT * FROM appointments_with_encounters
    UNION ALL
    SELECT * FROM encounters_without_appointments
) combined
LEFT JOIN fhir_prd_db.patient_access pa ON combined.patient_fhir_id = pa.id

ORDER BY patient_fhir_id, visit_date, appointment_start, encounter_start;


-- ================================================================================
-- 6D. IMAGING-CORTICOSTEROID TEMPORAL ANALYSIS VIEW
-- ================================================================================
-- Created: 2025-10-18
-- Purpose: Capture corticosteroid use at time of imaging studies
-- Clinical Context: Corticosteroids (esp. dexamethasone) mask tumor progression
--                   on brain imaging by reducing edema and contrast enhancement.
--                   RANO criteria require documenting steroid use for response assessment.
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
        END as medication_start_datetime,

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
        END as medication_stop_datetime,

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
-- VERIFICATION QUERIES FOR v_imaging_corticosteroid_use
-- ================================================================================

-- 1. Overall corticosteroid exposure at imaging
SELECT
    COUNT(DISTINCT imaging_procedure_id) as total_imaging_studies,
    COUNT(DISTINCT CASE WHEN on_corticosteroid = true THEN imaging_procedure_id END) as on_corticosteroid_count,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN on_corticosteroid = true THEN imaging_procedure_id END) /
          NULLIF(COUNT(DISTINCT imaging_procedure_id), 0), 1) as percent_on_corticosteroid
FROM fhir_prd_db.v_imaging_corticosteroid_use;

-- 2. Corticosteroid type distribution
SELECT
    corticosteroid_generic_name,
    COUNT(DISTINCT imaging_procedure_id) as imaging_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_imaging_corticosteroid_use
WHERE on_corticosteroid = true
GROUP BY corticosteroid_generic_name
ORDER BY imaging_count DESC;

-- 3. Brain MRI specific (most clinically relevant)
SELECT
    COUNT(DISTINCT imaging_procedure_id) as total_brain_mris,
    COUNT(DISTINCT CASE WHEN on_corticosteroid = true THEN imaging_procedure_id END) as on_corticosteroid,
    COUNT(DISTINCT CASE WHEN corticosteroid_generic_name = 'dexamethasone' THEN imaging_procedure_id END) as on_dexamethasone,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN on_corticosteroid = true THEN imaging_procedure_id END) /
          NULLIF(COUNT(DISTINCT imaging_procedure_id), 0), 1) as percent_on_steroids
FROM fhir_prd_db.v_imaging_corticosteroid_use
WHERE imaging_modality = 'MRI'
  AND (LOWER(imaging_procedure) LIKE '%brain%' OR LOWER(imaging_procedure) LIKE '%head%');

-- 4. Temporal relationship distribution
SELECT
    temporal_relationship,
    COUNT(DISTINCT imaging_procedure_id) as imaging_count
FROM fhir_prd_db.v_imaging_corticosteroid_use
WHERE corticosteroid_medication_fhir_id IS NOT NULL
GROUP BY temporal_relationship
ORDER BY imaging_count DESC;

-- 5. Multiple concurrent corticosteroids
SELECT
    total_corticosteroids_count,
    COUNT(DISTINCT imaging_procedure_id) as imaging_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_imaging_corticosteroid_use
WHERE total_corticosteroids_count > 0
GROUP BY total_corticosteroids_count
ORDER BY total_corticosteroids_count;

-- 6. Detection method effectiveness
SELECT
    detection_method,
    COUNT(*) as medication_count
FROM fhir_prd_db.v_imaging_corticosteroid_use
WHERE corticosteroid_medication_fhir_id IS NOT NULL
GROUP BY detection_method;

-- 7. Sample patient data (for validation)
SELECT
    imaging_date,
    imaging_modality,
    imaging_procedure,
    on_corticosteroid,
    corticosteroid_generic_name,
    corticosteroid_rxnorm_cui,
    temporal_relationship,
    total_corticosteroids_count
FROM fhir_prd_db.v_imaging_corticosteroid_use
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY imaging_date DESC;


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
    dr.date as dr_date,
    dr.description as dr_description,
    dr.context_period_start as dr_context_period_start,
    dr.context_period_end as dr_context_period_end,
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

    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(dr.date, 1, 10) AS DATE)))) as age_at_document_days

FROM fhir_prd_db.document_reference dr
LEFT JOIN document_contexts denc ON dr.id = denc.document_reference_id
LEFT JOIN document_categories dcat ON dr.id = dcat.document_reference_id
LEFT JOIN document_type_coding dtc ON dr.id = dtc.document_reference_id
LEFT JOIN fhir_prd_db.document_reference_content dcont ON dr.id = dcont.document_reference_id
LEFT JOIN fhir_prd_db.patient pa ON dr.subject_reference = CONCAT('Patient/', pa.id)
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


-- ================================================================================
-- ================================================================================
-- HYDROCEPHALUS VIEWS (3 VIEWS)
-- ================================================================================
-- ================================================================================
-- Added: October 18, 2025
-- Purpose: Comprehensive hydrocephalus and shunt management tracking
-- Views: v_hydrocephalus_diagnosis, v_hydrocephalus_procedures, v_hydrocephalus_documents
-- Coverage: 5,735 diagnoses, 1,196 procedures, document references for NLP
-- CBTN Fields: 21/23 (91% coverage)
-- ================================================================================

-- ================================================================================
-- HYDROCEPHALUS VIEWS - PRODUCTION READY
-- ================================================================================
-- Date: October 18, 2025
-- Version: 3.0 (Final - All Sub-Schemas + Document References)
-- Database: fhir_prd_db
--
-- USAGE: Copy and paste each CREATE VIEW statement into Athena console
--        Views are independent and can be created in any order
--
-- DATA COVERAGE:
--   - 5,735 hydrocephalus diagnoses (condition + sub-schemas)
--   - 1,196 shunt procedures
--   - 1,439 procedure reason codes
--   - 207 procedure body sites
--   - 237 medications with hydrocephalus indication
--   - 18,920 service requests for hydrocephalus
--   - Document references for NLP extraction (operative reports, consult notes)
--
-- CBTN COVERAGE: 21/23 fields (91% structured coverage)
--
-- STANDARDIZATION:
--   ✅ All dates append 'T00:00:00Z' if date-only (10 characters)
--   ✅ Consistent patient_fhir_id naming across all views
--   ✅ Field prefixes for data provenance (cond_, proc_, prc_, pbs_, doc_, etc.)
--   ✅ Document reference view for NLP extraction
-- ================================================================================


-- ================================================================================
-- VIEW 1: v_hydrocephalus_diagnosis
-- ================================================================================
-- Purpose: Comprehensive hydrocephalus diagnosis tracking with imaging and classification
-- Data Sources: condition, condition_code_coding, condition_category,
--               diagnostic_report, service_request_reason_code
-- CBTN Fields: hydro_yn, hydro_event_date, hydro_method_diagnosed,
--              medical_conditions_present_at_event(11)
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
    hc.onset_date_time as cond_onset_datetime,
    hc.onset_period_start as cond_onset_period_start,
    hc.onset_period_end as cond_onset_period_end,
    hc.abatement_date_time as cond_abatement_datetime,
    hc.recorded_date as cond_recorded_date,

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
    img.first_imaging_date as img_first_date,
    img.most_recent_imaging_date as img_most_recent_date,

    -- Service request fields (sr_ prefix)
    io.total_imaging_orders as sr_total_orders,
    io.ct_orders as sr_ct_orders,
    io.mri_orders as sr_mri_orders,
    io.first_order_date as sr_first_order_date,

    -- ============================================================================
    -- CBTN FIELD MAPPINGS
    -- ============================================================================

    -- hydro_yn (always true for this view)
    true as hydro_yn,

    -- hydro_event_date (onset date)
    COALESCE(hc.onset_date_time, hc.onset_period_start, hc.recorded_date) as hydro_event_date,

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
-- VIEW 2: v_hydrocephalus_procedures
-- ================================================================================
-- Purpose: Comprehensive hydrocephalus procedure tracking with all sub-schemas
-- Data Sources: procedure (all sub-schemas), device, encounter, medication_request
-- CBTN Fields: shunt_required, hydro_intervention, hydro_surgical_management,
--              hydro_shunt_programmable, hydro_nonsurg_management
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
        CASE
            WHEN LENGTH(p.performed_date_time) = 10 THEN p.performed_date_time || 'T00:00:00Z'
            ELSE p.performed_date_time
        END as proc_performed_datetime,
        CASE
            WHEN LENGTH(p.performed_period_start) = 10 THEN p.performed_period_start || 'T00:00:00Z'
            ELSE p.performed_period_start
        END as proc_period_start,
        CASE
            WHEN LENGTH(p.performed_period_end) = 10 THEN p.performed_period_end || 'T00:00:00Z'
            ELSE p.performed_period_end
        END as proc_period_end,

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
    pe.encounter_start as enc_start,
    pe.encounter_end as enc_end,
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
    COALESCE(sp.proc_performed_datetime, sp.proc_period_start) as hydro_event_date,

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
-- END OF HYDROCEPHALUS VIEWS
-- ================================================================================
--
-- DEPLOYMENT VALIDATION:
--   1. Run: SELECT COUNT(*) FROM fhir_prd_db.v_hydrocephalus_diagnosis;
--      Expected: ~5,735 diagnosis records
--
--   2. Run: SELECT COUNT(*) FROM fhir_prd_db.v_hydrocephalus_procedures;
--      Expected: ~1,196 procedure records
--
--   3. Run: SELECT COUNT(DISTINCT patient_fhir_id) FROM fhir_prd_db.v_hydrocephalus_diagnosis;
--      Expected: Check unique patient count
--
-- CBTN FIELD COVERAGE: 21/23 fields (91%)
--   HIGH Coverage (14 fields): All diagnosis, procedure, device, encounter fields
--   MEDIUM Coverage (7 fields): Medications, imaging validation
--   LOW Coverage (2 fields): Free-text "Other" fields (require NLP)
-- ================================================================================


-- ================================================================================
-- HYDROCEPHALUS VIEWS VERIFICATION QUERIES
-- ================================================================================

-- Test 1: Count records in hydrocephalus views
SELECT 'v_hydrocephalus_diagnosis' as view_name, COUNT(*) as total_records, COUNT(DISTINCT patient_fhir_id) as unique_patients FROM fhir_prd_db.v_hydrocephalus_diagnosis
UNION ALL
SELECT 'v_hydrocephalus_procedures', COUNT(*) as total_records, COUNT(DISTINCT patient_fhir_id) as unique_patients FROM fhir_prd_db.v_hydrocephalus_procedures
UNION ALL
SELECT 'v_hydrocephalus_documents', COUNT(*) as total_records, COUNT(DISTINCT patient_fhir_id) as unique_patients FROM fhir_prd_db.v_hydrocephalus_documents;

-- Test 2: Data quality checks for hydrocephalus diagnosis view
SELECT 
    COUNT(*) as total_diagnoses,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(DISTINCT CASE WHEN has_icd10_code = true THEN patient_fhir_id END) as patients_with_icd10,
    COUNT(DISTINCT CASE WHEN has_onset_date = true THEN patient_fhir_id END) as patients_with_onset_date,
    COUNT(DISTINCT CASE WHEN has_imaging_documentation = true THEN patient_fhir_id END) as patients_with_imaging,
    COUNT(DISTINCT CASE WHEN cat_is_problem_list = true THEN patient_fhir_id END) as patients_on_problem_list
FROM fhir_prd_db.v_hydrocephalus_diagnosis;

-- Test 3: Data quality checks for hydrocephalus procedures view
SELECT 
    COUNT(*) as total_procedures,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(DISTINCT CASE WHEN has_procedure_date = true THEN patient_fhir_id END) as patients_with_date,
    COUNT(DISTINCT CASE WHEN validated_by_reason_code = true THEN patient_fhir_id END) as validated_by_reason_code,
    COUNT(DISTINCT CASE WHEN has_body_site_documentation = true THEN patient_fhir_id END) as patients_with_body_site,
    COUNT(DISTINCT CASE WHEN has_device_record = true THEN patient_fhir_id END) as patients_with_device,
    COUNT(DISTINCT CASE WHEN has_nonsurgical_treatment = true THEN patient_fhir_id END) as patients_with_medications
FROM fhir_prd_db.v_hydrocephalus_procedures;

-- Test 4: Hydrocephalus type distribution
SELECT 
    cond_hydro_type as hydrocephalus_type,
    COUNT(*) as diagnosis_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_hydrocephalus_diagnosis
GROUP BY cond_hydro_type
ORDER BY diagnosis_count DESC;

-- Test 5: Shunt procedure type distribution
SELECT 
    proc_shunt_type as shunt_type,
    proc_category as procedure_category,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_hydrocephalus_procedures
GROUP BY proc_shunt_type, proc_category
ORDER BY procedure_count DESC;

-- Test 6: Document extraction priority distribution
SELECT 
    extraction_priority,
    document_category,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_hydrocephalus_documents
GROUP BY extraction_priority, document_category
ORDER BY extraction_priority, document_count DESC;

-- Test 7: Single patient comprehensive hydrocephalus data (replace with actual patient ID)
SELECT * FROM fhir_prd_db.v_hydrocephalus_diagnosis WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT * FROM fhir_prd_db.v_hydrocephalus_procedures WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
SELECT * FROM fhir_prd_db.v_hydrocephalus_documents WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3' ORDER BY extraction_priority;


-- ================================================================================
-- SECTION 6: AUTOLOGOUS STEM CELL TRANSPLANT VIEWS
-- ================================================================================
-- Purpose: Detect and validate autologous stem cell transplant events
-- Coverage: Multi-source detection (condition, procedure, observation, CD34 counts)
-- Key Sources:
--   - Condition table: Transplant status codes (Z94.84, Z94.81, 108631000119101)
--   - Procedure table: Transplant procedures (CPT 38241)
--   - Observation table: Transplant dates and CD34+ counts
-- Data Quality: Confidence scoring (high/medium/low) based on code specificity
-- Date: October 18, 2025
-- ================================================================================

-- ================================================================================
-- VIEW 6.1: v_autologous_stem_cell_transplant
-- ================================================================================
-- Purpose: Comprehensive autologous stem cell transplant detection and validation
-- Data Sources: condition, procedure, observation (CD34 counts, transplant dates)
-- Confidence Levels:
--   - High: ICD-10 108631000119101, CPT 38241
--   - Medium: Free text "autologous" mentions
--   - Low: General transplant status codes
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
    tc.condition_onset as cond_onset_datetime,
    tc.recorded_date as cond_recorded_datetime,
    tc.confirmed_autologous as cond_autologous_flag,
    tc.confidence_level as cond_confidence,

    -- Procedure data
    tp.procedure_id as proc_id,
    tp.procedure_description as proc_description,
    tp.cpt_code as proc_cpt_code,
    tp.procedure_date as proc_performed_datetime,
    tp.performed_period_start as proc_period_start,
    tp.confirmed_autologous as proc_autologous_flag,
    tp.confidence_level as proc_confidence,

    -- Transplant date from observation
    tdo.transplant_date as obs_transplant_datetime,
    tdo.transplant_date_value as obs_transplant_value,

    -- CD34 count data (validates stem cell collection)
    cd34.collection_date as cd34_collection_datetime,
    cd34.cd34_count as cd34_count_value,
    cd34.unit as cd34_unit,

    -- Best available transplant date
    COALESCE(tp.procedure_date, tdo.transplant_date, tc.condition_onset) as transplant_datetime,

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
-- VERIFICATION QUERIES - AUTOLOGOUS STEM CELL TRANSPLANT VIEWS
-- ================================================================================

-- Test 1: Overall patient counts
SELECT
    COUNT(DISTINCT patient_fhir_id) as total_patients,
    SUM(CASE WHEN confirmed_autologous = true THEN 1 ELSE 0 END) as confirmed_autologous_patients,
    SUM(CASE WHEN has_condition_data = true THEN 1 ELSE 0 END) as patients_with_condition,
    SUM(CASE WHEN has_procedure_data = true THEN 1 ELSE 0 END) as patients_with_procedure,
    SUM(CASE WHEN has_transplant_date_obs = true THEN 1 ELSE 0 END) as patients_with_obs_date,
    SUM(CASE WHEN has_cd34_data = true THEN 1 ELSE 0 END) as patients_with_cd34
FROM fhir_prd_db.v_autologous_stem_cell_transplant;

-- Test 2: Data completeness distribution
SELECT
    data_completeness_score,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    ROUND(COUNT(DISTINCT patient_fhir_id) * 100.0 / SUM(COUNT(DISTINCT patient_fhir_id)) OVER (), 2) as percentage
FROM fhir_prd_db.v_autologous_stem_cell_transplant
GROUP BY data_completeness_score
ORDER BY data_completeness_score DESC;

-- Test 3: Confidence level distribution
SELECT
    overall_confidence,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    SUM(CASE WHEN confirmed_autologous = true THEN 1 ELSE 0 END) as confirmed_autologous_count
FROM fhir_prd_db.v_autologous_stem_cell_transplant
GROUP BY overall_confidence
ORDER BY
    CASE overall_confidence
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
    END;

-- Test 4: ICD-10 code distribution
SELECT
    cond_icd10_code,
    cond_transplant_status,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_autologous_stem_cell_transplant
WHERE cond_icd10_code IS NOT NULL
GROUP BY cond_icd10_code, cond_transplant_status
ORDER BY patient_count DESC;

-- Test 5: CPT code distribution
SELECT
    proc_cpt_code,
    proc_description,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_autologous_stem_cell_transplant
WHERE proc_cpt_code IS NOT NULL
GROUP BY proc_cpt_code, proc_description
ORDER BY patient_count DESC;

-- Test 6: CD34 count summary statistics
SELECT
    COUNT(DISTINCT patient_fhir_id) as patients_with_cd34,
    COUNT(*) as total_cd34_records,
    AVG(TRY_CAST(cd34_count_value AS DOUBLE)) as avg_cd34_count,
    MIN(TRY_CAST(cd34_count_value AS DOUBLE)) as min_cd34_count,
    MAX(TRY_CAST(cd34_count_value AS DOUBLE)) as max_cd34_count
FROM fhir_prd_db.v_autologous_stem_cell_transplant
WHERE cd34_count_value IS NOT NULL;

-- Test 7: Single patient comprehensive transplant data (replace with actual patient ID)
SELECT * FROM fhir_prd_db.v_autologous_stem_cell_transplant
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY transplant_datetime;


-- ================================================================================
-- SECTION 7: CONCOMITANT MEDICATIONS VIEWS
-- ================================================================================
-- Purpose: Capture concomitant medications administered during chemotherapy windows
-- Coverage: Temporal overlap analysis between chemotherapy and supportive care meds
-- Key Sources:
--   - medication_request: Medication orders with start/stop dates
--   - medication_request_code_coding: RxNorm codes for medications
-- Key Features:
--   - Chemotherapy agent identification with time windows
--   - Conmed categorization (antiemetic, corticosteroid, growth_factor, etc.)
--   - Temporal overlap calculation with duration metrics
--   - Data quality scoring based on date source
-- Date: October 18, 2025
-- ================================================================================

-- ================================================================================
-- VIEW 7.1: v_concomitant_medications
-- ================================================================================
-- Purpose: Comprehensive view of concomitant medications during chemotherapy
-- Data Sources: medication_request, medication_request_code_coding
-- Overlap Types:
--   - during_chemo: Conmed entirely within chemo window
--   - started_during_chemo: Conmed started during chemo
--   - stopped_during_chemo: Conmed stopped during chemo
--   - spans_chemo: Conmed spans entire chemo period
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
-- Step 1: Get chemotherapy medications and time windows from v_chemo_medications
-- ================================================================================
-- Uses the authoritative v_chemo_medications view which:
--   - Leverages comprehensive drugs.csv reference (2,968 chemotherapy drugs)
--   - Includes therapeutic normalization (brand→generic)
--   - Excludes supportive care medications
--   - Validated with 968 patients, 0 issues
-- ================================================================================
chemotherapy_agents AS (
    SELECT
        patient_fhir_id,
        medication_request_fhir_id as medication_fhir_id,
        medication_rxnorm_code as rxnorm_cui,
        chemo_therapeutic_normalized as medication_name,  -- Use normalized name for consistency
        medication_status as status,
        medication_intent as intent,

        -- Use standardized datetime fields from v_chemo_medications
        -- These are already in ISO8601 format with proper handling
        medication_start_date as start_datetime,
        medication_stop_date as stop_datetime,
        medication_authored_date as authored_datetime,

        -- Date source for quality tracking
        CASE
            WHEN medication_start_date IS NOT NULL THEN 'timing_bounds'
            WHEN medication_stop_date IS NOT NULL THEN 'dispense_period'
            WHEN medication_authored_date IS NOT NULL THEN 'authored_on'
            ELSE 'missing'
        END as date_source

    FROM fhir_prd_db.v_chemo_medications
    -- v_chemo_medications is already filtered to chemotherapy medications
    -- Just ensure we have valid time windows for temporal overlap calculation
    WHERE medication_start_date IS NOT NULL
),

-- ================================================================================
-- Step 2: Identify all other medications (potential concomitant medications)
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
        -- Chemotherapy exclusion handled in the final join
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
    ca.start_datetime as chemo_start_datetime,
    ca.stop_datetime as chemo_stop_datetime,
    ca.authored_datetime as chemo_authored_datetime,

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
    am.start_datetime as conmed_start_datetime,
    am.stop_datetime as conmed_stop_datetime,
    am.authored_datetime as conmed_authored_datetime,

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
    CASE
        WHEN ca.start_datetime >= am.start_datetime THEN ca.start_datetime
        ELSE am.start_datetime
    END as overlap_start_datetime,

    -- Overlap stop (earlier of the two stop dates, or NULL if either is NULL)
    CASE
        WHEN ca.stop_datetime IS NULL OR am.stop_datetime IS NULL THEN NULL
        WHEN ca.stop_datetime <= am.stop_datetime THEN ca.stop_datetime
        ELSE am.stop_datetime
    END as overlap_stop_datetime,

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

ORDER BY ca.patient_fhir_id, ca.start_datetime, am.start_datetime;


-- ================================================================================
-- VERIFICATION QUERIES - CONCOMITANT MEDICATIONS VIEWS
-- ================================================================================

-- Test 1: Overall patient and medication counts
SELECT
    COUNT(DISTINCT patient_fhir_id) as total_patients,
    COUNT(DISTINCT chemo_medication_fhir_id) as unique_chemo_meds,
    COUNT(DISTINCT conmed_medication_fhir_id) as unique_conmed_meds,
    COUNT(*) as total_chemo_conmed_pairs
FROM fhir_prd_db.v_concomitant_medications;

-- Test 2: Most common chemotherapy agents
SELECT
    chemo_rxnorm_cui,
    chemo_medication_name,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(DISTINCT chemo_medication_fhir_id) as order_count
FROM fhir_prd_db.v_concomitant_medications
WHERE chemo_rxnorm_cui IS NOT NULL
GROUP BY chemo_rxnorm_cui, chemo_medication_name
ORDER BY patient_count DESC
LIMIT 20;

-- Test 3: Concomitant medication category distribution
SELECT
    conmed_category,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(DISTINCT conmed_medication_fhir_id) as unique_conmeds,
    COUNT(*) as total_conmed_records
FROM fhir_prd_db.v_concomitant_medications
GROUP BY conmed_category
ORDER BY total_conmed_records DESC;

-- Test 4: Most common concomitant medications by RxNorm
SELECT
    conmed_category,
    conmed_rxnorm_cui,
    conmed_medication_name,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(*) as usage_count
FROM fhir_prd_db.v_concomitant_medications
WHERE conmed_rxnorm_cui IS NOT NULL
GROUP BY conmed_category, conmed_rxnorm_cui, conmed_medication_name
ORDER BY usage_count DESC
LIMIT 30;

-- Test 5: Overlap type distribution
SELECT
    overlap_type,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(*) as record_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM fhir_prd_db.v_concomitant_medications
GROUP BY overlap_type
ORDER BY record_count DESC;

-- Test 6: Average conmeds per chemotherapy cycle
SELECT
    patient_fhir_id,
    chemo_medication_fhir_id,
    chemo_medication_name,
    chemo_start_datetime,
    COUNT(DISTINCT conmed_medication_fhir_id) as conmed_count
FROM fhir_prd_db.v_concomitant_medications
GROUP BY patient_fhir_id, chemo_medication_fhir_id, chemo_medication_name, chemo_start_datetime
ORDER BY conmed_count DESC
LIMIT 20;

-- Test 7: Data quality distribution
SELECT
    date_quality,
    has_chemo_rxnorm,
    has_conmed_rxnorm,
    COUNT(*) as record_count
FROM fhir_prd_db.v_concomitant_medications
GROUP BY date_quality, has_chemo_rxnorm, has_conmed_rxnorm
ORDER BY record_count DESC;

-- Test 8: Chemotherapy duration statistics
SELECT
    chemo_medication_name,
    COUNT(*) as cycle_count,
    AVG(chemo_duration_days) as avg_duration_days,
    MIN(chemo_duration_days) as min_duration_days,
    MAX(chemo_duration_days) as max_duration_days
FROM fhir_prd_db.v_concomitant_medications
WHERE chemo_duration_days IS NOT NULL
GROUP BY chemo_medication_name
ORDER BY cycle_count DESC
LIMIT 20;

-- Test 9: Single patient comprehensive conmed data (replace with actual patient ID)
SELECT
    chemo_medication_name,
    chemo_start_datetime,
    chemo_stop_datetime,
    conmed_category,
    conmed_medication_name,
    conmed_start_datetime,
    conmed_stop_datetime,
    overlap_type,
    overlap_duration_days
FROM fhir_prd_db.v_concomitant_medications
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY chemo_start_datetime, conmed_category, conmed_start_datetime;


-- ================================================================================
-- SECTION 8: AUTOLOGOUS STEM CELL COLLECTION
-- ================================================================================
-- Created: 2025-10-18
-- Purpose: Comprehensive view capturing autologous stem cell collection events
--          separate from transplant procedures. Includes collection procedures,
--          CD34+ cell counts, mobilization agents, and product quality metrics.
--
-- Data Sources:
--   - procedure: Collection procedures (CPT 38231 - Apheresis)
--   - observation: CD34+ cell counts and product quality
--   - medication_request: Mobilization agents (G-CSF, Plerixafor)
--   - specimen: Product storage and processing info
--
-- Key Variables:
--   - Collection date and method
--   - CD34+ counts (adequate ≥5×10⁶/kg)
--   - Mobilization regimen
--   - Product quality and viability
--
-- Temporal Sequence: Mobilization → Collection → Conditioning → Transplant
-- ================================================================================


CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_collection AS

WITH collection_procedures AS (
    -- Identify autologous stem cell collection procedures
    SELECT DISTINCT
        p.subject_reference as patient_fhir_id,
        p.id as procedure_fhir_id,
        p.code_text as procedure_description,

        -- Standardize collection date
        CASE
            WHEN LENGTH(p.performed_date_time) = 10
            THEN p.performed_date_time || 'T00:00:00Z'
            ELSE p.performed_date_time
        END as collection_datetime,

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
        CASE
            WHEN LENGTH(o.effective_date_time) = 10
            THEN o.effective_date_time || 'T00:00:00Z'
            ELSE o.effective_date_time
        END as measurement_datetime,

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
        END as mobilization_start_datetime,

        -- Standardize end date
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
        END as mobilization_stop_datetime,

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

        CASE
            WHEN LENGTH(o.effective_date_time) = 10
            THEN o.effective_date_time || 'T00:00:00Z'
            ELSE o.effective_date_time
        END as measurement_datetime,

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
    cd34.measurement_datetime as cd34_measurement_datetime,
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
    pq.measurement_datetime as quality_measurement_datetime,

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
-- VERIFICATION QUERIES FOR v_autologous_stem_cell_collection
-- ================================================================================

-- 1. Overall collection event counts
SELECT
    COUNT(DISTINCT patient_fhir_id) as total_patients_with_collections,
    COUNT(DISTINCT collection_procedure_fhir_id) as total_collection_procedures,
    COUNT(DISTINCT cd34_observation_fhir_id) as total_cd34_measurements,
    COUNT(DISTINCT mobilization_medication_fhir_id) as total_mobilization_agents,
    COUNT(DISTINCT quality_observation_fhir_id) as total_quality_observations
FROM fhir_prd_db.v_autologous_stem_cell_collection;

-- 2. Data completeness distribution
SELECT
    data_completeness,
    COUNT(*) as record_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_autologous_stem_cell_collection
GROUP BY data_completeness
ORDER BY record_count DESC;

-- 3. CD34 adequacy distribution
SELECT
    cd34_adequacy,
    COUNT(*) as measurement_count,
    AVG(CAST(cd34_count AS DOUBLE)) as avg_cd34_count,
    MIN(CAST(cd34_count AS DOUBLE)) as min_cd34_count,
    MAX(CAST(cd34_count AS DOUBLE)) as max_cd34_count
FROM fhir_prd_db.v_autologous_stem_cell_collection
WHERE cd34_count IS NOT NULL
GROUP BY cd34_adequacy
ORDER BY avg_cd34_count DESC;

-- 4. Mobilization agent usage
SELECT
    mobilization_agent_type,
    COUNT(*) as usage_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    AVG(days_from_mobilization_to_collection) as avg_days_to_collection,
    MIN(days_from_mobilization_to_collection) as min_days_to_collection,
    MAX(days_from_mobilization_to_collection) as max_days_to_collection
FROM fhir_prd_db.v_autologous_stem_cell_collection
WHERE mobilization_agent_type IS NOT NULL
GROUP BY mobilization_agent_type
ORDER BY usage_count DESC;

-- 5. Collection method distribution
SELECT
    collection_method,
    collection_cpt_code,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_autologous_stem_cell_collection
WHERE collection_procedure_fhir_id IS NOT NULL
GROUP BY collection_method, collection_cpt_code
ORDER BY procedure_count DESC;

-- 6. Product quality metrics summary
SELECT
    quality_metric_type,
    COUNT(*) as metric_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_autologous_stem_cell_collection
WHERE quality_observation_fhir_id IS NOT NULL
GROUP BY quality_metric_type
ORDER BY metric_count DESC;

-- 7. Temporal distribution of collections by year
SELECT
    YEAR(CAST(collection_datetime AS TIMESTAMP)) as collection_year,
    COUNT(DISTINCT collection_procedure_fhir_id) as collection_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_autologous_stem_cell_collection
WHERE collection_datetime IS NOT NULL
GROUP BY YEAR(CAST(collection_datetime AS TIMESTAMP))
ORDER BY collection_year;

-- 8. Sample patient-level summary (for validation)
SELECT
    patient_fhir_id,
    collection_datetime,
    collection_method,
    cd34_count,
    cd34_unit,
    cd34_adequacy,
    mobilization_agent_type,
    days_from_mobilization_to_collection,
    data_completeness
FROM fhir_prd_db.v_autologous_stem_cell_collection
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY collection_datetime, mobilization_start_datetime;


-- ================================================================================
-- SECTION 7: OPHTHALMOLOGY ASSESSMENTS VIEW
-- ================================================================================
-- Purpose: Comprehensive ophthalmology assessments for brain tumor patients
--          Captures visual acuity, visual fields, OCT, fundus exams, optic disc findings
-- Clinical context: Many pediatric brain tumor patients (esp. optic pathway gliomas,
--                   craniopharyngiomas) experience visual deficits requiring monitoring
-- Data sources: observation, procedure, service_request, diagnostic_report,
--               document_reference, encounter tables + sub-schema tables
--
-- Created: 2025-10-18
-- Based on: Exploratory analysis showing:
--   - 24,013 observations (315 patients)
--   - 2,345 procedures (410 patients)
--   - 4,137 service requests (631 patients)
--   - 3,731 diagnostic reports (637 patients)
--   - 731 document references (185 patients)
--   - 567 encounters (460 patients)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_ophthalmology_assessments AS

-- ============================================================
-- CTE 1: Visual Acuity Observations
-- ============================================================
WITH visual_acuity_obs AS (
    SELECT
        o.id as observation_fhir_id,
        SUBSTRING(o.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) as assessment_date,
        o.code_text as assessment_name,
        'visual_acuity' as assessment_category,
        'observation' as source_table,

        -- Value extraction (numeric or text)
        o.value_quantity_value as numeric_value,
        o.value_quantity_unit as value_unit,
        o.value_string as text_value,

        -- Multi-component observations (e.g., right/left eye separate)
        oc.component_code_text as component_name,
        oc.component_value_quantity_value as component_numeric_value,
        oc.component_value_quantity_unit as component_unit,

        -- Metadata
        o.status as observation_status,
        o.effective_date_time as full_datetime

    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE (
        -- Visual acuity search terms
        LOWER(o.code_text) LIKE '%visual%acuity%'
        OR LOWER(o.code_text) LIKE '%snellen%'
        OR LOWER(o.code_text) LIKE '%logmar%'
        OR LOWER(o.code_text) LIKE '%etdrs%'
        OR LOWER(o.code_text) LIKE '%hotv%'
        OR LOWER(o.code_text) LIKE '%lea%'
        OR LOWER(o.code_text) LIKE '%vision%screening%'
        OR LOWER(o.code_text) LIKE '%bcva%'
    )
),

-- ============================================================
-- CTE 2: Fundus/Optic Disc Observations
-- ============================================================
fundus_optic_disc_obs AS (
    SELECT
        o.id as observation_fhir_id,
        SUBSTRING(o.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) as assessment_date,
        o.code_text as assessment_name,

        -- Categorize by clinical finding
        CASE
            WHEN LOWER(o.code_text) LIKE '%papilledema%' THEN 'optic_disc_papilledema'
            WHEN LOWER(o.code_text) LIKE '%optic%disc%' OR LOWER(o.code_text) LIKE '%fundus%disc%' THEN 'optic_disc_exam'
            WHEN LOWER(o.code_text) LIKE '%fundus%macula%' THEN 'fundus_macula'
            WHEN LOWER(o.code_text) LIKE '%fundus%vessel%' THEN 'fundus_vessels'
            WHEN LOWER(o.code_text) LIKE '%fundus%vitreous%' THEN 'fundus_vitreous'
            WHEN LOWER(o.code_text) LIKE '%fundus%periphery%' THEN 'fundus_periphery'
            ELSE 'fundus_other'
        END as assessment_category,

        'observation' as source_table,
        o.value_quantity_value as numeric_value,
        o.value_quantity_unit as value_unit,
        o.value_string as text_value,
        oc.component_code_text as component_name,
        oc.component_value_quantity_value as component_numeric_value,
        oc.component_value_quantity_unit as component_unit,
        o.status as observation_status,
        o.effective_date_time as full_datetime

    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE (
        LOWER(o.code_text) LIKE '%fundus%'
        OR LOWER(o.code_text) LIKE '%optic%disc%'
        OR LOWER(o.code_text) LIKE '%papilledema%'
        OR LOWER(o.code_text) LIKE '%optic%pallor%'
        OR LOWER(o.code_text) LIKE '%optic%atrophy%'
        OR LOWER(o.code_text) LIKE '%cup%disc%'
    )
    AND NOT (LOWER(o.code_text) LIKE '%visual%acuity%')  -- Exclude already captured in visual_acuity_obs
),

-- ============================================================
-- CTE 3: Visual Field Procedures
-- ============================================================
visual_field_procedures AS (
    SELECT
        p.id as procedure_fhir_id,
        SUBSTRING(p.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) as assessment_date,
        p.code_text as assessment_name,
        'visual_field' as assessment_category,
        'procedure' as source_table,

        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,

        p.status as procedure_status,
        pc.code_coding_code as cpt_code,
        pc.code_coding_display as cpt_description,
        p.performed_date_time as full_datetime

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pc ON p.id = pc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%visual%field%'
        OR LOWER(p.code_text) LIKE '%perimetry%'
        OR LOWER(p.code_text) LIKE '%goldmann%'
        OR LOWER(p.code_text) LIKE '%humphrey%'
        -- CPT codes for visual fields
        OR pc.code_coding_code IN ('92081', '92082', '92083')
    )
),

-- ============================================================
-- CTE 4: OCT Procedures
-- ============================================================
oct_procedures AS (
    SELECT
        p.id as procedure_fhir_id,
        SUBSTRING(p.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) as assessment_date,
        p.code_text as assessment_name,

        -- Categorize OCT type
        CASE
            WHEN LOWER(p.code_text) LIKE '%optic%nerve%' THEN 'oct_optic_nerve'
            WHEN LOWER(p.code_text) LIKE '%retina%' THEN 'oct_retina'
            WHEN LOWER(p.code_text) LIKE '%macula%' THEN 'oct_macula'
            ELSE 'oct_unspecified'
        END as assessment_category,

        'procedure' as source_table,
        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,

        p.status as procedure_status,
        pc.code_coding_code as cpt_code,
        pc.code_coding_display as cpt_description,
        p.performed_date_time as full_datetime

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pc ON p.id = pc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%oct%'
        OR LOWER(p.code_text) LIKE '%optical%coherence%'
        OR LOWER(p.code_text) LIKE '%rnfl%'
        OR LOWER(p.code_text) LIKE '%ganglion%cell%'
        -- CPT codes for OCT
        OR pc.code_coding_code IN ('92133', '92134', '92133.999', '92134.999')
    )
),

-- ============================================================
-- CTE 5: Fundus Photography Procedures
-- ============================================================
fundus_photo_procedures AS (
    SELECT
        p.id as procedure_fhir_id,
        SUBSTRING(p.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) as assessment_date,
        p.code_text as assessment_name,
        'fundus_photography' as assessment_category,
        'procedure' as source_table,

        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,

        p.status as procedure_status,
        pc.code_coding_code as cpt_code,
        pc.code_coding_display as cpt_description,
        p.performed_date_time as full_datetime

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pc ON p.id = pc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%fundus%photo%'
        OR LOWER(p.code_text) LIKE '%fundus%imaging%'
        OR LOWER(p.code_text) LIKE '%retinal%photo%'
        -- CPT codes
        OR pc.code_coding_code IN ('92250', '92225', '92226', '92227', '92228')
    )
),

-- ============================================================
-- CTE 6: Ophthalmology Exam Procedures
-- ============================================================
ophthal_exam_procedures AS (
    SELECT
        p.id as procedure_fhir_id,
        SUBSTRING(p.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) as assessment_date,
        p.code_text as assessment_name,
        'ophthalmology_exam' as assessment_category,
        'procedure' as source_table,

        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,

        p.status as procedure_status,
        pc.code_coding_code as cpt_code,
        pc.code_coding_display as cpt_description,
        p.performed_date_time as full_datetime

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pc ON p.id = pc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%ophthal%exam%'
        OR LOWER(p.code_text) LIKE '%eye%exam%anes%'
        OR LOWER(p.code_text) LIKE '%optic%nerve%decompression%'
        OR LOWER(p.code_text) LIKE '%optic%glioma%'
        -- CPT codes for eye exams
        OR pc.code_coding_code IN ('92002', '92004', '92012', '92014', '92018')
    )
),

-- ============================================================
-- CTE 7: Service Requests (Orders)
-- ============================================================
ophthalmology_orders AS (
    SELECT
        sr.id as service_request_fhir_id,
        SUBSTRING(sr.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(sr.authored_on, 1, 10) AS DATE)) as order_date,
        sr.code_text as order_name,

        -- Categorize order type
        CASE
            WHEN LOWER(sr.code_text) LIKE '%visual%field%' THEN 'visual_field_order'
            WHEN LOWER(sr.code_text) LIKE '%oct%optic%' THEN 'oct_optic_nerve_order'
            WHEN LOWER(sr.code_text) LIKE '%oct%retina%' THEN 'oct_retina_order'
            WHEN LOWER(sr.code_text) LIKE '%ophthal%' THEN 'ophthalmology_order'
            ELSE 'other_eye_order'
        END as order_category,

        'service_request' as source_table,
        sr.status as order_status,
        sr.intent as order_intent,
        sr.authored_on as order_datetime

    FROM fhir_prd_db.service_request sr
    WHERE (
        LOWER(sr.code_text) LIKE '%ophthal%'
        OR LOWER(sr.code_text) LIKE '%visual%field%'
        OR LOWER(sr.code_text) LIKE '%oct%'
        OR LOWER(sr.code_text) LIKE '%optic%'
        OR LOWER(sr.code_text) LIKE '%eye%exam%'
    )
    AND NOT (LOWER(sr.code_text) LIKE '%poct%' OR LOWER(sr.code_text) LIKE '%glucose%')  -- Exclude non-ophthalmology
),

-- ============================================================
-- CTE 8: Diagnostic Reports
-- ============================================================
ophthalmology_reports AS (
    SELECT
        dr.id as diagnostic_report_fhir_id,
        SUBSTRING(dr.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(dr.effective_date_time, 1, 10) AS DATE)) as report_date,
        dr.code_text as report_name,

        -- Categorize report type
        CASE
            WHEN LOWER(dr.code_text) LIKE '%visual%field%' THEN 'visual_field_report'
            WHEN LOWER(dr.code_text) LIKE '%oct%optic%' THEN 'oct_optic_nerve_report'
            WHEN LOWER(dr.code_text) LIKE '%oct%retina%' THEN 'oct_retina_report'
            WHEN LOWER(dr.code_text) LIKE '%fundus%' THEN 'fundus_report'
            WHEN LOWER(dr.code_text) LIKE '%vision%screening%' THEN 'vision_screening_report'
            ELSE 'other_eye_report'
        END as report_category,

        'diagnostic_report' as source_table,
        dr.status as report_status,
        dr.effective_date_time as report_datetime

    FROM fhir_prd_db.diagnostic_report dr
    WHERE (
        LOWER(dr.code_text) LIKE '%ophthal%'
        OR LOWER(dr.code_text) LIKE '%visual%field%'
        OR LOWER(dr.code_text) LIKE '%oct%'
        OR LOWER(dr.code_text) LIKE '%fundus%'
        OR LOWER(dr.code_text) LIKE '%eye%'
        OR LOWER(dr.code_text) LIKE '%vision%screening%'
    )
    AND NOT (LOWER(dr.code_text) LIKE '%poct%' OR LOWER(dr.code_text) LIKE '%glucose%')  -- Exclude non-ophthalmology
),

-- ============================================================
-- CTE 9: Document References (Binary Files)
-- ============================================================
ophthalmology_documents AS (
    SELECT
        dref.id as document_reference_fhir_id,
        SUBSTRING(dref.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(dref.date, 1, 10) AS DATE)) as document_date,
        dref.description as document_description,
        dref.type_text as document_type,

        -- Categorize document type
        CASE
            WHEN LOWER(dref.description) LIKE '%oct%' THEN 'oct_document'
            WHEN LOWER(dref.description) LIKE '%visual%field%' OR LOWER(dref.description) LIKE '%goldman%' THEN 'visual_field_document'
            WHEN LOWER(dref.description) LIKE '%fundus%' THEN 'fundus_document'
            WHEN LOWER(dref.description) LIKE '%ophthal%consult%' THEN 'ophthalmology_consult'
            WHEN LOWER(dref.type_text) LIKE '%ophthal%' THEN 'ophthalmology_other'
            ELSE 'eye_related_document'
        END as document_category,

        'document_reference' as source_table,
        dref.status as document_status,
        dref.date as document_datetime,

        -- Binary file information
        dc.content_attachment_url as file_url,
        dc.content_attachment_content_type as file_type

    FROM fhir_prd_db.document_reference dref
    LEFT JOIN fhir_prd_db.document_reference_content dc ON dref.id = dc.document_reference_id
    WHERE (
        LOWER(dref.description) LIKE '%ophthal%'
        OR LOWER(dref.description) LIKE '%visual%field%'
        OR LOWER(dref.description) LIKE '%oct%'
        OR LOWER(dref.description) LIKE '%fundus%'
        OR LOWER(dref.description) LIKE '%eye%exam%'
        OR LOWER(dref.type_text) LIKE '%ophthal%'
        OR LOWER(dref.description) LIKE '%goldman%'
    )
    AND NOT (LOWER(dref.description) LIKE '%octreotide%')  -- Exclude nuclear medicine scans
),

-- ============================================================
-- CTE 10: UNION ALL Assessment Sources
-- ============================================================
all_assessments AS (
    -- Visual acuity observations
    SELECT
        observation_fhir_id as record_fhir_id,
        patient_fhir_id,
        assessment_date,
        assessment_name as assessment_description,
        assessment_category,
        source_table,
        observation_status as record_status,
        NULL as cpt_code,
        NULL as cpt_description,
        numeric_value,
        value_unit,
        text_value,
        component_name,
        component_numeric_value,
        component_unit,
        NULL as order_intent,
        NULL as file_url,
        NULL as file_type,
        full_datetime
    FROM visual_acuity_obs

    UNION ALL

    -- Fundus/optic disc observations
    SELECT
        observation_fhir_id,
        patient_fhir_id,
        assessment_date,
        assessment_name,
        assessment_category,
        source_table,
        observation_status,
        NULL, NULL,
        numeric_value,
        value_unit,
        text_value,
        component_name,
        component_numeric_value,
        component_unit,
        NULL, NULL, NULL,
        full_datetime
    FROM fundus_optic_disc_obs

    UNION ALL

    -- Visual field procedures
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        assessment_date,
        assessment_name,
        assessment_category,
        source_table,
        procedure_status,
        cpt_code,
        cpt_description,
        numeric_value,
        value_unit,
        text_value,
        component_name,
        component_numeric_value,
        component_unit,
        NULL, NULL, NULL,
        full_datetime
    FROM visual_field_procedures

    UNION ALL

    -- OCT procedures
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        assessment_date,
        assessment_name,
        assessment_category,
        source_table,
        procedure_status,
        cpt_code,
        cpt_description,
        numeric_value,
        value_unit,
        text_value,
        component_name,
        component_numeric_value,
        component_unit,
        NULL, NULL, NULL,
        full_datetime
    FROM oct_procedures

    UNION ALL

    -- Fundus photography procedures
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        assessment_date,
        assessment_name,
        assessment_category,
        source_table,
        procedure_status,
        cpt_code,
        cpt_description,
        numeric_value,
        value_unit,
        text_value,
        component_name,
        component_numeric_value,
        component_unit,
        NULL, NULL, NULL,
        full_datetime
    FROM fundus_photo_procedures

    UNION ALL

    -- Ophthalmology exam procedures
    SELECT
        procedure_fhir_id,
        patient_fhir_id,
        assessment_date,
        assessment_name,
        assessment_category,
        source_table,
        procedure_status,
        cpt_code,
        cpt_description,
        numeric_value,
        value_unit,
        text_value,
        component_name,
        component_numeric_value,
        component_unit,
        NULL, NULL, NULL,
        full_datetime
    FROM ophthal_exam_procedures
),

-- ============================================================
-- CTE 11: Service Requests Separate (Different Schema)
-- ============================================================
all_orders AS (
    SELECT
        service_request_fhir_id as record_fhir_id,
        patient_fhir_id,
        order_date as assessment_date,
        order_name as assessment_description,
        order_category as assessment_category,
        source_table,
        order_status as record_status,
        NULL as cpt_code,
        NULL as cpt_description,
        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,
        order_intent,
        NULL as file_url,
        NULL as file_type,
        order_datetime as full_datetime
    FROM ophthalmology_orders
),

-- ============================================================
-- CTE 12: Reports Separate (Different Schema)
-- ============================================================
all_reports AS (
    SELECT
        diagnostic_report_fhir_id as record_fhir_id,
        patient_fhir_id,
        report_date as assessment_date,
        report_name as assessment_description,
        report_category as assessment_category,
        source_table,
        report_status as record_status,
        NULL as cpt_code,
        NULL as cpt_description,
        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,
        NULL as order_intent,
        NULL as file_url,
        NULL as file_type,
        report_datetime as full_datetime
    FROM ophthalmology_reports
),

-- ============================================================
-- CTE 13: Documents Separate (Different Schema)
-- ============================================================
all_documents AS (
    SELECT
        document_reference_fhir_id as record_fhir_id,
        patient_fhir_id,
        document_date as assessment_date,
        document_description as assessment_description,
        document_category as assessment_category,
        source_table,
        document_status as record_status,
        NULL as cpt_code,
        NULL as cpt_description,
        NULL as numeric_value,
        NULL as value_unit,
        NULL as text_value,
        NULL as component_name,
        NULL as component_numeric_value,
        NULL as component_unit,
        NULL as order_intent,
        file_url,
        file_type,
        document_datetime as full_datetime
    FROM ophthalmology_documents
)

-- ============================================================
-- MAIN QUERY: Combine All Sources
-- ============================================================
SELECT
    record_fhir_id,
    patient_fhir_id,
    assessment_date,
    assessment_description,
    assessment_category,
    source_table,
    record_status,

    -- Procedure-specific fields
    cpt_code,
    cpt_description,

    -- Value fields (for observations)
    numeric_value,
    value_unit,
    text_value,

    -- Multi-component observations
    component_name,
    component_numeric_value,
    component_unit,

    -- Order-specific fields
    order_intent,

    -- Document-specific fields
    file_url,
    file_type,

    -- Full timestamp
    full_datetime

FROM (
    SELECT * FROM all_assessments
    UNION ALL
    SELECT * FROM all_orders
    UNION ALL
    SELECT * FROM all_reports
    UNION ALL
    SELECT * FROM all_documents
);


-- ================================================================================
-- VALIDATION QUERIES FOR v_ophthalmology_assessments
-- ================================================================================

-- 1. Summary by assessment category
SELECT
    assessment_category,
    source_table,
    COUNT(*) as record_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    MIN(assessment_date) as earliest_date,
    MAX(assessment_date) as latest_date
FROM fhir_prd_db.v_ophthalmology_assessments
GROUP BY assessment_category, source_table
ORDER BY record_count DESC;

-- 2. Patient-level summary
SELECT
    patient_fhir_id,
    COUNT(DISTINCT assessment_category) as distinct_assessment_types,
    COUNT(*) as total_assessments,
    MIN(assessment_date) as first_assessment,
    MAX(assessment_date) as last_assessment,
    LISTAGG(DISTINCT assessment_category, '; ') WITHIN GROUP (ORDER BY assessment_category) as assessment_types
FROM fhir_prd_db.v_ophthalmology_assessments
GROUP BY patient_fhir_id
HAVING COUNT(*) >= 5  -- Patients with at least 5 ophthalmology assessments
ORDER BY total_assessments DESC
LIMIT 20;

-- 3. OCT coverage by year
SELECT
    YEAR(assessment_date) as assessment_year,
    COUNT(*) as oct_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_ophthalmology_assessments
WHERE assessment_category IN ('oct_optic_nerve', 'oct_retina', 'oct_macula', 'oct_unspecified')
    AND assessment_date IS NOT NULL
GROUP BY YEAR(assessment_date)
ORDER BY assessment_year;

-- 4. Visual field testing frequency
SELECT
    patient_fhir_id,
    COUNT(*) as visual_field_count,
    MIN(assessment_date) as first_vf,
    MAX(assessment_date) as last_vf,
    DATE_DIFF('day', MIN(assessment_date), MAX(assessment_date)) as days_monitored
FROM fhir_prd_db.v_ophthalmology_assessments
WHERE assessment_category = 'visual_field'
GROUP BY patient_fhir_id
HAVING COUNT(*) >= 3  -- At least 3 visual field exams
ORDER BY visual_field_count DESC;

-- 5. Document references with binary files
SELECT
    assessment_category,
    file_type,
    COUNT(*) as file_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_ophthalmology_assessments
WHERE file_url IS NOT NULL
GROUP BY assessment_category, file_type
ORDER BY file_count DESC;


-- ================================================================================
-- SECTION 8: AUDIOLOGY ASSESSMENTS VIEW
-- ================================================================================
-- Purpose: Comprehensive audiology/hearing assessments for brain tumor patients
--          Captures audiograms, hearing loss diagnoses, ototoxicity monitoring
-- Clinical context: Platinum chemotherapy (cisplatin/carboplatin) causes ototoxicity
--                   Requires serial audiometry for early detection and intervention
-- Data sources: observation, observation_component, condition, procedure,
--               service_request, diagnostic_report, document_reference tables
--
-- Created: 2025-10-18
-- Based on: Exploratory analysis showing:
--   - 20,622 observations (1,141 patients) - audiograms, hearing aid status, laterality
--   - 1,718 procedures (379 patients) - audiometric screening, pure tone audiometry
--   - 6,993 conditions (521 patients) - hearing loss diagnoses with type/laterality
--   - 825 ototoxicity monitoring conditions (259 patients actively surveilled)
--   - 99 ototoxic hearing loss diagnoses (22 patients with confirmed platinum toxicity)
--   - 1,228 document references (424 patients) - audiogram files (XML, TIFF)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_audiology_assessments AS

-- ============================================================
-- CTE 1: Audiogram Frequency Thresholds
-- ============================================================
WITH audiogram_thresholds AS (
    SELECT
        o.id as observation_fhir_id,
        SUBSTRING(o.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) as assessment_date,

        -- Extract frequency and ear from code_text
        CASE
            WHEN LOWER(o.code_text) LIKE '%left ear%' THEN 'left'
            WHEN LOWER(o.code_text) LIKE '%right ear%' THEN 'right'
        END as ear_side,

        CASE
            WHEN LOWER(o.code_text) LIKE '%1000%hz%' THEN 1000
            WHEN LOWER(o.code_text) LIKE '%2000%hz%' THEN 2000
            WHEN LOWER(o.code_text) LIKE '%4000%hz%' THEN 4000
            WHEN LOWER(o.code_text) LIKE '%6000%hz%' THEN 6000
            WHEN LOWER(o.code_text) LIKE '%8000%hz%' THEN 8000
            WHEN LOWER(o.code_text) LIKE '%500%hz%' THEN 500
            WHEN LOWER(o.code_text) LIKE '%250%hz%' THEN 250
        END as frequency_hz,

        o.value_quantity_value as threshold_db,
        o.value_quantity_unit as threshold_unit,
        o.code_text as test_name,
        'audiogram_threshold' as assessment_category,
        'observation' as source_table,
        o.status as observation_status,
        o.effective_date_time as full_datetime

    FROM fhir_prd_db.observation o
    WHERE (
        LOWER(o.code_text) LIKE '%ear%hz%'
        AND (
            LOWER(o.code_text) LIKE '%1000%'
            OR LOWER(o.code_text) LIKE '%2000%'
            OR LOWER(o.code_text) LIKE '%4000%'
            OR LOWER(o.code_text) LIKE '%6000%'
            OR LOWER(o.code_text) LIKE '%8000%'
            OR LOWER(o.code_text) LIKE '%500%'
            OR LOWER(o.code_text) LIKE '%250%'
        )
    )
),

-- ============================================================
-- CTE 2: Hearing Aid Status & Laterality
-- ============================================================
hearing_aid_status AS (
    SELECT
        o.id as observation_fhir_id,
        SUBSTRING(o.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) as assessment_date,
        o.code_text as assessment_name,

        -- Determine assessment category
        CASE
            WHEN LOWER(o.code_text) LIKE '%hearing aid ear%' THEN 'hearing_aid_laterality'
            WHEN LOWER(o.code_text) LIKE '%hearing aid%' THEN 'hearing_aid_required'
        END as assessment_category,

        'observation' as source_table,

        -- Extract laterality from component value
        oc.component_value_string as laterality_value,

        -- Standardize laterality
        CASE
            WHEN LOWER(oc.component_value_string) LIKE '%both%ear%' THEN 'Bilateral'
            WHEN LOWER(oc.component_value_string) LIKE '%right%ear%' THEN 'Right'
            WHEN LOWER(oc.component_value_string) LIKE '%left%ear%' THEN 'Left'
            WHEN LOWER(o.code_text) LIKE '%hearing aid%' AND oc.component_code_text IS NOT NULL THEN 'Yes'
        END as standardized_value,

        o.status as observation_status,
        o.effective_date_time as full_datetime

    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE LOWER(o.code_text) LIKE '%hearing aid%'
),

-- ============================================================
-- CTE 3: Hearing Loss Type & Laterality (from Observations)
-- ============================================================
hearing_loss_observations AS (
    SELECT
        o.id as observation_fhir_id,
        SUBSTRING(o.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) as assessment_date,
        o.code_text as assessment_name,

        -- Categorize
        CASE
            WHEN LOWER(o.code_text) LIKE '%laterality%' THEN 'hearing_loss_laterality'
            WHEN LOWER(o.code_text) LIKE '%hearing loss type%' THEN 'hearing_loss_type'
            WHEN LOWER(o.code_text) LIKE '%sensorineural%' THEN 'hearing_loss_type'
            WHEN LOWER(o.code_text) LIKE '%conductive%' THEN 'hearing_loss_type'
            WHEN LOWER(o.code_text) LIKE '%hearing loss%' THEN 'hearing_loss_symptom'
        END as assessment_category,

        'observation' as source_table,

        -- Extract type from code_text
        CASE
            WHEN LOWER(o.code_text) LIKE '%sensorineural%' THEN 'Sensorineural'
            WHEN LOWER(o.code_text) LIKE '%conductive%' THEN 'Conductive'
            WHEN LOWER(o.code_text) LIKE '%mixed%' THEN 'Mixed'
        END as hearing_loss_type,

        -- Extract laterality from component
        CASE
            WHEN LOWER(oc.component_value_string) LIKE '%both%ear%' THEN 'Bilateral'
            WHEN LOWER(oc.component_value_string) LIKE '%right%ear%' THEN 'Right'
            WHEN LOWER(oc.component_value_string) LIKE '%left%ear%' THEN 'Left'
        END as laterality,

        oc.component_value_string as raw_value,
        o.status as observation_status,
        o.effective_date_time as full_datetime

    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE (
        LOWER(o.code_text) LIKE '%hearing loss%'
        OR LOWER(o.code_text) LIKE '%sensorineural%'
        OR LOWER(o.code_text) LIKE '%conductive%'
        OR LOWER(o.code_text) LIKE '%hard of hearing%'
    )
    AND NOT (LOWER(o.code_text) LIKE '%ear%hz%')  -- Exclude audiogram thresholds
),

-- ============================================================
-- CTE 4: Hearing Reception Threshold & Other Tests
-- ============================================================
hearing_tests_other AS (
    SELECT
        o.id as observation_fhir_id,
        SUBSTRING(o.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(o.effective_date_time, 1, 10) AS DATE)) as assessment_date,
        o.code_text as assessment_name,

        CASE
            WHEN LOWER(o.code_text) LIKE '%hearing reception threshold%' THEN 'hearing_reception_threshold'
            WHEN LOWER(o.code_text) LIKE '%hearing screen%result%' THEN 'hearing_screen_result'
            WHEN LOWER(o.code_text) LIKE '%hearing%intact%' THEN 'hearing_exam_normal'
            WHEN LOWER(o.code_text) LIKE '%vision and hearing%' THEN 'hearing_status_general'
        END as assessment_category,

        'observation' as source_table,
        o.value_quantity_value as numeric_value,
        o.value_quantity_unit as value_unit,
        oc.component_value_string as text_value,
        o.status as observation_status,
        o.effective_date_time as full_datetime

    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE (
        LOWER(o.code_text) LIKE '%hearing reception threshold%'
        OR LOWER(o.code_text) LIKE '%hearing screen%'
        OR LOWER(o.code_text) LIKE '%hearing%intact%'
        OR (LOWER(o.code_text) LIKE '%vision and hearing%' AND LOWER(o.code_text) LIKE '%hearing%')
    )
    AND NOT (LOWER(o.code_text) LIKE '%ear%hz%')
),

-- ============================================================
-- CTE 5: Hearing Loss Diagnoses (Conditions)
-- ============================================================
hearing_loss_diagnoses AS (
    SELECT
        c.id as condition_fhir_id,
        SUBSTRING(c.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(c.onset_date_time, 1, 10) AS DATE)) as diagnosis_date,
        c.code_text as diagnosis_name,

        -- Categorize diagnosis type
        CASE
            WHEN LOWER(c.code_text) LIKE '%ototoxic%' THEN 'ototoxic_hearing_loss'
            WHEN LOWER(c.code_text) LIKE '%ototoxicity monitoring%' THEN 'ototoxicity_monitoring'
            WHEN LOWER(c.code_text) LIKE '%sensorineural%' THEN 'sensorineural_hearing_loss'
            WHEN LOWER(c.code_text) LIKE '%conductive%' THEN 'conductive_hearing_loss'
            WHEN LOWER(c.code_text) LIKE '%mixed%' THEN 'mixed_hearing_loss'
            WHEN LOWER(c.code_text) LIKE '%deaf%' THEN 'deafness'
            ELSE 'hearing_loss_unspecified'
        END as diagnosis_category,

        'condition' as source_table,

        -- Extract hearing loss type
        CASE
            WHEN LOWER(c.code_text) LIKE '%sensorineural%' THEN 'Sensorineural'
            WHEN LOWER(c.code_text) LIKE '%conductive%' THEN 'Conductive'
            WHEN LOWER(c.code_text) LIKE '%mixed%' THEN 'Mixed'
            WHEN LOWER(c.code_text) LIKE '%ototoxic%' THEN 'Ototoxic (Sensorineural)'
        END as hearing_loss_type,

        -- Extract laterality from diagnosis text
        CASE
            WHEN LOWER(c.code_text) LIKE '%bilateral%' OR LOWER(c.code_text) LIKE '%both ears%' THEN 'Bilateral'
            WHEN LOWER(c.code_text) LIKE '%unilateral%' AND LOWER(c.code_text) LIKE '%left%' THEN 'Left'
            WHEN LOWER(c.code_text) LIKE '%unilateral%' AND LOWER(c.code_text) LIKE '%right%' THEN 'Right'
            WHEN LOWER(c.code_text) LIKE '%left ear%' THEN 'Left'
            WHEN LOWER(c.code_text) LIKE '%right ear%' THEN 'Right'
            WHEN LOWER(c.code_text) LIKE '%asymmetrical%' THEN 'Bilateral (asymmetric)'
        END as laterality,

        -- Flag ototoxicity
        CASE
            WHEN LOWER(c.code_text) LIKE '%ototoxic%' THEN TRUE
            ELSE FALSE
        END as is_ototoxic,

        ccs.clinical_status_coding_code as condition_status,
        c.onset_date_time as full_datetime

    FROM fhir_prd_db.condition c
    LEFT JOIN fhir_prd_db.condition_clinical_status_coding ccs ON c.id = ccs.condition_id
    WHERE (
        LOWER(c.code_text) LIKE '%hearing loss%'
        OR LOWER(c.code_text) LIKE '%deaf%'
        OR LOWER(c.code_text) LIKE '%ototoxic%'
        OR LOWER(c.code_text) LIKE '%ototoxicity%'
    )
),

-- ============================================================
-- CTE 6: Audiology Procedures
-- ============================================================
audiology_procedures AS (
    SELECT
        p.id as procedure_fhir_id,
        SUBSTRING(p.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)) as assessment_date,
        p.code_text as procedure_name,

        -- Categorize procedure type
        CASE
            WHEN LOWER(p.code_text) LIKE '%audiometric screening%' THEN 'audiometric_screening'
            WHEN LOWER(p.code_text) LIKE '%pure tone audiometry%' THEN 'pure_tone_audiometry'
            WHEN LOWER(p.code_text) LIKE '%speech%audiometry%' OR LOWER(p.code_text) LIKE '%speech threshold%' THEN 'speech_audiometry'
            WHEN LOWER(p.code_text) LIKE '%air%bone%' THEN 'air_bone_audiometry'
            WHEN LOWER(p.code_text) LIKE '%comprehensive hearing%' THEN 'comprehensive_hearing_test'
            WHEN LOWER(p.code_text) LIKE '%hearing aid check%' THEN 'hearing_aid_check'
            WHEN LOWER(p.code_text) LIKE '%abr%' OR LOWER(p.code_text) LIKE '%auditory brainstem%' THEN 'abr_test'
            WHEN LOWER(p.code_text) LIKE '%tympanometry%' THEN 'tympanometry'
            ELSE 'other_audiology_procedure'
        END as procedure_category,

        'procedure' as source_table,
        p.status as procedure_status,
        pc.code_coding_code as cpt_code,
        pc.code_coding_display as cpt_description,
        p.performed_date_time as full_datetime

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pc ON p.id = pc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%audiolog%'
        OR LOWER(p.code_text) LIKE '%audiometr%'
        OR LOWER(p.code_text) LIKE '%hearing%'
        OR LOWER(p.code_text) LIKE '%abr%'
    )
),

-- ============================================================
-- CTE 7: Audiology Service Requests (Orders)
-- ============================================================
audiology_orders AS (
    SELECT
        sr.id as service_request_fhir_id,
        SUBSTRING(sr.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(sr.authored_on, 1, 10) AS DATE)) as order_date,
        sr.code_text as order_name,

        CASE
            WHEN LOWER(sr.code_text) LIKE '%audiolog%' THEN 'audiology_order'
            WHEN LOWER(sr.code_text) LIKE '%audiometr%' THEN 'audiometry_order'
            WHEN LOWER(sr.code_text) LIKE '%hearing%' THEN 'hearing_test_order'
        END as order_category,

        'service_request' as source_table,
        sr.status as order_status,
        sr.intent as order_intent,
        sr.authored_on as order_datetime

    FROM fhir_prd_db.service_request sr
    WHERE (
        LOWER(sr.code_text) LIKE '%audiolog%'
        OR LOWER(sr.code_text) LIKE '%audiometr%'
        OR LOWER(sr.code_text) LIKE '%hearing%'
    )
),

-- ============================================================
-- CTE 8: Diagnostic Reports
-- ============================================================
audiology_reports AS (
    SELECT
        dr.id as diagnostic_report_fhir_id,
        SUBSTRING(dr.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(dr.effective_date_time, 1, 10) AS DATE)) as report_date,
        dr.code_text as report_name,

        CASE
            WHEN LOWER(dr.code_text) LIKE '%audiolog%' THEN 'audiology_report'
            WHEN LOWER(dr.code_text) LIKE '%audiometr%' THEN 'audiometry_report'
            WHEN LOWER(dr.code_text) LIKE '%hearing%' THEN 'hearing_test_report'
        END as report_category,

        'diagnostic_report' as source_table,
        dr.status as report_status,
        dr.effective_date_time as report_datetime

    FROM fhir_prd_db.diagnostic_report dr
    WHERE (
        LOWER(dr.code_text) LIKE '%audiolog%'
        OR LOWER(dr.code_text) LIKE '%audiometr%'
        OR LOWER(dr.code_text) LIKE '%hearing%'
    )
),

-- ============================================================
-- CTE 9: Document References (Audiogram Files)
-- ============================================================
audiology_documents AS (
    SELECT
        dref.id as document_reference_fhir_id,
        SUBSTRING(dref.subject_reference, 9) as patient_fhir_id,
        TRY(CAST(SUBSTR(dref.date, 1, 10) AS DATE)) as document_date,
        dref.description as document_description,
        dref.type_text as document_type,

        -- Categorize document
        CASE
            WHEN LOWER(dref.type_text) LIKE '%audiologic assessment%' THEN 'audiologic_assessment_document'
            WHEN LOWER(dref.description) LIKE '%audiolog%evaluation%' THEN 'audiology_evaluation_document'
            WHEN LOWER(dref.description) LIKE '%audiometr%' THEN 'audiometry_document'
            WHEN LOWER(dref.description) LIKE '%hearing%' THEN 'hearing_test_document'
            ELSE 'audiology_other_document'
        END as document_category,

        'document_reference' as source_table,
        dref.status as document_status,
        dref.date as document_datetime,

        -- Binary file information
        dc.content_attachment_url as file_url,
        dc.content_attachment_content_type as file_type

    FROM fhir_prd_db.document_reference dref
    LEFT JOIN fhir_prd_db.document_reference_content dc ON dref.id = dc.document_reference_id
    WHERE (
        LOWER(dref.description) LIKE '%audiolog%'
        OR LOWER(dref.type_text) LIKE '%audiolog%'
        OR LOWER(dref.description) LIKE '%hearing%'
        OR LOWER(dref.type_text) LIKE '%hearing%'
    )
)

-- ============================================================
-- MAIN QUERY: Combine All Sources
-- ============================================================
SELECT
    'audiogram' as data_type,
    observation_fhir_id as record_fhir_id,
    patient_fhir_id,
    assessment_date,
    test_name as assessment_description,
    assessment_category,
    source_table,
    observation_status as record_status,

    -- Audiogram-specific fields
    ear_side,
    frequency_hz,
    threshold_db,
    threshold_unit,
    NULL as hearing_loss_type,
    NULL as laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    full_datetime
FROM audiogram_thresholds

UNION ALL

SELECT
    'hearing_aid' as data_type,
    observation_fhir_id as record_fhir_id,
    patient_fhir_id,
    assessment_date,
    assessment_name as assessment_description,
    assessment_category,
    source_table,
    observation_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    NULL as hearing_loss_type,
    standardized_value as laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    full_datetime
FROM hearing_aid_status

UNION ALL

SELECT
    'hearing_loss_observation' as data_type,
    observation_fhir_id as record_fhir_id,
    patient_fhir_id,
    assessment_date,
    assessment_name as assessment_description,
    assessment_category,
    source_table,
    observation_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    hearing_loss_type,
    laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    full_datetime
FROM hearing_loss_observations

UNION ALL

SELECT
    'hearing_test' as data_type,
    observation_fhir_id as record_fhir_id,
    patient_fhir_id,
    assessment_date,
    assessment_name as assessment_description,
    assessment_category,
    source_table,
    observation_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    CAST(numeric_value AS VARCHAR) as threshold_db,
    value_unit as threshold_unit,
    NULL as hearing_loss_type,
    NULL as laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    full_datetime
FROM hearing_tests_other

UNION ALL

SELECT
    'diagnosis' as data_type,
    condition_fhir_id as record_fhir_id,
    patient_fhir_id,
    diagnosis_date as assessment_date,
    diagnosis_name as assessment_description,
    diagnosis_category as assessment_category,
    source_table,
    condition_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    hearing_loss_type,
    laterality,
    is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    full_datetime
FROM hearing_loss_diagnoses

UNION ALL

SELECT
    'procedure' as data_type,
    procedure_fhir_id as record_fhir_id,
    patient_fhir_id,
    assessment_date,
    procedure_name as assessment_description,
    procedure_category as assessment_category,
    source_table,
    procedure_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    NULL as hearing_loss_type,
    NULL as laterality,
    NULL as is_ototoxic,
    cpt_code,
    cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    full_datetime
FROM audiology_procedures

UNION ALL

SELECT
    'order' as data_type,
    service_request_fhir_id as record_fhir_id,
    patient_fhir_id,
    order_date as assessment_date,
    order_name as assessment_description,
    order_category as assessment_category,
    source_table,
    order_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    NULL as hearing_loss_type,
    NULL as laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    order_intent,
    NULL as file_url,
    NULL as file_type,

    order_datetime as full_datetime
FROM audiology_orders

UNION ALL

SELECT
    'report' as data_type,
    diagnostic_report_fhir_id as record_fhir_id,
    patient_fhir_id,
    report_date as assessment_date,
    report_name as assessment_description,
    report_category as assessment_category,
    source_table,
    report_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    NULL as hearing_loss_type,
    NULL as laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    NULL as file_url,
    NULL as file_type,

    report_datetime as full_datetime
FROM audiology_reports

UNION ALL

SELECT
    'document' as data_type,
    document_reference_fhir_id as record_fhir_id,
    patient_fhir_id,
    document_date as assessment_date,
    document_description as assessment_description,
    document_category as assessment_category,
    source_table,
    document_status as record_status,

    NULL as ear_side,
    NULL as frequency_hz,
    NULL as threshold_db,
    NULL as threshold_unit,
    NULL as hearing_loss_type,
    NULL as laterality,
    NULL as is_ototoxic,
    NULL as cpt_code,
    NULL as cpt_description,
    NULL as order_intent,
    file_url,
    file_type,

    document_datetime as full_datetime
FROM audiology_documents;


-- ================================================================================
-- VALIDATION QUERIES FOR v_audiology_assessments
-- ================================================================================

-- 1. Summary by data type and assessment category
SELECT
    data_type,
    assessment_category,
    COUNT(*) as record_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    MIN(assessment_date) as earliest_date,
    MAX(assessment_date) as latest_date
FROM fhir_prd_db.v_audiology_assessments
GROUP BY data_type, assessment_category
ORDER BY record_count DESC;

-- 2. Ototoxicity monitoring summary
SELECT
    COUNT(DISTINCT patient_fhir_id) as patients_with_ototoxicity_monitoring,
    COUNT(DISTINCT CASE WHEN is_ototoxic = TRUE THEN patient_fhir_id END) as patients_with_ototoxic_hearing_loss,
    COUNT(*) as total_ototoxicity_records
FROM fhir_prd_db.v_audiology_assessments
WHERE assessment_category IN ('ototoxicity_monitoring', 'ototoxic_hearing_loss');

-- 3. Hearing aid requirements
SELECT
    laterality,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_audiology_assessments
WHERE assessment_category IN ('hearing_aid_required', 'hearing_aid_laterality')
  AND laterality IS NOT NULL
GROUP BY laterality
ORDER BY patient_count DESC;

-- 4. Audiogram coverage by frequency
SELECT
    frequency_hz,
    ear_side,
    COUNT(*) as measurement_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    AVG(CAST(threshold_db AS DOUBLE)) as avg_threshold_db
FROM fhir_prd_db.v_audiology_assessments
WHERE data_type = 'audiogram'
  AND frequency_hz IS NOT NULL
GROUP BY frequency_hz, ear_side
ORDER BY frequency_hz, ear_side;

-- 5. Hearing loss type and laterality distribution
SELECT
    hearing_loss_type,
    laterality,
    COUNT(*) as diagnosis_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_audiology_assessments
WHERE data_type = 'diagnosis'
  AND hearing_loss_type IS NOT NULL
GROUP BY hearing_loss_type, laterality
ORDER BY diagnosis_count DESC;

-- 6. Patient-level longitudinal summary
SELECT
    patient_fhir_id,
    COUNT(DISTINCT CASE WHEN data_type = 'audiogram' THEN assessment_date END) as audiogram_sessions,
    COUNT(DISTINCT CASE WHEN data_type = 'diagnosis' THEN record_fhir_id END) as diagnoses,
    COUNT(DISTINCT CASE WHEN data_type = 'procedure' THEN assessment_date END) as procedures,
    MIN(assessment_date) as first_assessment,
    MAX(assessment_date) as last_assessment,
    DATE_DIFF('day', MIN(assessment_date), MAX(assessment_date)) as monitoring_duration_days,
    MAX(CASE WHEN is_ototoxic = TRUE THEN 1 ELSE 0 END) as has_ototoxic_diagnosis
FROM fhir_prd_db.v_audiology_assessments
GROUP BY patient_fhir_id
HAVING audiogram_sessions >= 3  -- Patients with serial monitoring
ORDER BY audiogram_sessions DESC
LIMIT 20;

-- 7. Document files available
SELECT
    file_type,
    COUNT(*) as file_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_audiology_assessments
WHERE file_url IS NOT NULL
GROUP BY file_type
ORDER BY file_count DESC;


-- ================================================================================
-- END OF ATHENA VIEW CREATION QUERIES
-- ================================================================================
