#!/usr/bin/env python3
"""
Analyze current variables.csv to understand what needs redesigning
"""

import csv
import json

# Increase CSV field size limit
csv.field_size_limit(10 * 1024 * 1024)

def analyze_variables(csv_file):
    """Analyze variables to identify what needs redesigning"""
    
    variables = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        variables = list(reader)
    
    # Analysis categories
    pure_extractors = []
    need_simplification = []
    surgery_related = []
    missing_variables = [
        {
            'name': 'surgery_diagnosis',
            'reason': 'Need diagnosis associated with each surgery (not just general primary_diagnosis)',
            'scope': 'many_per_note',
            'type': 'text'
        }
    ]
    
    for var in variables:
        name = var['variable_name']
        scope = var['scope']
        instruction = var['instruction']
        
        # Check if surgery-related
        if 'surgery' in name.lower() or 'surgery' in instruction.lower()[:500]:
            surgery_related.append({
                'name': name,
                'scope': scope,
                'has_filtering': any(phrase in instruction.lower() for phrase in [
                    'earliest', 'first surgery', 'second surgery', 'filter to rows where',
                    'row 1 only', 'surgery 1', 'surgery 2'
                ])
            })
        
        # Check if pure extractor or needs simplification
        if any(phrase in instruction.lower() for phrase in [
            'earliest', 'first surgery', 'second surgery', 'filter to rows where',
            'row 1 only', 'surgery 1', 'surgery 2', 'latest', 'most recent only'
        ]):
            need_simplification.append({
                'name': name,
                'scope': scope,
                'reason': 'Contains filtering/ordering logic that should move to dependent variables'
            })
        else:
            pure_extractors.append({
                'name': name,
                'scope': scope
            })
    
    # Print analysis
    print("=" * 80)
    print("VARIABLES.CSV ANALYSIS FOR REDESIGN")
    print("=" * 80)
    print()
    
    print(f"Total variables: {len(variables)}")
    print()
    
    print(f"✅ Pure extractors (already correct): {len(pure_extractors)}")
    print(f"⚠️  Need simplification (move filtering to dependent vars): {len(need_simplification)}")
    print(f"🔧 Surgery-related variables: {len(surgery_related)}")
    print(f"❌ Missing variables: {len(missing_variables)}")
    print()
    
    print("=" * 80)
    print("SURGERY-RELATED VARIABLES (most important for redesign)")
    print("=" * 80)
    for var in surgery_related:
        status = "❌ HAS FILTERING" if var['has_filtering'] else "✅ Pure extractor"
        print(f"{status}: {var['name']}")
        print(f"  Scope: {var['scope']}")
        print()
    
    print("=" * 80)
    print("VARIABLES NEEDING SIMPLIFICATION")
    print("=" * 80)
    for var in need_simplification[:15]:  # Show first 15
        print(f"⚠️  {var['name']}")
        print(f"  Scope: {var['scope']}")
        print(f"  Reason: {var['reason']}")
        print()
    
    if len(need_simplification) > 15:
        print(f"... and {len(need_simplification) - 15} more")
        print()
    
    print("=" * 80)
    print("MISSING VARIABLES TO ADD")
    print("=" * 80)
    for var in missing_variables:
        print(f"❌ {var['name']}")
        print(f"  Reason: {var['reason']}")
        print(f"  Scope: {var['scope']}")
        print(f"  Type: {var['type']}")
        print()
    
    print("=" * 80)
    print("SCOPE DISTRIBUTION")
    print("=" * 80)
    scopes = {}
    for var in variables:
        scope = var['scope']
        scopes[scope] = scopes.get(scope, 0) + 1
    
    for scope, count in sorted(scopes.items(), key=lambda x: x[1], reverse=True):
        print(f"  {scope}: {count} variables")
    
    return {
        'total': len(variables),
        'pure_extractors': pure_extractors,
        'need_simplification': need_simplification,
        'surgery_related': surgery_related,
        'missing': missing_variables
    }

if __name__ == "__main__":
    csv_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables.csv"
    
    analysis = analyze_variables(csv_file)
    
    # Save analysis to JSON
    with open('/tmp/variables_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print()
    print("=" * 80)
    print(f"✅ Analysis complete. Details saved to /tmp/variables_analysis.json")
    print("=" * 80)
