# Guide: Augmenting surgical_procedures Using v_procedures_tumor Analysis

**For:** Data Analyst responsible for surgical_procedures extraction
**Purpose:** Use v_procedures_tumor to identify missing tumor surgeries and enhance surgical_procedures logic

---

## Background

### Current State

| Data Source | Tumor Surgeries | Patients | Approach |
|-------------|-----------------|----------|----------|
| **surgical_procedures** | 3,204 | 1,592 | Epic OR log filtered (upfront WHERE clause) |
| **v_procedures_tumor** | 4,169 | 1,835 | Comprehensive FHIR (post-hoc classification) |
| **GAP** | **~965 procedures** | **243 patients** | Potential missing cases |

### Key Differences

**surgical_procedures filtering:**
```sql
WHERE category_coding_code = '387713003'  -- SNOMED: Surgical procedure
  AND identifier_type_text = 'ORL'         -- Has Epic OR Log ID
  AND proc_status = 'completed'            -- Completed only
```

**v_procedures_tumor filtering:**
- No upfront WHERE clause
- Includes orders, history, OR cases
- Multi-tier tumor classification logic
- Post-hoc filtering via annotation columns

---

## Step 1: Run the Discovery Query

### Query Location
`athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql`

### Deploy & Execute
```bash
/tmp/run_query.sh athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql
```

### What It Returns

The query identifies tumor surgeries in v_procedures_tumor that are NOT in surgical_procedures, with:

**Key Columns:**
- `patient_fhir_id` - Patient identifier
- `procedure_date` - When procedure occurred
- `procedure_code` - CPT/Epic code
- `coding_system` - CPT, EAP, etc. (decoded via OID)
- `epic_or_log_id` - Epic OR Log ID (if exists)
- `proc_category_text` - Ordered Procedures, Surgical History, or Surgical Procedures
- `snomed_category_code` - SNOMED code (387713003 = surgical procedure)
- `reason_missing_from_surgical_procedures` - Root cause analysis
- `recommendation` - Should this be added?

---

## Step 2: Review Results by Recommendation

### ✅ High Priority: Review to Add

**Filter for:**
```sql
WHERE recommendation LIKE '%REVIEW TO ADD%'
```

**Characteristics:**
- Has Epic OR Log ID
- Status = 'completed'
- Should be in surgical_procedures

**Action:**
1. Review a sample of these cases in Epic Hyperspace
2. Verify they are legitimate OR cases
3. Investigate why surgical_procedures missed them:
   - Missing SNOMED category code?
   - Different SNOMED code?
   - Epic OR Log ID format issue?
   - Other filtering logic?

**Example Investigation:**
```sql
-- Look at one specific case
SELECT *
FROM fhir_prd_db.v_procedures_tumor
WHERE procedure_fhir_id = '<example_id>'
  AND is_tumor_surgery = TRUE
  AND in_surgical_procedures_table = FALSE;

-- Check the FHIR procedure_category_coding table
SELECT *
FROM fhir_prd_db.procedure_category_coding
WHERE procedure_id = '<example_id>';

-- Check the procedure_identifier table
SELECT *
FROM fhir_prd_db.procedure_identifier
WHERE procedure_id = '<example_id>'
  AND identifier_type_text = 'ORL';
```

### ⚡ Medium Priority: Needs Review

**Filter for:**
```sql
WHERE recommendation LIKE '%REVIEW%'
  AND recommendation NOT LIKE '%DO NOT ADD%'
```

**Characteristics:**
- Surgical history but marked as performed
- High confidence tumor surgery but no OR log
- Edge cases requiring investigation

**Action:**
Review these to determine if they represent:
1. True CHOP OR cases that should be added
2. External procedures that should be excluded
3. Documentation-only entries

### ❌ Low Priority: Do NOT Add

**Filter for:**
```sql
WHERE recommendation LIKE '%DO NOT ADD%'
```

**Characteristics:**
- Procedure orders (never performed)
- Surgical history (external/historical)
- Status = 'not-done'

**Action:**
These are correctly excluded from surgical_procedures. No changes needed.

---

## Step 3: Analyze Root Causes

### Common Reasons Procedures Are Missing

Run the summary section of the query (uncomment the last section):

```sql
-- SUMMARY STATISTICS section
-- Shows count by missing_category
```

**Expected Categories:**

1. **Procedure Orders (Do Not Add)**
   - ~516 procedures
   - These are requisitions, not performed surgeries
   - Correctly excluded

2. **Surgical History (External/Historical)**
   - ~146 procedures (completed)
   - External procedures or historical documentation
   - Review to determine if any are CHOP OR cases

3. **Has Epic OR Log (Should Review)** ⚠️
   - **Most important category**
   - ~43 procedures with OR Log but not in surgical_procedures
   - These likely SHOULD be included

4. **Missing/Wrong SNOMED Category**
   - Procedures without SNOMED code 387713003
   - May need to relax SNOMED filtering

5. **Not Completed Status**
   - Procedures with status != 'completed'
   - Correctly excluded

---

## Step 4: Augment surgical_procedures Logic

Based on your analysis, you may need to update surgical_procedures extraction in one or more ways:

### Option A: Relax SNOMED Category Filtering

**Current:**
```sql
WHERE category_coding_code = '387713003'  -- Only 387713003 (surgical procedure)
```

**Enhanced:**
```sql
WHERE (
    category_coding_code = '387713003'  -- SNOMED: Surgical procedure
    OR category_coding_code IS NULL      -- Allow procedures without SNOMED
)
```

**Consider if:** Many high-confidence tumor surgeries are missing SNOMED codes

### Option B: Include Additional Epic Procedure Categories

**Current:**
```sql
WHERE identifier_type_text = 'ORL'  -- Epic OR Log only
```

**Enhanced:**
```sql
WHERE (
    identifier_type_text = 'ORL'                  -- Epic OR Log
    OR (
        category_text = 'Surgical Procedures'     -- Epic category
        AND status = 'completed'
    )
)
```

**Consider if:** Some surgical procedures don't have OR Log IDs but are valid surgeries

### Option C: Add Tumor-Specific CPT Code Filter

**Enhanced:**
```sql
-- Add CTE with v_procedures_tumor's CPT classification logic
WITH tumor_cpt_codes AS (
    SELECT code_coding_code
    FROM (VALUES
        ('61500'), ('61510'), ('61518'), ('61545'),  -- Tumor resection CPT codes
        ('61750'), ('61751'), ('61781'),             -- Stereotactic procedures
        -- ... (see v_procedures_tumor for full list)
    ) AS t(code_coding_code)
)
SELECT ...
WHERE (
    category_coding_code = '387713003'
    OR code_coding_code IN (SELECT * FROM tumor_cpt_codes)  -- Explicit tumor CPT codes
)
```

**Consider if:** Want to ensure all tumor surgery CPT codes are captured

### Option D: Use v_procedures_tumor Classification

**Most Comprehensive:**
```sql
-- Join to v_procedures_tumor and use its classification
SELECT
    sp.*,
    vpt.is_tumor_surgery,
    vpt.cpt_classification,
    vpt.classification_confidence
FROM surgical_procedures_raw sp
LEFT JOIN fhir_prd_db.v_procedures_tumor vpt
    ON sp.procedure_id = vpt.procedure_fhir_id
WHERE (
    sp.category_coding_code = '387713003'
    OR vpt.is_tumor_surgery = TRUE  -- Use v_procedures_tumor's classification
)
```

**Consider if:** Want to leverage v_procedures_tumor's multi-tier classification logic

---

## Step 5: Test & Validate Changes

### Before Making Changes

1. **Document current counts:**
```sql
SELECT
    COUNT(*) as total_procedures,
    COUNT(DISTINCT mrn) as total_patients,
    SUM(CASE WHEN is_tumor_related THEN 1 ELSE 0 END) as tumor_procedures
FROM fhir_prd_db.surgical_procedures;
```

2. **Export sample of current data for comparison**

### After Making Changes

1. **Compare new counts:**
```sql
-- Should see increase in procedures/patients
SELECT
    COUNT(*) as total_procedures,
    COUNT(DISTINCT mrn) as total_patients,
    SUM(CASE WHEN is_tumor_related THEN 1 ELSE 0 END) as tumor_procedures
FROM fhir_prd_db.surgical_procedures_NEW;
```

2. **Identify what was added:**
```sql
-- New procedures in updated version
SELECT new.*
FROM surgical_procedures_NEW new
LEFT JOIN surgical_procedures old ON new.procedure_id = old.procedure_id
WHERE old.procedure_id IS NULL
ORDER BY new.procedure_date DESC
LIMIT 100;
```

3. **Validate tumor classification:**
```sql
-- Ensure new procedures are actually tumor-related
SELECT
    procedure_name,
    cpt_code,
    is_tumor_related,
    COUNT(*) as cnt
FROM surgical_procedures_NEW new
LEFT JOIN surgical_procedures old ON new.procedure_id = old.procedure_id
WHERE old.procedure_id IS NULL
GROUP BY 1, 2, 3
ORDER BY cnt DESC;
```

---

## Step 6: Document Changes

Update surgical_procedures documentation with:

1. **What changed:**
   - New filtering logic
   - Additional procedures captured
   - Rationale for changes

2. **Impact:**
   - Before/after counts
   - New patient coverage
   - New tumor surgeries identified

3. **Validation:**
   - Sample cases reviewed
   - False positive rate
   - Data quality checks

---

## Common Scenarios

### Scenario 1: Found 43 cases with OR Log but not in surgical_procedures

**Investigation:**
```sql
-- Check these specific cases
SELECT
    patient_fhir_id,
    procedure_date,
    proc_code_text,
    epic_or_log_id,
    category_coding_code,
    proc_status
FROM fhir_prd_db.v_procedures_tumor
WHERE is_tumor_surgery = TRUE
  AND epic_or_log_id IS NOT NULL
  AND in_surgical_procedures_table = FALSE
ORDER BY procedure_date DESC;
```

**Likely Causes:**
- Missing SNOMED category code in FHIR
- Different SNOMED code (not 387713003)
- Status not exactly 'completed' (e.g., 'completed-amended')

**Solution:** Relax SNOMED or status filtering

### Scenario 2: Many high-confidence tumor surgeries without OR Log

**Investigation:**
```sql
SELECT
    proc_category_text,
    procedure_source_type,
    COUNT(*) as cnt
FROM fhir_prd_db.v_procedures_tumor
WHERE is_tumor_surgery = TRUE
  AND epic_or_log_id IS NULL
  AND classification_confidence >= 90
GROUP BY 1, 2
ORDER BY cnt DESC;
```

**Likely Findings:**
- Most are "Ordered Procedures" (don't add)
- Some are "Surgical History" (external procedures)
- Few are actual surgical procedures without OR Log

**Solution:** Review "Surgical Procedures" category cases to see if they should be included

### Scenario 3: Tumor surgeries with different CPT codes

**Investigation:**
```sql
-- What CPT codes are in v_procedures_tumor but not surgical_procedures?
WITH vpt_cpts AS (
    SELECT DISTINCT pcc_code_coding_code as cpt
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = TRUE
      AND pcc_coding_system_code = 'CPT'
),
sp_cpts AS (
    SELECT DISTINCT cpt_code as cpt
    FROM fhir_prd_db.surgical_procedures
    WHERE is_tumor_related = TRUE
)
SELECT
    v.cpt,
    COUNT(*) as usage_in_vpt
FROM vpt_cpts v
LEFT JOIN sp_cpts s ON v.cpt = s.cpt
WHERE s.cpt IS NULL
GROUP BY v.cpt
ORDER BY usage_in_vpt DESC;
```

**Solution:** Review these CPT codes and add to tumor classification logic if legitimate

---

## Validation Checklist

Before deploying changes to surgical_procedures:

- [ ] Identified root causes for missing procedures
- [ ] Reviewed sample of high-priority cases in Epic
- [ ] Tested proposed filtering changes
- [ ] Compared before/after counts
- [ ] Validated new procedures are actually tumor-related
- [ ] Checked for false positives
- [ ] Documented changes and rationale
- [ ] Reviewed with clinical team if needed
- [ ] Updated surgical_procedures documentation

---

## Key Insights from v_procedures_tumor

### Multi-Tier Tumor Classification

v_procedures_tumor uses 4 tiers to classify tumor surgeries:

1. **Tier 1: CPT Code Classification** (highest confidence)
   - Specific CPT codes: 61500, 61510, 61518, etc.
   - Classification types: definite_tumor, tumor_support, ambiguous, exclude

2. **Tier 2: Keyword-Based**
   - Procedure text contains: "craniotomy tumor", "tumor resection", etc.
   - Exclude keywords: "shunt", "nerve block", "lumbar puncture"

3. **Tier 3: Reason Code Validation**
   - Reason codes: "brain tumor", "tumor excision", etc.

4. **Tier 4: Body Site Validation**
   - Body sites: "Brain", "Skull", "Cranial", etc.

**Consider:** Adopting similar multi-tier logic for surgical_procedures

### Classification Confidence Scores

v_procedures_tumor assigns confidence scores (1-100):
- **90-100:** Definite tumor surgery (CPT-based, validated with reason codes)
- **70-89:** High confidence (tumor-specific keywords + validation)
- **50-69:** Medium confidence (ambiguous CPT + validation)
- **<50:** Lower confidence (generic surgical keywords)

**Consider:** Using confidence scores to filter surgical_procedures

---

## Questions to Ask

1. **SNOMED Category:**
   - How many tumor surgeries are missing SNOMED code 387713003?
   - Should we relax this requirement?

2. **Epic OR Log:**
   - Are all OR cases guaranteed to have OR Log IDs?
   - Do ambulatory/outpatient surgeries have OR Logs?

3. **Procedure Status:**
   - Are there status values other than 'completed' that should be included?
   - E.g., 'completed-amended', 'in-progress' (for ongoing cases)

4. **Epic Categories:**
   - Beyond 'Surgical Procedures', are there other Epic categories to consider?
   - Check: proc_category_text in FHIR

5. **Clinical Validation:**
   - Should clinical team review sample of "should add" cases?
   - Acceptable false positive rate?

---

## Resources

- **Analysis Query:** `athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql`
- **v_procedures_tumor Docs:** `documentation/V_PROCEDURES_TUMOR_DOCUMENTATION.md`
- **Comparison Analysis:** `documentation/PROCEDURES_COMPARISON_ANALYSIS.md`
- **Current View:** `athena_views/views/v_procedures_tumor` (in DATETIME_STANDARDIZED_VIEWS.sql)

---

## Support

Questions? Discuss with:
- Data engineering team (view logic)
- Clinical team (tumor surgery definitions)
- Epic team (OR Log ID, SNOMED categories)

---

**Last Updated:** 2025-10-29
**Created By:** BRIM Analytics Team
