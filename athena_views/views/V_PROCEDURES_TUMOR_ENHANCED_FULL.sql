-- ============================================================================
-- VIEW: v_procedures_tumor (ENHANCED VERSION)
-- ============================================================================
-- Purpose: Add annotation columns to help filter and categorize procedures
-- New Columns Added (10 total):
--   1. epic_or_log_id - Direct Epic OR Log case ID from procedure_identifier
--   2. in_surgical_procedures_table - Boolean flag if procedure exists in surgical_procedures
--   3. surgical_procedures_mrn - MRN from surgical_procedures (if linked)
--   4. surgical_procedures_epic_case_id - Epic case ID from surgical_procedures (if linked)
--   5. proc_category_annotation - Categorization: PROCEDURE_ORDER, SURGICAL_HISTORY, SURGICAL_PROCEDURE, etc.
--   6. procedure_source_type - HIGH LEVEL: OR_CASE, SURGICAL_HISTORY, PROCEDURE_ORDER, COMPLETED_SURGICAL, etc.
--   7. is_likely_performed - Boolean (excludes orders, history, not-done)
--   8. proc_status_annotation - Readable status: COMPLETED, NOT_DONE, ERROR, etc.
--   9. has_minimum_data_quality - Boolean (has date, completed status, CPT code)
--  10. category_coding_code - SNOMED category code (from procedure_category_coding)
-- ============================================================================
-- Enhancement Date: 2025-10-29
-- Modification: Insert after line 394 of original, add columns after line 454
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_procedures_tumor AS
WITH
-- [Lines 3-394: All existing CTEs remain unchanged from DATETIME_STANDARDIZED_VIEWS.sql]
-- Includes: cpt_classifications, epic_codes, procedure_codes, procedure_dates, procedure_validation, combined_classification

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

            ELSE NULL
        END as cpt_classification,

        CASE
            WHEN pcc.code_coding_code IN (
                '61500', '61510', '61512', '61516', '61518', '61519', '61520', '61521', '61524',
                '61545', '61546', '61548', '61750', '61751', '61781', '61782', '61783',
                '62164', '62165', '61140', '61580', '61584', '61592', '61600', '61601', '61607',
                '62201', '62200', '61210', '61215', '61304', '61305', '64999'
            ) THEN 'surgical'
            ELSE 'nonsurgical'
        END as classification_type

    FROM fhir_prd_db.procedure_code_coding pcc
    WHERE pcc.code_coding_system = 'http://www.ama-assn.org/go/cpt'
),

epic_codes AS (
    SELECT
        procedure_id,
        code_coding_code as epic_code,
        code_coding_display as epic_display,

        CASE
            WHEN code_coding_code IN ('10001', '10002', '10003') THEN 'CNS Tumor - Brain'
            WHEN code_coding_code IN ('10004', '10005') THEN 'CNS Tumor - Spine'
            WHEN code_coding_code IN ('19001', '19002', '19003') THEN 'VP Shunt'
            WHEN code_coding_code IN ('15001', '15002') THEN 'Bone Marrow Transplant'
            ELSE NULL
        END as epic_category

    FROM fhir_prd_db.procedure_code_coding
    WHERE code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.7.7.2.798276'
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
            TRY(CAST(p.performed_date_time AS DATE)),
            TRY(CAST(p.performed_period_start AS DATE)),
            TRY(CAST(p.performed_string AS DATE))
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
            WHEN cpt.cpt_classification LIKE 'craniotomy_tumor_resection'
                OR cpt.cpt_classification LIKE 'stereotactic_tumor_procedure'
                OR cpt.cpt_classification LIKE 'neuroendoscopy_tumor'
                OR cpt.cpt_classification LIKE 'open_brain_biopsy'
                OR cpt.cpt_classification LIKE 'skull_base_tumor'
                OR (pc.is_surgical_keyword AND pv.has_tumor_reason)
                OR (pc.is_surgical_keyword AND pv.has_tumor_body_site)
            THEN
                CASE
                    WHEN cpt.cpt_classification NOT LIKE 'exclude%' THEN true
                    WHEN cpt.cpt_classification IS NULL THEN true
                    ELSE false
                END
            ELSE false
        END as is_tumor_surgery,

        CASE
            WHEN cpt.cpt_classification LIKE 'exclude%' THEN true
            ELSE false
        END as is_excluded_procedure,

        CASE
            WHEN cpt.cpt_classification LIKE 'craniotomy_tumor_resection' THEN 'craniotomy'
            WHEN cpt.cpt_classification LIKE 'stereotactic_tumor_procedure' THEN 'stereotactic_procedure'
            WHEN cpt.cpt_classification LIKE 'neuroendoscopy_tumor' THEN 'neuroendoscopy'
            WHEN cpt.cpt_classification LIKE 'open_brain_biopsy' THEN 'open_biopsy'
            WHEN cpt.cpt_classification LIKE 'skull_base_tumor' THEN 'skull_base'
            WHEN pc.is_surgical_keyword THEN 'unknown'
            ELSE 'unknown'
        END as surgery_type,

        CASE
            WHEN cpt.cpt_classification IS NOT NULL THEN 3
            WHEN epic.epic_category IS NOT NULL THEN 2
            WHEN pc.is_surgical_keyword THEN 1
            ELSE 0
        END as classification_confidence

    FROM fhir_prd_db.procedure p
    LEFT JOIN cpt_classifications cpt ON p.id = cpt.procedure_id
    LEFT JOIN epic_codes epic ON p.id = epic.procedure_id
    LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
    LEFT JOIN procedure_validation pv ON p.id = pv.procedure_id
),

-- ========================================================================
-- NEW CTEs: Epic OR Log and Surgical Procedures Linkage
-- ========================================================================

epic_or_identifiers AS (
    SELECT
        procedure_id,
        identifier_value as epic_or_log_id
    FROM fhir_prd_db.procedure_identifier
    WHERE identifier_type_text = 'ORL'
),

surgical_procedures_link AS (
    SELECT
        procedure_id,
        epic_case_orlog_id,
        mrn,
        TRUE as in_surgical_procedures_table
    FROM fhir_prd_db.surgical_procedures
)

-- ========================================================================
-- FINAL SELECT WITH ENHANCED ANNOTATION COLUMNS
-- ========================================================================

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
    pc.keyword_classification,
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
    pp.performer_function_text as pp_performer_function_text,

    -- ========================================================================
    -- NEW ANNOTATION COLUMNS (10 total)
    -- ========================================================================

    -- 1. Epic OR Log ID from procedure_identifier table
    epi.epic_or_log_id,

    -- 2. Flag if procedure exists in surgical_procedures table
    COALESCE(spl.in_surgical_procedures_table, FALSE) as in_surgical_procedures_table,

    -- 3-4. MRN and Epic case ID from surgical_procedures (if linked)
    spl.mrn as surgical_procedures_mrn,
    spl.epic_case_orlog_id as surgical_procedures_epic_case_id,

    -- 5. Categorize proc_category_text for easier filtering
    CASE
        WHEN p.category_text = 'Ordered Procedures' THEN 'PROCEDURE_ORDER'
        WHEN p.category_text = 'Surgical History' THEN 'SURGICAL_HISTORY'
        WHEN p.category_text = 'Surgical Procedures' THEN 'SURGICAL_PROCEDURE'
        WHEN p.category_text IS NULL THEN 'UNCATEGORIZED'
        ELSE 'OTHER_CATEGORY'
    END as proc_category_annotation,

    -- 6. High-level source type classification
    CASE
        WHEN epi.epic_or_log_id IS NOT NULL THEN 'OR_CASE'
        WHEN spl.in_surgical_procedures_table THEN 'OR_CASE'
        WHEN p.category_text = 'Surgical History' THEN 'SURGICAL_HISTORY'
        WHEN p.category_text = 'Ordered Procedures' THEN 'PROCEDURE_ORDER'
        WHEN p.category_text = 'Surgical Procedures' AND p.status = 'completed' THEN 'COMPLETED_SURGICAL'
        WHEN p.status = 'not-done' THEN 'NOT_DONE'
        ELSE 'OTHER'
    END as procedure_source_type,

    -- 7. Flag for likely performed procedures (excludes orders, history, not-done)
    CASE
        WHEN p.category_text IN ('Ordered Procedures') THEN FALSE
        WHEN p.status = 'not-done' THEN FALSE
        WHEN p.status = 'entered-in-error' THEN FALSE
        WHEN p.status = 'completed' THEN TRUE
        WHEN epi.epic_or_log_id IS NOT NULL THEN TRUE
        WHEN spl.in_surgical_procedures_table THEN TRUE
        ELSE FALSE
    END as is_likely_performed,

    -- 8. Annotation for status
    CASE
        WHEN p.status = 'completed' THEN 'COMPLETED'
        WHEN p.status = 'not-done' THEN 'NOT_DONE'
        WHEN p.status = 'entered-in-error' THEN 'ERROR'
        WHEN p.status = 'in-progress' THEN 'IN_PROGRESS'
        WHEN p.status = 'on-hold' THEN 'ON_HOLD'
        WHEN p.status = 'stopped' THEN 'STOPPED'
        WHEN p.status = 'unknown' THEN 'UNKNOWN'
        ELSE 'OTHER_STATUS'
    END as proc_status_annotation,

    -- 9. Data quality flag: Has minimum required data for analysis
    CASE
        WHEN pd.procedure_date IS NOT NULL
            AND p.status = 'completed'
            AND pc.code_coding_code IS NOT NULL
        THEN TRUE
        ELSE FALSE
    END as has_minimum_data_quality,

    -- 10. SNOMED category code (useful for filtering)
    pcat.category_coding_code as category_coding_code

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN fhir_prd_db.patient pa ON p.subject_reference = CONCAT('Patient/', pa.id)
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN combined_classification cc ON p.id = cc.procedure_id
LEFT JOIN fhir_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
LEFT JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id

-- NEW JOINS
LEFT JOIN epic_or_identifiers epi ON p.id = epi.procedure_id
LEFT JOIN surgical_procedures_link spl ON p.id = spl.procedure_id

ORDER BY p.subject_reference, pd.procedure_date;
