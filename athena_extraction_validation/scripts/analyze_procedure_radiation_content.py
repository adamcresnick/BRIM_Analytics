#!/usr/bin/env python3
"""
Analyze Procedure Tables for Radiation Therapy Content

This script analyzes procedure-related tables for RT-specific content using:
- RT-specific keywords (not general oncology terms)
- CPT codes for radiation oncology procedures
- SNOMED codes for RT procedures
- Procedure text fields (code_text, outcome_text, notes)

Tables analyzed:
- procedure (parent)
- procedure_code_coding (CPT/SNOMED codes)
- procedure_note (procedure notes/documentation)
- procedure_reason_code (indication codes)
- procedure_body_site (anatomical sites)
- procedure_performer (provider information)

Author: Clinical Data Extraction Team
Date: 2025-10-12
"""

import boto3
import time
import json
from collections import Counter

# Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
REGION = 'us-east-1'
DATABASE = 'fhir_prd_db'
S3_OUTPUT = 's3://aws-athena-query-results-343218191717-us-east-1/'

# RT-SPECIFIC Keywords (same as extraction script)
RADIATION_SPECIFIC_KEYWORDS = [
    # Core RT terms
    'radiation', 'radiotherapy', 'rad onc', 'rad-onc', 'radonc', 'radiation oncology',
    # Modalities & abbreviations
    'xrt', 'imrt', 'vmat', '3d-crt', '3dcrt',
    'proton', 'photon', 'electron',
    'brachytherapy', 'hdr', 'ldr', 'seed implant',
    # Stereotactic
    'stereotactic', 'sbrt', 'srs', 'sabr', 'radiosurgery',
    'gamma knife', 'cyberknife',
    # Delivery & planning
    'beam', 'external beam', 'teletherapy', 'conformal',
    'intensity modulated', 'volumetric modulated',
    # Treatment phases
    'rt simulation', 'rt sim', 'simulation',
    're-irradiation', 'reirradiation', 'boost',
    # Dosimetry
    'dose', 'dosage', 'gy', 'gray', 'cgy', 'centigray',
    'fraction', 'fractions', 'fractionation',
    # Technical terms
    'isocenter', 'ptv', 'gtv', 'ctv', 'planning target',
    'treatment planning', 'port film', 'portal',
    'linac', 'linear accelerator', 'cyclotron',
]

# CPT Code ranges for Radiation Oncology (77xxx series)
RT_CPT_PREFIXES = [
    '770', '771', '772', '773', '774', '775', '776', '777', '778', '779'
]


def execute_athena_query(athena_client, query, max_wait=180):
    """Execute Athena query and wait for results."""
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': S3_OUTPUT}
        )
        
        query_id = response['QueryExecutionId']
        
        for _ in range(max_wait):
            status_result = athena_client.get_query_execution(QueryExecutionId=query_id)
            state = status_result['QueryExecution']['Status']['State']
            
            if state == 'SUCCEEDED':
                return athena_client.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
            elif state in ['FAILED', 'CANCELLED']:
                reason = status_result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                print(f"    ❌ Query failed: {reason}")
                return None
            
            time.sleep(1)
        
        print(f"    ⏱️  Query timeout")
        return None
        
    except Exception as e:
        print(f"    ❌ Error: {str(e)}")
        return None


def analyze_procedure_parent():
    """Analyze procedure parent table for RT content in text fields."""
    print("\n" + "="*80)
    print("ANALYZING: procedure (parent table)")
    print("="*80)
    
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    athena = session.client('athena')
    
    # Query text fields
    query = f"""
    SELECT 
        id,
        code_text,
        outcome_text,
        category_text,
        status,
        performed_date_time,
        performed_period_start
    FROM {DATABASE}.procedure
    WHERE code_text IS NOT NULL 
       OR outcome_text IS NOT NULL
       OR category_text IS NOT NULL
    """
    
    print("\nQuerying procedure text fields...")
    results = execute_athena_query(athena, query)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No text data found.")
        return
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    print(f"Total procedures with text: {len(data)}")
    
    # Check for RT keywords
    rt_matches = []
    keyword_hits = Counter()
    
    for row in data:
        row_dict = dict(zip(columns, row))
        combined_text = ' '.join([
            row_dict.get('code_text', ''),
            row_dict.get('outcome_text', ''),
            row_dict.get('category_text', '')
        ]).lower()
        
        # Check each keyword
        found_keywords = []
        for keyword in RADIATION_SPECIFIC_KEYWORDS:
            if keyword in combined_text:
                found_keywords.append(keyword)
                keyword_hits[keyword] += 1
        
        if found_keywords:
            rt_matches.append({
                'id': row_dict['id'],
                'keywords': found_keywords,
                'code_text': row_dict.get('code_text', '')[:100],
                'performed': row_dict.get('performed_date_time') or row_dict.get('performed_period_start')
            })
    
    # Results
    hit_rate = (len(rt_matches) / len(data) * 100) if data else 0
    print(f"\n✅ RT-SPECIFIC Hit Rate: {len(rt_matches)}/{len(data)} ({hit_rate:.1f}%)")
    
    if keyword_hits:
        print("\nTop RT Keywords Found:")
        for keyword, count in keyword_hits.most_common(15):
            print(f"  {keyword:30} {count:4} hits")
    
    if rt_matches:
        print(f"\nSample RT Procedures ({min(5, len(rt_matches))}):")
        for match in rt_matches[:5]:
            print(f"\n  ID: {match['id']}")
            print(f"  Date: {match['performed']}")
            print(f"  Keywords: {', '.join(match['keywords'][:5])}")
            if match['code_text']:
                print(f"  Text: {match['code_text']}")


def analyze_procedure_code_coding():
    """Analyze procedure_code_coding for RT CPT codes."""
    print("\n" + "="*80)
    print("ANALYZING: procedure_code_coding (CPT/SNOMED codes)")
    print("="*80)
    
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    athena = session.client('athena')
    
    # Query for RT CPT codes (77xxx series)
    # CORRECTED COLUMN NAMES: code_coding_code, code_coding_display, code_coding_system
    query = f"""
    SELECT 
        procedure_id,
        code_coding_code,
        code_coding_display,
        code_coding_system
    FROM {DATABASE}.procedure_code_coding
    WHERE code_coding_code LIKE '77%'
       OR LOWER(code_coding_display) LIKE '%radiation%'
       OR LOWER(code_coding_display) LIKE '%radiotherapy%'
       OR LOWER(code_coding_display) LIKE '%brachytherapy%'
    """
    
    print("\nQuerying procedure codes...")
    results = execute_athena_query(athena, query)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No RT codes found.")
        return
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    print(f"\n✅ Found {len(data)} RT procedure codes")
    
    # Group by code
    code_counter = Counter()
    for row in data:
        row_dict = dict(zip(columns, row))
        code = row_dict.get('code_coding_code', '')
        display = row_dict.get('code_coding_display', '')
        code_counter[f"{code} - {display}"] += 1
    
    print("\nTop RT Procedure Codes:")
    for code_display, count in code_counter.most_common(20):
        print(f"  {code_display[:70]:<70} {count:4}")


def analyze_procedure_note():
    """Analyze procedure_note for RT content."""
    print("\n" + "="*80)
    print("ANALYZING: procedure_note (procedure documentation)")
    print("="*80)
    
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    athena = session.client('athena')
    
    # Query notes
    # CORRECTED COLUMN NAMES: note_author_reference_display (not note_author_display)
    query = f"""
    SELECT 
        procedure_id,
        note_text,
        note_time,
        note_author_reference_display
    FROM {DATABASE}.procedure_note
    WHERE note_text IS NOT NULL
    """
    
    print("\nQuerying procedure notes...")
    results = execute_athena_query(athena, query)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No notes found.")
        return
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    print(f"Total procedure notes: {len(data)}")
    
    # Check for RT keywords
    rt_notes = []
    keyword_hits = Counter()
    
    for row in data:
        row_dict = dict(zip(columns, row))
        note_text = row_dict.get('note_text', '').lower()
        
        found_keywords = []
        for keyword in RADIATION_SPECIFIC_KEYWORDS:
            if keyword in note_text:
                found_keywords.append(keyword)
                keyword_hits[keyword] += 1
        
        if found_keywords:
            rt_notes.append({
                'procedure_id': row_dict['procedure_id'],
                'keywords': found_keywords,
                'note_sample': row_dict.get('note_text', '')[:150]
            })
    
    # Results
    hit_rate = (len(rt_notes) / len(data) * 100) if data else 0
    print(f"\n✅ RT-SPECIFIC Hit Rate: {len(rt_notes)}/{len(data)} ({hit_rate:.1f}%)")
    
    if keyword_hits:
        print("\nTop RT Keywords in Notes:")
        for keyword, count in keyword_hits.most_common(15):
            print(f"  {keyword:30} {count:4} hits")


def analyze_procedure_reason_code():
    """Analyze procedure_reason_code for RT indications."""
    print("\n" + "="*80)
    print("ANALYZING: procedure_reason_code (procedure indications)")
    print("="*80)
    
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    athena = session.client('athena')
    
    # Query reason codes
    query = f"""
    SELECT 
        procedure_id,
        reason_code_coding,
        reason_code_text
    FROM {DATABASE}.procedure_reason_code
    WHERE reason_code_text IS NOT NULL
       OR reason_code_coding IS NOT NULL
    """
    
    print("\nQuerying procedure reason codes...")
    results = execute_athena_query(athena, query)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No reason codes found.")
        return
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    print(f"Total reason codes: {len(data)}")
    
    # Check for RT keywords
    rt_reasons = []
    keyword_hits = Counter()
    
    for row in data:
        row_dict = dict(zip(columns, row))
        combined_text = row_dict.get('reason_code_text', '').lower()
        
        # Also check coding displays
        coding_json = row_dict.get('reason_code_coding', '')
        if coding_json:
            try:
                codings = json.loads(coding_json.replace("'", '"'))
                for coding in codings:
                    if isinstance(coding, dict):
                        combined_text += ' ' + coding.get('display', '').lower()
            except:
                pass
        
        found_keywords = []
        for keyword in RADIATION_SPECIFIC_KEYWORDS:
            if keyword in combined_text:
                found_keywords.append(keyword)
                keyword_hits[keyword] += 1
        
        if found_keywords:
            rt_reasons.append({
                'procedure_id': row_dict['procedure_id'],
                'keywords': found_keywords
            })
    
    # Results
    hit_rate = (len(rt_reasons) / len(data) * 100) if data else 0
    print(f"\n✅ RT-SPECIFIC Hit Rate: {len(rt_reasons)}/{len(data)} ({hit_rate:.1f}%)")
    
    if keyword_hits:
        print("\nTop RT Keywords in Reason Codes:")
        for keyword, count in keyword_hits.most_common(10):
            print(f"  {keyword:30} {count:4} hits")


def print_final_summary():
    """Print recommendations based on analysis."""
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    print("\n📋 Tables to Include in Extraction:")
    print("  1. procedure (parent) - IF hit rate > 1%")
    print("     • Use code_text, outcome_text for RT keyword filtering")
    print("     • Capture performed_date_time for temporal alignment")
    
    print("\n  2. procedure_code_coding - HIGHLY RECOMMENDED")
    print("     • Filter for CPT 77xxx codes (radiation oncology)")
    print("     • Also check display text for RT keywords")
    print("     • Join to parent for dates and context")
    
    print("\n  3. procedure_note - IF hit rate > 5%")
    print("     • Contains procedure documentation")
    print("     • Filter with RT-specific keywords")
    print("     • May contain dose/technique information")
    
    print("\n  4. procedure_reason_code - MAYBE")
    print("     • Indications for procedures")
    print("     • Check if RT-specific reasons present")
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Review hit rates from analysis above")
    print("2. Add high-value tables to extract_radiation_data.py")
    print("3. Use resource prefixes: proc_, pcc_, pn_, prc_")
    print("4. Capture date fields for cross-resource alignment")
    print("5. Test on RT patient to validate extraction")


def main():
    """Main execution."""
    print("\n" + "="*80)
    print("PROCEDURE TABLES: RT CONTENT ANALYSIS")
    print("="*80)
    print("Using RT-SPECIFIC keywords (not general oncology)")
    print("="*80)
    
    # Analyze each table
    analyze_procedure_parent()
    analyze_procedure_code_coding()
    analyze_procedure_note()
    analyze_procedure_reason_code()
    
    # Recommendations
    print_final_summary()
    
    print("\n✅ Procedure RT content analysis complete!")


if __name__ == '__main__':
    main()
