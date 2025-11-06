#!/usr/bin/env python3
"""
V4.8: cBioPortal-Style Horizontal Swim-Lane Timeline Visualization

Implements professional timeline design based on cBioPortal clinical-timeline:
- Horizontal time axis (left to right chronology)
- Separate swim lanes for each treatment modality
- Treatment spans shown as bars
- Point events shown as markers
- Color-coded by category
- Professional, publication-ready design

Reference: https://github.com/cBioPortal/clinical-timeline
"""

import argparse
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Color scheme (professional, colorblind-friendly)
COLORS = {
    'diagnosis': '#2E86AB',      # Blue
    'surgery': '#A23B72',        # Purple
    'chemotherapy': '#F18F01',   # Orange
    'radiation': '#C73E1D',      # Red
    'imaging': '#6A994E',        # Green
    'pathology': '#06A77D',      # Teal
    'clinical_event': '#777777'  # Gray
}


def categorize_event(event_type: str) -> Tuple[str, str]:
    """
    Categorize event and return (swim_lane, color).

    Returns:
        Tuple of (swim_lane_name, color_hex)
    """
    event_lower = event_type.lower()

    if 'diagnosis' in event_lower or 'sample' in event_lower:
        return ('Diagnosis', COLORS['diagnosis'])
    elif 'surgery' in event_lower or 'procedure' in event_lower:
        return ('Surgery', COLORS['surgery'])
    elif 'chemo' in event_lower:
        return ('Chemotherapy', COLORS['chemotherapy'])
    elif 'radiation' in event_lower:
        return ('Radiation', COLORS['radiation'])
    elif 'imaging' in event_lower:
        return ('Imaging', COLORS['imaging'])
    elif 'pathology' in event_lower or 'lab' in event_lower:
        return ('Pathology', COLORS['pathology'])
    else:
        return ('Clinical Events', COLORS['clinical_event'])


def create_horizontal_timeline(artifact_path: Path, output_dir: Optional[Path] = None) -> Path:
    """
    Create cBioPortal-style horizontal swim-lane timeline.

    Args:
        artifact_path: Path to patient_timeline_artifact.json
        output_dir: Output directory (default: artifact parent/visualizations)

    Returns:
        Path to generated HTML file
    """
    logger.info(f"Loading artifact from {artifact_path}")

    with open(artifact_path) as f:
        artifact = json.load(f)

    patient_id = artifact.get('patient_id', 'Unknown')
    demographics = artifact.get('demographics', {})
    who_diagnosis = artifact.get('who_diagnosis', {})
    timeline_events = artifact.get('timeline_events', [])

    # Extract metadata
    age = demographics.get('age_at_diagnosis', 'Unknown')
    gender = demographics.get('gender', 'Unknown')
    who_dx = who_diagnosis.get('diagnosis', 'Unknown')

    # Parse all events
    events_by_lane = {
        'Diagnosis': [],
        'Surgery': [],
        'Chemotherapy': [],
        'Radiation': [],
        'Imaging': [],
        'Pathology': [],
        'Clinical Events': []
    }

    for event in timeline_events:
        event_type = event.get('event_type', 'unknown')
        event_date_str = event.get('event_date')

        if not event_date_str:
            continue

        try:
            # Handle both timezone-aware and naive datetimes - normalize to naive
            event_date_temp = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
            event_date = event_date_temp.replace(tzinfo=None) if event_date_temp.tzinfo else event_date_temp
        except:
            continue

        lane, color = categorize_event(event_type)

        # Determine if this is a span (treatment) or point (event)
        end_date = None
        is_span = False

        if 'chemo' in event_type.lower():
            end_date_str = event.get('therapy_end_date')
            if end_date_str:
                try:
                    # Handle both timezone-aware and naive datetimes
                    end_date_temp = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    # Make timezone-naive for consistency
                    end_date = end_date_temp.replace(tzinfo=None) if end_date_temp.tzinfo else end_date_temp
                    is_span = True
                except:
                    pass
        elif 'radiation' in event_type.lower():
            end_date_str = event.get('date_at_radiation_stop')
            if end_date_str:
                try:
                    # Handle both timezone-aware and naive datetimes
                    end_date_temp = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    # Make timezone-naive for consistency
                    end_date = end_date_temp.replace(tzinfo=None) if end_date_temp.tzinfo else end_date_temp
                    is_span = True
                except:
                    pass

        # Build event label
        label = event.get('description', event_type.replace('_', ' ').title())

        # Add treatment line info
        ordinality = event.get('relationships', {}).get('ordinality', {})
        treatment_line = ordinality.get('treatment_line') or ordinality.get('radiation_course') or ordinality.get('surgery_number')

        # Truncate long labels
        if len(label) > 40:
            label = label[:37] + '...'

        # Build hover text
        hover_parts = [
            f"<b>{event.get('description', event_type)}</b>",
            f"<b>Date:</b> {event_date.strftime('%b %d, %Y')}"
        ]

        if treatment_line:
            if 'chemo' in event_type.lower():
                hover_parts.append(f"<b>Line:</b> {treatment_line}")
            elif 'radiation' in event_type.lower():
                hover_parts.append(f"<b>Course:</b> {treatment_line}")
            elif 'surgery' in event_type.lower():
                hover_parts.append(f"<b>Surgery #:</b> {treatment_line}")

        # Add EOR for surgeries
        if 'surgery' in event_type.lower():
            eor = event.get('extent_of_resection')
            if eor:
                hover_parts.append(f"<b>Extent of Resection:</b> {eor}")

        # Add agents for chemo
        if 'chemo' in event_type.lower():
            agents = event.get('agent_names', [])
            if agents:
                hover_parts.append(f"<b>Agents:</b> {', '.join(agents)}")

        # Add dose for radiation
        if 'radiation' in event_type.lower():
            dose = event.get('total_dose_gy')
            if dose:
                hover_parts.append(f"<b>Dose:</b> {dose} Gy")

        if end_date:
            hover_parts.append(f"<b>End Date:</b> {end_date.strftime('%b %d, %Y')}")
            duration_days = (end_date - event_date).days
            hover_parts.append(f"<b>Duration:</b> {duration_days} days")

        if event.get('therapy_status') == 'ongoing':
            hover_parts.append("<b>Status:</b> ONGOING")

        events_by_lane[lane].append({
            'start_date': event_date,
            'end_date': end_date,
            'is_span': is_span,
            'label': label,
            'color': color,
            'hover_text': '<br>'.join(hover_parts),
            'treatment_line': treatment_line
        })

    # Remove empty lanes
    events_by_lane = {k: v for k, v in events_by_lane.items() if v}

    if not any(events_by_lane.values()):
        logger.warning("No events to visualize")
        return None

    # Create figure with swim lanes
    num_lanes = len(events_by_lane)
    fig = go.Figure()

    # Add traces for each lane
    lane_names = list(events_by_lane.keys())

    for lane_idx, lane_name in enumerate(lane_names):
        lane_events = events_by_lane[lane_name]
        y_position = num_lanes - lane_idx  # Reverse order (top to bottom)

        # Separate spans and points
        spans = [e for e in lane_events if e['is_span']]
        points = [e for e in lane_events if not e['is_span']]

        # Draw treatment spans as horizontal bars
        for span in spans:
            fig.add_trace(go.Scatter(
                x=[span['start_date'], span['end_date']],
                y=[y_position, y_position],
                mode='lines',
                line=dict(
                    color=span['color'],
                    width=20
                ),
                hovertext=span['hover_text'],
                hoverinfo='text',
                showlegend=False,
                name=''
            ))

            # Add label in middle of span
            mid_date = span['start_date'] + (span['end_date'] - span['start_date']) / 2
            fig.add_annotation(
                x=mid_date,
                y=y_position,
                text=span['label'],
                showarrow=False,
                font=dict(size=9, color='white'),
                xanchor='center',
                yanchor='middle'
            )

        # Draw point events as markers
        if points:
            fig.add_trace(go.Scatter(
                x=[p['start_date'] for p in points],
                y=[y_position] * len(points),
                mode='markers',
                marker=dict(
                    color=[p['color'] for p in points],
                    size=12,
                    symbol='circle',
                    line=dict(width=2, color='white')
                ),
                hovertext=[p['hover_text'] for p in points],
                hoverinfo='text',
                showlegend=False,
                name=''
            ))

            # Add labels for point events
            for point in points:
                fig.add_annotation(
                    x=point['start_date'],
                    y=y_position + 0.15,
                    text=point['label'],
                    showarrow=False,
                    font=dict(size=8, color=point['color']),
                    xanchor='center',
                    yanchor='bottom'
                )

    # Get date range
    all_dates = []
    for events in events_by_lane.values():
        for event in events:
            all_dates.append(event['start_date'])
            if event['end_date']:
                all_dates.append(event['end_date'])

    min_date = min(all_dates)
    max_date = max(all_dates)
    date_range = (max_date - min_date).days
    padding = max(30, date_range * 0.05)  # 5% padding or 30 days minimum

    # Update layout
    fig.update_layout(
        title=dict(
            text=f"<b>Clinical Journey Timeline</b><br>" +
                 f"<sub>{who_dx} | Age: {age} | Gender: {gender}</sub>",
            x=0.5,
            xanchor='center',
            font=dict(size=18)
        ),
        xaxis=dict(
            title='<b>Time</b>',
            showgrid=True,
            gridcolor='#E5E5E5',
            type='date',
            range=[
                min_date - pd.Timedelta(days=padding),
                max_date + pd.Timedelta(days=padding)
            ]
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickmode='array',
            tickvals=list(range(1, num_lanes + 1)),
            ticktext=lane_names[::-1],  # Reverse order
            range=[0.5, num_lanes + 0.5]
        ),
        height=max(400, num_lanes * 120),
        width=1400,
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=150, r=50, t=120, b=80),
        font=dict(family='Arial, sans-serif', size=12)
    )

    # Add horizontal gridlines between lanes
    for i in range(1, num_lanes):
        fig.add_hline(
            y=i + 0.5,
            line_dash="dot",
            line_color="#CCCCCC",
            line_width=1
        )

    # Determine output path
    if output_dir is None:
        output_dir = artifact_path.parent / "visualizations"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "timeline_enhanced.html"

    # Save
    logger.info(f"Saving horizontal swim-lane timeline to {output_path}")
    fig.write_html(
        str(output_path),
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )

    # Also save PNG
    try:
        png_path = output_dir / "timeline_enhanced.png"
        fig.write_image(str(png_path), width=1400, height=max(400, num_lanes * 120))
        logger.info(f"Saved PNG to {png_path}")
    except Exception as e:
        logger.warning(f"Could not save PNG (kaleido may not be installed): {e}")

    logger.info("✅ Horizontal swim-lane timeline created successfully")
    logger.info(f"View timeline: open {output_path}")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Create cBioPortal-style horizontal timeline")
    parser.add_argument("artifact_path", type=Path, help="Path to patient_timeline_artifact.json")
    parser.add_argument("--output-dir", "-o", type=Path, help="Output directory")

    args = parser.parse_args()

    if not args.artifact_path.exists():
        logger.error(f"Artifact not found: {args.artifact_path}")
        return 1

    output_path = create_horizontal_timeline(args.artifact_path, args.output_dir)

    if output_path:
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())
