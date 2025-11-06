# Tiered Reasoning Architecture: MedGemma + Investigation Engine

**Version**: V4.7
**Date**: 2025-11-06
**Purpose**: Define the complete 3-tier reasoning architecture for clinical data extraction and quality assurance

---

## Overview

This system implements a **3-tier progressive reasoning cascade** with dual-purpose Investigation Engine:

1. **Tier 2A**: Fast keyword pattern matching
2. **Tier 2B**: MedGemma context-specific clinical reasoning
3. **Tier 2C**: Investigation Engine fallback reasoning + end-to-end QA/QC

---

## Tier 2A: Enhanced Keyword Search

### Scope
- Task-specific, single document or query result
- Examples: Single imaging report, single operative note, single pathology result

### Purpose
- Fast first-pass extraction using explicit medical terminology
- Covers both radiological assessment AND surgical procedure terminology

### Implementation Pattern
```python
# Enhanced keyword lists for EOR extraction
gtr_keywords = ['no residual', 'complete resection', 'gross total']
partial_keywords = ['partial debulk', 'debulking', 'incomplete resection']

if any(kw in report_text for kw in partial_keywords):
    return 'Partial'
```

### When Used
- **Always** attempted first for every extraction task
- If successful → Return result (fastest path)
- If fails → Escalate to Tier 2B

---

## Tier 2B: MedGemma Context-Specific Clinical Reasoning

### Scope
- Task-specific, single context (document/structured data/query result)
- Examples:
  - "Based on THIS imaging report, what is extent of resection?"
  - "Based on THIS operative note, what procedure was performed?"
  - "Based on THIS pathology report, what is IDH mutation status?"

### Purpose
- **TRUE LLM clinical reasoning** for specific extraction tasks
- Clinical inference from indirect descriptions
- Contextual understanding and ambiguity resolution
- Medical terminology mapping to standard classifications

### Implementation Pattern
```python
def _medgemma_extract_eor_from_imaging(self, report_text, surgery_date, img_date):
    """
    Use MedGemma to intelligently interpret radiology report text.

    LLM REASONING CAPABILITIES:
    - Clinical inference: "Post-op changes in resection cavity" → Infer GTR if no residual mentioned
    - Contextual understanding: "Debulking" → Classify as Partial
    - Ambiguity resolution: Favor conservative classification when unclear
    - Terminology mapping: "Near-complete" → STR
    """

    prompt = f"""You are reviewing a post-operative radiology report from {img_date}
    for a brain tumor surgery performed on {surgery_date}.

    **Your Task**: Use your clinical reasoning to classify the extent of tumor resection.

    **Clinical Reasoning Instructions**:
    1. **Inference from Indirect Descriptions**:
       - "Post-operative changes in resection cavity" → Infer surgery occurred
       - "Improved mass effect" → Infer significant tissue removal

    2. **Contextual Understanding**:
       - "Debulking" → Classify as Partial
       - "Near-complete resection" → Classify as STR

    3. **Ambiguity Resolution**:
       - If unclear, favor conservative classification

    **Report Text**: {report_text}

    Return JSON with: extent_of_resection, clinical_reasoning, confidence
    """
```

### Key Differentiators from Keyword Matching
| Aspect | Keyword Matching | MedGemma Reasoning |
|--------|------------------|-------------------|
| Approach | `if 'debulking' in text` | Clinical inference from context |
| Ambiguity | Fails on unclear text | Makes reasoned clinical judgment |
| Explanation | None | Provides reasoning explanation |
| Contextual | Word presence only | Interprets clinical meaning |

### When Used
- When Tier 2A (keywords) fails to find explicit terminology
- If successful → Return result with reasoning
- If fails → Escalate to Tier 2C

---

## Tier 2C: Investigation Engine - Dual Purpose

### Purpose 1: Context-Specific Fallback Reasoning (Task-Level)

#### Scope
- Single extraction task that failed in Tiers 2A + 2B
- Examples:
  - MedGemma failed to extract EOR from imaging report
  - No operative notes found in expected view
  - Pathology report has corrupted text

#### Purpose
- **Analyze WHY** MedGemma/data query failed
- **Identify alternative data sources** or inference strategies
- **Apply fallback reasoning rules** based on domain knowledge
- **Flag data quality issues** for manual review

#### Implementation Pattern
```python
def _investigation_engine_fallback_eor(self, report_text, surgery_date, img_date, medgemma_failure_reason):
    """
    Investigation Engine analyzes WHY MedGemma failed and applies fallback strategies.

    CRITICAL: Investigation Engine has COMPREHENSIVE KNOWLEDGE of:
    - ALL Athena views (v_imaging, v_procedures_tumor, v_pathology_diagnostics, etc.)
    - ALL FHIR resource types (DocumentReference, Binary, Observation, Procedure, etc.)
    - System architecture (Phase 1-6 workflow, extraction patterns, data lineage)
    - Data quality patterns (common truncation issues, external institution data gaps)
    - Clinical domain knowledge (standard treatment protocols, temporal expectations)

    This ensures NO STONE LEFT UNTURNED in finding required clinical information.

    META-REASONING CAPABILITIES:
    1. Failure diagnosis: Why did MedGemma fail?
       - Corrupted text?
       - Ambiguous terminology?
       - Missing information?
       - Pre-operative report (not post-op)?
       - Wrong FHIR resource type queried?

    2. COMPREHENSIVE alternative data source identification:
       a) Alternative Athena views:
          - v_imaging vs v_imaging_results vs v_radiology_reports
          - v_procedures_tumor vs v_clinical_notes vs v_operative_notes
          - v_pathology_diagnostics vs v_laboratory_results

       b) Alternative FHIR resources:
          - DocumentReference (operative notes, discharge summaries)
          - Binary (PDF operative notes, scanned reports)
          - Observation (structured imaging findings, tumor measurements)
          - DiagnosticReport (radiology reports with structured data)

       c) Cross-view inference:
          - No EOR in v_procedures_tumor → Check v_imaging for post-op assessment
          - No radiation dose in v_radiation → Check v_clinical_notes for treatment plan
          - No molecular markers in v_pathology_diagnostics → Check v_binary_files for pathology PDFs

       d) Temporal/contextual queries:
          - Post-op imaging within 72 hours of surgery
          - Discharge summary within 7 days of surgery (often contains EOR)
          - Clinical notes mentioning "extent of resection" or "debulking"

    3. Fallback reasoning rules:
       - Rule 1: "Resection cavity" without residual tumor → Likely GTR
       - Rule 2: Surgery occurred but unclear EOR → Conservative "Partial"
       - Rule 3: >7 days post-op → Unreliable for EOR (may show recurrence)
       - Rule 4: Radiation dose >54 Gy suggests residual disease → Infer STR/Partial
       - Rule 5: External institution surgery → Check v_binary_files for transferred records

    4. Data quality flagging:
       - Text truncated/corrupted → Flag for manual review
       - Contradictory information → Flag clinical discrepancy
       - Missing expected documentation → Flag data completeness issue
       - External institution data gaps → Flag for additional data request
    """

    prompt = f"""You are the Investigation Engine performing SECONDARY REVIEW after
    MedGemma failed to extract extent of resection.

    **Context**:
    - Surgery Date: {surgery_date}
    - Imaging Date: {img_date}
    - MedGemma Failure Reason: {medgemma_failure_reason}

    **Your Meta-Reasoning Task**:
    1. Analyze WHY MedGemma failed
    2. Identify alternative data sources we should check
    3. Apply fallback reasoning rules
    4. Flag data quality issues if present

    **Fallback Reasoning Rules**:
    - Rule 1: "Resection cavity" without residual → Likely GTR
    - Rule 2: Surgery occurred but unclear → Conservative "Partial"
    - Rule 3: >7 days post-op → Unreliable for EOR

    Return JSON with:
    - extent_of_resection (or null)
    - failure_analysis
    - suggested_alternatives (list of alternative views/documents to check)
    - data_quality_flags (list of issues found)
    - fallback_reasoning
    - confidence
    """
```

#### When Used
- When Tier 2B (MedGemma) fails on specific extraction
- Called **during extraction phases** (Phase 3.5, Phase 4, Phase 5)
- Operates on **single task context**

---

### Purpose 2: End-to-End Timeline QA/QC (Timeline-Level)

#### Scope
- **COMPLETE patient journey** across ALL phases
- Examples:
  - Does entire timeline make clinical sense?
  - Are there temporal inconsistencies?
  - Does treatment match diagnosis/molecular profile?
  - Are critical milestones missing?

#### Purpose
- **Overarching clinical coherence validation**
- **Temporal consistency checking** (dates make sense?)
- **Clinical protocol validation** (treatment matches diagnosis?)
- **Data completeness assessment** (missing critical data?)
- **Extraction failure pattern analysis** (systematic gaps?)
- **Disease progression logic** (tumor trajectory plausible?)

#### Implementation Pattern
```python
def _phase7_investigation_engine_qaqc(self):
    """
    Phase 7: End-to-end Investigation Engine quality assurance.

    Analyzes COMPLETE timeline for:
    - Temporal consistency
    - Clinical protocol coherence
    - Data completeness
    - Extraction failure patterns
    - Disease progression logic
    """

    validation_report = {
        'temporal_consistency': self._validate_temporal_consistency(),
        'clinical_protocol_coherence': self._validate_clinical_protocols(),
        'data_completeness': self._assess_data_completeness(),
        'extraction_failure_patterns': self._analyze_extraction_failures(),
        'disease_progression_logic': self._validate_disease_progression()
    }

    return validation_report

def _validate_temporal_consistency(self):
    """
    Check if dates make clinical sense.

    Examples:
    - Surgery BEFORE diagnosis? → FLAG
    - Radiation start BEFORE surgery? → FLAG
    - Post-op imaging BEFORE surgery? → FLAG
    - Chemotherapy end BEFORE start? → FLAG
    """

def _validate_clinical_protocols(self):
    """
    Check if treatment matches diagnosis and molecular profile.

    Examples:
    - IDH-wildtype glioblastoma + Stupp protocol (TMZ+RT)? → ✓
    - IDH-mutant Grade 2 astrocytoma + 60 Gy radiation? → FLAG (high-grade protocol)
    - MGMT-methylated + no TMZ? → FLAG (should consider TMZ)
    - 1p/19q co-deleted oligodendroglioma + RT only? → FLAG (should see PCV or TMZ)
    """

def _assess_data_completeness(self):
    """
    Check if critical clinical milestones are documented.

    Examples:
    - Every surgery should have post-op imaging within 72 hours
    - Every diagnosis should have molecular markers (IDH, 1p/19q, MGMT)
    - Every radiation should have dose/fractionation
    - Every chemotherapy should have agent + dates
    """

def _analyze_extraction_failures(self):
    """
    Identify systematic extraction failure patterns.

    Examples:
    - All surgeries missing EOR? → v_procedures_tumor field mapping issue
    - Phase 4 binary extraction 80% failure rate? → Data quality problem
    - No radiation found for any patient? → View schema issue
    """

def _validate_disease_progression(self):
    """
    Check if tumor measurements and clinical trajectory make sense.

    Examples:
    - Tumor growing despite treatment? → Progression
    - New enhancement 6 months post-GTR? → Recurrence vs pseudoprogression
    - Decreasing tumor size during treatment? → Response
    - Stable disease for 2 years post-RT? → Durable control
    """
```

#### When Used
- **After Phase 6** (artifact generation complete)
- Operates on **complete timeline artifact**
- **Phase 7** in the workflow
- Has access to:
  - All `timeline_events`
  - All `extraction_gaps`
  - All Phase 1-6 metadata
  - Patient demographics
  - WHO classification
  - Molecular markers

---

## Complete Workflow Integration

### Task-Level Extraction Flow (e.g., EOR from imaging)
```
1. Tier 2A (Keywords): Check for explicit terminology
   ↓ FAIL

2. Tier 2B (MedGemma): Clinical reasoning on THIS report
   ↓ FAIL

3. Tier 2C (Investigation Engine - Task Level):
   - Analyze WHY failed
   - Suggest alternative documents
   - Apply fallback reasoning rules
   - Flag data quality issues
   ↓ COMPLETE

4. Return result OR flag for manual review
```

### Timeline-Level QA/QC Flow (Phase 7)
```
Phase 1-6: Extract complete timeline
   ↓

Phase 6: Generate timeline artifact
   ↓

Phase 7: Investigation Engine End-to-End QA/QC
   ├─ Temporal consistency validation
   ├─ Clinical protocol coherence check
   ├─ Data completeness assessment
   ├─ Extraction failure pattern analysis
   └─ Disease progression logic validation
   ↓

Output: Timeline artifact + QA/QC validation report
```

---

## Key Architectural Principles

### 1. Progressive Reasoning Cascade
- Start with fastest method (keywords)
- Escalate to more sophisticated reasoning only when needed
- Maximize efficiency while ensuring completeness

### 2. Separation of Concerns
- **Tier 2A/2B**: Task-specific extraction (single document/context)
- **Tier 2C (Task-Level)**: Why did THIS extraction fail?
- **Tier 2C (Timeline-Level)**: Does COMPLETE timeline make sense?

### 3. Dual-Purpose Investigation Engine
- **Context-Specific Fallback**: Operates during extraction phases on single tasks
- **End-to-End QA/QC**: Operates after Phase 6 on complete timeline
- Same reasoning engine, different scopes

### 4. Explainability
- Every tier logs reasoning process
- MedGemma provides clinical reasoning explanation
- Investigation Engine provides failure analysis + fallback logic
- Full audit trail for clinical validation

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Tier 2A (Keywords) | ✅ Implemented | Enhanced with surgical terminology |
| Tier 2B (MedGemma Task-Specific) | ✅ Implemented | Clinical reasoning prompts |
| Tier 2C (Investigation Engine - Task Level) | ⚠️ Partially Implemented | Document-level meta-reasoning exists, needs alternative source identification |
| Tier 2C (Investigation Engine - Timeline Level) | ❌ Not Implemented | Phase 7 QA/QC needs to be built |

---

## Next Steps

1. **Refactor Tier 2C Task-Level**:
   - Rename current `_investigation_engine_review_imaging_for_eor()` for clarity
   - Add alternative data source identification
   - Implement data quality flagging

2. **Implement Tier 2C Timeline-Level (Phase 7)**:
   - Build temporal consistency validator
   - Build clinical protocol validator
   - Build data completeness assessor
   - Build extraction failure pattern analyzer
   - Build disease progression validator

3. **Integration**:
   - Connect Phase 7 to main workflow (after Phase 6)
   - Update artifact structure to include QA/QC report
   - Add Investigation Engine findings to visualization

4. **Documentation**:
   - Update V4_7_COMPREHENSIVE with Phase 7 details
   - Document Investigation Engine prompt engineering
   - Add QA/QC validation criteria reference

---

**Version History**:
- V4.7 (2025-11-06): Initial architecture definition with dual-purpose Investigation Engine
