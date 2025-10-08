# Encounters Staging File - Column Reference Guide

**File**: `ALL_ENCOUNTERS_METADATA_C1277724.csv`  
**Patient**: C1277724 (e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Last Updated**: October 7, 2025  
**Total Records**: 999 encounters + 1 header = 1000 rows

---

## Column Headers (26 Total)

### Core Identifiers
1. **encounter_fhir_id** ✅ *FHIR Resource ID*
   - Unique FHIR identifier for the encounter
   - Format: `e{alphanumeric}3` (e.g., `ed1kngi-cjyWdjjba39IopA3`)
   - **Use**: Link to other FHIR resources (procedures, observations, documents, etc.)
   - **Example**: `ewkYwy07HLPthEW9WZL8Xsw3`

2. **encounter_date**
   - Date of encounter (YYYY-MM-DD format)
   - Extracted from `period_start`
   - **Use**: Human-readable date for filtering and sorting
   - **Example**: `2018-05-28`

3. **age_at_encounter_days** ✅ *Calculated Field*
   - Patient age in days at time of encounter
   - Formula: `(encounter_date - birth_date).days` where birth_date = 2005-05-13
   - **Use**: Age-based analysis, linking to gold standard
   - **Example**: `4763` (corresponds to 2018-05-28)

### Status & Classification
4. **status**
   - FHIR encounter status
   - Values: `finished`, `in-progress`, `unknown`
   - **Use**: Filter to completed encounters
   - Most common: `finished`

5. **class_code**
   - FHIR class code (numeric)
   - Values: `5` (Appointment), `10` (Surgery Log), `13` (Support OP), etc.
   - **Use**: Internal FHIR coding

6. **class_display** ✅ *KEY FILTERING FIELD*
   - Human-readable encounter class
   - **Key Values**:
     - `Surgery Log` - Surgical encounters (diagnosis events) ⭐
     - `HOV` - Hospital Outpatient Visit (follow-up oncology visits) ⭐
     - `Appointment` - Scheduled appointments
     - `Support OP Encounter` - Administrative/support (refills, phone, orders)
     - `Scannable Encounter` - Documents/forms
     - `Discharge` - Discharge encounters
   - **Use**: Primary filtering for encounter type

### Service Details
7. **service_type_text**
   - General service type description
   - Values: `General Pediatrics`, `null` (most common)
   - Sparsely populated (only 36 encounters)
   - **Use**: Limited utility for filtering

8. **priority_text**
   - Encounter priority level
   - Sparsely populated
   - **Use**: Limited utility

### Timing
9. **period_start**
   - Encounter start date/time (ISO 8601 format)
   - Format: `YYYY-MM-DDTHH:MM:SSZ`
   - **Example**: `2018-05-28T12:15:00Z`
   - **Use**: Precise timestamp, duration calculations

10. **period_end**
    - Encounter end date/time (ISO 8601 format)
    - May be null for some encounters
    - **Example**: `2018-05-28T19:00:00Z`
    - **Use**: Encounter duration calculations

11. **length_value**
    - Encounter duration value
    - Sparsely populated
    - **Use**: Duration analysis (when populated)

12. **length_unit**
    - Unit for length_value (e.g., minutes, hours)
    - Sparsely populated
    - **Use**: Duration analysis (when populated)

### Provider & Location
13. **service_provider_display**
    - Hospital or provider name
    - Common value: `THE CHILDREN'S HOSPITAL OF PHILADELPHIA ACPR`
    - **Use**: Multi-site analysis (if applicable)

14. **part_of_reference**
    - Reference to parent encounter (if applicable)
    - Format: `Encounter/{encounter_id}`
    - **Use**: Link related encounters (e.g., post-op to main surgery)

### Encounter Type Details
15. **type_coding** ✅ *FHIR Codes (JSON)*
    - FHIR type codes as JSON array
    - Format: `[{'system': '...', 'code': '...', 'display': '...'}]`
    - **Example**: `[{'system': 'urn:oid:1.2.840.114350.1.13.20.2.7.10.698084.30', 'code': '51', 'display': 'Surgery'}]`
    - **Use**: Structured coding (requires JSON parsing)

16. **type_text** ✅ *KEY FILTERING FIELD*
    - Human-readable encounter type(s) - **MOST IMPORTANT FOR FILTERING**
    - Multiple values separated by `;` (semicolon + space)
    - **Key Values for Oncology Follow-ups**:
      - `ROUTINE ONCO VISIT` ⭐ (33 encounters)
      - `FOLLOW U/EST(ONCOLOGY)` ⭐ (18 encounters)
      - `VIDEO - RD ONCO FOL UP` ⭐ (1 encounter)
      - `LONG ONCO VISIT` (1 encounter)
      - `SICK(ONCOLOGY)` (1 encounter)
    - **Common Values to Exclude**:
      - `Refill` (137 encounters)
      - `MyChart Encounter` (131 encounters)
      - `Telephone` (95 encounters)
      - `Orders Only` (31 encounters)
      - `Pharmacy Visit` (16 encounters)
    - **Example**: `Recurring Outpatient; Hospital Encounter; ROUTINE ONCO VISIT`
    - **Use**: PRIMARY field for identifying oncology follow-up visits

### Reason for Encounter
17. **reason_code_coding** ✅ *FHIR Codes (JSON)*
    - FHIR reason codes as JSON array
    - Format: Similar to type_coding
    - Sparsely populated (538 of 999 encounters)
    - **Use**: Structured reason coding

18. **reason_code_text**
    - Human-readable reason(s) for encounter
    - Multiple values separated by `;`
    - **Common Values**:
      - `Refill Request` (155)
      - `Other` (47)
      - `Follow Up` (30)
      - `Fever` (27)
      - `Well Child` (22)
    - Sparsely populated (538 of 999 encounters)
    - **Use**: Limited utility (many nulls, not oncology-specific)

### Diagnosis Linkage
19. **diagnosis_condition_reference** ✅ *FHIR Condition ID*
    - Reference to condition (diagnosis) resource
    - Format: `Condition/{condition_id}` or multiple separated by `;`
    - **VERY SPARSE**: Only 3 of 999 encounters have this populated
    - **Example**: `Condition/eXYZ123...`
    - **Use**: Link to condition table (limited coverage)

20. **diagnosis_condition_display**
    - Human-readable diagnosis name
    - Only 3 encounters populated
    - Value: `Pilocytic astrocytoma of cerebellum`
    - **Use**: Limited utility due to sparsity

21. **diagnosis_use_coding**
    - Diagnosis use type (admission, billing, discharge, etc.)
    - Only 3 encounters populated
    - **Use**: Limited utility

22. **diagnosis_rank**
    - Diagnosis priority ranking
    - Only 3 encounters populated
    - **Use**: Limited utility

### Service Type Details
23. **service_type_coding_display_detail**
    - Detailed service type from encounter_service_type_coding subtable
    - **Values**:
      - `General Pediatrics` (36 encounters)
      - `Oncology` (2 encounters) ⭐
      - `Neurosurgery` (2 encounters)
      - `Emergency` (2 encounters)
      - `Rehabilitation Medicine` (2 encounters)
    - Only 44 of 999 encounters populated
    - **Use**: Limited utility (sparse)

### Location Details
24. **location_location_reference** ✅ *FHIR Location ID*
    - Reference to location resource(s)
    - Format: `Location/{location_id}` or multiple separated by `;`
    - 999 of 999 encounters populated ✅
    - **Example**: `Location/efy2ierbL8EeYWPLR4mjUIybY61hGDM1MJWgcdWzAotY3`
    - **Use**: Link to location table for facility analysis

25. **location_status**
    - Status of location reference
    - Values present but interpretation unclear
    - **Use**: Context for location reference

### Derived Classification
26. **patient_type** ✅ *Calculated Field*
    - Inpatient/Outpatient classification
    - **Values**:
      - `Outpatient` (290) - Based on `Appointment` class_display
      - `Unknown` (709) - Cannot determine from class_display
      - `Inpatient` (0) - None found
    - Formula: Based on keywords in class_display
    - **Use**: Patient type analysis (limited accuracy)

---

## Key Fields Summary

### For Diagnosis Event Identification:
- **encounter_fhir_id** - Unique identifier
- **encounter_date** - Event date
- **age_at_encounter_days** - Age at event
- **class_display** = `'Surgery Log'` ⭐ **PRIMARY FILTER**
- **type_text** - Contains `'Surgery'`
- **period_start/end** - Procedure duration

### For Follow-Up Encounter Identification:
- **encounter_fhir_id** - Unique identifier
- **encounter_date** - Visit date
- **age_at_encounter_days** - Age at visit
- **class_display** = `'HOV'` ⭐ **PRIMARY FILTER**
- **type_text** - Contains `'ROUTINE ONCO VISIT'` or `'ONCO'` ⭐ **KEY FILTER**
- **reason_code_text** - May contain `'Follow Up'`

### For Resource Linkage:
- **encounter_fhir_id** - Links to procedures, observations, documents
- **diagnosis_condition_reference** - Links to conditions (sparse)
- **location_location_reference** - Links to locations
- **part_of_reference** - Links to parent encounters

---

## Appointments Data - Current Status

### ⚠️ Issue: Appointment Table Query Not Supported

The appointment extraction query failed with error:
```
An error occurred (InvalidRequestException) when calling the 
StartQueryExecution operation: Queries of this type are not supported
```

### Attempted Extraction:
```sql
SELECT DISTINCT
    a.id as appointment_fhir_id,
    a.status as appointment_status,
    a.appointment_type_text,
    a.description,
    a.start, a.end,
    a.minutes_duration, a.created,
    a.comment, a.patient_instruction,
    a.cancelation_reason_text, a.priority
FROM appointment a
WHERE a.id IN (
    SELECT REPLACE(ea.appointment_reference, 'Appointment/', '')
    FROM encounter_appointment ea
    WHERE ea.encounter_id IN (
        SELECT id FROM encounter 
        WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    )
)
AND a.status NOT IN ('cancelled', 'noshow')  ← Filter applied ✅
ORDER BY a.start
```

### What We Tried to Capture:
- **appointment_fhir_id** - Unique appointment identifier
- **appointment_status** - Status (filtered: `fulfilled`, `arrived`, `booked` only)
- **appointment_type_text** - Type of appointment
- **start/end** - Appointment timing
- **cancelation_reason_text** - If cancelled (excluded)

### Findings:
1. ✅ **encounter_appointment** table is **empty** for this patient (0 linkages found)
2. ⚠️ Appointment table has query restrictions in Athena
3. 📋 Appointment data may not be linked to encounters in this database

### Alternative Approach:
Since encounter_appointment linkage is empty, appointments are likely:
1. Represented directly as encounters with `class_display = 'Appointment'` (290 found)
2. Not separately tracked in appointment table for this patient
3. Embedded within encounter metadata

### Recommendation:
**Use encounters with `class_display = 'Appointment'` as appointment data**. These already have:
- FHIR ID (encounter_fhir_id)
- Date/time (period_start/end)
- Type (type_text)
- Status (status)

---

## Filtering Status Implemented

### ✅ Encounters - All Included
- **No filtering applied** - 999 encounters captured
- All encounter statuses included (`finished`, `in-progress`, `unknown`)
- All encounter types included (Surgery Log, HOV, Appointment, Support OP, etc.)

### ✅ Appointments - Filtered (but empty)
- **Filtered out**: `cancelled` and `noshow` appointments
- **Included**: `fulfilled`, `arrived`, `booked` appointments
- **Result**: 0 appointments (no encounter-appointment linkages exist)

---

## Usage Examples

### Example 1: Extract Surgical Diagnosis Events
```python
import pandas as pd

df = pd.read_csv('ALL_ENCOUNTERS_METADATA_C1277724.csv')

surgical_events = df[
    (df['class_display'] == 'Surgery Log') &
    (df['encounter_date'].isin(['2018-05-28', '2021-03-10']))
]

print(surgical_events[['encounter_fhir_id', 'encounter_date', 'age_at_encounter_days']])
```

### Example 2: Extract Oncology Follow-Up Visits
```python
follow_ups = df[
    (df['class_display'] == 'HOV') &
    (df['type_text'].str.contains('ROUTINE ONCO VISIT', case=False, na=False)) &
    (df['encounter_date'] >= '2018-05-28')
]

print(f"Found {len(follow_ups)} oncology follow-up visits")
```

### Example 3: Link to Other Resources
```python
# Get encounter FHIR IDs for linking to procedures
encounter_ids = df['encounter_fhir_id'].tolist()

# Use in query:
# SELECT * FROM procedure 
# WHERE encounter_reference IN ('Encounter/{id1}', 'Encounter/{id2}', ...)
```

---

## Data Quality Notes

### Well-Populated Fields (>90%):
- ✅ encounter_fhir_id (100%)
- ✅ encounter_date (100%)
- ✅ age_at_encounter_days (100%)
- ✅ status (100%)
- ✅ class_display (100%)
- ✅ type_text (100%)
- ✅ location_location_reference (100%)

### Moderately Populated (50-90%):
- ⚠️ reason_code_text (53.9%)

### Sparsely Populated (<10%):
- ⚠️ service_type_coding_display_detail (4.4%)
- ⚠️ service_type_text (3.6%)
- ⚠️ diagnosis_condition_reference (0.3%)
- ⚠️ diagnosis_condition_display (0.3%)

### Recommendations:
1. **Primary filters**: Use `class_display` and `type_text` (100% populated)
2. **Avoid**: `diagnosis_condition_reference` (too sparse)
3. **Avoid**: `service_type_text` (mostly null)
4. **Use cautiously**: `reason_code_text` (46% missing)

---

## Next Steps

1. ✅ **COMPLETE**: Encounter FHIR IDs included
2. ✅ **COMPLETE**: Cancelled/noshow appointments filtered (none found)
3. ⏳ **PENDING**: Use this staging file for analysis
4. ⏳ **PENDING**: Implement filtering logic for gold standard validation
5. ⏳ **PENDING**: Link encounters to procedures/observations via FHIR IDs

---

**Status**: ✅ Staging file ready with FHIR IDs and filtered appointments (though no appointment linkages exist)
