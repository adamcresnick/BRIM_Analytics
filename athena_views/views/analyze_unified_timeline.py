#!/usr/bin/env python3
"""
Comprehensive analysis of v_unified_patient_timeline structure.
"""

import re

MASTER_FILE = 'DATETIME_STANDARDIZED_VIEWS.sql'

def analyze_timeline_view():
    """Extract and analyze all sections of the unified timeline view."""

    with open(MASTER_FILE, 'r') as f:
        content = f.read()

    # Find the timeline view
    view_start = content.find('-- VIEW: v_unified_patient_timeline')
    view_end = content.find('\n-- ================================================================================', view_start + 100)
    if view_end == -1:
        view_end = len(content)

    view_content = content[view_start:view_end]

    print("=" * 80)
    print("UNIFIED PATIENT TIMELINE COMPREHENSIVE ANALYSIS")
    print("=" * 80)

    # 1. Extract documented coverage
    coverage_match = re.search(r'-- Coverage:\n(.+?)\n--', view_content, re.DOTALL)
    if coverage_match:
        print("\n📋 DOCUMENTED DATA SOURCES:")
        print("-" * 80)
        coverage_lines = coverage_match.group(1).strip().split('\n')
        for line in coverage_lines:
            line = line.replace('--', '').strip()
            if line:
                print(f"   {line}")

    # 2. Find all UNION ALL sections
    print("\n\n📊 ACTUAL UNION ALL SECTIONS:")
    print("-" * 80)

    # Split by UNION ALL and analyze each section
    sections = view_content.split('UNION ALL')

    section_info = []
    for i, section in enumerate(sections, 1):
        # Find the comment describing the section
        comment_match = re.search(r'-- =+\n-- (\d+)\. (.+?)\n-- Source: (.+?)\n-- Provenance: (.+?)\n-- =+', section)

        if comment_match:
            section_num = comment_match.group(1)
            title = comment_match.group(2)
            source = comment_match.group(3)
            provenance = comment_match.group(4)

            # Find FROM clause
            from_match = re.search(r'FROM fhir_prd_db\.(\w+)', section)
            actual_view = from_match.group(1) if from_match else 'UNKNOWN'

            # Find event_type value
            event_type_match = re.search(r"'([^']+)' as event_type", section)
            event_type = event_type_match.group(1) if event_type_match else 'UNKNOWN'

            section_info.append({
                'num': section_num,
                'title': title,
                'source': source,
                'provenance': provenance,
                'actual_view': actual_view,
                'event_type': event_type
            })

    for info in section_info:
        print(f"\n{info['num']}. {info['title']}")
        print(f"   Event Type:  {info['event_type']}")
        print(f"   Source View: {info['actual_view']}")
        print(f"   Source Doc:  {info['source']}")
        print(f"   Provenance:  {info['provenance']}")

    # 3. Check for any views mentioned in coverage but not in UNION sections
    print("\n\n🔍 DATA SOURCE COVERAGE VERIFICATION:")
    print("-" * 80)

    documented_views = [
        'v_diagnoses', 'v_problem_list_diagnoses', 'v_hydrocephalus_diagnosis',
        'v_procedures', 'v_procedures_tumor', 'v_hydrocephalus_procedures',
        'v_imaging', 'v_medications', 'v_chemo_medications', 'v_concomitant_medications',
        'v_imaging_corticosteroid_use', 'v_visits_unified', 'v_measurements',
        'v_molecular_tests', 'v_radiation_treatment_courses',
        'v_radiation_treatment_appointments', 'v_ophthalmology_assessments',
        'v_audiology_assessments', 'v_autologous_stem_cell_transplant',
        'v_autologous_stem_cell_collection'
    ]

    actual_views = [info['actual_view'] for info in section_info]

    print("\n✅ Views INCLUDED in timeline:")
    for view in sorted(set(actual_views)):
        print(f"   • {view}")

    missing_views = [v for v in documented_views if v not in actual_views]
    if missing_views:
        print("\n⚠️  Views DOCUMENTED but NOT INCLUDED:")
        for view in sorted(missing_views):
            print(f"   • {view}")

    # 4. Analyze event categorization
    print("\n\n🏷️  EVENT TYPES AND CATEGORIES:")
    print("-" * 80)

    event_types = {}
    for info in section_info:
        event_type = info['event_type']
        if event_type not in event_types:
            event_types[event_type] = []
        event_types[event_type].append(info['title'])

    for event_type in sorted(event_types.keys()):
        print(f"\n{event_type}:")
        for title in event_types[event_type]:
            print(f"   • {title}")

    # 5. Check for references to updated views
    print("\n\n🔄 DEPENDENCY ON RECENTLY FIXED VIEWS:")
    print("-" * 80)

    fixed_views = [
        'v_concomitant_medications',
        'v_imaging_corticosteroid_use',
        'v_autologous_stem_cell_collection'
    ]

    for view in fixed_views:
        if view in actual_views:
            print(f"   ✅ {view} - INCLUDED (recently fixed)")
        else:
            print(f"   ℹ️  {view} - NOT INCLUDED")

    # 6. Summary statistics
    print("\n\n📈 SUMMARY STATISTICS:")
    print("-" * 80)
    print(f"   Total UNION ALL sections:     {len(section_info)}")
    print(f"   Unique source views:          {len(set(actual_views))}")
    print(f"   Unique event types:           {len(event_types)}")
    print(f"   Documented data sources:      {len(documented_views)}")
    print(f"   Coverage percentage:          {len(set(actual_views))/len(documented_views)*100:.1f}%")

if __name__ == '__main__':
    analyze_timeline_view()
