#!/usr/bin/env python3
"""
Agent 1 (Claude) reviews existing Agent 2 (MedGemma) extractions
and generates patient-specific QA report

This script demonstrates the Agent 1 ↔ Agent 2 iterative resolution workflow:
1. Load existing extraction results (51 imaging events)
2. Detect inconsistencies using Agent 1 temporal/logical checks
3. For each inconsistency, resolve via Agent 2 interaction
4. Generate comprehensive patient QA report
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import duckdb

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_extraction_results(results_path: str) -> dict:
    """Load existing extraction results"""
    with open(results_path) as f:
        return json.load(f)


def detect_temporal_inconsistencies(results: dict, timeline_db: duckdb.DuckDBPyConnection):
    """
    Agent 1: Detect temporal inconsistencies in Agent 2 extractions
    """
    print("\n" + "="*80)
    print("AGENT 1: DETECTING INCONSISTENCIES IN AGENT 2 EXTRACTIONS")
    print("="*80 + "\n")

    # Get tumor status extractions
    tumor_status_extractions = [
        r for r in results['results']
        if r['extraction_type'] == 'tumor_status' and r['success']
    ]

    print(f"Analyzing {len(tumor_status_extractions)} tumor status extractions\n")

    # Get timeline data
    timeline_query = """
    SELECT
        event_id,
        event_date,
        age_at_event_years,
        event_type,
        event_subtype
    FROM events
    WHERE patient_id = ?
    ORDER BY event_date
    """

    events = timeline_db.execute(
        timeline_query,
        [results['patient_id']]
    ).fetchall()

    # Create event lookup
    event_lookup = {e[0]: e for e in events}

    # Combine extractions with timeline data
    combined = []
    for ext in tumor_status_extractions:
        event_id = ext['event_id']
        if event_id in event_lookup:
            event_data = event_lookup[event_id]
            combined.append({
                'event_id': event_id,
                'event_date': event_data[1],
                'age_years': float(event_data[2]) if event_data[2] else 0,
                'tumor_status': ext['value'],
                'confidence': ext['confidence']
            })

    # Sort by date
    combined.sort(key=lambda x: x['event_date'])

    # Detect inconsistencies
    inconsistencies = []

    print("Inconsistency Detection Results:\n")

    # Check 1: Duplicates (same date)
    print("1. Checking for duplicate events (same date)...")
    date_groups = {}
    for event in combined:
        date_str = str(event['event_date'])
        if date_str not in date_groups:
            date_groups[date_str] = []
        date_groups[date_str].append(event)

    duplicate_count = 0
    for date, events_on_date in date_groups.items():
        if len(events_on_date) > 1:
            duplicate_count += 1
            inconsistencies.append({
                'type': 'duplicate',
                'severity': 'high',
                'description': f"Duplicate events on {date}: {len(events_on_date)} events",
                'events': [e['event_id'] for e in events_on_date],
                'details': events_on_date
            })

    print(f"   Found {duplicate_count} duplicate date groups\n")

    # Check 2: Rapid status changes (Increased → Decreased in < 7 days)
    print("2. Checking for rapid tumor status changes...")
    rapid_change_count = 0
    for i in range(len(combined) - 1):
        current = combined[i]
        next_event = combined[i + 1]

        if current['tumor_status'] == 'Increased' and next_event['tumor_status'] == 'Decreased':
            days_diff = (next_event['event_date'] - current['event_date']).days

            if days_diff < 7:
                rapid_change_count += 1
                inconsistencies.append({
                    'type': 'temporal',
                    'severity': 'high',
                    'description': f"Status changed Increased→Decreased in {days_diff} days",
                    'events': [current['event_id'], next_event['event_id']],
                    'details': {
                        'prior': current,
                        'current': next_event,
                        'days_diff': days_diff
                    }
                })

    print(f"   Found {rapid_change_count} rapid status changes\n")

    # Check 3: Wrong extraction type
    print("3. Checking for wrong extraction types...")
    wrong_type_count = 0
    EOR_VALUES = ['Gross Total Resection', 'Near Total Resection', 'Subtotal Resection']

    for event in combined:
        if event['tumor_status'] in EOR_VALUES:
            wrong_type_count += 1
            inconsistencies.append({
                'type': 'wrong_type',
                'severity': 'high',
                'description': f"'{event['tumor_status']}' is EOR, not tumor_status",
                'events': [event['event_id']],
                'details': event
            })

    print(f"   Found {wrong_type_count} wrong extraction types\n")

    # Check 4: Low confidence
    print("4. Checking for low confidence extractions...")
    low_conf_count = sum(1 for e in combined if e['confidence'] < 0.75)
    print(f"   Found {low_conf_count} low confidence extractions (< 0.75)\n")

    # Summary
    print("="*80)
    print(f"INCONSISTENCY SUMMARY: {len(inconsistencies)} total issues detected")
    print("="*80)
    print(f"  Duplicates: {duplicate_count}")
    print(f"  Rapid changes: {rapid_change_count}")
    print(f"  Wrong types: {wrong_type_count}")
    print(f"  Low confidence: {low_conf_count}")
    print()

    return inconsistencies, combined


def demonstrate_agent2_query(inconsistency: dict, medgemma=None):
    """
    Agent 1: Query Agent 2 for explanation of inconsistency
    """
    print("\n" + "="*80)
    print(f"AGENT 1 → AGENT 2: QUERYING ABOUT {inconsistency['type'].upper()} INCONSISTENCY")
    print("="*80 + "\n")

    if inconsistency['type'] == 'temporal':
        # Build query for Agent 2
        prior = inconsistency['details']['prior']
        current = inconsistency['details']['current']
        days_diff = inconsistency['details']['days_diff']

        print(f"Prior event ({prior['event_date']}):")
        print(f"  Status: {prior['tumor_status']}")
        print(f"  Confidence: {prior['confidence']:.2f}\n")

        print(f"Current event ({current['event_date']}):")
        print(f"  Status: {current['tumor_status']}")
        print(f"  Confidence: {current['confidence']:.2f}\n")

        print(f"Time difference: {days_diff} days")
        print(f"Issue: Status flipped from Increased to Decreased in {days_diff} days\n")

        print("Agent 1 prepares query for Agent 2...")
        print("\nQUERY TO AGENT 2:")
        print("-" * 80)

        query = f"""You previously classified these two imaging reports:

**Event 1** ({prior['event_date']}):
- Classification: tumor_status = Increased
- Confidence: {prior['confidence']:.2f}

**Event 2** ({current['event_date']}, {days_diff} days later):
- Classification: tumor_status = Decreased
- Confidence: {current['confidence']:.2f}

**INCONSISTENCY**: Tumor status changed from "Increased" to "Decreased" in only {days_diff} days without documented treatment intervention.

**Questions**:
1. Is it clinically plausible for tumor status to improve this rapidly?
2. Could these be duplicate scans (same imaging study extracted twice)?
3. Could one classification be incorrect?
4. What would you recommend: keep both / mark as duplicate / re-review one or both?

Provide your assessment."""

        print(query)
        print("-" * 80)

        # NOTE: In production, we would actually call Agent 2 here:
        # response = medgemma.extract(prompt=query, ...)

        print("\n[In production, Agent 2 would respond here]")
        print("\nExpected Agent 2 response would include:")
        print("  1. Assessment of clinical plausibility")
        print("  2. Evidence from source reports")
        print("  3. Recommended resolution")

    elif inconsistency['type'] == 'duplicate':
        print(f"Detected duplicate events on {inconsistency['events'][0]}")
        print(f"Number of events: {len(inconsistency['events'])}")
        print("\nAgent 1 resolution: Skip duplicates (no Agent 2 query needed)")

    elif inconsistency['type'] == 'wrong_type':
        print(f"Detected wrong extraction type:")
        print(f"  Event: {inconsistency['events'][0]}")
        print(f"  Value: {inconsistency['details']['tumor_status']}")
        print("\nAgent 1 resolution: Re-extract as 'extent_of_resection'")


def generate_qa_report(
    patient_id: str,
    inconsistencies: list,
    combined_events: list,
    output_dir: str = "data/qa_reports"
):
    """
    Agent 1: Generate patient-specific QA report
    """
    print("\n" + "="*80)
    print("AGENT 1: GENERATING PATIENT QA REPORT")
    print("="*80 + "\n")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = Path(output_dir) / f"{patient_id}_{timestamp}_qa_report.md"

    with open(report_path, 'w') as f:
        f.write(f"# Patient QA Report: {patient_id}\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Agent 1 (Claude)**: Orchestration and QA\n")
        f.write(f"**Agent 2 (MedGemma)**: Extraction\n\n")

        f.write(f"---\n\n")

        # Summary
        f.write(f"## Executive Summary\n\n")
        f.write(f"- **Total imaging events analyzed**: {len(combined_events)}\n")
        f.write(f"- **Inconsistencies detected**: {len(inconsistencies)}\n")
        f.write(f"- **Requires human review**: {'Yes ⚠️' if len(inconsistencies) > 0 else 'No ✅'}\n\n")

        # Inconsistency breakdown
        inconsistency_types = {}
        for inc in inconsistencies:
            inc_type = inc['type']
            if inc_type not in inconsistency_types:
                inconsistency_types[inc_type] = 0
            inconsistency_types[inc_type] += 1

        f.write(f"### Inconsistency Breakdown\n\n")
        for inc_type, count in inconsistency_types.items():
            f.write(f"- **{inc_type}**: {count}\n")
        f.write(f"\n")

        # Detailed inconsistencies
        f.write(f"---\n\n")
        f.write(f"## Detected Inconsistencies\n\n")

        for i, inc in enumerate(inconsistencies, 1):
            f.write(f"### {i}. {inc['type'].upper()} - {inc['severity']}\n\n")
            f.write(f"**Description**: {inc['description']}\n\n")
            f.write(f"**Affected Events**: {', '.join(inc['events'])}\n\n")

            if inc['type'] == 'temporal':
                details = inc['details']
                f.write(f"**Timeline**:\n")
                f.write(f"- **Prior**: {details['prior']['event_date']} - {details['prior']['tumor_status']} (conf: {details['prior']['confidence']:.2f})\n")
                f.write(f"- **Current**: {details['current']['event_date']} - {details['current']['tumor_status']} (conf: {details['current']['confidence']:.2f})\n")
                f.write(f"- **Time gap**: {details['days_diff']} days\n\n")

                f.write(f"**Agent 1 Assessment**: Rapid status change without documented treatment intervention suggests:\n")
                f.write(f"1. Possible duplicate scan\n")
                f.write(f"2. Possible misclassification by Agent 2\n")
                f.write(f"3. Requires Agent 2 re-review with additional context\n\n")

                f.write(f"**Recommended Action**: Query Agent 2 for explanation and multi-source validation\n\n")

            elif inc['type'] == 'duplicate':
                f.write(f"**Events on same date**:\n")
                for event in inc['details']:
                    f.write(f"- {event['event_id']}: {event['tumor_status']} (conf: {event['confidence']:.2f})\n")
                f.write(f"\n")

                f.write(f"**Agent 1 Resolution**: Skip duplicate events, keep only first occurrence\n\n")

            elif inc['type'] == 'wrong_type':
                f.write(f"**Misclassified Value**: `{inc['details']['tumor_status']}`\n\n")
                f.write(f"**Agent 1 Assessment**: This value belongs to `extent_of_resection`, not `tumor_status`\n\n")
                f.write(f"**Agent 1 Resolution**: Re-extract using correct variable type\n\n")

            f.write(f"---\n\n")

        # Recommendations
        f.write(f"## Recommendations for Human Review\n\n")

        high_priority = [i for i in inconsistencies if i['severity'] == 'high']

        if high_priority:
            f.write(f"⚠️ **{len(high_priority)} high-priority issues require review**\n\n")

            for inc in high_priority:
                f.write(f"1. **{inc['type']}**: {inc['description']}\n")
                f.write(f"   - Events: {', '.join(inc['events'])}\n\n")
        else:
            f.write(f"✅ No high-priority issues detected\n\n")

        # Next steps
        f.write(f"## Next Steps\n\n")
        f.write(f"1. **Agent 1**: Query Agent 2 for explanations of temporal inconsistencies\n")
        f.write(f"2. **Agent 1**: Gather additional sources (imaging PDFs, progress notes) for multi-source validation\n")
        f.write(f"3. **Agent 1**: Re-extract with correct variable types where needed\n")
        f.write(f"4. **Human**: Review escalated issues and provide final adjudication\n")

    print(f"✅ Generated QA report: {report_path}\n")

    return report_path


def main():
    """Main execution"""
    # Paths
    extraction_results = "data/extraction_results/imaging_extraction_20251019_225055.json"
    timeline_db_path = "data/timeline.duckdb"

    print("="*80)
    print("AGENT 1 ↔ AGENT 2 ITERATIVE RESOLUTION WORKFLOW")
    print("Demonstration: Review existing extractions and generate QA report")
    print("="*80)

    # Load data
    print(f"\nLoading extraction results: {extraction_results}")
    results = load_extraction_results(extraction_results)
    print(f"  Patient: {results['patient_id']}")
    print(f"  Imaging events: {results['imaging_events_processed']}")
    print(f"  Successful extractions: {results['successful_extractions']}")

    # Connect to timeline database
    print(f"\nConnecting to timeline database: {timeline_db_path}")
    timeline_db = duckdb.connect(timeline_db_path, read_only=True)

    # Detect inconsistencies (Agent 1)
    inconsistencies, combined_events = detect_temporal_inconsistencies(results, timeline_db)

    # Demonstrate Agent 2 query for one inconsistency
    if inconsistencies:
        print("\nDemonstrating Agent 1 → Agent 2 interaction for first inconsistency...")
        medgemma = None  # Would initialize in production
        demonstrate_agent2_query(inconsistencies[0], medgemma)

    # Generate QA report (Agent 1)
    report_path = generate_qa_report(
        patient_id=results['patient_id'],
        inconsistencies=inconsistencies,
        combined_events=combined_events
    )

    print("\n" + "="*80)
    print("WORKFLOW COMPLETE")
    print("="*80)
    print(f"\n✅ Patient QA report generated: {report_path}")
    print(f"\nNext: Implement Agent 2 queries and multi-source validation")

    timeline_db.close()


if __name__ == "__main__":
    main()
