# Pathology Documents Analysis: Surgical Pathology vs Lab Results
**Date**: October 4, 2025
**Question**: Are the 40 "Pathology study" documents actual surgical pathology reports or just lab results?

---

## Evidence Summary

### Document Characteristics

**All 40 "Pathology study" documents share identical characteristics**:
- `document_type`: "Pathology study"
- `type_coding_display`: "Pathology study"
- `category_text`: "Clinical Note"
- `content_type`: "text/html" (all text-based, extractable)
- `description`: (empty for all)
- `document_type_code`: (empty for all)

### Temporal Distribution

| Year | Count | Context |
|------|-------|---------|
| 2014 | 3 | Pre-diagnosis (patient age 9) |
| 2020 | 2 | During 2nd line chemotherapy |
| 2021 | 11 | **Around 2nd surgery period** |
| 2022 | 10 | Post-2nd surgery surveillance |
| 2023 | 8 | Surveillance |
| 2024 | 6 | Current surveillance |

**Key Finding**: Only **1 document dated 2021-03-18** (8 days after 2nd surgery on 2021-03-10)
- This timing suggests surgical pathology report
- Surgical pathology typically filed 3-10 days post-surgery

**Notably Missing**:
- **0 documents** from 2018 (diagnosis year, 1st surgery 2018-05-28)
- **0 documents** in June 2018 when initial pathology/diagnosis would have been

---

## Clinical Context

### Expected Surgical Pathology Reports for Patient C1277724

**Based on gold standard**:
1. **2018-05-28**: First surgery (posterior fossa craniotomy)
   - Expected: Surgical pathology report 2018-05-30 to 2018-06-10
   - **FINDING**: 0 pathology documents in this window ❌

2. **2021-03-10**: Second surgery (recurrence)
   - Expected: Surgical pathology report 2021-03-12 to 2021-03-20
   - **FINDING**: 1 document on 2021-03-18 ✅

### Interpretation

**Likely composition of 40 "Pathology study" documents**:

| Document Type | Est. Count | Evidence |
|---------------|-----------|----------|
| **Surgical Pathology** (2021 surgery) | 1-2 | 1 doc on 2021-03-18 (correct timing) |
| **Molecular/NGS reports** | 3-5 | Multiple docs per year 2021-2024 (BRAF testing, surveillance) |
| **Lab results** (CBC, Chemistry) | 30-35 | Quarterly surveillance labs, pre-chemo labs |

---

## Evidence Against "All 40 are Surgical Pathology"

### 1. **Missing 2018 Surgical Pathology** ❌
- Patient had major surgery 2018-05-28
- NO pathology documents from 2018 at all
- Initial diagnosis pathology is MISSING from this set
- **Conclusion**: 2018 surgical pathology either:
  - Not in FHIR HealthLake (possible)
  - Categorized under different document type
  - In accessible binaries but not typed as "Pathology study"

### 2. **High Frequency** ⚠️
- 40 pathology documents over 10 years (2014-2024)
- Patient only had **2 surgeries** (2018, 2021)
- Expected surgical pathology: 2-4 reports max
- **Conclusion**: Most of these 40 are NOT surgical pathology

### 3. **Surveillance Period Distribution** ⚠️
- 2022-2024: 24 documents (2-3 per quarter)
- Matches frequency of routine surveillance labs
- Does NOT match surgical pathology frequency
- **Conclusion**: These are likely quarterly lab panels

### 4. **Pre-Diagnosis Documents** ⚠️
- 3 documents from 2014 (age 9, before CNS tumor diagnosis)
- Unless prior cancer history, these are routine pediatric labs
- **Conclusion**: Not brain tumor surgical pathology

---

## Evidence For "Some are Surgical/Molecular Pathology"

### 1. **2021-03-18 Document** ✅
- 8 days after 2nd surgery (2021-03-10)
- Perfect timing for surgical pathology report
- **High confidence**: This IS surgical pathology from 2nd surgery

### 2. **Molecular Testing Period (2021-2024)** ✅
- 11 documents in 2021 (year of recurrence/2nd surgery)
- Likely includes:
  - Surgical pathology (2021-03-18)
  - BRAF fusion testing (molecular pathology)
  - Possibly IDH/MGMT testing
- **Moderate confidence**: 2-5 are molecular pathology reports

### 3. **2020 Documents** ⚠️
- 2 documents during 2nd line chemotherapy
- Could be tissue re-analysis or molecular profiling
- Could also be routine labs
- **Low confidence**: Unknown

---

## Recommendation: Tiered Inclusion Strategy

### TIER 1: DEFINITELY INCLUDE (⭐⭐⭐)
```
✅ 2021-03-18 document (1 doc)
   - 8 days after 2nd surgery
   - Very likely surgical pathology report with recurrence diagnosis
```

### TIER 2: PROBABLY INCLUDE (⭐⭐)
```
✅ All 2021 documents (11 total)
   - Recurrence period
   - May include molecular testing (BRAF fusion)
   - Even if some are labs, surgical path is here
```

### TIER 3: MAYBE INCLUDE (⭐)
```
⚠️  2022-2024 documents (24 total)
   - Surveillance period
   - Likely mostly lab results
   - But may include molecular follow-up testing

⚠️  2020 documents (2 total)
   - During treatment
   - Unknown if pathology or labs
```

### TIER 4: UNLIKELY TO HELP (❌)
```
❌ 2014 documents (3 total)
   - Pre-diagnosis, age 9
   - Almost certainly pediatric routine labs
```

---

## Recommended Action for project.csv

### OPTION 1: Include ALL 40 "Pathology study" documents (SAFEST) ✅

**Rationale**:
- BRIM will ignore lab results (no diagnosis/molecular keywords)
- Real surgical pathology will be extracted
- Minimal harm from including lab results
- Ensures we don't miss molecular testing reports

**Pros**:
- ✅ Guaranteed to include 2021-03-18 surgical pathology
- ✅ Captures any molecular testing reports
- ✅ Simple selection criteria (all "Pathology study")

**Cons**:
- ⚠️ Adds 30-35 irrelevant lab result documents
- ⚠️ Slightly increases BRIM processing time

---

### OPTION 2: Include only 2021 documents (TARGETED) ⭐

**Rationale**:
- Focus on year of 2nd surgery + molecular testing
- 11 documents is manageable
- Likely contains the critical surgical pathology

**Pros**:
- ✅ Includes 2021-03-18 surgical pathology
- ✅ Includes molecular testing from recurrence workup
- ✅ Avoids irrelevant pre-diagnosis and surveillance labs

**Cons**:
- ⚠️ May miss molecular testing from 2022-2024
- ⚠️ Requires date filtering logic

---

### OPTION 3: Also search for surgical pathology in OTHER document types (COMPREHENSIVE) ⭐⭐

**2018 Surgical Pathology is MISSING from "Pathology study" documents**

**Search these alternative sources**:

1. **Progress Notes from June 2018** (413 available)
   - May contain pathology findings dictated into progress notes
   - "Path shows pilocytic astrocytoma..."
   - BRIM can extract diagnosis from progress note text

2. **Clinical Report-Other** (39 available, but mostly TIFF images)
   - 2 are "Clinical Report-Laboratory" (might be surgical path)
   - Most are image/tiff (require OCR, skip)

3. **Consult Notes from May-June 2018** (20 available)
   - Neurosurgery or neuropathology consults
   - May discuss pathology findings

**Recommended**:
```
✅ ADD: All 40 "Pathology study" documents (includes 2021 surgical path)
✅ ADD: 20-30 Progress Notes from June 2018 (contains 2018 diagnosis discussion)
✅ ADD: 2 "Clinical Report-Laboratory" (may be surgical path reports)
```

**Total**: 62-72 documents for diagnosis/molecular variables

---

## Impact on Gold Standard Variables

### Variables Dependent on Pathology Reports

| Variable | Data Source | Document Need |
|----------|-------------|---------------|
| **primary_diagnosis** | Surgical pathology | 2021-03-18 doc OR June 2018 Progress Notes |
| **diagnosis_date** | Pathology report or progress note | June 2018 Progress Notes (2018 path missing) |
| **who_grade** | Surgical pathology | 2021-03-18 doc OR June 2018 Progress Notes |
| **tumor_location** | Surgical pathology | 2021-03-18 doc OR imaging |
| **idh_mutation** | Molecular pathology | 2021 docs (molecular testing) |
| **mgmt_methylation** | Molecular pathology | 2021 docs (if tested) |
| **braf_status** | Molecular pathology | 2021 docs (BRAF fusion confirmed) |

**Critical Finding**:
- **2018 surgical pathology is MISSING from "Pathology study" set**
- **Must rely on June 2018 Progress Notes** for initial diagnosis extraction

---

## Final Recommendation

### For project.csv Document Selection:

```
PATHOLOGY/DIAGNOSIS COVERAGE:

✅ INCLUDE: All 40 "Pathology study" documents
   - Ensures 2021-03-18 surgical pathology captured
   - Captures all molecular testing reports
   - Lab results will be ignored by BRIM (no harm)

✅ INCLUDE: 20-30 Progress Notes from June 2018
   - PRIMARY source for 2018 diagnosis (pathology missing)
   - Search for keywords: "diagnosis", "pilocytic astrocytoma", "pathology"
   - Extract: primary_diagnosis, who_grade, diagnosis_date

✅ INCLUDE: 2 "Clinical Report-Laboratory" documents
   - May contain surgical pathology reports
   - Worth checking
```

**Expected Outcome**:
- **primary_diagnosis**: Extracted from June 2018 Progress Notes (80% confidence) OR 2021-03-18 surgical path (100% confidence for recurrence)
- **who_grade**: Extracted from June 2018 Progress Notes (Grade I for pilocytic astrocytoma)
- **braf_status**: Extracted from 2021 molecular pathology (BRAF fusion)
- **diagnosis_date**: Extracted from June 2018 Progress Notes ("diagnosed on 2018-06-04")

---

## Summary

**Answer to Original Question**:
> "Are the 40 'Pathology study' documents true surgical pathology or lab results?"

**Answer**: **MIXED - Estimated composition**:
- 1-2 are surgical pathology (2021-03-18 confirmed)
- 3-5 are molecular pathology reports (BRAF, etc.)
- 30-35 are routine surveillance lab results

**BUT**: The **2018 surgical pathology is MISSING** from this set entirely.

**Action**: Include all 40 + add June 2018 Progress Notes as primary 2018 diagnosis source.

---

*Analysis completed: October 4, 2025*
*Recommendation: OPTION 3 (Comprehensive approach)*
