# Integration TODO: Radiation/Chemotherapy + Prompt Optimizations

## Status

**Completed:**
- ✅ Created standalone radiation JSON builder ([build_radiation_json.py](scripts/build_radiation_json.py))
- ✅ Created standalone chemotherapy JSON builder ([build_chemotherapy_json.py](scripts/build_chemotherapy_json.py))
- ✅ Tested both builders work correctly with Athena views
- ✅ Documented prompt optimization recommendations ([PROGRESS_NOTE_PROMPT_OPTIMIZATION_ANALYSIS.md](PROGRESS_NOTE_PROMPT_OPTIMIZATION_ANALYSIS.md))
- ✅ Found patient with radiation data: `Patient/eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3`

**NOT Completed (Remaining Work):**
- ❌ Integrate radiation/chemotherapy builders into [run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py)
- ❌ Implement 4 prompt optimizations
- ❌ Test integrated workflow

---

## Task 1: Integrate Radiation & Chemotherapy JSON Builders

### What Needs to Be Done

Add to [run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py):

**PHASE 1A-NEW: Query Radiation Data** (insert before current PHASE 1A)

```python
# Import the builders at top of file
from scripts.build_radiation_json import RadiationJSONBuilder
from scripts.build_chemotherapy_json import ChemotherapyJSONBuilder

# In main() function, after initialization, add:

print("="*80)
print("PHASE 1-PRE: QUERY RADIATION AND CHEMOTHERAPY DATA")
print("="*80)
print()

# 1-PRE-A: Radiation data
print("1-PRE-A. Querying radiation data...")
radiation_builder = RadiationJSONBuilder(aws_profile='radiant-prod')
try:
    radiation_json = radiation_builder.build_comprehensive_json(args.patient_id)
    print(f"  Radiation courses: {radiation_json.get('total_courses', 0)}")
    print(f"  Radiation documents: {len(radiation_json.get('supporting_documents', {}).get('treatment_summaries', []))}")
except Exception as e:
    print(f"  ⚠️  No radiation data or error: {e}")
    radiation_json = None

# 1-PRE-B: Chemotherapy data
print("1-PRE-B. Querying chemotherapy data...")
chemo_builder = ChemotherapyJSONBuilder(aws_profile='radiant-prod')
try:
    chemo_json = chemo_builder.build_comprehensive_json(args.patient_id)
    print(f"  Chemotherapy courses: {chemo_json.get('total_courses', 0)}")
    print(f"  Total medications: {chemo_json.get('total_medications', 0)}")
except Exception as e:
    print(f"  ⚠️  No chemotherapy data or error: {e}")
    chemo_json = None

print()
```

**Location:** Insert this RIGHT AFTER line 367 (before current PHASE 1 starts)

---

## Task 2: Update Timeline Context to Include Chemo/Radiation (Optimization #3)

### What Needs to Be Done

Update the `build_timeline_context()` function (lines 611-688):

```python
def build_timeline_context(
    current_date_str: str,
    chemo_json: Optional[Dict] = None,
    radiation_json: Optional[Dict] = None
) -> Dict:
    """
    Build events_before and events_after context for a given date.
    NOW INCLUDES: imaging, surgeries, chemotherapy courses, radiation treatments
    """
    from datetime import datetime, timedelta

    try:
        current_date = datetime.fromisoformat(str(current_date_str).replace(' ', 'T'))
    except (ValueError, AttributeError):
        return {'events_before': [], 'events_after': []}

    events_before = []
    events_after = []

    # Add imaging events (existing code - keep as is)
    for img in imaging_text_reports:
        # ... existing imaging code ...

    # Add procedure events (existing code - keep as is)
    for proc_id, proc_date_str, surgery_type in surgical_history:
        # ... existing procedure code ...

    # NEW: Add chemotherapy course events
    if chemo_json and chemo_json.get('treatment_courses'):
        for course in chemo_json['treatment_courses']:
            try:
                course_start = course.get('course_start_date')
                if not course_start:
                    continue

                course_date = datetime.fromisoformat(course_start.split()[0])
                days_diff = (current_date - course_date).days

                if abs(days_diff) > 180:  # Within 6 months
                    continue

                event = {
                    'event_type': 'Medication',
                    'event_category': 'Chemotherapy',
                    'event_date': course_start.split()[0],
                    'days_diff': -days_diff,
                    'description': f"{len(course['medications'])} chemotherapy medications started"
                }

                if days_diff > 0:
                    events_before.append(event)
                elif days_diff < 0:
                    events_after.append(event)
            except:
                continue

    # NEW: Add radiation treatment events
    if radiation_json and radiation_json.get('treatment_courses'):
        for treatment in radiation_json['treatment_courses']:
            try:
                treatment_start = treatment.get('start_date')
                if not treatment_start:
                    continue

                treatment_date = datetime.fromisoformat(treatment_start.split()[0])
                days_diff = (current_date - treatment_date).days

                if abs(days_diff) > 180:
                    continue

                event = {
                    'event_type': 'Radiation',
                    'event_category': 'Radiation Therapy',
                    'event_date': treatment_start.split()[0],
                    'days_diff': -days_diff,
                    'description': f"Radiation to {treatment.get('radiation_field', 'unknown site')}"
                }

                if days_diff > 0:
                    events_before.append(event)
                elif days_diff < 0:
                    events_after.append(event)
            except:
                continue

    # Sort by proximity to current date (existing code - keep as is)
    events_before.sort(key=lambda x: abs(x['days_diff']))
    events_after.sort(key=lambda x: abs(x['days_diff']))

    return {
        'events_before': events_before,
        'events_after': events_after
    }
```

**Then update ALL calls to `build_timeline_context()` to pass the new parameters:**

```python
# Example (line ~698):
timeline_events = build_timeline_context(
    report_date,
    chemo_json=chemo_json,
    radiation_json=radiation_json
)
```

---

## Task 3: Add Progress Note-Specific Prompts (Optimization #1 & #2)

### What Needs to Be Done

Add to [agents/extraction_prompts.py](agents/extraction_prompts.py) at the end of the file:

```python
def build_progress_note_comprehensive_prompt(
    note_data: Dict[str, Any],
    context: Dict[str, Any],
    priority_reason: str
) -> str:
    """
    Comprehensive prompt for progress note extraction (Optimization #1 & #2 & #4 combined)

    Extracts ALL fields in a single LLM call:
    - Document classification
    - Tumor status
    - Tumor location
    - Treatment response
    - Clinical reasoning
    - Toxicities
    - Treatment plan changes

    Customizes based on priority_reason (post_surgery, post_imaging, post_medication_change, final_note)
    """

    note_text = note_data.get('extracted_text', note_data.get('note_text', ''))
    note_date = note_data.get('dr_date', 'Unknown')

    # Build temporal context
    events_before = context.get('events_before', [])
    events_after = context.get('events_after', [])

    context_summary = []
    for event in events_before[:5]:  # Show up to 5 recent events
        days = abs(event.get('days_diff', 0))
        context_summary.append(
            f"- {event['event_type']} {days} days BEFORE: {event['description']}"
        )

    for event in events_after[:3]:  # Show up to 3 upcoming events
        days = abs(event.get('days_diff', 0))
        context_summary.append(
            f"- {event['event_type']} {days} days AFTER: {event['description']}"
        )

    context_text = "\n".join(context_summary) if context_summary else "No major clinical events in surrounding timeline"

    # Customize based on priority reason
    priority_focus = ""
    if priority_reason == "post_surgery":
        priority_focus = """
**PRIORITY FOCUS (Post-Surgery Note):**
This note was selected because it occurs shortly after a tumor surgery. Focus on:
- Post-operative assessment and recovery
- Discussion of surgical findings and pathology
- Changes to treatment plan based on surgical outcome
- Post-operative complications if any
"""
    elif priority_reason == "post_medication_change":
        priority_focus = """
**PRIORITY FOCUS (Medication Change Note):**
This note was selected because it occurs around a chemotherapy/treatment change. Focus on:
- Rationale for medication change (progression, toxicity, completion)
- Baseline disease assessment before new medication
- Response assessment from previous medication if discussed
- Anticipated toxicity monitoring plan
"""
    elif priority_reason == "post_imaging":
        priority_focus = """
**PRIORITY FOCUS (Post-Imaging Note):**
This note was selected because it occurs shortly after imaging. Focus on:
- Clinical interpretation of imaging findings
- How imaging results affect treatment decisions
- Discussion of response criteria (RANO, RECIST, etc.)
- Any changes to treatment plan based on imaging
"""
    elif priority_reason == "final_note":
        priority_focus = """
**PRIORITY FOCUS (Most Recent Note):**
This is the patient's most recent progress note. Focus on:
- Current disease status summary
- Active treatment regimen
- Upcoming planned interventions
- Overall disease trajectory (improving, stable, declining)
"""

    prompt = f"""You are a medical AI extracting comprehensive clinical information from an oncology progress note.

**NOTE INFORMATION:**
Date: {note_date}
Priority Reason: {priority_reason}

**TEMPORAL CONTEXT (Clinical Events):**
{context_text}

{priority_focus}

**PROGRESS NOTE TEXT:**
{note_text}

**EXTRACTION TASK:**
Extract the following information from this progress note. Look for information in the Assessment and Plan sections primarily.

**OUTPUT FORMAT (JSON):**
{{
  "document_classification": {{
    "document_type": "progress_note",
    "specialty": "oncology" | "hematology" | "neurology" | "other",
    "note_sections_present": ["subjective", "objective", "assessment", "plan"]  // which SOAP sections are present
  }},

  "tumor_status": {{
    "status": "NED" | "Stable" | "Increased" | "Decreased" | "New_Malignancy" | "Not_mentioned",
    "confidence": 0.0-1.0,
    "clinical_assessment": "Free text summary of disease state from clinician's perspective",
    "evidence": "Direct quote from note"
  }},

  "tumor_location": {{
    "primary_location": "Anatomical location if mentioned",
    "laterality": "left" | "right" | "bilateral" | "midline" | null,
    "evidence": "Direct quote"
  }},

  "treatment_response": {{
    "response_category": "complete_response" | "partial_response" | "stable_disease" | "progressive_disease" | "not_assessed",
    "response_criteria_used": "RANO" | "RECIST" | "clinical_assessment" | null,
    "evidence": "Direct quote discussing response"
  }},

  "clinical_reasoning": {{
    "why_treatment_changed": "Explanation if treatment plan changed",
    "clinical_concerns": "Any concerns mentioned by clinician",
    "future_plan": "What is planned for next steps"
  }},

  "toxicities": [
    {{
      "adverse_event": "Description of side effect/toxicity",
      "grade": "1-5 or null if not graded",
      "attribution": "definitely_related" | "possibly_related" | "unlikely_related" | "unrelated",
      "management": "How toxicity is being managed",
      "evidence": "Direct quote"
    }}
  ],

  "treatment_plan": {{
    "medications_started": ["List of new medications"],
    "medications_stopped": ["List of stopped medications"],
    "medications_dose_modified": ["List of medications with dose changes"],
    "upcoming_procedures": ["Planned procedures/surgeries"],
    "upcoming_imaging": ["Planned imaging studies"]
  }}
}}

**INSTRUCTIONS:**
1. Only extract information explicitly stated in the note
2. Use "Not_mentioned" or null for fields without information
3. Include direct quotes as evidence when possible
4. Pay special attention to the Assessment and Plan sections
5. Consider the temporal context when interpreting clinical decisions
6. Return ONLY valid JSON, no additional text

OUTPUT:
"""

    return prompt
```

**Then update [run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py) Phase 2D (lines ~912-946):**

```python
# 2D: Extract from progress notes
print(f"2D. Extracting from {len(prioritized_notes)} prioritized progress notes...")
for idx, prioritized_note in enumerate(prioritized_notes, 1):
    note_data = prioritized_note.note
    note_id = note_data['document_reference_id']
    note_date = note_data['dr_date']
    priority_reason = prioritized_note.priority_reason

    # Build timeline context with chemo/radiation
    timeline_events = build_timeline_context(
        note_date,
        chemo_json=chemo_json,
        radiation_json=radiation_json
    )

    # Extract text from note (cached if previously extracted)
    cached_doc = doc_cache.get_cached_document(note_id)
    if cached_doc:
        extracted_text = cached_doc.extracted_text
    else:
        extracted_text, error = binary_agent.extract_text_from_binary(
            binary_id=note_data['binary_id'],
            patient_fhir_id=args.patient_id,
            content_type=note_data.get('content_type'),
            document_reference_id=note_id
        )
        if error:
            workflow_logger.log_warning(f"Failed to extract note {note_id}: {error}")
            continue
        doc_cache.cache_document_from_binary(
            document_id=note_id,
            patient_fhir_id=args.patient_id,
            extracted_text=extracted_text,
            content_type=note_data.get('content_type')
        )

    # Prepare context
    context = {
        'patient_id': args.patient_id,
        'report_date': note_date,
        'events_before': timeline_events['events_before'],
        'events_after': timeline_events['events_after']
    }

    # NEW: Use comprehensive progress note prompt (Optimization #1, #2, #4)
    comprehensive_prompt = build_progress_note_comprehensive_prompt(
        {**note_data, 'extracted_text': extracted_text},
        context,
        priority_reason
    )

    comprehensive_result = medgemma.extract(comprehensive_prompt, "progress_note_comprehensive")

    print(f"  [{idx}/{len(prioritized_notes)}] {note_id[:30]}... ({note_date})")
    print(f"    Priority: {priority_reason}")
    print(f"    Tumor status: {comprehensive_result.extracted_data.get('tumor_status', {}).get('status', 'unknown')}")

    all_extractions.append({
        'source': 'progress_note',
        'source_id': note_id,
        'date': note_date,
        'priority_reason': priority_reason,
        'comprehensive_extraction': comprehensive_result.extracted_data if comprehensive_result.success else {'error': comprehensive_result.error},
        'confidence': comprehensive_result.confidence
    })
    extraction_count['progress_notes'] += 1
```

---

## Task 4: Test the Integrated Workflow

### Commands to Run

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Test on patient with radiation data
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3

# Check output
ls -lh data/patient_abstractions/*/
```

### Expected Output

```
PHASE 1-PRE: QUERY RADIATION AND CHEMOTHERAPY DATA
  Radiation courses: 2
  Radiation documents: 13
  Chemotherapy courses: 3
  Total medications: 8

PHASE 1: QUERYING ALL DATA SOURCES FROM ATHENA
  1A. Imaging text reports: 15
  1B. Imaging PDFs: 8
  1C. Operative reports: 2
  1D. Progress notes: 12 prioritized

PHASE 2: AGENT 2 EXTRACTION
  ... (extraction results with comprehensive progress note data)
```

---

## Summary of Changes

### Files to Modify

1. **[scripts/run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py)**:
   - Add imports for RadiationJSONBuilder, ChemotherapyJSONBuilder
   - Add PHASE 1-PRE before current PHASE 1
   - Update `build_timeline_context()` to accept chemo_json and radiation_json
   - Update all calls to `build_timeline_context()` to pass new parameters
   - Replace Phase 2D progress note extraction with comprehensive prompt

2. **[agents/extraction_prompts.py](agents/extraction_prompts.py)**:
   - Add `build_progress_note_comprehensive_prompt()` function

### Estimated Implementation Time

- Radiation/Chemo integration: 30 minutes
- Timeline context update: 20 minutes
- Progress note prompts: 40 minutes
- Testing: 30 minutes
- **Total: ~2 hours**

### Benefits Once Complete

- ✅ Full radiation treatment data available in timeline
- ✅ Full chemotherapy treatment data available in timeline
- ✅ Progress notes have complete temporal context (imaging + surgery + chemo + radiation)
- ✅ Progress note extraction is optimized for clinical content (SOAP format, treatment response, toxicities)
- ✅ Priority reason-aware prompts focus extraction appropriately
- ✅ Single LLM call per progress note (instead of 3) = 66% cost savings
- ✅ Expected +15-30% improvement in extraction accuracy
