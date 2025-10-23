"""
Agent 1: Extraction Quality Reviewer

Post-extraction quality analysis that:
1. Generates human-readable summary of extraction process
2. Deep dives into log files to identify failure patterns
3. Compares Phase 1 queries vs successful extractions
4. Interacts with Agent 2 to retry/correct failed extractions
5. Reviews prioritized notes to identify gaps and recommend additional retrieval
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class ExtractionQualityReviewer:
    """
    Agent 1 component that performs comprehensive post-extraction quality review.

    This agent acts as a clinical abstraction quality supervisor, analyzing:
    - What worked and didn't work across all phases
    - Why extractions failed (S3 errors, token expiration, parsing failures)
    - What data was queried but never successfully extracted
    - Whether prioritized notes cover all critical clinical events
    - Whether Agent 2 needs to re-attempt failed extractions
    """

    def __init__(self, medgemma_agent=None):
        """
        Initialize the quality reviewer

        Args:
            medgemma_agent: Optional Agent 2 (MedGemma) instance for correction attempts
        """
        self.medgemma_agent = medgemma_agent

    def generate_extraction_summary(
        self,
        comprehensive_data: Dict[str, Any],
        workflow_log_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate human-readable summary of entire extraction process.

        Returns:
            Dictionary with summary sections:
            - executive_summary: High-level overview
            - phase_results: What happened in each phase
            - successes: What worked well
            - failures: What failed and why
            - recommendations: What should be done next
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'patient_id': comprehensive_data.get('patient_id'),
            'executive_summary': {},
            'phase_results': {},
            'successes': [],
            'failures': [],
            'recommendations': []
        }

        # Executive summary
        phases = comprehensive_data.get('phases', {})
        data_query = phases.get('data_query', {})
        agent2_extraction = phases.get('agent2_extraction', {})

        total_sources = data_query.get('total_sources', 0)
        total_extracted = agent2_extraction.get('total_extractions', 0)
        extraction_rate = (total_extracted / total_sources * 100) if total_sources > 0 else 0.0

        summary['executive_summary'] = {
            'total_sources_queried': total_sources,
            'total_successful_extractions': total_extracted,
            'extraction_success_rate': f"{extraction_rate:.1f}%",
            'radiation_included': 'radiation' in comprehensive_data and comprehensive_data['radiation'] is not None,
            'chemotherapy_included': 'chemotherapy' in comprehensive_data and comprehensive_data['chemotherapy'] is not None,
            'agent1_phases_completed': {
                'temporal_inconsistency_detection': 'temporal_inconsistencies' in phases,
                'agent_feedback': 'agent_feedback' in phases,
                'eor_adjudication': 'eor_adjudication' in phases,
                'event_classification': 'event_classification' in phases
            }
        }

        # Phase-by-phase results
        summary['phase_results'] = self._analyze_phase_results(comprehensive_data)

        # Identify successes
        summary['successes'] = self._identify_successes(comprehensive_data)

        # Identify failures (requires log analysis if available)
        if workflow_log_path and workflow_log_path.exists():
            summary['failures'] = self._identify_failures_from_logs(workflow_log_path)
        else:
            summary['failures'] = self._identify_failures_from_data(comprehensive_data)

        # Generate recommendations
        summary['recommendations'] = self._generate_recommendations(
            comprehensive_data,
            summary['failures']
        )

        return summary

    def analyze_extraction_gaps(
        self,
        phase1_data: Dict[str, Any],
        successful_extractions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare what was queried in Phase 1 vs what was successfully extracted.

        Returns:
            Dictionary with:
            - imaging_text_gap: {queried: N, extracted: M, gap: N-M}
            - imaging_pdf_gap: {queried: N, extracted: M, gap: N-M}
            - operative_gap: {queried: N, extracted: M, gap: N-M}
            - progress_notes_gap: {queried: N, extracted: M, gap: N-M}
            - missing_sources: [list of source IDs that failed]
        """
        # Count what was queried
        queried_counts = {
            'imaging_text': phase1_data.get('imaging_text_count', 0),
            'imaging_pdf': phase1_data.get('imaging_pdf_count', 0),
            'operative': phase1_data.get('operative_report_count', 0),
            'progress_notes': phase1_data.get('progress_note_prioritized_count', 0)
        }

        # Count what was extracted
        extracted_by_source = {}
        for extraction in successful_extractions:
            source_type = extraction.get('source')
            if source_type not in extracted_by_source:
                extracted_by_source[source_type] = []
            extracted_by_source[source_type].append(extraction.get('source_id'))

        extracted_counts = {
            'imaging_text': len(extracted_by_source.get('imaging_text', [])),
            'imaging_pdf': len(extracted_by_source.get('imaging_pdf', [])),
            'operative': len(extracted_by_source.get('operative', [])),
            'progress_notes': len(extracted_by_source.get('progress_notes', []))
        }

        # Calculate gaps
        gaps = {}
        for source_type in queried_counts:
            queried = queried_counts[source_type]
            extracted = extracted_counts[source_type]
            gap = queried - extracted
            gap_pct = (gap / queried * 100) if queried > 0 else 0.0

            gaps[f'{source_type}_gap'] = {
                'queried': queried,
                'extracted': extracted,
                'gap': gap,
                'gap_percentage': f"{gap_pct:.1f}%"
            }

        return gaps

    def deep_analyze_failures(
        self,
        log_file_path: Path,
        comprehensive_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep dive into logs to identify patterns in failures.

        Returns:
            Dictionary with:
            - error_patterns: {error_type: count}
            - s3_errors: {file_id: error_message}
            - token_expiration: {timestamp: affected_sources}
            - parsing_errors: {source_id: error_message}
            - retry_candidates: [list of sources that could be retried]
        """
        analysis = {
            'error_patterns': {},
            's3_errors': [],
            'token_expiration': None,
            'parsing_errors': [],
            'retry_candidates': []
        }

        if not log_file_path.exists():
            logger.warning(f"Log file not found: {log_file_path}")
            return analysis

        with open(log_file_path, 'r') as f:
            log_content = f.read()

        # Pattern 1: S3 404 errors
        s3_404_pattern = r'ERROR.*Error streaming from S3.*404.*Not Found'
        s3_errors = re.findall(s3_404_pattern, log_content)
        analysis['s3_errors'] = [
            {'error': err, 'type': 'file_not_found'}
            for err in s3_errors[:10]  # Limit to first 10
        ]
        analysis['error_patterns']['s3_404_not_found'] = len(s3_errors)

        # Pattern 2: Token expiration
        token_pattern = r'(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}).*TokenRetrievalError.*Token has expired'
        token_errors = re.findall(token_pattern, log_content)
        if token_errors:
            analysis['token_expiration'] = {
                'first_occurrence': token_errors[0],
                'count': len(token_errors)
            }
            analysis['error_patterns']['token_expiration'] = len(token_errors)

        # Pattern 3: JSON parsing errors
        parse_pattern = r'ERROR.*JSONDecodeError|ERROR.*Failed to parse'
        parse_errors = re.findall(parse_pattern, log_content)
        analysis['parsing_errors'] = [
            {'error': err}
            for err in parse_errors[:10]
        ]
        analysis['error_patterns']['json_parsing_failures'] = len(parse_errors)

        # Pattern 4: MedGemma/Ollama errors
        ollama_pattern = r'ERROR.*Ollama.*|ERROR.*MedGemma.*'
        ollama_errors = re.findall(ollama_pattern, log_content)
        analysis['error_patterns']['medgemma_errors'] = len(ollama_errors)

        # Identify retry candidates (sources that failed due to transient errors)
        if analysis['token_expiration']:
            # All sources after token expiration are retry candidates
            analysis['retry_candidates'].append({
                'reason': 'token_expiration',
                'recommendation': 'Retry all sources that failed after token expiration timestamp'
            })

        if analysis['s3_errors']:
            analysis['retry_candidates'].append({
                'reason': 's3_404_errors',
                'recommendation': 'These files do not exist in S3 - cannot retry. Check FHIR data integrity.'
            })

        return analysis

    def review_prioritized_notes(
        self,
        prioritized_notes: List[Dict[str, Any]],
        surgical_history: List[Dict[str, Any]],
        imaging_history: List[Dict[str, Any]],
        medication_changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Review prioritized notes to identify if critical clinical events are missing coverage.

        Returns:
            Dictionary with:
            - coverage_analysis: Per-event-type coverage stats
            - uncovered_events: Events that have no associated progress note
            - recommendations: Specific notes to retrieve
        """
        review = {
            'coverage_analysis': {},
            'uncovered_events': [],
            'recommendations': []
        }

        # Analyze surgery coverage
        surgeries_with_notes = sum(
            1 for note in prioritized_notes
            if note.get('priority_reason') == 'post_surgery'
        )
        surgery_coverage_pct = (surgeries_with_notes / len(surgical_history) * 100) if surgical_history else 100.0

        review['coverage_analysis']['surgeries'] = {
            'total_surgeries': len(surgical_history),
            'surgeries_with_notes': surgeries_with_notes,
            'coverage_percentage': f"{surgery_coverage_pct:.1f}%"
        }

        if surgery_coverage_pct < 100:
            review['uncovered_events'].append({
                'event_type': 'surgery',
                'count': len(surgical_history) - surgeries_with_notes,
                'severity': 'high'
            })
            review['recommendations'].append({
                'action': 'retrieve_additional_progress_notes',
                'event_type': 'surgery',
                'reason': f'{len(surgical_history) - surgeries_with_notes} surgeries lack post-operative notes',
                'recommendation': 'Expand date window from ±7 to ±14 days for uncovered surgeries'
            })

        # Analyze imaging coverage
        imaging_with_notes = sum(
            1 for note in prioritized_notes
            if note.get('priority_reason') == 'post_imaging'
        )

        # Not all imaging needs notes - only major imaging (MRI, CT, PET)
        major_imaging = [
            img for img in imaging_history
            if any(mod in img.get('imaging_modality', '').upper()
                   for mod in ['MRI', 'CT', 'PET'])
        ]

        imaging_coverage_pct = (imaging_with_notes / len(major_imaging) * 100) if major_imaging else 100.0

        review['coverage_analysis']['imaging'] = {
            'total_major_imaging': len(major_imaging),
            'imaging_with_notes': imaging_with_notes,
            'coverage_percentage': f"{imaging_coverage_pct:.1f}%"
        }

        # Medication coverage
        med_notes = sum(
            1 for note in prioritized_notes
            if 'medication' in note.get('priority_reason', '')
        )

        review['coverage_analysis']['medications'] = {
            'total_medication_changes': len(medication_changes),
            'changes_with_notes': med_notes,
            'coverage_percentage': f"{(med_notes / len(medication_changes) * 100) if medication_changes else 0:.1f}%"
        }

        return review

    def attempt_extraction_corrections(
        self,
        failed_sources: List[Dict[str, Any]],
        failure_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use Agent 2 to retry extractions that failed due to transient errors.

        Returns:
            Dictionary with:
            - retry_attempts: count
            - successful_retries: count
            - still_failing: [list of sources still failing]
            - new_extractions: [list of successful re-extractions]
        """
        if not self.medgemma_agent:
            logger.warning("No MedGemma agent provided - cannot attempt corrections")
            return {
                'retry_attempts': 0,
                'successful_retries': 0,
                'still_failing': failed_sources,
                'new_extractions': [],
                'error': 'No Agent 2 instance provided'
            }

        results = {
            'retry_attempts': 0,
            'successful_retries': 0,
            'still_failing': [],
            'new_extractions': []
        }

        # Only retry if failure was due to transient errors (not S3 404s)
        retryable_sources = []

        for source in failed_sources:
            source_id = source.get('source_id')

            # Check if this source failed due to token expiration (retryable)
            if failure_analysis.get('token_expiration'):
                retryable_sources.append(source)
            # Don't retry S3 404s - file doesn't exist
            elif any(source_id in err.get('error', '') for err in failure_analysis.get('s3_errors', [])):
                results['still_failing'].append({
                    **source,
                    'reason': 's3_file_not_found',
                    'retryable': False
                })
            else:
                retryable_sources.append(source)

        logger.info(f"Found {len(retryable_sources)} retryable sources out of {len(failed_sources)} total failures")

        # TODO: Implement actual retry logic with Agent 2
        # This would involve:
        # 1. Re-fetching the source content
        # 2. Calling Agent 2 (MedGemma) for extraction
        # 3. Validating the extraction
        # 4. Adding to results

        results['retry_attempts'] = len(retryable_sources)

        return results

    # ==================== HELPER METHODS ====================

    def _analyze_phase_results(self, comprehensive_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze results from each phase"""
        phases = comprehensive_data.get('phases', {})

        results = {}

        # PHASE 1-PRE: Radiation/Chemotherapy
        if 'radiation' in comprehensive_data:
            rad = comprehensive_data['radiation']
            results['phase_1_pre_radiation'] = {
                'status': 'success' if rad and 'error' not in rad else 'failed',
                'courses': rad.get('total_courses', 0) if rad else 0,
                'completeness': rad.get('completeness_score', 0) if rad else 0
            }

        if 'chemotherapy' in comprehensive_data:
            chemo = comprehensive_data['chemotherapy']
            results['phase_1_pre_chemotherapy'] = {
                'status': 'success' if chemo and 'error' not in chemo else 'failed',
                'courses': chemo.get('total_courses', 0) if chemo else 0,
                'medications': chemo.get('total_medications', 0) if chemo else 0
            }

        # PHASE 1: Data Query
        if 'data_query' in phases:
            dq = phases['data_query']
            results['phase_1_data_query'] = {
                'status': 'success',
                'total_sources': dq.get('total_sources', 0),
                'breakdown': {
                    'imaging_text': dq.get('imaging_text_count', 0),
                    'imaging_pdf': dq.get('imaging_pdf_count', 0),
                    'operative': dq.get('operative_report_count', 0),
                    'progress_notes_all': dq.get('progress_note_all_count', 0),
                    'progress_notes_oncology': dq.get('progress_note_oncology_count', 0),
                    'progress_notes_prioritized': dq.get('progress_note_prioritized_count', 0)
                }
            }

        # PHASE 2: Agent 2 Extraction
        if 'agent2_extraction' in phases:
            a2 = phases['agent2_extraction']
            total = a2.get('total_extractions', 0)
            by_source = a2.get('by_source', {})

            results['phase_2_extraction'] = {
                'status': 'success' if total > 0 else 'no_extractions',
                'total_extractions': total,
                'by_source': by_source
            }

        # PHASE 3: Temporal Inconsistencies
        if 'temporal_inconsistencies' in phases:
            ti = phases['temporal_inconsistencies']
            results['phase_3_temporal_analysis'] = {
                'status': 'completed',
                'inconsistencies_detected': ti.get('count', 0),
                'high_severity': ti.get('high_severity', 0)
            }

        # PHASE 4: Agent Feedback
        if 'agent_feedback' in phases:
            af = phases['agent_feedback']
            results['phase_4_agent_feedback'] = {
                'status': 'completed',
                'queries_sent': af.get('queries_sent', 0),
                'successful': af.get('successful_clarifications', 0)
            }

        # PHASE 5: EOR Adjudication
        if 'eor_adjudication' in phases:
            eor = phases['eor_adjudication']
            results['phase_5_eor_adjudication'] = {
                'status': 'completed',
                'adjudications': eor.get('count', 0),
                'discrepancies': eor.get('discrepancies', 0)
            }

        # PHASE 6: Event Classification
        if 'event_classification' in phases:
            ec = phases['event_classification']
            results['phase_6_event_classification'] = {
                'status': 'completed',
                'events_classified': ec.get('count', 0),
                'by_type': ec.get('by_type', {})
            }

        return results

    def _identify_successes(self, comprehensive_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Identify what worked well"""
        successes = []

        # Radiation success
        if 'radiation' in comprehensive_data:
            rad = comprehensive_data['radiation']
            if rad and 'error' not in rad and rad.get('total_courses', 0) > 0:
                successes.append({
                    'area': 'Radiation Extraction',
                    'description': f"Successfully extracted {rad['total_courses']} radiation courses with {rad.get('completeness_score', 0)}% completeness"
                })

        # Chemotherapy success
        if 'chemotherapy' in comprehensive_data:
            chemo = comprehensive_data['chemotherapy']
            if chemo and 'error' not in chemo and chemo.get('total_courses', 0) > 0:
                successes.append({
                    'area': 'Chemotherapy Extraction',
                    'description': f"Successfully extracted {chemo['total_courses']} chemotherapy courses with {chemo.get('total_medications', 0)} medications"
                })

        # Agent 2 extraction success
        phases = comprehensive_data.get('phases', {})
        if 'agent2_extraction' in phases:
            a2 = phases['agent2_extraction']
            total = a2.get('total_extractions', 0)
            if total > 0:
                successes.append({
                    'area': 'Agent 2 Extractions',
                    'description': f"Agent 2 successfully extracted data from {total} sources"
                })

        # Agent 1 temporal analysis
        if 'temporal_inconsistencies' in phases:
            ti = phases['temporal_inconsistencies']
            if ti.get('count', 0) > 0:
                successes.append({
                    'area': 'Quality Control',
                    'description': f"Agent 1 detected {ti['count']} temporal inconsistencies for review"
                })

        return successes

    def _identify_failures_from_data(self, comprehensive_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify failures from comprehensive data (when logs not available)"""
        failures = []

        phases = comprehensive_data.get('phases', {})

        # Check for missing radiation
        if 'radiation' not in comprehensive_data or comprehensive_data.get('radiation', {}).get('error'):
            failures.append({
                'area': 'Radiation Extraction',
                'severity': 'medium',
                'description': 'No radiation data extracted or extraction error',
                'impact': 'Radiation treatment history not available for timeline'
            })

        # Check for missing chemotherapy
        if 'chemotherapy' not in comprehensive_data or comprehensive_data.get('chemotherapy', {}).get('error'):
            failures.append({
                'area': 'Chemotherapy Extraction',
                'severity': 'medium',
                'description': 'No chemotherapy data extracted or extraction error',
                'impact': 'Medication history not available for timeline'
            })

        # Check for extraction gaps
        if 'data_query' in phases and 'agent2_extraction' in phases:
            dq = phases['data_query']
            a2 = phases['agent2_extraction']
            by_source = a2.get('by_source', {})

            # Operative reports gap
            operative_queried = dq.get('operative_report_count', 0)
            operative_extracted = by_source.get('operative', 0)
            if operative_queried > 0 and operative_extracted == 0:
                failures.append({
                    'area': 'Operative Note Extraction',
                    'severity': 'high',
                    'description': f'{operative_queried} operative reports queried but 0 extracted',
                    'impact': 'Surgical procedure details and EOR assessments missing'
                })

            # Progress notes gap
            progress_queried = dq.get('progress_note_prioritized_count', 0)
            progress_extracted = by_source.get('progress_notes', 0)
            if progress_queried > 0 and progress_extracted == 0:
                failures.append({
                    'area': 'Progress Note Extraction',
                    'severity': 'high',
                    'description': f'{progress_queried} progress notes prioritized but 0 extracted',
                    'impact': 'Disease state assessments from clinical notes missing'
                })

        return failures

    def _identify_failures_from_logs(self, log_path: Path) -> List[Dict[str, Any]]:
        """Identify failures by parsing log files"""
        failures = []

        deep_analysis = self.deep_analyze_failures(log_path, {})

        # S3 errors
        if deep_analysis['error_patterns'].get('s3_404_not_found', 0) > 0:
            failures.append({
                'area': 'S3 File Access',
                'severity': 'medium',
                'description': f"{deep_analysis['error_patterns']['s3_404_not_found']} files not found in S3",
                'impact': 'Some PDFs/documents could not be retrieved',
                'retryable': False
            })

        # Token expiration
        if deep_analysis.get('token_expiration'):
            failures.append({
                'area': 'AWS Authentication',
                'severity': 'high',
                'description': f"AWS SSO token expired at {deep_analysis['token_expiration']['first_occurrence']}",
                'impact': 'All subsequent extractions failed after token expiration',
                'retryable': True
            })

        # Parsing errors
        if deep_analysis['error_patterns'].get('json_parsing_failures', 0) > 0:
            failures.append({
                'area': 'JSON Parsing',
                'severity': 'medium',
                'description': f"{deep_analysis['error_patterns']['json_parsing_failures']} JSON parsing failures",
                'impact': 'Some Agent 2 responses could not be processed',
                'retryable': True
            })

        return failures

    def _generate_recommendations(
        self,
        comprehensive_data: Dict[str, Any],
        failures: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []

        # Token expiration recommendation
        if any('token expired' in f.get('description', '').lower() for f in failures):
            recommendations.append({
                'priority': 'high',
                'action': 'Implement AWS SSO token refresh',
                'reason': 'Token expiration caused all extractions to fail after ~2.5 hours',
                'implementation': 'Add token refresh logic to BinaryFileAgent.stream_from_s3()'
            })

        # Operative note recommendation
        if any('operative' in f.get('area', '').lower() for f in failures):
            recommendations.append({
                'priority': 'high',
                'action': 'Complete operative note PDF extraction implementation',
                'reason': 'Surgeries were queried but operative note PDFs were not extracted',
                'implementation': 'Add operative_notes_pdfs to PHASE 2 extraction loop'
            })

        # Progress note recommendation
        if any('progress note' in f.get('area', '').lower() for f in failures):
            recommendations.append({
                'priority': 'high',
                'action': 'Investigate progress note extraction failures',
                'reason': 'Prioritized progress notes failed to extract',
                'implementation': 'Review logs for specific error patterns and retry with fresh token'
            })

        # S3 errors recommendation
        if any('s3' in f.get('area', '').lower() for f in failures):
            recommendations.append({
                'priority': 'medium',
                'action': 'Validate FHIR data integrity',
                'reason': 'v_binary_files metadata references files that do not exist in S3',
                'implementation': 'Run data quality check on v_binary_files.binary_id -> S3 bucket mapping'
            })

        return recommendations
