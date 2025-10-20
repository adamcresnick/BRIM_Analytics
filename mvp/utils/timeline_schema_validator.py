"""
Timeline Database Schema Validator

Validates that the timeline database has the correct schema required by
MasterAgent and TimelineQueryInterface.

This prevents schema-related errors at runtime by checking the database
structure before agents attempt to use it.
"""

import duckdb
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


# Required schema definition
REQUIRED_SCHEMA = {
    'patients': {
        'columns': [
            ('patient_id', 'VARCHAR'),
            ('patient_fhir_id', 'VARCHAR'),
            ('mrn', 'VARCHAR'),
            ('birth_date', 'DATE'),
            ('created_at', 'TIMESTAMP')
        ],
        'primary_key': 'patient_id'
    },
    'events': {
        'columns': [
            ('event_id', 'VARCHAR'),
            ('patient_id', 'VARCHAR'),
            ('event_type', 'VARCHAR'),
            ('event_category', 'VARCHAR'),
            ('event_date', 'TIMESTAMP'),
            ('description', 'VARCHAR'),
            ('source_system', 'VARCHAR'),
            ('source_id', 'VARCHAR'),
            ('created_at', 'TIMESTAMP')
        ],
        'primary_key': 'event_id'
    },
    'source_documents': {
        'columns': [
            ('document_id', 'VARCHAR'),
            ('source_event_id', 'VARCHAR'),
            ('document_type', 'VARCHAR'),
            ('document_text', 'VARCHAR'),
            ('document_date', 'TIMESTAMP'),
            ('document_metadata', 'VARCHAR'),
            ('created_at', 'TIMESTAMP')
        ],
        'primary_key': 'document_id'
    },
    'extracted_variables': {
        'columns': [
            ('extraction_id', 'VARCHAR'),
            ('event_id', 'VARCHAR'),
            ('patient_id', 'VARCHAR'),
            ('variable_name', 'VARCHAR'),
            ('variable_value', 'VARCHAR'),
            ('confidence', 'DOUBLE'),
            ('extraction_method', 'VARCHAR'),
            ('extracted_at', 'TIMESTAMP'),
            ('provenance', 'VARCHAR')
        ],
        'primary_key': 'extraction_id'
    }
}


class TimelineSchemaValidator:
    """Validates timeline database schema"""

    def __init__(self, db_path: str):
        """
        Initialize validator.

        Args:
            db_path: Path to timeline DuckDB database
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(f"Timeline database not found: {db_path}")

        self.conn = duckdb.connect(str(self.db_path), read_only=True)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate database schema.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check all required tables exist
        existing_tables = self._get_existing_tables()

        for table_name in REQUIRED_SCHEMA.keys():
            if table_name not in existing_tables:
                errors.append(f"Missing required table: {table_name}")
                continue

            # Check table columns
            table_errors = self._validate_table_columns(table_name)
            errors.extend(table_errors)

        return (len(errors) == 0, errors)

    def validate_and_fix(self) -> Dict[str, any]:
        """
        Validate and attempt to fix schema issues.

        Returns:
            Summary of validation and fixes applied
        """
        # Re-open in write mode
        self.conn.close()
        self.conn = duckdb.connect(str(self.db_path), read_only=False)

        summary = {
            'initial_validation': {},
            'fixes_applied': [],
            'final_validation': {}
        }

        # Initial validation
        is_valid, errors = self.validate()
        summary['initial_validation'] = {
            'valid': is_valid,
            'errors': errors
        }

        if is_valid:
            logger.info("Schema is valid - no fixes needed")
            return summary

        # Attempt fixes
        logger.info(f"Schema validation failed with {len(errors)} errors - attempting fixes")

        for error in errors:
            if error.startswith("Missing required table:"):
                table_name = error.split(": ")[1]
                fix_result = self._create_missing_table(table_name)
                summary['fixes_applied'].append(fix_result)

            elif error.startswith("Missing column"):
                # Parse error to get table and column
                parts = error.split("'")
                if len(parts) >= 4:
                    column_name = parts[1]
                    table_name = parts[3]
                    fix_result = self._add_missing_column(table_name, column_name)
                    summary['fixes_applied'].append(fix_result)

        # Re-validate
        is_valid, errors = self.validate()
        summary['final_validation'] = {
            'valid': is_valid,
            'errors': errors
        }

        return summary

    def _get_existing_tables(self) -> List[str]:
        """Get list of existing tables"""
        result = self.conn.execute("SHOW TABLES").fetchall()
        return [row[0] for row in result]

    def _validate_table_columns(self, table_name: str) -> List[str]:
        """Validate columns for a specific table"""
        errors = []

        # Get actual columns
        actual_columns = self.conn.execute(
            f"DESCRIBE {table_name}"
        ).fetchall()

        actual_col_dict = {row[0]: row[1] for row in actual_columns}

        # Check required columns
        required_columns = REQUIRED_SCHEMA[table_name]['columns']

        for col_name, col_type in required_columns:
            if col_name not in actual_col_dict:
                errors.append(f"Missing column '{col_name}' in table '{table_name}'")
            # Note: DuckDB type checking can be complex, skipping for now

        return errors

    def _create_missing_table(self, table_name: str) -> Dict[str, any]:
        """Create a missing table"""
        try:
            schema_def = REQUIRED_SCHEMA[table_name]
            columns = schema_def['columns']
            primary_key = schema_def.get('primary_key')

            # Build CREATE TABLE statement
            col_defs = []
            for col_name, col_type in columns:
                col_def = f"{col_name} {col_type}"
                if col_name == primary_key:
                    col_def += " PRIMARY KEY"
                elif col_name == 'created_at':
                    col_def += " DEFAULT CURRENT_TIMESTAMP"
                col_defs.append(col_def)

            create_sql = f"CREATE TABLE {table_name} ({', '.join(col_defs)})"

            self.conn.execute(create_sql)
            logger.info(f"Created missing table: {table_name}")

            return {
                'table': table_name,
                'action': 'created',
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            return {
                'table': table_name,
                'action': 'create_failed',
                'success': False,
                'error': str(e)
            }

    def _add_missing_column(self, table_name: str, column_name: str) -> Dict[str, any]:
        """Add a missing column to a table"""
        try:
            # Find column definition
            schema_def = REQUIRED_SCHEMA[table_name]
            col_def = None

            for col_name, col_type in schema_def['columns']:
                if col_name == column_name:
                    col_def = f"{col_name} {col_type}"
                    if col_name == 'created_at':
                        col_def += " DEFAULT CURRENT_TIMESTAMP"
                    break

            if not col_def:
                raise ValueError(f"Column {column_name} not in schema definition")

            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_def}"
            self.conn.execute(alter_sql)
            logger.info(f"Added missing column: {table_name}.{column_name}")

            return {
                'table': table_name,
                'column': column_name,
                'action': 'added',
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to add column {table_name}.{column_name}: {e}")
            return {
                'table': table_name,
                'column': column_name,
                'action': 'add_failed',
                'success': False,
                'error': str(e)
            }

    def close(self):
        """Close database connection"""
        self.conn.close()


# CLI for validation
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Validate timeline database schema')
    parser.add_argument(
        'db_path',
        type=str,
        help='Path to timeline DuckDB database'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Attempt to fix schema issues'
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    try:
        validator = TimelineSchemaValidator(args.db_path)

        if args.fix:
            print("Validating and fixing schema...")
            summary = validator.validate_and_fix()

            print("\nInitial Validation:")
            print(f"  Valid: {summary['initial_validation']['valid']}")
            if summary['initial_validation']['errors']:
                print(f"  Errors: {len(summary['initial_validation']['errors'])}")
                for error in summary['initial_validation']['errors']:
                    print(f"    - {error}")

            if summary['fixes_applied']:
                print("\nFixes Applied:")
                for fix in summary['fixes_applied']:
                    if fix['success']:
                        print(f"  ✅ {fix['action']}: {fix.get('table', '')}.{fix.get('column', '')}")
                    else:
                        print(f"  ❌ {fix['action']}: {fix.get('table', '')} - {fix.get('error', '')}")

            print("\nFinal Validation:")
            print(f"  Valid: {summary['final_validation']['valid']}")
            if summary['final_validation']['errors']:
                print(f"  Remaining Errors: {len(summary['final_validation']['errors'])}")
                for error in summary['final_validation']['errors']:
                    print(f"    - {error}")
            else:
                print("  ✅ Schema is valid!")

        else:
            print("Validating schema...")
            is_valid, errors = validator.validate()

            if is_valid:
                print("✅ Schema is valid!")
            else:
                print(f"❌ Schema validation failed with {len(errors)} errors:")
                for error in errors:
                    print(f"  - {error}")

                print("\nRun with --fix to attempt automatic fixes")

        validator.close()
        sys.exit(0 if is_valid else 1)

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)
