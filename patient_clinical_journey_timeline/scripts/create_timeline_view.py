#!/usr/bin/env python3
"""
V4.7 Timeline Visualization Generator

Generates interactive HTML and publication-quality PDF timelines from patient JSON artifacts.
Integrates with V4.7 Investigation Engine results and color-codes by treatment lines.

Features:
- Treatment line color-coding for chemotherapy and radiation
- Stage-based visualization
- Investigation flag annotations
- PDF export via kaleido for publication-quality figures
- Interactive HTML with hover details
"""

import argparse
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_treatment_ordinality(event: Dict) -> Tuple[Optional[int], str]:
    """
    Extract treatment ordinality (line/course number) from event.

    Args:
        event: Timeline event dictionary

    Returns:
        Tuple of (ordinality_number, ordinality_label)
    """
    event_type = event.get('event_type', '').lower()

    # Check surgery_number
    if 'surgery' in event_type or 'procedure' in event_type:
        surgery_num = event.get('surgery_number')
        if surgery_num:
            return (surgery_num, f"Surgery #{surgery_num}")

    # Check chemotherapy treatment_line
    if 'chemo' in event_type:
        ordinality = event.get('relationships', {}).get('ordinality', {})
        treatment_line = ordinality.get('treatment_line')
        if treatment_line:
            return (treatment_line, f"Chemo Line {treatment_line}")

    # Check radiation course
    if 'radiation' in event_type:
        ordinality = event.get('relationships', {}).get('ordinality', {})
        radiation_course = ordinality.get('radiation_course')
        if radiation_course:
            return (radiation_course, f"Radiation Course {radiation_course}")

    return (None, "")


def extract_investigation_flags(event: Dict) -> List[str]:
    """
    Extract V4.7 investigation flags from event.

    Args:
        event: Timeline event dictionary

    Returns:
        List of investigation flag strings
    """
    flags = []

    # Check extent_of_resection sources
    eor = event.get('extent_of_resection_v4', {})
    if isinstance(eor, dict) and eor.get('sources'):
        for source in eor['sources']:
            flag = source.get('investigation_flag')
            if flag:
                flags.append(f"EOR: {flag}")

    # Check tumor_location sources
    location = event.get('clinical_features', {}).get('tumor_location', {})
    if isinstance(location, dict) and location.get('sources'):
        for source in location['sources']:
            flag = source.get('investigation_flag')
            if flag:
                flags.append(f"Location: {flag}")

    return flags


def categorize_event_type(event_type: str) -> str:
    """
    Categorize event type for consistent color-coding.

    Args:
        event_type: Event type string

    Returns:
        Category string for color grouping
    """
    event_type_lower = event_type.lower()

    if 'chemo' in event_type_lower:
        return "Chemotherapy"
    elif 'radiation' in event_type_lower:
        return "Radiation"
    elif 'surgery' in event_type_lower or 'procedure' in event_type_lower:
        return "Surgery/Procedure"
    elif 'imaging' in event_type_lower:
        return "Imaging"
    elif 'pathology' in event_type_lower:
        return "Pathology"
    elif 'molecular' in event_type_lower:
        return "Molecular"
    elif 'diagnosis' in event_type_lower:
        return "Diagnosis"
    elif 'complication' in event_type_lower:
        return "Complication"
    else:
        return "Other"


def create_timeline_from_json(
    json_path: Path,
    output_dir: Optional[Path] = None,
    export_pdf: bool = True
) -> Optional[Dict[str, Path]]:
    """
    Generate interactive HTML and PDF timelines from patient JSON artifact.

    Args:
        json_path: Path to patient timeline artifact JSON
        output_dir: Optional output directory (defaults to json_path.parent / 'visualizations')
        export_pdf: Whether to export PDF version (requires kaleido)

    Returns:
        Dictionary with paths to generated files, or None on failure
    """
    # --- Load JSON Data ---
    try:
        with open(json_path, 'r') as f:
            patient_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {json_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to read {json_path}: {e}")
        return None

    # --- Extract Patient Info (V4.7 Schema) ---
    patient_id = patient_data.get('patient_id', 'UnknownPatient')
    timeline_events = patient_data.get('timeline_events', [])
    who_diagnosis = patient_data.get('who_2021_classification', {}).get('diagnosis', 'Unknown')
    demographics = patient_data.get('patient_demographics', {})
    age_at_diagnosis = demographics.get('age_at_diagnosis_years', 'N/A')
    gender = demographics.get('gender', 'N/A')

    if not timeline_events:
        logger.warning(f"No timeline_events found in {json_path}")
        return None

    logger.info(f"Processing {len(timeline_events)} events for patient {patient_id}...")

    # --- Data Transformation ---
    df_data = []
    for event in timeline_events:
        event_type = event.get('event_type', 'Unknown')
        start_date_str = event.get('event_date')
        if not start_date_str:
            continue

        # Parse dates with error handling
        try:
            start_date = pd.to_datetime(start_date_str)
        except Exception as e:
            logger.warning(f"Invalid start date '{start_date_str}' in event {event.get('fhir_id')}: {e}")
            continue

        end_date_str = event.get('end_date')

        # Handle point-in-time vs. duration events
        if end_date_str:
            try:
                end_date = pd.to_datetime(end_date_str)
            except:
                end_date = start_date + pd.Timedelta(days=1)
        else:
            # Point events get 1-day duration for visibility
            end_date = start_date + pd.Timedelta(days=1)

        # Build descriptive task label (V4.7 schema)
        description = event.get('description', '')
        stage = event.get('stage', 'N/A')

        # Extract treatment ordinality
        ordinality_num, ordinality_label = extract_treatment_ordinality(event)

        # Build task label
        task_label_parts = [f"[Stage {stage}]", event_type.replace('_', ' ').title()]
        if ordinality_label:
            task_label_parts.append(ordinality_label)
        task_label_parts.append(f": {description[:80]}")
        task_label = " ".join(task_label_parts)

        # Categorize for base color-coding
        resource_type = categorize_event_type(event_type)

        # Create treatment line grouping for color-coding
        if ordinality_num is not None:
            # Use ordinality for color differentiation within category
            color_group = f"{resource_type} - {ordinality_label}"
        else:
            color_group = resource_type

        # Extract investigation flags
        investigation_flags = extract_investigation_flags(event)
        investigation_str = '; '.join(investigation_flags) if investigation_flags else None

        # Add confidence warnings if present
        confidence_warnings = []
        eor = event.get('extent_of_resection_v4', {})
        if isinstance(eor, dict) and eor.get('sources'):
            for source in eor['sources']:
                confidence = source.get('confidence', '').upper()
                if confidence in ['LOW', 'MEDIUM']:
                    confidence_warnings.append(f"EOR confidence: {confidence}")

        df_data.append({
            "Task": task_label,
            "Start": start_date,
            "Finish": end_date,
            "ResourceType": resource_type,
            "ColorGroup": color_group,
            "Stage": stage,
            "EventType": event_type,
            "Ordinality": ordinality_num if ordinality_num else 0,
            "OrdinalityLabel": ordinality_label if ordinality_label else "N/A",
            "InvestigationFlags": investigation_str,
            "ConfidenceWarnings": '; '.join(confidence_warnings) if confidence_warnings else None,
            "Description": description[:200]  # Truncate for hover
        })

    if not df_data:
        logger.warning("No processable events after transformation")
        return None

    df = pd.DataFrame(df_data)

    # Sort by start date for better visualization
    df = df.sort_values('Start')

    # --- Visualization ---
    logger.info("Creating interactive timeline visualization...")

    # Use ColorGroup for treatment line differentiation
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="ColorGroup",
        title=f"<b>Clinical Journey Timeline</b><br><sub>Patient: {patient_id} | WHO Dx: {who_diagnosis} | Age: {age_at_diagnosis} | Gender: {gender}</sub>",
        hover_data={
            "Task": False,  # Already in y-axis
            "Start": "|%Y-%m-%d",
            "Finish": "|%Y-%m-%d",
            "ResourceType": True,
            "Stage": True,
            "OrdinalityLabel": True,
            "InvestigationFlags": True,
            "ConfidenceWarnings": True,
            "Description": True,
            "ColorGroup": False  # Don't show in hover
        },
        labels={
            "Task": "Clinical Event",
            "ResourceType": "Event Category",
            "OrdinalityLabel": "Treatment Sequence",
            "InvestigationFlags": "V4.7 Investigation Flags",
            "ConfidenceWarnings": "Quality Warnings"
        }
    )

    # Customize layout
    fig.update_yaxes(autorange="reversed")  # Show events from top to bottom
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Clinical Events (Chronological)",
        legend_title="Event Category & Treatment Line",
        height=max(800, len(df_data) * 30),  # Dynamic height based on event count
        font=dict(size=10),
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01
        )
    )

    # Add stage boundary markers (vertical lines) - use add_shape instead of add_vline to avoid Timestamp issues
    stage_transitions = df.groupby('Stage')['Start'].min().sort_values()
    stage_colors = {
        '0': 'rgba(200, 200, 200, 0.5)',
        '1': 'rgba(173, 216, 230, 0.5)',
        '2': 'rgba(144, 238, 144, 0.5)',
        '3': 'rgba(255, 255, 224, 0.5)',
        '4': 'rgba(240, 128, 128, 0.5)',
        '5': 'rgba(255, 182, 193, 0.5)',
        '6': 'rgba(230, 230, 250, 0.5)'
    }

    for stage, start_date in stage_transitions.items():
        stage_str = str(stage)
        fig.add_shape(
            type="line",
            x0=start_date, x1=start_date,
            y0=0, y1=1,
            yref="paper",
            line=dict(
                color=stage_colors.get(stage_str, 'gray'),
                width=2,
                dash="dash"
            )
        )
        # Add annotation separately
        fig.add_annotation(
            x=start_date,
            y=1.02,
            yref="paper",
            text=f"Stage {stage}",
            showarrow=False,
            font=dict(size=10),
            bgcolor="white",
            bordercolor=stage_colors.get(stage_str, 'gray'),
            borderwidth=1
        )

    # --- Output ---
    if output_dir is None:
        output_dir = json_path.parent / 'visualizations'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean patient ID for filename
    clean_patient_id = patient_id.replace('Patient/', '').replace('/', '_')

    # Generate HTML
    html_filename = f"{clean_patient_id}_timeline.html"
    html_path = output_dir / html_filename
    fig.write_html(str(html_path))
    logger.info(f"✅ Generated HTML timeline: {html_path}")

    output_paths = {"html": html_path}

    # Generate PDF if requested
    if export_pdf:
        try:
            import kaleido
            pdf_filename = f"{clean_patient_id}_timeline.pdf"
            pdf_path = output_dir / pdf_filename

            # Update layout for PDF (better for printing)
            fig.update_layout(
                width=1400,
                height=max(1000, len(df_data) * 30)
            )

            fig.write_image(str(pdf_path), format='pdf')
            logger.info(f"✅ Generated PDF timeline: {pdf_path}")
            output_paths["pdf"] = pdf_path
        except ImportError:
            logger.warning("kaleido not installed - skipping PDF export. Install with: pip install kaleido")
        except Exception as e:
            logger.warning(f"Failed to generate PDF: {e}")

    # Generate summary statistics
    summary = {
        "total_events": len(df_data),
        "event_types": df['ResourceType'].value_counts().to_dict(),
        "stages": df['Stage'].value_counts().sort_index().to_dict(),
        "treatment_lines": {
            "chemotherapy": df[df['ResourceType'] == 'Chemotherapy']['Ordinality'].nunique(),
            "radiation": df[df['ResourceType'] == 'Radiation']['Ordinality'].nunique(),
            "surgery": df[df['ResourceType'] == 'Surgery/Procedure']['Ordinality'].nunique()
        },
        "investigation_flags": df['InvestigationFlags'].notna().sum(),
        "confidence_warnings": df['ConfidenceWarnings'].notna().sum()
    }

    logger.info(f"Timeline Summary:")
    logger.info(f"  Total events: {summary['total_events']}")
    logger.info(f"  Event types: {summary['event_types']}")
    logger.info(f"  Treatment lines: Chemo={summary['treatment_lines']['chemotherapy']}, RT={summary['treatment_lines']['radiation']}, Surgery={summary['treatment_lines']['surgery']}")
    logger.info(f"  Quality flags: {summary['investigation_flags']} investigation flags, {summary['confidence_warnings']} confidence warnings")

    return output_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate interactive HTML and PDF timelines from patient JSON artifact (V4.7)"
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to patient timeline artifact JSON"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory (default: <input_dir>/visualizations)"
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF export (only generate HTML)"
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else None

    result = create_timeline_from_json(
        input_path,
        output_dir,
        export_pdf=not args.no_pdf
    )

    if result:
        print(f"\n✅ Timeline generation complete:")
        for format_type, path in result.items():
            print(f"   {format_type.upper()}: {path}")
    else:
        print("\n❌ Failed to generate timeline")
        sys.exit(1)
