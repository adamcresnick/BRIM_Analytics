#!/usr/bin/env python3
"""
Remove duplicate NOTE_IDs from project.csv
Keeps only the first occurrence of each NOTE_ID
Creates backup before modification
"""

import csv
import shutil
from datetime import datetime

# Increase CSV field size limit
csv.field_size_limit(10 * 1024 * 1024)

def remove_duplicates(input_csv, output_csv):
    """Remove duplicate NOTE_IDs, keeping first occurrence"""
    
    # Create backup
    backup_file = input_csv.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    shutil.copy2(input_csv, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    seen_note_ids = set()
    rows_kept = []
    rows_removed = []
    
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows_kept.append(header)  # Keep header
        
        for line_num, row in enumerate(reader, start=2):
            if len(row) < 1:
                continue
                
            note_id = row[0]  # Column 1: NOTE_ID
            
            if note_id in seen_note_ids:
                # Duplicate - remove it
                rows_removed.append({
                    'line_num': line_num,
                    'note_id': note_id,
                    'note_datetime': row[2] if len(row) > 2 else "",
                    'note_title': row[4] if len(row) > 4 else ""
                })
            else:
                # First occurrence - keep it
                seen_note_ids.add(note_id)
                rows_kept.append(row)
    
    # Write cleaned CSV
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows_kept)
    
    print(f"\n✅ Cleaned CSV written to: {output_csv}")
    print(f"   Total rows in input: {len(rows_kept) + len(rows_removed) - 1}")  # -1 for header
    print(f"   Rows kept: {len(rows_kept) - 1}")  # -1 for header
    print(f"   Duplicate rows removed: {len(rows_removed)}")
    
    if rows_removed:
        print(f"\n📋 Removed duplicate NOTE_IDs:")
        for dup in rows_removed:
            print(f"   Line {dup['line_num']}: {dup['note_id']}")
            print(f"      DATETIME: {dup['note_datetime']}")
            print(f"      TITLE: {dup['note_title']}")
    
    return len(rows_removed)

if __name__ == "__main__":
    project_dir = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2"
    input_file = f"{project_dir}/project.csv"
    output_file = f"{project_dir}/project_deduped.csv"
    
    print("=" * 80)
    print("REMOVING DUPLICATE NOTE_IDs FROM project.csv")
    print("=" * 80)
    
    duplicates_removed = remove_duplicates(input_file, output_file)
    
    print(f"\n{'=' * 80}")
    print(f"✅ DEDUPLICATION COMPLETE")
    print(f"{'=' * 80}")
    print(f"\nNext steps:")
    print(f"1. Review the deduplicated file: {output_file}")
    print(f"2. If correct, replace original:")
    print(f"   mv {output_file} {input_file}")
    print(f"3. Backup is saved if you need to revert")
