#!/usr/bin/env python3
"""
Explore Radiation Treatment Data in Athena Database

This script searches for radiation therapy treatments, consultations, and planning
across multiple FHIR resource types:

1. Procedures - Radiation therapy procedures (CPT codes, procedure codes)
2. Encounters - Radiation oncology visits and consultations
3. Service Requests - Radiation therapy orders and referrals
4. Diagnostic Reports - Radiation planning reports
5. Care Plans - Radiation treatment protocols

Uses patient configuration for multi-patient support.
"""

import boto3
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

class RadiationDataExplorer:
    def __init__(self, patient_config: dict):
        """Initialize with patient configuration"""
        self.patient_fhir_id = patient_config['fhir_id']
        self.database = patient_config['database']
        self.s3_output = patient_config['s3_output']
        aws_profile = patient_config['aws_profile']
        
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        
        print(f"\n{'='*80}")
        print(f"🔬 RADIATION TREATMENT DATA EXPLORATION")
        print(f"{'='*80}")
        print(f"Patient FHIR ID: {self.patient_fhir_id}")
        print(f"Database: {self.database}")
        print(f"{'='*80}\n")
    
    def execute_query(self, query: str, description: str):
        """Execute Athena query and return results"""
        print(f"\n📋 {description}")
        print(f"   Query: {query[:100]}..." if len(query) > 100 else f"   Query: {query}")
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.s3_output}
            )
            
            query_id = response['QueryExecutionId']
            
            # Wait for completion
            import time
            for _ in range(30):
                time.sleep(2)
                result = self.athena.get_query_execution(QueryExecutionId=query_id)
                status = result['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    results = self.athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
                    
                    if not results['ResultSet']['Rows'] or len(results['ResultSet']['Rows']) <= 1:
                        print(f"   ⚠️  No results found")
                        return pd.DataFrame()
                    
                    # Parse results
                    columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
                    data = []
                    for row in results['ResultSet']['Rows'][1:]:
                        data.append([col.get('VarCharValue', '') for col in row['Data']])
                    
                    df = pd.DataFrame(data, columns=columns)
                    print(f"   ✅ Found {len(df)} records")
                    return df
                    
                elif status in ['FAILED', 'CANCELLED']:
                    error = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                    print(f"   ❌ Query failed: {error}")
                    return pd.DataFrame()
            
            print(f"   ⏱️  Query timeout")
            return pd.DataFrame()
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            return pd.DataFrame()
    
    def search_radiation_procedures(self):
        """Search procedure table for radiation therapy procedures"""
        print(f"\n{'='*80}")
        print(f"1. SEARCHING PROCEDURES FOR RADIATION THERAPY")
        print(f"{'='*80}")
        
        # Search main procedure table
        query = f"""
        SELECT 
            p.id,
            p.status,
            p.code_text,
            p.performed_date_time,
            p.category_text,
            p.outcome_text,
            p.encounter_display
        FROM {self.database}.procedure p
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(p.code_text) LIKE '%radiation%'
            OR LOWER(p.code_text) LIKE '%radiotherapy%'
            OR LOWER(p.code_text) LIKE '%radiosurgery%'
            OR LOWER(p.code_text) LIKE '%brachytherapy%'
            OR LOWER(p.code_text) LIKE '%imrt%'
            OR LOWER(p.code_text) LIKE '%proton%'
            OR LOWER(p.code_text) LIKE '%gamma knife%'
            OR LOWER(p.code_text) LIKE '%cyberknife%'
            OR LOWER(p.category_text) LIKE '%radiation%'
        )
        ORDER BY p.performed_date_time DESC
        """
        
        df = self.execute_query(query, "Querying procedure table for radiation therapy")
        
        # Also check procedure codes for radiation CPT codes
        print(f"\n   🔍 Checking CPT codes for radiation therapy...")
        code_query = f"""
        SELECT DISTINCT
            pcc.procedure_id,
            pcc.code_coding_code,
            pcc.code_coding_display,
            p.performed_date_time
        FROM {self.database}.procedure_code_coding pcc
        JOIN {self.database}.procedure p ON pcc.procedure_id = p.id
        WHERE p.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(pcc.code_coding_display) LIKE '%radiation%'
            OR LOWER(pcc.code_coding_display) LIKE '%radiotherapy%'
            OR LOWER(pcc.code_coding_display) LIKE '%radiosurgery%'
            OR pcc.code_coding_code LIKE '77%'  -- Radiation oncology CPT codes
        )
        ORDER BY p.performed_date_time DESC
        """
        
        codes_df = self.execute_query(code_query, "Checking CPT codes")
        
        if not df.empty:
            print(f"\n   📊 Radiation Procedures Found:")
            for _, row in df.iterrows():
                print(f"      - {row['performed_date_time']}: {row['code_text']}")
                if row['encounter_display']:
                    print(f"        Encounter: {row['encounter_display']}")
        
        if not codes_df.empty:
            print(f"\n   📊 Radiation CPT Codes Found:")
            for _, row in codes_df.iterrows():
                print(f"      - {row['performed_date_time']}: {row['code_coding_code']} - {row['code_coding_display']}")
        
        # Combine results
        if not codes_df.empty and not df.empty:
            df = pd.concat([df, codes_df], ignore_index=True)
        elif not codes_df.empty:
            df = codes_df
        
        return df
    
    def search_radiation_encounters(self):
        """Search encounter table for radiation oncology encounters"""
        print(f"\n{'='*80}")
        print(f"2. SEARCHING ENCOUNTERS FOR RADIATION ONCOLOGY")
        print(f"{'='*80}")
        
        query = f"""
        SELECT 
            e.id,
            e.status,
            e.class_code,
            e.class_display,
            e.service_provider_display,
            e.period_start,
            e.period_end,
            e.service_type_text
        FROM {self.database}.encounter e
        WHERE e.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(e.service_provider_display) LIKE '%radiation%'
            OR LOWER(e.service_type_text) LIKE '%radiation%'
            OR LOWER(e.service_type_text) LIKE '%oncology%'
            OR LOWER(e.class_display) LIKE '%radiation%'
        )
        ORDER BY e.period_start DESC
        """
        
        df = self.execute_query(query, "Querying encounter table for radiation oncology")
        
        # Also check encounter_location table (separate related table)
        print(f"\n   🔍 Checking encounter locations...")
        location_query = f"""
        SELECT DISTINCT
            el.encounter_id,
            el.location_display,
            e.period_start,
            e.service_provider_display
        FROM {self.database}.encounter_location el
        JOIN {self.database}.encounter e ON el.encounter_id = e.id
        WHERE e.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(el.location_display) LIKE '%radiation%'
            OR LOWER(el.location_display) LIKE '%oncology%'
        )
        ORDER BY e.period_start DESC
        """
        
        location_df = self.execute_query(location_query, "Checking encounter locations")
        
        if not df.empty:
            print(f"\n   📊 Radiation Encounters Found:")
            for _, row in df.iterrows():
                print(f"      - {row['period_start']}: {row['class_display']}")
                if row['service_provider_display']:
                    print(f"        Provider: {row['service_provider_display']}")
        
        if not location_df.empty:
            print(f"\n   📊 Radiation Encounter Locations Found:")
            for _, row in location_df.iterrows():
                print(f"      - {row['period_start']}: {row['location_display']}")
        
        # Combine results
        if not location_df.empty and not df.empty:
            df = pd.concat([df, location_df], ignore_index=True)
        elif not location_df.empty:
            df = location_df
        
        return df
    
    def search_service_requests(self):
        """Search service_request table for radiation therapy orders"""
        print(f"\n{'='*80}")
        print(f"3. SEARCHING SERVICE REQUESTS FOR RADIATION ORDERS")
        print(f"{'='*80}")
        
        query = f"""
        SELECT 
            sr.id,
            sr.status,
            sr.intent,
            sr.code_text,
            sr.authored_on,
            sr.occurrence_date_time,
            sr.requester_display
        FROM {self.database}.service_request sr
        WHERE sr.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(sr.code_text) LIKE '%radiation%'
            OR LOWER(sr.code_text) LIKE '%radiotherapy%'
            OR LOWER(sr.code_text) LIKE '%oncology%'
            OR LOWER(sr.code_text) LIKE '%radiosurgery%'
        )
        ORDER BY sr.authored_on DESC
        """
        
        df = self.execute_query(query, "Querying service_request for radiation orders")
        
        if not df.empty:
            print(f"\n   📊 Radiation Service Requests Found:")
            for _, row in df.iterrows():
                print(f"      - {row['authored_on']}: {row['code_text']}")
                print(f"        Status: {row['status']}, Intent: {row['intent']}")
                if row['requester_display']:
                    print(f"        Requester: {row['requester_display']}")
        
        return df
    
    def search_diagnostic_reports(self):
        """Search diagnostic_report table for radiation planning reports"""
        print(f"\n{'='*80}")
        print(f"4. SEARCHING DIAGNOSTIC REPORTS FOR RADIATION PLANNING")
        print(f"{'='*80}")
        
        query = f"""
        SELECT 
            dr.id,
            dr.status,
            dr.code_text,
            dr.effective_date_time,
            dr.issued,
            dr.conclusion
        FROM {self.database}.diagnostic_report dr
        WHERE dr.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(dr.code_text) LIKE '%radiation%'
            OR LOWER(dr.conclusion) LIKE '%radiation%'
            OR LOWER(dr.conclusion) LIKE '%radiotherapy%'
        )
        ORDER BY dr.effective_date_time DESC
        """
        
        df = self.execute_query(query, "Querying diagnostic_report for radiation planning")
        
        if not df.empty:
            print(f"\n   📊 Radiation Diagnostic Reports Found:")
            for _, row in df.iterrows():
                print(f"      - {row['effective_date_time']}: {row['code_text']}")
                if row['conclusion']:
                    print(f"        Conclusion: {row['conclusion'][:150]}...")
        
        return df
    
    def search_care_plans(self):
        """Search care_plan table for radiation treatment protocols"""
        print(f"\n{'='*80}")
        print(f"5. SEARCHING CARE PLANS FOR RADIATION PROTOCOLS")
        print(f"{'='*80}")
        
        query = f"""
        SELECT 
            cp.id,
            cp.status,
            cp.intent,
            cp.title,
            cp.description,
            cp.period_start,
            cp.period_end,
            cp.created
        FROM {self.database}.care_plan cp
        WHERE cp.subject_reference = '{self.patient_fhir_id}'
        AND (
            LOWER(cp.title) LIKE '%radiation%'
            OR LOWER(cp.description) LIKE '%radiation%'
            OR LOWER(cp.description) LIKE '%radiotherapy%'
            OR LOWER(cp.description) LIKE '%radiosurgery%'
        )
        ORDER BY cp.period_start DESC
        """
        
        df = self.execute_query(query, "Querying care_plan for radiation protocols")
        
        if not df.empty:
            print(f"\n   📊 Radiation Care Plans Found:")
            for _, row in df.iterrows():
                print(f"      - {row['title']}")
                print(f"        Period: {row['period_start']} to {row['period_end']}")
                if row['description']:
                    print(f"        Description: {row['description'][:150]}...")
        
        return df
    
    def search_appointments(self):
        """Search appointment table for radiation therapy appointments
        
        Note: Appointments are linked to patients through encounters via encounter_appointment table.
        Uses the same nested subquery pattern as the working encounters extraction script.
        """
        print(f"\n{'='*80}")
        print(f"6. SEARCHING APPOINTMENTS FOR RADIATION THERAPY")
        print(f"{'='*80}")
        
        print(f"\n   🔍 Appointments are linked via encounter_appointment junction table")
        
        # Use nested IN subquery pattern (same as working encounters script)
        query = f"""
        SELECT DISTINCT
            a.id,
            a.status,
            a.appointment_type_text,
            a.description,
            a.start,
            a.end,
            a.minutes_duration,
            a.comment
        FROM {self.database}.appointment a
        WHERE a.id IN (
            SELECT REPLACE(ea.appointment_reference, 'Appointment/', '')
            FROM {self.database}.encounter_appointment ea
            WHERE ea.encounter_id IN (
                SELECT id 
                FROM {self.database}.encounter 
                WHERE subject_reference = '{self.patient_fhir_id}'
            )
        )
        AND (
            LOWER(a.appointment_type_text) LIKE '%radiation%'
            OR LOWER(a.appointment_type_text) LIKE '%oncology%'
            OR LOWER(a.description) LIKE '%radiation%'
            OR LOWER(a.description) LIKE '%radiotherapy%'
            OR LOWER(a.comment) LIKE '%radiation%'
        )
        AND a.status NOT IN ('cancelled', 'noshow')
        ORDER BY a.start DESC
        """
        
        df = self.execute_query(query, "Querying appointment table via encounter linkage")
        
        if not df.empty:
            print(f"\n   📊 Radiation Appointments Found:")
            for _, row in df.iterrows():
                print(f"      - {row['start']}: {row['appointment_type_text']}")
                print(f"        Status: {row['status']}, Duration: {row['minutes_duration']} min")
                if row['description']:
                    print(f"        Description: {row['description'][:100]}...")
        
        return df
    
    def generate_summary(self, results_dict):
        """Generate summary of all findings"""
        print(f"\n{'='*80}")
        print(f"📊 RADIATION TREATMENT DATA SUMMARY")
        print(f"{'='*80}\n")
        
        total_records = sum(len(df) for df in results_dict.values() if not df.empty)
        
        print(f"Total radiation-related records found: {total_records}\n")
        
        for resource_type, df in results_dict.items():
            if not df.empty:
                print(f"✅ {resource_type}: {len(df)} records")
            else:
                print(f"⚠️  {resource_type}: No records found")
        
        if total_records == 0:
            print(f"\n❌ No radiation treatment data found for patient {self.patient_fhir_id}")
            print(f"\nPossible reasons:")
            print(f"  1. Patient has not received radiation therapy")
            print(f"  2. Radiation data is stored in different tables/fields")
            print(f"  3. Data uses different terminology (e.g., 'RT', 'XRT')")
            print(f"  4. Radiation data is in clinical notes (DocumentReference)")
        else:
            print(f"\n✅ Found radiation treatment data!")
            print(f"\nNext steps:")
            print(f"  1. Review the detailed findings above")
            print(f"  2. Extract specific radiation fields if needed")
            print(f"  3. Link radiation data to encounters and procedures")
            print(f"  4. Consider searching clinical notes for additional context")
        
        print(f"\n{'='*80}\n")


def main():
    """Main execution"""
    print(f"\nStarting radiation treatment data exploration...")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Load patient configuration
    config_file = Path(__file__).parent.parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    # Initialize explorer
    explorer = RadiationDataExplorer(patient_config=config)
    
    # Search all data sources
    results = {
        'Procedures': explorer.search_radiation_procedures(),
        'Encounters': explorer.search_radiation_encounters(),
        'Service Requests': explorer.search_service_requests(),
        'Diagnostic Reports': explorer.search_diagnostic_reports(),
        'Care Plans': explorer.search_care_plans(),
        'Appointments': explorer.search_appointments()
    }
    
    # Generate summary
    explorer.generate_summary(results)
    
    print(f"Exploration completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 0


if __name__ == "__main__":
    exit(main())
