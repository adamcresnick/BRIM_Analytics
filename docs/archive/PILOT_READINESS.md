# BRIM Analytics - Pilot Readiness Summary

**Date:** October 1, 2025  
**Status:** ✅ Ready for Production Pilot  
**Repository:** `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics`

---

## 🎯 What We've Built

A complete hybrid FHIR + BRIM extraction framework that combines:
- **Structured data extraction** from AWS Athena FHIR database
- **Unstructured note analysis** via BRIM Health's NLP API
- **Automated workflows** with validation and quality checks

---

## 📦 Deliverables

### 1. **Core Python Modules** (`src/`)
- ✅ `fhir_extractor.py` - Query FHIR resources from Athena
- ✅ `brim_csv_generator.py` - Generate BRIM-compatible CSVs with HINT columns
- ✅ `brim_api_client.py` - Automate BRIM API interactions
- ✅ `validation.py` - Cross-validate results

### 2. **Production Pilot Script** (`pilot_workflow.py`)
- ✅ Complete end-to-end workflow
- ✅ AWS connection testing
- ✅ Patient discovery and exploration
- ✅ CSV generation with validation
- ✅ Optional BRIM API upload

### 3. **Configuration** (`.env`)
- ✅ AWS Profile: `343218191717_AWSAdministratorAccess`
- ✅ Athena Database: `radiant_prd_343218191717_us_east_1_prd_fhir_datastore_*_healthlake_view`
- ✅ BRIM API Key: `t5g2bqNeiWyIXTAWEWUg0mg0nY8Gq8q4FTD1luQ75hd-6fgj`
- ✅ All settings pre-configured for production

### 4. **Documentation** (`docs/`)
- ✅ [HYBRID_FHIR_BRIM_EXTRACTION_STRATEGY.md](docs/HYBRID_FHIR_BRIM_EXTRACTION_STRATEGY.md) - Complete architectural guide
- ✅ README.md - Quick start guide
- ✅ Code comments and docstrings throughout

### 5. **Setup Automation**
- ✅ `setup.sh` - One-command environment setup
- ✅ `requirements.txt` - All Python dependencies specified

---

## 🚀 How to Run the Pilot

### Step 1: Initial Setup (One-time)

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Run setup
chmod +x setup.sh
./setup.sh

# Activate environment
source venv/bin/activate
```

### Step 2: Login to AWS

```bash
# AWS SSO login
aws sso login --profile 343218191717_AWSAdministratorAccess

# Verify (should show account 343218191717)
aws sts get-caller-identity --profile 343218191717_AWSAdministratorAccess
```

### Step 3: Explore & Find Patients

```bash
# Discover available patients in FHIR database
python pilot_workflow.py --explore-only
```

**This will show:**
- ✓ AWS connection status
- ✓ Available FHIR tables
- ✓ Sample patients with clinical notes
- ✓ Recommended patient for testing

### Step 4: Run Extraction for One Patient

```bash
# Replace Patient/abc123 with actual patient ID from Step 3
python pilot_workflow.py \
    --patient-id "Patient/abc123" \
    --research-id "TEST001"
```

**This will:**
1. Extract FHIR context (surgeries, diagnoses, medications)
2. Discover clinical notes (DocumentReference → Binary)
3. Generate 3 BRIM CSVs with HINT columns
4. Validate outputs
5. Save to `./output/` directory

**Generated files:**
- `brim_project_TEST001_*.csv` - Clinical notes with HINT columns
- `brim_variables_*.csv` - Extraction instructions  
- `brim_decisions_*.csv` - Dependent variables

### Step 5: Review & Upload to BRIM

**Option A: Manual Upload**
1. Open BRIM web interface
2. Create new project
3. Upload the 3 CSV files
4. Run extraction
5. Download results

**Option B: Automated API Upload (Set in .env)**
```bash
# Edit .env
AUTO_UPLOAD_TO_BRIM=true

# Re-run pilot
python pilot_workflow.py --patient-id "Patient/abc123" --research-id "TEST001"
```

---

## 🎨 Key Innovation: HINT Columns

The framework pre-populates BRIM CSVs with structured FHIR data in **HINT columns**:

| HINT Column | Source | Purpose |
|-------------|--------|---------|
| `HINT_SURGERY_NUMBER` | Computed from procedure dates | Assign notes to surgical events |
| `HINT_DIAGNOSIS` | Most recent condition before note | Pre-fill diagnosis for validation |
| `HINT_WHO_GRADE` | Extracted from diagnosis text | Validate BRIM extraction |
| `HINT_MEDICATIONS` | Active meds at note time | Cross-reference prescriptions |

**Benefits:**
- ✅ **Faster extraction** - BRIM checks HINTs first
- ✅ **Validation** - Compare BRIM vs FHIR
- ✅ **Gap filling** - Use FHIR when narrative unclear

---

## 📊 Expected Pilot Outcomes

### For One Patient:
- **FHIR Structured Data:**
  - Demographics (1 record)
  - Surgeries (2-5 procedures expected)
  - Diagnoses (10-20 conditions)
  - Medications (50-100 orders)
  - Encounters (100+ visits)

- **Clinical Notes:**
  - 10-50 documents (operative notes, pathology, radiology, progress notes)
  - Decoded and sanitized text
  - Temporally assigned to surgical events

- **BRIM Variables:**
  - ~10-15 variables (surgery_number, document_type, diagnosis, WHO grade, etc.)
  - Domain-specific (neuro-oncology template)

- **Extraction Results:**
  - Structured output CSV from BRIM
  - Confidence scores per field
  - Validation flags where FHIR and BRIM disagree

### Success Criteria:
✅ FHIR data extracts without errors  
✅ Clinical notes discovered and decoded successfully  
✅ BRIM CSVs pass validation (11/5 columns correct)  
✅ HINT columns populated from FHIR context  
✅ surgery_number is first variable  
✅ Files ready for BRIM upload

---

## 🔧 Troubleshooting Guide

### AWS Connection Issues

**Problem:** "Cannot connect to Athena"
```bash
# Solution: Re-login to AWS SSO
aws sso login --profile 343218191717_AWSAdministratorAccess
```

**Problem:** "Database not found"
```bash
# Verify database name
aws athena list-databases --profile 343218191717_AWSAdministratorAccess
```

### Python Environment Issues

**Problem:** "Module not found"
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt
```

**Problem:** "PyAthena connection failed"
```bash
# Check S3 staging bucket exists
aws s3 ls s3://aws-athena-query-results-343218191717-us-east-1/ \
    --profile 343218191717_AWSAdministratorAccess
```

### FHIR Data Issues

**Problem:** "No patients found"
- Database may not have DocumentReference data
- Try exploring without filters
- Check different FHIR tables

**Problem:** "Binary decode error"
- Some Binary files are PDF/images, not text
- This is normal - script skips non-text files
- Increase `MAX_BINARY_SIZE_MB` if needed

### BRIM Issues

**Problem:** "API authentication failed"
- Verify API key in `.env`
- Check BRIM account is active
- Test API key in BRIM web interface

**Problem:** "CSV validation failed"
- Review validation errors
- Check column counts (11 for variables, 5 for decisions)
- Verify surgery_number is first variable

---

## 📚 Reference Documentation

### In This Repository:
- [Hybrid Strategy Guide](docs/HYBRID_FHIR_BRIM_EXTRACTION_STRATEGY.md)
- [README.md](README.md)
- Code docstrings in `src/` modules

### External Documentation:
- [BRIM Best Practices](/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/BRIM_CRITICAL_LESSONS_LEARNED.md)
- [BRIM Complete Workflow](/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/BRIM_COMPLETE_WORKFLOW_GUIDE.md)
- [FHIR Treatment Framework](/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/LONGITUDINAL_CANCER_TREATMENT_FRAMEWORK.md)

---

## 🎯 Next Steps After Pilot

1. **Review pilot results** - Check data quality and completeness
2. **Iterate on variables** - Add/modify based on extraction needs
3. **Expand to more patients** - Batch processing script
4. **Integrate with RADIANT** - Connect to portal workflows
5. **Build validation dashboard** - Compare FHIR vs BRIM results

---

## 👥 Support & Contact

**For questions:**
- GitHub Issues: RADIANT_PCA repository
- Documentation: This folder and `docs/`
- BRIM Support: support@brimhealth.com

**Key Files to Reference:**
- `.env` - All configuration
- `pilot_workflow.py` - Main script
- `src/fhir_extractor.py` - FHIR queries
- `src/brim_csv_generator.py` - CSV generation logic

---

## ✅ Pre-Flight Checklist

Before running pilot:

- [ ] AWS SSO logged in
- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip list` shows boto3, pyathena, etc.)
- [ ] `.env` file exists with correct credentials
- [ ] Can access Athena (run `--explore-only`)
- [ ] Know a patient ID to test with

---

**Ready to fly! 🚀**

Run: `python pilot_workflow.py --explore-only` to begin.
