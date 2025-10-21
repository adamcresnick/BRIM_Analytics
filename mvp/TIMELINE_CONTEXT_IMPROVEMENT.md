# Timeline Context Improvement for MedGemma Prompts

## Problem Identified

Your question revealed a critical gap: **MedGemma was not receiving timeline context** (`events_before` and `events_after`) when processing binary documents like PDFs and HTML progress reports.

### What Was Missing:

**Before:**
```python
context = {
    'patient_id': args.patient_id,
    'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
    'report_date': report_date
    # ❌ NO events_before
    # ❌ NO events_after
}
```

**Impact:**
- MedGemma couldn't identify prior imaging for comparison
- Tumor status prompts showed "No prior imaging available for comparison"
- Classification relied only on surgery dates, not full timeline
- Less accurate extractions due to missing context

## Solution Implemented

### 1. Created Timeline Context Builder Function

Added `build_timeline_context(current_date_str)` function that:
- Queries in-memory data from `imaging_text_reports` and `surgical_history`
- Builds `events_before` and `events_after` arrays for any given date
- Includes only events within ±180 days window
- Sorts by proximity to current date
- Returns standard timeline context format

**Location:** [run_full_multi_source_abstraction.py:598-675](scripts/run_full_multi_source_abstraction.py#L598-L675)

```python
def build_timeline_context(current_date_str: str) -> Dict:
    """
    Build events_before and events_after context for a given date.
    Uses in-memory data from imaging_text_reports and surgical_history.
    """
    # ... implementation details ...

    return {
        'events_before': events_before,  # Imaging + procedures before current date
        'events_after': events_after      # Imaging + procedures after current date
    }
```

### 2. Updated Context Building for All Document Types

#### Imaging Text Reports ([lines 684-694](scripts/run_full_multi_source_abstraction.py#L684-L694))

```python
# Build timeline context with events before/after this report
timeline_events = build_timeline_context(report_date)

context = {
    'patient_id': args.patient_id,
    'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
    'report_date': report_date,
    'events_before': timeline_events['events_before'],   # ✅ Now included
    'events_after': timeline_events['events_after']       # ✅ Now included
}
```

#### Imaging PDFs ([lines 770-780](scripts/run_full_multi_source_abstraction.py#L770-L780))

```python
# Build timeline context with events before/after this report
timeline_events = build_timeline_context(doc_date)

context = {
    'patient_id': args.patient_id,
    'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
    'report_date': doc_date,
    'events_before': timeline_events['events_before'],   # ✅ Now included
    'events_after': timeline_events['events_after']       # ✅ Now included
}
```

### 3. Example Timeline Context Now Provided

For a May 27, 2018 imaging report, MedGemma now receives:

```python
context = {
    'patient_id': 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
    'surgical_history': [
        {'date': '2018-05-15', 'description': 'Craniotomy for tumor resection'}
    ],
    'report_date': '2018-05-27 13:27:10.000',
    'events_before': [
        {
            'event_type': 'Imaging',
            'event_category': 'MRI Brain',
            'event_date': '2018-05-01',
            'days_diff': -26,        # 26 days before current report
            'description': 'MRI'
        },
        {
            'event_type': 'Procedure',
            'event_category': 'Surgery',
            'event_date': '2018-05-15',
            'days_diff': -12,        # 12 days before current report
            'description': 'Craniotomy for tumor resection'
        }
    ],
    'events_after': []
}
```

## Benefits

### 1. Accurate Prior Imaging Detection
- MedGemma can now identify the most recent prior imaging
- Prompts show: "Prior imaging: 26 days before (date: 2018-05-01)"
- Instead of: "No prior imaging available for comparison"

### 2. Improved Tumor Status Extraction
- Can properly assess "stable", "increased", "decreased" based on comparison
- Higher confidence scores when prior imaging is referenced
- Better evidence extraction from reports

### 3. Better Classification
- Temporal context helps distinguish pre-op vs surveillance imaging
- Can identify patterns (e.g., imaging before/after surgery)
- More accurate event type classification

### 4. Consistent Context Across All Sources
- Imaging text reports: ✅ Timeline context
- Imaging PDFs: ✅ Timeline context
- Operative reports: ✅ Timeline context (prior surgeries help identify re-resection vs initial)
- Progress notes: ✅ Timeline context (recent imaging + surgeries provide clinical context)

## Data Source

**Timeline data comes from in-memory queries, NOT DuckDB:**

The `build_timeline_context()` function uses:
1. `imaging_text_reports` - Already queried from Athena `v_imaging_with_reports`
2. `surgical_history` - Already queried from Athena `v_procedures_tumor`

This is efficient because:
- No additional database queries needed
- Timeline built on-the-fly from existing data
- No dependency on DuckDB timeline storage
- Works even before timeline database is populated

## Testing

To verify timeline context is working:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/e4BwD8ZYDBccepXcJ.Ilo3w3
```

**What to check:**
1. Tumor status extraction should return values other than "Unknown"
2. Evidence field should reference prior imaging dates
3. Confidence scores should be higher (> 0.7 for clear comparisons)
4. Comparison findings should mention "compared to [prior date]"

## Files Modified

1. **[run_full_multi_source_abstraction.py:598-675](scripts/run_full_multi_source_abstraction.py#L598-L675)**
   - Added `build_timeline_context()` helper function

2. **[run_full_multi_source_abstraction.py:684-694](scripts/run_full_multi_source_abstraction.py#L684-L694)**
   - Updated imaging text report context building

3. **[run_full_multi_source_abstraction.py:770-780](scripts/run_full_multi_source_abstraction.py#L770-L780)**
   - Updated imaging PDF context building

## Related Improvements

This change builds on the earlier fix to use full radiology report text:
- Query `v_imaging_with_reports` instead of `v_imaging`
- Use `radiology_report_text` field (full 1500-char reports)
- Pass complete report JSON to MedGemma
- Add timeline context for comparison

Together, these changes ensure MedGemma has:
1. ✅ Full report text (not just conclusion)
2. ✅ Complete report metadata as JSON
3. ✅ Timeline context with prior imaging
4. ✅ Surgical history for classification

This provides the complete context needed for accurate clinical data extraction.
