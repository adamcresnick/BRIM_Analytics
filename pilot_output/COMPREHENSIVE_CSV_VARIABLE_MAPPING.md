# Comprehensive CSV Variable Mapping & Extraction Source Analysis

**Date:** October 3, 2025  
**Patient:** C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Purpose:** Map ALL gold standard CSV fields to optimal extraction sources

---

## Executive Summary

### Gold Standard CSV Structure (18 tables):
1. **demographics** - Patient-level data
2. **diagnosis** - Diagnosis events (initial + progressions)
3. **encounters** - Follow-up visits
4. **treatments** - Surgery, chemo, radiation per event
5. **molecular_characterization** - Molecular markers
6. **molecular_tests_performed** - Testing details
7. **conditions_predispositions** - Symptoms and conditions
8. **concomitant_medications** - All medications
9. **family_cancer_history** - Family history
10. **hydrocephalus_details** - Hydrocephalus management
11. **imaging_clinical_related** - Imaging findings
12. **measurements** - Tumor measurements
13. **survival** - Survival status
14. **additional_fields** - Custom fields
15. **braf_alteration_details** - BRAF-specific details
16. **ophthalmology_functional_asses** - Visual assessments
17. **data_dictionary** - Field definitions
18. **data_dictionary_custom_forms** - Custom form definitions

---

## PATIENT C1277724: Gold Standard Values

### Demographics Table
```csv
research_id,legal_sex,race,ethnicity
C1277724,Female,White,Not Hispanic or Latino
```

### Diagnosis Table (3 events)
```csv
Event 1 (ET_FWYP9TY0): Initial CNS Tumor at age 4763 days (13.0 years)
- cns_integrated_diagnosis: Pilocytic astrocytoma
- who_grade: 1
- tumor_location: Cerebellum/Posterior Fossa
- metastasis: Yes (Leptomeningeal, Spine)
- shunt_required: Endoscopic Third Ventriculostomy (ETV) Shunt

Event 2 (ET_94NK0H3X): Progressive at age 5095 days (13.9 years)
- cns_integrated_diagnosis: Pilocytic astrocytoma
- who_grade: 1
- tumor_location: Cerebellum/Posterior Fossa
- site_of_progression: Local
- metastasis: No

Event 3 (ET_FRRCB155): Progressive at age 5780 days (15.8 years)
- cns_integrated_diagnosis: Pilocytic astrocytoma
- who_grade: 1
- tumor_location: Cerebellum/Posterior Fossa, Brain Stem-Midbrain/Tectum, Temporal Lobe
- site_of_progression: Local
- metastasis: No
```

### Treatments Table (3 events)
```csv
Event 1 (ET_FWYP9TY0): age_at_surgery=4763
- surgery: Yes
- extent_of_tumor_resection: Partial resection
- specimen_collection_origin: Initial CNS Tumor Surgery
- chemotherapy: No
- radiation: No

Event 2 (ET_94NK0H3X): age_at_chemo_start=5130
- surgery: No
- chemotherapy: Yes
- chemotherapy_agents: vinblastine;bevacizumab
- age_at_chemo_start: 5130 (14.0 years)
- age_at_chemo_stop: 5492 (15.0 years)
- radiation: No

Event 3 (ET_FRRCB155): age_at_surgery=5780, age_at_chemo_start=5873
- surgery: Yes
- extent_of_tumor_resection: Partial resection
- specimen_collection_origin: Progressive surgery
- chemotherapy: Yes
- chemotherapy_agents: selumetinib
- age_at_chemo_start: 5873 (16.0 years)
- age_at_chemo_stop: 7049 (19.3 years)
- radiation: No
```

### Molecular Characterization Table
```csv
research_id,mutation
C1277724,KIAA1549-BRAF fusion  (appears at ages 4763, 5780)
```

### Molecular Tests Performed Table
```csv
Event 1: age_at_molecular_testing=4763
- molecular_tests: Fusion Panel;Somatic Tumor Panel
- molecular_test_results: Not Applicable

Event 2: age_at_molecular_testing=5780
- molecular_tests: Fusion Panel;Somatic Tumor Panel
- molecular_test_results: Not Applicable
```

---

## COMPREHENSIVE VARIABLE MAPPING

### 🟢 CATEGORY 1: Patient Demographics (ONE_PER_PATIENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **research_id** | C1277724 | N/A (Epic MRN) | N/A | Manual mapping | N/A | ⚠️ MANUAL |
| **legal_sex** | Female | Patient.gender | patient.gender | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **race** | White | Patient.extension | patient_extension | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **ethnicity** | Not Hispanic or Latino | Patient.extension | patient_extension | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **date_of_birth** | ~2005-05-13 (calculated) | Patient.birthDate | patient.birth_date | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |

**Source Priority:**
1. **STRUCTURED extraction** from Patient resource (100% accurate)
2. NO narrative fallback needed - all fields fully structured

**Current Coverage:** 2/4 extracted (research_id is manual, race/ethnicity TODO)

---

### 🟡 CATEGORY 2: Diagnosis Information (PER_EVENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **event_id** | ET_FWYP9TY0, ET_94NK0H3X, ET_FRRCB155 | N/A | N/A | Generated identifier | N/A | ⚠️ GENERATED |
| **age_at_event_days** | 4763, 5095, 5780 | Calculated | Calculated | DOB + event date | 2 | ⏳ TODO |
| **clinical_status_at_event** | Alive | Patient.deceased[Boolean] | patient.deceased | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **event_type** | Initial CNS Tumor, Progressive | Manual classification | N/A | Timeline analysis | 3 | ⚠️ COMPLEX |
| **cns_integrated_diagnosis** | Pilocytic astrocytoma | Condition.code.text | problem_list_diagnoses | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **who_grade** | 1 (Grade I) | Condition.stage OR narrative | Condition OR pathology | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **tumor_location** | Cerebellum/Posterior Fossa | Condition.bodySite OR narrative | Condition OR radiology | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **metastasis** | Yes/No | Condition with metastasis codes | condition OR notes | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **metastasis_location** | Leptomeningeal, Spine | Condition.bodySite OR narrative | condition OR radiology | 🔴 **NARRATIVE** | 3 | ❌ BRIM |
| **site_of_progression** | Local | Narrative only | notes | 🔴 **NARRATIVE** | 3 | ❌ BRIM |
| **autopsy_performed** | Not Applicable | DocumentReference type | N/A | Document search | 3 | ❌ BRIM |
| **cause_of_death** | Not Applicable | Patient.deceased OR narrative | patient OR notes | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **tumor_or_molecular_tests_performed** | Whole Genome Sequencing, Specific gene mutation | DiagnosticReport OR Observation | molecular_tests OR observation | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **shunt_required** | Endoscopic Third Ventriculostomy | Procedure (CPT 62201) | procedure | ✅ **STRUCTURED** | 1 | ⏳ TODO |

**Source Priority:**
1. **STRUCTURED** for diagnosis name, grade (if coded), testing types
2. **HYBRID** for tumor location (Condition.bodySite + narrative details)
3. **NARRATIVE** for progression sites, metastasis locations

**Current Coverage:** 1/14 extracted (cns_integrated_diagnosis only)

---

### 🔵 CATEGORY 3: Surgery/Procedures (PER_EVENT, MANY_PER_EVENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **surgery** | Yes/No (boolean) | Procedure.code | procedure | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **age_at_surgery** | 4763, 5780 (days) | Procedure.performedDateTime | procedure | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **extent_of_tumor_resection** | Partial resection | Operative note narrative | DocumentReference text | 🔴 **NARRATIVE** | 3 | ❌ BRIM |
| **specimen_collection_origin** | Initial CNS Tumor Surgery, Progressive surgery | Timeline context + narrative | Procedure + notes | 🟡 **HYBRID** | 2 | ❌ BRIM |

**Gold Standard Surgeries:**
- Event 1 (ET_FWYP9TY0): age 4763 days → **Partial resection** → Initial surgery
- Event 2 (ET_94NK0H3X): No surgery
- Event 3 (ET_FRRCB155): age 5780 days → **Partial resection** → Progressive surgery

**FHIR Extraction Results:**
```json
"surgeries": [
  {"date": "2018-05-28", "cpt_code": "61500", "type": "RESECTION"},  // Age 4763 days ✅
  {"date": "2018-05-28", "cpt_code": "61518", "type": "RESECTION"},  // Age 4763 days (same encounter)
  {"date": "2021-03-10", "cpt_code": "61510", "type": "RESECTION"},  // Age 5780 days ✅
  {"date": "2021-03-16", "cpt_code": "61524", "type": "RESECTION"}   // Age 5786 days (6 days later)
]
```

**Analysis:**
- ✅ Gold standard Event 1 (age 4763 = 2018-05-28) → MATCHED (2 CPT codes in same encounter)
- ✅ Gold standard Event 3 (age 5780 = 2021-03-10) → MATCHED (2 surgeries 6 days apart)
- ❌ **Extent of resection** (GTR/NTR/STR) → NARRATIVE ONLY (operative notes)
- ❌ **Specimen origin** (initial vs progressive) → Requires timeline analysis

**Source Priority:**
1. **STRUCTURED** for surgery dates, CPT codes, surgery occurrence
2. **NARRATIVE** for extent of resection (GTR/NTR/STR/biopsy)
3. **HYBRID** for specimen origin (structured dates + clinical context)

**Current Coverage:** Surgery dates extracted (4 procedures), extent/origin need BRIM

---

### 🟣 CATEGORY 4: Chemotherapy (PER_EVENT, MANY_PER_EVENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **chemotherapy** | Yes/No (boolean) | MedicationRequest | patient_medications | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **chemotherapy_type** | Protocol vs standard of care | Narrative OR CarePlan | notes | 🔴 **NARRATIVE** | 3 | ❌ BRIM |
| **protocol_name** | N/A, Not Applicable | CarePlan.title OR narrative | care_plan OR notes | 🔴 **NARRATIVE** | 3 | ❌ BRIM |
| **chemotherapy_agents** | vinblastine;bevacizumab, selumetinib | MedicationRequest.medication | patient_medications | ✅ **STRUCTURED** | 1 | ⚠️ PARTIAL |
| **age_at_chemo_start** | 5130, 5873 (days) | MedicationRequest.authoredOn | patient_medications.authored_on | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **age_at_chemo_stop** | 5492, 7049 (days) | MedicationRequest.status + last dose | patient_medications | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **autologous_stem_cell_transplant** | No | Procedure (CPT codes) | procedure | ✅ **STRUCTURED** | 1 | ⏳ TODO |

**Gold Standard Medications:**
- Event 2: **vinblastine** + **bevacizumab** (ages 5130-5492 days)
- Event 3: **selumetinib** (ages 5873-7049 days)

**FHIR Extraction Results:**
```json
"treatments": [
  {"medication": "bevacizumab", "start_date": "2019-07-02", ...},  // 48 records
  // Missing: vinblastine, selumetinib
]
```

**Problem:** Filter too narrow!
```python
# CURRENT (WRONG):
WHERE (
    LOWER(medication_name) LIKE '%temozolomide%'
    OR LOWER(medication_name) LIKE '%bevacizumab%'
    OR LOWER(medication_name) LIKE '%chemotherapy%'
)

# NEEDED (CORRECT):
CHEMO_KEYWORDS = [
    'temozolomide', 'bevacizumab', 
    'vinblastine', 'vincristine',  # ← MISSING
    'selumetinib', 'koselugo',     # ← MISSING
    'carboplatin', 'cisplatin',
    'lomustine', 'cyclophosphamide', 'etoposide',
    'dabrafenib', 'trametinib',
    # ... more
]
```

**Source Priority:**
1. **STRUCTURED** for medication names, start dates, stop dates (from patient_medications view)
2. **NARRATIVE** for protocol names, treatment type classification

**Current Coverage:** 1/3 medications extracted (bevacizumab only, missing vinblastine + selumetinib)

---

### 🟠 CATEGORY 5: Radiation Therapy (PER_EVENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **radiation** | No | Procedure (CPT 77xxx) | procedure | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **radiation_type** | Not Applicable | Procedure.code OR narrative | procedure OR notes | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **radiation_site** | Not Applicable | Procedure.bodySite OR narrative | procedure OR notes | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **total_radiation_dose** | Not Applicable | Observation (radiation dose) | observation OR notes | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **age_at_radiation_start** | Not Applicable | Procedure.performedDateTime | procedure | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **age_at_radiation_stop** | Not Applicable | Procedure.performedPeriod | procedure | ✅ **STRUCTURED** | 1 | ⏳ TODO |

**Gold Standard:** Patient did NOT receive radiation

**FHIR Extraction Result:**
```json
"radiation_therapy": false  // ✅ CORRECT
```

**Source Priority:**
1. **STRUCTURED** for radiation occurrence (CPT codes 77xxx), dates
2. **HYBRID** for radiation type, site, dose (Procedure.code + narrative details)

**Current Coverage:** Boolean extracted correctly, details would need BRIM if radiation present

---

### 🔴 CATEGORY 6: Molecular Testing (PER_EVENT, ONE_PER_PATIENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **mutation** | KIAA1549-BRAF fusion | Observation.valueString | observation | ✅ **STRUCTURED** | 1 | ✅ EXTRACTED |
| **age_at_molecular_testing** | 4763, 5780 (days) | Observation.effectiveDateTime | observation | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **molecular_tests** | Fusion Panel, Somatic Tumor Panel | DiagnosticReport.code OR Observation.code | molecular_tests OR observation | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **molecular_test_results** | Not Applicable | DiagnosticReport.conclusion OR Observation.valueString | molecular_test_results OR observation | ✅ **STRUCTURED** | 1 | ⏳ TODO |

**Gold Standard Molecular Markers:**
- **BRAF:** KIAA1549-BRAF fusion (ages 4763, 5780)
- **IDH:** Not mentioned (assume wildtype)
- **MGMT:** Not mentioned (assume unknown/not tested)

**FHIR Extraction Result:**
```json
"molecular_markers": {
  "BRAF": "Next generation sequencing (NGS) analysis... KIAA1549-BRAF fusion..."
}
```

**Analysis:**
- ✅ BRAF fusion extracted from Observation.valueString
- ❌ IDH status not explicitly stated (should infer "wildtype" from BRAF-only finding)
- ❌ MGMT status not tested (should be "unknown")
- ❌ Age at testing not extracted (need Observation.effectiveDateTime)

**Source Priority:**
1. **STRUCTURED** for molecular marker results (Observation.valueString from molecular_tests view)
2. **STRUCTURED** for test dates (Observation.effectiveDateTime)
3. **NARRATIVE** for test interpretation (if Observation.valueString is coded, need pathology report text)

**Current Coverage:** BRAF fusion extracted, ages/test types need extraction, IDH/MGMT need logic

---

### 🟤 CATEGORY 7: Follow-up Encounters (MANY_PER_PATIENT)

| CSV Field | Gold Standard Value | FHIR Source | Athena Table | Extraction Method | Priority | Status |
|-----------|--------------------|--------------||---------------|-------------------|----------|--------|
| **age_at_encounter** | 4931, 5130, 5228... (days) | Encounter.period.start | encounter | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **clinical_status** | Alive | Patient.deceased | patient | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **follow_up_visit_status** | Visit Completed | Encounter.status | encounter | ✅ **STRUCTURED** | 1 | ⏳ TODO |
| **update_which_visit** | 6 Month Update, 12 Month Update | Calculated from dates | Calculated | 🟡 **HYBRID** | 2 | ⏳ TODO |
| **tumor_status** | Stable Disease, Change in tumor status | Narrative (oncology note) | notes | 🔴 **NARRATIVE** | 3 | ❌ BRIM |

**Gold Standard Encounters:**
- 6 follow-up encounters tracked (ages 4931-6233 days)
- Tumor status changes: Stable → Change → Stable → Stable → Change → Stable

**Source Priority:**
1. **STRUCTURED** for encounter dates, status, clinical status
2. **HYBRID** for visit type (6mo/12mo calculated from diagnosis date)
3. **NARRATIVE** for tumor status assessment (oncology notes)

**Current Coverage:** None extracted (encounter table not queried yet)

---

### ⚪ CATEGORY 8: Additional Tables (COMPLEX/CUSTOM)

#### Conditions/Predispositions Table
| CSV Field | Gold Standard Value | Source | Priority | Status |
|-----------|--------------------|--------------||--------|
| **condition_type** | Emesis, Headaches, Hydrocephalus, Posterior fossa syndrome, etc. | Condition resources OR clinical notes | 🟡 HYBRID | ❌ BRIM |
| **age_at_condition** | Event-specific ages | Condition.onsetDateTime OR note date | ✅ STRUCTURED | ⏳ TODO |

**Gold Standard Conditions:**
- Event 1 (age 4763): Behavior/Mood disorder, Emesis, Headaches, Hydrocephalus, Posterior fossa syndrome
- Event 2 (age 5095): Emesis, Focal neurological deficit, Posterior fossa syndrome, Visual deficit
- Event 3 (age 5780): None documented

#### Concomitant Medications Table
| CSV Field | Source | Priority | Status |
|-----------|--------|----------|--------|
| **medication_name** | patient_medications | ✅ STRUCTURED | ⏳ TODO |
| **age_at_medication_start** | patient_medications.authored_on | ✅ STRUCTURED | ⏳ TODO |

#### Hydrocephalus Details Table
| CSV Field | Gold Standard Value | Source | Priority | Status |
|-----------|--------------------|--------------||--------|
| **shunt_details** | Endoscopic Third Ventriculostomy (ETV) Shunt | Procedure (CPT 62201) | ✅ STRUCTURED | ⏳ TODO |

#### Imaging Clinical Related Table
| CSV Field | Source | Priority | Status |
|-----------|--------|----------|--------|
| **imaging_findings** | DiagnosticReport (radiology) | 🔴 NARRATIVE | ❌ BRIM |
| **age_at_imaging** | DiagnosticReport.effectiveDateTime | ✅ STRUCTURED | ⏳ TODO |

#### Measurements Table
| CSV Field | Source | Priority | Status |
|-----------|--------|----------|--------|
| **tumor_measurements** | DiagnosticReport text (radiology) | 🔴 NARRATIVE | ❌ BRIM |

#### Survival Table
| CSV Field | Source | Priority | Status |
|-----------|--------|----------|--------|
| **last_known_status** | Patient.deceased | ✅ STRUCTURED | ⏳ TODO |
| **age_at_last_contact** | Latest Encounter.period.start | ✅ STRUCTURED | ⏳ TODO |

---

## EXTRACTION SOURCE SUMMARY

### ✅ FULLY STRUCTURED (Query Athena directly)

| Variable Category | Fields | Athena Source | Status |
|-------------------|--------|---------------|--------|
| **Demographics** | gender, DOB | patient | ✅ EXTRACTED |
| **Diagnosis Name** | cns_integrated_diagnosis | problem_list_diagnoses | ✅ EXTRACTED |
| **Surgery Dates** | age_at_surgery | procedure.performed_date_time | ✅ EXTRACTED |
| **Surgery Boolean** | surgery (yes/no) | procedure (COUNT > 0) | ⏳ TODO |
| **Chemotherapy Agents** | chemotherapy_agents | patient_medications | ⚠️ PARTIAL (need expanded filter) |
| **Chemo Dates** | age_at_chemo_start, age_at_chemo_stop | patient_medications.authored_on | ✅ START, ⏳ STOP |
| **Radiation Boolean** | radiation (yes/no) | procedure (CPT 77xxx) | ✅ EXTRACTED |
| **Molecular Markers** | BRAF fusion | observation.value_string | ✅ EXTRACTED |
| **Molecular Test Dates** | age_at_molecular_testing | observation.effective_datetime | ⏳ TODO |
| **Encounter Dates** | age_at_encounter | encounter.period_start | ⏳ TODO |
| **Clinical Status** | Alive/Deceased | patient.deceased | ⏳ TODO |

**Count:** 11 variable categories, 7 extracted, 4 TODO

---

### 🟡 HYBRID (Structured + Narrative)

| Variable Category | Structured Component | Narrative Component | Status |
|-------------------|---------------------|---------------------|--------|
| **WHO Grade** | Condition.stage (if coded) | Pathology report | ⏳ TODO |
| **Tumor Location** | Condition.bodySite, Procedure.bodySite | Radiology, pathology, op notes | ⏳ TODO |
| **Specimen Origin** | Surgery date timeline | Clinical context (initial vs progressive) | ❌ BRIM |
| **Metastasis** | Condition with metastasis codes | Radiology reports, clinical notes | ❌ BRIM |
| **Radiation Type** | Procedure.code (CPT codes) | Radiation oncology notes | ⏳ TODO |
| **Test Interpretation** | Observation.interpretation | Pathology report conclusions | ⏳ TODO |

**Count:** 6 variable categories, 0 extracted, 3 TODO, 3 BRIM

---

### 🔴 NARRATIVE ONLY (BRIM extraction required)

| Variable Category | Why Narrative | BRIM Variable | Status |
|-------------------|---------------|---------------|--------|
| **Extent of Resection** | Surgeon's assessment only | extent_of_resection | ❌ BRIM |
| **Site of Progression** | Radiologist interpretation | N/A | ❌ BRIM |
| **Metastasis Locations** | Radiology descriptions | metastasis_location | ❌ BRIM |
| **Tumor Status** | Oncologist assessment | tumor_status | ❌ BRIM |
| **Protocol Name** | Treatment plan text | protocol_name | ❌ BRIM |
| **Chemotherapy Type** | Protocol vs standard text | chemotherapy_type | ❌ BRIM |
| **Symptoms** | Clinical note HPI sections | conditions_predispositions | ❌ BRIM |
| **Imaging Findings** | Radiology report impressions | imaging_findings | ❌ BRIM |
| **Tumor Measurements** | Radiology report bodies | measurements | ❌ BRIM |

**Count:** 9 variable categories, all require BRIM

---

## PRIORITIZED ACTION PLAN

### PHASE 1: Maximize Structured Extraction ✅ (DONE)

**Completed Additions:**
1. ✅ patient_gender (Patient.gender)
2. ✅ date_of_birth (Patient.birthDate)
3. ✅ primary_diagnosis (problem_list_diagnoses.diagnosis_name)
4. ✅ radiation_therapy (Procedure CPT 77xxx boolean)

**Before:** 4/26 fields extracted (15%)  
**After Phase 1:** 7/26 fields extracted (27%)

---

### PHASE 2: Expand Medication Filter 🔴 (CRITICAL)

**Problem:** Only extracting bevacizumab, missing vinblastine + selumetinib

**Fix:** Expand `extract_treatment_start_dates()` filter
```python
CHEMO_KEYWORDS = [
    # Current
    'temozolomide', 'temodar', 'tmz',
    'bevacizumab', 'avastin',
    
    # ADD (gold standard has these)
    'vinblastine', 'velban',         # ← CRITICAL
    'vincristine', 'oncovin',
    'selumetinib', 'koselugo',       # ← CRITICAL
    
    # ADD (common pediatric glioma chemo)
    'carboplatin', 'paraplatin',
    'cisplatin', 'platinol',
    'lomustine', 'ccnu', 'ceenu',
    'cyclophosphamide', 'cytoxan',
    'etoposide', 'vepesid',
    'irinotecan', 'camptosar',
    'procarbazine', 'matulane',
    
    # ADD (targeted therapies)
    'dabrafenib', 'tafinlar',
    'trametinib', 'mekinist',
]
```

**Expected:** Extract all 3 agents (vinblastine, bevacizumab, selumetinib)

**Time:** 10 minutes

---

### PHASE 3: Add Remaining Structured Fields ⏳

**6 Additional Extraction Methods Needed:**

1. **extract_race_ethnicity()** - Patient.extension table
2. **extract_molecular_test_details()** - molecular_tests table
3. **extract_encounter_dates()** - encounter table
4. **extract_clinical_status()** - Patient.deceased field
5. **extract_shunt_procedures()** - Procedure CPT 62201, 62223
6. **extract_chemotherapy_stop_dates()** - patient_medications.end_date OR last dose

**Expected:** 13/26 fields extracted (50%)

**Time:** 30-40 minutes

---

### PHASE 4: Add CPT/Procedure Classification Logic ⏳

**Surgery Type Classification:**
```python
def classify_surgery_type(cpt_code):
    BIOPSY_CPTS = ['61304', '61305', '61312', '61313', '61314', '61315']
    RESECTION_CPTS = ['61500', '61510', '61518', '61519', '61520', '61521', '61524', '61526', '61540']
    SHUNT_CPTS = ['62201', '62223', '62220', '62230']
    
    if cpt_code in BIOPSY_CPTS:
        return 'BIOPSY'
    elif cpt_code in RESECTION_CPTS:
        return 'RESECTION'
    elif cpt_code in SHUNT_CPTS:
        return 'SHUNT'
    else:
        return 'OTHER'
```

**Add to surgeries output:**
```json
{
  "date": "2018-05-28",
  "cpt_code": "61500",
  "surgery_type": "RESECTION",  // ← ADD
  "body_site": "Cerebellum"     // ← ADD (from Procedure.bodySite)
}
```

**Expected:** 15/26 fields extracted (58%)

**Time:** 15 minutes

---

### PHASE 5: Update BRIM Variables with STRUCTURED Priority 📋

**7 Variables Need Priority Instructions:**

1. **diagnosis_date** - "PRIORITY: Check STRUCTURED_diagnosis_date first"
2. **primary_diagnosis** - "PRIORITY: Check STRUCTURED_primary_diagnosis first"
3. **surgery_date** - "PRIORITY: Check STRUCTURED_surgeries first"
4. **surgery_type** - "PRIORITY: Check STRUCTURED_surgeries.surgery_type first"
5. **chemotherapy_agent** - "PRIORITY: Check STRUCTURED_treatments first"
6. **idh_mutation** - "PRIORITY: Check STRUCTURED_molecular_markers, if BRAF-only → 'wildtype'"
7. **radiation_therapy** - "PRIORITY: Check STRUCTURED_radiation_therapy boolean first"

**Example Enhanced Instruction:**
```csv
chemotherapy_agent,"PRIORITY 1: Check NOTE_ID='STRUCTURED_treatments' for pre-extracted medication names.
PRIORITY 2: Search MedicationRequest, MedicationAdministration FHIR resources.
PRIORITY 3: Search clinical text for drug names.

Extract each drug name separately. Include: temozolomide, vincristine, vinblastine, 
bevacizumab, selumetinib, carboplatin, cisplatin, lomustine, cyclophosphamide, etoposide.
Return generic or brand names."
```

**Time:** 20 minutes

---

### PHASE 6: Validate Enhanced Extraction 🧪

**Test Command:**
```bash
python3 scripts/extract_structured_data.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --output pilot_output/structured_data_phase_2_complete.json
```

**Expected Output:**
```json
{
  "patient_gender": "female",
  "date_of_birth": "2005-05-13",
  "race": "White",                           // ← NEW
  "ethnicity": "Not Hispanic or Latino",     // ← NEW
  
  "primary_diagnosis": "Pilocytic astrocytoma of cerebellum",
  "diagnosis_date": "2018-06-04",
  "who_grade": null,  // Try Condition.stage, likely null
  
  "surgeries": [
    {
      "date": "2018-05-28",
      "cpt_code": "61500",
      "surgery_type": "RESECTION",           // ← NEW
      "body_site": "Cerebellum",             // ← NEW
      "description": "..."
    },
    // ... 3 more
  ],
  
  "radiation_therapy": false,
  
  "molecular_markers": {
    "BRAF": "KIAA1549-BRAF fusion...",
    "test_dates": [                          // ← NEW
      {"marker": "BRAF", "age_days": 4763},
      {"marker": "BRAF", "age_days": 5780}
    ]
  },
  
  "treatments": [
    {"medication": "vinblastine", ...},      // ← NEW
    {"medication": "bevacizumab", ...},      // ✅ Already have
    {"medication": "selumetinib", ...}       // ← NEW
  ],
  
  "encounters": [                            // ← NEW
    {"age_days": 4931, "status": "finished", ...},
    // ... more
  ],
  
  "shunt_procedures": [                      // ← NEW
    {"date": "2018-05-28", "type": "ETV", "cpt_code": "62201"}
  ]
}
```

**Validation:**
- ✅ All 3 chemotherapy agents present (vinblastine, bevacizumab, selumetinib)
- ✅ Surgery types classified correctly (all RESECTION)
- ✅ Shunt procedure identified (ETV at age 4763)
- ✅ 15/26 fields extracted from structured sources (58%)

**Time:** 5 minutes

---

## COVERAGE PROJECTION

### Current Status (After Phase 1):
- **STRUCTURED extraction:** 7/26 fields (27%)
- **BRIM variables defined:** 14 variables
- **STRUCTURED priority instructions:** 0 variables

### After All Phases Complete:
- **STRUCTURED extraction:** 15/26 fields (58%)
- **BRIM variables defined:** 14 variables
- **STRUCTURED priority instructions:** 7 variables (50%)

### Expected Iteration 2 Accuracy:
- **Structured fields:** 100% accuracy (direct database queries)
- **BRIM with STRUCTURED priority:** 85-95% accuracy (ground truth anchors)
- **BRIM narrative-only:** 75-85% accuracy (LLM interpretation)
- **Overall:** **85-90% accuracy** (target achieved)

---

## KEY INSIGHTS

### 1. **Medication Filter Gap is Critical**
- Gold standard has 3 agents: vinblastine, bevacizumab, selumetinib
- We currently extract only bevacizumab (33% recall)
- **Impact:** Chemotherapy variables failing (critical clinical data)
- **Fix:** Expand keyword filter (10 minutes)
- **Priority:** 🔴 HIGHEST

### 2. **Structured Data Coverage Better Than Expected**
- Can extract 58% of gold standard fields from FHIR resources
- Demographics, dates, medications, procedures mostly structured
- Only extent of resection, tumor measurements truly narrative-only

### 3. **Race/Ethnicity in Patient Extensions**
- Not in main Patient table
- Need to query patient_extension table (US Core profiles)
- Fields: race.text, race.coding, ethnicity.text, ethnicity.coding

### 4. **Event Timeline Requires Assembly**
- Gold standard organizes by events (ET_FWYP9TY0, ET_94NK0H3X, ET_FRRCB155)
- FHIR has individual resources with dates
- Need to cluster by date ranges to create events
- **Example:** 2018-05-28 surgery + 2018-06-04 diagnosis → Event 1 (Initial CNS Tumor)

### 5. **Surgery Count Semantics Matter**
- Gold standard: 2 surgeries = 2 ENCOUNTERS (4763 days, 5780 days)
- FHIR: 4 procedures = 4 CPT codes (2 on 2018-05-28, 2 on 2021-03)
- Need to GROUP BY encounter_id or date to match gold standard

### 6. **WHO Grade Likely Not Coded**
- Checked Condition.stage → likely null
- Pilocytic astrocytoma → Grade I (can hardcode by diagnosis)
- Better: Extract from pathology report text with BRIM

### 7. **BRAF-Only Finding Implies IDH Wildtype**
- Molecular testing found KIAA1549-BRAF fusion
- No IDH1/IDH2 mutations mentioned
- Pilocytic astrocytoma → IDH wildtype (biologically)
- **Logic:** If BRAF fusion present AND IDH not mentioned → return 'wildtype'

### 8. **MGMT Not Relevant for Pilocytic Astrocytoma**
- MGMT methylation is glioblastoma biomarker
- Not tested in low-grade gliomas
- Should return 'unknown' or 'not applicable'

---

## NEXT IMMEDIATE ACTIONS

1. **🔴 CRITICAL:** Expand chemotherapy filter (10 min)
2. **⏳ HIGH:** Implement Phase 3 structured extractions (30 min)
3. **📋 HIGH:** Update BRIM variables with STRUCTURED priority (20 min)
4. **✅ MEDIUM:** Test enhanced extraction (5 min)
5. **🧪 MEDIUM:** Generate iteration 2 CSVs and validate (15 min)

**Total Time to Iteration 2:** ~80 minutes

---

**Status:** Ready to proceed with Phase 2 (medication filter expansion)
