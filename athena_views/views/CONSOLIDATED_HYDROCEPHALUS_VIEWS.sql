-- ================================================================================
-- CONSOLIDATED HYDROCEPHALUS VIEWS
-- ================================================================================
-- Date: October 18, 2025
-- Purpose: Comprehensive hydrocephalus and shunt data extraction
-- Coverage: 427 hydrocephalus diagnoses, 1,196 shunt procedures
-- CBTN Fields: 11 total (6/11 high coverage, 2/11 medium, 3/11 low/NLP)
-- ================================================================================

-- ================================================================================
-- 1. v_hydrocephalus_diagnosis - HYDROCEPHALUS DIAGNOSIS EVENTS
-- ================================================================================
-- Purpose: Track hydrocephalus diagnosis events with imaging context
-- Data Sources:
--   1. problem_list_diagnoses (primary) - 427 records
--   2. diagnostic_report (imaging) - CT/MRI findings
--   3. encounter (hospitalization context)
--
-- CBTN Fields Covered:
--   - hydro_yn (presence flag)
--   - medical_conditions_present_at_event(11) (hydrocephalus at diagnosis)
--   - hydro_event_date (diagnosis date)
--   - hydro_method_diagnosed (clinical vs imaging)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_hydrocephalus_diagnosis AS
WITH
-- Primary hydrocephalus diagnoses from problem list
hydro_diagnoses AS (
    SELECT
        pld.patient_id as patient_fhir_id,
        pld.condition_id,
        pld.diagnosis_name,
        pld.icd10_code,
        pld.icd10_display,
        pld.snomed_code,
        pld.snomed_display,
        pld.clinical_status_text,
        pld.onset_date_time,
        pld.abatement_date_time,
        pld.recorded_date,

        -- Classify hydrocephalus type from ICD-10
        CASE
            WHEN pld.icd10_code LIKE 'G91.0%' THEN 'Communicating'
            WHEN pld.icd10_code LIKE 'G91.1%' THEN 'Obstructive'
            WHEN pld.icd10_code LIKE 'G91.2%' THEN 'Normal-pressure'
            WHEN pld.icd10_code LIKE 'G91.3%' THEN 'Post-traumatic'
            WHEN pld.icd10_code LIKE 'G91.8%' THEN 'Other'
            WHEN pld.icd10_code LIKE 'G91.9%' THEN 'Unspecified'
            WHEN pld.icd10_code LIKE 'Q03%' THEN 'Congenital'
            ELSE 'Unclassified'
        END as hydrocephalus_type_code

    FROM fhir_prd_db.problem_list_diagnoses pld
    WHERE pld.patient_id IS NOT NULL
      AND (
          LOWER(pld.diagnosis_name) LIKE '%hydroceph%'
          OR pld.icd10_code LIKE 'G91%'
          OR pld.icd10_code LIKE 'Q03%'
      )
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

-- Aggregate imaging per patient for diagnosis method
imaging_summary AS (
    SELECT
        patient_fhir_id,
        LISTAGG(DISTINCT imaging_modality, ' | ') WITHIN GROUP (ORDER BY imaging_modality) as imaging_modalities,
        COUNT(DISTINCT report_id) as total_imaging_studies,
        COUNT(DISTINCT CASE WHEN imaging_modality = 'CT' THEN report_id END) as ct_studies,
        COUNT(DISTINCT CASE WHEN imaging_modality = 'MRI' THEN report_id END) as mri_studies,
        MIN(imaging_date) as first_imaging_date,
        MAX(imaging_date) as most_recent_imaging_date
    FROM hydro_imaging
    GROUP BY patient_fhir_id
)

-- Main SELECT: Combine diagnosis and imaging data
SELECT
    -- Patient identifier
    hd.patient_fhir_id,

    -- Diagnosis fields (pld_ prefix for problem list diagnosis)
    hd.condition_id as pld_condition_id,
    hd.diagnosis_name as pld_diagnosis_name,
    hd.icd10_code as pld_icd10_code,
    hd.icd10_display as pld_icd10_display,
    hd.snomed_code as pld_snomed_code,
    hd.snomed_display as pld_snomed_display,
    hd.clinical_status_text as pld_clinical_status,
    hd.onset_date_time as pld_onset_date,
    hd.abatement_date_time as pld_abatement_date,
    hd.recorded_date as pld_recorded_date,
    hd.hydrocephalus_type_code as pld_hydro_type_code,

    -- Imaging summary fields (img_ prefix)
    img.imaging_modalities as img_modalities_used,
    img.total_imaging_studies as img_total_studies,
    img.ct_studies as img_ct_count,
    img.mri_studies as img_mri_count,
    img.first_imaging_date as img_first_date,
    img.most_recent_imaging_date as img_most_recent_date,

    -- CBTN field mappings
    true as hydro_yn,  -- All records have hydrocephalus
    hd.onset_date_time as hydro_event_date,  -- Primary event date

    -- Diagnosis method (Clinical vs Imaging)
    CASE
        WHEN img.total_imaging_studies > 0 THEN 'Imaging'
        ELSE 'Clinical'
    END as hydro_method_diagnosed,

    -- Specific imaging modalities used (checkbox mapping)
    CASE WHEN img.ct_studies > 0 THEN true ELSE false END as diagnosed_by_ct,
    CASE WHEN img.mri_studies > 0 THEN true ELSE false END as diagnosed_by_mri,
    CASE WHEN img.total_imaging_studies = 0 THEN true ELSE false END as diagnosed_clinically,

    -- Data quality indicators
    CASE WHEN hd.icd10_code IS NOT NULL THEN true ELSE false END as has_icd10_code,
    CASE WHEN hd.onset_date_time IS NOT NULL THEN true ELSE false END as has_onset_date,
    CASE WHEN img.total_imaging_studies > 0 THEN true ELSE false END as has_imaging_documentation

FROM hydro_diagnoses hd
LEFT JOIN imaging_summary img ON hd.patient_fhir_id = img.patient_fhir_id

ORDER BY hd.patient_fhir_id, hd.onset_date_time;


-- ================================================================================
-- 2. v_hydrocephalus_procedures - SHUNT PROCEDURES AND MANAGEMENT
-- ================================================================================
-- Purpose: Track all hydrocephalus-related procedures with type classification
-- Data Sources:
--   1. procedure (primary) - 1,196 shunt procedures
--   2. procedure_note (operative details)
--   3. procedure_code_coding (CPT codes)
--   4. device (programmable shunt details)
--
-- CBTN Fields Covered:
--   - shunt_required (shunt type)
--   - hydro_surgical_management (procedure category)
--   - hydro_shunt_programmable (from device/notes)
--   - hydro_intervention (surgical flag)
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_hydrocephalus_procedures AS
WITH
-- Primary shunt procedures
shunt_procedures AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        p.id as procedure_id,
        p.code_text,
        p.status as proc_status,
        p.performed_date_time as proc_performed_datetime,
        p.performed_period_start as proc_period_start,
        p.performed_period_end as proc_period_end,
        p.category_text as proc_category_text,
        p.outcome_text as proc_outcome_text,
        p.location_display as proc_location,

        -- Shunt type classification (maps to shunt_required CBTN field)
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
            ELSE 'Other'
        END as shunt_type,

        -- Procedure category (maps to hydro_surgical_management CBTN field)
        CASE
            WHEN LOWER(p.code_text) LIKE '%placement%'
                 OR LOWER(p.code_text) LIKE '%insertion%'
                 OR LOWER(p.code_text) LIKE '%creation%'
                 OR LOWER(p.code_text) LIKE '%establish%' THEN 'VPS Placement'
            WHEN LOWER(p.code_text) LIKE '%revision%'
                 OR LOWER(p.code_text) LIKE '%replacement%'
                 OR LOWER(p.code_text) LIKE '%adjust%' THEN 'VPS Revision'
            WHEN LOWER(p.code_text) LIKE '%removal%'
                 OR LOWER(p.code_text) LIKE '%explant%' THEN 'Removal'
            WHEN LOWER(p.code_text) LIKE '%reprogram%' THEN 'Reprogramming'
            WHEN LOWER(p.code_text) LIKE '%evd%'
                 OR LOWER(p.code_text) LIKE '%temporary%' THEN 'Temporary EVD'
            WHEN LOWER(p.code_text) LIKE '%etv%'
                 OR LOWER(p.code_text) LIKE '%ventriculostomy%' THEN 'ETV'
            ELSE 'Other'
        END as procedure_category,

        -- CPT code hints (for validation)
        CASE
            WHEN p.code_text LIKE '%62220%' THEN '62220: VA shunt'
            WHEN p.code_text LIKE '%62223%' THEN '62223: VP shunt'
            WHEN p.code_text LIKE '%62230%' THEN '62230: Shunt revision'
            WHEN p.code_text LIKE '%62252%' THEN '62252: Reprogramming'
            WHEN p.code_text LIKE '%31291%' THEN '31291: ETV'
            ELSE NULL
        END as cpt_code_hint

    FROM fhir_prd_db.procedure p
    WHERE p.subject_reference IS NOT NULL
      AND (
          LOWER(p.code_text) LIKE '%shunt%'
          OR LOWER(p.code_text) LIKE '%ventriculostomy%'
          OR LOWER(p.code_text) LIKE '%ventricular%drain%'
          OR LOWER(p.code_text) LIKE '%csf%diversion%'
      )
),

-- Procedure notes (for programmable valve detection)
procedure_notes_agg AS (
    SELECT
        pn.procedure_id,
        LISTAGG(pn.note_text, ' | ') WITHIN GROUP (ORDER BY pn.note_time) as notes_aggregated,

        -- Check for programmable valve mentions
        MAX(CASE
            WHEN LOWER(pn.note_text) LIKE '%programmable%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%strata%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%hakim%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%polaris%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%progav%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%medtronic%' THEN true
            WHEN LOWER(pn.note_text) LIKE '%codman%' THEN true
            ELSE false
        END) as mentions_programmable_valve

    FROM fhir_prd_db.procedure_note pn
    WHERE pn.procedure_id IN (SELECT procedure_id FROM shunt_procedures)
    GROUP BY pn.procedure_id
),

-- Device table (programmable shunt devices)
shunt_devices AS (
    SELECT
        d.patient_reference as patient_fhir_id,
        d.id as device_id,
        d.device_name,
        d.type_text as device_type,
        d.manufacturer,
        d.model_number,
        d.status as device_status,

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
        END as is_programmable

    FROM fhir_prd_db.device d
    WHERE d.patient_reference IS NOT NULL
      AND (
          LOWER(d.type_text) LIKE '%shunt%'
          OR LOWER(d.device_name) LIKE '%ventriculo%'
          OR LOWER(d.device_name) LIKE '%csf%'
      )
),

-- Aggregate devices per patient
patient_devices AS (
    SELECT
        patient_fhir_id,
        COUNT(*) as total_shunt_devices,
        MAX(is_programmable) as has_programmable_shunt,
        LISTAGG(DISTINCT device_name, ' | ') WITHIN GROUP (ORDER BY device_name) as device_names,
        LISTAGG(DISTINCT manufacturer, ' | ') WITHIN GROUP (ORDER BY manufacturer) as manufacturers
    FROM shunt_devices
    GROUP BY patient_fhir_id
)

-- Main SELECT: Combine procedure, notes, and device data
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
    sp.cpt_code_hint as proc_cpt_hint,

    -- Shunt classification
    sp.shunt_type as proc_shunt_type,
    sp.procedure_category as proc_category,

    -- Procedure notes (pn_ prefix)
    pn.notes_aggregated as pn_notes,
    pn.mentions_programmable_valve as pn_mentions_programmable,

    -- Device information (dev_ prefix)
    pd.total_shunt_devices as dev_total_devices,
    pd.has_programmable_shunt as dev_has_programmable,
    pd.device_names as dev_device_names,
    pd.manufacturers as dev_manufacturers,

    -- CBTN field mappings
    sp.shunt_type as shunt_required,  -- VPS, ETV, EVD, Other
    sp.procedure_category as hydro_surgical_management,  -- Placement, Revision, etc.

    -- Programmable valve determination (from notes OR device)
    COALESCE(pd.has_programmable_shunt, pn.mentions_programmable_valve, false) as hydro_shunt_programmable,

    -- Intervention type
    CASE
        WHEN sp.procedure_category IN ('VPS Placement', 'VPS Revision', 'ETV', 'Temporary EVD') THEN 'Surgical'
        WHEN sp.procedure_category = 'Reprogramming' THEN 'Medical'
        ELSE 'Unknown'
    END as hydro_intervention_type,

    -- Data quality indicators
    CASE WHEN sp.proc_performed_datetime IS NOT NULL OR sp.proc_period_start IS NOT NULL THEN true ELSE false END as has_procedure_date,
    CASE WHEN pn.notes_aggregated IS NOT NULL THEN true ELSE false END as has_procedure_notes,
    CASE WHEN pd.total_shunt_devices > 0 THEN true ELSE false END as has_device_record,
    CASE WHEN sp.proc_status = 'completed' THEN true ELSE false END as is_completed

FROM shunt_procedures sp
LEFT JOIN procedure_notes_agg pn ON sp.procedure_id = pn.procedure_id
LEFT JOIN patient_devices pd ON sp.patient_fhir_id = pd.patient_fhir_id

ORDER BY sp.patient_fhir_id, sp.proc_period_start;


-- ================================================================================
-- END OF CONSOLIDATED HYDROCEPHALUS VIEWS
-- ================================================================================
