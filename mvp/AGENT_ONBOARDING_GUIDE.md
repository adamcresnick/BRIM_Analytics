# Agent 1 (Claude) Onboarding Guide

**Purpose:** Provide comprehensive context for new Claude sessions working on the Multi-Agent Clinical Data Extraction System

**Last Updated:** 2025-10-25
**System Version:** v1.3.0
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

### Key Capabilities (v1.3.0)

✅ **Multi-source extraction**: Imaging text, imaging PDFs, operative reports, progress notes
✅ **Document text caching**: 80% cost savings, extract once use forever
✅ **Progress note prioritization**: 660 notes → ~20-40 key notes (96% reduction)
✅ **Temporal inconsistency detection**: Identifies clinically implausible patterns
✅ **Agent ↔ Agent feedback loops**: Iterative clarification queries
✅ **Multi-source EOR adjudication**: Operative reports (gold standard) vs imaging
✅ **Event type classification**: Initial/Recurrence/Progressive/Second Malignancy
✅ **Workflow monitoring**: Multi-level logging, error tracking, notifications
✅ **Timestamped abstractions**: Never overwrites, always creates new dated folders
✅ **Enhanced operative note extraction**: Deduplication, datetime bug fixes, failure tracking
✅ **Automatic AWS SSO refresh**: Handles token expiration in long-running workflows
✅ **Athena view deployment**: Automated timeline view deployment with prerequisites
✅ **ChemotherapyFilter integration**: Automatic medication categorization in timeline

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

### 5. Enhanced Operative Note Extraction (v1.3.0)

**Purpose:** Robust operative note extraction with deduplication and error handling

**Bug Fixes (Oct 23-24):**

1. **Datetime Column Handling:**
   - All observation datetime columns wrapped in `TRY_CAST(... AS TIMESTAMP(3))`
   - Prevents extraction crashes from malformed datetime strings
   - Affects: operative notes, pathology reports, radiology reports in `v_binary_files`

2. **Operative Note Deduplication:**
   - Prevents duplicate extractions when same note linked to multiple procedures
   - Uses `document_reference_id` for deduplication instead of `procedure_fhir_id`
   - Reduces extraction costs and improves data quality
   - Example: Single operative note with tumor and non-tumor procedures

3. **Extraction Failure Tracking:**
   - Failed operative note extractions logged to `failed_operative_extractions` list
   - Enables post-workflow QA review
   - Format: `{'document_reference_id': '...', 'error': '...', 'procedure_id': '...'}`

**Usage in Workflow:**
```python
# Deduplication
seen_doc_refs = set()
for note in operative_reports:
    doc_ref_id = note['document_reference_id']
    if doc_ref_id in seen_doc_refs:
        continue  # Skip duplicate
    seen_doc_refs.add(doc_ref_id)

    # Extract text from cache or Binary
    cached_doc = doc_cache.get_cached_document(doc_ref_id)
    if cached_doc:
        text = cached_doc.extracted_text
    else:
        text, error = binary_agent.extract_text_from_binary(...)
        if error:
            failed_operative_extractions.append({
                'document_reference_id': doc_ref_id,
                'error': error,
                'procedure_id': note['procedure_fhir_id']
            })
            continue
```

**Code Location:** `scripts/run_full_multi_source_abstraction.py` lines 450-550

**Quality Assurance:**
After workflow completion, check `comprehensive_summary['failed_operative_extractions']` for:
- Binary files not found in S3 (404 errors)
- PDF corruption or unsupported formats
- Text extraction timeouts (large PDFs)
- SSO token expiration (now auto-retried)

### 6. Automatic AWS SSO Token Refresh (v1.3.0)

**Purpose:** Automatically handle expired SSO tokens during long-running extractions

**How It Works:**
1. BinaryFileAgent detects SSO token expiration errors
2. Triggers `aws sso login --profile radiant-prod` subprocess
3. Waits for user to complete browser authentication
4. Retries failed operation automatically
5. Continues extraction workflow without manual intervention

**Impact:**
- Eliminates workflow interruptions from token expiration
- Enables multi-hour extraction workflows
- Reduces manual monitoring requirements

**Code Location:** `agents/binary_file_agent.py` lines 180-220

**User Experience:**
```
⚠️  AWS SSO token expired. Initiating automatic login...
🔐 Please complete SSO login in your browser...
✓ SSO login successful! Resuming extraction...
```

**Note:** User must still complete browser authentication, but workflow resumes automatically afterward.

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

## Athena View Deployment and Timeline Maintenance

### When to Rebuild Timeline Views

Rebuild Athena timeline views when:
1. Source FHIR views change (v_medications, v_imaging, v_procedures_tumor, etc.)
2. Timeline view logic updated (new event types, column changes)
3. Temporal context calculations modified
4. Column name standardization applied

**Recent Updates (Oct 25):**
- Column standardization: `patient_id` → `patient_fhir_id` across all views
- Datetime standardization: `VARCHAR` → `TIMESTAMP(3)` for all datetime columns
- New data source: `v_visits_unified` v2.2 (unified encounters + appointments)
- Updated prerequisite views with correct column names

### Prerequisite Views (MUST DEPLOY FIRST)

The unified timeline depends on two prerequisite views that **MUST** be deployed before the main timeline view:

1. **v_diagnoses** - Normalizes `v_problem_list_diagnoses`
   - Removes `pld_` column prefixes
   - Standardizes diagnosis data structure
   - File: `athena_views/views/V_DIAGNOSES.sql`

2. **v_radiation_summary** - Aggregates `v_radiation_treatments`
   - Course-level radiation summaries (course 1, 2, 3)
   - Uses `patient_fhir_id` (not `patient_id`)
   - File: `athena_views/views/V_RADIATION_SUMMARY.sql`

### Deployment Procedure

```bash
# Navigate to athena_views directory
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views

# Deploy all timeline views (prerequisites + main view)
./deploy_unified_timeline.sh

# Output:
# Deploying v_diagnoses...
#   ✅ v_diagnoses deployed successfully!
# Deploying v_radiation_summary...
#   ✅ v_radiation_summary deployed successfully!
# Deploying v_unified_patient_timeline...
#   ✅ v_unified_patient_timeline deployed successfully!
```

**Deployment Script:** `athena_views/deploy_unified_timeline.sh`
- Deploys views in correct order (prerequisites first)
- Handles Athena's single-statement limitation
- Polls for query completion
- Reports deployment status

### Timeline View Files

- `athena_views/views/V_DIAGNOSES.sql` - Diagnosis normalization view
- `athena_views/views/V_RADIATION_SUMMARY.sql` - Radiation course summaries
- `athena_views/views/V_UNIFIED_PATIENT_TIMELINE.sql` - Main timeline view (with comments & validation queries)
- `athena_views/views/V_UNIFIED_PATIENT_TIMELINE_DEPLOY.sql` - Clean deployment version (no comments)
- `athena_views/deploy_unified_timeline.sh` - Automated deployment script

### Rebuild DuckDB Timeline After Athena Updates

**CRITICAL:** After deploying updated Athena views, rebuild local DuckDB timeline:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/build_timeline_database.py
```

**What This Does:**
1. Queries updated `v_unified_patient_timeline` from Athena
2. Applies ChemotherapyFilter to medication categorization
3. Computes temporal context (disease phases, milestones)
4. Loads data into `data/timeline.duckdb`
5. Creates indexes for fast queries

**Output:**
```
================================================================================
BUILD DUCKDB TIMELINE DATABASE
Patient: e4BwD8ZYDBccepXcJ.Ilo3w3
================================================================================

Applying ChemotherapyFilter to medications
  ✓ vinBLAStine inj 10 mg → Chemotherapy (rxnorm_ingredient, high confidence)
  ✓ selumetinib capsule → Targeted Therapy (drug_name_alias, medium confidence)

✓ Updated 110 medication categories using ChemotherapyFilter

Milestones identified:
  first_treatment_date: 2021-05-20

Disease phase distribution:
  Observation     12527
  Surveillance      478
  On-treatment      261

✅ TIMELINE DATABASE CREATED SUCCESSFULLY
Database location: /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/data/timeline.duckdb

Event counts by type:
  Visit                1007
  Measurement           438
  Medication            281
  Imaging                82
  Procedure               9
  Molecular Test          3
```

**Validation:**
```python
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
conn.execute('SELECT event_type, COUNT(*) FROM events GROUP BY event_type').fetchdf()
```

### ChemotherapyFilter Integration in Timeline Build

**Automatic Medication Categorization:**

When building the timeline database, medications are automatically categorized using ChemotherapyFilter:

**Process:**
1. Query medications from `v_medications` (includes medication names and RxNorm codes)
2. Apply ChemotherapyFilter to each medication
3. Classify as: Chemotherapy, Targeted Therapy, or Other Medication
4. Update `event_category` in timeline database

**Reference Files Location:**
`athena_views/data_dictionary/chemo_reference/`
- `chemotherapy_drugs.csv` - 3067 drug names and classifications
- `chemotherapy_drug_aliases.csv` - 23795 name variations
- `chemotherapy_rxnorm_mappings.csv` - 2806 RxNorm code mappings

**Code Location:** `scripts/build_timeline_database.py` lines 120-180

### Troubleshooting Timeline Deployment

**Error: "Only one sql statement is allowed"**
- Cause: SQL file contains comments or multiple statements
- Solution: Use `V_UNIFIED_PATIENT_TIMELINE_DEPLOY.sql` (clean version without comments)

**Error: "Column 'patient_id' cannot be resolved"**
- Cause: View uses old column name
- Solution: Update to `patient_fhir_id` everywhere in source views

**Timeline has no events after rebuild:**
- Check SSO token: `aws sso login --profile radiant-prod`
- Verify Athena views deployed successfully via AWS Console
- Check test patient ID matches: `e4BwD8ZYDBccepXcJ.Ilo3w3`

**Deployment takes very long:**
- Normal for large views (v_unified_patient_timeline can take 30-60 seconds)
- Script polls every 2 seconds for completion
- Check Athena console for query progress

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
/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/
├── mvp/
│   ├── agents/
│   │   ├── master_agent.py              # Agent 1 (Claude orchestrator)
│   │   ├── medgemma_agent.py            # Agent 2 (MedGemma wrapper)
│   │   ├── binary_file_agent.py         # PDF/HTML extraction from S3
│   │   ├── extraction_prompts.py        # All extraction prompts
│   │   ├── eor_adjudicator.py           # Multi-source EOR reconciliation
│   │   └── event_type_classifier.py     # Event classification logic
│   ├── scripts/
│   │   ├── run_full_multi_source_abstraction.py  # Main workflow
│   │   └── build_timeline_database.py   # Build DuckDB timeline from Athena
│   ├── utils/
│   │   ├── Athena_Schema.csv            # AUTHORITATIVE schema (always check!)
│   │   ├── workflow_monitoring.py       # Enhanced logging
│   │   ├── document_text_cache.py       # PDF/HTML text caching
│   │   ├── progress_note_prioritization.py  # Note prioritization
│   │   └── progress_note_filters.py     # Oncology filtering
│   ├── data/
│   │   ├── timeline.duckdb              # Patient timeline database
│   │   ├── document_text_cache.duckdb   # Cached extracted text
│   │   └── patient_abstractions/        # Timestamped output folders
│   ├── docs/
│   │   ├── WORKFLOW_MONITORING.md       # Monitoring framework docs
│   │   ├── DOCUMENT_TEXT_CACHE.md       # Caching system docs
│   │   └── PROGRESS_NOTE_PRIORITIZATION.md  # Prioritization docs
│   ├── COMPREHENSIVE_SYSTEM_DOCUMENTATION.md  # Complete system guide
│   ├── ATHENA_VIEW_COLUMN_QUICK_REFERENCE.md  # Column name reference
│   ├── AGENT_ONBOARDING_GUIDE.md        # This file
│   ├── V_UNIFIED_TIMELINE_REBUILD_ASSESSMENT.md  # Timeline rebuild rationale
│   └── PRODUCTION_DEPLOYMENT_ROADMAP.md  # Production deployment plan
├── athena_views/
│   ├── views/
│   │   ├── V_DIAGNOSES.sql              # Prerequisite: Normalized diagnoses
│   │   ├── V_RADIATION_SUMMARY.sql      # Prerequisite: Radiation course summaries
│   │   ├── V_UNIFIED_PATIENT_TIMELINE.sql  # Main timeline view (with comments)
│   │   └── V_UNIFIED_PATIENT_TIMELINE_DEPLOY.sql  # Clean deployment version
│   ├── deploy_unified_timeline.sh       # Automated timeline deployment
│   └── data_dictionary/
│       └── chemo_reference/             # ChemotherapyFilter reference files
│           ├── chemotherapy_drugs.csv
│           ├── chemotherapy_drug_aliases.csv
│           └── chemotherapy_rxnorm_mappings.csv
```

---

## Troubleshooting

### Issue: AWS SSO Token Expired

**Symptoms:** `Error when retrieving token from sso: Token has expired and refresh failed`

**Automatic Handling (v1.3.0):**
BinaryFileAgent now automatically handles SSO token expiration:
1. Detects token expiration error
2. Triggers `aws sso login` automatically
3. Waits for browser authentication
4. Resumes extraction workflow

**User Experience:**
```
⚠️  AWS SSO token expired. Initiating automatic login...
🔐 Please complete SSO login in your browser...
✓ SSO login successful! Resuming extraction...
```

**Manual Solution (if needed):**
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

### v1.3.0 (2025-10-25) - Current Version
- ✅ Enhanced operative note extraction with deduplication and datetime bug fixes
- ✅ Automatic AWS SSO token refresh for long-running workflows
- ✅ Extraction failure tracking for quality assurance
- ✅ Athena timeline view deployment automation (prerequisites + main view)
- ✅ DuckDB timeline rebuild procedures documented
- ✅ ChemotherapyFilter integration in timeline build
- ✅ Column name standardization: patient_id → patient_fhir_id across all views
- ✅ Datetime standardization: VARCHAR → TIMESTAMP(3) for all datetime columns
- ✅ v_visits_unified v2.2 integration in timeline

### v1.2.0 (2025-10-20)
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

**Last Updated:** 2025-10-25
**Maintained By:** Adam Cresnick, MD & Claude (Agent 1)
**Repository:** https://github.com/adamcresnick/BRIM_Analytics
