# Agent 1 Implementation Guide

## Overview

This document describes the complete Agent 1 (Enhanced Master Agent) implementation integrated into the `run_full_multi_source_abstraction.py` workflow.

## Implementation Status

### ✅ Phase 3: Temporal Inconsistency Detection (IMPLEMENTED)

**Location**: Lines 853-949 in `run_full_multi_source_abstraction.py`

**What it does**:
- Analyzes tumor status extractions from imaging reports chronologically
- Detects temporal patterns that don't make clinical sense
- Implements two detection rules:
  1. **Rapid Improvement**: Tumor status improved from "Increased" to "Decreased" in <14 days without surgery
  2. **Unexpected Progression**: Disease detected <90 days after NED (No Evidence of Disease)

**Detection Logic**:
```python
# Build imaging extractions timeline
imaging_extractions = []
for extraction in all_extractions:
    if extraction['source'] in ['imaging_text', 'imaging_pdf']:
        # Extract tumor status
        # Add to timeline

# Sort chronologically and compare consecutive pairs
for i in range(len(imaging_extractions) - 1):
    prior = imaging_extractions[i]
    current = imaging_extractions[i + 1]

    # Calculate days between
    # Check for suspicious patterns
    # Mark high-severity inconsistencies for Agent 2 review
```

**Output**:
```json
{
  "temporal_inconsistencies": {
    "count": 2,
    "high_severity": 1,
    "requiring_agent2_query": 1,
    "details": [
      {
        "inconsistency_id": "rapid_improvement_...",
        "type": "rapid_improvement",
        "severity": "high",
        "description": "Tumor status improved from Increased to Decreased in 10 days without documented surgery",
        "prior_date": "2021-03-10",
        "current_date": "2021-03-20",
        "days_between": 10,
        "requires_agent2_query": true
      }
    ]
  }
}
```

### ⏳ Phase 4: Agent 1 ↔ Agent 2 Iterative Clarification (TO IMPLEMENT)

**Purpose**: Query Agent 2 (MedGemma) for clarification on high-severity temporal inconsistencies

**Implementation approach**:
```python
clarifications = []

# For each inconsistency requiring Agent 2 query
for inc in [i for i in inconsistencies if i.get('requires_agent2_query')]:
    # Build clarification prompt
    prompt = f"""
    # AGENT 1 REQUESTS CLARIFICATION FROM AGENT 2

    ## Temporal Inconsistency Detected
    {inc['description']}

    ## Timeline
    - {inc['prior_date']}: {inc['prior_status']}
    - {inc['current_date']}: {inc['current_status']}
    - Days between: {inc['days_between']}

    ## Question
    Please re-review these imaging reports and determine:
    1. Is this rapid change clinically plausible?
    2. Should either extraction be revised?
    3. What clinical explanation could account for this pattern?

    Provide recommendation: keep_both | revise_first | revise_second | escalate_to_human
    """

    # Query Agent 2
    result = medgemma.extract(prompt, "temporal_inconsistency_clarification")

    clarifications.append({
        'inconsistency_id': inc['inconsistency_id'],
        'agent2_response': result.extracted_data,
        'success': result.success
    })
```

### ⏳ Phase 5: Multi-Source EOR Adjudication (TO IMPLEMENT)

**Purpose**: When operative reports and imaging reports disagree on extent of resection (EOR), Agent 1 adjudicates which source is more reliable

**Implementation approach**:
```python
eor_adjudications = []

# Group extractions by procedure
procedures = {}
for ext in all_extractions:
    if ext['source'] == 'operative_report' and 'eor' in ext:
        proc_id = ext['source_id']
        procedures[proc_id] = {
            'operative_eor': ext['eor'].get('extent_of_resection'),
            'imaging_eors': []
        }

# Find corresponding post-op imaging (within 72 hours)
for proc_id, proc_data in procedures.items():
    surgery_date = ... # Get from extraction

    # Find imaging within 72 hours
    for ext in all_extractions:
        if ext['source'] in ['imaging_text', 'imaging_pdf']:
            img_date = datetime.fromisoformat(ext['date'])
            if 0 <= (img_date - surgery_date).days <= 3:
                proc_data['imaging_eors'].append(ext)

    # Adjudicate using EORAdjudicator
    if proc_data['imaging_eors']:
        sources = [
            EORSource(
                source_type='operative_report',
                source_id=proc_id,
                source_date=surgery_date,
                eor=proc_data['operative_eor'],
                confidence=0.95,
                evidence='...',
                extracted_by='agent2'
            ),
            # Add imaging sources...
        ]

        adjudication = eor_adjudicator.adjudicate_eor(proc_id, surgery_date, sources)
        eor_adjudications.append({
            'procedure_id': proc_id,
            'final_eor': adjudication.final_eor,
            'confidence': adjudication.confidence,
            'agreement_status': adjudication.agreement,
            'sources_count': len(sources)
        })
```

### ⏳ Phase 6: Event Type Classification (TO FIX)

**Current Status**: Implementation exists but returns 0 events

**Problem**: `event_classifier.classify_patient_events(patient_id)` queries the timeline database for tumor_status extractions, but extractions haven't been written to the timeline yet - they only exist in the `all_extractions` list.

**Fix Options**:

**Option 1**: Write extractions to timeline before Phase 6
```python
# After Phase 2, before Phase 6:
for ext in all_extractions:
    if ext['source'] in ['imaging_text', 'imaging_pdf']:
        if 'tumor_status' in ext:
            timeline.save_extraction(
                patient_id=args.patient_id,
                event_id=ext['source_id'],
                variable_name='tumor_status',
                variable_value=ext['tumor_status'].get('overall_status'),
                confidence=ext.get('tumor_status_confidence')
            )
```

**Option 2**: Pass extractions directly to classifier
```python
# Modify EventTypeClassifier to accept in-memory extractions
event_classifications = event_classifier.classify_events_from_memory(
    patient_id=args.patient_id,
    tumor_extractions=all_extractions,
    surgical_history=[e for e in all_extractions if e['source'] == 'operative_report']
)
```

## Integration Summary

### Before (TODOs):
- Phase 3: Empty list, 0 inconsistencies
- Phase 4: Empty list, 0 Agent 2 queries
- Phase 5: Empty list, 0 EOR adjudications
- Phase 6: Calls classifier but gets 0 events (database empty)

### After (Full Implementation):
- Phase 3: ✅ Detects temporal inconsistencies in imaging timeline
- Phase 4: Query Agent 2 for clarification on suspicious patterns
- Phase 5: Adjudicate EOR from operative reports vs post-op imaging
- Phase 6: Classify events (Initial/Recurrence/Progressive/Second Malignancy)

## Running the Workflow

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Run full workflow with all Agent 1 phases
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --timeline-db data/patient_timeline.duckdb

# Output location
# data/patient_abstractions/{timestamp}/Patient_e4BwD8ZYDBccepXcJ.Ilo3w3_comprehensive.json
```

## Next Steps for Tomorrow

When you ask me to run the extraction tomorrow, I will have access to this context via:

1. **This documentation file** (`AGENT_1_IMPLEMENTATION.md`)
2. **The implemented code** in `run_full_multi_source_abstraction.py`
3. **Test patient data**: `Patient/e4BwD8ZYDBccepXcJ.Ilo3w3`

### Quick Start Commands:

```bash
# Navigate to project
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Run extraction
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --timeline-db data/patient_timeline.duckdb

# Check output
ls -lh data/patient_abstractions/
```

### Expected Output:

```
PHASE 1: QUERYING ALL DATA SOURCES FROM ATHENA
  Imaging text reports... ✅ 82 records
  Imaging PDFs... ✅ 104 records
  Operative reports... ✅ 9 records
  Progress notes... ✅ 2474 records → 58 prioritized

PHASE 2: AGENT 2 EXTRACTION
  ✅ Completed 82 imaging text extractions
  ✅ Completed ~104 imaging PDF extractions
  ✅ Completed ~9 operative report extractions
  ✅ Completed 58 progress note extractions

PHASE 3: AGENT 1 TEMPORAL INCONSISTENCY DETECTION
  Detected X temporal inconsistencies
    High severity: Y
    Medium severity: Z

PHASE 4: AGENT 1 <-> AGENT 2 ITERATIVE CLARIFICATION
  Y Agent 2 queries sent

PHASE 5: AGENT 1 MULTI-SOURCE EOR ADJUDICATION
  N EOR adjudications completed

PHASE 6: AGENT 1 EVENT TYPE CLASSIFICATION
  ✅ Classified M events
```

## Known Issues

1. **Progress note extraction**: Fixed (parameter bug)
2. **PDF extraction**: Fixed (parameter bug)
3. **Operative report dates**: Fixed (using `procedure_date` field)
4. **Event classification returning 0**: Needs timeline write or in-memory classifier

## Files Modified

1. `scripts/run_full_multi_source_abstraction.py` - Integrated Agent 1 logic
2. `agents/enhanced_master_agent.py` - Exists, has temporal detection logic
3. `agents/eor_adjudicator.py` - Exists, has adjudication logic
4. `agents/event_type_classifier.py` - Exists, needs timeline data or in-memory support

## Architecture

```
Multi-Source Extraction Workflow
│
├─ Phase 1: Query Athena
│  └─ Get imaging, operative reports, progress notes
│
├─ Phase 2: Agent 2 (MedGemma) Extraction
│  ├─ Imaging text reports → tumor_status, imaging_type
│  ├─ Imaging PDFs → tumor_status, imaging_type
│  ├─ Operative reports → extent_of_resection
│  └─ Progress notes → disease_state
│
├─ Phase 3: Agent 1 Temporal Inconsistency Detection ✅
│  └─ Detect illogical tumor status progressions
│
├─ Phase 4: Agent 1 ↔ Agent 2 Clarification ⏳
│  └─ Query Agent 2 to resolve inconsistencies
│
├─ Phase 5: Agent 1 EOR Adjudication ⏳
│  └─ Reconcile operative vs imaging EOR
│
└─ Phase 6: Agent 1 Event Classification ⏳
   └─ Classify: Initial/Recurrence/Progressive/Second Malignancy
```
