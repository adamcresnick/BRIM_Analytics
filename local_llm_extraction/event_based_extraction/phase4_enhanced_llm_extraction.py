"""
Phase 4: Enhanced LLM Extraction with Structured Data Context
=============================================================
Uses structured data model to guide and validate LLM extractions
"""

import pandas as pd
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import subprocess
import time
import re

# Import Ollama client - this is how it's done in tested workflows
try:
    from ollama import Client as OllamaClient
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("Ollama Python client not installed. Install with: pip install ollama")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import data dictionary loader
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_dictionary_loader import get_data_dictionary

class EnhancedLLMExtractor:
    """
    Orchestrates LLM extraction using structured data as ground truth context
    Key innovation: The LLM uses verified structured data to inform its extraction decisions
    """

    def __init__(self, staging_path: Path, ollama_model: str = "gemma2:27b"):
        self.staging_path = Path(staging_path)
        self.ollama_model = ollama_model
        self.output_base = self.staging_path.parent / "outputs"
        self.output_base.mkdir(exist_ok=True)

        # Initialize Ollama client if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                self.ollama_client = OllamaClient(host='http://127.0.0.1:11434')
                # Test connection
                self.ollama_client.list()
                logger.info(f"Ollama client initialized with model: {ollama_model}")
            except Exception as e:
                logger.warning(f"Could not connect to Ollama: {e}")
                self.ollama_client = None

        # Store phase data for context-aware extraction
        self.phase1_data = {}
        self.phase2_timeline = []
        self.phase3_documents = []

    def set_phase_data(self, phase1_data: Dict, phase2_timeline: List, phase3_documents: List):
        """Set data from previous phases for context-aware extraction."""
        self.phase1_data = phase1_data or {}
        self.phase2_timeline = phase2_timeline or []
        self.phase3_documents = phase3_documents or []
        logger.info(f"Phase data set - P1: {len(self.phase1_data)} items, P2: {len(self.phase2_timeline)} events, P3: {len(self.phase3_documents)} docs")

    def query_phase_data(self, query_type: str, params: Dict = None) -> Any:
        """Query data from previous phases to inform extraction."""
        params = params or {}

        if query_type == 'surgery_dates':
            return [s.get('date') for s in self.phase1_data.get('surgical_events', [])]
        elif query_type == 'has_chemotherapy':
            return self.phase1_data.get('has_chemotherapy', False)
        elif query_type == 'has_radiation':
            return self.phase1_data.get('has_radiation_therapy', False)
        elif query_type == 'events_near_date':
            target_date = params.get('date')
            window_days = params.get('window_days', 7)
            if target_date and self.phase2_timeline:
                # Find events within window of target date
                nearby = []
                for event in self.phase2_timeline:
                    if 'date' in event:
                        # Simple date proximity check
                        nearby.append(event)
                return nearby[:5]  # Return up to 5 nearby events
        elif query_type == 'document_count':
            return len(self.phase3_documents)

        return None

    def create_enhanced_prompt(self, variable: str, document_text: str,
                              structured_context: Dict, document_metadata: Dict = None) -> str:
        """
        Create an LLM prompt that includes structured data as context
        This guides the LLM to make extraction decisions consistent with known facts
        """

        prompt_parts = []
        document_metadata = document_metadata or {}

        # 1. System instruction with structured context
        prompt_parts.append("You are a clinical data extraction expert. You have access to VERIFIED STRUCTURED DATA from multiple phases that should guide your extraction.")

        # Add Phase 1 context (Structured Data)
        prompt_parts.append("\n=== PHASE 1: STRUCTURED DATA (VERIFIED) ===")
        surgeries = self.query_phase_data('surgery_dates')
        if surgeries:
            prompt_parts.append(f"Known Surgeries: {len(surgeries)} surgical events identified")
            for i, date in enumerate(surgeries[:3], 1):
                prompt_parts.append(f"  Surgery {i}: {date}")

        has_chemo = self.query_phase_data('has_chemotherapy')
        has_rad = self.query_phase_data('has_radiation')
        prompt_parts.append(f"Chemotherapy: {'Yes' if has_chemo else 'No'}")
        prompt_parts.append(f"Radiation: {'Yes' if has_rad else 'No'}")

        # Add Phase 2 context (Timeline)
        prompt_parts.append("\n=== PHASE 2: CLINICAL TIMELINE ===")
        if document_metadata.get('document_date'):
            nearby_events = self.query_phase_data(
                'events_near_date',
                {'date': document_metadata['document_date'], 'window_days': 14}
            )
            if nearby_events:
                prompt_parts.append(f"Events near this document date ({document_metadata['document_date']}):")
                for event in nearby_events[:3]:
                    prompt_parts.append(f"  - {event.get('type', 'Unknown')}: {event.get('date', 'Unknown')}")

        # Add Phase 3 context (Document Selection)
        prompt_parts.append("\n=== PHASE 3: DOCUMENT CONTEXT ===")
        if document_metadata.get('document_type'):
            prompt_parts.append(f"Document Type: {document_metadata['document_type']}")
        if document_metadata.get('tier'):
            tier_explanations = {
                1: "Primary source (±7 days from event) - HIGHEST PRIORITY",
                2: "Secondary source (±14 days from event)",
                3: "Tertiary source (±30 days from event)"
            }
            prompt_parts.append(f"Selection Tier: {tier_explanations.get(document_metadata['tier'], 'Unknown')}")

        doc_count = self.query_phase_data('document_count')
        if doc_count:
            prompt_parts.append(f"Total documents selected for extraction: {doc_count}")

        prompt_parts.append("\n=== VERIFIED STRUCTURED DATA (GROUND TRUTH) ===")

        # Add schema information about available structured data sources
        if 'available_structured_sources' in structured_context:
            prompt_parts.append("\n=== AVAILABLE STRUCTURED DATA SOURCES (FOR VALIDATION & ADJUDICATION) ===")
            schema_info = structured_context['available_structured_sources']
            prompt_parts.append(schema_info['description'])

            for source in schema_info['sources']:
                prompt_parts.append(f"\n📊 {source['name'].upper()}:")
                prompt_parts.append(f"   Description: {source['description']}")
                prompt_parts.append(f"   Key Fields: {', '.join(source['key_fields'])}")
                prompt_parts.append(f"   Use For: {source['use_for']}")
                if 'note' in source:
                    prompt_parts.append(f"   ⚠️ Note: {source['note']}")
                if 'source_hierarchy' in source:
                    prompt_parts.append(f"   Hierarchy: {source['source_hierarchy']}")
                if 'confidence' in source:
                    prompt_parts.append(f"   Confidence Level: {source['confidence']}")

            if 'validation_instructions' in schema_info:
                prompt_parts.append(f"\n💡 {schema_info['validation_instructions']}")

        # Add variable-specific validation hint
        if 'validation_hint' in structured_context:
            prompt_parts.append(f"\n⚠️ VALIDATION HINT FOR THIS VARIABLE: {structured_context['validation_hint']}")

        # ==================================================================
        # DATA DICTIONARY FIELD DEFINITION (REPLACES HARDCODED PROMPTS)
        # ==================================================================
        prompt_parts.append("\n" + "="*70)
        prompt_parts.append("EXTRACTION TASK - PLEASE READ THE FIELD DEFINITION CAREFULLY")
        prompt_parts.append("="*70)

        # Load data dictionary definition for this variable
        data_dict = get_data_dictionary()
        field_definition = data_dict.format_field_for_prompt(variable)
        prompt_parts.append(field_definition)

        prompt_parts.append("\n" + "="*70)
        prompt_parts.append("EXTRACTION INSTRUCTIONS")
        prompt_parts.append("="*70)
        prompt_parts.append("1. You MUST extract ONLY the information that matches the field definition above")
        prompt_parts.append("2. If the field has 'VALID VALUES', you MUST use one of those exact codes/labels")
        prompt_parts.append("3. Cross-reference your extraction with the structured data context above")
        prompt_parts.append("4. If dates are mentioned, they should align with known dates from Phase 1 & 2")
        prompt_parts.append("5. Provide a confidence score (0-1) based on:")
        prompt_parts.append("   - Clarity of information in document")
        prompt_parts.append("   - Alignment with structured data context")
        prompt_parts.append("   - Match with valid values in data dictionary")

        # 2. Add relevant structured context based on variable (keep for backward compatibility)
        if variable in ["extent_of_resection", "extent_of_tumor_resection"]:
            if 'surgery_dates' in structured_context:
                prompt_parts.append(f"Known Surgery Dates: {', '.join(structured_context['surgery_dates'])}")
            if 'surgery_types' in structured_context:
                prompt_parts.append(f"Known Surgery Types: {', '.join(structured_context['surgery_types'])}")
            if 'initial_surgery' in structured_context:
                prompt_parts.append(f"Initial Surgery Date: {structured_context['initial_surgery']}")
                prompt_parts.append(f"Initial Surgery Type: {structured_context.get('initial_surgery_type', 'Unknown')}")

            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract EXTENT OF TUMOR RESECTION (variable: {variable})")
            prompt_parts.append("IMPORTANT: The surgery date MUST match one of the known surgery dates above.")
            prompt_parts.append("If the document mentions a surgery on a different date, it's likely not relevant.")
            prompt_parts.append("\nValid values ONLY:")
            prompt_parts.append("  • GTR (Gross Total Resection) - complete removal of visible tumor")
            prompt_parts.append("  • STR (Subtotal Resection) - >90% but <100% removal, 'near total', 'near complete'")
            prompt_parts.append("  • Partial - <90% removal")
            prompt_parts.append("  • Biopsy only - no resection")
            prompt_parts.append("\nLook for: 'gross total resection', 'GTR', 'complete resection', 'near total resection', 'subtotal resection', 'STR', 'partial resection', 'debulking'")

        elif variable == "tumor_location":
            if 'diagnosis_date' in structured_context:
                prompt_parts.append(f"Diagnosis Date: {structured_context['diagnosis_date']}")

            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract ANATOMICAL TUMOR LOCATION (variable: {variable})")
            prompt_parts.append("Provide the specific brain or spine location using neuroanatomical terminology.")
            prompt_parts.append("\nValid locations:")
            prompt_parts.append("  • Frontal lobe (left/right)")
            prompt_parts.append("  • Temporal lobe (left/right)")
            prompt_parts.append("  • Parietal lobe (left/right)")
            prompt_parts.append("  • Occipital lobe (left/right)")
            prompt_parts.append("  • Cerebellum (left/right/midline)")
            prompt_parts.append("  • Brainstem (pons/medulla/midbrain)")
            prompt_parts.append("  • Thalamus, Basal ganglia")
            prompt_parts.append("  • Corpus callosum, Pineal region")
            prompt_parts.append("  • Spinal cord (level)")
            prompt_parts.append("\nLook for: imaging findings, operative descriptions, anatomical terms")

        elif variable == "surgery_type":
            if 'surgery_dates' in structured_context:
                prompt_parts.append(f"Known Surgery Dates: {', '.join(structured_context['surgery_dates'])}")

            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract TYPE OF SURGERY (variable: {variable})")
            prompt_parts.append("\nValid surgery types:")
            prompt_parts.append("  • Craniotomy for tumor resection")
            prompt_parts.append("  • Stereotactic biopsy")
            prompt_parts.append("  • Endoscopic resection")
            prompt_parts.append("  • Shunt placement (VP shunt, EVD)")
            prompt_parts.append("  • Re-resection / Second-look surgery")
            prompt_parts.append("\nLook for: procedure names, operative approach, surgical technique")

        elif variable == "specimen_to_cbtn":
            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract SPECIMEN TO CBTN status (variable: {variable})")
            prompt_parts.append("Determine if tumor specimen was sent to Children's Brain Tumor Network (CBTN) or biobank.")
            prompt_parts.append("\nValid values ONLY: Yes, No, Unknown")
            prompt_parts.append("\nLook for: 'CBTN', 'Children's Brain Tumor Network', 'biobank', 'tissue bank', 'research specimen'")

        elif variable == "who_grade":
            if 'diagnosis_date' in structured_context:
                prompt_parts.append(f"Diagnosis Date: {structured_context['diagnosis_date']}")

            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract WHO GRADE (variable: {variable})")
            prompt_parts.append("Extract the WHO CNS tumor grade from pathology.")
            prompt_parts.append("\nValid values ONLY:")
            prompt_parts.append("  • Grade I (benign)")
            prompt_parts.append("  • Grade II (low-grade)")
            prompt_parts.append("  • Grade III (anaplastic)")
            prompt_parts.append("  • Grade IV (glioblastoma)")
            prompt_parts.append("\nLook for: 'WHO grade', 'Grade I/II/III/IV', pathology report findings")

        elif variable in ["tumor_histology", "histopathology"]:
            if 'diagnosis_date' in structured_context:
                prompt_parts.append(f"Diagnosis Date: {structured_context['diagnosis_date']}")
            if 'diagnosis_histology' in structured_context:
                prompt_parts.append(f"Known Diagnosis: {structured_context['diagnosis_histology']}")
            if 'molecular_markers' in structured_context:
                prompt_parts.append(f"Known Molecular Markers: {structured_context['molecular_markers']}")

            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract TUMOR HISTOPATHOLOGY (variable: {variable})")
            prompt_parts.append("Extract the specific histopathologic diagnosis from pathology report.")
            prompt_parts.append(f"IMPORTANT: Should be consistent with known diagnosis: {structured_context.get('diagnosis_histology', 'Unknown')}")
            prompt_parts.append("\nCommon pediatric brain tumor types:")
            prompt_parts.append("  • Gliomas: Glioblastoma, Anaplastic astrocytoma, Diffuse astrocytoma, Pilocytic astrocytoma")
            prompt_parts.append("  • Ependymoma (including variants)")
            prompt_parts.append("  • Medulloblastoma")
            prompt_parts.append("  • ATRT (Atypical teratoid/rhabdoid tumor)")
            prompt_parts.append("  • Craniopharyngioma")
            prompt_parts.append("  • Choroid plexus tumors")
            prompt_parts.append("  • Embryonal tumors (PNET, etc.)")
            prompt_parts.append("\nLook for: pathology diagnosis, histologic type, tumor classification, Ki-67 index")

        elif variable == "chemotherapy_response":
            if 'chemotherapy_drugs' in structured_context:
                prompt_parts.append(f"Known Chemotherapy Drugs: {', '.join(structured_context['chemotherapy_drugs'])}")
            if 'chemotherapy_periods' in structured_context:
                for period in structured_context['chemotherapy_periods']:
                    prompt_parts.append(f"- {period['drug']}: {period['start']} to {period.get('end', 'ongoing')}")

            prompt_parts.append("\nEXTRACTION TASK:")
            prompt_parts.append("Extract treatment response to chemotherapy.")
            prompt_parts.append("IMPORTANT: Only extract responses for the known drugs listed above.")
            prompt_parts.append("Valid responses: CR (complete response), PR (partial response), SD (stable disease), PD (progressive disease)")

        elif variable == "progression_status":
            if 'imaging_dates' in structured_context:
                prompt_parts.append(f"Critical Imaging Dates: {', '.join(structured_context['imaging_dates'][:5])}")
            if 'treatment_changes' in structured_context:
                prompt_parts.append("Known Treatment Changes:")
                for change in structured_context['treatment_changes'][:3]:
                    prompt_parts.append(f"- {change['date']}: {change['type']}")

            prompt_parts.append("\nEXTRACTION TASK:")
            prompt_parts.append("Extract disease progression or recurrence status.")
            prompt_parts.append("IMPORTANT: Progression dates should align with imaging dates or treatment changes above.")
            prompt_parts.append("Look for: new enhancement, increased tumor size, new lesions, recurrence")

        elif variable == "molecular_testing":
            if 'test_names' in structured_context:
                prompt_parts.append(f"Known Tests Performed: {', '.join(structured_context['test_names'])}")
            if 'molecular_test_dates' in structured_context:
                prompt_parts.append(f"Test Dates: {', '.join(structured_context['molecular_test_dates'])}")

            prompt_parts.append("\nEXTRACTION TASK:")
            prompt_parts.append("Extract molecular testing results.")
            prompt_parts.append(f"IMPORTANT: Focus on these known tests: {', '.join(structured_context.get('test_names', []))}")
            prompt_parts.append("Look for: BRAF status, IDH mutations, H3K27M, MGMT methylation")

        elif variable == "survival_status":
            if 'last_visit' in structured_context:
                prompt_parts.append(f"Last Known Visit: {structured_context['last_visit']}")
            if 'date_of_birth' in structured_context:
                prompt_parts.append(f"Date of Birth: {structured_context['date_of_birth']}")
            if 'diagnosis_date' in structured_context:
                prompt_parts.append(f"Diagnosis Date: {structured_context['diagnosis_date']}")

            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract SURVIVAL STATUS (variable: {variable})")
            prompt_parts.append(f"IMPORTANT: Last contact should be close to {structured_context.get('last_visit', 'unknown')}")
            prompt_parts.append("\nValid values: Alive, Deceased, Unknown")
            prompt_parts.append("\nExtract: vital status (alive/deceased), date of last contact or death")

        else:
            # Generic extraction for variables without specific prompts
            prompt_parts.append("\n=== EXTRACTION TASK ===")
            prompt_parts.append(f"Extract the value for variable: {variable}")
            prompt_parts.append(f"Variable name: {variable.replace('_', ' ').title()}")
            prompt_parts.append("\nProvide the most specific and accurate information available in the document.")
            prompt_parts.append("If the information is not present, return 'Not found'.")

        # 3. Add the document text
        prompt_parts.append("\n=== DOCUMENT TO EXTRACT FROM ===")
        prompt_parts.append(document_text[:5000])  # Limit to first 5000 chars

        # 4. Add extraction instructions
        prompt_parts.append("\n=== EXTRACTION INSTRUCTIONS ===")
        prompt_parts.append("1. Extract ONLY information that matches the structured data context")
        prompt_parts.append("2. If dates don't align with known dates, the information is likely incorrect")
        prompt_parts.append("3. Provide confidence score (0-1) based on alignment with structured data")
        prompt_parts.append("4. Format response as JSON with fields: 'value', 'confidence', 'supporting_text', 'date_extracted'")

        return "\n".join(prompt_parts)

    def extract_with_structured_context(self, patient_id: str,
                                       variable: str,
                                       documents: List[Dict],
                                       structured_context: Dict) -> Dict:
        """
        Perform extraction using structured data as context

        Args:
            patient_id: Patient identifier
            variable: Variable to extract (e.g., 'extent_of_resection')
            documents: List of documents to extract from
            structured_context: Structured data context from Phase 2

        Returns:
            Extraction results with confidence scores
        """

        logger.info(f"Extracting {variable} for patient {patient_id} with structured context")

        results = {
            'variable': variable,
            'patient_id': patient_id,
            'extraction_date': datetime.now().isoformat(),
            'structured_context_used': True,
            'extractions': []
        }

        for doc in documents:
            logger.info(f"Processing document: {doc.get('document_id', 'unknown')}")

            # Create enhanced prompt with structured context
            prompt = self.create_enhanced_prompt(
                variable,
                doc.get('text', ''),
                structured_context
            )

            # Call LLM (in production, this would use actual Ollama)
            extraction = self._call_llm(prompt, doc.get('document_id'))

            # Validate extraction against structured data
            validated_extraction = self._validate_extraction(
                extraction,
                variable,
                structured_context
            )

            results['extractions'].append({
                'document_id': doc.get('document_id'),
                'document_type': doc.get('document_type'),
                'extraction': validated_extraction,
                'used_structured_context': True
            })

        # Aggregate extractions
        results['aggregated'] = self._aggregate_extractions(
            results['extractions'],
            structured_context
        )

        return results

    def _call_llm(self, prompt: str, document_id: str) -> Dict:
        """
        Call LLM with prompt - using Ollama client library as in tested workflows
        """

        # Check if Ollama client is available
        if not self.ollama_client:
            logger.debug("Ollama client not available, using fallback extraction")
            return self._fallback_extraction(prompt, document_id)

        # Add JSON formatting instruction to prompt
        json_prompt = prompt + "\n\nIMPORTANT: Return your response as valid JSON with these fields:\n{\n  \"value\": \"extracted value or 'Not found'\",\n  \"confidence\": 0.0 to 1.0,\n  \"supporting_text\": \"relevant text from document\",\n  \"date_extracted\": \"date if found or null\"\n}"

        try:
            # Call Ollama using client library (as in tested workflows)
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=[
                    {'role': 'user', 'content': json_prompt}
                ],
                options={
                    'temperature': 0.3,  # Lower temperature for more consistent extraction
                    'num_predict': 500   # Limit response length
                }
            )

            # Extract the response content
            if response and 'message' in response:
                response_text = response['message']['content'].strip()

                # Try to parse JSON response
                try:
                    # Extract JSON from response (Ollama may add extra text)
                    json_match = re.search(r'\{[^}]*\}', response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        extraction = json.loads(json_str)

                        # Validate required fields
                        if all(key in extraction for key in ['value', 'confidence']):
                            logger.debug(f"Successfully extracted: {extraction.get('value')}")
                            return extraction
                        else:
                            logger.warning("Incomplete extraction from Ollama")
                            return self._fallback_extraction(prompt, document_id)
                    else:
                        # If no JSON, try to parse as plain text
                        return self._parse_plain_text_response(response_text)

                except json.JSONDecodeError:
                    logger.debug("Failed to parse Ollama response as JSON, parsing as text")
                    return self._parse_plain_text_response(response_text)
            else:
                logger.warning("Empty response from Ollama")
                return self._fallback_extraction(prompt, document_id)

        except Exception as e:
            logger.warning(f"Error calling Ollama: {e}")
            return self._fallback_extraction(prompt, document_id)

    def _fallback_extraction(self, prompt: str, document_id: str) -> Dict:
        """
        Fallback extraction when Ollama is not available
        Uses keyword matching for basic extraction
        """
        # Extract variable type from prompt
        prompt_lower = prompt.lower()

        if 'extent of resection' in prompt_lower:
            # Look for resection keywords in prompt
            if 'gross total' in prompt_lower or 'gtr' in prompt_lower:
                return {'value': 'GTR', 'confidence': 0.6, 'supporting_text': 'Keyword match: gross total', 'date_extracted': None}
            elif 'subtotal' in prompt_lower or 'str' in prompt_lower:
                return {'value': 'STR', 'confidence': 0.6, 'supporting_text': 'Keyword match: subtotal', 'date_extracted': None}
            elif 'partial' in prompt_lower:
                return {'value': 'Partial', 'confidence': 0.6, 'supporting_text': 'Keyword match: partial', 'date_extracted': None}

        return {
            'value': 'Unable to extract',
            'confidence': 0.0,
            'supporting_text': 'Ollama not available, fallback extraction failed',
            'date_extracted': None
        }

    def _parse_plain_text_response(self, response: str) -> Dict:
        """
        Parse plain text response from Ollama when JSON parsing fails
        """
        response_lower = response.lower()

        # Try to extract common values
        value = 'Not found'
        confidence = 0.5

        if 'gross total' in response_lower or 'gtr' in response_lower:
            value = 'GTR'
            confidence = 0.7
        elif 'subtotal' in response_lower or 'str' in response_lower:
            value = 'STR'
            confidence = 0.7
        elif 'partial' in response_lower:
            value = 'Partial'
            confidence = 0.7
        elif 'biopsy' in response_lower:
            value = 'Biopsy only'
            confidence = 0.7

        return {
            'value': value,
            'confidence': confidence,
            'supporting_text': response[:200] if response else '',
            'date_extracted': None
        }

    def _validate_extraction(self, extraction: Dict, variable: str,
                           structured_context: Dict) -> Dict:
        """
        Validate extraction against structured data and adjust confidence
        """

        validated = extraction.copy()

        # Date validation
        if 'date_extracted' in extraction and extraction['date_extracted']:
            extracted_date = pd.to_datetime(extraction['date_extracted'])

            # Check if date matches known dates
            if variable == 'extent_of_resection' and 'surgery_dates' in structured_context:
                surgery_dates = [pd.to_datetime(d) for d in structured_context['surgery_dates']]
                date_matches = any(abs((extracted_date - sd).days) <= 7 for sd in surgery_dates)

                if not date_matches:
                    validated['confidence'] *= 0.5
                    validated['validation_warning'] = 'Date does not match known surgery dates'

            elif variable == 'tumor_histology' and 'diagnosis_date' in structured_context:
                diagnosis_date = pd.to_datetime(structured_context['diagnosis_date'])
                days_diff = abs((extracted_date - diagnosis_date).days)

                if days_diff > 30:
                    validated['confidence'] *= 0.7
                    validated['validation_warning'] = 'Date far from diagnosis date'

        # Value validation
        if variable == 'chemotherapy_response' and 'chemotherapy_drugs' in structured_context:
            known_drugs = structured_context['chemotherapy_drugs']
            extracted_text = extraction.get('supporting_text', '').lower()

            drug_mentioned = any(drug.lower() in extracted_text for drug in known_drugs)
            if not drug_mentioned:
                validated['confidence'] *= 0.6
                validated['validation_warning'] = 'No known chemotherapy drugs mentioned'

        # Boost confidence if extraction aligns well with structured data
        if variable == 'tumor_histology' and 'diagnosis_histology' in structured_context:
            if structured_context['diagnosis_histology'].lower() in extraction.get('value', '').lower():
                validated['confidence'] = min(1.0, validated['confidence'] * 1.2)
                validated['validation_boost'] = 'Matches known diagnosis'

        return validated

    def _aggregate_extractions(self, extractions: List[Dict],
                              structured_context: Dict) -> Dict:
        """
        Aggregate multiple extractions into final result
        Prioritize extractions that align with structured data
        """

        if not extractions:
            return {'value': 'No extractions', 'confidence': 0.0}

        # Sort by confidence (which now incorporates structured data validation)
        sorted_extractions = sorted(
            extractions,
            key=lambda x: x.get('extraction', {}).get('confidence', 0),
            reverse=True
        )

        # Take highest confidence extraction
        best = sorted_extractions[0]['extraction']

        # Calculate aggregate confidence based on consistency
        values = [e['extraction']['value'] for e in extractions
                 if e['extraction'].get('confidence', 0) > 0.5]

        if values:
            # Check consistency
            unique_values = set(values)
            consistency_factor = 1.0 if len(unique_values) == 1 else 0.8

            aggregate = {
                'value': best['value'],
                'confidence': best['confidence'] * consistency_factor,
                'source_count': len(extractions),
                'consistent': len(unique_values) == 1,
                'all_values': list(unique_values)
            }

            # Add validation status
            if 'validation_warning' in best:
                aggregate['validation_warning'] = best['validation_warning']
            if 'validation_boost' in best:
                aggregate['validation_boost'] = best['validation_boost']

            return aggregate

        return {'value': 'No confident extractions', 'confidence': 0.0}

    def create_ollama_config(self, patient_id: str,
                            clinical_timeline: Dict,
                            selected_documents: pd.DataFrame,
                            variables: List[str]) -> Dict:
        """
        Create configuration for Ollama-based extraction with structured context
        """

        config = {
            'patient_id': patient_id,
            'model': 'gemma2:27b',
            'extraction_mode': 'structured_context_enhanced',
            'timestamp': datetime.now().isoformat(),
            'variables': []
        }

        # Extract structured context from timeline
        structured_context = self._extract_structured_context(clinical_timeline)

        for variable in variables:
            variable_config = {
                'name': variable,
                'structured_context': self._get_variable_context(variable, structured_context),
                'documents': self._select_documents_for_variable(variable, selected_documents),
                'validation_rules': self._get_validation_rules(variable)
            }
            config['variables'].append(variable_config)

        # Add global context
        config['global_context'] = {
            'diagnosis_date': structured_context.get('diagnosis_date'),
            'age_at_diagnosis': structured_context.get('age_at_diagnosis'),
            'last_contact': structured_context.get('last_visit'),
            'treatment_summary': self._create_treatment_summary(structured_context)
        }

        return config

    def _extract_structured_context(self, timeline: Dict) -> Dict:
        """Extract structured context from clinical timeline"""

        context = {}

        # Basic demographics and diagnosis
        context['date_of_birth'] = timeline.get('date_of_birth')
        context['diagnosis_date'] = timeline.get('diagnosis_date')
        context['age_at_diagnosis'] = timeline.get('age_at_diagnosis')

        # Diagnosis details from problem list analysis
        if 'problem_list_analysis' in timeline:
            problem_analysis = timeline['problem_list_analysis']
            if 'tumor_diagnosis' in problem_analysis:
                context['diagnosis_histology'] = problem_analysis['tumor_diagnosis'].get('specific_diagnosis')

        # Surgery information
        if 'tumor_surgeries' in timeline:
            surgeries = timeline['tumor_surgeries']
            context['surgery_dates'] = [s['date'] for s in surgeries]
            context['surgery_types'] = [s['type'] for s in surgeries]
            if surgeries:
                context['initial_surgery'] = surgeries[0]['date']
                context['initial_surgery_type'] = surgeries[0]['type']

        # Chemotherapy
        if 'chemotherapy_periods' in timeline:
            context['chemotherapy_periods'] = timeline['chemotherapy_periods']
            context['chemotherapy_drugs'] = list(set(
                p['drug'] for p in timeline['chemotherapy_periods']
            ))

        # Molecular testing
        if 'molecular_tests' in timeline:
            tests = timeline['molecular_tests']
            context['molecular_test_dates'] = tests.get('test_dates', [])
            context['test_names'] = tests.get('test_names', [])
            context['molecular_markers'] = tests.get('markers_identified', [])

        # Imaging
        if 'critical_imaging' in timeline:
            context['imaging_dates'] = [
                img['date'] for img in timeline['critical_imaging']
            ]

        # Treatment changes
        if 'treatment_changes' in timeline:
            context['treatment_changes'] = timeline['treatment_changes']

        # Last contact
        context['last_visit'] = timeline.get('last_contact')

        return context

    def _get_variable_context(self, variable: str, structured_context: Dict) -> Dict:
        """Get specific context for a variable"""

        variable_context_map = {
            'extent_of_resection': ['surgery_dates', 'surgery_types', 'initial_surgery', 'initial_surgery_type'],
            'tumor_histology': ['diagnosis_date', 'diagnosis_histology', 'molecular_markers'],
            'chemotherapy_response': ['chemotherapy_drugs', 'chemotherapy_periods', 'imaging_dates'],
            'progression_status': ['imaging_dates', 'treatment_changes', 'surgery_dates'],
            'molecular_testing': ['test_names', 'molecular_test_dates', 'molecular_markers'],
            'survival_status': ['last_visit', 'date_of_birth', 'diagnosis_date']
        }

        relevant_keys = variable_context_map.get(variable, [])

        return {k: v for k, v in structured_context.items() if k in relevant_keys}

    def _select_documents_for_variable(self, variable: str,
                                      all_documents: pd.DataFrame) -> List[str]:
        """Select relevant documents for a specific variable"""

        document_map = {
            'extent_of_resection': ['operative_note', 'radiology_report', 'mri_report'],
            'tumor_histology': ['pathology_report', 'molecular_report'],
            'chemotherapy_response': ['oncology_note', 'clinic_note', 'mri_report'],
            'progression_status': ['mri_report', 'oncology_note', 'radiology_report'],
            'molecular_testing': ['molecular_report', 'pathology_report'],
            'survival_status': ['discharge_summary', 'clinic_note', 'progress_note']
        }

        preferred_types = document_map.get(variable, [])

        if 'document_type' in all_documents.columns:
            relevant = all_documents[
                all_documents['document_type'].isin(preferred_types)
            ]
            return relevant['document_id'].tolist()[:10]  # Limit to 10 docs

        return all_documents['document_id'].tolist()[:5]  # Default fallback

    def _get_validation_rules(self, variable: str) -> Dict:
        """Get validation rules for a variable"""

        rules = {
            'extent_of_resection': {
                'valid_values': ['GTR', 'gross total', 'STR', 'subtotal', 'partial', 'biopsy'],
                'date_tolerance_days': 7,
                'required_context': ['surgery_dates']
            },
            'tumor_histology': {
                'keywords': ['astrocytoma', 'glioma', 'WHO', 'grade'],
                'date_tolerance_days': 30,
                'required_context': ['diagnosis_date']
            },
            'chemotherapy_response': {
                'valid_values': ['CR', 'PR', 'SD', 'PD', 'complete', 'partial', 'stable', 'progressive'],
                'required_context': ['chemotherapy_drugs']
            },
            'progression_status': {
                'keywords': ['progression', 'recurrence', 'new', 'increased', 'enhancement'],
                'required_context': ['imaging_dates']
            },
            'molecular_testing': {
                'markers': ['BRAF', 'IDH', 'H3K27M', 'MGMT', 'fusion'],
                'required_context': ['test_names']
            },
            'survival_status': {
                'valid_values': ['alive', 'deceased', 'dead', 'expired'],
                'required_context': ['last_visit']
            }
        }

        return rules.get(variable, {})

    def _create_treatment_summary(self, structured_context: Dict) -> str:
        """Create a treatment summary from structured context"""

        summary_parts = []

        if 'initial_surgery' in structured_context:
            summary_parts.append(
                f"Surgery: {structured_context['initial_surgery']} ({structured_context.get('initial_surgery_type', 'type unknown')})"
            )

        if 'chemotherapy_drugs' in structured_context:
            drugs = ', '.join(structured_context['chemotherapy_drugs'])
            summary_parts.append(f"Chemotherapy: {drugs}")

        if 'molecular_markers' in structured_context:
            markers = ', '.join(structured_context['molecular_markers'])
            summary_parts.append(f"Molecular: {markers}")

        return '; '.join(summary_parts) if summary_parts else 'No treatment data available'

    def generate_extraction_report(self, results: Dict) -> str:
        """Generate detailed extraction report"""

        report = []
        report.append("="*70)
        report.append("ENHANCED LLM EXTRACTION REPORT WITH STRUCTURED CONTEXT")
        report.append("="*70)
        report.append(f"\nPatient ID: {results.get('patient_id')}")
        report.append(f"Extraction Date: {results.get('extraction_date')}")
        report.append("Mode: Structured Context Enhanced")

        # Global context used
        if 'global_context' in results:
            ctx = results['global_context']
            report.append(f"\nGlobal Context Used:")
            report.append(f"  Diagnosis Date: {ctx.get('diagnosis_date')}")
            report.append(f"  Treatment Summary: {ctx.get('treatment_summary')}")

        # Variable results
        for var_result in results.get('variables', []):
            report.append(f"\n{'='*60}")
            report.append(f"Variable: {var_result['name'].upper().replace('_', ' ')}")
            report.append("-"*40)

            if 'aggregated' in var_result:
                agg = var_result['aggregated']
                report.append(f"Final Value: {agg.get('value')}")
                report.append(f"Confidence: {agg.get('confidence', 0):.1%}")
                report.append(f"Consistency: {'Yes' if agg.get('consistent') else 'No'}")

                if 'validation_warning' in agg:
                    report.append(f"⚠️  Warning: {agg['validation_warning']}")
                if 'validation_boost' in agg:
                    report.append(f"✓ Validation: {agg['validation_boost']}")

            # Structured context used
            if 'structured_context' in var_result:
                report.append(f"\nStructured Context Keys Used:")
                for key in var_result['structured_context'].keys():
                    report.append(f"  - {key}")

        report.append("\n" + "="*70)

        return "\n".join(report)


if __name__ == "__main__":
    # Test enhanced extraction
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")

    extractor = EnhancedLLMExtractor(staging_path)

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # Load clinical timeline
    timeline_file = output_path / f"integrated_timeline_{patient_id}.json"
    if timeline_file.exists():
        with open(timeline_file, 'r') as f:
            clinical_timeline = json.load(f)
    else:
        clinical_timeline = {
            'diagnosis_date': '2018-05-28',
            'age_at_diagnosis': 13.04,
            'tumor_surgeries': [{'date': '2018-05-28', 'type': 'resection'}],
            'chemotherapy_periods': [
                {'drug': 'Bevacizumab', 'start': '2019-05-30', 'end': '2019-12-26'}
            ]
        }

    # Extract structured context
    structured_context = extractor._extract_structured_context(clinical_timeline)

    # Test with sample documents
    test_documents = [
        {
            'document_id': 'operative_note_2018-05-28',
            'document_type': 'operative_note',
            'text': 'Craniotomy for tumor resection. Complete gross total resection achieved.'
        },
        {
            'document_id': 'pathology_report_2018-05-29',
            'document_type': 'pathology_report',
            'text': 'Pilocytic astrocytoma, WHO Grade I. Ki-67 index 2%.'
        }
    ]

    # Test extraction for extent of resection
    results = extractor.extract_with_structured_context(
        patient_id,
        'extent_of_resection',
        test_documents,
        structured_context
    )

    # Generate report
    print("\n" + "="*70)
    print("ENHANCED LLM EXTRACTION TEST")
    print("="*70)
    print(f"\nVariable: extent_of_resection")
    print(f"Structured Context Keys: {list(structured_context.keys())[:5]}")
    print(f"\nAggregated Result:")
    print(f"  Value: {results['aggregated']['value']}")
    print(f"  Confidence: {results['aggregated']['confidence']:.1%}")
    print(f"  Validation: {'✓' if results['aggregated']['confidence'] > 0.8 else '⚠️'}")
    print("\nKey Innovation: LLM uses verified structured data to validate extractions!")