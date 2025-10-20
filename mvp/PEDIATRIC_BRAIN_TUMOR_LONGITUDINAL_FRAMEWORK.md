# Pediatric Brain Tumor Longitudinal Natural History Framework

**Purpose**: Establish comprehensive timeline framework for pediatric brain tumor patients that captures the complete diagnostic and treatment arc, independent of any specific data model structure. This framework supports external control arm development for clinical trials and natural history studies.

**Date Created**: 2025-10-19
**Status**: Foundation Document - All downstream work builds from this framework

---

## 1. Clinical Context: Pediatric Low-Grade Glioma Natural History

### 1.1 Disease Overview
- **Example Disease**: Pilocytic Astrocytoma (WHO Grade 1)
- **Typical Patient Age**: Pediatric (ages 1-18 years)
- **Treatment Philosophy**: Surgery-first approach; avoid radiation in young children when possible
- **Prognosis**: 90-95% cure rate with complete resection
- **Surveillance Duration**: Many years (slow-growing tumors)

### 1.2 Standard Treatment Timeline Arc

```
DIAGNOSIS → SURGERY → OBSERVATION or SYSTEMIC THERAPY → SURVEILLANCE → LONG-TERM FOLLOW-UP
   |            |              |                            |                    |
Days 0-30   Days 0-60    Months 0-18               Months 3-60+         Years 5-15+
```

**Phase 1: Diagnostic Workup** (Days -30 to 0)
- Symptom presentation (headaches, vomiting, vision changes, ataxia)
- Initial imaging (MRI brain with/without contrast)
- Neurosurgical consultation
- Multidisciplinary tumor board discussion
- Ophthalmology assessment (visual acuity, visual fields)
- Pre-operative assessments

**Phase 2: Initial Surgical Intervention** (Days 0-7)
- Tumor resection (goal: gross total resection)
- Possible CSF diversion (EVD, shunt placement)
- Inpatient recovery
- Post-operative imaging (within 48-72 hours)
- Pathology diagnosis confirmation
- Molecular testing (BRAF status, IDH mutation, MGMT methylation)

**Phase 3: Treatment Decision** (Weeks 2-6)
- Oncology consultation
- Extent of resection assessment
- Decision: Observation vs Chemotherapy vs Radiation vs Targeted Therapy
  - **Complete resection + Grade 1** → Observation with surveillance imaging
  - **Incomplete resection or progression** → Chemotherapy (carboplatin/vincristine) or targeted therapy (MEK inhibitors for BRAF fusion)
  - **Older patients with residual disease** → Consider radiation therapy

**Phase 4: Active Treatment** (Months 0-18, if applicable)
- **Chemotherapy regimen**: Every 2-6 weeks for 12-18 months
- **Targeted therapy**: Daily oral MEK inhibitor (selumetinib) for variable duration
- **Radiation therapy**: 4-6 week course (avoided in children <10 years when possible)
- Supportive care (anti-emetics, growth factor support)
- Treatment-related toxicity monitoring

**Phase 5: Surveillance** (Months 3-60+)
- **MRI frequency**:
  - Post-surgery: Every 3-4 months (Year 1)
  - Year 2: Every 4-6 months
  - Years 3-5: Every 6-12 months
  - Years 5+: Annually
- Clinical assessments at each imaging timepoint
- Neurocognitive assessments
- Endocrine evaluations (pituitary function)
- Ophthalmology follow-up
- Quality of life assessments

**Phase 6: Long-Term Survivorship** (Years 5-15+)
- Annual MRI surveillance (many years for slow-growing tumors)
- Late effects monitoring (neurocognitive, endocrine, vision, hearing)
- Transition to adult care
- Second malignancy surveillance

---

## 2. External Control Arm Requirements for Clinical Trials

### 2.1 Regulatory Context (FDA 2024 Guidance)

**Why External Controls in Pediatric Oncology?**
- Rarity of pediatric brain tumors makes randomized trials infeasible
- Ethical concerns randomizing children to ineffective control arms
- Single-arm trials common; external controls provide comparative context
- Real-world data (RWD) from registries/EHRs increasingly accepted by FDA/EMA

**Key Requirements for External Control Arms**:
1. **Prospective study design** to avoid selection bias
2. **Sufficient baseline data** to ensure comparability of populations
3. **Consistent endpoint measurements** (PFS, OS, response rate)
4. **Robust statistical methodology** for comparative analysis
5. **High-quality patient-level longitudinal data**

### 2.2 Data Quality Standards

**Primary Endpoints (Time-to-Event)**:
- Overall Survival (OS)
- Event-Free Survival (EFS)
- Progression-Free Survival (PFS)

**Secondary Endpoints**:
- Objective Response Rate (ORR)
- Tumor growth rate
- Quality of life metrics
- Neurocognitive outcomes
- Treatment-related toxicities

**Required Data Elements**:
- Demographics (age, sex, race, ethnicity)
- Diagnosis details (histology, molecular features, tumor location)
- Baseline tumor measurements
- Treatment details (dates, agents, doses, toxicities)
- Imaging assessments with radiologist interpretations
- Follow-up dates and survival status
- Disease progression events with dates

**Data Completeness Thresholds**:
- Primary endpoints: 100% required
- Key baseline variables: >90% completeness
- Imaging assessments: >85% availability at protocol timepoints
- Molecular testing: Document availability rate (may be <100% for historical cohorts)

---

## 3. Comprehensive Patient Timeline Framework

### 3.1 Timeline Data Domains (Athena FHIR Structure)

The patient timeline is constructed by integrating data across **8 core domains**:

| **Domain** | **Athena Source** | **Key Variables** | **Temporal Anchors** |
|------------|-------------------|-------------------|----------------------|
| **1. Demographics** | Patient | Birth date, sex, race, ethnicity | `birth_date` (Day 0) |
| **2. Encounters** | Encounter | Appointment dates, visit types, service providers | `encounter_date`, `period_start`, `period_end` |
| **3. Diagnoses** | Condition | Diagnosis name, onset date, clinical status, ICD-10/SNOMED codes | `onset_date_time`, `recorded_date` |
| **4. Procedures** | Procedure | Surgeries, biopsies, CSF shunts, catheter placements | `procedure_date`, `performed_period_start` |
| **5. Imaging** | DiagnosticReport, Observation | MRI/CT scans, report conclusions, tumor measurements | `imaging_date`, `issued_date` |
| **6. Molecular Testing** | Observation (Lab) | BRAF fusion, IDH mutation, MGMT methylation, NGS panels | `test_date`, `specimen_collection_date` |
| **7. Medications** | MedicationRequest | Chemotherapy agents, targeted therapy, supportive meds | `medication_start_date`, `authored_on` |
| **8. Radiation Therapy** | CarePlan, Procedure | Treatment courses, appointments, dose, technique | `course_start_date`, `course_end_date`, `appointment_date` |

### 3.2 Temporal Anchor Hierarchy

**Primary Temporal Anchor**: `birth_date` (Day 0)

**Derived Age Calculations**:
```python
age_at_event_days = (event_date - birth_date).days
age_at_event_years = age_at_event_days / 365.25
```

**Key Milestone Dates** (Disease-Specific):
1. **Diagnosis Date** (`onset_date_time` for primary CNS tumor diagnosis)
2. **Surgery Date** (`procedure_date` for tumor resection)
3. **Treatment Start Date** (`medication_start_date` for chemotherapy/targeted therapy; `course_start_date` for radiation)
4. **Treatment End Date** (`medication_end_date`; `course_end_date`)
5. **Progression Date** (`onset_date_time` for recurrence/progression diagnosis)
6. **Surveillance Imaging Dates** (`imaging_date` for serial MRI scans)
7. **Last Follow-Up Date** (most recent `encounter_date`)
8. **Death Date** (if applicable, from `deceased_date_time`)

### 3.3 Timeline Construction Algorithm (Source-Agnostic)

**Step 1: Extract Birth Date**
```python
birth_date = query_patient_demographics(patient_id)['birth_date']
# Example: 2005-05-13
```

**Step 2: Identify Initial CNS Tumor Diagnosis**
```python
# Query all diagnoses for CNS tumor codes
diagnosis_records = query_diagnoses(patient_id,
    icd10_codes=['C71.*', 'D33.*', 'D43.*'],  # Malignant + benign CNS neoplasms
    snomed_codes=['126952004', '277507004', '25173007']  # CNS tumor, PA, recurrent neoplasm
)

# Filter to earliest diagnosis with "Pilocytic astrocytoma" or similar
initial_diagnosis = diagnosis_records.filter(
    clinical_status='Active',
    diagnosis_name__contains='astrocytoma'
).sort_by('onset_date_time').first()

diagnosis_date = initial_diagnosis['onset_date_time']  # Example: 2018-06-04
age_at_diagnosis_days = (diagnosis_date - birth_date).days  # 4770 days
age_at_diagnosis_years = age_at_diagnosis_days / 365.25  # 13.06 years
```

**Step 3: Identify Primary Tumor Resection Surgery**
```python
# Query procedures within 60 days after diagnosis
surgery_records = query_procedures(patient_id,
    procedure_codes=['61510', '61512', '61518'],  # CPT codes for craniotomy
    date_range=(diagnosis_date, diagnosis_date + timedelta(days=60))
)

primary_surgery = surgery_records.filter(
    procedure_name__contains='craniotomy'
).sort_by('procedure_date').first()

surgery_date = primary_surgery['procedure_date']  # Example: 2018-06-06
age_at_surgery_days = (surgery_date - birth_date).days  # 4772 days
```

**Step 4: Extract Imaging Timeline**
```python
# Query all MRI brain scans
imaging_timeline = query_imaging(patient_id,
    modality='MRI',
    body_site='Brain'
).sort_by('imaging_date')

# Categorize imaging by phase
pre_surgical_imaging = imaging_timeline.filter(
    imaging_date < surgery_date
)

post_surgical_imaging = imaging_timeline.filter(
    imaging_date >= surgery_date
)

# Calculate intervals between scans
for i, scan in enumerate(post_surgical_imaging):
    if i == 0:
        scan['days_since_surgery'] = (scan['imaging_date'] - surgery_date).days
    else:
        scan['days_since_prior_scan'] = (scan['imaging_date'] - post_surgical_imaging[i-1]['imaging_date']).days
```

**Step 5: Extract Molecular Testing Timeline**
```python
# Query molecular test results
molecular_tests = query_molecular_tests(patient_id).sort_by('test_date')

for test in molecular_tests:
    test['days_since_diagnosis'] = (test['test_date'] - diagnosis_date).days
    test['days_since_surgery'] = (test['test_date'] - surgery_date).days

# Example: BRAF fusion testing on surgical specimen
braf_test = molecular_tests.filter(
    test_name__contains='Comprehensive Solid Tumor Panel',
    specimen_type='Frozen Tissue'
).first()
```

**Step 6: Extract Treatment Timeline**
```python
# Query chemotherapy/targeted therapy
medications = query_medications(patient_id,
    medication_name__contains=['vincristine', 'carboplatin', 'selumetinib']
).sort_by('medication_start_date')

# Identify treatment start
first_treatment = medications.first()
treatment_start_date = first_treatment['medication_start_date']  # Example: 2021-05-20
age_at_treatment_start_days = (treatment_start_date - birth_date).days  # 5851 days

# Calculate treatment duration
last_treatment = medications.filter(status='stopped').last()
treatment_end_date = last_treatment['validity_period_end']  # Example: 2024-06-04
treatment_duration_days = (treatment_end_date - treatment_start_date).days  # ~1110 days (3 years)

# Query radiation therapy (if applicable)
radiation_summary = query_radiation_summary(patient_id)
if radiation_summary['radiation_therapy_received']:
    radiation_start = radiation_summary['course_1_start_date']  # Example: 2021-07-15
    radiation_end = radiation_summary['course_1_end_date']
```

**Step 7: Identify Progression/Recurrence Events**
```python
# Query for recurrence/progression diagnoses
progression_events = query_diagnoses(patient_id,
    snomed_codes=['25173007'],  # Recurrent neoplasm
    onset_date__gt=diagnosis_date
).sort_by('onset_date_time')

for event in progression_events:
    event['days_since_initial_diagnosis'] = (event['onset_date_time'] - diagnosis_date).days
    event['days_since_surgery'] = (event['onset_date_time'] - surgery_date).days
```

**Step 8: Extract Assessments Timeline**
```python
# Ophthalmology assessments
ophtho_encounters = query_encounters(patient_id,
    service_type='Ophthalmology'
).sort_by('encounter_date')

# Extract visual acuity measurements
visual_acuity_measurements = query_measurements(patient_id,
    measurement_type='Visual Acuity'
).sort_by('measurement_date')

# Neurocognitive assessments (if documented)
neurocog_assessments = query_procedures(patient_id,
    procedure_name__contains='neuropsychological'
).sort_by('procedure_date')
```

**Step 9: Construct Unified Timeline**
```python
unified_timeline = []

# Add all events with standardized structure
for diagnosis in diagnosis_records:
    unified_timeline.append({
        'event_type': 'Diagnosis',
        'event_date': diagnosis['onset_date_time'],
        'age_days': (diagnosis['onset_date_time'] - birth_date).days,
        'description': diagnosis['diagnosis_name'],
        'source': 'Condition',
        'metadata': {...}
    })

for surgery in surgery_records:
    unified_timeline.append({
        'event_type': 'Procedure',
        'event_date': surgery['procedure_date'],
        'age_days': (surgery['procedure_date'] - birth_date).days,
        'description': surgery['procedure_name'],
        'source': 'Procedure',
        'metadata': {...}
    })

# Add imaging, medications, radiation, assessments similarly...

# Sort unified timeline by date
unified_timeline = sorted(unified_timeline, key=lambda x: x['event_date'])
```

---

## 4. Concrete Patient Example: Timeline Walkthrough

### 4.1 Patient Demographics
- **Patient ID**: e4BwD8ZYDBccepXcJ.Ilo3w3
- **Birth Date**: 2005-05-13 (Day 0)
- **Sex**: Female
- **Race**: White
- **Ethnicity**: Not Hispanic or Latino
- **Current Age**: 20 years (as of 2025-10-19)

### 4.2 Complete Timeline Reconstruction

```
=== BIRTH ===
2005-05-13 (Day 0, Age 0.00 years) - Birth

=== PRE-DIAGNOSIS PERIOD (2005-2018) ===
2005-05-19 (Day 6) - Encounter: General Pediatrics (Recheck Weight)
2006-05-19 (Day 371) - Encounter: Well Child Visit
... [routine pediatric care, chronic ear infections, otitis media]

=== DIAGNOSTIC PERIOD (May-June 2018) ===
2018-05-27 (Day 4762, Age 13.04 years)
  - Diagnosis: Neoplasm of posterior cranial fossa (D49.6)
  - Diagnosis: Obstructive hydrocephalus (G91.1)
  - Clinical Presentation: Posterior fossa mass with hydrocephalus

2018-05-28 (Day 4763, Age 13.05 years)
  - Molecular Test: Comprehensive Solid Tumor Panel (specimen collected)
    Source: Frozen tissue from surgical resection

2018-06-04 (Day 4770, Age 13.06 years)
  - Diagnosis: Pilocytic astrocytoma of cerebellum (C71.6)
  - Status: Active diagnosis (confirmed pathology)
  - Location: Cerebellum (fourth ventricle)

2018-06-06 (Day 4772, Age 13.07 years)
  - Procedure: Suboccipital craniotomy for tumor resection
  - Procedure: Right frontal ventriculostomy catheter placement
  - Surgery Type: Primary tumor resection

=== IMMEDIATE POST-OPERATIVE PERIOD (June-August 2018) ===
2018-06-12 (Day 4778)
  - Diagnosis: Posterior cranial fossa compression syndrome (G93.5)
  - Diagnosis: Dysphagia (R13.10) - Resolved by 2019-06-05
  - Diagnosis: Chronic constipation (K59.09) - Resolved by 2019-06-05

2018-06-15 (Day 4781)
  - Diagnosis: History of malnutrition (Z86.39) - Resolved by 2019-06-05

2018-06-19 (Day 4785)
  - Diagnosis: Encounter for rehabilitation (Z51.89)

2018-06-22 (Day 4788)
  - Imaging: CT Brain without contrast (post-operative surveillance)

2018-06-25 (Day 4791)
  - Imaging: CT Brain without contrast

2018-06-26 (Day 4792)
  - Diagnosis: Persistent vomiting (R11.15)

2018-07-23 (Day 4819)
  - Diagnosis: Ataxia (R27.0)

2018-07-25 (Day 4821)
  - Diagnosis: Abnormality of gait (R26.9)

2018-08-03 (Day 4830)
  - Imaging: MRI Brain with/without contrast
    Finding: "Interval progression of residual neoplasm with areas of new enhancement in the left cerebral peduncle and thalamus"
    Interpretation: Residual tumor progression detected ~2 months post-surgery

  - Imaging: MRI Entire Spine with/without contrast
    Finding: "Posterior lower thoracic dural based thickening/metastasis, likely subdural"
    Interpretation: Possible drop metastases to spine

2018-08-08 (Day 4835)
  - Diagnosis: Dysarthria (R47.1)
  - Diagnosis: Acquired aphasia (R47.01)

2018-09-29 (Day 4887)
  - Diagnosis: Nystagmus (H55.00)
  - Status: Obstructive hydrocephalus resolved (abatement date)

2018-12-15 (Day 4964)
  - Diagnosis: Diplopia (H53.2)

=== TREATMENT DECISION PERIOD (2019) ===
2019-05-28 (Day 5128, Age 14.04 years)
  - Diagnosis: Encounter for antineoplastic chemotherapy (Z51.11)
  - Clinical Decision: Initiate systemic therapy for residual/progressive disease

2019-06-25 (Day 5156)
  - Diagnosis: Port-A-Cath in place (Z95.828) - Resolved 2021-04-03

=== RADIATION THERAPY PERIOD (July-August 2021) ===
2021-07-15 (Day 5907, Age 16.17 years)
  - Radiation Course 1: Start date
  - Total Appointments: 72 radiation treatment sessions
  - Re-irradiation: Yes (indicates prior radiation or second course)

2021-08-05 (Day 5928)
  - Radiation Course 2: Start date

=== TARGETED THERAPY PERIOD (May 2021 - June 2024) ===
2021-05-20 (Day 5851, Age 16.02 years)
  - Medication Start: Selumetinib (Koselugo) 10 mg oral capsule
  - Indication: Pilocytic astrocytoma of cerebellum
  - Care Plan: ONCOLOGY TREATMENT protocol
  - Reason: Encounter for antineoplastic chemotherapy

2021-05-20 to 2024-06-04 (Days 5851-6962, Duration ~3.04 years)
  - Continuous selumetinib therapy (multiple prescription refills documented)
  - Dosing: 10 mg capsules (later adjusted to combination 10 mg + 25 mg for 25 mg AM / 20 mg PM)
  - Frequency: Daily oral administration

2024-06-04 (Day 6962, Age 19.05 years)
  - Selumetinib therapy stopped
  - Final prescription validity period ended

2024-07-09 (Day 6997)
  - Brief selumetinib re-initiation (30-day course, completed)

=== SECOND RADIATION THERAPY PERIOD (July-August 2024) ===
2024-07-10 (Day 6998, Age 19.16 years)
  - Radiation Course 3: Start date

2024-08-20 (Day 7039)
  - Radiation Course 4: Start date

=== POST-TREATMENT PERIOD (2021-2025) ===
2021-03-10 (Day 5780)
  - Molecular Test: Comprehensive Solid Tumor Panel T/N Pair (tumor/normal paired analysis)
  - Specimen: Frozen tissue from resection
  - Molecular Test: Tumor Panel Normal Paired (blood specimen)
  - Purpose: Genomic characterization of recurrent/progressive tumor

2021-03-22 (Day 5792)
  - Diagnosis: CINV - Chemotherapy-induced nausea and vomiting (T45.1X5A)
  - Status: Active (treatment-related toxicity)

=== SURVEILLANCE PERIOD (2022-2025) ===
2024-08-12 (Day 7031)
  - Imaging: MRI Brain with contrast (gadobutrol contrast agent)

2024-09-09 (Day 7059)
  - Imaging: MRI Brain with contrast

2024-09-12 (Day 7062)
  - Medication: Influenza vaccine administered

2024-12-02 (Day 7143)
  - Imaging: MRI Brain with contrast

2025-05-14 (Day 7306)
  - Imaging: MRI Brain with contrast

=== CURRENT STATUS (2025-10-19) ===
Current Age: 20 years (7463 days from birth)
Time Since Diagnosis: 7.42 years (2693 days from 2018-06-04)
Time Since Initial Surgery: 7.40 years (2691 days from 2018-06-06)
Time Since Targeted Therapy Start: 4.42 years (1612 days from 2021-05-20)
Total Duration of Selumetinib Therapy: 3.04 years (1111 days)
Total Radiation Courses: 4
Disease Status: Under surveillance
```

### 4.3 Timeline Key Observations

**Diagnosis to Treatment Arc**:
- Diagnosis → Surgery: 2 days
- Surgery → Progression Detection: 58 days
- Diagnosis → Systemic Therapy Start: 1081 days (2.96 years)
- Diagnosis → Radiation Therapy Start: 1201 days (3.29 years)

**Treatment Complexity**:
- Multiple treatment modalities over 6+ years
- Surgery (Day 4772) → Surveillance (Days 4788-4830) → Progression (Day 4830) → Radiation (Day 5907-5928) → Targeted Therapy (Days 5851-6962) → Re-irradiation (Days 6998-7039)

**Longitudinal Surveillance**:
- MRI frequency post-treatment: Approximately every 2-4 months
- Total imaging encounters: 181 documented imaging studies
- Total encounters: 999 documented encounters
- Total medications: 1121 medication records
- Total procedures: 72 documented procedures

**Disease Trajectory**:
- Initial presentation: Posterior fossa mass with hydrocephalus
- Post-surgical complication: Residual tumor with progression
- Treatment escalation: Radiation → Targeted therapy → Re-irradiation
- Long-term management: Ongoing surveillance with serial MRI

---

## 5. Timeline Quality Metrics for External Control Arms

### 5.1 Completeness Metrics

**Required Data Completeness Thresholds**:
- Diagnosis date: 100%
- Birth date (for age calculation): 100%
- Primary treatment dates (surgery/radiation/chemo start): 100%
- Baseline imaging: 100%
- Survival status at last follow-up: 100%
- Molecular testing results: Document availability rate (target >80% for modern cohorts)

**Desirable Data Completeness Thresholds**:
- Follow-up imaging at protocol timepoints: >85%
- Treatment end dates: >90%
- Progression events with dates: >85%
- Toxicity/adverse events: >75%

### 5.2 Temporal Consistency Validation Rules

**Logical Temporal Sequence Checks**:
```python
# Rule 1: Birth date < All other dates
assert all(event['event_date'] > birth_date for event in timeline)

# Rule 2: Diagnosis date <= Surgery date
assert diagnosis_date <= surgery_date

# Rule 3: Surgery date < Post-operative imaging date
assert surgery_date < first_post_op_imaging_date

# Rule 4: Treatment start >= Diagnosis date
assert treatment_start_date >= diagnosis_date

# Rule 5: Imaging intervals reasonable (not >2 years gap during active treatment)
for i in range(len(imaging_timeline) - 1):
    interval_days = (imaging_timeline[i+1]['imaging_date'] - imaging_timeline[i]['imaging_date']).days
    if treatment_active:
        assert interval_days <= 730, "Imaging gap >2 years during active treatment"

# Rule 6: Medication start < Medication end
for med in medications:
    if med['end_date']:
        assert med['start_date'] < med['end_date']

# Rule 7: Progression date > Initial diagnosis date
for progression in progression_events:
    assert progression['onset_date'] > diagnosis_date

# Rule 8: Last follow-up date = Most recent encounter
last_followup = max(encounter['encounter_date'] for encounter in encounters)
```

### 5.3 Data Density Metrics

**Timeline Density Score**:
```python
# Calculate events per year of follow-up
follow_up_duration_years = (last_followup_date - diagnosis_date).days / 365.25

total_events = (
    len(encounters) +
    len(imaging_studies) +
    len(procedures) +
    len(medication_records)
)

timeline_density = total_events / follow_up_duration_years

# Example for patient e4BwD8ZYDBccepXcJ.Ilo3w3:
# Follow-up: 7.42 years
# Total events: ~27,000+ (999 encounters + 181 imaging + 72 procedures + 1121 medications + 22,000 binary files)
# Density: ~3,640 events/year (exceptionally high-density longitudinal data)
```

**Imaging Surveillance Compliance**:
```python
# Define expected imaging timepoints post-treatment
expected_timepoints = [
    {'months': 3, 'window_days': 30},
    {'months': 6, 'window_days': 45},
    {'months': 12, 'window_days': 60},
    {'months': 18, 'window_days': 60},
    {'months': 24, 'window_days': 90}
]

# Calculate compliance
imaging_compliance_rate = count_imaging_within_windows(imaging_timeline, expected_timepoints) / len(expected_timepoints)
```

---

## 6. Mapping Timeline to Arbitrary Endpoint Structures

### 6.1 Design Principle: **Timeline First, Structure Later**

The comprehensive patient timeline is **source-agnostic** and **endpoint-agnostic**. It captures the complete longitudinal arc of the patient's disease journey without assuming any specific data model structure.

**Advantages**:
1. **Flexibility**: Timeline can be mapped onto BRIM event-based structure, CDISC SDTM, OMOP CDM, or custom trial-specific schemas
2. **Completeness**: No data lost due to premature structural assumptions
3. **Auditability**: Complete provenance from source (Athena FHIR) to timeline to endpoint structure
4. **Extensibility**: New variables/endpoints can be derived without re-querying source systems

### 6.2 Example Mappings

**Mapping to BRIM Event-Based Structure**:
```python
# From unified timeline → BRIM diagnosis form
brim_diagnosis_event = {
    'event_id': generate_event_id(),
    'event_type': 'Initial CNS Tumor',
    'age_at_event_days': age_at_diagnosis_days,  # 4770
    'cns_integrated_diagnosis': 'Pilocytic astrocytoma',
    'who_grade': 'Grade 1',
    'tumor_location': extract_from_imaging(pre_surgical_imaging[0], variable='tumor_location'),
    'date_of_event': diagnosis_date  # 2018-06-04
}

# From unified timeline → BRIM treatment form
brim_treatment_event = {
    'event_id': brim_diagnosis_event['event_id'],  # Same event
    'treatment_which_visit': 'Initial Diagnosis',
    'age_at_surgery': age_at_surgery_days,  # 4772
    'surgery_performed': 'Yes',
    'extent_of_resection': extract_from_imaging(post_surgical_imaging[0], variable='extent_of_resection'),
    'age_at_chemo_start': age_at_treatment_start_days,  # 5851
    'chemotherapy_agents': 'Selumetinib (MEK inhibitor)',
    'age_at_radiation_start': (radiation_start_date - birth_date).days  # 5907
}

# From unified timeline → BRIM imaging custom form
for scan in post_surgical_imaging:
    brim_imaging_record = {
        'event_id': brim_diagnosis_event['event_id'],
        'imaging_timepoint': assign_timepoint(scan['imaging_date'], reference_date=diagnosis_date),
        'age_at_date_scan': (scan['imaging_date'] - birth_date).days,
        'imaging_clinical_status': extract_from_imaging(scan, variable='tumor_status'),
        'cortico_yn': extract_from_imaging(scan, variable='cortical_involvement')
    }
```

**Mapping to CDISC SDTM**:
```python
# DM (Demographics) domain
dm_record = {
    'USUBJID': patient_id,
    'RFSTDTC': diagnosis_date.isoformat(),  # Reference start date
    'RFENDTC': last_followup_date.isoformat(),
    'BRTHDTC': birth_date.isoformat(),
    'AGE': age_at_diagnosis_years,
    'SEX': demographics['sex'],
    'RACE': demographics['race']
}

# EX (Exposure) domain
for med in medications:
    ex_record = {
        'USUBJID': patient_id,
        'EXTRT': med['medication_name'],
        'EXSTDTC': med['start_date'].isoformat(),
        'EXENDTC': med['end_date'].isoformat() if med['end_date'] else None,
        'EXDOSE': extract_dose(med),
        'EXDOSFRQ': extract_frequency(med)
    }

# TU (Tumor Identification) domain
for imaging in imaging_timeline:
    tu_record = {
        'USUBJID': patient_id,
        'TUDTC': imaging['imaging_date'].isoformat(),
        'TULOC': extract_from_imaging(imaging, 'tumor_location'),
        'TUMETHOD': imaging['modality'],  # 'MRI'
    }
```

**Mapping to Trial-Specific Endpoints (PFS)**:
```python
# Define progression event
progression_event = progression_events[0] if progression_events else None

if progression_event:
    pfs_date = progression_event['onset_date_time']
    pfs_days = (pfs_date - diagnosis_date).days
    pfs_event = 1  # Event occurred
else:
    pfs_date = last_followup_date
    pfs_days = (pfs_date - diagnosis_date).days
    pfs_event = 0  # Censored

trial_endpoint_record = {
    'patient_id': patient_id,
    'diagnosis_date': diagnosis_date,
    'pfs_days': pfs_days,
    'pfs_event': pfs_event,
    'pfs_date': pfs_date,
    'os_days': (last_followup_date - diagnosis_date).days,
    'os_event': 1 if deceased else 0
}
```

---

## 7. Implementation Considerations

### 7.1 Data Extraction Strategy

**Phase 1: Complete Timeline Extraction** (Current Focus)
- Query all 8 domains from Athena FHIR views
- Construct unified timeline with all events
- Store in intermediate JSON/Parquet format
- Validate temporal consistency

**Phase 2: Variable Extraction** (MedGemma Integration)
- Extract structured variables from Athena structured fields
- Extract unstructured variables from Athena free text (imaging conclusions, molecular narratives)
- Extract unstructured variables from S3 binary files (PDFs, HTML reports)
- Merge extractions with conflict resolution

**Phase 3: Endpoint Mapping** (Structure Application)
- Map unified timeline + extracted variables → BRIM forms
- Apply event classification logic (Initial vs Recurrence vs Progression)
- Assign timepoints relative to diagnosis
- Generate final BRIM-compatible dataset

### 7.2 Timeline Storage Schema

**Recommended Format**: Parquet with nested structures

```python
timeline_schema = {
    'patient_id': 'string',
    'birth_date': 'date',
    'demographics': {
        'sex': 'string',
        'race': 'string',
        'ethnicity': 'string'
    },
    'events': [
        {
            'event_type': 'string',  # 'Diagnosis', 'Procedure', 'Imaging', 'Medication', 'Assessment'
            'event_date': 'timestamp',
            'age_days': 'int32',
            'age_years': 'float32',
            'description': 'string',
            'source_domain': 'string',  # 'Condition', 'Procedure', 'DiagnosticReport', etc.
            'source_id': 'string',  # FHIR resource ID
            'codes': {
                'icd10': ['string'],
                'snomed': ['string'],
                'cpt': ['string']
            },
            'metadata': 'json'  # Domain-specific fields
        }
    ],
    'milestones': {
        'diagnosis_date': 'date',
        'surgery_date': 'date',
        'treatment_start_date': 'date',
        'last_followup_date': 'date'
    }
}
```

### 7.3 Quality Assurance Workflow

**Automated Validation**:
1. Temporal consistency checks (diagnosis < surgery < treatment)
2. Data completeness metrics (% non-null for required fields)
3. Timeline density calculations
4. Duplicate event detection
5. Outlier detection (e.g., age at event >100 years)

**Manual Review Triggers**:
- Missing diagnosis date
- Missing surgery date when procedure records exist
- Imaging gaps >2 years during active surveillance
- Progression date before diagnosis date
- Conflicting data from multiple sources

---

## 8. Next Steps

### 8.1 Immediate Priorities
1. ✅ **Complete**: Document pediatric brain tumor natural history and external control arm requirements
2. ✅ **Complete**: Define comprehensive timeline framework across 8 data domains
3. ✅ **Complete**: Create concrete patient timeline example (Patient e4BwD8ZYDBccepXcJ.Ilo3w3)
4. **Pending**: Implement Python timeline extraction functions for all 8 domains
5. **Pending**: Create timeline validation suite

### 8.2 Future Work
1. Map timeline → BRIM event-based structure
2. Define event classification logic (Initial vs Recurrence vs Progression)
3. Implement timepoint assignment algorithm
4. Create variable extraction orchestration (Athena structured + free text + S3 binary)
5. Build conflict resolution logic for multi-source extractions

---

## 9. References

### 9.1 Clinical Guidelines
- NCI PDQ: Childhood Astrocytomas and Other Gliomas Treatment (2024)
- SIOP-LGG 2024: Low-Grade Glioma Treatment Protocols
- COG ACNS: Children's Oncology Group Low-Grade Astrocytoma Studies

### 9.2 Regulatory Guidance
- FDA Draft Guidance: Considerations for the Design and Conduct of Externally Controlled Trials (2023)
- EMA Reflection Paper: Use of External Controls in Oncology (2022)
- FDA Real-World Evidence Framework (2024)

### 9.3 Research Literature
- Journal of Clinical Oncology: "Use of External Control Cohorts in Pediatric Brain Tumor Clinical Trials" (2024)
- Pharmacoepidemiology and Drug Safety: "Real-world evidence to support regulatory decision-making for medicines" (2020)
- Pediatric Brain Tumor Consortium: Distributed Data Management Systems (2010)

---

**Document Status**: Foundation Complete ✅
**Last Updated**: 2025-10-19
**Next Review**: After implementing timeline extraction functions
