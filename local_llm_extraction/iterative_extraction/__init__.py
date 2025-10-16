"""
Iterative extraction framework with multi-pass clinical reasoning
"""
from .extraction_result import Candidate, PassResult, ExtractionResult
from .pass2_structured_query import StructuredDataQuerier
from .pass3_cross_validation import CrossSourceValidator
from .pass4_temporal_reasoning import TemporalReasoner

__all__ = [
    'Candidate',
    'PassResult',
    'ExtractionResult',
    'StructuredDataQuerier',
    'CrossSourceValidator',
    'TemporalReasoner'
]
