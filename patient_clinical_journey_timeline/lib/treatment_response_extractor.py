"""
Treatment Response Extractor for Patient Timeline Abstraction

This module extracts treatment response assessments from radiology reports
using MedGemma LLM. Links imaging to prior treatments and extracts qualitative
response categories.

V4.2 Enhancement #4
Created: 2025-11-03
Author: RADIANT PCA Engineering Team
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

# Import dataclasses from clinical_event
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from clinical_event import TreatmentResponse

logger = logging.getLogger(__name__)


class TreatmentResponseExtractor:
    """
    Extracts treatment response assessments from radiology reports

    Links imaging studies to prior treatments (surgery, chemo, radiation) and
    extracts qualitative response categories ("improved", "stable", "worse").

    V4.2 Enhancement - Basic qualitative response
    V5.0 will add full RANO criteria with bidimensional measurements
    """

    def __init__(self, medgemma_agent=None):
        """
        Initialize treatment response extractor

        Args:
            medgemma_agent: MedGemma agent instance for LLM extraction
        """
        self.medgemma_agent = medgemma_agent

    def extract_response(
        self,
        report_text: str,
        imaging_date: str,
        timeline_events: List[Dict[str, Any]],
        source_id: Optional[str] = None
    ) -> Optional[TreatmentResponse]:
        """
        Extract treatment response from imaging report

        Args:
            report_text: Full text of radiology report
            imaging_date: Date of imaging study (YYYY-MM-DD)
            timeline_events: List of all timeline events (for treatment context)
            source_id: FHIR resource ID (e.g., "DiagnosticReport/abc123")

        Returns:
            TreatmentResponse object or None if no response detected
        """
        if not self.medgemma_agent:
            logger.warning("MedGemma agent not available, cannot extract response")
            return None

        if not report_text or len(report_text.strip()) < 50:
            logger.debug("Report text too short for response extraction")
            return None

        try:
            # Find most recent treatment before this imaging date
            treatment_context = self._find_recent_treatment(
                imaging_date=imaging_date,
                timeline_events=timeline_events
            )

            if not treatment_context:
                logger.debug("No recent treatment found before imaging date")
                return None

            # Build extraction prompt with treatment context
            prompt = self._build_extraction_prompt(
                report_text=report_text,
                imaging_date=imaging_date,
                treatment_context=treatment_context
            )

            # Call MedGemma
            response = self.medgemma_agent.extract(prompt)

            # Parse JSON response
            result = self._parse_llm_response(response)

            if not result or not result.get('response_detected'):
                logger.debug("No treatment response detected in report")
                return None

            # Create TreatmentResponse object
            extraction_timestamp = datetime.now().isoformat()

            treatment_response = TreatmentResponse(
                response_category=result.get('response_category', 'stable'),
                assessment_method='qualitative',
                qualitative_description=result.get('qualitative_description'),
                clinical_context=treatment_context['treatment_type'],
                days_since_treatment_start=treatment_context['days_since_treatment'],
                confidence=result.get('extraction_confidence', 'MEDIUM'),
                extraction_method='llm_extraction',
                source_id=source_id,
                extracted_from_text=result.get('extracted_from_text', '')[:500],
                extracted_at=extraction_timestamp
            )

            # Validate
            errors = treatment_response.validate()
            if errors:
                logger.warning(f"Treatment response validation errors: {errors}")
                # Still return it - validation errors are non-fatal for qualitative

            logger.info(f"Extracted treatment response: {treatment_response.response_category}")
            return treatment_response

        except Exception as e:
            logger.error(f"Error extracting treatment response: {e}")
            return None

    def _find_recent_treatment(
        self,
        imaging_date: str,
        timeline_events: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find most recent treatment event before imaging date

        Args:
            imaging_date: Date of imaging study (YYYY-MM-DD)
            timeline_events: List of all timeline events

        Returns:
            Dict with treatment context or None
        """
        try:
            imaging_dt = datetime.fromisoformat(imaging_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            logger.error(f"Invalid imaging_date format: {imaging_date}")
            return None

        # Treatment event types to consider
        treatment_types = ['surgery', 'chemotherapy', 'radiation_start', 'radiation']

        # Find most recent treatment before imaging
        recent_treatment = None
        min_days_diff = float('inf')

        for event in timeline_events:
            if event.get('event_type') not in treatment_types:
                continue

            event_date = event.get('event_date')
            if not event_date:
                continue

            try:
                event_dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                continue

            # Only consider treatments BEFORE imaging
            if event_dt >= imaging_dt:
                continue

            days_diff = (imaging_dt - event_dt).days

            # Look for treatments within last 365 days (1 year window)
            if days_diff <= 365 and days_diff < min_days_diff:
                min_days_diff = days_diff
                recent_treatment = {
                    'treatment_type': event.get('event_type'),
                    'treatment_date': event_date,
                    'days_since_treatment': days_diff,
                    'description': event.get('description', '')
                }

        return recent_treatment

    def _build_extraction_prompt(
        self,
        report_text: str,
        imaging_date: str,
        treatment_context: Dict[str, Any]
    ) -> str:
        """
        Build MedGemma prompt for treatment response extraction

        Args:
            report_text: Radiology report text
            imaging_date: Date of imaging
            treatment_context: Context from recent treatment

        Returns:
            Formatted prompt string
        """
        # Limit report text
        max_chars = 8000
        if len(report_text) > max_chars:
            report_text = report_text[:max_chars] + "\n...[truncated]"

        treatment_type = treatment_context.get('treatment_type', 'unknown')
        treatment_date = treatment_context.get('treatment_date', 'unknown')
        days_since = treatment_context.get('days_since_treatment', 0)

        prompt = f"""You are a medical AI extracting treatment response assessment from radiology reports.

CLINICAL CONTEXT:
- Patient had {treatment_type} on {treatment_date} ({days_since} days ago)
- This imaging study is on {imaging_date}
- Goal: Assess tumor response to {treatment_type}

RESPONSE CATEGORIES (choose one):
1. "improved" - Tumor decreased in size, less enhancement, improvement noted
2. "stable" - No significant change, stable appearance, unchanged
3. "worse" - Tumor increased in size, more enhancement, progression noted
4. "CR" - Complete response (no evidence of tumor)
5. "PR" - Partial response (>50% decrease)
6. "SD" - Stable disease (neither PR nor PD)
7. "PD" - Progressive disease (>25% increase or new lesions)

EXTRACTION RULES:
- If report mentions "stable", "unchanged", "no significant change" → "stable"
- If report mentions "decreased", "improved", "smaller", "less enhancement" → "improved"
- If report mentions "increased", "larger", "progressive", "worsening" → "worse"
- If report uses RANO terms (CR/PR/SD/PD), extract exact term
- If no comparison or response language found, set response_detected=false
- Extract the specific text that describes the response
- Provide confidence: HIGH (explicit response language), MEDIUM (implied), LOW (unclear)

IMAGING REPORT:
{report_text}

OUTPUT SCHEMA (JSON):
{{
  "response_detected": true,
  "response_category": "stable",
  "qualitative_description": "No significant interval change in tumor appearance",
  "extracted_from_text": "stable appearance of residual tumor, unchanged from prior",
  "extraction_confidence": "HIGH"
}}

If NO treatment response language found, return:
{{
  "response_detected": false,
  "extraction_confidence": "LOW"
}}

CRITICAL: Return ONLY valid JSON. No explanatory text before or after.
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM JSON response

        Args:
            response: Raw LLM response string

        Returns:
            Parsed dict or None if parsing fails
        """
        try:
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith('```'):
                # Extract JSON from markdown code block
                lines = cleaned.split('\n')
                lines = lines[1:]  # Skip first line (```json or ```)
                for i, line in enumerate(lines):
                    if line.strip() == '```':
                        lines = lines[:i]
                        break
                cleaned = '\n'.join(lines)

            # Parse JSON
            result = json.loads(cleaned)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
