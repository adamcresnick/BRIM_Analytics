# BRIM Analytics Document Query Strategy
**Date**: October 4, 2025
**Source**: FHIR v1 DocumentReference schema analysis
**Total Documents**: 10.0M+ across all patients
**Text-Processable**: 8.7M (text/html + text/rtf)
**Objective**: Prioritized document selection for patient C1277724 BRIM extraction

---

## Key Findings from Schema Analysis

### **MIME Type Distribution** (All patients):
```
text/html:        4,534,551 (45.3%)  ← BRIM-processable
text/rtf:         4,208,218 (42.1%)  ← BRIM-processable
application/pdf:    393,723 (3.9%)   ← May need conversion
application/xml:    395,421 (4.0%)   ← May need conversion
text/xml:           310,989 (3.1%)   ← External C-CDA documents
image/tiff:         135,824 (1.4%)   ✗ Not BRIM-processable
image/jpeg:          32,821 (0.3%)   ✗ Not BRIM-processable
```

### **Category Distribution**:
```
Clinical Note:           8,752,832 (87.5%)  ← PRIMARY TARGET
Summary Document:          395,421 (4.0%)
External C-CDA Document:   310,989 (3.1%)
Document Information:      271,405 (2.7%)   ← Mostly admin forms
Correspondence:            210,677 (2.1%)
Imaging Result:             73,578 (0.7%)   ← Mostly application/pdf
```

---

## CRITICAL INSIGHT: Imaging Results Are PDFs

**Problem**: Radiology reports are stored as `application/pdf`, NOT `text/html` or `text/rtf`

**Imaging Results MIME Distribution**:
- `application/pdf`: ~73,500 (99.9% of imaging results)
- `text/html`: <100 (<0.1%)

**Implication**: If BRIM can only process text-based files, we **CANNOT include radiology narrative reports** in current form.

**Options**:
1. **Accept limitation**: Skip radiology narrative reports for now (use structured imaging metadata from `radiology_imaging_mri` table instead)
2. **PDF conversion**: Convert PDF radiology reports to text/HTML before BRIM upload (requires preprocessing)
3. **Request BRIM enhancement**: Ask if BRIM platform can accept PDFs

---

## Revised Top 20 Note Types (Text-Processable Only)

### **TIER 1: CRITICAL** (Must include - text/html or text/rtf)

| Rank | Note Type | Format | Count (All) | Category | Variables Supported |
|------|-----------|--------|-------------|----------|---------------------|
| 1 | **Pathology study** | text/html, text/rtf | 142,982 | Clinical Note | primary_diagnosis, diagnosis_date, who_grade, tumor_location, braf_status, idh_mutation, mgmt_methylation, 1p19q_codeletion, other_molecular_markers |
| 2 | **OP Note - Complete** | text/html, text/rtf | 46,448 | Clinical Note | surgery_date, surgery_type, surgery_extent, surgery_location |
| 3 | **Discharge Summary** | text/html, text/rtf | 78,750 | Clinical Note | primary_diagnosis, surgery_date, surgery_type, chemotherapy_agent, chemotherapy_start_date, radiation_therapy_yn, clinical_status |
| 4 | **Consult Note** | text/html, text/rtf | 174,152 | Clinical Note | chemotherapy_agent, chemotherapy_start_date, chemotherapy_end_date, chemotherapy_status, chemotherapy_line, chemotherapy_protocol, progression_date, recurrence_date, clinical_status |
| 5 | **H&P** | text/html, text/rtf | 192,990 | Clinical Note | primary_diagnosis, diagnosis_date, surgery_date, tumor_location, clinical_status |

### **TIER 2: HIGH VALUE** (Strong multi-variable support)

| Rank | Note Type | Format | Count (All) | Variables Supported |
|------|-----------|--------|-------------|---------------------|
| 6 | **Progress Notes** | text/html, text/rtf | 4,365,798 | clinical_status, progression_date, recurrence_date, chemotherapy_status, chemotherapy_response, tumor_size (from clinical exam), imaging_findings (from clinical interpretation) |
| 7 | **OP Note - Brief** | text/html, text/rtf | 38,736 | surgery_date, surgery_type, surgery_location |
| 8 | **Assessment & Plan Note** | text/html, text/rtf | 64,816 | clinical_status, progression_date, recurrence_date, chemotherapy_response, treatment planning |
| 9 | **Transfer Note** | text/html, text/rtf | 31,824 | clinical_status, primary_diagnosis, treatment summary |
| 10 | **Interval H&P Note** | text/html, text/rtf | 9,080 | clinical_status, disease progression, treatment updates |

### **TIER 3: SUPPORTING** (Additional context)

| Rank | Note Type | Format | Count (All) | Variables Supported |
|------|-----------|--------|-------------|---------------------|
| 11 | **Anesthesia Preprocedure Evaluation** | text/html, text/rtf | 367,632 | surgery_date, surgery_type, clinical_status |
| 12 | **Anesthesia Postprocedure Evaluation** | text/html, text/rtf | 158,312 | surgery_date, surgery_type, clinical_status |
| 13 | **Anesthesia Procedure Notes** | text/html, text/rtf | 24,344 | surgery_date, surgery_type |
| 14 | **Care Plan Note** | text/html, text/rtf | 275,952 | chemotherapy_protocol, radiation_therapy_yn, clinical_status |
| 15 | **Laboratory report** | text/html, text/rtf | 14,206 | Molecular markers (if molecular pathology reports included) |
| 16 | **Addendum Note** | text/html, text/rtf | 152,208 | Updates to previous clinical notes |
| 17 | **Procedures** | text/html, text/rtf | 33,474 | Procedure details (lumbar puncture, CSF analysis, biopsies) |
| 18 | **Diagnostic imaging study** | text/html, text/rtf | 156,174 | imaging_type, imaging_date, imaging_findings (if text-based reports) |
| 19 | **Radiology Note** | text/html, text/rtf | 11,492 | Radiology addendum or correlative notes |
| 20 | **MH Progress Note** | text/html, text/rtf | 21,892 | clinical_status, quality of life, neurological function |

---

## Note Types Currently in Phase 3a_v2 project.csv

### ✅ **Already Have** (6 types):
1. ✅ Pathology study (20 docs)
2. ✅ OP Note - Complete (4 docs)
3. ✅ OP Note - Brief (3 docs)
4. ✅ Anesthesia Preprocedure Evaluation (4 docs)
5. ✅ Anesthesia Postprocedure Evaluation (4 docs)
6. ✅ Anesthesia Procedure Notes (3 docs)

### ❌ **Missing from Top 20** (14 types):
7. ❌ **Discharge Summary** ← CRITICAL
8. ❌ **Consult Note** ← CRITICAL
9. ❌ **H&P** ← HIGH VALUE
10. ❌ **Progress Notes** ← HIGH VALUE
11. ❌ **Assessment & Plan Note**
12. ❌ **Transfer Note**
13. ❌ **Interval H&P Note**
14. ❌ **Care Plan Note**
15. ❌ **Laboratory report**
16. ❌ **Addendum Note**
17. ❌ **Procedures**
18. ❌ **Diagnostic imaging study**
19. ❌ **Radiology Note**
20. ❌ **MH Progress Note**

---

## Recommended Query Strategy

### **Phase 1: Core Clinical Documents** (Top 5)

```sql
-- Query 1: Pathology, Operative, Discharge, Consult, H&P
SELECT
    dr.id as document_id,
    dr.type_text,
    dr.document_date,
    dr.status,
    dr.context_practice_setting_text,
    drc.content_attachment_url,
    drc.content_attachment_content_type,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.type_text IN (
    'Pathology study',
    'OP Note - Complete (Template or Full Dictation)',
    'OP Note - Brief (Needs Dictation)',
    'Discharge Summary',
    'Consult Note',
    'H&P'
  )
  AND drc.content_attachment_content_type IN ('text/html', 'text/rtf')
ORDER BY
    CASE dr.type_text
        WHEN 'Pathology study' THEN 1
        WHEN 'OP Note - Complete (Template or Full Dictation)' THEN 2
        WHEN 'Discharge Summary' THEN 3
        WHEN 'Consult Note' THEN 4
        WHEN 'H&P' THEN 5
        ELSE 99
    END,
    dr.document_date DESC;
```

**Expected for C1277724**:
- Pathology study: 10-20 reports (diagnosis, molecular markers)
- OP Note - Complete: 2-4 notes (2018, 2021 surgeries)
- Discharge Summary: 2-4 summaries (surgical admissions)
- Consult Note: 20-40 notes (oncology, neurosurgery, radiation oncology)
- H&P: 2-4 pre-op H&Ps

**Estimated total**: ~50-80 documents

---

### **Phase 2: Longitudinal Clinical Assessment** (Progress Notes with Filtering)

**Challenge**: Progress Notes are extremely high volume (4.3M across all patients)

**Strategy**: Apply **temporal and contextual filters**

```sql
-- Query 2: Filtered Progress Notes (oncology/neurosurgery, key time periods)
SELECT
    dr.id as document_id,
    dr.type_text,
    dr.document_date,
    dr.context_practice_setting_text,
    drc.content_attachment_url,
    drc.content_attachment_content_type
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.type_text = 'Progress Notes'
  AND drc.content_attachment_content_type IN ('text/html', 'text/rtf')
  AND (
    -- Filter by clinical context
    dr.context_practice_setting_text IN (
      'Neurosurgery',
      'Oncology',
      'Hematology Oncology',
      'Radiation Oncology',
      'Neuro-Oncology'
    )
    OR
    -- Filter by key time periods (±30 days from major events)
    (
      dr.document_date BETWEEN '2018-05-05' AND '2018-07-05'  -- Around 2018 surgery
      OR dr.document_date BETWEEN '2018-06-01' AND '2018-07-04'  -- Around diagnosis
      OR dr.document_date BETWEEN '2021-02-10' AND '2021-04-10'  -- Around 2021 surgery
      OR dr.document_date BETWEEN '2018-09-01' AND '2018-11-01'  -- Chemo start
      OR dr.document_date BETWEEN '2019-04-15' AND '2019-06-15'  -- Chemo switch
      OR dr.document_date BETWEEN '2021-04-01' AND '2021-06-01'  -- Selumetinib start
    )
  )
ORDER BY dr.document_date DESC;
```

**Expected for C1277724**: ~50-100 filtered progress notes

---

### **Phase 3: Supporting Documentation** (Remaining Top 20)

```sql
-- Query 3: Assessment & Plan, Transfer, Care Plan, Lab reports
SELECT
    dr.id as document_id,
    dr.type_text,
    dr.document_date,
    dr.context_practice_setting_text,
    drc.content_attachment_url,
    drc.content_attachment_content_type
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.type_text IN (
    'Assessment & Plan Note',
    'Transfer Note',
    'Interval H&P Note',
    'Care Plan Note',
    'Laboratory report',
    'Addendum Note',
    'Procedures',
    'Diagnostic imaging study',
    'Radiology Note',
    'Anesthesia Preprocedure Evaluation',
    'Anesthesia Postprocedure Evaluation',
    'Anesthesia Procedure Notes'
  )
  AND drc.content_attachment_content_type IN ('text/html', 'text/rtf')
ORDER BY dr.document_date DESC;
```

**Expected for C1277724**: ~30-50 additional documents

---

## MIME Type Handling Strategy

### **BRIM-Processable Formats** (No conversion needed):
✅ `text/html` - Use directly
✅ `text/rtf` - Use directly

### **Requires Conversion/Special Handling**:
⚠️ `application/pdf` - Radiology reports, external documents
- **Option 1**: Skip for now (use structured imaging metadata instead)
- **Option 2**: OCR/PDF-to-text conversion before BRIM upload
- **Option 3**: Include as-is if BRIM supports PDF parsing

⚠️ `application/xml` - Summary documents (395K total)
⚠️ `text/xml` - External C-CDA documents (311K total)
- May contain comprehensive external medical records
- Could be parsed and converted to text format

❌ `image/tiff`, `image/jpeg`, `image/png` - Not processable by BRIM

---

## Document Prioritization Scoring

### **Scoring Algorithm** (for ranking within each note type):

```python
def calculate_document_priority(doc):
    score = 0

    # 1. Type priority (0-100)
    type_scores = {
        'Pathology study': 100,
        'OP Note - Complete': 95,
        'Discharge Summary': 90,
        'Consult Note': 85,
        'H&P': 85,
        'Progress Notes': 75,
        # ... etc
    }
    score += type_scores.get(doc['type_text'], 50)

    # 2. Temporal proximity to key events (0-50)
    key_dates = ['2018-05-28', '2018-06-04', '2021-03-10']  # surgeries, diagnosis
    min_distance = min([abs(doc['date'] - key_date) for key_date in key_dates])
    if min_distance <= 7: score += 50
    elif min_distance <= 30: score += 40
    elif min_distance <= 90: score += 30
    elif min_distance <= 365: score += 20
    else: score += 10

    # 3. Clinical context (0-25)
    if doc['context'] in ['Neurosurgery', 'Oncology', 'Neuro-Oncology']:
        score += 25
    elif doc['context'] in ['Radiation Oncology', 'Hematology Oncology']:
        score += 20
    elif doc['context']:
        score += 10

    # 4. Document status (0-10)
    if doc['status'] in ['current', 'final']:
        score += 10

    # 5. Content format preference (0-15)
    if doc['mime_type'] == 'text/html':
        score += 15  # HTML often better formatted
    elif doc['mime_type'] == 'text/rtf':
        score += 10

    return score
```

**Maximum score**: 200 points

---

## Expected Document Counts for Patient C1277724

### **Conservative Estimate** (Phase 1-3 combined):

| Note Type Category | Expected Count |
|-------------------|----------------|
| Pathology study | 15-20 |
| Operative notes | 4-6 |
| Discharge summaries | 2-4 |
| Consult notes | 20-40 |
| H&P | 2-4 |
| Progress notes (filtered) | 50-100 |
| Assessment & Plan | 5-10 |
| Anesthesia notes | 6-12 |
| Care Plan notes | 5-10 |
| Laboratory reports | 5-10 |
| Other supporting | 10-20 |
| **TOTAL** | **124-236** |

### **Recommended Target for BRIM Upload**:
- **150-200 documents** (balances comprehensiveness with processing efficiency)
- Use scoring algorithm to select top-ranked documents within each category

---

## Category-Specific Filtering

### **Consult Note** - Filter by specialty:
```sql
WHERE dr.type_text = 'Consult Note'
  AND dr.context_practice_setting_text IN (
    'Oncology',
    'Hematology Oncology',
    'Neuro-Oncology',
    'Radiation Oncology',
    'Neurosurgery',
    'Ophthalmology'  -- for optic pathway gliomas
  )
```

### **Progress Notes** - Exclude routine/low-value:
```sql
WHERE dr.type_text = 'Progress Notes'
  AND dr.context_practice_setting_text NOT IN (
    'Nutrition',
    'Social Work',
    'Child Life',
    'Physical Therapy',
    'Speech Language Pathology'
  )
  AND dr.type_coding_display NOT LIKE '%Vital%'  -- Exclude vitals-only notes
```

### **Diagnostic imaging study** - Text-based only:
```sql
WHERE dr.type_text = 'Diagnostic imaging study'
  AND drc.content_attachment_content_type IN ('text/html', 'text/rtf')
  -- This filters out DICOM images and keeps narrative reports
```

---

## Implementation Checklist

### ✅ **Phase 1: Core Clinical Documents** (TOP PRIORITY)
- [ ] Query Pathology study (text/html, text/rtf)
- [ ] Query OP Note - Complete
- [ ] Query OP Note - Brief
- [ ] Query Discharge Summary
- [ ] Query Consult Note (oncology, neurosurgery, radiation oncology)
- [ ] Query H&P
- [ ] **Validate**: ~50-80 documents

### ✅ **Phase 2: Longitudinal Assessment** (HIGH PRIORITY)
- [ ] Query Progress Notes with temporal filters (±30 days from key events)
- [ ] Query Progress Notes with context filters (oncology, neurosurgery)
- [ ] **Validate**: ~50-100 documents

### ✅ **Phase 3: Supporting Documentation** (MEDIUM PRIORITY)
- [ ] Query Assessment & Plan Note
- [ ] Query Transfer Note
- [ ] Query Care Plan Note
- [ ] Query Laboratory report
- [ ] Query Procedures
- [ ] Query Anesthesia notes (if not already included)
- [ ] **Validate**: ~30-50 documents

### ⚠️ **Phase 4: PDF Content** (OPTIONAL - if BRIM supports PDF)
- [ ] Query Imaging Results (application/pdf) - Radiology reports
- [ ] Assess PDF conversion options
- [ ] **Validate**: ~51 MRI reports available

### 📊 **Phase 5: Quality Control**
- [ ] Apply scoring algorithm to rank all documents
- [ ] Select top 150-200 documents
- [ ] Download Binary content from S3
- [ ] Validate text extraction (check for formatting issues)
- [ ] Generate updated project.csv

---

## Radiology Report Handling Decision

### **Current Limitation**:
Imaging results are stored as `application/pdf`, not text-based formats

### **Three Options**:

#### **Option 1: Skip Radiology Narratives** (Recommended for Phase 3a_v2)
**Pros**:
- No preprocessing required
- Use structured imaging metadata from `radiology_imaging_mri` table
- Structured data already includes: imaging_type, imaging_date, imaging_procedure

**Cons**:
- Missing narrative findings: tumor_size measurements, contrast_enhancement descriptions, imaging_findings text

**Impact on variables**:
- ❌ tumor_size (narrative measurements)
- ❌ contrast_enhancement (narrative descriptions)
- ❌ imaging_findings (radiologist interpretations)
- ✅ imaging_type (from structured data)
- ✅ imaging_date (from structured data)

#### **Option 2: PDF-to-Text Conversion** (Future enhancement)
**Approach**:
1. Download PDF radiology reports from S3
2. Use PDF extraction library (PyPDF2, pdfplumber, or AWS Textract)
3. Convert to HTML/text format
4. Add to project.csv

**Pros**:
- Enables full imaging variable coverage
- Maintains original content fidelity

**Cons**:
- Requires preprocessing pipeline
- PDF quality variable (scanned vs native)
- Formatting may be lost

#### **Option 3: Request BRIM PDF Support** (Platform enhancement)
**Ask BRIM**: Can the platform accept `application/pdf` documents?

**If yes**:
- Include radiology PDFs directly in project.csv
- Significantly improves imaging variable coverage

---

## Updated Variable Coverage Estimate

### **With Text-Based Documents Only** (Option 1):

| Variable Category | Coverage | Source |
|------------------|----------|--------|
| **Diagnosis** (7 vars) | 95% | Pathology study, Discharge Summary, Consult Note |
| **Molecular** (4 vars) | 90% | Pathology study, Laboratory report |
| **Surgery** (4 vars) | 95% | OP Notes, Discharge Summary, H&P |
| **Chemotherapy** (7 vars) | 85% | Consult Note, Progress Notes, Care Plan |
| **Radiation** (3 vars) | 90% | Consult Note, Discharge Summary |
| **Imaging** (5 vars) | **50%** | Structured data only (no narrative reports) |
| **Clinical Status** (3 vars) | 85% | Progress Notes, Consult Note, Assessment & Plan |
| **Demographics** (5 vars) | 100% | FHIR Bundle, structured data |

**Overall projected accuracy**: **85-88%** (vs 81.2% baseline)

### **With PDF Radiology Reports** (Option 2 or 3):

| Variable Category | Coverage |
|------------------|----------|
| **Imaging** (5 vars) | **90%** ← IMPROVED |

**Overall projected accuracy**: **88-92%** (vs 81.2% baseline)

---

## Next Steps

1. **Execute Phase 1 query** (Core clinical documents)
2. **Validate document counts** for patient C1277724
3. **Decide on radiology report handling** (Option 1 vs 2 vs 3)
4. **Execute Phase 2-3 queries** (Longitudinal + Supporting)
5. **Apply scoring algorithm** to prioritize top 150-200 documents
6. **Download Binary content** from S3
7. **Generate updated project.csv** with enhanced document set
8. **Upload to BRIM** and validate extraction accuracy

---

**Document Status**: ✅ Complete
**Analysis Basis**: FHIR v1 DocumentReference schema (3,103 type combinations, 10M+ documents)
**Recommended Approach**: Text-based documents only (Phase 1-3), defer PDF radiology reports
**Expected Accuracy Improvement**: 81.2% → 85-88% (without radiology), 88-92% (with radiology PDFs)
