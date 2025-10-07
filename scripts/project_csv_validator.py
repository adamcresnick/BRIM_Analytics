#!/usr/bin/env python3
"""
Project CSV Validation and Sanitization Utility

This module ensures project.csv files meet BRIM requirements by:
1. Detecting and removing duplicate rows (NOTE_ID + PERSON_ID combinations)
2. Standardizing patient IDs (consistent format like 'C1277724')
3. Validating required fields and data quality
4. Reporting issues before upload

CRITICAL ISSUES ADDRESSED:
- Issue 1: Duplicate NOTE_IDs cause "X duplicate rows" warnings in BRIM
- Issue 2: Inconsistent PERSON_ID formats (e.g., '1277724' vs 'C1277724') cause BRIM to count multiple patients
- Issue 3: Missing or empty required fields cause upload failures

Usage:
    from project_csv_validator import ProjectCSVValidator
    
    validator = ProjectCSVValidator()
    issues = validator.validate_and_fix('project.csv', 'project_clean.csv')
    
Or command line:
    python project_csv_validator.py --input project.csv --output project_clean.csv
"""

import csv
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set
from collections import Counter
import re


class ProjectCSVValidator:
    """Validates and sanitizes BRIM project.csv files"""
    
    # BRIM required columns for project.csv
    REQUIRED_COLUMNS = ['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE']
    
    # Expected patient ID patterns (add your patterns)
    # Pattern 1: C followed by numbers (e.g., C1277724)
    # Pattern 2: Just numbers (e.g., 1277724) - will be standardized to Pattern 1
    PATIENT_ID_PATTERNS = {
        'with_prefix': re.compile(r'^C\d+$'),  # C1277724
        'without_prefix': re.compile(r'^\d+$'),  # 1277724
    }
    
    def __init__(self, field_size_limit: int = 10000000):
        """
        Initialize validator.
        
        Args:
            field_size_limit: Max CSV field size (default 10MB for large NOTE_TEXT fields)
        """
        csv.field_size_limit(field_size_limit)
        self.issues = []
        self.warnings = []
        self.fixes_applied = []
    
    def validate_and_fix(
        self, 
        input_path: str, 
        output_path: str = None,
        standardize_patient_ids: bool = True,
        remove_duplicates: bool = True,
        backup: bool = True
    ) -> Dict[str, any]:
        """
        Validate and fix project.csv file.
        
        Args:
            input_path: Path to input project.csv
            output_path: Path to output fixed CSV (if None, overwrites input)
            standardize_patient_ids: Whether to standardize PERSON_ID format
            remove_duplicates: Whether to remove duplicate rows
            backup: Whether to create backup before overwriting
            
        Returns:
            Dictionary with validation results and statistics
        """
        input_file = Path(input_path)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Set output path
        if output_path is None:
            output_path = input_path
        output_file = Path(output_path)
        
        # Create backup if overwriting
        if backup and input_path == output_path:
            backup_path = self._create_backup(input_file)
            print(f"✅ Backup created: {backup_path}")
        
        print("=" * 80)
        print("PROJECT.CSV VALIDATION AND SANITIZATION")
        print("=" * 80)
        print(f"Input:  {input_file}")
        print(f"Output: {output_file}")
        print()
        
        # Reset tracking
        self.issues = []
        self.warnings = []
        self.fixes_applied = []
        
        # Step 1: Validate structure
        print("📋 Step 1: Validating CSV structure...")
        structure_ok = self._validate_structure(input_file)
        
        # Step 2: Load and analyze data
        print("\n📊 Step 2: Loading and analyzing data...")
        rows, stats = self._load_and_analyze(input_file)
        
        # Step 3: Detect patient ID inconsistencies
        print("\n🔍 Step 3: Checking patient ID consistency...")
        patient_id_issues = self._check_patient_ids(rows)
        
        # Step 4: Detect duplicates
        print("\n🔍 Step 4: Checking for duplicate rows...")
        duplicate_issues = self._check_duplicates(rows)
        
        # Step 5: Apply fixes
        print("\n🔧 Step 5: Applying fixes...")
        fixed_rows = rows.copy()
        
        if standardize_patient_ids and patient_id_issues['inconsistent_formats']:
            fixed_rows = self._standardize_patient_ids(fixed_rows, patient_id_issues)
        
        if remove_duplicates and duplicate_issues['total_duplicates'] > 0:
            fixed_rows = self._remove_duplicates(fixed_rows)
        
        # Step 6: Final validation
        print("\n✅ Step 6: Final validation...")
        final_stats = self._get_stats(fixed_rows)
        
        # Step 7: Write output
        print("\n💾 Step 7: Writing output file...")
        self._write_csv(output_file, fixed_rows)
        
        # Summary
        return self._generate_summary(stats, final_stats, patient_id_issues, duplicate_issues)
    
    def _create_backup(self, filepath: Path) -> Path:
        """Create timestamped backup of file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.parent / f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
        
        import shutil
        shutil.copy2(filepath, backup_path)
        
        return backup_path
    
    def _validate_structure(self, filepath: Path) -> bool:
        """Validate CSV has required columns"""
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            if fieldnames is None:
                self.issues.append("❌ CRITICAL: CSV has no header row")
                return False
            
            missing = set(self.REQUIRED_COLUMNS) - set(fieldnames)
            if missing:
                self.issues.append(f"❌ CRITICAL: Missing required columns: {missing}")
                return False
            
            extra = set(fieldnames) - set(self.REQUIRED_COLUMNS)
            if extra:
                self.warnings.append(f"⚠️  Extra columns found (will be ignored): {extra}")
            
            print(f"   ✅ All required columns present: {self.REQUIRED_COLUMNS}")
            return True
    
    def _load_and_analyze(self, filepath: Path) -> Tuple[List[Dict], Dict]:
        """Load CSV and get basic statistics"""
        rows = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        stats = self._get_stats(rows)
        
        print(f"   ✅ Loaded {stats['total_rows']} rows")
        print(f"      - Unique NOTE_IDs: {stats['unique_note_ids']}")
        print(f"      - Unique PERSON_IDs: {stats['unique_person_ids']}")
        print(f"      - Date range: {stats['date_range']}")
        
        return rows, stats
    
    def _get_stats(self, rows: List[Dict]) -> Dict:
        """Calculate statistics for rows"""
        note_ids = [r['NOTE_ID'] for r in rows if r.get('NOTE_ID')]
        person_ids = [r['PERSON_ID'] for r in rows if r.get('PERSON_ID')]
        datetimes = [r['NOTE_DATETIME'] for r in rows if r.get('NOTE_DATETIME')]
        
        return {
            'total_rows': len(rows),
            'unique_note_ids': len(set(note_ids)),
            'unique_person_ids': len(set(person_ids)),
            'person_id_values': sorted(set(person_ids)),
            'date_range': f"{min(datetimes) if datetimes else 'N/A'} to {max(datetimes) if datetimes else 'N/A'}",
            'empty_note_text': sum(1 for r in rows if not r.get('NOTE_TEXT', '').strip()),
            'empty_note_id': sum(1 for r in rows if not r.get('NOTE_ID', '').strip()),
            'empty_person_id': sum(1 for r in rows if not r.get('PERSON_ID', '').strip()),
        }
    
    def _check_patient_ids(self, rows: List[Dict]) -> Dict:
        """Check for patient ID inconsistencies"""
        person_ids = [r['PERSON_ID'] for r in rows if r.get('PERSON_ID')]
        unique_ids = set(person_ids)
        
        # Categorize by pattern
        with_prefix = []
        without_prefix = []
        invalid = []
        
        for pid in unique_ids:
            if self.PATIENT_ID_PATTERNS['with_prefix'].match(pid):
                with_prefix.append(pid)
            elif self.PATIENT_ID_PATTERNS['without_prefix'].match(pid):
                without_prefix.append(pid)
            else:
                invalid.append(pid)
        
        issues = {
            'total_unique': len(unique_ids),
            'with_prefix': with_prefix,
            'without_prefix': without_prefix,
            'invalid': invalid,
            'inconsistent_formats': len(with_prefix) > 0 and len(without_prefix) > 0,
        }
        
        # Report issues
        if issues['inconsistent_formats']:
            print(f"   ❌ CRITICAL: Inconsistent patient ID formats detected!")
            print(f"      - With 'C' prefix: {with_prefix}")
            print(f"      - Without 'C' prefix: {without_prefix}")
            print(f"      → BRIM will count these as {len(unique_ids)} different patients!")
            self.issues.append("Inconsistent PERSON_ID formats")
        elif len(unique_ids) > 1:
            print(f"   ⚠️  Multiple patient IDs found: {sorted(unique_ids)}")
            print(f"      (Formats are consistent, but confirm this is expected)")
            self.warnings.append(f"Multiple patients in file: {sorted(unique_ids)}")
        else:
            print(f"   ✅ Consistent patient ID: {list(unique_ids)[0]}")
        
        if invalid:
            print(f"   ❌ CRITICAL: Invalid patient ID format: {invalid}")
            self.issues.append(f"Invalid PERSON_ID formats: {invalid}")
        
        # Show row counts per ID
        id_counts = Counter(person_ids)
        for pid, count in sorted(id_counts.items()):
            print(f"      - {pid}: {count} rows")
        
        return issues
    
    def _check_duplicates(self, rows: List[Dict]) -> Dict:
        """Check for duplicate rows"""
        # Check NOTE_ID duplicates (most critical for BRIM)
        note_ids = [r['NOTE_ID'] for r in rows]
        note_id_counts = Counter(note_ids)
        duplicates = {nid: count for nid, count in note_id_counts.items() if count > 1}
        
        # Check full row duplicates (NOTE_ID + PERSON_ID combination)
        row_keys = [(r['NOTE_ID'], r['PERSON_ID']) for r in rows]
        row_key_counts = Counter(row_keys)
        full_duplicates = {key: count for key, count in row_key_counts.items() if count > 1}
        
        issues = {
            'total_duplicates': len(rows) - len(set(note_ids)),
            'duplicate_note_ids': duplicates,
            'duplicate_combinations': full_duplicates,
        }
        
        if duplicates:
            print(f"   ❌ CRITICAL: {len(duplicates)} NOTE_IDs have duplicates!")
            print(f"      Total duplicate rows: {issues['total_duplicates']}")
            for nid, count in sorted(duplicates.items())[:5]:  # Show first 5
                print(f"      - {nid}: {count} occurrences")
            if len(duplicates) > 5:
                print(f"      ... and {len(duplicates) - 5} more")
            self.issues.append(f"{len(duplicates)} duplicate NOTE_IDs")
        else:
            print(f"   ✅ No duplicate NOTE_IDs found")
        
        return issues
    
    def _standardize_patient_ids(self, rows: List[Dict], patient_id_issues: Dict) -> List[Dict]:
        """Standardize patient IDs to consistent format (add 'C' prefix if missing)"""
        print("   🔧 Standardizing patient IDs...")
        
        # Build mapping: without_prefix -> with_prefix
        # E.g., '1277724' -> 'C1277724'
        mapping = {}
        for without in patient_id_issues['without_prefix']:
            # Find corresponding with_prefix version
            expected_with = f"C{without}"
            if expected_with in patient_id_issues['with_prefix']:
                mapping[without] = expected_with
            else:
                # No corresponding version, just add 'C'
                mapping[without] = expected_with
        
        # Apply mapping
        fixed_count = 0
        for row in rows:
            old_id = row['PERSON_ID']
            if old_id in mapping:
                row['PERSON_ID'] = mapping[old_id]
                fixed_count += 1
        
        print(f"      ✅ Fixed {fixed_count} rows")
        for old, new in mapping.items():
            print(f"         {old} → {new}")
        
        self.fixes_applied.append(f"Standardized {fixed_count} PERSON_IDs")
        
        return rows
    
    def _remove_duplicates(self, rows: List[Dict]) -> List[Dict]:
        """Remove duplicate rows, keeping first occurrence"""
        print("   🔧 Removing duplicate rows...")
        
        seen_note_ids = set()
        dedup_rows = []
        removed = []
        
        for row in rows:
            note_id = row['NOTE_ID']
            if note_id not in seen_note_ids:
                seen_note_ids.add(note_id)
                dedup_rows.append(row)
            else:
                removed.append(note_id)
        
        print(f"      ✅ Removed {len(removed)} duplicate rows")
        if removed[:3]:
            print(f"         First duplicates removed: {removed[:3]}")
        
        self.fixes_applied.append(f"Removed {len(removed)} duplicate rows")
        
        return dedup_rows
    
    def _write_csv(self, filepath: Path, rows: List[Dict]):
        """Write sanitized CSV"""
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.REQUIRED_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"   ✅ Written {len(rows)} rows ({file_size_mb:.2f} MB)")
    
    def _generate_summary(self, before_stats: Dict, after_stats: Dict, 
                         patient_id_issues: Dict, duplicate_issues: Dict) -> Dict:
        """Generate summary report"""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        # Before/After
        print("\n📊 Before → After:")
        print(f"   Total rows:        {before_stats['total_rows']} → {after_stats['total_rows']}")
        print(f"   Unique NOTE_IDs:   {before_stats['unique_note_ids']} → {after_stats['unique_note_ids']}")
        print(f"   Unique PERSON_IDs: {before_stats['unique_person_ids']} → {after_stats['unique_person_ids']}")
        
        # Issues found
        if self.issues:
            print(f"\n❌ Critical Issues ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   - {issue}")
        else:
            print("\n✅ No critical issues found")
        
        # Warnings
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        # Fixes applied
        if self.fixes_applied:
            print(f"\n🔧 Fixes Applied ({len(self.fixes_applied)}):")
            for fix in self.fixes_applied:
                print(f"   - {fix}")
        
        # Final status
        print("\n" + "=" * 80)
        if not self.issues and after_stats['unique_person_ids'] == 1:
            print("✅ PROJECT.CSV IS READY FOR BRIM UPLOAD")
            print(f"   - {after_stats['total_rows']} rows")
            print(f"   - {after_stats['unique_note_ids']} unique documents")
            print(f"   - 1 patient: {after_stats['person_id_values'][0]}")
        elif not self.issues:
            print("⚠️  PROJECT.CSV HAS WARNINGS BUT CAN BE UPLOADED")
            print(f"   - Multiple patients detected: {after_stats['person_id_values']}")
        else:
            print("❌ PROJECT.CSV HAS ISSUES - REVIEW BEFORE UPLOAD")
        print("=" * 80)
        
        return {
            'before': before_stats,
            'after': after_stats,
            'issues': self.issues,
            'warnings': self.warnings,
            'fixes_applied': self.fixes_applied,
            'patient_id_issues': patient_id_issues,
            'duplicate_issues': duplicate_issues,
            'ready_for_upload': len(self.issues) == 0,
        }


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Validate and sanitize BRIM project.csv files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate and fix in place (creates backup)
  python project_csv_validator.py --input project.csv
  
  # Validate and write to new file
  python project_csv_validator.py --input project.csv --output project_clean.csv
  
  # Check only, don't fix
  python project_csv_validator.py --input project.csv --check-only
        """
    )
    
    parser.add_argument('--input', required=True, help='Input project.csv file')
    parser.add_argument('--output', help='Output file (default: overwrite input)')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup when overwriting')
    parser.add_argument('--check-only', action='store_true', help='Validate only, do not fix')
    
    args = parser.parse_args()
    
    validator = ProjectCSVValidator()
    
    if args.check_only:
        # Just validate, don't write
        print("CHECK-ONLY MODE (no fixes will be applied)")
        print()
        validator.validate_and_fix(
            args.input,
            output_path=args.input + '.tmp',  # Temp file
            backup=False
        )
        # Remove temp file
        Path(args.input + '.tmp').unlink(missing_ok=True)
    else:
        # Validate and fix
        result = validator.validate_and_fix(
            args.input,
            output_path=args.output,
            backup=not args.no_backup
        )
        
        # Exit code based on results
        sys.exit(0 if result['ready_for_upload'] else 1)


if __name__ == '__main__':
    main()
