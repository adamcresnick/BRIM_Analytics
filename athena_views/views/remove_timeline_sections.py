#!/usr/bin/env python3
"""
Remove specific sections from v_unified_patient_timeline.
"""

import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'

# Views to remove
VIEWS_TO_REMOVE = [
    'v_radiation_summary',
    'v_ophthalmology_assessments',
    'v_audiology_assessments',
    'v_autologous_stem_cell_transplant',
    'v_autologous_stem_cell_collection',
    'v_imaging_corticosteroid_use'
]

def remove_timeline_sections():
    """Remove specific UNION ALL sections from the timeline view."""

    with open(MASTER_FILE, 'r') as f:
        content = f.read()

    # Find the timeline view
    view_start = content.find('-- VIEW: v_unified_patient_timeline')
    view_end = content.find('\n-- ================================================================================', view_start + 500)

    if view_end == -1:
        # Timeline is the last view
        view_end = len(content)

    before_view = content[:view_start]
    view_content = content[view_start:view_end]
    after_view = content[view_end:]

    print("=" * 80)
    print("REMOVING SECTIONS FROM v_unified_patient_timeline")
    print("=" * 80)

    sections_removed = 0

    for view_to_remove in VIEWS_TO_REMOVE:
        # Find the section that uses this view
        # Look for the comment header + SELECT + FROM pattern

        # Pattern: -- ==== ... FROM fhir_prd_db.{view_name} ... UNION ALL
        # We want to remove from the previous UNION ALL (or SELECT if first) to the next UNION ALL

        from_pattern = f'FROM fhir_prd_db.{view_to_remove}'

        if from_pattern in view_content:
            print(f"\n🔍 Found section using {view_to_remove}")

            # Find the FROM statement
            from_pos = view_content.find(from_pattern)

            # Find the start of this section (previous UNION ALL or start of CREATE)
            # Look backwards for either "UNION ALL" or "CREATE OR REPLACE"
            section_start = view_content.rfind('UNION ALL', 0, from_pos)

            if section_start == -1:
                # This might be the first section after CREATE
                section_start = view_content.find('SELECT', 0, from_pos)
                # Actually, find the CREATE statement
                create_pos = view_content.find('CREATE OR REPLACE VIEW')
                if create_pos != -1 and create_pos < from_pos:
                    # This is the first SELECT after CREATE, find it
                    section_start = view_content.find('\nSELECT', create_pos, from_pos)

            # Find the end of this section (next UNION ALL or ORDER BY at end)
            section_end = view_content.find('\nUNION ALL', from_pos)

            if section_end == -1:
                # This is the last section, find ORDER BY
                section_end = view_content.find('\nORDER BY', from_pos)
                if section_end == -1:
                    section_end = len(view_content)

            # Extract the section to remove
            section_to_remove = view_content[section_start:section_end]

            # Show preview
            lines = section_to_remove.split('\n')
            print(f"   Section starts at position {section_start}")
            print(f"   Section ends at position {section_end}")
            print(f"   Section is {len(lines)} lines")
            print(f"   First line: {lines[0][:80] if lines else ''}...")
            print(f"   Last line: {lines[-1][:80] if len(lines) > 1 else ''}...")

            # Remove the section
            view_content = view_content[:section_start] + view_content[section_end:]
            sections_removed += 1
            print(f"   ✅ Removed section for {view_to_remove}")
        else:
            print(f"   ⚠️  {view_to_remove} not found in timeline")

    # Reassemble the file
    new_content = before_view + view_content + after_view

    # Write back
    with open(MASTER_FILE, 'w') as f:
        f.write(new_content)

    print("\n" + "=" * 80)
    print(f"✅ REMOVED {sections_removed} SECTIONS")
    print("=" * 80)
    print(f"\nUpdated file: {MASTER_FILE}")

    # Show which views remain
    print("\n📋 Remaining views in timeline:")
    remaining_froms = re.findall(r'FROM fhir_prd_db\.(v_\w+)', view_content)
    for view in sorted(set(remaining_froms)):
        if view != 'v_unified_patient_timeline':  # Exclude self-references
            print(f"   • {view}")

if __name__ == '__main__':
    remove_timeline_sections()
