# New Session Prompt: Phase 4 Implementation

**Use this exact prompt to start a new session for Phase 4 implementation**

---

## Context Summary

I'm continuing work on the **Patient Clinical Journey Timeline Framework** for the RADIANT PCA BRIM Analytics project. The framework creates per-patient clinical timelines by:

1. Loading WHO 2021 CNS tumor molecular classifications (already done for 9 patients)
2. Querying 6 Athena views for structured clinical data (visits, procedures, chemo, radiation, imaging, pathology)
3. Constructing a 7-stage stepwise timeline that validates treatments against WHO 2021 expected paradigms
4. Identifying extraction gaps (missing data)
5. **Extracting from binary documents using MedGemma** ← THIS IS WHAT WE NEED TO IMPLEMENT
6. Integrating extractions into timeline
7. Generating final JSON artifacts

**Phases 1-3 are COMPLETE and tested successfully.** We need to implement **Phase 4: MedGemma binary extraction**.

---

## What's Already Complete

### Infrastructure ✅
- **Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/`
- **Agents copied**: `agents/medgemma_agent.py` and `agents/binary_file_agent.py` from MVP
- **Working script**: `scripts/patient_timeline_abstraction_V1.py` (Phases 1-3 complete)
- **Test results**: Successfully ran on Pineoblastoma patient, generated 2,202 timeline events, identified 153 extraction gaps

### Documentation ✅ (150+ pages)
1. **STEPWISE_TIMELINE_CONSTRUCTION.md** (30 pages) - How the 7-stage timeline works
2. **IMAGING_REPORT_EXTRACTION_STRATEGY.md** (30 pages) - When/how to extract imaging reports
3. **MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md** (40 pages) - Two-agent architecture with 3 detailed prompt examples
4. **PHASE4_MEDGEMMA_IMPLEMENTATION_GUIDE.md** (45 pages) - Mock testing strategy
5. **PHASE4_READY_TO_IMPLEMENT.md** (15 pages) - Real MedGemma integration plan
6. **SESSION_COMPLETE_PHASE4_READY.md** - Complete implementation roadmap
7. **SESSION_SUMMARY_2025_10_30.md** - Comprehensive session summary

### Key Achievements ✅
- **7-stage stepwise timeline** following user requirement: "start with encounters/appointments, then procedures, then chemotherapy, then radiation (all after defining the molecular diagnosis)"
- **Protocol validation** at each stage against WHO 2021 expected treatments
- **Imaging diagnostic_report_ids** added for MedGemma targeting
- **153 extraction gaps identified** with `medgemma_target` fields for binary extraction

---

## What We Need to Implement Now

### Task: Create `patient_timeline_abstraction_V2.py` with real Phase 4

**File to create**: `scripts/patient_timeline_abstraction_V2.py`

**What it should do**:
1. Copy all code from `patient_timeline_abstraction_V1.py`
2. Add agent imports: `from agents import MedGemmaAgent, BinaryFileAgent`
3. Initialize agents in `__init__()`
4. Replace `_phase4_extract_from_binaries_placeholder()` with real implementation
5. Add 4 context-aware prompt generators
6. Add binary document fetching
7. Add extraction integration logic
8. Add CLI arg: `--max-extractions` for testing

---

## Critical Context from Previous Work

### 1. Existing MedGemma Infrastructure (MVP)

**MedGemmaAgent** (`agents/medgemma_agent.py`):
- Model: `gemma2:27b` via Ollama (http://localhost:11434)
- Temperature: 0.1 (deterministic extraction)
- JSON format output with retry logic
- Usage:
```python
agent = MedGemmaAgent(model_name="gemma2:27b", temperature=0.1)
result = agent.extract(prompt=context_aware_prompt)
# result.extracted_data contains parsed JSON
# result.confidence contains extraction confidence
```

**BinaryFileAgent** (`agents/binary_file_agent.py`):
- S3 bucket: `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`
- S3 prefix: `prd/source/Binary/`
- AWS profile: `radiant-prod`
- **CRITICAL BUG FIX**: FHIR Binary IDs use periods (.) but S3 files use underscores (_)
  - Example: `Binary/fmAXdcPPNkiCF9rr.5soVBQ` → `prd/source/Binary/fmAXdcPPNkiCF9rr_5soVBQ`
- Usage:
```python
agent = BinaryFileAgent(aws_profile="radiant-prod")
extracted = agent.fetch_and_extract_text(binary_id="Binary/xyz...")
# extracted.extracted_text contains full document text
```

### 2. WHO 2021 Classifications Already Done

**File**: `WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md`

Contains complete molecular classifications for 9 patients:
- 4 patients: Diffuse midline glioma, H3 K27-altered (WHO grade 4)
- 1 patient: Diffuse hemispheric glioma, H3 G34-mutant (WHO grade 4)
- 1 patient: Pineoblastoma, MYC/FOXR2-activated (WHO grade 4)
- 1 patient: Astrocytoma, IDH-mutant (WHO grade 3)
- 2 patients: Insufficient/no data

These are **embedded in the V1 script** as `WHO_2021_CLASSIFICATIONS` dictionary. DO NOT re-extract.

### 3. The 7-Stage Timeline (Phase 2)

**Stage 0**: Molecular diagnosis (WHO 2021 anchor) - establishes expected treatment paradigm
**Stage 1**: Encounters/appointments - validates care coordination
**Stage 2**: Procedures (surgeries) - validates against tumor biology
**Stage 3**: Chemotherapy episodes - validates regimen against WHO 2021 recommendations
**Stage 4**: Radiation episodes - validates dose/fields against WHO 2021 paradigms
**Stage 5**: Imaging studies - assesses surveillance adherence
**Stage 6**: Pathology granular records - links molecular findings to timeline

**Output example**:
```
Stage 0: Molecular diagnosis
  ✅ WHO 2021: Pineoblastoma, CNS WHO grade 4
Stage 1: Encounters/appointments
  ✅ Added 683 encounters/appointments
Stage 2: Procedures (surgeries)
  ✅ Added 11 surgical procedures
Stage 3: Chemotherapy episodes
  ✅ Added 42 chemotherapy episodes
  📋 Expected per WHO 2021: High-dose platinum-based
Stage 4: Radiation episodes
  ✅ Added 2 radiation episodes
  📋 Expected per WHO 2021: 54 Gy craniospinal + posterior fossa boost
Stage 5: Imaging studies
  ✅ Added 140 imaging studies
Stage 6: Pathology events (granular)
  ✅ Added 1309 pathology records
```

### 4. Gap Types Identified (Phase 3)

**153 extraction gaps** for Pineoblastoma patient:
- **11 missing_eor**: Surgeries without extent of resection
- **2 missing_radiation_dose**: Radiation episodes without total_dose_cgy
- **140 vague_imaging_conclusion**: Imaging reports with NULL/empty/short (<50 chars) conclusion text

Each gap has `medgemma_target` field (e.g., `DiagnosticReport/12345`) for binary extraction.

---

## Implementation Details

### Phase 4 Structure

```python
def _phase4_extract_from_binaries(self):
    """Real MedGemma extraction"""

    if not self.medgemma_agent or not self.binary_agent:
        print("  ⚠️  Ollama/MedGemma not available - skipping")
        return

    # Prioritize gaps (HIGHEST → HIGH → MEDIUM)
    prioritized_gaps = sorted(self.extraction_gaps, key=lambda x: ...)

    for gap in prioritized_gaps:
        # 1. Generate context-aware prompt (CLAUDE does this)
        prompt = self._generate_medgemma_prompt(gap)

        # 2. Fetch binary document from S3
        text = self._fetch_binary_document(gap['medgemma_target'])

        # 3. Call MedGemma
        result = self.medgemma_agent.extract(f"{prompt}\n\nDOCUMENT:\n{text}")

        # 4. Integrate into timeline
        self._integrate_extraction_into_timeline(gap, result.extracted_data)
```

### Context-Aware Prompt Example (Imaging Report)

```python
def _generate_imaging_prompt(self, gap: Dict) -> str:
    """Generate prompt based on WHO 2021 diagnosis + timeline phase"""

    who_dx = self.who_2021_classification.get('who_2021_diagnosis')

    # Calculate temporal context
    days_from_radiation = self._calculate_days_from_radiation(gap['event_date'])
    is_pseudoprogression_window = 21 <= days_from_radiation <= 90

    prompt = f"""You are extracting from a radiology report.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Imaging Date: {gap['event_date']}
- Imaging Modality: {gap['imaging_modality']}
"""

    if is_pseudoprogression_window:
        prompt += f"""
CRITICAL: This is {days_from_radiation} days post-radiation (PSEUDOPROGRESSION WINDOW).
Increased enhancement could be treatment effect OR true progression - detailed features critical.
"""

    prompt += """
EXTRACT (JSON):
{
  "lesions": [
    {
      "location": "string",
      "current_dimensions_cm": {"ap": float, "ml": float, "si": float},
      "prior_dimensions_cm": {"ap": float, "ml": float, "si": float} or null,
      "enhancement_pattern": "string"
    }
  ],
  "rano_assessment": {
    "new_lesions": "yes/no",
    "rano_category": "CR/PR/SD/PD/INDETERMINATE"
  },
  "extraction_confidence": "HIGH/MEDIUM/LOW"
}
"""
    return prompt
```

---

## Files You MUST Read First

1. **SESSION_COMPLETE_PHASE4_READY.md** - Complete implementation roadmap
2. **PHASE4_READY_TO_IMPLEMENT.md** - Real MedGemma integration plan
3. **MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md** - Architecture + 3 detailed prompt examples
4. **scripts/patient_timeline_abstraction_V1.py** - Base script to copy from

---

## Testing Plan

### Test 1: Verify Ollama (5 min)
```bash
ollama list  # Should show gemma2:27b
# If not: ollama pull gemma2:27b
```

### Test 2: Single Extraction (10 min)
```bash
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_test_single \
  --max-extractions 1
```
**Expected**: 1 imaging report extracted, timeline artifact enriched

### Test 3: High-Priority Only (20 min)
```bash
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_test_high_priority \
  --priority-filter HIGHEST
```

---

## Critical Requirements

### DO NOT:
- ❌ Re-extract WHO 2021 molecular classifications (already done, embedded in script)
- ❌ Guess at column names (use exact names from Athena_Schema_10302025.csv)
- ❌ Create a SQL view for Phase 4 (it's a per-patient Python workflow)
- ❌ Use mock MedGemma (use real gemma2:27b via Ollama)

### DO:
- ✅ Copy V1 script → V2
- ✅ Use existing MedGemmaAgent and BinaryFileAgent from `agents/`
- ✅ Generate context-aware prompts based on WHO 2021 diagnosis + timeline phase
- ✅ Fetch binaries from S3 (apply period→underscore conversion)
- ✅ Integrate extractions back into timeline events
- ✅ Test incrementally (1 extraction, then high-priority, then all)

---

## Expected Output After Implementation

### Timeline Artifact (Before MedGemma)
```json
{
  "event_type": "imaging",
  "event_date": "2023-08-15",
  "report_conclusion": "Increased enhancement",  // VAGUE
  "diagnostic_report_id": "DiagnosticReport/12345"
}
```

### Timeline Artifact (After MedGemma)
```json
{
  "event_type": "imaging",
  "event_date": "2023-08-15",
  "report_conclusion": "Increased enhancement",
  "diagnostic_report_id": "DiagnosticReport/12345",
  "medgemma_extraction": {  // ADDED BY PHASE 4
    "lesions": [
      {
        "location": "Pineal region",
        "current_dimensions_cm": {"ap": 3.2, "ml": 2.1, "si": 2.8},
        "prior_dimensions_cm": {"ap": 3.8, "ml": 2.5, "si": 3.1},
        "percent_change": -15.8,
        "enhancement_pattern": "Heterogeneous ring"
      }
    ],
    "rano_assessment": {
      "new_lesions": "no",
      "rano_category": "PR"
    },
    "extraction_confidence": "HIGH"
  }
}
```

---

## User's Critical Feedback (MUST FOLLOW)

From previous session:
1. ✅ "starting with encounters/appointments, then procedures, then chemotherapy, then radiation (all after defining the molecular diagnosis)" - IMPLEMENTED in 7-stage timeline
2. ✅ "don't forget that you/medgemma need extract the imaging report text from v_imaging" - diagnostic_report_ids ADDED
3. ✅ "molecular components should be abstracted as we did previously" - WHO_2021_CLASSIFICATIONS dict EMBEDDED
4. ✅ "we explicitly provided the schema file to ensure you would not guess" - Athena_Schema_10302025.csv USED
5. ✅ "you MUST follow stepwise processes that leverage the background materials" - extraction_priority field USED

---

## Estimated Implementation Time

**2-3 hours** to implement + test Phase 4:
- Copy V1 → V2 (5 min)
- Add agent initialization (15 min)
- Implement Phase 4 main loop (30 min)
- Implement 4 prompt generators (45 min)
- Implement binary fetching (15 min)
- Implement integration logic (30 min)
- Testing (30-60 min)

---

## Ready to Start?

Once you've read this prompt and the key documentation files, confirm:
1. ✅ Ollama is running (`ollama list`)
2. ✅ AWS SSO is logged in (`aws sso login --profile radiant-prod`)
3. ✅ You've read SESSION_COMPLETE_PHASE4_READY.md

Then start implementing `patient_timeline_abstraction_V2.py`!

---

**Last Updated**: 2025-10-31
**Session Goal**: Implement Phase 4 with real MedGemma integration
**Success Criteria**: Extract from ≥1 binary document, integrate into timeline, generate enriched JSON artifact
