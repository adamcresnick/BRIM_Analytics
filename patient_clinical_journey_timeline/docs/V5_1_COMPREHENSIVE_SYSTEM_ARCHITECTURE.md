# V5.1: Comprehensive Clinical Timeline System Architecture

**Date**: 2025-11-12
**Version**: V5.1 (with Phase 0 Diagnostic Reasoning & Phase 7 QA/QC)
**Status**: ✅ CODE COMPLETE - Ready for Testing
**Purpose**: Complete system knowledge transfer for future agents

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Purpose & Capabilities](#system-purpose--capabilities)
3. [Complete Architecture](#complete-architecture)
4. [Core Modules & File Structure](#core-modules--file-structure)
5. [Data Sources & Infrastructure](#data-sources--infrastructure)
6. [Execution Workflow](#execution-workflow)
7. [Code Objects & Key Classes](#code-objects--key-classes)
8. [Expected Behavior & Outputs](#expected-behavior--outputs)
9. [Running the System](#running-the-system)
10. [Testing & Validation](#testing--validation)
11. [Known Issues & Limitations](#known-issues--limitations)
12. [Future Development](#future-development)

---

## Executive Summary

### What This System Does

The **RADIANT Clinical Timeline Abstraction System** extracts comprehensive, structured patient timelines from FHIR-based EHR data for pediatric and adult CNS tumor patients. It produces:

1. **WHO 2021 integrated diagnoses** with molecular classification
2. **Complete treatment timelines** with surgery, chemotherapy, radiation, imaging
3. **Treatment ordinality** (1st surgery, 2nd line chemo, 3rd radiation course)
4. **Protocol matching** (identifies which clinical trials patients enrolled in)
5. **Quality assurance** via Investigation Engine validation (Phase 7)
6. **Diagnostic reasoning validation** with biological plausibility checking (Phase 0)

### Key Innovations

- **3-Tier Reasoning Architecture**: Rules → MedGemma LLM → Investigation Engine
- **Diagnostic Reasoning Infrastructure** (Phase 0): Multi-source evidence aggregation with conflict detection
- **Multi-Source Adjudication**: Combines operative notes + post-op imaging for extent of resection
- **Protocol Knowledge Base**: 42 pediatric/adult oncology protocols with signature agent matching
- **Phase 7 QA/QC**: End-to-end validation detecting treatment-diagnosis mismatches
- **Intelligent Date Adjudication**: 4-tier cascade for chemotherapy dates (V4.8)
- **Resume from Checkpoints**: Can restart from any phase after interruption

### Current State (V5.1)

**✅ CODE COMPLETE** - All diagnostic reasoning infrastructure implemented:
- Phase 0.1: Multi-source evidence aggregation (Tier 2A/2B/2C)
- Phase 0.2: WHO triage enhancement (Tier 2A/2B/2C)
- Phase 0.3: DiagnosisValidator (biological plausibility)
- Phase 0.4: Integration into WHO workflow
- Phase 7: Investigation Engine QA/QC

**🎯 NEXT**: Testing on Patient 6 (medulloblastoma) to validate Phase 0/7 implementations

---

## System Purpose & Capabilities

### Primary Use Cases

1. **Clinical Trial Matching**: Identify patients who received specific protocols (e.g., "all IDH-mutant patients on Stupp Protocol")
2. **Outcomes Research**: Calculate survival metrics (PFS, OS) stratified by treatment
3. **Quality Assurance**: Detect protocol deviations, treatment-diagnosis mismatches
4. **Clinical Summaries**: Generate I-PASS handoff-style patient summaries
5. **Regulatory Reporting**: FDA-ready data with full provenance/audit trails

### Supported Tumor Types

- **Pediatric CNS tumors**: Medulloblastoma, ependymoma, AT/RT, DIPG, infant brain tumors
- **Adult CNS tumors**: Glioblastoma, IDH-mutant astrocytoma, oligodendroglioma
- **Leukemia/Lymphoma**: T-ALL, B-NHL
- **Solid tumors**: Neuroblastoma, Wilms tumor

### Key Features

| Feature | Description | Phase |
|---------|-------------|-------|
| WHO 2021 Classification | Molecular-informed tumor classification | Phase 0 |
| Diagnostic Evidence Aggregation | Collect diagnosis mentions from 9 clinical sources | Phase 0.1 |
| WHO Triage Enhancement | 3-tier cascade for section selection | Phase 0.2 |
| Biological Plausibility | Detects impossible marker-diagnosis combinations | Phase 0.3 |
| Treatment Timelines | Surgery, chemo, radiation with dates | Phases 1-2 |
| Treatment Ordinality | 1st/2nd/3rd line, surgery sequence | Phase 2.5 |
| Protocol Matching | Identifies clinical trial enrollment | Phase 5.0 |
| Investigation Engine QA/QC | End-to-end validation | Phase 7 |
| Gap Remediation | Multi-tier note search for missing data | Phase 2.2 |
| Binary Document Extraction | MedGemma extraction from PDFs/images | Phase 4 |
| Clinical Summaries | Resident-style I-PASS handoff | Phase 6 |

---

## Complete Architecture

### Phase Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 0: DIAGNOSTIC REASONING INFRASTRUCTURE                        │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 0.1: Multi-Source Evidence Aggregation                       │
│   └─ DiagnosticEvidenceAggregator                                  │
│      ├─ Tier 2A: Pathology + Problem Lists (keyword)              │
│      ├─ Tier 2B: Imaging + Notes + Discharge (MedGemma)           │
│      └─ Tier 2C: Alternative sources (Investigation Engine)        │
│                                                                     │
│ Phase 0.2: WHO Reference Triage Enhancement                        │
│   └─ WHOReferenceTriageEnhanced                                    │
│      ├─ Tier 2A: Rule-based (APC, CTNNB1, IDH, age)              │
│      ├─ Tier 2B: MedGemma clinical reasoning                       │
│      └─ Tier 2C: Investigation Engine conflict detection           │
│                                                                     │
│ Phase 0.3: Biological Plausibility Validation                      │
│   └─ DiagnosisValidator                                            │
│      └─ IMPOSSIBLE_COMBINATIONS (e.g., APC + Glioblastoma)        │
│                                                                     │
│ Phase 0.4: WHO Classification with Diagnostic Anchoring            │
│   └─ _generate_who_classification()                                │
│      └─ Integrates Phases 0.1-0.3 before Stage 1 extraction       │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1: STRUCTURED DATA LOADING                                    │
├─────────────────────────────────────────────────────────────────────┤
│ Query Athena views for all structured data:                         │
│   • v_demographics (age, gender)                                     │
│   • v_pathology_diagnostics (molecular markers)                      │
│   • v_procedures_tumor (surgeries)                                   │
│   • v_chemo_treatment_episodes (chemotherapy)                        │
│   • v_radiation_episode_enrichment (radiation)                       │
│   • v_imaging (MRI/CT with reports)                                  │
│   • v_visits_unified (encounters)                                    │
│                                                                     │
│ V4.1 Enhancements:                                                  │
│   • Institution tracking (3-tier extraction)                         │
│   • Tumor location mapping (CBTN anatomical codes)                   │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2: TIMELINE CONSTRUCTION                                      │
├─────────────────────────────────────────────────────────────────────┤
│ Build initial timeline events from Phase 1 data:                    │
│   • surgery, chemotherapy_start/end, radiation_start/end, imaging   │
│                                                                     │
│ Phase 2.1: Minimal Completeness Validation                          │
│   └─ Validate CORE timeline (WHO + surgeries required)             │
│                                                                     │
│ Phase 2.2: Core Timeline Gap Remediation                            │
│   ├─ Multi-tier chemotherapy end date search                        │
│   ├─ Multi-tier radiation end date search                           │
│   └─ Multi-source extent of resection (operative notes + imaging)   │
│                                                                     │
│ Phase 2.5: Treatment Ordinality                                     │
│   ├─ Surgery ordinality (1st, 2nd, 3rd surgery)                    │
│   ├─ Chemotherapy treatment lines (1st, 2nd, 3rd line)             │
│   └─ Radiation courses (1st, 2nd, 3rd course)                      │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3: GAP IDENTIFICATION                                         │
├─────────────────────────────────────────────────────────────────────┤
│ Identify missing data for binary extraction:                        │
│   • Missing EOR values                                               │
│   • Missing radiation details                                        │
│   • Missing imaging conclusions                                      │
│                                                                     │
│ Phase 3.5: V_Imaging EOR Enrichment                                 │
│   └─ Query v_imaging for post-op MRI/CT (structured EOR)           │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 4: BINARY EXTRACTION WITH MEDGEMMA                            │
├─────────────────────────────────────────────────────────────────────┤
│   • Build patient document inventory from v_binary_files            │
│   • Prioritize gaps (HIGHEST → HIGH → MEDIUM → LOW)                │
│   • Extract from PDFs/images with MedGemma LLM                      │
│   • EOROrchestrator adjudicates operative note vs imaging EOR       │
│                                                                     │
│ Phase 4.5: Completeness Assessment                                  │
│   └─ Assess remaining gaps, compute success rates                   │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 5: PROTOCOL VALIDATION & THERAPEUTIC APPROACH                 │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 5.0: Therapeutic Approach Framework (V5.0)                    │
│   ├─ Treatment line detection                                       │
│   ├─ Regimen matching (42 protocol knowledge base)                 │
│   │   ├─ Signature agent matching (e.g., nelarabine → T-ALL)      │
│   │   ├─ Radiation fingerprints (e.g., CSI 18 Gy → SJMB12)        │
│   │   └─ Indication-based matching                                 │
│   ├─ Cycle detection                                               │
│   ├─ Response assessment integration                               │
│   └─ Clinical endpoints calculation (PFS, OS)                       │
│                                                                     │
│ Phase 5 (Original): Protocol Validation                             │
│   └─ Validate radiation doses against WHO 2021 standards           │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 6: ARTIFACT GENERATION                                        │
├─────────────────────────────────────────────────────────────────────┤
│   • Generate final JSON artifact with full provenance               │
│   • V4.8: Enhanced timeline visualization                           │
│   • V4.8: Clinical summary (I-PASS resident handoff)               │
│   • Save checkpoints for resumability                               │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 7: INVESTIGATION ENGINE END-TO-END QA/QC (NEW in V5.1)       │
├─────────────────────────────────────────────────────────────────────┤
│ InvestigationEngineQAQC validates complete timeline:                │
│   ├─ Temporal consistency (treatment after diagnosis)               │
│   ├─ Protocol coherence (treatment matches diagnosis)               │
│   │   └─ Medulloblastoma → expects CSI (not focal RT)             │
│   ├─ Data completeness (critical milestones present)                │
│   ├─ Extraction failure patterns (systematic gaps)                  │
│   └─ Disease progression logic (progression after treatment)        │
│                                                                     │
│ Output: validation_report with critical_violations and warnings     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Modules & File Structure

### Repository Structure

```
RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/
├── scripts/                              # Main execution scripts
│   ├── patient_timeline_abstraction_V3.py    # MAIN ENTRY POINT
│   ├── protocol_knowledge_base.py            # 42 protocol definitions
│   ├── therapeutic_approach_abstractor.py     # Phase 5.0 treatment matching
│   └── [other agent files...]
│
├── lib/                                  # Core modules
│   ├── diagnostic_evidence_aggregator.py     # Phase 0.1 (NEW V5.1)
│   ├── who_reference_triage.py               # Phase 0.2 (ENHANCED V5.1)
│   ├── diagnosis_validator.py                # Phase 0.3 (EXISTING)
│   ├── investigation_engine_qaqc.py          # Phase 7 (NEW V5.1)
│   ├── eor_orchestrator.py                   # Multi-source EOR adjudication
│   ├── treatment_ordinality_processor.py     # Phase 2.5
│   ├── athena_schema_loader.py               # Schema discovery
│   └── [other utility modules...]
│
├── agents/                               # MedGemma agent interfaces
│   ├── medgemma_agent.py                     # MedGemma LLM client
│   ├── eor_agent.py                          # EOR extraction agent
│   ├── chemotherapy_agent.py                 # Chemotherapy extraction
│   └── [other extraction agents...]
│
├── docs/                                 # Documentation
│   ├── V5_1_COMPREHENSIVE_SYSTEM_ARCHITECTURE.md  # THIS FILE
│   ├── V4_7_COMPREHENSIVE_INVESTIGATION_ENGINE_ARCHITECTURE.md
│   ├── V5_0_THERAPEUTIC_APPROACH_FRAMEWORK.md
│   ├── V5_0_PROTOCOL_AUGMENTATION.md
│   ├── DIAGNOSTIC_REASONING_SPRINT_PLAN.md
│   ├── TIERED_REASONING_ARCHITECTURE.md
│   ├── DATA_MODELING_PRINCIPLES.md
│   └── [other documentation...]
│
├── reference_materials/                  # Knowledge bases
│   ├── WHO_CNS5_Treatment_Guide.pdf
│   ├── CBTN_Anatomical_Codes.json
│   └── [other references...]
│
├── output/                               # Output artifacts
│   ├── {patient_id}/                         # Per-patient output
│   │   ├── timeline_artifact.json            # Final artifact
│   │   ├── clinical_summary.md               # Human-readable summary
│   │   ├── timeline.html                     # Interactive visualization
│   │   └── checkpoints/                      # Resume checkpoints
│   └── who_classifications/                  # Cached WHO classifications
│
└── data/                                 # Cached data
    └── who_2021_classification_cache.json
```

### Key File Descriptions

#### Main Entry Point

**[scripts/patient_timeline_abstraction_V3.py](../scripts/patient_timeline_abstraction_V3.py)**
- **Purpose**: Orchestrates entire extraction pipeline
- **Entry**: `python3 patient_timeline_abstraction_V3.py <patient_id> --output-dir <dir>`
- **Key Methods**:
  - `_generate_who_classification()`: Phase 0 WHO classification with diagnostic reasoning
  - `_phase1_load_structured_data()`: Load Athena views
  - `_phase2_build_timeline()`: Construct initial timeline
  - `_phase2_2_core_gap_remediation()`: Multi-tier note search
  - `_phase2_5_treatment_ordinality()`: Assign ordinality
  - `_phase4_binary_extraction()`: MedGemma extraction
  - `_phase5_protocol_validation()`: WHO standards validation
  - `_phase6_generate_artifact()`: Final JSON output
  - **NEW**: Phase 7 integration (lines 1945-1960)

#### Diagnostic Reasoning Infrastructure (Phase 0)

**[lib/diagnostic_evidence_aggregator.py](../lib/diagnostic_evidence_aggregator.py)** (NEW in V5.1)
- **Purpose**: Multi-source diagnostic evidence collection (Phase 0.1)
- **Key Classes**:
  - `DiagnosticEvidenceAggregator`: Collects diagnosis from 9 sources
  - `DiagnosisEvidence`: Evidence dataclass with source, confidence, date
  - `EvidenceSource`: Enum ranking clinical authority
- **Key Methods**:
  - `aggregate_all_evidence()`: Tier 2A/2B/2C cascade
  - `_extract_from_pathology()`: Tier 2A keywords
  - `_extract_from_problem_lists()`: Tier 2A keywords
  - `_extract_from_imaging_reports()`: Tier 2B MedGemma
  - `_extract_from_clinical_notes()`: Tier 2B MedGemma
  - `_extract_from_discharge_summaries()`: Tier 2B MedGemma
  - `_investigation_engine_search_alternatives()`: Tier 2C fallback

**[lib/who_reference_triage.py](../lib/who_reference_triage.py)** (ENHANCED in V5.1)
- **Purpose**: WHO section triage with 3-tier reasoning (Phase 0.2)
- **Key Methods**:
  - `identify_relevant_section()`: Tier 2A/2B/2C cascade
  - `_medgemma_clinical_triage()`: Tier 2B LLM reasoning (lines 314-456)
  - `_investigation_engine_validate_triage()`: Tier 2C conflict detection (lines 458-573)
- **Enhancements**: Added APC/CTNNB1 to embryonal markers, conflict detection for impossible combinations

**[lib/diagnosis_validator.py](../lib/diagnosis_validator.py)** (EXISTING)
- **Purpose**: Biological plausibility checking (Phase 0.3)
- **Key Method**: `validate()` checks IMPOSSIBLE_COMBINATIONS

#### Phase 7 QA/QC (NEW in V5.1)

**[lib/investigation_engine_qaqc.py](../lib/investigation_engine_qaqc.py)** (NEW)
- **Purpose**: End-to-end quality assurance after artifact generation
- **Key Class**: `InvestigationEngineQAQC`
- **Key Methods**:
  - `run_comprehensive_validation()`: Main QA/QC orchestrator
  - `_validate_temporal_consistency()`: Dates chronologically ordered
  - `_validate_protocol_against_diagnosis()`: **CRITICAL** - treatment matches diagnosis
  - `_assess_data_completeness()`: Critical milestones present
  - `_analyze_extraction_failures()`: Systematic gap patterns
  - `_validate_disease_progression()`: Progression logic

#### Therapeutic Approach (Phase 5.0)

**[scripts/protocol_knowledge_base.py](../scripts/protocol_knowledge_base.py)** (V5.0)
- **Purpose**: 42 protocol definitions with signature agents
- **Protocols**: COG, St. Jude, consortium, legacy, salvage
- **Key Functions**:
  - `get_protocols_by_indication()`
  - `get_protocols_by_signature_agent()`
  - `get_protocols_by_radiation_signature()`
- **Signature Agents**: nelarabine (T-ALL), carboplatin+isotretinoin (ACNS0332), etc.

**[scripts/therapeutic_approach_abstractor.py](../scripts/therapeutic_approach_abstractor.py)** (V5.0)
- **Purpose**: Match observed treatment to known protocols
- **Key Method**: `match_regimen_to_protocol()` (3-step algorithm)
  - Step 1: Signature agent matching (+20 bonus)
  - Step 2: Radiation signature matching (+15 bonus)
  - Step 3: Indication-based matching

#### Multi-Source Adjudication

**[lib/eor_orchestrator.py](../lib/eor_orchestrator.py)**
- **Purpose**: Adjudicate extent of resection from multiple sources
- **Sources**: Operative notes + post-op imaging
- **Logic**: Prioritizes imaging (objective) over operative notes when conflict

---

## Data Sources & Infrastructure

### AWS Infrastructure

| Component | Value |
|-----------|-------|
| AWS Profile | `radiant-prod` |
| Region | `us-east-1` |
| Database | `fhir_prd_db` |
| Query Engine | AWS Athena (Presto SQL) |
| S3 Bucket (binaries) | `s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/source/Binary/` |
| S3 Bucket (query results) | `s3://radiant-prd-343218191717-us-east-1-prd-athena-output/` |

### Athena Views (Structured Data)

| View | Purpose | Key Fields | Typical Rows |
|------|---------|------------|--------------|
| `v_demographics` | Patient context | `age`, `gender`, `race` | 1 |
| `v_pathology_diagnostics` | Molecular markers | `diagnostic_name`, `component_name`, `result_value`, `diagnostic_date` | 100-20,000 |
| `v_procedures_tumor` | Surgeries | `procedure_type`, `performed_datetime`, `encounter_id` | 1-10 |
| `v_chemo_treatment_episodes` | Chemotherapy | `episode_drug_names`, `episode_start_datetime`, `episode_end_datetime` | 5-50 |
| `v_radiation_episode_enrichment` | Radiation | `start_date`, `end_date`, `total_dose_cgy`, `fractions` | 1-5 |
| `v_imaging` | Imaging studies | `imaging_date`, `modality`, `report_conclusion`, `result_information` | 20-150 |
| `v_conditions` | Problem lists | `condition_display_name`, `onset_date`, `verification_status` | 10-100 |
| `v_binary_files` | Document inventory | `dr_type_text`, `dr_date`, `binary_id` | 50-500 |

**CRITICAL Date Handling Pattern**:
```sql
-- ❌ BROKEN:
WHERE CAST(dr.date AS DATE) >= DATE '2021-10-01'

-- ✅ CORRECT:
WHERE dr.date IS NOT NULL
  AND LENGTH(dr.date) >= 10
  AND DATE(SUBSTR(dr.date, 1, 10)) >= DATE '2021-10-01'
```

### LLM Infrastructure

| Component | Value |
|-----------|-------|
| LLM | MedGemma (gemma2:27b) via Ollama |
| Host | Local Ollama server |
| Context Window | 8192 tokens |
| Temperature | 0.1 (deterministic extraction) |

---

## Execution Workflow

### Command Line Interface

```bash
# Basic usage
python3 patient_timeline_abstraction_V3.py <patient_fhir_id> \
  --output-dir <output_directory> \
  --aws-profile radiant-prod

# Common options
--skip-binary              # Skip Phase 4 binary extraction
--resume                   # Resume from checkpoint
--force-reclassify         # Force WHO reclassification (ignore cache)
--max-extractions 50       # Limit binary document extractions
```

### Execution Flow

1. **Load WHO Classification** (Phase 0)
   - Check cache: `data/who_2021_classification_cache.json`
   - If cached: Load cached classification
   - If not cached: Run Phase 0.1-0.4 diagnostic reasoning pipeline

2. **Load Structured Data** (Phase 1)
   - Query 8 Athena views in parallel
   - Track query execution times
   - Log row counts

3. **Build Timeline** (Phase 2)
   - Construct events from Phase 1 data
   - Phase 2.1: Validate minimal completeness
   - Phase 2.2: Multi-tier gap remediation (chemo/radiation end dates, EOR)
   - Phase 2.5: Assign treatment ordinality

4. **Identify Gaps** (Phase 3)
   - Compare timeline to expected data
   - Phase 3.5: Query v_imaging for structured EOR

5. **Binary Extraction** (Phase 4)
   - Build document inventory
   - Prioritize gaps (HIGHEST → LOW)
   - Extract with MedGemma (up to --max-extractions)
   - Phase 4.5: Assess completeness

6. **Protocol Validation & Matching** (Phase 5)
   - V5.0: Match treatment to 42 protocols
   - Original: Validate radiation doses

7. **Generate Artifact** (Phase 6)
   - Create JSON artifact
   - Generate clinical summary (I-PASS)
   - Generate timeline visualization

8. **QA/QC Validation** (Phase 7) - NEW
   - Run InvestigationEngineQAQC
   - Validate temporal consistency
   - **Validate protocol coherence** (treatment matches diagnosis)
   - Store validation_report in artifact

9. **Output**
   - `{output_dir}/{patient_id}/timeline_artifact.json`
   - `{output_dir}/{patient_id}/clinical_summary.md`
   - `{output_dir}/{patient_id}/timeline.html`

### Checkpointing

Checkpoints saved after each phase:
```
{output_dir}/{patient_id}/checkpoints/
├── phase_0_who_classification.json
├── phase_1_structured_data.json
├── phase_2_timeline_construction.json
├── phase_3_gap_identification.json
├── phase_4_binary_extraction.json
├── phase_5_protocol_validation.json
└── phase_6_artifact_generation.json
```

Resume with: `--resume`

---

## Code Objects & Key Classes

### Phase 0: Diagnostic Reasoning

```python
# lib/diagnostic_evidence_aggregator.py
class DiagnosticEvidenceAggregator:
    def __init__(self, query_athena: Callable):
        self.query_athena = query_athena

    def aggregate_all_evidence(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        # Tier 2A: Keywords from pathology + problem lists
        # Tier 2B: MedGemma from imaging + notes + discharge
        # Tier 2C: Investigation Engine alternatives
        pass

@dataclass
class DiagnosisEvidence:
    diagnosis: str
    source: EvidenceSource  # Clinical authority ranking
    confidence: float
    date: Optional[datetime]
    raw_data: Dict
    extraction_method: str  # 'keyword', 'medgemma', 'investigation_engine'
```

```python
# lib/who_reference_triage.py
class WHOReferenceTriageEnhanced:
    def identify_relevant_section(self, stage1_findings: Dict) -> str:
        # Tier 2A: Rule-based (IDH, age, embryonal markers)
        # Tier 2B: MedGemma clinical reasoning
        # Tier 2C: Investigation Engine conflict detection
        pass

    def _medgemma_clinical_triage(self, stage1_findings: Dict) -> Optional[Dict]:
        # LLM reasoning for ambiguous cases
        # Returns: {'section': str, 'confidence': float, 'reasoning': str}
        pass

    def _investigation_engine_validate_triage(
        self,
        triage_section: str,
        stage1_findings: Dict
    ) -> Dict:
        # Conflict detection (e.g., APC + non-embryonal section)
        # Returns: {'conflicts_detected': bool, 'corrected_section': str, ...}
        pass
```

### Phase 7: QA/QC

```python
# lib/investigation_engine_qaqc.py
class InvestigationEngineQAQC:
    def __init__(
        self,
        anchored_diagnosis: Dict[str, Any],
        timeline_events: List[Dict[str, Any]],
        patient_fhir_id: str
    ):
        self.anchored_diagnosis = anchored_diagnosis
        self.timeline_events = timeline_events
        self.patient_fhir_id = patient_fhir_id

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        return {
            'temporal_consistency': self._validate_temporal_consistency(),
            'protocol_coherence': self._validate_protocol_against_diagnosis(),
            'data_completeness': self._assess_data_completeness(),
            'extraction_failures': self._analyze_extraction_failures(),
            'progression_logic': self._validate_disease_progression(),
            'critical_violations': [...],
            'warnings': [...],
            'recommendations': [...]
        }

    def _validate_protocol_against_diagnosis(self) -> Dict[str, Any]:
        # CRITICAL: Medulloblastoma → expects CSI (not focal RT)
        # CRITICAL: Glioblastoma → expects 60 Gy + TMZ
        # CRITICAL: Low-grade → should NOT see 60 Gy
        pass
```

### Phase 5.0: Therapeutic Approach

```python
# scripts/protocol_knowledge_base.py
ALL_PROTOCOLS = {
    "acns0332": {
        "name": "COG ACNS0332 (High-Risk Medulloblastoma)",
        "indications": ["medulloblastoma_high_risk", "metastatic_medulloblastoma"],
        "evidence_level": "standard_of_care",
        "signature_agents": ["carboplatin", "isotretinoin"],  # Fingerprints!
        "signature_radiation": {"csi_dose_gy": 36.0, "type": "craniospinal"},
        ...
    },
    "aall0434": {
        "name": "COG AALL0434 (T-cell ALL)",
        "signature_agents": ["nelarabine"],  # Only T-ALL uses nelarabine!
        ...
    },
    # ... 40 more protocols
}

def get_protocols_by_signature_agent(agent: str) -> List[Dict]:
    # Query by signature agent (e.g., nelarabine → AALL0434)
    pass
```

```python
# scripts/therapeutic_approach_abstractor.py
def match_regimen_to_protocol(line_events, diagnosis, knowledge_base):
    # Step 1: Signature agent matching (+20 bonus)
    if "nelarabine" in agents:
        return "aall0434"  # T-ALL protocol

    # Step 2: Radiation signature matching (+15 bonus)
    if csi_dose == 18.0:
        return "sjmb12"  # WNT-MB (unique dose!)

    # Step 3: Indication-based matching
    for protocol in get_protocols_by_indication(diagnosis):
        score = score_component_match(observed, protocol['components'])
        if score >= 90:
            return protocol

    return None
```

---

## Expected Behavior & Outputs

### Artifact Structure

```json
{
  "patient_id": "eEJcrpDHtP-6cfR7bRFzo4rcdRi2fSkhGm.GuVGnCOSo3",
  "abstraction_timestamp": "2025-11-12T10:30:00Z",

  "who_2021_classification": {
    "who_2021_diagnosis": "Medulloblastoma, WNT-activated",
    "grade": "4",
    "key_markers": {"APC": "mutation", "CTNNB1": "mutation"},
    "confidence": "high",
    "validation": {
      "is_valid": true,
      "violations": []
    }
  },

  "patient_demographics": {...},

  "therapeutic_approach": {
    "lines_of_therapy": [
      {
        "line_number": 1,
        "regimen": {
          "protocol_id": "acns0331",
          "regimen_name": "COG ACNS0331 (Average-Risk Medulloblastoma)",
          "match_confidence": "high",
          "matching_method": "signature_agent",
          "components": [...]
        },
        "response_assessments": [...],
        "discontinuation": {...}
      }
    ]
  },

  "timeline_events": [...],

  "phase_7_validation": {
    "temporal_consistency": {"is_valid": true, ...},
    "protocol_coherence": {
      "is_valid": true,
      "critical_violations": [],
      "warnings": []
    },
    "data_completeness": {"completeness_score": 0.85, ...},
    "critical_violations": [],
    "warnings": [],
    "recommendations": []
  }
}
```

### Clinical Summary Output

```markdown
# Clinical Summary: Patient eEJcrpDHtP-...

## WHO 2021 Diagnosis
- **Diagnosis**: Medulloblastoma, WNT-activated
- **Grade**: 4
- **Key Markers**: APC mutation, CTNNB1 mutation
- **Confidence**: High

## Treatment Summary

### Line 1: COG ACNS0331 (Average-Risk Medulloblastoma)
- **Protocol Match**: High confidence (95%)
- **Matching Method**: Signature Agent
- **Components**:
  - Surgery: Gross total resection (2023-05-15)
  - Radiation: CSI 23.4 Gy + boost 30.6 Gy (total 54 Gy)
  - Chemotherapy: Vincristine weekly × 8, maintenance × 6 cycles
- **Duration**: 196 days
- **Best Response**: Stable disease
- **Status**: Completed

## Phase 7 Quality Assurance
✅ Temporal consistency validated
✅ Treatment protocol matches diagnosis (CSI appropriate for medulloblastoma)
✅ Data completeness: 85%
```

---

## Running the System

### Prerequisites

1. **AWS Credentials**: `~/.aws/credentials` with `radiant-prod` profile
2. **Python 3.8+**
3. **Ollama** with gemma2:27b model
4. **Dependencies**: `pip install -r requirements.txt`

### Example Commands

```bash
# Test Patient 6 (medulloblastoma) - Phase 0/7 validation
cd scripts
export AWS_PROFILE=radiant-prod
python3 patient_timeline_abstraction_V3.py \
  --patient-id eEJcrpDHtP-6cfR7bRFzo4rcdRi2fSkhGm.GuVGnCOSo3 \
  --output-dir ../output/patient6_v5_1_test \
  --force-reclassify

# Resume from checkpoint (skip Phase 0-3)
python3 patient_timeline_abstraction_V3.py \
  --patient-id <patient_id> \
  --output-dir <dir> \
  --resume

# Skip binary extraction (fast testing)
python3 patient_timeline_abstraction_V3.py \
  --patient-id <patient_id> \
  --output-dir <dir> \
  --skip-binary
```

### Expected Console Output

```
================================================================================
PHASE 0: DIAGNOSTIC REASONING - FOUNDATIONAL ANCHOR
================================================================================
   [Phase 0.1] Aggregating diagnostic evidence from all sources...
      → Tier 2A: Found 5 pathology evidence items
      → Tier 2A: Found 2 problem list evidence items
      → Tier 2B: Found 3 imaging report evidence items
      → Tier 2B: Found 1 clinical note evidence items
      → Tier 2C not needed: Sufficient evidence already collected (11 items)
   ✅ Phase 0.1 complete: 11 total evidence items collected

   [Phase 0.2] WHO Reference Triage with 3-tier reasoning...
      → Tier 2A: Embryonal markers found (APC, CTNNB1)
      → Tier 2A: Selected 'embryonal_tumors'
      → Tier 2C: Validating triage decision...
      ✅ Tier 2C: No conflicts detected, triage validated

   [Phase 0.3] Validating diagnosis biological plausibility...
      ✅ No biological impossibilities detected

================================================================================
PHASE 7: INVESTIGATION ENGINE - END-TO-END QA/QC
================================================================================
   [Phase 7.1] Validating temporal consistency...
      ✅ Temporal consistency validated

   [Phase 7.2] Validating treatment protocol against diagnosis...
      → Validating medulloblastoma protocol...
      ✅ CSI found (expected for medulloblastoma)
      ✅ Treatment protocol validated against diagnosis

   [Phase 7.3] Assessing data completeness...
      → Completeness score: 85.00%
      ✅ All critical milestones present

   [Phase 7.4] Analyzing extraction failure patterns...
      ✅ No systematic extraction failures detected

   [Phase 7.5] Validating disease progression logic...
      ✅ Disease progression logic validated

================================================================================
PHASE 7 VALIDATION SUMMARY
================================================================================
✅ No critical violations detected
⚠️  2 warnings
💡 3 recommendations
================================================================================
```

---

## Testing & Validation

### Test Cases

1. **Patient 6 (Medulloblastoma, WNT-activated)**
   - **Purpose**: Validate Phase 0.2 Tier 2C catches APC misclassification
   - **Expected**: WHO section = 'embryonal_tumors' (not 'adult_diffuse_gliomas')
   - **Expected**: Phase 7 validates CSI protocol

2. **IDH-mutant Astrocytoma Cohort**
   - **Purpose**: Validate Phase 5.0 protocol matching (Stupp Protocol)
   - **Expected**: Match to `stupp_protocol` with high confidence

3. **T-ALL Patient with Nelarabine**
   - **Purpose**: Validate signature agent matching
   - **Expected**: Match to `aall0434` via nelarabine

### Validation Metrics

| Metric | Target | Current |
|--------|--------|---------|
| WHO Classification Accuracy | >95% | TBD |
| Protocol Match Accuracy | >90% | TBD |
| Temporal Consistency | 100% | TBD |
| Data Completeness | >80% | TBD |
| Phase 7 Critical Violations | 0 | TBD |

---

## Known Issues & Limitations

### Current Limitations

1. **Hardcoded Protocol Knowledge Base**: All 42 protocols hardcoded in `protocol_knowledge_base.py`. Updates require code changes.

2. **Date Handling Complexity**: FHIR timestamp strings require special `DATE(SUBSTR(...))` pattern for all queries.

3. **Binary Extraction Budget**: MedGemma extraction limited by `--max-extractions` (default 50). Large document sets may be incomplete.

4. **Phase 7 Not Yet Tested**: V5.1 Phase 7 implementation complete but not validated on real patients.

5. **No Multi-Institution Variability**: Phase 7 assumes standard protocol implementation. Institutional variations not modeled.

### Known Bugs

**None currently identified** - all Phase 0/7 implementations compiled successfully.

---

## Future Development

### Immediate Next Steps (Post-V5.1)

1. **Test Phase 0/7 on Patient 6**: Validate APC conflict detection and CSI validation
2. **Test on Full Cohort**: Run all 6 medulloblastoma patients
3. **Performance Profiling**: Measure Phase 0/7 overhead

### V5.2+ Roadmap

1. **Dynamic Protocol Loading**: Load protocols from external APIs (ClinicalTrials.gov)
2. **ML-Based Protocol Matching**: Train model on labeled enrollments
3. **Temporal Protocol Evolution**: Track protocol amendments over time
4. **Adult Oncology Protocols**: Expand beyond pediatric protocols
5. **Protocol-Guided Recommendations**: Suggest next-line therapies based on progression

---

## Document Maintenance

**Last Updated**: 2025-11-12
**Version**: V5.1.0
**Maintainer**: RADIANT PCA Development Team

**Change Log**:
- 2025-11-12: Initial V5.1 comprehensive architecture document created
- Incorporated Phase 0 diagnostic reasoning infrastructure (V5.1)
- Incorporated Phase 7 Investigation Engine QA/QC (V5.1)
- Documented Phase 5.0 therapeutic approach framework
- Consolidated information from 3 source documents

**Related Documents**:
- [V4.7 Comprehensive Investigation Engine Architecture](V4_7_COMPREHENSIVE_INVESTIGATION_ENGINE_ARCHITECTURE.md)
- [V5.0 Therapeutic Approach Framework](V5_0_THERAPEUTIC_APPROACH_FRAMEWORK.md)
- [V5.0 Protocol Augmentation](V5_0_PROTOCOL_AUGMENTATION.md)
- [Diagnostic Reasoning Sprint Plan](DIAGNOSTIC_REASONING_SPRINT_PLAN.md)
- [Tiered Reasoning Architecture](TIERED_REASONING_ARCHITECTURE.md)

**For Future Agents**: This document provides complete system knowledge. You should be able to:
1. Run the pipeline on new patients
2. Understand all phase outputs
3. Debug extraction failures
4. Extend protocol knowledge base
5. Implement new validation logic

If you need more context on specific components, consult the related documents above.

---

**END OF COMPREHENSIVE ARCHITECTURE DOCUMENT**
