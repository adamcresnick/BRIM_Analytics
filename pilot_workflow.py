"""
BRIM Analytics Pilot Script
============================

Test the complete workflow with real AWS and BRIM credentials.

This script will:
1. Query actual FHIR data from Athena
2. Generate BRIM CSVs with HINT columns
3. Upload to BRIM via API (optional)
4. Download and analyze results

Usage:
    python pilot_workflow.py --patient-id <FHIR_ID> --research-id <RESEARCH_ID>
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


def test_aws_connection():
    """Test AWS Athena connection."""
    print("\n🔍 Testing AWS Athena Connection...")
    print("-" * 80)
    
    try:
        import boto3
        
        # Use the specified profile
        session = boto3.Session(
            profile_name=os.getenv('AWS_PROFILE'),
            region_name=os.getenv('AWS_REGION')
        )
        
        # Test Athena access
        athena = session.client('athena')
        
        # List databases to verify access
        response = athena.list_databases(
            CatalogName='AwsDataCatalog'
        )
        
        databases = [db['Name'] for db in response.get('Databases', [])]
        target_db = os.getenv('ATHENA_DATABASE')
        
        if target_db in databases:
            print(f"✓ Connected to AWS profile: {os.getenv('AWS_PROFILE')}")
            print(f"✓ Region: {os.getenv('AWS_REGION')}")
            print(f"✓ Found target database: {target_db}")
            return session
        else:
            print(f"✗ Target database not found: {target_db}")
            print(f"  Available databases: {', '.join(databases[:5])}...")
            return None
            
    except Exception as e:
        print(f"✗ AWS connection failed: {e}")
        print("\nPlease ensure:")
        print("  1. AWS SSO is logged in: aws sso login --profile 343218191717_AWSAdministratorAccess")
        print("  2. Profile exists in ~/.aws/config")
        return None


def setup_athena_connection(session):
    """Setup PyAthena connection using boto3 session."""
    
    try:
        from pyathena import connect
        from pyathena.pandas.cursor import PandasCursor
        
        conn = connect(
            s3_staging_dir=os.getenv('ATHENA_S3_STAGING'),
            region_name=os.getenv('AWS_REGION'),
            database=os.getenv('ATHENA_DATABASE'),
            cursor_class=PandasCursor,
            profile_name=os.getenv('AWS_PROFILE')
        )
        
        print("✓ PyAthena connection established")
        return conn
        
    except ImportError:
        print("✗ PyAthena not installed. Install with: pip install pyathena")
        return None
    except Exception as e:
        print(f"✗ PyAthena connection failed: {e}")
        return None


def explore_fhir_schema(conn):
    """Explore available FHIR tables."""
    
    print("\n📊 Exploring FHIR Schema...")
    print("-" * 80)
    
    try:
        # List tables
        query = "SHOW TABLES"
        df = conn.cursor().execute(query).as_pandas()
        
        print(f"Found {len(df)} tables in database")
        
        # Filter for key tables
        key_tables = ['patient', 'documentreference', 'binary', 'condition', 
                     'procedure', 'medicationrequest', 'encounter']
        
        available = []
        for table in key_tables:
            if table in df['tab_name'].values:
                available.append(table)
        
        print(f"Key tables available: {', '.join(available)}")
        
        return available
        
    except Exception as e:
        print(f"✗ Schema exploration failed: {e}")
        return []


def find_sample_patients(conn, limit=5):
    """Find sample patients with clinical notes."""
    
    print(f"\n🔍 Finding Sample Patients (limit: {limit})...")
    print("-" * 80)
    
    try:
        query = f"""
        SELECT 
            subject.reference as patient_id,
            COUNT(*) as document_count,
            MIN(date) as earliest_note,
            MAX(date) as latest_note
        FROM documentreference
        WHERE status = 'current'
        GROUP BY subject.reference
        HAVING COUNT(*) > 5
        ORDER BY document_count DESC
        LIMIT {limit}
        """
        
        df = conn.cursor().execute(query).as_pandas()
        
        if not df.empty:
            print(f"✓ Found {len(df)} patients with clinical notes:\n")
            print(df.to_string(index=False))
            print("\nRecommended patient for testing:")
            print(f"  Patient ID: {df.iloc[0]['patient_id']}")
            print(f"  Documents: {df.iloc[0]['document_count']}")
            return df
        else:
            print("✗ No patients found with clinical notes")
            return None
            
    except Exception as e:
        print(f"✗ Patient search failed: {e}")
        return None


def run_pilot_extraction(patient_id, research_id, conn):
    """Run complete extraction workflow for one patient."""
    
    print(f"\n🚀 Starting Pilot Extraction")
    print("=" * 80)
    print(f"Patient ID: {patient_id}")
    print(f"Research ID: {research_id}")
    print("=" * 80)
    
    from fhir_extractor import FHIRExtractor
    from brim_csv_generator import BRIMCSVGenerator
    
    # Create output directory
    output_dir = Path(os.getenv('OUTPUT_DIR', './output'))
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # -------------------------------------------------------------------------
    # PHASE 1: Extract FHIR Context
    # -------------------------------------------------------------------------
    print("\n📊 PHASE 1: Extracting FHIR Context")
    print("-" * 80)
    
    extractor = FHIRExtractor(conn)
    
    try:
        print("Extracting clinical context...")
        context = extractor.extract_patient_context(patient_id)
        
        print(f"✓ Surgeries: {len(context.get('surgeries', []))}")
        print(f"✓ Diagnoses: {len(context.get('diagnoses', []))}")
        print(f"✓ Medications: {len(context.get('medications', []))}")
        print(f"✓ Encounters: {len(context.get('encounters', []))}")
        
    except Exception as e:
        print(f"✗ Context extraction failed: {e}")
        return None
    
    try:
        print("\nDiscovering clinical notes...")
        notes = extractor.discover_clinical_notes(patient_id)
        print(f"✓ Found {len(notes)} clinical documents")
        
        if notes:
            print("\nDocument types:")
            import pandas as pd
            notes_df = pd.DataFrame(notes)
            if 'document_type' in notes_df.columns:
                print(notes_df['document_type'].value_counts().to_string())
        
    except Exception as e:
        print(f"✗ Notes discovery failed: {e}")
        return None
    
    if not notes:
        print("⚠ No clinical notes found for this patient")
        return None
    
    # -------------------------------------------------------------------------
    # PHASE 2: Generate BRIM CSVs
    # -------------------------------------------------------------------------
    print("\n📝 PHASE 2: Generating BRIM CSVs")
    print("-" * 80)
    
    generator = BRIMCSVGenerator(context)
    
    # Define output paths
    project_csv = output_dir / f"brim_project_{research_id}_{timestamp}.csv"
    variables_csv = output_dir / f"brim_variables_{timestamp}.csv"
    decisions_csv = output_dir / f"brim_decisions_{timestamp}.csv"
    
    try:
        print("Generating project CSV with HINT columns...")
        generator.generate_project_csv(
            clinical_notes=notes,
            patient_research_id=research_id,
            output_path=str(project_csv),
            fhir_extractor=extractor
        )
        
        print("\nGenerating variables CSV...")
        generator.generate_variables_csv(
            clinical_domain=os.getenv('CLINICAL_DOMAIN', 'neuro_oncology'),
            output_path=str(variables_csv)
        )
        
        print("\nGenerating decisions CSV...")
        num_surgeries = max(len(context.get('surgeries', [])), 2)
        generator.generate_decisions_csv(
            output_path=str(decisions_csv),
            num_surgeries=num_surgeries
        )
        
    except Exception as e:
        print(f"✗ CSV generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Validate
    print("\nValidating CSVs...")
    validation = generator.validate_csvs(
        str(project_csv),
        str(variables_csv),
        str(decisions_csv)
    )
    
    if validation['valid']:
        print("✓ All CSVs valid")
    else:
        print("✗ Validation errors:")
        for error in validation['errors']:
            print(f"  - {error}")
        return None
    
    print("\n✓ BRIM CSVs generated successfully:")
    print(f"  - Project: {project_csv}")
    print(f"  - Variables: {variables_csv}")
    print(f"  - Decisions: {decisions_csv}")
    
    # -------------------------------------------------------------------------
    # PHASE 3: BRIM API Upload (Optional)
    # -------------------------------------------------------------------------
    if os.getenv('AUTO_UPLOAD_TO_BRIM', 'false').lower() == 'true':
        print("\n🚀 PHASE 3: Uploading to BRIM")
        print("-" * 80)
        
        try:
            from brim_api_client import run_complete_workflow
            
            result = run_complete_workflow(
                project_csv=str(project_csv),
                variables_csv=str(variables_csv),
                decisions_csv=str(decisions_csv),
                api_key=os.getenv('BRIM_API_KEY'),
                project_name=f"Pilot_{research_id}_{timestamp}",
                output_dir=str(output_dir)
            )
            
            print(f"\n✓ BRIM extraction complete!")
            print(f"  Results: {result['results_path']}")
            
        except Exception as e:
            print(f"✗ BRIM upload failed: {e}")
            print("\nCSVs are ready for manual upload to BRIM")
    else:
        print("\n⏭ Skipping BRIM upload (AUTO_UPLOAD_TO_BRIM=false)")
        print("CSVs are ready for manual upload to BRIM")
    
    print("\n" + "=" * 80)
    print("✓ Pilot Extraction Complete!")
    print("=" * 80)
    
    return {
        'project_csv': str(project_csv),
        'variables_csv': str(variables_csv),
        'decisions_csv': str(decisions_csv),
        'context': context,
        'notes_count': len(notes)
    }


def main():
    parser = argparse.ArgumentParser(
        description='BRIM Analytics Pilot - Test workflow with production data'
    )
    
    parser.add_argument(
        '--patient-id',
        help='FHIR Patient ID (e.g., Patient/12345). Leave empty to discover patients.'
    )
    parser.add_argument(
        '--research-id',
        help='De-identified research ID (e.g., C1277724)'
    )
    parser.add_argument(
        '--explore-only',
        action='store_true',
        help='Only explore schema and find patients, do not extract'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("BRIM ANALYTICS PILOT WORKFLOW")
    print("=" * 80)
    print(f"Environment: Production")
    print(f"AWS Profile: {os.getenv('AWS_PROFILE')}")
    print(f"Athena Database: {os.getenv('ATHENA_DATABASE')}")
    print(f"BRIM API: {os.getenv('BRIM_API_BASE_URL')}")
    print("=" * 80)
    
    # Test AWS connection
    session = test_aws_connection()
    if not session:
        print("\n❌ Cannot proceed without AWS connection")
        print("\nTo fix:")
        print("  1. Run: aws sso login --profile 343218191717_AWSAdministratorAccess")
        print("  2. Verify ~/.aws/config has the profile")
        sys.exit(1)
    
    # Setup Athena connection
    conn = setup_athena_connection(session)
    if not conn:
        print("\n❌ Cannot proceed without Athena connection")
        sys.exit(1)
    
    # Explore schema
    available_tables = explore_fhir_schema(conn)
    
    # Find sample patients
    sample_patients = find_sample_patients(conn, limit=5)
    
    if args.explore_only:
        print("\n✓ Exploration complete (--explore-only specified)")
        return
    
    # Check if patient ID provided
    if not args.patient_id:
        if sample_patients is not None and not sample_patients.empty:
            suggested_patient = sample_patients.iloc[0]['patient_id']
            print(f"\n💡 No patient specified. Try:")
            print(f"   python pilot_workflow.py --patient-id '{suggested_patient}' --research-id TEST001")
        else:
            print("\n❌ No patient ID specified and no sample patients found")
        sys.exit(0)
    
    if not args.research_id:
        print("\n❌ Research ID required (--research-id)")
        print("   Example: --research-id C1277724")
        sys.exit(1)
    
    # Run pilot extraction
    result = run_pilot_extraction(
        patient_id=args.patient_id,
        research_id=args.research_id,
        conn=conn
    )
    
    if result:
        print("\n📁 Generated Files:")
        print(f"  Project CSV: {result['project_csv']}")
        print(f"  Variables CSV: {result['variables_csv']}")
        print(f"  Decisions CSV: {result['decisions_csv']}")
        print(f"\n📊 Extracted:")
        print(f"  Clinical Notes: {result['notes_count']}")
        print(f"  Surgeries: {len(result['context'].get('surgeries', []))}")
        print(f"  Diagnoses: {len(result['context'].get('diagnoses', []))}")
    else:
        print("\n❌ Extraction failed. See errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
