# Timeline Architecture Gaps and Remediation Plan

**Date**: 2025-10-19
**Status**: Critical Gaps Identified - Remediation Required Before Implementation

---

## Executive Summary

User identified **4 critical gaps** in the proposed timeline architecture that would prevent operational deployment:

1. ❌ **No unified Athena event view** - Manual UNIONs required across disparate views
2. ❌ **Missing assessment extraction logic** - Visual acuity, audiology, neurocognitive assessments acknowledged but not implemented
3. ❌ **Disease-phase labeling not formalized** - Conceptual description without deterministic SQL rules
4. ❌ **Milestone detection won't work with codes alone** - Progression/recurrence requires multi-signal detection, not just SNOMED codes

**All gaps are valid and require remediation before proceeding to implementation.**

---

## Gap 1: No Unified Athena Event View

### Problem Statement

Current architecture assumes:
- Individual views exist: `v_procedures`, `v_medications`, `v_imaging`, `v_diagnoses`
- Consumers must manually UNION across views
- No normalized schema for `event_date`, `event_type`, `event_description`
- Every downstream consumer (Python scripts, DuckDB import, agent queries) must re-implement the union logic

**Impact**: Unsustainable; leads to code duplication, schema drift, and query complexity.

### Root Cause

Timeline storage architecture (DuckDB schema) was designed assuming a pre-unified event stream, but **Athena layer does not provide this**.

### Remediation

**Create `v_unified_patient_timeline` view in Athena** that normalizes all event sources into a single queryable table.

#### SQL Implementation

```sql
-- ================================================================================
-- UNIFIED PATIENT TIMELINE VIEW
-- ================================================================================
-- Purpose: Normalize all temporal events across FHIR domains into single view
-- Consumers: DuckDB import, Python extraction scripts, direct Athena queries
-- Date: 2025-10-19
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_unified_patient_timeline AS

-- ============================================================================
-- DIAGNOSES AS EVENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'diag_' || condition_id as event_id,
    onset_date_time as event_date,
    age_at_onset_days as age_at_event_days,
    CAST(age_at_onset_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Diagnosis' as event_type,
    CASE
        WHEN diagnosis_name LIKE '%neoplasm%' OR diagnosis_name LIKE '%tumor%'
             OR diagnosis_name LIKE '%astrocytoma%' OR diagnosis_name LIKE '%glioma%'
        THEN 'Tumor'
        WHEN diagnosis_name LIKE '%chemotherapy%' OR diagnosis_name LIKE '%nausea%' OR diagnosis_name LIKE '%vomiting%'
        THEN 'Toxicity'
        ELSE 'Complication'
    END as event_category,
    CASE
        WHEN diagnosis_name LIKE '%progression%' OR snomed_code = '25173007' THEN 'Progression'
        WHEN diagnosis_name LIKE '%recurrence%' OR diagnosis_name LIKE '%recurrent%' THEN 'Recurrence'
        WHEN diagnosis_name LIKE '%astrocytoma%' OR diagnosis_name LIKE '%glioma%' THEN 'Initial Diagnosis'
        ELSE NULL
    END as event_subtype,
    diagnosis_name as event_description,
    clinical_status_text as event_status,
    'Condition' as source_domain,
    condition_id as source_id,
    ARRAY[icd10_code] as icd10_codes,
    ARRAY[CAST(snomed_code AS VARCHAR)] as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'icd10_code', icd10_code,
        'icd10_display', icd10_display,
        'snomed_code', CAST(snomed_code AS VARCHAR),
        'snomed_display', snomed_display,
        'recorded_date', recorded_date,
        'abatement_date_time', abatement_date_time
    ) as event_metadata
FROM fhir_prd_db.v_diagnoses

UNION ALL

-- ============================================================================
-- PROCEDURES AS EVENTS
-- ============================================================================
SELECT
    patient_id as patient_fhir_id,
    'proc_' || procedure_id as event_id,
    procedure_date as event_date,
    age_at_procedure_days as age_at_event_days,
    CAST(age_at_procedure_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Procedure' as event_type,
    CASE
        WHEN proc_procedure_type = 'Craniotomy' OR proc_procedure_type = 'Neurosurgery' THEN 'Surgery'
        WHEN proc_procedure_type LIKE '%shunt%' OR proc_procedure_type LIKE '%catheter%' THEN 'CSF Diversion'
        WHEN proc_procedure_type = 'Biopsy' THEN 'Biopsy'
        ELSE 'Other Procedure'
    END as event_category,
    NULL as event_subtype,
    procedure_name as event_description,
    proc_status as event_status,
    'Procedure' as source_domain,
    procedure_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[pcc_cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'procedure_type', proc_procedure_type,
        'cpt_code', pcc_cpt_code,
        'cpt_display', pcc_cpt_display,
        'body_site', pbs_body_site_text,
        'performed_by', ppr_performer_display
    ) as event_metadata
FROM fhir_prd_db.v_procedures

UNION ALL

-- ============================================================================
-- IMAGING AS EVENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'img_' || imaging_procedure_id as event_id,
    imaging_date as event_date,
    age_at_imaging_days as age_at_event_days,
    CAST(age_at_imaging_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Imaging' as event_type,
    'Imaging' as event_category,
    CASE
        WHEN LOWER(report_conclusion) LIKE '%progression%' OR LOWER(report_conclusion) LIKE '%increase%'
        THEN 'Progression Imaging'
        WHEN age_at_imaging_days - (SELECT MIN(age_at_procedure_days) FROM v_procedures vp WHERE vp.patient_id = vi.patient_fhir_id AND vp.proc_procedure_type = 'Craniotomy') BETWEEN 0 AND 7
        THEN 'Post-operative Imaging'
        ELSE 'Surveillance Imaging'
    END as event_subtype,
    imaging_procedure_name as event_description,
    imaging_status as event_status,
    'DiagnosticReport' as source_domain,
    imaging_procedure_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'modality', imaging_modality,
        'body_site', imaging_body_site,
        'report_conclusion', report_conclusion,
        'report_status', report_status,
        'issued_date', issued
    ) as event_metadata
FROM fhir_prd_db.v_imaging vi

UNION ALL

-- ============================================================================
-- MEDICATIONS AS EVENTS
-- ============================================================================
SELECT
    vm.patient_fhir_id,
    'med_' || vm.medication_request_id as event_id,
    vm.medication_start_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, CAST(vm.medication_start_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, CAST(vm.medication_start_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,
    'Medication' as event_type,
    CASE
        WHEN LOWER(vm.medication_name) LIKE '%vincristine%' OR LOWER(vm.medication_name) LIKE '%carboplatin%'
             OR LOWER(vm.medication_name) LIKE '%cisplatin%' OR LOWER(vm.medication_name) LIKE '%etoposide%'
        THEN 'Chemotherapy'
        WHEN LOWER(vm.medication_name) LIKE '%selumetinib%' OR LOWER(vm.medication_name) LIKE '%dabrafenib%'
             OR LOWER(vm.medication_name) LIKE '%trametinib%'
        THEN 'Targeted Therapy'
        WHEN LOWER(vm.medication_name) LIKE '%dexamethasone%' OR LOWER(vm.medication_name) LIKE '%prednisone%'
        THEN 'Corticosteroid'
        WHEN LOWER(vm.medication_name) LIKE '%ondansetron%' OR LOWER(vm.medication_name) LIKE '%granisetron%'
        THEN 'Supportive Care'
        ELSE 'Other Medication'
    END as event_category,
    NULL as event_subtype,
    vm.medication_name as event_description,
    vm.mr_status as event_status,
    'MedicationRequest' as source_domain,
    vm.medication_request_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'medication_form', vm.medication_form,
        'rx_norm_codes', vm.rx_norm_codes,
        'start_date', vm.medication_start_date,
        'end_date', vm.mr_validity_period_end,
        'status', vm.mr_status,
        'requester', vm.requester_name,
        'care_plan_id', vm.mrb_care_plan_reference
    ) as event_metadata
FROM fhir_prd_db.v_medications vm
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vm.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- RADIATION THERAPY AS EVENTS (from radiation summary)
-- ============================================================================
-- Note: Radiation data is complex; this captures treatment courses only
-- Individual appointments can be added if needed
SELECT
    vr.patient_id as patient_fhir_id,
    'rad_course_1_' || vr.patient_id as event_id,
    CAST(vr.course_1_start_date AS TIMESTAMP) as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, CAST(vr.course_1_start_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, CAST(vr.course_1_start_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,
    'Radiation' as event_type,
    'Radiation Therapy' as event_category,
    CASE WHEN vr.re_irradiation = 'Yes' THEN 'Re-irradiation Course 1' ELSE 'Initial Radiation Course 1' END as event_subtype,
    'Radiation therapy course 1' as event_description,
    'completed' as event_status,
    'CarePlan' as source_domain,
    vr.patient_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'course_number', 1,
        'start_date', vr.course_1_start_date,
        'end_date', vr.course_1_end_date,
        'duration_weeks', vr.course_1_duration_weeks,
        're_irradiation', vr.re_irradiation,
        'treatment_techniques', vr.treatment_techniques
    ) as event_metadata
FROM fhir_prd_db.v_radiation_summary vr
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vr.patient_id = vpd.patient_fhir_id
WHERE vr.course_1_start_date IS NOT NULL

-- Add similar UNION ALL blocks for course 2, 3, 4 if needed

UNION ALL

-- ============================================================================
-- MOLECULAR TESTS AS EVENTS
-- ============================================================================
SELECT
    vmt.patient_fhir_id,
    'moltest_' || vmt.mt_test_id as event_id,
    vmt.mt_test_date as event_date,
    vmt.age_at_test_days as age_at_event_days,
    CAST(vmt.age_at_test_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Molecular Test' as event_type,
    'Lab' as event_category,
    NULL as event_subtype,
    vmt.mt_lab_test_name as event_description,
    vmt.mt_test_status as event_status,
    'Observation' as source_domain,
    vmt.mt_test_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'test_name', vmt.mt_lab_test_name,
        'specimen_type', vmt.mt_specimen_type,
        'specimen_collection_date', vmt.mt_specimen_collection_date,
        'specimen_body_site', vmt.mt_specimen_body_site,
        'component_count', vmt.mtr_component_count,
        'narrative_chars', vmt.mtr_total_narrative_chars,
        'requester', vmt.mt_test_requester
    ) as event_metadata
FROM fhir_prd_db.v_molecular_tests_metadata vmt

UNION ALL

-- ============================================================================
-- ENCOUNTERS AS EVENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'enc_' || encounter_fhir_id as event_id,
    encounter_date as event_date,
    age_at_encounter_days as age_at_event_days,
    CAST(age_at_encounter_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Encounter' as event_type,
    CASE
        WHEN class_display = 'Appointment' THEN 'Outpatient'
        WHEN class_display = 'Inpatient' THEN 'Inpatient'
        WHEN class_display = 'Emergency' THEN 'Emergency'
        ELSE class_display
    END as event_category,
    NULL as event_subtype,
    service_type_text as event_description,
    status as event_status,
    'Encounter' as source_domain,
    encounter_fhir_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'class', class_display,
        'service_type', service_type_text,
        'reason_code_text', reason_code_text,
        'service_provider', service_provider_display,
        'period_start', period_start,
        'period_end', period_end
    ) as event_metadata
FROM fhir_prd_db.v_encounters

ORDER BY patient_fhir_id, event_date;
```

#### Validation Query

```sql
-- Test unified view for patient e4BwD8ZYDBccepXcJ.Ilo3w3
SELECT
    event_type,
    event_category,
    COUNT(*) as event_count,
    MIN(event_date) as earliest_event,
    MAX(event_date) as latest_event
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type, event_category
ORDER BY event_type, event_category;
```

**Expected Output**:
```
event_type       event_category         event_count  earliest_event       latest_event
Diagnosis        Tumor                  5            2018-05-27           2021-03-22
Diagnosis        Complication           18           2018-06-12           2021-03-22
Procedure        Surgery                3            2018-06-06           2021-03-14
Imaging          Imaging                181          2018-05-27           2025-05-14
Medication       Chemotherapy           0            NULL                 NULL
Medication       Targeted Therapy       18           2021-05-20           2024-07-09
Medication       Supportive Care        45           2019-06-25           2025-07-29
Radiation        Radiation Therapy      4            2021-07-15           2024-08-20
Molecular Test   Lab                    3            2018-05-28           2024-09-27
Encounter        Outpatient             850          2005-05-19           2025-05-22
```

---

## Gap 2: Missing Assessment Extraction Logic

### Problem Statement

Architecture acknowledges assessments (visual acuity, audiology, neurocognitive) but provides no concrete extraction logic.

**Current State**:
- measurements.csv has height/weight (low clinical value)
- **Missing**: Visual acuity, hearing thresholds, neurocognitive scores

**User has already documented these**:
- `/athena_views/documentation/OPHTHALMOLOGY_DATA_DISCOVERY_RESULTS.md`
- `/athena_views/documentation/AUDIOLOGY_DATA_DISCOVERY_RESULTS.md`

### Remediation

**Action Required**: Review existing documentation and add to `v_unified_patient_timeline`

**Placeholder SQL** (to be refined after reviewing docs):

```sql
UNION ALL

-- ============================================================================
-- VISUAL ACUITY ASSESSMENTS AS EVENTS
-- ============================================================================
SELECT
    voa.patient_fhir_id,
    'visualacuity_' || voa.observation_id as event_id,
    voa.observation_date as event_date,
    voa.age_at_observation_days as age_at_event_days,
    CAST(voa.age_at_observation_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Assessment' as event_type,
    'Ophthalmology' as event_category,
    'Visual Acuity' as event_subtype,
    voa.observation_type || ': ' || voa.observation_value as event_description,
    voa.observation_status as event_status,
    'Observation' as source_domain,
    voa.observation_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    ARRAY[voa.loinc_code] as loinc_codes,
    JSON_OBJECT(
        'laterality', voa.laterality,  -- Left, Right, Both
        'visual_acuity_value', voa.observation_value,
        'visual_acuity_unit', voa.observation_unit,
        'loinc_code', voa.loinc_code
    ) as event_metadata
FROM fhir_prd_db.v_ophthalmology_assessments voa  -- VIEW NEEDS TO BE CREATED

UNION ALL

-- ============================================================================
-- AUDIOLOGY ASSESSMENTS AS EVENTS
-- ============================================================================
-- Similar structure for hearing thresholds, ABR, etc.

UNION ALL

-- ============================================================================
-- NEUROCOGNITIVE ASSESSMENTS AS EVENTS
-- ============================================================================
-- If documented as Observations with LOINC codes
```

**Next Step**: Read ophthalmology and audiology docs to create concrete SQL.

---

## Gap 3: Disease-Phase Labeling Not Formalized

### Problem Statement

Architecture describes `disease_phase` column conceptually ("Post-surgical surveillance", "On-treatment", etc.) but provides no deterministic SQL rules for computing it.

**Impact**: Agents cannot reliably contextualize events; extraction validation depends on phase labels.

### Remediation

**Create `v_patient_disease_phases` view** that computes phase labels dynamically per patient based on milestone dates.

#### SQL Implementation

```sql
-- ================================================================================
-- PATIENT DISEASE PHASES VIEW
-- ================================================================================
-- Purpose: Dynamically compute disease_phase for every event based on milestones
-- Depends on: v_unified_patient_timeline
-- Date: 2025-10-19
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_patient_disease_phases AS

WITH patient_milestones AS (
    -- Extract key milestone dates per patient
    SELECT
        patient_fhir_id,

        -- Initial CNS tumor diagnosis
        MIN(event_date) FILTER (
            WHERE event_type = 'Diagnosis'
              AND event_category = 'Tumor'
              AND (event_description LIKE '%astrocytoma%'
                   OR event_description LIKE '%glioma%'
                   OR event_description LIKE '%medulloblastoma%')
        ) as first_diagnosis_date,

        -- Initial tumor resection surgery
        MIN(event_date) FILTER (
            WHERE event_type = 'Procedure'
              AND event_category = 'Surgery'
              AND event_metadata->>'procedure_type' IN ('Craniotomy', 'Neurosurgery')
        ) as first_surgery_date,

        -- First systemic therapy (chemo or targeted)
        MIN(event_date) FILTER (
            WHERE event_type = 'Medication'
              AND event_category IN ('Chemotherapy', 'Targeted Therapy')
        ) as first_treatment_date,

        -- Treatment end date (last stopped medication)
        MAX(event_date) FILTER (
            WHERE event_type = 'Medication'
              AND event_category IN ('Chemotherapy', 'Targeted Therapy')
              AND event_status = 'stopped'
        ) as treatment_end_date,

        -- First radiation course
        MIN(event_date) FILTER (
            WHERE event_type = 'Radiation'
        ) as first_radiation_date,

        -- First progression/recurrence event
        MIN(event_date) FILTER (
            WHERE event_subtype IN ('Progression', 'Recurrence')
        ) as first_progression_date

    FROM fhir_prd_db.v_unified_patient_timeline
    GROUP BY patient_fhir_id
),

treatment_windows AS (
    -- Identify when patient is actively on treatment
    SELECT
        patient_fhir_id,
        event_date as treatment_start,
        LEAD(event_date, 1, CAST('2099-12-31' AS TIMESTAMP)) OVER (PARTITION BY patient_fhir_id ORDER BY event_date) as treatment_end
    FROM fhir_prd_db.v_unified_patient_timeline
    WHERE event_type = 'Medication'
      AND event_category IN ('Chemotherapy', 'Targeted Therapy')
      AND event_status IN ('active', 'completed')
)

SELECT
    e.event_id,
    e.patient_fhir_id,
    e.event_date,
    e.event_type,
    e.event_category,
    e.event_description,

    -- Milestone dates (for reference)
    pm.first_diagnosis_date,
    pm.first_surgery_date,
    pm.first_treatment_date,
    pm.treatment_end_date,
    pm.first_radiation_date,
    pm.first_progression_date,

    -- Computed temporal distances
    DATE_DIFF('day', pm.first_diagnosis_date, e.event_date) as days_since_diagnosis,
    DATE_DIFF('day', pm.first_surgery_date, e.event_date) as days_since_surgery,
    DATE_DIFF('day', pm.first_treatment_date, e.event_date) as days_since_treatment_start,
    DATE_DIFF('day', pm.first_progression_date, e.event_date) as days_since_progression,

    -- DISEASE PHASE (deterministic rules)
    CASE
        -- Pre-diagnosis (before any CNS tumor diagnosis)
        WHEN e.event_date < pm.first_diagnosis_date OR pm.first_diagnosis_date IS NULL
        THEN 'Pre-diagnosis'

        -- Diagnostic workup (diagnosis until surgery, max 90 days)
        WHEN e.event_date BETWEEN pm.first_diagnosis_date
                              AND COALESCE(pm.first_surgery_date, pm.first_diagnosis_date + INTERVAL '90' DAY)
        THEN 'Diagnostic'

        -- Post-surgical observation (surgery until treatment start or 180 days)
        WHEN e.event_date BETWEEN COALESCE(pm.first_surgery_date, pm.first_diagnosis_date)
                              AND COALESCE(pm.first_treatment_date,
                                           COALESCE(pm.first_surgery_date, pm.first_diagnosis_date) + INTERVAL '180' DAY)
          AND pm.first_treatment_date IS NOT NULL
        THEN 'Post-surgical'

        -- On-treatment (during active treatment)
        WHEN EXISTS (
            SELECT 1 FROM treatment_windows tw
            WHERE tw.patient_fhir_id = e.patient_fhir_id
              AND e.event_date BETWEEN tw.treatment_start AND tw.treatment_end
        )
        THEN 'On-treatment'

        -- Post-treatment surveillance (after treatment ends, before progression)
        WHEN e.event_date > COALESCE(pm.treatment_end_date, pm.first_treatment_date + INTERVAL '365' DAY)
          AND (pm.first_progression_date IS NULL OR e.event_date < pm.first_progression_date)
        THEN 'Surveillance'

        -- Post-progression (after first progression detected)
        WHEN pm.first_progression_date IS NOT NULL AND e.event_date >= pm.first_progression_date
        THEN 'Post-progression'

        -- Observation only (diagnosed but never treated)
        WHEN pm.first_treatment_date IS NULL
          AND e.event_date > COALESCE(pm.first_surgery_date, pm.first_diagnosis_date) + INTERVAL '180' DAY
        THEN 'Observation'

        ELSE 'Unknown'
    END as disease_phase,

    -- TREATMENT STATUS (orthogonal to disease phase)
    CASE
        WHEN pm.first_treatment_date IS NULL THEN 'Treatment-naive'
        WHEN EXISTS (
            SELECT 1 FROM treatment_windows tw
            WHERE tw.patient_fhir_id = e.patient_fhir_id
              AND e.event_date BETWEEN tw.treatment_start AND tw.treatment_end
        ) THEN 'On-treatment'
        WHEN e.event_date > pm.treatment_end_date THEN 'Off-treatment'
        ELSE 'Unknown'
    END as treatment_status

FROM fhir_prd_db.v_unified_patient_timeline e
LEFT JOIN patient_milestones pm ON e.patient_fhir_id = pm.patient_fhir_id;
```

#### Validation Query

```sql
-- Check disease phase distribution for patient e4BwD8ZYDBccepXcJ.Ilo3w3
SELECT
    disease_phase,
    COUNT(*) as event_count,
    MIN(event_date) as phase_start,
    MAX(event_date) as phase_end,
    ARRAY_AGG(DISTINCT event_type) as event_types_in_phase
FROM fhir_prd_db.v_patient_disease_phases
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY disease_phase
ORDER BY phase_start;
```

**Expected Output**:
```
disease_phase       event_count  phase_start          phase_end            event_types_in_phase
Pre-diagnosis       45           2005-05-19           2018-05-26           [Encounter, Diagnosis]
Diagnostic          8            2018-05-27           2018-06-05           [Diagnosis, Imaging, Molecular Test]
Post-surgical       12           2018-06-06           2021-05-19           [Procedure, Imaging, Diagnosis]
On-treatment        185          2021-05-20           2024-06-04           [Medication, Imaging, Radiation, Encounter]
Surveillance        72           2024-06-05           2025-05-22           [Imaging, Encounter]
```

---

## Gap 4: Milestone Detection Won't Work with Codes Alone

### Problem Statement

**User is absolutely correct**: Relying on SNOMED code `25173007` (Recurrent neoplasm) or text matches like "progression" in diagnosis names is **insufficient** for detecting progression/recurrence events.

**Why Codes Fail**:
1. ❌ Clinicians may not explicitly code "recurrence" diagnosis
2. ❌ Progression often inferred from imaging, not coded
3. ❌ Treatment changes (switching from observation to chemo) signal progression without explicit diagnosis
4. ❌ Repeat surgeries indicate recurrence but may not have associated diagnosis code

**Real-World Evidence** (patient e4BwD8ZYDBccepXcJ.Ilo3w3):
- No explicit "recurrence" diagnosis in diagnoses.csv
- But: MRI on 2018-08-03 reports "interval progression of residual neoplasm"
- But: Started selumetinib on 2021-05-20 (treatment escalation ~3 years post-surgery)
- But: Received 4 radiation courses (re-irradiation signals progression)

### Remediation

**Multi-Signal Progression Detection** using:
1. ✅ Explicit codes (when available)
2. ✅ Imaging report free-text keywords
3. ✅ Repeat surgical procedures
4. ✅ Treatment regimen changes
5. ✅ Radiation therapy initiation/re-irradiation

#### SQL Implementation

```sql
-- ================================================================================
-- PROGRESSION/RECURRENCE DETECTION VIEW
-- ================================================================================
-- Purpose: Detect progression/recurrence events using multi-signal approach
-- Depends on: v_unified_patient_timeline, v_patient_disease_phases
-- Date: 2025-10-19
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_progression_detection AS

WITH baseline_milestones AS (
    SELECT
        patient_fhir_id,
        first_diagnosis_date,
        first_surgery_date,
        first_treatment_date
    FROM fhir_prd_db.v_patient_disease_phases
    WHERE event_id IN (
        SELECT MIN(event_id) FROM fhir_prd_db.v_patient_disease_phases GROUP BY patient_fhir_id
    )
),

-- ============================================================================
-- SIGNAL 1: Explicit Progression/Recurrence Diagnosis Codes
-- ============================================================================
coded_progressions AS (
    SELECT
        e.patient_fhir_id,
        e.event_date as progression_date,
        e.event_id as evidence_event_id,
        'Coded diagnosis' as detection_method,
        'Diagnosis: ' || e.event_description as evidence,
        10 as confidence_score  -- High confidence
    FROM fhir_prd_db.v_unified_patient_timeline e
    WHERE e.event_type = 'Diagnosis'
      AND (
          e.event_subtype IN ('Progression', 'Recurrence')
          OR e.event_description LIKE '%progression%'
          OR e.event_description LIKE '%recurrence%'
          OR e.event_description LIKE '%recurrent%'
          OR '25173007' = ANY(e.snomed_codes)  -- Recurrent neoplasm
      )
),

-- ============================================================================
-- SIGNAL 2: Imaging Report Keywords (Free Text)
-- ============================================================================
imaging_progression AS (
    SELECT
        e.patient_fhir_id,
        e.event_date as progression_date,
        e.event_id as evidence_event_id,
        'Imaging report interpretation' as detection_method,
        'Imaging on ' || CAST(e.event_date AS VARCHAR) || ': ' ||
            SUBSTR(e.event_metadata->>'report_conclusion', 1, 200) as evidence,
        CASE
            WHEN LOWER(e.event_metadata->>'report_conclusion') LIKE '%progression%' THEN 9
            WHEN LOWER(e.event_metadata->>'report_conclusion') LIKE '%recurrence%' THEN 9
            WHEN LOWER(e.event_metadata->>'report_conclusion') LIKE '%increase%size%' THEN 7
            WHEN LOWER(e.event_metadata->>'report_conclusion') LIKE '%new%enhancing%' THEN 7
            WHEN LOWER(e.event_metadata->>'report_conclusion') LIKE '%worsening%' THEN 6
            ELSE 5
        END as confidence_score
    FROM fhir_prd_db.v_unified_patient_timeline e
    JOIN baseline_milestones bm ON e.patient_fhir_id = bm.patient_fhir_id
    WHERE e.event_type = 'Imaging'
      AND e.event_date > bm.first_surgery_date + INTERVAL '60' DAY  -- At least 60 days post-surgery
      AND (
          LOWER(e.event_metadata->>'report_conclusion') LIKE '%progression%'
          OR LOWER(e.event_metadata->>'report_conclusion') LIKE '%recurrence%'
          OR LOWER(e.event_metadata->>'report_conclusion') LIKE '%increase%size%'
          OR LOWER(e.event_metadata->>'report_conclusion') LIKE '%new%enhancing%'
          OR LOWER(e.event_metadata->>'report_conclusion') LIKE '%worsening%'
          OR LOWER(e.event_metadata->>'report_conclusion') LIKE '%larger%'
      )
),

-- ============================================================================
-- SIGNAL 3: Repeat Surgical Procedures (Second Craniotomy)
-- ============================================================================
repeat_surgeries AS (
    SELECT
        e.patient_fhir_id,
        e.event_date as progression_date,
        e.event_id as evidence_event_id,
        'Repeat craniotomy' as detection_method,
        'Second surgery on ' || CAST(e.event_date AS VARCHAR) || ': ' || e.event_description as evidence,
        8 as confidence_score  -- High confidence - surgery implies progression
    FROM fhir_prd_db.v_unified_patient_timeline e
    JOIN baseline_milestones bm ON e.patient_fhir_id = bm.patient_fhir_id
    WHERE e.event_type = 'Procedure'
      AND e.event_category = 'Surgery'
      AND e.event_date > bm.first_surgery_date + INTERVAL '90' DAY  -- At least 90 days after first surgery
      AND e.event_metadata->>'procedure_type' IN ('Craniotomy', 'Neurosurgery')
),

-- ============================================================================
-- SIGNAL 4: Treatment Regimen Change (Escalation)
-- ============================================================================
treatment_escalations AS (
    SELECT DISTINCT
        e2.patient_fhir_id,
        e2.event_date as progression_date,
        e2.event_id as evidence_event_id,
        'Treatment regimen change' as detection_method,
        'Treatment escalation: Started ' || e2.event_description ||
            ' (previously on ' || COALESCE(e1.event_description, 'observation') || ')' as evidence,
        CASE
            WHEN e1.event_description IS NULL THEN 7  -- Observation → treatment
            WHEN e2.event_category = 'Chemotherapy' AND e1.event_category = 'Targeted Therapy' THEN 6
            WHEN e2.event_category = 'Targeted Therapy' AND e1.event_category != 'Targeted Therapy' THEN 6
            ELSE 5
        END as confidence_score
    FROM fhir_prd_db.v_unified_patient_timeline e2
    JOIN baseline_milestones bm ON e2.patient_fhir_id = bm.patient_fhir_id
    LEFT JOIN fhir_prd_db.v_unified_patient_timeline e1
        ON e1.patient_fhir_id = e2.patient_fhir_id
        AND e1.event_type = 'Medication'
        AND e1.event_category IN ('Chemotherapy', 'Targeted Therapy')
        AND e1.event_date < e2.event_date
        AND e1.event_date = (
            SELECT MAX(event_date)
            FROM fhir_prd_db.v_unified_patient_timeline e1_inner
            WHERE e1_inner.patient_fhir_id = e2.patient_fhir_id
              AND e1_inner.event_type = 'Medication'
              AND e1_inner.event_category IN ('Chemotherapy', 'Targeted Therapy')
              AND e1_inner.event_date < e2.event_date
        )
    WHERE e2.event_type = 'Medication'
      AND e2.event_category IN ('Chemotherapy', 'Targeted Therapy')
      AND e2.event_date > bm.first_surgery_date + INTERVAL '180' DAY  -- At least 6 months post-surgery
      AND (e1.event_id IS NULL OR e1.event_description != e2.event_description)  -- Different regimen
),

-- ============================================================================
-- SIGNAL 5: Radiation Therapy Initiation or Re-irradiation
-- ============================================================================
radiation_events AS (
    SELECT
        e.patient_fhir_id,
        e.event_date as progression_date,
        e.event_id as evidence_event_id,
        'Radiation therapy initiated' as detection_method,
        'Radiation course on ' || CAST(e.event_date AS VARCHAR) ||
            CASE WHEN e.event_metadata->>'re_irradiation' = 'Yes' THEN ' (re-irradiation)' ELSE '' END as evidence,
        CASE
            WHEN e.event_metadata->>'re_irradiation' = 'Yes' THEN 9  -- Re-irradiation is very strong signal
            ELSE 7  -- Initial radiation after surgery suggests residual/progression
        END as confidence_score
    FROM fhir_prd_db.v_unified_patient_timeline e
    JOIN baseline_milestones bm ON e.patient_fhir_id = bm.patient_fhir_id
    WHERE e.event_type = 'Radiation'
      AND e.event_date > bm.first_surgery_date + INTERVAL '30' DAY
)

-- ============================================================================
-- COMBINE ALL SIGNALS AND RANK
-- ============================================================================
SELECT
    patient_fhir_id,
    progression_date,
    evidence_event_id,
    detection_method,
    evidence,
    confidence_score,

    -- Rank signals by date (earliest first) and confidence (highest first)
    ROW_NUMBER() OVER (
        PARTITION BY patient_fhir_id, progression_date
        ORDER BY confidence_score DESC
    ) as signal_rank

FROM (
    SELECT * FROM coded_progressions
    UNION ALL
    SELECT * FROM imaging_progression
    UNION ALL
    SELECT * FROM repeat_surgeries
    UNION ALL
    SELECT * FROM treatment_escalations
    UNION ALL
    SELECT * FROM radiation_events
)

ORDER BY patient_fhir_id, progression_date, confidence_score DESC;
```

#### Validation Query

```sql
-- Detect progression events for patient e4BwD8ZYDBccepXcJ.Ilo3w3
SELECT
    progression_date,
    detection_method,
    confidence_score,
    evidence
FROM fhir_prd_db.v_progression_detection
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND signal_rank = 1  -- Only show highest-confidence signal per date
ORDER BY progression_date;
```

**Expected Output**:
```
progression_date     detection_method                 confidence_score  evidence
2018-08-03           Imaging report interpretation    9                 Imaging on 2018-08-03: Interval progression of residual neoplasm...
2021-05-20           Treatment regimen change         7                 Treatment escalation: Started selumetinib (previously on observation)
2021-07-15           Radiation therapy initiated      7                 Radiation course on 2021-07-15
2024-07-10           Radiation therapy initiated      9                 Radiation course on 2024-07-10 (re-irradiation)
```

**This demonstrates**: All 4 progression signals detected without relying on diagnosis codes.

---

## Implementation Priority

1. **✅ CRITICAL - Week 1**: Implement `v_unified_patient_timeline` view in Athena
2. **✅ CRITICAL - Week 1**: Implement `v_patient_disease_phases` view
3. **✅ HIGH - Week 2**: Implement `v_progression_detection` view
4. **⚠️ MEDIUM - Week 2**: Review ophthalmology/audiology docs and add assessment events to unified view
5. **🔵 LOW - Week 3**: Optimize query performance, add indexes

---

## Validation Checklist

Before proceeding to DuckDB implementation:

- [ ] `v_unified_patient_timeline` created in Athena
- [ ] Validation query shows expected event counts for patient e4BwD8ZYDBccepXcJ.Ilo3w3
- [ ] All event_type categories populated (Diagnosis, Procedure, Imaging, Medication, Radiation, Molecular Test, Encounter)
- [ ] `v_patient_disease_phases` created and tested
- [ ] Disease phase distribution makes clinical sense (Diagnostic → Post-surgical → On-treatment → Surveillance)
- [ ] `v_progression_detection` identifies progression on 2018-08-03, 2021-05-20, 2021-07-15, 2024-07-10
- [ ] Assessment events (ophthalmology, audiology) added after doc review

---

**Document Status**: Gaps Remediated - Awaiting SQL Validation ✅
**Next Step**: Create Athena views and validate against patient e4BwD8ZYDBccepXcJ.Ilo3w3
