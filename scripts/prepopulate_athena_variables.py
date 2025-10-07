#!/usr/bin/env python3
"""
Pre-populate BRIM Variables from Athena Materialized Views

This script directly populates variables that are available from Athena
queries (materialized views) instead of extracting them from clinical notes.

This is Phase 0 of the iterative extraction strategy - preparing variables
that don't need note extraction.

Variables pre-populated (8 total):
1. patient_gender - from demographics
2. date_of_birth - from demographics
3. race - from demographics
4. ethnicity - from demographics
5. age_at_diagnosis - calculated from birth_date + diagnosis_date
6. chemotherapy_received - Yes/No based on medication records
7. chemotherapy_agents - from medications (filtered to chemo drugs)
8. concomitant_medications - from medications (non-chemo drugs)

Usage:
    python scripts/prepopulate_athena_variables.py \
        --demographics pilot_output/brim_csvs_iteration_3c_phase3a_v2/reference_patient_demographics.csv \
        --medications pilot_output/brim_csvs_iteration_3c_phase3a_v2/reference_patient_medications.csv \
        --imaging pilot_output/brim_csvs_iteration_3c_phase3a_v2/reference_patient_imaging.csv \
        --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/athena_prepopulated_values.json
"""

import pandas as pd
import json
import argparse
from datetime import datetime
from pathlib import Path


# Known chemotherapy drug patterns (RxNorm codes or names)
CHEMOTHERAPY_PATTERNS = [
    'temozolomide', 'temodar',
    'vincristine', 'oncovin',
    'carboplatin', 'paraplatin',
    'cisplatin', 'platinol',
    'etoposide', 'vepesid',
    'lomustine', 'ccnu', 'gleostine',
    'bevacizumab', 'avastin',
    'procarbazine',
    'cyclophosphamide', 'cytoxan',
    'doxorubicin', 'adriamycin',
    'methotrexate',
    'cytarabine', 'ara-c',
    'ifosfamide',
    'dacarbazine', 'dtic',
    'nitrosourea'
]


def is_chemotherapy(medication_name):
    """Determine if a medication is chemotherapy based on name patterns."""
    if pd.isna(medication_name):
        return False
    
    med_lower = medication_name.lower()
    for pattern in CHEMOTHERAPY_PATTERNS:
        if pattern in med_lower:
            return True
    return False


def calculate_age_at_diagnosis(birth_date_str, diagnosis_date_str):
    """Calculate age at diagnosis from birth date and diagnosis date."""
    if pd.isna(birth_date_str) or pd.isna(diagnosis_date_str):
        return None
    
    try:
        birth_date = pd.to_datetime(birth_date_str)
        diagnosis_date = pd.to_datetime(diagnosis_date_str)
        
        age = diagnosis_date.year - birth_date.year
        # Adjust if birthday hasn't occurred yet in diagnosis year
        if (diagnosis_date.month, diagnosis_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    except Exception as e:
        print(f"⚠️  Error calculating age: {e}")
        return None


def prepopulate_athena_variables(demographics_path, medications_path, imaging_path, 
                                  diagnosis_date=None):
    """
    Pre-populate variables from Athena materialized views.
    
    Args:
        demographics_path: Path to reference_patient_demographics.csv
        medications_path: Path to reference_patient_medications.csv
        imaging_path: Path to reference_patient_imaging.csv
        diagnosis_date: Optional diagnosis date (str) for age calculation
        
    Returns:
        dict: Pre-populated variable values
    """
    
    print("=" * 80)
    print("PRE-POPULATING VARIABLES FROM ATHENA MATERIALIZED VIEWS")
    print("=" * 80)
    
    prepopulated = {}
    
    # Load demographics
    print(f"\n📊 Loading demographics from {demographics_path}")
    demographics_df = pd.read_csv(demographics_path)
    
    if len(demographics_df) == 0:
        print("⚠️  No demographics data found")
        return prepopulated
    
    # Assume single patient (pilot)
    demo = demographics_df.iloc[0]
    
    # 1. Patient Gender
    if 'gender' in demo and pd.notna(demo['gender']):
        prepopulated['patient_gender'] = {
            'value': demo['gender'],
            'source': 'athena_demographics',
            'confidence': 'high',
            'scope': 'one_per_patient'
        }
        print(f"  ✅ patient_gender: {demo['gender']}")
    
    # 2. Date of Birth
    if 'birth_date' in demo and pd.notna(demo['birth_date']):
        prepopulated['date_of_birth'] = {
            'value': demo['birth_date'],
            'source': 'athena_demographics',
            'confidence': 'high',
            'scope': 'one_per_patient'
        }
        print(f"  ✅ date_of_birth: {demo['birth_date']}")
    
    # 3. Race
    if 'race' in demo and pd.notna(demo['race']):
        prepopulated['race'] = {
            'value': demo['race'],
            'source': 'athena_demographics',
            'confidence': 'high',
            'scope': 'one_per_patient'
        }
        print(f"  ✅ race: {demo['race']}")
    
    # 4. Ethnicity
    if 'ethnicity' in demo and pd.notna(demo['ethnicity']):
        prepopulated['ethnicity'] = {
            'value': demo['ethnicity'],
            'source': 'athena_demographics',
            'confidence': 'high',
            'scope': 'one_per_patient'
        }
        print(f"  ✅ ethnicity: {demo['ethnicity']}")
    
    # 5. Age at Diagnosis (requires diagnosis date)
    if diagnosis_date and 'birth_date' in demo and pd.notna(demo['birth_date']):
        age = calculate_age_at_diagnosis(demo['birth_date'], diagnosis_date)
        if age is not None:
            prepopulated['age_at_diagnosis'] = {
                'value': age,
                'source': 'athena_demographics_calculated',
                'confidence': 'high',
                'scope': 'one_per_patient',
                'calculation': f"diagnosis_date ({diagnosis_date}) - birth_date ({demo['birth_date']})"
            }
            print(f"  ✅ age_at_diagnosis: {age} years")
    else:
        print(f"  ⚠️  age_at_diagnosis: Requires diagnosis_date (not provided or not in notes yet)")
    
    # Load medications
    print(f"\n💊 Loading medications from {medications_path}")
    medications_df = pd.read_csv(medications_path)
    
    if len(medications_df) > 0:
        # 6. Chemotherapy Received
        chemo_meds = medications_df[medications_df['medication_name'].apply(is_chemotherapy)]
        chemo_received = 'Yes' if len(chemo_meds) > 0 else 'No'
        
        prepopulated['chemotherapy_received'] = {
            'value': chemo_received,
            'source': 'athena_medications',
            'confidence': 'high',
            'scope': 'one_per_patient',
            'medication_count': len(chemo_meds)
        }
        print(f"  ✅ chemotherapy_received: {chemo_received} ({len(chemo_meds)} chemo medications)")
        
        # 7. Chemotherapy Agents
        if len(chemo_meds) > 0:
            chemo_agents = chemo_meds['medication_name'].tolist()
            prepopulated['chemotherapy_agents'] = {
                'value': chemo_agents,
                'source': 'athena_medications',
                'confidence': 'high',
                'scope': 'many_per_note',  # Each agent is a separate entry
                'records': []
            }
            
            for idx, med_row in chemo_meds.iterrows():
                prepopulated['chemotherapy_agents']['records'].append({
                    'agent_name': med_row['medication_name'],
                    'start_date': med_row.get('medication_start_date'),
                    'end_date': med_row.get('medication_end_date'),
                    'status': med_row.get('medication_status'),
                    'rxnorm_code': med_row.get('rxnorm_code')
                })
            
            print(f"  ✅ chemotherapy_agents: {len(chemo_agents)} agents")
            for agent in chemo_agents:
                print(f"      - {agent}")
        
        # 8. Concomitant Medications (non-chemo)
        non_chemo_meds = medications_df[~medications_df['medication_name'].apply(is_chemotherapy)]
        if len(non_chemo_meds) > 0:
            concomitant_meds = non_chemo_meds['medication_name'].tolist()
            prepopulated['concomitant_medications'] = {
                'value': concomitant_meds,
                'source': 'athena_medications',
                'confidence': 'high',
                'scope': 'many_per_note',
                'records': []
            }
            
            for idx, med_row in non_chemo_meds.iterrows():
                prepopulated['concomitant_medications']['records'].append({
                    'medication_name': med_row['medication_name'],
                    'start_date': med_row.get('medication_start_date'),
                    'end_date': med_row.get('medication_end_date'),
                    'status': med_row.get('medication_status'),
                    'rxnorm_code': med_row.get('rxnorm_code')
                })
            
            print(f"  ✅ concomitant_medications: {len(concomitant_meds)} medications")
            for med in concomitant_meds:
                print(f"      - {med}")
    else:
        print("  ⚠️  No medications data found")
    
    # Load imaging (informational - not pre-populating imaging_findings)
    print(f"\n🔬 Loading imaging from {imaging_path}")
    imaging_df = pd.read_csv(imaging_path)
    if len(imaging_df) > 0:
        print(f"  ℹ️  {len(imaging_df)} imaging studies found (findings require note extraction)")
        imaging_types = imaging_df['imaging_type'].value_counts()
        for img_type, count in imaging_types.items():
            print(f"      - {img_type}: {count} studies")
    
    # Summary
    print("\n" + "=" * 80)
    print("PRE-POPULATION SUMMARY")
    print("=" * 80)
    print(f"✅ Variables pre-populated: {len(prepopulated)} of 8 possible")
    print(f"\nPre-populated variables:")
    for var_name in prepopulated.keys():
        print(f"  - {var_name}")
    
    print(f"\n⚠️  Variables requiring note extraction:")
    required_vars = {
        'age_at_diagnosis': 'Needs diagnosis_date from notes',
        'chemotherapy_agents': 'If no Athena medication records',
        'concomitant_medications': 'If no Athena medication records'
    }
    for var_name, reason in required_vars.items():
        if var_name not in prepopulated:
            print(f"  - {var_name}: {reason}")
    
    return prepopulated


def main():
    parser = argparse.ArgumentParser(description='Pre-populate BRIM variables from Athena data')
    parser.add_argument('--demographics', required=True, help='Path to demographics CSV')
    parser.add_argument('--medications', required=True, help='Path to medications CSV')
    parser.add_argument('--imaging', required=True, help='Path to imaging CSV')
    parser.add_argument('--diagnosis-date', help='Diagnosis date (YYYY-MM-DD) for age calculation')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Verify input files exist
    for path_arg, path_val in [('demographics', args.demographics), 
                                ('medications', args.medications),
                                ('imaging', args.imaging)]:
        if not Path(path_val).exists():
            print(f"❌ Error: {path_arg} file not found: {path_val}")
            return 1
    
    # Pre-populate variables
    prepopulated = prepopulate_athena_variables(
        args.demographics,
        args.medications,
        args.imaging,
        args.diagnosis_date
    )
    
    # Save to JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(prepopulated, f, indent=2)
    
    print(f"\n💾 Saved pre-populated variables to: {output_path}")
    print(f"\n✅ Phase 0 complete! {len(prepopulated)} variables pre-populated from Athena.")
    print(f"➡️  Next: Run Phase 1 extraction for remaining {33 - len(prepopulated)} variables")
    
    return 0


if __name__ == '__main__':
    exit(main())
