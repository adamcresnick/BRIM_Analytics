# Phase 1 Extraction - Quick Start Guide

**Status**: ✅ **READY TO UPLOAD AND RUN**  
**Date**: October 5, 2025  
**Patient**: C1277724

---

## 📦 What's Ready

### ✅ All Phase 1 Files Generated

1. **`project_phase1_tier1.csv`** (396 rows)
   - 71% reduction from original (1,373 → 396 rows)
   - 391 Tier 1 documents + 5 structured rows
   - Pathology, operative, consult, oncology/neurosurgery progress, imaging

2. **`variables_phase1.csv`** (25 variables)
   - 24% reduction from original (33 → 25 variables)
   - Excludes 8 Athena-prepopulated variables
   - Focus on note-extraction variables only

3. **`decisions.csv`** (existing, no changes)
   - Use current decisions.csv as-is

4. **`athena_prepopulated_values.json`** (8 variables)
   - Pre-populated from structured data
   - Will merge with extraction results after Phase 1

---

## 🚀 Upload to BRIM (3 Steps)

### Step 1: Rename Phase 1 Files

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2

# Copy Phase 1 files to BRIM upload names
cp project_phase1_tier1.csv project_brim_upload.csv
cp variables_phase1.csv variables_brim_upload.csv
cp decisions.csv decisions_brim_upload.csv
```

### Step 2: Upload to BRIM

**BRIM Project Name**: `BRIM_Pilot9_Phase1_Tier1`

**Upload these files**:
- `project_brim_upload.csv` → Upload as "project.csv"
- `variables_brim_upload.csv` → Upload as "variables.csv"
- `decisions_brim_upload.csv` → Upload as "decisions.csv"

### Step 3: Start Extraction

Click "Start Extraction" in BRIM

---

## 📊 Expected Results

### Volume & Performance

| Metric | Original (Stopped) | Phase 1 Expected |
|--------|-------------------|------------------|
| **Documents** | 3,865 | 391 (90% reduction) |
| **Project rows** | 1,373 | 396 (71% reduction) |
| **Variables** | 33 (12 started) | 25 |
| **Est. extraction rows** | ~40,149 | ~5,000-7,000 |
| **Est. time** | 10-15 hours | 2-4 hours |
| **Est. cost** | $150-300 | $50-80 |

### Quality Expectations

- **Extraction success rate**: 95-100% (based on partial extraction: 99.8%)
- **Variable completeness**: 80-90% (20-23 of 25 variables with data)
- **Gold standard match**: ≥95% (where Athena comparison available)

---

## ⏱️ Monitoring During Extraction

### Check These Points

**After 30 minutes**:
- [ ] Extraction progressing normally
- [ ] No error messages
- [ ] Variables being extracted: 25 (not 33)

**After 1 hour**:
- [ ] Progress: ~25-30% complete
- [ ] Row count: ~1,000-1,500 rows
- [ ] Extraction quality looks good

**After 2 hours**:
- [ ] Progress: ~50-60% complete
- [ ] Row count: ~2,500-3,500 rows
- [ ] No stalled variables

**After 3-4 hours**:
- [ ] Extraction complete
- [ ] Total rows: ~5,000-7,000
- [ ] Ready to download results

---

## 📥 After Extraction Completes

### Step 1: Download Results

**Download**: BRIM extraction results  
**Save as**: `phase1_extraction_results.csv`

```bash
# Move download to working directory
mv ~/Downloads/BRIM_Pilot9_Phase1_Tier1_Export.csv \
   /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_extraction_results.csv
```

### Step 2: Quick Quality Check

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2

# Check row count
wc -l phase1_extraction_results.csv

# Check variable distribution
python3 << 'PYEOF'
import pandas as pd
df = pd.read_csv('phase1_extraction_results.csv')
print(f"Total rows: {len(df)}")
print(f"Unique variables: {df['Name'].nunique()}")
print("\nVariable extraction counts:")
print(df['Name'].value_counts())
PYEOF
```

**Expected**:
- Total rows: 5,000-7,000
- Unique variables: 25
- Each variable: 100-500 extraction attempts

### Step 3: Merge with Athena Pre-populated Variables

```bash
python3 << 'PYEOF'
import pandas as pd
import json

# Load Phase 1 extraction
phase1_df = pd.read_csv('phase1_extraction_results.csv')
print(f"Phase 1 rows: {len(phase1_df)}")
print(f"Phase 1 variables: {phase1_df['Name'].nunique()}")

# Load Athena pre-populated values
with open('athena_prepopulated_values.json', 'r') as f:
    athena_data = json.load(f)

print(f"\nAthena variables: {len(athena_data)}")
for var_name in athena_data.keys():
    print(f"  - {var_name}")

# Note: Actual merging logic would create BRIM-formatted rows for Athena variables
# For now, we have both datasets ready for validation
print("\n✅ Phase 1 + Athena data ready for validation")
PYEOF
```

---

## 📊 Validation Assessment

### Quick Completeness Check

```bash
python3 << 'PYEOF'
import pandas as pd

df = pd.read_csv('phase1_extraction_results.csv')

# Calculate completeness for each variable
print("=" * 80)
print("PHASE 1 VARIABLE COMPLETENESS")
print("=" * 80)

for var_name in sorted(df['Name'].unique()):
    var_df = df[df['Name'] == var_name]
    total = len(var_df)
    with_value = var_df['Value'].notna().sum()
    pct = with_value / total * 100 if total > 0 else 0
    
    status = "✅" if pct >= 80 else "⚠️" if pct >= 50 else "❌"
    print(f"{status} {var_name:<45} {with_value:>4}/{total:>4} ({pct:>5.1f}%)")

# Summary
complete_vars = df.groupby('Name')['Value'].apply(lambda x: (x.notna().sum() / len(x)) >= 0.8).sum()
total_vars = df['Name'].nunique()

print("\n" + "=" * 80)
print(f"Complete variables (≥80%): {complete_vars} / {total_vars}")
print(f"Athena variables: 8 (pre-populated)")
print(f"Total coverage: {complete_vars + 8} / 33 variables")
PYEOF
```

**Interpretation**:
- **✅ Complete (≥80%)**: Variable successfully extracted, good coverage
- **⚠️ Partial (50-79%)**: Variable found but incomplete, may need Phase 2
- **❌ Incomplete (<50%)**: Variable not well captured, needs Phase 2

### Decision: Phase 2 Needed?

**If ≥20 variables complete (≥80% coverage)**:
- ✅ **Success!** Phase 1 sufficient
- Proceed to: Final data assembly and validation
- No Phase 2 needed

**If 15-19 variables complete**:
- ⚠️ **Partial success** - Identify incomplete variables
- Proceed to: Phase 2 for specific variables
- Expected time: 1-2 hours additional

**If <15 variables complete**:
- ❌ **Needs review** - Check extraction quality
- Investigate: Instruction clarity, document quality
- Consider: Revising variable instructions before Phase 2

---

## 📝 Next Steps Based on Results

### If Phase 1 Sufficient (≥20/25 variables complete)

```bash
# 1. Document Phase 1 success
echo "Phase 1 extraction complete and sufficient" > phase1_outcome.txt
echo "Complete variables: X / 25" >> phase1_outcome.txt
echo "With Athena: Y / 33 total" >> phase1_outcome.txt

# 2. Commit Phase 1 results
git add phase1_extraction_results.csv
git add phase1_outcome.txt
git commit -m "feat: Phase 1 extraction complete - X/25 variables captured"

# 3. Proceed to final validation and gold standard comparison
```

### If Phase 2 Needed (<20/25 variables complete)

```bash
# 1. Identify incomplete variables
python3 << 'PYEOF'
import pandas as pd
df = pd.read_csv('phase1_extraction_results.csv')

incomplete_vars = []
for var_name in df['Name'].unique():
    var_df = df[df['Name'] == var_name]
    completion = var_df['Value'].notna().sum() / len(var_df)
    if completion < 0.8:
        incomplete_vars.append(var_name)

print("Variables needing Phase 2:")
for var in incomplete_vars:
    print(f"  - {var}")

with open('phase2_target_variables.txt', 'w') as f:
    f.write('\n'.join(incomplete_vars))
PYEOF

# 2. Generate Phase 2 documents (Tier 2 expansion)
python3 scripts/generate_tier2_project.py \
  --metadata pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files_comprehensive_metadata.csv \
  --project pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv \
  --phase1-docs pilot_output/brim_csvs_iteration_3c_phase3a_v2/project_phase1_tier1.csv \
  --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/project_phase2_tier2.csv

# 3. Generate Phase 2 variables (incomplete vars only)
python3 scripts/generate_phase2_variables.py \
  --variables pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables.csv \
  --incomplete-vars phase2_target_variables.txt \
  --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables_phase2.csv

# 4. Upload Phase 2 to BRIM and extract
# 5. Merge Phase 1 + Phase 2 results
```

---

## 🎯 Success Indicators

### Phase 1 is Successful If:

- [ ] Extraction completes in 2-4 hours ✓
- [ ] Total rows: 5,000-7,000 ✓
- [ ] Variables extracted: 25 ✓
- [ ] **Complete variables: ≥20 of 25 (≥80%)** ✓
- [ ] Extraction quality: ≥95% success rate ✓
- [ ] No major errors or issues ✓

### Combined Phase 1 + Athena Coverage:

- Phase 1: 20-25 variables (note extraction)
- Athena: 8 variables (pre-populated)
- **Total: 28-33 of 33 variables** ✓

---

## 📞 Quick Reference Commands

### Check extraction status
```bash
# Row count
wc -l phase1_extraction_results.csv

# Variable count
cut -d',' -f1 phase1_extraction_results.csv | sort | uniq | wc -l

# Completeness summary
python3 -c "import pandas as pd; df=pd.read_csv('phase1_extraction_results.csv'); print(df['Name'].value_counts())"
```

### Commit Phase 1 results
```bash
git add pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_extraction_results.csv
git add pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_outcome.txt
git commit -m "feat: Phase 1 extraction complete - Y/25 variables captured"
git push
```

---

## 📚 Documentation Reference

- **Strategy**: `ITERATIVE_EXTRACTION_STRATEGY.md`
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`
- **This guide**: `PHASE1_QUICK_START.md`

---

**Ready to Execute**: ✅ Upload files and start extraction  
**Expected Duration**: 2-4 hours  
**Next Review**: After extraction completes, run validation assessment
