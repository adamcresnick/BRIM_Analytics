"""
Phase 5: Cross-Source Validation Framework
==========================================
Validates BRIM extractions against structured data and identifies discrepancies
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrossSourceValidator:
    """
    Validates extracted information across multiple sources:
    1. BRIM extractions from unstructured text
    2. Structured data from Athena tables
    3. Clinical timeline from integrated sources
    """

    # Validation rules and tolerances
    VALIDATION_RULES = {
        'date_tolerance_days': 7,  # Allow 7-day difference in dates
        'numeric_tolerance_percent': 0.1,  # 10% tolerance for numeric values
        'string_similarity_threshold': 0.85,  # 85% similarity for text matching
        'confidence_threshold': 0.7  # Minimum confidence for BRIM extractions
    }

    # Field mappings between BRIM and structured data
    FIELD_MAPPINGS = {
        'extent_of_resection': {
            'structured_source': 'procedures',
            'structured_field': 'proc_code_text',
            'validation_type': 'categorical',
            'categories': {
                'gross total': ['gross total', 'gtr', 'complete resection'],
                'subtotal': ['subtotal', 'str', 'near total'],
                'partial': ['partial', 'debulking'],
                'biopsy': ['biopsy', 'stereotactic']
            }
        },
        'tumor_histology': {
            'structured_source': 'diagnoses',
            'structured_field': 'diagnosis_name',
            'validation_type': 'text_match',
            'keywords': ['astrocytoma', 'glioma', 'medulloblastoma', 'ependymoma']
        },
        'molecular_markers': {
            'structured_source': 'molecular_tests',
            'structured_field': 'test_result',
            'validation_type': 'presence',
            'markers': ['BRAF', 'IDH1', 'IDH2', 'H3K27M', 'MGMT']
        },
        'chemotherapy_drugs': {
            'structured_source': 'medications',
            'structured_field': 'medication_name',
            'validation_type': 'list_match'
        },
        'radiation_dose': {
            'structured_source': 'radiation',
            'structured_field': 'total_dose',
            'validation_type': 'numeric',
            'unit': 'Gy'
        },
        'survival_status': {
            'structured_source': 'encounters',
            'structured_field': 'last_contact',
            'validation_type': 'date_check'
        }
    }

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)
        self.output_base = self.staging_path.parent / "outputs"
        self.output_base.mkdir(exist_ok=True)

    def validate_extraction_results(self, patient_id: str,
                                   brim_results: Dict,
                                   clinical_timeline: Dict) -> Dict:
        """
        Validate BRIM extraction results against structured data

        Args:
            patient_id: Patient identifier
            brim_results: Results from Phase 4 BRIM extraction
            clinical_timeline: Integrated timeline from Phase 2

        Returns:
            Validation report with discrepancies and confidence scores
        """
        logger.info(f"Starting cross-source validation for patient {patient_id}")

        # Load structured data
        structured_data = self._load_structured_data(patient_id)

        # Initialize validation report
        validation_report = {
            'patient_id': patient_id,
            'validation_date': datetime.now().isoformat(),
            'validations': {},
            'discrepancies': [],
            'statistics': {
                'total_fields': 0,
                'validated_fields': 0,
                'matched_fields': 0,
                'discrepant_fields': 0,
                'missing_in_structured': 0,
                'missing_in_extracted': 0
            }
        }

        # Validate each extracted variable
        for var_name, var_result in brim_results.get('variables', {}).items():
            if var_name in self.FIELD_MAPPINGS:
                validation = self._validate_field(
                    var_name,
                    var_result,
                    structured_data,
                    clinical_timeline
                )
                validation_report['validations'][var_name] = validation
                validation_report['statistics']['total_fields'] += 1

                if validation['status'] != 'not_validated':
                    validation_report['statistics']['validated_fields'] += 1

                    if validation['match_status'] == 'matched':
                        validation_report['statistics']['matched_fields'] += 1
                    elif validation['match_status'] == 'discrepant':
                        validation_report['statistics']['discrepant_fields'] += 1
                        validation_report['discrepancies'].append({
                            'field': var_name,
                            'extracted_value': validation.get('extracted_value'),
                            'structured_value': validation.get('structured_value'),
                            'discrepancy_type': validation.get('discrepancy_type'),
                            'severity': self._assess_discrepancy_severity(validation)
                        })

        # Calculate validation metrics
        validation_report['metrics'] = self._calculate_validation_metrics(validation_report)

        # Generate recommendations
        validation_report['recommendations'] = self._generate_recommendations(validation_report)

        # Save validation report
        report_path = self.output_base / f"validation_report_{patient_id}.json"
        with open(report_path, 'w') as f:
            json.dump(validation_report, f, indent=2)

        logger.info(f"Validation complete: {validation_report['metrics']['accuracy']:.1%} accuracy")

        return validation_report

    def _load_structured_data(self, patient_id: str) -> Dict[str, pd.DataFrame]:
        """Load all structured data sources for validation"""
        structured_data = {}
        patient_path = self.staging_path / f"patient_{patient_id}"

        # Define data sources to load
        data_sources = [
            'procedures', 'diagnoses', 'medications',
            'imaging', 'encounters', 'molecular_tests_metadata',
            'problem_list', 'observations'
        ]

        for source in data_sources:
            file_path = patient_path / f"{source}.csv"
            if file_path.exists():
                structured_data[source] = pd.read_csv(file_path)
                logger.info(f"Loaded {len(structured_data[source])} records from {source}")
            else:
                structured_data[source] = pd.DataFrame()

        return structured_data

    def _validate_field(self, field_name: str,
                       brim_result: Dict,
                       structured_data: Dict[str, pd.DataFrame],
                       timeline: Dict) -> Dict:
        """Validate a single field against structured data"""

        mapping = self.FIELD_MAPPINGS[field_name]
        validation_type = mapping['validation_type']

        validation = {
            'field': field_name,
            'validation_type': validation_type,
            'timestamp': datetime.now().isoformat(),
            'status': 'validated',
            'match_status': 'unknown'
        }

        # Get extracted value from BRIM
        if 'extraction' in brim_result:
            extracted_value = brim_result['extraction'].get('value')
            extraction_confidence = brim_result['extraction'].get('confidence', 0)
            validation['extracted_value'] = extracted_value
            validation['extraction_confidence'] = extraction_confidence
        else:
            validation['status'] = 'not_validated'
            validation['reason'] = 'No BRIM extraction found'
            return validation

        # Get structured data source
        source_name = mapping['structured_source']
        if source_name not in structured_data or structured_data[source_name].empty:
            validation['status'] = 'not_validated'
            validation['reason'] = f'No structured data in {source_name}'
            return validation

        source_df = structured_data[source_name]

        # Perform validation based on type
        if validation_type == 'categorical':
            validation = self._validate_categorical(validation, extracted_value, source_df, mapping)
        elif validation_type == 'text_match':
            validation = self._validate_text_match(validation, extracted_value, source_df, mapping)
        elif validation_type == 'numeric':
            validation = self._validate_numeric(validation, extracted_value, source_df, mapping)
        elif validation_type == 'date_check':
            validation = self._validate_date(validation, extracted_value, source_df, mapping, timeline)
        elif validation_type == 'list_match':
            validation = self._validate_list(validation, extracted_value, source_df, mapping)
        elif validation_type == 'presence':
            validation = self._validate_presence(validation, extracted_value, source_df, mapping)

        return validation

    def _validate_categorical(self, validation: Dict, extracted_value: str,
                             source_df: pd.DataFrame, mapping: Dict) -> Dict:
        """Validate categorical values"""

        # Normalize extracted value
        extracted_norm = str(extracted_value).lower().strip()

        # Find category for extracted value
        extracted_category = None
        for category, terms in mapping['categories'].items():
            if any(term in extracted_norm for term in terms):
                extracted_category = category
                break

        # Search structured data
        field_name = mapping['structured_field']
        if field_name in source_df.columns:
            structured_values = source_df[field_name].dropna().astype(str)

            # Find category in structured data
            structured_category = None
            for value in structured_values:
                value_norm = value.lower().strip()
                for category, terms in mapping['categories'].items():
                    if any(term in value_norm for term in terms):
                        structured_category = category
                        break
                if structured_category:
                    break

            validation['structured_value'] = structured_category

            if extracted_category == structured_category:
                validation['match_status'] = 'matched'
            else:
                validation['match_status'] = 'discrepant'
                validation['discrepancy_type'] = 'category_mismatch'

        return validation

    def _validate_text_match(self, validation: Dict, extracted_value: str,
                            source_df: pd.DataFrame, mapping: Dict) -> Dict:
        """Validate text matching with fuzzy logic"""

        field_name = mapping['structured_field']
        if field_name not in source_df.columns:
            validation['status'] = 'not_validated'
            return validation

        # Get keywords to look for
        keywords = mapping.get('keywords', [])

        # Check extracted value for keywords
        extracted_keywords = []
        extracted_norm = str(extracted_value).lower()
        for keyword in keywords:
            if keyword.lower() in extracted_norm:
                extracted_keywords.append(keyword)

        # Check structured data for keywords
        structured_keywords = []
        structured_values = source_df[field_name].dropna().astype(str)
        for value in structured_values:
            value_norm = value.lower()
            for keyword in keywords:
                if keyword.lower() in value_norm and keyword not in structured_keywords:
                    structured_keywords.append(keyword)

        validation['extracted_keywords'] = extracted_keywords
        validation['structured_keywords'] = structured_keywords

        # Calculate similarity
        if extracted_keywords and structured_keywords:
            common = set(extracted_keywords) & set(structured_keywords)
            all_keywords = set(extracted_keywords) | set(structured_keywords)
            similarity = len(common) / len(all_keywords) if all_keywords else 0

            validation['similarity_score'] = similarity
            if similarity >= self.VALIDATION_RULES['string_similarity_threshold']:
                validation['match_status'] = 'matched'
            else:
                validation['match_status'] = 'partial_match'
        else:
            validation['match_status'] = 'no_keywords_found'

        return validation

    def _validate_numeric(self, validation: Dict, extracted_value: Any,
                         source_df: pd.DataFrame, mapping: Dict) -> Dict:
        """Validate numeric values with tolerance"""

        try:
            # Extract numeric value
            if isinstance(extracted_value, str):
                # Remove units and convert
                import re
                numeric_match = re.search(r'[\d.]+', str(extracted_value))
                if numeric_match:
                    extracted_num = float(numeric_match.group())
                else:
                    validation['status'] = 'not_validated'
                    validation['reason'] = 'Could not extract numeric value'
                    return validation
            else:
                extracted_num = float(extracted_value)

            validation['extracted_numeric'] = extracted_num

            # Get structured numeric value
            field_name = mapping['structured_field']
            if field_name in source_df.columns:
                structured_values = pd.to_numeric(source_df[field_name], errors='coerce').dropna()
                if not structured_values.empty:
                    structured_num = structured_values.iloc[0]  # Use first valid value
                    validation['structured_numeric'] = float(structured_num)

                    # Check tolerance
                    tolerance = self.VALIDATION_RULES['numeric_tolerance_percent']
                    diff_percent = abs(extracted_num - structured_num) / structured_num if structured_num != 0 else 0

                    validation['difference_percent'] = diff_percent

                    if diff_percent <= tolerance:
                        validation['match_status'] = 'matched'
                    else:
                        validation['match_status'] = 'discrepant'
                        validation['discrepancy_type'] = 'numeric_difference'

        except (ValueError, TypeError) as e:
            validation['status'] = 'not_validated'
            validation['reason'] = f'Numeric conversion error: {str(e)}'

        return validation

    def _validate_date(self, validation: Dict, extracted_value: Any,
                      source_df: pd.DataFrame, mapping: Dict,
                      timeline: Dict) -> Dict:
        """Validate dates with tolerance"""

        try:
            # Parse extracted date
            extracted_date = pd.to_datetime(extracted_value, utc=True)
            validation['extracted_date'] = extracted_date.isoformat()

            # Get date from timeline (most reliable source)
            if 'last_contact' in timeline:
                structured_date = pd.to_datetime(timeline['last_contact'], utc=True)
                validation['structured_date'] = structured_date.isoformat()

                # Check tolerance
                days_diff = abs((extracted_date - structured_date).days)
                validation['days_difference'] = days_diff

                if days_diff <= self.VALIDATION_RULES['date_tolerance_days']:
                    validation['match_status'] = 'matched'
                else:
                    validation['match_status'] = 'discrepant'
                    validation['discrepancy_type'] = 'date_difference'
            else:
                validation['status'] = 'not_validated'
                validation['reason'] = 'No structured date found'

        except Exception as e:
            validation['status'] = 'not_validated'
            validation['reason'] = f'Date parsing error: {str(e)}'

        return validation

    def _validate_list(self, validation: Dict, extracted_value: Any,
                      source_df: pd.DataFrame, mapping: Dict) -> Dict:
        """Validate list values (e.g., medications)"""

        # Parse extracted list
        if isinstance(extracted_value, str):
            extracted_list = [item.strip() for item in extracted_value.split(',')]
        elif isinstance(extracted_value, list):
            extracted_list = extracted_value
        else:
            extracted_list = [str(extracted_value)]

        validation['extracted_list'] = extracted_list

        # Get structured list
        field_name = mapping['structured_field']
        if field_name in source_df.columns:
            structured_list = source_df[field_name].dropna().unique().tolist()
            validation['structured_list'] = structured_list

            # Normalize for comparison
            extracted_norm = set(item.lower() for item in extracted_list)
            structured_norm = set(str(item).lower() for item in structured_list)

            # Calculate overlap
            common = extracted_norm & structured_norm
            all_items = extracted_norm | structured_norm

            if all_items:
                overlap_ratio = len(common) / len(all_items)
                validation['overlap_ratio'] = overlap_ratio

                if overlap_ratio >= 0.5:  # At least 50% overlap
                    validation['match_status'] = 'matched'
                else:
                    validation['match_status'] = 'partial_match'

                validation['common_items'] = list(common)
                validation['extracted_only'] = list(extracted_norm - structured_norm)
                validation['structured_only'] = list(structured_norm - extracted_norm)
            else:
                validation['match_status'] = 'no_items'

        return validation

    def _validate_presence(self, validation: Dict, extracted_value: Any,
                          source_df: pd.DataFrame, mapping: Dict) -> Dict:
        """Validate presence of markers/features"""

        markers = mapping.get('markers', [])

        # Check extracted value for markers
        extracted_markers = []
        extracted_text = str(extracted_value).upper()
        for marker in markers:
            if marker.upper() in extracted_text:
                extracted_markers.append(marker)

        validation['extracted_markers'] = extracted_markers

        # Check structured data for markers
        field_name = mapping.get('structured_field', 'test_result')
        structured_markers = []

        if field_name in source_df.columns:
            for value in source_df[field_name].dropna():
                value_upper = str(value).upper()
                for marker in markers:
                    if marker.upper() in value_upper and marker not in structured_markers:
                        structured_markers.append(marker)

        validation['structured_markers'] = structured_markers

        # Compare presence
        if set(extracted_markers) == set(structured_markers):
            validation['match_status'] = 'matched'
        elif set(extracted_markers) & set(structured_markers):
            validation['match_status'] = 'partial_match'
        else:
            validation['match_status'] = 'discrepant'
            validation['discrepancy_type'] = 'marker_mismatch'

        return validation

    def _assess_discrepancy_severity(self, validation: Dict) -> str:
        """Assess the severity of a discrepancy"""

        # Critical discrepancies
        critical_fields = ['extent_of_resection', 'tumor_histology', 'survival_status']
        if validation['field'] in critical_fields:
            return 'critical'

        # High severity for low confidence extractions
        if validation.get('extraction_confidence', 1.0) < 0.5:
            return 'high'

        # Check discrepancy type
        discrepancy_type = validation.get('discrepancy_type', '')
        if discrepancy_type in ['date_difference', 'numeric_difference']:
            # Check magnitude
            if 'days_difference' in validation and validation['days_difference'] > 30:
                return 'high'
            if 'difference_percent' in validation and validation['difference_percent'] > 0.25:
                return 'high'

        # Default to medium
        return 'medium'

    def _calculate_validation_metrics(self, report: Dict) -> Dict:
        """Calculate validation performance metrics"""

        stats = report['statistics']

        metrics = {
            'accuracy': stats['matched_fields'] / stats['validated_fields']
                       if stats['validated_fields'] > 0 else 0,
            'validation_coverage': stats['validated_fields'] / stats['total_fields']
                                 if stats['total_fields'] > 0 else 0,
            'discrepancy_rate': stats['discrepant_fields'] / stats['validated_fields']
                              if stats['validated_fields'] > 0 else 0
        }

        # Severity distribution
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for discrepancy in report['discrepancies']:
            severity = discrepancy.get('severity', 'medium')
            severity_counts[severity] += 1

        metrics['severity_distribution'] = severity_counts

        # Field-specific accuracy
        field_accuracy = {}
        for field_name, validation in report['validations'].items():
            if validation['status'] == 'validated':
                field_accuracy[field_name] = 1.0 if validation['match_status'] == 'matched' else 0.0

        metrics['field_accuracy'] = field_accuracy

        return metrics

    def _generate_recommendations(self, report: Dict) -> List[Dict]:
        """Generate recommendations based on validation results"""

        recommendations = []

        # Check critical discrepancies
        critical_discrepancies = [
            d for d in report['discrepancies']
            if d.get('severity') == 'critical'
        ]

        if critical_discrepancies:
            recommendations.append({
                'priority': 'high',
                'type': 'manual_review',
                'message': f"Manual review required for {len(critical_discrepancies)} critical discrepancies",
                'fields': [d['field'] for d in critical_discrepancies]
            })

        # Check low confidence extractions
        low_confidence = []
        for field_name, validation in report['validations'].items():
            if validation.get('extraction_confidence', 1.0) < 0.7:
                low_confidence.append(field_name)

        if low_confidence:
            recommendations.append({
                'priority': 'medium',
                'type': 'improve_extraction',
                'message': f"Consider re-extraction or additional documents for {len(low_confidence)} low-confidence fields",
                'fields': low_confidence
            })

        # Check validation coverage
        metrics = report['metrics']
        if metrics['validation_coverage'] < 0.8:
            recommendations.append({
                'priority': 'low',
                'type': 'expand_validation',
                'message': f"Validation coverage is {metrics['validation_coverage']:.1%}. Consider adding more validation rules."
            })

        # Field-specific recommendations
        for field_name, accuracy in metrics.get('field_accuracy', {}).items():
            if accuracy < 0.5:
                recommendations.append({
                    'priority': 'medium',
                    'type': 'field_specific',
                    'field': field_name,
                    'message': f"Low accuracy ({accuracy:.1%}) for {field_name}. Review extraction logic."
                })

        return recommendations

    def generate_validation_summary(self, report: Dict) -> str:
        """Generate human-readable validation summary"""

        summary = []
        summary.append("="*70)
        summary.append("PHASE 5: CROSS-SOURCE VALIDATION SUMMARY")
        summary.append("="*70)
        summary.append(f"\nPatient ID: {report['patient_id']}")
        summary.append(f"Validation Date: {report['validation_date']}")

        # Metrics
        metrics = report['metrics']
        summary.append(f"\nValidation Metrics:")
        summary.append(f"  Overall Accuracy: {metrics['accuracy']:.1%}")
        summary.append(f"  Validation Coverage: {metrics['validation_coverage']:.1%}")
        summary.append(f"  Discrepancy Rate: {metrics['discrepancy_rate']:.1%}")

        # Severity distribution
        if 'severity_distribution' in metrics:
            summary.append(f"\nDiscrepancy Severity:")
            for severity, count in metrics['severity_distribution'].items():
                summary.append(f"  {severity.capitalize()}: {count}")

        # Field-specific results
        summary.append(f"\nField Validation Results:")
        summary.append("-"*40)

        for field_name, validation in report['validations'].items():
            status_icon = "✓" if validation.get('match_status') == 'matched' else "✗"
            confidence = validation.get('extraction_confidence', 0)
            summary.append(f"\n{status_icon} {field_name.upper().replace('_', ' ')}:")
            summary.append(f"  Status: {validation['match_status']}")
            summary.append(f"  Confidence: {confidence:.1%}")

            if 'extracted_value' in validation:
                summary.append(f"  Extracted: {validation['extracted_value']}")
            if 'structured_value' in validation:
                summary.append(f"  Structured: {validation['structured_value']}")

        # Critical discrepancies
        critical = [d for d in report['discrepancies'] if d.get('severity') == 'critical']
        if critical:
            summary.append(f"\n⚠️  CRITICAL DISCREPANCIES ({len(critical)}):")
            for disc in critical:
                summary.append(f"  - {disc['field']}: {disc.get('discrepancy_type', 'unknown')}")

        # Recommendations
        if report.get('recommendations'):
            summary.append(f"\nRecommendations:")
            for rec in report['recommendations']:
                priority_icon = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
                summary.append(f"  {priority_icon} {rec['message']}")

        summary.append("\n" + "="*70)

        summary_text = "\n".join(summary)

        # Save summary
        summary_path = self.output_base / f"validation_summary_{report['patient_id']}.txt"
        with open(summary_path, 'w') as f:
            f.write(summary_text)

        return summary_text


if __name__ == "__main__":
    # Test with our patient
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    output_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/multi_source_extraction_framework/outputs")

    validator = CrossSourceValidator(staging_path)

    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # Load BRIM results from Phase 4
    brim_results_file = output_path / f"brim_results_{patient_id}.json"
    if brim_results_file.exists():
        with open(brim_results_file, 'r') as f:
            brim_results = json.load(f)
    else:
        # Create sample BRIM results for testing
        brim_results = {
            'patient_id': patient_id,
            'variables': {
                'extent_of_resection': {
                    'extraction': {
                        'value': 'gross total resection',
                        'confidence': 0.95
                    }
                },
                'tumor_histology': {
                    'extraction': {
                        'value': 'Pilocytic astrocytoma, WHO Grade I',
                        'confidence': 0.98
                    }
                },
                'chemotherapy_drugs': {
                    'extraction': {
                        'value': 'Bevacizumab, Vinblastine, Selumetinib',
                        'confidence': 0.85
                    }
                }
            }
        }

    # Load clinical timeline from Phase 2
    timeline_file = output_path / f"integrated_timeline_{patient_id}.json"
    if timeline_file.exists():
        with open(timeline_file, 'r') as f:
            clinical_timeline = json.load(f)
    else:
        clinical_timeline = {
            'last_contact': '2025-07-29',
            'diagnosis_date': '2018-05-28'
        }

    # Run validation
    validation_report = validator.validate_extraction_results(
        patient_id,
        brim_results,
        clinical_timeline
    )

    # Generate summary
    summary = validator.generate_validation_summary(validation_report)
    print(summary)