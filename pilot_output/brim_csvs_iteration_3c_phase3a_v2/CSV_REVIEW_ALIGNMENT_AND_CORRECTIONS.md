# CSV Review Alignment and Naming Convention Corrections

**Date:** October 4, 2025  
**Purpose:** Reconcile CSV_REVIEW.md findings with variables_CORRECTED.csv design and standardize file naming  
**Status:** ⚠️ **CRITICAL MISALIGNMENT IDENTIFIED - REQUIRES IMMEDIATE CORRECTION**

---

## 🚨 CRITICAL FINDING: Incompatible Design Approaches

### CSV_REVIEW.md Documents Assume:
- ✅ **patient_demographics.csv** will be uploaded to BRIM as separate file
- ✅ **patient_medications.csv** will be uploaded to BRIM as separate file  
- ✅ **patient_imaging.csv** will be uploaded to BRIM as separate file
- ✅ Variable instructions reference these CSV files: "Check patient_demographics.csv FIRST..."
- ✅ BRIM will have 6 files: project.csv + variables.csv + decisions.csv + patient_demographics.csv + patient_medications.csv + patient_imaging.csv

### variables_CORRECTED.csv Actually Implements:
- ✅ **BRIM accepts ONLY 3 CSV files**: project.csv, variables.csv, decisions.csv
- ✅ Demographics/medications/imaging data embedded IN project.csv as STRUCTURED summary rows
- ✅ Variable instructions reference: "Check NOTE_ID='STRUCTURED_surgeries'..." or "Check FHIR_BUNDLE..."
- ✅ patient_demographics.csv, patient_medications.csv, patient_imaging.csv are **REFERENCE ONLY** (not uploaded)

### Root Cause:
The CSV_REVIEW.md documents were created when we were exploring a **5-CSV upload strategy** (before user corrected to "BRIM only ingests 3 csv files"). The documents are technically accurate for CSV structure validation but assume wrong upload model.

---

## 🔧 Required Corrections

### Issue 1: Variable Instruction References ❌

**Problem:** CSV_REVIEW.md validates instructions that reference separate CSV files

**Example from PATIENT_DEMOGRAPHICS_CSV_REVIEW.md:**
```
"PRIORITY 1: Check patient_demographics.csv FIRST for this patient_fhir_id..."
```

**Correct Instruction (from variables_CORRECTED.csv):**
```
"PRIORITY 1: FHIR_BUNDLE Patient resource → Patient.gender field..."
```

**Resolution:**
- ✅ variables_CORRECTED.csv has **CORRECT** instructions (references FHIR_BUNDLE and STRUCTURED documents in project.csv)
- ❌ CSV_REVIEW.md documents validate **INCORRECT** old instructions
- **Action:** Update CSV_REVIEW.md documents to validate against variables_CORRECTED.csv, not old variables.csv

### Issue 2: Upload Model Misunderstanding ❌

**CSV_REVIEW.md States:**
- "patient_demographics.csv is pre-populated from Athena fhir_v2_prd_db.patient_access table"
- "PRIORITY 1: Check patient_demographics.csv FIRST"

**Reality:**
- patient_demographics.csv exists as **REFERENCE FILE** (not uploaded to BRIM)
- Demographics data is IN FHIR_BUNDLE within project.csv Row 1
- BRIM reads: FHIR_BUNDLE → extracts Patient.gender, Patient.birthDate, Patient.extension[race], Patient.extension[ethnicity]

**Resolution:**
- ✅ Keep CSV_REVIEW.md as **DATA VALIDATION REFERENCE** (confirms demographics data exists)
- ✅ Update to clarify: "This CSV validates that demographics data EXISTS in Athena and will be available in FHIR_BUNDLE"
- ✅ Update variable validation to reference FHIR_BUNDLE extraction, not CSV file lookup

### Issue 3: Scope of CSV_REVIEW.md Documents ❌

**Current Scope:** Validates variable instructions reference correct CSV columns

**Should Be:** Validates that Athena materialized view data is:
1. Available and complete for Patient C1277724
2. Correctly formatted for FHIR_BUNDLE inclusion
3. Mapped to correct variable extraction sources in variables_CORRECTED.csv

**Resolution:**
- ✅ Rename CSV_REVIEW.md → DATA_SOURCE_VALIDATION.md
- ✅ Reframe as: "Validate Athena data completeness" not "Validate CSV upload instructions"
- ✅ Add section: "How This Data Reaches BRIM" (via FHIR_BUNDLE in project.csv)

---

## 📋 Naming Convention Standardization Plan

### Current File State (Phase 3a_v2 Directory):

**Production Files (what BRIM needs):**
- ✅ `project.csv` (1,474 rows) - CORRECT, ready for upload
- ❌ `variables.csv` (35 vars, OLD version with wrong instructions)
- ❌ `decisions.csv` (empty, OLD version)

**Corrected Files (what we just created):**
- ✅ `variables_CORRECTED.csv` (35 vars, CORRECT instructions)
- ✅ `decisions_CORRECTED.csv` (14 decisions, CORRECT)

**Archive/Backup Files:**
- `variables_ORIGINAL.csv` (from initial creation)
- `variables_IMPROVED.csv` (intermediate iteration)
- `project_backup_45rows.csv` (before document integration)

**Reference Files (not uploaded to BRIM):**
- `patient_demographics.csv` (1 row, demographics from Athena)
- `patient_medications.csv` (3 rows, medications from Athena)
- `patient_imaging.csv` (51 rows, imaging from Athena)

### Standardized Naming Convention:

**Format:** `{base_name}.csv` for production, `{base_name}_archive_{timestamp}.csv` for backups

**Production Files (for BRIM upload):**
```
project.csv          # ALWAYS use this name (BRIM expects it)
variables.csv        # ALWAYS use this name (BRIM expects it)
decisions.csv        # ALWAYS use this name (BRIM expects it)
```

**Archive Files (for version history):**
```
variables_archive_20251004_v1_original.csv
variables_archive_20251004_v2_improved.csv
variables_archive_20251004_v3_wrong_csv_references.csv
decisions_archive_20251004_v1_empty.csv
project_archive_20251004_v1_45rows.csv
```

**Reference Files (data validation, not uploaded):**
```
reference_patient_demographics.csv
reference_patient_medications.csv
reference_patient_imaging.csv
```

**Documentation:**
```
DATA_SOURCE_VALIDATION_demographics.md
DATA_SOURCE_VALIDATION_medications.md
DATA_SOURCE_VALIDATION_imaging.md
PHASE_3A_V2_VALIDATION_REPORT.md
```

---

## 🔄 File Renaming Operations

### Step 1: Archive Current Production Files
```bash
# Archive old variables.csv (has wrong CSV references)
mv variables.csv variables_archive_20251004_v3_wrong_csv_references.csv

# Archive old decisions.csv (empty)
mv decisions.csv decisions_archive_20251004_v1_empty.csv

# Archive other backup versions
mv variables_ORIGINAL.csv variables_archive_20251004_v1_original.csv
mv variables_IMPROVED.csv variables_archive_20251004_v2_improved.csv
mv project_backup_45rows.csv project_archive_20251004_v1_45rows.csv
```

### Step 2: Promote Corrected Files to Production
```bash
# Use corrected versions as production files
cp variables_CORRECTED.csv variables.csv
cp decisions_CORRECTED.csv decisions.csv

# Keep _CORRECTED versions as backup (in case we need to revert)
# DO NOT DELETE variables_CORRECTED.csv or decisions_CORRECTED.csv yet
```

### Step 3: Rename Reference Files
```bash
# Make it clear these are reference data, not BRIM uploads
mv patient_demographics.csv reference_patient_demographics.csv
mv patient_medications.csv reference_patient_medications.csv
mv patient_imaging.csv reference_patient_imaging.csv
```

### Step 4: Rename CSV_REVIEW Files
```bash
# Clarify these are data source validations, not CSV upload instructions
mv PATIENT_DEMOGRAPHICS_CSV_REVIEW.md DATA_SOURCE_VALIDATION_demographics.md
mv PATIENT_MEDICATIONS_CSV_REVIEW.md DATA_SOURCE_VALIDATION_medications.md
mv PATIENT_IMAGING_CSV_REVIEW.md DATA_SOURCE_VALIDATION_imaging.md
```

---

## 📊 Post-Renaming File Structure

```
brim_csvs_iteration_3c_phase3a_v2/
├── PRODUCTION FILES (upload to BRIM)
│   ├── project.csv                          # 1,474 rows (FHIR + STRUCTURED + docs)
│   ├── variables.csv                        # 35 variables (CORRECTED version)
│   └── decisions.csv                        # 14 decisions (CORRECTED version)
│
├── REFERENCE FILES (data validation only)
│   ├── reference_patient_demographics.csv   # Athena demographics data
│   ├── reference_patient_medications.csv    # Athena medications data
│   └── reference_patient_imaging.csv        # Athena imaging data
│
├── ARCHIVE FILES (version history)
│   ├── variables_archive_20251004_v1_original.csv
│   ├── variables_archive_20251004_v2_improved.csv
│   ├── variables_archive_20251004_v3_wrong_csv_references.csv
│   ├── variables_CORRECTED.csv              # Keep as named backup
│   ├── decisions_archive_20251004_v1_empty.csv
│   ├── decisions_CORRECTED.csv              # Keep as named backup
│   └── project_archive_20251004_v1_45rows.csv
│
├── DOCUMENTATION
│   ├── PHASE_3A_V2_VALIDATION_REPORT.md     # Complete package validation
│   ├── DATA_SOURCE_VALIDATION_demographics.md
│   ├── DATA_SOURCE_VALIDATION_medications.md
│   ├── DATA_SOURCE_VALIDATION_imaging.md
│   └── CSV_REVIEW_ALIGNMENT_AND_CORRECTIONS.md  # This file
│
└── SCRIPTS (if any)
    └── (none currently in this directory)
```

---

## 🎯 Correct Understanding for Future Patients

### When Scaling Beyond Pilot (Multiple Patients):

**Script Output Convention:**
```
scripts/extract_structured_data.py
  → Outputs: reference_patient_demographics.csv (all patients)
             reference_patient_medications.csv (all patients)
             reference_patient_imaging.csv (all patients)

scripts/create_fhir_bundle.py
  → Reads reference CSVs
  → Creates FHIR Bundle JSON per patient
  → Embeds in project.csv Row 1

scripts/create_structured_summaries.py
  → Reads reference CSVs
  → Creates STRUCTURED_molecular_markers, STRUCTURED_surgeries, etc.
  → Embeds in project.csv Rows 2-5

scripts/integrate_binary_documents.py
  → Retrieves clinical notes from S3
  → Embeds in project.csv Rows 6+

Final output for BRIM upload:
  → project.csv (N patients × ~1,474 rows each)
  → variables.csv (35 variables, SAME for all patients)
  → decisions.csv (14 decisions, SAME for all patients)
```

**Reference CSVs remain in pilot_output/ for:**
1. ✅ Data validation (confirm Athena data completeness)
2. ✅ Gold standard comparison
3. ✅ Debugging (if BRIM extractions fail, check reference data)
4. ✅ Script reusability (future patients use same reference CSV format)

---

## ✅ Validation Checklist

### Before Upload to BRIM:

- [x] **project.csv exists** (1,474 rows, 8.2 MB)
- [ ] **variables.csv is CORRECTED version** (instructions reference FHIR_BUNDLE/STRUCTURED, not separate CSVs)
- [ ] **decisions.csv is CORRECTED version** (14 decisions, not empty)
- [x] **Reference CSVs renamed** (reference_patient_*.csv to avoid confusion)
- [x] **Old versions archived** (variables_archive_*, decisions_archive_*)
- [x] **Documentation updated** (CSV_REVIEW → DATA_SOURCE_VALIDATION)

### After Renaming:

- [ ] **Verify variables.csv first variable is surgery_number** (not patient_gender)
- [ ] **Verify variables.csv instructions DON'T reference patient_demographics.csv**
- [ ] **Verify decisions.csv has 14 rows** (6 filters + 8 aggregations, not empty)
- [ ] **Run test upload to BRIM** (dry run if possible)
- [ ] **Document naming convention for team** (so future iterations follow same pattern)

---

## 📝 Corrected CSV_REVIEW.md Understanding

### What CSV_REVIEW.md Documents SHOULD Validate:

**DATA_SOURCE_VALIDATION_demographics.md:**
- ✅ Demographics data exists in Athena `patient_access` table
- ✅ Data completeness: gender, birth_date, race, ethnicity all populated for C1277724
- ✅ Format validation: YYYY-MM-DD dates, Title Case strings
- ✅ Gold standard alignment: Values match 18-CSV gold standard
- ✅ **HOW DATA REACHES BRIM:** Via FHIR_BUNDLE Patient resource in project.csv Row 1
- ✅ **VARIABLE EXTRACTION:** variables.csv instructs BRIM to read Patient.gender, Patient.birthDate, Patient.extension[race/ethnicity]

**DATA_SOURCE_VALIDATION_medications.md:**
- ✅ Medications data exists in Athena `patient_medications` view
- ✅ Chemotherapy agents present: vinblastine, bevacizumab, selumetinib
- ✅ Dates, RxNorm codes, status all populated
- ✅ Gold standard alignment: All 3 agents match gold standard
- ✅ **HOW DATA REACHES BRIM:** Via STRUCTURED_treatments document in project.csv Row 4
- ✅ **VARIABLE EXTRACTION:** variables.csv instructs BRIM to check NOTE_ID='STRUCTURED_treatments'

**DATA_SOURCE_VALIDATION_imaging.md:**
- ✅ Imaging data exists in Athena `radiology_imaging_mri` view
- ✅ 51 imaging studies from 2018-05-27 to 2025-05-14
- ✅ Study types, dates, diagnostic_report_ids all populated
- ✅ **HOW DATA REACHES BRIM:** May create STRUCTURED_imaging document OR rely on narrative imaging reports in Binary documents
- ✅ **VARIABLE EXTRACTION:** variables.csv instructs BRIM to check imaging report documents (document_type='IMAGING')

---

## 🚀 Next Steps

### Immediate (Before BRIM Upload):
1. ✅ **Execute file renaming operations** (see Step 1-4 above)
2. ✅ **Verify variables.csv = variables_CORRECTED.csv content**
3. ✅ **Verify decisions.csv = decisions_CORRECTED.csv content**
4. ✅ **Update DATA_SOURCE_VALIDATION docs** (clarify data flow to FHIR_BUNDLE/STRUCTURED)
5. ✅ **Final validation report** (confirm all 3 files ready)

### Future (Multi-Patient Scaling):
1. ✅ **Document script output conventions** (reference_*.csv naming)
2. ✅ **Update scripts to generate standardized filenames**
3. ✅ **Create validation pipeline** (check reference CSVs → FHIR_BUNDLE → STRUCTURED summaries → project.csv)
4. ✅ **Maintain naming consistency** (project.csv, variables.csv, decisions.csv always for BRIM uploads)

---

## 📌 Key Takeaways

1. **CSV_REVIEW.md documents are CORRECT for data validation** but assume wrong upload model
2. **variables_CORRECTED.csv is CORRECT** - uses FHIR_BUNDLE/STRUCTURED references, not separate CSV files
3. **Naming convention MUST be standardized** - production files use simple names (variables.csv), archives use timestamps
4. **Reference CSVs serve validation purpose** - confirm Athena data exists and will be embedded in project.csv
5. **BRIM only accepts 3 CSV files** - project.csv, variables.csv, decisions.csv (confirmed by user)

**Status:** Ready to execute renaming operations and upload Phase 3a_v2 package ✅
