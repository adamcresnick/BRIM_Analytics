#!/usr/bin/env python3
"""
Validate investigational drug multi-drug strings by:
1. Checking if individual drugs exist as separate medication_request records
2. Checking if parsed drug names match drugs.csv reference
3. Assessing validation criteria for investigational drug extraction
"""

import pandas as pd
import re
from pathlib import Path

# Load data
print("Loading data...")
chemo_df = pd.read_csv('data/chemotherapy_with_normalized.csv')
drugs_ref = pd.read_csv('../athena_views/data_dictionary/chemo_reference/drugs.csv')

# Get all multi-drug strings from investigational extraction
inv_extracted = chemo_df[chemo_df['rxnorm_match_type'] == 'investigational_extracted']
multi_drug = inv_extracted[
    inv_extracted['chemo_therapeutic_normalized'].str.contains(',', na=False) |
    inv_extracted['chemo_therapeutic_normalized'].str.contains(' and ', na=False)
]

# Get unique multi-drug strings
unique_combos = multi_drug['chemo_therapeutic_normalized'].unique()

print(f"\nFound {len(unique_combos)} unique multi-drug strings")
print("="*80)

# Drug name parsing patterns
def parse_drug_names(combo_string):
    """Parse multi-drug string into individual drug names"""
    if pd.isna(combo_string):
        return []

    # Clean up the string
    s = str(combo_string).lower().strip()

    # Remove prefixes like "combination, " or "braf inhibitor "
    s = re.sub(r'^(combination,?\s+|braf inhibitor\s+|mek inhibitor\s+)', '', s)

    # Split on common delimiters
    # Handle: "drug1, drug2, drug3 and drug4"
    s = s.replace(' and ', ', ')
    s = s.replace(' plus ', ', ')
    s = s.replace(' + ', ', ')

    # Split and clean
    drugs = [d.strip() for d in s.split(',') if d.strip()]

    # Remove common non-drug words
    non_drugs = ['once daily', 'softs', 'twice daily', 'combination', '']
    drugs = [d for d in drugs if d not in non_drugs]

    return drugs

# Create reference lookup (normalized names)
drugs_lookup = set()
for _, row in drugs_ref.iterrows():
    drugs_lookup.add(row['preferred_name'].lower().strip())
    if pd.notna(row.get('therapeutic_normalized')):
        drugs_lookup.add(row['therapeutic_normalized'].lower().strip())

# Also add from aliases if available
aliases_file = Path('../athena_views/data_dictionary/chemo_reference/drug_aliases.csv')
if aliases_file.exists():
    aliases_df = pd.read_csv(aliases_file)
    for alias in aliases_df['alias'].str.lower().str.strip():
        drugs_lookup.add(alias)

print(f"Reference drugs.csv contains {len(drugs_lookup)} unique drug names/aliases\n")

# Analyze each multi-drug combo
results = []

for combo in unique_combos[:12]:  # Top 12
    # Get patients with this combo
    combo_patients = multi_drug[multi_drug['chemo_therapeutic_normalized'] == combo]['patient_fhir_id'].unique()

    # Parse individual drugs
    parsed_drugs = parse_drug_names(combo)

    # Check if parsed drugs exist in drugs.csv
    drugs_in_ref = [d for d in parsed_drugs if d in drugs_lookup]
    drugs_not_in_ref = [d for d in parsed_drugs if d not in drugs_lookup]

    # For each patient, check if they have individual medication records for each drug
    patients_with_evidence = []
    patients_without_evidence = []

    for patient_id in combo_patients[:5]:  # Sample first 5 patients
        patient_meds = chemo_df[chemo_df['patient_fhir_id'] == patient_id]

        # Get all unique drugs this patient received (excluding the combo-string itself)
        patient_drug_names = set()
        for _, med in patient_meds.iterrows():
            med_name = str(med['chemo_therapeutic_normalized']).lower().strip()
            if med_name != combo.lower().strip():
                patient_drug_names.add(med_name)

        # Check how many parsed drugs have individual evidence
        drugs_with_evidence = [d for d in parsed_drugs if d in patient_drug_names]

        if len(drugs_with_evidence) > 0:
            patients_with_evidence.append({
                'patient_id': patient_id[:30],
                'drugs_found': drugs_with_evidence,
                'drugs_missing': [d for d in parsed_drugs if d not in patient_drug_names]
            })
        else:
            patients_without_evidence.append(patient_id[:30])

    results.append({
        'combo_string': combo,
        'record_count': len(multi_drug[multi_drug['chemo_therapeutic_normalized'] == combo]),
        'patient_count': len(combo_patients),
        'parsed_drugs': parsed_drugs,
        'in_drugs_csv': drugs_in_ref,
        'not_in_drugs_csv': drugs_not_in_ref,
        'patients_sampled': len(combo_patients[:5]),
        'patients_with_some_evidence': len(patients_with_evidence),
        'patients_without_any_evidence': len(patients_without_evidence),
        'evidence_details': patients_with_evidence[:3]  # Show first 3
    })

# Print results
print("\n" + "="*80)
print("VALIDATION RESULTS")
print("="*80)

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['combo_string']}")
    print(f"   Records: {r['record_count']}, Patients: {r['patient_count']}")
    print(f"\n   Parsed into {len(r['parsed_drugs'])} drugs:")
    for drug in r['parsed_drugs']:
        in_ref = "✓ IN drugs.csv" if drug in r['in_drugs_csv'] else "✗ NOT in drugs.csv"
        print(f"     - {drug:40s} {in_ref}")

    print(f"\n   Validation (sampled {r['patients_sampled']} patients):")
    print(f"     - {r['patients_with_some_evidence']} patients have evidence for SOME individual drugs")
    print(f"     - {r['patients_without_any_evidence']} patients have NO evidence for ANY individual drugs")

    if r['evidence_details']:
        print(f"\n   Evidence examples:")
        for detail in r['evidence_details']:
            print(f"     Patient {detail['patient_id']}:")
            if detail['drugs_found']:
                print(f"       ✓ Found: {', '.join(detail['drugs_found'])}")
            if detail['drugs_missing']:
                print(f"       ✗ Missing: {', '.join(detail['drugs_missing'])}")

    print()

# Summary statistics
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

total_parsed = sum(len(r['parsed_drugs']) for r in results)
total_in_ref = sum(len(r['in_drugs_csv']) for r in results)
total_not_in_ref = sum(len(r['not_in_drugs_csv']) for r in results)

print(f"\nTotal parsed drugs: {total_parsed}")
print(f"  In drugs.csv: {total_in_ref} ({total_in_ref/total_parsed*100:.1f}%)")
print(f"  NOT in drugs.csv: {total_not_in_ref} ({total_not_in_ref/total_parsed*100:.1f}%)")

patients_sampled = sum(r['patients_sampled'] for r in results)
patients_with_evidence = sum(r['patients_with_some_evidence'] for r in results)
patients_without = sum(r['patients_without_any_evidence'] for r in results)

print(f"\nPatients sampled: {patients_sampled}")
print(f"  With some individual drug evidence: {patients_with_evidence} ({patients_with_evidence/patients_sampled*100:.1f}%)")
print(f"  Without any individual drug evidence: {patients_without} ({patients_without/patients_sampled*100:.1f}%)")

print("\n" + "="*80)
print("ASSESSMENT")
print("="*80)
print("""
The investigational drug extraction has THREE potential issues:

1. PARSING: Multi-drug regimen strings are not parsed into individual drugs
   → Fix: Add drug name parsing logic

2. VALIDATION: No check if individual drugs exist as separate medication_request records
   → Fix: Validate against patient's other medications

3. REFERENCE COVERAGE: Some parsed drugs may not be in drugs.csv
   → Fix: Add missing investigational drugs to reference OR flag as unverifiable

RECOMMENDATION:
Create a standardized validation process that:
- Parses multi-drug strings using delimiters (comma, "and", "plus", "+")
- Validates each parsed drug exists as an individual medication_request
- Checks each parsed drug against drugs.csv
- Flags unverifiable investigational drugs for manual review
""")

print("\nValidation complete. Review results above.")
