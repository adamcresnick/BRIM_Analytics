#!/usr/bin/env python3
"""
Test Single Extraction

Quick test of the multi-agent framework on one radiology report.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import MasterAgent, MedGemmaAgent
import json

def main():
    print("=" * 80)
    print("SINGLE EXTRACTION TEST")
    print("=" * 80)

    # Initialize
    print("\n1. Initializing agents...")
    medgemma = MedGemmaAgent(model_name='gemma2:27b', temperature=0.1)
    master = MasterAgent(
        timeline_db_path='data/timeline.duckdb',
        medgemma_agent=medgemma,
        dry_run=True
    )
    print("   ✓ Agents initialized")

    # Run extraction on single patient, limit to first event
    print("\n2. Running imaging classification on first event...")
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Get just first event for testing
    events = master.timeline.get_imaging_events_needing_extraction(patient_id)
    if len(events) == 0:
        print("   ✗ No imaging events found")
        return 1

    first_event_id = events.iloc[0]['event_id']
    print(f"   Testing on: {first_event_id}")

    # Get report and context
    report = master.timeline.get_radiology_report(first_event_id)
    context = master.timeline.get_event_context_window(first_event_id, 30, 30)

    print(f"   Report: {len(report['document_text'])} chars")
    print(f"   Date: {report['document_date']}")

    # Extract imaging classification
    result = master._extract_imaging_classification(
        event_id=first_event_id,
        report=report,
        context=context,
        patient_id=patient_id
    )

    print("\n3. Results:")
    print(f"   Success: {result['success']}")
    if result['success']:
        print(f"   Classification: {result['value']}")
        print(f"   Confidence: {result['confidence']:.2f}")
    else:
        print(f"   Error: {result.get('error', 'Unknown')}")

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)

    return 0

if __name__ == '__main__':
    sys.exit(main())
