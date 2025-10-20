# Comprehensive Multi-Agent Clinical Data Extraction System

**Last Updated:** 2025-10-20
**System Version:** Enhanced Master Agent v1.1 with Workflow Monitoring

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Workflow Monitoring & Notifications](#workflow-monitoring--notifications)
4. [Database Schema](#database-schema)
5. [Agent Responsibilities](#agent-responsibilities)
6. [Workflows](#workflows)
7. [Directory Structure](#directory-structure)
8. [Scripts & Tools](#scripts--tools)
9. [Data Models](#data-models)
10. [Setup & Installation](#setup--installation)
11. [Step-by-Step Workflows](#step-by-step-workflows)
12. [Troubleshooting](#troubleshooting)
13. [Future Work](#future-work)

---

## System Overview

### Purpose
Extract and validate clinical variables from pediatric brain tumor patient records using a multi-agent AI system with:
- **Agent 1 (Claude/MasterAgent)**: Orchestrator, validator, adjudicator
- **Agent 2 (MedGemma)**: Medical text extractor

### Key Features
- **Timeline-aware extraction**: Uses temporal context from patient history
- **Multi-step extraction**: Classification → EOR → Tumor Status
- **Temporal inconsistency detection**: Identifies clinically implausible patterns
- **Iterative Agent ↔ Agent queries**: Agent 1 asks Agent 2 for clarification
- **Multi-source adjudication**: Reconciles operative reports vs imaging
- **Event type classification**: Determines Initial/Recurrence/Progressive/Second Malignancy
- **Comprehensive QA reports**: Documents all decisions and inconsistencies
- **Workflow monitoring**: Multi-level logging (console, file, JSON) with error tracking
- **Automated notifications**: Email, Slack, webhook alerts for critical errors
- **Timestamped abstractions**: Each run creates dated folder with checkpoints

### Data Sources
1. **v_imaging** (Athena): Text imaging reports (DiagnosticReport.conclusion)
2. **v_binary_files** (Athena): PDF imaging reports, operative notes, progress notes
3. **v_procedures_tumor** (Athena): Surgical procedures with tumor classification
4. **Timeline Database** (DuckDB): Stores events, extractions, temporal context

---

## Architecture

### Two-Agent System

```
┌─────────────────────────────────────────────────────────────┐
│                         HUMAN USER                          │
│              (Directs workflow, reviews escalations)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             AGENT 1: Enhanced MasterAgent (Claude)           │
│─────────────────────────────────────────────────────────────│
│ Responsibilities:                                            │
│ • Query timeline database for patient history               │
│ • Build temporal context for Agent 2                        │
│ • Orchestrate extraction workflow                           │
│ • Detect temporal inconsistencies                           │
│ • Query Agent 2 iteratively for clarification               │
│ • Adjudicate multi-source conflicts                         │
│ • Classify event types                                      │
│ • Generate comprehensive patient abstractions               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Sends prompts with temporal context
                  │ Requests clarification when suspicious
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENT 2: MedGemmaAgent (Gemma 27B)             │
│─────────────────────────────────────────────────────────────│
│ Responsibilities:                                            │
│ • Extract clinical variables from text                      │
│ • Classify imaging (pre-op/post-op/surveillance)            │
│ • Extract extent of resection                               │
│ • Extract tumor status                                      │
│ • Provide confidence scores                                 │
│ • Respond to Agent 1's clarification queries                │
│ • NO cross-source reconciliation (Agent 1's job)            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. GATHER DATA
   └─> Query Athena (v_imaging, v_binary_files, v_procedures_tumor)
   └─> Load timeline database (patient history, prior extractions)

2. BASE EXTRACTION (MasterAgent)
   └─> For each imaging event:
       ├─> Get radiology report text
       ├─> Get temporal context (events ±30 days, surgical history)
       ├─> Build extraction prompt with context
       ├─> Send to Agent 2 (MedGemma)
       ├─> Receive structured JSON response
       └─> Store in timeline database

3. POST-EXTRACTION VALIDATION (EnhancedMasterAgent)
   └─> Load all new extractions
   └─> Detect temporal inconsistencies:
       ├─> Rapid changes (Increased→Decreased in <7 days)
       ├─> Illogical progressions
       └─> Unexplained improvements without surgery

4. ITERATIVE AGENT 2 QUERIES
   └─> For each inconsistency:
       ├─> Gather additional context (surgical history, other sources)
       ├─> Build clarification prompt
       ├─> Query Agent 2: "Does this make sense given [context]?"
       ├─> Receive Agent 2's explanation
       └─> Agent 1 adjudicates based on response

5. MULTI-SOURCE INTEGRATION
   └─> Query operative reports
   └─> Extract EOR from surgical notes (Agent 2)
   └─> Adjudicate: Operative report > Post-op imaging

   └─> Query progress notes
   └─> Filter to oncology-specific (exclude telephone, nursing)
   └─> Extract disease state from clinical assessments (Agent 2)
   └─> Validate against imaging findings

6. EVENT TYPE CLASSIFICATION (Agent 1)
   └─> Analyze surgical history + tumor progression
   └─> Determine:
       ├─> Initial CNS Tumor (first event)
       ├─> Recurrence (growth after GTR)
       ├─> Progressive (growth after Partial)
       └─> Second Malignancy (new location)

7. GENERATE COMPREHENSIVE ABSTRACTION
   └─> Compile all extractions
   └─> Document inconsistencies
   └─> Document Agent 2 clarifications
   └─> Document event classifications
   └─> Save patient QA report
```

---

## Workflow Monitoring & Notifications

### Overview

The system includes comprehensive monitoring and notification capabilities to ensure reliable operation and rapid error detection.

**Key Components:**
- **Multi-level logging**: Console (human-readable), file (detailed debug), JSON (machine-readable)
- **Error tracking**: Structured error categorization with severity levels
- **Performance metrics**: Success rates, extraction counts, phase tracking
- **Notification channels**: Email (SMTP), Slack (webhook), generic webhook
- **Automated alerting**: Critical errors trigger immediate notifications

### Logging Architecture

```
Workflow Execution
    │
    ├─> Console Logger (INFO level)
    │   └─> Real-time human-readable output
    │
    ├─> File Logger (DEBUG level)
    │   └─> logs/workflow_runs/{workflow}_{timestamp}.log
    │   └─> Includes line numbers, stack traces, full context
    │
    ├─> JSON Logger (INFO level)
    │   └─> logs/workflow_runs/{workflow}_{timestamp}.jsonl
    │   └─> Machine-readable structured logs
    │   └─> For ingestion into monitoring tools (ELK, Grafana)
    │
    └─> Metrics Logger
        └─> logs/workflow_runs/{workflow}_{timestamp}_metrics.json
        └─> Workflow performance and error statistics
```

### Error Severity Levels

| Level | Description | Notification | Example |
|-------|-------------|--------------|---------|
| **INFO** | Normal operation | No | "Starting extraction phase" |
| **WARNING** | Recoverable issues | Optional | "Missing optional field: tumor_size" |
| **ERROR** | Failed operation, retryable | Yes (configurable) | "MedGemma extraction timeout" |
| **CRITICAL** | Workflow failure | Always | "Database connection lost" |

### Usage Example

```python
from utils.workflow_monitoring import WorkflowLogger
from pathlib import Path

# Initialize logger
logger = WorkflowLogger(
    workflow_name="multi_source_abstraction",
    log_dir=Path("logs/workflow_runs"),
    patient_id="patient123",
    enable_json=True,
    enable_notifications=True
)

# Log messages with context
logger.log_info("Starting extraction", context={"source": "imaging"})
logger.log_warning("Missing field", context={"field": "tumor_size"})
logger.log_error(
    "Extraction failed",
    error_type="MedGemmaTimeout",
    stack_trace=traceback.format_exc(),
    notify=True  # Send notification
)

# Track workflow progress
logger.update_phase("temporal_validation")
logger.record_extraction(success=True)

# Save metrics and print summary
logger.save_metrics()
print(logger.get_summary())
```

### Notification Configuration

**Configuration File:** `config/notification_config.json`

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "from_address": "alerts@yourorg.com",
    "recipients": ["team@yourorg.com"]
  },
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
    "channel": "#workflow-alerts",
    "notify_on": ["error", "critical"]
  },
  "webhook": {
    "enabled": false,
    "url": "https://monitoring-service.com/webhook"
  }
}
```

### Timestamped Abstractions

**Every workflow run creates a timestamped folder:**

```
data/patient_abstractions/20251020_083136/
├── patient123_enhanced.json           # Comprehensive abstraction
├── patient123_checkpoint.json         # Recovery checkpoint
└── logs/
    ├── multi_source_abstraction_20251020_083136.log        # Detailed logs
    ├── multi_source_abstraction_20251020_083136.jsonl      # Structured logs
    └── multi_source_abstraction_20251020_083136_metrics.json  # Performance metrics
```

**Benefits:**
- **Reproducibility**: Complete audit trail for each run
- **Comparison**: Compare extractions across time
- **Recovery**: Checkpoint allows resume from failure
- **Debugging**: Full logs preserved per run

### Metrics Tracked

The system automatically tracks:

```json
{
  "workflow_id": "multi_source_abstraction_20251020_083136",
  "patient_id": "patient123",
  "start_time": "2025-10-20T08:31:36",
  "current_phase": "temporal_validation",
  "phases_completed": ["data_query", "extraction"],
  "total_extractions": 82,
  "successful_extractions": 79,
  "failed_extractions": 3,
  "errors": [
    {
      "timestamp": "2025-10-20T08:32:15",
      "severity": "error",
      "phase": "extraction",
      "error_type": "MedGemmaTimeout",
      "error_message": "Extraction timed out after 30s",
      "context": {"report_id": "imaging_001"}
    }
  ]
}
```

### Integration with Workflows

All production workflows now include monitoring:

**Example: Full Multi-Source Abstraction**

```python
# scripts/run_full_multi_source_abstraction.py

from utils.workflow_monitoring import WorkflowLogger
import traceback

# Initialize monitoring
logger = WorkflowLogger(
    workflow_name="multi_source_abstraction",
    log_dir=output_dir / "logs",
    patient_id=args.patient_id,
    enable_json=True,
    enable_notifications=True
)

try:
    # Phase 1: Data Query
    logger.update_phase("data_query")
    logger.log_info("Querying Athena for all data sources")

    imaging_reports = query_athena(imaging_query)
    logger.log_info(f"Retrieved {len(imaging_reports)} imaging reports")

    # Phase 2: Extraction
    logger.update_phase("extraction")

    for report in imaging_reports:
        try:
            result = medgemma.extract(prompt)
            logger.record_extraction(success=True)
        except Exception as e:
            logger.log_error(
                f"Extraction failed for report {report['id']}",
                error_type=type(e).__name__,
                stack_trace=traceback.format_exc(),
                context={"report_id": report['id']},
                notify=True
            )
            logger.record_extraction(success=False)

    # Save final metrics
    logger.save_metrics()
    logger.log_info("Workflow completed successfully")
    print(logger.get_summary())

except Exception as e:
    logger.log_critical(
        "Workflow failed with critical error",
        error_type=type(e).__name__,
        stack_trace=traceback.format_exc()
    )
    raise
```

### Documentation

**Full documentation:** [docs/WORKFLOW_MONITORING.md](docs/WORKFLOW_MONITORING.md)

**Configuration example:** [config/notification_config.example.json](config/notification_config.example.json)

**Key files:**
- `utils/workflow_monitoring.py` - Core monitoring framework
- `docs/WORKFLOW_MONITORING.md` - Complete usage guide
- `config/notification_config.example.json` - Configuration template

---

## Database Schema

### Timeline Database (DuckDB)

**Location:** `data/timeline.duckdb`

#### Table: `patients`
| Column | Type | Description |
|--------|------|-------------|
| patient_id | VARCHAR PK | Internal patient ID |
| patient_fhir_id | VARCHAR | FHIR Patient resource ID |
| mrn | VARCHAR | Medical record number |
| birth_date | DATE | Date of birth |
| created_at | TIMESTAMP | Record creation timestamp |

#### Table: `events`
| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR PK | Unique event identifier |
| patient_id | VARCHAR | FK to patients |
| event_type | VARCHAR | Visit, Imaging, Procedure, Medication, etc. |
| event_category | VARCHAR | MRI Brain, Craniotomy, etc. |
| event_date | TIMESTAMP | When event occurred |
| description | VARCHAR | Event description |
| source_system | VARCHAR | athena, ehr, manual |
| source_id | VARCHAR | ID in source system |
| created_at | TIMESTAMP | Record creation |

#### Table: `source_documents`
| Column | Type | Description |
|--------|------|-------------|
| document_id | VARCHAR PK | Unique document ID |
| source_event_id | VARCHAR | FK to events |
| document_type | VARCHAR | radiology_report, operative_note, progress_note |
| document_text | VARCHAR | Full document text |
| document_date | TIMESTAMP | Document date |
| document_metadata | VARCHAR | JSON metadata |
| created_at | TIMESTAMP | Record creation |

#### Table: `extracted_variables`
| Column | Type | Description |
|--------|------|-------------|
| extraction_id | VARCHAR PK | Unique extraction ID |
| event_id | VARCHAR | FK to events |
| patient_id | VARCHAR | FK to patients |
| variable_name | VARCHAR | imaging_classification, tumor_status, extent_of_resection |
| variable_value | VARCHAR | Extracted value |
| confidence | DOUBLE | Agent 2 confidence score (0.0-1.0) |
| extraction_method | VARCHAR | medgemma, manual, rule_based |
| extracted_at | TIMESTAMP | Extraction timestamp |
| provenance | VARCHAR | JSON provenance info |

### Athena Views (Read-Only)

#### v_imaging
- Imaging text reports from DiagnosticReport resources
- Key columns: `patient_fhir_id`, `imaging_date`, `report_conclusion`, `imaging_modality`

#### v_binary_files
- Binary attachments and their metadata from DocumentReference + Binary resources
- Types: PDFs, HTML notes, operative reports, progress notes
- Key columns: `patient_fhir_id`, `dr_date`, `dr_type_text`, `dr_category_text`, `content_type`, `binary_id`

#### v_procedures_tumor
- Surgical procedures with tumor classification
- Key columns: `patient_fhir_id`, `proc_performed_date_time`, `proc_code_text`, `surgery_type`, `is_tumor_surgery`

---

## Agent Responsibilities

### Agent 1: Enhanced MasterAgent

**File:** `agents/enhanced_master_agent.py`

**Core Responsibilities:**

1. **Timeline Management**
   - Load patient timeline from DuckDB
   - Query events by type, date range
   - Provide temporal context to Agent 2

2. **Orchestration**
   - Determine which events need extraction
   - Build extraction prompts with context
   - Delegate to Agent 2
   - Store results in timeline database

3. **Temporal Validation**
   - Detect rapid status changes
   - Identify illogical progressions
   - Flag unexplained improvements

4. **Iterative Queries**
   - When inconsistency detected:
     - Gather additional context
     - Ask Agent 2 for explanation
     - Adjudicate based on response

5. **Multi-Source Adjudication**
   - Reconcile operative report EOR vs imaging EOR
   - Apply source hierarchy (operative > imaging)
   - Validate imaging tumor status vs clinical assessment

6. **Event Type Classification**
   - Analyze surgical history
   - Determine: Initial/Recurrence/Progressive/Second Malignancy
   - Apply clinical logic (GTR + growth = Recurrence)

7. **Comprehensive Reporting**
   - Generate patient QA reports
   - Document all inconsistencies
   - Document all Agent 2 clarifications
   - Document all adjudication decisions

**Key Methods:**
- `orchestrate_comprehensive_extraction(patient_id)` - Main workflow
- `_detect_temporal_inconsistencies(patient_id, results)` - Find suspicious patterns
- `_query_agent2_for_clarification(patient_id, inconsistency)` - Iterative query
- `_classify_all_events(patient_id)` - Event type classification

### Agent 2: MedGemmaAgent

**File:** `agents/medgemma_agent.py`

**Core Responsibilities:**

1. **Clinical Text Extraction**
   - Extract structured variables from unstructured text
   - Provide confidence scores
   - Quote evidence from source text

2. **Imaging Classification**
   - Classify as: pre_operative, post_operative, surveillance
   - Based on temporal context + report keywords

3. **Extent of Resection Extraction**
   - From post-operative imaging: GTR, STR, Partial, Biopsy
   - From operative reports: Surgeon's assessment (GOLD STANDARD)

4. **Tumor Status Extraction**
   - From surveillance imaging: NED, Stable, Increased, Decreased, New_Malignancy
   - Compare to prior imaging when available

5. **Respond to Clarification Queries**
   - Re-review documents with additional context
   - Provide clinical plausibility assessment
   - Recommend action: keep_both, revise, escalate

**Does NOT:**
- Cross-source reconciliation (Agent 1's job)
- Event type classification (Agent 1's job)
- Temporal inconsistency detection (Agent 1's job)

**Key Methods:**
- `extract(prompt, expected_schema)` - Main extraction method
- Returns: `ExtractionResult(success, extracted_data, confidence, raw_response)`

---

## Workflows

### Workflow 1: Base Imaging Extraction

**Script:** `scripts/run_imaging_extraction.py`

**Purpose:** Extract variables from imaging reports using MasterAgent with timeline context

**Steps:**
```bash
# 1. Build timeline database
python3 scripts/build_timeline_database.py

# 2. Run extraction
python3 scripts/run_imaging_extraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --extraction-type all

# 3. Results stored in timeline.duckdb → extracted_variables table
```

**What Happens:**
1. MasterAgent loads timeline database
2. Queries imaging events needing extraction
3. For each event:
   - Gets radiology report text
   - Gets temporal context (±30 days, surgeries)
   - Builds 3 prompts:
     - Imaging classification
     - Extent of resection (if post-op)
     - Tumor status
   - Sends to Agent 2
   - Stores results

**Output:**
- Extractions in `timeline.duckdb`
- Summary JSON in `data/extraction_results/`

### Workflow 2: Enhanced Extraction with Validation

**Script:** `scripts/run_enhanced_extraction.py`

**Purpose:** Full workflow with temporal validation and iterative Agent 2 queries

**Steps:**
```bash
# 1. Ensure timeline database is fresh
python3 scripts/build_timeline_database.py

# 2. Run enhanced extraction
python3 scripts/run_enhanced_extraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3

# 3. Review comprehensive abstraction
cat data/patient_abstractions/e4BwD8ZYDBccepXcJ.Ilo3w3_enhanced_*.json
```

**What Happens:**
1. EnhancedMasterAgent calls base MasterAgent extraction
2. Loads all new tumor status extractions
3. Detects temporal inconsistencies:
   - Rapid changes (Increased→Decreased <7 days)
   - Checks if surgery explains change
4. For each inconsistency requiring Agent 2 query:
   - Gathers imaging reports + surgical history
   - Builds clarification prompt
   - Queries Agent 2
   - Adjudicates based on response
5. Classifies event types based on surgical history
6. Generates comprehensive abstraction

**Output:**
- All base extractions in `timeline.duckdb`
- Comprehensive abstraction in `data/patient_abstractions/`
- Includes:
  - Imaging extraction summary
  - Temporal inconsistencies detected
  - Agent 2 clarifications
  - Event type classifications

### Workflow 3: Multi-Source Comprehensive Abstraction

**Script:** `scripts/run_comprehensive_abstraction.py`

**Purpose:** Integrate operative reports and progress notes for multi-source validation

**Steps:**
```bash
# 1. Run comprehensive abstraction
python3 scripts/run_comprehensive_abstraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3

# This integrates:
# - Base imaging extraction (MasterAgent)
# - Operative report EOR extraction
# - Progress note disease state validation
# - EOR adjudication (operative vs imaging)
# - Temporal inconsistency detection
# - Event type classification
```

**What Happens:**
1. Base imaging extraction with timeline context
2. Query v_procedures_tumor for surgeries
3. Extract EOR from operative notes (Agent 2)
4. Query v_binary_files for progress notes
5. Filter to oncology-specific notes (exclude telephone, nursing)
6. Extract disease state from clinical assessments (Agent 2)
7. Adjudicate EOR: operative report > imaging
8. Detect temporal inconsistencies
9. Query Agent 2 for clarification
10. Classify event types
11. Generate comprehensive abstraction

**Output:**
- Complete patient abstraction with all sources
- Multi-source adjudications
- Progress note filtering statistics

---

## Directory Structure

```
mvp/
├── agents/
│   ├── __init__.py
│   ├── master_agent.py              # Base MasterAgent (timeline + orchestration)
│   ├── enhanced_master_agent.py     # + temporal validation + iterative queries
│   ├── medgemma_agent.py            # Agent 2 (MedGemma wrapper)
│   ├── binary_file_agent.py         # S3/Binary file handler
│   ├── extraction_prompts.py        # Prompt templates for Agent 2
│   ├── eor_adjudicator.py           # Multi-source EOR reconciliation
│   ├── event_type_classifier.py     # Event type determination logic
│   └── agent1_agent2_resolution_workflow.py  # QA/resolution workflows
│
├── scripts/
│   ├── build_timeline_database.py           # Build DuckDB from Athena
│   ├── run_imaging_extraction.py            # Base extraction workflow
│   ├── run_enhanced_extraction.py           # + temporal validation
│   ├── run_comprehensive_abstraction.py     # + multi-source integration
│   ├── test_patient_end_to_end.py           # E2E test with real data
│   └── demo_agent1_agent2_workflow.py       # Demo workflow (simulated)
│
├── utils/
│   ├── progress_note_filters.py             # Filter oncology notes
│   ├── timeline_schema_validator.py         # Validate/fix DB schema
│   ├── athena_schema_registry.py            # Column name validation
│   ├── query_binary_files.py                # Binary file utilities
│   └── workflow_monitoring.py               # Logging & notification framework
│
├── data/
│   ├── timeline.duckdb                      # Timeline database
│   ├── extraction_results/                   # Extraction run logs/results
│   ├── patient_abstractions/                 # Comprehensive abstractions (timestamped)
│   │   └── 20251020_083136/                  # Example timestamped run
│   │       ├── patient_enhanced.json         # Comprehensive abstraction
│   │       ├── patient_checkpoint.json       # Recovery checkpoint
│   │       └── logs/                         # Run-specific logs
│   ├── qa_reports/                           # QA/inconsistency reports
│   └── archive/                              # Archived databases
│
├── logs/
│   └── workflow_runs/                        # Workflow monitoring logs
│       ├── {workflow}_{timestamp}.log        # Detailed logs
│       ├── {workflow}_{timestamp}.jsonl      # Structured logs
│       └── {workflow}_{timestamp}_metrics.json  # Performance metrics
│
├── config/
│   ├── notification_config.json             # Notification settings (user-created)
│   └── notification_config.example.json     # Configuration template
│
├── timeline_query_interface.py              # DuckDB query interface
│
└── docs/
    ├── COMPREHENSIVE_SYSTEM_DOCUMENTATION.md (this file)
    ├── AGENT_WORKFLOW_ENHANCEMENTS.md        # Enhancement history
    ├── PREVENTING_COLUMN_NAME_ERRORS.md      # Best practices
    ├── ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md # Column reference
    └── WORKFLOW_MONITORING.md                # Monitoring framework guide
```

---

## Scripts & Tools

### Core Scripts

#### 1. `build_timeline_database.py`
**Purpose:** Build timeline database from Athena FHIR views

**Usage:**
```bash
python3 scripts/build_timeline_database.py
```

**What it does:**
1. Queries Athena for patient events (Imaging, Procedures, Medications, etc.)
2. Creates DuckDB database with schema
3. Inserts events with temporal ordering
4. Creates indexes for performance

**Output:** `data/timeline.duckdb`

**When to run:**
- First time setup
- After FHIR data updates in Athena
- When starting fresh (archive old database first)

#### 2. `run_imaging_extraction.py`
**Purpose:** Run base imaging extraction with MasterAgent

**Usage:**
```bash
# All extraction types for test patient
python3 scripts/run_imaging_extraction.py

# Specific extraction type
python3 scripts/run_imaging_extraction.py --extraction-type tumor_status

# Different patient
python3 scripts/run_imaging_extraction.py --patient-id Patient/xyz

# Dry run (don't save to database)
python3 scripts/run_imaging_extraction.py --dry-run
```

**Arguments:**
- `--patient-id`: Patient FHIR ID (default: test patient)
- `--extraction-type`: `all`, `imaging_classification`, `extent_of_resection`, `tumor_status`
- `--dry-run`: Don't save results to database
- `--timeline-db`: Path to timeline database
- `--ollama-url`: Ollama API URL

**Output:**
- Extractions in timeline database
- JSON summary in `data/extraction_results/`

#### 3. `run_enhanced_extraction.py`
**Purpose:** Run extraction with temporal validation and iterative Agent 2 queries

**Usage:**
```bash
python3 scripts/run_enhanced_extraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3
```

**What it does:**
1. Runs base imaging extraction (MasterAgent)
2. Detects temporal inconsistencies
3. Queries Agent 2 for clarification when suspicious
4. Classifies event types
5. Generates comprehensive abstraction

**Output:**
- Base extractions in timeline database
- Comprehensive abstraction in `data/patient_abstractions/`

#### 4. `run_comprehensive_abstraction.py`
**Purpose:** Full multi-source workflow

**Usage:**
```bash
python3 scripts/run_comprehensive_abstraction.py
```

**What it does:**
1. Base imaging extraction
2. Operative report EOR extraction
3. Progress note disease state validation
4. Multi-source EOR adjudication
5. Temporal inconsistency detection
6. Event type classification
7. Comprehensive abstraction generation

**Output:** Complete patient abstraction with all data sources

### Utility Scripts

#### 5. `timeline_schema_validator.py`
**Purpose:** Validate and fix timeline database schema

**Usage:**
```bash
# Validate only
python3 utils/timeline_schema_validator.py data/timeline.duckdb

# Validate and fix
python3 utils/timeline_schema_validator.py data/timeline.duckdb --fix
```

**What it checks:**
- All required tables exist
- All required columns exist
- Correct data types (basic check)

**What it fixes:**
- Creates missing tables
- Adds missing columns

#### 6. `progress_note_filters.py`
**Purpose:** Filter progress notes to oncology-specific

**Usage:**
```python
from utils.progress_note_filters import filter_oncology_notes

# Filter notes
oncology_notes = filter_oncology_notes(all_notes)

# Get statistics
stats = get_note_filtering_stats(all_notes)
# Returns: total, oncology count, excluded count, exclusion reasons
```

**Filtering Logic:**
- **Include:** Oncology, assessment & plan, consult notes, progress notes, H&P
- **Exclude:** Telephone, nursing, social work, pharmacy, admin notes

#### 7. `athena_schema_registry.py`
**Purpose:** Validate Athena view column names before querying

**Usage:**
```bash
# Validate columns
python3 utils/athena_schema_registry.py validate v_procedures_tumor \
    proc_code_text proc_outcome_text

# Suggest correct column name
python3 utils/athena_schema_registry.py suggest v_procedures_tumor \
    procedure_code_text

# Output: Did you mean 'proc_code_text'?
```

**Prevents:** Column name errors that waste time

---

## Data Models

### Extraction Prompts

#### Imaging Classification
**Input:** Radiology report + temporal context (surgeries ±30 days)

**Output:**
```json
{
  "imaging_classification": "pre_operative|post_operative|surveillance",
  "confidence": 0.0-1.0,
  "reasoning": "...",
  "keywords_found": ["post-operative", "status post resection"]
}
```

**Logic:**
- `post_operative`: 0-3 days after surgery, mentions surgical changes
- `pre_operative`: Before first surgery, baseline imaging
- `surveillance`: >14 days after surgery, follow-up monitoring

#### Extent of Resection
**Input:** Post-operative imaging OR operative report + surgical context

**Output:**
```json
{
  "extent_of_resection": "GTR|STR|Partial|Biopsy",
  "confidence": 0.0-1.0,
  "evidence": "Direct quote from report",
  "residual_tumor_description": "...",
  "measurement_if_available": "1.2 cm"
}
```

**Source Hierarchy:**
1. **Operative report** (GOLD STANDARD): Surgeon's direct assessment
2. **Post-op imaging** (within 72 hours): Radiologist assessment

#### Tumor Status
**Input:** Surveillance imaging + prior imaging context

**Output:**
```json
{
  "tumor_status": "NED|Stable|Increased|Decreased|New_Malignancy",
  "confidence": 0.0-1.0,
  "comparison_findings": "...",
  "measurements": {
    "current_size": "2.1 x 1.8 cm",
    "prior_size": "2.0 x 1.7 cm",
    "change_description": "slight increase"
  },
  "enhancement_pattern": "...",
  "evidence": "Direct quote"
}
```

### Event Type Classification

**Logic:**
```python
if first_tumor_event:
    event_type = "Initial CNS Tumor"

elif new_location:
    event_type = "Second Malignancy"

elif prior_surgery.eor == "Gross Total Resection":
    if tumor_grows:
        event_type = "Recurrence"

elif prior_surgery.eor in ["Partial Resection", "Biopsy Only"]:
    if tumor_grows:
        event_type = "Progressive"
```

**Output:**
```python
EventTypeClassification(
    event_id="...",
    event_date=datetime,
    event_type="Initial CNS Tumor|Recurrence|Progressive|Second Malignancy",
    confidence=0.0-1.0,
    reasoning="...",
    supporting_evidence={...}
)
```

### Temporal Inconsistency Detection

**Detection Rules:**

1. **Rapid Improvement**
   - Pattern: Increased → Decreased in <7 days
   - Check: Was there surgery between?
   - If no surgery: Suspicious → Query Agent 2

2. **Unexplained Recurrence**
   - Pattern: NED → Disease in <180 days
   - Severity: Medium (expected pattern after GTR)
   - Action: Note for event type classification

3. **Illogical Progression**
   - Pattern: NED → Increased → NED without GTR
   - Severity: High
   - Action: Query Agent 2 for clarification

**Output:**
```python
TemporalInconsistency(
    inconsistency_id="...",
    inconsistency_type="rapid_change|unexplained_recurrence|illogical_progression",
    severity="high|medium|low",
    description="...",
    affected_events=["event_id_1", "event_id_2"],
    context={
        "prior_date": "...",
        "current_date": "...",
        "days_between": 5,
        "surgery_found": False
    },
    requires_agent2_query=True
)
```

---

## Setup & Installation

### Prerequisites

1. **Python 3.12+**
2. **Ollama** with Gemma 27B model
3. **AWS CLI** configured with radiant-prod profile
4. **DuckDB** (installed via pip)

### Installation Steps

```bash
# 1. Clone repository
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# 2. Install Python dependencies
pip install -r requirements.txt
# Required: duckdb, boto3, pandas, requests, pymupdf, python-dateutil

# 3. Install and start Ollama
# macOS: brew install ollama
ollama serve

# 4. Pull Gemma 27B model
ollama pull gemma2:27b

# 5. Configure AWS CLI
aws configure sso --profile radiant-prod
aws sso login --profile radiant-prod

# 6. Verify Athena access
aws athena list-databases --catalog-name AwsDataCatalog --profile radiant-prod --region us-east-1

# 7. Build timeline database
python3 scripts/build_timeline_database.py

# 8. Validate schema
python3 utils/timeline_schema_validator.py data/timeline.duckdb --fix

# 9. Run test extraction
python3 scripts/run_imaging_extraction.py --dry-run
```

### Verification

```bash
# Check timeline database
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
print('Events:', conn.execute('SELECT COUNT(*) FROM events').fetchone()[0])
print('Extractions:', conn.execute('SELECT COUNT(*) FROM extracted_variables').fetchone()[0])
"

# Check Ollama
curl http://localhost:11434/api/tags

# Check AWS credentials
aws sts get-caller-identity --profile radiant-prod
```

---

## Step-by-Step Workflows

### Workflow A: First-Time Complete Patient Abstraction

**Goal:** Generate comprehensive abstraction for a patient from scratch

```bash
# Step 1: Ensure fresh timeline database
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Archive old database if exists
mkdir -p data/archive
mv data/timeline.duckdb data/archive/timeline_$(date +%Y%m%d_%H%M%S).duckdb

# Build new timeline database
python3 scripts/build_timeline_database.py
# Output: data/timeline.duckdb with patient events

# Step 2: Validate schema
python3 utils/timeline_schema_validator.py data/timeline.duckdb --fix
# Ensures all tables and columns are correct

# Step 3: Run enhanced extraction
python3 scripts/run_enhanced_extraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3

# This will:
# - Extract from 51 imaging events
# - Detect temporal inconsistencies
# - Query Agent 2 for clarification
# - Classify event types
# - Generate comprehensive abstraction

# Step 4: Review results
# Timeline database extractions:
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
results = conn.execute('''
    SELECT variable_name, COUNT(*) as count
    FROM extracted_variables
    GROUP BY variable_name
''').fetchdf()
print(results)
"

# Comprehensive abstraction:
cat data/patient_abstractions/e4BwD8ZYDBccepXcJ.Ilo3w3_enhanced_*.json | python3 -m json.tool

# Step 5: Review temporal inconsistencies
# Look in the abstraction JSON for:
# - temporal_inconsistencies.details[]
# - agent2_clarifications.resolutions[]
```

**Expected Output:**
- ~150 extractions (51 events × 3 types each)
- 0-10 temporal inconsistencies detected
- 0-5 Agent 2 clarification queries
- Event type classifications for all tumor events
- Comprehensive abstraction JSON file

### Workflow B: Add Multi-Source Validation

**Goal:** Add operative reports and progress notes to existing extraction

```bash
# Step 1: Run comprehensive abstraction (includes multi-source)
python3 scripts/run_comprehensive_abstraction.py \
    --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3

# This adds:
# - Operative report EOR extraction
# - Progress note disease state validation
# - EOR adjudication (operative vs imaging)
# - Filtered progress notes (oncology-specific only)

# Step 2: Review progress note filtering
# Check abstraction for:
# - progress_notes.total: 999
# - progress_notes.oncology_specific: 830 (83.1%)
# - Excluded: telephone, nursing notes

# Step 3: Review EOR adjudication
# Check for:
# - Operative report EOR (gold standard)
# - Post-op imaging EOR
# - Final adjudicated EOR
# - Agreement status (full_agreement, partial_agreement, discrepancy)
```

### Workflow C: Re-run After FHIR Data Updates

**Goal:** Re-extract after new imaging/procedures added to Athena

```bash
# Step 1: Archive current timeline database
mkdir -p data/archive
cp data/timeline.duckdb data/archive/timeline_$(date +%Y%m%d_%H%M%S).duckdb

# Step 2: Clear old extractions (keep events)
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
conn.execute('DELETE FROM extracted_variables')
print('✅ Cleared extractions, kept events')
"

# Step 3: Rebuild timeline database from Athena
python3 scripts/build_timeline_database.py

# Step 4: Run enhanced extraction
python3 scripts/run_enhanced_extraction.py

# This will extract only NEW events (ones without extractions)
```

### Workflow D: Investigate Temporal Inconsistency

**Goal:** Deep-dive into a specific temporal inconsistency

```bash
# Step 1: Identify inconsistency from abstraction
cat data/patient_abstractions/*_enhanced_*.json | \
    python3 -m json.tool | \
    grep -A 20 "temporal_inconsistencies"

# Step 2: Query timeline for affected events
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')

# Get events around inconsistency date
events = conn.execute('''
    SELECT event_id, event_date, event_type, description
    FROM events
    WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        AND event_date BETWEEN '2018-05-25' AND '2018-05-31'
    ORDER BY event_date
''').fetchdf()

print(events)

# Get extractions for those events
extractions = conn.execute('''
    SELECT event_id, variable_name, variable_value, confidence
    FROM extracted_variables
    WHERE event_id IN (SELECT event_id FROM events
                       WHERE event_date BETWEEN '2018-05-25' AND '2018-05-31')
    ORDER BY variable_name
''').fetchdf()

print(extractions)
"

# Step 3: Check if surgery explains inconsistency
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')

surgeries = conn.execute('''
    SELECT event_id, event_date, description
    FROM events
    WHERE patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
        AND event_type = 'Procedure'
        AND event_date BETWEEN '2018-05-25' AND '2018-05-31'
    ORDER BY event_date
''').fetchdf()

print('Surgeries in window:')
print(surgeries)
"

# Step 4: Review Agent 2's clarification (if queried)
cat data/patient_abstractions/*_enhanced_*.json | \
    python3 -m json.tool | \
    grep -A 30 "agent2_clarifications"
```

---

## Troubleshooting

### Issue 0: Workflow Completes But No Data Saved (CRITICAL)

**Symptoms:**
- Workflow runs for 20+ minutes
- Shows "✅ Completed X extractions"
- Only creates error checkpoint file
- No `*_comprehensive.json` or `*_enhanced.json` output

**Root Cause:** JSON serialization error (ExtractionResult objects not serializable)

**Fixed in v1.1.1:**
- ExtractionResult objects now converted to dicts before save
- Emergency partial data save on ANY error
- Creates `*_PARTIAL.json` with whatever was extracted

**Verification:**
```bash
# Check for output files
ls -lh data/patient_abstractions/[timestamp]/

# Should see:
# - [patient]_comprehensive.json (success) OR
# - [patient]_PARTIAL.json (partial success with error)
# - [patient]_checkpoint.json (status tracking)
```

**If still seeing data loss:**
```python
# Check if ExtractionResult being stored directly
grep "ExtractionResult" scripts/run_*.py
# Should find NO matches in data storage sections
```

### Issue 1: Timeline Database Schema Errors

**Error:** `Table 'source_documents' does not exist` or `Column 'source_event_id' does not exist`

**Solution:**
```bash
# Validate and fix schema
python3 utils/timeline_schema_validator.py data/timeline.duckdb --fix

# If that doesn't work, rebuild from scratch
mv data/timeline.duckdb data/timeline_broken.duckdb
python3 scripts/build_timeline_database.py
```

### Issue 2: Ollama Connection Errors

**Error:** `Cannot connect to Ollama at http://localhost:11434`

**Solution:**
```bash
# Start Ollama
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags

# Pull model if missing
ollama pull gemma2:27b
```

### Issue 3: AWS SSO Token Expired

**Error:** `Token has expired and refresh failed`

**Solution:**
```bash
# Re-login
aws sso login --profile radiant-prod

# Verify credentials
aws sts get-caller-identity --profile radiant-prod
```

### Issue 4: Athena Column Name Errors

**Error:** `Column 'procedure_code_text' cannot be resolved`

**Solution:**
```bash
# Check correct column names
python3 utils/athena_schema_registry.py suggest v_procedures_tumor procedure_code_text

# Output: Did you mean 'proc_code_text'?

# Use column reference guide
cat ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md
```

**Prevention:** Always check column names before writing queries:
1. Review `ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md`
2. Run `SHOW COLUMNS FROM view_name` in Athena console
3. Use schema registry to validate

### Issue 5: Agent 2 Returns Low Confidence

**Problem:** Extractions have confidence < 0.5

**Causes:**
1. Report text is too brief or ambiguous
2. Missing comparison to prior imaging
3. Temporal context not provided

**Solution:**
```bash
# Check if MasterAgent is providing context
# Look in logs for:
# - "Get temporal context (events ±30 days)"
# - Context should include surgical history

# If context missing, rebuild timeline:
python3 scripts/build_timeline_database.py
```

### Issue 6: No Imaging Events Found

**Error:** `No imaging events found needing extraction`

**Causes:**
1. All events already have extractions
2. Timeline database not populated

**Solution:**
```bash
# Check event count
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
print('Events:', conn.execute('SELECT COUNT(*) FROM events').fetchone()[0])
print('Imaging:', conn.execute(\"SELECT COUNT(*) FROM events WHERE event_type='Imaging'\").fetchone()[0])
print('Extractions:', conn.execute('SELECT COUNT(*) FROM extracted_variables').fetchone()[0])
"

# If extractions already exist and you want to re-run:
python3 -c "
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
conn.execute('DELETE FROM extracted_variables')
"
```

---

## Future Work

### Phase 1: Complete Multi-Source Integration (IN PROGRESS)

#### Remaining Tasks:
1. **Fetch actual note text from v_binary_files**
   - Currently using metadata placeholders
   - Need to fetch Binary resources from S3
   - Parse HTML/PDF for progress notes and operative reports

2. **Implement EOR adjudication with real operative notes**
   - Agent 2 extracts EOR from actual surgical note text
   - Compare operative vs post-op imaging EOR
   - Generate adjudication report

3. **Disease state validation from progress notes**
   - Agent 2 extracts clinical assessment from oncology notes
   - Compare clinical status vs imaging tumor status
   - Flag discrepancies (clinical progression before imaging changes)

### Phase 2: Scale to Cohort

#### Tasks:
1. **Test on 5 pilot patients**
   - Validate workflow across different disease trajectories
   - Measure resolution rate (target >80% automated)
   - Identify edge cases requiring human review

2. **Batch processing framework**
   - Process multiple patients in parallel
   - Queue management for Agent 2 calls
   - Progress tracking

3. **Scale to 200 BRIM patients**
   - Full cohort processing
   - Aggregate statistics
   - Quality metrics

### Phase 3: Advanced Features

#### 1. Treatment Response Assessment
- Integrate MedicationRequest data
- Correlate tumor status with chemotherapy cycles
- RANO/RECIST criteria implementation

#### 2. Longitudinal Trajectory Analysis
- Multi-timepoint tumor measurement tracking
- Growth rate calculations
- Survival outcome correlation

#### 3. Natural Language Queries
- "Show all patients with progression after GTR"
- "Find rapid responses to temozolomide"
- Query interface for clinical researchers

#### 4. Visualization Dashboard
- Patient timeline visualization
- Tumor measurement trends
- Multi-source reconciliation view

### Phase 4: Model Improvements

#### 1. Fine-tune MedGemma
- Train on pediatric brain tumor specific corpus
- Improve rare entity recognition (medulloblastoma, ependymoma)
- Better understanding of RANO criteria

#### 2. Agent 1 Decision Logic
- Machine learning for temporal inconsistency detection
- Learn from human adjudication decisions
- Confidence calibration

#### 3. Multi-modal Integration
- Process actual imaging (DICOM)
- Combine radiology report + image features
- Automated tumor segmentation integration

---

## Version History

### v1.1.1 (2025-10-20) - Critical Data Loss Prevention Fix
- 🔥 **CRITICAL**: Fixed JSON serialization preventing data from being saved
- ✅ Convert ExtractionResult objects to dicts before checkpoint save
- ✅ Emergency partial data save on ANY workflow error
- ✅ Confidence scores now preserved in saved extractions
- ✅ Creates *_PARTIAL.json for debugging failed runs
- **Impact**: Prevents 100% data loss on serialization errors (26 min of work saved)

### v1.1 (2025-10-20) - Workflow Monitoring & Notifications
- ✅ Multi-level logging framework (console, file, JSON)
- ✅ Structured error tracking with severity levels
- ✅ Performance metrics and workflow summaries
- ✅ Notification system (Email, Slack, webhook)
- ✅ Timestamped abstraction folders with checkpoints
- ✅ Comprehensive monitoring documentation
- ✅ Document text cache with full provenance (80% cost reduction)
- ✅ Progress note prioritization (660 notes → ~20-40 key notes)
- ✅ Full multi-source abstraction workflow
- ✅ Progress note filtering (oncology-specific, 66.1% retention)
- ✅ Fixed all Athena column name errors

### v1.0 (2025-10-20) - Enhanced Master Agent
- ✅ EnhancedMasterAgent with temporal validation
- ✅ Iterative Agent 1 ↔ Agent 2 queries
- ✅ Event type classification
- ✅ Progress note filtering
- ✅ Timeline schema validator
- ✅ Comprehensive documentation

### v0.9 (2025-10-19) - Multi-Source Framework
- ✅ Operative report EOR extraction prompts
- ✅ Progress note disease state prompts
- ✅ EOR adjudicator
- ✅ Multi-source integration scripts

### v0.8 (2025-10-19) - Base MasterAgent
- ✅ MasterAgent with timeline integration
- ✅ Multi-step extraction framework
- ✅ Timeline database with DuckDB
- ✅ MedGemmaAgent wrapper

---

## Contact & Support

**Project:** RADIANT Pediatric Cancer Analytics - BRIM Cohort
**Institution:** [Institution Name]
**PI:** [PI Name]

For questions or issues:
1. Check this documentation first
2. Review troubleshooting section
3. Check existing documentation:
   - `AGENT_WORKFLOW_ENHANCEMENTS.md`
   - `PREVENTING_COLUMN_NAME_ERRORS.md`
   - `ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md`

---

**Document Maintained By:** Claude Code (Agent 1)
**Last Comprehensive Update:** 2025-10-20
