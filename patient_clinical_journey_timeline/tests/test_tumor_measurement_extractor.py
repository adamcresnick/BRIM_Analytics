"""
Unit Tests for Tumor Measurement Extractor

Tests the TumorMeasurementExtractor class to ensure proper extraction
and parsing of tumor measurements from radiology reports.

Created: 2025-11-03
Author: RADIANT PCA Engineering Team
"""

import unittest
import json
from unittest.mock import Mock, MagicMock
from typing import List

import sys
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from tumor_measurement_extractor import TumorMeasurementExtractor
from clinical_event import TumorMeasurement


class MockMedGemmaAgent:
    """Mock MedGemma agent for testing"""

    def __init__(self, response_data=None):
        self.response_data = response_data or {}

    def extract(self, prompt, temperature=0.1):
        """Mock extract method - returns JSON string like real MedGemma"""
        # Return JSON string (simulating LLM response)
        return json.dumps(self.response_data)


class TestTumorMeasurementExtractor(unittest.TestCase):
    """Test TumorMeasurementExtractor class"""

    def test_initialization(self):
        """Test extractor initialization"""
        agent = MockMedGemmaAgent()
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)
        self.assertIsNotNone(extractor)
        self.assertEqual(extractor.medgemma_agent, agent)

    def test_initialization_without_agent(self):
        """Test extractor initialization without agent"""
        extractor = TumorMeasurementExtractor(medgemma_agent=None)
        self.assertIsNone(extractor.medgemma_agent)

    def test_extract_single_bidimensional_measurement(self):
        """Test extracting single bidimensional measurement"""
        mock_response = {
            "measurements": [
                {
                    "lesion_id": "target_1",
                    "location": "right frontal lobe",
                    "measurement_type": "bidimensional",
                    "longest_diameter_mm": 31.0,
                    "perpendicular_diameter_mm": 24.0,
                    "extracted_from_text": "enhancing mass 3.1 x 2.4 cm"
                }
            ],
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        report_text = """
        MRI Brain with contrast:
        There is an enhancing mass in the right frontal lobe measuring 3.1 x 2.4 cm.
        """

        measurements = extractor.extract_measurements(
            report_text=report_text,
            source_id="DiagnosticReport/123"
        )

        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0].lesion_id, "target_1")
        self.assertEqual(measurements[0].location, "right frontal lobe")
        self.assertEqual(measurements[0].measurement_type, "bidimensional")
        self.assertEqual(measurements[0].longest_diameter_mm, 31.0)
        self.assertEqual(measurements[0].perpendicular_diameter_mm, 24.0)
        self.assertEqual(measurements[0].confidence, "HIGH")

    def test_extract_multiple_measurements(self):
        """Test extracting multiple measurements (target and non-target)"""
        mock_response = {
            "measurements": [
                {
                    "lesion_id": "target_1",
                    "location": "right frontal lobe",
                    "measurement_type": "bidimensional",
                    "longest_diameter_mm": 28.0,
                    "perpendicular_diameter_mm": 21.0,
                    "extracted_from_text": "residual enhancing lesion 2.8 x 2.1 cm"
                },
                {
                    "lesion_id": "non_target_1",
                    "location": "corpus callosum",
                    "measurement_type": "qualitative",
                    "qualitative_assessment": "stable",
                    "extracted_from_text": "stable T2/FLAIR abnormality"
                }
            ],
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        report_text = """
        Comparison to prior study 6 months ago:
        1. Residual enhancing lesion in right frontal lobe measures 2.8 x 2.1 cm, slightly decreased.
        2. Stable T2/FLAIR abnormality in corpus callosum.
        """

        measurements = extractor.extract_measurements(report_text=report_text)

        self.assertEqual(len(measurements), 2)
        # Target lesion
        self.assertEqual(measurements[0].measurement_type, "bidimensional")
        self.assertEqual(measurements[0].longest_diameter_mm, 28.0)
        # Non-target lesion
        self.assertEqual(measurements[1].measurement_type, "qualitative")
        self.assertEqual(measurements[1].qualitative_assessment, "stable")

    def test_extract_volumetric_measurement(self):
        """Test extracting volumetric measurement"""
        mock_response = {
            "measurements": [
                {
                    "lesion_id": "target_1",
                    "location": "temporal lobe",
                    "measurement_type": "volumetric",
                    "volume_mm3": 15000.0,
                    "extracted_from_text": "tumor volume 15 cc"
                }
            ],
            "extraction_confidence": "MEDIUM"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        report_text = "3D volumetric analysis shows tumor volume of 15 cc."

        measurements = extractor.extract_measurements(report_text=report_text)

        self.assertEqual(len(measurements), 1)
        self.assertEqual(measurements[0].measurement_type, "volumetric")
        self.assertEqual(measurements[0].volume_mm3, 15000.0)

    def test_no_agent_returns_empty(self):
        """Test that extractor without agent returns empty list"""
        extractor = TumorMeasurementExtractor(medgemma_agent=None)

        measurements = extractor.extract_measurements(report_text="Some report text")

        self.assertEqual(len(measurements), 0)

    def test_empty_report_returns_empty(self):
        """Test that empty report returns empty list"""
        # Don't need agent for this test - empty text exits early
        agent = MockMedGemmaAgent(response_data={"measurements": []})
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        measurements = extractor.extract_measurements(report_text="")

        self.assertEqual(len(measurements), 0)

    def test_short_report_returns_empty(self):
        """Test that very short report returns empty list"""
        # Don't need agent for this test - short text exits early
        agent = MockMedGemmaAgent(response_data={"measurements": []})
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        measurements = extractor.extract_measurements(report_text="Short")

        self.assertEqual(len(measurements), 0)

    def test_parse_markdown_json_response(self):
        """Test parsing JSON wrapped in markdown code blocks"""
        mock_response_with_markdown = """```json
{
  "measurements": [
    {
      "lesion_id": "target_1",
      "location": "frontal lobe",
      "measurement_type": "bidimensional",
      "longest_diameter_mm": 30.0,
      "perpendicular_diameter_mm": 20.0,
      "extracted_from_text": "mass 3.0 x 2.0 cm"
    }
  ],
  "extraction_confidence": "HIGH"
}
```"""

        # Test the parsing method directly
        extractor = TumorMeasurementExtractor()
        result = extractor._parse_llm_response(mock_response_with_markdown)

        self.assertIsNotNone(result)
        self.assertIn("measurements", result)
        self.assertEqual(len(result["measurements"]), 1)

    def test_parse_plain_json_response(self):
        """Test parsing plain JSON response"""
        mock_response = '{"measurements": [], "extraction_confidence": "LOW"}'

        extractor = TumorMeasurementExtractor()
        result = extractor._parse_llm_response(mock_response)

        self.assertIsNotNone(result)
        self.assertEqual(result["measurements"], [])
        self.assertEqual(result["extraction_confidence"], "LOW")

    def test_parse_invalid_json_returns_none(self):
        """Test that invalid JSON returns None"""
        invalid_json = "This is not JSON at all!"

        extractor = TumorMeasurementExtractor()
        result = extractor._parse_llm_response(invalid_json)

        self.assertIsNone(result)

    def test_swapped_diameters_auto_fix(self):
        """Test auto-fix for swapped diameters"""
        mock_response = {
            "measurements": [
                {
                    "lesion_id": "target_1",
                    "location": "frontal lobe",
                    "measurement_type": "bidimensional",
                    "longest_diameter_mm": 20.0,  # Swapped!
                    "perpendicular_diameter_mm": 30.0,  # Swapped!
                    "extracted_from_text": "mass 3.0 x 2.0 cm"
                }
            ],
            "extraction_confidence": "MEDIUM"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        # Need report > 50 chars
        report_text = "MRI Brain: There is an enhancing mass measuring 3.0 x 2.0 cm in the frontal lobe."
        measurements = extractor.extract_measurements(report_text=report_text)

        # Should auto-fix by swapping
        self.assertEqual(measurements[0].longest_diameter_mm, 30.0)
        self.assertEqual(measurements[0].perpendicular_diameter_mm, 20.0)

    def test_cross_sectional_area_calculation(self):
        """Test that cross-sectional area is calculated in to_dict()"""
        mock_response = {
            "measurements": [
                {
                    "lesion_id": "target_1",
                    "location": "frontal lobe",
                    "measurement_type": "bidimensional",
                    "longest_diameter_mm": 30.0,
                    "perpendicular_diameter_mm": 20.0,
                    "extracted_from_text": "mass 3.0 x 2.0 cm"
                }
            ],
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        # Need report > 50 chars
        report_text = "MRI Brain with contrast shows an enhancing mass measuring 3.0 x 2.0 cm."
        measurements = extractor.extract_measurements(report_text=report_text)

        # Get dict representation
        measurement_dict = measurements[0].to_dict()

        # Should have calculated cross_sectional_area
        self.assertEqual(measurement_dict['cross_sectional_area_mm2'], 600.0)

    def test_build_extraction_prompt(self):
        """Test that extraction prompt is properly formatted"""
        extractor = TumorMeasurementExtractor()

        report_text = "Sample radiology report with tumor measurements."
        imaging_modality = "MRI Brain"

        prompt = extractor._build_extraction_prompt(
            report_text=report_text,
            imaging_modality=imaging_modality
        )

        # Check that key elements are in prompt
        self.assertIn("MEASUREMENT TYPES", prompt)
        self.assertIn("Bidimensional", prompt)
        self.assertIn("EXTRACTION RULES", prompt)
        self.assertIn("target_1", prompt)
        self.assertIn("non_target_1", prompt)
        self.assertIn("MRI Brain", prompt)
        self.assertIn(report_text, prompt)
        self.assertIn("OUTPUT SCHEMA", prompt)

    def test_long_report_text_truncation(self):
        """Test that very long report text is truncated"""
        extractor = TumorMeasurementExtractor()

        # Create very long report (>8000 chars)
        long_report = "X" * 10000

        prompt = extractor._build_extraction_prompt(report_text=long_report)

        # Prompt should contain truncation marker
        self.assertIn("[truncated]", prompt)
        # Prompt should not contain full 10000 chars
        self.assertLess(len(prompt), 12000)  # Some overhead for prompt template


class TestExtractedMeasurementIntegration(unittest.TestCase):
    """Integration tests for extracted measurements"""

    def test_measurement_serialization_to_json(self):
        """Test that extracted measurements can be serialized to JSON"""
        mock_response = {
            "measurements": [
                {
                    "lesion_id": "target_1",
                    "location": "frontal lobe",
                    "measurement_type": "bidimensional",
                    "longest_diameter_mm": 30.0,
                    "perpendicular_diameter_mm": 20.0,
                    "extracted_from_text": "mass 3.0 x 2.0 cm"
                }
            ],
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TumorMeasurementExtractor(medgemma_agent=agent)

        # Need report > 50 chars
        report_text = "MRI Brain: Enhancing mass in frontal lobe measures 3.0 x 2.0 centimeters."
        measurements = extractor.extract_measurements(report_text=report_text)

        # Convert to dicts
        measurements_dicts = [m.to_dict() for m in measurements]

        # Should be JSON serializable
        json_str = json.dumps(measurements_dicts, indent=2)

        # Parse back
        parsed = json.loads(json_str)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['lesion_id'], 'target_1')
        self.assertEqual(parsed[0]['cross_sectional_area_mm2'], 600.0)


if __name__ == '__main__':
    unittest.main()
