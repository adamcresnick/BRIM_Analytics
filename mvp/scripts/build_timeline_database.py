#!/usr/bin/env python3
"""
Build DuckDB Timeline Database from Athena v_unified_patient_timeline

Purpose: Export unified timeline for test patient from Athena and load into DuckDB
         for agent-based temporal context queries and extraction.

Based on: TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md
Date: 2025-10-19
"""

import duckdb
import pandas as pd
import json
import boto3
import time
from datetime import datetime
from pathlib import Path

# Configuration
TEST_PATIENT_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"
AWS_PROFILE = "343218191717_AWSAdministratorAccess"
AWS_REGION = "us-east-1"
ATHENA_DATABASE = "fhir_prd_db"
ATHENA_OUTPUT_LOCATION = "s3://aws-athena-query-results-343218191717-us-east-1/"
DUCKDB_PATH = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/data/timeline.duckdb"


def execute_athena_query(query, database=ATHENA_DATABASE):
    """
    Execute Athena query and return results as pandas DataFrame
    """
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    athena_client = session.client('athena')

    # Start query execution
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
    )

    query_execution_id = response['QueryExecutionId']
    print(f"Started Athena query: {query_execution_id}")

    # Wait for query to complete
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            print(f"Query succeeded!")
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            raise Exception(f"Query {status}: {reason}")

        print(f"Query status: {status}... waiting")
        time.sleep(2)

    # Get results
    results = []
    columns = None
    paginator = athena_client.get_paginator('get_query_results')

    for page_num, page in enumerate(paginator.paginate(QueryExecutionId=query_execution_id)):
        rows = page['ResultSet']['Rows']

        # First page, first row contains column names
        if page_num == 0 and rows:
            columns = [col.get('VarCharValue', '') for col in rows[0]['Data']]
            rows = rows[1:]  # Skip header row

        # Extract data rows - handle all Athena data types
        for row in rows:
            row_data = []
            for col in row['Data']:
                # Athena returns different keys for different types:
                # VarCharValue for strings, ints, dates, etc.
                # For JSON/ARRAY, it still uses VarCharValue with JSON string
                value = col.get('VarCharValue')
                row_data.append(value)
            results.append(row_data)

    # Create DataFrame
    df = pd.DataFrame(results, columns=columns)

    print(f"Retrieved {len(df)} rows")
    return df


def export_unified_timeline_for_patient(patient_id):
    """
    Export v_unified_patient_timeline from Athena for specific patient
    """
    print(f"\n{'='*80}")
    print(f"Exporting unified timeline for patient: {patient_id}")
    print(f"{'='*80}\n")

    # Use UNLOAD to export to Parquet which preserves all data types
    # This avoids casting issues with JSON and ARRAY columns
    query = f"""
    UNLOAD (
        SELECT *
        FROM {ATHENA_DATABASE}.v_unified_patient_timeline
        WHERE patient_fhir_id = '{patient_id}'
        ORDER BY event_date
    )
    TO 's3://aws-athena-query-results-343218191717-us-east-1/timeline_export/{patient_id}/'
    WITH (format = 'PARQUET', compression = 'SNAPPY')
    """

    # Query basic fields first - test if JSON VARCHAR fields are the problem
    query = f"""
    SELECT
        patient_fhir_id,
        event_id,
        event_date,
        age_at_event_days,
        age_at_event_years,
        event_type,
        event_category,
        event_subtype,
        event_description,
        event_status,
        source_view,
        source_domain,
        source_id
    FROM {ATHENA_DATABASE}.v_unified_patient_timeline
    WHERE patient_fhir_id = '{patient_id}'
    """

    df = execute_athena_query(query)

    # Sort by event_date in pandas (couldn't do in Athena with JSON columns)
    df['event_date'] = pd.to_datetime(df['event_date'])
    df = df.sort_values('event_date').reset_index(drop=True)

    print(f"\nEvent type distribution:")
    print(df['event_type'].value_counts())

    return df


def compute_milestones(df):
    """
    Identify key milestone dates for temporal context computation
    """
    # Convert event_date to datetime first
    df = df.copy()
    df['event_date'] = pd.to_datetime(df['event_date'])

    milestones = {}

    # First diagnosis
    tumor_diagnoses = df[
        (df['event_type'] == 'Diagnosis') &
        (df['event_category'] == 'Tumor')
    ]
    if not tumor_diagnoses.empty:
        milestones['first_diagnosis_date'] = tumor_diagnoses['event_date'].min()

    # First surgery
    surgeries = df[
        (df['event_type'] == 'Procedure') &
        (df['event_category'] == 'Surgery')
    ]
    if not surgeries.empty:
        milestones['first_surgery_date'] = surgeries['event_date'].min()

    # First treatment
    treatments = df[
        (df['event_type'] == 'Medication') &
        (df['event_category'].isin(['Chemotherapy', 'Targeted Therapy']))
    ]
    if not treatments.empty:
        milestones['first_treatment_date'] = treatments['event_date'].min()

    # First radiation
    radiation = df[df['event_type'] == 'Radiation']
    if not radiation.empty:
        milestones['first_radiation_date'] = radiation['event_date'].min()

    print(f"\nMilestones identified:")
    for milestone, date in milestones.items():
        print(f"  {milestone}: {date}")

    return milestones


def compute_temporal_context(df, milestones):
    """
    Add temporal context fields: days_since_*, disease_phase, treatment_status
    Based on v_patient_disease_phases logic from TIMELINE_ARCHITECTURE_GAPS
    """
    print(f"\nComputing temporal context fields...")

    df = df.copy()
    df['event_date'] = pd.to_datetime(df['event_date'])

    # Compute days_since_* fields
    if 'first_diagnosis_date' in milestones:
        df['days_since_diagnosis'] = (df['event_date'] - milestones['first_diagnosis_date']).dt.days
    else:
        df['days_since_diagnosis'] = None

    if 'first_surgery_date' in milestones:
        df['days_since_surgery'] = (df['event_date'] - milestones['first_surgery_date']).dt.days
    else:
        df['days_since_surgery'] = None

    if 'first_treatment_date' in milestones:
        df['days_since_treatment_start'] = (df['event_date'] - milestones['first_treatment_date']).dt.days
    else:
        df['days_since_treatment_start'] = None

    # Compute disease_phase (simplified logic - can be refined)
    def compute_disease_phase(row):
        event_date = row['event_date']

        # Pre-diagnosis
        if 'first_diagnosis_date' not in milestones or event_date < milestones['first_diagnosis_date']:
            return 'Pre-diagnosis'

        # Diagnostic phase (diagnosis to surgery, max 90 days)
        if 'first_surgery_date' in milestones:
            if event_date < milestones['first_surgery_date']:
                return 'Diagnostic'

            # Post-surgical (surgery to treatment start, max 180 days)
            if 'first_treatment_date' in milestones:
                if event_date < milestones['first_treatment_date']:
                    days_since_surgery = (event_date - milestones['first_surgery_date']).days
                    if days_since_surgery <= 180:
                        return 'Post-surgical'

        # On-treatment
        if 'first_treatment_date' in milestones and event_date >= milestones['first_treatment_date']:
            # Simple heuristic: assume treatment lasts ~1 year unless we have end dates
            days_since_treatment = (event_date - milestones['first_treatment_date']).days
            if days_since_treatment <= 365:
                return 'On-treatment'
            else:
                return 'Surveillance'

        # Observation only
        return 'Observation'

    df['disease_phase'] = df.apply(compute_disease_phase, axis=1)

    # Compute treatment_status (simplified)
    def compute_treatment_status(row):
        if 'first_treatment_date' not in milestones:
            return 'Treatment-naive'

        if row['event_date'] < milestones['first_treatment_date']:
            return 'Treatment-naive'

        # Simple heuristic
        days_since_treatment = (row['event_date'] - milestones['first_treatment_date']).days
        if days_since_treatment <= 365:
            return 'On-treatment'
        else:
            return 'Off-treatment'

    df['treatment_status'] = df.apply(compute_treatment_status, axis=1)

    print(f"\nDisease phase distribution:")
    print(df['disease_phase'].value_counts())

    return df


def create_duckdb_timeline_database(db_path):
    """
    Create DuckDB database schema from TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md
    """
    print(f"\n{'='*80}")
    print(f"Creating DuckDB timeline database at: {db_path}")
    print(f"{'='*80}\n")

    # Create directory if needed
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(db_path)

    # Create patients table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id VARCHAR PRIMARY KEY,
        birth_date DATE,
        sex VARCHAR,
        race VARCHAR,
        ethnicity VARCHAR,
        first_diagnosis_date TIMESTAMP,
        first_surgery_date TIMESTAMP,
        first_treatment_date TIMESTAMP,
        first_radiation_date TIMESTAMP,
        last_followup_date TIMESTAMP,
        deceased BOOLEAN DEFAULT FALSE,
        deceased_date DATE,
        age_at_diagnosis_days INTEGER,
        age_at_surgery_days INTEGER,
        followup_duration_days INTEGER,
        extraction_date TIMESTAMP,
        data_version VARCHAR
    )
    """)
    print("✓ Created patients table")

    # Create events table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR NOT NULL,

        event_date TIMESTAMP NOT NULL,
        event_date_precision VARCHAR DEFAULT 'day',
        age_at_event_days INTEGER,
        age_at_event_years DECIMAL(5,2),

        event_type VARCHAR NOT NULL,
        event_category VARCHAR,
        event_subtype VARCHAR,
        description TEXT,
        event_status VARCHAR,
        source_view VARCHAR NOT NULL,
        source_domain VARCHAR NOT NULL,
        source_id VARCHAR,

        icd10_codes VARCHAR[],
        snomed_codes VARCHAR[],
        cpt_codes VARCHAR[],
        loinc_codes VARCHAR[],

        days_since_diagnosis INTEGER,
        days_since_surgery INTEGER,
        days_since_treatment_start INTEGER,
        disease_phase VARCHAR,
        treatment_status VARCHAR,

        metadata JSON,
        extraction_context JSON,

        extracted_from_source VARCHAR DEFAULT 'athena_v_unified_timeline',
        extraction_timestamp TIMESTAMP
    )
    """)
    print("✓ Created events table")

    # Create extracted_variables table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS extracted_variables (
        extraction_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR NOT NULL,

        source_event_id VARCHAR,
        source_document_type VARCHAR,
        source_document_date DATE,
        source_text TEXT,

        variable_name VARCHAR NOT NULL,
        variable_value VARCHAR,
        variable_confidence DECIMAL(3,2),

        event_date TIMESTAMP,
        days_since_diagnosis INTEGER,
        disease_phase VARCHAR,
        treatment_status VARCHAR,

        extraction_method VARCHAR,
        extraction_timestamp TIMESTAMP,
        model_version VARCHAR,
        prompt_version VARCHAR,

        validated BOOLEAN DEFAULT FALSE,
        validation_status VARCHAR,
        validation_notes TEXT,

        conflicts_with_extraction_ids VARCHAR[],
        conflict_resolution_rule VARCHAR,

        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
        FOREIGN KEY (source_event_id) REFERENCES events(event_id)
    )
    """)
    print("✓ Created extracted_variables table")

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_patient_date ON events(patient_id, event_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(event_category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_disease_phase ON events(disease_phase)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_extractions_patient_variable ON extracted_variables(patient_id, variable_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_extractions_source_event ON extracted_variables(source_event_id)")

    print("✓ Created indexes")

    return conn


def get_patient_birth_date(patient_id):
    """
    Query patient birth date from Athena
    """
    query = f"""
    SELECT pd_birth_date
    FROM {ATHENA_DATABASE}.v_patient_demographics
    WHERE patient_fhir_id = '{patient_id}'
    LIMIT 1
    """
    result = execute_athena_query(query)
    if not result.empty and result.iloc[0]['pd_birth_date']:
        return pd.to_datetime(result.iloc[0]['pd_birth_date'])
    return None


def load_timeline_into_duckdb(df, milestones, conn, patient_id):
    """
    Load timeline DataFrame into DuckDB events table
    """
    print(f"\n{'='*80}")
    print(f"Loading timeline into DuckDB")
    print(f"{'='*80}\n")

    # Get patient birth date
    birth_date = get_patient_birth_date(patient_id)
    if birth_date:
        print(f"  Patient birth date: {birth_date}")

    # Insert patient record
    patient_data = {
        'patient_id': patient_id,
        'birth_date': birth_date,
        'first_diagnosis_date': milestones.get('first_diagnosis_date'),
        'first_surgery_date': milestones.get('first_surgery_date'),
        'first_treatment_date': milestones.get('first_treatment_date'),
        'first_radiation_date': milestones.get('first_radiation_date'),
        'extraction_date': datetime.now(),
        'data_version': 'v2.2'
    }

    conn.execute("""
        INSERT OR REPLACE INTO patients
        (patient_id, first_diagnosis_date, first_surgery_date, first_treatment_date,
         first_radiation_date, extraction_date, data_version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        patient_data['patient_id'],
        patient_data['first_diagnosis_date'],
        patient_data['first_surgery_date'],
        patient_data['first_treatment_date'],
        patient_data['first_radiation_date'],
        patient_data['extraction_date'],
        patient_data['data_version']
    ])
    print(f"✓ Inserted patient record for {patient_id}")

    # Prepare events for insertion
    df_insert = df.copy()
    df_insert['patient_id'] = df_insert['patient_fhir_id']
    df_insert['description'] = df_insert['event_description']
    df_insert['extraction_timestamp'] = datetime.now()

    # Filter out rows with NULL event_date or NULL event_id
    df_insert = df_insert[df_insert['event_date'].notna() & df_insert['event_id'].notna()]
    print(f"  Filtered to {len(df_insert)} events with valid dates and IDs")

    # Convert string fields to proper types
    df_insert['age_at_event_days'] = pd.to_numeric(df_insert['age_at_event_days'], errors='coerce')
    df_insert['age_at_event_years'] = pd.to_numeric(df_insert['age_at_event_years'], errors='coerce')

    # Compute missing age_at_event_days from birth_date
    if birth_date:
        df_insert['event_date_dt'] = pd.to_datetime(df_insert['event_date'])
        missing_age = df_insert['age_at_event_days'].isna()
        df_insert.loc[missing_age, 'age_at_event_days'] = \
            (df_insert.loc[missing_age, 'event_date_dt'] - birth_date).dt.days
        df_insert.loc[missing_age, 'age_at_event_years'] = \
            df_insert.loc[missing_age, 'age_at_event_days'] / 365.25
        computed_count = missing_age.sum()
        print(f"  Computed age for {computed_count} events from birth date")

    # Parse JSON fields
    for json_col in ['event_metadata', 'extraction_context', 'icd10_codes', 'snomed_codes', 'cpt_codes', 'loinc_codes']:
        if json_col in df_insert.columns:
            df_insert[json_col] = df_insert[json_col].apply(
                lambda x: json.loads(x) if pd.notna(x) and isinstance(x, str) else x
            )

    # Insert events
    conn.execute("DELETE FROM events WHERE patient_id = ?", [patient_id])

    for idx, row in df_insert.iterrows():
        # Make event_id unique by adding row index if duplicate
        event_id = f"{row['event_id']}_{idx}" if df_insert['event_id'].duplicated().iloc[idx] else row['event_id']

        # Convert JSON fields to string for DuckDB storage
        metadata_json = json.dumps(row['event_metadata']) if pd.notna(row.get('event_metadata')) else None
        extraction_context_json = json.dumps(row['extraction_context']) if pd.notna(row.get('extraction_context')) else None

        conn.execute("""
            INSERT INTO events (
                event_id, patient_id, event_date, age_at_event_days, age_at_event_years,
                event_type, event_category, event_subtype, description, event_status,
                source_view, source_domain, source_id,
                days_since_diagnosis, days_since_surgery, days_since_treatment_start,
                disease_phase, treatment_status,
                metadata, extraction_context,
                extraction_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            event_id,
            row['patient_id'],
            pd.to_datetime(row['event_date']),
            int(row['age_at_event_days']) if pd.notna(row['age_at_event_days']) else None,
            float(row['age_at_event_years']) if pd.notna(row['age_at_event_years']) else None,
            row['event_type'],
            row['event_category'],
            row['event_subtype'],
            row['description'],
            row['event_status'],
            row['source_view'],
            row['source_domain'],
            row['source_id'],
            int(row['days_since_diagnosis']) if pd.notna(row['days_since_diagnosis']) else None,
            int(row['days_since_surgery']) if pd.notna(row['days_since_surgery']) else None,
            int(row['days_since_treatment_start']) if pd.notna(row['days_since_treatment_start']) else None,
            row['disease_phase'],
            row['treatment_status'],
            metadata_json,
            extraction_context_json,
            row['extraction_timestamp']
        ])

    print(f"✓ Inserted {len(df_insert)} events")

    # Verify insertion
    count = conn.execute("SELECT COUNT(*) FROM events WHERE patient_id = ?", [patient_id]).fetchone()[0]
    print(f"✓ Verified {count} events in database")


def main():
    """
    Main workflow: Export timeline from Athena → Load into DuckDB
    """
    print(f"\n{'='*80}")
    print(f"BUILD DUCKDB TIMELINE DATABASE")
    print(f"Patient: {TEST_PATIENT_ID}")
    print(f"{'='*80}\n")

    # Step 1: Export from Athena
    df = export_unified_timeline_for_patient(TEST_PATIENT_ID)

    # Step 2: Compute milestones
    milestones = compute_milestones(df)

    # Step 3: Add temporal context
    df = compute_temporal_context(df, milestones)

    # Step 4: Create DuckDB database
    conn = create_duckdb_timeline_database(DUCKDB_PATH)

    # Step 5: Load into DuckDB
    load_timeline_into_duckdb(df, milestones, conn, TEST_PATIENT_ID)

    # Step 6: Summary statistics
    print(f"\n{'='*80}")
    print(f"TIMELINE DATABASE SUMMARY")
    print(f"{'='*80}\n")

    print("Event counts by type:")
    result = conn.execute("""
        SELECT event_type, COUNT(*) as count
        FROM events
        WHERE patient_id = ?
        GROUP BY event_type
        ORDER BY count DESC
    """, [TEST_PATIENT_ID]).fetchall()
    for row in result:
        print(f"  {row[0]:30s} {row[1]:5d}")

    print(f"\nImaging events:")
    imaging_count = conn.execute("""
        SELECT COUNT(*)
        FROM events
        WHERE patient_id = ?
          AND event_type = 'Imaging'
    """, [TEST_PATIENT_ID]).fetchone()[0]
    print(f"  {imaging_count} imaging events total")

    print(f"\n{'='*80}")
    print(f"✅ TIMELINE DATABASE CREATED SUCCESSFULLY")
    print(f"Database location: {DUCKDB_PATH}")
    print(f"{'='*80}\n")

    conn.close()


if __name__ == "__main__":
    main()
