-- ================================================================================
-- HYDROCEPHALUS DATA ASSESSMENT QUERIES
-- ================================================================================
-- Date: October 18, 2025
-- Purpose: Assess hydrocephalus and shunt data availability in FHIR tables
-- Test Patients:
--   - e4BwD8ZYDBccepXcJ.Ilo3w3 (pilot patient)
--   - eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3
--   - enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3
--   - emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3
-- ================================================================================

-- ================================================================================
-- QUERY 1: HYDROCEPHALUS CONDITIONS
-- ================================================================================
-- Objective: Identify patients with documented hydrocephalus diagnosis
-- Maps to: hydro_yn, medical_conditions_present_at_event(11)
-- ================================================================================

SELECT
    c.subject_reference as patient_fhir_id,
    c.id as condition_id,
    c.code_text,
    c.code_coding,
    c.clinical_status,
    c.verification_status,
    c.category_text,
    c.onset_date_time,
    c.onset_period_start,
    c.onset_period_end,
    c.recorded_date,
    c.recorder_display,

    -- Classification
    CASE
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.0') THEN 'Communicating hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.1') THEN 'Obstructive hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.2') THEN 'Normal-pressure hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.3') THEN 'Post-traumatic hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.8') THEN 'Other hydrocephalus'
        WHEN REGEXP_LIKE(c.code_coding, 'G91\\.9') THEN 'Hydrocephalus, unspecified'
        WHEN REGEXP_LIKE(c.code_coding, 'Q03\\.') THEN 'Congenital hydrocephalus'
        ELSE 'Hydrocephalus (text match)'
    END as hydrocephalus_type

FROM fhir_prd_db.condition c
WHERE c.subject_reference IS NOT NULL
  AND (
      LOWER(c.code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(c.code_coding, 'G91\\.')
      OR REGEXP_LIKE(c.code_coding, 'Q03\\.')
  )
  AND c.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY c.subject_reference, c.onset_date_time;


-- ================================================================================
-- QUERY 2: SHUNT PROCEDURES
-- ================================================================================
-- Objective: Identify shunt procedures with type classification
-- Maps to: shunt_required, hydro_surgical_management
-- ================================================================================

SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text,
    p.code_coding,
    p.status,
    p.performed_date_time,
    p.performed_period_start,
    p.performed_period_end,

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
        ELSE 'Other Shunt'
    END as shunt_type,

    -- Procedure category
    CASE
        WHEN LOWER(p.code_text) LIKE '%placement%'
             OR LOWER(p.code_text) LIKE '%insertion%'
             OR LOWER(p.code_text) LIKE '%creation%'
             OR LOWER(p.code_text) LIKE '%establish%' THEN 'Initial Placement'
        WHEN LOWER(p.code_text) LIKE '%revision%'
             OR LOWER(p.code_text) LIKE '%replacement%'
             OR LOWER(p.code_text) LIKE '%adjust%' THEN 'Revision'
        WHEN LOWER(p.code_text) LIKE '%removal%'
             OR LOWER(p.code_text) LIKE '%explant%' THEN 'Removal'
        WHEN LOWER(p.code_text) LIKE '%reprogram%'
             OR p.code_coding LIKE '%62252%' THEN 'Reprogramming'
        ELSE 'Unknown Category'
    END as procedure_category,

    -- CPT code check
    CASE
        WHEN p.code_coding LIKE '%62220%' THEN 'CPT 62220: VA shunt creation'
        WHEN p.code_coding LIKE '%62223%' THEN 'CPT 62223: VP shunt creation'
        WHEN p.code_coding LIKE '%62225%' THEN 'CPT 62225: Catheter replacement'
        WHEN p.code_coding LIKE '%62230%' THEN 'CPT 62230: Shunt revision'
        WHEN p.code_coding LIKE '%62252%' THEN 'CPT 62252: Shunt reprogramming'
        WHEN p.code_coding LIKE '%62256%' THEN 'CPT 62256: Shunt removal'
        WHEN p.code_coding LIKE '%62258%' THEN 'CPT 62258: Complete shunt replacement'
        WHEN p.code_coding LIKE '%62200%' THEN 'CPT 62200: Ventriculocisternostomy'
        WHEN p.code_coding LIKE '%31291%' THEN 'CPT 31291: ETV'
        ELSE NULL
    END as cpt_code_description

FROM fhir_prd_db.procedure p
WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
      OR LOWER(p.code_text) LIKE '%csf%diversion%'
      OR p.code_coding LIKE '%62220%'
      OR p.code_coding LIKE '%62223%'
      OR p.code_coding LIKE '%62225%'
      OR p.code_coding LIKE '%62230%'
      OR p.code_coding LIKE '%62252%'
      OR p.code_coding LIKE '%62256%'
      OR p.code_coding LIKE '%62258%'
      OR p.code_coding LIKE '%31291%'
  )
  AND p.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY p.subject_reference, p.performed_period_start;


-- ================================================================================
-- QUERY 3: PROGRAMMABLE SHUNT DEVICES
-- ================================================================================
-- Objective: Identify programmable shunt devices
-- Maps to: hydro_shunt_programmable
-- ================================================================================

SELECT
    d.patient_reference as patient_fhir_id,
    d.id as device_id,
    d.device_name,
    d.type_text,
    d.manufacturer,
    d.model_number,
    d.status,

    -- Programmable valve detection
    CASE
        WHEN LOWER(d.device_name) LIKE '%programmable%'
             OR LOWER(d.type_text) LIKE '%programmable%'
             OR LOWER(d.model_number) LIKE '%strata%'
             OR LOWER(d.model_number) LIKE '%hakim%'
             OR LOWER(d.model_number) LIKE '%polaris%'
             OR LOWER(d.model_number) LIKE '%progav%'
             OR LOWER(d.manufacturer) LIKE '%medtronic%'
             OR LOWER(d.manufacturer) LIKE '%codman%'
             OR LOWER(d.manufacturer) LIKE '%sophysa%'
             OR LOWER(d.manufacturer) LIKE '%aesculap%' THEN true
        ELSE false
    END as is_programmable,

    -- Device category
    CASE
        WHEN LOWER(d.type_text) LIKE '%ventriculoperitoneal%'
             OR LOWER(d.device_name) LIKE '%vp%shunt%' THEN 'VP Shunt'
        WHEN LOWER(d.type_text) LIKE '%ventriculoatrial%'
             OR LOWER(d.device_name) LIKE '%va%shunt%' THEN 'VA Shunt'
        WHEN LOWER(d.type_text) LIKE '%csf%'
             OR LOWER(d.device_name) LIKE '%cerebrospinal%' THEN 'CSF Shunt'
        ELSE 'Other'
    END as device_category

FROM fhir_prd_db.device d
WHERE d.patient_reference IS NOT NULL
  AND (
      LOWER(d.type_text) LIKE '%shunt%'
      OR LOWER(d.type_text) LIKE '%csf%'
      OR LOWER(d.device_name) LIKE '%ventriculo%'
      OR LOWER(d.device_name) LIKE '%shunt%'
  )
  AND d.patient_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY d.patient_reference;


-- ================================================================================
-- QUERY 4: IMAGING STUDIES FOR HYDROCEPHALUS DIAGNOSIS
-- ================================================================================
-- Objective: Identify CT/MRI studies documenting hydrocephalus
-- Maps to: hydro_method_diagnosed
-- ================================================================================

SELECT
    dr.subject_reference as patient_fhir_id,
    dr.id as report_id,
    dr.code_text as study_type,
    dr.effective_date_time,
    dr.effective_period_start,
    dr.status,
    dr.conclusion,

    -- Imaging modality
    CASE
        WHEN LOWER(dr.code_text) LIKE '%ct%'
             OR LOWER(dr.code_text) LIKE '%computed%tomography%' THEN 'CT'
        WHEN LOWER(dr.code_text) LIKE '%mri%'
             OR LOWER(dr.code_text) LIKE '%magnetic%resonance%' THEN 'MRI'
        WHEN LOWER(dr.code_text) LIKE '%ultrasound%'
             OR LOWER(dr.code_text) LIKE '%us%' THEN 'Ultrasound'
        ELSE 'Other'
    END as imaging_modality,

    -- Hydrocephalus findings
    CASE
        WHEN LOWER(dr.conclusion) LIKE '%hydroceph%' THEN 'Hydrocephalus documented'
        WHEN LOWER(dr.conclusion) LIKE '%ventriculomegaly%' THEN 'Ventriculomegaly'
        WHEN LOWER(dr.conclusion) LIKE '%enlarged%ventricle%' THEN 'Enlarged ventricles'
        WHEN LOWER(dr.conclusion) LIKE '%ventricular%dilation%' THEN 'Ventricular dilation'
        ELSE 'Other finding'
    END as finding_category

FROM fhir_prd_db.diagnostic_report dr
WHERE dr.subject_reference IS NOT NULL
  AND (
      LOWER(dr.code_text) LIKE '%brain%'
      OR LOWER(dr.code_text) LIKE '%head%'
      OR LOWER(dr.code_text) LIKE '%cranial%'
      OR LOWER(dr.code_text) LIKE '%neuro%'
  )
  AND (
      LOWER(dr.conclusion) LIKE '%hydroceph%'
      OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
      OR LOWER(dr.conclusion) LIKE '%enlarged%ventricle%'
      OR LOWER(dr.conclusion) LIKE '%ventricular%dilation%'
  )
  AND dr.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY dr.subject_reference, dr.effective_date_time;


-- ================================================================================
-- QUERY 5: MEDICAL MANAGEMENT - STEROIDS
-- ================================================================================
-- Objective: Identify steroid therapy for hydrocephalus
-- Maps to: hydro_nonsurg_management (Steroid)
-- ================================================================================

SELECT
    mr.subject_reference as patient_fhir_id,
    mr.id as medication_request_id,
    mr.medication_codeable_concept_text as medication,
    mr.authored_on,
    mr.status,
    mr.intent,
    mrrc.reason_code_text,

    -- Steroid classification
    CASE
        WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%dexamethasone%' THEN 'Dexamethasone'
        WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%methylprednisolone%' THEN 'Methylprednisolone'
        WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%prednisone%' THEN 'Prednisone'
        WHEN LOWER(mr.medication_codeable_concept_text) LIKE '%prednisolone%' THEN 'Prednisolone'
        ELSE 'Other steroid'
    END as steroid_type

FROM fhir_prd_db.medication_request mr
LEFT JOIN fhir_prd_db.medication_request_reason_code mrrc
    ON mr.id = mrrc.medication_request_id
WHERE mr.subject_reference IS NOT NULL
  AND (
      LOWER(mr.medication_codeable_concept_text) LIKE '%dexamethasone%'
      OR LOWER(mr.medication_codeable_concept_text) LIKE '%methylprednisolone%'
      OR LOWER(mr.medication_codeable_concept_text) LIKE '%prednisone%'
      OR LOWER(mr.medication_codeable_concept_text) LIKE '%prednisolone%'
  )
  AND (
      LOWER(mrrc.reason_code_text) LIKE '%hydroceph%'
      OR LOWER(mrrc.reason_code_text) LIKE '%intracranial%pressure%'
      OR LOWER(mrrc.reason_code_text) LIKE '%icp%'
      OR LOWER(mrrc.reason_code_text) LIKE '%brain%edema%'
  )
  AND mr.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY mr.subject_reference, mr.authored_on;


-- ================================================================================
-- QUERY 6: COHORT-WIDE ASSESSMENT - ALL PATIENTS
-- ================================================================================
-- Objective: Get counts across all patients to assess overall coverage
-- ================================================================================

-- 6A: Count of patients with hydrocephalus conditions
SELECT
    'Hydrocephalus Conditions' as data_type,
    COUNT(DISTINCT c.subject_reference) as patient_count,
    COUNT(c.id) as record_count
FROM fhir_prd_db.condition c
WHERE c.subject_reference IS NOT NULL
  AND (
      LOWER(c.code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(c.code_coding, 'G91\\.')
      OR REGEXP_LIKE(c.code_coding, 'Q03\\.')
  )

UNION ALL

-- 6B: Count of patients with shunt procedures
SELECT
    'Shunt Procedures' as data_type,
    COUNT(DISTINCT p.subject_reference) as patient_count,
    COUNT(p.id) as record_count
FROM fhir_prd_db.procedure p
WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
  )

UNION ALL

-- 6C: Count of patients with shunt devices
SELECT
    'Shunt Devices' as data_type,
    COUNT(DISTINCT d.patient_reference) as patient_count,
    COUNT(d.id) as record_count
FROM fhir_prd_db.device d
WHERE d.patient_reference IS NOT NULL
  AND (
      LOWER(d.type_text) LIKE '%shunt%'
      OR LOWER(d.device_name) LIKE '%ventriculo%'
  )

UNION ALL

-- 6D: Count of patients with hydrocephalus imaging findings
SELECT
    'Hydrocephalus Imaging' as data_type,
    COUNT(DISTINCT dr.subject_reference) as patient_count,
    COUNT(dr.id) as record_count
FROM fhir_prd_db.diagnostic_report dr
WHERE dr.subject_reference IS NOT NULL
  AND (
      LOWER(dr.conclusion) LIKE '%hydroceph%'
      OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
  );


-- ================================================================================
-- QUERY 7: DETAILED PROCEDURE NOTES
-- ================================================================================
-- Objective: Get procedure notes for programmable valve information
-- Maps to: hydro_shunt_programmable (from narrative text)
-- ================================================================================

SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text,
    p.performed_period_start,
    pn.note_text,
    pn.note_time,

    -- Check for programmable valve mentions
    CASE
        WHEN LOWER(pn.note_text) LIKE '%programmable%' THEN true
        WHEN LOWER(pn.note_text) LIKE '%strata%' THEN true
        WHEN LOWER(pn.note_text) LIKE '%hakim%' THEN true
        WHEN LOWER(pn.note_text) LIKE '%polaris%' THEN true
        WHEN LOWER(pn.note_text) LIKE '%progav%' THEN true
        ELSE false
    END as mentions_programmable

FROM fhir_prd_db.procedure p
JOIN fhir_prd_db.procedure_note pn ON p.id = pn.procedure_id
WHERE p.subject_reference IS NOT NULL
  AND LOWER(p.code_text) LIKE '%shunt%'
  AND p.subject_reference IN (
      'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
      'Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',
      'Patient/enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3',
      'Patient/emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
  )
ORDER BY p.subject_reference, p.performed_period_start, pn.note_time;
