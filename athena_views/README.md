# Athena Views

**Purpose**: Centralized management of all 15 Athena SQL views for FHIR data extraction

**Last Updated**: 2025-10-17

---

## Overview

This directory contains all SQL view definitions, documentation, and verification scripts for the Athena-based FHIR data extraction system. These views replicate the output of the Python extraction scripts but run entirely in AWS Athena for scalable, all-patient queries.

### What's Here

- **views/**: SQL CREATE VIEW statements
- **documentation/**: Detailed guides and analysis
- **verification/**: Testing and validation scripts

---

## Quick Start

### 1. Create All Views

Copy and paste each CREATE VIEW statement from [views/ATHENA_VIEW_CREATION_QUERIES.sql](views/ATHENA_VIEW_CREATION_QUERIES.sql) into the AWS Athena Console.

```sql
-- Run each CREATE OR REPLACE VIEW statement one at a time
-- Example:
CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics AS
SELECT ...
```

### 2. Verify Views Work

```sql
-- Test that all views exist
SHOW VIEWS IN fhir_prd_db;

-- Test a simple query
SELECT * FROM fhir_prd_db.v_patient_demographics LIMIT 10;
```

### 3. Check Documentation

See [verification/ATHENA_VIEWS_VERIFICATION.md](verification/ATHENA_VIEWS_VERIFICATION.md) for complete validation results.

---

## The 15 Views

All views are defined in `views/ATHENA_VIEW_CREATION_QUERIES.sql`:

### Core Clinical Data (9 views)
1. **v_patient_demographics** - Basic patient info (age, gender, race, ethnicity)
2. **v_problem_list_diagnoses** - All diagnoses with ICD-10/SNOMED codes
3. **v_procedures** - Surgical procedures with CPT codes
4. **v_medications** - Medication requests linked to care plans
5. **v_imaging** - MRI and other imaging with diagnostic reports
6. **v_encounters** - All patient encounters (inpatient, outpatient)
7. **v_measurements** - Lab results and vital signs (UNION of observation + lab_tests)
8. **v_binary_files** - Document references (22K+ docs per patient)
9. **v_molecular_tests** - Genetic/molecular test results

### Radiation Oncology (6 views)
10. **v_radiation_treatment_appointments** - RT appointments
11. **v_radiation_treatment_courses** - RT treatment courses
12. **v_radiation_care_plan_notes** - RT care plan narratives
13. **v_radiation_care_plan_hierarchy** - Care plan linkages
14. **v_radiation_service_request_notes** - RT order notes
15. **v_radiation_service_request_rt_history** - RT treatment history

---

## Recent Updates

### October 17, 2025

**Patient Identifier Standardization**
- All views now use `patient_fhir_id` as standard column name
- 3 views updated: v_procedures, v_imaging, v_measurements
- See [documentation/PATIENT_IDENTIFIER_ANALYSIS.md](documentation/PATIENT_IDENTIFIER_ANALYSIS.md)

**Re-run Required**:
```sql
-- Source: views/RERUN_STANDARDIZED_VIEWS.sql
CREATE OR REPLACE VIEW fhir_prd_db.v_procedures AS ...
CREATE OR REPLACE VIEW fhir_prd_db.v_imaging AS ...
CREATE OR REPLACE VIEW fhir_prd_db.v_measurements AS ...
```

### October 16, 2025

**All 15 Views Fixed and Validated** ✅
- Fixed 60+ column name mismatches
- Completely rewrote v_molecular_tests (wrong tables)
- Added patient identifier to v_radiation_treatment_appointments
- Fixed SQL reserved keyword issue ('end' → "end")
- See [documentation/ATHENA_VIEW_FIXES.md](documentation/ATHENA_VIEW_FIXES.md)

---

## Date/Time Standardization (In Progress)

FHIR data contains mixed date formats:
- ISO 8601 with timezone: `2025-01-24T09:02:00Z`
- Date-only: `2012-10-19`

**Analysis Complete**: [documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md](documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md)

**Proposed Solution**: Hybrid approach with both `*_date` and `*_datetime` columns

**Example Implementation**: [documentation/DATE_STANDARDIZATION_EXAMPLE.sql](documentation/DATE_STANDARDIZATION_EXAMPLE.sql)

**Status**: Pending review before implementation

---

## Documentation

### View Definitions
- [views/ATHENA_VIEW_CREATION_QUERIES.sql](views/ATHENA_VIEW_CREATION_QUERIES.sql) - All 15 CREATE VIEW statements
- [views/RERUN_STANDARDIZED_VIEWS.sql](views/RERUN_STANDARDIZED_VIEWS.sql) - Patient ID standardization updates

### Implementation Guides
- [documentation/ATHENA_VIEW_FIXES.md](documentation/ATHENA_VIEW_FIXES.md) - Complete fix history (60+ fixes)
- [documentation/PATIENT_IDENTIFIER_ANALYSIS.md](documentation/PATIENT_IDENTIFIER_ANALYSIS.md) - Patient ID standardization
- [documentation/STANDARDIZATION_SUMMARY.md](documentation/STANDARDIZATION_SUMMARY.md) - What changed and why

### Date/Time Standardization
- [documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md](documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md) - Comprehensive analysis
- [documentation/DATE_STANDARDIZATION_EXAMPLE.sql](documentation/DATE_STANDARDIZATION_EXAMPLE.sql) - Working example

### Verification
- [verification/ATHENA_VIEWS_VERIFICATION.md](verification/ATHENA_VIEWS_VERIFICATION.md) - Test results

---

## Usage Examples

### Query Single Patient
```sql
-- Get all data for one patient
SELECT * FROM fhir_prd_db.v_patient_demographics
WHERE patient_fhir_id = 'Patient/xyz';

SELECT * FROM fhir_prd_db.v_problem_list_diagnoses
WHERE patient_fhir_id = 'Patient/xyz';

SELECT * FROM fhir_prd_db.v_procedures
WHERE patient_fhir_id = 'Patient/xyz';  -- Note: now standardized!
```

### Query All Patients
```sql
-- Get brain tumor patients across entire database
SELECT
    pd.patient_fhir_id,
    pd.pd_age_years,
    pld.pld_diagnosis_name,
    pld.pld_icd10_code
FROM fhir_prd_db.v_patient_demographics pd
JOIN fhir_prd_db.v_problem_list_diagnoses pld
    ON pd.patient_fhir_id = pld.patient_fhir_id
WHERE LOWER(pld.pld_diagnosis_name) LIKE '%brain%'
   OR LOWER(pld.pld_diagnosis_name) LIKE '%glioma%'
   OR pld.pld_icd10_code LIKE 'C71%';
```

### Export to CSV
```sql
-- Use Athena console "Download results" button
-- Or use AWS CLI:
aws athena start-query-execution \
    --query-string "SELECT * FROM fhir_prd_db.v_patient_demographics" \
    --result-configuration OutputLocation=s3://your-bucket/results/
```

---

## Relationship to Staging Extraction

These Athena views **replicate** the output of the Python extraction scripts in `../staging_extraction/config_driven/`:

| Python Script | Athena View | Output File |
|---|---|---|
| extract_patient_demographics.py | v_patient_demographics | patient_demographics.csv |
| extract_problem_list_diagnoses.py | v_problem_list_diagnoses | problem_list_diagnoses.csv |
| extract_all_procedures_metadata.py | v_procedures | procedures.csv |
| extract_all_medications_metadata.py | v_medications | medications.csv |
| extract_all_imaging_metadata.py | v_imaging | imaging.csv |
| extract_all_encounters_metadata.py | v_encounters | encounters.csv |
| extract_all_measurements_metadata.py | v_measurements | measurements.csv |
| extract_all_binary_files_metadata.py | v_binary_files | binary_files.csv |
| extract_all_molecular_tests_metadata.py | v_molecular_tests | molecular_tests_metadata.csv |
| extract_radiation_data.py | v_radiation_* (6 views) | 6 radiation CSV files |

**Key Difference**:
- **Python scripts**: Extract data for ONE patient at a time
- **Athena views**: Query data for ALL patients at once

---

## Database Schema

**Database**: `fhir_prd_db`
**AWS Account**: 343218191717
**Region**: us-east-1
**Output Location**: s3://aws-athena-query-results-343218191717-us-east-1/

### Source Tables Used

The views query these underlying FHIR tables:
- patient_access
- problem_list_diagnoses
- procedure (+ 10 child tables)
- medication_request (+ 9 child tables)
- observation, lab_tests, lab_test_results
- encounter (+ 3 child tables)
- diagnostic_report (+ 2 child tables)
- document_reference (+ 2 child tables)
- molecular_tests, molecular_test_results
- appointment, appointment_participant
- service_request (+ 3 child tables)
- care_plan (+ 3 child tables)
- specimen

---

## Known Issues

### 1. v_measurements Performance
The UNION ALL of observation + lab_tests can be slow for large queries. Consider:
- Adding WHERE filters on patient_fhir_id
- Using LIMIT for testing
- Querying observation and lab_tests separately for specific use cases

### 2. Date Format Inconsistency
Date columns have mixed formats (ISO 8601 vs date-only). See Date/Time Standardization section above.

### 3. v_binary_files Volume
Can return 20,000+ rows per patient. Use filters:
```sql
WHERE dr_type_text = 'Radiology Report'  -- Limit to specific document types
```

---

## Support

**Issues**: Report in GitHub at https://github.com/anthropics/claude-code/issues
**Questions**: Check [../staging_extraction/README.md](../staging_extraction/README.md) for extraction pipeline docs

---

## Change Log

### 2025-10-17
- ✅ Standardized patient_fhir_id across all views
- ✅ Analyzed date/time format inconsistencies
- ✅ Created comprehensive documentation
- ✅ Reorganized into athena_views/ directory

### 2025-10-16
- ✅ Fixed all 15 views (60+ column mismatches)
- ✅ Added patient identifier to v_radiation_treatment_appointments
- ✅ Verified all views query successfully
