# Multi-Agent Clinical Extraction Framework

**Version:** 1.0
**Date:** 2025-10-19
**Status:** Ready for Testing

## Overview

This framework implements a two-agent architecture for extracting clinical information from free-text radiology reports and clinical notes:

- **Master Agent** (Claude Sonnet 4.5) - Orchestration, planning, temporal reasoning
- **Medical Agent** (MedGemma 27B) - Medical text extraction, clinical interpretation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MasterAgent                             │
│  (Claude Sonnet 4.5 - Orchestration & Planning)            │
│                                                              │
│  Responsibilities:                                           │
│  - Query timeline for events needing extraction             │
│  - Build temporal context (procedures ±30 days)             │
│  - Construct specialized prompts                            │
│  - Delegate to MedGemma for extraction                      │
│  - Store results with provenance                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ delegates extraction
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    MedGemmaAgent                             │
│  (MedGemma 27B via Ollama - Medical Extraction)            │
│                                                              │
│  Responsibilities:                                           │
│  - Parse clinical text (radiology reports, notes)           │
│  - Extract structured medical variables                     │
│  - Provide confidence scores                                │
│  - Return JSON-formatted results                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ queries/stores
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│               TimelineQueryInterface                         │
│  (DuckDB - Timeline & Documents Storage)                   │
│                                                              │
│  Tables:                                                     │
│  - events: 1,820 temporal events                            │
│  - source_documents: 51 radiology reports                   │
│  - extracted_variables: Agent extractions                   │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. MedGemmaAgent ([medgemma_agent.py](medgemma_agent.py))

Wraps calls to MedGemma 27B model running locally via Ollama.

**Key Methods:**
```python
agent = MedGemmaAgent(
    model_name="medgemma:27b",
    ollama_url="http://localhost:11434",
    temperature=0.1
)

result = agent.extract(
    prompt="Extract extent of resection from this report...",
    expected_schema={"required": ["extent_of_resection", "confidence"]}
)
```

**Returns:**
```python
ExtractionResult(
    success=True,
    extracted_data={"extent_of_resection": "GTR", "confidence": 0.95},
    confidence=0.95,
    raw_response="...",
    prompt_tokens=156,
    completion_tokens=42
)
```

### 2. MasterAgent ([master_agent.py](master_agent.py))

Orchestrates multi-step extraction workflows.

**Key Methods:**
```python
master = MasterAgent(
    timeline_db_path="data/timeline.duckdb",
    dry_run=False
)

# Run imaging extraction for patient
summary = master.orchestrate_imaging_extraction(
    patient_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
    extraction_type="all"  # or specific type
)
```

**Extraction Types:**
- `imaging_classification` - Classify as pre-op/post-op/surveillance
- `extent_of_resection` - Extract GTR/STR/Partial/Biopsy from post-op imaging
- `tumor_status` - Extract NED/Stable/Increased/Decreased from surveillance
- `all` - Run all three extractions

### 3. Extraction Prompts ([extraction_prompts.py](extraction_prompts.py))

Structured prompt templates for each extraction type.

**Imaging Classification:**
- Classifies imaging relative to surgical timeline
- Uses temporal proximity (days from surgery)
- Validates with report keywords
- Output: `pre_operative` | `post_operative` | `surveillance`

**Extent of Resection:**
- Only runs on post-operative imaging (≤14 days after surgery)
- Extracts from radiologist's assessment
- Looks for keywords: "gross total", "subtotal", "partial", "biopsy"
- Output: `GTR` | `STR` | `Partial` | `Biopsy` | `Unknown`

**Tumor Status:**
- Requires comparison to prior imaging
- Extracts radiologist's comparison statements
- Parses measurements if available
- Output: `NED` | `Stable` | `Increased` | `Decreased` | `New_Malignancy`

## Usage

### Prerequisites

1. **Ollama running with MedGemma:**
```bash
# Start Ollama
ollama serve

# Pull MedGemma (if not already)
ollama pull medgemma:27b
```

2. **Timeline database built:**
```bash
python3 scripts/build_timeline_database.py
```

3. **Source documents loaded:**
```bash
python3 scripts/load_radiology_reports.py
```

### Running Extraction

**Basic usage:**
```bash
# Extract all types for test patient
python3 scripts/run_imaging_extraction.py

# Dry run (don't save to database)
python3 scripts/run_imaging_extraction.py --dry-run

# Extract specific type
python3 scripts/run_imaging_extraction.py --extraction-type imaging_classification

# Different patient
python3 scripts/run_imaging_extraction.py --patient-id Patient/xyz
```

**Programmatic usage:**
```python
from agents import MasterAgent, MedGemmaAgent

# Initialize agents
medgemma = MedGemmaAgent()
master = MasterAgent(
    timeline_db_path="data/timeline.duckdb",
    medgemma_agent=medgemma,
    dry_run=False
)

# Run extraction
summary = master.orchestrate_imaging_extraction(
    patient_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
    extraction_type="all"
)

# Check results
print(f"Processed: {summary['imaging_events_processed']}")
print(f"Successful: {summary['successful_extractions']}")
print(f"Failed: {summary['failed_extractions']}")

for result in summary['results']:
    print(f"{result['event_id']}: {result['value']} (confidence: {result['confidence']})")
```

## Data Flow

### 1. Query Timeline
```python
# Master agent queries for imaging events needing extraction
events = timeline.get_imaging_events_needing_extraction(patient_id)
# Returns: DataFrame with 82 imaging events for test patient
```

### 2. Retrieve Documents
```python
# Get radiology report for specific event
report = timeline.get_radiology_report(event_id)
# Returns: {
#   'document_id': 'rad_report_xyz',
#   'document_text': '...',
#   'document_date': '2023-06-15',
#   'metadata': {...}
# }
```

### 3. Build Temporal Context
```python
# Get events ±30 days around imaging
context = timeline.get_event_context_window(
    event_id=event_id,
    days_before=30,
    days_after=30
)
# Returns: {
#   'target_event': {...},
#   'events_before': [...],  # Procedures, meds, etc.
#   'events_after': [...]
# }
```

### 4. Extract with MedGemma
```python
# Build specialized prompt
prompt = build_eor_extraction_prompt(report, context)

# Call MedGemma
result = medgemma.extract(prompt, expected_schema={...})
```

### 5. Store Results
```python
# Store with full provenance
variable_id = timeline.store_extracted_variable(
    patient_id=patient_id,
    source_event_id=event_id,
    variable_name="extent_of_resection",
    variable_value="GTR",
    variable_confidence=0.95,
    extraction_method="medgemma_27b",
    extraction_prompt=prompt[:500],
    extraction_response=result.raw_response[:1000],
    extracted_values_json=json.dumps(result.extracted_data)
)
```

## Output Schema

### Imaging Classification
```json
{
  "imaging_classification": "post_operative",
  "confidence": 0.92,
  "reasoning": "Imaging is 2 days after craniotomy for tumor resection. Report describes post-surgical changes.",
  "keywords_found": ["post-operative", "status post resection", "surgical cavity"]
}
```

### Extent of Resection
```json
{
  "extent_of_resection": "GTR",
  "confidence": 0.95,
  "evidence": "Report states: 'no residual enhancing tumor identified'",
  "residual_tumor_description": "None",
  "measurement_if_available": null
}
```

### Tumor Status
```json
{
  "tumor_status": "Stable",
  "confidence": 0.88,
  "comparison_findings": "Compared to prior study, no significant change in size or enhancement pattern",
  "measurements": {
    "current_size": "2.1 x 1.8 cm",
    "prior_size": "2.0 x 1.7 cm",
    "change_description": "minimal change, within measurement error"
  },
  "enhancement_pattern": "Stable peripheral enhancement",
  "evidence": "Direct quote: 'stable post-treatment appearance'"
}
```

## Provenance Tracking

Every extraction is stored in `extracted_variables` table with:

| Field | Description |
|-------|-------------|
| `variable_id` | Unique extraction ID |
| `patient_id` | Patient FHIR ID |
| `source_event_id` | Event that was analyzed |
| `variable_name` | What was extracted (e.g., "extent_of_resection") |
| `variable_value` | Extracted value (e.g., "GTR") |
| `variable_confidence` | 0.0-1.0 confidence score |
| `extraction_method` | "medgemma_27b" |
| `extraction_prompt` | Prompt sent to model |
| `extraction_response` | Raw model response |
| `extracted_values_json` | Full JSON with all extracted fields |
| `extracted_timestamp` | When extraction occurred |

This enables:
- Auditing extraction logic
- Reprocessing with improved prompts
- Cross-validation between sources
- Human review of low-confidence extractions

## Error Handling

The framework handles:

1. **Ollama Connection Errors**
   - Checks Ollama availability on initialization
   - Provides clear instructions to start server

2. **Model Response Errors**
   - Retries up to 3 times on JSON parsing failures
   - Returns structured error in `ExtractionResult`

3. **Missing Data**
   - Skips events without radiology reports
   - Logs warnings for missing context

4. **Schema Validation**
   - Validates extracted JSON against expected schema
   - Raises errors for missing required fields

## Performance

**Test Patient (e4BwD8ZYDBccepXcJ.Ilo3w3):**
- 82 imaging events
- 51 with radiology reports
- ~30-60 seconds per extraction (MedGemma 27B on local hardware)
- Total: ~45 minutes for complete extraction (3 types × 51 reports)

**Optimization Options:**
- Run extraction types in parallel (if hardware supports multiple Ollama instances)
- Cache prior imaging comparisons to reduce prompt size
- Batch similar reports together

## Testing

**Dry run mode:**
```bash
python3 scripts/run_imaging_extraction.py --dry-run
```

This runs full extraction workflow but doesn't save to database - useful for:
- Testing prompts
- Validating model responses
- Debugging extraction logic

## Next Steps

1. **Test on sample reports** - Run dry-run extraction on test patient
2. **Review extraction quality** - Check confidence scores and errors
3. **Tune prompts** - Refine based on initial results
4. **Add progress notes extraction** - Extend to v_progress_notes
5. **Cross-validation** - Compare imaging extractions with clinical notes
6. **Human review workflow** - Flag low-confidence extractions for review

## Files

```
agents/
├── __init__.py                    # Package exports
├── medgemma_agent.py              # MedGemma 27B wrapper
├── master_agent.py                # Orchestration logic
├── extraction_prompts.py          # Prompt templates
└── README.md                      # This file

scripts/
└── run_imaging_extraction.py      # CLI extraction pipeline

tests/
└── test_extraction.py             # Unit tests (TODO)
```

## Dependencies

```
duckdb
requests
pandas
```

**External:**
- Ollama (with medgemma:27b model)
- Timeline database (DuckDB)
- Source documents loaded

## Troubleshooting

**"Cannot connect to Ollama":**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve

# Pull MedGemma if needed
ollama pull medgemma:27b
```

**"Timeline database not found":**
```bash
# Build timeline database first
python3 scripts/build_timeline_database.py
```

**"No radiology reports found":**
```bash
# Load source documents
python3 scripts/load_radiology_reports.py
```

## References

- [MULTI_AGENT_TUMOR_STATUS_WORKFLOW.md](../../athena_views/views/MULTI_AGENT_TUMOR_STATUS_WORKFLOW.md) - Clinical workflow specification
- [TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md](../TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md) - Timeline database design
- [timeline_query_interface.py](../timeline_query_interface.py) - Timeline query API
