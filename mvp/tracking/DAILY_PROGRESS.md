# MVP Daily Progress Tracker

**Goal**: Build 2-agent framework (Claude + MedGemma) with sufficient context for Agent 1

**Success Criteria**:
- ✅ Agent 1 knows all 27 view schemas without user input
- ✅ Agent 1 knows 35 BRIM variable definitions
- ✅ Agent 1 can orchestrate document selection → S3 check → Agent 2 extraction
- ✅ Extract 5 variables from patient C1277724 with >80% accuracy

---

## Week 1: MVP Build

### Day 1 (2025-10-19) - SETUP & CONTEXT

**Tasks**:
- [x] Create MVP directory structure
- [x] Design minimal context delivery mechanism
- [ ] Write `.claude/clinical-extraction/master-workflow.md`
- [ ] Write `.claude/clinical-extraction/variable-schema.md`
- [ ] Write `.claude/clinical-extraction/quick-reference.md`
- [ ] Generate all view schemas → `.claude/schemas/`
- [ ] Create `simple_orchestrator.py` with 4 core functions

**Completed**:
- MVP directory structure created
- Context delivery mechanism designed (Static + Pre-generated + Runtime)

**Blockers**: None

**Tomorrow**: Finish context files, build orchestrator

---

### Day 2 (2025-10-20) - ORCHESTRATOR

**Tasks**:
- [ ] Complete `simple_orchestrator.py`
- [ ] Test Athena queries
- [ ] Test S3 binary file retrieval
- [ ] Test MedGemma subprocess call
- [ ] Unit tests for each function

**Expected Completion**: 4 working Python functions

---

### Day 3 (2025-10-21) - END-TO-END TEST

**Tasks**:
- [ ] Agent 1 queries patient C1277724 timeline
- [ ] Agent 1 selects 3 pathology documents
- [ ] Agent 1 checks S3 availability
- [ ] Agent 1 extracts text from 1 document
- [ ] Agent 1 calls Agent 2 to extract "primary_diagnosis"

**Expected Output**: JSON with extracted variable

---

### Day 4 (2025-10-22) - EXPAND & VALIDATE

**Tasks**:
- [ ] Extract 5 variables: primary_diagnosis, who_grade, surgery_date, tumor_location, chemotherapy_agent
- [ ] Compare against GOLD_STANDARD_C1277724.md
- [ ] Measure accuracy, latency, cost
- [ ] Document what worked, what didn't

**Expected Metrics**:
- Accuracy: >80% (4/5 variables correct)
- Latency: <60 seconds total
- Cost: <$0.50 for Claude API calls

---

### Day 5 (2025-10-23) - RETROSPECTIVE

**Tasks**:
- [ ] Write retrospective: What worked, what didn't
- [ ] Identify gaps in Agent 1 context
- [ ] Decide: Does Agent 1 need more context? Different format?
- [ ] Decide: Is Python orchestrator sufficient or do we need MCP?
- [ ] Plan Week 2 based on learnings

---

## Metrics Dashboard

### Context Delivery
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Agent 1 startup time | <5 sec | TBD | ⏳ |
| Static context size | <20K tokens | TBD | ⏳ |
| Schema lookup time | <2 sec | TBD | ⏳ |
| Context sufficiency | 100% (no user input needed) | TBD | ⏳ |

### Extraction Performance
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Variables extracted | 5 | TBD | ⏳ |
| Accuracy vs gold standard | >80% | TBD | ⏳ |
| Total processing time | <60 sec | TBD | ⏳ |
| Cost per patient | <$0.50 | TBD | ⏳ |

### Technical Validation
| Question | Answer | Status |
|----------|--------|--------|
| Is static context sufficient? | TBD | ⏳ |
| Do we need RAG? | TBD | ⏳ |
| Do we need MCP? | TBD | ⏳ |
| Can Python handle orchestration? | TBD | ⏳ |

---

## Open Questions

1. **Context Format**: Is markdown sufficient or do we need structured JSON?
2. **Schema Freshness**: How often do views change? Can we rely on pre-generated schemas?
3. **Document Selection**: Can Agent 1 write good SQL filters or does it need examples?
4. **Agent 2 Prompts**: What prompt engineering is needed for MedGemma?
5. **Error Handling**: What happens when documents are missing from S3?

---

## Decisions Made

| Decision | Rationale | Date |
|----------|-----------|------|
| Use static .claude/ files for workflows | Zero infrastructure, auto-loads | 2025-10-19 |
| Pre-generate schema docs | Fresh enough, no Athena costs | 2025-10-19 |
| Python-only for MVP | Simpler than TypeScript + MCP | 2025-10-19 |
| Target 5 variables for Day 4 | Enough to validate approach | 2025-10-19 |

---

## Risks & Mitigation

| Risk | Impact | Mitigation | Owner |
|------|--------|------------|-------|
| Static context too limited | Agent 1 can't operate autonomously | Add schema lookup helper function | TBD |
| MedGemma extraction quality low | Variables incorrectly extracted | Compare vs Claude API extraction | TBD |
| S3 availability blocks workflow | Can't access documents | Implement fallback document selection | TBD |
| Context becomes stale | Agent 1 uses outdated schemas | Automated schema regeneration script | TBD |

---

## Next Week Preview (IF MVP succeeds)

### Week 2: Decide & Enhance
- **Option A (Python works)**: Extend orchestrator, add 10 more variables
- **Option B (Context insufficient)**: Add lightweight schema caching
- **Option C (MedGemma struggles)**: Try Claude API for extraction comparison
- **Option D (All good)**: Scale to 10 patients batch processing

---

**Last Updated**: 2025-10-19 (Day 1)
**Next Update**: 2025-10-20 (Day 2)
