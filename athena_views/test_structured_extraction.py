"""
Test Script: STRUCTURED_ONLY Field Extraction
==============================================
Test Athena-based multi-agent framework on pilot patient.
Extract and validate STRUCTURED_ONLY fields against gold standard.

Author: RADIANT PCA Project
Date: October 17, 2025
"""

import sys
import os
import json
from pathlib import Path
import boto3
from datetime import datetime

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent))

from multi_agent.athena_query_agent import AthenaQueryAgent
from multi_agent.master_orchestrator import MasterOrchestrator


def setup_aws_session():
    """Set up AWS session with SSO profile."""
    print("Setting up AWS session with profile 'radiant-prod'...")

    session = boto3.Session(
        profile_name='radiant-prod',
        region_name='us-east-1'
    )

    # Test credentials
    sts = session.client('sts')
    identity = sts.get_caller_identity()
    print(f"✓ AWS Identity: {identity['Arn']}")
    print(f"✓ Account ID: {identity['Account']}")

    return session


def test_structured_extraction():
    """Test STRUCTURED_ONLY field extraction."""

    print("\n" + "=" * 80)
    print("TEST: STRUCTURED_ONLY Field Extraction")
    print("=" * 80)

    # Setup
    session = setup_aws_session()

    # Initialize agents
    print("\n[1/5] Initializing Athena Query Agent...")
    athena_agent = AthenaQueryAgent(
        database='fhir_prd_db',
        output_location='s3://aws-athena-query-results-us-east-1-343218191717/',
        region='us-east-1'
    )
    # Override client with session
    athena_agent.client = session.client('athena', region_name='us-east-1')

    print("[2/5] Initializing Master Orchestrator...")
    orchestrator = MasterOrchestrator(athena_agent=athena_agent)

    # Test patient (pilot patient with known gold standard)
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Gold standard values
    gold_standard = {
        'patient_gender': 'female',
        'date_of_birth': '2005-05-13',  # May vary format
        'race': 'White',
        'ethnicity': 'Not Hispanic or Latino',
        'chemotherapy_agents': ['Bevacizumab', 'Vinblastine', 'Selumetinib']
    }

    print(f"\n[3/5] Testing patient: {patient_id}")
    print(f"Gold standard: {json.dumps(gold_standard, indent=2)}")

    # Extract STRUCTURED_ONLY fields
    print("\n[4/5] Extracting STRUCTURED_ONLY fields...")

    fields_to_test = [
        'patient_gender',
        'date_of_birth',
        'race',
        'ethnicity',
        'chemotherapy_agent'
    ]

    results = {}
    for field in fields_to_test:
        print(f"\n  Extracting: {field}")
        try:
            result = orchestrator.extract_field(patient_id, field)
            results[field] = result
            print(f"    Value: {result['value']}")
            print(f"    Confidence: {result['confidence']}")
            print(f"    Source: {result['source']}")
        except Exception as e:
            print(f"    ❌ ERROR: {str(e)}")
            results[field] = {'error': str(e)}

    # Validate results
    print("\n[5/5] Validating against gold standard...")
    validation_results = validate_results(results, gold_standard)

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    for field, validation in validation_results.items():
        status = "✓ PASS" if validation['pass'] else "✗ FAIL"
        print(f"{status} - {field}")
        print(f"  Expected: {validation['expected']}")
        print(f"  Got: {validation['actual']}")
        if not validation['pass']:
            print(f"  Reason: {validation.get('reason', 'Value mismatch')}")

    # Overall stats
    passed = sum(1 for v in validation_results.values() if v['pass'])
    total = len(validation_results)
    accuracy = (passed / total * 100) if total > 0 else 0

    print(f"\nOverall Accuracy: {passed}/{total} ({accuracy:.1f}%)")

    # Save results
    output_dir = Path(__file__).parent / 'test_results'
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'structured_test_{timestamp}.json'

    test_output = {
        'patient_id': patient_id,
        'timestamp': timestamp,
        'gold_standard': gold_standard,
        'extraction_results': results,
        'validation_results': validation_results,
        'accuracy': accuracy,
        'dialogue_history': orchestrator.dialogue_history
    }

    with open(output_file, 'w') as f:
        json.dump(test_output, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    return accuracy >= 80  # Pass if 80%+ accuracy


def validate_results(results, gold_standard):
    """Validate extraction results against gold standard."""
    validation = {}

    # Validate gender
    if 'patient_gender' in results:
        expected = gold_standard['patient_gender'].lower()
        actual = str(results['patient_gender'].get('value', '')).lower()
        validation['patient_gender'] = {
            'expected': expected,
            'actual': actual,
            'pass': expected == actual
        }

    # Validate DOB (check year at minimum)
    if 'date_of_birth' in results:
        expected_year = '2005'
        actual = str(results['date_of_birth'].get('value', ''))
        validation['date_of_birth'] = {
            'expected': gold_standard['date_of_birth'],
            'actual': actual,
            'pass': expected_year in actual
        }

    # Validate race
    if 'race' in results:
        expected = gold_standard['race'].lower()
        actual = str(results['race'].get('value', '')).lower()
        validation['race'] = {
            'expected': expected,
            'actual': actual,
            'pass': expected in actual or actual in expected
        }

    # Validate ethnicity
    if 'ethnicity' in results:
        expected = 'not hispanic'
        actual = str(results['ethnicity'].get('value', '')).lower()
        validation['ethnicity'] = {
            'expected': gold_standard['ethnicity'],
            'actual': actual,
            'pass': expected in actual
        }

    # Validate chemotherapy agents (check if all 3 present)
    if 'chemotherapy_agent' in results:
        expected_agents = [a.lower() for a in gold_standard['chemotherapy_agents']]
        actual_agents = results['chemotherapy_agent'].get('value', [])

        if isinstance(actual_agents, list):
            actual_agents_lower = [str(a).lower() for a in actual_agents]
            found_agents = []
            for expected in expected_agents:
                for actual in actual_agents_lower:
                    if expected in actual:
                        found_agents.append(expected)
                        break

            validation['chemotherapy_agent'] = {
                'expected': gold_standard['chemotherapy_agents'],
                'actual': actual_agents,
                'pass': len(found_agents) >= 3,
                'found': found_agents
            }
        else:
            validation['chemotherapy_agent'] = {
                'expected': gold_standard['chemotherapy_agents'],
                'actual': actual_agents,
                'pass': False,
                'reason': 'Expected list of agents'
            }

    return validation


if __name__ == '__main__':
    print("=" * 80)
    print("Athena-Based Multi-Agent Framework - STRUCTURED_ONLY Field Test")
    print("=" * 80)

    try:
        success = test_structured_extraction()

        if success:
            print("\n✅ TEST PASSED: Extraction accuracy >= 80%")
            sys.exit(0)
        else:
            print("\n⚠️  TEST INCOMPLETE: Accuracy < 80% or errors occurred")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
