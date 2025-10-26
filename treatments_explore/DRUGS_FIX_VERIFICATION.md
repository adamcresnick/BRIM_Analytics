# Drugs Fix Verification Report

**Date**: 2025-10-26
**Purpose**: Verify that fix_drugs_normalization.py covers ALL problematic drugs found in paradigm validation

## Summary

✓ **ALL 21 problematic drugs from paradigm validation are covered by the fix**
⚠ **Additional issue identified: Triamcinolone** (107 patients, 25 paradigms) - needs clinical decision

## Problematic Drugs from Validation

### Brand/Generic Duplicates (11 drugs)
| Brand Name | Generic Name | Fix Status | Expected Result |
|------------|--------------|------------|-----------------|
| afinitor | everolimus | ✓ COVERED | Both → 'everolimus' |
| tafinlar | dabrafenib | ✓ COVERED | Both → 'dabrafenib' |
| mekinist | trametinib | ✓ COVERED | Both → 'trametinib' |
| lupron depot | leuprolide | ✓ COVERED | Both → 'leuprolide' |
| koselugo | selumetinib | ✓ COVERED | Both → 'selumetinib' |
| vitrakvi | larotrectinib | ✓ COVERED | Both → 'larotrectinib' |

### Biosimilar Duplicates (3 brand names)
| Brand Name | Generic Name | Fix Status | Expected Result |
|------------|--------------|------------|-----------------|
| fulphila | pegfilgrastim | ✓ COVERED | Both → 'pegfilgrastim' |
| zarxio | filgrastim | ✓ COVERED | Both → 'filgrastim' |
| nivestym | filgrastim | ✓ COVERED | Both → 'filgrastim' |

### Formulation Duplicates (1 pair)
| Brand/Formulation | Generic | Fix Status | Expected Result |
|-------------------|---------|------------|-----------------|
| etopophos | etoposide | ✓ COVERED | Both → 'etoposide' |

### Supportive Care Drugs (2 brand names)
| Brand Name | Generic Name | Fix Status | Expected Result |
|------------|--------------|------------|-----------------|
| zofran | ondansetron | ✓ COVERED | Both → 'ondansetron', is_supportive_care=True |
| emend | aprepitant | ✓ COVERED | Both → 'aprepitant', is_supportive_care=True |

### Generic Names (no fix needed, kept as-is)
- everolimus, dabrafenib, trametinib, leuprolide, larotrectinib, selumetinib
- etoposide, filgrastim, pegfilgrastim

## Expected Impact After Fix

### Paradigm Issues That Will Be Resolved

**Therapeutic Duplicates (13 issues → 0 expected)**:
- P007: dabrafenib + tafinlar + mekinist + trametinib → All collapse to dabrafenib + trametinib ✓
- P064: Same as P007 → Will collapse ✓
- P008: leuprolide + lupron depot → Will collapse to leuprolide ✓
- P038: afinitor + everolimus → Will collapse to everolimus ✓
- P049: larotrectinib + vitrakvi → Will collapse to larotrectinib ✓
- P053: koselugo + selumetinib → Will collapse to selumetinib ✓
- P061: Same as P053 → Will collapse ✓
- C081: fulphila + pegfilgrastim → Will collapse to pegfilgrastim ✓
- C098: etopophos + etoposide → Will collapse to etoposide ✓
- C211: filgrastim + zarxio → Will collapse to filgrastim ✓
- P031: filgrastim + nivestym → Will collapse to filgrastim ✓

**Supportive Care Contamination (6 issues → 0 expected)**:
- C214: bevacizumab + emend → emend will be excluded ✓
- C225: cyclophosphamide + emend → emend will be excluded ✓
- C226: emend + vincristine → emend will be excluded ✓
- C228: emend + temozolomide → emend will be excluded ✓
- P012: carboplatin + vincristine + zofran → zofran will be excluded ✓
- P056: triamcinolone + zofran → zofran will be excluded ✓

**Total Patients Benefiting from Fix**: 91 patients (64 from duplicates + 27 from supportive care)

## Additional Issue: Triamcinolone

### Current Status
- **Occurrences**: 2,151 records in extracted data
- **Patients Affected**: 107 patients across 25 paradigms
- **Current Categorization**: `drug_category='chemotherapy'`, `is_supportive_care=False`
- **Actual Use**: Corticosteroid used for managing edema/inflammation (supportive care)

### Paradigms Affected
Top 10 paradigms with triamcinolone:
1. C091 (12 patients): doxorubicin + triamcinolone
2. C092 (11 patients): leucovorin + triamcinolone
3. C093 (11 patients): dexrazoxane + triamcinolone
4. C120 (9 patients): cytarabine + triamcinolone
5. C129 (8 patients): irinotecan + triamcinolone
6. C146 (7 patients): dactinomycin + triamcinolone
7. C218 (6 patients): mekinist + triamcinolone
8. P009 (5 patients): tretinoin + triamcinolone
9. P014 (4 patients): testosterone cypionate + triamcinolone
10. P020 (3 patients): atra + triamcinolone

### Clinical Context

**Typical Uses of Triamcinolone**:
1. **Supportive Care** (most common in pediatric oncology):
   - Managing cerebral edema from brain tumors
   - Reducing inflammation from chemotherapy side effects
   - Treating allergic reactions
   - Managing skin conditions

2. **Therapeutic** (rare):
   - Intralesional injection for certain skin cancers
   - Part of some lymphoma regimens (very uncommon)

### Current Fix Behavior

The fix script identifies triamcinolone as a CORTICOSTEROID but does NOT mark it as supportive_care:

```python
CORTICOSTEROIDS = {
    'dexamethasone', 'prednisone', 'prednisolone', 'methylprednisolone',
    'hydrocortisone', 'triamcinolone', 'betamethasone'
}

def categorize_drug(row):
    if therapeutic_norm in CORTICOSTEROIDS:
        # If it's already categorized as chemotherapy, it's likely being used therapeutically
        # We'll keep the category but users should filter based on context
        if therapeutic_norm == 'dexamethasone':
            return 'supportive_care', True
        return current_category, False  # Not purely supportive care
```

**Why dexamethasone gets special treatment**:
- Dexamethasone is explicitly marked in sources as 'Supportive_Care'
- Dexamethasone IS used therapeutically in lymphoma regimens
- But dexamethasone is MORE commonly used as supportive care

**Why triamcinolone doesn't**:
- Not marked in sources as 'Supportive_Care'
- Current category is 'chemotherapy'
- Fix assumes if categorized as chemotherapy, it's therapeutic

### Recommendation: Clinical Decision Required

**Option 1: Mark triamcinolone as supportive_care (RECOMMENDED)**
- Rationale: In pediatric oncology context, triamcinolone is primarily used for edema/inflammation management
- Impact: Will exclude triamcinolone from paradigm analysis
- Risk: If any patients were receiving therapeutic triamcinolone, it will be missed
- Implementation: Add to SUPPORTIVE_CARE_GENERICS or add special case like dexamethasone

**Option 2: Keep current behavior (NOT RECOMMENDED)**
- Rationale: Preserve all corticosteroids for manual review
- Impact: 25 paradigms will still contain triamcinolone (107 patients)
- Risk: Paradigms contaminated with supportive care drugs
- Implementation: No changes to fix script

**Option 3: Context-based filtering (COMPLEX)**
- Rationale: Filter based on concurrent drugs or indication codes
- Impact: More accurate but requires additional logic
- Risk: Implementation complexity
- Implementation: Post-processing filter in paradigm analysis

### Proposed Fix Update

If choosing Option 1, update fix_drugs_normalization.py:

```python
# EITHER: Add to SUPPORTIVE_CARE_GENERICS
SUPPORTIVE_CARE_GENERICS = {
    # Antiemetics
    'ondansetron', 'granisetron', 'dolasetron', 'palonosetron',
    'aprepitant', 'fosaprepitant', 'rolapitant',
    'metoclopramide', 'prochlorperazine',

    # Corticosteroids used primarily for supportive care
    'triamcinolone',  # ← ADD THIS

    # Antihistamines
    'diphenhydramine', 'hydroxyzine',
}

# OR: Add special case in categorize_drug()
if therapeutic_norm in CORTICOSTEROIDS:
    # Special cases: dexamethasone and triamcinolone primarily supportive
    if therapeutic_norm in ('dexamethasone', 'triamcinolone'):
        return 'supportive_care', True
    return current_category, False
```

## Other Corticosteroids in Data

Should also check if other corticosteroids need the same treatment:
- prednisone
- prednisolone
- methylprednisolone
- hydrocortisone
- betamethasone

These may also be primarily supportive care in pediatric oncology context.

## Validation Plan

After deploying the fix:

1. **Re-run paradigm validation**:
   ```bash
   python3 validate_paradigms_rxnorm.py
   ```

2. **Expected results**:
   - ✓ 0 RxNorm duplicates
   - ✓ 0 therapeutic duplicates
   - ✓ 0 supportive care contamination (if triamcinolone addressed)
   - ⚠ 25 paradigms with triamcinolone (if not addressed)

3. **Check paradigm reduction**:
   - Current: 280 paradigms
   - Expected: ~260-265 paradigms (duplicates collapsed)
   - Expected: ~235-240 paradigms (if triamcinolone excluded)

## Files Modified

### Created
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/data_dictionary/chemo_reference/fix_drugs_normalization.py`
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore/validate_paradigms_rxnorm.py`
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore/FILTERING_FAILURE_ROOT_CAUSE_ANALYSIS.md`
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/treatments_explore/DRUGS_FIX_VERIFICATION.md` (this file)

### Will Modify
- `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/data_dictionary/chemo_reference/drugs.csv` (when fix script runs)

## Status

- ✓ Fix script covers all 21 problematic drugs from validation
- ✓ Fix has already been run and drugs.csv updated
- ⚠ **CLINICAL DECISION NEEDED**: Should triamcinolone be marked as supportive_care?
- ⏳ Awaiting decision before deploying to S3 and re-running pipeline

---

**Next Steps**:
1. **Decide on triamcinolone treatment** (Option 1, 2, or 3)
2. Update fix script if needed
3. Deploy fixed drugs.csv to S3
4. Recreate Athena external table
5. Re-extract chemotherapy data
6. Re-run paradigm analysis
7. Validate results with validate_paradigms_rxnorm.py
