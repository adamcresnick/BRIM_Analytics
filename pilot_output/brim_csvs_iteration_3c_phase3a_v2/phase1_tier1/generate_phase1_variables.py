#!/usr/bin/env python3
"""
Generate Phase 1 Variables CSV (Excluding Athena Pre-populated Variables)

This script creates a filtered variables.csv containing only variables that
require note extraction, excluding the 8 variables pre-populated from Athena.

Excluded variables (8 total):
1. patient_gender
2. date_of_birth
3. age_at_diagnosis
4. race
5. ethnicity
6. chemotherapy_received
7. chemotherapy_agents
8. concomitant_medications

Included variables (25 total):
- All variables requiring note extraction

Usage:
    python scripts/generate_phase1_variables.py \
        --variables pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables.csv \
        --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables_phase1.csv
"""

import pandas as pd
import argparse
from pathlib import Path


# Variables pre-populated from Athena (to be excluded)
ATHENA_VARIABLES = [
    'patient_gender',
    'date_of_birth',
    'age_at_diagnosis',
    'race',
    'ethnicity',
    'chemotherapy_received',
    'chemotherapy_agents',
    'concomitant_medications'
]


def generate_phase1_variables(variables_path, output_path, athena_vars=None):
    """
    Generate Phase 1 variables CSV excluding Athena-prepopulated variables.
    
    Args:
        variables_path: Path to full variables.csv
        output_path: Path to save Phase 1 variables.csv
        athena_vars: List of Athena variable names to exclude (default: ATHENA_VARIABLES)
        
    Returns:
        int: Number of Phase 1 variables
    """
    
    if athena_vars is None:
        athena_vars = ATHENA_VARIABLES
    
    print("=" * 80)
    print("GENERATING PHASE 1 VARIABLES CSV (EXCLUDING ATHENA VARIABLES)")
    print("=" * 80)
    
    # Load full variables
    print(f"\n📂 Loading variables from {variables_path}")
    variables_df = pd.read_csv(variables_path)
    print(f"  Total variables: {len(variables_df)}")
    
    # Display all variables by scope
    print(f"\n📊 Original Variable Distribution by Scope:")
    scope_counts = variables_df['scope'].value_counts()
    for scope, count in scope_counts.items():
        print(f"  {scope:<30} {count:>3} variables")
    
    # Identify Athena variables in the file
    print(f"\n🔍 Identifying Athena-prepopulated variables to exclude...")
    athena_in_file = variables_df[variables_df['variable_name'].isin(athena_vars)]
    print(f"  Found {len(athena_in_file)} Athena variables:")
    for idx, row in athena_in_file.iterrows():
        print(f"    ❌ {row['variable_name']:<40} (scope: {row['scope']})")
    
    # Check for any Athena variables not in file (shouldn't happen)
    athena_not_found = set(athena_vars) - set(variables_df['variable_name'])
    if athena_not_found:
        print(f"\n  ⚠️  Warning: {len(athena_not_found)} Athena variables not found in file:")
        for var_name in athena_not_found:
            print(f"    - {var_name}")
    
    # Filter to Phase 1 variables (exclude Athena)
    print(f"\n✂️  Filtering to Phase 1 variables...")
    phase1_variables = variables_df[~variables_df['variable_name'].isin(athena_vars)].copy()
    print(f"  Phase 1 variables: {len(phase1_variables)}")
    
    # Display Phase 1 variables by scope
    print(f"\n📊 Phase 1 Variable Distribution by Scope:")
    phase1_scope_counts = phase1_variables['scope'].value_counts()
    for scope, count in phase1_scope_counts.items():
        print(f"  {scope:<30} {count:>3} variables")
    
    # List all Phase 1 variables
    print(f"\n📋 Phase 1 Variables (Note Extraction Required):")
    print(f"{'Variable Name':<45} {'Scope':<25} {'Type':<15}")
    print("-" * 87)
    for idx, row in phase1_variables.iterrows():
        print(f"{row['variable_name']:<45} {row['scope']:<25} {row['variable_type']:<15}")
    
    # Save Phase 1 variables
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    phase1_variables.to_csv(output_path, index=False)
    
    print(f"\n💾 Saved Phase 1 variables to: {output_path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("PHASE 1 VARIABLES GENERATION SUMMARY")
    print("=" * 80)
    print(f"Original variables: {len(variables_df)}")
    print(f"Athena-prepopulated (excluded): {len(athena_in_file)}")
    print(f"Phase 1 variables (note extraction): {len(phase1_variables)}")
    print(f"Reduction: {len(athena_in_file)} variables ({len(athena_in_file)/len(variables_df)*100:.1f}%)")
    
    print(f"\n✅ Phase 1 variables CSV generation complete!")
    print(f"➡️  Next: Upload to BRIM as variables.csv")
    print(f"    - project_phase1_tier1.csv → project.csv")
    print(f"    - variables_phase1.csv → variables.csv")
    print(f"    - decisions.csv (no changes)")
    
    return len(phase1_variables)


def main():
    parser = argparse.ArgumentParser(
        description='Generate Phase 1 variables CSV (excluding Athena variables)'
    )
    parser.add_argument('--variables', required=True,
                       help='Path to full variables.csv')
    parser.add_argument('--output', required=True,
                       help='Output path for Phase 1 variables.csv')
    parser.add_argument('--athena-vars', nargs='+',
                       help='Optional: Custom list of Athena variable names to exclude')
    
    args = parser.parse_args()
    
    # Verify input file exists
    if not Path(args.variables).exists():
        print(f"❌ Error: variables file not found: {args.variables}")
        return 1
    
    # Generate Phase 1 variables
    phase1_count = generate_phase1_variables(
        args.variables,
        args.output,
        args.athena_vars
    )
    
    return 0


if __name__ == '__main__':
    exit(main())
