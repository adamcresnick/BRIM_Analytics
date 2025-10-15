"""
REDCap Terminology Mapper
Maps extracted clinical text to REDCap controlled vocabularies.
Handles the full CBTN data dictionary terminology alignment.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import pandas as pd
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class REDCapTerminologyMapper:
    """
    Maps extracted text values to REDCap controlled vocabulary codes.
    """

    def __init__(self, data_dictionary_path: str):
        """
        Initialize the terminology mapper.

        Args:
            data_dictionary_path: Path to CBTN data dictionary CSV
        """
        self.data_dictionary_path = data_dictionary_path
        self.data_dictionary = self._load_data_dictionary()
        self.vocabularies = self._build_all_vocabularies()
        self.who_map = self._build_who_cns5_mapping()  # Fixed attribute name
        self.location_map = self._build_location_mapping()

    def _load_data_dictionary(self) -> pd.DataFrame:
        """Load the CBTN data dictionary."""
        try:
            return pd.read_csv(self.data_dictionary_path)
        except Exception as e:
            logger.error(f"Failed to load data dictionary: {e}")
            raise

    def _build_all_vocabularies(self) -> Dict[str, Dict]:
        """
        Build all controlled vocabularies from the data dictionary.
        Returns: {field_name: {code: label, ...}}
        """
        vocabularies = {}

        for _, row in self.data_dictionary.iterrows():
            field_name = row['Variable / Field Name']
            choices = row.get('Choices, Calculations, OR Slider Labels', '')

            if pd.notna(choices) and '|' in str(choices):
                vocab = {}
                for choice in str(choices).split('|'):
                    choice = choice.strip()
                    if ',' in choice:
                        parts = choice.split(',', 1)
                        code = parts[0].strip()
                        label = parts[1].strip() if len(parts) > 1 else ''
                        vocab[code] = label

                vocabularies[field_name] = vocab

        logger.info(f"Loaded vocabularies for {len(vocabularies)} fields")
        return vocabularies

    def _build_who_cns5_mapping(self) -> Dict[str, str]:
        """
        Build WHO CNS5 diagnosis mapping dictionary.
        Maps common terms to REDCap codes.
        """
        who_map = {}

        if 'who_cns5_diagnosis' in self.vocabularies:
            vocab = self.vocabularies['who_cns5_diagnosis']

            # Build reverse mapping and synonyms
            for code, label in vocab.items():
                # Add exact label
                who_map[label.lower()] = code

                # Add common abbreviations and synonyms
                if 'glioblastoma' in label.lower():
                    who_map['gbm'] = code
                    who_map['glioblastoma multiforme'] = code
                    who_map['grade iv astrocytoma'] = code

                if 'pilocytic astrocytoma' in label.lower():
                    who_map['pa'] = code
                    who_map['juvenile pilocytic astrocytoma'] = code
                    who_map['jpa'] = code

                if 'medulloblastoma' in label.lower():
                    who_map['mb'] = code
                    who_map['medulloblastoma'] = code

                if 'ependymoma' in label.lower():
                    who_map['epn'] = code
                    who_map['ependymoma'] = code

                if 'diffuse midline glioma' in label.lower():
                    who_map['dmg'] = code
                    who_map['dipg'] = code
                    who_map['diffuse intrinsic pontine glioma'] = code

                if 'atrt' in label.lower() or 'rhabdoid' in label.lower():
                    who_map['atrt'] = code
                    who_map['at/rt'] = code
                    who_map['atypical teratoid rhabdoid tumor'] = code

        return who_map

    def _build_location_mapping(self) -> Dict[str, str]:
        """
        Build anatomical location mapping dictionary.
        """
        location_map = {}

        if 'tumor_location' in self.vocabularies:
            vocab = self.vocabularies['tumor_location']

            for code, label in vocab.items():
                # Add exact label
                location_map[label.lower()] = code

                # Add anatomical synonyms
                if 'frontal' in label.lower():
                    location_map['frontal'] = code
                    location_map['prefrontal'] = code
                    location_map['motor cortex'] = code

                if 'temporal' in label.lower():
                    location_map['temporal'] = code
                    location_map['hippocampal'] = code
                    location_map['mesial temporal'] = code

                if 'parietal' in label.lower():
                    location_map['parietal'] = code
                    location_map['sensory cortex'] = code

                if 'occipital' in label.lower():
                    location_map['occipital'] = code
                    location_map['visual cortex'] = code

                if 'cerebellum' in label.lower() or 'posterior fossa' in label.lower():
                    location_map['cerebellar'] = code
                    location_map['cerebellum'] = code
                    location_map['posterior fossa'] = code
                    location_map['vermis'] = code

                if 'brainstem' in label.lower():
                    location_map['brainstem'] = code
                    location_map['pons'] = code
                    location_map['pontine'] = code
                    location_map['medulla'] = code
                    location_map['midbrain'] = code

        return location_map

    def map_to_vocabulary(
        self,
        field_name: str,
        extracted_value: str,
        allow_other: bool = True
    ) -> Tuple[str, Optional[str]]:
        """
        Map an extracted value to REDCap vocabulary.

        Args:
            field_name: REDCap field name
            extracted_value: Extracted text value
            allow_other: Whether to use "Other" field if available

        Returns:
            Tuple of (mapped_code, other_text)
        """
        if field_name not in self.vocabularies:
            logger.warning(f"No vocabulary found for field: {field_name}")
            return extracted_value, None

        vocab = self.vocabularies[field_name]

        # Special handling for specific fields
        if field_name == 'who_cns5_diagnosis':
            return self._map_who_cns5(extracted_value)

        if field_name == 'tumor_location':
            return self._map_tumor_location(extracted_value)

        # General mapping
        extracted_lower = extracted_value.lower().strip()

        # Try exact match
        for code, label in vocab.items():
            if extracted_lower == label.lower():
                return code, None

        # Try contains match
        for code, label in vocab.items():
            if extracted_lower in label.lower() or label.lower() in extracted_lower:
                return code, None

        # Try similarity matching
        best_match = self._find_best_match(extracted_value, vocab)
        if best_match and best_match['similarity'] > 0.8:
            return best_match['code'], None

        # Use "Other" field if available
        if allow_other:
            other_code = self._find_other_code(vocab)
            if other_code:
                return other_code, extracted_value

        # Return unmapped value
        logger.warning(
            f"Could not map '{extracted_value}' for field {field_name}"
        )
        return extracted_value, None

    def _map_who_cns5(self, extracted_value: str) -> Tuple[str, Optional[str]]:
        """
        Special mapping for WHO CNS5 diagnosis.
        """
        extracted_lower = extracted_value.lower().strip()

        # Check pre-built mapping
        if extracted_lower in self.who_map:
            return self.who_map[extracted_lower], None

        # Check vocabularies
        vocab = self.vocabularies.get('who_cns5_diagnosis', {})

        # Pattern matching for WHO classifications
        patterns = {
            r'glioblastoma|gbm|grade\s*(iv|4).*glioma': 'High-Grade Glioma, Glioblastoma, IDH-wildtype',
            r'pilocytic\s*astrocytoma': 'Low-Grade Glioma, Pilocytic astrocytoma',
            r'medulloblastoma': 'Medulloblastoma, NOS or NEC',
            r'ependymoma': 'Ependymoma, NOS or NEC',
            r'diffuse\s*(midline|intrinsic\s*pontine)\s*glioma|dmg|dipg': 'High-Grade Glioma, Diffuse midline glioma, H3 K27-altered',
            r'atrt|rhabdoid': 'Atypical teratoid/rhabdoid tumor, ATRT, NOS or NEC'
        }

        for pattern, diagnosis in patterns.items():
            if re.search(pattern, extracted_lower):
                # Find code for this diagnosis
                for code, label in vocab.items():
                    if diagnosis.lower() in label.lower():
                        return code, None

        # Check for "Other" option
        for code, label in vocab.items():
            if 'other' in label.lower() or 'not a primary' in label.lower():
                return code, extracted_value

        return extracted_value, None

    def _map_tumor_location(self, extracted_value: str) -> Tuple[str, Optional[str]]:
        """
        Special mapping for tumor location (can be multiple).
        """
        extracted_lower = extracted_value.lower().strip()
        mapped_codes = []

        # Split on common delimiters
        locations = re.split(r'[;,/]|\s+and\s+', extracted_lower)

        vocab = self.vocabularies.get('tumor_location', {})

        for location in locations:
            location = location.strip()

            # Check location map
            if location in self.location_map:
                mapped_codes.append(self.location_map[location])
                continue

            # Check vocabulary
            for code, label in vocab.items():
                if location in label.lower() or label.lower() in location:
                    mapped_codes.append(code)
                    break

        if mapped_codes:
            # Return pipe-separated codes for checkboxes
            return '|'.join(mapped_codes), None

        # Return unmapped
        return extracted_value, None

    def _find_best_match(
        self,
        text: str,
        vocabulary: Dict[str, str]
    ) -> Optional[Dict]:
        """
        Find best match using string similarity.
        """
        best_match = None
        best_similarity = 0.0

        for code, label in vocabulary.items():
            similarity = SequenceMatcher(
                None, text.lower(), label.lower()
            ).ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = {
                    'code': code,
                    'label': label,
                    'similarity': similarity
                }

        return best_match if best_similarity > 0.5 else None

    def _find_other_code(self, vocabulary: Dict[str, str]) -> Optional[str]:
        """
        Find the code for "Other" option in vocabulary.
        """
        for code, label in vocabulary.items():
            if 'other' in label.lower() and 'mother' not in label.lower():
                return code
        return None

    def map_checkbox_field(
        self,
        field_name: str,
        extracted_values: List[str]
    ) -> str:
        """
        Map multiple values for checkbox fields.

        Args:
            field_name: REDCap field name
            extracted_values: List of extracted values

        Returns:
            Pipe-separated codes (e.g., "1|3|5")
        """
        if field_name not in self.vocabularies:
            return '|'.join(extracted_values)

        vocab = self.vocabularies[field_name]
        mapped_codes = []

        for value in extracted_values:
            code, _ = self.map_to_vocabulary(field_name, value, allow_other=False)
            if code and code in vocab:
                mapped_codes.append(code)

        return '|'.join(mapped_codes) if mapped_codes else ''

    def validate_mapped_value(
        self,
        field_name: str,
        mapped_value: str
    ) -> bool:
        """
        Validate that a mapped value is valid for the field.
        """
        if field_name not in self.vocabularies:
            return True  # Can't validate without vocabulary

        vocab = self.vocabularies[field_name]

        # Check if it's a valid code
        if mapped_value in vocab:
            return True

        # Check checkbox fields (pipe-separated)
        if '|' in mapped_value:
            codes = mapped_value.split('|')
            return all(code in vocab for code in codes)

        return False

    def get_field_choices(self, field_name: str) -> Dict[str, str]:
        """
        Get all choices for a field.

        Returns:
            Dict of {code: label}
        """
        return self.vocabularies.get(field_name, {})

    def get_choice_label(self, field_name: str, code: str) -> Optional[str]:
        """
        Get the label for a specific choice code.
        """
        vocab = self.vocabularies.get(field_name, {})
        return vocab.get(code)

    def export_terminology_report(self) -> Dict[str, Any]:
        """
        Export a report of all terminologies loaded.
        """
        report = {
            'total_fields': len(self.vocabularies),
            'fields': {}
        }

        for field_name, vocab in self.vocabularies.items():
            report['fields'][field_name] = {
                'choice_count': len(vocab),
                'choices': vocab,
                'has_other': any('other' in label.lower() for label in vocab.values())
            }

        return report