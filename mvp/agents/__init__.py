"""
Multi-Agent Framework for Clinical Data Extraction

Master Agent (Claude Sonnet 4.5) orchestrates workflow
Medical Agent (MedGemma 27B) extracts from clinical text
"""

from .medgemma_agent import MedGemmaAgent, ExtractionResult
from .master_agent import MasterAgent

__all__ = [
    'MedGemmaAgent',
    'ExtractionResult',
    'MasterAgent'
]
