# BRIM Iteration 2 - Quick Reference

**Last Updated:** October 2, 2025  
**Status:** ✅ Ready for Step 1 (Update Variables)  
**GitHub:** Synced at commit `071e79b`

---

## What We Just Fixed ✅

### The Problem
- Query used `performed_date_time IS NOT NULL` but field had **empty strings**
- Only extracted 1 surgery (missed 3 that had dates in `performed_period_start`)

### The Solution
```sql
CASE 
    WHEN p.performed_date_time IS NOT NULL AND p.performed_date_time != '' 
        THEN p.performed_date_time
    WHEN p.performed_period_start IS NOT NULL AND p.performed_period_start != '' 
        THEN SUBSTR(p.performed_period_start, 1, 10)
    ELSE NULL
END as surgery_date
```

### The Result
Now extracting **4 procedures** (was 1):
- `2018-05-28` - CPT 61500, 61518 (Initial surgery)
- `2021-03-10` - CPT 61510 (Progressive surgery)
- `2021-03-16` - CPT 61524 (Progressive surgery)

---

## Next 3 Steps (45 minutes total)

### ⏳ Step 1: Update Variables (15 min)
Copy `pilot_output/brim_csvs_final/variables.csv` and add PRIORITY instructions to 7 variables:
- `diagnosis_date` - Check STRUCTURED_diagnosis_date first
- `molecular_profile` - Check STRUCTURED_molecular_markers first
- `idh_mutation` - Check STRUCTURED_molecular_markers first
- `surgery_date` - Check STRUCTURED_surgeries first
- `surgery_type` - Check STRUCTURED_surgeries first
- `surgery_location` - Check STRUCTURED_surgeries first
- `chemotherapy_agent` - Check STRUCTURED_treatments first

**Template:** `"PRIORITY 1: Check NOTE_ID='STRUCTURED_[name]' document..."`

### ⏳ Step 2: Regenerate CSVs (5 min)
```bash
python3 scripts/pilot_generate_brim_csvs.py \
  --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json \
  --structured-data pilot_output/structured_data_final.json \
  --prioritized-docs pilot_output/prioritized_documents.json \
  --output-dir pilot_output/brim_csvs_iteration_2
```

### ⏳ Step 3: Upload & Run (20 min)
1. Go to https://brim.radiant-tst.d3b.io
2. Open Project 17
3. Upload 3 files (replace existing)
4. Trigger extraction
5. Download results

---

## Expected Results

| Test | Current | Target | Fix |
|------|---------|--------|-----|
| gender | ✅ Pass | ✅ Pass | Already working |
| molecular | ❌ Fail | ✅ Pass | PRIORITY instruction |
| diagnosis_date | ✅ Pass | ✅ Pass | Already working |
| surgery_count | ❌ Fail (24) | ✅ Pass (2-4) | Pre-filtering |
| chemo_agents | ❌ Fail (7) | ✅ Pass (3) | PRIORITY instruction |
| tumor_location | ❌ Fail | ✅ Pass | Improved extraction |
| who_grade | ✅ Pass | ✅ Pass | Already working |
| diagnosis_type | ✅ Pass | ✅ Pass | Already working |

**Current:** 50% (4/8)  
**Target:** 85-90% (7-8/8)

---

## Key Files

### Modified
- `scripts/extract_structured_data.py` - Surgery extraction fix

### New Documentation
- `pilot_output/ITERATION_2_PROGRESS_AND_NEXT_STEPS.md` - Full details
- `pilot_output/COMPREHENSIVE_VALIDATION_ANALYSIS.md` - Root cause analysis
- `pilot_output/DESIGN_INTENT_VS_IMPLEMENTATION.md` - Design validation

### Data Files
- `pilot_output/structured_data_final.json` - 4 surgeries extracted (gitignored)
- `pilot_output/brim_csvs_final/` - Iteration 1 CSVs
- `pilot_output/brim_csvs_iteration_2/` - **TO BE CREATED**

---

## Critical Insights

1. **Empty strings ≠ NULL** in Athena - Always check both
2. **Gold standard "2 surgeries"** = 2 encounters, not 2 procedures
3. **Deduplication was NOT the problem** - All STRUCTURED docs preserved
4. **LLM needs explicit priorities** - Won't automatically prefer structured data
5. **FHIR has multiple date fields** - `performed_date_time` OR `performed_period_start`

---

## Quick Commands

```bash
# View current surgeries
cat pilot_output/structured_data_final.json | jq '.surgeries'

# Check git status
git status

# Run validation (after iteration 2)
python scripts/automated_brim_validation.py \
  --validate-only \
  --results-csv pilot_output/brim_results_c1277724/results_iteration2_*.csv \
  --gold-standard-dir data/20250723_multitab_csvs
```

---

**📍 WHERE WE ARE:** Just finished fixing structured data extraction (1→4 surgeries)  
**🎯 NEXT ACTION:** Update `variables.csv` with PRIORITY instructions (Step 1)  
**⏱️ TIME TO COMPLETION:** ~45 minutes
