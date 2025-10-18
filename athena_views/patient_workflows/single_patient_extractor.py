"""
Single Patient Extractor
=========================
End-to-end extraction workflow for a single patient.
Orchestrates Athena queries and multi-agent data abstraction.

Author: RADIANT PCA Project
Date: October 17, 2025
Branch: feature/multi-agent-framework
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from multi_agent.athena_query_agent import AthenaQueryAgent
from multi_agent.master_orchestrator import MasterOrchestrator, FieldCategory


class SinglePatientExtractor:
    """
    End-to-end extraction workflow for a single patient.

    Workflow:
    1. Query all Athena views for patient data
    2. Extract STRUCTURED_ONLY fields directly
    3. Extract HYBRID fields with validation
    4. Extract DOCUMENT_ONLY fields (when Medical Reasoning Agent available)
    5. Generate comprehensive extraction report
    """

    def __init__(
        self,
        athena_database: str = 'fhir_prd_db',
        athena_output_location: str = 's3://aws-athena-query-results-us-east-1-YOUR_BUCKET/',
        region: str = 'us-east-1'
    ):
        """
        Initialize Single Patient Extractor.

        Args:
            athena_database: Athena database name
            athena_output_location: S3 bucket for query results
            region: AWS region
        """
        # Initialize agents
        self.athena_agent = AthenaQueryAgent(
            database=athena_database,
            output_location=athena_output_location,
            region=region
        )

        self.orchestrator = MasterOrchestrator(athena_agent=self.athena_agent)

        # Extraction results
        self.patient_data = {}
        self.extraction_results = {}
        self.extraction_metadata = {}

    def extract_patient(
        self,
        patient_fhir_id: str,
        field_list: Optional[List[str]] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract all fields for a single patient.

        Args:
            patient_fhir_id: Patient FHIR ID
            field_list: Optional list of fields to extract (default: all)
            output_dir: Optional output directory for results

        Returns:
            Complete extraction results
        """
        print(f"Starting extraction for patient: {patient_fhir_id}")
        print("=" * 80)

        start_time = datetime.now()

        # Step 1: Query all Athena data
        print("\n[Step 1/5] Querying Athena for structured data...")
        self.patient_data = self._query_all_athena_data(patient_fhir_id)
        self._print_athena_summary()

        # Step 2: Extract STRUCTURED_ONLY fields
        print("\n[Step 2/5] Extracting STRUCTURED_ONLY fields...")
        structured_results = self._extract_structured_fields(patient_fhir_id, field_list)
        self._print_extraction_summary(structured_results, "STRUCTURED_ONLY")

        # Step 3: Extract HYBRID fields
        print("\n[Step 3/5] Extracting HYBRID fields...")
        hybrid_results = self._extract_hybrid_fields(patient_fhir_id, field_list)
        self._print_extraction_summary(hybrid_results, "HYBRID")

        # Step 4: Extract DOCUMENT_ONLY fields
        print("\n[Step 4/5] Extracting DOCUMENT_ONLY fields...")
        document_results = self._extract_document_fields(patient_fhir_id, field_list)
        self._print_extraction_summary(document_results, "DOCUMENT_ONLY")

        # Step 5: Generate report
        print("\n[Step 5/5] Generating extraction report...")
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        final_results = {
            'patient_fhir_id': patient_fhir_id,
            'extraction_timestamp': start_time.isoformat(),
            'extraction_duration_seconds': duration,
            'athena_data_summary': self._get_athena_summary(),
            'structured_fields': structured_results,
            'hybrid_fields': hybrid_results,
            'document_fields': document_results,
            'overall_summary': self.orchestrator.get_extraction_summary(patient_fhir_id),
            'dialogue_history': self.orchestrator.dialogue_history
        }

        # Save results if output directory specified
        if output_dir:
            self._save_results(final_results, output_dir, patient_fhir_id)

        print("\n" + "=" * 80)
        print(f"Extraction complete! Duration: {duration:.2f} seconds")
        self._print_final_summary(final_results)

        return final_results

    def _query_all_athena_data(self, patient_fhir_id: str) -> Dict[str, Any]:
        """Query all 15 Athena views for patient."""
        return self.athena_agent.query_all_patient_data(patient_fhir_id)

    def _extract_structured_fields(
        self,
        patient_fhir_id: str,
        field_list: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract all STRUCTURED_ONLY fields."""
        structured_fields = [
            'patient_gender', 'date_of_birth', 'race', 'ethnicity',
            'chemotherapy_agent', 'chemotherapy_start_date', 'chemotherapy_status'
        ]

        if field_list:
            structured_fields = [f for f in structured_fields if f in field_list]

        results = {}
        for field in structured_fields:
            results[field] = self.orchestrator.extract_field(patient_fhir_id, field)

        return results

    def _extract_hybrid_fields(
        self,
        patient_fhir_id: str,
        field_list: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract all HYBRID fields."""
        hybrid_fields = [
            'primary_diagnosis', 'diagnosis_date', 'who_grade', 'tumor_location',
            'extent_of_resection', 'surgery_date', 'surgery_type', 'radiation_dose'
        ]

        if field_list:
            hybrid_fields = [f for f in hybrid_fields if f in field_list]

        results = {}
        for field in hybrid_fields:
            results[field] = self.orchestrator.extract_field(patient_fhir_id, field)

        return results

    def _extract_document_fields(
        self,
        patient_fhir_id: str,
        field_list: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract all DOCUMENT_ONLY fields."""
        document_fields = [
            'clinical_status', 'imaging_findings', 'tumor_size', 'pathology_notes'
        ]

        if field_list:
            document_fields = [f for f in document_fields if f in field_list]

        results = {}
        for field in document_fields:
            results[field] = self.orchestrator.extract_field(patient_fhir_id, field)

        return results

    def _get_athena_summary(self) -> Dict[str, int]:
        """Get summary counts from Athena data."""
        return {
            'demographics': 1 if self.patient_data.get('demographics') else 0,
            'diagnoses': len(self.patient_data.get('diagnoses', [])),
            'procedures': len(self.patient_data.get('procedures', [])),
            'medications': len(self.patient_data.get('medications', [])),
            'imaging': len(self.patient_data.get('imaging', [])),
            'encounters': len(self.patient_data.get('encounters', [])),
            'measurements': len(self.patient_data.get('measurements', [])),
            'molecular_tests': len(self.patient_data.get('molecular_tests', [])),
            'radiation_appointments': len(self.patient_data.get('radiation_appointments', [])),
            'radiation_courses': len(self.patient_data.get('radiation_courses', []))
        }

    def _print_athena_summary(self):
        """Print summary of Athena query results."""
        summary = self._get_athena_summary()
        print(f"  ✓ Demographics: {summary['demographics']} record")
        print(f"  ✓ Diagnoses: {summary['diagnoses']} records")
        print(f"  ✓ Procedures: {summary['procedures']} records")
        print(f"  ✓ Medications: {summary['medications']} records")
        print(f"  ✓ Imaging: {summary['imaging']} records")
        print(f"  ✓ Encounters: {summary['encounters']} records")
        print(f"  ✓ Measurements: {summary['measurements']} records")
        print(f"  ✓ Molecular Tests: {summary['molecular_tests']} records")
        print(f"  ✓ Radiation Appointments: {summary['radiation_appointments']} records")
        print(f"  ✓ Radiation Courses: {summary['radiation_courses']} records")

    def _print_extraction_summary(self, results: Dict[str, Any], category: str):
        """Print summary of extraction results for a category."""
        if not results:
            print(f"  No {category} fields to extract")
            return

        high_conf = sum(1 for r in results.values() if r['confidence'] >= 0.85)
        medium_conf = sum(1 for r in results.values() if 0.60 <= r['confidence'] < 0.85)
        low_conf = sum(1 for r in results.values() if r['confidence'] < 0.60)

        print(f"  ✓ Extracted {len(results)} {category} fields")
        print(f"    - High confidence (≥0.85): {high_conf}")
        print(f"    - Medium confidence (0.60-0.84): {medium_conf}")
        print(f"    - Low confidence (<0.60): {low_conf}")

    def _print_final_summary(self, results: Dict[str, Any]):
        """Print final extraction summary."""
        summary = results['overall_summary']
        print(f"\nFinal Summary:")
        print(f"  Total fields extracted: {summary['total_fields']}")
        print(f"  High confidence: {summary['high_confidence']} ({summary['confidence_distribution']['high (0.85-1.0)']})")
        print(f"  Medium confidence: {summary['medium_confidence']} ({summary['confidence_distribution']['medium (0.60-0.84)']})")
        print(f"  Low confidence: {summary['low_confidence']} ({summary['confidence_distribution']['low (< 0.60)']})")

    def _save_results(
        self,
        results: Dict[str, Any],
        output_dir: str,
        patient_fhir_id: str
    ):
        """Save extraction results to JSON file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"extraction_{patient_fhir_id}_{timestamp}.json"
        filepath = output_path / filename

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\nResults saved to: {filepath}")


def main():
    """Command-line interface for single patient extraction."""
    parser = argparse.ArgumentParser(
        description='Extract clinical data for a single patient using Athena-based multi-agent framework'
    )
    parser.add_argument(
        '--patient-id',
        required=True,
        help='Patient FHIR ID (e.g., e4BwD8ZYDBccepXcJ.Ilo3w3)'
    )
    parser.add_argument(
        '--fields',
        nargs='+',
        help='List of fields to extract (default: all fields)'
    )
    parser.add_argument(
        '--output-dir',
        default='./extraction_results',
        help='Output directory for results (default: ./extraction_results)'
    )
    parser.add_argument(
        '--athena-database',
        default='fhir_prd_db',
        help='Athena database name (default: fhir_prd_db)'
    )
    parser.add_argument(
        '--athena-output-bucket',
        required=True,
        help='S3 bucket for Athena query results (e.g., s3://your-bucket/)'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )

    args = parser.parse_args()

    # Initialize extractor
    extractor = SinglePatientExtractor(
        athena_database=args.athena_database,
        athena_output_location=args.athena_output_bucket,
        region=args.region
    )

    # Run extraction
    try:
        results = extractor.extract_patient(
            patient_fhir_id=args.patient_id,
            field_list=args.fields,
            output_dir=args.output_dir
        )
        print("\n✅ Extraction completed successfully!")
        return 0
    except Exception as e:
        print(f"\n❌ Extraction failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
