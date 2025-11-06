#!/usr/bin/env python3
"""
V4.8: Clinical Summary Generator

Generates resident-style clinical handoff summaries with embedded timeline visualizations.
Follows best practices for medical handoffs (I-PASS framework).

Output: Markdown file with embedded timeline plot
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_date(date_str: Optional[str]) -> str:
    """Format ISO date to readable format."""
    if not date_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%b %d, %Y")
    except:
        return date_str


def generate_patient_summary(artifact_path: Path) -> str:
    """
    Generate resident-style clinical handoff summary.

    Based on I-PASS framework:
    - Illness severity
    - Patient summary
    - Action list
    - Situation awareness
    - Synthesis by receiver

    Args:
        artifact_path: Path to patient_timeline_artifact.json

    Returns:
        Markdown-formatted clinical summary
    """
    logger.info(f"Loading artifact from {artifact_path}")

    with open(artifact_path) as f:
        artifact = json.load(f)

    patient_id = artifact.get('patient_id', 'Unknown')
    demographics = artifact.get('demographics', {})
    who_diagnosis = artifact.get('who_diagnosis', {})
    timeline_events = artifact.get('timeline_events', [])

    # Extract key information
    age = demographics.get('age_at_diagnosis', 'Unknown')
    gender = demographics.get('gender', 'Unknown')
    who_dx = who_diagnosis.get('diagnosis', 'Unknown')
    who_grade = who_diagnosis.get('grade', 'Unknown')
    dx_date = format_date(who_diagnosis.get('classification_date'))

    # Group events by type
    surgeries = [e for e in timeline_events if e.get('event_type') == 'surgery']
    chemo_events = [e for e in timeline_events if 'chemo' in e.get('event_type', '').lower()]
    radiation_events = [e for e in timeline_events if 'radiation' in e.get('event_type', '').lower()]
    imaging_events = [e for e in timeline_events if e.get('event_type') == 'imaging']

    # Identify missing data
    missing_data = []

    # Check for missing chemotherapy end dates
    missing_chemo_end = sum(1 for e in chemo_events
                           if e.get('event_type') == 'chemotherapy_start'
                           and not e.get('therapy_end_date'))
    if missing_chemo_end > 0:
        missing_data.append(f"{missing_chemo_end} chemotherapy end date(s)")

    # Check for ongoing therapy
    ongoing_therapy = [e for e in chemo_events + radiation_events
                      if e.get('therapy_status') == 'ongoing']

    # Check for missing radiation end dates
    missing_rad_end = sum(1 for e in radiation_events
                         if e.get('event_type') == 'radiation_start'
                         and not e.get('date_at_radiation_stop')
                         and e.get('therapy_status') != 'ongoing')
    if missing_rad_end > 0:
        missing_data.append(f"{missing_rad_end} radiation end date(s)")

    # Check for missing extent of resection
    missing_eor = sum(1 for e in surgeries if not e.get('extent_of_resection'))
    if missing_eor > 0:
        missing_data.append(f"{missing_eor} extent of resection value(s)")

    # Generate markdown summary
    md = []
    md.append(f"# Clinical Summary: Patient {patient_id}")
    md.append(f"")
    md.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    md.append(f"")
    md.append(f"---")
    md.append(f"")

    # ONE-LINER (Like resident presenting to attending)
    md.append(f"## Patient Presentation")
    md.append(f"")
    one_liner = (f"This is a {age}-year-old {gender} with **{who_dx}, WHO Grade {who_grade}**, "
                f"diagnosed {dx_date}, who has undergone {len(surgeries)} surgical procedure(s), "
                f"{len(set(e.get('event_date') for e in chemo_events))} chemotherapy course(s), "
                f"and {len(set(e.get('event_date') for e in radiation_events))} radiation course(s).")
    md.append(one_liner)
    md.append(f"")

    # DIAGNOSIS
    md.append(f"## Diagnosis")
    md.append(f"")
    md.append(f"- **WHO 2021 Classification:** {who_dx}")
    md.append(f"- **Grade:** {who_grade}")
    md.append(f"- **Classification Date:** {dx_date}")
    if who_diagnosis.get('key_markers'):
        md.append(f"- **Key Molecular Markers:** {', '.join(who_diagnosis['key_markers'])}")
    md.append(f"- **Method:** {who_diagnosis.get('classification_method', 'Unknown')}")
    md.append(f"- **Confidence:** {who_diagnosis.get('confidence', 'Unknown')}")
    md.append(f"")

    # SURGICAL HISTORY
    md.append(f"## Surgical History ({len(surgeries)} procedures)")
    md.append(f"")
    if surgeries:
        for i, surg in enumerate(surgeries, 1):
            surg_date = format_date(surg.get('event_date'))
            procedure = surg.get('procedure_display', surg.get('procedure_type', 'Unknown procedure'))
            eor = surg.get('extent_of_resection', '**MISSING**')
            location = surg.get('clinical_features', {}).get('tumor_location', {}).get('anatomical_site', 'Unknown')
            institution = surg.get('clinical_features', {}).get('institution', {}).get('name', 'Unknown')

            md.append(f"### Surgery #{i}: {surg_date}")
            md.append(f"- **Procedure:** {procedure}")
            md.append(f"- **Extent of Resection:** {eor}")
            md.append(f"- **Location:** {location}")
            md.append(f"- **Institution:** {institution}")
            md.append(f"")
    else:
        md.append("*No surgical procedures documented.*")
        md.append(f"")

    # CHEMOTHERAPY HISTORY
    md.append(f"## Chemotherapy History")
    md.append(f"")
    chemo_starts = [e for e in chemo_events if e.get('event_type') == 'chemotherapy_start']
    if chemo_starts:
        for i, chemo in enumerate(chemo_starts, 1):
            start_date = format_date(chemo.get('event_date'))
            agents = chemo.get('agent_names', ['Unknown agents'])
            end_date = format_date(chemo.get('therapy_end_date'))
            status = chemo.get('therapy_status')
            treatment_line = chemo.get('relationships', {}).get('ordinality', {}).get('treatment_line', 'Unknown')

            md.append(f"### Course #{i} (Line {treatment_line}): {', '.join(agents)}")
            md.append(f"- **Start Date:** {start_date}")
            if status == 'ongoing':
                md.append(f"- **Status:** **ONGOING** (patient appears to still be on active therapy)")
            elif end_date and end_date != "Unknown":
                md.append(f"- **End Date:** {end_date}")
            else:
                md.append(f"- **End Date:** **MISSING**")
            md.append(f"")
    else:
        md.append("*No chemotherapy documented.*")
        md.append(f"")

    # RADIATION HISTORY
    md.append(f"## Radiation History")
    md.append(f"")
    rad_starts = [e for e in radiation_events if e.get('event_type') == 'radiation_start']
    if rad_starts:
        for i, rad in enumerate(rad_starts, 1):
            start_date = format_date(rad.get('event_date'))
            end_date = format_date(rad.get('date_at_radiation_stop'))
            status = rad.get('therapy_status')
            fractions = rad.get('total_fractions', 'Unknown')
            dose = rad.get('total_dose_gy', 'Unknown')
            course = rad.get('relationships', {}).get('ordinality', {}).get('radiation_course', 'Unknown')

            md.append(f"### Course #{i} (Radiation Course {course})")
            md.append(f"- **Start Date:** {start_date}")
            if status == 'ongoing':
                md.append(f"- **Status:** **ONGOING** (patient appears to still be on active therapy)")
            elif end_date and end_date != "Unknown":
                md.append(f"- **End Date:** {end_date}")
            else:
                md.append(f"- **End Date:** **MISSING**")
            md.append(f"- **Total Fractions:** {fractions}")
            md.append(f"- **Total Dose:** {dose} Gy")
            md.append(f"")
    else:
        md.append("*No radiation therapy documented.*")
        md.append(f"")

    # IMAGING SURVEILLANCE
    md.append(f"## Imaging Surveillance")
    md.append(f"")
    md.append(f"**Total imaging studies:** {len(imaging_events)}")
    md.append(f"")

    # Most recent imaging
    if imaging_events:
        recent_imaging = sorted(imaging_events,
                              key=lambda x: x.get('event_date', ''),
                              reverse=True)[:3]
        md.append(f"### Most Recent Imaging (last 3 studies)")
        md.append(f"")
        for img in recent_imaging:
            img_date = format_date(img.get('event_date'))
            img_type = img.get('imaging_type', 'Unknown')
            rano = img.get('rano_assessment', 'Not assessed')
            md.append(f"- **{img_date}:** {img_type} - RANO: {rano}")
        md.append(f"")

    # DATA GAPS AND ACTION ITEMS
    md.append(f"## Data Quality & Missing Information")
    md.append(f"")
    if missing_data or ongoing_therapy:
        md.append(f"### Missing Data Elements")
        md.append(f"")
        if missing_data:
            for item in missing_data:
                md.append(f"- {item}")
        md.append(f"")

        if ongoing_therapy:
            md.append(f"### Ongoing Therapy")
            md.append(f"")
            md.append(f"The following treatments appear to be ongoing based on recent clinical notes:")
            md.append(f"")
            for therapy in ongoing_therapy:
                therapy_type = "Chemotherapy" if 'chemo' in therapy.get('event_type', '') else "Radiation"
                start_date = format_date(therapy.get('event_date'))
                agents = therapy.get('agent_names', ['Unknown'])
                md.append(f"- **{therapy_type}** started {start_date}: {', '.join(agents)}")
            md.append(f"")
    else:
        md.append("*No missing data elements identified.*")
        md.append(f"")

    # TIMELINE VISUALIZATION
    md.append(f"---")
    md.append(f"")
    md.append(f"## Clinical Journey Timeline")
    md.append(f"")
    md.append(f"![Clinical Timeline](timeline_enhanced.png)")
    md.append(f"")
    md.append(f"*Interactive version available in `timeline.html`*")
    md.append(f"")

    # METADATA
    md.append(f"---")
    md.append(f"")
    md.append(f"## Document Metadata")
    md.append(f"")
    md.append(f"- **Patient ID:** `{patient_id}`")
    md.append(f"- **Total Timeline Events:** {len(timeline_events)}")
    md.append(f"- **Date Range:** {format_date(min(e.get('event_date', '') for e in timeline_events if e.get('event_date')))} to {format_date(max(e.get('event_date', '') for e in timeline_events if e.get('event_date')))}")
    md.append(f"- **Abstraction Date:** {datetime.now().strftime('%B %d, %Y')}")
    md.append(f"")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Generate clinical summary from timeline artifact")
    parser.add_argument("artifact_path", type=Path, help="Path to patient_timeline_artifact.json")
    parser.add_argument("--output", "-o", type=Path, help="Output path (default: <artifact_dir>/clinical_summary.md)")

    args = parser.parse_args()

    if not args.artifact_path.exists():
        logger.error(f"Artifact not found: {args.artifact_path}")
        return 1

    # Generate summary
    summary = generate_patient_summary(args.artifact_path)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.artifact_path.parent / "clinical_summary.md"

    # Write summary
    logger.info(f"Writing clinical summary to {output_path}")
    output_path.write_text(summary)

    logger.info("✅ Clinical summary generated successfully")
    logger.info(f"   Output: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
