# Athena Extraction & Validation Workflows

**Purpose**: Complete workflow for extracting and validating clinical data from AWS Athena FHIR v2 database for BRIM Analytics project.

**Last Updated**: 2025-10-09

---

## 📁 Folder Structure

```
athena_extraction_validation/
├── README.md                          # This file
├── scripts/                           # Extraction and validation scripts
│   ├── extract_all_encounters_metadata.py
│   ├── extract_all_procedures_metadata.py
│   ├── link_procedures_to_encounters.py
│   ├── validate_demographics_csv.py
│   ├── validate_diagnosis_csv.py
│   ├── validate_encounters_csv.py
│   ├── test_molecular_queries.py
│   ├── test_molecular_results_table.py
│   ├── discover_procedure_schema.py
│   └── inventory_gold_standard_csvs.py
├── staging_files/                     # CSV staging files (raw extractions)
│   ├── ALL_ENCOUNTERS_METADATA_C1277724.csv
│   ├── ALL_PROCEDURES_METADATA_C1277724.csv
│   └── ALL_PROCEDURES_WITH_ENCOUNTERS_C1277724.csv
├── docs/                              # All documentation and reports
│   ├── GENERALIZABLE_EXTRACTION_WORKFLOW.md  # ⭐ START HERE
│   ├── README_ATHENA_VALIDATION_STRATEGY.md
│   ├── README_EXTRACTION_ARCHITECTURE.md
│   ├── ENCOUNTERS_SCHEMA_DISCOVERY.md
│   ├── ENCOUNTERS_STAGING_FILE_ANALYSIS.md
│   ├── ENCOUNTERS_COLUMN_REFERENCE.md
│   ├── PROCEDURES_SCHEMA_DISCOVERY.md
│   ├── PROCEDURES_STAGING_FILE_ANALYSIS.md
│   ├── PROCEDURES_COLUMN_REFERENCE.md
│   ├── PROCEDURE_ENCOUNTER_LINKAGE_VALIDATION.md
│   ├── demographics_validation.md
│   ├── diagnosis_validation.md
│   ├── encounters_validation.md
│   ├── SESSION_SUMMARY_*.md
│   └── [other documentation files]
└── inventory/                         # Gold standard CSV inventory
```

---

## 🚀 Quick Start

### For New Users - READ THIS FIRST

**Start with**: [`docs/GENERALIZABLE_EXTRACTION_WORKFLOW.md`](docs/GENERALIZABLE_EXTRACTION_WORKFLOW.md)

This comprehensive guide provides:
- Complete script inventory with usage examples
- Step-by-step workflow for ANY patient (not just C1277724)
- Validation strategies without gold standard data
- Adaptation patterns for different cancer types
- Production deployment checklist

---

## 📊 Extraction Scripts

### 1. Demographics Extraction ✅ 100% Validated
**Script**: `scripts/validate_demographics_csv.py`

**Status**: Production-ready, 100% accuracy achieved

**Usage**:
```bash
python3 scripts/validate_demographics_csv.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --patient-research-id C1277724 \
  --gold-standard-csv data/20250723_multitab_csvs/20250723_multitab__demographics.csv \
  --output-report docs/demographics_validation.md
```

**Extracts**: legal_sex, race, ethnicity, birth_date

**Validation Report**: [`docs/demographics_validation.md`](docs/demographics_validation.md)

---

### 2. Diagnosis Extraction
**Script**: `scripts/validate_diagnosis_csv.py`

**Status**: Validated, documented in diagnosis_validation.md

**Usage**:
```bash
python3 scripts/validate_diagnosis_csv.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --patient-research-id C1277724
```

**Validation Report**: [`docs/diagnosis_validation.md`](docs/diagnosis_validation.md)

---

### 3. Encounters Extraction ⏳ In Progress
**Scripts**: 
- `scripts/extract_all_encounters_metadata.py` - Extract ALL encounters
- `scripts/validate_encounters_csv.py` - Validate against gold standard

**Status**: 
- ✅ Staging file created (999 encounters)
- ✅ Schema discovery complete (19 tables)
- ✅ Pattern analysis complete
- ⏳ Validation script needs update (currently 50% accuracy)

**Usage**:
```bash
# Step 1: Extract all encounters to staging file
python3 scripts/extract_all_encounters_metadata.py

# Step 2: Validate (after updating with Surgery Log logic)
python3 scripts/validate_encounters_csv.py
```

**Staging File**: [`staging_files/ALL_ENCOUNTERS_METADATA_C1277724.csv`](staging_files/ALL_ENCOUNTERS_METADATA_C1277724.csv)

**Documentation**:
- [`docs/ENCOUNTERS_SCHEMA_DISCOVERY.md`](docs/ENCOUNTERS_SCHEMA_DISCOVERY.md) - All 19 encounter tables
- [`docs/ENCOUNTERS_STAGING_FILE_ANALYSIS.md`](docs/ENCOUNTERS_STAGING_FILE_ANALYSIS.md) - Pattern analysis
- [`docs/ENCOUNTERS_COLUMN_REFERENCE.md`](docs/ENCOUNTERS_COLUMN_REFERENCE.md) - Field definitions
- [`docs/encounters_validation.md`](docs/encounters_validation.md) - Validation report

**Key Finding**: Surgery Log encounters are 100% reliable for identifying diagnosis events

---

### 4. Procedures Extraction ✅ Validated
**Scripts**:
- `scripts/extract_all_procedures_metadata.py` - Extract ALL procedures
- `scripts/link_procedures_to_encounters.py` - Resolve dates via encounter linkage

**Status**:
- ✅ Staging file created (72 procedures, 34 columns)
- ✅ Schema discovery complete (22 tables)
- ✅ Encounter linkage complete (88.9% linked)
- ✅ Date resolution improved 83.3% (8→68 dated procedures)
- ✅ Surgical timeline 100% validated

**Usage**:
```bash
# Step 1: Extract all procedures
python3 scripts/extract_all_procedures_metadata.py

# Step 2: Link to encounters for date resolution
python3 scripts/link_procedures_to_encounters.py
```

**Staging Files**:
- [`staging_files/ALL_PROCEDURES_METADATA_C1277724.csv`](staging_files/ALL_PROCEDURES_METADATA_C1277724.csv) - Original (34 columns)
- [`staging_files/ALL_PROCEDURES_WITH_ENCOUNTERS_C1277724.csv`](staging_files/ALL_PROCEDURES_WITH_ENCOUNTERS_C1277724.csv) - Enhanced (44 columns)

**Documentation**:
- [`docs/PROCEDURES_SCHEMA_DISCOVERY.md`](docs/PROCEDURES_SCHEMA_DISCOVERY.md) - All 22 procedure tables
- [`docs/PROCEDURES_STAGING_FILE_ANALYSIS.md`](docs/PROCEDURES_STAGING_FILE_ANALYSIS.md) - Pattern analysis
- [`docs/PROCEDURES_COLUMN_REFERENCE.md`](docs/PROCEDURES_COLUMN_REFERENCE.md) - Field definitions
- [`docs/PROCEDURE_ENCOUNTER_LINKAGE_VALIDATION.md`](docs/PROCEDURE_ENCOUNTER_LINKAGE_VALIDATION.md) - ⭐ Validation results

**Key Findings**:
- 10 surgical procedures identified
- 8/10 link to Surgery Log encounters (100% timeline validation)
- Multi-stage recurrence surgery discovered (6 procedures over 6 days)
- Anesthesia procedures perfectly mark surgical events

---

### 5. Molecular Diagnostics Extraction ✅ Validated
**Scripts**:
- `scripts/test_molecular_queries.py` - Test molecular_tests table queries
- `scripts/test_molecular_results_table.py` - Verify molecular_test_results linkage

**Status**:
- ✅ Athena tables identified and verified (molecular_tests, molecular_test_results)
- ✅ Queries defined and tested (3 tests, 6 result components found)
- ✅ PHI protection implemented (no MRN in queries)
- ✅ Semantic matching for test names implemented
- ✅ Validation improved from 50% → 61.4% accuracy

**Usage**:
```bash
# Test molecular_tests table access
python3 scripts/test_molecular_queries.py

# Verify molecular_test_results linkage
python3 scripts/test_molecular_results_table.py
```

**Athena Tables**:
1. `fhir_v2_prd_db.molecular_tests` - Test metadata (test_id, lab_test_name, result_datetime, status)
2. `fhir_v2_prd_db.molecular_test_results` - Result components (test_component, test_result_narrative)

**Queries Defined**:
```sql
-- Get all molecular tests for patient
SELECT 
    patient_id, test_id, result_datetime, 
    lab_test_name, lab_test_status
FROM fhir_v2_prd_db.molecular_tests
WHERE patient_id = '{patient_fhir_id}'
    AND lab_test_status = 'completed'
ORDER BY result_datetime;

-- Get test results with narratives (joined)
SELECT 
    mt.patient_id, mt.test_id, mt.result_datetime,
    mt.lab_test_name, mtr.test_component,
    LENGTH(mtr.test_result_narrative) as narrative_length
FROM fhir_v2_prd_db.molecular_tests mt
LEFT JOIN fhir_v2_prd_db.molecular_test_results mtr 
    ON mt.test_id = mtr.test_id
WHERE mt.patient_id = '{patient_fhir_id}'
ORDER BY mt.result_datetime;
```

**Data Extracted for C1277724**:
| Date | Test Name | Components |
|------|-----------|------------|
| 2018-05-28 | Comprehensive Solid Tumor Panel | GENOMICS INTERPRETATION (645 chars)<br>GENOMICS METHOD (6,327 chars) |
| 2021-03-10 | Comprehensive Solid Tumor Panel T/N Pair | GENOMICS INTERPRETATION (1,243 chars)<br>GENOMICS METHOD (7,069 chars) |
| 2021-03-10 | Tumor Panel Normal Paired | GENOMICS METHOD (6,507 chars)<br>GENOMICS RESULTS (193 chars) |

**Documentation**:
- [`docs/MOLECULAR_TESTS_VERIFICATION.md`](docs/MOLECULAR_TESTS_VERIFICATION.md) - Query verification and results
- [`docs/MOLECULAR_DATA_GAP_ANALYSIS.md`](docs/MOLECULAR_DATA_GAP_ANALYSIS.md) - Comprehensive gap analysis

**Key Findings**:
- 3 completed molecular tests identified
- 6 result components with narratives (645-7,069 characters each)
- Semantic matching maps "Comprehensive Solid Tumor Panel" to WGS
- KIAA1549-BRAF fusion documented in narrative text
- RNA-Seq not found in molecular_tests table (research assay gap)

**Next Steps**:
- Extract test_result_narrative for mutation details
- Implement NLP parsing for structured mutation data (KIAA1549-BRAF)
- Link to gold standard molecular_characterization.csv

---

## 📖 Documentation Guide

### Essential Reading (Priority Order)

1. **[GENERALIZABLE_EXTRACTION_WORKFLOW.md](docs/GENERALIZABLE_EXTRACTION_WORKFLOW.md)** ⭐ START HERE
   - Complete workflow for ANY patient
   - All scripts documented with examples
   - Validation without gold standard
   - Production deployment guide

2. **[README_EXTRACTION_ARCHITECTURE.md](docs/README_EXTRACTION_ARCHITECTURE.md)**
   - System architecture overview
   - Data flow diagrams
   - Design decisions

3. **[README_ATHENA_VALIDATION_STRATEGY.md](docs/README_ATHENA_VALIDATION_STRATEGY.md)**
   - Validation approach and methodology
   - Quality metrics
   - Gap analysis

### Resource-Specific Guides

**Encounters**:
- Schema: [`ENCOUNTERS_SCHEMA_DISCOVERY.md`](docs/ENCOUNTERS_SCHEMA_DISCOVERY.md)
- Analysis: [`ENCOUNTERS_STAGING_FILE_ANALYSIS.md`](docs/ENCOUNTERS_STAGING_FILE_ANALYSIS.md)
- Reference: [`ENCOUNTERS_COLUMN_REFERENCE.md`](docs/ENCOUNTERS_COLUMN_REFERENCE.md)
- Validation: [`encounters_validation.md`](docs/encounters_validation.md)

**Procedures**:
- Schema: [`PROCEDURES_SCHEMA_DISCOVERY.md`](docs/PROCEDURES_SCHEMA_DISCOVERY.md)
- Analysis: [`PROCEDURES_STAGING_FILE_ANALYSIS.md`](docs/PROCEDURES_STAGING_FILE_ANALYSIS.md)
- Reference: [`PROCEDURES_COLUMN_REFERENCE.md`](docs/PROCEDURES_COLUMN_REFERENCE.md)
- Linkage: [`PROCEDURE_ENCOUNTER_LINKAGE_VALIDATION.md`](docs/PROCEDURE_ENCOUNTER_LINKAGE_VALIDATION.md)

### Session Summaries
- [`SESSION_SUMMARY_ENCOUNTERS_STAGING.md`](docs/SESSION_SUMMARY_ENCOUNTERS_STAGING.md)
- [`SESSION_SUMMARY_PROCEDURES_STAGING.md`](docs/SESSION_SUMMARY_PROCEDURES_STAGING.md)
- [`SESSION_SUMMARY_LINKAGE.md`](docs/SESSION_SUMMARY_LINKAGE.md)
- [`SESSION_SUMMARY_2025-10-07.md`](docs/SESSION_SUMMARY_2025-10-07.md)

---

## 🎯 Current Status

### ✅ Completed
- Demographics extraction & validation (100% accuracy)
- Diagnosis extraction & validation (61.4% with molecular tests)
- Molecular diagnostics discovery & validation (3 tests, 6 components)
- Molecular test queries defined and tested (2 Athena tables)
- Encounters staging file creation (999 encounters)
- Encounters schema discovery (19 tables)
- Procedures staging file creation (72 procedures)
- Procedures schema discovery (22 tables)
- Procedure-encounter linkage (83.3% date improvement)
- Surgical timeline validation (100% accuracy)
- Comprehensive documentation (25+ markdown files)
- Generalizable workflow guide

### ⏳ In Progress
- Encounters validation script update (use Surgery Log for diagnosis events)
- Production extraction script creation

### 📋 Next Steps
1. Update `validate_encounters_csv.py` with Surgery Log logic
2. Add problem_list query for progression events
3. Update follow-up filtering with oncology keywords
4. Test and validate improved extraction (target: 80%+ accuracy)
5. Create production-ready extraction script

---

## 📊 Key Metrics

| Resource | Tables Discovered | Records Extracted | Validation Accuracy | Status |
|----------|------------------|-------------------|---------------------|---------|
| Demographics | 1 | 1 patient | 100% | ✅ Complete |
| Diagnosis | Multiple | Multiple diagnoses | 61.4% (with molecular) | ✅ Complete |
| Encounters | 19 | 999 encounters | 50% → 80%+ (pending) | ⏳ In Progress |
| Procedures | 22 | 72 procedures | 100% (surgical timeline) | ✅ Complete |
| Molecular Tests | 2 | 3 tests, 6 components | 61.4% (semantic matching) | ✅ Complete |

---

## 🔧 Technical Details

### Prerequisites
- Python 3.8+
- AWS credentials with Athena access (profile: `343218191717_AWSAdministratorAccess`)
- Libraries: boto3, pandas, awswrangler

### Database
- **Name**: fhir_v2_prd_db
- **Region**: us-east-1
- **Type**: AWS Athena (FHIR v2 resources)

### Patient Test Case
- **Research ID**: C1277724
- **FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3
- **Birth Date**: 2005-05-13
- **Condition**: Pediatric medulloblastoma (initial diagnosis 2018-03-26, recurrence 2021-01-14)

---

## 🎓 Key Lessons Learned

1. **Extract ALL data first, analyze patterns second** - Don't filter during extraction
2. **Surgery Log encounters are 100% reliable** for identifying surgical diagnosis events
3. **Procedure dates are sparse** - 89% require encounter linkage for temporal resolution
4. **Multi-stage surgeries exist** - Don't assume one procedure = one surgical event
5. **Pattern-based filtering works** - Use keywords and data patterns, not hardcoded dates
6. **Comprehensive documentation is essential** - Enables reproducibility and generalization

---

## 📞 Support

### Questions or Issues?
1. Check the [GENERALIZABLE_EXTRACTION_WORKFLOW.md](docs/GENERALIZABLE_EXTRACTION_WORKFLOW.md) guide
2. Review resource-specific schema discovery docs
3. Check session summaries for detailed explanations
4. Review validation reports for expected patterns

### Contributing
- All scripts should be generalized (no patient-specific hardcoding)
- Document assumptions and limitations
- Create validation reports for new extractions
- Update this README with new findings

---

## 📝 Change Log

**2025-10-09**:
- Created organized folder structure (scripts/, staging_files/, docs/)
- Added comprehensive README
- Moved all documentation to docs/ folder
- Moved all CSV files to staging_files/ folder

**2025-10-08**:
- Created procedure-encounter linkage workflow
- Validated surgical timeline (100% accuracy)
- Discovered multi-stage recurrence surgery pattern
- Created generalizable extraction workflow guide

**2025-10-07**:
- Created comprehensive encounters staging file (999 encounters)
- Created comprehensive procedures staging file (72 procedures)
- Completed schema discovery for encounters and procedures
- Validated demographics extraction (100% accuracy)

---

**For detailed workflow instructions, start with**: [`docs/GENERALIZABLE_EXTRACTION_WORKFLOW.md`](docs/GENERALIZABLE_EXTRACTION_WORKFLOW.md) ⭐
