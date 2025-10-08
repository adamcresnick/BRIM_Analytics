# Diagnosis CSV Validation Report

**Date**: 2025-10-07 15:31:05  
**Patient**: C1277724  
**FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3  
**Database**: fhir_v2_prd_db

---

## Executive Summary

**Athena Events Extracted**: 23  
**Gold Standard Events**: 8

### Accuracy by Field Category

| Category | Accuracy | Matched | Total | Status |
|----------|----------|---------|-------|--------|
| 📊 **Structured** (Athena-extractable) | 61.4% | 43/70 | ⚠️ Needs Work |
| 🔀 **Hybrid** (Structured + Narrative) | 50.0% | 4/8 | ✅ Partial |
| 📝 **Narrative** (BRIM required) | N/A | 0/1 | ⏭️ Not Attempted |

---

## Detailed Field Analysis

### ✅ Structured Fields (Athena-Extractable)

These fields should be 100% extractable from Athena tables:


#### age_at_event_days
- **Status**: ❌ FAILING
- **Accuracy**: 0.0% (0/6)
- **Issues**:
  - Event 2: Expected `4763`, Got `371`
  - Event 3: Expected `4763`, Got `4762`
  - Event 4: Expected `5095`, Got `4762`
  - Event 5: Expected `5780`, Got `4762`
  - Event 6: Expected `5780`, Got `4770`
  - Event 7: Expected `5780`, Got `4778`


#### cns_integrated_diagnosis
- **Status**: ❌ FAILING
- **Accuracy**: 0.0% (0/8)
- **Issues**:
  - Event 0: Expected `Pilocytic astrocytoma`, Got `Nystagmus`
  - Event 1: Expected `Pilocytic astrocytoma`, Got `Nystagmus`
  - Event 2: Expected `Pilocytic astrocytoma`, Got `Simple or unspecified chronic serous otitis media`
  - Event 3: Expected `Pilocytic astrocytoma`, Got `Obstructive hydrocephalus`
  - Event 4: Expected `Pilocytic astrocytoma`, Got `Neoplasm of posterior cranial fossa`
  - Event 5: Expected `Pilocytic astrocytoma`, Got `Neoplasm of posterior cranial fossa`
  - Event 6: Expected `Pilocytic astrocytoma`, Got `Pilocytic astrocytoma of cerebellum`
  - Event 7: Expected `Pilocytic astrocytoma`, Got `Dysphagia`


#### clinical_status_at_event
- **Status**: ✅ WORKING
- **Accuracy**: 100.0% (8/8)


#### autopsy_performed
- **Status**: ✅ WORKING
- **Accuracy**: 100.0% (8/8)


#### cause_of_death
- **Status**: ✅ WORKING
- **Accuracy**: 100.0% (8/8)


#### event_type
- **Status**: ⚠️ PARTIAL
- **Accuracy**: 62.5% (5/8)
- **Issues**:
  - Event 1: Expected `Initial CNS Tumor`, Got `Progressive`
  - Event 2: Expected `Initial CNS Tumor`, Got `Progressive`
  - Event 3: Expected `Initial CNS Tumor`, Got `Progressive`


#### metastasis
- **Status**: ⚠️ PARTIAL
- **Accuracy**: 50.0% (4/8)
- **Issues**:
  - Event 0: Expected `Yes`, Got `No`
  - Event 1: Expected `Yes`, Got `No`
  - Event 2: Expected `Yes`, Got `No`
  - Event 3: Expected `Yes`, Got `No`


#### shunt_required
- **Status**: ⚠️ PARTIAL
- **Accuracy**: 75.0% (6/8)
- **Issues**:
  - Event 0: Expected `Endoscopic Third Ventriculostomy (ETV) Shunt`, Got `Not Applicable`
  - Event 2: Expected `Endoscopic Third Ventriculostomy (ETV) Shunt`, Got `Not Applicable`


#### tumor_or_molecular_tests_performed
- **Status**: ⚠️ PARTIAL
- **Accuracy**: 50.0% (4/8)
- **Issues**:
  - Event 0: Expected `Whole Genome Sequencing`, Got `Not Applicable`
  - Event 1: Expected `Whole Genome Sequencing`, Got `Not Applicable`
  - Event 2: Expected `Whole Genome Sequencing`, Got `Not Applicable`
  - Event 4: Expected `nan`, Got `Comprehensive Solid Tumor Panel`


### 🔀 Hybrid Fields (Structured + Narrative)

These fields have partial structured data but may need narrative enrichment:


#### who_grade
- **Status**: ❌ MISSING
- **Accuracy**: 0.0% (0/0)
- **Note**: This field typically requires both structured data and narrative analysis
- **Recommendation**: Supplement with narrative extraction from pathology/imaging reports


#### tumor_location
- **Status**: ❌ MISSING
- **Accuracy**: 0.0% (0/0)
- **Note**: This field typically requires both structured data and narrative analysis
- **Recommendation**: Supplement with narrative extraction from pathology/imaging reports


#### cns_integrated_category
- **Status**: ❌ MISSING
- **Accuracy**: 0.0% (0/0)
- **Note**: This field typically requires both structured data and narrative analysis
- **Recommendation**: Supplement with narrative extraction from pathology/imaging reports


#### metastasis_location
- **Status**: ⚠️ PARTIAL
- **Accuracy**: 50.0% (4/8)
- **Note**: This field typically requires both structured data and narrative analysis
- **Recommendation**: Supplement with narrative extraction from pathology/imaging reports


### 📝 Narrative Fields (BRIM Required)

These fields require narrative extraction and are not attempted in this validation:


#### site_of_progression
- **Status**: ⏭️ Not Attempted
- **Reason**: Requires narrative extraction via BRIM
- **Source**: Oncology progress notes, imaging reports


---

## Sample Event Comparison

### Gold Standard Event 1
```json
{
  "research_id": "C1277724",
  "event_id": "ET_FWYP9TY0",
  "autopsy_performed": "Not Applicable",
  "clinical_status_at_event": "Alive",
  "cause_of_death": "Not Applicable",
  "event_type": "Initial CNS Tumor",
  "age_at_event_days": 4763,
  "cns_integrated_category": "Low-Grade Glioma",
  "cns_integrated_diagnosis": "Pilocytic astrocytoma",
  "who_grade": "1",
  "metastasis": "Yes",
  "metastasis_location": "Leptomeningeal",
  "metastasis_location_other": "Not Applicable",
  "site_of_progression": "Not Applicable",
  "tumor_or_molecular_tests_performed": "Whole Genome Sequencing",
  "tumor_or_molecular_tests_performed_other": "Not Applicable",
  "tumor_location": "Cerebellum/Posterior Fossa",
  "tumor_location_other": "Not Applicable",
  "shunt_required": "Endoscopic Third Ventriculostomy (ETV) Shunt",
  "shunt_required_other": "Not Applicable"
}
```

### Athena Extracted Event 1
```json
{
  "research_id": "C1277724",
  "event_id": "AUTO_1",
  "autopsy_performed": "Not Applicable",
  "clinical_status_at_event": "Alive",
  "cause_of_death": "Not Applicable",
  "event_type": "Initial CNS Tumor",
  "age_at_event_days": null,
  "cns_integrated_category": null,
  "cns_integrated_diagnosis": "Nystagmus",
  "who_grade": null,
  "metastasis": "No",
  "metastasis_location": "Not Applicable",
  "metastasis_location_other": "Not Applicable",
  "site_of_progression": null,
  "tumor_or_molecular_tests_performed": "Not Applicable",
  "tumor_or_molecular_tests_performed_other": "Not Applicable",
  "tumor_location": null,
  "tumor_location_other": "Not Applicable",
  "shunt_required": "Not Applicable",
  "shunt_required_other": "Not Applicable"
}
```

---

## Assessment

### ✅ What's Working

- **clinical_status_at_event**: 100.0% accuracy
- **autopsy_performed**: 100.0% accuracy
- **cause_of_death**: 100.0% accuracy
- **shunt_required**: 75.0% accuracy

### ❌ Critical Gaps

- **age_at_event_days**: Only 0.0% accuracy
  - **Action**: Review extraction logic and Athena table mapping
- **cns_integrated_diagnosis**: Only 0.0% accuracy
  - **Action**: Review extraction logic and Athena table mapping
- **event_type**: Only 62.5% accuracy
  - **Action**: Review extraction logic and Athena table mapping
- **metastasis**: Only 50.0% accuracy
  - **Action**: Review extraction logic and Athena table mapping
- **tumor_or_molecular_tests_performed**: Only 50.0% accuracy
  - **Action**: Review extraction logic and Athena table mapping


### 🔧 Recommendations

⚠️ **Structured extraction needs improvements**

**Priority Actions**:
1. Fix event clustering logic (Initial vs Progressive)
2. Improve age_at_event calculation
3. Review diagnosis name mapping


---

## Athena Tables Used

1. **problem_list_diagnoses**: Primary diagnosis source
2. **condition** + **condition_code_coding**: Metastasis detection
3. **procedure** + **procedure_code_coding**: Shunt procedures
4. **molecular_tests**: Test types performed

---

**Validation Status**: {'✅ STRUCTURED FIELDS WORKING' if metrics['structured_accuracy'] >= 70 else '⚠️ NEEDS IMPROVEMENT'}
