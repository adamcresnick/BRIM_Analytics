"""
Debug script to investigate date availability for chemotherapy medications
"""

import pandas as pd
from pathlib import Path

# Load the comprehensive chemotherapy data
output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
chemo_df = pd.read_csv(output_path / "comprehensive_chemotherapy_e4BwD8ZYDBccepXcJ.Ilo3w3.csv")

print("="*80)
print("DATE COLUMN AVAILABILITY IN CHEMOTHERAPY DATA")
print("="*80)

# Check what date columns exist
date_columns = [
    'medication_start_date',
    'medication_end_date',
    'med_date_given_start',
    'med_date_given_end',
    'mr_validity_period_start',
    'mr_validity_period_end',
    'cp_period_start',
    'cp_period_end'
]

print(f"\nTotal chemotherapy records: {len(chemo_df)}")
print("\nDate column availability:")
for col in date_columns:
    if col in chemo_df.columns:
        non_null = chemo_df[col].notna().sum()
        print(f"  {col}: {non_null}/{len(chemo_df)} non-null ({non_null/len(chemo_df)*100:.1f}%)")
    else:
        print(f"  {col}: NOT PRESENT IN DATAFRAME")

# Check by specific drugs
print("\n" + "="*60)
print("DATE AVAILABILITY BY DRUG")
print("="*60)

for drug_name in ['bevacizumab', 'vinblastine', 'selumetinib']:
    print(f"\n{drug_name.upper()}:")

    # Find records for this drug
    drug_mask = chemo_df['identified_drugs'].str.contains(drug_name, case=False, na=False)
    drug_records = chemo_df[drug_mask]

    print(f"  Total records: {len(drug_records)}")

    if len(drug_records) > 0:
        # Check date availability for this drug
        for col in date_columns:
            if col in drug_records.columns:
                non_null = drug_records[col].notna().sum()
                if non_null > 0:
                    print(f"  {col}: {non_null} non-null")

        # Check care plan availability
        if 'cp_title' in drug_records.columns:
            care_plans = drug_records['cp_title'].notna().sum()
            print(f"  Care plans: {care_plans} non-null")
            if care_plans > 0:
                unique_plans = drug_records['cp_title'].dropna().unique()
                for plan in unique_plans[:3]:  # Show first 3
                    print(f"    - {plan}")

print("\n" + "="*60)
print("SAMPLE RECORDS WITH DATES")
print("="*60)

# Show a few records that have dates
for col in date_columns:
    if col in chemo_df.columns:
        records_with_date = chemo_df[chemo_df[col].notna()]
        if len(records_with_date) > 0:
            print(f"\nSample record with {col}:")
            sample = records_with_date.iloc[0]
            print(f"  Drug: {sample.get('identified_drugs', 'Unknown')}")
            print(f"  Medication: {sample.get('medication_name', 'Unknown')}")
            print(f"  Date value: {sample[col]}")
            print(f"  Care plan: {sample.get('cp_title', 'None')}")
            break