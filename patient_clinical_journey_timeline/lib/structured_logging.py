#!/usr/bin/env python3
"""
Structured Logging Utility - V5.2

Provides structured logging with context (patient_id, phase, aws_profile) for better
log aggregation and debugging in multi-patient cohort runs.

Usage:
    from lib.structured_logging import get_logger

    logger = get_logger(__name__, patient_id='patient123', phase='PHASE_1', aws_profile='radiant-prod')
    logger.info("Loading pathology data")
    # Output: 2025-01-15 10:30:00 - module_name - INFO - [patient_id=patient123] [phase=PHASE_1] [aws_profile=radiant-prod] Loading pathology data

    # Update context dynamically
    logger.update_context(phase='PHASE_2')
    logger.info("Constructing timeline")
"""

import logging
from typing import Optional, Dict, Any


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter that adds structured context to all log messages.

    Enables filtering/aggregation in production log monitoring systems.
    """

    def __init__(
        self,
        logger: logging.Logger,
        patient_id: Optional[str] = None,
        phase: Optional[str] = None,
        aws_profile: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize structured logger with context.

        Args:
            logger: Base logger instance
            patient_id: Patient FHIR ID (for tracing in cohort runs)
            phase: Current phase (PHASE_0, PHASE_1, etc.)
            aws_profile: AWS profile being used (radiant-prod, radiant-dev, etc.)
            extra_context: Additional custom context fields
        """
        self.context = {
            'patient_id': patient_id,
            'phase': phase,
            'aws_profile': aws_profile
        }

        if extra_context:
            self.context.update(extra_context)

        # Remove None values
        self.context = {k: v for k, v in self.context.items() if v is not None}

        super().__init__(logger, self.context)

    def process(self, msg, kwargs):
        """
        Process log message by prepending structured context.

        Format: [patient_id=X] [phase=Y] [aws_profile=Z] Original message
        """
        # Build context prefix
        context_parts = []
        for key, value in self.context.items():
            context_parts.append(f"[{key}={value}]")

        context_prefix = " ".join(context_parts)

        # Prepend context to message
        if context_prefix:
            msg = f"{context_prefix} {msg}"

        return msg, kwargs

    def update_context(self, **kwargs):
        """
        Update logging context dynamically.

        Example:
            logger.update_context(phase='PHASE_2')
            logger.update_context(extraction_source='pathology')
        """
        self.context.update(kwargs)
        # Remove None values
        self.context = {k: v for k, v in self.context.items() if v is not None}

    def remove_context(self, *keys):
        """
        Remove specific context keys.

        Example:
            logger.remove_context('extraction_source')
        """
        for key in keys:
            self.context.pop(key, None)

    def get_context(self) -> Dict[str, Any]:
        """Return current logging context."""
        return self.context.copy()


def get_logger(
    name: str,
    patient_id: Optional[str] = None,
    phase: Optional[str] = None,
    aws_profile: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> StructuredLoggerAdapter:
    """
    Get a structured logger with context.

    Args:
        name: Logger name (typically __name__)
        patient_id: Patient FHIR ID
        phase: Current phase
        aws_profile: AWS profile
        extra_context: Additional custom context

    Returns:
        StructuredLoggerAdapter with context

    Example:
        logger = get_logger(__name__, patient_id='patient123', phase='PHASE_0')
        logger.info("Starting diagnostic reasoning")
        # Output: [patient_id=patient123] [phase=PHASE_0] Starting diagnostic reasoning
    """
    base_logger = logging.getLogger(name)
    return StructuredLoggerAdapter(
        base_logger,
        patient_id=patient_id,
        phase=phase,
        aws_profile=aws_profile,
        extra_context=extra_context
    )


def setup_root_logging(level: int = logging.INFO, format_string: Optional[str] = None):
    """
    Setup root logging configuration.

    Args:
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        format_string: Custom format string (optional)

    Example:
        setup_root_logging(level=logging.DEBUG)
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=level,
        format=format_string,
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# Convenience function for backward compatibility
def create_phase_logger(
    module_name: str,
    patient_id: str,
    phase: str,
    aws_profile: str
) -> StructuredLoggerAdapter:
    """
    Create logger with phase context (convenience wrapper).

    Example:
        logger = create_phase_logger(__name__, 'patient123', 'PHASE_0', 'radiant-prod')
    """
    return get_logger(module_name, patient_id=patient_id, phase=phase, aws_profile=aws_profile)
