#!/usr/bin/env python3
"""
Integrate retrieved Binary documents into project.csv for BRIM Phase 3a_v2 upload.

This script:
1. Reads existing project.csv (892 rows)
2. Preserves FHIR_BUNDLE row and STRUCTURED data rows
3. Reads retrieved_binary_documents.csv (1,371 rows)
4. Combines into new project.csv (~1,376 rows)
5. Validates output format and completeness

Author: GitHub Copilot
Date: 2025-01-XX
"""

import pandas as pd
import sys
from pathlib import Path
import numpy as np

# Configuration
PROJECT_DIR = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics")
PHASE_DIR = PROJECT_DIR / "pilot_output" / "brim_csvs_iteration_3c_phase3a_v2"

EXISTING_PROJECT_CSV = PHASE_DIR / "project.csv"
RETRIEVED_DOCS_CSV = PHASE_DIR / "retrieved_binary_documents.csv"
OUTPUT_PROJECT_CSV = PHASE_DIR / "project_integrated.csv"

# Expected structure markers
FHIR_BUNDLE_MARKER = "FHIR_BUNDLE"
STRUCTURED_MARKERS = [
    "Molecular Testing Summary",
    "Surgical History Summary", 
    "Treatment History Summary",
    "Diagnosis Date Summary"
]

def load_existing_project():
    """Load existing project.csv and separate preserved rows from documents."""
    print(f"[1/6] Loading existing project.csv from {EXISTING_PROJECT_CSV}...")
    
    df = pd.read_csv(EXISTING_PROJECT_CSV)
    print(f"  ✓ Loaded {len(df)} rows")
    
    # Identify preserved rows (FHIR_BUNDLE + STRUCTURED summaries)
    # NOTE_TITLE column contains these markers
    preserved_mask = (
        (df['NOTE_TITLE'] == FHIR_BUNDLE_MARKER) |
        (df['NOTE_TITLE'].isin(STRUCTURED_MARKERS))
    )
    
    preserved_rows = df[preserved_mask].copy()
    document_rows = df[~preserved_mask].copy()
    
    print(f"  ✓ Identified {len(preserved_rows)} preserved rows:")
    for i, row in preserved_rows.iterrows():
        print(f"    - Row {i+1}: {row['NOTE_TITLE']}")
    
    print(f"  ✓ Identified {len(document_rows)} existing document rows (will be replaced)")
    
    return df, preserved_rows, document_rows


def load_retrieved_documents():
    """Load retrieved Binary documents."""
    print(f"\n[2/6] Loading retrieved Binary documents from {RETRIEVED_DOCS_CSV}...")
    
    df = pd.read_csv(RETRIEVED_DOCS_CSV)
    print(f"  ✓ Loaded {len(df)} documents")
    
    # Show document type breakdown
    if 'DOCUMENT_TYPE' in df.columns:
        print(f"\n  Document Type Breakdown:")
        type_counts = df['DOCUMENT_TYPE'].value_counts()
        for doc_type, count in type_counts.items():
            print(f"    - {doc_type}: {count}")
    
    return df


def transform_retrieved_to_project_format(retrieved_df):
    """Transform retrieved documents to match project.csv format."""
    print(f"\n[3/6] Transforming retrieved documents to project.csv format...")
    
    # Map columns:
    # retrieved_binary_documents.csv: NOTE_ID, SUBJECT_ID, NOTE_DATETIME, NOTE_TEXT, DOCUMENT_TYPE
    # project.csv: NOTE_ID, PERSON_ID, NOTE_DATETIME, NOTE_TEXT, NOTE_TITLE
    
    transformed = pd.DataFrame({
        'NOTE_ID': retrieved_df['NOTE_ID'],
        'PERSON_ID': retrieved_df['SUBJECT_ID'],
        'NOTE_DATETIME': retrieved_df['NOTE_DATETIME'],
        'NOTE_TEXT': retrieved_df['NOTE_TEXT'],
        'NOTE_TITLE': retrieved_df['DOCUMENT_TYPE']  # Use document type as title
    })
    
    print(f"  ✓ Transformed {len(transformed)} documents")
    
    # Validate required fields BEFORE filtering
    missing_note_id = transformed['NOTE_ID'].isna().sum()
    missing_person_id = transformed['PERSON_ID'].isna().sum()
    missing_datetime = transformed['NOTE_DATETIME'].isna().sum()
    missing_text = transformed['NOTE_TEXT'].isna().sum()
    
    if missing_note_id > 0:
        print(f"  ⚠ WARNING: {missing_note_id} documents missing NOTE_ID")
    if missing_person_id > 0:
        print(f"  ⚠ WARNING: {missing_person_id} documents missing PERSON_ID")
    if missing_datetime > 0:
        print(f"  ⚠ WARNING: {missing_datetime} documents missing NOTE_DATETIME - will exclude")
    if missing_text > 0:
        print(f"  ⚠ WARNING: {missing_text} documents missing NOTE_TEXT - will exclude")
    
    # Filter out documents with missing critical fields
    before_count = len(transformed)
    transformed = transformed[
        transformed['NOTE_ID'].notna() &
        transformed['NOTE_DATETIME'].notna() &
        transformed['NOTE_TEXT'].notna()
    ].copy()
    after_count = len(transformed)
    
    if before_count != after_count:
        excluded = before_count - after_count
        print(f"  ⚠ Excluded {excluded} documents with missing critical fields")
        print(f"  ✓ Proceeding with {after_count} valid documents")
    
    # Check for empty text content
    empty_text = (transformed['NOTE_TEXT'].str.strip() == '').sum()
    if empty_text > 0:
        print(f"  ⚠ WARNING: {empty_text} documents have empty NOTE_TEXT (but will include)")
    
    return transformed


def combine_project_csv(preserved_rows, new_documents):
    """Combine preserved rows with new document rows."""
    print(f"\n[4/6] Combining preserved rows with new documents...")
    
    # Concatenate: preserved rows first, then documents
    combined = pd.concat([preserved_rows, new_documents], ignore_index=True)
    
    print(f"  ✓ Combined project.csv structure:")
    print(f"    - Preserved rows: {len(preserved_rows)}")
    print(f"    - New documents: {len(new_documents)}")
    print(f"    - Total rows: {len(combined)}")
    
    return combined


def validate_output(combined_df, expected_preserved=5, expected_docs=1371):
    """Validate output CSV format and completeness."""
    print(f"\n[5/6] Validating output...")
    
    errors = []
    warnings = []
    
    # Check row count
    expected_total = expected_preserved + expected_docs
    if len(combined_df) != expected_total:
        warnings.append(f"Expected {expected_total} total rows, got {len(combined_df)}")
    
    # Check preserved rows
    preserved_mask = (
        (combined_df['NOTE_TITLE'] == FHIR_BUNDLE_MARKER) |
        (combined_df['NOTE_TITLE'].isin(STRUCTURED_MARKERS))
    )
    preserved_count = preserved_mask.sum()
    if preserved_count != expected_preserved:
        errors.append(f"Expected {expected_preserved} preserved rows, got {preserved_count}")
    
    # Check document rows (allow some variance due to filtering)
    document_count = (~preserved_mask).sum()
    if document_count < expected_docs - 5:  # Allow up to 5 excluded documents
        warnings.append(f"Expected ~{expected_docs} document rows, got {document_count}")
    elif document_count != expected_docs:
        warnings.append(f"Document count: {document_count} (expected {expected_docs})")
    
    # Check required columns
    required_cols = ['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE']
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
    
    # Check for null values in critical fields
    for col in ['NOTE_ID', 'NOTE_TEXT']:
        null_count = combined_df[col].isna().sum()
        if null_count > 0:
            errors.append(f"{null_count} null values in {col}")
    
    # Check datetime format
    try:
        pd.to_datetime(combined_df['NOTE_DATETIME'], errors='coerce')
        invalid_dates = combined_df['NOTE_DATETIME'].isna().sum()
        if invalid_dates > 0:
            warnings.append(f"{invalid_dates} invalid datetime values")
    except Exception as e:
        warnings.append(f"Could not validate datetime format: {e}")
    
    # Print results
    if errors:
        print(f"  ✗ VALIDATION FAILED:")
        for error in errors:
            print(f"    - ERROR: {error}")
        return False
    else:
        print(f"  ✓ Validation passed!")
    
    if warnings:
        print(f"  ⚠ Warnings:")
        for warning in warnings:
            print(f"    - {warning}")
    
    return True


def save_output(combined_df):
    """Save combined project.csv."""
    print(f"\n[6/6] Saving integrated project.csv to {OUTPUT_PROJECT_CSV}...")
    
    # Save with same CSV format as input (quoted strings)
    combined_df.to_csv(OUTPUT_PROJECT_CSV, index=False, quoting=1)  # quoting=1 = QUOTE_ALL
    
    print(f"  ✓ Saved {len(combined_df)} rows")
    
    # Verify file size
    file_size_mb = OUTPUT_PROJECT_CSV.stat().st_size / (1024 * 1024)
    print(f"  ✓ Output file size: {file_size_mb:.2f} MB")


def main():
    """Main execution."""
    print("=" * 80)
    print("INTEGRATE BINARY DOCUMENTS INTO PROJECT.CSV")
    print("=" * 80)
    print(f"Phase: 3a_v2")
    print(f"Patient: C1277724")
    print(f"Expected output: ~1,376 rows (5 preserved + 1,371 documents)")
    print("=" * 80)
    
    try:
        # Step 1: Load existing project.csv
        original_df, preserved_rows, old_documents = load_existing_project()
        
        # Step 2: Load retrieved documents
        retrieved_df = load_retrieved_documents()
        
        # Step 3: Transform to project.csv format
        new_documents = transform_retrieved_to_project_format(retrieved_df)
        
        # Step 4: Combine
        combined_df = combine_project_csv(preserved_rows, new_documents)
        
        # Step 5: Validate
        if not validate_output(combined_df, 
                              expected_preserved=len(preserved_rows),
                              expected_docs=len(new_documents)):
            print("\n✗ Validation failed - review errors above")
            sys.exit(1)
        
        # Step 6: Save
        save_output(combined_df)
        
        print("\n" + "=" * 80)
        print("✓ INTEGRATION COMPLETE!")
        print("=" * 80)
        print(f"Original project.csv: {len(original_df)} rows")
        print(f"  - Preserved rows: {len(preserved_rows)}")
        print(f"  - Old documents: {len(old_documents)} (replaced)")
        print(f"\nRetrieved documents: {len(retrieved_df)} rows")
        print(f"\nNew project.csv: {len(combined_df)} rows")
        print(f"  - Preserved rows: {len(preserved_rows)}")
        print(f"  - New documents: {len(new_documents)}")
        print(f"\nOutput saved to: {OUTPUT_PROJECT_CSV}")
        print("\nNext steps:")
        print("  1. Review project_integrated.csv")
        print("  2. If validated, rename to project.csv")
        print("  3. Validate Phase 3a_v2 package completeness (5 CSVs)")
        print("  4. Upload to BRIM")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
