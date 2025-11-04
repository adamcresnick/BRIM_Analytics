"""
Unit Tests for Treatment Response Extractor

Tests the TreatmentResponseExtractor class to ensure proper extraction
of treatment response assessments from radiology reports.

Created: 2025-11-03
Author: RADIANT PCA Engineering Team
"""

import unittest
import json
from unittest.mock import Mock
from datetime import datetime, timedelta

import sys
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from treatment_response_extractor import TreatmentResponseExtractor
from clinical_event import TreatmentResponse


class MockMedGemmaAgent:
    """Mock MedGemma agent for testing"""

    def __init__(self, response_data=None):
        self.response_data = response_data or {}

    def extract(self, prompt, temperature=0.1):
        """Mock extract method - returns JSON string"""
        return json.dumps(self.response_data)


class TestTreatmentResponseExtractor(unittest.TestCase):
    """Test TreatmentResponseExtractor class"""

    def setUp(self):
        """Set up test timeline events"""
        self.timeline_events = [
            {
                'event_type': 'surgery',
                'event_date': '2024-01-15',
                'description': 'Craniotomy for tumor resection'
            },
            {
                'event_type': 'chemotherapy',
                'event_date': '2024-02-01',
                'description': 'Started TMZ'
            },
            {
                'event_type': 'imaging',
                'event_date': '2024-03-15',
                'imaging_modality': 'MRI Brain'
            }
        ]

    def test_initialization(self):
        """Test extractor initialization"""
        agent = MockMedGemmaAgent()
        extractor = TreatmentResponseExtractor(medgemma_agent=agent)
        self.assertIsNotNone(extractor)

    def test_extract_stable_response(self):
        """Test extracting stable disease response"""
        mock_response = {
            "response_detected": True,
            "response_category": "stable",
            "qualitative_description": "No significant interval change",
            "extracted_from_text": "stable postoperative changes",
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TreatmentResponseExtractor(medgemma_agent=agent)

        report_text = "MRI Brain: Stable postoperative changes. No significant interval change from prior study."
        imaging_date = "2024-03-15"

        response = extractor.extract_response(
            report_text=report_text,
            imaging_date=imaging_date,
            timeline_events=self.timeline_events
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.response_category, "stable")
        self.assertEqual(response.assessment_method, "qualitative")
        self.assertGreater(response.days_since_treatment_start, 0)

    def test_extract_improved_response(self):
        """Test extracting improved/decreased response"""
        mock_response = {
            "response_detected": True,
            "response_category": "improved",
            "qualitative_description": "Decreased tumor size",
            "extracted_from_text": "tumor decreased from 3.1 to 2.8 cm",
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TreatmentResponseExtractor(medgemma_agent=agent)

        report_text = "MRI Brain: Residual tumor decreased from 3.1 to 2.8 cm. Improved from prior."
        imaging_date = "2024-03-15"

        response = extractor.extract_response(
            report_text=report_text,
            imaging_date=imaging_date,
            timeline_events=self.timeline_events
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.response_category, "improved")

    def test_extract_worse_response(self):
        """Test extracting progressive disease response"""
        mock_response = {
            "response_detected": True,
            "response_category": "worse",
            "qualitative_description": "Increased tumor size",
            "extracted_from_text": "tumor increased to 3.5 cm",
            "extraction_confidence": "HIGH"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TreatmentResponseExtractor(medgemma_agent=agent)

        report_text = "MRI Brain: Tumor increased in size to 3.5 cm. Progressive disease."
        imaging_date = "2024-03-15"

        response = extractor.extract_response(
            report_text=report_text,
            imaging_date=imaging_date,
            timeline_events=self.timeline_events
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.response_category, "worse")

    def test_no_response_detected(self):
        """Test when no treatment response language found"""
        mock_response = {
            "response_detected": False,
            "extraction_confidence": "LOW"
        }

        agent = MockMedGemmaAgent(response_data=mock_response)
        extractor = TreatmentResponseExtractor(medgemma_agent=agent)

        report_text = "MRI Brain: Routine follow-up imaging. Technical quality good."
        imaging_date = "2024-03-15"

        response = extractor.extract_response(
            report_text=report_text,
            imaging_date=imaging_date,
            timeline_events=self.timeline_events
        )

        self.assertIsNone(response)

    def test_find_recent_treatment_surgery(self):
        """Test finding most recent treatment (surgery)"""
        extractor = TreatmentResponseExtractor()

        imaging_date = "2024-03-15"
        treatment_context = extractor._find_recent_treatment(
            imaging_date=imaging_date,
            timeline_events=self.timeline_events
        )

        self.assertIsNotNone(treatment_context)
        # Should find chemotherapy (most recent before imaging)
        self.assertEqual(treatment_context['treatment_type'], 'chemotherapy')
        self.assertEqual(treatment_context['treatment_date'], '2024-02-01')
        self.assertGreater(treatment_context['days_since_treatment'], 0)

    def test_find_recent_treatment_none_before_imaging(self):
        """Test when no treatment before imaging date"""
        extractor = TreatmentResponseExtractor()

        # Imaging BEFORE any treatment
        imaging_date = "2024-01-01"
        treatment_context = extractor._find_recent_treatment(
            imaging_date=imaging_date,
            timeline_events=self.timeline_events
        )

        self.assertIsNone(treatment_context)

    def test_find_recent_treatment_within_year(self):
        """Test treatment must be within 1 year"""
        extractor = TreatmentResponseExtractor()

        # Old treatment (>1 year ago)
        old_timeline = [
            {
                'event_type': 'surgery',
                'event_date': '2022-01-15',  # 2+ years ago
            }
        ]

        imaging_date = "2024-03-15"
        treatment_context = extractor._find_recent_treatment(
            imaging_date=imaging_date,
            timeline_events=old_timeline
        )

        # Should not find treatment >365 days ago
        self.assertIsNone(treatment_context)

    def test_no_agent_returns_none(self):
        """Test that extractor without agent returns None"""
        extractor = TreatmentResponseExtractor(medgemma_agent=None)

        response = extractor.extract_response(
            report_text="Some report text that is long enough for extraction",
            imaging_date="2024-03-15",
            timeline_events=self.timeline_events
        )

        self.assertIsNone(response)

    def test_short_report_returns_none(self):
        """Test that short report returns None"""
        agent = MockMedGemmaAgent()
        extractor = TreatmentResponseExtractor(medgemma_agent=agent)

        response = extractor.extract_response(
            report_text="Short",
            imaging_date="2024-03-15",
            timeline_events=self.timeline_events
        )

        self.assertIsNone(response)

    def test_build_extraction_prompt(self):
        """Test prompt building with treatment context"""
        extractor = TreatmentResponseExtractor()

        treatment_context = {
            'treatment_type': 'surgery',
            'treatment_date': '2024-01-15',
            'days_since_treatment': 60
        }

        report_text = "MRI Brain: Stable postoperative changes."
        imaging_date = "2024-03-15"

        prompt = extractor._build_extraction_prompt(
            report_text=report_text,
            imaging_date=imaging_date,
            treatment_context=treatment_context
        )

        # Check key elements in prompt
        self.assertIn("surgery", prompt)
        self.assertIn("2024-01-15", prompt)
        self.assertIn("60 days", prompt)
        self.assertIn("RESPONSE CATEGORIES", prompt)
        self.assertIn("improved", prompt)
        self.assertIn("stable", prompt)
        self.assertIn("worse", prompt)
        self.assertIn(report_text, prompt)

    def test_parse_markdown_json(self):
        """Test parsing JSON with markdown code blocks"""
        extractor = TreatmentResponseExtractor()

        markdown_response = """```json
{
  "response_detected": true,
  "response_category": "stable",
  "extraction_confidence": "HIGH"
}
```"""

        result = extractor._parse_llm_response(markdown_response)

        self.assertIsNotNone(result)
        self.assertTrue(result['response_detected'])
        self.assertEqual(result['response_category'], 'stable')

    def test_parse_invalid_json_returns_none(self):
        """Test that invalid JSON returns None"""
        extractor = TreatmentResponseExtractor()

        invalid_json = "This is not JSON!"
        result = extractor._parse_llm_response(invalid_json)

        self.assertIsNone(result)


    def test_semantic_validation_valid_response(self):
        """Test semantic validation passes for valid response"""
        extractor = TreatmentResponseExtractor()

        valid_result = {
            'response_detected': True,
            'response_category': 'stable',
            'qualitative_description': 'No significant interval change',
            'extracted_from_text': 'stable postoperative changes',
            'extraction_confidence': 'HIGH'
        }

        is_valid, errors = extractor._validate_semantic_quality(valid_result)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_semantic_validation_detects_operative_note(self):
        """Test semantic validation detects operative note document"""
        extractor = TreatmentResponseExtractor()

        # Simulated operative note sent to response extraction
        invalid_result = {
            'response_detected': True,
            'response_category': 'stable',
            'qualitative_description': 'procedure performed under anesthesia with incision made',
            'extracted_from_text': 'operative findings included tumor resection',
            'extraction_confidence': 'MEDIUM'
        }

        is_valid, errors = extractor._validate_semantic_quality(invalid_result)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_semantic_validation_detects_long_description(self):
        """Test semantic validation detects suspiciously long description"""
        extractor = TreatmentResponseExtractor()

        invalid_result = {
            'response_detected': True,
            'response_category': 'stable',
            'qualitative_description': 'a' * 550,  # 550 character description (too long)
            'extracted_from_text': 'stable',
            'extraction_confidence': 'HIGH'
        }

        is_valid, errors = extractor._validate_semantic_quality(invalid_result)
        self.assertFalse(is_valid)
        self.assertIn('too long', errors[0])

    def test_semantic_validation_detects_missing_category(self):
        """Test semantic validation detects missing category when detected=true"""
        extractor = TreatmentResponseExtractor()

        invalid_result = {
            'response_detected': True,
            # Missing response_category!
            'qualitative_description': 'stable appearance',
            'extraction_confidence': 'HIGH'
        }

        is_valid, errors = extractor._validate_semantic_quality(invalid_result)
        self.assertFalse(is_valid)
        self.assertIn('no category provided', errors[0])


if __name__ == '__main__':
    unittest.main()
