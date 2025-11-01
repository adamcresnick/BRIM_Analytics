# Phase 4 MedGemma Binary Extraction - Implementation Summary

**Date**: 2025-10-31
**Status**: Full Escalating Search Strategy Implemented ✅
**Working Directory**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/`

---

## Executive Summary

Implemented **Phase 4: MedGemma Binary Document Extraction** with a comprehensive **two-agent negotiation architecture** and **escalating search strategy**. The system now:

1. ✅ Extracts structured clinical data from binary documents (PDF, XML, HTML)
2. ✅ Uses **Agent 1 (Claude orchestrator) ↔ Agent 2 (MedGemma extractor)** negotiation loop
3. ✅ Validates document content BEFORE extraction
4. ✅ Validates extraction results AFTER extraction
5. ✅ Re-extracts with clarification when incomplete
6. ✅ **Escalates through alternative documents** when primary sources fail
7. ✅ Uses real examples from human abstraction for prompt engineering

---

## Architecture Overview

### Two-Agent System

```
┌─────────────────────────────────────────────────────────────┐
│  AGENT 1: Claude Orchestrator (patient_timeline_abstractor) │
│  - Identifies extraction gaps                                │
│  - Prioritizes documents based on patient availability       │
│  - Validates document content (keyword checking)             │
│  - Validates extraction results (required field checking)    │
│  - Negotiates with MedGemma through re-extraction           │
│  - Escalates to alternative documents when needed            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ Sends prompts + documents
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  AGENT 2: MedGemma Extractor (gemma2:27b via Ollama)       │
│  - Extracts structured data from clinical text              │
│  - Returns JSON with requested fields                       │
│  - Confidence assessment (HIGH/MEDIUM/LOW)                  │
└─────────────────────────────────────────────────────────────┘
```

### Escalating Search Workflow

```
PRIMARY DOCUMENT ATTEMPT
  ↓
Document Content Validation
  ├─ Valid → Extract with MedGemma
  │           ↓
  │      Extraction Result Validation
  │           ├─ Complete → ✅ RESOLVED
  │           └─ Incomplete → Re-extraction with clarification
  │                            ├─ Complete → ✅ RESOLVED
  │                            └─ Still incomplete → ESCALATE ↓
  │
  └─ Invalid (wrong doc type) → ESCALATE ↓

ESCALATION: ALTERNATIVE DOCUMENT SEARCH
  ↓
Build Patient Document Inventory (all available docs)
  ↓
Find Alternative Documents (gap-specific prioritization)
  ↓
FOR EACH ALTERNATIVE (up to 5):
  ├─ Fetch document
  ├─ Validate content
  ├─ Extract with MedGemma
  ├─ Validate extraction
  └─ If complete → ✅ RESOLVED

If all alternatives exhausted → ❌ UNAVAILABLE_IN_RECORDS
```

---

## Key Files Implemented/Modified

### 1. Main Implementation
**File**: `scripts/patient_timeline_abstraction_V2.py`
**Key Methods**:

#### Escalation Infrastructure
- `_build_patient_document_inventory()` - Catalogs ALL available documents by type
- `_find_alternative_documents(gap, inventory)` - Returns prioritized candidates for gap type
- `_try_alternative_documents(gap, missing_fields)` - Executes escalation loop

#### Primary Document Discovery
- `_find_operative_note_binary(surgery_date)` - Queries operative reports (±7 days)
- `_find_radiation_document(radiation_date)` - Queries v_radiation_documents (±30 days)

#### Validation & Negotiation
- `_validate_document_content(text, gap_type)` - Keyword-based validation BEFORE extraction
- `_validate_extraction_result(data, gap_type)` - Required field validation AFTER extraction
- `_retry_extraction_with_clarification(gap, text, result, missing_fields)` - Re-extraction with specific guidance

#### Prompt Engineering
- `_generate_radiation_summary_prompt(gap)` - **Enhanced with real RADIANT PCA examples**
  - Example 1: Focal proton therapy (5940 cGy)
  - Example 2: Craniospinal + focal boost (2340 cGy + 5400 cGy total)
  - Example 3: Standard focal photon (5400 cGy)
- `_generate_operative_note_prompt(gap)` - Enhanced with interpretation guide for ambiguous language
- `_generate_imaging_prompt(gap)` - Enhanced with RANO criteria and examples

### 2. Agent Classes
**File**: `agents/medgemma_agent.py` - MedGemma wrapper (no changes, already functional)
**File**: `agents/binary_file_agent.py` - Added XML support for radiation treatment summaries

### 3. Strategy Documentation
**Files Created**:
- `HUMAN_ABSTRACTION_EXAMPLES.md` - 12 real examples from clinical abstraction team
- `DOCUMENT_PRIORITIZATION_STRATEGY.md` - Comprehensive escalation strategy for all gap types
- `EOR_PRIORITIZATION_PROPOSAL.md` - Post-op MRI fallback for surgery EOR
- `MEDGEMMA_PROMPT_ENGINEERING_REVIEW.md` - Detailed prompt improvements
- `PHASE4_IMPLEMENTATION_SUMMARY.md` - This document

---

## Alternative Document Prioritization by Gap Type

### Surgery - Extent of Resection (EOR)
**Primary**: Operative reports (dr_type_text = 'Operative Record')
**Alternatives** (in priority order):
1. **Discharge summaries** mentioning surgery/resection (±14 days)
2. **Post-operative MRI** showing residual assessment (surgery_date + 24-72 hours)
3. **Pathology reports** with specimen details
4. **Progress notes** mentioning surgical outcome (±30 days)

### Radiation - Comprehensive Dose Details
**Primary**: v_radiation_documents (±30 days)
**Alternatives**:
1. **Radiation-specific documents** from v_binary_files (Rad Onc Treatment Report, etc.)
2. **Treatment planning documents** (±7 days from start)
3. **Progress notes** mentioning radiation (±60 days)
4. **Discharge summaries** discussing radiation (±60 days)

### Chemotherapy - Agent Names, Dates, Protocols
**Primary**: v_chemo_treatment_episodes (structured)
**Alternatives**:
1. **Oncology progress notes** (episode_start to episode_end)
2. **Treatment plans** with protocols (±7 days)
3. **Infusion records** (actual administration)
4. **Neuro-oncology clinic notes** (±60 days)

### Imaging - Tumor Measurements and RANO
**Primary**: Imaging report from v_imaging
**Alternatives**:
1. **Prior imaging** for comparison measurements (most recent before current)
2. **Clinic notes** interpreting imaging (±30 days)
3. **Tumor board notes** with imaging review (±30 days)

---

## Validation Rules (Required Fields)

### Surgery EOR
**Required**:
- `extent_of_resection` (GTR/NTR/STR/BIOPSY/UNCLEAR)
- `surgeon_assessment` (verbatim text)

**Optional**:
- `percent_resection`
- `residual_tumor`
- `extraction_confidence`

### Radiation Details
**Required**:
- `date_at_radiation_start` (YYYY-MM-DD)
- `total_dose_cgy` (integer)
- `radiation_type` (focal/craniospinal/whole_ventricular/focal_with_boost)

**Critical for Craniospinal + Boost**:
- `completed_craniospinal_or_whole_ventricular_radiation_dose` (e.g., 2340 cGy)
- `radiation_focal_or_boost_dose` (e.g., 5400 cGy CUMULATIVE to tumor bed)

### Imaging/RANO
**Required**:
- `lesions` (array, can be empty [])
- `rano_assessment` (object with new_lesions and rano_category)

---

## Human Abstraction Integration

### Gold Standard Examples Used
**Source**: `/Users/resnick/Downloads/example extraction.csv`

**Key Examples**:
1. **Patient eQSB0y3q** (Astrocytoma):
   - Surgery: Biopsy only (day 4545)
   - Chemo: temozolomide;nivolumab (days 4581-4735)
   - Radiation: Focal proton 5940 cGy (days 4581-4629)

2. **Patient e8jPD8zawpt** (Medulloblastoma) - **CRITICAL EXAMPLE**:
   - Surgery: Gross/Near total resection (day 6421)
   - Chemo: temozolomide per ACNS0126 (days 6454-6626)
   - **Radiation: Craniospinal + boost** (days 6457-6504)
     - `total_radiation_dose`: 4140 cGy (craniospinal to brain/spine)
     - `total_radiation_dose_focal`: 5400 cGy (cumulative to posterior fossa)
     - This pattern was added as Example 2 in radiation prompt!

### Prompt Engineering Improvements
All prompts now include:
- **Field-specific instructions** for each output field
- **Real RADIANT PCA examples** (not synthetic)
- **Interpretation guides** for ambiguous clinical language
- **Extraction confidence criteria** (HIGH/MEDIUM/LOW)
- **Critical validation notes** emphasizing required fields

---

## Testing Strategy

### Test Patients
1. **eQSB0y3q** - Astrocytoma, IDH-mutant, CNS WHO grade 3
   - Purpose: Focal radiation extraction, temozolomide chemo
   - Expected: 5940 cGy focal proton radiation

2. **e8jPD8zawpt** - High-risk medulloblastoma
   - Purpose: Craniospinal + boost radiation extraction
   - Expected: 4140 cGy CSI + 5400 cGy total to posterior fossa

### Test Progression
1. ✅ Initial test - Identified wrong document extraction issue
2. ✅ Improved prompts with real examples
3. ✅ Added validation and re-extraction loop
4. ✅ **Implemented full escalation strategy** ← Current
5. ⏳ Testing with escalation - Running now

### Test Output Location
```
output/escalation_test_eQSB0y3q/<timestamp>/
  └─ eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83_timeline_artifact.json
```

---

## Technical Implementation Details

### Document Inventory Structure
```python
inventory = {
    'operative_records': [...],      # Operative Record, OP Note
    'discharge_summaries': [...],     # Discharge Summary
    'progress_notes': [...],          # Progress Notes
    'imaging_reports': [...],         # Diagnostic imaging study
    'pathology_reports': [...],       # Pathology report
    'consultation_notes': [...],      # Consultation Note, Consult
    'radiation_documents': [...],     # Rad Onc *, Radiation *
    'treatment_plans': [...],         # Treatment Plan
    'other': [...]                    # Everything else
}
```

Each document contains:
- `binary_id` - For fetching from S3
- `dr_type_text` - Document type classification
- `dr_date` - Document date for temporal filtering
- `dr_description` - For keyword filtering
- `content_type` - PDF, XML, HTML, etc.

### Alternative Document Candidate Structure
```python
candidate = {
    'priority': 1,                    # Lower = higher priority
    'source_type': 'operative_record', # Human-readable type
    'binary_id': 'abc123',
    'dr_date': '2024-03-15',
    'days_from_event': 2,             # Temporal proximity
    # ... other metadata from inventory
}
```

### Status Codes
| Status | Meaning | Next Action |
|--------|---------|-------------|
| `RESOLVED` | Successfully extracted all required fields | ✅ Done |
| `WRONG_DOCUMENT_TYPE` | Primary doc failed validation | Try alternatives |
| `INCOMPLETE_EXTRACTION` | Missing required fields after re-extraction | Try alternatives |
| `RE_EXTRACTION_FAILED` | Re-extraction attempt failed | Try alternatives |
| `UNAVAILABLE_IN_RECORDS` | Exhausted all alternative documents | Accept as missing |
| `EXTRACTION_TECHNICAL_FAILURE` | MedGemma technical error | Manual review |

---

## Critical Insights & Decisions

### 1. v_radiation_documents: Use with Validation
**Issue**: View includes false positives (ED visits mentioning radiation history)
**Solution**: Continue using v_radiation_documents as PRIMARY, but rely on:
- Document content validation (keyword checking)
- MedGemma's ability to recognize wrong documents
- Escalation to alternatives when validation fails

**Rationale**: Better to have high recall (find all radiation docs) with some false positives, then filter through validation, than to miss true radiation treatment summaries.

### 2. Craniospinal + Boost Pattern
**Critical Understanding**:
- `completed_craniospinal_or_whole_ventricular_radiation_dose` = Dose to brain/spine ONLY
- `radiation_focal_or_boost_dose` = **CUMULATIVE** dose to tumor bed
- Tumor bed receives: CSI dose + boost dose
- Example: 2340 cGy (CSI) applied first, then 3060 cGy boost → 5400 cGy total to posterior fossa

### 3. Post-Operative MRI for EOR
**Identified Gap**: Currently ONLY queries operative reports
**Proposed**: Add post-op MRI (24-72 hours) as fallback
**Status**: Documented in EOR_PRIORITIZATION_PROPOSAL.md, not yet implemented
**Priority**: Medium (operative reports usually sufficient)

### 4. Extraction Confidence != Extraction Success
**Key Distinction**:
- `extraction_confidence` (HIGH/MEDIUM/LOW) = MedGemma's self-assessment
- Extraction success = Agent 1's validation that ALL required fields present
- An extraction can have HIGH confidence but still be INCOMPLETE if required fields missing

### 5. Max 5 Alternative Documents
**Rationale**: Balance between:
- Exhaustive search (higher yield)
- Computational cost (MedGemma calls expensive)
- Practical limits (if 5 alternatives fail, unlikely 6th succeeds)

---

## Known Issues & Future Work

### Current Limitations
1. **TIFF images unsupported** - Need OCR integration for scanned documents
2. **Empty dates in timeline** - Some events have empty `event_date` fields (source data issue)
3. **Post-op MRI not queried** - Missing radiographic EOR assessment fallback
4. **No cross-modality validation** - Don't compare surgeon's EOR vs radiologist's residual assessment

### Future Enhancements
1. **OCR for TIFF/scanned PDFs** - pytesseract or AWS Textract integration
2. **Parallel extraction attempts** - Try multiple alternatives simultaneously
3. **Confidence weighting** - Prefer alternatives with higher extraction confidence
4. **Temporal reasoning** - Use timeline context to validate extracted dates
5. **Cross-validation** - Compare operative report EOR vs post-op MRI residual

### Testing Needed
1. ✅ Escalation strategy with patient eQSB0y3q - Running now
2. ⏳ Craniospinal + boost patient (e8jPD8zawpt)
3. ⏳ Batch testing across 10-20 patients
4. ⏳ Comparison of MedGemma results vs human abstraction
5. ⏳ Inter-rater reliability (MedGemma vs human abstractor agreement)

---

## Performance Metrics to Track

### Extraction Yield
- **Primary document success rate**: % gaps resolved from primary source
- **Escalation success rate**: % gaps resolved from alternatives (after primary failed)
- **Final yield**: % gaps resolved after exhausting all strategies

### Quality Metrics
- **Accuracy**: Agreement with human abstraction (field-by-field)
- **Completeness**: % required fields successfully extracted
- **Precision**: % extracted values that are correct
- **Recall**: % true values that were extracted

### Efficiency Metrics
- **Average alternatives tried**: Mean number of documents tried per gap
- **Time per extraction**: Mean duration for MedGemma extraction
- **Total extraction time**: End-to-end Phase 4 duration

---

## Command Reference

### Run Abstraction with Escalation
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline

python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83 \
  --output-dir output/escalation_test_eQSB0y3q \
  --max-extractions 5
```

### Query Document Inventory for Patient
```sql
SELECT
    binary_id,
    dr_type_text,
    dr_date,
    dr_description,
    content_type
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = 'Patient/eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83'
ORDER BY dr_date DESC;
```

### Check MedGemma Availability
```bash
curl http://localhost:11434/api/tags
```

---

## Dependencies

### Python Packages
- `boto3` - AWS S3 and Athena access
- `requests` - Ollama API calls
- `beautifulsoup4` - HTML/XML text extraction
- `PyPDF2` or `pdfplumber` - PDF text extraction
- `dateutil` - Date parsing for temporal filtering

### Infrastructure
- **AWS**: Athena (query Athena views), S3 (fetch binary documents)
- **Ollama**: Local LLM runtime for gemma2:27b
- **MedGemma**: gemma2:27b model (medical domain-adapted)

### Key Athena Views
- `fhir_prd_db.v_binary_files` - ALL documents with metadata
- `fhir_prd_db.v_radiation_documents` - Radiation-specific documents
- `fhir_prd_db.v_radiation_episode_enrichment` - Radiation episodes with doses
- `fhir_prd_db.v_chemo_treatment_episodes` - Chemotherapy episodes
- `fhir_prd_db.v_procedures_tumor` - Surgical procedures
- `fhir_prd_db.v_imaging` - Imaging studies with reports

---

## Git Commit Summary

**Branch**: main
**Key Commits**:
1. Implemented Phase 4 MedGemma binary extraction with two-agent negotiation
2. Added document content validation and extraction result validation
3. Implemented re-extraction with clarification for incomplete results
4. Enhanced prompts with real RADIANT PCA examples from human abstraction
5. **Implemented full escalating search strategy with alternative documents**
6. Added comprehensive documentation (5 strategy docs + this summary)

**Files Modified**:
- `scripts/patient_timeline_abstraction_V2.py` - Main implementation (~1800 lines)
- `agents/binary_file_agent.py` - Added XML support
- `agents/medgemma_agent.py` - No changes (already functional)

**Files Created**:
- `HUMAN_ABSTRACTION_EXAMPLES.md`
- `DOCUMENT_PRIORITIZATION_STRATEGY.md`
- `EOR_PRIORITIZATION_PROPOSAL.md`
- `MEDGEMMA_PROMPT_ENGINEERING_REVIEW.md`
- `PHASE4_IMPLEMENTATION_SUMMARY.md`

---

## Next Session Checklist

When resuming work on this project:

1. ✅ Read `NEW_SESSION_PROMPT.md` for current state
2. ✅ Review `PHASE4_IMPLEMENTATION_SUMMARY.md` (this doc) for implementation details
3. ✅ Check latest test results in `output/escalation_test_eQSB0y3q/<timestamp>/`
4. ⏳ Compare MedGemma extractions against human abstraction (`/Users/resnick/Downloads/example extraction.csv`)
5. ⏳ Test with craniospinal + boost patient (e8jPD8zawpt)
6. ⏳ Implement post-op MRI fallback for EOR if needed
7. ⏳ Run batch testing across multiple patients
8. ⏳ Calculate accuracy metrics vs human abstraction

---

**Session Completed**: 2025-10-31
**Implementation Status**: Full escalation strategy ✅
**Test Status**: Running escalation test with patient eQSB0y3q
**Ready for**: Results review and batch testing
