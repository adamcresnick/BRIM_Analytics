# 2-Agent Clinical Data Extraction Framework - Comprehensive Infrastructure Plan

**Date**: 2025-10-19
**Version**: 1.0
**Authors**: Claude (Agent 1 Orchestrator) + User (Domain Expert)
**Project**: BRIM Analytics - Pediatric Brain Tumor Clinical Data Extraction

---

## Executive Summary

After deep analysis of available technologies (MCP, RAG, open-source clinical extraction frameworks), current infrastructure, and project requirements, this document presents a comprehensive architecture for a **2-agent clinical data extraction framework** that combines:

1. **Agent 1 (Claude - Master Orchestrator)**: Uses MCP servers for context management + RAG for dynamic knowledge retrieval
2. **Agent 2 (MedGemma/Ollama - Extraction Specialist)**: Integrated via MCP with structured data query capability
3. **Unified Context Layer**: Custom MCP server providing schema metadata, documentation, and runtime state

This framework enables Agent 1 to have complete context about workflows, database schemas, document classification, patient timelines, and extraction best practices—all without requiring the user to manually provide this information each session.

---

## Key Architecture Decisions

### 1. **MCP-Based Infrastructure** (vs REST APIs)
- Context persistence across requests
- Native Claude Code tool discovery
- Industry standard (OpenAI, Google adopted in 2025)
- Multiple servers run simultaneously

### 2. **RAG for Documentation** (vs static context dump)
- Only retrieve relevant docs per query (~5K tokens vs 500K)
- Semantic search over 50+ .md files
- Scalable to unlimited documentation

### 3. **Hybrid Context Management**
- **Static** (.claude/ files): Core workflows, variable schemas
- **Dynamic** (RAG): Example queries, detailed documentation
- **Real-time** (MCP): Patient data, schema metadata, S3 content

### 4. **MedGemma as MCP Server** (vs direct subprocess)
- Agent 1 treats as abstract "extraction tool"
- Centralized retry logic and error handling
- Future-proof: Can swap Ollama → other LLMs without changing Agent 1

---

## Proposed MCP Servers

### 1. FHIR Metadata MCP Server (NEW - TypeScript)
**Tools:**
- `get_view_schema(view_name)` → columns, types, descriptions
- `query_patient_timeline(patient_id)` → surgeries, meds, imaging dates
- `get_sample_documents(practice_setting, limit)` → example records
- `get_temporal_window_docs(patient_id, event_type, date)` → filtered binary files

### 2. MedGemma Extraction MCP Server (NEW - Python)
**Tools:**
- `extract_variable(variable_name, document_text, context)` → {value, confidence}
- `extract_batch(variable_list, document_text)` → multiple variables
- Integrates existing `StructuredDataQueryEngine` for cross-referencing

### 3. Documentation RAG MCP Server (NEW - Python)
**Tools:**
- `search_documentation(query, top_k)` → relevant sections from .md files
- `get_workflow_guide(workflow_name)` → complete workflow docs
- Vector DB: ChromaDB with `sentence-transformers/all-MiniLM-L6-v2`

### 4. Enhanced Athena Data MCP Server (EXPAND EXISTING)
**New Tools:**
- `get_s3_binary_content(binary_id)` → extracted text (HTML/RTF/PDF)
- `check_s3_availability(binary_ids[])` → availability status
- `get_athena_query_stats(query_id)` → performance metrics
- AWS Glue integration for schema management

---

## Agent 1 Workflow

```
User Request → Agent 1 (Claude)
  ↓
[Load Static Context from .claude/clinical-extraction/]
  ↓
[Query RAG: "How do I select pathology reports?"]
  ↓
[MCP: query_patient_timeline(patient_id)] → surgeries, meds, imaging dates
  ↓
[MCP: get_temporal_window_docs()] → filter v_binary_files
  ↓
[MCP: check_s3_availability()] → verify documents exist
  ↓
[MCP: get_s3_binary_content()] → extract text from PDFs/HTML/RTF
  ↓
[MCP: extract_variable()] → Agent 2 (MedGemma) extracts clinical data
  ↓
[Validate against structured data]
  ↓
[Output BRIM CSV]
```

---

## Implementation Plan

### Phase 1: MCP Infrastructure (Weeks 1-2)
1. Create `fhir-metadata-mcp-server` (TypeScript)
2. Create `medgemma-extraction-mcp-server` (Python)
3. Create `documentation-rag-mcp-server` (Python)
4. Enhance `radiant-unified` MCP server with S3/Glue tools

### Phase 2: Context Files (Week 3)
1. Create `.claude/clinical-extraction/` directory
2. Write `master-orchestrator.md` (Agent 1 instructions)
3. Write `variable-schema.md` (35 BRIM variables)
4. Write `document-selection-workflow.md` (metadata filtering)
5. Write `extraction-workflow.md` (Agent 2 integration)
6. Write `validation-rules.md` (cross-referencing rules)

### Phase 3: Integration & Testing (Week 4)
1. End-to-end test with patient C1277724
2. Measure extraction accuracy vs gold standard
3. Performance benchmarking (time, cost, throughput)
4. Error handling (missing docs, Ollama timeouts, ambiguous values)

### Phase 4: Scaling (Weeks 5-6)
1. Batch processing for 10+ patients
2. Parallel Agent 2 calls
3. Caching for repeated queries
4. Cost optimization

---

## Expected Outcomes

### Context Management
- **Agent 1 start time**: <5 seconds (vs 30+ seconds manual)
- **Relevant context precision**: 95%+ (vs ~70% manual)
- **Schema awareness**: 100% automatic (vs 0% manual)

### Extraction Quality
- **Variable coverage**: 32/35 (91%) vs 20/35 (57%) with random docs
- **Documents/patient**: 15-20 vs 40-84 previously
- **Document precision**: 80-95% (metadata filters) vs ~50% (random)
- **Extraction accuracy**: 85-95% (with cross-referencing)

### Performance
- **Processing time**: 5-10 minutes/patient
- **Cost**: $0.10-0.50/patient (Claude API only, Ollama is free)
- **Throughput**: 100+ patients/day (single machine)

---

## Comparison to Open Source Solutions

### vs Microsoft Text Analytics for Health
- ✅ **Cost**: $0.10-0.50/patient vs $1/1K text records
- ✅ **Privacy**: Local MedGemma vs cloud PHI processing
- ✅ **Customization**: Domain-specific brain tumor extraction

### vs NLP2FHIR Pipeline
- ✅ **Accuracy**: 0.85-0.95 for targeted variables vs 0.69-0.99 generic
- ✅ **Structured Data Integration**: Full cross-referencing capability

### vs LLM-AIx (Oncology Extraction)
- ✅ **Automation**: Metadata-based document selection (vs manual)
- ✅ **Validation**: Structured data cross-referencing layer

---

## Risk Mitigation

### Risk 1: S3 Availability (43% missing documents)
**Mitigation**: Fallback document selection, structured data prioritization
**Expected**: >75% availability after fallback

### Risk 2: Ollama Timeouts
**Mitigation**: 60s timeout, 3 retries with exponential backoff, fallback to Claude API
**Expected**: <5% failure rate

### Risk 3: RAG Precision
**Mitigation**: Relevance threshold >0.7, fallback to static docs
**Expected**: >90% precision for top-3 results

### Risk 4: MCP Server Downtime
**Mitigation**: Health checks, graceful degradation, auto-restart
**Expected**: <1% downtime, <5min recovery

---

## Files to Create

```
RADIANT_PCA/
├── mcp-servers/
│   ├── fhir-metadata-server/          (NEW - TypeScript)
│   ├── medgemma-extraction-server/    (NEW - Python)
│   └── documentation-rag-server/      (NEW - Python)
│
├── .claude/
│   └── clinical-extraction/            (NEW - Markdown)
│       ├── master-orchestrator.md
│       ├── variable-schema.md
│       ├── document-selection-workflow.md
│       ├── extraction-workflow.md
│       └── validation-rules.md
│
└── BRIM_Analytics/
    ├── orchestrator/                   (NEW - Python)
    │   ├── agent1_coordinator.py
    │   ├── batch_processor.py
    │   └── validation.py
    │
    └── TWO_AGENT_FRAMEWORK_ARCHITECTURE_PLAN.md  (THIS FILE)
```

---

## Future Enhancements

### Phase 5: Multi-Modal Document Processing
- Extract data from images (radiographs, pathology slides)
- AWS Textract or Tesseract OCR integration
- **Impact**: +5-10% variable coverage

### Phase 6: Active Learning for Document Selection
- Learn which documents successfully extract variable X
- Build classifier: Document metadata → P(contains variable X)
- **Impact**: 50% reduction in documents needed

### Phase 7: Multi-Patient Batch Optimization
- Distributed processing (AWS Batch, EMR)
- Parallel Agent 2 calls across multiple GPUs
- **Impact**: 100× throughput (1000 patients/day)

### Phase 8: Real-Time Extraction for Clinical Care
- Trigger extraction on new EHR data arrival (FHIR webhook)
- **Impact**: <5 minute extraction for clinical decision support

---

## Conclusion

This architecture provides Agent 1 (Claude) with:
- ✅ Complete schema knowledge (via FHIR Metadata MCP)
- ✅ Historical context (via RAG)
- ✅ Real-time patient data (via Athena MCP)
- ✅ Document classification metadata (via FHIR Metadata MCP)
- ✅ Extraction capability (via MedGemma MCP)
- ✅ Workflow orchestration (via static context files)

**All without requiring the user to manually provide schemas, documentation, or workflows each session.**

The framework is:
- **Scalable**: 100+ patients/day
- **Cost-effective**: $0.10-0.50/patient
- **Privacy-preserving**: Local MedGemma, no PHI to cloud
- **Future-proof**: MCP industry standard, swappable LLMs
- **Accurate**: 85-95% extraction accuracy with 91% variable coverage

---

**Ready for Implementation**

**Next Steps**:
1. Review and approve architecture
2. Begin Phase 1 implementation (MCP servers)
3. Establish CI/CD pipeline for MCP server deployment
4. Create project board for tracking implementation tasks
