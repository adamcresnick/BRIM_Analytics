#!/usr/bin/env python3
"""
Real Document Extraction Pipeline
Uses actual clinical documents from:
1. Materialized imaging.csv text
2. S3 binary retrieval for operative notes and other documents
3. Event-based prioritization from patient journey
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

# Import the query engine from phase4
from phase4_llm_with_query_capability import StructuredDataQueryEngine

# Import Ollama client
from ollama import Client

# AWS Configuration for S3 retrieval
AWS_PROFILE = '343218191717_AWSAdministratorAccess'
AWS_REGION = 'us-east-1'
S3_BUCKET = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
S3_PREFIX = 'prd/source/Binary/'


class RealDocumentRetriever:
    """
    Retrieves actual clinical documents from S3 and materialized tables
    """

    def __init__(self, staging_dir: str, use_s3: bool = True):
        self.staging_dir = Path(staging_dir)
        self.use_s3 = use_s3
        self.s3_client = None

        if use_s3:
            try:
                session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
                self.s3_client = session.client('s3')
                logger.info("AWS S3 client initialized for document retrieval")
            except Exception as e:
                logger.warning(f"S3 not available: {e}. Will use only materialized tables.")
                self.use_s3 = False

    def get_imaging_text(self, patient_id: str, target_date: datetime) -> Optional[str]:
        """
        Get actual imaging report text from materialized imaging.csv
        """
        imaging_path = self.staging_dir / f'patient_{patient_id}' / 'imaging.csv'
        if not imaging_path.exists():
            return None

        imaging_df = pd.read_csv(imaging_path)
        imaging_df['imaging_date'] = pd.to_datetime(imaging_df['imaging_date'])

        # Find imaging within +/- 7 days of target date
        date_window = timedelta(days=7)
        mask = (
            (imaging_df['imaging_date'] >= target_date - date_window) &
            (imaging_df['imaging_date'] <= target_date + date_window)
        )

        matches = imaging_df[mask]
        if not matches.empty:
            # Return the actual imaging narrative text
            row = matches.iloc[0]
            return row['result_information']

        return None

    def retrieve_from_s3(self, binary_id: str) -> Optional[str]:
        """
        Retrieve actual document content from S3
        """
        if not self.s3_client or not binary_id:
            return None

        try:
            # Format S3 key
            if binary_id.startswith('Binary/'):
                s3_binary_id = binary_id[7:]
            else:
                s3_binary_id = binary_id

            s3_binary_id = s3_binary_id.replace('.', '_')
            s3_key = f"{S3_PREFIX}{s3_binary_id}"

            # Get object from S3
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
            logger.error(f"Failed to retrieve {binary_id} from S3: {e}")

        return None

    def get_surgical_documents(self, patient_id: str, surgery_date: datetime,
                             binary_metadata: pd.DataFrame) -> List[Dict]:
        """
        Get actual documents for a surgical event
        """
        documents = []

        # Parse dates
        binary_metadata['dr_date'] = pd.to_datetime(binary_metadata['dr_date'], errors='coerce')

        # Time windows for surgery
        pre_op_window = timedelta(days=7)
        post_op_window = timedelta(days=30)

        # Filter to surgery time window
        mask = (
            (binary_metadata['dr_date'] >= surgery_date - pre_op_window) &
            (binary_metadata['dr_date'] <= surgery_date + post_op_window)
        )
        surgery_docs = binary_metadata[mask].copy()

        # Prioritize document types
        priority_types = [
            'operative',
            'surgery',
            'pathology',
            'anesthesia',
            'imaging',
            'mri',
            'ct'
        ]

        for doc_type in priority_types:
            type_docs = surgery_docs[
                surgery_docs['dr_type_text'].str.lower().str.contains(doc_type, na=False)
            ]

            for idx, row in type_docs.iterrows():
                doc_info = {
                    'document_id': row['dr_id'],
                    'document_type': row['dr_type_text'],
                    'document_date': row['dr_date'],
                    'binary_id': row.get('dc_binary_id', ''),
                    'description': row.get('dr_description', ''),
                    'content': None
                }

                # Get content based on document type
                if 'imaging' in doc_type or 'mri' in doc_type or 'ct' in doc_type:
                    # Try materialized imaging table first
                    content = self.get_imaging_text(patient_id, row['dr_date'])
                    if content:
                        doc_info['content'] = content
                        doc_info['source'] = 'imaging_table'
                elif self.use_s3 and doc_info['binary_id']:
                    # Retrieve from S3
                    content = self.retrieve_from_s3(doc_info['binary_id'])
                    if content:
                        doc_info['content'] = content
                        doc_info['source'] = 's3'

                if doc_info['content']:
                    documents.append(doc_info)

                # Limit documents per type
                if len([d for d in documents if doc_type in d['document_type'].lower()]) >= 2:
                    break

        return documents


class ClinicalVariableExtractor:
    """
    Extract clinical variables using Ollama on real documents
    """

    def __init__(self):
        self.ollama_client = Client(host='http://127.0.0.1:11434')
        self.model_name = 'gemma2:27b'
        logger.info(f"Initialized Ollama extractor with {self.model_name}")

    def extract_extent_of_resection(self, document_text: str) -> Dict:
        """
        Extract extent of resection from operative note or imaging
        """
        prompt = f"""Extract the extent of tumor resection from this medical document.

Use one of these standard terms:
- Gross total resection (GTR) or 100%
- Near-total resection (>95%)
- Subtotal resection (50-95%)
- Partial resection (<50%)
- Biopsy only

Document:
{document_text[:4000]}

Provide only the extent of resection term:"""

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return {
                'value': response['message']['content'].strip(),
                'confidence': 0.9,
                'source': 'llm_extraction'
            }
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {'value': 'Extraction failed', 'confidence': 0.0, 'error': str(e)}

    def extract_tumor_location(self, document_text: str) -> Dict:
        """
        Extract tumor anatomical location
        """
        prompt = f"""Extract the anatomical location of the brain tumor from this document.

Be specific about the brain region (e.g., cerebellum, posterior fossa, brainstem, frontal lobe, etc.)

Document:
{document_text[:4000]}

Provide only the anatomical location:"""

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return {
                'value': response['message']['content'].strip(),
                'confidence': 0.9,
                'source': 'llm_extraction'
            }
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {'value': 'Extraction failed', 'confidence': 0.0, 'error': str(e)}

    def extract_residual_tumor(self, imaging_text: str) -> Dict:
        """
        Extract residual tumor information from post-op imaging
        """
        # Handle NaN or None values
        if pd.isna(imaging_text) or imaging_text is None:
            return {'value': 'No imaging text available', 'confidence': 0.0, 'source': 'no_content'}

        imaging_text = str(imaging_text)

        prompt = f"""From this imaging report, determine if there is residual tumor present.

Extract:
1. Presence of residual tumor (Yes/No)
2. If yes, size and location

Document:
{imaging_text[:4000]}

Provide a brief statement about residual tumor:"""

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return {
                'value': response['message']['content'].strip(),
                'confidence': 0.85,
                'source': 'llm_extraction'
            }
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {'value': 'Extraction failed', 'confidence': 0.0, 'error': str(e)}


def main():
    """
    Main pipeline: Process surgical events with real document extraction
    """

    staging_dir = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files')
    patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

    # Initialize components
    retriever = RealDocumentRetriever(staging_dir, use_s3=True)
    extractor = ClinicalVariableExtractor()

    # Load binary files metadata
    binary_path = staging_dir / f'patient_{patient_id}' / 'binary_files.csv'
    binary_metadata = pd.read_csv(binary_path)
    logger.info(f"Loaded {len(binary_metadata)} binary document references")

    # Get surgical events from procedures
    procedures_path = staging_dir / f'patient_{patient_id}' / 'procedures.csv'
    procedures_df = pd.read_csv(procedures_path)

    # Find tumor surgeries
    display_col = 'pcc_code_coding_display' if 'pcc_code_coding_display' in procedures_df.columns else 'proc_code_text'
    date_col = 'proc_performed_period_start' if 'proc_performed_period_start' in procedures_df.columns else 'procedure_date'

    tumor_keywords = ['tumor', 'craniotomy', 'craniectomy', 'resection', 'brain']
    mask = procedures_df[display_col].str.lower().str.contains('|'.join(tumor_keywords), na=False)
    tumor_surgeries = procedures_df[mask].copy()
    tumor_surgeries[date_col] = pd.to_datetime(tumor_surgeries[date_col])

    # Process each surgery
    results = {
        'patient_id': patient_id,
        'extraction_timestamp': datetime.now().isoformat(),
        'surgeries': []
    }

    for idx, surgery in tumor_surgeries.iterrows():
        surgery_date = surgery[date_col]
        if pd.isna(surgery_date):
            continue

        logger.info(f"\nProcessing surgery: {surgery_date.date()}")
        logger.info(f"Procedure: {surgery[display_col]}")

        # Get documents for this surgery
        documents = retriever.get_surgical_documents(
            patient_id, surgery_date, binary_metadata
        )
        logger.info(f"Retrieved {len(documents)} documents")

        surgery_result = {
            'surgery_date': surgery_date.strftime('%Y-%m-%d'),
            'procedure': surgery[display_col],
            'documents_retrieved': len(documents),
            'extractions': {}
        }

        # Extract from operative notes
        operative_docs = [d for d in documents if 'operative' in d['document_type'].lower()]
        if operative_docs:
            doc = operative_docs[0]
            logger.info(f"  Extracting from operative note ({doc['source']})")

            extent = extractor.extract_extent_of_resection(doc['content'])
            surgery_result['extractions']['extent_of_resection'] = extent

            location = extractor.extract_tumor_location(doc['content'])
            surgery_result['extractions']['tumor_location'] = location

        # Extract from imaging
        imaging_docs = [d for d in documents if any(
            term in d['document_type'].lower() for term in ['imaging', 'mri', 'ct']
        )]
        if imaging_docs:
            doc = imaging_docs[0]
            logger.info(f"  Extracting from imaging report ({doc['source']})")

            residual = extractor.extract_residual_tumor(doc['content'])
            surgery_result['extractions']['residual_tumor'] = residual

        results['surgeries'].append(surgery_result)

    # Save results
    output_path = Path('real_document_extraction_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print("\n" + "="*80)
    print("REAL DOCUMENT EXTRACTION COMPLETE")
    print("="*80)
    print(f"Patient: {patient_id}")
    print(f"Surgeries Processed: {len(results['surgeries'])}")

    for surgery in results['surgeries']:
        print(f"\nSurgery: {surgery['surgery_date']}")
        print(f"  Documents: {surgery['documents_retrieved']}")
        for var, extraction in surgery['extractions'].items():
            print(f"  {var}: {extraction['value']}")

    print(f"\n✓ Results saved to: {output_path}")


if __name__ == '__main__':
    main()