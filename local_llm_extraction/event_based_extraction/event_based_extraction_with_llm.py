#!/usr/bin/env python3
"""
Event-Based Extraction with Real LLM Integration
Combines event-based workflow with actual Ollama/MedGemma extraction
"""

import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the query engine from phase4
from phase4_llm_with_query_capability import StructuredDataQueryEngine

# Import Ollama client
try:
    from ollama import Client
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not available. Install with: pip install ollama")

class EventBasedLLMExtraction:
    """
    Event-based extraction with real LLM calls and structured data queries
    """

    def __init__(self, staging_dir: str, use_medgemma: bool = False):
        self.staging_dir = Path(staging_dir)
        self.query_engine = StructuredDataQueryEngine(staging_dir)
        self.use_medgemma = use_medgemma

        if not use_medgemma and OLLAMA_AVAILABLE:
            self.ollama_client = Client(host='http://127.0.0.1:11434')
            self.model_name = 'gemma2:27b'
            logger.info(f"Using Ollama with model: {self.model_name}")
        elif use_medgemma:
            logger.info("MedGemma mode selected (would need implementation)")
        else:
            logger.warning("No LLM available - will use mock extraction")

    def identify_surgical_events(self, patient_id: str) -> List[Dict]:
        """
        Identify all surgical events from procedures table
        """
        procedures_path = self.staging_dir / f'patient_{patient_id}' / 'procedures.csv'
        if not procedures_path.exists():
            logger.warning(f"Procedures file not found: {procedures_path}")
            return []

        procedures_df = pd.read_csv(procedures_path)

        # Filter for tumor-related surgeries using correct column names
        tumor_keywords = ['tumor', 'craniotomy', 'craniectomy', 'resection', 'brain']

        # Check for procedure description in multiple possible columns
        if 'pcc_code_coding_display' in procedures_df.columns:
            display_col = 'pcc_code_coding_display'
        elif 'proc_code_text' in procedures_df.columns:
            display_col = 'proc_code_text'
        else:
            display_col = procedures_df.columns[0]  # Fallback

        mask = procedures_df[display_col].str.lower().str.contains('|'.join(tumor_keywords), na=False)
        tumor_surgeries = procedures_df[mask].copy()

        # Group by date to identify distinct events
        date_col = 'proc_performed_period_start' if 'proc_performed_period_start' in procedures_df.columns else 'procedure_date'
        tumor_surgeries[date_col] = pd.to_datetime(tumor_surgeries[date_col])
        tumor_surgeries = tumor_surgeries.sort_values(date_col)

        # Identify unique surgical events (group same-day procedures)
        events = []
        seen_dates = set()

        for idx, row in tumor_surgeries.iterrows():
            surgery_date = row[date_col].date()
            if surgery_date not in seen_dates:
                seen_dates.add(surgery_date)

                # Determine if initial or progressive
                event_type = 'Initial CNS Tumor' if len(events) == 0 else 'Progressive'

                # Handle age_at_procedure_days safely
                age_days = row.get('age_at_procedure_days', 0)
                if pd.isna(age_days):
                    age_days = 0

                events.append({
                    'event_number': len(events) + 1,
                    'date': str(surgery_date),
                    'event_type': event_type,
                    'procedure': row[display_col],
                    'age_at_event_days': int(age_days)
                })

        return events

    def extract_with_llm_and_queries(self, document_text: str, variable_name: str,
                                     event_context: Dict) -> Dict:
        """
        Extract variable using LLM with ability to query structured data
        """
        # Create extraction prompt with query capability
        prompt = f"""You are extracting clinical variables from medical documents.
You have access to structured data that you can query to validate your extraction.

AVAILABLE QUERY FUNCTIONS:
- QUERY_SURGERY_DATES: Get all surgery dates for the patient
- QUERY_MEDICATIONS:[drug_name]: Query specific medication records
- QUERY_DIAGNOSIS: Get diagnosis information
- QUERY_MOLECULAR_TESTS: Get molecular test results

TASK: Extract '{variable_name}' for surgical event on {event_context['date']}

DOCUMENT CONTENT:
{document_text[:3000]}  # Truncate for context window

INSTRUCTIONS:
1. First, attempt to extract the variable from the document
2. If you need to validate or get additional context, use a query function
3. Format queries as: QUERY_FUNCTION_NAME or QUERY_FUNCTION_NAME:parameter
4. Provide your final answer with confidence score

Please extract the value and indicate any queries you need to make."""

        if OLLAMA_AVAILABLE and not self.use_medgemma:
            try:
                # Make LLM call
                response = self.ollama_client.chat(
                    model=self.model_name,
                    messages=[{'role': 'user', 'content': prompt}]
                )

                llm_output = response['message']['content']

                # Parse LLM output for query requests
                queries_executed = []
                if 'QUERY_' in llm_output:
                    # Extract and execute queries
                    lines = llm_output.split('\n')
                    for line in lines:
                        if line.startswith('QUERY_'):
                            query_parts = line.split(':')
                            query_type = query_parts[0].replace('QUERY_', '').lower()

                            if query_type == 'surgery_dates':
                                result = self.query_engine.query_surgery_dates(event_context['patient_id'])
                                queries_executed.append({'type': 'surgery_dates', 'result': result})

                            elif query_type == 'medications' and len(query_parts) > 1:
                                drug_name = query_parts[1].strip()
                                result = self.query_engine.query_medications(
                                    event_context['patient_id'], drug_name
                                )
                                queries_executed.append({'type': f'medications:{drug_name}', 'result': result})

                # Extract the final value from LLM output
                # This is simplified - real implementation would parse more carefully
                value = self._parse_llm_extraction(llm_output, variable_name)

                return {
                    'value': value,
                    'confidence': 0.85 if queries_executed else 0.75,
                    'queries_executed': [q['type'] for q in queries_executed],
                    'llm_calls': 1,
                    'method': 'ollama_with_queries'
                }

            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
                return {
                    'value': 'Extraction Error',
                    'confidence': 0.0,
                    'error': str(e)
                }
        else:
            # Fallback mock extraction
            return {
                'value': 'Mock Value',
                'confidence': 0.5,
                'method': 'mock'
            }

    def _parse_llm_extraction(self, llm_output: str, variable_name: str) -> str:
        """
        Parse the LLM output to extract the final value
        """
        # Look for common patterns in LLM output
        patterns = {
            'extent_of_resection': [
                'gross total resection', 'subtotal resection', 'partial resection',
                'near total resection', 'biopsy only'
            ],
            'tumor_location': [
                'cerebellum', 'posterior fossa', 'brainstem', 'frontal lobe',
                'temporal lobe', 'parietal lobe', 'occipital lobe'
            ],
            'metastasis': ['yes', 'no', 'present', 'absent', 'none identified'],
            'progression_recurrence_indicator': ['initial', 'progressive', 'recurrent']
        }

        llm_lower = llm_output.lower()

        # Try to find known values for this variable
        if variable_name in patterns:
            for pattern in patterns[variable_name]:
                if pattern in llm_lower:
                    return pattern.title()

        # Look for explicit statements
        if 'value:' in llm_lower:
            parts = llm_output.split('value:')
            if len(parts) > 1:
                value = parts[1].split('\n')[0].strip()
                return value

        # Default
        return 'Unable to determine'

    def extract_variables_for_event(self, patient_id: str, event: Dict,
                                   binary_metadata: pd.DataFrame) -> Dict:
        """
        Extract all variables for a specific surgical event using LLM
        """
        # Select documents relevant to this event
        event_docs = self._select_event_documents(event, binary_metadata)

        # Prepare event context
        event_context = {
            'patient_id': patient_id,
            'date': event['date'],
            'event_type': event['event_type'],
            'event_number': event['event_number']
        }

        variables = {
            'event_number': event['event_number'],
            'event_type_structured': event['event_type'],
            'surgery_date': event['date'],
            'age_at_event_days': event['age_at_event_days']
        }

        # Variables requiring LLM extraction
        llm_variables = [
            'extent_from_operative_note',
            'extent_from_postop_imaging',
            'tumor_location',
            'metastasis',
            'progression_recurrence_indicator',
            'site_of_progression'
        ]

        total_llm_calls = 0
        total_queries = []

        for var_name in llm_variables:
            # Select appropriate documents for this variable
            if 'operative' in var_name:
                doc_mask = event_docs['dr_type_text'].str.contains('operative|surgery',
                                                                  case=False, na=False)
            elif 'imaging' in var_name:
                doc_mask = event_docs['dr_type_text'].str.contains('imaging|mri|ct',
                                                                  case=False, na=False)
            else:
                doc_mask = pd.Series([True] * len(event_docs))

            # Ensure doc_mask has same index as event_docs
            doc_mask = doc_mask.reindex(event_docs.index, fill_value=False)
            relevant_docs = event_docs[doc_mask]

            if len(relevant_docs) > 0:
                # For now, use first relevant document
                # In production, would aggregate across multiple docs
                doc = relevant_docs.iloc[0]

                # Load document content (simplified - would actually load from binary URL)
                document_text = f"[Document {doc['dr_id']}: {doc.get('dr_description', 'No description')}]"

                # Extract with LLM and queries
                extraction = self.extract_with_llm_and_queries(
                    document_text, var_name, event_context
                )

                variables[var_name] = extraction['value']
                if 'llm_calls' in extraction:
                    total_llm_calls += extraction['llm_calls']
                if 'queries_executed' in extraction:
                    total_queries.extend(extraction['queries_executed'])
            else:
                variables[var_name] = 'No relevant documents'

        # Add extraction metadata
        variables['_extraction_metadata'] = {
            'total_llm_calls': total_llm_calls,
            'total_queries_executed': len(set(total_queries)),
            'unique_queries': list(set(total_queries)),
            'documents_processed': len(event_docs)
        }

        return variables

    def _select_event_documents(self, event: Dict, binary_metadata: pd.DataFrame) -> pd.DataFrame:
        """
        Select documents within time window of surgical event
        """
        event_date = pd.to_datetime(event['date'], utc=True)

        # Parse document dates
        if 'dr_date' in binary_metadata.columns:
            binary_metadata['dr_date'] = pd.to_datetime(
                binary_metadata['dr_date'], utc=True, errors='coerce'
            )

            # Time window: -30 to +90 days from surgery
            start_date = event_date - timedelta(days=30)
            end_date = event_date + timedelta(days=90)

            mask = (binary_metadata['dr_date'] >= start_date) & \
                   (binary_metadata['dr_date'] <= end_date)
            event_docs = binary_metadata[mask].copy()

            # Calculate proximity to surgery
            event_docs['days_from_surgery'] = (
                event_docs['dr_date'] - event_date
            ).dt.days

            # Sort by proximity
            event_docs['abs_days'] = event_docs['days_from_surgery'].abs()
            event_docs = event_docs.sort_values('abs_days')

            # Limit to most relevant documents
            return event_docs.head(20)  # Top 20 most relevant docs
        else:
            # Return sample if no date column
            return binary_metadata.head(10)

    def process_patient_events(self, patient_id: str) -> Dict:
        """
        Process all surgical events for a patient with LLM extraction
        """
        # Load binary files metadata
        binary_path = self.staging_dir / f'patient_{patient_id}' / 'binary_files.csv'
        if not binary_path.exists():
            logger.error(f"Binary files not found: {binary_path}")
            return {'error': 'Binary files not found'}

        binary_metadata = pd.read_csv(binary_path)
        logger.info(f"Loaded {len(binary_metadata)} documents")

        # Identify surgical events
        events = self.identify_surgical_events(patient_id)
        logger.info(f"Identified {len(events)} surgical events")

        results = {
            'patient_id': patient_id,
            'total_events': len(events),
            'extraction_method': 'ollama' if OLLAMA_AVAILABLE else 'mock',
            'events': []
        }

        for event in events:
            logger.info(f"\nProcessing Event {event['event_number']}: {event['date']}")

            # Extract variables for this event
            event_variables = self.extract_variables_for_event(
                patient_id, event, binary_metadata
            )

            results['events'].append({
                'event_info': event,
                'variables': event_variables
            })

            # Log extraction statistics
            if '_extraction_metadata' in event_variables:
                meta = event_variables['_extraction_metadata']
                logger.info(f"  LLM Calls: {meta['total_llm_calls']}")
                logger.info(f"  Queries Executed: {meta['total_queries_executed']}")
                if meta['unique_queries']:
                    logger.info(f"  Query Types: {', '.join(meta['unique_queries'])}")

        return results


def main():
    """Test the event-based LLM extraction"""

    # Configuration
    staging_dir = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files'
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Initialize extractor
    extractor = EventBasedLLMExtraction(staging_dir, use_medgemma=False)

    # Process all events
    results = extractor.process_patient_events(patient_id)

    # Save results
    output_path = Path('event_based_llm_extraction_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print("\n" + "="*80)
    print("EVENT-BASED LLM EXTRACTION COMPLETE")
    print("="*80)
    print(f"Patient: {patient_id}")
    print(f"Total Events: {results['total_events']}")
    print(f"Extraction Method: {results['extraction_method']}")

    for event_data in results['events']:
        event = event_data['event_info']
        vars = event_data['variables']
        meta = vars.get('_extraction_metadata', {})

        print(f"\nEvent {event['event_number']}: {event['date']} ({event['event_type']})")
        print(f"  LLM Calls Made: {meta.get('total_llm_calls', 0)}")
        print(f"  Queries Executed: {meta.get('total_queries_executed', 0)}")
        if meta.get('unique_queries'):
            print(f"  Query Types: {', '.join(meta['unique_queries'])}")
        print(f"  Key Findings:")
        print(f"    - Extent: {vars.get('extent_from_operative_note', 'N/A')}")
        print(f"    - Location: {vars.get('tumor_location', 'N/A')}")
        print(f"    - Progression: {vars.get('progression_recurrence_indicator', 'N/A')}")

    print(f"\n✓ Full results saved to: {output_path}")


if __name__ == '__main__':
    main()