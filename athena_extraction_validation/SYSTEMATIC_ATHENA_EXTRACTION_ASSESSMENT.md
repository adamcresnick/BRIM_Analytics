# Systematic Athena Extraction Capacity Assessment

**Date**: October 7, 2025  
**Purpose**: Systematically assess our capacity to extract gold standard CSV data from Athena materialized views  
**Scope**: 18 CSV files, 28,502 rows, 200+ variables

---

## Executive Summary

### Assessment Strategy: 3-Phase Approach

**Phase 1: CSV-by-CSV Field Mapping** (Per-CSV Analysis)
- Map each CSV column to Athena materialized view tables/fields
- Classify extractability: 100% Structured / Hybrid / Narrative-Only
- Identify existing extraction scripts and their coverage
- Document gaps requiring new extraction methods

**Phase 2: Materialized View Coverage Analysis** (Per-Table Analysis)
- For each Athena table, document complete schema
- Map to gold standard CSV fields (reverse mapping)
- Identify unused fields that could provide additional value
- Document join patterns and relationships

**Phase 3: Gap Prioritization & Implementation Plan** (Action Planning)
- Prioritize gaps by: (1) Extractability, (2) Clinical importance, (3) Complexity
- Create implementation roadmap with time estimates
- Define validation metrics per extraction method
- Document BRIM requirements for narrative-only fields

---

## Phase 1: CSV-by-CSV Field Mapping

### CSV 1: demographics.csv
**Rows**: 189 | **Columns**: 4 | **Completeness**: 100%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| `research_id` | C1277724 | N/A | Manual mapping (Epic MRN) | MANUAL | N/A | ⚠️ MANUAL |
| `legal_sex` | Female | `patient_access` | `gender` | 100% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |
| `race` | White | `patient_access` | `race` | 100% STRUCTURED | None | ⏳ TODO |
| `ethnicity` | Not Hispanic or Latino | `patient_access` | `ethnicity` | 100% STRUCTURED | None | ⏳ TODO |

**Assessment**:
- ✅ **100% extractable** from Athena (3/4 fields, excluding manual research_id)
- ⏳ **Gap**: race/ethnicity fields not yet extracted
- 🎯 **Priority**: HIGH (easy win, 10 min fix)
- 📝 **Action**: Add `extract_race_ethnicity()` method to extract_structured_data.py

---

### CSV 2: diagnosis.csv
**Rows**: 1,689 | **Columns**: 20 | **Completeness**: 97.85%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| `research_id` | C1277724 | N/A | Manual mapping | MANUAL | N/A | ⚠️ MANUAL |
| `event_id` | ET_FWYP9TY0 | N/A | Generated identifier | GENERATED | None | ⏳ TODO |
| `age_at_event_days` | 4763 | Calculated | birth_date + onset_date | 100% STRUCTURED | None | ⏳ TODO |
| `clinical_status_at_event` | Alive | `patient` | `deceased` (boolean) | 100% STRUCTURED | None | ⏳ TODO |
| `event_type` | Initial CNS Tumor | N/A | Timeline analysis logic | COMPLEX | None | ⏳ TODO |
| `cns_integrated_diagnosis` | Pilocytic astrocytoma | `problem_list_diagnoses` | `diagnosis_name` | 100% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |
| `who_grade` | 1 | `condition` | `stage.summary.text` | HYBRID (40%) | None | 🔴 BRIM |
| `metastasis` | Yes/No | `condition` | code='metastatic' | HYBRID (60%) | None | 🔴 BRIM |
| `metastasis_location` | Leptomeningeal, Spine | `condition` | `bodySite.text` | NARRATIVE ONLY | None | 🔴 BRIM |
| `site_of_progression` | Local | N/A | Narrative only | NARRATIVE ONLY | None | 🔴 BRIM |
| `tumor_location` | Cerebellum/Posterior Fossa | `condition` | `bodySite.text` | HYBRID (40%) | None | 🔴 BRIM |
| `tumor_or_molecular_tests_performed` | WGS, Specific gene mutation | `molecular_tests` OR `observation` | `code.text` | 90% STRUCTURED | None | ⏳ TODO |
| `shunt_required` | ETV Shunt | `procedure` | CPT 62201, 62223 | 100% STRUCTURED | None | ⏳ TODO |
| `autopsy_performed` | Not Applicable | `document_reference` | type='autopsy' | 100% STRUCTURED | None | ⏳ TODO |
| `cause_of_death` | Not Applicable | `patient` | `deceased.reason` | HYBRID (70%) | None | ⏳ TODO |

**Assessment**:
- ✅ **60% extractable** from Athena (9/15 clinical fields)
- 🟡 **40% hybrid** (3 fields: WHO grade, tumor location, metastasis)
- 🔴 **BRIM required** (3 fields: metastasis location, site of progression, autopsy findings)
- 🎯 **Priority**: MEDIUM (extract structured first, then BRIM for narrative)
- 📝 **Actions**:
  1. Add molecular_tests extraction (15 min)
  2. Add shunt_required extraction (10 min)
  3. Add clinical_status extraction (5 min)
  4. Add event timeline logic (30 min - COMPLEX)

---

### CSV 3: treatments.csv
**Rows**: 695 | **Columns**: 27 | **Completeness**: 100%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| **SURGERY** | | | | | | |
| `surgery` | Yes/No | `procedure` | COUNT(*) > 0 | 100% STRUCTURED | None | ⏳ TODO |
| `age_at_surgery` | 4763 | `procedure` | `performed_date_time` | 100% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |
| `extent_of_tumor_resection` | Partial resection | N/A | Operative notes | NARRATIVE ONLY | None | 🔴 BRIM |
| `specimen_collection_origin` | Initial CNS Tumor Surgery | N/A | Timeline + context | HYBRID (30%) | None | 🔴 BRIM |
| **CHEMOTHERAPY** | | | | | | |
| `chemotherapy` | Yes/No | `patient_medications` | COUNT(*) > 0 | 100% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |
| `chemotherapy_agents` | vinblastine;bevacizumab | `patient_medications` | `medication_name` | 100% STRUCTURED | extract_structured_data.py | ⚠️ PARTIAL (33%) |
| `age_at_chemo_start` | 5130 | `patient_medications` | `authored_on` | 100% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |
| `age_at_chemo_stop` | 5492 | `patient_medications` | `end_date` OR last dose | 90% STRUCTURED | None | ⏳ TODO |
| `chemotherapy_type` | Protocol vs standard | N/A | Oncology notes | NARRATIVE ONLY | None | 🔴 BRIM |
| `protocol_name` | CCG-A9952 | `care_plan` OR notes | `title` OR narrative | HYBRID (20%) | None | 🔴 BRIM |
| **RADIATION** | | | | | | |
| `radiation` | Yes/No | `procedure` | CPT 77xxx COUNT > 0 | 100% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |
| `radiation_type` | Photons | `procedure` | `code.text` | HYBRID (60%) | None | ⏳ TODO |
| `radiation_site` | Focal/Tumor bed | `procedure` | `bodySite.text` | HYBRID (50%) | None | 🔴 BRIM |
| `total_radiation_dose` | 59.40 Gy | `observation` OR notes | `value` OR narrative | HYBRID (40%) | None | 🔴 BRIM |
| `age_at_radiation_start` | 5235 | `procedure` | `performed_period.start` | 100% STRUCTURED | None | ⏳ TODO |
| `age_at_radiation_stop` | 5278 | `procedure` | `performed_period.end` | 100% STRUCTURED | None | ⏳ TODO |
| **OTHER** | | | | | | |
| `treatment_status` | New/Modified | N/A | Timeline comparison | COMPLEX | None | ⏳ TODO |
| `reason_for_treatment_change` | Toxicities | N/A | Oncology notes | NARRATIVE ONLY | None | 🔴 BRIM |
| `autologous_stem_cell_transplant` | No | `procedure` | CPT 38241 | 100% STRUCTURED | None | ⏳ TODO |

**Assessment**:
- ✅ **63% extractable** from Athena (17/27 fields)
- 🟡 **15% hybrid** (4 fields: specimen origin, radiation details)
- 🔴 **BRIM required** (6 fields: extent of resection, protocol details, reasoning)
- 🎯 **Priority**: CRITICAL (chemotherapy filter blocking - fix immediately)
- 📝 **Actions**:
  1. **CRITICAL**: Expand chemotherapy filter to include vinblastine, selumetinib (10 min)
  2. Add chemo_stop_date extraction (10 min)
  3. Add radiation date extraction (10 min)
  4. Add autologous_stem_cell_transplant detection (5 min)

---

### CSV 4: concomitant_medications.csv
**Rows**: 9,548 (LARGEST) | **Columns**: 8 | **Completeness**: 100%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| `event_id` | ET_7DK4B210 | N/A | Generated (event timeline) | GENERATED | None | ⏳ TODO |
| `conmed_timepoint` | 6 Month Update | N/A | Calculated from event | CALCULATED | None | ⏳ TODO |
| `research_id` | C1277724 | N/A | Manual mapping | MANUAL | N/A | ⚠️ MANUAL |
| `form_conmed_number` | conmed_1 | N/A | Sequential numbering | GENERATED | None | ⏳ TODO |
| `age_at_conmed_date` | 2321 | `patient_medications` | `authored_on` | 100% STRUCTURED | None | ⏳ TODO |
| `rxnorm_cui` | 1116927 | `medication_code_coding` | `code` | 100% STRUCTURED | complete_medication_crosswalk.py | ✅ VALIDATED |
| `medication_name` | dexamethasone phosphate 4 MG/ML | `patient_medications` | `medication_name` | 100% STRUCTURED | complete_medication_crosswalk.py | ✅ VALIDATED |
| `conmed_routine` | Scheduled | `medication_request` | `dosage_instruction.timing` | 70% STRUCTURED | None | ⏳ TODO |

**Assessment**:
- ✅ **100% extractable** from Athena (medication data fully structured)
- ✅ **Existing validated script**: complete_medication_crosswalk.py (85-90% coverage)
- 🎯 **Priority**: LOW (already validated, just needs integration)
- 📝 **Actions**:
  1. Test complete_medication_crosswalk.py on C1277724 (5 min)
  2. Validate against 9,548-row gold standard (10 min)
  3. Add conmed_routine extraction if needed (10 min)

---

### CSV 5: molecular_characterization.csv
**Rows**: 52 | **Columns**: 2 | **Completeness**: 100%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| `research_id` | C1277724 | N/A | Manual mapping | MANUAL | N/A | ⚠️ MANUAL |
| `mutation` | KIAA1549-BRAF fusion | `observation` | `value_string` | 90% STRUCTURED | extract_structured_data.py | ✅ EXTRACTED |

**Assessment**:
- ✅ **100% extractable** from Athena (mutation text in Observation.valueString)
- ✅ **Already extracted**: BRAF fusion found in observation table
- ⚠️ **Gap**: Age at molecular testing not saved
- 🎯 **Priority**: LOW (mostly complete, add test ages)
- 📝 **Actions**:
  1. Add age_at_molecular_test extraction (5 min)
  2. Parse fusion partner names if needed (10 min)

---

### CSV 6: molecular_tests_performed.csv
**Rows**: 131 | **Columns**: 3 | **Completeness**: 100%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| `research_id` | C1277724 | N/A | Manual mapping | MANUAL | N/A | ⚠️ MANUAL |
| `assay` | Comprehensive Solid Tumor Panel | `molecular_tests` OR `observation` | `code.text` | 90% STRUCTURED | None | ⏳ TODO |
| `assay_type` | clinical/research | `diagnostic_report` | `category` | 70% STRUCTURED | None | ⏳ TODO |

**Assessment**:
- ✅ **90% extractable** from Athena (test names in molecular_tests table)
- 🎯 **Priority**: MEDIUM (test metadata useful for molecular analysis)
- 📝 **Actions**:
  1. Query molecular_tests table for assay names (10 min)
  2. Add assay_type classification logic (10 min)

---

### CSV 7: encounters.csv
**Rows**: 1,717 | **Columns**: 8 | **Completeness**: 97.75%

| CSV Column | Gold Standard Sample | Athena Table | Athena Field | Extractability | Existing Script | Status |
|------------|---------------------|--------------|--------------|----------------|-----------------|--------|
| `research_id` | C1277724 | N/A | Manual mapping | MANUAL | N/A | ⚠️ MANUAL |
| `event_id` | ET_7DK4B210 | N/A | Generated (event timeline) | GENERATED | None | ⏳ TODO |
| `age_at_encounter` | 2491 | `encounter` | `period.start` | 100% STRUCTURED | None | ⏳ TODO |
| `clinical_status` | Alive | `patient` | `deceased` | 100% STRUCTURED | None | ⏳ TODO |
| `follow_up_visit_status` | Visit Completed | `encounter` | `status` | 100% STRUCTURED | None | ⏳ TODO |
| `update_which_visit` | 6 Month Update | N/A | Calculated from diagnosis date | CALCULATED | None | ⏳ TODO |
| `tumor_status` | Stable Disease | N/A | Oncology notes | NARRATIVE ONLY | None | 🔴 BRIM |
| `orig_event_date_for_update_ordering_only` | 2321 | N/A | Event linkage | GENERATED | None | ⏳ TODO |

**Assessment**:
- ✅ **86% extractable** from Athena (6/7 fields, excluding tumor_status)
- ✅ **Framework exists**: COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md (412 lines)
- 🔴 **BRIM required**: tumor_status (oncology assessment)
- 🎯 **Priority**: MEDIUM (extract encounters, use BRIM for status)
- 📝 **Actions**:
  1. Convert COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md to script (20 min)
  2. Add visit type calculation logic (10 min)

---

### CSV 8-18: Remaining CSVs (Quick Assessment)

| CSV | Rows | Key Fields | Structured % | Priority | Notes |
|-----|------|------------|--------------|----------|-------|
| **conditions_predispositions** | 1,064 | medical_conditions, cancer_predisposition | 70% | MEDIUM | Condition codes + narrative |
| **family_cancer_history** | 242 | family_member, cancer_type | 80% | LOW | Mostly structured |
| **hydrocephalus_details** | 277 | hydro_yn, surgical_management | 90% | MEDIUM | Procedure codes available |
| **imaging_clinical_related** | 4,035 | cortico tracking, imaging_status | 90% | HIGH | ✅ map_imaging_clinical_related_v4.py exists |
| **measurements** | 7,814 | height, weight, head_circumference | 95% | HIGH | ✅ map_measurements.py exists |
| **survival** | 189 | age_at_last_status, os_days, efs_days | 100% | HIGH | All calculated from dates |
| **ophthalmology_functional_asses** | 1,258 | visual_acuity, OCT measurements | 100% | LOW | Specialty-specific, all structured |
| **additional_fields** | 189 | NF1 screening variables | 90% | LOW | Custom fields |
| **braf_alteration_details** | 232 | BRAF fusion details | 80% | MEDIUM | Observation table |
| **data_dictionary** | 67 | Metadata | N/A | LOW | Reference only |
| **data_dictionary_custom_forms** | 111 | Metadata | N/A | LOW | Reference only |

---

## Phase 2: Materialized View Coverage Analysis

### Understanding of Athena Materialized Views

Based on documentation review, here are the materialized views I have comprehensive understanding of:

### ✅ CORE PATIENT DATA

#### 1. **patient_access** (Patient Demographics)
**Schema Understanding**: COMPLETE  
**Documentation**: ATHENA_ARCHITECTURE_CLARIFICATION.md

```sql
-- Known Fields:
id                    VARCHAR   -- FHIR Patient.id
patient_id            VARCHAR   -- MRN equivalent  
gender                VARCHAR   -- Patient.gender (male/female/other)
birth_date            DATE      -- Patient.birthDate
deceased              BOOLEAN   -- Patient.deceased[Boolean]
race                  VARCHAR   -- US Core extension (ombCategory)
ethnicity             VARCHAR   -- US Core extension (detailed)
name_family           VARCHAR   -- Patient.name.family
name_given            VARCHAR   -- Patient.name.given
address_city          VARCHAR   -- Patient.address.city
address_state         VARCHAR   -- Patient.address.state
address_postal_code   VARCHAR   -- Patient.address.postalCode
```

**Gold Standard Mapping**:
- demographics.legal_sex → `gender` (100%)
- demographics.race → `race` (100%)
- demographics.ethnicity → `ethnicity` (100%)
- All CSVs.clinical_status → `deceased` (100%)

**Coverage**: ✅ 100% for demographics

---

#### 2. **problem_list_diagnoses** (Curated Diagnosis View)
**Schema Understanding**: COMPLETE  
**Documentation**: COMPREHENSIVE_DIAGNOSTIC_CAPTURE_GUIDE.md

```sql
-- Known Fields:
patient_id            VARCHAR   -- Patient reference
diagnosis_name        VARCHAR   -- Condition.code.text (primary field)
onset_date_time       TIMESTAMP -- Condition.onsetDateTime
icd10_code            VARCHAR   -- Condition.code.coding (ICD-10)
snomed_code           VARCHAR   -- Condition.code.coding (SNOMED)
clinical_status       VARCHAR   -- Condition.clinicalStatus
verification_status   VARCHAR   -- Condition.verificationStatus
category              VARCHAR   -- Condition.category
is_primary            BOOLEAN   -- problem-list-item flag
```

**Gold Standard Mapping**:
- diagnosis.cns_integrated_diagnosis → `diagnosis_name` (95%)
- diagnosis.age_at_event_days → calculated from `onset_date_time` (100%)

**Coverage**: ✅ 95% for diagnosis names, 100% for dates

**Notes**: 
- This is a CURATED view (not raw condition table)
- Contains only problem list items (high-quality diagnoses)
- C1277724 validated: "Pilocytic astrocytoma of cerebellum" found

---

#### 3. **patient_medications** (Medication History)
**Schema Understanding**: COMPLETE  
**Documentation**: CONCOMITANT_MEDICATIONS_IMPLEMENTATION_GUIDE.md

```sql
-- Known Fields:
patient_id            VARCHAR   -- Patient reference
medication_name       VARCHAR   -- MedicationRequest.medicationCodeableConcept.text
rxnorm_code           VARCHAR   -- Medication.code.coding (RxNorm)
authored_on           TIMESTAMP -- MedicationRequest.authoredOn (start date)
end_date              TIMESTAMP -- MedicationRequest.dosageInstruction.timing.repeat.boundsPeriod.end
dose_value            DECIMAL   -- MedicationRequest.dosageInstruction.doseAndRate.dose
dose_unit             VARCHAR   -- Dose unit
route                 VARCHAR   -- MedicationRequest.dosageInstruction.route
frequency             VARCHAR   -- MedicationRequest.dosageInstruction.timing
status                VARCHAR   -- MedicationRequest.status (active/completed/stopped)
category              VARCHAR   -- MedicationRequest.category
intent                VARCHAR   -- MedicationRequest.intent
```

**Gold Standard Mapping**:
- treatments.chemotherapy_agents → `medication_name` (100% if filter correct)
- treatments.age_at_chemo_start → `authored_on` (100%)
- treatments.age_at_chemo_stop → `end_date` OR last dose (90%)
- concomitant_medications.* → ALL FIELDS (85-90% validated)

**Coverage**: ✅ 85-90% validated (complete_medication_crosswalk.py)

**Critical Gap**: Filter too narrow (missing vinblastine, selumetinib)

---

### ✅ PROCEDURES & SURGERIES

#### 4. **procedure** (All Procedures)
**Schema Understanding**: COMPLETE  
**Documentation**: COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md

```sql
-- Known Fields:
id                    VARCHAR   -- Procedure.id
patient_id            VARCHAR   -- Procedure.subject
performed_date_time   TIMESTAMP -- Procedure.performedDateTime OR performedPeriod.start
performed_period_end  TIMESTAMP -- Procedure.performedPeriod.end
status                VARCHAR   -- Procedure.status
category              VARCHAR   -- Procedure.category
outcome               VARCHAR   -- Procedure.outcome
encounter_id          VARCHAR   -- Procedure.encounter
```

**Gold Standard Mapping**:
- treatments.surgery → COUNT(*) WHERE cpt IN (61500-61576) (100%)
- treatments.age_at_surgery → `performed_date_time` (100%)
- treatments.age_at_radiation_start → `performed_date_time` WHERE cpt LIKE '77%' (100%)
- diagnosis.shunt_required → EXISTS WHERE cpt IN (62201, 62223) (100%)

**Coverage**: ✅ 100% for dates/occurrence, CPT codes in separate table

---

#### 5. **procedure_code_coding** (CPT/SNOMED Codes)
**Schema Understanding**: COMPLETE  
**Documentation**: COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md

```sql
-- Known Fields:
procedure_id          VARCHAR   -- FK to procedure.id
code                  VARCHAR   -- Procedure.code.coding.code (CPT code)
display               VARCHAR   -- Procedure.code.coding.display
system                VARCHAR   -- Code system (CPT, SNOMED, etc.)
```

**Gold Standard Mapping**:
- Surgery type classification → `code` (neurosurgery vs shunt vs other)
- Radiation detection → `code` LIKE '77%' (100%)
- Stem cell transplant → `code` = '38241' (100%)

**Coverage**: ✅ 100% for procedure classification

**Critical Gap**: Need CPT classification logic (RESECTION vs SHUNT)

---

#### 6. **procedure_body_site** (Surgical Sites)
**Schema Understanding**: PARTIAL  
**Documentation**: Referenced but not detailed

```sql
-- Known Fields:
procedure_id          VARCHAR   -- FK to procedure.id
body_site_text        VARCHAR   -- Procedure.bodySite.text
body_site_code        VARCHAR   -- Procedure.bodySite.coding.code (SNOMED)
```

**Gold Standard Mapping**:
- diagnosis.tumor_location → `body_site_text` (40% structured, 60% narrative)
- treatments.radiation_site → `body_site_text` (50% structured)

**Coverage**: 🟡 40-50% (often generic like "Brain", need narrative details)

---

### ✅ MOLECULAR & LAB DATA

#### 7. **observation** (Lab Results, Molecular Markers)
**Schema Understanding**: COMPLETE  
**Documentation**: Multiple references

```sql
-- Known Fields:
patient_id            VARCHAR   -- Observation.subject
code                  VARCHAR   -- Observation.code.coding.code (LOINC)
code_text             VARCHAR   -- Observation.code.text
value_string          VARCHAR   -- Observation.valueString (text results)
value_quantity        DECIMAL   -- Observation.valueQuantity.value
value_unit            VARCHAR   -- Observation.valueQuantity.unit
effective_date_time   TIMESTAMP -- Observation.effectiveDateTime
status                VARCHAR   -- Observation.status
category              VARCHAR   -- Observation.category (lab, vital-signs, imaging)
interpretation        VARCHAR   -- Observation.interpretation
```

**Gold Standard Mapping**:
- molecular_characterization.mutation → `value_string` (90% - contains "KIAA1549-BRAF fusion")
- measurements.height_cm → `value_quantity` WHERE code='height' (95%)
- measurements.weight_kg → `value_quantity` WHERE code='weight' (95%)
- treatments.total_radiation_dose → `value_quantity` (40% structured)

**Coverage**: ✅ 90% for molecular markers, 95% for anthropometrics

**C1277724 Validation**: BRAF fusion found in value_string

---

#### 8. **molecular_tests** (Genomic Testing)
**Schema Understanding**: PARTIAL  
**Documentation**: Referenced

```sql
-- Inferred Fields:
patient_id            VARCHAR   -- Patient reference
test_name             VARCHAR   -- DiagnosticReport.code.text
test_date             TIMESTAMP -- DiagnosticReport.effectiveDateTime
test_type             VARCHAR   -- Panel type (Fusion, Somatic, WGS)
```

**Gold Standard Mapping**:
- molecular_tests_performed.assay → `test_name` (90%)
- diagnosis.tumor_or_molecular_tests_performed → `test_name` (90%)

**Coverage**: 🟡 90% (need to validate table structure)

---

#### 9. **molecular_test_results** (Test Result Details)
**Schema Understanding**: PARTIAL  
**Documentation**: Referenced

```sql
-- Inferred Fields:
patient_id            VARCHAR   -- Patient reference
test_id               VARCHAR   -- FK to molecular_tests
result_text           VARCHAR   -- Detailed findings
genes_tested          VARCHAR   -- List of genes
mutations_found       VARCHAR   -- Specific mutations
```

**Gold Standard Mapping**:
- molecular_characterization.mutation → `mutations_found` (complementary to observation)

**Coverage**: 🟡 70% (overlap with observation table)

---

### ✅ ENCOUNTERS & VISITS

#### 10. **encounter** (Visit Tracking)
**Schema Understanding**: COMPLETE  
**Documentation**: COMPREHENSIVE_ENCOUNTERS_FRAMEWORK.md (412 lines)

```sql
-- Known Fields:
id                    VARCHAR   -- Encounter.id
patient_id            VARCHAR   -- Encounter.subject
period_start          TIMESTAMP -- Encounter.period.start
period_end            TIMESTAMP -- Encounter.period.end
status                VARCHAR   -- Encounter.status (finished, cancelled, etc.)
class_code            VARCHAR   -- Encounter.class (outpatient, inpatient, emergency)
type                  VARCHAR   -- Encounter.type
service_type          VARCHAR   -- Encounter.serviceType
participant_type      VARCHAR   -- Practitioner type
location              VARCHAR   -- Encounter.location
```

**Gold Standard Mapping**:
- encounters.age_at_encounter → `period_start` (100%)
- encounters.follow_up_visit_status → `status` (100%)
- encounters.update_which_visit → calculated from diagnosis date (100%)

**Coverage**: ✅ 100% (framework complete, needs script implementation)

**Validation**: 1,000+ encounters validated in fhir_athena_crosswalk

---

### ✅ CLINICAL DOCUMENTS

#### 11. **document_reference** (Clinical Note Metadata)
**Schema Understanding**: COMPLETE  
**Documentation**: METADATA_DRIVEN_ABSTRACTION_STRATEGY.md (713 lines)

```sql
-- Known Fields:
id                    VARCHAR   -- DocumentReference.id
patient_id            VARCHAR   -- DocumentReference.subject
document_type         VARCHAR   -- DocumentReference.type.coding.display
specialty             VARCHAR   -- Specialty extracted from type
created_date          TIMESTAMP -- DocumentReference.date
author                VARCHAR   -- DocumentReference.author
status                VARCHAR   -- DocumentReference.status
description           VARCHAR   -- DocumentReference.description
content_type          VARCHAR   -- DocumentReference.content.attachment.contentType
s3_url                VARCHAR   -- DocumentReference.content.attachment.url
document_size         INTEGER   -- Document size in bytes
```

**Gold Standard Mapping**:
- Used for document prioritization (not direct CSV mapping)
- Enables Tier 1/2/3 document classification
- 3,865 documents with metadata cataloged

**Coverage**: ✅ 100% for metadata (content retrieval via S3)

**Specialty Distribution**:
- Oncology: 246 docs (6.4%)
- Neurosurgery: 87 docs (2.3%)
- Ophthalmology: 18 docs (0.5%)

---

### ✅ RADIOLOGY IMAGING

#### 12. **radiology_imaging_mri** (MRI Procedures)
**Schema Understanding**: COMPLETE  
**Documentation**: IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md

```sql
-- Known Fields:
patient_id            VARCHAR   -- Patient reference
imaging_date          TIMESTAMP -- ImagingStudy.started OR DiagnosticReport.effectiveDateTime
modality              VARCHAR   -- ImagingStudy.modality (MRI, CT, PET, etc.)
body_site             VARCHAR   -- ImagingStudy.series.bodySite
accession_number      VARCHAR   -- ImagingStudy.accession
number_of_series      INTEGER   -- ImagingStudy.numberOfSeries
number_of_instances   INTEGER   -- ImagingStudy.numberOfInstances
```

**Gold Standard Mapping**:
- imaging_clinical_related.age_at_date_scan → `imaging_date` (100%)
- Used for temporal alignment with corticosteroid prescriptions

**Coverage**: ✅ 100% for imaging metadata

---

#### 13. **radiology_imaging_mri_results** (Radiology Reports)
**Schema Understanding**: COMPLETE  
**Documentation**: IMAGING_CLINICAL_RELATED_IMPLEMENTATION_GUIDE.md

```sql
-- Known Fields:
patient_id            VARCHAR   -- Patient reference
imaging_study_id      VARCHAR   -- FK to radiology_imaging_mri
report_text           VARCHAR   -- DiagnosticReport.conclusion OR presentedForm
impression            VARCHAR   -- Impression section
findings              VARCHAR   -- Findings section
comparison            VARCHAR   -- Comparison to prior
report_date           TIMESTAMP -- DiagnosticReport.issued
```

**Gold Standard Mapping**:
- imaging_clinical_related.imaging_clinical_status → extracted from `impression` (NARRATIVE)
- diagnosis.tumor_location → extracted from `findings` (HYBRID)
- encounters.tumor_status → extracted from `impression` (NARRATIVE)

**Coverage**: 🔴 0% structured (all narrative extraction via BRIM)

---

### ⚠️ ADDITIONAL TABLES (Understanding Partial/Incomplete)

#### 14. **condition** (All Diagnoses - Raw FHIR)
**Schema Understanding**: PARTIAL  
**Note**: problem_list_diagnoses is PREFERRED (curated subset)

```sql
-- Known Fields:
patient_id            VARCHAR
code_text             VARCHAR   -- Condition.code.text
onset_date_time       TIMESTAMP
clinical_status       VARCHAR
category              VARCHAR
body_site_text        VARCHAR   -- Condition.bodySite.text
stage_summary         VARCHAR   -- Condition.stage.summary.text (WHO grade?)
```

**Coverage**: Use problem_list_diagnoses instead (curated, higher quality)

---

#### 15. **condition_code_coding** (Diagnosis Codes)
**Schema Understanding**: PARTIAL

```sql
-- Known Fields:
condition_id          VARCHAR   -- FK to condition.id
code                  VARCHAR   -- ICD-10, SNOMED codes
display               VARCHAR
system                VARCHAR   -- http://hl7.org/fhir/sid/icd-10 or SNOMED
```

**Coverage**: Available but problem_list_diagnoses already has codes

---

#### 16. **medication_request** (Medication Orders - Raw FHIR)
**Schema Understanding**: PARTIAL  
**Note**: patient_medications is PREFERRED (flattened view)

**Coverage**: Use patient_medications instead (easier querying)

---

#### 17. **medication_code_coding** (RxNorm Codes)
**Schema Understanding**: COMPLETE  
**Documentation**: CONCOMITANT_MEDICATIONS_IMPLEMENTATION_GUIDE.md

```sql
-- Known Fields:
medication_request_id VARCHAR   -- FK to medication_request.id
code                  VARCHAR   -- RxNorm CUI
display               VARCHAR   -- Medication name
system                VARCHAR   -- http://www.nlm.nih.gov/research/umls/rxnorm
```

**Coverage**: ✅ 100% (used by complete_medication_crosswalk.py)

---

#### 18. **care_plan** (Treatment Plans)
**Schema Understanding**: MINIMAL

```sql
-- Inferred Fields:
patient_id            VARCHAR
title                 VARCHAR   -- CarePlan.title (protocol name?)
category              VARCHAR
status                VARCHAR
created               TIMESTAMP
```

**Gold Standard Mapping**:
- treatments.protocol_name → `title` (20% structured, 80% in notes)

**Coverage**: 🟡 20% (likely low utilization, most in narrative)

---

#### 19. **patient_extension** (US Core Extensions)
**Schema Understanding**: PARTIAL  
**Documentation**: ATHENA_ARCHITECTURE_CLARIFICATION.md

```sql
-- Known Fields:
patient_id            VARCHAR
extension_url         VARCHAR   -- Extension identifier
value_string          VARCHAR   -- Extension value (race/ethnicity text)
value_coding_code     VARCHAR   -- OMB category codes
value_coding_display  VARCHAR
```

**Gold Standard Mapping**:
- demographics.race → `value_string` WHERE url='race' (100%)
- demographics.ethnicity → `value_string` WHERE url='ethnicity' (100%)

**Coverage**: ✅ 100% for race/ethnicity (just needs extraction)

---

#### 20. **appointment** & **appointment_participant** (Scheduling)
**Schema Understanding**: MINIMAL

**Gold Standard Mapping**: Not directly used (encounter table sufficient)

**Coverage**: N/A (not required for current CSVs)

---

## Phase 3: Gap Prioritization & Implementation Plan

### 🔴 CRITICAL (Blocking Progress)

| Gap | CSV Impact | Fix Complexity | Time Estimate | Priority Score |
|-----|------------|----------------|---------------|----------------|
| **Chemotherapy filter expansion** | treatments.chemotherapy_agents | TRIVIAL | 10 min | 🔴 100 |

**Action**: Add vinblastine, selumetinib, carboplatin, cisplatin, lomustine, etc. to CHEMO_KEYWORDS list

**Expected Impact**: 33% → 100% chemotherapy agent recall

---

### 🟠 HIGH PRIORITY (Easy Wins - High Value)

| Gap | CSV Impact | Fix Complexity | Time Estimate | Priority Score |
|-----|------------|----------------|---------------|----------------|
| **Race/ethnicity extraction** | demographics.race, demographics.ethnicity | TRIVIAL | 10 min | 🟠 95 |
| **Chemotherapy stop dates** | treatments.age_at_chemo_stop | EASY | 10 min | 🟠 90 |
| **Molecular test ages** | molecular_characterization (age) | TRIVIAL | 5 min | 🟠 85 |
| **Shunt procedure extraction** | diagnosis.shunt_required | EASY | 10 min | 🟠 85 |
| **Encounter date extraction** | encounters.age_at_encounter | EASY | 15 min | 🟠 80 |

**Total Time**: ~50 minutes for 5 high-value extractions

---

### 🟡 MEDIUM PRIORITY (Framework → Script)

| Gap | CSV Impact | Fix Complexity | Time Estimate | Priority Score |
|-----|------------|----------------|---------------|----------------|
| **Encounters script** | encounters.* (7 fields) | MODERATE | 20 min | 🟡 75 |
| **Molecular tests extraction** | molecular_tests_performed.assay | MODERATE | 15 min | 🟡 70 |
| **Radiation date extraction** | treatments.radiation_start/stop | EASY | 10 min | 🟡 65 |
| **Stem cell transplant detection** | treatments.autologous_stem_cell_transplant | TRIVIAL | 5 min | 🟡 60 |
| **CPT classification logic** | Surgery type (RESECTION vs SHUNT) | MODERATE | 15 min | 🟡 75 |

**Total Time**: ~65 minutes for 5 moderate-complexity tasks

---

### 🔵 LOW PRIORITY (Advanced Features)

| Gap | CSV Impact | Fix Complexity | Time Estimate | Priority Score |
|-----|------------|----------------|---------------|----------------|
| **Event timeline generation** | event_id assignment across all CSVs | COMPLEX | 60 min | 🔵 50 |
| **Visit type calculation** | encounters.update_which_visit | MODERATE | 20 min | 🔵 45 |
| **Treatment status tracking** | treatments.treatment_status | COMPLEX | 30 min | 🔵 40 |
| **Conmed routine extraction** | concomitant_medications.conmed_routine | MODERATE | 10 min | 🔵 35 |

**Total Time**: ~120 minutes for 4 complex features

---

### 🔴 BRIM REQUIRED (Narrative-Only)

| Variable | CSV | Extraction Approach | Expected Accuracy |
|----------|-----|---------------------|-------------------|
| **extent_of_resection** | treatments | Operative notes → "gross total", "subtotal", "biopsy" | 75-85% |
| **tumor_status** | encounters | Oncology notes → "stable", "progressive", "responsive" | 70-80% |
| **imaging_clinical_status** | imaging_clinical_related | Radiology impressions → "stable", "improved", "worse" | 75-85% |
| **metastasis_location** | diagnosis | Radiology reports → "leptomeningeal", "spine", etc. | 70-80% |
| **site_of_progression** | diagnosis | Oncology notes → "local", "distant", "both" | 70-80% |
| **protocol_name** | treatments | Oncology notes → "CCG-A9952", trial names | 60-75% |
| **chemotherapy_type** | treatments | Oncology notes → "protocol" vs "standard" | 65-75% |
| **radiation_site_detail** | treatments | Radiation oncology notes → "CSI with boost", etc. | 70-80% |
| **total_radiation_dose** | treatments | Radiation oncology notes → "59.40 Gy", etc. | 65-75% |

**Strategy**: Use STRUCTURED-first instructions, fallback to narrative

---

## Summary: Extraction Capacity Assessment

### Overall Coverage by CSV

| CSV | Total Fields | 100% Structured | Hybrid | Narrative-Only | Athena Coverage |
|-----|--------------|-----------------|--------|----------------|-----------------|
| demographics | 4 | 3 | 0 | 0 | ✅ 100% |
| diagnosis | 20 | 9 | 3 | 3 | 🟡 60% |
| treatments | 27 | 17 | 4 | 6 | 🟡 63% |
| concomitant_medications | 8 | 6 | 1 | 0 | ✅ 88% |
| molecular_characterization | 2 | 2 | 0 | 0 | ✅ 100% |
| molecular_tests_performed | 3 | 2 | 1 | 0 | ✅ 90% |
| encounters | 8 | 6 | 0 | 1 | ✅ 86% |
| conditions_predispositions | 6 | 4 | 1 | 1 | 🟡 70% |
| family_cancer_history | 6 | 5 | 0 | 1 | ✅ 80% |
| hydrocephalus_details | 10 | 9 | 0 | 1 | ✅ 90% |
| imaging_clinical_related | 21 | 19 | 0 | 2 | ✅ 90% |
| measurements | 9 | 9 | 0 | 0 | ✅ 95% |
| survival | 6 | 6 | 0 | 0 | ✅ 100% |
| ophthalmology | 57 | 57 | 0 | 0 | ✅ 100% |

**Aggregate**:
- **Total Fields**: ~200 across 18 CSVs
- **100% Structured**: ~150 fields (75%)
- **Hybrid**: ~20 fields (10%)
- **Narrative-Only**: ~30 fields (15%)

### Recommended Implementation Sequence

**Week 1: Critical Gaps (Total: ~80 minutes)**
1. Expand chemotherapy filter (10 min) 🔴
2. Add race/ethnicity extraction (10 min) 🟠
3. Add chemo stop dates (10 min) 🟠
4. Add molecular test ages (5 min) 🟠
5. Add shunt extraction (10 min) 🟠
6. Add encounter extraction (15 min) 🟠
7. Add CPT classification (15 min) 🟡
8. Add radiation dates (10 min) 🟡
9. Test & validate (20 min)

**Expected Result**: 85-90% overall accuracy for structured fields

**Week 2: Framework Implementation (Total: ~120 minutes)**
1. Convert encounters framework to script (20 min)
2. Add event timeline logic (60 min)
3. Add visit type calculation (20 min)
4. Add treatment status tracking (30 min)
5. Test & validate (20 min)

**Expected Result**: 90-95% coverage for all structured+hybrid fields

**Week 3: BRIM Integration (Total: variable)**
1. Update BRIM variable instructions with STRUCTURED-first priority
2. Test Phase 1 BRIM extraction with limited documents
3. Validate against gold standard for narrative-only fields
4. Iterate based on accuracy metrics

**Expected Result**: 85-90% overall accuracy (structured + BRIM combined)

---

**Status**: Ready for implementation
**Next Action**: Begin Week 1 Critical Gaps
