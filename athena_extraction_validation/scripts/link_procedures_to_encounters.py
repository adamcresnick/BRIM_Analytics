#!/usr/bin/env python3
"""
Link procedures to encounters to resolve dates and validate surgical timeline

This script:
1. Loads procedures staging file (ALL_PROCEDURES_METADATA_C1277724.csv)
2. Loads encounters staging file (ALL_ENCOUNTERS_METADATA_C1277724.csv)
3. Merges on encounter_reference to resolve dates for undated procedures
4. Validates surgical procedures against "Surgery Log" encounters
5. Creates enhanced procedures staging file with encounter dates
6. Generates validation report
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

class ProcedureEncounterLinker:
    def __init__(self):
        """Initialize with patient information"""
        self.patient_research_id = "C1277724"
        self.birth_date = datetime.strptime('2005-05-13', '%Y-%m-%d')
        
        # Expected surgical dates based on diagnosis timeline
        self.expected_initial_surgery = datetime.strptime('2018-05-28', '%Y-%m-%d')
        self.expected_recurrence_surgery = datetime.strptime('2021-03-10', '%Y-%m-%d')
        
        print(f"\n{'='*80}")
        print(f"🔗 PROCEDURE-ENCOUNTER LINKAGE & VALIDATION")
        print(f"{'='*80}")
        print(f"Patient: {self.patient_research_id}")
        print(f"Birth Date: {self.birth_date.strftime('%Y-%m-%d')}")
        print(f"{'='*80}\n")
    
    def load_staging_files(self):
        """Load both staging files"""
        print("📂 Loading staging files...")
        
        reports_dir = Path('athena_extraction_validation/reports')
        
        # Load procedures
        procedures_file = reports_dir / f'ALL_PROCEDURES_METADATA_{self.patient_research_id}.csv'
        self.procedures_df = pd.read_csv(procedures_file)
        print(f"  ✓ Loaded procedures: {len(self.procedures_df)} rows")
        
        # Load encounters
        encounters_file = reports_dir / f'ALL_ENCOUNTERS_METADATA_{self.patient_research_id}.csv'
        self.encounters_df = pd.read_csv(encounters_file)
        print(f"  ✓ Loaded encounters: {len(self.encounters_df)} rows\n")
    
    def analyze_linkage_coverage(self):
        """Analyze how many procedures link to encounters"""
        print(f"{'='*80}")
        print("📊 LINKAGE COVERAGE ANALYSIS")
        print(f"{'='*80}\n")
        
        # Procedures with encounter_reference
        with_encounter = self.procedures_df['encounter_reference'].notna().sum()
        without_encounter = self.procedures_df['encounter_reference'].isna().sum()
        
        print(f"Procedures with encounter_reference: {with_encounter}/{len(self.procedures_df)} ({with_encounter/len(self.procedures_df)*100:.1f}%)")
        print(f"Procedures without encounter_reference: {without_encounter}/{len(self.procedures_df)} ({without_encounter/len(self.procedures_df)*100:.1f}%)")
        
        # Procedures with explicit dates
        with_date = self.procedures_df['performed_period_start'].notna().sum()
        without_date = self.procedures_df['performed_period_start'].isna().sum()
        
        print(f"\nProcedures with explicit dates: {with_date}/{len(self.procedures_df)} ({with_date/len(self.procedures_df)*100:.1f}%)")
        print(f"Procedures without explicit dates: {without_date}/{len(self.procedures_df)} ({without_date/len(self.procedures_df)*100:.1f}%)")
        
        # Potential to resolve dates via encounter linkage
        undated_with_encounter = self.procedures_df[
            (self.procedures_df['performed_period_start'].isna()) &
            (self.procedures_df['encounter_reference'].notna())
        ]
        
        print(f"\n🎯 Undated procedures that can be resolved via encounter linkage:")
        print(f"   {len(undated_with_encounter)}/{without_date} ({len(undated_with_encounter)/without_date*100:.1f}% of undated)")
        print()
    
    def merge_with_encounters(self):
        """Merge procedures with encounters on encounter_reference"""
        print(f"{'='*80}")
        print("🔗 MERGING PROCEDURES WITH ENCOUNTERS")
        print(f"{'='*80}\n")
        
        # Select key encounter columns for merging
        encounter_cols = [
            'encounter_fhir_id',
            'encounter_date',
            'age_at_encounter_days',
            'class_code',
            'class_display',
            'type_text',
            'service_type_text',
            'location_location_reference'
        ]
        
        encounters_subset = self.encounters_df[encounter_cols].copy()
        
        # Rename to avoid column name conflicts
        encounters_subset = encounters_subset.rename(columns={
            'encounter_date': 'encounter_date_from_encounter',
            'age_at_encounter_days': 'age_from_encounter',
            'class_code': 'encounter_class_code',
            'class_display': 'encounter_class_display',
            'type_text': 'encounter_type_text',
            'service_type_text': 'encounter_service_type',
            'location_display': 'encounter_location'
        })
        
        # Merge
        self.merged_df = self.procedures_df.merge(
            encounters_subset,
            left_on='encounter_reference',
            right_on='encounter_fhir_id',
            how='left'
        )
        
        print(f"  ✓ Merged: {len(self.merged_df)} rows (same as procedures)")
        
        # Check how many got encounter data
        matched = self.merged_df['encounter_fhir_id'].notna().sum()
        print(f"  ✓ Procedures matched to encounters: {matched}/{len(self.merged_df)} ({matched/len(self.merged_df)*100:.1f}%)")
        print()
    
    def resolve_dates(self):
        """Create best_available_date column using priority order"""
        print(f"{'='*80}")
        print("📅 RESOLVING PROCEDURE DATES")
        print(f"{'='*80}\n")
        
        # Priority order:
        # 1. performed_period_start (if not NULL)
        # 2. performed_date_time (if period_start NULL)
        # 3. encounter_date_from_encounter (via linkage)
        
        self.merged_df['best_available_date'] = self.merged_df['performed_period_start'].fillna(
            self.merged_df['performed_date_time']
        ).fillna(
            self.merged_df['encounter_date_from_encounter']
        )
        
        # Convert to datetime and remove timezone info
        self.merged_df['best_available_date'] = pd.to_datetime(
            self.merged_df['best_available_date'], 
            errors='coerce',
            utc=True
        ).dt.tz_localize(None)  # Remove timezone to match birth_date
        
        # Calculate age using best available date
        self.merged_df['age_at_procedure_resolved'] = (
            self.merged_df['best_available_date'] - self.birth_date
        ).dt.days
        
        # Count resolution success
        original_dated = self.procedures_df['performed_period_start'].notna().sum()
        now_dated = self.merged_df['best_available_date'].notna().sum()
        improvement = now_dated - original_dated
        
        print(f"Date Resolution Results:")
        print(f"  Original dated procedures: {original_dated}/{len(self.procedures_df)} ({original_dated/len(self.procedures_df)*100:.1f}%)")
        print(f"  Now dated procedures: {now_dated}/{len(self.merged_df)} ({now_dated/len(self.merged_df)*100:.1f}%)")
        print(f"  ✓ Improvement: +{improvement} procedures ({improvement/len(self.procedures_df)*100:.1f}%)")
        
        # Show date source breakdown
        print(f"\nDate Source Breakdown:")
        from_period = self.merged_df['performed_period_start'].notna().sum()
        from_datetime = (
            self.merged_df['performed_period_start'].isna() & 
            self.merged_df['performed_date_time'].notna()
        ).sum()
        from_encounter = (
            self.merged_df['performed_period_start'].isna() & 
            self.merged_df['performed_date_time'].isna() & 
            self.merged_df['encounter_date_from_encounter'].notna()
        ).sum()
        
        print(f"  - From performed_period_start: {from_period}")
        print(f"  - From performed_date_time: {from_datetime}")
        print(f"  - From encounter linkage: {from_encounter}")
        print(f"  - Still undated: {len(self.merged_df) - now_dated}")
        print()
    
    def validate_surgical_procedures(self):
        """Validate surgical procedures against Surgery Log encounters"""
        print(f"{'='*80}")
        print("🔪 SURGICAL PROCEDURE VALIDATION")
        print(f"{'='*80}\n")
        
        # Filter for surgical procedures
        surgical = self.merged_df[
            self.merged_df['category_coding_display'] == 'Surgical procedure'
        ].copy()
        
        print(f"Total surgical procedures: {len(surgical)}")
        
        # Check Surgery Log encounters
        surgery_log = surgical[
            surgical['encounter_class_display'] == 'Surgery Log'
        ]
        
        print(f"Surgical procedures linked to 'Surgery Log' encounters: {len(surgery_log)}")
        
        if len(surgery_log) > 0:
            print(f"\n📋 Surgery Log Procedures:\n")
            for idx, row in surgery_log.iterrows():
                date = row['best_available_date'].strftime('%Y-%m-%d') if pd.notna(row['best_available_date']) else 'NO DATE'
                age = row['age_at_procedure_resolved'] if pd.notna(row['age_at_procedure_resolved']) else 'N/A'
                code = row['code_coding_display'] if pd.notna(row['code_coding_display']) else row['code_text']
                
                print(f"  {date} (Age: {age} days):")
                print(f"    Procedure: {code}")
                print(f"    Encounter: {row['encounter_class_display']}")
                print(f"    Type: {row['encounter_type_text']}")
                print()
        
        # Check for anesthesia procedures
        anesthesia = self.merged_df[
            self.merged_df['code_coding_display'].str.contains('ANES', case=False, na=False)
        ].copy()
        
        print(f"\n💉 Anesthesia Procedures (Surgical Markers): {len(anesthesia)}")
        
        if len(anesthesia) > 0:
            # Group by date to identify surgical events
            anesthesia_dated = anesthesia[anesthesia['best_available_date'].notna()]
            if len(anesthesia_dated) > 0:
                dates = anesthesia_dated['best_available_date'].dt.date.value_counts().sort_index()
                print(f"\nAnesthesia procedures by date:")
                for date, count in dates.items():
                    print(f"  {date}: {count} anesthesia procedure(s)")
        
        # Validate against expected surgical dates
        print(f"\n{'='*60}")
        print("🎯 VALIDATION AGAINST EXPECTED SURGICAL TIMELINE")
        print(f"{'='*60}\n")
        
        print(f"Expected Initial Surgery: {self.expected_initial_surgery.strftime('%Y-%m-%d')}")
        print(f"Expected Recurrence Surgery: {self.expected_recurrence_surgery.strftime('%Y-%m-%d')}")
        
        # Check for procedures near expected dates (±7 days)
        surgical_dated = surgical[surgical['best_available_date'].notna()].copy()
        
        if len(surgical_dated) > 0:
            print(f"\nFound {len(surgical_dated)} dated surgical procedures:")
            for idx, row in surgical_dated.iterrows():
                date = row['best_available_date']
                days_from_initial = (date - self.expected_initial_surgery).days
                days_from_recurrence = (date - self.expected_recurrence_surgery).days
                
                match = ""
                if abs(days_from_initial) <= 7:
                    match = "✅ MATCHES INITIAL SURGERY"
                elif abs(days_from_recurrence) <= 7:
                    match = "✅ MATCHES RECURRENCE SURGERY"
                
                print(f"\n  {date.strftime('%Y-%m-%d')}: {row['code_coding_display'][:60]}")
                print(f"    Days from initial: {days_from_initial:+d}, from recurrence: {days_from_recurrence:+d}")
                if match:
                    print(f"    {match}")
        
        print()
        return surgical, surgery_log
    
    def create_enhanced_staging_file(self):
        """Export enhanced staging file with resolved dates"""
        print(f"{'='*80}")
        print("💾 CREATING ENHANCED STAGING FILE")
        print(f"{'='*80}\n")
        
        # Select final columns
        output_df = self.merged_df.copy()
        
        # Reorder columns to put best_available_date near the front
        cols = list(output_df.columns)
        
        # Move best_available_date and age_at_procedure_resolved after procedure_fhir_id
        if 'best_available_date' in cols:
            cols.remove('best_available_date')
            cols.insert(1, 'best_available_date')
        
        if 'age_at_procedure_resolved' in cols:
            cols.remove('age_at_procedure_resolved')
            cols.insert(2, 'age_at_procedure_resolved')
        
        output_df = output_df[cols]
        
        # Export
        output_file = Path('athena_extraction_validation/reports') / f'ALL_PROCEDURES_WITH_ENCOUNTERS_{self.patient_research_id}.csv'
        output_df.to_csv(output_file, index=False)
        
        print(f"  ✓ Saved enhanced staging file:")
        print(f"    {output_file}")
        print(f"  ✓ Rows: {len(output_df)}")
        print(f"  ✓ Columns: {len(output_df.columns)}")
        print(f"  ✓ File size: {output_file.stat().st_size / 1024:.1f} KB")
        print()
        
        return output_file
    
    def generate_validation_report(self, surgical_df, surgery_log_df):
        """Generate comprehensive validation report"""
        print(f"{'='*80}")
        print("📊 VALIDATION SUMMARY REPORT")
        print(f"{'='*80}\n")
        
        total_procedures = len(self.merged_df)
        dated_procedures = self.merged_df['best_available_date'].notna().sum()
        
        print(f"Overall Statistics:")
        print(f"  Total procedures: {total_procedures}")
        print(f"  Dated procedures: {dated_procedures} ({dated_procedures/total_procedures*100:.1f}%)")
        print(f"  Undated procedures: {total_procedures - dated_procedures}")
        
        print(f"\nSurgical Procedures:")
        print(f"  Total surgical: {len(surgical_df)}")
        print(f"  Linked to Surgery Log encounters: {len(surgery_log_df)}")
        print(f"  Dated surgical: {surgical_df['best_available_date'].notna().sum()}")
        
        print(f"\nDate Resolution:")
        original = self.procedures_df['performed_period_start'].notna().sum()
        resolved = self.merged_df['best_available_date'].notna().sum()
        improvement = resolved - original
        print(f"  Original: {original} procedures")
        print(f"  Resolved: {resolved} procedures")
        print(f"  Improvement: +{improvement} procedures ({improvement/total_procedures*100:.1f}%)")
        
        print(f"\nCategory Breakdown:")
        print(self.merged_df['category_coding_display'].value_counts().to_string())
        
        print(f"\nEncounter Class Distribution (for linked procedures):")
        linked = self.merged_df[self.merged_df['encounter_class_display'].notna()]
        if len(linked) > 0:
            print(linked['encounter_class_display'].value_counts().to_string())
        
        print(f"\n{'='*80}\n")

def main():
    """Main execution"""
    try:
        linker = ProcedureEncounterLinker()
        
        # Step 1: Load staging files
        linker.load_staging_files()
        
        # Step 2: Analyze linkage coverage
        linker.analyze_linkage_coverage()
        
        # Step 3: Merge procedures with encounters
        linker.merge_with_encounters()
        
        # Step 4: Resolve dates using priority order
        linker.resolve_dates()
        
        # Step 5: Validate surgical procedures
        surgical_df, surgery_log_df = linker.validate_surgical_procedures()
        
        # Step 6: Create enhanced staging file
        output_file = linker.create_enhanced_staging_file()
        
        # Step 7: Generate validation report
        linker.generate_validation_report(surgical_df, surgery_log_df)
        
        print("✅ LINKAGE AND VALIDATION COMPLETE")
        print(f"\nOutput file: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
