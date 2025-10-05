# Quick Reference - Iteration 2 Status

**Date**: October 3, 2025  
**Status**: ✅ Complete  
**Result**: 50% accuracy (same as iteration 1)

---

## TL;DR

We enhanced structured data extraction and updated 10 variables with PRIORITY instructions, but accuracy remained at 50%. **Root cause**: BRIM LLM may not be prioritizing STRUCTURED documents as intended.

---

## What Worked ✅

1. **Structured data extraction**: All components working perfectly
   - Demographics: ✅ Gender correct
   - Diagnosis: ✅ Name and date correct  
   - WHO Grade: ✅ Semantic match
2. **CSV generation**: 45 documents including 4 STRUCTURED
3. **API workflow**: Upload and download working
4. **Validation**: Automated testing against gold standard

## What Didn't Work ❌

1. **Molecular markers**: STRUCTURED document ignored, returned "wildtype" instead of "KIAA1549-BRAF"
2. **Surgery count**: Counted 28 procedures instead of 2 encounters
3. **Chemotherapy**: Found all 3 agents but added false "none identified"
4. **Tumor location**: Missing from extraction

---

## Files Created/Updated

### New Documentation
- `docs/ITERATION_2_COMPLETE_HANDOFF.md` - Full handoff guide (700+ lines)
- `docs/STRATEGIC_GOALS_STRUCTURED_DATA_PRIORITY.md` - 4 strategic goals
- `docs/POST_IMPLEMENTATION_REVIEW_IMAGING_CORTICOSTEROIDS.md` - Imaging deferral

### Results
- `pilot_output/iteration_2_results/extractions.csv` - 223 rows from BRIM
- `pilot_output/iteration_2_results/extractions_validation.json` - Validation results

### Configuration
- `pilot_output/brim_csvs_iteration_2/` - Enhanced CSVs with STRUCTURED docs

---

## Next Steps

### Immediate (Iteration 3)
1. **Investigate BRIM document prioritization**: Contact support or review docs
2. **Test alternative approaches**:
   - Move STRUCTURED docs to END instead of beginning
   - Embed structured data directly in clinical note text
   - Add visual markers like "⚠️ USE THIS DOCUMENT FIRST ⚠️"

### Target
- **75% accuracy minimum** (6/8 tests)
- **85% target** (7/8 tests)
- **Fix**: Molecular markers, surgery count, chemotherapy consistency

---

## Quick Commands

```bash
# Navigate to project
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Extract structured data
python3 scripts/extract_structured_data.py

# Generate BRIM CSVs
python3 scripts/pilot_generate_brim_csvs.py

# Download results (after BRIM extraction complete)
python3 scripts/simple_download_project_19.py

# Validate results
python3 scripts/automated_brim_validation.py \
  --results-csv pilot_output/iteration_2_results/extractions.csv \
  --validate-only
```

---

## Key Insights

1. **STRUCTURED documents may not be prioritized** by BRIM LLM
2. **Instruction format** (PRIORITY 1/2/3) may not be recognized
3. **Aggregation logic** (decisions.csv) not consistently applied
4. **Pre-computed structured data** works perfectly on our end, but BRIM doesn't use it

---

## Configuration

**BRIM Project 19 Key**: `ruoUS2kf1o_2JXhoqsl2SpBShwC4pC73yoohjjUpkfxrEfAY`  
**API Base URL**: `https://brim.radiant-tst.d3b.io`  
**Patient**: C1277724  

---

**Full Details**: See `docs/ITERATION_2_COMPLETE_HANDOFF.md`
