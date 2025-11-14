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


def _is_better_response(new_response: str, current_best: str) -> bool:
    """Determine if new_response is better than current_best (CR > PR > SD > PD)."""
    response_hierarchy = {
        'complete_response': 4,
        'complete response': 4,
        'partial_response': 3,
        'partial response': 3,
        'stable_disease': 2,
        'stable disease': 2,
        'progressive_disease': 1,
        'progressive disease': 1
    }
    new_score = response_hierarchy.get(new_response.lower(), 0)
    current_score = response_hierarchy.get(current_best.lower(), 0)
    return new_score > current_score


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
    demographics = artifact.get('patient_demographics', {})
    who_diagnosis = artifact.get('who_2021_classification', {})
    timeline_events = artifact.get('timeline_events', [])
    therapeutic_approach = artifact.get('therapeutic_approach')  # V5.0

    # Extract key information
    age = demographics.get('pd_age_years', 'Unknown')
    gender = demographics.get('pd_gender', 'Unknown')
    who_dx = who_diagnosis.get('who_2021_diagnosis', 'Unknown')
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
        # key_markers is a string, not a list
        md.append(f"- **Key Molecular Markers:** {who_diagnosis['key_markers']}")
    md.append(f"- **Method:** {who_diagnosis.get('classification_method', 'Unknown')}")
    md.append(f"- **Confidence:** {who_diagnosis.get('confidence', 'Unknown')}")
    md.append(f"")

    # SURGICAL HISTORY
    md.append(f"## Surgical History ({len(surgeries)} procedures)")
    md.append(f"")
    if surgeries:
        for i, surg in enumerate(surgeries, 1):
            surg_date = format_date(surg.get('event_date'))
            # V5.7 FIX: Use correct field names from timeline artifact
            procedure = surg.get('description', surg.get('procedure_display', surg.get('procedure_type', 'Unknown procedure')))
            eor = surg.get('extent_of_resection', '**MISSING**')
            # V5.7 FIX: tumor_location is at v41_tumor_location, not nested under clinical_features
            v41_location = surg.get('v41_tumor_location', {})
            # Extract locations from CBTN ontology mapping (returns list)
            if v41_location and v41_location.get('locations'):
                location = ', '.join(v41_location.get('locations', []))
            else:
                location = 'Unknown'
            # V5.7 FIX: institution uses 'value' not 'name'
            institution = surg.get('clinical_features', {}).get('institution', {}).get('value', 'Unknown') or 'Unknown'

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
            # V4.8.2: Use episode_start_datetime from V4.8 adjudication as primary source
            start_date = format_date(chemo.get('episode_start_datetime') or chemo.get('event_date'))

            # V4.8.1: Use comprehensive drug name fields with fallback hierarchy
            # Prefer: chemo_preferred_name > episode_drug_names > medication_name > agent_names
            agents_str = (chemo.get('chemo_preferred_name') or
                         chemo.get('episode_drug_names') or
                         chemo.get('medication_name') or
                         chemo.get('agent_names') or
                         'Unknown agents')

            # Handle both string and list formats
            if isinstance(agents_str, list):
                agents_display = ', '.join(agents_str)
            else:
                agents_display = agents_str

            # V4.8.1: Extract drug category and care plan (protocol) information
            drug_category = chemo.get('chemo_drug_category') or chemo.get('episode_drug_categories')
            care_plan = chemo.get('episode_care_plan_title')

            # V4.8.2: Prefer episode_end_datetime (from V4.8 adjudication) over therapy_end_date (from V4.6.3 note extraction)
            # V4.8 adjudication uses dosage instructions and is more reliable than note timestamps
            end_date_raw = chemo.get('episode_end_datetime') or chemo.get('therapy_end_date')

            # V4.8.3: Temporal validation - reject end dates BEFORE start dates
            end_date = None
            if end_date_raw:
                try:
                    start_dt_str = chemo.get('episode_start_datetime') or chemo.get('event_date')
                    if start_dt_str and end_date_raw:
                        start_dt = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end_date_raw.replace('Z', '+00:00'))

                        if end_dt < start_dt:
                            # Data quality issue - end date before start date
                            # Don't display this invalid end date
                            pass
                        else:
                            end_date = format_date(end_date_raw)
                    else:
                        end_date = format_date(end_date_raw)
                except:
                    # If parsing fails, use the formatted date
                    end_date = format_date(end_date_raw)

            status = chemo.get('therapy_status')
            treatment_line = chemo.get('relationships', {}).get('ordinality', {}).get('treatment_line', 'Unknown')

            md.append(f"### Course #{i} (Line {treatment_line}): {agents_display}")
            if drug_category:
                md.append(f"- **Drug Category:** {drug_category}")
            if care_plan:
                md.append(f"- **Protocol/Care Plan:** {care_plan}")
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
            end_date_raw = rad.get('date_at_radiation_stop') or rad.get('therapy_end_date')

            # V4.8.3: Temporal validation - reject end dates BEFORE start dates
            end_date = None
            if end_date_raw:
                try:
                    start_dt_str = rad.get('event_date')
                    if start_dt_str and end_date_raw:
                        start_dt = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end_date_raw.replace('Z', '+00:00'))

                        if end_dt < start_dt:
                            # Data quality issue - don't display invalid end date
                            pass
                        else:
                            end_date = format_date(end_date_raw)
                    else:
                        end_date = format_date(end_date_raw)
                except:
                    end_date = format_date(end_date_raw)

            status = rad.get('therapy_status')
            fractions = rad.get('total_fractions', 'Unknown')
            dose = rad.get('total_dose_gy', 'Unknown')
            course = rad.get('relationships', {}).get('ordinality', {}).get('radiation_course', 'Unknown')

            # V4.8.1: Extract care plan (protocol) and appointment information
            care_plan = rad.get('care_plan_titles')
            appointment_count = rad.get('total_appointments')
            fulfillment_rate = rad.get('appointment_fulfillment_rate_pct')

            md.append(f"### Course #{i} (Radiation Course {course})")
            if care_plan:
                md.append(f"- **Protocol/Care Plan:** {care_plan}")
            md.append(f"- **Start Date:** {start_date}")
            if status == 'ongoing':
                md.append(f"- **Status:** **ONGOING** (patient appears to still be on active therapy)")
            elif end_date and end_date != "Unknown":
                md.append(f"- **End Date:** {end_date}")
            else:
                md.append(f"- **End Date:** **MISSING**")
            md.append(f"- **Total Fractions:** {fractions}")
            md.append(f"- **Total Dose:** {dose} Gy")
            if appointment_count:
                md.append(f"- **Appointments:** {appointment_count} scheduled")
                if fulfillment_rate:
                    md.append(f"- **Fulfillment Rate:** {fulfillment_rate}%")
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

    # V5.0: THERAPEUTIC APPROACH SUMMARY
    if therapeutic_approach:
        md.append(f"## Treatment Summary (V5.0 Therapeutic Approach)")
        md.append(f"")

        lines_of_therapy = therapeutic_approach.get('lines_of_therapy', [])
        clinical_endpoints = therapeutic_approach.get('clinical_endpoints', {})

        md.append(f"**Number of Treatment Lines:** {len(lines_of_therapy)}")

        overall_metrics = clinical_endpoints.get('overall_metrics', {})
        if overall_metrics.get('time_to_first_progression_days'):
            md.append(f"**Time to First Progression:** {overall_metrics['time_to_first_progression_days']} days")

        md.append(f"")

        for line in lines_of_therapy:
            line_num = line.get('line_number')
            line_name = line.get('line_name', f"Line {line_num}")
            start_date = format_date(line.get('start_date'))
            end_date = format_date(line.get('end_date')) if line.get('end_date') else "Ongoing"
            duration = line.get('duration_days', '?')
            intent = line.get('treatment_intent', 'Unknown')

            regimen = line.get('regimen', {})
            regimen_name = regimen.get('regimen_name', 'Unknown regimen')
            protocol_ref = regimen.get('protocol_reference', '')
            confidence = regimen.get('match_confidence', 'unknown')

            md.append(f"### {line_name}")
            md.append(f"")
            md.append(f"- **Intent:** {intent.replace('_', ' ').title()}")
            md.append(f"- **Regimen:** {regimen_name}")
            if protocol_ref and protocol_ref != 'No standard protocol match':
                md.append(f"- **Protocol Reference:** {protocol_ref}")
            md.append(f"- **Protocol Match Confidence:** {confidence}")
            md.append(f"- **Start Date:** {start_date}")
            md.append(f"- **End Date:** {end_date}")
            if duration != '?':
                md.append(f"- **Duration:** {duration} days")

            # Response assessments
            assessments = line.get('response_assessments', [])
            if assessments:
                md.append(f"- **Response Assessments:** {len(assessments)} imaging study(ies)")
                best_response = None
                for assessment in assessments:
                    rano = assessment.get('rano_response')
                    if rano:
                        if not best_response or _is_better_response(rano, best_response):
                            best_response = rano
                if best_response:
                    md.append(f"- **Best Response:** {best_response.replace('_', ' ').title()}")

            # Chemotherapy cycles
            cycles = line.get('chemotherapy_cycles', [])
            if cycles:
                md.append(f"- **Chemotherapy Cycles:** {len(cycles)} cycle(s)")

            # Radiation courses
            radiation = line.get('radiation_courses', [])
            if radiation:
                for rad_course in radiation:
                    dose = rad_course.get('total_dose_gy', '?')
                    fractions = rad_course.get('fractions_delivered', '?')
                    frac_type = rad_course.get('fractionation_type', 'unknown')
                    md.append(f"- **Radiation:** {dose} Gy in {fractions} fractions ({frac_type})")

            # Reason for line change
            reason = line.get('reason_for_change', '')
            if reason and line_num < len(lines_of_therapy):
                md.append(f"- **Reason for Line Change:** {reason.replace('_', ' ').title()}")

            md.append(f"")

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
