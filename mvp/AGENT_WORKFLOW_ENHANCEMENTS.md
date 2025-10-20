# Agent 1 ↔ Agent 2 Workflow Enhancements

## Summary

Enhanced the multi-agent clinical data extraction framework to properly implement the Agent 1 (Claude) ↔ Agent 2 (MedGemma) architecture with clear separation of responsibilities.

**Date:** 2025-10-20

---

## Architecture Clarification

### Agent 1 (Claude) - Orchestrator & Adjudicator
- Gathers multi-source data from Athena
- Sends targeted extraction requests to Agent 2
- Adjudicates conflicts across sources
- Classifies event_type based on surgical history
- Iteratively queries Agent 2 for clarification
- Documents all decisions in patient QA reports

### Agent 2 (MedGemma) - Targeted Extractor
- Extracts variables from documents provided by Agent 1
- Returns structured JSON with confidence scores
- Responds to Agent 1's clarification queries
- **Does NOT** perform cross-source reconciliation (Agent 1's job)

---

## New Components Created

### 1. Agent 2 Extraction Prompts

**File:** `agents/extraction_prompts.py`

#### Operative Report EOR Extraction (`build_operative_report_eor_extraction_prompt`)
- **Purpose:** Extract extent of resection from operative notes (GOLD STANDARD)
- **Categories:**
  - Gross Total Resection / Near Total Resection
  - Partial Resection
  - Biopsy Only
- **Key Fields:**
  - `extent_of_resection`
  - `surgeon_statement` (direct quote)
  - `residual_tumor_reason` (if applicable)
  - `estimated_percent_resection`
  - `complications`

#### Progress Note Disease State Validation (`build_progress_note_disease_state_prompt`)
- **Purpose:** Extract oncologist's clinical disease assessment
- **Categories:** NED, Stable, Progressive, Responding, Recurrence, Uncertain
- **Key Fields:**
  - `clinical_disease_status`
  - `oncologist_assessment` (direct quote from A&P)
  - `neurological_exam` (status and findings)
  - `treatment_response_statement`
  - `performance_status` (KPS, ECOG)
  - `imaging_correlation` (does clinical assessment agree with imaging?)
  - `management_plan`

**Why Important:** Clinical assessment can reveal progression before imaging changes and takes precedence over imaging-only assessments.

---

### 2. Progress Note Filtering

**File:** `utils/progress_note_filters.py`

#### Oncology-Specific Note Identification
- **Included:** Oncology, neuro-oncology, hematology-oncology progress notes
- **Excluded:** Telephone encounters, nursing notes, social work, pharmacy, admin
- **Keyword Matching:** Chemotherapy, radiation, tumor board, disease progression, surveillance

#### Functions:
- `is_oncology_note(note)` - Boolean filter
- `filter_oncology_notes(notes)` - Filter list
- `get_note_filtering_stats(notes)` - Analytics

**Impact:** Reduces progress notes by ~50% (e.g., 999 → 500) by excluding non-clinical notes

---

### 3. Agent 1 Event Type Classification

**File:** `agents/event_type_classifier.py`

#### Event Type Logic (Per User Specification)
- **Initial CNS Tumor:** First documented tumor event
- **Recurrence:** Tumor growth after Gross Total Resection
- **Progressive:** Tumor growth after Partial Resection or Biopsy Only
- **Second Malignancy:** New tumor in different location

#### Class: `EventTypeClassifier`
- `classify_event()` - Classify single event based on surgical history
- `classify_patient_events()` - Classify all events for patient
- `_is_new_location()` - Detect second malignancies
- `_get_most_recent_surgery_before()` - Find relevant surgical context

**Key Point:** This is an **Agent 1 responsibility** that requires analyzing surgical history + tumor status trajectory. Agent 2 only extracts tumor_status; Agent 1 determines event_type.

---

### 4. Agent 1 Multi-Source EOR Adjudication

**File:** `agents/eor_adjudicator.py`

#### Source Hierarchy
1. **Operative report** (GOLD STANDARD - surgeon's direct assessment)
2. **Post-operative imaging** (within 72 hours)
3. **Procedure notes** (structured data)

#### Class: `EORAdjudicator`
- `adjudicate_eor()` - Reconcile EOR from multiple sources
- `_assess_agreement()` - Detect full agreement, partial agreement, or discrepancy
- `_query_agent2_for_clarification()` - Request Agent 2 re-review when discrepancy
- `_determine_final_eor()` - Apply source hierarchy
- `_calculate_confidence()` - Higher confidence when sources agree

#### Agreement Types:
- **Full Agreement:** All sources same EOR
- **Partial Agreement:** GTR vs Near Total, or Near Total vs Partial
- **Discrepancy:** GTR vs Partial (query Agent 2 for clarification)

**Output:** `EORAdjudication` dataclass with final EOR, confidence, reasoning, and all sources assessed

---

### 5. Demonstration Workflow

**File:** `scripts/demo_agent1_agent2_workflow.py`

Complete end-to-end demonstration showing:
1. Agent 1 gathers multi-source data
2. Agent 1 filters progress notes (50% reduction)
3. Agent 1 sends 3 targeted requests to Agent 2:
   - Tumor status from imaging PDF
   - EOR from operative report
   - Disease state from progress note
4. Agent 1 adjudicates multi-source EOR (operative + imaging agree)
5. Agent 1 classifies event_type as "Initial CNS Tumor"
6. Agent 1 resolves temporal inconsistency via surgical context
7. Agent 1 generates patient QA report

**Test Case:** Patient e4BwD8ZYDBccepXcJ.Ilo3w3 May 2018 temporal inconsistency
- May 27: tumor_status = Increased
- May 28: Craniotomy with GTR
- May 29: tumor_status = Decreased
- **Resolution:** NOT inconsistency - surgical intervention explains change

---

## Updated Files

### `agents/extraction_prompts.py`
- Added `build_operative_report_eor_extraction_prompt()`
- Added `build_progress_note_disease_state_prompt()`
- Updated `__all__` exports

### `scripts/test_comprehensive_multi_source_workflow.py`
- Fixed column names in v_procedures_tumor query:
  - `proc_code_text` (not procedure_code_text)
  - `proc_outcome_text` (not procedure_outcome_text)
  - `pbs_body_site_text` (not procedure_bodySite_text)
  - `proc_performed_date_time` (not procedure_date)
- Added `surgery_type` field
- Added `is_tumor_surgery = true` filter

---

## Key Terminology Updates

### Extent of Resection (EOR)
Per user specification:
- ✅ **Gross Total Resection** / **Near Total Resection**
- ✅ **Partial Resection**
- ✅ **Biopsy Only**

Previous terms like "STR" (Subtotal) should map to "Near Total Resection"

### Event Type
Per user specification:
- ✅ **Initial CNS Tumor**
- ✅ **Recurrence**
- ✅ **Progressive**
- ✅ **Second Malignancy**

---

## Workflow Comparison

### Before
- Agent 2 extracted tumor_status from imaging only
- No operative report EOR extraction
- No progress note validation
- No event_type classification
- No multi-source adjudication
- 999 progress notes processed (including telephone calls, nursing notes)

### After
- ✅ Agent 2 extracts from multiple document types (imaging, operative reports, progress notes)
- ✅ Operative reports processed for EOR (gold standard)
- ✅ Progress notes filtered to oncology-specific (~50% reduction)
- ✅ Agent 2 validates disease state from clinical assessments
- ✅ Agent 1 adjudicates EOR across operative report + imaging
- ✅ Agent 1 classifies event_type based on surgical history
- ✅ Agent 1 can iteratively query Agent 2 for clarification
- ✅ All decisions documented in patient QA report

---

## Data Source Integration

### Complete Multi-Source Pipeline
1. **v_imaging** - Text imaging reports → tumor_status
2. **v_binary_files** (imaging PDFs) → tumor_status
3. **v_procedures_tumor** (operative reports) → extent_of_resection (GOLD STANDARD)
4. **v_binary_files** (progress notes, filtered) → clinical_disease_status validation

### Source Hierarchy for Adjudication
**EOR:** Operative report > Post-op imaging > Procedure structured data
**Disease State:** Oncology progress note + exam > Imaging > Imaging text alone

---

## Next Steps for Production

### Integration with MedGemma (Agent 2)
1. Connect to MedGemma via Ollama
2. Send extraction prompts from Agent 1
3. Parse structured JSON responses
4. Handle clarification queries

### Full Patient Processing
1. Query all data sources for patient
2. Filter progress notes to oncology-specific
3. Send batched extraction requests to Agent 2
4. Perform Agent 1 adjudications
5. Classify all event types
6. Generate comprehensive patient QA report

### Scale to Cohort
1. Test on 5 pilot patients
2. Measure resolution rate (target >80% automated)
3. Review escalated cases requiring human input
4. Scale to 200 BRIM patients

---

## Testing

Run demonstration:
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/demo_agent1_agent2_workflow.py
```

Expected output:
- 6 workflow phases demonstrated
- Progress note filtering (50% reduction)
- 3 Agent 2 extraction requests
- Multi-source EOR adjudication (full agreement)
- Event type classification (Initial CNS Tumor)
- Temporal inconsistency resolution
- Patient QA report generation

---

## Files Summary

### Created
1. `agents/extraction_prompts.py` - Added operative report & progress note prompts
2. `utils/progress_note_filters.py` - Oncology-specific note filtering
3. `agents/event_type_classifier.py` - Agent 1 event type logic
4. `agents/eor_adjudicator.py` - Agent 1 multi-source EOR reconciliation
5. `scripts/demo_agent1_agent2_workflow.py` - Complete workflow demonstration
6. `AGENT_WORKFLOW_ENHANCEMENTS.md` - This document

### Updated
1. `scripts/test_comprehensive_multi_source_workflow.py` - Fixed v_procedures_tumor column names

---

## Questions Answered

### Q: Should event_type be Agent 1 or Agent 2 responsibility?
**A:** Agent 1. Requires analyzing surgical history + tumor status trajectory over time.

### Q: How to assess operative reports for EOR?
**A:** Agent 1 sends operative note to Agent 2 via `build_operative_report_eor_extraction_prompt()`. Operative report takes precedence over imaging.

### Q: How to identify oncology-specific progress notes?
**A:** `utils/progress_note_filters.py` filters based on dr_type_text, keywords, and exclusions.

### Q: How does Agent 1 adjudicate conflicts?
**A:** `agents/eor_adjudicator.py` applies source hierarchy, assesses agreement, and can query Agent 2 for clarification.

---

## Architecture Benefits

1. **Clear Separation of Concerns:** Agent 2 extracts, Agent 1 orchestrates
2. **Source Hierarchy:** Operative reports prioritized appropriately
3. **Iterative Queries:** Agent 1 can request clarification from Agent 2
4. **Clinical Validation:** Progress notes validate imaging assessments
5. **Comprehensive Documentation:** All decisions tracked in QA reports
6. **Scalable:** Framework supports batch processing with quality checks
