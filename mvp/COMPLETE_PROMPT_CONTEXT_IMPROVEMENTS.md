# Complete MedGemma Prompt and Context Improvements

## Summary of All Changes

This document consolidates ALL improvements made to ensure MedGemma receives complete report data and full timeline context for accurate clinical data extraction.

---

## Problem 1: MedGemma Only Saw Summary Fields, Not Full Reports

### Issue
- Querying `v_imaging` which only has `report_conclusion` (often NULL)
- MedGemma was NOT seeing the actual 1500-character radiology reports
- All tumor status extractions returned "Unknown" with 0.0 confidence

### Solution
1. **Query correct view**: Changed from `v_imaging` to `v_imaging_with_reports`
2. **Use correct field**: Access `radiology_report_text` instead of `report_conclusion`
3. **Pass complete data**: Send entire report dict as JSON to MedGemma

**Files Modified:**
- [run_full_multi_source_abstraction.py:368-380](scripts/run_full_multi_source_abstraction.py#L368-L380) - Query changes
- [extraction_prompts.py:16-98](agents/extraction_prompts.py#L16-L98) - Imaging classification prompt
- [extraction_prompts.py:291-344](agents/extraction_prompts.py#L291-L344) - Tumor status prompt

---

## Problem 2: MedGemma Missing Timeline Context

### Issue
- Context dict only had `patient_id`, `surgical_history`, `report_date`
- **Missing** `events_before` and `events_after` arrays
- MedGemma couldn't identify prior imaging for comparison
- Prompts showed "No prior imaging available for comparison"

### Solution
1. **Created timeline builder**: `build_timeline_context(current_date_str)` function
2. **Updated all extractions**: Pass timeline context to imaging, operative, and progress notes
3. **In-memory data source**: Uses existing Athena query results (no additional DB queries)

**Files Modified:**
- [run_full_multi_source_abstraction.py:598-675](scripts/run_full_multi_source_abstraction.py#L598-L675) - Timeline context builder
- [run_full_multi_source_abstraction.py:684-694](scripts/run_full_multi_source_abstraction.py#L684-L694) - Imaging text context
- [run_full_multi_source_abstraction.py:770-780](scripts/run_full_multi_source_abstraction.py#L770-L780) - Imaging PDF context
- [run_full_multi_source_abstraction.py:908-916](scripts/run_full_multi_source_abstraction.py#L908-L916) - Operative report context
- [run_full_multi_source_abstraction.py:1005-1013](scripts/run_full_multi_source_abstraction.py#L1005-L1013) - Progress note context

---

## Comprehensive Prompt Updates

### 1. Imaging Classification Prompt ([extraction_prompts.py:16-98](agents/extraction_prompts.py#L16-L98))

**Added:**
- Complete report JSON block
- Flexible field name lookups (supports multiple field naming conventions)
- Full radiology report text section

**Example Output:**
```
**COMPLETE REPORT DATA (JSON):**
```json
{
  "diagnostic_report_id": "...",
  "imaging_date": "2018-05-27",
  "imaging_modality": "MRI Brain",
  "radiology_report_text": "FULL 1500-CHAR REPORT HERE",
  "patient_fhir_id": "..."
}
```

**RADIOLOGY REPORT TEXT:**
[Full report text for easy reading]
```

### 2. Tumor Status Extraction Prompt ([extraction_prompts.py:291-344](agents/extraction_prompts.py#L291-L344))

**Added:**
- Timeline context showing prior imaging
- Complete report JSON block
- Full radiology report text section
- Flexible field name lookups

**Example Output:**
```
**IMAGING INFORMATION:**
Current imaging date: 2018-05-27
Comparison: Prior imaging: 26 days before (date: 2018-05-01)

**COMPLETE REPORT DATA (JSON):**
[Full report dict]

**RADIOLOGY REPORT TEXT:**
[Full 1500-char report]
```

### 3. Operative Report EOR Prompt ([extraction_prompts.py:230-282](agents/extraction_prompts.py#L230-L282))

**Added:**
- Surgical timeline (prior surgeries)
- Complete operative report JSON block
- Helps identify re-resection vs initial resection

**Example Output:**
```
**SURGICAL TIMELINE (prior surgeries):**
- Craniotomy for tumor resection: 90 days before (date: 2018-02-15)

**COMPLETE OPERATIVE REPORT DATA (JSON):**
[Full operative report dict]

**OPERATIVE NOTE TEXT:**
[Full operative note text]
```

### 4. Progress Note Disease State Prompt ([extraction_prompts.py:442-510](agents/extraction_prompts.py#L442-L510))

**Added:**
- Clinical timeline (recent imaging + surgeries)
- Complete progress note JSON block
- Context for understanding disease state changes

**Example Output:**
```
**CLINICAL TIMELINE (context for this assessment):**
Recent Imaging:
  - MRI Brain: 7 days before (date: 2018-05-20)
  - MRI Brain: 90 days before (date: 2018-02-15)
Surgical History:
  - Craniotomy for tumor resection: 12 days before (date: 2018-05-15)

**COMPLETE PROGRESS NOTE DATA (JSON):**
[Full progress note dict]

**PROGRESS NOTE TEXT:**
[Full progress note text]
```

---

## Timeline Context Implementation Details

### Function: `build_timeline_context(current_date_str)`

**Location:** [run_full_multi_source_abstraction.py:598-675](scripts/run_full_multi_source_abstraction.py#L598-L675)

**What it does:**
1. Takes a document date as input
2. Queries in-memory `imaging_text_reports` and `surgical_history`
3. Builds `events_before` and `events_after` arrays
4. Filters to ±180 day window
5. Sorts by proximity to current date
6. Returns standard timeline context dict

**Returns:**
```python
{
    'events_before': [
        {
            'event_type': 'Imaging',
            'event_category': 'MRI Brain',
            'event_date': '2018-05-01',
            'days_diff': -26,  # 26 days before current
            'description': 'MRI'
        },
        {
            'event_type': 'Procedure',
            'event_category': 'Surgery',
            'event_date': '2018-05-15',
            'days_diff': -12,  # 12 days before current
            'description': 'Craniotomy for tumor resection'
        }
    ],
    'events_after': []  # Events after current date
}
```

**Performance:**
- No additional database queries
- Uses existing in-memory data from Athena
- O(n) complexity where n = number of imaging reports + surgeries
- Cached surgical_history built once at workflow start

---

## Data Flow for Each Document Type

### Imaging Text Reports

1. **Query Athena** → `v_imaging_with_reports` (includes `radiology_report_text`)
2. **For each report**:
   - Build timeline context from in-memory data
   - Pass complete report dict + timeline context to prompts
   - MedGemma extracts classification + tumor status

### Imaging PDFs

1. **Query Athena** → `v_binary_files` (PDF metadata)
2. **Extract text** → BinaryFileAgent extracts full PDF text
3. **For each PDF**:
   - Build timeline context
   - Create report dict with `radiology_report_text` and `document_text`
   - Pass complete report dict + timeline context to prompts

### Operative Reports

1. **Query Athena** → `v_procedures_tumor` (surgery metadata)
2. **Find operative notes** → Query `v_binary_files` for linked operative notes
3. **Extract text** → BinaryFileAgent extracts operative note text
4. **For each operative report**:
   - Build timeline context (shows prior surgeries)
   - Create operative report dict with all metadata
   - Pass complete report dict + timeline context to EOR extraction prompt

### Progress Notes

1. **Query Athena** → `v_binary_files` (progress note metadata)
2. **Prioritize notes** → ProgressNotePrioritizer reduces 1486 → 57 notes
3. **Extract text** → BinaryFileAgent extracts note text
4. **For each progress note**:
   - Build timeline context (shows recent imaging + surgeries)
   - Create progress note dict with all metadata
   - Pass complete note dict + timeline context to disease state prompt

---

## Benefits Summary

### 1. Full Report Text Access
- ✅ MedGemma sees complete 1500-char radiology reports (not just conclusions)
- ✅ All metadata fields available as JSON
- ✅ Higher extraction accuracy from complete data

### 2. Timeline-Aware Extraction
- ✅ Can identify prior imaging for comparison
- ✅ Understands surgical history context
- ✅ Better classification (pre-op vs surveillance vs post-op)
- ✅ Higher confidence scores when timeline context supports findings

### 3. Consistent Data Format
- ✅ All prompts use same pattern: JSON block + text block + timeline
- ✅ Flexible field name lookups work with different schemas
- ✅ Complete report dicts prevent data loss

### 4. No Performance Impact
- ✅ Timeline built from in-memory data (no extra DB queries)
- ✅ Surgical history pre-computed once
- ✅ Efficient O(n) timeline building

---

## Testing Verification

Run the full workflow and verify improvements:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/e4BwD8ZYDBccepXcJ.Ilo3w3
```

**Expected results:**

1. **Tumor Status Extraction**:
   - Should return values other than "Unknown"
   - Confidence scores > 0.7 for clear comparisons
   - Evidence field references prior imaging dates
   - Comparison findings mention "compared to [prior date]"

2. **EOR Extraction**:
   - Should identify if this is re-resection vs initial surgery
   - Contextual understanding of surgical history
   - More accurate classification

3. **Progress Note Disease State**:
   - Should correlate with recent imaging findings
   - Reference recent surgical events
   - More clinically coherent assessments

4. **Classification**:
   - Accurate pre-op vs post-op vs surveillance distinction
   - Based on full timeline, not just nearest surgery

---

## Complete File Change Summary

### Modified Files:

1. **[scripts/run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py)**
   - Lines 368-380: Query `v_imaging_with_reports` instead of `v_imaging`
   - Lines 598-675: Added `build_timeline_context()` function
   - Lines 684-694: Imaging text - added timeline context
   - Lines 762-780: Imaging PDF - added timeline context + full report dict
   - Lines 896-920: Operative report - added timeline context + full report dict
   - Lines 994-1017: Progress note - added timeline context + full note dict

2. **[agents/extraction_prompts.py](agents/extraction_prompts.py)**
   - Lines 16-98: Updated `build_imaging_classification_prompt()` - added JSON block + flexible fields
   - Lines 230-282: Updated `build_operative_report_eor_extraction_prompt()` - added surgical timeline + JSON block
   - Lines 291-344: Updated `build_tumor_status_extraction_prompt()` - added timeline + JSON block
   - Lines 442-510: Updated `build_progress_note_disease_state_prompt()` - added clinical timeline + JSON block

### Created Documentation:

1. **[example_actual_prompt.md](example_actual_prompt.md)**
   - Shows actual prompt text sent to MedGemma
   - Demonstrates the problem and solution
   - Includes example outputs

2. **[PROMPT_IMPROVEMENT_SUMMARY.md](PROMPT_IMPROVEMENT_SUMMARY.md)**
   - Documents the full report text fix
   - Shows before/after for v_imaging query

3. **[TIMELINE_CONTEXT_IMPROVEMENT.md](TIMELINE_CONTEXT_IMPROVEMENT.md)**
   - Documents timeline context addition
   - Explains in-memory data source
   - Shows example timeline context

4. **[COMPLETE_PROMPT_CONTEXT_IMPROVEMENTS.md](COMPLETE_PROMPT_CONTEXT_IMPROVEMENTS.md)** (this file)
   - Comprehensive summary of all changes
   - End-to-end data flow documentation
   - Testing verification guide

---

## Clinical Impact

These improvements ensure MedGemma can make clinically accurate assessments by providing:

1. **Complete Clinical Documentation** - Full radiology reports, not summaries
2. **Temporal Context** - Understanding of disease progression over time
3. **Surgical Context** - Knowledge of prior interventions
4. **Multi-Source Correlation** - Can relate imaging findings to surgical outcomes and clinical assessments

This enables the two-agent workflow (Agent 1 orchestration + Agent 2 extraction) to function as designed, with Agent 1 able to detect temporal inconsistencies and Agent 2 able to make accurate extractions with full context.
