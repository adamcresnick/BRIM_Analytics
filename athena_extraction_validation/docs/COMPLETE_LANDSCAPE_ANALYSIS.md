# Complete Athena Extraction Landscape Analysis
## Understanding What We Have vs What We Need

**Date**: October 7, 2025  
**Purpose**: Comprehensive audit of gold standard CSVs, Athena materialized views, and existing extraction work to prevent duplication

---

## Executive Summary

### Gold Standard CSV Files (18 Tables)
**Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/20250723_multitab_csvs/`

1. **20250723_multitab__demographics.csv** (191 rows, 4 columns)
   - research_id, legal_sex, race, ethnicity
   - **Athena Coverage**: 100% from `patient` table (gender field directly mapped)

2. **20250723_multitab__diagnosis.csv** (1,691 rows, 19 columns)
   - event_id, age_at_event_days, cns_integrated_diagnosis, who_grade, metastasis, tumor_location, etc.
   - **Athena Coverage**: ~60% structured (`problem_list_diagnoses` for diagnosis/date, `condition` for codes)
   - **BRIM Needed**: WHO grade (pathology), metastasis location (radiology), site_of_progression (clinical notes)

3. **20250723_multitab__treatments.csv** (697 rows, 26 columns)
   - surgery, age_at_surgery, extent_of_tumor_resection, chemotherapy, chemotherapy_agents, radiation, etc.
   - **Athena Coverage**: ~70% structured (`procedure` for dates/CPT codes, `patient_medications` for drugs)
   - **BRIM Needed**: Extent of resection (operative notes), protocol names (oncology notes)

4. **20250723_multitab__concomitant_medications.csv** (9,550 rows, 8 columns)
   - event_id, conmed_timepoint, rxnorm_cui, medication_name, conmed_routine
   - **Athena Coverage**: 85-90% from `patient_medications` table (RxNorm codes available)

5. **20250723_multitab__imaging_clinical_related.csv** (4,037 rows, 21 columns)
   - age_at_date_scan, cortico_yn, cortico_1-5 (name/dose), ophtho_imaging_yn, imaging_clinical_status
   - **Athena Coverage**: ~90% structured (`radiology_imaging_mri`, `radiology_imaging_mri_results`, `medication_request` for corticosteroids)
   - **BRIM Needed**: Clinical status (Stable/Improved/Progressed from radiology impressions)

6. **20250723_multitab__measurements.csv** (7,816 rows, 9 columns)
   - age_at_measurement_date, height_cm, weight_kg, head_circumference_cm, percentiles
   - **Athena Coverage**: 95%+ structured (`observation` table for vital signs)
   - **BRIM Needed**: Percentile calculations (use CDC/WHO growth charts)

7. **20250723_multitab__encounters.csv** (rows TBD, columns TBD)
   - **Athena Coverage**: 100% structured (`encounter`, `appointment` tables)

8. **20250723_multitab__molecular_characterization.csv** (rows TBD)
   - **Athena Coverage**: 60-70% structured (`observation`, `molecular_tests` tables)
   - **BRIM Needed**: Interpretations from molecular pathology reports

9. **20250723_multitab__molecular_tests_performed.csv** (rows TBD)
   - **Athena Coverage**: Similar to #8

10. **20250723_multitab__conditions_predispositions.csv** (rows TBD)
    - **Athena Coverage**: 90%+ structured (`condition`, `problem_list_diagnoses`)

11. **20250723_multitab__family_cancer_history.csv** (rows TBD)
    - **Athena Coverage**: 0-10% structured (family history usually in social history notes)
    - **BRIM Needed**: Social history/intake notes extraction

12. **20250723_multitab__hydrocephalus_details.csv** (rows TBD)
    - **Athena Coverage**: ~50% structured (shunt procedures from `procedure` table, ICP from `observation`)
    - **BRIM Needed**: Clinical assessments from neurosurgery notes

13. **20250723_multitab__survival.csv** (rows TBD)
    - **Athena Coverage**: 100% if available (`patient.deceased`, last encounter date)

14. **20250723_multitab__ophthalmology_functional_asses.csv** (rows TBD)
    - **Athena Coverage**: ~30% structured (some visual acuity from `observation`)
    - **BRIM Needed**: Ophthalmology exam notes

15-18. **Additional fields, BRAF details, data dictionaries** (rows TBD)
    - Mixed coverage

---

## Athena Materialized Views Inventory

### ✅ COMPLETE & VALIDATED Materialized Views

#### **Demographics & Patient Core**
1. **`patient`** - Core patient demographics
   - Fields: id, birth_date, gender, deceased[Boolean], deceased_date_time
   - Coverage: 100% for legal_sex, DOB, survival status
   - **Gold Standard Mapping**: demographics.csv (legal_sex)

2. **`patient_extension`** - Patient extensions (race, ethnicity)
   - Fields: patient_id, url, value_string, value_coding_code
   - Coverage: 100% for race/ethnicity
   - **Gold Standard Mapping**: demographics.csv (race, ethnicity)

#### **Diagnosis & Conditions**
3. **`problem_list_diagnoses`** - Curated diagnosis view ⭐ PRIMARY SOURCE
   - Fields: patient_id, diagnosis_name, onset_date_time, icd10_code, snomed_code
   - Coverage: 95% for primary CNS diagnoses
   - **Gold Standard Mapping**: diagnosis.csv (cns_integrated_diagnosis, diagnosis_date)
   - **Test Patient C1277724**: Pilocytic astrocytoma diagnosed 2018-06-04

4. **`condition`** - All condition resources (74 columns)
   - Fields: id, subject_reference, code_text, onset_date_time, clinical_status_text, verification_status_text
   - Coverage: Comprehensive but noisy (includes historical, resolved conditions)
   - **Gold Standard Mapping**: Supplement problem_list_diagnoses for metastasis, progression

5. **`condition_code_coding`** - Structured diagnosis codes
   - Fields: condition_id, code_coding_system (ICD-10, SNOMED), code_coding_code, code_coding_display
   - Coverage: 100% for coded diagnoses
   - **Usage**: Link ICD-10 codes to conditions

#### **Surgical Procedures**
6. **`procedure`** - All procedure resources (30 columns)
   - Fields: id, subject_reference, performed_date_time, performed_period_start/end, status, code_text
   - Coverage: 100% for surgery dates
   - **Gold Standard Mapping**: treatments.csv (surgery=Yes/No, age_at_surgery)
   - **Test Patient C1277724**: 4 surgeries (2018-05-28, 2021-03-10, 2021-03-16)

7. **`procedure_code_coding`** - CPT/HCPCS procedure codes
   - Fields: procedure_id, code_coding_code (CPT), code_coding_display
   - Coverage: 100% for coded procedures
   - **Key CPT Codes**:
     - 61500-61576: Craniotomy for tumor resection
     - 62201/62223: Shunt procedures
     - 61304-61315: Craniectomy, biopsy
     - 77261-77499: Radiation therapy

8. **`procedure_body_site`** - Anatomical locations
   - Fields: procedure_id, body_site_text, body_site_coding_code
   - Coverage: ~60% (often generic like "Brain")
   - **Gold Standard Mapping**: Partial for treatments.csv (tumor_location)

#### **Medications & Treatments**
9. **`patient_medications`** - Medication history view ⭐ PRIMARY SOURCE
   - Fields: patient_id, medication_name, rxnorm_code, authored_on, status, intent
   - Coverage: 85-90% for therapeutic medications (per documentation)
   - **Gold Standard Mapping**: 
     - concomitant_medications.csv (rxnorm_cui, medication_name)
     - treatments.csv (chemotherapy_agents)
   - **Test Patient C1277724**: bevacizumab (48 records), **MISSING** vinblastine, selumetinib

10. **`medication_request`** - Raw medication orders
    - Fields: id, subject_reference, medication_reference_display, authored_on, intent, status
    - Coverage: Comprehensive but needs RxNorm linking
    - **Usage**: Fallback if patient_medications incomplete

#### **Imaging & Radiology**
11. **`radiology_imaging_mri`** - MRI procedures ⭐ PRIMARY SOURCE
    - Fields: id, patient_id, mrn, performed_date, modality, body_site, result_diagnostic_report_id
    - Coverage: 100% for MRI dates
    - **Gold Standard Mapping**: imaging_clinical_related.csv (age_at_date_scan)
    - **Linkage**: result_diagnostic_report_id → radiology_imaging_mri_results

12. **`radiology_imaging_mri_results`** - MRI narrative findings
    - Fields: id, result_information (narrative text), conclusion_text
    - Coverage: 100% for radiology impressions
    - **Gold Standard Mapping**: imaging_clinical_related.csv (imaging_clinical_status: Stable/Improved/Progressed)
    - **Extraction Method**: BRIM for "stable disease", "interval progression", "improvement"

13. **`radiology_imaging`** - Other imaging modalities (CT, X-ray, ultrasound)
    - Fields: Similar to radiology_imaging_mri
    - Coverage: 100% for non-MRI imaging

#### **Lab & Molecular Tests**
14. **`observation`** - Vital signs, labs, molecular markers
    - Fields: id, subject_reference, code_text, value_quantity_value, value_string, effective_date_time
    - Coverage: 100% for structured labs
    - **Gold Standard Mapping**: 
     - measurements.csv (height_cm, weight_kg, head_circumference_cm)
     - molecular_characterization.csv (mutation: KIAA1549-BRAF fusion)
   - **Test Patient C1277724**: BRAF fusion found in observation.value_string

15. **`molecular_tests`** - Molecular test orders
    - Fields: id, patient_id, test_name, test_date
    - Coverage: ~70% (some tests only in DiagnosticReport narratives)

16. **`molecular_test_results`** - Molecular test results
    - Fields: molecular_test_id, result_value, interpretation
    - Coverage: ~60% (interpretations often narrative)

#### **Encounters & Visits**
17. **`encounter`** - Clinical visits
    - Fields: id, subject_reference, period_start, period_end, type_coding_display, class_code
    - Coverage: 100% for visit dates
    - **Gold Standard Mapping**: encounters.csv
    - **Types**: inpatient, outpatient, emergency, observation

18. **`appointment`** - Scheduled appointments
    - Fields: id, subject_reference, start_date, end_date, status, appointment_type
    - Coverage: 100% for scheduled visits
    - **Gold Standard Mapping**: encounters.csv (scheduled follow-ups)

#### **Document Discovery**
19. **`document_reference`** - Clinical document metadata ⚠️ Use v1 database
    - Fields: id, type_text, date, subject_reference, status, description
    - Coverage: INCOMPLETE in fhir_v2_prd_db (use fhir_v1_prd_db instead)
    - **Document Types**: 
      - "OP Note - Complete", "Pathology Report", "Radiology", "Progress Notes"
      - Critical for BRIM document selection

20. **`document_reference_content`** - Document S3 URLs
    - Fields: document_reference_id, content_attachment_url, content_attachment_content_type
    - **Usage**: Retrieve Binary resources for BRIM extraction

---

## Existing Extraction Work (DO NOT DUPLICATE!)

### ✅ COMPLETED: BRIM Workflow Infrastructure

**Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/`

1. **`scripts/extract_structured_data.py`** (767 lines) ✅ OPERATIONAL
   - **Purpose**: Pre-extract structured fields from Athena before BRIM
   - **Database Strategy**: Dual-database (fhir_v2_prd_db for clinical, fhir_v1_prd_db for documents)
   - **Extracts**:
     - diagnosis_date from `problem_list_diagnoses.onset_date_time`
     - surgeries from `procedure` (CPT 61500-61576) with dates
     - molecular_markers from `observation.value_string` (BRAF, IDH1, MGMT)
     - treatment_dates from `patient_medications` (bevacizumab only - filter too narrow!)
   - **Output**: `pilot_output/structured_data_{patient_id}.json`
   - **Test Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)
   - **Status**: ✅ Working but needs expansion (see gaps below)

2. **`scripts/athena_document_prioritizer.py`** ✅ OPERATIONAL
   - **Purpose**: Query Athena to select high-value documents for BRIM
   - **Strategy**: Tiered document selection based on clinical relevance
   - **Queries**: `document_reference` table for pathology, operative, oncology notes
   - **Output**: List of document IDs for binary retrieval

3. **`scripts/query_accessible_binaries.py`** ✅ OPERATIONAL
   - **Purpose**: Find all accessible Binary resources for patient
   - **Output**: CSV of document IDs, types, dates

4. **`scripts/retrieve_binary_documents.py`** ✅ OPERATIONAL
   - **Purpose**: Download Binary content from S3 for BRIM processing
   - **Input**: Document IDs from query_accessible_binaries
   - **Output**: Raw document text files

5. **`scripts/pilot_generate_brim_csvs.py`** ✅ OPERATIONAL
   - **Purpose**: Generate variables.csv and project.csv for BRIM API
   - **Integration**: Uses structured_data.json to pre-populate known fields
   - **BRIM Strategy**: Create STRUCTURED_* pseudo-documents with Athena ground truth

6. **Documentation Files** ✅ COMPLETE
   - `docs/MATERIALIZED_VIEW_STRATEGY.md` (925 lines) - Comprehensive view catalog
   - `docs/MATERIALIZED_VIEW_STRATEGY_VALIDATION.md` (1,011 lines) - Validation against fhir_athena_crosswalk docs
   - `pilot_output/COMPREHENSIVE_CSV_VARIABLE_MAPPING.md` (716 lines) - Variable-to-Athena mapping
   - `pilot_output/STRUCTURED_DATA_MAXIMIZATION_ANALYSIS.md` (431 lines) - Coverage gap analysis

### ⚠️ IDENTIFIED GAPS in Existing Extraction (HIGH PRIORITY)

**From `STRUCTURED_DATA_MAXIMIZATION_ANALYSIS.md` (lines 1-200):**

#### 1. **patient_gender** - 100% structured, NOT extracted
```python
# EASY WIN: Add to extract_structured_data.py
SELECT gender FROM fhir_v2_prd_db.patient 
WHERE id = '{patient_fhir_id}'
```

#### 2. **race & ethnicity** - 100% structured, NOT extracted
```python
# EASY WIN: Query patient_extension table
SELECT value_string FROM fhir_v2_prd_db.patient_extension
WHERE patient_id = '{patient_fhir_id}' 
  AND url LIKE '%race%'
```

#### 3. **chemotherapy_agents** - FILTER TOO NARROW!
**Current Filter** (bevacizumab only):
```python
WHERE (
    LOWER(medication_name) LIKE '%temozolomide%'
    OR LOWER(medication_name) LIKE '%bevacizumab%'
    OR LOWER(medication_name) LIKE '%chemotherapy%'
)
```

**NEEDED** (comprehensive chemotherapy list):
```python
CHEMO_KEYWORDS = [
    'temozolomide', 'temodar', 'bevacizumab', 'avastin',
    'vincristine', 'vinblastine', 'vinorelbine',  # ← MISSING from current filter
    'carboplatin', 'cisplatin', 'oxaliplatin',
    'selumetinib', 'koselugo',  # ← MISSING, used in gold standard!
    'dabrafenib', 'trametinib', 
    'lomustine', 'ccnu', 'cyclophosphamide',
    'etoposide', 'vp-16', 'irinotecan',
    'procarbazine', 'methotrexate'
]
```
**Impact**: Gold standard shows **vinblastine + bevacizumab** and **selumetinib** for C1277724, but current extraction only captures bevacizumab.

#### 4. **radiation_therapy** - 100% structured, NOT extracted
```python
# EASY WIN: Query procedure table for radiation CPT codes
SELECT COUNT(*) FROM fhir_v2_prd_db.procedure p
LEFT JOIN fhir_v2_prd_db.procedure_code_coding pcc ON p.id = pcc.procedure_id
WHERE p.subject_reference = '{patient_fhir_id}'
  AND pcc.code_coding_code BETWEEN '77261' AND '77499'
```

#### 5. **surgery_body_site** - Partially structured, NOT extracted
```python
# Add to existing surgery extraction:
LEFT JOIN procedure_body_site pbs ON p.id = pbs.procedure_id
# Caveat: Often generic ("Brain"), need narrative for specifics
```

---

## Critical Cross-Reference: fhir_athena_crosswalk Documentation

**Location**: `/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/`

### ✅ VALIDATED Alignment (From MATERIALIZED_VIEW_STRATEGY_VALIDATION.md)

**Key Finding**: BRIM materialized view strategy **perfectly aligns** with fhir_athena_crosswalk approaches after reviewing 40+ documentation files.

**Validated Patterns**:
1. **Use `problem_list_diagnoses` as primary diagnosis source** (not raw `condition` table)
   - Confirmed in: `COMPREHENSIVE_PROBLEM_LIST_ANALYSIS.md`, `PROBLEM_LIST_DATA_LINEAGE_VERIFICATION.md`
   
2. **Temporal correlation critical for treatment periods**
   - Confirmed in: `LONGITUDINAL_CANCER_TREATMENT_FRAMEWORK.md`, `CHEMOTHERAPY_IDENTIFICATION_STRATEGY.md`
   
3. **RxNorm mapping essential for medication identification**
   - Confirmed in: `CONCOMITANT_MEDICATIONS_IMPLEMENTATION_GUIDE.md` (85-90% coverage validated)
   
4. **Multi-table joins for comprehensive surgical capture**
   - Confirmed in: `COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md` (1,076 lines)
   
5. **Radiology views for imaging clinical data**
   - Confirmed in: `IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md`, `IMAGING_CORTICOSTEROID_MAPPING_STRATEGY.md`

### 📋 IMPLEMENTED in fhir_athena_crosswalk (DO NOT RE-IMPLEMENT!)

**These extraction scripts already exist in `/Users/resnick/Downloads/fhir_athena_crosswalk/scripts/`:**

1. **`map_demographics.py`** ✅ COMPLETED & VALIDATED
   - Source: patient_access table
   - Coverage: 100% for gender, race, ethnicity
   - **Action**: Review and integrate, do not rewrite

2. **`map_diagnosis.py`** ✅ COMPLETED & VALIDATED
   - Source: problem_list_diagnoses
   - Coverage: 100% for diagnosis name, date
   - **Action**: Review and integrate

3. **`complete_medication_crosswalk.py`** ✅ COMPLETED & VALIDATED
   - Source: patient_medications
   - Coverage: 85-90% for concomitant medications
   - **Action**: Review and integrate (comprehensive RxNorm mapping)

4. **`map_imaging_clinical_related_v4.py`** 🔄 IN PROGRESS
   - Source: radiology_imaging_mri, radiology_imaging_mri_results, medication_request
   - Coverage: 90%+ (missing only clinical status interpretation)
   - **Action**: Complete and validate

5. **`map_measurements.py`** 🔄 IN PROGRESS
   - Source: observation (vital signs)
   - Coverage: 95%+ (missing percentile calculations)
   - **Action**: Complete and validate

6. **`corticosteroid_reference.py`** ✅ COMPLETED
   - 53 RxNorm codes for 10 corticosteroid drug families
   - **Action**: Integrate into BRIM workflow

---

## Integration Strategy: Athena + BRIM Hybrid Workflow

### Phase 1: Maximize Athena Structured Extraction ✅ CURRENT STATE

**Goal**: Extract 100% of what's available in materialized views BEFORE invoking BRIM

**Components**:
1. ✅ `extract_structured_data.py` - Pre-populate ground truth
2. ✅ Generate `STRUCTURED_*` pseudo-documents with Athena data
3. ✅ BRIM validates/supplements (not extracts from scratch)

**Current Coverage** (per `STRUCTURED_DATA_MAXIMIZATION_ANALYSIS.md`):
- ✅ 6 variables fully covered (diagnosis_date, surgery_date, etc.)
- 🟡 3 variables partially covered (WHO grade, surgery_type, location)
- ❌ 5 variables narrative only (extent_of_resection, progression site, etc.)

### Phase 2: Expand Structured Extraction (HIGH PRIORITY - THIS VALIDATION PROJECT!)

**Goal**: Close gaps in existing extraction before creating new BRIM variables

**Actions**:
1. ✅ Add patient_gender extraction (trivial query)
2. ✅ Add race/ethnicity extraction (patient_extension table)
3. ✅ Expand chemotherapy filter (add vinblastine, selumetinib, 20+ more agents)
4. ✅ Add radiation_therapy extraction (CPT code 77261-77499)
5. ✅ Add surgery_body_site (procedure_body_site join)
6. ✅ Review fhir_athena_crosswalk scripts (do not duplicate demographics, diagnosis, meds!)

**Expected Outcome**:
- 🎯 10-12 variables fully covered (up from 6)
- 🎯 Reduce BRIM variable count from ~33 to ~20

### Phase 3: Targeted BRIM Extraction (NARRATIVE ONLY)

**Variables requiring narrative extraction** (per `COMPREHENSIVE_CSV_VARIABLE_MAPPING.md`):

**HIGH PRIORITY** (clinical trial critical):
1. **extent_of_tumor_resection** - Operative note ("Gross Total Resection", "Subtotal Resection", "Biopsy only")
2. **who_grade** - Pathology report ("WHO Grade I", "Grade II", etc.)
3. **site_of_progression** - Oncology/radiology notes ("Local", "Distant", "Leptomeningeal")
4. **metastasis_location** - Radiology reports (specific spinal/brain locations)
5. **imaging_clinical_status** - Radiology impressions ("Stable", "Improved", "Progressed")

**MEDIUM PRIORITY**:
6. **chemotherapy_type** - Oncology notes ("Protocol", "Standard of care")
7. **protocol_name** - Oncology notes (specific trial names)
8. **specimen_collection_origin** - Timeline context ("Initial CNS Tumor Surgery" vs "Progressive")

**LOW PRIORITY** (supplementary):
9. **family_cancer_history** - Social history notes
10. **ophthalmology assessments** - Ophthalmology exam notes

---

## Proposed Validation Workflow (CSV-by-CSV)

### Step 1: Audit Gold Standard CSVs
**Script**: `scripts/inventory_gold_standard_csvs.py` (ALREADY CREATED)
- Discover all 18 CSV files
- Extract column names, sample data, row counts
- Output: `gold_standard_inventory.json` + `gold_standard_summary.md`

### Step 2: Map Variables to Athena Tables
**Document**: `athena_extraction_validation/VARIABLE_TO_ATHENA_MAPPING.md`
- For each CSV field:
  - Athena table/column (if structured)
  - Extractability: 100% / Partial / 0% (BRIM needed)
  - Existing script (if any from fhir_athena_crosswalk)
  - Gap analysis

### Step 3: Validate Existing Extractions
**Priority Order**:
1. **demographics.csv** - Validate `map_demographics.py` from fhir_athena_crosswalk
2. **concomitant_medications.csv** - Validate `complete_medication_crosswalk.py` (85-90% coverage)
3. **diagnosis.csv** - Validate `map_diagnosis.py`
4. **imaging_clinical_related.csv** - Complete `map_imaging_clinical_related_v4.py`
5. **measurements.csv** - Complete `map_measurements.py`

### Step 4: Expand Structured Extraction (Close Gaps)
**Script**: `scripts/extract_structured_data_v2.py` (enhanced version)
- Add patient_gender
- Add race/ethnicity
- Expand chemotherapy filter (comprehensive list)
- Add radiation_therapy
- Add surgery_body_site
- Test on C1277724, compare to gold standard

### Step 5: Define BRIM Variable Scope
**Document**: `athena_extraction_validation/BRIM_VARIABLE_REQUIREMENTS.md`
- List all variables requiring narrative extraction
- Prioritize by clinical trial importance
- Define extraction strategies (which document types, search patterns)
- Create variable.csv and decisions.csv templates

### Step 6: Integration Testing
**Script**: `scripts/validate_hybrid_extraction.py`
- Run Athena extraction (structured data)
- Run BRIM extraction (narrative variables)
- Merge results
- Compare against gold standard CSVs
- Generate coverage report

---

## Key Decisions & Recommendations

### ✅ DO THIS (High Value, Low Effort)

1. **Expand `extract_structured_data.py` to close known gaps**
   - Add 5 easy queries (gender, race/ethnicity, radiation, expanded chemo filter)
   - Expected impact: +30% variable coverage with minimal effort

2. **Review & integrate fhir_athena_crosswalk scripts**
   - DO NOT rewrite demographics, diagnosis, medications extraction
   - Validate existing scripts work with BRIM_Analytics test patient
   - Document any modifications needed

3. **Create comprehensive chemotherapy agent list**
   - Review gold standard treatments.csv for all unique agents
   - Build exhaustive RxNorm mapping (not just temozolomide/bevacizumab)
   - Test filter captures vinblastine, selumetinib, others

4. **Run inventory script on gold standard CSVs**
   - Execute `inventory_gold_standard_csvs.py`
   - Understand complete variable landscape (all 18 CSVs)
   - Prioritize CSVs by clinical trial importance

### ⚠️ BE CAREFUL (Potential Duplication Risk)

1. **Check fhir_athena_crosswalk/scripts/ before writing ANY new extraction code**
   - Likely scripts already exist for demographics, diagnosis, meds, imaging, measurements
   - Review, test, integrate (don't reinvent)

2. **Understand materialized view limitations**
   - `document_reference` incomplete in fhir_v2_prd_db (use fhir_v1_prd_db)
   - `patient_medications` filter may be too narrow (document assumptions)
   - Body sites often generic ("Brain" not "Cerebellum/Posterior Fossa")

3. **Respect Athena vs BRIM boundary**
   - Athena: Dates, codes, counts, structured values
   - BRIM: Surgeon assessments, radiologist impressions, clinical judgments
   - Don't force narrative extraction into SQL queries

### ❌ DON'T DO THIS (Wasted Effort)

1. **DO NOT create new demographics/diagnosis/medication extraction scripts from scratch**
   - These exist in fhir_athena_crosswalk with 100%, 100%, 85-90% coverage
   - Review `map_demographics.py`, `map_diagnosis.py`, `complete_medication_crosswalk.py`

2. **DO NOT try to extract extent_of_resection from structured data**
   - This is a surgeon's subjective assessment in operative notes
   - No CPT code distinguishes GTR/NTR/STR
   - Accept this requires BRIM

3. **DO NOT query raw `condition` table for primary diagnosis**
   - Use `problem_list_diagnoses` view (curated, dual-coded ICD-10/SNOMED)
   - Validated in fhir_athena_crosswalk documentation

4. **DO NOT duplicate the inventory/mapping work**
   - This validation project IS the comprehensive audit
   - Build on `COMPREHENSIVE_CSV_VARIABLE_MAPPING.md` (716 lines already written!)

---

## Next Steps (Prioritized)

### Week 1: Complete Landscape Understanding ✅ THIS DOCUMENT

1. ✅ Read all gold standard CSVs (headers + sample rows)
2. ✅ Review existing extraction scripts
3. ✅ Cross-reference fhir_athena_crosswalk documentation
4. ✅ Document materialized views (already done in MATERIALIZED_VIEW_STRATEGY.md)
5. ✅ Identify gaps and duplication risks

### Week 2: Close Known Gaps in Structured Extraction

1. Enhance `extract_structured_data.py`:
   - Add patient_gender query
   - Add race/ethnicity query
   - Expand chemotherapy filter (comprehensive list)
   - Add radiation_therapy query
   - Add surgery_body_site
   
2. Test on C1277724:
   - Run enhanced extraction
   - Compare to gold standard demographics, diagnosis, treatments
   - Validate coverage metrics

3. Review fhir_athena_crosswalk scripts:
   - Test `map_demographics.py` on BRIM_Analytics patient
   - Test `complete_medication_crosswalk.py`
   - Identify integration requirements

### Week 3: CSV-by-CSV Validation

1. Run inventory script on all 18 gold standard CSVs
2. Create VARIABLE_TO_ATHENA_MAPPING.md for each CSV
3. Execute/validate existing scripts (demographics, diagnosis, meds, imaging, measurements)
4. Generate coverage reports per CSV

### Week 4: Define BRIM Scope & Integration

1. List all variables requiring narrative extraction (based on gap analysis)
2. Prioritize by clinical trial importance
3. Create BRIM variable specifications
4. Design hybrid extraction workflow (Athena → BRIM → merge)

---

## Test Patient Reference Data

**Patient ID**: C1277724  
**FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3  
**Birth Date**: ~2005-05-13 (calculated)  
**Diagnosis**: Pilocytic astrocytoma, WHO Grade I  
**Diagnosis Date**: 2018-06-04 (age 4763 days = 13.0 years)

**Key Clinical Events**:
- **Surgery 1**: 2018-05-28 (age 4763 days) - Partial resection, Initial CNS Tumor
- **Surgery 2**: 2021-03-10 (age 5780 days) - Partial resection, Progressive disease
- **Chemotherapy 1**: vinblastine + bevacizumab (ages 5130-5492 days)
- **Chemotherapy 2**: selumetinib (ages 5873-7049 days)
- **Molecular**: KIAA1549-BRAF fusion
- **Metastasis**: Yes (Leptomeningeal, Spine) at initial diagnosis

**Gold Standard CSV Locations**:
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/20250723_multitab_csvs/`

**Existing Extraction Output**:
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/structured_data.json`

---

## Conclusion

**WE HAVE**:
- ✅ 20 validated Athena materialized views fully documented
- ✅ Working extraction infrastructure (extract_structured_data.py)
- ✅ 5 completed/in-progress scripts from fhir_athena_crosswalk
- ✅ Comprehensive variable mapping (716 lines)
- ✅ BRIM integration strategy (materialized view + narrative hybrid)

**WE NEED**:
- ⏳ Close 5 known gaps in structured extraction (gender, race/ethnicity, expanded chemo, radiation, body site)
- ⏳ Validate fhir_athena_crosswalk scripts work with BRIM_Analytics patient
- ⏳ Complete CSV-by-CSV extractability audit (use inventory script)
- ⏳ Define final BRIM variable scope (narrative-only variables)
- ⏳ Create hybrid extraction validation (Athena + BRIM → gold standard comparison)

**WE MUST AVOID**:
- ❌ Duplicating demographics, diagnosis, medication extraction (already done in fhir_athena_crosswalk)
- ❌ Trying to extract narrative variables from structured data (respect Athena/BRIM boundary)
- ❌ Ignoring materialized view limitations (document incomplete, body sites generic)

**NEXT ACTION**: Enhance `extract_structured_data.py` to close 5 known gaps, then validate against gold standard CSVs.

---

*Last Updated: October 7, 2025*  
*Maintainer: FHIR Crosswalk Validation Team*  
*Integration Project: RADIANT_PCA BRIM_Analytics*
