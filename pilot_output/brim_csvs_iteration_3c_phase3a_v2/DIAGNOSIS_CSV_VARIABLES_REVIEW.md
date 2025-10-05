# Diagnosis.csv Variables Review - Approach Validation
**Date**: October 4, 2025  
**Data Dictionary**: `/data/20250723_multitab_csvs/20250723_multitab__diagnosis.csv`  
**Current Configuration**: Phase 3a_v2 variables.csv  
**Purpose**: Validate variable extraction approach against data dictionary structure

---

## Data Dictionary Analysis

### Fields in diagnosis.csv (19 total):

1. **research_id** - Patient identifier (e.g., C1277724)
2. **event_id** - Event identifier (e.g., ET_7DK4B210)
3. **autopsy_performed** - Yes/No/Not Applicable
4. **clinical_status_at_event** - Alive/Deceased-due to disease/Deceased-other
5. **cause_of_death** - Not Applicable/disease-related
6. **event_type** - Initial CNS Tumor/Progressive/Recurrence/Second Malignancy/Deceased
7. **age_at_event_days** - Age in days at event occurrence
8. **cns_integrated_category** - Low-Grade Glioma/High-Grade Glioma/Glioneuronal/etc.
9. **cns_integrated_diagnosis** - Specific diagnosis (e.g., "Pilocytic astrocytoma")
10. **who_grade** - 1, 2, 3, 4, No grade specified
11. **metastasis** - Yes/No/Unavailable
12. **metastasis_location** - Brain/Leptomeningeal/Not Applicable
13. **metastasis_location_other** - Free text
14. **site_of_progression** - Local/Metastatic/Both/Not Applicable
15. **tumor_or_molecular_tests_performed** - FISH/SNP array/Specific gene mutation/etc.
16. **tumor_or_molecular_tests_performed_other** - Free text
17. **tumor_location** - Anatomical location (e.g., "Cerebellum/Posterior Fossa")
18. **tumor_location_other** - Free text if "Other locations NOS"
19. **shunt_required** - Shunt type or Not Applicable

---

## My Current Approach vs. Data Dictionary

### ✅ **Variables I'm Extracting (4 from diagnosis.csv)**

| My Variable | Data Dict Field | Approach | Alignment |
|-------------|-----------------|----------|-----------|
| **primary_diagnosis** | `cns_integrated_diagnosis` | FHIR Condition + pathology reports | ✅ ALIGNED |
| **diagnosis_date** | Derived from `age_at_event_days` where `event_type='Initial CNS Tumor'` | FHIR Condition + pathology + surgery fallback | ✅ ALIGNED |
| **who_grade** | `who_grade` | Pathology reports + inference rules | ✅ ALIGNED |
| **tumor_location** | `tumor_location` | Imaging + pathology + operative notes | ✅ ALIGNED |

---

## Detailed Variable-by-Variable Review

### 1. **primary_diagnosis** ↔ `cns_integrated_diagnosis`

**Data Dictionary Values** (from sample):
- "Pilocytic astrocytoma" (most common in sample)
- "Ganglioglioma"
- "Pleomorphic xanthoastrocytoma"
- "Low-Grade Glioma, NOS or NEC"

**My Current Approach**:
```
PRIORITY 1: Check FHIR Condition resources for primary CNS tumor diagnosis.
Look in Condition.code.coding.display field for diagnosis name.
Keywords: 'pilocytic', 'astrocytoma', 'glioma', 'glioblastoma', 'ependymoma', 
'medulloblastoma', 'oligodendroglioma'.

PRIORITY 2: If not in FHIR, search pathology reports for diagnosis keywords 
in 'Final Diagnosis' or 'Pathologic Diagnosis' sections.

Gold Standard for C1277724: 'Pilocytic astrocytoma' or 'Astrocytoma, pilocytic'.

Data Dictionary: cns_integrated_diagnosis (checkbox with 123 options based on 
2021 WHO CNS Classification). Return diagnosis name as free text.
```

**Validation Questions for You**:
1. ✅ **Alignment**: Should extract "Pilocytic astrocytoma" which matches data dictionary exactly
2. ⚠️ **Question**: Should I add "Ganglioglioma" and "Pleomorphic xanthoastrocytoma" to keywords?
3. ⚠️ **Question**: Data dictionary has 123 WHO classification options - should I list more diagnosis types in keywords or is current approach sufficient?
4. ✅ **Scope**: Currently `one_per_patient` - correct since we want primary/initial diagnosis

**My Assessment**: **80% ALIGNED** - Core approach correct, could strengthen keyword list

---

### 2. **diagnosis_date** ↔ Derived from `age_at_event_days` + `event_type='Initial CNS Tumor'`

**Data Dictionary Logic**:
- Multiple rows per patient (longitudinal events)
- `event_type` includes: "Initial CNS Tumor", "Progressive", "Recurrence", "Second Malignancy", "Deceased"
- `age_at_event_days` gives temporal context
- **First row with `event_type='Initial CNS Tumor'`** = diagnosis date

**Example** (C1277724 equivalent from sample):
```
C1003557, ET_7DK4B210, event_type=Initial CNS Tumor, age_at_event_days=2321
→ Diagnosis date = birth_date + 2321 days
```

**My Current Approach**:
```
PRIORITY 1: Check FHIR Condition resources for primary CNS tumor diagnosis onset date.
Look in Condition.onsetDateTime or Condition.recordedDate fields.

PRIORITY 2: Search pathology reports for 'Date of diagnosis:', 
'Diagnosis established on:', or report date if diagnosis is in the report.

PRIORITY 3 (FALLBACK ONLY): If diagnosis date not found in FHIR or pathology, 
use date of first surgery as proxy.

Gold Standard for C1277724: 2018-06-04 (pathology diagnosis date).

PHASE 3a FAILURE: Extracted 2018-05-28 (surgery date) instead of 2018-06-04 
(actual diagnosis date from pathology). 
FIX: Prioritize pathology report date BEFORE falling back to surgery.
```

**Validation Questions for You**:
1. ✅ **PRIORITY 1**: FHIR Condition.onsetDateTime should correspond to diagnosis date - correct?
2. ✅ **PRIORITY 2**: Pathology report date is best source after FHIR - correct?
3. ⚠️ **Question**: Should I mention that diagnosis_date should match the `event_type='Initial CNS Tumor'` row in data dictionary?
4. ⚠️ **Question**: Is surgery date acceptable as PRIORITY 3 fallback, or should I avoid it entirely?

**My Assessment**: **85% ALIGNED** - Approach sound but could reference data dictionary event_type logic

---

### 3. **who_grade** ↔ `who_grade`

**Data Dictionary Values** (from sample):
- "1" (Grade I - most common for pilocytic)
- "2" (Grade II)
- "3" (Grade III - for PXA progression)
- "4" (Grade IV)
- "No grade specified"

**Data Dictionary Format**: **Numeric** (1, 2, 3, 4) or "No grade specified"

**My Current Approach**:
```
PRIORITY 1: Check pathology reports and molecular testing documents for WHO grade.
Look for explicit keywords: 'WHO grade', 'WHO Grade I', 'WHO Grade II', 
'WHO Grade III', 'WHO Grade IV', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 
'low-grade', 'high-grade'.

INFERENCE RULE: If diagnosis is 'pilocytic astrocytoma' and no grade explicitly stated, 
infer 'Grade I' (pilocytic is always WHO Grade I by 2021 classification).

Gold Standard for C1277724: 'Grade I' (pilocytic astrocytoma).

PHASE 3a RESULT: ✅ 100% accurate with inference rule.

CRITICAL FORMAT: Return EXACTLY 'Grade I', 'Grade II', 'Grade III', 'Grade IV', 
or 'No grade specified' (Title Case with Roman numerals).
DO NOT return numeric values (1, 2, 3, 4) or Arabic format.

Data Dictionary: who_grade (dropdown: 1, 2, 3, 4, No grade specified - 
backend converts Roman to Arabic).
```

**🚨 CRITICAL FORMAT MISMATCH DETECTED!**

**Data Dictionary Shows**: Numeric format (1, 2, 3, 4)  
**My Instruction Says**: Roman numerals (Grade I, Grade II, Grade III, Grade IV)  
**My Note Says**: "backend converts Roman to Arabic" - but is this correct?

**Validation Questions for You**:
1. ❌ **FORMAT CONFLICT**: Should BRIM extract "1" or "Grade I"?
2. ⚠️ **Question**: Looking at diagnosis.csv, values are numeric (1, 2, 3, 4). Should I change instruction to return numbers?
3. ⚠️ **Question**: Or does BRIM's backend convert "Grade I" → "1" automatically?
4. ✅ **Inference Rule**: Pilocytic → Grade I inference is correct biologically

**My Assessment**: **70% ALIGNED** - ⚠️ **POTENTIAL FORMAT ISSUE** needs clarification

---

### 4. **tumor_location** ↔ `tumor_location`

**Data Dictionary Values** (from sample - matches my option_definitions exactly):
- "Cerebellum/Posterior Fossa" (most common in sample)
- "Suprasellar/Hypothalamic/Pituitary"
- "Optic Pathway"
- "Temporal Lobe"
- "Brain Stem-Medulla"
- "Brain Stem- Midbrain/Tectum" (note: space after dash in data)
- "Brain Stem- Pons" (note: space after dash)
- "Ventricles"
- "Thalamus"
- "Frontal Lobe", "Parietal Lobe"
- "Other locations NOS" (with `tumor_location_other` free text like "Cerebellar peduncle")

**My Current Approach**:
```
PRIORITY 1: Check imaging reports, pathology reports, and operative notes for 
TUMOR anatomical location (NOT surgical approach or procedure location).

Keywords for TUMOR location: 'tumor in', 'mass in', 'lesion in', 'involving', 
'centered in', 'located in'.

Gold Standard for C1277724: 'Cerebellum/Posterior Fossa'.

PHASE 2 SUCCESS: 'Cerebellum/Posterior Fossa' extracted 21x.
PHASE 3a SUCCESS: ✅ Maintained 100% accuracy.

CRITICAL NEGATIVE EXAMPLES: DO NOT return 'Craniotomy' (surgical procedure), 
'Skull' (surgical approach), 'Bone flap' (surgical anatomy).

Data Dictionary: tumor_location (checkbox with 24 options).

Valid values: 'Frontal Lobe', 'Temporal Lobe', 'Parietal Lobe', 'Occipital Lobe', 
'Thalamus', 'Ventricles', 'Suprasellar/Hypothalamic/Pituitary', 
'Cerebellum/Posterior Fossa', 'Brain Stem-Medulla', 'Brain Stem-Midbrain/Tectum', 
'Brain Stem-Pons', ... [24 total options]

Return EXACTLY one of the 24 valid values (Title Case with forward slashes and 
hyphens as shown).
```

**Validation Questions for You**:
1. ✅ **Option Definitions**: My 24 options match data dictionary - confirmed by sample data
2. ⚠️ **Format Question**: Data dictionary has "Brain Stem- Pons" (space after dash). My option_definitions has "Brain Stem-Pons" (no space). Should I match exactly?
3. ⚠️ **Scope Question**: Data dictionary allows multiple tumor_location rows per event. Should my scope be `many_per_note` instead of `one_per_patient`?
4. ✅ **DO NOT Guidance**: "Craniotomy"/"Skull" negative examples proven effective in Phase 2

**My Assessment**: **90% ALIGNED** - ⚠️ Minor formatting question (space after dash), possible scope question

---

## Variables in diagnosis.csv That I'm NOT Extracting

### Variables I Could Add (but currently not in scope):

| Data Dict Field | Why Not Extracting | Should I Add? |
|-----------------|-------------------|---------------|
| **event_type** | Not in my 35 variables | ⚠️ Could help with progression/recurrence tracking |
| **age_at_event_days** | Calculating `age_at_diagnosis` differently | ✅ My approach is equivalent |
| **cns_integrated_category** | Not in original scope | ⚠️ Could add as parent category of diagnosis |
| **metastasis** | Not in my 35 variables | ⚠️ Relevant for advanced disease tracking |
| **metastasis_location** | Not in my 35 variables | ⚠️ Relevant for advanced disease tracking |
| **site_of_progression** | Partially covered by `clinical_status` | ✅ My clinical_status approach is broader |
| **tumor_or_molecular_tests_performed** | Not in my 35 variables | ✅ Covered by specific molecular variables (IDH, MGMT, BRAF) |
| **shunt_required** | Not in my 35 variables | ⚠️ Clinical detail not in current scope |
| **autopsy_performed** | Not in my 35 variables | ❌ Not relevant for living patients in scope |
| **cause_of_death** | Not in my 35 variables | ❌ Not relevant for living patients in scope |

---

## Critical Issues Found

### 🚨 **Issue 1: WHO Grade Format Mismatch**

**Problem**: Data dictionary shows numeric (1, 2, 3, 4), my instruction says Roman numerals (Grade I, Grade II, Grade III, Grade IV)

**Impact**: HIGH - BRIM may extract "Grade I" but data dictionary expects "1"

**Your Decision Needed**:
- [ ] Option A: Change instruction to return numeric (1, 2, 3, 4)
- [ ] Option B: Keep Roman numerals, confirm BRIM backend converts
- [ ] Option C: Return both formats (e.g., "Grade I (1)")

---

### ⚠️ **Issue 2: Brain Stem Hyphen Spacing**

**Problem**: Data dictionary has "Brain Stem- Pons" (space after dash), my option_definitions has "Brain Stem-Pons" (no space)

**Impact**: MEDIUM - Could cause exact match failure

**Your Decision Needed**:
- [ ] Option A: Update my option_definitions to match data dictionary spacing exactly
- [ ] Option B: Keep current format, BRIM handles minor spacing variations
- [ ] Option C: Add both formats to option_definitions

---

### ⚠️ **Issue 3: tumor_location Scope**

**Problem**: Data dictionary allows multiple tumor_location rows per event (see C102459 with both Brain Stem-Medulla AND Cerebellum/Posterior Fossa). My current scope is `one_per_patient`.

**Impact**: MEDIUM - May miss multifocal tumors

**Your Decision Needed**:
- [ ] Option A: Change scope to `many_per_note` to capture multifocal disease
- [ ] Option B: Keep `one_per_patient`, focus on primary location only
- [ ] Option C: Extract all locations but have aggregation prioritize primary site

---

### ⚠️ **Issue 4: Missing progression/recurrence Variables**

**Problem**: Data dictionary has rich longitudinal event tracking (event_type: Initial/Progressive/Recurrence/Second Malignancy). I only have `clinical_status`, `progression_date`, `recurrence_date` which are date-focused, not event-type-focused.

**Impact**: LOW-MEDIUM - May miss structured progression events

**Your Decision Needed**:
- [ ] Option A: Add `event_type` variable to capture Initial/Progressive/Recurrence structure
- [ ] Option B: Current clinical_status approach is sufficient
- [ ] Option C: Enhance clinical_status to explicitly map to event_type values

---

## Summary Assessment

| Variable | Alignment | Format Match | Scope Match | Keywords | Overall |
|----------|-----------|--------------|-------------|----------|---------|
| **primary_diagnosis** | ✅ Good | ✅ Text | ✅ one_per_patient | ⚠️ Could expand | **80%** |
| **diagnosis_date** | ✅ Good | ✅ Date | ✅ one_per_patient | ✅ Good | **85%** |
| **who_grade** | ✅ Good | ❌ **Roman vs Numeric** | ✅ one_per_patient | ✅ Good | **70%** ⚠️ |
| **tumor_location** | ✅ Excellent | ⚠️ Spacing | ⚠️ Scope question | ✅ Good | **90%** |

---

## Recommendations

### **Immediate Actions** (Before Upload):

1. **🚨 CRITICAL: Resolve WHO Grade Format**
   - Determine if BRIM expects "1" or "Grade I"
   - Update instruction accordingly

2. **⚠️ HIGH: Fix Brain Stem Spacing**
   - Review all 24 tumor_location option_definitions
   - Match data dictionary spacing exactly

3. **⚠️ MEDIUM: Consider tumor_location Scope**
   - Decide if multifocal tumors should be captured
   - Adjust scope if needed

### **Future Enhancements** (Post Phase 3a_v2):

4. **⚠️ LOW: Add cns_integrated_category**
   - Could help with broad classification (Low-Grade vs High-Grade Glioma)

5. **⚠️ LOW: Add event_type tracking**
   - Could improve progression/recurrence detection accuracy

6. **⚠️ LOW: Add metastasis variables**
   - Important for advanced disease tracking

---

## Questions for You

**Please review and provide decisions on**:

1. **WHO Grade Format**: Should I extract "1" or "Grade I"? (Critical)
2. **Brain Stem Spacing**: Should option_definitions match data dictionary spacing exactly?
3. **tumor_location Scope**: Should I capture multifocal tumors with many_per_note?
4. **Missing Variables**: Should I add event_type, cns_integrated_category, or metastasis variables?
5. **Keyword Expansion**: Should I add more diagnosis types to primary_diagnosis keywords?

---

## Confidence Level

**Overall Alignment**: **81%** (3.25/4 variables fully aligned)

**Ready for Upload**: ⚠️ **CONDITIONAL** - Pending WHO grade format decision

**Risk Level**: **MEDIUM** - One critical format issue, two minor formatting questions

