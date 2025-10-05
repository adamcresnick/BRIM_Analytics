#!/usr/bin/env python3
"""
Fix variables.csv by populating the prompt_template field

BRIM requires that variables have a prompt_template field populated.
Currently all our variables have empty prompt_template, causing decisions to be skipped.

Solution: Populate prompt_template from the instruction field.
"""

import csv
import shutil
from datetime import datetime

def populate_prompt_templates(input_file, output_file):
    """Populate prompt_template field in variables.csv"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Populate prompt_template from instruction
    updated_count = 0
    for row in rows:
        if not row.get('prompt_template', '').strip() and row.get('instruction', '').strip():
            # Use instruction as the prompt_template
            row['prompt_template'] = row['instruction']
            updated_count += 1
    
    # Write updated CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ Updated {updated_count} variables with prompt_template")
    return updated_count

if __name__ == "__main__":
    input_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables.csv"
    output_file = input_file  # Overwrite in place
    
    print("=" * 80)
    print("POPULATING prompt_template FIELDS IN variables.csv")
    print("=" * 80)
    print()
    
    # Backup first
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = input_file.replace('.csv', f'_backup_{timestamp}.csv')
    shutil.copy(input_file, backup_file)
    print(f"📦 Backed up to: {backup_file}")
    print()
    
    # Populate
    updated = populate_prompt_templates(input_file, output_file)
    
    print()
    print("=" * 80)
    print("✅ COMPLETE")
    print("=" * 80)
    print()
    print("Now re-upload variables.csv and decisions.csv to BRIM")
    print("Decisions should no longer be skipped!")
