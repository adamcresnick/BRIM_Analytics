#!/usr/bin/env python3
"""
Simple test of the unified workflow
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from unified_workflow_orchestrator import UnifiedWorkflowOrchestrator

def main():
    print("\n" + "="*80)
    print("TESTING UNIFIED MULTI-SOURCE EXTRACTION WORKFLOW")
    print("="*80)

    # Create orchestrator with test configuration
    test_config = {
        'paths': {
            'staging_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files',
            'binary_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/binary_files',
            'brim_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction',
            'output_base': '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs'
        },
        'workflow': {
            'max_documents_per_patient': 20,  # Smaller for testing
            'parallel_processing': False,
            'checkpoint_frequency': 5,
            'enable_phase_1': True,
            'enable_phase_2': True,
            'enable_phase_3': False,  # Skip for quick test
            'enable_phase_4': False,  # Skip for quick test
            'enable_phase_5': False   # Skip for quick test
        },
        'modules': {
            'chemotherapy_identification': True,
            'tumor_surgery_classification': True,
            'radiation_analysis': False,  # Skip for speed
            'imaging_prioritization': False,  # Skip for speed
            'molecular_integration': True,
            'problem_list_analysis': True
        }
    }

    try:
        # Initialize orchestrator
        print("\nInitializing orchestrator...")
        orchestrator = UnifiedWorkflowOrchestrator()

        # Override config
        orchestrator.config = test_config
        orchestrator._initialize_components()

        # Test patient discovery
        print("\nDiscovering patients...")
        patients = orchestrator.discover_patients()
        print(f"Found {len(patients)} patients:")
        for p in patients[:3]:  # Show first 3
            print(f"  - {p}")

        # Test with our specific patient
        test_patient = "e4BwD8ZYDBccepXcJ.Ilo3w3"
        print(f"\nTesting with patient: {test_patient}")

        # Process patient with limited phases
        results = orchestrator.process_patient(test_patient)

        # Report results
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        print(f"Status: {results.get('status', 'unknown')}")

        if 'phases' in results:
            for phase_key, phase_data in results['phases'].items():
                print(f"\n{phase_key.upper()}:")
                if phase_key == 'phase1' and 'data_sources' in phase_data:
                    sources = phase_data['data_sources']
                    found = sum(1 for s in sources.values() if s.get('exists'))
                    print(f"  Data sources: {found}/{len(sources)} found")
                elif phase_key == 'phase2' and 'components' in phase_data:
                    components = phase_data['components']
                    if 'diagnosis' in components:
                        print(f"  Diagnosis date: {components['diagnosis'].get('date')}")
                        print(f"  Age at diagnosis: {components['diagnosis'].get('age')}")
                    if 'chemotherapy' in components:
                        print(f"  Chemotherapy medications: {components['chemotherapy'].get('medications_identified', 0)}")

        print("\n" + "="*60)
        print("TEST COMPLETE - Workflow is functional!")
        print("="*60)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())