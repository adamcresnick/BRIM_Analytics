# Project Organization Guide
**Branch**: feature/multi-agent-framework
**Last Updated**: October 17, 2025
**Work Period**: October 16-17, 2025

---

## 🎯 Quick Navigation

| What You Need | Where To Go |
|--------------|-------------|
| **Athena SQL Views** | [athena_views/](#1-athena-views) |
| **Data Extraction Scripts** | [staging_extraction/](#2-staging-extraction) |
| **CSV Outputs** | [staging_extraction/staging_files/](#csv-outputs) |
| **Multi-Agent Workflows** | [local_llm_extraction/](#3-local-llm-extraction) |
| **Today's Work Summary** | [What Was Accomplished](#what-was-accomplished-oct-16-17) |

---

## 📁 Directory Structure

```
/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/
│
├── 📊 athena_views/                    ← All 15 Athena SQL views
│   ├── README.md                       (Quick start guide)
│   ├── views/
│   │   ├── ATHENA_VIEW_CREATION_QUERIES.sql (All 15 CREATE VIEW statements)
│   │   └── RERUN_STANDARDIZED_VIEWS.sql     (Patient ID standardization)
│   ├── documentation/
│   │   ├── ATHENA_VIEW_FIXES.md             (60+ fixes documented)
│   │   ├── PATIENT_IDENTIFIER_ANALYSIS.md   (Patient ID analysis)
│   │   ├── DATE_TIME_STANDARDIZATION_ANALYSIS.md (Date format analysis - 700+ lines)
│   │   ├── DATE_STANDARDIZATION_EXAMPLE.sql (Working example)
│   │   └── STANDARDIZATION_SUMMARY.md       (What changed and why)
│   └── verification/
│       └── ATHENA_VIEWS_VERIFICATION.md     (Test results)
│
├── 🔄 staging_extraction/              ← Config-driven extraction pipeline
│   ├── README.md                       (Quick start guide)
│   ├── config_driven/                  (15 Python extraction scripts)
│   │   ├── extract_patient_demographics.py
│   │   ├── extract_problem_list_diagnoses.py
│   │   ├── extract_all_procedures_metadata.py
│   │   ├── extract_all_medications_metadata.py
│   │   ├── extract_all_imaging_metadata.py
│   │   ├── extract_all_encounters_metadata.py
│   │   ├── extract_all_measurements_metadata.py
│   │   ├── extract_all_binary_files_metadata.py
│   │   ├── extract_all_molecular_tests_metadata.py
│   │   ├── extract_radiation_data.py   (Produces 6 radiation CSVs)
│   │   └── shared_utilities.py
│   ├── documentation/
│   │   ├── STAGING_FILES_CANONICAL_REFERENCE.md
│   │   └── README_ATHENA_EXTRACTION.md
│   ├── patient_config.json             (Current patient configuration)
│   ├── patient_config_template.json
│   ├── initialize_patient_config.py
│   └── staging_files/                  (CSV outputs per patient)
│       └── patient_e4BwD8ZYDBccepXcJ.Ilo3w3/
│           ├── patient_demographics.csv
│           ├── problem_list_diagnoses.csv
│           ├── procedures.csv
│           ├── medications.csv
│           ├── imaging.csv
│           ├── encounters.csv
│           ├── measurements.csv
│           ├── binary_files.csv
│           ├── molecular_tests_metadata.csv
│           ├── appointments.csv
│           ├── radiation_treatment_appointments.csv
│           ├── radiation_treatment_courses.csv
│           ├── radiation_care_plan_notes.csv
│           ├── radiation_care_plan_hierarchy.csv
│           ├── radiation_service_request_notes.csv
│           ├── radiation_service_request_rt_history.csv
│           └── radiation_data_summary.csv
│
└── 🤖 local_llm_extraction/            ← Multi-agent workflows
    ├── README.md                       (Overview)
    ├── MULTI_AGENT_BRANCH_README.md    (Branch-specific guide)
    ├── event_based_extraction/         (Event-based workflows)
    ├── form_extractors/                (Form extraction)
    ├── iterative_extraction/           (Iterative refinement)
    ├── Dictionary/                     (Data dictionaries)
    ├── utils/
    ├── patient_config.json → ../staging_extraction/patient_config.json  (symlink)
    └── config_driven → ../staging_extraction/config_driven/             (symlink)
```

---

## 1️⃣ Athena Views

### Location
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views
```

### What's Here
All 15 Athena SQL views that replicate Python extraction script outputs for scalable, all-patient queries.

### The 15 Views

#### Core Clinical Data (9 views)
1. **v_patient_demographics** - Basic patient info (age, gender, race, ethnicity)
2. **v_problem_list_diagnoses** - All diagnoses with ICD-10/SNOMED codes
3. **v_procedures** - Surgical procedures with CPT codes
4. **v_medications** - Medication requests linked to care plans
5. **v_imaging** - MRI and other imaging with diagnostic reports
6. **v_encounters** - All patient encounters (inpatient, outpatient)
7. **v_measurements** - Lab results and vital signs (UNION of observation + lab_tests)
8. **v_binary_files** - Document references (22K+ docs per patient)
9. **v_molecular_tests** - Genetic/molecular test results

#### Radiation Oncology (6 views)
10. **v_radiation_treatment_appointments** - RT appointments
11. **v_radiation_treatment_courses** - RT treatment courses
12. **v_radiation_care_plan_notes** - RT care plan narratives
13. **v_radiation_care_plan_hierarchy** - Care plan linkages
14. **v_radiation_service_request_notes** - RT order notes
15. **v_radiation_service_request_rt_history** - RT treatment history

### Quick Start
```sql
-- Copy SQL from this file and run in AWS Athena Console
open athena_views/views/ATHENA_VIEW_CREATION_QUERIES.sql

-- Test a view
SELECT * FROM fhir_prd_db.v_patient_demographics LIMIT 10;
```

### Key Documentation
- [athena_views/README.md](athena_views/README.md) - Comprehensive guide
- [athena_views/documentation/ATHENA_VIEW_FIXES.md](athena_views/documentation/ATHENA_VIEW_FIXES.md) - All 60+ fixes
- [athena_views/documentation/PATIENT_IDENTIFIER_ANALYSIS.md](athena_views/documentation/PATIENT_IDENTIFIER_ANALYSIS.md) - Patient ID standardization
- [athena_views/documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md](athena_views/documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md) - Date format analysis

---

## 2️⃣ Staging Extraction

### Location
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/staging_extraction
```

### What's Here
Config-driven Python scripts that extract FHIR data for individual patients and save as CSV files.

### The 15 Extraction Scripts

Located in `staging_extraction/config_driven/`:

| Script | Output CSV | Description |
|--------|-----------|-------------|
| extract_patient_demographics.py | patient_demographics.csv | Age, gender, race, ethnicity |
| extract_problem_list_diagnoses.py | problem_list_diagnoses.csv | All diagnoses with ICD-10 |
| extract_all_procedures_metadata.py | procedures.csv | Surgical procedures with CPT |
| extract_all_medications_metadata.py | medications.csv | Medications + care plans |
| extract_all_imaging_metadata.py | imaging.csv | MRI and imaging reports |
| extract_all_encounters_metadata.py | encounters.csv | All patient encounters |
| extract_all_measurements_metadata.py | measurements.csv | Labs + vitals |
| extract_all_binary_files_metadata.py | binary_files.csv | Document references |
| extract_all_molecular_tests_metadata.py | molecular_tests_metadata.csv | Genetic tests |
| extract_radiation_data.py | 6 radiation CSVs | All radiation therapy data |

### Quick Start
```bash
# 1. Configure patient
cd staging_extraction
python initialize_patient_config.py

# 2. Run extraction
cd config_driven
python extract_patient_demographics.py

# 3. Check outputs
ls ../staging_files/patient_XXXX/*.csv
```

### CSV Outputs

Most recent extractions in:
```bash
staging_extraction/staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/
```

Contains 17 CSV files:
- 9 core clinical data files
- 7 radiation therapy files
- 1 summary file

### Key Documentation
- [staging_extraction/README.md](staging_extraction/README.md) - Complete guide
- [staging_extraction/documentation/STAGING_FILES_CANONICAL_REFERENCE.md](staging_extraction/documentation/STAGING_FILES_CANONICAL_REFERENCE.md) - File specifications

---

## 3️⃣ Local LLM Extraction

### Location
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction
```

### What's Here
Multi-agent workflows for advanced LLM-based extraction and processing.

### Key Components

#### event_based_extraction/
Multi-agent workflows for event-based data extraction
- Surgery events
- Treatment events
- Diagnosis events

#### form_extractors/
Structured data extraction from clinical forms
- BRIM forms
- Research protocols
- Clinical assessments

#### iterative_extraction/
Iterative refinement workflows
- Multiple passes over data
- Quality improvement loops
- Validation steps

#### Dictionary/
Data dictionaries and schemas

### Symlinks (for backward compatibility)
- `patient_config.json` → `../staging_extraction/patient_config.json`
- `config_driven` → `../staging_extraction/config_driven/`

### Key Documentation
- [local_llm_extraction/README.md](local_llm_extraction/README.md) - Overview
- [local_llm_extraction/MULTI_AGENT_BRANCH_README.md](local_llm_extraction/MULTI_AGENT_BRANCH_README.md) - Branch guide

---

## 🎉 What Was Accomplished (Oct 16-17)

### Athena Views
- ✅ Created and validated all 15 SQL views
- ✅ Fixed 60+ column name mismatches
- ✅ Completely rewrote v_molecular_tests (was using wrong tables)
- ✅ Added patient identifier to v_radiation_treatment_appointments
- ✅ Fixed SQL reserved keyword issue (`end` → `"end"`)
- ✅ Standardized `patient_fhir_id` across all views
- ✅ Analyzed date/time format inconsistencies (700+ line analysis)

### Staging Extraction
- ✅ Organized 15 Python extraction scripts
- ✅ Generated complete CSV outputs for test patient
- ✅ Documented all file formats and schemas
- ✅ Created config-driven extraction framework

### Documentation
- ✅ Created 3,000+ lines of documentation
- ✅ Comprehensive fix history
- ✅ Patient ID standardization analysis
- ✅ Date/time format analysis
- ✅ Working examples and guides
- ✅ Updated all README files

### Project Organization
- ✅ Reorganized into clean, logical structure
- ✅ Separated concerns (SQL / Python / LLM)
- ✅ Created symlinks for backward compatibility
- ✅ Clear navigation with README at each level

---

## 🚀 Quick Commands

### View Athena Views
```bash
cd athena_views
open views/ATHENA_VIEW_CREATION_QUERIES.sql
```

### Run Data Extraction
```bash
cd staging_extraction/config_driven
python extract_patient_demographics.py
```

### View CSV Outputs
```bash
cd staging_extraction/staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3
ls *.csv
open patient_demographics.csv
```

### Work on Multi-Agent
```bash
cd local_llm_extraction
open MULTI_AGENT_BRANCH_README.md
```

---

## 📊 Database Connection

**Database**: `fhir_prd_db`
**AWS Account**: 343218191717
**Region**: us-east-1
**Output Location**: s3://aws-athena-query-results-343218191717-us-east-1/

---

## 🔗 Key Files Reference

### SQL Views
- All 15 views: [athena_views/views/ATHENA_VIEW_CREATION_QUERIES.sql](athena_views/views/ATHENA_VIEW_CREATION_QUERIES.sql)
- Patient ID updates: [athena_views/views/RERUN_STANDARDIZED_VIEWS.sql](athena_views/views/RERUN_STANDARDIZED_VIEWS.sql)

### Python Scripts
- 15 extraction scripts: [staging_extraction/config_driven/](staging_extraction/config_driven/)
- Patient configuration: [staging_extraction/patient_config.json](staging_extraction/patient_config.json)

### Documentation
- Athena guide: [athena_views/README.md](athena_views/README.md)
- Extraction guide: [staging_extraction/README.md](staging_extraction/README.md)
- Multi-agent guide: [local_llm_extraction/MULTI_AGENT_BRANCH_README.md](local_llm_extraction/MULTI_AGENT_BRANCH_README.md)
- View fixes: [athena_views/documentation/ATHENA_VIEW_FIXES.md](athena_views/documentation/ATHENA_VIEW_FIXES.md)
- Patient ID analysis: [athena_views/documentation/PATIENT_IDENTIFIER_ANALYSIS.md](athena_views/documentation/PATIENT_IDENTIFIER_ANALYSIS.md)
- Date/time analysis: [athena_views/documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md](athena_views/documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md)

### Outputs
- CSV files: [staging_extraction/staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/](staging_extraction/staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/)

---

## 🌿 Git Branch

This work is on the `feature/multi-agent-framework` branch.

```bash
# Check current branch
git branch --show-current
# Output: feature/multi-agent-framework

# View all branches
git branch -a
```

---

## 📝 Next Steps

### 1. Review Date/Time Standardization
See [athena_views/documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md](athena_views/documentation/DATE_TIME_STANDARDIZATION_ANALYSIS.md) for proposed hybrid approach (date + datetime columns).

### 2. Test Extraction Pipeline
```bash
cd staging_extraction/config_driven
python extract_patient_demographics.py
```

### 3. Continue Multi-Agent Development
Resume work in `local_llm_extraction/` with cleaned structure.

### 4. Commit to Git
All changes are ready to commit to the `feature/multi-agent-framework` branch.

---

## 💡 Tips

### Finding Things Quickly
- **Need SQL?** → `athena_views/views/`
- **Need Python extraction?** → `staging_extraction/config_driven/`
- **Need CSV outputs?** → `staging_extraction/staging_files/`
- **Need multi-agent code?** → `local_llm_extraction/`
- **Need documentation?** → Look for README.md in each directory

### Understanding Symlinks
Symlinks (marked with `→`) are shortcuts:
- `local_llm_extraction/patient_config.json` → Points to `staging_extraction/patient_config.json`
- Opening the symlink actually opens the real file
- Like a bookmark or alias

### Working with Git
```bash
# See what changed
git status

# See what branch you're on
git branch --show-current

# See all branches
git branch -a
```

---

## 📞 Support

- **Issues**: Report at GitHub issues
- **Questions**: Check README.md files in each directory
- **Athena**: See [athena_views/README.md](athena_views/README.md)
- **Extraction**: See [staging_extraction/README.md](staging_extraction/README.md)
- **Multi-Agent**: See [local_llm_extraction/MULTI_AGENT_BRANCH_README.md](local_llm_extraction/MULTI_AGENT_BRANCH_README.md)

---

## 📅 Change Log

### 2025-10-17
- ✅ Created comprehensive project organization
- ✅ Reorganized into clean directory structure
- ✅ Standardized patient_fhir_id across all views
- ✅ Analyzed date/time format inconsistencies
- ✅ Created this organization guide

### 2025-10-16
- ✅ Fixed all 15 Athena views
- ✅ Validated all views with test queries
- ✅ Generated complete CSV outputs for test patient
- ✅ Documented all extraction scripts

---

**Last Updated**: October 17, 2025
**Branch**: feature/multi-agent-framework
**Status**: ✅ Clean and Organized
