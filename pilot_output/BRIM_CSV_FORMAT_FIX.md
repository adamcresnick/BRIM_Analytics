# BRIM CSV Format Fix - Iteration 3a Corrected

**Date**: October 3, 2025  
**Issue**: Variables.csv upload succeeded but skipped 4 variables due to "incomplete info"  
**Root Cause**: Wrong CSV format (4 columns instead of required 11 columns)  
**Status**: ✅ Fixed and pushed to GitHub (commit f6e6607)

---

## Problem

When uploading `pilot_output/brim_csvs_iteration_3a_corrected/variables.csv` to BRIM, the system reported:

```
Finished in 1 seconds. Upload successful: variables.csv and decisions.csv. 
Skipped 4 variable lines due to incomplete info!
```

All 4 variables were skipped, meaning the extraction would run with 0 variables configured.

---

## Root Cause

**Wrong Format (Original):**
```csv
variable_name,cardinality,scope,instruction
first_surgery_date,one_per_patient,patient_level,"..."
```

**Columns**: 4 (variable_name, cardinality, scope, instruction)

**Required Format (BRIM Standard):**
```csv
variable_name,instruction,prompt_template,aggregation_instruction,aggregation_prompt_template,variable_type,scope,option_definitions,aggregation_option_definitions,only_use_true_value_in_aggregation,default_value_for_empty_response
first_surgery_date,"...",,,,text,one_per_patient,,,,unknown
```

**Columns**: 11 (as shown above)

### Missing Columns That Caused "Incomplete Info"

1. `prompt_template` - Leave empty (use default)
2. `aggregation_instruction` - Leave empty (no aggregation for single-event test)
3. `aggregation_prompt_template` - Leave empty
4. **`variable_type`** - **CRITICAL**: Must be "text" (defines data type)
5. `option_definitions` - JSON for dropdown values (if applicable)
6. `aggregation_option_definitions` - Leave empty
7. `only_use_true_value_in_aggregation` - Leave empty
8. **`default_value_for_empty_response`** - **CRITICAL**: Must be "unknown" or "Other" (fallback value)

Without `variable_type` and `default_value_for_empty_response`, BRIM considers the variable definition incomplete.

---

## Fix Applied

### **Column Mapping**

| Old Column | New Column | Value | Notes |
|------------|------------|-------|-------|
| `variable_name` | `variable_name` | Same | Variable identifier |
| `instruction` | `instruction` | Same | Extraction instructions |
| (missing) | `prompt_template` | (empty) | Use BRIM default |
| (missing) | `aggregation_instruction` | (empty) | No aggregation |
| (missing) | `aggregation_prompt_template` | (empty) | No aggregation |
| (missing) | **`variable_type`** | **`text`** | **Required - defines data type** |
| `scope` | `scope` | `one_per_patient` | Cardinality |
| (missing) | `option_definitions` | JSON or empty | Dropdown values for surgery_type and extent |
| (missing) | `aggregation_option_definitions` | (empty) | No aggregation options |
| (missing) | `only_use_true_value_in_aggregation` | (empty) | Not applicable |
| (missing) | **`default_value_for_empty_response`** | **`unknown` or `Other`** | **Required - fallback value** |
| `cardinality` | (removed) | N/A | Not a BRIM column |
| `patient_level` | (removed) | N/A | Not a BRIM column |

### **Corrected Variables**

All 4 variables now have complete 11-column format:

1. **`first_surgery_date`**
   - variable_type: `text`
   - scope: `one_per_patient`
   - default_value: `unknown`
   - option_definitions: (empty - free text)

2. **`first_surgery_type`**
   - variable_type: `text`
   - scope: `one_per_patient`
   - default_value: `Other`
   - option_definitions: `{"Tumor Resection": "Tumor Resection", "Biopsy": "Biopsy", "Shunt": "Shunt", "Other": "Other"}`

3. **`first_surgery_extent`**
   - variable_type: `text`
   - scope: `one_per_patient`
   - default_value: `Unknown`
   - option_definitions: `{"Gross Total Resection": "Gross Total Resection", ..., "Unknown": "Unknown"}`

4. **`first_surgery_location`**
   - variable_type: `text`
   - scope: `one_per_patient`
   - default_value: `unknown`
   - option_definitions: (empty - free text)

---

## Data Dictionary Alignment Preserved

The fix maintains all data dictionary alignments:

- ✅ **surgery_type**: Exact dropdown values ("Tumor Resection", "Biopsy", "Shunt", "Other")
- ✅ **extent_of_resection**: Title Case dropdown values ("Partial Resection", "Gross Total Resection", etc.)
- ✅ **surgery_date**: YYYY-MM-DD date format
- ✅ **surgery_location**: Free text (not constrained)

---

## Expected Gold Standard Results (Phase 1 Test)

| Variable | Gold Standard | Expected Extract | Status |
|----------|---------------|------------------|--------|
| `first_surgery_date` | 2018-05-28 | 2018-05-28 | Ready to test |
| `first_surgery_type` | Tumor Resection | Tumor Resection | Ready to test |
| `first_surgery_extent` | Partial Resection | Partial Resection | Ready to test |
| `first_surgery_location` | Posterior fossa | Posterior fossa OR Cerebellum | Ready to test |

**Success Criteria**: 4/4 correct extractions → Phase 1 complete → Proceed to Phase 2 (multi-event longitudinal)

---

## Files Updated

**Local & GitHub:**
- `pilot_output/brim_csvs_iteration_3a_corrected/variables.csv` (corrected format)

**Commits:**
- `f6e6607` - "Fix variables.csv format - add all 11 required BRIM columns"
- `51a03bd` - "Add Phase 1 iteration_3a_corrected with data-dictionary-aligned single-event test variables" (original)

---

## Next Steps

1. ✅ **Re-upload corrected variables.csv to BRIM Project 20**
   - Should now show: "Upload successful: variables.csv and decisions.csv. 4 variables configured."
   - No more "skipped" messages

2. ⏭️ **Run extraction** (5-10 minutes)

3. ⏭️ **Download and validate results**
   - Compare to gold standard
   - Verify data dictionary value formatting
   - Check if STRUCTURED_surgeries table was used

4. ⏭️ **Phase 1 decision**:
   - If 4/4 correct → Proceed to Phase 2 (multi-event longitudinal)
   - If 3/4 correct → Minor instruction refinement
   - If 0-2/4 correct → Escalate STRUCTURED priority issue

---

## Lessons Learned

1. **BRIM CSV format is strict** - Must have exactly 11 columns in specific order
2. **variable_type is critical** - Without it, BRIM can't process the variable
3. **default_value_for_empty_response is required** - Defines fallback when extraction fails
4. **option_definitions enables dropdown validation** - Ensures exact value matching
5. **Always validate against working examples** - iteration_2 format was the reference

---

**Status**: ✅ **Ready for Re-Upload**  
**No more "incomplete info" errors expected**
