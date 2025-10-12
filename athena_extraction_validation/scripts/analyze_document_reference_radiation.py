#!/usr/bin/env python3
"""
Analyze DocumentReference tables for radiation-related external documents.

This script specifically looks for radiation therapy documents from outside institutions
that may be in non-HTML/RTF formats (PDFs, DICOM, images, etc.).

Focus areas:
1. Content types (MIME types) - PDF, DICOM, images
2. Document categories and types - radiation, treatment summaries
3. Context - facility types, practice settings
4. Related encounters and events

Author: Clinical Data Extraction Team
Date: 2025-10-12
"""

import boto3
import time
import pandas as pd
from collections import Counter
import json

# Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
REGION = 'us-east-1'
DATABASE = 'fhir_prd_db'
S3_OUTPUT = 's3://aws-athena-query-results-343218191717-us-east-1/'

# RT-specific keywords
RT_KEYWORDS = [
    'radiation', 'radiotherapy', 'rad onc', 'radonc', 'xrt', 'imrt', 'vmat',
    'proton', 'photon', 'electron', 'brachytherapy', 'hdr', 'ldr',
    'stereotactic', 'sbrt', 'srs', 'radiosurgery', 'beam', 'dose', 'gy',
    'fraction', 'treatment planning', 'simulation', 'external beam'
]

# Test patient IDs with known RT
TEST_PATIENTS = [
    'eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3',
    'emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3'
]

def execute_query(athena_client, query):
    """Execute Athena query and return results."""
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': S3_OUTPUT}
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait for query completion
        max_wait = 60
        waited = 0
        while waited < max_wait:
            status = athena_client.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            
            if state == 'SUCCEEDED':
                break
            elif state in ['FAILED', 'CANCELLED']:
                reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                print(f"Query failed: {reason}")
                return None
            
            time.sleep(2)
            waited += 2
        
        if waited >= max_wait:
            print(f"Query timed out after {max_wait} seconds")
            return None
        
        result = athena_client.get_query_results(QueryExecutionId=query_id)
        return result
        
    except Exception as e:
        print(f"Error executing query: {str(e)}")
        return None


def analyze_document_reference_content(athena_client, patient_ids):
    """Analyze document_reference_content for MIME types and attachment info."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: document_reference_content (MIME types, formats)")
    print(f"{'='*80}")
    
    patient_list = "', '".join(patient_ids)
    
    query = f"""
    SELECT 
        parent.id as document_id,
        parent.status,
        parent.doc_status,
        parent.date as doc_date,
        parent.description,
        content.content_attachment_content_type,
        content.content_attachment_url,
        content.content_attachment_size,
        content.content_attachment_title,
        content.content_format_system,
        content.content_format_code,
        content.content_format_display
    FROM {DATABASE}.document_reference_content content
    JOIN {DATABASE}.document_reference parent ON content.document_reference_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result or len(result['ResultSet']['Rows']) <= 1:
        print("❌ No document content found")
        return
    
    # Parse results
    columns = [col['Name'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in result['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    print(f"Total documents: {len(df)}")
    
    # Analyze MIME types
    print(f"\nMIME Type Distribution:")
    mime_counts = df['content_attachment_content_type'].value_counts()
    for mime, count in mime_counts.head(20).items():
        print(f"  {mime:50} {count:5}")
    
    # Focus on non-HTML/RTF formats
    non_html_rtf = df[
        ~df['content_attachment_content_type'].str.contains('html|rtf', case=False, na=False)
    ]
    print(f"\n📄 Non-HTML/RTF documents: {len(non_html_rtf)} ({len(non_html_rtf)/len(df)*100:.1f}%)")
    
    if len(non_html_rtf) > 0:
        print("\nNon-HTML/RTF MIME types:")
        for mime, count in non_html_rtf['content_attachment_content_type'].value_counts().head(10).items():
            print(f"  {mime:50} {count:5}")
    
    # Check for RT-related documents by description/title
    rt_docs = []
    for idx, row in df.iterrows():
        text = f"{row['description']} {row['content_attachment_title']}".lower()
        if any(keyword in text for keyword in RT_KEYWORDS):
            rt_docs.append(row)
    
    if rt_docs:
        rt_df = pd.DataFrame(rt_docs)
        print(f"\n☢️  RT-related documents (by description/title): {len(rt_df)}")
        print("\nRT Document Details:")
        for idx, row in rt_df.iterrows():
            print(f"\n  Document ID: {row['document_id']}")
            print(f"  MIME Type: {row['content_attachment_content_type']}")
            print(f"  Title: {row['content_attachment_title']}")
            print(f"  Description: {row['description'][:100] if row['description'] else 'N/A'}")
            print(f"  Size: {row['content_attachment_size']} bytes")
            print(f"  Date: {row['doc_date']}")
    
    return df


def analyze_document_reference_type(athena_client, patient_ids):
    """Analyze document_reference_type_coding for radiation-related document types."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: document_reference_type_coding (document classifications)")
    print(f"{'='*80}")
    
    patient_list = "', '".join(patient_ids)
    
    query = f"""
    SELECT 
        parent.id as document_id,
        parent.status,
        parent.date as doc_date,
        parent.description,
        type_code.type_coding_code,
        type_code.type_coding_display,
        type_code.type_coding_system
    FROM {DATABASE}.document_reference_type_coding type_code
    JOIN {DATABASE}.document_reference parent ON type_code.document_reference_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result or len(result['ResultSet']['Rows']) <= 1:
        print("❌ No document type codes found")
        return
    
    # Parse results
    columns = [col['Name'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in result['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    print(f"Total document type codes: {len(df)}")
    
    # Check for RT-related type codes
    pattern = '|'.join(RT_KEYWORDS)
    rt_types = df[
        df['type_coding_display'].str.contains(pattern, case=False, na=False, regex=True) |
        df['type_coding_code'].str.contains(pattern, case=False, na=False, regex=True) |
        df['description'].str.contains(pattern, case=False, na=False, regex=True)
    ]
    
    print(f"\n☢️  RT-related document types: {len(rt_types)} ({len(rt_types)/len(df)*100:.1f}%)")
    
    if len(rt_types) > 0:
        print("\nMost Common RT Document Type Codes:")
        for display, count in rt_types['type_coding_display'].value_counts().head(10).items():
            print(f"  {display:60} {count:3}")
    
    return df


def analyze_document_reference_category(athena_client, patient_ids):
    """Analyze document_reference_category for radiation-related categories."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: document_reference_category (document categories)")
    print(f"{'='*80}")
    
    patient_list = "', '".join(patient_ids)
    
    query = f"""
    SELECT 
        parent.id as document_id,
        parent.date as doc_date,
        category.category_coding_code,
        category.category_coding_display,
        category.category_coding_system
    FROM {DATABASE}.document_reference_category category
    JOIN {DATABASE}.document_reference parent ON category.document_reference_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result or len(result['ResultSet']['Rows']) <= 1:
        print("❌ No document categories found")
        return
    
    # Parse results
    columns = [col['Name'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in result['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    print(f"Total document categories: {len(df)}")
    
    print(f"\nCategory Distribution:")
    for display, count in df['category_coding_display'].value_counts().head(20).items():
        print(f"  {display:60} {count:3}")
    
    # Check for RT-related categories
    pattern = '|'.join(RT_KEYWORDS)
    rt_categories = df[
        df['category_coding_display'].str.contains(pattern, case=False, na=False, regex=True) |
        df['category_coding_code'].str.contains(pattern, case=False, na=False, regex=True)
    ]
    
    print(f"\n☢️  RT-related categories: {len(rt_categories)} ({len(rt_categories)/len(df)*100:.1f}%)")
    
    return df


def analyze_document_reference_facility(athena_client, patient_ids):
    """Analyze facility_type to identify external/outside institutions."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: document_reference_context_facility_type_coding (outside facilities)")
    print(f"{'='*80}")
    
    patient_list = "', '".join(patient_ids)
    
    query = f"""
    SELECT 
        parent.id as document_id,
        parent.date as doc_date,
        parent.description,
        facility.context_facility_type_coding_code,
        facility.context_facility_type_coding_display,
        facility.context_facility_type_coding_system
    FROM {DATABASE}.document_reference_context_facility_type_coding facility
    JOIN {DATABASE}.document_reference parent ON facility.document_reference_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result or len(result['ResultSet']['Rows']) <= 1:
        print("❌ No facility type codes found")
        return
    
    # Parse results
    columns = [col['Name'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in result['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    print(f"Total documents with facility info: {len(df)}")
    
    print(f"\nFacility Type Distribution:")
    for display, count in df['context_facility_type_coding_display'].value_counts().head(20).items():
        print(f"  {display:60} {count:3}")
    
    # Look for external/outside facility indicators
    external_keywords = ['external', 'outside', 'community', 'referring', 'other']
    external_pattern = '|'.join(external_keywords)
    
    external_docs = df[
        df['context_facility_type_coding_display'].str.contains(external_pattern, case=False, na=False, regex=True) |
        df['context_facility_type_coding_code'].str.contains(external_pattern, case=False, na=False, regex=True)
    ]
    
    print(f"\n🏥 External facility documents: {len(external_docs)} ({len(external_docs)/len(df)*100:.1f}%)")
    
    return df


def analyze_document_reference_practice_setting(athena_client, patient_ids):
    """Analyze practice_setting to identify radiation oncology settings."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: document_reference_context_practice_setting_coding (radiation oncology)")
    print(f"{'='*80}")
    
    patient_list = "', '".join(patient_ids)
    
    query = f"""
    SELECT 
        parent.id as document_id,
        parent.date as doc_date,
        parent.description,
        setting.context_practice_setting_coding_code,
        setting.context_practice_setting_coding_display,
        setting.context_practice_setting_coding_system
    FROM {DATABASE}.document_reference_context_practice_setting_coding setting
    JOIN {DATABASE}.document_reference parent ON setting.document_reference_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result or len(result['ResultSet']['Rows']) <= 1:
        print("❌ No practice setting codes found")
        return
    
    # Parse results
    columns = [col['Name'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in result['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    print(f"Total documents with practice setting: {len(df)}")
    
    print(f"\nPractice Setting Distribution:")
    for display, count in df['context_practice_setting_coding_display'].value_counts().head(20).items():
        print(f"  {display:60} {count:3}")
    
    # Check for RT-related practice settings
    pattern = '|'.join(RT_KEYWORDS + ['oncology', 'hematology'])
    rt_settings = df[
        df['context_practice_setting_coding_display'].str.contains(pattern, case=False, na=False, regex=True) |
        df['context_practice_setting_coding_code'].str.contains(pattern, case=False, na=False, regex=True)
    ]
    
    print(f"\n☢️  RT-related practice settings: {len(rt_settings)} ({len(rt_settings)/len(df)*100:.1f}%)")
    
    if len(rt_settings) > 0:
        print("\nRT Practice Settings Found:")
        for display, count in rt_settings['context_practice_setting_coding_display'].value_counts().items():
            print(f"  {display:60} {count:3}")
    
    return df


def main():
    """Main analysis workflow."""
    print("="*80)
    print("DOCUMENT REFERENCE ANALYSIS - RADIATION THERAPY EXTERNAL DOCUMENTS")
    print("="*80)
    print(f"\nFocus: Non-HTML/RTF documents from outside institutions")
    print(f"Test Patients: {len(TEST_PATIENTS)}")
    for pid in TEST_PATIENTS:
        print(f"  - {pid}")
    
    # Initialize AWS session
    try:
        session = boto3.Session(profile_name=AWS_PROFILE)
        athena = session.client('athena', region_name=REGION)
        print("\n✅ AWS session initialized")
    except Exception as e:
        print(f"\n❌ Failed to initialize AWS session: {e}")
        return
    
    # Run analyses
    print("\n" + "="*80)
    print("STARTING ANALYSIS")
    print("="*80)
    
    # 1. Content analysis (MIME types)
    content_df = analyze_document_reference_content(athena, TEST_PATIENTS)
    
    # 2. Document type analysis
    type_df = analyze_document_reference_type(athena, TEST_PATIENTS)
    
    # 3. Category analysis
    category_df = analyze_document_reference_category(athena, TEST_PATIENTS)
    
    # 4. Facility analysis (external institutions)
    facility_df = analyze_document_reference_facility(athena, TEST_PATIENTS)
    
    # 5. Practice setting analysis (radiation oncology)
    setting_df = analyze_document_reference_practice_setting(athena, TEST_PATIENTS)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
