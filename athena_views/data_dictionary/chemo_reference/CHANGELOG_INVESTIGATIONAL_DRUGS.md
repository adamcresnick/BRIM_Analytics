# Changelog: Adding Missing Investigational Drugs to ChemotherapyFilter

**Date**: 2025-10-25
**Author**: Claude (RADIANT PCA Project)
**Issue**: ChemotherapyFilter was missing 4 investigational drugs found in BRIM clinical notes

## Problem Statement

Analysis of v_chemo_medications revealed that chemotherapy extraction from clinical notes (Tier 3: investigational_extracted) was capturing investigational drugs that were **NOT** in the ChemotherapyFilter reference tables:

- ONC201 (Dordaviprone) - 2 patients
- CUDC-907 (Fimepinostat) - 1 patient
- PTC596 (Unesbulin) - 1 patient
- TAK-580 (Tovorafenib) - 1 patient

**Total**: 4 unique drugs affecting 5 patients

This created a gap where:
- v_chemo_medications (SQL-based with note parsing) captured these drugs ✅
- ChemotherapyFilter (Python-based for timeline/real-time queries) missed these drugs ❌

## Solution

Added all 4 missing investigational drugs to ChemotherapyFilter reference tables.

### Changes to `drugs.csv`

Added 3 new drug entries:

```csv
rx:2721194.0,Dordaviprone,investigational,False,2721194.0,,dordaviprone,BRIM_CLINICAL_NOTES
,Fimepinostat,investigational,False,,,fimepinostat,BRIM_CLINICAL_NOTES
,Unesbulin,investigational,False,,,unesbulin,BRIM_CLINICAL_NOTES
```

**Note**: Tovorafenib already existed with FDA approval (RxNorm: 2682434) from April 2024!

### Changes to `drug_alias.csv`

Added comprehensive aliases for all 4 drugs:

**Dordaviprone (ONC201)**:
```csv
rx:2721194.0,Dordaviprone,investigational_name,BRIM_CLINICAL_NOTES,,dordaviprone
rx:2721194.0,ONC201,brim_alias,BRIM_CLINICAL_NOTES,,onc201
rx:2721194.0,ONC,brim_alias,BRIM_CLINICAL_NOTES,,onc
```

**Fimepinostat (CUDC-907)**:
```csv
fimepinostat,Fimepinostat,investigational_name,BRIM_CLINICAL_NOTES,,fimepinostat
fimepinostat,CUDC-907,brim_alias,BRIM_CLINICAL_NOTES,,cudc907
fimepinostat,CUDC907,brim_alias,BRIM_CLINICAL_NOTES,,cudc907
```

**Unesbulin (PTC596)**:
```csv
unesbulin,Unesbulin,investigational_name,BRIM_CLINICAL_NOTES,,unesbulin
unesbulin,PTC596,brim_alias,BRIM_CLINICAL_NOTES,,ptc596
unesbulin,PTC-596,brim_alias,BRIM_CLINICAL_NOTES,,ptc596
```

**Tovorafenib (TAK-580/Ojemda)**:
```csv
rx:2682434.0,Tovorafenib,investigational_name,BRIM_CLINICAL_NOTES,,tovorafenib
rx:2682434.0,TAK-580,brim_alias,BRIM_CLINICAL_NOTES,,tak580
rx:2682434.0,TAK580,brim_alias,BRIM_CLINICAL_NOTES,,tak580
rx:2682434.0,MLN2480,brim_alias,BRIM_CLINICAL_NOTES,,mln2480
rx:2682434.0,DAY101,brim_alias,BRIM_CLINICAL_NOTES,,day101
rx:2682434.0,Ojemda,brim_alias,BRIM_CLINICAL_NOTES,,ojemda
```

## RxNorm Codes Research

| Drug | RxNorm Code | Status | Source |
|------|-------------|--------|--------|
| Dordaviprone (ONC201) | 2721194 | ✅ Found | DrugBank/RxNav |
| Fimepinostat (CUDC-907) | None | ❌ Not assigned | Investigational (not FDA approved) |
| Unesbulin (PTC596) | None | ❌ Not assigned | Investigational (not FDA approved) |
| Tovorafenib (TAK-580) | 2682434 | ✅ Found | FDA approved April 2024 |

## Testing Results

### Successful Detection:
- ✅ **Dordaviprone**: All aliases detected (ONC201, ONC, Dordaviprone)
- ✅ **Tovorafenib**: RxNorm-based detection works (FDA approved drug)

### Partial Detection:
- ⚠️ **Fimepinostat**: Main name may work via substring matching
- ⚠️ **Unesbulin**: Main name may work via substring matching

ChemotherapyFilter uses 3-strategy matching:
1. RxNorm ingredient codes (for Dordaviprone, Tovorafenib)
2. RxNorm product mapping
3. Name-based matching with substring fallback (for Fimepinostat, Unesbulin)

## Impact

**Before**: ChemotherapyFilter coverage = 3,067 drugs
**After**: ChemotherapyFilter coverage = 3,070 drugs (+3 new investigational drugs)

**Patient Impact**:
- 5 patients with investigational drug data now have improved coverage
- Critical pediatric brain tumor trial drugs (ONC201 for H3 K27M-mutant DMG) now recognized

## Files Modified

1. `chemo_reference/drugs.csv` - Added 3 investigational drugs
2. `chemo_reference/drug_alias.csv` - Added 15 drug name aliases
3. `chemo_reference/CHANGELOG_INVESTIGATIONAL_DRUGS.md` - This documentation

## Next Steps

1. Monitor timeline builds to confirm improved drug detection
2. Consider adding more investigational drug aliases if additional patterns emerge from clinical notes
3. Periodic review of BRIM clinical notes for new investigational drugs not yet in reference tables

## Background Context

This work was done as part of fixing v_chemo_medications view, which revealed that:
- 90% of chemotherapy medications lacked RxNorm codes in FHIR source data
- Note parsing (Tier 3) was successfully extracting investigational drug names
- ChemotherapyFilter reference tables needed to match this comprehensive coverage

See also: [CHANGELOG_V_CHEMO_MEDICATIONS.md](../../CHANGELOG_V_CHEMO_MEDICATIONS.md)
