"""
BRIM CSV Generator Module
==========================

Generate BRIM-compatible CSV files from FHIR data.
"""

import pandas as pd
import csv
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime


class BRIMCSVGenerator:
    """
    Generate BRIM-compatible CSV files with HINT columns.
    
    Creates three required files:
    1. Project CSV - Clinical notes with HINT columns
    2. Variables CSV - Extraction instructions
    3. Decisions CSV - Dependent variable definitions
    """
    
    def __init__(self, fhir_context: Dict[str, Any]):
        """
        Initialize with FHIR context data.
        
        Args:
            fhir_context: Dictionary from FHIRExtractor.extract_patient_context()
        """
        self.fhir_context = fhir_context
    
    @staticmethod
    def sanitize_html(content: str) -> str:
        """
        Remove HTML, JavaScript, CSS from clinical notes.
        
        CRITICAL: Must be done before BRIM processing!
        
        Args:
            content: Raw content (may contain HTML)
            
        Returns:
            Clean text only
        """
        
        if not content:
            return ''
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script, style, meta, link elements
        for element in soup(['script', 'style', 'meta', 'link', 'head']):
            element.decompose()
        
        # Get text and normalize whitespace
        text = soup.get_text(separator=' ', strip=True)
        text = ' '.join(text.split())
        
        return text
    
    def generate_project_csv(
        self, 
        clinical_notes: List[Dict],
        patient_research_id: str,
        output_path: str,
        fhir_extractor=None
    ) -> str:
        """
        Generate BRIM project CSV with enriched HINT columns.
        
        Args:
            clinical_notes: List from FHIRExtractor.discover_clinical_notes()
            patient_research_id: De-identified patient ID
            output_path: Where to save CSV
            fhir_extractor: FHIRExtractor instance for getting Binary content
            
        Returns:
            Path to generated CSV
        """
        
        rows = []
        
        for i, note in enumerate(clinical_notes):
            # Extract Binary content if available
            note_text = ''
            if fhir_extractor and 'binary_url' in note and note['binary_url']:
                # Extract Binary ID from URL
                import re
                match = re.search(r'Binary/([^/]+)', note['binary_url'])
                if match:
                    binary_id = match.group(1)
                    content = fhir_extractor.extract_binary_content(binary_id)
                    if content:
                        note_text = self.sanitize_html(content)
            
            # Fallback to description if no Binary content
            if not note_text and 'description' in note:
                note_text = note.get('description', '')
            
            # Skip if no content
            if not note_text:
                continue
            
            # Generate HINT columns from FHIR context
            document_date = pd.to_datetime(note['document_date'])
            
            surgery_number = fhir_extractor.assign_surgery_number(
                document_date,
                self.fhir_context['surgeries']
            ) if fhir_extractor else 'other'
            
            diagnosis = fhir_extractor.get_relevant_diagnosis(
                document_date,
                self.fhir_context['diagnoses']
            ) if fhir_extractor else ''
            
            who_grade = fhir_extractor.extract_who_grade(diagnosis) if fhir_extractor else ''
            
            active_meds = fhir_extractor.get_active_medications(
                document_date,
                self.fhir_context['medications']
            ) if fhir_extractor else []
            
            row = {
                'NOTE_ID': f"DOC_{i+1:04d}",
                'PERSON_ID': patient_research_id,
                'NOTE_DATETIME': document_date.strftime('%Y-%m-%d %H:%M:%S'),
                'NOTE_TEXT': note_text,
                'NOTE_TITLE': note.get('document_type', 'Unknown'),
                # HINT columns from FHIR
                'HINT_SURGERY_NUMBER': surgery_number,
                'HINT_DIAGNOSIS': diagnosis,
                'HINT_WHO_GRADE': who_grade,
                'HINT_MEDICATIONS': '; '.join(active_meds) if active_meds else '',
            }
            
            rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        # CRITICAL: Use QUOTE_ALL for BRIM compatibility
        df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
        
        print(f"Generated BRIM project CSV: {output_path}")
        print(f"  - {len(df)} documents")
        print(f"  - Date range: {df['NOTE_DATETIME'].min()} to {df['NOTE_DATETIME'].max()}")
        
        return output_path
    
    def generate_variables_csv(
        self,
        clinical_domain: str,
        output_path: str,
        custom_variables: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate BRIM variables CSV.
        
        Args:
            clinical_domain: Domain-specific variables ('neuro_oncology', 'general', etc.)
            output_path: Where to save CSV
            custom_variables: Optional additional variables to include
            
        Returns:
            Path to generated CSV
        """
        
        variables = []
        
        # CRITICAL: surgery_number MUST be first
        variables.append({
            'variable_name': 'surgery_number',
            'instruction': 'Check the HINT_SURGERY_NUMBER field. Return that exact value.',
            'variable_type': 'text',
            'prompt_template': '',
            'can_be_missing': '0',
            'scope': 'one_per_note',
            'option_definitions': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': ''
        })
        
        # Document type classification
        variables.append({
            'variable_name': 'document_type',
            'instruction': 'Classify this document. Return OPERATIVE for operative reports or surgical notes. Return PATHOLOGY for pathology or histology reports. Return RADIOLOGY for radiology or imaging reports. Return OTHER for all other documents.',
            'variable_type': 'text',
            'prompt_template': '',
            'can_be_missing': '0',
            'scope': 'one_per_note',
            'option_definitions': 'OPERATIVE;PATHOLOGY;RADIOLOGY;OTHER',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': ''
        })
        
        # Domain-specific variables
        if clinical_domain == 'neuro_oncology':
            variables.extend(self._get_neuro_oncology_variables())
        
        # Add custom variables if provided
        if custom_variables:
            variables.extend(custom_variables)
        
        # Create DataFrame with exact 11 columns
        df = pd.DataFrame(variables)
        
        # Ensure all required columns exist
        required_columns = [
            'variable_name', 'instruction', 'variable_type', 'prompt_template',
            'can_be_missing', 'scope', 'option_definitions',
            'aggregation_instruction', 'aggregation_prompt_template',
            'aggregation_option_definitions', 'only_use_true_value_in_aggregation'
        ]
        
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Save with proper quoting
        df[required_columns].to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
        
        print(f"Generated BRIM variables CSV: {output_path}")
        print(f"  - {len(df)} variables defined")
        
        return output_path
    
    def _get_neuro_oncology_variables(self) -> List[Dict]:
        """Define neuro-oncology specific variables."""
        
        return [
            {
                'variable_name': 'pathologic_diagnosis',
                'instruction': 'Extract pathologic diagnosis. FIRST check HINT_DIAGNOSIS field. If present and consistent with text, return it. Otherwise extract from text. Look for specific tumor types: pilocytic astrocytoma, glioblastoma, medulloblastoma, ependymoma, etc.',
                'variable_type': 'text',
                'prompt_template': '',
                'can_be_missing': '1',
                'scope': 'many_per_note',
                'option_definitions': '',
                'aggregation_instruction': '',
                'aggregation_prompt_template': '',
                'aggregation_option_definitions': '',
                'only_use_true_value_in_aggregation': ''
            },
            {
                'variable_name': 'who_grade',
                'instruction': 'Extract WHO grade. FIRST check HINT_WHO_GRADE field. If present, validate against text. Return exactly one of: I, II, III, IV. Look for patterns like "WHO Grade I" or "Grade II" in pathology sections.',
                'variable_type': 'text',
                'prompt_template': '',
                'can_be_missing': '1',
                'scope': 'many_per_note',
                'option_definitions': 'I;II;III;IV',
                'aggregation_instruction': '',
                'aggregation_prompt_template': '',
                'aggregation_option_definitions': '',
                'only_use_true_value_in_aggregation': ''
            },
            {
                'variable_name': 'tumor_location',
                'instruction': 'Extract primary tumor location. Look for anatomical locations: cerebellum, frontal lobe, temporal lobe, parietal lobe, occipital lobe, brainstem, thalamus, posterior fossa, pineal region, etc.',
                'variable_type': 'text',
                'prompt_template': '',
                'can_be_missing': '1',
                'scope': 'many_per_note',
                'option_definitions': '',
                'aggregation_instruction': '',
                'aggregation_prompt_template': '',
                'aggregation_option_definitions': '',
                'only_use_true_value_in_aggregation': ''
            },
            {
                'variable_name': 'extent_of_resection_percent',
                'instruction': 'Extract extent of tumor resection as percentage. Use these mappings: GTR/Gross total/Complete = 100. NTR/Near-total = 95. STR/Subtotal = 70. Partial = 50. Biopsy only = 0. Return numeric value 0-100.',
                'variable_type': 'integer',
                'prompt_template': '',
                'can_be_missing': '1',
                'scope': 'one_per_note',
                'option_definitions': '',
                'aggregation_instruction': '',
                'aggregation_prompt_template': '',
                'aggregation_option_definitions': '',
                'only_use_true_value_in_aggregation': ''
            },
            {
                'variable_name': 'hydrocephalus_present',
                'instruction': 'Determine if hydrocephalus is documented. Look for: hydrocephalus, ventriculomegaly, enlarged ventricles, ventricular dilation. Return true if present, false if explicitly absent, leave empty if not mentioned.',
                'variable_type': 'boolean',
                'prompt_template': '',
                'can_be_missing': '1',
                'scope': 'many_per_note',
                'option_definitions': '',
                'aggregation_instruction': '',
                'aggregation_prompt_template': '',
                'aggregation_option_definitions': '',
                'only_use_true_value_in_aggregation': ''
            },
            {
                'variable_name': 'tumor_max_dimension_cm',
                'instruction': 'Extract maximum tumor dimension in centimeters. Look for measurements like "3.5 cm lesion" or "tumor measures 4 x 3 x 2 cm". Return largest dimension as numeric value.',
                'variable_type': 'float',
                'prompt_template': '',
                'can_be_missing': '1',
                'scope': 'many_per_note',
                'option_definitions': '',
                'aggregation_instruction': '',
                'aggregation_prompt_template': '',
                'aggregation_option_definitions': '',
                'only_use_true_value_in_aggregation': ''
            },
        ]
    
    def generate_decisions_csv(
        self,
        output_path: str,
        num_surgeries: int = 2
    ) -> str:
        """
        Generate BRIM decisions CSV for dependent variables.
        
        Args:
            output_path: Where to save CSV
            num_surgeries: Number of surgical events to create aggregations for
            
        Returns:
            Path to generated CSV
        """
        
        decisions = []
        
        # Create surgery-specific aggregations
        base_variables = ['pathologic_diagnosis', 'who_grade', 'tumor_location']
        
        for surgery_num in range(1, num_surgeries + 1):
            for var in base_variables:
                decisions.append({
                    'decision_name': f'{var}_surgery{surgery_num}',
                    'instruction': f'Aggregate all {var} values from documents where surgery_number is "{surgery_num}". If multiple values exist, prioritize those from PATHOLOGY documents, then OPERATIVE, then RADIOLOGY. Return the most specific value.',
                    'decision_type': 'text',
                    'prompt_template': '',
                    'variables': f'{var};surgery_number;document_type'
                })
        
        # Create DataFrame
        df = pd.DataFrame(decisions)
        
        # Ensure all 5 required columns
        required_columns = ['decision_name', 'instruction', 'decision_type', 'prompt_template', 'variables']
        
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        df[required_columns].to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
        
        print(f"Generated BRIM decisions CSV: {output_path}")
        print(f"  - {len(df)} dependent variables defined")
        
        return output_path
    
    def validate_csvs(self, project_csv: str, variables_csv: str, decisions_csv: str) -> Dict[str, Any]:
        """
        Validate generated CSVs meet BRIM requirements.
        
        Args:
            project_csv: Path to project CSV
            variables_csv: Path to variables CSV
            decisions_csv: Path to decisions CSV
            
        Returns:
            Validation report dict
        """
        
        report = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Validate project CSV
        try:
            project_df = pd.read_csv(project_csv)
            
            required_project_cols = ['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE']
            for col in required_project_cols:
                if col not in project_df.columns:
                    report['errors'].append(f"Project CSV missing required column: {col}")
                    report['valid'] = False
            
            if project_df.empty:
                report['warnings'].append("Project CSV has no rows")
        
        except Exception as e:
            report['errors'].append(f"Error reading project CSV: {e}")
            report['valid'] = False
        
        # Validate variables CSV
        try:
            vars_df = pd.read_csv(variables_csv)
            
            if len(vars_df.columns) != 11:
                report['errors'].append(f"Variables CSV has {len(vars_df.columns)} columns, must have exactly 11")
                report['valid'] = False
            
            if vars_df.iloc[0]['variable_name'] != 'surgery_number':
                report['errors'].append("First variable must be 'surgery_number'")
                report['valid'] = False
            
            valid_scopes = ['one_per_note', 'many_per_note', 'one_per_patient']
            invalid_scopes = vars_df[~vars_df['scope'].isin(valid_scopes)]
            if not invalid_scopes.empty:
                report['errors'].append(f"Invalid scope values: {invalid_scopes['variable_name'].tolist()}")
                report['valid'] = False
        
        except Exception as e:
            report['errors'].append(f"Error reading variables CSV: {e}")
            report['valid'] = False
        
        # Validate decisions CSV
        try:
            dec_df = pd.read_csv(decisions_csv)
            
            if len(dec_df.columns) != 5:
                report['errors'].append(f"Decisions CSV has {len(dec_df.columns)} columns, must have exactly 5")
                report['valid'] = False
        
        except Exception as e:
            report['errors'].append(f"Error reading decisions CSV: {e}")
            report['valid'] = False
        
        return report
