#!/usr/bin/env python3
"""
Validate treatment paradigms for:
1. Drugs with same RxNorm code (same parent drug, different names)
2. Supportive care drugs incorrectly included
"""

import json
import pandas as pd
from collections import defaultdict
from pathlib import Path

def load_data():
    """Load paradigms and drugs reference."""
    paradigms_file = Path(__file__).parent / 'data/treatment_paradigms/treatment_paradigms.json'
    drugs_file = Path(__file__).parent.parent / 'athena_views/data_dictionary/chemo_reference/drugs.csv'

    with open(paradigms_file) as f:
        paradigms = json.load(f)

    drugs_df = pd.read_csv(drugs_file)

    return paradigms, drugs_df

def check_paradigm_issues(paradigms, drugs_df):
    """Check each paradigm for issues."""

    issues = []

    # Create lookup dictionaries
    # Map lowercase drug name -> drug info
    drug_lookup = {}
    for _, row in drugs_df.iterrows():
        name = str(row['preferred_name']).lower().strip()
        drug_lookup[name] = {
            'rxnorm_in': row.get('rxnorm_in'),
            'therapeutic_normalized': row.get('therapeutic_normalized'),
            'is_supportive_care': row.get('is_supportive_care'),
            'drug_category': row.get('drug_category'),
            'preferred_name': row['preferred_name']
        }

    for paradigm_id, paradigm_data in paradigms.items():
        drugs = paradigm_data['drugs']
        patient_count = paradigm_data['patient_count']

        # Check 1: Drugs with same RxNorm code (same parent drug)
        rxnorm_to_drugs = defaultdict(list)
        therapeutic_to_drugs = defaultdict(list)

        for drug in drugs:
            drug_lower = drug.lower().strip()
            if drug_lower in drug_lookup:
                info = drug_lookup[drug_lower]

                # Group by RxNorm code
                rxnorm = info['rxnorm_in']
                if pd.notna(rxnorm) and rxnorm != '':
                    rxnorm_to_drugs[rxnorm].append(drug)

                # Group by therapeutic_normalized
                ther_norm = info['therapeutic_normalized']
                if pd.notna(ther_norm) and ther_norm != '':
                    therapeutic_to_drugs[ther_norm].append(drug)

        # Flag paradigms with multiple drugs sharing same RxNorm
        for rxnorm, drug_list in rxnorm_to_drugs.items():
            if len(drug_list) > 1:
                issues.append({
                    'paradigm_id': paradigm_id,
                    'type': 'rxnorm_duplicate',
                    'issue': f"Multiple drugs with same RxNorm {rxnorm}",
                    'drugs': drug_list,
                    'patient_count': patient_count,
                    'all_paradigm_drugs': drugs
                })

        # Flag paradigms with multiple drugs sharing same therapeutic_normalized
        for ther_norm, drug_list in therapeutic_to_drugs.items():
            if len(drug_list) > 1:
                # Check if this is already flagged as rxnorm_duplicate
                already_flagged = any(
                    issue['paradigm_id'] == paradigm_id and
                    issue['type'] == 'rxnorm_duplicate' and
                    set(issue['drugs']) == set(drug_list)
                    for issue in issues
                )
                if not already_flagged:
                    issues.append({
                        'paradigm_id': paradigm_id,
                        'type': 'therapeutic_duplicate',
                        'issue': f"Multiple drugs with same therapeutic_normalized '{ther_norm}'",
                        'drugs': drug_list,
                        'patient_count': patient_count,
                        'all_paradigm_drugs': drugs
                    })

        # Check 2: Supportive care drugs in paradigm
        supportive_drugs = []
        for drug in drugs:
            drug_lower = drug.lower().strip()
            if drug_lower in drug_lookup:
                info = drug_lookup[drug_lower]
                if info['is_supportive_care'] == True or info['drug_category'] == 'supportive_care':
                    supportive_drugs.append({
                        'drug': drug,
                        'category': info['drug_category'],
                        'is_supportive': info['is_supportive_care']
                    })

        if supportive_drugs:
            issues.append({
                'paradigm_id': paradigm_id,
                'type': 'supportive_care',
                'issue': f"{len(supportive_drugs)} supportive care drug(s) in paradigm",
                'supportive_drugs': supportive_drugs,
                'patient_count': patient_count,
                'all_paradigm_drugs': drugs
            })

    return issues

def print_issues_report(issues):
    """Print detailed report of issues."""

    print("="*100)
    print("PARADIGM VALIDATION REPORT")
    print("="*100)

    # Group by type
    rxnorm_dupes = [i for i in issues if i['type'] == 'rxnorm_duplicate']
    ther_dupes = [i for i in issues if i['type'] == 'therapeutic_duplicate']
    supportive = [i for i in issues if i['type'] == 'supportive_care']

    print(f"\nTotal issues found: {len(issues)}")
    print(f"  - RxNorm duplicates: {len(rxnorm_dupes)}")
    print(f"  - Therapeutic duplicates: {len(ther_dupes)}")
    print(f"  - Supportive care contamination: {len(supportive)}")

    # Print RxNorm duplicates
    if rxnorm_dupes:
        print("\n" + "="*100)
        print("RXNORM DUPLICATES (Same drug with different names)")
        print("="*100)
        for issue in sorted(rxnorm_dupes, key=lambda x: x['patient_count'], reverse=True):
            print(f"\n{issue['paradigm_id']}: {issue['patient_count']} patients")
            print(f"  Issue: {issue['issue']}")
            print(f"  Duplicate drugs: {', '.join(issue['drugs'])}")
            print(f"  Full paradigm: {', '.join(issue['all_paradigm_drugs'])}")

    # Print therapeutic duplicates
    if ther_dupes:
        print("\n" + "="*100)
        print("THERAPEUTIC DUPLICATES (Same therapeutic_normalized)")
        print("="*100)
        for issue in sorted(ther_dupes, key=lambda x: x['patient_count'], reverse=True):
            print(f"\n{issue['paradigm_id']}: {issue['patient_count']} patients")
            print(f"  Issue: {issue['issue']}")
            print(f"  Duplicate drugs: {', '.join(issue['drugs'])}")
            print(f"  Full paradigm: {', '.join(issue['all_paradigm_drugs'])}")

    # Print supportive care
    if supportive:
        print("\n" + "="*100)
        print("SUPPORTIVE CARE CONTAMINATION")
        print("="*100)
        for issue in sorted(supportive, key=lambda x: x['patient_count'], reverse=True):
            print(f"\n{issue['paradigm_id']}: {issue['patient_count']} patients")
            print(f"  Issue: {issue['issue']}")
            for sd in issue['supportive_drugs']:
                print(f"    - {sd['drug']}: category={sd['category']}, is_supportive={sd['is_supportive']}")
            print(f"  Full paradigm: {', '.join(issue['all_paradigm_drugs'])}")

    # Summary statistics
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)

    total_patients_affected_rxnorm = sum(i['patient_count'] for i in rxnorm_dupes)
    total_patients_affected_ther = sum(i['patient_count'] for i in ther_dupes)
    total_patients_affected_supp = sum(i['patient_count'] for i in supportive)

    print(f"\nPatients affected by RxNorm duplicates: {total_patients_affected_rxnorm}")
    print(f"Patients affected by therapeutic duplicates: {total_patients_affected_ther}")
    print(f"Patients affected by supportive care: {total_patients_affected_supp}")

    # Most common issues
    if rxnorm_dupes:
        print("\nMost common RxNorm duplicate pairs:")
        from collections import Counter
        pairs = Counter()
        for issue in rxnorm_dupes:
            drug_pair = tuple(sorted(issue['drugs']))
            pairs[drug_pair] += issue['patient_count']
        for pair, count in pairs.most_common(10):
            print(f"  {' + '.join(pair)}: {count} patients")

    if supportive:
        print("\nMost common supportive care drugs:")
        from collections import Counter
        supp_counts = Counter()
        for issue in supportive:
            for sd in issue['supportive_drugs']:
                supp_counts[sd['drug']] += issue['patient_count']
        for drug, count in supp_counts.most_common(10):
            print(f"  {drug}: {count} patients")

def main():
    print("Loading data...")
    paradigms, drugs_df = load_data()

    print(f"Loaded {len(paradigms)} paradigms")
    print(f"Loaded {len(drugs_df)} drugs from reference")

    print("\nChecking paradigms for issues...")
    issues = check_paradigm_issues(paradigms, drugs_df)

    print_issues_report(issues)

    # Save issues to file
    issues_file = Path(__file__).parent / 'data/treatment_paradigms/paradigm_validation_issues.json'
    with open(issues_file, 'w') as f:
        json.dump(issues, f, indent=2, default=str)
    print(f"\n✓ Detailed issues saved to {issues_file}")

if __name__ == '__main__':
    main()
