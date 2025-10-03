# Phase 2 Quick Reference - Data Dictionary Location Alignment

**Date**: October 3, 2025  
**Iteration**: 3b_phase2  
**Status**: ✅ Ready for Upload

---

## What Changed from Phase 1

### 🔧 Fixed: Location Values Now Data-Dictionary-Aligned

**Phase 1 Issue**:
- Got: "Skull" (procedure location)
- Want: "Cerebellum/Posterior Fossa" (tumor location)
- Problem: Free text field, vague instruction

**Phase 2 Solution**:
- ✅ **24 checkbox options** from data dictionary tumor_location field
- ✅ **option_definitions JSON** with exact values
- ✅ **Enhanced instruction**: "Extract TUMOR anatomical location (NOT surgical approach)"
- ✅ **DO NOT examples**: "DO NOT return procedure locations like 'Craniotomy' or 'Skull' as surgical approach"

### 📊 Scope Change: Single-Event → Multi-Event

| Variable | Phase 1 | Phase 2 |
|----------|---------|---------|
| **Scope** | one_per_patient | many_per_note |
| **Instruction** | "Row 1 ONLY" | "ALL rows in table" |
| **Expected Count** | 1 extraction per variable | 2 extractions per variable |
| **Total Extractions** | 4 values | 8 values |

---

## Data Dictionary Tumor Location Values (24 Options)

From `tumor_location` field (checkbox type):

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
23. Skull (valid for skull-based tumors, NOT brain parenchymal)
24. Unavailable

**Note**: "Skull" IS valid for meningiomas/skull-based tumors, but NOT for brain tumors like pilocytic astrocytoma.

---

## Expected Phase 2 Results

### Target: 8/8 Correct (100%)

| Variable | Surgery 1 (2018-05-28) | Surgery 2 (2021-03-10) |
|----------|------------------------|------------------------|
| **surgery_date** | 2018-05-28 | 2021-03-10 |
| **surgery_type** | Tumor Resection | Tumor Resection |
| **surgery_extent** | Partial Resection | Partial Resection |
| **surgery_location** | Cerebellum/Posterior Fossa | Cerebellum/Posterior Fossa |

### Key Validation Points

✅ **Count**: 8 total extractions (4 variables × 2 surgeries)  
✅ **Location Format**: "Cerebellum/Posterior Fossa" (NOT "Skull" or "Posterior fossa")  
✅ **Title Case**: All dropdown values with proper casing  
✅ **Date Format**: YYYY-MM-DD  
✅ **Event Grouping**: Can match surgery 1 fields vs surgery 2 fields

---

## Upload Instructions

**Files**: `pilot_output/brim_csvs_iteration_3b_phase2/`
- variables.csv (4.9 KB, 4 variables)
- decisions.csv (40 B, header only)
- project.csv (3.3 MB, 45 documents)

**Expected Upload Message**:
```
Upload successful: variables.csv and decisions.csv.
4 variables configured.
0 skipped lines.
```

**Extraction Time**: ~10-15 minutes

---

## Critical Instruction Changes

### surgery_location (The Fix)

**Before** (Phase 1):
```
"Extract from Row 1 ONLY from 'Anatomical Location' column. 
Return as free text."
```

**After** (Phase 2):
```
"CRITICAL: Extract TUMOR anatomical location (NOT surgical 
approach/procedure location). Return EXACTLY one of these Data 
Dictionary values per surgery: 'Frontal Lobe', 'Temporal Lobe', 
..., 'Cerebellum/Posterior Fossa', ..., 'Skull', 'Unavailable'. 

DO NOT return procedure locations like 'Craniotomy' or surgical 
approaches. Look for tumor location in pathology, radiology, or 
operative notes describing WHERE the tumor is located (not where 
the incision is made)."
```

**Why This Works**:
1. ✅ option_definitions constrains to 24 valid values
2. ✅ CRITICAL prefix emphasizes tumor vs procedure
3. ✅ DO NOT examples exclude "Craniotomy", "Skull as procedure"
4. ✅ WHERE to look guidance directs to tumor location sources

---

## Success Metrics

| Metric | Phase 1 Actual | Phase 2 Target | Delta |
|--------|----------------|----------------|-------|
| **Accuracy** | 87.5% (3.5/4) | 100% (8/8) | +12.5% |
| **Location Correct** | ⚠️ Partial (50%) | ✅ 100% | +50% |
| **Extractions** | 4 values | 8 values | 2× |
| **Data Dict Alignment** | 75% (3/4) | 100% (4/4) | +25% |

---

## Next Actions

### For User:

1. **Upload to BRIM** (Project 21)
   - Navigate to https://brim.radiant-tst.d3b.io
   - Upload 3 CSV files from iteration_3b_phase2
   - Verify: "4 variables configured, 0 skipped"

2. **Run Extraction** (~15 min)
   - Click "Run Extraction"
   - Wait for completion
   - Download results CSV

3. **Share Results**
   - Provide results CSV to agent for validation
   - Expected: 8 rows (4 variables × 2 surgeries)

### For Agent (Automatic):

1. **Validate Accuracy**
   - Check 8/8 extractions correct
   - Verify location = "Cerebellum/Posterior Fossa" (NOT "Skull")
   - Confirm Title Case formatting

2. **Validate Event Grouping**
   - Test if surgery_date[0] matches surgery_type[0]
   - Check if row associations maintained

3. **Document Results**
   - Create PHASE_2_RESULTS_ANALYSIS.md
   - Update progress tracking
   - Recommend Phase 3 approach

---

**Status**: ✅ Ready for Testing  
**Expected Outcome**: 100% accuracy with data-dictionary-aligned location values  
**Key Fix**: Tumor location (NOT procedure location) with 24 checkbox options
