# New Session Prompt: Phase 4 Testing & Iteration

**Use this exact prompt to continue work on Phase 4 testing and iteration**

---

## Current Status: Phase 4 IMPLEMENTED ✅

**Last Updated**: 2025-10-31

The **Patient Clinical Journey Timeline Framework** for RADIANT PCA BRIM Analytics is now fully implemented with **Phase 4: MedGemma Binary Extraction with Escalating Search Strategy**.

### Implementation Status
- ✅ **Phases 1-3**: Complete (WHO 2021 classifications, 7-stage timeline, gap identification)
- ✅ **Phase 4**: FULLY IMPLEMENTED with two-agent negotiation and escalating search
- ⏳ **Testing**: In progress - validating against human abstraction gold standard
- 📋 **Next**: Test validation, iteration, and production deployment

---

## What Was Implemented in Phase 4

### Core Architecture: Two-Agent Negotiation System

**Agent 1 (Claude/Orchestrator)**:
- Identifies extraction gaps in timeline
- Builds patient-specific document inventory
- Validates document content BEFORE extraction
- Validates extraction results AFTER extraction
- Orchestrates escalating search through alternative documents

**Agent 2 (MedGemma 27B/Extractor)**:
- Extracts structured clinical data from binary documents
- Returns JSON with confidence scores
- Re-extracts with clarification when incomplete

### Key Features Implemented

1. **Validation & Negotiation Loop**
   - Document content validation (keyword checking) BEFORE extraction
   - Extraction result validation (required field checking) AFTER extraction
   - Re-extraction with field-specific clarification when incomplete
   - Escalation to alternative documents when all retries fail

2. **Escalating Search Strategy**
   - Patient-specific document inventory (`_build_patient_document_inventory()`)
   - Gap-type-aware alternative document prioritization (`_find_alternative_documents()`)
   - Tries up to 5 alternative documents (`_try_alternative_documents()`)
   - Temporal proximity filtering (prioritizes documents closest to event)

3. **Context-Aware Prompts with Real Examples**
   - Surgery/EOR: Operative note prompt with surgeon assessment interpretation guide
   - Radiation: Comprehensive prompt with craniospinal+boost pattern examples
   - Imaging: RANO criteria details with pseudoprogression window awareness
   - All prompts enhanced with real RADIANT PCA human abstraction examples

4. **Multi-Source Document Targeting**
   - Surgery gaps: Query v_binary_files for operative notes ±7 days
   - Radiation gaps: Query v_radiation_documents ±30 days (with validation to filter false positives)
   - Imaging gaps: Use diagnostic_report_id from v_imaging
   - Escalation: Search all available patient documents with gap-specific prioritization

5. **XML/HTML Support**
   - Added text/xml and application/xml content type support in BinaryFileAgent
   - Critical for radiation treatment planning documents

---

## Critical Context You MUST Know

### 1. FHIR Resource Mapping (Binary Document Retrieval)

**CORRECT WORKFLOW**:
```
DiagnosticReport/DocumentReference
  → Query v_binary_files WHERE document_reference_id = resource_id
  → Get binary_id
  → Apply period-to-underscore conversion (FHIR bug)
  → Fetch from S3
```

**Example**:
```sql
SELECT binary_id, content_type
FROM fhir_prd_db.v_binary_files
WHERE document_reference_id = 'DiagnosticReport/xyz123'
```
Then fetch `Binary/fmAXdcPPNkiCF9rr.5soVBQ` → S3 key: `prd/source/Binary/fmAXdcPPNkiCF9rr_5soVBQ`

### 2. Craniospinal + Boost Pattern (CRITICAL)

From human abstraction example (Patient e8jPD8zawpt):
```
Radiation treatment: Craniospinal irradiation + posterior fossa boost
- completed_craniospinal_or_whole_ventricular_radiation_dose: 4140 cGy (to brain/spine)
- radiation_focal_or_boost_dose: 5400 cGy (CUMULATIVE to tumor bed)

Calculation: 4140 cGy (CSI) + 1260 cGy (boost) = 5400 cGy total to posterior fossa
```

**Key Insight**: `radiation_focal_or_boost_dose` is the **CUMULATIVE** dose to the tumor bed, NOT just the boost portion. This is Example 2 in the radiation prompt.

### 3. v_radiation_documents Approach

**User Directive**: "let's leave radiation documents alone and just make sure medgemma doesn't return wrong information from this source"

**Implementation**:
- Use v_radiation_documents as PRIMARY source (±30 days from radiation start)
- Rely on document content validation to filter false positives
- Escalate to alternatives (treatment plans, progress notes) if validation fails
- Do NOT switch to v_binary_files query

### 4. Document Prioritization by Gap Type

**Surgery/EOR Gaps** (Priority order):
1. Operative records (highest priority)
2. Discharge summaries mentioning surgery
3. Post-operative imaging reports
4. Progress notes ±14 days from surgery

**Radiation Gaps** (Priority order):
1. v_radiation_documents (±30 days, with validation)
2. Treatment planning documents
3. Progress notes mentioning radiation
4. Discharge summaries

**Imaging Gaps** (Priority order):
1. Diagnostic report from v_imaging (already targeted)
2. Alternative: Not typically escalated (imaging conclusion is direct)

### 5. Extraction Gap Statuses

After Phase 4 processing, gaps can have these statuses:
- `RESOLVED`: Successfully extracted from primary or alternative document
- `WRONG_DOCUMENT_TYPE`: Document content validation failed, no suitable alternatives found
- `INCOMPLETE_EXTRACTION`: MedGemma extraction missing required fields after retry and escalation
- `RE_EXTRACTION_FAILED`: Re-extraction with clarification failed
- `UNAVAILABLE_IN_RECORDS`: All alternative documents exhausted
- `MEDGEMMA_ERROR`: Technical error (Ollama down, JSON parsing failure)

---

## File Structure

### Location
`/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/`

### Implementation Files

**scripts/patient_timeline_abstraction_V2.py** (~1800 lines)
- Main implementation with full Phase 4 escalation strategy
- Two-agent negotiation loop
- Patient-specific document inventory
- Alternative document search
- Enhanced prompts with real examples

**agents/medgemma_agent.py** (254 lines)
- MedGemma 27B wrapper via Ollama
- Model: gemma2:27b at http://localhost:11434
- JSON format output with retry logic
- Temperature: 0.1 (deterministic)

**agents/binary_file_agent.py**
- S3 binary document fetcher
- Bucket: radiant-prd-343218191717-us-east-1-prd-ehr-pipeline
- Supports: PDF, HTML, XML, RTF, plain text
- AWS profile: radiant-prod

### Documentation Files (READ THESE)

**PHASE4_IMPLEMENTATION_SUMMARY.md** (~400 lines) ⭐ CRITICAL
- Complete implementation details with code snippets
- Architecture diagrams
- Alternative document prioritization tables
- Validation rules
- Command reference and troubleshooting

**HUMAN_ABSTRACTION_EXAMPLES.md**
- 12 real examples from clinical abstraction team
- Surgery: biopsy, GTR/NTR, STR
- Chemotherapy: multi-agent, protocol-based
- Radiation: focal, craniospinal+boost, photon vs proton
- Patient e8jPD8zawpt craniospinal+boost pattern (Example 2 in radiation prompt)

**DOCUMENT_PRIORITIZATION_STRATEGY.md**
- Comprehensive escalation strategy documentation
- Gap-type-specific prioritization
- SQL query templates
- Implementation guidance

**MEDGEMMA_PROMPT_ENGINEERING_REVIEW.md**
- Analysis of prompt improvements
- Field-specific instructions
- Real examples integration
- Confidence criteria

**EOR_PRIORITIZATION_PROPOSAL.md**
- Post-operative MRI fallback proposal (not yet implemented)
- Dual-priority strategy for surgery EOR

### Legacy Documentation (Background)

**STEPWISE_TIMELINE_CONSTRUCTION.md** (30 pages)
- How the 7-stage timeline works
- Stage-by-stage validation logic

**IMAGING_REPORT_EXTRACTION_STRATEGY.md** (30 pages)
- When/how to extract imaging reports
- RANO criteria integration

**MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md** (40 pages)
- Original two-agent architecture design
- 3 detailed prompt examples (before real examples added)

**PHASE4_MEDGEMMA_IMPLEMENTATION_GUIDE.md** (45 pages)
- Original mock testing strategy

**PHASE4_READY_TO_IMPLEMENT.md** (15 pages)
- Original real MedGemma integration plan

---

## Key Methods in patient_timeline_abstraction_V2.py

### Phase 4 Main Loop
```python
def _phase4_extract_from_binaries(self):
    """Real MedGemma extraction with escalating search strategy"""
```
- Prioritizes gaps: HIGHEST (surgery EOR, radiation details) → HIGH → MEDIUM → LOW
- For each gap:
  1. Fetch primary target document
  2. Validate document content (Agent 1)
  3. Extract with MedGemma (Agent 2)
  4. Validate extraction result (Agent 1)
  5. Re-extract with clarification if incomplete (Agent 2)
  6. Escalate to alternative documents if still incomplete (Agent 1 + Agent 2)
  7. Mark final status (RESOLVED or failure reason)

### Escalation Infrastructure
```python
def _build_patient_document_inventory(self) -> Dict
```
- Catalogs ALL available documents for patient from v_binary_files
- Categories: operative_records, discharge_summaries, progress_notes, imaging_reports, pathology_reports, consultation_notes, radiation_documents, treatment_plans, other

```python
def _find_alternative_documents(self, gap: Dict, inventory: Dict) -> List[Dict]
```
- Returns prioritized list of candidate documents based on gap type
- Calculates temporal distance from event_date
- Sorts by: priority (1-4) → days_from_event (closest first)

```python
def _try_alternative_documents(self, gap: Dict, missing_fields: List[str]) -> bool
```
- Tries up to 5 alternative documents
- Validates each document content before extraction
- Validates each extraction result after
- Returns True if successful, False if all exhausted

### Validation Methods
```python
def _validate_document_content(self, extracted_text: str, gap_type: str) -> Tuple[bool, str]
```
- Checks for required keywords before extraction
- Example: Surgery gaps require ≥2 of ['surgery', 'operative', 'procedure', 'resection', 'excision']
- Prevents extracting from wrong document types

```python
def _validate_extraction_result(self, extraction_data: Dict, gap_type: str) -> Tuple[bool, List[str]]
```
- Checks for required fields after extraction
- Example: Radiation gaps require ['date_at_radiation_start', 'total_dose_cgy', 'radiation_type']
- Returns missing fields list for targeted re-extraction

```python
def _retry_extraction_with_clarification(self, original_prompt: str, document_text: str, missing_fields: List[str], gap_type: str) -> Dict
```
- Re-prompts MedGemma with field-specific guidance
- Example: "date_at_radiation_start: Extract the FIRST day of radiation therapy (look for 'treatment start', 'initial fraction', 'began radiation')"

### Target Finding Methods
```python
def _find_operative_note_binary(self, surgery_date: str) -> Optional[str]
```
- Queries v_binary_files for operative notes ±7 days from surgery
- Returns binary_id or None

```python
def _find_radiation_document(self, radiation_start_date: str) -> Optional[str]
```
- Queries v_radiation_documents ±30 days from radiation start
- Uses diagnostic_report_id (relies on validation to filter false positives)
- Returns resource_id or None

### Binary Fetching
```python
def _fetch_binary_document(self, fhir_resource_id: str) -> str
```
- Maps DiagnosticReport/DocumentReference → Binary ID via v_binary_files
- Applies period-to-underscore conversion for S3
- Uses BinaryFileAgent to fetch and extract text
- Handles PDF, HTML, XML, RTF

---

## Testing Strategy

### Current Test Status

**Test Running**: Patient eQSB0y3q (Astrocytoma, IDH-mutant, grade 3)
```bash
# Process 8e9f3f running
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83 \
  --output-dir output/escalation_test_eQSB0y3q \
  --max-extractions 5
```

**Output Location**: `output/escalation_test_eQSB0y3q/`

### Next Testing Steps

1. **Review Escalation Test Results**
   - Check `output/escalation_test_eQSB0y3q/timeline_artifact.json`
   - Validate medgemma_extraction fields
   - Check gap statuses (RESOLVED vs failures)
   - Review phase4_extraction_log.json for escalation behavior

2. **Test Craniospinal + Boost Patient**
   ```bash
   python3 scripts/patient_timeline_abstraction_V2.py \
     --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
     --output-dir output/craniospinal_boost_test \
     --max-extractions 10
   ```
   - Compare radiation extraction against human abstraction (CSV row for e8jPD8zawpt)
   - Verify: completed_craniospinal_dose = 4140 cGy, radiation_focal_dose = 5400 cGy

3. **Compare Against Human Abstraction Gold Standard**
   - Load `/Users/resnick/Downloads/example extraction.csv`
   - For each patient in CSV, run extraction and compare:
     - Surgery: extent_of_resection, surgeon_assessment
     - Radiation: all dose fields, treatment dates
     - Chemotherapy: protocols, start/end dates
   - Calculate agreement metrics (exact match, partial match, miss)

4. **Batch Test on All 9 Patients**
   ```bash
   for patient_id in <list from WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md>; do
     python3 scripts/patient_timeline_abstraction_V2.py \
       --patient-id $patient_id \
       --output-dir output/batch_test_${patient_id:0:10}
   done
   ```

### Test Validation Checklist

For each test run, verify:
- [ ] Phase 4 initiates without errors
- [ ] medgemma_target populated for surgery/radiation gaps
- [ ] Binary documents fetched successfully (no S3 errors)
- [ ] MedGemma extractions have valid JSON
- [ ] Validation catches wrong document types
- [ ] Re-extraction triggered for incomplete results
- [ ] Escalation triggered when re-extraction fails
- [ ] Alternative documents tried (check logs)
- [ ] Final gap statuses accurate (RESOLVED vs failure reasons)
- [ ] Timeline artifact contains medgemma_extraction fields
- [ ] Extraction log contains detailed history

---

## Command Reference

### Run Full Extraction (All Gaps)
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline

python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id <fhir_patient_id> \
  --output-dir output/<test_name>
```

### Run Limited Extraction (Testing)
```bash
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id <fhir_patient_id> \
  --output-dir output/<test_name> \
  --max-extractions 5
```

### Run High-Priority Only
```bash
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id <fhir_patient_id> \
  --output-dir output/<test_name> \
  --priority-filter HIGHEST
```

### Check Ollama Status
```bash
ollama list  # Should show gemma2:27b
ollama ps    # Shows running models
```

### Check AWS Profile
```bash
aws sso login --profile radiant-prod
aws sts get-caller-identity --profile radiant-prod
```

### View Test Output
```bash
# Timeline artifact
cat output/<test_name>/timeline_artifact.json | jq '.timeline_events[] | select(.medgemma_extraction)'

# Extraction log
cat output/<test_name>/phase4_extraction_log.json | jq '.extractions[] | select(.status == "success")'

# Gap analysis
cat output/<test_name>/phase4_extraction_log.json | jq '.extraction_gaps[] | select(.status == "RESOLVED")'
```

---

## Known Issues & Limitations

### 1. Empty event_date Fields
**Issue**: Some timeline events have empty event_date fields
**Impact**: Temporal proximity filtering cannot calculate days_from_event
**Likely Cause**: Source data issue in Athena views (v_procedures, v_imaging)
**Status**: Not yet investigated

### 2. TIFF Image Support
**Issue**: image/tiff content type unsupported by BinaryFileAgent
**Impact**: Cannot extract text from scanned documents (operative notes, pathology reports)
**Solution**: Need OCR integration (pytesseract or AWS Textract)
**Status**: Not yet implemented

### 3. v_radiation_documents False Positives
**Issue**: View includes ED visits mentioning radiation history (not treatment records)
**Impact**: May target wrong documents for radiation gaps
**Mitigation**: Document content validation filters these out before extraction
**Status**: Working as designed (per user directive)

### 4. Re-extraction Effectiveness
**Issue**: Field-specific clarification may not always improve extraction
**Impact**: May exhaust retries without getting complete data
**Mitigation**: Escalation to alternative documents provides fallback
**Status**: Monitoring test results

### 5. Alternative Document Exhaustion
**Issue**: Some gaps may not have any suitable alternative documents
**Impact**: Marked as UNAVAILABLE_IN_RECORDS even though data might exist in unstructured notes
**Future Work**: Free-text search across ALL documents (computationally expensive)
**Status**: Accepted limitation for Phase 4

---

## Critical Requirements (MUST FOLLOW)

### DO NOT:
- ❌ Re-extract WHO 2021 molecular classifications (already embedded in script)
- ❌ Guess at column names (use exact names from Athena_Schema_10302025.csv)
- ❌ Switch from v_radiation_documents to v_binary_files for radiation (user explicitly said leave it alone)
- ❌ Mark extractions as RESOLVED if required fields are missing
- ❌ Create new documentation files unless explicitly needed

### DO:
- ✅ Review PHASE4_IMPLEMENTATION_SUMMARY.md before making any changes
- ✅ Test against human abstraction gold standard (example extraction.csv)
- ✅ Validate craniospinal + boost pattern extraction (patient e8jPD8zawpt)
- ✅ Check escalation behavior in phase4_extraction_log.json
- ✅ Kill old background processes before Git sync
- ✅ Compare extraction results across test runs for consistency

---

## WHO 2021 Classifications (Embedded in Script)

**9 Patients with molecular classifications**:
- 4 patients: Diffuse midline glioma, H3 K27-altered (WHO grade 4)
- 1 patient: Diffuse hemispheric glioma, H3 G34-mutant (WHO grade 4)
- 1 patient: Pineoblastoma, MYC/FOXR2-activated (WHO grade 4)
- 1 patient: Astrocytoma, IDH-mutant (WHO grade 3)
- 2 patients: Insufficient/no data

These are in `WHO_2021_CLASSIFICATIONS` dictionary in the script. **DO NOT re-extract.**

---

## 7-Stage Timeline (Phases 1-3 Complete)

**Stage 0**: Molecular diagnosis (WHO 2021 anchor)
**Stage 1**: Encounters/appointments
**Stage 2**: Procedures (surgeries)
**Stage 3**: Chemotherapy episodes
**Stage 4**: Radiation episodes
**Stage 5**: Imaging studies
**Stage 6**: Pathology granular records

Each stage validates treatments against WHO 2021 expected paradigms.

---

## Athena Views Used

**Phase 2 (Timeline Construction)**:
- `fhir_prd_db.v_encounters_appointments`
- `fhir_prd_db.v_procedures`
- `fhir_prd_db.v_chemotherapy_episodes`
- `fhir_prd_db.v_radiation_episodes`
- `fhir_prd_db.v_imaging`
- `fhir_prd_db.v_pathology_granular`

**Phase 4 (Binary Extraction)**:
- `fhir_prd_db.v_binary_files` (primary for mapping DocumentReference → Binary ID)
- `fhir_prd_db.v_radiation_documents` (specific for radiation gap targeting)

---

## Next Session Checklist

When starting the next session:

1. **Check Background Processes**
   ```bash
   # Check for running Python processes
   ps aux | grep patient_timeline_abstraction

   # Kill old processes if needed (9 old processes identified)
   pkill -f "patient_timeline_abstraction_V2.py"
   ```

2. **Review Latest Test Results**
   - Check `output/escalation_test_eQSB0y3q/` for completion
   - Review timeline_artifact.json for medgemma_extraction fields
   - Review phase4_extraction_log.json for gap statuses

3. **Sync to GitHub**
   ```bash
   cd /Users/resnick/Documents/GitHub/RADIANT_PCA
   git status
   git add BRIM_Analytics/patient_clinical_journey_timeline/
   git commit -m "Phase 4: Implement escalating search strategy with two-agent negotiation

   - Full validation loop (document content + extraction result validation)
   - Patient-specific alternative document search with temporal proximity
   - Enhanced prompts with real RADIANT PCA human abstraction examples
   - Support for craniospinal + boost radiation pattern
   - XML/HTML document support for radiation treatment plans
   - Comprehensive documentation (PHASE4_IMPLEMENTATION_SUMMARY.md)"

   git push origin main
   ```

4. **Read Key Documentation**
   - PHASE4_IMPLEMENTATION_SUMMARY.md (400 lines - CRITICAL)
   - HUMAN_ABSTRACTION_EXAMPLES.md (real examples for validation)
   - Review latest test outputs

5. **Prepare for Iteration**
   - Compare extractions against human abstraction CSV
   - Identify patterns of failure (wrong documents, incomplete extractions)
   - Adjust validation rules or prompts as needed
   - Test on patients with known complex cases (craniospinal+boost, multi-agent chemo)

---

## Success Metrics

Phase 4 is considered successful when:
- ✅ Extractions from binary documents integrate into timeline artifacts
- ✅ Validation catches wrong document types (no ED visit notes for radiation)
- ✅ Re-extraction improves incomplete results
- ✅ Escalation finds alternative documents when primary fails
- ✅ Craniospinal + boost pattern extracted correctly (patient e8jPD8zawpt)
- ✅ Agreement with human abstraction ≥80% for high-priority gaps
- ✅ Extraction logs show clear audit trail of Agent 1↔Agent 2 negotiation

---

**Last Updated**: 2025-10-31 (Phase 4 fully implemented)
**Current Focus**: Testing, validation against human abstraction, iteration
**Ready for**: Production deployment after validation complete
