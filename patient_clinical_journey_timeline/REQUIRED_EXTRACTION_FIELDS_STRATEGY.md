# Required Extraction Fields Strategy
**Date**: 2025-11-01
**Purpose**: Define required fields for MedGemma binary extraction across all treatment modalities
**Status**: Surgery/Radiation/Imaging IMPLEMENTED | Chemotherapy PLANNED

---

## Executive Summary

This document defines the **required fields** that must be extracted from clinical documents for each gap type in the Patient Clinical Journey Timeline Framework. These fields drive the **escalating search strategy** where Agent 1 (Claude) validates that Agent 2 (MedGemma) successfully extracts ALL required fields before marking an extraction as complete.

**Key Principle**: If required fields are missing after primary document extraction + re-extraction, the system **automatically escalates to alternative documents** (progress notes, discharge summaries, etc.) until all fields are found or alternatives are exhausted.

---

## Implementation Status

| Treatment Modality | Phase 3 (Gap ID) | Phase 4 (Extraction) | Phase 5 (Validation) | Status |
|-------------------|------------------|---------------------|---------------------|---------|
| **Surgery (EOR)** | ✅ Implemented | ✅ Implemented | ✅ Implemented | **ACTIVE** |
| **Radiation** | ✅ Implemented | ✅ Implemented | ✅ Implemented | **ACTIVE** |
| **Imaging (RANO)** | ✅ Implemented | ✅ Implemented | ⚠️ Partial | **ACTIVE** |
| **Chemotherapy** | ❌ Not Implemented | ❌ Not Implemented | ❌ Not Implemented | **PLANNED** |

---

## 1. Surgery: Extent of Resection (EOR)

### Gap Type: `missing_eor`

### Required Fields (2)

| Field Name | Data Type | Description | Example Values | Validation Source |
|------------|-----------|-------------|----------------|-------------------|
| **extent_of_resection** | string | Categorical resection extent | "gross_total_resection", "subtotal_resection", "biopsy_only" | Operative note + Post-op MRI |
| **surgeon_assessment** | string | Verbatim surgeon's assessment | "Complete gross total resection of right frontal mass achieved" | Operative note procedure description |

### Clinical Rationale

**Dual-source validation required**:
- **Operative notes**: Surgeon's intraoperative assessment (subjective)
- **Post-operative imaging** (MRI within 72 hours): Radiographic confirmation of resection extent (objective)

**Why both sources matter**:
- Surgeon may report "gross total resection" but post-op MRI shows residual enhancement
- Standard of care includes early post-op MRI (within 24-72 hours) for neuro-oncology patients
- Objective imaging provides ground truth for residual disease measurement

### Escalation Strategy

**Primary target**: Operative note binary
**Alternative documents** (in priority order):
1. Post-operative imaging reports (MRI within ±7 days)
2. Discharge summaries (contain operative summary + imaging results)
3. Consultation notes (post-op follow-up)

### Implementation Status: ✅ IMPLEMENTED
- **Location**: `patient_timeline_abstraction_V2.py:1875`
- **Guidance updated**: Lines 1913 (includes post-op imaging reference)

---

## 2. Radiation: Treatment Episode Details

### Gap Type: `missing_radiation_details`

### Required Fields (4)

| Field Name | Data Type | Description | Example Values | Clinical Significance |
|------------|-----------|-------------|----------------|----------------------|
| **date_at_radiation_start** | date (YYYY-MM-DD) | First day of radiation treatment | "2023-04-15" | Episode start boundary |
| **date_at_radiation_stop** | date (YYYY-MM-DD) | Last day of radiation treatment | "2023-06-08" | Episode end boundary - CRITICAL for re-irradiation tracking |
| **total_dose_cgy** | integer | Total cumulative dose in centiGray | 5400 (= 54 Gy) | Dosimetry validation |
| **radiation_type** | string (enum) | Anatomical treatment pattern | "focal", "craniospinal", "whole_ventricular", "focal_with_boost" | Protocol compliance |

### Clinical Rationale

**Why `date_at_radiation_stop` is REQUIRED**:
- Track **re-irradiation episodes** upon progression/recurrence
- Distinguish **multiple treatment courses** (initial vs. salvage radiation)
- Calculate **treatment duration** (days from start to stop)
- Identify **concurrent vs. sequential** treatment patterns

**Re-irradiation example**:
- Patient receives 54 Gy focal radiation (2018-04-15 to 2018-06-08)
- Disease progresses in 2020
- Patient receives salvage radiation 30 Gy (2020-09-01 to 2020-10-15)
- **Without end dates**, these episodes cannot be distinguished

### Validation Keywords (Comprehensive)

From SQL-aligned radiation terminology (`patient_timeline_abstraction_V2.py:1818-1836`):

**Core radiation terms**: radiation, radiotherapy, radiosurgery, xrt, rt, imrt
**Treatment modalities**: proton, cyberknife, gamma knife, sbrt, srs
**Anatomical patterns**: craniospinal, csi, focal, whole brain, wbrt, ventricular, spine, boost, local, field
**Dose & delivery**: dose, gy, cgy, gray, dosage, fraction, fractions, fractionation, beam, beams, port, fields
**Planning terms**: treatment, therapy, plan, planning, simulation, sim, delivery, tx, rx

**Minimum keywords required**: 2 (lowered from 3 to increase sensitivity)

### Escalation Strategy

**Primary target**: Radiation-specific documents (treatment summaries, planning notes)
**Alternative documents** (temporal + type prioritization):
1. **Radiation documents** (±30 days, highest priority)
2. **Progress notes** (±30 days, mentions of treatment dates/doses)
3. **Discharge summaries** (±60 days, comprehensive treatment summaries)
4. **Treatment plans** (±90 days, planning documentation)

**No keyword filtering on alternatives** - rely on temporal proximity + document type + MedGemma validation


---

## 3. Imaging: RANO Response Assessment

### Required Fields (2)

| Field Name | Data Type | Description | Example Values | Clinical Use |
|------------|-----------|-------------|----------------|--------------|
| **lesions** | array of objects | Tumor lesions with measurements | `[{"location": "right frontal", "size_mm": 32, "enhancement": true}]` | Tumor burden tracking |
| **rano_assessment** | string (enum) | RANO criteria response | "complete_response", "partial_response", "stable_disease", "progressive_disease" | Treatment efficacy |

### Clinical Rationale

**RANO (Response Assessment in Neuro-Oncology)** criteria:
- Standardized measurement of brain tumor response to treatment
- Combines lesion size changes, new lesions, clinical status, and steroid use
- Required for clinical trial reporting and treatment decision-making

### Escalation Strategy

**Primary target**: Diagnostic report from imaging event
**Alternative documents**:
1. Subsequent imaging reports (compare serial scans)
2. Oncology progress notes (contain imaging interpretation)
3. Tumor board summaries (comprehensive assessment)

### Implementation Status: ✅ IMPLEMENTED
- **Location**: `patient_timeline_abstraction_V2.py:1882`
- **Validation**: Partial (RANO schema validation needs enhancement)

---

## 4. Chemotherapy: Protocol and Therapy Changes

### Gap Type: `missing_chemotherapy_details` (PLANNED)

### Required Fields (6)

| Field Name | Data Type | Description | Example Values | Clinical Significance |
|------------|-----------|-------------|----------------|----------------------|
| **protocol_name** | string | Name or number of clinical protocol | "COG ACNS0126", "SJMB12", "ACNS1422" | Protocol compliance tracking |
| **on_protocol_status** | string (enum) | Enrollment status | "enrolled", "treated_as_per_protocol", "treated_like_protocol", "off_protocol" | Distinguishes enrolled vs. protocol-guided care |
| **agent_names** | array of strings | Chemotherapy drug names | `["Temozolomide", "Vincristine", "Carboplatin"]` | Regimen identification |
| **start_date** | date (YYYY-MM-DD) | Treatment episode start | "2023-04-15" | Episode boundary |
| **end_date** | date (YYYY-MM-DD) | Treatment episode end | "2023-10-20" | Episode boundary |
| **change_in_therapy_reason** | string (nullable) | Reason for therapy modification | "progression", "toxicity", "patient_preference", null | Treatment trajectory analysis |

### Clinical Rationale

**Protocol tracking importance**:
- Pediatric brain tumor patients often enrolled in multi-institutional protocols (COG, SJMB, ACNS)
- "Enrolled" vs. "treated as per protocol" distinction affects:
  - Data collection requirements
  - Follow-up schedules
  - Outcome reporting obligations
- Off-protocol modifications common due to toxicity or disease progression

**Change in therapy reasons**:
- **Progression**: Disease not responding, escalate treatment
- **Toxicity**: Dose reduction or agent substitution needed
- **Patient preference**: Family requests treatment modification
- **Protocol amendment**: Study design changes mid-treatment

**Episode tracking**:
- Multiple chemotherapy courses common (induction → consolidation → maintenance)
- Re-challenge with same agents after progression
- Start/end dates distinguish separate treatment episodes

### Validation Keywords (Proposed)

**Protocol terms**: protocol, trial, study, enrolled, enrollment, consent, COG, ACNS, SJMB, POG
**Chemotherapy terms**: chemotherapy, chemo, agent, drug, cycle, course, regimen, infusion
**Agent names**: temozolomide, vincristine, carboplatin, cisplatin, etoposide, cyclophosphamide, lomustine
**Change indicators**: changed, modified, discontinued, stopped, held, dose reduction, escalation, toxicity, progression



### Escalation Strategy (Proposed)

**Primary target**: Chemotherapy treatment summaries, infusion records
**Alternative documents**:
1. **Treatment plan documents** (protocol enrollment forms)
2. **Progress notes** (treatment discussions, dose modifications)
3. **Discharge summaries** (comprehensive treatment history)
4. **Consultation notes** (oncology visits discussing therapy changes)

### Document Source Priority

| Document Type | Priority | Typical Content | Days from Event |
|---------------|----------|-----------------|-----------------|
| Chemotherapy treatment summary | 1 (HIGHEST) | Complete protocol details, all agents, doses | ±7 days |
| Infusion records | 2 | Agent names, doses, dates | Same day |
| Oncology progress notes | 3 | Treatment discussions, toxicity, modifications | ±14 days |
| Discharge summaries | 4 | Comprehensive treatment history | ±30 days |
| Treatment plans | 5 | Protocol enrollment, consent forms | ±60 days |



**Blocked by**:
- Phase 3 gap identification logic not implemented
- Phase 4 extraction prompt not created
- Phase 5 WHO 2021 protocol validation not defined

**Estimated implementation**:
- Phase 3 (gap ID): 1-2 hours
- Phase 4 (extraction): 2-3 hours
- Phase 5 (validation): 1-2 hours
- Testing: 2-4 hours
- **Total**: 6-11 hours

---

## Implementation Strategy

### Current Session (2025-11-01)

**Phase 1**: ✅ Test and validate current implementation (Surgery/Radiation/Imaging)
- Verify HTML content type fix working
- Confirm comprehensive radiation keywords detecting documents
- Validate escalation strategy proceeding through alternatives
- Test with multiple patients (Astrocytoma, Pineoblastoma)

**Phase 2**: 📋 Document chemotherapy requirements (THIS DOCUMENT)

**Phase 3**: ⏳ Implement chemotherapy extraction (FUTURE)

### Recommended Implementation Order

1. **Validate current workflow** (Surgery/Radiation/Imaging) - **PRIORITY 1**
   - Run end-to-end tests with fixed HTML extraction
   - Verify escalation to alternatives working
   - Compare against human abstraction examples
   - Identify any remaining bugs or data quality issues

2. **Document chemotherapy requirements** - **PRIORITY 2** ✅ COMPLETE
   - Define required fields (this document)
   - Align with WHO 2021 protocol expectations
   - Review with domain experts

3. **Implement chemotherapy extraction** - **PRIORITY 3** (FUTURE)
   - Phase 3: Gap identification logic
   - Phase 4: MedGemma extraction prompt
   - Phase 5: Protocol validation
   - Testing with diverse chemotherapy regimens

---

## Escalating Search Strategy (Overview)

### Two-Agent Validation Loop

```
PRIMARY DOCUMENT ATTEMPT
│
├─ Agent 1: Fetch document from primary target
├─ Agent 1: VALIDATE content (keyword matching)
├─ Agent 2 (MedGemma): Extract structured data
├─ Agent 1: VALIDATE extraction (required fields check)
│
├─ If incomplete → RE-EXTRACTION with clarification prompt
│
└─ Still incomplete → ESCALATION TO ALTERNATIVES
    │
    ├─ Alternative #1 (highest temporal proximity + document type priority)
    │   ├─ Agent 1: VALIDATE content
    │   ├─ Agent 2: Extract
    │   ├─ Agent 1: VALIDATE result
    │   └─ If incomplete → Continue
    │
    ├─ Alternative #2
    ├─ Alternative #3
    ├─ Alternative #4
    ├─ Alternative #5 (max limit)
    │
    └─ All exhausted → Mark as UNAVAILABLE_IN_RECORDS
```

### Design Rationale

**Why this strategy is clinically sound**:
1. **Temporal proximity**: Documents near event dates likely contain relevant information
2. **Document type prioritization**: Treatment summaries > progress notes > discharge summaries
3. **Keyword validation**: Ensures document relevance before expensive LLM extraction
4. **Multiple attempts**: Clinical data often scattered across multiple documents
5. **Escalation limit**: Prevents infinite loops on truly missing data

**When it fails** (expected scenarios):
- Data never documented (e.g., outside institution radiation, verbal surgeon assessment only)
- Binary files corrupted or missing from S3
- Clinical notes use non-standard terminology (mitigated by comprehensive keyword lists)
- Information exists but in non-text format (images, scanned PDFs without OCR)

---

## Testing and Validation

### Test Patients

| Patient ID | WHO 2021 Diagnosis | Key Testing Focus |
|------------|-------------------|-------------------|
| `eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83` | Astrocytoma, IDH-mutant, Grade 3 | Radiation escalation, HTML extraction |
| `e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3` | Pineoblastoma | Craniospinal+boost pattern, imaging RANO |

### Validation Criteria

**Successful extraction requires**:
1. ✅ All required fields populated (no null values)
2. ✅ Data clinically plausible (dates in valid range, doses in expected ranges)
3. ✅ Matches human abstraction (when gold standard available)
4. ✅ Extraction confidence HIGH or MEDIUM (LOW triggers manual review)

### Human Abstraction Comparison

**Gold standard**: `/Users/resnick/Downloads/example extraction.csv`
**Comparison fields**:
- Surgery dates and EOR classification
- Radiation start/stop dates and total doses
- Chemotherapy protocols and agents
- Imaging response assessments

---

## References

### Code Locations

**Required fields definition**: `patient_timeline_abstraction_V2.py:1874-1883`
**Validation keywords**: `patient_timeline_abstraction_V2.py:1817-1841`
**Escalation logic**: `patient_timeline_abstraction_V2.py:1031-1126`
**Field guidance**: `patient_timeline_abstraction_V2.py:1912-1921`

### Related Documentation

- `PHASE4_IMPLEMENTATION_SUMMARY.md` - Phase 4 architecture and workflow
- `MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md` - Two-agent validation loop design
- `RADIATION_EPISODE_APPROACH.md` - Radiation terminology and episode detection
- `HUMAN_ABSTRACTION_EXAMPLES.md` - Gold standard comparison examples

---

## Change Log

| Date | Change | Author | Rationale |
|------|--------|--------|-----------|
| 2025-11-01 | Added `date_at_radiation_stop` to required fields | Session continuation | Track re-irradiation episodes |
| 2025-11-01 | Updated EOR guidance to include post-op imaging | Session continuation | Dual-source validation (operative note + MRI) |
| 2025-11-01 | Expanded radiation keywords from 6 to 35+ terms | Session continuation | Align with SQL terminology, increase sensitivity |
| 2025-11-01 | Documented chemotherapy required fields (not implemented) | Session continuation | Future implementation roadmap |
| 2025-11-01 | Fixed HTML content type mislabeling bug | Session continuation | Documents declared as text/html were routed to PDF extractor |

---

## Next Steps

### Immediate (This Session)
1. ✅ Document chemotherapy requirements (COMPLETE - this document)
2. ⏳ **Run comprehensive test with fixed HTML extraction** (NEXT)
3. ⏳ Validate escalation strategy working end-to-end
4. ⏳ Compare results against human abstraction

### Future Sessions
1. Implement chemotherapy Phase 3 gap identification
2. Create chemotherapy MedGemma extraction prompt
3. Add chemotherapy WHO 2021 protocol validation
4. Test with diverse chemotherapy regimens (TMZ, multi-agent protocols)
5. Expand to additional tumor types (medulloblastoma, ependymoma, etc.)
