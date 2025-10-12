# Config-Driven Extraction Scripts

## Overview
These are **refactored versions** of the extraction scripts that use a centralized `patient_config.json` file instead of hardcoded patient information.

## Key Differences from Original Scripts

### Original Scripts (patient-specific)
- Hardcoded: `PATIENT_MRN = 'C1277724'`
- Hardcoded: `PATIENT_FHIR_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'`
- Output files: `ALL_MEDICATIONS_METADATA_C1277724.csv`

### Config-Driven Scripts (multi-patient)
- Load from: `patient_config.json`
- Generic output: `medications.csv`, `encounters.csv`, etc.
- Patient-specific output directory: `staging_files/patient_<shortid>/`

## Usage

1. **Edit patient_config.json** (in parent directory):
```json
{
  "fhir_id": "eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3",
  "birth_date": "1988-05-13",
  "gender": "female",
  "output_dir": "staging_files/patient_eXdoUrDdY4gkdnZEs6uTeq",
  "database": "fhir_v2_prd_db",
  "aws_profile": "343218191717_AWSAdministratorAccess",
  "s3_output": "s3://aws-athena-query-results-343218191717-us-east-1/"
}
```

2. **Run any extraction script**:
```bash
python3 extract_all_medications_metadata.py
```

3. **Output goes to**: `staging_files/patient_eXdoUrDdY4gkdnZEs6uTeq/medications.csv`

## Scripts Included
- extract_all_encounters_metadata.py ✅
- extract_all_procedures_metadata.py ✅
- extract_all_binary_files_metadata.py ✅
- extract_all_medications_metadata.py ✅
- extract_all_measurements_metadata.py ✅
- extract_all_diagnoses_metadata.py ✅
- extract_all_imaging_metadata.py ⚠️ (corrupted during refactoring - needs restoration)
- filter_chemotherapy_from_medications.py ✅
- **extract_radiation_data.py** ✅ **NEW** (October 12, 2025)

## Status
- **Created**: October 11, 2025
- **Updated**: October 12, 2025 - Added radiation therapy extraction
- **Purpose**: Multi-patient extraction workflow
- **Note**: These scripts were created by modifying the originals in place (mistake!), then backed up here before restoring the originals from git.

## Radiation Therapy Extraction (NEW - October 12, 2025)

The `extract_radiation_data.py` script has been refactored to use the config-driven pattern:

**Output Files** (up to 10 CSV files per patient):
```
radiation_oncology_consults.csv          # Rad Onc consultation appointments
radiation_treatment_appointments.csv     # RT treatment appointments & milestones
radiation_treatment_courses.csv          # Identified treatment courses
radiation_care_plan_notes.csv           # Care plan notes (RT-related)
radiation_care_plan_hierarchy.csv       # Care plan relationships
service_request_notes.csv               # Service request notes
service_request_rt_history.csv          # RT history codes
procedure_rt_codes.csv                  # RT procedure codes (CPT 77xxx)
procedure_notes.csv                     # RT-specific procedure notes
radiation_oncology_documents.csv        # Rad Onc documents (with retrieval flags)
radiation_data_summary.csv              # Extraction summary statistics
```

**Test Results** (Patient eXdoUrDdY4gkdnZEs6uTeq):
- ✅ 4 radiation treatment appointments
- ✅ 38 service request notes (dosage information)
- ✅ Successfully integrated with other extraction scripts
- ✅ Config-driven: no command-line arguments needed
- ✅ Output to standardized staging directory

## Next Steps
- Fix extract_all_imaging_metadata.py (missing methods after bad refactoring)
- Test radiation extraction with RT patient (should have more data than test patient)
- Consider merging successful patterns back into originals with optional config support
- Add service_request_notes.csv to other extraction pipelines for consistency
