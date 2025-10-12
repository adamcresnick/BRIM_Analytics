# Radiation Therapy Data Extraction Script

## Quick Start

```bash
# Login to AWS
aws sso login --profile 343218191717_AWSAdministratorAccess

# Run extraction
python3 scripts/extract_radiation_data.py <patient_id>
```

## What It Does

Extracts comprehensive radiation therapy data from Athena FHIR database:
- ✅ Radiation oncology consultations
- ✅ Treatment simulations
- ✅ Treatment start/end dates
- ✅ Treatment duration calculations
- ✅ Re-irradiation detection
- ✅ Treatment technique identification (IMRT, proton, etc.)

## Output Files

Results saved to `staging_files/patient_{id}/`:

1. **radiation_oncology_consults.csv** - Rad onc consultation appointments
2. **radiation_treatment_appointments.csv** - All RT-related appointments
3. **radiation_treatment_courses.csv** - Reconstructed treatment courses with dates
4. **radiation_data_summary.csv** - Single-row summary for BRIM variables

## Example Output

```
Patient: eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3

Radiation Therapy Received: Yes
Number of Rad Onc Consults: 2
Number of RT Appointments:  12
Number of Treatment Courses: 3
Re-irradiation:             Yes
Treatment Techniques:       IMRT

Course #1:
  Start Date: 2023-09-14
  End Date:   2023-10-25
  Duration:   5.9 weeks (41 days)

Course #2:
  Start Date: 2024-09-05
  End Date:   2024-09-25
  Duration:   2.9 weeks (20 days)
```

## Tested Patients

- ✅ `eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3` - Has radiation data (2 courses, re-irradiation)
- ✅ `eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3` - No radiation data (negative control)

## Full Documentation

See: `docs/RADIATION_EXTRACTION_SCRIPT_DOCUMENTATION.md`
