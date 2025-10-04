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

### Variables That Should Use Athena patient_access Table

**All 5 Demographics Variables**:
1. ✅ `patient_gender` → `patient_access.gender` (capitalize to match data dictionary)
2. ✅ `date_of_birth` → `patient_access.birth_date`
3. ✅ `race` → `patient_access.race`
4. ✅ `ethnicity` → `patient_access.ethnicity`
5. ✅ `age_at_diagnosis` → **CALCULATED** from `patient_access.birth_date` + `diagnosis_date`

### Approach: Pre-populate Demographics CSV

**File**: `pilot_output/brim_csvs_iteration_3c_phase3a_v2/patient_demographics.csv`

```csv
patient_fhir_id,gender,birth_date,race,ethnicity
e4BwD8ZYDBccepXcJ.Ilo3w3,Female,2005-05-13,White,Not Hispanic or Latino
```

**Mapping from Athena to BRIM**:
| Athena Column | Athena Value | BRIM Variable | BRIM Value | Transformation |
|---------------|--------------|---------------|------------|----------------|
| `gender` | female | `patient_gender` | Female | Capitalize first letter |
| `birth_date` | 2005-05-13 | `date_of_birth` | 2005-05-13 | Direct copy |
| `race` | White | `race` | White | Direct copy |
| `ethnicity` | Not Hispanic or Latino | `ethnicity` | Not Hispanic or Latino | Direct copy |
| (calculated) | - | `age_at_diagnosis` | 13 | Calculate from birth_date + diagnosis_date |

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

### Demographics Variables (5 total) - ALL from Athena

With `patient_demographics.csv` provided from Athena `patient_access` table:

| Variable | Phase 3a Result | Athena Source | Phase 3a_v2 Expected | Status |
|----------|----------------|---------------|---------------------|--------|
| patient_gender | Female | patient_access.gender="female" | Female | ✅ Maintained (was correct) |
| date_of_birth | Unavailable | patient_access.birth_date="2005-05-13" | 2005-05-13 | ✅ FIXED |
| race | Unavailable | patient_access.race="White" | White | ✅ FIXED |
| ethnicity | Unavailable | patient_access.ethnicity="Not Hispanic or Latino" | Not Hispanic or Latino | ✅ FIXED |
| age_at_diagnosis | 15 years | CALCULATED from birth_date + diagnosis_date | 13 | ✅ FIXED |

**Demographics Accuracy**: 
- Phase 3a: 20% (1/5) - Only gender was correct
- Phase 3a_v2: 100% (5/5) - All will use Athena data

### Other Variables (11 total)

| Variable | Phase 3a Result | Phase 3a_v2 Expected | Status |
|----------|----------------|---------------------|--------|
| primary_diagnosis | Pilocytic astrocytoma | Pilocytic astrocytoma | ✅ Maintained |
| diagnosis_date | 2018-05-28 | 2018-06-04 | ⚠️ Needs clarification |
| who_grade | Grade I | Grade I | ✅ Maintained |
| tumor_location | Cerebellum/Posterior Fossa | Cerebellum/Posterior Fossa | ✅ Maintained |
| idh_mutation | IDH wild-type | IDH wild-type | ✅ Maintained |
| mgmt_methylation | Not tested | Not tested | ✅ Maintained |
| braf_status | BRAF fusion | BRAF fusion | ✅ Maintained |
| surgery_date | 2018-05-28, 2021-03-10 | 2018-05-28, 2021-03-10 | ✅ Maintained |
| surgery_type | Tumor Resection | Tumor Resection | ✅ Maintained |
| surgery_extent | Partial Resection | Partial Resection | ✅ Maintained |
| surgery_location | Cerebellum/Posterior Fossa | Cerebellum/Posterior Fossa | ✅ Maintained |

**Overall Phase 3a_v2 Expected Accuracy**: 
- With demographics fixed: **94-100% (15-16/16 correct)**
- Demographics: 100% (5/5) ← **All from Athena**
- Diagnosis: 75-100% (3-4/4) ← diagnosis_date pending
- Molecular: 100% (3/3) ← Already perfect
- Surgery: 100% (4/4) ← Already perfect

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

## Key Insights: Why Athena Integration is Critical

### Phase 3a Demographics Performance Without Athena

| Variable | Result | Why It Failed |
|----------|--------|---------------|
| patient_gender | ✅ Female | FHIR Patient resource was accessible |
| date_of_birth | ❌ Unavailable | FHIR birthDate field empty or inaccessible |
| race | ❌ Unavailable | Not in FHIR Patient, only in Athena |
| ethnicity | ❌ Unavailable | Not in FHIR Patient, only in Athena |
| age_at_diagnosis | ❌ 15 years | Extracted from text (wrong surgery date) |

**Demographics Accuracy Without Athena**: 20% (1/5)

### Phase 3a_v2 Demographics Performance With Athena

| Variable | Expected Result | Why It Will Succeed |
|----------|----------------|---------------------|
| patient_gender | ✅ Female | Direct from patient_access.gender |
| date_of_birth | ✅ 2005-05-13 | Direct from patient_access.birth_date |
| race | ✅ White | Direct from patient_access.race |
| ethnicity | ✅ Not Hispanic or Latino | Direct from patient_access.ethnicity |
| age_at_diagnosis | ✅ 13 | Calculated from Athena birth_date |

**Demographics Accuracy With Athena**: 100% (5/5)

### The Athena Advantage

**Structured Data > Text Extraction**:
- Athena: Normalized, validated, single source of truth
- Text: Variable formats, temporal ambiguity, extraction errors

**Examples from Phase 3a**:
- `date_of_birth`: FHIR had no data → Athena has "2005-05-13"
- `race`: Not in FHIR → Athena has "White"
- `ethnicity`: Not in FHIR → Athena has "Not Hispanic or Latino"
- `age_at_diagnosis`: Text said "15 years" (wrong surgery) → Athena calculation gives "13 years"

## Key Lessons

1. **Always query Athena first** for structured data before assuming text extraction needed
2. **Pre-populate CSVs** with Athena data for best performance and accuracy
3. **ALL demographics should use Athena** - race, ethnicity, DOB, gender (not just DOB)
4. **Block text extraction** explicitly for calculated fields (age_at_diagnosis)
5. **Validate gold standards** against authoritative sources (Athena) before assuming failures
6. **Understand temporal context** - narrative text may refer to different time points (surgery vs diagnosis)
7. **80% accuracy boost** possible for demographics just by adding Athena integration (20% → 100%)
