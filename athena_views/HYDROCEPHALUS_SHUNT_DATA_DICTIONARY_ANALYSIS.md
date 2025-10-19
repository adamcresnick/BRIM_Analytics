# Hydrocephalus and Shunt Data Dictionary Analysis
**Date**: October 18, 2025
**Purpose**: Map CBTN data dictionary hydrocephalus/shunt fields to FHIR source tables and design structured queries

---

## CBTN Data Dictionary Fields

### 1. Diagnosis Form - Medical Conditions at Event

**Field**: `medical_conditions_present_at_event`
- **Type**: Checkbox
- **Label**: "Medical Conditions Present at Event (Current Instance)"
- **Options**: Includes "11, Hydrocephalus" among other conditions
- **Branching Logic**: `[clinical_status_at_event] = '1'`
- **Required**: Yes

**Field**: `shunt_required` (at diagnosis)
- **Type**: Radio
- **Label**: "Indicate the shunt required"
- **Options**:
  - 1 = Ventriculo-Peritoneal Shunt (VPS)
  - 2 = Endoscopic Third Ventriculostomy (ETV) Shunt
  - 3 = Other
  - 4 = Not Done
- **Branching Logic**: `[medical_conditions_present_at_event(11)] = '1'`
- **Note**: Only appears if hydrocephalus is present at diagnosis event

**Field**: `shunt_required_other`
- **Type**: Text
- **Label**: "Shunt other, specify:"
- **Branching Logic**: `[shunt_required] = '3'`

---

### 2. Hydrocephalus Details Form (Repeating Events)

**Overview**: This is a dedicated repeating event form for tracking hydrocephalus episodes over time

#### 2.1 Hydrocephalus Diagnosis

**Field**: `hydro_yn`
- **Type**: Radio
- **Label**: "Does the subject have hydrocephalus?"
- **Options**:
  - 1 = Yes
  - 2 = No
  - 3 = Unknown

**Field**: `hydro_event_date`
- **Type**: Text (date_ymd)
- **Label**: "Date of hydrocephalus event:"
- **Validation**: Date format, max = today
- **Identifier**: Yes (PHI)
- **Branching Logic**: `[hydro_yn] = '1'`

**Field**: `hydro_method_diagnosed`
- **Type**: Checkbox
- **Label**: "How was hydrocephalus diagnosed?"
- **Options**:
  - 1 = Clinical
  - 2 = Diagnostic imaging CT
  - 3 = Diagnostic imaging MRI
- **Branching Logic**: `[hydro_yn] = '1'`

#### 2.2 Hydrocephalus Intervention

**Field**: `hydro_intervention`
- **Type**: Checkbox
- **Label**: "Type of Intervention for hydrocephalus"
- **Options**:
  - 1 = Surgical
  - 2 = Medical
  - 3 = Hospitalization
  - 4 = None (NONEOFTHEABOVE)
- **Note**: "If surgical, will also always be hospitalization"
- **Branching Logic**: `[hydro_yn] = '1'`

#### 2.3 Surgical Management

**Field**: `hydro_surgical_management`
- **Type**: Checkbox
- **Label**: "Surgical management of hydrocephalus"
- **Options**:
  - 1 = Temporary External Ventricular Drain (EVD) removed without need for permanent shunt
  - 2 = Endoscopic Third Ventriculostomy (ETV)
  - 3 = Ventriculoperitoneal Shunt (VPS) placement
  - 4 = Ventriculoperitoneal Shunt (VPS) revision
  - 5 = Other, specify
- **Branching Logic**: `[hydro_intervention(1)] = '1'`

**Field**: `hydro_surgical_management_other`
- **Type**: Text
- **Label**: "Surgical management of hydrocephalus other, specify"
- **Branching Logic**: `[hydro_surgical_management(5)] = '1'`

**Field**: `hydro_shunt_programmable`
- **Type**: Radio
- **Label**: "Does shunt have programmable valve?"
- **Options**:
  - 1 = Yes
  - 2 = No
  - 3 = Not applicable, no shunt
  - 4 = Unknown
- **Branching Logic**: `[hydro_surgical_management(3)] = '1' or [hydro_surgical_management(4)] = '1' or [hydro_surgical_management(5)] = '1'`

#### 2.4 Non-Surgical Management

**Field**: `hydro_nonsurg_management`
- **Type**: Checkbox
- **Label**: "Non-surgical management of hydrocephalus"
- **Options**:
  - 1 = Steroid
  - 2 = Shunt reprogramming
  - 3 = Other, specify
- **Branching Logic**: `[hydro_intervention(2)] = '1'`

**Field**: `hydro_nonsurg_management_other`
- **Type**: Text
- **Label**: "Non-surgical management of hydrocephalus other, specify"
- **Branching Logic**: `[hydro_nonsurg_management(3)] = '1'`

---

## Summary of Data Dictionary Fields

### Total Fields: 11

| Field Name | Form | Type | Critical Info |
|------------|------|------|---------------|
| medical_conditions_present_at_event | diagnosis | checkbox | Initial hydrocephalus flag |
| shunt_required | diagnosis | radio | Shunt type at diagnosis |
| shunt_required_other | diagnosis | text | Custom shunt description |
| hydro_yn | hydrocephalus_details | radio | Hydrocephalus present flag |
| hydro_event_date | hydrocephalus_details | date | Event date (PHI) |
| hydro_method_diagnosed | hydrocephalus_details | checkbox | Diagnosis method |
| hydro_intervention | hydrocephalus_details | checkbox | Intervention type |
| hydro_surgical_management | hydrocephalus_details | checkbox | Surgical procedure type |
| hydro_surgical_management_other | hydrocephalus_details | text | Custom procedure |
| hydro_shunt_programmable | hydrocephalus_details | radio | Programmable valve flag |
| hydro_nonsurg_management | hydrocephalus_details | checkbox | Medical management |
| hydro_nonsurg_management_other | hydrocephalus_details | text | Custom medical management |

---

## FHIR Source Table Mapping Strategy

### Primary Data Sources

#### 1. **Condition Table** - Hydrocephalus Diagnosis
```
FHIR Resource: Condition
Table: fhir_prd_db.condition
Target Fields:
  - hydro_yn (derived from condition code/text)
  - medical_conditions_present_at_event (hydrocephalus flag)

Search Patterns:
  - code_text LIKE '%hydrocephalus%'
  - code_text LIKE '%hydroceph%'
  - ICD-10: G91.% (Hydrocephalus codes)
  - ICD-10: Q03.% (Congenital hydrocephalus)
```

**Expected ICD-10 Codes**:
- G91.0 - Communicating hydrocephalus
- G91.1 - Obstructive hydrocephalus
- G91.2 - Normal-pressure hydrocephalus
- G91.3 - Post-traumatic hydrocephalus
- G91.4 - Hydrocephalus in diseases classified elsewhere
- G91.8 - Other hydrocephalus
- G91.9 - Hydrocephalus, unspecified
- Q03.0 - Malformations of aqueduct of Sylvius
- Q03.1 - Atresia of foramina of Magendie and Luschka
- Q03.8 - Other congenital hydrocephalus
- Q03.9 - Congenital hydrocephalus, unspecified

#### 2. **Procedure Table** - Shunt Procedures
```
FHIR Resource: Procedure
Table: fhir_prd_db.procedure
Target Fields:
  - shunt_required
  - hydro_surgical_management
  - hydro_shunt_programmable

Search Patterns (code_text):
  - '%ventriculoperitoneal%shunt%' OR '%VP%shunt%' OR '%VPS%'
  - '%endoscopic%third%ventriculostomy%' OR '%ETV%'
  - '%external%ventricular%drain%' OR '%EVD%'
  - '%shunt%revision%'
  - '%shunt%placement%'
  - '%ventriculo%peritoneal%'
  - '%programmable%valve%'
```

**Expected CPT Codes**:
- 62220 - Creation of shunt; ventriculo-atrial, -jugular, -auricular
- 62223 - Creation of shunt; ventriculo-peritoneal, -pleural, other terminus
- 62225 - Replacement or irrigation of ventricular catheter
- 62230 - Replacement or revision of cerebrospinal fluid shunt
- 62252 - Reprogramming of programmable cerebrospinal fluid shunt
- 62256 - Removal of complete cerebrospinal fluid shunt system
- 62258 - Replacement of complete cerebrospinal fluid shunt system
- 62200 - Ventriculocisternostomy, third ventricle
- 62201 - Stereotactic creation of lesion by microelectrode recording
- 31291 - Endoscopic third ventriculostomy

**Procedure Sub-Schemas**:
```sql
procedure_body_site: Location of shunt placement
procedure_code_coding: CPT/ICD-10-PCS codes
procedure_performer: Neurosurgeon
procedure_reason_code: Indication (hydrocephalus)
procedure_note: Surgical details, programmable valve info
```

#### 3. **Observation Table** - Imaging Diagnosis
```
FHIR Resource: Observation
Table: fhir_prd_db.observation
Target Fields:
  - hydro_method_diagnosed (imaging findings)
  - hydro_event_date (from observation effective date)

Search Patterns:
  - code_text LIKE '%ventricle%enlarged%'
  - code_text LIKE '%ventricular%dilation%'
  - code_text LIKE '%hydrocephalus%'
  - value_string/value_codeable_concept_text containing hydrocephalus findings
```

**Observation Categories**:
- Radiology reports (CT, MRI)
- Neurological exam findings
- Intracranial pressure measurements

#### 4. **DiagnosticReport Table** - Imaging Studies
```
FHIR Resource: DiagnosticReport
Table: fhir_prd_db.diagnostic_report
Target Fields:
  - hydro_method_diagnosed (CT vs MRI)

Search Patterns:
  - code_text LIKE '%CT%brain%' OR '%MRI%brain%'
  - conclusion LIKE '%hydrocephalus%'
  - conclusion LIKE '%ventriculomegaly%'
  - conclusion LIKE '%enlarged ventricles%'
```

#### 5. **ServiceRequest Table** - Shunt Orders
```
FHIR Resource: ServiceRequest
Table: fhir_prd_db.service_request
Target Fields:
  - shunt_required (ordered procedures)
  - hydro_surgical_management (planned vs completed)

Search Patterns:
  - code_text LIKE '%shunt%'
  - code_text LIKE '%ventriculostomy%'
  - patient_instruction containing shunt details
```

#### 6. **MedicationRequest Table** - Medical Management
```
FHIR Resource: MedicationRequest
Table: fhir_prd_db.medication_request
Target Fields:
  - hydro_nonsurg_management (steroids)

Search Patterns for Steroids:
  - code_text LIKE '%dexamethasone%'
  - code_text LIKE '%methylprednisolone%'
  - code_text LIKE '%prednisone%'
  - reason_code_text LIKE '%hydrocephalus%'
  - reason_code_text LIKE '%increased%intracranial%pressure%'
```

#### 7. **Encounter Table** - Hospitalization
```
FHIR Resource: Encounter
Table: fhir_prd_db.encounter
Target Fields:
  - hydro_intervention (hospitalization flag)
  - hydro_event_date (from encounter period)

Search Patterns:
  - class_code = 'IMP' (inpatient)
  - reason_code_text LIKE '%hydrocephalus%'
  - diagnosis_condition_reference linking to hydrocephalus condition
```

#### 8. **Device Table** - Shunt Device Details
```
FHIR Resource: Device
Table: fhir_prd_db.device
Target Fields:
  - hydro_shunt_programmable (device properties)
  - shunt_required (device type)

Search Patterns:
  - device_name LIKE '%programmable%'
  - device_name LIKE '%VP%shunt%'
  - device_name LIKE '%ventriculoperitoneal%'
  - type_text LIKE '%CSF%shunt%'
  - type_text LIKE '%programmable%valve%'
```

**Common Programmable Shunt Brands**:
- Medtronic Strata
- Codman Hakim
- Sophysa Polaris
- Aesculap proGAV

---

## Structured Query Strategy

### Query 1: Identify Patients with Hydrocephalus

**Objective**: Map to `hydro_yn = 1` and `medical_conditions_present_at_event(11) = 1`

**Primary Sources**:
1. **Condition table** - Direct diagnosis codes
2. **Diagnostic report conclusions** - Imaging findings
3. **Observation value text** - Clinical findings

**Query Approach**:
```sql
-- Patients with documented hydrocephalus condition
SELECT DISTINCT
    subject_reference as patient_fhir_id,
    'condition' as data_source,
    id as source_id,
    code_text,
    code_coding,
    onset_date_time,
    recorded_date
FROM fhir_prd_db.condition
WHERE subject_reference IS NOT NULL
  AND (
      LOWER(code_text) LIKE '%hydroceph%'
      OR REGEXP_LIKE(code_coding, 'G91\\.') -- ICD-10 hydrocephalus
      OR REGEXP_LIKE(code_coding, 'Q03\\.') -- Congenital hydrocephalus
  )
```

### Query 2: Identify Shunt Procedures

**Objective**: Map to `shunt_required`, `hydro_surgical_management`

**Primary Sources**:
1. **Procedure table** - Completed procedures
2. **ServiceRequest table** - Ordered procedures
3. **Procedure sub-schemas** - Detailed procedure info

**Query Approach**:
```sql
-- Shunt procedures with type classification
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text as procedure_name,
    p.performed_date_time,
    p.performed_period_start,
    p.performed_period_end,
    p.status,

    -- Classify shunt type
    CASE
        WHEN LOWER(p.code_text) LIKE '%ventriculoperitoneal%'
             OR LOWER(p.code_text) LIKE '%vp%shunt%'
             OR LOWER(p.code_text) LIKE '%vps%' THEN 'VPS'
        WHEN LOWER(p.code_text) LIKE '%endoscopic%third%ventriculostomy%'
             OR LOWER(p.code_text) LIKE '%etv%' THEN 'ETV'
        WHEN LOWER(p.code_text) LIKE '%external%ventricular%drain%'
             OR LOWER(p.code_text) LIKE '%evd%' THEN 'EVD'
        ELSE 'Other'
    END as shunt_type,

    -- Classify procedure category
    CASE
        WHEN LOWER(p.code_text) LIKE '%placement%'
             OR LOWER(p.code_text) LIKE '%insertion%'
             OR LOWER(p.code_text) LIKE '%creation%' THEN 'Initial Placement'
        WHEN LOWER(p.code_text) LIKE '%revision%'
             OR LOWER(p.code_text) LIKE '%replacement%' THEN 'Revision'
        WHEN LOWER(p.code_text) LIKE '%removal%' THEN 'Removal'
        WHEN LOWER(p.code_text) LIKE '%reprogramming%' THEN 'Reprogramming'
        ELSE 'Unknown'
    END as procedure_category,

    -- Aggregate procedure notes for programmable valve info
    pn.note_text_aggregated

FROM fhir_prd_db.procedure p
LEFT JOIN (
    SELECT
        procedure_id,
        LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_time) as note_text_aggregated
    FROM fhir_prd_db.procedure_note
    GROUP BY procedure_id
) pn ON p.id = pn.procedure_id

WHERE p.subject_reference IS NOT NULL
  AND (
      LOWER(p.code_text) LIKE '%shunt%'
      OR LOWER(p.code_text) LIKE '%ventriculostomy%'
      OR LOWER(p.code_text) LIKE '%ventricular%drain%'
      OR REGEXP_LIKE(p.code_coding, '622(20|23|25|30|52|56|58|00|01)')  -- CPT codes
  )
```

### Query 3: Identify Programmable Shunts

**Objective**: Map to `hydro_shunt_programmable = 1`

**Primary Sources**:
1. **Device table** - Implanted devices
2. **Procedure notes** - Surgical details mentioning programmable valve
3. **Procedure code details** - Specific CPT codes for programmable valves

**Query Approach**:
```sql
-- Programmable shunt devices
SELECT DISTINCT
    d.patient_reference as patient_fhir_id,
    d.id as device_id,
    d.device_name,
    d.type_text,
    d.manufacturer,
    d.model_number,

    -- Programmable flag
    CASE
        WHEN LOWER(d.device_name) LIKE '%programmable%'
             OR LOWER(d.type_text) LIKE '%programmable%'
             OR LOWER(d.model_number) LIKE '%strata%'
             OR LOWER(d.model_number) LIKE '%hakim%'
             OR LOWER(d.model_number) LIKE '%polaris%'
             OR LOWER(d.model_number) LIKE '%progav%' THEN true
        ELSE false
    END as is_programmable

FROM fhir_prd_db.device d
WHERE d.patient_reference IS NOT NULL
  AND (
      LOWER(d.type_text) LIKE '%shunt%'
      OR LOWER(d.type_text) LIKE '%csf%'
      OR LOWER(d.device_name) LIKE '%ventriculoperitoneal%'
  )
```

### Query 4: Identify Medical Management

**Objective**: Map to `hydro_nonsurg_management`

**Primary Sources**:
1. **MedicationRequest** - Steroids for hydrocephalus
2. **Procedure** - Shunt reprogramming (CPT 62252)

**Query Approach**:
```sql
-- Medical management: steroids and reprogramming
WITH steroid_medications AS (
    SELECT
        mr.subject_reference as patient_fhir_id,
        'Steroid' as management_type,
        mr.id as source_id,
        mr.medication_codeable_concept_text as medication_name,
        mr.authored_on,
        mrrc.reason_code_text
    FROM fhir_prd_db.medication_request mr
    LEFT JOIN fhir_prd_db.medication_request_reason_code mrrc
        ON mr.id = mrrc.medication_request_id
    WHERE mr.subject_reference IS NOT NULL
      AND (
          LOWER(mr.medication_codeable_concept_text) LIKE '%dexamethasone%'
          OR LOWER(mr.medication_codeable_concept_text) LIKE '%methylprednisolone%'
          OR LOWER(mr.medication_codeable_concept_text) LIKE '%prednisone%'
      )
      AND (
          LOWER(mrrc.reason_code_text) LIKE '%hydroceph%'
          OR LOWER(mrrc.reason_code_text) LIKE '%intracranial%pressure%'
          OR LOWER(mrrc.reason_code_text) LIKE '%icp%'
      )
),
shunt_reprogramming AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        'Shunt Reprogramming' as management_type,
        p.id as source_id,
        p.code_text as procedure_name,
        p.performed_date_time as performed_date,
        NULL as reason_code_text
    FROM fhir_prd_db.procedure p
    WHERE p.subject_reference IS NOT NULL
      AND (
          LOWER(p.code_text) LIKE '%reprogram%'
          OR p.code_coding LIKE '%62252%'  -- CPT code for reprogramming
      )
)
SELECT * FROM steroid_medications
UNION ALL
SELECT
    patient_fhir_id,
    management_type,
    source_id,
    procedure_name as medication_name,
    performed_date as authored_on,
    reason_code_text
FROM shunt_reprogramming
```

### Query 5: Identify Diagnosis Method

**Objective**: Map to `hydro_method_diagnosed`

**Primary Sources**:
1. **DiagnosticReport** - CT vs MRI studies
2. **Observation** - Clinical diagnosis

**Query Approach**:
```sql
-- Diagnosis method: CT, MRI, or Clinical
SELECT
    dr.subject_reference as patient_fhir_id,
    dr.id as report_id,
    dr.code_text as study_type,
    dr.effective_date_time,

    -- Classify diagnosis method
    CASE
        WHEN LOWER(dr.code_text) LIKE '%ct%'
             OR LOWER(dr.code_text) LIKE '%computed%tomography%' THEN 'CT'
        WHEN LOWER(dr.code_text) LIKE '%mri%'
             OR LOWER(dr.code_text) LIKE '%magnetic%resonance%' THEN 'MRI'
        ELSE 'Other Imaging'
    END as imaging_modality,

    -- Extract hydrocephalus findings
    dr.conclusion,

    -- Check if hydrocephalus mentioned
    CASE
        WHEN LOWER(dr.conclusion) LIKE '%hydroceph%'
             OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
             OR LOWER(dr.conclusion) LIKE '%enlarged%ventricle%' THEN true
        ELSE false
    END as hydrocephalus_documented

FROM fhir_prd_db.diagnostic_report dr
WHERE dr.subject_reference IS NOT NULL
  AND (
      LOWER(dr.code_text) LIKE '%brain%'
      OR LOWER(dr.code_text) LIKE '%head%'
      OR LOWER(dr.code_text) LIKE '%cranial%'
  )
  AND (
      LOWER(dr.conclusion) LIKE '%hydroceph%'
      OR LOWER(dr.conclusion) LIKE '%ventriculomegaly%'
      OR LOWER(dr.conclusion) LIKE '%enlarged%ventricle%'
  )
```

---

## Consolidated View Design

### Recommended Approach: Two Views

#### View 1: `v_hydrocephalus_diagnosis`
**Purpose**: Track hydrocephalus diagnosis events over time

**Data Sources**:
- Condition table (diagnosis codes)
- DiagnosticReport (imaging findings)
- Observation (clinical findings)
- Encounter (hospitalization context)

**Key Fields**:
- patient_fhir_id
- diagnosis_date (hydro_event_date)
- diagnosis_source (condition, imaging, clinical)
- diagnosis_method (CT, MRI, clinical)
- icd10_code
- condition_status
- imaging_modality
- imaging_report_id
- hospitalization_flag

#### View 2: `v_hydrocephalus_procedures`
**Purpose**: Track all hydrocephalus-related procedures

**Data Sources**:
- Procedure table (completed procedures)
- ServiceRequest table (ordered procedures)
- Device table (shunt devices)
- Procedure sub-schemas (detailed info)

**Key Fields**:
- patient_fhir_id
- procedure_id
- procedure_date (hydro_event_date)
- procedure_type (VPS, ETV, EVD, Revision, Reprogramming)
- procedure_category (Surgical, Medical)
- shunt_type (from classification logic)
- programmable_valve_flag
- device_id
- device_manufacturer
- device_model
- procedure_notes
- cpt_code

---

## Expected Data Coverage

### High Coverage Fields (Likely >70%)
1. **hydro_yn** - Condition table should have good coverage
2. **shunt_required** - Procedure table should capture most shunts
3. **hydro_surgical_management** - Procedure codes will classify type
4. **hydro_event_date** - Procedure/Condition dates available

### Medium Coverage Fields (Likely 30-70%)
5. **hydro_method_diagnosed** - Depends on diagnostic report conclusion quality
6. **hydro_intervention** - Encounter/Procedure linkage required
7. **hydro_shunt_programmable** - Device table or procedure notes needed

### Low Coverage Fields (Likely <30%)
8. **hydro_nonsurg_management** - Medical management may be poorly documented
9. **hydro_nonsurg_management_other** - Free text, likely minimal structured data
10. **hydro_surgical_management_other** - Free text, likely minimal structured data

### Document NLP Required
- Programmable valve details from operative notes
- Custom shunt types from procedure notes
- Medical management details from progress notes
- Clinical diagnosis details from physical exam notes

---

## Next Steps

1. ✅ Analyze data dictionary fields (COMPLETE)
2. ⏳ Query test patients to assess actual data availability
3. ⏳ Create `v_hydrocephalus_diagnosis` view
4. ⏳ Create `v_hydrocephalus_procedures` view
5. ⏳ Test on pilot patient cohort
6. ⏳ Document coverage gaps requiring NLP extraction
7. ⏳ Integrate with AthenaQueryAgent

---

## Notes

- **Repeating Events**: The hydrocephalus_details form is a repeating event, so patients can have multiple hydrocephalus episodes over time
- **Two Entry Points**: Hydrocephalus can be documented at initial diagnosis (diagnosis form) or as a separate event (hydrocephalus_details form)
- **Surgical = Hospitalization**: Per data dictionary notes, surgical intervention always implies hospitalization
- **Programmable Valve**: Critical field for shunt reprogramming eligibility
- **Medical Management**: Steroids and shunt reprogramming are non-surgical options

---

**Status**: Analysis complete, ready for query development
