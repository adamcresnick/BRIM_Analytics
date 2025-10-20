#!/usr/bin/env python3
"""
Athena Schema Registry - Column Name Validation System

This module provides runtime column validation to prevent query errors
from incorrect column names. It caches actual Athena view schemas and
validates queries before execution.

Usage:
    from utils.athena_schema_registry import AthenaSchemaRegistry

    registry = AthenaSchemaRegistry()

    # Validate column names before querying
    if registry.validate_columns('v_procedures_tumor', ['proc_code_text', 'proc_outcome_text']):
        # Safe to query
        pass

    # Get correct column name suggestions
    correct_name = registry.suggest_column('v_procedures_tumor', 'procedure_code_text')
    # Returns: 'proc_code_text'
"""

import boto3
import time
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
import json
from datetime import datetime, timedelta
from difflib import get_close_matches


class AthenaSchemaRegistry:
    """
    Centralized schema registry for all Athena views.
    Caches column names and provides validation/suggestion capabilities.
    """

    def __init__(
        self,
        aws_profile: str = 'radiant-prod',
        database: str = 'fhir_prd_db',
        cache_dir: Path = None,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize schema registry

        Args:
            aws_profile: AWS profile to use
            database: Athena database name
            cache_dir: Directory to cache schema (default: data/schema_cache)
            cache_ttl_hours: Hours before cache expires (default: 24)
        """
        self.aws_profile = aws_profile
        self.database = database
        self.cache_ttl_hours = cache_ttl_hours

        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / 'data' / 'schema_cache'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Athena client
        session = boto3.Session(profile_name=aws_profile)
        self.athena_client = session.client('athena', region_name='us-east-1')

        # Schema cache: {view_name: {column_name: data_type}}
        self.schemas: Dict[str, Dict[str, str]] = {}

    def get_schema(self, view_name: str, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get schema for a view (from cache or Athena)

        Args:
            view_name: Name of the view (e.g., 'v_procedures_tumor')
            force_refresh: Force refresh from Athena even if cached

        Returns:
            Dictionary mapping column names to data types
        """
        # Check in-memory cache
        if view_name in self.schemas and not force_refresh:
            return self.schemas[view_name]

        # Check file cache
        cache_file = self.cache_dir / f"{view_name}_schema.json"
        if cache_file.exists() and not force_refresh:
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age < timedelta(hours=self.cache_ttl_hours):
                with open(cache_file, 'r') as f:
                    cached_schema = json.load(f)
                    self.schemas[view_name] = cached_schema['columns']
                    return self.schemas[view_name]

        # Fetch from Athena
        print(f"Fetching schema for {view_name} from Athena...")
        schema = self._fetch_schema_from_athena(view_name)

        # Cache to memory and file
        self.schemas[view_name] = schema
        with open(cache_file, 'w') as f:
            json.dump({
                'view_name': view_name,
                'database': self.database,
                'fetched_at': datetime.now().isoformat(),
                'columns': schema
            }, f, indent=2)

        return schema

    def _fetch_schema_from_athena(self, view_name: str) -> Dict[str, str]:
        """Fetch schema from Athena using SHOW COLUMNS"""
        query = f"SHOW COLUMNS FROM {self.database}.{view_name}"

        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={
                'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
            }
        )

        query_id = response['QueryExecutionId']

        # Wait for completion
        while True:
            status_response = self.athena_client.get_query_execution(QueryExecutionId=query_id)
            status = status_response['QueryExecution']['Status']['State']

            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Schema query {status} for {view_name}: {reason}")

            time.sleep(1)

        # Get results
        results = self.athena_client.get_query_results(QueryExecutionId=query_id)

        # Parse columns (format: col_name\tdata_type)
        schema = {}
        for row in results['ResultSet']['Rows'][1:]:  # Skip header
            values = [col.get('VarCharValue', '') for col in row['Data']]
            if len(values) >= 2:
                col_name = values[0]
                data_type = values[1]
                schema[col_name] = data_type

        return schema

    def validate_columns(
        self,
        view_name: str,
        column_names: List[str],
        raise_on_error: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate that column names exist in view

        Args:
            view_name: Name of the view
            column_names: List of column names to validate
            raise_on_error: Raise exception if validation fails

        Returns:
            (is_valid, invalid_columns)
        """
        schema = self.get_schema(view_name)
        valid_columns = set(schema.keys())

        invalid = [col for col in column_names if col not in valid_columns]

        if invalid and raise_on_error:
            suggestions = [self.suggest_column(view_name, col) for col in invalid]
            error_msg = f"Invalid columns for {view_name}:\n"
            for inv, sugg in zip(invalid, suggestions):
                error_msg += f"  ❌ '{inv}' not found"
                if sugg:
                    error_msg += f" (did you mean '{sugg}'?)"
                error_msg += "\n"
            raise ValueError(error_msg)

        return len(invalid) == 0, invalid

    def suggest_column(
        self,
        view_name: str,
        incorrect_column: str,
        max_suggestions: int = 3
    ) -> Optional[str]:
        """
        Suggest correct column name based on fuzzy matching

        Args:
            view_name: Name of the view
            incorrect_column: Incorrect column name
            max_suggestions: Maximum number of suggestions

        Returns:
            Best matching column name or None
        """
        schema = self.get_schema(view_name)
        valid_columns = list(schema.keys())

        matches = get_close_matches(
            incorrect_column,
            valid_columns,
            n=max_suggestions,
            cutoff=0.6
        )

        return matches[0] if matches else None

    def get_columns_by_pattern(
        self,
        view_name: str,
        pattern: str,
        case_sensitive: bool = False
    ) -> List[str]:
        """
        Get columns matching a pattern

        Args:
            view_name: Name of the view
            pattern: Pattern to match (substring)
            case_sensitive: Whether to match case-sensitively

        Returns:
            List of matching column names
        """
        schema = self.get_schema(view_name)

        if case_sensitive:
            return [col for col in schema.keys() if pattern in col]
        else:
            pattern_lower = pattern.lower()
            return [col for col in schema.keys() if pattern_lower in col.lower()]

    def get_columns_by_prefix(self, view_name: str, prefix: str) -> List[str]:
        """Get all columns starting with a prefix"""
        schema = self.get_schema(view_name)
        return [col for col in schema.keys() if col.startswith(prefix)]

    def print_schema(self, view_name: str, prefix_filter: Optional[str] = None):
        """Pretty-print schema for a view"""
        schema = self.get_schema(view_name)

        print(f"\n{'='*80}")
        print(f"Schema for {self.database}.{view_name}")
        print(f"{'='*80}\n")

        if prefix_filter:
            filtered = {k: v for k, v in schema.items() if k.startswith(prefix_filter)}
            print(f"Filtered by prefix '{prefix_filter}': {len(filtered)} columns\n")
        else:
            filtered = schema
            print(f"Total columns: {len(filtered)}\n")

        # Group by prefix
        prefixes = {}
        for col, dtype in filtered.items():
            prefix = col.split('_')[0] if '_' in col else 'other'
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append((col, dtype))

        for prefix in sorted(prefixes.keys()):
            print(f"{prefix.upper()} PREFIX:")
            for col, dtype in sorted(prefixes[prefix]):
                print(f"  {col:<40} {dtype}")
            print()

    def validate_query_columns(
        self,
        query: str,
        raise_on_error: bool = False
    ) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Parse and validate all column references in a query

        Args:
            query: SQL query string
            raise_on_error: Raise exception if validation fails

        Returns:
            (is_valid, {view_name: [invalid_columns]})
        """
        # Simple regex-based extraction (can be improved with SQL parser)
        import re

        # Extract view names from FROM clauses
        from_pattern = r'FROM\s+(?:fhir_prd_db\.)?(\w+)'
        views = re.findall(from_pattern, query, re.IGNORECASE)

        # Extract column references (table_alias.column or just column)
        col_pattern = r'\b(\w+)\.(\w+)\b'
        column_refs = re.findall(col_pattern, query)

        invalid_by_view = {}

        for view in set(views):
            # Get all column references for this view
            view_cols = [col for alias, col in column_refs if alias in ['p', 'dr', 'e', 'mr']]  # Common aliases

            if view_cols:
                is_valid, invalid = self.validate_columns(view, view_cols, raise_on_error=False)
                if invalid:
                    invalid_by_view[view] = invalid

        all_valid = len(invalid_by_view) == 0

        if not all_valid and raise_on_error:
            error_msg = "Query contains invalid column references:\n"
            for view, invalid_cols in invalid_by_view.items():
                error_msg += f"\n{view}:\n"
                for col in invalid_cols:
                    suggestion = self.suggest_column(view, col)
                    error_msg += f"  ❌ '{col}'"
                    if suggestion:
                        error_msg += f" → did you mean '{suggestion}'?"
                    error_msg += "\n"
            raise ValueError(error_msg)

        return all_valid, invalid_by_view

    def refresh_all_schemas(self, view_names: List[str] = None):
        """Refresh schemas for all views or specified list"""
        if view_names is None:
            # Default to common views
            view_names = [
                'v_imaging',
                'v_binary_files',
                'v_procedures_tumor',
                'v_diagnoses',
                'v_medications',
                'v_patient_demographics',
                'v_encounters',
                'v_radiation',
                'v_measurements'
            ]

        print(f"Refreshing schemas for {len(view_names)} views...")
        for view_name in view_names:
            try:
                self.get_schema(view_name, force_refresh=True)
                print(f"  ✅ {view_name}")
            except Exception as e:
                print(f"  ❌ {view_name}: {str(e)}")


# Convenience functions
def validate_columns(view_name: str, columns: List[str]) -> Tuple[bool, List[str]]:
    """Quick validation without creating registry instance"""
    registry = AthenaSchemaRegistry()
    return registry.validate_columns(view_name, columns)


def suggest_column(view_name: str, incorrect_column: str) -> Optional[str]:
    """Quick suggestion without creating registry instance"""
    registry = AthenaSchemaRegistry()
    return registry.suggest_column(view_name, incorrect_column)


def print_schema(view_name: str, prefix_filter: Optional[str] = None):
    """Quick schema print without creating registry instance"""
    registry = AthenaSchemaRegistry()
    registry.print_schema(view_name, prefix_filter)


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python athena_schema_registry.py <view_name>                 # Print full schema")
        print("  python athena_schema_registry.py <view_name> <prefix>        # Filter by prefix")
        print("  python athena_schema_registry.py validate <view> <col1> ...  # Validate columns")
        print("  python athena_schema_registry.py suggest <view> <bad_col>    # Suggest correction")
        print("  python athena_schema_registry.py refresh                     # Refresh all schemas")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'refresh':
        registry = AthenaSchemaRegistry()
        registry.refresh_all_schemas()

    elif command == 'validate':
        view_name = sys.argv[2]
        columns = sys.argv[3:]
        is_valid, invalid = validate_columns(view_name, columns)

        if is_valid:
            print(f"✅ All {len(columns)} columns are valid for {view_name}")
        else:
            print(f"❌ Invalid columns for {view_name}:")
            registry = AthenaSchemaRegistry()
            for col in invalid:
                suggestion = registry.suggest_column(view_name, col)
                if suggestion:
                    print(f"  '{col}' → did you mean '{suggestion}'?")
                else:
                    print(f"  '{col}' → no suggestion found")
            sys.exit(1)

    elif command == 'suggest':
        view_name = sys.argv[2]
        bad_column = sys.argv[3]
        suggestion = suggest_column(view_name, bad_column)

        if suggestion:
            print(f"'{bad_column}' → '{suggestion}'")
        else:
            print(f"No suggestion found for '{bad_column}'")
            print("\nSearching for similar patterns...")
            registry = AthenaSchemaRegistry()
            # Extract key parts and search
            parts = bad_column.split('_')
            for part in parts:
                if len(part) > 3:
                    matches = registry.get_columns_by_pattern(view_name, part, case_sensitive=False)
                    if matches:
                        print(f"\nColumns containing '{part}':")
                        for match in matches[:5]:
                            print(f"  - {match}")

    else:
        # Print schema
        view_name = sys.argv[1]
        prefix_filter = sys.argv[2] if len(sys.argv) > 2 else None
        print_schema(view_name, prefix_filter)
