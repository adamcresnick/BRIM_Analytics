#!/usr/bin/env python3
"""
Analyze care_plan_note and care_plan_part_of for radiation-related content.
NO PATIENT ID LEAKAGE - aggregated analysis only.
"""

import boto3
import time
import re
from datetime import datetime
from collections import Counter

TEST_PATIENTS = [
    'eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3',  # Has RT
    'emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3',  # Has RT
    'eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3',  # No RT
    'enen8-RpIWkLodbVcZHGc4Gt2.iQxz6uAOLVmZkNWMTo3'   # No RT
]

RADIATION_KEYWORDS = [
    'radiation', 'radiotherapy', 'rad onc', 'imrt', 'xrt', 'rt ', 
    'proton', 'stereotactic', 'sbrt', 'srs', 'csi', 're-irradiation',
    'gamma knife', 'cyberknife', 'brachytherapy', 'cobalt', 
    'dose', 'gray', 'gy', 'fraction', 'beam', 'treatment planning'
]

athena = boto3.client('athena', region_name='us-east-1')
DATABASE = 'fhir_prd_db'
OUTPUT_LOCATION = 's3://aws-athena-query-results-343218191717-us-east-1/'

def execute_query(query_string):
    """Execute Athena query and wait for results."""
    try:
        response = athena.start_query_execution(
            QueryString=query_string,
            QueryExecutionContext={'Database': DATABASE},
            ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
        )
        query_id = response['QueryExecutionId']
        
        max_wait = 30
        elapsed = 0
        while elapsed < max_wait:
            status = athena.get_query_execution(QueryExecutionId=query_id)
            state = status['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(1)
            elapsed += 1
        
        if state != 'SUCCEEDED':
            return None
        
        result = athena.get_query_results(QueryExecutionId=query_id)
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def analyze_care_plan_note():
    """Analyze care_plan_note for radiation content - NO PATIENT IDs"""
    patient_list = "', '".join(TEST_PATIENTS)
    
    query = f"""
    SELECT child.note_text
    FROM {DATABASE}.care_plan_note child
    JOIN {DATABASE}.care_plan parent ON child.care_plan_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    print(f"\n{'='*80}")
    print("ANALYZING: care_plan_note")
    print(f"{'='*80}\n")
    
    result = execute_query(query)
    if not result:
        print("❌ Query failed")
        return
    
    rows = result['ResultSet']['Rows'][1:]  # Skip header
    print(f"Total notes retrieved: {len(rows)}")
    
    # Analyze without showing patient IDs
    radiation_notes = []
    keyword_counts = Counter()
    
    for row in rows:
        if len(row['Data']) > 0 and 'VarCharValue' in row['Data'][0]:
            note_text = row['Data'][0]['VarCharValue'].lower()
            
            # Check for radiation keywords
            found_keywords = []
            for keyword in RADIATION_KEYWORDS:
                if keyword.lower() in note_text:
                    found_keywords.append(keyword)
                    keyword_counts[keyword] += 1
            
            if found_keywords:
                radiation_notes.append({
                    'text': note_text[:200] + '...',  # Truncate for privacy
                    'keywords': found_keywords
                })
    
    print(f"\n📊 RADIATION-RELATED NOTES: {len(radiation_notes)}/{len(rows)}")
    
    if keyword_counts:
        print(f"\n🔍 Keyword Frequency:")
        for keyword, count in keyword_counts.most_common(10):
            print(f"   {keyword}: {count} occurrences")
    
    if radiation_notes:
        print(f"\n📝 Sample radiation notes (truncated, NO patient IDs):")
        for i, note in enumerate(radiation_notes[:5], 1):
            print(f"\n   Note {i}:")
            print(f"   Keywords: {', '.join(note['keywords'])}")
            print(f"   Text: {note['text'][:150]}...")
    else:
        print("\n❌ No radiation-related content found in care_plan_note")

def analyze_care_plan_part_of():
    """Analyze care_plan_part_of for radiation plan references - NO PATIENT IDs"""
    patient_list = "', '".join(TEST_PATIENTS)
    
    query = f"""
    SELECT child.part_of_reference
    FROM {DATABASE}.care_plan_part_of child
    JOIN {DATABASE}.care_plan parent ON child.care_plan_id = parent.id
    WHERE parent.subject_reference IN ('{patient_list}')
    """
    
    print(f"\n{'='*80}")
    print("ANALYZING: care_plan_part_of")
    print(f"{'='*80}\n")
    
    result = execute_query(query)
    if not result:
        print("❌ Query failed")
        return
    
    rows = result['ResultSet']['Rows'][1:]  # Skip header
    print(f"Total part_of references: {len(rows)}")
    
    # Analyze reference patterns (NO patient IDs)
    reference_types = Counter()
    radiation_refs = []
    
    for row in rows:
        if len(row['Data']) > 0 and 'VarCharValue' in row['Data'][0]:
            ref = row['Data'][0]['VarCharValue']
            ref_lower = ref.lower()
            
            # Classify reference type
            if '/' in ref:
                ref_type = ref.split('/')[0] if '/' in ref else 'Unknown'
                reference_types[ref_type] += 1
            
            # Check for radiation keywords in reference
            if any(keyword in ref_lower for keyword in RADIATION_KEYWORDS):
                radiation_refs.append(ref[:100])  # Truncate
    
    print(f"\n📊 REFERENCE TYPE DISTRIBUTION:")
    for ref_type, count in reference_types.most_common(10):
        print(f"   {ref_type}: {count} references")
    
    print(f"\n🎯 RADIATION-RELATED REFERENCES: {len(radiation_refs)}/{len(rows)}")
    
    if radiation_refs:
        print(f"\n📝 Sample radiation references (truncated):")
        for i, ref in enumerate(radiation_refs[:10], 1):
            print(f"   {i}. {ref}...")
    else:
        print("\n❌ No radiation-related references found in part_of_reference")

def main():
    print(f"""
{'='*80}
CARE PLAN RADIATION CONTENT ANALYSIS
Database: {DATABASE}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

Analyzing 2 tables with data:
  1. care_plan_note (56 records)
  2. care_plan_part_of (4,640 records)

NO PATIENT IDs WILL BE DISPLAYED
{'='*80}
""")
    
    analyze_care_plan_note()
    time.sleep(2)
    analyze_care_plan_part_of()
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
