# ⭐ START NEW SESSION HERE ⭐

**For continuing Phase 4 implementation**

---

## Quick Start (30 seconds)

**Paste this into new Claude Code session**:

```
I'm continuing work on the Patient Clinical Journey Timeline Framework for RADIANT PCA.

Read this file for complete context:
/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/NEW_SESSION_PROMPT.md

Summary: Implement Phase 4 (MedGemma binary extraction) in patient_timeline_abstraction_V2.py.
All infrastructure ready (agents copied, docs complete, V1 tested). Just need to implement extraction loop.

Working directory: /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/
```

---

## What You'll Be Implementing

**File to create**: `scripts/patient_timeline_abstraction_V2.py`

**Time estimate**: 2-3 hours

**What it does**:
1. Copy all code from `patient_timeline_abstraction_V1.py` (Phases 1-3 working)
2. Add real MedGemma integration for Phase 4
3. Generate context-aware prompts based on WHO 2021 diagnosis + timeline phase
4. Fetch binary documents from S3
5. Extract structured data using MedGemma (gemma2:27b)
6. Integrate extractions back into timeline
7. Output enriched JSON artifacts

---

## Status Check

### ✅ Complete
- Phases 1-3 working (7-stage timeline, gap identification)
- Agents copied (`medgemma_agent.py`, `binary_file_agent.py`)
- 150+ pages of documentation
- Tested on Pineoblastoma patient: 2,202 events, 153 gaps identified

### ⬜ To Do
- Verify Ollama running: `ollama list` (should show `gemma2:27b`)
- Verify AWS SSO: `aws sso login --profile radiant-prod`
- Implement V2 script with Phase 4
- Test incrementally

---

## Key Files to Reference

1. **NEW_SESSION_PROMPT.md** ⭐ (Complete context - READ FIRST)
2. **SESSION_COMPLETE_PHASE4_READY.md** (Implementation roadmap)
3. **PHASE4_READY_TO_IMPLEMENT.md** (Real MedGemma integration plan)
4. **MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md** (Prompt examples)
5. **scripts/patient_timeline_abstraction_V1.py** (Base to copy from)

---

## Test Plan

```bash
# Test 1: Single extraction (10 min)
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_test_single \
  --max-extractions 1

# Test 2: High-priority only (20 min)
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_test_high_priority \
  --priority-filter HIGHEST

# Test 3: All 153 gaps (60-90 min)
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_full
```

---

## Critical Don'ts

- ❌ Don't re-extract WHO 2021 classifications (already done, embedded in script)
- ❌ Don't create SQL view (it's a Python workflow)
- ❌ Don't use mock MedGemma (use real gemma2:27b)
- ❌ Don't guess column names (they're in Athena_Schema_10302025.csv)

---

## If Stuck

1. Read NEW_SESSION_PROMPT.md for complete context
2. Check MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md for prompt examples
3. Review V1 script to understand existing structure
4. Ask user for clarification

---

**Last Updated**: 2025-10-31
**Next Action**: Read NEW_SESSION_PROMPT.md and start implementing V2
