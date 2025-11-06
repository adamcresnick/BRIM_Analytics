# V4.6 Architectural Gap Fixes - Implementation Summary

**Date**: 2025-11-05
**Context**: Continuation session - implementing architectural gaps identified in design document review

---

## Executive Summary

Implementing 4 critical architectural gaps that were identified by comparing V4.6 implementation against design documentation:

1. ✅ **Gap #1 (PARTIAL)**: Investigation Engine for Phase 4.5 gap-filling failures
2. ⏳ **Gap #2**: Treatment change reason computation
3. ⏳ **Gap #3**: related_events relationship enrichment
4. ⏳ **Gap #5**: RANO response assessment extraction

---

## Gap #1: Investigation Engine Integration (HIGH PRIORITY) 🔴

### Problem
When Phase 4.5 gap-filling encounters "No source documents available", it gives up immediately. This happens because:
- MedGemma extraction fails validation in Phase 4
- `source_document_ids` never populated on events
- Gap-filling has no documents to work with
- Investigation Engine NOT triggered to find alternatives

### Solution Implemented
**File**: `orchestration/investigation_engine.py`
**Lines**: 427-517

Added new method `investigate_gap_filling_failure()` that suggests alternative document sources:

```python
def investigate_gap_filling_failure(self, gap_type: str, event: Dict, reason: str) -> Dict:
    """
    V4.6 GAP #1: Investigate why gap-filling failed.

    Suggests alternatives like:
    - radiation_dose: Use v_radiation_documents with extraction_priority
    - surgery_eor: Use v_document_reference_enriched with encounter lookup
    - imaging_conclusion: Use structured DiagnosticReport.conclusion field
    """
```

**File**: `scripts/patient_timeline_abstraction_V3.py`
**Lines**: 5491-5536

Modified `_fill_single_gap()` to trigger Investigation Engine:

```python
if not source_docs:
    logger.warning(f"⚠️  No source documents available for gap-filling")

    # GAP #1 FIX: Trigger Investigation Engine
    if self.investigation_engine:
        investigation = self.investigation_engine.investigate_gap_filling_failure(...)

        if investigation and investigation.get('suggested_alternatives'):
            for alt in alternatives[:3]:
                alt_docs = self._try_alternative_document_source(alt, event, gap_type)
                if alt_docs:
                    source_docs = alt_docs
                    break
```

### What's Still Needed

**CRITICAL**: Implement `_try_alternative_document_source()` method that executes Investigation Engine suggestions:

```python
def _try_alternative_document_source(self, alternative: Dict, event: Dict, gap_type: str) -> List[str]:
    """
    V4.6 GAP #1: Execute Investigation Engine's suggested alternative document source.

    Args:
        alternative: Dict with 'method', 'description', 'confidence'
        event: The event missing data
        gap_type: Type of gap (radiation_dose, surgery_eor, imaging_conclusion)

    Returns:
        List of document IDs found via alternative method, or []
    """
    method = alternative.get('method')

    if method == 'v_radiation_documents_priority':
        # Query v_radiation_documents with extraction_priority ORDER BY
        return self._query_radiation_documents_by_priority(event)

    elif method == 'structured_conclusion':
        # Use DiagnosticReport.conclusion from v2_imaging.result_information
        return self._get_imaging_structured_conclusion(event)

    elif method == 'v_document_reference_enriched':
        # Use encounter-based document discovery
        return self._query_document_reference_enriched(event)

    elif method == 'expand_temporal_window':
        # Expand from ±30 days to ±60 days
        return self._query_documents_expanded_window(event, gap_type)

    return []
```

Then implement each helper method:

1. `_query_radiation_documents_by_priority()` - Already have similar code in Phase 4, lines 3440-3461
2. `_get_imaging_structured_conclusion()` - Extract from v2_imaging.result_information
3. `_query_document_reference_enriched()` - Query new view with encounter linkage
4. `_query_documents_expanded_window()` - Retry temporal matching with wider window

### Expected Impact
- Gap-filling success rate: **0% → 60-80%**
- Radiation dose extraction: **0/3 → 2-3/3**
- Surgery EOR extraction: **0/3 → 1-2/3**
- Imaging conclusion extraction: **0/59 → 40-50/59**

---

## Gap #2: Treatment Change Reason (MEDIUM PRIORITY) 🟡

### Problem
Timeline events show `treatment_line: 2` but NOT `reason_for_change_from_prior: "progression"`.

Cannot automatically identify:
- Progression-driven treatment changes
- Toxicity-driven treatment changes
- Planned completion vs early discontinuation

### Solution Design

**File**: `lib/treatment_ordinality.py` (existing)
**New Method**: `_compute_treatment_change_reason()`

```python
def _compute_treatment_change_reason(self, current_line_events, prior_line_events, timeline):
    """
    GAP #2: Determine why treatment changed from prior line to current line.

    Logic:
    1. Find imaging between prior_line.end_date and current_line.start_date
    2. Check for progression keywords: "increased", "new lesions", "progression"
    3. Check for toxicity keywords in clinical notes
    4. Check for "completion" keywords

    Returns:
        "progression" | "toxicity" | "completion" | "unclear"
    """
    interim_imaging = [e for e in timeline
                       if e['event_type'] == 'imaging'
                       and prior_line_end < e['event_date'] < current_line_start]

    # Check for progression
    for img in interim_imaging:
        if 'progression' in img.get('report_conclusion', '').lower():
            return 'progression'
        if 'increased' in img.get('report_conclusion', '').lower():
            return 'progression'
        if 'new lesion' in img.get('report_conclusion', '').lower():
            return 'progression'

    # Check for toxicity (requires clinical notes extraction)
    # ...

    return 'unclear'
```

### Implementation Location
Add to Phase 2.5 in `scripts/patient_timeline_abstraction_V3.py` after ordinality assignment.

### Expected Impact
- Enables progression-free survival (PFS) calculation
- Enables treatment efficacy analysis
- Required for Gap #4 (radiation protocol validation)

---

## Gap #3: related_events Enrichment (MEDIUM PRIORITY) 🟡

### Problem
Events have `relationships: { ordinality: {...} }` but missing `related_events: { postop_imaging: [...], preop_imaging: [...] }`.

Cannot easily query "show me all postop imaging for surgery #2".

### Solution Design

**File**: `scripts/patient_timeline_abstraction_V3.py`
**New Method**: `_enrich_event_relationships()` (Phase 2.5b)

```python
def _enrich_event_relationships(self):
    """
    V4.6 GAP #3: Populate related_events for cross-event linkage.

    For each surgery:
    - Find imaging ±7 days → preop_imaging, postop_imaging
    - Find pathology reports with matching specimen_id

    For each chemotherapy_start:
    - Find corresponding chemotherapy_end
    - Find response imaging (first imaging >30 days after chemo end)

    For each radiation_start:
    - Find corresponding radiation_end
    - Find simulation imaging (imaging ±7 days before rad start)
    """
    for event in self.timeline_events:
        if 'relationships' not in event:
            event['relationships'] = {}

        if event['event_type'] == 'surgery':
            event['relationships']['related_events'] = {
                'preop_imaging': self._find_imaging_before(event, days=7),
                'postop_imaging': self._find_imaging_after(event, days=7),
                'pathology_reports': self._find_pathology_for_surgery(event)
            }

        elif event['event_type'] == 'chemotherapy_start':
            event['relationships']['related_events'] = {
                'chemotherapy_end': self._find_chemo_end(event),
                'response_imaging': self._find_response_imaging(event)
            }

        elif event['event_type'] == 'radiation_start':
            event['relationships']['related_events'] = {
                'radiation_end': self._find_radiation_end(event),
                'simulation_imaging': self._find_simulation_imaging(event)
            }
```

Helper methods:
```python
def _find_imaging_before(self, surgery_event, days=7):
    surgery_date = datetime.fromisoformat(surgery_event['event_date'])
    window_start = surgery_date - timedelta(days=days)

    imaging_events = [e for e in self.timeline_events
                      if e['event_type'] == 'imaging'
                      and window_start <= datetime.fromisoformat(e['event_date']) < surgery_date]

    return [e['event_id'] for e in imaging_events]

def _find_imaging_after(self, surgery_event, days=7):
    surgery_date = datetime.fromisoformat(surgery_event['event_date'])
    window_end = surgery_date + timedelta(days=days)

    imaging_events = [e for e in self.timeline_events
                      if e['event_type'] == 'imaging'
                      and surgery_date < datetime.fromisoformat(e['event_date']) <= window_end]

    return [e['event_id'] for e in imaging_events]
```

### Implementation Location
Add Phase 2.5b after `_assign_treatment_ordinality()` in Phase 2.

### Expected Impact
- Enables EOR Orchestrator to find postop imaging automatically
- Enables response assessment queries
- Required for treatment efficacy analysis

---

## Gap #5: RANO Response Assessment (LOW PRIORITY) 🟢

### Problem
Imaging events loaded from v2_imaging but no extraction of:
- `rano_assessment`: CR | PR | SD | PD
- `progression_flag`: progression_suspected | recurrence_suspected
- `response_flag`: response_suspected | stable_disease | complete_response_suspected

Cannot automatically detect progression for PFS calculation.

### Solution Design

**File**: `scripts/patient_timeline_abstraction_V3.py`
**Modification**: Extend Phase 4 imaging extraction

Add MedGemma imaging extraction with RANO schema:

```python
imaging_extraction_schema = {
    "rano_assessment": "CR | PR | SD | PD | Not Applicable",
    "change_from_prior": "increased | decreased | stable | new_lesions | not_stated",
    "new_lesions": "yes | no | unclear",
    "lesions": [
        {
            "location": "string",
            "max_diameter_mm": "number",
            "description": "string"
        }
    ],
    "radiologist_impression": "string (free text conclusion)"
}
```

Add keyword-based classification as fallback:

```python
def _classify_imaging_response(self, report_text: str) -> Dict:
    """
    V4.6 GAP #5: Classify imaging response using RANO keywords.

    Returns:
        {
            'rano_assessment': 'PD' | 'SD' | 'PR' | 'CR' | None,
            'progression_flag': 'progression_suspected' | None,
            'response_flag': 'response_suspected' | 'stable_disease' | None
        }
    """
    text_lower = report_text.lower()

    # Progression indicators
    progression_keywords = ['increased', 'enlarging', 'expansion', 'growth', 'worsen',
                            'progression', 'new enhancement', 'new lesion', 'recurrence']
    if any(kw in text_lower for kw in progression_keywords):
        return {
            'rano_assessment': 'PD',
            'progression_flag': 'progression_suspected',
            'response_flag': None
        }

    # Response indicators
    response_keywords = ['decreased', 'reduction', 'shrinkage', 'smaller', 'improvement', 'resolving']
    if any(kw in text_lower for kw in response_keywords):
        return {
            'rano_assessment': 'PR',
            'progression_flag': None,
            'response_flag': 'response_suspected'
        }

    # Stable disease
    stable_keywords = ['stable', 'unchanged', 'no change', 'no significant change']
    if any(kw in text_lower for kw in stable_keywords):
        return {
            'rano_assessment': 'SD',
            'progression_flag': None,
            'response_flag': 'stable_disease'
        }

    return {'rano_assessment': None, 'progression_flag': None, 'response_flag': None}
```

### Implementation Location
1. Add to Phase 4 imaging gap-filling (lines 5587-5620)
2. Add keyword classification to Phase 1 when loading v2_imaging (lines 2300-2400)

### Expected Impact
- Enables automatic progression detection
- Enables PFS calculation
- Enables treatment response analysis
- Foundation for RANO-compliant reporting

---

## Implementation Priority

Based on architectural impact and current gap-filling failure rate:

1. **IMMEDIATE** 🔴: Complete Gap #1 (`_try_alternative_document_source` + helper methods)
2. **SHORT-TERM** 🟡: Gap #3 (related_events enrichment) - enables EOR orchestrator improvements
3. **SHORT-TERM** 🟡: Gap #2 (treatment change reason) - enables efficacy analysis
4. **FUTURE** 🟢: Gap #5 (RANO assessment) - nice-to-have for progression detection

---

## Testing Plan

After implementing each gap:

1. **Gap #1 Test**:
   ```bash
   python3 scripts/patient_timeline_abstraction_V3.py \
     --patient-id ekrJf9m27ER1umcVah.rRqC.9hDY9ch91PfbuGjUHko03 \
     --output-dir output/v46_gap1_test \
     --max-extractions 5
   ```
   **Expected**: Gap-filling success rate >50% (currently 0%)

2. **Gap #2 Test**: Check timeline JSON for `reason_for_change_from_prior` field on chemotherapy events

3. **Gap #3 Test**: Check timeline JSON for `relationships.related_events.postop_imaging` on surgery events

4. **Gap #5 Test**: Check timeline JSON for `rano_assessment` and `progression_flag` on imaging events

---

## Files Modified

### Completed:
- ✅ `orchestration/investigation_engine.py` (lines 427-517)
- ✅ `scripts/patient_timeline_abstraction_V3.py` (lines 5491-5536)

### To Be Modified:
- ⏳ `scripts/patient_timeline_abstraction_V3.py` - Add `_try_alternative_document_source()` and helpers
- ⏳ `lib/treatment_ordinality.py` - Add `_compute_treatment_change_reason()`
- ⏳ `scripts/patient_timeline_abstraction_V3.py` - Add `_enrich_event_relationships()` and helpers
- ⏳ `scripts/patient_timeline_abstraction_V3.py` - Add `_classify_imaging_response()`

---

## Next Steps

**Immediate** (Session continuation):
1. Implement `_try_alternative_document_source()` method
2. Implement 4 helper methods for alternative document sources
3. Test Gap #1 fix with `--max-extractions 5`
4. If successful, proceed to Gaps #2, #3, #5

**Follow-up** (Next session):
1. Analyze Gap #1 test results
2. Refine Investigation Engine suggestions based on actual success rates
3. Implement remaining gaps based on priority

---

**Implementation Status**: 25% Complete (1/4 gaps partially implemented)
**Estimated Remaining Work**: 2-3 hours for full implementation + testing
