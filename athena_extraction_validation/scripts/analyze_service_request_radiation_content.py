#!/usr/bin/env python3
"""
Analyze service_request tables for radiation-related content.

Uses UNNEST to properly query array/struct columns in Athena.
Focus on high-priority tables with radiation-related content.
NO PATIENT ID LEAKAGE - aggregated analysis only.
"""

import boto3
import time
from datetime import datetime
from collections import Counter

# Configuration
DATABASE = 'fhir_prd_db'
OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Test patients (2 with RT, 2 without)
TEST_PATIENTS = [
    'eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3',  # Has RT
    'emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3',  # Has RT
    'eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',  # No RT
    'enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3'   # No RT
]

# Radiation therapy SPECIFIC keywords (excluding general oncology terms)
RADIATION_SPECIFIC_KEYWORDS = [
    # Radiation therapy general
    'radiation', 'radiotherapy', 'xrt', 'rt ', 'rad onc', 'radiation oncology',
    
    # Radiation modalities
    'imrt', 'vmat', '3d-crt', '3dcrt', 'proton', 'photon', 'electron',
    'brachytherapy', 'hdr', 'ldr', 'seed implant',
    
    # Stereotactic techniques
    'stereotactic', 'sbrt', 'srs', 'sabr', 'radiosurgery',
    'gamma knife', 'gammaknife', 'cyberknife',
    
    # Radiation-specific terms
    'beam', 'teletherapy', 'external beam', 'conformal', 
    'dose', 'dosage', 'gy', 'gray', 'cgy', 'centigray',
    'fraction', 'fractions', 'fractionation',
    'isocenter', 'planning target', 'ptv', 'gtv', 'ctv',
    'treatment planning', 'simulation', 'port film',
    'linac', 'linear accelerator', 'cyclotron',
    'boost', 'field', 'portal'
]

# General oncology keywords (for comparison - not used for RT-specific analysis)
GENERAL_ONCOLOGY_KEYWORDS = [
    'oncology', 'tumor', 'cancer', 'neoplasm', 'malignancy', 'metastasis'
]

def execute_query(athena_client, query):
    """Execute Athena query and return results."""
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait for query completion
        max_wait = 60
        elapsed = 0
        while elapsed < max_wait:
            status = athena_client.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(1)
            elapsed += 1
        
        if state != 'SUCCEEDED':
            reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"Query failed: {reason}")
            return None
        
        result = athena_client.get_query_results(QueryExecutionId=query_id)
        return result
        
    except Exception as e:
        print(f"Error executing query: {str(e)}")
        return None

def analyze_service_request_note(athena_client, patient_ids):
    """Analyze service_request_note for radiation-related content."""
    print(f"\n{'='*133}")
    print(f"ANALYZING: service_request_note")
    print(f"{'='*133}")
    
    patient_list = "', '".join(patient_ids)
    
    # Query service_request_note with JOIN to parent
    query = f"""
    SELECT note.note_text
    FROM {DATABASE}.service_request_note note
    JOIN {DATABASE}.service_request parent ON note.service_request_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result:
        print("❌ Query failed")
        return
    
    rows = result['ResultSet']['Rows'][1:]  # Skip header
    print(f"Total notes retrieved: {len(rows)}")
    
    if not rows:
        print("No notes found")
        return
    
    # Analyze notes for radiation keywords
    radiation_notes = []
    keyword_counts = Counter()
    
    for row in rows:
        if not row['Data'] or not row['Data'][0].get('VarCharValue'):
            continue
            
        note_text = row['Data'][0]['VarCharValue'].lower()
        
        # Check for radiation-specific keywords
        found_keywords = []
        for keyword in RADIATION_SPECIFIC_KEYWORDS:
            if keyword in note_text:
                found_keywords.append(keyword)
                keyword_counts[keyword] += 1
        
        if found_keywords:
            radiation_notes.append({
                'text': note_text[:200],  # Truncate for display
                'keywords': found_keywords
            })
    
    # Print summary
    print(f"\n📊 RADIATION-RELATED NOTES: {len(radiation_notes)}/{len(rows)}")
    if rows:
        print(f"   Hit rate: {len(radiation_notes)/len(rows)*100:.1f}%")
    
    print(f"\n🔍 Top 15 Keywords:")
    for keyword, count in keyword_counts.most_common(15):
        print(f"   {keyword:<25} {count:>4} occurrences")
    
    if radiation_notes:
        print(f"\n📝 Sample radiation notes (first 5, truncated, NO patient IDs):\n")
        for i, note in enumerate(radiation_notes[:5], 1):
            print(f"   Note {i}:")
            print(f"   Keywords: {', '.join(note['keywords'][:10])}")
            print(f"   Text: {note['text'][:150]}...")
            print()

def analyze_service_request_reason_code(athena_client, patient_ids):
    """Analyze service_request_reason_code for radiation-SPECIFIC content."""
    print(f"\n{'='*133}")
    print(f"ANALYZING: service_request_reason_code (RADIATION-SPECIFIC KEYWORDS ONLY)")
    print(f"{'='*133}")
    
    patient_list = "', '".join(patient_ids)
    
    # Query reason codes (reason_code_coding is JSON string, reason_code_text is plain text)
    # We'll parse in Python since Athena JSON parsing is complex
    query = f"""
    SELECT 
        reason.reason_code_coding,
        reason.reason_code_text
    FROM {DATABASE}.service_request_reason_code reason
    JOIN {DATABASE}.service_request parent ON reason.service_request_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result:
        print("❌ Query failed")
        return
    
    rows = result['ResultSet']['Rows'][1:]  # Skip header
    print(f"Total reason codes retrieved: {len(rows)}")
    
    if not rows:
        print("No reason codes found")
        return
    
    # Analyze for RADIATION-SPECIFIC keywords (not general oncology)
    radiation_reasons = []
    keyword_counts = Counter()
    
    import json
    for row in rows:
        if len(row['Data']) < 2:
            continue
            
        coding_json = row['Data'][0].get('VarCharValue', '')
        text = row['Data'][1].get('VarCharValue', '')
        
        # Parse JSON coding array
        try:
            codings = json.loads(coding_json.replace("'", '"')) if coding_json else []
        except:
            codings = []
        
        # Check text and all coding displays for RADIATION-SPECIFIC keywords
        combined_text = text.lower() if text else ''
        for coding in codings:
            if isinstance(coding, dict):
                combined_text += ' ' + coding.get('display', '').lower()
                combined_text += ' ' + coding.get('code', '').lower()
        
        found_keywords = []
        for keyword in RADIATION_SPECIFIC_KEYWORDS:
            if keyword in combined_text:
                found_keywords.append(keyword)
                keyword_counts[keyword] += 1
        
        if found_keywords:
            # Get first coding for display
            primary_coding = codings[0] if codings else {}
            radiation_reasons.append({
                'code': primary_coding.get('code', ''),
                'display': primary_coding.get('display', ''),
                'text': text,
                'num_codings': len(codings),
                'keywords': found_keywords
            })
    
    # Print summary
    print(f"\n📊 RADIATION-RELATED REASON CODES: {len(radiation_reasons)}/{len(rows)}")
    if rows:
        print(f"   Hit rate: {len(radiation_reasons)/len(rows)*100:.1f}%")
    
    print(f"\n🔍 Top 10 Keywords:")
    for keyword, count in keyword_counts.most_common(10):
        print(f"   {keyword:<25} {count:>4} occurrences")
    
    if radiation_reasons:
        print(f"\n📝 Sample radiation reason codes (first 5, NO patient IDs):\n")
        for i, reason in enumerate(radiation_reasons[:5], 1):
            print(f"   Reason {i}:")
            print(f"   Code: {reason['code']}")
            print(f"   Display: {reason['display'][:100]}")
            print(f"   Text: {reason['text'][:100] if reason['text'] else 'N/A'}")
            print(f"   Keywords: {', '.join(reason['keywords'][:5])}")
            print(f"   Number of codings: {reason['num_codings']}")
            print()

def analyze_service_request_category(athena_client, patient_ids):
    """Analyze service_request_category for radiation-SPECIFIC categories."""
    print(f"\n{'='*133}")
    print(f"ANALYZING: service_request_category (RADIATION-SPECIFIC KEYWORDS ONLY)")
    print(f"{'='*133}")
    
    patient_list = "', '".join(patient_ids)
    
    # Query categories (category_coding is JSON string, category_text is plain text)
    query = f"""
    SELECT 
        cat.category_coding,
        cat.category_text
    FROM {DATABASE}.service_request_category cat
    JOIN {DATABASE}.service_request parent ON cat.service_request_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    result = execute_query(athena_client, query)
    if not result:
        print("❌ Query failed")
        return
    
    rows = result['ResultSet']['Rows'][1:]  # Skip header
    print(f"Total categories retrieved: {len(rows)}")
    
    if not rows:
        print("No categories found")
        return
    
    # Analyze for RADIATION-SPECIFIC keywords (not general oncology)
    radiation_categories = []
    keyword_counts = Counter()
    
    import json
    for row in rows:
        if len(row['Data']) < 2:
            continue
            
        coding_json = row['Data'][0].get('VarCharValue', '')
        text = row['Data'][1].get('VarCharValue', '')
        
        # Parse JSON coding array
        try:
            codings = json.loads(coding_json.replace("'", '"')) if coding_json else []
        except:
            codings = []
        
        # Check text and all coding displays for RADIATION-SPECIFIC keywords
        combined_text = text.lower() if text else ''
        for coding in codings:
            if isinstance(coding, dict):
                combined_text += ' ' + coding.get('display', '').lower()
                combined_text += ' ' + coding.get('code', '').lower()
        
        found_keywords = []
        for keyword in RADIATION_SPECIFIC_KEYWORDS:
            if keyword in combined_text:
                found_keywords.append(keyword)
                keyword_counts[keyword] += 1
        
        if found_keywords:
            # Get first coding for display
            primary_coding = codings[0] if codings else {}
            radiation_categories.append({
                'code': primary_coding.get('code', ''),
                'display': primary_coding.get('display', ''),
                'text': text,
                'num_codings': len(codings),
                'keywords': found_keywords
            })
    
    # Print summary
    print(f"\n📊 RADIATION-RELATED CATEGORIES: {len(radiation_categories)}/{len(rows)}")
    if rows:
        print(f"   Hit rate: {len(radiation_categories)/len(rows)*100:.1f}%")
    
    print(f"\n🔍 Top 10 Keywords:")
    for keyword, count in keyword_counts.most_common(10):
        print(f"   {keyword:<25} {count:>4} occurrences")
    
    if radiation_categories:
        print(f"\n📝 Sample radiation categories (first 5, NO patient IDs):\n")
        for i, cat in enumerate(radiation_categories[:5], 1):
            print(f"   Category {i}:")
            print(f"   Code: {cat['code']}")
            print(f"   Display: {cat['display'][:100]}")
            print(f"   Text: {cat['text'][:100] if cat['text'] else 'N/A'}")
            print(f"   Keywords: {', '.join(cat['keywords'][:5])}")
            print(f"   Number of codings: {cat['num_codings']}")
            print()

def main():
    """Main execution."""
    print("="*133)
    print(" " * 50 + "SERVICE REQUEST RADIATION CONTENT ANALYSIS")
    print(f"Database: {DATABASE}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*133)
    
    print("\nAnalyzing high-priority tables with data:")
    print("  1. service_request_note (1,638 records)")
    print("  2. service_request_reason_code (791 records)")
    print("  3. service_request_category (3,649 records)")
    print("\nNO PATIENT IDs WILL BE DISPLAYED")
    print("="*133)
    
    # Initialize Athena client
    athena_client = boto3.client('athena', region_name='us-east-1')
    
    # Analyze each table
    analyze_service_request_note(athena_client, TEST_PATIENTS)
    analyze_service_request_reason_code(athena_client, TEST_PATIENTS)
    analyze_service_request_category(athena_client, TEST_PATIENTS)
    
    print("\n" + "="*133)
    print("ANALYSIS COMPLETE")
    print("="*133)

if __name__ == "__main__":
    main()
