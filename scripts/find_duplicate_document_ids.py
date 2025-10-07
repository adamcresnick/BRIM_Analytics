#!/usr/bin/env python3
"""
Find duplicate Document IDs in project.csv WITHOUT displaying MRN
Outputs safe metadata only (no column 3 which contains MRN)
"""

import csv
import sys
from collections import defaultdict

# Increase CSV field size limit for large documents
csv.field_size_limit(10 * 1024 * 1024)  # 10MB per field

def find_duplicates(project_csv_path):
    """Find all duplicate NOTE_IDs and their metadata (excluding PERSON_ID/MRN)"""
    
    # Track all NOTE_IDs and their row details
    note_id_rows = defaultdict(list)
    
    with open(project_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
        
        for line_num, row in enumerate(reader, start=2):  # Start at line 2 (after header)
            if len(row) < 5:
                continue
                
            note_id = row[0]  # Column 1: NOTE_ID (this is the Document ID)
            # SKIP row[1] - this is PERSON_ID/MRN - NEVER ACCESS OR DISPLAY
            note_datetime = row[2] if len(row) > 2 else ""  # Column 3: NOTE_DATETIME
            # SKIP row[3] - this is NOTE_TEXT - too large
            note_title = row[4] if len(row) > 4 else ""  # Column 5: NOTE_TITLE
            
            # Store safe metadata (no MRN, no NOTE_TEXT)
            note_id_rows[note_id].append({
                'line_num': line_num,
                'note_datetime': note_datetime,
                'note_title': note_title
            })
    
    # Find duplicates
    duplicates = {note_id: rows for note_id, rows in note_id_rows.items() if len(rows) > 1}
    
    # Write results to file
    output_file = '/tmp/duplicate_analysis_safe.txt'
    
    with open(output_file, 'w') as out:
        out.write("=" * 80 + "\n")
        out.write("DUPLICATE NOTE_IDs ANALYSIS (MRN/PERSON_ID REDACTED)\n")
        out.write("=" * 80 + "\n\n")
        
        out.write(f"Total unique duplicate NOTE_IDs: {len(duplicates)}\n")
        out.write(f"Total documents in file: {len(note_id_rows)}\n\n")
        
        if duplicates:
            out.write("=" * 80 + "\n")
            out.write("DETAILED DUPLICATE ANALYSIS\n")
            out.write("=" * 80 + "\n\n")
            
            for note_id, rows in sorted(duplicates.items()):
                out.write(f"\nNOTE_ID: {note_id}\n")
                out.write(f"  Appears: {len(rows)} times\n")
                out.write(f"  Line numbers: {', '.join(str(r['line_num']) for r in rows)}\n\n")
                
                out.write("  Details:\n")
                for i, row in enumerate(rows, 1):
                    out.write(f"    Instance {i}:\n")
                    out.write(f"      Line: {row['line_num']}\n")
                    out.write(f"      NOTE_DATETIME: {row['note_datetime']}\n")
                    out.write(f"      NOTE_TITLE: {row['note_title']}\n")
                out.write("\n" + "-" * 80 + "\n")
        else:
            out.write("✅ NO DUPLICATES FOUND\n")
    
    print(f"Analysis complete. Results written to: {output_file}")
    print(f"Found {len(duplicates)} duplicate NOTE_IDs")
    
    return output_file

if __name__ == "__main__":
    project_csv = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv"
    
    output_file = find_duplicates(project_csv)
    
    # Display the results
    with open(output_file, 'r') as f:
        print("\n" + f.read())
