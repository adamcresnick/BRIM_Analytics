#!/usr/bin/env python3
"""
Enhanced Extraction with Strategic Fallback
- Retrieves additional documents when variables are unavailable
- Gathers multiple sources of evidence for each variable
- Uses patient timeline and event context for strategic document selection
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

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Ollama client
from ollama import Client

# AWS Configuration
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
AWS_REGION = 'us-east-1'
S3_BUCKET = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
S3_PREFIX = 'prd/source/Binary/'


class StrategicDocumentRetriever:
    """
    Strategically retrieves documents based on patient timeline and extraction needs
    """

    def __init__(self, staging_dir: str):
        self.staging_dir = Path(staging_dir)
        self.s3_client = None

        # Initialize AWS S3 client
        try:
            session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
            self.s3_client = session.client('s3')
            logger.info("AWS S3 client initialized")
        except Exception as e:
            logger.warning(f"S3 not available: {e}")

    def get_primary_documents(self, patient_id: str, event_date: datetime,
                            binary_metadata: pd.DataFrame) -> Dict[str, List]:
        """
        Get primary documents for initial extraction attempt
        Returns documents categorized by type
        """
        documents = {
            'operative': [],
            'pathology': [],
            'imaging': [],
            'progress': [],
            'consultation': []
        }

        # Parse dates
        binary_metadata['dr_date'] = pd.to_datetime(binary_metadata['dr_date'], utc=True, errors='coerce')
        event_date = pd.to_datetime(event_date, utc=True)

        # Time windows for different document types
        windows = {
            'operative': (-3, 7),      # 3 days before to 7 days after
            'pathology': (-7, 30),     # 7 days before to 30 days after
            'imaging': (-7, 30),       # 7 days before to 30 days after
            'progress': (-30, 60),     # 30 days before to 60 days after
            'consultation': (-30, 30)  # 30 days before to 30 days after
        }

        for doc_type, (pre_days, post_days) in windows.items():
            start_date = event_date - timedelta(days=abs(pre_days))
            end_date = event_date + timedelta(days=post_days)

            # Filter by date and document type
            date_mask = (
                (binary_metadata['dr_date'] >= start_date) &
                (binary_metadata['dr_date'] <= end_date)
            )

            # Type-specific filtering
            type_keywords = {
                'operative': ['operative', 'surgery', 'surgical', 'operation'],
                'pathology': ['pathology', 'path report', 'histology', 'cytology'],
                'imaging': ['mri', 'ct', 'imaging', 'radiology', 'scan'],
                'progress': ['progress', 'clinic note', 'follow', 'visit'],
                'consultation': ['consult', 'consultation', 'opinion']
            }

            type_mask = binary_metadata['dr_type_text'].str.lower().str.contains(
                '|'.join(type_keywords[doc_type]), na=False
            )

            relevant_docs = binary_metadata[date_mask & type_mask].copy()

            # Calculate proximity to event
            relevant_docs['days_from_event'] = (relevant_docs['dr_date'] - event_date).dt.days
            relevant_docs['abs_days'] = relevant_docs['days_from_event'].abs()

            # Sort by proximity and limit
            relevant_docs = relevant_docs.sort_values('abs_days').head(5)

            for idx, row in relevant_docs.iterrows():
                documents[doc_type].append(row.to_dict())

        return documents

    def get_fallback_documents(self, patient_id: str, event_date: datetime,
                             binary_metadata: pd.DataFrame,
                             missing_variables: List[str]) -> Dict[str, List]:
        """
        Get additional documents when primary extraction fails
        Uses strategic selection based on missing variables
        """
        fallback_docs = {
            'extended_operative': [],
            'radiology_reports': [],
            'discharge_summaries': [],
            'oncology_notes': [],
            'free_text_athena': []
        }

        event_date = pd.to_datetime(event_date, utc=True)
        binary_metadata['dr_date'] = pd.to_datetime(binary_metadata['dr_date'], utc=True, errors='coerce')

        # Extended search strategies based on missing variables
        if 'extent_of_tumor_resection' in missing_variables:
            # Look for discharge summaries and extended operative window
            extended_window = timedelta(days=14)
            mask = (
                (binary_metadata['dr_date'] >= event_date - timedelta(days=1)) &
                (binary_metadata['dr_date'] <= event_date + extended_window)
            )

            # Discharge summaries often contain surgical summaries
            discharge_mask = binary_metadata['dr_type_text'].str.lower().str.contains(
                'discharge|summary|transfer', na=False
            )
            discharge_docs = binary_metadata[mask & discharge_mask].head(3)
            fallback_docs['discharge_summaries'] = discharge_docs.to_dict('records')

            # Any operative-related notes in extended window
            op_mask = binary_metadata['dr_description'].str.lower().str.contains(
                'resect|excis|remov|debulk|biops', na=False
            ) if 'dr_description' in binary_metadata.columns else pd.Series([False] * len(binary_metadata))

            extended_op = binary_metadata[mask & op_mask].head(5)
            fallback_docs['extended_operative'] = extended_op.to_dict('records')

        if 'tumor_location' in missing_variables:
            # Look for radiology reports in wider window
            wide_window = timedelta(days=60)
            mask = (
                (binary_metadata['dr_date'] >= event_date - wide_window) &
                (binary_metadata['dr_date'] <= event_date + wide_window)
            )

            # Radiology reports with location keywords
            rad_mask = binary_metadata['dr_type_text'].str.lower().str.contains(
                'mri|ct|radiology|imaging', na=False
            )

            # Prioritize reports mentioning anatomical locations
            if 'dr_description' in binary_metadata.columns:
                location_mask = binary_metadata['dr_description'].str.lower().str.contains(
                    'frontal|temporal|parietal|occipital|cerebellum|brainstem|thalamus|ventricle',
                    na=False
                )
                rad_docs = binary_metadata[mask & rad_mask & location_mask].head(5)
            else:
                rad_docs = binary_metadata[mask & rad_mask].head(5)

            fallback_docs['radiology_reports'] = rad_docs.to_dict('records')

            # Oncology notes often describe tumor location
            onc_mask = binary_metadata['dr_type_text'].str.lower().str.contains(
                'oncology|tumor board|cancer|neuro', na=False
            )
            onc_docs = binary_metadata[mask & onc_mask].head(3)
            fallback_docs['oncology_notes'] = onc_docs.to_dict('records')

        # Get free-text Athena entries (structured data with narratives)
        fallback_docs['free_text_athena'] = self._get_athena_freetext(
            patient_id, event_date, missing_variables
        )

        return fallback_docs

    def _get_athena_freetext(self, patient_id: str, event_date: datetime,
                            missing_variables: List[str]) -> List[Dict]:
        """
        Retrieve free-text fields from Athena structured tables
        """
        freetext_sources = []

        # Check pathology table for free-text reports
        pathology_path = self.staging_dir / f'patient_{patient_id}' / 'pathology.csv'
        if pathology_path.exists():
            path_df = pd.read_csv(pathology_path)
            if 'result_text' in path_df.columns:
                # Get pathology reports near event date
                path_df['report_date'] = pd.to_datetime(path_df.get('report_date', path_df.get('date', '')), errors='coerce')
                event_date_naive = pd.to_datetime(event_date).tz_localize(None)

                for idx, row in path_df.iterrows():
                    if pd.notna(row.get('result_text', '')):
                        report_date = pd.to_datetime(row.get('report_date')).tz_localize(None) if pd.notna(row.get('report_date')) else None
                        if report_date and abs((report_date - event_date_naive).days) <= 30:
                            freetext_sources.append({
                                'source': 'pathology',
                                'date': str(report_date),
                                'content': row['result_text'],
                                'type': 'athena_freetext'
                            })

        # Check imaging table for narratives
        imaging_path = self.staging_dir / f'patient_{patient_id}' / 'imaging.csv'
        if imaging_path.exists():
            imaging_df = pd.read_csv(imaging_path)
            imaging_df['imaging_date'] = pd.to_datetime(imaging_df['imaging_date'], utc=True, errors='coerce')

            # Get imaging near event
            mask = (
                (imaging_df['imaging_date'] >= event_date - timedelta(days=30)) &
                (imaging_df['imaging_date'] <= event_date + timedelta(days=30))
            )
            relevant_imaging = imaging_df[mask]

            for idx, row in relevant_imaging.iterrows():
                if pd.notna(row.get('result_information', '')):
                    freetext_sources.append({
                        'source': 'imaging',
                        'date': str(row['imaging_date']),
                        'content': row['result_information'],
                        'type': 'athena_freetext',
                        'modality': row.get('imaging_modality', '')
                    })

        return freetext_sources

    def retrieve_content(self, document_info: Dict) -> Optional[str]:
        """
        Retrieve actual document content from S3 or Athena tables
        """
        # If it's Athena freetext, return directly
        if document_info.get('type') == 'athena_freetext':
            return document_info.get('content', '')

        # Try S3 retrieval for binary documents
        binary_id = document_info.get('dc_binary_id', '')
        if self.s3_client and binary_id:
            try:
                # Format S3 key
                if binary_id.startswith('Binary/'):
                    s3_binary_id = binary_id[7:]
                else:
                    s3_binary_id = binary_id

                s3_binary_id = s3_binary_id.replace('.', '_')
                s3_key = f"{S3_PREFIX}{s3_binary_id}"

                # Get from S3
                response = self.s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
                content = response['Body'].read()

                # Parse and decode
                binary_data = json.loads(content)
                if 'data' in binary_data:
                    decoded = base64.b64decode(binary_data['data']).decode('utf-8', errors='ignore')

                    # Extract text from HTML
                    if '<html' in decoded.lower():
                        soup = BeautifulSoup(decoded, 'html.parser')
                        text = soup.get_text(separator='\n', strip=True)
                        return text

                    return decoded

            except Exception as e:
                logger.debug(f"S3 retrieval failed for {binary_id}: {e}")

        return None


class MultiSourceExtractor:
    """
    Extracts variables from multiple sources and aggregates evidence
    """

    def __init__(self):
        self.ollama_client = Client(host='http://127.0.0.1:11434')
        self.model_name = 'gemma2:27b'
        logger.info(f"Initialized multi-source extractor with {self.model_name}")

    def extract_with_multiple_sources(self, variable_name: str,
                                     documents: List[Tuple[Dict, str]],
                                     event_context: Dict) -> Dict:
        """
        Extract variable from multiple document sources and aggregate evidence
        """
        extractions = []

        for doc_info, content in documents:
            if not content or pd.isna(content):
                continue

            extraction = self._extract_single(variable_name, content, doc_info, event_context)
            if extraction:
                extractions.append(extraction)

        # Aggregate multiple extractions
        if not extractions:
            return {
                'value': 'Unavailable',
                'confidence': 0.0,
                'sources': [],
                'evidence_count': 0
            }

        # Aggregate based on variable type
        aggregated = self._aggregate_extractions(variable_name, extractions)
        return aggregated

    def _extract_single(self, variable_name: str, content: str,
                       doc_info: Dict, event_context: Dict) -> Dict:
        """
        Extract variable from single document
        """
        prompts = {
            'extent_of_tumor_resection': """Extract the extent of tumor resection.
Use ONLY these terms:
- Gross total resection (GTR)
- Near-total resection (>95%)
- Subtotal resection (50-95%)
- Partial resection (<50%)
- Biopsy only

Document: {content}

Provide only the extent term:""",

            'tumor_location': """Extract the anatomical location of the brain tumor.
Be specific (e.g., frontal lobe, temporal lobe, parietal lobe, occipital lobe,
cerebellum, posterior fossa, brainstem, thalamus, ventricles, etc.)

Document: {content}

Provide only the anatomical location:""",

            'metastasis': """Determine if there is metastatic disease.
Look for: CSF spread, spinal metastasis, leptomeningeal disease, drop metastasis

Document: {content}

Answer: Yes/No/Not mentioned:""",

            'site_of_progression': """For progressive disease, identify the site of progression.
Options: Local (same location), Distant/Metastatic (new location), or Cannot determine

Document: {content}

Provide only: Local/Metastatic/Cannot determine:"""
        }

        if variable_name not in prompts:
            return None

        prompt = prompts[variable_name].format(content=content[:3000])

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            return {
                'value': response['message']['content'].strip(),
                'source': doc_info.get('dr_type_text', doc_info.get('source', 'unknown')),
                'date': str(doc_info.get('dr_date', doc_info.get('date', ''))),
                'confidence': 0.8
            }

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None

    def _aggregate_extractions(self, variable_name: str, extractions: List[Dict]) -> Dict:
        """
        Aggregate multiple extractions into final value with confidence
        """
        if not extractions:
            return {'value': 'Unavailable', 'confidence': 0.0, 'sources': [], 'evidence_count': 0}

        # Count value frequencies
        value_counts = {}
        for ext in extractions:
            value = ext['value']
            if value not in value_counts:
                value_counts[value] = 0
            value_counts[value] += 1

        # Get most common value
        most_common = max(value_counts.items(), key=lambda x: x[1])
        consensus_value = most_common[0]
        agreement_ratio = most_common[1] / len(extractions)

        # Calculate confidence based on agreement and source quality
        base_confidence = 0.6 + (agreement_ratio * 0.3)

        # Boost confidence for operative notes and pathology
        high_quality_sources = sum(1 for e in extractions
                                 if 'operative' in e.get('source', '').lower()
                                 or 'pathology' in e.get('source', '').lower())
        if high_quality_sources > 0:
            base_confidence = min(1.0, base_confidence + 0.1 * high_quality_sources)

        return {
            'value': consensus_value,
            'confidence': round(base_confidence, 2),
            'sources': [e['source'] for e in extractions],
            'evidence_count': len(extractions),
            'agreement_ratio': round(agreement_ratio, 2),
            'all_values': [e['value'] for e in extractions]
        }


class EnhancedExtractionPipeline:
    """
    Complete pipeline with fallback strategies
    """

    def __init__(self, staging_dir: str):
        self.staging_dir = Path(staging_dir)
        self.retriever = StrategicDocumentRetriever(staging_dir)
        self.extractor = MultiSourceExtractor()

    def extract_surgical_event(self, patient_id: str, event: Dict,
                              binary_metadata: pd.DataFrame) -> Dict:
        """
        Extract all variables for a surgical event with fallback strategies
        """
        event_date = pd.to_datetime(event['date'])
        event_context = {
            'patient_id': patient_id,
            'event_date': event_date,
            'event_type': event.get('type', 'surgery'),
            'procedure': event.get('procedure', '')
        }

        # Initialize results
        results = {
            'event_info': event,
            'extractions': {},
            'extraction_metadata': {
                'primary_documents_retrieved': 0,
                'fallback_documents_retrieved': 0,
                'total_llm_calls': 0
            }
        }

        # Get primary documents
        primary_docs = self.retriever.get_primary_documents(
            patient_id, event_date, binary_metadata
        )

        # Count primary documents
        primary_count = sum(len(docs) for docs in primary_docs.values())
        results['extraction_metadata']['primary_documents_retrieved'] = primary_count
        logger.info(f"Retrieved {primary_count} primary documents")

        # Variables to extract
        target_variables = [
            'extent_of_tumor_resection',
            'tumor_location',
            'metastasis',
            'site_of_progression' if event.get('type') == 'Progressive' else None
        ]
        target_variables = [v for v in target_variables if v]

        # First attempt: Extract from primary documents
        missing_variables = []

        for variable in target_variables:
            # Gather documents with content
            relevant_docs = []

            # Prioritize document types based on variable
            if variable == 'extent_of_tumor_resection':
                doc_priority = ['operative', 'pathology', 'imaging', 'discharge_summaries']
            elif variable == 'tumor_location':
                doc_priority = ['operative', 'pathology', 'imaging', 'oncology_notes']
            elif variable == 'metastasis':
                doc_priority = ['imaging', 'pathology', 'progress']
            else:
                doc_priority = ['imaging', 'progress', 'consultation']

            for doc_type in doc_priority:
                if doc_type in primary_docs:
                    for doc_info in primary_docs[doc_type]:
                        content = self.retriever.retrieve_content(doc_info)
                        if content:
                            relevant_docs.append((doc_info, content))

            # Extract from multiple sources
            if relevant_docs:
                extraction = self.extractor.extract_with_multiple_sources(
                    variable, relevant_docs, event_context
                )
                results['extractions'][variable] = extraction
                results['extraction_metadata']['total_llm_calls'] += len(relevant_docs)

                # Check if extraction was successful
                if extraction['value'] in ['Unavailable', 'Cannot determine', 'Not mentioned']:
                    missing_variables.append(variable)
                    logger.info(f"Variable {variable} not found in primary documents")
            else:
                missing_variables.append(variable)

        # Fallback: Get additional documents for missing variables
        if missing_variables:
            logger.info(f"Attempting fallback extraction for: {missing_variables}")

            fallback_docs = self.retriever.get_fallback_documents(
                patient_id, event_date, binary_metadata, missing_variables
            )

            # Count fallback documents
            fallback_count = sum(len(docs) for docs in fallback_docs.values())
            results['extraction_metadata']['fallback_documents_retrieved'] = fallback_count
            logger.info(f"Retrieved {fallback_count} fallback documents")

            # Try extracting missing variables from fallback sources
            for variable in missing_variables:
                fallback_relevant = []

                for doc_type, docs in fallback_docs.items():
                    for doc_info in docs:
                        content = self.retriever.retrieve_content(doc_info)
                        if content:
                            fallback_relevant.append((doc_info, content))

                if fallback_relevant:
                    extraction = self.extractor.extract_with_multiple_sources(
                        variable, fallback_relevant, event_context
                    )

                    # Update if better than previous
                    if variable not in results['extractions'] or \
                       extraction['confidence'] > results['extractions'][variable]['confidence']:
                        results['extractions'][variable] = extraction
                        results['extraction_metadata']['total_llm_calls'] += len(fallback_relevant)
                        logger.info(f"Fallback extraction successful for {variable}")

        return results


def main():
    """
    Run enhanced extraction pipeline
    """
    staging_dir = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files')
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Initialize pipeline
    pipeline = EnhancedExtractionPipeline(staging_dir)

    # Load binary metadata
    binary_path = staging_dir / f'patient_{patient_id}' / 'binary_files.csv'
    binary_metadata = pd.read_csv(binary_path)
    logger.info(f"Loaded {len(binary_metadata)} binary document references")

    # Get surgical events
    procedures_path = staging_dir / f'patient_{patient_id}' / 'procedures.csv'
    procedures_df = pd.read_csv(procedures_path)

    # Find tumor surgeries
    display_col = 'pcc_code_coding_display' if 'pcc_code_coding_display' in procedures_df.columns else 'proc_code_text'
    date_col = 'proc_performed_period_start' if 'proc_performed_period_start' in procedures_df.columns else 'procedure_date'

    tumor_keywords = ['tumor', 'craniotomy', 'craniectomy', 'resection', 'brain']
    mask = procedures_df[display_col].str.lower().str.contains('|'.join(tumor_keywords), na=False)
    tumor_surgeries = procedures_df[mask]

    # Process each surgery
    all_results = {
        'patient_id': patient_id,
        'extraction_timestamp': datetime.now().isoformat(),
        'events': []
    }

    for idx, surgery in tumor_surgeries.iterrows():
        event = {
            'date': surgery[date_col],
            'procedure': surgery[display_col],
            'type': 'Initial' if idx == 0 else 'Progressive'
        }

        logger.info(f"\nProcessing surgery: {event['date']} ({event['type']})")

        results = pipeline.extract_surgical_event(patient_id, event, binary_metadata)
        all_results['events'].append(results)

        # Print summary
        print(f"\nEvent: {event['date']}")
        for var, extraction in results['extractions'].items():
            print(f"  {var}: {extraction['value']}")
            print(f"    - Confidence: {extraction['confidence']}")
            print(f"    - Sources: {extraction['evidence_count']} documents")
            if 'agreement_ratio' in extraction:
                print(f"    - Agreement: {extraction['agreement_ratio']}")

    # Save complete results
    output_path = Path('enhanced_extraction_results.json')
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n✓ Complete results saved to: {output_path.absolute()}")

    # Also create data dictionary formatted output
    from radiology_dictionary_extraction import create_patient_record, format_for_redcap

    # Update the extraction results file for dictionary formatting
    with open('real_document_extraction_results.json', 'w') as f:
        # Convert to format expected by dictionary extraction
        converted = {
            'patient_id': patient_id,
            'extraction_timestamp': all_results['extraction_timestamp'],
            'surgeries': []
        }

        for event_result in all_results['events']:
            surgery_entry = {
                'surgery_date': event_result['event_info']['date'],
                'procedure': event_result['event_info']['procedure'],
                'documents_retrieved': event_result['extraction_metadata']['primary_documents_retrieved'],
                'extractions': {}
            }

            # Map variables
            for var, extraction in event_result['extractions'].items():
                surgery_entry['extractions'][var] = extraction

            converted['surgeries'].append(surgery_entry)

        json.dump(converted, f, indent=2, default=str)

    print("\n✓ Data dictionary formatted output updated")
    print(f"  Review at: {output_path.parent / 'radiology_dictionary_output.json'}")


if __name__ == '__main__':
    main()