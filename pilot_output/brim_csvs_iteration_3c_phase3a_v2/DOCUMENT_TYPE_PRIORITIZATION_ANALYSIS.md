# Document Type Prioritization Analysis
**Date**: October 4, 2025
**Patient**: C1277724 (e4BwD8ZYDBccepXcJ.Ilo3w3)
**Analysis Source**: accessible_binary_files_annotated.csv (3,865 documents)

---

## Executive Summary

**Discovery**: 3,865 accessible binary documents available for patient C1277724
- ✅ **2,480 text-based documents** (HTML/RTF) - ready for BRIM extraction
- ⚠️ **229 PDF documents** - may require OCR
- ❌ **223 image files** (TIFF/JPEG/PNG) - require OCR, not recommended
- ❌ **762 XML files** - mostly C-CDA summaries (structured duplicates)

**Current State**: project.csv has 891 documents
**Recommendation**: Expand to ~400-550 high-value documents strategically selected

---

## Document Type Distribution

### Top 10 Document Types by Volume

| Count | Document Type | Clinical Value |
|-------|---------------|----------------|
| 1,277 | Progress Notes | ⭐⭐⭐ HIGH - Treatment timeline, chemotherapy, status |
| 761 | Encounter Summary | ❌ LOW - XML structured data (duplicates) |
| 397 | Telephone Encounter | ⚠️ MEDIUM - May contain medication changes |
| 163 | Diagnostic imaging study | ⭐⭐⭐ HIGH - Tumor size, imaging findings |
| 148 | Assessment & Plan Note | ⭐⭐ MEDIUM-HIGH - Treatment decisions |
| 107 | Patient Instructions | ❌ LOW - Administrative |
| 97 | After Visit Summary | ⚠️ MEDIUM - May contain treatment plans |
| 64 | Nursing Note | ⚠️ MEDIUM - May contain symptoms |
| 47 | Consult Note | ⭐⭐ MEDIUM-HIGH - Specialist assessments |
| 40 | Pathology study | ⭐⭐⭐ CRITICAL - Diagnosis, grade, molecular |

---

## High-Value Clinical Document Analysis

### 1. Pathology Documents (CRITICAL)
**Count**: 40 documents
**Content Type**: text/html, text/rtf (all extractable)
**Temporal Distribution**:
- 2021: 11 documents (second surgery period)
- 2022: 10 documents
- 2023: 8 documents
- 2024: 6 documents

**Variables Supported** (7):
- primary_diagnosis
- diagnosis_date
- who_grade
- tumor_location
- idh_mutation
- mgmt_methylation
- braf_status

**Priority**: ✅ **USE ALL 40** in project.csv

---

### 2. Imaging/Radiology Documents (HIGH)
**Count**: 245 documents total
- 162 text-based (HTML/RTF) ✅
- 83 PDF/other formats ⚠️

**Temporal Distribution**:
- 2018: 56 documents (diagnosis year)
- 2019: 27 documents
- 2020: 22 documents
- 2021: 46 documents (second surgery)
- 2022: 26 documents
- 2023: 19 documents
- 2024: 30 documents (increased surveillance)
- 2025: 9 documents (ongoing)

**Variables Supported** (3 free-text from narratives):
- tumor_size (many_per_note)
- contrast_enhancement (many_per_note)
- imaging_findings (many_per_note)

**Note**: patient_imaging.csv already provides:
- imaging_type (51 MRI studies)
- imaging_date (51 dates)

**Priority**: ✅ **USE 100-150** text-based imaging reports
- Focus on: 2018 (diagnosis), 2021 (recurrence), 2024-2025 (current status)
- Prioritize: "MR Brain W & W/O IV Contrast" and "Diagnostic imaging study"

---

### 3. Procedure/Operative Notes (HIGH)
**Count**: 82 documents
- 71 text-based (HTML/RTF) ✅
- 11 other formats

**Key Dates**:
- 2018-05-28 area: First surgery documents
- 2021-03-10 area: Second surgery documents

**Variables Supported** (4):
- surgery_date (many_per_note)
- surgery_type (many_per_note)
- surgery_extent (many_per_note)
- surgery_location (many_per_note)

**Current Status**: Phase 2 achieved 100% accuracy with STRUCTURED_surgeries

**Priority**: ✅ **USE 50-70** procedure notes
- Include: Complete operative notes, procedure notes, anesthesia evaluations
- Link to known surgery dates for validation

---

### 4. Progress Notes (HIGH for Treatment Timeline)
**Count**: 1,277 documents (ALL text-based HTML/RTF) ✅

**Temporal Distribution**:
- 2018: 760 documents (diagnosis & initial treatment)
- 2019: 121 documents (1st line chemo)
- 2020: 49 documents
- 2021: 201 documents (recurrence & 3rd line start)
- 2022-2025: 81 documents (ongoing surveillance)

**Variables Supported** (10+):
- chemotherapy_line (many_per_note)
- chemotherapy_route (many_per_note)
- chemotherapy_dose (many_per_note)
- clinical_status (many_per_note)
- progression_date (aggregated)
- recurrence_date (aggregated)
- radiation_therapy_yn (one_per_patient)
- radiation_start_date (one_per_patient)
- radiation_dose (one_per_patient)
- radiation_fractions (one_per_patient)

**Priority**: ✅ **USE 200-300** strategically selected progress notes
- Focus years: 2018, 2019, 2021 (treatment changes)
- Include: Oncology visits, treatment planning, response assessments

---

### 5. Consult Notes (MEDIUM-HIGH)
**Count**: 47 documents (46 text-based) ✅

**Sample Dates**:
- 2021-11-05, 2021-03-19, 2021-03-12 (around second surgery)

**Variables Supported**:
- Specialist assessments (neurosurgery, oncology)
- Treatment recommendations
- Second opinions

**Priority**: ⏭️ **Consider 20-30** consult notes for future iterations
- Valuable for context but lower priority than direct treatment notes

---

### 6. Assessment & Plan Notes (MEDIUM-HIGH)
**Count**: 148 documents (ALL text-based) ✅

**Variables Supported**:
- clinical_status
- Treatment plans
- Disease progression assessments

**Priority**: ⏭️ **Consider 50-100** for future iterations
- Useful for clinical_status and treatment decision tracking

---

## Content Type Analysis

### Extraction Feasibility

| Content Type | Count | BRIM Compatible | Recommendation |
|--------------|-------|-----------------|----------------|
| text/html | 2,480 | ✅ YES | Primary extraction source |
| text/rtf | 2,248 | ✅ YES | Primary extraction source |
| application/xml | 762 | ⚠️ Structured | C-CDA summaries - skip |
| text/xml | 169 | ⚠️ Structured | C-CDA summaries - skip |
| application/pdf | 229 | ⚠️ Maybe OCR | Use if critical documents |
| image/tiff | 191 | ❌ Requires OCR | Skip |
| image/jpeg | 31 | ❌ Requires OCR | Skip |
| image/png | 1 | ❌ Requires OCR | Skip |
| video/quicktime | 2 | ❌ Not extractable | Skip |

**Key Finding**: 2,480 text-based documents available (64% of total) - all directly extractable

---

## Variable Coverage Analysis

### Current Variables (35) - Coverage Assessment

| Variable Category | Variables | Document Sources Available | Status |
|-------------------|-----------|---------------------------|--------|
| **Demographics** (5) | patient_gender, date_of_birth, age_at_diagnosis, race, ethnicity | ✅ CSV | Complete |
| **Diagnosis** (4) | primary_diagnosis, diagnosis_date, who_grade, tumor_location | ✅ 40 Pathology | Good |
| **Molecular** (3) | idh_mutation, mgmt_methylation, braf_status | ✅ 40 Pathology | Excellent |
| **Surgery** (4) | surgery_date, surgery_type, surgery_extent, surgery_location | ✅ 82 Procedure | Excellent |
| **Chemotherapy** (7) | agent, start_date, end_date, status, line, route, dose | ✅ CSV + 1,277 Progress | Mixed |
| **Radiation** (4) | therapy_yn, start_date, dose, fractions | ⚠️ 1,277 Progress | Not tested |
| **Clinical Status** (3) | clinical_status, progression_date, recurrence_date | ⚠️ 1,277 Progress + 245 Imaging | Not tested |
| **Imaging** (5) | imaging_type, imaging_date, tumor_size, contrast_enhancement, findings | ✅ CSV + 245 Imaging | Partial |

---

## Recommended Variables to Add (NONE - Current 35 is comprehensive)

After deep analysis, **NO new variables are recommended at this time**. The current 35 variables comprehensively cover:
- ✅ Core demographics (5 variables)
- ✅ Diagnosis & molecular (7 variables)
- ✅ Treatment modalities: surgery (4), chemotherapy (7), radiation (4)
- ✅ Disease monitoring: imaging (5), clinical status (3)

**Why not add more variables?**
1. **Current bottleneck is extraction accuracy, not variable coverage**
   - Phase 3a: 81.2% accuracy (13/16 variables correct)
   - Focus should be on improving extraction instructions, not adding variables

2. **Document availability supports current variables well**
   - All 35 variables have adequate document sources (40-1,277 documents each)
   - Adding more variables would dilute focus without improving outcomes

3. **BRIM platform limitations**
   - Each variable requires careful instruction crafting
   - More variables = more potential failure points
   - Better to achieve 90%+ accuracy on 35 variables than 70% on 50 variables

---

## Recommended Document Selection Strategy

### Phase 3a_v2 (IMMEDIATE - Target: ~400-550 documents)

**Tier 1 - CRITICAL (Include ALL)**:
```
40  Pathology documents (diagnosis, molecular)
```

**Tier 2 - HIGH VALUE (Strategic Selection)**:
```
100-150  Imaging reports (tumor tracking over time)
         → Focus: 2018 (diagnosis), 2021 (recurrence), 2024-2025 (current)

50-70    Procedure/Operative notes (surgery details)
         → Focus: 2018-05-28 area, 2021-03-10 area

200-300  Progress Notes (treatment timeline, status)
         → Focus: 2018 (initial treatment), 2019 (progression), 2021 (recurrence)
```

**Total Phase 3a_v2**: 390-560 high-value documents

### Phase 3b (FUTURE - Target: ~1,000-1,500 documents)

**Tier 3 - COMPREHENSIVE (Add Remaining)**:
```
50-100   Assessment & Plan Notes (treatment decisions)
20-30    Consult Notes (specialist insights)
400-800  Additional Progress Notes (complete treatment timeline)
```

**Total Phase 3b**: ~1,000-1,500 comprehensive clinical narrative

### NOT Recommended:
```
❌ 762 XML Encounter Summaries (C-CDA duplicates)
❌ 223 Image files (TIFF/JPEG/PNG - require OCR)
❌ 2 Video files (not extractable)
❌ Low-value administrative documents (patient instructions, after-visit summaries)
```

---

## Implementation Steps for variables.csv Enhancement

### Option 1: Keep Current 35 Variables (RECOMMENDED) ✅

**Why**: Document analysis shows excellent coverage for all 35 variables
- Pathology: 40 docs support 7 variables
- Imaging: 245 docs support 5 variables
- Procedure: 82 docs support 4 variables
- Progress Notes: 1,277 docs support 10+ variables

**Action**: Focus on improving extraction instructions, not adding variables

### Option 2: Add Symptom/Toxicity Variables (NOT RECOMMENDED) ❌

**Potential new variables**:
- treatment_toxicity (grade, type)
- adverse_events
- performance_status
- symptom_severity

**Why NOT recommended**:
1. Not in original BRIM data dictionary requirements
2. Difficult to extract consistently from narrative text
3. Would require 200+ additional progress note reviews
4. Current priority is accuracy on core variables, not expansion

### Option 3: Add Genomic Panel Variables (CONSIDER FOR FUTURE) ⏭️

**Potential new variables**:
- tumor_mutational_burden
- microsatellite_instability
- additional_alterations (TP53, CDKN2A, etc.)

**Why MAYBE later**:
1. Pathology documents (40) may contain NGS panel results
2. Relevant for precision oncology treatment decisions
3. BUT: Current molecular variables (IDH, MGMT, BRAF) are already 100% accurate
4. Expansion should wait until Phase 3a_v2 results validate current approach

---

## Key Recommendations

### 1. Document Selection for project.csv
✅ **Expand from 891 to ~400-550 strategically selected documents**
- Use document type + date filtering based on this analysis
- Prioritize text-based (HTML/RTF) over PDF/images
- Focus on treatment milestone periods (2018, 2019, 2021)

### 2. Variables.csv
✅ **Keep current 35 variables - DO NOT add new variables yet**
- Current variables have excellent document support (40-1,277 docs each)
- Focus on instruction refinement, not expansion
- Wait for Phase 3a_v2 results before considering additions

### 3. Extraction Strategy
✅ **Implement tiered approach**
- Phase 3a_v2: 400-550 high-value documents → target 85%+ accuracy
- Phase 3b: 1,000-1,500 comprehensive documents → target 90%+ accuracy
- Final: Full 2,480 text-based documents → target 95%+ accuracy

### 4. Quality over Quantity
✅ **Strategic selection beats volume**
- 400 well-selected documents > 2,000 unfocused documents
- Each document type serves specific variable extraction goals
- Temporal alignment with treatment milestones maximizes accuracy

---

## Conclusion

**The 3,865 accessible documents provide MORE than adequate coverage for all 35 current variables.**

**Next Action**: Create a document selection script that:
1. Filters accessible_binary_files_annotated.csv by:
   - Document type (pathology, imaging, procedure, progress)
   - Content type (text/html, text/rtf only)
   - Date ranges (2018, 2019, 2021 treatment milestones)
2. Selects ~400-550 highest-value documents
3. Generates updated project.csv for Phase 3a_v2 upload

**No variables.csv changes recommended** - current 35 variables are comprehensive and well-supported by available documents.

---

*Analysis completed: October 4, 2025*
