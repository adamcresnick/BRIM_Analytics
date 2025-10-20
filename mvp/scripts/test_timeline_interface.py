#!/usr/bin/env python3
"""
Test TimelineQueryInterface

Validates that the query interface works correctly with real patient data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from timeline_query_interface import TimelineQueryInterface
import pandas as pd

DUCKDB_PATH = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/data/timeline.duckdb"
TEST_PATIENT_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"

def test_database_stats(tqi: TimelineQueryInterface):
    """Test getting database statistics"""
    print("=" * 80)
    print("DATABASE STATISTICS")
    print("=" * 80)

    stats = tqi.get_database_stats()

    print(f"\nPatients: {stats['patient_count']}")

    print("\nEvent Counts:")
    for event in stats['event_counts']:
        print(f"  {event['event_type']}: {event['count']}")

    print("\nDocument Counts:")
    for doc in stats['document_counts']:
        print(f"  {doc['document_type']}: {doc['count']}")

    print("\nExtraction Counts:")
    if stats['extraction_counts']:
        for ext in stats['extraction_counts']:
            print(f"  {ext['variable_name']}: {ext['count']}")
    else:
        print("  (none yet)")


def test_patient_timeline(tqi: TimelineQueryInterface):
    """Test getting patient timeline"""
    print("\n" + "=" * 80)
    print(f"PATIENT TIMELINE: {TEST_PATIENT_ID}")
    print("=" * 80)

    # Get patient info
    patient_info = tqi.get_patient_info(TEST_PATIENT_ID)
    print(f"\nPatient Info:")
    print(f"  Birth Date: {patient_info['birth_date']}")
    print(f"  First Treatment: {patient_info['first_treatment_date']}")

    # Get all events
    timeline = tqi.get_patient_timeline(TEST_PATIENT_ID)
    print(f"\nTotal Events: {len(timeline)}")

    # Get imaging events only
    imaging = tqi.get_patient_timeline(TEST_PATIENT_ID, event_type='Imaging')
    print(f"Imaging Events: {len(imaging)}")

    # Show recent imaging
    print("\nMost Recent Imaging Events:")
    recent = imaging.nlargest(5, 'event_date')[['event_date', 'description', 'disease_phase', 'days_since_diagnosis']]
    print(recent.to_string(index=False))


def test_imaging_needing_extraction(tqi: TimelineQueryInterface):
    """Test finding imaging events needing extraction"""
    print("\n" + "=" * 80)
    print("IMAGING EVENTS NEEDING EXTRACTION")
    print("=" * 80)

    imaging = tqi.get_imaging_events_needing_extraction(TEST_PATIENT_ID)

    print(f"\nTotal imaging needing extraction: {len(imaging)}")
    print(f"With reports: {imaging['has_report'].sum()}")
    print(f"Already extracted: {imaging['already_extracted'].sum()}")

    if len(imaging) > 0:
        print("\nSample (first 5):")
        sample = imaging.head(5)[['event_date', 'description', 'has_report', 'report_length', 'disease_phase']]
        print(sample.to_string(index=False))


def test_radiology_report_retrieval(tqi: TimelineQueryInterface):
    """Test retrieving radiology reports"""
    print("\n" + "=" * 80)
    print("RADIOLOGY REPORT RETRIEVAL")
    print("=" * 80)

    # Get all reports
    reports = tqi.get_all_radiology_reports(TEST_PATIENT_ID)
    print(f"\nTotal radiology reports: {len(reports)}")

    if len(reports) > 0:
        print("\nReport lengths:")
        print(f"  Average: {reports['char_count'].mean():.0f} chars")
        print(f"  Max: {reports['char_count'].max()} chars")
        print(f"  Min: {reports['char_count'].min()} chars")

        # Get a specific report
        event_id = reports.iloc[0]['source_event_id']
        print(f"\nRetrieving report for event: {event_id}")

        report = tqi.get_radiology_report(event_id)
        if report:
            print(f"  Document ID: {report['document_id']}")
            print(f"  Date: {report['event_date']}")
            print(f"  Length: {report['char_count']} chars")
            print(f"  Disease Phase: {report['disease_phase']}")
            print(f"  Days Since Diagnosis: {report['days_since_diagnosis']}")
            print(f"  Metadata: {report['metadata']}")
            print(f"\n  Report Preview (first 200 chars):")
            print(f"  {report['document_text'][:200]}...")


def test_event_context_window(tqi: TimelineQueryInterface):
    """Test getting event context window"""
    print("\n" + "=" * 80)
    print("EVENT CONTEXT WINDOW")
    print("=" * 80)

    # Get an imaging event
    imaging = tqi.get_patient_timeline(TEST_PATIENT_ID, event_type='Imaging')
    if len(imaging) > 0:
        event_id = imaging.iloc[0]['event_id']
        event_date = imaging.iloc[0]['event_date']

        print(f"\nGetting context for imaging event: {event_id}")
        print(f"Event Date: {event_date}")

        context = tqi.get_event_context_window(event_id, days_before=30, days_after=30)

        print(f"\nContext window (±30 days):")
        print(f"  Target Event: {context['target_event']['description']}")
        print(f"  Events in window: {len(context['context_events'])}")
        print(f"  Active medications: {len(context['active_medications'])}")
        print(f"  Recent procedures: {len(context['recent_procedures'])}")

        if len(context['context_events']) > 0:
            print("\n  Sample events in window:")
            sample = context['context_events'].head(5)[['event_date', 'event_type', 'description']]
            print(sample.to_string(index=False))


def test_active_treatments(tqi: TimelineQueryInterface):
    """Test getting active treatments at a date"""
    print("\n" + "=" * 80)
    print("ACTIVE TREATMENTS AT DATE")
    print("=" * 80)

    # Get an imaging event date
    imaging = tqi.get_patient_timeline(TEST_PATIENT_ID, event_type='Imaging')
    if len(imaging) > 0:
        event_date = pd.to_datetime(imaging.iloc[0]['event_date'])

        print(f"\nChecking active treatments at: {event_date.date()}")

        treatments = tqi.get_active_treatments_at_date(TEST_PATIENT_ID, event_date)

        print(f"  Medications on/before this date: {len(treatments)}")

        if len(treatments) > 0:
            print("\n  Most recent medications:")
            recent = treatments.head(5)[['event_date', 'event_category', 'description']]
            print(recent.to_string(index=False))


def main():
    print("=" * 80)
    print("TIMELINE QUERY INTERFACE TEST")
    print("=" * 80)

    with TimelineQueryInterface(DUCKDB_PATH) as tqi:
        # Run all tests
        test_database_stats(tqi)
        test_patient_timeline(tqi)
        test_imaging_needing_extraction(tqi)
        test_radiology_report_retrieval(tqi)
        test_event_context_window(tqi)
        test_active_treatments(tqi)

    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()
