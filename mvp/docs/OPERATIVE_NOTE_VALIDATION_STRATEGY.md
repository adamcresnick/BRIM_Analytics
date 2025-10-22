# Operative Note Validation Strategy

**Date:** 2025-10-22
**Purpose:** Ensure every tumor surgery event has an operative report identified

---

## Overview

To ensure data completeness in the multi-source abstraction workflow, we need to validate that every tumor surgery event identified from `v_procedures_tumor` has a corresponding operative note document from `v_binary_files`.

## Validation Tools Created

### 1. SQL Validation Query
**File:** [`scripts/validate_surgery_operative_note_coverage.sql`](../scripts/validate_surgery_operative_note_coverage.sql)

**Purpose:** Comprehensive SQL query for Athena that:
- Identifies all tumor surgery events
- Attempts to match each surgery to an operative note using 3 strategies
- Reports coverage statistics and gaps

**Matching Strategies (in order of preference):**

1. **EXACT MATCH (Preferred)**: `dr_context_period_start` = surgery date
   - Most reliable method
   - Uses DocumentReference.context.period.start field
   - This field contains the actual procedure datetime

2. **NEAR MATCH (Fallback)**: `dr_context_period_start` ± 3 days from surgery
   - Accounts for minor date discrepancies
   - Still uses the reliable context_period field

3. **DR_DATE MATCH (Last Resort)**: `dr_date` ± 7 days from surgery
   - Uses document creation date instead of procedure date
   - Less reliable but may catch edge cases
   - Note: Many "External Operative Note" documents have NULL dr_date

**Output:**
- Coverage summary (total surgeries vs matched)
- Match type breakdown
- List of all matched surgeries with match details
- List of unmatched surgeries with gap analysis

### 2. Python Validation Script
**File:** [`scripts/validate_surgery_operative_note_coverage.py`](../scripts/validate_surgery_operative_note_coverage.py)

**Purpose:** Programmatic validation with detailed reporting

**Usage:**
```bash
# Validate single patient
python3 scripts/validate_surgery_operative_note_coverage.py --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3

# Validate all patients (cohort-wide analysis)
python3 scripts/validate_surgery_operative_note_coverage.py --all-patients
```

**Features:**
- Real-time Athena query execution
- Per-patient detailed analysis
- Cohort-wide coverage statistics
- Gap identification and categorization

---

## Current Status & Findings

### Test Patient: `e4BwD8ZYDBccepXcJ.Ilo3w3`

**Tumor Surgeries Identified:** 9 procedures from `v_procedures_tumor`

**Operative Notes Available:** Multiple documents in `v_binary_files` with types:
- "OP Note - Complete (Template or Full Dictation)"
- "OP Note - Brief (Needs Dictation)"
- "Operative Record"
- "Anesthesia Postprocedure Evaluation"

**Previous Coverage (OLD matching logic):**
- **0/9 surgeries matched** (0% coverage)
- Reason: Used `dr_date` field with ±7 day window
- Problem: `dr_date` is NULL for many "External Operative Note" documents

**Expected Coverage (NEW matching logic):**
- **9/9 surgeries should match** (100% coverage expected)
- Reason: Uses `dr_context_period_start` with exact date match
- Validation: Currently running workflow (bash ID 6ed671) will confirm

---

## Workflow Integration

The multi-source abstraction workflow ([`run_full_multi_source_abstraction.py`](../scripts/run_full_multi_source_abstraction.py)) now uses the corrected matching logic:

**Lines 912-936:**
```python
op_note_query = f"""
    SELECT
        document_reference_id,
        binary_id,
        dr_context_period_start,
        dr_type_text
    FROM v_binary_files
    WHERE patient_fhir_id = '{athena_patient_id}'
        AND (
            dr_type_text LIKE 'OP Note%'
            OR dr_type_text = 'Operative Record'
            OR dr_type_text = 'Anesthesia Postprocedure Evaluation'
        )
        AND DATE(dr_context_period_start) = DATE '{proc_date_str}'  # EXACT date match
    ORDER BY
        CASE
            WHEN dr_type_text LIKE '%Complete%' THEN 1  # Prefer complete notes
            WHEN dr_type_text = 'Anesthesia Postprocedure Evaluation' THEN 2
            WHEN dr_type_text LIKE '%Brief%' THEN 3
            ELSE 4
        END
    LIMIT 1
"""
```

**Key Change:**
- **OLD:** `ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE '{proc_date_str}')) <= 7`
- **NEW:** `DATE(dr_context_period_start) = DATE '{proc_date_str}'`

---

## Recommended Validation Workflow

### For Single Patient Validation:

1. **Run validation script:**
   ```bash
   cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
   python3 scripts/validate_surgery_operative_note_coverage.py --patient-id <patient_fhir_id>
   ```

2. **Review output:**
   - Check coverage percentage
   - Identify unmatched surgeries
   - Analyze gap reasons

3. **Investigate gaps:**
   - For unmatched surgeries, check if operative notes exist but have wrong dates
   - Verify surgery dates in `v_procedures_tumor`
   - Check document dates in `v_binary_files`

### For Cohort-Wide Validation:

1. **Run cohort analysis:**
   ```bash
   python3 scripts/validate_surgery_operative_note_coverage.py --all-patients
   ```

2. **Analyze results:**
   - Overall coverage percentage
   - Patients with gaps
   - Common gap patterns

3. **Identify systematic issues:**
   - Data quality problems (missing documents)
   - Matching logic edge cases
   - View construction issues

---

## Known Data Quality Issues

### 1. External Operative Notes Missing Dates
**Scope:** 367 documents across 116 patients
**Issue:** `dr_date` field is NULL
**Impact:** Cannot match using dr_date-based logic
**Solution:** Use `dr_context_period_start` instead (IMPLEMENTED)

### 2. S3 File Availability
**Scope:** 24/104 imaging PDFs for test patient
**Issue:** FHIR metadata exists but files missing from S3
**Impact:** Cannot extract text from these documents
**Solution:** Data pipeline investigation required

---

## Future Enhancements

### 1. Automated Validation in Workflow
Add validation check to workflow that:
- Runs after Phase 1 (data query)
- Reports expected vs actual operative note matches
- Warns about potential gaps before starting extraction

### 2. Gap Resolution Logic
For unmatched surgeries:
- Expand search window to ±7 days on context_period
- Try alternate document types (e.g., "Anesthesia Record")
- Flag for manual review

### 3. Coverage Metrics Dashboard
Track over time:
- Per-patient coverage
- Cohort-wide coverage trends
- Most common gap reasons
- Data quality improvements

---

## References

- **Original Operative Note Linkage Strategy:**
  `brim_workflows_individual_fields/extent_of_resection/docs/IMAGING_AND_OPERATIVE_NOTE_LINKAGE_STRATEGY.md`

- **Surgery Event Identification:**
  `v_procedures_tumor` view definition in `DATETIME_STANDARDIZED_VIEWS.sql:1418`

- **Operative Note Documents:**
  `v_binary_files` view queried with specific document types

---

## Change Log

| Date | Change | Author | Reason |
|------|--------|------| -------|
| 2025-10-22 | Changed from `dr_date ±7 days` to `dr_context_period_start exact match` | System | Fix 0% operative note coverage |
| 2025-10-22 | Created validation SQL query and Python script | System | Enable coverage verification |
| 2025-10-22 | Documented known data quality issues | System | Track systematic problems |

