#!/usr/bin/env python3
"""
Find ALL duplicate NOTE_IDs in project CSV using proper CSV parsing
"""

import csv

# Increase CSV field size limit
csv.field_size_limit(10 * 1024 * 1024)

def find_all_duplicates(csv_file):
    """Find all duplicate NOTE_IDs"""
    
    note_id_count = {}
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
        
        for row in reader:
            if len(row) < 1:
                continue
            note_id = row[0]
            note_id_count[note_id] = note_id_count.get(note_id, 0) + 1
    
    duplicates = {nid: count for nid, count in note_id_count.items() if count > 1}
    
    print(f"Total unique NOTE_IDs: {len(note_id_count)}")
    print(f"Duplicate NOTE_IDs: {len(duplicates)}")
    
    if duplicates:
        print("\nDuplicates found:")
        for nid, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True):
            # Only show first/last 20 chars to avoid printing full IDs
            short_id = nid[:20] + "..." + nid[-20:] if len(nid) > 45 else nid
            print(f"  {short_id}: appears {count} times")
    else:
        print("\n✅ NO DUPLICATES")
    
    return len(duplicates)

if __name__ == "__main__":
    import sys
    
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/project_deduped.csv"
    
    print(f"Checking: {csv_file}")
    print("=" * 80)
    find_all_duplicates(csv_file)
