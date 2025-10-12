# Radiation Extraction Script Update - Care Plan Tables Added

**Date:** 2025-10-12  
**Script:** `scripts/extract_radiation_data.py`  
**Database:** fhir_prd_db (UPGRADED from fhir_v2_prd_db)

## Update Summary

### What Changed

Added extraction of **2 new data sources** that were previously missed:

1. **`care_plan_note`** - Patient instructions and clinical notes
2. **`care_plan_part_of`** - Treatment plan hierarchy relationships

### Key Technical Fix

**Critical Discovery:** The `care_plan` table stores patient IDs **WITHOUT** the "Patient/" prefix, unlike other FHIR tables.

```python
# Other FHIR tables use:
WHERE subject_patient_id = 'Patient/eoA0IUD9y...'

# care_plan table uses:
WHERE subject_reference = 'eoA0IUD9y...'  # NO Patient/ prefix!
```

This required passing the bare `patient_id` instead of `patient_fhir_id` to the care_plan extraction functions.

## New Functions Added

### 1. `extract_care_plan_notes(athena_client, patient_id)`

**Purpose:** Extract radiation-related notes from care_plan_note table

**What It Does:**
- Queries care_plan_note with JOIN to parent care_plan
- Filters for radiation keywords
- Detects dose information (Gy mentions)
- Categorizes notes: Patient Instructions, Dosage Info, Side Effects

**Output:** DataFrame with columns:
- `care_plan_id`
- `note_text` (full clinical notes)
- `care_plan_status`, `care_plan_intent`, `care_plan_title`
- `period_start`, `period_end`
- `contains_dose` (boolean - has "Gy" mention)
- `note_type` (categorization)

### 2. `extract_care_plan_hierarchy(athena_client, patient_id)`

**Purpose:** Extract treatment plan hierarchy relationships

**What It Does:**
- Queries care_plan_part_of to find plan linkages
- Identifies parent-child plan relationships
- Filters for radiation-related references
- Analyzes hierarchy structure (parents, children, ratios)

**Output:** DataFrame with columns:
- `care_plan_id`
- `part_of_reference` (parent plan FHIR ID)
- `care_plan_status`, `care_plan_intent`, `care_plan_title`
- `period_start`, `period_end`

## Testing Results

### Test Patient 1: eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3

**Previous Results:**
- 2 rad onc consults
- 12 RT appointments
- 3 treatment courses
- Re-irradiation: Yes

**NEW Care Plan Data:**
- ✅ **2 radiation-related notes** (from 42 total care plan notes)
- ✅ **78 radiation-related hierarchy links** (from 999 total relationships)
  - 51 unique parent plans
  - 78 unique child plans
  - Average 1.5 children per parent
- ❌ 0 notes with dose in Gy (but notes contain RT prep instructions)

**New Output Files:**
- `radiation_care_plan_notes.csv` (2 rows)
- `radiation_care_plan_hierarchy.csv` (78 rows)

**Sample Note Content:**
```
"INSTRUCTIONS FOR PRE-ANESTHESIA MANAGEMENT
...Roberts Proton Therapy Center on the CN Level...
...nebulizer treatments at least 2 times per day..."
```

### Test Patient 2: emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3

**Previous Results:**
- 11 rad onc consults
- 12 RT appointments (all IMRT sessions)
- 0 treatment courses (daily session pattern)

**NEW Care Plan Data:**
- ❌ 0 radiation-related notes (from 8 total care plan notes)
- ❌ 0 radiation-related hierarchy (from 263 total relationships)

**Interpretation:** This patient's RT documentation is entirely in appointments, not care plans.

## Summary Statistics Updated

The summary CSV now includes 3 new fields:

```python
summary['num_care_plan_notes'] = len(care_plan_notes_df)
summary['num_care_plan_hierarchy'] = len(care_plan_hierarchy_df)
summary['care_plan_notes_with_dose'] = care_plan_notes_df['contains_dose'].sum()
```

**Console Output:**
```
--- NEW: Care Plan Data ---
Care Plan Notes (RT-related): 2
Notes with Dose Info (Gy):    0
Care Plan Hierarchy Links:    78
```

## Data Quality Findings

### care_plan_note
- **Hit Rate:** 2/42 notes (4.8%) for test patient
- **Content Type:** Pre-anesthesia instructions, proton therapy prep
- **Dose Information:** Mentions "Roberts Proton Therapy Center" but no Gy values
- **Value:** Patient preparation details not in appointments

### care_plan_part_of
- **Hit Rate:** 78/999 relationships (7.8%) for test patient
- **Structure:** Complex parent-child hierarchies
- **Use Case:** Could reconstruct complete treatment protocols
- **Value:** Shows treatment plan organization structure

## Coverage Analysis

### Patient Coverage Variability

| Patient | RT Status | Care Plan Notes | Care Plan Hierarchy |
|---------|-----------|-----------------|---------------------|
| Patient 1 | Has RT (3 courses) | ✅ 2 notes | ✅ 78 links |
| Patient 2 | Has RT (12 sessions) | ❌ 0 notes | ❌ 0 links |

**Conclusion:** Care plan data availability varies by patient and institution. Some patients have rich care plan documentation, others have only appointment data.

## Script Changes Summary

### Database Update
```python
# OLD
DATABASE = 'fhir_v2_prd_db'

# NEW
DATABASE = 'fhir_prd_db'  # UPDATED: Using new production database
```

### New Function Signatures
```python
def extract_care_plan_notes(athena_client, patient_id):
    # NOTE: Uses bare patient_id (no 'Patient/' prefix)
    
def extract_care_plan_hierarchy(athena_client, patient_id):
    # NOTE: Uses bare patient_id (no 'Patient/' prefix)
```

### Main Workflow Update
```python
# Extract data
consults_df = extract_radiation_oncology_consults(athena, patient_fhir_id)
treatments_df = extract_radiation_treatment_appointments(athena, patient_fhir_id)
# NEW: care_plan tables use bare patient_id
care_plan_notes_df = extract_care_plan_notes(athena, patient_id)
care_plan_hierarchy_df = extract_care_plan_hierarchy(athena, patient_id)
```

### Output Files Added
- `radiation_care_plan_notes.csv` (if any found)
- `radiation_care_plan_hierarchy.csv` (if any found)

## Updated Documentation

### Script Header
```python
"""
Extract Radiation Oncology Data from Athena FHIR Database

Data Sources:
- appointment + appointment_service_type (consults & treatments)
- care_plan_note (patient instructions, dose info in Gy)  # NEW
- care_plan_part_of (treatment plan hierarchy)            # NEW
```

## Recommendations

### For Users
1. ✅ **Script is production-ready** - all changes tested
2. ✅ **Backward compatible** - still extracts all previous data
3. ⚠️ **Variable coverage** - care plan data not available for all patients
4. ℹ️ **Complementary data** - provides context missing from appointments

### For Future Enhancement
1. Parse note_text for structured data (dose, side effects, protocols)
2. Use hierarchy to group related treatment sessions
3. Cross-validate dates between notes and appointments
4. Extract proton vs photon therapy details from notes

## Validation Status

- ✅ Script runs without errors
- ✅ Correctly handles patients with and without care plan data
- ✅ No patient ID leakage in logs
- ✅ All new CSV files created successfully
- ✅ Summary statistics accurate
- ✅ Backward compatible with existing workflow

## Files Modified

1. **`scripts/extract_radiation_data.py`**
   - Added 2 new extraction functions (~160 lines)
   - Updated main workflow
   - Updated summary reporting
   - Updated output file saving
   - Changed database to fhir_prd_db
   - Total: ~740 lines (from ~555 lines)

## Related Documentation

- `/docs/CAREPLAN_MISSING_TABLES_FINDINGS.md` - Full investigation results
- `/logs/careplan_missing_tables_check.log` - Table check results
- `/logs/careplan_radiation_content_analysis.log` - Content analysis
- `/docs/COMPREHENSIVE_RADIATION_SOURCE_SEARCH.md` - Original search (needs update)

---

**Status:** ✅ COMPLETE - Script updated and tested  
**Next Action:** Deploy for BRIM trial patient extraction  
**Priority:** Ready for production use
