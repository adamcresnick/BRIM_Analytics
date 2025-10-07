#!/usr/bin/env python3
"""
Fix patient ID inconsistency in project.csv

Problem: Some rows have PERSON_ID='1277724', others have 'C1277724'
Solution: Standardize all to 'C1277724'
"""

import csv
import sys
from datetime import datetime

def fix_patient_ids(input_file, output_file):
    """Fix inconsistent patient IDs"""
    
    csv.field_size_limit(10000000)  # Handle large fields
    
    # Backup
    backup_file = input_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    
    import shutil
    shutil.copy2(input_file, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    fixed_count = 0
    total_rows = 0
    
    with open(input_file, 'r', encoding='utf-8') as fin, \
         open(output_file, 'w', encoding='utf-8', newline='') as fout:
        
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            total_rows += 1
            
            # Check if PERSON_ID is missing 'C' prefix
            person_id = row['PERSON_ID']
            if person_id == '1277724':
                row['PERSON_ID'] = 'C1277724'
                fixed_count += 1
                print(f"Fixed: {row['NOTE_ID']} - Changed PERSON_ID from '1277724' to 'C1277724'")
            
            writer.writerow(row)
    
    print(f"\n✅ Fixed {fixed_count} rows out of {total_rows} total rows")
    print(f"✅ Output written to: {output_file}")
    
    return fixed_count

if __name__ == "__main__":
    input_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv"
    output_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/project_fixed.csv"
    
    print("=" * 80)
    print("FIXING PATIENT ID INCONSISTENCY IN PROJECT.CSV")
    print("=" * 80)
    print()
    print("Problem: PERSON_ID field has both '1277724' and 'C1277724'")
    print("Solution: Standardize all to 'C1277724'")
    print()
    
    fixed = fix_patient_ids(input_file, output_file)
    
    print()
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    # Verify the fix
    import subprocess
    result = subprocess.run(
        f"grep -E '^[^,]+,1277724,' {output_file} | wc -l",
        shell=True,
        capture_output=True,
        text=True
    )
    
    remaining = int(result.stdout.strip())
    
    if remaining == 0:
        print("✅ SUCCESS: All patient IDs now use 'C1277724' format")
        print("\nNext steps:")
        print("1. Replace project.csv with project_fixed.csv")
        print("2. Re-upload to BRIM")
        print("3. Should now show '1 patient' instead of '2 patients'")
    else:
        print(f"⚠️  WARNING: Still {remaining} rows with '1277724' (without C)")
