# Phase 3a_v2: Athena Demographics Integration Summary

## Key Discovery

✅ **Patient demographics ARE available in Athena**: `fhir_v2_prd_db.patient_access` table
✅ **Our gold standard was CORRECT**: Patient C1277724 DOB = 2005-05-13, age at diagnosis = 13 years
✅ **Phase 3a failures were due to lack of structured data access**, not BRIM limitations

## Correct Patient Data (from Athena)

**Table**: `fhir_v2_prd_db.patient_access`
**Patient FHIR ID**: `e4BwD8ZYDBccepXcJ.Ilo3w3`

```sql
SELECT id, gender, birth_date, race, ethnicity, deceased_boolean
FROM fhir_v2_prd_db.patient_access
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

**Results**:
| Field | Value | Gold Standard Match |
|-------|-------|-------------------|
| `id` | e4BwD8ZYDBccepXcJ.Ilo3w3 | ✅ |
| `gender` | female | ✅ (capitalize to "Female") |
| `birth_date` | 2005-05-13 | ✅ EXACT MATCH |
| `race` | White | ✅ |
| `ethnicity` | Not Hispanic or Latino | ✅ |

## Age Validation

```
Birth Date:      2005-05-13
First Surgery:   2018-05-28  →  Age: 13.04 years = 13 years ✅
Diagnosis Date:  2018-06-04  →  Age: 13.06 years = 13 years ✅
Second Surgery:  2021-03-10  →  Age: 15.82 years = 15 years ✅
```

**Phase 3a BRIM extracted "15 years"** - This was from narrative text referring to the **second surgery**, not diagnosis!

## Integration Strategy for Phase 3a_v2

### Approach: Pre-populate Demographics CSV

**File**: `pilot_output/brim_csvs_iteration_3c_phase3a_v2/patient_demographics.csv`

```csv
patient_fhir_id,gender,birth_date,race,ethnicity
e4BwD8ZYDBccepXcJ.Ilo3w3,Female,2005-05-13,White,Not Hispanic or Latino
```

**Note**: 
- Gender capitalized to "Female" (Athena has "female", data dictionary expects "Female")
- All other values match Athena exactly

### Updated Variable Instructions

#### 1. date_of_birth
```csv
variable_name,field_type,field_label,option_definitions,prompt
date_of_birth,date,Date of Birth,,"PRIORITY 1: Check patient_demographics.csv for birth_date field matching patient FHIR ID '{patient_fhir_id}'.

PRIORITY 2: If patient_demographics.csv not available, search FHIR Patient resource for birthDate field.

PRIORITY 3: If FHIR resource unavailable, search clinical notes for keywords:
- 'DOB:'
- 'Date of Birth:'
- 'Born on'
- 'Birth date:'

Return in YYYY-MM-DD format only."
```

#### 2. patient_gender
```csv
variable_name,field_type,field_label,option_definitions,prompt
patient_gender,radio,Patient Gender,"{""Male"": ""Male"", ""Female"": ""Female""}","PRIORITY 1: Check patient_demographics.csv for gender field matching patient FHIR ID '{patient_fhir_id}'.

PRIORITY 2: If patient_demographics.csv not available, search FHIR Patient resource for gender field.

PRIORITY 3: If FHIR resource unavailable, search clinical notes for gender indicators.

Return EXACTLY one of: 'Male' or 'Female' (capitalized)."
```

#### 3. race
```csv
variable_name,field_type,field_label,option_definitions,prompt
race,dropdown,Race,"{""White"": ""White"", ""Black or African American"": ""Black or African American"", ""Asian"": ""Asian"", ""American Indian or Alaska Native"": ""American Indian or Alaska Native"", ""Native Hawaiian or Other Pacific Islander"": ""Native Hawaiian or Other Pacific Islander"", ""Unknown"": ""Unknown"", ""Declined to answer"": ""Declined to answer""}","PRIORITY 1: Check patient_demographics.csv for race field matching patient FHIR ID '{patient_fhir_id}'.

PRIORITY 2: If patient_demographics.csv not available, search FHIR Patient resource for race extension.

PRIORITY 3: If unavailable, return 'Unknown'.

Return EXACTLY one of the option values."
```

#### 4. ethnicity
```csv
variable_name,field_type,field_label,option_definitions,prompt
ethnicity,dropdown,Ethnicity,"{""Hispanic or Latino"": ""Hispanic or Latino"", ""Not Hispanic or Latino"": ""Not Hispanic or Latino"", ""Unknown"": ""Unknown"", ""Declined to answer"": ""Declined to answer""}","PRIORITY 1: Check patient_demographics.csv for ethnicity field matching patient FHIR ID '{patient_fhir_id}'.

PRIORITY 2: If patient_demographics.csv not available, search FHIR Patient resource for ethnicity extension.

PRIORITY 3: If unavailable, return 'Unknown'.

Return EXACTLY one of the option values."
```

#### 5. age_at_diagnosis
```csv
variable_name,field_type,field_label,option_definitions,prompt
age_at_diagnosis,text,Age at Diagnosis,,"CRITICAL: This is a CALCULATED field. DO NOT extract from clinical notes.

CALCULATION FORMULA:
1. Get date_of_birth from patient_demographics.csv or extraction results
2. Get diagnosis_date from extraction results
3. Calculate: age = FLOOR((diagnosis_date - date_of_birth) / 365.25)

Return ONLY the integer number of years (e.g., '13' not '13 years').

DO NOT extract phrases from clinical notes like:
- '15-year-old girl'
- 'patient is 15 years old'
- 'a 15 year old female'

These phrases may refer to age at surgery/encounter, NOT age at diagnosis.

If date_of_birth or diagnosis_date unavailable, return 'Unable to calculate'."
```

## Expected Phase 3a_v2 Results

With `patient_demographics.csv` provided:

| Variable | Phase 3a | Phase 3a_v2 Expected | Change |
|----------|----------|---------------------|--------|
| date_of_birth | Unavailable | 2005-05-13 | ✅ FIXED |
| patient_gender | Female | Female | ✅ Maintained |
| race | Unavailable | White | ✅ FIXED |
| ethnicity | Unavailable | Not Hispanic or Latino | ✅ FIXED |
| age_at_diagnosis | 15 years | 13 | ✅ FIXED |
| diagnosis_date | 2018-05-28 | 2018-06-04 | ⚠️ Needs clarification |

**Expected Accuracy**: 95-100% (15-16/16 correct)

## Next Steps

1. ✅ Create `patient_demographics.csv` (COMPLETE)
2. ⏳ Update `variables.csv` with Athena-first priority
3. ⏳ Clarify `diagnosis_date` definition (pathology vs surgery)
4. ⏳ Upload Phase 3a_v2 to BRIM with 3 files:
   - `variables.csv` (updated)
   - `decisions.csv` (unchanged)
   - `patient_demographics.csv` (NEW)
   - `project.csv` (reuse from Phase 3a)
5. ⏳ Run Phase 3a_v2 extraction (Pilot 7)
6. ⏳ Validate results (expect 95%+ accuracy)

## Key Lessons

1. **Always query Athena first** for structured data before assuming text extraction needed
2. **Pre-populate CSVs** with Athena data for best performance and accuracy
3. **Block text extraction** explicitly for calculated fields (age_at_diagnosis)
4. **Validate gold standards** against authoritative sources (Athena) before assuming failures
5. **Understand temporal context** - narrative text may refer to different time points (surgery vs diagnosis)
