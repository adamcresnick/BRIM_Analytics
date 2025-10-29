# Radiation Episode View Design Document
**Date**: 2025-10-29
**Purpose**: Design comprehensive episode-based radiation treatment timeline views following chemotherapy episode methodology

---

## Executive Summary

This document outlines the design for two radiation oncology views that group individual radiation treatment events into logical episode spans, enabling layered timeline visualization and optimized document selection for NLP/LLM abstraction.

**Parallel Development**: These views will be developed alongside chemotherapy episode views to enable unified treatment timeline abstraction workflows.

**Key Design Principles**:
1. **Multi-source episode detection**: Hybrid approach using structured data + temporal windowing + care plan boundaries
2. **Episode sequencing**: Track treatment courses over time, detect re-irradiation
3. **Appointment-episode linkage**: Connect individual fractions to treatment courses
4. **Document temporal classification**: Identify planning docs, progress notes, and treatment summaries relative to episode dates
5. **NLP optimization**: Prioritize documents for abstraction based on episode context and temporal relationship

---

## Current State Assessment

### Available Data Sources (913 Total Radiation Patients)

| View | Patient Coverage | Key Data | Episode Relevance |
|------|------------------|----------|-------------------|
| **v_radiation_treatments** | 91 patients | `course_id`, dose, field, site, dates from ELECT observations | ✅ **Primary episode identifier** for structured data |
| **v_radiation_care_plan_hierarchy** | 568 patients | Care plan periods, titles, status, hierarchy | ✅ **Episode boundaries** from treatment planning |
| **v_radiation_documents** | 684 patients | Prioritized documents (treatment summaries, consults), dates | ✅ **NLP source** + episode date inference |
| **v_radiation_treatment_appointments** | 358 patients, 961 appointments | Individual fraction timestamps, status | ✅ **Episode composition** (fractions → courses) |
| **v_radiation_summary** | 913 patients (union) | Data availability flags, date ranges, quality scores | ✅ **Episode validation** and quality assessment |

### Critical Gap Identified

**Problem**: Current `V_RADIATION_TREATMENT_EPISODES_COMPREHENSIVE.sql` only creates episodes for ~90 patients with `course_id` from structured observations.

**Impact**: **~820 patients** (90% of radiation cohort) have radiation data but NO episodes created.

**Root Cause**: No temporal windowing fallback for patients without explicit `course_id`.

---

## Proposed Solution: Two-View Architecture

### View 1: `v_radiation_treatment_episodes`
**Production view** with comprehensive episode metadata, multi-source fallback, and NLP optimization flags.

### View 2: `v_radiation_course_timeline`
**Timeline integration view** with simplified span representation for unified patient timeline visualization.

---

## View 1: v_radiation_treatment_episodes (Production View)

### Purpose
Create one row per radiation treatment episode (course) with comprehensive metadata from all 5 radiation views, using hybrid episode detection strategy.

### Episode Detection Strategy (Hybrid Approach)

Episodes will be created using a **priority-based fallback** approach:

#### **Strategy A: Structured Course ID** (~90 patients)
- **Source**: `v_radiation_treatments.course_id` (from ELECT observations or service requests)
- **Reliability**: HIGH - Explicit course identifier
- **Coverage**: Limited to patients with structured ELECT intake data
- **Episode ID**: Use `course_id` directly

```sql
-- Example: Patient has obs_course_line = "Line 1", "Line 2" → 2 episodes
SELECT patient_fhir_id, course_id as episode_id,
       'structured_course_id' as episode_detection_method
FROM v_radiation_treatments
WHERE course_id IS NOT NULL
```

#### **Strategy B: Care Plan Periods** (~568 patients)
- **Source**: `v_radiation_care_plan_hierarchy.cp_period_start/end`
- **Reliability**: MEDIUM-HIGH - Clinical treatment plan boundaries
- **Coverage**: Patients with radiation care plans (may overlap with Strategy A)
- **Episode ID**: `care_plan_id`

```sql
-- Example: Patient has 2 care plans with non-overlapping periods → 2 episodes
SELECT patient_fhir_id, care_plan_id as episode_id,
       cp_period_start as episode_start, cp_period_end as episode_end,
       'care_plan_period' as episode_detection_method
FROM v_radiation_care_plan_hierarchy
```

#### **Strategy C: Appointment Temporal Windowing** (~358 patients)
- **Source**: `v_radiation_treatment_appointments` grouped by temporal gaps
- **Reliability**: MEDIUM - Heuristic-based (gap threshold = 14 days)
- **Coverage**: Patients with appointments but no course_id/care plans
- **Episode ID**: Generated from patient + sequence number
- **Logic**: Typical radiation = 5 fractions/week for 4-6 weeks. Gap > 14 days → new course.

```sql
-- Window function approach (similar to chemotherapy episodes)
WITH appointment_gaps AS (
    SELECT
        patient_fhir_id,
        appointment_id,
        appointment_start,
        -- Mark new episode when gap > 14 days from previous appointment
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(CAST(appointment_start AS DATE))
                    OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start),
                CAST(appointment_start AS DATE)
            ) > 14 THEN 1
            ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start) as episode_number
    FROM v_radiation_treatment_appointments
)
SELECT patient_fhir_id,
       patient_fhir_id || '_apt_episode_' || episode_number as episode_id,
       MIN(appointment_start) as episode_start,
       MAX(appointment_start) as episode_end,
       'appointment_temporal_window' as episode_detection_method
FROM appointment_gaps
GROUP BY patient_fhir_id, episode_number
```

#### **Strategy D: Document Temporal Clustering** (~684 patients)
- **Source**: `v_radiation_documents.doc_date` grouped by temporal proximity
- **Reliability**: LOW-MEDIUM - Inferred from documentation patterns
- **Coverage**: Patients with documents but no other episode indicators
- **Episode ID**: Generated from patient + sequence number
- **Logic**: Treatment summaries typically created at episode end. Cluster documents within 60-day windows.

```sql
-- Fallback for document-only patients
-- Look for temporal clusters of radiation documents
WITH document_gaps AS (
    SELECT
        patient_fhir_id,
        doc_date,
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(doc_date) OVER (PARTITION BY patient_fhir_id ORDER BY doc_date),
                doc_date
            ) > 60 THEN 1
            ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY doc_date) as episode_number
    FROM v_radiation_documents
)
SELECT patient_fhir_id,
       patient_fhir_id || '_doc_episode_' || episode_number as episode_id,
       MIN(doc_date) as episode_start,
       MAX(doc_date) as episode_end,
       'document_temporal_cluster' as episode_detection_method
FROM document_gaps
GROUP BY patient_fhir_id, episode_number
```

### Episode Sequencing & Re-Irradiation Detection

**Course Numbering**:
```sql
ROW_NUMBER() OVER (PARTITION BY patient_fhir_id ORDER BY episode_start_date) as course_number
```

**First Course Flag**:
```sql
CASE WHEN course_number = 1 THEN true ELSE false END as is_first_course
```

**Re-Irradiation Detection**:
```sql
-- Re-irradiation = subsequent course to same anatomic site
CASE
    WHEN course_number > 1
    AND radiation_site_codes SIMILAR TO (
        SELECT radiation_site_codes
        FROM prior_episodes
        WHERE course_number < current.course_number
    )
    THEN true
    ELSE false
END as is_reirradiation
```

**Days Since Previous Course**:
```sql
DATE_DIFF('day',
    LAG(episode_end_date) OVER (PARTITION BY patient_fhir_id ORDER BY episode_start_date),
    episode_start_date
) as days_since_previous_course
```

### Appointment-to-Episode Linking

**Challenge**: v_radiation_treatment_appointments has NO course_id field.

**Solution**: Link appointments to episodes via temporal overlap + patient match.

```sql
-- For each episode, find appointments that fall within episode date range
WITH episode_appointments AS (
    SELECT
        e.episode_id,
        e.patient_fhir_id,
        e.episode_start_datetime,
        e.episode_end_datetime,
        a.appointment_id,
        a.appointment_start,
        a.appointment_status
    FROM episodes e
    LEFT JOIN v_radiation_treatment_appointments a
        ON e.patient_fhir_id = a.patient_fhir_id
        AND a.appointment_start >= e.episode_start_datetime
        AND a.appointment_start <= DATE_ADD('day', 30, e.episode_end_datetime) -- 30-day buffer
)
SELECT
    episode_id,
    ARRAY_AGG(appointment_id ORDER BY appointment_start) as constituent_appointment_ids,
    COUNT(DISTINCT appointment_id) as num_fractions,
    COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) as num_fulfilled_fractions,
    COUNT(DISTINCT CASE WHEN appointment_status = 'cancelled' THEN appointment_id END) as num_cancelled_fractions,
    CAST(COUNT(DISTINCT CASE WHEN appointment_status = 'fulfilled' THEN appointment_id END) AS DOUBLE) /
        NULLIF(COUNT(DISTINCT appointment_id), 0) as fraction_completion_rate
FROM episode_appointments
GROUP BY episode_id
```

### Document-Episode Temporal Relationship

**Critical for NLP**: Documents created **AFTER** episode completion (treatment summaries) are HIGH VALUE for abstraction.

```sql
-- Classify each document relative to episode dates
WITH episode_documents AS (
    SELECT
        e.episode_id,
        e.patient_fhir_id,
        e.episode_start_datetime,
        e.episode_end_datetime,
        d.document_id,
        d.doc_date,
        d.extraction_priority,
        d.document_category,
        CASE
            WHEN d.doc_date < e.episode_start_datetime THEN 'BEFORE_EPISODE' -- Planning docs
            WHEN d.doc_date >= e.episode_start_datetime
                 AND d.doc_date <= e.episode_end_datetime THEN 'DURING_EPISODE' -- Progress notes
            WHEN d.doc_date > e.episode_end_datetime THEN 'AFTER_EPISODE' -- Treatment summaries!
            ELSE 'UNKNOWN'
        END as document_temporal_relationship
    FROM episodes e
    LEFT JOIN v_radiation_documents d ON e.patient_fhir_id = d.patient_fhir_id
)
SELECT
    episode_id,
    COUNT(DISTINCT CASE WHEN document_temporal_relationship = 'BEFORE_EPISODE' THEN document_id END) as num_documents_before_episode,
    COUNT(DISTINCT CASE WHEN document_temporal_relationship = 'DURING_EPISODE' THEN document_id END) as num_documents_during_episode,
    COUNT(DISTINCT CASE WHEN document_temporal_relationship = 'AFTER_EPISODE' THEN document_id END) as num_documents_after_episode,
    COUNT(DISTINCT CASE
        WHEN document_temporal_relationship = 'AFTER_EPISODE'
        AND document_category = 'Treatment Summary'
        THEN document_id
    END) as num_treatment_summaries_post_episode,
    ARRAY_AGG(DISTINCT CASE
        WHEN document_temporal_relationship = 'AFTER_EPISODE'
        AND extraction_priority IN (1, 2)
        THEN document_id
    END) as high_priority_post_episode_doc_ids
FROM episode_documents
GROUP BY episode_id
```

### Complete Field Schema

```sql
-- ============================================================================
-- EPISODE IDENTIFIERS
-- ============================================================================
episode_id VARCHAR,                    -- Unique episode identifier
patient_fhir_id VARCHAR,              -- Patient reference
course_number INTEGER,                 -- Sequential course number (1, 2, 3...)
episode_detection_method VARCHAR,      -- How episode was identified

-- ============================================================================
-- EPISODE TEMPORAL BOUNDARIES
-- ============================================================================
episode_start_date DATE,              -- Best available start date
episode_start_datetime TIMESTAMP(3),  -- Best available start timestamp
episode_end_date DATE,                -- Best available end date
episode_end_datetime TIMESTAMP(3),    -- Best available end timestamp
episode_duration_days INTEGER,        -- Duration in days

-- Date source tracking for transparency
episode_start_date_source VARCHAR,    -- obs_start | cp_start | apt_start | doc_start
episode_end_date_source VARCHAR,      -- obs_stop | cp_end | apt_end | doc_end

-- Source-specific dates (all available)
obs_start_date TIMESTAMP(3),          -- From v_radiation_treatments
obs_stop_date TIMESTAMP(3),
cp_start_date TIMESTAMP(3),           -- From v_radiation_care_plan_hierarchy
cp_end_date TIMESTAMP(3),
apt_first_date TIMESTAMP(3),          -- From v_radiation_treatment_appointments
apt_last_date TIMESTAMP(3),
doc_earliest_date TIMESTAMP(3),       -- From v_radiation_documents
doc_latest_date TIMESTAMP(3),

-- ============================================================================
-- TREATMENT DETAILS (from v_radiation_treatments)
-- ============================================================================
total_dose_cgy DOUBLE,                -- Sum of all dose values
avg_dose_cgy DOUBLE,                  -- Average dose per record
min_dose_cgy DOUBLE,
max_dose_cgy DOUBLE,
num_dose_records INTEGER,

num_unique_fields INTEGER,            -- Count of radiation fields
num_unique_sites INTEGER,             -- Count of radiation sites
radiation_fields VARCHAR,             -- Aggregated field list
radiation_site_codes VARCHAR,         -- Aggregated site codes
radiation_sites_summary VARCHAR,      -- Human-readable site summary

-- ============================================================================
-- APPOINTMENT DETAILS (linked to episode)
-- ============================================================================
constituent_appointment_ids ARRAY(VARCHAR),  -- Array of appointment IDs
num_fractions INTEGER,                -- Total appointments in episode
num_fulfilled_fractions INTEGER,      -- Completed appointments
num_cancelled_fractions INTEGER,      -- Cancelled appointments
num_noshow_fractions INTEGER,         -- No-show appointments
fraction_completion_rate DOUBLE,      -- fulfilled / total

-- ============================================================================
-- CARE PLAN CONTEXT
-- ============================================================================
care_plan_ids VARCHAR,                -- Aggregated care plan IDs
care_plan_titles VARCHAR,             -- Aggregated care plan titles
care_plan_statuses VARCHAR,           -- Aggregated care plan statuses
num_care_plans INTEGER,               -- Count of linked care plans

-- ============================================================================
-- DOCUMENT CONTEXT WITH TEMPORAL RELATIONSHIP
-- ============================================================================
num_documents_total INTEGER,                     -- All radiation documents for patient
num_documents_before_episode INTEGER,            -- Planning documents
num_documents_during_episode INTEGER,            -- Progress notes
num_documents_after_episode INTEGER,             -- Treatment summaries (HIGH VALUE!)
num_treatment_summaries_post_episode INTEGER,   -- Treatment summaries created post-episode
high_priority_post_episode_doc_ids ARRAY(VARCHAR), -- Priority 1-2 docs after episode

-- Document categories present
document_categories VARCHAR,          -- Aggregated document category list

-- ============================================================================
-- EPISODE SEQUENCING
-- ============================================================================
is_first_course BOOLEAN,              -- True if course_number = 1
is_reirradiation BOOLEAN,             -- True if course_number > 1 AND site overlap
days_since_previous_course INTEGER,   -- Gap between courses

-- ============================================================================
-- DATA AVAILABILITY FLAGS
-- ============================================================================
has_structured_dose BOOLEAN,          -- Has dose from observations
has_structured_site BOOLEAN,          -- Has site from observations
has_structured_field BOOLEAN,         -- Has field from observations
has_episode_dates BOOLEAN,            -- Has start/end dates from any source
has_care_plans BOOLEAN,               -- Has linked care plans
has_documents BOOLEAN,                -- Has radiation documents
has_appointments BOOLEAN,             -- Has appointment fractions
has_complete_structured_data BOOLEAN, -- dose + field + site + dates

-- ============================================================================
-- DATA QUALITY SCORING
-- ============================================================================
episode_data_quality_score DOUBLE,    -- 0.0 to 1.0 weighted score
data_quality_tier VARCHAR,            -- HIGH | MEDIUM | LOW

-- Weighted scoring:
-- - Episode dates (25%)
-- - Dose data (20%)
-- - Field data (20%)
-- - Site data (15%)
-- - Documents (10%)
-- - Care plans (10%)

-- ============================================================================
-- RECOMMENDED ANALYSIS STRATEGY
-- ============================================================================
recommended_analysis_approach VARCHAR,

-- Possible values:
-- - DIRECT_ANALYSIS_WITH_VALIDATION: Complete structured data + documents
-- - DIRECT_ANALYSIS_READY: Complete structured data, no documents
-- - ANALYSIS_READY_NO_DATES: Treatment details but missing dates
-- - DOCUMENT_EXTRACTION_RECOMMENDED: High-priority documents available
-- - PARTIAL_DATA_AVAILABLE: Some data, incomplete
-- - INSUFFICIENT_DATA: Minimal data

-- ============================================================================
-- NLP OPTIMIZATION FLAGS
-- ============================================================================
nlp_priority_tier VARCHAR,            -- Tier for NLP extraction prioritization

-- Tier 1 (HIGHEST): Treatment summaries post-episode + structured validation
-- Tier 2 (HIGH): Treatment summaries post-episode, no structured data
-- Tier 3 (MEDIUM): Documents during episode + partial structured data
-- Tier 4 (LOW): Documents only, no clear episode boundaries
-- Tier 5 (MINIMAL): Insufficient data for meaningful NLP

nlp_recommended_documents ARRAY(VARCHAR), -- Array of document IDs for NLP (prioritized order)

nlp_validation_strategy VARCHAR,
-- Possible values:
-- - STRUCTURED_FIRST_DOCUMENT_VALIDATION: Use structured data, validate with documents
-- - DOCUMENT_FIRST_STRUCTURED_AUGMENTATION: Extract from documents, augment with structured
-- - DOCUMENT_ONLY: No structured data available
-- - STRUCTURED_ONLY: No documents for validation
```

---

## View 2: v_radiation_course_timeline (Timeline Integration View)

### Purpose
Simplified view for unified patient timeline visualization showing radiation treatment episode spans alongside other treatment modalities (chemotherapy, surgery, etc.).

### Design Principle
Parallel structure to chemotherapy episode timeline view to enable union operations for unified timelines.

### Field Schema

```sql
SELECT
    -- ========================================================================
    -- PATIENT & EPISODE IDENTIFIERS
    -- ========================================================================
    patient_fhir_id,
    episode_id,
    course_number,

    -- ========================================================================
    -- TEMPORAL SPAN (for timeline visualization)
    -- ========================================================================
    episode_start_datetime,
    episode_end_datetime,
    episode_duration_days,

    -- ========================================================================
    -- EVENT TYPE & CATEGORY (for timeline grouping)
    -- ========================================================================
    CASE
        WHEN is_reirradiation THEN 'Radiation Course (Re-Irradiation)'
        ELSE 'Radiation Course'
    END as event_type,

    'Treatment Course' as event_category,

    -- ========================================================================
    -- EVENT DESCRIPTION (summary for timeline display)
    -- ========================================================================
    CASE
        WHEN radiation_sites_summary IS NOT NULL AND total_dose_cgy IS NOT NULL THEN
            radiation_sites_summary || ' - ' || CAST(total_dose_cgy AS VARCHAR) || ' cGy'
        WHEN radiation_sites_summary IS NOT NULL THEN
            radiation_sites_summary
        WHEN total_dose_cgy IS NOT NULL THEN
            CAST(total_dose_cgy AS VARCHAR) || ' cGy'
        ELSE 'Radiation Treatment'
    END as event_description,

    -- ========================================================================
    -- EPISODE METADATA (for filtering/coloring in timeline)
    -- ========================================================================
    num_fractions,
    fraction_completion_rate,
    data_quality_tier,
    episode_detection_method,

    -- ========================================================================
    -- RE-IRRADIATION FLAG (for visual differentiation)
    -- ========================================================================
    is_reirradiation,
    is_first_course,

    -- ========================================================================
    -- DRILL-DOWN REFERENCE (link back to detailed episode view)
    -- ========================================================================
    episode_id as detail_view_link

FROM fhir_prd_db.v_radiation_treatment_episodes

ORDER BY patient_fhir_id, episode_start_datetime
```

### Timeline Integration Example

```sql
-- Unified treatment timeline (radiation + chemotherapy)
SELECT * FROM (
    SELECT
        patient_fhir_id,
        episode_start_datetime as event_start,
        episode_end_datetime as event_end,
        event_type,
        event_category,
        event_description
    FROM fhir_prd_db.v_radiation_course_timeline

    UNION ALL

    SELECT
        patient_fhir_id,
        episode_start_date as event_start,
        episode_end_date as event_end,
        'Chemotherapy Episode' as event_type,
        'Treatment Course' as event_category,
        medication_regimen as event_description
    FROM fhir_prd_db.v_medication_episodes

    UNION ALL

    SELECT
        patient_fhir_id,
        visit_start_datetime as event_start,
        visit_end_datetime as event_end,
        'Encounter' as event_type,
        'Healthcare Encounter' as event_category,
        encounter_type as event_description
    FROM fhir_prd_db.v_visits_unified
)
ORDER BY patient_fhir_id, event_start
```

---

## NLP/LLM Abstraction Optimization Strategy

### Primary Goal
Leverage episode views to intelligently select documents for NLP abstraction, prioritizing high-value documents that capture complete treatment information.

### Document Selection Hierarchy

#### **Tier 1: Treatment Summaries Post-Episode (HIGHEST VALUE)**
- **Why**: Comprehensive retrospective summary of entire radiation course
- **Selection**: `num_treatment_summaries_post_episode > 0`
- **Validation**: Cross-reference with structured data if available

```sql
-- Tier 1 NLP candidates
SELECT
    e.patient_fhir_id,
    e.episode_id,
    d.document_id,
    d.doc_description,
    d.docc_attachment_url,
    'TIER_1_TREATMENT_SUMMARY_POST_EPISODE' as nlp_priority
FROM v_radiation_treatment_episodes e
JOIN v_radiation_documents d
    ON e.patient_fhir_id = d.patient_fhir_id
    AND d.document_id = ANY(e.high_priority_post_episode_doc_ids)
WHERE e.num_treatment_summaries_post_episode > 0
ORDER BY e.episode_data_quality_score DESC
```

#### **Tier 2: Consultation Notes Pre-Episode (HIGH VALUE)**
- **Why**: Treatment planning rationale, prescribed regimen details
- **Selection**: `extraction_priority = 2` AND `doc_date < episode_start_date`

```sql
-- Tier 2 NLP candidates
SELECT
    e.patient_fhir_id,
    e.episode_id,
    d.document_id,
    d.doc_description,
    'TIER_2_CONSULTATION_PRE_EPISODE' as nlp_priority
FROM v_radiation_treatment_episodes e
JOIN v_radiation_documents d
    ON e.patient_fhir_id = d.patient_fhir_id
WHERE d.extraction_priority = 2
  AND d.doc_date < e.episode_start_datetime
  AND d.doc_date >= DATE_ADD('day', -30, e.episode_start_datetime) -- Within 30 days before
ORDER BY d.doc_date DESC
```

#### **Tier 3: Progress Notes During Episode (MEDIUM VALUE)**
- **Why**: Real-time treatment modifications, toxicity assessments
- **Selection**: `doc_date BETWEEN episode_start AND episode_end`
- **Strategy**: Sample representative progress notes (not all)

```sql
-- Tier 3 NLP candidates (sampled)
WITH ranked_progress_notes AS (
    SELECT
        e.patient_fhir_id,
        e.episode_id,
        d.document_id,
        d.doc_date,
        ROW_NUMBER() OVER (
            PARTITION BY e.episode_id
            ORDER BY d.doc_date
        ) as note_sequence
    FROM v_radiation_treatment_episodes e
    JOIN v_radiation_documents d
        ON e.patient_fhir_id = d.patient_fhir_id
    WHERE d.doc_date >= e.episode_start_datetime
      AND d.doc_date <= e.episode_end_datetime
      AND d.document_category = 'Progress Note'
)
-- Select first, middle, and last progress note per episode
SELECT patient_fhir_id, episode_id, document_id, doc_date,
       'TIER_3_PROGRESS_NOTE_SAMPLED' as nlp_priority
FROM ranked_progress_notes
WHERE note_sequence = 1  -- First
   OR note_sequence = (SELECT MAX(note_sequence) FROM ranked_progress_notes) -- Last
   OR note_sequence = (SELECT MAX(note_sequence) / 2 FROM ranked_progress_notes) -- Middle
```

#### **Tier 4: Document-Only Episodes (LOW-MEDIUM VALUE)**
- **Why**: No structured data for validation, rely entirely on NLP
- **Selection**: `episode_detection_method = 'document_temporal_cluster'`
- **Strategy**: Extract all high-priority documents in cluster

### NLP Validation Workflows

#### **Workflow A: Structured-First with Document Validation**
For episodes with `has_complete_structured_data = true` AND `has_documents = true`:

1. Use structured data (dose, site, field, dates) as baseline
2. Extract treatment summary post-episode via NLP
3. **Validate**: Cross-check NLP extraction against structured data
4. **Flag discrepancies** for manual review
5. **Augment**: Add soft data from NLP (toxicity, outcomes, notes) to structured baseline

#### **Workflow B: Document-First with Structured Augmentation**
For episodes with `has_documents = true` AND `has_complete_structured_data = false`:

1. Extract treatment details from treatment summary via NLP
2. **Augment**: Add any available structured data (partial dose, appointments)
3. **Flag**: Note that primary data source is NLP extraction (lower confidence)

#### **Workflow C: Document-Only**
For episodes with `episode_detection_method = 'document_temporal_cluster'`:

1. Extract all treatment details from documents via NLP
2. **Flag**: No structured data validation available (lowest confidence)
3. **Prioritize**: Mark for manual review if critical treatment decisions depend on accuracy

---

## SQL Testing Stages for Optimized Development

### Stage 1: Episode Detection Testing

**Goal**: Validate each episode detection strategy independently before integration.

#### Test 1A: Structured Course ID Coverage
```sql
-- How many episodes can we create from course_id?
SELECT
    'Structured Course ID' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT course_id) as total_episodes,
    ROUND(AVG(episodes_per_patient), 2) as avg_episodes_per_patient
FROM (
    SELECT patient_fhir_id, course_id,
           COUNT(*) OVER (PARTITION BY patient_fhir_id) as episodes_per_patient
    FROM v_radiation_treatments
    WHERE course_id IS NOT NULL
) t
```

**Expected Output**:
- `patients_covered`: ~90
- `total_episodes`: ~90-100 (some patients may have multiple courses)
- `avg_episodes_per_patient`: ~1.0-1.2

#### Test 1B: Care Plan Period Coverage
```sql
-- How many episodes from care plan periods?
SELECT
    'Care Plan Periods' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT care_plan_id) as total_episodes,
    COUNT(DISTINCT patient_fhir_id) - (
        SELECT COUNT(DISTINCT patient_fhir_id)
        FROM v_radiation_treatments
        WHERE course_id IS NOT NULL
    ) as incremental_patients
FROM v_radiation_care_plan_hierarchy
```

**Expected Output**:
- `patients_covered`: ~568
- `total_episodes`: ~568-600
- `incremental_patients`: ~478 (patients NOT in Strategy A)

#### Test 1C: Appointment Temporal Windowing Coverage
```sql
-- How many episodes from appointment temporal clustering?
WITH appointment_gaps AS (
    SELECT
        patient_fhir_id,
        appointment_id,
        appointment_start,
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(CAST(appointment_start AS DATE))
                    OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start),
                CAST(appointment_start AS DATE)
            ) > 14 THEN 1
            ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start) as episode_number
    FROM v_radiation_treatment_appointments
)
SELECT
    'Appointment Temporal Window' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT patient_fhir_id || '_' || episode_number) as total_episodes,
    COUNT(DISTINCT patient_fhir_id) - (
        SELECT COUNT(DISTINCT patient_fhir_id)
        FROM v_radiation_treatments
        WHERE course_id IS NOT NULL
        UNION
        SELECT DISTINCT patient_fhir_id FROM v_radiation_care_plan_hierarchy
    ) as incremental_patients
FROM appointment_gaps
```

**Expected Output**:
- `patients_covered`: ~358
- `total_episodes`: ~370-400 (some patients have multiple courses)
- `incremental_patients`: ~50-100 (patients NOT in Strategies A or B)

**Critical Validation**: Sample 10 patients, manually review appointment clusters. Are episode boundaries reasonable?

#### Test 1D: Document Temporal Clustering Coverage
```sql
-- How many episodes from document clustering?
WITH document_gaps AS (
    SELECT
        patient_fhir_id,
        document_id,
        doc_date,
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(doc_date) OVER (PARTITION BY patient_fhir_id ORDER BY doc_date),
                doc_date
            ) > 60 THEN 1
            ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY doc_date) as episode_number
    FROM v_radiation_documents
)
SELECT
    'Document Temporal Cluster' as strategy,
    COUNT(DISTINCT patient_fhir_id) as patients_covered,
    COUNT(DISTINCT patient_fhir_id || '_' || episode_number) as total_episodes,
    -- Incremental: patients NOT covered by A, B, or C
    COUNT(DISTINCT CASE
        WHEN patient_fhir_id NOT IN (
            SELECT patient_fhir_id FROM v_radiation_treatments WHERE course_id IS NOT NULL
            UNION
            SELECT patient_fhir_id FROM v_radiation_care_plan_hierarchy
            UNION
            SELECT patient_fhir_id FROM v_radiation_treatment_appointments
        ) THEN patient_fhir_id
    END) as incremental_patients
FROM document_gaps
```

**Expected Output**:
- `patients_covered`: ~684
- `total_episodes`: ~700-800
- `incremental_patients`: ~100-200 (patients ONLY in documents)

**Critical Validation**: Sample 10 document-only patients. Do temporal clusters make clinical sense?

---

### Stage 2: Episode Date Resolution Testing

**Goal**: Test COALESCE logic for episode start/end dates across multiple sources.

```sql
-- Test date source priority and coverage
WITH episode_dates AS (
    SELECT
        patient_fhir_id,
        -- Source-specific dates
        obs_start_date,
        obs_stop_date,
        cp_period_start as cp_start_date,
        cp_period_end as cp_end_date,
        apt_first_date,
        apt_last_date,
        doc_earliest_date,
        doc_latest_date,

        -- Best available dates (COALESCE)
        COALESCE(obs_start_date, cp_start_date, apt_first_date, doc_earliest_date) as episode_start,
        COALESCE(obs_stop_date, cp_end_date, apt_last_date, doc_latest_date) as episode_end,

        -- Track which source was used
        CASE
            WHEN obs_start_date IS NOT NULL THEN 'obs_start'
            WHEN cp_start_date IS NOT NULL THEN 'cp_start'
            WHEN apt_first_date IS NOT NULL THEN 'apt_start'
            WHEN doc_earliest_date IS NOT NULL THEN 'doc_start'
            ELSE NULL
        END as start_date_source
    FROM (
        SELECT
            t.patient_fhir_id,
            t.obs_start_date,
            t.obs_stop_date,
            cp.cp_period_start,
            cp.cp_period_end,
            apt.first_appointment_date as apt_first_date,
            apt.last_appointment_date as apt_last_date,
            doc.earliest_document_date as doc_earliest_date,
            doc.latest_document_date as doc_latest_date
        FROM (SELECT DISTINCT patient_fhir_id FROM v_radiation_summary) all_pts
        LEFT JOIN (SELECT patient_fhir_id, MIN(obs_start_date) as obs_start_date, MAX(obs_stop_date) as obs_stop_date FROM v_radiation_treatments GROUP BY patient_fhir_id) t ON all_pts.patient_fhir_id = t.patient_fhir_id
        LEFT JOIN (SELECT patient_fhir_id, MIN(cp_period_start) as cp_period_start, MAX(cp_period_end) as cp_period_end FROM v_radiation_care_plan_hierarchy GROUP BY patient_fhir_id) cp ON all_pts.patient_fhir_id = cp.patient_fhir_id
        LEFT JOIN (SELECT patient_fhir_id, MIN(appointment_start) as first_appointment_date, MAX(appointment_start) as last_appointment_date FROM v_radiation_treatment_appointments GROUP BY patient_fhir_id) apt ON all_pts.patient_fhir_id = apt.patient_fhir_id
        LEFT JOIN (SELECT patient_fhir_id, MIN(doc_date) as earliest_document_date, MAX(doc_date) as latest_document_date FROM v_radiation_documents GROUP BY patient_fhir_id) doc ON all_pts.patient_fhir_id = doc.patient_fhir_id
    ) combined
)
SELECT
    start_date_source,
    COUNT(*) as patients_using_this_source,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM episode_dates
WHERE episode_start IS NOT NULL
GROUP BY start_date_source
ORDER BY patients_using_this_source DESC
```

**Expected Output**:
| start_date_source | patients_using_this_source | percentage |
|-------------------|----------------------------|------------|
| doc_start | ~400-500 | ~45-55% |
| cp_start | ~200-300 | ~22-33% |
| apt_start | ~100-150 | ~11-16% |
| obs_start | ~90 | ~10% |

**Critical Validation**:
- Are dates reasonable? (No future dates, no dates before 1990)
- Sample 20 patients with multiple date sources: Do priorities make clinical sense?

---

### Stage 3: Appointment-Episode Linking Testing

**Goal**: Validate temporal overlap logic for linking appointments to episodes.

```sql
-- Test appointment linkage accuracy
WITH episodes AS (
    -- Simplified episode creation for testing
    SELECT
        patient_fhir_id,
        'test_episode_1' as episode_id,
        TIMESTAMP '2023-01-15 00:00:00' as episode_start,
        TIMESTAMP '2023-03-01 00:00:00' as episode_end
    FROM (SELECT DISTINCT patient_fhir_id FROM v_radiation_treatment_appointments LIMIT 10)
),
linked_appointments AS (
    SELECT
        e.patient_fhir_id,
        e.episode_id,
        a.appointment_id,
        a.appointment_start,
        CASE
            WHEN a.appointment_start >= e.episode_start
                 AND a.appointment_start <= e.episode_end THEN 'WITHIN_EPISODE'
            WHEN a.appointment_start < e.episode_start THEN 'BEFORE_EPISODE'
            WHEN a.appointment_start > e.episode_end THEN 'AFTER_EPISODE'
        END as appointment_timing
    FROM episodes e
    LEFT JOIN v_radiation_treatment_appointments a
        ON e.patient_fhir_id = a.patient_fhir_id
)
SELECT
    appointment_timing,
    COUNT(*) as total_appointments
FROM linked_appointments
GROUP BY appointment_timing
```

**Expected Behavior**:
- Majority of appointments should be `WITHIN_EPISODE`
- Some `BEFORE_EPISODE` (simulation appointments) or `AFTER_EPISODE` (follow-up)

**Critical Validation**:
- Sample 5 patients with multiple appointments
- Manually verify episode boundaries align with appointment sequences

---

### Stage 4: Document Temporal Classification Testing

**Goal**: Validate document temporal relationship logic (before/during/after episode).

```sql
-- Test document temporal classification
WITH test_episodes AS (
    SELECT
        patient_fhir_id,
        'test_episode_1' as episode_id,
        TIMESTAMP '2023-01-01' as episode_start,
        TIMESTAMP '2023-02-28' as episode_end
    FROM (SELECT DISTINCT patient_fhir_id FROM v_radiation_documents LIMIT 20)
),
classified_docs AS (
    SELECT
        e.patient_fhir_id,
        e.episode_id,
        d.document_id,
        d.document_category,
        d.doc_date,
        CASE
            WHEN d.doc_date < e.episode_start THEN 'BEFORE_EPISODE'
            WHEN d.doc_date BETWEEN e.episode_start AND e.episode_end THEN 'DURING_EPISODE'
            WHEN d.doc_date > e.episode_end THEN 'AFTER_EPISODE'
            ELSE 'UNKNOWN'
        END as temporal_relationship
    FROM test_episodes e
    LEFT JOIN v_radiation_documents d ON e.patient_fhir_id = d.patient_fhir_id
)
SELECT
    document_category,
    temporal_relationship,
    COUNT(*) as document_count
FROM classified_docs
WHERE temporal_relationship != 'UNKNOWN'
GROUP BY document_category, temporal_relationship
ORDER BY document_category, temporal_relationship
```

**Expected Patterns**:
- **Treatment Summaries**: Majority `AFTER_EPISODE` (created retrospectively)
- **Consultations**: Majority `BEFORE_EPISODE` (planning phase)
- **Progress Notes**: Majority `DURING_EPISODE` (ongoing care)

**Critical Validation**:
- Sample 10 "Treatment Summary" documents with `BEFORE_EPISODE` classification
- **Question**: Are these mislabeled? Or truly pre-treatment summaries?

---

### Stage 5: Re-Irradiation Detection Testing

**Goal**: Validate logic for detecting re-irradiation based on site overlap across courses.

```sql
-- Test re-irradiation detection
WITH patient_courses AS (
    SELECT
        patient_fhir_id,
        course_number,
        radiation_site_codes,
        episode_start_date,
        LAG(radiation_site_codes) OVER (PARTITION BY patient_fhir_id ORDER BY course_number) as prev_course_sites
    FROM v_radiation_treatment_episodes
    WHERE course_number IS NOT NULL
      AND radiation_site_codes IS NOT NULL
)
SELECT
    patient_fhir_id,
    course_number,
    radiation_site_codes as current_sites,
    prev_course_sites,
    CASE
        WHEN course_number > 1
             AND (
                 -- Check for any site code overlap (simple string match for testing)
                 radiation_site_codes LIKE '%' || SPLIT(prev_course_sites, ',')[1] || '%'
                 OR prev_course_sites LIKE '%' || SPLIT(radiation_site_codes, ',')[1] || '%'
             )
        THEN true
        ELSE false
    END as detected_as_reirradiation
FROM patient_courses
WHERE course_number > 1
LIMIT 50
```

**Critical Validation**:
- Manually review 20 patients flagged as `detected_as_reirradiation = true`
- **Question**: Are these truly re-irradiation to same anatomic site?
- **Refine**: May need more sophisticated site overlap logic (e.g., ICD-O-3 topography code mapping)

---

### Stage 6: NLP Document Selection Testing

**Goal**: Validate document prioritization logic for NLP abstraction.

```sql
-- Test NLP document prioritization
WITH nlp_candidates AS (
    SELECT
        e.patient_fhir_id,
        e.episode_id,
        e.course_number,
        e.episode_data_quality_score,
        d.document_id,
        d.document_category,
        d.extraction_priority,
        CASE
            WHEN d.document_id = ANY(e.high_priority_post_episode_doc_ids)
                 AND d.document_category = 'Treatment Summary'
            THEN 'TIER_1_TREATMENT_SUMMARY_POST_EPISODE'

            WHEN d.extraction_priority = 2
                 AND d.doc_date < e.episode_start_datetime
            THEN 'TIER_2_CONSULTATION_PRE_EPISODE'

            WHEN d.doc_date BETWEEN e.episode_start_datetime AND e.episode_end_datetime
                 AND d.document_category = 'Progress Note'
            THEN 'TIER_3_PROGRESS_NOTE_DURING_EPISODE'

            WHEN e.episode_detection_method = 'document_temporal_cluster'
            THEN 'TIER_4_DOCUMENT_ONLY_EPISODE'

            ELSE 'TIER_5_LOW_PRIORITY'
        END as nlp_priority_tier
    FROM v_radiation_treatment_episodes e
    LEFT JOIN v_radiation_documents d ON e.patient_fhir_id = d.patient_fhir_id
)
SELECT
    nlp_priority_tier,
    COUNT(DISTINCT episode_id) as episodes_with_this_tier,
    COUNT(DISTINCT document_id) as total_documents,
    ROUND(AVG(episode_data_quality_score), 3) as avg_episode_quality
FROM nlp_candidates
GROUP BY nlp_priority_tier
ORDER BY
    CASE nlp_priority_tier
        WHEN 'TIER_1_TREATMENT_SUMMARY_POST_EPISODE' THEN 1
        WHEN 'TIER_2_CONSULTATION_PRE_EPISODE' THEN 2
        WHEN 'TIER_3_PROGRESS_NOTE_DURING_EPISODE' THEN 3
        WHEN 'TIER_4_DOCUMENT_ONLY_EPISODE' THEN 4
        WHEN 'TIER_5_LOW_PRIORITY' THEN 5
    END
```

**Expected Distribution**:
- **TIER_1**: ~50-100 episodes (treatment summaries are rare)
- **TIER_2**: ~200-300 episodes (consultations more common)
- **TIER_3**: ~300-400 episodes (progress notes during treatment)
- **TIER_4**: ~100-200 episodes (document-only patients)

**Critical Validation**:
- Sample 10 documents from each tier
- **Question**: Does prioritization align with NLP extraction value?
- **Refine**: Adjust tier criteria based on manual review

---

### Stage 7: End-to-End Episode Quality Testing

**Goal**: Validate complete episode creation across all 913 radiation patients.

```sql
-- Final coverage and quality assessment
WITH episode_summary AS (
    SELECT
        'All Patients' as cohort,
        COUNT(DISTINCT patient_fhir_id) as total_patients
    FROM v_radiation_summary

    UNION ALL

    SELECT
        'Patients with Episodes' as cohort,
        COUNT(DISTINCT patient_fhir_id) as total_patients
    FROM v_radiation_treatment_episodes
)
SELECT * FROM episode_summary

UNION ALL

SELECT
    'Episode Quality: ' || data_quality_tier as cohort,
    COUNT(DISTINCT patient_fhir_id) as total_patients
FROM v_radiation_treatment_episodes
GROUP BY data_quality_tier

UNION ALL

SELECT
    'Episode Detection: ' || episode_detection_method as cohort,
    COUNT(DISTINCT episode_id) as total_patients
FROM v_radiation_treatment_episodes
GROUP BY episode_detection_method
```

**Success Criteria**:
- **Coverage**: ≥ 90% of 913 patients have at least 1 episode created (~820+ patients)
- **Quality Distribution**:
  - HIGH quality: ~10-15% (complete structured + documents)
  - MEDIUM quality: ~40-50% (partial structured or care plans)
  - LOW quality: ~35-45% (appointment/document only)
- **Detection Method Distribution**:
  - Structured course ID: ~10%
  - Care plan periods: ~50-60%
  - Appointment temporal: ~20-30%
  - Document temporal: ~10-15%

**Critical Validation**:
- If coverage < 90%, investigate patients without episodes
- Sample 20 patients across all quality tiers and detection methods
- Manually review episode boundaries, dates, and metadata accuracy

---

## Implementation Recommendations

### Phased Development Approach

**Phase 1: Foundation (Week 1)**
- Implement episode detection strategies A-D independently
- Run Stage 1 testing (episode detection coverage)
- Validate temporal windowing thresholds (14-day gap, 60-day gap)

**Phase 2: Date Resolution (Week 1-2)**
- Implement COALESCE logic for multi-source dates
- Run Stage 2 testing (date source priority)
- Add source tracking fields for transparency

**Phase 3: Entity Linking (Week 2)**
- Implement appointment-episode linking
- Implement document-episode temporal classification
- Run Stages 3-4 testing

**Phase 4: Enrichment (Week 2-3)**
- Add episode sequencing (course_number, is_first_course)
- Add re-irradiation detection
- Add data quality scoring
- Run Stage 5 testing

**Phase 5: NLP Optimization (Week 3)**
- Add NLP priority tiers
- Add document selection logic
- Run Stage 6 testing

**Phase 6: Integration & Validation (Week 3-4)**
- Create v_radiation_course_timeline view
- Run Stage 7 end-to-end testing
- Document any edge cases or limitations

### Performance Optimization Strategies

1. **Materialize intermediate CTEs** for frequently-used sub-queries
2. **Index patient_fhir_id** on all source views
3. **Partition by date** if episode queries become slow (unlikely with ~1K patients)
4. **Consider materialized view** for v_radiation_treatment_episodes if refresh latency is acceptable

### Data Quality Monitoring

Establish ongoing data quality checks:

```sql
-- Weekly data quality report
SELECT
    DATE(CURRENT_TIMESTAMP) as report_date,
    COUNT(DISTINCT patient_fhir_id) as total_patients_with_episodes,
    COUNT(DISTINCT CASE WHEN data_quality_tier = 'HIGH' THEN patient_fhir_id END) as high_quality_count,
    COUNT(DISTINCT CASE WHEN has_episode_dates = false THEN episode_id END) as episodes_missing_dates,
    COUNT(DISTINCT CASE WHEN num_fractions = 0 THEN episode_id END) as episodes_missing_fractions,
    AVG(episode_data_quality_score) as avg_quality_score
FROM v_radiation_treatment_episodes
```

---

## Appendix: Gap Threshold Rationale

### Appointment Temporal Windowing: 14-Day Gap

**Clinical Context**:
- Standard radiation fractionation: 5 days/week (Monday-Friday)
- Typical course duration: 4-6 weeks
- Planned treatment breaks: Weekends (2 days), occasional holidays (3-4 days)

**14-Day Threshold Rationale**:
- Allows for 2 consecutive weekends + 1 mid-week holiday
- Distinguishes between "treatment pause" vs "new treatment course"
- Conservative enough to avoid over-splitting single courses
- Permissive enough to separate truly distinct courses

**Alternative Thresholds to Test**:
- **10 days**: More aggressive splitting (may separate continuous courses with holiday breaks)
- **21 days**: More permissive (may merge distinct courses scheduled close together)

### Document Temporal Clustering: 60-Day Gap

**Clinical Context**:
- Treatment summaries typically created within 30 days post-treatment
- Consultation notes may occur 1-2 months before treatment start
- Recurrence treatment often occurs 6+ months after initial treatment

**60-Day Threshold Rationale**:
- Captures all documents related to single treatment episode
- Separates documents for initial treatment vs recurrence treatment
- Allows for realistic documentation delays post-treatment

**Alternative Thresholds to Test**:
- **30 days**: More aggressive (may split single episode documents)
- **90 days**: More permissive (may merge initial + early recurrence documents)

---

## Appendix: Example Patient Scenarios

### Scenario 1: Complete Structured Data + Documents (IDEAL)

**Patient**: `Patient/ABC123`

**Available Data**:
- v_radiation_treatments: 2 course IDs (Line 1, Line 2)
  - Line 1: Cranial, 5400 cGy, dates 2023-01-15 to 2023-03-01
  - Line 2: Spine, 3000 cGy, dates 2024-06-01 to 2024-07-15 (re-irradiation)
- v_radiation_care_plan_hierarchy: 2 care plans matching treatment dates
- v_radiation_treatment_appointments: 54 appointments (30 for Line 1, 24 for Line 2)
- v_radiation_documents:
  - Consultation note 2023-01-05 (before Line 1)
  - Treatment summary 2023-03-10 (after Line 1)
  - Consultation note 2024-05-20 (before Line 2)
  - Treatment summary 2024-07-25 (after Line 2)

**Episode Creation**:
- **Episode 1**:
  - `episode_id`: `ABC123_course_Line1`
  - `course_number`: 1
  - `episode_detection_method`: structured_course_id
  - `episode_start_date`: 2023-01-15 (from obs_start_date)
  - `episode_end_date`: 2023-03-01 (from obs_stop_date)
  - `total_dose_cgy`: 5400
  - `radiation_sites_summary`: Cranial
  - `num_fractions`: 30
  - `num_documents_before_episode`: 1
  - `num_documents_after_episode`: 1
  - `data_quality_tier`: HIGH
  - `nlp_priority_tier`: TIER_1 (has treatment summary post-episode)

- **Episode 2**:
  - `episode_id`: `ABC123_course_Line2`
  - `course_number`: 2
  - `is_reirradiation`: false (different site: spine vs cranial)
  - `days_since_previous_course`: 457 (15 months gap)
  - Similar metadata as Episode 1

### Scenario 2: Care Plan Only (MEDIUM QUALITY)

**Patient**: `Patient/DEF456`

**Available Data**:
- v_radiation_treatments: NO structured data
- v_radiation_care_plan_hierarchy: 1 care plan
  - cp_period_start: 2023-04-01
  - cp_period_end: 2023-05-30
  - cp_title: "Radiation Oncology - Brain"
- v_radiation_treatment_appointments: 25 appointments between 2023-04-03 and 2023-05-28
- v_radiation_documents:
  - Consultation 2023-03-25
  - 3 progress notes during April-May

**Episode Creation**:
- **Episode 1**:
  - `episode_id`: `DEF456_cp_12345`
  - `course_number`: 1
  - `episode_detection_method`: care_plan_period
  - `episode_start_date`: 2023-04-01 (from cp_period_start)
  - `episode_end_date`: 2023-05-30 (from cp_period_end)
  - `total_dose_cgy`: NULL (no structured data)
  - `radiation_sites_summary`: "Brain" (inferred from care plan title)
  - `num_fractions`: 25 (linked from appointments)
  - `num_documents_before_episode`: 1
  - `num_documents_during_episode`: 3
  - `data_quality_tier`: MEDIUM
  - `nlp_priority_tier`: TIER_2 (has consultation pre-episode, but no treatment summary)

### Scenario 3: Appointment Temporal Window Only (MEDIUM-LOW QUALITY)

**Patient**: `Patient/GHI789`

**Available Data**:
- v_radiation_treatments: NO structured data
- v_radiation_care_plan_hierarchy: NO care plans
- v_radiation_treatment_appointments:
  - 20 appointments 2022-09-01 to 2022-10-15 (cluster 1)
  - 15 appointments 2023-08-05 to 2023-09-20 (cluster 2, gap = 294 days)
- v_radiation_documents: 1 progress note during cluster 1

**Episode Creation**:
- **Episode 1**:
  - `episode_id`: `GHI789_apt_episode_1`
  - `course_number`: 1
  - `episode_detection_method`: appointment_temporal_window
  - `episode_start_date`: 2022-09-01 (first appointment)
  - `episode_end_date`: 2022-10-15 (last appointment)
  - `total_dose_cgy`: NULL
  - `radiation_sites_summary`: NULL
  - `num_fractions`: 20
  - `data_quality_tier`: LOW
  - `nlp_priority_tier`: TIER_3 (only progress note during episode)

- **Episode 2**:
  - `episode_id`: `GHI789_apt_episode_2`
  - `course_number`: 2
  - `days_since_previous_course`: 294
  - Similar metadata, likely re-irradiation (same patient, 10 months later)

### Scenario 4: Document-Only (LOW QUALITY, HIGH NLP DEPENDENCY)

**Patient**: `Patient/JKL012`

**Available Data**:
- v_radiation_treatments: NO structured data
- v_radiation_care_plan_hierarchy: NO care plans
- v_radiation_treatment_appointments: NO appointments
- v_radiation_documents:
  - Treatment summary 2021-06-15
  - Consultation 2021-04-10
  - Progress note 2021-05-20

**Episode Creation**:
- **Episode 1**:
  - `episode_id`: `JKL012_doc_episode_1`
  - `course_number`: 1
  - `episode_detection_method`: document_temporal_cluster
  - `episode_start_date`: 2021-04-10 (earliest doc date)
  - `episode_end_date`: 2021-06-15 (latest doc date)
  - `total_dose_cgy`: NULL (must extract from documents via NLP)
  - `radiation_sites_summary`: NULL (must extract from documents via NLP)
  - `num_fractions`: NULL
  - `num_documents_after_episode`: 0 (using doc dates as boundaries, no post-episode docs)
  - `data_quality_tier`: LOW
  - `nlp_priority_tier`: TIER_4 (document-only, extract treatment summary 2021-06-15)
  - **NLP Strategy**: Extract ALL treatment details from treatment summary document

---

## Success Metrics

### Coverage Metrics
- ✅ **≥ 90%** of 913 radiation patients have ≥ 1 episode created
- ✅ **≥ 80%** of episodes have valid start/end dates
- ✅ **≥ 60%** of episodes have ≥ 1 document linked

### Quality Metrics
- ✅ **≥ 15%** of episodes are HIGH quality (complete structured + documents)
- ✅ **≥ 40%** of episodes are MEDIUM quality (partial data)
- ✅ **≥ 95%** of episodes have data_quality_score > 0.25

### NLP Readiness Metrics
- ✅ **≥ 100** episodes have TIER_1 treatment summaries post-episode
- ✅ **≥ 300** episodes have TIER_2 consultations pre-episode
- ✅ **≥ 500** episodes have ≥ 1 NLP-extractable document

### Timeline Integration Metrics
- ✅ v_radiation_course_timeline successfully unions with v_medication_episodes
- ✅ Unified timeline contains all treatment modalities for sample patient cohort
- ✅ Timeline visualization renders without errors

---

## Conclusion

This design document provides a comprehensive blueprint for creating radiation episode views that:

1. **Maximize patient coverage** through hybrid episode detection (structured + temporal + care plan + document)
2. **Enable layered timeline visualization** via simplified timeline integration view
3. **Optimize NLP/LLM abstraction** through document temporal classification and prioritization
4. **Support re-irradiation tracking** via episode sequencing and site overlap detection
5. **Ensure data transparency** through source tracking and quality scoring

The phased testing approach ensures each component is validated independently before integration, minimizing errors and enabling iterative refinement based on real data patterns.

**Next Steps**: Proceed to implementation Phase 1 (episode detection strategies), validate with Stage 1 testing queries, and iterate based on findings.
