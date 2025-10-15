"""
Demographics Form Extractor for CBTN REDCap
Extracts basic demographic variables:
- Legal sex
- Race (multi-select)
- Ethnicity
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


class DemographicsFormExtractor(BaseFormExtractor):
    """
    Extractor for the CBTN Demographics form.
    Handles basic patient demographic information.
    """

    # Race mapping for checkbox field
    RACE_MAPPING = {
        'white': '1',
        'caucasian': '1',
        'european': '1',
        'black': '2',
        'african american': '2',
        'african': '2',
        'asian': '3',
        'chinese': '3',
        'japanese': '3',
        'korean': '3',
        'indian': '3',
        'pacific islander': '4',
        'native hawaiian': '4',
        'hawaiian': '4',
        'samoan': '4',
        'american indian': '5',
        'alaska native': '5',
        'native american': '5',
        'indigenous': '5',
        'other': '7',
        'unavailable': '7',
        'unknown': '7',
        'not reported': '7'
    }

    # Ethnicity mapping
    ETHNICITY_MAPPING = {
        'hispanic': '1',
        'latino': '1',
        'latina': '1',
        'latinx': '1',
        'spanish': '1',
        'mexican': '1',
        'puerto rican': '1',
        'cuban': '1',
        'not hispanic': '2',
        'non-hispanic': '2',
        'non hispanic': '2',
        'unavailable': '3',
        'unknown': '3',
        'not reported': '3'
    }

    def __init__(self, data_dictionary_path: str, s3_client=None, ollama_client=None):
        """Initialize the Demographics form extractor."""
        super().__init__(data_dictionary_path)
        self.s3_client = s3_client
        self.ollama_client = ollama_client

    def get_form_name(self) -> str:
        """Return the REDCap form name."""
        return 'demographics'

    def get_variable_extraction_config(self, variable_name: str) -> Optional[Dict]:
        """Get extraction configuration for demographics variables."""

        configs = {
            'legal_sex': {
                'sources': ['demographics_note', 'admission_note', 'registration'],
                'prompt': """
                Extract the patient's legal sex/gender as recorded in medical records.

                Use ONLY these exact values:
                - Male (or return 0)
                - Female (or return 1)
                - Not Available (or return 2)

                Look for: sex, gender, M, F, male, female, boy, girl

                Note: This refers to legal/administrative sex, not gender identity.

                Return ONLY: Male, Female, or Not Available
                """,
                'structured_source': 'patient_table'  # Can also get from Athena
            },

            'race': {
                'sources': ['demographics_note', 'registration', 'admission_note'],
                'prompt': """
                Extract the patient's race/racial background.

                Look for ALL that apply:
                - White/Caucasian
                - Black or African American
                - Asian (includes Chinese, Japanese, Korean, Indian, etc.)
                - Native Hawaiian or Other Pacific Islander
                - American Indian or Alaska Native
                - Other/Unavailable/Not Reported

                Common descriptions:
                - Caucasian → White
                - AA, African American → Black
                - Chinese, Japanese, Korean, Indian → Asian
                - Hispanic/Latino (note: this is ethnicity, not race)

                Return ALL applicable races separated by semicolons.
                Example: "White;Asian" or "Black or African American"
                """,
                'type': 'checkbox'  # Multi-select field
            },

            'ethnicity': {
                'sources': ['demographics_note', 'registration', 'admission_note'],
                'prompt': """
                Extract the patient's ethnicity.

                Use ONLY these exact values:
                - Hispanic or Latino
                - Not Hispanic or Latino
                - Unavailable

                Look for: Hispanic, Latino/Latina/Latinx, Spanish origin, Mexican, Puerto Rican, Cuban

                Important: Ethnicity is separate from race. A patient can be any race and be Hispanic or not.

                Return ONLY one value: Hispanic or Latino, Not Hispanic or Latino, or Unavailable
                """
            }
        }

        return configs.get(variable_name)

    def extract_demographics(
        self,
        patient_id: str,
        extraction_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract all demographics variables for a patient.

        Args:
            patient_id: Patient identifier
            extraction_date: Optional date for document retrieval

        Returns:
            Dict of extracted demographic variables
        """
        logger.info(f"Extracting demographics for patient {patient_id}")

        results = {}

        # Try structured data first (from Athena patient table)
        structured_demographics = self._get_structured_demographics(patient_id)
        if structured_demographics:
            logger.info("Found demographics in structured data")
            results.update(structured_demographics)

        # Extract from clinical documents
        for var_name in ['legal_sex', 'race', 'ethnicity']:
            config = self.get_variable_extraction_config(var_name)

            if config:
                # Skip if already found in structured data with high confidence
                if var_name in results and results[var_name].get('confidence', 0) > 0.9:
                    continue

                extraction_result = self.extract_with_multi_source_validation(
                    patient_id=patient_id,
                    event_date=extraction_date or datetime.now(),
                    variable_name=var_name,
                    sources=config['sources'],
                    custom_prompt=config['prompt']
                )

                # Map to REDCap codes
                if var_name == 'race' and config.get('type') == 'checkbox':
                    extraction_result['value'] = self._map_race_to_codes(
                        extraction_result['value']
                    )
                elif var_name == 'ethnicity':
                    extraction_result['value'] = self._map_ethnicity_to_code(
                        extraction_result['value']
                    )

                results[var_name] = extraction_result

        return results

    def _get_structured_demographics(self, patient_id: str) -> Optional[Dict]:
        """
        Get demographics from structured Athena tables.
        """
        try:
            # Check local staging files
            patient_path = Path('../athena_extraction_validation/staging_files/patient.csv')
            if patient_path.exists():
                df = pd.read_csv(patient_path)

                # Filter for patient
                patient_data = df[df['patient_id'] == patient_id]

                if not patient_data.empty:
                    row = patient_data.iloc[0]
                    structured = {}

                    # Map gender
                    if 'gender' in row:
                        gender = str(row['gender']).lower()
                        if 'f' in gender or 'female' in gender:
                            structured['legal_sex'] = {
                                'value': '1',  # Female
                                'confidence': 0.95,
                                'sources': ['patient_table'],
                                'structured': True
                            }
                        elif 'm' in gender or 'male' in gender:
                            structured['legal_sex'] = {
                                'value': '0',  # Male
                                'confidence': 0.95,
                                'sources': ['patient_table'],
                                'structured': True
                            }

                    # Race and ethnicity might be in patient table
                    if 'race' in row and pd.notna(row['race']):
                        structured['race'] = {
                            'value': self._map_race_to_codes(str(row['race'])),
                            'confidence': 0.90,
                            'sources': ['patient_table'],
                            'structured': True
                        }

                    if 'ethnicity' in row and pd.notna(row['ethnicity']):
                        structured['ethnicity'] = {
                            'value': self._map_ethnicity_to_code(str(row['ethnicity'])),
                            'confidence': 0.90,
                            'sources': ['patient_table'],
                            'structured': True
                        }

                    return structured if structured else None

        except Exception as e:
            logger.warning(f"Could not load structured demographics: {e}")

        return None

    def _map_race_to_codes(self, extracted_race: str) -> str:
        """
        Map extracted race text to REDCap codes.
        Handles multi-select (checkbox) field.
        """
        if not extracted_race or extracted_race == 'Unavailable':
            return '7'  # Other/Unavailable

        extracted_lower = extracted_race.lower()
        mapped_codes = []

        # Split on common delimiters
        races = re.split(r'[;,/]|\s+and\s+', extracted_lower)

        for race in races:
            race = race.strip()

            # Check each race keyword
            for keyword, code in self.RACE_MAPPING.items():
                if keyword in race:
                    if code not in mapped_codes:
                        mapped_codes.append(code)
                    break

        if mapped_codes:
            return '|'.join(mapped_codes)  # Pipe-separated for checkbox
        else:
            return '7'  # Other/Unavailable

    def _map_ethnicity_to_code(self, extracted_ethnicity: str) -> str:
        """
        Map extracted ethnicity text to REDCap code.
        Single-select field.
        """
        if not extracted_ethnicity:
            return '3'  # Unavailable

        extracted_lower = extracted_ethnicity.lower()

        # Check ethnicity keywords
        for keyword, code in self.ETHNICITY_MAPPING.items():
            if keyword in extracted_lower:
                return code

        # Check for explicit "not hispanic"
        if 'not' in extracted_lower or 'non' in extracted_lower:
            return '2'  # Not Hispanic or Latino

        return '3'  # Unavailable

    def _retrieve_documents(
        self,
        patient_id: str,
        event_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve demographic documents."""
        documents = []

        # Map source types to S3 prefixes
        prefix_map = {
            'demographics_note': f"{patient_id}/demographics/",
            'registration': f"{patient_id}/registration/",
            'admission_note': f"{patient_id}/admission/"
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

        return documents

    def _retrieve_documents_in_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve documents within date range for fallback."""
        # Demographics are typically static, so return same as regular retrieval
        return self._retrieve_documents(patient_id, start_date, source_type)

    def _llm_extract(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Extract using LLM or pattern matching."""
        content = document['content'].lower()

        # Simple pattern matching as fallback
        if variable_name == 'legal_sex':
            if 'female' in content or '\nf\n' in content or 'gender: f' in content:
                return 'Female', 'Found: female'
            elif 'male' in content or '\nm\n' in content or 'gender: m' in content:
                return 'Male', 'Found: male'

        elif variable_name == 'race':
            races = []
            if 'white' in content or 'caucasian' in content:
                races.append('White')
            if 'black' in content or 'african american' in content:
                races.append('Black or African American')
            if 'asian' in content:
                races.append('Asian')
            if races:
                return ';'.join(races), f"Found races: {races}"

        elif variable_name == 'ethnicity':
            if 'hispanic' in content or 'latino' in content or 'latina' in content:
                return 'Hispanic or Latino', 'Found: Hispanic/Latino'
            elif 'not hispanic' in content or 'non-hispanic' in content:
                return 'Not Hispanic or Latino', 'Found: Not Hispanic'

        return 'Unavailable', ''

    def _get_fallback_sources(self, variable_name: str) -> List[str]:
        """Get fallback sources for demographics."""
        return ['admission_note', 'clinic_note', 'progress_note']