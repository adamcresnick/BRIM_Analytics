# Audiology Data Discovery Results

**Date**: 2025-10-18
**Database**: fhir_prd_db (CBTN Production)
**Purpose**: Identify audiology/hearing assessment data for brain tumor patients at risk for ototoxicity

---

## Executive Summary

**OUTSTANDING audiology data coverage** across **7 FHIR resource tables**, capturing assessments for **1,141+ unique patients**. The dataset includes:
- **20,622 observations** (hearing reception thresholds, audiogram frequencies, hearing aid status)
- **1,718 procedures** (audiometric screening, pure tone audiometry, speech audiometry)
- **1,825 service requests** (orders for hearing tests)
- **1,301 diagnostic reports** (completed audiology reports)
- **1,228 document references** (audiogram files, reports)
- **6,993 conditions** (hearing loss diagnoses with laterality and type)

**Critical Finding**: **825 "Ototoxicity Monitoring" conditions** across 259 patients + **99 "Ototoxic hearing loss of both ears" diagnoses** across 22 patients, indicating active platinum chemotherapy surveillance.

---

## Data Coverage by FHIR Table

### Table 1: Observation (RICHEST SOURCE)
- **Total Records**: 20,622
- **Unique Patients**: 1,141 ⭐ **Highest coverage**
- **Records with Numeric Values**: 20,622 (100% - likely decibel measurements)

**Top Observation Types**:

#### Symptoms & Screening
1. **"SYMPTOMS - HENT - EAR SYMPTOMS - HEARING LOSS"** (2,489 records, 202 patients)
2. **"HEARING RECEPTION THRESHOLD"** (2,377 records, 438 patients) - Speech audiometry
3. **"HEARING SCREEN RESULT"** (127 records, 98 patients)

#### Laterality & Type
4. **"HARD OF HEARING - LATERALITY"** (1,675 records, 142 patients) ⭐ **Captures left/right/bilateral**
5. **"HEARING LOSS TYPE"** (1,114 records, 97 patients) - Conductive vs sensorineural
6. **"SENSORINEURAL HEARING LOSS"** (960 records, 77 patients)

#### Hearing Aid Status
7. **"HEARING AID"** (782 records, 52 patients) ⭐ **Yes/No for requires hearing aid**
8. **"HEARING AID EAR"** (679 records, 46 patients) ⭐ **Left/Right/Bilateral**

#### Audiogram Frequencies (Pure Tone Thresholds)
9. **"LEFT EAR 2000 HZ"** (186 records, 128 patients)
10. **"RIGHT EAR 2000 HZ"** (186 records, 128 patients)
11. **"LEFT EAR 4000 HZ"** (186 records, 128 patients)
12. **"RIGHT EAR 4000 HZ"** (186 records, 128 patients)
13. **"LEFT EAR 1000 HZ"** (186 records, 128 patients)
14. **"RIGHT EAR 1000 HZ"** (186 records, 128 patients)
15. **"LEFT EAR 8000 HZ"** (72 records, 62 patients)
16. **"RIGHT EAR 8000 HZ"** (72 records, 62 patients)
17. **"LEFT EAR 6000 HZ"** (70 records, 60 patients)
18. **"RIGHT EAR 6000 HZ"** (71 records, 61 patients)

**Clinical Significance**: Full audiogram frequency spectrum captured (1000-8000 Hz), enabling:
- High-frequency hearing loss detection (cisplatin toxicity starts at 6000-8000 Hz)
- Bilateral comparison
- Serial monitoring for progression

---

### Table 2: Procedure
- **Total Procedures**: 1,718
- **Unique Patients**: 379
- **Completed Procedures**: 1,718 (100%)

**Top Procedure Types**:
1. **"AUDIOMETRIC SCREENING"** (788 procedures, 261 patients) - Most common
2. **"PURE TONE AUDIOMETRY, AIR"** (165 procedures, 76 patients) - Standard audiogram
3. **"SPEECH THRESHOLD AUDIOMETRY"** (158 procedures, 75 patients)
4. **"AUDIOMETRY, AIR & BONE"** (69 procedures, 37 patients) - Differentiates conductive vs sensorineural
5. **"COMPREHENSIVE HEARING TEST"** (60 procedures, 37 patients)
6. **"SPEECH AUDIOMETRY, COMPLETE"** (59 procedures, 36 patients)
7. **"SELECT PICTURE AUDIOMETRY"** (28 procedures, 23 patients) - Pediatric testing method
8. **"HEARING AID CHECK, ONE EAR"** (7 procedures, 4 patients)
9. **"HEARING AID CHECK, BOTH EARS"** (6 procedures, 4 patients)
10. **"ABR hearing test"** (1 procedure) - Auditory Brainstem Response (objective test)

---

### Table 3: ServiceRequest (Orders)
- **Total Orders**: 1,825
- **Unique Patients**: 428
- **Completed Orders**: 1,471 (81%)

**Clinical Significance**: High order volume indicates routine ototoxicity monitoring protocols

---

### Table 4: DiagnosticReport
- **Total Reports**: 1,301
- **Unique Patients**: 466
- **Final Reports**: 1,290 (99%)

---

### Table 5: DocumentReference (Binary Files)
- **Total Documents**: 1,228
- **Unique Patients**: 424

**Expected Content**: PDF audiograms, tympanometry plots, ABR waveforms

---

### Table 6: Condition (DIAGNOSES - KEY FOR GRADING)
- **Total Conditions**: 6,993
- **Unique Patients**: 521

**Top Condition Types**:

#### Sensorineural Hearing Loss (SNHL) - Most Common Type
1. **"Sensorineural hearing loss, bilateral"** (1,071 conditions, 148 patients)
2. **"SNHL of both ears"** (641 conditions, 51 patients)
3. **"SNHL"** (242 conditions, 21 patients)
4. **"Sensorineural hearing loss, unilateral"** (152 conditions, 40 patients)

#### Ototoxicity Monitoring & Ototoxic Hearing Loss
5. **"Ototoxicity Monitoring"** (825 conditions, 259 patients) ⚠️ **Active chemo surveillance**
6. **"Ototoxic hearing loss of both ears"** (99 conditions, 22 patients) ⚠️ **Confirmed platinum toxicity**

#### Unspecified / General
7. **"Unspecified hearing loss"** (663 conditions, 199 patients)
8. **"Hearing loss"** (254 conditions, 82 patients)

#### Conductive Hearing Loss
9. **"Conductive hearing loss, bilateral"** (177 conditions, 36 patients)
10. **"Conductive hearing loss, unilateral"** (63 conditions, 29 patients)

#### Mixed Type
11. **"Mixed conductive and sensorineural hearing loss of both ears"** (122 conditions, 4 patients)

#### Laterality Captured
12. **"Hearing loss, bilateral"** (102 conditions, 54 patients)
13. **"Bilateral hearing loss, unspecified type"** (96 conditions, 50 patients)
14. **"Hearing loss of right ear"** (57 conditions, 16 patients)
15. **"Hearing loss of left ear"** (50 conditions, 19 patients)

#### Severity
16. **"Deaf, bilateral"** (73 conditions, 1 patient) - Severe/profound loss

---

## Structured Data Fields Identified

Based on observation code_text patterns, the following structured fields ARE captured:

### ✅ Hearing Aid Status
- **Field**: `"DIAGNOSES/PROBLEMS - HENT - EAR PROBLEM - HEARING PROBLEM - HEARING AID"`
- **Values**: Binary presence/absence (782 observations, 52 patients)
- **Location**: observation table

### ✅ Hearing Aid Laterality
- **Field**: `"DIAGNOSES/PROBLEMS - HENT - EAR PROBLEM - HEARING PROBLEM - HEARING AID EAR"`
- **Values**: Left, Right, Bilateral (679 observations, 46 patients)
- **Location**: observation table

### ✅ Hearing Loss Type
- **Field**: `"DIAGNOSES/PROBLEMS - HENT - EAR PROBLEM - HEARING PROBLEM - HEARING LOSS TYPE"`
- **Values**: Sensorineural, Conductive, Mixed (1,114 observations, 97 patients)
- **Location**: observation table + condition table

### ✅ Laterality (General)
- **Field**: `"DIAGNOSES/PROBLEMS - HENT - EAR PROBLEM - HEARING PROBLEM - HARD OF HEARING - LATERALITY"`
- **Values**: Left, Right, Bilateral (1,675 observations, 142 patients)
- **Location**: observation table + condition table (in diagnosis text)

### ✅ Audiogram Thresholds (dB HL)
- **Fields**: `"LEFT EAR [frequency] HZ"`, `"RIGHT EAR [frequency] HZ"`
- **Frequencies**: 1000, 2000, 4000, 6000, 8000 Hz
- **Values**: Numeric decibel values (in value_quantity_value field)
- **Location**: observation table

### ⚠️ Degree of Hearing Loss (NEEDS INVESTIGATION)
- **Not found explicitly as "Grade I/II/III/IV" or "None"**
- **Likely calculated from**:
  - Audiogram thresholds (dB HL values)
  - Condition severity text
  - May need derivation: Mild (26-40 dB), Moderate (41-55 dB), Moderate-Severe (56-70 dB), Severe (71-90 dB), Profound (>90 dB)

### ⚠️ Ototoxicity Grading Scale (NEEDS INVESTIGATION)
- **Not found explicitly as "CTCAEv4.03", "CTCAEv5", "SIOP Boston", "Other"**
- **However**:
  - 825 "Ototoxicity Monitoring" conditions exist (indicating protocol-driven surveillance)
  - 99 "Ototoxic hearing loss" diagnoses (confirming platinum toxicity)
  - Scale may be:
    - Documented in encounter notes (not structured)
    - Calculated from audiograms using SIOP Boston or CTCAE criteria
    - Stored in diagnostic_report text

---

## What We Can Extract

### Confirmed Structured Data
1. ✅ **Requires hearing aid?** - Yes/No (from observation "HEARING AID")
2. ✅ **Hearing aid laterality** - Left/Right/Bilateral (from observation "HEARING AID EAR")
3. ✅ **Hearing loss type** - Sensorineural/Conductive/Mixed (from observation + condition)
4. ✅ **If unilateral, left or right?** - Left/Right/Bilateral (from condition diagnosis text + observation)
5. ✅ **Audiogram thresholds** - dB HL at 1000-8000 Hz (from observation numeric values)
6. ✅ **Ototoxicity diagnosis** - "Ototoxic hearing loss" present (from condition table)
7. ✅ **Ototoxicity monitoring status** - "Ototoxicity Monitoring" active (from condition table)

### Derivable Data (Calculation Required)
8. ⚙️ **Degree of hearing loss** - Grade I/II/III/IV/None
   - **Method**: Calculate pure tone average (PTA) from audiogram thresholds
   - **Formula**: PTA = Average of 500, 1000, 2000, 4000 Hz thresholds
   - **Grading**:
     - None: PTA 0-25 dB
     - Grade I (Mild): PTA 26-40 dB
     - Grade II (Moderate): PTA 41-55 dB
     - Grade III (Moderate-Severe): PTA 56-70 dB
     - Grade IV (Severe/Profound): PTA >70 dB

9. ⚙️ **Ototoxicity grading scale used** - CTCAEv4.03 / CTCAEv5 / SIOP Boston
   - **Possible locations**:
     - DiagnosticReport.text field (need to parse report narrative)
     - Encounter notes
     - May need manual annotation or NLP extraction

### Bilateral vs Unilateral (Already Captured)
10. ✅ **If yes to above, unilateral or bilateral?** - Already in laterality fields

---

## Sample Queries for Key Fields

### Query 1: Hearing Aid Requirements
```sql
SELECT
    patient_fhir_id,
    assessment_date,
    CASE
        WHEN code_text LIKE '%HEARING AID%' THEN 'Yes'
        ELSE 'No'
    END as requires_hearing_aid,
    CASE
        WHEN code_text LIKE '%HEARING AID EAR%' AND value_string LIKE '%Left%' THEN 'Left'
        WHEN code_text LIKE '%HEARING AID EAR%' AND value_string LIKE '%Right%' THEN 'Right'
        WHEN code_text LIKE '%HEARING AID EAR%' AND value_string LIKE '%Bilateral%' THEN 'Bilateral'
    END as hearing_aid_ear
FROM observation
WHERE code_text LIKE '%HEARING AID%';
```

### Query 2: Hearing Loss Laterality
```sql
SELECT
    patient_fhir_id,
    code_text as diagnosis,
    CASE
        WHEN code_text LIKE '%bilateral%' THEN 'Bilateral'
        WHEN code_text LIKE '%unilateral%' OR code_text LIKE '%left ear%' THEN 'Unilateral - Left'
        WHEN code_text LIKE '%right ear%' THEN 'Unilateral - Right'
    END as laterality
FROM condition
WHERE code_text LIKE '%hearing loss%';
```

### Query 3: Audiogram Thresholds (for Degree Calculation)
```sql
SELECT
    patient_fhir_id,
    assessment_date,
    CASE
        WHEN code_text LIKE '%LEFT EAR 1000 HZ%' THEN 'L_1000Hz'
        WHEN code_text LIKE '%RIGHT EAR 1000 HZ%' THEN 'R_1000Hz'
        -- ... etc for all frequencies
    END as frequency,
    value_quantity_value as threshold_dB
FROM observation
WHERE code_text LIKE '%EAR%HZ%'
ORDER BY patient_fhir_id, assessment_date, frequency;
```

---

## Recommended View Structure

### Proposed: `v_audiology_assessments`

**CTEs to Create**:
1. **hearing_aid_status** - Requires hearing aid? Yes/No + Laterality
2. **hearing_loss_diagnosis** - Type (SNHL/Conductive/Mixed) + Laterality from conditions
3. **audiogram_thresholds** - Frequency-specific dB values (wide format or pivoted)
4. **calculated_hearing_loss_grade** - Derive Grade I-IV from PTA calculation
5. **ototoxicity_conditions** - Flag patients with ototoxicity monitoring/diagnosis
6. **audiology_procedures** - Screening, comprehensive tests, ABR
7. **audiology_reports** - DiagnosticReport summaries
8. **audiology_documents** - Binary file references (audiogram PDFs)

**Main Fields**:
- record_fhir_id, patient_fhir_id, assessment_date
- assessment_category (audiogram, hearing_aid, diagnosis, screening, monitoring)
- requires_hearing_aid (Yes/No)
- hearing_aid_laterality (Left/Right/Bilateral)
- hearing_loss_type (Sensorineural/Conductive/Mixed/None)
- hearing_loss_laterality (Left/Right/Bilateral/None)
- degree_of_hearing_loss (Grade I/II/III/IV/None) - **CALCULATED**
- ototoxicity_monitoring_active (Yes/No)
- ototoxicity_confirmed (Yes/No)
- audiogram_frequencies (JSON or separate columns: L1000, R1000, L2000, R2000, etc.)
- ototoxicity_grading_scale (CTCAEv4.03/CTCAEv5/SIOP Boston/Other/Unknown) - **May need NLP**

---

## Next Steps

1. ✅ **Create v_audiology_assessments view** with all structured data
2. ⚙️ **Add PTA calculation logic** to derive hearing loss grades
3. 🔍 **Sample diagnostic_report text** to find ototoxicity grading scale mentions
4. 🔍 **Check encounter notes** for grading scale documentation
5. 📊 **Validate with audiology team** - Confirm field interpretations
6. 🧪 **Test queries** on sample patients with known hearing loss

---

## Clinical Significance

### Ototoxicity Surveillance
- **259 patients** with active "Ototoxicity Monitoring" conditions
- **22 patients** with confirmed ototoxic hearing loss
- High-frequency audiometry (6000-8000 Hz) captured for early detection

### Hearing Rehabilitation
- **52 patients** with documented hearing aid requirements
- **46 patients** with hearing aid laterality specified
- Hearing aid checks/fittings documented in procedures

### Platinum Chemotherapy Impact
- Sensorineural hearing loss predominates (expected with cisplatin/carboplatin)
- Bilateral involvement most common (systemic toxicity pattern)
- Serial audiograms enable trajectory analysis

---

## Files to Create

1. **AUDIOLOGY_EXPLORATORY_QUERIES.sql** - Comprehensive query set
2. **AUDIOLOGY_DATA_DISCOVERY_RESULTS.md** - This document
3. **ATHENA_VIEW_CREATION_QUERIES.sql** - Add Section 8: v_audiology_assessments
4. **AUDIOLOGY_ASSESSMENT_CLINICAL_GUIDE.md** - Interpretation guide for analysts

---

## Summary for User Question

**YES**, we can identify most of the fields you requested:

| Field | Status | Source |
|-------|--------|--------|
| Requires hearing aid? (Yes/No) | ✅ Direct | observation "HEARING AID" |
| Hearing aid laterality (Left/Right) | ✅ Direct | observation "HEARING AID EAR" |
| Degree of hearing loss (Grade I-IV) | ⚙️ Calculated | Derived from audiogram thresholds |
| Hearing loss laterality | ✅ Direct | condition diagnosis text + observation |
| Ototoxicity grading scale | ⚠️ Investigate | Possibly in diagnostic_report text or encounter notes |
| Bilateral vs Unilateral | ✅ Direct | condition diagnosis + observation laterality |

**Data Volume**:
- 1,141 patients with audiology data
- 20,622 observations (audiograms, symptoms, hearing aid status)
- 6,993 hearing loss diagnoses
- 825 ototoxicity monitoring records
