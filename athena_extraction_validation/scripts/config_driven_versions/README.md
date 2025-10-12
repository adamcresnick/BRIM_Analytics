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

## Status
- **Created**: October 11, 2025
- **Purpose**: Multi-patient extraction workflow
- **Note**: These scripts were created by modifying the originals in place (mistake!), then backed up here before restoring the originals from git.

## Next Steps
- Fix extract_all_imaging_metadata.py (missing methods after bad refactoring)
- Test all scripts with new patient configuration
- Consider merging successful patterns back into originals with optional config support
