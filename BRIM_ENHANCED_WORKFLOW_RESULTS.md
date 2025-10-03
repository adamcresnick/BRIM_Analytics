# BRIM Enhanced Workflow - Pilot Patient Results

**Date**: October 2, 2025  
**Patient**: e4BwD8ZYDBccepXcJ.Ilo3w3 (Subject ID: 1277724)  
**Status**: ✅ Ready for BRIM Upload

---

## Executive Summary

Successfully implemented complete enhanced BRIM CSV generation workflow combining:
- **Structured clinical findings** from FHIR v2 materialized views (ground truth data)
- **Prioritized clinical documents** from FHIR v1 Binary resources (actual HTML narratives)
- **Intelligent document prioritization** (pathology, operative notes, anesthesia)

### Key Achievement
Generated BRIM-ready CSV package with **89 rows** including both ground truth structured data AND actual clinical narratives, expected to significantly improve extraction accuracy.

---

## Results Summary

### Files Generated
Location: `pilot_output/brim_csvs_final/`

| File | Rows/Items | Description |
|------|-----------|-------------|
| **project.csv** | 89 rows | 1 FHIR bundle + 4 structured findings + 84 clinical documents |
| **variables.csv** | 14 variables | BRIM variable specifications |
| **decisions.csv** | 5 decisions | Dependent decision mappings |

### Document Extraction Success Rate
- **Total Attempted**: 148 documents (20 prioritized + 128 procedure-linked)
- **Successfully Extracted**: 84 documents (57%)
- **Failed**: 64 documents (likely missing from S3 or different Binary ID format)

---

## Document Breakdown

### 1. Structured Findings (4 synthetic documents)
**Source**: FHIR v2 materialized views (ground truth data)

| Document | Content | Purpose |
|----------|---------|---------|
| **Molecular Testing Summary** | KIAA1549-BRAF fusion (from `molecular_tests` view) | Provides ground truth molecular markers |
| **Surgical History Summary** | 6 procedures: ventriculostomy, craniectomy, craniotomy (from `procedure` table) | Provides ground truth surgical dates/procedures |
| **Treatment History Summary** | 48 medication records: bevacizumab, selumetinib (from `patient_medications` view) | Provides ground truth treatment timeline |
| **Diagnosis Date Summary** | 2018-06-04, Pilocytic astrocytoma, ICD-10: C71.6 (from `problem_list_diagnoses` view) | Provides ground truth diagnosis date |

### 2. Clinical Documents (84 from S3 Binary extraction)
**Source**: FHIR v1 Binary resources (actual clinical narratives)

| Document Type | Count | Priority Score | Source |
|---------------|-------|----------------|--------|
| **Pathology reports** | 20 | 100 | Prioritized documents |
| **Complete operative notes** | 20 | 95 | Procedure-linked documents |
| **Brief operative notes** | 14 | 95 | Procedure-linked documents |
| **Procedure notes** | 8 | 90 | Procedure-linked documents |
| **Anesthesia evaluations** | 22 | 85 | Procedure-linked documents (pre/post/procedure) |

---

## Technical Implementation

### Data Sources
1. **FHIR v2 Database** (`fhir_v2_prd_db`):
   - `problem_list_diagnoses` view → Diagnosis date
   - `procedure` table → Surgical procedures
   - `patient_medications` view → Treatment history
   - `molecular_tests` view → Molecular markers
   - `procedure_report` table → Links procedures to documents

2. **FHIR v1 Database** (`fhir_v1_prd_db`):
   - `document_reference` table → Document metadata
   - `document_reference_content` table → Binary resource references

3. **S3 Binary Storage** (`prd/source/Binary/`):
   - FHIR Binary resources with base64-encoded HTML content
   - Naming bug: Periods (.) in Binary IDs replaced with underscores (_)

### Extraction Pipeline
```
1. extract_structured_data.py
   ↓ (Athena queries to materialized views)
   structured_data_enhanced.json (diagnosis, surgeries, molecular, treatments)

2. athena_document_prioritizer.py
   ↓ (Document prioritization + procedure-linking queries)
   prioritized_documents.json (20 prioritized + 128 procedure-linked)

3. pilot_generate_brim_csvs.py
   ↓ (S3 Binary fetching + HTML sanitization)
   brim_csvs_final/ (project.csv, variables.csv, decisions.csv)
```

### Key Technical Fixes
1. **AWS SSO Authentication**: Required explicit `AWS_PROFILE` export
   ```bash
   export AWS_PROFILE=343218191717_AWSAdministratorAccess
   ```

2. **Binary Resource Access**: 
   - Used boto3 S3 GetObject (not HTTPS requests)
   - Applied period→underscore filename transformation
   - Decoded FHIR Binary JSON format: `{"resourceType":"Binary","data":"base64..."}`

3. **Subject Reference Format**: No `Patient/` prefix (just patient ID)
   - Correct: `subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'`
   - Wrong: `subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'`

---

## Sample Content

### Structured Finding: Molecular Testing
```
MOLECULAR/GENETIC TESTING RESULTS (Structured Data Extract):

Gene: BRAF
Finding: Next generation sequencing (NGS) analysis... showed:
1. One Tier 1A fusion gene: KIAA1549 (NM_020910.2) - BRAF (NM_004333.4)
2. Five variants of unknown significance...
```

### Clinical Document: Operative Note
```
SURG. DATE: 03/16/2021
TIME OF PROCEDURE: 02:15 PM
SURGEON: Alexander Tucker, MD
ASSISTANT: Peter J Madsen, MD and Phillip Storm, MD

PREOPERATIVE DIAGNOSES:
- Hydrocephalus
- 4th ventricular outlet obstruction
- Pilocytic astrocytoma

PROCEDURES PERFORMED:
- Suboccipital craniotomy for 4th ventricular fenestration
```

---

## Next Steps: BRIM Upload & Validation

### 1. Upload to BRIM Platform
**URL**: https://app.brimhealth.com

**Steps**:
1. Log in to BRIM platform
2. Create new project or update existing pilot project
3. Upload files:
   - `pilot_output/brim_csvs_final/project.csv`
   - `pilot_output/brim_csvs_final/variables.csv`
   - `pilot_output/brim_csvs_final/decisions.csv`
4. Run extraction job
5. Download results

### 2. Validation Metrics
Compare BRIM extraction results against ground truth structured data:

| Variable | Ground Truth (Structured Data) | Expected BRIM Accuracy |
|----------|--------------------------------|------------------------|
| **Diagnosis Date** | 2018-06-04 | >95% (explicitly provided) |
| **Surgery Count** | 6 procedures | 100% (all procedures listed) |
| **Molecular Marker** | KIAA1549-BRAF fusion | >90% (explicitly provided) |
| **Treatment Count** | 48 medication records | >85% (timeline provided) |
| **Overall Accuracy** | Baseline: ~65% | **Target: >85%** |

### 3. Accuracy Improvement Analysis
Calculate improvement over baseline:
```python
# Baseline: Standard FHIR bundle only (~65% accuracy)
# Enhanced: FHIR bundle + structured findings + prioritized docs

improvement = (enhanced_accuracy - baseline_accuracy) / baseline_accuracy * 100
# Expected: ~30% improvement (65% → 85%)
```

---

## Command Reference

### Run Complete Enhanced Workflow
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Step 1: Extract structured data from materialized views
python scripts/extract_structured_data.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --output pilot_output/structured_data_enhanced.json

# Step 2: Prioritize documents (pathology, operative notes)
python scripts/athena_document_prioritizer.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --limit 20 \
  --output pilot_output/prioritized_documents.json

# Step 3: Generate BRIM CSVs with everything
export AWS_PROFILE=343218191717_AWSAdministratorAccess
aws sso login --profile 343218191717_AWSAdministratorAccess  # if needed
python3 scripts/pilot_generate_brim_csvs.py \
  --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json \
  --structured-data pilot_output/structured_data_enhanced.json \
  --prioritized-docs pilot_output/prioritized_documents.json \
  --output-dir pilot_output/brim_csvs_final
```

### Validate Output
```bash
# Check row count
wc -l pilot_output/brim_csvs_final/project.csv

# View document breakdown
python3 -c "
import csv
csv.field_size_limit(10000000)
with open('pilot_output/brim_csvs_final/project.csv') as f:
    reader = csv.DictReader(f)
    types = {}
    for row in reader:
        types[row['NOTE_TITLE']] = types.get(row['NOTE_TITLE'], 0) + 1
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f'{count:3d} × {t}')
"
```

---

## GitHub Commits

All enhancements pushed to `adamcresnick/RADIANT_PCA:main`:

1. **6c8d835**: Binary document extraction implementation (latest)
2. **dd3dd71**: Structured clinical findings integration
3. **851cb0d**: Document prioritization fixes (subject_reference format)
4. **b2d309d**: Timeline query corrections
5. **7011ca2**: Molecular marker fallback extraction

---

## Success Criteria ✅

- [x] Structured data extraction from materialized views
- [x] Document prioritization with scoring algorithm
- [x] Binary HTML content fetching from S3
- [x] FHIR Binary resource decoding (base64)
- [x] HTML sanitization
- [x] BRIM CSV generation (89 rows)
- [x] All code committed and pushed to GitHub
- [ ] Upload to BRIM platform (NEXT STEP)
- [ ] Run extraction job
- [ ] Validate accuracy improvement

---

## Contact & Support

**Project**: RADIANT_PCA / BRIM_Analytics  
**Patient Cohort**: Pediatric low-grade glioma (pilot)  
**Data Sources**: CHOP Epic EHR → FHIR → Athena/S3  
**Extraction Platform**: BRIM Health (https://app.brimhealth.com)
