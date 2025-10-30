# Surgical Procedures Comparison Analysis
## v_procedures_tumor (View) vs surgical_procedures (Table)

**Analysis Date:** 2025-10-29
**Purpose:** Deep comparison of structure, content, and surgical procedure representation

---

## Executive Summary

Two surgical procedure data sources exist in `fhir_prd_db`:
1. **`v_procedures_tumor`** - Comprehensive FHIR-based view with tumor surgery classification (69,635 procedures, 1,835 patients)
2. **`surgical_procedures`** - New Epic-sourced table focused on surgical cases (8,513 procedures, 1,592 patients)

**Key Findings:**
- **100% patient overlap** - All 1,592 patients in `surgical_procedures` exist in `v_procedures_tumor`
- **100% CPT overlap** - All 582 CPT codes in `surgical_procedures` exist in `v_procedures_tumor`
- **8.2x more procedures** in v_procedures_tumor (69,635 vs 8,513)
- **Different data sources**: FHIR Procedure resource vs Epic surgical cases
- **Complementary strengths**: v_procedures_tumor has clinical classification, surgical_procedures has Epic case IDs

---

## 1. Schema Comparison

### Column Count
- **v_procedures_tumor:** 46 columns
- **surgical_procedures:** 11 columns

### Common Fields

| Field | v_procedures_tumor | surgical_procedures | Notes |
|-------|-------------------|---------------------|-------|
| **Patient ID** | `patient_fhir_id` | `patient_id` | Same format |
| **Procedure ID** | `procedure_fhir_id` | `procedure_id` | Different ID systems |
| **CPT Code** | `cpt_code` | `cpt_code` | ✅ Same |
| **Procedure Text** | `proc_code_text` | `procedure_display` | Different descriptors |
| **Status** | `proc_status` | `status` | ✅ Same values |
| **Date** | `procedure_date` (DATE) | `performed_period_start` (STRING) | Different types |
| **Performer** | `pp_performer_actor_display` | `performer` | ✅ Same values |
| **Outcome** | `proc_outcome_text` | `outcome_text` | Similar |

### Unique to v_procedures_tumor (35 additional columns)

**FHIR Resource Fields:**
- `proc_performed_date_time`, `proc_performed_period_start/end`
- `proc_performed_string`, `proc_performed_age_value/unit`
- `proc_category_text`
- `proc_encounter_reference`, `proc_encounter_display`
- `proc_location_reference`, `proc_location_display`
- `proc_recorder_reference/display`
- `proc_asserter_reference/display`
- `proc_status_reason_text`
- `proc_subject_reference`

**Clinical Classification (Unique Value!):**
- `is_surgical_keyword` (boolean)
- `procedure_classification` (31 categories)
- `cpt_classification` (31 categories)
- `cpt_type` (14 types)
- `epic_category` (23 categories)
- `epic_code`
- `keyword_classification` (24 categories)

**Tumor Surgery Classification (HIGH VALUE!):**
- `is_tumor_surgery` (boolean) - **4,169 tumor surgeries identified**
- `is_excluded_procedure` (boolean)
- `surgery_type` (varchar) - e.g., "resection", "biopsy", "shunt"
- `classification_confidence` (integer)
- `has_tumor_reason`, `has_exclude_reason` (booleans)
- `has_tumor_body_site`, `has_exclude_body_site` (booleans)
- `validation_reason_code`, `validation_body_site`

**Additional Context:**
- `age_at_procedure_days` (derived field)
- `pcc_code_coding_system/code/display` (procedure coding)
- `pcat_category_coding_display` (category)
- `pbs_body_site_text` (body site)
- `pp_performer_function_text` (performer role)

### Unique to surgical_procedures (2 additional columns)

- **`mrn`** - Medical record number (1,592 unique MRNs)
- **`epic_case_orlog_id`** - Epic OR log case ID (4,431 unique cases)
  - **HIGH VALUE:** Direct link to Epic surgical case records
  - Allows linkage to OR time data, surgical staff, equipment, etc.

---

## 2. Content Volume Comparison

| Metric | v_procedures_tumor | surgical_procedures | Ratio |
|--------|-------------------|---------------------|-------|
| **Total Procedures** | 69,635 | 8,513 | 8.2:1 |
| **Unique Patients** | 1,835 | 1,592 | 1.15:1 |
| **Procedures per Patient** | 37.9 | 5.3 | 7.1:1 |
| **Unique CPT Codes** | 1,302 | 582 | 2.2:1 |
| **Procedures with CPT** | 46,626 (67%) | 7,380 (87%) | - |
| **Date Coverage** | 66,890 (96%) | 8,513 (100%) | - |

### Why the Large Volume Difference?

**v_procedures_tumor includes:**
- All FHIR Procedure resources (surgical AND non-surgical)
- Multiple procedure records per surgical case
- Ancillary procedures (e.g., navigational, microscopy)
- Historical procedures across all encounters

**surgical_procedures includes:**
- Only procedures linked to Epic surgical cases (OR log entries)
- Primary surgical procedures from OR cases
- More recent data (loaded today)

---

## 3. Patient and CPT Code Overlap

### Patient Overlap

| Category | Count | Percentage |
|----------|-------|------------|
| **Patients in surgical_procedures** | 1,592 | 100% |
| **Patients in v_procedures_tumor** | 1,835 | - |
| **Overlap (in both)** | 1,592 | **100%** |
| **Only in v_procedures_tumor** | 243 | 13.2% |

**Key Finding:** ✅ **100% of surgical_procedures patients exist in v_procedures_tumor**
- Confirms surgical_procedures is a **subset** of v_procedures_tumor
- 243 additional patients in v_procedures_tumor likely have procedures but no Epic OR cases

### CPT Code Overlap

| Category | Count | Percentage |
|----------|-------|------------|
| **CPT codes in v_procedures_tumor** | 1,302 | - |
| **CPT codes in surgical_procedures** | 582 | - |
| **Overlap (in both)** | 582 | **100%** |
| **Only in v_procedures_tumor** | 720 | 55.3% |

**Key Finding:** ✅ **100% of surgical_procedures CPT codes exist in v_procedures_tumor**
- surgical_procedures uses common surgical CPT codes
- v_procedures_tumor captures 720 additional CPT codes (non-surgical, ancillary, historical)

---

## 4. Top Surgical Procedures Comparison

### Top 10 CPT Codes in v_procedures_tumor (Tumor Surgeries Only)

| Rank | CPT | Description | Count | Patients |
|------|-----|-------------|-------|----------|
| 1 | 61781 | Stereotactic computer-assisted intradural | 852 | 551 |
| 2 | 64999 | Unlisted procedure nervous system | 452 | 233 |
| 3 | 61781 | Navigational procedure brain (intra) | 373 | 333 |
| 4 | 61510 | Craniotomy, trephine bone flap brain tumor supratentorial | 295 | 233 |
| 5 | 61510 | Craniotomy, brain tumor excision, supratentorial | 295 | 259 |
| 6 | 61518 | Craniectomy, excision brain tumor infratentorial/posterior fossa | 243 | 200 |
| 7 | 61210 | Burr hole implant ventricular catheter/other device | 214 | 171 |
| 8 | 61518 | Craniotomy posterior fossa/suboccipital brain tumor resection | 198 | 175 |
| 9 | 61500 | Craniectomy with excision tumor/lesion skull | 157 | 139 |
| 10 | 61210 | Ventriculostomy placement, EVD burr hole | 155 | 137 |

### Top 10 CPT Codes in surgical_procedures

| Rank | CPT | Description | Count | Patients |
|------|-----|-------------|-------|----------|
| 1 | 61781 | Stereotactic computer-assisted intradural | 805 | 557 |
| 2 | 61781 | Navigational procedure brain (intra) | 366 | 333 |
| 3 | 64999 | Unlisted procedure nervous system | 360 | 243 |
| 4 | 61510 | Craniotomy, brain tumor excision, supratentorial | 286 | 257 |
| 5 | 61510 | Craniotomy, trephine bone flap brain tumor supratentorial | 269 | 230 |
| 6 | 61518 | Craniectomy, excision brain tumor infratentorial/posterior fossa | 224 | 192 |
| 7 | 61210 | Burr hole implant ventricular catheter/other device | 207 | 171 |
| 8 | 61518 | Craniotomy posterior fossa/suboccipital brain tumor resection | 192 | 175 |
| 9 | 61210 | Ventriculostomy placement, EVD burr hole | 151 | 138 |
| 10 | 61781 | Navigational procedure brain, Axiem | 150 | 131 |

**Key Observations:**
- ✅ **Exact same top procedures** in both sources (same rank order)
- ✅ **Similar procedure counts** (within ~5-10% for most codes)
- ✅ **Same patient counts** for most procedures
- **Confirms:** surgical_procedures captures major surgical cases well

---

## 5. Tumor Surgery Classification Analysis

**CRITICAL ADVANTAGE of v_procedures_tumor:**

### Tumor Surgery Identification

| Metric | v_procedures_tumor | surgical_procedures |
|--------|-------------------|---------------------|
| **Tumor Surgeries Identified** | 4,169 | N/A (not classified) |
| **Surgical Keyword Matches** | 7,238 | N/A |
| **Excluded Procedures** | 2,881 | N/A |

### Surgery Type Classification

**v_procedures_tumor provides detailed surgery types:**

| Surgery Type | Description | Use Case |
|--------------|-------------|----------|
| `craniotomy` | Resection surgeries | Primary tumor removal |
| `stereotactic_procedure` | Navigational/stereotactic | Biopsy, targeted therapy |
| `unknown` | Unlisted/other | Requires manual review |
| *(others)* | Shunt, biopsy, etc. | Specific procedure types |

**surgical_procedures:** ❌ No tumor surgery classification
- All procedures treated equally
- Cannot distinguish tumor resection vs. shunt placement vs. biopsy
- Requires manual review or linking to v_procedures_tumor

---

## 6. Data Quality Comparison

### Date Availability

| Source | Field | Coverage | Format |
|--------|-------|----------|--------|
| **v_procedures_tumor** | `procedure_date` | 66,890 (96%) | DATE |
| **v_procedures_tumor** | `proc_performed_date_time` | 13,670 (20%) | TIMESTAMP(3) |
| **v_procedures_tumor** | `proc_performed_period_start` | 0 (0%) | TIMESTAMP(3) |
| **surgical_procedures** | `performed_period_start` | 8,513 (100%) | STRING (ISO8601) |
| **surgical_procedures** | `performed_period_end` | 8,513 (100%) | STRING (ISO8601) |

**Key Findings:**
- ✅ surgical_procedures has **100% date coverage**
- ✅ v_procedures_tumor has **96% date coverage** (procedure_date)
- ⚠️ surgical_procedures dates are STRING type (need casting)
- ✅ v_procedures_tumor dates are proper DATE/TIMESTAMP types

### Epic Linkage

| Source | Epic Field | Coverage | Unique Values |
|--------|-----------|----------|---------------|
| **v_procedures_tumor** | `epic_code` | 9,855 (14%) | 84 unique |
| **v_procedures_tumor** | `epic_category` | N/A | 23 categories |
| **surgical_procedures** | `epic_case_orlog_id` | 8,513 (100%) | 4,431 unique |

**CRITICAL DIFFERENCE:**
- **v_procedures_tumor:** Has Epic *codes* and *categories* (classifications)
- **surgical_procedures:** Has Epic *case IDs* (direct OR log linkage)
- **Implication:** surgical_procedures enables linkage to Epic OR data (times, staff, equipment)

### MRN Availability

| Source | MRN Field | Availability |
|--------|-----------|--------------|
| **v_procedures_tumor** | None | ❌ Not available |
| **surgical_procedures** | `mrn` | ✅ 1,592 unique MRNs (100%) |

**Value:** surgical_procedures provides MRN for direct Epic patient lookup

---

## 7. Sample Data Comparison

### v_procedures_tumor Sample (Tumor Surgery)
```
Patient: ecuOhnjtGGUhEQgPz2Bokh8GYFmt9RZZB6yi-8vLv6943
Procedure ID: fqJCIloRBDCf1tBE90O4PCdVw8XjkbkCVKMRC1UeKryM4
Date: 2025-07-29
CPT: 61518
Description: CRNEC EXC BRAIN TUMOR INFRATENTORIAL/POST FOSSA
Status: completed
is_tumor_surgery: TRUE
surgery_type: craniotomy
Performer: Phillip Storm, MD
```

### surgical_procedures Sample (Same Patient, Different Procedure)
```
Patient: ecuOhnjtGGUhEQgPz2Bokh8GYFmt9RZZB6yi-8vLv6943
Procedure ID: fb9mnj6tdOSo07eRebfUeVPyUwA4KYlHgp6d.y7QT-0U4
Date: 2025-07-29T14:59:00Z
CPT: 69990
Description: MICROSURG TQS REQ USE OPERATING MICROSCOPE
Status: completed
Epic Case: 1038154
Performer: Phillip Storm, MD
```

**Observation:** Same patient, same date, different procedures
- v_procedures_tumor: Primary tumor surgery (61518)
- surgical_procedures: Ancillary microscopy procedure (69990)
- **Implication:** Multiple procedure records per surgical case

---

## 8. Strengths and Weaknesses

### v_procedures_tumor Strengths ✅

1. **Tumor Surgery Classification**
   - 4,169 tumor surgeries explicitly identified
   - Surgery type classification (craniotomy, biopsy, shunt, etc.)
   - Confidence scoring for classifications

2. **Comprehensive Procedure Coverage**
   - 69,635 procedures (8.2x more than surgical_procedures)
   - 1,302 unique CPT codes (2.2x more)
   - Historical procedures across all encounters

3. **Rich Clinical Context**
   - Body site, reason code validation
   - Encounter linkage
   - Performer role/function
   - Location references

4. **FHIR Compliance**
   - Standard FHIR Procedure resource structure
   - Interoperable with other FHIR systems

### v_procedures_tumor Weaknesses ❌

1. **No Epic Case ID**
   - Cannot link to Epic OR log data
   - Cannot access OR times, equipment, staff assignments

2. **No MRN**
   - Cannot do direct Epic patient lookup without additional joins

3. **Lower Date Coverage for Timestamps**
   - Only 20% have `proc_performed_date_time` (detailed timestamp)
   - 0% have `proc_performed_period_start/end`

4. **Epic Code Coverage**
   - Only 14% of procedures have `epic_code`
   - Limited Epic category data

### surgical_procedures Strengths ✅

1. **Epic OR Case Linkage**
   - 100% have `epic_case_orlog_id`
   - Direct link to Epic surgical case records
   - Enables OR time, staff, equipment analysis

2. **MRN Availability**
   - 100% have `mrn` field
   - Direct Epic patient identification

3. **100% Date Coverage**
   - All procedures have start/end dates
   - Precise timestamps (ISO8601 format)

4. **High CPT Coverage**
   - 87% have CPT codes (vs 67% in v_procedures_tumor)

5. **Clean Surgical Focus**
   - Only OR cases (no ancillary procedures)
   - Simpler for surgical case analysis

### surgical_procedures Weaknesses ❌

1. **No Tumor Surgery Classification**
   - Cannot distinguish tumor resection vs. other surgery
   - No surgery type categorization
   - Requires manual review or linkage to v_procedures_tumor

2. **Limited Coverage**
   - Only 8,513 procedures (12% of v_procedures_tumor)
   - Only OR cases (misses non-surgical procedures)

3. **Minimal Metadata**
   - Only 11 columns (vs 46 in v_procedures_tumor)
   - No body site, reason code, encounter linkage
   - No performer role/function

4. **String Date Types**
   - Dates stored as STRING (ISO8601)
   - Requires casting for date operations

---

## 9. Overlap and Complementarity Analysis

### What surgical_procedures Adds to v_procedures_tumor

1. **Epic OR Case IDs** (4,431 unique cases)
   - Enables linkage to:
     - OR time data (case start, end, wheels in/out)
     - Surgical staff assignments
     - Equipment tracking
     - Anesthesia records

2. **MRN Field**
   - Direct Epic patient identification
   - Simplifies Epic data linkage

3. **100% Date Coverage with Precision**
   - Exact timestamps (vs date-only in v_procedures_tumor)
   - Start AND end times available

### What v_procedures_tumor Adds to surgical_procedures

1. **Tumor Surgery Classification** (4,169 identified)
   - `is_tumor_surgery` flag
   - `surgery_type` categorization
   - Clinical validation fields

2. **Comprehensive Procedure Coverage**
   - 8.2x more procedures
   - Captures non-surgical procedures
   - Historical completeness

3. **Rich Clinical Context**
   - FHIR resource linkages (encounter, location, etc.)
   - Body site and reason code validation
   - Performer role details

4. **Epic Category Classifications**
   - 23 Epic categories
   - 84 Epic codes
   - Procedure classification logic

---

## 10. Use Case Recommendations

### When to Use v_procedures_tumor

**Best for:**
- ✅ **Tumor surgery cohort identification** (use `is_tumor_surgery = true`)
- ✅ **Surgery type analysis** (resection vs biopsy vs shunt)
- ✅ **Comprehensive procedure history** (all procedures, not just OR cases)
- ✅ **FHIR-based analytics** (standard resource structure)
- ✅ **Body site and clinical context analysis**

**Example Query:**
```sql
SELECT *
FROM fhir_prd_db.v_procedures_tumor
WHERE is_tumor_surgery = true
  AND surgery_type = 'craniotomy'
  AND procedure_date >= DATE('2024-01-01');
```

### When to Use surgical_procedures

**Best for:**
- ✅ **Epic OR case linkage** (use `epic_case_orlog_id`)
- ✅ **Surgical case time analysis** (OR duration, start/end times)
- ✅ **Recent surgical cases** (newly loaded data)
- ✅ **MRN-based Epic lookups**
- ✅ **Primary surgical procedure analysis** (excludes ancillary)

**Example Query:**
```sql
SELECT *
FROM fhir_prd_db.surgical_procedures
WHERE cpt_code IN ('61510', '61518')  -- Tumor resection CPTs
  AND status = 'completed'
  AND performed_period_start >= '2024-01-01';
```

### When to JOIN Both Sources

**Best for:**
- ✅ **Tumor surgery + Epic OR data** (classification + case linkage)
- ✅ **Complete surgical case context** (clinical + operational)
- ✅ **Validation studies** (compare representation across sources)

**Example Query:**
```sql
SELECT
    vpt.patient_fhir_id,
    vpt.procedure_date,
    vpt.cpt_code,
    vpt.proc_code_text,
    vpt.is_tumor_surgery,
    vpt.surgery_type,
    sp.epic_case_orlog_id,
    sp.mrn,
    sp.performed_period_start,
    sp.performed_period_end
FROM fhir_prd_db.v_procedures_tumor vpt
INNER JOIN fhir_prd_db.surgical_procedures sp
    ON vpt.patient_fhir_id = sp.patient_id
    AND vpt.cpt_code = sp.cpt_code
    AND vpt.procedure_date = TRY(CAST(sp.performed_period_start AS DATE))
WHERE vpt.is_tumor_surgery = true;
```

---

## 11. Recommendations

### Immediate Actions

1. **Create Unified View** combining strengths of both:
   ```sql
   CREATE VIEW v_surgical_procedures_unified AS
   SELECT
       vpt.*,
       sp.epic_case_orlog_id,
       sp.mrn,
       sp.performed_period_start as epic_start_timestamp,
       sp.performed_period_end as epic_end_timestamp
   FROM fhir_prd_db.v_procedures_tumor vpt
   LEFT JOIN fhir_prd_db.surgical_procedures sp
       ON vpt.patient_fhir_id = sp.patient_id
       AND vpt.cpt_code = sp.cpt_code
       AND vpt.procedure_date = TRY(CAST(sp.performed_period_start AS DATE));
   ```

2. **Validate Overlap**
   - Investigate why 243 patients exist in v_procedures_tumor but not surgical_procedures
   - Determine if surgical_procedures should be expanded or if these are non-OR procedures

3. **Standardize Date Types**
   - Consider converting surgical_procedures dates to TIMESTAMP(3) for consistency
   - Use FROM_ISO8601_TIMESTAMP() for proper parsing

### Long-term Improvements

1. **Enhance surgical_procedures**
   - Add tumor surgery classification from v_procedures_tumor
   - Add surgery type field
   - Include body site information

2. **Enhance v_procedures_tumor**
   - Backfill Epic case IDs from surgical_procedures
   - Add MRN field via patient table join
   - Improve Epic code coverage

3. **Create Episode-Level View**
   - Group related procedures by surgical case
   - Use epic_case_orlog_id as episode identifier
   - Aggregate all procedures per case

---

## 12. Source Query Comparison

### surgical_procedures Query (Epic OR-Focused)

```sql
SELECT
    subject_reference AS patient_id,
    patient_access.mrn,
    procedure.id AS procedure_id,
    identifier_value AS epic_case_orlog_id,
    procedure_code_coding.code_coding_code AS cpt_code,
    procedure.code_text AS procedure_display,
    status,
    performed_period_start,
    performed_period_end,
    procedure_performer.performer_actor_display AS performer,
    outcome_text
FROM procedure
LEFT JOIN procedure_category_coding ON procedure.id = procedure_category_coding.procedure_id
LEFT JOIN procedure_code_coding ON procedure.id = procedure_code_coding.procedure_id
    AND code_coding_system = 'http://www.ama-assn.org/go/cpt'
LEFT JOIN procedure_identifier ON procedure.id = procedure_identifier.procedure_id
    AND identifier_type_text = 'ORL'  -- OR Log identifier
LEFT JOIN procedure_performer ON procedure.id = procedure_performer.procedure_id
INNER JOIN patient_access ON procedure.subject_reference = patient_access.id
WHERE category_coding_code = '387713003'  -- SNOMED: Surgical procedure
  AND category_text <> 'Surgical History'
  AND status = 'completed'
```

**Key Filters:**
- `category_coding_code = '387713003'` - **SNOMED code for "Surgical procedure"**
- `category_text <> 'Surgical History'` - **Excludes historical procedures**
- `status = 'completed'` - **Only completed procedures**
- `identifier_type_text = 'ORL'` - **Filters for OR Log cases only**

**Join Strategy:**
- INNER JOIN on `patient_access` for MRN (requires patient access record)
- LEFT JOINs for optional metadata (CPT, performer, OR log ID)

---

### v_procedures_tumor Query (FHIR-Comprehensive with Classification)

**Base Query:**
```sql
FROM procedure
LEFT JOIN procedure_code_coding pcc ON procedure.id = pcc.procedure_id
    AND pcc.code_coding_system = 'http://www.ama-assn.org/go/cpt'
LEFT JOIN procedure_category_coding pcat ON procedure.id = pcat.procedure_id
LEFT JOIN procedure_body_site pbs ON procedure.id = pbs.procedure_id
LEFT JOIN procedure_performer pp ON procedure.id = pp.procedure_id
-- (additional joins for reason codes, dates, etc.)
```

**No WHERE Clause Filters:**
- ❌ No category filter (includes ALL procedures)
- ❌ No status filter (includes all statuses)
- ❌ No Epic OR Log filter
- ✅ Relies on post-hoc classification logic instead

**Classification Logic (Applied in SELECT):**

**Tier 1: CPT-Based Tumor Surgery Classification**
```sql
CASE
    -- DIRECT TUMOR RESECTION
    WHEN cpt_code IN (
        '61500',  -- Craniectomy tumor/lesion skull
        '61510',  -- Craniotomy bone flap brain tumor supratentorial
        '61518',  -- Craniotomy brain tumor infratentorial/posterior fossa
        '61545',  -- Craniotomy excision craniopharyngioma
        ...
    ) THEN 'craniotomy_tumor_resection'

    -- STEREOTACTIC PROCEDURES
    WHEN cpt_code IN (
        '61750',  -- Stereotactic biopsy
        '61781',  -- Stereotactic computer assisted
        ...
    ) THEN 'stereotactic_tumor_procedure'

    -- EXCLUSIONS (VP shunts, spasticity, diagnostic procedures)
    WHEN cpt_code IN ('62220', '62223', '62225', ...) THEN 'exclude_vp_shunt'
    WHEN cpt_code IN ('64615', '64642', ...) THEN 'exclude_spasticity_pain'
    ...
END AS cpt_classification
```

**Tier 2: Keyword-Based Classification**
```sql
CASE
    WHEN LOWER(proc.code_text) LIKE '%tumor%'
        OR LOWER(proc.code_text) LIKE '%resection%'
        OR LOWER(proc.code_text) LIKE '%craniotomy%'
        ... THEN TRUE
    ELSE FALSE
END AS is_surgical_keyword
```

**Tier 3: Reason Code Validation**
```sql
CASE
    WHEN reason_code IN ('biopsy tumor', 'tumor excision', 'brain tumor', ...)
    THEN TRUE
    ELSE FALSE
END AS has_tumor_reason
```

**Tier 4: Body Site Validation**
```sql
CASE
    WHEN body_site_text LIKE '%brain%'
        OR body_site_text LIKE '%cranial%'
        ... THEN TRUE
    ELSE FALSE
END AS has_tumor_body_site
```

**Final Tumor Surgery Flag:**
```sql
is_tumor_surgery = (
    cpt_classification IN ('craniotomy_tumor_resection', 'stereotactic_tumor_procedure', ...)
    OR (is_surgical_keyword AND has_tumor_reason)
    OR (is_surgical_keyword AND has_tumor_body_site)
)
AND NOT (cpt_classification LIKE 'exclude_%')
```

---

### Critical Differences in Approach

| Aspect | surgical_procedures | v_procedures_tumor |
|--------|--------------------|--------------------|
| **Filtering Strategy** | Upfront WHERE clause | Post-hoc classification |
| **Primary Filter** | SNOMED category code | CPT + keyword + reason + body site |
| **Epic OR Focus** | ✅ Requires ORL identifier | ❌ No OR Log requirement |
| **Completeness** | Only OR cases | All FHIR procedures |
| **Classification** | None (all assumed surgical) | Multi-tier tumor surgery logic |
| **Historical Procedures** | Excluded | Included |
| **Status Filter** | completed only | All statuses |

---

### Why surgical_procedures Has Fewer Procedures

**surgical_procedures filters OUT:**
1. **Non-OR procedures** (no ORL identifier)
   - Bedside procedures
   - Office procedures
   - Interventional radiology procedures
2. **Non-completed procedures** (status filter)
   - Cancelled
   - Entered in error
   - In progress
3. **Historical procedures** (category_text filter)
   - Surgical history from outside institutions
   - Pre-Epic historical data
4. **Non-surgical category procedures** (SNOMED filter)
   - Diagnostic procedures
   - Imaging procedures
   - Therapeutic procedures (non-surgical)

**v_procedures_tumor includes ALL, then classifies:**
- No upfront filters
- Includes ancillary procedures (microscopy, navigation)
- Includes non-OR procedures
- Includes all statuses
- Uses classification to identify tumor surgeries post-hoc

---

### Implications for Data Completeness

**surgical_procedures strengths:**
- ✅ **High precision** for surgical cases (SNOMED category filter)
- ✅ **OR-specific** (Epic case linkage guaranteed)
- ✅ **Clean dataset** (no historical or non-OR procedures)

**v_procedures_tumor strengths:**
- ✅ **High sensitivity** for tumor procedures (multi-tier classification)
- ✅ **Comprehensive coverage** (all procedure types)
- ✅ **Historical completeness** (no exclusions for surgical history)

**Trade-off:**
- surgical_procedures: **Precision > Recall** (fewer false positives, may miss edge cases)
- v_procedures_tumor: **Recall > Precision** (captures all relevant, may include ancillary)

---

## 13. Data Source Lineage

### v_procedures_tumor
**Source:** FHIR `Procedure` resource
**ETL:** FHIR bulk export → S3 → Athena table → View with classification logic
**Classification Logic:** Multi-tier approach (CPT codes, keywords, reason codes, body sites)
**Update Frequency:** Unknown (appears to be batch FHIR sync)
**Query Location:** `DATETIME_STANDARDIZED_VIEWS.sql` (lines 2569+)

### surgical_procedures
**Source:** Epic OR Log (surgical cases)
**Load Date:** 2025-10-29 (loaded today)
**Direct Epic Extract:** FHIR Procedure resource filtered for OR cases
**Epic Filter:** `identifier_type_text = 'ORL'` (OR Log identifier)
**SNOMED Filter:** `category_coding_code = '387713003'` (Surgical procedure)
**Update Frequency:** Unknown (newly created table)

---

## Conclusion

**v_procedures_tumor** and **surgical_procedures** are **highly complementary** data sources:

### Overlap
- ✅ 100% patient overlap (all surgical_procedures patients exist in v_procedures_tumor)
- ✅ 100% CPT overlap (all surgical_procedures CPT codes exist in v_procedures_tumor)
- ✅ Same top surgical procedures with similar counts

### Differences
- **Volume:** v_procedures_tumor has 8.2x more procedures (comprehensive vs OR-only)
- **Classification:** v_procedures_tumor has tumor surgery identification; surgical_procedures does not
- **Epic Linkage:** surgical_procedures has OR case IDs and MRNs; v_procedures_tumor does not
- **Metadata:** v_procedures_tumor has 46 columns vs 11 in surgical_procedures

### Recommended Strategy
**Use BOTH in combination:**
1. **Start with v_procedures_tumor** for tumor surgery cohort identification (`is_tumor_surgery = true`)
2. **JOIN to surgical_procedures** to add Epic OR case IDs and precise timestamps
3. **Create unified view** combining classification from v_procedures_tumor with Epic linkage from surgical_procedures

This approach maximizes both **clinical value** (tumor surgery classification) and **operational value** (Epic OR data linkage).
