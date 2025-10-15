"""
Base Form Extractor Class for CBTN REDCap Data Dictionary
Provides core functionality for all form-specific extractors including:
- Multi-source evidence aggregation
- Terminology mapping to REDCap controlled vocabularies
- Branching logic evaluation
- Confidence scoring
- Strategic fallback mechanisms
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from abc import ABC, abstractmethod
import re
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseFormExtractor(ABC):
    """
    Base class for all REDCap form extractors.
    Implements common extraction patterns and multi-source validation.
    """

    def __init__(self, data_dictionary_path: str, llm_client=None):
        """
        Initialize the base form extractor.

        Args:
            data_dictionary_path: Path to CBTN REDCap data dictionary CSV
            llm_client: LLM client for extraction (Ollama)
        """
        self.data_dictionary_path = data_dictionary_path
        self.llm_client = llm_client
        self.data_dictionary = self._load_data_dictionary()
        self.form_variables = self._get_form_variables()
        self.controlled_vocabularies = self._load_controlled_vocabularies()

    def _load_data_dictionary(self) -> pd.DataFrame:
        """Load the CBTN REDCap data dictionary."""
        try:
            df = pd.read_csv(self.data_dictionary_path)
            return df
        except Exception as e:
            logger.error(f"Failed to load data dictionary: {e}")
            raise

    @abstractmethod
    def get_form_name(self) -> str:
        """Return the REDCap form name this extractor handles."""
        pass

    def _get_form_variables(self) -> pd.DataFrame:
        """Get all variables for this specific form."""
        form_name = self.get_form_name()
        return self.data_dictionary[
            self.data_dictionary['Form Name'] == form_name
        ]

    def _load_controlled_vocabularies(self) -> Dict[str, Dict]:
        """
        Parse controlled vocabularies from data dictionary.
        Returns dict of {field_name: {code: label}}
        """
        vocabularies = {}

        for _, row in self.form_variables.iterrows():
            field_name = row['Variable / Field Name']
            choices = row.get('Choices, Calculations, OR Slider Labels', '')

            if pd.notna(choices) and '|' in str(choices):
                vocab = {}
                # Parse choices like "1, Alive | 2, Deceased-due to disease"
                for choice in str(choices).split('|'):
                    choice = choice.strip()
                    if ',' in choice:
                        parts = choice.split(',', 1)
                        code = parts[0].strip()
                        label = parts[1].strip() if len(parts) > 1 else ''
                        vocab[code] = label

                vocabularies[field_name] = vocab

        return vocabularies

    def extract_with_multi_source_validation(
        self,
        patient_id: str,
        event_date: datetime,
        variable_name: str,
        sources: List[str],
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract a variable from multiple sources with consensus validation.

        Args:
            patient_id: Patient identifier
            event_date: Date of clinical event
            variable_name: REDCap variable name
            sources: List of document sources to check
            custom_prompt: Optional custom extraction prompt

        Returns:
            Dict with 'value', 'confidence', 'sources', 'evidence'
        """
        extracted_values = []
        source_evidence = []

        # Extract from each source
        for source_type in sources:
            try:
                documents = self._retrieve_documents(
                    patient_id, event_date, source_type
                )

                for doc in documents:
                    value, evidence = self._llm_extract(
                        variable_name, doc, custom_prompt
                    )

                    if value and value != "Unavailable":
                        extracted_values.append({
                            'value': value,
                            'source': source_type,
                            'evidence': evidence
                        })
                        source_evidence.append(evidence)

            except Exception as e:
                logger.warning(f"Failed to extract from {source_type}: {e}")
                continue

        # No values found - trigger fallback
        if not extracted_values:
            logger.info(f"No values found for {variable_name}, triggering fallback")
            return self._fallback_extraction(
                patient_id, event_date, variable_name
            )

        # Calculate consensus
        final_value, confidence = self._calculate_consensus(extracted_values)

        # Map to REDCap vocabulary if applicable
        if variable_name in self.controlled_vocabularies:
            final_value = self._map_to_redcap_choice(variable_name, final_value)

        return {
            'value': final_value,
            'confidence': confidence,
            'sources': [ev['source'] for ev in extracted_values],
            'evidence': source_evidence,
            'agreement_ratio': self._calculate_agreement_ratio(extracted_values)
        }

    def _calculate_consensus(
        self,
        extracted_values: List[Dict]
    ) -> Tuple[Any, float]:
        """
        Calculate consensus value from multiple extractions.

        Returns:
            Tuple of (consensus_value, confidence_score)
        """
        if not extracted_values:
            return "Unavailable", 0.0

        # Count occurrences of each value
        value_counts = {}
        for item in extracted_values:
            value = item['value']
            value_counts[value] = value_counts.get(value, 0) + 1

        # Find most common value
        most_common = max(value_counts, key=value_counts.get)
        agreement_count = value_counts[most_common]
        total_count = len(extracted_values)

        # Calculate confidence
        base_confidence = 0.6
        agreement_bonus = (agreement_count / total_count) * 0.3
        source_bonus = min(0.1, len(extracted_values) * 0.025)

        confidence = min(1.0, base_confidence + agreement_bonus + source_bonus)

        return most_common, confidence

    def _calculate_agreement_ratio(self, extracted_values: List[Dict]) -> float:
        """Calculate the agreement ratio among extracted values."""
        if not extracted_values:
            return 0.0

        values = [ev['value'] for ev in extracted_values]
        if not values:
            return 0.0

        # Find most common value
        value_counts = {}
        for value in values:
            value_counts[value] = value_counts.get(value, 0) + 1

        most_common_count = max(value_counts.values())
        return most_common_count / len(values)

    def _map_to_redcap_choice(
        self,
        field_name: str,
        extracted_text: str
    ) -> str:
        """
        Map extracted text to REDCap controlled vocabulary.

        Args:
            field_name: REDCap field name
            extracted_text: Extracted text value

        Returns:
            REDCap code or original text if no match
        """
        if field_name not in self.controlled_vocabularies:
            return extracted_text

        choices = self.controlled_vocabularies[field_name]

        # Try exact match first (case-insensitive)
        extracted_lower = extracted_text.lower()
        for code, label in choices.items():
            if extracted_lower == label.lower():
                return code
            # Check if extracted text is contained in label
            if extracted_lower in label.lower():
                return code

        # Try semantic similarity
        best_match = self._find_best_semantic_match(extracted_text, choices)
        if best_match and best_match['similarity'] > 0.8:
            return best_match['code']

        # Check for "Other" option
        other_field = f"{field_name}_other"
        if 'Other' in choices.values() or 'other' in [v.lower() for v in choices.values()]:
            # Find the code for "Other"
            for code, label in choices.items():
                if 'other' in label.lower():
                    # Store the extracted text in the _other field
                    self._store_other_value(other_field, extracted_text)
                    return code

        # No match found - return as is
        logger.warning(
            f"Could not map '{extracted_text}' to REDCap choice for {field_name}"
        )
        return extracted_text

    def _find_best_semantic_match(
        self,
        text: str,
        choices: Dict[str, str]
    ) -> Optional[Dict]:
        """
        Find best semantic match using string similarity.

        Returns:
            Dict with 'code' and 'similarity' or None
        """
        best_match = None
        best_similarity = 0.0

        for code, label in choices.items():
            # Calculate similarity ratio
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

    def _store_other_value(self, field_name: str, value: str):
        """Store value for an 'other' field."""
        # This would be implemented to store the value appropriately
        # For now, we'll log it
        logger.info(f"Storing '{value}' for other field: {field_name}")

    def _fallback_extraction(
        self,
        patient_id: str,
        event_date: datetime,
        variable_name: str
    ) -> Dict[str, Any]:
        """
        Implement strategic fallback when primary extraction fails.

        This method extends the search window and uses alternative sources.
        """
        logger.info(f"Executing fallback extraction for {variable_name}")

        # Extend temporal window
        extended_window = timedelta(days=30)
        start_date = event_date - extended_window
        end_date = event_date + extended_window

        # Define fallback sources based on variable type
        fallback_sources = self._get_fallback_sources(variable_name)

        # Try extraction with extended window
        fallback_values = []

        for source in fallback_sources:
            try:
                documents = self._retrieve_documents_in_range(
                    patient_id, start_date, end_date, source
                )

                for doc in documents:
                    value, evidence = self._llm_extract(
                        variable_name, doc, None
                    )

                    if value and value != "Unavailable":
                        fallback_values.append({
                            'value': value,
                            'source': f"{source}_fallback",
                            'evidence': evidence
                        })

            except Exception as e:
                logger.warning(f"Fallback extraction failed for {source}: {e}")
                continue

        if fallback_values:
            final_value, confidence = self._calculate_consensus(fallback_values)

            # Apply confidence penalty for fallback
            confidence = confidence * 0.85

            return {
                'value': final_value,
                'confidence': confidence,
                'sources': [fv['source'] for fv in fallback_values],
                'fallback_used': True,
                'agreement_ratio': self._calculate_agreement_ratio(fallback_values)
            }

        # No fallback succeeded
        return {
            'value': 'Unavailable',
            'confidence': 0.0,
            'sources': [],
            'fallback_used': True,
            'fallback_failed': True
        }

    @abstractmethod
    def _get_fallback_sources(self, variable_name: str) -> List[str]:
        """
        Get fallback document sources for a specific variable.
        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def _retrieve_documents(
        self,
        patient_id: str,
        event_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """
        Retrieve documents from specified source.
        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def _retrieve_documents_in_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """
        Retrieve documents within date range.
        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def _llm_extract(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Extract variable value using LLM.
        Must be implemented by subclasses.

        Returns:
            Tuple of (extracted_value, evidence_text)
        """
        pass

    def evaluate_branching_logic(
        self,
        field_name: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate if a field should be shown based on branching logic.

        Args:
            field_name: REDCap field name
            context: Current form context with other field values

        Returns:
            True if field should be shown/extracted
        """
        # Get branching logic from data dictionary
        field_row = self.form_variables[
            self.form_variables['Variable / Field Name'] == field_name
        ]

        if field_row.empty:
            return True  # Default to showing field

        branching_logic = field_row.iloc[0].get(
            'Branching Logic (Show field only if...)', ''
        )

        if pd.isna(branching_logic) or not branching_logic:
            return True  # No branching logic

        # Evaluate the branching logic
        return self._evaluate_logic_expression(branching_logic, context)

    def _evaluate_logic_expression(
        self,
        logic: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate REDCap branching logic expression.

        This is a simplified evaluator - full implementation would
        handle all REDCap logic operators.
        """
        try:
            # Handle simple equality checks
            if '=' in logic:
                # Parse expressions like [field_name] = 'value'
                match = re.match(r'\[(\w+)\]\s*=\s*[\'"]?(\w+)[\'"]?', logic)
                if match:
                    field, value = match.groups()
                    return str(context.get(field, '')) == value

            # Handle 'or' conditions
            if ' or ' in logic.lower():
                conditions = logic.split(' or ')
                return any(
                    self._evaluate_logic_expression(cond, context)
                    for cond in conditions
                )

            # Default to True for complex logic we can't parse
            logger.warning(f"Could not parse branching logic: {logic}")
            return True

        except Exception as e:
            logger.error(f"Error evaluating branching logic: {e}")
            return True

    def extract_form_data(
        self,
        patient_id: str,
        event_date: datetime,
        event_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract all variables for this form.

        Args:
            patient_id: Patient identifier
            event_date: Date of clinical event
            event_context: Optional context from other forms

        Returns:
            Dict of extracted variables with confidence scores
        """
        results = {}
        context = event_context or {}

        # Extract each variable in the form
        for _, row in self.form_variables.iterrows():
            field_name = row['Variable / Field Name']
            field_type = row['Field Type']

            # Skip identifier fields and system fields
            if row.get('Identifier?') == 'y':
                logger.info(f"Skipping identifier field: {field_name}")
                continue

            # Check branching logic
            if not self.evaluate_branching_logic(field_name, context):
                logger.info(f"Skipping {field_name} due to branching logic")
                continue

            # Get extraction configuration for this variable
            extraction_config = self.get_variable_extraction_config(field_name)

            if not extraction_config:
                logger.info(f"No extraction config for {field_name}")
                continue

            # Extract the variable
            extraction_result = self.extract_with_multi_source_validation(
                patient_id=patient_id,
                event_date=event_date,
                variable_name=field_name,
                sources=extraction_config.get('sources', []),
                custom_prompt=extraction_config.get('prompt')
            )

            results[field_name] = extraction_result

            # Update context for branching logic
            context[field_name] = extraction_result['value']

        return results

    @abstractmethod
    def get_variable_extraction_config(self, variable_name: str) -> Optional[Dict]:
        """
        Get extraction configuration for a specific variable.
        Must be implemented by subclasses.

        Returns:
            Dict with 'sources', 'prompt', and other config
        """
        pass