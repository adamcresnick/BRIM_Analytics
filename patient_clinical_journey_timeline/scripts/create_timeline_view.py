

import argparse
import json
from pathlib import Path
import pandas as pd
import plotly.express as px
from datetime import datetime

def create_timeline_from_json(json_path: Path):
    """
    Reads a patient's JSON artifact, transforms the data, and generates
    an interactive HTML timeline view.

    Args:
        json_path: Path to the input JSON artifact file.
    """
    # Load the JSON data
    with open(json_path, 'r') as f:
        patient_data = json.load(f)

    patient_id = patient_data.get('patient_fhir_id', 'UnknownPatient')
    timeline_events = patient_data.get('timeline_events', [])

    if not timeline_events:
        print(f"No timeline_events found in {json_path}. Exiting.")
        return

    print(f"Processing {len(timeline_events)} events for patient {patient_id}...")

    # --- Data Transformation ---
    df_data = []
    for event in timeline_events:
        event_type = event.get('event_type', 'Unknown')
        start_date_str = event.get('event_date')
        if not start_date_str:
            continue  # Skip events without a start date

        start_date = pd.to_datetime(start_date_str)
        end_date_str = event.get('end_date')

        # Handle point-in-time vs. duration events
        if end_date_str:
            end_date = pd.to_datetime(end_date_str)
        else:
            # For point events, create a small duration to make them visible
            end_date = start_date + pd.Timedelta(days=1)

        # Create a descriptive task label
        task_desc = event.get('event_description')
        if not task_desc:
            task_desc = event.get('proc_code_text', event_type)
        task_label = f"{event_type.replace('_', ' ').title()}: {task_desc}"


        # Group event types for consistent coloring
        resource_type = "Other"
        if 'chemo' in event_type.lower():
            resource_type = "Chemotherapy"
        elif 'radiation' in event_type.lower():
            resource_type = "Radiation"
        elif 'surgery' in event_type.lower() or 'procedure' in event_type.lower():
            resource_type = "Procedure"
        elif 'imaging' in event_type.lower():
            resource_type = "Imaging"
        elif 'pathology' in event_type.lower():
            resource_type = "Pathology"
        elif 'diagnosis' in event_type.lower():
            resource_type = "Diagnosis"


        df_data.append({
            "Task": task_label,
            "Start": start_date,
            "Finish": end_date,
            "ResourceType": resource_type
        })

    if not df_data:
        print("No processable events found after transformation. Exiting.")
        return

    df = pd.DataFrame(df_data)

    # Ensure dates are in datetime format
    df['Start'] = pd.to_datetime(df['Start'])
    df['Finish'] = pd.to_datetime(df['Finish'])


    # --- Visualization ---
    # TODO: Refine the Plotly visualization
    # Create a Gantt chart
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="ResourceType",
        title=f"Clinical Timeline for Patient: {patient_id}",
        hover_data={"Task": True, "Start": "|%Y-%m-%d", "Finish": "|%Y-%m-%d", "ResourceType": True}
    )

    fig.update_yaxes(autorange="reversed") # Show events from top to bottom
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Clinical Events",
        legend_title="Event Category"
    )

    # --- Output ---
    output_filename = f"{patient_id}_timeline.html"
    output_path = json_path.parent / output_filename
    fig.write_html(output_path)

    print(f"\nSuccessfully generated timeline: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate an interactive HTML timeline from a patient's JSON artifact."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the patient's JSON artifact file."
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found at {input_path}")
        exit(1)

    create_timeline_from_json(input_path)
