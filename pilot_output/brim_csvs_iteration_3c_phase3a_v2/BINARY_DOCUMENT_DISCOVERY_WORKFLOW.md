# Binary Document Discovery and Annotation Workflow
**Date**: October 4, 2025  
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Purpose**: Document the complete workflow for discovering, validating, and annotating S3-available Binary clinical documents for BRIM extraction

---

## 📋 Overview

This workflow enables systematic discovery of all S3-available Binary clinical documents for a patient, with comprehensive metadata annotations to support targeted document selection for BRIM free-text extraction.

**Key Outputs:**
1. `accessible_binary_files.csv` - All S3-available documents with basic metadata (3,865 documents)
2. `accessible_binary_files_annotated.csv` - Enhanced with content_type, category_text, and type_coding_display (3,865 documents)

**Total Documents Found:**
- **6,280 DocumentReferences** in fhir_v1_prd_db.document_reference
- **3,865 S3-Available Binary files** (61.5% availability rate)
- **2,415 S3-Unavailable** (38.5% - Binary files not in S3)

---

## 🔧 Workflow Steps

### Step 1: Query All DocumentReferences with Binary IDs

**Script**: `scripts/query_accessible_binaries.py`

**Query Strategy:**
```sql
SELECT 
    dr.id as document_reference_id,
    dr.type_text as document_type,
    drtc.type_coding_display as type_coding_display,
    dr.date as document_date,
    drc.content_attachment_url as binary_id,
    drc.content_attachment_content_type as content_type,
    drcat.category_text as category_text,
    dr.description as document_description,
    dr.context_period_start as context_start,
    dr.context_period_end as context_end
FROM fhir_v1_prd_db.document_reference dr
INNER JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_category drcat
    ON dr.id = drcat.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND drc.content_attachment_url IS NOT NULL
    AND drc.content_attachment_url != ''
    AND drc.content_attachment_url LIKE 'Binary/%'
ORDER BY dr.date DESC;
```

**Key Points:**
- Query `fhir_v1_prd_db` (NOT fhir_v2_prd_db) for DocumentReference resources
- INNER JOIN with `document_reference_content` to get Binary IDs
- LEFT JOIN with `document_reference_type_coding` for type_coding_display
- LEFT JOIN with `document_reference_category` for category_text
- Filter: `subject_reference = '{PATIENT_FHIR_ID}'` (NO "Patient/" prefix)
- Filter: Binary ID must be present and start with "Binary/"

**Critical Configuration:**
```python
AWS_PROFILE = "343218191717_AWSAdministratorAccess"
AWS_REGION = "us-east-1"
ATHENA_DATABASE = "fhir_v1_prd_db"
S3_BUCKET = "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline"
S3_PREFIX = "prd/source/Binary/"
PATIENT_FHIR_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"
```

**S3 Naming Bug Fix:**
```python
# Binary IDs in FHIR have periods (.), but S3 files use underscores (_)
s3_filename = binary_id.replace('.', '_')
s3_key = f"{S3_PREFIX}{s3_filename}"

# Example:
# FHIR Binary ID: "fHw5lxTPzUVaBIhcFxkhV.5LfcVwfvri28QqHYOVZSnk4"
# S3 Key: "prd/source/Binary/fHw5lxTPzUVaBIhcFxkhV_5LfcVwfvri28QqHYOVZSnk4"
```

---

### Step 2: Verify S3 Availability for Each Binary

**Method:**
```python
def check_s3_availability(binary_id):
    """Check if Binary file exists in S3."""
    if not binary_id or binary_id == 'Binary/':
        return False
    
    # Extract ID from Binary/xxx format
    if binary_id.startswith('Binary/'):
        binary_id = binary_id.replace('Binary/', '')
    
    # Apply period-to-underscore bug fix
    s3_key = f"prd/source/Binary/{binary_id.replace('.', '_')}"
    
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except:
        return False
```

**Performance:**
- Checks 6,280 documents in ~10-15 minutes
- Progress indicator every 100 documents
- Uses boto3 `head_object` (metadata check only, no file download)

**Results (C1277724):**
- **3,865 accessible** (61.5%)
- **2,415 unavailable** (38.5%)

---

### Step 3: Annotate with Additional Metadata

**Script**: `scripts/annotate_accessible_binaries.py`

**Purpose**: Enhance basic metadata with three additional columns from related tables:
1. `type_coding_display` - From `document_reference_type_coding`
2. `content_type` - From `document_reference_content.content_attachment_content_type`
3. `category_text` - From `document_reference_category`

**Approach**: Batch queries (1000 IDs at a time due to query length limits)

**Query Example (type_coding_display):**
```sql
SELECT 
    document_reference_id,
    type_coding_display
FROM fhir_v1_prd_db.document_reference_type_coding
WHERE document_reference_id IN ('fVoLUv7OE...', 'fVoLUv7OE...', ...)
```

**Implementation Notes:**
- Reads existing `accessible_binary_files.csv`
- Runs 3 separate queries (one per annotation column)
- Creates Python dictionaries to map document_reference_id → value
- Merges annotations into existing document records
- Outputs `accessible_binary_files_annotated.csv`

---

## 📊 Document Type Distribution

### Document Types (from `document_type` field)
Based on 3,865 S3-available documents:

| Document Type | Count | Percentage |
|--------------|-------|------------|
| Progress Notes | 1,277 | 33.0% |
| Encounter Summary | 761 | 19.7% |
| Telephone Encounter | 397 | 10.3% |
| Unknown | 182 | 4.7% |
| Diagnostic imaging study | 163 | 4.2% |
| Assessment & Plan Note | 148 | 3.8% |
| Patient Instructions | 107 | 2.8% |
| After Visit Summary | 97 | 2.5% |
| Nursing Note | 64 | 1.7% |
| Consult Note | 44 | 1.1% |
| **Other types** | 625 | 16.2% |

### Content Types (from `content_type` field)
Based on annotated subset (1,000 documents):

| Content Type | Count | Percentage |
|-------------|-------|------------|
| application/xml | 762 | 76.2% |
| text/xml | 83 | 8.3% |
| text/rtf | 79 | 7.9% |
| text/html | 34 | 3.4% |
| application/pdf | 28 | 2.8% |
| image/tiff | 10 | 1.0% |
| video/quicktime | 2 | 0.2% |
| image/png | 1 | 0.1% |
| image/jpeg | 1 | 0.1% |

### Category Text (from `category_text` field)
Based on annotated subset (1,000 documents):

| Category | Count | Percentage |
|----------|-------|------------|
| Summary Document | 762 | 76.2% |
| Clinical Note | 112 | 11.2% |
| External C-CDA Document | 83 | 8.3% |
| Document Information | 26 | 2.6% |
| Imaging Result | 16 | 1.6% |
| Clinical Reference | 1 | 0.1% |

---

## 📁 Output Files

### File 1: `accessible_binary_files.csv`
**Created by**: `scripts/query_accessible_binaries.py`  
**Rows**: 3,865 (S3-available documents only)  
**Columns**:
1. `document_reference_id` - FHIR DocumentReference.id
2. `document_type` - DocumentReference.type.text
3. `document_type_code` - (empty placeholder)
4. `document_date` - DocumentReference.date
5. `binary_id` - Binary resource ID (format: "Binary/fXXXXX...")
6. `description` - DocumentReference.description
7. `context_start` - DocumentReference.context.period.start
8. `context_end` - DocumentReference.context.period.end
9. `s3_available` - Always "Yes" (unavailable docs filtered out)

**Sample Row:**
```csv
fVoLUv7OE3ZAxE2nz1L-X.9XL299H4D3APe7k4Ok.L1k4,Encounter Summary,,2025-08-01T06:13:10Z,Binary/fHw5lxTPzUVaBIhcFxkhV.5LfcVwfvri28QqHYOVZSnk4,,2016-11-22,2016-11-22,Yes
```

---

### File 2: `accessible_binary_files_annotated.csv`
**Created by**: `scripts/annotate_accessible_binaries.py`  
**Rows**: 3,865 (same as File 1)  
**Columns**: 11 (adds 3 annotation columns)
1. `document_reference_id`
2. `document_type`
3. `document_type_code`
4. **`type_coding_display`** ← NEW (from document_reference_type_coding)
5. `document_date`
6. `binary_id`
7. **`content_type`** ← NEW (from document_reference_content)
8. **`category_text`** ← NEW (from document_reference_category)
9. `description`
10. `context_start`
11. `context_end`
12. `s3_available`

**Sample Row:**
```csv
fVoLUv7OE3ZAxE2nz1L-X.9XL299H4D3APe7k4Ok.L1k4,Encounter Summary,,,2025-08-01T06:13:10Z,Binary/fHw5lxTPzUVaBIhcFxkhV.5LfcVwfvri28QqHYOVZSnk4,application/xml,Summary Document,,2016-11-22,2016-11-22,Yes
```

**Note**: First 1,000 rows have annotations populated; remaining 2,865 rows have empty values for `type_coding_display`, `content_type`, and `category_text`. Can be expanded by running annotation script with batching.

---

## 🎯 Use Cases

### Use Case 1: Targeted Document Selection for BRIM
**Scenario**: Select 15-20 high-value documents for `project.csv` based on HIGHEST_VALUE_BINARY_DOCUMENT_SELECTION_STRATEGY.md

**Filter Examples:**
```python
# Surgical pathology reports
pathology_docs = df[
    (df['document_type'].str.contains('Pathology|Surgical Path', case=False)) &
    (df['document_date'] >= '2018-05-20') &
    (df['document_date'] <= '2018-06-05')
]

# Molecular testing reports
molecular_docs = df[
    (df['document_type'].str.contains('Molecular|Genetic|BRAF', case=False)) |
    (df['description'].str.contains('KIAA1549|BRAF|fusion', case=False))
]

# MRI radiology reports - diagnosis period
mri_diagnosis = df[
    (df['document_type'].str.contains('imaging|radiology|MRI', case=False)) &
    (df['document_date'] >= '2018-05-20') &
    (df['document_date'] <= '2018-05-31')
]

# Oncology consultation notes
oncology_notes = df[
    (df['document_type'].str.contains('Consult|Consultation', case=False)) &
    (df['category_text'] == 'Clinical Note')
]
```

---

### Use Case 2: Document Type Analysis
**Scenario**: Understand what document types are available for variable extraction

**Analysis:**
```python
import pandas as pd

df = pd.read_csv('accessible_binary_files_annotated.csv')

# Group by document_type and content_type
summary = df.groupby(['document_type', 'content_type']).size().reset_index(name='count')
summary = summary.sort_values('count', ascending=False)

# Identify PDF documents (good for pathology/radiology reports)
pdf_docs = df[df['content_type'] == 'application/pdf']
print(f"PDF documents: {len(pdf_docs)} (likely pathology/radiology reports)")

# Identify RTF documents (often operative notes)
rtf_docs = df[df['content_type'] == 'text/rtf']
print(f"RTF documents: {len(rtf_docs)} (likely operative notes)")

# Identify imaging results
imaging_docs = df[
    (df['category_text'] == 'Imaging Result') |
    (df['document_type'].str.contains('imaging|radiology', case=False))
]
print(f"Imaging documents: {len(imaging_docs)}")
```

---

### Use Case 3: Temporal Document Selection
**Scenario**: Select documents from specific time periods (diagnosis, treatment, progression, surveillance)

**Critical Time Windows for C1277724:**
1. **Diagnosis**: 2018-05-20 to 2018-06-05 (initial diagnosis + surgery #1)
2. **First Treatment**: 2018-10-01 to 2019-05-01 (Vinblastine)
3. **First Progression**: 2019-04-25 to 2019-05-15 (progression + treatment change)
4. **Second Surgery**: 2021-02-08 to 2021-03-10 (recurrence + surgery #2)
5. **Current Treatment**: 2021-05-01 to present (Selumetinib)

**Filter Example:**
```python
# Diagnosis period documents
diagnosis_docs = df[
    (df['document_date'] >= '2018-05-20') &
    (df['document_date'] <= '2018-06-05')
].sort_values('document_date')

# Group by document type to see what's available
print(diagnosis_docs['document_type'].value_counts())
```

---

## 🔄 Workflow Execution

### Quick Start: Run Complete Workflow

```bash
# Step 1: Query all DocumentReferences and verify S3 availability
python3 scripts/query_accessible_binaries.py

# Output: accessible_binary_files.csv (3,865 rows)

# Step 2: Annotate with additional metadata
python3 scripts/annotate_accessible_binaries.py

# Output: accessible_binary_files_annotated.csv (3,865 rows with 3 extra columns)
```

### Execution Time
- **Step 1**: ~10-15 minutes (6,280 S3 head_object checks)
- **Step 2**: ~2-3 minutes (3 Athena queries for first 1,000 docs)
- **Total**: ~12-18 minutes

---

## 🚨 Common Issues & Solutions

### Issue 1: Wrong S3 Bucket
**Symptom**: 0% S3 availability rate (all documents show unavailable)

**Solution**: Verify S3_BUCKET is correct
```python
# WRONG: S3_BUCKET = "healthlake-fhir-data-343218191717-us-east-1"
# CORRECT:
S3_BUCKET = "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline"
```

---

### Issue 2: Patient ID Format in Query
**Symptom**: 0 DocumentReferences returned from Athena query

**Solution**: Remove "Patient/" prefix from subject_reference filter
```sql
-- WRONG: WHERE dr.subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
-- CORRECT:
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

---

### Issue 3: Period vs Underscore in S3 Keys
**Symptom**: Some Binary files not found despite being in S3

**Solution**: Apply period-to-underscore conversion
```python
# Binary IDs have periods, S3 files use underscores (S3 naming bug)
s3_key = f"prd/source/Binary/{binary_id.replace('.', '_')}"
```

---

### Issue 4: Query Length Limits in Annotation Script
**Symptom**: Annotation script only processes first 1,000 documents

**Solution**: Implement batching (divide doc_ref_ids into chunks of 1,000)
```python
# Current: Only processes first 1,000
doc_ref_ids[:1000]

# Enhanced: Batch all documents
for i in range(0, len(doc_ref_ids), 1000):
    batch = doc_ref_ids[i:i+1000]
    # Run query for this batch
```

---

## 📈 Expected Results (C1277724)

### Query Statistics
- **Total DocumentReferences**: 6,280
- **S3-Available**: 3,865 (61.5%)
- **S3-Unavailable**: 2,415 (38.5%)

### Document Type Coverage
- **Clinical Notes**: 1,277 Progress Notes + 148 Assessment & Plan Notes = **1,425 total**
- **Encounter Summaries**: 761 (19.7%)
- **Imaging Studies**: 163 (4.2%)
- **Consultation Notes**: 44 (1.1%)

### Content Format Distribution
- **XML**: 845 documents (82.5% of annotated subset)
- **RTF**: 79 documents (7.7% - likely operative notes)
- **PDF**: 28 documents (2.7% - likely pathology/radiology reports)
- **HTML**: 34 documents (3.3%)
- **Images**: 12 documents (1.2% - TIFF, PNG, JPEG)

---

## 🎓 Lessons Learned

### Lesson 1: Use fhir_v1_prd_db for Binary Documents
DocumentReference resources with Binary content are in `fhir_v1_prd_db`, NOT `fhir_v2_prd_db`.

### Lesson 2: S3 Naming Bug is Critical
Binary IDs use periods (.) but S3 files use underscores (_). Always apply conversion when checking S3 availability.

### Lesson 3: JOINs on Large Tables Are Slow
Initial approach with 3 LEFT JOINs timed out. Better to query base documents first, then add annotations in separate queries.

### Lesson 4: Athena Query Length Limits
Cannot pass 6,280 IDs in a single IN clause. Batch queries into groups of 1,000 IDs.

### Lesson 5: 61.5% Availability is Expected
Based on empirical testing (BRIM_ENHANCED_WORKFLOW_RESULTS.md: 84/148 = 57%), expect ~60% of DocumentReferences to have S3 Binary files.

---

## 🔗 Related Documentation

- **HIGHEST_VALUE_BINARY_DOCUMENT_SELECTION_STRATEGY.md** - Strategy for selecting 15-20 targeted documents from the 3,865 available
- **BINARY_S3_AVAILABILITY_ANALYSIS.md** - Analysis of S3 availability patterns (57-61% success rate)
- **ENHANCED_WORKFLOW_VS_PHASE3A_V2_COMPARISON.md** - Architectural differences between workflows
- **PATIENT_IMAGING_CSV_REVIEW.md** - Using imaging CSV metadata to guide radiology report selection

---

## ✅ Validation Checklist

Before using `accessible_binary_files_annotated.csv`:

- [ ] Verify 3,865 rows (S3-available documents only)
- [ ] Check date range: earliest to latest document_date spans patient timeline
- [ ] Confirm S3_BUCKET: `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`
- [ ] Validate S3_PREFIX: `prd/source/Binary/`
- [ ] Test sample Binary retrieval: `aws s3 cp s3://{bucket}/{prefix}{binary_id_with_underscores} test.xml`
- [ ] Verify document type distribution matches expectations (Progress Notes ~33%, Encounter Summary ~20%)
- [ ] Check content_type annotations present for first ~1,000 rows
- [ ] Confirm category_text annotations present for first ~1,000 rows

---

## 📝 Next Steps

1. **Expand Annotations** (Optional): Run `annotate_accessible_binaries.py` with batching to annotate all 3,865 documents (currently only first 1,000 have annotations)

2. **Filter for High-Value Documents**: Apply HIGHEST_VALUE_BINARY_DOCUMENT_SELECTION_STRATEGY.md criteria to select 15-20 documents:
   - 2 Surgical pathology reports (2018-05-29, 2021-03-10)
   - 1 Molecular testing report (KIAA1549-BRAF fusion)
   - 2 Complete operative notes (2018-05-28, 2021-03-10)
   - 1 Pre-operative MRI report (2018-05-27)
   - 1-2 Progression MRI reports (2019-04-25, 2021-02-08)
   - 2-4 Oncology consultation notes (treatment planning)
   - 3-5 Recent surveillance MRI reports (2023-2025)

3. **Retrieve Binary Content**: Use `scripts/pilot_generate_brim_csvs.py._fetch_binary_content()` to download selected Binary files

4. **Update project.csv**: Add selected documents to `project.csv` for BRIM extraction

5. **Upload to BRIM**: Execute Phase 3a_v2 with enhanced document set for >85% accuracy target

---

**Last Updated**: October 4, 2025  
**Scripts**: 
- `scripts/query_accessible_binaries.py` (Step 1)
- `scripts/annotate_accessible_binaries.py` (Step 2)

**Outputs**: 
- `accessible_binary_files.csv` (3,865 rows, 9 columns)
- `accessible_binary_files_annotated.csv` (3,865 rows, 12 columns)
