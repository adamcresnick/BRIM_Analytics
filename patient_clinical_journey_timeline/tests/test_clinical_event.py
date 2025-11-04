"""
Unit Tests for Clinical Event Data Models (V4.2)

Tests the ClinicalEvent, TumorMeasurement, and TreatmentResponse dataclasses
to ensure validation, serialization, and type safety work correctly.

Created: 2025-11-03
Author: RADIANT PCA Engineering Team
"""

import unittest
import json
from datetime import datetime
from typing import Dict, Any

import sys
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from clinical_event import (
    ClinicalEvent,
    TumorMeasurement,
    TreatmentResponse,
    EventType,
    TreatmentCategory,
    create_surgery_event,
    create_imaging_event,
    create_pathology_event,
)


class TestTumorMeasurement(unittest.TestCase):
    """Test TumorMeasurement dataclass"""

    def test_bidimensional_measurement_valid(self):
        """Test valid bidimensional measurement"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="right frontal lobe",
            measurement_type="bidimensional",
            longest_diameter_mm=30.0,
            perpendicular_diameter_mm=20.0,
            extracted_from_text="enhancing mass 3.0 x 2.0 cm"
        )

        # Validation should pass
        errors = measurement.validate()
        self.assertEqual(len(errors), 0, f"Validation failed: {errors}")

        # to_dict should auto-calculate cross-sectional area
        result = measurement.to_dict()
        self.assertEqual(result['cross_sectional_area_mm2'], 600.0)

    def test_bidimensional_measurement_invalid_diameters(self):
        """Test bidimensional with longest < perpendicular (invalid)"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="frontal lobe",
            measurement_type="bidimensional",
            longest_diameter_mm=20.0,  # Smaller than perpendicular!
            perpendicular_diameter_mm=30.0,
        )

        errors = measurement.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Longest diameter must be >=" in err for err in errors))

    def test_bidimensional_measurement_missing_diameter(self):
        """Test bidimensional missing perpendicular diameter"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="frontal lobe",
            measurement_type="bidimensional",
            longest_diameter_mm=30.0,
            # perpendicular_diameter_mm missing!
        )

        errors = measurement.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("require both diameters" in err for err in errors))

    def test_volumetric_measurement_valid(self):
        """Test valid volumetric measurement"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="temporal lobe",
            measurement_type="volumetric",
            volume_mm3=15000.0,
            extracted_from_text="tumor volume 15 cc"
        )

        errors = measurement.validate()
        self.assertEqual(len(errors), 0)

    def test_volumetric_measurement_missing_volume(self):
        """Test volumetric measurement missing volume"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="temporal lobe",
            measurement_type="volumetric",
            # volume_mm3 missing!
        )

        errors = measurement.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("require volume_mm3" in err for err in errors))

    def test_qualitative_measurement_valid(self):
        """Test valid qualitative measurement"""
        measurement = TumorMeasurement(
            lesion_id="non_target_1",
            location="corpus callosum",
            measurement_type="qualitative",
            qualitative_assessment="stable",
            extracted_from_text="stable T2/FLAIR abnormality"
        )

        errors = measurement.validate()
        self.assertEqual(len(errors), 0)

    def test_qualitative_measurement_missing_assessment(self):
        """Test qualitative measurement missing assessment"""
        measurement = TumorMeasurement(
            lesion_id="non_target_1",
            location="corpus callosum",
            measurement_type="qualitative",
            # qualitative_assessment missing!
        )

        errors = measurement.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("require qualitative_assessment" in err for err in errors))

    def test_invalid_measurement_type(self):
        """Test invalid measurement type"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="frontal lobe",
            measurement_type="invalid_type",  # Invalid!
        )

        errors = measurement.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Invalid measurement_type" in err for err in errors))

    def test_to_dict_excludes_none(self):
        """Test that to_dict() excludes None values"""
        measurement = TumorMeasurement(
            lesion_id="target_1",
            location="frontal lobe",
            measurement_type="bidimensional",
            longest_diameter_mm=30.0,
            perpendicular_diameter_mm=20.0,
            # volume_mm3 is None (should be excluded)
        )

        result = measurement.to_dict()
        self.assertNotIn('volume_mm3', result)
        self.assertIn('cross_sectional_area_mm2', result)


class TestTreatmentResponse(unittest.TestCase):
    """Test TreatmentResponse dataclass"""

    def test_qualitative_response_valid(self):
        """Test valid qualitative response (V4.2)"""
        response = TreatmentResponse(
            response_category="stable",
            assessment_method="qualitative",
            qualitative_description="Stable postoperative changes",
            clinical_context="post-surgery",
            days_since_treatment_start=92,
            confidence="HIGH"
        )

        errors = response.validate()
        self.assertEqual(len(errors), 0)

    def test_rano_response_valid(self):
        """Test valid RANO response (V5.0)"""
        response = TreatmentResponse(
            response_category="PR",  # Partial Response
            assessment_method="rano_criteria",
            sum_of_products=450.0,
            percent_change=-52.3,
            new_lesions=False,
            baseline_study_id="DiagnosticReport/abc123",
            days_since_treatment_start=120,
            confidence="HIGH"
        )

        errors = response.validate()
        self.assertEqual(len(errors), 0)

    def test_invalid_response_category(self):
        """Test invalid response category"""
        response = TreatmentResponse(
            response_category="invalid_category",  # Invalid!
            assessment_method="qualitative"
        )

        errors = response.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Invalid response_category" in err for err in errors))

    def test_to_dict_excludes_none(self):
        """Test that to_dict() excludes None values"""
        response = TreatmentResponse(
            response_category="stable",
            assessment_method="qualitative",
            qualitative_description="Stable disease",
            # sum_of_products is None (should be excluded)
        )

        result = response.to_dict()
        self.assertNotIn('sum_of_products', result)
        self.assertIn('qualitative_description', result)


class TestClinicalEvent(unittest.TestCase):
    """Test ClinicalEvent base class"""

    def test_surgery_event_valid(self):
        """Test valid surgery event"""
        event = ClinicalEvent(
            event_type=EventType.SURGERY.value,
            event_date="2024-01-15",
            stage=2,
            source="v_procedures_tumor",
            surgery_type="craniotomy_tumor_resection",
            description="Craniotomy for tumor resection"
        )

        errors = event.validate()
        self.assertEqual(len(errors), 0, f"Validation failed: {errors}")

    def test_surgery_event_missing_surgery_type(self):
        """Test surgery event missing required surgery_type"""
        event = ClinicalEvent(
            event_type=EventType.SURGERY.value,
            event_date="2024-01-15",
            stage=2,
            source="v_procedures_tumor",
            # surgery_type missing!
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("require surgery_type" in err for err in errors))

    def test_imaging_event_valid(self):
        """Test valid imaging event"""
        event = ClinicalEvent(
            event_type=EventType.IMAGING.value,
            event_date="2024-02-01",
            stage=5,
            source="v_imaging",
            imaging_modality="MRI Brain",
            description="MRI Brain with contrast"
        )

        errors = event.validate()
        self.assertEqual(len(errors), 0)

    def test_imaging_event_missing_modality(self):
        """Test imaging event missing imaging_modality"""
        event = ClinicalEvent(
            event_type=EventType.IMAGING.value,
            event_date="2024-02-01",
            stage=5,
            source="v_imaging",
            # imaging_modality missing!
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("require imaging_modality" in err for err in errors))

    def test_invalid_event_type(self):
        """Test invalid event type"""
        event = ClinicalEvent(
            event_type="invalid_type",  # Invalid!
            event_date="2024-01-15",
            stage=2,
            source="test"
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Invalid event_type" in err for err in errors))

    def test_invalid_stage(self):
        """Test invalid stage number"""
        event = ClinicalEvent(
            event_type=EventType.SURGERY.value,
            event_date="2024-01-15",
            stage=10,  # Invalid! Must be 0-6
            source="test",
            surgery_type="craniotomy"
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Invalid stage" in err for err in errors))

    def test_invalid_date_format(self):
        """Test invalid date format"""
        event = ClinicalEvent(
            event_type=EventType.SURGERY.value,
            event_date="01/15/2024",  # Invalid format!
            stage=2,
            source="test",
            surgery_type="craniotomy"
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Invalid event_date format" in err for err in errors))

    def test_chemotherapy_event_with_line_number(self):
        """Test chemotherapy event with V4 ordinality"""
        event = ClinicalEvent(
            event_type="chemotherapy",
            event_date="2024-03-01",
            stage=3,
            source="v_chemotherapy_regimen",
            line_number=2,
            regimen_summary="TMZ + Nivolumab",
            drug_list=["Temozolomide", "Nivolumab"]
        )

        errors = event.validate()
        self.assertEqual(len(errors), 0)

    def test_chemotherapy_invalid_line_number(self):
        """Test chemotherapy with invalid line_number"""
        event = ClinicalEvent(
            event_type="chemotherapy",
            event_date="2024-03-01",
            stage=3,
            source="v_chemotherapy_regimen",
            line_number=0,  # Invalid! Must be >= 1
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("line_number must be >= 1" in err for err in errors))

    def test_radiation_event_with_course_number(self):
        """Test radiation event with V4 ordinality"""
        event = ClinicalEvent(
            event_type="radiation",
            event_date="2024-04-01",
            stage=4,
            source="v_radiation_episodes",
            course_number=1,
            total_dose=54.0,
            dose_unit="Gy",
            fractions=30
        )

        errors = event.validate()
        self.assertEqual(len(errors), 0)

    def test_event_with_tumor_measurements(self):
        """Test imaging event with tumor measurements (V4.2)"""
        measurements = [
            TumorMeasurement(
                lesion_id="target_1",
                location="frontal lobe",
                measurement_type="bidimensional",
                longest_diameter_mm=28.0,
                perpendicular_diameter_mm=21.0
            )
        ]

        event = ClinicalEvent(
            event_type=EventType.IMAGING.value,
            event_date="2024-05-01",
            stage=5,
            source="v_imaging",
            imaging_modality="MRI Brain",
            tumor_measurements=[m.to_dict() for m in measurements]
        )

        errors = event.validate()
        self.assertEqual(len(errors), 0)

    def test_event_with_invalid_tumor_measurement(self):
        """Test event with invalid tumor measurement triggers validation"""
        # Create invalid measurement (bidimensional missing diameter)
        invalid_measurement = {
            "lesion_id": "target_1",
            "location": "frontal lobe",
            "measurement_type": "bidimensional",
            "longest_diameter_mm": 30.0,
            # perpendicular_diameter_mm missing!
        }

        event = ClinicalEvent(
            event_type=EventType.IMAGING.value,
            event_date="2024-05-01",
            stage=5,
            source="v_imaging",
            imaging_modality="MRI Brain",
            tumor_measurements=[invalid_measurement]
        )

        errors = event.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Measurement 0" in err for err in errors))

    def test_event_with_treatment_response(self):
        """Test imaging event with treatment response (V4.2)"""
        response = TreatmentResponse(
            response_category="stable",
            assessment_method="qualitative",
            qualitative_description="Stable postoperative changes",
            clinical_context="post-surgery",
            days_since_treatment_start=60
        )

        event = ClinicalEvent(
            event_type=EventType.IMAGING.value,
            event_date="2024-06-01",
            stage=5,
            source="v_imaging",
            imaging_modality="MRI Brain",
            treatment_response=response.to_dict()
        )

        errors = event.validate()
        self.assertEqual(len(errors), 0)

    def test_to_dict_excludes_none(self):
        """Test that to_dict() excludes None values"""
        event = ClinicalEvent(
            event_type=EventType.SURGERY.value,
            event_date="2024-01-15",
            stage=2,
            source="v_procedures_tumor",
            surgery_type="craniotomy",
            # Many fields are None (should be excluded)
        )

        result = event.to_dict()
        self.assertNotIn('imaging_modality', result)
        self.assertNotIn('tumor_measurements', result)
        self.assertIn('surgery_type', result)

    def test_from_dict(self):
        """Test creating ClinicalEvent from dictionary"""
        data = {
            "event_type": EventType.SURGERY.value,
            "event_date": "2024-01-15",
            "stage": 2,
            "source": "v_procedures_tumor",
            "surgery_type": "craniotomy",
            "description": "Initial resection"
        }

        event = ClinicalEvent.from_dict(data)
        self.assertEqual(event.event_type, EventType.SURGERY.value)
        self.assertEqual(event.surgery_type, "craniotomy")


class TestFactoryFunctions(unittest.TestCase):
    """Test factory functions for creating events"""

    def test_create_surgery_event(self):
        """Test create_surgery_event factory"""
        event = create_surgery_event(
            event_date="2024-01-15",
            surgery_type="craniotomy_tumor_resection",
            description="Initial resection",
            clinical_features={
                "institution": {
                    "value": "Children's Hospital of Philadelphia",
                    "sources": []
                }
            }
        )

        self.assertEqual(event.event_type, EventType.SURGERY.value)
        self.assertEqual(event.stage, 2)
        self.assertEqual(event.surgery_type, "craniotomy_tumor_resection")
        self.assertIsNotNone(event.clinical_features)

    def test_create_imaging_event(self):
        """Test create_imaging_event factory"""
        measurements = [
            TumorMeasurement(
                lesion_id="target_1",
                location="frontal lobe",
                measurement_type="bidimensional",
                longest_diameter_mm=30.0,
                perpendicular_diameter_mm=20.0
            )
        ]

        response = TreatmentResponse(
            response_category="stable",
            assessment_method="qualitative",
            qualitative_description="Stable disease"
        )

        event = create_imaging_event(
            event_date="2024-02-01",
            imaging_modality="MRI Brain",
            description="Follow-up MRI",
            tumor_measurements=measurements,
            treatment_response=response
        )

        self.assertEqual(event.event_type, EventType.IMAGING.value)
        self.assertEqual(event.imaging_modality, "MRI Brain")
        self.assertIsNotNone(event.tumor_measurements)
        self.assertIsNotNone(event.treatment_response)

    def test_create_pathology_event(self):
        """Test create_pathology_event factory"""
        event = create_pathology_event(
            event_date="2024-01-20",
            specimen_type="brain_biopsy",
            description="Surgical pathology"
        )

        self.assertEqual(event.event_type, EventType.PATHOLOGY.value)
        self.assertEqual(event.specimen_type, "brain_biopsy")


class TestJSONSerialization(unittest.TestCase):
    """Test JSON serialization of events"""

    def test_event_serializes_to_json(self):
        """Test that events can be serialized to JSON"""
        event = create_surgery_event(
            event_date="2024-01-15",
            surgery_type="craniotomy",
            description="Initial resection"
        )

        # Convert to dict and then to JSON
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict, indent=2)

        # Should be valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(parsed['event_type'], EventType.SURGERY.value)
        self.assertEqual(parsed['surgery_type'], "craniotomy")

    def test_complex_event_with_measurements_serializes(self):
        """Test complex event with measurements serializes correctly"""
        measurements = [
            TumorMeasurement(
                lesion_id="target_1",
                location="frontal lobe",
                measurement_type="bidimensional",
                longest_diameter_mm=30.0,
                perpendicular_diameter_mm=20.0,
                extracted_from_text="mass 3.0 x 2.0 cm"
            )
        ]

        response = TreatmentResponse(
            response_category="stable",
            assessment_method="qualitative",
            qualitative_description="Stable disease",
            days_since_treatment_start=90
        )

        event = create_imaging_event(
            event_date="2024-02-01",
            imaging_modality="MRI Brain",
            tumor_measurements=measurements,
            treatment_response=response,
            clinical_features={
                "institution": {
                    "value": "CHOP",
                    "sources": []
                }
            },
            v2_annotation={
                "binary_content_id": "Binary/123",
                "encounter_id": "Encounter/456"
            }
        )

        # Serialize
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict, indent=2)
        parsed = json.loads(json_str)

        # Validate structure
        self.assertIn('tumor_measurements', parsed)
        self.assertEqual(len(parsed['tumor_measurements']), 1)
        self.assertEqual(parsed['tumor_measurements'][0]['cross_sectional_area_mm2'], 600.0)

        self.assertIn('treatment_response', parsed)
        self.assertEqual(parsed['treatment_response']['response_category'], 'stable')

        self.assertIn('clinical_features', parsed)
        self.assertIn('v2_annotation', parsed)


if __name__ == '__main__':
    unittest.main()
