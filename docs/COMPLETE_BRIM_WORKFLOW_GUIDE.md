# Complete BRIM Workflow Guide

**Last Updated:** October 2, 2025  
**Version:** 1.0  
**Purpose:** Comprehensive documentation for AI agents and developers working with BRIM Analytics

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Sources](#data-sources)
4. [CSV Format Specifications](#csv-format-specifications)
5. [Script Documentation](#script-documentation)
6. [Workflow Steps](#workflow-steps)
7. [Troubleshooting](#troubleshooting)
8. [Future Enhancements](#future-enhancements)

---

## Overview

### What is BRIM Analytics?

BRIM Analytics is a **hybrid FHIR + Clinical Notes extraction framework** that combines:
- **Structured FHIR data** from AWS S3 (Patient, Condition, Procedure, Medication, etc.)
- **Unstructured clinical notes** from Binary resources via DocumentReferences
- **BRIM Health's NLP platform** for LLM-based data extraction

### Key Innovation

Instead of extracting only from clinical notes OR only from FHIR, this approach:
1. Packages the entire FHIR Bundle as ONE "document" in BRIM
2. Extracts clinical notes from S3 Binary files as additional documents
3. Uses single-pass LLM extraction across both structured and unstructured sources

### Current Status

**Production Ready:** Pilot script validated and tested  
**Patient Coverage:** Configurable (currently pilot patient e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Clinical Notes:** 188 notes extracted from 388 DocumentReferences  
**FHIR Resources:** 1,770 resources in Bundle  

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      AWS S3 Bucket                           │
│  radiant-prd-343218191717-us-east-1-prd-ehr-pipeline       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  prd/ndjson/Patient/         ← Patient demographics         │
│  prd/ndjson/Condition/       ← Diagnoses                   │
│  prd/ndjson/Procedure/       ← Surgical procedures         │
│  prd/ndjson/Medication*/     ← Chemotherapy agents         │
│  prd/ndjson/Observation/     ← Lab results, vitals         │
│  prd/ndjson/DocumentReference/ ← Index to clinical notes   │
│  prd/source/Binary/          ← Clinical note content       │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           pilot_generate_brim_csvs.py                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Extract FHIR Bundle (1,770 resources)                  │
│  2. Query DocumentReferences (2,560 files via pagination)  │
│  3. Fetch Binary content from prd/source/Binary/{id}       │
│  4. Generate 3 CSVs: project, variables, decisions         │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    BRIM Platform                             │
│                 (app.brimhealth.com)                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Upload: variables.csv, decisions.csv, project.csv         │
│  LLM Extraction: GPT-4/Claude processes all documents      │
│  Output: 18 CSVs with extracted clinical variables         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **FHIR Bundle Creation**: Query 8 FHIR resource types from S3, combine into single JSON
2. **Clinical Notes Extraction**: 
   - List all 2,560 DocumentReference NDJSON files (S3 pagination)
   - Filter for target patient
   - Extract Binary IDs from DocumentReference.content[].attachment.url
   - Fetch Binary files from `prd/source/Binary/{binary_id}`
   - Decode base64 FHIR Binary.data content
   - Sanitize HTML to plain text
3. **CSV Generation**:
   - project.csv: 1 FHIR Bundle + 188 clinical notes = 189 rows
   - variables.csv: 13 extraction rules
   - decisions.csv: 5 aggregation rules
4. **BRIM Processing**: Upload CSVs, run extraction job, download results

---

## Data Sources

### S3 Bucket Structure

**Bucket:** `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`

#### FHIR Resources (ndjson/)

| Resource Type | Location | Count (Pilot) | Purpose |
|--------------|----------|---------------|---------|
| Patient | `prd/ndjson/Patient/` | 1 | Demographics, DOB, gender |
| Condition | `prd/ndjson/Condition/` | ~50 | Diagnoses, WHO grade |
| Procedure | `prd/ndjson/Procedure/` | ~30 | Surgeries, dates, types |
| MedicationRequest | `prd/ndjson/MedicationRequest/` | ~20 | Prescribed chemo agents |
| MedicationStatement | `prd/ndjson/MedicationStatement/` | ~15 | Administered medications |
| MedicationAdministration | `prd/ndjson/MedicationAdministration/` | ~10 | Med administration records |
| Observation | `prd/ndjson/Observation/` | ~100 | Labs, vitals, molecular markers |
| DiagnosticReport | `prd/ndjson/DiagnosticReport/` | ~20 | Pathology, radiology reports |

**Access Pattern:**
```python
s3_client.select_object_content(
    Bucket='radiant-prd-343218191717-us-east-1-prd-ehr-pipeline',
    Key='prd/ndjson/Patient/part-00000-*.ndjson',
    Expression="SELECT * FROM S3Object[*] s WHERE s.id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'"
)
```

#### Clinical Notes (Binary files)

**Index Location:** `prd/ndjson/DocumentReference/*.ndjson` (2,560 files)  
**Content Location:** `prd/source/Binary/{binary_id}`  
**Format:** FHIR Binary resources with base64-encoded content

**Access Pattern:**
```python
# Step 1: List all DocumentReference files with pagination
paginator = s3_client.get_paginator('list_objects_v2')
for page in paginator.paginate(Bucket=bucket, Prefix='prd/ndjson/DocumentReference/'):
    # Process each file
    
# Step 2: Extract Binary ID from DocumentReference
binary_id = doc_ref['content'][0]['attachment']['url'].split('/')[-1]

# Step 3: Fetch Binary file directly
binary_obj = s3_client.get_object(Bucket=bucket, Key=f'prd/source/Binary/{binary_id}')
```

**Success Rate:** ~48% (188 extracted from 388 DocumentReferences)  
**Failure Reason:** Binary files not yet downloaded from Epic to S3

### Patient Identifiers

**FHIR Patient ID:** `e4BwD8ZYDBccepXcJ.Ilo3w3` (used for S3 queries)  
**Subject ID (PERSON_ID):** `1277724` (used in BRIM CSVs)  

**Mapping:** Extracted from Patient resource's `identifier` array where `system = "urn:id:extID"`

---

## CSV Format Specifications

### Critical Format Rules (BRIM Platform Requirements)

#### Supported Data Types
- ✅ **text** - For all text, dates, numbers, categorical data
- ✅ **boolean** - For true/false values ONLY
- ❌ **date** - NOT SUPPORTED (use text with YYYY-MM-DD format)
- ❌ **integer** - NOT SUPPORTED (use text with numeric string)

#### Empty Field Rules
- **prompt_template** - MUST be empty (BRIM uses `instruction` field instead)
- **aggregation_instruction** - Leave empty unless specific aggregation needed
- **aggregation_prompt_template** - Leave empty to use default
- **only_use_true_value_in_aggregation** - Empty for non-boolean types
- **aggregation_option_definitions** - Empty unless custom aggregation options

#### CSV Formatting
- **Quoting:** Use `csv.QUOTE_MINIMAL` (only quote when necessary)
- **Encoding:** UTF-8
- **Line endings:** Unix (LF) or Windows (CRLF) both accepted

### 1. project.csv

**Purpose:** Contains the actual documents (FHIR Bundle + clinical notes) to extract from

**Format:** 5 columns
```csv
NOTE_ID,PERSON_ID,NOTE_DATETIME,NOTE_TEXT,NOTE_TITLE
```

**Field Specifications:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| NOTE_ID | Text | Unique document identifier | `FHIR_BUNDLE`, `doc-12345` |
| PERSON_ID | Text | Patient identifier (not FHIR ID) | `1277724` |
| NOTE_DATETIME | DateTime | ISO 8601 timestamp | `2024-01-15T10:30:00Z` |
| NOTE_TEXT | Text | Full document content | FHIR JSON or clinical note text |
| NOTE_TITLE | Text | Document type label | `FHIR_BUNDLE`, `OPERATIVE_NOTE` |

**Example Row:**
```csv
FHIR_BUNDLE,1277724,2024-10-02T12:00:00Z,"{""resourceType"":""Bundle"",""entry"":[...]}",FHIR Resource Bundle
```

**Pilot Output:**
- 1 FHIR Bundle (3.3 MB JSON, 1,770 resources)
- 188 clinical notes (plain text, HTML sanitized)
- **Total: 189 rows**

### 2. variables.csv

**Purpose:** Defines extraction rules for individual data points

**Format:** 11 columns
```csv
variable_name,instruction,prompt_template,aggregation_instruction,aggregation_prompt_template,variable_type,scope,option_definitions,aggregation_option_definitions,only_use_true_value_in_aggregation,default_value_for_empty_response
```

**Field Specifications:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| variable_name | ✅ | Text | Unique variable identifier (e.g., `patient_gender`) |
| instruction | ✅ | Text | **MAIN LLM PROMPT** - detailed extraction instructions |
| prompt_template | ✅ | Text | **MUST BE EMPTY** - leave blank to use default |
| aggregation_instruction | ❌ | Text | How to combine values across documents (empty = no aggregation) |
| aggregation_prompt_template | ❌ | Text | Custom aggregation prompt (empty = use default) |
| variable_type | ✅ | Text | `text` or `boolean` ONLY |
| scope | ✅ | Text | `one_per_note`, `many_per_note`, `one_per_patient` |
| option_definitions | ❌ | JSON | Categorical options `{"value1": "Label 1", "value2": "Label 2"}` |
| aggregation_option_definitions | ❌ | JSON | Options for aggregated results (empty = same as option_definitions) |
| only_use_true_value_in_aggregation | ❌ | Text | **EMPTY** for non-boolean, `true` for boolean if needed |
| default_value_for_empty_response | ✅ | Text | Value if not found (e.g., `unknown`, `Not documented`, `0`) |

**Example Variable:**
```csv
primary_diagnosis,"Extract the primary brain tumor diagnosis. If document_type is FHIR_BUNDLE: Check Condition resources for oncology diagnoses (code.coding.display fields). If narrative document: Look for diagnostic terms like glioblastoma, astrocytoma, medulloblastoma, ependymoma, oligodendroglioma, meningioma, etc. Include WHO grade if mentioned. Prioritize pathology-confirmed diagnoses over clinical impressions. Return the most specific diagnosis found.",,,,text,one_per_patient,,,,"unknown"
```

**Pilot Variables (13 total):**
1. document_type (text, one_per_note) - Classify document type
2. patient_gender (text, one_per_patient) - Extract gender
3. date_of_birth (text, one_per_patient) - Extract DOB in YYYY-MM-DD
4. primary_diagnosis (text, one_per_patient) - Extract brain tumor diagnosis
5. diagnosis_date (text, one_per_patient) - Date of diagnosis
6. who_grade (text, one_per_patient) - WHO tumor grade (I-IV)
7. surgery_date (text, many_per_note) - All surgery dates
8. surgery_type (text, many_per_note) - Surgery classification
9. extent_of_resection (text, many_per_note) - Resection extent
10. chemotherapy_agent (text, many_per_note) - Chemo drug names
11. radiation_therapy (boolean, one_per_patient) - Radiation received?
12. idh_mutation (text, one_per_patient) - IDH status
13. mgmt_methylation (text, one_per_patient) - MGMT status

### 3. decisions.csv

**Purpose:** Defines aggregation/cross-validation rules across variables

**Format:** 7 columns
```csv
decision_name,instruction,decision_type,prompt_template,variables,dependent_variables,default_value_for_empty_response
```

**Field Specifications:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| decision_name | ✅ | Text | Unique decision identifier |
| instruction | ✅ | Text | **MAIN LLM PROMPT** - aggregation/validation instructions |
| decision_type | ✅ | Text | `text` or `boolean` ONLY (no integer) |
| prompt_template | ✅ | Text | **MUST BE EMPTY** |
| variables | ✅ | JSON Array | List of input variables `["var1", "var2"]` |
| dependent_variables | ❌ | JSON Array | Additional dependencies (often empty `[]`) |
| default_value_for_empty_response | ✅ | Text | Default if decision cannot be made |

**Example Decision:**
```csv
confirmed_diagnosis,"Cross-validate primary diagnosis from FHIR and narrative sources. Compare primary_diagnosis values from FHIR_BUNDLE and narrative documents. If they match, return that diagnosis. If different, return both separated by ' OR '. Prioritize pathology reports.",text,,"[""primary_diagnosis""]","[]","unknown"
```

**Pilot Decisions (5 total):**
1. confirmed_diagnosis - Cross-validate diagnosis from multiple sources
2. total_surgeries - Count unique surgical procedures (returns text number)
3. best_resection - Determine most extensive resection achieved
4. chemotherapy_regimen - Aggregate all chemo agents into regimen
5. molecular_profile - Summarize IDH/MGMT testing results

---

## Script Documentation

### pilot_generate_brim_csvs.py

**Location:** `scripts/pilot_generate_brim_csvs.py`  
**Purpose:** Generate BRIM-compatible CSVs from FHIR data and clinical notes

#### Usage

```bash
# Basic usage (pilot patient)
python scripts/pilot_generate_brim_csvs.py \
    --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json

# Custom patient (future)
python scripts/pilot_generate_brim_csvs.py \
    --patient-id "Patient/xyz789" \
    --subject-id "123456" \
    --output-dir "custom_output/"
```

#### Command Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--bundle-path` | ✅ | None | Path to extracted FHIR Bundle JSON |
| `--patient-id` | ❌ | `e4BwD8ZYDBccepXcJ.Ilo3w3` | FHIR Patient ID |
| `--subject-id` | ❌ | `1277724` | PERSON_ID for BRIM |
| `--output-dir` | ❌ | `pilot_output/brim_csvs/` | Output directory |

#### Class: BRIMCSVGenerator

**Initialization:**
```python
generator = BRIMCSVGenerator(
    bundle_file='path/to/bundle.json',
    patient_id='e4BwD8ZYDBccepXcJ.Ilo3w3',
    subject_id='1277724',
    output_dir='pilot_output/brim_csvs/'
)
```

**Key Methods:**

##### extract_clinical_notes()
```python
def extract_clinical_notes(self) -> List[Dict]
```
Extracts clinical notes from S3 DocumentReferences and Binary files.

**Process:**
1. Uses S3 pagination to list ALL DocumentReference files (2,560 total)
2. Queries each file for patient's DocumentReferences
3. Extracts Binary IDs from `content[].attachment.url`
4. Fetches Binary content from `prd/source/Binary/{id}`
5. Decodes base64 FHIR Binary.data
6. Sanitizes HTML to plain text using BeautifulSoup
7. Returns list of note dictionaries

**Returns:**
```python
[
    {
        'note_id': 'doc-12345',
        'note_text': 'Operative Note: Patient underwent...',
        'note_datetime': '2023-05-15T10:00:00Z',
        'note_title': 'OPERATIVE NOTE'
    },
    ...
]
```

##### generate_project_csv()
```python
def generate_project_csv(self) -> Path
```
Creates project.csv with FHIR Bundle + clinical notes.

**Output:** `{output_dir}/project.csv` (189 rows for pilot)

##### generate_variables_csv()
```python
def generate_variables_csv(self) -> Path
```
Creates variables.csv with extraction rules.

**Output:** `{output_dir}/variables.csv` (13 variables for pilot)

##### generate_decisions_csv()
```python
def generate_decisions_csv(self) -> Path
```
Creates decisions.csv with aggregation rules.

**Output:** `{output_dir}/decisions.csv` (5 decisions for pilot)

##### generate_all()
```python
def generate_all(self) -> None
```
Main entry point - executes full workflow:
1. Extract clinical notes from S3
2. Generate project.csv
3. Generate variables.csv
4. Generate decisions.csv

#### Dependencies

```python
import os
import json
import csv
import boto3  # AWS S3 access
import base64  # Binary decoding
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup  # HTML sanitization
```

**Install:**
```bash
pip install boto3 beautifulsoup4 lxml
```

#### AWS Configuration

**Required:** AWS CLI configured with SSO profile
```bash
aws sso login --profile 343218191717_AWSAdministratorAccess
export AWS_PROFILE=343218191717_AWSAdministratorAccess
```

**IAM Permissions Needed:**
- `s3:ListBucket` on `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`
- `s3:GetObject` on `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/*`

---

## Workflow Steps

### Step 1: Extract FHIR Bundle (Prerequisite)

**Note:** This step is done separately before running the BRIM script.

```bash
# Extract FHIR resources for pilot patient
python src/fhir_extractor.py \
    --patient-id "e4BwD8ZYDBccepXcJ.Ilo3w3" \
    --output pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json
```

**Output:** JSON file with Bundle containing ~1,770 resources

### Step 2: Generate BRIM CSVs

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Run the script
python scripts/pilot_generate_brim_csvs.py \
    --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json
```

**Expected Output:**
```
📂 Loading FHIR Bundle from pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json
✅ Loaded bundle with 1770 resources

======================================================================
🚀 BRIM CSV GENERATION
======================================================================
FHIR Patient ID: e4BwD8ZYDBccepXcJ.Ilo3w3
Subject ID (PERSON_ID): 1277724
Output Dir: pilot_output/brim_csvs
======================================================================

📥 Extracting clinical notes from S3...
🔍 Listing all DocumentReference NDJSON files...
📄 Processing DocumentReference files: 100% (2560/2560)
✅ Found 388 DocumentReferences for patient
📝 Extracting Binary content...
✅ Extracted 188 clinical notes (48.5% success rate)

📝 Generating project.csv...
✅ Generated pilot_output/brim_csvs/project.csv with 189 rows

📋 Generating variables.csv...
✅ Generated pilot_output/brim_csvs/variables.csv with 13 variables

🎯 Generating decisions.csv...
✅ Generated pilot_output/brim_csvs/decisions.csv with 5 decisions

======================================================================
✅ GENERATION COMPLETE
======================================================================

📁 Generated files:
   1. pilot_output/brim_csvs/project.csv
   2. pilot_output/brim_csvs/variables.csv
   3. pilot_output/brim_csvs/decisions.csv
```

### Step 3: Upload to BRIM Platform

1. **Login:** https://app.brimhealth.com
2. **Navigate:** Projects → Your Project → Configuration
3. **Upload Variables & Decisions:**
   - Click "Upload Variables CSV"
   - Select `pilot_output/brim_csvs/variables.csv`
   - Click "Upload Decisions CSV"
   - Select `pilot_output/brim_csvs/decisions.csv`
   - **Verify:** "Upload successful" with no skip warnings

4. **Upload Project Data:**
   - Navigate to Data tab
   - Click "Upload Project CSV"
   - Select `pilot_output/brim_csvs/project.csv`
   - **Wait:** Large file (5-10 MB), may take 30-60 seconds

### Step 4: Run Extraction Job

1. **Start Extraction:**
   - Click "Run Extraction" button
   - Confirm job parameters
   - **Wait:** 10-30 minutes depending on document count

2. **Monitor Progress:**
   - Job status page shows progress
   - Email notification on completion

### Step 5: Download Results

1. **Download CSVs:**
   - Navigate to Results tab
   - Click "Download All Results"
   - **Expect:** 18 CSV files (13 variables + 5 decisions)

2. **Validation:**
   - Compare with manual CSVs in `/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/`
   - Calculate accuracy metrics

---

## Troubleshooting

### Common Upload Errors

#### "Skipped X variable lines due to incomplete info!"

**Cause:** BRIM detected missing required fields or unsupported data types

**Solutions:**
1. **Check variable_type:** Must be `text` or `boolean` (NOT `date` or `integer`)
2. **Check prompt_template:** Must be empty string (not filled)
3. **Check aggregation fields:** Should be empty unless specifically needed
4. **Check only_use_true_value_in_aggregation:** Should be empty for non-boolean types

**Example Fix:**
```python
# ❌ WRONG - using date type
{
    'variable_name': 'surgery_date',
    'variable_type': 'date',  # NOT SUPPORTED
}

# ✅ CORRECT - using text type
{
    'variable_name': 'surgery_date',
    'variable_type': 'text',  # Dates as text in YYYY-MM-DD format
    'instruction': 'Extract surgery date in YYYY-MM-DD format'
}
```

#### "Skipped X decision lines due to incomplete info!"

**Cause:** Decision type is not supported or variables array is malformed

**Solutions:**
1. **Check decision_type:** Must be `text` or `boolean` (NOT `integer`)
2. **Check variables field:** Must be valid JSON array `["var1", "var2"]`
3. **Check prompt_template:** Must be empty
4. **Check dependent_variables:** Should be empty array `[]` if not used

**Example Fix:**
```python
# ❌ WRONG - using integer type
{
    'decision_name': 'total_surgeries',
    'decision_type': 'integer',  # NOT SUPPORTED
}

# ✅ CORRECT - using text type
{
    'decision_name': 'total_surgeries',
    'decision_type': 'text',  # Return count as text "1", "2", etc.
}
```

### S3 Access Issues

#### AccessDenied on ListBucket

**Error:** `User is not authorized to perform: s3:ListBucket`

**Solution:**
```bash
# Re-authenticate with AWS SSO
aws sso login --profile 343218191717_AWSAdministratorAccess

# Verify credentials
aws sts get-caller-identity --profile 343218191717_AWSAdministratorAccess
```

#### Binary Files Not Found (48% success rate)

**Cause:** Binary files not yet downloaded from Epic to S3

**Impact:** Some clinical notes missing, but NOT a critical error

**Workaround:** 
- Accept current 48% extraction rate
- Future: Epic sync will populate missing Binary files

### CSV Format Issues

#### Headers not matching

**Cause:** Column order doesn't match BRIM specification

**Solution:** Use exact column order from this documentation

**Variables (11 columns):**
```
variable_name,instruction,prompt_template,aggregation_instruction,aggregation_prompt_template,variable_type,scope,option_definitions,aggregation_option_definitions,only_use_true_value_in_aggregation,default_value_for_empty_response
```

**Decisions (7 columns):**
```
decision_name,instruction,decision_type,prompt_template,variables,dependent_variables,default_value_for_empty_response
```

#### Encoding errors

**Cause:** Non-UTF-8 characters in clinical notes

**Solution:** Script already handles this with UTF-8 encoding and HTML sanitization

### Performance Issues

#### Slow DocumentReference querying

**Expected:** 2-3 minutes for 2,560 files with S3 pagination

**If slower:** Check network connection and AWS region latency

#### Large project.csv upload timeout

**Expected:** 30-60 seconds for 5-10 MB file

**If timeout:** 
- Check file size (should be < 10 MB)
- Try splitting into multiple projects if needed

---

## Future Enhancements

### Short Term

1. **Multiple Patients:**
   - Remove hardcoded pilot patient ID
   - Add batch processing loop
   - Generate separate CSVs per patient

2. **Error Recovery:**
   - Retry logic for S3 failures
   - Partial extraction save/resume
   - Better logging and progress tracking

3. **Binary Extraction Optimization:**
   - Check for Binary file existence before fetching
   - Batch download Binary files
   - Cache results to avoid re-downloading

### Long Term

1. **Automated Workflow:**
   - End-to-end script: FHIR extraction → BRIM CSVs → Upload → Download results
   - Scheduled runs for new patients
   - Integration with BRIM API (when available)

2. **Validation Pipeline:**
   - Compare BRIM results with manual CSVs
   - Calculate accuracy metrics automatically
   - Flag discrepancies for review

3. **Production Scaling:**
   - Process hundreds of patients in parallel
   - Distributed S3 querying
   - Optimize for 10,000+ documents per patient

4. **Custom Variables:**
   - Configuration file for variables/decisions
   - Easy addition of new variables without code changes
   - Template-based prompt generation

---

## References

### Key Files

- **Main Script:** `scripts/pilot_generate_brim_csvs.py`
- **Example CSVs:** `pilot_output/brim_csvs/`
- **Production Config:** `/Users/resnick/Downloads/fhir_athena_crosswalk/brim_workspace/production/config/`
- **Manual CSVs:** `/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/`

### Documentation

- **BRIM Format Spec:** (embedded in this document)
- **FHIR Resources:** https://www.hl7.org/fhir/
- **AWS S3 API:** https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html

### Contact

**Repository:** https://github.com/adamcresnick/RADIANT_PCA/tree/main/BRIM_Analytics  
**Last Updated:** October 2, 2025  
**Maintainer:** Adam Resnick (via AI agent assistance)

---

**End of Complete BRIM Workflow Guide**
