#!/usr/bin/env python3
"""
LLM Prompt Wrapper - V5.3

Provides structured context wrapping for all LLM requests (MedGemma, etc.).
Standardizes prompts with patient_id, diagnosis, phase, evidence summary, and expected schema.

Makes responses easier to parse and helps validate whether LLM answered fully.

Usage:
    from lib.llm_prompt_wrapper import LLMPromptWrapper, ClinicalContext

    context = ClinicalContext(
        patient_id='patient123',
        phase='PHASE_0',
        known_diagnosis='Medulloblastoma, WNT-activated',
        known_markers=['WNT pathway activation', 'CTNNB1 mutation']
    )

    wrapper = LLMPromptWrapper()
    wrapped_prompt = wrapper.wrap_extraction_prompt(
        task_description="Extract diagnosis from radiology report",
        document_text=report_text,
        expected_schema={
            "diagnosis_found": "boolean",
            "diagnosis": "string or null",
            "confidence": "float 0.0-1.0"
        },
        context=context
    )

    # Send wrapped_prompt to LLM
    response = medgemma.query(wrapped_prompt)

    # Validate response against schema
    is_valid = wrapper.validate_response(response, expected_schema)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class ClinicalContext:
    """
    Clinical context for LLM prompts.

    Provides standardized context that helps LLM make more accurate extractions
    by understanding patient's existing diagnosis, markers, and phase.
    """
    patient_id: str
    phase: str
    known_diagnosis: Optional[str] = None
    known_markers: List[str] = field(default_factory=list)
    who_section: Optional[str] = None
    evidence_summary: Optional[str] = None
    extraction_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_prompt_string(self) -> str:
        """Convert context to formatted prompt string."""
        lines = [
            "=== CLINICAL CONTEXT ===",
            f"Patient ID: {self.patient_id}",
            f"Phase: {self.phase}",
            f"Extraction Timestamp: {self.extraction_timestamp}"
        ]

        if self.known_diagnosis:
            lines.append(f"Known Diagnosis: {self.known_diagnosis}")

        if self.known_markers:
            lines.append(f"Known Molecular Markers: {', '.join(self.known_markers)}")

        if self.who_section:
            lines.append(f"WHO 2021 Section: {self.who_section}")

        if self.evidence_summary:
            lines.append(f"Evidence Summary: {self.evidence_summary}")

        return "\n".join(lines)


class LLMPromptWrapper:
    """
    Wraps LLM prompts with structured context and expected schema.

    Standardizes all LLM calls across the pipeline for better extraction
    accuracy and response validation.

    V5.6: Added intelligent summarization for long documents (>15,000 chars)
    to avoid context loss from truncation.
    """

    def __init__(self, medgemma_agent: Optional[Any] = None):
        """
        Initialize LLM prompt wrapper.

        Args:
            medgemma_agent: Optional MedGemma agent for summarizing long documents
        """
        self.prompt_history: List[Dict[str, Any]] = []
        self.medgemma_agent = medgemma_agent

    def wrap_extraction_prompt(
        self,
        task_description: str,
        document_text: str,
        expected_schema: Dict[str, Any],
        context: ClinicalContext,
        additional_instructions: Optional[str] = None,
        max_document_length: int = 4000
    ) -> str:
        """
        Wrap an extraction prompt with structured context and schema.

        Args:
            task_description: Description of extraction task
            document_text: Clinical document text to extract from
            expected_schema: Expected JSON response schema
            context: Clinical context for patient
            additional_instructions: Optional additional instructions
            max_document_length: Maximum document length to include (truncate if longer)

        Returns:
            Wrapped prompt string ready for LLM

        Example:
            wrapped_prompt = wrapper.wrap_extraction_prompt(
                task_description="Extract CNS tumor diagnosis from radiology report",
                document_text=radiology_text,
                expected_schema={
                    "diagnosis_found": "boolean",
                    "diagnosis": "string or null",
                    "location": "string or null",
                    "confidence": "float 0.0-1.0"
                },
                context=clinical_context
            )
        """
        # V5.6: Smart handling of long documents
        # - If ≤15,000 chars: Use full document
        # - If >15,000 chars AND MedGemma available: Summarize with diagnostic focus
        # - If >15,000 chars AND no MedGemma: Fall back to truncation
        if len(document_text) > 15000:
            if self.medgemma_agent:
                logger.info(f"      Document is {len(document_text)} chars, summarizing with diagnostic focus...")
                document_text = self._summarize_long_document(
                    document_text=document_text,
                    task_description=task_description,
                    context=context
                )
                logger.info(f"      Summarized to {len(document_text)} chars")
            else:
                logger.warning(f"      Document is {len(document_text)} chars but MedGemma unavailable, truncating to {max_document_length}")
                document_text = document_text[:max_document_length] + "\n\n[...TRUNCATED - MedGemma unavailable for summarization...]"

        # Build prompt
        prompt_parts = [
            context.to_prompt_string(),
            "",
            "=== TASK ===",
            task_description,
            "",
            "=== CLINICAL DOCUMENT ===",
            document_text,
            "",
            "=== EXPECTED OUTPUT SCHEMA ===",
            "Return ONLY valid JSON matching this exact structure:",
            json.dumps(expected_schema, indent=2)
        ]

        if additional_instructions:
            prompt_parts.extend([
                "",
                "=== ADDITIONAL INSTRUCTIONS ===",
                additional_instructions
            ])

        prompt_parts.extend([
            "",
            "=== RESPONSE FORMAT ===",
            "- Return ONLY valid JSON",
            "- Do NOT include explanations or markdown formatting",
            "- Ensure all schema fields are present",
            "- Use null for missing/unknown values",
            "- Confidence should reflect certainty based on context provided"
        ])

        full_prompt = "\n".join(prompt_parts)

        # Log prompt for audit
        self.prompt_history.append({
            'timestamp': datetime.now().isoformat(),
            'patient_id': context.patient_id,
            'phase': context.phase,
            'task': task_description,
            'prompt_length': len(full_prompt),
            'expected_schema': expected_schema
        })

        return full_prompt

    def _summarize_long_document(
        self,
        document_text: str,
        task_description: str,
        context: ClinicalContext
    ) -> str:
        """
        V5.6: Summarize long documents (>15,000 chars) with focus on diagnostic/classification features.

        Uses MedGemma to intelligently compress the document while preserving:
        - Primary diagnosis statements
        - Molecular markers and test results
        - Histological findings
        - WHO classification information
        - Clinical significance statements

        Args:
            document_text: Full document text (>15,000 chars)
            task_description: What we're extracting (helps focus summarization)
            context: Clinical context

        Returns:
            Summarized document text (typically 3000-8000 chars)
        """
        summarization_prompt = f"""You are a medical document summarization expert specializing in CNS tumor pathology.

{context.to_prompt_string()}

=== TASK ===
Summarize the following clinical document for the purpose of: {task_description}

CRITICAL: Preserve ALL diagnostic and classification information, including:
1. Primary diagnosis statements (exact wording)
2. ALL molecular markers, genetic tests, and results (IDH, BRAF, H3, 1p/19q, MGMT, etc.)
3. Histological findings and grade
4. WHO classification mentions
5. Clinical significance or prognosis statements
6. Dates and temporal information

DISCARD:
- Administrative text
- Non-diagnostic sections
- Repetitive/boilerplate content

Return a focused summary that captures the diagnostic essence while reducing length.

=== DOCUMENT TO SUMMARIZE ===
{document_text}

=== SUMMARY ===
"""

        try:
            summary = self.medgemma_agent.query(summarization_prompt, temperature=0.1)

            # Remove any markdown formatting MedGemma might add
            if summary.startswith("```"):
                lines = summary.split("\n")
                summary = "\n".join([l for l in lines if not l.startswith("```")])

            summary = summary.strip()

            # Safety: If summarization failed or returned too little, use smart truncation
            if len(summary) < 1000:
                logger.warning(f"      Summarization returned only {len(summary)} chars, using smart truncation instead")
                # Take first 7500 + last 7500 chars (captures intro AND conclusion)
                summary = document_text[:7500] + "\n\n[...MIDDLE SECTION TRUNCATED...]\n\n" + document_text[-7500:]

            return summary

        except Exception as e:
            logger.error(f"      Summarization failed: {e}, using smart truncation")
            # Fallback: Take first 7500 + last 7500 chars
            return document_text[:7500] + "\n\n[...MIDDLE SECTION TRUNCATED...]\n\n" + document_text[-7500:]

    def wrap_reconciliation_prompt(
        self,
        llm_extraction: str,
        structured_source: str,
        structured_source_type: str,
        context: ClinicalContext,
        conflict_type: str = "terminology_mismatch"
    ) -> str:
        """
        Wrap a conflict reconciliation prompt.

        Used in Phase 7 when LLM extraction conflicts with structured data.
        Asks LLM to reconcile by providing both sources of evidence.

        Args:
            llm_extraction: What LLM previously extracted
            structured_source: Structured data from FHIR/Athena
            structured_source_type: Type of structured source (pathology, problem_list, etc.)
            context: Clinical context
            conflict_type: Type of conflict (terminology_mismatch, date_discrepancy, etc.)

        Returns:
            Wrapped reconciliation prompt

        Example:
            reconciliation_prompt = wrapper.wrap_reconciliation_prompt(
                llm_extraction="cerebellar tumor",
                structured_source="Medulloblastoma, WNT-activated (pathology 2023-01-15)",
                structured_source_type="surgical_pathology",
                context=clinical_context,
                conflict_type="terminology_mismatch"
            )
        """
        expected_schema = {
            "same_diagnosis": "boolean",
            "explanation": "string",
            "recommended_term": "string",
            "confidence": "float 0.0-1.0"
        }

        task_description = f"""
You previously extracted: "{llm_extraction}"

However, {structured_source_type} data shows: "{structured_source}"

CONFLICT TYPE: {conflict_type}

QUESTION: Are these referring to the same diagnosis, or different diagnoses?

Consider:
- Terminology differences (e.g., "cerebellar tumor" vs "medulloblastoma" - same location)
- Date context (diagnosis evolves over time)
- Clinical authority (pathology > imaging > notes)
- Molecular subtyping refinement

Provide a reconciliation with explanation.
"""

        prompt_parts = [
            context.to_prompt_string(),
            "",
            "=== CONFLICT RECONCILIATION TASK ===",
            task_description,
            "",
            "=== EXPECTED OUTPUT SCHEMA ===",
            "Return ONLY valid JSON matching this exact structure:",
            json.dumps(expected_schema, indent=2),
            "",
            "=== RESPONSE FORMAT ===",
            "- same_diagnosis: true if both refer to same condition, false if different",
            "- explanation: Detailed reasoning for your conclusion",
            "- recommended_term: The preferred terminology to use going forward",
            "- confidence: Your confidence in this reconciliation (0.0-1.0)"
        ]

        return "\n".join(prompt_parts)

    def validate_response(
        self,
        response_text: str,
        expected_schema: Dict[str, Any]
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate LLM response against expected schema.

        Args:
            response_text: Raw LLM response
            expected_schema: Expected schema dict

        Returns:
            Tuple of (is_valid, parsed_json, error_message)

        Example:
            is_valid, data, error = wrapper.validate_response(
                response_text=llm_response,
                expected_schema={"diagnosis_found": "boolean", "diagnosis": "string"}
            )

            if is_valid:
                print(f"Diagnosis found: {data['diagnosis_found']}")
            else:
                logger.error(f"Invalid response: {error}")
        """
        # Try to parse JSON
        try:
            # Clean response (remove markdown if present)
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.split("```json")[1]
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            logger.warning(f"LLM response validation failed: {error_msg}")
            return False, None, error_msg

        # Validate schema fields present
        missing_fields = []
        for field in expected_schema.keys():
            if field not in parsed:
                missing_fields.append(field)

        if missing_fields:
            error_msg = f"Missing required fields: {missing_fields}"
            logger.warning(f"LLM response validation failed: {error_msg}")
            return False, parsed, error_msg

        # Validate confidence field if present
        if 'confidence' in parsed:
            try:
                conf = float(parsed['confidence'])
                if not (0.0 <= conf <= 1.0):
                    error_msg = f"Confidence {conf} out of range [0.0, 1.0]"
                    logger.warning(f"LLM response validation failed: {error_msg}")
                    return False, parsed, error_msg
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid confidence value: {str(e)}"
                logger.warning(f"LLM response validation failed: {error_msg}")
                return False, parsed, error_msg

        # All validations passed
        return True, parsed, None

    def create_diagnosis_extraction_schema(self) -> Dict[str, Any]:
        """Standard schema for diagnosis extraction tasks."""
        return {
            "diagnosis_found": "boolean",
            "diagnosis": "string or null",
            "confidence": "float 0.0-1.0",
            "location": "string or null",
            "date_mentioned": "string or null"
        }

    def create_marker_extraction_schema(self) -> Dict[str, Any]:
        """Standard schema for molecular marker extraction tasks."""
        return {
            "markers_found": "boolean",
            "markers": "list of strings or empty list",
            "marker_details": "list of dicts with {marker, value, interpretation} or empty list",
            "confidence": "float 0.0-1.0"
        }

    def create_treatment_extraction_schema(self) -> Dict[str, Any]:
        """Standard schema for treatment extraction tasks."""
        return {
            "treatment_found": "boolean",
            "treatment_type": "string or null (surgery/radiation/chemotherapy/other)",
            "treatment_details": "string or null",
            "start_date": "string or null",
            "end_date": "string or null",
            "confidence": "float 0.0-1.0"
        }

    def get_prompt_statistics(self) -> Dict[str, Any]:
        """Get statistics on prompts generated."""
        if not self.prompt_history:
            return {'total_prompts': 0}

        return {
            'total_prompts': len(self.prompt_history),
            'avg_prompt_length': sum(p['prompt_length'] for p in self.prompt_history) / len(self.prompt_history),
            'phases': list(set(p['phase'] for p in self.prompt_history)),
            'tasks': list(set(p['task'] for p in self.prompt_history))
        }
