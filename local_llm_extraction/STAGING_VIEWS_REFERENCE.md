# Athena Staging Views and Materialized Views Reference

## Overview

This document provides a comprehensive reference for all Athena staging views and materialized views used in the RADIANT PCA extraction pipeline. These views are the foundation for both structured data extraction (Phase 1) and LLM-based extraction validation (Phases 2-4).

**Configuration Source**: [staging_views_config.py](form_extractors/staging_views_config.py)

---

## 10 Core Staging Views

### 1. **procedures**
**Description**: All procedures including surgeries, biopsies, and interventions

**Primary Key**: `procedure_id`

**Date Columns**:
- `proc_performed_date_time`
- `procedure_date`

**Key Columns**:
- `procedure_id`
- `proc_code`
- `proc_code_text`
- `is_surgical_keyword`

**Extraction Relevance**:
- `extent_of_resection`: PRIMARY
- `surgery_date`: PRIMARY
- `surgery_type`: PRIMARY
- `complications`: SECONDARY

---

### 2. **diagnoses**
**Description**: ICD-10 diagnosis codes and clinical problems

**Primary Key**: `diagnosis_id`

**Date Columns**:
- `onset_date_time`
- `recorded_date`

**Key Columns**:
- `diagnosis_id`
- `icd10_code`
- `diagnosis_name`
- `status`

**Extraction Relevance**:
- `who_cns5_diagnosis`: PRIMARY
- `tumor_grade`: PRIMARY
- `metastasis`: PRIMARY
- `comorbidities`: SECONDARY

---

### 3. **medications**
**Description**: All medications including chemotherapy and supportive care

**Primary Key**: `medication_id`

**Date Columns**:
- `medication_start_date`
- `med_date_given_start`
- `med_date_given_end`

**Key Columns**:
- `medication_id`
- `medication_name`
- `rxnorm_code`
- `ingredient_rxnorm`
- `product_rxnorm`
- `is_chemotherapy`
- `dosage`
- `route`
- `frequency`

**Extraction Relevance**:
- `chemotherapy_drugs`: PRIMARY
- `concomitant_medications`: PRIMARY
- `steroid_use`: SECONDARY
- `anticonvulsants`: SECONDARY

---

### 4. **imaging**
**Description**: Imaging studies including MRI, CT, and PET scans

**Primary Key**: `imaging_id`

**Date Columns**:
- `imaging_date`
- `study_date`

**Key Columns**:
- `imaging_id`
- `modality`
- `body_site`
- `contrast`
- `findings`
- `impression`
- `is_postop_72hr`

**Extraction Relevance**:
- `extent_of_resection`: **CRITICAL** (Post-op imaging is gold standard)
- `tumor_location`: PRIMARY
- `tumor_size`: PRIMARY
- `progression`: PRIMARY
- `residual_tumor`: PRIMARY

**⚠️ CRITICAL NOTE**: The `findings` and `impression` fields contain **unstructured text** (not binary PDFs). These are structured fields with narrative radiology reports embedded in the CSV.

---

### 5. **measurements**
**Description**: Clinical measurements and tumor dimensions

**Primary Key**: `measurement_id`

**Date Columns**:
- `measurement_date`

**Key Columns**:
- `measurement_id`
- `measurement_name`
- `value_numeric`
- `unit`
- `reference_range`

**Extraction Relevance**:
- `tumor_volume`: PRIMARY
- `kps_score`: PRIMARY
- `lansky_score`: PRIMARY

---

### 6. **binary_files**
**Description**: References to binary documents in S3 (NOT the documents themselves)

**Primary Key**: `file_id`

**Date Columns**:
- `dr_date`
- `document_date`

**Key Columns**:
- `file_id`
- `file_name`
- `document_type`
- `s3_path`
- `file_size`
- `is_priority`

**Extraction Relevance**:
- ALL variables: SOURCE_DOCUMENTS

**Note**: This view is a metadata catalog. Actual document retrieval happens via S3 using the `s3_path`.

---

### 7. **encounters**
**Description**: Clinical encounters and visits

**Primary Key**: `encounter_id`

**Date Columns**:
- `encounter_date`
- `admit_date`
- `discharge_date`

**Key Columns**:
- `encounter_id`
- `encounter_type`
- `department`
- `provider_specialty`
- `chief_complaint`

**Extraction Relevance**:
- `hospitalization`: PRIMARY
- `follow_up`: SECONDARY

---

### 8. **appointments**
**Description**: Scheduled and completed appointments

**Primary Key**: `appointment_id`

**Date Columns**:
- `appointment_date`
- `scheduled_date`

**Key Columns**:
- `appointment_id`
- `appointment_type`
- `department`
- `provider`
- `status`

**Extraction Relevance**:
- `follow_up_schedule`: SECONDARY

---

### 9. **radiation_treatment_courses**
**Description**: Radiation therapy courses and parameters

**Primary Key**: `course_id`

**Date Columns**:
- `start_date`
- `end_date`

**Key Columns**:
- `course_id`
- `treatment_site`
- `total_dose_gy`
- `fractions`
- `technique`
- `intent`

**Extraction Relevance**:
- `radiation_therapy`: PRIMARY
- `radiation_dose`: PRIMARY
- `radiation_site`: PRIMARY
- `radiation_technique`: PRIMARY

---

### 10. **radiation_data_summary**
**Description**: Summarized radiation therapy data

**Primary Key**: `summary_id`

**Date Columns**:
- `treatment_date`

**Key Columns**:
- `summary_id`
- `site`
- `dose_per_fraction`
- `total_dose`
- `boost`
- `concurrent_chemo`

**Extraction Relevance**:
- `radiation_summary`: PRIMARY

---

## 5 Materialized Views

These are derived views that combine multiple staging tables to provide higher-level clinical context.

### 1. **surgery_events**
**Description**: Consolidated surgical events with classifications

**Source Tables**:
- `procedures`
- `encounters`
- `binary_files`

**Key Fields**:
- `surgery_date`
- `surgery_type`
- `extent_of_resection`
- `operative_note_id`
- `pathology_report_id`

**Extraction Relevance**:
- `extent_of_resection`: GOLD_STANDARD
- `surgery_classification`: PRIMARY

---

### 2. **chemotherapy_timeline**
**Description**: Longitudinal chemotherapy exposure timeline

**Source Tables**:
- `medications`
- `encounters`

**Key Fields**:
- `drug_name`
- `start_date`
- `end_date`
- `cumulative_dose`
- `line_of_therapy`
- `response`

**Extraction Relevance**:
- `chemotherapy_lines`: PRIMARY
- `treatment_response`: PRIMARY

---

### 3. **molecular_profile**
**Description**: Integrated molecular test results

**Source Tables**:
- `measurements`
- `binary_files`

**Key Fields**:
- `test_date`
- `test_type`
- `gene`
- `alteration`
- `variant_allele_frequency`
- `clinical_significance`

**Extraction Relevance**:
- `molecular_alterations`: PRIMARY
- `targeted_therapy_eligibility`: PRIMARY

**⚠️ CRITICAL NOTE**: Molecular test results can exist in:
1. **Structured fields** in measurements (e.g., `test_result_value`)
2. **Binary PDF reports** referenced in binary_files

The LLM must understand this distinction to avoid searching for non-existent binary files.

---

### 4. **clinical_timeline**
**Description**: Complete patient clinical timeline

**Source Tables**: ALL staging views

**Key Fields**:
- `event_date`
- `event_type`
- `event_category`
- `event_description`
- `source_document`

**Extraction Relevance**:
- ALL variables: CONTEXTUAL

**Note**: This is built by Phase 2 (timeline_builder) and provides temporal context for all extractions.

---

### 5. **imaging_progression**
**Description**: Imaging-based progression events

**Source Tables**:
- `imaging`
- `measurements`

**Key Fields**:
- `progression_date`
- `progression_type`
- `recist_criteria`
- `site_of_progression`
- `prior_baseline`

**Extraction Relevance**:
- `progression_date`: PRIMARY
- `progression_site`: PRIMARY
- `recurrence`: PRIMARY

---

## Query Functions for LLM

These are pre-defined query patterns that the LLM can use during extraction:

### QUERY_SURGERY_DATES
- **Description**: Get all surgery dates for patient
- **Returns**: `List[Dict[date, type, extent]]`
- **Source**: procedures
- **Filters**: `is_surgical_keyword = true`

### QUERY_DIAGNOSIS
- **Description**: Get primary diagnosis and date
- **Returns**: `Dict[diagnosis, icd10_code, date]`
- **Source**: diagnoses
- **Filters**: Brain tumor codes: C71, D43, D33

### QUERY_MEDICATIONS
- **Description**: Verify patient received specific medication
- **Parameters**: `drug_name`
- **Returns**: `List[Dict[medication, start_date, end_date]]`
- **Source**: medications

### QUERY_MOLECULAR_TESTS
- **Description**: Get molecular test results
- **Returns**: `List[Dict[test, date, result]]`
- **Source**: molecular_profile

### QUERY_IMAGING_ON_DATE
- **Description**: Get imaging near specific date
- **Parameters**: `date`, `tolerance_days`
- **Returns**: `List[Dict[study, findings, impression]]`
- **Source**: imaging

### QUERY_POSTOP_IMAGING ⚠️ CRITICAL
- **Description**: Get post-operative imaging within 72 hours
- **Parameters**: `surgery_date`
- **Returns**: `Dict[extent, residual, complications]`
- **Source**: imaging
- **Filters**: `is_postop_72hr = true`
- **Critical**: TRUE (This is the gold standard for extent of resection)

### QUERY_PROBLEM_LIST
- **Description**: Get active clinical problems
- **Returns**: `List[Dict[problem, status, onset_date]]`
- **Source**: diagnoses
- **Filters**: `status = active`

### QUERY_ENCOUNTERS_RANGE
- **Description**: Get encounters in date range
- **Parameters**: `start_date`, `end_date`
- **Returns**: `List[Dict[date, type, department]]`
- **Source**: encounters

### VERIFY_DATE_PROXIMITY
- **Description**: Check if dates are within tolerance
- **Parameters**: `date1`, `date2`, `tolerance_days`
- **Returns**: `bool`
- **Source**: COMPUTED

### QUERY_CHEMOTHERAPY_EXPOSURE
- **Description**: Check chemotherapy drugs received
- **Returns**: `List[Dict[drug, dates, line_of_therapy]]`
- **Source**: chemotherapy_timeline

### QUERY_RADIATION_DETAILS
- **Description**: Get radiation therapy details
- **Returns**: `Dict[site, dose, fractions, technique]`
- **Source**: radiation_treatment_courses

---

## Form-Specific Extraction Requirements

### diagnosis_form
**Required Views**: diagnoses, imaging, binary_files
**Required Queries**: QUERY_DIAGNOSIS, QUERY_MOLECULAR_TESTS
**Variables**: who_cns5_diagnosis, tumor_grade, tumor_location, metastasis, molecular_alterations

### treatment_form
**Required Views**: procedures, imaging, binary_files
**Required Queries**: QUERY_SURGERY_DATES, QUERY_POSTOP_IMAGING
**Critical Validation**: extent_of_resection
**Variables**: extent_of_resection, surgery_date, surgery_type, residual_tumor, complications

### chemotherapy_form
**Required Views**: medications, chemotherapy_timeline
**Required Queries**: QUERY_CHEMOTHERAPY_EXPOSURE, QUERY_MEDICATIONS
**Variables**: chemotherapy_drugs, start_date, end_date, best_response, toxicity

### radiation_form
**Required Views**: radiation_treatment_courses, radiation_data_summary
**Required Queries**: QUERY_RADIATION_DETAILS
**Variables**: radiation_site, total_dose, fractions, technique, concurrent_chemo

### demographics_form
**Required Views**: encounters, diagnoses
**Variables**: legal_sex, race, ethnicity, vital_status

### medical_history_form
**Required Views**: diagnoses, measurements, molecular_profile
**Required Queries**: QUERY_PROBLEM_LIST, QUERY_MOLECULAR_TESTS
**Variables**: family_history, cancer_predisposition, germline_testing, comorbidities

### concomitant_medications_form
**Required Views**: medications
**Required Queries**: QUERY_MEDICATIONS
**Variables**: medication_name, start_date, end_date, indication, route

### imaging_form
**Required Views**: imaging, imaging_progression, measurements
**Required Queries**: QUERY_IMAGING_ON_DATE
**Variables**: imaging_date, modality, tumor_size, progression_status, new_lesions

### outcome_form
**Required Views**: encounters, diagnoses, imaging_progression
**Variables**: vital_status, date_of_death, cause_of_death, progression_free_survival, overall_survival

---

## Critical Design Principles

### 1. Gold Standard Hierarchies
- **Post-op imaging (24-72h MRI)**: 0.95 confidence for extent of resection
- **Pathology reports**: 0.90 confidence for diagnosis
- **Operative notes**: 0.75 confidence (overridden by imaging)

### 2. Structured vs Binary Data
- Some views contain **unstructured text in structured fields** (imaging.findings, imaging.impression)
- Binary files are **references only** - actual documents retrieved from S3
- LLM must be explicitly told which data is in structured fields vs binary PDFs

### 3. Temporal Context
- All views have date columns for temporal alignment
- Clinical timeline provides sequential event context
- Post-op imaging must be within 24-72h of surgery to be gold standard

### 4. Multi-Source Validation
- Cross-validation required when sources conflict
- Higher confidence sources override lower confidence sources
- Manual review flagged when confidence < 0.60

---

## Usage in Multi-Agent Framework

For the multi-agent architecture, this configuration serves as:

1. **Master Agent (Claude)**: Uses staging view metadata to plan extraction strategy and validate MedGemma outputs
2. **Medical Agent (MedGemma)**: Uses view schemas to query structured data and understand available sources
3. **Dialogue Protocol**: Both agents reference this schema when discussing data source conflicts or validation needs

**Example Dialogue Scenario**:
```
Master: "For extent_of_resection, what is the gold standard source?"
Medical: "QUERY_POSTOP_IMAGING from imaging view (is_postop_72hr=true), confidence 0.95"
Master: "Operative note says GTR, but post-op MRI shows residual. Which should we use?"
Medical: "Post-op MRI (0.95) overrides operative note (0.75). Extraction: STR"
```

---

## File Locations

- **Configuration**: `/form_extractors/staging_views_config.py`
- **Structured Query Engine**: `/form_extractors/structured_data_query_engine.py`
- **Phase 1 Harvester**: `/event_based_extraction/phase1_enhanced_structured_harvester.py`
- **Pass 2 Structured Query**: `/iterative_extraction/pass2_structured_query.py`
