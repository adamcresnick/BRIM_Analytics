# Longitudinal Data Model Requirements for BRIM Oncology Extraction

**Date:** October 2, 2025  
**Analysis:** Data Structure Review

## Executive Summary

The BRIM extraction framework must handle **longitudinal oncology data** where patients undergo multiple treatments over time. This is especially critical for brain tumor patients who may have:
- Initial resection surgery
- Recurrence surgeries (months/years later)
- Multiple tumor locations
- Progressive treatment courses
- Evolving molecular profiles

## Current Patient Case Study: 1277724

### Clinical Timeline (Evidence from Data)

**Patient:** 19 yo female with **recurrent** pilocytic astrocytoma

**Surgical History (Multiple Procedures):**
1. **March 10, 2021**: Initial posterior fossa surgery
   - Two procedures on same date per FHIR Procedure resources
   - "CRANIEC TREPHINE BONE FLP BRAIN TUMOR SUPRTENTOR"
   - "CRNEC INFRATNTOR/POSTFOSSA EXC/FENESTRATION CYST" (DEBULKING)

2. **Left parietal craniotomy** (date unknown from current data)
   - Radiology note: "surgical changes of prior left parietal craniotomy"
   - "associated parietal surgical cavity and peripheral gliosis"

3. **Right frontal shunt placement** (date unknown)
   - "right transfrontal shunt track"
   - "right frontal catheter tracts with surrounding encephalomalacia/gliosis"

**Current Status (2024):**
- On targeted therapy (Selumetinib)
- Follow-up imaging for "recurrent" disease
- Multiple post-surgical changes visible on MRI

### Data Model Implications

#### 1. **Surgery Data Must Be Granular**

**Current BRIM Scope: `many_per_note`**
- ✅ **Correct**: Allows multiple surgery_date entries
- ✅ **Correct**: Allows multiple surgery_type entries
- ✅ **Correct**: Allows multiple extent_of_resection entries

**Critical Requirement:** Each surgery should be extractable with:
- Surgery date
- Surgery type
- Surgery location (anatomical site)
- Extent of resection (for that specific surgery)
- Outcome/complications

**Problem:** Current FHIR Bundle only contains 2021-03-10 surgeries. Missing:
- Prior left parietal craniotomy date
- Prior right frontal shunt placement date

**Solution:** 
- Extract ALL surgeries mentioned in radiology/narrative notes
- Parse phrases like "status post surgery on [date]", "prior surgery", "previous craniotomy"
- Infer surgery dates from imaging timepoints when explicit dates unavailable

#### 2. **Temporal Relationships Matter**

**Scenarios to Handle:**
1. **Initial vs. Recurrence Surgery**
   - "Initial resection 2021" → "Recurrence surgery 2023"
   - Different outcomes for same patient

2. **Sequential Surgeries for Same Tumor**
   - Incomplete resection → Re-resection weeks later
   - Both surgeries should be captured

3. **Multiple Tumors/Locations**
   - Posterior fossa tumor → separate parietal tumor
   - Each location may have different histology, grade, molecular profile

#### 3. **Aggregation Logic for Decisions**

**Current Issue:** `total_surgeries` returned 0 when should be ≥3

**Root Cause Analysis:**
- Instruction: "Count unique surgery_date values"
- Problem: Only 1 unique date found (2021-03-10)
- Multiple procedures on same date counted as 1
- Surgeries mentioned in radiology (without FHIR Procedure resources) not counted

**Corrected Logic:**
```
total_surgeries should count:
1. All distinct surgery_date entries from FHIR Procedures
2. PLUS: Surgeries mentioned in narrative without structured dates
   - "prior left parietal craniotomy" = 1 additional surgery
   - "right frontal shunt" = 1 additional surgery
3. Method: Count anatomical site mentions when dates unavailable
```

**New Instruction for total_surgeries:**
```
Count all unique surgical procedures the patient has undergone across entire medical history. 
Include:
1. Count distinct surgery_date values where surgery_type != OTHER
2. Count surgeries mentioned in clinical notes without explicit dates (e.g., "status post 
   prior craniotomy", "previous resection", "surgical changes from prior surgery")
3. Identify unique anatomical locations (posterior fossa, parietal, frontal) as indicators 
   of separate surgeries

Examples:
- "surgery on 2021-03-10" + "prior left parietal craniotomy" = 2 surgeries
- Same date, 2 procedures, same location = 1 surgery
- Same date, 2 procedures, different locations = 2 surgeries

Return total count as number string.
```

#### 4. **Best Resection Logic for Multiple Surgeries**

**Current Issue:** Returned "DEBULKING" but radiology shows "gross total resection"

**Problem:** Temporal confusion - which surgery achieved GTR?

**Analysis:**
- 2021 surgery: Type = DEBULKING
- Post-2021 imaging: "gross total resection of enhancing cystic structures in posterior fossa"
- Interpretation: Later imaging confirmed GTR was achieved (either at time of 2021 surgery or subsequent surgery)

**Corrected Logic:**
```
best_resection across ALL surgeries means:
1. Find ALL extent_of_resection entries
2. Find ALL surgery_type entries
3. Take the MOST EXTENSIVE across entire history
4. Priority: GTR > Near Total > Subtotal > Debulking > Biopsy

Do NOT assume procedure coding (DEBULKING) overrides radiological confirmation (GTR).
Radiology reports provide ground truth for actual extent achieved.
```

#### 5. **Variable Scope Design Principles**

| Variable | Scope | Rationale |
|----------|-------|-----------|
| **surgery_date** | `many_per_note` | ✅ Each surgery has a date |
| **surgery_type** | `many_per_note` | ✅ Each surgery has a type |
| **extent_of_resection** | `many_per_note` | ✅ Each surgery has an extent |
| **surgery_location** | `many_per_note` | ⚠️ MISSING - need to add |
| **total_surgeries** | `one_per_patient` | ✅ Aggregate count |
| **best_resection** | `one_per_patient` | ✅ Best across all surgeries |
| **initial_surgery_date** | `one_per_patient` | ⚠️ MISSING - earliest surgery |
| **most_recent_surgery_date** | `one_per_patient` | ⚠️ MISSING - latest surgery |

#### 6. **Treatment Timeline Tracking**

**For Longitudinal Analysis, Need:**

**Initial Treatment Phase:**
- Initial diagnosis date
- Initial surgery date
- Initial surgery extent
- Initial pathology
- Initial molecular markers

**Recurrence/Progression Phase:**
- Recurrence date
- Salvage surgery date(s)
- Salvage surgery extent(s)
- Re-biopsy molecular markers (may change)

**Current Treatment Phase:**
- Most recent treatment
- Current therapy (Selumetinib in this case)
- Current disease status

#### 7. **Recommended Variable Additions**

```python
# ADD to variables list:

{
    'variable_name': 'surgery_location',
    'instruction': 'Extract anatomical location of surgery. Common brain locations: 
        posterior fossa, cerebellum, frontal lobe, parietal lobe, temporal lobe, 
        occipital lobe, midbrain, thalamus, brainstem, ventricles. Look in operative 
        reports or radiology descriptions of "surgical changes" / "craniotomy" / 
        "resection cavity". Return specific anatomical location per surgery.',
    'variable_type': 'text',
    'scope': 'many_per_note',
},

{
    'variable_name': 'initial_surgery_date',
    'instruction': 'Find the EARLIEST/FIRST surgery date for this patient. Look for 
        phrases like "initial resection", "initial surgery", "first craniotomy", or 
        determine earliest date from all surgery_date entries. Return in YYYY-MM-DD format.',
    'variable_type': 'text',
    'scope': 'one_per_patient',
},

{
    'variable_name': 'recurrence_surgery',
    'instruction': 'Determine if patient had surgery for tumor recurrence/progression. 
        Look for: "recurrent tumor", "tumor recurrence", "progression", "salvage surgery", 
        "second-look surgery", "re-resection". Return true if recurrence surgery performed, 
        false if only initial surgery, unknown if cannot determine.',
    'variable_type': 'boolean',
    'scope': 'one_per_patient',
},

{
    'variable_name': 'disease_status',
    'instruction': 'Extract current disease status. Options: newly diagnosed (initial 
        diagnosis, treatment-naive), stable (no progression), progressive (growing/worsening), 
        recurrent (returned after remission), unknown. Look in latest clinical notes or 
        radiology impression.',
    'variable_type': 'text',
    'scope': 'one_per_patient',
    'option_definitions': '{"newly_diagnosed": "Initial diagnosis", "stable": "Stable disease", 
        "progressive": "Progressive disease", "recurrent": "Recurrent disease", "unknown": "Unknown status"}',
}
```

## Revised Decision Instructions

### total_surgeries (CRITICAL FIX)

```python
{
    'decision_name': 'total_surgeries',
    'instruction': '''Count total number of unique surgical procedures across patient's 
        entire treatment history. 
        
        METHOD:
        1. Count unique surgery_date entries (where surgery_type != OTHER)
        2. ALSO count surgeries mentioned in narrative without explicit dates:
           - Look for: "prior craniotomy", "previous resection", "status post surgery"
           - Look for: Multiple anatomical locations (posterior fossa, parietal, frontal)
           - Each unique location suggests separate surgery
        3. If same date but different locations → count separately
        4. If same date and same location → count as one surgery
        
        EXAMPLES:
        - surgery_date=2021-03-10 (posterior fossa) + "prior left parietal craniotomy" 
          + "right frontal shunt" = 3 surgeries
        - surgery_date=2021-03-10 (2 procedures, same site) = 1 surgery
        - Two surgeries mentioned, no dates = return "2" based on narrative
        
        Return count as number string ("1", "2", "3", etc.).
        If no surgeries mentioned anywhere, return "0".''',
    'decision_type': 'text',
    'variables': '["surgery_date", "surgery_type", "surgery_location"]',
    'default_value_for_empty_response': '0'
}
```

### best_resection (IMPROVED)

```python
{
    'decision_name': 'best_resection',
    'instruction': '''Determine the MOST EXTENSIVE tumor resection achieved across ALL 
        surgeries in patient's history.
        
        PRIORITY ORDER (most to least extensive):
        1. gross total resection (GTR) - from extent_of_resection
        2. near total resection (NTR) - from extent_of_resection  
        3. subtotal resection (STR) - from extent_of_resection
        4. RESECTION - from surgery_type
        5. DEBULKING - from surgery_type
        6. BIOPSY - from either variable
        
        IMPORTANT:
        - ALWAYS prioritize extent_of_resection over surgery_type (radiological 
          confirmation is more accurate than procedure coding)
        - If radiology states "gross total resection" but procedure coded as "debulking", 
          return "gross total resection"
        - Search ALL extent_of_resection and surgery_type entries
        - Return the BEST outcome ever achieved, not just most recent
        
        EXAMPLES:
        - extent=["not specified", "gross total resection", "not specified"], 
          type=[DEBULKING, OTHER] → "gross total resection"
        - extent=["subtotal resection"], type=[RESECTION, BIOPSY] → "subtotal resection"
        - extent=["not specified"], type=[DEBULKING, RESECTION] → "RESECTION"
        
        Return the most extensive resection category achieved.''',
    'decision_type': 'text',
    'variables': '["surgery_type", "extent_of_resection"]',
}
```

## Testing Plan

### 1. Regenerate CSVs with Updated Instructions
```bash
python scripts/pilot_generate_brim_csvs.py \
    --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json
```

### 2. Upload via API and Extract
```bash
export BRIM_API_TOKEN="your_token"
export BRIM_PROJECT_ID="16"

python scripts/brim_api_workflow.py upload \
    --project-csv pilot_output/brim_csvs/project.csv \
    --variables-csv pilot_output/brim_csvs/variables.csv \
    --decisions-csv pilot_output/brim_csvs/decisions.csv \
    --output pilot_output/BRIM_Export_v2.csv \
    --wait 60
```

### 3. Compare Results
```bash
python scripts/brim_api_workflow.py analyze \
    --results pilot_output/BRIM_Export_v2.csv \
    --baseline pilot_output/20251002-BRIM_Pilot2-BrimDataExport.csv
```

### 4. Expected Improvements

| Variable | Baseline | Expected v2 |
|----------|----------|-------------|
| **total_surgeries** | 0 ❌ | 2-3 ✅ |
| **best_resection** | DEBULKING ⚠️ | gross total resection ✅ |
| **date_of_birth** | Not documented ❌ | 2005-01-01 ✅ |
| **idh_mutation** | unknown ⚠️ | (unchanged - need text extraction) |
| **diagnosis_date** | unknown ❌ | 2021-03-10 or earlier ✅ |

## Conclusion

The longitudinal nature of oncology data requires:
1. ✅ **Granular event capture** - Each surgery/treatment as separate entry
2. ✅ **Intelligent aggregation** - Count ALL events, not just dated ones
3. ✅ **Temporal awareness** - Distinguish initial vs. recurrence
4. ✅ **Priority logic** - Best outcome across history, not just most recent
5. ⚠️ **Missing data handling** - Infer from narrative when structured data absent

**Next Steps:**
1. Add surgery_location variable
2. Update total_surgeries to count narrative-mentioned surgeries
3. Update best_resection to prioritize radiological confirmation
4. Test with updated configuration
5. Validate against ground truth (manual chart review)
