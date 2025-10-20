# Agent 1 (Claude) Onboarding Guide

**Purpose:** Provide comprehensive context for new Claude sessions working on the Multi-Agent Clinical Data Extraction System

**Last Updated:** 2025-10-20
**System Version:** v1.2.0
**Repository:** https://github.com/adamcresnick/BRIM_Analytics

---

## Quick Start for New Sessions

### Essential Context Documents (Read These First)

1. **[COMPREHENSIVE_SYSTEM_DOCUMENTATION.md](COMPREHENSIVE_SYSTEM_DOCUMENTATION.md)** - Complete system architecture, workflows, components
2. **[ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md](ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md)** - Authoritative column names for queries
3. **[utils/Athena_Schema.csv](utils/Athena_Schema.csv)** - Complete Athena schema (ALWAYS check before writing queries)
4. **[SESSION_SUMMARY_20251020.md](SESSION_SUMMARY_20251020.md)** - Development history and key decisions

### Critical Rules

⚠️ **NEVER GUESS ATHENA COLUMN NAMES** - Always check [utils/Athena_Schema.csv](utils/Athena_Schema.csv) first
⚠️ **ALWAYS FINISH JOBS** - Complete all implementation before moving to next task
⚠️ **TEST BEFORE COMMITTING** - Run code to verify it works
⚠️ **COMPLETE INTEGRATION** - Don't leave placeholder implementations

---

## System Overview

### What This System Does

Extracts and validates clinical variables from pediatric brain tumor patient records using a two-agent architecture:

- **Agent 1 (You - Claude/MasterAgent)**: Orchestrator, validator, adjudicator, timeline analyzer
- **Agent 2 (MedGemma 27B)**: Medical text extractor (local Ollama model)

### Key Capabilities (v1.2.0)

✅ **Multi-source extraction**: Imaging text, imaging PDFs, operative reports, progress notes
✅ **Document text caching**: 80% cost savings, extract once use forever
✅ **Progress note prioritization**: 660 notes → ~20-40 key notes (96% reduction)
✅ **Temporal inconsistency detection**: Identifies clinically implausible patterns
✅ **Agent ↔ Agent feedback loops**: Iterative clarification queries
✅ **Multi-source EOR adjudication**: Operative reports (gold standard) vs imaging
✅ **Event type classification**: Initial/Recurrence/Progressive/Second Malignancy
✅ **Workflow monitoring**: Multi-level logging, error tracking, notifications
✅ **Timestamped abstractions**: Never overwrites, always creates new dated folders

---

## Architecture

### Two-Agent System

```
HUMAN USER
    ↓
AGENT 1 (Claude - MasterAgent)
    • Queries timeline database for patient history
    • Orchestrates extraction workflow across all sources
    • Detects temporal inconsistencies
    • Queries Agent 2 iteratively for clarification
    • Adjudicates multi-source conflicts
    • Classifies event types
    • Generates comprehensive patient abstractions
    ↓
AGENT 2 (MedGemma 27B via Ollama)
    • Extracts clinical variables from medical text
    • Classifies imaging (pre-op/post-op/surveillance)
    • Extracts extent of resection (EOR)
    • Extracts tumor status
    • Provides confidence scores
    • Responds to Agent 1's clarification queries
```

### Data Sources

1. **AWS Athena Views** (FHIR data from S3):
   - `v_imaging` - Text imaging reports (DiagnosticReport.conclusion)
   - `v_binary_files` - PDFs, HTML notes (Binary resources with DocumentReference metadata)
   - `v_procedures_tumor` - Surgical procedures with tumor classification

2. **DuckDB Databases** (Local):
   - `data/timeline.duckdb` - Patient timeline, events, extractions
   - `data/document_text_cache.duckdb` - Cached PDF/HTML text with provenance

3. **S3 Binary Storage**:
   - `s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/source/Binary/`
   - Accessed via BinaryFileAgent for PDF/HTML extraction

---

## Key Components (v1.2.0)

### 1. WorkflowMonitoring (`utils/workflow_monitoring.py`)

**Purpose:** Enhanced logging and error tracking

**Key Features:**
- Multi-level logging: console (human-readable), file (detailed), JSON (machine-readable)
- Error tracking with severity levels (WARNING, ERROR, CRITICAL)
- Notification framework (Email, Slack, webhook)
- Performance metrics

**Usage:**
```python
workflow_logger = WorkflowLogger(
    workflow_name="full_multi_source_abstraction",
    log_dir=output_dir,
    patient_id=patient_id,
    enable_json=True,
    enable_notifications=False
)
workflow_logger.log_info("Starting extraction")
workflow_logger.log_error("Failed to extract", error_type="extraction_error")
```

**Documentation:** [docs/WORKFLOW_MONITORING.md](docs/WORKFLOW_MONITORING.md)

### 2. DocumentTextCache (`utils/document_text_cache.py`)

**Purpose:** Cache extracted PDF/HTML text to avoid reprocessing (~80% cost savings)

**What Gets Cached:**
- All imaging PDF text (PyMuPDF extraction)
- All operative report text (HTML/PDF/text)
- All prioritized progress note text (HTML/PDF/text)

**Schema:** 23 provenance fields including:
- `extracted_text` (the actual text)
- `text_hash` (SHA256 for deduplication)
- `extraction_method` (pdf_pymupdf, html_beautifulsoup, text_plain)
- `extraction_version` (v1.1, v1.2, etc.)
- `binary_id`, `patient_fhir_id`, `document_date`

**Usage:**
```python
doc_cache = DocumentTextCache(db_path="data/document_text_cache.duckdb")

# Check cache first
cached_doc = doc_cache.get_cached_document(document_id)
if cached_doc:
    text = cached_doc.extracted_text
else:
    # Extract and cache
    text, error = binary_agent.extract_text_from_binary(binary_id, patient_id)
    doc_cache.cache_document_from_binary(
        document_id=document_id,
        patient_fhir_id=patient_id,
        extracted_text=text,
        extraction_method="pdf_pymupdf",
        binary_id=binary_id,
        document_date=doc_date
    )
```

**Documentation:** [docs/DOCUMENT_TEXT_CACHE.md](docs/DOCUMENT_TEXT_CACHE.md)

### 3. BinaryFileAgent (`agents/binary_file_agent.py`)

**Purpose:** Extract text from S3-stored PDF/HTML/text binary resources

**Capabilities:**
- PDF text extraction (PyMuPDF/fitz)
- HTML text extraction (BeautifulSoup)
- Plain text extraction
- S3 fetch and error handling

**Usage:**
```python
binary_agent = BinaryFileAgent()
extracted_text, error = binary_agent.extract_text_from_binary(binary_id, patient_id)
```

**Used In:**
- Phase 2B: Imaging PDF extraction
- Phase 2C: Operative report extraction
- Phase 2D: Progress note extraction

### 4. ProgressNotePrioritizer (`utils/progress_note_prioritization.py`)

**Purpose:** Reduce 660 oncology notes → ~20-40 clinically significant notes (96% reduction)

**Prioritization Strategy:**
- First note after each surgery (±7 days)
- First note after each imaging event (±7 days)
- First note after chemotherapy drug changes (start/stop)
- Always include final progress note

**Usage:**
```python
note_prioritizer = ProgressNotePrioritizer()
prioritized_notes = note_prioritizer.prioritize_notes(
    progress_notes=oncology_notes,
    surgeries=operative_reports,
    imaging_events=imaging_text_reports
)
# Returns list of PrioritizedNote objects with priority_reason
```

**Documentation:** [docs/PROGRESS_NOTE_PRIORITIZATION.md](docs/PROGRESS_NOTE_PRIORITIZATION.md)

---

## Main Workflow Script

### `scripts/run_full_multi_source_abstraction.py`

**Purpose:** Complete end-to-end comprehensive abstraction workflow

**Phases:**

1. **Phase 1: Query ALL Data Sources from Athena**
   - 1A: Imaging text reports (v_imaging)
   - 1B: Imaging PDFs (v_binary_files)
   - 1C: Operative reports (v_procedures_tumor)
   - 1D: Progress notes (v_binary_files) → filter oncology → prioritize

2. **Phase 2: Agent 2 Extraction with Agent 1 Review**
   - 2A: Extract from imaging text reports (82 reports)
   - 2B: Extract from imaging PDFs (104 PDFs) - **FULLY FUNCTIONAL**
   - 2C: Extract from operative reports (9 surgeries) - **FULLY FUNCTIONAL**
   - 2D: Extract from prioritized progress notes (~20-40 notes) - **FULLY FUNCTIONAL**

3. **Phase 3: Temporal Inconsistency Detection** (Agent 1)
   - Analyze timeline for clinical implausibility
   - Identify suspicious patterns

4. **Phase 4: Agent 1 ↔ Agent 2 Feedback Loops**
   - Agent 1 queries Agent 2 for clarification
   - Iterative refinement

5. **Phase 5: Multi-Source EOR Adjudication** (Agent 1)
   - Operative report (gold standard) vs imaging assessment

6. **Phase 6: Event Type Classification** (Agent 1)
   - Initial CNS Tumor / Recurrence / Progressive / Second Malignancy

7. **Phase 7: Save Comprehensive Abstraction**
   - Timestamped folder (e.g., `20251020_143522/`)
   - JSON with all extractions, decisions, QA reports
   - Checkpoint file for recovery

**Usage:**
```bash
python3 scripts/run_full_multi_source_abstraction.py --patient-id <PATIENT_FHIR_ID>
```

**Output:**
- `data/patient_abstractions/<TIMESTAMP>/<PATIENT_ID>.json` - Full abstraction
- `data/patient_abstractions/<TIMESTAMP>/<PATIENT_ID>_checkpoint.json` - Recovery checkpoint
- Log files in abstraction folder

---

## Critical Development Guidelines

### 1. ALWAYS Check Athena Schema Before Writing Queries

**Authoritative Source:** `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/utils/Athena_Schema.csv`

**Common Mistakes to Avoid:**
- ❌ `dr_id` → ✅ `document_reference_id`
- ❌ `dr_date` is correct (timestamp(3))
- ❌ `proc_id` → ✅ `procedure_fhir_id`
- ❌ `proc_date` → ✅ `proc_performed_date_time`

**Quick Reference:** [ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md](ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md)

### 2. Complete All Implementations

**DO:**
✅ Fully implement all phases before moving on
✅ Test code before committing
✅ Wire all components into workflow
✅ Complete documentation updates

**DON'T:**
❌ Leave placeholder implementations ("will implement later")
❌ Skip testing
❌ Commit broken code
❌ Forget to integrate created components

### 3. JSON Serialization

**CRITICAL:** ExtractionResult objects are NOT JSON serializable

**Correct:**
```python
all_extractions.append({
    'classification': classification_result.extracted_data if classification_result.success
                     else {'error': classification_result.error},
    'confidence': classification_result.confidence
})
```

**Incorrect:**
```python
all_extractions.append({
    'classification': classification_result  # ❌ NOT JSON serializable
})
```

### 4. Emergency Data Save

Always include emergency partial data save in exception handler:

```python
except Exception as e:
    logger.error(f"Workflow failed: {e}", exc_info=True)

    # CRITICAL: Save whatever data we have
    try:
        emergency_path = output_dir / f"{patient_id}_PARTIAL.json"
        with open(emergency_path, 'w') as f:
            json.dump(comprehensive_summary, f, indent=2)
        print(f"\n⚠️  PARTIAL DATA SAVED: {emergency_path}")
    except Exception as save_error:
        logger.error(f"Failed to save partial data: {save_error}")
```

---

## Common Tasks for New Sessions

### Task 1: Run Comprehensive Abstraction for Patient

```bash
# 1. Ensure AWS SSO is authenticated
aws sso login --profile radiant-prod

# 2. Run comprehensive workflow
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/run_full_multi_source_abstraction.py --patient-id <PATIENT_FHIR_ID>

# 3. Check output
ls -la data/patient_abstractions/$(ls -t data/patient_abstractions/ | head -1)/
```

### Task 2: Add New Clinical Variable to Extract

1. Update extraction prompts in `agents/extraction_prompts.py`
2. Update `agents/medgemma_agent.py` if needed (new extraction type)
3. Modify workflow script to call new extraction
4. Update timeline schema if storing in database
5. Test extraction on sample patient
6. Update documentation

### Task 3: Fix Athena Query Error

1. Read error message carefully
2. Check [utils/Athena_Schema.csv](utils/Athena_Schema.csv) for correct column name
3. Check [ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md](ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md)
4. Never guess - always verify against schema
5. Test query in Athena console before deploying

### Task 4: Debug Extraction Issues

1. Check MedGemma is running: `ollama list` (should show gemma2:27b)
2. Check extraction logs in abstraction folder
3. Review Agent 2 confidence scores (low confidence = potential issue)
4. Check timeline database for patient history context
5. Manually review source text vs extracted data
6. Check for temporal inconsistencies flagged by Agent 1

### Task 5: Add New Document Type for Extraction

1. Query `v_binary_files` to understand metadata (dr_category_text, dr_type_text, content_type)
2. Add filtering logic in Phase 1 (data query)
3. Integrate with BinaryFileAgent for text extraction
4. Add to DocumentTextCache caching logic
5. Create extraction prompt in `agents/extraction_prompts.py`
6. Add extraction loop in Phase 2
7. Update comprehensive_summary tracking
8. Test end-to-end
9. Update documentation

---

## File Structure Reference

```
/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/
├── agents/
│   ├── master_agent.py              # Agent 1 (Claude orchestrator)
│   ├── medgemma_agent.py            # Agent 2 (MedGemma wrapper)
│   ├── binary_file_agent.py         # PDF/HTML extraction from S3
│   ├── extraction_prompts.py        # All extraction prompts
│   ├── eor_adjudicator.py           # Multi-source EOR reconciliation
│   └── event_type_classifier.py     # Event classification logic
├── scripts/
│   └── run_full_multi_source_abstraction.py  # Main workflow
├── utils/
│   ├── Athena_Schema.csv            # AUTHORITATIVE schema (always check!)
│   ├── workflow_monitoring.py       # Enhanced logging
│   ├── document_text_cache.py       # PDF/HTML text caching
│   ├── progress_note_prioritization.py  # Note prioritization
│   └── progress_note_filters.py     # Oncology filtering
├── data/
│   ├── timeline.duckdb              # Patient timeline database
│   ├── document_text_cache.duckdb   # Cached extracted text
│   └── patient_abstractions/        # Timestamped output folders
├── docs/
│   ├── WORKFLOW_MONITORING.md       # Monitoring framework docs
│   ├── DOCUMENT_TEXT_CACHE.md       # Caching system docs
│   └── PROGRESS_NOTE_PRIORITIZATION.md  # Prioritization docs
├── COMPREHENSIVE_SYSTEM_DOCUMENTATION.md  # Complete system guide
├── ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md  # Column name reference
├── AGENT_ONBOARDING_GUIDE.md        # This file
└── PRODUCTION_DEPLOYMENT_ROADMAP.md  # Production deployment plan
```

---

## Troubleshooting

### Issue: AWS SSO Token Expired

**Symptoms:** `Error when retrieving token from sso: Token has expired and refresh failed`

**Solution:**
```bash
aws sso login --profile radiant-prod
```

### Issue: MedGemma Not Responding

**Symptoms:** Extraction hangs, timeout errors

**Check:**
```bash
ollama list  # Should show gemma2:27b
ollama ps    # Should show running model if in use
```

**Restart:**
```bash
ollama restart
```

### Issue: Column Name Error in Athena Query

**Symptoms:** `COLUMN_NOT_FOUND: Column 'xyz' cannot be resolved`

**Solution:**
1. Open [utils/Athena_Schema.csv](utils/Athena_Schema.csv)
2. Search for the view name (e.g., `v_binary_files`)
3. Find correct column name
4. Update query
5. NEVER guess column names

### Issue: Workflow Completed But No Data Saved

**Symptoms:** Only checkpoint file created, no JSON with extractions

**Possible Causes:**
1. JSON serialization error (ExtractionResult objects not converted to dicts)
2. Exception before final save

**Check:**
- Look for `*_PARTIAL.json` file (emergency save)
- Check workflow logs for errors
- Verify all `extracted_data` dicts are extracted from ExtractionResult objects

**Prevention:**
- v1.1.1+ includes automatic emergency partial data save
- Always test JSON serialization before large runs

---

## Version History Quick Reference

### v1.2.0 (2025-10-20) - Current Version
- ✅ All 4 components fully integrated (WorkflowMonitoring, DocumentTextCache, BinaryFileAgent, ProgressNotePrioritizer)
- ✅ Phases 2B, 2C, 2D fully functional (imaging PDFs, operative reports, progress notes)
- ✅ Complete end-to-end multi-source workflow operational

### v1.1.1 (2025-10-20)
- 🔥 CRITICAL: Fixed JSON serialization bug causing 100% data loss
- ✅ Emergency partial data save on errors

### v1.1 (2025-10-20)
- ✅ Workflow monitoring framework
- ✅ Document text cache created
- ✅ Progress note prioritization created

### v1.0 (2025-10-19)
- ✅ Two-agent architecture implemented
- ✅ Timeline-aware extraction
- ✅ Multi-step extraction workflow

---

## Getting Help

### Documentation Priority Order

1. **This document** - Quick context for new sessions
2. **COMPREHENSIVE_SYSTEM_DOCUMENTATION.md** - Complete system architecture
3. **Component-specific docs** in `docs/` folder
4. **Session summaries** (SESSION_SUMMARY_*.md) - Development history

### When Starting a New Session

**Prompt for Human to Provide:**

```
I need help with the Multi-Agent Clinical Data Extraction System.
Please read these context documents:

1. AGENT_ONBOARDING_GUIDE.md (this provides complete context)
2. COMPREHENSIVE_SYSTEM_DOCUMENTATION.md (system architecture)
3. utils/Athena_Schema.csv (authoritative schema - check before any Athena queries)

Key context:
- System version: v1.2.0
- Two-agent architecture: Claude (Agent 1) ↔ MedGemma (Agent 2)
- Main workflow: scripts/run_full_multi_source_abstraction.py
- Critical rule: NEVER guess Athena column names, always check schema

My task: [describe what you need]
```

### What Information to Provide

When asking for help, include:
1. **What you're trying to accomplish**
2. **What you've tried**
3. **Error messages** (full stack trace)
4. **Patient ID** (if applicable)
5. **Workflow phase** where issue occurred
6. **Recent changes** to code

---

## Production Deployment Context

**Current State:** Single-patient local test workflow
**Next Steps:** See [PRODUCTION_DEPLOYMENT_ROADMAP.md](PRODUCTION_DEPLOYMENT_ROADMAP.md)

**Key Differences:**
- Local: Test one patient at a time, manual execution
- Production: Batch processing, automated orchestration, monitoring, error recovery

---

**Last Updated:** 2025-10-20
**Maintained By:** Adam Cresnick, MD & Claude (Agent 1)
**Repository:** https://github.com/adamcresnick/BRIM_Analytics
