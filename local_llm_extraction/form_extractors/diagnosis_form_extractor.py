"""
Diagnosis Form Extractor for CBTN REDCap
Extracts core clinical diagnosis variables including:
- Clinical status at event
- Event type (Initial/Recurrence/Progressive)
- WHO CNS5 diagnosis with grade
- Tumor location (multi-select)
- Metastasis information
- Molecular testing performed
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import re
import boto3
import ollama

from .base_form_extractor import BaseFormExtractor

logger = logging.getLogger(__name__)


class DiagnosisFormExtractor(BaseFormExtractor):
    """
    Extractor for the CBTN Diagnosis form.
    This is the core clinical event form with highest priority variables.
    """

    # WHO CNS5 Diagnosis mapping (abbreviated for key categories)
    WHO_CNS5_CATEGORIES = {
        'high_grade_glioma': [
            'glioblastoma', 'gbm', 'anaplastic astrocytoma', 'aa',
            'high grade glioma', 'hgg', 'grade iv', 'grade 4',
            'idh-mutant', 'idh-wildtype', 'idh wildtype'
        ],
        'low_grade_glioma': [
            'pilocytic astrocytoma', 'low grade glioma', 'lgg',
            'grade i', 'grade ii', 'grade 1', 'grade 2',
            'diffuse astrocytoma', 'oligodendroglioma', 'pleomorphic xanthoastrocytoma'
        ],
        'medulloblastoma': [
            'medulloblastoma', 'mb', 'wnt-activated', 'shh-activated',
            'group 3', 'group 4', 'non-wnt/non-shh'
        ],
        'ependymoma': [
            'ependymoma', 'epn', 'rela fusion', 'yap1 fusion',
            'pfa', 'pfb', 'supratentorial', 'posterior fossa'
        ],
        'dipg_dmg': [
            'dipg', 'diffuse intrinsic pontine glioma', 'dmg',
            'diffuse midline glioma', 'h3 k27m', 'h3 k27-altered',
            'h3.3', 'h3.1', 'pontine glioma', 'brainstem glioma'
        ],
        'atrt': [
            'atrt', 'atypical teratoid rhabdoid', 'at/rt',
            'rhabdoid tumor', 'smarcb1', 'smarca4'
        ]
    }

    # Anatomical location mapping
    TUMOR_LOCATIONS = {
        'frontal': ['frontal', 'prefrontal', 'motor cortex', 'broca'],
        'temporal': ['temporal', 'hippocampus', 'amygdala', 'wernicke'],
        'parietal': ['parietal', 'sensory cortex', 'angular gyrus'],
        'occipital': ['occipital', 'visual cortex', 'calcarine'],
        'cerebellum': ['cerebellum', 'cerebellar', 'posterior fossa', 'vermis'],
        'brainstem': ['brainstem', 'pons', 'medulla', 'midbrain', 'pontine'],
        'thalamus': ['thalamus', 'thalamic', 'diencephalon'],
        'ventricles': ['ventricle', 'ventricular', 'ependymal', 'intraventricular'],
        'spine': ['spine', 'spinal', 'cervical', 'thoracic', 'lumbar', 'cord']
    }

    def __init__(self, data_dictionary_path: str, s3_client=None, ollama_client=None):
        """
        Initialize the Diagnosis form extractor.

        Args:
            data_dictionary_path: Path to CBTN data dictionary
            s3_client: AWS S3 client for document retrieval
            ollama_client: Ollama client for LLM extraction
        """
        super().__init__(data_dictionary_path)
        self.s3_client = s3_client or boto3.client('s3')
        self.ollama_client = ollama_client
        self.s3_bucket = 'cnb-redcap-curation'

    def get_form_name(self) -> str:
        """Return the REDCap form name."""
        return 'diagnosis'

    def get_variable_extraction_config(self, variable_name: str) -> Optional[Dict]:
        """
        Get extraction configuration for diagnosis form variables.

        Returns configuration with document sources and prompts.
        """
        configs = {
            'clinical_status_at_event': {
                'sources': ['discharge_summary', 'death_summary', 'last_encounter'],
                'prompt': """
                Extract the patient's clinical status at this event.

                Use ONLY these exact terms:
                - Alive (for all surgical events)
                - Deceased-due to disease
                - Deceased-due to other causes
                - Deceased-due to unknown causes
                - Unknown

                Look for: vital status, death, expired, passed away, alive, living

                Return ONLY the status term.
                """,
                'default': 'Alive'  # Default for surgical events
            },

            'event_type': {
                'sources': ['pathology_report', 'oncology_note', 'operative_note'],
                'prompt': """
                Determine the event type for this brain tumor surgery/diagnosis.

                Use ONLY these exact terms:
                - Initial CNS Tumor (first diagnosis/surgery)
                - Recurrence (tumor returned after remission)
                - Progressive (tumor growth/progression)
                - Second Malignancy (new, different tumor)
                - Unavailable

                Look for key phrases:
                - "initial diagnosis", "newly diagnosed", "first presentation" → Initial
                - "recurrent", "recurrence", "relapse" → Recurrence
                - "progressive disease", "progression", "increased size" → Progressive
                - "second tumor", "new primary" → Second Malignancy

                Return ONLY the event type term.
                """
            },

            'date_of_event': {
                'sources': ['operative_note', 'pathology_report'],
                'prompt': """
                Extract the date of this surgical event or autopsy.

                Look for:
                - Date of surgery/operation
                - Date of procedure
                - Date of biopsy
                - Date of autopsy (if deceased)

                Return date in YYYY-MM-DD format.
                """
            },

            'free_text_diagnosis': {
                'sources': ['pathology_report'],
                'prompt': """
                Extract the EXACT pathology diagnosis as written in the report.

                Look for the final diagnosis section or diagnostic line.
                Include the WHO grade if mentioned.

                Return the diagnosis text EXACTLY as written (e.g., "Glioblastoma WHO Grade IV").
                Do not interpret or modify the text.
                """
            },

            'who_cns5_diagnosis': {
                'sources': ['pathology_report'],
                'prompt': self._get_who_cns5_prompt()
            },

            'who_grade': {
                'sources': ['pathology_report'],
                'prompt': """
                Extract the WHO grade of the brain tumor.

                Use ONLY these values:
                - 1 (Grade I, Grade 1)
                - 2 (Grade II, Grade 2)
                - 3 (Grade III, Grade 3)
                - 4 (Grade IV, Grade 4)
                - 1/2 (Grade I/II)
                - 3/4 (Grade III/IV)
                - No grade specified

                Look for: WHO Grade, Grade, Roman numerals (I, II, III, IV)

                Return ONLY the grade value.
                """
            },

            'tumor_location': {
                'sources': ['operative_note', 'imaging_report', 'pathology_report'],
                'prompt': """
                Extract ALL anatomical locations of the brain tumor.

                Use these exact terms (can select multiple):
                - Frontal lobe
                - Temporal lobe
                - Parietal lobe
                - Occipital lobe
                - Thalamus
                - Ventricles
                - Suprasellar/Hypothalamus
                - Cerebellum/Posterior Fossa
                - Brainstem
                - Cervical Spinal Cord
                - Thoracic Spinal Cord
                - Lumbar-Thecal Spinal Cord
                - Optic Pathway
                - Pineal
                - Basal Ganglia
                - Hippocampus
                - Meninges/Dura
                - Skull

                Return ALL applicable locations separated by semicolons.
                Example: "Frontal lobe;Temporal lobe"
                """
            },

            'metastasis': {
                'sources': ['imaging_report', 'oncology_note', 'pathology_report'],
                'prompt': """
                Determine if metastasis is present.

                Look for:
                - Metastatic disease
                - Leptomeningeal spread
                - CSF dissemination
                - Drop metastases
                - Multiple lesions
                - Disseminated disease

                Return ONLY: Yes, No, or Unavailable
                """
            },

            'metastasis_location': {
                'sources': ['imaging_report', 'oncology_note'],
                'prompt': """
                If metastasis is present, identify ALL locations.

                Use these exact terms (can select multiple):
                - CSF
                - Spine
                - Bone Marrow
                - Brain
                - Leptomeningeal
                - Other

                Return locations separated by semicolons.
                Return "Unavailable" if no metastasis or locations unknown.
                """
            },

            'site_of_progression': {
                'sources': ['imaging_report', 'oncology_note'],
                'prompt': """
                For progressive disease, identify the site of progression.

                Use ONLY these terms:
                - Local (at primary site)
                - Metastatic (distant sites)
                - Both
                - Unavailable

                Return ONLY one term.
                """
            },

            'tumor_or_molecular_tests_performed': {
                'sources': ['pathology_report', 'molecular_report', 'lab_results'],
                'prompt': """
                Identify ALL molecular/genetic tests performed on the tumor.

                Look for these test types:
                - FISH/ISH (Fluorescence in situ hybridization)
                - IHC (Immunohistochemistry)
                - WES (Whole exome sequencing)
                - WGS (Whole genome sequencing)
                - RNA-seq
                - Methylation profiling
                - Somatic tumor panel
                - Fusion panel
                - Microarray
                - NGS panel
                - H3 K27M testing
                - IDH1/IDH2 mutation
                - 1p/19q co-deletion
                - MGMT methylation
                - BRAF testing

                Return ALL tests performed separated by semicolons.
                Example: "IHC;FISH;Methylation profiling"
                """
            }
        }

        return configs.get(variable_name)

    def _get_who_cns5_prompt(self) -> str:
        """Generate the WHO CNS5 diagnosis mapping prompt."""
        return """
        Map the pathology diagnosis to the WHO CNS5 classification.

        Major categories:

        HIGH-GRADE GLIOMAS:
        - High-Grade Glioma, Glioblastoma, IDH-wildtype
        - High-Grade Glioma, Astrocytoma, IDH-mutant
        - High-Grade Glioma, Diffuse midline glioma, H3 K27-altered
        - High-Grade Glioma, Diffuse hemispheric glioma, H3 G34-mutant
        - High-Grade Glioma, Diffuse pediatric-type high-grade glioma, H3-wildtype and IDH-wildtype

        LOW-GRADE GLIOMAS:
        - Low-Grade Glioma, Pilocytic astrocytoma
        - Low-Grade Glioma, Diffuse astrocytoma, MYB- or MYBL1-altered
        - Low-Grade Glioma, Diffuse low-grade glioma, MAPK pathway-altered
        - Low-Grade Glioma, Pleomorphic xanthoastrocytoma

        EPENDYMOMAS:
        - Ependymoma, Supratentorial ependymoma, ZFTA fusion-positive
        - Ependymoma, Supratentorial ependymoma, YAP1 fusion-positive
        - Ependymoma, Posterior fossa ependymoma, group PFA
        - Ependymoma, Posterior fossa ependymoma, group PFB

        MEDULLOBLASTOMAS:
        - Medulloblastoma, WNT-activated
        - Medulloblastoma, SHH-activated and TP53-wildtype
        - Medulloblastoma, SHH-activated and TP53-mutant
        - Medulloblastoma, Group 3
        - Medulloblastoma, Group 4

        EMBRYONAL:
        - Atypical teratoid/rhabdoid tumor, ATRT-SHH
        - Atypical teratoid/rhabdoid tumor, ATRT-MYC
        - Other CNS Embryonal tumors, CNS neuroblastoma, FOXR2-activated

        If the diagnosis doesn't clearly match, return:
        - "Other/Not a primary CNS tumor"

        Return ONLY the WHO CNS5 classification term.
        """

    def _retrieve_documents(
        self,
        patient_id: str,
        event_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """
        Retrieve documents from S3 for the specified source type.
        """
        documents = []

        try:
            # Define S3 prefix based on source type
            prefix_map = {
                'pathology_report': f"{patient_id}/pathology/",
                'operative_note': f"{patient_id}/operative_notes/",
                'imaging_report': f"{patient_id}/radiology/",
                'oncology_note': f"{patient_id}/oncology/",
                'discharge_summary': f"{patient_id}/discharge/",
                'molecular_report': f"{patient_id}/molecular/",
                'lab_results': f"{patient_id}/labs/"
            }

            prefix = prefix_map.get(source_type, f"{patient_id}/")

            # List objects in S3
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return documents

            # Filter documents by date proximity
            for obj in response['Contents']:
                # Parse date from object metadata or key
                doc_date = self._extract_date_from_key(obj['Key'])

                if doc_date and abs((doc_date - event_date).days) <= 7:
                    # Retrieve document content
                    doc_response = self.s3_client.get_object(
                        Bucket=self.s3_bucket,
                        Key=obj['Key']
                    )

                    content = doc_response['Body'].read().decode('utf-8')

                    documents.append({
                        'key': obj['Key'],
                        'content': content,
                        'date': doc_date,
                        'source_type': source_type
                    })

        except Exception as e:
            logger.error(f"Error retrieving documents from S3: {e}")

        # Also check structured data tables
        if source_type == 'pathology_report':
            # Add pathology from structured tables
            structured_path = self._get_structured_pathology(patient_id, event_date)
            if structured_path:
                documents.append(structured_path)

        return documents

    def _retrieve_documents_in_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """
        Retrieve documents within a date range for fallback extraction.
        """
        documents = []

        try:
            prefix = f"{patient_id}/"

            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return documents

            for obj in response['Contents']:
                doc_date = self._extract_date_from_key(obj['Key'])

                if doc_date and start_date <= doc_date <= end_date:
                    # Check if this matches our source type
                    if self._matches_source_type(obj['Key'], source_type):
                        doc_response = self.s3_client.get_object(
                            Bucket=self.s3_bucket,
                            Key=obj['Key']
                        )

                        content = doc_response['Body'].read().decode('utf-8')

                        documents.append({
                            'key': obj['Key'],
                            'content': content,
                            'date': doc_date,
                            'source_type': source_type
                        })

        except Exception as e:
            logger.error(f"Error retrieving documents in range: {e}")

        return documents

    def _extract_date_from_key(self, key: str) -> Optional[datetime]:
        """Extract date from S3 object key."""
        # Look for date patterns in the key
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{8}',  # YYYYMMDD
            r'\d{2}/\d{2}/\d{4}'  # MM/DD/YYYY
        ]

        for pattern in date_patterns:
            match = re.search(pattern, key)
            if match:
                date_str = match.group()
                try:
                    # Parse different date formats
                    if '-' in date_str:
                        return datetime.strptime(date_str, '%Y-%m-%d')
                    elif '/' in date_str:
                        return datetime.strptime(date_str, '%m/%d/%Y')
                    elif len(date_str) == 8:
                        return datetime.strptime(date_str, '%Y%m%d')
                except ValueError:
                    continue

        return None

    def _matches_source_type(self, key: str, source_type: str) -> bool:
        """Check if S3 key matches the source type."""
        type_keywords = {
            'pathology_report': ['pathology', 'path', 'histology'],
            'operative_note': ['operative', 'surgery', 'op_note'],
            'imaging_report': ['radiology', 'mri', 'ct', 'imaging'],
            'oncology_note': ['oncology', 'onc', 'clinic'],
            'discharge_summary': ['discharge', 'summary'],
            'molecular_report': ['molecular', 'genetic', 'sequencing'],
            'lab_results': ['lab', 'laboratory', 'results']
        }

        keywords = type_keywords.get(source_type, [])
        key_lower = key.lower()

        return any(keyword in key_lower for keyword in keywords)

    def _get_structured_pathology(
        self,
        patient_id: str,
        event_date: datetime
    ) -> Optional[Dict]:
        """
        Get pathology data from structured Athena tables.
        """
        try:
            # Read from local staging files if available
            staging_path = Path('../athena_extraction_validation/staging_files/pathology.csv')
            if staging_path.exists():
                import pandas as pd
                df = pd.read_csv(staging_path)

                # Filter for patient and date
                patient_data = df[df['patient_id'] == patient_id]

                if not patient_data.empty:
                    # Find closest date
                    for _, row in patient_data.iterrows():
                        if 'collection_date' in row:
                            try:
                                path_date = pd.to_datetime(row['collection_date'])
                                if abs((path_date - event_date).days) <= 7:
                                    return {
                                        'content': row.get('report_text', ''),
                                        'date': path_date,
                                        'source_type': 'pathology_structured'
                                    }
                            except:
                                continue

        except Exception as e:
            logger.warning(f"Could not load structured pathology: {e}")

        return None

    def _llm_extract(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Extract variable value using Ollama LLM.
        """
        if not self.ollama_client:
            # Initialize Ollama if not provided
            try:
                # Simple extraction without Ollama client for now
                # In production, would use: ollama.chat(model='gemma2:27b', ...)
                return self._simple_extraction(variable_name, document, custom_prompt)
            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
                return "Unavailable", ""

        # Use Ollama for extraction
        try:
            prompt = custom_prompt or f"Extract {variable_name} from this document."

            # Truncate document to avoid token limits
            content = document['content'][:2000]

            response = ollama.chat(
                model='gemma2:27b',
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a clinical data extractor. Extract only the requested information.'
                    },
                    {
                        'role': 'user',
                        'content': f"{prompt}\n\nDocument:\n{content}"
                    }
                ],
                options={
                    'temperature': 0.1,
                    'max_tokens': 100
                }
            )

            extracted_value = response['message']['content'].strip()

            # Get evidence snippet
            evidence = self._extract_evidence_snippet(content, extracted_value)

            return extracted_value, evidence

        except Exception as e:
            logger.error(f"Ollama extraction failed: {e}")
            return "Unavailable", ""

    def _simple_extraction(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Simple pattern-based extraction as fallback.
        """
        content = document['content'].lower()

        # Pattern-based extraction for key variables
        if variable_name == 'who_grade':
            grade_patterns = [
                r'who grade[:\s]*(iv|4)',
                r'who grade[:\s]*(iii|3)',
                r'who grade[:\s]*(ii|2)',
                r'who grade[:\s]*(i|1)',
                r'grade[:\s]*(iv|4)',
                r'grade[:\s]*(iii|3)',
                r'grade[:\s]*(ii|2)',
                r'grade[:\s]*(i|1)'
            ]

            for pattern in grade_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    grade = match.group(1)
                    # Convert Roman to Arabic
                    grade_map = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4'}
                    if grade.lower() in grade_map:
                        grade = grade_map[grade.lower()]
                    return grade, match.group(0)

        elif variable_name == 'free_text_diagnosis':
            # Look for diagnosis patterns
            diagnosis_patterns = [
                r'final diagnosis[:\s]*([^\n]+)',
                r'diagnosis[:\s]*([^\n]+)',
                r'pathologic diagnosis[:\s]*([^\n]+)'
            ]

            for pattern in diagnosis_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip(), match.group(0)

        elif variable_name == 'tumor_location':
            locations = []
            for loc_key, keywords in self.TUMOR_LOCATIONS.items():
                if any(kw in content for kw in keywords):
                    # Map to REDCap terminology
                    redcap_map = {
                        'frontal': 'Frontal lobe',
                        'temporal': 'Temporal lobe',
                        'parietal': 'Parietal lobe',
                        'occipital': 'Occipital lobe',
                        'cerebellum': 'Cerebellum/Posterior Fossa',
                        'brainstem': 'Brainstem',
                        'thalamus': 'Thalamus',
                        'ventricles': 'Ventricles',
                        'spine': 'Spine NOS'
                    }
                    if loc_key in redcap_map:
                        locations.append(redcap_map[loc_key])

            if locations:
                return ';'.join(locations), f"Locations found: {locations}"

        return "Unavailable", ""

    def _extract_evidence_snippet(self, content: str, value: str) -> str:
        """Extract evidence snippet around the found value."""
        if not value or value == "Unavailable":
            return ""

        # Find value in content and get surrounding context
        value_lower = value.lower()
        content_lower = content.lower()

        pos = content_lower.find(value_lower)
        if pos != -1:
            # Get 100 characters before and after
            start = max(0, pos - 100)
            end = min(len(content), pos + len(value) + 100)
            return content[start:end]

        return ""

    def _get_fallback_sources(self, variable_name: str) -> List[str]:
        """
        Get fallback document sources for diagnosis variables.
        """
        fallback_map = {
            'who_cns5_diagnosis': ['discharge_summary', 'oncology_note', 'clinic_note'],
            'who_grade': ['discharge_summary', 'oncology_note'],
            'tumor_location': ['discharge_summary', 'clinic_note', 'progress_note'],
            'metastasis': ['oncology_note', 'clinic_note', 'progress_note'],
            'event_type': ['discharge_summary', 'clinic_note', 'history'],
            'molecular_tests': ['lab_results', 'genetic_report', 'clinic_note']
        }

        # Default fallback sources
        default_fallback = ['discharge_summary', 'clinic_note', 'progress_note']

        return fallback_map.get(variable_name, default_fallback)

    def extract_diagnosis_event(
        self,
        patient_id: str,
        event_date: datetime,
        is_surgical_event: bool = True
    ) -> Dict[str, Any]:
        """
        Extract all diagnosis form variables for a clinical event.

        Args:
            patient_id: Patient identifier
            event_date: Date of the clinical event
            is_surgical_event: Whether this is a surgical event (affects defaults)

        Returns:
            Dict of extracted diagnosis variables with confidence scores
        """
        logger.info(f"Extracting diagnosis form for patient {patient_id}, event {event_date}")

        # Initialize context
        context = {}

        # Set default clinical status for surgical events
        if is_surgical_event:
            context['clinical_status_at_event'] = 'Alive'

        # Extract all form variables
        results = self.extract_form_data(
            patient_id=patient_id,
            event_date=event_date,
            event_context=context
        )

        # Apply special validation rules
        results = self._apply_diagnosis_validation(results, is_surgical_event)

        # Add metadata
        results['_metadata'] = {
            'form': 'diagnosis',
            'extraction_date': datetime.now().isoformat(),
            'patient_id': patient_id,
            'event_date': event_date.isoformat(),
            'is_surgical_event': is_surgical_event
        }

        return results

    def _apply_diagnosis_validation(
        self,
        results: Dict[str, Any],
        is_surgical_event: bool
    ) -> Dict[str, Any]:
        """
        Apply diagnosis-specific validation rules.
        """
        # Rule: Clinical status should be "Alive" for surgical events
        if is_surgical_event and 'clinical_status_at_event' in results:
            if results['clinical_status_at_event']['value'] != 'Alive':
                logger.warning(
                    f"Overriding clinical status to 'Alive' for surgical event"
                )
                results['clinical_status_at_event']['value'] = 'Alive'
                results['clinical_status_at_event']['validation_override'] = True

        # Rule: If metastasis = No, clear metastasis_location
        if 'metastasis' in results and results['metastasis']['value'] == 'No':
            if 'metastasis_location' in results:
                results['metastasis_location']['value'] = 'Not applicable'
                results['metastasis_location']['skip_reason'] = 'No metastasis'

        # Rule: site_of_progression only if event_type = Progressive
        if 'event_type' in results:
            if results['event_type']['value'] != 'Progressive':
                if 'site_of_progression' in results:
                    results['site_of_progression']['value'] = 'Not applicable'
                    results['site_of_progression']['skip_reason'] = 'Not progressive event'

        return results