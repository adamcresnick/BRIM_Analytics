# FIX STRATEGY: Medication Progress Note Prioritization Bug

**Bug Report:** [BUG_REPORT_MEDICATION_PROGRESS_NOTE_PRIORITIZATION.md](./BUG_REPORT_MEDICATION_PROGRESS_NOTE_PRIORITIZATION.md)
**Date:** 2025-10-20
**Status:** DEBUG LOGGING ADDED - Ready for testing

---

## CHANGES MADE

### 1. Added Comprehensive Debug Logging

**File:** `/mvp/utils/progress_note_prioritization.py`

**Lines 160-171:** Added logging to medication change loop
```python
logger.info(f"Processing {len(medication_changes)} medication changes for note prioritization")
for idx, med_change in enumerate(medication_changes, 1):
    raw_change_date = med_change.get('change_date')
    logger.debug(f"Med change {idx}/{len(medication_changes)}: raw_date={raw_change_date} (type={type(raw_change_date).__name__})")

    change_date = self._parse_date(raw_change_date)
    logger.info(f"Med change {idx}: Searching for notes around {change_date.date()} (parsed from {raw_change_date})")
```

**Lines 180, 201:** Added search result logging
```python
logger.debug(f"Med change {idx}: Pre-med search result: {pre_med_change_note is not None}")
logger.debug(f"Med change {idx}: Post-med search result: {post_med_change_note is not None}")
```

**Lines 265-283:** Added detailed type checking and comparison logging
```python
logger.debug(f"_find_first_note_after_event: event_date={event_date} (type={type(event_date).__name__})")

if not isinstance(event_date, datetime) or not isinstance(note_date, datetime):
    logger.warning(f"TYPE MISMATCH: event_date is {type(event_date).__name__}, note_date is {type(note_date).__name__}")

if event_date <= note_date <= window_end:
    logger.debug(f"MATCH FOUND: note_date={note_date.date()}, days_from_event={days_from_event}")
```

---

## EXPECTED DEBUG OUTPUT

When the workflow runs, we should now see log entries like:

### If Working Correctly:
```
INFO:utils.progress_note_prioritization:Processing 19 medication changes for note prioritization
INFO:utils.progress_note_prioritization:Med change 1: Searching for notes around 2021-05-20
DEBUG:utils.progress_note_prioritization:_find_first_note_after_event: event_date=2021-05-20 00:00:00 (type=datetime)
DEBUG:utils.progress_note_prioritization:MATCH FOUND: note_date=2021-05-21, days_from_event=1
DEBUG:utils.progress_note_prioritization:Med change 1: Post-med search result: True
DEBUG:utils.progress_note_prioritization:Added post-medication-change note: 1 days after change
...
INFO:utils.progress_note_prioritization:  Post-medication-change: 35
```

### If Type Mismatch Issue:
```
INFO:utils.progress_note_prioritization:Med change 1: Searching for notes around 2021-05-20
DEBUG:utils.progress_note_prioritization:Med change 1/19: raw_date=2021-05-20 (type=date)
WARNING:utils.progress_note_prioritization:TYPE MISMATCH: event_date is date, note_date is datetime
```

### If Date Parsing Fails:
```
WARNING:utils.progress_note_prioritization:Med change 1: Failed to parse date from 2021-05-20
```

---

## NEXT STEPS

### Step 1: Run Workflow with Debug Logging

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Kill any running workflows
pkill -f "run_full_multi_source_abstraction.py"

# Run with debug logging
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    > /tmp/DEBUG_MED_PRIORITIZATION.log 2>&1

# Check for debug messages
grep -A 5 "Processing.*medication changes" /tmp/DEBUG_MED_PRIORITIZATION.log
grep "TYPE MISMATCH" /tmp/DEBUG_MED_PRIORITIZATION.log
grep "MATCH FOUND" /tmp/DEBUG_MED_PRIORITIZATION.log
```

### Step 2: Analyze Debug Output

Based on what we see in the logs:

**Scenario A: Type Mismatch Found**
- Issue: `datetime.date` vs `datetime` comparison
- Fix: Normalize all dates to `datetime` before comparison
- Implementation: Update `_parse_date()` to always return `datetime`

**Scenario B: Dates Not Being Parsed**
- Issue: `_parse_date()` returning `None`
- Fix: Add more robust date parsing logic
- Implementation: Handle `datetime.date` objects from DuckDB

**Scenario C: No Matches Found Despite Correct Types**
- Issue: Logic error in comparison
- Fix: Review window calculation or comparison operators
- Implementation: Add sample date debugging

### Step 3: Implement Root Cause Fix

Once we identify the issue from debug logs, implement the appropriate fix:

#### Fix Option 1: Normalize Dates in _parse_date()
```python
def _parse_date(self, date_value: Any) -> Optional[datetime]:
    """Parse date ensuring datetime type for consistent comparison"""
    if date_value is None:
        return None

    # Already datetime - return as-is
    if isinstance(date_value, datetime):
        return date_value

    # datetime.date from DuckDB - convert to datetime at midnight
    if isinstance(date_value, date):
        return datetime.combine(date_value, datetime.min.time())

    # String parsing...
    if isinstance(date_value, str):
        # Try pandas
        try:
            parsed = pd.to_datetime(date_value)
            return parsed.to_pydatetime() if hasattr(parsed, 'to_pydatetime') else parsed
        except:
            pass

        # Try ISO format
        try:
            return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
        except:
            pass

    logger.warning(f"Could not parse date from {date_value} (type={type(date_value).__name__})")
    return None
```

#### Fix Option 2: Type Checking Before Comparison
```python
def _find_first_note_after_event(self, notes_with_dates, event_date, window_days):
    """Find first note after event with type-safe comparison"""

    # Ensure event_date is datetime
    if isinstance(event_date, date) and not isinstance(event_date, datetime):
        event_date = datetime.combine(event_date, datetime.min.time())

    window_end = event_date + timedelta(days=window_days)

    for note, note_date in notes_with_dates:
        # Ensure note_date is datetime
        if isinstance(note_date, date) and not isinstance(note_date, datetime):
            note_date = datetime.combine(note_date, datetime.min.time())

        if event_date <= note_date <= window_end:
            days_from_event = (note_date - event_date).days
            return {'note': note, 'days_from_event': days_from_event}

    return None
```

### Step 4: Create Unit Test

```python
# /mvp/tests/test_medication_note_prioritization.py

import pytest
from datetime import datetime, date
from utils.progress_note_prioritization import ProgressNotePrioritizer

def test_same_day_medication_note_with_date_object():
    """Test that datetime.date from DuckDB is handled correctly"""
    prioritizer = ProgressNotePrioritizer()

    # Medication change with datetime.date (from DuckDB)
    medication_changes = [{
        'change_date': date(2023, 8, 10),  # DuckDB returns date objects
        'medication_id': 'med_123'
    }]

    # Progress note with datetime (from Athena TIMESTAMP)
    notes = [{
        'dr_date': datetime(2023, 8, 10, 14, 30, 0),
        'document_reference_id': 'note_123',
        'dr_type_text': 'Progress Notes'
    }]

    result = prioritizer.prioritize_notes(
        progress_notes=notes,
        medication_changes=medication_changes
    )

    # Should find 1 post-medication-change note
    post_med_notes = [n for n in result if n.priority_reason == 'post_medication_change']
    assert len(post_med_notes) == 1
    assert post_med_notes[0].days_from_event == 0  # Same day

def test_medication_notes_within_7_days():
    """Test finding notes within ±7 day window"""
    prioritizer = ProgressNotePrioritizer()

    medication_changes = [{
        'change_date': date(2024, 7, 9),
        'medication_id': 'med_456'
    }]

    notes = [
        {'dr_date': datetime(2024, 7, 2, 10, 0), 'document_reference_id': 'too_early', 'dr_type_text': 'Progress Notes'},
        {'dr_date': datetime(2024, 7, 9, 10, 0), 'document_reference_id': 'same_day', 'dr_type_text': 'Progress Notes'},
        {'dr_date': datetime(2024, 7, 10, 10, 0), 'document_reference_id': 'next_day', 'dr_type_text': 'Progress Notes'},
        {'dr_date': datetime(2024, 7, 16, 10, 0), 'document_reference_id': 'day_7', 'dr_type_text': 'Progress Notes'},
        {'dr_date': datetime(2024, 7, 17, 10, 0), 'document_reference_id': 'too_late', 'dr_type_text': 'Progress Notes'},
    ]

    result = prioritizer.prioritize_notes(
        progress_notes=notes,
        medication_changes=medication_changes
    )

    post_med_notes = [n for n in result if n.priority_reason == 'post_medication_change']

    # Should find same_day, next_day, or day_7 (first match)
    assert len(post_med_notes) >= 1
    assert post_med_notes[0].note['document_reference_id'] in ['same_day', 'next_day', 'day_7']
```

### Step 5: Verify Fix

```bash
# Run unit tests
pytest /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/tests/test_medication_note_prioritization.py -v

# Run full workflow
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    | grep "Post-medication-change"

# Expected: Post-medication-change: 35 (or similar)

# Run Athena verification
python3 scripts/verify_oncology_medication_notes.py

# Compare workflow output with Athena results
```

---

## SUCCESS CRITERIA

✅ Debug logs show medication changes are being processed
✅ No TYPE MISMATCH warnings in logs
✅ MATCH FOUND messages appear for known same-day notes
✅ Workflow output shows `Post-medication-change: 35` (or similar positive number)
✅ Unit tests pass
✅ Athena verification matches workflow output

---

## ROLLBACK PLAN

If the fix causes issues:

1. The debug logging can remain (it's informational only)
2. Revert any date normalization changes to `_parse_date()`
3. Revert any type checking changes to comparison functions
4. Document the specific failure mode for further investigation

---

## FILES MODIFIED

1. ✅ `/mvp/utils/progress_note_prioritization.py` - Added debug logging
2. ⏳ `/mvp/utils/progress_note_prioritization.py` - Will add date normalization fix (pending debug results)
3. ⏳ `/mvp/tests/test_medication_note_prioritization.py` - Will create (pending)

---

## DOCUMENTATION UPDATES NEEDED

After fix is verified:

1. Update [COMPREHENSIVE_SYSTEM_DOCUMENTATION.md](./COMPREHENSIVE_SYSTEM_DOCUMENTATION.md) with date handling requirements
2. Add note to [ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md](./ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md) about TIMESTAMP(3) handling
3. Update changelog with bug fix details
4. Document test cases in testing documentation

---

**Ready for Step 1:** Run workflow with debug logging enabled
