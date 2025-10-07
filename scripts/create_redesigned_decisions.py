#!/usr/bin/env python3
"""
Create redesigned decisions.csv (dependent variables) - Option B Full Redesign

BRIM Format Based on Documentation:
- name: Dependent variable name
- variable_type: text | boolean | integer | float  
- instructions: How to compute the dependent variable
- input_variables: Semicolon-separated list of variables to reference
- default_empty_value: What to return if no evidence found
- option_definitions: JSON object for categorical variables (optional)

Key Changes from Old Format:
- decision_name → name
- decision_type (filter/aggregation) → variable_type (text/boolean/integer/float)
- prompt → instructions
- REMOVE: output_variable, aggregation_prompt
- ADD: default_empty_value, variable_type must be data type not workflow type
"""

import csv
import json
from datetime import datetime

def create_redesigned_decisions(output_file):
    """Create redesigned decisions CSV in BRIM format"""
    
    # Define the BRIM format columns
    fieldnames = [
        'name',
        'variable_type',
        'instructions',
        'input_variables',
        'default_empty_value',
        'option_definitions'
    ]
    
    # Define all dependent variables
    dependent_variables = [
        # Surgery-Specific Dependent Variables (Filters)
        {
            'name': 'diagnosis_surgery1',
            'variable_type': 'text',
            'instructions': '''Return the diagnosis associated with the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST value in the surgery_date variable (first surgery date)
2. Look for surgery_diagnosis values associated with that date
3. If surgery_diagnosis not available, use primary_diagnosis from documents near that date
4. Prioritize pathology-confirmed diagnoses

TEMPORAL CONTEXT:
- surgery_date provides all surgery dates
- surgery_diagnosis provides diagnosis for each surgery
- Document_type helps prioritize source reliability (PATHOLOGY > OPERATIVE > other)

Gold Standard for C1277724 Surgery 1 (2018-05-28): Pilocytic astrocytoma''',
            'input_variables': 'surgery_date;surgery_diagnosis;primary_diagnosis;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': ''
        },
        {
            'name': 'extent_surgery1',
            'variable_type': 'text',
            'instructions': '''Return the extent of resection for the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST value in surgery_date (first surgery date)
2. Find surgery_extent values associated with that date
3. Prioritize document_type='OPERATIVE' (surgeon's assessment is most authoritative)

VALID RETURN VALUES:
Must be one of: Gross Total Resection, Near Total Resection, Subtotal Resection, Partial Resection, Biopsy Only, Unknown

Gold Standard for C1277724 Surgery 1 (2018-05-28): Partial Resection''',
            'input_variables': 'surgery_date;surgery_extent;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': json.dumps({
                "Gross Total Resection": "Gross Total Resection",
                "Near Total Resection": "Near Total Resection",
                "Subtotal Resection": "Subtotal Resection",
                "Partial Resection": "Partial Resection",
                "Biopsy Only": "Biopsy Only",
                "Unknown": "Unknown"
            })
        },
        {
            'name': 'location_surgery1',
            'variable_type': 'text',
            'instructions': '''Return the anatomical location for the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST value in surgery_date (first surgery date)
2. Find surgery_location values associated with that date
3. Use most specific location mentioned

VALID RETURN VALUES:
Must match one of the defined anatomical locations

Gold Standard for C1277724 Surgery 1 (2018-05-28): Cerebellum/Posterior Fossa''',
            'input_variables': 'surgery_date;surgery_location;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': json.dumps({
                "Frontal Lobe": "Frontal Lobe",
                "Temporal Lobe": "Temporal Lobe",
                "Parietal Lobe": "Parietal Lobe",
                "Occipital Lobe": "Occipital Lobe",
                "Thalamus": "Thalamus",
                "Ventricles": "Ventricles",
                "Suprasellar/Hypothalamic/Pituitary": "Suprasellar/Hypothalamic/Pituitary",
                "Cerebellum/Posterior Fossa": "Cerebellum/Posterior Fossa",
                "Brain Stem": "Brain Stem",
                "Spinal Cord": "Spinal Cord",
                "Unknown": "Unknown"
            })
        },
        {
            'name': 'diagnosis_surgery2',
            'variable_type': 'text',
            'instructions': '''Return the diagnosis associated with the SECOND surgery (if it exists).

FILTERING LOGIC:
1. Check if surgery_number >= 2 (patient had at least 2 surgeries)
2. If yes: Identify the SECOND EARLIEST value in surgery_date
3. Find surgery_diagnosis associated with that date
4. If not available, use primary_diagnosis from documents near that date
5. If surgery_number < 2: Return empty string

EXPECTED BEHAVIOR:
- If only 1 surgery: Return empty/Unknown
- If 2+ surgeries: Return diagnosis for second surgery

Gold Standard for C1277724 Surgery 2 (2021-03-10): Pilocytic astrocytoma, recurrent''',
            'input_variables': 'surgery_number;surgery_date;surgery_diagnosis;primary_diagnosis;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': ''
        },
        {
            'name': 'extent_surgery2',
            'variable_type': 'text',
            'instructions': '''Return the extent of resection for the SECOND surgery (if it exists).

FILTERING LOGIC:
1. Check if surgery_number >= 2
2. If yes: Identify SECOND EARLIEST surgery_date
3. Find surgery_extent associated with that date
4. If surgery_number < 2: Return empty string

Gold Standard for C1277724 Surgery 2 (2021-03-10): Partial Resection''',
            'input_variables': 'surgery_number;surgery_date;surgery_extent;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': json.dumps({
                "Gross Total Resection": "Gross Total Resection",
                "Near Total Resection": "Near Total Resection",
                "Subtotal Resection": "Subtotal Resection",
                "Partial Resection": "Partial Resection",
                "Biopsy Only": "Biopsy Only",
                "Unknown": "Unknown"
            })
        },
        {
            'name': 'location_surgery2',
            'variable_type': 'text',
            'instructions': '''Return the anatomical location for the SECOND surgery (if it exists).

FILTERING LOGIC:
1. Check if surgery_number >= 2
2. If yes: Identify SECOND EARLIEST surgery_date
3. Find surgery_location associated with that date
4. If surgery_number < 2: Return empty string

Gold Standard for C1277724 Surgery 2 (2021-03-10): Cerebellum/Posterior Fossa''',
            'input_variables': 'surgery_number;surgery_date;surgery_location;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': json.dumps({
                "Frontal Lobe": "Frontal Lobe",
                "Temporal Lobe": "Temporal Lobe",
                "Parietal Lobe": "Parietal Lobe",
                "Occipital Lobe": "Occipital Lobe",
                "Thalamus": "Thalamus",
                "Ventricles": "Ventricles",
                "Suprasellar/Hypothalamic/Pituitary": "Suprasellar/Hypothalamic/Pituitary",
                "Cerebellum/Posterior Fossa": "Cerebellum/Posterior Fossa",
                "Brain Stem": "Brain Stem",
                "Spinal Cord": "Spinal Cord",
                "Unknown": "Unknown"
            })
        },
        
        # Aggregation Dependent Variables
        {
            'name': 'total_surgeries',
            'variable_type': 'integer',
            'instructions': '''Count the total number of distinct surgeries for this patient.

AGGREGATION LOGIC:
Count the number of unique values in surgery_date variable.
This should match the surgery_number variable.

EXPECTED OUTPUT: Integer count
Gold Standard for C1277724: 2''',
            'input_variables': 'surgery_date',
            'default_empty_value': '0',
            'option_definitions': ''
        },
        {
            'name': 'all_chemotherapy_agents',
            'variable_type': 'text',
            'instructions': '''Aggregate all chemotherapy agents into a semicolon-separated list.

AGGREGATION LOGIC:
1. Collect ALL chemotherapy_agents values extracted across all documents
2. Remove duplicate agent names
3. Return as semicolon-separated list

EXPECTED OUTPUT: "agent1;agent2;agent3"
Gold Standard for C1277724: vinblastine;bevacizumab;selumetinib''',
            'input_variables': 'chemotherapy_agents',
            'default_empty_value': 'None',
            'option_definitions': ''
        },
        {
            'name': 'all_symptoms',
            'variable_type': 'text',
            'instructions': '''Aggregate all documented symptoms into a semicolon-separated list.

AGGREGATION LOGIC:
1. Collect ALL symptoms_present values across all documents
2. Remove duplicates
3. Return as semicolon-separated list

EXPECTED OUTPUT: "symptom1;symptom2;symptom3"
Gold Standard for C1277724: Emesis;Headaches;Hydrocephalus;Visual deficit;Posterior fossa syndrome''',
            'input_variables': 'symptoms_present',
            'default_empty_value': 'None documented',
            'option_definitions': ''
        },
        {
            'name': 'earliest_symptom_date',
            'variable_type': 'text',
            'instructions': '''Identify the earliest date when symptoms were first documented.

AGGREGATION LOGIC:
1. Find the EARLIEST document where symptoms_present != "None documented"
2. Prioritize document_type='H&P' or 'CONSULTATION' (initial presentation)
3. Return the document date

EXPECTED OUTPUT: YYYY-MM-DD format
Gold Standard for C1277724: Around initial diagnosis date (2018-06-04)''',
            'input_variables': 'symptoms_present;document_type',
            'default_empty_value': 'Unknown',
            'option_definitions': ''
        },
        {
            'name': 'molecular_tests_summary',
            'variable_type': 'text',
            'instructions': '''Create comprehensive molecular profile summary.

AGGREGATION LOGIC:
Combine all molecular test results into single text summary.
Format: "BRAF: [status]; IDH: [status]; MGMT: [status]; Tests: [list]"

EXAMPLE OUTPUT:
"BRAF: KIAA1549-BRAF fusion; IDH: wild-type; MGMT: Not tested; Tests: WGS, Fusion Panel"

Gold Standard for C1277724: BRAF fusion present (KIAA1549-BRAF)''',
            'input_variables': 'molecular_testing_performed;braf_status;idh_mutation;mgmt_methylation',
            'default_empty_value': 'No molecular testing documented',
            'option_definitions': ''
        },
        {
            'name': 'imaging_progression_timeline',
            'variable_type': 'text',
            'instructions': '''Create timeline of imaging findings showing disease course.

AGGREGATION LOGIC:
1. Extract ALL imaging_findings with their document dates
2. Prioritize document_type='IMAGING'
3. Sort chronologically
4. Return as semicolon-separated list with dates

EXAMPLE OUTPUT:
"2018-05-27: Baseline tumor 3cm;2019-06-15: Stable;2021-03-01: Progression 4.5cm"

Gold Standard for C1277724: Multiple imaging studies documenting progression''',
            'input_variables': 'imaging_findings;document_type',
            'default_empty_value': 'No imaging timeline documented',
            'option_definitions': ''
        },
        {
            'name': 'treatment_response_summary',
            'variable_type': 'text',
            'instructions': '''Summarize treatment response for each treatment line.

AGGREGATION LOGIC:
1. Match chemotherapy_agents with corresponding treatment_response assessments
2. Create summary: "[agent]: [response]" for each treatment line

EXAMPLE OUTPUT:
"vinblastine: Partial Response; bevacizumab: Stable Disease; selumetinib: Progressive Disease"

Gold Standard for C1277724: Variable responses across treatment lines''',
            'input_variables': 'treatment_response;chemotherapy_agents',
            'default_empty_value': 'No treatment response documented',
            'option_definitions': ''
        }
    ]
    
    # Write to CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dependent_variables)
    
    print(f"✅ Redesigned decisions.csv written to: {output_file}")
    print(f"   Total dependent variables: {len(dependent_variables)}")
    print(f"   Format: BRIM-compliant (name, variable_type, instructions, input_variables, default_empty_value, option_definitions)")
    
    # Summary by type
    filter_count = sum(1 for dv in dependent_variables if 'surgery' in dv['name'] and 'total' not in dv['name'])
    agg_count = len(dependent_variables) - filter_count
    
    print(f"\n   Breakdown:")
    print(f"     - Surgery-specific filters: {filter_count}")
    print(f"     - Aggregations: {agg_count}")
    
    return dependent_variables

if __name__ == "__main__":
    output_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/decisions_v2_redesigned.csv"
    
    print("=" * 80)
    print("CREATING REDESIGNED DECISIONS.CSV (Option B - Full Redesign)")
    print("=" * 80)
    print()
    
    dependent_vars = create_redesigned_decisions(output_file)
    
    print()
    print("=" * 80)
    print("✅ DECISIONS REDESIGN COMPLETE")
    print("=" * 80)
    print("\nKey Changes from Old Format:")
    print("  ❌ REMOVED: decision_type (filter/aggregation)")
    print("  ✅ ADDED: variable_type (text/boolean/integer/float)")
    print("  ❌ REMOVED: output_variable (redundant with name)")
    print("  ❌ REMOVED: aggregation_prompt (merged into instructions)")
    print("  ✅ ADDED: default_empty_value (required by BRIM)")
    print("  ✅ ENHANCED: option_definitions (proper JSON for categorical vars)")
    print("\nAll filtering logic now in dependent variables (not in variable instructions)")
