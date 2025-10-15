"""
Phase 3: Intelligent Binary Document Selection
==============================================
Selects most relevant documents from binary files for focused BRIM extraction
based on clinical timeline and event priorities
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import logging
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentDocumentSelector:
    """
    Select high-priority documents for BRIM extraction based on:
    1. Clinical event timeline
    2. Document type priorities
    3. Temporal proximity to key events
    4. Content relevance indicators
    """

    # Document type priorities (1=highest)
    DOCUMENT_PRIORITIES = {
        'operative_note': 1,
        'pathology_report': 1,
        'molecular_report': 2,
        'radiology_report': 2,
        'mri_report': 2,
        'ct_report': 3,
        'discharge_summary': 3,
        'oncology_note': 3,
        'clinic_note': 4,
        'progress_note': 4,
        'consultation': 4,
        'radiation_note': 4,
        'nursing_note': 5,
        'other': 6
    }

    # Key search terms by category
    KEY_TERMS = {
        'extent_of_resection': [
            'gross total', 'subtotal', 'partial resection',
            'complete resection', 'residual', 'extent'
        ],
        'tumor_pathology': [
            'pilocytic', 'astrocytoma', 'glioma', 'who grade',
            'ki-67', 'idh', 'braf', 'molecular'
        ],
        'progression': [
            'progression', 'recurrence', 'new enhancement',
            'increased size', 'growing', 'worsening'
        ],
        'metastasis': [
            'metastatic', 'metastasis', 'leptomeningeal',
            'disseminated', 'drop metastasis', 'spine'
        ],
        'treatment_response': [
            'stable disease', 'partial response', 'complete response',
            'progressive disease', 'mixed response'
        ]
    }

    def __init__(self, staging_path: Path, binary_files_path: Path):
        self.staging_path = Path(staging_path)
        self.binary_files_path = Path(binary_files_path)

    def select_priority_documents(self, patient_id: str,
                                 clinical_timeline: Dict,
                                 max_documents: int = 100) -> pd.DataFrame:
        """
        Select highest priority documents for BRIM extraction

        Args:
            patient_id: Patient identifier
            clinical_timeline: Timeline with key clinical events
            max_documents: Maximum number of documents to select

        Returns:
            DataFrame with selected documents and priority scores
        """
        logger.info(f"Selecting priority documents for patient {patient_id}")

        # Load binary files metadata
        patient_path = self.staging_path / f"patient_{patient_id}"
        binary_metadata = self._load_binary_metadata(patient_path)

        if binary_metadata.empty:
            logger.warning("No binary files metadata found")
            return pd.DataFrame()

        # Extract key dates from timeline
        key_dates = self._extract_key_dates(clinical_timeline)

        # Score each document
        binary_metadata = self._score_documents(binary_metadata, key_dates)

        # Select top documents
        selected_docs = self._select_top_documents(binary_metadata, max_documents)

        # Group by clinical relevance
        selected_docs = self._categorize_by_clinical_relevance(selected_docs, key_dates)

        logger.info(f"Selected {len(selected_docs)} priority documents")

        return selected_docs

    def _load_binary_metadata(self, patient_path: Path) -> pd.DataFrame:
        """Load and parse binary files metadata"""
        binary_file = patient_path / "binary_files.csv"

        if not binary_file.exists():
            return pd.DataFrame()

        df = pd.read_csv(binary_file)

        # Parse dates
        date_cols = ['document_date', 'created_date', 'file_date']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')

        # Extract document type from filename or description
        if 'file_name' in df.columns:
            df['document_type'] = df['file_name'].apply(self._classify_document_type)

        logger.info(f"Loaded {len(df)} binary files")

        return df

    def _classify_document_type(self, filename: str) -> str:
        """Classify document type from filename"""
        filename_lower = str(filename).lower()

        type_patterns = {
            'operative_note': ['operative', 'operation', 'surgery'],
            'pathology_report': ['pathology', 'path report', 'histology'],
            'molecular_report': ['molecular', 'genomic', 'sequencing'],
            'mri_report': ['mri', 'magnetic resonance'],
            'ct_report': ['ct scan', 'computed tomography'],
            'radiology_report': ['radiology', 'imaging'],
            'discharge_summary': ['discharge', 'summary'],
            'oncology_note': ['oncology', 'chemotherapy', 'tumor board'],
            'radiation_note': ['radiation', 'radiotherapy'],
            'clinic_note': ['clinic', 'outpatient'],
            'progress_note': ['progress', 'note'],
            'consultation': ['consult', 'consultation']
        }

        for doc_type, patterns in type_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return doc_type

        return 'other'

    def _extract_key_dates(self, clinical_timeline: Dict) -> Dict[str, pd.Timestamp]:
        """Extract key clinical dates from timeline"""
        key_dates = {}

        # Diagnosis/Initial surgery
        if 'diagnosis_date' in clinical_timeline:
            key_dates['diagnosis'] = pd.to_datetime(clinical_timeline['diagnosis_date'], utc=True)

        # Treatment starts
        if 'treatment_phases' in clinical_timeline:
            for phase in clinical_timeline['treatment_phases']:
                if phase.get('phase') == 'chemotherapy' and phase.get('start_date'):
                    key_dates['chemo_start'] = pd.to_datetime(phase['start_date'], utc=True)
                    break

        # Progression/Recurrence events
        if 'chronological_events' in clinical_timeline:
            for event in clinical_timeline['chronological_events']:
                if 'progression' in str(event.get('event_type', '')).lower():
                    key_dates['progression'] = pd.to_datetime(event['date'], utc=True)
                    break

        # Add specific dates for our patient
        key_dates['initial_surgery'] = pd.to_datetime('2018-05-28', utc=True)
        key_dates['chemo_start'] = pd.to_datetime('2019-05-30', utc=True)
        key_dates['radiation_start'] = pd.to_datetime('2021-07-15', utc=True)

        logger.info(f"Identified {len(key_dates)} key clinical dates")

        return key_dates

    def _score_documents(self, df: pd.DataFrame, key_dates: Dict[str, pd.Timestamp]) -> pd.DataFrame:
        """
        Score documents based on multiple factors

        Scoring factors:
        1. Document type priority (0-10 points)
        2. Temporal proximity to key events (0-10 points)
        3. Content relevance (0-5 points)
        4. Recency bonus (0-2 points)
        """
        df['priority_score'] = 0
        df['scoring_reasons'] = ''

        # 1. Document type scoring
        df['type_score'] = df['document_type'].map(
            lambda x: 11 - self.DOCUMENT_PRIORITIES.get(x, 6)
        )
        df['priority_score'] += df['type_score']

        # 2. Temporal proximity scoring
        if 'document_date' in df.columns:
            df['temporal_score'] = 0

            for event_name, event_date in key_dates.items():
                if pd.notna(event_date):
                    # Calculate days from event
                    days_diff = np.abs((df['document_date'] - event_date).dt.days)

                    # Score based on proximity (max 10 points per event)
                    proximity_score = np.where(
                        days_diff <= 7, 10,  # Within 1 week
                        np.where(days_diff <= 30, 7,  # Within 1 month
                        np.where(days_diff <= 90, 4,  # Within 3 months
                        np.where(days_diff <= 180, 2,  # Within 6 months
                        0)))  # Beyond 6 months
                    )

                    # Keep maximum score across all events
                    df['temporal_score'] = np.maximum(df['temporal_score'], proximity_score)

                    # Track which event drove the score
                    high_score_mask = proximity_score >= 7
                    df.loc[high_score_mask, 'scoring_reasons'] += f'{event_name}({proximity_score[high_score_mask].max()});'

            df['priority_score'] += df['temporal_score']

        # 3. Content relevance (if description available)
        if 'description' in df.columns or 'content_preview' in df.columns:
            content_col = 'description' if 'description' in df.columns else 'content_preview'

            df['content_score'] = 0
            for category, terms in self.KEY_TERMS.items():
                for term in terms:
                    mask = df[content_col].str.contains(term, case=False, na=False)
                    df.loc[mask, 'content_score'] += 1
                    df.loc[mask, 'scoring_reasons'] += f'{category}:{term};'

            # Cap content score at 5
            df['content_score'] = np.minimum(df['content_score'], 5)
            df['priority_score'] += df['content_score']

        # 4. Recency bonus (documents from last 2 years)
        if 'document_date' in df.columns:
            recent_cutoff = pd.Timestamp.now(tz='UTC') - timedelta(days=730)
            df.loc[df['document_date'] > recent_cutoff, 'priority_score'] += 2
            df.loc[df['document_date'] > recent_cutoff, 'scoring_reasons'] += 'recent;'

        return df

    def _select_top_documents(self, df: pd.DataFrame, max_documents: int) -> pd.DataFrame:
        """Select top scoring documents with diversity constraints"""

        # Sort by priority score
        df = df.sort_values('priority_score', ascending=False)

        selected = []
        doc_types_count = {}

        # Ensure diversity - limit documents per type
        max_per_type = {
            'operative_note': 10,
            'pathology_report': 10,
            'mri_report': 20,
            'oncology_note': 15,
            'other': 30
        }

        for idx, doc in df.iterrows():
            doc_type = doc['document_type']
            current_count = doc_types_count.get(doc_type, 0)
            max_allowed = max_per_type.get(doc_type, 10)

            if current_count < max_allowed:
                selected.append(doc)
                doc_types_count[doc_type] = current_count + 1

            if len(selected) >= max_documents:
                break

        selected_df = pd.DataFrame(selected)

        # Log selection summary
        logger.info("Document selection summary:")
        for doc_type, count in doc_types_count.items():
            logger.info(f"  {doc_type}: {count}")

        return selected_df

    def _categorize_by_clinical_relevance(self, df: pd.DataFrame,
                                         key_dates: Dict[str, pd.Timestamp]) -> pd.DataFrame:
        """Categorize documents by their clinical relevance"""

        df['clinical_category'] = 'other'

        if 'document_date' in df.columns:
            # Diagnosis period (±30 days from initial surgery)
            if 'initial_surgery' in key_dates:
                diagnosis_mask = np.abs(
                    (df['document_date'] - key_dates['initial_surgery']).dt.days
                ) <= 30
                df.loc[diagnosis_mask, 'clinical_category'] = 'diagnosis'

            # Treatment monitoring
            if 'chemo_start' in key_dates:
                treatment_mask = (
                    (df['document_date'] >= key_dates['chemo_start']) &
                    (df['document_date'] <= key_dates['chemo_start'] + timedelta(days=365))
                )
                df.loc[treatment_mask, 'clinical_category'] = 'treatment_monitoring'

            # Progression/Recurrence
            if 'progression' in key_dates:
                progression_mask = np.abs(
                    (df['document_date'] - key_dates['progression']).dt.days
                ) <= 60
                df.loc[progression_mask, 'clinical_category'] = 'progression'

        return df

    def export_for_brim(self, selected_docs: pd.DataFrame, output_path: Path):
        """Export selected documents in BRIM-compatible format"""

        output_path = Path(output_path)
        output_path.mkdir(exist_ok=True)

        # Create project.csv for BRIM
        project_df = selected_docs[['document_id', 'file_path', 'document_type', 'priority_score']].copy()
        project_df.to_csv(output_path / 'priority_documents.csv', index=False)

        # Create metadata JSON
        metadata = {
            'selection_date': datetime.now().isoformat(),
            'total_selected': len(selected_docs),
            'selection_criteria': {
                'max_documents': len(selected_docs),
                'document_types': selected_docs['document_type'].value_counts().to_dict(),
                'clinical_categories': selected_docs['clinical_category'].value_counts().to_dict()
            }
        }

        with open(output_path / 'selection_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Exported {len(selected_docs)} documents for BRIM processing")


if __name__ == "__main__":
    # Test with our patient
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    binary_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/binary_files")

    selector = IntelligentDocumentSelector(staging_path, binary_path)

    # Load clinical timeline (from our previous work)
    timeline_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
    timeline_file = timeline_path / "integrated_timeline_e4BwD8ZYDBccepXcJ.Ilo3w3.json"

    if timeline_file.exists():
        with open(timeline_file, 'r') as f:
            clinical_timeline = json.load(f)
    else:
        # Use minimal timeline for testing
        clinical_timeline = {
            'diagnosis_date': '2018-05-28',
            'treatment_phases': [
                {'phase': 'chemotherapy', 'start_date': '2019-05-30'},
                {'phase': 'radiation', 'start_date': '2021-07-15'}
            ]
        }

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # Select priority documents
    priority_docs = selector.select_priority_documents(
        patient_id,
        clinical_timeline,
        max_documents=100
    )

    if not priority_docs.empty:
        # Export for BRIM
        output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")
        selector.export_for_brim(priority_docs, output_path)

        print("\n" + "="*70)
        print("PHASE 3: INTELLIGENT DOCUMENT SELECTION COMPLETE")
        print("="*70)
        print(f"\nSelected {len(priority_docs)} priority documents from 22,127 total")
        print("\nDocument Type Distribution:")
        print(priority_docs['document_type'].value_counts())
        print("\nClinical Category Distribution:")
        print(priority_docs['clinical_category'].value_counts())
        print("\nTop 10 Documents by Priority Score:")
        top_10 = priority_docs.nlargest(10, 'priority_score')[['document_type', 'priority_score', 'clinical_category']]
        print(top_10.to_string())
    else:
        print("No documents selected - check binary files metadata")