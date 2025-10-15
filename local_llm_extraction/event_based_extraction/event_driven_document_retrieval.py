#!/usr/bin/env python3
"""
Event-Driven Document Retrieval and Extraction
Retrieves actual binary documents based on clinical events and patient journey
Integrates with LLM extraction pipeline
"""

import json
import logging
import pandas as pd
import boto3
import base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sys
import os
import re

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

# AWS Configuration (optional - for actual retrieval)
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
AWS_REGION = 'us-east-1'
S3_BUCKET = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
S3_PREFIX = 'prd/source/Binary/'


class EventDrivenDocumentRetriever:
    """
    Retrieves documents based on clinical events and patient journey
    """

    def __init__(self, staging_dir: str, use_aws: bool = False):
        self.staging_dir = Path(staging_dir)
        self.use_aws = use_aws
        self.s3_client = None

        if use_aws:
            try:
                session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
                self.s3_client = session.client('s3')
                logger.info("AWS S3 client initialized")
            except Exception as e:
                logger.warning(f"AWS initialization failed: {e}. Will use simulation mode.")
                self.use_aws = False

    def identify_key_clinical_events(self, patient_id: str) -> Dict:
        """
        Identify key clinical events from patient journey
        Returns surgery dates, therapy periods, and other milestones
        """
        events = {
            'surgeries': [],
            'chemotherapy_periods': [],
            'radiation_periods': [],
            'key_imaging_dates': []
        }

        # Get surgeries from procedures
        procedures_path = self.staging_dir / f'patient_{patient_id}' / 'procedures.csv'
        if procedures_path.exists():
            procedures_df = pd.read_csv(procedures_path)

            # Find tumor surgeries
            display_col = 'pcc_code_coding_display' if 'pcc_code_coding_display' in procedures_df.columns else 'proc_code_text'
            date_col = 'proc_performed_period_start' if 'proc_performed_period_start' in procedures_df.columns else 'procedure_date'

            tumor_keywords = ['tumor', 'craniotomy', 'craniectomy', 'resection', 'brain']
            mask = procedures_df[display_col].str.lower().str.contains('|'.join(tumor_keywords), na=False)
            tumor_surgeries = procedures_df[mask].copy()

            for idx, row in tumor_surgeries.iterrows():
                if pd.notna(row[date_col]):
                    events['surgeries'].append({
                        'date': pd.to_datetime(row[date_col]),
                        'description': row[display_col],
                        'type': 'Initial' if len(events['surgeries']) == 0 else 'Progressive'
                    })

        # Get chemotherapy periods from medications
        medications_path = self.staging_dir / f'patient_{patient_id}' / 'medications.csv'
        if medications_path.exists():
            medications_df = pd.read_csv(medications_path)

            # Look for key chemotherapy agents
            chemo_keywords = ['bevacizumab', 'vinblastine', 'carboplatin', 'vincristine']
            for drug in chemo_keywords:
                drug_records = medications_df[
                    medications_df['medication_display'].str.lower().str.contains(drug, na=False)
                ]
                if not drug_records.empty:
                    start_date = pd.to_datetime(drug_records['effective_period_start'].min())
                    end_date = pd.to_datetime(drug_records['effective_period_end'].max())
                    events['chemotherapy_periods'].append({
                        'drug': drug,
                        'start': start_date,
                        'end': end_date
                    })

        return events

    def prioritize_documents_for_event(self, event: Dict, binary_metadata: pd.DataFrame,
                                      event_type: str) -> pd.DataFrame:
        """
        Prioritize documents based on event type and temporal proximity
        """
        # Parse dates
        binary_metadata['dr_date'] = pd.to_datetime(binary_metadata['dr_date'], errors='coerce')

        if event_type == 'surgery':
            event_date = event['date']

            # Define time windows based on clinical relevance
            pre_window = timedelta(days=7)  # Pre-op planning
            post_window = timedelta(days=30)  # Post-op recovery

            # Filter documents in time window
            mask = (
                (binary_metadata['dr_date'] >= event_date - pre_window) &
                (binary_metadata['dr_date'] <= event_date + post_window)
            )
            relevant_docs = binary_metadata[mask].copy()

            # Prioritize by document type
            priority_order = {
                'operative': 1,
                'surgery': 1,
                'anesthesia': 2,
                'pathology': 2,
                'imaging': 3,
                'mri': 3,
                'ct': 3,
                'progress': 4,
                'consult': 5
            }

            # Assign priority scores
            relevant_docs['priority'] = 999  # Default low priority
            for keyword, priority in priority_order.items():
                mask = relevant_docs['dr_type_text'].str.lower().str.contains(keyword, na=False)
                relevant_docs.loc[mask, 'priority'] = priority

            # Sort by priority and date proximity
            relevant_docs['days_from_event'] = abs((relevant_docs['dr_date'] - event_date).dt.days)
            relevant_docs = relevant_docs.sort_values(['priority', 'days_from_event'])

            return relevant_docs.head(10)  # Top 10 most relevant documents

        elif event_type == 'chemotherapy':
            # For chemo, get documents during treatment period
            start_date = event['start']
            end_date = event['end']

            mask = (
                (binary_metadata['dr_date'] >= start_date) &
                (binary_metadata['dr_date'] <= end_date)
            )
            relevant_docs = binary_metadata[mask].copy()

            # Prioritize progress notes and labs
            priority_order = {
                'progress': 1,
                'laboratory': 2,
                'lab': 2,
                'oncology': 3,
                'consult': 4,
                'imaging': 5
            }

            relevant_docs['priority'] = 999
            for keyword, priority in priority_order.items():
                mask = relevant_docs['dr_type_text'].str.lower().str.contains(keyword, na=False)
                relevant_docs.loc[mask, 'priority'] = priority

            relevant_docs = relevant_docs.sort_values(['priority', 'dr_date'])
            return relevant_docs.head(20)  # More documents for longer period

        return pd.DataFrame()  # Empty if no matching event type

    def retrieve_document_content(self, doc_row: pd.Series) -> Optional[str]:
        """
        Retrieve actual document content from S3 or return simulated content
        """
        binary_id = doc_row.get('dc_binary_id', doc_row.get('binary_id', ''))

        if self.use_aws and self.s3_client and binary_id:
            # Actual S3 retrieval
            try:
                # Remove "Binary/" prefix and convert periods
                if binary_id.startswith('Binary/'):
                    s3_binary_id = binary_id[7:]
                else:
                    s3_binary_id = binary_id
                s3_binary_id = s3_binary_id.replace('.', '_')
                s3_key = f"{S3_PREFIX}{s3_binary_id}"

                # Get from S3
                response = self.s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
                content = response['Body'].read()

                # Parse JSON and decode base64
                binary_data = json.loads(content)
                if 'data' in binary_data:
                    decoded = base64.b64decode(binary_data['data']).decode('utf-8', errors='ignore')

                    # Extract text from HTML if needed
                    if '<html' in decoded.lower():
                        soup = BeautifulSoup(decoded, 'html.parser')
                        text = soup.get_text(separator='\n', strip=True)
                        return text
                    return decoded

            except Exception as e:
                logger.error(f"Failed to retrieve {binary_id}: {e}")

        # Fallback: Use actual imaging text from staging files if available
        if 'imaging' in doc_row.get('dr_type_text', '').lower():
            # Try to get from imaging.csv
            imaging_path = self.staging_dir / f"patient_{doc_row.get('patient_id', '')}" / 'imaging.csv'
            if imaging_path.exists():
                imaging_df = pd.read_csv(imaging_path)
                # Match by date
                doc_date = pd.to_datetime(doc_row['dr_date'])
                imaging_df['imaging_date'] = pd.to_datetime(imaging_df['imaging_date'])

                # Find matching imaging report
                date_matches = imaging_df[
                    (imaging_df['imaging_date'].dt.date == doc_date.date())
                ]
                if not date_matches.empty:
                    # Return actual imaging narrative
                    return date_matches.iloc[0]['result_information']

        # Generate informative placeholder
        return f"""
Document Type: {doc_row.get('dr_type_text', 'Unknown')}
Date: {doc_row.get('dr_date', 'Unknown')}
Description: {doc_row.get('dr_description', 'No description')}

[Document content would be retrieved from Binary ID: {binary_id}]
"""


class EventBasedLLMExtractor:
    """
    Performs LLM extraction on retrieved documents
    """

    def __init__(self, staging_dir: str):
        self.staging_dir = Path(staging_dir)
        self.query_engine = StructuredDataQueryEngine(staging_dir)

        if OLLAMA_AVAILABLE:
            self.ollama_client = Client(host='http://127.0.0.1:11434')
            self.model_name = 'gemma2:27b'
            logger.info(f"Using Ollama with model: {self.model_name}")

    def extract_surgical_variables(self, documents: List[Tuple[pd.Series, str]],
                                  event: Dict) -> Dict:
        """
        Extract surgical variables from retrieved documents
        """
        variables = {
            'surgery_date': event['date'].strftime('%Y-%m-%d'),
            'surgery_type': event['type'],
            'procedure': event['description']
        }

        # Find operative note
        operative_note = None
        imaging_report = None

        for doc_row, content in documents:
            if 'operative' in doc_row.get('dr_type_text', '').lower():
                operative_note = content
            elif 'imaging' in doc_row.get('dr_type_text', '').lower():
                if not imaging_report:  # Take first imaging report
                    imaging_report = content

        # Extract extent of resection
        if operative_note:
            extent = self._extract_with_ollama(
                operative_note,
                'extent_of_resection',
                "Extract the extent of tumor resection. Use terms: Gross total resection, Near-total resection (>95%), Subtotal resection (50-95%), Partial resection (<50%), or Biopsy only."
            )
            variables['extent_of_resection'] = extent

        # Extract tumor location
        if operative_note:
            location = self._extract_with_ollama(
                operative_note,
                'tumor_location',
                "Extract the anatomical location of the tumor."
            )
            variables['tumor_location'] = location

        # Validate with imaging
        if imaging_report:
            residual = self._extract_with_ollama(
                imaging_report,
                'residual_tumor',
                "Is there residual tumor present? Extract details about any remaining tumor."
            )
            variables['imaging_validation'] = residual

        return variables

    def _extract_with_ollama(self, document: str, variable: str, instruction: str) -> str:
        """
        Extract variable using Ollama
        """
        if not OLLAMA_AVAILABLE:
            return f"[Mock: {variable}]"

        prompt = f"""{instruction}

Document content:
{document[:3000]}

Extract only the requested information. Be concise and precise."""

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content'].strip()
        except Exception as e:
            logger.error(f"Ollama extraction failed: {e}")
            return "Extraction error"


def main():
    """
    Main execution: Retrieve documents and perform extraction based on clinical events
    """

    staging_dir = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files'
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Initialize components
    retriever = EventDrivenDocumentRetriever(staging_dir, use_aws=False)
    extractor = EventBasedLLMExtractor(staging_dir)

    # Load binary metadata
    binary_path = Path(staging_dir) / f'patient_{patient_id}' / 'binary_files.csv'
    binary_metadata = pd.read_csv(binary_path)
    binary_metadata['patient_id'] = patient_id  # Add for reference

    logger.info(f"Loaded {len(binary_metadata)} binary document references")

    # Identify clinical events
    events = retriever.identify_key_clinical_events(patient_id)
    logger.info(f"Identified {len(events['surgeries'])} surgeries, {len(events['chemotherapy_periods'])} chemo periods")

    results = {
        'patient_id': patient_id,
        'timestamp': datetime.now().isoformat(),
        'surgical_events': []
    }

    # Process each surgical event
    for surgery in events['surgeries']:
        logger.info(f"\nProcessing surgery: {surgery['date'].date()} ({surgery['type']})")

        # Prioritize and retrieve documents
        prioritized_docs = retriever.prioritize_documents_for_event(
            surgery, binary_metadata, 'surgery'
        )

        logger.info(f"  Selected {len(prioritized_docs)} relevant documents")

        # Retrieve content for top documents
        retrieved_documents = []
        for idx, doc_row in prioritized_docs.iterrows():
            if len(retrieved_documents) >= 5:  # Limit to top 5
                break
            content = retriever.retrieve_document_content(doc_row)
            if content:
                retrieved_documents.append((doc_row, content))
                logger.info(f"    Retrieved: {doc_row['dr_type_text']} from {doc_row['dr_date']}")

        # Extract variables
        if retrieved_documents:
            extracted_vars = extractor.extract_surgical_variables(retrieved_documents, surgery)
            results['surgical_events'].append(extracted_vars)

            logger.info(f"  Extracted variables:")
            for key, value in extracted_vars.items():
                if len(str(value)) > 100:
                    logger.info(f"    {key}: {str(value)[:100]}...")
                else:
                    logger.info(f"    {key}: {value}")

    # Save results
    output_path = Path('event_driven_extraction_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "="*80)
    print("EVENT-DRIVEN DOCUMENT RETRIEVAL AND EXTRACTION COMPLETE")
    print("="*80)
    print(f"Patient: {patient_id}")
    print(f"Surgical Events Processed: {len(results['surgical_events'])}")

    for event in results['surgical_events']:
        print(f"\nSurgery: {event['surgery_date']} ({event['surgery_type']})")
        print(f"  Extent: {event.get('extent_of_resection', 'N/A')}")
        print(f"  Location: {event.get('tumor_location', 'N/A')}")
        if 'imaging_validation' in event:
            print(f"  Imaging: {event['imaging_validation'][:100]}...")

    print(f"\n✓ Results saved to: {output_path}")


if __name__ == '__main__':
    main()