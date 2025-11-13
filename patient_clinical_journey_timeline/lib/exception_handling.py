#!/usr/bin/env python3
"""
Exception Handling Framework - V5.2

Provides tiered exception handling (FATAL vs RECOVERABLE) with artifact completeness
metadata to prevent silent data loss.

Usage:
    from lib.exception_handling import FatalError, RecoverableError, CompletenessTracker

    # FATAL errors - stop execution
    raise FatalError("Missing anchored diagnosis - cannot proceed")

    # RECOVERABLE errors - log warning and continue
    try:
        extract_from_source()
    except Exception as e:
        raise RecoverableError("Pathology extraction failed", original_exception=e)

    # Track completeness
    tracker = CompletenessTracker()
    tracker.mark_attempted('pathology_extraction')
    tracker.mark_success('pathology_extraction', record_count=5)
    completeness_metadata = tracker.get_completeness_metadata()
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for tiered exception handling."""
    FATAL = "fatal"              # Must stop execution
    RECOVERABLE = "recoverable"  # Can continue with warning
    WARNING = "warning"          # Informational only


class FatalError(Exception):
    """
    Fatal error - execution must stop.

    Examples:
        - Missing anchored diagnosis
        - Athena connection failure
        - Invalid patient ID
        - Critical data corruption
    """

    def __init__(
        self,
        message: str,
        phase: Optional[str] = None,
        patient_id: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.phase = phase
        self.patient_id = patient_id
        self.original_exception = original_exception
        self.timestamp = datetime.now()

    def __str__(self):
        parts = [f"FATAL ERROR: {self.message}"]
        if self.phase:
            parts.append(f"Phase: {self.phase}")
        if self.patient_id:
            parts.append(f"Patient: {self.patient_id}")
        if self.original_exception:
            parts.append(f"Caused by: {type(self.original_exception).__name__}: {str(self.original_exception)}")
        return " | ".join(parts)


class RecoverableError(Exception):
    """
    Recoverable error - log warning and continue.

    Examples:
        - Single source extraction failure (when other sources available)
        - Binary document not found (skip this document)
        - MedGemma timeout (fall back to keywords)
        - Non-critical data missing
    """

    def __init__(
        self,
        message: str,
        phase: Optional[str] = None,
        patient_id: Optional[str] = None,
        original_exception: Optional[Exception] = None,
        recovery_action: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.phase = phase
        self.patient_id = patient_id
        self.original_exception = original_exception
        self.recovery_action = recovery_action
        self.timestamp = datetime.now()

    def __str__(self):
        parts = [f"RECOVERABLE ERROR: {self.message}"]
        if self.phase:
            parts.append(f"Phase: {self.phase}")
        if self.patient_id:
            parts.append(f"Patient: {self.patient_id}")
        if self.recovery_action:
            parts.append(f"Recovery: {self.recovery_action}")
        if self.original_exception:
            parts.append(f"Caused by: {type(self.original_exception).__name__}: {str(self.original_exception)}")
        return " | ".join(parts)


@dataclass
class DataSourceAttempt:
    """
    Tracks a single data source extraction attempt.

    Attributes:
        source_name: Name of data source (e.g., 'pathology', 'imaging')
        attempted: Whether extraction was attempted
        succeeded: Whether extraction succeeded
        record_count: Number of records extracted (if successful)
        error_message: Error message (if failed)
        timestamp: When extraction was attempted
    """
    source_name: str
    attempted: bool = False
    succeeded: bool = False
    record_count: int = 0
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None


class CompletenessTracker:
    """
    Tracks data extraction completeness across all sources.

    Enables artifact metadata showing which sources were attempted/successful,
    preventing silent data loss.
    """

    def __init__(self):
        self.sources: Dict[str, DataSourceAttempt] = {}
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[str] = []

    def mark_attempted(self, source_name: str):
        """Mark a data source extraction as attempted."""
        if source_name not in self.sources:
            self.sources[source_name] = DataSourceAttempt(source_name=source_name)
        self.sources[source_name].attempted = True
        self.sources[source_name].timestamp = datetime.now()

    def mark_success(self, source_name: str, record_count: int = 0):
        """Mark a data source extraction as successful."""
        if source_name not in self.sources:
            self.sources[source_name] = DataSourceAttempt(source_name=source_name)
        self.sources[source_name].succeeded = True
        self.sources[source_name].record_count = record_count

    def mark_failure(self, source_name: str, error_message: str):
        """Mark a data source extraction as failed."""
        if source_name not in self.sources:
            self.sources[source_name] = DataSourceAttempt(source_name=source_name)
        self.sources[source_name].attempted = True
        self.sources[source_name].succeeded = False
        self.sources[source_name].error_message = error_message
        self.sources[source_name].timestamp = datetime.now()

    def log_error(
        self,
        error_type: str,
        message: str,
        phase: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.RECOVERABLE
    ):
        """Log an error for later reporting."""
        self.errors.append({
            'error_type': error_type,
            'message': message,
            'phase': phase,
            'severity': severity.value,
            'timestamp': datetime.now().isoformat()
        })

    def log_warning(self, message: str):
        """Log a warning for later reporting."""
        self.warnings.append(message)

    def get_completeness_score(self) -> float:
        """
        Calculate completeness score (0.0-1.0).

        Returns:
            Completeness score: successful_sources / attempted_sources
        """
        attempted = sum(1 for s in self.sources.values() if s.attempted)
        if attempted == 0:
            return 0.0

        succeeded = sum(1 for s in self.sources.values() if s.succeeded)
        return succeeded / attempted

    def get_completeness_metadata(self) -> Dict[str, Any]:
        """
        Generate completeness metadata for artifact.

        Returns:
            Dict with completeness score, source details, errors, and warnings
        """
        return {
            'completeness_score': self.get_completeness_score(),
            'data_sources': {
                name: {
                    'attempted': source.attempted,
                    'succeeded': source.succeeded,
                    'record_count': source.record_count,
                    'error_message': source.error_message,
                    'timestamp': source.timestamp.isoformat() if source.timestamp else None
                }
                for name, source in self.sources.items()
            },
            'errors': self.errors,
            'warnings': self.warnings,
            'total_sources_attempted': sum(1 for s in self.sources.values() if s.attempted),
            'total_sources_succeeded': sum(1 for s in self.sources.values() if s.succeeded),
            'total_records_extracted': sum(s.record_count for s in self.sources.values())
        }

    def get_failed_sources(self) -> List[str]:
        """Get list of failed source names."""
        return [
            name for name, source in self.sources.items()
            if source.attempted and not source.succeeded
        ]

    def has_critical_failures(self, critical_sources: List[str]) -> bool:
        """
        Check if any critical sources failed.

        Args:
            critical_sources: List of source names that are critical

        Returns:
            True if any critical source failed
        """
        failed = self.get_failed_sources()
        return any(source in critical_sources for source in failed)


def handle_error(
    error: Exception,
    phase: str,
    patient_id: str,
    completeness_tracker: Optional[CompletenessTracker] = None,
    source_name: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None
) -> None:
    """
    Central error handling function.

    Determines if error is FATAL or RECOVERABLE and handles appropriately.

    Args:
        error: Exception that occurred
        phase: Current phase (PHASE_0, PHASE_1, etc.)
        patient_id: Patient FHIR ID
        completeness_tracker: CompletenessTracker instance (optional)
        source_name: Data source name (optional)
        logger_instance: Logger instance (optional)

    Raises:
        FatalError: If error is fatal
    """
    log = logger_instance or logger

    # Check if error is already typed
    if isinstance(error, FatalError):
        if completeness_tracker and source_name:
            completeness_tracker.mark_failure(source_name, str(error))
            completeness_tracker.log_error(
                error_type=type(error).__name__,
                message=str(error),
                phase=phase,
                severity=ErrorSeverity.FATAL
            )
        log.error(str(error))
        raise

    elif isinstance(error, RecoverableError):
        if completeness_tracker and source_name:
            completeness_tracker.mark_failure(source_name, str(error))
            completeness_tracker.log_error(
                error_type=type(error).__name__,
                message=str(error),
                phase=phase,
                severity=ErrorSeverity.RECOVERABLE
            )
        log.warning(str(error))
        return  # Continue execution

    # Classify unknown exceptions
    error_name = type(error).__name__

    # FATAL error patterns
    fatal_patterns = [
        'ConnectionError',
        'BotoCoreError',
        'ClientError',  # AWS errors
        'KeyError',  # Missing critical data
        'ValueError',  # Invalid data
        'FileNotFoundError',  # Missing critical files
    ]

    is_fatal = any(pattern in error_name for pattern in fatal_patterns)

    if is_fatal:
        fatal_error = FatalError(
            message=f"Critical error in {phase}",
            phase=phase,
            patient_id=patient_id,
            original_exception=error
        )
        if completeness_tracker and source_name:
            completeness_tracker.mark_failure(source_name, str(fatal_error))
            completeness_tracker.log_error(
                error_type=error_name,
                message=str(error),
                phase=phase,
                severity=ErrorSeverity.FATAL
            )
        log.error(str(fatal_error))
        raise fatal_error

    else:
        # Treat as recoverable
        recoverable_error = RecoverableError(
            message=f"Non-critical error in {phase}",
            phase=phase,
            patient_id=patient_id,
            original_exception=error,
            recovery_action="Continuing with partial data"
        )
        if completeness_tracker and source_name:
            completeness_tracker.mark_failure(source_name, str(recoverable_error))
            completeness_tracker.log_error(
                error_type=error_name,
                message=str(error),
                phase=phase,
                severity=ErrorSeverity.RECOVERABLE
            )
        log.warning(str(recoverable_error))
        return
