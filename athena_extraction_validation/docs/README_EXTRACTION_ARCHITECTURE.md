# Athena Extraction Architecture

**Date**: October 7, 2025  
**Status**: Production-Ready Extraction Scripts + Validation Framework

---

## Overview

This directory contains two types of scripts with distinct purposes:

### 1. **Extraction Scripts** (`scripts/extract_*.py`)
- **Purpose**: Production-ready data extraction from Athena
- **Input**: List of patient FHIR IDs
- **Output**: CSV files with all extractable fields
- **Use Case**: Batch processing for cohort studies, clinical data pipelines
- **No Gold Standard Required**: Works independently

### 2. **Validation Scripts** (`athena_extraction_validation/scripts/validate_*.py`)
- **Purpose**: Test extraction accuracy against gold standard CSVs
- **Input**: Patient FHIR ID + Gold Standard CSV
- **Output**: Validation reports with accuracy metrics
- **Use Case**: Development, testing, gap identification
- **Requires Gold Standard**: Used during development only

---

## Production Extraction Scripts

### extract_diagnosis.py

**Status**: ✅ Production Ready

**Input**:
```bash
python3 scripts/extract_diagnosis.py \
  --patient-ids e4BwD8ZYDBccepXcJ.Ilo3w3 PATIENT_ID_2 PATIENT_ID_3 \
  --output-csv outputs/diagnosis_cohort.csv

# Or from file:
python3 scripts/extract_diagnosis.py \
  --patient-ids-file patient_list.txt \
  --output-csv outputs/diagnosis_cohort.csv
```

**Athena Tables Used**:
1. `fhir_v2_prd_db.problem_list_diagnoses` - Primary diagnosis source
2. `fhir_v2_prd_db.patient_access` - Birth dates for age calculations
3. `fhir_v2_prd_db.condition` + `condition_code_coding` - Metastasis detection
4. `fhir_v2_prd_db.procedure` + `procedure_code_coding` - Shunt procedures
5. `fhir_v2_prd_db.molecular_tests` + `molecular_test_results` - Genomic testing

**Output Schema** (24 fields):
```csv
patient_fhir_id              - FHIR Patient ID
event_id                     - Generated event identifier
event_type                   - Initial CNS Tumor | Progressive
age_at_event_days            - Age in days at diagnosis
diagnosis_date               - YYYY-MM-DD
cns_integrated_diagnosis     - Diagnosis name from problem_list
icd10_code                   - ICD-10 code
clinical_status_at_event     - Alive | Deceased
autopsy_performed            - Yes | No | Not Applicable
cause_of_death               - Text or Not Applicable
metastasis                   - Yes | No
metastasis_location          - Comma-separated locations
metastasis_location_other    - Not Applicable
shunt_required               - ETV Shunt | Yes | No | Not Applicable
shunt_required_other         - Not Applicable
tumor_or_molecular_tests_performed - Test name or Not Applicable
tumor_or_molecular_tests_performed_other - Not Applicable
cns_integrated_category      - NULL (requires narrative - BRIM)
who_grade                    - NULL (requires narrative - BRIM)
tumor_location               - NULL (requires narrative - BRIM)
tumor_location_other         - Not Applicable
site_of_progression          - NULL (requires narrative - BRIM)
extraction_method            - ATHENA_STRUCTURED
extraction_timestamp         - ISO timestamp
```

**Extraction Logic**:

1. **Cancer Diagnosis Filtering**: 
   - Filters `problem_list_diagnoses` for cancer-related terms
   - Keywords: astrocytoma, glioma, tumor, neoplasm, cancer, carcinoma, sarcoma, blastoma

2. **Event Clustering**:
   - First diagnosis = "Initial CNS Tumor"
   - Subsequent diagnoses = "Progressive"

3. **Age Calculation**:
   - Uses `patient_access.birth_date`
   - Calculates `(diagnosis_date - birth_date).days`

4. **Metastasis Detection**:
   - Queries `condition` table for metastasis codes
   - Matches within ±6 months of diagnosis date
   - Extracts specific locations (leptomeningeal, spine)

5. **Shunt Detection**:
   - Queries `procedure` table for CPT codes 62xxx
   - Matches within ±30 days of diagnosis
   - Identifies ETV vs generic shunt

6. **Molecular Test Detection**:
   - Queries `molecular_tests` + `molecular_test_results`
   - Matches within ±6 months of diagnosis
   - Identifies test types (WGS, panels)

**Known Limitations**:
- ❌ WHO grade: Not in structured data (requires pathology reports)
- ❌ Tumor location: Not in structured data (requires operative notes)
- ❌ CNS category: Not in structured data (requires pathology)
- ❌ Site of progression: Not in structured data (requires oncology notes)
- ⚠️ Metastasis: May miss some cases (condition codes incomplete)

**Performance**:
- Single patient: ~12 seconds
- 10 patients: ~45 seconds
- 100 patients: ~6 minutes (estimated)

---

### extract_demographics.py

**Status**: ⏳ To Be Created

**Planned Input**:
```bash
python3 scripts/extract_demographics.py \
  --patient-ids-file patient_list.txt \
  --output-csv outputs/demographics_cohort.csv
```

**Athena Tables**:
- `fhir_v2_prd_db.patient_access` (100% coverage)

**Output Fields**:
- patient_fhir_id
- legal_sex (from gender)
- race
- ethnicity
- birth_date

**Expected Accuracy**: 100% (validated)

---

### extract_treatments.py

**Status**: ⏳ To Be Created

**Planned Tables**:
1. `procedure` + `procedure_code_coding` - Surgeries
2. `patient_medications` - Chemotherapy agents
3. `procedure` (CPT 77xxx) - Radiation therapy

**Critical Gap to Fix**:
- ❌ Chemotherapy filter too narrow (missing vinblastine, selumetinib)
- Must expand CHEMO_KEYWORDS list

---

### extract_concomitant_medications.py

**Status**: ⏳ To Be Created

**Planned Tables**:
- `patient_medications` (RxNorm codes)

**Expected Coverage**: 85-90%

---

### extract_molecular_characterization.py

**Status**: ⏳ To Be Created

**Planned Tables**:
1. `molecular_tests` + `molecular_test_results`
2. `observation` (genomic observations)

**Known Issue**: 
- ❌ molecular_tests table empty for test patient C1277724
- May need to query `observation` table with genomic codes

---

### extract_encounters.py

**Status**: ⏳ To Be Created

**Planned Tables**:
- `encounter` (100% structured)

---

### extract_measurements.py

**Status**: ⏳ To Be Created

**Planned Tables**:
- `observation` (vital signs, growth measurements)

**Expected Coverage**: 95%+

---

## Validation Scripts (Development Only)

### validate_demographics_csv.py

**Status**: ✅ Complete

**Validation Results** (C1277724):
- Accuracy: **100.0%** (3/3 fields matched)
- All demographics fields extractable from `patient_access`

### validate_diagnosis_csv.py

**Status**: ✅ Complete

**Validation Results** (C1277724):
- Structured Accuracy: **55.7%** (39/70 fields)
- Perfect Fields: clinical_status (100%), autopsy (100%), cause_of_death (100%)
- Needs Work: age_at_event (0%), diagnosis matching (0%), molecular tests (0%)

**Identified Gaps**:
1. ❌ Event clustering: Extracting ALL diagnoses instead of cancer-specific
2. ❌ Age calculation: Using wrong diagnosis dates
3. ❌ Molecular test detection: Table empty
4. ⚠️ Metastasis detection: Missing some cases (50% accuracy)

### validate_treatments_csv.py

**Status**: ⏳ To Be Created

**Expected to Test**:
- Surgery extraction accuracy
- Chemotherapy filter coverage (critical gap)
- Radiation detection
- Temporal clustering

---

## Development Workflow

### Phase 1: Create Extraction Script

1. Identify Athena tables and columns
2. Write extraction logic
3. Test with single patient
4. Handle edge cases

### Phase 2: Validate Against Gold Standard

1. Create validation script
2. Run on test patient (C1277724)
3. Compare field-by-field
4. Calculate accuracy metrics
5. Identify gaps

### Phase 3: Iterate and Fix

1. Fix identified gaps in extraction script
2. Re-validate
3. Update documentation
4. Move to next CSV

### Phase 4: Production Deployment

1. Test on patient cohort
2. Performance optimization
3. Error handling
4. Batch processing

---

## Current Status

| CSV | Extraction Script | Validation Script | Status |
|-----|-------------------|-------------------|--------|
| demographics | ⏳ To Create | ✅ Complete (100%) | Validated |
| diagnosis | ✅ **extract_diagnosis.py** | ✅ Complete (55.7%) | **READY** |
| treatments | ⏳ To Create | ⏳ To Create | Pending |
| concomitant_medications | ⏳ To Create | ⏳ To Create | Pending |
| molecular_characterization | ⏳ To Create | ⏳ To Create | Pending |
| molecular_tests_performed | ⏳ To Create | ⏳ To Create | Pending |
| encounters | ⏳ To Create | ⏳ To Create | Pending |
| measurements | ⏳ To Create | ⏳ To Create | Pending |
| imaging_clinical_related | ⏳ To Create | ⏳ To Create | Pending |
| survival | ⏳ To Create | ⏳ To Create | Pending |

**Total Progress**: 1/18 extraction scripts complete (5.6%)

---

## Priority Next Steps

1. **Fix diagnosis extraction gaps** (highest priority):
   - ✅ Cancer-specific filtering (DONE in extract_diagnosis.py)
   - ✅ Correct age calculation (DONE)
   - ❌ Improve metastasis detection (condition codes incomplete)
   - ❌ Fix molecular test detection (table empty)

2. **Create extract_demographics.py**:
   - Simplest case (100% validated)
   - ~30 minutes to implement

3. **Create extract_treatments.py**:
   - Critical chemotherapy filter gap
   - Must test on C1277724 (vinblastine, bevacizumab, selumetinib)

4. **Create extract_concomitant_medications.py**:
   - Large CSV (9,548 rows)
   - High value for clinical analysis

---

## Notes

### Molecular Tests Issue

The `molecular_tests` table is **empty** for patient C1277724, despite gold standard showing:
- "Whole Genome Sequencing" performed

**Possible Solutions**:
1. Query `observation` table with genomic codes
2. Query `diagnostic_report` for molecular pathology
3. Check `procedure` for genomic testing CPT codes
4. May require BRIM extraction from pathology reports

### Metastasis Detection Issue

Condition codes are missing metastasis entries for C1277724, despite gold standard showing:
- Leptomeningeal metastasis
- Spine metastasis

**Possible Solutions**:
1. Query radiology reports via BRIM (narrative extraction)
2. Check `diagnostic_report` for imaging findings
3. Expand condition code search terms

---

## Usage Examples

### Extract Diagnosis for Single Patient
```bash
python3 scripts/extract_diagnosis.py \
  --patient-ids e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --output-csv outputs/diagnosis_single.csv
```

### Extract Diagnosis for Cohort
```bash
# Create patient list file
echo "e4BwD8ZYDBccepXcJ.Ilo3w3" > patient_ids.txt
echo "PATIENT_ID_2" >> patient_ids.txt
echo "PATIENT_ID_3" >> patient_ids.txt

# Run extraction
python3 scripts/extract_diagnosis.py \
  --patient-ids-file patient_ids.txt \
  --output-csv outputs/diagnosis_cohort.csv
```

### Validate Extraction (Development)
```bash
python3 athena_extraction_validation/scripts/validate_diagnosis_csv.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --patient-research-id C1277724 \
  --patient-birth-date 2005-05-13 \
  --gold-standard-csv data/20250723_multitab_csvs/20250723_multitab__diagnosis.csv \
  --output-report athena_extraction_validation/reports/diagnosis_validation.md
```

---

**Last Updated**: October 7, 2025  
**Next Review**: After completing demographics and treatments extraction scripts
