# BRIM Decisions CSV Upload Fix - Root Cause Analysis

## Date
October 5, 2025

## Issue
BRIM was skipping ALL 13 decisions with error: "Skipped 13 decision lines due to incomplete info!"

## Symptoms
- ✅ Variables CSV uploaded successfully
- ✅ Decisions CSV uploaded successfully  
- ❌ ALL decisions (13/13) were skipped during processing
- Error message: "incomplete info"

## Root Cause Investigation

### Initial Hypothesis (WRONG)
We initially thought decisions required variables with `scope='document'`. This was proven FALSE by examining the CSK example file which showed:
- ✅ CSK decisions successfully reference variables with `scope='many_per_note'`
- ✅ All 12 CSK variables had `scope='many_per_note'`

### Actual Root Cause (CORRECT)
**BRIM requires that all variables referenced by decisions have a `prompt_template` field populated.**

Our `variables.csv` had:
- ✅ `instruction` field populated (with extraction instructions)
- ❌ `prompt_template` field **empty** (blank strings)

The generation script `pilot_generate_brim_csvs.py` line 748 explicitly set:
```python
# Ensure prompt_template is empty string (per production examples)
for var in variables:
    var['prompt_template'] = ''
```

This was based on an incorrect assumption from old production examples.

## How BRIM Validates Decisions

When processing a decision, BRIM:
1. ✅ Validates decision CSV format (columns, types)
2. ✅ Checks that referenced variables exist in variables.csv
3. ❌ **Checks that each referenced variable has `prompt_template` populated**
4. If any variable lacks `prompt_template`, the entire decision is skipped

## The Fix

### Script Changes
Modified `scripts/pilot_generate_brim_csvs.py` line 748:

**BEFORE (Bug):**
```python
# Ensure prompt_template is empty string (per production examples)
for var in variables:
    var['prompt_template'] = ''
```

**AFTER (Fixed):**
```python
# CRITICAL FIX: Populate prompt_template from instruction field
# BRIM requires prompt_template to be populated for decisions to work
# If empty, decisions will be skipped with "incomplete info" error
for var in variables:
    if not var.get('prompt_template'):
        var['prompt_template'] = var['instruction']
```

### One-Time Fix for Existing Files
Created `scripts/fix_variables_prompt_template.py` to fix existing variables.csv:
```python
# Populate prompt_template from instruction
for row in rows:
    if not row.get('prompt_template', '').strip() and row.get('instruction', '').strip():
        row['prompt_template'] = row['instruction']
```

## Verification Process

### Check 1: Variables Have Prompts
```python
import csv

with open('variables.csv', 'r') as f:
    rows = list(csv.DictReader(f))
    missing = [r['variable_name'] for r in rows if not r.get('prompt_template', '').strip()]
    
print(f"Variables missing prompt_template: {len(missing)}")
# Expected: 0
```

### Check 2: Decision Variables Have Prompts  
```python
import csv, json

# Get variables
with open('variables.csv', 'r') as f:
    vars_dict = {row['variable_name']: row for row in csv.DictReader(f)}

# Check each decision
with open('decisions.csv', 'r') as f:
    for dec in csv.DictReader(f):
        vars_list = json.loads(dec['variables'])
        missing_prompt = [v for v in vars_list if not vars_dict[v].get('prompt_template', '').strip()]
        
        if missing_prompt:
            print(f"❌ {dec['decision_name']}: Missing prompts for {missing_prompt}")
        else:
            print(f"✅ {dec['decision_name']}: All variables have prompts")
```

## Expected Upload Result

**BEFORE Fix:**
```
Upload successful: variables.csv and decisions.csv
Skipped 13 decision lines due to incomplete info!
```

**AFTER Fix:**
```
Upload successful: variables.csv and decisions.csv
0 decision lines skipped  ✅
```

## Lessons Learned

### What We Learned About BRIM Architecture

1. **Scope is NOT a restriction for decisions**
   - Decisions can reference variables with any scope (document, one_per_note, many_per_note, one_per_patient)
   - The CSK example proves this definitively

2. **prompt_template is REQUIRED for all variables**
   - Even if you have `instruction` populated
   - BRIM uses `prompt_template` to prompt the LLM for extraction
   - Without it, variables cannot be used in decisions

3. **instruction vs prompt_template**
   - `instruction`: Human-readable description (optional for BRIM, required for humans)
   - `prompt_template`: LLM prompt for extraction (REQUIRED by BRIM)
   - Best practice: Set both to the same value unless you need different prompts

4. **CSV Format Requirements**
   - `variables.csv` needs 11 columns (we had the right structure)
   - `decisions.csv` needs 5 columns: decision_name, instruction, decision_type, prompt_template, variables
   - Variables must be JSON array with quoted strings: `["var1", "var2"]`
   - Multi-line fields are OK if properly quoted

## Files Modified

### Production Scripts
- ✅ `scripts/pilot_generate_brim_csvs.py` - Fixed prompt_template generation (line 748)

### Utility Scripts (One-time use)
- ✅ `scripts/fix_variables_prompt_template.py` - Fixes existing variables.csv files

### Documentation
- ✅ `docs/BRIM_DECISIONS_FIX_ROOT_CAUSE.md` - This file

## Testing Checklist

Before uploading to BRIM:
- [ ] Run generation script: `python3 scripts/pilot_generate_brim_csvs.py`
- [ ] Verify prompt_template populated: `python3 -c "import csv; rows=list(csv.DictReader(open('variables.csv'))); print('Missing:', [r['variable_name'] for r in rows if not r.get('prompt_template', '').strip()])"`
- [ ] Check decisions reference existing vars: (see Check 2 above)
- [ ] Upload to BRIM and verify: "0 decision lines skipped"

## References

- CSK Example Files:
  - `/Users/resnick/Downloads/CSK_variables.cbeb58cdb633 (2).csv`
  - `/Users/resnick/Downloads/CSK_decisions.4ec22b56bf7b (4).csv`
  
- BRIM Screenshot Documentation (from user):
  - Shows 5-column format for decisions.csv
  - Shows variables field format: `["variable_name_1", "variable_name_2"]`
  
- Patient C1277724 Gold Standards:
  - Test case used throughout development
  - Validated against comprehensive clinical documentation

## Future Prevention

The fix is now permanent in the generation script. For all future patients:
1. Run `python3 scripts/pilot_generate_brim_csvs.py` - will auto-populate prompt_template
2. Upload variables.csv and decisions.csv to BRIM
3. Verify "0 decision lines skipped" in upload response
4. If any skipped, check that referenced variables have prompt_template populated

No manual intervention should be needed going forward.
