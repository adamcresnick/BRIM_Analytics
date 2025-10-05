# BRIM CSV Generation Workflow - Updated for Next Patients

## Overview
This document describes the updated workflow for generating BRIM CSVs for new patients after the prompt_template fix.

## What Changed (October 5, 2025)

### The Fix
**Problem:** BRIM was skipping all decisions because `prompt_template` field in variables.csv was empty.

**Solution:** Updated `pilot_generate_brim_csvs.py` to automatically populate `prompt_template` from `instruction` field.

**Impact:** All future CSV generations will work correctly without manual intervention.

## Workflow for Next Patients

### Step 1: Generate CSVs
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

python3 scripts/pilot_generate_brim_csvs.py \
    --patient-id <FHIR_PATIENT_ID> \
    --subject-id <PERSON_ID> \
    --output-dir pilot_output/brim_csvs_<patient_name>
```

**What This Does:**
- Extracts clinical notes from S3/Athena
- Generates `project.csv` with all notes
- Generates `variables.csv` with **prompt_template auto-populated** ✅
- Generates `decisions.csv` with correct BRIM format
- Validates patient IDs (no duplicates)
- Validates all CSVs before saving

### Step 2: Validate CSVs (Automatic)
The generation script now includes automatic validation:
- ✅ All variables have `prompt_template` populated
- ✅ All decision variables exist in variables.csv
- ✅ Project CSV has consistent PERSON_ID
- ✅ No duplicate NOTE_IDs

**Manual Double-Check (Optional):**
```python
# Verify prompt_template populated
python3 -c "
import csv
with open('pilot_output/brim_csvs_<patient>/variables.csv') as f:
    rows = list(csv.DictReader(f))
    missing = [r['variable_name'] for r in rows if not r.get('prompt_template', '').strip()]
    print(f'Variables missing prompt_template: {len(missing)}')
    print(f'Expected: 0')
"
```

### Step 3: Upload to BRIM
Upload the three CSV files to BRIM:
1. `variables.csv` (extraction rules with prompts)
2. `decisions.csv` (aggregation/filtering rules)
3. `project.csv` (clinical notes)

**Expected Result:**
```
Upload successful: variables.csv and decisions.csv
0 decision lines skipped ✅
```

If you see "Skipped X decision lines", something is wrong - check validation.

### Step 4: Run Extraction
Trigger BRIM extraction via web UI or API.

## Files Generated

### project.csv
- **Columns:** NOTE_ID, PERSON_ID, NOTE_DATETIME, NOTE_TEXT, NOTE_TITLE
- **Content:** All clinical notes for the patient
- **Validation:** Consistent PERSON_ID, no duplicate NOTE_IDs

### variables.csv  
- **Columns:** 11 columns including variable_name, instruction, **prompt_template**, etc.
- **Content:** 33+ extraction variables
- **Key Fix:** `prompt_template` = `instruction` (auto-populated) ✅

### decisions.csv
- **Columns:** 5 columns (decision_name, instruction, decision_type, prompt_template, variables)
- **Content:** 13+ dependent variable rules
- **Format:** Variables as JSON array: `["var1", "var2"]`

## Troubleshooting

### Issue: "Skipped X decision lines due to incomplete info!"

**Root Cause:** Variables referenced by decisions don't have `prompt_template` populated.

**Fix:**
```bash
# Run the fix script on existing variables.csv
python3 scripts/fix_variables_prompt_template.py
```

**Then regenerate CSVs using the updated generation script (fix is permanent).**

### Issue: "2 patients" error in BRIM

**Root Cause:** Inconsistent PERSON_ID values in project.csv.

**Fix:** The generation script now auto-validates and standardizes PERSON_IDs.

If still occurring, run:
```bash
python3 scripts/project_csv_validator.py --file project.csv --fix
```

### Issue: Duplicate NOTE_IDs

**Root Cause:** Same clinical note extracted twice.

**Fix:** Generation script now auto-deduplicates. Manual fix:
```bash
python3 scripts/project_csv_validator.py --file project.csv --fix
```

## Key Scripts

### Generation
- **`pilot_generate_brim_csvs.py`** - Main generation script (FIXED ✅)

### Validation  
- **`project_csv_validator.py`** - Validates and fixes project.csv
- **`validate_redesigned_csvs.py`** - Validates variables and decisions

### Utilities (for existing files only)
- **`fix_variables_prompt_template.py`** - Populates prompt_template in old variables.csv

### Documentation
- **`BRIM_DECISIONS_FIX_ROOT_CAUSE.md`** - Detailed root cause analysis
- **`PROJECT_CSV_WORKFLOW.md`** - Project CSV best practices

## Testing Checklist

Before uploading to BRIM for a new patient:

- [ ] CSVs generated successfully (no errors)
- [ ] Variables CSV has prompt_template populated (check count)
- [ ] Decisions CSV references valid variables
- [ ] Project CSV has 1 PERSON_ID value
- [ ] Project CSV has no duplicate NOTE_IDs  
- [ ] File sizes reasonable (project.csv > 100KB typically)

## Example Commands

### Generate CSVs for New Patient
```bash
python3 scripts/pilot_generate_brim_csvs.py \
    --patient-id 12345678-abcd-1234-abcd-1234567890ab \
    --subject-id C9876543 \
    --output-dir pilot_output/brim_csvs_patient_smith
```

### Validate Existing Project CSV
```bash
python3 scripts/project_csv_validator.py \
    --file pilot_output/brim_csvs_patient_smith/project.csv \
    --validate \
    --fix
```

### Check Variables Have Prompts
```bash
cd pilot_output/brim_csvs_patient_smith
python3 -c "
import csv
rows = list(csv.DictReader(open('variables.csv')))
missing = [r['variable_name'] for r in rows if not r.get('prompt_template', '').strip()]
print(f'✅ All {len(rows)} variables have prompt_template' if not missing else f'❌ Missing: {missing}')
"
```

## References

- Root Cause Analysis: `docs/BRIM_DECISIONS_FIX_ROOT_CAUSE.md`
- Project CSV Guide: `docs/PROJECT_CSV_WORKFLOW.md`
- Validation Guide: `docs/PROJECT_CSV_QUALITY_ASSURANCE.md`
- Pre-Upload Checklist: `PRE_UPLOAD_CHECKLIST.md`

## Support

If issues occur:
1. Check the troubleshooting section above
2. Review error messages from BRIM
3. Validate CSVs using validation scripts
4. Check documentation for specific error patterns

## Summary

✅ **The workflow is now fixed for all future patients**
✅ Generation script auto-populates prompt_template  
✅ Validation scripts catch common issues
✅ Documentation explains all edge cases

Just run the generation script and upload - it should work!
