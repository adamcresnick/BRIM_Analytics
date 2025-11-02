# V3 Care Plan Validation Framework - Implementation Plan

**Date**: 2025-11-02
**Status**: PLANNING
**Version**: V3.0 (Evolution from V2.0)

---

## Executive Summary

This document provides a comprehensive, stepwise implementation plan for **Patient Timeline Abstraction V3**, which augments V2's gap-filling approach with a **Care Plan Validation Framework**. The V3 framework:

1. **Preserves ALL V2 functionality** (3,024 lines, 39 methods)
2. **Adds disease-specific care standards** from WHO 2021 Comprehensive Pediatric CNS Tumor Reference
3. **Implements extraction tracking** for free text schema fields and binary documents
4. **Validates care against established protocols** for the patient's specific diagnosis
5. **Makes no guesses or assumptions** - only implements concrete, evidence-based functionality

---

## Table of Contents

1. [V2 Architecture Review](#v2-architecture-review)
2. [V3 Enhancement Strategy](#v3-enhancement-strategy)
3. [Care Plan Validation Framework Design](#care-plan-validation-framework-design)
4. [Implementation Roadmap](#implementation-roadmap)
5. [Code Preservation Map](#code-preservation-map)
6. [Integration Points](#integration-points)
7. [Testing Strategy](#testing-strategy)
8. [Risk Mitigation](#risk-mitigation)

---

## V2 Architecture Review

### Current V2 Structure

**File**: `scripts/patient_timeline_abstraction_V2.py`
**Size**: 3,024 lines
**Methods**: 39
**Classes**: 1 (`PatientTimelineAbstractor`)

### V2 Execution Flow (6 Phases)

```
Phase 1: Load Structured Data
  ├─ v_demographics_flattened
  ├─ v_surgeries_procedures
  ├─ v_chemo_treatment_episodes
  ├─ v_radiation_episode_enrichment
  └─ v_pathology_diagnostics

Phase 2: Construct Initial Timeline
  ├─ Surgery events
  ├─ Radiation events
  ├─ Chemotherapy events
  └─ Pathology events

Phase 3: Identify Extraction Gaps
  ├─ missing_surgery_details
  ├─ missing_radiation_details
  ├─ missing_chemotherapy_details
  └─ missing_imaging_details

Phase 4: Extract from Binary Documents
  ├─ Build document inventory (v_binary_files)
  ├─ Match documents to gaps
  ├─ Extract text (AWS Textract for TIFF/JPEG/PNG, PDF extraction placeholder)
  ├─ MedGemma extraction
  └─ Validation and integration

Phase 4.5: Assess Extraction Completeness
  └─ Compare filled vs unfilled gaps

Phase 5: Protocol Validation (Placeholder)
  └─ Reserved for future care plan validation

Phase 6: Generate Artifact
  └─ Output JSON timeline
```

### V2 Method Inventory (All 39 Methods)

| Line | Method | Purpose | V3 Action |
|------|--------|---------|-----------|
| 198 | `__init__` | Initialize abstractor | **PRESERVE** + enhance |
| 238 | `_load_who_classification` | Load WHO 2021 classification | **PRESERVE** (Fix 8) |
| 297 | `_initialize_empty_cache` | Initialize WHO cache | **PRESERVE** (Fix 8) |
| 321 | `_save_who_classification` | Save WHO to cache | **PRESERVE** (Fix 8) |
| 361 | `_generate_who_classification` | Dynamic WHO classification (Tier 1) | **PRESERVE** (Fix 8) |
| 544 | `_format_pathology_for_who_prompt` | Format pathology for WHO prompt | **PRESERVE** (Fix 8) |
| 622 | `_enhance_classification_with_binary_pathology` | WHO Tier 2 binary fallback | **PRESERVE** (Fix 8) |
| 794 | `_extract_text_from_binary_document` | Extract text router | **PRESERVE** (Fix 6) |
| 832 | `_extract_from_pdf` | PDF extraction (placeholder) | **PRESERVE** (TODO) |
| 839 | `_extract_from_image_textract` | AWS Textract OCR | **PRESERVE** (Fix 6) |
| 874 | `_is_tiff` | TIFF magic number detection | **PRESERVE** (Fix 6) |
| 879 | `run` | Main orchestrator | **PRESERVE** + add Phase 5 |
| 933 | `_phase1_load_structured_data` | Load all schemas | **PRESERVE** + add demographics |
| 1014 | `_phase2_construct_initial_timeline` | Build timeline | **PRESERVE** |
| 1209 | `_phase3_identify_extraction_gaps` | Identify missing data | **PRESERVE** |
| 1322 | `_find_operative_note_binary` | Find surgery document | **PRESERVE** |
| 1362 | `_find_radiation_document` | Find radiation document | **PRESERVE** |
| 1408 | `_find_chemotherapy_document` | Find chemo document | **PRESERVE** |
| 1459 | `_build_patient_document_inventory` | Inventory v_binary_files | **PRESERVE** |
| 1530 | `_find_alternative_documents` | Escalation document search | **PRESERVE** |
| 1725 | `_try_alternative_documents` | Try escalation docs | **PRESERVE** |
| 1822 | `_verify_medgemma_available` | Check Ollama | **PRESERVE** |
| 1843 | `_phase4_extract_from_binaries_placeholder` | Skipped if no agents | **PRESERVE** |
| 1854 | `_phase4_extract_from_binaries` | Binary extraction loop | **PRESERVE** + track |
| 2038 | `_generate_medgemma_prompt` | Prompt router | **PRESERVE** |
| 2054 | `_generate_imaging_prompt` | Imaging prompt | **PRESERVE** |
| 2177 | `_generate_operative_note_prompt` | Surgery prompt | **PRESERVE** |
| 2265 | `_generate_radiation_summary_prompt` | Radiation prompt | **PRESERVE** |
| 2384 | `_generate_chemotherapy_prompt` | Chemo prompt | **PRESERVE** |
| 2409 | `_generate_generic_prompt` | Generic prompt | **PRESERVE** |
| 2429 | `_fetch_binary_document` | Fetch FHIR Binary from S3 | **PRESERVE** |
| 2524 | `_get_patient_chemotherapy_keywords` | Chemo drug list | **PRESERVE** |
| 2554 | `_validate_document_content` | Validate extracted text | **PRESERVE** |
| 2627 | `_validate_extraction_result` | Validate MedGemma output | **PRESERVE** (Fix 8) |
| 2681 | `_retry_extraction_with_clarification` | Retry failed extractions | **PRESERVE** |
| 2754 | `_integrate_extraction_into_timeline` | Merge extraction to timeline | **PRESERVE** (Fix 1) |
| 2807 | `_phase4_5_assess_extraction_completeness` | Gap assessment | **PRESERVE** |
| 2877 | `_phase5_protocol_validation` | **PLACEHOLDER** | **IMPLEMENT** |
| 2930 | `_phase6_generate_artifact` | Output JSON | **PRESERVE** + enhance |

### V2 Data Structures

```python
self.timeline_events = []           # Timeline events
self.extraction_gaps = []           # Identified data gaps
self.binary_extractions = []        # Binary document extractions
self.protocol_validations = []      # Phase 5 validations (EMPTY in V2)
self.completeness_assessment = {}   # Gap assessment results
```

### V2 Dependencies

- **Agents**: MedGemmaAgent, BinaryFileAgent (multi-agent framework)
- **AWS**: Athena, S3, Textract
- **LLM**: Ollama (gemma2:27b)
- **Python**: boto3, pathlib, json, logging

---

## V3 Enhancement Strategy

### Design Principles

1. **Augmentation, Not Replacement**: V3 adds functionality to V2, never removes
2. **Backward Compatibility**: V2 workflows continue to function identically
3. **Opt-In Complexity**: Care plan validation is additive (can be disabled)
4. **Evidence-Based**: All care standards sourced from WHO 2021 PDF
5. **Transparent Tracking**: Every extraction tracked with source attribution

### What V3 Adds

#### 1. Disease-Specific Care Standards (WHO 2021)

**Source**: `Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf` (394.4 KB, 38 pages)

**Coverage**:
- Pediatric Low-Grade Gliomas (diffuse & circumscribed)
  - Pilocytic Astrocytoma
  - SEGA (Tuberous Sclerosis)
  - Pleomorphic Xanthoastrocytoma
  - Ganglioglioma, DNET
- Pediatric High-Grade Gliomas
  - DIPG (H3 K27-altered)
  - H3 G34-mutant hemispheric glioma
  - Infant-type hemispheric glioma
- Ependymal Tumors
- Embryonal Tumors
  - Medulloblastoma (WNT, SHH, Group 3/4)
  - ATRT
  - ETMR
- Germ Cell Tumors
- Craniopharyngioma
- Tumor Predisposition Syndromes

**Extraction Strategy**:
1. Parse WHO PDF to extract treatment protocols per diagnosis
2. Map WHO classification (from V2 dynamic WHO classification) to care standards
3. Create diagnosis → expected care mappings

#### 2. Patient Demographics Integration

**Source**: `v_patient_demographics` (schema TBD - needs query)

**Purpose**:
- Age at diagnosis → age-appropriate treatment protocols
- Gender → gender-specific risk factors (e.g., pineal germinoma male:female 10:1)
- Genetic syndromes → predisposition-aware care (NF1, NF2, TSC, Li-Fraumeni, etc.)

#### 3. Extraction Tracking Framework

**New Data Structure**:
```python
self.extraction_tracker = {
    'free_text_schema_fields': {
        'v_pathology_diagnostics': {
            'fields_queried': ['diagnostic_name', 'result_value', ...],
            'rows_found': 21675,
            'abstracted_count': 150,
            'abstraction_rate': 0.007
        },
        # ... other schemas
    },
    'binary_documents': {
        'fetched': [
            {
                'binary_id': 'ez99FproUH0nx9RO4d0Dxn0nrc9rzkbd_apMU2ZLJ6H03',
                'content_type': 'image/tiff',
                'extraction_method': 'AWS_Textract',
                'text_length': 1481,
                'gap_type': 'missing_radiation_details',
                'success': True,
                'keywords_found': ['radiation', 'dose', 'gy', ...]
            },
            # ... all fetched docs
        ],
        'attempted_count': 50,
        'success_count': 35,
        'success_rate': 0.70
    },
    'extraction_timeline': [
        {'timestamp': '2025-11-02T17:30:00', 'phase': 'Phase 1', 'action': 'Loaded v_pathology_diagnostics', 'rows': 21675},
        {'timestamp': '2025-11-02T17:30:05', 'phase': 'Phase 4', 'action': 'Extracted TIFF radiation doc', 'binary_id': 'ez99...'},
        # ... chronological extraction log
    ]
}
```

#### 4. Care Plan Validation Framework

**Purpose**: Validate that patient received evidence-based care per WHO 2021 standards

**Validation Categories**:
1. **Diagnostic Workup Validation**
   - Molecular testing performed (BRAF, H3 K27M, etc.)
   - Imaging adequacy (MRI brain + spine for medulloblastoma)
   - CSF cytology for dissemination (if indicated)

2. **Treatment Protocol Validation**
   - Surgery: Extent of resection appropriate for diagnosis
   - Radiation: Dose and field match protocol (e.g., CSI 23.4 Gy for average-risk medullo)
   - Chemotherapy: Regimen matches diagnosis (e.g., carboplatin/vincristine for pLGG)
   - Targeted therapy: If actionable mutation present (e.g., BRAF V600E → MEK inhibitor)

3. **Surveillance Adequacy**
   - Follow-up imaging frequency
   - Endocrine monitoring (post-RT)
   - Long-term effects monitoring

4. **Deviation Flagging**
   - Missing expected treatments
   - Off-protocol dosing
   - Missed molecular testing opportunities

**Implementation**:
```python
def _phase5_protocol_validation(self):
    """
    Phase 5: Validate care against disease-specific WHO 2021 protocols

    Steps:
    1. Retrieve WHO classification from Phase 1
    2. Load expected care protocol from parsed WHO PDF
    3. Compare timeline events to expected protocol
    4. Identify deviations, missing elements, or adherence
    5. Generate validation report
    """
    validation_results = {
        'diagnosis': self.who_2021_classification,
        'expected_protocol': {},  # from WHO PDF
        'actual_care': {},         # from timeline
        'adherence_score': 0.0,
        'deviations': [],
        'missing_elements': [],
        'positive_findings': []
    }

    # Implementation in V3
    self.protocol_validations.append(validation_results)
```

---

## Care Plan Validation Framework Design

### Component 1: WHO PDF Parser

**New File**: `scripts/who_protocol_parser.py`

**Purpose**: Extract structured care protocols from WHO 2021 PDF

**Output Schema**:
```json
{
  "diagnosis": "Pilocytic Astrocytoma",
  "who_grade": 1,
  "expected_workup": {
    "imaging": ["MRI brain with contrast"],
    "molecular": ["BRAF alteration testing (KIAA1549-BRAF fusion or BRAF V600E)"],
    "csf_staging": false
  },
  "treatment_protocol": {
    "first_line": {
      "surgery": "Maximal safe resection (curative if gross total resection)",
      "chemotherapy": {
        "indication": "If unresectable or progressive",
        "regimens": [
          "Carboplatin/Vincristine (Packer regimen) for 12-18 months",
          "Vinblastine monotherapy for 70 weeks"
        ]
      },
      "radiation": {
        "indication": "Reserved for refractory cases or older teens",
        "dose": "54 Gy focal radiation",
        "notes": "Avoid in young children due to long-term toxicity"
      },
      "targeted_therapy": {
        "indication": "If BRAF V600E or NF1-related",
        "agents": ["Selumetinib (MEK inhibitor)", "Dabrafenib/Trametinib"]
      }
    }
  },
  "surveillance": {
    "imaging_frequency": "MRI every 3-6 months for 2 years, then annually",
    "endocrine_monitoring": "If radiation given: TSH, IGF-1, cortisol annually"
  },
  "prognostic_factors": {
    "5_year_survival": "~95% if gross total resection",
    "progression_free_survival": "~42% at 10 years (indolent recurrences common)"
  }
}
```

**Implementation Steps**:
1. Use PyPDF2 or pdfplumber to extract text from WHO PDF
2. Use regex/NLP to identify diagnosis sections
3. Parse treatment recommendations into structured format
4. Store in `cache/who_protocols_cache.json`

### Component 2: Demographics Loader

**New Method**: `_load_patient_demographics()`

**Integration**: Add to Phase 1

```python
def _load_patient_demographics(self):
    """Load patient demographics from v_patient_demographics"""
    query = f"""
    SELECT
        patient_fhir_id,
        age_at_diagnosis,
        gender,
        race_ethnicity,
        genetic_syndrome_flags,  -- if available
        enrollment_date,
        last_contact_date
    FROM v_patient_demographics
    WHERE patient_fhir_id = '{self.athena_patient_id}'
    """

    demographics = query_athena(query, "Loading patient demographics")

    self.patient_demographics = demographics[0] if demographics else {}

    # Extract age-specific protocol considerations
    age = self.patient_demographics.get('age_at_diagnosis', None)
    if age and age < 3:
        self.protocol_considerations.append('Infant protocol: avoid/delay radiation')

    logger.info(f"Demographics: Age={age}, Gender={self.patient_demographics.get('gender')}")
```

### Component 3: Extraction Tracker

**New Methods**:
- `_init_extraction_tracker()` - Initialize tracker in `__init__`
- `_track_schema_query(schema_name, fields, row_count)` - Track Phase 1 queries
- `_track_binary_fetch(binary_id, content_type, success, metadata)` - Track Phase 4 fetches
- `_track_extraction_attempt(gap, document, result)` - Track MedGemma extractions
- `_generate_extraction_report()` - Summary in Phase 6

**Integration Points**:
- **Phase 1**: After each schema query, call `_track_schema_query()`
- **Phase 4**: Before/after each binary fetch, call `_track_binary_fetch()`
- **Phase 4**: After each MedGemma extraction, call `_track_extraction_attempt()`
- **Phase 6**: Call `_generate_extraction_report()` before JSON output

### Component 4: Protocol Validator

**New Methods**:
- `_load_expected_protocol()` - Load WHO protocol for patient's diagnosis
- `_map_timeline_to_protocol()` - Map actual care to expected protocol
- `_calculate_adherence_score()` - Quantify protocol adherence
- `_identify_deviations()` - Flag missing or off-protocol care
- `_generate_validation_report()` - Human-readable validation summary

**Execution in Phase 5**:
```python
def _phase5_protocol_validation(self):
    """Validate care against disease-specific WHO 2021 protocols"""
    logger.info("\n" + "="*80)
    logger.info("PHASE 5: PROTOCOL VALIDATION")
    logger.info("="*80)

    # 1. Get WHO classification
    diagnosis = self.who_2021_classification.get('who_2021_classification', 'Unknown')

    if diagnosis == 'Unknown' or diagnosis == 'Insufficient data':
        logger.warning("⚠️  Cannot validate protocol - WHO classification unknown")
        self.protocol_validations.append({
            'status': 'SKIPPED',
            'reason': 'No WHO classification available'
        })
        return

    # 2. Load expected protocol from WHO PDF cache
    expected_protocol = self._load_expected_protocol(diagnosis)

    if not expected_protocol:
        logger.warning(f"⚠️  No protocol found for diagnosis: {diagnosis}")
        self.protocol_validations.append({
            'status': 'SKIPPED',
            'reason': f'No protocol available for {diagnosis}'
        })
        return

    # 3. Map timeline events to protocol elements
    actual_care = self._map_timeline_to_protocol(expected_protocol)

    # 4. Calculate adherence
    adherence_score = self._calculate_adherence_score(expected_protocol, actual_care)

    # 5. Identify deviations
    deviations = self._identify_deviations(expected_protocol, actual_care)

    # 6. Store validation results
    validation_result = {
        'diagnosis': diagnosis,
        'expected_protocol': expected_protocol,
        'actual_care': actual_care,
        'adherence_score': adherence_score,
        'deviations': deviations,
        'validation_date': datetime.now().isoformat()
    }

    self.protocol_validations.append(validation_result)

    # 7. Log summary
    logger.info(f"\n✅ Protocol Validation Complete")
    logger.info(f"   Diagnosis: {diagnosis}")
    logger.info(f"   Adherence Score: {adherence_score:.1%}")
    logger.info(f"   Deviations: {len(deviations)}")
```

---

## Implementation Roadmap

### Phase A: Preparation (Week 1)

**Goal**: Set up V3 infrastructure without modifying V2

**Tasks**:
1. ✅ Create this implementation plan document
2. Copy V2 to V3: `cp patient_timeline_abstraction_V2.py patient_timeline_abstraction_V3.py`
3. Create WHO protocol parser: `who_protocol_parser.py`
4. Query v_patient_demographics schema (fix Athena query)
5. Parse WHO PDF into structured protocols
6. Create `cache/who_protocols_cache.json`

**Deliverables**:
- `patient_timeline_abstraction_V3.py` (identical to V2)
- `who_protocol_parser.py`
- `cache/who_protocols_cache.json` (parsed WHO protocols)
- `v_patient_demographics.schema.json` (documented schema)

**Testing**:
- Run V3 on test patient → should produce identical output to V2

### Phase B: Extraction Tracking (Week 2)

**Goal**: Add extraction tracking without changing V2 behavior

**Tasks**:
1. Add `extraction_tracker` data structure to `__init__`
2. Implement `_init_extraction_tracker()`
3. Implement `_track_schema_query()`
4. Implement `_track_binary_fetch()`
5. Implement `_track_extraction_attempt()`
6. Implement `_generate_extraction_report()`
7. Integrate tracking calls in Phases 1, 4, 6

**Deliverables**:
- V3 with extraction tracking enabled
- `extraction_report` section in output JSON

**Testing**:
- Run V3 on test patient
- Verify extraction report shows:
  - v_pathology_diagnostics: 21,675 rows queried
  - Binary docs: X attempted, Y successful
  - Extraction timeline with timestamps

### Phase C: Demographics Integration (Week 2)

**Goal**: Load patient demographics and use for protocol selection

**Tasks**:
1. Implement `_load_patient_demographics()`
2. Add demographics query to Phase 1
3. Store `self.patient_demographics`
4. Add age-based protocol considerations

**Deliverables**:
- Demographics loaded in Phase 1
- Age-appropriate protocol flags set

**Testing**:
- Verify demographics loaded for test patient
- Verify age < 3 triggers infant protocol flag

### Phase D: Protocol Validation Framework (Week 3-4)

**Goal**: Implement full Phase 5 care plan validation

**Tasks**:
1. Implement `_load_expected_protocol(diagnosis)`
2. Implement `_map_timeline_to_protocol()`
3. Implement `_calculate_adherence_score()`
4. Implement `_identify_deviations()`
5. Implement `_generate_validation_report()`
6. Fully implement `_phase5_protocol_validation()`
7. Add `protocol_validation` section to output JSON

**Deliverables**:
- Complete Phase 5 implementation
- Protocol validation report in output

**Testing**:
- Test on patient with Pilocytic Astrocytoma
  - Verify expected protocol loaded
  - Verify surgery/chemo/radiation mapped correctly
  - Verify adherence score calculated
  - Verify deviations identified (e.g., missing BRAF testing)

### Phase E: Integration & Testing (Week 5)

**Goal**: End-to-end testing and validation

**Tasks**:
1. Run V3 on all 9 test patients
2. Compare V3 output to V2 output (should match except for new sections)
3. Validate protocol validation results against manual chart review
4. Performance testing (ensure V3 not significantly slower than V2)
5. Documentation updates

**Deliverables**:
- V3 tested on 9 patients
- Validation report comparing V2 vs V3 outputs
- Performance benchmarks

**Testing**:
- V3 produces identical timeline events as V2
- V3 adds protocol validation without errors
- V3 extraction tracker comprehensive and accurate

---

## Code Preservation Map

### Methods Preserved Verbatim (No Changes)

These 32 methods will be **copied exactly** from V2 to V3:

```
_load_who_classification
_initialize_empty_cache
_save_who_classification
_generate_who_classification
_format_pathology_for_who_prompt
_enhance_classification_with_binary_pathology
_extract_text_from_binary_document
_extract_from_pdf
_extract_from_image_textract
_is_tiff
_phase2_construct_initial_timeline
_phase3_identify_extraction_gaps
_find_operative_note_binary
_find_radiation_document
_find_chemotherapy_document
_build_patient_document_inventory
_find_alternative_documents
_try_alternative_documents
_verify_medgemma_available
_phase4_extract_from_binaries_placeholder
_generate_medgemma_prompt
_generate_imaging_prompt
_generate_operative_note_prompt
_generate_radiation_summary_prompt
_generate_chemotherapy_prompt
_generate_generic_prompt
_fetch_binary_document
_get_patient_chemotherapy_keywords
_validate_document_content
_validate_extraction_result
_retry_extraction_with_clarification
_phase4_5_assess_extraction_completeness
```

### Methods Enhanced (Augmented, Not Replaced)

These 7 methods will **add functionality** while preserving existing behavior:

| Method | V2 Functionality | V3 Enhancement |
|--------|-----------------|----------------|
| `__init__` | Initialize data structures | Add `extraction_tracker`, `patient_demographics`, `protocol_considerations` |
| `run` | Execute 6 phases | Keep same flow, Phase 5 now functional (was placeholder) |
| `_phase1_load_structured_data` | Load 4 schemas | Add `_load_patient_demographics()` call |
| `_phase4_extract_from_binaries` | Binary extraction loop | Add tracking calls: `_track_binary_fetch()`, `_track_extraction_attempt()` |
| `_integrate_extraction_into_timeline` | Merge extraction data | Add tracking: log successful merges to `extraction_tracker` |
| `_phase5_protocol_validation` | Empty placeholder | **Full implementation** of care plan validation |
| `_phase6_generate_artifact` | Output JSON | Add `extraction_report` and `protocol_validation` sections to JSON |

### Methods Added (New in V3)

These 11 methods are **new** in V3:

```
_init_extraction_tracker()              # Initialize tracking data structure
_track_schema_query()                   # Track Phase 1 schema queries
_track_binary_fetch()                   # Track Phase 4 binary document fetches
_track_extraction_attempt()             # Track MedGemma extraction attempts
_generate_extraction_report()           # Generate extraction summary

_load_patient_demographics()            # Load demographics from v_patient_demographics

_load_expected_protocol()               # Load WHO protocol for diagnosis
_map_timeline_to_protocol()             # Map actual care to expected protocol
_calculate_adherence_score()            # Calculate adherence percentage
_identify_deviations()                  # Identify missing/off-protocol care
_generate_validation_report()           # Human-readable validation report
```

---

## Integration Points

### Integration Point 1: `__init__` Enhancement

**Location**: Line 198
**V2 Code**:
```python
def __init__(self, patient_id: str, output_dir: Path, max_extractions: Optional[int] = None, force_reclassify: bool = False):
    # ... existing initialization ...

    # Data structures
    self.timeline_events = []
    self.extraction_gaps = []
    self.binary_extractions = []
    self.protocol_validations = []
    self.completeness_assessment = {}
```

**V3 Enhancement**:
```python
def __init__(self, patient_id: str, output_dir: Path, max_extractions: Optional[int] = None, force_reclassify: bool = False):
    # ... existing initialization (PRESERVE) ...

    # Data structures (PRESERVE)
    self.timeline_events = []
    self.extraction_gaps = []
    self.binary_extractions = []
    self.protocol_validations = []
    self.completeness_assessment = {}

    # NEW: V3 data structures
    self.patient_demographics = {}
    self.protocol_considerations = []
    self.extraction_tracker = self._init_extraction_tracker()  # NEW METHOD
```

### Integration Point 2: Phase 1 Demographics

**Location**: Line 933 (`_phase1_load_structured_data`)
**V2 Code**:
```python
def _phase1_load_structured_data(self):
    logger.info("\n" + "="*80)
    logger.info("PHASE 1: LOADING STRUCTURED DATA")
    logger.info("="*80)

    # Load demographics
    # Load surgeries
    # Load chemotherapy
    # Load radiation
    # Load pathology
```

**V3 Enhancement**:
```python
def _phase1_load_structured_data(self):
    logger.info("\n" + "="*80)
    logger.info("PHASE 1: LOADING STRUCTURED DATA")
    logger.info("="*80)

    # Load demographics (EXISTING)
    demographics_query = f"SELECT * FROM v_demographics_flattened WHERE patient_fhir_id = '{self.athena_patient_id}'"
    demographics = query_athena(demographics_query, "Loading patient demographics")
    # ... existing code ...

    # NEW: Load detailed demographics
    self._load_patient_demographics()  # NEW METHOD
    self._track_schema_query('v_patient_demographics', ['age_at_diagnosis', 'gender', ...], len(self.patient_demographics))  # NEW

    # Load surgeries (EXISTING - unchanged)
    # ...
```

### Integration Point 3: Phase 4 Tracking

**Location**: Line 1854 (`_phase4_extract_from_binaries`)
**V2 Code**:
```python
for gap in gaps_needing_extraction:
    # ... find documents ...

    for doc in candidate_docs:
        # Fetch binary document
        extracted_text = self._fetch_binary_document(doc['binary_id'])

        if extracted_text:
            # ... MedGemma extraction ...
            result = self.medgemma_agent.extract(full_prompt)

            # ... validation ...
```

**V3 Enhancement**:
```python
for gap in gaps_needing_extraction:
    # ... find documents (PRESERVE) ...

    for doc in candidate_docs:
        # Fetch binary document (PRESERVE)
        extracted_text = self._fetch_binary_document(doc['binary_id'])

        # NEW: Track fetch attempt
        self._track_binary_fetch(
            binary_id=doc['binary_id'],
            content_type=doc['content_type'],
            success=extracted_text is not None,
            metadata={'gap_type': gap['gap_type'], 'text_length': len(extracted_text) if extracted_text else 0}
        )

        if extracted_text:
            # ... MedGemma extraction (PRESERVE) ...
            result = self.medgemma_agent.extract(full_prompt)

            # NEW: Track extraction attempt
            self._track_extraction_attempt(
                gap=gap,
                document=doc,
                result={'success': result.success, 'confidence': result.confidence}
            )

            # ... validation (PRESERVE) ...
```

### Integration Point 4: Phase 5 Implementation

**Location**: Line 2877 (`_phase5_protocol_validation`)
**V2 Code**:
```python
def _phase5_protocol_validation(self):
    """
    Phase 5: Protocol validation placeholder

    Future implementation: Validate patient care against established protocols
    """
    logger.info("\n" + "="*80)
    logger.info("PHASE 5: PROTOCOL VALIDATION (Placeholder)")
    logger.info("="*80)
    logger.info("⏭️  Protocol validation not yet implemented")

    # Placeholder for future protocol validation
    self.protocol_validations.append({
        'status': 'not_implemented',
        'note': 'Protocol validation will be added in future version'
    })
```

**V3 Full Implementation**: (See "Care Plan Validation Framework Design" section above)

### Integration Point 5: Phase 6 Output Enhancement

**Location**: Line 2930 (`_phase6_generate_artifact`)
**V2 Code**:
```python
def _phase6_generate_artifact(self):
    # ... existing code ...

    output_data = {
        'patient_id': self.athena_patient_id,
        'who_2021_classification': self.who_2021_classification,
        'timeline_events': self.timeline_events,
        'extraction_gaps': self.extraction_gaps,
        'binary_extractions': self.binary_extractions,
        'protocol_validations': self.protocol_validations,
        'completeness_assessment': self.completeness_assessment,
        'generation_timestamp': datetime.now().isoformat()
    }
```

**V3 Enhancement**:
```python
def _phase6_generate_artifact(self):
    # ... existing code (PRESERVE) ...

    # NEW: Generate extraction report
    extraction_report = self._generate_extraction_report()

    output_data = {
        'patient_id': self.athena_patient_id,
        'who_2021_classification': self.who_2021_classification,
        'patient_demographics': self.patient_demographics,  # NEW
        'timeline_events': self.timeline_events,
        'extraction_gaps': self.extraction_gaps,
        'binary_extractions': self.binary_extractions,
        'protocol_validations': self.protocol_validations,  # Now populated by Phase 5
        'completeness_assessment': self.completeness_assessment,
        'extraction_report': extraction_report,  # NEW
        'generation_timestamp': datetime.now().isoformat()
    }
```

---

## Testing Strategy

### Unit Testing

**Test File**: `tests/test_patient_timeline_abstraction_V3.py`

**Test Categories**:
1. **V2 Regression Tests**: Ensure all V2 functionality preserved
   - Test all 39 V2 methods produce identical outputs
   - Compare V3 timeline events to V2 timeline events (should match)

2. **New Functionality Tests**: Validate V3 enhancements
   - Test `_init_extraction_tracker()` initializes correct structure
   - Test `_track_schema_query()` logs schema queries
   - Test `_track_binary_fetch()` logs binary fetches
   - Test `_load_patient_demographics()` loads demographics
   - Test `_load_expected_protocol()` loads WHO protocols
   - Test `_calculate_adherence_score()` calculates correctly

3. **Integration Tests**: End-to-end workflows
   - Test V3 on Pilocytic Astrocytoma patient
   - Test V3 on Medulloblastoma patient
   - Test V3 on DIPG patient

### Acceptance Testing

**Test Patient**: `eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83` (Gliomatosis cerebri)

**Test Criteria**:
1. ✅ V3 produces same timeline events as V2
2. ✅ V3 adds extraction report showing:
   - v_pathology_diagnostics: 21,675 rows queried
   - Binary documents: 50 attempted, 35 successful
   - Extraction timeline with 100+ entries
3. ✅ V3 loads patient demographics (age=12, gender=male)
4. ✅ V3 performs protocol validation:
   - Diagnosis: Gliomatosis cerebri
   - Expected protocol: Radiation + temozolomide (per WHO)
   - Actual care: Radiation (11/02/2017 - 12/20/2017), 54 Gy
   - Adherence score: 75% (radiation done, chemo unclear)
   - Deviations: Molecular testing not documented

### Performance Testing

**Benchmarks**:
- V2 runtime: ~60 seconds for 50 extractions
- V3 runtime: ≤ 75 seconds for 50 extractions (25% overhead acceptable)
- Memory: ≤ 512 MB

---

## Risk Mitigation

### Risk 1: Breaking V2 Functionality

**Mitigation**:
- Copy V2 to V3 (never modify V2)
- Run regression tests after every change
- Use git branches: `feature/v3-extraction-tracking`, `feature/v3-protocol-validation`
- Code review before merging

### Risk 2: WHO PDF Parsing Errors

**Mitigation**:
- Manual validation of parsed protocols (spot-check 10 diagnoses)
- Fallback: if protocol not found, skip validation (don't fail)
- Version WHO PDF cache (track which version parsed)

### Risk 3: v_patient_demographics Schema Unknown

**Mitigation**:
- Query schema first before implementation
- If schema unavailable, make demographics optional
- Gracefully degrade: if no demographics, skip age-based protocol selection

### Risk 4: Performance Degradation

**Mitigation**:
- Profile V3 to identify bottlenecks
- Cache WHO protocols (don't re-parse PDF on every run)
- Make extraction tracking lightweight (no expensive operations)

### Risk 5: Incomplete WHO Protocol Coverage

**Mitigation**:
- Start with 5 most common diagnoses (Pilocytic, Medulloblastoma, DIPG, Ependymoma, ATRT)
- Add "Protocol not available" graceful degradation
- Incrementally expand protocol coverage

---

## Conclusion

This implementation plan provides a **concrete, stepwise strategy** for evolving Patient Timeline Abstraction from V2 to V3. The plan:

- **Preserves ALL V2 functionality** (32 methods copied verbatim, 7 augmented, 0 removed)
- **Adds Care Plan Validation Framework** that validates care against WHO 2021 standards
- **Implements Extraction Tracking** for transparency and audit trails
- **Integrates Patient Demographics** for age-appropriate protocol selection
- **Makes no guesses or assumptions** - all protocols sourced from WHO PDF
- **Provides clear milestones** (5 implementation phases over 5 weeks)
- **Mitigates risks** with regression testing, fallbacks, and graceful degradation

**Next Step**: User approval of this plan before proceeding with Phase A (Preparation).

---

**Document Version**: 1.0
**Last Updated**: 2025-11-02
**Author**: Claude (Anthropic)
**Reviewed By**: [Pending User Review]
