# CSV-by-CSV Validation Progress Tracker

**Test Patient**: C1277724  
**FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3  
**Started**: October 7, 2025  
**Strategy**: Systematic validation of all 18 gold standard CSVs against Athena extraction

---

## Validation Status Overview

| # | CSV | Rows | Fields | Accuracy | Status | Report | Extraction Script |
|---|-----|------|--------|----------|--------|--------|-------------------|
| 1 | demographics | 189 | 4 | **100.0%** | ✅ COMPLETE | [demographics_validation.md](reports/demographics_validation.md) | ⏳ To Create |
| 2 | diagnosis | 1,689 | 20 | **61.4%** | ✅ IMPROVED | [diagnosis_validation.md](reports/diagnosis_validation.md) | ✅ **extract_diagnosis.py** |
| 3 | treatments | 695 | 27 | - | ⏳ PENDING | - | ⏳ To Create |
| 4 | concomitant_medications | 9,548 | 8 | - | ⏳ PENDING | - | ⏳ To Create |
| 5 | molecular_characterization | 52 | 2 | **50%** | 🔍 ANALYZED | [MOLECULAR_DATA_GAP_ANALYSIS.md](MOLECULAR_DATA_GAP_ANALYSIS.md) | ⏳ BRIM Required |
| 6 | molecular_tests_performed | 131 | 3 | **67%** | 🔍 ANALYZED | [MOLECULAR_DATA_GAP_ANALYSIS.md](MOLECULAR_DATA_GAP_ANALYSIS.md) | ⏳ To Create |
| 7 | encounters | 1,717 | 8 | - | ⏳ PENDING | - |
| 8 | conditions_predispositions | 1,064 | 6 | - | ⏳ PENDING | - |
| 9 | family_cancer_history | 242 | 6 | - | ⏳ PENDING | - |
| 10 | hydrocephalus_details | 277 | 10 | - | ⏳ PENDING | - |
| 11 | imaging_clinical_related | 4,035 | 21 | - | ⏳ PENDING | - |
| 12 | measurements | 7,814 | 9 | - | ⏳ PENDING | - |
| 13 | survival | 189 | 6 | - | ⏳ PENDING | - |
| 14 | ophthalmology_functional_asses | 1,258 | 57 | - | ⏳ PENDING | - |
| 15 | additional_fields | 189 | 8 | - | ⏳ PENDING | - | ⏳ To Create |
| 16 | braf_alteration_details | 232 | 10 | **40%** | 🔍 ANALYZED | [MOLECULAR_DATA_GAP_ANALYSIS.md](MOLECULAR_DATA_GAP_ANALYSIS.md) | ⏳ To Create + BRIM |
| 17 | data_dictionary | 67 | 13 | - | 📋 REFERENCE | - |
| 18 | data_dictionary_custom_forms | 111 | 12 | - | 📋 REFERENCE | - |

**Overall Progress**: 1/16 validated (6.25%) - excluding reference dictionaries

---

## Detailed Results

### ✅ CSV 1: demographics.csv - VALIDATED

**Date**: October 7, 2025 10:03:51  
**Accuracy**: 100.0% (3/3 fields matched)  
**Completeness**: 100.0%  
**Athena Table**: `patient_access`

#### Fields Validated:
- ✅ `legal_sex`: Female (from `patient_access.gender`)
- ✅ `race`: White (from `patient_access.race`)
- ✅ `ethnicity`: Not Hispanic or Latino (from `patient_access.ethnicity`)

#### Athena Query:
```sql
SELECT id, gender, birth_date, race, ethnicity
FROM fhir_v2_prd_db.patient_access
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

#### Key Findings:
1. **All fields 100% structured** - No BRIM extraction needed
2. **patient_access table confirmed reliable** - Contains race/ethnicity from US Core extensions
3. **Gender mapping works correctly** - "female" → "Female"
4. **Birth date available** - 2005-05-13 (for age calculations)

#### Recommendations:
- Document as REFERENCE extraction for other patients
- Use this extraction as foundation for age calculations across all other CSVs
- Move to next CSV: diagnosis.csv

---

### ⏳ CSV 2: diagnosis.csv - PENDING

**Rows**: 1,689  
**Fields**: 20  
**Expected Coverage**: 60% structured, 40% hybrid/narrative

#### Fields to Validate:
- `research_id` - Manual mapping
- `event_id` - Generated identifier
- `age_at_event_days` - Calculated (birth_date + onset_date)
- `clinical_status_at_event` - patient.deceased boolean
- `event_type` - Timeline analysis (Initial vs Progressive)
- `cns_integrated_diagnosis` - ✅ Already extracted (problem_list_diagnoses)
- `who_grade` - HYBRID (condition.stage OR pathology)
- `tumor_location` - HYBRID (condition.bodySite OR narrative)
- `metastasis` - HYBRID (condition codes OR narrative)
- `metastasis_location` - NARRATIVE (radiology reports)
- `site_of_progression` - NARRATIVE (oncology notes)
- `tumor_or_molecular_tests_performed` - molecular_tests table
- `shunt_required` - procedure table (CPT 62201, 62223)
- `autopsy_performed` - document_reference search
- `cause_of_death` - HYBRID (patient.deceased reason OR narrative)

#### Athena Tables Needed:
- `problem_list_diagnoses` (primary diagnosis)
- `condition` + `condition_code_coding` (metastasis, grade)
- `procedure` + `procedure_code_coding` (shunt)
- `molecular_tests` (test types)
- `patient` (clinical status)

#### Critical Dependencies:
1. Event timeline logic (cluster resources by date)
2. WHO grade extraction (likely not coded, need BRIM)
3. Metastasis detection (ICD-10 codes for metastatic disease)

---

### ⏳ CSV 3: treatments.csv - PENDING

**Rows**: 695  
**Fields**: 27  
**Expected Coverage**: 63% structured, 37% hybrid/narrative  
**🔴 CRITICAL**: Chemotherapy filter gap (only 33% recall)

#### Fields to Validate:
**Surgery** (4 fields):
- `surgery` - procedure COUNT > 0
- `age_at_surgery` - ✅ Already extracted
- `extent_of_tumor_resection` - NARRATIVE (operative notes)
- `specimen_collection_origin` - HYBRID (timeline + context)

**Chemotherapy** (7 fields):
- `chemotherapy` - ✅ Already extracted (boolean)
- `chemotherapy_agents` - ⚠️ PARTIAL (33% - missing vinblastine, selumetinib)
- `age_at_chemo_start` - ✅ Already extracted
- `age_at_chemo_stop` - Need to add (patient_medications.end_date)
- `chemotherapy_type` - NARRATIVE (protocol vs standard)
- `protocol_name` - NARRATIVE (trial names)
- `autologous_stem_cell_transplant` - procedure (CPT 38241)

**Radiation** (6 fields):
- `radiation` - ✅ Already extracted (boolean)
- `radiation_type` - HYBRID (procedure.code OR narrative)
- `radiation_site` - HYBRID (procedure.bodySite OR narrative)
- `total_radiation_dose` - HYBRID (observation OR narrative)
- `age_at_radiation_start` - procedure.performed_period.start
- `age_at_radiation_stop` - procedure.performed_period.end

**Other** (3 fields):
- `treatment_status` - Timeline comparison
- `reason_for_treatment_change` - NARRATIVE

#### Gold Standard C1277724:
- Event 1: Surgery at age 4763 (partial resection)
- Event 2: **vinblastine + bevacizumab** at ages 5130-5492
- Event 3: Surgery at age 5780 + **selumetinib** at ages 5873-7049

#### Known Issues:
1. **CRITICAL**: Chemotherapy filter only finds bevacizumab (1/3 agents)
2. Missing: age_at_chemo_stop extraction
3. Missing: radiation date extraction
4. Missing: stem cell transplant detection

---

## Next Steps

### Immediate Actions:

1. **✅ DONE**: Validate demographics.csv (100% passed)

2. **⏳ NEXT**: Create diagnosis.csv validation script
   - Query problem_list_diagnoses for diagnosis name/date
   - Query condition table for metastasis codes
   - Query procedure for shunt procedures
   - Query molecular_tests for test types
   - Calculate age_at_event from birth_date
   - Compare against gold standard
   - Expected: 60% accuracy (structured only)

3. **🔴 CRITICAL**: Fix chemotherapy filter BEFORE treatments validation
   - Add vinblastine, selumetinib, carboplatin, cisplatin, lomustine to CHEMO_KEYWORDS
   - Expected improvement: 33% → 100% agent recall

4. **Continue systematic validation**:
   - Complete all 16 clinical CSVs
   - Document accuracy per CSV
   - Identify gaps requiring BRIM
   - Prioritize fixes by impact

### Validation Workflow (Per CSV):

```
For each CSV:
  1. Review gold standard structure (columns, sample values)
  2. Map columns to Athena tables/fields
  3. Create validation script (similar to demographics)
  4. Execute query for C1277724
  5. Compare extracted vs gold standard
  6. Calculate accuracy metrics
  7. Generate validation report
  8. Document gaps and recommendations
  9. Update this tracker
  10. Move to next CSV
```

### Success Criteria:

- **Tier 1 (High Priority)**: demographics, diagnosis, treatments, concomitant_medications
  - Target: 75-100% accuracy for structured fields
  - Complete by: End of Week 1

- **Tier 2 (Medium Priority)**: encounters, molecular, measurements, imaging
  - Target: 70-95% accuracy
  - Complete by: End of Week 2

- **Tier 3 (Lower Priority)**: conditions, family_history, hydrocephalus, ophthalmology, additional_fields, braf_details, survival
  - Target: 60-90% accuracy
  - Complete by: End of Week 3

### Expected Outcomes:

By completing this systematic validation, we will:
1. **Confirm Athena extraction capacity** for each CSV
2. **Identify critical gaps** requiring immediate fixes
3. **Document BRIM requirements** for narrative-only fields
4. **Establish accuracy baselines** for each data category
5. **Create reusable validation scripts** for future patients
6. **Build confidence** in hybrid Athena + BRIM approach

---

## Validation Scripts

### Created:
- ✅ `validate_demographics_csv.py` - 100% working

### To Create:
- ⏳ `validate_diagnosis_csv.py` - Next
- ⏳ `validate_treatments_csv.py` - After diagnosis
- ⏳ `validate_concomitant_medications_csv.py`
- ⏳ `validate_molecular_characterization_csv.py`
- ⏳ `validate_molecular_tests_performed_csv.py`
- ⏳ `validate_encounters_csv.py`
- ⏳ ... (one per CSV)

---

**Last Updated**: October 7, 2025 10:05:00  
**Status**: In Progress (1/16 complete)  
**Next Validation**: diagnosis.csv
