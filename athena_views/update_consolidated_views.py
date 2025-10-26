#!/usr/bin/env python3
"""
Update DATETIME_STANDARDIZED_VIEWS.sql with latest view definitions
- Replace v_chemo_medications with version that includes therapeutic_normalized
- Add v_unified_patient_timeline (uses v_chemo_medications as source)
"""

import re
from pathlib import Path

def main():
    views_dir = Path(__file__).parent / 'views'
    consolidated_file = views_dir / 'DATETIME_STANDARDIZED_VIEWS.sql'

    # Read files
    print("Reading view files...")
    with open(consolidated_file, 'r') as f:
        consolidated_content = f.read()

    with open(views_dir / 'V_CHEMO_MEDICATIONS.sql', 'r') as f:
        new_chemo_meds = f.read()

    with open(views_dir / 'V_UNIFIED_PATIENT_TIMELINE.sql', 'r') as f:
        unified_timeline = f.read()

    # Step 1: Replace v_chemo_medications section
    print("\n1. Replacing v_chemo_medications section...")

    # Find start and end of v_chemo_medications section
    chemo_pattern = r'(-- VIEW: v_chemo_medications.*?)(CREATE OR REPLACE VIEW fhir_prd_db\.v_chemo_medications.*?)(;)\s*\n+(CREATE OR REPLACE VIEW fhir_prd_db\.v_procedures_tumor)'

    replacement = r'\g<1>' + new_chemo_meds.rstrip() + '\n;\n\n\g<4>'

    updated_content = re.sub(chemo_pattern, replacement, consolidated_content, flags=re.DOTALL)

    if updated_content == consolidated_content:
        print("  WARNING: v_chemo_medications section not found or not replaced!")
    else:
        print("  ✓ v_chemo_medications section updated")

    # Step 2: Add v_unified_patient_timeline at the end (if not already present)
    print("\n2. Adding v_unified_patient_timeline...")

    if 'v_unified_patient_timeline' in updated_content.lower():
        print("  ℹ v_unified_patient_timeline already exists, replacing...")

        # Remove existing v_unified_patient_timeline section
        timeline_pattern = r'-- ={70,}\s*-- VIEW.*?v_unified_patient_timeline.*?CREATE OR REPLACE VIEW.*?v_unified_patient_timeline.*?;'
        updated_content = re.sub(timeline_pattern, '', updated_content, flags=re.DOTALL | re.IGNORECASE)

    # Add at end
    timeline_header = """
-- ================================================================================
-- VIEW: v_unified_patient_timeline
-- PURPOSE: Normalize ALL temporal events across FHIR domains
-- KEY UPDATES: Uses v_chemo_medications as source for accurate drug categorization
--              and therapeutic_normalized for drug continuity detection
-- ================================================================================

"""

    updated_content = updated_content.rstrip() + '\n\n' + timeline_header + unified_timeline.rstrip() + '\n;\n'
    print("  ✓ v_unified_patient_timeline added")

    # Step 3: Write updated file
    print("\n3. Writing updated consolidated file...")

    # Backup original
    backup_file = consolidated_file.with_suffix('.sql.bak')
    with open(backup_file, 'w') as f:
        f.write(consolidated_content)
    print(f"  ✓ Backup created: {backup_file.name}")

    # Write updated
    with open(consolidated_file, 'w') as f:
        f.write(updated_content)

    # Get file sizes
    orig_size_mb = len(consolidated_content) / (1024 * 1024)
    new_size_mb = len(updated_content) / (1024 * 1024)

    print(f"\n✓ Successfully updated {consolidated_file.name}")
    print(f"  Original size: {orig_size_mb:.2f} MB")
    print(f"  New size: {new_size_mb:.2f} MB")
    print(f"  Change: {new_size_mb - orig_size_mb:+.2f} MB")

if __name__ == '__main__':
    main()
