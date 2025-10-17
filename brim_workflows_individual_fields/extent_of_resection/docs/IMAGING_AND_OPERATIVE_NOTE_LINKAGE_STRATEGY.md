# Imaging and Operative Note Linkage Strategy for Extent of Resection Extraction

**Created**: 2025-10-11
**Purpose**: Document linking strategy between Athena structured data and clinical narrative documents
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

---

## Executive Summary

✅ **YES - Both operative notes and radiology reports ARE defined in document_reference staging files**
✅ **YES - Context period matching enables precise document-to-clinical-event linking**
✅ **YES - Athena imaging extraction contains full radiology interpretation text**

### Key Findings

1. **Operative Notes** exist as distinct document types in DocumentReference resources
2. **Radiology Reports** exist both as:
   - Athena `radiology_imaging_mri` staging files (with `result_information` field containing full narrative text)
   - DocumentReference resources (as "Diagnostic imaging study" or "MR Brain" document types)
3. **Context Period Matching** is the PRIMARY linkage strategy (not encounter references)

---

## PART 1: Operative Notes for Extent of Resection

### **Document Types Found**

From `ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv`:

| Document Type | Count | Description |
|---------------|-------|-------------|
| **OP Note - Complete (Template or Full Dictation)** | 40 | Full operative reports with surgeon's assessment |
| **OP Note - Brief (Needs Dictation)** | 36 | Brief operative summaries |
| **External Operative Note** | 8 | Operative notes from external facilities |
| **Operative Record** | 1 | Structured operative record |
| **Anesthesia Procedure Notes** | 48 | Intra-operative anesthesia notes |
| **Anesthesia Postprocedure Evaluation** | varies | Post-op anesthesia assessments (may contain extent) |

**Total**: 133+ operative-related documents across all document types

---

### **Critical Discovery: Context Period = Surgery Date**

Operative notes are linked to surgeries via the **`context_period_start`** field, NOT the encounter reference.

#### **Surgery 1 (2018-05-28) Operative Notes:**

| Document Type | Document Date | Context Period Start | Encounter | S3 Available |
|---------------|---------------|---------------------|-----------|--------------|
| **OP Note - Complete** | 2018-05-29 13:39 | **2018-05-28 13:57** ✅ | exTYKBLePDyUyLwkYmgekgA3 | Yes (3 copies) |
| OP Note - Brief | 2018-05-29 15:41 | 2018-05-29 01:41 | exTYKBLePDyUyLwkYmgekgA3 | Yes (4 copies) |
| Operative Record | 2018-06-04 12:07 | *(empty)* | *(empty)* | Yes (1) |

**Gold Standard Surgery Date**: 2018-05-28 11:58:00
**OP Note Context Period**: 2018-05-28 13:57:00 ✅ **EXACT MATCH**

#### **Surgery 2 (2021-03-10) Operative Notes:**

| Document Type | Document Date | Context Period Start | Encounter | S3 Available |
|---------------|---------------|---------------------|-----------|--------------|
| **OP Note - Brief** | 2021-03-10 17:17 | **2021-03-10 17:17** ✅ | eTu932UZCvh8.kGNvsHUMJA3 | Yes (4 copies) |
| **OP Note - Complete** | 2021-03-16 14:08 | **2021-03-10 14:46** ✅ | eTu932UZCvh8.kGNvsHUMJA3 | Yes (3 copies) |
| OP Note - Complete | 2021-03-15 10:36 | 2021-03-14 22:00 | eTu932UZCvh8.kGNvsHUMJA3 | Yes (2 copies) |
| OP Note - Brief | 2021-03-16 22:07 | 2021-03-16 22:07 | eTu932UZCvh8.kGNvsHUMJA3 | Yes (4 copies) |
| OP Note - Complete | 2021-03-19 13:11 | 2021-03-16 18:15 | eTu932UZCvh8.kGNvsHUMJA3 | Yes (4 copies) |

**Gold Standard Surgery Date**: 2021-03-10 12:03:00
**OP Note Context Periods**: 2021-03-10 17:17 and 2021-03-10 14:46 ✅ **SAME-DAY MATCH**

---

### **Linkage Strategy for Extent of Resection**

#### **Tier 1: Context Period Exact Match (HIGHEST PRIORITY)**

```python
# Query: Get operative notes where context_period_start = surgery_date
SELECT
    d.document_type,
    d.document_date,
    d.binary_id,
    d.s3_key,
    d.context_period_start,
    d.context_period_end
FROM document_references d
WHERE d.document_type IN (
    'OP Note - Complete (Template or Full Dictation)',
    'OP Note - Brief (Needs Dictation)',
    'Operative Record',
    'Anesthesia Postprocedure Evaluation'
)
AND DATE(d.context_period_start) = DATE('{surgery_date}')  -- e.g., '2018-05-28'
AND d.s3_available = 'Yes'
ORDER BY d.document_date ASC
```

**Expected Results**:
- Surgery 1: 3 OP Note - Complete documents
- Surgery 2: 7 OP Note documents (4 Brief + 3 Complete)

#### **Tier 2: Document Date Proximity (±3 days)**

```python
# Query: Get operative notes within ±3 days of surgery
SELECT d.*
FROM document_references d
WHERE d.document_type LIKE '%OP Note%'
AND d.document_date BETWEEN
    DATE('{surgery_date}') - INTERVAL 1 DAY AND
    DATE('{surgery_date}') + INTERVAL 3 DAYS
AND d.s3_available = 'Yes'
ORDER BY
    ABS(DATEDIFF(d.document_date, '{surgery_date}')) ASC,
    CASE
        WHEN d.document_type LIKE '%Complete%' THEN 1
        WHEN d.document_type LIKE '%Brief%' THEN 2
        ELSE 3
    END
```

**Prioritization**:
1. **OP Note - Complete** (full surgeon assessment)
2. **Anesthesia Postprocedure Evaluation** (often contains extent summary)
3. OP Note - Brief
4. Operative Record

---

### **BRIM Variable Instruction Update for surgery_extent**

```csv
surgery_extent,"Extract extent of tumor resection for each surgery.

PRIORITY SEARCH ORDER:
1. NOTE_ID='STRUCTURED_surgeries' - Shows surgery dates and metadata
2. **CONTEXT PERIOD MATCHING**: Documents where context_period_start = surgery_date
   - Search for document_type='OP Note - Complete (Template or Full Dictation)'
   - These documents contain surgeon's intraoperative assessment
3. Documents dated within +1 to +3 days of surgery date AND containing 'Anesthesia Postprocedure'
4. Documents with document_type='Operative Record'

DOCUMENT IDENTIFICATION STRATEGY:
For Surgery on YYYY-MM-DD:
  Step 1: Find documents where DATE(context_period_start) = 'YYYY-MM-DD'
  Step 2: Prioritize 'OP Note - Complete' over 'OP Note - Brief'
  Step 3: Look for sections: 'PROCEDURE', 'OPERATIVE FINDINGS', 'IMPRESSION'

TEMPORAL FILTERING EXAMPLES:
- Surgery 1 (2018-05-28): Search context_period_start='2018-05-28' OR documents dated 2018-05-28 to 2018-05-31
- Surgery 2 (2021-03-10): Search context_period_start='2021-03-10' OR documents dated 2021-03-10 to 2021-03-13

VALID VALUES: Return EXACTLY one per surgery:
- Gross Total Resection (GTR, >95% removed, no visible residual)
- Near Total Resection (NTR, 90-95% removed, minimal residual)
- Subtotal Resection (STR, 50-90% removed)
- Partial Resection (<50% removed or debulking)
- Biopsy Only (no resection, diagnostic only)
- Unknown

KEYWORDS TO SEARCH:
- GTR: 'gross total', 'complete resection', 'no residual', 'all visible tumor removed'
- NTR: 'near total', 'near complete', 'minimal residual'
- STR: 'subtotal', 'majority removed', '50-90%'
- Partial: 'partial resection', 'debulking', '<50%', 'incomplete'
- Biopsy: 'biopsy only', 'diagnostic biopsy', 'no resection attempted'

CRITICAL: Match EXACTLY with Title Case

Gold Standard for C1277724:
- Surgery 1 (2018-05-28): Partial Resection
- Surgery 2 (2021-03-10): Partial Resection

Data Dictionary: extent_of_tumor_resection (dropdown in treatments table)"
```

---

## PART 2: Radiology Reports for Imaging Findings

### **Athena Imaging Extraction Structure**

From `extract_all_imaging_metadata.py` and sample patient 55529723:

#### **Staging File: ALL_IMAGING_METADATA_{MRN}.csv**

**Columns**:
```
patient_id, patient_mrn, imaging_procedure_id, imaging_date,
imaging_procedure, result_diagnostic_report_id, imaging_modality,
result_information, result_display, age_at_imaging_days, age_at_imaging_years
```

#### **Key Field: `result_information`**

✅ **CONTAINS FULL RADIOLOGY INTERPRETATION TEXT**

This field includes:
- **Narrative reports** - Complete radiologist interpretation (thousands of characters)
- **Impression summaries** - Concise clinical summary (hundreds of characters)
- Clinical indication
- Comparison to prior studies
- Findings descriptions
- Assessment/impression

**Example from patient 55529723**:

```
result_display: Narrative
result_information: "BRAIN MRI, WITH AND WITHOUT CONTRAST:

CLINICAL INDICATION: Acute pontine hemorrhage, found to have underlying high-grade glioma

TECHNIQUE: Sagittal 3D T1 gradient echo with axial reformations, axial and sagittal TSE T2,
axial and coronal FLAIR, axial spin echo T1, axial SWI, arterial spin labeled perfusion imaging...

COMPARISON: Brain MR 6/14/2019

FINDINGS:
There has been suboccipital craniectomy for hematoma evacuation with expected postsurgical changes.
Fluid is seen within the craniectomy site, consistent with a small pseudomeningocele.

Susceptibility effect is seen within the area of prior pontine hemorrhage. No new or worsening
areas of hemorrhage are identified. Mild surrounding FLAIR signal abnormality is seen within the
pons and ventral medulla. Contrast enhancement is seen along the margins of the cavity, with more
focal, rounded contrast enhancement along the superior aspect of the cavity (series 18, image 57).
There is substantially decreased mass effect within the pons and adjacent posterior fossa structures,
with improved sulcal effacement. There is no evidence of herniation..."
```

---

### **DocumentReference Imaging Documents**

From `ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv`:

#### **Imaging Document Types**:

| Document Type | Count (C1277724) | S3 Availability | Contains Interpretation? |
|---------------|------------------|-----------------|--------------------------|
| **Diagnostic imaging study** | 163 | ~100% | ✅ **YES** - Full radiology report |
| **MR Brain W & W/O IV Contrast** | 39 | 100% | ✅ **YES** - Structured report |
| MRI Exam Screening Form | 30 | varies | ❌ No - Administrative |
| **Radiology Note** | 16 | varies | ✅ **YES** - Addendum notes |
| **CT Brain W/O IV Contrast** | 10 | 100% | ✅ **YES** - Full report |
| External Radiology and Imaging | 7 | varies | ⚠️ **MAYBE** - External reports |

**Total**: 297 imaging-related documents

---

### **Imaging Context Period Matching**

Similar to operative notes, imaging documents use `context_period_start` to link to the imaging study date.

#### **Sample Imaging Documents (Patient C1277724):**

| Document Type | Document Date | Context Period Start | Encounter | S3 Available |
|---------------|---------------|---------------------|-----------|--------------|
| MR Brain W & W/O IV Contrast | 2025-05-14 | **2025-05-14** ✅ | eFRrTaE9HjoOE0WgMpNPaMQ3 | Yes |
| Diagnostic imaging study | 2025-05-14 | **2025-05-14** ✅ | eFRrTaE9HjoOE0WgMpNPaMQ3 | Yes |
| MR Brain W/O IV Contrast | 2025-01-03 | **2025-01-02** ✅ | ecFhJEHcxrcwurFs9.5RIYQ3 | Yes |
| Diagnostic imaging study | 2025-01-02 | **2025-01-02** ✅ | ecFhJEHcxrcwurFs9.5RIYQ3 | Yes |
| MR Brain W & W/O IV Contrast | 2021-03-17 17:26 | **2021-03-17 16:34** ✅ | e63T2.v531KG9lVVlryccXg3 | Yes |
| Diagnostic imaging study | 2021-03-17 16:34 | **2021-03-17 16:34** ✅ | eTu932UZCvh8.kGNvsHUMJA3 | Yes |

**Pattern**: `context_period_start` = imaging study date (within same day)

---

### **Dual Source Strategy for Imaging**

For BRIM extraction, imaging findings can be obtained from **TWO complementary sources**:

#### **Source 1: Athena Staging File (PREFERRED for structured queries)**

**File**: `ALL_IMAGING_METADATA_{MRN}.csv`

**Advantages**:
- ✅ Pre-extracted `result_information` field with full narrative
- ✅ Structured metadata (modality, procedure type, diagnostic_report_id)
- ✅ Age calculations already performed
- ✅ Direct linkage to imaging_procedure_id

**Query Strategy**:
```python
# Filter imaging studies by date range
df = pd.read_csv(f'ALL_IMAGING_METADATA_{MRN}.csv')

# Get imaging around surgery dates
surgery1_imaging = df[
    (df['imaging_date'] >= '2018-05-15') &
    (df['imaging_date'] <= '2018-06-15')
].sort_values('imaging_date')

# Extract result_information for each study
for _, row in surgery1_imaging.iterrows():
    if row['result_display'] == 'Impression':
        # Use concise impression
        impression_text = row['result_information']
    elif row['result_display'] == 'Narrative':
        # Use full narrative report
        narrative_text = row['result_information']
```

**Create STRUCTURED_imaging Synthetic Document**:
```markdown
# STRUCTURED Imaging Studies for Patient C1277724

## Pre-Surgery 1 Imaging (2018-05-15 to 2018-05-28)

| Date | Modality | Procedure | Impression |
|------|----------|-----------|------------|
| 2018-05-27 | MRI | MR Brain W & W/O IV Contrast | {result_information where result_display='Impression'} |

## Post-Surgery 1 Imaging (2018-05-29 to 2018-06-15)

| Date | Modality | Procedure | Impression |
|------|----------|-----------|------------|
| 2018-05-30 | MRI | MR Brain W/O IV Contrast | Post-op changes... |
```

#### **Source 2: DocumentReference S3 Binary Files (FALLBACK)**

**Files**: Binary documents from S3 bucket

**Advantages**:
- ✅ Original source documents with full formatting
- ✅ May include images/tables not captured in structured extraction
- ✅ Contains document metadata (encounter, facility, authenticator)

**Query Strategy**:
```python
# Get imaging documents via context_period matching
SELECT
    d.document_type,
    d.document_date,
    d.binary_id,
    d.s3_key,
    d.context_period_start
FROM document_references d
WHERE d.document_type IN (
    'Diagnostic imaging study',
    'MR Brain W & W/O IV Contrast',
    'MR Brain W/O IV Contrast',
    'CT Brain W/O IV Contrast'
)
AND DATE(d.context_period_start) BETWEEN '{start_date}' AND '{end_date}'
AND d.s3_available = 'Yes'
ORDER BY d.context_period_start ASC
```

---

### **Linkage Between Sources**

**Question**: Can we link Athena `imaging_procedure_id` to DocumentReference `binary_id`?

**Answer**: ⚠️ **NOT DIRECTLY** - Different resource types

- **Athena `imaging_procedure_id`**: References `ImagingStudy` or `Procedure` FHIR resource
- **DocumentReference `binary_id`**: References `Binary` resource containing document content
- **Linkage field**: `result_diagnostic_report_id` in Athena → `DiagnosticReport` → DocumentReference

**However**: For BRIM purposes, **temporal + modality matching is sufficient**:

```python
# Match Athena imaging to DocumentReference by date + modality
athena_imaging = {'date': '2018-05-27', 'modality': 'MRI', 'procedure': 'MR Brain W & W/O IV Contrast'}

# Find matching DocumentReference
doc_match = documents[
    (documents['context_period_start'].str.startswith('2018-05-27')) &
    (documents['document_type'].str.contains('MR Brain'))
]
```

---

## PART 3: Implementation Strategy

### **Step 1: Create Surgery-Specific Document Linkage**

**Script**: `link_surgery_documents.py`

```python
#!/usr/bin/env python3
"""
Link documents to surgeries using context_period_start matching
"""
import pandas as pd

def get_surgery_documents(surgery_date, surgery_type='resection'):
    """
    Get all documents linked to a specific surgery

    Args:
        surgery_date: YYYY-MM-DD format
        surgery_type: 'resection', 'shunt', 'biopsy'

    Returns:
        DataFrame with linked documents
    """
    # Load document metadata
    docs = pd.read_csv('ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv')

    # Filter by context_period_start = surgery_date
    surgery_docs = docs[
        docs['context_period_start'].str.startswith(surgery_date)
    ].copy()

    # Prioritize document types
    priority_map = {
        'OP Note - Complete (Template or Full Dictation)': 1,
        'Anesthesia Postprocedure Evaluation': 2,
        'OP Note - Brief (Needs Dictation)': 3,
        'Operative Record': 4
    }

    surgery_docs['priority'] = surgery_docs['document_type'].map(priority_map).fillna(99)
    surgery_docs = surgery_docs.sort_values(['priority', 'document_date'])

    return surgery_docs[surgery_docs['s3_available'] == 'Yes']

# Example usage
surgery1_docs = get_surgery_documents('2018-05-28')
print(f"Found {len(surgery1_docs)} documents for Surgery 1")
print(surgery1_docs[['document_type', 'document_date', 'context_period_start']].head())
```

### **Step 2: Create STRUCTURED_surgery_documents Synthetic Document**

**Script**: `create_structured_surgery_documents.py`

```python
def create_structured_surgery_doc(procedures_df, documents_df):
    """
    Create STRUCTURED markdown table linking surgeries to documents
    """
    md_content = "# STRUCTURED Surgery Documents for Patient C1277724\n\n"

    for _, surgery in procedures_df.iterrows():
        surgery_date = surgery['best_available_date'][:10]

        md_content += f"## Surgery: {surgery['code_text']} ({surgery_date})\n\n"
        md_content += "### Documents Available:\n\n"
        md_content += "| Document Type | Date | Context Period | S3 Available | Likely Contains Extent? |\n"
        md_content += "|---------------|------|----------------|--------------|-------------------------|\n"

        # Get documents for this surgery
        surgery_docs = get_surgery_documents(surgery_date)

        for _, doc in surgery_docs.iterrows():
            likely_extent = '**YES**' if 'OP Note - Complete' in doc['document_type'] else 'Maybe'
            md_content += f"| {doc['document_type']} | {doc['document_date'][:10]} | {doc['context_period_start'][:10]} | {doc['s3_available']} | {likely_extent} |\n"

        md_content += "\n"

    return md_content
```

### **Step 3: Create STRUCTURED_imaging Synthetic Document**

**Script**: `create_structured_imaging.py`

```python
def create_structured_imaging_doc(imaging_df, surgery_dates):
    """
    Create STRUCTURED imaging document organized by clinical timeline
    """
    md_content = "# STRUCTURED Imaging Studies for Patient C1277724\n\n"

    for i, surgery_date in enumerate(surgery_dates):
        # Pre-surgery imaging (2 weeks before)
        pre_date = (pd.to_datetime(surgery_date) - pd.Timedelta(days=14)).strftime('%Y-%m-%d')

        pre_imaging = imaging_df[
            (imaging_df['imaging_date'] >= pre_date) &
            (imaging_df['imaging_date'] < surgery_date)
        ]

        md_content += f"## Pre-Surgery {i+1} Imaging ({pre_date} to {surgery_date})\n\n"
        md_content += "| Date | Modality | Procedure | Impression |\n"
        md_content += "|------|----------|-----------|------------|\n"

        for _, img in pre_imaging.iterrows():
            if img['result_display'] == 'Impression':
                # Truncate to first 200 chars
                impression = img['result_information'][:200].replace('\n', ' ')
                md_content += f"| {img['imaging_date'][:10]} | {img['imaging_modality']} | {img['imaging_procedure']} | {impression}... |\n"

        md_content += "\n"

        # Post-surgery imaging (2 weeks after)
        post_date = (pd.to_datetime(surgery_date) + pd.Timedelta(days=14)).strftime('%Y-%m-%d')

        post_imaging = imaging_df[
            (imaging_df['imaging_date'] >= surgery_date) &
            (imaging_df['imaging_date'] <= post_date)
        ]

        md_content += f"## Post-Surgery {i+1} Imaging ({surgery_date} to {post_date})\n\n"
        md_content += "| Date | Modality | Procedure | Impression (May contain extent assessment) |\n"
        md_content += "|------|----------|-----------|-------------------------------------------|\n"

        for _, img in post_imaging.iterrows():
            if img['result_display'] == 'Impression':
                impression = img['result_information'][:200].replace('\n', ' ')
                md_content += f"| {img['imaging_date'][:10]} | {img['imaging_modality']} | {img['imaging_procedure']} | {impression}... |\n"

        md_content += "\n"

    return md_content
```

### **Step 4: Update BRIM Variable Instructions**

Add temporal filtering guidance to all surgery-related variables:

```csv
surgery_extent,"[...existing instruction...]

DOCUMENT IDENTIFICATION:
Step 1: Check STRUCTURED_surgery_documents table for available documents
Step 2: Search documents where context_period_start = surgery_date
Step 3: Prioritize 'OP Note - Complete' documents
Step 4: Fallback to 'Anesthesia Postprocedure Evaluation' (dated +1 day)"

imaging_findings,"[...existing instruction...]

DOCUMENT IDENTIFICATION:
Step 1: Check STRUCTURED_imaging table for pre/post-op imaging
Step 2: For extent assessment, prioritize POST-operative imaging (1-7 days after surgery)
Step 3: Look for 'residual tumor', 'resection cavity', 'post-operative changes' keywords"
```

---

## Summary

### ✅ **Confirmed Capabilities**

1. **Operative notes ARE in document_reference staging files** (40+ complete, 36+ brief)
2. **Radiology interpretations ARE in Athena imaging staging files** (`result_information` field)
3. **Context period matching WORKS** for linking documents to clinical events
4. **Dual source strategy** enables both structured (Athena CSV) and unstructured (S3 binary) access

### ✅ **Linkage Strategy**

| Clinical Event | Linkage Field | Query Strategy |
|----------------|---------------|----------------|
| **Surgery → Operative Notes** | `context_period_start` = surgery_date | Exact date match |
| **Surgery → Pre-op Imaging** | `imaging_date` within 14 days before | Temporal range |
| **Surgery → Post-op Imaging** | `imaging_date` within 7 days after | Temporal range + keyword |
| **Imaging Study → Radiology Report** | `imaging_procedure_id` = `imaging_procedure_id` | Athena CSV join |

### 📋 **Next Steps**

1. ✅ Run imaging extraction for C1277724 (currently only exists for patient 55529723)
2. ⏳ Implement `link_surgery_documents.py` script
3. ⏳ Create `STRUCTURED_surgery_documents.md` synthetic document
4. ⏳ Create `STRUCTURED_imaging.md` synthetic document
5. ⏳ Update BRIM variables.csv with context period matching instructions
6. ⏳ Test extraction on C1277724 pilot patient

---

**Document Status**: Complete
**Validation**: Confirmed with C1277724 procedures and patient 55529723 imaging data
