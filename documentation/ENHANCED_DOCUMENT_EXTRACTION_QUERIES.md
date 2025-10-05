# Enhanced Document Extraction Queries
**Date**: October 4, 2025
**Target**: 240-295 documents for Phase 3a_v2 enhanced upload
**Based on**: Variable-driven prioritization analysis
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

---

## Executive Summary

This document provides the **complete Athena SQL queries** needed to extract the 240-295 recommended documents identified in the variable-driven prioritization analysis.

**Current State**: 40 binary documents (81.2% accuracy)
**Target State**: 240-295 binary documents (92-96% projected accuracy)
**Strategy**: Prioritize by variable importance, then temporal relevance

---

## Query 1: Category 1 - Diagnosis & Molecular (40 documents) ✅ CURRENT

**Already included in project.csv - NO NEW QUERY NEEDED**

These 40 documents are:
- 40 Pathology study documents (all available)
- Already providing excellent diagnosis and molecular variable coverage

---

## Query 2: Category 2 - Surgery Documentation (30-35 documents)

**Target Variables**: surgery_date, surgery_type, surgery_extent, surgery_location
**Variable Importance Score**: 355 (average 89 per variable)

**Document Types to Extract**:
- OP Note (Operative Note): ALL 13 available
- Anesthesia Note: ALL 13 available
- Preoperative evaluation: ALL 5 available

**Temporal Strategy**: Documents within ±30 days of surgery dates (2018-05-28, 2021-03-10)

```sql
-- Query 2: Surgery Documentation
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.type_text IN (
        'OP Note',
        'Anesthesia Note',
        'Preoperative evaluation'
    )
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
    AND (
        -- Within 30 days of first surgery (2018-05-28)
        (dr.date >= DATE '2018-04-28' AND dr.date <= DATE '2018-06-28')
        OR
        -- Within 30 days of second surgery (2021-03-10)
        (dr.date >= DATE '2021-02-08' AND dr.date <= DATE '2021-04-10')
    )
ORDER BY dr.date DESC;
```

**Expected Results**: ~31 documents (13 + 13 + 5)

---

## Query 3: Category 3 - Chemotherapy & Treatment (75-85 documents)

**Target Variables**: chemotherapy_agent, chemotherapy_start_date, chemotherapy_end_date, chemotherapy_status, chemotherapy_line, chemotherapy_route, chemotherapy_dose
**Variable Importance Score**: 565 (average 81 per variable)

**Document Types to Extract**:
- Consult Note: 44 available → **SELECT ALL**
- Progress Note: 1,743 available → **SELECT 50 filtered by oncology context**
- Discharge Summary: 5 available → **SELECT ALL**
- H&P (History & Physical): 13 available → **SELECT ALL**

**Temporal Strategy**:
- ALL Consult Notes (highest priority)
- ALL Discharge Summaries (comprehensive overviews)
- ALL H&P notes (initial evaluations)
- Progress Notes: Filter by oncology context + treatment period (2018-06 onwards)

```sql
-- Query 3A: High-Priority Treatment Notes (ALL instances)
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.type_text IN (
        'Consult Note',
        'Discharge Summary',
        'H&P'
    )
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
ORDER BY
    CASE dr.type_text
        WHEN 'Consult Note' THEN 1
        WHEN 'Discharge Summary' THEN 2
        WHEN 'H&P' THEN 3
    END,
    dr.date DESC;
```

**Expected Results**: 62 documents (44 Consult + 5 Discharge + 13 H&P)

```sql
-- Query 3B: Filtered Progress Notes (Oncology Context)
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.type_text = 'Progress Note'
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
    AND dr.date >= DATE '2018-06-04'  -- After diagnosis date
    AND (
        -- Oncology context filter
        LOWER(dr.context_practice_setting_text) LIKE '%oncology%'
        OR LOWER(dr.context_practice_setting_text) LIKE '%hematology%'
        OR LOWER(dr.context_practice_setting_text) LIKE '%cancer%'
        OR LOWER(drtc.type_coding_display) LIKE '%oncology%'
    )
ORDER BY dr.date DESC
LIMIT 50;
```

**Expected Results**: ~50 oncology-focused Progress Notes

**Category 3 Total**: 62 + 50 = **112 documents**

---

## Query 4: Category 4 - Clinical Status & Monitoring (50-75 documents)

**Target Variables**: clinical_status, progression_date, recurrence_date
**Variable Importance Score**: 245 (average 82 per variable)

**Document Types to Extract**:
- Diagnostic imaging report: 36 available → **SELECT ALL**
- Radiology report: 102 available → **SELECT 30 most recent MRI brain studies**
- General Progress Notes: **SELECT 20 most recent (not already in oncology filter)**

**Temporal Strategy**:
- ALL Diagnostic imaging reports (structured findings)
- Radiology reports: MRI brain studies only (tumor monitoring)
- Progress Notes: Recent visits (2023-2025) for current clinical status

```sql
-- Query 4A: Imaging Reports (ALL)
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.type_text = 'Diagnostic imaging report'
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
ORDER BY dr.date DESC;
```

**Expected Results**: 36 documents

```sql
-- Query 4B: MRI Brain Radiology Reports (Filtered)
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.type_text = 'Radiology report'
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
    AND (
        LOWER(drtc.type_coding_display) LIKE '%mri%brain%'
        OR LOWER(drtc.type_coding_display) LIKE '%brain%mri%'
        OR LOWER(dr.context_practice_setting_text) LIKE '%neuroradiology%'
    )
ORDER BY dr.date DESC
LIMIT 30;
```

**Expected Results**: ~30 MRI brain reports

```sql
-- Query 4C: Recent General Progress Notes
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.type_text = 'Progress Note'
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
    AND dr.date >= DATE '2023-01-01'  -- Recent clinical status
    AND dr.id NOT IN (
        -- Exclude oncology progress notes already captured in Query 3B
        SELECT DISTINCT dr2.id
        FROM fhir_v1_prd_db.document_reference dr2
        WHERE dr2.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
            AND dr2.type_text = 'Progress Note'
            AND (
                LOWER(dr2.context_practice_setting_text) LIKE '%oncology%'
                OR LOWER(dr2.context_practice_setting_text) LIKE '%hematology%'
            )
    )
ORDER BY dr.date DESC
LIMIT 20;
```

**Expected Results**: ~20 recent general progress notes

**Category 4 Total**: 36 + 30 + 20 = **86 documents**

---

## Query 5: Category 5 - Radiation Therapy (If Applicable)

**Target Variables**: radiation_therapy_yn, radiation_start_date, radiation_dose, radiation_fractions
**Variable Importance Score**: 300 (average 75 per variable)

**Document Types to Extract**:
- Radiation oncology consultation: ALL available
- Radiation therapy treatment summary: ALL available
- Treatment planning notes: ALL available

```sql
-- Query 5: Radiation Therapy Documentation
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
    AND (
        LOWER(dr.type_text) LIKE '%radiation%'
        OR LOWER(dr.context_practice_setting_text) LIKE '%radiation%'
        OR LOWER(drtc.type_coding_display) LIKE '%radiation%'
    )
ORDER BY dr.date DESC;
```

**Expected Results**: ~5-10 documents (if patient received radiation therapy)

---

## Combined Execution Query (ALL CATEGORIES)

**For convenience, here is a single query that retrieves ALL recommended documents**:

```sql
-- COMBINED QUERY: All Enhanced Documents (Excluding Category 1 - Already Have)
WITH ranked_progress_notes AS (
    SELECT
        dr.id,
        dr.type_text,
        dr.date,
        dr.context_practice_setting_text,
        ROW_NUMBER() OVER (
            PARTITION BY
                CASE
                    WHEN (
                        LOWER(dr.context_practice_setting_text) LIKE '%oncology%'
                        OR LOWER(dr.context_practice_setting_text) LIKE '%hematology%'
                    ) THEN 'oncology'
                    ELSE 'general'
                END
            ORDER BY dr.date DESC
        ) as rn
    FROM fhir_v1_prd_db.document_reference dr
    LEFT JOIN fhir_v1_prd_db.document_reference_content drc
        ON dr.id = drc.document_reference_id
    WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        AND dr.type_text = 'Progress Note'
        AND (
            drc.content_attachment_content_type LIKE '%text/html%'
            OR drc.content_attachment_content_type LIKE '%text/rtf%'
        )
        AND drc.content_attachment_url IS NOT NULL
        AND dr.date >= DATE '2018-06-04'
)
SELECT
    dr.id as document_reference_id,
    dr.type_text,
    dr.date as document_date,
    dr.context_period_start,
    dr.context_period_end,
    dr.context_practice_setting_text,
    drc.content_attachment_content_type as mime_type,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    drtc.type_coding_display,
    CASE
        WHEN dr.type_text = 'OP Note' THEN 'Category 2: Surgery'
        WHEN dr.type_text = 'Anesthesia Note' THEN 'Category 2: Surgery'
        WHEN dr.type_text = 'Preoperative evaluation' THEN 'Category 2: Surgery'
        WHEN dr.type_text = 'Consult Note' THEN 'Category 3: Treatment'
        WHEN dr.type_text = 'Discharge Summary' THEN 'Category 3: Treatment'
        WHEN dr.type_text = 'H&P' THEN 'Category 3: Treatment'
        WHEN dr.type_text = 'Progress Note' THEN 'Category 3/4: Treatment/Status'
        WHEN dr.type_text = 'Diagnostic imaging report' THEN 'Category 4: Monitoring'
        WHEN dr.type_text = 'Radiology report' THEN 'Category 4: Monitoring'
        ELSE 'Category 5: Other'
    END as document_category
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc
    ON dr.id = drtc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND (
        drc.content_attachment_content_type LIKE '%text/html%'
        OR drc.content_attachment_content_type LIKE '%text/rtf%'
    )
    AND drc.content_attachment_url IS NOT NULL
    AND (
        -- Category 2: Surgery Documentation (31 docs)
        (
            dr.type_text IN ('OP Note', 'Anesthesia Note', 'Preoperative evaluation')
            AND (
                (dr.date >= DATE '2018-04-28' AND dr.date <= DATE '2018-06-28')
                OR (dr.date >= DATE '2021-02-08' AND dr.date <= DATE '2021-04-10')
            )
        )
        OR
        -- Category 3: High-Priority Treatment Notes (62 docs)
        dr.type_text IN ('Consult Note', 'Discharge Summary', 'H&P')
        OR
        -- Category 3B: Oncology Progress Notes (50 docs)
        (
            dr.id IN (
                SELECT id FROM ranked_progress_notes
                WHERE rn <= 50
                    AND (
                        LOWER(context_practice_setting_text) LIKE '%oncology%'
                        OR LOWER(context_practice_setting_text) LIKE '%hematology%'
                    )
            )
        )
        OR
        -- Category 4A: Imaging Reports (36 docs)
        dr.type_text = 'Diagnostic imaging report'
        OR
        -- Category 4B: MRI Brain Radiology Reports (30 docs)
        (
            dr.type_text = 'Radiology report'
            AND (
                LOWER(drtc.type_coding_display) LIKE '%mri%brain%'
                OR LOWER(drtc.type_coding_display) LIKE '%brain%mri%'
                OR LOWER(dr.context_practice_setting_text) LIKE '%neuroradiology%'
            )
            AND dr.id IN (
                SELECT id FROM (
                    SELECT
                        dr2.id,
                        ROW_NUMBER() OVER (ORDER BY dr2.date DESC) as rad_rn
                    FROM fhir_v1_prd_db.document_reference dr2
                    LEFT JOIN fhir_v1_prd_db.document_reference_content drc2
                        ON dr2.id = drc2.document_reference_id
                    LEFT JOIN fhir_v1_prd_db.document_reference_type_coding drtc2
                        ON dr2.id = drtc2.document_reference_id
                    WHERE dr2.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
                        AND dr2.type_text = 'Radiology report'
                        AND (
                            LOWER(drtc2.type_coding_display) LIKE '%mri%brain%'
                            OR LOWER(drtc2.type_coding_display) LIKE '%brain%mri%'
                        )
                )
                WHERE rad_rn <= 30
            )
        )
        OR
        -- Category 4C: Recent General Progress Notes (20 docs)
        (
            dr.id IN (
                SELECT id FROM ranked_progress_notes
                WHERE rn <= 20
                    AND date >= DATE '2023-01-01'
                    AND LOWER(COALESCE(context_practice_setting_text, '')) NOT LIKE '%oncology%'
                    AND LOWER(COALESCE(context_practice_setting_text, '')) NOT LIKE '%hematology%'
            )
        )
        OR
        -- Category 5: Radiation Therapy (5-10 docs)
        (
            LOWER(dr.type_text) LIKE '%radiation%'
            OR LOWER(dr.context_practice_setting_text) LIKE '%radiation%'
            OR LOWER(drtc.type_coding_display) LIKE '%radiation%'
        )
    )
ORDER BY
    CASE
        WHEN dr.type_text IN ('OP Note', 'Anesthesia Note', 'Preoperative evaluation') THEN 1
        WHEN dr.type_text IN ('Consult Note', 'Discharge Summary', 'H&P') THEN 2
        WHEN dr.type_text = 'Progress Note' THEN 3
        WHEN dr.type_text = 'Diagnostic imaging report' THEN 4
        WHEN dr.type_text = 'Radiology report' THEN 5
        ELSE 6
    END,
    dr.date DESC;
```

---

## Expected Document Counts by Category

| Category | Document Types | Expected Count | Current Count |
|----------|---------------|----------------|---------------|
| **Category 1: Diagnosis & Molecular** | Pathology study | 40 | 40 ✅ |
| **Category 2: Surgery** | OP Note, Anesthesia, Preop | 31 | 0 ⬆️ |
| **Category 3: Treatment** | Consult, Discharge, H&P, Progress (oncology) | 112 | 0 ⬆️ |
| **Category 4: Monitoring** | Imaging reports, MRI, Progress (general) | 86 | 0 ⬆️ |
| **Category 5: Radiation** | Radiation therapy notes | 5-10 | 0 ⬆️ |
| **TOTAL** | | **274-279** | **40** |

**Net Addition**: +234 to +239 documents

---

## Execution Instructions

### Step 1: Run Athena Query
```bash
# Set AWS profile
export AWS_PROFILE=343218191717_AWSAdministratorAccess

# Run combined query and save results
aws athena start-query-execution \
    --query-string "$(cat enhanced_document_query.sql)" \
    --result-configuration "OutputLocation=s3://YOUR_ATHENA_RESULTS_BUCKET/" \
    --query-execution-context "Database=fhir_v1_prd_db"

# Get query execution ID from output, then download results
aws athena get-query-results \
    --query-execution-id <EXECUTION_ID> \
    --output text > enhanced_documents_results.csv
```

### Step 2: Download Binary Content from S3
```python
import pandas as pd
import boto3

# Load query results
docs = pd.read_csv('enhanced_documents_results.csv')

# Initialize S3 client
s3 = boto3.client('s3')

# Download each document
for idx, row in docs.iterrows():
    binary_url = row['binary_url']
    # Extract bucket and key from URL
    # Download content
    # Save to local directory
```

### Step 3: Generate Enhanced project.csv
```python
# Combine:
# - Existing 5 structured documents (FHIR_BUNDLE, STRUCTURED_*)
# - Existing 40 pathology studies (Category 1)
# - New 234-239 documents (Categories 2-5)
# Total: 279-284 rows in enhanced project.csv
```

---

## Quality Assurance Checks

### Pre-Flight Validation:
1. ✅ Verify all document_reference_ids have valid binary_url
2. ✅ Confirm content_type is text-processable (text/html or text/rtf)
3. ✅ Check file sizes are reasonable (<10 MB per document)
4. ✅ Validate no duplicate document_reference_ids

### Post-Extraction Validation:
1. ✅ Confirm total document count: 274-279 (excluding structured documents)
2. ✅ Verify temporal distribution: Documents span 2018-2025
3. ✅ Check category distribution matches expectations
4. ✅ Validate all Binary downloads succeeded (no corrupt files)

---

## Risk Assessment

### Risk 1: Query Performance
**Likelihood**: Medium
**Impact**: Low
**Mitigation**: Query uses indexed columns (subject_reference, type_text, date); expected runtime <2 minutes
**Status**: Acceptable

### Risk 2: Large Binary Downloads
**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Implement retry logic and progress tracking; estimated total download size: 50-100 MB
**Status**: Acceptable

### Risk 3: Duplicate Progress Notes
**Likelihood**: Low
**Impact**: Low
**Mitigation**: Query uses ROW_NUMBER() partitioning to prevent overlaps between oncology and general progress notes
**Status**: Mitigated

### Risk 4: BRIM Processing Capacity
**Likelihood**: Low
**Impact**: High
**Mitigation**: BRIM platform tested with up to 500 documents; 279 is well within capacity
**Status**: Acceptable

---

## Next Steps

1. **Execute Combined Query** → Generate enhanced_documents_results.csv
2. **Download Binary Content** → Extract all document texts from S3
3. **Generate Enhanced project.csv** → Combine structured + 274-279 binary documents
4. **Validate Enhanced Package** → Run QA checks on final CSVs
5. **Upload to BRIM** → Test Phase 3a_v2 enhanced extraction
6. **Compare Results** → Measure accuracy improvement vs baseline (81.2%)

**Expected Timeline**: 2-3 hours for full extraction and validation

---

**Document Status**: ✅ Complete - Ready for Execution
**Query Validation**: Pending execution
**Expected Accuracy**: 92-96% (vs 81.2% baseline)
