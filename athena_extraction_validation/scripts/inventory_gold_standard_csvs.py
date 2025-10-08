#!/usr/bin/env python3
"""
Inventory Gold Standard CSVs - Phase 1 Discovery

Purpose:
  Systematically discover and catalog all gold standard CSV files to understand
  what variables need to be extracted from Athena fhir_v2_prd_db.

Inputs:
  - Directory path containing 20250723_multitab_*.csv files
  
Outputs:
  - gold_standard_inventory.json: Complete catalog of all CSVs with metadata
  - gold_standard_summary.md: Human-readable summary report

Usage:
  python scripts/inventory_gold_standard_csvs.py \\
    --csv-dir /Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs \\
    --output-dir athena_extraction_validation/inventory
"""

import argparse
import json
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


class GoldStandardInventory:
    """Discover and catalog all gold standard CSV files"""
    
    def __init__(self, csv_dir: str, output_dir: str):
        self.csv_dir = Path(csv_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.inventory = {}
        
    def discover_csv_files(self) -> List[Path]:
        """Find all CSV files matching gold standard pattern"""
        csv_files = list(self.csv_dir.glob("20250723_multitab_*.csv"))
        csv_files.sort()
        print(f"\n📁 Discovered {len(csv_files)} gold standard CSV files")
        return csv_files
    
    def extract_csv_metadata(self, csv_path: Path) -> Dict[str, Any]:
        """Extract comprehensive metadata from a single CSV file"""
        print(f"\n📊 Analyzing: {csv_path.name}")
        
        # Read CSV
        try:
            df = pd.read_csv(csv_path, nrows=100)  # Sample first 100 rows
            df_full_count = pd.read_csv(csv_path, usecols=[0])  # Just count rows efficiently
            
            metadata = {
                'filename': csv_path.name,
                'full_path': str(csv_path.absolute()),
                'file_size_mb': round(csv_path.stat().st_size / (1024 * 1024), 2),
                'table_name': csv_path.stem.replace('20250723_multitab__', ''),
                'total_rows': len(df_full_count),
                'total_columns': len(df.columns),
                'columns': self._analyze_columns(df),
                'sample_row': df.head(1).to_dict('records')[0] if not df.empty else {},
                'date_fields': self._identify_date_fields(df),
                'identifier_fields': self._identify_identifier_fields(df),
                'categorical_fields': self._identify_categorical_fields(df),
                'numeric_fields': self._identify_numeric_fields(df),
                'completeness': self._calculate_completeness(df),
                'analysis_date': datetime.now().isoformat()
            }
            
            print(f"  ✅ Rows: {metadata['total_rows']:,} | Columns: {metadata['total_columns']}")
            
            return metadata
            
        except Exception as e:
            print(f"  ❌ Error analyzing {csv_path.name}: {str(e)}")
            return {
                'filename': csv_path.name,
                'error': str(e),
                'analysis_date': datetime.now().isoformat()
            }
    
    def _analyze_columns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detailed analysis of each column"""
        columns = []
        for col in df.columns:
            col_info = {
                'name': col,
                'dtype': str(df[col].dtype),
                'null_count': int(df[col].isnull().sum()),
                'null_percent': round(df[col].isnull().sum() / len(df) * 100, 2),
                'unique_values': int(df[col].nunique()),
                'sample_values': df[col].dropna().head(3).tolist()
            }
            columns.append(col_info)
        return columns
    
    def _identify_date_fields(self, df: pd.DataFrame) -> List[str]:
        """Identify fields containing dates"""
        date_fields = []
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['date', 'time', 'age_at', 'dob']):
                date_fields.append(col)
        return date_fields
    
    def _identify_identifier_fields(self, df: pd.DataFrame) -> List[str]:
        """Identify primary/foreign key fields"""
        id_fields = []
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['id', 'key', 'research_id', 'patient_id', 'event_id']):
                id_fields.append(col)
        return id_fields
    
    def _identify_categorical_fields(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Identify categorical fields with value counts"""
        categorical = []
        for col in df.columns:
            if df[col].dtype == 'object' and df[col].nunique() < 20:
                value_counts = df[col].value_counts().head(10).to_dict()
                categorical.append({
                    'field': col,
                    'unique_values': int(df[col].nunique()),
                    'top_values': value_counts
                })
        return categorical
    
    def _identify_numeric_fields(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Identify numeric fields with basic stats"""
        numeric = []
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric.append({
                    'field': col,
                    'min': float(df[col].min()) if not df[col].isnull().all() else None,
                    'max': float(df[col].max()) if not df[col].isnull().all() else None,
                    'mean': float(df[col].mean()) if not df[col].isnull().all() else None
                })
        return numeric
    
    def _calculate_completeness(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate overall data completeness"""
        total_cells = df.shape[0] * df.shape[1]
        filled_cells = df.count().sum()
        return {
            'overall_percent': round(filled_cells / total_cells * 100, 2) if total_cells > 0 else 0,
            'total_cells': int(total_cells),
            'filled_cells': int(filled_cells),
            'null_cells': int(total_cells - filled_cells)
        }
    
    def generate_inventory(self) -> Dict[str, Any]:
        """Generate complete inventory of all CSVs"""
        csv_files = self.discover_csv_files()
        
        inventory = {
            'generation_date': datetime.now().isoformat(),
            'csv_directory': str(self.csv_dir),
            'total_csv_files': len(csv_files),
            'csvs': {}
        }
        
        for csv_path in csv_files:
            table_name = csv_path.stem.replace('20250723_multitab__', '')
            inventory['csvs'][table_name] = self.extract_csv_metadata(csv_path)
        
        return inventory
    
    def save_inventory_json(self, inventory: Dict[str, Any]):
        """Save inventory as JSON"""
        output_path = self.output_dir / 'gold_standard_inventory.json'
        with open(output_path, 'w') as f:
            json.dump(inventory, f, indent=2)
        print(f"\n✅ Saved JSON inventory: {output_path}")
    
    def generate_markdown_summary(self, inventory: Dict[str, Any]):
        """Generate human-readable Markdown summary"""
        md_lines = [
            "# Gold Standard CSV Inventory",
            f"\n**Generation Date**: {inventory['generation_date']}",
            f"**CSV Directory**: `{inventory['csv_directory']}`",
            f"**Total CSV Files**: {inventory['total_csv_files']}",
            "\n---\n",
            "## Summary Table\n",
            "| CSV Name | Rows | Columns | Size (MB) | Completeness | Status |",
            "|----------|------|---------|-----------|--------------|--------|"
        ]
        
        for table_name, metadata in inventory['csvs'].items():
            if 'error' not in metadata:
                row = (
                    f"| `{table_name}` "
                    f"| {metadata['total_rows']:,} "
                    f"| {metadata['total_columns']} "
                    f"| {metadata['file_size_mb']} "
                    f"| {metadata['completeness']['overall_percent']}% "
                    f"| ✅ Analyzed |"
                )
            else:
                row = f"| `{table_name}` | ERROR | - | - | - | ❌ Error |"
            md_lines.append(row)
        
        md_lines.extend([
            "\n---\n",
            "## Detailed Analysis\n"
        ])
        
        for table_name, metadata in inventory['csvs'].items():
            if 'error' not in metadata:
                md_lines.extend(self._generate_csv_detail_section(table_name, metadata))
        
        output_path = self.output_dir / 'gold_standard_summary.md'
        with open(output_path, 'w') as f:
            f.write('\n'.join(md_lines))
        print(f"✅ Saved Markdown summary: {output_path}")
    
    def _generate_csv_detail_section(self, table_name: str, metadata: Dict[str, Any]) -> List[str]:
        """Generate detailed Markdown section for one CSV"""
        lines = [
            f"\n### {table_name}.csv\n",
            f"**File**: `{metadata['filename']}`  ",
            f"**Rows**: {metadata['total_rows']:,}  ",
            f"**Columns**: {metadata['total_columns']}  ",
            f"**Size**: {metadata['file_size_mb']} MB  ",
            f"**Completeness**: {metadata['completeness']['overall_percent']}%\n"
        ]
        
        # Column list
        lines.append("#### Columns\n")
        lines.append("| Column Name | Type | Null % | Unique Values | Sample |")
        lines.append("|-------------|------|--------|---------------|--------|")
        for col in metadata['columns']:
            sample = ', '.join([str(v) for v in col['sample_values'][:2]])
            if len(sample) > 50:
                sample = sample[:47] + "..."
            lines.append(
                f"| `{col['name']}` "
                f"| {col['dtype']} "
                f"| {col['null_percent']}% "
                f"| {col['unique_values']} "
                f"| {sample} |"
            )
        
        # Identifier fields
        if metadata['identifier_fields']:
            lines.append(f"\n**Identifier Fields**: {', '.join([f'`{f}`' for f in metadata['identifier_fields']])}")
        
        # Date fields
        if metadata['date_fields']:
            lines.append(f"**Date Fields**: {', '.join([f'`{f}`' for f in metadata['date_fields']])}")
        
        # Categorical fields
        if metadata['categorical_fields']:
            lines.append("\n#### Categorical Fields\n")
            for cat in metadata['categorical_fields']:
                lines.append(f"**`{cat['field']}`** ({cat['unique_values']} unique values):")
                for value, count in list(cat['top_values'].items())[:5]:
                    lines.append(f"  - `{value}`: {count}")
        
        lines.append("\n---\n")
        return lines
    
    def run(self):
        """Execute complete inventory process"""
        print("\n" + "="*60)
        print("  GOLD STANDARD CSV INVENTORY")
        print("="*60)
        
        inventory = self.generate_inventory()
        self.save_inventory_json(inventory)
        self.generate_markdown_summary(inventory)
        
        print("\n" + "="*60)
        print(f"  ✅ INVENTORY COMPLETE: {inventory['total_csv_files']} CSVs analyzed")
        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Inventory and catalog all gold standard CSV files'
    )
    parser.add_argument(
        '--csv-dir',
        required=True,
        help='Directory containing 20250723_multitab_*.csv files'
    )
    parser.add_argument(
        '--output-dir',
        default='athena_extraction_validation/inventory',
        help='Directory for output files'
    )
    
    args = parser.parse_args()
    
    inventory_tool = GoldStandardInventory(args.csv_dir, args.output_dir)
    inventory_tool.run()


if __name__ == '__main__':
    main()
