# Athena Extraction Validation Strategy
## Comprehensive Validation of FHIR v2 Database Queries Against Gold Standard CSVs

**Date**: October 7, 2025  
**Purpose**: Systematically validate which clinical trial variables CAN be fully extracted from Athena `fhir_v2_prd_db` alone vs which require narrative/BRIM extraction  
**Approach**: CSV-by-CSV validation targeting one output file at a time

---

## Executive Summary

This project validates **Athena-only extraction completeness** for 18 clinical trial CSV files by:
1. **Reviewing existing documentation** for each CSV's extraction methodology
2. **Identifying which variables** are 100% extractable from structured FHIR data
3. **Creating/validating extraction scripts** for each CSV independently
4. **Comparing outputs** against gold standard manually-created CSVs
5. **Documenting gaps** where narrative/BRIM extraction is required

---

## Documentation Review Summary

### Completed Work (From `/Users/resnick/Downloads/fhir_athena_crosswalk/documentation`)

| Document | Status | Key Insights |
|----------|--------|--------------|
| `CSV_MAPPING_MASTER_STATUS.md` | ✅ COMPLETE | Master tracker: 3 CSVs completed, 2 in progress, 8 frameworks documented |
| `CONCOMITANT_MEDICATIONS_FRAMEWORK.md` | ✅ COMPLETE | 370 lines - Temporal exclusion, therapeutic classification |
| `CONCOMITANT_MEDICATIONS_IMPLEMENTATION_GUIDE.md` | ✅ COMPLETE | 329 lines - Production SQL, RxNorm mapping, 85-90% coverage validated |
| `CONCOMITANT_MEDICATIONS_VALIDATION_RESULTS.md` | ✅ COMPLETE | 7.8KB - Test results showing category-level performance |
| `IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md` | ✅ COMPLETE | 324 lines - Corticosteroid reference (53 codes), radiology views |
| `IMAGING_CORTICOSTEROID_MAPPING_STRATEGY.md` | ✅ COMPLETE | Strategy for 10 drug families, temporal alignment |
| `MEASUREMENTS_IMPLEMENTATION_GUIDE.md` | ✅ COMPLETE | 408 lines - Anthropometric data, unit conversions |
| `COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md` | ✅ COMPLETE | 412 lines - Longitudinal timeline, visit classification |
| `ENCOUNTERS_VALIDATION_RESULTS.md` | ✅ COMPLETE | 7.4KB - 1000+ encounters validated |
| `COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md` | ✅ COMPLETE | 1076 lines - Multi-table surgical event detection |
| `COMPREHENSIVE_DIAGNOSTIC_CAPTURE_GUIDE.md` | ✅ COMPLETE | 442 lines - Diagnostic events, document linkages |
| `CONDITIONS_PREDISPOSITIONS_COMPREHENSIVE_MAPPING.md` | ✅ COMPLETE | Framework for genetic conditions |
| `COMPLETE_DOCUMENTATION_SUMMARY.md` | ✅ COMPLETE | Confirms all frameworks captured |

---

## Gold Standard CSV Files

### Location
```
/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/
```

### Known Files (From Documentation References)
1. `20250723_multitab__demographics.csv` - ✅ COMPLETED extraction
2. `20250723_multitab__diagnosis.csv` - ✅ COMPLETED extraction  
3. `20250723_multitab__concomitant_medications.csv` - ✅ COMPLETED extraction
4. `20250723_multitab__imaging_clinical_related.csv` - 🔄 IN PROGRESS
5. `20250723_multitab__measurements.csv` - 🔄 IN PROGRESS
6. `20250723_multitab__molecular_characterization.csv` - 📋 FRAMEWORK EXISTS
7. `20250723_multitab__molecular_tests_performed.csv` - 📋 FRAMEWORK EXISTS
8. `20250723_multitab__treatments.csv` (surgery/chemo/radiation) - 📋 FRAMEWORK EXISTS
9. `20250723_multitab__surgery.csv` - 📋 FRAMEWORK EXISTS
10. `20250723_multitab__radiation.csv` - 📋 FRAMEWORK EXISTS
11. `20250723_multitab__radiology.csv` - 📋 FRAMEWORK EXISTS
12. `20250723_multitab__survival.csv` - 📋 FRAMEWORK EXISTS
13. `20250723_multitab__therapeutic.csv` - 📋 FRAMEWORK EXISTS
14. Additional files to discover...

---

## CSV-by-CSV Validation Plan

### Validation Workflow (Per CSV)

```
For each CSV file:
  1. Read gold standard CSV structure
  2. Review existing documentation
  3. Map each column to FHIR v2 source
  4. Classify variables:
     - 100% Athena-extractable (structured data)
     - Partially Athena-extractable (needs enrichment)
     - Requires narrative extraction (BRIM needed)
  5. Create/validate extraction script
  6. Execute query against test patient (C1277724)
  7. Compare output vs gold standard
  8. Document coverage metrics
  9. Identify gaps requiring BRIM
```

---

## Phase 1: Inventory & Analysis

### Step 1.1: Discover All Gold Standard CSVs

**Script**: `scripts/inventory_gold_standard_csvs.py`

```python
"""
Scan 20250723_multitab_csvs/ directory
For each CSV:
  - Get file size
  - Read first 10 rows
  - Extract column names
  - Get row count
  - Identify primary keys
  - Detect date fields
  - Sample data types
Output: gold_standard_inventory.json
"""
```

**Output**: `athena_extraction_validation/gold_standard_inventory.json`

### Step 1.2: Map CSVs to Existing Documentation

**Script**: `scripts/map_csvs_to_documentation.py`

```python
"""
For each discovered CSV:
  - Search documentation for matching guides
  - Extract documented FHIR tables
  - Identify existing scripts
  - Classify completion status
  - List required Athena views
Output: csv_documentation_mapping.json
"""
```

**Output**: `athena_extraction_validation/csv_documentation_mapping.json`

---

## Phase 2: CSV-Specific Extraction & Validation

### Priority Order

#### **Tier 1: COMPLETED** (Validate Only)
1. ✅ **demographics.csv**
   - Script: `scripts/map_demographics.py`
   - Athena Tables: `patient_access`
   - Expected Coverage: 100%
   - Test: Compare Patient C1277724 output

2. ✅ **concomitant_medications.csv**
   - Script: `scripts/complete_medication_crosswalk.py`
   - Athena Tables: `medication_request`, `medication_code_coding`
   - Expected Coverage: 85-90%
   - Test: Validate therapeutic classification

#### **Tier 2: IN PROGRESS** (Complete & Validate)
3. 🔄 **imaging_clinical_related.csv**
   - Script: `scripts/map_imaging_clinical_related_v4.py`
   - Athena Tables: `radiology_imaging_mri`, `radiology_imaging_mri_results`, `medication_request`
   - Expected Coverage: 90%+
   - Gaps: Clinical status (narrative), ophthalmology flag (needs rule refinement)

4. 🔄 **measurements.csv**
   - Script: `scripts/map_measurements.py`
   - Athena Tables: `observation`, `lab_test_results`
   - Expected Coverage: 95%+
   - Gaps: Growth percentiles (requires CDC/WHO reference calculation)

#### **Tier 3: FRAMEWORKS EXIST** (Implement & Validate)
5. 📋 **encounters.csv**
   - Documentation: `COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md`
   - Athena Tables: `encounter`, `appointment`, `appointment_participant`
   - Expected Coverage: 100%
   - Action: Convert framework to script

6. 📋 **treatments.csv** (complex - surgery + chemo + radiation)
   - Documentation: `COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md`, `LONGITUDINAL_CANCER_TREATMENT_FRAMEWORK.md`
   - Athena Tables: `procedure`, `procedure_code_coding`, `medication_request`, multiple child tables
   - Expected Coverage: 70-80% (extent of resection requires narrative)
   - Action: Create unified treatment extractor

7. 📋 **molecular_characterization.csv**
   - Documentation: Referenced in frameworks
   - Athena Tables: `observation`, `molecular_tests`, `molecular_test_results`
   - Expected Coverage: 60-70% (interpretations often narrative)
   - Action: Structure + narrative hybrid

8. 📋 **conditions_predispositions.csv**
   - Documentation: `CONDITIONS_PREDISPOSITIONS_COMPREHENSIVE_MAPPING.md`
   - Athena Tables: `condition`, `condition_code_coding`, `problem_list_diagnoses`
   - Expected Coverage: 90%+
   - Action: Implement predisposition logic

#### **Tier 4: TO BE DESIGNED**
9-18. Remaining CSVs requiring discovery and framework design

---

## Phase 3: Gap Analysis & BRIM Requirements

### For Each CSV, Document:

**Athena-Extractable Variables**:
```yaml
variable_name: gender
athena_source: patient_access.gender
coverage: 100%
data_type: structured
confidence: HIGH
```

**Partially Athena-Extractable Variables**:
```yaml
variable_name: tumor_location
athena_source: condition.bodySite.coding
coverage: 40%
enrichment_needed: operative notes, radiology reports
confidence: MEDIUM
brim_role: Extract detailed anatomical location from narratives
```

**BRIM-Required Variables**:
```yaml
variable_name: extent_of_tumor_resection
athena_source: null
coverage: 0%
brim_source: operative note sections ("Extent of Resection:", "Gross Total Resection")
confidence: LOW (narrative only)
brim_role: Extract surgeon's assessment of resection completeness
```

---

## Implementation Scripts

### Core Validation Script Template

**File**: `scripts/validate_{csv_name}.py`

```python
#!/usr/bin/env python3
"""
Validate {CSV_NAME} extraction against gold standard

Purpose:
  1. Execute Athena query for test patient C1277724
  2. Load gold standard CSV
  3. Compare field-by-field
  4. Calculate coverage metrics
  5. Identify gaps requiring BRIM
  
Usage:
  python scripts/validate_{csv_name}.py \\
    --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \\
    --gold-standard-path /path/to/20250723_multitab__{csv_name}.csv \\
    --output-report athena_extraction_validation/reports/{csv_name}_validation.md
"""

import boto3
import pandas as pd
import json
from datetime import datetime

class {CSVName}Validator:
    def __init__(self, aws_profile, database, patient_fhir_id, birth_date):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena = self.session.client('athena', region_name='us-east-1')
        self.database = database
        self.patient_fhir_id = patient_fhir_id
        self.birth_date = birth_date
        
    def extract_from_athena(self):
        """Execute Athena query and return DataFrame"""
        query = self.build_extraction_query()
        result = self.execute_query(query)
        return self.process_results(result)
    
    def build_extraction_query(self):
        """Build SQL query for {CSV_NAME}"""
        # Based on documentation from {FRAMEWORK_DOC}
        return f"""
        -- Query implementation here
        """
    
    def compare_with_gold_standard(self, athena_df, gold_df):
        """Field-by-field comparison"""
        report = {
            'csv_name': '{csv_name}',
            'validation_date': datetime.now().isoformat(),
            'patient_id': self.patient_fhir_id,
            'metrics': {},
            'field_coverage': {},
            'gaps': []
        }
        
        for column in gold_df.columns:
            coverage = self.calculate_coverage(athena_df, gold_df, column)
            report['field_coverage'][column] = coverage
            
            if coverage['percent'] < 50:
                report['gaps'].append({
                    'field': column,
                    'coverage': coverage['percent'],
                    'recommendation': 'BRIM extraction required'
                })
        
        return report
    
    def calculate_coverage(self, athena_df, gold_df, column):
        """Calculate match percentage for a column"""
        # Implementation
        pass
    
    def generate_markdown_report(self, report):
        """Create human-readable validation report"""
        # Implementation
        pass

if __name__ == '__main__':
    validator = {CSVName}Validator(
        aws_profile='343218191717_AWSAdministratorAccess',
        database='fhir_v2_prd_db',
        patient_fhir_id='e4BwD8ZYDBccepXcJ.Ilo3w3',
        birth_date='2005-05-13'
    )
    
    athena_df = validator.extract_from_athena()
    gold_df = pd.read_csv('path/to/gold_standard.csv')
    report = validator.compare_with_gold_standard(athena_df, gold_df)
    validator.generate_markdown_report(report)
```

---

## Validation Metrics

### Per-CSV Metrics

```yaml
csv_name: demographics
total_fields: 8
athena_extractable_fields: 8
coverage_percentage: 100%
fields:
  - research_id: 100% (patient_access.patient_id)
  - birth_date: 100% (patient_access.birth_date)
  - legal_sex: 100% (patient_access.gender)
  - race: 100% (patient_access.race)
  - ethnicity: 100% (patient_access.ethnicity)
  - age_at_diagnosis: 100% (calculated from birth_date + diagnosis_date)
brim_required_fields: []
recommendation: "Athena extraction is COMPLETE. No BRIM needed."
```

### Per-Field Classification

```yaml
field_name: extent_of_tumor_resection
csv_name: treatments
athena_coverage: 0%
athena_source: null
structured_data_available: false
narrative_indicators:
  - "Operative note section: 'Extent of Resection'"
  - "Common phrases: 'Gross Total Resection', 'Subtotal Resection', 'Biopsy only'"
brim_extraction_strategy:
  document_types: ["Operative Note", "Surgical Pathology"]
  search_patterns: ["extent of resection", "gross total", "subtotal", "near total", "partial"]
  variable_type: categorical
  scope: many_per_note (one per surgery)
data_dictionary_reference: "treatments.extent_of_tumor_resection"
confidence: HIGH (requires narrative extraction)
```

---

## Output Deliverables

### 1. Inventory Files
- `gold_standard_inventory.json` - All discovered CSVs with metadata
- `csv_documentation_mapping.json` - CSV-to-documentation linkages

### 2. Validation Reports (Per CSV)
- `reports/demographics_validation.md`
- `reports/concomitant_medications_validation.md`
- `reports/imaging_clinical_related_validation.md`
- `reports/measurements_validation.md`
- ... (one per CSV)

### 3. Summary Reports
- `ATHENA_EXTRACTION_COMPLETENESS_SUMMARY.md` - Overall coverage metrics
- `BRIM_REQUIREMENTS_MASTER_LIST.md` - All variables requiring narrative extraction
- `MISSING_SCRIPTS_ACTION_PLAN.md` - CSVs needing script development

### 4. Extraction Scripts (Per CSV)
- `scripts/extract_demographics.py`
- `scripts/extract_concomitant_medications.py`
- `scripts/extract_imaging_clinical_related.py`
- ... (validated, production-ready)

---

## Success Criteria

### Phase 1 (Inventory) - COMPLETE when:
- [ ] All gold standard CSVs discovered and cataloged
- [ ] All CSV columns mapped to documentation
- [ ] Existing scripts identified and linked

### Phase 2 (Extraction & Validation) - COMPLETE when:
- [ ] All 18 CSVs have extraction scripts
- [ ] All scripts validated against test patient C1277724
- [ ] Coverage metrics calculated for every field
- [ ] Gaps documented with BRIM requirements

### Phase 3 (Gap Analysis) - COMPLETE when:
- [ ] Every variable classified: Athena-complete vs BRIM-needed
- [ ] BRIM variable instructions drafted for gaps
- [ ] Integration strategy documented (Athena → BRIM → post-processing)

---

## Next Steps

### Immediate Actions (This Week)

1. **Create Inventory Script** (`scripts/inventory_gold_standard_csvs.py`)
   - Scan `/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/`
   - Extract metadata for all CSVs
   - Output JSON catalog

2. **Validate Tier 1 (Completed CSVs)**
   - Run `validate_demographics.py`
   - Run `validate_concomitant_medications.py`
   - Confirm 100% and 85-90% coverage respectively

3. **Complete Tier 2 (In Progress CSVs)**
   - Finish `map_imaging_clinical_related_v4.py` implementation
   - Test `map_measurements.py` execution
   - Generate validation reports

4. **Design Tier 3 Scripts** (High Priority)
   - Convert `COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md` → `extract_encounters.py`
   - Start `extract_treatments.py` (complex, multi-source)

### Short Term (Next 2 Weeks)

5. **Complete All Tier 3 Extractions**
   - Implement scripts for all 8 frameworks
   - Validate against gold standards
   - Document coverage gaps

6. **Design Tier 4 CSVs**
   - Create frameworks for remaining CSVs
   - Follow established patterns

### Medium Term (Next Month)

7. **Create Master BRIM Integration Plan**
   - List all variables requiring narrative extraction
   - Design STRUCTURED_* document approach
   - Create hybrid extraction workflow

---

## Key References

### Documentation
- **Master Status**: `CSV_MAPPING_MASTER_STATUS.md`
- **Complete Summary**: `COMPLETE_DOCUMENTATION_SUMMARY.md`
- **Validation Strategy**: `BRIM_VALIDATION_STRATEGY.md` (in BRIM_Analytics)

### Database Resources
- **Primary Database**: `fhir_v2_prd_db`
- **AWS Profile**: `343218191717_AWSAdministratorAccess`
- **Test Patient**: C1277724 (FHIR: e4BwD8ZYDBccepXcJ.Ilo3w3)
- **Birth Date**: 2005-05-13

### Existing Scripts
- `scripts/map_demographics.py` ✅
- `scripts/map_diagnosis.py` ✅
- `scripts/complete_medication_crosswalk.py` ✅
- `scripts/map_imaging_clinical_related_v4.py` 🔄
- `scripts/map_measurements.py` 🔄
- `scripts/corticosteroid_reference.py` (supporting module) ✅

---

*Last Updated: October 7, 2025*  
*Next Review: Weekly until Phase 2 complete*  
*Maintainer: FHIR Crosswalk Validation Team*
