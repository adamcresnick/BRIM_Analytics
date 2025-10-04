# Phase 3a Project.csv Error - Troubleshooting Guide

**Error**: `cannot access local variable '_var_var_109' where it is not associated with a value`

**Root Cause**: BRIM project.csv is empty (only headers, no data rows)

---

## Problem Analysis

### What Happened
1. You uploaded variables.csv (17 variables) ✅
2. You uploaded decisions.csv (empty) ✅  
3. You uploaded project.csv with **only headers, no data** ❌
4. BRIM tried to run extraction but had no source documents
5. Internal BRIM error: variable reference not initialized

### Why Phase 2 Didn't Have This Issue
Phase 2 likely used one of these approaches:
- Connected directly to FHIR data source (not CSV upload)
- Had STRUCTURED documents pre-loaded in BRIM
- Used a different project with existing data

---

## Solution Options

### ✅ **Option 1: Connect to FHIR Data Source (RECOMMENDED)**

**If BRIM supports direct FHIR connection:**
1. In BRIM project settings, look for "Data Source" or "Connect to FHIR"
2. Provide FHIR endpoint or upload FHIR bundle JSON
3. Patient ID: `e4BwD8ZYDBccepXcJ.Ilo3w3`
4. BRIM will automatically extract from FHIR resources

**Advantages**:
- ✅ No manual project.csv creation needed
- ✅ Direct access to Patient, Condition, Procedure resources
- ✅ Most reliable for demographics (Patient.gender, Patient.birthDate)

---

### ✅ **Option 2: Use Existing Phase 2 Project Data**

**If Phase 2 project already has the clinical notes:**
1. In BRIM, duplicate Phase 2 project
2. Replace variables.csv with Phase 3a variables.csv (17 variables)
3. Keep existing project.csv/data source from Phase 2
4. Run extraction

**Advantages**:
- ✅ Reuses proven Phase 2 data source
- ✅ No new data upload needed
- ✅ Fast setup (5 minutes)

---

### ⚠️ **Option 3: Create Full project.csv from FHIR Bundle**

**If BRIM requires CSV upload only:**

This requires extracting all clinical notes from the FHIR bundle and formatting as CSV. This is complex and time-consuming.

**I can help generate this if Options 1 & 2 don't work.**

---

## Recommended Immediate Action

### **Try Option 2 First (Fastest)**

1. **In BRIM UI**:
   - Go to Phase 2 project (Project 21 or Pilot 5)
   - Click "Duplicate Project" or "Create New Version"
   - New project name: "Phase 3a Tier 1 Expansion"

2. **Upload ONLY variables.csv**:
   - File: `pilot_output/brim_csvs_iteration_3c_phase3a/variables.csv`
   - **Do NOT upload project.csv** (keep Phase 2's data source)
   - Keep decisions.csv empty or use Phase 2's

3. **Run Extraction**:
   - BRIM will use Phase 2's data with Phase 3a's 17 variables
   - Expected time: 12-15 minutes

4. **Download results and validate**

---

## If You Need to Create project.csv (Option 3)

Let me know and I can:

1. **Extract all notes from FHIR bundle** (`fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json`)
2. **Convert to project.csv format**:
   ```csv
   NOTE_ID,PERSON_ID,NOTE_DATETIME,NOTE_TEXT,NOTE_TITLE
   note_001,C1277724,2018-05-28,"Operative report text...",Operative Note
   note_002,C1277724,2018-06-04,"Pathology report text...",Pathology Report
   ...
   ```

3. **Include STRUCTURED documents** if needed:
   ```csv
   STRUCTURED_surgeries,C1277724,2025-10-03,"| Date | Surgery Type | Extent | Location |...",Structured Surgery Table
   ```

This is a 30-60 minute process. **Try Option 2 first** - it's much faster.

---

## Quick Diagnostic Questions

To help troubleshoot further, please share:

1. **How did you upload data in Phase 2?**
   - Direct FHIR connection?
   - CSV upload?
   - Pre-loaded project?

2. **Does BRIM have a "Data Source" or "Connect to FHIR" option?**

3. **Can you duplicate/clone the Phase 2 project in BRIM?**

4. **What does the Phase 2 project.csv look like?**
   - Empty (just headers)?
   - Full of clinical notes?

---

## Expected Project.csv Structure (If Needed)

If you need to create project.csv, minimum structure:

```csv
NOTE_ID,PERSON_ID,NOTE_DATETIME,NOTE_TEXT,NOTE_TITLE
pathology_001,C1277724,2018-06-04,"DIAGNOSIS: Pilocytic astrocytoma, WHO Grade I. BRAF fusion detected (KIAA1549-BRAF).",Pathology Report
surgery_001,C1277724,2018-05-28,"Procedure: Partial resection of posterior fossa tumor. Location: Cerebellum.",Operative Note
surgery_002,C1277724,2021-03-10,"Procedure: Partial resection of recurrent cerebellar tumor.",Operative Note
demographics_001,C1277724,2005-05-13,"Patient: Female, DOB: 2005-05-13",Demographics
```

**But Option 2 (duplicate Phase 2 project) is MUCH easier!**

---

## Status & Next Steps

**Current Blocker**: Empty project.csv causing BRIM extraction failure

**Recommended Path**:
1. ✅ Try Option 2 (duplicate Phase 2 project)
2. ⏸️ If fails, report back what Phase 2 data source looks like
3. ⏸️ If necessary, I'll generate full project.csv from FHIR bundle

**Let me know which option you'd like to pursue!**
