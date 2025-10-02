# BRIM Pilot Results Analysis
**Date:** October 2, 2025  
**Patient ID:** 1277724  
**Export File:** 20251002-BRIM_Pilot2-BrimDataExport.csv

## Executive Summary

The BRIM extraction completed successfully for the pilot patient. This analysis reviews the accuracy and completeness of extracted variables and decisions, identifies issues, and proposes improvements.

## Results Overview

**Total Extractions:** 41 rows (excluding header)
- **Variables:** 13 extracted
- **Decisions:** 5 aggregated

### Extraction Quality Summary

| Category | Status | Notes |
|----------|--------|-------|
| ✅ **Strong Extractions** | 6/13 | Gender, diagnosis, grade, chemotherapy, surgery dates/types |
| ⚠️ **Partial/Inaccurate** | 3/13 | Resection extent, document type, DOB |
| ❌ **Failed/Unknown** | 4/13 | IDH mutation, MGMT, diagnosis date, radiation therapy |
| 🔧 **Decision Issues** | 2/5 | Total surgeries (returned 0, should be 2+), best resection |

---

## Detailed Variable Analysis

### ✅ STRONG PERFORMANCE

#### 1. **patient_gender** ✅
- **Extracted:** `female`
- **Raw Text:** "19 yo female referred for evaluation..."
- **Assessment:** Perfect extraction with clear reasoning
- **Action:** None needed

#### 2. **primary_diagnosis** ✅
- **Extracted:** `Pilocytic astrocytoma of cerebellum`
- **Raw Text:** "Pilocytic astrocytoma of cerebellum (disorder)"
- **Assessment:** Correct with 1.0 confidence
- **Action:** None needed

#### 3. **who_grade** ✅
- **Extracted:** `low-grade glioma`
- **Raw Text:** Multiple mentions of "low-grade glioma" across notes
- **Assessment:** Correct classification with strong reasoning
- **Action:** None needed

#### 4. **chemotherapy_agent** ✅
- **Extracted:** `Selumetinib`
- **Raw Text:** "targeted (selumetinib) therapy"
- **Assessment:** Correctly identified targeted therapy agent
- **Action:** None needed

#### 5. **surgery_date** ✅
- **Extracted:** `2021-03-10` (2 instances)
- **Raw Text:** FHIR Procedure resources with performedPeriod start dates
- **Assessment:** Accurate date extraction from structured FHIR data
- **Action:** None needed

#### 6. **surgery_type** ✅ (partial)
- **Extracted:** `DEBULKING`, `OTHER`, `OTHER`
- **Raw Text:** "CRNEC INFRATNTOR/POSTFOSSA EXC/FENESTRATION CYST"
- **Assessment:** Correctly identified debulking surgery
- **Issue:** Anesthesia procedure ("ANES PERFORM INJ...") classified as surgery type
- **Action:** Need to filter out non-surgical procedures

---

### ⚠️ PARTIAL/NEEDS IMPROVEMENT

#### 7. **extent_of_resection** ⚠️
- **Extracted:** `not specified` (2x), `gross total resection` (1x)
- **Raw Text:** Mixed - surgical changes, "gross total resection of enhancing cystic structures"
- **Assessment:** 
  - ✅ Correctly identified GTR in radiology report
  - ❌ Marked as "not specified" for descriptive surgical changes that don't explicitly state resection extent
- **Issue:** Conservative interpretation may miss implicit resection information
- **Action:** 
  - Enhance instruction to infer resection extent from surgical cavity descriptions
  - Add examples of indirect resection evidence (e.g., "surgical cavity" suggests resection occurred)

#### 8. **document_type** ⚠️
- **Extracted:** `RADIOLOGY`
- **Raw Text:** MRI reports, but also includes "text=Vital Signs", "text=Consult Note", "text=Lab"
- **Assessment:**
  - ✅ Correctly identified radiology as most frequent
  - ❌ Ignored other document types present in the FHIR Bundle
- **Issue:** The "many labels per note" scope should have extracted multiple document types
- **Action:**
  - Clarify that FHIR_BUNDLE contains multiple document types
  - Instruction should extract each document type separately
  - Consider changing scope or aggregation strategy

#### 9. **date_of_birth** ⚠️
- **Extracted:** `Not documented`
- **Raw Text:** "19 yo female" mentioned in clinical notes
- **Assessment:**
  - ❌ Failed to extract DOB despite clear age reference (19 years old)
  - ❌ Reasoning states "no Patient resource" but age is in clinical text
- **Issue:** Instruction only looks for explicit DOB/dates, not age that can be used to calculate approximate DOB
- **Action:**
  - Update instruction to extract age if DOB not available
  - Add logic to calculate approximate birth year from age and note date
  - Example: "19 yo" in 2024 → approximate DOB ~2005

---

### ❌ FAILED EXTRACTIONS (Unknown/Default Values)

#### 10. **idh_mutation** ❌
- **Extracted:** `unknown`
- **Raw Text:** None
- **Assessment:** No molecular testing data in FHIR Bundle
- **Issue:** FHIR data doesn't contain Observation resources with molecular markers
- **Root Cause:** Data source limitation - molecular results may be in:
  - Separate Observation resources not included in Bundle
  - Clinical notes as unstructured text (not parsed)
  - External pathology reports not integrated
- **Action:**
  - Add DocumentReference text extraction to search clinical notes
  - Look for patterns: "IDH wildtype", "IDH mutant", "IDH1 R132H"
  - Consider adding Observation resources to FHIR extraction

#### 11. **mgmt_methylation** ❌
- **Extracted:** `unknown`
- **Raw Text:** None
- **Assessment:** Similar to IDH - no molecular data
- **Issue:** Same data source limitation
- **Action:**
  - Search clinical notes for "MGMT methylated", "MGMT unmethylated"
  - Add pathology report text extraction

#### 12. **diagnosis_date** ❌
- **Extracted:** `unknown`
- **Raw Text:** None (but likely in Condition resources)
- **Assessment:** Failed to extract despite likely presence in FHIR Condition.onsetDateTime
- **Issue:** Instruction may not be properly querying Condition resources
- **Action:**
  - Verify FHIR Condition resources are in project.csv
  - Update instruction to explicitly look for Condition.onsetDateTime
  - Fallback to earliest surgery date or clinical note mention

#### 13. **radiation_therapy** ❌
- **Extracted:** `false`
- **Raw Text:** None
- **Assessment:** May be false negative - need to verify
- **Issue:** 
  - No radiation Procedure resources in FHIR Bundle, OR
  - Radiation mentioned in clinical notes but not extracted
- **Action:**
  - Search DocumentReference texts for radiation keywords
  - Look for: "radiation", "XRT", "IMRT", "stereotactic", "Gy"
  - Verify if patient actually received radiation (ground truth needed)

---

## Decision Variable Analysis

### ❌ CRITICAL ISSUES

#### 14. **total_surgeries** ❌ CRITICAL
- **Extracted:** `0`
- **Expected:** At least `2` (two surgery dates on 2021-03-10)
- **Raw Text:** Shows surgery_date entries with valid dates
- **Assessment:** **MAJOR BUG** - Count logic completely failed
- **Issue:** 
  - Decision instruction asks to count "unique surgical procedures"
  - LLM reasoning: "does not include any details about types or names"
  - Bug: Despite having surgery_date evidence, returned 0
- **Root Cause:**
  - Instruction unclear about what constitutes a "unique" surgery
  - May be requiring both date AND type to count
  - Aggregation logic not properly counting surgery_date entries
- **Action:** 🚨 HIGH PRIORITY
  - Simplify instruction: "Count the number of unique surgery dates"
  - Or: "Count all surgery_type entries that are not 'OTHER'"
  - Add explicit examples in instruction
  - Test with current data to verify fix

#### 15. **best_resection** ⚠️
- **Extracted:** `DEBULKING`
- **Expected:** Possibly `gross total resection` (GTR mentioned in radiology)
- **Assessment:** Reasonable but may be inaccurate
- **Issue:**
  - Chose DEBULKING from surgery_type over GTR from extent_of_resection
  - Reasoning: "DEBULKING is more extensive than OTHER"
  - But: Radiology report clearly states "gross total resection"
- **Root Cause:**
  - Decision depends on both surgery_type and extent_of_resection
  - Unclear which source to prioritize (operative note vs. radiology interpretation)
- **Action:**
  - Update instruction to prioritize extent_of_resection over surgery_type
  - Hierarchy: GTR > Near Total > Subtotal > Debulking > Biopsy
  - Add clinical context: radiology confirmation often more accurate than procedure coding

#### 16. **confirmed_diagnosis** ✅
- **Extracted:** `Pilocytic astrocytoma of cerebellum`
- **Assessment:** Correct aggregation from primary_diagnosis
- **Action:** None needed

#### 17. **molecular_profile** ⚠️
- **Extracted:** `IDH mutation status: unknown`
- **Assessment:** Correctly aggregated from idh_mutation
- **Issue:** Inherits failure from base variable
- **Action:** Fix idh_mutation extraction first

#### 18. **chemotherapy_regimen** ✅
- **Extracted:** `Selumetinib`
- **Assessment:** Correct aggregation from chemotherapy_agent
- **Action:** None needed

---

## Priority Issues Ranked

### 🚨 CRITICAL (Must Fix)
1. **total_surgeries = 0** - Completely wrong, blocks analysis
2. **date_of_birth = "Not documented"** - Age present but not extracted

### ⚠️ HIGH PRIORITY (Significant Impact)
3. **best_resection** - May be wrong (DEBULKING vs GTR)
4. **surgery_type includes anesthesia** - Noise in data
5. **extent_of_resection** - Too conservative, missing implicit evidence

### 📋 MEDIUM PRIORITY (Data Completeness)
6. **idh_mutation = unknown** - Need text extraction from clinical notes
7. **mgmt_methylation = unknown** - Need text extraction
8. **diagnosis_date = unknown** - Should be extractable from Condition resources
9. **radiation_therapy = false** - Need text extraction to verify

### 💡 LOW PRIORITY (Nice to Have)
10. **document_type** - Should extract multiple types, not just most frequent

---

## Proposed Variable Instruction Updates

### 1. Fix total_surgeries Decision
**Current Instruction:**
```
Count the total number of unique surgical procedures the patient has undergone. 
Use the surgery_type and surgery_date variables.
```

**Updated Instruction:**
```
Count the total number of unique surgical procedures by counting distinct surgery_date 
values where surgery_type is NOT 'OTHER'. If multiple surgery_type entries exist for 
the same date, count as one surgery. Return the count as a number (e.g., "1", "2", "3").

Examples:
- surgery_date: 2021-03-10, surgery_type: DEBULKING → count = 1
- surgery_date: 2021-03-10 (2x), surgery_type: DEBULKING, OTHER → count = 1 
- surgery_date: 2021-03-10, 2022-05-15, surgery_type: DEBULKING, RESECTION → count = 2
```

### 2. Fix date_of_birth Variable
**Current Instruction:**
```
Extract the patient's date of birth in YYYY-MM-DD format from the Patient resource 
in the FHIR Bundle. Look for Patient.birthDate. If not found, return "Not documented".
```

**Updated Instruction:**
```
Extract the patient's date of birth in YYYY-MM-DD format. Priority order:

1. FHIR Patient.birthDate (if available) - exact date
2. Age mentioned in clinical text (e.g., "19 yo", "35 year old") - calculate approximate 
   birth year by subtracting age from current note date year, use YYYY-01-01 format
3. If neither available, return "Not documented"

Examples:
- Patient.birthDate: "2005-03-15" → "2005-03-15"
- "19 yo female" in 2024 → "2005-01-01" (approximate)
- No age or DOB → "Not documented"
```

### 3. Enhance extent_of_resection Variable
**Current Instruction:**
```
Determine the extent of surgical resection from radiology reports or operative notes. 
Options: gross total resection, near total resection, subtotal resection, biopsy only, not specified.
```

**Updated Instruction:**
```
Determine the extent of surgical resection from radiology reports or operative notes. 
Look for explicit statements AND indirect evidence.

**Explicit evidence:**
- "gross total resection", "complete resection", "GTR"
- "near total resection", "NTR", "95% resection"
- "subtotal resection", "STR", "partial resection"
- "biopsy", "needle biopsy"

**Indirect evidence:**
- "surgical cavity", "resection bed", "postoperative changes" → likely resection occurred
- "enhancing cystic structures...gross total resection" → GTR
- "residual tumor", "incomplete resection" → subtotal

Return: gross total resection | near total resection | subtotal resection | biopsy only | not specified

Only use "not specified" if no direct or indirect evidence exists.
```

### 4. Filter surgery_type to Exclude Non-Surgical Procedures
**Current Instruction:**
```
Classify surgical procedure types from FHIR Procedure resources. 
Options: BIOPSY, DEBULKING, RESECTION, SHUNT, OTHER.
```

**Updated Instruction:**
```
Classify surgical procedure types from FHIR Procedure resources. Ignore non-surgical 
procedures like anesthesia, nursing orders, or administrative entries.

**Include:**
- Craniotomy, craniectomy procedures
- Tumor resection, debulking, excision
- Biopsy procedures  
- Shunt placement
- Any procedure with "SURGERY", "RESECTION", "CRANIOTOMY" in the name

**Exclude (mark as OTHER or skip):**
- Anesthesia procedures (ANES...)
- Surgical case requests/orders (administrative)
- Pre-operative or post-operative care orders
- Nursing procedures

Options: BIOPSY | DEBULKING | RESECTION | SHUNT | OTHER

If excluded, do not create an entry.
```

### 5. Update best_resection Decision to Prioritize Clinical Evidence
**Current Instruction:**
```
Aggregate surgery_type and extent_of_resection to determine the most extensive resection. 
Priority: GTR > Near Total > Subtotal > Debulking > Biopsy.
```

**Updated Instruction:**
```
Determine the most extensive resection the patient received by combining surgery_type 
and extent_of_resection variables. Prioritize radiological confirmation over procedure coding.

**Priority Order (most to least extensive):**
1. gross total resection (if in extent_of_resection)
2. near total resection (if in extent_of_resection)
3. subtotal resection (if in extent_of_resection)
4. RESECTION (from surgery_type)
5. DEBULKING (from surgery_type)
6. BIOPSY (from surgery_type or extent_of_resection)

**Logic:**
- If extent_of_resection contains GTR/NTR/STR, use that (radiology-confirmed)
- Otherwise, use highest-priority surgery_type
- If multiple surgeries, return the most extensive one

Examples:
- extent_of_resection: "gross total resection", surgery_type: DEBULKING → GTR
- extent_of_resection: "not specified", surgery_type: RESECTION, DEBULKING → RESECTION
- extent_of_resection: "subtotal resection", surgery_type: BIOPSY → subtotal resection
```

### 6. Add Text Extraction for Molecular Markers
**New instruction for idh_mutation:**
```
Extract IDH mutation status from pathology reports, molecular testing results, or 
clinical notes. Look for both structured FHIR Observation resources and unstructured text.

**Search patterns in text:**
- "IDH wildtype", "IDH wild-type", "IDH WT" → wildtype
- "IDH mutant", "IDH mutation", "IDH1 R132H", "IDH2" → mutant
- "IDH: negative", "no IDH mutation" → wildtype
- Negative mentions: "IDH testing not performed", "pending" → unknown

**Search in:**
1. FHIR Observation resources with code related to IDH
2. Pathology report text (DocumentReference)
3. Clinical note text mentioning "IDH" or "molecular"

Return: wildtype | mutant | unknown
```

---

## Recommendations for BRIM API Integration

To enable iterative improvement, we need:

### 1. **API Capabilities to Implement**
- ✅ Upload updated variables.csv and decisions.csv
- ✅ Trigger extraction job programmatically
- ✅ Monitor job status (polling or webhooks)
- ✅ Download results CSV when complete
- ✅ Compare results to baseline/ground truth

### 2. **Automated Iteration Workflow**
```
1. Generate CSVs with updated instructions
2. Upload to BRIM via API
3. Trigger extraction
4. Wait for completion (with timeout)
5. Download results
6. Parse and score accuracy
7. Identify remaining issues
8. Update instructions
9. Repeat until accuracy threshold met (e.g., 90%)
```

### 3. **Accuracy Metrics to Track**
- **Variable-level accuracy:** % correct for each variable
- **Patient-level accuracy:** % of variables correct per patient
- **Critical variable accuracy:** Focus on diagnosis, surgery, molecular markers
- **Extraction completeness:** % of variables with non-default values
- **Reasoning quality:** Review LLM reasoning for errors

### 4. **Ground Truth Needed**
To validate accuracy, we need:
- Manual chart review results (gold standard)
- Expected values for pilot patient 1277724
- Comparison CSVs from prior manual extraction
- Clinical expert validation

---

## Next Steps

### Immediate (Today)
1. ✅ Complete this analysis document
2. 🔄 Research BRIM API documentation/endpoints
3. 🔄 Create Python script for API interaction
4. 🔄 Update pilot_generate_brim_csvs.py with improved instructions

### Short-term (This Week)
5. Test updated configuration with BRIM
6. Implement automated iteration workflow
7. Validate improvements against ground truth
8. Document accuracy gains

### Medium-term (Next Sprint)
9. Expand to multiple patients
10. Add clinical note text extraction
11. Implement FHIR Observation extraction for molecular markers
12. Build accuracy dashboard

---

## Conclusion

The BRIM pilot extraction demonstrates strong performance on core clinical variables 
(diagnosis, surgery, demographics) but has critical issues with decision aggregation 
(total_surgeries = 0) and gaps in molecular marker extraction. 

**Key Findings:**
- ✅ 6/13 variables extracted accurately
- ❌ 2/5 decisions have significant errors
- 📊 Estimated current accuracy: ~60-70%
- 🎯 Target accuracy: 90%+

**Priority Fixes:**
1. Fix total_surgeries counting logic (critical bug)
2. Enhance date_of_birth to use age when DOB unavailable
3. Improve extent_of_resection and best_resection accuracy
4. Add text extraction for molecular markers

With API integration and iterative improvement, we can systematically address these 
issues and achieve production-ready accuracy.
