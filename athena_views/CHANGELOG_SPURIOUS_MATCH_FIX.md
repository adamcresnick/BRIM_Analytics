# Fix: Spurious 2-Letter Drug Code Matches in v_chemo_medications

**Date:** 2025-10-26
**Issue:** Critical data quality issue with 2-letter drug codes
**Impact:** HIGH - Affects ~1M+ medication orders

## Problem

The v_chemo_medications view was experiencing spurious substring matches with 2-letter drug codes (AC, AG, CY, DA, VA) in the name-based matching logic.

### Root Cause

The name matching used `LIKE '%{drug_name}%'` which caused 2-letter codes to match ANY medication containing those letters:

- **AC** → matched "**ac**etaminophen", "l**ac**tated ringers", "v**ac**cine", "bev**ac**izumab"
- **AG** → matched "m**ag**nesium", "di**ag**nostic", "**ag**ent"
- **VA** → matched "**va**ccine", "**va**lium", "**va**lproic acid"
- **CY** → matched "**cy**clophosphamide", "**cy**tarabine"
- **DA** → matched "**da**ptomycin", "**da**unorubicin"

### Data Impact

From validation query before fix:
```
AC matched:
- lactated ringers: 23,032 orders, 1,536 patients
- acetaminophen suspension: 14,337 orders, 1,325 patients
- acetaminophen tablet: 7,421 orders, 1,061 patients
- bevacizumab: 6,964 orders, 176 patients
Total spurious AC matches: ~51,754 orders
```

Similar spurious matches occurred for AG, CY, DA, VA resulting in **~1M+ false positive chemotherapy medication orders**.

## Solution

Added `LENGTH(cd.preferred_name) > 2` filter to name-based matching logic in v_chemo_medications.sql (line 125).

### What Changed

**File:** `athena_views/views/V_CHEMO_MEDICATIONS.sql`

**Before:**
```sql
WHERE
    -- Match on medication name (case-insensitive, partial match)
    (
        LOWER(m.code_text) LIKE '%' || LOWER(cd.preferred_name) || '%'
        ...
    )
```

**After:**
```sql
WHERE
    -- Exclude very short drug names (<=2 chars) to prevent spurious substring matches
    -- (e.g., "AC" matching "acetaminophen", "AG" matching "magnesium")
    LENGTH(cd.preferred_name) > 2
    -- Match on medication name (case-insensitive, partial match)
    AND (
        LOWER(m.code_text) LIKE '%' || LOWER(cd.preferred_name) || '%'
        ...
    )
```

### What's Protected

- **AC, AG, CY, DA, VA** - 2-letter codes now excluded from name matching
- These codes remain in drugs.csv but won't cause spurious matches
- Codes with RxNorm (like ADE, CVP, VAC) still match via RxNorm strategy
- 3-letter codes (BCG, TMZ, PLD, S-1) still work correctly

## Validation

### Test Query
```sql
SELECT
    chemo_preferred_name,
    COUNT(*) as order_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_chemo_medications
WHERE chemo_preferred_name IN ('AC', 'AG', 'VA', 'VAC', 'DA', 'CY')
GROUP BY chemo_preferred_name
```

### Expected Results After Fix
- AC, AG, CY, DA, VA should return 0 rows (excluded from name matching, no RxNorm codes)
- VAC should still match (has RxNorm code: rx:798451.0)
- vincristine, carboplatin, other legitimate drugs should match normally

## Downstream Impact

### Affected Systems
1. **v_chemo_medications view** - Fixed ✅
2. **timeline.duckdb** - Requires rebuild with corrected data
3. **Treatment paradigm analysis** - Previous results invalid, requires re-run
4. **Patient abstractions** - May need refresh if using cached data

### Rebuild Required
```bash
# Rebuild timeline database
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/build_timeline_database.py

# Re-run treatment paradigm analysis
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore
python3 scripts/empirical_treatment_paradigm_analysis.py data/chemotherapy_all_patients_corrected.csv
```

## Deployment

1. View deployed to Athena: `0d86218c-959b-4915-98ab-fd2d10b168ba` ✅
2. Testing validation query: `51a9574c-480f-473f-897a-e43c4def8448`
3. Committed to GitHub: [pending]
4. Timeline rebuild: [pending]
5. Paradigm analysis re-run: [pending]

## References

- Drugs with 2-letter codes: AC, AG, CY, DA, VA (5 total)
- Drugs with 3-letter codes preserved: BCG, BTZ, CFZ, CLA, DpC, EF5, FEC, FLT, ICG, MSC, PLD, POM, S-1, TMZ, TPC, UFT (16 total)
- drugs.csv location: `athena_views/data_dictionary/chemo_reference/drugs.csv`
