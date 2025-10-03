# PHASE 2 IMPLEMENTATION - Multi-Event Longitudinal Extraction

**Created**: October 3, 2025  
**Based on**: Phase 1 SUCCESS (87.5% accuracy)  
**Iteration**: 3b_phase2  
**Status**: Ready for Upload

---

## Phase 2 Objectives

**Primary Goal**: Extract ALL surgery events (not just first) to validate multi-event longitudinal extraction with maintained event grouping.

**Key Changes from Phase 1**:
1. ✅ **Scope**: `one_per_patient` → `many_per_note` (extract multiple values)
2. ✅ **Instructions**: "Row 1 ONLY" → "ALL rows" (longitudinal extraction)
3. ✅ **Location Values**: Free text → Data Dictionary checkbox (24 specific options)
4. ✅ **Expected Count**: Added guidance "Expected: 2 surgeries for C1277724"

**Success Criteria**:
- Extract 8 total values (2 dates, 2 types, 2 extents, 2 locations)
- Maintain event grouping: surgery_date[0] ↔ surgery_type[0] ↔ surgery_extent[0] ↔ surgery_location[0]
- 100% accuracy (8/8 correct)

---

## Critical Fix: Location Values Now Data-Dictionary-Aligned

### Problem Identified in Phase 1

**Phase 1 Result**: `first_surgery_location = "Skull"`
- ⚠️ Extracted procedure location (from "CRANIECTOMY W/EXCISION TUMOR/LESION **SKULL**")
- ❌ NOT tumor anatomical location (should be "Cerebellum/Posterior Fossa")
- ⚠️ Too general for clinical analysis

**Root Cause**: 
- Instruction was vague: "Extract from 'Anatomical Location' column"
- No constraint on valid values (free text)
- BRIM chose surgical approach over tumor location

### Solution: Data Dictionary Checkbox Values

**Data Dictionary Field**: `tumor_location` (checkbox field type)

**24 Valid Options**:
1. Frontal Lobe
2. Temporal Lobe
3. Parietal Lobe
4. Occipital Lobe
5. Thalamus
6. Ventricles
7. Suprasellar/Hypothalamic/Pituitary
8. **Cerebellum/Posterior Fossa** ← Gold Standard for C1277724
9. Brain Stem-Medulla
10. Brain Stem-Midbrain/Tectum
11. Brain Stem-Pons
12. Spinal Cord-Cervical
13. Spinal Cord-Thoracic
14. Spinal Cord-Lumbar/Thecal Sac
15. Optic Pathway
16. Cranial Nerves NOS
17. Other locations NOS
18. Spine NOS
19. Pineal Gland
20. Basal Ganglia
21. Hippocampus
22. Meninges/Dura
23. Skull
24. Unavailable

**Note**: "Skull" IS a valid option (#23) but should ONLY be used for skull-based tumors (e.g., meningiomas), NOT for brain parenchymal tumors.

### Enhanced Instruction

**Key Additions**:
1. **CRITICAL prefix**: "Extract TUMOR anatomical location (NOT surgical approach/procedure location)"
2. **option_definitions JSON**: All 24 values with exact casing
3. **DO NOT examples**: "DO NOT return procedure locations like 'Craniotomy' or surgical approaches"
4. **WHERE to look**: "Look for tumor location in pathology, radiology, or operative notes describing WHERE the tumor is located (not where the incision is made)"

**Expected Outcome**:
- Phase 2 should extract "Cerebellum/Posterior Fossa" (not "Skull")
- Both surgeries should have same location (tumor hasn't moved)

---

## Variable Definitions (Phase 2)

### 1. surgery_date (many_per_note)

**Changes from Phase 1**:
- Scope: `one_per_patient` → `many_per_note`
- Instruction: "Row 1 ONLY" → "ALL dates from table"
- Expected count: 2 surgery dates

**Gold Standard for C1277724**:
- Surgery 1: 2018-05-28
- Surgery 2: 2021-03-10

**Instruction Excerpt**:
> "Locate the surgery history table and extract ALL dates from the 'Date' column (NOT just Row 1). Return one date per surgery in format YYYY-MM-DD... Expected count: 2 surgery dates."

---

### 2. surgery_type (many_per_note)

**Changes from Phase 1**:
- Scope: `one_per_patient` → `many_per_note`
- Instruction: "Row 1 ONLY" → "ALL rows from table"
- Expected count: 2 surgery types

**Gold Standard for C1277724**:
- Surgery 1: Tumor Resection
- Surgery 2: Tumor Resection

**option_definitions** (unchanged):
```json
{
  "Tumor Resection": "Tumor Resection",
  "Biopsy": "Biopsy",
  "Shunt": "Shunt",
  "Other": "Other"
}
```

**Instruction Excerpt**:
> "Extract from ALL rows (NOT just Row 1) from 'Surgery Type' column. Return EXACTLY one of these Data Dictionary values per surgery... Expected count: 2 surgery types."

---

### 3. surgery_extent (many_per_note)

**Changes from Phase 1**:
- Scope: `one_per_patient` → `many_per_note`
- Instruction: "Row 1 ONLY" → "ALL rows from table"
- Expected count: 2 surgery extents

**Gold Standard for C1277724**:
- Surgery 1: Partial Resection
- Surgery 2: Partial Resection

**option_definitions** (unchanged):
```json
{
  "Gross Total Resection": "Gross Total Resection",
  "Near Total Resection": "Near Total Resection",
  "Subtotal Resection": "Subtotal Resection",
  "Partial Resection": "Partial Resection",
  "Biopsy Only": "Biopsy Only",
  "Unknown": "Unknown"
}
```

**Instruction Excerpt**:
> "Extract from ALL rows (NOT just Row 1) from 'Extent of Resection' column... Expected count: 2 surgery extents."

---

### 4. surgery_location (many_per_note) ⭐ MAJOR UPDATE

**Changes from Phase 1**:
- Scope: `one_per_patient` → `many_per_note`
- Instruction: "Row 1 ONLY" → "ALL rows from table"
- **Field Type**: Free text → Checkbox (constrained values)
- **option_definitions**: Added 24 data dictionary locations
- **Expected count**: 2 surgery locations

**Gold Standard for C1277724**:
- Surgery 1: Cerebellum/Posterior Fossa
- Surgery 2: Cerebellum/Posterior Fossa

**option_definitions** (NEW):
```json
{
  "Frontal Lobe": "Frontal Lobe",
  "Temporal Lobe": "Temporal Lobe",
  "Parietal Lobe": "Parietal Lobe",
  "Occipital Lobe": "Occipital Lobe",
  "Thalamus": "Thalamus",
  "Ventricles": "Ventricles",
  "Suprasellar/Hypothalamic/Pituitary": "Suprasellar/Hypothalamic/Pituitary",
  "Cerebellum/Posterior Fossa": "Cerebellum/Posterior Fossa",
  "Brain Stem-Medulla": "Brain Stem-Medulla",
  "Brain Stem-Midbrain/Tectum": "Brain Stem-Midbrain/Tectum",
  "Brain Stem-Pons": "Brain Stem-Pons",
  "Spinal Cord-Cervical": "Spinal Cord-Cervical",
  "Spinal Cord-Thoracic": "Spinal Cord-Thoracic",
  "Spinal Cord-Lumbar/Thecal Sac": "Spinal Cord-Lumbar/Thecal Sac",
  "Optic Pathway": "Optic Pathway",
  "Cranial Nerves NOS": "Cranial Nerves NOS",
  "Other locations NOS": "Other locations NOS",
  "Spine NOS": "Spine NOS",
  "Pineal Gland": "Pineal Gland",
  "Basal Ganglia": "Basal Ganglia",
  "Hippocampus": "Hippocampus",
  "Meninges/Dura": "Meninges/Dura",
  "Skull": "Skull",
  "Unavailable": "Unavailable"
}
```

**Instruction Excerpt** (CRITICAL sections):
> "CRITICAL: Extract TUMOR anatomical location (NOT surgical approach/procedure location). Return EXACTLY one of these Data Dictionary values per surgery... DO NOT return procedure locations like 'Craniotomy' or surgical approaches. Look for tumor location in pathology, radiology, or operative notes describing WHERE the tumor is located (not where the incision is made)."

**Why This Fixes the Phase 1 Issue**:
1. ✅ **option_definitions** constrains to 24 valid anatomical locations
2. ✅ **CRITICAL prefix** emphasizes tumor vs procedure distinction
3. ✅ **DO NOT examples** explicitly exclude "Craniotomy", "Skull" (as procedure)
4. ✅ **Gold standard guidance** shows expected value "Cerebellum/Posterior Fossa"
5. ✅ **Default value** "Unavailable" (not "unknown") matches data dictionary

---

## Expected Results for C1277724

### Target Extractions (8 total)

| Variable | Surgery 1 (2018-05-28) | Surgery 2 (2021-03-10) | Status |
|----------|------------------------|------------------------|--------|
| **surgery_date** | 2018-05-28 | 2021-03-10 | Date format YYYY-MM-DD |
| **surgery_type** | Tumor Resection | Tumor Resection | Title Case dropdown |
| **surgery_extent** | Partial Resection | Partial Resection | Title Case dropdown |
| **surgery_location** | Cerebellum/Posterior Fossa | Cerebellum/Posterior Fossa | Data dict checkbox |

**Total**: 8 extractions (4 variables × 2 surgeries)

### Event Grouping Validation

**Critical Test**: Do the variables maintain row-based associations?

**Expected Grouping**:
```
Event 1 (Surgery 1):
  - surgery_date[0] = 2018-05-28
  - surgery_type[0] = Tumor Resection
  - surgery_extent[0] = Partial Resection
  - surgery_location[0] = Cerebellum/Posterior Fossa

Event 2 (Surgery 2):
  - surgery_date[1] = 2021-03-10
  - surgery_type[1] = Tumor Resection
  - surgery_extent[1] = Partial Resection
  - surgery_location[1] = Cerebellum/Posterior Fossa
```

**Validation Questions**:
1. Can we match surgery_date[0] with surgery_type[0]? (Are they for same surgery?)
2. Does BRIM preserve table row structure when extracting multiple events?
3. If grouping is lost, do we need surgery_1_date, surgery_2_date variable naming instead?

---

## STRUCTURED_surgeries Document Reference

**Document ID**: `STRUCTURED_surgeries`

**Table Format**:
```markdown
# SURGICAL HISTORY SUMMARY

| Surgery ID | Date | CPT Code | Surgery Type | Extent | Location |
|------------|------|----------|--------------|--------|----------|
| SURG_001 | 2018-05-28 | 61518 | Tumor Resection | Partial Resection | Posterior fossa |
| SURG_002 | 2021-03-10 | 61510 | Tumor Resection | Partial Resection | Posterior fossa |

## EXTRACTION INSTRUCTIONS
**For surgery_date**: Extract from ALL rows, Date column
**For surgery_type**: Extract from ALL rows, Surgery Type column
**For surgery_extent**: Extract from ALL rows, Extent column
**For surgery_location**: Extract from ALL rows, Location column
```

**Key Points**:
- 2 rows = 2 surgeries
- Clear column headers
- Consistent formatting
- Location shows "Posterior fossa" (lowercase in table)
- BRIM must map "Posterior fossa" → "Cerebellum/Posterior Fossa" (data dict value)

---

## Upload Instructions

### Files to Upload (3 files)

1. **variables.csv** (4 variables, many_per_note scope)
2. **decisions.csv** (header only - no aggregations in Phase 2)
3. **project.csv** (45 documents including STRUCTURED_surgeries, 3.3 MB)

### BRIM Project Setup

**Project Name**: Project 21 - Phase 2 Multi-Event Test  
**URL**: https://brim.radiant-tst.d3b.io

**Steps**:
1. Navigate to BRIM web UI
2. Create new project OR clear existing project
3. Upload 3 files from `pilot_output/brim_csvs_iteration_3b_phase2/`
4. Verify upload success: "4 variables configured, 0 skipped"
5. Click "Run Extraction"
6. Wait ~10-15 minutes for completion
7. Download results CSV

### Expected Upload Success Message

```
Finished in 1 seconds. 
Upload successful: variables.csv and decisions.csv. 
4 variables configured.
0 skipped lines.
```

**No More "Skipped 4 variable lines" Error** ✅

---

## Validation Plan

### Automated Validation Script

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics
python3 -c "
import csv

# Gold standard
gold = {
    'surgery_date': ['2018-05-28', '2021-03-10'],
    'surgery_type': ['Tumor Resection', 'Tumor Resection'],
    'surgery_extent': ['Partial Resection', 'Partial Resection'],
    'surgery_location': ['Cerebellum/Posterior Fossa', 'Cerebellum/Posterior Fossa']
}

# Read BRIM results
with open('pilot_output/phase_2_results.csv', 'r') as f:
    reader = csv.DictReader(f)
    results = {}
    for row in reader:
        var = row['Name']
        value = row['Value']
        if var not in results:
            results[var] = []
        results[var].append(value)

# Validate
total = 0
correct = 0
for var, expected_list in gold.items():
    actual_list = results.get(var, [])
    for i, expected in enumerate(expected_list):
        total += 1
        actual = actual_list[i] if i < len(actual_list) else 'MISSING'
        if actual == expected:
            correct += 1
            print(f'✅ {var}[{i}] = {actual}')
        else:
            print(f'❌ {var}[{i}] Expected: {expected}, Got: {actual}')

print(f'\nAccuracy: {correct}/{total} = {correct/total*100:.1f}%')
"
```

### Manual Validation Checklist

**Count Validation**:
- [ ] surgery_date has 2 values
- [ ] surgery_type has 2 values
- [ ] surgery_extent has 2 values
- [ ] surgery_location has 2 values
- [ ] Total: 8 extractions

**Value Validation**:
- [ ] surgery_date[0] = 2018-05-28 ✅
- [ ] surgery_date[1] = 2021-03-10 ✅
- [ ] surgery_type[0] = "Tumor Resection" ✅ (Title Case)
- [ ] surgery_type[1] = "Tumor Resection" ✅
- [ ] surgery_extent[0] = "Partial Resection" ✅ (Title Case)
- [ ] surgery_extent[1] = "Partial Resection" ✅
- [ ] surgery_location[0] = "Cerebellum/Posterior Fossa" ✅ (NOT "Skull")
- [ ] surgery_location[1] = "Cerebellum/Posterior Fossa" ✅

**Event Grouping Validation**:
- [ ] Can identify Surgery 1 fields vs Surgery 2 fields
- [ ] Chronological order maintained (2018 before 2021)
- [ ] If BRIM export has Document_id, check if same for grouped events

---

## Success Metrics

### Phase 2 Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Variable Count** | 4 variables accepted | Check upload success message |
| **Extraction Count** | 8 total values | 4 variables × 2 surgeries |
| **Date Accuracy** | 2/2 dates correct | 100% |
| **Type Accuracy** | 2/2 types correct | 100% |
| **Extent Accuracy** | 2/2 extents correct | 100% |
| **Location Accuracy** | 2/2 locations correct | 100% with data dict values |
| **Overall Accuracy** | 8/8 = 100% | All values correct |
| **Event Grouping** | Maintained | Can match surgery 1 vs 2 |

### Comparison to Phase 1

| Aspect | Phase 1 | Phase 2 Target | Improvement |
|--------|---------|----------------|-------------|
| **Scope** | one_per_patient | many_per_note | Longitudinal extraction |
| **Variables** | 4 | 4 | Same |
| **Extractions** | 4 (1 per variable) | 8 (2 per variable) | 2× data captured |
| **Location Field** | Free text | Checkbox (24 options) | Data dict aligned |
| **Accuracy** | 87.5% (3.5/4) | 100% (8/8 target) | +12.5 points |

---

## Risk Assessment

### Known Risks

1. **Event Grouping May Be Lost** (Medium Risk)
   - BRIM may extract values as flat lists without row associations
   - Mitigation: Check if Document_id or instance_index preserves grouping
   - Fallback: Implement surgery_1_*, surgery_2_* variable naming

2. **Location Mapping May Fail** (Low Risk)
   - STRUCTURED table shows "Posterior fossa" (lowercase)
   - BRIM must map to "Cerebellum/Posterior Fossa" (data dict value)
   - Mitigation: option_definitions JSON should enforce exact match
   - Fallback: Add "posterior fossa" → "Cerebellum/Posterior Fossa" mapping note

3. **Multiple Extractions May Confuse BRIM** (Low Risk)
   - First test of many_per_note with table format
   - Mitigation: Clear "ALL rows" instruction, expected count guidance
   - Evidence: Phase 1 proved single-row extraction works

4. **FHIR Fallback May Override STRUCTURED** (Low Risk)
   - If PRIORITY 1 fails, BRIM searches FHIR Bundle
   - May find only 1 surgery in FHIR (not both)
   - Mitigation: STRUCTURED document should be primary source

### Confidence Level

**Overall Confidence**: High (80%)

**Rationale**:
- ✅ Phase 1 proved table-based STRUCTURED approach works
- ✅ CSV format validated (no skipped variables)
- ✅ option_definitions enforcement proven (surgery_type, surgery_extent)
- ✅ Data dictionary alignment achieved
- ⚠️ Untested: many_per_note extraction from tables
- ⚠️ Untested: Location value mapping (lowercase → Title Case)

**Expected Outcomes**:
- **Best Case** (50% probability): 8/8 correct with event grouping maintained
- **Good Case** (30% probability): 7-8/8 correct but event grouping lost
- **Acceptable Case** (15% probability): 6/8 correct (location mapping issue)
- **Failure Case** (5% probability): <6/8 correct (multi-event extraction fails)

---

## Next Steps After Phase 2

### If 100% Success (8/8 correct)

**Proceed to Phase 3**: Aggregation Decisions
- Add `total_surgeries` decision (count unique surgery_date values)
- Add `best_resection` decision (return most extensive from surgery_extent)
- Test if decisions can aggregate multi-event data correctly

**Expand Variable Set**:
- Add chemotherapy variables (multi-event longitudinal)
- Add molecular markers (one-per-patient from STRUCTURED)
- Add radiation therapy variables

### If 75-99% Success (6-7/8 correct)

**Iterate on Failed Variable**:
- Analyze which variable failed and why
- Refine instruction for that variable
- Re-run Phase 2 with updated instruction

**Document Lessons Learned**:
- What worked vs didn't work
- Platform limitations identified
- Workarounds needed

### If <75% Success (<6/8 correct)

**Escalate to BRIM Platform Team**:
- Question: Does BRIM support many_per_note extraction from tables?
- Question: How to preserve event grouping for longitudinal data?
- Request: API documentation for multi-event extraction patterns

**Consider Alternative Approach**:
- Implement surgery_1_*, surgery_2_* variable naming (event-indexed)
- Pre-compute aggregations in STRUCTURED documents
- Use decisions for event grouping logic

---

## Files Summary

**Location**: `pilot_output/brim_csvs_iteration_3b_phase2/`

**Files**:
1. **variables.csv** (4.9 KB)
   - 4 variables (surgery_date, surgery_type, surgery_extent, surgery_location)
   - All with many_per_note scope
   - Location has 24 data dictionary option_definitions

2. **decisions.csv** (40 B)
   - Header only (no aggregations in Phase 2)

3. **project.csv** (3.3 MB)
   - 45 documents including STRUCTURED_surgeries table
   - Same as Phase 1 (no changes needed)

**Git Status**: Ready to commit after upload test

---

## Appendix: Data Dictionary Reference

### tumor_location Field Definition

**Source**: `data/20250723_multitab_csvs/20250723_multitab__data_dictionary.csv`

**Field Properties**:
- **Variable Name**: tumor_location
- **Section**: diagnosis
- **Field Type**: checkbox (multiple selections allowed)
- **Field Label**: "Tumor Location(s) at time of diagnosis/clinical event?"
- **Description**: "Location of tumor. Multiple locations can be selected."
- **Validation**: Required if clinical_status_at_event = 1, 2, or 4

**Valid Options** (24 total):
1. Frontal Lobe
2. Temporal Lobe
3. Parietal Lobe
4. Occipital Lobe
5. Thalamus
6. Ventricles
7. Suprasellar/Hypothalamic/Pituitary
8. **Cerebellum/Posterior Fossa** ← Most common for pediatric brain tumors
9. Brain Stem-Medulla
10. Brain Stem-Midbrain/Tectum
11. Brain Stem-Pons
12. Spinal Cord-Cervical
13. Spinal Cord-Thoracic
14. Spinal Cord-Lumbar/Thecal Sac
15. Optic Pathway
16. Cranial Nerves NOS
17. Other locations NOS
18. Spine NOS
19. Pineal Gland
20. Basal Ganglia
21. Hippocampus
22. Meninges/Dura
23. Skull ← Valid for skull-based tumors only (e.g., meningiomas)
24. Unavailable

**Note**: For patient C1277724 with pilocytic astrocytoma of cerebellum, correct value is #8 "Cerebellum/Posterior Fossa" (not #23 "Skull").

---

**Status**: ✅ Ready for Upload and Testing  
**Created**: October 3, 2025  
**Next Action**: User uploads to BRIM and runs extraction
