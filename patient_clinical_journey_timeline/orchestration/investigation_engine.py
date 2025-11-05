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
