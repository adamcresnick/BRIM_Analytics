# Canonical Staging Files Workflow - Source of Truth

**Created**: 2025-10-16
**Branch**: feature/multi-agent-framework
**Purpose**: Definitive reference for config-driven staging file generation

---

## Executive Summary

This document identifies the **canonical (latest) scripts and documentation** for generating staging files from Athena FHIR databases. Use this as the authoritative reference when copying code to the multi-agent framework branch.

---

## 📁 Canonical Source Location

**Primary Directory**: `/athena_extraction_validation/scripts/config_driven_versions/`

**Status**: ✅ **PRODUCTION-READY** (as of October 13, 2025)

**Key Feature**: All scripts use centralized `patient_config.json` - no hardcoded patient IDs

---

## 🎯 Latest Canonical Scripts (15 files)

### Core Extraction Scripts (9 scripts)

| Script | Modified Date | Status | Output File | Description |
|--------|---------------|--------|-------------|-------------|
| **extract_patient_demographics.py** | Oct 13, 2025 | ✅ LATEST | demographics.csv | Patient demographics from patient table |
| **extract_problem_list_diagnoses.py** | Oct 13, 2025 | ✅ LATEST | diagnoses.csv | Problem list with ICD-10/SNOMED codes |
| **extract_all_molecular_tests_metadata.py** | Oct 13, 2025 | ✅ LATEST | molecular_tests_metadata.csv | Molecular test results |
| **extract_all_medications_metadata.py** | Oct 12, 2025 | ✅ LATEST | medications.csv | Medications with `medication_` prefix |
| **extract_all_encounters_metadata.py** | Oct 12, 2025 | ✅ LATEST | encounters.csv | Encounters/appointments |
| **extract_all_imaging_metadata.py** | Oct 12, 2025 | ✅ LATEST | imaging.csv | Imaging with `imaging_` prefix |
| **extract_all_binary_files_metadata.py** | Oct 12, 2025 | ✅ LATEST | binary_files.csv | Document references |
| **extract_all_measurements_metadata.py** | Oct 12, 2025 | ✅ LATEST | measurements.csv | Observations and labs |
| **extract_all_procedures_metadata.py** | Oct 12, 2025 | ✅ LATEST | procedures.csv | Procedures with `proc_` prefix |

### Radiation Therapy Extraction (1 script)

| Script | Modified Date | Status | Output Files | Description |
|--------|---------------|--------|-------------|-------------|
| **extract_radiation_data.py** | Oct 12, 2025 | ✅ LATEST | 10 CSV files | Comprehensive RT extraction with `cp_`, `sr_`, `proc_` prefixes |

### Supporting Scripts (5 scripts)

| Script | Modified Date | Status | Purpose |
|--------|---------------|--------|---------|
| **filter_chemotherapy_from_medications.py** | Oct 11, 2025 | ✅ LATEST | Filters chemotherapy from medications.csv |
| **explore_radiation_treatments.py** | Oct 12, 2025 | ⚠️ EXPLORATORY | Analysis tool for RT data |
| **explore_radiation_data.py** | Oct 11, 2025 | ⚠️ EXPLORATORY | Analysis tool for RT data |
| **extract_all_imaging_metadata_original.py** | Oct 11, 2025 | 🗑️ DEPRECATED | Backup before refactoring |
| **extract_all_diagnoses_metadata.py** | Oct 11, 2025 | ✅ LATEST | Alternative diagnoses extractor |

---

## 📋 Configuration File (REQUIRED)

### File: `patient_config.json`

**Location**: `/athena_extraction_validation/patient_config.json`

**Structure**:
```json
{
  "fhir_id": "e4BwD8ZYDBccepXcJ.Ilo3w3",
  "birth_date": "2005-05-13",
  "gender": "female",
  "output_dir": "/path/to/staging_files/patient_e4BwD8ZYDBccepXcJ",
  "database": "fhir_v2_prd_db",
  "aws_profile": "343218191717_AWSAdministratorAccess",
  "s3_output": "s3://aws-athena-query-results-343218191717-us-east-1/"
}
```

**Initialization Helper**:
```bash
python3 /athena_extraction_validation/scripts/initialize_patient_config.py PATIENT_FHIR_ID
```

---

## 📚 Canonical Documentation (10 files)

### Primary Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| **COLUMN_NAMING_CONVENTIONS.md** | `/docs/` | **CRITICAL**: Defines column prefixing strategy (`proc_`, `imaging_`, `cp_`, `sr_`, etc.) |
| **README_ATHENA_VALIDATION_STRATEGY.md** | `/docs/` | Overall extraction validation strategy |
| **SYNTHESIS_COMPLETE_UNDERSTANDING.md** | `/docs/` | Complete strategic picture of hybrid Athena + BRIM pipeline |
| **README.md** | `/athena_extraction_validation/` | Main repository README with architecture overview |
| **README.md** | `/scripts/config_driven_versions/` | Config-driven scripts documentation |

### Resource-Specific Documentation

| Document | Location | Resource |
|----------|----------|----------|
| **PROCEDURES_STAGING_FILE_ANALYSIS.md** | `/docs/` | Procedures extraction |
| **IMAGING_STAGING_FILE_ANALYSIS.md** | `/docs/` | Imaging extraction |
| **MEASUREMENTS_STAGING_FILE_ANALYSIS.md** | `/docs/` | Measurements extraction |
| **COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md** | `/docs/` | Radiation therapy extraction |
| **ENCOUNTERS_SCHEMA_DISCOVERY.md** | `/docs/` | Encounters extraction |

---

## 🏗️ Column Prefixing Strategy (THE KEY FEATURE)

### Why Column Prefixing Matters

When tables are merged or used together, column prefixes **identify the source table** unambiguously.

### Prefix Conventions

| Prefix | Source Table | Example Columns |
|--------|--------------|-----------------|
| `proc_` | procedure | `proc_status`, `proc_performed_date_time`, `proc_code_text` |
| `pcc_` | procedure_code_coding | `pcc_code_coding_system`, `pcc_code` |
| `imaging_` | radiology_imaging_mri | `imaging_procedure_id`, `imaging_date`, `imaging_modality` |
| `medication_` | medication_request | `medication_name`, `medication_start_date`, `medication_status` |
| `cp_` | care_plan | `cp_status`, `cp_intent`, `cp_period_start` |
| `cpn_` | care_plan_note | `cpn_note_text`, `cpn_contains_dose` |
| `cppo_` | care_plan_part_of | `cppo_part_of_reference` |
| `sr_` | service_request | `sr_intent`, `sr_occurrence_date_time` |
| `srn_` | service_request_note | `srn_note_text`, `srn_note_time` |
| `srrc_` | service_request_reason_code | `srrc_reason_code`, `srrc_reason_display` |

### Implementation Pattern

**SQL Aliases in Extraction Queries**:
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

### Common/Shared Columns (No Prefix)

- `patient_id`
- `patient_fhir_id`
- `patient_mrn` (excluded from CSV outputs for privacy)
- Primary keys (e.g., `procedure_fhir_id`, `medication_request_id`)

---

## 📊 Output File Structure

### Per-Patient Directory Structure

```
staging_files/
└── patient_{short_id}/
    ├── demographics.csv
    ├── diagnoses.csv
    ├── procedures.csv
    ├── medications.csv
    ├── imaging.csv
    ├── measurements.csv
    ├── encounters.csv
    ├── appointments.csv
    ├── binary_files.csv
    ├── molecular_tests_metadata.csv
    └── radiation_*/                    # 10 RT CSV files
        ├── radiation_oncology_consults.csv
        ├── radiation_treatment_appointments.csv
        ├── radiation_treatment_courses.csv
        ├── radiation_care_plan_notes.csv
        ├── radiation_care_plan_hierarchy.csv
        ├── service_request_notes.csv
        ├── service_request_rt_history.csv
        ├── procedure_rt_codes.csv
        ├── procedure_notes.csv
        ├── radiation_oncology_documents.csv
        └── radiation_data_summary.csv
```

---

## ⚠️ Files to EXCLUDE from Multi-Agent Branch

### Deprecated/Backup Files

- `extract_all_imaging_metadata_original.py` - Backup before refactoring
- Any files in `/scripts/_archive/`
- `explore_radiation_*.py` - Exploratory analysis scripts (not production)

### Old Patient-Specific Scripts (in `/scripts/` parent directory)

These have **hardcoded patient IDs** and should NOT be copied:
- `extract_all_medications_metadata.py` (parent directory version)
- `extract_all_imaging_metadata.py` (parent directory version)
- Any scripts with hardcoded `PATIENT_MRN = 'C1277724'`

**Rule**: Only use scripts from `/scripts/config_driven_versions/` directory!

---

## ✅ Verification Checklist

Before using a script in multi-agent framework, verify:

- [ ] Script loads from `patient_config.json` (not hardcoded)
- [ ] Script uses SQL column aliases with prefixes (`proc_`, `imaging_`, etc.)
- [ ] Script outputs to `config['output_dir']` (not hardcoded path)
- [ ] Script is in `/scripts/config_driven_versions/` directory
- [ ] Script modification date is October 2025 (latest refactoring)
- [ ] Documentation in `/docs/` matches script behavior

---

## 🚀 Execution Order (Recommended)

### Step 1: Initialize Configuration
```bash
cd /athena_extraction_validation/scripts/
python3 initialize_patient_config.py PATIENT_FHIR_ID
```

### Step 2: Core Extractions (Run in any order)
```bash
cd config_driven_versions/

python3 extract_patient_demographics.py
python3 extract_problem_list_diagnoses.py
python3 extract_all_procedures_metadata.py
python3 extract_all_medications_metadata.py
python3 extract_all_imaging_metadata.py
python3 extract_all_measurements_metadata.py
python3 extract_all_encounters_metadata.py
python3 extract_all_binary_files_metadata.py
python3 extract_all_molecular_tests_metadata.py
```

### Step 3: Specialized Extractions
```bash
python3 filter_chemotherapy_from_medications.py  # Requires medications.csv
python3 extract_radiation_data.py                # Creates 10 RT files
```

**Total Execution Time**: ~70 seconds for complete extraction

---

## 🔑 Key Design Principles

### 1. Config-Driven Architecture
- **No hardcoded patient IDs** in any script
- Single source of truth: `patient_config.json`
- Easy multi-patient processing

### 2. Column Prefixing for Data Provenance
- **Every column** tagged with source table prefix
- Enables unambiguous table merging
- Self-documenting CSVs

### 3. Standardized Output Structure
- Generic filenames (`medications.csv`, not `medications_C1277724.csv`)
- Patient-specific directories for organization
- Consistent column naming across all extractions

### 4. Privacy-First Design
- MRN excluded from CSV outputs
- Age calculations instead of absolute dates
- Encounter references for context without identifiers

---

## 📝 Migration Notes for Multi-Agent Branch

### What to Copy

1. **All scripts from** `/scripts/config_driven_versions/` (15 files)
2. **All documentation from** `/docs/` (10 files)
3. **Helper scripts**:
   - `initialize_patient_config.py`
   - `patient_config_template.json`
4. **Main README**: `/athena_extraction_validation/README.md`

### What NOT to Copy

1. Old patient-specific scripts in `/scripts/` parent directory
2. `_archive/` directory contents
3. Exploratory analysis scripts (`explore_*.py`)
4. Backup files (`*_original.py`)

### Required Updates After Copying

1. Update paths in documentation to match new branch structure
2. Create `.gitignore` entry for `patient_config.json`
3. Verify AWS profile configuration matches target environment
4. Test with known patient ID to validate all extractions

---

## 🎯 For Multi-Agent Framework Integration

### How Staging Files Support Multi-Agent Architecture

**Master Agent (Claude)**:
- Reads staging files to understand structured data availability
- Uses column prefixes to identify data sources
- Plans extraction strategy based on what's in staging vs what needs narrative extraction

**Medical Agent (MedGemma)**:
- Queries staging files for validation during extraction
- Cross-references structured data with narrative findings
- Uses prefixed columns to cite specific sources in reasoning

**Dialogue Protocol**:
```
Master: "Check staging: do we have post-op imaging for surgery on 2018-05-29?"
Medical: [Queries imaging.csv with imaging_date filter]
Medical: "Yes - imaging_procedure_id xyz, imaging_modality=MRI, 29 hours post-op"
Master: "Extract extent of resection from imaging_result_information field"
Medical: [Performs extraction with structured context]
```

### Integration Points

1. **Phase 1 Harvester** → Reads staging CSVs into `data_sources` dictionary
2. **Phase 2 Timeline Builder** → Uses prefixed columns to build clinical timeline
3. **Phase 4 Iterative Extraction** → Passes structured context to LLM with source attribution
4. **Pass 2 Structured Query** → Queries staging data using column prefixes

---

## 📌 Summary

**Canonical Location**: `/athena_extraction_validation/scripts/config_driven_versions/`

**Latest Scripts**: 15 production-ready scripts (Oct 12-13, 2025)

**Key Feature**: Column prefixing via SQL aliases (`proc_`, `imaging_`, `cp_`, `sr_`, etc.)

**Configuration**: Centralized `patient_config.json` (no hardcoded IDs)

**Documentation**: 10 comprehensive markdown files in `/docs/`

**Status**: ✅ **PRODUCTION-READY** for multi-agent framework integration

---

**Next Step**: Copy canonical scripts and documentation to multi-agent branch, ensuring all column prefixing conventions are preserved.
