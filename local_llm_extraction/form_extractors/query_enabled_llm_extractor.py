"""
Query-Enabled LLM Extractor
============================
This is the KEY INNOVATION: LLM can actively query structured data during extraction.
Enables validation against ground truth, preventing hallucination and temporal errors.
"""

import json
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .structured_data_query_engine import StructuredDataQueryEngine

logger = logging.getLogger(__name__)


class QueryEnabledLLMExtractor:
    """
    Enhanced LLM extractor that can query structured data during extraction.
    This prevents hallucination by validating against verified structured data.
    """

    def __init__(self,
                 query_engine: StructuredDataQueryEngine,
                 ollama_model: str = "gemma2:27b"):
        """
        Initialize the query-enabled LLM extractor.

        Args:
            query_engine: Query engine for structured data access
            ollama_model: Ollama model to use
        """
        self.query_engine = query_engine
        self.ollama_model = ollama_model
        self.extraction_count = 0
        self.validation_count = 0

    def extract_with_validation(self,
                               variable_name: str,
                               document_content: str,
                               document_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract a variable with active query validation.

        Args:
            variable_name: Variable to extract
            document_content: Document text
            document_metadata: Document metadata (date, type, etc.)

        Returns:
            Extraction result with validation status
        """
        self.extraction_count += 1

        # Determine which queries are needed for this variable
        required_queries = self._get_required_queries(variable_name)

        # Execute queries to get ground truth
        query_results = {}
        for query_name in required_queries:
            query_results[query_name] = self._execute_query(query_name, document_metadata)

        # Build the extraction prompt with query context
        prompt = self._build_query_aware_prompt(
            variable_name,
            document_content,
            document_metadata,
            query_results
        )

        # Execute LLM extraction
        try:
            extraction = self._call_ollama(prompt)

            # Validate extraction against query results
            validation_result = self._validate_against_queries(
                variable_name,
                extraction,
                query_results,
                document_metadata
            )

            if validation_result['is_valid']:
                self.validation_count += 1

            return {
                'variable': variable_name,
                'value': extraction.get('value'),
                'confidence': self._calculate_confidence(extraction, validation_result),
                'validation_status': validation_result['status'],
                'supporting_queries': list(query_results.keys()),
                'extraction_method': 'query_enabled',
                'document_type': document_metadata.get('document_type'),
                'document_date': document_metadata.get('document_date'),
                'validation_details': validation_result
            }

        except Exception as e:
            logger.error(f"Query-enabled extraction failed: {str(e)}")
            return {
                'variable': variable_name,
                'value': None,
                'confidence': 0.0,
                'validation_status': 'failed',
                'error': str(e)
            }

    def _get_required_queries(self, variable_name: str) -> List[str]:
        """Determine which queries are needed for a variable."""
        query_map = {
            'extent_of_resection': ['QUERY_SURGERY_DATES', 'QUERY_POSTOP_IMAGING'],
            'surgery_date': ['QUERY_SURGERY_DATES'],
            'who_cns5_diagnosis': ['QUERY_DIAGNOSIS', 'QUERY_MOLECULAR_TESTS'],
            'chemotherapy_drugs': ['QUERY_CHEMOTHERAPY_EXPOSURE'],
            'radiation_dose': ['QUERY_RADIATION_DETAILS'],
            'progression_date': ['QUERY_IMAGING_ON_DATE'],
            'metastasis': ['QUERY_IMAGING_ON_DATE', 'QUERY_PROBLEM_LIST'],
            'molecular_alterations': ['QUERY_MOLECULAR_TESTS']
        }

        return query_map.get(variable_name, [])

    def _execute_query(self, query_name: str, context: Dict[str, Any]) -> Any:
        """Execute a query function."""
        if query_name == 'QUERY_SURGERY_DATES':
            return self.query_engine.QUERY_SURGERY_DATES()

        elif query_name == 'QUERY_POSTOP_IMAGING':
            # Need surgery date from context
            surgery_date = context.get('surgery_date') or context.get('event_date')
            if surgery_date:
                return self.query_engine.QUERY_POSTOP_IMAGING(surgery_date)

        elif query_name == 'QUERY_DIAGNOSIS':
            return self.query_engine.QUERY_DIAGNOSIS()

        elif query_name == 'QUERY_CHEMOTHERAPY_EXPOSURE':
            return self.query_engine.QUERY_CHEMOTHERAPY_EXPOSURE()

        elif query_name == 'QUERY_MOLECULAR_TESTS':
            return self.query_engine.QUERY_MOLECULAR_TESTS()

        elif query_name == 'QUERY_RADIATION_DETAILS':
            return self.query_engine.QUERY_RADIATION_DETAILS()

        elif query_name == 'QUERY_IMAGING_ON_DATE':
            target_date = context.get('document_date')
            if target_date:
                return self.query_engine.QUERY_IMAGING_ON_DATE(target_date, tolerance_days=30)

        elif query_name == 'QUERY_PROBLEM_LIST':
            return self.query_engine.QUERY_PROBLEM_LIST()

        return None

    def _build_query_aware_prompt(self,
                                 variable_name: str,
                                 document_content: str,
                                 document_metadata: Dict[str, Any],
                                 query_results: Dict[str, Any]) -> str:
        """Build extraction prompt with query context."""
        prompt = f"""You are a clinical data abstractor with access to VERIFIED structured data.

CRITICAL: You have access to the following VERIFIED DATA from the patient's medical record:

{self._format_query_results(query_results)}

TASK: Extract {variable_name} from the following document.

VALIDATION REQUIREMENTS:
1. The extracted value MUST be consistent with the verified data above
2. If the document contradicts the verified data, trust the verified data
3. If the document date doesn't match any verified events, DO NOT extract

Document Type: {document_metadata.get('document_type', 'Unknown')}
Document Date: {document_metadata.get('document_date', 'Unknown')}

DOCUMENT CONTENT:
{document_content[:2000]}

Based on the document AND the verified data, extract {variable_name}.

IMPORTANT:
- For extent of resection: If post-op imaging is available in verified data, use that as GOLD STANDARD
- For dates: Only extract if they match verified surgery/event dates
- For medications: Only extract if confirmed in verified medication list

Return JSON format:
{{
    "value": "extracted value or null if not found",
    "source_in_document": "exact text from document",
    "matches_verified_data": true/false,
    "confidence_reason": "explanation"
}}"""

        return prompt

    def _format_query_results(self, query_results: Dict[str, Any]) -> str:
        """Format query results for the prompt."""
        formatted = []

        for query_name, results in query_results.items():
            if results:
                formatted.append(f"\n{query_name}:")
                if isinstance(results, list):
                    for item in results[:5]:  # Limit to first 5
                        formatted.append(f"  - {self._format_query_item(item)}")
                elif isinstance(results, dict):
                    formatted.append(f"  {self._format_query_item(results)}")

        return "\n".join(formatted) if formatted else "No verified data available"

    def _format_query_item(self, item: Dict[str, Any]) -> str:
        """Format a single query result item."""
        if 'date' in item:
            return f"{item.get('date')}: {item.get('type', '')} {item.get('value', '')}"
        elif 'medication' in item:
            return f"{item.get('medication')} ({item.get('start_date', 'N/A')})"
        elif 'diagnosis' in item:
            return f"{item.get('diagnosis')} ({item.get('icd10_code', '')})"
        else:
            return str(item)

    def _call_ollama(self, prompt: str) -> Dict[str, Any]:
        """Call Ollama model for extraction."""
        try:
            cmd = [
                "ollama", "run", self.ollama_model,
                "--format", "json",
                prompt
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            else:
                logger.error(f"Ollama error: {result.stderr}")
                return {}

        except subprocess.TimeoutExpired:
            logger.error("Ollama call timed out")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response: {e}")
            return {}
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return {}

    def _validate_against_queries(self,
                                 variable_name: str,
                                 extraction: Dict[str, Any],
                                 query_results: Dict[str, Any],
                                 document_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extraction against query results."""
        validation_result = {
            'is_valid': False,
            'status': 'unvalidated',
            'reasons': []
        }

        # Special validation for extent of resection
        if variable_name == 'extent_of_resection':
            postop_imaging = query_results.get('QUERY_POSTOP_IMAGING')
            if postop_imaging and postop_imaging.get('extent'):
                # Post-op imaging is GOLD STANDARD
                if extraction.get('value') != postop_imaging['extent']:
                    validation_result['status'] = 'overridden_by_imaging'
                    validation_result['corrected_value'] = postop_imaging['extent']
                    validation_result['reasons'].append(
                        f"Post-op imaging shows: {postop_imaging['extent']}"
                    )
                else:
                    validation_result['is_valid'] = True
                    validation_result['status'] = 'validated_by_imaging'

        # Date validation
        elif variable_name == 'surgery_date':
            surgery_dates = query_results.get('QUERY_SURGERY_DATES', [])
            doc_date = document_metadata.get('document_date')

            for surgery in surgery_dates:
                if surgery.get('date') == doc_date:
                    validation_result['is_valid'] = True
                    validation_result['status'] = 'validated'
                    break
            else:
                validation_result['status'] = 'date_mismatch'
                validation_result['reasons'].append(
                    f"Document date {doc_date} doesn't match surgery dates"
                )

        # Medication validation
        elif variable_name == 'chemotherapy_drugs':
            chemo_exposure = query_results.get('QUERY_CHEMOTHERAPY_EXPOSURE', [])
            extracted_drug = extraction.get('value', '').lower()

            for drug in chemo_exposure:
                if extracted_drug in drug.get('drug', '').lower():
                    validation_result['is_valid'] = True
                    validation_result['status'] = 'validated'
                    break
            else:
                validation_result['status'] = 'not_in_medication_list'

        # Generic validation
        else:
            if extraction.get('matches_verified_data'):
                validation_result['is_valid'] = True
                validation_result['status'] = 'validated'
            else:
                validation_result['status'] = 'unvalidated'

        return validation_result

    def _calculate_confidence(self,
                            extraction: Dict[str, Any],
                            validation_result: Dict[str, Any]) -> float:
        """Calculate confidence based on extraction and validation."""
        base_confidence = 0.5

        # Boost for matching verified data
        if validation_result['is_valid']:
            base_confidence += 0.3

        # Boost for specific validation types
        if validation_result['status'] == 'validated_by_imaging':
            base_confidence = 0.95  # Gold standard
        elif validation_result['status'] == 'overridden_by_imaging':
            base_confidence = 0.1  # Low confidence in original extraction
        elif validation_result['status'] == 'validated':
            base_confidence += 0.2

        # Penalty for mismatches
        if validation_result['status'] in ['date_mismatch', 'not_in_medication_list']:
            base_confidence *= 0.5

        # Consider extraction confidence
        if extraction.get('matches_verified_data'):
            base_confidence += 0.1

        return min(1.0, max(0.0, base_confidence))

    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            'total_extractions': self.extraction_count,
            'validated_extractions': self.validation_count,
            'validation_rate': self.validation_count / self.extraction_count
            if self.extraction_count > 0 else 0,
            'query_count': len(self.query_engine.query_history)
        }


def create_query_enabled_prompt_for_extent(
    document_content: str,
    surgery_dates: List[Dict[str, Any]],
    postop_imaging: Optional[Dict[str, Any]]) -> str:
    """
    Create a specialized prompt for extent of resection with query context.
    This demonstrates the power of query-enabled extraction.
    """
    prompt = f"""You are extracting extent of resection with access to VERIFIED DATA.

VERIFIED SURGERY DATES from patient record:
{json.dumps(surgery_dates, indent=2)}

{'GOLD STANDARD POST-OP IMAGING:' if postop_imaging else 'No post-op imaging available'}
{json.dumps(postop_imaging, indent=2) if postop_imaging else ''}

CRITICAL INSTRUCTIONS:
1. If post-op imaging is available, it OVERRIDES any operative note assessment
2. Only extract extent for surgeries matching the verified dates
3. If document mentions a different date, DO NOT extract

DOCUMENT:
{document_content[:2000]}

Extract extent of resection. If post-op imaging contradicts the document, use imaging.

Return JSON:
{{
    "extent": "value or null",
    "source": "operative_note or postop_imaging",
    "confidence": "high/medium/low"
}}"""

    return prompt