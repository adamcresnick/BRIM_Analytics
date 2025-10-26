# Patient Timeline Construction - Deep Dive

## Overview

The patient timeline is a **DuckDB database** that serves as the central temporal backbone for the extraction workflow. It contains structured event data and extracted clinical variables, enabling temporal context queries and multi-source data integration.

---

## Timeline Database Schema

### Database Location
- **File**: `data/timeline.duckdb`
- **Technology**: DuckDB (embedded analytical database)
- **Access**: `TimelineQueryInterface` class

### Three Core Tables

#### 1. **`patients` Table**
Stores patient demographics and milestone dates.

**Schema**:
```sql
CREATE TABLE patients (
    patient_id VARCHAR PRIMARY KEY,
    birth_date DATE,
    sex VARCHAR,
    race VARCHAR,
    ethnicity VARCHAR,

    -- Milestone dates
    first_diagnosis_date TIMESTAMP,
    first_surgery_date TIMESTAMP,
    first_treatment_date TIMESTAMP,
    first_radiation_date TIMESTAMP,
    last_followup_date TIMESTAMP,

    -- Demographics
    deceased BOOLEAN DEFAULT FALSE,
    deceased_date DATE,
    age_at_diagnosis_days INTEGER,
    age_at_surgery_days INTEGER,
    followup_duration_days INTEGER,

    -- Metadata
    extraction_date TIMESTAMP,
    data_version VARCHAR
)
```

**What Populates It**:
- Built during initial timeline construction from Athena `v_patient_demographics`
- Milestone dates computed from event analysis
- Updated once per patient, not modified during extraction

#### 2. **`events` Table**
The core timeline - all clinical events chronologically ordered.

**Schema**:
```sql
CREATE TABLE events (
    event_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,

    -- Temporal information
    event_date TIMESTAMP NOT NULL,
    event_date_precision VARCHAR DEFAULT 'day',
    age_at_event_days INTEGER,
    age_at_event_years DECIMAL(5,2),

    -- Event classification
    event_type VARCHAR NOT NULL,           -- 'Imaging', 'Procedure', 'Medication', 'Diagnosis', 'Radiation'
    event_category VARCHAR,                -- 'Surgery', 'Chemotherapy', 'Targeted Therapy', 'Tumor'
    event_subtype VARCHAR,
    description TEXT,
    event_status VARCHAR,

    -- Data source tracking
    source_view VARCHAR NOT NULL,          -- Athena view name (e.g., 'v_imaging', 'v_procedures_tumor')
    source_domain VARCHAR NOT NULL,        -- FHIR domain (e.g., 'ImagingStudy', 'Procedure')
    source_id VARCHAR,                     -- Source FHIR resource ID

    -- Code mappings
    icd10_codes VARCHAR[],
    snomed_codes VARCHAR[],
    cpt_codes VARCHAR[],
    loinc_codes VARCHAR[],

    -- Computed temporal context
    days_since_diagnosis INTEGER,
    days_since_surgery INTEGER,
    days_since_treatment_start INTEGER,
    disease_phase VARCHAR,                 -- 'Pre-diagnosis', 'Diagnostic', 'Post-surgical', 'On-treatment', 'Surveillance'
    treatment_status VARCHAR,              -- 'Treatment-naive', 'On-treatment', 'Off-treatment'

    -- Extended metadata
    metadata JSON,
    extraction_context JSON,

    -- Provenance
    extracted_from_source VARCHAR DEFAULT 'athena_v_unified_timeline',
    extraction_timestamp TIMESTAMP
)
```

**What Populates It**:
- **Source**: Athena `v_unified_patient_timeline` view (unified across all FHIR domains)
- **Initial Load**: `build_timeline_database.py` exports from Athena
- **Temporal Context**: Computed fields added during load:
  - `days_since_diagnosis/surgery/treatment_start`
  - `disease_phase` (Pre-diagnosis → Diagnostic → Post-surgical → On-treatment → Surveillance)
  - `treatment_status` (Treatment-naive → On-treatment → Off-treatment)
- **ChemotherapyFilter**: Medication categorization corrected using reference lists
- **During Extraction**: NO new events added (read-only during extraction)

**Event Types**:
- **Imaging**: MRI, CT, PET scans (from `v_imaging`)
- **Procedure**: Surgeries, biopsies (from `v_procedures_tumor`)
- **Medication**: All medications (from `v_medications`)
  - **Category**: Chemotherapy, Targeted Therapy, Supportive Care (filtered by ChemotherapyFilter)
- **Diagnosis**: Tumor diagnoses (from `v_diagnoses`)
- **Radiation**: Radiation treatments (from `v_radiation_summary`)

#### 3. **`extracted_variables` Table**
Stores LLM-extracted clinical variables from documents.

**Schema**:
```sql
CREATE TABLE extracted_variables (
    extraction_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,

    -- Source document info
    source_event_id VARCHAR,               -- Links to events.event_id
    source_document_type VARCHAR,          -- 'operative_note', 'progress_note', 'imaging_pdf'
    source_document_date DATE,
    source_text TEXT,                      -- Relevant excerpt

    -- Extracted variable
    variable_name VARCHAR NOT NULL,        -- 'tumor_status', 'extent_of_resection', 'tumor_location'
    variable_value VARCHAR,                -- Extracted value
    variable_confidence DECIMAL(3,2),      -- 0.0-1.0

    -- Temporal context (copied from source event)
    event_date TIMESTAMP,
    days_since_diagnosis INTEGER,
    disease_phase VARCHAR,
    treatment_status VARCHAR,

    -- Extraction provenance
    extraction_method VARCHAR,             -- 'medgemma', 'claude', 'manual'
    extraction_timestamp TIMESTAMP,
    model_version VARCHAR,
    prompt_version VARCHAR,

    -- Validation
    validated BOOLEAN DEFAULT FALSE,
    validation_status VARCHAR,
    validation_notes TEXT,

    -- Conflict resolution
    conflicts_with_extraction_ids VARCHAR[],
    conflict_resolution_rule VARCHAR,

    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (source_event_id) REFERENCES events(event_id)
)
```

**What Populates It**:
- **Written During PHASE 6** (Event Classification)
- **Variables Extracted**:
  - `tumor_status`: From imaging PDFs, operative notes, progress notes
  - `extent_of_resection`: From operative notes
  - `tumor_location`: From all document types
- **Purpose**: Make extracted variables queryable by event classifier and temporal analysis

---

## Timeline Construction Process

### Initial Build (Pre-Extraction)

**Script**: `build_timeline_database.py`

**Steps**:

1. **Export from Athena** (`v_unified_patient_timeline`)
   ```sql
   SELECT * FROM v_unified_patient_timeline
   WHERE patient_fhir_id = '<patient_id>'
   ORDER BY event_date
   ```
   - Returns: All events across FHIR domains (Imaging, Procedure, Medication, Diagnosis, etc.)

2. **Apply ChemotherapyFilter**
   - Query `v_medications` for medication names and RxNorm codes
   - Use `ChemotherapyFilter` reference lists to classify:
     - **Chemotherapy**: Traditional cytotoxic agents
     - **Targeted Therapy**: Selumetinib, dabrafenib, trametinib, etc.
   - Update `event_category` for medication events

3. **Compute Milestones**
   ```python
   milestones = {
       'first_diagnosis_date': min(diagnosis events),
       'first_surgery_date': min(surgery events),
       'first_treatment_date': min(chemotherapy/targeted therapy events),
       'first_radiation_date': min(radiation events)
   }
   ```

4. **Compute Temporal Context**
   - `days_since_diagnosis` = event_date - first_diagnosis_date
   - `days_since_surgery` = event_date - first_surgery_date
   - `days_since_treatment_start` = event_date - first_treatment_date

   - **Disease Phase** (rule-based):
     - **Pre-diagnosis**: Before first diagnosis
     - **Diagnostic**: Diagnosis → first surgery (max 90 days)
     - **Post-surgical**: First surgery → first treatment (max 180 days)
     - **On-treatment**: First treatment → +365 days
     - **Surveillance**: >365 days after treatment start
     - **Observation**: All other periods

   - **Treatment Status**:
     - **Treatment-naive**: Before first treatment date
     - **On-treatment**: First treatment → +365 days
     - **Off-treatment**: >365 days after treatment

5. **Load into DuckDB**
   - Create tables (patients, events, extracted_variables)
   - Insert patient record with milestones
   - Insert events with computed temporal fields
   - Create indexes on patient_id, event_date, event_type, event_category

**Result**: Static timeline database ready for extraction queries

---

## Timeline Usage During Extraction

### PHASE 1: Data Query
**Timeline Access**: Read-only query for medication-based prioritization

```python
# Query chemotherapy/targeted therapy start events
chemo_events_df = timeline.conn.execute(f"""
    SELECT event_id, event_date, event_category, description
    FROM events
    WHERE patient_id = '{patient_id}'
      AND event_type = 'Medication'
      AND event_category IN ('Chemotherapy', 'Targeted Therapy')
    ORDER BY event_date
""").fetchdf()
```

**Purpose**: Get medication change dates for progress note prioritization (±14 day windows)

**After Query**: `timeline.close()` to avoid DuckDB lock conflicts

---

### PHASE 2-5: Extraction Phases
**Timeline Access**: None (closed to avoid locks)

**Data Flow**:
1. Extract data from documents (imaging, operative notes, progress notes)
2. Store extractions in memory (`all_extractions` list)
3. No writes to timeline during this phase

---

### PHASE 6: Event Classification
**Timeline Access**: Write extracted variables

**What Gets Written**:

1. **Tumor Status Extractions** (from all document types):
   ```python
   timeline.conn.execute('''
       INSERT OR IGNORE INTO extracted_variables
       (patient_id, source_event_id, variable_name, variable_value,
        variable_confidence, extraction_date)
       VALUES (?, ?, ?, ?, ?, ?)
   ''', [
       patient_id,
       extraction['source_id'],      # Event ID from events table
       'tumor_status',
       tumor_status,                 # e.g., 'Residual tumor', 'No evidence of disease'
       confidence,                   # 0.0-1.0
       datetime.now()
   ])
   ```

2. **Extent of Resection** (from operative notes):
   ```python
   timeline.conn.execute('''
       INSERT OR IGNORE INTO extracted_variables
       (patient_id, source_event_id, variable_name, variable_value,
        variable_confidence, extraction_date)
       VALUES (?, ?, ?, ?, ?, ?)
   ''', [
       patient_id,
       extraction['source_id'],
       'extent_of_resection',
       eor_value,                    # 'GTR', 'STR', 'Biopsy only'
       confidence,
       datetime.now()
   ])
   ```

**Purpose**: Event classifier can query extracted variables to classify clinical events

---

## What's IN vs. NOT IN the Timeline

### ✅ **IN the Timeline** (from Athena)

| Event Type | Source Athena View | Count (Typical) |
|------------|-------------------|-----------------|
| **Imaging** | `v_imaging` | ~250-300 scans |
| **Procedures** | `v_procedures_tumor` | ~10-15 surgeries |
| **Medications** | `v_medications` | ~1,000-1,500 orders |
| **Diagnoses** | `v_diagnoses` | ~50-100 diagnoses |
| **Radiation** | `v_radiation_summary` | ~0-5 courses |
| **Labs** | `v_labs` (if included) | ~500-1,000 results |
| **Vital Signs** | `v_vitals` (if included) | ~100-200 measurements |

### ❌ **NOT IN the Timeline** (queried separately during extraction)

| Data Type | Why NOT in Timeline | Where Queried |
|-----------|---------------------|---------------|
| **Document Text** | Too large (100KB-5MB per document) | S3 via BinaryFileAgent |
| **Operative Note PDFs** | Binary content | Athena `v_binary_files` → S3 |
| **Progress Note PDFs** | Binary content | Athena `v_binary_files` → S3 |
| **Imaging Report PDFs** | Binary content | Athena `v_binary_files` → S3 |
| **Radiation Plans** | Separate query | Athena `v_radiation_summary` |
| **Chemotherapy Courses** | Computed during extraction | Built from `v_chemo_medications` |

**Rationale**: Timeline contains **event metadata** (dates, types, categories). **Document content** is fetched on-demand during extraction to avoid massive database size.

---

## Temporal Context Computation

### How It Works

The timeline enables **temporal queries** like:
- "What treatments was the patient on during this imaging scan?"
- "How many days after surgery was this operative note written?"
- "Was this imaging during surveillance or on-treatment?"

**Example Query** (used by event classifier):
```python
# Get events within ±30 days of target date
context_events = timeline.conn.execute("""
    SELECT * FROM events
    WHERE patient_id = ?
      AND event_date BETWEEN ? AND ?
      AND event_id != ?
    ORDER BY event_date
""", [patient_id, target_date - 30 days, target_date + 30 days, exclude_event_id])
```

**Example Query** (medications active at date):
```python
# Get medications before/on target date
active_meds = timeline.conn.execute("""
    SELECT * FROM events
    WHERE patient_id = ?
      AND event_type = 'Medication'
      AND event_date <= ?
    ORDER BY event_date DESC
    LIMIT 10
""", [patient_id, target_date])
```

---

## Timeline Schema Extensions (Future)

### Planned Additions

1. **`source_documents` Table** (referenced but not implemented):
   ```sql
   CREATE TABLE source_documents (
       document_id VARCHAR PRIMARY KEY,
       patient_id VARCHAR,
       source_event_id VARCHAR,
       document_type VARCHAR,  -- 'radiology_report', 'operative_note', 'progress_note'
       document_text TEXT,
       char_count INTEGER,
       document_date TIMESTAMP,
       metadata JSON,
       FOREIGN KEY (source_event_id) REFERENCES events(event_id)
   )
   ```
   **Purpose**: Cache document text in timeline for faster re-extraction

2. **`treatment_courses` Table** (for chemotherapy/radiation grouping):
   ```sql
   CREATE TABLE treatment_courses (
       course_id VARCHAR PRIMARY KEY,
       patient_id VARCHAR,
       course_type VARCHAR,  -- 'Chemotherapy', 'Radiation'
       start_date TIMESTAMP,
       end_date TIMESTAMP,
       medications_included VARCHAR[],
       fractions_delivered INTEGER,
       FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
   )
   ```

3. **`event_relationships` Table** (link related events):
   ```sql
   CREATE TABLE event_relationships (
       relationship_id VARCHAR PRIMARY KEY,
       source_event_id VARCHAR,
       target_event_id VARCHAR,
       relationship_type VARCHAR,  -- 'follows', 'caused_by', 'related_to'
       confidence DECIMAL(3,2),
       FOREIGN KEY (source_event_id) REFERENCES events(event_id),
       FOREIGN KEY (target_event_id) REFERENCES events(event_id)
   )
   ```

---

## Summary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      TIMELINE CONSTRUCTION                       │
└─────────────────────────────────────────────────────────────────┘

BEFORE EXTRACTION:
┌──────────────────┐
│  Athena Queries  │
│                  │
│ • v_unified_     │
│   patient_       │
│   timeline       │
│ • v_medications  │
│ • v_patient_     │
│   demographics   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ ChemotherapyFilter│
│ (classify meds)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Compute          │
│ • Milestones     │
│ • Temporal ctx   │
│ • Disease phase  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ DuckDB Timeline  │
│                  │
│ • patients       │
│ • events         │
│ • extracted_     │
│   variables      │
└──────────────────┘

DURING EXTRACTION:
┌──────────────────┐
│  PHASE 1         │
│  Query timeline  │
│  for med changes │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  PHASE 2-5       │
│  Extract from    │
│  documents       │
│  (timeline       │
│   closed)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  PHASE 6         │
│  Write extracted_│
│  variables to    │
│  timeline        │
└──────────────────┘
```

---

## Key Insights

1. **Timeline is Pre-Built**: Constructed before extraction from Athena unified view

2. **Event Metadata Only**: Timeline stores event dates/types, NOT document content

3. **Temporal Backbone**: Enables date-based queries (±N days from event)

4. **Two-Way Flow**:
   - **Read**: Query events for context (PHASE 1)
   - **Write**: Store extracted variables (PHASE 6)

5. **Read-Only During Extraction**: Closed during PHASE 2-5 to avoid locks

6. **Extracted Variables Purpose**: Make LLM extractions queryable for event classification

7. **DuckDB Benefits**:
   - Embedded (no server needed)
   - Fast analytical queries
   - SQL interface
   - JSON support

---

## Files Reference

| File | Purpose |
|------|---------|
| `build_timeline_database.py` | Initial timeline construction from Athena |
| `timeline_query_interface.py` | Query API wrapper for timeline |
| `run_full_multi_source_abstraction.py` | Uses timeline for med queries + writes extractions |
| `agents/event_type_classifier.py` | Queries timeline for event classification |
| `data/timeline.duckdb` | The actual database file |
