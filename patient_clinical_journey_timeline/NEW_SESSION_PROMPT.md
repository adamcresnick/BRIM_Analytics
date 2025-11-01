# New Session Prompt: Continue Timeline Framework Development

**Use this exact prompt to continue work on the Patient Clinical Journey Timeline Framework**

---

## Current Status: Phase 4 ENHANCED - Radiation/Surgery/Imaging Complete ✅

**Last Updated**: 2025-11-01
**Session**: Continuation - HTML content type fix + comprehensive radiation keywords + chemotherapy planning

### Implementation Status

| Phase | Status | Details |
|-------|--------|---------|
| **Phases 1-3** | ✅ **COMPLETE** | WHO 2021 classifications, 7-stage timeline, gap identification |
| **Phase 4: Surgery/Radiation/Imaging** | ✅ **COMPLETE + ENHANCED** | HTML extraction fixed, comprehensive keywords, dual-source EOR validation |
| **Phase 4: Chemotherapy** | ⚠️ **PARTIALLY IMPLEMENTED** | Gap identification added, needs completion |
| **Phase 5** | 📋 **PLANNED** | WHO 2021 protocol validation |
| **Testing** | ⏳ **IN PROGRESS** | Validating fixes, need clean end-to-end test |

---

## Session 2025-11-01 Accomplishments

### 🎯 Major Bug Fixes

#### 1. HTML Content Type Mislabeling Bug FIXED ✅
**Problem**: Documents with `contentType: text/html` in FHIR Binary were being routed to PDF extractor, causing "Failed to open stream" errors.

**Root Cause**: In `_fetch_binary_document()` (Line 1749), when alternative documents passed Binary IDs directly, the code hardcoded:
```python
content_type = "application/pdf"  # ❌ WRONG - assumes all binaries are PDFs
```

**Solution** ([`patient_timeline_abstraction_V2.py:1746-1771`](scripts/patient_timeline_abstraction_V2.py#L1746-L1771)):
- Added database query to v_binary_files to retrieve actual `content_type`
- Query executes even for direct Binary IDs (format: `Binary/xyz`)
- Falls back to `application/pdf` only if query fails

**Result**: HTML documents now extract successfully using BeautifulSoup parser

**Test Evidence**:
```
11:13:26,603 - Found content_type text/html for Binary/eLArUwwXJ7dlOjuLRLpAomvo6ayIy77Pdgp3NXWYEsvE3
11:13:26,603 - Extracting content from Binary/... (text/html)  ← CORRECT!
11:13:26,857 - Successfully extracted 47.3KB from FHIR Binary resource
```

---

#### 2. Radiation Validation Keywords Expanded ✅
**Problem**: Limited keywords (only 6 terms) caused validation failures for documents that DID contain radiation information but used different terminology.

**Solution** ([`patient_timeline_abstraction_V2.py:1818-1836`](scripts/patient_timeline_abstraction_V2.py#L1818-L1836)):
- Expanded from 6 terms → **35+ comprehensive radiation terms**
- Aligned with SQL terminology from `DATETIME_STANDARDIZED_VIEWS.sql`
- Lowered minimum keywords from 3 → 2 to increase sensitivity

**Keywords Added**:
- **Core terms**: radiation, radiotherapy, radiosurgery, xrt, rt, imrt
- **Treatment modalities**: proton, cyberknife, gamma knife, sbrt, srs
- **Anatomical patterns**: craniospinal, csi, focal, whole brain, wbrt, ventricular, spine, boost, local, field
- **Dose/delivery**: dose, gy, cgy, gray, dosage, fraction, fractions, fractionation, beam, beams, port, fields
- **Planning**: treatment, therapy, plan, planning, simulation, sim, delivery, tx, rx

**Source**: Keywords extracted from production SQL views (`DATETIME_STANDARDIZED_VIEWS.sql`)

---

### 🔬 Required Fields Enhancements

#### 3. Added `date_at_radiation_stop` as Required Field ✅
**Location**: [`patient_timeline_abstraction_V2.py:1878`](scripts/patient_timeline_abstraction_V2.py#L1878)

**Rationale**: Track **re-irradiation episodes** upon progression/recurrence

**Example Use Case**:
- Patient receives 54 Gy focal radiation (2018-04-15 to 2018-06-08)
- Disease progresses in 2020
- Patient receives salvage radiation 30 Gy (2020-09-01 to 2020-10-15)
- **Without end dates**, these episodes cannot be distinguished

**Required fields for radiation (now 4)**:
1. `date_at_radiation_start` - Episode start boundary
2. `date_at_radiation_stop` - Episode end boundary ✨ **NEW**
3. `total_dose_cgy` - Total cumulative dose
4. `radiation_type` - focal, craniospinal, whole_ventricular, focal_with_boost

---

#### 4. Updated EOR Guidance for Dual-Source Validation ✅
**Location**: [`patient_timeline_abstraction_V2.py:1913`](scripts/patient_timeline_abstraction_V2.py#L1913)

**Updated Guidance**:
```python
'extent_of_resection': 'Look for phrases like "gross total resection", "subtotal resection", "biopsy only" in operative note AND post-operative imaging (MRI within 72 hours)'
```

**Clinical Rationale**:
- **Operative notes**: Surgeon's intraoperative assessment (subjective)
- **Post-op imaging** (MRI within 72 hours): Radiographic confirmation (objective)
- Surgeon may report "gross total resection" but imaging shows residual enhancement
- Standard of care includes early post-op MRI for neuro-oncology patients

---

### 📚 Documentation Created

#### 5. Comprehensive Strategy Document ✅
**File**: [`REQUIRED_EXTRACTION_FIELDS_STRATEGY.md`](REQUIRED_EXTRACTION_FIELDS_STRATEGY.md)

**Contents**:
- **Current implementation**: Surgery (2 fields), Radiation (4 fields), Imaging (2 fields)
- **Chemotherapy requirements**: 6 fields documented for future implementation
- **Escalating search strategy**: Detailed flowchart and rationale
- **Implementation roadmap**: Priorities and timelines
- **Testing validation criteria**: How to assess successful extraction

**Key Sections**:
- Required fields by gap type with clinical rationale
- Validation keywords (comprehensive lists)
- Escalation strategies (document prioritization)
- Change log (tracks all updates)

---

## Chemotherapy Implementation Status

### ⚠️ PARTIALLY IMPLEMENTED (Needs Completion)

**What's Done**:
1. ✅ **Phase 3 Gap Identification** ([Lines 729-754](scripts/patient_timeline_abstraction_V2.py#L729-L754))
   - Identifies missing protocol_name, on_protocol_status, agent_names
   - Creates `missing_chemotherapy_details` gap type

2. ✅ **Helper Function Created** ([Lines 852-901](scripts/patient_timeline_abstraction_V2.py#L852-L901))
   - `_find_chemotherapy_document()` queries v_binary_files
   - Looks for chemotherapy/infusion/treatment/oncology/progress keywords
   - Searches within ±14 days of treatment date

**What's Missing** (Blocks Testing):
1. ❌ **Required fields validation** not added to `_validate_extraction_result()`
2. ❌ **MedGemma extraction prompt** not created in `_generate_medgemma_prompt()`
3. ❌ **Validation keywords** not added to `_validate_document_content()`
4. ❌ **Document prioritization** not added to `_find_alternative_documents()`
5. ❌ **Field guidance** not added to `_retry_extraction_with_clarification()`

**Required Fields (from Strategy Document)**:
```python
'missing_chemotherapy_details': [
    'protocol_name',           # e.g., "COG ACNS0126", "SJMB12"
    'on_protocol_status',      # "enrolled", "treated_as_per_protocol", "treated_like_protocol", "off_protocol"
    'agent_names',             # ["Temozolomide", "Vincristine", "Carboplatin"]
    'start_date',              # "2023-04-15"
    'end_date',                # "2023-10-20"
    'change_in_therapy_reason' # "progression", "toxicity", "patient_preference", null
]
```

**Document Prioritization (from existing documentation)**:
Based on [`PRIORITIZED_NOTE_TYPES_FOR_BRIM_VARIABLES.md`](../documentation/PRIORITIZED_NOTE_TYPES_FOR_BRIM_VARIABLES.md) and [`CHEMOTHERAPY_EPISODE_APPROACH.md`](../documentation/CHEMOTHERAPY_EPISODE_APPROACH.md):

1. **Priority 1**: Medication notes (embedded in FHIR Medication resources) - 69.6% contain cycle/course info
2. **Priority 2**: Consult notes (oncology) - 43,538 documents - treatment planning, protocols
3. **Priority 3**: Progress notes (oncology visits) - 727,633 documents - treatment response
4. **Priority 4**: Discharge summaries - 13,449 documents - comprehensive treatment history
5. **Priority 5**: Care plan documents - 68,988 documents - protocol documentation

---

## Next Steps (Prioritized)

### IMMEDIATE (This Session or Next)

#### Option 1: Complete Chemotherapy Implementation (~2-3 hours)
**Tasks**:
1. Add chemotherapy required fields to `_validate_extraction_result()` (~15 min)
2. Create chemotherapy MedGemma prompt in `_generate_medgemma_prompt()` (~45 min)
3. Add chemotherapy validation keywords to `_validate_document_content()` (~15 min)
4. Add chemotherapy document prioritization to `_find_alternative_documents()` (~30 min)
5. Add chemotherapy field guidance to `_retry_extraction_with_clarification()` (~15 min)
6. Test with patient who has chemotherapy data (~1 hour)

**Estimated Completion**: 2-3 hours
**Risk**: High context usage, may hit token limits

---

#### Option 2: Commit Current Progress + Clean Test (RECOMMENDED)
**Tasks**:
1. ✅ **DONE**: Kill all background processes (18+ were running)
2. **Commit current work** with descriptive message
3. **Comment out incomplete chemotherapy code** to prevent test failures
4. **Run clean end-to-end test** with Surgery/Radiation/Imaging only
5. **Validate results** against human abstraction gold standard
6. **Start fresh session** for chemotherapy implementation

**Estimated Completion**: 30-60 minutes
**Risk**: Low - validates what's working before adding complexity

---

### SHORT TERM (Next 1-2 Sessions)

1. **Complete chemotherapy implementation** (if not done above)
2. **Run comprehensive tests** across multiple patients:
   - Astrocytoma (eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83)
   - Pineoblastoma (e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3)
3. **Compare against human abstraction** (`/Users/resnick/Downloads/example extraction.csv`)
4. **Iterate on prompts** based on extraction accuracy
5. **Document test results** and accuracy metrics

---

### MEDIUM TERM (Next 3-5 Sessions)

1. **Implement Phase 5**: WHO 2021 Protocol Validation
   - Validate radiation doses against diagnosis-specific guidelines
   - Validate chemotherapy regimens against diagnosis-specific protocols
   - Flag protocol deviations for manual review

2. **Expand to additional tumor types**:
   - Medulloblastoma (craniospinal + boost pattern)
   - Ependymoma (focal radiation)
   - High-grade glioma (Stupp protocol validation)

3. **Performance optimization**:
   - Cache document inventory across patients
   - Parallel extraction where possible
   - Optimize Athena queries

4. **Production deployment planning**:
   - Error handling and retry logic
   - Logging and monitoring
   - Batch processing capabilities

---

## Testing Strategy

### Test Patients

| Patient ID | WHO 2021 Diagnosis | Key Features to Test |
|------------|-------------------|---------------------|
| `eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83` | Astrocytoma, IDH-mutant, Grade 3 | HTML extraction, radiation escalation, multiple documents |
| `e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3` | Pineoblastoma | Craniospinal+boost pattern, imaging RANO |

### Validation Criteria

**Successful Extraction Requires**:
1. ✅ All required fields populated (no null values)
2. ✅ Data clinically plausible (dates valid, doses in expected ranges)
3. ✅ Matches human abstraction (when gold standard available)
4. ✅ Extraction confidence HIGH or MEDIUM (LOW triggers manual review)

### Gold Standard Comparison

**Reference**: `/Users/resnick/Downloads/example extraction.csv`

**Fields to Compare**:
- Surgery dates and EOR classification
- Radiation start/stop dates and total doses
- Chemotherapy protocols and agents
- Imaging response assessments

---

## Key Files Modified This Session

| File | Lines | Changes |
|------|-------|---------|
| [`patient_timeline_abstraction_V2.py`](scripts/patient_timeline_abstraction_V2.py) | 1746-1771 | Fixed HTML content type query for Binary IDs |
| | 1818-1836 | Expanded radiation keywords (6→35+ terms) |
| | 1878 | Added `date_at_radiation_stop` to required fields |
| | 1913 | Updated EOR guidance (post-op imaging) |
| | 729-754 | Added chemotherapy gap identification |
| | 852-901 | Created `_find_chemotherapy_document()` helper |
| [`REQUIRED_EXTRACTION_FIELDS_STRATEGY.md`](REQUIRED_EXTRACTION_FIELDS_STRATEGY.md) | NEW | Comprehensive strategy document (6 required fields per modality) |

---

## Git Commit Strategy

### Commit 1: HTML Content Type Fix + Radiation Keywords
```bash
git add scripts/patient_timeline_abstraction_V2.py
git commit -m "Fix HTML content type mislabeling + expand radiation keywords

- Fix: Query v_binary_files for actual content_type (Lines 1746-1771)
  - Was hardcoding 'application/pdf' for all Binary IDs
  - Now correctly identifies text/html and routes to BeautifulSoup parser
- Enhance: Expand radiation keywords from 6 to 35+ terms (Lines 1818-1836)
  - Aligned with SQL terminology from DATETIME_STANDARDIZED_VIEWS.sql
  - Added treatment modalities, anatomical patterns, dose/delivery terms
  - Lowered minimum keywords from 3 to 2
- Add: date_at_radiation_stop as required field (Line 1878)
  - Track re-irradiation episodes
- Update: EOR guidance for dual-source validation (Line 1913)
  - Operative note + post-op imaging (MRI within 72 hours)

Result: HTML documents now extract successfully, radiation validation more comprehensive"
```

### Commit 2: Strategy Documentation
```bash
git add REQUIRED_EXTRACTION_FIELDS_STRATEGY.md
git commit -m "Document comprehensive extraction field requirements

- Create REQUIRED_EXTRACTION_FIELDS_STRATEGY.md
- Document required fields for Surgery (2), Radiation (4), Imaging (2)
- Document chemotherapy requirements (6 fields) for future implementation
- Include escalating search strategy with clinical rationale
- Add implementation roadmap and testing validation criteria"
```

### Commit 3: Chemotherapy Partial Implementation (Optional - if keeping)
```bash
git add scripts/patient_timeline_abstraction_V2.py
git commit -m "Chemotherapy: Add Phase 3 gap identification (PARTIAL)

- Add chemotherapy gap detection (Lines 729-754)
- Create _find_chemotherapy_document() helper (Lines 852-901)
- Status: INCOMPLETE - requires validation/prompts/keywords to function
- TODO: Complete remaining 5 tasks before testing"
```

**OR** (Recommended):

### Commit 3: Comment Out Incomplete Chemotherapy Code
```bash
# Comment out Lines 729-754 and 852-901 in patient_timeline_abstraction_V2.py
git add scripts/patient_timeline_abstraction_V2.py
git commit -m "Comment out incomplete chemotherapy code

- Chemotherapy gap identification partially implemented but incomplete
- Commenting out to prevent test failures
- Will complete in dedicated session with fresh context"
```

---

## Context Status

**Token Usage**: ~105K / 200K (52.5%)
**Background Processes Killed**: 18+ were running simultaneously
**Recommendation**: Commit and start fresh session for chemotherapy completion

---

## Quick Start Commands for Next Session

### Option 1: Continue Chemotherapy Implementation
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline

# Review incomplete tasks
grep -n "missing_chemotherapy_details" scripts/patient_timeline_abstraction_V2.py

# Continue implementation (see "IMMEDIATE" section above for task list)
```

### Option 2: Run Clean Test (Surgery/Radiation/Imaging Only)
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline

# Comment out chemotherapy code first (Lines 729-754, 852-901)
# Then run clean test

python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83 \
  --output-dir output/clean_test_surgery_radiation_imaging \
  --max-extractions 10
```

---

## Critical Reminders

1. **Always kill background processes** before starting new tests: `pkill -9 -f "patient_timeline_abstraction_V2.py"`
2. **AWS SSO renewal**: If token expires, run `aws sso login --profile radiant-prod`
3. **MedGemma availability**: Verify with `ollama list | grep gemma2:27b`
4. **Test incrementally**: Start with 1-2 extractions, then scale up
5. **Compare against gold standard**: `/Users/resnick/Downloads/example extraction.csv`

---

## Architecture References

- **Two-Agent Validation Loop**: [`MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md`](docs/MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md)
- **Phase 4 Implementation**: [`PHASE4_IMPLEMENTATION_SUMMARY.md`](PHASE4_IMPLEMENTATION_SUMMARY.md)
- **Required Fields Strategy**: [`REQUIRED_EXTRACTION_FIELDS_STRATEGY.md`](REQUIRED_EXTRACTION_FIELDS_STRATEGY.md)
- **Radiation Terminology**: [`../documentation/RADIATION_EPISODE_APPROACH.md`](../documentation/RADIATION_EPISODE_APPROACH.md)
- **Chemotherapy Episode Approach**: [`../documentation/CHEMOTHERAPY_EPISODE_APPROACH.md`](../documentation/CHEMOTHERAPY_EPISODE_APPROACH.md)
- **Document Prioritization**: [`../documentation/PRIORITIZED_NOTE_TYPES_FOR_BRIM_VARIABLES.md`](../documentation/PRIORITIZED_NOTE_TYPES_FOR_BRIM_VARIABLES.md)

---

**Session End Time**: 2025-11-01 ~15:30 EST
**Context Usage**: 105K / 200K tokens
**Next Session**: Complete chemotherapy OR validate current work
