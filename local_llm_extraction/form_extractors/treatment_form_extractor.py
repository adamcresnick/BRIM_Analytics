"""
Treatment Form Extractor for CBTN REDCap
Extracts treatment variables with CRITICAL post-operative imaging validation.
Includes surgery, radiation, and chemotherapy details.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import re
import pandas as pd

from .base_form_extractor import BaseFormExtractor

logger = logging.getLogger(__name__)


class TreatmentFormExtractor(BaseFormExtractor):
    """
    Extractor for the CBTN Treatment form.

    CRITICAL: Implements mandatory post-operative imaging validation
    for extent of resection based on pilot findings.
    """

    # Chemotherapy protocol mapping (abbreviated list)
    PROTOCOL_KEYWORDS = {
        'ACNS0332': ['acns0332', 'high risk medulloblastoma'],
        'ACNS0831': ['acns0831', 'average risk medulloblastoma'],
        'ACNS1123': ['acns1123', 'high grade glioma', 'phase 2'],
        'SJMB03': ['sjmb03', 'st jude medulloblastoma'],
        'SJMB12': ['sjmb12', 'st jude', 'molecularly defined'],
        'HIT-SKK': ['hit-skk', 'infant medulloblastoma'],
        'COG-ACNS1221': ['acns1221', 'diffuse intrinsic pontine'],
        'PNOC003': ['pnoc003', 'dmg', 'h3.3k27m'],
        'PBTC-029': ['pbtc-029', 'pediatric brain tumor'],
        'DFCI': ['dfci', 'dana farber'],
        'CCG': ['ccg', 'children\'s cancer group'],
        'POG': ['pog', 'pediatric oncology group']
    }

    # Radiation site mapping
    RADIATION_SITES = {
        'focal': ['focal', 'tumor bed', 'local', 'boost only'],
        'csi': ['craniospinal', 'csi', 'whole neuraxis'],
        'wv': ['whole ventricular', 'ventricular', 'wv'],
        'whole_brain': ['whole brain', 'wbrt', 'cranial']
    }

    def __init__(self, data_dictionary_path: str, s3_client=None, ollama_client=None):
        """Initialize the Treatment form extractor."""
        super().__init__(data_dictionary_path)
        self.s3_client = s3_client
        self.ollama_client = ollama_client

    def get_form_name(self) -> str:
        """Return the REDCap form name."""
        return 'treatment'

    def get_variable_extraction_config(self, variable_name: str) -> Optional[Dict]:
        """Get extraction configuration for treatment variables."""

        configs = {
            'treatment_updated': {
                'sources': ['oncology_note', 'clinic_note', 'treatment_summary'],
                'prompt': """
                Determine the treatment status at this visit.

                Use ONLY these terms:
                - New (starting new treatment)
                - Ongoing (continuing current treatment)
                - Modified (treatment changed)
                - No treatment (observation only)
                - Unavailable

                Look for: new regimen, continuing, modified protocol, observation

                Return ONLY the status term.
                """
            },

            'surgery': {
                'sources': ['operative_note', 'discharge_summary'],
                'prompt': """
                Was surgery performed? Return ONLY: Yes or No
                """
            },

            'surgery_type': {
                'sources': ['operative_note', 'discharge_summary'],
                'prompt': """
                Extract the type of neurosurgical procedure performed.

                Use ONLY these terms:
                - Craniotomy
                - Spinal laminectomy
                - Endoscopic endonasal
                - Stereotactic guided biopsy
                - LITT
                - Other

                Look for surgical approach and technique descriptions.

                Return ONLY the surgery type term.
                """
            },

            'extent_of_tumor_resection': {
                'sources': ['operative_note', 'post_op_imaging', 'discharge_summary'],
                'prompt': """
                Extract the extent of tumor resection achieved.

                Use ONLY these exact terms:
                - Gross/Near total (>95% removal, GTR, NTR)
                - Partial (50-95% removal, STR, subtotal)
                - Biopsy only (tissue sampling only)
                - Unavailable
                - N/A

                Look for:
                - Percentage of tumor removed
                - GTR, STR, NTR abbreviations
                - "gross total", "near total", "subtotal", "partial"
                - "debulking" vs "biopsy"
                - Post-operative imaging assessment

                CRITICAL: Post-operative MRI assessment takes precedence over operative note.

                Return ONLY the extent category term.
                """,
                'requires_validation': True  # Flag for post-op imaging validation
            },

            'specimen_to_cbtn': {
                'sources': ['operative_note', 'pathology_report'],
                'prompt': """
                Was tumor specimen sent to CBTN biobank?

                Look for: CBTN, biobank, specimen routing, tissue banking

                Return: Yes, No, or Unavailable
                """
            },

            'specimen_collection_origin': {
                'sources': ['operative_note', 'pathology_report'],
                'prompt': """
                Determine the clinical context of this specimen collection.

                Use ONLY these terms:
                - Initial CNS Tumor Surgery
                - Repeat resection
                - Second look surgery
                - Recurrence surgery
                - Progressive surgery
                - Second malignancy
                - Autopsy
                - Unavailable

                Return ONLY the origin term.
                """
            },

            'radiation': {
                'sources': ['radiation_oncology', 'treatment_plan', 'oncology_note'],
                'prompt': """
                Was radiation therapy given? Return ONLY: Yes or No
                """
            },

            'radiation_start_date': {
                'sources': ['radiation_oncology', 'treatment_plan'],
                'prompt': """
                Extract the radiation therapy start date.
                Return in YYYY-MM-DD format or "Unavailable".
                """
            },

            'radiation_site': {
                'sources': ['radiation_oncology', 'treatment_plan'],
                'prompt': """
                Extract the radiation treatment site/field.

                Use ONLY these terms:
                - Focal/Tumor bed
                - Craniospinal with focal boost
                - Whole Ventricular with focal boost
                - Other
                - Unavailable

                Look for: CSI, craniospinal, focal, boost, whole ventricular

                Return ONLY the site term.
                """
            },

            'radiation_dose_csi_gy': {
                'sources': ['radiation_oncology', 'treatment_plan'],
                'prompt': """
                Extract the craniospinal (CSI) radiation dose in Gy.
                Return numeric value only or "Unavailable".
                """
            },

            'radiation_dose_boost_gy': {
                'sources': ['radiation_oncology', 'treatment_plan'],
                'prompt': """
                Extract the focal boost radiation dose in Gy.
                Return numeric value only or "Unavailable".
                """
            },

            'radiation_type': {
                'sources': ['radiation_oncology', 'treatment_plan'],
                'prompt': """
                Extract the type of radiation delivered.

                Use ONLY these terms:
                - Protons
                - Photons
                - Combination
                - Gamma Knife
                - Other

                Return ONLY the radiation type.
                """
            },

            'chemotherapy': {
                'sources': ['oncology_note', 'chemotherapy_orders', 'treatment_plan'],
                'prompt': """
                Was chemotherapy given? Return ONLY: Yes or No
                """
            },

            'chemotherapy_type': {
                'sources': ['oncology_note', 'treatment_plan'],
                'prompt': """
                Determine the chemotherapy approach.

                Use ONLY these terms:
                - Protocol follows but not enrolled
                - Protocol follows and enrolled
                - Other SOC (non-protocol)
                - Unavailable

                Look for: protocol enrollment, clinical trial, standard of care

                Return ONLY the chemotherapy type.
                """
            },

            'protocol_name': {
                'sources': ['oncology_note', 'treatment_plan', 'consent_form'],
                'prompt': """
                Extract the specific protocol or clinical trial name.

                Look for protocol numbers like:
                - ACNS#### (COG protocols)
                - SJMB## (St Jude protocols)
                - PNOC### (PNOC protocols)
                - PBTC-### (PBTC protocols)
                - Other institutional protocols

                Return the full protocol name/number or "Unavailable".
                """
            },

            'chemotherapy_agent_1': {
                'sources': ['medication_admin', 'chemotherapy_orders', 'oncology_note'],
                'prompt': """
                Extract the first chemotherapy agent used.

                Common pediatric brain tumor agents:
                - Vincristine
                - Carboplatin
                - Cisplatin
                - Cyclophosphamide
                - Lomustine (CCNU)
                - Temozolomide
                - Etoposide
                - Methotrexate
                - Bevacizumab

                Return the drug name or "Unavailable".
                """
            }
        }

        return configs.get(variable_name)

    def extract_surgical_treatment(
        self,
        patient_id: str,
        surgery_date: datetime
    ) -> Dict[str, Any]:
        """
        Extract surgical treatment variables with CRITICAL extent validation.

        THIS IS THE MOST IMPORTANT METHOD IN THE ENTIRE SYSTEM.
        Post-operative imaging validation prevents critical errors.
        """
        logger.info(f"Extracting surgical treatment for {patient_id} on {surgery_date}")

        results = {}

        # Extract operative note assessment
        operative_config = self.get_variable_extraction_config('extent_of_tumor_resection')
        operative_result = self.extract_with_multi_source_validation(
            patient_id=patient_id,
            event_date=surgery_date,
            variable_name='extent_of_tumor_resection',
            sources=['operative_note', 'discharge_summary'],
            custom_prompt=operative_config['prompt']
        )

        # CRITICAL: Post-operative imaging validation
        postop_extent = self._validate_extent_with_postop_imaging(
            patient_id, surgery_date
        )

        if postop_extent and postop_extent != operative_result['value']:
            logger.warning(
                f"CRITICAL DISCREPANCY DETECTED: "
                f"Operative note: {operative_result['value']}, "
                f"Post-op imaging: {postop_extent}"
            )

            # Override with post-op imaging (gold standard)
            results['extent_of_tumor_resection'] = {
                'value': postop_extent,
                'confidence': 0.95,  # High confidence for imaging
                'sources': ['post_op_imaging', 'operative_note'],
                'validation': 'post_op_imaging_override',
                'operative_assessment': operative_result['value'],
                'imaging_assessment': postop_extent,
                'discrepancy_detected': True,
                'override_reason': 'Post-operative MRI is gold standard for extent assessment'
            }
        else:
            results['extent_of_tumor_resection'] = operative_result
            results['extent_of_tumor_resection']['validation'] = 'confirmed' if postop_extent else 'no_imaging'

        # Extract other surgical variables
        for var_name in ['surgery_type', 'specimen_to_cbtn', 'specimen_collection_origin']:
            config = self.get_variable_extraction_config(var_name)
            if config:
                results[var_name] = self.extract_with_multi_source_validation(
                    patient_id=patient_id,
                    event_date=surgery_date,
                    variable_name=var_name,
                    sources=config['sources'],
                    custom_prompt=config['prompt']
                )

        return results

    def _validate_extent_with_postop_imaging(
        self,
        patient_id: str,
        surgery_date: datetime
    ) -> Optional[str]:
        """
        CRITICAL METHOD: Validate extent of resection with post-operative imaging.

        This method addresses the key finding from our pilot:
        Operative notes can fundamentally misclassify surgical extent.
        Post-op MRI within 48-72 hours is the gold standard.
        """
        logger.info("Performing CRITICAL post-op imaging validation for extent of resection")

        # Look for post-op MRI within 72 hours
        postop_window = timedelta(days=3)

        try:
            # First check structured imaging table
            imaging_extent = self._extract_from_imaging_table(
                patient_id, surgery_date, postop_window
            )

            if imaging_extent:
                logger.info(f"Found extent in structured imaging: {imaging_extent}")
                return imaging_extent

            # Check radiology reports in S3
            imaging_docs = self._retrieve_postop_imaging_reports(
                patient_id, surgery_date, postop_window
            )

            for doc in imaging_docs:
                extent = self._extract_extent_from_imaging(doc)
                if extent and extent != "Unavailable":
                    logger.info(f"Extracted extent from post-op imaging: {extent}")
                    return extent

        except Exception as e:
            logger.error(f"Error in post-op imaging validation: {e}")

        logger.warning("No post-operative imaging found for validation")
        return None

    def _extract_from_imaging_table(
        self,
        patient_id: str,
        surgery_date: datetime,
        window: timedelta
    ) -> Optional[str]:
        """Extract extent from structured imaging table."""
        try:
            # Check local staging files
            imaging_path = Path('../athena_extraction_validation/staging_files/imaging.csv')
            if imaging_path.exists():
                df = pd.read_csv(imaging_path)

                # Filter for patient
                patient_imaging = df[df['patient_id'] == patient_id]

                for _, row in patient_imaging.iterrows():
                    if 'imaging_date' in row:
                        img_date = pd.to_datetime(row['imaging_date'])

                        # Check if within post-op window
                        if 0 <= (img_date - surgery_date).days <= window.days:
                            # Look for extent in narrative
                            narrative = str(row.get('narrative', '')).lower()

                            if 'gross total' in narrative or 'gtr' in narrative:
                                return 'Gross/Near total'
                            elif 'near total' in narrative or 'ntr' in narrative:
                                return 'Gross/Near total'
                            elif 'subtotal' in narrative or 'str' in narrative:
                                return 'Partial'
                            elif 'partial' in narrative:
                                return 'Partial'
                            elif 'biopsy' in narrative:
                                return 'Biopsy only'

        except Exception as e:
            logger.warning(f"Could not check imaging table: {e}")

        return None

    def _retrieve_postop_imaging_reports(
        self,
        patient_id: str,
        surgery_date: datetime,
        window: timedelta
    ) -> List[Dict]:
        """Retrieve post-operative imaging reports."""
        reports = []

        try:
            # S3 prefix for radiology
            prefix = f"{patient_id}/radiology/"

            if self.s3_client:
                response = self.s3_client.list_objects_v2(
                    Bucket='cnb-redcap-curation',
                    Prefix=prefix
                )

                if 'Contents' in response:
                    for obj in response['Contents']:
                        # Check if MRI and within window
                        key_lower = obj['Key'].lower()
                        if 'mri' in key_lower or 'mr_' in key_lower:
                            # Extract date from key
                            doc_date = self._extract_date_from_key(obj['Key'])

                            if doc_date:
                                days_post = (doc_date - surgery_date).days
                                if 0 <= days_post <= window.days:
                                    # Retrieve report
                                    doc_response = self.s3_client.get_object(
                                        Bucket='cnb-redcap-curation',
                                        Key=obj['Key']
                                    )

                                    content = doc_response['Body'].read().decode('utf-8')
                                    reports.append({
                                        'content': content,
                                        'date': doc_date,
                                        'days_post_op': days_post,
                                        'type': 'post_op_mri'
                                    })

        except Exception as e:
            logger.error(f"Error retrieving post-op imaging: {e}")

        return reports

    def _extract_extent_from_imaging(self, imaging_doc: Dict) -> Optional[str]:
        """
        Extract extent of resection from post-operative imaging report.

        This is the GOLD STANDARD for extent assessment.
        """
        content = imaging_doc['content'].lower()

        # Look for explicit extent descriptions
        extent_patterns = [
            (r'gross total resection|gtr|complete resection|no residual', 'Gross/Near total'),
            (r'near[\s-]?total|ntr|>95%|greater than 95', 'Gross/Near total'),
            (r'subtotal|str|partial resection|50-95%', 'Partial'),
            (r'partial|<50%|less than 50|debulking', 'Partial'),
            (r'biopsy only|tissue sampling|diagnostic biopsy', 'Biopsy only'),
            (r'significant residual|substantial residual', 'Partial'),
            (r'minimal residual|small residual', 'Gross/Near total')
        ]

        for pattern, extent in extent_patterns:
            if re.search(pattern, content):
                return extent

        # Look for residual tumor descriptions
        if 'no residual' in content or 'no evidence of residual' in content:
            return 'Gross/Near total'
        elif 'residual tumor' in content or 'residual enhancement' in content:
            # Try to quantify
            if 'small' in content or 'minimal' in content:
                return 'Gross/Near total'
            else:
                return 'Partial'

        return None

    def _extract_date_from_key(self, key: str) -> Optional[datetime]:
        """Extract date from S3 object key."""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{8}',
            r'\d{2}/\d{2}/\d{4}'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, key)
            if match:
                date_str = match.group()
                try:
                    if '-' in date_str:
                        return datetime.strptime(date_str, '%Y-%m-%d')
                    elif '/' in date_str:
                        return datetime.strptime(date_str, '%m/%d/%Y')
                    elif len(date_str) == 8:
                        return datetime.strptime(date_str, '%Y%m%d')
                except ValueError:
                    continue

        return None

    def extract_radiation_treatment(
        self,
        patient_id: str,
        treatment_date: datetime
    ) -> Dict[str, Any]:
        """Extract radiation treatment variables."""
        results = {}

        radiation_vars = [
            'radiation', 'radiation_start_date', 'radiation_site',
            'radiation_dose_csi_gy', 'radiation_dose_boost_gy',
            'radiation_type'
        ]

        for var_name in radiation_vars:
            config = self.get_variable_extraction_config(var_name)
            if config:
                results[var_name] = self.extract_with_multi_source_validation(
                    patient_id=patient_id,
                    event_date=treatment_date,
                    variable_name=var_name,
                    sources=config['sources'],
                    custom_prompt=config['prompt']
                )

        return results

    def extract_chemotherapy_treatment(
        self,
        patient_id: str,
        treatment_date: datetime
    ) -> Dict[str, Any]:
        """Extract chemotherapy treatment variables."""
        results = {}

        # Check if chemotherapy was given
        chemo_config = self.get_variable_extraction_config('chemotherapy')
        chemo_result = self.extract_with_multi_source_validation(
            patient_id=patient_id,
            event_date=treatment_date,
            variable_name='chemotherapy',
            sources=chemo_config['sources'],
            custom_prompt=chemo_config['prompt']
        )

        results['chemotherapy'] = chemo_result

        if chemo_result['value'] == 'Yes':
            # Extract chemotherapy details
            chemo_vars = [
                'chemotherapy_type', 'protocol_name',
                'chemotherapy_agent_1', 'chemotherapy_agent_2',
                'chemotherapy_agent_3', 'chemotherapy_agent_4',
                'chemotherapy_agent_5'
            ]

            for var_name in chemo_vars:
                config = self.get_variable_extraction_config(var_name)
                if config:
                    results[var_name] = self.extract_with_multi_source_validation(
                        patient_id=patient_id,
                        event_date=treatment_date,
                        variable_name=var_name,
                        sources=config.get('sources', []),
                        custom_prompt=config.get('prompt')
                    )

            # Map protocol name to controlled vocabulary
            if 'protocol_name' in results:
                results['protocol_name']['value'] = self._map_protocol_name(
                    results['protocol_name']['value']
                )

        return results

    def _map_protocol_name(self, extracted_protocol: str) -> str:
        """Map extracted protocol text to controlled vocabulary."""
        extracted_lower = extracted_protocol.lower()

        # Check against known protocols
        for protocol, keywords in self.PROTOCOL_KEYWORDS.items():
            if any(keyword in extracted_lower for keyword in keywords):
                return protocol

        # Return as-is if no match
        return extracted_protocol

    def _retrieve_documents(
        self,
        patient_id: str,
        event_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve documents from various sources."""
        # Implementation would retrieve from S3 and structured tables
        # Simplified for now
        return []

    def _retrieve_documents_in_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve documents within date range."""
        # Implementation would retrieve from S3 and structured tables
        return []

    def _llm_extract(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Extract using LLM."""
        # Implementation would use Ollama
        # For now, return placeholder
        return "Unavailable", ""

    def _get_fallback_sources(self, variable_name: str) -> List[str]:
        """Get fallback sources for treatment variables."""
        fallback_map = {
            'extent_of_tumor_resection': ['discharge_summary', 'clinic_note', 'pathology_report'],
            'protocol_name': ['consent_form', 'clinic_note', 'discharge_summary'],
            'chemotherapy_agent': ['pharmacy_records', 'nursing_notes', 'discharge_summary']
        }

        return fallback_map.get(variable_name, ['discharge_summary', 'clinic_note'])