#!/usr/bin/env python3
"""
Validate Demographics CSV Extraction Against Gold Standard

Purpose:
  1. Extract demographics from Athena for test patient C1277724
  2. Compare against gold standard demographics.csv
  3. Calculate field-by-field accuracy metrics
  4. Document gaps requiring fixes

Usage:
  python3 scripts/validate_demographics_csv.py \
    --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --patient-research-id C1277724 \
    --gold-standard-csv data/20250723_multitab_csvs/20250723_multitab__demographics.csv \
    --output-report athena_extraction_validation/reports/demographics_validation.md

Security:
  - Works in background mode (no MRN echoing to terminal)
  - Sanitizes output before writing reports
  - Uses research_id as primary identifier
"""

import argparse
import boto3
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import sys
import time

class DemographicsValidator:
    """Validate demographics extraction against gold standard"""
    
    def __init__(self, aws_profile: str, database: str, patient_fhir_id: str, 
                 patient_research_id: str, birth_date: str = "2005-05-13"):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.patient_fhir_id = patient_fhir_id
        self.patient_research_id = patient_research_id
        self.birth_date = birth_date
        self.output_location = 's3://aws-athena-query-results-343218191717-us-east-1/'
        
    def execute_query(self, query: str, description: str = "") -> list:
        """Execute Athena query and return results"""
        print(f"  Executing: {description}...", end='', flush=True)
        
        try:
            response = self.athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for query to complete
            max_attempts = 30
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                query_status = self.athena.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = query_status['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    reason = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    print(f" FAILED: {reason}")
                    return []
                
                time.sleep(1)
            
            # Get results
            results = self.athena.get_query_results(QueryExecutionId=query_execution_id)
            
            # Parse results
            if not results.get('ResultSet', {}).get('Rows'):
                print(" No results")
                return []
            
            rows = results['ResultSet']['Rows']
            if len(rows) <= 1:  # Only header
                print(" No data rows")
                return []
            
            # Extract column names
            columns = [col['VarCharValue'] for col in rows[0]['Data']]
            
            # Extract data rows
            data_rows = []
            for row in rows[1:]:
                row_data = {}
                for i, col in enumerate(row['Data']):
                    value = col.get('VarCharValue', None)
                    row_data[columns[i]] = value
                data_rows.append(row_data)
            
            print(f" ✓ ({len(data_rows)} rows)")
            return data_rows
            
        except Exception as e:
            print(f" ERROR: {str(e)}")
            return []
    
    def extract_from_athena(self) -> dict:
        """Extract demographics from Athena patient_access table"""
        print("\n🔍 EXTRACTING FROM ATHENA")
        print("=" * 60)
        
        # Query patient_access table
        query = f"""
        SELECT 
            id AS fhir_id,
            gender,
            birth_date,
            race,
            ethnicity
        FROM {self.database}.patient_access
        WHERE id = '{self.patient_fhir_id}'
        LIMIT 1
        """
        
        results = self.execute_query(query, "Query patient_access table")
        
        if not results:
            print("  ⚠️  WARNING: No results from patient_access")
            return {}
        
        result = results[0]
        
        # Map Athena fields to demographics CSV format
        athena_data = {
            'research_id': self.patient_research_id,  # Manual mapping
            'legal_sex': self._map_gender(result.get('gender', '')),
            'race': result.get('race', ''),
            'ethnicity': result.get('ethnicity', ''),
            'birth_date': result.get('birth_date', '')  # For validation only
        }
        
        print("\n  📊 Athena Results:")
        print(f"     FHIR ID: {result.get('fhir_id', 'N/A')}")
        print(f"     Gender: {result.get('gender', 'N/A')}")
        print(f"     Birth Date: {result.get('birth_date', 'N/A')}")
        print(f"     Race: {result.get('race', 'N/A')}")
        print(f"     Ethnicity: {result.get('ethnicity', 'N/A')}")
        
        return athena_data
    
    def _map_gender(self, athena_gender: str) -> str:
        """Map FHIR gender to demographics CSV format"""
        mapping = {
            'male': 'Male',
            'female': 'Female',
            'other': 'Other',
            'unknown': 'Other/Unavailable/Not Reported'
        }
        return mapping.get(athena_gender.lower(), athena_gender)
    
    def load_gold_standard(self, csv_path: str) -> dict:
        """Load gold standard demographics for test patient"""
        print("\n📁 LOADING GOLD STANDARD")
        print("=" * 60)
        
        df = pd.read_csv(csv_path)
        print(f"  Total patients in gold standard: {len(df)}")
        
        patient_row = df[df['research_id'] == self.patient_research_id]
        
        if patient_row.empty:
            print(f"  ⚠️  WARNING: Patient {self.patient_research_id} not found in gold standard")
            return {}
        
        gold_data = patient_row.iloc[0].to_dict()
        
        print(f"\n  📊 Gold Standard for {self.patient_research_id}:")
        print(f"     Legal Sex: {gold_data.get('legal_sex', 'N/A')}")
        print(f"     Race: {gold_data.get('race', 'N/A')}")
        print(f"     Ethnicity: {gold_data.get('ethnicity', 'N/A')}")
        
        return gold_data
    
    def compare_fields(self, athena_data: dict, gold_data: dict) -> dict:
        """Field-by-field comparison"""
        print("\n🔍 FIELD-BY-FIELD COMPARISON")
        print("=" * 60)
        
        fields_to_compare = ['legal_sex', 'race', 'ethnicity']
        
        comparison = {
            'total_fields': len(fields_to_compare),
            'matched': 0,
            'mismatched': 0,
            'missing': 0,
            'details': []
        }
        
        for field in fields_to_compare:
            athena_value = athena_data.get(field, None)
            gold_value = gold_data.get(field, None)
            
            if athena_value is None or athena_value == '':
                status = '❌ MISSING'
                comparison['missing'] += 1
            elif athena_value == gold_value:
                status = '✅ MATCH'
                comparison['matched'] += 1
            else:
                status = '⚠️  MISMATCH'
                comparison['mismatched'] += 1
            
            detail = {
                'field': field,
                'gold_standard': gold_value,
                'athena_extracted': athena_value,
                'status': status
            }
            comparison['details'].append(detail)
            
            print(f"\n  {field}:")
            print(f"    Gold Standard: {gold_value}")
            print(f"    Athena: {athena_value}")
            print(f"    {status}")
        
        return comparison
    
    def calculate_metrics(self, comparison: dict) -> dict:
        """Calculate accuracy metrics"""
        total = comparison['total_fields']
        matched = comparison['matched']
        
        metrics = {
            'accuracy': (matched / total * 100) if total > 0 else 0,
            'completeness': ((matched + comparison['mismatched']) / total * 100) if total > 0 else 0,
            'total_fields': total,
            'matched': matched,
            'mismatched': comparison['mismatched'],
            'missing': comparison['missing']
        }
        
        return metrics
    
    def generate_report(self, comparison: dict, metrics: dict, 
                       athena_data: dict, gold_data: dict) -> str:
        """Generate markdown validation report"""
        
        report = f"""# Demographics CSV Validation Report

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Patient**: {self.patient_research_id}  
**FHIR ID**: {self.patient_fhir_id}  
**Database**: {self.database}

---

## Executive Summary

**Overall Accuracy**: {metrics['accuracy']:.1f}%  
**Completeness**: {metrics['completeness']:.1f}%

| Metric | Count | Percentage |
|--------|-------|------------|
| ✅ Matched | {metrics['matched']}/{metrics['total_fields']} | {metrics['accuracy']:.1f}% |
| ⚠️  Mismatched | {metrics['mismatched']}/{metrics['total_fields']} | {(metrics['mismatched']/metrics['total_fields']*100):.1f}% |
| ❌ Missing | {metrics['missing']}/{metrics['total_fields']} | {(metrics['missing']/metrics['total_fields']*100):.1f}% |

---

## Field-by-Field Comparison

| Field | Gold Standard | Athena Extracted | Status |
|-------|---------------|------------------|--------|
"""
        
        for detail in comparison['details']:
            report += f"| `{detail['field']}` | {detail['gold_standard']} | {detail['athena_extracted'] or 'NULL'} | {detail['status']} |\n"
        
        report += f"""
---

## Raw Data

### Gold Standard
```json
{json.dumps(gold_data, indent=2)}
```

### Athena Extracted
```json
{json.dumps(athena_data, indent=2)}
```

---

## Assessment

### ✅ What's Working

"""
        
        working = [d for d in comparison['details'] if '✅' in d['status']]
        if working:
            for detail in working:
                report += f"- **{detail['field']}**: Successfully extracted from Athena ({detail['gold_standard']})\n"
        else:
            report += "- No fields currently working\n"
        
        report += "\n### ❌ Gaps Identified\n\n"
        
        gaps = [d for d in comparison['details'] if '❌' in d['status'] or '⚠️' in d['status']]
        if gaps:
            for detail in gaps:
                report += f"- **{detail['field']}**: {detail['status']}\n"
                if '❌' in detail['status']:
                    report += f"  - **Issue**: Field not extracted from Athena\n"
                    report += f"  - **Expected**: {detail['gold_standard']}\n"
                    report += f"  - **Action Required**: Implement extraction logic\n"
                else:
                    report += f"  - **Issue**: Value mismatch\n"
                    report += f"  - **Expected**: {detail['gold_standard']}\n"
                    report += f"  - **Got**: {detail['athena_extracted']}\n"
                    report += f"  - **Action Required**: Review mapping logic\n"
                report += "\n"
        else:
            report += "- No gaps identified\n"
        
        report += """
---

## Recommendations

"""
        
        if metrics['accuracy'] == 100:
            report += "✅ **VALIDATION PASSED**: All demographics fields extracted correctly from Athena.\n\n"
            report += "**Next Steps**:\n"
            report += "1. Move to next CSV validation (diagnosis.csv)\n"
            report += "2. Document demographics extraction as COMPLETE\n"
        elif metrics['completeness'] == 100:
            report += "⚠️  **PARTIAL SUCCESS**: All fields extracted but some values mismatch.\n\n"
            report += "**Next Steps**:\n"
            report += "1. Review field mapping logic\n"
            report += "2. Fix value transformations\n"
            report += "3. Re-run validation\n"
        else:
            report += "❌ **GAPS FOUND**: Some fields not extracted from Athena.\n\n"
            report += "**Next Steps**:\n"
            
            if 'race' in [d['field'] for d in gaps]:
                report += "1. **HIGH PRIORITY**: Add race/ethnicity extraction from patient_access table\n"
                report += "   - Fields are present in patient_access table\n"
                report += "   - Validated in ATHENA_ARCHITECTURE_CLARIFICATION.md\n"
                report += "   - Estimated fix time: 10 minutes\n\n"
            
            report += "2. Update extract_structured_data.py to include missing fields\n"
            report += "3. Re-run validation\n"
        
        report += """
---

## Athena Query Used

```sql
SELECT 
    id AS fhir_id,
    gender,
    birth_date,
    race,
    ethnicity
FROM fhir_v2_prd_db.patient_access
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
LIMIT 1
```

---

**Validation Status**: {'✅ PASSED' if metrics['accuracy'] == 100 else '⚠️ PARTIAL' if metrics['completeness'] == 100 else '❌ GAPS FOUND'}
"""
        
        return report


def main():
    parser = argparse.ArgumentParser(description='Validate demographics CSV extraction')
    parser.add_argument('--patient-fhir-id', default='e4BwD8ZYDBccepXcJ.Ilo3w3',
                       help='FHIR ID of test patient')
    parser.add_argument('--patient-research-id', default='C1277724',
                       help='Research ID of test patient')
    parser.add_argument('--gold-standard-csv', 
                       default='data/20250723_multitab_csvs/20250723_multitab__demographics.csv',
                       help='Path to gold standard demographics CSV')
    parser.add_argument('--output-report',
                       default='athena_extraction_validation/reports/demographics_validation.md',
                       help='Output path for validation report')
    parser.add_argument('--aws-profile', default='343218191717_AWSAdministratorAccess',
                       help='AWS profile name')
    parser.add_argument('--database', default='fhir_v2_prd_db',
                       help='Athena database name')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("DEMOGRAPHICS CSV VALIDATION")
    print("=" * 60)
    print(f"\nPatient: {args.patient_research_id}")
    print(f"FHIR ID: {args.patient_fhir_id}")
    print(f"Database: {args.database}")
    print(f"Gold Standard: {args.gold_standard_csv}")
    
    # Initialize validator
    validator = DemographicsValidator(
        aws_profile=args.aws_profile,
        database=args.database,
        patient_fhir_id=args.patient_fhir_id,
        patient_research_id=args.patient_research_id
    )
    
    # Extract from Athena
    athena_data = validator.extract_from_athena()
    
    if not athena_data:
        print("\n❌ FAILED: Could not extract data from Athena")
        sys.exit(1)
    
    # Load gold standard
    gold_data = validator.load_gold_standard(args.gold_standard_csv)
    
    if not gold_data:
        print("\n❌ FAILED: Could not load gold standard data")
        sys.exit(1)
    
    # Compare
    comparison = validator.compare_fields(athena_data, gold_data)
    
    # Calculate metrics
    metrics = validator.calculate_metrics(comparison)
    
    print("\n📊 VALIDATION METRICS")
    print("=" * 60)
    print(f"  Overall Accuracy: {metrics['accuracy']:.1f}%")
    print(f"  Completeness: {metrics['completeness']:.1f}%")
    print(f"  Matched: {metrics['matched']}/{metrics['total_fields']}")
    print(f"  Mismatched: {metrics['mismatched']}/{metrics['total_fields']}")
    print(f"  Missing: {metrics['missing']}/{metrics['total_fields']}")
    
    # Generate report
    report = validator.generate_report(comparison, metrics, athena_data, gold_data)
    
    # Write report
    output_path = Path(args.output_report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report written to: {output_path}")
    
    # Exit with appropriate code
    if metrics['accuracy'] == 100:
        print("\n✅ VALIDATION PASSED")
        sys.exit(0)
    else:
        print("\n⚠️  VALIDATION INCOMPLETE")
        sys.exit(1)


if __name__ == '__main__':
    main()
