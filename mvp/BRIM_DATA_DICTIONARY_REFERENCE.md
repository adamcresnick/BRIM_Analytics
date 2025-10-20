# BRIM Data Dictionary Reference Files

## Purpose

This document codifies the **three key data dictionary files** that define the BRIM data model structure, which the patient timeline must align with.

---

## File 1: Main BRIM Data Dictionary
**Path**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/20250723_multitab_csvs/20250723_multitab__data_dictionary.csv`

**Size**: 28KB

**Structure**: CSV with columns:
- `Variable / Field Name`
- `Tab` (Collection form name)
- `CollectionForm Name`
- `Field Type` (radio, checkbox, dropdown, text, notes)
- `Field Label`
- `Choices, Calculations, OR Slider Labels`
- `Field Note`
- `Branching Logic`
- `Required Field?`
- `post-data entry coding logic`
- `Field Description`
- `Comments`

**Key Forms/Tabs**:
1. **demographics**: legal_sex, race, ethnicity
2. **diagnosis**:
   - `clinical_status_at_event` (Alive, Deceased-due to disease, etc.)
   - `event_type` (Initial CNS Tumor, Second Malignancy, Recurrence, Progressive, Deceased)
   - `age_at_event_days` - **PRIMARY TEMPORAL ANCHOR**
   - `cns_integrated_diagnosis` (123 diagnosis choices based on WHO 2021)
   - `who_grade` (1-4 or No grade specified)
   - `tumor_location` (24 anatomical location choices)
   - `metastasis`, `metastasis_location`
   - `tumor_or_molecular_tests_performed`
   - `shunt_required`
3. **treatment** (linked to diagnosis events):
   - `treatment_which_visit` (Initial Diagnosis, 3M, 6M, 12M, 18M, 24M, 30M, 36M, 42M, 48M, 60M, 5Y+, 10Y+, 15Y+)
   - `treatment_updated` (New, Ongoing, Modified Treatment, No treatment, Unavailable)
   - `surgery`: `age_at_surgery`, `extent_of_tumor_resection`, `specimen_collection_origin`
   - `chemotherapy`: `age_at_chemo_start`, `age_at_chemo_stop`, `chemotherapy_type`, `protocol_name`, `chemotherapy_agents`
   - `radiation`: `age_at_radiation_start`, `age_at_radiation_stop`, `radiation_type`, `radiation_site`, `total_radiation_dose`
4. **encounters** (follow-up visits):
   - `age_at_visit_follow_up_days` - **FOLLOW-UP TEMPORAL ANCHOR**
   - `update_which_visit` (same timepoint choices as treatment)
   - `follow_up_visit_status` (Visit Completed, Not seen, Lost to follow up)
   - `clinical_status` (Alive, Deceased)
   - `tumor_status` (No evidence of disease, Stable Disease, Change in tumor status, Decrease in tumor size, Not evaluated)
5. **survival**:
   - `age_at_last_known_status`
   - `os_days`, `os_censoring_status` (0=alive, 1=dead)
   - `efs_days`, `efs_censoring_status` (0=alive no progression, 1=event)
6. **family_cancer_history**: family_member, cancer_type, etc.
7. **conditions_predispositions**: `cancer_predisposition`, `medical_conditions_present_at_event`

**Critical Temporal Fields**:
- `age_at_event_days` - Date of surgery/diagnosis/death (converted to age in days from birth)
- `age_at_surgery` - Surgery dates
- `age_at_chemo_start` / `age_at_chemo_stop` - Chemotherapy timeline
- `age_at_radiation_start` / `age_at_radiation_stop` - Radiation timeline
- `age_at_visit_follow_up_days` - Follow-up encounter dates

**Event-Based Structure**:
- Each diagnosis event (Initial, Recurrence, Progression, Second Malignancy) gets unique `event_id`
- Treatments are linked to diagnosis events via `event_id`
- Follow-up encounters are linked to diagnosis events and have `update_which_visit` timepoints
- Multiple diagnosis events per patient create separate timelines

---

## File 2: Custom Forms Data Dictionary
**Path**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/20250723_multitab_csvs/20250723_multitab__data_dictionary_custom_forms.csv`

**Size**: 32KB

**Structure**: Same column structure as File 1

**Key Forms/Tabs**:
1. **additional_fields**:
   - `optic_pathway_glioma` (Yes/No/Unknown)
   - `nf1_yn`, `age_at_nf1_diagnosis_date_clinical`, `age_at_nf1_diagnosis_date_germline`
   - `nf1_germline_genetic_testing`, `pathogenic_nf1_variant`
2. **braf_alteration_details**:
   - `age_at_specimen_collection` - **TEMPORAL ANCHOR FOR MOLECULAR TESTING**
   - `braf_alteration_list` (BRAF V600E, BRAF V600K, KIAA1549-BRAF fusion, Other BRAF Fusion, CRAF/RAF1 Fusion)
   - `tumor_char_test_list` (FISH/ISH, Somatic Tumor Panel, Fusion Panel, WES/WGS, IHC, Microarray)
   - `methyl_profiling_yn`, `methyl_profiling_detail`
   - `braf_reports_submitted_to_cbtn`
3. **imaging_clinical_related**:
   - `age_at_date_scan` - **TEMPORAL ANCHOR FOR IMAGING**
   - `cortico_yn`, `cortico_number`, `cortico_1_name`, `cortico_1_dose`, etc. (up to 5 corticosteroids)
   - `ophtho_imaging_yn` (Was ophthalmology assessment done within prior 90 days?)
   - `imaging_clinical_status` (Stable, Improved, Deteriorating, Not Reporting)
4. **ophthalmology_functional_assessment**:
   - `age_at_ophtho_date` - **TEMPORAL ANCHOR FOR OPHTHALMOLOGY**
   - `ophtho_exams` (Visual Fields, Optic Disc, Visual Acuity, OCT)
   - Visual field deficits by quadrant (left/right eye)
   - Optic disc exam (pallor, edema - left/right)
   - Visual acuity scores (Teller, Snellen, HOTV, ETDRS, Cardiff, LEA, Other, logMAR)
   - OCT measurements (microns, left/right)
5. **hydrocephalus_details**:
   - `hydro_yn`, `age_at_hydro_event_date` - **TEMPORAL ANCHOR**
   - `hydro_method_diagnosed` (Clinical, CT, MRI)
   - `hydro_intervention` (Surgical, Medical, Hospitalization, None)
   - `hydro_surgical_management` (EVD, ETV, VPS placement, VPS revision)
   - `hydro_shunt_programmable` (Yes/No/Not applicable/Unknown)
   - `hydro_nonsurg_management` (Steroid, Shunt reprogramming, Other)
6. **concomitant_medications**:
   - `conmed_timepoint` (Event Diagnosis, 6M, 12M, 18M, 24M, 36M, 48M, 60M, 10Y, 15Y, 20Y)
   - `age_at_conmed_date` - **TEMPORAL ANCHOR**
   - `form_conmed_number` (1-10 medications, or None noted)
   - `rxnorm_cui`, `medication_name`, `conmed_routine` (Scheduled, PRN, Unknown)
7. **measurements**:
   - `age_at_measurement_date` - **TEMPORAL ANCHOR**
   - `height_cm`, `weight_kg`, `head_circumference_cm`
   - **Note**: "All data for this form is extracted directly from the clinical record. It is not manually entered into an CRF."

**Branching Logic Examples**:
- Corticosteroid fields only shown if `cortico_yn = '1'`
- Ophthalmology fields conditional on `ophtho_exams` checkboxes
- Hydrocephalus surgical management only shown if `hydro_intervention(1) = '1'` (Surgical selected)

---

## File 3: CBTN Data Dictionary (RedCap Export)
**Path**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction/Dictionary/CBTN_DataDictionary_2025-10-15.csv`

**Structure**: RedCap data dictionary export with columns:
- `Variable / Field Name`
- `Form Name`
- `Section Header`
- `Field Type`
- `Field Label`
- `Choices, Calculations, OR Slider Labels`
- `Field Note`
- `Text Validation Type OR Show Slider Number`
- `Text Validation Min`, `Text Validation Max`
- `Identifier?` (y/blank - indicates PHI fields)
- `Branching Logic`
- `Required Field?`
- `Custom Alignment`
- `Question Number`
- `Matrix Group Name`, `Matrix Ranking?`
- `Field Annotation`

**Key Differences from Files 1 & 2**:
1. **RedCap-specific metadata**: Includes `Identifier?` flag, `Field Annotation`, custom alignment
2. **Enrollment & Cohort Forms**:
   - `study_id`, `subject_consent_date`, `enrollment_status` (Transfer/Existing vs Prospective)
   - `subject_results_return`, `frontier`, `phi` (PHI sharing consent)
   - `subject_deidentified` (permanently de-identified vs identifiable)
   - `first_name`, `last_name`, `mrn`, `dob` (marked as `Identifier? = y`)
   - `cbtn_d0261_subject` (Day One Low Grade Glioma FY2024-2025 cohort)
   - `az_hgg_cbtn_0149_subject` (AstraZeneca High Grade Glioma FY2025-2026 cohort)
3. **Medical History Form**:
   - `cancer_predisposition` (same 17 choices as File 1, but includes `germline` field, `results_available`, `cancer_predis_relative`)
   - `family_history` (more detailed family member structure with birth order for siblings)
4. **Diagnosis Form**:
   - `diagnosis_id` (auto-generated ID for data warehouse, marked `@HIDDEN`)
   - `clinical_status_at_event` (same as File 1)
   - `cause_of_death` (if deceased-due to other causes)
   - `gift_from_a_child_referral` (autopsy program referral)
   - `event_type` (same as File 1)
   - `date_of_event` (instead of `age_at_event_days`) - **yyyy-mm-dd format, must match specimen collection date**
   - `ops_center_pathology_review` (CHOP pathology diagnosis - read-only for non-CHOP sites)
   - `free_text_diagnosis` (pathology diagnosis from referring institution)
   - `who_cns5_diagnosis` (same 123 choices as File 1's `cns_integrated_diagnosis`)

**Critical Fields for Timeline Alignment**:
- `date_of_event` (yyyy-mm-dd) vs `age_at_event_days` (integer days from birth)
- `diagnosis_id` (warehouse auto-generated) - links diagnosis events across tables
- Cohort identification fields (`cbtn_d0261_subject`, etc.) - subset data by research cohort

**RedCap Annotations**:
- `@HIDDEN` - Field not shown in forms (auto-generated)
- `@READONLY` - Field locked after initial entry
- `@HIDEBUTTON` - Date picker button hidden
- `@DEFAULT="1"` - Default value pre-selected
- `@HIDECHOICE="11"` - Specific choice hidden from dropdown
- `@IF([field]='','',@READONLY)` - Conditional read-only based on value

**Data Entry Workflow Clues**:
- File 3 is the **source RedCap data dictionary** used for manual data entry at participating institutions
- File 1 & 2 are **extracted/transformed versions** used for BRIM platform data export
- Transformation: `date_of_event` (File 3) → `age_at_event_days` (File 1) via "Convert date to age in days" post-processing

---

## Key Insights for Timeline Construction

### 1. Event-Based Data Model
All three files use **event-driven architecture**:
- Each diagnosis event (Initial, Recurrence, Progression, Second Malignancy, Deceased) creates new record
- Diagnosis events anchor all other data (treatments, encounters, imaging, molecular tests)
- Multiple events per patient = multiple timelines

### 2. Temporal Anchors (Age in Days from Birth)
Primary anchors:
- `age_at_event_days` (diagnosis/surgery/death)
- `age_at_surgery`
- `age_at_chemo_start`, `age_at_chemo_stop`
- `age_at_radiation_start`, `age_at_radiation_stop`
- `age_at_visit_follow_up_days`

Secondary anchors (custom forms):
- `age_at_date_scan` (imaging)
- `age_at_ophtho_date` (ophthalmology)
- `age_at_specimen_collection` (molecular tests)
- `age_at_hydro_event_date` (hydrocephalus)
- `age_at_conmed_date` (medication reconciliation)
- `age_at_measurement_date` (vitals)

All temporal data stored as **integer days from birth**, not calendar dates (for PHI protection with date shifting).

### 3. Timepoint Structure
Follow-up visits use standardized timepoints relative to diagnosis event:
- Initial Diagnosis (0 months)
- 3 Month Update
- 6 Month Update
- 12 Month Update
- 18 Month Update
- 24 Month Update
- 30 Month Update
- 36 Month Update
- 42 Month Update
- 48 Month Update
- 60 Month Update
- 5 Year Plus Update
- 10 Year Plus Update
- 15 Year Plus Update

Actual visit dates (`age_at_visit_follow_up_days`) are mapped to **closest timepoint** for organizational purposes.

### 4. Branching Logic
Forms have conditional display logic:
- Custom forms only shown if certain conditions met
- Example: Ophthalmology fields only shown if optic pathway tumor
- Example: Hydrocephalus surgical management only shown if surgical intervention selected
- Example: Corticosteroid dosing fields dynamically shown based on `cortico_number`

This means **not all forms apply to all patients**.

### 5. Data Quality Indicators
Built-in data quality fields:
- `formstatus_demo` (form completion status)
- Required fields flagged with `Required Field? = y`
- Post-data entry coding logic (e.g., "Convert date to age in days")
- Validation types (date_ymd, autocomplete)
- Default values and hidden choices

### 6. PHI Handling
File 3 identifies PHI fields with `Identifier? = y`:
- `study_id`, `subject_consent_date`
- `first_name`, `last_name`, `mrn`, `dob`

Files 1 & 2 use **de-identified temporal data** (age in days, not calendar dates).

---

## Usage for Timeline Construction

When constructing patient timeline from Athena data → BRIM variables:

1. **Extract diagnosis dates from Athena** → Convert to `age_at_event_days`
2. **Identify event types** (Initial vs Recurrence vs Progression) based on timeline
3. **Map treatment dates** to diagnosis events
4. **Assign follow-up visits to timepoints** based on days from diagnosis
5. **Populate custom forms** conditionally based on diagnosis (e.g., optic pathway glioma → ophthalmology forms)
6. **Ensure temporal consistency** (chemo start > diagnosis date, imaging near diagnosis, etc.)

---

**Last Updated**: 2025-10-19
**Purpose**: Reference document for Agent 1 to understand BRIM data model structure when constructing patient timelines
