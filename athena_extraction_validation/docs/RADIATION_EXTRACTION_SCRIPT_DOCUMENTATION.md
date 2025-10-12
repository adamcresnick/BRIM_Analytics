# Radiation Therapy Data Extraction - Documentation

**Script:** `scripts/extract_radiation_data.py`  
**Created:** 2025-10-12  
**Purpose:** Extract comprehensive radiation oncology data from Athena FHIR database

## Overview

This script extracts all radiation therapy-related data from the FHIR v2 database, including:
- Radiation oncology consultations
- Treatment appointments (simulations, starts, ends)
- Treatment course identification
- Re-irradiation detection
- Treatment technique identification (IMRT, proton, stereotactic, etc.)

## Usage

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation

# Single patient extraction
python3 scripts/extract_radiation_data.py <patient_id>

# Examples
python3 scripts/extract_radiation_data.py C1277724
python3 scripts/extract_radiation_data.py eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3
python3 scripts/extract_radiation_data.py eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3
```

## Prerequisites

1. **AWS SSO Authentication:**
   ```bash
   aws sso login --profile 343218191717_AWSAdministratorAccess
   ```

2. **Python Dependencies:**
   - boto3
   - pandas
   - json
   - re

## Data Sources

### 1. Radiation Oncology Consults
**Source:** `appointment_service_type` table  
**Method:** Two-stage query to work around Athena limitations

**Query Strategy:**
```sql
-- Stage 1: Get all service types for patient
SELECT DISTINCT ast.appointment_id, ast.service_type_coding
FROM appointment_service_type ast
JOIN appointment_participant ap ON ast.appointment_id = ap.appointment_id
WHERE ap.participant_actor_reference = 'Patient/{id}'

-- Stage 2: Filter in pandas for radiation terms
-- Stage 3: Get full appointment details for matching IDs
SELECT DISTINCT a.*
FROM appointment a
WHERE a.id IN ('{filtered_ids}')
```

**Search Terms in service_type_display:**
- "rad onc"
- "radiation"
- "xrt"

### 2. Radiation Treatment Appointments
**Source:** `appointment` table (comment, patient_instruction, description fields)  
**Method:** Get all appointments, filter in pandas

**Search Terms:**
- radiation
- radiotherapy
- rad onc
- imrt
- xrt
- rt simulation / rt sim
- re-irradiation / reirradiation
- proton
- photon
- intensity modulated
- stereotactic
- sbrt / srs
- cranial radiation
- csi (craniospinal irradiation)

### 3. Treatment Categorization

Appointments are automatically categorized based on comment text:

| Category | Trigger Words | Example |
|----------|--------------|---------|
| Consultation | consult, consultation | "RAD ONC CONSULT" |
| Simulation | simulation, sim | "IMRT SIM" |
| Treatment Start | start + (rt/imrt/treatment) | "Start IMRT - DONE" |
| Treatment End | end + radiation | "End of Radiation Treatment" |
| Re-irradiation | re-irradiation, reirradiation | "s/p focal RT and re-irradiation" |
| Post-Treatment | s/p + (rt/radiation) | "s/p focal RT" |
| Treatment Session | imrt, proton, stereotactic | "IMRT session" |
| Related Visit | (any other radiation mention) | "follow-up with oncology" |

### 4. Treatment Course Identification

**Logic:**
1. Find all appointments marked as "Treatment Start"
2. For each start, find the next "Treatment End" appointment
3. Calculate duration in days and weeks
4. Extract treatment comments

**Output Fields:**
- `course_number`: 1, 2, 3, etc.
- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD
- `duration_days`: Integer
- `duration_weeks`: Float (rounded to 1 decimal)
- `start_comment`: Full comment from start appointment
- `end_comment`: Full comment from end appointment
- `start_status`: fulfilled, cancelled, etc.

## Output Files

All files are saved to: `staging_files/patient_{patient_id}/`

### 1. radiation_oncology_consults.csv
Contains all radiation oncology consultation appointments with full FHIR appointment details plus parsed service type.

**Key Columns:**
- `id`: FHIR appointment ID
- `start`: Consultation date/time
- `status`: fulfilled, cancelled, etc.
- `service_type_display`: Human-readable service type (e.g., "RAD ONC CONSULT")
- `comment`: Clinical notes
- All other FHIR appointment fields

### 2. radiation_treatment_appointments.csv
Contains all radiation treatment-related appointments.

**Key Columns:**
- `id`: FHIR appointment ID
- `start`: Appointment date/time
- `status`: Appointment status
- `comment`: Clinical notes (key field!)
- `patient_instruction`: Patient-facing instructions
- `rt_category`: Categorization (Simulation, Treatment Start, etc.)
- `rt_milestone`: Key milestones (START, END, RE-RT, s/p RT)
- All other FHIR appointment fields

### 3. radiation_treatment_courses.csv
Reconstructed treatment courses with start/end dates.

**Columns:**
- `course_number`: 1, 2, 3, etc.
- `start_date`: YYYY-MM-DD
- `end_date`: YYYY-MM-DD
- `duration_days`: Integer
- `duration_weeks`: Float
- `start_comment`: Comment from start appointment
- `end_comment`: Comment from end appointment
- `start_status`: Status of start appointment

### 4. radiation_data_summary.csv
Single-row summary for BRIM trial variable extraction.

**Columns:**
- `patient_id`: Patient identifier
- `extraction_date`: Timestamp of extraction
- `num_rad_onc_consults`: Count of rad onc consultations
- `num_radiation_appointments`: Count of RT-related appointments
- `num_treatment_courses`: Count of distinct RT courses
- `radiation_therapy_received`: Yes/No
- `re_irradiation`: Yes/No
- `course_1_start_date`, `course_1_end_date`, `course_1_duration_weeks`
- `course_2_start_date`, `course_2_end_date`, `course_2_duration_weeks`
- `course_3_start_date`, `course_3_end_date`, `course_3_duration_weeks`
- `treatment_techniques`: Comma-separated list (e.g., "IMRT")

## Athena SQL Limitations

The script works around several Athena SQL limitations:

### 1. No OR Clauses in JOIN Contexts
**Problem:** Complex WHERE clauses with OR fail when joining tables.

**Solution:** Get all data, filter in pandas.

### 2. No Column Listing with Complex JOINs
**Problem:** `SELECT a.id, a.start, ...` fails with certain JOINs.

**Solution:** Use `SELECT a.*` or two-stage queries.

### 3. No JSON Field Querying in JOINs
**Problem:** Cannot directly query JSON fields in complex JOINs.

**Solution:** 
1. Get JSON field as VARCHAR
2. Parse in Python
3. Filter in pandas

## Validation Results

### Test Patient 1: eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3
**Result:** ✅ **No radiation therapy**
- Total appointments: 62
- Radiation appointments: 0
- Rad onc consults: 0
- Treatment courses: 0

This is the expected result - patient did not receive radiation therapy.

### Test Patient 2: eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3
**Result:** ✅ **Comprehensive radiation therapy data**
- Total appointments: 476
- Radiation appointments: 12 (core treatment milestones)
- Rad onc consults: 2
- Treatment courses: 3 (likely 2 actual courses + 1 cancelled/rescheduled start)

**Key Findings:**
- 2 radiation oncology consultations (2023-08-21, 2024-07-25)
- 5 simulation appointments (IMRT planning)
- 3 treatment start dates (2 in 2023, 1 in 2024)
- 2 treatment end dates (2023-10-25, 2024-09-25)
- Re-irradiation documented (second course in 2024)
- Treatment technique: IMRT (Intensity-Modulated Radiation Therapy)

**Treatment Timeline:**
1. **First Course (2023):**
   - Consult: 2023-08-21
   - Simulations: Aug 22
   - Treatment: Sep 14 - Oct 25 (~6 weeks)
   
2. **Second Course - Re-irradiation (2024):**
   - Consult: 2024-07-25
   - Simulations: Aug 27, Sep 10
   - Treatment: Sep 5 - Sep 25 (~3 weeks)

## BRIM Trial Variable Mapping

This extraction directly supports these BRIM variables:

| BRIM Variable | Source | Extraction |
|---------------|--------|------------|
| `RADIATION_THERAPY_RECEIVED` | Summary | `radiation_therapy_received` |
| `NUMBER_OF_RT_COURSES` | Summary | `num_treatment_courses` |
| `RT_COURSE_1_START_DATE` | Courses | `course_1_start_date` |
| `RT_COURSE_1_END_DATE` | Courses | `course_1_end_date` |
| `RT_COURSE_1_DURATION_WEEKS` | Courses | `course_1_duration_weeks` |
| `RT_COURSE_2_START_DATE` | Courses | `course_2_start_date` |
| `RT_COURSE_2_END_DATE` | Courses | `course_2_end_date` |
| `RT_COURSE_2_DURATION_WEEKS` | Courses | `course_2_duration_weeks` |
| `RE_IRRADIATION` | Summary | `re_irradiation` |
| `RT_TECHNIQUE` | Summary | `treatment_techniques` |
| `RAD_ONC_CONSULTS` | Summary | `num_rad_onc_consults` |

**Variables Requiring Additional Data:**
- Radiation dose (total Gy) - Not in appointment data
- Dose per fraction - Not in appointment data
- Treatment target/field - May be in clinical notes
- Concurrent chemotherapy - Requires medication extraction
- Reason for re-irradiation - May be in clinical notes

## Integration with BRIM Workflow

### Option 1: Standalone Extraction
Run this script separately for each patient and merge outputs.

### Option 2: Integration into pilot_workflow.py
Add radiation extraction as a workflow step:

```python
# In pilot_workflow.py
from scripts.extract_radiation_data import main as extract_radiation_data

# After other extractions
print("\nExtracting radiation therapy data...")
radiation_summary = extract_radiation_data(patient_id)
```

### Option 3: Batch Processing
Create a batch script to process all BRIM patients:

```python
import pandas as pd
from scripts.extract_radiation_data import main as extract_radiation_data

# Read patient list
patients = pd.read_csv('patient_list.csv')

for patient_id in patients['patient_id']:
    try:
        extract_radiation_data(patient_id)
    except Exception as e:
        print(f"Error for {patient_id}: {e}")
```

## Known Limitations

### 1. Duplicate Start Dates
Some patients may have multiple "Start" appointments due to:
- Cancelled/rescheduled appointments (status = "cancelled")
- Initial vs. actual treatment start
- Documentation inconsistencies

**Mitigation:** Review appointment status field; prioritize "fulfilled" status.

### 2. Missing Dose Information
Appointment data does NOT contain:
- Total radiation dose (Gy)
- Dose per fraction
- Treatment fields/volumes

**Mitigation:** Would require clinical notes or external radiation oncology system.

### 3. Daily Treatment Sessions
Individual daily treatment sessions are NOT captured in appointment data.

**Current Data:** Only major milestones (consult, simulation, start, end)

**Impact:** Cannot calculate actual number of fractions delivered; must infer from duration.

### 4. Treatment Intent
Cannot determine from appointment data:
- Curative vs. palliative intent
- Definitive vs. adjuvant therapy
- Primary vs. salvage treatment

**Mitigation:** May be in clinical notes.

## Troubleshooting

### Error: "Token has expired and refresh failed"
**Solution:**
```bash
aws sso login --profile 343218191717_AWSAdministratorAccess
```

### Error: "Queries of this type are not supported"
**Cause:** Complex Athena SQL query with OR clauses or column aliasing.

**Solution:** Already handled in script with two-stage queries.

### No appointments found but patient should have data
**Check:**
1. Patient ID format: Should NOT include "Patient/" prefix when calling script
2. FHIR reference: Script automatically adds "Patient/" prefix
3. AWS profile: Verify correct profile is active

### Radiation appointments found but no treatment courses
**Possible Reasons:**
1. No explicit "Start" or "End" appointments
2. Treatment ongoing (no end date yet)
3. Treatment documented differently (e.g., only simulations scheduled)

**Solution:** Review `radiation_treatment_appointments.csv` for all mentions.

## Future Enhancements

### 1. Clinical Notes Integration
Extract radiation dose and treatment parameters from:
- Radiation oncology consult notes
- Treatment planning notes
- Summary documents

### 2. Imaging Correlation
Link to:
- Planning CT scans
- Simulation imaging
- Follow-up imaging

### 3. Toxicity Tracking
Extract radiation-related toxicities from:
- Problem list
- Encounter diagnoses
- Clinical notes

### 4. Outcome Correlation
Link radiation data to:
- Disease progression
- Survival outcomes
- Quality of life measures

## References

- **FHIR Tables:** `appointment`, `appointment_participant`, `appointment_service_type`
- **AWS Athena:** Database `fhir_v2_prd_db`
- **Related Documentation:**
  - `docs/RADIATION_TREATMENT_IDENTIFICATION_FINDINGS.md`
  - `athena_extraction_validation/docs/RADIATION_DATA_PATIENT_eoA0IUD9y_COMPREHENSIVE.md`
- **Related Scripts:**
  - `scripts/search_radiation_appointment_service_types.py`
  - `scripts/search_radiation_procedures.py`
  - `scripts/search_radiation_service_requests.py`

## Contact

For questions or issues, contact the Clinical Data Extraction Team.

---

**Last Updated:** 2025-10-12  
**Version:** 1.0  
**Status:** Production-ready, validated with multiple test patients
