# Gold Standard Contamination Assessment

**Date**: October 5, 2025  
**Issue**: Found patient-specific gold standard values in extraction prompts  
**Impact**: Compromises generalizability of extraction framework

---

## Patient-Specific Gold Standards (DO NOT INCLUDE IN PROMPTS)

These are the **ACTUAL ANSWERS** for this specific patient:

### Demographics
- **DOB**: 2005-05-13
- **Gender**: Female
- **Race**: White
- **Ethnicity**: Not Hispanic or Latino

### Diagnosis
- **Primary diagnosis**: Pilocytic astrocytoma
- **Diagnosis date**: 2018-06-15  
- **WHO grade**: Grade I (for this diagnosis)
- **Tumor location**: Cerebellum/Posterior Fossa

### Surgeries
- **Surgery 1**: 2018-05-28, Partial Resection, Cerebellum/Posterior Fossa
- **Surgery 2**: 2021-03-10, Partial Resection, Cerebellum/Posterior Fossa

### Medications
- **Chemotherapy**: Bevacizumab (2019-05-15 to 2021-04-30)
- **Concomitant**: Vinblastine, Selumetinib

---

## What IS Acceptable in Prompts (Generic Examples)

### ✅ VALID VALUES Lists
These are **generic options** that BRIM needs to know are valid:
- WHO grades: "Grade I, Grade II, Grade III, Grade IV, No grade specified"
- Surgical extents: "Gross Total Resection, Subtotal Resection, Partial Resection, Biopsy Only"
- Anatomical locations: "Cerebellum/Posterior Fossa, Frontal Lobe, Temporal Lobe, ..." (full list of 24)

**Why acceptable?** These are standard medical vocabularies, not patient-specific answers.

### ✅ Generic Examples (NOT from this patient)
- primary_diagnosis EXAMPLES: "Glioblastoma multiforme, Diffuse astrocytoma, Oligodendroglioma"
- who_grade INFERENCE: "If diagnosis='Glioblastoma' → infer 'Grade IV'"

**Why acceptable?** These demonstrate format but don't reveal THIS patient's data.

---

## What IS NOT Acceptable (Contamination)

### ❌ Patient-Specific Examples
- primary_diagnosis EXAMPLES: "Pilocytic astrocytoma" ← **THIS IS THE ANSWER!**
- who_grade INFERENCE: "If diagnosis='Pilocytic astrocytoma' → infer 'Grade I'" ← **REVEALS ANSWER!**
- Date references: "2018-05-28", "2018-06-15", "2021-03-10"

**Why not acceptable?** These directly tell BRIM what this patient's answers should be.

---

## Contamination Found & Fixed

### Variables Fixed (2)

#### 1. primary_diagnosis
- **Contamination**: EXAMPLES section included "Pilocytic astrocytoma" (this patient's actual diagnosis)
- **Fix**: Replaced with "Glioblastoma multiforme, Diffuse astrocytoma, Oligodendroglioma"
- **Status**: ✅ FIXED

#### 2. who_grade  
- **Contamination**: INFERENCE RULES mentioned "If diagnosis='Pilocytic astrocytoma' → Grade I"
- **Fix**: Replaced with "If diagnosis='Glioblastoma' → Grade IV"
- **Status**: ✅ FIXED

### False Positives (3) - Actually OK

#### 1. surgery_extent
- **Found**: "Partial Resection" in VALID VALUES list
- **Assessment**: ✅ ACCEPTABLE - this is a standard surgical option, not uniquely identifying this patient
- **Action**: No change needed

#### 2. tumor_location
- **Found**: "Cerebellum/Posterior Fossa" in VALID VALUES list (1 of 24 options)
- **Assessment**: ✅ ACCEPTABLE - standard anatomical term in complete location vocabulary
- **Action**: No change needed

#### 3. who_grade
- **Found**: "Grade I" in VALID VALUES list
- **Assessment**: ✅ ACCEPTABLE - one of 5 valid grade options
- **Action**: No change needed

---

## Verification Results

### ✅ All Patient-Specific Values Removed

**Checked for:**
- ✅ Pilocytic astrocytoma (in EXAMPLES) - REMOVED
- ✅ 2018-05-28, 2018-06-15, 2021-03-10 (dates) - NOT FOUND
- ✅ C1277724 (RxNorm code) - NOT FOUND
- ✅ Patient-specific inference rules - REMOVED

### ✅ Generic Vocabularies Preserved

**Kept as-is:**
- ✅ VALID VALUES lists (standard medical vocabularies)
- ✅ Generic examples from other diagnoses
- ✅ Structural instructions (extraction logic)

---

## Principle for Future Prompts

### The "Blind Test" Rule

**Would this prompt work for a completely different patient?**

- ✅ **YES**: "Extract WHO grade. Valid options: Grade I, Grade II, Grade III, Grade IV"
  - Works for any patient, provides vocabulary guidance

- ❌ **NO**: "Extract WHO grade. Examples: Grade I for Pilocytic astrocytoma"
  - Reveals this patient's diagnosis-grade pair

### When in Doubt

**If a value appears in our reference gold standards for THIS patient:**
1. Check if it's in a VALID VALUES list (vocabulary) → OK
2. Check if it's in an EXAMPLES section → REMOVE if patient-specific
3. Check if it's in an INFERENCE rule → REMOVE if patient-specific

**Generalizable prompts work for ANY patient, not just our pilot case.**

---

## Final Status

✅ **variables.csv**: 24 variables, 0 contaminated  
✅ **decisions.csv**: 13 decisions, 0 contaminated  
✅ **project.csv**: 396 documents (no patient data in prompts)

**Ready for generalizable extraction testing.**
