# MVP Requirements and Implementation Plan
## Two-Agent Clinical Data Extraction Framework

**Last Updated**: October 19, 2025
**Status**: Planning Phase
**GitHub Tracking**: See [Tracking Strategy](#github-tracking-strategy)

---

## Executive Summary

This document defines requirements for a minimal viable product (MVP) that validates the core 2-agent clinical data extraction workflow:

- **Agent 1 (Claude)**: Master orchestrator with complete context about workflows, schemas, and metadata
- **Agent 2 (MedGemma/Ollama)**: Clinical text extraction specialist

**Core Principle**: Agent 1 must be self-sufficient - requiring NO manual schema input, workflow explanation, or context provision from the user each session.

**Validation Target**: Extract 5 variables for patient C1277724 with >80% accuracy, <60s latency, <$0.50 cost.

---

## Requirements Specification

### R1: Agent 1 Context Requirements

Agent 1 must have immediate access to:

#### R1.1: Workflow Knowledge
- [ ] Master orchestration workflow (query → filter → verify → extract → validate)
- [ ] Document selection strategy (metadata-based filtering)
- [ ] S3 availability checking procedure
- [ ] Agent 2 interaction protocol
- [ ] Validation and output formatting

**Success Criteria**: Agent 1 can execute full workflow without asking user for process clarification.

#### R1.2: Database Schema Knowledge
- [ ] Summary of all 27 Athena views with descriptions
- [ ] Detailed schema for core views:
  - `v_procedures_tumor` (surgery timeline)
  - `v_medications` (chemotherapy)
  - `v_imaging` (radiology timeline)
  - `v_diagnoses` (diagnosis dates, ICD codes)
  - `v_binary_files` (22K documents with metadata)
- [ ] Common SQL patterns and examples
- [ ] Known schema quirks (e.g., period-to-underscore in S3 filenames)

**Success Criteria**: Agent 1 can write correct SQL queries for timeline/metadata extraction without user providing schema details.

#### R1.3: Variable Schema Knowledge
- [ ] Definitions for 35 BRIM variables
- [ ] Expected data types and formats
- [ ] Fallback strategies when data unavailable
- [ ] Structured data sources for each variable
- [ ] Document types most likely to contain each variable

**Success Criteria**: Agent 1 knows what to extract, where to look, and how to validate.

#### R1.4: Document Classification Metadata
- [ ] `dr_practice_setting_text` values (Oncology, Neurosurgery, Radiology, Pathology)
- [ ] `dr_type_coding_display` values (document types)
- [ ] Temporal filtering strategies (diagnosis ±14 days, surgery ±3 days)
- [ ] Content type distribution (text/html 34%, text/rtf 33%, PDF 2%)
- [ ] S3 availability rate (57% empirically measured)

**Success Criteria**: Agent 1 can select 15-20 high-value documents using metadata alone, without text analysis.

---

### R2: Python Orchestrator Requirements

Simple Python module with 4 core functions (NO MCP overhead):

#### R2.1: `query_athena(sql: str) -> List[Dict]`
- [ ] Execute SQL query against AWS Athena
- [ ] Return results as list of dictionaries
- [ ] Handle common errors (syntax, timeout, permissions)
- [ ] Support parameterized queries (patient_fhir_id substitution)

#### R2.2: `check_s3_availability(binary_ids: List[str]) -> Dict[str, bool]`
- [ ] Check if binary files exist in S3
- [ ] Handle period-to-underscore filename transformation
- [ ] Return dictionary mapping binary_id → exists (True/False)
- [ ] Batch check multiple files efficiently

#### R2.3: `extract_text_from_s3(binary_id: str) -> str`
- [ ] Download binary file from S3
- [ ] Extract text based on content type:
  - `text/html`: HTML → markdown conversion
  - `text/rtf`: RTF → plain text
  - `application/pdf`: PDF → text extraction
- [ ] Return extracted text or error message
- [ ] Handle large files (>5MB) gracefully

#### R2.4: `call_medgemma(document_text: str, variable: str, context: Dict) -> Dict`
- [ ] Format prompt for MedGemma with document text, variable definition, and patient context
- [ ] Call Ollama via subprocess with 60-second timeout
- [ ] Parse JSON response from MedGemma
- [ ] Return structured extraction result with confidence score

**Success Criteria**: Agent 1 can call these functions via simple Python subprocess and receive structured responses.

---

### R3: Static Context Files

Files auto-loaded by Claude Code from `.claude/` directory:

#### R3.1: `.claude/clinical-extraction/master-workflow.md`
- [ ] Agent 1 role definition
- [ ] Step-by-step orchestration workflow
- [ ] Available Python functions and calling conventions
- [ ] Quality metrics and validation approach
- [ ] Common troubleshooting scenarios

**Token Budget**: ~3,000 tokens

#### R3.2: `.claude/clinical-extraction/variable-schema.md`
- [ ] Definitions for 35 BRIM variables
- [ ] For each variable:
  - Name and description
  - Expected data type/format
  - Structured data sources (Athena views)
  - Document types likely to contain
  - Example values
  - Validation rules

**Token Budget**: ~5,000 tokens

#### R3.3: `.claude/clinical-extraction/quick-reference.md`
- [ ] Common SQL patterns (timeline queries, metadata filters)
- [ ] Document selection examples
- [ ] S3 filename transformation rules
- [ ] MedGemma prompt templates
- [ ] Validation strategies

**Token Budget**: ~2,000 tokens

**Total Context Budget**: ~10,000 tokens (leaves ~190K for dynamic content)

**Success Criteria**: Agent 1 has complete workflow/variable knowledge without reading additional files.

---

### R4: Pre-Generated Schema Documentation

Schema files generated once via Python script, updated when views change:

#### R4.1: `.claude/schemas/all-views-summary.md`
- [ ] List of all 27 Athena views
- [ ] One-line description for each
- [ ] Link to detailed schema file
- [ ] Last updated timestamp

**Token Budget**: ~1,000 tokens

#### R4.2: `.claude/schemas/v_{view_name}.md` (27 files)
- [ ] Full column list with data types
- [ ] Sample row (anonymized)
- [ ] Common query patterns
- [ ] Join relationships to other views
- [ ] Known data quality issues

**Token Budget per file**: ~500-1,000 tokens
**Read on demand**: Agent 1 only reads when writing complex SQL

#### R4.3: Schema Generation Script
- [ ] `mvp/schemas/generate_schema_docs.py`
- [ ] Queries `INFORMATION_SCHEMA.COLUMNS` for each view
- [ ] Generates markdown files with consistent format
- [ ] Can be re-run when views are modified

**Success Criteria**: Agent 1 can read view schema details on-demand without user providing schema manually.

---

### R5: End-to-End Validation Requirements

Test with patient C1277724, extract 5 variables:

#### R5.1: Target Variables
1. **primary_diagnosis**: Expected "Low-grade glioma, NOS" (from v_diagnoses or pathology report)
2. **who_grade**: Expected "WHO Grade I" (from pathology report)
3. **surgery_date**: Expected "2018-06-06" (from v_procedures_tumor)
4. **tumor_location**: Expected "Optic pathway/hypothalamus" (from radiology or operative note)
5. **chemotherapy_agent**: Expected "Vinblastine, Bevacizumab, Selumetinib" (from v_medications or oncology notes)

#### R5.2: Workflow Steps to Validate
- [ ] Step 1: Agent 1 queries patient timeline (diagnosis, surgery, chemo dates)
- [ ] Step 2: Agent 1 filters v_binary_files using metadata
- [ ] Step 3: Agent 1 checks S3 availability (expect 57% success rate)
- [ ] Step 4: Agent 1 extracts text from available documents
- [ ] Step 5: Agent 1 calls Agent 2 for each variable
- [ ] Step 6: Agent 1 validates against structured data (cross-check v_medications, v_procedures_tumor)
- [ ] Step 7: Agent 1 outputs JSON with extracted variables

#### R5.3: Success Metrics
- [ ] **Accuracy**: ≥4/5 variables correct (80%)
- [ ] **Latency**: <60 seconds total processing time
- [ ] **Cost**: <$0.50 in Claude API costs (~25K input + 2K output tokens)
- [ ] **Context Sufficiency**: Agent 1 does NOT ask user for schemas, workflows, or clarification
- [ ] **S3 Availability**: Confirms ~57% rate, implements fallback document selection

#### R5.4: Output Format
```json
{
  "patient_id": "e4BwD8ZYDBccepXcJ.Ilo3w3",
  "extraction_date": "2025-10-19",
  "variables": {
    "primary_diagnosis": {
      "value": "Low-grade glioma, NOS",
      "confidence": 0.95,
      "source": "pathology_report_2018-06-10",
      "validation": "matches v_diagnoses ICD code C71.9"
    },
    "who_grade": {
      "value": "WHO Grade I",
      "confidence": 0.90,
      "source": "pathology_report_2018-06-10",
      "validation": "consistent with low-grade glioma diagnosis"
    },
    ...
  },
  "metrics": {
    "processing_time_seconds": 45,
    "claude_input_tokens": 24500,
    "claude_output_tokens": 1800,
    "estimated_cost_usd": 0.42,
    "documents_selected": 18,
    "documents_available_s3": 10,
    "documents_extracted": 8,
    "medgemma_calls": 5
  }
}
```

**Success Criteria**: Output JSON matches expected values with validation sources clearly documented.

---

## Component Breakdown

### Component 1: Static Context Files
**Purpose**: Provide Agent 1 with always-available workflow, variable, and quick-reference knowledge.

**Deliverables**:
- `.claude/clinical-extraction/master-workflow.md`
- `.claude/clinical-extraction/variable-schema.md`
- `.claude/clinical-extraction/quick-reference.md`

**Dependencies**: None

**Validation**: Agent 1 can describe full workflow and all 35 variables without reading external files.

---

### Component 2: Pre-Generated Schema Documentation
**Purpose**: Provide on-demand access to detailed view schemas without querying Athena.

**Deliverables**:
- `mvp/schemas/generate_schema_docs.py` (schema generator script)
- `.claude/schemas/all-views-summary.md` (27 view list)
- `.claude/schemas/v_{view_name}.md` (27 individual schema files)

**Dependencies**:
- AWS Athena access to query `INFORMATION_SCHEMA`
- All 27 views already created (completed in previous work)

**Validation**: Agent 1 can write correct SQL for v_procedures_tumor, v_medications, v_binary_files without user providing schema.

---

### Component 3: Simple Python Orchestrator
**Purpose**: Provide Agent 1 with callable functions for Athena queries, S3 access, and Agent 2 interaction.

**Deliverables**:
- `mvp/orchestrator/simple_orchestrator.py` (4 core functions)
- `mvp/orchestrator/config.py` (AWS credentials, S3 bucket, Athena database)
- `mvp/orchestrator/README.md` (usage examples)

**Dependencies**:
- `boto3` (AWS SDK)
- `beautifulsoup4` (HTML parsing)
- `pypdf` (PDF text extraction)
- `striprtf` (RTF text extraction)
- Ollama with MedGemma model installed

**Validation**: Agent 1 can call each function and receive expected response format.

---

### Component 4: End-to-End Test Script
**Purpose**: Validate complete workflow with patient C1277724.

**Deliverables**:
- `mvp/tests/test_patient_c1277724.py` (automated test)
- `mvp/tests/expected_output.json` (gold standard for 5 variables)
- `mvp/tests/test_results.md` (metrics and findings)

**Dependencies**:
- Components 1-3 completed
- Patient C1277724 data available in Athena and S3

**Validation**: Test passes with ≥80% accuracy, <60s latency, <$0.50 cost.

---

## GitHub Tracking Strategy

### Branch Strategy
- `main` - stable code, no active development
- `mvp/context-files` - Component 1 (static context)
- `mvp/schema-docs` - Component 2 (pre-generated schemas)
- `mvp/orchestrator` - Component 3 (Python functions)
- `mvp/testing` - Component 4 (end-to-end validation)

Merge to `main` only after component validation complete.

---

### Issue Template

Create GitHub issues for each requirement with this structure:

```markdown
### Requirement ID
[e.g., R1.1, R2.3, R3.1]

### Component
[e.g., Static Context Files, Python Orchestrator]

### Description
[Clear description of what needs to be built]

### Success Criteria
- [ ] Criteria 1
- [ ] Criteria 2

### Dependencies
[Other issues that must be completed first]

### Validation Approach
[How to test this requirement is met]

### Branch
[GitHub branch name]
```

---

### Milestones

**Milestone 1: Context Complete**
- Issues: All R1.x, R3.x, R4.x requirements
- Goal: Agent 1 has complete workflow, variable, and schema knowledge
- Success: Agent 1 can describe workflow and write SQL without user input

**Milestone 2: Orchestrator Functional**
- Issues: All R2.x requirements
- Goal: Agent 1 can call Python functions for Athena, S3, and MedGemma
- Success: Each function returns expected response format

**Milestone 3: End-to-End Validation**
- Issues: All R5.x requirements
- Goal: Complete workflow validated with patient C1277724
- Success: ≥80% accuracy, <60s latency, <$0.50 cost

---

### Tracking Progress

Check progress at any time:
```bash
# View open issues by milestone
gh issue list --milestone "Context Complete"

# View branch status
git branch -v | grep mvp/

# View test results
cat mvp/tests/test_results.md
```

**No time-based tracking** - work proceeds at user-determined pace, tracked by GitHub issue completion.

---

## Decision Log

### Decision 1: Static Context vs. MCP Server
**Decision**: Use static `.claude/` files for workflow/variable knowledge
**Rationale**:
- Auto-loaded by Claude Code (zero infrastructure)
- Sufficient for ~10K tokens of static content
- MCP adds complexity without clear MVP benefit
**Validation**: If Agent 1 repeatedly asks for context, revisit MCP approach

---

### Decision 2: Pre-Generated Schemas vs. Dynamic Lookup
**Decision**: Generate schema docs once via Python script, read on-demand
**Rationale**:
- 27 views * ~500 tokens = 13.5K tokens (too large for always-loaded context)
- Schemas change infrequently (only when views modified)
- On-demand reading = Agent 1 only loads schemas when writing complex SQL
**Validation**: If schemas become stale, add schema generation to CI/CD

---

### Decision 3: Python Functions vs. MCP Server
**Decision**: Simple Python module with 4 functions called via subprocess
**Rationale**:
- MVP needs validation, not abstraction
- Existing `real_agentic_ollama_pilot.py` already uses subprocess successfully
- MCP adds TypeScript, protocol overhead, debugging complexity
**Validation**: If Agent 1 struggles with subprocess calls OR we add 10+ functions, revisit MCP

---

### Decision 4: RAG Vector DB vs. Static Files
**Decision**: No vector database for MVP
**Rationale**:
- 50 markdown files (~500KB total) = not a retrieval problem
- Static context + pre-generated schemas = sufficient for MVP
- ChromaDB/MCP overhead not justified for 50 files
**Validation**: If Agent 1 can't find relevant schema/workflow info, add semantic search

---

### Decision 5: MedGemma vs. Claude API for Extraction
**Decision**: Keep MedGemma (Agent 2) for MVP, measure quality gap
**Rationale**:
- User already has MedGemma/Ollama setup working
- Local execution = no per-token cost for extraction
- MVP goal is to validate workflow, not optimize extraction quality
**Validation**: After MVP, compare MedGemma vs Claude API accuracy and cost

---

## Risk Assessment

### Risk 1: Static Context Insufficient
**Probability**: Medium
**Impact**: High (Agent 1 asks user for context repeatedly)
**Mitigation**:
- Keep static context comprehensive (~10K tokens)
- Include common SQL patterns and examples in quick-reference
- Monitor: If Agent 1 asks >2 clarifying questions, context is insufficient

---

### Risk 2: S3 Availability <57%
**Probability**: Low (empirically measured at 57%)
**Impact**: Medium (fewer documents available for extraction)
**Mitigation**:
- Always check S3 availability before extraction
- Implement fallback document selection (alternative docs in same temporal window)
- Document S3 availability per patient in test results

---

### Risk 3: MedGemma Accuracy <<80%
**Probability**: Medium (no baseline yet)
**Impact**: High (MVP validation fails)
**Mitigation**:
- Test with 5 variables first (easy to manually validate)
- Compare structured data (v_medications, v_procedures_tumor) vs extracted data
- If accuracy <70%, switch to Claude API for extraction and re-measure

---

### Risk 4: Python Orchestrator Too Simplistic
**Probability**: Low
**Impact**: Low (can iterate quickly with Python)
**Mitigation**:
- Keep functions simple and focused (single responsibility)
- Add error handling and timeouts
- If Agent 1 struggles with subprocess, add helper script that Agent 1 calls directly

---

### Risk 5: Agent 1 Writes Incorrect SQL
**Probability**: Medium
**Impact**: Medium (incorrect timeline/metadata extraction)
**Mitigation**:
- Include SQL examples in quick-reference.md
- Validate SQL results against known patient C1277724 data
- If Agent 1 makes >2 SQL errors, add more examples or provide schema hints

---

## Next Steps

### Immediate (Unblocked)
1. Create Component 1: Static context files (`.claude/clinical-extraction/*.md`)
2. Create Component 2: Schema generation script and pre-generated schemas
3. Create Component 3: Python orchestrator with 4 core functions

### Blocked Until MVP Complete
- MCP server development (deferred)
- RAG vector database (deferred)
- Multi-patient batch processing (deferred)
- Security/compliance hardening (deferred)
- Production deployment (deferred)

### After MVP Validation
**If MVP succeeds (≥80% accuracy)**:
- Expand to full 35 variables
- Test with 3 more patients
- Measure cost/latency at scale
- Decide: Is MCP/RAG needed OR is MVP approach sufficient?

**If MVP fails (<80% accuracy)**:
- Root cause analysis: Context insufficient? MedGemma quality? Document selection?
- Iterate on failing component
- Re-validate with patient C1277724

---

## Success Definition

**MVP is successful when**:
1. Agent 1 executes full workflow for patient C1277724 WITHOUT asking user for schemas, workflows, or clarification
2. Extraction accuracy ≥80% (4/5 variables correct)
3. Processing time <60 seconds
4. Cost <$0.50 per patient
5. All code tracked in GitHub with requirements mapped to issues

**MVP proves**:
- 2-agent architecture is viable
- Static context + pre-generated schemas = sufficient for Agent 1
- Simple Python orchestrator = sufficient for MVP
- Metadata-based document selection works (15-20 high-value docs selected)
- S3 availability rate confirmed (~57%)

**After MVP success, we can confidently decide**: What infrastructure (if any) to build next.

---

*This document supersedes time-based tracking (DAILY_PROGRESS.md).*
*Timing determined by user; progress tracked via GitHub issues and milestones.*
