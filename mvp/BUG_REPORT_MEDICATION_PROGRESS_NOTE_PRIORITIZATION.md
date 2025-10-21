# BUG REPORT: Progress Note Prioritization Fails to Find Medication-Proximate Notes

**Date:** 2025-10-20
**Severity:** CRITICAL
**Component:** Progress Note Prioritization
**File:** `/mvp/utils/progress_note_prioritization.py`
**Method:** `_find_notes_around_medication_changes()`

---

## EXECUTIVE SUMMARY

The progress note prioritizer reports **0 post-medication-change notes** despite Athena database verification confirming **35 oncology progress notes exist within ±7 days of 17 medication start dates** for patient `e4BwD8ZYDBccepXcJ.Ilo3w3`.

This is a critical bug that prevents the workflow from identifying clinically important progress notes documenting baseline assessment and treatment response around chemotherapy/targeted therapy initiation.

---

## EVIDENCE

### 1. Workflow Output
```
INFO:utils.progress_note_prioritization:Prioritizing 660 progress notes based on clinical events
INFO:utils.progress_note_prioritization:Prioritized 15 progress notes from 660 total notes
INFO:utils.progress_note_prioritization:  Post-surgery: 1
INFO:utils.progress_note_prioritization:  Post-imaging: 13
INFO:utils.progress_note_prioritization:  Post-medication-change: 0  ❌
INFO:utils.progress_note_prioritization:  Final note: 1
```

### 2. Medication Events Confirmed
Timeline database query confirms **19 chemotherapy/targeted therapy events** (17 unique dates):
```
2021-05-20 | Targeted Therapy | selumetinib cap
2021-08-25 | Targeted Therapy | selumetinib cap
2021-11-11 | Chemotherapy     | KOSELUGO 10 MG
2021-11-21 | Targeted Therapy | selumetinib cap
2022-01-09 | Chemotherapy     | TRIAMCINOLONE ACETONIDE
2022-02-28 | Chemotherapy     | KOSELUGO 10 MG
2022-05-12 | Targeted Therapy | selumetinib cap
2022-09-07 | Chemotherapy     | KOSELUGO 10 MG
2022-11-03 | Chemotherapy     | KOSELUGO 10 MG
2023-04-14 | Chemotherapy     | KOSELUGO 10 MG
2023-06-20 | Targeted Therapy | selumetinib cap (2 events)
2023-08-10 | Targeted Therapy | selumetinib cap
2023-12-06 | Targeted Therapy | selumetinib cap (2 events)
2024-01-02 | Chemotherapy     | KOSELUGO 10 MG
2024-02-02 | Targeted Therapy | selumetinib cap
2024-06-04 | Chemotherapy     | KOSELUGO 10 MG
2024-07-09 | Targeted Therapy | selumetinib cap
```

**Source:** DuckDB query on `data/timeline.duckdb`
```sql
SELECT event_date, event_category, description
FROM events
WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND event_type = 'Medication'
    AND event_category IN ('Chemotherapy', 'Targeted Therapy')
```

### 3. Athena Verification: 35 Matching Notes Found

Independent Athena query with **identical oncology filtering logic** found **35 oncology progress notes within ±7 days**:

```
Med Date        | Note Date       | Days  | Type
----------------|--------------------|-------|-------------
2021-05-20      | 2021-05-14      | -6    | Progress Notes
2021-05-20      | 2021-05-17      | -3    | Progress Notes
2021-05-20      | 2021-05-21      | 1     | Progress Notes (3x)
2021-08-25      | 2021-09-01      | 7     | Progress Notes
2021-11-11      | 2021-11-04      | -7    | Progress Notes
2021-11-11      | 2021-11-10      | -1    | Progress Notes
2021-11-11      | 2021-11-15      | 4     | Progress Notes (3x)
2021-11-21      | 2021-11-15      | -6    | Progress Notes (3x)
2021-11-21      | 2021-11-22      | 1     | Progress Notes
2022-01-09      | 2022-01-03      | -6    | Progress Notes
2022-01-09      | 2022-01-13      | 4     | Progress Notes
2022-05-12      | 2022-05-09      | -3    | Progress Notes (2x)
2022-05-12      | 2022-05-13      | 1     | Progress Notes (4x)
2022-05-12      | 2022-05-19      | 7     | Progress Notes
2022-09-07      | 2022-09-12      | 5     | Progress Notes
2022-11-03      | 2022-11-06      | 3     | Progress Notes
2022-11-03      | 2022-11-09      | 6     | Progress Notes
2023-06-20      | 2023-06-26      | 6     | Progress Notes
2023-08-10      | 2023-08-10      | 0     | Progress Notes ⭐ SAME DAY
2023-08-10      | 2023-08-11      | 1     | Progress Notes
2024-02-02      | 2024-02-02      | 0     | Progress Notes ⭐ SAME DAY
2024-07-09      | 2024-07-09      | 0     | Progress Notes ⭐ SAME DAY
2024-07-09      | 2024-07-10      | 1     | Progress Notes
2024-07-09      | 2024-07-16      | 7     | Progress Notes (2x)
```

**Source:** Athena query on `fhir_prd_db.v_binary_files`
**Verification Script:** `/mvp/scripts/verify_oncology_medication_notes.py`

### 4. Same-Day Medication Start Notes

**3 progress notes exist on the EXACT SAME DAY as medication starts:**
- 2023-08-10: Medication start + progress note (0 days difference)
- 2024-02-02: Medication start + progress note (0 days difference)
- 2024-07-09: Medication start + progress note (0 days difference)

These should be the **highest priority** post-medication-change notes (baseline assessment), yet the prioritizer finds **0**.

---

## ROOT CAUSE ANALYSIS

### Data Flow Confirmation

1. ✅ **Medication Events Retrieved:** 19 events successfully queried from timeline database
2. ✅ **Progress Notes Retrieved:** 999 total notes from Athena → 660 oncology-filtered notes
3. ✅ **Oncology Filtering Applied:** `filter_oncology_notes()` correctly reduces to 660 notes
4. ✅ **Data Passed to Prioritizer:** Both medication_changes and oncology_notes passed to `note_prioritizer.prioritize_notes()`
5. ❌ **Date Matching FAILS:** `_find_notes_around_medication_changes()` returns empty list

### Suspected Root Causes

#### Hypothesis 1: Date Format Mismatch
**Medication dates** come from DuckDB as `datetime.date` objects:
```python
# From run_full_multi_source_abstraction.py:413-417
for _, row in chemo_events_df.iterrows():
    medication_changes.append({
        'change_date': row['event_date'],  # datetime.date from DuckDB
        'medication_id': row['event_id']
    })
```

**Progress note dates** come from Athena as TIMESTAMP(3):
```python
# From v_binary_files schema
dr_date TIMESTAMP(3)  # Millisecond precision timestamp
```

**Status of Previous Fix:**
- We added `datetime.date` handling to `_parse_date()` at line 304-305
- However, this may not be applied consistently across all comparison points

#### Hypothesis 2: Date Comparison Logic Error
The `_find_notes_around_medication_changes()` method (lines 238-276) performs date comparisons:
```python
# Line 256 (AFTER our fix):
if event_date <= note_date <= window_end:
```

**Potential issues:**
- `event_date` may be `datetime.date` while `note_date` is `datetime`
- Python date/datetime comparison has strict type requirements
- Comparison may fail silently or return False for type mismatches

#### Hypothesis 3: Medication Changes Not Being Processed
The prioritizer may not be iterating through medication_changes correctly:
```python
# From progress_note_prioritization.py:238-276
def _find_notes_around_medication_changes(...)
```

**Need to verify:**
- Is the medication_changes list actually being iterated?
- Are any exceptions being silently caught?
- Is the window calculation correct?

---

## DEBUGGING STEPS COMPLETED

1. ✅ Verified medication filtering works (19 events found)
2. ✅ Verified ChemotherapyFilter integration successful
3. ✅ Verified SQL query finds both Chemotherapy AND Targeted Therapy
4. ✅ Verified DuckDB lock fix working (no lock errors)
5. ✅ Verified oncology note filtering reduces 999 → 660 notes
6. ✅ Verified Athena has 35 matching notes within ±7 days
7. ✅ Verified same-day medication start notes exist (3 cases)
8. ✅ Verified date parsing fix for `datetime.date` objects added

---

## PROPOSED FIX STRATEGY

### Step 1: Add Comprehensive Debug Logging
Add logging to `_find_notes_around_medication_changes()` to trace:
- Number of medication_changes received
- Each medication date being processed
- Number of notes checked for each medication
- Actual date comparisons being made
- Any type mismatches detected

### Step 2: Normalize All Dates to datetime
Ensure consistent date type handling:
```python
def _normalize_to_datetime(self, date_value):
    """Convert any date format to datetime for consistent comparison"""
    if isinstance(date_value, datetime):
        return date_value
    if isinstance(date_value, date):
        return datetime.combine(date_value, datetime.min.time())
    if isinstance(date_value, str):
        # Parse string dates
        ...
    return None
```

### Step 3: Add Type Checking in Comparisons
Add explicit type checking before date comparisons:
```python
if not isinstance(event_date, datetime) or not isinstance(note_date, datetime):
    self.logger.warning(f"Type mismatch: event_date={type(event_date)}, note_date={type(note_date)}")
    continue
```

### Step 4: Create Unit Test
Create test case with known medication date and progress note:
```python
def test_same_day_medication_note():
    """Test that note on same day as medication is found"""
    medication_changes = [{
        'change_date': datetime(2023, 8, 10),
        'medication_id': 'med_123'
    }]

    notes = [{
        'dr_date': datetime(2023, 8, 10, 14, 30, 0),
        'document_reference_id': 'note_123'
    }]

    result = prioritizer._find_notes_around_medication_changes(
        notes, medication_changes, days_before=7, days_after=7
    )

    assert len(result) == 1  # Should find the same-day note
```

### Step 5: Verify Fix
Run verification script and confirm:
- All 3 same-day notes found
- All 35 notes within ±7 days found
- Workflow output shows `Post-medication-change: 35` (or similar)

---

## IMPACT ASSESSMENT

### Clinical Impact
**HIGH** - Failure to identify medication-proximate progress notes means:
- Missing baseline clinical assessments before treatment start
- Missing treatment response documentation after initiation
- Incomplete clinical timeline for patient abstraction
- Potential data quality issues in downstream analysis

### Workflow Impact
**MEDIUM** - Current workflow still processes:
- Post-imaging notes (13 found)
- Post-surgery notes (1 found)
- Final note (1 found)

But missing medication-based prioritization reduces clinical comprehensiveness.

### Patient Count Impact
**UNKNOWN** - This bug affects patient `e4BwD8ZYDBccepXcJ.Ilo3w3`. Need to assess:
- How many patients have medication events in timeline?
- How many would have post-medication-change notes if bug fixed?
- What percentage of patients are affected?

---

## FILES REQUIRING CHANGES

1. **Primary Fix:**
   - `/mvp/utils/progress_note_prioritization.py` (lines 238-276, 304-310)

2. **Testing:**
   - Create: `/mvp/tests/test_medication_note_prioritization.py`

3. **Verification:**
   - Existing: `/mvp/scripts/verify_oncology_medication_notes.py` (already created)

---

## NEXT STEPS

1. **Immediate:** Add debug logging to identify exact failure point
2. **Short-term:** Implement date normalization fix
3. **Medium-term:** Create comprehensive unit tests
4. **Long-term:** Audit all date comparisons in codebase for type consistency

---

## RELATED ISSUES

- **DuckDB Lock Fix:** Resolved (2025-10-20) - Added `timeline.close()` after queries
- **Same-Day Note Matching Fix:** Partially resolved (2025-10-20) - Changed `<` to `<=` but still not working
- **Date Parsing Fix:** Partially resolved (2025-10-20) - Added `datetime.date` handling but incomplete

---

## REPRODUCTION

To reproduce this bug:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# 1. Query medication dates from timeline
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb', read_only=True)
result = conn.execute(\"\"\"
    SELECT COUNT(*) FROM events
    WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND event_category IN ('Chemotherapy', 'Targeted Therapy')
\"\"\").fetchone()
print(f'Medication events: {result[0]}')
"

# 2. Verify Athena has matching notes
export AWS_PROFILE=radiant-prod
python3 scripts/verify_oncology_medication_notes.py

# 3. Run workflow and observe output
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    | grep "Post-medication-change"

# Expected: Post-medication-change: 35 (or similar)
# Actual: Post-medication-change: 0
```

---

**Report prepared by:** Claude Code
**Verification scripts:** Available in `/mvp/scripts/`
**Status:** OPEN - Awaiting fix implementation
