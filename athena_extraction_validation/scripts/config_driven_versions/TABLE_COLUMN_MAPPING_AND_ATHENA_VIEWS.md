# Table & Column Mapping + Athena View Definitions
## Complete Reference for All Extraction Scripts

**Date**: October 12, 2025 (Updated)  
**Version**: 2.0 - Comprehensive Update  
**Purpose**: Document all source tables, columns, and prefixes used in extraction scripts, plus provide Athena SQL to recreate each output as a database view.

**Updates in v2.0**:
- ✅ Updated medications.csv: 44 → 45 columns (added `cp_created`)
- ✅ Updated appointments.csv: 15 → 21 columns (added 6 `ap_participant_*` fields)
- ✅ Updated imaging.csv: 17 → 18 columns (documented `patient_mrn`)
- ✅ Updated procedures.csv: ~40 → 34 columns (exact count)
- ✅ Updated measurements.csv: ~28 → 30 columns (exact count)
- ✅ **NEW**: Added diagnoses.csv documentation (17 columns)
- ✅ All Athena view definitions verified and updated

---

## Table of Contents
1. [Column Prefix Definitions](#column-prefix-definitions)
2. [Medications Extraction](#1-medications-extraction)
3. [Procedures Extraction](#2-procedures-extraction)
4. [Measurements Extraction](#3-measurements-extraction)
5. [Binary Files Extraction](#4-binary-files-extraction)
6. [Imaging Extraction](#5-imaging-extraction)
7. [Appointments Extraction](#6-appointments-extraction)
8. [Encounters Extraction](#7-encounters-extraction)
9. [Diagnoses Extraction](#8-diagnoses-extraction) ⭐ NEW

---

## Column Prefix Definitions

All extraction scripts use **table prefixes** to indicate data provenance (which table each column comes from). This prevents ambiguity when the same field name exists in multiple tables.

### Complete Prefix Legend

| Prefix | Source Table | Description |
|--------|--------------|-------------|
| **Medications Script** | | |
| `mr_` | medication_request | Main medication request table (prescriptions) |
| `mrn_` | medication_request_note | Clinical notes about medications (dose adjustments, trial status) |
| `mrr_` | medication_request_reason_code | Reason codes/indications for medications |
| `mrb_` | medication_request_based_on | Care plan linkages for medications |
| `mf_` | medication_form_coding | Medication form codes (tablet, injection, etc.) |
| `mi_` | medication_ingredient | Medication ingredient strengths |
| `cp_` | care_plan | Care plan/protocol details |
| `cpc_` | care_plan_category | Care plan categories (ONCOLOGY TREATMENT, etc.) |
| `cpcon_` | care_plan_addresses | Care plan addresses/concerns (what plan addresses) |
| `cpa_` | care_plan_activity | Care plan activity status |
| **Procedures Script** | | |
| `proc_` | procedure | Main procedure table (surgeries, interventions) |
| `pcc_` | procedure_code_coding | CPT/HCPCS procedure codes |
| `pcat_` | procedure_category_coding | Procedure categories |
| `pbs_` | procedure_body_site | Anatomical body sites for procedures |
| `pp_` | procedure_performer | Surgeons/providers who performed procedures |
| `prc_` | procedure_reason_code | Reasons/indications for procedures |
| `ppr_` | procedure_report | Procedure reports (operative notes, etc.) |
| **Measurements Script** | | |
| `obs_` | observation | Observations (anthropometric measurements, vitals) |
| `lt_` | lab_tests | Laboratory test metadata |
| `ltr_` | lab_test_results | Laboratory test result values |
| **Binary Files Script** | | |
| `dr_` | document_reference | Main document reference table |
| `dc_` | document_reference_content | Binary content details (IDs, types, sizes) |
| `de_` | document_reference_context_encounter | Encounter references for documents |
| `dt_` | document_reference_type_coding | Document type coding |
| `dcat_` | document_reference_category | Document categories |
| **Appointments Script** | | |
| `appt_` | appointment | Appointment details |
| `ap_` | appointment_participant | Appointment participant information (actor, type, required, status, period) |
| **Diagnoses Script** | | |
| (no prefix) | problem_list_diagnoses | Problem list diagnoses (single table extraction) |

**Note**: No prefixes are used for:
- **Imaging extraction** (uses materialized views: `radiology_imaging_mri`, `radiology_imaging`)
- **Encounters extraction** (main `encounter` table doesn't need prefixes for clarity)
- **Diagnoses extraction** (single table, no ambiguity)

---

## 1. Medications Extraction

### Output File: `medications.csv`

### Source Tables (10 tables with JOINs)

1. **patient_medications** (base view - no prefix for backward compatibility)
2. **medication_request** (`mr_` prefix) - Prescription details, temporal fields
3. **medication_request_note** (`mrn_` prefix) - Aggregated clinical notes
4. **medication_request_reason_code** (`mrr_` prefix) - Aggregated reason codes
5. **medication_request_based_on** (`mrb_` prefix) - Care plan linkages
6. **medication_form_coding** (`mf_` prefix) - Form codes via medication_id
7. **medication_ingredient** (`mi_` prefix) - Ingredient strengths via medication_id
8. **care_plan** (`cp_` prefix) - Protocol details
9. **care_plan_category** (`cpc_` prefix) - Aggregated categories
10. **care_plan_addresses** (`cpcon_` prefix) - Aggregated addresses/concerns

### Column Mapping (45 columns) ⭐ UPDATED

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| patient_fhir_id | patient_medications | patient_id | Patient FHIR ID |
| medication_request_id | patient_medications | medication_request_id | Medication request ID |
| medication_id | patient_medications | medication_id | Medication resource ID |
| medication_name | patient_medications | medication_name | Medication display name |
| medication_form | patient_medications | form_text | Medication form (tablet, capsule) |
| rx_norm_codes | patient_medications | rx_norm_codes | RxNorm codes |
| medication_start_date | patient_medications | authored_on | When medication was ordered |
| requester_name | patient_medications | requester_name | Prescribing provider |
| medication_status | patient_medications | status | Medication status |
| encounter_display | patient_medications | encounter_display | Encounter context |
| mr_validity_period_start | medication_request | dispense_request_validity_period_start | Medication validity start |
| mr_validity_period_end | medication_request | dispense_request_validity_period_end | **Individual medication stop date** |
| mr_authored_on | medication_request | authored_on | Prescription authored date |
| mr_status | medication_request | status | Request status |
| mr_status_reason_text | medication_request | status_reason_text | Status reason |
| mr_priority | medication_request | priority | Request priority |
| mr_intent | medication_request | intent | Request intent |
| mr_do_not_perform | medication_request | do_not_perform | Do not perform flag |
| mr_course_of_therapy_type_text | medication_request | course_of_therapy_type_text | Therapy course type (continuous, acute) |
| mr_dispense_initial_fill_duration_value | medication_request | dispense_request_initial_fill_duration_value | Initial fill duration |
| mr_dispense_initial_fill_duration_unit | medication_request | dispense_request_initial_fill_duration_unit | Duration unit |
| mr_dispense_expected_supply_duration_value | medication_request | dispense_request_expected_supply_duration_value | Expected supply duration |
| mr_dispense_expected_supply_duration_unit | medication_request | dispense_request_expected_supply_duration_unit | Duration unit |
| mr_dispense_number_of_repeats_allowed | medication_request | dispense_request_number_of_repeats_allowed | Number of refills |
| mr_substitution_allowed_boolean | medication_request | substitution_allowed_boolean | Substitution allowed |
| mr_substitution_reason_text | medication_request | substitution_reason_text | Substitution reason |
| mr_prior_prescription_display | medication_request | prior_prescription_display | Prior prescription (tracks switches) |
| mrn_note_text_aggregated | medication_request_note | note_text | Aggregated notes (LISTAGG) |
| mrr_reason_code_text_aggregated | medication_request_reason_code | reason_code_text | Aggregated reason codes (LISTAGG) |
| mrb_care_plan_reference | medication_request_based_on | based_on_reference | Care plan reference ID |
| mrb_care_plan_display | medication_request_based_on | based_on_display | Care plan display name |
| mf_form_coding_codes | medication_form_coding | form_coding_code | Form codes (LISTAGG) |
| mf_form_coding_displays | medication_form_coding | form_coding_display | Form displays (LISTAGG) |
| mi_ingredient_strengths | medication_ingredient | ingredient_strength_numerator_value + unit | Ingredient strengths (LISTAGG) |
| cp_id | care_plan | id | Care plan ID |
| cp_title | care_plan | title | Care plan title |
| cp_status | care_plan | status | Care plan status |
| cp_intent | care_plan | intent | Care plan intent |
| **cp_created** | **care_plan** | **created** | **When care plan was created** ⭐ **NEW** |
| cp_period_start | care_plan | period_start | Care plan period start |
| cp_period_end | care_plan | period_end | Care plan period end |
| cp_author_display | care_plan | author_display | Care plan author |
| cpc_categories_aggregated | care_plan_category | category_text | Categories (LISTAGG) |
| cpcon_addresses_aggregated | care_plan_addresses | addresses_display | Addresses/concerns (LISTAGG) |
| cpa_activity_detail_status | care_plan_activity | activity_detail_status | Activity status |

### Athena View Definition

```sql
-- Create view: medications_view
-- Database: fhir_prd_db (use instead of fhir_v2_prd_db)
-- Usage: SELECT * FROM fhir_prd_db.medications_view WHERE patient_fhir_id = 'Patient/{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.medications_view AS
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
    
    -- Patient medications view (no prefix for backward compatibility)
    pm.medication_request_id,
    pm.medication_id,
    pm.medication_name,
    pm.form_text as medication_form,
    pm.rx_norm_codes,
    pm.authored_on as medication_start_date,
    pm.requester_name,
    pm.status as medication_status,
    pm.encounter_display,
    
    -- Temporal fields (mr_ prefix)
    mr.dispense_request_validity_period_start as mr_validity_period_start,
    mr.dispense_request_validity_period_end as mr_validity_period_end,
    mr.authored_on as mr_authored_on,
    
    -- Status & priority (mr_ prefix)
    mr.status as mr_status,
    mr.status_reason_text as mr_status_reason_text,
    mr.priority as mr_priority,
    mr.intent as mr_intent,
    mr.do_not_perform as mr_do_not_perform,
    
    -- Treatment strategy (mr_ prefix)
    mr.course_of_therapy_type_text as mr_course_of_therapy_type_text,
    mr.dispense_request_initial_fill_duration_value as mr_dispense_initial_fill_duration_value,
    mr.dispense_request_initial_fill_duration_unit as mr_dispense_initial_fill_duration_unit,
    mr.dispense_request_expected_supply_duration_value as mr_dispense_expected_supply_duration_value,
    mr.dispense_request_expected_supply_duration_unit as mr_dispense_expected_supply_duration_unit,
    mr.dispense_request_number_of_repeats_allowed as mr_dispense_number_of_repeats_allowed,
    
    -- Treatment changes (mr_ prefix)
    mr.substitution_allowed_boolean as mr_substitution_allowed_boolean,
    mr.substitution_reason_text as mr_substitution_reason_text,
    mr.prior_prescription_display as mr_prior_prescription_display,
    
    -- Aggregated metadata (prefixes)
    mn.note_text_aggregated as mrn_note_text_aggregated,
    mrr.reason_code_text_aggregated as mrr_reason_code_text_aggregated,
    mrb.based_on_reference as mrb_care_plan_reference,
    mrb.based_on_display as mrb_care_plan_display,
    mf.form_coding_codes as mf_form_coding_codes,
    mf.form_coding_displays as mf_form_coding_displays,
    mi.ingredient_strengths as mi_ingredient_strengths,
    
    -- Care plan details (cp_ prefix)
    cp.id as cp_id,
    cp.title as cp_title,
    cp.status as cp_status,
    cp.intent as cp_intent,
    cp.created as cp_created,  -- ⭐ NEW: When care plan was created
    cp.period_start as cp_period_start,
    cp.period_end as cp_period_end,
    cp.author_display as cp_author_display,
    cpc.categories_aggregated as cpc_categories_aggregated,
    cpcon.addresses_aggregated as cpcon_addresses_aggregated,
    cpa.activity_detail_status as cpa_activity_detail_status
    
FROM fhir_prd_db.patient_medications pm

LEFT JOIN fhir_prd_db.medication_request mr
    ON pm.medication_request_id = mr.id

LEFT JOIN medication_notes mn
    ON pm.medication_request_id = mn.medication_request_id

LEFT JOIN medication_reasons mrr
    ON pm.medication_request_id = mrr.medication_request_id

LEFT JOIN fhir_prd_db.medication_request_based_on mrb
    ON pm.medication_request_id = mrb.medication_request_id

LEFT JOIN medication_forms mf
    ON pm.medication_id = mf.medication_id

LEFT JOIN medication_ingredients mi
    ON pm.medication_id = mi.medication_id

LEFT JOIN fhir_prd_db.care_plan cp
    ON mrb.based_on_reference = cp.id

LEFT JOIN care_plan_categories cpc
    ON cp.id = cpc.care_plan_id

LEFT JOIN care_plan_conditions cpcon
    ON cp.id = cpcon.care_plan_id

LEFT JOIN fhir_prd_db.care_plan_activity cpa
    ON cp.id = cpa.care_plan_id

ORDER BY pm.authored_on DESC, pm.medication_name;
```

---

## 2. Procedures Extraction

### Output File: `procedures.csv`

### Source Tables (7 tables with JOINs)

1. **procedure** (`proc_` prefix) - Main procedure table
2. **procedure_code_coding** (`pcc_` prefix) - CPT/HCPCS codes
3. **procedure_category_coding** (`pcat_` prefix) - Procedure categories
4. **procedure_body_site** (`pbs_` prefix) - Anatomical body sites
5. **procedure_performer** (`pp_` prefix) - Performers (surgeons, providers)
6. **procedure_reason_code** (`prc_` prefix) - Reasons/indications
7. **procedure_report** (`ppr_` prefix) - Procedure reports

### Column Mapping (34 columns) ⭐ UPDATED (exact count)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| procedure_fhir_id | procedure | id | Procedure FHIR ID (primary key) |
| proc_status | procedure | status | Procedure status |
| proc_performed_date_time | procedure | performed_date_time | When procedure occurred |
| proc_performed_period_start | procedure | performed_period_start | Procedure period start |
| proc_performed_period_end | procedure | performed_period_end | Procedure period end |
| proc_performed_string | procedure | performed_string | Performed string value |
| proc_performed_age_value | procedure | performed_age_value | Age at procedure (value) |
| proc_performed_age_unit | procedure | performed_age_unit | Age unit |
| proc_code_text | procedure | code_text | Procedure code text |
| proc_category_text | procedure | category_text | Category text |
| proc_subject_reference | procedure | subject_reference | Patient reference |
| proc_encounter_reference | procedure | encounter_reference | Encounter reference |
| proc_encounter_display | procedure | encounter_display | Encounter display |
| proc_location_reference | procedure | location_reference | Location reference |
| proc_location_display | procedure | location_display | Location display |
| proc_outcome_text | procedure | outcome_text | Procedure outcome |
| proc_recorder_reference | procedure | recorder_reference | Recorder reference |
| proc_recorder_display | procedure | recorder_display | Recorder display |
| proc_asserter_reference | procedure | asserter_reference | Asserter reference |
| proc_asserter_display | procedure | asserter_display | Asserter display |
| proc_status_reason_text | procedure | status_reason_text | Status reason |
| pcc_code_coding_system | procedure_code_coding | code_coding_system | Code system (CPT, HCPCS) |
| pcc_code_coding_code | procedure_code_coding | code_coding_code | CPT/HCPCS code (aggregated) |
| pcc_code_coding_display | procedure_code_coding | code_coding_display | Code display (aggregated) |
| pcat_category_coding_display | procedure_category_coding | category_coding_display | Category display (aggregated) |
| pbs_body_site_text | procedure_body_site | body_site_text | Body site (aggregated) |
| pp_performer_actor_display | procedure_performer | performer_actor_display | Performer name (aggregated) |
| pp_performer_function_text | procedure_performer | performer_function_text | Performer function (aggregated) |
| prc_reason_code_text | procedure_reason_code | reason_code_text | Reason text (aggregated) |
| ppr_report_reference | procedure_report | report_reference | Report reference (aggregated) |
| ppr_report_display | procedure_report | report_display | Report display (aggregated) |

### Athena View Definition

```sql
-- Create view: procedures_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.procedures_view WHERE proc_subject_reference = 'Patient/{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.procedures_view AS
WITH procedure_codes_agg AS (
    SELECT 
        procedure_id,
        LISTAGG(DISTINCT code_coding_system, ' | ') WITHIN GROUP (ORDER BY code_coding_system) as code_coding_systems,
        LISTAGG(DISTINCT code_coding_code, ' | ') WITHIN GROUP (ORDER BY code_coding_code) as code_coding_codes,
        LISTAGG(DISTINCT code_coding_display, ' | ') WITHIN GROUP (ORDER BY code_coding_display) as code_coding_displays
    FROM fhir_prd_db.procedure_code_coding
    GROUP BY procedure_id
),
procedure_categories_agg AS (
    SELECT 
        procedure_id,
        LISTAGG(DISTINCT category_coding_display, ' | ') WITHIN GROUP (ORDER BY category_coding_display) as category_coding_displays
    FROM fhir_prd_db.procedure_category_coding
    GROUP BY procedure_id
),
procedure_body_sites_agg AS (
    SELECT 
        procedure_id,
        LISTAGG(DISTINCT body_site_text, ' | ') WITHIN GROUP (ORDER BY body_site_text) as body_site_texts
    FROM fhir_prd_db.procedure_body_site
    GROUP BY procedure_id
),
procedure_performers_agg AS (
    SELECT 
        procedure_id,
        LISTAGG(DISTINCT performer_actor_display, ' | ') WITHIN GROUP (ORDER BY performer_actor_display) as performer_actor_displays,
        LISTAGG(DISTINCT performer_function_text, ' | ') WITHIN GROUP (ORDER BY performer_function_text) as performer_function_texts
    FROM fhir_prd_db.procedure_performer
    GROUP BY procedure_id
),
procedure_reasons_agg AS (
    SELECT 
        procedure_id,
        LISTAGG(DISTINCT reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_texts
    FROM fhir_prd_db.procedure_reason_code
    GROUP BY procedure_id
),
procedure_reports_agg AS (
    SELECT 
        procedure_id,
        LISTAGG(DISTINCT report_reference, ' | ') WITHIN GROUP (ORDER BY report_reference) as report_references,
        LISTAGG(DISTINCT report_display, ' | ') WITHIN GROUP (ORDER BY report_display) as report_displays
    FROM fhir_prd_db.procedure_report
    GROUP BY procedure_id
)

SELECT 
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
    
    -- Aggregated codes (pcc_ prefix)
    pcc.code_coding_systems as pcc_code_coding_system,
    pcc.code_coding_codes as pcc_code_coding_code,
    pcc.code_coding_displays as pcc_code_coding_display,
    
    -- Aggregated categories (pcat_ prefix)
    pcat.category_coding_displays as pcat_category_coding_display,
    
    -- Aggregated body sites (pbs_ prefix)
    pbs.body_site_texts as pbs_body_site_text,
    
    -- Aggregated performers (pp_ prefix)
    pp.performer_actor_displays as pp_performer_actor_display,
    pp.performer_function_texts as pp_performer_function_text,
    
    -- Aggregated reasons (prc_ prefix)
    prc.reason_code_texts as prc_reason_code_text,
    
    -- Aggregated reports (ppr_ prefix)
    ppr.report_references as ppr_report_reference,
    ppr.report_displays as ppr_report_display
    
FROM fhir_prd_db.procedure p

LEFT JOIN procedure_codes_agg pcc ON p.id = pcc.procedure_id
LEFT JOIN procedure_categories_agg pcat ON p.id = pcat.procedure_id
LEFT JOIN procedure_body_sites_agg pbs ON p.id = pbs.procedure_id
LEFT JOIN procedure_performers_agg pp ON p.id = pp.procedure_id
LEFT JOIN procedure_reasons_agg prc ON p.id = prc.procedure_id
LEFT JOIN procedure_reports_agg ppr ON p.id = ppr.procedure_id

ORDER BY p.performed_date_time DESC;
```

---

## 3. Measurements Extraction

### Output File: `measurements.csv`

### Source Tables (3 tables with UNION)

1. **observation** (`obs_` prefix) - Anthropometric measurements, vitals
2. **lab_tests** (`lt_` prefix) - Laboratory test metadata
3. **lab_test_results** (`ltr_` prefix) - Laboratory result values

### Column Mapping (30 columns) ⭐ UPDATED (exact count)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| patient_id | observation / lab_tests | subject_reference / patient_id | Patient identifier |
| obs_observation_id | observation | id | Observation ID |
| obs_measurement_type | observation | code_text | Measurement type |
| obs_measurement_value | observation | value_quantity_value | Measurement value |
| obs_measurement_unit | observation | value_quantity_unit | Measurement unit |
| obs_measurement_date | observation | effective_datetime | Measurement date |
| obs_issued | observation | issued | When observation was issued |
| obs_status | observation | status | Observation status |
| obs_encounter_reference | observation | encounter_reference | Encounter reference |
| lt_test_id | lab_tests | test_id | Lab test ID |
| lt_measurement_type | lab_tests | lab_test_name | Lab test name |
| lt_measurement_date | lab_tests | result_datetime | Result date |
| lt_status | lab_tests | lab_test_status | Lab test status |
| lt_result_diagnostic_report_id | lab_tests | result_diagnostic_report_id | Report ID |
| lt_lab_test_requester | lab_tests | lab_test_requester | Requesting provider |
| ltr_test_component | lab_test_results | test_component | Test component |
| ltr_value_string | lab_test_results | value_string | String value |
| ltr_measurement_value | lab_test_results | value_quantity_value | Numeric value |
| ltr_measurement_unit | lab_test_results | value_quantity_unit | Value unit |
| ltr_value_codeable_concept_text | lab_test_results | value_codeable_concept_text | Codeable concept |
| ltr_value_range_low_value | lab_test_results | value_range_low_value | Reference range low |
| ltr_value_range_low_unit | lab_test_results | value_range_low_unit | Low unit |
| ltr_value_range_high_value | lab_test_results | value_range_high_value | Reference range high |
| ltr_value_range_high_unit | lab_test_results | value_range_high_unit | High unit |
| ltr_value_boolean | lab_test_results | value_boolean | Boolean value |
| ltr_value_integer | lab_test_results | value_integer | Integer value |
| source_table | N/A | 'observation' or 'lab_tests' | Data source indicator |

### Athena View Definition

```sql
-- Create view: measurements_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.measurements_view WHERE patient_id = '{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.measurements_view AS

-- Anthropometric observations
SELECT 
    subject_reference as patient_id,
    id as obs_observation_id,
    code_text as obs_measurement_type,
    value_quantity_value as obs_measurement_value,
    value_quantity_unit as obs_measurement_unit,
    effective_datetime as obs_measurement_date,
    issued as obs_issued,
    status as obs_status,
    encounter_reference as obs_encounter_reference,
    NULL as lt_test_id,
    NULL as lt_measurement_type,
    NULL as lt_measurement_date,
    NULL as lt_status,
    NULL as lt_result_diagnostic_report_id,
    NULL as lt_lab_test_requester,
    NULL as ltr_test_component,
    NULL as ltr_value_string,
    NULL as ltr_measurement_value,
    NULL as ltr_measurement_unit,
    NULL as ltr_value_codeable_concept_text,
    NULL as ltr_value_range_low_value,
    NULL as ltr_value_range_low_unit,
    NULL as ltr_value_range_high_value,
    NULL as ltr_value_range_high_unit,
    NULL as ltr_value_boolean,
    NULL as ltr_value_integer,
    'observation' as source_table
FROM fhir_prd_db.observation
WHERE status = 'final'
AND (
    LOWER(code_text) LIKE '%height%'
    OR LOWER(code_text) LIKE '%length%'
    OR (LOWER(code_text) LIKE '%weight%' 
        AND LOWER(code_text) NOT LIKE '%birth%'
        AND LOWER(code_text) NOT LIKE '%discharge%')
    OR LOWER(code_text) LIKE '%head circumference%'
    OR LOWER(code_text) LIKE '%head circ%'
    OR LOWER(code_text) LIKE '%ofc%'
)

UNION ALL

-- Laboratory tests with results
SELECT 
    lt.patient_id,
    NULL as obs_observation_id,
    NULL as obs_measurement_type,
    NULL as obs_measurement_value,
    NULL as obs_measurement_unit,
    NULL as obs_measurement_date,
    NULL as obs_issued,
    NULL as obs_status,
    NULL as obs_encounter_reference,
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
    ltr.value_integer as ltr_value_integer,
    'lab_tests' as source_table
FROM fhir_prd_db.lab_tests lt
LEFT JOIN fhir_prd_db.lab_test_results ltr ON lt.test_id = ltr.test_id

ORDER BY 
    COALESCE(obs_measurement_date, lt_measurement_date) DESC;
```

---

## 4. Binary Files Extraction

### Output File: `binary_files.csv`

### Source Tables (5 tables with LEFT JOINs)

1. **document_reference** (`dr_` prefix) - Main document table
2. **document_reference_content** (`dc_` prefix) - Binary content details
3. **document_reference_context_encounter** (`de_` prefix) - Encounter linkages
4. **document_reference_type_coding** (`dt_` prefix) - Type coding
5. **document_reference_category** (`dcat_` prefix) - Document categories

### Column Mapping (26 columns)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| dr_id | document_reference | id | Document reference ID |
| dr_type_text | document_reference | type_text | Document type text |
| dr_date | document_reference | date | Document date |
| dr_description | document_reference | description | Document description |
| dr_status | document_reference | status | Document status |
| dr_doc_status | document_reference | doc_status | Doc status |
| dc_binary_url | document_reference_content | content_attachment_url | Binary URL (Binary/{id}) |
| dc_binary_id | document_reference_content | content_attachment_url | Cleaned Binary ID |
| dc_content_type | document_reference_content | content_attachment_content_type | Content type (MIME) |
| dc_content_size_bytes | document_reference_content | content_attachment_size | File size in bytes |
| dc_content_title | document_reference_content | content_attachment_title | Content title |
| dc_content_format | document_reference_content | content_format_display | Content format |
| de_encounter_reference | document_reference_context_encounter | context_encounter_reference | Encounter reference |
| de_encounter_display | document_reference_context_encounter | context_encounter_display | Encounter display |
| dt_type_coding_system | document_reference_type_coding | type_coding_system | Type coding system |
| dt_type_coding_code | document_reference_type_coding | type_coding_code | Type coding code |
| dt_type_coding_display | document_reference_type_coding | type_coding_display | Type coding display |
| dcat_category_text | document_reference_category | category_text | Category text |
| dr_context_period_start | document_reference | context_period_start | Context period start |
| dr_context_period_end | document_reference | context_period_end | Context period end |
| dr_context_facility_type_text | document_reference | context_facility_type_text | Facility type |
| dr_context_practice_setting_text | document_reference | context_practice_setting_text | Practice setting |
| dr_authenticator_display | document_reference | authenticator_display | Authenticator |
| dr_custodian_display | document_reference | custodian_display | Custodian |

### Athena View Definition

```sql
-- Create view: binary_files_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.binary_files_view WHERE dr_subject_reference = 'Patient/{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.binary_files_view AS
SELECT 
    -- Document Reference fields (dr_ prefix)
    dr.id as dr_id,
    dr.subject_reference as dr_subject_reference,
    dr.type_text as dr_type_text,
    dr.date as dr_date,
    dr.description as dr_description,
    dr.status as dr_status,
    dr.doc_status as dr_doc_status,
    
    -- Binary Content fields (dc_ prefix)
    dc.content_attachment_url as dc_binary_url,
    REPLACE(dc.content_attachment_url, 'Binary/', '') as dc_binary_id,
    dc.content_attachment_content_type as dc_content_type,
    dc.content_attachment_size as dc_content_size_bytes,
    dc.content_attachment_title as dc_content_title,
    dc.content_format_display as dc_content_format,
    
    -- Encounter Reference fields (de_ prefix)
    de.context_encounter_reference as de_encounter_reference,
    de.context_encounter_display as de_encounter_display,
    
    -- Type Coding fields (dt_ prefix)
    dt.type_coding_system as dt_type_coding_system,
    dt.type_coding_code as dt_type_coding_code,
    dt.type_coding_display as dt_type_coding_display,
    
    -- Category fields (dcat_ prefix)
    dcat.category_text as dcat_category_text,
    
    -- Context Period fields (dr_ prefix)
    dr.context_period_start as dr_context_period_start,
    dr.context_period_end as dr_context_period_end,
    dr.context_facility_type_text as dr_context_facility_type_text,
    dr.context_practice_setting_text as dr_context_practice_setting_text,
    
    -- Authenticator/Custodian fields (dr_ prefix)
    dr.authenticator_display as dr_authenticator_display,
    dr.custodian_display as dr_custodian_display
    
FROM fhir_prd_db.document_reference dr

LEFT JOIN fhir_prd_db.document_reference_content dc
    ON dr.id = dc.document_reference_id

LEFT JOIN fhir_prd_db.document_reference_context_encounter de
    ON dr.id = de.document_reference_id

LEFT JOIN fhir_prd_db.document_reference_type_coding dt
    ON dr.id = dt.document_reference_id

LEFT JOIN fhir_prd_db.document_reference_category dcat
    ON dr.id = dcat.document_reference_id

ORDER BY dr.date DESC;
```

---

## 5. Imaging Extraction

### Output File: `imaging.csv`

### Source Tables (Materialized Views + diagnostic_report)

1. **radiology_imaging_mri** (no prefix) - MRI studies
2. **radiology_imaging_mri_results** (no prefix) - MRI result narratives
3. **radiology_imaging** (no prefix) - Other imaging modalities
4. **diagnostic_report** (report_ prefix for joined fields) - Report metadata
5. **diagnostic_report_category** (via CTE) - Report categories

### Column Mapping (18 columns) ⭐ UPDATED (+patient_mrn convenience field)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| patient_id | radiology_imaging_mri / radiology_imaging | patient_id | Patient FHIR ID |
| imaging_procedure_id | radiology_imaging_mri / radiology_imaging | imaging_procedure_id | Imaging procedure ID |
| imaging_date | radiology_imaging_mri / radiology_imaging | result_datetime | When imaging occurred |
| imaging_procedure | radiology_imaging_mri / radiology_imaging | imaging_procedure | Procedure description |
| result_diagnostic_report_id | radiology_imaging_mri / radiology_imaging | result_diagnostic_report_id | Report ID |
| imaging_modality | N/A | 'MRI' or from imaging_procedure | Imaging modality |
| result_information | radiology_imaging_mri_results | result_information | Result narrative |
| result_display | radiology_imaging_mri_results | result_display | Result display |
| diagnostic_report_id | diagnostic_report | id | Report ID (for JOIN) |
| report_status | diagnostic_report | status | Report status |
| category_text | diagnostic_report_category | category_text | Report category (aggregated) |
| report_issued | diagnostic_report | issued | When report was issued |
| report_effective_period_start | diagnostic_report | effective_period_start | Report period start |
| report_effective_period_stop | diagnostic_report | effective_period_stop | Report period end |
| report_conclusion | diagnostic_report | conclusion | Report conclusion |
| **patient_mrn** | **patient (via JOIN)** | **mrn** | **Patient MRN (convenience field)** ⭐ **NEW** |

### Athena View Definition

```sql
-- Create view: imaging_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.imaging_view WHERE patient_id = '{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.imaging_view AS
WITH report_categories AS (
    SELECT 
        diagnostic_report_id,
        LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as category_text
    FROM fhir_prd_db.diagnostic_report_category
    GROUP BY diagnostic_report_id
),
mri_with_results AS (
    SELECT 
        mri.patient_id,
        mri.imaging_procedure_id,
        mri.result_datetime as imaging_date,
        mri.imaging_procedure,
        mri.result_diagnostic_report_id,
        'MRI' as imaging_modality,
        results.result_information,
        results.result_display
    FROM fhir_prd_db.radiology_imaging_mri mri
    LEFT JOIN fhir_prd_db.radiology_imaging_mri_results results
        ON mri.imaging_procedure_id = results.imaging_procedure_id
),
other_imaging AS (
    SELECT 
        patient_id,
        imaging_procedure_id,
        result_datetime as imaging_date,
        imaging_procedure,
        result_diagnostic_report_id,
        COALESCE(imaging_procedure, 'Unknown') as imaging_modality,
        NULL as result_information,
        NULL as result_display
    FROM fhir_prd_db.radiology_imaging
)

SELECT 
    combined.patient_id,
    combined.imaging_procedure_id,
    combined.imaging_date,
    combined.imaging_procedure,
    combined.result_diagnostic_report_id,
    combined.imaging_modality,
    combined.result_information,
    combined.result_display,
    dr.id as diagnostic_report_id,
    dr.status as report_status,
    rc.category_text,
    dr.issued as report_issued,
    dr.effective_period_start as report_effective_period_start,
    dr.effective_period_stop as report_effective_period_stop,
    dr.conclusion as report_conclusion
FROM (
    SELECT * FROM mri_with_results
    UNION ALL
    SELECT * FROM other_imaging
) combined

LEFT JOIN fhir_prd_db.diagnostic_report dr
    ON combined.result_diagnostic_report_id = dr.id

LEFT JOIN report_categories rc
    ON dr.id = rc.diagnostic_report_id

ORDER BY combined.imaging_date DESC;
```

---

## 6. Appointments Extraction

### Output File: `appointments.csv`

### Source Tables (2 tables with JOIN)

1. **appointment** (`appt_` prefix) - Appointment details
2. **appointment_participant** (`ap_` prefix) - Participant information

### Column Mapping (21 columns) ⭐ UPDATED (+6 participant fields)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| appointment_fhir_id | appointment | id | Appointment FHIR ID |
| appt_id | appointment | id | Appointment ID |
| appt_status | appointment | status | Appointment status |
| appt_appointment_type_text | appointment | appointment_type_text | Appointment type |
| appt_description | appointment | description | Appointment description |
| appt_start | appointment | start | Appointment start time |
| appt_end | appointment | end | Appointment end time |
| appt_minutes_duration | appointment | minutes_duration | Duration in minutes |
| appt_created | appointment | created | When appointment was created |
| appt_comment | appointment | comment | Appointment comment |
| appt_patient_instruction | appointment | patient_instruction | Patient instructions |
| appt_cancelation_reason_text | appointment | cancelation_reason_text | Cancellation reason |
| appt_priority | appointment | priority | Appointment priority |
| **ap_participant_actor_reference** | **appointment_participant** | **participant_actor_reference** | **Participant reference** ⭐ **NEW** |
| **ap_participant_actor_type** | **appointment_participant** | **participant_actor_type** | **Participant actor type** ⭐ **NEW** |
| **ap_participant_required** | **appointment_participant** | **participant_required** | **Participant required flag** ⭐ **NEW** |
| **ap_participant_status** | **appointment_participant** | **participant_status** | **Participant status** ⭐ **NEW** |
| **ap_participant_period_start** | **appointment_participant** | **participant_period_start** | **Participant period start** ⭐ **NEW** |
| **ap_participant_period_end** | **appointment_participant** | **participant_period_end** | **Participant period end** ⭐ **NEW** |

### Athena View Definition

```sql
-- Create view: appointments_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.appointments_view WHERE ap_participant_actor_reference LIKE 'Patient/{fhir_id}%'

CREATE OR REPLACE VIEW fhir_prd_db.appointments_view AS
SELECT DISTINCT
    a.id as appointment_fhir_id,
    
    -- Appointment fields (appt_ prefix)
    a.id as appt_id,
    a.status as appt_status,
    a.appointment_type_text as appt_appointment_type_text,
    a.description as appt_description,
    a.start as appt_start,
    a.end as appt_end,
    a.minutes_duration as appt_minutes_duration,
    a.created as appt_created,
    a.comment as appt_comment,
    a.patient_instruction as appt_patient_instruction,
    a.cancelation_reason_text as appt_cancelation_reason_text,
    a.priority as appt_priority,
    
    -- Participant fields (ap_ prefix)
    ap.participant_actor_reference as ap_participant_actor_reference,
    ap.participant_actor_type as ap_participant_actor_type,
    ap.participant_required as ap_participant_required,
    ap.participant_status as ap_participant_status,
    ap.participant_period_start as ap_participant_period_start,
    ap.participant_period_end as ap_participant_period_end

FROM fhir_prd_db.appointment a

INNER JOIN fhir_prd_db.appointment_participant ap 
    ON a.id = ap.appointment_id

ORDER BY a.start DESC;
```

---

## 7. Encounters Extraction

### Output File: `encounters.csv`

### Source Tables (6 tables)

1. **encounter** (no prefix) - Main encounter table
2. **encounter_type** - Encounter type subtable
3. **encounter_reason_code** - Encounter reason codes
4. **encounter_diagnosis** - Encounter diagnosis linkages
5. **encounter_appointment** - Encounter-appointment linkages

**Note**: Encounters CSV uses minimal prefixes since the main `encounter` table fields are unambiguous.

### Column Mapping (26 columns from main table)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| encounter_fhir_id | encounter | id | Encounter FHIR ID |
| encounter_date | encounter | period_start | Encounter date (extracted) |
| age_at_encounter_days | N/A | calculated | Age in days at encounter |
| status | encounter | status | Encounter status |
| class_code | encounter | class_code | Encounter class code |
| class_display | encounter | class_display | Encounter class display |
| service_type_text | encounter | service_type_text | Service type |
| priority_text | encounter | priority_text | Priority |
| period_start | encounter | period_start | Period start |
| period_end | encounter | period_end | Period end |
| length_value | encounter | length_value | Length value |
| length_unit | encounter | length_unit | Length unit |
| service_provider_display | encounter | service_provider_display | Service provider |
| part_of_reference | encounter | part_of_reference | Parent encounter reference |

### Athena View Definition

```sql
-- Create view: encounters_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.encounters_view WHERE subject_reference = 'Patient/{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.encounters_view AS
WITH encounter_types_agg AS (
    SELECT 
        encounter_id,
        LISTAGG(DISTINCT type_text, ' | ') WITHIN GROUP (ORDER BY type_text) as type_texts
    FROM fhir_prd_db.encounter_type
    GROUP BY encounter_id
),
encounter_reasons_agg AS (
    SELECT 
        encounter_id,
        LISTAGG(DISTINCT reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_texts
    FROM fhir_prd_db.encounter_reason_code
    GROUP BY encounter_id
),
encounter_diagnoses_agg AS (
    SELECT 
        encounter_id,
        LISTAGG(DISTINCT diagnosis_condition_display, ' | ') WITHIN GROUP (ORDER BY diagnosis_condition_display) as diagnosis_displays
    FROM fhir_prd_db.encounter_diagnosis
    GROUP BY encounter_id
)

SELECT 
    e.id as encounter_fhir_id,
    e.subject_reference,
    CAST(e.period_start AS DATE) as encounter_date,
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
    
    -- Aggregated subtables
    et.type_texts as encounter_types,
    er.reason_code_texts as encounter_reasons,
    ed.diagnosis_displays as encounter_diagnoses

FROM fhir_prd_db.encounter e

LEFT JOIN encounter_types_agg et ON e.id = et.encounter_id
LEFT JOIN encounter_reasons_agg er ON e.id = er.encounter_id
LEFT JOIN encounter_diagnoses_agg ed ON e.id = ed.encounter_id

ORDER BY e.period_start DESC;
```

---

## Usage Examples

### Query Individual Views

```sql
-- Medications for specific patient
SELECT * FROM fhir_prd_db.medications_view 
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Procedures for specific patient  
SELECT * FROM fhir_prd_db.procedures_view 
WHERE proc_subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Measurements for specific patient
SELECT * FROM fhir_prd_db.measurements_view 
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Binary files for specific patient
SELECT * FROM fhir_prd_db.binary_files_view 
WHERE dr_subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Imaging for specific patient
SELECT * FROM fhir_prd_db.imaging_view 
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Appointments for specific patient (use LIKE for flexible matching)
SELECT * FROM fhir_prd_db.appointments_view 
WHERE ap_participant_actor_reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%';

-- Encounters for specific patient
SELECT * FROM fhir_prd_db.encounters_view 
WHERE subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Diagnoses for specific patient ⭐ NEW
SELECT * FROM fhir_prd_db.diagnoses_view 
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
```

### Export View Results to S3 (Athena UNLOAD)

```sql
-- Export medications view to S3
UNLOAD (
    SELECT * FROM fhir_prd_db.medications_view 
    WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
)
TO 's3://your-bucket/medications/'
WITH (format = 'TEXTFILE', field_delimiter = ',', compression = 'GZIP');
```

---

## Notes

### Important Considerations

1. **Patient Reference Formats**:
   - Some tables use `Patient/{fhir_id}` format (medication_request, procedure, encounter)
   - Some tables use bare FHIR ID (observation, lab_tests, imaging views)
   - Adjust WHERE clauses accordingly

2. **Performance**:
   - Views use CTEs with LISTAGG for aggregation (can be slow for large datasets)
   - Consider materializing views for frequently-accessed patient cohorts
   - Add indexes on subject_reference, patient_id fields if performance is critical

3. **Null Handling**:
   - LEFT JOINs preserve all records from main table even if subtables have no data
   - Aggregated fields will be NULL if no child records exist
   - Scripts handle this with pandas fillna() operations

4. **Date Fields**:
   - All date fields validated against actual schemas (see DATE_FIELDS_VALIDATION.md)
   - Some date fields don't exist (e.g., mr.created, dr.indexed - removed)
   - Field names vary (effective_period_stop vs _end)

5. **Athena Limitations**:
   - Cannot use explicit column aliasing (SELECT col as alias) with JOINs in some contexts
   - Nested subqueries with functions can fail
   - Use CTEs (WITH clauses) for complex aggregations
   - Scripts use SELECT * then rename in pandas when needed

6. **Database Differences**:
   - `fhir_v2_prd_db` vs `fhir_prd_db` have same schema structure
   - Views above use `fhir_prd_db` as requested
   - Scripts use `fhir_v2_prd_db` by default (configurable via patient_config.json)

---

---

## 8. Diagnoses Extraction ⭐ NEW SECTION

### Output File: `diagnoses.csv`

### Source Tables (1 table - single source)

1. **problem_list_diagnoses** (no prefix) - Problem list diagnoses with ICD-10 and SNOMED codes

**Note**: This extraction uses the `problem_list_diagnoses` materialized view which consolidates data from:
- `condition` table (main diagnosis table)
- `condition_code_coding` table (ICD-10 and SNOMED codes)
- Patient demographic data for age calculations

### Column Mapping (17 columns)

| Output Column | Source Table | Source Column | Description |
|---------------|--------------|---------------|-------------|
| patient_id | problem_list_diagnoses | patient_id | Patient FHIR ID |
| condition_id | problem_list_diagnoses | condition_id | Condition/diagnosis FHIR ID |
| diagnosis_name | problem_list_diagnoses | diagnosis_name | Human-readable diagnosis name |
| clinical_status_text | problem_list_diagnoses | clinical_status_text | Clinical status (Active, Resolved, Inactive) |
| onset_date_time | problem_list_diagnoses | onset_date_time | When diagnosis began |
| abatement_date_time | problem_list_diagnoses | abatement_date_time | When diagnosis resolved |
| recorded_date | problem_list_diagnoses | recorded_date | When diagnosis was recorded in system |
| icd10_code | problem_list_diagnoses | icd10_code | ICD-10 diagnosis code |
| icd10_display | problem_list_diagnoses | icd10_display | ICD-10 code description |
| snomed_code | problem_list_diagnoses | snomed_code | SNOMED CT code |
| snomed_display | problem_list_diagnoses | snomed_display | SNOMED CT description |
| age_at_onset_days | N/A | calculated | Age in days at diagnosis onset |
| age_at_onset_years | N/A | calculated | Age in years at diagnosis onset |
| age_at_abatement_days | N/A | calculated | Age in days at diagnosis resolution |
| age_at_abatement_years | N/A | calculated | Age in years at diagnosis resolution |
| age_at_recorded_days | N/A | calculated | Age in days when diagnosis was recorded |
| age_at_recorded_years | N/A | calculated | Age in years when diagnosis was recorded |

### Athena View Definition

```sql
-- Create view: diagnoses_view
-- Database: fhir_prd_db
-- Usage: SELECT * FROM fhir_prd_db.diagnoses_view WHERE patient_id = '{fhir_id}'

CREATE OR REPLACE VIEW fhir_prd_db.diagnoses_view AS
SELECT 
    patient_id,
    condition_id,
    diagnosis_name,
    clinical_status_text,
    onset_date_time,
    abatement_date_time,
    recorded_date,
    icd10_code,
    icd10_display,
    snomed_code,
    snomed_display
FROM problem_list_diagnoses
ORDER BY recorded_date DESC, onset_date_time DESC;
```

**Note**: Age calculations are performed in the Python extraction script using the patient's birth date from `patient_config.json`. These are not included in the Athena view as they require patient-specific context.

---

## Changelog

- **2025-10-12**: Initial creation with all 7 extraction scripts documented
- **2025-10-12**: Added complete prefix definitions and Athena view SQL for all scripts
- **2025-10-12**: Documented column mappings with source tables and descriptions
- **2025-10-12 (v2.0)**: ⭐ **COMPREHENSIVE UPDATE**
  - Updated medications.csv: 44 → 45 columns (added `cp_created`)
  - Updated appointments.csv: 15 → 21 columns (added 6 `ap_participant_*` fields)
  - Updated imaging.csv: 17 → 18 columns (documented `patient_mrn`)
  - Updated procedures.csv: ~40 → 34 exact column count
  - Updated measurements.csv: ~28 → 30 exact column count
  - **NEW**: Added complete diagnoses.csv section (17 columns)
  - All Athena views updated to match current extraction scripts
  - All column counts verified against actual CSV outputs
