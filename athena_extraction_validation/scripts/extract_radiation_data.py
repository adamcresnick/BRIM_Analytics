#!/usr/bin/env python3
"""
Extract Radiation Oncology Data from Athena FHIR Database

This script extracts comprehensive radiation therapy data including:
- Radiation oncology consults (from appointment_service_type)
- Treatment appointments (simulations, start, end)
- Care plan notes with dose information (care_plan_note)
- Treatment plan hierarchy (care_plan_part_of)
- Service request notes with coordination details (service_request_note)
- RT history from service request reasons (service_request_reason_code)
- Procedure RT codes (CPT 77xxx, includes proton therapy)
- Procedure notes with RT keywords (dose information)
- Treatment timeline reconstruction
- Re-irradiation identification

Data Sources:
- appointment + appointment_service_type (consults & treatments)
- care_plan_note (patient instructions, dose info in Gy)
- care_plan_part_of (treatment plan hierarchy)
- service_request_note (treatment coordination, 27.5% RT hit rate)
- service_request_reason_code (RT history tracking, 4.8% RT hit rate)
- procedure_code_coding (CPT 77xxx codes, 86 RT codes including proton)
- procedure_note (RT keywords, 1.0% hit rate but high quality)

Column Naming Convention:
- Resource prefixes: cp_, cpn_, cppo_, sr_, srn_, srrc_, proc_, pcc_, pn_
- Enables cross-resource joins and clear data provenance
- See COLUMN_NAMING_CONVENTIONS.md for full reference

Author: Clinical Data Extraction Team
Date: 2025-10-12
Updated: 2025-10-12 - Added procedure table extraction
"""

import boto3
import time
import pandas as pd
import json
import re
import sys
from pathlib import Path

# Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
REGION = 'us-east-1'
DATABASE = 'fhir_prd_db'  # UPDATED: Using new production database
S3_OUTPUT = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / 'staging_files'

# RT-SPECIFIC search terms for radiation therapy identification
# NOTE: These are RT-SPECIFIC keywords, not general oncology terms
RADIATION_SEARCH_TERMS = [
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
    # Anatomical sites (RT-specific)
    'cranial radiation', 'csi', 'craniospinal',
    'whole brain', 'wbrt', 'pci',  # Prophylactic cranial irradiation
]


def execute_athena_query(athena_client, query, database, max_wait=180):
    """
    Execute an Athena query and wait for results.
    
    Args:
        athena_client: boto3 Athena client
        query: SQL query string
        database: Database name
        max_wait: Maximum wait time in seconds
        
    Returns:
        Query results or None if failed
    """
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': S3_OUTPUT}
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait for query completion
        for _ in range(max_wait):
            status_result = athena_client.get_query_execution(QueryExecutionId=query_id)
            state = status_result['QueryExecution']['Status']['State']
            
            if state == 'SUCCEEDED':
                return athena_client.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
            elif state in ['FAILED', 'CANCELLED']:
                reason = status_result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                print(f"Query failed: {reason}")
                return None
            
            time.sleep(1)
        
        print(f"Query timeout after {max_wait} seconds")
        return None
        
    except Exception as e:
        print(f"Error executing query: {e}")
        return None


def parse_service_type_display(service_type_json):
    """
    Parse the display value from service_type_coding JSON.
    
    Args:
        service_type_json: JSON string or dict
        
    Returns:
        Display value or empty string
    """
    if not service_type_json:
        return ''
    
    try:
        # Try parsing as JSON
        if isinstance(service_type_json, str):
            data = json.loads(service_type_json)
        else:
            data = service_type_json
            
        if isinstance(data, list) and len(data) > 0:
            return data[0].get('display', '')
        elif isinstance(data, dict):
            return data.get('display', '')
            
    except json.JSONDecodeError:
        # Fallback: regex search
        match = re.search(r"'display':\s*'([^']+)'", str(service_type_json))
        if match:
            return match.group(1)
    
    return ''


def extract_radiation_oncology_consults(athena_client, patient_fhir_id):
    """
    Extract radiation oncology consultation appointments.
    
    Args:
        athena_client: boto3 Athena client
        patient_fhir_id: Full FHIR patient reference (e.g., 'Patient/ABC123')
        
    Returns:
        DataFrame with radiation oncology consults
    """
    print("\n" + "="*80)
    print("EXTRACTING RADIATION ONCOLOGY CONSULTS")
    print("="*80)
    
    # First get all appointments with service types (Athena limitation: must use simple SELECT)
    query = f"""
    SELECT DISTINCT ast.appointment_id, ast.service_type_coding
    FROM {DATABASE}.appointment_service_type ast
    JOIN {DATABASE}.appointment_participant ap ON ast.appointment_id = ap.appointment_id
    WHERE ap.participant_actor_reference = '{patient_fhir_id}'
    """
    
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No appointment service types found.")
        return pd.DataFrame()
    
    # Parse service types
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    service_types_df = pd.DataFrame(data, columns=columns)
    
    # Parse service type display
    service_types_df['service_type_display'] = service_types_df['service_type_coding'].apply(parse_service_type_display)
    
    # Filter for radiation-related service types
    rad_pattern = r'rad.*onc|radiation|xrt'
    rad_service_types = service_types_df[
        service_types_df['service_type_display'].str.contains(rad_pattern, na=False, case=False, regex=True)
    ]
    
    if len(rad_service_types) == 0:
        print("No radiation oncology consults found.")
        return pd.DataFrame()
    
    print(f"Found {len(rad_service_types)} appointment(s) with radiation service types")
    
    # Now get full appointment details for these IDs
    appointment_ids = "', '".join(rad_service_types['appointment_id'].tolist())
    
    query2 = f"""
    SELECT DISTINCT a.*
    FROM {DATABASE}.appointment a
    WHERE a.id IN ('{appointment_ids}')
    ORDER BY a.start
    """
    
    results2 = execute_athena_query(athena_client, query2, DATABASE)
    
    if not results2 or len(results2['ResultSet']['Rows']) <= 1:
        print("Could not retrieve appointment details.")
        return pd.DataFrame()
    
    # Parse appointment details
    columns2 = [col['Name'] for col in results2['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data2 = []
    
    for row in results2['ResultSet']['Rows'][1:]:
        data2.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data2, columns=columns2)
    
    # Merge with service type display
    df = df.merge(
        rad_service_types[['appointment_id', 'service_type_display']], 
        left_on='id', 
        right_on='appointment_id', 
        how='left'
    )
    
    print(f"\n✅ Found {len(df)} radiation oncology consultation appointments")
    
    if len(df) > 0:
        print("\nConsultation Details:")
        for idx, row in df.iterrows():
            date = row['start'][:10] if row['start'] else 'N/A'
            print(f"  {date} | {row['service_type_display']:40} | {row['status']}")
    
    return df


def extract_radiation_treatment_appointments(athena_client, patient_fhir_id):
    """
    Extract all radiation treatment-related appointments from text fields.
    
    Args:
        athena_client: boto3 Athena client
        patient_fhir_id: Full FHIR patient reference
        
    Returns:
        DataFrame with radiation treatment appointments
    """
    print("\n" + "="*80)
    print("EXTRACTING RADIATION TREATMENT APPOINTMENTS")
    print("="*80)
    
    # Get ALL appointments first (Athena limitation workaround)
    query = f"""
    SELECT DISTINCT a.*
    FROM {DATABASE}.appointment a
    JOIN {DATABASE}.appointment_participant ap ON a.id = ap.appointment_id
    WHERE ap.participant_actor_reference = '{patient_fhir_id}'
    ORDER BY a.start
    """
    
    print("\nQuerying all appointments...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No appointments found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total appointments: {len(df)}")
    
    # Filter for radiation-related content in text fields
    print("\nFiltering for radiation-related appointments...")
    
    # Build regex pattern from search terms
    pattern = '|'.join([re.escape(term) for term in RADIATION_SEARCH_TERMS])
    
    rad_df = df[
        df['comment'].str.contains(pattern, na=False, case=False, regex=True) |
        df['patient_instruction'].str.contains(pattern, na=False, case=False, regex=True) |
        df['description'].str.contains(pattern, na=False, case=False, regex=True)
    ].copy()
    
    print(f"\n✅ Found {len(rad_df)} radiation treatment appointments")
    
    if len(rad_df) > 0:
        rad_df = rad_df.sort_values('start')
        
        # Categorize appointments
        rad_df['rt_category'] = 'Unknown'
        rad_df['rt_milestone'] = ''
        
        for idx, row in rad_df.iterrows():
            comment = str(row['comment']).lower() if pd.notna(row['comment']) else ''
            instruction = str(row['patient_instruction']).lower() if pd.notna(row['patient_instruction']) else ''
            combined = comment + ' ' + instruction
            
            # Categorize
            if 'consult' in combined or 'consultation' in combined:
                rad_df.at[idx, 'rt_category'] = 'Consultation'
            elif 'simulation' in combined or 'sim' in combined:
                rad_df.at[idx, 'rt_category'] = 'Simulation'
            elif 'start' in combined and ('rt' in combined or 'imrt' in combined or 'treatment' in combined):
                rad_df.at[idx, 'rt_category'] = 'Treatment Start'
                rad_df.at[idx, 'rt_milestone'] = 'START'
            elif 'end' in combined and 'radiation' in combined:
                rad_df.at[idx, 'rt_category'] = 'Treatment End'
                rad_df.at[idx, 'rt_milestone'] = 'END'
            elif 're-irradiation' in combined or 'reirradiation' in combined:
                rad_df.at[idx, 'rt_category'] = 'Re-irradiation'
                rad_df.at[idx, 'rt_milestone'] = 'RE-RT'
            elif 's/p' in combined and ('rt' in combined or 'radiation' in combined):
                rad_df.at[idx, 'rt_category'] = 'Post-Treatment'
                rad_df.at[idx, 'rt_milestone'] = 's/p RT'
            elif any(term in combined for term in ['imrt', 'proton', 'photon', 'stereotactic']):
                rad_df.at[idx, 'rt_category'] = 'Treatment Session'
            else:
                rad_df.at[idx, 'rt_category'] = 'Related Visit'
        
        # Print summary by category
        print("\nAppointment Breakdown by Category:")
        category_counts = rad_df['rt_category'].value_counts()
        for category, count in category_counts.items():
            print(f"  {category:20} {count:3}")
    
    return rad_df


def extract_care_plan_notes(athena_client, patient_id):
    """
    Extract radiation-related notes from care_plan_note table.
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix - care_plan uses bare IDs)
        
    Returns:
        DataFrame with radiation-related care plan notes
    """
    print("\n" + "="*80)
    print("EXTRACTING CARE PLAN NOTES")
    print("="*80)
    
    query = f"""
    SELECT 
        child.care_plan_id,
        child.note_text as cpn_note_text,
        parent.status as cp_status,
        parent.intent as cp_intent,
        parent.title as cp_title,
        parent.period_start as cp_period_start,
        parent.period_end as cp_period_end
    FROM {DATABASE}.care_plan_note child
    JOIN {DATABASE}.care_plan parent ON child.care_plan_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
    ORDER BY parent.period_start
    """
    
    print("\nQuerying care_plan_note...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No care plan notes found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total care plan notes: {len(df)}")
    
    # Filter for radiation-related content
    pattern = '|'.join([re.escape(term) for term in RADIATION_SEARCH_TERMS])
    rad_notes = df[
        df['cpn_note_text'].str.contains(pattern, na=False, case=False, regex=True)
    ].copy()
    
    print(f"\n✅ Found {len(rad_notes)} radiation-related care plan notes")
    
    if len(rad_notes) > 0:
        # Extract dose information (Gy) if present
        rad_notes['cpn_contains_dose'] = rad_notes['cpn_note_text'].str.contains(
            r'\d+\.?\d*\s*gy', na=False, case=False, regex=True
        )
        
        dose_mentions = rad_notes['cpn_contains_dose'].sum()
        if dose_mentions > 0:
            print(f"   → {dose_mentions} notes contain dose information (Gy)")
        
        # Categorize note types
        rad_notes['cpn_note_type'] = 'General'
        for idx, row in rad_notes.iterrows():
            note_lower = str(row['cpn_note_text']).lower()
            if 'instruction' in note_lower:
                rad_notes.at[idx, 'cpn_note_type'] = 'Patient Instructions'
            elif 'dose' in note_lower or 'gy' in note_lower:
                rad_notes.at[idx, 'cpn_note_type'] = 'Dosage Information'
            elif 'side effect' in note_lower or 'symptom' in note_lower:
                rad_notes.at[idx, 'cpn_note_type'] = 'Side Effects/Monitoring'
        
        print("\nNote Type Breakdown:")
        type_counts = rad_notes['cpn_note_type'].value_counts()
        for note_type, count in type_counts.items():
            print(f"  {note_type:30} {count:3}")
    
    return rad_notes


def extract_care_plan_hierarchy(athena_client, patient_id):
    """
    Extract care plan hierarchy from care_plan_part_of table.
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix - care_plan uses bare IDs)
        
    Returns:
        DataFrame with care plan hierarchy relationships
    """
    print("\n" + "="*80)
    print("EXTRACTING CARE PLAN HIERARCHY")
    print("="*80)
    
    query = f"""
    SELECT 
        child.care_plan_id,
        child.part_of_reference as cppo_part_of_reference,
        parent.status as cp_status,
        parent.intent as cp_intent,
        parent.title as cp_title,
        parent.period_start as cp_period_start,
        parent.period_end as cp_period_end
    FROM {DATABASE}.care_plan_part_of child
    JOIN {DATABASE}.care_plan parent ON child.care_plan_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
    ORDER BY parent.period_start
    """
    
    print("\nQuerying care_plan_part_of...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No care plan hierarchy found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total care plan relationships: {len(df)}")
    
    # Filter for radiation-related references
    # Check both the title and the part_of_reference fields
    pattern = '|'.join([re.escape(term) for term in RADIATION_SEARCH_TERMS])
    rad_hierarchy = df[
        (df['cp_title'].str.contains(pattern, na=False, case=False, regex=True)) |
        (df['cppo_part_of_reference'].str.contains(pattern, na=False, case=False, regex=True))
    ].copy()
    
    print(f"\n✅ Found {len(rad_hierarchy)} radiation-related care plan relationships")
    
    if len(rad_hierarchy) > 0:
        # Analyze reference patterns
        unique_parents = rad_hierarchy['cppo_part_of_reference'].nunique()
        unique_children = rad_hierarchy['care_plan_id'].nunique()
        
        print(f"   → {unique_parents} unique parent plans")
        print(f"   → {unique_children} unique child plans")
        print(f"   → Average {len(rad_hierarchy)/unique_parents:.1f} children per parent")
    
    return rad_hierarchy


def extract_service_request_notes(athena_client, patient_id):
    """
    Extract radiation-related notes from service_request_note table.
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix - service_request uses bare IDs)
        
    Returns:
        DataFrame with radiation-related service request notes
    """
    print("\n" + "="*80)
    print("EXTRACTING SERVICE REQUEST NOTES")
    print("="*80)
    
    query = f"""
    SELECT 
        parent.id as service_request_id,
        parent.intent as sr_intent,
        parent.status as sr_status,
        parent.authored_on as sr_authored_on,
        parent.occurrence_date_time as sr_occurrence_date_time,
        parent.occurrence_period_start as sr_occurrence_period_start,
        parent.occurrence_period_end as sr_occurrence_period_end,
        note.note_text as srn_note_text,
        note.note_time as srn_note_time
    FROM {DATABASE}.service_request_note note
    JOIN {DATABASE}.service_request parent ON note.service_request_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
    ORDER BY COALESCE(note.note_time, parent.occurrence_date_time, parent.occurrence_period_start, parent.authored_on)
    """
    
    print("\nQuerying service_request_note...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No service request notes found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total service request notes: {len(df)}")
    
    # Filter for radiation-specific content
    rt_specific_keywords = [
        'radiation', 'radiotherapy', 'xrt', 'rt ', 'imrt', 'vmat', 'proton',
        'dose', 'gy', 'gray', 'fraction', 'beam', 'stereotactic', 'sbrt', 'srs'
    ]
    pattern = '|'.join([re.escape(term) for term in rt_specific_keywords])
    
    rad_notes = df[
        df['srn_note_text'].str.contains(pattern, na=False, case=False, regex=True)
    ].copy()
    
    print(f"\n✅ Found {len(rad_notes)} radiation-specific service request notes")
    
    if len(rad_notes) > 0:
        # Extract dose information (Gy) if present
        rad_notes['srn_contains_dose'] = rad_notes['srn_note_text'].str.contains(
            r'\d+\.?\d*\s*gy', na=False, case=False, regex=True
        )
        
        dose_mentions = rad_notes['srn_contains_dose'].sum()
        if dose_mentions > 0:
            print(f"   → {dose_mentions} notes contain dose information (Gy)")
        
        # Categorize note types
        rad_notes['srn_note_type'] = 'General'
        for idx, row in rad_notes.iterrows():
            note_lower = str(row['srn_note_text']).lower()
            if 'coordination' in note_lower or 'schedule' in note_lower:
                rad_notes.at[idx, 'srn_note_type'] = 'Treatment Coordination'
            elif 'dose' in note_lower or 'gy' in note_lower:
                rad_notes.at[idx, 'srn_note_type'] = 'Dosage Information'
            elif 'team' in note_lower or 'oncology' in note_lower:
                rad_notes.at[idx, 'srn_note_type'] = 'Team Communication'
        
        print("\nNote Type Breakdown:")
        type_counts = rad_notes['srn_note_type'].value_counts()
        for note_type, count in type_counts.items():
            print(f"  {note_type:30} {count:3}")
    
    return rad_notes


def extract_service_request_reason_codes(athena_client, patient_id):
    """
    Extract RT history codes from service_request_reason_code table.
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix - service_request uses bare IDs)
        
    Returns:
        DataFrame with radiation therapy history codes
    """
    print("\n" + "="*80)
    print("EXTRACTING SERVICE REQUEST REASON CODES (RT HISTORY)")
    print("="*80)
    
    query = f"""
    SELECT 
        parent.id as service_request_id,
        parent.intent as sr_intent,
        parent.status as sr_status,
        parent.authored_on as sr_authored_on,
        parent.occurrence_date_time as sr_occurrence_date_time,
        parent.occurrence_period_start as sr_occurrence_period_start,
        parent.occurrence_period_end as sr_occurrence_period_end,
        reason.reason_code_coding as srrc_reason_code_coding,
        reason.reason_code_text as srrc_reason_code_text
    FROM {DATABASE}.service_request_reason_code reason
    JOIN {DATABASE}.service_request parent ON reason.service_request_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
    ORDER BY COALESCE(parent.occurrence_date_time, parent.occurrence_period_start, parent.authored_on)
    """
    
    print("\nQuerying service_request_reason_code...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No service request reason codes found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total service request reason codes: {len(df)}")
    
    # Parse JSON codings and filter for RT-specific content
    rt_specific_keywords = [
        'radiation', 'radiotherapy', 'beam', 'xrt', 'imrt', 'proton',
        'dose', 'gy', 'stereotactic', 'brachytherapy'
    ]
    
    rt_records = []
    for idx, row in df.iterrows():
        coding_json = row['srrc_reason_code_coding']
        text = row['srrc_reason_code_text']
        
        # Parse JSON coding array
        try:
            codings = json.loads(coding_json.replace("'", '"')) if coding_json else []
        except:
            codings = []
        
        # Check text and all coding displays for RT-specific keywords
        combined_text = (text.lower() if text else '')
        for coding in codings:
            if isinstance(coding, dict):
                combined_text += ' ' + coding.get('display', '').lower()
                combined_text += ' ' + coding.get('code', '').lower()
        
        # Check for RT keywords
        is_rt_related = any(keyword in combined_text for keyword in rt_specific_keywords)
        
        if is_rt_related:
            # Extract primary coding
            primary = codings[0] if codings else {}
            rt_records.append({
                'service_request_id': row['service_request_id'],
                'sr_intent': row['sr_intent'],
                'sr_status': row['sr_status'],
                'sr_authored_on': row['sr_authored_on'],
                'sr_occurrence_date_time': row['sr_occurrence_date_time'],
                'sr_occurrence_period_start': row['sr_occurrence_period_start'],
                'sr_occurrence_period_end': row['sr_occurrence_period_end'],
                'srrc_reason_code': primary.get('code', ''),
                'srrc_reason_display': primary.get('display', ''),
                'srrc_reason_system': primary.get('system', ''),
                'srrc_reason_text': text,
                'srrc_num_codings': len(codings)
            })
    
    rad_df = pd.DataFrame(rt_records)
    
    print(f"\n✅ Found {len(rad_df)} RT-specific reason codes")
    
    if len(rad_df) > 0:
        # Show most common RT-related codes
        print("\nMost Common RT-Related Codes:")
        code_counts = rad_df['srrc_reason_display'].value_counts().head(5)
        for display, count in code_counts.items():
            print(f"  {display[:60]:60} {count:3}")
    
    return rad_df


def extract_procedure_rt_codes(athena_client, patient_id):
    """
    Extract RT procedures via CPT codes from procedure_code_coding.
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix - procedure uses bare IDs)
        
    Returns:
        DataFrame with RT procedure codes
    """
    print("\n" + "="*80)
    print("EXTRACTING PROCEDURE RT CODES (CPT 77xxx)")
    print("="*80)
    
    query = f"""
    SELECT 
        parent.id as procedure_id,
        parent.performed_date_time as proc_performed_date_time,
        parent.performed_period_start as proc_performed_period_start,
        parent.performed_period_end as proc_performed_period_end,
        parent.status as proc_status,
        parent.code_text as proc_code_text,
        parent.category_text as proc_category_text,
        coding.code_coding_code as pcc_code,
        coding.code_coding_display as pcc_display,
        coding.code_coding_system as pcc_system
    FROM {DATABASE}.procedure_code_coding coding
    JOIN {DATABASE}.procedure parent ON coding.procedure_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
      AND (
          coding.code_coding_code LIKE '77%'
          OR LOWER(coding.code_coding_display) LIKE '%radiation%'
          OR LOWER(coding.code_coding_display) LIKE '%radiotherapy%'
          OR LOWER(coding.code_coding_display) LIKE '%brachytherapy%'
          OR LOWER(coding.code_coding_display) LIKE '%proton%'
      )
    ORDER BY parent.performed_date_time
    """
    
    print("\nQuerying procedure_code_coding...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No RT procedure codes found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"\n✅ Found {len(df)} RT procedure codes")
    
    if len(df) > 0:
        # Categorize by CPT code range and display text
        df['pcc_procedure_type'] = 'Other RT'
        for idx, row in df.iterrows():
            code = str(row['pcc_code'])
            display = str(row['pcc_display']).lower()
            
            if 'fluoro' in display or 'venous access' in display or 'picc' in display or 'port' in display:
                df.at[idx, 'pcc_procedure_type'] = 'IR/Fluoro (not RT)'
            elif 'proton' in display:
                df.at[idx, 'pcc_procedure_type'] = 'Proton Therapy'
            elif code.startswith('770'):
                df.at[idx, 'pcc_procedure_type'] = 'Consultation/Planning'
            elif code.startswith('771'):
                df.at[idx, 'pcc_procedure_type'] = 'Physics/Dosimetry'
            elif code.startswith('772'):
                df.at[idx, 'pcc_procedure_type'] = 'Treatment Delivery'
            elif code.startswith('773'):
                df.at[idx, 'pcc_procedure_type'] = 'Stereotactic'
            elif code.startswith('774'):
                df.at[idx, 'pcc_procedure_type'] = 'Brachytherapy'
        
        print("\nProcedure Type Breakdown:")
        type_counts = df['pcc_procedure_type'].value_counts()
        for proc_type, count in type_counts.items():
            print(f"  {proc_type:30} {count:3}")
    
    return df


def extract_procedure_notes(athena_client, patient_id):
    """
    Extract RT-related procedure notes.
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix - procedure uses bare IDs)
        
    Returns:
        DataFrame with RT-related procedure notes
    """
    print("\n" + "="*80)
    print("EXTRACTING PROCEDURE NOTES (RT-SPECIFIC)")
    print("="*80)
    
    query = f"""
    SELECT 
        parent.id as procedure_id,
        parent.performed_date_time as proc_performed_date_time,
        parent.performed_period_start as proc_performed_period_start,
        parent.performed_period_end as proc_performed_period_end,
        parent.status as proc_status,
        parent.code_text as proc_code_text,
        note.note_text as pn_note_text,
        note.note_time as pn_note_time,
        note.note_author_reference_display as pn_author_display
    FROM {DATABASE}.procedure_note note
    JOIN {DATABASE}.procedure parent ON note.procedure_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
      AND note.note_text IS NOT NULL
    ORDER BY parent.performed_date_time
    """
    
    print("\nQuerying procedure_note...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No procedure notes found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total procedure notes: {len(df)}")
    
    # Filter for RT-specific content
    rt_keywords = [
        'radiation', 'radiotherapy', 'xrt', 'rt ', 'imrt', 'vmat', 'proton',
        'brachytherapy', 'ldr', 'hdr', 'dose', 'gy', 'gray', 'fraction',
        'stereotactic', 'sbrt', 'srs'
    ]
    pattern = '|'.join([re.escape(term) for term in rt_keywords])
    
    rad_notes = df[
        df['pn_note_text'].str.contains(pattern, na=False, case=False, regex=True)
    ].copy()
    
    print(f"\n✅ Found {len(rad_notes)} RT-specific procedure notes")
    
    if len(rad_notes) > 0:
        # Extract dose information (Gy) if present
        rad_notes['pn_contains_dose'] = rad_notes['pn_note_text'].str.contains(
            r'\d+\.?\d*\s*gy', na=False, case=False, regex=True
        )
        
        dose_mentions = rad_notes['pn_contains_dose'].sum()
        if dose_mentions > 0:
            print(f"   → {dose_mentions} notes contain dose information (Gy)")
    
    return rad_notes


def extract_radiation_oncology_documents(athena_client, patient_id):
    """
    Extract radiation oncology DocumentReferences, prioritizing external records.
    
    Focus on:
    - Practice setting = 'Radiation Oncology' 
    - Non-HTML/RTF formats (PDFs, images) - likely from external institutions
    - RT keywords in description
    
    Args:
        athena_client: boto3 Athena client
        patient_id: Patient ID (WITHOUT 'Patient/' prefix)
        
    Returns:
        DataFrame with RT-related document references
    """
    print("\n" + "="*80)
    print("EXTRACTING RADIATION ONCOLOGY DOCUMENTS")
    print("="*80)
    
    query = f"""
    SELECT DISTINCT
        dr.id as document_id,
        dr.date as doc_date,
        dr.status as doc_status,
        dr.doc_status,
        dr.type_text as doc_type_text,
        dr.description as doc_description,
        dc.content_attachment_content_type as doc_mime_type,
        dc.content_attachment_url as doc_binary_id,
        dc.content_attachment_size as doc_size_bytes,
        dc.content_attachment_title as doc_title,
        setting.context_practice_setting_coding_display as doc_practice_setting,
        setting.context_practice_setting_coding_code as doc_practice_code,
        de.context_encounter_reference as doc_encounter_ref,
        dt.type_coding_display as doc_type_coding_display
    FROM {DATABASE}.document_reference dr
    JOIN {DATABASE}.document_reference_content dc 
        ON dc.document_reference_id = dr.id
    LEFT JOIN {DATABASE}.document_reference_context_practice_setting_coding setting 
        ON setting.document_reference_id = dr.id
    LEFT JOIN {DATABASE}.document_reference_context_encounter de
        ON de.document_reference_id = dr.id
    LEFT JOIN {DATABASE}.document_reference_type_coding dt
        ON dt.document_reference_id = dr.id
    WHERE dr.subject_reference = '{patient_id}'
      AND (
          -- Primary filter: Radiation Oncology practice setting
          setting.context_practice_setting_coding_display = 'Radiation Oncology'
          -- OR: Non-HTML/RTF with oncology-related setting and RT keywords
          OR (
              dc.content_attachment_content_type IN (
                  'application/pdf', 'image/tiff', 'image/jpeg', 'image/png'
              )
              AND setting.context_practice_setting_coding_display IN ('Oncology', 'Hematology Oncology', 'Radiology')
              AND (
                  LOWER(dr.description) LIKE '%radiation%'
                  OR LOWER(dr.description) LIKE '%radiotherapy%'
                  OR LOWER(dr.description) LIKE '%rad onc%'
                  OR LOWER(dr.description) LIKE '%xrt%'
                  OR LOWER(dr.description) LIKE '%beam%'
                  OR LOWER(dr.type_text) LIKE '%radiation%'
                  OR LOWER(dt.type_coding_display) LIKE '%radiation%'
              )
          )
      )
    ORDER BY dr.date DESC
    """
    
    print("\nQuerying document_reference tables...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        print("No radiation oncology documents found.")
        return pd.DataFrame()
    
    # Parse results
    columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    data = []
    
    for row in results['ResultSet']['Rows'][1:]:
        data.append([col.get('VarCharValue', '') for col in row['Data']])
    
    df = pd.DataFrame(data, columns=columns)
    
    print(f"Total RT-related documents: {len(df)}")
    
    if len(df) > 0:
        # Categorize by MIME type
        df['doc_format_category'] = 'Other'
        df.loc[df['doc_mime_type'].str.contains('pdf', case=False, na=False), 'doc_format_category'] = 'PDF'
        df.loc[df['doc_mime_type'].str.contains('tiff|tif', case=False, na=False, regex=True), 'doc_format_category'] = 'TIFF Image'
        df.loc[df['doc_mime_type'].str.contains('jpeg|jpg', case=False, na=False, regex=True), 'doc_format_category'] = 'JPEG Image'
        df.loc[df['doc_mime_type'].str.contains('png', case=False, na=False), 'doc_format_category'] = 'PNG Image'
        df.loc[df['doc_mime_type'].str.contains('html', case=False, na=False), 'doc_format_category'] = 'HTML'
        df.loc[df['doc_mime_type'].str.contains('rtf', case=False, na=False), 'doc_format_category'] = 'RTF'
        
        # Flag likely external documents (PDFs and images)
        df['doc_is_likely_external'] = df['doc_format_category'].isin(['PDF', 'TIFF Image', 'JPEG Image', 'PNG Image'])
        
        # Flag documents needing additional binary retrieval in THIS workflow
        # HTML/RTF are already extracted separately via existing DocumentReference workflow
        # Only process non-HTML/RTF formats here for RT-specific content extraction
        df['doc_needs_retrieval'] = ~df['doc_format_category'].isin(['HTML', 'RTF'])
        
        # Priority scoring for manual review and retrieval
        # HIGH: PDFs from Radiation Oncology (external treatment summaries) - NEEDS RETRIEVAL
        # MEDIUM: Images from Rad Onc or PDFs from related specialties - NEEDS RETRIEVAL  
        # LOW: HTML/RTF from Rad Onc - ALREADY EXTRACTED SEPARATELY (listed but not retrieved here)
        df['doc_priority'] = 'LOW'  # Default for HTML/RTF
        df.loc[
            (df['doc_practice_setting'] == 'Radiation Oncology') & 
            (df['doc_format_category'].isin(['PDF', 'TIFF Image'])),
            'doc_priority'
        ] = 'HIGH'
        df.loc[
            (df['doc_practice_setting'] == 'Radiation Oncology') & 
            (df['doc_format_category'].isin(['JPEG Image', 'PNG Image'])),
            'doc_priority'
        ] = 'MEDIUM'
        df.loc[
            (df['doc_practice_setting'] != 'Radiation Oncology') & 
            (df['doc_format_category'].isin(['PDF', 'TIFF Image', 'JPEG Image', 'PNG Image'])),
            'doc_priority'
        ] = 'MEDIUM'
        
        print("\n✅ Document Summary:")
        print(f"\nBy Practice Setting:")
        setting_counts = df['doc_practice_setting'].value_counts()
        for setting, count in setting_counts.items():
            print(f"  {setting:40} {count:3}")
        
        print(f"\nBy Format:")
        format_counts = df['doc_format_category'].value_counts()
        for fmt, count in format_counts.items():
            print(f"  {fmt:40} {count:3}")
        
        print(f"\nBy Priority:")
        priority_counts = df['doc_priority'].value_counts()
        for priority, count in priority_counts.items():
            print(f"  {priority:40} {count:3}")
        
        external_count = df['doc_is_likely_external'].sum()
        retrieval_count = df['doc_needs_retrieval'].sum()
        print(f"\nLikely External Documents: {external_count} ({external_count/len(df)*100:.1f}%)")
        print(f"Needs Retrieval (non-HTML/RTF): {retrieval_count} ({retrieval_count/len(df)*100:.1f}%)")
        print(f"Already Extracted Elsewhere (HTML/RTF): {len(df) - retrieval_count} ({(len(df) - retrieval_count)/len(df)*100:.1f}%)")
    
    return df


def identify_treatment_courses(rad_df):
    """
    Identify distinct radiation treatment courses from appointment data.
    
    Args:
        rad_df: DataFrame with radiation treatment appointments
        
    Returns:
        List of treatment course dictionaries
    """
    if len(rad_df) == 0:
        return []
    
    print("\n" + "="*80)
    print("IDENTIFYING TREATMENT COURSES")
    print("="*80)
    
    courses = []
    
    # Find all treatment starts
    starts = rad_df[rad_df['rt_milestone'] == 'START'].sort_values('start')
    ends = rad_df[rad_df['rt_milestone'] == 'END'].sort_values('start')
    
    if len(starts) > 0:
        print(f"\nFound {len(starts)} treatment start date(s)")
        print(f"Found {len(ends)} treatment end date(s)")
        
        for idx, start_row in starts.iterrows():
            course_num = len(courses) + 1
            start_date = start_row['start'][:10] if start_row['start'] else None
            
            # Find corresponding end date (first end after this start)
            end_date = None
            end_comment = ''
            
            if len(ends) > 0:
                future_ends = ends[ends['start'] > start_row['start']]
                if len(future_ends) > 0:
                    end_row = future_ends.iloc[0]
                    end_date = end_row['start'][:10] if end_row['start'] else None
                    end_comment = end_row['comment']
            
            # Calculate duration
            duration_days = None
            duration_weeks = None
            if start_date and end_date:
                try:
                    start_dt = pd.to_datetime(start_date)
                    end_dt = pd.to_datetime(end_date)
                    duration_days = (end_dt - start_dt).days
                    duration_weeks = round(duration_days / 7, 1)
                except:
                    pass
            
            course = {
                'course_number': course_num,
                'start_date': start_date,
                'end_date': end_date,
                'duration_days': duration_days,
                'duration_weeks': duration_weeks,
                'start_comment': start_row['comment'],
                'end_comment': end_comment,
                'start_status': start_row['status'],
            }
            
            courses.append(course)
            
            print(f"\nCourse #{course_num}:")
            print(f"  Start Date: {start_date}")
            print(f"  End Date:   {end_date}")
            if duration_weeks:
                print(f"  Duration:   {duration_weeks} weeks ({duration_days} days)")
            print(f"  Comment:    {start_row['comment'][:100]}...")
    
    # Check for re-irradiation mentions
    reirrad = rad_df[rad_df['rt_milestone'] == 'RE-RT']
    if len(reirrad) > 0:
        print(f"\n🔄 Re-irradiation documented in {len(reirrad)} appointment(s)")
    
    return courses


def generate_summary_report(patient_id, consults_df, treatments_df, courses):
    """
    Generate a summary report of radiation therapy data.
    
    Args:
        patient_id: Patient ID
        consults_df: DataFrame of radiation oncology consults
        treatments_df: DataFrame of radiation treatments
        courses: List of treatment course dictionaries
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        'patient_id': patient_id,
        'extraction_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'num_rad_onc_consults': len(consults_df),
        'num_radiation_appointments': len(treatments_df),
        'num_treatment_courses': len(courses),
        'radiation_therapy_received': 'Yes' if len(treatments_df) > 0 else 'No',
        're_irradiation': 'Yes' if len(courses) > 1 or any('re-' in str(c.get('start_comment', '')).lower() for c in courses) else 'No',
    }
    
    # Add course-specific details
    for i, course in enumerate(courses, 1):
        summary[f'course_{i}_start_date'] = course.get('start_date')
        summary[f'course_{i}_end_date'] = course.get('end_date')
        summary[f'course_{i}_duration_weeks'] = course.get('duration_weeks')
    
    # Treatment techniques
    if len(treatments_df) > 0:
        techniques = []
        for idx, row in treatments_df.iterrows():
            comment = str(row['comment']).lower() if pd.notna(row['comment']) else ''
            if 'imrt' in comment:
                techniques.append('IMRT')
            if 'proton' in comment:
                techniques.append('Proton')
            if 'stereotactic' in comment or 'sbrt' in comment or 'srs' in comment:
                techniques.append('Stereotactic')
        
        summary['treatment_techniques'] = ', '.join(set(techniques)) if techniques else 'Not specified'
    
    return summary


def main():
    """Main extraction workflow."""
    
    if len(sys.argv) < 2:
        print("Usage: python extract_radiation_data.py <patient_id>")
        print("\nExample:")
        print("  python extract_radiation_data.py C1277724")
        print("  python extract_radiation_data.py eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3")
        sys.exit(1)
    
    patient_id = sys.argv[1]
    
    # Construct FHIR reference
    if not patient_id.startswith('Patient/'):
        patient_fhir_id = f'Patient/{patient_id}'
    else:
        patient_fhir_id = patient_id
        patient_id = patient_id.replace('Patient/', '')
    
    print("="*80)
    print("RADIATION THERAPY DATA EXTRACTION")
    print("="*80)
    print(f"\nPatient ID: {patient_id}")
    print(f"FHIR Reference: {patient_fhir_id}")
    print(f"Database: {DATABASE}")
    print(f"AWS Profile: {AWS_PROFILE}")
    
    # Initialize AWS session
    try:
        session = boto3.Session(profile_name=AWS_PROFILE)
        athena = session.client('athena', region_name=REGION)
        print("\n✅ AWS session initialized")
    except Exception as e:
        print(f"\n❌ Failed to initialize AWS session: {e}")
        sys.exit(1)
    
    # Extract data
    consults_df = extract_radiation_oncology_consults(athena, patient_fhir_id)
    treatments_df = extract_radiation_treatment_appointments(athena, patient_fhir_id)
    # NOTE: care_plan and service_request tables use bare patient_id (no 'Patient/' prefix)
    care_plan_notes_df = extract_care_plan_notes(athena, patient_id)
    care_plan_hierarchy_df = extract_care_plan_hierarchy(athena, patient_id)
    # NEW: service_request tables
    service_request_notes_df = extract_service_request_notes(athena, patient_id)
    service_request_reason_df = extract_service_request_reason_codes(athena, patient_id)
    # NEW: procedure tables
    procedure_rt_codes_df = extract_procedure_rt_codes(athena, patient_id)
    procedure_notes_df = extract_procedure_notes(athena, patient_id)
    # NEW: document_reference tables (external RT records)
    documents_df = extract_radiation_oncology_documents(athena, patient_id)
    
    # Identify treatment courses
    courses = identify_treatment_courses(treatments_df)
    
    # Generate summary
    summary = generate_summary_report(patient_id, consults_df, treatments_df, courses)
    
    # Add care plan summary data
    summary['num_care_plan_notes'] = len(care_plan_notes_df)
    summary['num_care_plan_hierarchy'] = len(care_plan_hierarchy_df)
    if len(care_plan_notes_df) > 0:
        summary['care_plan_notes_with_dose'] = care_plan_notes_df['cpn_contains_dose'].sum()
    else:
        summary['care_plan_notes_with_dose'] = 0
    
    # Add service_request summary data
    summary['num_service_request_notes'] = len(service_request_notes_df)
    summary['num_service_request_rt_history'] = len(service_request_reason_df)
    if len(service_request_notes_df) > 0:
        summary['service_request_notes_with_dose'] = service_request_notes_df['srn_contains_dose'].sum()
    else:
        summary['service_request_notes_with_dose'] = 0
    
    # Add procedure summary data
    summary['num_procedure_rt_codes'] = len(procedure_rt_codes_df)
    summary['num_procedure_notes'] = len(procedure_notes_df)
    if len(procedure_notes_df) > 0:
        summary['procedure_notes_with_dose'] = procedure_notes_df['pn_contains_dose'].sum()
    else:
        summary['procedure_notes_with_dose'] = 0
    
    # Add document summary data
    summary['num_rt_documents'] = len(documents_df)
    if len(documents_df) > 0:
        summary['num_rt_documents_pdf'] = (documents_df['doc_format_category'] == 'PDF').sum()
        summary['num_rt_documents_external'] = documents_df['doc_is_likely_external'].sum()
        summary['num_rt_documents_high_priority'] = (documents_df['doc_priority'] == 'HIGH').sum()
        summary['num_rt_documents_needs_retrieval'] = documents_df['doc_needs_retrieval'].sum()
    else:
        summary['num_rt_documents_pdf'] = 0
        summary['num_rt_documents_external'] = 0
        summary['num_rt_documents_high_priority'] = 0
        summary['num_rt_documents_needs_retrieval'] = 0
    
    # Print summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    print(f"\nRadiation Therapy Received: {summary['radiation_therapy_received']}")
    print(f"Number of Rad Onc Consults: {summary['num_rad_onc_consults']}")
    print(f"Number of RT Appointments:  {summary['num_radiation_appointments']}")
    print(f"Number of Treatment Courses: {summary['num_treatment_courses']}")
    print(f"Re-irradiation:             {summary['re_irradiation']}")
    print(f"\n--- Care Plan Data ---")
    print(f"Care Plan Notes (RT-related): {summary['num_care_plan_notes']}")
    print(f"Notes with Dose Info (Gy):    {summary['care_plan_notes_with_dose']}")
    print(f"Care Plan Hierarchy Links:    {summary['num_care_plan_hierarchy']}")
    print(f"\n--- Service Request Data ---")
    print(f"Service Request Notes (RT):   {summary['num_service_request_notes']}")
    print(f"Notes with Dose Info (Gy):    {summary['service_request_notes_with_dose']}")
    print(f"RT History Reason Codes:      {summary['num_service_request_rt_history']}")
    print(f"\n--- Procedure Data ---")
    print(f"Procedure RT Codes (CPT 77xxx): {summary['num_procedure_rt_codes']}")
    print(f"Procedure Notes (RT keywords):  {summary['num_procedure_notes']}")
    print(f"Notes with Dose Info (Gy):      {summary['procedure_notes_with_dose']}")
    print(f"\n--- Document Reference Data (NEW) ---")
    print(f"RT-Related Documents:          {summary['num_rt_documents']}")
    print(f"PDFs (likely external):        {summary['num_rt_documents_pdf']}")
    print(f"Likely External Docs:          {summary['num_rt_documents_external']}")
    print(f"High Priority Docs:            {summary['num_rt_documents_high_priority']}")
    print(f"Needs Retrieval (non-HTML/RTF): {summary['num_rt_documents_needs_retrieval']}")
    print(f"Note: HTML/RTF docs are already extracted via separate workflow")
    
    if 'treatment_techniques' in summary:
        print(f"\nTreatment Techniques:       {summary['treatment_techniques']}")
    
    # Save outputs
    patient_dir = OUTPUT_DIR / f'patient_{patient_id}'
    patient_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Saving results to: {patient_dir}")
    
    # Save consults
    if len(consults_df) > 0:
        consults_file = patient_dir / 'radiation_oncology_consults.csv'
        consults_df.to_csv(consults_file, index=False)
        print(f"  ✅ Saved: radiation_oncology_consults.csv ({len(consults_df)} rows)")
    
    # Save treatments
    if len(treatments_df) > 0:
        treatments_file = patient_dir / 'radiation_treatment_appointments.csv'
        treatments_df.to_csv(treatments_file, index=False)
        print(f"  ✅ Saved: radiation_treatment_appointments.csv ({len(treatments_df)} rows)")
    
    # Save courses
    if len(courses) > 0:
        courses_df = pd.DataFrame(courses)
        courses_file = patient_dir / 'radiation_treatment_courses.csv'
        courses_df.to_csv(courses_file, index=False)
        print(f"  ✅ Saved: radiation_treatment_courses.csv ({len(courses)} rows)")
    
    # Save care plan notes
    if len(care_plan_notes_df) > 0:
        notes_file = patient_dir / 'radiation_care_plan_notes.csv'
        care_plan_notes_df.to_csv(notes_file, index=False)
        print(f"  ✅ Saved: radiation_care_plan_notes.csv ({len(care_plan_notes_df)} rows)")
    
    # Save care plan hierarchy
    if len(care_plan_hierarchy_df) > 0:
        hierarchy_file = patient_dir / 'radiation_care_plan_hierarchy.csv'
        care_plan_hierarchy_df.to_csv(hierarchy_file, index=False)
        print(f"  ✅ Saved: radiation_care_plan_hierarchy.csv ({len(care_plan_hierarchy_df)} rows)")
    
    # Save service request notes
    if len(service_request_notes_df) > 0:
        sr_notes_file = patient_dir / 'service_request_notes.csv'
        service_request_notes_df.to_csv(sr_notes_file, index=False)
        print(f"  ✅ Saved: service_request_notes.csv ({len(service_request_notes_df)} rows)")
    
    # Save service request reason codes (RT history)
    if len(service_request_reason_df) > 0:
        sr_reason_file = patient_dir / 'service_request_rt_history.csv'
        service_request_reason_df.to_csv(sr_reason_file, index=False)
        print(f"  ✅ Saved: service_request_rt_history.csv ({len(service_request_reason_df)} rows)")
    
    # Save procedure RT codes
    if len(procedure_rt_codes_df) > 0:
        proc_codes_file = patient_dir / 'procedure_rt_codes.csv'
        procedure_rt_codes_df.to_csv(proc_codes_file, index=False)
        print(f"  ✅ Saved: procedure_rt_codes.csv ({len(procedure_rt_codes_df)} rows)")
    
    # Save procedure notes
    if len(procedure_notes_df) > 0:
        proc_notes_file = patient_dir / 'procedure_notes.csv'
        procedure_notes_df.to_csv(proc_notes_file, index=False)
        print(f"  ✅ Saved: procedure_notes.csv ({len(procedure_notes_df)} rows)")
    
    # Save radiation oncology documents
    if len(documents_df) > 0:
        docs_file = patient_dir / 'radiation_oncology_documents.csv'
        documents_df.to_csv(docs_file, index=False)
        print(f"  ✅ Saved: radiation_oncology_documents.csv ({len(documents_df)} rows)")
    
    # Save summary
    summary_df = pd.DataFrame([summary])
    summary_file = patient_dir / 'radiation_data_summary.csv'
    summary_df.to_csv(summary_file, index=False)
    print(f"  ✅ Saved: radiation_data_summary.csv")
    
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
    
    return summary


if __name__ == '__main__':
    main()
