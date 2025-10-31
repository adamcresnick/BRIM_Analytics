# Existing Athena View Schema Review

**Purpose**: Comprehensive review of existing view architectures to fully leverage thoughtful design features in the patient clinical journey timeline.

**Date**: 2025-10-30
**Reviewer**: Claude (Anthropic)

---

## Executive Summary

After reviewing the existing Athena view implementations (particularly [DATETIME_STANDARDIZED_VIEWS.sql:7104-7782](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql#L7104)), I've identified sophisticated architecture patterns that our timeline views should fully leverage:

### Key Discoveries

1. **5-Tier NLP Prioritization Framework** in v_pathology_diagnostics (lines 7338-7362)
   - Priority 1: Final surgical pathology reports (definitive diagnosis)
   - Priority 2: Surgical pathology reports (gross observations, preliminary)
   - Priority 3: Biopsy and specimen reports
   - Priority 4: Consultation notes
   - Priority 5: Other diagnostic reports

2. **Surgery-Anchored Temporal Metrics** (`days_from_surgery`) with ±7 day specimen linkage windows

3. **Multi-Source FHIR Integration** (4 diagnostic sources):
   - surgical_pathology_observation (structured data from Observation resources)
   - surgical_pathology_report (DiagnosticReport narratives)
   - pathology_document (DocumentReference for send-out analyses)
   - problem_list_diagnosis (Condition resources, ±180 day window)

4. **Document Category Classification** for NLP extraction type guidance

5. **Encounter-Based Linkage** with specimen → service_request → procedure chains

---

## View-by-View Schema Analysis

### 1. v_pathology_diagnostics (27 columns)

**Source**: DATETIME_STANDARDIZED_VIEWS.sql lines 7104-7782 (678 lines)

**Key Architecture Features**:

#### CTE Structure (Episodic Design)
```sql
1. tumor_surgeries        -- Anchor: validated v_procedures_tumor (is_tumor_surgery = TRUE)
2. surgical_specimens     -- ±7 day linkage to surgeries
3. surgical_pathology_observations  -- Observation resources via specimen_reference
4. surgical_pathology_narratives    -- DiagnosticReport resources via encounter
5. pathology_document_references    -- DocumentReference for send-outs
6. problem_list_diagnoses           -- Condition resources ±180 days
7. molecular_test_results           -- From molecular_tests materialized table
```

#### NLP Prioritization Framework (lines 7338-7382)
```sql
extraction_priority (INTEGER):
  1 = Final surgical pathology reports
      - LOWER(dr.code_text) LIKE '%surgical%pathology%final%'
      - LOWER(dr.code_text) LIKE '%pathology%final%diagnosis%'
      - drcc.code_coding_code = '34574-4' (LOINC)

  2 = Surgical pathology reports (gross observations)
      - LOWER(dr.code_text) LIKE '%surgical%pathology%'
      - drcc.code_coding_code = '24419-4' (LOINC: Surgical pathology gross)

  3 = Biopsy and specimen reports
      - LOWER(dr.code_text) LIKE '%biopsy%'

  4 = Consultation notes
      - LOWER(dr.code_text) LIKE '%pathology%consult%'

  5 = Other diagnostic reports

document_category (VARCHAR):
  - 'Final Pathology Report'
  - 'Surgical Pathology Report'
  - 'Gross Pathology Observation'
  - 'Biopsy Report'
  - 'Pathology Consultation'
  - 'Specimen Report'
  - 'Other Pathology Report'
```

#### Complete Column Schema
```sql
-- Patient & Temporal
patient_fhir_id                 VARCHAR
diagnostic_datetime             TIMESTAMP(3)  -- Full precision
diagnostic_date                 DATE          -- For date-based joins

-- Source Identification
diagnostic_source               VARCHAR       -- 4 possible values (see above)
source_id                       VARCHAR       -- FHIR resource ID
diagnostic_name                 VARCHAR       -- Code text / description

-- Diagnostic Content
component_name                  VARCHAR       -- Observation component OR document type
result_value                    VARCHAR       -- FREE TEXT pathology results (critical!)
diagnostic_category             VARCHAR       -- Generic categorization

-- Test Metadata
code                            VARCHAR       -- LOINC/coding system code
coding_system_code              VARCHAR       -- OID masterfile code
coding_system_name              VARCHAR       -- OID description
test_lab                        VARCHAR       -- Lab performing test
test_status                     VARCHAR       -- Result status
test_orderer                    VARCHAR       -- Ordering provider
component_count                 BIGINT        -- Number of components

-- Specimen Linkage
specimen_types                  VARCHAR       -- From specimen.type_text
specimen_sites                  VARCHAR       -- From specimen.collection_body_site_text
specimen_collection_datetime    TIMESTAMP(3)  -- When specimen collected

-- Procedure Linkage (surgery-anchored)
linked_procedure_id             VARCHAR       -- Procedure FHIR ID
linked_procedure_name           VARCHAR       -- Surgery name
linked_procedure_datetime       TIMESTAMP(3)  -- Surgery datetime

-- Encounter Linkage
encounter_id                    VARCHAR       -- Encounter FHIR ID

-- NLP PRIORITIZATION FRAMEWORK (our target for binary extraction!)
extraction_priority             INTEGER       -- 1-5 (1=highest priority)
document_category               VARCHAR       -- Classification for NLP type
days_from_surgery               BIGINT        -- Temporal relevance
```

#### Key Insights for Timeline Integration

**CRITICAL**: The `extraction_priority` field tells us **which documents most urgently need binary NLP extraction**. Our timeline-focused abstraction script should:
1. Query timeline for patients
2. Identify diagnosis events with `extraction_priority IN (1, 2)`
3. Pull corresponding `v_binary_files` records for MedGemma extraction
4. Prioritize documents with `days_from_surgery <= 7` (immediate post-op period)

---

### 2. v_chemo_treatment_episodes (36 columns)

**Source**: Likely in DATETIME_STANDARDIZED_VIEWS.sql or separate view file

#### Complete Column Schema (from Athena_Schema_10302025.csv)
```sql
-- Episode Identification
episode_id                      VARCHAR       -- Unique episode identifier
patient_fhir_id                 VARCHAR       -- Patient ID

-- Temporal Bounds
episode_start_datetime          TIMESTAMP(3)  -- Episode start
episode_end_datetime            TIMESTAMP(3)  -- Episode end
episode_duration_days           INTEGER       -- Calculated duration

-- Medication Summary
medication_count                INTEGER       -- # medications in episode
chemo_preferred_name            VARCHAR       -- Primary medication name(s)
chemo_drug_category             VARCHAR       -- Classification (Chemotherapy, Targeted Therapy, etc.)

-- Dosing Information
total_episode_dose              DOUBLE        -- Cumulative dose
total_episode_dose_unit         VARCHAR       -- Dose unit (mg, mg/m2, etc.)
max_single_dose                 DOUBLE        -- Largest single dose
max_single_dose_unit            VARCHAR       -- Unit for max dose

-- Administration Details
administration_count            INTEGER       -- # of administrations
unique_medication_codes         INTEGER       -- Distinct RxNorm codes
route_of_administration         VARCHAR       -- IV, PO, etc.

-- Clinical Context
indication                      VARCHAR       -- Treatment indication
treatment_line                  VARCHAR       -- First-line, second-line, etc.
treatment_intent                VARCHAR       -- Curative, palliative, etc.

-- Data Quality
completeness_score              DOUBLE        -- Episode data completeness
confidence_score                DOUBLE        -- Classification confidence

-- Temporal Quality
has_start_date                  BOOLEAN       -- Start date available
has_end_date                    BOOLEAN       -- End date available
is_ongoing                      BOOLEAN       -- Episode still active

-- Source Tracking
source_encounter_id             VARCHAR       -- Primary encounter
source_medication_ids           VARCHAR       -- Comma-separated medication IDs
```

#### Key Insights for Timeline Integration

**Episode-Level Aggregation**: This view pre-aggregates medications into treatment episodes. Our timeline should:
- Use `episode_start_datetime` and `episode_end_datetime` for TWO timeline events (start + end)
- Include `chemo_preferred_name` in event_description for regimen identification
- Leverage `treatment_line` to detect salvage therapy after progression
- Use `episode_duration_days` to identify unusually short/long treatment courses

---

### 3. v_radiation_episode_enrichment (49 columns)

**Source**: [V_RADIATION_EPISODE_ENRICHMENT.sql](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/testing/V_RADIATION_EPISODE_ENRICHMENT.sql) (331 lines, TESTING STATUS)

**NOTE**: This is the **enriched experimental version**. Production uses [V_RADIATION_TREATMENT_EPISODES.sql](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/V_RADIATION_TREATMENT_EPISODES.sql) (238 lines).

#### Complete Column Schema
```sql
-- Episode Identification
episode_id                      VARCHAR       -- Course ID
patient_fhir_id                 VARCHAR       -- Patient ID

-- Temporal Bounds
episode_start_date              DATE          -- First treatment date
episode_end_date                DATE          -- Last treatment date
episode_duration_days           INTEGER       -- Duration

-- Dose Summary
total_dose_cgy                  DOUBLE        -- Total dose in cGy
max_dose_cgy                    DOUBLE        -- Maximum dose
prescribed_dose_cgy             DOUBLE        -- Prescribed dose (from care plan)
num_fractions                   INTEGER       -- Number of fractions
avg_dose_per_fraction_cgy       DOUBLE        -- Average per fraction

-- Field/Site Information
radiation_fields                VARCHAR       -- Treatment fields (comma-separated)
num_unique_fields               INTEGER       -- Count of unique fields
radiation_sites                 VARCHAR       -- Body sites treated
primary_site                    VARCHAR       -- Primary treatment site

-- Appointment Summary (ENRICHMENT)
appointment_count               INTEGER       -- Total appointments
completed_appointment_count     INTEGER       -- Completed appointments
cancelled_appointment_count     INTEGER       -- Cancelled appointments
no_show_appointment_count       INTEGER       -- No-shows

-- Care Plan Metadata (ENRICHMENT)
care_plan_titles                VARCHAR       -- Care plan names
care_plan_intent                VARCHAR       -- Treatment intent
care_plan_categories            VARCHAR       -- Categories

-- Data Quality & Enrichment Scores
enrichment_score                DOUBLE        -- 0-1 enrichment completeness
dose_data_quality_score         DOUBLE        -- Dose information quality
temporal_data_quality_score     DOUBLE        -- Date information quality

-- Appointment Phase Classification (ENRICHMENT FEATURE!)
pre_treatment_appointments      INTEGER       -- Before episode_start_date
during_treatment_appointments   INTEGER       -- During episode
post_treatment_appointments     INTEGER       -- After episode_end_date
early_followup_appointments     INTEGER       -- 1-30 days post
late_followup_appointments      INTEGER       -- 31-90 days post

-- Source Tracking
source_observation_ids          VARCHAR       -- Observation resource IDs
source_care_plan_ids            VARCHAR       -- CarePlan resource IDs
source_appointment_ids          VARCHAR       -- Appointment resource IDs
```

#### Key Insights for Timeline Integration

**Appointment Phase Temporal Context**: The enrichment version adds appointment phase classification that's **PERFECT for our imaging phase linkage**:
- `pre_treatment_appointments` → baseline imaging expected
- `during_treatment_appointments` → on-treatment response assessment
- `post_treatment_appointments` → early response assessment

**Protocol Validation**: Use `total_dose_cgy` and `num_fractions` to validate against WHO 2021 standards:
- Medulloblastoma: 23.4-36 Gy CSI + 54 Gy boost
- HGG: 54-60 Gy in 1.8-2 Gy fractions
- Ependymoma: 54-59.4 Gy

---

### 4. v_procedures_tumor (62 columns)

**Source**: DATETIME_STANDARDIZED_VIEWS.sql or separate view file

#### Key Column Schema (Subset Most Relevant)
```sql
-- Procedure Identification
procedure_fhir_id               VARCHAR       -- Unique ID
patient_fhir_id                 VARCHAR       -- Patient ID
proc_performed_date_time        TIMESTAMP(3)  -- When performed

-- Procedure Classification
proc_code_text                  VARCHAR       -- Procedure description
surgery_type                    VARCHAR       -- resection, biopsy, debulking
surgery_extent                  VARCHAR       -- GTR, STR, partial, etc.
is_tumor_surgery                BOOLEAN       -- Validated tumor surgery flag
is_likely_performed             BOOLEAN       -- Confidence filter

-- Outcome Information (FREE TEXT!)
proc_outcome_text               VARCHAR       -- CRITICAL for EOR extraction
proc_status_reason_text         VARCHAR       -- Why status changed

-- Body Site Information
pbs_body_site_text              VARCHAR       -- Surgical site
surgical_site                   VARCHAR       -- Normalized site

-- Coding Information
cpt_code                        VARCHAR       -- CPT code
snomed_code                     VARCHAR       -- SNOMED code
epic_or_log_id                  VARCHAR       -- Epic procedure ID

-- Encounter Linkage
proc_encounter_reference        VARCHAR       -- Link to encounter

-- Classification Confidence
classification_confidence       VARCHAR       -- High, Medium, Low
confidence_score                DOUBLE        -- 0-1 score
```

#### Key Insights for Timeline Integration

**proc_outcome_text is GOLD**: This free text field contains EOR information that our free text pattern matching can extract:
```sql
WHEN LOWER(proc_outcome_text) SIMILAR TO '%(gross total|complete resection|gtr|100%)%'
    THEN 'GTR'
WHEN LOWER(proc_outcome_text) SIMILAR TO '%(subtotal|near total|ntr|90%|95%)%'
    THEN 'STR'
```

**is_tumor_surgery + is_likely_performed**: Pre-validated filter. Always use these flags to avoid non-tumor procedures.

---

### 5. v_imaging (18 columns)

**Source**: DATETIME_STANDARDIZED_VIEWS.sql

#### Complete Column Schema
```sql
-- Patient & Temporal
patient_fhir_id                 VARCHAR       -- Patient ID
imaging_date                    DATE          -- Study date
imaging_id                      VARCHAR       -- Unique imaging ID

-- Study Information
imaging_modality                VARCHAR       -- MRI, CT, PET, etc.
imaging_procedure               VARCHAR       -- Procedure description
category_text                   VARCHAR       -- Study category

-- Report Content (FREE TEXT!)
result_information              VARCHAR       -- Full radiology report text
result_display                  VARCHAR       -- Display text
report_conclusion               VARCHAR       -- CRITICAL: Radiologist impression
report_status                   VARCHAR       -- Final, preliminary, etc.

-- Diagnostic Report Linkage
result_diagnostic_report_id     VARCHAR       -- DiagnosticReport ID
diagnostic_report_id            VARCHAR       -- Alternative DR ID

-- Temporal Metadata
report_issued                   TIMESTAMP(3)  -- When report finalized
report_effective_period_start   TIMESTAMP(3)  -- Study start
report_effective_period_stop    TIMESTAMP(3)  -- Study end

-- Age Context
age_at_imaging_years            DOUBLE        -- Patient age at imaging
```

#### Key Insights for Timeline Integration

**report_conclusion is the KEY field**: This contains the radiologist's impression with keywords for response assessment:
- Progression: "increased", "enlarged", "new enhancement", "expansion", "worsening"
- Response: "decreased", "reduced", "smaller", "improved", "resolved"
- Stable: "unchanged", "stable", "no significant change"

**Multi-level text fields**: If `report_conclusion` is NULL, fall back to:
1. `result_information` (full report)
2. `result_display` (display text)

---

### 6. v_visits_unified (20 columns)

**Source**: DATETIME_STANDARDIZED_VIEWS.sql

#### Complete Column Schema
```sql
-- Patient & Temporal
patient_fhir_id                 VARCHAR       -- Patient ID
visit_date                      DATE          -- Visit date
visit_id                        VARCHAR       -- Visit identifier

-- Visit Classification
visit_type                      VARCHAR       -- Office visit, telehealth, etc.
appointment_type_text           VARCHAR       -- Appointment type description
service_category                VARCHAR       -- Service category

-- Status Information
appointment_status              VARCHAR       -- booked, arrived, fulfilled, etc.
encounter_status                VARCHAR       -- planned, in-progress, finished
cancelation_reason_text         VARCHAR       -- Why cancelled

-- Visit Context (FREE TEXT!)
appointment_description         VARCHAR       -- Visit description/purpose
visit_reason                    VARCHAR       -- Reason for visit

-- Participant Information
participant_type                VARCHAR       -- Provider type
participant_name                VARCHAR       -- Provider name

-- Location Information
location_name                   VARCHAR       -- Where visit occurred
service_type                    VARCHAR       -- Type of service

-- Temporal Details
visit_start_datetime            TIMESTAMP(3)  -- Visit start
visit_end_datetime              TIMESTAMP(3)  -- Visit end
visit_duration_minutes          INTEGER       -- Duration

-- Age Context
age_at_visit_days               INTEGER       -- Patient age in days
age_at_visit_years              DOUBLE        -- Patient age in years
```

#### Key Insights for Timeline Integration

**Visit Context**: Use `appointment_description` and `visit_reason` to identify clinically significant visits:
- Post-op follow-ups (within 30 days of surgery)
- Treatment planning visits (before chemo/radiation start)
- Response assessment visits (with imaging orders)

**Temporal Proximity to Treatments**: Link visits to nearby treatment events to understand treatment planning timeline.

---

## Recommendations for Timeline View Updates

### 1. Fully Leverage extraction_priority from v_pathology_diagnostics

**Current State**: Our timeline view doesn't include extraction_priority

**Recommended Update**:
```sql
-- In diagnosis_events CTE, add:
pd.extraction_priority,
pd.document_category,
pd.days_from_surgery
```

**Why**: This allows timeline-focused abstraction script to identify Priority 1-2 documents needing binary extraction.

### 2. Include Episode Enrichment Scores

**Current State**: We're not capturing data quality scores

**Recommended Update**:
```sql
-- In chemo/radiation events, add:
ce.completeness_score,
ce.confidence_score,
re.enrichment_score,
re.dose_data_quality_score
```

**Why**: Helps identify episodes with incomplete data needing manual review.

### 3. Add Age Context Consistently

**Current State**: Age fields inconsistently captured

**Recommended Update**:
```sql
-- Unified age_at_event column across all event types:
COALESCE(
    img.age_at_imaging_years,
    vis.age_at_visit_years,
    DATE_DIFF('year', patient_birth_date, event_date)
) as age_at_event_years
```

**Why**: Age-stratified analyses (pediatric vs AYA vs adult protocols).

### 4. Leverage Appointment Phase Classification from Enrichment View

**Current State**: We're using v_radiation_episode_enrichment but not fully leveraging appointment phase data

**Recommended Enhancement**:
```sql
-- Add appointment phase counts to radiation events:
re.pre_treatment_appointments,
re.during_treatment_appointments,
re.post_treatment_appointments,
re.early_followup_appointments,
re.late_followup_appointments
```

**Why**: Links imaging to treatment phases for response assessment.

---

## Integration Checklist for Timeline Views

- [x] Surgery-anchored temporal metrics (days_from_initial_surgery)
- [x] Multi-source diagnostic integration (4 sources from v_pathology_diagnostics)
- [ ] **TODO**: Add extraction_priority and document_category from v_pathology_diagnostics
- [ ] **TODO**: Add data quality/enrichment scores from episode views
- [x] Free text pattern matching for treatment response (report_conclusion, proc_outcome_text)
- [ ] **TODO**: Age context consistently across all event types
- [ ] **TODO**: Appointment phase linkage from v_radiation_episode_enrichment
- [x] Episode-level aggregation (chemo/radiation)
- [x] Treatment protocol validation (dose ranges)
- [x] Temporal phase classification (pre-op, post-op, surveillance, etc.)

---

## Next Steps

1. **Update V_PATIENT_CLINICAL_JOURNEY_TIMELINE.sql** to include extraction_priority, document_category from v_pathology_diagnostics
2. **Enhance run_timeline_focused_abstraction.py** to prioritize documents by extraction_priority
3. **Add data quality scores** to timeline for episode completeness tracking
4. **Test with 9-patient cohort** to validate all fields populated correctly

---

## References

- [DATETIME_STANDARDIZED_VIEWS.sql](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql) (7,782 lines)
- [V_RADIATION_EPISODE_ENRICHMENT.sql](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/testing/V_RADIATION_EPISODE_ENRICHMENT.sql) (331 lines, testing)
- [Athena_Schema_10302025.csv](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_10302025.csv) (Complete schema reference)
