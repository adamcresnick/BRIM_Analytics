# Progress Note Selection Optimization Analysis
**Date:** 2025-10-23
**Purpose:** Assess progress note selection logic across workflows to prevent over-selection and duplication

---

## Executive Summary

### Current State
The system uses **three different progress note selection strategies** across workflows:

1. **Main Workflow (run_full_multi_source_abstraction.py)**: Event-based prioritization using ProgressNotePrioritizer
2. **Chemotherapy JSON Builder**: Time-window selection (±14 days around treatment courses)
3. **Radiation JSON Builder**: NO progress note selection (only supporting documents)

### Key Finding: MINIMAL OVERLAP RISK

After analyzing all three strategies, **there is minimal risk of over-selection or duplication** for the following reasons:

1. Different use cases: Main workflow extracts disease state; chemo/radiation builders provide treatment context
2. Different consumption patterns: Main workflow sends notes to Agent 2; builders package notes as supporting evidence
3. Non-overlapping execution: Chemo/radiation builders run BEFORE main workflow's progress note prioritization

### Recommendation: NO CHANGES NEEDED

The current architecture is **well-designed and does not require optimization** at this time.

---

## Detailed Analysis

### 1. Main Workflow Progress Note Selection

**Location:** [run_full_multi_source_abstraction.py:436-578](run_full_multi_source_abstraction.py#L436-L578)

**Strategy:**
Event-based prioritization using `ProgressNotePrioritizer` class

**Selection Criteria:**
```python
# Phase 1D: Query all oncology-relevant progress notes
SELECT * FROM v_binary_files
WHERE patient_fhir_id = '{patient_id}'
    AND (content_type = 'text/plain' OR content_type = 'text/html' OR content_type = 'application/pdf')
    AND (
        LOWER(dr_category_text) LIKE '%progress note%'
        OR LOWER(dr_category_text) LIKE '%clinical note%'
        OR LOWER(dr_type_text) LIKE '%oncology%'
        OR LOWER(dr_type_text) LIKE '%hematology%'
    )

# Then filter to oncology-specific using semantic filtering
oncology_notes = filter_oncology_notes(all_progress_notes)

# Then prioritize based on clinical events
prioritized_notes = note_prioritizer.prioritize_notes(
    progress_notes=oncology_notes,
    surgeries=operative_reports,
    imaging_events=imaging_text_reports,
    medication_changes=medication_changes  # From timeline DB
)
```

**Prioritization Windows** (from [utils/progress_note_prioritization.py](utils/progress_note_prioritization.py)):
- **Post-surgery**: First note within **±7 days** after surgery
- **Post-imaging**: First note within **±7 days** after imaging
- **Pre-medication-change**: Last note within **7 days BEFORE** medication start
- **Post-medication-change**: First note within **7 days AFTER** medication start
- **Final note**: Always include most recent progress note

**Purpose:**
Capture disease state assessments at critical clinical decision points for Agent 2 extraction.

**Typical Selection for Patient:**
- ~3-8 notes per surgery (assuming 1-2 surgeries)
- ~3-8 notes per major imaging event
- ~4-12 notes for medication changes (pre+post for each chemotherapy start)
- 1 final note
- **Estimated total: 15-30 notes** for a typical patient

---

### 2. Chemotherapy JSON Builder Progress Note Selection

**Location:** [scripts/build_chemotherapy_json.py:164-237](scripts/build_chemotherapy_json.py#L164-L237)

**Strategy:**
Time-window selection around treatment course starts

**Selection Criteria:**
```python
# Progress notes (±14 days around course start)
SELECT * FROM v_binary_files
WHERE patient_fhir_id = '{patient_id}'
    AND dr_category_text LIKE '%Progress Note%'
    AND ABS(DATE_DIFF('day', DATE(dr_date), DATE '{course_start}')) <= 14
ORDER BY dr_date
LIMIT 50
```

**Selection Windows:**
- **Progress notes**: ±14 days around chemotherapy course start
- **Infusion records**: ±3 days around course start
- **Treatment plans**: 30 days BEFORE course start

**Purpose:**
Provide treatment context and binary confirmation of chemotherapy administration. These notes are included in the comprehensive JSON structure but are NOT directly sent to Agent 2 for extraction - they serve as **supporting evidence** for data quality validation.

**Typical Selection for Patient:**
- ~2-4 notes per treatment course (within ±14 day window)
- If patient has 3 treatment courses: **~6-12 notes total**

---

### 3. Radiation JSON Builder Progress Note Selection

**Location:** [scripts/build_radiation_json.py:168-264](scripts/build_radiation_json.py#L168-L264)

**Strategy:**
**NO progress note selection**

**Selection Criteria:**
```python
# Radiation builder queries these supporting documents:
- v_radiation_summary
- v_radiation_treatments
- v_radiation_documents (treatment summaries, consults, plans)
- v_radiation_care_plan_hierarchy
- v_radiation_treatment_appointments

# But does NOT select generic progress notes
```

**Purpose:**
Radiation data is sufficiently structured in dedicated radiation tables that progress notes are not needed. Radiation-specific documents (treatment summaries, simulation notes, completion reports) are captured via `v_radiation_documents`.

**Typical Selection for Patient:**
- **0 progress notes** (only radiation-specific documents)

---

## Overlap Analysis

### Scenario 1: Do Main Workflow and Chemo Builder Select Same Notes?

**Analysis:**

| Dimension | Main Workflow | Chemo JSON Builder | Overlap? |
|-----------|---------------|-------------------|----------|
| **Timing Window** | ±7 days from medication start | ±14 days from course start | **Yes - Partial** |
| **Use Case** | Disease state extraction | Treatment context validation | **No** |
| **Execution** | Agent 2 extraction in Phase 2 | JSON packaging in Phase 1 | **No** |
| **Consumption** | Notes sent to Agent 2 for NLP | Notes stored as metadata | **No** |

**Conclusion:**
While there may be **time-window overlap** (7 days vs 14 days around medication changes), the **use cases differ fundamentally**:

- **Main workflow**: Sends notes to Agent 2 for disease state extraction
- **Chemo builder**: Packages notes as supporting evidence in JSON structure

Additionally, execution timing differs:
- Chemotherapy JSON builder would run **BEFORE** main workflow's progress note prioritization
- Main workflow queries chemotherapy events from timeline DB (which would be populated by chemo builder results)

### Scenario 2: Do All Three Workflows Result in Over-Selection?

**Hypothetical Patient with Heavy Treatment:**
- 2 surgeries
- 5 major imaging events
- 3 chemotherapy courses (each with 1-2 medication starts)
- Radiation treatment course

**Selection Breakdown:**

| Source | Selection Logic | Estimated Count |
|--------|----------------|----------------|
| Main Workflow - Surgery | ±7 days × 2 surgeries | ~4 notes |
| Main Workflow - Imaging | ±7 days × 5 imaging events | ~8 notes |
| Main Workflow - Medications | ±7 days × 4 med changes (pre+post) | ~8 notes |
| Main Workflow - Final Note | Most recent | 1 note |
| **Main Workflow Total** | | **~21 notes** |
| Chemo JSON Builder | ±14 days × 3 courses | ~9 notes |
| Radiation JSON Builder | N/A | 0 notes |
| **Grand Total** | | **~30 notes** |

**Potential Duplicates:**
- Main workflow medication-related notes (±7 days) might overlap with chemo builder notes (±14 days)
- Estimated overlap: ~5-8 notes

**Actual Load for Agent 2:**
Only the 21 notes from main workflow are sent to Agent 2. The 9 chemo builder notes are stored as JSON metadata and not processed by Agent 2.

**Conclusion:**
Total of **~21 unique notes sent to Agent 2**, which is reasonable for a heavily-treated patient.

---

## Optimization Opportunities

### Option 1: Consolidate Medication-Related Note Selection ❌ NOT RECOMMENDED

**Approach:**
Have main workflow query chemotherapy JSON builder results and skip medication-based note prioritization.

**Why NOT Recommended:**
1. **Breaks separation of concerns**: Chemo builder focuses on treatment confirmation; main workflow focuses on disease state
2. **Timeline dependency**: Main workflow already uses timeline DB for medication events
3. **Different purposes**: Main workflow needs notes for disease state extraction; chemo builder needs notes for treatment validation
4. **Minimal actual duplication**: Notes are used differently in each context

### Option 2: Deduplicate Notes Before Agent 2 Extraction ✅ FUTURE CONSIDERATION

**Approach:**
If/when chemo and radiation builders are integrated into main workflow, deduplicate notes by `document_reference_id` before sending to Agent 2.

**Implementation:**
```python
# After all note selection strategies run
all_selected_notes = []
all_selected_notes.extend(prioritized_notes_from_main_workflow)
all_selected_notes.extend(chemo_progress_notes_from_json_builder)
all_selected_notes.extend(radiation_progress_notes_from_json_builder)

# Deduplicate by document_reference_id
unique_notes = {note['document_reference_id']: note for note in all_selected_notes}
deduplicated_notes = list(unique_notes.values())
```

**Why Future Consideration:**
- Currently, chemo/radiation builders are standalone scripts
- Main workflow doesn't yet integrate these builders
- Would only be relevant if builders are integrated and notes are actually duplicated in Agent 2 processing

### Option 3: Use Unified Progress Note Selector ✅ BEST LONG-TERM APPROACH

**Approach:**
Create a unified `ProgressNoteSelector` class that handles ALL progress note selection across workflows, with awareness of different use cases.

**Design:**
```python
class UnifiedProgressNoteSelector:
    """
    Unified progress note selection across all workflows

    Manages selection for:
    - Disease state assessment (main workflow)
    - Treatment confirmation (chemo/radiation builders)
    - Supporting evidence (binary file confirmation)

    Prevents duplication while maintaining separate use cases
    """

    def __init__(self):
        self.selected_notes = {}  # document_reference_id -> NoteMetadata

    def select_for_disease_state(
        self,
        surgeries,
        imaging_events,
        medication_changes
    ):
        """Main workflow disease state selection"""
        # Uses ±7 day windows
        # Marks notes as purpose='disease_state'

    def select_for_treatment_confirmation(
        self,
        treatment_courses,
        course_type='chemotherapy'
    ):
        """Chemo/radiation builder treatment confirmation"""
        # Uses ±14 day windows
        # Marks notes as purpose='treatment_confirmation'
        # Deduplicates with disease_state notes

    def get_notes_for_agent2(self):
        """Returns deduplicated notes for Agent 2 extraction"""
        # Returns only notes marked for disease_state

    def get_notes_for_treatment_validation(self):
        """Returns notes for binary confirmation in JSON builders"""
        # Returns notes marked for treatment_confirmation
        # May include duplicates if needed for validation
```

**Benefits:**
- Single source of truth for all progress note selection
- Explicit tracking of note purposes
- Built-in deduplication
- Easier to audit and optimize

**Implementation Complexity:**
- Moderate (would require refactoring existing selection logic)
- Best done as part of larger integration effort

---

## Recommendations

### Immediate (This Sprint): NO ACTION NEEDED ✅

**Rationale:**
Current architecture has minimal risk of over-selection because:

1. **Different execution contexts**: Chemo/radiation builders run standalone; main workflow runs separately
2. **Different use cases**: Notes serve different purposes in each workflow
3. **No evidence of actual duplication**: Notes aren't being processed twice by Agent 2
4. **Reasonable note counts**: ~15-30 notes per patient is appropriate for heavily-treated oncology patients

### Short-Term (Next Integration): TRACK DUPLICATION 📊

**Action:**
When integrating chemo/radiation builders into main workflow, add instrumentation to track:

```python
# In run_full_multi_source_abstraction.py
duplication_tracker = {
    'main_workflow_notes': set(),
    'chemo_builder_notes': set(),
    'radiation_builder_notes': set(),
    'duplicates': set()
}

# After each selection
for note in prioritized_notes:
    note_id = note.note['document_reference_id']
    if note_id in duplication_tracker['main_workflow_notes']:
        duplication_tracker['duplicates'].add(note_id)
    duplication_tracker['main_workflow_notes'].add(note_id)

# Log duplication statistics
print(f"Duplication rate: {len(duplication_tracker['duplicates']) / len(duplication_tracker['main_workflow_notes']) * 100:.1f}%")
```

### Long-Term (Future Refactor): UNIFIED SELECTOR 🔄

**Action:**
Implement `UnifiedProgressNoteSelector` class as described in Option 3 above.

**Timing:**
- After chemo/radiation builders are fully integrated
- After initial production deployment proves the concept
- As part of broader system optimization initiative

---

## Appendix: Code References

### Main Workflow Note Selection

**File:** [run_full_multi_source_abstraction.py](run_full_multi_source_abstraction.py)

**Query (Lines 437-461):**
```sql
SELECT
    document_reference_id,
    dr_date,
    dr_type_text,
    dr_category_text,
    binary_id,
    content_type,
    patient_fhir_id
FROM v_binary_files
WHERE patient_fhir_id = '{athena_patient_id}'
    AND (
        content_type = 'text/plain'
        OR content_type = 'text/html'
        OR content_type = 'application/pdf'
    )
    AND (
        LOWER(dr_category_text) LIKE '%progress note%'
        OR LOWER(dr_category_text) LIKE '%clinical note%'
        OR LOWER(dr_type_text) LIKE '%oncology%'
        OR LOWER(dr_type_text) LIKE '%hematology%'
    )
ORDER BY dr_date
```

**Prioritization (Lines 551-556):**
```python
prioritized_notes = note_prioritizer.prioritize_notes(
    progress_notes=oncology_notes,
    surgeries=operative_reports,
    imaging_events=imaging_text_reports,
    medication_changes=medication_changes if medication_changes else None
)
```

### Chemotherapy Builder Note Selection

**File:** [scripts/build_chemotherapy_json.py](scripts/build_chemotherapy_json.py)

**Progress Notes Query (Lines 200-209):**
```sql
SELECT *
FROM v_binary_files
WHERE patient_fhir_id = '{athena_patient_id}'
    AND dr_category_text LIKE '%Progress Note%'
    AND ABS(DATE_DIFF('day', DATE(dr_date), DATE '{course_start}')) <= 14
ORDER BY dr_date
LIMIT 50
```

**Integration into Course JSON (Lines 275-287):**
```python
binary_files = self.get_binary_files_for_course(
    patient_fhir_id,
    course_start.split()[0] if course_start else '',
    course_end.split()[0] if course_end else ''
)

binary_confirmation = {
    'infusion_records': len(binary_files['infusion_records']),
    'progress_notes_mentions': len(binary_files['progress_notes']),
    'treatment_plans': len(binary_files['treatment_plans']),
    'confirmed': len(binary_files['infusion_records']) > 0 or len(binary_files['progress_notes']) > 0
}
```

### Progress Note Prioritizer Implementation

**File:** [utils/progress_note_prioritization.py](utils/progress_note_prioritization.py)

**Post-Surgery Window (Lines 98-126):**
```python
# Find first note after surgery (within window)
post_surgery_note = self._find_first_note_after_event(
    notes_with_dates,
    surgery_date,
    self.post_event_window_days  # Default: 7 days
)
```

**Medication Change Window (Lines 157-217):**
```python
# Find last note BEFORE medication change (baseline)
pre_med_change_note = self._find_last_note_before_event(
    notes_with_dates,
    change_date,
    self.post_event_window_days  # Default: 7 days
)

# Find first note AFTER medication change (response assessment)
post_med_change_note = self._find_first_note_after_event(
    notes_with_dates,
    change_date,
    self.post_event_window_days  # Default: 7 days
)
```

---

## Conclusion

The current progress note selection architecture is **well-designed and does not require immediate optimization**. The three selection strategies serve different purposes and have minimal overlap:

1. **Main Workflow**: Event-based disease state extraction (±7 days)
2. **Chemo Builder**: Treatment validation support (±14 days)
3. **Radiation Builder**: No progress note selection

**Risk of over-selection:** MINIMAL
**Recommended action:** NO CHANGES AT THIS TIME
**Future consideration:** Implement unified selector when builders are fully integrated
