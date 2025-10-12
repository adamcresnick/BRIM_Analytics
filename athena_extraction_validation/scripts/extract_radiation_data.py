#!/usr/bin/env python3
"""
Extract Radiation Oncology Data from Athena FHIR Database

This script extracts comprehensive radiation therapy data including:
- Radiation oncology consults (from appointment_service_type)
- Treatment appointments (simulations, start, end)
- Treatment timeline reconstruction
- Re-irradiation identification

Author: Clinical Data Extraction Team
Date: 2025-10-12
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
DATABASE = 'fhir_v2_prd_db'
S3_OUTPUT = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / 'staging_files'

# Search terms for radiation therapy identification
RADIATION_SEARCH_TERMS = [
    'radiation',
    'radiotherapy',
    'rad onc',
    'imrt',
    'xrt',
    'rt simulation',
    'rt sim',
    're-irradiation',
    'reirradiation',
    'proton',
    'photon',
    'intensity modulated',
    'stereotactic',
    'sbrt',
    'srs',
    'cranial radiation',
    'csi',  # Craniospinal irradiation
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
    
    # Identify treatment courses
    courses = identify_treatment_courses(treatments_df)
    
    # Generate summary
    summary = generate_summary_report(patient_id, consults_df, treatments_df, courses)
    
    # Print summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    print(f"\nRadiation Therapy Received: {summary['radiation_therapy_received']}")
    print(f"Number of Rad Onc Consults: {summary['num_rad_onc_consults']}")
    print(f"Number of RT Appointments:  {summary['num_radiation_appointments']}")
    print(f"Number of Treatment Courses: {summary['num_treatment_courses']}")
    print(f"Re-irradiation:             {summary['re_irradiation']}")
    
    if 'treatment_techniques' in summary:
        print(f"Treatment Techniques:       {summary['treatment_techniques']}")
    
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
