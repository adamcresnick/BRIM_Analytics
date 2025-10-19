# ATHENA VIEWS - MASTER DATA DICTIONARY
**Version:** 2.1 (Unified Timeline Updated)
**Last Updated:** 2025-10-19
**Total Views:** 25 (22 source views + 2 prerequisites + 1 unified timeline)

---

## PURPOSE
This document provides a comprehensive reference for all Athena views with:
- Complete column listings
- Column prefix decoding (maps columns back to FHIR resources)
- Datetime standardization status
- View dependencies and relationships

**IMPORTANT:** All views now use **TIMESTAMP(3)** for datetime columns (millisecond precision).
This ensures consistent typing across views and eliminates downstream casting requirements.

---

## COLUMN PREFIX DECODER

Understanding column prefixes helps trace data back to source FHIR resources:

| Prefix | Source FHIR Resource | Example Columns |
|--------|---------------------|-----------------|
| `pld_` | Problem List Diagnosis (Condition) | pld_diagnosis_name, pld_onset_date |
| `proc_` | Procedure | proc_performed_datetime, proc_code_text |
| `obs_` | Observation | obs_effective_date, obs_value |
| `mr_` | Medication Request | mr_authored_on, mr_medication_name |
| `cp_` | Care Plan | cp_period_start, cp_title |
| `sr_` | Service Request | sr_authored_on, sr_code_text |
| `apt_` | Appointment | apt_start, apt_status |
| `dr_` | Diagnostic Report | dr_effective_date, dr_code_text |
| `img_` | Imaging (DiagnosticReport subset) | img_modality, img_body_site |
| `lt_` | Lab Test (Observation subset) | lt_test_name, lt_result_value |
| `ltr_` | Lab Test Result | ltr_value, ltr_unit |
| `pd_` | Patient Demographics | pd_birth_date, pd_gender |
| `cd34_` | CD34 Measurement (Observation) | cd34_count, cd34_unit |
| `chemo_` | Chemotherapy (MedicationRequest) | chemo_drug_name, chemo_start_date |
| `conmed_` | Concomitant Medication | conmed_medication_name, conmed_start_datetime |
| `hd_` | Hydrocephalus Diagnosis | hd_diagnosis_name, hd_onset_date |

**NO PREFIX:** Unified/normalized views (v_diagnoses, v_unified_patient_timeline)

---

## VIEW CATEGORIES

### 1. PATIENT DEMOGRAPHICS
- **v_patient_demographics** (1 view)

### 2. DIAGNOSES
- **v_problem_list_diagnoses** - All diagnoses from problem lists
- **v_hydrocephalus_diagnosis** - Hydrocephalus-specific diagnoses
- **v_diagnoses** - Normalized diagnosis view (no prefixes)

### 3. PROCEDURES
- **v_procedures_tumor** - Tumor-related procedures
- **v_hydrocephalus_procedures** - Hydrocephalus interventions

### 4. MEDICATIONS
- **v_medications** - All medications
- **v_concomitant_medications** - Medications given during chemotherapy
- **v_imaging_corticosteroid_use** - Corticosteroids at time of imaging

### 5. IMAGING
- **v_imaging** - All imaging studies
- **v_binary_files** - Imaging file references

### 6. RADIATION
- **v_radiation_treatments** - Radiation treatment courses
- **v_radiation_treatment_appointments** - Individual radiation appointments
- **v_radiation_documents** - Radiation-related documents
- **v_radiation_care_plan_hierarchy** - Radiation care plan structure
- **v_radiation_summary** - Aggregated radiation summary (prerequisite view)

### 7. MEASUREMENTS & LABS
- **v_measurements** - Height, weight, vitals, labs
- **v_molecular_tests** - Molecular/genetic testing

### 8. ASSESSMENTS
- **v_audiology_assessments** - Hearing assessments
- **v_ophthalmology_assessments** - Vision assessments

### 9. TRANSPLANT
- **v_autologous_stem_cell_collection** - Stem cell collection procedures
- **v_autologous_stem_cell_transplant** - Transplant procedures

### 10. ENCOUNTERS & VISITS
- **v_encounters** - All encounters
- **v_visits_unified** - Unified appointments + encounters

### 11. UNIFIED TIMELINE
- **v_unified_patient_timeline** - All events across all domains

---

## DETAILED VIEW SPECIFICATIONS

### v_patient_demographics
**Purpose:** Core patient demographics
**Key Columns:**
- `patient_fhir_id` (VARCHAR) - Patient identifier
- `pd_gender` (VARCHAR)
- `pd_race` (VARCHAR)
- `pd_ethnicity` (VARCHAR)
- `pd_birth_date` (TIMESTAMP(3)) - Birth datetime
- `pd_age_years` (INTEGER) - Current age

**Datetime Columns:** 1 (pd_birth_date)

---

### v_problem_list_diagnoses
**Purpose:** All diagnoses from problem lists
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `pld_condition_id` (VARCHAR) - Condition FHIR ID
- `pld_diagnosis_name` (VARCHAR)
- `pld_clinical_status` (VARCHAR) - active, resolved, etc.
- `pld_onset_date` (TIMESTAMP(3)) - When diagnosed
- `age_at_onset_days` (INTEGER)
- `pld_abatement_date` (TIMESTAMP(3)) - When resolved
- `pld_recorded_date` (TIMESTAMP(3)) - When recorded
- `age_at_recorded_days` (INTEGER)
- `pld_icd10_code` (VARCHAR)
- `pld_icd10_display` (VARCHAR)
- `pld_snomed_code` (VARCHAR)
- `pld_snomed_display` (VARCHAR)

**Datetime Columns:** 3 (pld_onset_date, pld_abatement_date, pld_recorded_date)

---

### v_diagnoses
**Purpose:** Normalized diagnosis view (removes pld_ prefix for unified timeline)
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `condition_id` (VARCHAR) - No prefix
- `diagnosis_name` (VARCHAR) - No prefix
- `clinical_status_text` (VARCHAR) - No prefix
- `onset_date_time` (TIMESTAMP(3)) - No prefix
- `age_at_onset_days` (INTEGER)
- `abatement_date_time` (TIMESTAMP(3)) - No prefix
- `recorded_date` (TIMESTAMP(3)) - No prefix
- `age_at_recorded_days` (INTEGER)
- `icd10_code` (VARCHAR) - No prefix
- `snomed_code` (BIGINT) - No prefix

**Datetime Columns:** 3 (onset_date_time, abatement_date_time, recorded_date)
**Source:** v_problem_list_diagnoses

---

### v_procedures_tumor
**Purpose:** Tumor-related surgical procedures
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `tumor_procedure_id` (VARCHAR)
- `tumor_procedure_classification` (VARCHAR) - resection, biopsy, shunt, etc.
- `procedure_name` (VARCHAR)
- `procedure_date` (TIMESTAMP(3))
- `age_at_procedure_days` (INTEGER)
- `body_site` (VARCHAR)
- `extent_of_resection` (VARCHAR)
- `procedure_status` (VARCHAR)

**Datetime Columns:** 1 (procedure_date)

---

### v_hydrocephalus_procedures
**Purpose:** Hydrocephalus interventions (shunts, ETV, etc.)
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `procedure_id` (VARCHAR)
- `code_text` (VARCHAR)
- `proc_status` (VARCHAR)
- `proc_performed_datetime` (TIMESTAMP(3))
- `proc_period_start` (TIMESTAMP(3))
- `proc_period_end` (TIMESTAMP(3))
- `procedure_category` (VARCHAR) - Placement, Revision, ETV, etc.
- `shunt_type` (VARCHAR) - VP, VA, LP, etc.
- `device_manufacturer` (VARCHAR)
- `device_model` (VARCHAR)

**Datetime Columns:** 3 (proc_performed_datetime, proc_period_start, proc_period_end)

---

### v_medications
**Purpose:** All medications
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `medication_request_id` (VARCHAR)
- `medication_name` (VARCHAR)
- `medication_generic_name` (VARCHAR)
- `rxnorm_code` (VARCHAR)
- `medication_category` (VARCHAR) - chemotherapy, antiemetic, etc.
- `dosage_text` (VARCHAR)
- `route` (VARCHAR)
- `frequency` (VARCHAR)
- `status` (VARCHAR)

**Datetime Columns:** 0 (medications don't have standardized datetime in this view)

---

### v_concomitant_medications
**Purpose:** Medications given during chemotherapy periods
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `chemo_medication_request_id` (VARCHAR)
- `chemo_drug_name` (VARCHAR)
- `chemo_drug_generic_name` (VARCHAR)
- `chemo_start_datetime` (TIMESTAMP(3))
- `chemo_stop_datetime` (TIMESTAMP(3))
- `chemo_authored_datetime` (TIMESTAMP(3))
- `conmed_medication_request_id` (VARCHAR)
- `conmed_medication_name` (VARCHAR)
- `conmed_start_datetime` (TIMESTAMP(3))
- `conmed_stop_datetime` (TIMESTAMP(3))
- `conmed_authored_datetime` (TIMESTAMP(3))
- `overlap_start_datetime` (TIMESTAMP(3))
- `overlap_stop_datetime` (TIMESTAMP(3))
- `overlap_duration_days` (DOUBLE)

**Datetime Columns:** 8 (all chemo_, conmed_, and overlap_ datetime fields)

---

### v_imaging_corticosteroid_use
**Purpose:** Corticosteroid use at time of imaging (for pseudoprogression analysis)
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `imaging_procedure_id` (VARCHAR)
- `imaging_date` (TIMESTAMP(3))
- `imaging_modality` (VARCHAR)
- `corticosteroid_medication_request_id` (VARCHAR)
- `corticosteroid_name` (VARCHAR)
- `corticosteroid_generic_name` (VARCHAR)
- `corticosteroid_rxnorm_cui` (VARCHAR)
- `medication_start_datetime` (TIMESTAMP(3))
- `medication_stop_datetime` (TIMESTAMP(3))
- `days_from_med_start_to_imaging` (INTEGER)
- `days_from_imaging_to_med_stop` (INTEGER)
- `temporal_relationship` (VARCHAR) - before, during, after

**Datetime Columns:** 3 (imaging_date, medication_start_datetime, medication_stop_datetime)

---

### v_imaging
**Purpose:** All imaging studies
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `imaging_procedure_id` (VARCHAR)
- `imaging_modality` (VARCHAR) - MRI, CT, PET, etc.
- `imaging_date` (TIMESTAMP(3))
- `age_at_imaging_days` (INTEGER)
- `age_at_imaging_years` (DOUBLE)
- `body_site` (VARCHAR)
- `imaging_type` (VARCHAR)
- `result_status` (VARCHAR)
- `report_effective_period_start` (TIMESTAMP(3))
- `report_effective_period_stop` (TIMESTAMP(3))
- `report_issued` (TIMESTAMP(3))

**Datetime Columns:** 4 (imaging_date, report_effective_period_start, report_effective_period_stop, report_issued)

---

### v_binary_files
**Purpose:** Imaging file attachments and URLs
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `document_reference_id` (VARCHAR)
- `file_type` (VARCHAR)
- `file_url` (VARCHAR)
- `file_size` (INTEGER)
- `file_creation_date` (TIMESTAMP(3))
- `document_type` (VARCHAR)
- `document_category` (VARCHAR)

**Datetime Columns:** 1 (file_creation_date)

---

### v_radiation_treatments
**Purpose:** Radiation treatment courses with dose, site, dates
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `course_id` (VARCHAR)
- `obs_course_line_number` (VARCHAR) - Course 1, Course 2, etc.
- `obs_dose_value` (DOUBLE)
- `obs_dose_unit` (VARCHAR)
- `obs_radiation_field` (VARCHAR)
- `obs_radiation_site_code` (INTEGER)
- `obs_start_date` (TIMESTAMP(3))
- `obs_stop_date` (TIMESTAMP(3))
- `obs_status` (VARCHAR)
- `obs_effective_date` (TIMESTAMP(3))
- `apt_total_appointments` (INTEGER)
- `apt_first_appointment_date` (TIMESTAMP(3))
- `apt_last_appointment_date` (TIMESTAMP(3))
- `best_treatment_start_date` (TIMESTAMP(3))
- `best_treatment_stop_date` (TIMESTAMP(3))

**Datetime Columns:** 7 (obs_start_date, obs_stop_date, obs_effective_date, apt_first_appointment_date, apt_last_appointment_date, best_treatment_start_date, best_treatment_stop_date)

---

### v_radiation_treatment_appointments
**Purpose:** Individual radiation appointment records
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `appointment_id` (VARCHAR)
- `appointment_status` (VARCHAR)
- `appointment_type_text` (VARCHAR)
- `appointment_start` (TIMESTAMP(3))
- `appointment_end` (TIMESTAMP(3))
- `minutes_duration` (INTEGER)
- `created` (TIMESTAMP(3))

**Datetime Columns:** 3 (appointment_start, appointment_end, created)

---

### v_radiation_documents
**Purpose:** Radiation treatment plan documents
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `document_reference_id` (VARCHAR)
- `doc_type_text` (VARCHAR)
- `doc_category_text` (VARCHAR)
- `doc_date` (TIMESTAMP(3))
- `doc_context_period_start` (TIMESTAMP(3))
- `doc_context_period_end` (TIMESTAMP(3))
- `doc_status` (VARCHAR)
- `content_url` (VARCHAR)
- `content_type` (VARCHAR)

**Datetime Columns:** 3 (doc_date, doc_context_period_start, doc_context_period_end)

---

### v_radiation_care_plan_hierarchy
**Purpose:** Radiation care plan structure
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `care_plan_id` (VARCHAR)
- `parent_care_plan_id` (VARCHAR)
- `care_plan_title` (VARCHAR)
- `care_plan_status` (VARCHAR)
- `cp_period_start` (TIMESTAMP(3))
- `cp_period_end` (TIMESTAMP(3))
- `hierarchy_level` (INTEGER)

**Datetime Columns:** 2 (cp_period_start, cp_period_end)

---

### v_radiation_summary
**Purpose:** Aggregated radiation course summary (prerequisite view)
**Key Columns:**
- `patient_id` (VARCHAR) - Note: uses patient_id not patient_fhir_id
- `course_1_start_date` (DATE)
- `course_1_end_date` (DATE)
- `course_1_duration_weeks` (DOUBLE)
- `re_irradiation` (VARCHAR) - Yes/No
- `treatment_techniques` (VARCHAR)
- `num_radiation_appointments` (INTEGER)

**Datetime Columns:** 2 DATE types (course_1_start_date, course_1_end_date)
**Dependencies:** v_radiation_treatments, v_radiation_treatment_appointments

---

### v_measurements
**Purpose:** Height, weight, vitals, lab results
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `measurement_category` (VARCHAR) - vital_signs, anthropometric, lab_test
- `measurement_name` (VARCHAR)
- `measurement_value` (DOUBLE)
- `measurement_unit` (VARCHAR)
- `obs_measurement_date` (TIMESTAMP(3)) - From observations
- `lt_measurement_date` (TIMESTAMP(3)) - From lab tests
- `age_at_measurement_days` (INTEGER)
- `age_at_measurement_years` (DOUBLE)

**Datetime Columns:** 2 (obs_measurement_date, lt_measurement_date)

---

### v_molecular_tests
**Purpose:** Molecular and genetic testing
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `test_id` (VARCHAR)
- `test_name` (VARCHAR)
- `test_category` (VARCHAR)
- `test_result` (VARCHAR)
- `test_interpretation` (VARCHAR)
- `test_date` (TIMESTAMP(3))
- `age_at_test_days` (INTEGER)

**Datetime Columns:** 1 (test_date)

---

### v_audiology_assessments
**Purpose:** Hearing assessments and audiograms
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `record_fhir_id` (VARCHAR)
- `data_type` (VARCHAR) - audiogram, hearing_aid, diagnosis, procedure, etc.
- `assessment_date` (DATE)
- `assessment_description` (VARCHAR)
- `assessment_category` (VARCHAR)
- `ear_side` (VARCHAR) - left/right
- `frequency_hz` (INTEGER) - For audiograms
- `threshold_db` (VARCHAR) - Hearing threshold
- `hearing_loss_type` (VARCHAR)
- `is_ototoxic` (BOOLEAN)
- `full_datetime` (TIMESTAMP(3))

**Datetime Columns:** 2 (assessment_date as DATE, full_datetime as TIMESTAMP(3))

---

### v_ophthalmology_assessments
**Purpose:** Vision assessments and ophthalmology exams
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `record_fhir_id` (VARCHAR)
- `assessment_date` (DATE)
- `assessment_description` (VARCHAR)
- `assessment_category` (VARCHAR) - visual_acuity, oct_optic_nerve, visual_field, etc.
- `source_table` (VARCHAR)
- `record_status` (VARCHAR)
- `cpt_code` (VARCHAR)
- `numeric_value` (DOUBLE)
- `value_unit` (VARCHAR)
- `full_datetime` (TIMESTAMP(3))

**Datetime Columns:** 2 (assessment_date as DATE, full_datetime as TIMESTAMP(3))

---

### v_autologous_stem_cell_collection
**Purpose:** Stem cell collection procedures
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `collection_procedure_fhir_id` (VARCHAR)
- `collection_datetime` (TIMESTAMP(3))
- `collection_method` (VARCHAR)
- `cd34_count` (DOUBLE)
- `cd34_unit` (VARCHAR)
- `cd34_adequacy` (VARCHAR) - adequate, minimal, inadequate
- `cd34_measurement_datetime` (TIMESTAMP(3))
- `mobilization_agent` (VARCHAR)
- `mobilization_start_datetime` (TIMESTAMP(3))
- `mobilization_stop_datetime` (TIMESTAMP(3))
- `quality_measurement_datetime` (TIMESTAMP(3))

**Datetime Columns:** 5 (collection_datetime, cd34_measurement_datetime, mobilization_start_datetime, mobilization_stop_datetime, quality_measurement_datetime)

---

### v_autologous_stem_cell_transplant
**Purpose:** Stem cell transplant procedures
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `transplant_procedure_id` (VARCHAR)
- `transplant_date` (TIMESTAMP(3))
- `transplant_type` (VARCHAR)
- `conditioning_regimen` (VARCHAR)
- `graft_source` (VARCHAR)
- `transplant_status` (VARCHAR)

**Datetime Columns:** 1 (transplant_date)

---

### v_encounters
**Purpose:** All clinical encounters
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `encounter_fhir_id` (VARCHAR)
- `encounter_date` (DATE)
- `age_at_encounter_days` (INTEGER)
- `status` (VARCHAR)
- `class_code` (VARCHAR)
- `class_display` (VARCHAR)
- `period_start` (TIMESTAMP(3))
- `period_end` (TIMESTAMP(3))
- `length_value` (DOUBLE)
- `length_unit` (VARCHAR)
- `patient_type` (VARCHAR) - Inpatient/Outpatient

**Datetime Columns:** 3 (encounter_date as DATE, period_start, period_end)

---

### v_visits_unified
**Purpose:** Unified view of appointments + encounters
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `appointment_fhir_id` (VARCHAR)
- `visit_type` (VARCHAR)
- `appointment_status` (VARCHAR)
- `appointment_start` (TIMESTAMP(3))
- `appointment_end` (TIMESTAMP(3))
- `encounter_id` (VARCHAR)
- `encounter_status` (VARCHAR)
- `encounter_start` (TIMESTAMP(3))
- `encounter_end` (TIMESTAMP(3))
- `visit_date` (DATE)
- `age_at_visit_days` (INTEGER)

**Datetime Columns:** 5 (appointment_start, appointment_end, encounter_start, encounter_end, visit_date as DATE)

---

### v_hydrocephalus_diagnosis
**Purpose:** Hydrocephalus-specific diagnoses
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `hd_condition_id` (VARCHAR)
- `hd_diagnosis_name` (VARCHAR)
- `hd_clinical_status` (VARCHAR)
- `hd_onset_date` (TIMESTAMP(3))
- `hd_verification_status` (VARCHAR)
- `hd_icd10_code` (VARCHAR)

**Datetime Columns:** 1 (hd_onset_date)

---

### v_unified_patient_timeline
**Purpose:** Master timeline combining all 13 event sources
**Version:** 2.2 (Updated to use v_visits_unified instead of v_encounters)
**Key Columns:**
- `patient_fhir_id` (VARCHAR)
- `event_id` (VARCHAR)
- `event_date` (DATE) - Standardized event date
- `age_at_event_days` (INTEGER)
- `age_at_event_years` (DOUBLE)
- `event_type` (VARCHAR) - Diagnosis, Procedure, Imaging, Medication, Visit, etc.
- `event_category` (VARCHAR) - Tumor, Treatment Toxicity, Completed Visit, etc.
- `event_subtype` (VARCHAR) - Progression, Recurrence, etc.
- `event_description` (VARCHAR)
- `event_status` (VARCHAR)
- `source_view` (VARCHAR) - Which view this came from
- `source_domain` (VARCHAR) - FHIR resource type
- `source_id` (VARCHAR) - FHIR resource ID
- `icd10_codes` (ARRAY<VARCHAR>)
- `snomed_codes` (ARRAY<VARCHAR>)
- `cpt_codes` (ARRAY<VARCHAR>)
- `loinc_codes` (ARRAY<VARCHAR>)
- `event_metadata` (VARCHAR) - JSON with domain-specific fields
- `extraction_context` (VARCHAR) - JSON with provenance metadata

**Datetime Columns:** 1 (event_date as DATE, derived from source datetime columns)
**Dependencies:** ALL source views
**Event Sources:** 13 (diagnoses, procedures, imaging, medications, **visits_unified**, measurements, molecular_tests, radiation_appointments, ophthalmology, audiology, transplants, corticosteroid_imaging, radiation_summary)

**IMPORTANT CHANGE (v2.2):** Now uses **v_visits_unified** instead of v_encounters. This provides:
- Unified appointment + encounter data (no duplication)
- Complete visit context (scheduled, no-show, cancelled, unscheduled)
- Richer metadata (appointment type, status, duration)

---

## DATETIME STANDARDIZATION SUMMARY

**Total Datetime Columns Standardized:** 102
**Standardization Pattern:**
- VARCHAR ISO8601 → `TRY(CAST(... AS TIMESTAMP(3)))`
- Existing TIMESTAMP → `TRY(CAST(... AS TIMESTAMP(3)))` for consistency
- DATE extraction → `DATE(timestamp_column)` instead of `SUBSTR(..., 1, 10)`

**Benefits:**
- Consistent typing across all views
- No downstream casting needed
- Proper NULL handling with TRY()
- Millisecond precision preserved
- Compatible with date math functions

---

## VIEW DEPENDENCIES

**Deployment Order:**
1. **Source Views** (22 views) - Can be deployed in any order
2. **Prerequisites** (2 views) - Require source views:
   - v_diagnoses (requires v_problem_list_diagnoses)
   - v_radiation_summary (requires v_radiation_treatments, v_radiation_treatment_appointments)
3. **Unified Timeline** (1 view) - Requires ALL source + prerequisite views:
   - v_unified_patient_timeline

---

## USAGE GUIDELINES

### For Analysts
- Use `v_unified_patient_timeline` for temporal analysis across domains
- Use source views (v_imaging, v_medications, etc.) for domain-specific analysis
- All datetime columns are TIMESTAMP(3) - use DATE() to extract date portion
- Prefix decoder helps understand column provenance

### For Developers
- Column prefixes indicate source FHIR resource
- Views with prefixes preserve all source data (no joins needed)
- Normalized views (v_diagnoses, v_unified_patient_timeline) remove prefixes
- All datetime math uses TIMESTAMP(3) types

### For DBAs
- Views are materialized daily (refresh schedule TBD)
- DATETIME_STANDARDIZED_VIEWS.sql contains all 24 view definitions
- V_UNIFIED_TIMELINE_PREREQUISITES.sql creates v_diagnoses + v_radiation_summary
- V_UNIFIED_PATIENT_TIMELINE.sql creates unified timeline

---

## MASTER SQL FILES

1. **DATETIME_STANDARDIZED_VIEWS.sql** (4,063 lines)
   - Contains all 22 source views + v_patient_demographics + v_diagnoses + v_radiation_summary
   - Single source of truth for datetime standardization

2. **V_UNIFIED_TIMELINE_PREREQUISITES.sql** (186 lines)
   - Creates v_diagnoses (normalizes v_problem_list_diagnoses)
   - Creates v_radiation_summary (aggregates v_radiation_treatments)

3. **V_UNIFIED_PATIENT_TIMELINE.sql** (1,162 lines)
   - Creates v_unified_patient_timeline
   - Combines 13 event sources into single timeline

---

## CHANGE LOG

**2025-10-19 (v2.0):**
- Datetime standardization: 102 VARCHAR → TIMESTAMP(3) conversions
- Fixed 8 SQL syntax errors (comma placement)
- Fixed 5 duplicate column aliases
- Fixed 3 SUBSTR on TIMESTAMP errors
- Fixed 2 missing TRY(CAST) wrappers
- Fixed COALESCE type mismatches
- All 25 views deployed to Athena successfully

**Previous Versions:**
- v1.0: Initial view creation (pre-datetime standardization)

---

## SUPPORT & REFERENCES

- **Master SQL File:** DATETIME_STANDARDIZED_VIEWS.sql
- **Deployment Guide:** DEPLOYMENT_ORDER.md
- **Analysis Summary:** ANALYSIS_SUMMARY.md
- **Standardization Status:** DATETIME_STANDARDIZATION_STATUS.md

---
