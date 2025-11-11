#!/usr/bin/env python3
"""
Quality Control and Sanity Check System

This module implements a general-purpose quality control agent that performs:
1. Cross-phase consistency validation
2. Process logic sanity checks
3. Data workflow validation
4. Failure detection and handling review
5. Conclusion-evidence alignment checks

The QC agent runs between workflow phases to detect logical contradictions,
data inconsistencies, and process failures that should trigger warnings or
automatic remediation.

Design Principles:
- GENERAL PURPOSE: Not tied to cache or any specific subsystem
- CROSS-PHASE: Validates consistency across multiple workflow phases
- PROACTIVE: Detects issues before they cause downstream failures
- SELF-HEALING: Can trigger automatic remediation (cache invalidation, re-queries, etc.)
- EVIDENCE-BASED: All findings include reasoning and supporting evidence

Usage:
    from lib.quality_control_agent import QualityControlAgent, QCContext

    qc = QualityControlAgent(patient_id='eEJcrpDHtP...')

    # Build context from workflow state
    context = QCContext(
        phase='Phase1_Complete',
        who_classification={'diagnosis': 'Classification failed: No findings'},
        data_counts={'pathology': 952, 'surgeries': 4},
        timeline_events=[...]
    )

    # Run QC validation
    result = qc.validate(context)

    if not result.is_valid:
        print(f"⚠️  QC Issues detected: {len(result.issues)}")
        for issue in result.issues:
            print(f"  {issue.severity}: {issue.message}")
            if issue.auto_remediation_available:
                issue.remediate()
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Issue severity levels"""
    CRITICAL = "CRITICAL"      # Must halt execution and fix
    HIGH = "HIGH"              # Should trigger warning and investigate
    MEDIUM = "MEDIUM"          # Note for review, continue execution
    LOW = "LOW"                # Info only, no action needed


class IssueType(Enum):
    """Categories of quality control issues"""
    # Data-Conclusion Mismatches
    DATA_VS_CONCLUSION = "data_vs_conclusion"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    CONTRADICTION = "contradiction"

    # Process Logic Issues
    TEMPORAL_IMPOSSIBILITY = "temporal_impossibility"
    SEQUENCE_VIOLATION = "sequence_violation"
    MISSING_PREREQUISITE = "missing_prerequisite"

    # Data Quality Issues
    DATA_COMPLETENESS = "data_completeness"
    DATA_CONSISTENCY = "data_consistency"
    OUTLIER_DETECTED = "outlier_detected"

    # Failure Handling Issues
    UNHANDLED_FAILURE = "unhandled_failure"
    FAILED_WITHOUT_RETRY = "failed_without_retry"
    STALE_CACHED_FAILURE = "stale_cached_failure"


@dataclass
class QCIssue:
    """
    Represents a quality control issue detected by the agent.
    """
    severity: Severity
    issue_type: IssueType
    phase: str
    message: str
    reasoning: str
    evidence: Dict[str, Any]
    recommended_action: str
    auto_remediation_available: bool = False
    remediation_function: Optional[callable] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization"""
        return {
            'severity': self.severity.value,
            'issue_type': self.issue_type.value,
            'phase': self.phase,
            'message': self.message,
            'reasoning': self.reasoning,
            'evidence': self.evidence,
            'recommended_action': self.recommended_action,
            'auto_remediation_available': self.auto_remediation_available
        }

    def remediate(self) -> bool:
        """Execute auto-remediation if available"""
        if self.auto_remediation_available and self.remediation_function:
            try:
                logger.info(f"🔧 Executing auto-remediation for: {self.message}")
                self.remediation_function()
                logger.info(f"✅ Remediation successful")
                return True
            except Exception as e:
                logger.error(f"❌ Remediation failed: {e}")
                return False
        return False


@dataclass
class QCContext:
    """
    Context information for quality control validation.

    This aggregates state from multiple workflow phases for cross-phase analysis.
    """
    phase: str
    patient_id: str

    # Phase 0: WHO Classification
    who_classification: Optional[Dict[str, Any]] = None
    classification_method: Optional[str] = None
    classification_date: Optional[str] = None

    # Phase 1: Data Loading
    data_counts: Optional[Dict[str, int]] = None
    data_sources: Optional[List[str]] = None
    query_failures: Optional[List[Dict]] = None

    # Phase 2: Timeline Construction
    timeline_events: Optional[List[Dict]] = None
    temporal_bounds: Optional[Tuple[datetime, datetime]] = None

    # Phase 3: Gap Identification
    identified_gaps: Optional[List[Dict]] = None

    # Phase 4: Binary Extraction
    binary_extractions: Optional[List[Dict]] = None
    extraction_failures: Optional[List[Dict]] = None

    # Phase 5: Therapeutic Approach
    therapeutic_approach: Optional[Dict] = None
    protocol_validations: Optional[List[Dict]] = None

    # Demographics
    patient_age: Optional[int] = None
    patient_demographics: Optional[Dict] = None

    # General
    execution_start_time: Optional[datetime] = None
    phase_timings: Optional[Dict[str, float]] = field(default_factory=dict)


@dataclass
class QCResult:
    """
    Result of quality control validation.
    """
    is_valid: bool
    issues: List[QCIssue]
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    auto_remediations_executed: int = 0

    def get_critical_issues(self) -> List[QCIssue]:
        """Get only CRITICAL severity issues"""
        return [i for i in self.issues if i.severity == Severity.CRITICAL]

    def get_high_issues(self) -> List[QCIssue]:
        """Get only HIGH severity issues"""
        return [i for i in self.issues if i.severity == Severity.HIGH]

    def should_halt_execution(self) -> bool:
        """Determine if execution should halt based on issues"""
        return len(self.get_critical_issues()) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization"""
        return {
            'is_valid': self.is_valid,
            'total_issues': len(self.issues),
            'critical_issues': len(self.get_critical_issues()),
            'high_issues': len(self.get_high_issues()),
            'issues': [issue.to_dict() for issue in self.issues],
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'auto_remediations_executed': self.auto_remediations_executed
        }


class QualityControlAgent:
    """
    General-purpose quality control agent for workflow validation.

    Performs sanity checks on:
    - Process logic (are steps happening in sensible order?)
    - Data workflows (does data flow make sense?)
    - Failures (are failures being handled appropriately?)
    - Conclusions (do conclusions match the evidence?)
    """

    def __init__(self, patient_id: str, orchestrator: Optional[Any] = None):
        """
        Initialize QC Agent.

        Args:
            patient_id: Patient identifier for logging
            orchestrator: Reference to PatientTimelineOrchestrator for remediation
        """
        self.patient_id = patient_id
        self.orchestrator = orchestrator
        self.validation_history: List[QCResult] = []

    def validate(self, context: QCContext) -> QCResult:
        """
        Run comprehensive quality control validation.

        Args:
            context: QCContext with state from workflow phases

        Returns:
            QCResult with issues, warnings, and recommendations
        """
        logger.info(f"🔍 QC Agent validating {context.phase} for patient {self.patient_id}")

        issues: List[QCIssue] = []
        warnings: List[str] = []
        recommendations: List[str] = []

        # Run all validation rules
        issues.extend(self._validate_data_conclusion_alignment(context))
        issues.extend(self._validate_process_logic(context))
        issues.extend(self._validate_data_quality(context))
        issues.extend(self._validate_failure_handling(context))
        issues.extend(self._validate_temporal_logic(context))
        issues.extend(self._validate_clinical_plausibility(context))

        # Determine overall validity
        is_valid = len([i for i in issues if i.severity in [Severity.CRITICAL, Severity.HIGH]]) == 0

        # Generate warnings and recommendations
        for issue in issues:
            if issue.severity == Severity.CRITICAL:
                warnings.append(f"CRITICAL: {issue.message}")
            elif issue.severity == Severity.HIGH:
                warnings.append(f"HIGH: {issue.message}")

            recommendations.append(issue.recommended_action)

        result = QCResult(
            is_valid=is_valid,
            issues=issues,
            warnings=list(set(warnings)),  # Deduplicate
            recommendations=list(set(recommendations))  # Deduplicate
        )

        # Log summary
        if not is_valid:
            logger.warning(f"⚠️  QC validation FAILED: {len(result.get_critical_issues())} critical, {len(result.get_high_issues())} high issues")
        else:
            logger.info(f"✅ QC validation PASSED (found {len(issues)} low/medium issues)")

        # Execute auto-remediations for CRITICAL issues
        auto_remediation_count = 0
        for issue in result.get_critical_issues():
            if issue.auto_remediation_available:
                if issue.remediate():
                    auto_remediation_count += 1

        result.auto_remediations_executed = auto_remediation_count

        # Store in history
        self.validation_history.append(result)

        return result

    def _validate_data_conclusion_alignment(self, context: QCContext) -> List[QCIssue]:
        """
        Validate that conclusions align with available data.

        Examples:
        - Classification says "no findings" but 952 pathology records exist
        - Diagnosis is "medulloblastoma" but zero molecular markers present
        - Says "high confidence" but only 1 supporting data point
        """
        issues = []

        if not context.who_classification or not context.data_counts:
            return issues  # Cannot validate without both

        diagnosis = context.who_classification.get('who_2021_diagnosis', '')
        method = context.who_classification.get('classification_method', '')
        pathology_count = context.data_counts.get('pathology', 0)
        surgery_count = context.data_counts.get('surgeries', 0)

        # RULE 1: Failed classification with available data
        if ('failed' in diagnosis.lower() or 'no findings' in diagnosis.lower()) and pathology_count > 0:
            issues.append(QCIssue(
                severity=Severity.CRITICAL,
                issue_type=IssueType.DATA_VS_CONCLUSION,
                phase=context.phase,
                message=f"Classification failed ('{diagnosis}') but {pathology_count} pathology records exist",
                reasoning="If pathology data exists, classification should not fail with 'no findings'. This indicates either:\n"
                          "1. Stale cached classification from before data was available\n"
                          "2. Classification logic not querying data correctly\n"
                          "3. Data quality issues preventing extraction",
                evidence={
                    'diagnosis': diagnosis,
                    'method': method,
                    'pathology_count': pathology_count,
                    'surgery_count': surgery_count
                },
                recommended_action="Invalidate cached classification and regenerate with current data",
                auto_remediation_available=True if self.orchestrator else False,
                remediation_function=self._remediate_failed_classification_with_data if self.orchestrator else None
            ))

        # RULE 2: Specific diagnosis without supporting data
        specific_diagnoses = ['medulloblastoma', 'glioblastoma', 'astrocytoma', 'ependymoma']
        if any(d in diagnosis.lower() for d in specific_diagnoses) and pathology_count == 0:
            issues.append(QCIssue(
                severity=Severity.HIGH,
                issue_type=IssueType.EVIDENCE_INSUFFICIENT,
                phase=context.phase,
                message=f"Specific diagnosis ('{diagnosis}') but zero pathology records",
                reasoning="Specific tumor diagnoses require pathology evidence. Either:\n"
                          "1. Data sourcing is incomplete\n"
                          "2. Classification is from external source without local evidence\n"
                          "3. Data exists but not being queried correctly",
                evidence={
                    'diagnosis': diagnosis,
                    'pathology_count': pathology_count
                },
                recommended_action="Investigate data sourcing and verify classification provenance"
            ))

        # RULE 3: Unknown/Cannot determine with substantial data
        if ('unknown' in diagnosis.lower() or 'cannot determine' in diagnosis.lower()) and pathology_count > 10:
            issues.append(QCIssue(
                severity=Severity.MEDIUM,
                issue_type=IssueType.DATA_VS_CONCLUSION,
                phase=context.phase,
                message=f"Diagnosis is 'unknown/cannot determine' but {pathology_count} pathology records exist",
                reasoning="With 10+ pathology records, some classification should be possible. This suggests:\n"
                          "1. Data quality issues (missing key fields)\n"
                          "2. Classification logic too strict\n"
                          "3. Genuinely ambiguous case needing expert review",
                evidence={
                    'diagnosis': diagnosis,
                    'pathology_count': pathology_count
                },
                recommended_action="Review pathology data quality and classification logic"
            ))

        return issues

    def _validate_process_logic(self, context: QCContext) -> List[QCIssue]:
        """
        Validate process execution logic makes sense.

        Examples:
        - Phase 1 skipped but Phase 2 needs Phase 1 data
        - Retry not attempted after transient failure
        - Operation timed out but no timeout handling
        """
        issues = []

        # RULE: Query failures should be retried for transient errors
        if context.query_failures:
            for failure in context.query_failures:
                error_msg = failure.get('error', '').lower()
                if 'timeout' in error_msg or 'connection' in error_msg or 'throttl' in error_msg:
                    if not failure.get('retry_attempted', False):
                        issues.append(QCIssue(
                            severity=Severity.HIGH,
                            issue_type=IssueType.FAILED_WITHOUT_RETRY,
                            phase=context.phase,
                            message=f"Transient failure '{failure.get('query_name')}' not retried",
                            reasoning="Transient failures (timeouts, connection errors, throttling) should be retried.\n"
                                      "Not retrying means potentially missing data due to temporary issue.",
                            evidence=failure,
                            recommended_action="Implement retry logic for transient failures"
                        ))

        return issues

    def _validate_data_quality(self, context: QCContext) -> List[QCIssue]:
        """
        Validate data quality and completeness.

        Examples:
        - All records have NULL dates
        - 100% of records missing key fields
        - Outlier data volumes (10000+ records for single patient)
        """
        issues = []

        if not context.data_counts:
            return issues

        # RULE: Outlier detection for data volumes
        pathology_count = context.data_counts.get('pathology', 0)
        if pathology_count > 10000:
            issues.append(QCIssue(
                severity=Severity.MEDIUM,
                issue_type=IssueType.OUTLIER_DETECTED,
                phase=context.phase,
                message=f"Unusually high pathology count: {pathology_count} records",
                reasoning=f"Typical patients have <500 pathology records. {pathology_count} suggests:\n"
                          "1. Data duplication issue\n"
                          "2. Incorrect patient ID filtering\n"
                          "3. Legitimately complex case with extensive testing",
                evidence={'pathology_count': pathology_count},
                recommended_action="Investigate for data duplication or incorrect filtering"
            ))

        return issues

    def _validate_failure_handling(self, context: QCContext) -> List[QCIssue]:
        """
        Validate that failures are handled appropriately.

        Examples:
        - Failed result cached (preventing self-healing)
        - Exception logged but not handled
        - Silent failure (no error logged)
        """
        issues = []

        # RULE: Never cache failed classifications
        if context.who_classification:
            diagnosis = context.who_classification.get('who_2021_diagnosis', '')
            cached_timestamp = context.who_classification.get('timestamp')

            if ('failed' in diagnosis.lower() or 'error' in diagnosis.lower()) and cached_timestamp:
                issues.append(QCIssue(
                    severity=Severity.CRITICAL,
                    issue_type=IssueType.STALE_CACHED_FAILURE,
                    phase=context.phase,
                    message=f"Failed classification is cached: '{diagnosis}'",
                    reasoning="Failed classifications should NEVER be cached because:\n"
                              "1. Prevents self-healing when data becomes available\n"
                              "2. Perpetuates failures across runs\n"
                              "3. Wastes computation retrying known failures",
                    evidence={
                        'diagnosis': diagnosis,
                        'cached_timestamp': cached_timestamp
                    },
                    recommended_action="Remove failed classification from cache",
                    auto_remediation_available=True if self.orchestrator else False,
                    remediation_function=self._remediate_cached_failure if self.orchestrator else None
                ))

        return issues

    def _validate_temporal_logic(self, context: QCContext) -> List[QCIssue]:
        """
        Validate temporal logic makes sense.

        Examples:
        - Surgery on 2020-05-15 but pathology report dated 2020-05-10
        - Treatment started before diagnosis
        - Patient age at event is negative
        """
        issues = []

        if not context.timeline_events or len(context.timeline_events) < 2:
            return issues  # Need at least 2 events to check ordering

        # RULE: Diagnoses should precede treatments
        diagnosis_dates = [e['event_date'] for e in context.timeline_events
                          if e.get('event_type') in ['diagnosis', 'pathology_record', 'who_classification']
                          and e.get('event_date')]

        treatment_dates = [e['event_date'] for e in context.timeline_events
                          if e.get('event_type') in ['chemotherapy_episode', 'radiation_episode', 'surgery']
                          and e.get('event_date')]

        if diagnosis_dates and treatment_dates:
            earliest_diagnosis = min(diagnosis_dates)
            earliest_treatment = min(treatment_dates)

            if earliest_treatment < earliest_diagnosis:
                issues.append(QCIssue(
                    severity=Severity.HIGH,
                    issue_type=IssueType.TEMPORAL_IMPOSSIBILITY,
                    phase=context.phase,
                    message=f"Treatment started ({earliest_treatment}) before first diagnosis ({earliest_diagnosis})",
                    reasoning="Treatments should not start before diagnosis. This suggests:\n"
                              "1. Missing earlier diagnosis event\n"
                              "2. Date extraction error\n"
                              "3. Treatment for different condition",
                    evidence={
                        'earliest_diagnosis': earliest_diagnosis,
                        'earliest_treatment': earliest_treatment
                    },
                    recommended_action="Verify diagnosis dates and treatment indications"
                ))

        return issues

    def _validate_clinical_plausibility(self, context: QCContext) -> List[QCIssue]:
        """
        Validate clinical plausibility of findings.

        Examples:
        - Pediatric protocol for 45-year-old patient
        - Incompatible treatment combination
        - Treatment duration exceeds patient lifespan
        """
        issues = []

        # RULE: Age-appropriate protocols
        if context.patient_age and context.therapeutic_approach:
            protocols = context.therapeutic_approach.get('recommended_protocols', {})

            if context.patient_age < 18:
                # Should use pediatric protocols
                if any('adult' in str(p).lower() for p in protocols.values()):
                    issues.append(QCIssue(
                        severity=Severity.MEDIUM,
                        issue_type=IssueType.SEQUENCE_VIOLATION,
                        phase=context.phase,
                        message=f"Adult protocol recommended for pediatric patient (age {context.patient_age})",
                        reasoning="Pediatric patients (<18 years) should receive age-appropriate protocols.\n"
                                  "Adult protocols may have incorrect dosing or toxicity profiles.",
                        evidence={
                            'patient_age': context.patient_age,
                            'protocols': protocols
                        },
                        recommended_action="Review protocol selection logic for age-based routing"
                    ))

        return issues

    # Remediation Functions

    def _remediate_failed_classification_with_data(self):
        """Remediate: Failed classification with available data"""
        if not self.orchestrator:
            return

        logger.info("🔧 Invalidating stale cached classification")
        # Remove from cache
        if hasattr(self.orchestrator, '_remove_cached_classification'):
            self.orchestrator._remove_cached_classification()

        # Regenerate
        logger.info("🔄 Regenerating WHO classification with current data")
        new_classification = self.orchestrator._generate_who_classification()
        self.orchestrator.who_2021_classification = new_classification
        self.orchestrator._save_who_classification(new_classification)

    def _remediate_cached_failure(self):
        """Remediate: Remove failed classification from cache"""
        if not self.orchestrator:
            return

        logger.info("🔧 Removing failed classification from cache")
        if hasattr(self.orchestrator, '_remove_cached_classification'):
            self.orchestrator._remove_cached_classification()

    # Failure Analysis Functions

    def analyze_all_failures(self, context: QCContext) -> 'FailureAnalysisReport':
        """
        Comprehensive failure analysis across entire workflow.

        Questions every failure and does NOT accept them as normal.

        Returns:
            FailureAnalysisReport with root cause analysis and remediation assessment
        """
        logger.info(f"🔍 Analyzing all failures for patient {self.patient_id}")

        analyzed_failures = []

        # Analyze query failures
        if context.query_failures:
            for failure in context.query_failures:
                analyzed_failures.append(self._analyze_query_failure(failure))

        # Analyze classification failures
        if context.who_classification:
            diagnosis = context.who_classification.get('who_2021_diagnosis', '')
            if 'failed' in diagnosis.lower() or 'error' in diagnosis.lower():
                analyzed_failures.append(self._analyze_classification_failure(context.who_classification, context))

        # Analyze extraction failures
        if context.extraction_failures:
            for failure in context.extraction_failures:
                analyzed_failures.append(self._analyze_extraction_failure(failure))

        # Analyze gap identification (missing data is a type of failure)
        if context.identified_gaps:
            for gap in context.identified_gaps:
                # Only analyze gaps that shouldn't exist given available data
                if self._is_gap_a_failure(gap, context):
                    analyzed_failures.append(self._analyze_gap_as_failure(gap, context))

        return FailureAnalysisReport(
            patient_id=self.patient_id,
            total_failures=len(analyzed_failures),
            analyzed_failures=analyzed_failures,
            generated_at=datetime.now().isoformat()
        )

    def _analyze_query_failure(self, failure: Dict) -> 'AnalyzedFailure':
        """
        Analyze a query failure with root cause analysis.

        Questions:
        1. Why did the query fail?
        2. Was retry attempted?
        3. If retry failed, why?
        4. If no retry, why not?
        5. Is this a systemic issue or one-off?
        """
        query_name = failure.get('query_name', 'Unknown query')
        error = failure.get('error', 'No error message')
        retry_attempted = failure.get('retry_attempted', False)
        retry_result = failure.get('retry_result')

        # Root cause analysis
        root_cause = self._determine_query_failure_root_cause(error)

        # Remediation assessment
        remediation_attempted = retry_attempted
        remediation_succeeded = retry_result == 'success' if retry_result else False

        if not remediation_attempted:
            why_no_remediation = self._explain_why_no_query_retry(error, failure)
        elif not remediation_succeeded:
            why_remediation_failed = self._explain_why_query_retry_failed(error, retry_result)
        else:
            why_no_remediation = None
            why_remediation_failed = None

        # Enhanced traceability: Extract source details
        source_details = {
            'athena_database': failure.get('database', 'fhir_prd_db'),
            'query_string': failure.get('query_string', 'Not captured'),
            'query_execution_id': failure.get('query_execution_id'),
            'output_location': failure.get('output_location'),
            'execution_time_ms': failure.get('execution_time_ms')
        }

        # Investigation context
        investigation_context = {
            'aws_region': 'us-east-1',
            'aws_profile': failure.get('aws_profile', 'radiant-prod'),
            'patient_id': self.patient_id,
            'query_timestamp': failure.get('timestamp', datetime.now().isoformat()),
            'debug_info': f"Check Athena console for query execution ID: {failure.get('query_execution_id', 'N/A')}"
        }

        # Build remediation attempts list if retries occurred
        remediation_attempts_list = None
        if retry_attempted:
            remediation_attempts_list = [
                RemediationAttempt(
                    attempt_number=1,
                    timestamp=failure.get('retry_timestamp', datetime.now().isoformat()),
                    action_taken='Athena query retry',
                    parameters={'retry_delay_seconds': failure.get('retry_delay', 5)},
                    result='success' if remediation_succeeded else 'failed',
                    error_if_failed=error if not remediation_succeeded else None,
                    changes_made=['Re-executed same query'] if remediation_succeeded else [],
                    duration_seconds=failure.get('retry_duration_seconds')
                )
            ]

        return AnalyzedFailure(
            failure_type='query_failure',
            component=query_name,
            error_message=error,
            root_cause=root_cause,
            remediation_attempted=remediation_attempted,
            remediation_succeeded=remediation_succeeded,
            why_no_remediation=why_no_remediation,
            why_remediation_failed=why_remediation_failed,
            severity=Severity.HIGH if not remediation_succeeded else Severity.LOW,
            evidence=failure,
            source_details=source_details,
            error_stack_trace=failure.get('stack_trace'),
            remediation_attempts=remediation_attempts_list,
            investigation_context=investigation_context,
            timestamp=failure.get('timestamp', datetime.now().isoformat())
        )

    def _analyze_classification_failure(self, classification: Dict, context: QCContext) -> 'AnalyzedFailure':
        """
        Analyze a WHO classification failure.

        Questions:
        1. Why did classification fail?
        2. Was there sufficient data to classify?
        3. Was retry attempted?
        4. Was the failure cached (preventing self-healing)?
        5. Can we remediate now?
        """
        diagnosis = classification.get('who_2021_diagnosis', '')
        method = classification.get('classification_method', '')
        cached_timestamp = classification.get('timestamp')

        # Root cause analysis
        pathology_count = context.data_counts.get('pathology', 0) if context.data_counts else 0

        if pathology_count == 0:
            root_cause = "No pathology data available - classification cannot proceed without molecular/histology data"
        elif pathology_count > 0 and 'no findings' in diagnosis.lower():
            root_cause = "Classification logic failed to extract findings from available pathology data - indicates data quality or extraction logic issue"
        elif 'error' in diagnosis.lower():
            root_cause = f"Classification process encountered error - method: {method}"
        else:
            root_cause = "Unknown - diagnosis indicates failure but root cause unclear"

        # Remediation assessment
        is_cached = cached_timestamp is not None
        remediation_possible = pathology_count > 0  # Can retry if data exists

        if is_cached:
            why_no_remediation = "Failure was cached - prevents self-healing on subsequent runs. Cache should NEVER store failures."
        elif not remediation_possible:
            why_no_remediation = f"No pathology data available ({pathology_count} records) - cannot classify without data"
        else:
            why_no_remediation = "Failure not cached, remediation possible by regenerating classification"

        return AnalyzedFailure(
            failure_type='classification_failure',
            component='WHO 2021 Classification',
            error_message=diagnosis,
            root_cause=root_cause,
            remediation_attempted=False,  # Classification failures typically not auto-retried
            remediation_succeeded=False,
            why_no_remediation=why_no_remediation,
            why_remediation_failed=None,
            severity=Severity.CRITICAL if is_cached else (Severity.HIGH if remediation_possible else Severity.MEDIUM),
            evidence={
                'diagnosis': diagnosis,
                'method': method,
                'pathology_count': pathology_count,
                'is_cached': is_cached
            }
        )

    def _analyze_extraction_failure(self, failure: Dict) -> 'AnalyzedFailure':
        """
        Analyze a binary extraction failure.

        Questions:
        1. Why did extraction fail?
        2. Was it document access issue or parsing issue?
        3. Was retry attempted?
        4. Is this a critical gap or acceptable failure?
        """
        document_uri = failure.get('document_uri', 'Unknown document')
        error = failure.get('error', 'No error message')
        retry_attempted = failure.get('retry_attempted', False)

        # Root cause analysis
        if 'not found' in error.lower() or '404' in error:
            root_cause = "Document not found - indicates data availability issue or incorrect URI"
        elif 'timeout' in error.lower():
            root_cause = "Document retrieval timeout - indicates S3/network issue or document too large"
        elif 'parse' in error.lower() or 'extract' in error.lower():
            root_cause = "Document parsing failure - indicates corrupted document or unsupported format"
        else:
            root_cause = f"Unknown extraction failure: {error}"

        # Remediation assessment
        is_transient = 'timeout' in error.lower() or 'connection' in error.lower()

        if not retry_attempted and is_transient:
            why_no_remediation = "Transient error not retried - should implement retry logic for network/timeout errors"
        elif not retry_attempted:
            why_no_remediation = "Non-transient error - retry unlikely to succeed without fixing root cause"
        else:
            why_no_remediation = None

        # Enhanced traceability: Extract source details
        source_details = {
            's3_uri': document_uri,
            's3_bucket': failure.get('s3_bucket'),
            's3_key': failure.get('s3_key'),
            'document_type': failure.get('document_type'),
            'document_category': failure.get('document_category'),
            'document_date': failure.get('document_date'),
            'fhir_resource_id': failure.get('fhir_resource_id'),
            'fhir_resource_type': failure.get('fhir_resource_type')
        }

        # Investigation context
        investigation_context = {
            'patient_id': self.patient_id,
            'extraction_timestamp': failure.get('timestamp', datetime.now().isoformat()),
            'extraction_agent': failure.get('agent', 'MedGemma'),
            'extraction_priority': failure.get('extraction_priority'),
            'debug_info': f"Check S3 object exists: aws s3 ls {document_uri}" if document_uri.startswith('s3://') else None,
            'related_encounter_id': failure.get('encounter_id'),
            'related_procedure_id': failure.get('procedure_id')
        }

        # Build remediation attempts list if retries occurred
        remediation_attempts_list = None
        if retry_attempted:
            retry_count = failure.get('retry_count', 1)
            remediation_attempts_list = []
            for i in range(retry_count):
                remediation_attempts_list.append(
                    RemediationAttempt(
                        attempt_number=i + 1,
                        timestamp=failure.get(f'retry_{i+1}_timestamp', datetime.now().isoformat()),
                        action_taken='Binary document extraction retry',
                        parameters={
                            'retry_delay_seconds': failure.get(f'retry_{i+1}_delay', 10 * (i+1)),
                            'extraction_method': failure.get('extraction_method')
                        },
                        result='failed',  # All attempts failed if we're analyzing
                        error_if_failed=failure.get(f'retry_{i+1}_error', error),
                        changes_made=[],
                        duration_seconds=failure.get(f'retry_{i+1}_duration_seconds')
                    )
                )

        # Related records: Get surrounding extraction context
        related_records = []
        if failure.get('related_extractions'):
            related_records = failure['related_extractions']

        return AnalyzedFailure(
            failure_type='extraction_failure',
            component=document_uri,
            error_message=error,
            root_cause=root_cause,
            remediation_attempted=retry_attempted,
            remediation_succeeded=False,  # If we're analyzing it, it failed
            why_no_remediation=why_no_remediation,
            why_remediation_failed="Retry failed - root cause not resolved" if retry_attempted else None,
            severity=Severity.MEDIUM,
            evidence=failure,
            source_details=source_details,
            error_stack_trace=failure.get('stack_trace'),
            remediation_attempts=remediation_attempts_list,
            investigation_context=investigation_context,
            related_records=related_records if related_records else None,
            timestamp=failure.get('timestamp', datetime.now().isoformat())
        )

    def _is_gap_a_failure(self, gap: Dict, context: QCContext) -> bool:
        """
        Determine if an identified gap is actually a failure (i.e., data exists but wasn't found).
        """
        gap_type = gap.get('gap_type', '')

        # If we have pathology data but gap says "missing diagnosis" - that's a failure
        if 'diagnosis' in gap_type.lower() and context.data_counts and context.data_counts.get('pathology', 0) > 0:
            return True

        # If we have treatment data but gap says "missing treatment" - that's a failure
        if 'treatment' in gap_type.lower():
            if context.data_counts and (
                context.data_counts.get('chemotherapy', 0) > 0 or
                context.data_counts.get('radiation', 0) > 0 or
                context.data_counts.get('surgeries', 0) > 0
            ):
                return True

        return False

    def _analyze_gap_as_failure(self, gap: Dict, context: QCContext) -> 'AnalyzedFailure':
        """
        Analyze a gap that shouldn't exist (data exists but wasn't found).
        """
        gap_type = gap.get('gap_type', 'Unknown gap')
        description = gap.get('description', '')

        root_cause = f"Data exists but gap identification logic didn't find it - indicates query/extraction logic issue"

        return AnalyzedFailure(
            failure_type='gap_identification_failure',
            component=gap_type,
            error_message=description,
            root_cause=root_cause,
            remediation_attempted=False,
            remediation_succeeded=False,
            why_no_remediation="Logic issue requires code fix - cannot auto-remediate",
            why_remediation_failed=None,
            severity=Severity.MEDIUM,
            evidence={
                'gap': gap,
                'available_data': context.data_counts
            }
        )

    def _determine_query_failure_root_cause(self, error: str) -> str:
        """Determine root cause of query failure from error message."""
        error_lower = error.lower()

        if 'timeout' in error_lower:
            return "Query timeout - indicates large dataset, complex query, or Athena performance issue"
        elif 'throttl' in error_lower or 'rate limit' in error_lower:
            return "Rate limiting - too many concurrent queries or quota exceeded"
        elif 'permission' in error_lower or 'access denied' in error_lower:
            return "Permission error - IAM role lacks necessary Athena/S3 permissions"
        elif 'syntax' in error_lower or 'parse' in error_lower:
            return "SQL syntax error - query malformed or invalid"
        elif 'not found' in error_lower or 'does not exist' in error_lower:
            return "Table/view not found - schema changed or incorrect database/table name"
        elif 'connection' in error_lower or 'network' in error_lower:
            return "Network connectivity issue - transient network problem"
        else:
            return f"Unknown query failure: {error}"

    def _explain_why_no_query_retry(self, error: str, failure: Dict) -> str:
        """Explain why query was not retried."""
        error_lower = error.lower()

        if 'timeout' in error_lower or 'connection' in error_lower or 'throttl' in error_lower:
            return "SHOULD HAVE BEEN RETRIED - transient errors should have retry logic"
        elif 'syntax' in error_lower or 'not found' in error_lower:
            return "Non-transient error - retry would fail again without code fix"
        else:
            return "Unknown reason - retry logic may not be implemented"

    def _explain_why_query_retry_failed(self, error: str, retry_result: Any) -> str:
        """Explain why query retry failed."""
        return f"Retry failed with same error - root cause not resolved. Original error: {error}"


@dataclass
class RemediationAttempt:
    """
    Detailed record of a single remediation attempt.
    """
    attempt_number: int
    timestamp: str
    action_taken: str
    parameters: Dict[str, Any]
    result: str  # 'success', 'failed', 'partial'
    error_if_failed: Optional[str]
    changes_made: List[str]
    duration_seconds: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'attempt_number': self.attempt_number,
            'timestamp': self.timestamp,
            'action_taken': self.action_taken,
            'parameters': self.parameters,
            'result': self.result,
            'error_if_failed': self.error_if_failed,
            'changes_made': self.changes_made,
            'duration_seconds': self.duration_seconds
        }


@dataclass
class AnalyzedFailure:
    """
    Represents a failure that has been analyzed for root cause and remediation.

    Enhanced with detailed traceability for investigation.
    """
    failure_type: str
    component: str
    error_message: str
    root_cause: str
    remediation_attempted: bool
    remediation_succeeded: bool
    why_no_remediation: Optional[str]
    why_remediation_failed: Optional[str]
    severity: Severity
    evidence: Dict[str, Any]

    # Enhanced traceability fields
    source_details: Optional[Dict[str, Any]] = None  # File paths, S3 URIs, table names, query IDs
    error_stack_trace: Optional[str] = None  # Full stack trace if available
    remediation_attempts: Optional[List[RemediationAttempt]] = None  # Detailed attempt history
    investigation_context: Optional[Dict[str, Any]] = None  # Additional context for debugging
    related_records: Optional[List[Dict[str, Any]]] = None  # Related data that might help investigation
    timestamp: Optional[str] = None  # When failure occurred

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization with full traceability."""
        base_dict = {
            'failure_type': self.failure_type,
            'component': self.component,
            'error_message': self.error_message,
            'root_cause': self.root_cause,
            'remediation_attempted': self.remediation_attempted,
            'remediation_succeeded': self.remediation_succeeded,
            'why_no_remediation': self.why_no_remediation,
            'why_remediation_failed': self.why_remediation_failed,
            'severity': self.severity.value,
            'evidence': self.evidence,
            'timestamp': self.timestamp
        }

        # Add enhanced fields if present
        if self.source_details:
            base_dict['source_details'] = self.source_details

        if self.error_stack_trace:
            base_dict['error_stack_trace'] = self.error_stack_trace

        if self.remediation_attempts:
            base_dict['remediation_attempts'] = [attempt.to_dict() for attempt in self.remediation_attempts]
            base_dict['total_remediation_attempts'] = len(self.remediation_attempts)

        if self.investigation_context:
            base_dict['investigation_context'] = self.investigation_context

        if self.related_records:
            base_dict['related_records'] = self.related_records
            base_dict['related_records_count'] = len(self.related_records)

        return base_dict


@dataclass
class FailureAnalysisReport:
    """
    Comprehensive report of all failures in a workflow run.

    This report questions every failure and provides root cause analysis.
    """
    patient_id: str
    total_failures: int
    analyzed_failures: List[AnalyzedFailure]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'patient_id': self.patient_id,
            'total_failures': self.total_failures,
            'critical_failures': len([f for f in self.analyzed_failures if f.severity == Severity.CRITICAL]),
            'high_severity_failures': len([f for f in self.analyzed_failures if f.severity == Severity.HIGH]),
            'remediable_failures': len([f for f in self.analyzed_failures if not f.remediation_attempted and f.why_no_remediation and 'SHOULD HAVE' in f.why_no_remediation]),
            'analyzed_failures': [f.to_dict() for f in self.analyzed_failures],
            'generated_at': self.generated_at
        }

    def save_to_file(self, output_dir: str):
        """Save failure analysis report to JSON file."""
        import json
        from pathlib import Path

        output_path = Path(output_dir) / f"failure_analysis_{self.patient_id}.json"
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"📋 Failure analysis report saved to {output_path}")
