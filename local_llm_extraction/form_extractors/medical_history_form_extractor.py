"""
Medical History Form Extractor for CBTN REDCap
Extracts medical history variables including:
- Cancer predisposition conditions
- Germline testing
- Family history of cancer (complex branching logic)
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import re
import pandas as pd

from .base_form_extractor import BaseFormExtractor

logger = logging.getLogger(__name__)


class MedicalHistoryFormExtractor(BaseFormExtractor):
    """
    Extractor for the CBTN Medical History form.
    Handles cancer predisposition, germline testing, and complex family history.
    """

    # Cancer predisposition syndrome mapping
    PREDISPOSITION_MAPPING = {
        'nf1': ('1', 'Neurofibromatosis, Type 1 (NF-1)'),
        'neurofibromatosis type 1': ('1', 'Neurofibromatosis, Type 1 (NF-1)'),
        'von recklinghausen': ('1', 'Neurofibromatosis, Type 1 (NF-1)'),
        'nf2': ('2', 'Neurofibromatosis, Type 2 (NF-2)'),
        'neurofibromatosis type 2': ('2', 'Neurofibromatosis, Type 2 (NF-2)'),
        'schwannomatosis': ('3', 'Schwannomatosis (LZTR1)'),
        'lztr1': ('3', 'Schwannomatosis (LZTR1)'),
        'tuberous sclerosis': ('4', 'Tuberous Sclerosis (TSC1, TSC2)'),
        'tsc': ('4', 'Tuberous Sclerosis (TSC1, TSC2)'),
        'tsc1': ('4', 'Tuberous Sclerosis (TSC1, TSC2)'),
        'tsc2': ('4', 'Tuberous Sclerosis (TSC1, TSC2)'),
        'li-fraumeni': ('5', 'Li-Fraumeni syndrome (TP53)'),
        'li fraumeni': ('5', 'Li-Fraumeni syndrome (TP53)'),
        'tp53': ('5', 'Li-Fraumeni syndrome (TP53)'),
        'lfs': ('5', 'Li-Fraumeni syndrome (TP53)'),
        'gorlin': ('8', 'Gorlin Syndrome (PTCH1, SUFU)'),
        'gorlin syndrome': ('8', 'Gorlin Syndrome (PTCH1, SUFU)'),
        'ptch1': ('8', 'Gorlin Syndrome (PTCH1, SUFU)'),
        'sufu': ('8', 'Gorlin Syndrome (PTCH1, SUFU)'),
        'nevoid basal cell': ('8', 'Gorlin Syndrome (PTCH1, SUFU)'),
        'cmmrd': ('10', 'Constitutional Mismatch Repair Deficiency Syndrome'),
        'constitutional mismatch': ('10', 'Constitutional Mismatch Repair Deficiency Syndrome'),
        'lynch': ('11', 'Lynch Syndrome'),
        'lynch syndrome': ('11', 'Lynch Syndrome'),
        'hnpcc': ('11', 'Lynch Syndrome'),
        'retinoblastoma': ('12', 'Retinoblastoma (RB1)'),
        'rb1': ('12', 'Retinoblastoma (RB1)'),
        'fap': ('13', 'Familial adenomatous polyposis (APC)'),
        'familial adenomatous': ('13', 'Familial adenomatous polyposis (APC)'),
        'apc': ('13', 'Familial adenomatous polyposis (APC)'),
        'rhabdoid tumor predisposition': ('14', 'Rhabdoid tumor predisposition syndrome'),
        'smarcb1': ('14', 'Rhabdoid tumor predisposition syndrome'),
        'smarca4': ('14', 'Rhabdoid tumor predisposition syndrome'),
        'vhl': ('15', 'Von Hippel-Lindau (VHL)'),
        'von hippel': ('15', 'Von Hippel-Lindau (VHL)'),
        'von hippel-lindau': ('15', 'Von Hippel-Lindau (VHL)'),
        'brca1': ('16', 'BRCA1/2'),
        'brca2': ('16', 'BRCA1/2'),
        'brca': ('16', 'BRCA1/2'),
        'chek2': ('17', 'CHEK2')
    }

    # Family member mapping
    FAMILY_MEMBERS = {
        'mother': '1',
        'mom': '1',
        'maternal': '1',
        'father': '2',
        'dad': '2',
        'paternal': '2',
        'sister': '3',
        'brother': '4',
        'maternal grandmother': '5',
        'maternal grandfather': '6',
        'paternal grandmother': '7',
        'paternal grandfather': '8',
        'cousin': '12'
    }

    # Cancer type mapping for family history
    CANCER_TYPE_MAPPING = {
        'cns': '1',
        'brain': '1',
        'brain tumor': '1',
        'glioma': '1',
        'lung': '2',
        'lung cancer': '2',
        'skin': '3',
        'melanoma': '3',
        'basal cell': '3',
        'bone': '4',
        'osteosarcoma': '4',
        'breast': '5',
        'breast cancer': '5',
        'colon': '6',
        'colorectal': '6',
        'liver': '7',
        'hepatocellular': '7',
        'lymphoma': '8',
        'hodgkin': '8',
        'non-hodgkin': '8',
        'ovarian': '9',
        'ovarian cancer': '9',
        'prostate': '10',
        'prostate cancer': '10',
        'uterine': '11',
        'endometrial': '11',
        'pancreas': '12',
        'pancreatic': '12',
        'bladder': '13',
        'bladder cancer': '13',
        'thyroid': '14',
        'thyroid cancer': '14',
        'kidney': '15',
        'renal': '15',
        'renal cell': '15'
    }

    def __init__(self, data_dictionary_path: str, s3_client=None, ollama_client=None):
        """Initialize the Medical History form extractor."""
        super().__init__(data_dictionary_path)
        self.s3_client = s3_client
        self.ollama_client = ollama_client

    def get_form_name(self) -> str:
        """Return the REDCap form name."""
        return 'medical_history'

    def get_variable_extraction_config(self, variable_name: str) -> Optional[Dict]:
        """Get extraction configuration for medical history variables."""

        configs = {
            'cancer_predisposition': {
                'sources': ['genetics_note', 'oncology_note', 'problem_list', 'clinic_note'],
                'prompt': """
                Extract any cancer predisposition syndromes or conditions.

                Look for these specific conditions:
                - Neurofibromatosis Type 1 (NF1)
                - Neurofibromatosis Type 2 (NF2)
                - Schwannomatosis
                - Tuberous Sclerosis (TSC1/TSC2)
                - Li-Fraumeni syndrome (TP53)
                - Gorlin Syndrome (PTCH1, SUFU)
                - Constitutional Mismatch Repair Deficiency (CMMRD)
                - Lynch Syndrome
                - Retinoblastoma (RB1)
                - Familial adenomatous polyposis (FAP/APC)
                - Rhabdoid tumor predisposition (SMARCB1/SMARCA4)
                - Von Hippel-Lindau (VHL)
                - BRCA1/BRCA2
                - CHEK2

                Also look for: genetic syndrome, hereditary cancer, germline mutation

                Return ALL conditions found separated by semicolons.
                If none found, return "None documented"
                """,
                'type': 'checkbox'  # Multi-select field
            },

            'germline': {
                'sources': ['genetics_note', 'lab_results', 'genetic_report'],
                'prompt': """
                Was germline genetic testing performed to confirm a cancer predisposition syndrome?

                Look for:
                - Germline testing
                - Constitutional genetic testing
                - Hereditary cancer panel
                - Blood/saliva genetic test (not tumor)
                - Genetic counseling results

                Return ONLY: Yes or No
                """,
                'branching': 'cancer_predisposition != None documented'  # Only if predisposition found
            },

            'results_available': {
                'sources': ['genetics_note', 'lab_results', 'genetic_report'],
                'prompt': """
                Are germline genetic testing results available in the record?

                Look for:
                - Genetic test results
                - Variant identified
                - Pathogenic mutation
                - VUS (variant of uncertain significance)
                - Negative/positive result

                Return ONLY: Yes or No
                """,
                'branching': 'germline = Yes'  # Only if germline testing performed
            },

            'family_history': {
                'sources': ['family_history', 'social_history', 'oncology_note', 'genetics_note'],
                'prompt': """
                Is there a documented family history of cancer?

                Look for any mention of cancer in family members:
                - Parents (mother, father)
                - Siblings (brother, sister)
                - Grandparents
                - Other relatives

                Return: Yes, No, or Unavailable
                """
            },

            'family_member': {
                'sources': ['family_history', 'social_history', 'oncology_note'],
                'prompt': """
                Identify ALL family members with cancer history.

                Look for:
                - Mother/maternal
                - Father/paternal
                - Sister(s) - note if multiple
                - Brother(s) - note if multiple
                - Maternal/Paternal Grandmother
                - Maternal/Paternal Grandfather
                - Cousins
                - Aunts/Uncles

                Return ALL affected family members separated by semicolons.
                Example: "Mother;Father;Sister"
                """,
                'type': 'checkbox',
                'branching': 'family_history = Yes'
            }
        }

        # Add dynamic family member cancer type configs
        for member in ['mother', 'father', 'sister', 'brother']:
            configs[f'{member}_what_type_of_cancer'] = {
                'sources': ['family_history', 'social_history', 'oncology_note'],
                'prompt': f"""
                What type(s) of cancer did the patient's {member} have?

                Common cancer types:
                - CNS/Brain tumor
                - Lung cancer
                - Skin cancer/Melanoma
                - Bone cancer
                - Breast cancer
                - Colon/Colorectal cancer
                - Liver cancer
                - Lymphoma
                - Ovarian cancer
                - Prostate cancer
                - Uterine/Endometrial cancer
                - Pancreatic cancer
                - Bladder cancer
                - Thyroid cancer
                - Kidney/Renal cancer

                Return ALL cancer types for {member} separated by semicolons.
                Return "Unavailable/Not Specified" if type unknown.
                """,
                'type': 'checkbox',
                'branching': f'family_member contains {member}'
            }

        return configs.get(variable_name)

    def extract_medical_history(
        self,
        patient_id: str,
        extraction_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract all medical history variables for a patient.

        Args:
            patient_id: Patient identifier
            extraction_date: Optional date for document retrieval

        Returns:
            Dict of extracted medical history variables
        """
        logger.info(f"Extracting medical history for patient {patient_id}")

        results = {}
        context = {}

        # Extract cancer predisposition
        predisposition_config = self.get_variable_extraction_config('cancer_predisposition')
        predisposition_result = self.extract_with_multi_source_validation(
            patient_id=patient_id,
            event_date=extraction_date or datetime.now(),
            variable_name='cancer_predisposition',
            sources=predisposition_config['sources'],
            custom_prompt=predisposition_config['prompt']
        )

        # Map to REDCap codes
        predisposition_result['value'] = self._map_predisposition_to_codes(
            predisposition_result['value']
        )
        results['cancer_predisposition'] = predisposition_result
        context['cancer_predisposition'] = predisposition_result['value']

        # Extract germline testing if predisposition found
        if predisposition_result['value'] != '7':  # Not "None documented"
            germline_config = self.get_variable_extraction_config('germline')
            germline_result = self.extract_with_multi_source_validation(
                patient_id=patient_id,
                event_date=extraction_date or datetime.now(),
                variable_name='germline',
                sources=germline_config['sources'],
                custom_prompt=germline_config['prompt']
            )
            results['germline'] = germline_result
            context['germline'] = germline_result['value']

            # Extract results availability if germline performed
            if germline_result['value'] == 'Yes':
                results_config = self.get_variable_extraction_config('results_available')
                results_available = self.extract_with_multi_source_validation(
                    patient_id=patient_id,
                    event_date=extraction_date or datetime.now(),
                    variable_name='results_available',
                    sources=results_config['sources'],
                    custom_prompt=results_config['prompt']
                )
                results['results_available'] = results_available

        # Extract family history
        family_history_result = self._extract_family_history(
            patient_id, extraction_date or datetime.now()
        )
        results.update(family_history_result)

        return results

    def _extract_family_history(
        self,
        patient_id: str,
        extraction_date: datetime
    ) -> Dict[str, Any]:
        """
        Extract complex family history with branching logic.
        """
        results = {}

        # Check if family history exists
        fh_config = self.get_variable_extraction_config('family_history')
        fh_result = self.extract_with_multi_source_validation(
            patient_id=patient_id,
            event_date=extraction_date,
            variable_name='family_history',
            sources=fh_config['sources'],
            custom_prompt=fh_config['prompt']
        )

        # Map to REDCap codes (0=Yes, 1=No, 2=Unavailable)
        fh_value = fh_result['value']
        if fh_value == 'Yes':
            fh_result['value'] = '0'
        elif fh_value == 'No':
            fh_result['value'] = '1'
        else:
            fh_result['value'] = '2'

        results['family_history'] = fh_result

        # If family history present, extract details
        if fh_value == 'Yes':
            # Extract affected family members
            fm_config = self.get_variable_extraction_config('family_member')
            fm_result = self.extract_with_multi_source_validation(
                patient_id=patient_id,
                event_date=extraction_date,
                variable_name='family_member',
                sources=fm_config['sources'],
                custom_prompt=fm_config['prompt']
            )

            # Map to REDCap codes
            fm_result['value'] = self._map_family_members_to_codes(fm_result['value'])
            results['family_member'] = fm_result

            # Extract cancer types for each affected member
            affected_members = fm_result['value'].split('|') if fm_result['value'] else []

            for member_code in affected_members:
                member_name = self._get_member_name_from_code(member_code)
                if member_name and member_name in ['mother', 'father', 'sister', 'brother']:
                    # Extract cancer type for this member
                    cancer_config = self.get_variable_extraction_config(
                        f'{member_name}_what_type_of_cancer'
                    )
                    if cancer_config:
                        cancer_result = self.extract_with_multi_source_validation(
                            patient_id=patient_id,
                            event_date=extraction_date,
                            variable_name=f'{member_name}_what_type_of_cancer',
                            sources=cancer_config['sources'],
                            custom_prompt=cancer_config['prompt']
                        )

                        # Map to REDCap codes
                        cancer_result['value'] = self._map_cancer_types_to_codes(
                            cancer_result['value']
                        )
                        results[f'{member_name}_what_type_of_cancer'] = cancer_result

        return results

    def _map_predisposition_to_codes(self, extracted_text: str) -> str:
        """Map predisposition conditions to REDCap codes."""
        if not extracted_text or 'none' in extracted_text.lower():
            return '7'  # None documented

        extracted_lower = extracted_text.lower()
        mapped_codes = []

        # Check each condition
        for keyword, (code, _) in self.PREDISPOSITION_MAPPING.items():
            if keyword in extracted_lower:
                if code not in mapped_codes:
                    mapped_codes.append(code)

        if mapped_codes:
            return '|'.join(mapped_codes)  # Checkbox field
        else:
            return '6'  # Other inherited conditions NOS

    def _map_family_members_to_codes(self, extracted_text: str) -> str:
        """Map family members to REDCap codes."""
        if not extracted_text:
            return '11'  # Unavailable

        extracted_lower = extracted_text.lower()
        mapped_codes = []

        # Split members
        members = re.split(r'[;,/]|\s+and\s+', extracted_lower)

        for member in members:
            member = member.strip()

            # Check for multiple siblings
            if 'sister' in member:
                if 'second' in member or '2' in member:
                    mapped_codes.append('13')  # Sister (Second)
                elif 'third' in member or '3' in member:
                    mapped_codes.append('14')  # Sister (Third)
                else:
                    mapped_codes.append('3')  # Sister

            elif 'brother' in member:
                if 'second' in member or '2' in member:
                    mapped_codes.append('15')  # Brother (Second)
                elif 'third' in member or '3' in member:
                    mapped_codes.append('16')  # Brother (Third)
                else:
                    mapped_codes.append('4')  # Brother

            else:
                # Check other family members
                for keyword, code in self.FAMILY_MEMBERS.items():
                    if keyword in member:
                        if code not in mapped_codes:
                            mapped_codes.append(code)
                        break

        if mapped_codes:
            return '|'.join(mapped_codes)
        else:
            return '11'  # Unavailable

    def _map_cancer_types_to_codes(self, extracted_text: str) -> str:
        """Map cancer types to REDCap codes."""
        if not extracted_text or 'unavailable' in extracted_text.lower():
            return '16'  # Unavailable/Not Specified

        extracted_lower = extracted_text.lower()
        mapped_codes = []

        # Split cancer types
        cancers = re.split(r'[;,/]|\s+and\s+', extracted_lower)

        for cancer in cancers:
            cancer = cancer.strip()

            for keyword, code in self.CANCER_TYPE_MAPPING.items():
                if keyword in cancer:
                    if code not in mapped_codes:
                        mapped_codes.append(code)
                    break

        if not mapped_codes and 'other' in extracted_lower:
            mapped_codes.append('17')  # Other

        if mapped_codes:
            return '|'.join(mapped_codes)
        else:
            return '16'  # Unavailable/Not Specified

    def _get_member_name_from_code(self, code: str) -> Optional[str]:
        """Get member name from REDCap code."""
        member_map = {
            '1': 'mother',
            '2': 'father',
            '3': 'sister',
            '4': 'brother',
            '13': 'sister',  # Sister (Second)
            '14': 'sister',  # Sister (Third)
            '15': 'brother',  # Brother (Second)
            '16': 'brother'  # Brother (Third)
        }
        return member_map.get(code)

    def _retrieve_documents(
        self,
        patient_id: str,
        event_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve medical history documents."""
        documents = []

        prefix_map = {
            'genetics_note': f"{patient_id}/genetics/",
            'oncology_note': f"{patient_id}/oncology/",
            'problem_list': f"{patient_id}/problems/",
            'clinic_note': f"{patient_id}/clinic/",
            'family_history': f"{patient_id}/family_history/",
            'social_history': f"{patient_id}/social_history/",
            'genetic_report': f"{patient_id}/lab/genetic/",
            'lab_results': f"{patient_id}/lab/"
        }

        if self.s3_client and source_type in prefix_map:
            try:
                prefix = prefix_map[source_type]
                response = self.s3_client.list_objects_v2(
                    Bucket='cnb-redcap-curation',
                    Prefix=prefix
                )

                if 'Contents' in response:
                    for obj in response['Contents']:
                        doc_response = self.s3_client.get_object(
                            Bucket='cnb-redcap-curation',
                            Key=obj['Key']
                        )

                        content = doc_response['Body'].read().decode('utf-8')
                        documents.append({
                            'key': obj['Key'],
                            'content': content,
                            'source_type': source_type
                        })

            except Exception as e:
                logger.error(f"Error retrieving {source_type}: {e}")

        # Also check problem list from structured data
        if source_type == 'problem_list':
            structured_problems = self._get_structured_problems(patient_id)
            if structured_problems:
                documents.append(structured_problems)

        return documents

    def _get_structured_problems(self, patient_id: str) -> Optional[Dict]:
        """Get problem list from structured data."""
        try:
            problem_path = Path('../athena_extraction_validation/staging_files/problem_list.csv')
            if problem_path.exists():
                df = pd.read_csv(problem_path)
                patient_problems = df[df['patient_id'] == patient_id]

                if not patient_problems.empty:
                    problems = ' '.join(patient_problems['problem_description'].astype(str))
                    return {
                        'content': problems,
                        'source_type': 'problem_list_structured'
                    }

        except Exception as e:
            logger.warning(f"Could not load problem list: {e}")

        return None

    def _retrieve_documents_in_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve documents within date range."""
        return self._retrieve_documents(patient_id, start_date, source_type)

    def _llm_extract(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Extract using pattern matching."""
        content = document['content'].lower()

        # Pattern matching for key variables
        if variable_name == 'cancer_predisposition':
            conditions = []
            for keyword, (_, name) in self.PREDISPOSITION_MAPPING.items():
                if keyword in content:
                    conditions.append(name)

            if conditions:
                return ';'.join(conditions), f"Found: {conditions}"
            else:
                return 'None documented', ''

        elif variable_name == 'germline':
            if 'germline' in content or 'constitutional genetic' in content:
                if 'positive' in content or 'identified' in content or 'confirmed' in content:
                    return 'Yes', 'Germline testing performed'
            return 'No', ''

        elif variable_name == 'family_history':
            if 'family history' in content:
                if 'positive' in content or 'significant' in content:
                    return 'Yes', 'Positive family history'
                elif 'negative' in content or 'no family' in content:
                    return 'No', 'Negative family history'

        return 'Unavailable', ''

    def _get_fallback_sources(self, variable_name: str) -> List[str]:
        """Get fallback sources."""
        return ['clinic_note', 'admission_note', 'discharge_summary']