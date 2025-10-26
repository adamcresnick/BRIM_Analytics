#!/usr/bin/env python3
"""
Rebuild DATETIME_STANDARDIZED_VIEWS.sql from individual view files
This consolidates all v_* view definitions into a single deployable file
"""

import os
from pathlib import Path

# List of view files to include (in desired order)
VIEW_FILES = [
    'V_CHEMOTHERAPY_DRUGS_NEW.sql',  # Base chemotherapy reference
    'V_CHEMO_MEDICATIONS.sql',       # Updated with therapeutic_normalized
    'V_MEDICATIONS.sql',
    'V_CONCOMITANT_MEDICATIONS.sql',
    'V_DIAGNOSES.sql',
    'V_PROBLEM_LIST_DIAGNOSES.sql',
    'V_HYDROCEPHALUS_DIAGNOSIS.sql',
    'V_PROCEDURES_TUMOR.sql',
    'V_HYDROCEPHALUS_PROCEDURES.sql',
    'V_IMAGING.sql',
    'V_IMAGING_CORTICOSTEROID_USE.sql',
    'V_VISITS_UNIFIED.sql',
    'V_MEASUREMENTS.sql',
    'V_MOLECULAR_TESTS.sql',
    'V_RADIATION_TREATMENTS.sql',
    'V_RADIATION_TREATMENT_APPOINTMENTS_FIXED.sql',
    'V_RADIATION_SUMMARY.sql',
    'V_RADIATION_CARE_PLAN_HIERARCHY.sql',
    'V_RADIATION_DOCUMENTS.sql',
    'V_AUTOLOGOUS_STEM_CELL_TRANSPLANT.sql',
    'V_AUTOLOGOUS_STEM_CELL_COLLECTION.sql',
    'V_OPHTHALMOLOGY_ASSESSMENTS.sql',
    'V_AUDIOLOGY_ASSESSMENTS.sql',
    'V_PATIENT_DEMOGRAPHICS.sql',
    'V_ENCOUNTERS.sql',
    'V_BINARY_FILES.sql',
    'V_UNIFIED_PATIENT_TIMELINE.sql',  # NEW: Added unified timeline
]

def read_view_file(filepath):
    """Read a view file and return its contents"""
    with open(filepath, 'r') as f:
        return f.read()

def main():
    views_dir = Path(__file__).parent / 'views'
    output_file = views_dir / 'DATETIME_STANDARDIZED_VIEWS.sql'

    # Header
    header = """-- ================================================================================
-- DATETIME STANDARDIZED ATHENA VIEWS - CONSOLIDATED FILE
-- ================================================================================
-- Purpose: All Athena view definitions in a single file for deployment
-- Date: 2025-10-26
--
-- This file consolidates all v_* view definitions including:
--   - Datetime standardization (VARCHAR → TIMESTAMP(3))
--   - Drug normalization (therapeutic_normalized for salt variants)
--   - Unified patient timeline
--
-- DEPLOYMENT:
--   Deploy individual views using their respective deployment scripts
--   This file serves as a reference and can be used for bulk deployment
-- ================================================================================

"""

    with open(output_file, 'w') as out:
        out.write(header)

        for view_file in VIEW_FILES:
            filepath = views_dir / view_file

            if not filepath.exists():
                print(f"WARNING: {view_file} not found, skipping...")
                continue

            print(f"Adding {view_file}...")

            # Add separator
            out.write(f"\n-- {'='*80}\n")
            out.write(f"-- VIEW FILE: {view_file}\n")
            out.write(f"-- {'='*80}\n\n")

            # Read and write view content
            content = read_view_file(filepath)
            out.write(content)

            # Ensure ends with semicolon and newlines
            if not content.rstrip().endswith(';'):
                out.write('\n;\n')
            out.write('\n\n')

    print(f"\n✓ Successfully created {output_file}")
    print(f"  Total views: {len(VIEW_FILES)}")

    # Get file size
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"  File size: {size_mb:.2f} MB")

if __name__ == '__main__':
    main()
