# Encounters Schema Discovery Report

**Date**: 2025-06-13  
**Patient**: C1277724 (e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Purpose**: Comprehensive database schema review for encounters extraction

---

## Executive Summary

Discovered 33 encounter/appointment-related tables in FHIR v2 database. Key finding: **encounter.class_display = 'Surgery Log'** identifies surgical encounters, solving the missing surgical dates problem. Found third diagnosis event (2021-03-10 surgery) in encounter table that was missing from procedure table.

---

## Database Tables Discovered

### Encounter Tables (19 total)
1. **encounter** (main table - 24 columns)
2. encounter_type
3. encounter_reason_code
4. encounter_diagnosis
5. encounter_participant
6. encounter_location
7. encounter_class_history
8. encounter_service_type_coding
9. encounter_appointment
10. encounter_hospitalization
11. encounter_identifier
12. encounter_priority_coding
13. encounter_status_history
14. encounter_account
15. encounter_based_on
16. encounter_class
17. encounter_episode_of_care
18. encounter_reason_reference
19. document_reference_context_encounter

### Appointment Tables (14 total)
1. **appointment** (main table - 13 columns)
2. appointment_appointment_type_coding
3. appointment_participant
4. appointment_service_category
5. appointment_service_type
6. appointment_reason_code
7. appointment_based_on
8. appointment_cancelation_reason_coding
9. appointment_identifier
10. appointment_reason_reference
11. appointment_requested_period
12. appointment_slot
13. appointment_specialty
14. appointment_supporting_information

---

## Main Table Structures

### encounter (24 columns)

**Key Identification Columns:**
- `id` - Unique encounter ID
- `subject_reference` - Patient FHIR ID
- `status` - 'finished', 'in-progress', 'unknown'
- **`class_display`** - **CRITICAL**: "Surgery Log", "Appointment", "HOV", "Support OP Encounter"
- `period_start` - Encounter start date/time
- `period_end` - Encounter end date/time

**Service Details:**
- `service_type_text` - Type of service provided
- `priority_text` - Encounter priority
- `service_provider_reference` - Hospital/provider
- `service_provider_display` - Provider name

**Structural:**
- `resource_type` - Always 'Encounter'
- `class_code`, `class_system` - FHIR codes
- `length_value`, `length_unit` - Duration
- `part_of_reference` - Parent encounter if exists

**Full Column List:**
1. id
2. resource_type
3. status
4. class_code
5. class_system
6. **class_display** ← KEY FOR SURGICAL EVENTS
7. service_type_text
8. priority_text
9. subject_reference ← PATIENT ID
10. subject_type
11. subject_display
12. **period_start** ← ENCOUNTER DATE
13. period_end
14. length_value
15. length_comparator
16. length_unit
17. length_system
18. length_code
19. service_provider_reference
20. service_provider_type
21. service_provider_display
22. part_of_reference
23. part_of_type
24. part_of_display

### appointment (13 columns)

**Key Columns:**
- `id` - Unique appointment ID
- `status` - Appointment status
- `appointment_type_text` - Type of appointment
- `start` - Appointment start date/time
- `end` - Appointment end date/time
- `minutes_duration` - Appointment duration
- `description` - Appointment description
- `comment` - Additional notes
- `patient_instruction` - Instructions for patient

**Full Column List:**
1. id
2. resource_type
3. status
4. cancelation_reason_text
5. appointment_type_text
6. priority
7. description
8. start
9. end
10. minutes_duration
11. created
12. comment
13. patient_instruction

---

## Key Encounter Subtables

### encounter_type
Links encounter to FHIR type codes.

**Columns:**
- id
- encounter_id (FK to encounter)
- type_coding - FHIR type code
- type_text - Human-readable type

**Use Case**: May distinguish follow-up visits from other appointments

---

### encounter_reason_code
Stores reason(s) for encounter.

**Columns:**
- id
- encounter_id (FK to encounter)
- reason_code_coding - FHIR reason code
- reason_code_text - Human-readable reason

**Use Case**: Filter for oncology-related encounters

---

### encounter_diagnosis
Links encounters to conditions/diagnoses.

**Columns:**
- id
- encounter_id (FK to encounter)
- diagnosis_condition_reference - FK to condition table
- diagnosis_condition_display - Condition name
- diagnosis_use_coding - Diagnosis type (admission, billing, discharge)
- diagnosis_rank - Priority order

**Use Case**: Link encounters to cancer diagnoses

---

### encounter_participant
Lists providers/practitioners in encounter.

**Columns:**
- id
- encounter_id (FK to encounter)
- participant_type - Role in encounter
- participant_individual_reference - Provider ID

**Use Case**: Track which oncologists were present

---

### encounter_location
Location(s) where encounter occurred.

**Columns:**
- id
- encounter_id (FK to encounter)
- location_location_reference - Location ID
- location_status - planned/active/completed

**Use Case**: Filter to specific hospital locations

---

### encounter_service_type_coding
Detailed service type classification.

**Columns:**
- id
- encounter_id (FK to encounter)
- service_type_coding_system - Code system
- service_type_coding_code - Service code
- service_type_coding_display - Human-readable service

**Use Case**: Filter to oncology/neurology services

---

### encounter_appointment
Links encounters to appointments.

**Columns:**
- id
- encounter_id (FK to encounter)
- appointment_reference - FK to appointment table

**Use Case**: **CRITICAL** - May distinguish scheduled follow-ups from ad-hoc encounters

---

## Critical Discovery: Surgery Log Encounters

### Sample Surgical Encounter Found

**Query Used:**
```sql
SELECT * FROM encounter
WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
LIMIT 1
```

**Result:**
```
id: eDPj1SkOuVjVPYGhPgUGLqg3
resource_type: Encounter
status: unknown
class_display: Surgery Log  ← CRITICAL!
subject_reference: e4BwD8ZYDBccepXcJ.Ilo3w3
period_start: 2021-03-10T12:20:00Z
period_end: 2021-03-10T19:50:00Z
service_provider_display: THE CHILDREN'S HOSPITAL OF PHILADELPHIA
```

**Significance**: This is the **third diagnosis event** (2021-03-10, age 5780 days) that was missing from procedure table!

---

## Problem Solved: Missing Surgical Dates

### Previous Approach (FAILED)
```sql
SELECT p.performed_date_time
FROM procedure p
JOIN procedure_code_coding pcc ON p.id = pcc.procedure_id
WHERE p.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND pcc.code_coding_code IN ('61500', '61510', '61518', '61524')
```

**Result**: Found 4 procedures but only 1 with date (2018-05-28)
- `` | 61524 | CRNEC INFRATNTOR/POSTFOSSA EXC/FENESTRATION CYST
- `` | 61510 | CRANIEC TREPHINE BONE FLP BRAIN TUMOR SUPRTENT OR
- `` | 61518 | CRNEC EXC BRAIN TUMOR INFRATENTORIAL/POST FOSSA
- **2018-05-28** | 61500 | CRANIECTOMY W/EXCISION TUMOR/LESION SKULL

### New Approach (SOLUTION)
```sql
SELECT period_start, class_display, id
FROM encounter
WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND class_display = 'Surgery Log'
    AND period_start IS NOT NULL
ORDER BY period_start
```

**Expected Result**: 2 surgical encounters
- 2018-05-28 (initial surgery)
- 2021-03-10 (second surgery)

---

## Diagnosis Events Strategy

### Gold Standard Events (C1277724)
1. **ET_FWYP9TY0** (age 4763 = 2018-05-28): Initial surgery
2. **ET_94NK0H3X** (age 5095 = 2019-04-25): Progression detected (MRI → chemotherapy)
3. **ET_FRRCB155** (age 5780 = 2021-03-10): Second surgery

### Data Sources
1. **Surgical Events**: `encounter.class_display = 'Surgery Log'`
2. **Progression Events**: `problem_list_diagnoses` with keywords: progress, recurrence, metastasis

### Implementation Query
```sql
-- Surgical diagnosis events
SELECT 
    id as encounter_id,
    period_start,
    class_display
FROM encounter
WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND class_display = 'Surgery Log'
    AND period_start IS NOT NULL
ORDER BY period_start

-- Progression diagnosis events
SELECT 
    onset_date_time,
    diagnosis_name
FROM problem_list_diagnoses
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND onset_date_time IS NOT NULL
    AND (
        LOWER(diagnosis_name) LIKE '%progress%'
        OR LOWER(diagnosis_name) LIKE '%recur%'
        OR LOWER(diagnosis_name) LIKE '%metasta%'
    )
ORDER BY onset_date_time
```

---

## Follow-Up Encounters Filtering Problem

### Current Issue
**Query extracts 321 encounters but gold standard has 10**

### Current Filter (TOO BROAD)
```sql
SELECT id, period_start, class_display
FROM encounter
WHERE subject_reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'
    AND period_start IS NOT NULL
    AND status IN ('finished', 'in-progress')
    AND (
        class_display IN ('Appointment', 'HOV')
        OR (class_display = 'Support OP Encounter' 
            AND service_type_text LIKE '%oncology%')
    )
    AND period_start >= '2018-05-28'
```

**Problem**: Includes all appointments (daily visits, unrelated appointments, etc.)

### Investigation Strategy

Query gold standard encounter dates to find distinguishing characteristics:

**Ages**: 4931, 5130, 5228, 5396, 5613, 5928, 6095, 6233, 6411, 6835 days  
**Dates**: 2018-09-14, 2018-12-23, 2019-03-31, 2019-09-25, 2020-03-30, 2020-12-10, 2021-05-27, 2021-10-12, 2022-04-09, 2023-06-03

**Hypothesis 1: Appointment Linkage**
Check if gold standard encounters all have appointment references:
```sql
SELECT 
    e.id,
    e.period_start,
    ea.appointment_reference
FROM encounter e
LEFT JOIN encounter_appointment ea ON e.id = ea.encounter_id
WHERE e.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND DATE(e.period_start) IN ('2018-09-14', '2018-12-23', ...)
```

**Hypothesis 2: Specific Encounter Types**
Check encounter_type for common patterns:
```sql
SELECT 
    e.period_start,
    et.type_coding,
    et.type_text
FROM encounter e
JOIN encounter_type et ON e.id = et.encounter_id
WHERE e.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND DATE(e.period_start) IN ('2018-09-14', '2018-12-23', ...)
```

**Hypothesis 3: Oncology Reason Codes**
Check if specific reason codes distinguish follow-ups:
```sql
SELECT 
    e.period_start,
    erc.reason_code_coding,
    erc.reason_code_text
FROM encounter e
JOIN encounter_reason_code erc ON e.id = erc.encounter_id
WHERE e.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND DATE(e.period_start) IN ('2018-09-14', '2018-12-23', ...)
```

---

## Implementation Plan

### Phase 1: Fix Diagnosis Events (30-45 min)

**Step 1**: Replace procedure query with encounter.class_display query
```python
surgical_query = f"""
SELECT 
    id as encounter_id,
    period_start,
    class_display
FROM {self.database}.encounter
WHERE subject_reference = '{self.patient_fhir_id}'
    AND class_display = 'Surgery Log'
    AND period_start IS NOT NULL
ORDER BY period_start
"""
```

**Step 2**: Add progression event query
```python
progression_query = f"""
SELECT 
    onset_date_time,
    diagnosis_name
FROM {self.database}.problem_list_diagnoses
WHERE patient_id = '{self.patient_fhir_id}'
    AND onset_date_time IS NOT NULL
    AND (
        LOWER(diagnosis_name) LIKE '%progress%'
        OR LOWER(diagnosis_name) LIKE '%recur%'
        OR LOWER(diagnosis_name) LIKE '%metasta%'
    )
ORDER BY onset_date_time
"""
```

**Step 3**: Combine events into diagnosis_dates dictionary

**Expected Outcome**: Find 3 diagnosis events instead of 1

---

### Phase 2: Fix Encounter Filtering (45-60 min)

**Step 1**: Investigate gold standard encounters using subtables

**Step 2**: Identify distinguishing pattern (appointment linkage, type, reason codes)

**Step 3**: Refine encounter filter based on findings

**Expected Outcome**: Reduce from 321 → 10-20 encounters

---

## Next Steps

1. ✅ Schema discovery complete
2. ⏳ Implement Phase 1 (diagnosis events)
3. ⏳ Validate improvement
4. ⏳ Implement Phase 2 (encounter filtering)
5. ⏳ Final validation (target: 80%+ accuracy)
6. ⏳ Create production extraction script
7. ⏳ Document findings and move to next CSV

---

## References

- **Gold Standard**: GOLD_STANDARD_C1277724.md
- **Framework**: COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md
- **Validation Script**: athena_extraction_validation/scripts/validate_encounters_csv.py
- **Database**: fhir_v2_prd_db (AWS Athena)
