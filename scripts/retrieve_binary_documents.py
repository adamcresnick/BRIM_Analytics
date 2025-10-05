#!/usr/bin/env python3
"""
Retrieve Binary documents from S3 for BRIM extraction.

Downloads ~1,385 documents based on event-based selection strategy:
- Progress Notes: 1,277 (ALL, HTML preferred)
- H&P: 13 (ALL, HTML preferred)
- Operative Notes: 29 (ALL, HTML preferred)
- Consultation Notes: 46 (ALL, HTML preferred)
- Event-Based Imaging: 20-24 (SELECTIVE, tied to surgeries/therapies)

Excludes:
- Pathology Study (40 - data already in Athena free-text)
- Encounter Summaries (761 XML - redundant with FHIR)
- Telephone Encounters (397 - limited content)
- Non-event Imaging (153 - not tied to clinical milestones)
"""

import pandas as pd
import boto3
import base64
import re
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys
from pathlib import Path

# Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
AWS_REGION = 'us-east-1'
S3_BUCKET = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
S3_PREFIX = 'prd/source/Binary/'
PATIENT_ID = 'C1277724'

# Surgery dates for event-based imaging (using strings for pandas comparison)
SURGERY_1_DATE = '2018-05-28'
SURGERY_2_DATE = '2021-03-10'

# Therapy periods for event-based imaging
VINBLASTINE_START = '2018-09-01'
VINBLASTINE_END = '2019-03-01'
SURVEILLANCE_START = '2023-01-01'
SURVEILLANCE_END = '2025-05-22'


def setup_aws_session():
    """Initialize AWS session with profile."""
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    return session.client('s3')


def load_annotated_files(csv_path):
    """Load accessible_binary_files_annotated.csv."""
    print(f"\n[1/7] Loading annotated Binary files from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"  ✓ Loaded {len(df)} documents")
    return df


def filter_progress_notes(df):
    """Filter for ALL Progress Notes with HTML preference."""
    print("\n[2/7] Filtering Progress Notes...")
    
    # Get all Progress Notes
    progress = df[df['document_type'] == 'Progress Notes'].copy()
    
    # Prefer HTML format
    progress['has_html'] = progress['content_type'].str.contains('text/html', na=False)
    progress = progress.sort_values(['has_html', 'document_date'], ascending=[False, False])
    
    print(f"  ✓ Selected {len(progress)} Progress Notes")
    return progress[['document_reference_id', 'document_type', 'document_date', 'binary_id', 'content_type']]


def filter_hp_notes(df):
    """Filter for ALL H&P with HTML preference."""
    print("\n[3/7] Filtering H&P Notes...")
    
    # Get all H&P
    hp = df[df['document_type'].str.contains('H&P', case=False, na=False)].copy()
    
    # Prefer HTML format
    hp['has_html'] = hp['content_type'].str.contains('text/html', na=False)
    hp = hp.sort_values(['has_html', 'document_date'], ascending=[False, False])
    
    print(f"  ✓ Selected {len(hp)} H&P Notes")
    return hp[['document_reference_id', 'document_type', 'document_date', 'binary_id', 'content_type']]


def filter_operative_notes(df):
    """Filter for ALL Operative Notes with HTML preference."""
    print("\n[4/7] Filtering Operative Notes...")
    
    # Get all OP Notes
    op = df[df['document_type'].str.contains('OP Note', case=False, na=False)].copy()
    
    # Prefer HTML format
    op['has_html'] = op['content_type'].str.contains('text/html', na=False)
    op = op.sort_values(['has_html', 'document_date'], ascending=[False, False])
    
    print(f"  ✓ Selected {len(op)} Operative Notes")
    return op[['document_reference_id', 'document_type', 'document_date', 'binary_id', 'content_type']]


def filter_consultation_notes(df):
    """Filter for ALL Consultation Notes with HTML preference."""
    print("\n[5/7] Filtering Consultation Notes...")
    
    # Get all Consult Notes
    consult = df[df['document_type'] == 'Consult Note'].copy()
    
    # Prefer HTML format
    consult['has_html'] = consult['content_type'].str.contains('text/html', na=False)
    consult = consult.sort_values(['has_html', 'document_date'], ascending=[False, False])
    
    print(f"  ✓ Selected {len(consult)} Consultation Notes")
    return consult[['document_reference_id', 'document_type', 'document_date', 'binary_id', 'content_type']]


def filter_event_based_imaging(df):
    """Filter for event-based imaging tied to surgeries and therapies."""
    print("\n[6/7] Filtering Event-Based Imaging...")
    
    # Get all imaging studies with HTML
    imaging = df[
        (df['document_type'].str.contains('MR|CT|Diagnostic imaging', case=False, na=False)) &
        (df['content_type'].str.contains('text/html', na=False))
    ].copy()
    
    # Convert document_date to datetime (keeping timezone info)
    imaging['doc_datetime'] = pd.to_datetime(imaging['document_date'])
    
    # Convert reference dates to pandas Timestamp with same timezone
    surgery1_dt = pd.to_datetime(SURGERY_1_DATE)
    surgery2_dt = pd.to_datetime(SURGERY_2_DATE)
    vinb_start_dt = pd.to_datetime(VINBLASTINE_START)
    vinb_end_dt = pd.to_datetime(VINBLASTINE_END)
    surv_start_dt = pd.to_datetime(SURVEILLANCE_START)
    surv_end_dt = pd.to_datetime(SURVEILLANCE_END)
    
    # Make timezone-aware if needed
    if imaging['doc_datetime'].dt.tz is not None:
        surgery1_dt = surgery1_dt.tz_localize('UTC')
        surgery2_dt = surgery2_dt.tz_localize('UTC')
        vinb_start_dt = vinb_start_dt.tz_localize('UTC')
        vinb_end_dt = vinb_end_dt.tz_localize('UTC')
        surv_start_dt = surv_start_dt.tz_localize('UTC')
        surv_end_dt = surv_end_dt.tz_localize('UTC')
    
    selected_imaging = []
    
    # Surgery 1 (May 28, 2018) - 2 pre, 2 post
    pre_surgery1 = imaging[
        (imaging['doc_datetime'] >= surgery1_dt - pd.Timedelta(days=8)) &
        (imaging['doc_datetime'] < surgery1_dt)
    ].nsmallest(2, 'doc_datetime')
    selected_imaging.append(pre_surgery1)
    
    post_surgery1 = imaging[
        (imaging['doc_datetime'] >= surgery1_dt) &
        (imaging['doc_datetime'] <= surgery1_dt + pd.Timedelta(days=13))
    ].nsmallest(2, 'doc_datetime')
    selected_imaging.append(post_surgery1)
    
    # Surgery 2 (March 10, 2021) - 2 pre, 2 post
    pre_surgery2 = imaging[
        (imaging['doc_datetime'] >= surgery2_dt - pd.Timedelta(days=7)) &
        (imaging['doc_datetime'] < surgery2_dt)
    ].nsmallest(2, 'doc_datetime')
    selected_imaging.append(pre_surgery2)
    
    post_surgery2 = imaging[
        (imaging['doc_datetime'] >= surgery2_dt) &
        (imaging['doc_datetime'] <= surgery2_dt + pd.Timedelta(days=15))
    ].nsmallest(2, 'doc_datetime')
    selected_imaging.append(post_surgery2)
    
    # Vinblastine therapy period - 2-3 studies during treatment
    therapy_imaging = imaging[
        (imaging['doc_datetime'] >= vinb_start_dt) &
        (imaging['doc_datetime'] <= vinb_end_dt)
    ].nsmallest(3, 'doc_datetime')
    selected_imaging.append(therapy_imaging)
    
    # Recent surveillance - 6 most recent
    surveillance = imaging[
        (imaging['doc_datetime'] >= surv_start_dt) &
        (imaging['doc_datetime'] <= surv_end_dt)
    ].nlargest(6, 'doc_datetime')
    selected_imaging.append(surveillance)
    
    # Combine and remove duplicates
    result = pd.concat(selected_imaging, ignore_index=True).drop_duplicates(subset=['document_reference_id'])
    
    print(f"  ✓ Selected {len(result)} Event-Based Imaging studies")
    print(f"    - Surgery 1 events: {len(pre_surgery1) + len(post_surgery1)}")
    print(f"    - Surgery 2 events: {len(pre_surgery2) + len(post_surgery2)}")
    print(f"    - Therapy period: {len(therapy_imaging)}")
    print(f"    - Recent surveillance: {len(surveillance)}")
    
    return result[['document_reference_id', 'document_type', 'document_date', 'binary_id', 'content_type']]


def retrieve_binary_content(s3_client, binary_id):
    """
    Retrieve Binary content from S3.
    
    Args:
        s3_client: Boto3 S3 client
        binary_id: FHIR Binary ID (format: Binary/xxx)
    
    Returns:
        str: Decoded content or None if error
    """
    # Remove "Binary/" prefix if present
    if binary_id.startswith('Binary/'):
        s3_binary_id = binary_id[7:]  # Remove "Binary/" prefix
    else:
        s3_binary_id = binary_id
    
    # Simple period-to-underscore conversion (matching query_accessible_binaries.py)
    s3_binary_id = s3_binary_id.replace('.', '_')
    
    s3_key = f"{S3_PREFIX}{s3_binary_id}"
    
    try:
        # Get object from S3
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = response['Body'].read()
        
        # Parse JSON
        binary_data = json.loads(content)
        
        # Decode base64 content from 'data' field (not 'content')
        if 'data' in binary_data:
            decoded = base64.b64decode(binary_data['data']).decode('utf-8', errors='ignore')
            return decoded
        else:
            return None
            
    except Exception as e:
        print(f"  ✗ Error retrieving {binary_id}: {str(e)}")
        return None


def extract_text_from_html(html_content):
    """
    Extract plain text from HTML content.
    
    Args:
        html_content: HTML string
    
    Returns:
        str: Extracted plain text
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        print(f"  ✗ Error extracting HTML text: {str(e)}")
        return html_content  # Return raw content if parsing fails


def extract_text_from_rtf(rtf_content):
    """
    Extract plain text from RTF content (basic extraction).
    
    Args:
        rtf_content: RTF string
    
    Returns:
        str: Extracted plain text
    """
    # Basic RTF stripping - remove control words
    text = re.sub(r'\\[a-z]+\d*\s?', '', rtf_content)
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def download_and_extract_documents(s3_client, selected_docs):
    """
    Download Binary documents from S3 and extract text.
    
    Args:
        s3_client: Boto3 S3 client
        selected_docs: DataFrame with selected documents
    
    Returns:
        DataFrame: Documents with extracted text
    """
    print("\n[7/7] Downloading and extracting Binary content from S3...")
    
    results = []
    total = len(selected_docs)
    errors = 0
    
    for idx, row in selected_docs.iterrows():
        if (idx + 1) % 50 == 0:
            print(f"  Progress: {idx + 1}/{total} documents ({(idx + 1) / total * 100:.1f}%)")
        
        # Retrieve Binary content
        content = retrieve_binary_content(s3_client, row['binary_id'])
        
        if content is None:
            errors += 1
            continue
        
        # Extract text based on content type
        if 'text/html' in str(row['content_type']):
            note_text = extract_text_from_html(content)
        elif 'text/rtf' in str(row['content_type']):
            note_text = extract_text_from_rtf(content)
        else:
            note_text = content  # Use raw content for other types
        
        # Store result
        results.append({
            'NOTE_ID': row['document_reference_id'],
            'SUBJECT_ID': PATIENT_ID,
            'NOTE_DATETIME': row['document_date'],
            'NOTE_TEXT': note_text,
            'DOCUMENT_TYPE': row['document_type']
        })
    
    print(f"\n  ✓ Successfully retrieved {len(results)} documents")
    if errors > 0:
        print(f"  ⚠ Failed to retrieve {errors} documents")
    
    return pd.DataFrame(results)


def main():
    """Main execution."""
    print("=" * 80)
    print("BINARY DOCUMENT RETRIEVAL FOR BRIM EXTRACTION")
    print("=" * 80)
    print(f"Patient: {PATIENT_ID}")
    print(f"S3 Bucket: {S3_BUCKET}")
    print(f"Expected documents: ~1,385-1,389")
    print("=" * 80)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    input_csv = base_dir / 'pilot_output' / 'brim_csvs_iteration_3c_phase3a_v2' / 'accessible_binary_files_annotated.csv'
    output_csv = base_dir / 'pilot_output' / 'brim_csvs_iteration_3c_phase3a_v2' / 'retrieved_binary_documents.csv'
    
    # Load annotated files
    df = load_annotated_files(input_csv)
    
    # Filter document categories
    progress_notes = filter_progress_notes(df)
    hp_notes = filter_hp_notes(df)
    operative_notes = filter_operative_notes(df)
    consultation_notes = filter_consultation_notes(df)
    imaging = filter_event_based_imaging(df)
    
    # Combine all selected documents
    selected_docs = pd.concat([
        progress_notes,
        hp_notes,
        operative_notes,
        consultation_notes,
        imaging
    ], ignore_index=True)
    
    print(f"\n{'=' * 80}")
    print(f"TOTAL SELECTED DOCUMENTS: {len(selected_docs)}")
    print(f"{'=' * 80}")
    print(f"  - Progress Notes: {len(progress_notes)}")
    print(f"  - H&P: {len(hp_notes)}")
    print(f"  - Operative Notes: {len(operative_notes)}")
    print(f"  - Consultation Notes: {len(consultation_notes)}")
    print(f"  - Event-Based Imaging: {len(imaging)}")
    print(f"{'=' * 80}")
    
    # Setup AWS
    s3_client = setup_aws_session()
    
    # Download and extract documents
    extracted_docs = download_and_extract_documents(s3_client, selected_docs)
    
    # Save results
    print(f"\nSaving results to {output_csv}...")
    extracted_docs.to_csv(output_csv, index=False)
    print(f"  ✓ Saved {len(extracted_docs)} documents")
    
    # Summary statistics
    print(f"\n{'=' * 80}")
    print("RETRIEVAL SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total documents selected: {len(selected_docs)}")
    print(f"Total documents retrieved: {len(extracted_docs)}")
    print(f"Success rate: {len(extracted_docs) / len(selected_docs) * 100:.1f}%")
    print(f"\nOutput saved to: {output_csv}")
    print(f"{'=' * 80}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
