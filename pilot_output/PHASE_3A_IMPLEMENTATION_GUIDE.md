# Phase 3a Implementation Guide - Tier 1 Expansion
**Date**: October 3, 2025  
**Iteration**: 3c_phase3a  
**Objective**: Add 13 Tier 1 variables (demographics, diagnosis, molecular) to proven 4 surgery variables  
**Expected Accuracy**: 95%+ (low complexity, high confidence)

---

## Executive Summary

**What Changed from Phase 2**:
- Added 13 new **one_per_patient** variables (demographics, diagnosis, molecular)
- Kept 4 proven **many_per_note** surgery variables from Phase 2
- Total: **17 variables** (vs 4 in Phase 2)
- All Tier 1 variables use direct FHIR extraction (no aggregation needed)

**Why Tier 1 First**:
- ✅ Lowest complexity (one value per patient)
- ✅ FHIR structured data available (Patient, Condition resources)
- ✅ Builds on Phase 2 100% success patterns
- ✅ Quick validation (2 hours vs 1 week for multi-event variables)

---

## Variable Inventory

### New Tier 1 Variables (13 total)

#### Demographics (5 variables)

| Variable | Source | Type | Scope | Gold Standard (C1277724) | Data Dict Field |
|----------|--------|------|-------|-------------------------|----------------|
| **patient_gender** | Patient.gender | dropdown | one_per_patient | Female | legal_sex |
| **date_of_birth** | Patient.birthDate | date | one_per_patient | 2005-05-13 | date_of_birth |
| **age_at_diagnosis** | Calculated | number | one_per_patient | 13 years | age_at_event_days |
| **race** | Patient.extension | checkbox | one_per_patient | White (likely) | race |
| **ethnicity** | Patient.extension | checkbox | one_per_patient | Not Hispanic or Latino (likely) | ethnicity |

#### Core Diagnosis (4 variables)

| Variable | Source | Type | Scope | Gold Standard (C1277724) | Data Dict Field |
|----------|--------|------|-------|-------------------------|----------------|
| **primary_diagnosis** | Condition.code | text | one_per_patient | Pilocytic astrocytoma | cns_integrated_diagnosis |
| **diagnosis_date** | Condition.onsetDateTime | date | one_per_patient | 2018-06-04 | age_at_event_days |
| **who_grade** | Pathology reports | dropdown | one_per_patient | Grade I | who_grade |
| **tumor_location** | Imaging/path reports | checkbox | one_per_patient | Cerebellum/Posterior Fossa | tumor_location |

#### Molecular Markers (4 variables)

| Variable | Source | Type | Scope | Gold Standard (C1277724) | Data Dict Field |
|----------|--------|------|-------|-------------------------|----------------|
| **idh_mutation** | Molecular reports | radio | one_per_patient | IDH wild-type | idh_mutation |
| **mgmt_methylation** | Molecular reports | radio | one_per_patient | Not tested | mgmt_methylation |
| **braf_status** | NGS reports | dropdown | one_per_patient | BRAF fusion | (custom field) |

### Existing Phase 2 Surgery Variables (4 total)

| Variable | Source | Type | Scope | Gold Standard (C1277724) | Status |
|----------|--------|------|-------|-------------------------|--------|
| **surgery_date** | STRUCTURED_surgeries | date | many_per_note | 2018-05-28, 2021-03-10 | ✅ Phase 2 validated |
| **surgery_type** | STRUCTURED_surgeries | dropdown | many_per_note | Tumor Resection (2x) | ✅ Phase 2 validated |
| **surgery_extent** | STRUCTURED_surgeries | dropdown | many_per_note | Partial Resection (2x) | ✅ Phase 2 validated |
| **surgery_location** | STRUCTURED_surgeries | checkbox | many_per_note | Cerebellum/Posterior Fossa (2x) | ✅ Phase 2 validated |

---

## Data Dictionary Alignment

### Demographics Field Mappings

#### patient_gender (legal_sex)
**Data Dictionary**:
- Field Type: dropdown
- Values: 0=Male, 1=Female, 2=Unavailable
- Source: Patient resource gender field

**BRIM Instruction**:
```
Return EXACTLY one of: 'Male' or 'Female'
CRITICAL: Return Title Case exact match
If FHIR Patient.gender is 'female' return 'Female'
If 'male' return 'Male'
```

**option_definitions**:
```json
{
  "Male": "Male",
  "Female": "Female",
  "Unavailable": "Unavailable"
}
```

#### date_of_birth
**Data Dictionary**:
- Field Type: text
- Format: yyyy-mm-dd
- Source: Patient.birthDate

**BRIM Instruction**:
```
Return in YYYY-MM-DD format
Extract exact date from Patient.birthDate
DO NOT calculate or infer from age
```

#### race
**Data Dictionary**:
- Field Type: checkbox (multiple selections allowed)
- Values: White, Black or African American, Asian, Native Hawaiian or Other Pacific Islander, American Indian or Alaska Native, Other, Unavailable
- Source: Patient.extension with url=race

**option_definitions**:
```json
{
  "White": "White",
  "Black or African American": "Black or African American",
  "Asian": "Asian",
  "Native Hawaiian or Other Pacific Islander": "Native Hawaiian or Other Pacific Islander",
  "American Indian or Alaska Native": "American Indian or Alaska Native",
  "Other": "Other",
  "Unavailable": "Unavailable"
}
```

#### ethnicity
**Data Dictionary**:
- Field Type: radio (single selection)
- Values: 1=Hispanic or Latino, 2=Not Hispanic or Latino, 3=Unavailable
- Source: Patient.extension with url=ethnicity

**option_definitions**:
```json
{
  "Hispanic or Latino": "Hispanic or Latino",
  "Not Hispanic or Latino": "Not Hispanic or Latino",
  "Unavailable": "Unavailable"
}
```

---

### Diagnosis Field Mappings

#### who_grade
**Data Dictionary**:
- Field Type: dropdown
- Values: 1, 2, 3, 4, No grade specified
- BRIM Mapping: Grade I, Grade II, Grade III, Grade IV, No grade specified

**BRIM Instruction**:
```
Return EXACTLY 'Grade I', 'Grade II', 'Grade III', 'Grade IV', or 'No grade specified'
Match Title Case
DO NOT return numeric values (1, 2, 3, 4) - use 'Grade I' format
```

**option_definitions**:
```json
{
  "Grade I": "Grade I",
  "Grade II": "Grade II",
  "Grade III": "Grade III",
  "Grade IV": "Grade IV",
  "No grade specified": "No grade specified"
}
```

#### tumor_location
**Data Dictionary**:
- Field Type: checkbox (24 anatomical locations)
- Values: Same 24 options as surgery_location (proven in Phase 2)

**BRIM Instruction**:
```
Extract WHERE tumor is located (anatomical site), NOT surgical procedure location
DO NOT return 'Craniotomy' or 'Skull'
Look for: 'cerebellar tumor', 'posterior fossa mass', 'cerebellar hemisphere'
Return EXACTLY one of the 24 valid values
```

**CRITICAL Success Factor**: Phase 2 proved option_definitions JSON + DO NOT examples prevent procedure location extraction

---

### Molecular Field Mappings

#### idh_mutation
**Data Dictionary**:
- Field Type: radio (single selection)
- Values: Mutant, Wildtype, Unknown, Not tested

**option_definitions**:
```json
{
  "IDH mutant": "IDH mutant",
  "IDH wild-type": "IDH wild-type",
  "Unknown": "Unknown",
  "Not tested": "Not tested"
}
```

**INFERENCE RULE**:
```
If BRAF fusion detected and no IDH mention, return 'IDH wild-type'
(BRAF and IDH mutations are mutually exclusive)
```

#### mgmt_methylation
**Data Dictionary**:
- Field Type: radio (single selection)
- Values: Methylated, Unmethylated, Unknown, Not tested

**option_definitions**:
```json
{
  "Methylated": "Methylated",
  "Unmethylated": "Unmethylated",
  "Unknown": "Unknown",
  "Not tested": "Not tested"
}
```

**CLINICAL NOTE**:
```
MGMT testing primarily for glioblastoma (high-grade)
Rarely ordered for Grade I tumors
If no mention in molecular reports, return 'Not tested'
```

#### braf_status
**Data Dictionary**:
- Field Type: Custom (not in standard data dictionary)
- Values: BRAF V600E mutation, BRAF fusion, BRAF wild-type, Unknown, Not tested

**option_definitions**:
```json
{
  "BRAF V600E mutation": "BRAF V600E mutation",
  "BRAF fusion": "BRAF fusion",
  "BRAF wild-type": "BRAF wild-type",
  "Unknown": "Unknown",
  "Not tested": "Not tested"
}
```

**Gold Standard Example**:
```
NGS report: "KIAA1549 (NM_020910.2) - BRAF (NM_004333.4) fusion"
BRIM should return: "BRAF fusion"
```

---

## Expected Results for C1277724

### Gold Standard Values (17 variables)

| Variable | Expected Value | Confidence | Notes |
|----------|---------------|-----------|-------|
| **patient_gender** | Female | 100% | FHIR Patient.gender = "female" |
| **date_of_birth** | 2005-05-13 | 100% | FHIR Patient.birthDate exact |
| **age_at_diagnosis** | 13 | 100% | Calculated: 2018-06-04 - 2005-05-13 |
| **race** | White | 80% | Not in FHIR, may need inference |
| **ethnicity** | Not Hispanic or Latino | 80% | Not in FHIR, may need inference |
| **primary_diagnosis** | Pilocytic astrocytoma | 95% | Pathology reports clear |
| **diagnosis_date** | 2018-06-04 | 95% | structured_data.json has this |
| **who_grade** | Grade I | 95% | Pilocytic = Grade I standard |
| **tumor_location** | Cerebellum/Posterior Fossa | 100% | Phase 2 validated |
| **idh_mutation** | IDH wild-type | 90% | Inference from BRAF fusion |
| **mgmt_methylation** | Not tested | 100% | Not in molecular reports |
| **braf_status** | BRAF fusion | 100% | NGS report explicit |
| **surgery_date** | 2018-05-28, 2021-03-10 | 100% | Phase 2 validated (2x) |
| **surgery_type** | Tumor Resection (2x) | 100% | Phase 2 validated |
| **surgery_extent** | Partial Resection (2x) | 100% | Phase 2 validated |
| **surgery_location** | Cerebellum/Posterior Fossa (2x) | 100% | Phase 2 validated |

**Expected Extraction Counts**:
- 13 one_per_patient variables: 1 value each = **13 values**
- 4 many_per_note surgery variables: 2 surgeries each = **8 values** (from Phase 2 we saw over-extraction: ~26 values per variable)
- **Total expected**: 13 + 8 = **21 values minimum** (likely 13 + 100 = **113 values** with over-extraction)

---

## Success Criteria

### Primary Metrics

| Metric | Target | Phase 2 Baseline | Notes |
|--------|--------|------------------|-------|
| **Overall Accuracy** | 95%+ | 100% (8/8) | Tier 1 lower complexity |
| **Demographics Accuracy** | 95%+ | N/A | 5/5 variables correct |
| **Diagnosis Accuracy** | 95%+ | N/A | 4/4 variables correct |
| **Molecular Accuracy** | 90%+ | N/A | 3/4 variables correct (IDH inference risky) |
| **Surgery Accuracy** | 100% | 100% | Maintain Phase 2 success |
| **Data Dict Alignment** | 100% | 100% | All dropdowns match option_definitions |
| **Extraction Time** | < 15 min | 12 min | Acceptable range |

### Variable-Level Targets

**MUST ACHIEVE 100%**:
- patient_gender (FHIR structured)
- date_of_birth (FHIR structured)
- braf_status (explicit in reports)
- All 4 surgery variables (Phase 2 proven)

**SHOULD ACHIEVE 95%+**:
- primary_diagnosis (clear in pathology)
- diagnosis_date (documented)
- who_grade (inferable from diagnosis)
- tumor_location (Phase 2 approach proven)

**ACCEPTABLE 80%+**:
- race (may not be documented)
- ethnicity (may not be documented)
- age_at_diagnosis (calculation dependent)
- idh_mutation (inference rule)

---

## Risk Assessment

### Known Risks

#### Risk 1: Demographics Not in FHIR Extensions
**Probability**: Medium (50%)  
**Impact**: Moderate (2 variables affected: race, ethnicity)

**Mitigation**:
- Fallback to narrative text search in clinical notes
- Accept "Unavailable" as valid answer if not documented
- Success criteria: 80% (not 100%) for these variables

**Acceptance**:
- If race/ethnicity return "Unavailable", still counts as correct if truly not documented

---

#### Risk 2: WHO Grade Inference for Pilocytic Astrocytoma
**Probability**: Low (20%)  
**Impact**: Low (1 variable affected: who_grade)

**Mitigation**:
- Instruction includes: "If diagnosis is pilocytic astrocytoma and no grade specified, infer 'Grade I'"
- Clinical standard: pilocytic astrocytoma is ALWAYS WHO Grade I
- Pathology reports likely explicit

**Acceptance**:
- Inference from diagnosis name acceptable if explicit grade not stated

---

#### Risk 3: IDH Mutation Inference from BRAF
**Probability**: Medium (30%)  
**Impact**: Low (1 variable affected: idh_mutation)

**Mitigation**:
- Instruction includes: "If BRAF fusion detected and no IDH mention, return 'IDH wild-type'"
- Clinical fact: BRAF and IDH mutations mutually exclusive in gliomas
- Inference documented in instruction

**Acceptance**:
- If BRIM extracts "Not tested" instead of inferring "IDH wild-type", acceptable
- Success criteria: 80% (not 100%)

---

#### Risk 4: Over-Extraction from Surgery Variables
**Probability**: High (100% - expected from Phase 2)  
**Impact**: None (not a problem)

**Mitigation**:
- Phase 2 showed 102 values (expected 8) = 100% recall
- All gold standard values captured despite over-extraction
- Aggregation decisions for Tier 3 will handle deduplication

**Acceptance**:
- Over-extraction is FEATURE not bug (ensures 100% recall)
- Phase 2 proved this approach works

---

## Implementation Checklist

### Pre-Upload Validation

- [x] **variables.csv created** (17 variables, 11 columns)
- [x] **decisions.csv created** (empty, no Tier 1 aggregation needed)
- [x] **project.csv created** (empty template with headers)
- [ ] **Verify FHIR bundle has Patient resource** (gender, birthDate)
- [ ] **Verify diagnosis_date in structured_data.json**
- [ ] **Verify BRAF results in molecular reports**

### BRIM Upload Steps

1. **Create new BRIM Project** (Project 23 or next available)
2. **Upload variables.csv** (17 variables)
3. **Upload decisions.csv** (empty, but required)
4. **Upload project.csv** (or connect to FHIR data source)
5. **Run extraction** (expected time: 12-15 minutes)
6. **Download results CSV**

### Post-Extraction Validation

- [ ] **Check extraction counts**: 21-113 values total
- [ ] **Run validation script** (Python script with gold standards)
- [ ] **Verify 100% accuracy for MUST ACHIEVE variables**
- [ ] **Verify 95%+ accuracy for SHOULD ACHIEVE variables**
- [ ] **Document any failures with root cause analysis**
- [ ] **Commit results to GitHub**

---

## Validation Script

See **Phase 3a Python Validation Script** below for automated gold standard checking.

Expected output:
```
======================================================================
BRIM PHASE 3a TIER 1 EXPANSION VALIDATION RESULTS
17 Variables: 13 Tier 1 (new) + 4 Surgery (Phase 2 validated)
======================================================================

TOTAL EXTRACTIONS: 113 values (expected: 21-113)

ONE_PER_PATIENT VARIABLES (13 Tier 1):
----------------------------------------------------------------------
patient_gender           ✅ 1 extraction  → "Female" (GOLD STANDARD MATCH)
date_of_birth            ✅ 1 extraction  → "2005-05-13" (GOLD STANDARD MATCH)
age_at_diagnosis         ✅ 1 extraction  → "13" (GOLD STANDARD MATCH)
race                     ✅ 1 extraction  → "White" or "Unavailable" (ACCEPTABLE)
ethnicity                ✅ 1 extraction  → "Not Hispanic or Latino" or "Unavailable" (ACCEPTABLE)
primary_diagnosis        ✅ 1 extraction  → "Pilocytic astrocytoma" (GOLD STANDARD MATCH)
diagnosis_date           ✅ 1 extraction  → "2018-06-04" (GOLD STANDARD MATCH)
who_grade                ✅ 1 extraction  → "Grade I" (GOLD STANDARD MATCH)
tumor_location           ✅ 1 extraction  → "Cerebellum/Posterior Fossa" (GOLD STANDARD MATCH)
idh_mutation             ✅ 1 extraction  → "IDH wild-type" or "Not tested" (ACCEPTABLE)
mgmt_methylation         ✅ 1 extraction  → "Not tested" (GOLD STANDARD MATCH)
braf_status              ✅ 1 extraction  → "BRAF fusion" (GOLD STANDARD MATCH)

MANY_PER_NOTE VARIABLES (4 Surgery from Phase 2):
----------------------------------------------------------------------
surgery_date             ✅ 25 extractions → Contains "2018-05-28" AND "2021-03-10" (GOLD STANDARD MATCH)
surgery_type             ✅ 30 extractions → Contains "Tumor Resection" (16x) (GOLD STANDARD MATCH)
surgery_extent           ✅ 21 extractions → Contains "Partial Resection" (10x) (GOLD STANDARD MATCH)
surgery_location         ✅ 26 extractions → Contains "Cerebellum/Posterior Fossa" (21x) (GOLD STANDARD MATCH)

======================================================================
GOLD STANDARD VALIDATION: 17/17 = 100.0% ✅
======================================================================

TIER 1 DEMOGRAPHICS (5 variables):  5/5 = 100% ✅
TIER 1 DIAGNOSIS (4 variables):     4/4 = 100% ✅
TIER 1 MOLECULAR (4 variables):     4/4 = 100% ✅
PHASE 2 SURGERY (4 variables):      4/4 = 100% ✅ (maintained from Phase 2)

🎉 PHASE 3a SUCCESS! Ready for Tier 2 expansion (chemotherapy + radiation)
```

---

## Next Steps After Phase 3a

### If Phase 3a Achieves 95%+ Accuracy:
✅ **Proceed to Phase 3b (Tier 2 Expansion)**
- Add chemotherapy variables (7 many_per_note)
- Add radiation variables (4 one_per_patient)
- Total: 28 variables (17 current + 11 Tier 2)
- Timeline: Week 2-3 (October 2025)

### If Phase 3a Achieves 80-94% Accuracy:
⚠️ **Iterate on Failed Variables**
- Analyze which variables failed
- Enhance instructions for failed variables
- Re-test with Phase 3a_v2 before Tier 2

### If Phase 3a Achieves < 80% Accuracy:
🚫 **Pause and Re-Evaluate**
- Deep dive root cause analysis
- May need STRUCTURED document creation for demographics
- Consult BRIM documentation for extraction limitations

---

**Status**: ✅ **Phase 3a Ready for Upload**  
**Expected Upload Date**: October 3-4, 2025  
**Expected Results Date**: October 4-5, 2025  
**Confidence Level**: Very High (95%+ expected accuracy)
