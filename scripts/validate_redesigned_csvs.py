#!/usr/bin/env python3
"""
Validate redesigned CSVs for BRIM upload

Checks:
1. No empty required fields
2. Valid variable_type values (text/boolean/integer/float)
3. input_variables reference existing variable names
4. option_definitions are valid JSON (when present)
5. No duplicate names
6. Proper CSV formatting
"""

import csv
import json
import sys
from pathlib import Path

# BRIM data types
VALID_VARIABLE_TYPES = {'text', 'boolean', 'integer', 'float'}

def validate_variables(filepath):
    """Validate variables.csv format"""
    print(f"\n📋 VALIDATING VARIABLES: {filepath}")
    print("=" * 80)
    
    errors = []
    warnings = []
    variable_names = set()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Check required columns
        required_cols = {'variable_name', 'variable_type', 'scope'}
        missing_cols = required_cols - set(reader.fieldnames)
        if missing_cols:
            errors.append(f"❌ Missing required columns: {missing_cols}")
            return errors, warnings, variable_names
        
        for i, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            var_name = row.get('variable_name', '').strip()
            
            # Check empty name
            if not var_name:
                errors.append(f"❌ Row {i}: Empty variable_name")
                continue
            
            # Check duplicate names
            if var_name in variable_names:
                errors.append(f"❌ Row {i}: Duplicate variable_name '{var_name}'")
            variable_names.add(var_name)
            
            # Check variable_type
            var_type = row.get('variable_type', '').strip()
            if not var_type:
                errors.append(f"❌ Row {i} ({var_name}): Empty variable_type")
            elif var_type not in VALID_VARIABLE_TYPES:
                errors.append(f"❌ Row {i} ({var_name}): Invalid variable_type '{var_type}' (must be text/boolean/integer/float)")
            
            # Check scope
            scope = row.get('scope', '').strip()
            valid_scopes = {'one_per_patient', 'many_per_note', 'one_per_note'}
            if not scope:
                errors.append(f"❌ Row {i} ({var_name}): Empty scope")
            elif scope not in valid_scopes:
                warnings.append(f"⚠️  Row {i} ({var_name}): Unusual scope '{scope}'")
            
            # Check instruction exists
            instruction = row.get('instruction', '').strip()
            if not instruction:
                warnings.append(f"⚠️  Row {i} ({var_name}): Empty instruction")
            
            # Check option_definitions if present
            option_defs = row.get('option_definitions', '').strip()
            if option_defs:
                try:
                    json.loads(option_defs)
                except json.JSONDecodeError as e:
                    errors.append(f"❌ Row {i} ({var_name}): Invalid JSON in option_definitions: {e}")
    
    print(f"✅ Total variables: {len(variable_names)}")
    
    if errors:
        print(f"\n❌ ERRORS FOUND: {len(errors)}")
        for err in errors[:10]:  # Show first 10
            print(f"   {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    else:
        print("✅ No errors found in variables.csv")
    
    if warnings:
        print(f"\n⚠️  WARNINGS: {len(warnings)}")
        for warn in warnings[:5]:
            print(f"   {warn}")
        if len(warnings) > 5:
            print(f"   ... and {len(warnings) - 5} more warnings")
    
    return errors, warnings, variable_names


def validate_decisions(filepath, valid_variable_names):
    """Validate decisions.csv (dependent variables) format"""
    print(f"\n📋 VALIDATING DECISIONS: {filepath}")
    print("=" * 80)
    
    errors = []
    warnings = []
    decision_names = set()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Check required columns
        required_cols = {'name', 'variable_type', 'instructions', 'input_variables', 'default_empty_value'}
        missing_cols = required_cols - set(reader.fieldnames)
        if missing_cols:
            errors.append(f"❌ Missing required columns: {missing_cols}")
            return errors, warnings
        
        for i, row in enumerate(reader, start=2):
            decision_name = row.get('name', '').strip()
            
            # Check empty name
            if not decision_name:
                errors.append(f"❌ Row {i}: Empty name")
                continue
            
            # Check duplicate names
            if decision_name in decision_names:
                errors.append(f"❌ Row {i}: Duplicate name '{decision_name}'")
            decision_names.add(decision_name)
            
            # Check variable_type
            var_type = row.get('variable_type', '').strip()
            if not var_type:
                errors.append(f"❌ Row {i} ({decision_name}): Empty variable_type")
            elif var_type not in VALID_VARIABLE_TYPES:
                errors.append(f"❌ Row {i} ({decision_name}): Invalid variable_type '{var_type}' (must be text/boolean/integer/float)")
            
            # Check instructions
            instructions = row.get('instructions', '').strip()
            if not instructions:
                errors.append(f"❌ Row {i} ({decision_name}): Empty instructions")
            
            # Check input_variables reference existing variables
            input_vars = row.get('input_variables', '').strip()
            if not input_vars:
                errors.append(f"❌ Row {i} ({decision_name}): Empty input_variables")
            else:
                # Parse semicolon-separated list
                var_list = [v.strip() for v in input_vars.split(';') if v.strip()]
                for var in var_list:
                    if var not in valid_variable_names:
                        errors.append(f"❌ Row {i} ({decision_name}): input_variable '{var}' not found in variables.csv")
            
            # Check default_empty_value exists (can be empty string but field must exist)
            if 'default_empty_value' not in row:
                errors.append(f"❌ Row {i} ({decision_name}): Missing default_empty_value column")
            
            # Check option_definitions if present
            option_defs = row.get('option_definitions', '').strip()
            if option_defs:
                try:
                    json.loads(option_defs)
                except json.JSONDecodeError as e:
                    errors.append(f"❌ Row {i} ({decision_name}): Invalid JSON in option_definitions: {e}")
    
    print(f"✅ Total dependent variables: {len(decision_names)}")
    
    if errors:
        print(f"\n❌ ERRORS FOUND: {len(errors)}")
        for err in errors[:10]:
            print(f"   {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    else:
        print("✅ No errors found in decisions.csv")
    
    if warnings:
        print(f"\n⚠️  WARNINGS: {len(warnings)}")
        for warn in warnings[:5]:
            print(f"   {warn}")
    
    return errors, warnings


def main():
    base_dir = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2")
    
    variables_file = base_dir / "variables_v2_redesigned.csv"
    decisions_file = base_dir / "decisions_v2_redesigned.csv"
    
    print("=" * 80)
    print("VALIDATING REDESIGNED BRIM CSVs")
    print("=" * 80)
    
    # Validate variables
    var_errors, var_warnings, variable_names = validate_variables(variables_file)
    
    # Validate decisions
    dec_errors, dec_warnings = validate_decisions(decisions_file, variable_names)
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    total_errors = len(var_errors) + len(dec_errors)
    total_warnings = len(var_warnings) + len(dec_warnings)
    
    if total_errors == 0:
        print("✅ ALL VALIDATIONS PASSED!")
        print(f"   - Variables: {len(variable_names)} variables, 0 errors")
        print(f"   - Decisions: {len([1 for _ in csv.DictReader(open(decisions_file))])} dependent variables, 0 errors")
        if total_warnings > 0:
            print(f"   - Warnings: {total_warnings} (non-blocking)")
        print("\n✅ CSVs are ready for BRIM upload!")
        return 0
    else:
        print(f"❌ VALIDATION FAILED")
        print(f"   - Total errors: {total_errors}")
        print(f"   - Total warnings: {total_warnings}")
        print("\n❌ Fix errors before uploading to BRIM")
        return 1

if __name__ == "__main__":
    sys.exit(main())
