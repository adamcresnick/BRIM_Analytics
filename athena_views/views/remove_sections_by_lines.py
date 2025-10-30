#!/usr/bin/env python3
"""
Remove specific sections from v_unified_patient_timeline by line numbers.
"""

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'

# Sections to remove (FROM line numbers, we'll find boundaries programmatically)
SECTIONS_TO_REMOVE = {
    'v_radiation_summary': 5610,
    'v_ophthalmology_assessments': 5822,
    'v_audiology_assessments': 5888,
    'v_autologous_stem_cell_transplant': 5956,
    'v_autologous_stem_cell_collection': 6019,
    'v_imaging_corticosteroid_use': 6084
}

def find_section_boundaries(lines, from_line_num):
    """Find the start and end of a UNION ALL section containing the FROM statement."""
    # from_line_num is 1-indexed, convert to 0-indexed
    from_idx = from_line_num - 1

    # Search backwards for the comment header (-- ====)
    section_start = from_idx
    for i in range(from_idx, max(0, from_idx - 100), -1):
        if '-- ============================================================================' in lines[i]:
            section_start = i
            break

    # Search forward for next UNION ALL or ORDER BY
    section_end = len(lines)
    for i in range(from_idx, min(len(lines), from_idx + 200)):
        if i > from_idx and 'UNION ALL' in lines[i]:
            # Include the UNION ALL line in the removal
            section_end = i + 1
            break
        if 'ORDER BY' in lines[i]:
            section_end = i
            break

    return section_start, section_end

def remove_sections():
    """Remove sections from the timeline view."""

    with open(MASTER_FILE, 'r') as f:
        lines = f.readlines()

    print("=" * 80)
    print("REMOVING SECTIONS FROM v_unified_patient_timeline")
    print("=" * 80)

    # Sort sections by line number in descending order (remove from bottom to top)
    sorted_sections = sorted(SECTIONS_TO_REMOVE.items(), key=lambda x: x[1], reverse=True)

    total_lines_removed = 0

    for view_name, from_line in sorted_sections:
        start, end = find_section_boundaries(lines, from_line)

        num_lines = end - start
        print(f"\n📍 {view_name}:")
        print(f"   FROM line: {from_line}")
        print(f"   Section start: {start + 1}")
        print(f"   Section end: {end}")
        print(f"   Lines to remove: {num_lines}")
        print(f"   First line: {lines[start][:70]}..." if start < len(lines) else "")

        # Remove the section
        del lines[start:end]
        total_lines_removed += num_lines
        print(f"   ✅ Removed {num_lines} lines")

    # Write back
    with open(MASTER_FILE, 'w') as f:
        f.writelines(lines)

    print("\n" + "=" * 80)
    print(f"✅ REMOVED {len(sorted_sections)} SECTIONS ({total_lines_removed} lines)")
    print("=" * 80)
    print(f"\nUpdated file: {MASTER_FILE}")

    # Count remaining UNION ALL statements
    union_count = sum(1 for line in lines if 'UNION ALL' in line and '5107' < str(lines.index(line)) < '6200')
    print(f"\nRemaining UNION ALL statements in timeline: {union_count}")

if __name__ == '__main__':
    remove_sections()
