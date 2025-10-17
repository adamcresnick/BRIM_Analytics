# Date/Time Format Standardization Analysis

**Date**: 2025-10-17
**Purpose**: Identify and standardize date/time formats across all 15 Athena views

---

## Executive Summary

**Problem**: FHIR data stores dates in **two incompatible formats**:
1. **ISO 8601 with timezone**: `2025-01-24T09:02:00Z` (observation, appointment, procedure, lab_tests, etc.)
2. **Date-only format**: `2012-10-19` (problem_list_diagnoses, patient birth_date)

**Impact**:
- Python pandas reads these as different types (datetime64 vs object/string)
- Timezone information is lost when extracting just the date
- Age calculations can be off by hours/days depending on timezone
- Joins across tables may fail due to format mismatches

**Solution**: Standardize ALL date/time columns in Athena views using consistent extraction functions

---

## Current Date/Time Formats in Source Tables

### Format 1: ISO 8601 with UTC Timezone (`YYYY-MM-DDTHH:MM:SSZ`)

**Tables using this format**:
- `observation.effective_date_time`: `2025-01-24T09:02:00Z`
- `observation.issued`: `2025-01-24T09:39:07Z`
- `appointment.start`: `2001-09-06T13:00:00Z`
- `appointment.created`: (empty in sample, but same format when present)
- `procedure.performed_date_time`: `2024-11-08T16:39:08Z`
- `procedure.performed_period_start`: `2025-01-07T16:57:00Z`
- `lab_tests.result_datetime`: `2010-08-05T16:00:00Z`
- `molecular_tests.result_datetime`: Similar format
- `medication_request.authored_on`: Similar format
- `service_request.occurrence_date_time`: Similar format
- `service_request.authored_on`: Similar format
- `care_plan.period_start/end`: Similar format
- `document_reference.date`: Similar format

**Characteristics**:
- Always stored as VARCHAR in Athena
- Includes time component (HH:MM:SS)
- Includes timezone indicator (`Z` = UTC)
- Length: 20 characters

### Format 2: Date-Only (`YYYY-MM-DD`)

**Tables using this format**:
- `problem_list_diagnoses.onset_date_time`: `2012-10-19`
- `problem_list_diagnoses.recorded_date`: `2012-10-19`
- `patient_access.birth_date`: Similar format

**Characteristics**:
- Stored as VARCHAR in Athena
- No time component
- No timezone indicator
- Length: 10 characters

---

## Current Handling in Views

### Inconsistent SUBSTR() Usage

Views currently use `SUBSTR(date_column, 1, 10)` to extract dates, which:
- ✅ Works for ISO 8601 format (extracts `2025-01-24` from `2025-01-24T09:02:00Z`)
- ✅ Works for date-only format (returns `2012-10-19` unchanged)
- ❌ **Loses time information** (can't determine if event was morning vs evening)
- ❌ **Loses timezone information** (can't convert to local time)
- ❌ **Inconsistent for sorting** when time matters

### Example from v_problem_list_diagnoses (lines 48-56):
```sql
pld.onset_date_time as pld_onset_date,  -- Output: "2012-10-19"
TRY(DATE_DIFF('day',
    DATE(pa.birth_date),
    CAST(SUBSTR(pld.onset_date_time, 1, 10) AS DATE))) as age_at_onset_days
```

### Example from v_measurements (lines 488, 549-551):
```sql
effective_date_time as obs_measurement_date,  -- Output: "2025-01-24T09:02:00Z"
...
TRY(DATE_DIFF('day',
    DATE(pa.birth_date),
    CAST(SUBSTR(COALESCE(obs_measurement_date, lt_measurement_date), 1, 10) AS DATE))) as age_at_measurement_days
```

---

## Problems with Current Approach

### 1. Mixed Date Formats in Output

**Example**: `measurements.csv` from Python script
```csv
patient_fhir_id,obs_measurement_date,lt_measurement_date
e4BwD8...,2025-01-24T09:02:00Z,
e4BwD8...,,2010-08-05T16:00:00Z
```

Some columns output full ISO 8601, others output date-only. This causes:
- Pandas treats columns inconsistently
- Sorting may not work as expected
- Age calculations differ by hours/days

### 2. Timezone Loss

When extracting dates with `SUBSTR(date, 1, 10)`:
- `2025-01-24T09:02:00Z` → `2025-01-24`
- Time component lost (was this 9am or 9pm?)
- Timezone lost (can't convert to patient's local time)

**Impact**:
- Events on same day can't be ordered correctly
- Multi-day hospitalizations lose precision
- Cross-system integration requires timezone

### 3. Inconsistent Python Script Behavior

Python scripts sometimes:
- Return full ISO 8601 strings (observation dates)
- Extract dates with `SUBSTR()` in SQL (problem_list dates)
- Use `pd.to_datetime()` with `errors='coerce'` (handles both formats but inconsistent)

**Result**: Mixed date formats in CSV outputs

---

## Recommended Standardization Strategy

### Option 1: Store Full ISO 8601 (Recommended for Precision)

**Advantages**:
- Preserves all information (date, time, timezone)
- Allows precise event ordering
- Supports timezone conversions
- Best for clinical research

**Disadvantages**:
- Larger storage/output size
- Downstream tools must handle timestamps

**Implementation**:
```sql
-- For ISO 8601 columns - return as-is
a.start as appointment_start,  -- Returns: 2025-01-24T09:02:00Z

-- For date-only columns - pad with midnight UTC
CASE
    WHEN LENGTH(pld.onset_date_time) = 10
    THEN pld.onset_date_time || 'T00:00:00Z'
    ELSE pld.onset_date_time
END as pld_onset_date  -- Returns: 2012-10-19T00:00:00Z
```

### Option 2: Store Date-Only (Recommended for Simplicity)

**Advantages**:
- Consistent format across all columns
- Smaller output files
- Easier for non-technical users
- Matches current age calculation needs

**Disadvantages**:
- Loses time-of-day information
- Can't order same-day events
- Loses timezone information

**Implementation**:
```sql
-- Extract date portion for all columns
SUBSTR(a.start, 1, 10) as appointment_start,  -- Returns: 2025-01-24
SUBSTR(pld.onset_date_time, 1, 10) as pld_onset_date,  -- Returns: 2012-10-19
```

### Option 3: Hybrid Approach (**RECOMMENDED**)

**Strategy**:
- Store **date-only** for age calculations and filtering (standardized columns)
- Store **full ISO 8601** for datetime columns where precision matters (separate columns)

**Implementation**:
```sql
-- Date columns (for filtering, joining, age calculations)
SUBSTR(a.start, 1, 10) as appointment_date,  -- YYYY-MM-DD

-- Full datetime columns (for precise ordering, timezone conversion)
a.start as appointment_start_datetime,  -- YYYY-MM-DDTHH:MM:SSZ
a."end" as appointment_end_datetime,

-- Age calculations use date-only
TRY(DATE_DIFF('day',
    DATE(pa.birth_date),
    TRY(CAST(SUBSTR(a.start, 1, 10) AS DATE)))) as age_at_appointment_days
```

**Benefits**:
- ✅ Consistent date format for all `*_date` columns
- ✅ Preserves precision in `*_datetime` columns
- ✅ Clear naming convention
- ✅ Supports both use cases

---

## Proposed Standardization Rules

### Rule 1: All `*_date` columns return `YYYY-MM-DD` format
```sql
-- Good
SUBSTR(column_name, 1, 10) as column_date

-- Bad
column_name as column_date  -- Mixed formats!
```

### Rule 2: All `*_datetime` columns return `YYYY-MM-DDTHH:MM:SSZ` format
```sql
-- For ISO 8601 source columns
column_name as column_datetime  -- Return as-is

-- For date-only source columns (rare)
CASE
    WHEN LENGTH(column_name) = 10
    THEN column_name || 'T00:00:00Z'
    ELSE column_name
END as column_datetime
```

### Rule 3: Age calculations always use date-only
```sql
-- Use SUBSTR to extract date, then TRY(CAST(...AS DATE))
TRY(DATE_DIFF('day',
    DATE(pa.birth_date),
    TRY(CAST(SUBSTR(event_datetime, 1, 10) AS DATE)))) as age_at_event_days
```

### Rule 4: Sorting uses appropriate column
```sql
-- For day-level precision
ORDER BY appointment_date

-- For precise ordering within a day
ORDER BY appointment_start_datetime
```

---

## Column-by-Column Recommendations

### v_patient_demographics
| Current Column | Format | Recommendation |
|---|---|---|
| pd_birth_date | YYYY-MM-DD | ✅ Keep as-is |
| pd_age_years | INTEGER | ✅ Keep as-is |

**No changes needed** - already date-only

---

### v_problem_list_diagnoses
| Current Column | Format | Recommendation |
|---|---|---|
| pld_onset_date | YYYY-MM-DD | ✅ Keep as-is (currently using SUBSTR) |
| pld_abatement_date | YYYY-MM-DD | ✅ Keep as-is |
| pld_recorded_date | YYYY-MM-DD | ✅ Keep as-is |

**No changes needed** - already date-only

---

### v_procedures
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| proc_performed_date_time | **Mixed** | ISO 8601 with time | **ADD**: `proc_performed_date` (date-only)<br>**KEEP**: `proc_performed_date_time` (full ISO) |
| proc_performed_period_start | **Mixed** | ISO 8601 with time | **ADD**: `proc_performed_start_date` (date-only)<br>**KEEP**: `proc_performed_period_start` (full ISO) |
| proc_performed_period_end | **Mixed** | ISO 8601 with time | **ADD**: `proc_performed_end_date` (date-only)<br>**KEEP**: `proc_performed_period_end` (full ISO) |
| procedure_date | YYYY-MM-DD | ✅ Correctly calculated | ✅ Keep as-is |

**Changes needed**: Add date-only columns for consistency

---

### v_medications
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| medication_start_date | **Mixed** | alias for authored_on (ISO 8601) | **RENAME**: `medication_start_datetime`<br>**ADD**: `medication_start_date` (date-only) |
| mr_authored_on | **Mixed** | ISO 8601 with time | **ADD**: `mr_authored_date` (date-only)<br>**KEEP**: `mr_authored_on` (full ISO) |
| mr_validity_period_start | **Mixed** | ISO 8601 with time | **ADD**: `mr_validity_start_date` (date-only)<br>**KEEP**: `mr_validity_period_start` (full ISO) |
| mr_validity_period_end | **Mixed** | ISO 8601 with time | **ADD**: `mr_validity_end_date` (date-only)<br>**KEEP**: `mr_validity_period_end` (full ISO) |

**Changes needed**: Add date-only columns + rename for clarity

---

### v_imaging
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| imaging_date | **Mixed** | ISO 8601 with time | **RENAME**: `imaging_datetime`<br>**ADD**: `imaging_date` (date-only) |
| report_issued | **Mixed** | ISO 8601 with time | **ADD**: `report_issued_date` (date-only)<br>**KEEP**: `report_issued` (full ISO) |
| report_effective_period_start | **Mixed** | ISO 8601 with time | **ADD**: `report_effective_start_date` (date-only)<br>**KEEP**: `report_effective_period_start` (full ISO) |
| report_effective_period_stop | **Mixed** | ISO 8601 with time | **ADD**: `report_effective_stop_date` (date-only)<br>**KEEP**: `report_effective_period_stop` (full ISO) |

**Changes needed**: Add date-only columns for filtering/joining

---

### v_encounters
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| encounter_date | YYYY-MM-DD | ✅ Correctly extracted with TRY(CAST(SUBSTR())) | ✅ Keep as-is |
| period_start | **Mixed** | ISO 8601 with time | **KEEP**: for precise times |
| period_end | **Mixed** | ISO 8601 with time | **KEEP**: for precise times |

**Changes needed**: None (already has encounter_date for filtering)

---

### v_measurements (HIGHEST PRIORITY - Mixed formats in UNION)
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| obs_measurement_date | **Mixed** | ISO 8601 with time | **RENAME**: `obs_measurement_datetime`<br>**ADD**: `obs_measurement_date` (date-only) |
| obs_issued | **Mixed** | ISO 8601 with time | **ADD**: `obs_issued_date` (date-only)<br>**KEEP**: `obs_issued` (full ISO) |
| lt_measurement_date | **Mixed** | ISO 8601 with time | **RENAME**: `lt_measurement_datetime`<br>**ADD**: `lt_measurement_date` (date-only) |

**CRITICAL**: UNION combines observation + lab_tests rows. Both must have consistent format!

**Changes needed**: Add date-only columns to both CTEs

---

### v_binary_files
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| dr_date | **Mixed** | ISO 8601 with time | **RENAME**: `dr_datetime`<br>**ADD**: `dr_date` (date-only) |
| dr_context_period_start | **Mixed** | ISO 8601 with time | **ADD**: `dr_context_start_date` (date-only)<br>**KEEP**: `dr_context_period_start` (full ISO) |
| dr_context_period_end | **Mixed** | ISO 8601 with time | **ADD**: `dr_context_end_date` (date-only)<br>**KEEP**: `dr_context_period_end` (full ISO) |

**Changes needed**: Add date-only columns

---

### v_molecular_tests
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| mt_test_date | YYYY-MM-DD | ✅ Correctly extracted with SUBSTR | ✅ Keep as-is |
| mt_specimen_collection_date | YYYY-MM-DD | ✅ Correctly extracted with SUBSTR | ✅ Keep as-is |
| mt_procedure_date | YYYY-MM-DD | ✅ Correctly extracted with SUBSTR | ✅ Keep as-is |

**No changes needed** - already date-only

---

### v_radiation_treatment_appointments
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| appointment_start | **Mixed** | ISO 8601 with time | **ADD**: `appointment_start_date` (date-only)<br>**KEEP**: `appointment_start` (full ISO) |
| appointment_end | **Mixed** | ISO 8601 with time | **ADD**: `appointment_end_date` (date-only)<br>**KEEP**: `appointment_end` (full ISO) |
| created | **Mixed** | ISO 8601 with time | **ADD**: `created_date` (date-only)<br>**KEEP**: `created` (full ISO) |

**Changes needed**: Add date-only columns

---

### v_radiation_treatment_courses
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| sr_occurrence_date_time | **Mixed** | ISO 8601 with time | **ADD**: `sr_occurrence_date` (date-only)<br>**KEEP**: `sr_occurrence_date_time` (full ISO) |
| sr_occurrence_period_start | **Mixed** | ISO 8601 with time | **ADD**: `sr_occurrence_start_date` (date-only)<br>**KEEP**: `sr_occurrence_period_start` (full ISO) |
| sr_occurrence_period_end | **Mixed** | ISO 8601 with time | **ADD**: `sr_occurrence_end_date` (date-only)<br>**KEEP**: `sr_occurrence_period_end` (full ISO) |
| sr_authored_on | **Mixed** | ISO 8601 with time | **ADD**: `sr_authored_date` (date-only)<br>**KEEP**: `sr_authored_on` (full ISO) |

**Changes needed**: Add date-only columns

---

### v_radiation_care_plan_notes
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| cp_period_start | **Mixed** | ISO 8601 with time | **ADD**: `cp_period_start_date` (date-only)<br>**KEEP**: `cp_period_start` (full ISO) |
| cp_period_end | **Mixed** | ISO 8601 with time | **ADD**: `cp_period_end_date` (date-only)<br>**KEEP**: `cp_period_end` (full ISO) |

**Changes needed**: Add date-only columns

---

### v_radiation_care_plan_hierarchy
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| cp_period_start | **Mixed** | ISO 8601 with time | **ADD**: `cp_period_start_date` (date-only)<br>**KEEP**: `cp_period_start` (full ISO) |
| cp_period_end | **Mixed** | ISO 8601 with time | **ADD**: `cp_period_end_date` (date-only)<br>**KEEP**: `cp_period_end` (full ISO) |

**Changes needed**: Add date-only columns

---

### v_radiation_service_request_notes
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| sr_authored_on | **Mixed** | ISO 8601 with time | **ADD**: `sr_authored_date` (date-only)<br>**KEEP**: `sr_authored_on` (full ISO) |
| sr_occurrence_date_time | **Mixed** | ISO 8601 with time | **ADD**: `sr_occurrence_date` (date-only)<br>**KEEP**: `sr_occurrence_date_time` (full ISO) |
| sr_occurrence_period_start | **Mixed** | ISO 8601 with time | **ADD**: `sr_occurrence_start_date` (date-only)<br>**KEEP**: `sr_occurrence_period_start` (full ISO) |
| sr_occurrence_period_end | **Mixed** | ISO 8601 with time | **ADD**: `sr_occurrence_end_date` (date-only)<br>**KEEP**: `sr_occurrence_period_end` (full ISO) |
| srn_note_time | **Mixed** | ISO 8601 with time | **ADD**: `srn_note_date` (date-only)<br>**KEEP**: `srn_note_time` (full ISO) |

**Changes needed**: Add date-only columns

---

### v_radiation_service_request_rt_history
| Current Column | Format | Current Issue | Recommendation |
|---|---|---|---|
| sr_authored_on | **Mixed** | ISO 8601 with time | **ADD**: `sr_authored_date` (date-only)<br>**KEEP**: `sr_authored_on` (full ISO) |

**Changes needed**: Add date-only columns

---

## Implementation Summary

### Views Needing Changes: 11 of 15

**No changes (already date-only or hybrid)**:
1. ✅ v_patient_demographics
2. ✅ v_problem_list_diagnoses
3. ✅ v_encounters (already has encounter_date)
4. ✅ v_molecular_tests (already has date-only columns)

**Need changes (add date-only columns)**:
5. v_procedures
6. v_medications
7. v_imaging
8. v_measurements (**PRIORITY - UNION issue**)
9. v_binary_files
10. v_radiation_treatment_appointments
11. v_radiation_treatment_courses
12. v_radiation_care_plan_notes
13. v_radiation_care_plan_hierarchy
14. v_radiation_service_request_notes
15. v_radiation_service_request_rt_history

---

## Next Steps

1. **Review**: Confirm hybrid approach (date + datetime columns) meets requirements
2. **Update**: Modify SQL views to add date-only columns
3. **Test**: Verify date extraction works for both source formats
4. **Document**: Update Python scripts to use new date-only columns
5. **Validate**: Compare output CSVs before/after to ensure consistency

**Estimated effort**: ~4-6 hours to update all views + testing
