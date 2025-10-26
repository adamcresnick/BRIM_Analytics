#!/usr/bin/env python3
"""
Empirical Treatment Paradigm Discovery
========================================
Data-driven analysis to discover ALL treatment patterns across the patient cohort,
not just the most common ones.

Approach:
1. Extract complete chemotherapy data for all patients
2. Create treatment "fingerprints" for each patient (drug combinations, temporal patterns)
3. Identify distinct treatment paradigms empirically
4. Cluster patients by similar treatment patterns
5. Characterize each paradigm (drug sets, sequences, patient counts)

Author: RADIANT PCA Project
Date: 2025-10-25
"""

import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json
from pathlib import Path

class TreatmentParadigmAnalyzer:
    """Discover treatment paradigms empirically from chemotherapy data"""

    def __init__(self, chemo_data_path: str, use_normalized_names: bool = True):
        """
        Initialize with path to extracted chemotherapy CSV

        Args:
            chemo_data_path: Path to CSV from v_chemo_medications query
            use_normalized_names: If True, use chemo_therapeutic_normalized for grouping/continuity
                                 (recommended to avoid false drug duplicates from salt variants)
        """
        self.data = pd.read_csv(chemo_data_path)
        self.use_normalized_names = use_normalized_names

        # Use medication_authored_date if available, otherwise medication_start_date or order_date
        if 'medication_authored_date' in self.data.columns:
            date_col = 'medication_authored_date'
        elif 'medication_start_date' in self.data.columns:
            date_col = 'medication_start_date'
        else:
            date_col = 'order_date'
        self.data['order_date'] = pd.to_datetime(self.data[date_col], format='mixed', utc=True)

        # Determine which drug name column to use for analysis
        if use_normalized_names and 'chemo_therapeutic_normalized' in self.data.columns:
            self.drug_column = 'chemo_therapeutic_normalized'
            print(f"Using therapeutic_normalized column for drug continuity detection")
        else:
            self.drug_column = 'chemo_preferred_name'
            if use_normalized_names:
                print("WARNING: therapeutic_normalized column not found, falling back to chemo_preferred_name")
                print("         This may cause false drug duplicates (e.g., 'irinotecan' vs 'Irinotecan Hydrochloride')")

        # Results
        self.patient_fingerprints = {}
        self.paradigms = {}

    def create_patient_fingerprints(self):
        """
        Create treatment "fingerprints" for each patient

        Fingerprint includes:
        - Unique drugs received (set)
        - Drug combinations (concurrent within 30 days)
        - Sequential patterns (order of drug introduction)
        - Treatment duration
        - Number of different regimens
        """
        print("Creating patient treatment fingerprints...")

        for patient_id, patient_data in self.data.groupby('patient_fhir_id'):
            # Sort by date
            patient_data = patient_data.sort_values('order_date')

            # Unique drugs (using therapeutic_normalized for accurate drug continuity)
            # Filter out NaN values
            unique_drugs = set(patient_data[self.drug_column].dropna().unique())

            # Time-windowed combinations (30-day windows)
            combinations = self._find_concurrent_drugs(patient_data)

            # Sequential introduction pattern
            sequence = self._find_drug_sequence(patient_data)

            # Treatment timeline
            first_order = patient_data['order_date'].min()
            last_order = patient_data['order_date'].max()
            duration_days = (last_order - first_order).days if pd.notna(last_order) and pd.notna(first_order) else 0

            # Store fingerprint
            self.patient_fingerprints[patient_id] = {
                'unique_drugs': unique_drugs,
                'drug_count': len(unique_drugs),
                'concurrent_combinations': combinations,
                'sequential_pattern': sequence,
                'first_treatment': first_order,
                'last_treatment': last_order,
                'duration_days': duration_days,
                'total_orders': len(patient_data)
            }

        print(f"  Created fingerprints for {len(self.patient_fingerprints)} patients")

    def _find_concurrent_drugs(self, patient_data, window_days=30):
        """Find drugs given concurrently (within time window)"""
        combinations = set()

        for idx, row in patient_data.iterrows():
            current_date = row['order_date']
            current_drug = row[self.drug_column]

            # Skip if current drug is NaN/NULL
            if pd.isna(current_drug):
                continue

            # Find other drugs within window
            window_start = current_date - timedelta(days=window_days)
            window_end = current_date + timedelta(days=window_days)

            concurrent = patient_data[
                (patient_data['order_date'] >= window_start) &
                (patient_data['order_date'] <= window_end) &
                (patient_data[self.drug_column] != current_drug) &
                (patient_data[self.drug_column].notna())  # Exclude NaN values
            ][self.drug_column].unique()

            if len(concurrent) > 0:
                for other_drug in concurrent:
                    combo = tuple(sorted([current_drug, other_drug]))
                    combinations.add(combo)

        return list(combinations)

    def _find_drug_sequence(self, patient_data, phase_gap_days=90):
        """
        Find sequential introduction pattern of drugs
        Drugs introduced within phase_gap_days are considered same phase
        """
        patient_data = patient_data.sort_values('order_date')

        # Get first occurrence of each drug (using therapeutic_normalized for drug continuity)
        first_use = patient_data.groupby(self.drug_column)['order_date'].min().sort_values()

        # Group into phases based on time gaps
        phases = []
        current_phase = []
        last_date = None

        for drug, date in first_use.items():
            if last_date is None or (date - last_date).days <= phase_gap_days:
                current_phase.append(drug)
            else:
                if current_phase:
                    phases.append(current_phase)
                current_phase = [drug]
            last_date = date

        if current_phase:
            phases.append(current_phase)

        return phases

    def discover_paradigms(self):
        """
        Discover distinct treatment paradigms based on patient fingerprints

        Paradigms are defined by:
        1. Core drug set (drugs used together)
        2. Sequential pattern (if applicable)
        3. Minimum patient count threshold
        """
        print("\nDiscovering treatment paradigms...")

        # Group by unique drug sets
        drug_set_groups = defaultdict(list)
        for patient_id, fingerprint in self.patient_fingerprints.items():
            drug_set = frozenset(fingerprint['unique_drugs'])
            drug_set_groups[drug_set].append(patient_id)

        # Also group by common combinations
        combo_groups = defaultdict(list)
        for patient_id, fingerprint in self.patient_fingerprints.items():
            for combo in fingerprint['concurrent_combinations']:
                combo_groups[frozenset(combo)].append(patient_id)

        # Create paradigms
        paradigm_id = 1

        # Paradigm 1: Exact drug set matches (2+ patients)
        print("\n  Paradigm Type 1: Complete Drug Set Matches")
        for drug_set, patients in sorted(drug_set_groups.items(), key=lambda x: -len(x[1])):
            if len(patients) >= 2 and len(drug_set) >= 2:  # At least 2 patients, 2+ drugs
                self.paradigms[f"P{paradigm_id:03d}"] = {
                    'type': 'complete_drug_set',
                    'drugs': sorted(list(drug_set)),
                    'patient_ids': patients,
                    'patient_count': len(patients),
                    'description': f"{len(drug_set)} drugs: " + ", ".join(sorted(list(drug_set))[:5])
                }
                paradigm_id += 1

        # Paradigm 2: Common combinations (even if not complete sets)
        print("  Paradigm Type 2: Common Drug Combinations")
        for combo, patients in sorted(combo_groups.items(), key=lambda x: -len(x[1])):
            if len(patients) >= 5 and len(combo) >= 2:  # At least 5 patients
                combo_key = f"C{paradigm_id:03d}"
                # Check if not already captured in complete sets
                if not any(combo.issubset(p['drugs']) for p in self.paradigms.values() if p['type'] == 'complete_drug_set'):
                    self.paradigms[combo_key] = {
                        'type': 'drug_combination',
                        'drugs': sorted(list(combo)),
                        'patient_ids': patients,
                        'patient_count': len(patients),
                        'description': " + ".join(sorted(list(combo)))
                    }
                    paradigm_id += 1

        print(f"\n  Discovered {len(self.paradigms)} distinct treatment paradigms")

    def summarize_paradigms(self):
        """Create summary statistics for each paradigm"""
        print("\n" + "=" * 80)
        print("TREATMENT PARADIGM SUMMARY")
        print("=" * 80)

        # Sort by patient count
        sorted_paradigms = sorted(
            self.paradigms.items(),
            key=lambda x: x[1]['patient_count'],
            reverse=True
        )

        for paradigm_id, paradigm in sorted_paradigms[:50]:  # Top 50
            print(f"\n{paradigm_id}: {paradigm['description']}")
            print(f"  Type: {paradigm['type']}")
            print(f"  Patients: {paradigm['patient_count']}")
            print(f"  Drugs ({len(paradigm['drugs'])}): {', '.join(paradigm['drugs'][:10])}")
            if len(paradigm['drugs']) > 10:
                print(f"       ... and {len(paradigm['drugs']) - 10} more")

        return sorted_paradigms

    def export_results(self, output_dir: str):
        """Export paradigms and patient assignments to JSON/CSV"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Export paradigms
        paradigms_json = {
            pid: {
                'type': p['type'],
                'drugs': p['drugs'],
                'patient_count': p['patient_count'],
                'description': p['description']
            }
            for pid, p in self.paradigms.items()
        }

        with open(output_path / 'treatment_paradigms.json', 'w') as f:
            json.dump(paradigms_json, f, indent=2)

        # Export patient assignments (many-to-many)
        assignments = []
        for paradigm_id, paradigm in self.paradigms.items():
            for patient_id in paradigm['patient_ids']:
                assignments.append({
                    'paradigm_id': paradigm_id,
                    'patient_fhir_id': patient_id,
                    'paradigm_type': paradigm['type'],
                    'drug_count': len(paradigm['drugs']),
                    'cohort_size': paradigm['patient_count']
                })

        pd.DataFrame(assignments).to_csv(
            output_path / 'patient_paradigm_assignments.csv',
            index=False
        )

        # Export patient fingerprints
        fingerprints_df = pd.DataFrame([
            {
                'patient_fhir_id': pid,
                'unique_drugs': '; '.join(sorted(fp['unique_drugs'])),
                'drug_count': fp['drug_count'],
                'total_orders': fp['total_orders'],
                'duration_days': fp['duration_days']
            }
            for pid, fp in self.patient_fingerprints.items()
        ])
        fingerprints_df.to_csv(output_path / 'patient_treatment_fingerprints.csv', index=False)

        print(f"\n✅ Results exported to {output_path}")
        print(f"   - treatment_paradigms.json: {len(self.paradigms)} paradigms")
        print(f"   - patient_paradigm_assignments.csv: {len(assignments)} assignments")
        print(f"   - patient_treatment_fingerprints.csv: {len(self.patient_fingerprints)} patients")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python empirical_treatment_paradigm_analysis.py <chemotherapy_data.csv>")
        sys.exit(1)

    # Run analysis
    analyzer = TreatmentParadigmAnalyzer(sys.argv[1])
    analyzer.create_patient_fingerprints()
    analyzer.discover_paradigms()
    sorted_paradigms = analyzer.summarize_paradigms()

    # Export
    output_dir = Path(sys.argv[1]).parent / 'treatment_paradigms'
    analyzer.export_results(str(output_dir))
