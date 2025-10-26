# Treatment Paradigm Filtering Failure: Root Cause Analysis

**Date**: 2025-10-26
**Analyst**: Claude (AI Assistant)
**Issue**: Treatment paradigms contained brand/generic duplicates and supportive care drugs

## Executive Summary

The treatment paradigm analysis extracted **280 paradigms** from v_chemo_medications, but many contained:
1. **Brand/generic duplicates** (e.g., "mekinist, tafinlar, dabrafenib, trametinib")
2. **Supportive care drugs** (e.g., "zofran", "emend", "triamcinolone")
3. **Biosimilar duplicates** (e.g., "fulphila, pegfilgrastim")

**Root Cause**: The `therapeutic_normalized` column in drugs.csv was **never actually populated with brand→generic mappings**, despite commit messages claiming it would. Additionally, supportive care brand names were miscategorized as chemotherapy.

## Problem Discovery Timeline

### Initial Symptoms
User reviewed [treatment_paradigms.json](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore/data/treatment_paradigms/treatment_paradigms.json) and found:

**P007**: dabrafenib, mekinist, tafinlar, trametinib (6 patients)
- Contains BOTH brand names (Mekinist, Tafinlar) AND generic names (trametinib, dabrafenib)

**P012**: carboplatin, vincristine, zofran (4 patients)
- Contains antiemetic "zofran" which is supportive care, not chemotherapy

**P056**: triamcinolone, zofran (2 patients)
- Contains ONLY supportive care drugs (corticosteroid + antiemetic)

### Investigation Questions

User requested: "can you first deeply review our previous effort to filter and label these correctly and why they have failed?"

## Root Cause Analysis

### 1. therapeutic_normalized Field NEVER Normalized Brand→Generic

#### The Intention (from commit 162f19b)
Commit message stated:
```
Applied normalization function that handles:
* Brand → generic mappings
* Biosimilar suffixes (-awwb, -xxxx, etc.)
* Salt forms (hydrochloride, sulfate, etc.)
```

#### The Reality
The actual normalization function **only implemented salt/biosimilar removal**, NOT brand→generic mapping:

```python
# What it actually did:
"Irinotecan Hydrochloride" → "irinotecan"  # Salt removal ✓
"bevacizumab-awwb" → "bevacizumab"  # Biosimilar ✓
"Mekinist" → "mekinist"  # NO CHANGE ✗ (should be → "trametinib")
"Afinitor" → "afinitor"  # NO CHANGE ✗ (should be → "everolimus")
```

#### Evidence from drugs.csv
```csv
drug_id,preferred_name,therapeutic_normalized
rx:845509.0,Afinitor,afinitor        # WRONG: should be "everolimus"
rx:141704.0,everolimus,everolimus    # Separate entry!
rx:1425105.0,Mekinist,mekinist       # WRONG: should be "trametinib"
rx:1425099.0,trametinib,trametinib   # Separate entry!
rx:1425223.0,Tafinlar,tafinlar       # WRONG: should be "dabrafenib"
rx:1424911.0,dabrafenib,dabrafenib  # Separate entry!
```

**Impact**: Brand and generic names treated as different drugs, creating duplicate paradigms.

### 2. Supportive Care Brand Names Miscategorized

#### The Data Inconsistency
drugs.csv had **TWO versions** of same supportive care drug:

**Generic (from FDA_v24)**: Correctly categorized
```csv
rx:26225.0,ondansetron,FDA_v24|Supportive_Care,supportive_care,ondansetron
rx:358255.0,aprepitant,FDA_v24|Supportive_Care,supportive_care,aprepitant
```

**Brand (from FDA_old)**: Incorrectly categorized
```csv
rx:66981.0,Zofran,FDA_old,chemotherapy,zofran        # WRONG category
rx:357280.0,Emend,FDA_old,chemotherapy,emend         # WRONG category
```

#### Why This Happened
- FDA_v24 dataset included proper Supportive_Care source flags
- FDA_old dataset (older) lacked supportive care classifications
- Both were merged into drugs.csv without reconciliation
- Brand names defaulted to `drug_category='chemotherapy'`

### 3. V_CHEMO_MEDICATIONS Filter Ineffective

[V_CHEMO_MEDICATIONS.sql:37-39](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/V_CHEMO_MEDICATIONS.sql#L37-L39):
```sql
WHERE cd.drug_category IN ('chemotherapy', 'targeted_therapy', 'immunotherapy', 'hormone_therapy')
```

**Intended**: Exclude supportive_care category
**Reality**: Brand names like Zofran had `drug_category='chemotherapy'`, so they passed through!

### 4. chemotherapy_filter.py Exclusion Failed

[chemotherapy_filter.py:86-115](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/data_dictionary/chemotherapy_filter.py#L86-L115):
```python
supportive_care_drugs = self.drugs_df[
    self.drugs_df['sources'].str.contains('Supportive_Care', na=False)
]
```

**Intended**: Exclude drugs with 'Supportive_Care' in sources
**Reality**:
- `ondansetron` (generic): sources=`'FDA_v24|Supportive_Care'` → Excluded ✓
- `Zofran` (brand): sources=`'FDA_old'` → NOT Excluded ✗

## Data Extraction Path Analysis

### How Patients Got Supportive Care in Paradigms

1. **FHIR Data**: Patient received medication coded as "Zofran" (brand name)
2. **RxNorm Match**: Matched to drugs.csv row for "Zofran" (not "ondansetron")
3. **Category Check**: Zofran has `drug_category='chemotherapy'` → Passes filter
4. **Normalization**: `therapeutic_normalized='zofran'` (not normalized to 'ondansetron')
5. **Paradigm Analysis**: Grouped as unique drug "zofran" separate from "ondansetron"

## Complete Impact Assessment

### Problematic Paradigms Identified

**Brand/Generic Duplicates (21 paradigms)**:
- P007, P008, P038, P049, P053: Brand + generic for same drug
- C081/C082: fulphila + pegfilgrastim (biosimilar duplicate)
- C097/C098: zarxio + filgrastim (biosimilar duplicate)
- C207/C208: nivestym + filgrastim (biosimilar duplicate)
- C276: cabozantinib + cabozantinib s-malate (salt duplicate)

**Supportive Care Contamination (8 paradigms)**:
- P012: carboplatin, vincristine, **zofran**
- P056: **triamcinolone, zofran**
- C214: cisplatin, **dexamethasone**
- C225/C226/C228: Various drugs + **ondansetron** or **zofran**

**Corticosteroid Artifacts (15+ paradigms)**:
- P009, P014, P020, P034, P043, P044, P048, P054, P066, etc.
- Contain **triamcinolone** (used for edema/side effects, not therapeutic)

### Data Volume Impact

From [chemotherapy_all_patients_filtered_therapeutic_fixed.csv](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore/data/chemotherapy_all_patients_filtered_therapeutic_fixed.csv):

**Total records**: 134,606

**Supportive care contamination**:
- zofran: 207 records (0.15%)
- emend: 152 records (0.11%)
- triamcinolone: 2,151 records (1.60%)
- **Total supportive care**: ~2,510 records (1.9%)

**Brand name duplicates** (estimated):
- afinitor: 64 records (duplicates everolimus)
- mekinist: 854 records (duplicates trametinib)
- tafinlar: 396 records (duplicates dabrafenib)
- koselugo: 276 records (duplicates selumetinib)
- Others: ~500 records
- **Total brand duplicates**: ~2,090 records (1.6%)

## The Fix

### fix_drugs_normalization.py

Created Python script that:

1. **Implements True Brand→Generic Mapping**:
```python
BRAND_TO_GENERIC = {
    # Antiemetics
    'zofran': 'ondansetron',
    'emend': 'aprepitant',
    'aloxi': 'palonosetron',

    # Targeted therapy
    'afinitor': 'everolimus',
    'mekinist': 'trametinib',
    'tafinlar': 'dabrafenib',
    'koselugo': 'selumetinib',
    'vitrakvi': 'larotrectinib',

    # Hormone therapy
    'lupron depot': 'leuprolide',
    'casodex': 'bicalutamide',

    # Biosimilars
    'fulphila': 'pegfilgrastim',
    'zarxio': 'filgrastim',
    'nivestym': 'filgrastim',

    # 30+ more brand names...
}
```

2. **Fixes Supportive Care Categorization**:
```python
SUPPORTIVE_CARE_GENERICS = {
    'ondansetron', 'granisetron', 'palonosetron',
    'aprepitant', 'fosaprepitant', 'rolapitant',
    'metoclopramide', 'prochlorperazine',
    'diphenhydramine', 'hydroxyzine',
}

def categorize_drug(row):
    # Whitelist approach: only mark as supportive if genuinely supportive
    if therapeutic_norm in SUPPORTIVE_CARE_GENERICS:
        return 'supportive_care', True

    if preferred_name in BRAND_TO_GENERIC:
        if BRAND_TO_GENERIC[preferred_name] in SUPPORTIVE_CARE_GENERICS:
            return 'supportive_care', True
```

3. **Preserves Special Formulations**:
   - Liposomal (doxorubicin liposomal ≠ doxorubicin)
   - Pegylated (pegfilgrastim ≠ filgrastim)
   - Albumin-bound (abraxane = paclitaxel albumin-bound ≠ paclitaxel)

### Results After Fix

**Normalization changes**: 104 drugs
- Afinitor → everolimus
- Mekinist → trametinib
- Tafinlar → dabrafenib
- Zofran → ondansetron
- Emend → aprepitant
- 99 more...

**Categorization changes**: 14 drugs
- Zofran: chemotherapy → **supportive_care**, is_supportive_care=**True**
- Emend: chemotherapy → **supportive_care**, is_supportive_care=**True**
- Aloxi: chemotherapy → **supportive_care**, is_supportive_care=**True**
- 11 more antiemetics and antihistamines

**Normalization collapse**:
- Original drugs: 2,968
- Unique normalized names: 2,801 (was 2,826 before fix)
- Variants collapsed: 167 (was 142 before fix)
- Reduction: 5.6% (vs 4.8% before)

## Recommendations

### Immediate Actions

1. **Deploy Fixed drugs.csv to S3**:
```bash
aws s3 cp drugs.csv s3://aws-athena-query-results-343218191717-us-east-1/chemotherapy-reference-data/
```

2. **Recreate External Table in Athena**:
```sql
-- Run: athena_views/views/CREATE_CHEMOTHERAPY_DRUGS_TABLE.sql
```

3. **Re-extract Chemotherapy Data**:
```bash
python3 treatments_explore/scripts/extract_chemotherapy_fresh.py
```

4. **Re-run Paradigm Analysis**:
```bash
python3 treatments_explore/scripts/empirical_treatment_paradigm_analysis.py
```

### Post-Fix Validation

Expected improvements:
- ✓ 0 brand/generic duplicate paradigms
- ✓ 0 supportive care-only paradigms
- ✓ Supportive care drugs excluded from extraction
- ✓ ~10-15% reduction in paradigm count (duplicates collapsed)
- ✓ More accurate patient assignments (no false regimen matches)

### Long-term Improvements

1. **Unified Index Audit**:
   - Review `/Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index/`
   - Fix dacarbazine and procarbazine having "Supportive_Care" source flag
   - Ensure FDA_old entries are reconciled with FDA_v24

2. **Automated Validation**:
   - Add CI/CD checks for drugs.csv:
     - All brand names map to generics in therapeutic_normalized
     - No drugs with same RxNorm_in have different therapeutic_normalized
     - All known antiemetics/antihistamines have is_supportive_care=True

3. **Corticosteroid Handling**:
   - Need context-aware classification for dexamethasone, prednisone, etc.
   - When used in lymphoma regimens → therapeutic (keep)
   - When used for antiemetic/edema → supportive care (exclude)
   - May require analysis of concurrent drugs or indication codes

## Lessons Learned

1. **Test Normalization with Known Cases**: Should have validated Afinitor→everolimus before deploying
2. **Reconcile Duplicate Sources**: FDA_old vs FDA_v24 inconsistencies should be resolved at ingestion
3. **Explicit Validation Tests**: Add unit tests for brand→generic mappings
4. **Document Field Semantics**: therapeutic_normalized column purpose was unclear
5. **Source Data Verification**: Always query source FHIR tables, don't assume CSV is correct

## Files Modified

### Created
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/data_dictionary/chemo_reference/fix_drugs_normalization.py`
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore/FILTERING_FAILURE_ROOT_CAUSE_ANALYSIS.md` (this file)

### Modified
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/data_dictionary/chemo_reference/drugs.csv`
  - 104 therapeutic_normalized values updated
  - 14 drug_category and is_supportive_care flags corrected

### Backup
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/data_dictionary/chemo_reference/drugs_before_fix.csv`

---

**Status**: Root cause identified and fixed. Awaiting deployment and validation.
**Next Step**: Deploy fixed drugs.csv and re-run full pipeline.
