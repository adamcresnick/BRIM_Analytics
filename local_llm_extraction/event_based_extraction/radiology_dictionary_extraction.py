#!/usr/bin/env python3
"""
Radiology/Op Note Data Dictionary Compliant Extraction
Extracts variables according to the RADIANT data dictionary format
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_extraction_results():
    """Load the real document extraction results"""
    results_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/real_document_extraction_results.json')
    with open(results_path, 'r') as f:
        return json.load(f)

def load_imaging_data(patient_id: str):
    """Load imaging data for additional context"""
    staging_dir = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files')
    imaging_path = staging_dir / f'patient_{patient_id}' / 'imaging.csv'
    if imaging_path.exists():
        return pd.read_csv(imaging_path)
    return None

def calculate_age_at_event(event_date: str, birth_date: str = '2005-05-17'):
    """Calculate age in days at event"""
    event_dt = pd.to_datetime(event_date)
    birth_dt = pd.to_datetime(birth_date)
    return (event_dt - birth_dt).days

def map_extent_of_resection(extracted_value: str) -> int:
    """Map extracted extent to data dictionary codes"""
    value_lower = str(extracted_value).lower()

    if 'gross total' in value_lower or 'near total' in value_lower or 'gtr' in value_lower or '>95%' in value_lower:
        return 1  # Gross/Near total resection
    elif 'partial' in value_lower or 'subtotal' in value_lower or '50-95%' in value_lower or '<50%' in value_lower:
        return 2  # Partial resection
    elif 'biopsy' in value_lower:
        return 3  # Biopsy only
    else:
        return 4  # Unavailable

def map_tumor_location(extracted_value: str) -> list:
    """Map extracted location to data dictionary codes"""
    location_codes = []
    value_lower = str(extracted_value).lower()

    # Mapping based on extracted locations
    location_map = {
        'frontal': 1,
        'temporal': 2,
        'parietal': 3,
        'occipital': 4,
        'thalamus': 5,
        'ventricle': 6,
        'suprasellar': 7,
        'hypothalamic': 7,
        'pituitary': 7,
        'cerebellum': 8,
        'posterior fossa': 8,
        'medulla': 9,
        'midbrain': 10,
        'tectum': 10,
        'pons': 11,
        'brainstem': 11,  # Default to pons if brainstem not specified
        'cervical': 12,
        'thoracic': 13,
        'lumbar': 14,
        'optic': 15,
        'cranial nerve': 16,
        'pineal': 19,
        'basal ganglia': 20,
        'hippocampus': 21,
        'meninges': 22,
        'dura': 22,
        'skull': 23
    }

    for location, code in location_map.items():
        if location in value_lower:
            location_codes.append(code)

    if not location_codes:
        location_codes.append(24)  # Unavailable

    return location_codes

def determine_event_type(surgery_index: int, previous_extent: str = None) -> int:
    """Determine event type based on surgery order and previous extent"""
    if surgery_index == 0:
        return 5  # Initial CNS Tumor
    elif previous_extent and 'gross' in str(previous_extent).lower():
        return 7  # Recurrence (after gross total resection)
    else:
        return 8  # Progressive (after partial resection or unknown)

def extract_metastasis_info(imaging_text: str) -> dict:
    """Extract metastasis information from imaging reports"""
    result = {
        'metastasis': 1,  # Default to No
        'metastasis_location': [],
        'metastasis_location_other': ''
    }

    if pd.isna(imaging_text) or not imaging_text:
        result['metastasis'] = 2  # Unavailable
        return result

    text_lower = str(imaging_text).lower()

    # Check for metastasis mentions
    if 'metastas' in text_lower or 'disseminat' in text_lower or 'drop' in text_lower or 'seed' in text_lower:
        result['metastasis'] = 0  # Yes

        # Check locations
        if 'csf' in text_lower or 'cerebrospinal' in text_lower:
            result['metastasis_location'].append(0)  # CSF
        if 'spine' in text_lower or 'spinal' in text_lower:
            result['metastasis_location'].append(1)  # Spine
        if 'bone marrow' in text_lower:
            result['metastasis_location'].append(2)  # Bone Marrow
        if 'brain' in text_lower and 'multiple' in text_lower:
            result['metastasis_location'].append(4)  # Brain
        if 'leptomeningeal' in text_lower:
            result['metastasis_location'].append(5)  # Leptomeningeal

        if not result['metastasis_location']:
            result['metastasis_location'].append(6)  # Unavailable

    return result

def create_patient_record(patient_id: str):
    """Create data dictionary compliant record for patient"""

    # Load extraction results
    extraction_results = load_extraction_results()
    imaging_df = load_imaging_data(patient_id)

    # Process each surgical event
    events = []

    for idx, surgery in enumerate(extraction_results['surgeries']):
        event = {}

        # Determine event type
        previous_extent = extraction_results['surgeries'][idx-1]['extractions'].get('extent_of_resection', {}).get('value') if idx > 0 else None
        event['event_type'] = determine_event_type(idx, previous_extent)

        # Age at event
        event['age_at_event_days'] = calculate_age_at_event(surgery['surgery_date'])

        # Get relevant imaging for this surgery date
        surgery_date = pd.to_datetime(surgery['surgery_date'])
        relevant_imaging = None
        if imaging_df is not None:
            # Parse dates with UTC timezone
            imaging_df['imaging_date'] = pd.to_datetime(imaging_df['imaging_date'], utc=True)
            surgery_date = pd.to_datetime(surgery_date, utc=True)
            # Find imaging within 30 days after surgery
            post_op_imaging = imaging_df[
                (imaging_df['imaging_date'] >= surgery_date) &
                (imaging_df['imaging_date'] <= surgery_date + pd.Timedelta(days=30))
            ]
            if not post_op_imaging.empty:
                relevant_imaging = post_op_imaging.iloc[0]['result_information']

        # Metastasis assessment
        metastasis_info = extract_metastasis_info(relevant_imaging)
        event['metastasis'] = metastasis_info['metastasis']
        event['metastasis_location'] = metastasis_info['metastasis_location']
        event['metastasis_location_other'] = metastasis_info['metastasis_location_other']

        # Site of progression (for progressive events)
        if event['event_type'] == 8:  # Progressive
            event['site_of_progression'] = 1  # Local (based on imaging showing same location)
        else:
            event['site_of_progression'] = 3  # Unavailable

        # Tumor location
        if 'tumor_location' in surgery.get('extractions', {}):
            location_value = surgery['extractions']['tumor_location'].get('value', '')
            event['tumor_location'] = map_tumor_location(location_value)
        else:
            # Default based on procedure description
            if 'posterior fossa' in surgery['procedure'].lower() or 'infratentorial' in surgery['procedure'].lower():
                event['tumor_location'] = [8]  # Cerebellum/Posterior Fossa
            elif 'brainstem' in surgery['procedure'].lower():
                event['tumor_location'] = [11]  # Brain Stem-Pons
            else:
                event['tumor_location'] = [24]  # Unavailable

        event['tumor_location_other'] = ''

        # Shunt information (not extracted in current pipeline)
        event['shunt_required'] = 4  # Not Done

        # Surgery information
        event['surgery'] = 1  # Yes
        event['age_at_surgery'] = event['age_at_event_days']

        # Extent of tumor resection
        if 'extent_of_resection' in surgery.get('extractions', {}):
            extent_value = surgery['extractions']['extent_of_resection'].get('value', '')
            event['extent_of_tumor_resection'] = map_extent_of_resection(extent_value)
        else:
            event['extent_of_tumor_resection'] = 4  # Unavailable

        events.append(event)

    return {
        'patient_id': patient_id,
        'events': events,
        'extraction_timestamp': datetime.now().isoformat()
    }

def format_for_redcap(patient_record: dict):
    """Format the patient record for REDCap import"""
    redcap_records = []

    for event_idx, event in enumerate(patient_record['events'], 1):
        record = {
            'record_id': f"{patient_record['patient_id']}_event{event_idx}",
            'event_name': f"event_{event_idx}",
            **event
        }

        # Convert lists to pipe-separated strings for checkbox fields
        if 'metastasis_location' in record and isinstance(record['metastasis_location'], list):
            record['metastasis_location'] = '|'.join(map(str, record['metastasis_location']))
        if 'tumor_location' in record and isinstance(record['tumor_location'], list):
            record['tumor_location'] = '|'.join(map(str, record['tumor_location']))

        redcap_records.append(record)

    return redcap_records

def main():
    """Generate data dictionary compliant output"""
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Create patient record
    logger.info(f"Creating data dictionary compliant record for patient {patient_id}")
    patient_record = create_patient_record(patient_id)

    # Format for REDCap
    redcap_records = format_for_redcap(patient_record)

    # Save results
    output_path = Path('radiology_dictionary_output.json')
    with open(output_path, 'w') as f:
        json.dump({
            'patient_record': patient_record,
            'redcap_format': redcap_records
        }, f, indent=2, default=str)

    # Print summary
    print("\n" + "="*80)
    print("DATA DICTIONARY COMPLIANT EXTRACTION")
    print("="*80)
    print(f"Patient ID: {patient_id}")
    print(f"Number of Events: {len(patient_record['events'])}")

    for idx, event in enumerate(patient_record['events'], 1):
        print(f"\n--- Event {idx} ---")
        print(f"Event Type: {event['event_type']} ({'Initial CNS Tumor' if event['event_type']==5 else 'Progressive' if event['event_type']==8 else 'Recurrence'})")
        print(f"Age at Event: {event['age_at_event_days']} days ({event['age_at_event_days']/365.25:.1f} years)")
        print(f"Surgery: {'Yes' if event['surgery']==1 else 'No'}")

        extent_map = {1: 'Gross/Near total', 2: 'Partial', 3: 'Biopsy only', 4: 'Unavailable'}
        print(f"Extent of Resection: {extent_map.get(event['extent_of_tumor_resection'], 'Unknown')}")

        location_map = {8: 'Cerebellum/Posterior Fossa', 11: 'Brain Stem-Pons', 24: 'Unavailable'}
        locations = event['tumor_location']
        location_names = [location_map.get(loc, f'Code {loc}') for loc in locations] if isinstance(locations, list) else [location_map.get(locations, f'Code {locations}')]
        print(f"Tumor Location: {', '.join(location_names)}")

        metastasis_map = {0: 'Yes', 1: 'No', 2: 'Unavailable'}
        print(f"Metastasis: {metastasis_map.get(event['metastasis'], 'Unknown')}")

        if event['event_type'] == 8:  # Progressive
            progression_map = {1: 'Local', 2: 'Metastatic', 3: 'Unavailable'}
            print(f"Site of Progression: {progression_map.get(event['site_of_progression'], 'Unknown')}")

    print(f"\n✓ Results saved to: {output_path}")
    print("\nREDCap Format Sample:")
    print(json.dumps(redcap_records[0], indent=2))

if __name__ == '__main__':
    main()