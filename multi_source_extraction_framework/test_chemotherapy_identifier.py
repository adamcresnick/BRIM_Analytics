"""
Test the standardized chemotherapy identifier
"""

import pandas as pd
import sys
from pathlib import Path
from chemotherapy_identifier import ChemotherapyIdentifier

# Load patient medications
staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
patient_path = staging_path / "patient_e4BwD8ZYDBccepXcJ.Ilo3w3"
meds_df = pd.read_csv(patient_path / "medications.csv")

print(f"Total medications loaded: {len(meds_df)}")

# Initialize identifier
identifier = ChemotherapyIdentifier()

# Identify chemotherapy
chemo_df, summary = identifier.identify_chemotherapy(meds_df)

# Print results
print("\n" + "="*60)
print("CHEMOTHERAPY IDENTIFICATION RESULTS")
print("="*60)
print(f"Total medications: {summary['total_medications']}")
print(f"Chemotherapy identified: {summary['chemotherapy_identified']}")
print(f"Percentage: {summary['percentage']:.1f}%")

print(f"\nUnique drugs found ({len(summary['unique_drugs'])}):")
for drug in sorted(summary['unique_drugs']):
    count = summary['drug_counts'].get(drug, 0)
    print(f"  - {drug}: {count} records")

print("\nStrategy breakdown:")
for strategy, count in summary['strategy_counts'].items():
    print(f"  - {strategy}: {count} medications")

print("\nConfidence distribution:")
high_confidence = (chemo_df['confidence_score'] >= 2).sum()
single_match = (chemo_df['confidence_score'] == 1).sum()
print(f"  - High confidence (2+ strategies): {high_confidence}")
print(f"  - Single strategy match: {single_match}")

# Get treatment timeline
timeline = identifier.get_treatment_timeline(chemo_df)
if not timeline.empty:
    print("\nTreatment Timeline:")
    print(timeline[['drug', 'start_date', 'end_date', 'total_orders']].to_string())

# Save results
output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
output_path.mkdir(exist_ok=True)
chemo_df.to_csv(output_path / "standardized_chemotherapy_e4BwD8ZYDBccepXcJ.Ilo3w3.csv", index=False)
print(f"\nResults saved to: {output_path / 'standardized_chemotherapy_e4BwD8ZYDBccepXcJ.Ilo3w3.csv'}")