#!/usr/bin/env python3
"""
Create decisions.csv in BRIM's ACTUAL expected format based on screenshot documentation

BRIM Expected Format:
decision_name,instruction,decision_type,prompt_template,variables

Key differences from what we created:
- Column name: 'decision_name' (not 'name')
- Column name: 'instruction' (not 'instructions')  
- Column name: 'decision_type' (text/boolean/integer/float - the DATA TYPE)
- Column name: 'prompt_template' (the full prompt)
- Column name: 'variables' (format: "[variable_name_1, variable_name_2]")
- NO default_empty_value column
- NO option_definitions column
"""

import csv
import json

def create_brim_format_decisions(output_file):
    """Create decisions CSV in BRIM's actual expected format"""
    
    fieldnames = ['decision_name', 'instruction', 'decision_type', 'prompt_template', 'variables']
    
    decisions = [
        # Surgery-specific filters
        {
            'decision_name': 'diagnosis_surgery1',
            'instruction': 'Return the diagnosis associated with the FIRST surgery (earliest surgery_date).',
            'decision_type': 'text',
            'prompt_template': '''Return the diagnosis associated with the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST value in the surgery_date variable (first surgery date)
2. Look for surgery_diagnosis values associated with that date
3. If surgery_diagnosis not available, use primary_diagnosis from documents near that date
4. Prioritize pathology-confirmed diagnoses

Gold Standard for C1277724 Surgery 1 (2018-05-28): Pilocytic astrocytoma

Return ONLY the diagnosis text. If no diagnosis found, return "Unknown".''',
            'variables': '[surgery_date, surgery_diagnosis, primary_diagnosis, document_type]'
        },
        {
            'decision_name': 'extent_surgery1',
            'instruction': 'Return the extent of resection for the FIRST surgery (earliest surgery_date).',
            'decision_type': 'text',
            'prompt_template': '''Return the extent of resection for the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST value in surgery_date (first surgery date)
2. Find surgery_extent values associated with that date
3. Prioritize document_type='OPERATIVE' (surgeon's assessment is most authoritative)

VALID RETURN VALUES:
Must be one of: Gross Total Resection, Near Total Resection, Subtotal Resection, Partial Resection, Biopsy Only, Unknown

Gold Standard for C1277724 Surgery 1 (2018-05-28): Partial Resection

Return ONLY the extent classification.''',
            'variables': '[surgery_date, surgery_extent, document_type]'
        },
        {
            'decision_name': 'location_surgery1',
            'instruction': 'Return the anatomical location for the FIRST surgery (earliest surgery_date).',
            'decision_type': 'text',
            'prompt_template': '''Return the anatomical location for the FIRST surgery.

FILTERING LOGIC:
1. Identify the EARLIEST value in surgery_date (first surgery date)
2. Find surgery_location values associated with that date
3. Use most specific location mentioned

Gold Standard for C1277724 Surgery 1 (2018-05-28): Cerebellum/Posterior Fossa

Return ONLY the location name.''',
            'variables': '[surgery_date, surgery_location, document_type]'
        },
        {
            'decision_name': 'diagnosis_surgery2',
            'instruction': 'Return the diagnosis for the SECOND surgery if it exists (second earliest surgery_date).',
            'decision_type': 'text',
            'prompt_template': '''Return the diagnosis associated with the SECOND surgery (if it exists).

FILTERING LOGIC:
1. Check if surgery_number >= 2 (patient had at least 2 surgeries)
2. If yes: Identify the SECOND EARLIEST value in surgery_date
3. Find surgery_diagnosis associated with that date
4. If not available, use primary_diagnosis from documents near that date
5. If surgery_number < 2: Return "Unknown"

Gold Standard for C1277724 Surgery 2 (2021-03-10): Pilocytic astrocytoma, recurrent

Return ONLY the diagnosis text.''',
            'variables': '[surgery_number, surgery_date, surgery_diagnosis, primary_diagnosis, document_type]'
        },
        {
            'decision_name': 'extent_surgery2',
            'instruction': 'Return the extent of resection for the SECOND surgery if it exists.',
            'decision_type': 'text',
            'prompt_template': '''Return the extent of resection for the SECOND surgery (if it exists).

FILTERING LOGIC:
1. Check if surgery_number >= 2
2. If yes: Identify SECOND EARLIEST surgery_date
3. Find surgery_extent associated with that date
4. If surgery_number < 2: Return "Unknown"

Gold Standard for C1277724 Surgery 2 (2021-03-10): Partial Resection

Return ONLY the extent classification.''',
            'variables': '[surgery_number, surgery_date, surgery_extent, document_type]'
        },
        {
            'decision_name': 'location_surgery2',
            'instruction': 'Return the anatomical location for the SECOND surgery if it exists.',
            'decision_type': 'text',
            'prompt_template': '''Return the anatomical location for the SECOND surgery (if it exists).

FILTERING LOGIC:
1. Check if surgery_number >= 2
2. If yes: Identify SECOND EARLIEST surgery_date
3. Find surgery_location associated with that date
4. If surgery_number < 2: Return "Unknown"

Gold Standard for C1277724 Surgery 2 (2021-03-10): Cerebellum/Posterior Fossa

Return ONLY the location name.''',
            'variables': '[surgery_number, surgery_date, surgery_location, document_type]'
        },
        
        # Aggregation decisions
        {
            'decision_name': 'total_surgeries',
            'instruction': 'Count the total number of distinct surgeries for this patient.',
            'decision_type': 'integer',
            'prompt_template': '''Count the total number of distinct surgeries for this patient.

AGGREGATION LOGIC:
Count the number of unique values in surgery_date variable.
This should match the surgery_number variable.

Gold Standard for C1277724: 2

Return ONLY the integer count.''',
            'variables': '[surgery_date]'
        },
        {
            'decision_name': 'all_chemotherapy_agents',
            'instruction': 'Aggregate all chemotherapy agents into a semicolon-separated list.',
            'decision_type': 'text',
            'prompt_template': '''Aggregate all chemotherapy agents into a semicolon-separated list.

AGGREGATION LOGIC:
1. Collect ALL chemotherapy_agents values extracted across all documents
2. Remove duplicate agent names
3. Return as semicolon-separated list

Gold Standard for C1277724: vinblastine;bevacizumab;selumetinib

Return in format: "agent1;agent2;agent3"''',
            'variables': '[chemotherapy_agents]'
        },
        {
            'decision_name': 'all_symptoms',
            'instruction': 'Aggregate all documented symptoms into a semicolon-separated list.',
            'decision_type': 'text',
            'prompt_template': '''Aggregate all documented symptoms into a semicolon-separated list.

AGGREGATION LOGIC:
1. Collect ALL symptoms_present values across all documents
2. Remove duplicates
3. Return as semicolon-separated list

Gold Standard for C1277724: Emesis;Headaches;Hydrocephalus;Visual deficit;Posterior fossa syndrome

Return in format: "symptom1;symptom2;symptom3"''',
            'variables': '[symptoms_present]'
        },
        {
            'decision_name': 'earliest_symptom_date',
            'instruction': 'Identify the earliest date when symptoms were first documented.',
            'decision_type': 'text',
            'prompt_template': '''Identify the earliest date when symptoms were first documented.

AGGREGATION LOGIC:
1. Find the EARLIEST document where symptoms_present != "None documented"
2. Prioritize document_type='H&P' or 'CONSULTATION' (initial presentation)
3. Return the document date

Gold Standard for C1277724: Around initial diagnosis date (2018-06-04)

Return in YYYY-MM-DD format or "Unknown".''',
            'variables': '[symptoms_present, document_type]'
        },
        {
            'decision_name': 'molecular_tests_summary',
            'instruction': 'Create comprehensive molecular profile summary.',
            'decision_type': 'text',
            'prompt_template': '''Create comprehensive molecular profile summary.

AGGREGATION LOGIC:
Combine all molecular test results into single text summary.
Format: "BRAF: [status]; IDH: [status]; MGMT: [status]; Tests: [list]"

Gold Standard for C1277724: BRAF fusion present (KIAA1549-BRAF)

Return structured summary.''',
            'variables': '[molecular_testing_performed, braf_status, idh_mutation, mgmt_methylation]'
        },
        {
            'decision_name': 'imaging_progression_timeline',
            'instruction': 'Create timeline of imaging findings showing disease course.',
            'decision_type': 'text',
            'prompt_template': '''Create timeline of imaging findings showing disease course.

AGGREGATION LOGIC:
1. Extract ALL imaging_findings with their document dates
2. Prioritize document_type='IMAGING'
3. Sort chronologically
4. Return as semicolon-separated list with dates

Gold Standard for C1277724: Multiple imaging studies documenting progression

Return in format: "YYYY-MM-DD: finding;YYYY-MM-DD: finding"''',
            'variables': '[imaging_findings, document_type]'
        },
        {
            'decision_name': 'treatment_response_summary',
            'instruction': 'Summarize treatment response for each treatment line.',
            'decision_type': 'text',
            'prompt_template': '''Summarize treatment response for each treatment line.

AGGREGATION LOGIC:
1. Match chemotherapy_agents with corresponding treatment_response assessments
2. Create summary: "[agent]: [response]" for each treatment line

Gold Standard for C1277724: Variable responses across treatment lines

Return in format: "agent1: response1; agent2: response2"''',
            'variables': '[treatment_response, chemotherapy_agents]'
        }
    ]
    
    # Write CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(decisions)
    
    print(f"✅ Created {output_file} with {len(decisions)} decisions")
    print(f"   Format: BRIM screenshot format")
    print(f"   Columns: {fieldnames}")
    
    return decisions

if __name__ == "__main__":
    output_file = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/decisions_BRIM_FORMAT.csv"
    
    print("=" * 80)
    print("CREATING DECISIONS.CSV IN BRIM'S ACTUAL EXPECTED FORMAT")
    print("=" * 80)
    print()
    print("Based on BRIM screenshot documentation:")
    print("  decision_name,instruction,decision_type,prompt_template,variables")
    print()
    
    decisions = create_brim_format_decisions(output_file)
    
    print()
    print("=" * 80)
    print("✅ COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Replace decisions_PRODUCTION.csv with decisions_BRIM_FORMAT.csv")
    print("2. Re-upload to BRIM")
    print("3. Should now show '0 lines skipped' instead of '13 lines skipped'")
