# Multi-Agent Framework Branch

## Branch Information
- **Branch Name**: `feature/multi-agent-framework`
- **Created**: 2025-10-16
- **Branched From**: `feature/full-dictionary-extraction` (commit 80e07a7)

## Objective

Implement a multi-agent architecture where **Claude acts as Master Orchestrator** and **MedGemma acts as Medical Extraction Agent**, enabling iterative dialogue, intelligent adjudication, and scalable extraction across the full CBTN data dictionary (345 fields).

## Inherited Components

This branch inherits all completed work from the parent branch:

### ✅ 5-Phase Architecture
- **Phase 1**: Comprehensive structured data harvesting
- **Phase 2**: Clinical timeline construction
- **Phase 3**: Three-tier document selection (±7d, ±14d, ±30d)
- **Phase 4**: Enhanced LLM extraction with structured context
- **Phase 5**: Cross-source validation

### ✅ 4-Pass Iterative Extraction
- **Pass 1**: Document-based LLM extraction
- **Pass 2**: Structured data interrogation
- **Pass 3**: Cross-source validation
- **Pass 4**: Temporal reasoning

### ✅ Data Dictionary Integration
- CBTN data dictionary loader (345 fields)
- Dynamic field definition lookup for LLM prompts
- Valid value enforcement

### ✅ Structured Context Propagation
- Phase 1 & 2 data available to LLM
- Schema information for 6 materialized views
- Variable-specific validation hints

### ✅ Gold Standard Hierarchies
- Post-op imaging (24-72h): 0.95 confidence
- Diagnosis sources: Pathology (0.90) > ICD-10 (0.70) > Problem list (0.50)
- Surgery classification: tumor_resection, csf_diversion, biopsy, other

## What's New: Multi-Agent Framework

### Architecture

```
┌─────────────────────────────────────────────┐
│      MASTER AGENT (Claude Sonnet 4.5)      │
│  • Orchestration & quality control          │
│  • Conflict adjudication                    │
│  • Data dictionary enforcement              │
│  • Strategic planning                       │
└─────────────────────────────────────────────┘
                    ↓
          Dialogue Protocol
                    ↓
┌─────────────────────────────────────────────┐
│   MEDICAL EXTRACTION AGENT (MedGemma 27B)  │
│  • Document reading & comprehension          │
│  • Medical terminology understanding         │
│  • Responds to targeted questions           │
└─────────────────────────────────────────────┘
```

### Key Features

1. **Iterative Dialogue**
   - Master agent can request clarification
   - Medical agent responds to follow-up questions
   - Multiple rounds until confidence threshold met

2. **Intelligent Adjudication**
   - Master applies rules + reasoning for conflicts
   - Can handle edge cases not covered by hardcoded logic
   - Adaptive strategy per patient complexity

3. **Data Dictionary Enforcement**
   - Master validates all extractions against data dictionary
   - Requests remapping if LLM returns invalid codes
   - Ensures CBTN compliance

4. **Full Audit Trail**
   - Complete dialogue history for clinical review
   - Transparent reasoning chain
   - Reproducible decision-making

## Implementation Plan

### Phase 1: Core Framework (Week 1-2)
- [ ] Implement MasterAgent class
- [ ] Create MedicalExtractionAgent wrapper
- [ ] Design dialogue protocol (message types)
- [ ] Implement DialogueManager

### Phase 2: Dialogue Capabilities (Week 2-3)
- [ ] Follow-up question generation
- [ ] Targeted clarification requests
- [ ] Validation request workflows
- [ ] Conflict adjudication logic

### Phase 3: Integration (Week 3-4)
- [ ] Integrate with existing Phases 1-5
- [ ] Replace Phase 4 single-pass with dialogue loop
- [ ] Update Phase 5 validation
- [ ] Add comprehensive logging

### Phase 4: Testing (Week 4-5)
- [ ] Test on pilot patient
- [ ] Compare vs single-agent baseline
- [ ] Optimize dialogue efficiency
- [ ] Tune confidence thresholds

### Phase 5: Scale Testing (Week 5-6)
- [ ] Test on 10 patients
- [ ] Measure accuracy improvement
- [ ] Assess computational cost
- [ ] Document edge cases

## File Structure

```
local_llm_extraction/
├── multi_agent/                    (NEW)
│   ├── master_agent.py            # Claude orchestrator
│   ├── medical_extraction_agent.py # MedGemma wrapper
│   ├── dialogue_manager.py        # Dialogue state
│   └── message_protocol.py        # Message types
│
├── event_based_extraction/         (EXISTING - will integrate)
│   ├── phase1_enhanced_structured_harvester.py
│   ├── phase2_timeline_builder.py
│   ├── phase3_document_selector.py
│   ├── phase4_iterative_llm_extraction.py
│   └── phase5_cross_source_validation.py
│
├── iterative_extraction/           (EXISTING - will enhance)
│   ├── pass2_structured_query.py
│   ├── pass3_cross_validation.py
│   └── pass4_temporal_reasoning.py
│
└── utils/                          (EXISTING)
    └── data_dictionary_loader.py
```

## Testing Strategy

### Baseline Comparison
Test the same patient (e4BwD8ZYDBccepXcJ.Ilo3w3) with both approaches:
- **Single-Agent** (current): 1 LLM call per variable
- **Multi-Agent** (new): Iterative dialogue until confident

### Success Metrics
- **Extraction Accuracy**: % of correct extractions
- **Manual Review Rate**: % needing human review
- **Confidence Scores**: Average confidence per variable
- **Dialogue Efficiency**: Average turns per extraction
- **Computational Cost**: Total LLM calls and time

### Expected Improvements
- Accuracy: +10-20%
- Manual review: -20-30% (from 43% to ~15-20%)
- Audit trail: Full dialogue history

## Documentation

- **Proposal**: `/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/MULTI_AGENT_FRAMEWORK_PROPOSAL.md`
- **Current State**: `CURRENT_STATE_BEFORE_MULTI_AGENT_BRANCH.md`
- **Implementation Guide**: (to be created)

## Running the Current Baseline

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction
python test_context_aware_pipeline.py
```

Output: `extraction_results_{patient_id}_{timestamp}.json`

## Next Steps

1. Create `multi_agent/` directory structure
2. Implement MasterAgent class with adjudication logic
3. Create MedicalExtractionAgent wrapper for Ollama
4. Design and test dialogue protocol
5. Integrate with existing Phase 4 extraction

---

**Status**: Ready for development
**Documentation**: See MULTI_AGENT_FRAMEWORK_PROPOSAL.md for detailed architecture
