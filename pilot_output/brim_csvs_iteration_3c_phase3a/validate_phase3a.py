#!/usr/bin/env python3
"""
Phase 3a Validation Script - Tier 1 Expansion
Validates BRIM extraction results for 17 variables (13 Tier 1 + 4 Surgery)
Patient: C1277724
Date: October 3, 2025
"""

import csv
import sys
from collections import defaultdict
from typing import Dict, List, Set

# Gold Standard Values for C1277724
GOLD_STANDARD = {
    # Demographics (5 variables)
    "patient_gender": {"expected": ["Female"], "acceptable": ["Female"], "must_match": True},
    "date_of_birth": {"expected": ["2005-05-13"], "acceptable": ["2005-05-13"], "must_match": True},
    "age_at_diagnosis": {"expected": ["13"], "acceptable": ["13", "12", "14"], "must_match": False},  # Allow rounding variation
    "race": {"expected": ["White"], "acceptable": ["White", "Unavailable", "Unknown"], "must_match": False},
    "ethnicity": {"expected": ["Not Hispanic or Latino"], "acceptable": ["Not Hispanic or Latino", "Unavailable", "Unknown"], "must_match": False},
    
    # Core Diagnosis (4 variables)
    "primary_diagnosis": {"expected": ["Pilocytic astrocytoma", "Astrocytoma, pilocytic"], "acceptable": ["Pilocytic astrocytoma", "Astrocytoma, pilocytic", "Pilocytic Astrocytoma"], "must_match": False},
    "diagnosis_date": {"expected": ["2018-06-04"], "acceptable": ["2018-06-04", "2018-06"], "must_match": False},
    "who_grade": {"expected": ["Grade I"], "acceptable": ["Grade I", "1"], "must_match": False},
    "tumor_location": {"expected": ["Cerebellum/Posterior Fossa"], "acceptable": ["Cerebellum/Posterior Fossa", "Cerebellum", "Posterior Fossa"], "must_match": False},
    
    # Molecular Markers (4 variables)
    "idh_mutation": {"expected": ["IDH wild-type"], "acceptable": ["IDH wild-type", "Not tested", "Unknown"], "must_match": False},  # Inference acceptable
    "mgmt_methylation": {"expected": ["Not tested"], "acceptable": ["Not tested", "Unknown"], "must_match": False},
    "braf_status": {"expected": ["BRAF fusion"], "acceptable": ["BRAF fusion", "KIAA1549-BRAF fusion"], "must_match": True},
    
    # Surgery (4 variables - many_per_note, Phase 2 validated)
    "surgery_date": {"expected": ["2018-05-28", "2021-03-10"], "acceptable": ["2018-05-28", "2021-03-10"], "must_match": True},
    "surgery_type": {"expected": ["Tumor Resection"], "acceptable": ["Tumor Resection"], "must_match": True},
    "surgery_extent": {"expected": ["Partial Resection"], "acceptable": ["Partial Resection", "Subtotal Resection"], "must_match": False},
    "surgery_location": {"expected": ["Cerebellum/Posterior Fossa"], "acceptable": ["Cerebellum/Posterior Fossa"], "must_match": True},
}

# Variable Categories for Reporting
VARIABLE_CATEGORIES = {
    "Demographics": ["patient_gender", "date_of_birth", "age_at_diagnosis", "race", "ethnicity"],
    "Diagnosis": ["primary_diagnosis", "diagnosis_date", "who_grade", "tumor_location"],
    "Molecular": ["idh_mutation", "mgmt_methylation", "braf_status"],
    "Surgery": ["surgery_date", "surgery_type", "surgery_extent", "surgery_location"],
}

def read_brim_export(filepath: str) -> Dict[str, List[str]]:
    """Read BRIM export CSV and organize by variable name"""
    extractions = defaultdict(list)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # BRIM export uses 'Name' and 'Value' columns (not 'variable_name' and 'value')
            variable_name = row.get('Name', '').strip()
            value = row.get('Value', '').strip()
            if variable_name and value:
                extractions[variable_name].append(value)
    
    return dict(extractions)

def validate_variable(variable_name: str, extracted_values: List[str], gold_standard: Dict) -> Dict:
    """Validate a single variable against gold standard"""
    result = {
        "variable_name": variable_name,
        "extracted_count": len(extracted_values),
        "unique_values": list(set(extracted_values)),
        "expected_values": gold_standard["expected"],
        "matches_found": [],
        "is_valid": False,
        "must_match": gold_standard["must_match"],
        "confidence": "HIGH" if gold_standard["must_match"] else "MEDIUM",
    }
    
    # Check if any expected values found in extractions
    for expected in gold_standard["expected"]:
        if expected in extracted_values:
            result["matches_found"].append(expected)
    
    # Check if any acceptable values found
    for acceptable in gold_standard["acceptable"]:
        if acceptable in extracted_values:
            if acceptable not in result["matches_found"]:
                result["matches_found"].append(acceptable)
    
    # Validation logic
    if gold_standard["must_match"]:
        # MUST MATCH: All expected values must be found
        result["is_valid"] = all(exp in extracted_values for exp in gold_standard["expected"])
    else:
        # SHOULD MATCH: At least one acceptable value found
        result["is_valid"] = len(result["matches_found"]) > 0
    
    return result

def print_results(extractions: Dict[str, List[str]], validation_results: List[Dict]):
    """Print formatted validation results"""
    
    print("=" * 70)
    print("BRIM PHASE 3a TIER 1 EXPANSION VALIDATION RESULTS")
    print("17 Variables: 13 Tier 1 (new) + 4 Surgery (Phase 2 validated)")
    print("=" * 70)
    print()
    
    # Total extractions
    total_extractions = sum(len(values) for values in extractions.values())
    print(f"TOTAL EXTRACTIONS: {total_extractions} values")
    print()
    
    # Results by category
    for category, variables in VARIABLE_CATEGORIES.items():
        print(f"{category.upper()} VARIABLES ({len(variables)} total):")
        print("-" * 70)
        
        category_correct = 0
        for var in variables:
            if var not in extractions:
                print(f"{var:30} ❌ NOT EXTRACTED")
                continue
            
            result = next((r for r in validation_results if r["variable_name"] == var), None)
            if not result:
                continue
            
            status = "✅" if result["is_valid"] else "❌"
            count = result["extracted_count"]
            unique = len(result["unique_values"])
            matches = result["matches_found"]
            
            if result["is_valid"]:
                category_correct += 1
            
            # Format output based on extraction count
            if count == 1:
                # One_per_patient variables
                value = result["unique_values"][0] if result["unique_values"] else "None"
                if matches:
                    print(f"{var:30} {status} {count} extraction  → \"{value}\" (MATCH)")
                else:
                    print(f"{var:30} {status} {count} extraction  → \"{value}\" (NO MATCH - expected {result['expected_values']})")
            else:
                # Many_per_note variables
                if matches:
                    match_str = ", ".join([f"\"{m}\"" for m in matches])
                    print(f"{var:30} {status} {count} extractions → Contains {match_str} (MATCH)")
                else:
                    expected_str = ", ".join([f"\"{e}\"" for e in result['expected_values']])
                    print(f"{var:30} {status} {count} extractions → Missing {expected_str}")
        
        print()
        print(f"{category} Accuracy: {category_correct}/{len(variables)} = {100*category_correct/len(variables):.1f}%")
        print()
    
    # Overall results
    print("=" * 70)
    total_valid = sum(1 for r in validation_results if r["is_valid"])
    total_vars = len(validation_results)
    accuracy = 100 * total_valid / total_vars if total_vars > 0 else 0
    
    print(f"GOLD STANDARD VALIDATION: {total_valid}/{total_vars} = {accuracy:.1f}%", end="")
    if accuracy >= 95:
        print(" ✅")
    elif accuracy >= 80:
        print(" ⚠️")
    else:
        print(" ❌")
    print("=" * 70)
    print()
    
    # Detailed failures
    failures = [r for r in validation_results if not r["is_valid"]]
    if failures:
        print("DETAILED FAILURE ANALYSIS:")
        print("-" * 70)
        for failure in failures:
            print(f"\nVariable: {failure['variable_name']}")
            print(f"  Expected: {failure['expected_values']}")
            print(f"  Extracted: {failure['unique_values']}")
            print(f"  Matches Found: {failure['matches_found']}")
            print(f"  Must Match: {failure['must_match']}")
        print()
    
    # Success message
    if accuracy >= 95:
        print("🎉 PHASE 3a SUCCESS! Ready for Tier 2 expansion (chemotherapy + radiation)")
    elif accuracy >= 80:
        print("⚠️  PHASE 3a PARTIAL SUCCESS. Review failures before Tier 2.")
    else:
        print("❌ PHASE 3a NEEDS ITERATION. Significant failures detected.")
    print()

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 validate_phase3a.py <brim_export.csv>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    # Read extractions
    extractions = read_brim_export(filepath)
    
    # Validate each variable
    validation_results = []
    for variable_name, gold_standard in GOLD_STANDARD.items():
        extracted_values = extractions.get(variable_name, [])
        result = validate_variable(variable_name, extracted_values, gold_standard)
        validation_results.append(result)
    
    # Print results
    print_results(extractions, validation_results)
    
    # Exit code based on accuracy
    total_valid = sum(1 for r in validation_results if r["is_valid"])
    accuracy = 100 * total_valid / len(validation_results)
    
    if accuracy >= 95:
        sys.exit(0)  # Success
    elif accuracy >= 80:
        sys.exit(1)  # Partial success
    else:
        sys.exit(2)  # Failure

if __name__ == "__main__":
    main()
