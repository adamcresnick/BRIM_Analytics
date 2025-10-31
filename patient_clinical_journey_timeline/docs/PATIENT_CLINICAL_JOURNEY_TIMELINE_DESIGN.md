# Patient Clinical Journey Timeline View - Design Document

## Executive Summary

This document outlines the architecture for `v_patient_clinical_journey_timeline`, a comprehensive view that constructs chronological patient timelines integrating diagnosis, surgeries, treatments (chemotherapy and radiation), imaging studies, and clinical visits. The view is designed to support clinical decision-making, treatment response assessment, and research analysis for pediatric CNS tumor patients.

## Design Principles

1. **Chronological Unification**: All clinical events unified into a single temporal sequence per patient
2. **WHO 2021 Context-Aware**: Diagnosis classifications inform expected treatment paradigms
3. **Episode-Anchored**: Surgery dates serve as temporal anchors; treatments grouped into episodes
4. **Treatment Protocol Tracking**: Start/stop dates, regimens, doses, and temporal phases captured
5. **Molecular-Informed Expectations**: Molecular profiles (H3, IDH, BRAF) contextualize treatment patterns
6. **Multi-Modal Timeline**: Integrates procedures, medications, radiation, imaging, and encounters

---

## Data Sources

### Primary Views (5 Required + 1 Contextual)

| View | Purpose | Key Temporal Field(s) | Episode Concept |
|------|---------|----------------------|-----------------|
| **v_pathology_diagnostics** | Diagnosis events with WHO 2021 classifications | `diagnostic_date`, `days_from_surgery` | Surgery-anchored pathology |
| **v_procedures_tumor** | Surgical procedures (resections, biopsies) | `proc_performed_date_time` | Individual procedures |
| **v_chemo_treatment_episodes** | Chemotherapy treatment episodes | `episode_start_datetime`, `episode_end_datetime` | Medication episode grouping |
| **v_radiation_episode_enrichment** | Radiation episodes with appointment metadata | `episode_start_date`, `episode_end_date` | Radiation course grouping |
| **v_imaging** | Imaging studies (MRI, CT, PET) | `imaging_date` | Individual imaging events |
| **v_visits_unified** | Clinical visits and encounters | `visit_date` | Individual visit events |

### Schema Summary (185 Total Columns Available)

- **v_pathology_diagnostics**: 27 columns (diagnosis, molecular markers, document metadata)
- **v_procedures_tumor**: 62 columns (procedure details, classifications, Epic IDs)
- **v_chemo_treatment_episodes**: 36 columns (medications, regimens, doses, episode metrics)
- **v_radiation_episode_enrichment**: 49 columns (dose, fields, appointment phases, care plans)
- **v_imaging**: 18 columns (modality, findings, age at imaging)
- **v_visits_unified**: 20 columns (visit type, appointment status, encounter context)

---

## Event Type Taxonomy

### Core Event Types

| Event Type | Source View(s) | Temporal Granularity | Episode Association |
|------------|---------------|---------------------|---------------------|
| **diagnosis** | v_pathology_diagnostics | Date (diagnostic_date) | Links to surgery via days_from_surgery |
| **surgery** | v_procedures_tumor | DateTime (proc_performed_date_time) | Individual procedure IDs |
| **chemo_episode_start** | v_chemo_treatment_episodes | DateTime (episode_start_datetime) | episode_id |
| **chemo_episode_end** | v_chemo_treatment_episodes | DateTime (episode_end_datetime) | episode_id |
| **radiation_episode_start** | v_radiation_episode_enrichment | Date (episode_start_date) | episode_id |
| **radiation_episode_end** | v_radiation_episode_enrichment | Date (episode_end_date) | episode_id |
| **imaging** | v_imaging | Date (imaging_date) | Individual imaging events |
| **visit** | v_visits_unified | Date (visit_date) | Individual visit IDs |

### Event Metadata Structure

Each event in the timeline includes:
```sql
- patient_fhir_id          -- Patient identifier
- event_date               -- Normalized date (DATE type)
- event_datetime           -- Full timestamp where available (TIMESTAMP type)
- event_type               -- From taxonomy above
- event_subtype            -- Detailed classification (e.g., 'GTR', 'STR', 'biopsy')
- event_description        -- Human-readable summary
- event_id                 -- Source record identifier
- source_view              -- Originating view name
- episode_id               -- For episodic events (chemo, radiation)
- days_from_initial_surgery -- Temporal offset from first tumor surgery
- age_at_event_years       -- Patient age (where available)
```

---

## WHO 2021 Treatment Paradigm Integration

### Treatment Context by Diagnosis

Based on the molecular classification from v_pathology_diagnostics, we can contextualize expected treatments:

#### Low-Grade Gliomas (WHO Grade 1-2)
**Molecular Profiles**: BRAF V600E mutation, BRAF fusion/duplication, NF1-associated
**Expected Timeline Pattern**:
1. **Surgery**: GTR preferred (event_subtype = 'GTR' or 'complete_resection')
2. **Watch-and-Wait**: If GTR achieved - expect imaging surveillance without immediate adjuvant therapy
3. **Chemotherapy**: If residual/progressive - carboplatin/vincristine (look for these in chemo_preferred_name)
4. **Targeted Therapy**: BRAF V600E → dabrafenib/trametinib (for recurrent/progressive)
5. **Radiation**: Reserved for recurrent disease after chemo failure

#### High-Grade Gliomas (WHO Grade 3-4)
**Molecular Profiles**: H3 K27-altered, H3 G34-mutant, IDH-wildtype
**Expected Timeline Pattern**:
1. **Surgery**: Maximal safe resection
2. **Radiation**: Post-op (typically 54 Gy in 30 fractions) - check total_dose_cgy ≈ 5400
3. **Chemotherapy**: Concurrent/adjuvant temozolomide OR clinical trial agents
4. **Imaging**: Baseline within 48h post-op, then q3 months during active treatment

#### Medulloblastoma (Embryonal Tumors)
**Molecular Subgroups**: WNT, SHH, Group 3, Group 4
**Expected Timeline Pattern**:
1. **Surgery**: Maximal resection
2. **Radiation**: Craniospinal irradiation (CSI) - standard risk: 23.4 Gy CSI + 54 Gy boost
3. **Chemotherapy**: Multi-agent (vincristine, cisplatin, cyclophosphamide, etc.)
4. **Timing**: Radiation typically starts 28-35 days post-surgery
5. **Surveillance**: MRI spine + brain q3-4 months year 1-2

#### Ependymoma
**Molecular Classes**: PFA, PFB (posterior fossa), ST-RELA, ST-YAP1 (supratentorial)
**Expected Timeline Pattern**:
1. **Surgery**: GTR critical for prognosis
2. **Radiation**: Focal 54-59.4 Gy (if GTR) or 59.4 Gy (if STR) - NO chemotherapy for localized
3. **Second-Look Surgery**: If STR initially, often attempt second resection before radiation
4. **Chemotherapy**: Reserved for metastatic or very young children (<12-18 months)

---

## Timeline Construction Logic

### Step 1: Identify Index Surgery (Temporal Anchor)

```sql
WITH patient_index_surgery AS (
    SELECT
        patient_fhir_id,
        MIN(proc_performed_date_time) as initial_surgery_datetime,
        CAST(MIN(proc_performed_date_time) AS DATE) as initial_surgery_date
    FROM fhir_prd_db.v_procedures_tumor
    WHERE is_tumor_surgery = true
        AND surgery_type IN ('resection', 'biopsy', 'debulking')
    GROUP BY patient_fhir_id
)
```

### Step 2: Normalize All Events to Common Schema

Create CTEs for each event type, transforming to unified structure:

```sql
-- Diagnosis Events
diagnosis_events AS (
    SELECT
        pd.patient_fhir_id,
        CAST(pd.diagnostic_date AS DATE) as event_date,
        CAST(pd.diagnostic_date AS TIMESTAMP) as event_datetime,
        'diagnosis' as event_type,
        pd.diagnostic_source as event_subtype,
        CONCAT(pd.diagnostic_name,
               CASE WHEN pd.component_name IS NOT NULL
                    THEN ' - ' || pd.component_name || ': ' || pd.result_value
                    END) as event_description,
        pd.source_id as event_id,
        'v_pathology_diagnostics' as source_view,
        NULL as episode_id,
        pd.days_from_surgery,
        pd.extraction_priority as priority_score,
        pd.diagnostic_category,
        pd.document_category
    FROM fhir_prd_db.v_pathology_diagnostics pd
),

-- Surgery Events
surgery_events AS (
    SELECT
        pt.patient_fhir_id,
        CAST(pt.proc_performed_date_time AS DATE) as event_date,
        pt.proc_performed_date_time as event_datetime,
        'surgery' as event_type,
        pt.surgery_type as event_subtype,
        CONCAT(pt.proc_code_text,
               ' (', pt.surgery_extent,
               CASE WHEN pt.is_tumor_surgery THEN ', tumor surgery' ELSE '' END,
               ')') as event_description,
        pt.procedure_fhir_id as event_id,
        'v_procedures_tumor' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, CAST(pt.proc_performed_date_time AS DATE)) as days_from_initial_surgery,
        NULL as priority_score,
        pt.procedure_category,
        NULL as document_category
    FROM fhir_prd_db.v_procedures_tumor pt
    LEFT JOIN patient_index_surgery pis ON pt.patient_fhir_id = pis.patient_fhir_id
    WHERE pt.is_tumor_surgery = true OR pt.surgery_type IS NOT NULL
),

-- Chemotherapy Episode Events (START and END)
chemo_start_events AS (
    SELECT
        ce.patient_fhir_id,
        CAST(ce.episode_start_datetime AS DATE) as event_date,
        ce.episode_start_datetime as event_datetime,
        'chemo_episode_start' as event_type,
        'treatment_initiation' as event_subtype,
        CONCAT('Chemotherapy started: ', ce.chemo_preferred_name,
               ' (', ce.medication_count, ' medications, ',
               ce.episode_duration_days, ' days)') as event_description,
        ce.episode_id as event_id,
        'v_chemo_treatment_episodes' as source_view,
        ce.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, CAST(ce.episode_start_datetime AS DATE)) as days_from_initial_surgery,
        NULL as priority_score,
        ce.chemo_drug_category as event_category,
        NULL as document_category
    FROM fhir_prd_db.v_chemo_treatment_episodes ce
    LEFT JOIN patient_index_surgery pis ON ce.patient_fhir_id = pis.patient_fhir_id
),

chemo_end_events AS (
    SELECT
        ce.patient_fhir_id,
        CAST(ce.episode_end_datetime AS DATE) as event_date,
        ce.episode_end_datetime as event_datetime,
        'chemo_episode_end' as event_type,
        'treatment_completion' as event_subtype,
        CONCAT('Chemotherapy completed: ', ce.chemo_preferred_name,
               ' (total dose: ', ce.total_episode_dose, ' ', ce.total_episode_dose_unit, ')') as event_description,
        ce.episode_id as event_id,
        'v_chemo_treatment_episodes' as source_view,
        ce.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, CAST(ce.episode_end_datetime AS DATE)) as days_from_initial_surgery,
        NULL as priority_score,
        ce.chemo_drug_category as event_category,
        NULL as document_category
    FROM fhir_prd_db.v_chemo_treatment_episodes ce
    LEFT JOIN patient_index_surgery pis ON ce.patient_fhir_id = pis.patient_fhir_id
),

-- Radiation Episode Events (START and END)
radiation_start_events AS (
    SELECT
        re.patient_fhir_id,
        re.episode_start_date as event_date,
        CAST(re.episode_start_date AS TIMESTAMP) as event_datetime,
        'radiation_episode_start' as event_type,
        'treatment_initiation' as event_subtype,
        CONCAT('Radiation started: ', re.total_dose_cgy, ' cGy planned',
               ' (', re.num_unique_fields, ' fields)') as event_description,
        re.episode_id as event_id,
        'v_radiation_episode_enrichment' as source_view,
        re.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, re.episode_start_date) as days_from_initial_surgery,
        re.enrichment_score as priority_score,
        re.radiation_fields as event_category,
        NULL as document_category
    FROM fhir_prd_db.v_radiation_episode_enrichment re
    LEFT JOIN patient_index_surgery pis ON re.patient_fhir_id = pis.patient_fhir_id
),

radiation_end_events AS (
    SELECT
        re.patient_fhir_id,
        re.episode_end_date as event_date,
        CAST(re.episode_end_date AS TIMESTAMP) as event_datetime,
        'radiation_episode_end' as event_type,
        'treatment_completion' as event_subtype,
        CONCAT('Radiation completed: ', re.total_dose_cgy, ' cGy delivered',
               ' in ', DATE_DIFF('day', re.episode_start_date, re.episode_end_date), ' days') as event_description,
        re.episode_id as event_id,
        'v_radiation_episode_enrichment' as source_view,
        re.episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, re.episode_end_date) as days_from_initial_surgery,
        re.enrichment_score as priority_score,
        re.radiation_fields as event_category,
        NULL as document_category
    FROM fhir_prd_db.v_radiation_episode_enrichment re
    LEFT JOIN patient_index_surgery pis ON re.patient_fhir_id = pis.patient_fhir_id
),

-- Imaging Events
imaging_events AS (
    SELECT
        im.patient_fhir_id,
        im.imaging_date as event_date,
        CAST(im.imaging_date AS TIMESTAMP) as event_datetime,
        'imaging' as event_type,
        im.imaging_modality as event_subtype,
        CONCAT(im.imaging_procedure,
               CASE WHEN im.report_conclusion IS NOT NULL
                    THEN ' - ' || im.report_conclusion
                    END) as event_description,
        im.imaging_id as event_id,
        'v_imaging' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, im.imaging_date) as days_from_initial_surgery,
        NULL as priority_score,
        im.imaging_modality as event_category,
        NULL as document_category
    FROM fhir_prd_db.v_imaging im
    LEFT JOIN patient_index_surgery pis ON im.patient_fhir_id = pis.patient_fhir_id
),

-- Visit Events
visit_events AS (
    SELECT
        vu.patient_fhir_id,
        vu.visit_date as event_date,
        CAST(vu.visit_date AS TIMESTAMP) as event_datetime,
        'visit' as event_type,
        vu.visit_type as event_subtype,
        CONCAT(vu.visit_type,
               ' (', vu.appointment_status, ', ', vu.encounter_status, ')') as event_description,
        vu.visit_id as event_id,
        'v_visits_unified' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, vu.visit_date) as days_from_initial_surgery,
        NULL as priority_score,
        vu.visit_type as event_category,
        NULL as document_category
    FROM fhir_prd_db.v_visits_unified vu
    LEFT JOIN patient_index_surgery pis ON vu.patient_fhir_id = pis.patient_fhir_id
)
```

### Step 3: Union All Events

```sql
unified_timeline AS (
    SELECT * FROM diagnosis_events
    UNION ALL
    SELECT * FROM surgery_events
    UNION ALL
    SELECT * FROM chemo_start_events
    UNION ALL
    SELECT * FROM chemo_end_events
    UNION ALL
    SELECT * FROM radiation_start_events
    UNION ALL
    SELECT * FROM radiation_end_events
    UNION ALL
    SELECT * FROM imaging_events
    UNION ALL
    SELECT * FROM visit_events
)
```

### Step 4: Add Sequence Numbering and Phase Classification

```sql
timeline_sequenced AS (
    SELECT
        ut.*,
        ROW_NUMBER() OVER (
            PARTITION BY ut.patient_fhir_id
            ORDER BY ut.event_date, ut.event_datetime, ut.event_type
        ) as event_sequence_number,

        -- Classify temporal phase relative to initial surgery
        CASE
            WHEN ut.days_from_initial_surgery < 0 THEN 'pre_surgery'
            WHEN ut.days_from_initial_surgery = 0 THEN 'surgery_day'
            WHEN ut.days_from_initial_surgery BETWEEN 1 AND 30 THEN 'early_post_op'
            WHEN ut.days_from_initial_surgery BETWEEN 31 AND 90 THEN 'adjuvant_treatment_window'
            WHEN ut.days_from_initial_surgery BETWEEN 91 AND 365 THEN 'active_treatment_phase'
            WHEN ut.days_from_initial_surgery > 365 THEN 'surveillance_phase'
            ELSE 'unknown_phase'
        END as treatment_phase,

        -- Calculate time to next event
        LEAD(ut.event_date) OVER (
            PARTITION BY ut.patient_fhir_id
            ORDER BY ut.event_date, ut.event_datetime
        ) as next_event_date,

        DATE_DIFF('day',
            ut.event_date,
            LEAD(ut.event_date) OVER (
                PARTITION BY ut.patient_fhir_id
                ORDER BY ut.event_date, ut.event_datetime
            )
        ) as days_to_next_event

    FROM unified_timeline ut
)
```

---

## Treatment Protocol Detection

### Radiation Dose Validation

Using WHO 2021 standards to flag potential protocol deviations:

```sql
radiation_protocol_check AS (
    SELECT
        re.patient_fhir_id,
        re.episode_id,
        re.total_dose_cgy,

        -- Standard pediatric protocols
        CASE
            WHEN re.total_dose_cgy BETWEEN 5300 AND 5500 THEN 'Standard 54 Gy (typical HGG/ependymoma)'
            WHEN re.total_dose_cgy BETWEEN 5900 AND 6000 THEN 'High-dose 59.4 Gy (ependymoma STR)'
            WHEN re.total_dose_cgy BETWEEN 2300 AND 2400 THEN 'CSI standard-risk (medulloblastoma)'
            WHEN re.total_dose_cgy BETWEEN 3500 AND 3700 THEN 'CSI high-risk (medulloblastoma)'
            WHEN re.total_dose_cgy < 5000 THEN 'Low-dose protocol (LGG or palliative)'
            ELSE 'Non-standard dosing'
        END as radiation_protocol_classification,

        -- Expected based on diagnosis
        pd.diagnostic_name,
        CASE
            WHEN pd.diagnostic_name LIKE '%medulloblastoma%' AND re.total_dose_cgy NOT BETWEEN 2300 AND 5500
                THEN 'Potential protocol deviation: medulloblastoma typically 23.4-54 Gy'
            WHEN pd.diagnostic_name LIKE '%ependymoma%' AND re.total_dose_cgy NOT BETWEEN 5400 AND 6000
                THEN 'Potential protocol deviation: ependymoma typically 54-59.4 Gy'
            WHEN pd.diagnostic_name LIKE '%high-grade glioma%' AND re.total_dose_cgy NOT BETWEEN 5400 AND 6000
                THEN 'Potential protocol deviation: HGG typically 54-60 Gy'
            ELSE NULL
        END as protocol_deviation_flag

    FROM fhir_prd_db.v_radiation_episode_enrichment re
    LEFT JOIN fhir_prd_db.v_pathology_diagnostics pd
        ON re.patient_fhir_id = pd.patient_fhir_id
        AND pd.extraction_priority = 1 -- Highest priority diagnosis
)
```

### Chemotherapy Regimen Detection

```sql
chemo_regimen_classification AS (
    SELECT
        ce.patient_fhir_id,
        ce.episode_id,
        ce.chemo_preferred_name,

        -- Standard pediatric CNS tumor regimens
        CASE
            WHEN LOWER(ce.chemo_preferred_name) LIKE '%carboplatin%'
                 AND LOWER(ce.chemo_preferred_name) LIKE '%vincristine%'
                THEN 'Carboplatin/Vincristine (standard LGG)'
            WHEN LOWER(ce.chemo_preferred_name) LIKE '%temozolomide%'
                THEN 'Temozolomide (standard HGG adjuvant)'
            WHEN LOWER(ce.chemo_preferred_name) LIKE '%vincristine%'
                 AND LOWER(ce.chemo_preferred_name) LIKE '%cisplatin%'
                 AND LOWER(ce.chemo_preferred_name) LIKE '%cyclophosphamide%'
                THEN 'Multi-agent (medulloblastoma protocol)'
            WHEN LOWER(ce.chemo_preferred_name) LIKE '%dabrafenib%'
                 AND LOWER(ce.chemo_preferred_name) LIKE '%trametinib%'
                THEN 'Targeted BRAF V600E therapy'
            ELSE 'Other/non-standard regimen'
        END as regimen_classification

    FROM fhir_prd_db.v_chemo_treatment_episodes ce
)
```

---

## Output Schema

### Final View Columns

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_patient_clinical_journey_timeline AS
SELECT
    -- Patient identifiers
    ts.patient_fhir_id,
    ts.event_sequence_number,

    -- Temporal fields
    ts.event_date,
    ts.event_datetime,
    ts.days_from_initial_surgery,
    ts.treatment_phase,
    ts.days_to_next_event,

    -- Event classification
    ts.event_type,
    ts.event_subtype,
    ts.event_description,
    ts.event_category,

    -- Source tracking
    ts.event_id,
    ts.source_view,
    ts.episode_id,

    -- Priority/Quality
    ts.priority_score,
    ts.document_category,

    -- Diagnosis context (from v_pathology_diagnostics)
    pd.diagnostic_name as patient_diagnosis,
    pd.diagnostic_category as diagnosis_category,
    pd.component_name as molecular_marker,
    pd.result_value as molecular_result,

    -- Protocol context
    rpc.radiation_protocol_classification,
    rpc.protocol_deviation_flag as radiation_protocol_deviation,
    crc.regimen_classification as chemo_regimen_type,

    -- Age context
    COALESCE(
        img.age_at_imaging_years,
        vis.age_at_visit_days / 365.25,
        -- Add other age calculations as needed
        NULL
    ) as age_at_event_years

FROM timeline_sequenced ts

-- Join diagnosis context (highest priority diagnosis per patient)
LEFT JOIN (
    SELECT DISTINCT
        patient_fhir_id,
        FIRST_VALUE(diagnostic_name) OVER (PARTITION BY patient_fhir_id ORDER BY extraction_priority) as diagnostic_name,
        FIRST_VALUE(diagnostic_category) OVER (PARTITION BY patient_fhir_id ORDER BY extraction_priority) as diagnostic_category,
        FIRST_VALUE(component_name) OVER (PARTITION BY patient_fhir_id ORDER BY extraction_priority) as component_name,
        FIRST_VALUE(result_value) OVER (PARTITION BY patient_fhir_id ORDER BY extraction_priority) as result_value
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE extraction_priority IS NOT NULL
) pd ON ts.patient_fhir_id = pd.patient_fhir_id

-- Join protocol checks
LEFT JOIN radiation_protocol_check rpc
    ON ts.episode_id = rpc.episode_id
    AND ts.event_type IN ('radiation_episode_start', 'radiation_episode_end')
LEFT JOIN chemo_regimen_classification crc
    ON ts.episode_id = crc.episode_id
    AND ts.event_type IN ('chemo_episode_start', 'chemo_episode_end')

-- Join age context from source views
LEFT JOIN fhir_prd_db.v_imaging img
    ON ts.event_id = img.imaging_id AND ts.source_view = 'v_imaging'
LEFT JOIN fhir_prd_db.v_visits_unified vis
    ON ts.event_id = vis.visit_id AND ts.source_view = 'v_visits_unified'

ORDER BY ts.patient_fhir_id, ts.event_sequence_number;
```

---

## Treatment Response Detection Using Free Text Fields

### Available Free Text Fields by View

| View | Free Text Column | Content Type | Use for Response Assessment |
|------|-----------------|--------------|----------------------------|
| **v_imaging** | `report_conclusion` | Radiologist impression/summary | Tumor size changes, enhancement patterns, progression/response keywords |
| **v_imaging** | `result_display` | Result display text | Additional findings |
| **v_imaging** | `result_information` | Structured result info | Coded findings |
| **v_procedures_tumor** | `proc_outcome_text` | Surgical outcome narrative | Extent of resection, complications, residual tumor |
| **v_procedures_tumor** | `proc_code_text` | Procedure description | Procedure type details |
| **v_visits_unified** | `appointment_description` | Visit description | Visit purpose, clinical context |
| **v_visits_unified** | `cancelation_reason_text` | Cancelation reasons | Treatment interruptions |

### Response Assessment Keywords and Patterns

Based on standard RANO (Response Assessment in Neuro-Oncology) criteria and clinical practice:

#### Progression Indicators (in report_conclusion)
```sql
-- Regex patterns for progression detection
progression_patterns AS (
    SELECT
        patient_fhir_id,
        imaging_date,
        report_conclusion,
        CASE
            WHEN LOWER(report_conclusion) SIMILAR TO '%(increas|enlarg|expan|grow|worsen|progress|new enhanc|new lesion)%'
                THEN 'progression_suspected'
            WHEN LOWER(report_conclusion) SIMILAR TO '%(recur|new tumor|new mass)%'
                THEN 'recurrence_suspected'
            ELSE NULL
        END as progression_flag
    FROM fhir_prd_db.v_imaging
    WHERE report_conclusion IS NOT NULL
)
```

#### Response Indicators (in report_conclusion)
```sql
response_patterns AS (
    SELECT
        patient_fhir_id,
        imaging_date,
        report_conclusion,
        CASE
            WHEN LOWER(report_conclusion) SIMILAR TO '%(decreas|reduc|shrink|smaller|improv|resolv)%'
                THEN 'response_suspected'
            WHEN LOWER(report_conclusion) SIMILAR TO '%(stable|unchanged|no change|no significant change)%'
                THEN 'stable_disease'
            WHEN LOWER(report_conclusion) SIMILAR TO '%(no evidence|no residual|complete respon)%'
                THEN 'complete_response_suspected'
            ELSE NULL
        END as response_flag
    FROM fhir_prd_db.v_imaging
    WHERE report_conclusion IS NOT NULL
)
```

#### Surgical Outcome Assessment (in proc_outcome_text)
```sql
surgical_outcome_assessment AS (
    SELECT
        patient_fhir_id,
        proc_performed_date_time,
        proc_outcome_text,
        CASE
            WHEN LOWER(proc_outcome_text) SIMILAR TO '%(gross total|complete resection|gtr|100%)%'
                THEN 'GTR'
            WHEN LOWER(proc_outcome_text) SIMILAR TO '%(subtotal|near total|ntr|90%|95%)%'
                THEN 'STR'
            WHEN LOWER(proc_outcome_text) SIMILAR TO '%(partial|incomplete)%'
                THEN 'partial_resection'
            WHEN LOWER(proc_outcome_text) SIMILAR TO '%(biopsy only)%'
                THEN 'biopsy'
            ELSE 'unspecified_extent'
        END as resection_extent_from_text,

        CASE
            WHEN LOWER(proc_outcome_text) SIMILAR TO '%(residual|remaining tumor|left behind)%'
                THEN true
            ELSE false
        END as residual_tumor_mentioned
    FROM fhir_prd_db.v_procedures_tumor
    WHERE proc_outcome_text IS NOT NULL
)
```

### Treatment Response Timeline Construction

Enhanced timeline with response assessment integrated:

```sql
-- Add imaging with response assessment
imaging_events_with_response AS (
    SELECT
        im.patient_fhir_id,
        im.imaging_date as event_date,
        CAST(im.imaging_date AS TIMESTAMP) as event_datetime,
        'imaging' as event_type,
        im.imaging_modality as event_subtype,

        -- Enhanced description with response flag
        CONCAT(
            im.imaging_procedure,
            CASE WHEN im.report_conclusion IS NOT NULL
                 THEN ' - ' || im.report_conclusion
                 END,
            CASE
                WHEN prog.progression_flag IS NOT NULL
                    THEN ' [' || prog.progression_flag || ']'
                WHEN resp.response_flag IS NOT NULL
                    THEN ' [' || resp.response_flag || ']'
                ELSE ''
            END
        ) as event_description,

        im.imaging_id as event_id,
        'v_imaging' as source_view,
        NULL as episode_id,
        DATE_DIFF('day', pis.initial_surgery_date, im.imaging_date) as days_from_initial_surgery,

        -- Response assessment fields
        prog.progression_flag,
        resp.response_flag,
        im.report_conclusion as free_text_content,

        NULL as priority_score,
        im.imaging_modality as event_category,
        NULL as document_category

    FROM fhir_prd_db.v_imaging im
    LEFT JOIN patient_index_surgery pis ON im.patient_fhir_id = pis.patient_fhir_id
    LEFT JOIN progression_patterns prog
        ON im.patient_fhir_id = prog.patient_fhir_id
        AND im.imaging_date = prog.imaging_date
    LEFT JOIN response_patterns resp
        ON im.patient_fhir_id = resp.patient_fhir_id
        AND im.imaging_date = resp.imaging_date
)
```

### Timeline-Based Response Analysis

#### Detect Imaging Sequences Around Treatment Episodes

```sql
-- Link imaging to nearest treatment episode
imaging_treatment_linkage AS (
    SELECT
        ie.patient_fhir_id,
        ie.event_date as imaging_date,
        ie.progression_flag,
        ie.response_flag,
        ie.report_conclusion,

        -- Find nearest radiation episode
        (SELECT episode_id
         FROM fhir_prd_db.v_radiation_episode_enrichment re
         WHERE re.patient_fhir_id = ie.patient_fhir_id
           AND ie.event_date BETWEEN
                DATE_ADD('day', -30, re.episode_start_date) AND
                DATE_ADD('day', 90, re.episode_end_date)
         ORDER BY ABS(DATE_DIFF('day', ie.event_date, re.episode_end_date))
         LIMIT 1
        ) as nearest_radiation_episode_id,

        -- Find nearest chemo episode
        (SELECT episode_id
         FROM fhir_prd_db.v_chemo_treatment_episodes ce
         WHERE ce.patient_fhir_id = ie.patient_fhir_id
           AND CAST(ie.event_date AS TIMESTAMP) BETWEEN
                CAST(DATE_ADD('day', -30, CAST(ce.episode_start_datetime AS DATE)) AS TIMESTAMP) AND
                CAST(DATE_ADD('day', 90, CAST(ce.episode_end_datetime AS DATE)) AS TIMESTAMP)
         ORDER BY ABS(DATE_DIFF('day', ie.event_date, CAST(ce.episode_end_datetime AS DATE)))
         LIMIT 1
        ) as nearest_chemo_episode_id,

        -- Classify imaging timing
        CASE
            WHEN ie.days_from_initial_surgery BETWEEN -7 AND 2
                THEN 'pre_op_baseline'
            WHEN ie.days_from_initial_surgery BETWEEN 0 AND 2
                THEN 'immediate_post_op'
            WHEN EXISTS (
                SELECT 1 FROM fhir_prd_db.v_radiation_episode_enrichment re
                WHERE re.patient_fhir_id = ie.patient_fhir_id
                  AND ie.event_date BETWEEN re.episode_start_date AND re.episode_end_date
            ) THEN 'during_radiation'
            WHEN EXISTS (
                SELECT 1 FROM fhir_prd_db.v_radiation_episode_enrichment re
                WHERE re.patient_fhir_id = ie.patient_fhir_id
                  AND ie.event_date BETWEEN
                      DATE_ADD('day', 1, re.episode_end_date) AND
                      DATE_ADD('day', 60, re.episode_end_date)
            ) THEN 'early_post_radiation'
            WHEN EXISTS (
                SELECT 1 FROM fhir_prd_db.v_chemo_treatment_episodes ce
                WHERE ce.patient_fhir_id = ie.patient_fhir_id
                  AND CAST(ie.event_date AS TIMESTAMP) BETWEEN
                      ce.episode_start_datetime AND ce.episode_end_datetime
            ) THEN 'during_chemo'
            WHEN ie.days_from_initial_surgery > 365
                THEN 'long_term_surveillance'
            ELSE 'surveillance'
        END as imaging_phase

    FROM imaging_events_with_response ie
)
```

#### Progression-Free Survival Calculation

```sql
-- Calculate time to first progression event
time_to_progression AS (
    SELECT
        patient_fhir_id,
        MIN(imaging_date) as first_progression_date,
        MIN(days_from_initial_surgery) as days_to_progression
    FROM imaging_treatment_linkage
    WHERE progression_flag IN ('progression_suspected', 'recurrence_suspected')
    GROUP BY patient_fhir_id
),

-- Join to treatment completion dates
pfs_analysis AS (
    SELECT
        pis.patient_fhir_id,
        pis.initial_surgery_date,

        -- Latest treatment completion
        GREATEST(
            COALESCE(MAX(CAST(ce.episode_end_datetime AS DATE)), pis.initial_surgery_date),
            COALESCE(MAX(re.episode_end_date), pis.initial_surgery_date)
        ) as treatment_completion_date,

        ttp.first_progression_date,
        ttp.days_to_progression,

        -- PFS from treatment completion to progression
        DATE_DIFF('day',
            GREATEST(
                COALESCE(MAX(CAST(ce.episode_end_datetime AS DATE)), pis.initial_surgery_date),
                COALESCE(MAX(re.episode_end_date), pis.initial_surgery_date)
            ),
            ttp.first_progression_date
        ) as pfs_days_from_treatment_completion,

        -- Flag if progressed
        CASE WHEN ttp.first_progression_date IS NOT NULL THEN true ELSE false END as progressed

    FROM patient_index_surgery pis
    LEFT JOIN fhir_prd_db.v_chemo_treatment_episodes ce
        ON pis.patient_fhir_id = ce.patient_fhir_id
    LEFT JOIN fhir_prd_db.v_radiation_episode_enrichment re
        ON pis.patient_fhir_id = re.patient_fhir_id
    LEFT JOIN time_to_progression ttp
        ON pis.patient_fhir_id = ttp.patient_fhir_id
    GROUP BY pis.patient_fhir_id, pis.initial_surgery_date, ttp.first_progression_date, ttp.days_to_progression
)
```

### Enhanced Timeline Schema with Response Fields

Update the final view to include response assessment:

```sql
-- Add these columns to the final timeline view
SELECT
    ts.*,

    -- Response assessment (for imaging events)
    itl.progression_flag,
    itl.response_flag,
    itl.imaging_phase,
    itl.nearest_radiation_episode_id as linked_radiation_episode,
    itl.nearest_chemo_episode_id as linked_chemo_episode,

    -- Surgical outcome (for surgery events)
    soa.resection_extent_from_text,
    soa.residual_tumor_mentioned,

    -- Free text content for further analysis
    ts.free_text_content,

    -- PFS metrics (patient-level, repeated for all events)
    pfs.days_to_progression as patient_days_to_progression,
    pfs.pfs_days_from_treatment_completion as patient_pfs_from_treatment,
    pfs.progressed as patient_has_progressed

FROM timeline_sequenced ts

LEFT JOIN imaging_treatment_linkage itl
    ON ts.event_id = itl.imaging_id AND ts.source_view = 'v_imaging'
LEFT JOIN surgical_outcome_assessment soa
    ON ts.event_id = soa.procedure_fhir_id AND ts.source_view = 'v_procedures_tumor'
LEFT JOIN pfs_analysis pfs
    ON ts.patient_fhir_id = pfs.patient_fhir_id

ORDER BY ts.patient_fhir_id, ts.event_sequence_number;
```

### Treatment Response Summary View

Create a companion summary view for quick response assessment:

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_patient_treatment_response_summary AS
WITH latest_imaging_per_phase AS (
    SELECT
        patient_fhir_id,
        imaging_phase,
        MAX(imaging_date) as latest_imaging_date,
        FIRST_VALUE(progression_flag) OVER (
            PARTITION BY patient_fhir_id, imaging_phase
            ORDER BY imaging_date DESC
        ) as latest_progression_flag,
        FIRST_VALUE(response_flag) OVER (
            PARTITION BY patient_fhir_id, imaging_phase
            ORDER BY imaging_date DESC
        ) as latest_response_flag,
        FIRST_VALUE(report_conclusion) OVER (
            PARTITION BY patient_fhir_id, imaging_phase
            ORDER BY imaging_date DESC
        ) as latest_report_conclusion
    FROM imaging_treatment_linkage
    GROUP BY patient_fhir_id, imaging_phase, imaging_date, progression_flag, response_flag, report_conclusion
)
SELECT
    pd.patient_fhir_id,
    pd.diagnostic_name,
    pd.component_name as molecular_marker,

    -- Surgical outcome
    MAX(CASE WHEN pt.surgery_type = 'resection' THEN pt.surgery_extent END) as initial_resection_extent,

    -- Treatment history
    COUNT(DISTINCT ce.episode_id) as chemo_episode_count,
    COUNT(DISTINCT re.episode_id) as radiation_episode_count,

    -- Latest imaging by phase
    MAX(CASE WHEN li.imaging_phase = 'immediate_post_op' THEN li.latest_response_flag END) as post_op_imaging_status,
    MAX(CASE WHEN li.imaging_phase = 'early_post_radiation' THEN li.latest_response_flag END) as post_radiation_imaging_status,
    MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) as surveillance_imaging_status,

    -- Progression status
    pfs.progressed,
    pfs.days_to_progression,
    pfs.pfs_days_from_treatment_completion,

    -- Overall response assessment
    CASE
        WHEN pfs.progressed = true THEN 'Progressive Disease'
        WHEN MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) = 'response_suspected'
            THEN 'Partial Response'
        WHEN MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) = 'complete_response_suspected'
            THEN 'Complete Response'
        WHEN MAX(CASE WHEN li.imaging_phase = 'long_term_surveillance' THEN li.latest_response_flag END) = 'stable_disease'
            THEN 'Stable Disease'
        ELSE 'Insufficient Data'
    END as overall_response_classification

FROM fhir_prd_db.v_pathology_diagnostics pd
LEFT JOIN fhir_prd_db.v_procedures_tumor pt
    ON pd.patient_fhir_id = pt.patient_fhir_id AND pt.is_tumor_surgery = true
LEFT JOIN fhir_prd_db.v_chemo_treatment_episodes ce
    ON pd.patient_fhir_id = ce.patient_fhir_id
LEFT JOIN fhir_prd_db.v_radiation_episode_enrichment re
    ON pd.patient_fhir_id = re.patient_fhir_id
LEFT JOIN latest_imaging_per_phase li
    ON pd.patient_fhir_id = li.patient_fhir_id
LEFT JOIN pfs_analysis pfs
    ON pd.patient_fhir_id = pfs.patient_fhir_id

WHERE pd.extraction_priority = 1  -- Highest priority diagnosis only

GROUP BY
    pd.patient_fhir_id,
    pd.diagnostic_name,
    pd.component_name,
    pfs.progressed,
    pfs.days_to_progression,
    pfs.pfs_days_from_treatment_completion;
```

---

## Use Cases and Example Queries

### Use Case 1: Complete Patient Journey for Single Patient

```sql
-- Retrieve full chronological timeline for patient
SELECT
    event_sequence_number,
    event_date,
    days_from_initial_surgery,
    treatment_phase,
    event_type,
    event_description,
    patient_diagnosis,
    molecular_marker,
    molecular_result
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE patient_fhir_id = 'eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83'
ORDER BY event_sequence_number;
```

**Expected Output**:
```
seq | date       | days | phase                  | type                  | description
----|------------|------|------------------------|----------------------|----------------------------------
1   | 2020-03-15 | 0    | surgery_day            | surgery              | Craniotomy with tumor resection (GTR, tumor surgery)
2   | 2020-03-16 | 1    | early_post_op          | imaging              | MRI Brain with contrast - Post-op baseline
3   | 2020-03-20 | 5    | early_post_op          | diagnosis            | Medulloblastoma, SHH-activated - PTCH1: mutation detected
4   | 2020-04-12 | 28   | early_post_op          | radiation_episode_start | Radiation started: 5400 cGy planned (2 fields)
5   | 2020-05-20 | 66   | adjuvant_treatment_window | radiation_episode_end | Radiation completed: 5400 cGy delivered in 38 days
6   | 2020-05-25 | 71   | adjuvant_treatment_window | chemo_episode_start | Chemotherapy started: vincristine/cisplatin/cyclophosphamide (3 medications, 180 days)
```

### Use Case 2: Treatment Protocol Adherence Analysis

```sql
-- Identify patients with potential protocol deviations
SELECT
    patient_fhir_id,
    patient_diagnosis,
    molecular_marker,
    event_type,
    event_description,
    radiation_protocol_classification,
    radiation_protocol_deviation,
    chemo_regimen_type
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE radiation_protocol_deviation IS NOT NULL
   OR chemo_regimen_type = 'Other/non-standard regimen'
ORDER BY patient_fhir_id, event_date;
```

### Use Case 3: Time-to-Treatment Analysis

```sql
-- Calculate days from surgery to treatment initiation
WITH treatment_starts AS (
    SELECT
        patient_fhir_id,
        patient_diagnosis,
        MIN(CASE WHEN event_type = 'radiation_episode_start' THEN days_from_initial_surgery END) as days_to_radiation,
        MIN(CASE WHEN event_type = 'chemo_episode_start' THEN days_from_initial_surgery END) as days_to_chemo
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    GROUP BY patient_fhir_id, patient_diagnosis
)
SELECT
    patient_diagnosis,
    COUNT(*) as patient_count,
    ROUND(AVG(days_to_radiation), 1) as avg_days_to_radiation,
    ROUND(AVG(days_to_chemo), 1) as avg_days_to_chemo,
    ROUND(STDDEV(days_to_radiation), 1) as stddev_days_to_radiation
FROM treatment_starts
GROUP BY patient_diagnosis
ORDER BY patient_count DESC;
```

### Use Case 4: Treatment Response Analysis with Imaging Timeline

```sql
-- Analyze imaging findings across treatment timeline
SELECT
    patient_fhir_id,
    event_sequence_number,
    event_date,
    days_from_initial_surgery,
    treatment_phase,
    imaging_phase,
    event_description,
    progression_flag,
    response_flag,
    linked_radiation_episode,
    linked_chemo_episode
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE patient_fhir_id = 'eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83'
  AND event_type = 'imaging'
ORDER BY event_sequence_number;
```

**Expected Output**:
```
seq | date       | days | phase           | imaging_phase      | description                                      | prog_flag | resp_flag
----|------------|------|-----------------|--------------------|--------------------------------------------------|-----------|------------------
2   | 2020-03-16 | 1    | early_post_op   | immediate_post_op  | MRI Brain - Residual enhancement [stable_disease]| NULL      | stable_disease
10  | 2020-05-22 | 68   | adjuvant_window | early_post_radiation| MRI Brain - Decreased enhancement [response_suspected] | NULL | response_suspected
15  | 2020-08-20 | 158  | active_treatment| surveillance       | MRI Brain - Stable appearance [stable_disease]   | NULL      | stable_disease
22  | 2021-02-15 | 337  | active_treatment| surveillance       | MRI Brain - New enhancement [progression_suspected] | progression_suspected | NULL
```

### Use Case 5: Progression-Free Survival by Diagnosis and Molecular Subtype

```sql
-- Calculate PFS metrics by diagnosis and molecular marker
SELECT
    patient_diagnosis,
    molecular_marker,
    COUNT(*) as patient_count,
    COUNT(CASE WHEN patient_has_progressed = true THEN 1 END) as progressed_count,
    ROUND(AVG(patient_days_to_progression), 1) as avg_days_to_progression,
    ROUND(AVG(patient_pfs_from_treatment), 1) as avg_pfs_from_treatment_completion,
    ROUND(100.0 * COUNT(CASE WHEN patient_has_progressed = true THEN 1 END) / COUNT(*), 1) as progression_rate_pct
FROM (
    SELECT DISTINCT
        patient_fhir_id,
        patient_diagnosis,
        molecular_marker,
        patient_days_to_progression,
        patient_pfs_from_treatment,
        patient_has_progressed
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE patient_diagnosis IS NOT NULL
)
GROUP BY patient_diagnosis, molecular_marker
HAVING COUNT(*) >= 3  -- At least 3 patients
ORDER BY progression_rate_pct DESC;
```

### Use Case 6: Imaging Surveillance Pattern Analysis

```sql
-- Assess imaging frequency during surveillance phase
SELECT
    patient_fhir_id,
    patient_diagnosis,
    COUNT(CASE WHEN event_type = 'imaging' AND treatment_phase = 'surveillance_phase' THEN 1 END) as surveillance_imaging_count,
    MIN(CASE WHEN event_type = 'imaging' AND treatment_phase = 'surveillance_phase' THEN days_from_initial_surgery END) as first_surveillance_imaging_days,
    MAX(CASE WHEN event_type = 'imaging' AND treatment_phase = 'surveillance_phase' THEN days_from_initial_surgery END) as last_surveillance_imaging_days,
    ROUND(
        (MAX(CASE WHEN event_type = 'imaging' AND treatment_phase = 'surveillance_phase' THEN days_from_initial_surgery END) -
         MIN(CASE WHEN event_type = 'imaging' AND treatment_phase = 'surveillance_phase' THEN days_from_initial_surgery END)) /
        NULLIF(COUNT(CASE WHEN event_type = 'imaging' AND treatment_phase = 'surveillance_phase' THEN 1 END) - 1, 0),
        1
    ) as avg_days_between_surveillance_imaging
FROM fhir_prd_db.v_patient_clinical_journey_timeline
GROUP BY patient_fhir_id, patient_diagnosis
HAVING surveillance_imaging_count > 0
ORDER BY patient_fhir_id;
```

---

## Implementation Plan

### Phase 1: Core Timeline Construction (MVP)
1. Create patient_index_surgery CTE
2. Build event CTEs for all 6 event types (diagnosis, surgery, chemo start/end, radiation start/end, imaging, visit)
3. UNION ALL into unified_timeline
4. Add sequence numbering and treatment phase classification
5. Create base view without protocol checks

**Deliverable**: `v_patient_clinical_journey_timeline_mvp`

### Phase 2: Protocol Context Integration
1. Create radiation_protocol_check CTE with WHO 2021 dose standards
2. Create chemo_regimen_classification CTE
3. Join protocol CTEs to main timeline
4. Add protocol deviation flags

**Deliverable**: `v_patient_clinical_journey_timeline` (full version)

### Phase 3: Testing and Validation
1. Test with sample patient cohort (9 patients from previous queries)
2. Validate event counts per patient
3. Verify temporal sequencing (no out-of-order events)
4. Check protocol classification accuracy against manual review
5. Performance testing (query execution time for full cohort)

**Deliverable**: Validation report + performance benchmarks

### Phase 4: Documentation and Deployment
1. Add inline SQL comments
2. Create example query library
3. Update AGENT_CONTEXT.md with new view
4. Git commit and push
5. Deploy to production Athena

**Deliverable**: Production-ready view with documentation

---

## Data Quality Considerations

### Temporal Data Completeness
- **Issue**: Not all events have TIMESTAMP precision (some only DATE)
- **Mitigation**: Use event_datetime where available; fall back to event_date CAST AS TIMESTAMP
- **Impact**: Same-day events may not have guaranteed ordering

### Episode Linkage
- **Issue**: Imaging/visits not inherently linked to treatment episodes
- **Mitigation**: Use temporal proximity (e.g., imaging within ±7 days of episode start = "baseline")
- **Future Enhancement**: Add phase classification for imaging relative to nearest treatment episode

### Diagnosis Deduplication
- **Issue**: v_pathology_diagnostics may have multiple diagnosis records per patient
- **Mitigation**: Use extraction_priority to select highest-quality diagnosis for context columns
- **Alternative**: Include ALL diagnosis events in timeline, filter by priority in queries

### Missing Data Handling
- **Age Calculation**: Not all source views have age; use COALESCE to pull from available sources
- **Protocol Classification**: NULL when diagnosis not recognized or dose outside standard ranges
- **days_from_initial_surgery**: NULL for patients without tumor surgery in v_procedures_tumor

---

## WHO 2021 Molecular Marker Integration

### Molecular Markers to Track

Based on v_pathology_diagnostics component fields and WHO 2021:

| Marker | Tumor Types | Clinical Significance | Expected in component_name |
|--------|-------------|----------------------|---------------------------|
| **H3 K27 alteration** | DMG, HGG | Poor prognosis; defines entity | H3-3A, HIST1H3B/C |
| **H3 G34 mutation** | HGG (hemisphere) | Distinct from K27; adolescent/YA | H3-3A G34R/V |
| **IDH mutation** | HGG (rare in peds) | Better prognosis if present | IDH1, IDH2 |
| **BRAF V600E** | LGG, ganglioglioma | Targetable; dabrafenib/trametinib | BRAF V600E |
| **BRAF fusion** | LGG (pilocytic astrocytoma) | Common in PA; MEK inhibitors | KIAA1549-BRAF, other fusions |
| **1p/19q codeletion** | Oligodendroglioma | Chemo/RT sensitive | 1p, 19q status |
| **MYCN amplification** | Medulloblastoma Group 3 | High-risk feature | MYCN |
| **TP53 mutation** | Multiple | Li-Fraumeni; avoid radiation | TP53 |
| **PTCH1 mutation** | Medulloblastoma SHH | Gorlin syndrome association | PTCH1 |

### Treatment Paradigm Lookup Table

```sql
-- Could be implemented as a separate reference table
CREATE TABLE molecular_treatment_paradigms AS
SELECT * FROM (
    VALUES
    ('H3 K27-altered diffuse midline glioma', 'H3-3A K27M', 'Radiation 54 Gy', 'Clinical trial preferred', 'Poor'),
    ('Medulloblastoma, SHH-activated', 'PTCH1 mutation', 'Surgery + CSI 23.4-36 Gy + chemo', 'Standard protocol', 'Intermediate'),
    ('Low-grade glioma, BRAF V600E', 'BRAF V600E', 'Surgery if feasible; dabrafenib/trametinib if progressive', 'Targeted therapy', 'Good'),
    ('Pilocytic astrocytoma', 'KIAA1549-BRAF fusion', 'Surgery (GTR preferred); observe if GTR', 'Watch-and-wait if GTR', 'Excellent'),
    ('High-grade glioma, IDH-wildtype', 'IDH wildtype', 'Surgery + RT 54-60 Gy + temozolomide or trial', 'Aggressive multimodal', 'Poor to intermediate')
    -- ... additional rows
) AS t(diagnosis, molecular_marker, standard_treatment, treatment_notes, prognosis_category);
```

---

## Performance Optimization

### Indexing Strategy (If Supported)
- Patient index: `patient_fhir_id`
- Temporal index: `event_date`
- Episode index: `episode_id` (for filtering to treatment episodes)

### Query Optimization
- Use WHERE clauses on patient_fhir_id for single-patient queries (highly selective)
- For cohort analysis, filter by treatment_phase or event_type to reduce result set
- Consider materialized view if query performance becomes issue (refresh nightly)

### Expected Performance
- **Single patient timeline**: <1 second (filtering on indexed patient_fhir_id)
- **Full cohort (1000 patients)**: 5-15 seconds (depends on date range filters)
- **Aggregation queries**: 10-30 seconds (group by diagnosis, treatment phase, etc.)

---

## Future Enhancements

### Phase 5: Treatment Response Integration
- Add progression/recurrence events from imaging reports (NLP extraction)
- Calculate time-to-progression from treatment completion
- Flag imaging findings suggesting response (e.g., "decreased enhancement", "stable")

### Phase 6: Clinical Trial Matching
- Add clinical trial eligibility flags based on diagnosis + molecular markers
- Link to external trial database (e.g., ClinicalTrials.gov identifiers)
- Identify patients eligible for specific protocols

### Phase 7: Visualization Support
- Add JSON output format for timeline visualization tools (e.g., Plotly, D3.js)
- Generate Gantt chart data structure (start/end dates for episodes)
- Color-coding schema by event type for visual clarity

### Phase 8: Predictive Analytics Integration
- Feature extraction for ML models (treatment sequence patterns)
- Risk stratification based on time-to-treatment delays
- Protocol adherence scoring (composite metric)

---

## Appendix: Column Mappings

### v_pathology_diagnostics → Timeline
- `diagnostic_date` → `event_date`
- `diagnostic_source` → `event_subtype`
- `diagnostic_name` → `event_description` (concatenated with component/result)
- `days_from_surgery` → `days_from_initial_surgery` (direct mapping)
- `extraction_priority` → `priority_score`

### v_procedures_tumor → Timeline
- `proc_performed_date_time` → `event_datetime`
- `surgery_type` → `event_subtype`
- `proc_code_text` → `event_description` (concatenated with extent)
- `procedure_fhir_id` → `event_id`

### v_chemo_treatment_episodes → Timeline
- `episode_start_datetime` → `event_datetime` (for start events)
- `episode_end_datetime` → `event_datetime` (for end events)
- `chemo_preferred_name` → Included in `event_description`
- `episode_id` → `episode_id`
- `medication_count`, `episode_duration_days` → Included in `event_description`

### v_radiation_episode_enrichment → Timeline
- `episode_start_date` → `event_date` (for start events)
- `episode_end_date` → `event_date` (for end events)
- `total_dose_cgy` → Included in `event_description`
- `episode_id` → `episode_id`
- `enrichment_score` → `priority_score`

### v_imaging → Timeline
- `imaging_date` → `event_date`
- `imaging_modality` → `event_subtype`
- `imaging_procedure`, `report_conclusion` → `event_description`
- `age_at_imaging_years` → `age_at_event_years`

### v_visits_unified → Timeline
- `visit_date` → `event_date`
- `visit_type` → `event_subtype`
- `appointment_status`, `encounter_status` → Included in `event_description`
- `visit_id` → `event_id`
- `age_at_visit_days` → Converted to `age_at_event_years` (/ 365.25)

---

## Summary

This design creates a **WHO 2021-informed, episode-aware, chronological patient timeline** that:

1. ✅ Unifies 8 event types across 6 source views into single timeline per patient
2. ✅ Anchors temporal sequencing to initial tumor surgery (days_from_initial_surgery)
3. ✅ Tracks treatment episodes (chemo, radiation) with start/stop dates
4. ✅ Integrates molecular diagnosis context to inform expected treatment paradigms
5. ✅ Validates radiation doses and chemotherapy regimens against WHO 2021 standards
6. ✅ Classifies treatment phases (pre-surgery → surgery → adjuvant → active → surveillance)
7. ✅ Supports clinical decision-making, research analysis, and protocol adherence monitoring

**Next Steps**: Proceed to SQL implementation (Phase 1: Core Timeline Construction).
