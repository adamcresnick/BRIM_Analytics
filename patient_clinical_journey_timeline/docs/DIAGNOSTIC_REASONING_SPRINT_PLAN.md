# Diagnostic Reasoning Infrastructure - Implementation Sprint Plan

**Version**: V5.1
**Date**: 2025-01-12
**Goal**: Harden diagnosis as the foundational reasoning layer for all timeline assessments
**Status**: READY TO IMPLEMENT

---

## Executive Summary

This sprint implements a comprehensive diagnostic reasoning framework that establishes **diagnosis as the foundational anchor** for all clinical timeline analysis. The framework integrates with the existing 3-tier reasoning architecture (Keywords → MedGemma → Investigation Engine) and ensures diagnosis quality through multi-source evidence aggregation, cross-validation, and biological plausibility checking.

### Success Criteria

1. ✅ Patient 6 correctly diagnosed as "Medulloblastoma, WNT-activated" (not Glioblastoma)
2. ✅ All 6 medulloblastoma patients correctly classified
3. ✅ Diagnosis confidence scores accurately reflect evidence quality
4. ✅ Biological impossibilities caught (e.g., APC + Glioblastoma)
5. ✅ Phase 1-6 timeline extraction anchored to validated diagnosis
6. ✅ Phase 7 QA/QC validates diagnosis against downstream treatment patterns

---

## Current State Analysis

### What's Working
- ✅ Stage 1: MedGemma extraction from pathology records (mostly working)
- ✅ Stage 2: MedGemma WHO classification (LLM quality is good)
- ✅ 3-tier reasoning architecture defined (TIERED_REASONING_ARCHITECTURE.md)
- ✅ WHO 2021 framework documented (WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md)

### What's Broken
- ❌ WHO Triage uses hardcoded marker lists instead of LLM reasoning
- ❌ Stage 2 WHO classification has NO validation layer
- ❌ Diagnosis NOT anchored as foundation for downstream phases
- ❌ No multi-source diagnosis aggregation (only uses pathology)
- ❌ Phase 7 Investigation Engine QA/QC not implemented

### Root Cause of Patient 6 Misdiagnosis
```
Stage 1: Extracted markers=['APC', 'Chromosome 6'], histology_findings=[]
         ↓
WHO Triage: embryonal_markers = ['SMARCB1', 'SMARCA4', 'MYC', 'MYCN']  ← Missing APC!
         ↓
Triage: Defaulted to 'adult_diffuse_gliomas' (no match found)
         ↓
Stage 2: MedGemma received WRONG WHO reference section (adult gliomas)
         ↓
Result: "Glioblastoma, IDH-wildtype" ← INCORRECT
```

---

## Implementation Phases

### **Phase 0.1: Multi-Source Diagnostic Evidence Aggregation**
**Goal**: Collect diagnosis mentions from ALL clinical sources, not just pathology

**Implementation**:
```python
# New file: lib/diagnostic_evidence_aggregator.py

class DiagnosticEvidenceAggregator:
    """
    Aggregates diagnosis evidence from multiple sources across the care journey.

    Sources (in order of clinical authority):
    1. Surgical pathology reports (v_pathology_diagnostics)
    2. Molecular testing reports (v_pathology_diagnostics)
    3. Problem/condition lists (v_conditions)
    4. Imaging reports (v_imaging - radiological impressions)
    5. Oncology notes (v_clinical_notes - diagnosis mentions)
    6. Radiation oncology notes (v_radiation - documented diagnoses)
    7. Progress notes (v_clinical_notes - ongoing diagnosis references)
    8. Discharge summaries (v_clinical_notes - admission/discharge diagnoses)
    9. Treatment protocols (protocol_knowledge_base - protocol requirements)
    """

    def aggregate_all_evidence(self, patient_fhir_id: str) -> List[DiagnosisEvidence]:
        """
        Collect ALL diagnosis mentions across the entire care journey.

        Returns:
            List of DiagnosisEvidence objects with source, confidence, date, supporting data
        """
        evidence = []

        # Tier 2A (Keywords): Fast extraction from structured sources
        evidence.extend(self._extract_from_pathology(patient_fhir_id))      # Highest authority
        evidence.extend(self._extract_from_problem_lists(patient_fhir_id))

        # Tier 2B (MedGemma): Clinical reasoning for narrative sources
        evidence.extend(self._extract_from_imaging_reports(patient_fhir_id))
        evidence.extend(self._extract_from_clinical_notes(patient_fhir_id))
        evidence.extend(self._extract_from_discharge_summaries(patient_fhir_id))

        # Tier 2C (Investigation Engine): Alternative sources if gaps found
        if len(evidence) < 2:  # Insufficient evidence
            evidence.extend(self._investigation_engine_search_alternatives(patient_fhir_id))

        return evidence
```

**Integration Point**: Called BEFORE Stage 1 WHO classification
**File to Modify**: `scripts/patient_timeline_abstraction_V3.py` - Add new Phase 0.1 step
**Estimated Time**: 2-3 hours

---

### **Phase 0.2: WHO Triage with 3-Tier Reasoning**
**Goal**: Replace hardcoded marker lists with LLM-based clinical reasoning

**Current (BROKEN)**:
```python
# lib/who_reference_triage.py:162
embryonal_markers = ['SMARCB1', 'SMARCA4', 'MYC', 'MYCN']  # ← Hardcoded, incomplete
if any(m in markers for m in embryonal_markers):
    return 'embryonal_tumors'
```

**New (TIERED REASONING)**:
```python
def identify_relevant_section(self, stage1_findings: Dict, all_evidence: List[DiagnosisEvidence]) -> str:
    """
    Apply 3-tier reasoning to select appropriate WHO section.

    Tier 2A (Rules): Check for definitive marker combinations
    Tier 2B (MedGemma): Clinical reasoning for triage decision
    Tier 2C (Investigation Engine): Validate triage makes sense
    """

    # Tier 2A: Check for definitive markers (EXPANDED list)
    embryonal_markers = ['SMARCB1', 'SMARCA4', 'MYC', 'MYCN', 'APC', 'CTNNB1',
                         'WNT', 'SHH', 'PTCH1', 'SMO', 'SUFU']
    if any(m in markers for m in embryonal_markers):
        logger.info("  Tier 2A: Embryonal tumors (definitive markers)")
        return 'embryonal_tumors'

    # Tier 2A: Check problem list diagnoses (NEW!)
    for evidence in all_evidence:
        if evidence.source == EvidenceSource.PROBLEM_LIST:
            if 'medulloblastoma' in evidence.diagnosis.lower():
                logger.info("  Tier 2A: Embryonal tumors (problem list)")
                return 'embryonal_tumors'

    # Tier 2B: MedGemma reasoning for ambiguous cases
    if not tier_2a_match:
        triage_decision = self._medgemma_clinical_triage(stage1_findings, all_evidence)
        if triage_decision['confidence'] >= 0.7:
            logger.info(f"  Tier 2B: {triage_decision['section']} (MedGemma reasoning)")
            return triage_decision['section']

    # Tier 2C: Investigation Engine validation
    validation = self._investigation_engine_validate_triage(
        triage_decision,
        stage1_findings,
        all_evidence
    )

    if validation['conflicts_detected']:
        logger.warning(f"  Tier 2C: Triage conflict detected - {validation['reason']}")
        # Use Investigation Engine's suggested section
        return validation['corrected_section']

    return triage_decision['section']
```

**Implementation**:
1. Expand embryonal_markers list with WNT pathway markers
2. Add check for problem_list_diagnoses
3. Implement `_medgemma_clinical_triage()` for Tier 2B
4. Implement `_investigation_engine_validate_triage()` for Tier 2C

**File to Modify**: `lib/who_reference_triage.py`
**Estimated Time**: 3-4 hours

---

### **Phase 0.3: Stage 3 Validation - Cross-Validation Layer**
**Goal**: Validate WHO classification against ALL diagnostic evidence

**New Stage After WHO Classification**:
```python
def _stage3_validate_diagnosis(
    self,
    who_classification: Dict,
    stage1_findings: Dict,
    all_evidence: List[DiagnosisEvidence]
) -> Dict:
    """
    Stage 3: Cross-validate WHO classification against all evidence.

    Validations:
    1. Biological plausibility (marker-diagnosis compatibility)
    2. Evidence consistency (does diagnosis match all sources?)
    3. Problem list cross-check (do problem lists agree?)
    4. Temporal consistency (diagnosis stable over time?)
    """

    diagnosis = who_classification.get('who_2021_diagnosis', '')
    markers = stage1_findings.get('molecular_markers', [])

    validation_result = {
        'is_valid': True,
        'confidence': who_classification.get('confidence', 0.5),
        'violations': [],
        'warnings': [],
        'conflicts': []
    }

    # Check 1: Biological plausibility
    violations = self._check_biological_plausibility(diagnosis, markers)
    if violations:
        validation_result['is_valid'] = False
        validation_result['violations'].extend(violations)
        logger.error(f"❌ CRITICAL: Diagnosis '{diagnosis}' fails biological plausibility")
        for v in violations:
            logger.error(f"    {v}")

    # Check 2: Cross-check against problem list diagnoses
    problem_diagnoses = [e.diagnosis for e in all_evidence
                         if e.source == EvidenceSource.PROBLEM_LIST]
    conflicts = self._check_problem_list_consistency(diagnosis, problem_diagnoses)
    if conflicts:
        validation_result['conflicts'].extend(conflicts)
        logger.warning(f"⚠️  Diagnosis conflicts with problem list")

    # Check 3: Marker-diagnosis compatibility
    incompatibilities = self._check_marker_diagnosis_compatibility(diagnosis, markers)
    if incompatibilities:
        validation_result['is_valid'] = False
        validation_result['violations'].extend(incompatibilities)

    # If validation fails, trigger Investigation Engine for resolution
    if not validation_result['is_valid']:
        logger.error("❌ Validation FAILED - Triggering Investigation Engine")
        corrected_diagnosis = self._investigation_engine_resolve_diagnosis(
            who_classification,
            stage1_findings,
            all_evidence,
            validation_result
        )
        return corrected_diagnosis

    # If conflicts but not violations, lower confidence
    if validation_result['conflicts']:
        validation_result['confidence'] *= 0.8
        who_classification['confidence'] = validation_result['confidence']
        who_classification['validation_warnings'] = validation_result['conflicts']

    who_classification['validation'] = validation_result
    return who_classification
```

**Biological Plausibility Rules**:
```python
IMPOSSIBLE_COMBINATIONS = {
    ('APC', 'glioblastoma'): "APC mutations are specific to WNT-medulloblastoma",
    ('CTNNB1', 'glioblastoma'): "CTNNB1 mutations are WNT pathway (medulloblastoma)",
    ('IDH1', 'medulloblastoma'): "IDH mutations never occur in medulloblastoma",
    ('IDH2', 'medulloblastoma'): "IDH mutations never occur in medulloblastoma",
    ('1p/19q', 'medulloblastoma'): "1p/19q codeletion is specific to oligodendroglioma",
    ('H3 K27', 'medulloblastoma'): "H3 K27 mutations are specific to diffuse midline glioma",
}
```

**Integration Point**: Called after Stage 2 WHO classification
**File to Create**: `lib/diagnosis_validator.py`
**File to Modify**: `scripts/patient_timeline_abstraction_V3.py`
**Estimated Time**: 2-3 hours

---

### **Phase 0.4: Diagnosis Anchoring for Downstream Phases**
**Goal**: Establish validated diagnosis as the ground truth for Phase 1-6

**Implementation**:
```python
# In patient_timeline_abstraction_V3.py

def _phase0_establish_diagnosis_anchor(self):
    """
    Phase 0: Establish diagnosis as foundational anchor BEFORE timeline extraction.

    This ensures all downstream analysis (Phase 1-6) is contextualized by
    the validated diagnosis.
    """

    logger.info("=" * 80)
    logger.info("PHASE 0: DIAGNOSTIC REASONING - FOUNDATIONAL ANCHOR")
    logger.info("=" * 80)

    # Phase 0.1: Aggregate evidence from all sources
    logger.info("[Phase 0.1] Aggregating diagnostic evidence from all sources...")
    evidence_aggregator = DiagnosticEvidenceAggregator()
    all_evidence = evidence_aggregator.aggregate_all_evidence(self.patient_fhir_id)
    logger.info(f"  Collected {len(all_evidence)} pieces of diagnostic evidence")

    # Phase 0.2: WHO Classification with tiered triage
    logger.info("[Phase 0.2] Performing WHO 2021 classification with tiered reasoning...")
    who_classification = self._generate_who_2021_classification_tiered(all_evidence)

    # Phase 0.3: Validate diagnosis against all evidence
    logger.info("[Phase 0.3] Validating diagnosis against all evidence...")
    validated_diagnosis = self._stage3_validate_diagnosis(
        who_classification,
        who_classification.get('stage1_findings'),
        all_evidence
    )

    # Phase 0.4: Establish anchoring confidence
    confidence = validated_diagnosis.get('confidence', 0.0)
    is_anchored = confidence >= 0.7 and validated_diagnosis.get('validation', {}).get('is_valid', False)

    validated_diagnosis['anchored_diagnosis'] = is_anchored

    if is_anchored:
        logger.info(f"✅ DIAGNOSIS ANCHORED (confidence={confidence:.2f})")
        logger.info(f"   {validated_diagnosis.get('who_2021_diagnosis')}")
    else:
        logger.warning(f"⚠️  DIAGNOSIS NOT ANCHORED (confidence={confidence:.2f})")
        logger.warning(f"   Phase 1-6 will proceed but results should be reviewed")
        logger.warning(f"   Phase 7 QA/QC will perform comprehensive validation")

    # Store for Phase 1-6 and Phase 7
    self.anchored_diagnosis = validated_diagnosis

    return validated_diagnosis
```

**Integration Point**: Called at START of main extraction (before Phase 1)
**File to Modify**: `scripts/patient_timeline_abstraction_V3.py`
**Estimated Time**: 1-2 hours

---

### **Phase 7: Investigation Engine End-to-End QA/QC**
**Goal**: Validate complete timeline against anchored diagnosis

**Implementation** (as designed in TIERED_REASONING_ARCHITECTURE.md):
```python
def _phase7_investigation_engine_qaqc(self):
    """
    Phase 7: End-to-end Investigation Engine quality assurance.

    Validates:
    1. Temporal consistency (dates make sense?)
    2. Clinical protocol coherence (treatment matches diagnosis?)
    3. Data completeness (critical milestones present?)
    4. Extraction failure patterns (systematic gaps?)
    5. Disease progression logic (tumor trajectory plausible?)
    """

    logger.info("=" * 80)
    logger.info("PHASE 7: INVESTIGATION ENGINE - END-TO-END QA/QC")
    logger.info("=" * 80)

    validation_report = {
        'temporal_consistency': self._validate_temporal_consistency(),
        'protocol_coherence': self._validate_protocol_against_diagnosis(),
        'data_completeness': self._assess_data_completeness(),
        'extraction_failures': self._analyze_extraction_failures(),
        'progression_logic': self._validate_disease_progression()
    }

    # Critical: Validate treatment matches anchored diagnosis
    protocol_validation = self._validate_protocol_against_diagnosis()
    if protocol_validation['violations']:
        logger.error("❌ CRITICAL: Treatment protocol does not match diagnosis")
        for violation in protocol_validation['violations']:
            logger.error(f"    {violation}")

    return validation_report

def _validate_protocol_against_diagnosis(self):
    """
    Validate treatment protocol matches WHO 2021 standards for this diagnosis.

    Examples:
    - Medulloblastoma, WNT-activated → Expect CSI (craniospinal irradiation) ~23.4-36 Gy
    - Glioblastoma, IDH-wildtype → Expect RT 60 Gy + concurrent TMZ
    - IDH-mutant Grade 2 astrocytoma → Should NOT see 60 Gy (max 54 Gy)
    """

    diagnosis = self.anchored_diagnosis.get('who_2021_diagnosis', '').lower()
    timeline_events = self.timeline_events

    violations = []

    # Check medulloblastoma protocol
    if 'medulloblastoma' in diagnosis:
        radiation_events = [e for e in timeline_events if e.get('event_type') == 'radiation_episode_end']

        # Expect CSI (craniospinal irradiation)
        found_csi = any('craniospinal' in str(e.get('event_description', '')).lower()
                        for e in radiation_events)

        if not found_csi:
            violations.append("Medulloblastoma patient missing expected craniospinal irradiation")

        # Expect total dose 23.4-36 Gy to craniospinal + 54-55.8 Gy boost to posterior fossa
        # Check if doses are in expected range

    # Check glioblastoma protocol
    elif 'glioblastoma' in diagnosis:
        # Expect 60 Gy radiation + concurrent temozolomide
        # ...

    return {
        'is_valid': len(violations) == 0,
        'violations': violations,
        'warnings': []
    }
```

**Integration Point**: Called AFTER Phase 6 (artifact generation)
**File to Create**: `lib/investigation_engine_qaqc.py`
**File to Modify**: `scripts/patient_timeline_abstraction_V3.py`
**Estimated Time**: 4-5 hours

---

## Testing Strategy

### Unit Tests
1. Test `DiagnosticEvidenceAggregator` with Patient 6 data
2. Test WHO Triage tier 2B/2C with ambiguous cases
3. Test biological plausibility rules with impossible combinations
4. Test Stage 3 validation with Patient 6 (should catch APC + Glioblastoma)

### Integration Tests
1. **Patient 6 Full Run**: Verify correct diagnosis "Medulloblastoma, WNT-activated"
2. **All 6 Medulloblastoma Patients**: Verify all correctly classified
3. **Negative Test**: Create synthetic case with APC + IDH mutation (should fail validation)
4. **Phase 7 QA/QC**: Verify protocol validation catches mismatches

### Acceptance Criteria
- [ ] Patient 6: Diagnosis = "Medulloblastoma, WNT-activated", confidence >= 0.85
- [ ] All 6 medulloblastoma patients: Correct classification, anchored = True
- [ ] Biological impossibilities: Caught and flagged with clear error messages
- [ ] Phase 7 validation: Detects treatment-diagnosis mismatches
- [ ] Execution time: Phase 0 completes in < 5 minutes (acceptable overhead)

---

## Implementation Order

### Sprint Day 1 (Morning)
1. **Phase 0.1**: Implement `DiagnosticEvidenceAggregator` (2-3 hours)
   - Create `lib/diagnostic_evidence_aggregator.py`
   - Implement pathology, problem list, imaging extraction
   - Test on Patient 6

### Sprint Day 1 (Afternoon)
2. **Phase 0.2**: Implement WHO Triage with 3-tier reasoning (3-4 hours)
   - Modify `lib/who_reference_triage.py`
   - Add Tier 2B MedGemma triage
   - Add Tier 2C Investigation Engine validation
   - Add APC/CTNNB1 to embryonal markers
   - Test on Patient 6

### Sprint Day 1 (Evening) or Day 2 (Morning)
3. **Phase 0.3**: Implement Stage 3 validation (2-3 hours)
   - Create `lib/diagnosis_validator.py`
   - Implement biological plausibility checks
   - Implement problem list cross-checking
   - Test on Patient 6

### Sprint Day 2 (Afternoon)
4. **Phase 0.4**: Implement diagnosis anchoring (1-2 hours)
   - Modify `scripts/patient_timeline_abstraction_V3.py`
   - Add `_phase0_establish_diagnosis_anchor()`
   - Integrate all Phase 0 components
   - Test full Phase 0 on Patient 6

5. **Phase 7**: Implement Investigation Engine QA/QC (4-5 hours)
   - Create `lib/investigation_engine_qaqc.py`
   - Implement temporal consistency validation
   - Implement protocol coherence validation
   - Integrate into main workflow as Phase 7
   - Test on Patient 6

### Sprint Day 2 (Evening) or Day 3
6. **Integration Testing** (2-3 hours)
   - Run all 6 medulloblastoma patients
   - Verify diagnoses correct
   - Verify Phase 7 validates correctly
   - Document results

7. **Documentation** (1-2 hours)
   - Update TIERED_REASONING_ARCHITECTURE.md with Phase 0 details
   - Create WHO_TRIAGE_REASONING_PROMPTS.md
   - Update V5_1_IMPLEMENTATION_COMPLETE.md

---

## File Structure

### New Files
```
lib/
├── diagnostic_evidence_aggregator.py    (Phase 0.1)
├── diagnosis_validator.py               (Phase 0.3)
└── investigation_engine_qaqc.py         (Phase 7)

docs/
├── DIAGNOSTIC_REASONING_SPRINT_PLAN.md  (this file)
├── WHO_TRIAGE_REASONING_PROMPTS.md      (Tier 2B/2C prompt engineering)
└── V5_1_IMPLEMENTATION_COMPLETE.md      (completion summary)
```

### Modified Files
```
lib/
└── who_reference_triage.py              (Phase 0.2 - add tiered reasoning)

scripts/
└── patient_timeline_abstraction_V3.py   (Phases 0.4, 7 - integration)
```

---

## Risk Mitigation

### Risk 1: LLM Reasoning Overhead
**Concern**: Tier 2B/2C add LLM calls → slow down
**Mitigation**: Cache triage decisions, use lightweight prompts, fall back to Tier 2A when possible

### Risk 2: Phase 0 Extends Execution Time
**Concern**: Multi-source aggregation adds significant time
**Mitigation**:
- Parallelize evidence collection where possible
- Use Tier 2A (keywords) first, only escalate to Tier 2B/2C when needed
- Target < 5 minutes for Phase 0 (acceptable overhead)

### Risk 3: Breaking Changes to Existing Patients
**Concern**: New validation might flag existing "correct" diagnoses as invalid
**Mitigation**:
- Make validation warnings non-blocking initially
- Review flagged cases manually before enforcing strict validation
- Provide confidence degradation rather than hard failures

### Risk 4: MedGemma Hallucination in Triage
**Concern**: Tier 2B MedGemma triage might hallucinate WHO sections
**Mitigation**:
- Constrain Tier 2B output to predefined WHO sections (enum)
- Tier 2C Investigation Engine validates Tier 2B output
- Fall back to expanded Tier 2A rules if Tier 2B confidence < 0.7

---

## Success Metrics

### Quantitative
- Patient 6 diagnostic accuracy: 100% (currently 0%)
- All 6 medulloblastoma patients: 100% accuracy
- Biological plausibility violations caught: 100%
- Phase 0 execution time: < 5 minutes
- Phase 7 protocol validation: > 90% accuracy

### Qualitative
- Clear reasoning chains for all diagnoses
- Transparent conflict resolution
- Actionable warnings for low-confidence cases
- Integration with existing 3-tier architecture
- Maintainable code with clear separation of concerns

---

## Post-Sprint Tasks

1. **Expand Biological Rules**: Add more marker-diagnosis impossibility rules
2. **Enhance Multi-Source Extraction**: Add more clinical note types
3. **Protocol Knowledge Base**: Expand WHO 2021 protocol standards
4. **Visualization**: Add Phase 0/7 validation results to timeline artifact
5. **Performance Optimization**: Profile and optimize LLM calls

---

**Ready to implement? Let's start with Phase 0.1!**
