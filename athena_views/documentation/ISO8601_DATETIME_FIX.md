# ISO 8601 DateTime Casting Fix

## Issue

The datetime standardization process incorrectly used `TRY(CAST(column AS TIMESTAMP(3)))` for columns containing ISO 8601 formatted timestamps (e.g., "2025-05-14T14:07:05Z"). This function expects a different format and returns NULL for all ISO 8601 values.

## Root Cause

Athena's `CAST(... AS TIMESTAMP(3))` function does **not** parse ISO 8601 format timestamps with the "T" delimiter and "Z" timezone indicator. It expects timestamps in format "YYYY-MM-DD HH:MM:SS.mmm".

## Solution

Use `FROM_ISO8601_TIMESTAMP(column)` for columns containing ISO 8601 formatted timestamps.

## Testing Results

| Table | Column | Format | `TRY(CAST...)` Works? | `FROM_ISO8601_TIMESTAMP(...)` Works? |
|-------|--------|--------|-----------------------|--------------------------------------|
| radiology_imaging_mri | result_datetime | 2025-03-25T22:07:00Z | ❌ NO | ✅ YES |
| radiology_imaging | result_datetime | 2025-03-25T22:07:00Z | ❌ NO | ✅ YES |
| lab_tests | result_datetime | 2021-07-28T00:26:00Z | ❌ NO | ✅ YES |
| molecular_tests | result_datetime | 2024-04-11T16:03:00Z | ❌ NO | ✅ YES |

## Affected Views

The following views in DATETIME_STANDARDIZED_VIEWS.sql need to be fixed:

### 1. v_imaging (Lines 2837-2862)
**Issue**: NULL imaging_date for all 181 imaging events
**Fix**:
```sql
-- BEFORE:
TRY(CAST(mri.result_datetime AS TIMESTAMP(3))) as imaging_date
TRY(CAST(ri.result_datetime AS TIMESTAMP(3))) as imaging_date

-- AFTER:
FROM_ISO8601_TIMESTAMP(mri.result_datetime) as imaging_date
FROM_ISO8601_TIMESTAMP(ri.result_datetime) as imaging_date
```

### 2. v_measurements (Line 2963)
**Issue**: NULL lt_measurement_date for all lab test measurements
**Fix**:
```sql
-- BEFORE:
TRY(CAST(lt.result_datetime AS TIMESTAMP(3))) as lt_measurement_date

-- AFTER:
FROM_ISO8601_TIMESTAMP(lt.result_datetime) as lt_measurement_date
```

### 3. v_molecular_tests (Lines 3060, 3063)
**Issue**: NULL mt_test_date and incorrect age_at_test_days
**Fix**:
```sql
-- BEFORE:
TRY(CAST(SUBSTR(mt.result_datetime, 1, 10) AS TIMESTAMP(3))) as mt_test_date
TRY(CAST(SUBSTR(mt.result_datetime, 1, 10) AS DATE)) as age_at_test_days

-- AFTER:
CAST(FROM_ISO8601_TIMESTAMP(mt.result_datetime) AS DATE) as mt_test_date
DATE_DIFF('day', DATE(pa.birth_date), CAST(FROM_ISO8601_TIMESTAMP(mt.result_datetime) AS DATE)) as age_at_test_days
```

## Documentation Updates Needed

### DATETIME_STANDARDIZATION_PLAN.md

Update Rule 1 to distinguish between two types of ISO timestamps:

**Rule 1A: VARCHAR with ISO8601 timestamp (with T/Z) → TIMESTAMP(3)**
```sql
-- Format: "2024-06-10T14:30:00Z"
FROM_ISO8601_TIMESTAMP(collection_datetime) AS collection_datetime
```

**Rule 1B: VARCHAR with standard timestamp (space-delimited) → TIMESTAMP(3)**
```sql
-- Format: "2024-06-10 14:30:00"
TRY(CAST(collection_datetime AS TIMESTAMP(3))) AS collection_datetime
```

## Impact Assessment

**Before Fix**:
- v_imaging: All 181 imaging events had NULL event_date in v_unified_patient_timeline
- v_measurements: Lab test dates were NULL
- v_molecular_tests: Molecular test dates were NULL

**After Fix**:
- All imaging events will have valid dates
- All lab test measurements will have valid dates
- All molecular tests will have valid dates
- v_unified_patient_timeline will include all temporal events

## Implementation Steps

1. ✅ Identify affected tables and test casting methods
2. ✅ Document the issue and solution
3. ✅ Update DATETIME_STANDARDIZED_VIEWS.sql with fixes
4. ✅ Update DATETIME_STANDARDIZATION_PLAN.md documentation
5. ✅ Deploy fixed views to Athena (v_imaging, v_measurements, v_molecular_tests)
6. ✅ Redeploy v_unified_patient_timeline to pick up fixed imaging dates
7. ⬜ Rebuild timeline database with complete data

## Deployment Log

- 2025-10-19 23:XX: Fixed DATETIME_STANDARDIZED_VIEWS.sql (lines 2841, 2855, 2963, 3060, 3063)
- 2025-10-19 23:XX: Updated DATETIME_STANDARDIZATION_PLAN.md (split Rule 1 into 1A/1B)
- 2025-10-19 23:XX: Deployed v_imaging (Query ID: 2e28061a-d3f2-4b6e-b129-67714fd8ce0a) ✅ SUCCEEDED
- 2025-10-19 23:XX: Deployed v_measurements (Query ID: c25e0fc0-597a-4537-939d-f4d57b0d6720) ✅ SUCCEEDED
- 2025-10-19 23:XX: Deployed v_molecular_tests (Query ID: 7a8eac71-a1f7-48b8-8c44-995b576ee325) ✅ SUCCEEDED
- 2025-10-19 23:XX: Redeployed v_unified_patient_timeline (Query ID: ce183dd0-18ac-485a-995c-e80dc4a99562) ✅ SUCCEEDED

## Verification

Test patient e4BwD8ZYDBccepXcJ.Ilo3w3:
- **Before**: 181 imaging events, 0 with dates (100% NULL)
- **After**: 181 imaging events, 181 with dates (100% valid)

---

**Date**: 2025-10-19
**Author**: Automated analysis
**Status**: ✅ COMPLETE - All views deployed successfully
