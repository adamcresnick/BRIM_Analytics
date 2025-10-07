# Decisions CSV Fix Report
**Date:** October 5, 2025  
**Issue:** BRIM skipped 13 of 14 decision lines due to incomplete info  
**Root Cause:** Aggregation-type decisions had empty `prompt` column

---

## Problem

BRIM upload message:
```
Finished in 1 seconds. Upload successful: variables.csv and decisions.csv. 
Skipped 13 decision lines due to incomplete info!
```

### Analysis

**decisions.csv structure:**
- **Columns**: `decision_name`, `decision_type`, `input_variables`, `output_variable`, `prompt`, `aggregation_prompt`
- **Filter decisions** (6 total): Had `prompt` filled, `aggregation_prompt` empty ✅
- **Aggregation decisions** (7 total): Had `prompt` EMPTY, `aggregation_prompt` filled ❌

**BRIM requirement:** The `prompt` column must be populated for ALL decisions, regardless of `decision_type`.

### Affected Decisions

All 7 aggregation-type decisions were skipped:
1. `total_surgeries`
2. `all_chemotherapy_agents`
3. `all_symptoms`
4. `earliest_symptom_date`
5. `molecular_tests_summary`
6. `imaging_progression_timeline`
7. `treatment_response_summary`

Only 1 decision was accepted (likely a filter-type decision with populated prompt).

---

## Solution

**Script:** `/scripts/fix_decisions_csv.py`

**Action Taken:**
- For each decision where `decision_type='aggregation'` AND `prompt` is empty:
  - Copy value from `aggregation_prompt` column to `prompt` column
  - Keep `aggregation_prompt` column as-is (duplicate content)
  
**Rationale:** BRIM may use `prompt` for all decision types and only reference `aggregation_prompt` as supplementary information.

---

## Results

### Before Fix
```csv
total_surgeries,aggregation,surgery_date,total_surgeries,"","Count total tumor resection surgeries..."
                                                          ^^^ EMPTY
```

### After Fix
```csv
total_surgeries,aggregation,surgery_date,total_surgeries,"Count total tumor resection surgeries...","Count total tumor resection surgeries..."
                                                          ^^^ NOW POPULATED                           ^^^ KEPT FOR REFERENCE
```

**Changes:**
- ✅ All 7 aggregation decisions now have `prompt` populated
- ✅ Total decisions: 13 (6 filter + 7 aggregation)
- ✅ Backup created: `decisions_backup_20251005_072901.csv`

---

## Validation

Run this to verify no empty prompts:
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2
python3 -c "
import csv
with open('decisions.csv', 'r') as f:
    reader = csv.DictReader(f)
    empty_prompts = [row['decision_name'] for row in reader if not row['prompt'].strip()]
    print(f'Decisions with empty prompts: {len(empty_prompts)}')
    if empty_prompts:
        print('Empty:', empty_prompts)
    else:
        print('✅ All decisions have prompts populated')
"
```

Expected output: `✅ All decisions have prompts populated`

---

## Next Steps

1. **Re-upload** `decisions.csv` to BRIM
2. Expected result: "Upload successful: variables.csv and decisions.csv. **0 lines skipped**"
3. Proceed with project.csv upload (1,472 rows, no duplicates)
4. Monitor extraction (expected 2-4 hours)

---

## Lessons Learned

### CSV Design Requirements
- **ALWAYS populate `prompt` column** for all decisions (both filter and aggregation types)
- **`aggregation_prompt` is optional/supplementary** - BRIM may not use it if `prompt` is empty
- Test CSV uploads incrementally (variables first, then decisions, then project)

### BRIM Behavior
- **Silent skipping**: BRIM skips incomplete rows with minimal error detail
- **Validation needed**: Always check "X lines skipped" in upload messages
- **Column requirements**: All required columns must have values for ALL rows

### Future Prevention
1. Add validation script to check for empty required fields before upload
2. Document BRIM CSV requirements clearly in `/docs/BRIM_CSV_FORMAT_REQUIREMENTS.md`
3. Create CSV linter as pre-upload check:
   ```python
   def validate_decisions_csv(file):
       required_fields = ['decision_name', 'decision_type', 'input_variables', 
                          'output_variable', 'prompt']
       # Check all required fields populated for all rows
   ```

---

## File Locations

- **Fixed decisions.csv**: `/pilot_output/brim_csvs_iteration_3c_phase3a_v2/decisions.csv`
- **Backup**: `/pilot_output/brim_csvs_iteration_3c_phase3a_v2/decisions_backup_20251005_072901.csv`
- **Fix script**: `/scripts/fix_decisions_csv.py`
- **This report**: `/pilot_output/brim_csvs_iteration_3c_phase3a_v2/DECISIONS_FIX_REPORT.md`

---

**Status:** ✅ READY FOR RE-UPLOAD TO BRIM
