#!/usr/bin/env python3
"""
Test the medication progress note prioritization fix
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
import logging
import pandas as pd
from datetime import datetime
from utils.progress_note_prioritization import ProgressNotePrioritizer
from utils.progress_note_filters import filter_oncology_notes

# Set up logging to see debug output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

PATIENT_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

# Connect to timeline database
conn = duckdb.connect('data/timeline.duckdb')

# Get medication changes from timeline
print("Fetching medication changes from timeline...")
med_changes_query = """
SELECT
    event_id as medication_id,
    event_date as change_date,
    description
FROM events
WHERE patient_id = ?
    AND event_type = 'Medication'
ORDER BY event_date
"""
med_changes = conn.execute(med_changes_query, [PATIENT_ID]).fetchdf()
print(f"Found {len(med_changes)} medication changes")
if len(med_changes) > 0:
    print(f"Date range: {med_changes['change_date'].min()} to {med_changes['change_date'].max()}")
    print(f"Sample medication dates: {med_changes['change_date'].head().tolist()}")
    print(f"Date types: {type(med_changes['change_date'].iloc[0])}")
else:
    print("No medication changes found - cannot test!")

# Get progress notes from Athena (simulated with sample data)
# In production this would query v_binary_files
# For testing, let's create sample notes around the medication dates
print("\nCreating sample progress notes around medication dates...")
sample_notes = []

if len(med_changes) == 0:
    print("Cannot create sample notes without medication data")
    conn.close()
    sys.exit(1)

# Create notes on same day, +3 days, +7 days for first few medication dates
for idx, row in med_changes.head(5).iterrows():
    med_date = row['change_date']

    # Note on same day
    sample_notes.append({
        'document_reference_id': f'note_same_day_{idx}',
        'dr_date': med_date,
        'dr_type_text': 'Oncology Progress Note',
        'dr_description': f'Visit on {med_date.date()}',
        'content_type': 'text/plain'
    })

    # Note 3 days after
    note_date_plus3 = med_date + pd.Timedelta(days=3)
    sample_notes.append({
        'document_reference_id': f'note_plus3_{idx}',
        'dr_date': note_date_plus3,
        'dr_type_text': 'Oncology Progress Note',
        'dr_description': f'Follow-up 3 days after',
        'content_type': 'text/plain'
    })

    # Note 7 days after (edge of window)
    note_date_plus7 = med_date + pd.Timedelta(days=7)
    sample_notes.append({
        'document_reference_id': f'note_plus7_{idx}',
        'dr_date': note_date_plus7,
        'dr_type_text': 'Oncology Progress Note',
        'dr_description': f'Follow-up 7 days after',
        'content_type': 'text/plain'
    })

print(f"Created {len(sample_notes)} sample progress notes")

# Convert medication changes to list of dicts
med_changes_list = med_changes.to_dict('records')

# Initialize prioritizer
print("\nInitializing ProgressNotePrioritizer...")
prioritizer = ProgressNotePrioritizer(post_event_window_days=7, include_final_note=True)

# Run prioritization
print("\n" + "="*80)
print("TESTING MEDICATION PROGRESS NOTE PRIORITIZATION")
print("="*80)

prioritized = prioritizer.prioritize_notes(
    progress_notes=sample_notes,
    surgeries=[],  # No surgeries for this test
    imaging_events=[],  # No imaging for this test
    medication_changes=med_changes_list
)

print("\n" + "="*80)
print("RESULTS")
print("="*80)
print(f"\nTotal prioritized notes: {len(prioritized)}")
print(f"  Post-medication-change: {sum(1 for p in prioritized if 'medication' in p.priority_reason)}")
print(f"  Pre-medication-change: {sum(1 for p in prioritized if p.priority_reason == 'pre_medication_change')}")
print(f"  Final note: {sum(1 for p in prioritized if p.priority_reason == 'final_note')}")

if sum(1 for p in prioritized if 'medication' in p.priority_reason) > 0:
    print("\n✅ SUCCESS: Medication progress notes are being prioritized!")
    print("\nSample prioritized medication notes:")
    for p in prioritized[:5]:
        if 'medication' in p.priority_reason:
            print(f"  - {p.priority_reason}: {p.note.get('dr_date')} ({p.days_from_event} days from event)")
else:
    print("\n❌ FAILURE: No medication progress notes prioritized!")
    print("The bug still exists.")

conn.close()
