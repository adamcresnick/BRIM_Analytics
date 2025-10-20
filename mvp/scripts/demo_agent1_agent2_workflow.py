#!/usr/bin/env python3
"""
Demonstration: Complete Agent 1 ↔ Agent 2 Workflow

This script demonstrates the full architecture where:

AGENT 1 (Claude - Orchestrator):
- Gathers multi-source data (imaging text, PDFs, operative reports, progress notes)
- Sends targeted extraction requests to Agent 2
- Receives Agent 2's extractions with confidence scores
- Adjudicates conflicts across sources
- Classifies event_type based on surgical history
- Iteratively queries Agent 2 for clarification
- Documents all inconsistencies in patient QA report

AGENT 2 (MedGemma - Extractor):
- Receives documents and extraction prompts from Agent 1
- Extracts targeted variables (tumor_status, EOR, disease state)
- Returns structured JSON with confidence scores
- Responds to Agent 1's clarification queries
- Does NOT do cross-source reconciliation

Data Sources:
1. v_imaging text reports → tumor_status extraction
2. v_binary_files imaging PDFs → tumor_status extraction
3. v_procedures_tumor operative reports → EOR extraction (GOLD STANDARD)
4. v_binary_files progress notes (filtered) → disease state validation

Test Case: Patient e4BwD8ZYDBccepXcJ.Ilo3w3 May 2018 temporal inconsistency
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.progress_note_filters import filter_oncology_notes, get_note_filtering_stats
from agents.extraction_prompts import (
    build_operative_report_eor_extraction_prompt,
    build_progress_note_disease_state_prompt,
    build_tumor_status_extraction_prompt
)
from agents.eor_adjudicator import EORAdjudicator, EORSource
from agents.event_type_classifier import EventTypeClassifier


def demonstrate_workflow():
    """
    Demonstrate complete Agent 1 ↔ Agent 2 workflow
    """
    print("="*80)
    print("AGENT 1 ↔ AGENT 2 ITERATIVE WORKFLOW DEMONSTRATION")
    print("="*80)
    print()
    print("Patient: e4BwD8ZYDBccepXcJ.Ilo3w3")
    print("Scenario: May 2018 temporal inconsistency")
    print("  - May 27: tumor_status = Increased")
    print("  - May 29: tumor_status = Decreased")
    print("  - May 28: Craniotomy procedure")
    print()
    print("="*80)
    print()

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # =========================================================================
    # PHASE 1: AGENT 1 GATHERS DATA
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 1: AGENT 1 GATHERS MULTI-SOURCE DATA")
    print("="*80 + "\n")

    # Simulate data gathering results (in production: query Athena)
    imaging_pdfs = [
        {
            'document_reference_id': 'DocumentReference/pdf1',
            'dr_date': '2018-05-27 10:30:00',
            'dr_type_text': 'Imaging Result',
            'content_title': 'MRI Brain with Contrast',
            'note_text': 'Impression: Increased size of enhancing mass in right temporal lobe...'
        }
    ]

    progress_notes_raw = [
        {
            'document_reference_id': 'DocumentReference/note1',
            'dr_date': '2018-05-29 13:30:00',
            'dr_type_text': 'Oncology Progress Note',
            'dr_description': 'Post-operative follow-up',
            'content_title': 'Neuro-Oncology Visit',
            'note_text': 'Patient s/p craniotomy 5/28. Neurological exam stable. Post-op MRI shows gross total resection achieved...'
        },
        {
            'document_reference_id': 'DocumentReference/note2',
            'dr_date': '2018-05-30 09:00:00',
            'dr_type_text': 'Telephone Encounter',
            'dr_description': 'Med refill request',
            'content_title': 'Phone call',
            'note_text': 'Patient called for pain medication refill...'
        }
    ]

    operative_reports = [
        {
            'procedure_id': 'Procedure/surg1',
            'procedure_date': datetime(2018, 5, 28, 8, 0),
            'proc_code_text': 'Craniotomy for tumor resection',
            'surgery_type': 'Tumor Resection',
            'note_text': 'Operative findings: Large enhancing mass in right temporal lobe. Proceeded with gross total resection. All visible tumor removed. Dura closed primarily...'
        }
    ]

    print(f"✅ Gathered {len(imaging_pdfs)} imaging PDFs")
    print(f"✅ Gathered {len(progress_notes_raw)} progress notes (pre-filter)")
    print(f"✅ Gathered {len(operative_reports)} operative reports")
    print()

    # Agent 1: Filter progress notes for oncology-specific
    print("AGENT 1: Filtering progress notes for oncology-specific...")
    progress_notes = filter_oncology_notes(progress_notes_raw)
    stats = get_note_filtering_stats(progress_notes_raw)

    print(f"  Total notes: {stats['total_notes']}")
    print(f"  Oncology notes: {stats['oncology_notes']} ({stats['oncology_percentage']}%)")
    print(f"  Excluded: {stats['excluded_notes']}")
    print(f"  Exclusion reasons: {stats['exclusion_reasons']}")
    print()

    # =========================================================================
    # PHASE 2: AGENT 1 QUERIES AGENT 2 FOR TARGETED EXTRACTIONS
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 2: AGENT 1 → AGENT 2 TARGETED EXTRACTION REQUESTS")
    print("="*80 + "\n")

    # Request 1: Extract tumor status from imaging PDF
    print("REQUEST 1: Extract tumor_status from imaging PDF")
    print("-" * 80)

    pdf_prompt = build_tumor_status_extraction_prompt(
        report=imaging_pdfs[0],
        context={'events_before': [], 'events_after': []}
    )

    print(f"Agent 1 sends to Agent 2:")
    print(f"  - Document: {imaging_pdfs[0]['document_reference_id']}")
    print(f"  - Prompt length: {len(pdf_prompt)} characters")
    print(f"  - Extraction type: tumor_status")
    print()

    # Simulate Agent 2 response
    agent2_response_1 = {
        'tumor_status': 'Increased',
        'confidence': 0.85,
        'evidence': 'Increased size of enhancing mass in right temporal lobe',
        'comparison_findings': 'Compared to prior, mass increased from 2.1 to 2.8 cm'
    }

    print(f"Agent 2 responds:")
    print(f"  tumor_status: {agent2_response_1['tumor_status']}")
    print(f"  confidence: {agent2_response_1['confidence']}")
    print(f"  evidence: {agent2_response_1['evidence']}")
    print()

    # Request 2: Extract EOR from operative report (GOLD STANDARD)
    print("\nREQUEST 2: Extract EOR from operative report (GOLD STANDARD)")
    print("-" * 80)

    op_prompt = build_operative_report_eor_extraction_prompt(
        operative_report=operative_reports[0],
        context={}
    )

    print(f"Agent 1 sends to Agent 2:")
    print(f"  - Document: {operative_reports[0]['procedure_id']}")
    print(f"  - Prompt length: {len(op_prompt)} characters")
    print(f"  - Extraction type: extent_of_resection (operative report - gold standard)")
    print()

    # Simulate Agent 2 response
    agent2_response_2 = {
        'extent_of_resection': 'Gross Total Resection',
        'confidence': 0.95,
        'surgeon_statement': 'All visible tumor removed',
        'residual_tumor_reason': None,
        'estimated_percent_resection': None,
        'complications': 'None'
    }

    print(f"Agent 2 responds:")
    print(f"  extent_of_resection: {agent2_response_2['extent_of_resection']}")
    print(f"  confidence: {agent2_response_2['confidence']}")
    print(f"  surgeon_statement: '{agent2_response_2['surgeon_statement']}'")
    print()

    # Request 3: Validate disease state from progress note
    print("\nREQUEST 3: Validate disease state from oncology progress note")
    print("-" * 80)

    progress_prompt = build_progress_note_disease_state_prompt(
        progress_note=progress_notes[0],
        context={}
    )

    print(f"Agent 1 sends to Agent 2:")
    print(f"  - Document: {progress_notes[0]['document_reference_id']}")
    print(f"  - Prompt length: {len(progress_prompt)} characters")
    print(f"  - Extraction type: clinical_disease_status validation")
    print()

    # Simulate Agent 2 response
    agent2_response_3 = {
        'clinical_disease_status': 'Responding',
        'confidence': 0.90,
        'oncologist_assessment': 'Post-op MRI shows gross total resection achieved',
        'neurological_exam': {
            'status': 'stable',
            'findings': 'Neurological exam stable'
        },
        'imaging_correlation': {
            'imaging_mentioned': 'yes',
            'imaging_interpretation': 'gross total resection',
            'agrees_with_imaging': 'yes'
        }
    }

    print(f"Agent 2 responds:")
    print(f"  clinical_disease_status: {agent2_response_3['clinical_disease_status']}")
    print(f"  confidence: {agent2_response_3['confidence']}")
    print(f"  oncologist_assessment: '{agent2_response_3['oncologist_assessment']}'")
    print()

    # =========================================================================
    # PHASE 3: AGENT 1 ADJUDICATES MULTI-SOURCE EOR
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 3: AGENT 1 ADJUDICATES MULTI-SOURCE EOR")
    print("="*80 + "\n")

    # Create EOR sources
    eor_sources = [
        EORSource(
            source_type='operative_report',
            source_id=operative_reports[0]['procedure_id'],
            source_date=operative_reports[0]['procedure_date'],
            eor='Gross Total Resection',
            confidence=0.95,
            evidence=agent2_response_2['surgeon_statement'],
            extracted_by='agent2'
        )
    ]

    # Simulate post-op imaging EOR (if available)
    # In production: Agent 1 would query for post-op imaging and send to Agent 2
    # For demo, assume it agrees
    eor_sources.append(
        EORSource(
            source_type='postop_imaging',
            source_id='DocumentReference/postop_mri',
            source_date=datetime(2018, 5, 29, 10, 0),
            eor='Gross Total Resection',
            confidence=0.85,
            evidence='No residual enhancing tumor identified',
            extracted_by='agent2'
        )
    )

    # Agent 1 performs adjudication
    adjudicator = EORAdjudicator()
    adjudication = adjudicator.adjudicate_eor(
        procedure_id=operative_reports[0]['procedure_id'],
        procedure_date=operative_reports[0]['procedure_date'],
        eor_sources=eor_sources
    )

    print("AGENT 1 ADJUDICATION RESULT:")
    print("-" * 80)
    print(f"  Final EOR: {adjudication.final_eor}")
    print(f"  Confidence: {adjudication.confidence}")
    print(f"  Primary Source: {adjudication.primary_source}")
    print(f"  Agreement: {adjudication.agreement}")
    print(f"  Sources Assessed: {len(adjudication.sources_assessed)}")
    print(f"  Reasoning: {adjudication.adjudication_reasoning}")
    print()

    # =========================================================================
    # PHASE 4: AGENT 1 CLASSIFIES EVENT TYPE
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 4: AGENT 1 CLASSIFIES EVENT TYPE")
    print("="*80 + "\n")

    print("Agent 1 analyzes surgical history and tumor progression...")
    print()

    # Simulate event type classification
    # In production: EventTypeClassifier would use timeline database

    surgical_history = [
        {
            'procedure_date': datetime(2018, 5, 28),
            'extent_of_resection': 'Gross Total Resection',
            'procedure_id': operative_reports[0]['procedure_id']
        }
    ]

    prior_tumor_events = []  # This is first tumor event

    print("AGENT 1 ANALYSIS:")
    print("-" * 80)
    print(f"  Prior tumor events: {len(prior_tumor_events)}")
    print(f"  Surgical history: {len(surgical_history)} surgeries")
    print(f"  Most recent surgery: {surgical_history[0]['procedure_date']} - {surgical_history[0]['extent_of_resection']}")
    print()

    print("AGENT 1 CLASSIFICATION LOGIC:")
    print("  → No prior tumor events")
    print("  → This is the FIRST documented tumor event")
    print("  → Classification: Initial CNS Tumor")
    print()

    event_type_classification = {
        'event_type': 'Initial CNS Tumor',
        'confidence': 0.95,
        'reasoning': 'First documented tumor event in patient timeline'
    }

    print(f"RESULT:")
    print(f"  event_type: {event_type_classification['event_type']}")
    print(f"  confidence: {event_type_classification['confidence']}")
    print(f"  reasoning: {event_type_classification['reasoning']}")
    print()

    # =========================================================================
    # PHASE 5: AGENT 1 RESOLVES TEMPORAL INCONSISTENCY
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 5: AGENT 1 RESOLVES TEMPORAL INCONSISTENCY")
    print("="*80 + "\n")

    print("DETECTED INCONSISTENCY:")
    print("-" * 80)
    print("  Event 1 (May 27): tumor_status = Increased")
    print("  Event 2 (May 29): tumor_status = Decreased")
    print("  Issue: 2-day rapid change")
    print()

    print("AGENT 1 MULTI-SOURCE ANALYSIS:")
    print("-" * 80)
    print("  1. Imaging PDF (May 27): Increased tumor size")
    print("  2. Operative Report (May 28): Gross Total Resection")
    print("  3. Progress Note (May 29): Post-op, GTR achieved")
    print()

    print("AGENT 1 ADJUDICATION:")
    print("-" * 80)
    print("  ✓ May 27 imaging correctly shows 'Increased' tumor")
    print("  ✓ May 28 surgery performed GTR")
    print("  ✓ May 29 'Decreased' reflects post-operative tumor removal")
    print("  → NOT an inconsistency - surgical intervention explains change")
    print()

    print("RESOLUTION:")
    print(f"  Action: keep_both")
    print(f"  Reasoning: Temporal change explained by GTR on May 28")
    print(f"  Confidence: 0.95")
    print()

    # =========================================================================
    # PHASE 6: AGENT 1 GENERATES PATIENT QA REPORT
    # =========================================================================
    print("\n" + "="*80)
    print("PHASE 6: AGENT 1 GENERATES PATIENT QA REPORT")
    print("="*80 + "\n")

    qa_report = {
        'patient_id': patient_id,
        'extraction_session_id': 'session_20251020',
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_events_processed': 2,
            'inconsistencies_detected': 1,
            'inconsistencies_resolved': 1,
            'agent2_queries': 3,
            'multi_source_adjudications': 1
        },
        'event_type_classifications': [
            {
                'event_date': '2018-05-27',
                'event_type': 'Initial CNS Tumor',
                'confidence': 0.95
            }
        ],
        'eor_adjudications': [
            {
                'procedure_date': '2018-05-28',
                'final_eor': 'Gross Total Resection',
                'confidence': 0.95,
                'sources': ['operative_report', 'postop_imaging'],
                'agreement': 'full_agreement'
            }
        ],
        'inconsistencies_resolved': [
            {
                'inconsistency_type': 'temporal',
                'description': 'Rapid tumor status change (Increased→Decreased in 2 days)',
                'resolution': 'Explained by GTR on May 28',
                'action': 'keep_both',
                'confidence': 0.95
            }
        ]
    }

    print("QA REPORT SUMMARY:")
    print("-" * 80)
    print(json.dumps(qa_report['summary'], indent=2))
    print()

    print("✅ Patient QA report generated")
    print(f"✅ All inconsistencies resolved: {qa_report['summary']['inconsistencies_resolved']}/{qa_report['summary']['inconsistencies_detected']}")
    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*80)
    print("WORKFLOW DEMONSTRATION COMPLETE")
    print("="*80 + "\n")

    print("AGENT 1 (Claude) ACTIONS:")
    print("  ✅ Gathered multi-source data (imaging, operative reports, progress notes)")
    print("  ✅ Filtered progress notes to oncology-specific (50% reduction)")
    print("  ✅ Sent 3 targeted extraction requests to Agent 2")
    print("  ✅ Adjudicated EOR from operative report + imaging (gold standard)")
    print("  ✅ Classified event_type as 'Initial CNS Tumor' (Agent 1 logic)")
    print("  ✅ Resolved temporal inconsistency via multi-source analysis")
    print("  ✅ Generated comprehensive patient QA report")
    print()

    print("AGENT 2 (MedGemma) ACTIONS:")
    print("  ✅ Extracted tumor_status from imaging PDF")
    print("  ✅ Extracted EOR from operative report (surgeon's statement)")
    print("  ✅ Validated disease state from progress note")
    print("  ✅ Provided confidence scores for all extractions")
    print("  ✅ No cross-source reconciliation (Agent 1's responsibility)")
    print()

    print("KEY ARCHITECTURAL POINTS:")
    print("  • Agent 2 extracts, Agent 1 adjudicates")
    print("  • Operative report = gold standard for EOR")
    print("  • Progress notes filtered and validated")
    print("  • Event type determined by Agent 1 based on surgical history")
    print("  • Iterative Agent 1 ↔ Agent 2 queries supported")
    print("  • All decisions documented in patient QA report")
    print()


if __name__ == "__main__":
    demonstrate_workflow()
