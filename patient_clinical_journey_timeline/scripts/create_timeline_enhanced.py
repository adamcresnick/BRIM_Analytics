#!/usr/bin/env python3
"""
V4.8: Enhanced Timeline Visualization with Best Practices

Implements timeline best practices:
- Dot markers instead of bars (clearer for discrete events)
- Vertical time axis (better for reading chronology)
- Color-coded by event category
- Clear visual hierarchy
- Hover details
- Treatment line indicators

Based on Tufte's principles and medical timeline best practices
"""

import argparse
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def categorize_event(event_type: str) -> tuple:
    """Categorize event and return (category, symbol, color)."""
    event_lower = event_type.lower()

    if 'surgery' in event_lower or 'procedure' in event_lower:
        return ('Surgery', 'diamond', '#E74C3C')  # Red diamond
    elif 'chemo' in event_lower:
        return ('Chemotherapy', 'circle', '#3498DB')  # Blue circle
    elif 'radiation' in event_lower:
        return ('Radiation', 'square', '#F39C12')  # Orange square
    elif 'imaging' in event_lower:
        return ('Imaging', 'triangle-up', '#9B59B6')  # Purple triangle
    elif 'pathology' in event_lower:
        return ('Pathology', 'hexagon', '#1ABC9C')  # Teal hexagon
    elif 'diagnosis' in event_lower:
        return ('Diagnosis', 'star', '#E67E22')  # Orange star
    else:
        return ('Other', 'circle-open', '#95A5A6')  # Gray circle


def create_enhanced_timeline(artifact_path: Path, output_dir: Optional[Path] = None) -> Path:
    """
    Create enhanced dot-based timeline visualization.

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

    # Prepare data for visualization
    data_points = []

    for event in timeline_events:
        event_type = event.get('event_type', 'unknown')
        event_date_str = event.get('event_date')

        if not event_date_str:
            continue

        try:
            event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
        except:
            continue

        category, symbol, color = categorize_event(event_type)

        # Build description
        description = event.get('description', event_type.replace('_', ' ').title())

        # Add treatment line info if available
        ordinality = event.get('relationships', {}).get('ordinality', {})
        treatment_line = ordinality.get('treatment_line') or ordinality.get('radiation_course')
        if treatment_line:
            line_label = f"Line {treatment_line}" if 'chemo' in event_type else f"Course {treatment_line}"
        else:
            line_label = None

        # Add extent of resection for surgeries
        eor = None
        if 'surgery' in event_type.lower():
            eor = event.get('extent_of_resection')

        # Add therapy dates for treatments
        end_date = None
        status = event.get('therapy_status')
        if 'chemo' in event_type.lower():
            end_date = event.get('therapy_end_date')
        elif 'radiation' in event_type.lower():
            end_date = event.get('date_at_radiation_stop')

        data_points.append({
            'date': event_date,
            'category': category,
            'symbol': symbol,
            'color': color,
            'description': description,
            'event_type': event_type,
            'treatment_line': line_label,
            'eor': eor,
            'end_date': end_date,
            'status': status
        })

    if not data_points:
        logger.warning("No events to visualize")
        return None

    df = pd.DataFrame(data_points)
    df = df.sort_values('date')

    # Create figure
    fig = go.Figure()

    # Add traces by category (for legend grouping)
    categories = df['category'].unique()

    for category in sorted(categories):
        cat_df = df[df['category'] == category]

        # Build hover text
        hover_texts = []
        for _, row in cat_df.iterrows():
            hover_parts = [
                f"<b>{row['description']}</b>",
                f"Date: {row['date'].strftime('%b %d, %Y')}",
                f"Type: {row['event_type'].replace('_', ' ').title()}"
            ]

            if row['treatment_line']:
                hover_parts.append(f"Treatment: {row['treatment_line']}")

            if row['eor']:
                hover_parts.append(f"Extent of Resection: {row['eor']}")

            if row['status'] == 'ongoing':
                hover_parts.append("<b>Status: ONGOING</b>")
            elif row['end_date']:
                try:
                    end_dt = datetime.fromisoformat(row['end_date'].replace('Z', '+00:00'))
                    hover_parts.append(f"End Date: {end_dt.strftime('%b %d, %Y')}")
                except:
                    pass

            hover_texts.append("<br>".join(hover_parts))

        fig.add_trace(go.Scatter(
            x=[1] * len(cat_df),  # All events on same vertical line
            y=cat_df['date'],
            mode='markers+text',
            name=category,
            marker=dict(
                symbol=cat_df['symbol'].iloc[0],
                size=12,
                color=cat_df['color'].iloc[0],
                line=dict(width=2, color='white')
            ),
            text=[f"  {d[:30]}..." if len(d) > 30 else f"  {d}" for d in cat_df['description']],
            textposition="middle right",
            textfont=dict(size=9),
            hovertext=hover_texts,
            hoverinfo='text'
        ))

    # Update layout for vertical timeline
    fig.update_layout(
        title=dict(
            text=f"<b>Clinical Journey Timeline</b><br><sub>Patient: {patient_id} | {who_dx} | Age: {age} | Gender: {gender}</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            range=[0.5, 1.5]
        ),
        yaxis=dict(
            title="Date",
            showgrid=True,
            gridcolor='lightgray',
            type='date'
        ),
        height=max(800, len(data_points) * 40),
        hovermode='closest',
        showlegend=True,
        legend=dict(
            title="Event Type",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        plot_bgcolor='white',
        margin=dict(l=100, r=200, t=100, b=50)
    )

    # Add vertical timeline line
    fig.add_shape(
        type="line",
        x0=1, x1=1,
        y0=df['date'].min(),
        y1=df['date'].max(),
        line=dict(color="gray", width=2)
    )

    # Determine output path
    if output_dir is None:
        output_dir = artifact_path.parent / "visualizations"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "timeline_enhanced.html"

    # Save
    logger.info(f"Saving enhanced timeline to {output_path}")
    fig.write_html(str(output_path))

    # Also save PNG
    try:
        png_path = output_dir / "timeline_enhanced.png"
        fig.write_image(str(png_path), width=1200, height=max(800, len(data_points) * 40))
        logger.info(f"Saved PNG to {png_path}")
    except Exception as e:
        logger.warning(f"Could not save PNG (kaleido may not be installed): {e}")

    logger.info("✅ Enhanced timeline created successfully")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Create enhanced timeline visualization")
    parser.add_argument("artifact_path", type=Path, help="Path to patient_timeline_artifact.json")
    parser.add_argument("--output-dir", "-o", type=Path, help="Output directory")

    args = parser.parse_args()

    if not args.artifact_path.exists():
        logger.error(f"Artifact not found: {args.artifact_path}")
        return 1

    output_path = create_enhanced_timeline(args.artifact_path, args.output_dir)

    if output_path:
        logger.info(f"View timeline: open {output_path}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())
