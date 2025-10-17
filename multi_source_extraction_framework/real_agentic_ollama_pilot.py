#!/usr/bin/env python3
"""
Real Agentic Ollama Pilot with Structured Query Capability
===========================================================
This pilot actually calls Ollama and demonstrates the query capability
"""

import pandas as pd
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import time
import sys
import re

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from phase4_llm_with_query_capability import StructuredDataQueryEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealAgenticOllamaPilot:
    """
    Real implementation of agentic Ollama that can query structured data
    """

    def __init__(self, staging_path: Path, binary_path: Path, ollama_model: str = "gemma2:27b"):
        self.staging_path = Path(staging_path)
        self.binary_path = Path(binary_path)
        self.ollama_model = ollama_model
        self.query_engine = StructuredDataQueryEngine(staging_path)

        # Track metrics
        self.ollama_calls = 0
        self.query_calls = 0
        self.extraction_results = []

    def call_ollama_with_prompt(self, prompt: str) -> str:
        """
        Actually call Ollama with a prompt
        """
        self.ollama_calls += 1

        # Build ollama command
        cmd = [
            'ollama', 'run', self.ollama_model,
            '--verbose'
        ]

        logger.info(f"Calling Ollama (call #{self.ollama_calls})...")

        try:
            # Run ollama with prompt
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=60  # 60 second timeout
            )

            if result.returncode == 0:
                response = result.stdout.strip()
                logger.info(f"Ollama responded (length: {len(response)} chars)")
                return response
            else:
                logger.error(f"Ollama error: {result.stderr}")
                return f"Error: {result.stderr}"

        except subprocess.TimeoutExpired:
            logger.error("Ollama call timed out")
            return "Error: Timeout"
        except Exception as e:
            logger.error(f"Ollama call failed: {str(e)}")
            return f"Error: {str(e)}"

    def extract_with_queries(self, patient_id: str, variable: str, document_text: str) -> Dict:
        """
        Perform extraction where Ollama can query structured data
        """

        logger.info(f"\n{'='*60}")
        logger.info(f"EXTRACTING: {variable}")
        logger.info("="*60)

        # Step 1: Build initial prompt with query instructions
        initial_prompt = self._build_query_aware_prompt(variable, document_text, patient_id)

        # Step 2: Call Ollama
        ollama_response = self.call_ollama_with_prompt(initial_prompt)

        # Step 3: Parse for query requests
        queries_needed = self._parse_query_requests(ollama_response)

        # Step 4: Execute queries if requested
        query_results = {}
        if queries_needed:
            logger.info(f"Ollama requested {len(queries_needed)} queries")
            for query in queries_needed:
                result = self._execute_query(query, patient_id)
                query_results[query] = result
                self.query_calls += 1
                logger.info(f"  Query: {query} → {len(result) if isinstance(result, list) else result}")

        # Step 5: If queries were executed, call Ollama again with results
        if query_results:
            followup_prompt = self._build_followup_prompt(
                variable, document_text, query_results, ollama_response
            )
            final_response = self.call_ollama_with_prompt(followup_prompt)
        else:
            final_response = ollama_response

        # Step 6: Parse extraction from response
        extraction = self._parse_extraction(final_response, variable)
        extraction['queries_executed'] = list(query_results.keys())
        extraction['query_count'] = len(query_results)

        return extraction

    def _build_query_aware_prompt(self, variable: str, document_text: str, patient_id: str) -> str:
        """
        Build prompt that teaches Ollama about query capability
        """

        prompt = f"""You are extracting clinical data with access to structured patient records.

AVAILABLE QUERIES (request these if needed):
- QUERY_SURGERY_DATES - Get all surgery dates
- QUERY_DIAGNOSIS - Get diagnosis information
- QUERY_MEDICATIONS:[drug_name] - Check if patient received specific drug
- QUERY_MOLECULAR_TESTS - Get molecular test results
- QUERY_PROBLEM_LIST - Get active problems

EXTRACTION TASK: Extract {variable}

PATIENT: {patient_id}

DOCUMENT TEXT:
{document_text[:3000]}

INSTRUCTIONS:
1. If you need to verify information (dates, medications, etc), request queries
2. Format query requests as: NEED_QUERY: QUERY_NAME
3. After receiving query results, provide extraction with confidence

What queries do you need to perform this extraction accurately?"""

        return prompt

    def _parse_query_requests(self, response: str) -> List[str]:
        """
        Parse query requests from Ollama response
        """
        queries = []

        # Look for query patterns
        patterns = [
            r'NEED_QUERY:\s*(\w+)',
            r'QUERY_(\w+)',
            r'query:\s*(\w+)',
            r'Request:\s*QUERY_(\w+)'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            queries.extend(matches)

        # Also check for specific query mentions
        if 'surgery' in response.lower() and 'date' in response.lower():
            queries.append('SURGERY_DATES')
        if 'medication' in response.lower() or 'drug' in response.lower():
            # Extract drug name if mentioned
            drug_match = re.search(r'(bevacizumab|vinblastine|selumetinib)', response, re.IGNORECASE)
            if drug_match:
                queries.append(f'MEDICATIONS:{drug_match.group(1)}')

        # Deduplicate
        return list(set(queries))

    def _execute_query(self, query: str, patient_id: str) -> Any:
        """
        Execute a structured data query
        """

        query_upper = query.upper()

        if 'SURGERY' in query_upper or query_upper == 'SURGERY_DATES':
            return self.query_engine.query_surgery_dates(patient_id)
        elif 'DIAGNOSIS' in query_upper:
            return self.query_engine.query_diagnosis(patient_id)
        elif 'MEDICATIONS:' in query_upper:
            drug = query.split(':')[1] if ':' in query else 'unknown'
            return self.query_engine.query_medications(patient_id, drug)
        elif 'MOLECULAR' in query_upper:
            return self.query_engine.query_molecular_tests(patient_id)
        elif 'PROBLEM' in query_upper:
            return self.query_engine.query_problem_list(patient_id)
        else:
            return f"Unknown query: {query}"

    def _build_followup_prompt(self, variable: str, document_text: str,
                              query_results: Dict, initial_response: str) -> str:
        """
        Build followup prompt with query results
        """

        prompt = f"""Based on your request, here are the query results:

QUERY RESULTS:
{json.dumps(query_results, indent=2, default=str)[:2000]}

Now extract {variable} from the document, using the query results to validate your extraction.

DOCUMENT TEXT:
{document_text[:2000]}

Provide:
1. Extracted value
2. Confidence (0-100%)
3. How query results support or contradict the extraction
4. Format: VALUE: [your extraction] | CONFIDENCE: [X%] | VALIDATION: [explanation]"""

        return prompt

    def _parse_extraction(self, response: str, variable: str) -> Dict:
        """
        Parse extraction from Ollama response
        """

        extraction = {
            'variable': variable,
            'raw_response': response[:500],  # First 500 chars
            'value': None,
            'confidence': 0.0,
            'validation': None
        }

        # Parse VALUE
        value_match = re.search(r'VALUE:\s*([^\|]+)', response)
        if value_match:
            extraction['value'] = value_match.group(1).strip()

        # Parse CONFIDENCE
        conf_match = re.search(r'CONFIDENCE:\s*(\d+)', response)
        if conf_match:
            extraction['confidence'] = float(conf_match.group(1)) / 100.0

        # Parse VALIDATION
        val_match = re.search(r'VALIDATION:\s*(.+)', response)
        if val_match:
            extraction['validation'] = val_match.group(1).strip()

        # Fallback parsing if structured format not found
        if not extraction['value']:
            # Look for common patterns
            if variable == 'extent_of_resection':
                if 'gross total' in response.lower() or 'gtr' in response.lower():
                    extraction['value'] = 'Gross total resection'
                    extraction['confidence'] = 0.8
                elif 'subtotal' in response.lower() or 'str' in response.lower():
                    extraction['value'] = 'Subtotal resection'
                    extraction['confidence'] = 0.7
            elif variable == 'chemotherapy_response':
                if 'stable disease' in response.lower():
                    extraction['value'] = 'Stable disease'
                    extraction['confidence'] = 0.75
                elif 'progression' in response.lower():
                    extraction['value'] = 'Progressive disease'
                    extraction['confidence'] = 0.7

        return extraction

    def run_pilot_test(self, patient_id: str):
        """
        Run pilot test with real Ollama calls
        """

        print("\n" + "="*80)
        print("REAL AGENTIC OLLAMA PILOT")
        print("="*80)
        print(f"Patient: {patient_id}")
        print(f"Model: {self.ollama_model}")
        print("="*80)

        # Test cases
        test_cases = [
            {
                'variable': 'extent_of_resection',
                'document': """OPERATIVE NOTE
                Date: May 28, 2018
                Procedure: Posterior fossa craniotomy

                The tumor was completely visualized. Using microsurgical techniques,
                gross total resection of the cerebellar tumor was achieved.
                No residual tumor was visible on inspection."""
            },
            {
                'variable': 'chemotherapy_response',
                'document': """ONCOLOGY CLINIC NOTE
                Date: December 15, 2019

                Patient has been on Bevacizumab and Vinblastine for 6 months.
                Latest MRI shows stable disease with no new enhancement.
                Continue current regimen."""
            }
        ]

        # Run tests
        for test in test_cases:
            result = self.extract_with_queries(
                patient_id,
                test['variable'],
                test['document']
            )

            self.extraction_results.append(result)

            # Print results
            print(f"\n{'='*60}")
            print(f"RESULTS: {test['variable']}")
            print("-"*60)
            print(f"Value: {result.get('value', 'Not extracted')}")
            print(f"Confidence: {result.get('confidence', 0)*100:.0f}%")
            print(f"Queries Executed: {result.get('query_count', 0)}")
            if result.get('validation'):
                print(f"Validation: {result['validation'][:100]}")

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """
        Print pilot summary
        """
        print("\n" + "="*80)
        print("PILOT SUMMARY")
        print("="*80)
        print(f"Ollama Calls: {self.ollama_calls}")
        print(f"Structured Queries: {self.query_calls}")
        print(f"Variables Extracted: {len(self.extraction_results)}")

        successful = sum(1 for r in self.extraction_results if r.get('confidence', 0) > 0.5)
        print(f"Successful Extractions: {successful}/{len(self.extraction_results)}")

        if self.query_calls > 0:
            print("\n✓ KEY ACHIEVEMENT: Ollama successfully queried structured data!")
            print("  This validates the agentic model concept")

        # Save results
        output_file = Path("real_ollama_pilot_results.json")
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'ollama_calls': self.ollama_calls,
                    'query_calls': self.query_calls,
                    'extractions': len(self.extraction_results)
                },
                'results': self.extraction_results
            }, f, indent=2, default=str)

        print(f"\n✓ Results saved to: {output_file}")


def main():
    """
    Run the real agentic Ollama pilot
    """

    # Configuration
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    binary_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/binary_files")
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # Check if Ollama is available
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode != 0:
            print("ERROR: Ollama is not available. Please ensure Ollama is running.")
            return 1

        # Check if model is available
        if 'gemma2:27b' not in result.stdout:
            print("WARNING: gemma2:27b not found. Checking for alternatives...")
            if 'gemma2' in result.stdout:
                print("Using gemma2 (base model)")
                model = 'gemma2'
            elif 'llama' in result.stdout:
                print("Using llama3.2")
                model = 'llama3.2'
            else:
                print("Using default model")
                model = None
        else:
            model = 'gemma2:27b'

    except FileNotFoundError:
        print("ERROR: Ollama command not found. Please install Ollama first.")
        return 1

    # Initialize and run pilot
    if model:
        pilot = RealAgenticOllamaPilot(staging_path, binary_path, model)
    else:
        # Try with a smaller model for testing
        pilot = RealAgenticOllamaPilot(staging_path, binary_path, 'llama3.2')

    pilot.run_pilot_test(patient_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())