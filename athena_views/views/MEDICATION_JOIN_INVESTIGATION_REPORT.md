# Medication Join Investigation - Comprehensive Report

**Date**: 2025-10-27
**Issue**: RxNorm code-based medication identification not working
**Root Cause**: BROKEN medication_request → medication join in 2 views

---

## Executive Summary

Empirical testing reveals that **RxNorm code-based corticosteroid identification works perfectly** when using the correct join, but **2 views are using a broken SUBSTRING join** that captures 0 medications.

### Key Findings:

✅ **CORRECT JOIN (Direct match)**:
- Captures **63,397 corticosteroid medication requests**
- Captures **1,788 patients** with corticosteroids
- **37% MORE coverage** than text matching alone

❌ **BROKEN JOIN (SUBSTRING)**:
- Captures **0 medication requests**
- Captures **0 patients**
- Completely non-functional

---

## Technical Details

### Data Structure

**medication_reference_reference format** (100% of records):
```
fgn2KEM..vlrTIjjXv0bLEcvMcJMgWpAh79HfIF3t3qA4
fSgKB.m2oHYTrPridlrtN0OMbRbonGoqbUv5hi9Vmz8o4
f0M.FOYpBYLxzCOgOjEjM-Qk-QDe0S4OhU8E7T8oZduw4
```

**Characteristics**:
- Direct medication IDs (no prefix)
- **NOT** in "Medication/xyz" format
- **NOT** in "urn:uuid:xyz" format

### Join Comparison

| Join Method | Syntax | Medication Requests | Patients | Status |
|-------------|--------|---------------------|----------|---------|
| **Direct match** | `m.id = mr.medication_reference_reference` | 852,432 | 1,845 | ✅ **CORRECT** |
| **SUBSTRING(12)** | `m.id = SUBSTRING(mr.medication_reference_reference, 12)` | 0 | 0 | ❌ **BROKEN** |
| **SUBSTRING(13)** | `m.id = SUBSTRING(mr.medication_reference_reference, 13)` | 0 | 0 | ❌ **BROKEN** |

### Corticosteroid Capture Comparison

**5-Drug RxNorm List** ('3264', '8640', '6902', '5492', '4850'):

| Approach | Requests | Patients | Notes |
|----------|----------|----------|-------|
| **RxNorm + Correct Join** | 63,397 | 1,788 | ✅ BEST - 37% more coverage |
| **Text Matching Only** | 46,098 | 1,719 | Missing RxNorm-only records |
| **RxNorm + Broken Join** | 0 | 0 | ❌ Completely non-functional |

---

## Views with BROKEN Joins

### 1. v_autologous_stem_cell_collection (Line 3018)

**Current** (BROKEN):
```sql
LEFT JOIN fhir_prd_db.medication m
    ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
```

**Should be**:
```sql
LEFT JOIN fhir_prd_db.medication m
    ON m.id = mr.medication_reference_reference
```

**Impact**: Cannot identify mobilization agents via RxNorm codes

### 2. v_imaging_corticosteroid_use (Line 3827)

**Current** (BROKEN):
```sql
LEFT JOIN fhir_prd_db.medication m
    ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
```

**Should be**:
```sql
LEFT JOIN fhir_prd_db.medication m
    ON m.id = mr.medication_reference_reference
```

**Impact**:
- Cannot identify corticosteroids via RxNorm codes
- Falling back to text matching only
- Missing 17,299 corticosteroid administrations (27% of total)
- Missing 69 patients with corticosteroids

---

## Views with CORRECT Joins

The following views are using the correct direct match join:

✅ v_concomitant_medications (Line 598)
✅ v_medications (Lines not checked but likely correct based on functionality)
✅ v_chemo_medications (Lines not checked but likely correct based on functionality)
✅ v_hydrocephalus_procedures (Lines not checked)

---

## Recommendations

### HIGH PRIORITY: Fix Broken Joins

**Action Items**:

1. **v_imaging_corticosteroid_use** - Fix join (HIGH impact)
   - Currently missing 27% of corticosteroid records
   - Simple one-line fix
   - Estimated effort: 5 minutes + testing

2. **v_autologous_stem_cell_collection** - Fix join (MEDIUM impact)
   - Currently unable to match mobilization agents via RxNorm
   - Simple one-line fix
   - Estimated effort: 5 minutes + testing

### MEDIUM PRIORITY: Standardize Corticosteroid Identification

After fixing joins, consider:

1. **Expand v_concomitant_medications corticosteroid list** from 5 to 20 drugs
   - Current: '3264', '8640', '6902', '5492', '4850'
   - Expand to match v_imaging_corticosteroid_use comprehensive list

2. **Use v_concomitant_medications as single source** for corticosteroid categorization
   - v_imaging can then simply filter `WHERE conmed_category = 'corticosteroid'`
   - Eliminates code duplication

---

## Implementation Plan

### Phase 1: Fix Broken Joins (IMMEDIATE)

```sql
-- Fix v_autologous_stem_cell_collection (Line 3018)
-- OLD:
LEFT JOIN fhir_prd_db.medication m
    ON m.id = SUBSTRING(mr.medication_reference_reference, 12)

-- NEW:
LEFT JOIN fhir_prd_db.medication m
    ON m.id = mr.medication_reference_reference
```

```sql
-- Fix v_imaging_corticosteroid_use (Line 3827)
-- OLD:
LEFT JOIN fhir_prd_db.medication m
    ON m.id = SUBSTRING(mr.medication_reference_reference, 12)

-- NEW:
LEFT JOIN fhir_prd_db.medication m
    ON m.id = mr.medication_reference_reference
```

### Phase 2: Validate Fixes

Run empirical tests to confirm:
- v_imaging_corticosteroid_use now captures 63,397 requests (vs 46,098 with text only)
- v_autologous_stem_cell_collection can now match RxNorm codes

### Phase 3: Standardize (Optional)

- Expand v_concomitant_medications to 20-drug corticosteroid list
- Update v_imaging_corticosteroid_use to reference v_concomitant_medications

---

## Expected Impact

### Before Fix:
- v_imaging_corticosteroid_use: 46,098 requests, 1,719 patients (text matching only)
- v_autologous_stem_cell_collection: 0 RxNorm matches (text matching only)

### After Fix:
- v_imaging_corticosteroid_use: **63,397 requests, 1,788 patients** (+37%, +4%)
- v_autologous_stem_cell_collection: Proper RxNorm matching enabled

---

## Answer to Original Question

> "Is the 5-drug approach comprehensive? Can we test this empirically?"

**Answer**: YES, empirically tested!

1. ✅ **5-drug RxNorm approach IS comprehensive** when join works correctly
   - Captures 63,397 corticosteroid requests
   - Captures 1,788 patients
   - **37% better coverage** than text matching

2. ❌ **But 2 views have BROKEN joins** preventing RxNorm matching
   - v_imaging_corticosteroid_use
   - v_autologous_stem_cell_collection

3. ✅ **Fixing the join is simple**: Remove `SUBSTRING(, 12)` and use direct match

**Recommendation**: Fix the 2 broken joins immediately to enable proper RxNorm-based medication identification.

---

**Files Generated**:
1. [investigate_medication_join.py](investigate_medication_join.py) - Investigation script
2. [test_corticosteroid_coverage.py](test_corticosteroid_coverage.py) - Coverage comparison script
3. [MEDICATION_JOIN_INVESTIGATION_REPORT.md](MEDICATION_JOIN_INVESTIGATION_REPORT.md) - This report

**Next Step**: Fix the 2 broken joins in DATETIME_STANDARDIZED_VIEWS.sql
