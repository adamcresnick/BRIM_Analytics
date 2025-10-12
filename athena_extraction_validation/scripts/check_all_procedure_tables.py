#!/usr/bin/env python3
"""
Comprehensive Procedure Table Discovery and Data Check

This script:
1. Discovers ALL procedure-related tables in fhir_prd_db
2. Checks each table for data presence
3. Reports table sizes and structure
4. Identifies which tables have patient data

Purpose: Understand complete procedure schema landscape before RT content analysis

Author: Clinical Data Extraction Team
Date: 2025-10-12
"""

import boto3
import time
import sys
from pathlib import Path

# Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
REGION = 'us-east-1'
DATABASE = 'fhir_prd_db'
S3_OUTPUT = 's3://aws-athena-query-results-343218191717-us-east-1/'

# Known RT patient for testing
TEST_PATIENT_ID = 'eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3'


def execute_athena_query(athena_client, query, database, max_wait=60):
    """Execute Athena query and wait for results."""
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': S3_OUTPUT}
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait for completion
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
        
        print(f"    ⏱️  Query timeout after {max_wait}s")
        return None
        
    except Exception as e:
        print(f"    ❌ Error: {str(e)}")
        return None


def discover_procedure_tables(athena_client):
    """
    Discover all procedure-related tables in the database.
    
    Returns:
        list: Table names starting with 'procedure'
    """
    print("="*80)
    print("DISCOVERING PROCEDURE TABLES")
    print("="*80)
    
    query = f"SHOW TABLES IN {DATABASE}"
    
    print(f"\nQuerying SHOW TABLES...")
    results = execute_athena_query(athena_client, query, DATABASE)
    
    if not results:
        print("Failed to get table list!")
        return []
    
    # Extract table names
    all_tables = []
    for row in results['ResultSet']['Rows'][1:]:  # Skip header
        table_name = row['Data'][0].get('VarCharValue', '')
        if table_name:
            all_tables.append(table_name)
    
    # Filter for procedure tables
    procedure_tables = [t for t in all_tables if t.startswith('procedure')]
    
    print(f"\n✅ Found {len(procedure_tables)} procedure-related tables:")
    for i, table in enumerate(sorted(procedure_tables), 1):
        print(f"  {i:2}. {table}")
    
    return sorted(procedure_tables)


def check_table_structure(athena_client, table_name):
    """
    Get column information for a table.
    
    Returns:
        list: Column names and types
    """
    query = f"DESCRIBE {DATABASE}.{table_name}"
    
    results = execute_athena_query(athena_client, query, DATABASE, max_wait=30)
    
    if not results:
        return []
    
    columns = []
    for row in results['ResultSet']['Rows']:
        if len(row['Data']) >= 2:
            col_name = row['Data'][0].get('VarCharValue', '')
            col_type = row['Data'][1].get('VarCharValue', '')
            if col_name and col_type and col_name != 'col_name':  # Skip header
                columns.append({'name': col_name, 'type': col_type})
    
    return columns


def check_table_row_count(athena_client, table_name):
    """
    Get approximate row count for a table.
    
    Returns:
        int: Number of rows, or None if query fails
    """
    query = f"SELECT COUNT(*) as row_count FROM {DATABASE}.{table_name}"
    
    results = execute_athena_query(athena_client, query, DATABASE, max_wait=120)
    
    if not results or len(results['ResultSet']['Rows']) <= 1:
        return None
    
    try:
        count = int(results['ResultSet']['Rows'][1]['Data'][0].get('VarCharValue', '0'))
        return count
    except:
        return None


def check_patient_data(athena_client, table_name, columns):
    """
    Check if table has data for test patient.
    Uses common FHIR reference patterns.
    
    Returns:
        dict: Patient data check results
    """
    # Look for common patient reference columns
    patient_ref_columns = [
        'subject_reference',
        'patient_reference',
        'subject',
        'patient'
    ]
    
    # Find which column exists
    col_names = [c['name'] for c in columns]
    patient_col = None
    
    for ref_col in patient_ref_columns:
        if ref_col in col_names:
            patient_col = ref_col
            break
    
    if not patient_col:
        return {
            'has_patient_column': False,
            'patient_col': None,
            'patient_count': None
        }
    
    # Check for test patient (try with and without 'Patient/' prefix)
    query = f"""
    SELECT COUNT(*) as count
    FROM {DATABASE}.{table_name}
    WHERE {patient_col} = '{TEST_PATIENT_ID}'
       OR {patient_col} = 'Patient/{TEST_PATIENT_ID}'
    """
    
    results = execute_athena_query(athena_client, query, DATABASE, max_wait=60)
    
    patient_count = None
    if results and len(results['ResultSet']['Rows']) > 1:
        try:
            patient_count = int(results['ResultSet']['Rows'][1]['Data'][0].get('VarCharValue', '0'))
        except:
            patient_count = None
    
    return {
        'has_patient_column': True,
        'patient_col': patient_col,
        'patient_count': patient_count
    }


def analyze_all_procedure_tables(athena_client):
    """
    Comprehensive analysis of all procedure tables.
    
    Returns:
        dict: Analysis results for each table
    """
    print("\n" + "="*80)
    print("COMPREHENSIVE PROCEDURE TABLE ANALYSIS")
    print("="*80)
    
    # Discover tables
    procedure_tables = discover_procedure_tables(athena_client)
    
    if not procedure_tables:
        print("\n❌ No procedure tables found!")
        return {}
    
    # Analyze each table
    results = {}
    
    for i, table_name in enumerate(procedure_tables, 1):
        print(f"\n{'='*80}")
        print(f"TABLE {i}/{len(procedure_tables)}: {table_name}")
        print(f"{'='*80}")
        
        # Get structure
        print("  → Checking structure...")
        columns = check_table_structure(athena_client, table_name)
        print(f"     ✓ {len(columns)} columns")
        
        # Get row count
        print("  → Counting rows...")
        row_count = check_table_row_count(athena_client, table_name)
        if row_count is not None:
            print(f"     ✓ {row_count:,} rows")
        else:
            print(f"     ✗ Could not count rows")
        
        # Check patient data
        if row_count and row_count > 0:
            print(f"  → Checking test patient data...")
            patient_info = check_patient_data(athena_client, table_name, columns)
            
            if patient_info['has_patient_column']:
                print(f"     ✓ Patient column: {patient_info['patient_col']}")
                if patient_info['patient_count'] is not None:
                    if patient_info['patient_count'] > 0:
                        print(f"     ✓ Test patient: {patient_info['patient_count']} rows")
                    else:
                        print(f"     ○ Test patient: no data")
            else:
                print(f"     ○ No patient reference column found")
        else:
            patient_info = {'has_patient_column': False, 'patient_col': None, 'patient_count': None}
        
        # Store results
        results[table_name] = {
            'columns': columns,
            'row_count': row_count,
            'patient_info': patient_info
        }
    
    return results


def print_summary(results):
    """Print summary of analysis results."""
    print("\n" + "="*80)
    print("SUMMARY REPORT")
    print("="*80)
    
    # Tables with data
    tables_with_data = {k: v for k, v in results.items() if v['row_count'] and v['row_count'] > 0}
    print(f"\n📊 Tables with Data: {len(tables_with_data)}/{len(results)}")
    print("-" * 80)
    
    if tables_with_data:
        # Sort by row count
        sorted_tables = sorted(tables_with_data.items(), key=lambda x: x[1]['row_count'], reverse=True)
        
        print(f"\n{'Table Name':<40} {'Rows':>12} {'Patient Col':<20} {'Test Patient':>12}")
        print("-" * 90)
        
        for table_name, data in sorted_tables:
            row_count = f"{data['row_count']:,}"
            patient_col = data['patient_info']['patient_col'] or 'N/A'
            patient_count = data['patient_info']['patient_count']
            
            if patient_count is not None and patient_count > 0:
                patient_str = f"✓ {patient_count}"
            elif patient_count == 0:
                patient_str = "○ none"
            else:
                patient_str = "?"
            
            print(f"{table_name:<40} {row_count:>12} {patient_col:<20} {patient_str:>12}")
    
    # Tables with test patient data
    patient_tables = {k: v for k, v in results.items() 
                     if v['patient_info']['patient_count'] and v['patient_info']['patient_count'] > 0}
    
    print(f"\n✓ Tables with Test Patient Data: {len(patient_tables)}")
    if patient_tables:
        for table_name in sorted(patient_tables.keys()):
            count = patient_tables[table_name]['patient_info']['patient_count']
            col = patient_tables[table_name]['patient_info']['patient_col']
            print(f"  • {table_name:<40} {count:3} rows (via {col})")
    
    # Key findings
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    
    parent_table = results.get('procedure')
    if parent_table and parent_table['row_count']:
        print(f"\n📋 procedure (parent table):")
        print(f"   • Total rows: {parent_table['row_count']:,}")
        print(f"   • Columns: {len(parent_table['columns'])}")
        if parent_table['patient_info']['patient_count']:
            print(f"   • Test patient rows: {parent_table['patient_info']['patient_count']}")
    
    # Child/sub-schema tables
    child_tables = {k: v for k, v in results.items() 
                   if k != 'procedure' and v['row_count'] and v['row_count'] > 0}
    
    if child_tables:
        print(f"\n📑 Child/Sub-schema Tables ({len(child_tables)}):")
        for table_name in sorted(child_tables.keys()):
            data = child_tables[table_name]
            print(f"   • {table_name}:")
            print(f"     - Rows: {data['row_count']:,}")
            if data['patient_info']['patient_count']:
                print(f"     - Test patient: {data['patient_info']['patient_count']} rows")
    
    # Tables to investigate further
    investigate = {k: v for k, v in tables_with_data.items() 
                   if v['patient_info']['patient_count'] and v['patient_info']['patient_count'] > 0}
    
    if investigate:
        print(f"\n🔍 Tables for RT Content Analysis ({len(investigate)}):")
        print("   These tables have test patient data and should be analyzed for RT content:")
        for table_name in sorted(investigate.keys()):
            print(f"   • {table_name}")


def main():
    """Main execution function."""
    print("\n" + "="*80)
    print("PROCEDURE SCHEMA COMPREHENSIVE ASSESSMENT")
    print("="*80)
    print(f"Database: {DATABASE}")
    print(f"Test Patient ID: {TEST_PATIENT_ID}")
    print("="*80)
    
    # Initialize Athena client
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    athena = session.client('athena')
    
    # Run analysis
    results = analyze_all_procedure_tables(athena)
    
    if not results:
        print("\n❌ Analysis failed - no results")
        return 1
    
    # Print summary
    print_summary(results)
    
    # Next steps
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Review tables with test patient data")
    print("2. Run RT content analysis on promising tables")
    print("3. Check for text fields that might contain RT keywords")
    print("4. Analyze procedure codes (CPT, SNOMED) for RT procedures")
    
    print("\n✅ Procedure schema assessment complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
