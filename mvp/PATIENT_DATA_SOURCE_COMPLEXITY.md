# Multi-Source Data Integration Complexity

## Patient Data Source Analysis
**Example Patient**: `Patient/eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3` (Similar patient: `eNdsM0zzuZ268JeTtY0hitxC1w1.4JrnpT8AldpjJR9E3`)

---

## Executive Summary

Extracting comprehensive pediatric cancer treatment data requires integrating **9+ distinct FHIR data sources** spanning **10+ years** of clinical care, combining **structured EHR data** with **unstructured clinical documents**, and correlating events across **multiple treatment modalities**.

This analysis demonstrates the **data complexity** and **technical challenges** inherent in creating research-ready oncology datasets from real-world clinical data.

---

## Data Source Inventory

| Data Source | Athena View | Record Count | Document Types | Date Range | Integration Complexity |
|------------|-------------|--------------|----------------|------------|----------------------|
| **Imaging Studies** | `v_imaging` | 189 studies | MRI, CT, PT scans | 2013-2023 (10 years) | **HIGH** - Requires modality classification, body site mapping |
| **Imaging Reports (Text)** | `v_binary_files` (text) | 30 reports | Radiology text reports | 2013-2023 | **VERY HIGH** - NLP extraction, temporal classification |
| **Imaging Reports (PDF)** | `v_binary_files` (PDF) | 50 PDFs | Radiology PDF reports | 2013-2023 | **VERY HIGH** - PDF parsing, OCR, LLM extraction |
| **Tumor Procedures** | `v_procedures_tumor` | 14 procedures | 6 surgeries, 8 CSF/other | 2013-2024 | **MEDIUM** - Procedure classification, date matching |
| **Operative Notes** | `v_binary_files` (operative) | 21 documents | OP notes, surgical records | 2013-2024 | **VERY HIGH** - Surgery matching (±7 days), PDF extraction |
| **Progress Notes** | `v_binary_files` (progress) | 1,111 notes<br>(16 prioritized) | Clinical notes, oncology notes | 2013-2024 | **EXTREME** - Event-based filtering (1.4% selection rate) |
| **Radiation Therapy** | `v_radiation_summary` | 7 courses | Proton, photon therapy | 2013-2023 | **HIGH** - Course aggregation, dose summation |
| **Chemotherapy** | `v_chemo_medications` | 3 courses | Systemic therapy regimens | 2013-2023 | **MEDIUM** - Temporal overlap, concomitant med analysis |
| **Diagnoses** | `v_diagnoses` | ~50 conditions | ICD-10 coded diagnoses | 2013-2024 | **MEDIUM** - Tumor diagnosis identification |
| **Encounters** | `v_encounters` | ~300 visits | Inpatient, ambulatory, emergency | 2013-2024 | **LOW** - Visit classification |

**TOTAL DATA SOURCES**: 10 distinct FHIR views
**TOTAL RECORDS TO INTEGRATE**: ~1,700+ individual records
**TEMPORAL SPAN**: 10+ years of longitudinal care
**SUCCESSFUL EXTRACTIONS**: 94 structured data points (from patient `eNdsM0zzuZ268JeTtY0hitxC1w1.4JrnpT8AldpjJR9E3`)

---

## Integration Challenges by Data Source

### 1. Imaging Studies (v_imaging)

**Challenge**: Temporal classification relative to surgery dates

- **Raw Data**: 189 imaging studies across 10 years
- **Required Integration**:
  - Join with `v_procedures_tumor` on `patient_fhir_id`
  - Calculate `DATE_DIFF` between imaging and each surgery
  - Classify as: `pre_operative`, `post_operative`, `surveillance`
- **Complexity Drivers**:
  - Multiple surgeries create ambiguous temporal relationships
  - Imaging may relate to different tumor sites
  - Requires ±30 day window analysis for each surgery

**SQL Pattern**:
```sql
SELECT i.*, p.procedure_date,
       DATE_DIFF('day', i.imaging_date, p.procedure_date) as days_to_surgery
FROM v_imaging i
CROSS JOIN v_procedures_tumor p
WHERE i.patient_fhir_id = p.patient_fhir_id
  AND p.is_tumor_surgery = true
  AND ABS(DATE_DIFF('day', i.imaging_date, p.procedure_date)) <= 30
```

---

### 2. Imaging Reports - Text (v_binary_files)

**Challenge**: LLM-based structured extraction from unstructured radiology reports

- **Raw Data**: 30 text-based radiology reports
- **Required Processing**:
  1. **Classification** (LLM Call #1): Determine imaging timing category
  2. **Tumor Status Extraction** (LLM Call #2): NED vs progression vs stable
  3. **Location Extraction** (LLM Call #3): Anatomical site normalization
- **Complexity Drivers**:
  - **3 sequential LLM calls** per report (~2-3 min each)
  - Requires surgical history context (from `v_procedures_tumor`)
  - Requires radiation/chemo history context (from `v_radiation_summary`, `v_chemo_medications`)
  - Temporal reasoning: "compared to prior from [date]"

**Example Extraction**:
```json
{
  "classification": "post_operative",
  "tumor_status": "NED",
  "tumor_location": "T2-3 to T4-5 thoracic spinal cord",
  "confidence": 0.95,
  "reasoning": "Report states 'no evidence of residual or recurrent tumor'..."
}
```

---

### 3. Imaging Reports - PDF (v_binary_files)

**Challenge**: PDF parsing + S3 streaming + LLM extraction

- **Raw Data**: 50 PDF radiology reports stored in S3
- **Required Processing**:
  1. **S3 Streaming**: Download PDF from `s3://radiant-prd-.../Binary/...`
  2. **PDF Text Extraction**: Parse PDF to extract text content
  3. **Document Caching**: Store extracted text in DuckDB cache
  4. **LLM Extraction**: Same 3-step process as text reports
- **Complexity Drivers**:
  - **AWS SSO Token Management**: Tokens expire after 8-12 hours
  - **S3 Path Transformation**: `Binary/fUccSfUIUZ.8Pawcj` → `Binary/fUccSfUIUZ_8Pawcj`
  - **Error Handling**: 404 errors when S3 objects missing (data integrity issue)
  - **Performance**: 2-3 minutes per PDF (text extraction + 3 LLM calls)

**Infrastructure Dependencies**:
- AWS SDK (boto3)
- S3 bucket permissions
- SSO credential refresh logic
- PDF parsing libraries

---

### 4. Tumor Procedures (v_procedures_tumor)

**Challenge**: Procedure classification and temporal anchoring

- **Raw Data**: 14 procedures (6 tumor surgeries, 8 CSF/other)
- **Required Integration**:
  - Identify tumor resections vs biopsies vs CSF procedures
  - Create temporal anchors for imaging classification
  - Match to operative notes (see #5)
- **Complexity Drivers**:
  - Multiple procedure types require different handling
  - Date precision varies (some only have dates, not datetimes)
  - Procedures span 10+ years with varying completeness

**Procedure Categories**:
- `is_tumor_resection`: True tumor surgeries
- `is_csf_management`: Shunt placements, revisions
- `is_biopsy`: Diagnostic procedures
- `is_central_line`: Supportive procedures

---

### 5. Operative Notes (v_binary_files)

**Challenge**: Surgery-to-document matching across temporal windows

- **Raw Data**: 21 operative note documents in metadata
- **Actual S3 Availability**: Variable (some missing due to data integrity issues)
- **Required Matching Algorithm**:
  1. Get surgeries from `v_procedures_tumor` where `is_tumor_surgery = true`
  2. For each surgery date, find operative notes where:
     - **Exact match**: `DATE(dr_context_period_start) = DATE(procedure_date)`
     - **Near match**: `ABS(DATE_DIFF('day', dr_context_period_start, procedure_date)) <= 7`
  3. Prioritize exact matches over near matches
  4. Handle multiple notes per surgery (common)
- **Complexity Drivers**:
  - **Temporal ambiguity**: Notes may be dated day of surgery OR day of dictation
  - **Data quality**: 18/21 notes matched to surgeries, but **0/6 extracted** due to S3 404 errors
  - **Multiple note types**: "OP Note", "Operative Record", "Anesthesia Postprocedure Evaluation"

**Matching SQL**:
```sql
SELECT p.procedure_date, b.dr_context_period_start, b.dr_type_text,
       ABS(DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start))) as days_diff
FROM v_procedures_tumor p
LEFT JOIN v_binary_files b
  ON p.patient_fhir_id = b.patient_fhir_id
  AND ABS(DATE_DIFF('day', DATE(p.procedure_date), DATE(b.dr_context_period_start))) <= 7
  AND (b.dr_type_text LIKE 'OP Note%' OR b.dr_type_text = 'Operative Record')
WHERE p.is_tumor_surgery = true
```

---

### 6. Progress Notes (v_binary_files)

**Challenge**: Event-driven prioritization from 1,111 total notes

- **Raw Data**: 1,111 total progress notes spanning 10 years
- **Prioritization Strategy**:
  1. **Oncology Filter**: 497 oncology-specific notes (44.7%)
  2. **Event-Based Selection**: 16 key notes (1.4% of total)
     - Notes within ±30 days of surgeries
     - Notes within ±14 days of radiation start/end
     - Notes within ±14 days of chemotherapy start/end
  3. **Temporal Deduplication**: Avoid redundant notes from same week
- **Complexity Drivers**:
  - **Massive volume**: 1,111 notes would require 55+ hours to process
  - **Multi-source temporal joins**:
    - Join with `v_procedures_tumor` (surgery dates)
    - Join with `v_radiation_summary` (course dates)
    - Join with `v_chemo_medications` (treatment dates)
  - **Priority scoring**: Rank notes by clinical event proximity

**Selection Logic**:
```python
# Near surgery (±30 days)
surgery_window_notes = filter_notes_near_dates(surgeries, window_days=30)

# Near radiation start/end (±14 days)
radiation_notes = filter_notes_near_dates(radiation_courses, window_days=14)

# Near chemo start/end (±14 days)
chemo_notes = filter_notes_near_dates(chemo_courses, window_days=14)

# Combine and deduplicate
prioritized_notes = deduplicate_by_date(
    surgery_window_notes + radiation_notes + chemo_notes,
    min_days_apart=7
)
```

**Result**: 1,111 → 497 → **16 notes** (99% reduction)

---

### 7. Radiation Therapy (v_radiation_summary)

**Challenge**: Multi-course aggregation with dose summation

- **Raw Data**: 7 radiation courses over 10 years
- **Required Aggregation**:
  - **Per Course**: Sum daily fractions to get total dose (cGy)
  - **Across Courses**: Track modality changes (proton vs photon)
  - **Temporal Relationships**: Match courses to imaging surveillance periods
- **Complexity Drivers**:
  - **Hierarchical data**: Care plans → Courses → Treatments (daily fractions)
  - **Dose calculations**: Convert fractional doses to cumulative doses
  - **Modality tracking**: Proton vs photon vs mixed courses
  - **Target site normalization**: Map anatomical descriptions to standard terms

**Data Hierarchy**:
```
v_radiation_care_plan_hierarchy (care plan)
  └─ v_radiation_summary (course level)
       ├─ course_start_date, course_end_date
       ├─ total_dose_cgy, fraction_count
       ├─ modality (proton/photon)
       └─ target_site
            └─ v_radiation_treatments (daily fractions)
                 ├─ treatment_date
                 ├─ dose_cgy
                 └─ fraction_number
```

---

### 8. Chemotherapy (v_chemo_medications)

**Challenge**: Temporal overlap analysis with concomitant medications

- **Raw Data**: 3 chemotherapy courses
- **Required Integration**:
  - **Temporal reasoning**: Identify chemo courses overlapping with imaging
  - **Concomitant medications**: Join with `v_concomitant_medications` to find supportive meds
  - **Intent classification**: Order vs plan vs administered
- **Complexity Drivers**:
  - **Date source variability**: `start_datetime` vs `authored_datetime` vs `stop_datetime`
  - **Overlap calculations**: Determine if chemo was active during imaging window
  - **Missing data**: Not all courses have well-defined start/stop dates

**Temporal Overlap SQL**:
```sql
SELECT i.imaging_date, c.medication_name, c.start_datetime, c.stop_datetime,
       CASE
         WHEN i.imaging_date BETWEEN DATE(c.start_datetime) AND DATE(c.stop_datetime)
         THEN 'Active during imaging'
         ELSE 'Not active'
       END as overlap_status
FROM v_imaging i
CROSS JOIN v_chemo_medications c
WHERE i.patient_fhir_id = c.patient_fhir_id
```

---

### 9. Diagnoses (v_diagnoses)

**Challenge**: Tumor diagnosis identification from 50+ conditions

- **Raw Data**: ~50 diagnosis records (ICD-10 codes)
- **Required Filtering**:
  - Identify primary tumor diagnosis (ICD-10 C codes)
  - Exclude general medical conditions
  - Track diagnosis onset vs recorded date
- **Complexity Drivers**:
  - **Code ambiguity**: Multiple ICD-10 codes may reference same tumor
  - **Temporal precision**: Onset date may precede clinical documentation by years
  - **Code hierarchy**: Need to map specific codes to general categories

---

### 10. Encounters (v_encounters)

**Challenge**: Visit type classification and admission tracking

- **Raw Data**: ~300 encounter records
- **Required Classification**:
  - Inpatient vs ambulatory vs emergency
  - Identify encounters near surgeries (potential hospitalizations)
  - Track length of stay for inpatient encounters
- **Complexity Drivers**:
  - **Class code standardization**: Map FHIR class codes to research categories
  - **Encounter hierarchies**: Some encounters are nested (part_of relationships)

---

## Temporal Integration Complexity

### Cross-Source Date Alignment

The extraction workflow must correlate events across **4 primary temporal anchors**:

| Temporal Anchor | Source View | Count | Date Field | Use Case |
|----------------|-------------|-------|------------|----------|
| **Surgery Dates** | `v_procedures_tumor` | 6 | `procedure_date` | Anchor for imaging classification |
| **Radiation Courses** | `v_radiation_summary` | 7 | `course_start_date`, `course_end_date` | Context for progress notes |
| **Chemotherapy Courses** | `v_chemo_medications` | 3 | `start_datetime`, `stop_datetime` | Context for progress notes |
| **Imaging Studies** | `v_imaging` | 189 | `imaging_date` | Timeline visualization |

### Example: Imaging Classification Logic

For **each of 189 imaging studies**, the system must:

1. **Find nearest prior surgery** (if any)
2. **Find nearest future surgery** (if any)
3. **Check radiation status** (active course during imaging?)
4. **Check chemotherapy status** (active treatment during imaging?)
5. **Classify based on temporal relationships**:
   - **Pre-operative**: Imaging 0-90 days before first surgery, no prior surgery
   - **Post-operative**: Imaging 0-180 days after surgery
   - **Surveillance**: Imaging >180 days after surgery, comparing to prior imaging
   - **Progression**: Evidence of tumor growth on surveillance imaging

This requires **O(n × m)** comparisons where:
- `n` = 189 imaging studies
- `m` = 6 surgeries + 7 radiation courses + 3 chemo courses = 16 temporal anchors
- **Total comparisons**: 189 × 16 = **3,024 date calculations**

---

## LLM Processing Requirements

### Extraction Pipeline per Imaging Report

For each imaging report PDF (50 total):

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: Document Retrieval & Preparation              │
├─────────────────────────────────────────────────────────┤
│ 1. AWS SSO Token Check          │ < 1 sec              │
│ 2. S3 Stream PDF                 │ 2-5 sec             │
│ 3. PDF Text Extraction           │ 3-10 sec            │
│ 4. Cache to DuckDB               │ < 1 sec             │
├─────────────────────────────────────────────────────────┤
│ PHASE 2: Context Assembly                              │
├─────────────────────────────────────────────────────────┤
│ 5. Query Surgical History        │ 2-3 sec (Athena)    │
│ 6. Query Radiation History       │ 2-3 sec (Athena)    │
│ 7. Query Chemo History           │ 2-3 sec (Athena)    │
│ 8. Build Temporal Context        │ < 1 sec             │
├─────────────────────────────────────────────────────────┤
│ PHASE 3: LLM Extraction (MedGemma via Ollama)          │
├─────────────────────────────────────────────────────────┤
│ 9. Classification Prompt         │ 30-90 sec (LLM)     │
│ 10. Tumor Status Prompt          │ 30-90 sec (LLM)     │
│ 11. Location Prompt              │ 30-90 sec (LLM)     │
├─────────────────────────────────────────────────────────┤
│ TOTAL PER REPORT: 2.5-4.5 minutes                      │
└─────────────────────────────────────────────────────────┘
```

**For 50 PDF reports**: 125-225 minutes (2-4 hours) of LLM processing time

**For entire patient** (30 text + 50 PDF = 80 imaging reports): **3-6 hours**

---

## Data Quality & Integrity Challenges

### Missing S3 Objects

**Issue**: Metadata exists in `v_binary_files` but S3 objects are missing

**Evidence** (Patient `eNdsM0zzuZ268JeTtY0hitxC1w1.4JrnpT8AldpjJR9E3`):
- **Metadata count**: 21 operative note documents
- **Matched to surgeries**: 18/21 (85.7%)
- **S3 objects available**: 0/6 attempted (0%)
- **Error**: `An error occurred (404) when calling the HeadObject operation: Not Found`

**Impact**:
- 0 operative reports successfully extracted
- Cannot validate surgical pathology findings
- Missing critical tumor characteristic data

**Root Cause**: Data pipeline populates `v_binary_files` metadata before S3 objects are uploaded, or S3 objects are deleted without metadata cleanup.

---

### AWS SSO Token Expiration

**Issue**: Long-running extractions (8-10 hours) exceed SSO token lifetime

**Evidence** (Patient `eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3`):
- **Extraction start**: 10:18 AM
- **Token expiration**: ~6:40 PM (8 hours later)
- **Operative/Progress note phases**: Started after token expiration
- **Result**: 0 operative reports, 0 progress notes extracted

**Mitigation**:
1. Implemented token refresh in `BinaryFileAgent`
2. User preemptively renews SSO before long extractions
3. Resume functionality (partial implementation) to restart from checkpoints

---

### Progress Note Volume

**Challenge**: Extracting from 1,111 notes is computationally infeasible

**Volume Analysis**:
- **Total progress notes**: 1,111 (all specialties)
- **Oncology notes**: 497 (44.7%)
- **Event-prioritized notes**: 16 (1.4%)

**Without Prioritization**:
- 1,111 notes × 2.5 min/note = **2,777 minutes (46 hours)** of processing
- Cost: ~$200-300 in compute/LLM costs

**With Event-Based Prioritization**:
- 16 notes × 2.5 min/note = **40 minutes** of processing
- **99% reduction** in processing time

---

## Technical Architecture Requirements

### Infrastructure Stack

```
┌─────────────────────────────────────────────────────────┐
│ AWS Infrastructure                                       │
├─────────────────────────────────────────────────────────┤
│ • AWS Athena (FHIR data queries)                        │
│ • S3 (Binary file storage)                              │
│ • AWS SSO (Authentication)                              │
│ • boto3 SDK (Python AWS client)                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Local Processing                                         │
├─────────────────────────────────────────────────────────┤
│ • DuckDB (Document text caching)                        │
│ • Ollama (Local LLM runtime)                            │
│ • MedGemma (Medical LLM model)                          │
│ • PDF parsing libraries (PyPDF2, pdfplumber)            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Python Orchestration                                     │
├─────────────────────────────────────────────────────────┤
│ • Multi-source query coordination                       │
│ • Temporal logic engine                                 │
│ • LLM prompt management                                 │
│ • Error handling & retry logic                          │
│ • Checkpoint/resume functionality                       │
└─────────────────────────────────────────────────────────┘
```

---

## Summary Statistics

### Data Integration Scope

| Metric | Value |
|--------|-------|
| **FHIR Data Sources** | 10 distinct views |
| **Total Records** | ~1,700+ (before filtering) |
| **Clinical Documents** | 1,212 (1,111 progress + 21 operative + 80 imaging) |
| **Temporal Span** | 10+ years (2013-2024) |
| **Temporal Anchors** | 16 key clinical events |
| **Required Athena Queries** | 15+ per patient |
| **LLM Extraction Calls** | 240+ per patient (80 reports × 3 calls each) |
| **Estimated Processing Time** | 8-10 hours per patient |
| **Successful Extractions** | 94 structured data points |

### Data Source Complexity Ranking

1. **Progress Notes** (EXTREME): 1,111 → 16 selection, event-based prioritization
2. **Imaging PDF Reports** (VERY HIGH): S3 streaming + PDF parsing + 3 LLM calls
3. **Imaging Text Reports** (VERY HIGH): Temporal classification + 3 LLM calls
4. **Operative Notes** (VERY HIGH): Surgery matching + S3 streaming + PDF parsing
5. **Radiation Summary** (HIGH): Multi-level aggregation, dose summation
6. **Imaging Studies** (HIGH): Temporal classification, modality mapping
7. **Chemotherapy** (MEDIUM): Temporal overlap, concomitant meds
8. **Tumor Procedures** (MEDIUM): Classification, temporal anchoring
9. **Diagnoses** (MEDIUM): Code filtering, tumor identification
10. **Encounters** (LOW): Visit type classification

---

## Key Takeaways for Stakeholders

### 1. Data Complexity
Comprehensive oncology data extraction requires integrating **10+ heterogeneous data sources** spanning **10+ years**, each with unique temporal relationships and data quality challenges.

### 2. Processing Requirements
Extracting one patient requires:
- **15+ Athena queries** to assemble context
- **240+ LLM inference calls** for unstructured data extraction
- **8-10 hours** of end-to-end processing time
- **Robust infrastructure** (AWS + local compute + LLM runtime)

### 3. Data Quality Gaps
Real-world EHR data has significant integrity issues:
- **S3 object availability**: 0% for some patients' operative notes
- **Metadata-data mismatches**: Metadata exists but files missing
- **Temporal ambiguity**: Date fields may reflect dictation, not event occurrence

### 4. Intelligent Prioritization is Essential
Without event-based filtering:
- Processing **1,111 progress notes** = **46 hours**
- With prioritization: **16 notes** = **40 minutes** (99% reduction)

### 5. Technical Sophistication Required
This is not "simple database query" work. It requires:
- **Temporal reasoning engines** for cross-source date correlation
- **LLM orchestration** with prompt management and retry logic
- **Infrastructure management** (AWS SSO, S3, Athena, DuckDB, Ollama)
- **Error handling** for data quality issues
- **Resume functionality** for long-running processes

---

**Document Created**: 2025-10-24
**Patient Examples**: `Patient/eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3`, `Patient/eNdsM0zzuZ268JeTtY0hitxC1w1.4JrnpT8AldpjJR9E3`
**Extraction Framework**: [run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py)
