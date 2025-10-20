# Timeline Storage and Query Architecture for Multi-Agent Context

**Purpose**: Define optimal storage architecture for comprehensive patient timelines that enables both Agent 1 (Claude) and Agent 2 (MedGemma/Ollama) to query temporal context for data extraction, validation, and adjudication.

**Date Created**: 2025-10-19
**Status**: Design Specification

---

## 1. Core Requirements

### 1.1 Agent Query Use Cases

**Agent 1 (Claude - Orchestrator) Needs**:
1. "What imaging studies occurred within 30 days before this surgery?"
2. "What was the patient's treatment regimen when this progression event occurred?"
3. "What surgeries happened between diagnosis and chemotherapy start?"
4. "Is this molecular test from the initial tumor or a recurrence specimen?"
5. "What was the patient's disease status at this encounter date?"
6. "Show me all events in a 90-day window around this radiation start date"

**Agent 2 (MedGemma - Extractor) Needs**:
1. Receive document text WITH temporal context: "This is an MRI from 2018-08-03, 58 days post-surgery, during active surveillance before treatment start"
2. Validate extracted values: "Is 'progression' consistent with this being 2 months after initial surgery?"
3. Disambiguate: "Is this 'astrocytoma' the initial diagnosis or a recurrence?" (based on date relative to prior diagnoses)
4. Contextualize extracted values: "Extracted 'extent of resection: gross total' - this is from the FIRST surgery, not a re-resection"

### 1.2 Data Architecture Goals

1. **Temporal Queryability**: Fast retrieval of events within date windows
2. **Contextual Enrichment**: Every event annotated with disease phase, treatment status, milestone proximity
3. **Bi-Directional Navigation**: Query forward ("what happened after X?") and backward ("what led to X?")
4. **Multi-Source Linkage**: Connect related events (imaging → procedure → diagnosis → treatment)
5. **Agent-Readable Format**: Serialize context into LLM-consumable text
6. **Conflict Resolution Support**: Track provenance when same variable extracted from multiple sources
7. **Scalability**: Handle 100+ patients with 10,000+ events each

---

## 2. Proposed Architecture: **DuckDB Timeline Database**

### 2.1 Why DuckDB?

✅ **Optimal Choice for This Use Case**

**Advantages**:
1. **Embedded Database**: No server setup; single file per patient or cohort
2. **SQL Interface**: Rich temporal queries with window functions, CTEs
3. **Fast Analytics**: Columnar storage optimized for analytical queries (not just row lookups)
4. **JSON Support**: Native JSON type for nested metadata
5. **Parquet Integration**: Can query Parquet files directly without loading
6. **Python Native**: First-class Python integration via `duckdb` library
7. **Temporal Functions**: Built-in date/time functions, interval arithmetic
8. **Small Footprint**: Lightweight; no memory overhead
9. **ACID Transactions**: Ensures data consistency during multi-step extractions

**Comparison to Alternatives**:
- ❌ **JSON files**: Not queryable; must load entire file; no indexing
- ❌ **CSV files**: No nested structures; no efficient temporal queries
- ❌ **SQLite**: Limited analytical query performance; weaker JSON support
- ❌ **PostgreSQL**: Overkill; requires server; harder to distribute
- ✅ **Parquet + DuckDB**: Best of both worlds (Parquet for storage, DuckDB for queries)

### 2.2 Storage Strategy: **Hybrid Approach**

**Three-Layer Architecture**:

```
Layer 1: PARQUET FILES (Archival Storage)
└── /data/timelines/parquet/
    ├── patient_{patient_id}_timeline.parquet
    └── patient_{patient_id}_timeline_metadata.json

Layer 2: DUCKDB DATABASE (Query Layer)
└── /data/timelines/timeline.duckdb
    ├── patient_timelines table (all patients)
    ├── events table (all events, indexed by patient_id, event_date)
    ├── event_windows table (pre-computed contextual windows)
    └── milestones table (diagnosis, surgery, treatment start/end per patient)

Layer 3: AGENT CONTEXT CACHE (LLM-Formatted Text)
└── /data/timelines/agent_context/
    ├── patient_{patient_id}_context.md (human-readable timeline)
    └── patient_{patient_id}_event_{event_id}_context.json (LLM-formatted event context)
```

**Workflow**:
1. **Extract** → Write to Parquet (append-only, immutable)
2. **Load** → Import Parquet into DuckDB for querying
3. **Query** → DuckDB temporal queries generate agent context
4. **Cache** → Store frequently-used contexts as pre-formatted text/JSON

---

## 3. Database Schema Design

### 3.1 Core Tables

#### Table 1: `patients`
```sql
CREATE TABLE patients (
    patient_id VARCHAR PRIMARY KEY,
    birth_date DATE NOT NULL,
    sex VARCHAR,
    race VARCHAR,
    ethnicity VARCHAR,
    first_diagnosis_date DATE,
    first_surgery_date DATE,
    first_treatment_date DATE,
    last_followup_date DATE,
    deceased BOOLEAN DEFAULT FALSE,
    deceased_date DATE,

    -- Derived fields
    age_at_diagnosis_days INTEGER,
    age_at_surgery_days INTEGER,
    followup_duration_days INTEGER,

    -- Metadata
    extraction_date TIMESTAMP,
    data_version VARCHAR
);

CREATE INDEX idx_patients_diagnosis_date ON patients(first_diagnosis_date);
```

#### Table 2: `events` (Core Timeline)
```sql
CREATE TABLE events (
    event_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,

    -- Temporal fields
    event_date TIMESTAMP NOT NULL,
    event_date_precision VARCHAR DEFAULT 'day',  -- 'day', 'month', 'year'
    age_at_event_days INTEGER NOT NULL,
    age_at_event_years DECIMAL(5,2),

    -- Event classification
    event_type VARCHAR NOT NULL,  -- 'Diagnosis', 'Procedure', 'Imaging', 'Medication', 'Assessment', 'Encounter'
    event_category VARCHAR,  -- 'Tumor', 'Surgery', 'Chemotherapy', 'Radiation', 'Imaging', 'Lab', 'Toxicity'
    event_subtype VARCHAR,  -- 'Initial Diagnosis', 'Progression', 'Recurrence', 'Post-op imaging', etc.

    -- Event description
    description TEXT NOT NULL,
    source_domain VARCHAR NOT NULL,  -- 'Condition', 'Procedure', 'DiagnosticReport', 'MedicationRequest', etc.
    source_id VARCHAR,  -- FHIR resource ID

    -- Clinical codes
    icd10_codes VARCHAR[],
    snomed_codes VARCHAR[],
    cpt_codes VARCHAR[],
    loinc_codes VARCHAR[],

    -- Status
    clinical_status VARCHAR,  -- 'Active', 'Resolved', 'Completed'

    -- Contextual fields (pre-computed for agent queries)
    days_since_diagnosis INTEGER,
    days_since_surgery INTEGER,
    days_since_treatment_start INTEGER,
    disease_phase VARCHAR,  -- 'Pre-diagnosis', 'Diagnostic', 'Post-surgical', 'On-treatment', 'Surveillance', 'Progression'
    treatment_status VARCHAR,  -- 'Treatment-naive', 'On-chemo', 'On-radiation', 'On-targeted', 'Off-treatment'

    -- Nested metadata (JSON)
    metadata JSON,  -- Domain-specific fields (imaging findings, medication dose, procedure details, etc.)

    -- Provenance
    extracted_from_source VARCHAR,  -- 'athena_structured', 'athena_free_text', 's3_binary'
    extraction_timestamp TIMESTAMP,

    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- Critical indexes for temporal queries
CREATE INDEX idx_events_patient_date ON events(patient_id, event_date);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_category ON events(event_category);
CREATE INDEX idx_events_days_since_diagnosis ON events(patient_id, days_since_diagnosis);
CREATE INDEX idx_events_disease_phase ON events(disease_phase);
```

#### Table 3: `milestones` (Key Disease Events)
```sql
CREATE TABLE milestones (
    milestone_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,

    milestone_type VARCHAR NOT NULL,  -- 'initial_diagnosis', 'surgery', 'progression', 'treatment_start', 'treatment_end', 'death'
    milestone_date DATE NOT NULL,
    age_at_milestone_days INTEGER NOT NULL,

    -- Links to events table
    event_id VARCHAR,  -- References events.event_id

    -- Milestone-specific metadata
    diagnosis_details JSON,  -- {histology, grade, location, molecular_features}
    surgery_details JSON,    -- {procedure_type, extent_of_resection, complications}
    treatment_details JSON,  -- {regimen, agents, intent}
    progression_details JSON,  -- {progression_type, site, imaging_date}

    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);

CREATE INDEX idx_milestones_patient ON milestones(patient_id);
CREATE INDEX idx_milestones_type ON milestones(milestone_type);
```

#### Table 4: `event_windows` (Pre-Computed Contextual Windows)
```sql
CREATE TABLE event_windows (
    window_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,

    -- Anchor event
    anchor_event_id VARCHAR NOT NULL,
    anchor_event_date TIMESTAMP NOT NULL,
    anchor_event_type VARCHAR NOT NULL,

    -- Window definition
    window_start_date TIMESTAMP NOT NULL,
    window_end_date TIMESTAMP NOT NULL,
    window_days_before INTEGER,
    window_days_after INTEGER,

    -- Events within window
    related_event_ids VARCHAR[],  -- Array of event_ids within window
    event_count INTEGER,

    -- Contextual summary (for LLM)
    context_summary TEXT,  -- "90-day window around surgery (2018-06-06): 5 imaging studies, 2 diagnoses, 12 medications"

    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (anchor_event_id) REFERENCES events(event_id)
);

CREATE INDEX idx_windows_anchor ON event_windows(anchor_event_id);
CREATE INDEX idx_windows_patient_date ON event_windows(patient_id, anchor_event_date);
```

#### Table 5: `extracted_variables` (MedGemma Extractions)
```sql
CREATE TABLE extracted_variables (
    extraction_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,

    -- Source document
    source_event_id VARCHAR,  -- Links to events table
    source_document_type VARCHAR,  -- 'imaging_report', 'pathology_report', 'operative_note', etc.
    source_document_date DATE,
    source_text TEXT,  -- Full document text or relevant excerpt

    -- Extracted variable
    variable_name VARCHAR NOT NULL,  -- 'tumor_location', 'extent_of_resection', 'braf_fusion', etc.
    variable_value VARCHAR,
    variable_confidence DECIMAL(3,2),  -- 0.00 to 1.00

    -- Temporal context (at time of extraction)
    event_date TIMESTAMP,
    days_since_diagnosis INTEGER,
    disease_phase VARCHAR,
    treatment_status VARCHAR,

    -- Extraction metadata
    extraction_method VARCHAR,  -- 'medgemma', 'claude', 'structured_field', 'manual_review'
    extraction_timestamp TIMESTAMP,
    model_version VARCHAR,
    prompt_version VARCHAR,

    -- Validation
    validated BOOLEAN DEFAULT FALSE,
    validation_status VARCHAR,  -- 'pending', 'confirmed', 'conflict', 'requires_review'
    validation_notes TEXT,

    -- Conflict resolution (if multiple sources)
    conflicts_with_extraction_ids VARCHAR[],  -- Array of extraction_ids with different values
    conflict_resolution_rule VARCHAR,  -- 'prefer_athena_free_text', 'prefer_binary', 'manual_review'

    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (source_event_id) REFERENCES events(event_id)
);

CREATE INDEX idx_extractions_patient_variable ON extracted_variables(patient_id, variable_name);
CREATE INDEX idx_extractions_source_event ON extracted_variables(source_event_id);
CREATE INDEX idx_extractions_validation_status ON extracted_variables(validation_status);
```

---

## 4. Temporal Query Patterns

### 4.1 Basic Temporal Queries

**Query 1: Events within date window**
```sql
-- Find all events within 30 days before a surgery
SELECT
    e.event_id,
    e.event_date,
    e.event_type,
    e.description,
    (s.event_date - e.event_date) as days_before_surgery
FROM events e
CROSS JOIN (
    SELECT event_date
    FROM events
    WHERE event_id = 'surgery_event_id_here'
) s
WHERE e.patient_id = 'patient_id_here'
    AND e.event_date BETWEEN (s.event_date - INTERVAL '30 days') AND s.event_date
    AND e.event_id != 'surgery_event_id_here'
ORDER BY e.event_date DESC;
```

**Query 2: Find treatment regimen at specific date**
```sql
-- What was patient on at 2018-08-03?
SELECT
    m.medication_name,
    m.medication_start_date,
    m.medication_end_date,
    CASE
        WHEN m.medication_end_date IS NULL THEN 'Active'
        ELSE 'Completed'
    END as status
FROM events e
WHERE e.patient_id = 'patient_id_here'
    AND e.event_type = 'Medication'
    AND e.event_date <= '2018-08-03'
    AND (e.metadata->>'medication_end_date' IS NULL
         OR e.metadata->>'medication_end_date'::date >= '2018-08-03')
ORDER BY e.event_date;
```

**Query 3: Procedures between two milestones**
```sql
-- Surgeries between diagnosis and chemotherapy start
SELECT
    e.event_date,
    e.description,
    e.metadata->>'procedure_type' as procedure_type,
    e.days_since_diagnosis
FROM events e
JOIN milestones m_diag ON e.patient_id = m_diag.patient_id
    AND m_diag.milestone_type = 'initial_diagnosis'
JOIN milestones m_tx ON e.patient_id = m_tx.patient_id
    AND m_tx.milestone_type = 'treatment_start'
WHERE e.patient_id = 'patient_id_here'
    AND e.event_type = 'Procedure'
    AND e.event_category = 'Surgery'
    AND e.event_date BETWEEN m_diag.milestone_date AND m_tx.milestone_date
ORDER BY e.event_date;
```

### 4.2 Contextual Enrichment Queries

**Query 4: Generate LLM context for a document**
```sql
-- Create temporal context for an imaging report on 2018-08-03
WITH target_event AS (
    SELECT patient_id, event_date, event_id
    FROM events
    WHERE event_id = 'imaging_event_id_here'
),
patient_info AS (
    SELECT
        p.patient_id,
        p.birth_date,
        p.first_diagnosis_date,
        p.first_surgery_date,
        p.first_treatment_date
    FROM patients p
    JOIN target_event te ON p.patient_id = te.patient_id
),
recent_milestones AS (
    SELECT
        m.milestone_type,
        m.milestone_date,
        (te.event_date - m.milestone_date) as days_since_milestone
    FROM milestones m
    JOIN target_event te ON m.patient_id = te.patient_id
    WHERE m.milestone_date <= te.event_date
    ORDER BY m.milestone_date DESC
    LIMIT 5
),
surrounding_events AS (
    SELECT
        e.event_type,
        e.event_date,
        e.description,
        (te.event_date - e.event_date) as days_before_target
    FROM events e
    JOIN target_event te ON e.patient_id = te.patient_id
    WHERE e.event_date BETWEEN (te.event_date - INTERVAL '60 days')
                           AND (te.event_date + INTERVAL '30 days')
        AND e.event_id != te.event_id
    ORDER BY e.event_date
)
SELECT
    'TEMPORAL CONTEXT' as section,
    json_build_object(
        'patient_age_at_event', (te.event_date - pi.birth_date) / 365.25,
        'days_since_diagnosis', (te.event_date - pi.first_diagnosis_date),
        'days_since_surgery', (te.event_date - pi.first_surgery_date),
        'disease_phase', CASE
            WHEN (te.event_date - pi.first_surgery_date) < 90 THEN 'Post-surgical surveillance'
            WHEN pi.first_treatment_date IS NULL THEN 'Pre-treatment'
            WHEN te.event_date >= pi.first_treatment_date THEN 'On-treatment'
        END,
        'recent_milestones', (SELECT json_agg(recent_milestones) FROM recent_milestones),
        'surrounding_events', (SELECT json_agg(surrounding_events) FROM surrounding_events)
    ) as context
FROM target_event te
JOIN patient_info pi ON te.patient_id = pi.patient_id;
```

**Query 5: Identify event sequence patterns**
```sql
-- Find "Diagnosis → Surgery → Imaging" sequences
SELECT
    e1.patient_id,
    e1.event_date as diagnosis_date,
    e2.event_date as surgery_date,
    e3.event_date as imaging_date,
    (e2.event_date - e1.event_date) as days_diagnosis_to_surgery,
    (e3.event_date - e2.event_date) as days_surgery_to_imaging
FROM events e1
JOIN events e2 ON e1.patient_id = e2.patient_id
    AND e2.event_type = 'Procedure'
    AND e2.event_category = 'Surgery'
    AND e2.event_date > e1.event_date
    AND e2.event_date <= e1.event_date + INTERVAL '60 days'
JOIN events e3 ON e2.patient_id = e3.patient_id
    AND e3.event_type = 'Imaging'
    AND e3.event_date > e2.event_date
    AND e3.event_date <= e2.event_date + INTERVAL '7 days'
WHERE e1.event_category = 'Tumor'
    AND e1.event_subtype = 'Initial Diagnosis'
ORDER BY e1.patient_id, e1.event_date;
```

---

## 5. Agent-to-Timeline Query Interface

### 5.1 Python Query Functions for Agents

```python
# File: timeline_query_interface.py

import duckdb
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class TimelineQueryInterface:
    """
    Query interface for agents to retrieve temporal context from patient timelines.
    """

    def __init__(self, db_path: str = "data/timelines/timeline.duckdb"):
        self.conn = duckdb.connect(db_path, read_only=True)

    def get_event_context_window(
        self,
        patient_id: str,
        event_id: str,
        days_before: int = 30,
        days_after: int = 30,
        format: str = "llm_text"  # 'llm_text', 'json', 'dataframe'
    ) -> str | Dict | pd.DataFrame:
        """
        Retrieve temporal context window around a specific event.

        Args:
            patient_id: Patient identifier
            event_id: Target event identifier
            days_before: Days before event to include
            days_after: Days after event to include
            format: Return format for agent consumption

        Returns:
            Formatted context (text for LLM, JSON for structured processing, or DataFrame)
        """

        query = f"""
        WITH target_event AS (
            SELECT
                event_id,
                event_date,
                event_type,
                description,
                disease_phase,
                treatment_status,
                days_since_diagnosis,
                days_since_surgery
            FROM events
            WHERE event_id = '{event_id}' AND patient_id = '{patient_id}'
        ),
        window_events AS (
            SELECT
                e.event_date,
                e.event_type,
                e.event_category,
                e.description,
                e.clinical_status,
                (te.event_date::DATE - e.event_date::DATE) as days_relative_to_target,
                e.metadata
            FROM events e
            CROSS JOIN target_event te
            WHERE e.patient_id = '{patient_id}'
                AND e.event_date BETWEEN (te.event_date - INTERVAL '{days_before} days')
                                     AND (te.event_date + INTERVAL '{days_after} days')
                AND e.event_id != '{event_id}'
            ORDER BY e.event_date
        ),
        patient_milestones AS (
            SELECT
                m.milestone_type,
                m.milestone_date,
                (te.event_date::DATE - m.milestone_date::DATE) as days_since_milestone
            FROM milestones m
            CROSS JOIN target_event te
            WHERE m.patient_id = '{patient_id}'
                AND m.milestone_date <= te.event_date::DATE
            ORDER BY m.milestone_date DESC
        )
        SELECT
            te.*,
            (SELECT json_agg(window_events ORDER BY event_date) FROM window_events) as window_events,
            (SELECT json_agg(patient_milestones ORDER BY milestone_date DESC) FROM patient_milestones) as milestones
        FROM target_event te;
        """

        result = self.conn.execute(query).fetchone()

        if format == "llm_text":
            return self._format_context_for_llm(result)
        elif format == "json":
            return self._format_context_as_json(result)
        else:
            return self.conn.execute(query).df()

    def _format_context_for_llm(self, result) -> str:
        """
        Format query result as natural language text for LLM consumption.
        """

        event_id, event_date, event_type, description, disease_phase, treatment_status, \
            days_since_diagnosis, days_since_surgery, window_events_json, milestones_json = result

        window_events = json.loads(window_events_json) if window_events_json else []
        milestones = json.loads(milestones_json) if milestones_json else []

        context_text = f"""
=== TEMPORAL CONTEXT FOR EVENT ===

TARGET EVENT:
- Date: {event_date}
- Type: {event_type}
- Description: {description}
- Disease Phase: {disease_phase}
- Treatment Status: {treatment_status}
- Days Since Diagnosis: {days_since_diagnosis}
- Days Since Surgery: {days_since_surgery}

RECENT MILESTONES:
"""
        for milestone in milestones[:5]:  # Top 5 most recent
            context_text += f"- {milestone['milestone_type']}: {milestone['milestone_date']} ({milestone['days_since_milestone']} days before this event)\n"

        context_text += f"""
EVENTS IN SURROUNDING WINDOW:

BEFORE TARGET EVENT:
"""
        before_events = [e for e in window_events if e['days_relative_to_target'] < 0]
        for event in sorted(before_events, key=lambda x: x['event_date'], reverse=True)[:10]:
            context_text += f"- [{event['days_relative_to_target']} days] {event['event_type']}: {event['description']}\n"

        context_text += f"""
AFTER TARGET EVENT:
"""
        after_events = [e for e in window_events if e['days_relative_to_target'] > 0]
        for event in sorted(after_events, key=lambda x: x['event_date'])[:10]:
            context_text += f"- [+{event['days_relative_to_target']} days] {event['event_type']}: {event['description']}\n"

        return context_text

    def _format_context_as_json(self, result) -> Dict:
        """Format as structured JSON for programmatic access."""

        event_id, event_date, event_type, description, disease_phase, treatment_status, \
            days_since_diagnosis, days_since_surgery, window_events_json, milestones_json = result

        return {
            "target_event": {
                "event_id": event_id,
                "event_date": str(event_date),
                "event_type": event_type,
                "description": description,
                "disease_phase": disease_phase,
                "treatment_status": treatment_status,
                "days_since_diagnosis": days_since_diagnosis,
                "days_since_surgery": days_since_surgery
            },
            "milestones": json.loads(milestones_json) if milestones_json else [],
            "window_events": json.loads(window_events_json) if window_events_json else []
        }

    def get_treatment_regimen_at_date(
        self,
        patient_id: str,
        query_date: datetime,
        format: str = "llm_text"
    ) -> str | Dict:
        """
        What treatments was the patient receiving at a specific date?
        """

        query = f"""
        SELECT
            e.description,
            e.metadata->>'medication_name' as medication_name,
            e.event_date as start_date,
            e.metadata->>'medication_end_date' as end_date,
            e.metadata->>'medication_form' as form,
            e.metadata->>'medication_status' as status
        FROM events e
        WHERE e.patient_id = '{patient_id}'
            AND e.event_type = 'Medication'
            AND e.event_category IN ('Chemotherapy', 'Targeted Therapy', 'Radiation')
            AND e.event_date::DATE <= '{query_date}'::DATE
            AND (e.metadata->>'medication_end_date' IS NULL
                 OR e.metadata->>'medication_end_date'::DATE >= '{query_date}'::DATE)
        ORDER BY e.event_date;
        """

        results = self.conn.execute(query).fetchall()

        if format == "llm_text":
            text = f"TREATMENT REGIMEN AT {query_date}:\n\n"
            for desc, med_name, start, end, form, status in results:
                text += f"- {med_name or desc} ({form})\n"
                text += f"  Started: {start}\n"
                text += f"  Status: {status}\n\n"
            return text
        else:
            return [
                {
                    "medication": med_name or desc,
                    "start_date": str(start),
                    "end_date": str(end) if end else None,
                    "form": form,
                    "status": status
                }
                for desc, med_name, start, end, form, status in results
            ]

    def get_progression_context(
        self,
        patient_id: str,
        progression_event_id: str
    ) -> str:
        """
        Generate comprehensive context for a progression/recurrence event.
        Includes: prior treatments, imaging timeline, previous surgeries.
        """

        query = f"""
        WITH progression_event AS (
            SELECT event_date, days_since_diagnosis, days_since_surgery
            FROM events
            WHERE event_id = '{progression_event_id}' AND patient_id = '{patient_id}'
        ),
        prior_treatments AS (
            SELECT
                e.event_category,
                e.description,
                e.event_date,
                (pe.event_date::DATE - e.event_date::DATE) as days_before_progression
            FROM events e
            CROSS JOIN progression_event pe
            WHERE e.patient_id = '{patient_id}'
                AND e.event_type = 'Medication'
                AND e.event_category IN ('Chemotherapy', 'Radiation', 'Targeted Therapy')
                AND e.event_date < pe.event_date
            ORDER BY e.event_date DESC
            LIMIT 5
        ),
        prior_surgeries AS (
            SELECT
                e.description,
                e.event_date,
                (pe.event_date::DATE - e.event_date::DATE) as days_before_progression,
                e.metadata->>'procedure_type' as procedure_type
            FROM events e
            CROSS JOIN progression_event pe
            WHERE e.patient_id = '{patient_id}'
                AND e.event_type = 'Procedure'
                AND e.event_category = 'Surgery'
                AND e.event_date < pe.event_date
            ORDER BY e.event_date DESC
        ),
        prior_imaging AS (
            SELECT
                e.event_date,
                (pe.event_date::DATE - e.event_date::DATE) as days_before_progression,
                e.metadata->>'imaging_modality' as modality,
                e.metadata->>'report_conclusion' as conclusion
            FROM events e
            CROSS JOIN progression_event pe
            WHERE e.patient_id = '{patient_id}'
                AND e.event_type = 'Imaging'
                AND e.event_date < pe.event_date
            ORDER BY e.event_date DESC
            LIMIT 10
        )
        SELECT
            pe.*,
            (SELECT json_agg(prior_treatments) FROM prior_treatments) as treatments,
            (SELECT json_agg(prior_surgeries) FROM prior_surgeries) as surgeries,
            (SELECT json_agg(prior_imaging) FROM prior_imaging) as imaging
        FROM progression_event pe;
        """

        result = self.conn.execute(query).fetchone()

        prog_date, days_since_diag, days_since_surg, treatments_json, surgeries_json, imaging_json = result

        treatments = json.loads(treatments_json) if treatments_json else []
        surgeries = json.loads(surgeries_json) if surgeries_json else []
        imaging = json.loads(imaging_json) if imaging_json else []

        context = f"""
=== PROGRESSION EVENT CONTEXT ===

PROGRESSION DETECTED: {prog_date}
- {days_since_diag} days ({days_since_diag/365.25:.1f} years) since initial diagnosis
- {days_since_surg} days ({days_since_surg/365.25:.1f} years) since initial surgery

PRIOR TREATMENTS:
"""
        for tx in treatments:
            context += f"- {tx['description']} ({tx['event_category']}): {tx['event_date']} ({tx['days_before_progression']} days before progression)\n"

        context += f"""
PRIOR SURGERIES:
"""
        for surg in surgeries:
            context += f"- {surg['description']}: {surg['event_date']} ({surg['days_before_progression']} days before progression)\n"

        context += f"""
IMAGING TIMELINE LEADING TO PROGRESSION:
"""
        for img in imaging:
            context += f"- [{img['days_before_progression']} days before] {img['modality']}: {img['conclusion'][:200] if img['conclusion'] else 'N/A'}...\n"

        return context

    def validate_extracted_value_temporal_consistency(
        self,
        patient_id: str,
        variable_name: str,
        extracted_value: str,
        source_event_id: str
    ) -> Dict:
        """
        Validate whether an extracted value is temporally consistent.

        Example: If extracting "progression", check if this is reasonable given
        timing relative to diagnosis, prior treatments, etc.
        """

        # Get event context
        context = self.get_event_context_window(patient_id, source_event_id,
                                                 days_before=180, days_after=90,
                                                 format="json")

        # Apply validation rules based on variable
        validation_result = {
            "variable": variable_name,
            "extracted_value": extracted_value,
            "source_event_id": source_event_id,
            "validation_status": "pending",
            "validation_notes": []
        }

        if variable_name == "tumor_status":
            # Check if "progression" makes sense
            if extracted_value.lower() in ["progression", "recurrence"]:
                days_since_diagnosis = context['target_event']['days_since_diagnosis']
                if days_since_diagnosis < 30:
                    validation_result['validation_status'] = "warning"
                    validation_result['validation_notes'].append(
                        f"Progression detected only {days_since_diagnosis} days after diagnosis - may be residual disease, not true progression"
                    )
                else:
                    validation_result['validation_status'] = "plausible"

        elif variable_name == "extent_of_resection":
            # Check if this is from post-op imaging
            days_since_surgery = context['target_event']['days_since_surgery']
            if days_since_surgery and days_since_surgery < 7:
                validation_result['validation_status'] = "confirmed"
                validation_result['validation_notes'].append(
                    f"Extracted from imaging {days_since_surgery} days post-surgery - consistent with post-operative assessment"
                )
            elif days_since_surgery and days_since_surgery > 180:
                validation_result['validation_status'] = "warning"
                validation_result['validation_notes'].append(
                    f"Imaging is {days_since_surgery} days post-surgery - this may reflect tumor regrowth, not initial resection extent"
                )

        return validation_result
```

### 5.2 Agent 2 (MedGemma) Integration

**Workflow**: Agent 1 queries timeline → Formats context → Passes to Agent 2 with document

```python
# Agent 1 orchestration example
from timeline_query_interface import TimelineQueryInterface

tq = TimelineQueryInterface()

# Step 1: Identify imaging report to extract from
imaging_event_id = "erNFnh2TkBgIXlRW7wzruHAUPWUNW-RW9M7omUgUyBQE3"
patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

# Step 2: Get temporal context
context = tq.get_event_context_window(
    patient_id=patient_id,
    event_id=imaging_event_id,
    days_before=60,
    days_after=30,
    format="llm_text"
)

# Step 3: Retrieve document text (from Athena or S3)
document_text = get_imaging_report_text(imaging_event_id)

# Step 4: Construct prompt for MedGemma
medgemma_prompt = f"""
{context}

=== DOCUMENT TO EXTRACT FROM ===
{document_text}

=== EXTRACTION TASK ===
Extract the following variables from this imaging report:
1. tumor_location
2. tumor_measurements
3. tumor_status (stable, progression, recurrence, resolved)
4. metastasis (yes/no)

Consider the temporal context provided above when determining tumor_status.
For example, if this is 58 days post-surgery and residual enhancement is seen,
this is likely "residual disease" not "progression" or "recurrence".

Return as JSON:
{{
  "tumor_location": "...",
  "tumor_measurements": "...",
  "tumor_status": "...",
  "metastasis": "..."
}}
"""

# Step 5: Call MedGemma
medgemma_response = call_medgemma(medgemma_prompt)

# Step 6: Validate extraction using temporal consistency
validation = tq.validate_extracted_value_temporal_consistency(
    patient_id=patient_id,
    variable_name="tumor_status",
    extracted_value=medgemma_response['tumor_status'],
    source_event_id=imaging_event_id
)

if validation['validation_status'] == "warning":
    # Flag for manual review or re-extraction with updated prompt
    print(f"Warning: {validation['validation_notes']}")
```

---

## 6. Storage Implementation Strategy

### 6.1 Phase 1: Parquet Generation (Per-Patient Files)

```python
# File: build_patient_timeline_parquet.py

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime

def build_patient_timeline_parquet(patient_id: str, athena_csv_dir: str, output_dir: str):
    """
    Extract timeline from Athena CSVs and write to Parquet.
    """

    # Load source CSVs
    demographics = pd.read_csv(f"{athena_csv_dir}/patient_demographics.csv")
    encounters = pd.read_csv(f"{athena_csv_dir}/encounters.csv")
    diagnoses = pd.read_csv(f"{athena_csv_dir}/diagnoses.csv")
    procedures = pd.read_csv(f"{athena_csv_dir}/procedures.csv")
    imaging = pd.read_csv(f"{athena_csv_dir}/imaging.csv")
    medications = pd.read_csv(f"{athena_csv_dir}/medications.csv")
    molecular_tests = pd.read_csv(f"{athena_csv_dir}/molecular_tests_metadata.csv")

    # Construct events dataframe
    events = []

    # Add diagnosis events
    for _, diag in diagnoses.iterrows():
        events.append({
            'event_id': f"diag_{diag['condition_id']}",
            'patient_id': patient_id,
            'event_date': pd.to_datetime(diag['onset_date_time']),
            'age_at_event_days': diag['age_at_onset_days'],
            'event_type': 'Diagnosis',
            'event_category': 'Tumor' if 'neoplasm' in diag['diagnosis_name'].lower() else 'Complication',
            'description': diag['diagnosis_name'],
            'source_domain': 'Condition',
            'source_id': diag['condition_id'],
            'icd10_codes': [diag['icd10_code']] if pd.notna(diag['icd10_code']) else [],
            'snomed_codes': [str(diag['snomed_code'])] if pd.notna(diag['snomed_code']) else [],
            'clinical_status': diag['clinical_status_text'],
            'metadata': {
                'icd10_display': diag['icd10_display'],
                'snomed_display': diag['snomed_display'],
                'recorded_date': diag['recorded_date']
            }
        })

    # Add imaging events (similar pattern)
    # Add procedure events (similar pattern)
    # Add medication events (similar pattern)

    events_df = pd.DataFrame(events)

    # Compute derived fields
    birth_date = pd.to_datetime(demographics.iloc[0]['pd_birth_date'])
    first_diagnosis_date = events_df[events_df['event_category'] == 'Tumor']['event_date'].min()

    events_df['days_since_diagnosis'] = (events_df['event_date'] - first_diagnosis_date).dt.days

    # Write to Parquet
    table = pa.Table.from_pandas(events_df)
    pq.write_table(table, f"{output_dir}/patient_{patient_id}_timeline.parquet")

    print(f"Wrote {len(events_df)} events to Parquet for patient {patient_id}")
```

### 6.2 Phase 2: DuckDB Import and Indexing

```python
# File: import_timelines_to_duckdb.py

import duckdb
import glob

def import_parquet_to_duckdb(parquet_dir: str, db_path: str):
    """
    Import all patient timeline Parquet files into DuckDB.
    """

    conn = duckdb.connect(db_path)

    # Create schema
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR NOT NULL,
        event_date TIMESTAMP NOT NULL,
        age_at_event_days INTEGER NOT NULL,
        age_at_event_years DECIMAL(5,2),
        event_type VARCHAR NOT NULL,
        event_category VARCHAR,
        event_subtype VARCHAR,
        description TEXT NOT NULL,
        source_domain VARCHAR NOT NULL,
        source_id VARCHAR,
        icd10_codes VARCHAR[],
        snomed_codes VARCHAR[],
        cpt_codes VARCHAR[],
        clinical_status VARCHAR,
        days_since_diagnosis INTEGER,
        days_since_surgery INTEGER,
        disease_phase VARCHAR,
        treatment_status VARCHAR,
        metadata JSON,
        extracted_from_source VARCHAR,
        extraction_timestamp TIMESTAMP
    );
    """)

    # Import Parquet files
    parquet_files = glob.glob(f"{parquet_dir}/patient_*_timeline.parquet")

    for parquet_file in parquet_files:
        conn.execute(f"""
        INSERT INTO events
        SELECT * FROM read_parquet('{parquet_file}');
        """)
        print(f"Imported {parquet_file}")

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_patient_date ON events(patient_id, event_date);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(event_category);")

    print(f"DuckDB timeline database ready at {db_path}")
    conn.close()
```

### 6.3 Phase 3: Pre-Compute Event Windows

```python
# File: precompute_event_windows.py

import duckdb

def precompute_event_windows(db_path: str):
    """
    Pre-compute common temporal windows to speed up agent queries.
    """

    conn = duckdb.connect(db_path)

    # Create event_windows table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS event_windows (
        window_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR NOT NULL,
        anchor_event_id VARCHAR NOT NULL,
        anchor_event_date TIMESTAMP NOT NULL,
        anchor_event_type VARCHAR NOT NULL,
        window_start_date TIMESTAMP NOT NULL,
        window_end_date TIMESTAMP NOT NULL,
        window_days_before INTEGER,
        window_days_after INTEGER,
        related_event_ids VARCHAR[],
        event_count INTEGER,
        context_summary TEXT
    );
    """)

    # Pre-compute 30-day windows around all surgeries
    conn.execute("""
    INSERT INTO event_windows
    SELECT
        'window_' || e.event_id as window_id,
        e.patient_id,
        e.event_id as anchor_event_id,
        e.event_date as anchor_event_date,
        e.event_type as anchor_event_type,
        e.event_date - INTERVAL '30 days' as window_start_date,
        e.event_date + INTERVAL '30 days' as window_end_date,
        30 as window_days_before,
        30 as window_days_after,
        ARRAY_AGG(e2.event_id) as related_event_ids,
        COUNT(e2.event_id) as event_count,
        '30-day window around ' || e.description as context_summary
    FROM events e
    LEFT JOIN events e2
        ON e.patient_id = e2.patient_id
        AND e2.event_date BETWEEN (e.event_date - INTERVAL '30 days')
                              AND (e.event_date + INTERVAL '30 days')
        AND e2.event_id != e.event_id
    WHERE e.event_category = 'Surgery'
    GROUP BY e.event_id, e.patient_id, e.event_date, e.event_type, e.description;
    """)

    print("Pre-computed event windows")
    conn.close()
```

---

## 7. Example: Complete Workflow for Patient e4BwD8ZYDBccepXcJ.Ilo3w3

```python
# Step 1: Build timeline from Athena CSVs
build_patient_timeline_parquet(
    patient_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
    athena_csv_dir="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3",
    output_dir="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/timelines/parquet"
)

# Step 2: Import into DuckDB
import_parquet_to_duckdb(
    parquet_dir="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/timelines/parquet",
    db_path="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/timelines/timeline.duckdb"
)

# Step 3: Pre-compute event windows
precompute_event_windows(
    db_path="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/timelines/timeline.duckdb"
)

# Step 4: Query for extraction context
tq = TimelineQueryInterface(db_path="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/timelines/timeline.duckdb")

# Example query: Get context for post-op MRI on 2018-08-03
context = tq.get_event_context_window(
    patient_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
    event_id="imaging_2018_08_03",  # Would be actual event_id
    days_before=60,
    days_after=30,
    format="llm_text"
)

print(context)
# Output:
# === TEMPORAL CONTEXT FOR EVENT ===
#
# TARGET EVENT:
# - Date: 2018-08-03 20:45:00
# - Type: Imaging
# - Description: MR Brain W & W/O IV Contrast
# - Disease Phase: Post-surgical surveillance
# - Treatment Status: Treatment-naive
# - Days Since Diagnosis: 60
# - Days Since Surgery: 58
#
# RECENT MILESTONES:
# - surgery: 2018-06-06 (58 days before this event)
# - initial_diagnosis: 2018-06-04 (60 days before this event)
#
# EVENTS IN SURROUNDING WINDOW:
#
# BEFORE TARGET EVENT:
# - [-5 days] Diagnosis: Dysarthria
# - [-6 days] Diagnosis: Acquired aphasia
# - [-9 days] Diagnosis: Abnormality of gait
# - [-11 days] Diagnosis: Ataxia
# - [-30 days] Imaging: CT Brain without contrast
# - [-39 days] Diagnosis: Persistent vomiting
# - [-42 days] Imaging: CT Brain without contrast
# - [-46 days] Imaging: CT Brain without contrast
# - [-51 days] Diagnosis: History of malnutrition
# - [-55 days] Diagnosis: Dysphagia
#
# AFTER TARGET EVENT:
# - [+4 days] Imaging: MR Entire Spine W & W/O IV Contrast
# - [+57 days] Diagnosis: Nystagmus
```

---

## 8. Recommended Implementation Timeline

**Week 1**: Build Parquet generation from Athena CSVs for 1 patient
**Week 2**: Implement DuckDB import and basic query functions
**Week 3**: Create TimelineQueryInterface with LLM formatting
**Week 4**: Integrate with MedGemma extraction workflow
**Week 5**: Pre-compute event windows and optimize queries
**Week 6**: Scale to full cohort (100+ patients)

---

**Document Status**: Design Complete ✅
**Next Step**: Implement Parquet generation script
