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
import time
import hashlib
from pathlib import Path

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
        max_retries: int = 3,
        cache_dir: Optional[str] = None,
        enable_chunking: bool = True,
        chunk_size: int = 8000  # chars per chunk
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.temperature = temperature
        self.max_retries = max_retries
        self.enable_chunking = enable_chunking
        self.chunk_size = chunk_size

        # Setup caching
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/tmp/medgemma_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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

    def _get_cache_key(self, prompt: str, temperature: float) -> str:
        """Generate cache key from prompt and temperature"""
        content = f"{prompt}|{temperature}|{self.model_name}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Retrieve cached response if available"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                logger.info(f"Cache hit for key {cache_key[:8]}...")
                return cached['response']
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return None

    def _save_to_cache(self, cache_key: str, response: str) -> None:
        """Save response to cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump({'response': response, 'timestamp': time.time()}, f)
            logger.info(f"Cached response for key {cache_key[:8]}...")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _chunk_text(self, text: str, max_chunk_size: int) -> List[str]:
        """
        Split text into chunks on paragraph boundaries.
        Tries to keep chunks under max_chunk_size while preserving document structure.
        """
        # Split on double newlines (paragraphs)
        paragraphs = text.split('\n\n')

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para) + 2  # +2 for \n\n

            if current_size + para_size > max_chunk_size and current_chunk:
                # Commit current chunk
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size

        # Add last chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        logger.info(f"Split document into {len(chunks)} chunks")
        return chunks

    def _merge_extraction_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple extraction results from chunked documents.
        Combines lists and takes the first non-null value for scalar fields.
        """
        merged = {}

        for result in results:
            for key, value in result.items():
                if key == 'confidence':
                    # Average confidences
                    if key not in merged:
                        merged[key] = []
                    merged[key].append(value)
                elif isinstance(value, list):
                    # Extend lists
                    if key not in merged:
                        merged[key] = []
                    elif not isinstance(merged[key], list):
                        # Previous chunk returned non-list, wrap it and continue
                        logger.warning(f"Chunk returned list for '{key}' but previous chunk had {type(merged[key]).__name__} - converting to list")
                        merged[key] = [merged[key]]
                    # Check if any items need to be lists (defensive)
                    merged[key].extend(value)
                elif isinstance(value, dict):
                    # Handle dict values
                    if key not in merged:
                        merged[key] = value
                    elif isinstance(merged[key], list):
                        # Chunk returns dict but we have a list - append it
                        logger.warning(f"Chunk returned dict for '{key}' but expected list - wrapping in list")
                        merged[key].append(value)
                    elif isinstance(merged[key], dict):
                        # Merge dicts
                        merged[key].update(value)
                elif value is not None:
                    # Handle scalar values (string, int, bool, etc.)
                    if key not in merged:
                        merged[key] = value
                    elif isinstance(merged[key], list):
                        # Chunk returns scalar but we have a list - append it
                        logger.warning(f"Chunk returned {type(value).__name__} for '{key}' but expected list - wrapping in list")
                        merged[key].append(value)
                    # else: keep existing value (first non-null scalar wins)

        # Average confidence scores
        if 'confidence' in merged and isinstance(merged['confidence'], list):
            merged['confidence'] = sum(merged['confidence']) / len(merged['confidence'])

        return merged

    def extract(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        expected_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None
    ) -> ExtractionResult:
        """
        Extract structured data from clinical text using MedGemma.

        Features:
        - Caching: Avoid re-processing identical prompts
        - Chunking: Split large documents automatically
        - Exponential backoff: Retry with increasing delays

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

        # Check cache first
        cache_key = self._get_cache_key(full_prompt, temp)
        cached_response = self._get_from_cache(cache_key)
        if cached_response:
            try:
                extracted_data = self._parse_response(cached_response)
                return ExtractionResult(
                    success=True,
                    extracted_data=extracted_data,
                    confidence=extracted_data.get('confidence', 0.8),
                    raw_response=cached_response,
                    prompt_tokens=len(full_prompt.split()),
                    completion_tokens=len(cached_response.split())
                )
            except Exception as e:
                logger.warning(f"Cached response invalid: {e}")

        # Check if we need to chunk the document
        prompt_length = len(full_prompt)
        if self.enable_chunking and prompt_length > self.chunk_size * 2:
            logger.info(f"Document is large ({prompt_length} chars), using chunking strategy")
            return self._extract_with_chunking(full_prompt, system_prompt, expected_schema, temp)

        # Try extraction with exponential backoff
        for attempt in range(self.max_retries):
            try:
                logger.info(f"MedGemma extraction attempt {attempt + 1}/{self.max_retries}")

                # Call Ollama API
                response = self._call_ollama(full_prompt, temp)

                # Save to cache
                self._save_to_cache(cache_key, response)

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
                # Exponential backoff before retry
                if attempt < self.max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"Waiting {backoff_time}s before retry...")
                    time.sleep(backoff_time)
                else:
                    return ExtractionResult(
                        success=False,
                        extracted_data={},
                        confidence=0.0,
                        raw_response=response if 'response' in locals() else "",
                        error=f"JSON parsing failed: {str(e)}"
                    )

            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama API error (attempt {attempt + 1}): {e}")
                # Exponential backoff before retry
                if attempt < self.max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"Waiting {backoff_time}s before retry...")
                    time.sleep(backoff_time)
                else:
                    return ExtractionResult(
                        success=False,
                        extracted_data={},
                        confidence=0.0,
                        raw_response="",
                        error=f"API error: {str(e)}"
                    )

            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                # Exponential backoff before retry
                if attempt < self.max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"Waiting {backoff_time}s before retry...")
                    time.sleep(backoff_time)
                else:
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

    def _extract_with_chunking(
        self,
        full_prompt: str,
        system_prompt: Optional[str] = None,
        expected_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1
    ) -> ExtractionResult:
        """
        Extract from a large document by chunking it into smaller pieces.
        Each chunk is processed separately, then results are merged.
        """
        # Split the prompt into instruction and document content
        # Assume format: "instruction\n\nDOCUMENT:\n{content}"
        parts = full_prompt.split('DOCUMENT:', 1)
        if len(parts) != 2:
            # Fallback: just chunk the whole thing
            instruction = ""
            document = full_prompt
        else:
            instruction = parts[0]
            document = parts[1]

        # Chunk the document
        chunks = self._chunk_text(document, self.chunk_size)

        # Extract from each chunk
        chunk_results = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")

            # Rebuild prompt with this chunk
            chunk_prompt = f"{instruction}DOCUMENT:\n{chunk}" if instruction else chunk

            # Try extraction on this chunk
            for attempt in range(self.max_retries):
                try:
                    response = self._call_ollama(chunk_prompt, temperature)
                    extracted_data = self._parse_response(response)

                    if expected_schema:
                        self._validate_schema(extracted_data, expected_schema)

                    chunk_results.append(extracted_data)
                    break  # Success, move to next chunk

                except Exception as e:
                    logger.warning(f"Chunk {i+1} extraction failed (attempt {attempt+1}): {e}")
                    if attempt < self.max_retries - 1:
                        backoff_time = 2 ** attempt
                        time.sleep(backoff_time)
                    else:
                        # This chunk failed, but continue with others
                        logger.error(f"Chunk {i+1} extraction failed after all retries")

        # Merge all chunk results
        if not chunk_results:
            return ExtractionResult(
                success=False,
                extracted_data={},
                confidence=0.0,
                raw_response="",
                error="All chunks failed extraction"
            )

        merged_data = self._merge_extraction_results(chunk_results)

        return ExtractionResult(
            success=True,
            extracted_data=merged_data,
            confidence=merged_data.get('confidence', 0.8),
            raw_response=json.dumps(merged_data, indent=2),  # Return JSON string, not debug message
            prompt_tokens=len(full_prompt.split()),
            completion_tokens=0  # Not tracked for chunked extraction
        )

    def _build_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Build full prompt with system message"""
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt

    def _call_ollama(self, prompt: str, temperature: float, use_streaming: bool = False) -> str:
        """
        Call Ollama API and return response text.

        Args:
            prompt: The prompt to send
            temperature: Sampling temperature
            use_streaming: If True, use streaming mode for very large documents

        Returns:
            Complete response text
        """
        prompt_length = len(prompt)
        preview = prompt[:200].replace("\n", " ") if prompt_length > 200 else prompt.replace("\n", " ")
        logger.info(f"MedGemma prompt length: {prompt_length} chars | preview: {preview[:200]}")

        start_time = time.perf_counter()

        # Adaptive timeout based on document size
        # Large documents (>15KB) need more time to process
        if prompt_length > 15000:
            timeout = 300  # 5 minutes for very large documents
            use_streaming = True  # Force streaming for very large docs
        elif prompt_length > 10000:
            timeout = 240  # 4 minutes for large documents
        else:
            timeout = 180  # 3 minutes for normal documents

        logger.info(f"Using timeout: {timeout}s for prompt length {prompt_length} | streaming: {use_streaming}")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": temperature,
            "stream": use_streaming,
            "format": "json"  # Request JSON format
        }

        if use_streaming:
            # Stream response to avoid timeout
            response_text = self._stream_ollama_response(payload, timeout)
        else:
            # Standard non-streaming request
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            response_text = result.get('response', '')

        elapsed = time.perf_counter() - start_time
        response_preview = response_text[:200].replace("\n", " ")
        logger.info(f"Ollama responded in {elapsed:.1f}s | response preview: {response_preview}")

        return response_text

    def _stream_ollama_response(self, payload: Dict[str, Any], timeout: int) -> str:
        """
        Stream response from Ollama to avoid timeout on long-running requests.
        """
        logger.info("Using streaming mode to avoid timeout")

        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json=payload,
            stream=True,
            timeout=(10, timeout)  # connection timeout, read timeout
        )

        response.raise_for_status()

        # Collect streamed chunks
        full_response = []
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        full_response.append(chunk['response'])
                    if chunk.get('done', False):
                        break
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse streaming chunk: {line}")

        return ''.join(full_response)

    def _normalize_dates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize date-only strings to ISO datetime format.
        Converts "2018-08-07" to "2018-08-07T00:00:00" for Athena compatibility.
        """
        import re
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')  # Matches YYYY-MM-DD only

        for key, value in data.items():
            if isinstance(value, str) and date_pattern.match(value):
                # Convert date-only to ISO datetime format
                data[key] = f"{value}T00:00:00"
                logger.debug(f"Normalized date field '{key}': {value} -> {data[key]}")
            elif isinstance(value, dict):
                # Recursively normalize nested dicts
                data[key] = self._normalize_dates(value)
            elif isinstance(value, list):
                # Recursively normalize lists
                data[key] = [self._normalize_dates(item) if isinstance(item, dict) else item for item in value]

        return data

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from model and normalize dates"""
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

        parsed_data = json.loads(response)

        # Normalize date-only strings to datetime format
        normalized_data = self._normalize_dates(parsed_data)

        return normalized_data

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
