#!/usr/bin/env python3
"""
Extract ALL encounters and appointments metadata from patient configuration
Purpose: Comprehensive data dump for analysis before implementing filtering logic
"""

import boto3
import pandas as pd
import time
import json
from datetime import datetime
from pathlib import Path

class AllEncountersExtractor:
    def __init__(self, aws_profile: str, database: str, patient_config: dict):
        """Initialize AWS Athena connection"""
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.s3_output = 's3://aws-athena-query-results-343218191717-us-east-1/'
        
        # Load patient details from config
        self.patient_fhir_id = patient_config['fhir_id']
        self.output_dir = Path(patient_config['output_dir'])
        
        # Parse birth date if provided (optional)
        if patient_config.get('birth_date'):
            self.birth_date = datetime.strptime(patient_config['birth_date'], '%Y-%m-%d')
        else:
            self.birth_date = None
        
        print(f"\n{'='*80}")
        print(f"📊 ALL ENCOUNTERS & APPOINTMENTS METADATA EXTRACTOR")
        print(f"{'='*80}")
        print(f"Patient FHIR ID: {self.patient_fhir_id}")
        if self.birth_date:
            print(f"Birth Date: {self.birth_date.strftime('%Y-%m-%d')}")
        print(f"Output Directory: {self.output_dir}")
        print(f"Database: {self.database}")
        print(f"{'='*80}\n")
    
    def execute_query(self, query: str, description: str) -> list:
        """Execute Athena query and return results"""
        print(f"🔍 {description}...", end=' ', flush=True)
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.s3_output}
            )
            
            query_id = response['QueryExecutionId']
            
            # Wait for query completion
            for _ in range(60):  # Increased timeout
                status = self.athena.get_query_execution(QueryExecutionId=query_id)
                state = status['QueryExecution']['Status']['State']
                
                if state == 'SUCCEEDED':
                    break
                elif state in ['FAILED', 'CANCELLED']:
                    reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    print(f"✗ Query {state}: {reason}")
                    return []
                
                time.sleep(2)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
            
            # Parse results
            data_rows = []
            if len(results['ResultSet']['Rows']) > 1:
                columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
                
                for row in results['ResultSet']['Rows'][1:]:
                    row_data = {}
                    for i, col in enumerate(columns):
                        value = row['Data'][i].get('VarCharValue', '') if i < len(row['Data']) else ''
                        row_data[col] = value
                    data_rows.append(row_data)
            
            print(f"✓ ({len(data_rows)} rows)")
            return data_rows
            
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            return []
    
    def calculate_age_days(self, date_str: str) -> int:
        """Calculate age in days from date string (only if birth_date provided)"""
        if not date_str or not self.birth_date:
            return None
        try:
            date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return (date_obj - self.birth_date).days
        except:
            return None
    
    def extract_main_encounters(self) -> pd.DataFrame:
        """Extract all encounters from main encounter table"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING MAIN ENCOUNTERS TABLE")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            e.id as encounter_fhir_id,
            e.status,
            e.class_code,
            e.class_display,
            e.service_type_text,
            e.priority_text,
            e.period_start,
            e.period_end,
            e.length_value,
            e.length_unit,
            e.service_provider_display,
            e.part_of_reference
        FROM {self.database}.encounter e
        WHERE e.subject_reference = '{self.patient_fhir_id}'
        ORDER BY e.period_start
        """
        
        encounters = self.execute_query(query, "Query main encounters table")
        
        if not encounters:
            return pd.DataFrame()
        
        df = pd.DataFrame(encounters)
        
        # Calculate age in days
        df['age_at_encounter_days'] = df['period_start'].apply(self.calculate_age_days)
        
        # Calculate encounter date (for readability)
        df['encounter_date'] = df['period_start'].str[:10]
        
        # Reorder columns
        cols = ['encounter_fhir_id', 'encounter_date', 'age_at_encounter_days', 'status', 
                'class_code', 'class_display', 'service_type_text', 'priority_text',
                'period_start', 'period_end', 'length_value', 'length_unit',
                'service_provider_display', 'part_of_reference']
        
        df = df[cols]
        
        print(f"\n📊 Summary:")
        print(f"  Total encounters: {len(df)}")
        print(f"  Date range: {df['encounter_date'].min()} to {df['encounter_date'].max()}")
        print(f"  Age range: {df['age_at_encounter_days'].min()} to {df['age_at_encounter_days'].max()} days")
        print(f"\n  Class Display breakdown:")
        print(df['class_display'].value_counts().to_string())
        
        return df
    
    def extract_encounter_types(self) -> pd.DataFrame:
        """Extract encounter types from subtable"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING ENCOUNTER TYPES")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            et.encounter_id,
            et.type_coding,
            et.type_text
        FROM {self.database}.encounter_type et
        WHERE et.encounter_id IN (
            SELECT id 
            FROM {self.database}.encounter 
            WHERE subject_reference = '{self.patient_fhir_id}'
        )
        """
        
        types = self.execute_query(query, "Query encounter_type subtable")
        
        if not types:
            return pd.DataFrame()
        
        df = pd.DataFrame(types)
        print(f"\n📊 Found {len(df)} encounter type records")
        if not df.empty and 'type_text' in df.columns:
            print(f"\n  Type breakdown:")
            print(df['type_text'].value_counts().to_string())
        
        return df
    
    def extract_encounter_reasons(self) -> pd.DataFrame:
        """Extract encounter reason codes"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING ENCOUNTER REASON CODES")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            erc.encounter_id,
            erc.reason_code_coding,
            erc.reason_code_text
        FROM {self.database}.encounter_reason_code erc
        WHERE erc.encounter_id IN (
            SELECT id 
            FROM {self.database}.encounter 
            WHERE subject_reference = '{self.patient_fhir_id}'
        )
        """
        
        reasons = self.execute_query(query, "Query encounter_reason_code subtable")
        
        if not reasons:
            return pd.DataFrame()
        
        df = pd.DataFrame(reasons)
        print(f"\n📊 Found {len(df)} encounter reason records")
        if not df.empty and 'reason_code_text' in df.columns:
            print(f"\n  Reason breakdown:")
            print(df['reason_code_text'].value_counts().head(10).to_string())
        
        return df
    
    def extract_encounter_diagnoses(self) -> pd.DataFrame:
        """Extract encounter diagnosis linkages"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING ENCOUNTER DIAGNOSES")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            ed.encounter_id,
            ed.diagnosis_condition_reference,
            ed.diagnosis_condition_display,
            ed.diagnosis_use_coding,
            ed.diagnosis_rank
        FROM {self.database}.encounter_diagnosis ed
        WHERE ed.encounter_id IN (
            SELECT id 
            FROM {self.database}.encounter 
            WHERE subject_reference = '{self.patient_fhir_id}'
        )
        """
        
        diagnoses = self.execute_query(query, "Query encounter_diagnosis subtable")
        
        if not diagnoses:
            return pd.DataFrame()
        
        df = pd.DataFrame(diagnoses)
        print(f"\n📊 Found {len(df)} encounter diagnosis records")
        if not df.empty and 'diagnosis_condition_display' in df.columns:
            print(f"\n  Diagnosis breakdown:")
            print(df['diagnosis_condition_display'].value_counts().head(10).to_string())
        
        return df
    
    def extract_encounter_appointments(self) -> pd.DataFrame:
        """Extract encounter-appointment linkages"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING ENCOUNTER-APPOINTMENT LINKS")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            ea.encounter_id,
            ea.appointment_reference
        FROM {self.database}.encounter_appointment ea
        WHERE ea.encounter_id IN (
            SELECT id 
            FROM {self.database}.encounter 
            WHERE subject_reference = '{self.patient_fhir_id}'
        )
        """
        
        appts = self.execute_query(query, "Query encounter_appointment subtable")
        
        if not appts:
            return pd.DataFrame()
        
        df = pd.DataFrame(appts)
        print(f"\n📊 Found {len(df)} encounter-appointment links")
        
        return df
    
    def extract_appointments(self) -> pd.DataFrame:
        """Extract all appointments via appointment_participant pathway
        
        NOTE: This uses the appointment_participant table, NOT encounter_appointment.
        The encounter_appointment table links appointments to encounters, but appointment_participant
        links appointments to patients directly. This is the correct pathway for patient data extraction.
        """
        print(f"\n{'='*80}")
        print("📋 EXTRACTING APPOINTMENTS TABLE (via appointment_participant)")
        print(f"{'='*80}\n")
        
        # Use appointment_participant pathway (CORRECT approach)
        # NOTE: Athena does NOT support column aliasing with JOINs in this context
        # Must use SELECT a.* and rename columns in pandas for table prefixes
        # Data uses 'Patient/{fhir_id}' format in participant_actor_reference
        query = f"""
        SELECT DISTINCT a.*
        FROM {self.database}.appointment a
        JOIN {self.database}.appointment_participant ap ON a.id = ap.appointment_id
        WHERE ap.participant_actor_reference = 'Patient/{self.patient_fhir_id}'
        ORDER BY a.start
        """
        
        appointments = self.execute_query(query, "Query appointment table via appointment_participant")
        
        if not appointments:
            return pd.DataFrame()
        
        df = pd.DataFrame(appointments)
        
        # Rename columns to add appt_ prefix for provenance tracking
        df = df.rename(columns={
            'id': 'appt_id',
            'status': 'appt_status',
            'appointment_type_text': 'appt_appointment_type_text',
            'description': 'appt_description',
            'start': 'appt_start',
            'end': 'appt_end',
            'minutes_duration': 'appt_minutes_duration',
            'created': 'appt_created',
            'comment': 'appt_comment',
            'patient_instruction': 'appt_patient_instruction',
            'cancelation_reason_text': 'appt_cancelation_reason_text',
            'priority': 'appt_priority'
        })
        
        # Add convenience columns
        df['appointment_fhir_id'] = df['appt_id']
        
        # Calculate age in days
        df['age_at_appointment_days'] = df['appt_start'].apply(self.calculate_age_days)
        
        # Calculate appointment date
        df['appointment_date'] = df['appt_start'].str[:10]
        
        # Reorder columns - prefixed columns come first for provenance clarity
        cols = ['appointment_fhir_id', 'appointment_date', 'age_at_appointment_days',
                'appt_id', 'appt_status', 'appt_appointment_type_text', 'appt_description', 
                'appt_start', 'appt_end', 'appt_minutes_duration', 'appt_created', 
                'appt_comment', 'appt_patient_instruction', 'appt_cancelation_reason_text', 'appt_priority',
                'ap_participant_actor_reference', 'ap_participant_actor_type', 'ap_participant_required',
                'ap_participant_status', 'ap_participant_period_start', 'ap_participant_period_end']
        
        # Only include columns that exist in the dataframe
        cols = [c for c in cols if c in df.columns]
        df = df[cols]
        
        print(f"\n📊 Summary:")
        print(f"  Total appointments: {len(df)}")
        if not df.empty:
            print(f"  Date range: {df['appointment_date'].min()} to {df['appointment_date'].max()}")
            print(f"  Age range: {df['age_at_appointment_days'].min()} to {df['age_at_appointment_days'].max()} days")
            if 'appt_appointment_type_text' in df.columns:
                print(f"\n  Appointment type breakdown:")
                print(df['appt_appointment_type_text'].value_counts().to_string())
        
        return df
    
    def extract_encounter_service_types(self) -> pd.DataFrame:
        """Extract encounter service type coding details"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING ENCOUNTER SERVICE TYPE CODING")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            estc.encounter_id,
            estc.service_type_coding_system,
            estc.service_type_coding_code,
            estc.service_type_coding_display
        FROM {self.database}.encounter_service_type_coding estc
        WHERE estc.encounter_id IN (
            SELECT id 
            FROM {self.database}.encounter 
            WHERE subject_reference = '{self.patient_fhir_id}'
        )
        """
        
        service_types = self.execute_query(query, "Query encounter_service_type_coding subtable")
        
        if not service_types:
            return pd.DataFrame()
        
        df = pd.DataFrame(service_types)
        print(f"\n📊 Found {len(df)} service type records")
        if not df.empty and 'service_type_coding_display' in df.columns:
            print(f"\n  Service type breakdown:")
            print(df['service_type_coding_display'].value_counts().to_string())
        
        return df
    
    def extract_encounter_locations(self) -> pd.DataFrame:
        """Extract encounter location details"""
        print(f"\n{'='*80}")
        print("📋 EXTRACTING ENCOUNTER LOCATIONS")
        print(f"{'='*80}\n")
        
        query = f"""
        SELECT 
            el.encounter_id,
            el.location_location_reference,
            el.location_status
        FROM {self.database}.encounter_location el
        WHERE el.encounter_id IN (
            SELECT id 
            FROM {self.database}.encounter 
            WHERE subject_reference = '{self.patient_fhir_id}'
        )
        """
        
        locations = self.execute_query(query, "Query encounter_location subtable")
        
        if not locations:
            return pd.DataFrame()
        
        df = pd.DataFrame(locations)
        print(f"\n📊 Found {len(df)} location records")
        
        return df
    
    def merge_and_export(self, encounters_df, types_df, reasons_df, diagnoses_df, 
                         appt_links_df, appointments_df, service_types_df, locations_df):
        """Merge all data and export to CSV"""
        print(f"\n{'='*80}")
        print("🔗 MERGING ALL DATA")
        print(f"{'='*80}\n")
        
        # Start with main encounters
        merged = encounters_df.copy()
        
        # Merge encounter types (may be multiple per encounter)
        if not types_df.empty:
            types_agg = types_df.groupby('encounter_id').agg({
                'type_coding': lambda x: '; '.join(filter(None, x)),
                'type_text': lambda x: '; '.join(filter(None, x))
            }).reset_index()
            # Rename encounter_id to encounter_fhir_id for merge
            types_agg.rename(columns={'encounter_id': 'encounter_fhir_id'}, inplace=True)
            merged = merged.merge(types_agg, on='encounter_fhir_id', how='left')
        
        # Merge encounter reasons (may be multiple per encounter)
        if not reasons_df.empty:
            reasons_agg = reasons_df.groupby('encounter_id').agg({
                'reason_code_coding': lambda x: '; '.join(filter(None, x)),
                'reason_code_text': lambda x: '; '.join(filter(None, x))
            }).reset_index()
            reasons_agg.rename(columns={'encounter_id': 'encounter_fhir_id'}, inplace=True)
            merged = merged.merge(reasons_agg, on='encounter_fhir_id', how='left')
        
        # Merge encounter diagnoses (may be multiple per encounter)
        if not diagnoses_df.empty:
            diagnoses_agg = diagnoses_df.groupby('encounter_id').agg({
                'diagnosis_condition_reference': lambda x: '; '.join(filter(None, x)),
                'diagnosis_condition_display': lambda x: '; '.join(filter(None, x)),
                'diagnosis_use_coding': lambda x: '; '.join(filter(None, x)),
                'diagnosis_rank': lambda x: '; '.join(filter(None, map(str, x)))
            }).reset_index()
            diagnoses_agg.rename(columns={'encounter_id': 'encounter_fhir_id'}, inplace=True)
            merged = merged.merge(diagnoses_agg, on='encounter_fhir_id', how='left')
        
        # Merge appointment links
        if not appt_links_df.empty:
            appt_links_df.rename(columns={'encounter_id': 'encounter_fhir_id'}, inplace=True)
            merged = merged.merge(appt_links_df, on='encounter_fhir_id', how='left')
        
        # Merge service types
        if not service_types_df.empty:
            service_types_agg = service_types_df.groupby('encounter_id').agg({
                'service_type_coding_display': lambda x: '; '.join(filter(None, x))
            }).reset_index()
            service_types_agg.rename(columns={'encounter_id': 'encounter_fhir_id'}, inplace=True)
            merged = merged.merge(service_types_agg, on='encounter_fhir_id', how='left')
            merged.rename(columns={'service_type_coding_display': 'service_type_coding_display_detail'}, inplace=True)
        
        # Merge locations
        if not locations_df.empty:
            locations_agg = locations_df.groupby('encounter_id').agg({
                'location_location_reference': lambda x: '; '.join(filter(None, x)),
                'location_status': lambda x: '; '.join(filter(None, x))
            }).reset_index()
            locations_agg.rename(columns={'encounter_id': 'encounter_fhir_id'}, inplace=True)
            merged = merged.merge(locations_agg, on='encounter_fhir_id', how='left')
        
        # Add inpatient/outpatient flag based on class_display
        merged['patient_type'] = merged['class_display'].apply(
            lambda x: 'Inpatient' if 'inpatient' in str(x).lower() or 'IMP' in str(x) 
                     else 'Outpatient' if 'outpatient' in str(x).lower() or 'AMB' in str(x) or 'Appointment' in str(x)
                     else 'Unknown'
        )
        
        print(f"✓ Merged encounters: {len(merged)} rows")
        
        # Export encounters to configured output directory
        encounters_file = self.output_dir / 'encounters.csv'
        merged.to_csv(encounters_file, index=False)
        print(f"✓ Saved: {encounters_file}")
        
        # Export appointments separately
        if not appointments_df.empty:
            appointments_file = self.output_dir / 'appointments.csv'
            appointments_df.to_csv(appointments_file, index=False)
            print(f"✓ Saved: {appointments_file}")
        
        print(f"\n{'='*80}")
        print("✅ EXTRACTION COMPLETE")
        print(f"{'='*80}\n")
        
        # Print summary statistics
        print("📊 FINAL SUMMARY:")
        print(f"  Total encounters: {len(merged)}")
        print(f"  Total appointments: {len(appointments_df) if not appointments_df.empty else 0}")
        print(f"  Date range: {merged['encounter_date'].min()} to {merged['encounter_date'].max()}")
        print(f"  Age range: {merged['age_at_encounter_days'].min()} to {merged['age_at_encounter_days'].max()} days")
        
        print(f"\n  Patient Type Distribution:")
        print(merged['patient_type'].value_counts().to_string())
        
        print(f"\n  Class Display Distribution:")
        print(merged['class_display'].value_counts().to_string())
        
        if 'type_text' in merged.columns:
            print(f"\n  Encounter Type Distribution (top 10):")
            type_counts = merged['type_text'].value_counts().head(10)
            print(type_counts.to_string())
        
        return merged, appointments_df

def main():
    """Main execution"""
    # Load patient configuration
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    extractor = AllEncountersExtractor(
        aws_profile=config['aws_profile'],
        database=config['database'],
        patient_config=config
    )
    
    # Ensure output directory exists
    extractor.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract all data
    encounters_df = extractor.extract_main_encounters()
    types_df = extractor.extract_encounter_types()
    reasons_df = extractor.extract_encounter_reasons()
    diagnoses_df = extractor.extract_encounter_diagnoses()
    appt_links_df = extractor.extract_encounter_appointments()
    appointments_df = extractor.extract_appointments()
    service_types_df = extractor.extract_encounter_service_types()
    locations_df = extractor.extract_encounter_locations()
    
    # Merge and export
    if not encounters_df.empty:
        merged, appts = extractor.merge_and_export(
            encounters_df, types_df, reasons_df, diagnoses_df,
            appt_links_df, appointments_df, service_types_df, locations_df
        )
        
        print(f"\n{'='*80}")
        print("📁 OUTPUT FILES:")
        print(f"{'='*80}")
        print(f"1. encounters.csv")
        print(f"2. appointments.csv")
        print(f"\nLocation: {extractor.output_dir}/")
        print(f"{'='*80}\n")
    else:
        print("\n❌ No encounters found!")

if __name__ == '__main__':
    main()
