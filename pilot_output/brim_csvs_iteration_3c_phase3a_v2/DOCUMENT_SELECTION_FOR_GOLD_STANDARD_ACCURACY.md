# Document Selection Strategy for Gold Standard Accuracy
**Date**: October 4, 2025
**Goal**: Optimize project.csv to improve extraction accuracy from 81.2% → 90%+
**Current Status**: Phase 3a had 3 failures out of 16 tested variables

---

## Executive Summary

**Phase 3a Results**: 81.2% accuracy (13/16 variables correct)
- ✅ **Perfect** (100%): Molecular (3/3), Surgery (4/4)
- ⚠️ **Good** (75%): Diagnosis (3/4)
- ⚠️ **Needs Work** (60%): Demographics (3/5)

**Root Cause**: Wrong document selection led to:
1. **diagnosis_date** failure - Pathology reports from 2018 missing (0 found)
2. **date_of_birth** failure - No documents with DOB in structured headers
3. **age_at_diagnosis** failure - Wrong narrative text ("15-year-old" at surgery, not diagnosis)

**Solution**: Add targeted documents from 3,865 available binaries to fix failures + cover untested variables

---

## Phase 3a Failure Analysis → Document Needs

### FAILURE 1: diagnosis_date
**Phase 3a Result**: ❌ Expected 2018-06-04, Got 2018-05-28 (surgery date instead)

**Root Cause**: No pathology reports from June 2018 in project.csv

**Document Gap**:
- Pathology documents from 2018: **0 found** ❌
- Documents in June 2018: 559 available (413 Progress Notes, 70 Assessment & Plan)

**Fix Strategy**:
```
ADD to project.csv:
✅ 5-10 Progress Notes from June 2018 (diagnosis month)
   - Search for: "diagnosis date", "pathology date", "diagnosed on"
   - Dates: 2018-06-01 to 2018-06-30

✅ 20-30 Assessment & Plan Notes from June 2018
   - Likely contain diagnosis discussion

⚠️  Note: Pathology reports from 2021 available (11 docs) but not 2018
   - This is expected - 2018 pathology may not be in accessible binaries
   - Diagnosis information likely in Progress Notes instead
```

**Expected Improvement**: diagnosis_date accuracy → 100%

---

### FAILURE 2: date_of_birth
**Phase 3a Result**: ❌ Expected 2005-05-13, Got "Unavailable"

**Root Cause**: FHIR Patient.birthDate not extracted from FHIR Bundle

**Document Gap**:
- FHIR Bundle in project.csv: Present (row 1)
- BUT: BRIM may not have parsed birthDate from nested JSON structure

**Fix Strategy**:
```
SOLUTION 1 (Athena CSV): ✅ ALREADY IMPLEMENTED
   - patient_demographics.csv has birth_date = 2005-05-13
   - Phase 3a_v2 instructions: "PRIORITY 1: Check patient_demographics.csv"
   - Expected to fix this issue

SOLUTION 2 (Fallback - if CSV doesn't work):
   ✅ ADD 5-10 Encounter Summaries (XML with demographics)
      - 761 available
      - Content type: application/xml
      - May have structured <birthDate> fields

   ✅ ADD 3-5 oldest Progress Notes (2005-2006)
      - May have "DOB: MM/DD/YYYY" in header
      - Dates: 2005-05-19, 2005-06-03, etc.
```

**Expected Improvement**: date_of_birth accuracy → 100% (via CSV) or 80% (via fallback)

---

### FAILURE 3: age_at_diagnosis
**Phase 3a Result**: ❌ Expected 13, Got "15 years" (wrong text extraction)

**Root Cause**: BRIM extracted age from narrative text instead of calculating from dates
- Text likely: "The patient is a 15-year-old girl who underwent craniotomy..."
- Age 15 was at **surgery** (2018-05-28), not **diagnosis** (2018-06-04)

**Document Gap**: INSTRUCTION PROBLEM, not document gap
- 382 documents around first surgery contain "15-year-old" text
- These documents should NOT be used for age extraction

**Fix Strategy**:
```
INSTRUCTION FIX (already implemented in Phase 3a_v2):
   ✅ "CRITICAL: DO NOT extract age from clinical notes text."
   ✅ "BLOCK all text extraction attempts."
   ✅ "MUST calculate from dates only."
   ✅ "PRIORITY 1: Check patient_demographics.csv for date_of_birth"

DOCUMENT STRATEGY:
   ❌ DO NOT add more Progress Notes from May-June 2018 for age extraction
      (they contain misleading "15-year-old" text)

   ✅ Rely on patient_demographics.csv for birth_date
   ✅ Rely on June 2018 Progress Notes for diagnosis_date
   ✅ Let BRIM calculate age from dates (not text)
```

**Expected Improvement**: age_at_diagnosis accuracy → 100% (via calculation, not text)

---

## Untested Variables → Document Needs

### 1. CLINICAL STATUS VARIABLES (3 variables - HIGH PRIORITY)

**Variables**: clinical_status, progression_date, recurrence_date

**Document Coverage Analysis**:

| Period | Event | Documents Available | Priority |
|--------|-------|---------------------|----------|
| **Apr-Jun 2019** | Progression (2nd line start) | 73 docs (26 Progress, 15 Telephone, 5 Imaging) | ⭐⭐⭐ CRITICAL |
| **Feb-Apr 2021** | Recurrence (2nd surgery) | 327 docs (161 Progress, 24 Imaging, 12 Consult) | ⭐⭐⭐ CRITICAL |

**Document Selection**:
```
PROGRESSION PERIOD (Apr-Jun 2019):
✅ ADD 15-20 Progress Notes (oncology notes discussing disease progression)
   - Search for: "progression", "progressive disease", "tumor growth"
   - Extract progression_date and clinical_status

✅ ADD 5 Imaging reports (May 2019)
   - Radiology impressions showing interval growth

RECURRENCE PERIOD (Feb-Apr 2021):
✅ ADD 30-40 Progress Notes (pre-surgical workup, recurrence discussion)
   - Search for: "recurrence", "recurrent tumor", "new lesion"
   - Extract recurrence_date and clinical_status

✅ ADD 10-15 Imaging reports (Feb-Mar 2021)
   - Radiology showing recurrent disease

✅ ADD 5-10 Consult Notes (neurosurgery planning 2nd surgery)
   - May discuss recurrence timeline
```

**Expected Coverage**: clinical_status (many_per_note), progression_date, recurrence_date → 80-90% accuracy

---

### 2. IMAGING FREE-TEXT VARIABLES (3 variables - MEDIUM PRIORITY)

**Variables**: tumor_size, contrast_enhancement, imaging_findings

**Document Coverage Analysis**:
- Total text-based imaging reports: 162 (HTML/RTF)
- 2018 (diagnosis): 43 reports
- 2021 (recurrence): 36 reports
- 2024 (current): 21 reports

**Document Selection**:
```
BASELINE (2018):
✅ ADD 10-15 imaging reports from May-June 2018 (initial diagnosis)
   - Establish baseline tumor size
   - Document initial imaging findings

PROGRESSION TRACKING (2019):
✅ ADD 5-10 imaging reports from 2019
   - Track tumor changes leading to 2nd line therapy

RECURRENCE (2021):
✅ ADD 15-20 imaging reports from Feb-Mar 2021
   - Document recurrent tumor characteristics
   - Compare to baseline

CURRENT STATUS (2024-2025):
✅ ADD 10 imaging reports from 2024-2025
   - Current disease status on selumetinib
```

**Total Imaging**: 40-55 reports (strategic temporal selection)

**Expected Coverage**: tumor_size, contrast_enhancement, imaging_findings → 70-85% accuracy

**Note**: patient_imaging.csv already provides imaging_type and imaging_date for 51 MRI studies

---

### 3. CHEMOTHERAPY FREE-TEXT VARIABLES (3 variables - MEDIUM PRIORITY)

**Variables**: chemotherapy_line, chemotherapy_route, chemotherapy_dose

**Document Coverage Analysis**:
- Progress notes around vinblastine start (Oct 2018): 12 docs
- Progress notes around bevacizumab start (May 2019): 8 docs
- Progress notes around selumetinib start (May 2021): 2 docs

**Document Selection**:
```
1ST LINE (Vinblastine - Oct 2018):
✅ ADD 8-10 Progress Notes from Sept-Oct 2018
   - Search for: "vinblastine", "1st line", "initial chemotherapy"
   - Extract chemotherapy_line="1st line", route="Intravenous", dose

2ND LINE (Bevacizumab - May 2019):
✅ ADD 6-8 Progress Notes from May-June 2019
   - Search for: "bevacizumab", "2nd line", "after progression"
   - Extract chemotherapy_line="2nd line", route="Intravenous", dose

3RD LINE (Selumetinib - May 2021):
✅ ADD 2-5 Progress Notes from May-June 2021
   - Search for: "selumetinib", "3rd line", "MEK inhibitor"
   - Extract chemotherapy_line="3rd line", route="Oral", dose
```

**Total Chemo Progress Notes**: 16-23 notes

**Expected Coverage**: chemotherapy_line, chemotherapy_route, chemotherapy_dose → 75-90% accuracy

**Note**: patient_medications.csv already provides:
- chemotherapy_agent (3 agents)
- chemotherapy_start_date (3 dates)
- chemotherapy_end_date (2 dates + 1 ongoing)
- chemotherapy_status (3 statuses)

---

### 4. RADIATION VARIABLES (4 variables - LOW PRIORITY)

**Variables**: radiation_therapy_yn, radiation_start_date, radiation_dose, radiation_fractions

**Patient-Specific Note**: C1277724 did NOT receive radiation therapy

**Document Selection**:
```
✅ Current strategy: Search all Progress Notes for "radiation" mentions
   - If no mentions found → return "No" for radiation_therapy_yn
   - Other 3 variables return "N/A"

❌ DO NOT add specific radiation oncology notes (patient didn't receive radiation)
```

**Expected Coverage**: radiation_therapy_yn="No" → 100% accuracy (once negative finding confirmed)

---

## Optimized Document Selection Plan

### Target: 450-550 Documents for project.csv

| Document Type | Period | Count | Purpose | Priority |
|---------------|--------|-------|---------|----------|
| **Pathology** | 2021-2024 | 30-40 | Diagnosis confirmation, molecular | ⭐⭐⭐ |
| **Progress Notes (Diagnosis)** | June 2018 | 20-30 | diagnosis_date extraction | ⭐⭐⭐ |
| **Progress Notes (Progression)** | Apr-Jun 2019 | 15-20 | progression_date, clinical_status | ⭐⭐⭐ |
| **Progress Notes (Recurrence)** | Feb-Apr 2021 | 30-40 | recurrence_date, clinical_status | ⭐⭐⭐ |
| **Progress Notes (Chemo)** | Oct 2018, May 2019, May 2021 | 16-23 | chemo line/route/dose | ⭐⭐ |
| **Imaging Reports** | 2018, 2019, 2021, 2024 | 40-55 | tumor_size, enhancement, findings | ⭐⭐⭐ |
| **Procedure/Operative** | May 2018, Mar 2021 | 50-70 | Surgery variables (already 100%) | ⭐⭐ |
| **Consult Notes** | 2018, 2021 | 10-15 | Context, recurrence confirmation | ⭐ |
| **Assessment & Plan** | June 2018, 2019, 2021 | 20-30 | Diagnosis, treatment decisions | ⭐⭐ |
| **Encounter Summaries (XML)** | Any (if needed for DOB) | 5-10 | Fallback for date_of_birth | ⚠️ |

**Total**: 236-353 core documents + existing documents = **450-550 total**

---

## Content Type Filter

**Include** (text-based only):
- ✅ text/html
- ✅ text/rtf
- ⚠️ application/xml (only if needed for DOB fallback)

**Exclude**:
- ❌ application/pdf (unless critical pathology/imaging)
- ❌ image/tiff, image/jpeg, image/png (require OCR)
- ❌ video/quicktime (not extractable)

---

## Expected Accuracy Improvements

### Phase 3a Results → Phase 3a_v2 Targets

| Category | Phase 3a | Phase 3a_v2 Target | Improvement Strategy |
|----------|----------|-------------------|----------------------|
| **Demographics** | 60% (3/5) | **100% (5/5)** | Athena CSV + fallback docs |
| **Diagnosis** | 75% (3/4) | **100% (4/4)** | Add June 2018 Progress Notes |
| **Molecular** | 100% (3/3) | **100% (3/3)** | Maintain (already perfect) |
| **Surgery** | 100% (4/4) | **100% (4/4)** | Maintain (already perfect) |
| **Chemotherapy** | Untested | **85% (6/7)** | Add chemo start Progress Notes |
| **Radiation** | Untested | **100% (4/4)** | Confirm "No" across all notes |
| **Clinical Status** | Untested | **80% (2.5/3)** | Add progression/recurrence docs |
| **Imaging** | Untested | **75% (3.75/5)** | Add 40-55 imaging reports |

**Overall Target**: **90.5% accuracy (31.75/35 variables)**

Up from Phase 3a: **81.2% (13/16)** → **90.5% (31.75/35)**

---

## Implementation Steps

### Step 1: Create Document Selection Script
```python
# Filter accessible_binary_files_annotated.csv by:
# 1. Content type (text/html, text/rtf)
# 2. Document type (as specified in table above)
# 3. Date ranges (treatment milestones)
# 4. Priority tiers (⭐⭐⭐ first, then ⭐⭐, then ⭐)
```

### Step 2: Generate Optimized project.csv
```python
# Extract selected documents from S3
# Create project.csv with:
# - 1 FHIR Bundle (patient demographics)
# - 450-550 selected clinical documents
# - Organized by document type and date
```

### Step 3: Validate Coverage
```python
# Verify each variable category has sufficient documents:
# - diagnosis_date: ≥20 June 2018 Progress Notes
# - progression_date: ≥15 Apr-Jun 2019 Progress Notes
# - recurrence_date: ≥30 Feb-Apr 2021 Progress Notes
# - tumor_size: ≥40 Imaging reports
# - chemotherapy_line: ≥16 chemo start Progress Notes
```

### Step 4: Upload to BRIM
```
Upload package:
1. variables.csv (35 variables - no changes)
2. project.csv (450-550 optimized documents)
3. decisions.csv (aggregation rules)
4. patient_demographics.csv (Athena structured data)
5. patient_medications.csv (Athena structured data)
6. patient_imaging.csv (Athena structured data)
```

---

## Key Recommendations

### 1. **Fix Phase 3a Failures First** (Priority ⭐⭐⭐)
- ✅ Add 20-30 June 2018 Progress Notes (diagnosis_date)
- ✅ Rely on patient_demographics.csv (date_of_birth, age_at_diagnosis)
- ✅ Block text extraction for age (calculation only)

### 2. **Add Untested Variable Coverage** (Priority ⭐⭐)
- ✅ Add 45-60 Progress Notes around treatment changes (clinical_status, chemo variables)
- ✅ Add 40-55 Imaging reports across timeline (imaging free-text variables)

### 3. **Maintain Phase 3a Successes** (Priority ⭐)
- ✅ Keep pathology documents for molecular variables (100% accurate)
- ✅ Keep procedure documents for surgery variables (100% accurate)

### 4. **Quality Control**
- ✅ Filter to text-based content types only (HTML/RTF)
- ✅ Focus on treatment milestone periods (2018, 2019, 2021)
- ✅ Avoid over-inclusion (450-550 target, not 2,000+)

---

## Summary

**The 3,865 accessible documents provide MORE than adequate coverage to fix all Phase 3a failures and test all untested variables.**

**Critical Finding**: Phase 3a failures were due to:
1. Missing June 2018 Progress Notes (diagnosis_date)
2. FHIR birthDate not extracted (fixed in Phase 3a_v2 via CSV)
3. Wrong instruction allowing text extraction (fixed in Phase 3a_v2)

**Next Action**: Create document selection script to generate optimized 450-550 document project.csv targeting 90%+ accuracy.

**No variables.csv changes needed** - all 35 variables have adequate document support. Focus is on strategic document selection + Athena CSV integration.

---

*Analysis completed: October 4, 2025*
*Ready for: Document selection script implementation*
