"""
Progress Note Filtering for Oncology-Specific Notes

Identifies oncology progress notes from DocumentReference based on metadata.
Excludes non-relevant notes (telephone, nursing, social work, etc.)
"""

from typing import Dict, List, Any
import re


# Oncology-specific note types (dr_type_text patterns)
ONCOLOGY_NOTE_TYPES = {
    'oncology',
    'hematology-oncology',
    'neuro-oncology',
    'medical oncology',
    'pediatric oncology',
    'radiation oncology',
    'progress notes',
    'assessment & plan',
    'consult note',
    'h&p'
}

# Oncology-related keywords in note titles/descriptions
ONCOLOGY_KEYWORDS = {
    'oncology',
    'chemotherapy',
    'radiation',
    'tumor board',
    'cancer',
    'malignancy',
    'neoplasm',
    'glioma',
    'medulloblastoma',
    'ependymoma',
    'astrocytoma',
    'treatment planning',
    'disease progression',
    'surveillance'
}

# Exclude these note types (not relevant for disease state)
EXCLUDED_NOTE_TYPES = {
    'telephone',
    'phone',
    'nurse',
    'nursing',
    'social work',
    'case management',
    'nutrition',
    'pharmacy',
    'lab',
    'radiology',
    'pathology',
    'administrative',
    'scheduling',
    'referral',
    'authorization'
}

# Exclude notes with these keywords
EXCLUDED_KEYWORDS = {
    'telephone encounter',
    'phone call',
    'med refill',
    'prescription refill',
    'lab results only',
    'appointment reminder',
    'no show',
    'cancelled'
}


def is_oncology_note(note: Dict[str, Any]) -> bool:
    """
    Determine if a progress note is oncology-specific.

    Args:
        note: DocumentReference record with dr_type_text, dr_description, content_title

    Returns:
        True if oncology-specific note, False otherwise
    """
    dr_type = (note.get('dr_type_text', '') or '').lower()
    description = (note.get('dr_description', '') or '').lower()
    title = (note.get('content_title', '') or '').lower()

    combined_text = f"{dr_type} {description} {title}"

    # First: Exclude non-relevant notes
    for excluded_type in EXCLUDED_NOTE_TYPES:
        if excluded_type in combined_text:
            return False

    for excluded_keyword in EXCLUDED_KEYWORDS:
        if excluded_keyword in combined_text:
            return False

    # Second: Include if matches oncology note type
    for onc_type in ONCOLOGY_NOTE_TYPES:
        if onc_type in dr_type:
            return True

    # Third: Include if contains oncology keywords
    for keyword in ONCOLOGY_KEYWORDS:
        if keyword in combined_text:
            return True

    # Default: exclude
    return False


def filter_oncology_notes(notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter list of progress notes to only oncology-specific notes.

    Args:
        notes: List of DocumentReference records

    Returns:
        Filtered list of oncology-specific notes
    """
    return [note for note in notes if is_oncology_note(note)]


def categorize_progress_notes(notes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize progress notes into oncology vs. excluded.

    Args:
        notes: List of DocumentReference records

    Returns:
        Dictionary with 'oncology' and 'excluded' lists
    """
    oncology = []
    excluded = []

    for note in notes:
        if is_oncology_note(note):
            oncology.append(note)
        else:
            excluded.append(note)

    return {
        'oncology': oncology,
        'excluded': excluded
    }


def get_note_filtering_stats(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate statistics about note filtering.

    Args:
        notes: List of DocumentReference records

    Returns:
        Statistics dictionary
    """
    categorized = categorize_progress_notes(notes)
    oncology = categorized['oncology']
    excluded = categorized['excluded']

    # Count exclusion reasons
    exclusion_reasons = {}
    for note in excluded:
        combined_text = f"{note.get('dr_type_text', '')} {note.get('dr_description', '')}".lower()

        found_reason = False
        for excluded_type in EXCLUDED_NOTE_TYPES:
            if excluded_type in combined_text:
                exclusion_reasons[excluded_type] = exclusion_reasons.get(excluded_type, 0) + 1
                found_reason = True
                break

        if not found_reason:
            for excluded_keyword in EXCLUDED_KEYWORDS:
                if excluded_keyword in combined_text:
                    exclusion_reasons[excluded_keyword] = exclusion_reasons.get(excluded_keyword, 0) + 1
                    break

    return {
        'total_notes': len(notes),
        'oncology_notes': len(oncology),
        'excluded_notes': len(excluded),
        'oncology_percentage': round(100 * len(oncology) / len(notes), 1) if notes else 0,
        'exclusion_reasons': exclusion_reasons
    }


# CLI for testing
if __name__ == "__main__":
    import sys
    import json

    # Test with sample note
    test_note = {
        'dr_type_text': 'Oncology Progress Note',
        'dr_description': 'Follow-up visit for brain tumor surveillance',
        'content_title': 'Pediatric Neuro-Oncology Visit'
    }

    print("Testing progress note filter...")
    print(f"Test note: {test_note}")
    print(f"Is oncology note: {is_oncology_note(test_note)}\n")

    # Test exclusions
    excluded_note = {
        'dr_type_text': 'Telephone Encounter',
        'dr_description': 'Med refill request',
        'content_title': 'Phone call'
    }

    print(f"Excluded note: {excluded_note}")
    print(f"Is oncology note: {is_oncology_note(excluded_note)}\n")
