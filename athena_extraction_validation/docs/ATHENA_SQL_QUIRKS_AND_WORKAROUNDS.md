# Athena SQL Quirks and Workarounds

**Date:** 2025-10-11  
**Context:** Appointment extraction debugging  
**Database:** fhir_v2_prd_db (Athena/Presto SQL)

## Critical Discovery: Column Aliasing Limitation with JOINs

### Problem Statement

When extracting appointment data using a JOIN between `appointment` and `appointment_participant` tables, Athena rejected queries with **specific column selection and aliasing**, returning:

```
InvalidRequestException: Queries of this type are not supported
```

### Failed Query Pattern

```sql
SELECT DISTINCT
    a.id as appointment_fhir_id,
    a.status as appointment_status,
    a.appointment_type_text,
    a.description,
    a.start,
    a.end,
    a.minutes_duration,
    a.created,
    a.comment,
    a.patient_instruction,
    a.cancelation_reason_text,
    a.priority
FROM fhir_v2_prd_db.appointment a
JOIN fhir_v2_prd_db.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference = 'Patient/{fhir_id}'
ORDER BY a.start
```

**Result:** ❌ "Queries of this type are not supported"

### Working Query Pattern

```sql
SELECT DISTINCT a.*
FROM fhir_v2_prd_db.appointment a
JOIN fhir_v2_prd_db.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference = 'Patient/{fhir_id}'
ORDER BY a.start
```

**Result:** ✅ Successfully returns all appointment records

### Additional Constraint: OR Clause Limitation

Athena also does **NOT support OR clauses** in the WHERE condition when used with this JOIN pattern:

```sql
-- THIS FAILS
WHERE ap.participant_actor_reference = '{fhir_id}'
   OR ap.participant_actor_reference = 'Patient/{fhir_id}'
```

**Workaround:** Use only the format that matches your data. In our case, the data uses `'Patient/{fhir_id}'` format exclusively.

## Implementation Pattern

### Python Implementation with DataFrame Column Renaming

```python
def extract_appointments(self) -> pd.DataFrame:
    """Extract appointments via appointment_participant pathway"""
    
    # Query with SELECT a.* (required by Athena)
    query = f"""
    SELECT DISTINCT a.*
    FROM {self.database}.appointment a
    JOIN {self.database}.appointment_participant ap ON a.id = ap.appointment_id
    WHERE ap.participant_actor_reference = 'Patient/{self.patient_fhir_id}'
    ORDER BY a.start
    """
    
    appointments = self.execute_query(query, "Query appointment table")
    
    if not appointments:
        return pd.DataFrame()
    
    df = pd.DataFrame(appointments)
    
    # Rename columns to match expected format (since we use SELECT a.*)
    df = df.rename(columns={
        'id': 'appointment_fhir_id',
        'status': 'appointment_status'
    })
    
    # Calculate derived columns
    df['age_at_appointment_days'] = df['start'].apply(self.calculate_age_days)
    df['appointment_date'] = df['start'].str[:10]
    
    # Reorder columns - use only columns that exist
    cols = ['appointment_fhir_id', 'appointment_date', 'age_at_appointment_days', 
            'appointment_status', 'appointment_type_text', 'description', 'start', 'end',
            'minutes_duration', 'created', 'comment', 'patient_instruction',
            'cancelation_reason_text', 'priority']
    
    # Filter to only existing columns
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    
    return df
```

## Columns Returned by SELECT a.*

From `appointment` table:
- `id` (requires rename to `appointment_fhir_id`)
- `resource_type` (always 'Appointment')
- `status` (requires rename to `appointment_status`)
- `cancelation_reason_text`
- `appointment_type_text`
- `priority`
- `description`
- `start` (ISO 8601 datetime)
- `end` (ISO 8601 datetime)
- `minutes_duration`
- `created` (ISO 8601 datetime)
- `comment`
- `patient_instruction`

## Testing Results

### Original Patient (e4BwD8ZYDBccepXcJ.Ilo3w3)
- **Before fix:** 0 appointments extracted
- **After fix:** 502 appointments extracted ✅
- Date range: 2005-05-19 to 2025-08-21
- Age range: 6 to 7405 days

### New Patient (eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3)
- **Before fix:** 0 appointments extracted
- **After fix:** 62 appointments extracted ✅
- Date range: 2012-07-19 to 2019-07-09
- Age range: 8833 to 11379 days

## Debugging Process

### Timeline of Discovery

1. **Initial Issue:** Appointment extraction returned 0 rows for all patients
2. **Pathway Testing:** Tested two approaches:
   - `encounter_appointment` with nested subquery: ❌ Fails (0 records in table)
   - `appointment_participant` with JOIN: Appeared to work in isolation
3. **Implementation:** Modified scripts to use `appointment_participant` pathway with column aliasing
4. **Failure:** Scripts still failed with "Queries of this type are not supported"
5. **Isolation Testing:** Tested exact query from script - also failed
6. **Hypothesis:** Suspected OR clause might be the issue
7. **Testing:** Removed OR clause - query succeeded but with 0 results
8. **Format Discovery:** Changed to `'Patient/{fhir_id}'` format - found appointments!
9. **Column Testing:** Tried with specific columns - FAILED
10. **Solution:** Used `SELECT a.*` - SUCCESS! ✅

### Key Insight

The error message "Queries of this type are not supported" is **NOT specific** to the actual problem. It can mean:
- OR clauses not supported in this JOIN context
- Column aliasing not supported in this JOIN context
- Other unsupported SQL patterns

**Solution:** Simplify query as much as possible, then add complexity incrementally.

## Athena SQL Best Practices for FHIR Extraction

### ✅ DO:
- Use `SELECT table_alias.*` when possible
- Use simple WHERE conditions without OR clauses
- Rename columns in application code (Python/pandas) after query execution
- Test queries in isolation before embedding in scripts
- Verify data format (e.g., 'Patient/{id}' vs just '{id}')

### ❌ DON'T:
- Use column aliasing in SELECT when JOINing tables (especially with complex WHERE)
- Use OR clauses in WHERE with JOINed tables
- Assume error messages are specific (they're often generic)
- Use nested subqueries with REPLACE() or complex string manipulation
- Assume a query that works in one context will work in another

## Related Athena Limitations

From previous debugging sessions:

1. **Nested Subqueries with String Functions:** Athena does not support nested subqueries that use `REPLACE()` or similar functions
2. **CTEs (Common Table Expressions):** Limited support depending on context
3. **Complex JOINs:** Some JOIN patterns work in isolation but fail when combined with other SQL features

## Git Commits

- **Initial fix (failed):** `007dac5` - Switched to appointment_participant pathway with column list
- **Corrected fix (working):** `381839d` - Changed to SELECT a.* without column aliasing
- **Documentation:** `02f3b3b` - Initial documentation (needs update)

## Files Modified

- `scripts/extract_all_encounters_metadata.py` (hardcoded patient version)
- `scripts/config_driven_versions/extract_all_encounters_metadata.py` (config-driven version)

## Impact

This fix resolves a critical data completeness issue. Appointments represent a significant portion of patient encounters and were completely missing from extracted data (0% capture → 100% capture).

For clinical trials and research workflows, appointment data provides:
- Visit schedules and adherence
- Appointment types (office visit, imaging, procedures, etc.)
- Temporal patterns in care delivery
- Linkage between encounters and scheduled care

## Recommendations for Future Extraction Scripts

1. **Start Simple:** Begin with `SELECT *` or `SELECT table_alias.*`
2. **Test Incrementally:** Add WHERE conditions, JOINs, ORDER BY one at a time
3. **Avoid Aliases in SELECT:** Rename columns in application code instead
4. **Document Quirks:** When you discover a limitation, document it immediately
5. **Keep Working Patterns:** Maintain a library of tested, working query patterns

## References

- **Validation Script:** `/Users/resnick/Downloads/Athena_db_structure/comprehensive_patient_extraction.py`
- **Documentation:** `docs/APPOINTMENT_EXTRACTION_FIX_2025-10-11.md`
- **Troubleshooting Guide:** `BRIM_TROUBLESHOOTING_GUIDE.md`

---

**Last Updated:** 2025-10-11  
**Validated Against:** fhir_v2_prd_db with 2 patients (564 total appointments extracted)
