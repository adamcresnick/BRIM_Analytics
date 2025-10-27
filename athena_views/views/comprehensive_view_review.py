#!/usr/bin/env python3
"""
Comprehensive review of all Athena views to identify optimization needs.
"""

import re
from pathlib import Path

MASTER_FILE = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql')

def extract_view_info():
    """Extract all view definitions and their dependencies."""

    with open(MASTER_FILE, 'r') as f:
        content = f.read()

    # Find all CREATE OR REPLACE VIEW statements
    view_pattern = r'CREATE OR REPLACE VIEW fhir_prd_db\.(v_\w+)'
    views = re.findall(view_pattern, content)

    view_info = []

    for view_name in views:
        # Find the view definition
        view_start = content.find(f'CREATE OR REPLACE VIEW fhir_prd_db.{view_name}')
        if view_start == -1:
            continue

        # Find next CREATE statement or end of file
        next_view = content.find('CREATE OR REPLACE VIEW', view_start + 10)
        if next_view == -1:
            view_def = content[view_start:]
        else:
            view_def = content[view_start:next_view]

        # Analyze dependencies
        dependencies = {
            'uses_v_medications': 'FROM fhir_prd_db.v_medications' in view_def or 'JOIN fhir_prd_db.v_medications' in view_def,
            'uses_v_chemo_medications': 'FROM fhir_prd_db.v_chemo_medications' in view_def or 'JOIN fhir_prd_db.v_chemo_medications' in view_def,
            'uses_medication_request': 'FROM fhir_prd_db.medication_request' in view_def or 'JOIN fhir_prd_db.medication_request' in view_def,
            'uses_v_chemotherapy_drugs': 'v_chemotherapy_drugs' in view_def,
            'uses_hardcoded_rxnorm': bool(re.search(r"IN\s*\(\s*'\d{4,6}'", view_def)),
            'has_date_casting': 'CAST(' in view_def and 'DATE' in view_def,
            'has_timestamp_parsing': 'FROM_ISO8601_TIMESTAMP' in view_def or 'TO_ISO8601' in view_def,
            'line_count': len(view_def.split('\n')),
        }

        # Check for specific optimization issues
        issues = []
        if dependencies['uses_hardcoded_rxnorm']:
            issues.append('HARDCODED_RXNORM_CODES')
        if dependencies['uses_v_medications'] and not dependencies['uses_v_chemo_medications']:
            if 'chemo' in view_name.lower() or 'medication' in view_name.lower():
                issues.append('SHOULD_USE_V_CHEMO_MEDICATIONS')
        if 'medication' in view_def.lower() and not dependencies['uses_v_chemo_medications'] and not dependencies['uses_v_medications']:
            if 'medication_request' in view_def.lower():
                issues.append('DIRECT_MEDICATION_REQUEST_ACCESS')

        view_info.append({
            'name': view_name,
            'dependencies': dependencies,
            'issues': issues,
            'view_def_snippet': view_def[:500]
        })

    return view_info

def generate_report(view_info):
    """Generate comprehensive review report."""

    print("=" * 100)
    print("COMPREHENSIVE VIEW REVIEW - OPTIMIZATION ANALYSIS")
    print("=" * 100)
    print(f"\nTotal views analyzed: {len(view_info)}\n")

    # Category 1: Views using v_chemo_medications (GOOD)
    chemo_med_views = [v for v in view_info if v['dependencies']['uses_v_chemo_medications']]
    print("=" * 100)
    print(f"✅ VIEWS USING v_chemo_medications ({len(chemo_med_views)})")
    print("=" * 100)
    for v in chemo_med_views:
        print(f"  - {v['name']}")

    # Category 2: Views using v_medications
    med_views = [v for v in view_info if v['dependencies']['uses_v_medications'] and not v['dependencies']['uses_v_chemo_medications']]
    print(f"\n" + "=" * 100)
    print(f"📊 VIEWS USING v_medications ({len(med_views)})")
    print("=" * 100)
    for v in med_views:
        print(f"  - {v['name']}")
        if v['issues']:
            print(f"    ⚠ Issues: {', '.join(v['issues'])}")

    # Category 3: Views with hardcoded RxNorm codes
    hardcoded_views = [v for v in view_info if v['dependencies']['uses_hardcoded_rxnorm']]
    print(f"\n" + "=" * 100)
    print(f"⚠️  VIEWS WITH HARDCODED RXNORM CODES ({len(hardcoded_views)})")
    print("=" * 100)
    for v in hardcoded_views:
        print(f"  - {v['name']}")
        print(f"    Lines: {v['dependencies']['line_count']}")
        if v['issues']:
            print(f"    Issues: {', '.join(v['issues'])}")

    # Category 4: Views accessing medication_request directly
    direct_access_views = [v for v in view_info if v['dependencies']['uses_medication_request']]
    print(f"\n" + "=" * 100)
    print(f"🔍 VIEWS ACCESSING medication_request DIRECTLY ({len(direct_access_views)})")
    print("=" * 100)
    for v in direct_access_views:
        print(f"  - {v['name']}")
        if 'DIRECT_MEDICATION_REQUEST_ACCESS' in v['issues']:
            print(f"    ⚠ May need optimization to use v_chemo_medications")

    # Category 5: Views using v_chemotherapy_drugs reference
    chemo_drugs_views = [v for v in view_info if v['dependencies']['uses_v_chemotherapy_drugs']]
    print(f"\n" + "=" * 100)
    print(f"📚 VIEWS USING v_chemotherapy_drugs REFERENCE ({len(chemo_drugs_views)})")
    print("=" * 100)
    for v in chemo_drugs_views:
        print(f"  - {v['name']}")

    # Summary of issues
    print(f"\n" + "=" * 100)
    print("SUMMARY OF OPTIMIZATION OPPORTUNITIES")
    print("=" * 100)

    total_issues = sum(len(v['issues']) for v in view_info)
    print(f"\nTotal issues found: {total_issues}")

    # Count by issue type
    issue_counts = {}
    for v in view_info:
        for issue in v['issues']:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    if issue_counts:
        print("\nIssue breakdown:")
        for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            print(f"  - {issue}: {count} views")

    # Recommendations
    print(f"\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)

    recommendations = []

    if hardcoded_views:
        recommendations.append({
            'priority': 'HIGH',
            'category': 'Hardcoded RxNorm codes',
            'views': [v['name'] for v in hardcoded_views],
            'action': 'Replace hardcoded RxNorm codes with v_chemotherapy_drugs reference',
            'benefit': 'Ensures consistency with comprehensive drug reference (2,968 drugs)'
        })

    should_use_chemo = [v for v in view_info if 'SHOULD_USE_V_CHEMO_MEDICATIONS' in v['issues']]
    if should_use_chemo:
        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'Should use v_chemo_medications',
            'views': [v['name'] for v in should_use_chemo],
            'action': 'Evaluate if these views should use v_chemo_medications instead of v_medications',
            'benefit': 'Better filtering and therapeutic normalization for chemo-specific analyses'
        })

    direct_med_request = [v for v in view_info if 'DIRECT_MEDICATION_REQUEST_ACCESS' in v['issues']]
    if direct_med_request:
        recommendations.append({
            'priority': 'LOW',
            'category': 'Direct medication_request access',
            'views': [v['name'] for v in direct_med_request],
            'action': 'Consider using v_medications or v_chemo_medications for standardization',
            'benefit': 'Consistent date handling and RxNorm code matching'
        })

    if not recommendations:
        print("\n✅ No optimization issues found! All views are using best practices.")
    else:
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. [{rec['priority']} PRIORITY] {rec['category']}")
            print(f"   Views affected: {len(rec['views'])}")
            for view in rec['views']:
                print(f"     - {view}")
            print(f"   Action: {rec['action']}")
            print(f"   Benefit: {rec['benefit']}")

    return view_info, recommendations

def main():
    view_info = extract_view_info()
    view_info, recommendations = generate_report(view_info)

    # Save detailed report
    output_file = Path(__file__).parent / 'VIEW_OPTIMIZATION_REPORT.md'
    with open(output_file, 'w') as f:
        f.write("# Comprehensive View Optimization Report\n\n")
        f.write(f"**Date**: 2025-10-27\n")
        f.write(f"**Total Views**: {len(view_info)}\n\n")

        f.write("## Executive Summary\n\n")
        total_issues = sum(len(v['issues']) for v in view_info)
        f.write(f"- Total optimization issues found: **{total_issues}**\n")
        f.write(f"- Views using v_chemo_medications: **{len([v for v in view_info if v['dependencies']['uses_v_chemo_medications']])}**\n")
        f.write(f"- Views with hardcoded RxNorm codes: **{len([v for v in view_info if v['dependencies']['uses_hardcoded_rxnorm']])}**\n\n")

        f.write("## Recommendations\n\n")
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                f.write(f"### {i}. [{rec['priority']}] {rec['category']}\n\n")
                f.write(f"**Views affected**: {len(rec['views'])}\n\n")
                for view in rec['views']:
                    f.write(f"- {view}\n")
                f.write(f"\n**Action**: {rec['action']}\n\n")
                f.write(f"**Benefit**: {rec['benefit']}\n\n")
        else:
            f.write("✅ No optimization issues found!\n\n")

        f.write("## Detailed View Analysis\n\n")
        for v in sorted(view_info, key=lambda x: x['name']):
            f.write(f"### {v['name']}\n\n")
            f.write(f"**Line count**: {v['dependencies']['line_count']}\n\n")
            f.write("**Dependencies**:\n")
            f.write(f"- Uses v_chemo_medications: {v['dependencies']['uses_v_chemo_medications']}\n")
            f.write(f"- Uses v_medications: {v['dependencies']['uses_v_medications']}\n")
            f.write(f"- Uses medication_request directly: {v['dependencies']['uses_medication_request']}\n")
            f.write(f"- Has hardcoded RxNorm codes: {v['dependencies']['uses_hardcoded_rxnorm']}\n")
            if v['issues']:
                f.write(f"\n**Issues**: {', '.join(v['issues'])}\n")
            f.write("\n")

    print(f"\n✅ Detailed report saved to: {output_file}")

if __name__ == '__main__':
    main()
