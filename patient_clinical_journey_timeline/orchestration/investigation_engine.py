"""
Investigation Engine for Athena Query Failures

Investigates query failures, analyzes data quality issues, and proposes fixes.
This module would have automatically caught and fixed the date parsing error.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# V4.8.2: Lazy import for ChemotherapyValidator to avoid circular dependencies
_chemotherapy_validator = None


def get_chemotherapy_validator():
    """Lazy load chemotherapy validator to avoid import cycles"""
    global _chemotherapy_validator
    if _chemotherapy_validator is None:
        from orchestration.chemotherapy_validator import ChemotherapyValidator
        _chemotherapy_validator = ChemotherapyValidator()
    return _chemotherapy_validator


class InvestigationEngine:
    """
    Investigates Athena query failures and data quality issues.

    Capabilities:
    - Classify error types
    - Extract problematic values from error messages
    - Sample actual data to understand format issues
    - Generate SQL fixes for common problems
    - Provide confidence scores for automated fixes
    """

    def __init__(self, athena_client, schema_loader):
        """
        Initialize investigation engine.

        Args:
            athena_client: Boto3 Athena client
            schema_loader: AthenaSchemaLoader instance
        """
        self.athena = athena_client
        self.schema = schema_loader
        self.database = 'fhir_prd_db'

        # V4.7.4: WHO CNS Clinical Protocol Knowledge Base
        self._init_clinical_protocols()

    def investigate_query_failure(
        self,
        query_id: str,
        query_string: str,
        error_message: str
    ) -> Dict:
        """
        Main entry point for investigating query failures.

        Args:
            query_id: Athena query execution ID
            query_string: The SQL query that failed
            error_message: Error message from Athena

        Returns:
            Dict with investigation results, proposed fix, and confidence score
        """
        logger.info(f"Investigating query failure: {query_id}")

        investigation = {
            'query_id': query_id,
            'error_type': self._classify_error(error_message),
            'error_message': error_message,
            'root_cause': None,
            'affected_fields': [],
            'sample_data': {},
            'format_analysis': {},
            'proposed_fix': None,
            'confidence': 0.0,
            'auto_fixable': False
        }

        # Route to specific investigation based on error type
        if 'INVALID_FUNCTION_ARGUMENT' in error_message:
            investigation.update(
                self._investigate_invalid_function_argument(
                    query_string,
                    error_message
                )
            )
        elif 'SYNTAX_ERROR' in error_message:
            investigation.update(
                self._investigate_syntax_error(
                    query_string,
                    error_message
                )
            )
        elif 'COLUMN_NOT_FOUND' in error_message or 'Column' in error_message:
            investigation.update(
                self._investigate_missing_column(
                    query_string,
                    error_message
                )
            )

        # Determine if auto-fixable
        investigation['auto_fixable'] = investigation['confidence'] > 0.8

        return investigation

    def _classify_error(self, error_message: str) -> str:
        """Classify the type of error from message"""
        if 'INVALID_FUNCTION_ARGUMENT' in error_message:
            return 'INVALID_FUNCTION_ARGUMENT'
        elif 'SYNTAX_ERROR' in error_message:
            return 'SYNTAX_ERROR'
        elif 'COLUMN_NOT_FOUND' in error_message or 'Column' in error_message:
            return 'COLUMN_NOT_FOUND'
        elif 'TYPE_MISMATCH' in error_message:
            return 'TYPE_MISMATCH'
        else:
            return 'UNKNOWN'

    def _investigate_invalid_function_argument(
        self,
        query_string: str,
        error_message: str
    ) -> Dict:
        """
        Investigate INVALID_FUNCTION_ARGUMENT errors.

        This would have caught the date parsing error:
        "Invalid format: '2018-08-07' is too short"
        """
        # Extract the problematic value from error message
        value_match = re.search(r'"([^"]+)" is too short', error_message)
        if not value_match:
            value_match = re.search(r'Invalid format: "([^"]+)"', error_message)

        if not value_match:
            return {'confidence': 0.3}

        problematic_value = value_match.group(1)
        logger.info(f"Problematic value: {problematic_value}")

        # Identify if this is a date parsing issue
        if self._is_date_value(problematic_value):
            return self._investigate_date_parsing_error(
                query_string,
                problematic_value,
                error_message
            )

        return {'confidence': 0.4}

    def _is_date_value(self, value: str) -> bool:
        """Check if a value looks like a date"""
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO datetime
        ]

        return any(re.match(pattern, value) for pattern in date_patterns)

    def _investigate_date_parsing_error(
        self,
        query_string: str,
        problematic_date: str,
        error_message: str
    ) -> Dict:
        """
        Deep investigation of date parsing errors.

        This is the key function that would have caught the v_visits_unified error.
        """
        logger.info(f"Investigating date parsing error with value: {problematic_date}")

        # Step 1: Identify the date_parse() function call in the query
        date_parse_pattern = r'date_parse\(([^,]+),\s*\'([^\']+)\'\)'
        matches = re.findall(date_parse_pattern, query_string)

        if not matches:
            return {'confidence': 0.5}

        # Step 2: For each date_parse call, identify the field and format
        investigations = []
        for field_expr, format_str in matches:
            field_expr = field_expr.strip()

            # Extract table and column if possible
            table_col = self._extract_table_column(field_expr, query_string)

            if table_col:
                table, column = table_col

                # Step 3: Sample actual data from the field
                sample_data = self._sample_date_field(table, column)

                # Step 4: Analyze formats
                format_analysis = self._analyze_date_formats(sample_data)

                investigations.append({
                    'field': field_expr,
                    'table': table,
                    'column': column,
                    'current_format': format_str,
                    'sample_data': sample_data[:5],
                    'format_analysis': format_analysis
                })

        if not investigations:
            return {'confidence': 0.6}

        # Step 5: Find the investigation with the problematic value
        main_investigation = None
        for inv in investigations:
            if problematic_date in inv['sample_data']:
                main_investigation = inv
                break

        if not main_investigation:
            # Use the first one
            main_investigation = investigations[0]

        # Step 6: Generate fix
        formats = main_investigation['format_analysis']['formats']
        proposed_fix = self._generate_multi_format_date_fix(
            main_investigation['field'],
            formats
        )

        return {
            'root_cause': f"Field '{main_investigation['field']}' contains multiple date formats: {formats}",
            'affected_fields': [main_investigation['field']],
            'sample_data': {main_investigation['field']: main_investigation['sample_data']},
            'format_analysis': main_investigation['format_analysis'],
            'proposed_fix': proposed_fix,
            'confidence': 0.9,
            'fix_explanation': f"Replace single date_parse() with COALESCE() of multiple TRY(date_parse()) calls to handle all formats"
        }

    def _extract_table_column(self, field_expr: str, query_string: str) -> Optional[Tuple[str, str]]:
        """
        Extract table and column name from a field expression.

        Examples:
            'e.period_start' -> ('encounter', 'period_start')
            'a.start' -> ('appointment', 'start')
        """
        # Simple case: alias.column
        if '.' in field_expr:
            alias, column = field_expr.split('.', 1)

            # Find table for this alias in FROM/JOIN clauses
            table_pattern = rf'FROM\s+{self.database}\.(\w+)\s+{alias}\b'
            match = re.search(table_pattern, query_string, re.IGNORECASE)
            if match:
                return (match.group(1), column)

            join_pattern = rf'JOIN\s+{self.database}\.(\w+)\s+{alias}\b'
            match = re.search(join_pattern, query_string, re.IGNORECASE)
            if match:
                return (match.group(1), column)

        return None

    def _sample_date_field(self, table: str, column: str, limit: int = 20) -> List[str]:
        """
        Sample actual date values from a field.

        Args:
            table: Table name
            column: Column name
            limit: Number of samples

        Returns:
            List of distinct values
        """
        query = self.schema.generate_sample_query(table, column, limit)
        if not query:
            return []

        try:
            results = self._execute_query(query)
            return [r[column] for r in results if r.get(column)]
        except Exception as e:
            logger.error(f"Failed to sample field {table}.{column}: {e}")
            return []

    def _analyze_date_formats(self, date_values: List[str]) -> Dict:
        """
        Analyze date formats in a list of values.

        Returns:
            Dict with format analysis
        """
        formats_found = set()

        for value in date_values:
            if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', value):
                formats_found.add('YYYY-MM-DDTHH:MM:SSZ')
            elif re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
                formats_found.add('YYYY-MM-DDTHH:MM:SS')
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                formats_found.add('YYYY-MM-DD')

        return {
            'has_multiple_formats': len(formats_found) > 1,
            'formats': sorted(list(formats_found)),
            'sample_count': len(date_values)
        }

    def _generate_multi_format_date_fix(
        self,
        field_name: str,
        formats: List[str]
    ) -> str:
        """
        Generate SQL fix for a field with multiple date formats.

        This generates the COALESCE(TRY...) pattern that fixes the error.

        Args:
            field_name: Field expression (e.g., 'e.period_start')
            formats: List of detected formats

        Returns:
            SQL expression to replace the problematic date_parse()
        """
        format_patterns = {
            'YYYY-MM-DDTHH:MM:SSZ': '%Y-%m-%dT%H:%i:%sZ',
            'YYYY-MM-DDTHH:MM:SS': '%Y-%m-%dT%H:%i:%s',
            'YYYY-MM-DD': '%Y-%m-%d'
        }

        tries = []
        for fmt in formats:
            pattern = format_patterns.get(fmt)
            if pattern:
                tries.append(f"TRY(date_parse({field_name}, '{pattern}'))")

        if len(tries) > 1:
            return f"COALESCE(\n    {',\n    '.join(tries)}\n)"
        elif len(tries) == 1:
            return tries[0]
        else:
            return f"TRY(CAST({field_name} AS TIMESTAMP))"

    def _investigate_syntax_error(
        self,
        query_string: str,
        error_message: str
    ) -> Dict:
        """Investigate SQL syntax errors"""
        return {
            'root_cause': 'SQL syntax error',
            'confidence': 0.3
        }

    def _investigate_missing_column(
        self,
        query_string: str,
        error_message: str
    ) -> Dict:
        """Investigate missing column errors"""
        # Extract column name from error
        col_match = re.search(r"Column '([^']+)'", error_message)
        if col_match:
            missing_col = col_match.group(1)

            return {
                'root_cause': f"Column '{missing_col}' not found in table",
                'affected_fields': [missing_col],
                'confidence': 0.7
            }

        return {'confidence': 0.4}

    def _execute_query(self, query: str, suppress_output: bool = True) -> List[Dict]:
        """
        Execute an Athena query and return results.

        Args:
            query: SQL query string
            suppress_output: Whether to suppress logging

        Returns:
            List of result rows as dicts
        """
        import time

        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={
                    'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
                }
            )

            query_id = response['QueryExecutionId']

            # Wait for completion
            for _ in range(60):
                status = self.athena.get_query_execution(QueryExecutionId=query_id)
                state = status['QueryExecution']['Status']['State']

                if state == 'SUCCEEDED':
                    break
                elif state in ['FAILED', 'CANCELLED']:
                    if not suppress_output:
                        logger.error(f"Query failed: {status['QueryExecution']['Status'].get('StateChangeReason')}")
                    return []

                time.sleep(1)

            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_id)

            if len(results['ResultSet']['Rows']) <= 1:
                return []

            header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            rows = []

            for row in results['ResultSet']['Rows'][1:]:
                row_dict = {}
                for i, col in enumerate(row['Data']):
                    row_dict[header[i]] = col.get('VarCharValue', '')
                rows.append(row_dict)

            return rows

        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return []

    def investigate_gap_filling_failure(
        self,
        gap_type: str,
        event: Dict,
        reason: str,
        patient_context: Optional[Dict] = None
    ) -> Dict:
        """
        V4.6 GAP #1: Investigate why gap-filling failed (no source documents available).
        V4.7.4 ENHANCEMENT: Added clinical protocol validation via patient_context.

        This method is called when Phase 4.5 gap-filling can't find source_document_ids,
        typically because MedGemma extraction in Phase 4 failed validation.

        Args:
            gap_type: Type of gap (surgery_eor, radiation_dose, imaging_conclusion, no_postop_imaging)
            event: The event missing data
            reason: Why gap-filling failed
            patient_context: Optional patient context for clinical validation
                {
                    'who_diagnosis': str,
                    'tumor_type': str,
                    'molecular_markers': Dict,
                    'surgeries': List[Dict],
                    'timeline_events': List[Dict]
                }

        Returns:
            Dict with suggested alternative document sources + clinical validation
        """
        logger.info(f"Investigating gap-filling failure for {gap_type}: {reason}")

        investigation = {
            'gap_type': gap_type,
            'event_date': event.get('event_date'),
            'reason': reason,
            'root_cause': 'MedGemma extraction failed validation, so source_document_ids not populated',
            'explanation': None,
            'suggested_alternatives': [],
            'clinical_validation': None  # V4.7.4: Clinical protocol validation
        }

        # Suggest alternative document sources based on gap type
        # V4.6 ENHANCEMENT: Added core timeline gap types from Phase 2.1
        if gap_type == 'missing_surgeries':
            investigation['explanation'] = (
                "No surgery events found in v_procedures_tumor. "
                "Try alternative procedure types (biopsy, resection, debulking) or expanded temporal window."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'query_alternative_procedure_types',
                    'description': 'Search for biopsies, resections, debulking procedures',
                    'confidence': 0.85
                },
                {
                    'method': 'query_encounters_for_procedures',
                    'description': 'Look for surgical encounters without linked Procedure resources',
                    'confidence': 0.7
                }
            ]
        elif gap_type == 'missing_chemo_end_dates':
            investigation['explanation'] = (
                "Chemotherapy start found but no corresponding end date. "
                "Try v_medication_administration for last administration date or clinical notes."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'query_last_medication_administration',
                    'description': 'Find last MedicationAdministration for chemotherapy agents',
                    'confidence': 0.9
                },
                {
                    'method': 'search_clinical_notes_for_completion',
                    'description': 'Search clinical notes for "completed chemotherapy" or "last dose"',
                    'confidence': 0.6
                }
            ]
        elif gap_type == 'missing_radiation_end_dates':
            investigation['explanation'] = (
                "Radiation start found but no corresponding end date. "
                "Try v_radiation_documents for completion summaries."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'query_radiation_completion_documents',
                    'description': 'Search radiation treatment summaries for completion date',
                    'confidence': 0.85
                },
                {
                    'method': 'calculate_from_fractions_and_start',
                    'description': 'Calculate end date from start date + number of fractions',
                    'confidence': 0.7
                }
            ]
        elif gap_type == 'radiation_dose':
            investigation['explanation'] = (
                "Temporal matching found low-quality documents (progress notes). "
                "Try v_radiation_documents with extraction_priority for better quality."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'v_radiation_documents_priority',
                    'description': 'Use v_radiation_documents view with priority sorting (Treatment summaries first)',
                    'confidence': 0.9,
                    'query_template': 'v_radiation_documents WHERE extraction_priority = 1'
                },
                {
                    'method': 'expand_temporal_window',
                    'description': 'Expand temporal window from ±30 days to ±60 days',
                    'confidence': 0.6
                },
                {
                    'method': 'alternative_document_categories',
                    'description': 'Try consultation notes or outside records',
                    'confidence': 0.5
                }
            ]
        elif gap_type == 'surgery_eor':
            investigation['explanation'] = (
                "Operative notes may be missing or under wrong encounter. "
                "Try v_document_reference_enriched with encounter-based lookup."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'v_document_reference_enriched',
                    'description': 'Use encounter-based document discovery',
                    'confidence': 0.8
                },
                {
                    'method': 'expand_document_categories',
                    'description': 'Include surgical notes, anesthesia records, surgeon progress notes',
                    'confidence': 0.7
                }
            ]
        elif gap_type == 'imaging_conclusion':
            investigation['explanation'] = (
                "Imaging reports may not have Binary attachments. "
                "Try DiagnosticReport.conclusion field or result_information."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'structured_conclusion',
                    'description': 'Use DiagnosticReport.conclusion from v2_imaging instead of Binary extraction',
                    'confidence': 0.95
                },
                {
                    'method': 'result_information_field',
                    'description': 'Parse v2_imaging.result_information field',
                    'confidence': 0.85
                }
            ]
        elif gap_type == 'no_postop_imaging':
            # V4.7.3: Investigate Phase 3.5 query failures (empty imaging results)
            investigation['explanation'] = (
                "Phase 3.5 v_imaging query returned 0 results for post-operative imaging. "
                "This could be: (1) Query bug (wrong column, syntax error), "
                "(2) Legitimate absence (patient has no post-op imaging), "
                "(3) Data quality issue (imaging in different table/format), or "
                "(4) Schema evolution (column renamed, table restructured)."
            )
            investigation['suggested_alternatives'] = [
                {
                    'method': 'verify_query_schema',
                    'description': 'Validate all column names exist in v_imaging (check for renamed/missing columns like imaging_type → imaging_modality)',
                    'confidence': 0.95,
                    'criticality': 'HIGH - Query failures often due to schema mismatches'
                },
                {
                    'method': 'expand_imaging_window',
                    'description': 'Expand post-op window from 0-5 days to 0-14 days (imaging may be delayed)',
                    'confidence': 0.75
                },
                {
                    'method': 'query_v_imaging_results',
                    'description': 'Try alternative table v_imaging_results for additional imaging data',
                    'confidence': 0.70
                },
                {
                    'method': 'query_all_imaging_modalities',
                    'description': 'Remove MRI/CT filter - check if imaging exists with different modality codes',
                    'confidence': 0.60
                },
                {
                    'method': 'check_external_institution',
                    'description': 'Patient may have had post-op imaging at external institution (not in FHIR data)',
                    'confidence': 0.50
                }
            ]

        # V4.7.4: Clinical Protocol Validation
        # If patient_context provided, validate if missing event violates standard-of-care
        if patient_context is not None:
            clinical_validation = self.validate_clinical_protocol(
                gap_type=gap_type,
                patient_context=patient_context,
                event=event
            )
            investigation['clinical_validation'] = clinical_validation

            # Log clinical assessment if protocol violation detected
            if not clinical_validation['is_clinically_plausible']:
                logger.warning(
                    f"⚠️  CLINICAL PROTOCOL VIOLATION: {clinical_validation['standard_of_care_violation']}"
                )
                logger.info(f"Clinical Rationale: {clinical_validation['clinical_rationale']}")
                logger.info(f"Expected Protocol: {clinical_validation['expected_protocol']}")

        return investigation

    def _init_clinical_protocols(self):
        """
        V4.7.4: Initialize WHO 2021 CNS Clinical Protocol Knowledge Base.

        References:
        - WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md
        - Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf

        Standard-of-care protocols by tumor type for clinical validation.
        """
        self.clinical_protocols = {
            # High-Grade Gliomas (WHO Grade 3-4)
            'high_grade_glioma': {
                'tumor_types': ['glioblastoma', 'high-grade glioma', 'diffuse midline glioma', 'anaplastic astrocytoma'],
                'expected_events': [
                    {
                        'event_type': 'surgery',
                        'timing': 'diagnosis',
                        'required': True,
                        'description': 'Maximal safe resection'
                    },
                    {
                        'event_type': 'postop_imaging',
                        'timing': '24-72 hours post-surgery',
                        'required': True,
                        'description': 'Baseline post-operative MRI for extent of resection assessment',
                        'clinical_rationale': 'Standard-of-care for brain tumor surgery requires post-op imaging within 24-72h to assess extent of resection and surgical complications'
                    },
                    {
                        'event_type': 'radiation',
                        'timing': '28-35 days post-surgery',
                        'required': True,
                        'description': 'Radiation therapy 54-60 Gy in 1.8-2 Gy fractions',
                        'protocol_deviations': {
                            '<21 days': 'Early radiation (insufficient surgical healing)',
                            '>42 days': 'Delayed radiation (tumor regrowth risk)'
                        }
                    },
                    {
                        'event_type': 'chemotherapy',
                        'timing': 'concurrent with radiation',
                        'required': True,
                        'description': 'Temozolomide or clinical trial agent'
                    }
                ]
            },

            # Low-Grade Gliomas (WHO Grade 1-2)
            'low_grade_glioma': {
                'tumor_types': ['pilocytic astrocytoma', 'ganglioglioma', 'low-grade glioma', 'pleomorphic xanthoastrocytoma'],
                'expected_events': [
                    {
                        'event_type': 'surgery',
                        'timing': 'diagnosis',
                        'required': True,
                        'description': 'Gross total resection (GTR) if feasible'
                    },
                    {
                        'event_type': 'postop_imaging',
                        'timing': '24-72 hours post-surgery',
                        'required': True,
                        'description': 'Baseline post-operative MRI for extent of resection',
                        'clinical_rationale': 'GTR vs STR determines need for adjuvant therapy'
                    },
                    {
                        'event_type': 'surveillance_imaging',
                        'timing': '3-6 months intervals',
                        'required': True,
                        'description': 'Watch-and-wait with surveillance MRI if GTR achieved'
                    }
                ]
            },

            # Medulloblastoma
            'medulloblastoma': {
                'tumor_types': ['medulloblastoma', 'embryonal tumor'],
                'expected_events': [
                    {
                        'event_type': 'surgery',
                        'timing': 'diagnosis',
                        'required': True,
                        'description': 'Maximal safe resection'
                    },
                    {
                        'event_type': 'postop_imaging',
                        'timing': '24-48 hours post-surgery',
                        'required': True,
                        'description': 'Baseline MRI brain + spine for residual disease and metastases',
                        'clinical_rationale': 'Medulloblastoma requires spine imaging for CSF dissemination assessment'
                    },
                    {
                        'event_type': 'radiation',
                        'timing': '28-35 days post-surgery',
                        'required': True,
                        'description': 'Craniospinal irradiation (CSI) + posterior fossa boost'
                    },
                    {
                        'event_type': 'chemotherapy',
                        'timing': 'concurrent and adjuvant',
                        'required': True,
                        'description': 'Multi-agent chemotherapy (vincristine, cisplatin, cyclophosphamide)'
                    }
                ]
            },

            # Ependymoma
            'ependymoma': {
                'tumor_types': ['ependymoma'],
                'expected_events': [
                    {
                        'event_type': 'surgery',
                        'timing': 'diagnosis',
                        'required': True,
                        'description': 'Gross total resection critical for outcomes'
                    },
                    {
                        'event_type': 'postop_imaging',
                        'timing': '24-72 hours post-surgery',
                        'required': True,
                        'description': 'Baseline post-operative MRI to confirm GTR',
                        'clinical_rationale': 'GTR is most important prognostic factor for ependymoma'
                    },
                    {
                        'event_type': 'radiation',
                        'timing': '28-42 days post-surgery if residual disease',
                        'required': 'conditional',
                        'description': 'Focal radiation 54-59.4 Gy'
                    }
                ]
            },

            # ATRT (Atypical Teratoid/Rhabdoid Tumor)
            'atrt': {
                'tumor_types': ['atypical teratoid', 'rhabdoid tumor', 'ATRT'],
                'expected_events': [
                    {
                        'event_type': 'surgery',
                        'timing': 'diagnosis',
                        'required': True,
                        'description': 'Maximal safe resection'
                    },
                    {
                        'event_type': 'postop_imaging',
                        'timing': '24-48 hours post-surgery',
                        'required': True,
                        'description': 'Baseline MRI brain + spine',
                        'clinical_rationale': 'ATRT has high metastatic potential requiring spine imaging'
                    },
                    {
                        'event_type': 'intensive_chemotherapy',
                        'timing': 'immediate post-surgery',
                        'required': True,
                        'description': 'Intensive multi-agent chemotherapy'
                    }
                ]
            }
        }

    def validate_clinical_protocol(
        self,
        gap_type: str,
        patient_context: Dict,
        event: Dict
    ) -> Dict:
        """
        V4.7.4: Validate if missing event violates standard clinical practice.

        Args:
            gap_type: Type of missing data (e.g., 'no_postop_imaging')
            patient_context: Patient diagnosis and treatment context
                {
                    'who_diagnosis': str,
                    'tumor_type': str,
                    'molecular_markers': Dict,
                    'surgeries': List[Dict],
                    'timeline_events': List[Dict]
                }
            event: The specific event context (e.g., surgery date)

        Returns:
            Dict with clinical validation assessment
        """
        validation = {
            'is_clinically_plausible': True,
            'standard_of_care_violation': None,
            'clinical_rationale': None,
            'expected_protocol': None,
            'confidence': 0.0
        }

        # Extract tumor type from WHO diagnosis
        tumor_type_match = None
        who_diagnosis = patient_context.get('who_diagnosis', '').lower()

        for protocol_key, protocol in self.clinical_protocols.items():
            for tumor_keyword in protocol['tumor_types']:
                if tumor_keyword.lower() in who_diagnosis:
                    tumor_type_match = protocol_key
                    break
            if tumor_type_match:
                break

        # If no matching protocol, return uncertain
        if not tumor_type_match:
            validation['clinical_rationale'] = f"No standard protocol found for diagnosis: {who_diagnosis}"
            validation['confidence'] = 0.3
            return validation

        protocol = self.clinical_protocols[tumor_type_match]

        # Validate specific gap types
        if gap_type == 'no_postop_imaging':
            # Find post-op imaging requirement in protocol
            postop_imaging_req = None
            for expected_event in protocol['expected_events']:
                if expected_event['event_type'] == 'postop_imaging':
                    postop_imaging_req = expected_event
                    break

            if postop_imaging_req and postop_imaging_req['required']:
                validation['is_clinically_plausible'] = False
                validation['standard_of_care_violation'] = (
                    f"Post-operative imaging is REQUIRED within {postop_imaging_req['timing']} "
                    f"for {tumor_type_match.replace('_', ' ').title()}"
                )
                validation['clinical_rationale'] = postop_imaging_req.get(
                    'clinical_rationale',
                    postop_imaging_req['description']
                )
                validation['expected_protocol'] = f"Surgery → Post-op MRI ({postop_imaging_req['timing']}) → EOR assessment"
                validation['confidence'] = 0.95
            else:
                validation['is_clinically_plausible'] = True
                validation['clinical_rationale'] = "Post-op imaging not strictly required for this tumor type"
                validation['confidence'] = 0.7

        return validation

    def investigate_phase1_data_loading(self, loaded_data: Dict) -> Dict:
        """
        V4.7: Investigate Phase 1 data loading for completeness issues.

        Checks:
        - Empty result sets (0 records loaded)
        - Unexpectedly small result sets
        - NULL/missing critical fields
        - Missing encounters that should exist

        Args:
            loaded_data: Dictionary with counts from each data source
                {
                    'demographics': {...},
                    'pathology_count': int,
                    'procedures_count': int,
                    'chemotherapy_count': int,
                    'radiation_count': int,
                    'imaging_count': int,
                    ...
                }

        Returns:
            Investigation result with issues_found and suggestions
        """
        investigation = {
            'phase': 'Phase 1',
            'issues_found': [],
            'suggestions': [],
            'statistics': {
                'data_sources_loaded': 0,
                'empty_sources': 0,
                'low_count_sources': 0
            }
        }

        # Count total data sources
        count_fields = [k for k in loaded_data.keys() if k.endswith('_count')]
        investigation['statistics']['data_sources_loaded'] = len(count_fields)

        # Check demographics
        if not loaded_data.get('demographics'):
            investigation['issues_found'].append('No demographics loaded')
            investigation['statistics']['empty_sources'] += 1
            investigation['suggestions'].append({
                'method': 'retry_demographics_query',
                'description': 'Retry patient demographics query with expanded search',
                'confidence': 0.9
            })

        # Check pathology
        pathology_count = loaded_data.get('pathology_count', 0)
        if pathology_count == 0:
            investigation['issues_found'].append('No pathology records found')
            investigation['statistics']['empty_sources'] += 1
            investigation['suggestions'].append({
                'method': 'query_alternative_pathology_sources',
                'description': 'Search v_observations_lab for tumor markers or alternative pathology tables',
                'confidence': 0.7
            })

        # Check procedures
        procedures_count = loaded_data.get('procedures_count', 0)
        if procedures_count == 0:
            investigation['issues_found'].append('No procedures found')
            investigation['statistics']['empty_sources'] += 1
            investigation['suggestions'].append({
                'method': 'query_encounters_for_surgical_context',
                'description': 'Look for surgical encounters without Procedure resources',
                'confidence': 0.8
            })

        # Check chemotherapy
        chemotherapy_count = loaded_data.get('chemotherapy_count', 0)
        if chemotherapy_count == 0:
            investigation['issues_found'].append('No chemotherapy episodes found - may not have received chemotherapy')
            investigation['statistics']['empty_sources'] += 1
            # Don't suggest remediation - absence may be clinically accurate
        elif chemotherapy_count > 0:
            # V4.8.2: Use reasoning-based validation for chemotherapy data quality
            logger.info(f"🔍 V4.8.2: Running reasoning-based chemotherapy validation on {chemotherapy_count} episodes...")

            try:
                validator = get_chemotherapy_validator()
                chemotherapy_records = loaded_data.get('chemotherapy_records', [])

                if chemotherapy_records:
                    # Get patient context if available
                    patient_context = loaded_data.get('demographics', {})

                    validation_result = validator.validate_chemotherapy_episodes(
                        episodes=chemotherapy_records,
                        patient_context=patient_context
                    )

                    # Add validation issues to investigation
                    if not validation_result.get('validation_passed'):
                        llm_issues = validation_result.get('issues_found', [])
                        for issue in llm_issues:
                            investigation['issues_found'].append(
                                f"Chemotherapy data quality: {issue.get('description', 'Unknown issue')}"
                            )

                        # Add LLM recommendations as suggestions
                        llm_recommendations = validation_result.get('recommendations', [])
                        for rec in llm_recommendations:
                            investigation['suggestions'].append({
                                'method': rec.get('action', 'unknown'),
                                'description': rec.get('description', ''),
                                'confidence': rec.get('confidence', 0.7),
                                'applies_to_episodes': rec.get('applies_to_episodes', [])
                            })

                        # Store full LLM reasoning for debugging
                        investigation['chemotherapy_validation'] = {
                            'llm_reasoning': validation_result.get('reasoning', ''),
                            'issues': llm_issues,
                            'recommendations': llm_recommendations
                        }

                        logger.info(f"✅ V4.8.2: LLM found {len(llm_issues)} data quality issues in chemotherapy episodes")
                    else:
                        logger.info(f"✅ V4.8.2: LLM validation passed - no data quality issues found")

            except Exception as e:
                logger.warning(f"⚠️  V4.8.2: Chemotherapy validation failed: {e}")
                # Don't fail the entire investigation if validation has issues
                investigation['issues_found'].append(f'Chemotherapy validation error: {str(e)}')

        # Check radiation
        radiation_count = loaded_data.get('radiation_count', 0)
        if radiation_count == 0:
            investigation['issues_found'].append('No radiation episodes found - may not have received radiation')
            investigation['statistics']['empty_sources'] += 1
            # Don't suggest remediation - absence may be clinically accurate

        # Check imaging
        imaging_count = loaded_data.get('imaging_count', 0)
        if imaging_count == 0:
            investigation['issues_found'].append('No imaging studies found')
            investigation['statistics']['empty_sources'] += 1
            investigation['suggestions'].append({
                'method': 'query_diagnostic_report_by_category',
                'description': 'Search DiagnosticReport by category (RAD, CT, MRI, imaging)',
                'confidence': 0.9
            })
        elif imaging_count < 3:
            # Low count - may want to expand search
            investigation['issues_found'].append(f'Only {imaging_count} imaging studies found - consider expanding search')
            investigation['statistics']['low_count_sources'] += 1
            investigation['suggestions'].append({
                'method': 'expand_imaging_date_range',
                'description': 'Expand imaging search date range beyond standard window',
                'confidence': 0.6
            })

        return investigation

    def investigate_phase4_medgemma_extraction(self, extractions: List[Dict]) -> Dict:
        """
        V4.7: Investigate Phase 4 MedGemma extractions for quality issues.

        Checks:
        - Low confidence scores (< 0.5)
        - Validation failures
        - Empty/NULL extracted values
        - Extraction timeout/errors

        Args:
            extractions: List of extraction results
                [
                    {
                        'field_name': str,
                        'confidence_score': float,
                        'validation_passed': bool,
                        'extracted_value': Any,
                        'extraction_time_seconds': float,
                        ...
                    },
                    ...
                ]

        Returns:
            Investigation result with quality metrics and suggestions
        """
        investigation = {
            'phase': 'Phase 4',
            'issues_found': [],
            'suggestions': [],
            'statistics': {
                'total_extractions': len(extractions),
                'validation_failures': 0,
                'low_confidence': 0,
                'average_confidence': 0.0,
                'null_extractions': 0,
                'timeouts': 0
            }
        }

        if not extractions:
            investigation['issues_found'].append('No MedGemma extractions performed')
            return investigation

        confidences = []
        low_confidence_fields = []
        validation_failed_fields = []
        null_fields = []

        for extraction in extractions:
            field_name = extraction.get('field_name', 'unknown')
            confidence = extraction.get('confidence_score', 0)
            confidences.append(confidence)

            # Check for low confidence
            if confidence < 0.5:
                investigation['statistics']['low_confidence'] += 1
                low_confidence_fields.append(f"{field_name} ({confidence:.2f})")

            # Check for validation failures
            if not extraction.get('validation_passed', True):
                investigation['statistics']['validation_failures'] += 1
                validation_failed_fields.append(field_name)

            # Check for null/empty extractions
            extracted_value = extraction.get('extracted_value')
            if extracted_value is None or extracted_value == '':
                investigation['statistics']['null_extractions'] += 1
                null_fields.append(field_name)

            # Check for timeouts
            if extraction.get('timeout', False) or extraction.get('error') == 'timeout':
                investigation['statistics']['timeouts'] += 1

        # Calculate average confidence
        if confidences:
            investigation['statistics']['average_confidence'] = sum(confidences) / len(confidences)

        # Generate issue reports
        if low_confidence_fields:
            investigation['issues_found'].append(
                f"{len(low_confidence_fields)} low confidence extractions: {', '.join(low_confidence_fields[:3])}"
                + (f" and {len(low_confidence_fields) - 3} more" if len(low_confidence_fields) > 3 else "")
            )
            investigation['suggestions'].append({
                'method': 'retry_with_refined_prompt',
                'description': f'Retry extractions for {len(low_confidence_fields)} low-confidence fields with more specific prompts',
                'confidence': 0.7
            })

        if validation_failed_fields:
            investigation['issues_found'].append(
                f"{len(validation_failed_fields)} validation failures: {', '.join(validation_failed_fields[:3])}"
                + (f" and {len(validation_failed_fields) - 3} more" if len(validation_failed_fields) > 3 else "")
            )
            investigation['suggestions'].append({
                'method': 'use_alternative_documents',
                'description': 'Retry with higher quality documents (treatment summaries vs progress notes)',
                'confidence': 0.8
            })

        if null_fields:
            investigation['issues_found'].append(
                f"{len(null_fields)} null/empty extractions: {', '.join(null_fields[:3])}"
                + (f" and {len(null_fields) - 3} more" if len(null_fields) > 3 else "")
            )

        if investigation['statistics']['timeouts'] > 0:
            investigation['issues_found'].append(f"{investigation['statistics']['timeouts']} extraction timeouts")
            investigation['suggestions'].append({
                'method': 'increase_timeout_or_simplify_prompt',
                'description': 'Increase MedGemma timeout or simplify extraction prompt',
                'confidence': 0.9
            })

        # Overall quality assessment
        avg_confidence = investigation['statistics']['average_confidence']
        if avg_confidence < 0.6:
            investigation['issues_found'].append(f'Low average confidence: {avg_confidence:.2f}')
            investigation['suggestions'].append({
                'method': 'review_document_quality',
                'description': 'Review quality of source documents - may be scanned images or incomplete notes',
                'confidence': 0.7
            })

        return investigation


if __name__ == '__main__':
    # Test the investigation engine
    from schema_loader import AthenaSchemaLoader
    import boto3

    # Initialize
    schema_path = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv'
    schema_loader = AthenaSchemaLoader(schema_path)
    athena_client = boto3.client('athena', region_name='us-east-1')

    engine = InvestigationEngine(athena_client, schema_loader)

    # Simulate the date parsing error
    test_query = """
    SELECT date_parse(e.period_start, '%Y-%m-%dT%H:%i:%sZ')
    FROM fhir_prd_db.encounter e
    """

    test_error = 'INVALID_FUNCTION_ARGUMENT: Invalid format: "2018-08-07" is too short'

    print("Testing investigation engine with date parsing error...")
    investigation = engine.investigate_query_failure(
        'test-query-id',
        test_query,
        test_error
    )

    print(f"\nRoot Cause: {investigation['root_cause']}")
    print(f"Confidence: {investigation['confidence']}")
    print(f"Auto-fixable: {investigation['auto_fixable']}")
    print(f"\nProposed Fix:\n{investigation['proposed_fix']}")
