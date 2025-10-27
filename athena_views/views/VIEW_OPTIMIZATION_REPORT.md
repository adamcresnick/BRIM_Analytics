# Comprehensive View Optimization Report

**Date**: 2025-10-27
**Total Views**: 26

## Executive Summary

- Total optimization issues found: **10**
- Views using v_chemo_medications: **3**
- Views with hardcoded RxNorm codes: **6**

## Recommendations

### 1. [HIGH] Hardcoded RxNorm codes

**Views affected**: 6

- v_concomitant_medications
- v_autologous_stem_cell_transplant
- v_procedures_tumor
- v_autologous_stem_cell_collection
- v_imaging_corticosteroid_use
- v_ophthalmology_assessments

**Action**: Replace hardcoded RxNorm codes with v_chemotherapy_drugs reference

**Benefit**: Ensures consistency with comprehensive drug reference (2,968 drugs)

### 2. [LOW] Direct medication_request access

**Views affected**: 4

- v_chemo_medications
- v_hydrocephalus_procedures
- v_autologous_stem_cell_collection
- v_imaging_corticosteroid_use

**Action**: Consider using v_medications or v_chemo_medications for standardization

**Benefit**: Consistent date handling and RxNorm code matching

## Detailed View Analysis

### v_audiology_assessments

**Line count**: 39

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_autologous_stem_cell_collection

**Line count**: 347

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: True
- Has hardcoded RxNorm codes: True

**Issues**: HARDCODED_RXNORM_CODES, DIRECT_MEDICATION_REQUEST_ACCESS

### v_autologous_stem_cell_transplant

**Line count**: 214

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: True

**Issues**: HARDCODED_RXNORM_CODES

### v_binary_files

**Line count**: 80

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_chemo_medications

**Line count**: 451

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: True
- Has hardcoded RxNorm codes: False

**Issues**: DIRECT_MEDICATION_REQUEST_ACCESS

### v_concomitant_medications

**Line count**: 321

**Dependencies**:
- Uses v_chemo_medications: True
- Uses v_medications: False
- Uses medication_request directly: True
- Has hardcoded RxNorm codes: True

**Issues**: HARDCODED_RXNORM_CODES

### v_diagnoses

**Line count**: 39

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_encounters

**Line count**: 134

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_hydrocephalus_diagnosis

**Line count**: 245

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_hydrocephalus_procedures

**Line count**: 403

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: True
- Has hardcoded RxNorm codes: False

**Issues**: DIRECT_MEDICATION_REQUEST_ACCESS

### v_imaging

**Line count**: 96

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_imaging_corticosteroid_use

**Line count**: 397

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: True
- Has hardcoded RxNorm codes: True

**Issues**: HARDCODED_RXNORM_CODES, DIRECT_MEDICATION_REQUEST_ACCESS

### v_measurements

**Line count**: 124

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_medications

**Line count**: 294

**Dependencies**:
- Uses v_chemo_medications: True
- Uses v_medications: False
- Uses medication_request directly: True
- Has hardcoded RxNorm codes: False

### v_molecular_tests

**Line count**: 94

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_ophthalmology_assessments

**Line count**: 13

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: True

**Issues**: HARDCODED_RXNORM_CODES

### v_patient_demographics

**Line count**: 21

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_problem_list_diagnoses

**Line count**: 44

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_procedures_tumor

**Line count**: 479

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: True

**Issues**: HARDCODED_RXNORM_CODES

### v_radiation_care_plan_hierarchy

**Line count**: 25

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_radiation_documents

**Line count**: 147

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_radiation_summary

**Line count**: 312

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_radiation_treatment_appointments

**Line count**: 143

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_radiation_treatments

**Line count**: 386

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_unified_patient_timeline

**Line count**: 1044

**Dependencies**:
- Uses v_chemo_medications: True
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

### v_visits_unified

**Line count**: 169

**Dependencies**:
- Uses v_chemo_medications: False
- Uses v_medications: False
- Uses medication_request directly: False
- Has hardcoded RxNorm codes: False

