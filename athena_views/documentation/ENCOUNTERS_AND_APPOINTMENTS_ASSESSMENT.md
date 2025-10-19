# Encounters and Appointments Assessment

**Date**: 2025-10-18
**Analyst**: Claude (BRIM Analytics Team)

---

## Executive Summary

Current `v_encounters` view captures **encounter data only** from the FHIR `encounter` table. **Appointments are NOT included** in this view. However, FHIR maintains a separate `appointment` table with distinct data that represents scheduled visits (both completed and planned), while encounters represent actual clinical interactions that occurred.

### Key Findings:

1. ✅ **Encounters are captured** in `v_encounters` (lines 1111-1163 in master file)
2. ❌ **Appointments are NOT captured** in `v_encounters`
3. ✅ **Appointments exist** in a radiation-specific view (`v_radiation_treatment_appointments`)
4. ✅ **Appointments table exists** in FHIR schema with full data
5. ⚠️ **No general appointments view** exists for all appointment types

---

## Current State Analysis

### 1. v_encounters View (Lines 1111-1163)

**Data Source**: `encounter` table + 3 sub-schema tables

**Captured Data**:
- Encounter metadata (ID, date, status, class, service type)
- Encounter types (aggregated from `encounter_type` table)
- Encounter reasons (aggregated from `encounter_reason_code` table)
- Encounter diagnoses (aggregated from `encounter_diagnosis` table)
- Age at encounter calculation
- Patient linkage via `subject_reference`

**NOT Captured**:
- Appointments data
- Appointment-encounter linkages (from `encounter_appointment` table)

**Schema Structure**:
```sql
FROM fhir_prd_db.encounter e
LEFT JOIN encounter_types_agg et ON e.id = et.encounter_id
LEFT JOIN encounter_reasons_agg er ON e.id = er.encounter_id
LEFT JOIN encounter_diagnoses_agg ed ON e.id = ed.encounter_id
LEFT JOIN fhir_prd_db.patient_access pa ON e.subject_reference = pa.id
```

---

### 2. Appointment Data in FHIR

**Tables Available**:
- `fhir_prd_db.appointment` - Main appointment table
- `fhir_prd_db.appointment_participant` - Participant linkages (patients, practitioners)

**Appointment Fields** (from schema analysis):
- `id` - Appointment FHIR ID
- `status` - Status (booked, fulfilled, cancelled, noshow, pending, etc.)
- `appointment_type_text` - Type of appointment
- `description` - Appointment description
- `start` - Scheduled start datetime
- `end` - Scheduled end datetime
- `minutes_duration` - Duration in minutes
- `created` - When appointment was created
- `comment` - Appointment comments
- `patient_instruction` - Instructions for patient
- `cancelation_reason_text` - Cancellation reason
- `priority` - Priority level

**Participant Fields** (from `appointment_participant`):
- `appointment_id` - Links to appointment.id
- `participant_actor_reference` - Reference to Patient/Practitioner/Location
- `participant_actor_type` - Type of participant
- `participant_required` - Whether required
- `participant_status` - Participant-specific status
- `participant_period_start` - Participant period start
- `participant_period_end` - Participant period end

---

### 3. Existing Appointment Views

#### v_radiation_treatment_appointments (Lines 1407-1424)

**Purpose**: Radiation oncology appointments only

**Data Captured**:
```sql
SELECT DISTINCT
    ap.participant_actor_reference as patient_fhir_id,
    a.id as appointment_id,
    a.status as appointment_status,
    a.appointment_type_text,
    a.priority,
    a.description,
    a.start as appointment_start,
    a."end" as appointment_end,
    a.minutes_duration,
    a.created,
    a.comment as appointment_comment,
    a.patient_instruction
FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference LIKE 'Patient/%'
```

**Limitation**: No filtering for radiation - captures ALL appointments despite view name

#### Consolidated Radiation View Appointment Integration

The `v_cranial_radiation_consolidated` view (lines 1590-1965) includes appointment summary data:

**Appointment CTE** (lines 1800-1820):
```sql
appointment_summary AS (
    SELECT
        ap.participant_actor_reference as patient_fhir_id,
        COUNT(DISTINCT a.id) as total_appointments,
        COUNT(DISTINCT CASE WHEN a.status = 'fulfilled' THEN a.id END) as fulfilled_appointments,
        COUNT(DISTINCT CASE WHEN a.status = 'cancelled' THEN a.id END) as cancelled_appointments,
        COUNT(DISTINCT CASE WHEN a.status = 'noshow' THEN a.id END) as noshow_appointments,
        MIN(a.start) as first_appointment_date,
        MAX(a.start) as last_appointment_date,
        MIN(CASE WHEN a.status = 'fulfilled' THEN a.start END) as first_fulfilled_appointment,
        MAX(CASE WHEN a.status = 'fulfilled' THEN a.start END) as last_fulfilled_appointment
    FROM fhir_prd_db.appointment a
    JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
    WHERE ap.participant_actor_reference LIKE 'Patient/%'
      AND ap.participant_actor_reference IN (
          SELECT DISTINCT subject_reference FROM fhir_prd_db.service_request
          WHERE LOWER(code_text) LIKE '%radiation%'
          UNION
          SELECT DISTINCT subject_reference FROM fhir_prd_db.observation
          WHERE LOWER(code_text) LIKE '%radiation%'
      )
    GROUP BY ap.participant_actor_reference
)
```

**Usage**: Aggregated appointment statistics for radiation patients only

---

### 4. Encounter-Appointment Linkage

**FHIR Table**: `encounter_appointment`

**Purpose**: Links encounters to the appointments that scheduled them

**Schema** (from documentation):
- `encounter_id` - Foreign key to encounter.id
- `appointment_reference` - Reference to Appointment (e.g., "Appointment/xyz")

**Current Status**: ❌ NOT used in `v_encounters` view

**Significance**: This linkage shows which appointment led to which encounter (actual clinical interaction)

---

## FHIR Semantic Difference: Encounter vs Appointment

### Appointment
- **Scheduled** clinical interaction (may or may not occur)
- Status values: `booked`, `pending`, `fulfilled`, `cancelled`, `noshow`, `entered-in-error`
- Represents **intent** to meet
- Created before the clinical interaction
- May have multiple participants (patient, practitioner, location)

### Encounter
- **Actual** clinical interaction that occurred
- Status values: `planned`, `in-progress`, `finished`, `cancelled`, `entered-in-error`
- Represents **actual** clinical event
- Created during or after the interaction
- Linked to diagnoses, procedures, medications ordered during visit

### Relationship
- One appointment may lead to one encounter (`fulfilled` → `finished`)
- Appointment `cancelled` or `noshow` → No encounter created
- Encounter may exist without appointment (walk-ins, emergency visits)
- `encounter_appointment` table links the two

---

## Gap Analysis

### What's Missing from v_encounters

1. **No Appointment Data**
   - Scheduled appointment date/time
   - Appointment status (fulfilled, cancelled, noshow)
   - Appointment type
   - Appointment creation date
   - Cancellation reasons
   - Patient instructions

2. **No Encounter-Appointment Linkage**
   - Which appointment led to this encounter
   - Whether encounter was scheduled or unscheduled
   - No-show analysis capability
   - Cancellation pattern analysis

3. **No Appointment-Only Records**
   - Scheduled future appointments (not yet encounters)
   - Cancelled appointments (never became encounters)
   - No-show appointments (scheduled but patient didn't arrive)

---

## Recommended Enhancements

### Option 1: Enhance v_encounters with Appointment Linkage

**Approach**: Add appointment data to existing `v_encounters` view via `encounter_appointment` table

**Pros**:
- Single view for complete visit context
- Shows which encounters were scheduled vs unscheduled
- Enables no-show/cancellation analysis per encounter
- Minimal changes to existing workflow

**Cons**:
- Doesn't capture appointment-only records (future, cancelled, noshow)
- Adds complexity to encounters view
- NULL appointment fields for unscheduled encounters

**Implementation**:
```sql
WITH encounter_appointment_agg AS (
    SELECT
        encounter_id,
        LISTAGG(DISTINCT appointment_reference, ' | ') WITHIN GROUP (ORDER BY appointment_reference) as appointment_references
    FROM fhir_prd_db.encounter_appointment
    GROUP BY encounter_id
)

-- Then join appointment details via appointment_references
LEFT JOIN fhir_prd_db.appointment a
    ON ea.appointment_references LIKE '%' || a.id || '%'
```

---

### Option 2: Create Separate v_appointments View

**Approach**: Create comprehensive appointments view alongside encounters view

**Pros**:
- Captures ALL appointment data (future, cancelled, noshow, fulfilled)
- Separates scheduled vs actual interactions (FHIR-compliant)
- Enables appointment management analytics
- Enables healthcare utilization analysis (appointment adherence, no-show rates)
- Clean separation of concerns

**Cons**:
- Users must query two views for complete picture
- Need to document encounter vs appointment semantics

**Implementation**:
```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_appointments AS
WITH appointment_participants_agg AS (
    SELECT
        appointment_id,
        MAX(CASE WHEN participant_actor_reference LIKE 'Patient/%'
            THEN participant_actor_reference END) as patient_fhir_id,
        MAX(CASE WHEN participant_actor_type = 'Practitioner'
            THEN participant_actor_reference END) as practitioner_fhir_id,
        MAX(CASE WHEN participant_actor_type = 'Location'
            THEN participant_actor_reference END) as location_fhir_id
    FROM fhir_prd_db.appointment_participant
    GROUP BY appointment_id
),
linked_encounters AS (
    SELECT
        ea.appointment_reference,
        SUBSTRING(ea.appointment_reference, 13) as appointment_id,  -- Remove "Appointment/"
        COUNT(DISTINCT ea.encounter_id) as encounter_count,
        MAX(ea.encounter_id) as primary_encounter_id
    FROM fhir_prd_db.encounter_appointment ea
    GROUP BY ea.appointment_reference
)
SELECT DISTINCT
    a.id as appointment_fhir_id,
    ap.patient_fhir_id,

    -- Appointment details
    a.status as appointment_status,
    a.appointment_type_text,
    a.description,
    a.start as appointment_start,
    a.end as appointment_end,
    a.minutes_duration,
    a.created as appointment_created,
    a.comment,
    a.patient_instruction,
    a.cancelation_reason_text,
    a.priority,

    -- Participant details
    ap.practitioner_fhir_id,
    ap.location_fhir_id,

    -- Linked encounter info
    le.encounter_count,
    le.primary_encounter_id,
    CASE
        WHEN le.encounter_count > 0 THEN true
        ELSE false
    END as has_linked_encounter,

    -- Age at appointment
    TRY(DATE_DIFF('day',
        DATE(pa.birth_date),
        TRY(CAST(SUBSTR(a.start, 1, 10) AS DATE)))) as age_at_appointment_days

FROM fhir_prd_db.appointment a
LEFT JOIN appointment_participants_agg ap ON a.id = ap.appointment_id
LEFT JOIN linked_encounters le ON a.id = le.appointment_id
LEFT JOIN fhir_prd_db.patient_access pa ON ap.patient_fhir_id = pa.id
WHERE ap.patient_fhir_id IS NOT NULL
ORDER BY a.start DESC;
```

---

### Option 3: Hybrid Approach (RECOMMENDED)

**Approach**:
1. Create separate `v_appointments` view for all appointments
2. Add appointment linkage to `v_encounters` for encounters with appointments
3. Users can query either independently or join them

**Pros**:
- Complete appointment data available
- Encounter-appointment linkage preserved
- Flexible querying (can analyze separately or together)
- Supports both clinical (encounters) and operational (appointments) analytics
- FHIR-compliant separation

**Cons**:
- Two views to maintain
- Requires user education on when to use which

**Use Cases Enabled**:

**Appointments View**:
- Scheduled future visits
- No-show analysis
- Cancellation patterns
- Appointment adherence rates
- Capacity planning
- Patient access metrics

**Encounters View (with appointment linkage)**:
- Actual clinical interactions
- Walk-in vs scheduled visits
- Diagnoses and treatments delivered
- Clinical outcomes

**Combined Analysis**:
- Compare scheduled vs actual visit patterns
- No-show impact on clinical outcomes
- Appointment-to-encounter conversion rates

---

## Data Volume Estimates

Based on consolidated radiation view statistics (lines 1798-1799):
- **Appointments**: 331,796 total across 1,855 patients
- **Average**: ~179 appointments per patient

This suggests significant appointment data exists across the entire FHIR database.

---

## Recommendations

### Immediate Action (RECOMMENDED):

1. **Create `v_appointments` view** (Option 2) to capture all appointment data
   - Essential for operational analytics
   - Captures future, cancelled, and no-show appointments
   - Minimal disruption to existing views

2. **Enhance `v_encounters` with appointment linkage** (if needed)
   - Add `encounter_appointment` join
   - Include appointment ID and status for encounters that were scheduled
   - Enables "scheduled vs unscheduled" encounter classification

3. **Document the semantic difference** between encounters and appointments
   - Update view documentation
   - Add usage examples for each view

### Future Enhancements:

4. **Create combined visit timeline view** showing both appointments and encounters
   - Useful for patient care coordination
   - Enables end-to-end visit analytics

---

## SQL Implementation Priority

### High Priority: v_appointments View
```sql
-- Section 9: General Appointments View
-- Captures ALL appointments (not just radiation)
-- Links to encounters where applicable
```

### Medium Priority: Encounter Enhancement
```sql
-- Add to existing v_encounters:
-- - encounter_appointment linkage
-- - appointment_status for linked appointments
-- - scheduled vs unscheduled classification
```

### Low Priority: Combined Analytics View
```sql
-- Future: v_visit_timeline
-- Combines appointments + encounters for complete visit history
```

---

## Conclusion

**Current State**: `v_encounters` captures encounters only. Appointments are **NOT included**.

**Gap**: No general-purpose appointments view exists. Appointment data is only used in radiation-specific views.

**Impact**: Missing operational analytics capabilities (no-show rates, cancellations, future appointments, appointment adherence).

**Recommended Fix**: Create `v_appointments` view to capture all appointment data alongside the existing `v_encounters` view. This provides complete visibility into both scheduled (appointments) and actual (encounters) clinical interactions.
