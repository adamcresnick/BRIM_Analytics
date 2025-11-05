"""
Athena Schema Loader and Query Generator

Loads the complete Athena FHIR schema from CSV to enable the orchestrator
to understand ALL available data resources and generate dynamic queries for
completeness validation and failure investigation.
"""

import pandas as pd
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AthenaSchemaLoader:
    """
    Loads and provides query access to the complete Athena FHIR schema.

    Enables the orchestrator to:
    - Understand all available tables and columns
    - Generate dynamic queries for resource counting
    - Investigate data quality issues
    - Sample field values for format analysis
    """

    def __init__(self, schema_csv_path: str):
        """
        Load the Athena schema from CSV file.

        Args:
            schema_csv_path: Path to Athena_Schema_1103b2025.csv
        """
        self.schema_path = Path(schema_csv_path)
        self.schema = self._load_schema()
        logger.info(f"Loaded schema with {len(self.schema)} tables")

    def _load_schema(self) -> Dict:
        """
        Load CSV schema into hierarchical structure.

        Returns:
            Dict mapping table_name -> {columns: [...], metadata: {...}}
        """
        try:
            df = pd.read_csv(self.schema_path)

            schema_dict = {}
            for _, row in df.iterrows():
                table = row['table_name']

                if table not in schema_dict:
                    schema_dict[table] = {
                        'columns': [],
                        'metadata': {}
                    }

                schema_dict[table]['columns'].append({
                    'name': row['column_name'],
                    'position': int(row['ordinal_position']),
                    'type': row['data_type'],
                    'nullable': row['is_nullable'] == 'YES'
                })

            # Sort columns by position
            for table in schema_dict:
                schema_dict[table]['columns'].sort(key=lambda x: x['position'])

            return schema_dict

        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            raise

    def get_table_schema(self, table_name: str) -> Optional[Dict]:
        """
        Get schema for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Dict with columns and metadata, or None if not found
        """
        return self.schema.get(table_name)

    def list_tables(self) -> List[str]:
        """Get list of all table names"""
        return list(self.schema.keys())

    def find_tables_with_column(self, column_pattern: str) -> List[str]:
        """
        Find all tables containing a column matching pattern.

        Args:
            column_pattern: Column name or pattern (case-insensitive)

        Returns:
            List of table names
        """
        matching_tables = []
        pattern_lower = column_pattern.lower()

        for table, metadata in self.schema.items():
            for col in metadata['columns']:
                if pattern_lower in col['name'].lower():
                    matching_tables.append(table)
                    break

        return matching_tables

    def find_patient_reference_tables(self) -> List[str]:
        """
        Find all tables that have patient reference columns.

        Returns:
            List of table names with patient references
        """
        patient_tables = []

        for table, metadata in self.schema.items():
            for col in metadata['columns']:
                col_name = col['name'].lower()
                if 'patient' in col_name and ('reference' in col_name or 'id' in col_name):
                    patient_tables.append(table)
                    break

        return patient_tables

    def get_column_type(self, table_name: str, column_name: str) -> Optional[str]:
        """
        Get the data type of a specific column.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            Data type string or None if not found
        """
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            return None

        for col in table_schema['columns']:
            if col['name'] == column_name:
                return col['type']

        return None

    def generate_count_query(
        self,
        table_name: str,
        patient_id: str,
        database: str = 'fhir_prd_db'
    ) -> Optional[str]:
        """
        Generate a COUNT query for a specific table and patient.

        Args:
            table_name: Table to query
            patient_id: Patient FHIR ID
            database: Database name

        Returns:
            SQL query string or None if table doesn't have patient reference
        """
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            logger.warning(f"Table not found: {table_name}")
            return None

        # Find patient reference column
        patient_col = None
        for col in table_schema['columns']:
            col_name = col['name'].lower()
            if 'patient' in col_name and ('reference' in col_name or 'fhir_id' in col_name or 'id' in col_name):
                patient_col = col['name']
                break

        if not patient_col:
            logger.debug(f"No patient reference column found in {table_name}")
            return None

        # Generate query
        query = f"""
        SELECT COUNT(*) as count
        FROM {database}.{table_name}
        WHERE {patient_col} = 'Patient/{patient_id}'
           OR {patient_col} = '{patient_id}'
        """

        return query.strip()

    def generate_sample_query(
        self,
        table_name: str,
        column_name: str,
        limit: int = 20,
        database: str = 'fhir_prd_db'
    ) -> Optional[str]:
        """
        Generate a query to sample distinct values from a column.

        Args:
            table_name: Table to query
            column_name: Column to sample
            limit: Number of samples
            database: Database name

        Returns:
            SQL query string
        """
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            return None

        # Verify column exists
        column_exists = any(col['name'] == column_name for col in table_schema['columns'])
        if not column_exists:
            logger.warning(f"Column {column_name} not found in {table_name}")
            return None

        query = f"""
        SELECT DISTINCT {column_name}
        FROM {database}.{table_name}
        WHERE {column_name} IS NOT NULL
        LIMIT {limit}
        """

        return query.strip()

    def identify_date_columns(self, table_name: str) -> List[str]:
        """
        Identify columns in a table that likely contain dates.

        Args:
            table_name: Table to analyze

        Returns:
            List of column names that likely contain dates
        """
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            return []

        date_columns = []
        date_keywords = ['date', 'time', 'period', 'start', 'end', 'when', 'recorded']

        for col in table_schema['columns']:
            col_name = col['name'].lower()
            if any(keyword in col_name for keyword in date_keywords):
                date_columns.append(col['name'])

        return date_columns

    def get_table_info_summary(self, table_name: str) -> Dict:
        """
        Get comprehensive information about a table.

        Args:
            table_name: Table to summarize

        Returns:
            Dict with table summary information
        """
        table_schema = self.get_table_schema(table_name)
        if not table_schema:
            return {}

        return {
            'table_name': table_name,
            'column_count': len(table_schema['columns']),
            'columns': [col['name'] for col in table_schema['columns']],
            'date_columns': self.identify_date_columns(table_name),
            'has_patient_reference': any(
                'patient' in col['name'].lower()
                for col in table_schema['columns']
            )
        }


if __name__ == '__main__':
    # Test the schema loader
    schema_path = '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv'

    loader = AthenaSchemaLoader(schema_path)

    print(f"Total tables: {len(loader.list_tables())}")
    print(f"\nPatient reference tables: {len(loader.find_patient_reference_tables())}")

    # Test table info
    print("\nEncounter table info:")
    info = loader.get_table_info_summary('encounter')
    print(f"  Columns: {info['column_count']}")
    print(f"  Date columns: {info['date_columns']}")

    # Test query generation
    print("\nGenerated count query:")
    query = loader.generate_count_query('encounter', 'test-patient-id')
    print(query)
