# MedGemma Prompt Improvements - Complete Report Data

## Problem Identified

The tumor status extraction was returning "Unknown" for all 82 imaging reports because:

1. **Wrong view**: Workflow was querying `v_imaging` which only has `report_conclusion` (often NULL or brief)
2. **Wrong field**: Should be using `radiology_report_text` from `v_imaging_with_reports` (contains full report, avg 1500 chars)
3. **Selective data**: Only passing specific fields to MedGemma, not the complete report

## Solution Implemented

### 1. Query the Correct View

**Changed from:**
```sql
SELECT
    diagnostic_report_id,
    imaging_date,
    imaging_modality,
    report_conclusion,  -- Often NULL or minimal text
    patient_fhir_id
FROM v_imaging
```

**Changed to:**
```sql
SELECT
    imaging_procedure_id as diagnostic_report_id,
    imaging_date,
    imaging_modality,
    radiology_report_text,  -- Full report text (avg 1500 chars)
    report_conclusion,
    patient_fhir_id
FROM v_imaging_with_reports
```

### 2. Pass Complete Report as JSON

**Previous approach** (selective fields):
```python
report = {
    'document_text': report_raw.get('radiology_report_text', ''),
    'document_date': report_date,
    'metadata': {
        'imaging_modality': report_raw.get('imaging_modality', '')
    }
}
```

**New approach** (complete report):
```python
# Pass entire report dict directly - no transformation needed
report = report_raw  # Contains ALL fields from Athena query
```

### 3. Updated Prompt Functions

Both `build_imaging_classification_prompt()` and `build_tumor_status_extraction_prompt()` now:

1. **Accept flexible field names** with fallbacks:
```python
report_text = report.get('document_text', report.get('radiology_report_text', ''))
imaging_date = report.get('document_date', report.get('imaging_date', 'Unknown'))
modality = report.get('metadata', {}).get('imaging_modality', report.get('imaging_modality', 'Unknown'))
```

2. **Include complete report JSON** in prompt:
```python
import json
report_json = json.dumps(report, indent=2, default=str)

prompt = f"""
**COMPLETE REPORT DATA (JSON):**
```json
{report_json}
```

**RADIOLOGY REPORT TEXT:**
{report_text}
"""
```

## Benefits

1. **Complete context**: MedGemma sees ALL available fields from the report
2. **No data loss**: Don't have to guess which fields are important
3. **Flexible**: Works with different report formats (text vs PDF)
4. **Transparent**: Easy to see exactly what MedGemma receives
5. **Future-proof**: New fields automatically available without code changes

## Expected Results

With full radiology report text now available, MedGemma should be able to:

1. **Extract tumor status** from comparison statements in reports
2. **Identify measurements** (e.g., "3.2 x 2.8 cm, previously 3.1 x 2.7 cm")
3. **Detect keywords** like "stable", "increased", "decreased", "NED"
4. **Parse enhancement patterns** and tumor characteristics
5. **Return appropriate confidence scores** based on available evidence

## Files Modified

1. **[run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py:368-380)**
   - Changed query from `v_imaging` to `v_imaging_with_reports`
   - Added `radiology_report_text` field
   - Removed report transformation (pass raw dict)

2. **[extraction_prompts.py](agents/extraction_prompts.py:16-98)**
   - Updated `build_imaging_classification_prompt()` to include complete report JSON
   - Added fallback field name lookups
   - Import json module

3. **[extraction_prompts.py](agents/extraction_prompts.py:291-344)**
   - Updated `build_tumor_status_extraction_prompt()` to include complete report JSON
   - Added fallback field name lookups
   - Import json module

## Testing

To verify the fix:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/e4BwD8ZYDBccepXcJ.Ilo3w3
```

Expected output:
- Tumor status should return values other than "Unknown"
- Confidence scores should be > 0.0
- Evidence field should contain actual report excerpts
- Measurements should be extracted where available
