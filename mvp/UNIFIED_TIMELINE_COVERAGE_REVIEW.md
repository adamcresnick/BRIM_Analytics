# v_unified_patient_timeline Coverage Review

**Purpose**: Verify that `v_unified_patient_timeline` integrates ALL temporal events from Athena views

**Date**: 2025-10-19
**Status**: Gap Analysis Complete

---

## Complete Athena View Inventory (28 Views)

Based on `/athena_views/views/ATHENA_VIEW_CREATION_QUERIES.sql`:

| # | View Name | Has Temporal Data? | Included in v_unified_patient_timeline? | Status |
|---|-----------|-------------------|----------------------------------------|---------|
| 1 | `v_patient_demographics` | ✅ birth_date | ❌ No (reference table only) | ✅ OK - Not an event |
| 2 | `v_problem_list_diagnoses` | ✅ onset_date, recorded_date | ✅ YES (via v_diagnoses) | ✅ COVERED |
| 3 | `v_procedures` | ✅ procedure_date | ✅ YES | ✅ COVERED |
| 4 | `v_procedures_tumor` | ✅ procedure_date | ✅ YES (subset of v_procedures) | ✅ COVERED |
| 5 | `v_medications` | ✅ medication_start_date | ✅ YES | ✅ COVERED |
| 6 | `v_imaging` | ✅ imaging_date | ✅ YES | ✅ COVERED |
| 7 | `v_encounters` | ✅ encounter_date | ✅ YES | ✅ COVERED |
| 8 | `v_appointments` | ✅ appointment_date | ⚠️ PARTIAL (duplicates encounters) | ⚠️ REVIEW |
| 9 | `v_visits_unified` | ✅ Maps appointments to encounters | ❌ NO | ⚠️ REVIEW |
| 10 | `v_imaging_corticosteroid_use` | ✅ corticosteroid timing windows | ❌ NO | ❌ **MISSING** |
| 11 | `v_measurements` | ✅ measurement_date | ⚠️ PARTIAL (only height/weight in demographics) | ❌ **MISSING** |
| 12 | `v_binary_files` | ✅ document_date | ❌ NO | ⚠️ REVIEW |
| 13 | `v_molecular_tests` | ✅ test_date | ✅ YES (as v_molecular_tests_metadata) | ✅ COVERED |
| 14 | `v_radiation_treatment_appointments` | ✅ appointment_date | ❌ NO | ❌ **MISSING** |
| 15 | `v_radiation_treatment_courses` | ✅ course_start_date, course_end_date | ✅ YES (via v_radiation_summary) | ⚠️ PARTIAL |
| 16 | `v_radiation_care_plan_notes` | ✅ note_date | ❌ NO | ❌ **MISSING** |
| 17 | `v_radiation_care_plan_hierarchy` | ✅ care_plan_created_date | ❌ NO | ⚠️ REVIEW |
| 18 | `v_radiation_service_request_notes` | ✅ service_request_date | ❌ NO | ❌ **MISSING** |
| 19 | `v_radiation_service_request_rt_history` | ✅ service_request_date | ❌ NO | ❌ **MISSING** |
| 20 | `v_radiation_treatments` | ✅ treatment_date | ❌ NO | ❌ **MISSING** |
| 21 | `v_radiation_documents` | ✅ document_date | ❌ NO | ⚠️ REVIEW |
| 22 | `v_hydrocephalus_diagnosis` | ✅ onset_date | ⚠️ PARTIAL (subset of diagnoses) | ✅ COVERED |
| 23 | `v_hydrocephalus_procedures` | ✅ procedure_date | ⚠️ PARTIAL (subset of procedures) | ✅ COVERED |
| 24 | `v_autologous_stem_cell_transplant` | ✅ transplant_date, conditioning_start | ❌ NO | ❌ **MISSING** |
| 25 | `v_concomitant_medications` | ✅ medication_start_date, timepoint | ❌ NO | ⚠️ REVIEW |
| 26 | `v_autologous_stem_cell_collection` | ✅ collection_date | ❌ NO | ❌ **MISSING** |
| 27 | `v_ophthalmology_assessments` | ✅ assessment_date | ❌ NO | ❌ **MISSING** |
| 28 | `v_audiology_assessments` | ✅ assessment_date | ❌ NO | ❌ **MISSING** |

---

## Gap Summary

### ✅ **COVERED (11 views)**
Successfully integrated into `v_unified_patient_timeline`:
1. v_diagnoses (includes problem_list_diagnoses)
2. v_procedures (includes procedures_tumor, hydrocephalus_procedures)
3. v_medications
4. v_imaging
5. v_encounters
6. v_molecular_tests
7. v_radiation_treatment_courses (partial - only course start/end, not individual appointments)

### ❌ **MISSING (10 views with temporal events)**

**CRITICAL - High Clinical Value**:
1. **v_ophthalmology_assessments** - Visual acuity, visual fields, OCT, fundus exams
   - **Impact**: Missing key neurotoxicity assessments for brain tumor patients
   - **Patient e4BwD8ZYDBccepXcJ.Ilo3w3**: Likely has multiple ophthalmology assessments (diplopia, nystagmus documented)

2. **v_audiology_assessments** - Audiograms, hearing thresholds, ototoxicity monitoring
   - **Impact**: Missing ototoxicity surveillance for platinum chemotherapy
   - **Prevalence**: 1,141 patients with audiometry data

3. **v_measurements** - Height, weight, BMI, lab values (CBC, metabolic panels)
   - **Impact**: Missing growth monitoring (pediatric patients), toxicity labs
   - **Patient e4BwD8ZYDBccepXcJ.Ilo3w3**: 1,570 measurement records

4. **v_autologous_stem_cell_transplant** - Transplant dates, conditioning regimens
   - **Impact**: Missing major treatment modality
   - **Prevalence**: 1,981 transplant records

5. **v_autologous_stem_cell_collection** - Collection dates, apheresis procedures
   - **Impact**: Missing preparatory procedures for transplant

**MODERATE - Radiation Detail**:
6. **v_radiation_treatment_appointments** - Individual fraction dates (72 appointments for patient e4BwD8ZYDBccepXcJ.Ilo3w3)
   - **Current**: Only course-level (start/end dates)
   - **Missing**: Daily treatment dates for dose tracking

7. **v_radiation_care_plan_notes** - Treatment planning notes with dates
8. **v_radiation_service_request_notes** - Radiation oncology consult notes
9. **v_radiation_service_request_rt_history** - Prior radiation history
10. **v_imaging_corticosteroid_use** - Corticosteroid timing around imaging (toxicity signal)

### ⚠️ **REVIEW NEEDED (7 views)**

**Potentially Redundant**:
1. **v_appointments** - May duplicate v_encounters
2. **v_visits_unified** - Maps appointments → encounters (useful for linkage, not independent events)
3. **v_concomitant_medications** - Subset of v_medications with timepoint mapping
4. **v_hydrocephalus_diagnosis** - Subset of v_diagnoses
5. **v_hydrocephalus_procedures** - Subset of v_procedures

**Document References (Not Events)**:
6. **v_binary_files** - Document metadata (S3 URLs) - not temporal events, used for extraction
7. **v_radiation_documents** - Radiation-specific documents

---

## Detailed Gap Analysis

### Gap 1: v_ophthalmology_assessments ❌ CRITICAL

**View Structure**:
```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_ophthalmology_assessments AS
WITH visual_acuity_obs AS (...),
     fundus_optic_disc_obs AS (...),
     visual_field_procedures AS (...),
     oct_procedures AS (...)
```

**Temporal Fields**:
- `assessment_date` (DATE)
- `full_datetime` (TIMESTAMP)

**Assessment Categories**:
- `visual_acuity` - Snellen, LogMAR, ETDRS, HOTV charts
- `optic_disc_papilledema` - Critical for ICP monitoring
- `optic_disc_exam` - Fundoscopy findings
- `visual_field` - Perimetry (Goldmann, Humphrey)
- `oct_optic_nerve`, `oct_retina`, `oct_macula` - Structural imaging

**Why Missing is Critical**:
- Brain tumor patients often have visual deficits (diplopia, vision loss, papilledema)
- Ophthalmology assessments track treatment neurotoxicity
- Visual acuity is a BRIM data dictionary variable (ophthalmology_functional_assessment form)

**Recommended Fix**:
```sql
UNION ALL

-- ============================================================================
-- OPHTHALMOLOGY ASSESSMENTS AS EVENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'ophtho_' || record_fhir_id as event_id,
    assessment_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, assessment_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, assessment_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Assessment' as event_type,
    'Ophthalmology' as event_category,
    assessment_category as event_subtype,  -- 'visual_acuity', 'visual_field', 'oct_optic_nerve', etc.
    assessment_description as event_description,
    record_status as event_status,
    source_table as source_domain,
    record_fhir_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'assessment_category', assessment_category,
        'numeric_value', numeric_value,
        'value_unit', value_unit,
        'text_value', text_value,
        'component_name', component_name,
        'component_numeric_value', component_numeric_value,
        'laterality', CASE
            WHEN LOWER(assessment_description) LIKE '%left%' THEN 'left'
            WHEN LOWER(assessment_description) LIKE '%right%' THEN 'right'
            WHEN LOWER(assessment_description) LIKE '%both%' THEN 'both'
            ELSE 'unspecified'
        END,
        'file_url', file_url,
        'file_type', file_type
    ) as event_metadata
FROM fhir_prd_db.v_ophthalmology_assessments voa
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON voa.patient_fhir_id = vpd.patient_fhir_id
```

**Patient e4BwD8ZYDBccepXcJ.Ilo3w3 Impact**:
- Has documented diplopia (2018-12-15), nystagmus (2018-09-29)
- Likely has serial visual assessments during treatment/surveillance
- Missing these events = incomplete neurotoxicity timeline

---

### Gap 2: v_audiology_assessments ❌ CRITICAL

**View Structure**:
```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_audiology_assessments AS
WITH audiogram_thresholds AS (...),
     hearing_aid_status AS (...),
     hearing_loss_diagnoses AS (...)
```

**Temporal Fields**:
- `assessment_date` (DATE)

**Assessment Categories**:
- `audiogram_threshold` - Pure tone audiometry at specific frequencies (250Hz-8000Hz)
- `hearing_aid_status` - Hearing aid use/fitting
- `ototoxicity_monitoring` - Serial audiometry for chemotherapy patients
- `hearing_loss_diagnosis` - Confirmed hearing loss with type/laterality

**Clinical Context**:
- 825 ototoxicity monitoring records (259 patients)
- 99 ototoxic hearing loss diagnoses (22 patients with platinum toxicity)
- Critical for carboplatin/cisplatin chemotherapy monitoring

**Recommended Fix**:
```sql
UNION ALL

-- ============================================================================
-- AUDIOLOGY ASSESSMENTS AS EVENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'audio_' || record_fhir_id as event_id,
    assessment_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, assessment_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, assessment_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Assessment' as event_type,
    'Audiology' as event_category,
    assessment_category as event_subtype,  -- 'audiogram_threshold', 'ototoxicity_monitoring', etc.
    assessment_description as event_description,
    record_status as event_status,
    source_table as source_domain,
    record_fhir_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'assessment_category', assessment_category,
        'frequency_hz', frequency_hz,
        'threshold_db', threshold_db,
        'laterality', laterality,
        'hearing_loss_type', hearing_loss_type,
        'file_url', file_url,
        'file_type', file_type
    ) as event_metadata
FROM fhir_prd_db.v_audiology_assessments vaa
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vaa.patient_fhir_id = vpd.patient_fhir_id
```

---

### Gap 3: v_measurements ❌ CRITICAL

**Current State**:
- `v_unified_patient_timeline` includes NO measurements
- Patient e4BwD8ZYDBccepXcJ.Ilo3w3 has **1,570 measurement records**

**View Structure**:
```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_measurements AS
WITH observations AS (
    -- Height, weight, BMI, vitals
    SELECT ... FROM observation
),
lab_tests AS (
    -- CBC, metabolic panels, etc.
    SELECT ... FROM lab_tests
)
```

**Temporal Fields**:
- `measurement_date` (DATE)
- `age_at_measurement_days`

**Measurement Types**:
- **Growth**: Height, weight, BMI (critical for pediatric patients)
- **Vitals**: BP, HR, temperature, SpO2
- **Labs**: CBC (neutrophil counts, platelets), metabolic panels, liver/kidney function

**Why Missing is Critical**:
- Growth monitoring essential for pediatric brain tumor patients
- Lab values track chemotherapy toxicity (neutropenia, thrombocytopenia)
- Frequent measurements (patient e4BwD8ZYDBccepXcJ.Ilo3w3: 1,570 records over 20 years)

**Recommended Fix**:
```sql
UNION ALL

-- ============================================================================
-- MEASUREMENTS AS EVENTS (Height, Weight, Vitals, Labs)
-- ============================================================================
SELECT
    patient_fhir_id,
    COALESCE('obs_' || obs_observation_id, 'lab_' || lt_test_id) as event_id,
    measurement_date as event_date,
    age_at_measurement_days as age_at_event_days,
    age_at_measurement_years as age_at_event_years,
    'Measurement' as event_type,
    CASE
        WHEN LOWER(obs_measurement_type) IN ('height', 'weight', 'bmi') THEN 'Growth'
        WHEN LOWER(obs_measurement_type) LIKE '%blood pressure%' OR LOWER(obs_measurement_type) LIKE '%heart rate%' THEN 'Vitals'
        WHEN LOWER(lt_measurement_type) LIKE '%cbc%' OR LOWER(lt_measurement_type) LIKE '%blood count%' THEN 'Hematology Lab'
        WHEN LOWER(lt_measurement_type) LIKE '%metabolic%' OR LOWER(lt_measurement_type) LIKE '%chemistry%' THEN 'Chemistry Lab'
        WHEN LOWER(lt_measurement_type) LIKE '%liver%' OR LOWER(lt_measurement_type) LIKE '%hepatic%' THEN 'Liver Function'
        WHEN LOWER(lt_measurement_type) LIKE '%renal%' OR LOWER(lt_measurement_type) LIKE '%creatinine%' THEN 'Renal Function'
        ELSE 'Other Lab'
    END as event_category,
    NULL as event_subtype,
    COALESCE(obs_measurement_type, lt_measurement_type) as event_description,
    COALESCE(obs_status, lt_status) as event_status,
    source_table as source_domain,
    COALESCE(obs_observation_id, lt_test_id) as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'measurement_type', COALESCE(obs_measurement_type, lt_measurement_type),
        'measurement_value', COALESCE(CAST(obs_measurement_value AS VARCHAR), ltr_value_string),
        'measurement_unit', COALESCE(obs_measurement_unit, ltr_measurement_unit),
        'value_range_low', ltr_value_range_low_value,
        'value_range_high', ltr_value_range_high_value,
        'test_component', ltr_test_component
    ) as event_metadata
FROM fhir_prd_db.v_measurements vm
```

**Patient e4BwD8ZYDBccepXcJ.Ilo3w3 Impact**:
- 1,570 measurements from birth (2005-05-13) to present (2025-10-19)
- Includes growth tracking (height/weight every visit)
- Labs during chemotherapy (CBC, metabolic panels)
- Currently ALL MISSING from timeline

---

### Gap 4: v_autologous_stem_cell_transplant ❌ HIGH

**View Structure**:
- Captures transplant status, conditioning regimen dates, transplant dates
- 1,981 transplant records across patient cohort

**Temporal Fields**:
- `transplant_date`
- `conditioning_regimen_start_date`
- `conditioning_regimen_end_date`

**Why Missing is Moderate-High**:
- Major treatment modality for some brain tumor patients
- Not applicable to patient e4BwD8ZYDBccepXcJ.Ilo3w3 (no transplant)
- But critical for patients who DID receive transplant

**Recommended Fix**:
```sql
UNION ALL

-- ============================================================================
-- AUTOLOGOUS STEM CELL TRANSPLANT AS EVENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'transplant_' || transplant_id as event_id,
    transplant_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, transplant_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, transplant_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Procedure' as event_type,
    'Stem Cell Transplant' as event_category,
    'Autologous Transplant' as event_subtype,
    'Autologous stem cell transplant' as event_description,
    transplant_status as event_status,
    source_table as source_domain,
    transplant_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'conditioning_regimen', conditioning_regimen,
        'conditioning_start_date', conditioning_regimen_start_date,
        'conditioning_end_date', conditioning_regimen_end_date,
        'transplant_date', transplant_date
    ) as event_metadata
FROM fhir_prd_db.v_autologous_stem_cell_transplant vasct
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vasct.patient_fhir_id = vpd.patient_fhir_id
```

---

### Gap 5: v_radiation_treatment_appointments ❌ MODERATE

**Current State**:
- `v_unified_patient_timeline` includes radiation COURSES (start/end dates)
- **Missing**: Individual treatment fractions (appointments)

**Patient e4BwD8ZYDBccepXcJ.Ilo3w3 Impact**:
- Received 72 radiation treatment appointments
- Currently only 4 course-level events captured

**Why Missing is Moderate**:
- Course-level dates sufficient for most timeline queries
- Individual fractions useful for:
  - Daily dose tracking
  - Treatment interruptions/delays
  - Concurrent chemotherapy timing

**Recommended Fix** (OPTIONAL - may create noise):
```sql
UNION ALL

-- ============================================================================
-- RADIATION TREATMENT APPOINTMENTS AS EVENTS (Individual Fractions)
-- ============================================================================
SELECT
    patient_fhir_id,
    'radfx_' || appointment_id as event_id,
    appointment_start_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, CAST(appointment_start_date AS DATE)) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, CAST(appointment_start_date AS DATE)) AS DOUBLE) / 365.25 as age_at_event_years,
    'Radiation Fraction' as event_type,
    'Radiation Therapy' as event_category,
    NULL as event_subtype,
    'Radiation treatment fraction' as event_description,
    appointment_status as event_status,
    'Appointment' as source_domain,
    appointment_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'appointment_start', appointment_start_date,
        'appointment_end', appointment_end_date,
        'service_category', service_category
    ) as event_metadata
FROM fhir_prd_db.v_radiation_treatment_appointments vrta
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vrta.patient_fhir_id = vpd.patient_fhir_id
```

---

### Gap 6: v_imaging_corticosteroid_use ❌ MODERATE

**View Purpose**: Captures corticosteroid timing windows around imaging dates

**Why Relevant**:
- Corticosteroids used to reduce brain edema around imaging
- Important for interpreting imaging findings (dexamethasone can mask progression)
- Toxicity signal (long-term steroid use)

**Recommended Fix**:
```sql
UNION ALL

-- ============================================================================
-- CORTICOSTEROID USE AS EVENTS (Linked to Imaging)
-- ============================================================================
SELECT
    patient_fhir_id,
    'cortico_' || medication_request_id as event_id,
    imaging_date as event_date,  -- Anchor to imaging date
    age_at_imaging_days as age_at_event_days,
    CAST(age_at_imaging_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Medication' as event_type,
    'Corticosteroid (Imaging-Related)' as event_category,
    NULL as event_subtype,
    medication_name || ' around imaging' as event_description,
    medication_status as event_status,
    'MedicationRequest' as source_domain,
    medication_request_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'medication_name', medication_name,
        'imaging_date', imaging_date,
        'imaging_modality', imaging_modality,
        'timing_window_start', timing_window_start,
        'timing_window_end', timing_window_end
    ) as event_metadata
FROM fhir_prd_db.v_imaging_corticosteroid_use vicu
```

---

## Recommended Remediation Priority

### **Phase 1: CRITICAL (Week 1)**
1. ✅ Add `v_ophthalmology_assessments` - Visual acuity, visual fields, OCT
2. ✅ Add `v_audiology_assessments` - Audiograms, ototoxicity monitoring
3. ✅ Add `v_measurements` - Growth (height/weight), vitals, labs

**Rationale**: These are high-frequency, high-clinical-value events missing for ALL patients

### **Phase 2: HIGH (Week 2)**
4. ✅ Add `v_autologous_stem_cell_transplant` - Transplant dates, conditioning
5. ✅ Add `v_autologous_stem_cell_collection` - Collection procedures
6. ✅ Add `v_imaging_corticosteroid_use` - Steroid timing around imaging

**Rationale**: Major treatment modalities and toxicity signals

### **Phase 3: MODERATE (Week 3)**
7. ⚠️ OPTIONAL: Add `v_radiation_treatment_appointments` - Individual fractions
   - **Trade-off**: Adds 72 events per patient receiving radiation vs 4 course-level events
   - **Decision**: Include if daily dose tracking required; otherwise course-level sufficient

8. ⚠️ REVIEW: `v_radiation_care_plan_notes`, `v_radiation_service_request_notes`
   - **Decision**: These are document references, not temporal events
   - **Action**: Include only if notes contain extractable structured data

### **Phase 4: DEFER**
9. ❌ SKIP: `v_appointments` - Duplicate of `v_encounters`
10. ❌ SKIP: `v_visits_unified` - Mapping table, not independent events
11. ❌ SKIP: `v_concomitant_medications` - Subset of `v_medications`
12. ❌ SKIP: `v_binary_files`, `v_radiation_documents` - Document metadata, not events

---

## Updated v_unified_patient_timeline - Complete Version

After adding all CRITICAL and HIGH priority gaps:

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_unified_patient_timeline AS

-- [EXISTING UNIONS - Already in remediation doc]
-- Diagnoses, Procedures, Imaging, Medications, Encounters, Molecular Tests, Radiation Courses

UNION ALL

-- ============================================================================
-- OPHTHALMOLOGY ASSESSMENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'ophtho_' || record_fhir_id as event_id,
    assessment_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, assessment_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, assessment_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Assessment' as event_type,
    'Ophthalmology' as event_category,
    assessment_category as event_subtype,
    assessment_description as event_description,
    record_status as event_status,
    source_table as source_domain,
    record_fhir_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'assessment_category', assessment_category,
        'numeric_value', numeric_value,
        'value_unit', value_unit,
        'text_value', text_value,
        'component_name', component_name,
        'component_numeric_value', component_numeric_value,
        'laterality', CASE
            WHEN LOWER(assessment_description) LIKE '%left%' THEN 'left'
            WHEN LOWER(assessment_description) LIKE '%right%' THEN 'right'
            WHEN LOWER(assessment_description) LIKE '%both%' THEN 'both'
            ELSE 'unspecified'
        END
    ) as event_metadata
FROM fhir_prd_db.v_ophthalmology_assessments voa
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON voa.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- AUDIOLOGY ASSESSMENTS
-- ============================================================================
SELECT
    patient_fhir_id,
    'audio_' || record_fhir_id as event_id,
    assessment_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, assessment_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, assessment_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Assessment' as event_type,
    'Audiology' as event_category,
    assessment_category as event_subtype,
    assessment_description as event_description,
    record_status as event_status,
    source_table as source_domain,
    record_fhir_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    ARRAY[cpt_code] as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'assessment_category', assessment_category,
        'frequency_hz', frequency_hz,
        'threshold_db', threshold_db,
        'laterality', laterality,
        'hearing_loss_type', hearing_loss_type
    ) as event_metadata
FROM fhir_prd_db.v_audiology_assessments vaa
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vaa.patient_fhir_id = vpd.patient_fhir_id

UNION ALL

-- ============================================================================
-- MEASUREMENTS (Growth, Vitals, Labs)
-- ============================================================================
SELECT
    patient_fhir_id,
    COALESCE('obs_' || obs_observation_id, 'lab_' || lt_test_id) as event_id,
    measurement_date as event_date,
    age_at_measurement_days as age_at_event_days,
    age_at_measurement_years as age_at_event_years,
    'Measurement' as event_type,
    CASE
        WHEN LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) IN ('height', 'weight', 'bmi') THEN 'Growth'
        WHEN LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) LIKE '%blood pressure%'
             OR LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) LIKE '%heart rate%' THEN 'Vitals'
        WHEN LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) LIKE '%cbc%'
             OR LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) LIKE '%blood count%' THEN 'Hematology Lab'
        WHEN LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) LIKE '%metabolic%'
             OR LOWER(COALESCE(obs_measurement_type, lt_measurement_type)) LIKE '%chemistry%' THEN 'Chemistry Lab'
        ELSE 'Other Lab'
    END as event_category,
    NULL as event_subtype,
    COALESCE(obs_measurement_type, lt_measurement_type) as event_description,
    COALESCE(obs_status, lt_status) as event_status,
    source_table as source_domain,
    COALESCE(obs_observation_id, lt_test_id) as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'measurement_type', COALESCE(obs_measurement_type, lt_measurement_type),
        'measurement_value', COALESCE(CAST(obs_measurement_value AS VARCHAR), ltr_value_string),
        'measurement_unit', COALESCE(obs_measurement_unit, ltr_measurement_unit),
        'value_range_low', ltr_value_range_low_value,
        'value_range_high', ltr_value_range_high_value
    ) as event_metadata
FROM fhir_prd_db.v_measurements vm

UNION ALL

-- ============================================================================
-- AUTOLOGOUS STEM CELL TRANSPLANT
-- ============================================================================
SELECT
    patient_fhir_id,
    'transplant_' || transplant_id as event_id,
    transplant_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, transplant_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, transplant_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Procedure' as event_type,
    'Stem Cell Transplant' as event_category,
    'Autologous Transplant' as event_subtype,
    'Autologous stem cell transplant' as event_description,
    transplant_status as event_status,
    source_table as source_domain,
    transplant_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'conditioning_regimen', conditioning_regimen,
        'conditioning_start_date', conditioning_regimen_start_date,
        'conditioning_end_date', conditioning_regimen_end_date
    ) as event_metadata
FROM fhir_prd_db.v_autologous_stem_cell_transplant vasct
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vasct.patient_fhir_id = vpd.patient_fhir_id
WHERE transplant_date IS NOT NULL

UNION ALL

-- ============================================================================
-- AUTOLOGOUS STEM CELL COLLECTION
-- ============================================================================
SELECT
    patient_fhir_id,
    'stemcell_coll_' || collection_id as event_id,
    collection_date as event_date,
    DATE_DIFF('day', vpd.pd_birth_date, collection_date) as age_at_event_days,
    CAST(DATE_DIFF('day', vpd.pd_birth_date, collection_date) AS DOUBLE) / 365.25 as age_at_event_years,
    'Procedure' as event_type,
    'Stem Cell Collection' as event_category,
    'Apheresis' as event_subtype,
    'Autologous stem cell collection' as event_description,
    collection_status as event_status,
    source_table as source_domain,
    collection_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'collection_date', collection_date,
        'collection_method', collection_method
    ) as event_metadata
FROM fhir_prd_db.v_autologous_stem_cell_collection vascc
LEFT JOIN fhir_prd_db.v_patient_demographics vpd ON vascc.patient_fhir_id = vpd.patient_fhir_id
WHERE collection_date IS NOT NULL

UNION ALL

-- ============================================================================
-- IMAGING-RELATED CORTICOSTEROID USE
-- ============================================================================
SELECT
    patient_fhir_id,
    'cortico_img_' || medication_request_id as event_id,
    imaging_date as event_date,
    age_at_imaging_days as age_at_event_days,
    CAST(age_at_imaging_days AS DOUBLE) / 365.25 as age_at_event_years,
    'Medication' as event_type,
    'Corticosteroid (Imaging)' as event_category,
    NULL as event_subtype,
    medication_name || ' around ' || imaging_modality || ' imaging' as event_description,
    medication_status as event_status,
    'MedicationRequest' as source_domain,
    medication_request_id as source_id,
    CAST(NULL AS ARRAY(VARCHAR)) as icd10_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as snomed_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as cpt_codes,
    CAST(NULL AS ARRAY(VARCHAR)) as loinc_codes,
    JSON_OBJECT(
        'medication_name', medication_name,
        'imaging_date', imaging_date,
        'imaging_modality', imaging_modality,
        'timing_window_start', timing_window_start,
        'timing_window_end', timing_window_end
    ) as event_metadata
FROM fhir_prd_db.v_imaging_corticosteroid_use vicu

ORDER BY patient_fhir_id, event_date;
```

---

## Expected Event Count for Patient e4BwD8ZYDBccepXcJ.Ilo3w3

**Before Gaps Fixed**:
- Diagnoses: 24
- Procedures: 72
- Imaging: 181
- Medications: 1,121
- Encounters: 999
- Molecular Tests: 3
- Radiation: 4 (courses)
- **TOTAL**: ~2,404 events

**After Gaps Fixed (Phase 1 + Phase 2)**:
- + Measurements: 1,570
- + Ophthalmology: ~50 (estimated, based on vision diagnoses)
- + Audiology: ~10 (estimated, if ototoxicity monitoring)
- + Corticosteroid (imaging): ~20 (estimated)
- **NEW TOTAL**: ~4,054 events

**If Phase 3 included** (radiation fractions):
- + Radiation appointments: 72
- **TOTAL**: ~4,126 events

---

## Validation Queries

After implementing complete `v_unified_patient_timeline`:

```sql
-- Test 1: Event type distribution for patient e4BwD8ZYDBccepXcJ.Ilo3w3
SELECT
    event_type,
    event_category,
    COUNT(*) as event_count,
    MIN(event_date) as earliest,
    MAX(event_date) as latest
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type, event_category
ORDER BY event_count DESC;

-- Test 2: Verify measurements included
SELECT COUNT(*) as measurement_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_type = 'Measurement';
-- EXPECTED: ~1570

-- Test 3: Verify ophthalmology assessments included
SELECT COUNT(*) as ophtho_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_category = 'Ophthalmology';
-- EXPECTED: >0 (patient has vision diagnoses)

-- Test 4: Check for duplicate events
SELECT
    event_id,
    COUNT(*) as duplicate_count
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY event_id
HAVING COUNT(*) > 1;
-- EXPECTED: 0 rows (no duplicates)
```

---

## Conclusion

### ✅ **Gaps Identified**: 10 missing views with temporal data
### ✅ **CRITICAL Gaps (Phase 1)**: 3 views (ophthalmology, audiology, measurements)
### ✅ **HIGH Gaps (Phase 2)**: 3 views (transplant, stem cell collection, corticosteroids)
### ⚠️ **MODERATE Gaps (Phase 3)**: 4 views (radiation details, care plan notes)

**Recommendation**: Implement Phase 1 (CRITICAL) and Phase 2 (HIGH) before proceeding to DuckDB implementation.

**Next Steps**:
1. Add UNION ALL blocks for Phase 1 views to `v_unified_patient_timeline`
2. Test with patient e4BwD8ZYDBccepXcJ.Ilo3w3 validation queries
3. Verify event counts match expectations
4. Proceed to Phase 2 additions
5. Create `v_patient_disease_phases` and `v_progression_detection` views

---

**Document Status**: Coverage Review Complete ✅
**Date**: 2025-10-19
