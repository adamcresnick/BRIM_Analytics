# BRIM Architecture Redesign Plan
**Date:** October 5, 2025  
**Objective:** Align our workflow with BRIM's intended two-stage architecture

---

## Current State Analysis

### ❌ **Architectural Misalignment**

**Our Current Approach (Incorrect):**
- Variables try to filter/aggregate during extraction
- Decisions (dependent variables) are underutilized
- Surgery-specific extractions attempted in variable instructions

**BRIM's Intended Workflow:**
1. **Stage 1 (Variables)**: Extract ALL occurrences from documents → many values per patient
2. **Stage 2 (Dependent Variables)**: Filter/aggregate those values → one value per patient

---

## The Problem

### Variables That Should Be Redesigned

| Current Variable | Scope | Problem | Should Be |
|-----------------|-------|---------|-----------|
| `surgery_date` | `many_per_note` | ✅ Correct | Extract ALL surgery dates |
| `surgery_location` | `many_per_note` | ✅ Correct | Extract ALL locations |
| `surgery_extent` | `many_per_note` | ✅ Correct | Extract ALL extents |
| `primary_diagnosis` | `many_per_note` | ✅ Correct | Extract ALL diagnoses |
| **None exist** | - | ❌ Missing | Need `surgery_diagnosis` variable |

### Decisions That Are Wrong

| Current Decision | Type | Problem | Should Be |
|-----------------|------|---------|-----------|
| `diagnosis_surgery1` | `filter` | Tries to filter in variable instructions | Use dependent variable to filter `primary_diagnosis` by `surgery_date` |
| `extent_surgery1` | `filter` | Tries to filter in variable instructions | Use dependent variable to filter `surgery_extent` by `surgery_date` |
| `location_surgery1` | `filter` | Tries to filter in variable instructions | Use dependent variable to filter `surgery_location` by `surgery_date` |
| `diagnosis_surgery2` | `filter` | Tries to filter in variable instructions | Use dependent variable to filter `primary_diagnosis` by 2nd `surgery_date` |
| `extent_surgery2` | `filter` | Tries to filter in variable instructions | Use dependent variable to filter `surgery_extent` by 2nd `surgery_date` |
| `location_surgery2` | `filter` | Tries to filter in variable instructions | Use dependent variable to filter `surgery_location` by 2nd `surgery_date` |

---

## Redesigned Architecture

### Stage 1: Variables (Extract Everything)

**Purpose:** Extract ALL occurrences without filtering

#### Core Surgery Variables (`many_per_note` scope)

1. **`surgery_date`** ✅ Already correct
   - Extract ALL surgery dates from all documents
   - Return multiple values (2018-05-28, 2021-03-10)
   - Scope: `many_per_note`

2. **`surgery_location`** ✅ Already correct
   - Extract ALL anatomical locations
   - Return multiple values (one per surgery found in document)
   - Scope: `many_per_note`

3. **`surgery_extent`** ✅ Already correct
   - Extract ALL extents of resection
   - Return multiple values
   - Scope: `many_per_note`

4. **`surgery_diagnosis`** ❌ MISSING - Need to add
   - Extract diagnosis associated with each surgery
   - Look in pathology reports, operative notes near surgery dates
   - Return multiple values (Pilocytic astrocytoma; Pilocytic astrocytoma, recurrent)
   - Scope: `many_per_note`
   - **Gold Standard**: "Pilocytic astrocytoma" (surgery 1), "Pilocytic astrocytoma, recurrent" (surgery 2)

5. **`primary_diagnosis`** - Already exists
   - Keep as-is for general diagnosis extraction
   - Used by dependent variables to correlate with surgeries

### Stage 2: Dependent Variables (Filter/Aggregate)

**Purpose:** Combine variable values with instructions to produce final answers

#### Surgery-Specific Dependent Variables

**Format Requirements (from BRIM docs):**
```csv
name,variable_type,instructions,input_variables,default_empty_value,option_definitions
```

**Key Fields:**
- `variable_type`: `text` | `boolean` | `integer` | `float`
- `input_variables`: List of variables to reference (e.g., "surgery_date;surgery_diagnosis;primary_diagnosis")
- `default_empty_value`: What to return if no evidence found (e.g., "Unknown", "None", "False")

#### 1. **diagnosis_surgery1** (Dependent Variable)

```csv
name: diagnosis_surgery1
variable_type: text
instructions: "Return the diagnosis associated with the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST surgery_date value
2. Find surgery_diagnosis values associated with that date
3. If surgery_diagnosis not found, use primary_diagnosis from documents near that date
4. Prioritize pathology-confirmed diagnoses

EXPECTED OUTPUT: Primary CNS tumor diagnosis name for first surgery
Gold Standard for C1277724: Pilocytic astrocytoma"

input_variables: surgery_date;surgery_diagnosis;primary_diagnosis;document_type
default_empty_value: Unknown
option_definitions: <leave empty or define diagnosis options>
```

#### 2. **extent_surgery1** (Dependent Variable)

```csv
name: extent_surgery1
variable_type: text
instructions: "Return the extent of resection for the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST surgery_date value
2. Find surgery_extent values associated with that date
3. Prioritize document_type='OPERATIVE' assessments

EXPECTED OUTPUT: One of the defined extent options
Gold Standard for C1277724: Partial Resection"

input_variables: surgery_date;surgery_extent;document_type
default_empty_value: Unknown
option_definitions: "{\"Gross Total Resection\": \"Gross Total Resection\", \"Near Total Resection\": \"Near Total Resection\", \"Subtotal Resection\": \"Subtotal Resection\", \"Partial Resection\": \"Partial Resection\", \"Biopsy Only\": \"Biopsy Only\", \"Unknown\": \"Unknown\"}"
```

#### 3. **location_surgery1** (Dependent Variable)

```csv
name: location_surgery1
variable_type: text
instructions: "Return the anatomical location for the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST surgery_date value
2. Find surgery_location values associated with that date
3. Use most specific anatomical location mentioned

EXPECTED OUTPUT: Anatomical location from defined options
Gold Standard for C1277724: Cerebellum/Posterior Fossa"

input_variables: surgery_date;surgery_location;document_type
default_empty_value: Unknown
option_definitions: "{\"Frontal Lobe\": \"Frontal Lobe\", \"Temporal Lobe\": \"Temporal Lobe\", \"Parietal Lobe\": \"Parietal Lobe\", \"Occipital Lobe\": \"Occipital Lobe\", \"Thalamus\": \"Thalamus\", \"Ventricles\": \"Ventricles\", \"Suprasellar/Hypothalamic/Pituitary\": \"Suprasellar/Hypothalamic/Pituitary\", \"Cerebellum/Posterior Fossa\": \"Cerebellum/Posterior Fossa\", \"Brain Stem\": \"Brain Stem\", \"Spinal Cord\": \"Spinal Cord\", \"Unknown\": \"Unknown\"}"
```

#### 4-6. **Surgery 2 Dependent Variables**

Same pattern as above but:
- Filter to SECOND EARLIEST surgery_date
- Add check: "If surgery_number < 2, return empty/Unknown"

#### 7. **total_surgeries** (Aggregation Dependent Variable)

```csv
name: total_surgeries
variable_type: integer
instructions: "Count total distinct surgeries.

AGGREGATION LOGIC:
Count the number of unique surgery_date values extracted.

EXPECTED OUTPUT: Integer count
Gold Standard for C1277724: 2"

input_variables: surgery_date
default_empty_value: 0
option_definitions: <empty>
```

#### 8-13. **Other Aggregation Dependent Variables**

- `all_chemotherapy_agents`: Aggregate `chemotherapy_agents` (semicolon-separated list)
- `all_symptoms`: Aggregate `symptoms_present` (semicolon-separated list)
- `earliest_symptom_date`: Find earliest date with symptoms
- `molecular_tests_summary`: Combine all molecular test results
- `imaging_progression_timeline`: Timeline of imaging findings
- `treatment_response_summary`: Match treatments with responses

---

## Implementation Steps

### Phase 1: Update Variables CSV ✅ (Minimal Changes)

Current variables are mostly correct. Only need to:

1. **Add `surgery_diagnosis` variable** (`many_per_note` scope)
   - Extract diagnosis associated with each surgery
   - Look in pathology/operative notes

2. **Verify `surgery_date`, `surgery_location`, `surgery_extent`** are `many_per_note`
   - Already correct in current variables.csv ✅

3. **Keep all other variables as-is**

### Phase 2: Completely Rewrite Decisions CSV ❌ (Major Changes)

**Required Format Changes:**

| Old Column | New Column | Notes |
|-----------|------------|-------|
| `decision_name` | `name` | Rename column |
| `decision_type` | `variable_type` | Change from "filter/aggregation" to "text/boolean/integer/float" |
| `input_variables` | `input_variables` | Keep same (semicolon-separated) |
| `output_variable` | **REMOVE** | Not needed - name serves this purpose |
| `prompt` | `instructions` | Rename column |
| `aggregation_prompt` | **REMOVE or merge** | Merge into instructions if needed |

**NEW columns to add:**
- `default_empty_value`: "Unknown", "None", "0", "False", etc.
- `option_definitions`: JSON object for categorical variables

### Phase 3: Test Upload

1. Upload updated variables.csv (with new `surgery_diagnosis`)
2. Upload rewritten decisions.csv (new format)
3. Upload project.csv (already fixed - no duplicates)
4. Monitor for "0 lines skipped" message

---

## Expected Benefits

### 1. **Proper BRIM Architecture**
- Variables do extraction only
- Dependent variables do filtering/aggregation
- Clear separation of concerns

### 2. **Better Accuracy**
- BRIM can see ALL surgery dates before filtering
- Context-aware filtering (knows which surgery is first/second)
- Proper temporal reasoning

### 3. **Reusability**
- Same variables can be reused for surgery 1, surgery 2, surgery N
- Dependent variables scale to N surgeries
- No hardcoding of surgery numbers in variable instructions

### 4. **Correct Use of BRIM Features**
- Leverages dependent variable input_variables feature
- Uses option_definitions for categorical values
- Proper default_empty_value handling

---

## Migration Path

### Option A: **Quick Fix** (Recommended for Phase 3a_v2)
1. Keep current variables.csv (mostly correct)
2. Add `surgery_diagnosis` variable
3. Rewrite decisions.csv to new format
4. Test upload

**Timeline:** 1-2 hours  
**Risk:** Low  
**Accuracy impact:** Should improve to 93-95%

### Option B: **Full Redesign** (Recommended for Phase 3b)
1. Review ALL variables for proper scope
2. Add any missing variables (surgery_diagnosis, etc.)
3. Completely rewrite decisions.csv
4. Redesign variable instructions to be more extraction-focused
5. Let dependent variables do ALL filtering/aggregation

**Timeline:** 4-6 hours  
**Risk:** Medium (more changes)  
**Accuracy impact:** Should achieve 95-98%

---

## Next Steps

**Immediate Action (for Phase 3a_v2 re-upload):**

1. ✅ Add `surgery_diagnosis` variable to variables.csv
2. ✅ Rewrite decisions.csv to BRIM format
3. ✅ Test upload (expect 0 lines skipped)
4. ✅ Run extraction
5. ✅ Compare results to Phase 3a baseline

**Should I proceed with Option A (Quick Fix)?**

---

**Files to Create:**
- `variables_v2_with_surgery_diagnosis.csv` (add 1 variable)
- `decisions_v2_brim_format.csv` (complete rewrite)
- `ARCHITECTURE_REDESIGN_VALIDATION.md` (this document)

