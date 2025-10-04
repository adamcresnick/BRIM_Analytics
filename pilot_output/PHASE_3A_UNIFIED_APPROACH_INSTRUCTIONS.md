# Phase 3a Unified Approach - Upload Instructions

**Date**: October 4, 2025  
**Strategy**: Expand Phase 2 (4 variables) → Phase 3a (17 variables) using SAME data source

---

## Understanding the Unified Approach

### What "Unified" Means

**NOT**: Creating separate projects for each variable set  
**YES**: ONE project with ALL variables, ONE data source, ONE extraction run

**Phase Evolution**:
- Phase 2: 4 surgery variables → 100% accuracy ✅
- Phase 3a: 17 variables (4 surgery + 13 Tier 1) → 95%+ expected ✅
- Phase 3b: 28 variables (+ 11 Tier 2 chemo/radiation) → Future
- Phase 4: 41 variables (+ 13 Tier 3 aggregations) → Future

**Same project.csv throughout!**

---

## What to Upload for Phase 3a

### File Checklist

| File | Source | Action |
|------|--------|--------|
| **variables.csv** | `pilot_output/brim_csvs_iteration_3c_phase3a/variables.csv` | ✅ Upload NEW (17 variables) |
| **decisions.csv** | `pilot_output/brim_csvs_iteration_3c_phase3a/decisions.csv` | ✅ Upload (empty - correct!) |
| **project.csv** | **REUSE from Phase 2** | ✅ Use Phase 2's data source |

---

## Option A: If Phase 2 Used FHIR Connection (RECOMMENDED)

**If you connected directly to FHIR endpoint in Phase 2:**

1. **Create New BRIM Project** (or duplicate Phase 2 project)
   - Project Name: "Phase 3a Tier 1 Expansion"

2. **Connect to SAME FHIR data source**
   - Use same connection settings as Phase 2
   - Patient ID: `e4BwD8ZYDBccepXcJ.Ilo3w3` or `C1277724`

3. **Upload ONLY 2 files**:
   - `variables.csv` (17 variables)
   - `decisions.csv` (empty)

4. **Run Extraction**
   - Expected time: 12-15 minutes
   - BRIM will extract from Patient, Condition, Procedure resources

---

## Option B: If Phase 2 Used CSV Upload

**If you uploaded a project.csv file in Phase 2:**

1. **Locate Phase 2's project.csv**
   
   Check where you got it from:
   ```bash
   # Was it one of these?
   pilot_output/brim_csvs_iteration_3b_phase2/project.csv
   # OR
   pilot_output/brim_csvs_iteration_3a_corrected/project.csv
   # OR
   # Another location?
   ```

2. **Create New BRIM Project**
   - Project Name: "Phase 3a Tier 1 Expansion"

3. **Upload 3 files**:
   - Phase 3a `variables.csv` (NEW - 17 variables)
   - Phase 3a `decisions.csv` (NEW - empty)
   - **Phase 2 `project.csv`** (REUSE - same data)

4. **Run Extraction**

---

## What Phase 2's project.csv Should Look Like

If you need to check if your Phase 2 project.csv is complete:

```bash
# Check line count (should be hundreds of lines with clinical notes)
wc -l pilot_output/brim_csvs_iteration_3b_phase2/project.csv

# Should see something like:
# 500 pilot_output/brim_csvs_iteration_3b_phase2/project.csv
```

**If project.csv has only 2 lines** (just headers):
- Phase 2 likely used FHIR connection (not CSV)
- Use Option A above

**If project.csv has 100+ lines**:
- Phase 2 used CSV upload
- Reuse that exact file for Phase 3a

---

## Key Point: Data Source is the SAME

### Phase 2 Extracted From:
- FHIR Patient resource (for future demographics use)
- FHIR Procedure resources (for surgeries)
- Clinical notes (for context)
- STRUCTURED_surgeries document (for table-based extraction)

### Phase 3a Will Extract From:
- **SAME** FHIR Patient resource (NOW extracting gender, DOB)
- **SAME** FHIR Procedure resources (surgeries again)
- **SAME** Clinical notes (pathology reports for diagnosis, WHO grade)
- **SAME** STRUCTURED_surgeries (surgeries again)
- + FHIR Condition resources (for diagnosis_date)
- + Molecular testing reports (for BRAF, IDH, MGMT)

**The data source doesn't change - only the variables.csv changes!**

---

## Expected Behavior

### What You Should See

**During Upload**:
- BRIM accepts variables.csv (17 variables)
- BRIM accepts decisions.csv (empty - no errors)
- BRIM accepts project.csv (or connects to FHIR)

**During Extraction**:
- BRIM processes 17 variables instead of 4
- Extraction time: 12-15 minutes (slightly longer than Phase 2's 12 min)
- Progress bar shows variable completion

**After Extraction**:
- Download BRIM export CSV
- Should have ~113 rows (13 one_per_patient + ~100 many_per_note surgery over-extraction)

---

## Troubleshooting

### Error: "cannot access local variable '_var_var_109'"

**Root Cause**: Empty project.csv (no data rows)

**Fix**: 
- If Phase 2 used FHIR connection, use Option A (connect to FHIR, don't upload empty project.csv)
- If Phase 2 used CSV, find that working project.csv and reuse it

---

### Error: "Variable not found in documents"

**Root Cause**: Some Phase 3a variables may not have data in Phase 2's project.csv

**Expected for**:
- `race`, `ethnicity` (may return "Unavailable" - acceptable)
- `idh_mutation` (may return "Not tested" - acceptable)

**NOT Expected for**:
- `patient_gender`, `date_of_birth` (should be in FHIR Patient)
- `surgery_*` variables (Phase 2 had these)

---

## Files Ready for Upload

```
pilot_output/brim_csvs_iteration_3c_phase3a/
├── variables.csv       ← Upload this (17 variables)
├── decisions.csv       ← Upload this (empty)
├── project.csv         ← DON'T use this (empty)
└── validate_phase3a.py ← Use after extraction

INSTEAD, for project.csv:
- Option A: Connect to FHIR (don't upload project.csv at all)
- Option B: Reuse Phase 2's project.csv from wherever you got it
```

---

## Post-Extraction Validation

```bash
# After downloading BRIM results:
cd pilot_output/brim_csvs_iteration_3c_phase3a/

# Run validation
python3 validate_phase3a.py /path/to/BRIM_Phase3a_Export.csv

# Expected: 16-17/17 = 95%+ accuracy
```

---

## Summary

**Unified Approach** = ONE data source, EXPANDING variables incrementally

**Phase 3a Upload**:
1. ✅ New variables.csv (17 variables)
2. ✅ New decisions.csv (empty)
3. ✅ **REUSE** Phase 2's project.csv or FHIR connection

**Don't recreate the data source - reuse what worked in Phase 2!**

---

## Next Question to Answer

**To help me guide you correctly, please answer:**

1. In Phase 2, did you:
   - [ ] A. Connect to a FHIR endpoint/data source directly in BRIM?
   - [ ] B. Upload a project.csv file with clinical notes?

2. If B, where did you get that project.csv from?
   - Path or description

This will tell me exactly what to reuse for Phase 3a!
