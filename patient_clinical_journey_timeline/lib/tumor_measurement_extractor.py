"""
Tumor Measurement Extractor for Patient Timeline Abstraction

This module extracts tumor measurements from radiology reports using MedGemma LLM.
Supports bidimensional (RANO standard), volumetric, and qualitative measurements.

V4.2 Enhancement #3
Created: 2025-11-03
Author: RADIANT PCA Engineering Team
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

# Import dataclasses from clinical_event
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from clinical_event import TumorMeasurement

logger = logging.getLogger(__name__)


class TumorMeasurementExtractor:
    """
    Extracts structured tumor measurements from imaging reports using MedGemma LLM

    Supports three measurement types:
    1. Bidimensional: Longest diameter × perpendicular diameter (RANO standard)
    2. Volumetric: Total volume in mm³ (if 3D reconstruction available)
    3. Qualitative: "stable", "increased", "decreased", "new lesion", etc.

    V4.2 Enhancement - Foundation for V5.0 RANO criteria
    """

    def __init__(self, medgemma_agent=None):
        """
        Initialize tumor measurement extractor

        Args:
            medgemma_agent: MedGemma agent instance for LLM extraction
        """
        self.medgemma_agent = medgemma_agent

    def extract_measurements(
        self,
        report_text: str,
        source_id: Optional[str] = None,
        imaging_modality: Optional[str] = None
    ) -> List[TumorMeasurement]:
        """
        Extract tumor measurements from imaging report text

        Args:
            report_text: Full text of radiology report
            source_id: FHIR resource ID (e.g., "DiagnosticReport/abc123")
            imaging_modality: Type of imaging (e.g., "MRI Brain", "CT Head")

        Returns:
            List of TumorMeasurement objects
        """
        if not self.medgemma_agent:
            logger.warning("MedGemma agent not available, cannot extract measurements")
            return []

        if not report_text or len(report_text.strip()) < 50:
            logger.debug("Report text too short for measurement extraction")
            return []

        try:
            # Build extraction prompt
            prompt = self._build_extraction_prompt(report_text, imaging_modality)

            # Call MedGemma
            response = self.medgemma_agent.extract(prompt)

            # Parse JSON response
            result = self._parse_llm_response(response)

            if not result:
                logger.debug("No valid measurements extracted from report")
                return []

            # Convert to TumorMeasurement objects
            measurements = []
            extraction_timestamp = datetime.now().isoformat()

            for m_dict in result.get('measurements', []):
                try:
                    measurement = TumorMeasurement(
                        lesion_id=m_dict.get('lesion_id', 'unknown'),
                        location=m_dict.get('location', 'unknown'),
                        measurement_type=m_dict.get('measurement_type', 'qualitative'),
                        longest_diameter_mm=m_dict.get('longest_diameter_mm'),
                        perpendicular_diameter_mm=m_dict.get('perpendicular_diameter_mm'),
                        volume_mm3=m_dict.get('volume_mm3'),
                        qualitative_assessment=m_dict.get('qualitative_assessment'),
                        extracted_from_text=m_dict.get('extracted_from_text', '')[:500],  # Limit length
                        confidence=result.get('extraction_confidence', 'MEDIUM'),
                        extraction_method='llm_extraction',
                        source_id=source_id,
                        extracted_at=extraction_timestamp
                    )

                    # Validate measurement
                    errors = measurement.validate()
                    if errors:
                        logger.warning(f"Measurement validation errors: {errors}")
                        # Try to fix common issues
                        measurement = self._attempt_fix_measurement(measurement, errors)

                    measurements.append(measurement)

                except Exception as e:
                    logger.error(f"Error creating TumorMeasurement object: {e}")
                    continue

            logger.info(f"Extracted {len(measurements)} tumor measurements from imaging report")
            return measurements

        except Exception as e:
            logger.error(f"Error extracting tumor measurements: {e}")
            return []

    def _build_extraction_prompt(
        self,
        report_text: str,
        imaging_modality: Optional[str] = None
    ) -> str:
        """
        Build MedGemma prompt for tumor measurement extraction

        Args:
            report_text: Radiology report text
            imaging_modality: Type of imaging

        Returns:
            Formatted prompt string
        """
        # Limit report text to prevent context overflow
        max_chars = 8000
        if len(report_text) > max_chars:
            report_text = report_text[:max_chars] + "\n...[truncated]"

        modality_context = ""
        if imaging_modality:
            modality_context = f"\nIMAGING MODALITY: {imaging_modality}"

        prompt = f"""You are a medical AI extracting tumor measurements from radiology reports.

MEASUREMENT TYPES:
1. Bidimensional (RANO standard): Longest diameter × perpendicular diameter
2. Volumetric: Total volume in mm³ (if 3D reconstruction available)
3. Qualitative: "stable", "increased", "decreased", "new lesion", "resolved", "present", "absent"

EXTRACTION RULES:
- Extract ALL lesions mentioned (target and non-target)
- Convert all measurements to millimeters (mm)
  * 1 cm = 10 mm
  * Example: "3.1 cm" = 31.0 mm
- If only one diameter given, extract as longest_diameter_mm, leave perpendicular null
- If two diameters given (e.g., "3.1 x 2.4 cm"), extract both
- For qualitative only (no measurements), set measurement_type="qualitative"
- Extract comparison statements (e.g., "increased from 2.5cm to 3.1cm")
- If text says "stable", "unchanged", "no significant change":
  * Set qualitative_assessment="stable"
  * Try to extract measurements if mentioned
- Assign lesion_id sequentially:
  * Use "target_1", "target_2", etc. for measurable enhancing lesions
  * Use "non_target_1", "non_target_2", etc. for non-measurable lesions
- Extract anatomical location for each lesion

LESION CATEGORIZATION:
- TARGET lesions: Measurable enhancing tumors (bidimensional)
- NON-TARGET lesions: Non-measurable abnormalities (qualitative)
  * T2/FLAIR signal abnormalities without enhancement
  * Small lesions (<5mm)
  * Diffuse/infiltrative areas without discrete margins
  * Post-treatment changes (edema, gliosis, encephalomalacia)
{modality_context}

IMAGING REPORT:
{report_text}

OUTPUT SCHEMA (JSON):
{{
  "measurements": [
    {{
      "lesion_id": "target_1",
      "location": "right frontal lobe",
      "measurement_type": "bidimensional",
      "longest_diameter_mm": 31.0,
      "perpendicular_diameter_mm": 24.0,
      "volume_mm3": null,
      "qualitative_assessment": null,
      "extracted_from_text": "enhancing mass in right frontal lobe measuring 3.1 x 2.4 cm"
    }},
    {{
      "lesion_id": "non_target_1",
      "location": "corpus callosum",
      "measurement_type": "qualitative",
      "longest_diameter_mm": null,
      "perpendicular_diameter_mm": null,
      "volume_mm3": null,
      "qualitative_assessment": "stable",
      "extracted_from_text": "stable T2/FLAIR abnormality in corpus callosum"
    }}
  ],
  "comparison_available": true,
  "overall_assessment": "stable disease",
  "extraction_confidence": "HIGH"
}}

CRITICAL: Return ONLY valid JSON. No explanatory text before or after. If no measurements found, return {{"measurements": [], "extraction_confidence": "LOW"}}.
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
                # Skip first line (```json or ```)
                lines = lines[1:]
                # Find closing ```
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

    def _attempt_fix_measurement(
        self,
        measurement: TumorMeasurement,
        errors: List[str]
    ) -> TumorMeasurement:
        """
        Attempt to fix common measurement validation errors

        Args:
            measurement: TumorMeasurement with validation errors
            errors: List of validation error messages

        Returns:
            Fixed TumorMeasurement (or original if unfixable)
        """
        # Fix: Bidimensional with swapped diameters (longest < perpendicular)
        if "Longest diameter must be >=" in str(errors):
            if (measurement.measurement_type == "bidimensional" and
                measurement.longest_diameter_mm and
                measurement.perpendicular_diameter_mm):
                # Swap them
                original_longest = measurement.longest_diameter_mm
                measurement.longest_diameter_mm = measurement.perpendicular_diameter_mm
                measurement.perpendicular_diameter_mm = original_longest
                logger.debug("Fixed swapped diameters")

        # Fix: Bidimensional missing perpendicular, convert to qualitative
        if "require both diameters" in str(errors):
            if measurement.measurement_type == "bidimensional":
                # Convert to qualitative if we only have one diameter
                measurement.measurement_type = "qualitative"
                measurement.qualitative_assessment = "measurable"
                logger.debug("Converted incomplete bidimensional to qualitative")

        return measurement

    def extract_comparison_info(
        self,
        report_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract comparison information from imaging report

        Args:
            report_text: Radiology report text

        Returns:
            Dict with comparison info (prior_study_date, comparison_statement, etc.)
        """
        if not self.medgemma_agent:
            return None

        try:
            prompt = f"""Extract comparison information from this radiology report.

REPORT:
{report_text[:4000]}

OUTPUT JSON:
{{
  "comparison_available": true/false,
  "prior_study_date": "YYYY-MM-DD" or null,
  "comparison_statement": "brief comparison summary",
  "interval_change": "increased" / "decreased" / "stable" / "new" / "resolved"
}}

Return ONLY valid JSON.
"""
            response = self.medgemma_agent.extract(prompt)
            result = self._parse_llm_response(response)
            return result

        except Exception as e:
            logger.error(f"Error extracting comparison info: {e}")
            return None
