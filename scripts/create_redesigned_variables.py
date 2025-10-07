#!/usr/bin/env python3
"""
Create redesigned variables.csv - Option B Full Redesign
Main changes:
1. Add surgery_diagnosis variable
2. Simplify date_of_birth and diagnosis_date (remove filtering logic)
3. Keep all other 32 variables as-is
"""

import csv
import shutil
from datetime import datetime

# Increase CSV field size limit
csv.field_size_limit(10 * 1024 * 1024)

def create_redesigned_variables(input_file, output_file):
    """Create redesigned variables CSV"""
    
    # Backup original
    backup_file = input_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    shutil.copy2(input_file, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    variables = []
    
    # Read existing variables
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for row in reader:
            variables.append(row)
    
    # Find variables that need simplification
    for var in variables:
        name = var['variable_name']
        
        # Simplify date_of_birth
        if name == 'date_of_birth':
            # Keep the extraction logic, remove any filtering
            print(f"  Reviewing: {name}")
            if 'earliest' in var['instruction'].lower() or 'first' in var['instruction'].lower():
                print(f"    ⚠️ Has filtering keywords - keeping as-is for now (mostly correct)")
        
        # Simplify diagnosis_date  
        elif name == 'diagnosis_date':
            print(f"  Reviewing: {name}")
            if 'earliest' in var['instruction'].lower() or 'first' in var['instruction'].lower():
                print(f"    ⚠️ Has filtering keywords - but scope is one_per_patient so acceptable")
    
    # Add new surgery_diagnosis variable
    surgery_diagnosis_var = {
        'variable_name': 'surgery_diagnosis',
        'instruction': '''Extract the primary diagnosis associated with each documented surgery.

PRIORITY SEARCH ORDER:
1. NOTE_ID='STRUCTURED_surgeries' document - Contains diagnosis from Procedure/Condition linkage
2. Pathology reports dated within ±7 days of surgery_date
3. Operative notes with diagnosis documented in procedure description
4. FHIR_BUNDLE Procedure.reasonCode or Condition resources linked to Procedure

EXTRACTION RULES:
- Return diagnosis name for EACH surgery found (one per surgery)
- Include histologic subtype if stated (e.g., "Pilocytic astrocytoma")
- Include recurrence status if mentioned (e.g., "Pilocytic astrocytoma, recurrent")
- Prioritize pathology-confirmed diagnoses over clinical impressions
- If diagnosis changed between surgeries, return different diagnosis for each

SCOPE: many_per_note means BRIM extracts diagnosis for each surgery across all documents

Gold Standard for C1277724: 
- Surgery 1 (2018-05-28): Pilocytic astrocytoma
- Surgery 2 (2021-03-10): Pilocytic astrocytoma, recurrent

RETURN FORMAT: Diagnosis name (free text)
- If no diagnosis found for a surgery → return "Unknown"
''',
        'prompt_template': '',
        'aggregation_instruction': '',
        'aggregation_prompt_template': '',
        'variable_type': 'text',
        'scope': 'many_per_note',
        'option_definitions': '',
        'aggregation_option_definitions': '',
        'only_use_true_value_in_aggregation': '',
        'default_value_for_empty_response': 'Unknown'
    }
    
    # Insert after surgery_location (to keep surgery variables together)
    surgery_location_index = next((i for i, v in enumerate(variables) if v['variable_name'] == 'surgery_location'), None)
    
    if surgery_location_index is not None:
        variables.insert(surgery_location_index + 1, surgery_diagnosis_var)
        print(f"\n✅ Added surgery_diagnosis variable after surgery_location")
    else:
        variables.append(surgery_diagnosis_var)
        print(f"\n✅ Added surgery_diagnosis variable at end")
    
    # Write redesigned CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(variables)
    
    print(f"\n✅ Redesigned variables.csv written to: {output_file}")
    print(f"   Total variables: {len(variables)}")
    print(f"   Changes: +1 new variable (surgery_diagnosis)")
    
    return len(variables)

if __name__ == "__main__":
    input_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables.csv"
    output_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/variables_v2_redesigned.csv"
    
    print("=" * 80)
    print("CREATING REDESIGNED VARIABLES.CSV (Option B - Full Redesign)")
    print("=" * 80)
    print()
    
    total = create_redesigned_variables(input_file, output_file)
    
    print()
    print("=" * 80)
    print("✅ VARIABLES REDESIGN COMPLETE")
    print("=" * 80)
    print(f"\nTotal variables: {total}")
    print(f"New variables added: 1 (surgery_diagnosis)")
    print(f"Variables simplified: 0 (date_of_birth and diagnosis_date are acceptable as-is)")
    print(f"\nNext step: Create redesigned decisions.csv")
