#!/usr/bin/env python3
"""
Fix decisions.csv - move aggregation_prompt content to prompt column for aggregation decisions
BRIM requires prompt column to be populated for ALL decisions
"""

import csv
import shutil
from datetime import datetime

# Increase CSV field size limit
csv.field_size_limit(10 * 1024 * 1024)

def fix_decisions_csv(input_file):
    """Move aggregation_prompt to prompt column for aggregation-type decisions"""
    
    # Create backup
    backup_file = input_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    shutil.copy2(input_file, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    fixed_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        
        for row in reader:
            decision_type = row.get('decision_type', '').strip()
            prompt = row.get('prompt', '').strip()
            aggregation_prompt = row.get('aggregation_prompt', '').strip()
            
            # If decision_type is 'aggregation' and prompt is empty, use aggregation_prompt
            if decision_type == 'aggregation' and not prompt and aggregation_prompt:
                row['prompt'] = aggregation_prompt
                print(f"  Fixed: {row['decision_name']} - moved aggregation_prompt to prompt")
            
            fixed_rows.append(row)
    
    # Write fixed CSV
    with open(input_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(fixed_rows)
    
    print(f"\n✅ Fixed decisions.csv written")
    print(f"   Total decisions: {len(fixed_rows)}")
    
    return len(fixed_rows)

if __name__ == "__main__":
    decisions_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/decisions.csv"
    
    print("=" * 80)
    print("FIXING DECISIONS.CSV - POPULATE PROMPT FOR AGGREGATION DECISIONS")
    print("=" * 80)
    
    total = fix_decisions_csv(decisions_file)
    
    print(f"\n{'=' * 80}")
    print(f"✅ FIX COMPLETE")
    print(f"{'=' * 80}")
    print(f"\nAll {total} decisions now have prompts populated")
    print(f"Aggregation decisions now use their aggregation_prompt in the prompt field")
    print(f"\nRe-upload decisions.csv to BRIM")
