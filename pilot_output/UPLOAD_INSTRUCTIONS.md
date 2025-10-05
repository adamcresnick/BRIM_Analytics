# BRIM Project 17 Upload Instructions

## Issue Resolved
**Problem:** Original `project.csv` had duplicate NOTE_IDs (89 rows, only 45 unique)  
**Solution:** Created `project_dedup.csv` with 45 unique documents

## Files Ready for Upload

### ✅ Automatically Uploaded via API
- **project_dedup.csv** (45 rows) - Will be uploaded automatically by the script

### ⚠️ Manual Upload Required (via Web UI)

#### 1. Variables Configuration
**File:** `pilot_output/brim_csvs_final/variables.csv`  
**Path:** `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_final/variables.csv`

**Contains 14 variables:**
- document_type
- patient_gender  
- date_of_birth
- primary_diagnosis
- diagnosis_date
- who_grade
- idh_mutation
- mgmt_methylation
- molecular_profile
- tumor_location
- surgery_date
- chemotherapy_agent
- radiation_therapy
- tumor_resection_extent

#### 2. Decisions Configuration  
**File:** `pilot_output/brim_csvs_final/decisions.csv`  
**Path:** `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_final/decisions.csv`

**Contains decision logic** for dependent variables and cross-validation rules

---

## Upload Steps

### Via Web UI (https://brim.radiant-tst.d3b.io)

1. **Login** to https://brim.radiant-tst.d3b.io
2. **Navigate** to Project 17 (BRIM_Pilot2)
3. **Upload Variables:**
   - Click "Upload Variables" or "Configure Variables"  
   - Select: `pilot_output/brim_csvs_final/variables.csv`
   - Confirm/Save
4. **Upload Decisions:**
   - Click "Upload Decisions" or "Configure Decisions"
   - Select: `pilot_output/brim_csvs_final/decisions.csv`  
   - Confirm/Save

---

## After Upload Complete

Once variables and decisions are uploaded, run the automated workflow:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

python scripts/automated_brim_validation.py \
    --max-iterations 1 \
    --target-accuracy 0.92 \
    --csv-dir pilot_output/brim_csvs_final \
    --gold-standard-dir data/20250723_multitab_csvs \
    --api-url "https://brim.radiant-tst.d3b.io" \
    --api-token "t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj" \
    --project-id 17
```

### What the Script Will Do:

1. ✅ **Upload** `project_dedup.csv` (45 documents) via API
2. ✅ **Trigger** extraction with your configured variables
3. ⏳ **Wait** ~60 seconds for processing  
4. ✅ **Download** results CSV from BRIM
5. ✅ **Validate** results against gold standard (patient C1277724)
6. 📊 **Calculate** accuracy metrics (target: 92%)
7. 🔄 **Iterate** if needed (improve prompts → re-run)

---

## Project 17 Configuration

**Project Details:**
- **ID:** 17
- **Name:** BRIM_Pilot2
- **Status:** Loaded  
- **Review Mode:** VARIABLES AND DECISIONS
- **API URL:** https://brim.radiant-tst.d3b.io
- **API Token:** t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj
- **Project Token:** 1SBNge25Wlg7hQJi1OgdLI_JBfu76GgG6aoETrgXgvjnm1VH

---

## API Limitations Discovered

The BRIM API currently does **NOT** provide endpoints for:
- ❌ Uploading `variables.csv` (must use web UI)
- ❌ Uploading `decisions.csv` (must use web UI)

The API **DOES** support:
- ✅ Creating projects: `POST /api/v1/projects/`
- ✅ Uploading project data: `POST /api/v1/upload/csv/`
- ✅ Fetching results: `POST /api/v1/results/`

**Request to BRIM Team:** Please add API endpoints for:
- `POST /api/v1/projects/{id}/variables` - Upload variables.csv  
- `POST /api/v1/projects/{id}/decisions` - Upload decisions.csv

---

## Data Summary

### Deduplicated Project CSV
- **Rows:** 45 unique documents
- **Patient:** 1277724 (pseudonymized MRN)
- **Document Types:**
  - Pathology study (20)
  - OP Note - Complete (4)
  - Anesthesia Notes (7)
  - OP Note - Brief (3)
  - FHIR Bundle (1)
  - Molecular Testing Summary (1)
  - Surgical History Summary (1)
  - Other clinical notes (8)

### Variables Configuration
- **14 variables** defined for extraction
- Mix of patient-level (gender, DOB) and document-level (diagnosis, molecular) variables
- Includes aggregation rules for multi-occurrence variables

### Gold Standard (Validation Target)
- **Patient:** C1277724
- **Source:** `data/20250723_multitab_csvs/`
- **Known Facts:**
  - Gender: Female
  - Diagnosis: Pilocytic astrocytoma, WHO Grade 1
  - Molecular: KIAA1549-BRAF fusion
  - Surgeries: 2 neurosurgeries
  - Chemotherapy: 3 agents (vinblastine, bevacizumab, selumetinib)
  - Location: Cerebellum/Posterior fossa

---

**Status:** Ready for upload! Let me know once variables/decisions are uploaded to Project 17.
