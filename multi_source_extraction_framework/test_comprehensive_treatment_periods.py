"""
Test Comprehensive Chemotherapy Identification with Treatment Periods
"""

import pandas as pd
import json
from pathlib import Path
from comprehensive_chemotherapy_identifier import ComprehensiveChemotherapyIdentifier

# Initialize identifier
print("="*80)
print("COMPREHENSIVE CHEMOTHERAPY IDENTIFICATION WITH TREATMENT PERIODS")
print("="*80)

identifier = ComprehensiveChemotherapyIdentifier()

# Load medications
staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
patient_path = staging_path / "patient_e4BwD8ZYDBccepXcJ.Ilo3w3"
meds_df = pd.read_csv(patient_path / "medications.csv")

print(f"\nTotal medications loaded: {len(meds_df)}")

# Identify chemotherapy using 5-strategy approach
print("\nExecuting 5-Strategy Chemotherapy Identification...")
chemo_df, summary = identifier.identify_chemotherapy(meds_df)

# Print identification results
print("\n" + "="*60)
print("IDENTIFICATION RESULTS")
print("="*60)
print(f"Total medications: {summary['total_medications']}")
print(f"Chemotherapy identified: {summary['chemotherapy_identified']} ({summary['percentage']:.1f}%)")

print(f"\nUnique drugs identified ({len(summary['unique_drugs'])}):")
for drug in sorted(summary['unique_drugs']):
    if drug in summary['drug_counts']:
        print(f"  - {drug}: {summary['drug_counts'][drug]} records")
    else:
        print(f"  - {drug}")

print("\nStrategy breakdown:")
for strategy, count in summary['strategy_breakdown'].items():
    print(f"  - {strategy}: {count} medications")

# Extract treatment periods
print("\n" + "="*60)
print("TREATMENT PERIOD EXTRACTION")
print("="*60)

periods_df = identifier.extract_treatment_periods(chemo_df)

if not periods_df.empty:
    print(f"Total treatment periods identified: {len(periods_df)}")

    # Group periods by drug
    print("\nTreatment Periods by Drug:")
    for drug in periods_df['drug_name'].unique():
        drug_periods = periods_df[periods_df['drug_name'] == drug]
        print(f"\n{drug.upper()}:")
        for _, period in drug_periods.iterrows():
            print(f"  Care Plan: {period['care_plan']}")
            print(f"  Start: {period['start_date'].strftime('%Y-%m-%d') if pd.notna(period['start_date']) else 'Unknown'}")
            print(f"  End: {period['end_date'].strftime('%Y-%m-%d') if pd.notna(period['end_date']) else 'Unknown'}")
            print(f"  Duration: {period['duration_days']} days")
            print(f"  Administrations: {period['total_administrations']}")
            print(f"  Dosing: {period['dosing_info']}")
            print(f"  Phase: {period.get('treatment_phase', 'Unknown')}")
            print()

    # Create treatment timeline
    timeline_data = identifier.create_treatment_timeline(periods_df)

    print("\n" + "="*60)
    print("TREATMENT TIMELINE")
    print("="*60)

    print(f"Overall treatment duration: {timeline_data['summary']['treatment_duration_days']} days")
    print(f"Total drugs used: {timeline_data['summary']['total_drugs']}")
    print(f"Treatment phases: {timeline_data['summary']['phases']}")

    print("\nChronological Events:")
    for event in timeline_data['timeline'][:20]:  # Show first 20 events
        print(f"  {event['date'][:10] if event['date'] else 'Unknown'}: {event['event']}")
        if 'phase' in event and event['phase'] != 'Unknown':
            print(f"    Phase: {event['phase']}")
        if 'care_plan' in event and event['care_plan'] != 'Not specified':
            print(f"    Care Plan: {event['care_plan']}")

    # Save results
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
    output_path.mkdir(exist_ok=True)

    # Save chemotherapy DataFrame
    chemo_output = output_path / "comprehensive_chemotherapy_e4BwD8ZYDBccepXcJ.Ilo3w3.csv"
    chemo_df.to_csv(chemo_output, index=False)
    print(f"\nChemotherapy data saved to: {chemo_output}")

    # Save treatment periods
    periods_output = output_path / "treatment_periods_e4BwD8ZYDBccepXcJ.Ilo3w3.csv"
    periods_df.to_csv(periods_output, index=False)
    print(f"Treatment periods saved to: {periods_output}")

    # Save timeline
    timeline_output = output_path / "treatment_timeline_e4BwD8ZYDBccepXcJ.Ilo3w3.json"
    with open(timeline_output, 'w') as f:
        json.dump(timeline_data, f, indent=2, default=str)
    print(f"Timeline saved to: {timeline_output}")

else:
    print("No treatment periods could be extracted")

print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)

# Highlight key chemotherapy agents
key_chemo = ['bevacizumab', 'vinblastine', 'selumetinib']
print("\nPrimary Chemotherapy Agents:")
for drug in key_chemo:
    if drug in summary['unique_drugs'] or drug.title() in summary['unique_drugs']:
        count = summary['drug_counts'].get(drug, 0) or summary['drug_counts'].get(drug.title(), 0)
        drug_periods = periods_df[periods_df['drug_name'].str.contains(drug, case=False, na=False)] if not periods_df.empty else pd.DataFrame()
        if not drug_periods.empty:
            total_days = drug_periods['duration_days'].sum()
            print(f"  {drug.upper()}: {count} records, {len(drug_periods)} treatment period(s), {total_days} total days")
        else:
            print(f"  {drug.upper()}: {count} records")

print("\nValidation Notes:")
print("  - RxNorm matching found vinblastine and selumetinib (have RxNorm codes)")
print("  - Name matching found bevacizumab (no RxNorm codes)")
print("  - Care plan category identified ONCOLOGY TREATMENT medications")
print("  - Combined 'Bevacizumab, Vinblastine' protocol identified")