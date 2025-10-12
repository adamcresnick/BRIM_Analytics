#!/usr/bin/env python3
"""
Local LLM Extraction Pipeline - BRIM Mimic

This script mimics BRIM's extraction workflow using Claude API locally:
1. Reads project.csv (documents), variables.csv (extraction instructions), decisions.csv (adjudication logic)
2. For each variable, extracts from relevant documents using Claude
3. For each decision, adjudicates across extracted variables using Claude
4. Outputs results in BRIM-compatible format

Usage:
    python3 local_llm_extraction_pipeline.py <config_file>

Requirements:
    - anthropic Python package
    - ANTHROPIC_API_KEY environment variable set
"""

import os
import sys
import yaml
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
import anthropic
import json
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LocalLLMExtractionPipeline:
    """Mimics BRIM extraction using Claude API locally"""

    def __init__(self, config_file: str):
        """Initialize pipeline with configuration"""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.patient_fhir_id = self.config['patient_fhir_id']
        self.person_id = self.config.get('pseudo_mrn', self.patient_fhir_id)

        # Output directory (same as input files)
        self.output_dir = Path(self.config['output_directory'])

        # Load input files
        self.project_df = None
        self.variables_df = None
        self.decisions_df = None

        # Storage for extraction results
        self.variable_results = []  # List of dicts with extraction results
        self.decision_results = []  # List of dicts with adjudication results

        # Initialize Claude client
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set.\n"
                "Set it with: export ANTHROPIC_API_KEY='your-api-key'"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet model

        logger.info("="*80)
        logger.info("LOCAL LLM EXTRACTION PIPELINE (BRIM Mimic)")
        logger.info("="*80)
        logger.info(f"Patient FHIR ID: {self.patient_fhir_id}")
        logger.info(f"Person ID: {self.person_id}")
        logger.info(f"Model: {self.model}")
        logger.info("="*80 + "\n")

    def load_input_files(self):
        """Load the 3 BRIM input CSV files"""
        logger.info("Loading BRIM input files...")

        # Project file (documents)
        project_file = self.output_dir / f"project_{self.patient_fhir_id}.csv"
        if not project_file.exists():
            raise FileNotFoundError(f"Project file not found: {project_file}")
        self.project_df = pd.read_csv(project_file)
        logger.info(f"  Loaded project.csv: {len(self.project_df)} documents")

        # Variables file (extraction instructions)
        variables_file = self.output_dir / f"variables_{self.patient_fhir_id}.csv"
        if not variables_file.exists():
            raise FileNotFoundError(f"Variables file not found: {variables_file}")
        self.variables_df = pd.read_csv(variables_file)
        logger.info(f"  Loaded variables.csv: {len(self.variables_df)} variables")

        # Decisions file (adjudication instructions)
        decisions_file = self.output_dir / f"decisions_{self.patient_fhir_id}.csv"
        if not decisions_file.exists():
            raise FileNotFoundError(f"Decisions file not found: {decisions_file}")
        self.decisions_df = pd.read_csv(decisions_file)
        logger.info(f"  Loaded decisions.csv: {len(self.decisions_df)} decisions\n")

    def extract_variable_from_document(self, variable_name: str, instruction: str,
                                      note_id: str, note_text: str, note_title: str) -> str:
        """
        Extract a single variable from a single document using Claude

        Returns:
            Extracted value as string
        """
        # Build extraction prompt
        prompt = f"""You are a medical data extraction assistant. Your task is to extract specific information from clinical documents.

DOCUMENT INFORMATION:
- NOTE_ID: {note_id}
- NOTE_TITLE: {note_title}

EXTRACTION TASK:
{instruction}

DOCUMENT TEXT:
{note_text}

INSTRUCTIONS:
1. Read the document carefully
2. Extract ONLY the requested information following the exact format specified
3. If the information is not found or not applicable, return the default value specified in the instruction
4. Return ONLY the extracted value, no explanation or preamble

EXTRACTED VALUE:"""

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0,  # Deterministic extraction
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text response
            result = message.content[0].text.strip()
            return result

        except Exception as e:
            logger.error(f"    Error extracting {variable_name} from {note_id}: {e}")
            return "ERROR"

    def extract_variables(self):
        """Extract all variables from all documents"""
        logger.info("="*80)
        logger.info("STEP 1: VARIABLE EXTRACTION")
        logger.info("="*80 + "\n")

        total_extractions = len(self.variables_df) * len(self.project_df)
        logger.info(f"Total extractions to perform: {total_extractions}")
        logger.info(f"  ({len(self.variables_df)} variables × {len(self.project_df)} documents)\n")

        extraction_count = 0

        # For each variable
        for var_idx, variable_row in self.variables_df.iterrows():
            variable_name = variable_row['variable_name']
            instruction = variable_row['instruction']
            scope = variable_row.get('scope', 'many_per_note')

            logger.info(f"Variable {var_idx+1}/{len(self.variables_df)}: {variable_name} (scope: {scope})")

            # For each document
            for doc_idx, doc_row in self.project_df.iterrows():
                note_id = doc_row['NOTE_ID']
                note_text = doc_row['NOTE_TEXT']
                note_title = doc_row['NOTE_TITLE']

                # Extract variable from document
                extracted_value = self.extract_variable_from_document(
                    variable_name=variable_name,
                    instruction=instruction,
                    note_id=note_id,
                    note_text=note_text,
                    note_title=note_title
                )

                extraction_count += 1

                # Store result
                self.variable_results.append({
                    'PERSON_ID': self.person_id,
                    'NOTE_ID': note_id,
                    'NOTE_TITLE': note_title,
                    'variable_name': variable_name,
                    'extracted_value': extracted_value,
                    'extraction_timestamp': datetime.now().isoformat()
                })

                # Log progress every 10 extractions
                if extraction_count % 10 == 0:
                    logger.info(f"  Progress: {extraction_count}/{total_extractions} extractions completed")

            logger.info(f"  Completed {variable_name} across {len(self.project_df)} documents\n")

        logger.info(f"✓ Variable extraction completed: {extraction_count} total extractions\n")

    def adjudicate_decision(self, decision_name: str, instruction: str,
                           relevant_variables: Dict[str, List[str]]) -> str:
        """
        Adjudicate a decision using extracted variable values

        Args:
            decision_name: Name of the decision
            instruction: Adjudication instruction
            relevant_variables: Dict mapping variable_name -> list of extracted values

        Returns:
            Adjudicated decision value as string
        """
        # Build adjudication prompt
        variable_summary = "\n\n".join([
            f"VARIABLE: {var_name}\nEXTRACTED VALUES ACROSS DOCUMENTS:\n" +
            "\n".join([f"  - {val}" for val in values])
            for var_name, values in relevant_variables.items()
        ])

        prompt = f"""You are a medical data adjudication assistant. Your task is to synthesize information from multiple extracted variables and make a final determination.

ADJUDICATION TASK:
{instruction}

EXTRACTED VARIABLE VALUES:
{variable_summary}

INSTRUCTIONS:
1. Review all extracted variable values carefully
2. Apply the adjudication logic specified in the instruction
3. Return the final adjudicated value following the exact format specified
4. Include brief justification if requested in the instruction
5. Return ONLY the adjudicated value (and justification if requested), no preamble

ADJUDICATED VALUE:"""

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0,  # Deterministic adjudication
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text response
            result = message.content[0].text.strip()
            return result

        except Exception as e:
            logger.error(f"    Error adjudicating {decision_name}: {e}")
            return "ERROR"

    def adjudicate_decisions(self):
        """Adjudicate all decisions using extracted variables"""
        logger.info("="*80)
        logger.info("STEP 2: DECISION ADJUDICATION")
        logger.info("="*80 + "\n")

        logger.info(f"Total decisions to adjudicate: {len(self.decisions_df)}\n")

        # Convert variable_results to DataFrame for easier lookup
        var_results_df = pd.DataFrame(self.variable_results)

        # For each decision
        for dec_idx, decision_row in self.decisions_df.iterrows():
            decision_name = decision_row['variable_name']
            instruction = decision_row['instruction']

            logger.info(f"Decision {dec_idx+1}/{len(self.decisions_df)}: {decision_name}")

            # Identify which variables this decision depends on (mentioned in instruction)
            # Simple heuristic: look for variable names in instruction
            relevant_variables = {}
            for var_name in self.variables_df['variable_name'].unique():
                if var_name in instruction:
                    # Get all extracted values for this variable
                    var_extractions = var_results_df[
                        var_results_df['variable_name'] == var_name
                    ]['extracted_value'].tolist()

                    # Remove duplicates and empty values
                    var_extractions = [v for v in var_extractions if v and v != 'Unavailable' and v != 'N/A']

                    if var_extractions:
                        relevant_variables[var_name] = var_extractions

            logger.info(f"  Depends on {len(relevant_variables)} variables: {', '.join(relevant_variables.keys())}")

            # Adjudicate decision
            adjudicated_value = self.adjudicate_decision(
                decision_name=decision_name,
                instruction=instruction,
                relevant_variables=relevant_variables
            )

            # Store result
            self.decision_results.append({
                'PERSON_ID': self.person_id,
                'decision_name': decision_name,
                'adjudicated_value': adjudicated_value,
                'adjudication_timestamp': datetime.now().isoformat()
            })

            logger.info(f"  Result: {adjudicated_value[:100]}{'...' if len(adjudicated_value) > 100 else ''}\n")

        logger.info(f"✓ Decision adjudication completed: {len(self.decision_results)} decisions\n")

    def save_results(self):
        """Save extraction results to CSV files (BRIM-compatible format)"""
        logger.info("="*80)
        logger.info("STEP 3: SAVING RESULTS")
        logger.info("="*80 + "\n")

        # Save variable extraction results
        var_output_file = self.output_dir / f"extraction_results_{self.patient_fhir_id}.csv"
        var_results_df = pd.DataFrame(self.variable_results)
        var_results_df.to_csv(var_output_file, index=False)
        logger.info(f"  Saved variable extraction results: {var_output_file}")
        logger.info(f"    ({len(var_results_df)} rows)")

        # Save decision adjudication results
        dec_output_file = self.output_dir / f"adjudication_results_{self.patient_fhir_id}.csv"
        dec_results_df = pd.DataFrame(self.decision_results)
        dec_results_df.to_csv(dec_output_file, index=False)
        logger.info(f"  Saved decision adjudication results: {dec_output_file}")
        logger.info(f"    ({len(dec_results_df)} rows)")

        # Create summary pivot table (wide format - one row per person)
        logger.info("\n  Creating summary pivot table...")
        summary_data = {'PERSON_ID': self.person_id}

        # Add decisions (one column per decision)
        for dec_result in self.decision_results:
            summary_data[dec_result['decision_name']] = dec_result['adjudicated_value']

        summary_df = pd.DataFrame([summary_data])
        summary_file = self.output_dir / f"extraction_summary_{self.patient_fhir_id}.csv"
        summary_df.to_csv(summary_file, index=False)
        logger.info(f"  Saved extraction summary: {summary_file}")
        logger.info(f"    ({len(summary_df.columns)} columns)\n")

        return var_output_file, dec_output_file, summary_file

    def run(self):
        """Execute the full extraction pipeline"""
        start_time = datetime.now()

        try:
            # Step 1: Load input files
            self.load_input_files()

            # Step 2: Extract variables
            self.extract_variables()

            # Step 3: Adjudicate decisions
            self.adjudicate_decisions()

            # Step 4: Save results
            var_file, dec_file, summary_file = self.save_results()

            # Summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info("="*80)
            logger.info("✓ EXTRACTION PIPELINE COMPLETED")
            logger.info("="*80)
            logger.info(f"Total execution time: {duration:.1f} seconds")
            logger.info(f"\nOutput files:")
            logger.info(f"  1. Variable extractions: {var_file.name}")
            logger.info(f"  2. Decision adjudications: {dec_file.name}")
            logger.info(f"  3. Summary (wide format): {summary_file.name}")
            logger.info("="*80 + "\n")

            return 0

        except Exception as e:
            logger.error(f"\n❌ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return 1


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python3 local_llm_extraction_pipeline.py <config_file>")
        print("\nExample:")
        print("  python3 local_llm_extraction_pipeline.py patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml")
        sys.exit(1)

    config_file = sys.argv[1]

    if not os.path.exists(config_file):
        print(f"Error: Config file not found: {config_file}")
        sys.exit(1)

    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export ANTHROPIC_API_KEY='your-api-key'")
        print("\nOr get an API key at: https://console.anthropic.com/")
        sys.exit(1)

    # Run pipeline
    pipeline = LocalLLMExtractionPipeline(config_file)
    exit_code = pipeline.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
