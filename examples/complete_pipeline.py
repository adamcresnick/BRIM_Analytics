"""
Complete FHIR + BRIM Extraction Pipeline
=========================================

End-to-end example: Extract data from FHIR, generate BRIM CSVs, run extraction via API.

Usage:
    python examples/complete_pipeline.py --patient-id Patient/12345 --api-key YOUR_API_KEY

Requirements:
    - Athena FHIR database access
    - BRIM API key
    - Python 3.8+
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from fhir_extractor import FHIRExtractor
from brim_csv_generator import BRIMCSVGenerator
from brim_api_client import run_complete_workflow

# For database connection (example using pyathena)
try:
    from pyathena import connect
    ATHENA_AVAILABLE = True
except ImportError:
    ATHENA_AVAILABLE = False
    print("Warning: pyathena not installed. Install with: pip install pyathena")


def setup_athena_connection(database: str, s3_staging: str, region: str = 'us-east-1'):
    """
    Setup Athena database connection.
    
    Args:
        database: Athena database name
        s3_staging: S3 bucket for query results (e.g., s3://my-bucket/athena-results/)
        region: AWS region
        
    Returns:
        Athena connection object
    """
    if not ATHENA_AVAILABLE:
        raise ImportError("pyathena is required. Install with: pip install pyathena")
    
    return connect(
        s3_staging_dir=s3_staging,
        region_name=region,
        database=database
    )


def main():
    parser = argparse.ArgumentParser(
        description='Complete FHIR + BRIM extraction pipeline'
    )
    
    # Required arguments
    parser.add_argument(
        '--patient-id',
        required=True,
        help='FHIR Patient resource ID (e.g., Patient/12345)'
    )
    parser.add_argument(
        '--patient-research-id',
        required=True,
        help='De-identified research ID for patient (e.g., C1277724)'
    )
    parser.add_argument(
        '--brim-api-key',
        required=True,
        help='BRIM API key'
    )
    
    # Database configuration
    parser.add_argument(
        '--athena-database',
        default='fhir',
        help='Athena database name (default: fhir)'
    )
    parser.add_argument(
        '--s3-staging',
        required=True,
        help='S3 staging location for Athena (e.g., s3://my-bucket/athena-results/)'
    )
    
    # Output configuration
    parser.add_argument(
        '--output-dir',
        default='./output',
        help='Output directory for generated files (default: ./output)'
    )
    parser.add_argument(
        '--clinical-domain',
        default='neuro_oncology',
        choices=['neuro_oncology', 'general'],
        help='Clinical domain for variable templates (default: neuro_oncology)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--skip-brim-upload',
        action='store_true',
        help='Generate CSVs only, skip BRIM API upload'
    )
    parser.add_argument(
        '--max-binary-size-mb',
        type=float,
        default=10.0,
        help='Maximum Binary content size to extract in MB (default: 10.0)'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("="*80)
    print("FHIR + BRIM Extraction Pipeline")
    print("="*80)
    print(f"Patient ID: {args.patient_id}")
    print(f"Research ID: {args.patient_research_id}")
    print(f"Output Directory: {output_dir}")
    print(f"Clinical Domain: {args.clinical_domain}")
    print("="*80)
    
    # -------------------------------------------------------------------------
    # PHASE 1: Extract FHIR Context
    # -------------------------------------------------------------------------
    print("\n📊 PHASE 1: Extracting FHIR Context")
    print("-" * 80)
    
    # Setup database connection
    print("Connecting to Athena...")
    conn = setup_athena_connection(
        database=args.athena_database,
        s3_staging=args.s3_staging
    )
    
    # Initialize FHIR extractor
    fhir_extractor = FHIRExtractor(conn)
    
    # Extract patient context
    print(f"Extracting clinical context for {args.patient_id}...")
    fhir_context = fhir_extractor.extract_patient_context(args.patient_id)
    
    print(f"✓ Found {len(fhir_context['surgeries'])} surgical procedures")
    print(f"✓ Found {len(fhir_context['diagnoses'])} diagnoses")
    print(f"✓ Found {len(fhir_context['medications'])} medication orders")
    print(f"✓ Found {len(fhir_context['encounters'])} encounters")
    
    # Discover clinical notes
    print("\nDiscovering clinical notes...")
    clinical_notes = fhir_extractor.discover_clinical_notes(args.patient_id)
    print(f"✓ Found {len(clinical_notes)} clinical documents")
    
    # -------------------------------------------------------------------------
    # PHASE 2: Generate BRIM CSVs
    # -------------------------------------------------------------------------
    print("\n📝 PHASE 2: Generating BRIM CSVs")
    print("-" * 80)
    
    # Initialize CSV generator
    csv_generator = BRIMCSVGenerator(fhir_context)
    
    # Define output paths
    project_csv = output_dir / f"brim_project_{timestamp}.csv"
    variables_csv = output_dir / f"brim_variables_{timestamp}.csv"
    decisions_csv = output_dir / f"brim_decisions_{timestamp}.csv"
    
    # Generate project CSV with HINT columns
    print("\nGenerating project CSV with HINT columns...")
    csv_generator.generate_project_csv(
        clinical_notes=clinical_notes,
        patient_research_id=args.patient_research_id,
        output_path=str(project_csv),
        fhir_extractor=fhir_extractor
    )
    
    # Generate variables CSV
    print("\nGenerating variables CSV...")
    csv_generator.generate_variables_csv(
        clinical_domain=args.clinical_domain,
        output_path=str(variables_csv)
    )
    
    # Generate decisions CSV
    print("\nGenerating decisions CSV...")
    num_surgeries = len(fhir_context['surgeries']) or 2
    csv_generator.generate_decisions_csv(
        output_path=str(decisions_csv),
        num_surgeries=num_surgeries
    )
    
    # Validate CSVs
    print("\nValidating generated CSVs...")
    validation = csv_generator.validate_csvs(
        str(project_csv),
        str(variables_csv),
        str(decisions_csv)
    )
    
    if validation['valid']:
        print("✓ All CSVs valid")
    else:
        print("✗ Validation errors found:")
        for error in validation['errors']:
            print(f"  - {error}")
        
        if validation['errors']:
            print("\n❌ Please fix validation errors before proceeding")
            sys.exit(1)
    
    if validation['warnings']:
        print("⚠ Warnings:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
    
    print("\n✓ BRIM CSVs generated successfully:")
    print(f"  - Project: {project_csv}")
    print(f"  - Variables: {variables_csv}")
    print(f"  - Decisions: {decisions_csv}")
    
    # -------------------------------------------------------------------------
    # PHASE 3: BRIM API Extraction (Optional)
    # -------------------------------------------------------------------------
    if args.skip_brim_upload:
        print("\n⏭ Skipping BRIM API upload (--skip-brim-upload specified)")
        print("\n✓ Pipeline complete! CSVs ready for manual BRIM upload.")
        return
    
    print("\n🚀 PHASE 3: BRIM API Extraction")
    print("-" * 80)
    
    project_name = f"Patient_{args.patient_research_id}_{timestamp}"
    
    try:
        result = run_complete_workflow(
            project_csv=str(project_csv),
            variables_csv=str(variables_csv),
            decisions_csv=str(decisions_csv),
            api_key=args.brim_api_key,
            project_name=project_name,
            output_dir=str(output_dir)
        )
        
        print("\n✓ BRIM extraction complete!")
        print(f"  - Project ID: {result['project_id']}")
        print(f"  - Job ID: {result['job_id']}")
        print(f"  - Results: {result['results_path']}")
        
    except Exception as e:
        print(f"\n❌ BRIM API error: {e}")
        print("\nCSVs are still available for manual upload:")
        print(f"  - {project_csv}")
        print(f"  - {variables_csv}")
        print(f"  - {decisions_csv}")
        sys.exit(1)
    
    # -------------------------------------------------------------------------
    # PHASE 4: Results Summary
    # -------------------------------------------------------------------------
    print("\n📊 PHASE 4: Results Summary")
    print("-" * 80)
    
    # Load and preview results
    import pandas as pd
    
    results_df = pd.read_csv(result['results_path'])
    
    print(f"\nExtracted {len(results_df)} records")
    print(f"Variables extracted: {len(results_df.columns)}")
    
    # Show sample of extracted variables
    print("\nSample extracted variables:")
    sample_cols = [col for col in results_df.columns if not col.startswith('NOTE_')][:10]
    print(results_df[sample_cols].head().to_string())
    
    print("\n" + "="*80)
    print("✓ Pipeline complete!")
    print("="*80)


if __name__ == '__main__':
    main()
