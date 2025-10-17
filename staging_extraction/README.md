# Staging File Extraction - Clean Multi-Agent Branch Copy

**Branch**: feature/multi-agent-framework
**Copied**: 2025-10-16
**Source**: `/athena_extraction_validation/scripts/config_driven_versions/`

---

## Purpose

This directory contains the **canonical, config-driven staging file generation scripts** for extracting structured data from Athena FHIR databases. These scripts are used by the multi-agent framework to:

1. Generate per-patient staging CSV files with column prefixing
2. Provide structured context for LLM-based extraction (Phase 1 & 2)
3. Enable cross-validation of narrative findings against structured data

---

## Directory Structure

```
staging_extraction/
├── config_driven/              # 12 canonical extraction scripts
│   ├── extract_patient_demographics.py
│   ├── extract_problem_list_diagnoses.py
│   ├── extract_all_molecular_tests_metadata.py
│   ├── extract_all_medications_metadata.py
│   ├── extract_all_encounters_metadata.py
│   ├── extract_all_imaging_metadata.py
│   ├── extract_all_binary_files_metadata.py
│   ├── extract_all_measurements_metadata.py
│   ├── extract_all_procedures_metadata.py
│   ├── extract_radiation_data.py
│   ├── extract_all_diagnoses_metadata.py
│   ├── filter_chemotherapy_from_medications.py
│   └── README.md
├── docs/                       # 10 documentation files
│   ├── COLUMN_NAMING_CONVENTIONS.md         ⭐ CRITICAL
│   ├── STAGING_FILES_CANONICAL_REFERENCE.md ⭐ START HERE
│   ├── README_ATHENA_VALIDATION_STRATEGY.md
│   ├── SYNTHESIS_COMPLETE_UNDERSTANDING.md
│   ├── COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md
│   ├── PROCEDURES_STAGING_FILE_ANALYSIS.md
│   ├── IMAGING_STAGING_FILE_ANALYSIS.md
│   ├── ENCOUNTERS_STAGING_FILE_ANALYSIS.md
│   ├── ENCOUNTERS_SCHEMA_DISCOVERY.md
│   └── MEDICATION_EXTRACTION_ENHANCEMENT_TEMPORAL_FIELDS.md
├── initialize_patient_config.py  # Helper to create patient_config.json
├── patient_config_template.json  # Template for patient configuration
├── README_ATHENA_EXTRACTION.md   # Original repository README
└── .gitignore                    # Excludes patient_config.json and outputs
```

---

## Quick Start

### 1. Initialize Patient Configuration

```bash
cd staging_extraction
python3 initialize_patient_config.py <PATIENT_FHIR_ID>
```

This creates `patient_config.json`:
```json
{
  "fhir_id": "e4BwD8ZYDBccepXcJ.Ilo3w3",
  "birth_date": "2005-05-13",
  "gender": "female",
  "output_dir": "/path/to/staging_files/patient_e4BwD8ZYDBccepXcJ",
  "database": "fhir_prd_db",
  "aws_profile": "343218191717_AWSAdministratorAccess",
  "s3_output": "s3://aws-athena-query-results-343218191717-us-east-1/"
}
```

### 2. Run Extractions

```bash
cd config_driven

# Core extractions (run in any order)
python3 extract_patient_demographics.py
python3 extract_problem_list_diagnoses.py
python3 extract_all_procedures_metadata.py
python3 extract_all_medications_metadata.py
python3 extract_all_imaging_metadata.py
python3 extract_all_measurements_metadata.py
python3 extract_all_encounters_metadata.py
python3 extract_all_binary_files_metadata.py
python3 extract_all_molecular_tests_metadata.py

# Specialized extractions
python3 filter_chemotherapy_from_medications.py  # Requires medications.csv
python3 extract_radiation_data.py                # Creates 10 RT files
```

**Total Time**: ~70 seconds for complete extraction

### 3. Output Files

```
staging_files/patient_<short_id>/
├── demographics.csv
├── diagnoses.csv
├── procedures.csv          ← proc_, pcc_ prefixes
├── medications.csv         ← medication_ prefixes
├── imaging.csv             ← imaging_ prefixes
├── measurements.csv
├── encounters.csv
├── binary_files.csv
├── molecular_tests_metadata.csv
└── radiation_*/
    ├── radiation_oncology_consults.csv
    ├── radiation_treatment_appointments.csv
    ├── radiation_treatment_courses.csv
    ├── radiation_care_plan_notes.csv      ← cp_, cpn_ prefixes
    ├── radiation_care_plan_hierarchy.csv  ← cp_, cppo_ prefixes
    ├── service_request_notes.csv          ← sr_, srn_ prefixes
    ├── service_request_rt_history.csv     ← sr_, srrc_ prefixes
    ├── procedure_rt_codes.csv
    ├── procedure_notes.csv
    ├── radiation_oncology_documents.csv
    └── radiation_data_summary.csv
```

---

## Key Features

### ✅ Config-Driven (No Hardcoded IDs)
All scripts read from centralized `patient_config.json` - easy to process multiple patients.

### ✅ Column Prefixing for Data Provenance
SQL aliases ensure every column identifies its source table:

```sql
SELECT
    p.id as procedure_fhir_id,
    p.status as proc_status,                    -- proc_ prefix
    p.performed_date_time as proc_performed_date_time,
    p.code_text as proc_code_text,
    pcc.code_coding_system as pcc_code_coding_system  -- pcc_ prefix
FROM procedure p
LEFT JOIN procedure_code_coding pcc ON p.id = pcc.procedure_id
WHERE p.subject_reference = '{patient_fhir_id}'
```

**Prefix Reference**:
- `proc_` = procedure table
- `pcc_` = procedure_code_coding table
- `imaging_` = radiology_imaging_mri table
- `medication_` = medication_request table
- `cp_` = care_plan table
- `cpn_` = care_plan_note table
- `sr_` = service_request table
- `srn_` = service_request_note table

See [COLUMN_NAMING_CONVENTIONS.md](docs/COLUMN_NAMING_CONVENTIONS.md) for complete reference.

### ✅ Standardized Output Structure
Generic filenames (e.g., `medications.csv` not `medications_C1277724.csv`) with patient-specific directories.

### ✅ Privacy-First Design
- MRN excluded from CSV outputs
- Age calculations instead of absolute dates
- Encounter references for context without identifiers

---

## Documentation Guide

| Document | Purpose | When to Read |
|----------|---------|--------------|
| [STAGING_FILES_CANONICAL_REFERENCE.md](docs/STAGING_FILES_CANONICAL_REFERENCE.md) | **START HERE** - Complete roadmap of canonical scripts | Always |
| [COLUMN_NAMING_CONVENTIONS.md](docs/COLUMN_NAMING_CONVENTIONS.md) | **CRITICAL** - Column prefixing strategy | Before writing analysis code |
| [README_ATHENA_VALIDATION_STRATEGY.md](docs/README_ATHENA_VALIDATION_STRATEGY.md) | Overall extraction validation strategy | Understanding validation approach |
| [SYNTHESIS_COMPLETE_UNDERSTANDING.md](docs/SYNTHESIS_COMPLETE_UNDERSTANDING.md) | Complete strategic picture | Understanding hybrid pipeline |
| Resource-specific docs | Detailed analysis for procedures, imaging, encounters, medications, radiation | When working with specific resources |

---

## Integration with Multi-Agent Framework

### Phase 1: Structured Data Harvesting
```python
from staging_extraction.form_extractors.staging_views_config import StagingViewsConfiguration

# Load staging files
procedures_df = pd.read_csv(f"{config['output_dir']}/procedures.csv")
imaging_df = pd.read_csv(f"{config['output_dir']}/imaging.csv")

# Column prefixes enable clear data provenance
surgery_date = procedures_df[procedures_df['is_surgical_keyword'] == True]['proc_performed_date_time'].iloc[0]
```

### Phase 2: Timeline Building
```python
# Merge DataFrames with no column conflicts due to prefixes
timeline = procedures_df[['proc_performed_date_time', 'proc_code_text']].merge(
    imaging_df[['imaging_date', 'imaging_modality']],
    left_on='proc_performed_date_time',
    right_on='imaging_date',
    how='outer'
)
```

### Phase 4: LLM Validation
```python
# Provide structured context to LLM
structured_context = {
    'surgeries': procedures_df[procedures_df['is_surgical_keyword'] == True].to_dict('records'),
    'post_op_imaging': imaging_df[imaging_df['is_postop_72hr'] == True].to_dict('records')
}

llm_prompt = f"""
Validate extent of resection extraction:
- Surgery date: {surgery_date}
- Post-op imaging: {structured_context['post_op_imaging']}
- Extracted value: {narrative_extraction['extent_of_resection']}

Does the narrative extraction match structured data?
"""
```

---

## Verification Checklist

Before using a script in production:

- [ ] Script loads from `patient_config.json` (not hardcoded)
- [ ] Script uses SQL column aliases with prefixes (`proc_`, `imaging_`, etc.)
- [ ] Script outputs to `config['output_dir']` (not hardcoded path)
- [ ] Script is in `/config_driven/` directory
- [ ] Script modification date is October 2025 (latest refactoring)
- [ ] Documentation matches script behavior

---

## Migration History

**2025-10-16**: Clean copy to multi-agent branch
- Source: `/athena_extraction_validation/scripts/config_driven_versions/`
- Status: ✅ Production-ready
- Scripts: 12 core extraction scripts
- Documentation: 10 comprehensive markdown files
- Key feature: Column prefixing for data provenance

**Excluded from Migration**:
- Deprecated scripts (`*_original.py`)
- Exploratory scripts (`explore_*.py`)
- Old patient-specific scripts with hardcoded IDs
- Archive directory contents

---

## Related Files in Parent Directory

- `../STAGING_VIEWS_REFERENCE.md` - Documents the Python configuration class for multi-agent framework
- `../form_extractors/staging_views_config.py` - Schema definitions for framework integration
- `../STAGING_FILES_CANONICAL_REFERENCE.md` - Master copy of this canonical reference

---

## AWS Configuration

Scripts use AWS Athena for querying FHIR database. Ensure credentials are configured:

```bash
aws configure --profile 343218191717_AWSAdministratorAccess
```

**Required IAM Permissions**:
- `athena:StartQueryExecution`
- `athena:GetQueryExecution`
- `athena:GetQueryResults`
- `s3:GetObject`, `s3:PutObject` (for query results bucket)
- `glue:GetTable`, `glue:GetDatabase` (for FHIR database access)

---

## Troubleshooting

### Issue: "patient_config.json not found"
**Solution**: Run `python3 initialize_patient_config.py <PATIENT_FHIR_ID>` first

### Issue: "Access Denied" on Athena query
**Solution**: Verify AWS profile and IAM permissions

### Issue: Output directory doesn't exist
**Solution**: Scripts auto-create output directory based on `patient_config.json`

### Issue: Column not found in DataFrame
**Solution**: Check column prefix - use `proc_status` not `status`, `imaging_date` not `date`

---

## Contact

For questions or issues with staging file extraction, refer to:
- [STAGING_FILES_CANONICAL_REFERENCE.md](docs/STAGING_FILES_CANONICAL_REFERENCE.md)
- Original repository: `/athena_extraction_validation/`
- Multi-agent branch: `feature/multi-agent-framework`
