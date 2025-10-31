"""
Agents for Patient Clinical Journey Timeline Abstraction

This package contains agents for binary extraction and medical LLM integration:
- MedGemmaAgent: Medical LLM for clinical text extraction (gemma2:27b via Ollama)
- BinaryFileAgent: Streams and extracts text from S3-stored binary files (PDF/HTML)
"""

from .medgemma_agent import MedGemmaAgent, ExtractionResult
from .binary_file_agent import BinaryFileAgent, BinaryFileMetadata, ExtractedBinaryContent

__all__ = [
    'MedGemmaAgent',
    'ExtractionResult',
    'BinaryFileAgent',
    'BinaryFileMetadata',
    'ExtractedBinaryContent'
]
