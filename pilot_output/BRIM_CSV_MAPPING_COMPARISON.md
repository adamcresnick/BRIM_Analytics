# BRIM vs CSV Mapping Master Status Comparison
**Date**: October 4, 2025

## Overview

This document maps the BRIM variable extraction project against the CSV Mapping Master Status from the original FHIR-to-Clinical-Trial crosswalk project to identify overlaps, gaps, and next steps.

---

## Status Summary

### CSV Mapping Project (Original)
- **Total CSVs**: 18
- **Completed**: 3 (demographics, diagnosis, concomitant_medications)
- **In Progress**: 2 (imaging_clinical_related, measurements)
- **Framework Documented**: 4 (encounters, treatments, conditions_predispositions)
- **Not Started**: 9

### BRIM Variable Extraction (Current)
- **Phase 2 Complete**: 4 variables (surgery) - 100% accuracy
- **Phase 3a Complete**: 17 variables (demographics, diagnosis, molecular, surgery) - 81.2% accuracy
- **Phase 3a_v2 Planned**: Same 17 variables with Athena integration - Expected 95%+
- **Roadmap**: 48 total variables across 4 tiers

---

## Detailed Variable-to-CSV Mapping

### ✅ TIER 1: Demographics (5 variables) → demographics.csv

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| patient_gender | sex | ✅ COMPLETED | ✅ Phase 3a | patient_access.gender | 🟢 EXACT |
| date_of_birth | birth_date | ✅ COMPLETED | ✅ Phase 3a | patient_access.birth_date | 🟢 EXACT |
| age_at_diagnosis | age_at_diagnosis | ✅ COMPLETED | ✅ Phase 3a | CALCULATED | 🟢 EXACT |
| race | race | ✅ COMPLETED | ✅ Phase 3a | patient_access.race | 🟢 EXACT |
| ethnicity | ethnicity | ✅ COMPLETED | ✅ Phase 3a | patient_access.ethnicity | 🟢 EXACT |

**Assessment**: ✅ **100% overlap** - demographics.csv is already complete in CSV project
**Action**: ✅ Phase 3a_v2 will use Athena patient_access table (same source as CSV mapping)

---

### ✅ TIER 1: Diagnosis (4 variables) → diagnosis.csv

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| primary_diagnosis | primary_diagnosis | ✅ COMPLETED | ✅ Phase 3a | Text extraction | 🟢 EXACT |
| diagnosis_date | diagnosis_date | ✅ COMPLETED | ✅ Phase 3a | Text extraction | 🟡 PARTIAL |
| who_grade | tumor_grade | ✅ COMPLETED | ✅ Phase 3a | Text extraction | 🟢 EXACT |
| tumor_location | topography | ✅ COMPLETED | ✅ Phase 3a | Text extraction | 🟢 EXACT |

**Assessment**: ✅ **100% overlap** - diagnosis.csv is already complete in CSV project
**Action**: ✅ Phase 3a variables align with completed CSV structure
**Note**: diagnosis_date needs clarification (surgery vs pathology date) in both projects

---

### ✅ TIER 1: Molecular (4 variables) → molecular_characterization.csv

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| idh_mutation | idh_status | 🔲 NOT STARTED | ✅ Phase 3a | Text extraction | 🟢 EXACT |
| mgmt_methylation | mgmt_status | 🔲 NOT STARTED | ✅ Phase 3a | Text extraction | 🟢 EXACT |
| braf_status | braf_alteration | 🔲 NOT STARTED | ✅ Phase 3a | Text extraction | 🟢 EXACT |
| (future) | egfr_status | 🔲 NOT STARTED | ⏳ Tier 4 | Text extraction | - |

**Assessment**: 🟡 **Partial overlap** - BRIM ahead on molecular variables
**Action**: ✅ BRIM Phase 3a provides template for molecular_characterization.csv mapping
**Gap**: CSV project hasn't started molecular mappings yet

---

### ✅ PHASE 2: Surgery (4 variables) → treatments.csv (surgery section)

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| surgery_date | surgery_date | 📋 FRAMEWORK | ✅ Phase 2 (100%) | Text extraction | 🟢 EXACT |
| surgery_type | surgery_type | 📋 FRAMEWORK | ✅ Phase 2 (100%) | Text extraction | 🟢 EXACT |
| surgery_extent | extent_of_resection | 📋 FRAMEWORK | ✅ Phase 2 (100%) | Text extraction | 🟢 EXACT |
| surgery_location | surgery_location | 📋 FRAMEWORK | ✅ Phase 2 (100%) | Text extraction | 🟢 EXACT |

**Assessment**: 🟢 **BRIM ahead** - Surgery variables proven at 100% accuracy
**Action**: ✅ BRIM Phase 2 provides validated template for treatments.csv surgery section
**Gap**: CSV project has framework but no implementation yet

---

### ⏳ TIER 2: Chemotherapy (7 variables) → treatments.csv (chemotherapy section) + concomitant_medications.csv

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| chemotherapy_agent | medication_name | ✅ COMPLETED | ⏳ Phase 3b | patient_medications.medication_name | 🟢 EXACT |
| chemotherapy_start_date | medication_start_date | ✅ COMPLETED | ⏳ Phase 3b | patient_medications.authored_on | 🟢 EXACT |
| chemotherapy_end_date | medication_end_date | ✅ COMPLETED | ⏳ Phase 3b | patient_medications.end_date | 🟢 EXACT |
| chemotherapy_line | treatment_line | 📋 FRAMEWORK | ⏳ Phase 3b | Text extraction | 🟡 PARTIAL |
| chemotherapy_status | medication_status | ✅ COMPLETED | ⏳ Phase 3b | patient_medications.status | 🟢 EXACT |
| chemotherapy_route | route | ✅ COMPLETED | ⏳ Phase 3b | Text extraction | 🟢 EXACT |
| chemotherapy_dose | dose | ✅ COMPLETED | ⏳ Phase 3b | Text extraction | 🟢 EXACT |

**Assessment**: 🟢 **CSV project ahead** - concomitant_medications.csv already complete
**Action**: ✅ Use CSV project's patient_medications queries as template for Phase 3b
**Advantage**: RxNorm-based chemotherapy identification already validated (100+ medications)

---

### ⏳ TIER 2: Radiation (4 variables) → treatments.csv (radiation section)

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| radiation_therapy_yn | radiation_given | 📋 FRAMEWORK | ⏳ Phase 3b | procedure.code | 🟢 EXACT |
| radiation_start_date | radiation_start_date | 📋 FRAMEWORK | ⏳ Phase 3b | procedure.performed_datetime | 🟢 EXACT |
| radiation_dose | radiation_dose | 📋 FRAMEWORK | ⏳ Phase 3b | Text extraction | 🟡 PARTIAL |
| radiation_fractions | radiation_fractions | 📋 FRAMEWORK | ⏳ Phase 3b | Text extraction | 🟡 PARTIAL |

**Assessment**: 🟡 **Both projects need implementation**
**Action**: ⏳ Coordinate implementation between BRIM Phase 3b and CSV treatments.csv
**Note**: Framework exists in CSV project, BRIM needs to implement with text extraction

---

### ⏳ TIER 3: Surgery Aggregations (5 variables) → treatments.csv (aggregated fields)

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| total_surgeries | number_of_surgeries | 📋 FRAMEWORK | ⏳ Phase 4 | COUNT(surgery_date) | 🟢 EXACT |
| first_surgery_date | first_surgery_date | 📋 FRAMEWORK | ⏳ Phase 4 | MIN(surgery_date) | 🟢 EXACT |
| last_surgery_date | last_surgery_date | 📋 FRAMEWORK | ⏳ Phase 4 | MAX(surgery_date) | 🟢 EXACT |
| best_resection | best_extent_of_resection | 📋 FRAMEWORK | ⏳ Phase 4 | PRIORITY(surgery_extent) | 🟢 EXACT |
| primary_surgery_location | primary_location | 📋 FRAMEWORK | ⏳ Phase 4 | MODE(surgery_location) | 🟢 EXACT |

**Assessment**: 🟡 **Both projects need aggregation logic**
**Action**: ⏳ BRIM decisions.csv will implement aggregation patterns applicable to CSV project

---

### ⏳ TIER 4: Imaging + Corticosteroids (11 variables) → imaging_clinical_related.csv

| BRIM Variable | CSV Column | CSV Status | BRIM Status | Athena Source | Match Quality |
|---------------|------------|------------|-------------|---------------|---------------|
| imaging_type | imaging_modality | 🔄 IN PROGRESS | ⏳ Phase 5 | radiology_imaging.imaging_procedure | 🟢 EXACT |
| imaging_date | imaging_date | 🔄 IN PROGRESS | ⏳ Phase 5 | radiology_imaging.result_datetime | 🟢 EXACT |
| corticosteroid_at_imaging | corticosteroid_yn | 🔄 IN PROGRESS | ⏳ Phase 5 | patient_medications + temporal | 🟢 EXACT |
| corticosteroid_agent | corticosteroid_name | 🔄 IN PROGRESS | ⏳ Phase 5 | patient_medications.medication_name | 🟢 EXACT |
| corticosteroid_dose | corticosteroid_dose | 🔄 IN PROGRESS | ⏳ Phase 5 | Text extraction | 🟡 PARTIAL |
| (+ 6 more imaging vars) | (various) | 🔄 IN PROGRESS | ⏳ Phase 5 | radiology_imaging_mri | 🟢 EXACT |

**Assessment**: 🟢 **CSV project ahead** - Implementation complete, testing pending
**Action**: ✅ Use CSV project's corticosteroid_reference.py (53 RxNorm codes) for Phase 5
**Advantage**: Temporal alignment logic already implemented in CSV project

---

### 🔲 GAP ANALYSIS: Variables in CSV Project NOT in BRIM Roadmap

| CSV File | Status | BRIM Equivalent | Priority | Action |
|----------|--------|-----------------|----------|--------|
| **encounters.csv** | 📋 FRAMEWORK | ❌ Not in roadmap | MEDIUM | Consider adding encounter dates/types |
| **conditions_predispositions.csv** | 📋 FRAMEWORK | ❌ Not in roadmap | LOW | Genetic conditions could be Tier 4 |
| **measurements.csv** | 🔄 IN PROGRESS | ❌ Not in roadmap | MEDIUM | Anthropometric data could be Tier 3 |
| **ophthalmology_functional_asses.csv** | 🔲 NOT STARTED | ❌ Not in roadmap | LOW | Vision assessments - specialized |
| **survival.csv** | 🔲 NOT STARTED | ❌ Not in roadmap | HIGH | Outcome data - critical |
| **hydrocephalus_details.csv** | 🔲 NOT STARTED | ❌ Not in roadmap | LOW | Complication tracking - specialized |
| **family_cancer_history.csv** | 🔲 NOT STARTED | ❌ Not in roadmap | LOW | Family history - specialized |
| **molecular_tests_performed.csv** | 🔲 NOT STARTED | ❌ Not in roadmap | MEDIUM | Test metadata - could add to Tier 1 |

---

## Integration Opportunities

### 1. ✅ IMMEDIATE: Leverage Completed CSV Mappings

**Demographics** (CSV ✅ COMPLETED, BRIM Phase 3a):
- ✅ Use `fhir_v2_prd_db.patient_access` table (same as CSV project)
- ✅ Pre-populate BRIM demographics CSV from Athena (Phase 3a_v2)
- ✅ Expected accuracy boost: 81% → 95%+

**Medications** (CSV ✅ COMPLETED, BRIM Phase 3b planned):
- ✅ Use CSV project's RxNorm chemotherapy identification
- ✅ Query `fhir_v2_prd_db.patient_medications` table
- ✅ Leverage validated medication crosswalk (100+ drugs)
- ✅ Apply CSV project's temporal alignment logic

### 2. 🔄 SHORT-TERM: Coordinate In-Progress Work

**Imaging + Corticosteroids** (CSV 🔄 IN PROGRESS, BRIM Phase 5 planned):
- ✅ Adopt CSV project's `corticosteroid_reference.py` module (53 RxNorm codes)
- ✅ Use `radiology_imaging_mri` materialized views
- ✅ Apply CSV project's temporal alignment between medications and imaging
- ⏳ Defer BRIM Phase 5 until CSV testing complete to avoid duplication

**Measurements** (CSV 🔄 IN PROGRESS, BRIM not planned):
- ⚠️ Consider adding anthropometric measurements to BRIM Tier 3
- ⚠️ Would require new variables: height, weight, head_circumference
- ⚠️ Low priority for oncology outcomes, may skip

### 3. ⏳ MEDIUM-TERM: Share Implementation Patterns

**Surgery Variables** (CSV 📋 FRAMEWORK, BRIM ✅ 100% VALIDATED):
- ✅ BRIM provides validated extraction patterns for treatments.csv surgery section
- ✅ Share Phase 2 prompt engineering patterns (option_definitions, CRITICAL directives)
- ✅ CSV project can adopt BRIM's many_per_note scope for longitudinal surgery tracking

**Radiation Variables** (CSV 📋 FRAMEWORK, BRIM Phase 3b planned):
- ⏳ Coordinate implementation between both projects
- ⏳ Share procedure code identification strategies
- ⏳ Align on text extraction for dose/fractions

### 4. 🔲 LONG-TERM: Address Gaps

**Encounters** (CSV 📋 FRAMEWORK, BRIM ❌ NOT PLANNED):
- ❌ BRIM doesn't track encounter types/dates separately
- ⚠️ Consider adding if needed for clinical context
- 📊 Low priority for current BRIM use case

**Survival Data** (CSV 🔲 NOT STARTED, BRIM ❌ NOT PLANNED):
- ❌ Critical outcome data not in BRIM roadmap
- ⚠️ HIGH PRIORITY gap for outcomes research
- 📊 Should be added to both projects

**Molecular Tests Metadata** (CSV 🔲 NOT STARTED, BRIM ❌ NOT PLANNED):
- ❌ Test names, dates, laboratories not tracked
- ⚠️ Could enhance Tier 1 molecular variables
- 📊 Medium priority enhancement

---

## Recommendations

### For BRIM Project

1. ✅ **Phase 3a_v2**: Adopt `fhir_v2_prd_db.patient_access` for demographics (IMMEDIATE)
   - Aligns with completed demographics.csv
   - Expected accuracy: 95%+

2. ✅ **Phase 3b**: Leverage concomitant_medications.csv implementation (NEAR-TERM)
   - Use RxNorm chemotherapy identification
   - Query patient_medications table
   - Expected accuracy: 90%+ (based on CSV validation)

3. ⏳ **Phase 5**: Defer imaging+corticosteroids until CSV testing complete (MEDIUM-TERM)
   - Avoid duplicating in-progress work
   - Adopt validated corticosteroid_reference.py module

4. ⚠️ **New Variables**: Consider adding survival data to roadmap (HIGH PRIORITY)
   - Critical for outcomes research
   - Gap in both projects

### For CSV Mapping Project

1. ✅ **treatments.csv surgery**: Adopt BRIM Phase 2 extraction patterns (IMMEDIATE)
   - Proven 100% accuracy
   - many_per_note scope for longitudinal tracking
   - option_definitions JSON for dropdown enforcement

2. ⏳ **molecular_characterization.csv**: Use BRIM Phase 3a as template (NEAR-TERM)
   - IDH, MGMT, BRAF extraction patterns validated
   - Text extraction from pathology reports

3. ⏳ **Coordinate radiation implementation** with BRIM Phase 3b (MEDIUM-TERM)
   - Share procedure code identification
   - Align on text extraction strategies

---

## Summary

### Overlap Assessment

| Category | CSV Status | BRIM Status | Alignment | Action |
|----------|------------|-------------|-----------|--------|
| **Demographics** | ✅ COMPLETE | ✅ Phase 3a | 🟢 100% | Use Athena patient_access |
| **Diagnosis** | ✅ COMPLETE | ✅ Phase 3a | 🟢 100% | Already aligned |
| **Molecular** | 🔲 NOT STARTED | ✅ Phase 3a | 🟡 BRIM ahead | CSV can adopt BRIM patterns |
| **Surgery** | 📋 FRAMEWORK | ✅ Phase 2 (100%) | 🟡 BRIM ahead | CSV can adopt BRIM patterns |
| **Chemotherapy** | ✅ COMPLETE | ⏳ Phase 3b | 🟢 CSV ahead | BRIM can leverage CSV work |
| **Radiation** | 📋 FRAMEWORK | ⏳ Phase 3b | 🟡 Both need work | Coordinate implementation |
| **Imaging+Steroids** | 🔄 IN PROGRESS | ⏳ Phase 5 | 🟢 CSV ahead | BRIM can adopt CSV module |
| **Encounters** | 📋 FRAMEWORK | ❌ Not planned | 🔴 Gap | Consider adding to BRIM |
| **Survival** | 🔲 NOT STARTED | ❌ Not planned | 🔴 Gap | HIGH PRIORITY for both |

### Key Insights

1. **Strong Overlap**: Demographics, diagnosis, molecular, surgery have 80%+ overlap
2. **CSV Ahead**: Medications and imaging+corticosteroids already implemented
3. **BRIM Ahead**: Surgery extraction proven at 100%, molecular variables validated
4. **Critical Gap**: Survival data missing from both projects
5. **Synergy Opportunity**: Share validated patterns bidirectionally

### Next Steps

1. ✅ **This Week**: Implement Phase 3a_v2 with Athena patient_access
2. ✅ **Next 2 Weeks**: Plan Phase 3b using CSV medications implementation
3. ⏳ **Month 1**: Coordinate radiation implementation between projects
4. ⏳ **Month 2**: Add survival variables to both projects
5. 📊 **Ongoing**: Share validation results and extraction patterns bidirectionally

---

**Overall Assessment**: 🟢 **Strong synergy** between BRIM and CSV projects with 60%+ variable overlap. Significant opportunity to share validated implementations and avoid duplication of effort.

*Last Updated: October 4, 2025*
*Next Review: October 11, 2025*
