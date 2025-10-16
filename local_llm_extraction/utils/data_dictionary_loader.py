"""
Data Dictionary Loader
Loads and provides access to CBTN data dictionary field definitions
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DataDictionaryLoader:
    """
    Loads CBTN data dictionary and provides field definitions for LLM prompts
    """

    def __init__(self, dictionary_path: Optional[str] = None):
        """
        Initialize the data dictionary loader

        Args:
            dictionary_path: Path to CBTN data dictionary CSV file
        """
        if dictionary_path is None:
            # Default path
            base_path = Path(__file__).parent.parent / "Dictionary"
            dictionary_path = base_path / "CBTN_DataDictionary_2025-10-15.csv"

        self.dictionary_path = Path(dictionary_path)
        self.data_dict = None
        self._load_dictionary()

    def _load_dictionary(self):
        """Load the data dictionary CSV file"""
        try:
            self.data_dict = pd.read_csv(self.dictionary_path, encoding='utf-8-sig')
            logger.info(f"Loaded data dictionary with {len(self.data_dict)} fields")

            # Clean column names (remove BOM and extra spaces)
            self.data_dict.columns = [col.strip() for col in self.data_dict.columns]

        except Exception as e:
            logger.error(f"Failed to load data dictionary from {self.dictionary_path}: {e}")
            self.data_dict = pd.DataFrame()

    def get_field_definition(self, variable_name: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive field definition for a variable

        Args:
            variable_name: The field name (e.g., 'extent_of_tumor_resection')

        Returns:
            Dictionary with field definition or None if not found
        """
        if self.data_dict is None or self.data_dict.empty:
            logger.warning("Data dictionary not loaded")
            return None

        # Find the field
        field_row = self.data_dict[
            self.data_dict['Variable / Field Name'] == variable_name
        ]

        if field_row.empty:
            logger.warning(f"Field '{variable_name}' not found in data dictionary")
            return None

        field = field_row.iloc[0]

        # Extract key information
        definition = {
            'variable_name': variable_name,
            'field_label': field.get('Field Label', ''),
            'field_type': field.get('Field Type', ''),
            'form_name': field.get('Form Name', ''),
            'section_header': field.get('Section Header', ''),
            'field_note': field.get('Field Note', ''),
            'choices': field.get('Choices, Calculations, OR Slider Labels', ''),
            'validation_type': field.get('Text Validation Type OR Show Slider Number', ''),
            'required': field.get('Required Field?', ''),
        }

        # Parse choices into a clean list
        if definition['choices'] and pd.notna(definition['choices']):
            definition['choices_parsed'] = self._parse_choices(definition['choices'])
        else:
            definition['choices_parsed'] = []

        return definition

    def _parse_choices(self, choices_str: str) -> list:
        """
        Parse the choices string into a clean list

        Args:
            choices_str: String like "1, Gross/Near total resection | 2, Partial resection | 3, Biopsy only"

        Returns:
            List of choice dictionaries
        """
        if not choices_str or pd.isna(choices_str):
            return []

        choices = []
        parts = str(choices_str).split('|')

        for part in parts:
            part = part.strip()
            if ',' in part:
                # Split on first comma only
                code, label = part.split(',', 1)
                choices.append({
                    'code': code.strip(),
                    'label': label.strip()
                })
            else:
                choices.append({
                    'code': '',
                    'label': part
                })

        return choices

    def format_field_for_prompt(self, variable_name: str) -> str:
        """
        Format field definition for inclusion in LLM prompt

        Args:
            variable_name: The field name

        Returns:
            Formatted string for prompt
        """
        definition = self.get_field_definition(variable_name)

        if definition is None:
            return f"Field '{variable_name}' not found in data dictionary."

        prompt_parts = []

        # Field label and description
        prompt_parts.append(f"📋 FIELD DEFINITION FOR: {variable_name}")
        prompt_parts.append(f"   Label: {definition['field_label']}")

        if definition['field_note']:
            prompt_parts.append(f"   Note: {definition['field_note']}")

        prompt_parts.append(f"   Type: {definition['field_type']}")

        # Valid choices/values
        if definition['choices_parsed']:
            prompt_parts.append(f"\n   ✓ VALID VALUES (you MUST select from these options):")
            for choice in definition['choices_parsed']:
                if choice['code']:
                    prompt_parts.append(f"      {choice['code']} = {choice['label']}")
                else:
                    prompt_parts.append(f"      • {choice['label']}")

        # Additional context
        if definition['form_name']:
            prompt_parts.append(f"\n   Form: {definition['form_name']}")

        if definition['section_header']:
            prompt_parts.append(f"   Section: {definition['section_header']}")

        if definition['required'] == 'y':
            prompt_parts.append(f"   ⚠️ This is a REQUIRED field")

        return "\n".join(prompt_parts)

    def get_related_fields(self, variable_name: str) -> list:
        """
        Get related fields that might provide context

        Args:
            variable_name: The primary field name

        Returns:
            List of related field names
        """
        if self.data_dict is None or self.data_dict.empty:
            return []

        # Get the form and section of the primary field
        field_row = self.data_dict[
            self.data_dict['Variable / Field Name'] == variable_name
        ]

        if field_row.empty:
            return []

        field = field_row.iloc[0]
        form_name = field.get('Form Name', '')
        section = field.get('Section Header', '')

        # Find fields in the same form and section
        related = self.data_dict[
            (self.data_dict['Form Name'] == form_name) &
            (self.data_dict['Section Header'] == section) &
            (self.data_dict['Variable / Field Name'] != variable_name)
        ]

        return related['Variable / Field Name'].tolist()[:5]  # Limit to 5 related fields


# Singleton instance
_dictionary_loader = None

def get_data_dictionary() -> DataDictionaryLoader:
    """Get or create the singleton data dictionary loader"""
    global _dictionary_loader
    if _dictionary_loader is None:
        _dictionary_loader = DataDictionaryLoader()
    return _dictionary_loader
