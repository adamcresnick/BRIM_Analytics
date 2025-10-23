#!/usr/bin/env python3
"""
Script to apply all radiation/chemotherapy integration and prompt optimizations
Run this to automatically update the codebase with all required changes
"""

import sys
from pathlib import Path

def add_comprehensive_progress_note_prompt():
    """Add comprehensive progress note prompt to extraction_prompts.py"""

    prompt_code = '''

def build_progress_note_comprehensive_prompt(
    note_data: Dict[str, Any],
    context: Dict[str, Any],
    priority_reason: str
) -> str:
    """
    Comprehensive prompt for progress note extraction (Optimizations #1, #2, #4 combined)

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

    context_text = "\\n".join(context_summary) if context_summary else "No major clinical events in surrounding timeline"

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
    "note_sections_present": ["subjective", "objective", "assessment", "plan"]
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
'''

    extraction_prompts_path = Path('agents/extraction_prompts.py')

    with open(extraction_prompts_path, 'a') as f:
        f.write(prompt_code)

    print("✅ Added build_progress_note_comprehensive_prompt to extraction_prompts.py")


def update_main_workflow():
    """Update run_full_multi_source_abstraction.py with all integrations"""

    workflow_path = Path('scripts/run_full_multi_source_abstraction.py')
    content = workflow_path.read_text()

    # 1. Add imports at top
    import_section = content.split('from agents.master_agent import MasterAgent')[0]
    new_imports = '''from scripts.build_radiation_json import RadiationJSONBuilder
from scripts.build_chemotherapy_json import ChemotherapyJSONBuilder
'''

    content = content.replace(
        'from agents.master_agent import MasterAgent',
        new_imports + 'from agents.master_agent import MasterAgent'
    )

    # 2. Add PHASE 1-PRE (radiation and chemotherapy querying)
    phase_1_pre = '''
        # ================================================================
        # PHASE 1-PRE: QUERY RADIATION AND CHEMOTHERAPY DATA
        # ================================================================
        print("="*80)
        print("PHASE 1-PRE: QUERY RADIATION AND CHEMOTHERAPY DATA")
        print("="*80)
        print()

        # 1-PRE-A: Radiation data
        print("1-PRE-A. Querying radiation data...")
        radiation_json = None
        try:
            radiation_builder = RadiationJSONBuilder(aws_profile='radiant-prod')
            radiation_json = radiation_builder.build_comprehensive_json(args.patient_id)
            print(f"  Radiation courses: {radiation_json.get('total_courses', 0)}")
            print(f"  Radiation documents: {len(radiation_json.get('supporting_documents', {}).get('treatment_summaries', []))}")
        except Exception as e:
            print(f"  ⚠️  No radiation data or error: {e}")
            radiation_json = None

        # 1-PRE-B: Chemotherapy data
        print("1-PRE-B. Querying chemotherapy data...")
        chemo_json = None
        try:
            chemo_builder = ChemotherapyJSONBuilder(aws_profile='radiant-prod')
            chemo_json = chemo_builder.build_comprehensive_json(args.patient_id)
            print(f"  Chemotherapy courses: {chemo_json.get('total_courses', 0)}")
            print(f"  Total medications: {chemo_json.get('total_medications', 0)}")
        except Exception as e:
            print(f"  ⚠️  No chemotherapy data or error: {e}")
            chemo_json = None

        print()

'''

    content = content.replace(
        '        # ================================================================\n        # PHASE 1: QUERY ALL DATA SOURCES FROM ATHENA',
        phase_1_pre + '        # ================================================================\n        # PHASE 1: QUERY ALL DATA SOURCES FROM ATHENA'
    )

    # 3. Update build_timeline_context to include chemo/radiation
    old_timeline_func = '''    def build_timeline_context(current_date_str: str) -> Dict:
        """
        Build events_before and events_after context for a given date.
        Uses in-memory data from imaging_text_reports and surgical_history.
        """'''

    new_timeline_func = '''    def build_timeline_context(
        current_date_str: str,
        chemo_json: Optional[Dict] = None,
        radiation_json: Optional[Dict] = None
    ) -> Dict:
        """
        Build events_before and events_after context for a given date.
        Uses in-memory data from imaging_text_reports, surgical_history, chemo, and radiation.
        """'''

    content = content.replace(old_timeline_func, new_timeline_func)

    # Add chemo/radiation events to timeline context (insert before "# Sort by proximity")
    chemo_radiation_events = '''
            # Add chemotherapy course events
            if chemo_json and chemo_json.get('treatment_courses'):
                for course in chemo_json['treatment_courses']:
                    try:
                        course_start = course.get('course_start_date')
                        if not course_start:
                            continue

                        course_date = datetime.fromisoformat(course_start.split()[0])
                        days_diff = (current_date - course_date).days

                        if abs(days_diff) > 180:
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

            # Add radiation treatment events
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

'''

    content = content.replace(
        '            # Sort by proximity to current date',
        chemo_radiation_events + '            # Sort by proximity to current date'
    )

    # 4. Update all build_timeline_context() calls to pass chemo_json and radiation_json
    content = content.replace(
        'timeline_events = build_timeline_context(report_date)',
        'timeline_events = build_timeline_context(report_date, chemo_json, radiation_json)'
    )
    content = content.replace(
        'timeline_events = build_timeline_context(note_date)',
        'timeline_events = build_timeline_context(note_date, chemo_json, radiation_json)'
    )
    content = content.replace(
        'timeline_events = build_timeline_context(doc_date)',
        'timeline_events = build_timeline_context(doc_date, chemo_json, radiation_json)'
    )

    # 5. Update extraction_prompts import to include comprehensive prompt
    content = content.replace(
        'from agents.extraction_prompts import (',
        'from agents.extraction_prompts import (\n    build_progress_note_comprehensive_prompt,'
    )

    # Write updated content
    workflow_path.write_text(content)

    print("✅ Updated run_full_multi_source_abstraction.py with radiation/chemotherapy integration")
    print("✅ Updated timeline context to include chemo/radiation events")
    print("✅ Added comprehensive progress note prompt import")


def main():
    print("="*80)
    print("APPLYING RADIATION/CHEMOTHERAPY INTEGRATION + PROMPT OPTIMIZATIONS")
    print("="*80)
    print()

    try:
        # Change to mvp directory
        mvp_dir = Path(__file__).parent
        import os
        os.chdir(mvp_dir)

        print("Step 1: Adding comprehensive progress note prompt...")
        add_comprehensive_progress_note_prompt()

        print("\nStep 2: Updating main workflow script...")
        update_main_workflow()

        print("\n" + "="*80)
        print("✅ ALL INTEGRATIONS APPLIED SUCCESSFULLY")
        print("="*80)
        print("\nNext steps:")
        print("1. Test the integrated workflow:")
        print("   python3 scripts/run_full_multi_source_abstraction.py \\")
        print("       --patient-id Patient/eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3")
        print("\n2. Commit and push changes:")
        print("   git add -A")
        print("   git commit -m 'Integrate radiation/chemotherapy + prompt optimizations'")
        print("   git push")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
