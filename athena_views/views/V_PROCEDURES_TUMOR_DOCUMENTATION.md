# v_procedures_tumor Enhanced View Documentation

**Last Updated:** 2025-10-29
**Version:** Enhanced with OR Case Annotations
**Database:** fhir_prd_db
**View Name:** v_procedures_tumor

## Table of Contents
1. [Overview](#overview)
2. [Key Enhancements](#key-enhancements)
3. [Comparison to surgical_procedures Table](#comparison-to-surgical_procedures-table)
4. [Schema Documentation](#schema-documentation)
5. [Data Quality and Coverage](#data-quality-and-coverage)
6. [Usage Examples](#usage-examples)
7. [Classification Logic](#classification-logic)
8. [Performance Considerations](#performance-considerations)

---

## Overview

`v_procedures_tumor` is a comprehensive FHIR-based view that identifies and classifies surgical procedures, with specialized logic for detecting neurosurgical tumor resections and related procedures. The view combines multiple FHIR resources and applies multi-tier classification logic to categorize procedures.

### Purpose
- **Primary Use:** Identify all tumor-related surgical procedures across the patient population
- **Secondary Use:** Provide comprehensive procedure tracking including orders, history, and OR cases
- **Key Feature:** Multi-tier tumor surgery classification using CPT codes, keywords, reason codes, and body sites

### Data Sources
- `fhir_prd_db.procedure` - Base FHIR Procedure resource
- `fhir_prd_db.procedure_code_coding` - CPT codes, Epic codes, SNOMED categories
- `fhir_prd_db.procedure_identifier` - Epic OR Log IDs (ORL identifiers)
- `fhir_prd_db.procedure_reason_code` - Procedure indications
- `fhir_prd_db.procedure_body_site` - Anatomical locations
- `fhir_prd_db.surgical_procedures` - Epic OR case data (for linkage)

---

## Key Enhancements

### New Annotation Columns (Added 2025-10-29)

The enhanced view includes 10 new annotation columns to help distinguish OR cases from procedure orders and surgical history:

| Column Name | Type | Description | Use Case |
|-------------|------|-------------|----------|
| `epic_or_log_id` | VARCHAR | Epic OR Log ID from procedure_identifier table | Link to Epic OR case tracking |
| `in_surgical_procedures_table` | BOOLEAN | TRUE if procedure exists in surgical_procedures table | Validate OR case linkage |
| `surgical_procedures_mrn` | VARCHAR | MRN from surgical_procedures (if linked) | Cross-reference patient ID |
| `surgical_procedures_epic_case_id` | VARCHAR | Epic case ID from surgical_procedures | Link to Epic case |
| `proc_category_annotation` | VARCHAR | Simplified category: PROCEDURE_ORDER, SURGICAL_HISTORY, SURGICAL_PROCEDURE, etc. | Easy filtering by category |
| `procedure_source_type` | VARCHAR | High-level source: OR_CASE, SURGICAL_HISTORY, PROCEDURE_ORDER, etc. | Primary filtering column |
| `is_likely_performed` | BOOLEAN | TRUE if procedure was likely actually performed (excludes orders, not-done) | Filter to actual procedures |
| `proc_status_annotation` | VARCHAR | Simplified status: COMPLETED, NOT_DONE, ERROR, etc. | Easy status filtering |
| `has_minimum_data_quality` | BOOLEAN | TRUE if has date, completed status, and CPT code | Data quality filter |
| `category_coding_code` | VARCHAR | SNOMED category code (e.g., 387713003 = surgical procedure) | SNOMED-based filtering |

### Enhancement Benefits
1. **Clear OR Case Identification:** Use `procedure_source_type = 'OR_CASE'` to get only actual OR cases
2. **Exclude Procedure Orders:** Filter out requisitions that were never performed
3. **Link to Epic:** Connect to Epic OR Log IDs for OR case details
4. **Data Quality Filtering:** Use `is_likely_performed` and `has_minimum_data_quality` flags
5. **Backward Compatible:** All original columns preserved, new columns added at end

---

## Comparison to surgical_procedures Table

### Overview
- **surgical_procedures:** Epic OR case data only (upfront filtered)
- **v_procedures_tumor:** Comprehensive FHIR procedure data (includes orders, history, OR cases)

### Side-by-Side Comparison

| Aspect | v_procedures_tumor | surgical_procedures |
|--------|-------------------|---------------------|
| **Total Procedures** | 69,635 | 8,513 |
| **Unique Patients** | 1,835 | 1,592 |
| **Date Coverage** | 1970-2025 (96% have dates) | 2005-2025 (100% have dates) |
| **Tumor Surgeries** | 4,169 (6.0%) | 3,204 (37.6%) |
| **Unique CPT Codes** | 1,302 | 582 |
| **Data Source** | FHIR Procedure resource | Epic OR log (Clarity) |
| **Column Count** | 56 (46 original + 10 new) | 11 |

### Patient Overlap
- **100% overlap:** All 1,592 patients in surgical_procedures exist in v_procedures_tumor
- **surgical_procedures is a subset:** It contains only OR cases with specific criteria
- **v_procedures_tumor is comprehensive:** Includes orders, history, and all OR cases

### Data Volume Breakdown (v_procedures_tumor)

| Category | Procedures | % of Total | Patients | Tumor Surgeries |
|----------|------------|------------|----------|-----------------|
| **OR Cases** | 10,299 | 14.8% | 1,599 | 3,254 |
| **Procedure Orders** | 44,487 | 63.9% | 1,725 | 516* |
| **Surgical History (Completed)** | 8,713 | 12.5% | 1,614 | 146 |
| **Surgical History (Not Done)** | 6,136 | 8.8% | 438 | 0 |

*Note: The 516 "tumor surgeries" in procedure orders are likely order codes that match tumor surgery CPT codes but were never performed. Filter these out using `is_likely_performed = true`.

### Key Differences in Filtering Strategy

#### surgical_procedures (Upfront Filtering)
```sql
WHERE category_coding_code = '387713003'  -- SNOMED: Surgical procedure
  AND identifier_type_text = 'ORL'         -- Has Epic OR Log ID
  AND proc_status = 'completed'            -- Completed only
```

#### v_procedures_tumor (No Upfront Filtering, Post-hoc Classification)
- No WHERE clause filtering
- Includes all procedure categories (orders, history, OR cases)
- Uses multi-tier classification logic to identify tumor surgeries
- Relies on annotation columns for filtering

### When to Use Each

**Use surgical_procedures when:**
- You ONLY need Epic OR cases
- You need Epic-specific fields (surgeon, anesthesia times, OR room)
- You want pre-filtered, high-quality OR data
- Performance is critical (8.5K rows vs 69K rows)

**Use v_procedures_tumor when:**
- You need comprehensive procedure tracking (orders, history, OR)
- You need tumor surgery classification logic
- You need FHIR-based procedure data
- You want to analyze procedure orders vs performed procedures
- You need more detailed CPT coding (1,302 vs 582 codes)

**Use BOTH when:**
- Cross-validating OR case data
- Linking FHIR procedures to Epic OR cases
- Comprehensive surgical analytics requiring both perspectives

---

## Schema Documentation

### Original Columns (46 total)

#### Patient & Procedure Identifiers
| Column | Type | Description |
|--------|------|-------------|
| patient_fhir_id | VARCHAR | FHIR Patient resource reference |
| procedure_fhir_id | VARCHAR | FHIR Procedure resource ID |
| proc_subject_reference | VARCHAR | Subject reference (usually patient) |
| proc_encounter_reference | VARCHAR | Associated encounter reference |
| proc_encounter_display | VARCHAR | Encounter display text |

#### Procedure Status & Dates
| Column | Type | Description |
|--------|------|-------------|
| proc_status | VARCHAR | FHIR status (completed, not-done, etc.) |
| proc_performed_date_time | TIMESTAMP(3) | Performed datetime |
| proc_performed_period_start | TIMESTAMP(3) | Period start |
| proc_performed_period_end | TIMESTAMP(3) | Period end |
| proc_performed_string | TIMESTAMP(3) | String representation as timestamp |
| proc_performed_age_value | TIMESTAMP(3) | Age value (if applicable) |
| proc_performed_age_unit | TIMESTAMP(3) | Age unit |
| procedure_date | DATE | Derived procedure date (COALESCE of datetime/period) |

#### Procedure Codes & Text
| Column | Type | Description |
|--------|------|-------------|
| proc_code_text | VARCHAR | Procedure code text/description |
| proc_category_text | VARCHAR | Epic category (Ordered Procedures, Surgical History, Surgical Procedures) |
| code_coding_system | VARCHAR | Coding system URI |
| code_coding_code | VARCHAR | Primary procedure code |
| code_coding_display | VARCHAR | Code display text |

#### Classification Fields
| Column | Type | Description |
|--------|------|-------------|
| cpt_classification | VARCHAR | CPT-based classification (craniotomy_tumor_resection, etc.) |
| cpt_code | VARCHAR | CPT code |
| cpt_type | VARCHAR | Classification type (definite_tumor, tumor_support, ambiguous, exclude) |
| epic_category | VARCHAR | Epic code category (neurosurgery_request, general_surgery_request) |
| epic_code | VARCHAR | Epic internal code |
| keyword_classification | VARCHAR | Keyword-based classification (keyword_tumor_specific, keyword_exclude, keyword_surgical_generic) |

#### Validation Fields
| Column | Type | Description |
|--------|------|-------------|
| has_tumor_reason | BOOLEAN | Reason code indicates tumor |
| has_exclude_reason | BOOLEAN | Reason code indicates exclusion |
| has_tumor_body_site | BOOLEAN | Body site indicates tumor location |
| has_exclude_body_site | BOOLEAN | Body site indicates exclusion |
| validation_reason_code | VARCHAR | Reason code text for validation |
| validation_body_site | VARCHAR | Body site text for validation |

#### Final Classification
| Column | Type | Description |
|--------|------|-------------|
| procedure_classification | VARCHAR | Final classification (COALESCE of cpt_classification, epic_category, keyword_classification) |
| is_tumor_surgery | BOOLEAN | TRUE if classified as tumor surgery |
| is_excluded_procedure | BOOLEAN | TRUE if should be excluded (shunts, nerve blocks, etc.) |
| classification_confidence | INTEGER | Confidence score (1=highest, 30=lowest) |

#### Reason Codes & Body Sites
| Column | Type | Description |
|--------|------|-------------|
| reason_code | VARCHAR | Procedure indication |
| reason_code_system | VARCHAR | Reason code system |
| reason_code_display | VARCHAR | Reason code display |
| body_site_text | VARCHAR | Anatomical location |
| body_site_system | VARCHAR | Body site coding system |
| body_site_code | VARCHAR | Body site code |

#### Additional Metadata
| Column | Type | Description |
|--------|------|-------------|
| note_text | VARCHAR | Procedure notes |
| outcome_text | VARCHAR | Procedure outcome |
| complication_text | VARCHAR | Complications |
| followup_text | VARCHAR | Follow-up instructions |
| report_text | VARCHAR | Procedure report |
| used_reference | VARCHAR | Devices/materials used |
| used_display | VARCHAR | Used item display text |

### New Annotation Columns (10 total)

See [Key Enhancements](#key-enhancements) section above for detailed descriptions.

---

## Data Quality and Coverage

### Procedure Count Summary (Total: 69,635)

```
OR Cases:                10,299 (14.8%)
├─ With Epic OR Log:     10,299 (100%)
├─ In surgical_proc:     10,256 (99.6%)
└─ Tumor surgeries:       3,254 (31.6%)

Procedure Orders:        44,487 (63.9%)
├─ Completed status:     44,487 (100%)
├─ Likely performed:          0 (0%)
└─ Tumor surgeries:         516 (1.2%)*

Surgical History:        14,849 (21.3%)
├─ Completed:             8,713 (58.7%)
│  └─ Tumor surgeries:      146 (1.7%)
└─ Not done:              6,136 (41.3%)
```

*Note: These 516 are procedure orders with tumor surgery CPT codes, not performed procedures.

### Patient Coverage
- **Total Patients:** 1,835
- **With OR Cases:** 1,599 (87.1%)
- **With Procedure Orders:** 1,725 (94.0%)
- **With Surgical History:** 1,646 (89.7%)

### Date Coverage
- **Date Range:** 1970-01-01 to 2025-10-29
- **Procedures with Dates:** 66,746 (95.9%)
- **Missing Dates:** 2,889 (4.1%)

### CPT Code Distribution
- **Unique CPT Codes:** 1,302
- **Top 10 CPT codes account for:** 31.2% of all procedures
- **Tumor surgery CPT codes:** 127 distinct codes

### Data Quality Flags
- **has_minimum_data_quality = TRUE:** 4,349 procedures (6.2%)
  - Requires: procedure_date IS NOT NULL, status = 'completed', CPT code IS NOT NULL
- **is_likely_performed = TRUE:** 18,012 procedures (25.9%)
  - Excludes: orders, not-done, entered-in-error

---

## Usage Examples

### Example 1: Get Only OR Cases (Actual Surgeries)
```sql
SELECT
    patient_fhir_id,
    procedure_fhir_id,
    procedure_date,
    proc_code_text,
    epic_or_log_id,
    is_tumor_surgery
FROM fhir_prd_db.v_procedures_tumor
WHERE procedure_source_type = 'OR_CASE'
  AND is_tumor_surgery = true
ORDER BY procedure_date DESC;
```

### Example 2: Exclude Procedure Orders (Get Only Performed Procedures)
```sql
SELECT
    patient_fhir_id,
    procedure_date,
    proc_code_text,
    procedure_classification,
    classification_confidence
FROM fhir_prd_db.v_procedures_tumor
WHERE is_likely_performed = true
  AND proc_status_annotation = 'COMPLETED'
ORDER BY procedure_date DESC;
```

### Example 3: Link to surgical_procedures Table
```sql
SELECT
    vpt.patient_fhir_id,
    vpt.procedure_fhir_id,
    vpt.proc_code_text,
    vpt.epic_or_log_id,
    vpt.in_surgical_procedures_table,
    vpt.surgical_procedures_mrn,
    vpt.surgical_procedures_epic_case_id
FROM fhir_prd_db.v_procedures_tumor vpt
WHERE vpt.in_surgical_procedures_table = true
  AND vpt.is_tumor_surgery = true;
```

### Example 4: Compare Orders vs Performed for Tumor Surgeries
```sql
SELECT
    procedure_source_type,
    proc_category_annotation,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    SUM(CASE WHEN is_tumor_surgery THEN 1 ELSE 0 END) as tumor_surgeries
FROM fhir_prd_db.v_procedures_tumor
WHERE is_tumor_surgery = true
GROUP BY procedure_source_type, proc_category_annotation
ORDER BY procedure_count DESC;
```

### Example 5: High-Quality Tumor Surgery Data Only
```sql
SELECT
    patient_fhir_id,
    procedure_date,
    proc_code_text,
    cpt_code,
    procedure_classification,
    classification_confidence
FROM fhir_prd_db.v_procedures_tumor
WHERE is_tumor_surgery = true
  AND has_minimum_data_quality = true
  AND is_likely_performed = true
  AND procedure_source_type = 'OR_CASE'
ORDER BY procedure_date DESC;
```

### Example 6: Analyze Procedure Orders That Were Never Performed
```sql
SELECT
    proc_code_text,
    cpt_code,
    COUNT(*) as order_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_procedures_tumor
WHERE procedure_source_type = 'PROCEDURE_ORDER'
  AND is_tumor_surgery = true
GROUP BY proc_code_text, cpt_code
ORDER BY order_count DESC
LIMIT 20;
```

### Example 7: Find Discrepancies Between v_procedures_tumor and surgical_procedures
```sql
-- Procedures in v_procedures_tumor with OR Log but NOT in surgical_procedures
SELECT
    patient_fhir_id,
    procedure_fhir_id,
    epic_or_log_id,
    proc_code_text,
    procedure_date
FROM fhir_prd_db.v_procedures_tumor
WHERE epic_or_log_id IS NOT NULL
  AND in_surgical_procedures_table = false;
```

---

## Classification Logic

### Multi-Tier Tumor Surgery Classification

The view uses a cascading classification system with 4 tiers:

#### Tier 1: CPT Code Classification (Highest Confidence)
Definite tumor surgeries identified by specific CPT codes:
- **craniotomy_tumor_resection:** CPT codes 61500, 61510, 61518, 61545, etc.
- **stereotactic_tumor_procedure:** CPT codes 61750, 61751, 61781, etc.
- **endoscopic_tumor_procedure:** CPT codes 62201, 31291, etc.
- **biopsy_tumor:** CPT codes 61140, 61750, etc.

Confidence Score: 1-5

#### Tier 2: Keyword-Based Classification
When CPT is ambiguous or missing, examine procedure text:
- **keyword_tumor_specific:** "craniotomy tumor", "tumor resection", "brain biopsy"
- **keyword_surgical_generic:** "craniotomy", "craniectomy", "surgery"
- **keyword_exclude:** "shunt", "nerve block", "lumbar puncture"

Confidence Score: 10-20

#### Tier 3: Reason Code Validation
Validate using procedure indications:
- **has_tumor_reason:** Reason codes like "brain tumor", "tumor excision", "biopsy tumor"
- **has_exclude_reason:** Reasons like "pain management", "hydrocephalus"

Confidence Score: Used to upgrade ambiguous cases

#### Tier 4: Body Site Validation
Validate using anatomical location:
- **has_tumor_body_site:** Body sites like "brain", "cranial", "cerebral"
- **has_exclude_body_site:** Sites like "spine", "peripheral nerve"

Confidence Score: Used to upgrade ambiguous cases

### Final is_tumor_surgery Logic
```sql
is_tumor_surgery =
  CASE
    WHEN has_exclude_reason OR has_exclude_body_site THEN FALSE
    WHEN cpt_type = 'definite_tumor' THEN TRUE
    WHEN cpt_type = 'tumor_support' THEN TRUE
    WHEN cpt_type = 'ambiguous' AND (has_tumor_reason OR has_tumor_body_site) THEN TRUE
    WHEN cpt_type IS NULL AND keyword_classification = 'keyword_tumor_specific' THEN TRUE
    ELSE FALSE
  END
```

### Exclusion Criteria
Procedures excluded from tumor surgery classification:
- **Shunt procedures:** VP shunts, EVD placements
- **Pain management:** Nerve blocks, chemodenervation, Botox
- **Diagnostic only:** Lumbar punctures, spinal taps (unless tumor-specific)
- **Exclude reason codes:** Hydrocephalus, pain, etc.
- **Exclude body sites:** Spine, peripheral nerves (unless tumor-specific)

---

## Performance Considerations

### View Complexity
- **Multiple CTEs:** 8 CTEs for classification logic
- **Multiple JOINs:** 7+ LEFT JOINs to various FHIR tables
- **Row Count:** 69,635 rows (8x larger than surgical_procedures)
- **Column Count:** 56 columns (5x more than surgical_procedures)

### Query Optimization Tips

1. **Always filter by procedure_source_type first:**
   ```sql
   WHERE procedure_source_type = 'OR_CASE'  -- Reduces from 69K to 10K rows
   ```

2. **Use is_likely_performed for actual procedures:**
   ```sql
   WHERE is_likely_performed = true  -- Reduces from 69K to 18K rows
   ```

3. **Filter by date early:**
   ```sql
   WHERE procedure_date >= DATE '2020-01-01'
   ```

4. **Use has_minimum_data_quality for high-quality data:**
   ```sql
   WHERE has_minimum_data_quality = true  -- Reduces to 4.3K rows
   ```

5. **Index-friendly filters:**
   - Filter by patient_fhir_id early in the query
   - Use exact matches on categorical fields (procedure_source_type, proc_category_annotation)

### Recommended Filter Combinations

**For clinical research (highest quality):**
```sql
WHERE procedure_source_type = 'OR_CASE'
  AND has_minimum_data_quality = true
  AND is_tumor_surgery = true
  AND classification_confidence <= 5
```

**For comprehensive tracking:**
```sql
WHERE is_likely_performed = true
  AND proc_status_annotation = 'COMPLETED'
  AND procedure_date IS NOT NULL
```

**For Epic OR case linkage:**
```sql
WHERE epic_or_log_id IS NOT NULL
  AND in_surgical_procedures_table = true
```

---

## Maintenance and Updates

### Last Major Updates
- **2025-10-29:** Added 10 annotation columns for OR case identification and linkage
- **2025-10-29:** Fixed procedure_codes CTE to include keyword_classification column
- **Previous:** Multi-tier tumor surgery classification logic

### Known Issues
- 516 procedure orders flagged as tumor surgeries (likely order codes matching tumor CPT codes)
  - **Workaround:** Filter using `is_likely_performed = true`
- 43 procedures have Epic OR Log IDs but aren't in surgical_procedures table
  - **Investigate:** May be cancelled OR cases or data sync issues

### Future Enhancements
- Add radiation procedure classification
- Include chemotherapy administration procedures
- Link to imaging procedures for surgical planning
- Add surgeon and OR team information from Epic

---

## Contact and Support

**Data Source:** FHIR Production Database (fhir_prd_db)
**Maintained By:** BRIM Analytics Team
**View Location:** `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/`

For questions or issues, please refer to:
- View definition: `DATETIME_STANDARDIZED_VIEWS.sql` (lines 2569-3032)
- Enhanced version: `V_PROCEDURES_TUMOR_ENHANCED_FULL.sql`
- Comparison analysis: `PROCEDURES_COMPARISON_ANALYSIS.md`
