-- ================================================================================
-- RECOMMENDED ATHENA VIEW UPDATES
-- ================================================================================
-- Date: October 18, 2025
-- Purpose: Enhanced procedure classification for accurate diagnostic event identification
-- Based on: DIAGNOSTIC_EVENT_CODING_ASSESSMENT.md
--
-- PRIORITY ORDER:
-- 1. v_procedures (CRITICAL - diagnostic event foundation)
-- 2. v_tumor_surgeries_with_pathology (NEW - links procedures to pathology)
-- 3. v_surgical_events_classified (NEW - temporal classification)
-- ================================================================================

-- ================================================================================
-- 1. ENHANCED v_procedures VIEW
-- ================================================================================
-- CHANGES FROM ORIGINAL:
-- - Added CPT code classification for neurosurgical procedures
-- - Added SNOMED code classification (secondary validation)
-- - Added non-tumor procedure exclusions
-- - Added procedure_classification field (replaces is_surgical_keyword)
-- - Maintains backward compatibility (is_surgical_keyword preserved)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_procedures AS
WITH
-- CPT Code Classification (PRIMARY - most specific)
cpt_classifications AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as cpt_code,
        CASE
            -- TUMOR-SPECIFIC NEUROSURGICAL PROCEDURES

            -- Craniotomy for tumor (CPT 61510-61519)
            WHEN pcc.code_coding_code IN ('61510', '61512', '61514', '61516', '61518', '61519')
                THEN 'craniotomy_tumor'

            -- Stereotactic biopsy (CPT 61750-61751)
            WHEN pcc.code_coding_code IN ('61750', '61751')
                THEN 'stereotactic_biopsy'

            -- Open brain biopsy (CPT 61140)
            WHEN pcc.code_coding_code = '61140'
                THEN 'open_biopsy'

            -- Craniectomy for tumor (CPT 61500-61501)
            WHEN pcc.code_coding_code IN ('61500', '61501')
                THEN 'craniectomy_tumor'

            -- Transsphenoidal surgery (CPT 61545-61548)
            WHEN pcc.code_coding_code IN ('61545', '61546', '61548')
                THEN 'transsphenoidal_resection'

            -- Skull base tumor resection (CPT 61520-61521)
            WHEN pcc.code_coding_code IN ('61520', '61521')
                THEN 'skull_base_tumor'

            -- Stereotactic radiosurgery planning (CPT 61793-61800)
            WHEN pcc.code_coding_code IN ('61793', '61796', '61797', '61798', '61799', '61800')
                THEN 'stereotactic_radiosurgery'

            -- NON-TUMOR PROCEDURES (EXCLUDE)

            -- VP shunt procedures (CPT 62220-62258)
            WHEN pcc.code_coding_code IN ('62220', '62223', '62225', '62230', '62252', '62256', '62258')
                THEN 'exclude_shunt'

            -- Burr holes (not tumor-related) (CPT 61154-61156)
            WHEN pcc.code_coding_code IN ('61154', '61156')
                THEN 'exclude_burr_hole'

            -- Craniotomy for trauma/hematoma (CPT 61312-61315)
            WHEN pcc.code_coding_code IN ('61312', '61313', '61314', '61315')
                THEN 'exclude_trauma'

            -- External ventricular drain (CPT 62160-62165)
            WHEN pcc.code_coding_code IN ('62160', '62161', '62162', '62164', '62165')
                THEN 'exclude_evd'

            ELSE NULL
        END as cpt_classification
    FROM fhir_prd_db.procedure_code_coding pcc
    WHERE LOWER(pcc.code_coding_system) LIKE '%cpt%'
),

-- SNOMED Code Classification (SECONDARY - semantic validation)
snomed_classifications AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as snomed_code,
        CASE
            -- Tumor-specific SNOMED codes
            WHEN pcc.code_coding_code = '118819003' THEN 'excision_neoplasm_brain'
            WHEN pcc.code_coding_code = '72561008' THEN 'biopsy_brain'
            WHEN pcc.code_coding_code = '25353009' THEN 'craniotomy'
            WHEN pcc.code_coding_code = '45368001' THEN 'transsphenoidal_hypophysectomy'
            WHEN pcc.code_coding_code = '392021009' THEN 'stereotactic_biopsy_brain'

            -- Non-tumor SNOMED codes (exclude)
            WHEN pcc.code_coding_code = '19923001' THEN 'exclude_vp_shunt'
            WHEN pcc.code_coding_code = '172821007' THEN 'exclude_evd'

            ELSE NULL
        END as snomed_classification
    FROM fhir_prd_db.procedure_code_coding pcc
    WHERE LOWER(pcc.code_coding_system) LIKE '%snomed%'
),

-- Enhanced Keyword Classification (TERTIARY - fallback for local codes)
procedure_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_system,
        pcc.code_coding_code,
        pcc.code_coding_display,

        -- Tumor surgery indicators (POSITIVE)
        CASE
            WHEN LOWER(pcc.code_coding_display) LIKE '%craniotomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%craniectomy%'
                OR LOWER(pcc.code_coding_display) LIKE '%tumor resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%mass resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%lesion resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%neoplasm resection%'
                OR LOWER(pcc.code_coding_display) LIKE '%stereotactic biopsy%'
                OR LOWER(pcc.code_coding_display) LIKE '%brain biopsy%'
                OR LOWER(pcc.code_coding_display) LIKE '%transsphenoidal%'
                OR LOWER(pcc.code_coding_display) LIKE '%endoscopic resection%'
            THEN 'keyword_tumor_surgery'

            -- Non-tumor indicators (NEGATIVE - exclude)
            WHEN LOWER(pcc.code_coding_display) LIKE '%shunt%'
                OR LOWER(pcc.code_coding_display) LIKE '%ventriculoperitoneal%'
                OR LOWER(pcc.code_coding_display) LIKE '%vp shunt%'
                OR LOWER(pcc.code_coding_display) LIKE '%external ventricular drain%'
                OR LOWER(pcc.code_coding_display) LIKE '%evd%'
                OR LOWER(pcc.code_coding_display) LIKE '%wound%'
                OR LOWER(pcc.code_coding_display) LIKE '%infection%'
                OR LOWER(pcc.code_coding_display) LIKE '%hematoma evacuation%'
                OR LOWER(pcc.code_coding_display) LIKE '%subdural evacuation%'
                OR LOWER(pcc.code_coding_display) LIKE '%angiography%'
                OR LOWER(pcc.code_coding_display) LIKE '%embolization%'
                OR LOWER(pcc.code_coding_display) LIKE '%consultation%'
                OR LOWER(pcc.code_coding_display) LIKE '%pre-operative%'
                OR LOWER(pcc.code_coding_display) LIKE '%post-operative%'
            THEN 'exclude_keyword'

            -- Generic surgical keywords (AMBIGUOUS - requires review)
            WHEN LOWER(pcc.code_coding_display) LIKE '%surgery%'
                OR LOWER(pcc.code_coding_display) LIKE '%surgical%'
                OR LOWER(pcc.code_coding_display) LIKE '%anesthesia%'
                OR LOWER(pcc.code_coding_display) LIKE '%anes%'
                OR LOWER(pcc.code_coding_display) LIKE '%oper%'
            THEN 'keyword_surgical_generic'

            ELSE NULL
        END as keyword_classification,

        -- Original is_surgical_keyword (BACKWARD COMPATIBILITY)
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

-- Procedure dates (unchanged)
procedure_dates AS (
    SELECT
        p.id as procedure_id,
        COALESCE(
            TRY(CAST(SUBSTR(p.performed_date_time, 1, 10) AS DATE)),
            TRY(CAST(SUBSTR(p.performed_period_start, 1, 10) AS DATE))
        ) as procedure_date
    FROM fhir_prd_db.procedure p
),

-- Combined classification logic
combined_classification AS (
    SELECT
        p.id as procedure_id,

        -- Prioritize CPT > SNOMED > Keyword
        COALESCE(
            cpt.cpt_classification,
            snomed.snomed_classification,
            pc.keyword_classification
        ) as procedure_classification,

        -- Individual classifications for debugging
        cpt.cpt_classification,
        cpt.cpt_code,
        snomed.snomed_classification,
        snomed.snomed_code,
        pc.keyword_classification,

        -- Tumor surgery flags
        CASE
            WHEN cpt.cpt_classification IS NOT NULL
                AND cpt.cpt_classification NOT LIKE 'exclude%'
                THEN true
            WHEN snomed.snomed_classification IS NOT NULL
                AND snomed.snomed_classification NOT LIKE 'exclude%'
                THEN true
            WHEN pc.keyword_classification = 'keyword_tumor_surgery'
                THEN true
            ELSE false
        END as is_tumor_surgery,

        -- Exclusion flag
        CASE
            WHEN cpt.cpt_classification LIKE 'exclude%'
                OR snomed.snomed_classification LIKE 'exclude%'
                OR pc.keyword_classification = 'exclude_keyword'
                THEN true
            ELSE false
        END as is_excluded_procedure,

        -- Surgery type categorization
        CASE
            WHEN cpt.cpt_classification LIKE '%biopsy%'
                OR snomed.snomed_classification LIKE '%biopsy%'
                OR pc.keyword_classification LIKE '%biopsy%'
                THEN 'biopsy'
            WHEN cpt.cpt_classification LIKE '%craniotomy%'
                OR cpt.cpt_classification LIKE '%craniectomy%'
                OR cpt.cpt_classification LIKE '%resection%'
                THEN 'resection'
            WHEN cpt.cpt_classification LIKE '%radiosurgery%'
                THEN 'radiosurgery'
            WHEN pc.keyword_classification = 'keyword_tumor_surgery'
                THEN 'tumor_procedure'
            WHEN pc.keyword_classification = 'keyword_surgical_generic'
                THEN 'surgical_generic'
            ELSE 'unknown'
        END as surgery_type,

        -- Confidence level
        CASE
            WHEN cpt.cpt_classification IS NOT NULL THEN 'high'
            WHEN snomed.snomed_classification IS NOT NULL THEN 'medium-high'
            WHEN pc.keyword_classification = 'keyword_tumor_surgery' THEN 'medium'
            WHEN pc.keyword_classification = 'keyword_surgical_generic' THEN 'low'
            ELSE 'unknown'
        END as classification_confidence

    FROM fhir_prd_db.procedure p
    LEFT JOIN cpt_classifications cpt ON p.id = cpt.procedure_id
    LEFT JOIN snomed_classifications snomed ON p.id = snomed.procedure_id
    LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
)

-- Main SELECT (same as original + new classification fields)
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
    cc.snomed_classification,
    cc.snomed_code,
    cc.keyword_classification,
    cc.is_tumor_surgery,
    cc.is_excluded_procedure,
    cc.surgery_type,
    cc.classification_confidence,

    -- Procedure category (pcat_ prefix) - UNCHANGED
    pcat.category_coding_display as pcat_category_coding_display,

    -- Body site (pbs_ prefix) - UNCHANGED
    pbs.body_site_text as pbs_body_site_text,

    -- Performer (pp_ prefix) - UNCHANGED
    pp.performer_actor_display as pp_performer_actor_display,
    pp.performer_function_text as pp_performer_function_text,

    -- Reason code (prc_ prefix) - UNCHANGED
    prc.reason_code_text as prc_reason_code_text,

    -- Report reference (ppr_ prefix) - UNCHANGED
    ppr.report_reference as ppr_report_reference,
    ppr.report_display as ppr_report_display

FROM fhir_prd_db.procedure p
LEFT JOIN procedure_codes pc ON p.id = pc.procedure_id
LEFT JOIN combined_classification cc ON p.id = cc.procedure_id
LEFT JOIN procedure_dates pd ON p.id = pd.procedure_id
LEFT JOIN fhir_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
LEFT JOIN fhir_prd_db.procedure_body_site pbs ON p.id = pbs.procedure_id
LEFT JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id
LEFT JOIN fhir_prd_db.procedure_reason_code prc ON p.id = prc.procedure_id
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


-- ================================================================================
-- 2. NEW: v_tumor_surgeries_with_pathology
-- ================================================================================
-- PURPOSE: Link tumor surgeries to pathology confirmations
-- ENABLES: Accurate diagnostic event identification
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_tumor_surgeries_with_pathology AS
WITH
-- Step 1: Get tumor procedures (using enhanced classification)
tumor_procedures AS (
    SELECT *
    FROM fhir_prd_db.v_procedures
    WHERE is_tumor_surgery = true
        AND is_excluded_procedure = false
),

-- Step 2: Get pathology reports with brain tumor confirmations
pathology_confirmations AS (
    SELECT
        dr.subject_reference as patient_fhir_id,
        dr.id as pathology_report_id,
        dr.effective_date_time as pathology_date,
        dr.code_text as report_type,
        dr.conclusion as pathology_findings,
        dr.status as pathology_status,

        -- Flag brain tumor pathology
        CASE
            WHEN LOWER(dr.conclusion) LIKE '%glioma%'
                OR LOWER(dr.conclusion) LIKE '%glioblastoma%'
                OR LOWER(dr.conclusion) LIKE '%astrocytoma%'
                OR LOWER(dr.conclusion) LIKE '%oligodendroglioma%'
                OR LOWER(dr.conclusion) LIKE '%ependymoma%'
                OR LOWER(dr.conclusion) LIKE '%medulloblastoma%'
                OR LOWER(dr.conclusion) LIKE '%atypical teratoid%'
                OR LOWER(dr.conclusion) LIKE '%at/rt%'
                OR LOWER(dr.conclusion) LIKE '%craniopharyngioma%'
                OR LOWER(dr.conclusion) LIKE '%pnet%'
                OR LOWER(dr.conclusion) LIKE '%germinoma%'
                OR LOWER(dr.conclusion) LIKE '%pineoblastoma%'
                OR LOWER(dr.conclusion) LIKE '%choroid plexus%'
                OR LOWER(dr.conclusion) LIKE '%meningioma%'
                OR LOWER(dr.conclusion) LIKE '%schwannoma%'
                OR LOWER(dr.conclusion) LIKE '%glioneural%'
            THEN true
            ELSE false
        END as confirms_brain_tumor,

        -- Extract tumor type
        CASE
            WHEN LOWER(dr.conclusion) LIKE '%glioblastoma%' THEN 'Glioblastoma'
            WHEN LOWER(dr.conclusion) LIKE '%diffuse midline glioma%' THEN 'Diffuse Midline Glioma'
            WHEN LOWER(dr.conclusion) LIKE '%pilocytic astrocytoma%' THEN 'Pilocytic Astrocytoma'
            WHEN LOWER(dr.conclusion) LIKE '%diffuse astrocytoma%' THEN 'Diffuse Astrocytoma'
            WHEN LOWER(dr.conclusion) LIKE '%oligodendroglioma%' THEN 'Oligodendroglioma'
            WHEN LOWER(dr.conclusion) LIKE '%ependymoma%' THEN 'Ependymoma'
            WHEN LOWER(dr.conclusion) LIKE '%medulloblastoma%' THEN 'Medulloblastoma'
            WHEN LOWER(dr.conclusion) LIKE '%atypical teratoid%' THEN 'Atypical Teratoid Rhabdoid Tumor'
            WHEN LOWER(dr.conclusion) LIKE '%at/rt%' THEN 'Atypical Teratoid Rhabdoid Tumor'
            WHEN LOWER(dr.conclusion) LIKE '%craniopharyngioma%' THEN 'Craniopharyngioma'
            ELSE 'Other Brain Tumor'
        END as tumor_type_extracted

    FROM fhir_prd_db.diagnostic_report dr
    WHERE (LOWER(dr.category_text) LIKE '%pathology%'
           OR LOWER(dr.code_text) LIKE '%pathology%'
           OR LOWER(dr.code_text) LIKE '%biopsy%'
           OR LOWER(dr.code_text) LIKE '%surgical specimen%'
           OR LOWER(dr.code_text) LIKE '%surgical pathology%')
        AND dr.status IN ('final', 'amended', 'corrected')  -- Only finalized reports
)

-- Step 3: Join procedures to pathology
SELECT
    tp.*,
    pc.pathology_report_id,
    pc.pathology_date,
    pc.report_type as pathology_report_type,
    pc.pathology_findings,
    pc.pathology_status,
    pc.confirms_brain_tumor,
    pc.tumor_type_extracted,

    -- Calculate days between procedure and pathology report
    DATE_DIFF('day',
        tp.procedure_date,
        TRY(CAST(SUBSTR(pc.pathology_date, 1, 10) AS DATE))) as days_to_pathology,

    -- Flag if pathology confirms tumor within reasonable timeframe (0-14 days)
    CASE
        WHEN pc.confirms_brain_tumor = true
            AND DATE_DIFF('day',
                tp.procedure_date,
                TRY(CAST(SUBSTR(pc.pathology_date, 1, 10) AS DATE))) BETWEEN 0 AND 14
        THEN true
        ELSE false
    END as has_pathology_confirmation

FROM tumor_procedures tp
LEFT JOIN pathology_confirmations pc
    ON tp.patient_fhir_id = pc.patient_fhir_id
    AND pc.confirms_brain_tumor = true
    -- Pathology report typically within 14 days of procedure
    AND DATE_DIFF('day',
        tp.procedure_date,
        TRY(CAST(SUBSTR(pc.pathology_date, 1, 10) AS DATE))) BETWEEN 0 AND 14
ORDER BY tp.patient_fhir_id, tp.procedure_date;


-- ================================================================================
-- 3. NEW: v_surgical_events_classified
-- ================================================================================
-- PURPOSE: Classify surgical events with temporal logic
-- ALIGNS WITH: CBTN specimen_collection_origin taxonomy
-- ENABLES: Automated age_at_diagnosis calculation
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_surgical_events_classified AS
WITH
-- Step 1: Get only pathology-confirmed tumor surgeries
confirmed_tumor_surgeries AS (
    SELECT *
    FROM fhir_prd_db.v_tumor_surgeries_with_pathology
    WHERE has_pathology_confirmation = true
),

-- Step 2: Add temporal sequencing
ranked_surgeries AS (
    SELECT
        *,
        -- Sequence number (1 = first surgery)
        ROW_NUMBER() OVER (
            PARTITION BY patient_fhir_id
            ORDER BY procedure_date,
                     -- Biopsies before resections on same day
                     CASE WHEN surgery_type = 'biopsy' THEN 1
                          WHEN surgery_type = 'resection' THEN 2
                          ELSE 3 END
        ) as surgery_sequence,

        -- First surgery date for this patient
        FIRST_VALUE(procedure_date) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY procedure_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) as first_surgery_date,

        -- Previous surgery date
        LAG(procedure_date) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY procedure_date
        ) as previous_surgery_date,

        -- Previous surgery type
        LAG(surgery_type) OVER (
            PARTITION BY patient_fhir_id
            ORDER BY procedure_date
        ) as previous_surgery_type

    FROM confirmed_tumor_surgeries
)

-- Step 3: Classify surgical events
SELECT
    *,

    -- Days since previous surgery
    DATE_DIFF('day', previous_surgery_date, procedure_date) as days_since_previous_surgery,

    -- Days since first surgery
    DATE_DIFF('day', first_surgery_date, procedure_date) as days_since_first_surgery,

    -- CBTN specimen_collection_origin classification
    CASE
        -- 4 = Initial CNS Tumor Surgery (first pathology-confirmed procedure)
        WHEN surgery_sequence = 1
            THEN '4_initial_cns_tumor_surgery'

        -- 5 = Repeat resection (within 30 days of first surgery, further debulking)
        WHEN surgery_sequence > 1
            AND DATE_DIFF('day', first_surgery_date, procedure_date) <= 30
            AND surgery_type = 'resection'
            THEN '5_repeat_resection'

        -- Subsequent surgeries (requires treatment data integration to distinguish)
        -- 6 = Second look surgery (after primary treatment)
        -- 7 = Recurrence surgery (documented disease recurrence)
        -- 8 = Progressive surgery (during treatment, disease progression)

        WHEN surgery_sequence > 1
            AND DATE_DIFF('day', first_surgery_date, procedure_date) > 30
            THEN 'requires_treatment_integration'

        ELSE 'unclassified'
    END as cbtn_specimen_collection_origin,

    -- Flag for diagnostic event (age_at_diagnosis)
    CASE WHEN surgery_sequence = 1 THEN true ELSE false END as is_diagnostic_event,

    -- Suggested next steps for unclassified
    CASE
        WHEN surgery_sequence > 1
            AND DATE_DIFF('day', first_surgery_date, procedure_date) > 30
            THEN 'Review operative note indication: recurrence vs progression vs second look'
        ELSE NULL
    END as classification_notes

FROM ranked_surgeries
ORDER BY patient_fhir_id, surgery_sequence;


-- ================================================================================
-- VERIFICATION QUERIES
-- ================================================================================

-- Test 1: Count procedures by classification
SELECT
    procedure_classification,
    surgery_type,
    classification_confidence,
    is_tumor_surgery,
    is_excluded_procedure,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_procedures
WHERE procedure_classification IS NOT NULL
GROUP BY procedure_classification, surgery_type, classification_confidence,
         is_tumor_surgery, is_excluded_procedure
ORDER BY procedure_count DESC;

-- Test 2: Tumor surgeries with pathology confirmation rate
SELECT
    surgery_type,
    COUNT(*) as total_tumor_surgeries,
    SUM(CASE WHEN has_pathology_confirmation THEN 1 ELSE 0 END) as with_pathology,
    ROUND(100.0 * SUM(CASE WHEN has_pathology_confirmation THEN 1 ELSE 0 END) / COUNT(*), 1) as confirmation_rate_pct
FROM fhir_prd_db.v_tumor_surgeries_with_pathology
GROUP BY surgery_type
ORDER BY total_tumor_surgeries DESC;

-- Test 3: Surgical event classification distribution
SELECT
    cbtn_specimen_collection_origin,
    surgery_type,
    COUNT(*) as event_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_surgical_events_classified
GROUP BY cbtn_specimen_collection_origin, surgery_type
ORDER BY event_count DESC;

-- Test 4: Patient-level diagnostic event summary
SELECT
    patient_fhir_id,
    MIN(procedure_date) as first_surgery_date,
    MIN(age_at_procedure_days) as age_at_diagnosis_days,
    MIN(age_at_procedure_days) / 365.25 as age_at_diagnosis_years,
    MIN(tumor_type_extracted) as primary_tumor_type,
    COUNT(*) as total_tumor_surgeries
FROM fhir_prd_db.v_surgical_events_classified
WHERE is_diagnostic_event = true
GROUP BY patient_fhir_id
ORDER BY first_surgery_date;

-- Test 5: Specific patient verification (replace with actual patient ID)
SELECT * FROM fhir_prd_db.v_procedures
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND is_tumor_surgery = true
ORDER BY procedure_date;

SELECT * FROM fhir_prd_db.v_surgical_events_classified
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY surgery_sequence;
