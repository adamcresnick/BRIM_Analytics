# Column Naming Conventions for Radiation Extraction Script

**Date**: 2025-10-12
**Purpose**: Document resource-prefixed column naming for clear data source identification

---

## Overview

All columns now include prefixes indicating their source FHIR resource. This enables:
- **Clear data provenance**: Know which resource each field comes from
- **Date alignment**: Distinguish between dates from different resources
- **Easier joins**: Unambiguous column names when merging DataFrames
- **Analysis clarity**: Understand data structure without consulting documentation

---

## Column Naming Prefixes

### care_plan Resources

**Prefix Legend**:
- `cp_` = care_plan (parent table)
- `cpn_` = care_plan_note (child table)
- `cppo_` = care_plan_part_of (child table)

**care_plan_note table** → `service_request_notes.csv`:
```
care_plan_id                    # No prefix (primary key)
cpn_note_text                   # Note text content
cpn_contains_dose               # Boolean: contains Gy dose info
cpn_note_type                   # Categorized: Patient Instructions | Dosage Information | Side Effects/Monitoring
cp_status                       # Care plan status
cp_intent                       # Care plan intent
cp_title                        # Care plan title
cp_period_start                 # Care plan start date
cp_period_end                   # Care plan end date
```

**care_plan_part_of table** → `care_plan_hierarchy.csv`:
```
care_plan_id                    # No prefix (primary key)
cppo_part_of_reference          # Reference to parent care plan
cp_status                       # Care plan status
cp_intent                       # Care plan intent
cp_title                        # Care plan title
cp_period_start                 # Care plan start date
cp_period_end                   # Care plan end date
```

---

### service_request Resources

**Prefix Legend**:
- `sr_` = service_request (parent table)
- `srn_` = service_request_note (child table)
- `srrc_` = service_request_reason_code (child table)

**service_request_note table** → `service_request_notes.csv`:
```
service_request_id              # No prefix (primary key)
sr_intent                       # Service request intent
sr_status                       # Service request status
sr_authored_on                  # Authoring date
sr_occurrence_date_time         # Occurrence date/time (specific)
sr_occurrence_period_start      # Occurrence period start (range)
sr_occurrence_period_end        # Occurrence period end (range)
srn_note_text                   # Note text content
srn_note_time                   # Note timestamp
srn_author_display              # Note author
srn_contains_dose               # Boolean: contains Gy dose info
srn_note_type                   # Categorized: Treatment Coordination | Dosage Information | Team Communication
```

**service_request_reason_code table** → `service_request_rt_history.csv`:
```
service_request_id              # No prefix (primary key)
sr_intent                       # Service request intent
sr_status                       # Service request status
sr_authored_on                  # Authoring date
sr_occurrence_date_time         # Occurrence date/time (specific)
sr_occurrence_period_start      # Occurrence period start (range)
sr_occurrence_period_end        # Occurrence period end (range)
srrc_reason_code                # Primary reason code (from coding array)
srrc_reason_display             # Code display text
srrc_reason_system              # Coding system (e.g., SNOMED)
srrc_reason_text                # Free text reason
srrc_num_codings                # Number of codes in array
```

---

## Date Column Strategy

### Date Column Hierarchy (by resource)

**care_plan**:
1. Primary: `cp_period_start`, `cp_period_end` (treatment course dates)
2. Sort order: `ORDER BY parent.period_start`

**service_request**:
1. Most specific: `sr_occurrence_date_time` (exact timestamp)
2. Period: `sr_occurrence_period_start`, `sr_occurrence_period_end` (date range)
3. Fallback: `sr_authored_on` (when request was created)
4. Sort order: `ORDER BY COALESCE(occurrence_date_time, occurrence_period_start, authored_on)`

**service_request_note** (additional):
- `srn_note_time` (when note was written)
- Sort order: `COALESCE(note.note_time, parent.occurrence_date_time, parent.occurrence_period_start, parent.authored_on)`

### Cross-Resource Date Alignment

**Example Use Case**: Find all data for a specific treatment date

```python
import pandas as pd

# Load all extractions
care_plan_df = pd.read_csv('care_plan_notes.csv')
service_notes_df = pd.read_csv('service_request_notes.csv')
service_history_df = pd.read_csv('service_request_rt_history.csv')

# Convert dates to datetime
care_plan_df['cp_period_start'] = pd.to_datetime(care_plan_df['cp_period_start'])
service_notes_df['sr_occurrence_date_time'] = pd.to_datetime(service_notes_df['sr_occurrence_date_time'])
service_history_df['sr_occurrence_date_time'] = pd.to_datetime(service_history_df['sr_occurrence_date_time'])

# Find events on 2024-03-15
target_date = pd.to_datetime('2024-03-15')

cp_events = care_plan_df[care_plan_df['cp_period_start'] == target_date]
sr_note_events = service_notes_df[service_notes_df['sr_occurrence_date_time'].dt.date == target_date.date()]
sr_history_events = service_history_df[service_history_df['sr_occurrence_date_time'].dt.date == target_date.date()]

print(f"Care plan events: {len(cp_events)}")
print(f"Service request notes: {len(sr_note_events)}")
print(f"RT history codes: {len(sr_history_events)}")
```

---

## RT-Specific Keywords Update

### Added Variants
Previously only had: `'rad onc'`

Now includes all variants:
- `'rad onc'` (space)
- `'rad-onc'` (hyphen)
- `'radonc'` (no separator)

This ensures we capture all common abbreviations for "Radiation Oncology".

---

## Column Prefix Benefits

### 1. Clear Data Provenance
**Before**:
```
period_start                    # Which resource? Ambiguous!
occurrence_date_time            # From where?
note_text                       # Which note table?
```

**After**:
```
cp_period_start                 # Clearly: care_plan.period_start
sr_occurrence_date_time         # Clearly: service_request.occurrence_date_time
cpn_note_text                   # Clearly: care_plan_note.note_text
srn_note_text                   # Clearly: service_request_note.note_text
```

### 2. Easier DataFrame Merges
```python
# Merge care_plan and service_request data
# No column name conflicts!
merged = care_plan_df.merge(
    service_notes_df,
    left_on='care_plan_id',
    right_on='service_request_id',
    how='outer'
)

# All columns preserved with clear origins:
# cp_period_start, sr_occurrence_date_time, cpn_note_text, srn_note_text
```

### 3. Self-Documenting CSVs
When users open CSVs in Excel/Pandas:
- Immediately see which FHIR resource each field comes from
- Understand date field differences without documentation
- Know which fields can be correlated

### 4. Analysis Clarity
```python
# Clear which dates to use for timeline
timeline = pd.concat([
    care_plan_df[['cp_period_start', 'cpn_note_type']].rename(
        columns={'cp_period_start': 'date', 'cpn_note_type': 'event'}
    ),
    service_notes_df[['sr_occurrence_date_time', 'srn_note_type']].rename(
        columns={'sr_occurrence_date_time': 'date', 'srn_note_type': 'event'}
    )
])
```

---

## Prefix Reference Table

| Prefix | Resource | Table | Example Columns |
|--------|----------|-------|-----------------|
| `cp_` | care_plan | Parent | status, intent, title, period_start, period_end |
| `cpn_` | care_plan_note | Child | note_text, contains_dose, note_type |
| `cppo_` | care_plan_part_of | Child | part_of_reference |
| `sr_` | service_request | Parent | intent, status, authored_on, occurrence_date_time, occurrence_period_start/end |
| `srn_` | service_request_note | Child | note_text, note_time, author_display, contains_dose, note_type |
| `srrc_` | service_request_reason_code | Child | reason_code, reason_display, reason_system, reason_text, num_codings |

---

## Updated Extraction Files

### Modified Functions
1. `extract_care_plan_notes()`:
   - Query aliases: `cp_*`, `cpn_*`
   - Filtering: Updated to use `cpn_note_text`
   - Derived columns: `cpn_contains_dose`, `cpn_note_type`

2. `extract_care_plan_hierarchy()`:
   - Query aliases: `cp_*`, `cppo_*`
   - Primary output unchanged (hierarchy relationships)

3. `extract_service_request_notes()`:
   - Query aliases: `sr_*`, `srn_*`
   - Filtering: Updated to use `srn_note_text`
   - Derived columns: `srn_contains_dose`, `srn_note_type`

4. `extract_service_request_reason_codes()`:
   - Query aliases: `sr_*`, `srrc_*`
   - Filtering: Updated to use `srrc_reason_code_coding`, `srrc_reason_code_text`
   - DataFrame construction: All columns prefixed

### Summary Statistics
Updated to reference new column names:
- `care_plan_notes_df['cpn_contains_dose']`
- `service_request_notes_df['srn_contains_dose']`

---

## Migration Notes

### Breaking Changes
All column names have changed. Scripts that read extraction CSVs will need updates:

**Before**:
```python
df['note_text']
df['period_start']
df['occurrence_date_time']
```

**After**:
```python
df['cpn_note_text']  # or df['srn_note_text']
df['cp_period_start']
df['sr_occurrence_date_time']
```

### Backward Compatibility
None - this is a breaking change. All downstream scripts must be updated.

### Testing Required
- Run extraction on RT patient
- Verify all CSV files have prefixed columns
- Check summary statistics compute correctly
- Validate date-based merges work as expected

---

## Future Enhancements

### Consistent Naming Across All Resources
Consider extending this prefix pattern to:
- `appt_` for appointment fields
- `apptst_` for appointment_service_type fields
- `proc_` for procedure fields
- `med_` for medication fields

### Standardized Date Handling
Create helper functions:
```python
def get_best_date(row, resource_prefix):
    """Extract best available date for a resource."""
    if resource_prefix == 'sr':
        return row['sr_occurrence_date_time'] or row['sr_occurrence_period_start'] or row['sr_authored_on']
    elif resource_prefix == 'cp':
        return row['cp_period_start']
    # etc.
```

---

## Summary

✅ **care_plan** columns now prefixed: `cp_`, `cpn_`, `cppo_`
✅ **service_request** columns now prefixed: `sr_`, `srn_`, `srrc_`
✅ **Date columns** clearly labeled by resource
✅ **RT keywords** updated to include rad-onc/radonc variants
✅ **Self-documenting** CSV outputs with clear provenance

**Result**: Clear data lineage, easier analysis, unambiguous date handling
