# Python Extraction vs Athena Views: Appointments & Encounters Gap Analysis

**Date**: 2025-10-18
**Analyst**: Claude (BRIM Analytics Team)

---

## Executive Summary

**Finding**: The Python extraction code (`extract_all_encounters_metadata.py`) **DOES extract both encounters AND appointments** into separate CSV files. However, the Athena views only have `v_encounters` (no general `v_appointments` view exists).

**Gap**: Python extraction is more comprehensive than Athena views.

---

## Python Extraction Code Analysis

### File: `extract_all_encounters_metadata.py`

**Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/scripts/config_driven_versions/extract_all_encounters_metadata.py`

**Title Comment** (lines 2-4):
```python
"""
Extract ALL encounters and appointments metadata from patient configuration
Purpose: Comprehensive data dump for analysis before implementing filtering logic
"""
```

### Key Functions:

#### 1. Encounter Extraction Functions

1. **`extract_main_encounters()`** (lines 101-154)
   - Source: `encounter` table
   - Output: Main encounter data with age calculation
   - Fields: 14 core encounter fields

2. **`extract_encounter_types()`** (lines 156-186)
   - Source: `encounter_type` subtable
   - Aggregates type codes/text per encounter

3. **`extract_encounter_reasons()`** (lines 188-218)
   - Source: `encounter_reason_code` subtable
   - Aggregates reason codes per encounter

4. **`extract_encounter_diagnoses()`** (lines 220-252)
   - Source: `encounter_diagnosis` subtable
   - Links encounters to conditions/diagnoses

5. **`extract_encounter_appointments()`** (lines 254-280)
   - Source: `encounter_appointment` subtable
   - Links encounters to appointments (the bridge table!)
   - Fields: `encounter_id`, `appointment_reference`

6. **`extract_encounter_service_types()`** (lines 369-400)
   - Source: `encounter_service_type_coding` subtable
   - Detailed service type coding

7. **`extract_encounter_locations()`** (lines 402-429)
   - Source: `encounter_location` subtable
   - Location references for encounters

---

#### 2. Appointment Extraction Function

**`extract_appointments()`** (lines 282-367)

**Key Implementation Details**:

```python
def extract_appointments(self) -> pd.DataFrame:
    """Extract all appointments via appointment_participant pathway

    NOTE: This uses the appointment_participant table, NOT encounter_appointment.
    The encounter_appointment table links appointments to encounters, but appointment_participant
    links appointments to patients directly. This is the correct pathway for patient data extraction.
    """
```

**SQL Query** (lines 297-305):
```python
query = f"""
SELECT DISTINCT a.*, ap.participant_actor_reference, ap.participant_actor_type,
       ap.participant_required, ap.participant_status,
       ap.participant_period_start, ap.participant_period_end
FROM {self.database}.appointment a
JOIN {self.database}.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference = 'Patient/{self.patient_fhir_id}'
ORDER BY a.start
"""
```

**Important Notes from Code** (lines 285-287):
- Uses `appointment_participant` table (NOT `encounter_appointment`)
- `encounter_appointment` links appointments to encounters (many-to-one)
- `appointment_participant` links appointments to patients (correct for patient extraction)

**Column Prefixing** (lines 315-335):
- All appointment table fields get `appt_` prefix (e.g., `appt_status`, `appt_start`)
- All participant fields get `ap_` prefix (e.g., `ap_participant_actor_reference`)
- Enables clear field provenance tracking

**Appointment Fields Extracted**:
- `appt_id` - Appointment FHIR ID
- `appt_status` - Status (booked, fulfilled, cancelled, noshow, etc.)
- `appt_appointment_type_text` - Appointment type
- `appt_description` - Description
- `appt_start` - Start datetime
- `appt_end` - End datetime
- `appt_minutes_duration` - Duration
- `appt_created` - Creation timestamp
- `appt_comment` - Comments
- `appt_patient_instruction` - Patient instructions
- `appt_cancelation_reason_text` - Cancellation reason
- `appt_priority` - Priority level

**Participant Fields Extracted**:
- `ap_participant_actor_reference` - Patient reference (Patient/{fhir_id})
- `ap_participant_actor_type` - Actor type
- `ap_participant_required` - Required flag
- `ap_participant_status` - Participant status
- `ap_participant_period_start` - Period start
- `ap_participant_period_end` - Period end

**Calculated Fields**:
- `appointment_fhir_id` - Convenience copy of appt_id
- `appointment_date` - Date extracted from appt_start
- `age_at_appointment_days` - Age calculation

---

### Output Files

**`merge_and_export()`** (lines 431-536)

**Encounters Output** (`encounters.csv`):
- Main encounters table merged with all subtables
- Includes appointment linkages from `encounter_appointment`
- Fields: ~20+ columns with aggregated subtable data
- Patient type classification (Inpatient/Outpatient)

**Appointments Output** (`appointments.csv`) - Line 509-512:
```python
# Export appointments separately
if not appointments_df.empty:
    appointments_file = self.output_dir / 'appointments.csv'
    appointments_df.to_csv(appointments_file, index=False)
    print(f"✓ Saved: {appointments_file}")
```

**Summary Output** (lines 518-534):
```python
print("📊 FINAL SUMMARY:")
print(f"  Total encounters: {len(merged)}")
print(f"  Total appointments: {len(appointments_df) if not appointments_df.empty else 0}")
```

---

## Athena Views Current State

### v_encounters (ATHENA_VIEW_CREATION_QUERIES.sql lines 1111-1163)

**Data Sources**:
- ✅ `encounter` table
- ✅ `encounter_type` subtable (aggregated)
- ✅ `encounter_reason_code` subtable (aggregated)
- ✅ `encounter_diagnosis` subtable (aggregated)
- ✅ `patient_access` table (for age calculation)

**Missing**:
- ❌ `encounter_appointment` linkage (NOT included)
- ❌ `encounter_service_type_coding` subtable
- ❌ `encounter_location` subtable

### v_appointments

**Status**: ❌ **DOES NOT EXIST** (no general appointments view)

**Partial Coverage**:
- `v_radiation_treatment_appointments` exists (lines 1407-1424) but only for radiation context
- Despite name, actually captures ALL appointments (no radiation filtering in WHERE clause)
- Used in `v_cranial_radiation_consolidated` as aggregated summary only

---

## Gap Analysis: Python vs Athena

### What Python Has That Athena Views Don't:

1. **Separate appointments.csv output**
   - Python: ✅ Full appointments table as separate CSV
   - Athena: ❌ No general `v_appointments` view

2. **Encounter-appointment linkages in encounters output**
   - Python: ✅ Includes `appointment_reference` from `encounter_appointment` table
   - Athena: ❌ No appointment linkage in `v_encounters`

3. **Encounter service type coding details**
   - Python: ✅ Extracts from `encounter_service_type_coding`
   - Athena: ❌ Not included (only `service_type_text` from main table)

4. **Encounter locations**
   - Python: ✅ Extracts from `encounter_location`
   - Athena: ❌ Not included

5. **Clear field provenance via prefixes**
   - Python: ✅ `appt_*` and `ap_*` prefixes
   - Athena: N/A (no appointments view)

---

## Documentation Analysis

### TABLE_COLUMN_MAPPING_AND_ATHENA_VIEWS.md

**Section 6: Appointments Extraction** (line 836)
- Output: `appointments.csv`
- Source tables: `appointment` + `appointment_participant`
- Documents the appointments view definition

**Section 7: Encounters Extraction** (line 912)
- Output: `encounters.csv`
- Source tables: `encounter` + 4 subtables (including `encounter_appointment`)
- Documents the encounters view definition

**Key Quote** (line 922):
```
5. **encounter_appointment** - Encounter-appointment linkages
```

This confirms that `encounter_appointment` table was **intended** to be used but is **NOT currently in the Athena view**.

---

## Consistency Issues

### Issue 1: Python Code Title vs Implementation

**Python File Docstring** (lines 2-4):
```python
"""
Extract ALL encounters and appointments metadata from patient configuration
Purpose: Comprehensive data dump for analysis before implementing filtering logic
"""
```

✅ **Accurate**: Code does extract both encounters AND appointments

### Issue 2: Athena View Naming

**View Name**: `v_encounters`
**Coverage**: Encounters only (no appointments)

✅ **Accurate naming**: View name correctly reflects its scope

### Issue 3: Missing Athena View

**Python Output**: `appointments.csv` (separate file)
**Athena Equivalent**: ❌ Missing `v_appointments` view

⚠️ **Gap**: Athena views incomplete compared to Python extraction

---

## Why This Matters

### Use Cases Enabled by Python (But NOT by Athena Views):

1. **Appointment Analytics**
   - No-show rate analysis
   - Cancellation pattern analysis
   - Appointment adherence metrics
   - Future appointment scheduling analysis

2. **Encounter-Appointment Correlation**
   - Which encounters were scheduled vs walk-in?
   - Did the appointment happen (fulfilled → encounter)?
   - No-show impact on clinical outcomes

3. **Operational Metrics**
   - Appointment capacity planning
   - Patient access metrics
   - Scheduling efficiency

4. **Patient Journey Analysis**
   - Complete visit timeline (appointments + encounters)
   - Care coordination tracking

---

## Recommendations

### Immediate: Align Athena Views with Python Extraction

1. **Create `v_appointments` view** matching Python `appointments.csv` output
   - Use same source tables (`appointment` + `appointment_participant`)
   - Include same field set
   - Use same column naming conventions (appt_, ap_ prefixes)

2. **Enhance `v_encounters` view** to match Python `encounters.csv` output
   - Add `encounter_appointment` linkage
   - Add `encounter_service_type_coding` details
   - Add `encounter_location` details

3. **Document the relationship** between appointments and encounters
   - Update view documentation
   - Explain when to use each view
   - Show example join queries

### Future: Maintain Parity

4. **Establish sync process**
   - When Python extraction changes, update Athena views
   - When Athena views change, update Python extraction
   - Maintain consistent field naming

5. **Create integration tests**
   - Compare Python CSV output to Athena view results
   - Validate row counts match
   - Validate field values match

---

## Implementation Priority

### High Priority
1. ✅ Create `v_appointments` view (matches Python appointments.csv)
2. ✅ Add `encounter_appointment` to `v_encounters` (matches Python encounters.csv)

### Medium Priority
3. Add `encounter_service_type_coding` to `v_encounters`
4. Add `encounter_location` to `v_encounters`

### Low Priority
5. Create combined `v_visit_timeline` view (appointments + encounters merged)

---

## Conclusion

**Answer to User's Question**:

**No**, the Python code did **NOT** focus only on encounters. The `extract_all_encounters_metadata.py` script extracts **BOTH** encounters and appointments into separate CSV files:

1. **encounters.csv** - All encounters with subtable aggregations
2. **appointments.csv** - All appointments with participant details

The Python extraction is **more comprehensive** than the current Athena views, which only have `v_encounters` (no general `v_appointments` view exists).

**Key Evidence**:
- Line 34: Print statement says "ENCOUNTERS & APPOINTMENTS METADATA EXTRACTOR"
- Line 282-367: `extract_appointments()` function extracts full appointment data
- Line 509-512: Appointments exported to separate CSV file
- Line 560: `appointments_df = extractor.extract_appointments()` in main execution
- Documentation (line 836): Section titled "6. Appointments Extraction"

**Recommendation**: Create `v_appointments` view in Athena to achieve parity with Python extraction capabilities.
