"""
MedGemma Agent - Medical LLM for Clinical Text Extraction

This agent wraps calls to MedGemma 27B model running locally via Ollama.
Handles prompt formatting, response parsing, and error handling for medical extractions.

Model: medgemma:27b
Endpoint: http://localhost:11434/api/generate (Ollama)
"""

import json
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Structured result from MedGemma extraction"""
    success: bool
    extracted_data: Dict[str, Any]
    confidence: float
    raw_response: str
    error: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


class MedGemmaAgent:
    """
    MedGemma 27B agent for medical text extraction.

    Responsibilities:
    - Format medical extraction prompts
    - Call local MedGemma model via Ollama API
    - Parse and validate structured JSON responses
    - Handle errors and retry logic
    """

    def __init__(
        self,
        model_name: str = "gemma2:27b",
        ollama_url: str = "http://localhost:11434",
        temperature: float = 0.1,
        max_retries: int = 3
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.temperature = temperature
        self.max_retries = max_retries

        # Verify Ollama is running
        self._verify_ollama_connection()

    def _verify_ollama_connection(self) -> None:
        """Verify Ollama server is accessible"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get('models', [])

            # Check if medgemma model is available
            model_names = [m['name'] for m in models]
            if self.model_name not in model_names:
                logger.warning(
                    f"Model {self.model_name} not found in Ollama. "
                    f"Available models: {model_names}. "
                    f"Pull with: ollama pull {self.model_name}"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"Cannot connect to Ollama at {self.ollama_url}: {e}")
            raise ConnectionError(
                f"Ollama not accessible at {self.ollama_url}. "
                f"Start Ollama with: ollama serve"
            ) from e

    def extract(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        expected_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None
    ) -> ExtractionResult:
        """
        Extract structured data from clinical text using MedGemma.

        Args:
            prompt: The extraction prompt with clinical text
            system_prompt: Optional system message for context
            expected_schema: Expected JSON schema for validation
            temperature: Override default temperature

        Returns:
            ExtractionResult with parsed data
        """
        temp = temperature if temperature is not None else self.temperature

        # Build full prompt
        full_prompt = self._build_prompt(prompt, system_prompt)

        # Try extraction with retries
        for attempt in range(self.max_retries):
            try:
                logger.info(f"MedGemma extraction attempt {attempt + 1}/{self.max_retries}")

                # Call Ollama API
                response = self._call_ollama(full_prompt, temp)

                # Parse JSON response
                extracted_data = self._parse_response(response)

                # Validate against schema if provided
                if expected_schema:
                    self._validate_schema(extracted_data, expected_schema)

                # Calculate confidence (use model's confidence if provided)
                confidence = extracted_data.get('confidence', 0.8)

                return ExtractionResult(
                    success=True,
                    extracted_data=extracted_data,
                    confidence=confidence,
                    raw_response=response,
                    prompt_tokens=len(full_prompt.split()),  # Approximate
                    completion_tokens=len(response.split())
                )

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return ExtractionResult(
                        success=False,
                        extracted_data={},
                        confidence=0.0,
                        raw_response=response if 'response' in locals() else "",
                        error=f"JSON parsing failed: {str(e)}"
                    )

            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama API error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return ExtractionResult(
                        success=False,
                        extracted_data={},
                        confidence=0.0,
                        raw_response="",
                        error=f"API error: {str(e)}"
                    )

            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return ExtractionResult(
                        success=False,
                        extracted_data={},
                        confidence=0.0,
                        raw_response="",
                        error=f"Unexpected error: {str(e)}"
                    )

        # Should not reach here
        return ExtractionResult(
            success=False,
            extracted_data={},
            confidence=0.0,
            raw_response="",
            error="Max retries exceeded"
        )

    def _build_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Build full prompt with system message"""
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt

    def _call_ollama(self, prompt: str, temperature: float) -> str:
        """Call Ollama API and return response text"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
            "format": "json"  # Request JSON format
        }

        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json=payload,
            timeout=120  # 2 minute timeout for large models
        )
        response.raise_for_status()

        result = response.json()
        return result.get('response', '')

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from model"""
        # Try to extract JSON from response (might have markdown code blocks)
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]

        response = response.strip()

        return json.loads(response)

    def _validate_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """Validate extracted data against expected schema"""
        # Basic validation - check required fields exist
        for key in schema.get('required', []):
            if key not in data:
                raise ValueError(f"Missing required field: {key}")

    def batch_extract(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        expected_schema: Optional[Dict[str, Any]] = None
    ) -> List[ExtractionResult]:
        """
        Extract from multiple prompts in batch.

        Note: Currently sequential. Could be parallelized if Ollama supports it.
        """
        results = []
        for i, prompt in enumerate(prompts):
            logger.info(f"Processing batch item {i + 1}/{len(prompts)}")
            result = self.extract(prompt, system_prompt, expected_schema)
            results.append(result)

        return results
