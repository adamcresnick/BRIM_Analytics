"""
Concomitant Medications Form Extractor for CBTN REDCap
Extracts non-cancer medications including:
- Medication names (up to 10)
- Schedule type (Scheduled/PRN/Unknown)
- Links to diagnosis event
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


class ConcomitantMedicationsFormExtractor(BaseFormExtractor):
    """
    Extractor for the CBTN Concomitant Medications form.
    Handles non-tumor-directed medications and supportive care drugs.
    """

    # Common pediatric brain tumor supportive care medications
    COMMON_MEDICATIONS = {
        # Anti-epileptics
        'levetiracetam': 'Keppra',
        'keppra': 'Keppra',
        'phenytoin': 'Dilantin',
        'dilantin': 'Dilantin',
        'carbamazepine': 'Tegretol',
        'tegretol': 'Tegretol',
        'valproic acid': 'Depakote',
        'depakote': 'Depakote',
        'lamotrigine': 'Lamictal',
        'lamictal': 'Lamictal',
        'oxcarbazepine': 'Trileptal',
        'trileptal': 'Trileptal',
        'lacosamide': 'Vimpat',
        'vimpat': 'Vimpat',

        # Corticosteroids
        'dexamethasone': 'Dexamethasone',
        'decadron': 'Dexamethasone',
        'prednisone': 'Prednisone',
        'prednisolone': 'Prednisolone',
        'methylprednisolone': 'Solu-Medrol',
        'solu-medrol': 'Solu-Medrol',
        'hydrocortisone': 'Hydrocortisone',

        # Anti-emetics
        'ondansetron': 'Zofran',
        'zofran': 'Zofran',
        'granisetron': 'Kytril',
        'kytril': 'Kytril',
        'metoclopramide': 'Reglan',
        'reglan': 'Reglan',
        'promethazine': 'Phenergan',
        'phenergan': 'Phenergan',
        'lorazepam': 'Ativan',
        'ativan': 'Ativan',

        # GI prophylaxis
        'omeprazole': 'Prilosec',
        'prilosec': 'Prilosec',
        'lansoprazole': 'Prevacid',
        'prevacid': 'Prevacid',
        'pantoprazole': 'Protonix',
        'protonix': 'Protonix',
        'esomeprazole': 'Nexium',
        'nexium': 'Nexium',
        'ranitidine': 'Zantac',
        'zantac': 'Zantac',
        'famotidine': 'Pepcid',
        'pepcid': 'Pepcid',

        # Antibiotics/Prophylaxis
        'sulfamethoxazole': 'Bactrim',
        'trimethoprim': 'Bactrim',
        'bactrim': 'Bactrim',
        'pentamidine': 'Pentamidine',
        'acyclovir': 'Zovirax',
        'zovirax': 'Zovirax',
        'valacyclovir': 'Valtrex',
        'valtrex': 'Valtrex',
        'fluconazole': 'Diflucan',
        'diflucan': 'Diflucan',

        # Pain management
        'acetaminophen': 'Tylenol',
        'tylenol': 'Tylenol',
        'ibuprofen': 'Motrin',
        'motrin': 'Motrin',
        'morphine': 'Morphine',
        'oxycodone': 'Oxycodone',
        'hydrocodone': 'Hydrocodone',
        'gabapentin': 'Neurontin',
        'neurontin': 'Neurontin',

        # Hormone replacement
        'levothyroxine': 'Synthroid',
        'synthroid': 'Synthroid',
        'hydrocortisone': 'Cortef',
        'cortef': 'Cortef',
        'desmopressin': 'DDAVP',
        'ddavp': 'DDAVP',
        'growth hormone': 'Growth Hormone',
        'somatropin': 'Growth Hormone',

        # Psychiatric/Behavioral
        'methylphenidate': 'Ritalin',
        'ritalin': 'Ritalin',
        'sertraline': 'Zoloft',
        'zoloft': 'Zoloft',
        'fluoxetine': 'Prozac',
        'prozac': 'Prozac',
        'escitalopram': 'Lexapro',
        'lexapro': 'Lexapro',
        'risperidone': 'Risperdal',
        'risperdal': 'Risperdal',

        # Other supportive
        'melatonin': 'Melatonin',
        'docusate': 'Colace',
        'colace': 'Colace',
        'senna': 'Senokot',
        'senokot': 'Senokot',
        'polyethylene glycol': 'Miralax',
        'miralax': 'Miralax'
    }

    # Medication schedule mapping
    SCHEDULE_MAPPING = {
        'scheduled': 'Scheduled',
        'daily': 'Scheduled',
        'bid': 'Scheduled',
        'tid': 'Scheduled',
        'qid': 'Scheduled',
        'q4h': 'Scheduled',
        'q6h': 'Scheduled',
        'q8h': 'Scheduled',
        'q12h': 'Scheduled',
        'prn': 'PRN',
        'as needed': 'PRN',
        'pro re nata': 'PRN',
        'unknown': 'Unknown'
    }

    def __init__(self, data_dictionary_path: str, s3_client=None, ollama_client=None):
        """Initialize the Concomitant Medications form extractor."""
        super().__init__(data_dictionary_path)
        self.s3_client = s3_client
        self.ollama_client = ollama_client

    def get_form_name(self) -> str:
        """Return the REDCap form name."""
        return 'concomitant_medications'

    def get_variable_extraction_config(self, variable_name: str) -> Optional[Dict]:
        """Get extraction configuration for medication variables."""

        configs = {
            'conmed_date': {
                'sources': ['medication_list', 'medication_reconciliation', 'mar'],
                'prompt': """
                Extract the medication reconciliation or list date.

                Look for:
                - Medication reconciliation date
                - Medication list updated date
                - MAR date

                Return date in YYYY-MM-DD format.
                """
            },

            'conmed_total': {
                'sources': ['medication_list', 'medication_reconciliation', 'mar'],
                'prompt': """
                Count the total number of non-cancer medications.

                Exclude:
                - Chemotherapy agents (vincristine, carboplatin, temozolomide, etc.)
                - Radiation-related medications

                Include:
                - Anti-seizure medications
                - Steroids (dexamethasone, prednisone)
                - Anti-emetics
                - Pain medications
                - Antibiotics/antifungals
                - GI medications
                - Hormone replacements
                - Psychiatric medications

                Return:
                - Exact number (1-10)
                - "More than 10" if >10 medications
                - "None noted" if no medications

                Return ONLY the count or phrase.
                """
            }
        }

        # Add configs for individual medications (1-10)
        for i in range(1, 11):
            configs[f'conmed_{i}'] = {
                'sources': ['medication_list', 'medication_reconciliation', 'mar'],
                'prompt': f"""
                Extract the {i}{"st" if i==1 else "nd" if i==2 else "rd" if i==3 else "th"} non-cancer medication name.

                Return the generic drug name (not brand name).
                Common supportive care medications include:
                - Anti-epileptics (levetiracetam, phenytoin, etc.)
                - Steroids (dexamethasone, prednisone)
                - Anti-emetics (ondansetron, metoclopramide)
                - GI prophylaxis (omeprazole, famotidine)
                - Prophylactic antibiotics (bactrim, acyclovir)
                - Pain medications
                - Hormone replacements

                Return ONLY the medication name or "N/A" if not applicable.
                """
            }

            configs[f'conmed_{i}_schedule'] = {
                'sources': ['medication_list', 'medication_reconciliation', 'mar'],
                'prompt': f"""
                Extract the schedule for medication #{i}.

                Use ONLY these values:
                - Scheduled (for regular/daily medications)
                - PRN (for as-needed medications)
                - Unknown

                Look for: daily, BID, TID, QID, PRN, as needed, scheduled

                Return ONLY: Scheduled, PRN, or Unknown
                """,
                'branching': f'conmed_{i} != N/A'
            }

        return configs.get(variable_name)

    def extract_concomitant_medications(
        self,
        patient_id: str,
        medication_date: datetime,
        diagnosis_link: Optional[str] = None,
        timepoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract concomitant medications for a specific timepoint.

        Args:
            patient_id: Patient identifier
            medication_date: Date of medication reconciliation
            diagnosis_link: Link to diagnosis event (tx_dx_link)
            timepoint: Update timepoint (3M, 6M, etc.)

        Returns:
            Dict of extracted medication variables
        """
        logger.info(f"Extracting concomitant medications for {patient_id} on {medication_date}")

        results = {}

        # Add linkage information
        if diagnosis_link:
            results['conmed_dx_link'] = {
                'value': diagnosis_link,
                'confidence': 1.0,
                'sources': ['provided'],
                'linked': True
            }

        if timepoint:
            results['conmed_timepoint'] = {
                'value': timepoint,
                'confidence': 1.0,
                'sources': ['provided']
            }

        # Get medications from structured data first
        structured_meds = self._get_structured_medications(patient_id, medication_date)

        if structured_meds:
            logger.info(f"Found {len(structured_meds)} medications in structured data")
            results.update(self._process_structured_medications(structured_meds))
        else:
            # Extract from clinical documents
            results.update(self._extract_from_documents(patient_id, medication_date))

        # Add medication reconciliation date
        results['conmed_date'] = {
            'value': medication_date.strftime('%Y-%m-%d'),
            'confidence': 1.0,
            'sources': ['provided']
        }

        return results

    def _get_structured_medications(
        self,
        patient_id: str,
        medication_date: datetime
    ) -> Optional[List[Dict]]:
        """Get medications from structured Athena tables."""
        try:
            # Check local staging files
            med_path = Path('../athena_extraction_validation/staging_files/medications.csv')
            if med_path.exists():
                df = pd.read_csv(med_path)

                # Filter for patient
                patient_meds = df[df['patient_id'] == patient_id]

                if not patient_meds.empty:
                    # Filter by date proximity (within 30 days)
                    medications = []

                    for _, row in patient_meds.iterrows():
                        if 'start_date' in row:
                            try:
                                start_date = pd.to_datetime(row['start_date'])
                                if abs((start_date - medication_date).days) <= 30:
                                    # Check if non-cancer medication
                                    med_name = str(row.get('medication_name', '')).lower()

                                    if not self._is_chemotherapy(med_name):
                                        medications.append({
                                            'name': self._standardize_medication_name(med_name),
                                            'schedule': self._extract_schedule(row),
                                            'source': 'medications_table'
                                        })
                            except:
                                continue

                    return medications[:10]  # Limit to 10 medications

        except Exception as e:
            logger.warning(f"Could not load structured medications: {e}")

        return None

    def _process_structured_medications(
        self,
        medications: List[Dict]
    ) -> Dict[str, Any]:
        """Process structured medications into REDCap format."""
        results = {}

        # Count total
        total = len(medications)
        if total == 0:
            total_value = "None noted"
        elif total > 10:
            total_value = "More than 10"
        else:
            total_value = str(total)

        results['conmed_total'] = {
            'value': total_value,
            'confidence': 0.95,
            'sources': ['medications_table'],
            'structured': True
        }

        # Add individual medications
        for i, med in enumerate(medications[:10], 1):
            results[f'conmed_{i}'] = {
                'value': med['name'],
                'confidence': 0.95,
                'sources': ['medications_table'],
                'structured': True
            }

            results[f'conmed_{i}_schedule'] = {
                'value': med['schedule'],
                'confidence': 0.90,
                'sources': ['medications_table']
            }

        # Fill remaining slots with N/A
        for i in range(len(medications) + 1, 11):
            results[f'conmed_{i}'] = {
                'value': 'N/A',
                'confidence': 1.0,
                'sources': ['not_applicable']
            }

        return results

    def _extract_from_documents(
        self,
        patient_id: str,
        medication_date: datetime
    ) -> Dict[str, Any]:
        """Extract medications from clinical documents."""
        results = {}

        # Extract total count
        total_config = self.get_variable_extraction_config('conmed_total')
        total_result = self.extract_with_multi_source_validation(
            patient_id=patient_id,
            event_date=medication_date,
            variable_name='conmed_total',
            sources=total_config['sources'],
            custom_prompt=total_config['prompt']
        )
        results['conmed_total'] = total_result

        # Determine number of medications to extract
        total_value = total_result['value']
        if total_value == "None noted":
            num_meds = 0
        elif total_value == "More than 10":
            num_meds = 10
        else:
            try:
                num_meds = min(int(total_value), 10)
            except:
                num_meds = 0

        # Extract individual medications
        for i in range(1, 11):
            if i <= num_meds:
                # Extract medication name
                med_config = self.get_variable_extraction_config(f'conmed_{i}')
                med_result = self.extract_with_multi_source_validation(
                    patient_id=patient_id,
                    event_date=medication_date,
                    variable_name=f'conmed_{i}',
                    sources=med_config['sources'],
                    custom_prompt=med_config['prompt']
                )

                # Standardize medication name
                med_result['value'] = self._standardize_medication_name(
                    med_result['value']
                )
                results[f'conmed_{i}'] = med_result

                # Extract schedule if medication found
                if med_result['value'] != 'N/A':
                    schedule_config = self.get_variable_extraction_config(
                        f'conmed_{i}_schedule'
                    )
                    schedule_result = self.extract_with_multi_source_validation(
                        patient_id=patient_id,
                        event_date=medication_date,
                        variable_name=f'conmed_{i}_schedule',
                        sources=schedule_config['sources'],
                        custom_prompt=schedule_config['prompt']
                    )
                    results[f'conmed_{i}_schedule'] = schedule_result
            else:
                # Fill with N/A
                results[f'conmed_{i}'] = {
                    'value': 'N/A',
                    'confidence': 1.0,
                    'sources': ['not_applicable']
                }

        return results

    def _is_chemotherapy(self, medication_name: str) -> bool:
        """Check if medication is a chemotherapy agent."""
        chemo_keywords = [
            'vincristine', 'carboplatin', 'cisplatin', 'cyclophosphamide',
            'lomustine', 'ccnu', 'temozolomide', 'temodar', 'etoposide',
            'methotrexate', 'bevacizumab', 'avastin', 'irinotecan',
            'topotecan', 'thiotepa', 'busulfan', 'melphalan',
            'carmustine', 'bcnu', 'procarbazine', 'vinblastine',
            'vinorelbine', 'paclitaxel', 'docetaxel', 'doxorubicin',
            'daunorubicin', 'idarubicin', 'mitoxantrone', 'bleomycin',
            'actinomycin', 'everolimus', 'sirolimus', 'sorafenib',
            'sunitinib', 'pazopanib', 'regorafenib', 'lenvatinib'
        ]

        med_lower = medication_name.lower()
        return any(chemo in med_lower for chemo in chemo_keywords)

    def _standardize_medication_name(self, medication_name: str) -> str:
        """Standardize medication name to generic form."""
        if not medication_name or medication_name == 'N/A':
            return 'N/A'

        med_lower = medication_name.lower()

        # Check common medications mapping
        for keyword, standard_name in self.COMMON_MEDICATIONS.items():
            if keyword in med_lower:
                return standard_name

        # Clean up the name
        # Remove dosage information
        cleaned = re.sub(r'\d+\s*mg|\d+\s*mcg|\d+\s*ml', '', medication_name)
        # Remove route information
        cleaned = re.sub(r'\s+(po|iv|im|sq|pr|sl)\s*', ' ', cleaned, flags=re.IGNORECASE)
        # Remove frequency
        cleaned = re.sub(r'\s+(daily|bid|tid|qid|prn|q\d+h)\s*', ' ', cleaned, flags=re.IGNORECASE)

        return cleaned.strip().title()

    def _extract_schedule(self, medication_row: pd.Series) -> str:
        """Extract schedule from medication row."""
        # Check for schedule information in various columns
        schedule_text = ''

        if 'frequency' in medication_row:
            schedule_text = str(medication_row['frequency']).lower()
        elif 'sig' in medication_row:
            schedule_text = str(medication_row['sig']).lower()
        elif 'instructions' in medication_row:
            schedule_text = str(medication_row['instructions']).lower()

        # Map to standardized schedule
        for keyword, schedule in self.SCHEDULE_MAPPING.items():
            if keyword in schedule_text:
                return schedule

        return 'Unknown'

    def _retrieve_documents(
        self,
        patient_id: str,
        event_date: datetime,
        source_type: str
    ) -> List[Dict]:
        """Retrieve medication-related documents."""
        documents = []

        prefix_map = {
            'medication_list': f"{patient_id}/medications/",
            'medication_reconciliation': f"{patient_id}/med_rec/",
            'mar': f"{patient_id}/mar/",
            'pharmacy': f"{patient_id}/pharmacy/"
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
        """Retrieve documents within date range."""
        # For medications, use standard retrieval
        return self._retrieve_documents(patient_id, start_date, source_type)

    def _llm_extract(
        self,
        variable_name: str,
        document: Dict,
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
        """Extract using pattern matching."""
        content = document['content'].lower()

        # Extract medication list
        if 'conmed_' in variable_name and not 'schedule' in variable_name:
            # Look for medication patterns
            medications = []

            for keyword, standard_name in self.COMMON_MEDICATIONS.items():
                if keyword in content and not self._is_chemotherapy(keyword):
                    medications.append(standard_name)

            if medications:
                # Return based on index
                try:
                    index = int(variable_name.split('_')[1]) - 1
                    if index < len(medications):
                        return medications[index], f"Found: {medications[index]}"
                except:
                    pass

        elif 'schedule' in variable_name:
            # Look for schedule patterns
            for keyword, schedule in self.SCHEDULE_MAPPING.items():
                if keyword in content:
                    return schedule, f"Schedule: {schedule}"

        elif variable_name == 'conmed_total':
            # Count medications
            count = 0
            for keyword in self.COMMON_MEDICATIONS.keys():
                if keyword in content and not self._is_chemotherapy(keyword):
                    count += 1

            if count == 0:
                return "None noted", ""
            elif count > 10:
                return "More than 10", f"Found {count} medications"
            else:
                return str(count), f"Found {count} medications"

        return 'N/A', ''

    def _get_fallback_sources(self, variable_name: str) -> List[str]:
        """Get fallback sources."""
        return ['discharge_summary', 'clinic_note', 'nursing_notes']