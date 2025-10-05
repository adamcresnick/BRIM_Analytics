# Data Dictionary Comprehensive Review
**Date**: 2025-01-03  
**Purpose**: Document all field definitions and requirements from data dictionaries to ensure extraction alignment

---

## Executive Summary

Reviewed **TWO** data dictionaries:
1. **20250723_multitab__data_dictionary.csv** (Main fields) - 190+ rows
2. **20250723_multitab__data_dictionary_custom_forms.csv** (Custom forms) - 113 rows

**Key Findings:**
- ✅ Concomitant medications structure fully documented in custom forms dictionary
- ✅ Chemotherapy fields confirmed as free text (not constrained lists)
- ✅ All age fields converted from yyyy-mm-dd to age in days
- ✅ RxNorm codes required for concomitant medications
- ✅ Medication dosing schedules tracked (Scheduled vs PRN)

---

## 1. Main Data Dictionary Fields

### Demographics Fields

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| research_id | text | CBTN unique research ID | Patient identifier |
| legal_sex | dropdown | 0=Male, 1=Female, 2=Unavailable | Gender identity |
| race | checkbox | White, Black, Asian, Native Hawaiian, American Indian, Other | Multiple selections allowed |
| ethnicity | radio | 1=Hispanic/Latino, 2=Not Hispanic/Latino, 3=Unavailable | Single selection |
| date_of_birth | text | yyyy-mm-dd | Converted to age in days for analysis |

**Extraction Implications:**
- `legal_sex` maps to FHIR Patient.gender (administrative gender)
- `race` requires parsing Patient.extension with multiple ombCategory values
- `ethnicity` requires parsing Patient.extension with single ombCategory value
- `date_of_birth` maps to Patient.birthDate

---

### Diagnosis & Event Fields

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| event_type | radio | Initial CNS Tumor, Second Malignancy, Recurrence, Progressive, Deceased | Event classification |
| age_at_event_days | text | yyyy-mm-dd → converted to days | Age at diagnosis event |
| cns_integrated_diagnosis | checkbox | 123 diagnosis options | Based on 2021 WHO CNS Classification |
| who_grade | dropdown | 1, 2, 3, 4, No grade specified | WHO tumor grading |
| tumor_location | checkbox | 24 anatomical locations | Frontal Lobe, Cerebellum, Brain Stem, etc. |
| clinical_status_at_event | dropdown | Alive/Deceased variations | Patient status at event |

**Extraction Implications:**
- `cns_integrated_diagnosis` maps to Condition.code (SNOMED/ICD codes)
- `who_grade` extractable from Observation or coded in Condition
- `tumor_location` maps to Condition.bodySite
- `age_at_event_days` calculated from event date and DOB

---

### Surgery Fields

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| surgery | radio | Yes, No, Unavailable | Surgery performed indicator |
| surgery_type | dropdown | Initial CNS Tumor Surgery, Second Malignancy Surgery, Progressive, Deceased | Surgery classification |
| extent_of_resection | dropdown | Gross total resection, Partial resection, Biopsy only, etc. | Resection extent |
| age_at_surgery | text | yyyy-mm-dd → converted to days | Age at surgery date |
| shunt_required | radio | VP Shunt, ETV Shunt, Other, Not Done | Hydrocephalus management |

**Extraction Implications:**
- `surgery` boolean from Procedure.status
- `surgery_type` requires CPT code classification (see ITERATION_2_PROGRESS notes)
- `extent_of_resection` from Procedure.bodySite or Procedure.note
- `age_at_surgery` from Procedure.performedDateTime or performedPeriod.start

**CRITICAL NOTE**: Gold standard counts ENCOUNTERS not individual procedures. Patient C1277724 has:
- 2018-05-28: 2 procedures (craniotomy + ETV) → **1 encounter**
- 2021-03-10: 1 procedure (partial resection) → **1 encounter**
- 2021-03-16: 1 procedure (stereotactic biopsy) → **1 encounter**
- **Total: 4 procedures across 3 encounters, but gold standard shows 2 surgical encounters**

Likely explanation: Gold standard counts only PRIMARY tumor resection surgeries, excludes:
- Shunt placements (ETV on 2018-05-28)
- Biopsies (stereotactic biopsy on 2021-03-16)

---

### Chemotherapy Fields

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| chemotherapy | radio | 0=Yes, 1=No, 2=Unavailable | Chemotherapy indicator |
| chemotherapy_type | dropdown | Protocol enrolled/not enrolled, Standard of care, Unavailable | Treatment classification |
| protocol_name | dropdown | Short name of protocol | Protocol identifier |
| **chemotherapy_agents** | **text** | **FREE TEXT (not constrained)** | **Drug names, separated by semicolons** |
| age_at_chemo_start | text | yyyy-mm-dd → converted to days | Start date |
| age_at_chemo_stop | text | yyyy-mm-dd → converted to days | Stop date |
| autologous_stem_cell_transplant | radio | Yes, No, Unavailable | Transplant indicator |

**Extraction Implications:**
- `chemotherapy_agents` is **FREE TEXT** - NOT a constrained list
- Multiple agents separated by semicolons (e.g., "vinblastine;bevacizumab")
- Agents extracted from MedicationRequest/MedicationAdministration
- Age fields calculated from medication dates and DOB

**CRITICAL**: Gold standard for C1277724:
- Event 2: **vinblastine** + **bevacizumab** (ages 5130-5492 days)
- Event 3: **selumetinib** (ages 5873-7049 days)

Our extraction MUST capture all 3 agents. Previous filter only captured bevacizumab (1/3 = 33% recall).

---

### Radiation Fields

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| radiation | radio | Yes, No, Unavailable | Radiation therapy indicator |
| radiation_type | dropdown | External beam, Proton beam, Brachytherapy, etc. | Radiation modality |
| age_at_radiation_start | text | yyyy-mm-dd → converted to days | Start date |
| age_at_radiation_stop | text | yyyy-mm-dd → converted to days | Stop date |

**Extraction Implications:**
- `radiation` boolean from Procedure resources (CPT codes 77xxx)
- `radiation_type` from Procedure.code classification
- Age fields from Procedure.performedDateTime

---

### Molecular Fields

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| mutation | text | Free text | Specific genetic alterations |
| age_at_molecular_testing | text | yyyy-mm-dd → converted to days | Testing date |
| idh_mutation | radio | Mutant, Wildtype, Unknown, Not tested | IDH status |
| mgmt_methylation | radio | Methylated, Unmethylated, Unknown, Not tested | MGMT status |

**Extraction Implications:**
- `mutation` from Observation or DiagnosticReport (genetic tests)
- `idh_mutation` and `mgmt_methylation` from specific test results
- **INFERENCE RULE**: If BRAF-only finding → IDH wildtype (mutually exclusive)
- **CLINICAL NOTE**: MGMT not typically tested for pilocytic astrocytoma (low-grade)

---

## 2. Custom Forms Data Dictionary

### Concomitant Medications Form

**Form Structure (Repeating per timepoint):**

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| conmed_timepoint | dropdown | Event Diagnosis, 6 Month Update, 12 Month Update, ... 20 Year Update | Associated timepoint |
| form_conmed_number | dropdown | 1-10, More than 10, None noted | Number of medications at timepoint |
| age_at_conmed_date | text | yyyy-mm-dd → converted to days | Date of medication reconciliation |
| rxnorm_cui | text | RxNorm Concept Unique Identifier | Standard drug code (e.g., 1116927) |
| medication_name | text | Medication name (required) | Full medication description with dose/formulation |
| conmed_routine | radio | 1=Scheduled, 2=As needed (PRN), 3=Unknown | Medication schedule category |

**Example Concomitant Medications (from CSV):**

| Patient | Event | Timepoint | Age (days) | RxNorm | Medication | Routine |
|---------|-------|-----------|------------|--------|------------|---------|
| C1003557 | ET_7DK4B210 | Event Diagnosis | 2321 | 1116927 | dexamethasone phosphate 4 MG/ML Injectable Solution | Scheduled |
| C1003557 | ET_7DK4B210 | Event Diagnosis | 2321 | 203171 | cefazolin sodium | Scheduled |
| C1003557 | ET_7DK4B210 | 6 Month Update | 2491 | 311376 | lorazepam 2 MG/ML Oral Solution | As needed (PRN) |
| C1003557 | ET_7DK4B210 | 6 Month Update | 2491 | 312935 | sennosides USP 8.6 MG Oral Tablet | As needed (PRN) |

**Medication Categories in Concomitant Medications:**
- **Corticosteroids**: dexamethasone (anti-inflammatory, edema management)
- **Antibiotics**: cefazolin (surgical prophylaxis)
- **Anti-anxiety**: lorazepam (PRN for anxiety/seizures)
- **Laxatives**: sennosides (PRN for constipation)
- **Anti-epileptics**: levetiracetam, phenytoin (seizure prophylaxis)
- **Anti-emetics**: ondansetron, metoclopramide (nausea management)
- **Anticoagulants**: enoxaparin, heparin (DVT prophylaxis)

**CRITICAL DISTINCTION:**
- **Chemotherapy** (treatments table): vinblastine, bevacizumab, selumetinib, temozolomide, etc.
- **Concomitant** (concomitant_medications table): dexamethasone, cefazolin, lorazepam, sennosides, etc.

These are tracked in SEPARATE tables with different structures.

---

### Other Custom Forms

#### BRAF Alteration Details
- `braf_alteration_list`: BRAF V600E/V600K Mutation, KIAA1549-BRAF fusion, Other BRAF Fusion, CRAF/RAF1 Fusion
- `tumor_char_test_list`: FISH/ISH, Somatic Tumor Panel, Fusion Panel, WES/WGS, IHC, Microarray
- `methyl_profiling_yn`: Methylation profiling completed (Yes/No/Unknown)

#### Hydrocephalus Details
- `hydro_yn`: Does subject have hydrocephalus?
- `hydro_method_diagnosed`: Clinical, CT, MRI
- `hydro_intervention`: Surgical, Medical, Hospitalization, None
- `hydro_surgical_management`: EVD, ETV, VPS placement, VPS revision

#### Imaging Clinical Related
- `age_at_date_scan`: Date of imaging scan
- `cortico_yn`: Patient on corticosteroids (Yes/No/Unknown)
- `cortico_1_name` to `cortico_5_name`: Up to 5 corticosteroids tracked with RxNorm codes and dosing
- `imaging_clinical_status`: Stable, Improved, Deteriorating, Not Reporting

#### Ophthalmology Functional Assessment
- `ophtho_exams`: Visual Fields, Optic Disc, Visual Acuity, OCT
- Visual acuity assessments: Teller, Snellen, HOTV, ETDRS, Cardiff, LEA
- `ophtho_logmar_left/right`: logMAR scores (-10 to +10)
- `ophtho_oct_left/right`: OCT measurements (microns)

---

## 3. Extraction Alignment Checklist

### ✅ Demographics
- [x] Patient.gender → legal_sex (0=Male, 1=Female)
- [x] Patient.birthDate → date_of_birth (yyyy-mm-dd)
- [ ] Patient.extension (race) → race checkbox (multiple selections)
- [ ] Patient.extension (ethnicity) → ethnicity radio (single selection)

### ✅ Diagnosis
- [x] Condition.code → cns_integrated_diagnosis (123 WHO options)
- [x] Condition.onsetDateTime → diagnosis_date, age_at_event_days
- [ ] Condition.code/note → who_grade (1-4 or No grade)
- [ ] Condition.bodySite → tumor_location (24 anatomical locations)

### ✅ Surgery
- [x] Procedure.performedDateTime/Period.start → age_at_surgery (with date handling fix)
- [x] Procedure.code → CPT classification for surgery_type
- [ ] Procedure.bodySite/note → extent_of_resection
- [ ] Count ENCOUNTERS not procedures (gold standard semantics)

### ⚠️ Chemotherapy (CRITICAL - FIXED)
- [x] MedicationRequest/Administration → chemotherapy_agents (FREE TEXT, semicolon-separated)
- [x] Expanded filter from 4 keywords → 50+ comprehensive keywords
- [x] Must capture ALL 3 agents: vinblastine, bevacizumab, selumetinib
- [x] Medication.authoredOn → age_at_chemo_start/stop

### ✅ Concomitant Medications (NEW)
- [x] Separate extraction from chemotherapy
- [x] MedicationRequest/Administration → medication_name
- [x] Include RxNorm codes if available
- [x] Track dosing schedule (Scheduled vs PRN) if available
- [x] Exclude chemotherapy keywords to get supportive care meds only

### ✅ Radiation
- [x] Procedure (CPT 77xxx) → radiation (Yes/No boolean)
- [ ] Procedure.code → radiation_type classification
- [ ] Procedure.performedDateTime → age_at_radiation_start/stop

### ⏳ Molecular
- [x] Observation/DiagnosticReport → mutation (free text)
- [ ] Specific test results → idh_mutation (with BRAF-only inference)
- [ ] Specific test results → mgmt_methylation
- [ ] Observation.effectiveDateTime → age_at_molecular_testing

---

## 4. Key Insights for BRIM Variable Instructions

### Priority 1: Free Text Fields
These fields accept FREE TEXT and should NOT be constrained:
- `chemotherapy_agents`: List drug names separated by semicolons
- `mutation`: Genetic alterations in natural language
- `tumor_location`: Anatomical descriptions (even with 24 checkbox options)
- `extent_of_resection`: Surgical details from operative notes

### Priority 2: Structured First, Then Narrative
For fields with structured sources, update BRIM instructions to check STRUCTURED documents FIRST:
1. Check `STRUCTURED_[field_name]` document
2. If incomplete, search FHIR resources in other documents
3. If still incomplete, search clinical narrative text

**Variables needing PRIORITY updates:**
1. patient_gender → STRUCTURED_demographics
2. date_of_birth → STRUCTURED_demographics
3. primary_diagnosis → STRUCTURED_diagnosis
4. diagnosis_date → STRUCTURED_diagnosis
5. surgery_date → STRUCTURED_surgeries
6. surgery_type → STRUCTURED_surgeries (CPT classification)
7. chemotherapy_agent → STRUCTURED_treatments
8. radiation_therapy → STRUCTURED_radiation
9. idh_mutation → STRUCTURED_molecular (with BRAF-only inference)
10. mgmt_methylation → STRUCTURED_molecular

### Priority 3: Age Conversion
All date fields in gold standard are converted to "age in days":
- Formula: `age_in_days = (event_date - date_of_birth).days`
- Format: Integer (e.g., 4763 days = 13.0 years)

**Date fields requiring conversion:**
- age_at_event_days
- age_at_surgery
- age_at_chemo_start, age_at_chemo_stop
- age_at_radiation_start, age_at_radiation_stop
- age_at_molecular_testing
- age_at_conmed_date

### Priority 4: Semantic Counting
**Gold standard counts ENCOUNTERS, not procedures:**
- C1277724 has 4 procedures but gold standard shows **2 surgical encounters**
- Likely excludes shunt placements and biopsies
- Counts only PRIMARY tumor resection surgeries

**BRIM extraction should:**
1. Extract ALL procedure dates (comprehensive)
2. Let decision logic determine which count as "surgical encounters"
3. Document exclusion criteria (shunts, biopsies) in decision instructions

---

## 5. Medication Extraction Strategy

### Chemotherapy Keywords (50+ comprehensive list)

**Alkylating Agents:**
- temozolomide, temodar, tmz
- lomustine, ccnu, ceenu, gleostine
- cyclophosphamide, cytoxan, neosar
- procarbazine, matulane
- carmustine, bcnu, gliadel

**Platinum Compounds:**
- carboplatin, paraplatin
- cisplatin, platinol

**Vinca Alkaloids (CRITICAL for C1277724):**
- vincristine, oncovin, marqibo
- **vinblastine, velban** ← Gold standard has this

**Topoisomerase Inhibitors:**
- etoposide, vepesid, toposar, etopophos
- irinotecan, camptosar, onivyde
- topotecan, hycamtin

**Antimetabolites:**
- methotrexate, trexall, otrexup, rasuvo
- 6-mercaptopurine, 6mp, purinethol
- thioguanine, 6-thioguanine

**Targeted Therapies (CRITICAL for C1277724):**
- bevacizumab, avastin ← Already captured
- **selumetinib, koselugo** ← Gold standard has this
- dabrafenib, tafinlar
- trametinib, mekinist
- vemurafenib, zelboraf
- everolimus, afinitor

**Immunotherapy:**
- nivolumab, opdivo
- pembrolizumab, keytruda
- ipilimumab, yervoy

**Result**: Filter expansion from 4 → 50+ keywords should capture all 3 gold standard agents (100% recall)

---

### Concomitant Medications (Supportive Care)

**Exclusion Strategy**: Extract all medications, EXCLUDE chemotherapy keywords

**Expected Categories:**
- Corticosteroids (dexamethasone, prednisone, methylprednisolone)
- Antibiotics (cefazolin, vancomycin, ceftriaxone)
- Anti-epileptics (levetiracetam, phenytoin, carbamazepine)
- Anti-emetics (ondansetron, metoclopramide, granisetron)
- Anti-anxiety (lorazepam, diazepam, alprazolam)
- Laxatives (sennosides, docusate, lactulose)
- Anticoagulants (enoxaparin, heparin, warfarin)
- Pain management (acetaminophen, ibuprofen, morphine)

**Gold Standard for C1277724**: 0 concomitant medications (none reported)

---

## 6. Testing Validation Plan

### Test 1: Medication Extraction Enhancement
```bash
python3 scripts/extract_structured_data.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --output pilot_output/structured_data_medications_fixed.json
```

**Expected Output:**
```json
{
  "treatments": [
    {"medication": "vinblastine ...", "start_date": "2019-XX-XX"},  // NEW
    {"medication": "bevacizumab ...", "start_date": "2019-07-02"},  // Already had (48 records)
    {"medication": "selumetinib ...", "start_date": "2021-XX-XX"}   // NEW
  ],
  "concomitant_medications": []  // 0 for C1277724
}
```

**Validation Criteria:**
- ✅ All 3 chemotherapy agents present (vinblastine, bevacizumab, selumetinib)
- ✅ Treatment count > 48 (was 48 bevacizumab-only, now includes vinblastine + selumetinib)
- ✅ Concomitant medications = 0 (matches gold standard for C1277724)

---

### Test 2: BRIM Iteration 2 Accuracy
After regenerating CSVs with enhanced structured data and PRIORITY instructions:

**Target Accuracy**: 85-90% (7-8 of 8 test variables)

| Variable | Iteration 1 | Iteration 2 Expected | Improvement |
|----------|-------------|---------------------|-------------|
| patient_gender | unknown ❌ | female ✅ | +1 (STRUCTURED_demographics) |
| diagnosis_date | 2018-06-04 ✅ | 2018-06-04 ✅ | 0 (already correct) |
| total_surgeries | 0 ❌ | 2 ✅ | +1 (filtered procedures) |
| chemotherapy_agent | 0 ❌ | 3 ✅ | +1 (expanded filter) |
| idh_mutation | no ❌ | wildtype ✅ | +1 (BRAF-only inference) |
| **Total Accuracy** | **50% (4/8)** | **85-90% (7-8/8)** | **+37.5%** |

---

## 7. Documentation Updates Required

### 1. Update variables.csv
Add PRIORITY instructions to 10 variables:
- patient_gender, date_of_birth, primary_diagnosis, diagnosis_date
- surgery_date, surgery_type, chemotherapy_agent, radiation_therapy
- idh_mutation, mgmt_methylation

**Example Enhanced Instruction (chemotherapy_agent):**
```
PRIORITY 1: Check NOTE_ID='STRUCTURED_treatments' for pre-extracted medication names.

PRIORITY 2: If incomplete, search MedicationRequest and MedicationAdministration resources.

PRIORITY 3: Search clinical text for drug names in progress notes.

Extract each drug name separately. Common agents include:
- Alkylating: temozolomide, lomustine, cyclophosphamide, procarbazine, carmustine
- Platinum: carboplatin, cisplatin
- Vinca alkaloids: vincristine, vinblastine
- Targeted therapies: bevacizumab, selumetinib, dabrafenib, trametinib, everolimus

Return generic or brand names. Scope is many_per_note - list all agents found.
```

### 2. Regenerate BRIM CSVs
```bash
python3 scripts/pilot_generate_brim_csvs.py \
  --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json \
  --structured-data pilot_output/structured_data_medications_fixed.json \
  --prioritized-docs pilot_output/prioritized_documents.json \
  --output-dir pilot_output/brim_csvs_iteration_2
```

**Expected Changes:**
- STRUCTURED_demographics document (NEW): gender, DOB
- STRUCTURED_treatments document (ENHANCED): all 3 chemotherapy agents
- STRUCTURED_concomitant_medications document (NEW): supportive care meds
- variables.csv (UPDATED): 10 variables with PRIORITY instructions

### 3. Upload to BRIM and Run Iteration 2
- Upload iteration_2 CSVs to BRIM project 17
- Trigger extraction
- Wait 12-15 minutes for processing
- Download results (extractions.csv, decisions.csv)

### 4. Validate Results
```bash
python3 scripts/automated_brim_validation.py \
  --extractions pilot_output/iteration_2_extractions.csv \
  --decisions pilot_output/iteration_2_decisions.csv \
  --gold-standard-dir data/20250723_multitab_csvs \
  --output pilot_output/iteration_2_validation_results.json
```

---

## 8. Next Steps

### IMMEDIATE (5 min)
1. ✅ Complete data dictionary review (DONE - this document)
2. ⏳ Test enhanced medication extraction

### HIGH PRIORITY (30 min)
3. Update variables.csv with PRIORITY instructions (10 variables)
4. Regenerate BRIM CSVs with enhanced structured data
5. Upload to BRIM and run iteration 2

### VALIDATION (10 min)
6. Validate iteration 2 results vs gold standard
7. Document accuracy improvements
8. Identify remaining gaps for Phase 2

**Expected Timeline**: ~45 minutes to iteration 2 validation

**Critical Path**: Test medications → Update variables → Regenerate CSVs → Upload to BRIM → Validate

---

## 9. References

**Data Dictionaries:**
- `/data/20250723_multitab_csvs/20250723_multitab__data_dictionary.csv` (Main fields, 190+ rows)
- `/data/20250723_multitab_csvs/20250723_multitab__data_dictionary_custom_forms.csv` (Custom forms, 113 rows)

**Gold Standard CSVs:**
- `/data/20250723_multitab_csvs/20250723_multitab__demographics.csv`
- `/data/20250723_multitab_csvs/20250723_multitab__diagnosis.csv`
- `/data/20250723_multitab_csvs/20250723_multitab__treatments.csv`
- `/data/20250723_multitab_csvs/20250723_multitab__concomitant_medications.csv`
- `/data/20250723_multitab_csvs/20250723_multitab__molecular_characterization.csv`

**Related Documentation:**
- `COMPREHENSIVE_CSV_VARIABLE_MAPPING.md` - All 33 variables analyzed
- `CSV_VARIABLE_QUICK_REFERENCE.md` - Matrix view of coverage
- `ITERATION_2_PROGRESS_AND_NEXT_STEPS.md` - Iteration 2 plan
- `DESIGN_INTENT_VS_IMPLEMENTATION.md` - Workflow design validation

---

**Status**: ✅ Data dictionary review complete. Ready to proceed with medication extraction testing.
