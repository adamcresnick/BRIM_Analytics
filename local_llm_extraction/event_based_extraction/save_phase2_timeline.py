"""
Save Phase 2 Timeline Results to JSON
"""

import json
from pathlib import Path
from phase1_structured_harvester import StructuredDataHarvester
from phase2_timeline_builder import ClinicalTimelineBuilder
from datetime import datetime

# Configuration
staging_path = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files"
patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
birth_date = "2005-05-13"

# Phase 1: Harvest structured data
harvester = StructuredDataHarvester(staging_path)
structured_features = harvester.harvest_for_patient(patient_id, birth_date)

# Phase 2: Build timeline
timeline_builder = ClinicalTimelineBuilder(staging_path, structured_features)
timeline = timeline_builder.build_timeline(patient_id, birth_date)

# Convert timeline to JSON-serializable format
timeline_json = []
for event in timeline:
    event_dict = {
        'event_id': event.event_id,
        'event_type': event.event_type,
        'event_date': event.event_date.isoformat(),
        'age_at_event_days': event.age_at_event_days,
        'description': event.description,
        'encounter_id': event.encounter_id,
        'procedure_codes': event.procedure_codes,
        'diagnosis_codes': event.diagnosis_codes,
        'binary_references': event.binary_references[:5] if event.binary_references else [],  # Limit to 5 for brevity
        'imaging_references': event.imaging_references,
        'measurements': event.measurements,
        'metadata': {k: str(v) if hasattr(v, '__str__') else v for k, v in event.metadata.items()},
        'parent_event_id': event.parent_event_id,
        'related_events': event.related_events
    }
    timeline_json.append(event_dict)

# Get summary
summary = timeline_builder.get_timeline_summary()

# Combine into final output
output = {
    'extraction_date': datetime.now().isoformat(),
    'patient_id': patient_id,
    'birth_date': birth_date,
    'summary': summary,
    'timeline': timeline_json
}

# Save to file
output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
output_path.mkdir(exist_ok=True)
output_file = output_path / f"phase2_timeline_{patient_id}.json"

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"Phase 2 Timeline saved to: {output_file}")
print(f"Total events in timeline: {len(timeline)}")
print(f"Event types: {summary['event_types']}")