# V4.7: Comprehensive Investigation Engine Architecture

**Date**: November 5, 2025
**Enhancement Type**: Multi-Phase Quality Assurance
**Status**: 🏗️ DESIGN PHASE

---

## Vision

Transform the Investigation Engine from a **reactive gap-filler** into a **proactive quality assurance system** that reviews EVERY phase for completeness, correctness, and optimization opportunities.

---

## Current Architecture (V4.6)

### Investigation Trigger Points

| Phase | What's Investigated | When | Status |
|-------|-------------------|------|--------|
| Phase 2.1 | Core timeline gaps | After validation | ✅ V4.6 |
| Phase 4.5 | Optional feature gaps | During gap-filling | ✅ V4.6 |

**Problem**: Only 2 of 7 phases are reviewed by Investigation Engine

---

## Proposed Architecture (V4.7)

### Investigation Trigger Points (Comprehensive)

| Phase | Investigation Focus | Quality Checks | Remediation Actions |
|-------|-------------------|----------------|-------------------|
| **Phase 1** | Data loading completeness | Empty result sets, NULL values, missing encounters | Retry with alternative queries, expanded date ranges |
| **Phase 2** | Timeline construction quality | Duplicate events, orphaned events, temporal gaps | Deduplicate, link orphans, identify missing periods |
| **Phase 2.1** | Core timeline completeness | Missing surgeries, treatment end dates | ✅ Suggest alternative data sources |
| **Phase 2.5** | Relationship enrichment | Missing related_events, incorrect ordinality | Re-link events, recalculate treatment lines |
| **Phase 3** | Gap identification accuracy | False positives, missed gaps | Validate gap detection logic |
| **Phase 4** | MedGemma extraction quality | Low confidence scores, validation failures | Retry with refined prompts, alternative documents |
| **Phase 4.5** | Gap-filling success | Remaining gaps after filling | ✅ Alternative document strategies |
| **Phase 5** | Protocol validation | Non-standard treatments, missing protocols | Flag for manual review |
| **Phase 6** | Artifact generation | Schema compliance, missing required fields | Validate JSON structure |

---

## Phase-by-Phase Investigation Design

### Phase 1: Data Loading Investigation

**Purpose**: Ensure all data sources returned adequate results

**Quality Checks**:
```python
def investigate_phase1_data_loading(self, loaded_data: Dict) -> Dict:
    """
    Investigate Phase 1 data loading for completeness issues.

    Checks:
    - Empty result sets (0 records loaded)
    - Unexpectedly small result sets (< expected minimum)
    - NULL/missing critical fields (patient demographics, WHO classification)
    - Missing encounters that should exist
    """
    investigation = {
        'phase': 'Phase 1',
        'issues_found': [],
        'suggestions': []
    }

    # Check demographics
    if not loaded_data.get('demographics'):
        investigation['issues_found'].append('No demographics loaded')
        investigation['suggestions'].append({
            'method': 'retry_demographics_query',
            'description': 'Retry patient demographics query with expanded search',
            'confidence': 0.9
        })

    # Check pathology
    if loaded_data.get('pathology_count', 0) == 0:
        investigation['issues_found'].append('No pathology records found')
        investigation['suggestions'].append({
            'method': 'query_alternative_pathology_sources',
            'description': 'Search v_observations_lab for tumor markers',
            'confidence': 0.7
        })

    # Check procedures
    if loaded_data.get('procedures_count', 0) == 0:
        investigation['issues_found'].append('No procedures found')
        investigation['suggestions'].append({
            'method': 'query_encounters_for_surgical_context',
            'description': 'Look for surgical encounters without Procedure resources',
            'confidence': 0.8
        })

    # Check chemotherapy
    if loaded_data.get('chemotherapy_count', 0) == 0:
        investigation['issues_found'].append('No chemotherapy episodes found')
        investigation['suggestions'].append({
            'method': 'query_medication_administration_direct',
            'description': 'Check v_medication_administration for chemo agents',
            'confidence': 0.85
        })

    # Check radiation
    if loaded_data.get('radiation_count', 0) == 0:
        investigation['issues_found'].append('No radiation episodes found')
        investigation['suggestions'].append({
            'method': 'query_procedure_radiation_codes',
            'description': 'Search Procedure resources for radiation therapy codes',
            'confidence': 0.75
        })

    # Check imaging
    if loaded_data.get('imaging_count', 0) == 0:
        investigation['issues_found'].append('No imaging studies found')
        investigation['suggestions'].append({
            'method': 'query_diagnostic_report_by_category',
            'description': 'Search DiagnosticReport by category (RAD, CT, MRI)',
            'confidence': 0.9
        })

    return investigation
```

**Expected Output**:
```
🔍 PHASE 1 INVESTIGATION:
  Issues Found: 2
    - No pathology records found
    - No chemotherapy episodes found

  Suggested Remediation:
    - query_alternative_pathology_sources: Search v_observations_lab for tumor markers (85% confidence)
    - query_medication_administration_direct: Check v_medication_administration (85% confidence)
```

---

### Phase 2: Timeline Construction Investigation

**Purpose**: Validate timeline structure and event relationships

**Quality Checks**:
```python
def investigate_phase2_timeline_construction(self, timeline_events: List[Dict]) -> Dict:
    """
    Investigate Phase 2 timeline construction for quality issues.

    Checks:
    - Duplicate events (same event_id, date, type)
    - Orphaned events (events without context)
    - Temporal gaps (> 180 days between events for active treatment patients)
    - Incorrect event ordering
    - Missing event_date or event_id
    """
    investigation = {
        'phase': 'Phase 2',
        'issues_found': [],
        'suggestions': [],
        'statistics': {
            'total_events': len(timeline_events),
            'event_types': {},
            'temporal_gaps_detected': 0,
            'orphaned_events': 0
        }
    }

    # Check for duplicates
    event_signatures = {}
    for event in timeline_events:
        sig = f"{event.get('event_type')}_{event.get('event_date')}_{event.get('event_id')}"
        if sig in event_signatures:
            investigation['issues_found'].append(f'Duplicate event: {sig}')
            investigation['suggestions'].append({
                'method': 'deduplicate_timeline_events',
                'description': 'Remove duplicate events based on event_id + date',
                'confidence': 1.0
            })
        event_signatures[sig] = True

    # Check for temporal gaps
    sorted_events = sorted(timeline_events, key=lambda x: x.get('event_date', ''))
    for i in range(len(sorted_events) - 1):
        current_date = datetime.fromisoformat(sorted_events[i].get('event_date', ''))
        next_date = datetime.fromisoformat(sorted_events[i+1].get('event_date', ''))
        gap_days = (next_date - current_date).days

        if gap_days > 180:  # 6 month gap
            investigation['statistics']['temporal_gaps_detected'] += 1
            investigation['issues_found'].append(f'Large temporal gap: {gap_days} days between events')
            investigation['suggestions'].append({
                'method': 'query_encounters_in_gap_period',
                'description': f'Search for clinical encounters between {current_date} and {next_date}',
                'confidence': 0.7
            })

    # Check for orphaned events (events without related_events)
    for event in timeline_events:
        if event.get('event_type') in ['surgery', 'chemo_start', 'radiation_start']:
            if not event.get('relationships', {}).get('related_events'):
                investigation['statistics']['orphaned_events'] += 1

    if investigation['statistics']['orphaned_events'] > 0:
        investigation['issues_found'].append(f'{investigation["statistics"]["orphaned_events"]} orphaned events without relationships')
        investigation['suggestions'].append({
            'method': 'retry_relationship_enrichment',
            'description': 'Re-run Gap #3 relationship enrichment with expanded temporal window',
            'confidence': 0.8
        })

    return investigation
```

---

### Phase 2.5: Treatment Ordinality Investigation

**Purpose**: Validate treatment line assignments and change reasons

**Quality Checks**:
```python
def investigate_phase2_5_treatment_ordinality(self, timeline_events: List[Dict]) -> Dict:
    """
    Investigate Phase 2.5 treatment ordinality for correctness.

    Checks:
    - Missing treatment_line for chemotherapy
    - Missing surgery_number for surgeries
    - Missing radiation_course for radiation
    - Incorrect sequencing (e.g., treatment_line 3 before treatment_line 2)
    - Missing reason_for_change_from_prior
    """
    investigation = {
        'phase': 'Phase 2.5',
        'issues_found': [],
        'suggestions': []
    }

    # Check chemotherapy treatment lines
    chemo_events = [e for e in timeline_events if e.get('event_type') in ['chemo_start', 'chemotherapy_start']]
    for chemo in chemo_events:
        ordinality = chemo.get('relationships', {}).get('ordinality', {})
        if not ordinality.get('treatment_line'):
            investigation['issues_found'].append(f'Missing treatment_line for chemotherapy on {chemo.get("event_date")}')
            investigation['suggestions'].append({
                'method': 'recalculate_treatment_ordinality',
                'description': 'Re-run treatment ordinality calculation',
                'confidence': 0.95
            })

    # Check treatment change reasons
    for i, chemo in enumerate(chemo_events[1:], start=1):
        ordinality = chemo.get('relationships', {}).get('ordinality', {})
        if not ordinality.get('reason_for_change_from_prior'):
            investigation['issues_found'].append(f'Missing reason_for_change_from_prior for treatment line {i+1}')
            investigation['suggestions'].append({
                'method': 'analyze_interim_imaging_for_progression',
                'description': 'Re-run Gap #2 treatment change reason analysis',
                'confidence': 0.8
            })

    return investigation
```

---

### Phase 3: Gap Identification Investigation

**Purpose**: Validate that gap detection logic is working correctly

**Quality Checks**:
```python
def investigate_phase3_gap_identification(self, identified_gaps: List[Dict]) -> Dict:
    """
    Investigate Phase 3 gap identification for false positives/negatives.

    Checks:
    - False positives (flagged as gap but data exists in different field)
    - Missed gaps (data clearly missing but not flagged)
    - Duplicate gap detection
    """
    investigation = {
        'phase': 'Phase 3',
        'issues_found': [],
        'suggestions': [],
        'statistics': {
            'total_gaps_identified': len(identified_gaps),
            'gap_types': {}
        }
    }

    # Count gap types
    for gap in identified_gaps:
        gap_type = gap.get('gap_type', 'unknown')
        investigation['statistics']['gap_types'][gap_type] = investigation['statistics']['gap_types'].get(gap_type, 0) + 1

    # Check for duplicate gaps
    gap_signatures = {}
    for gap in identified_gaps:
        sig = f"{gap.get('gap_type')}_{gap.get('event_id')}"
        if sig in gap_signatures:
            investigation['issues_found'].append(f'Duplicate gap: {sig}')
            investigation['suggestions'].append({
                'method': 'deduplicate_gap_list',
                'description': 'Remove duplicate gaps',
                'confidence': 1.0
            })
        gap_signatures[sig] = True

    return investigation
```

---

### Phase 4: MedGemma Extraction Investigation

**Purpose**: Ensure extraction quality and identify retry opportunities

**Quality Checks**:
```python
def investigate_phase4_medgemma_extraction(self, extractions: List[Dict]) -> Dict:
    """
    Investigate Phase 4 MedGemma extractions for quality issues.

    Checks:
    - Low confidence scores (< 0.5)
    - Validation failures
    - Empty/NULL extracted values
    - Extraction timeout/errors
    """
    investigation = {
        'phase': 'Phase 4',
        'issues_found': [],
        'suggestions': [],
        'statistics': {
            'total_extractions': len(extractions),
            'validation_failures': 0,
            'low_confidence': 0,
            'average_confidence': 0
        }
    }

    confidences = []
    for extraction in extractions:
        confidence = extraction.get('confidence_score', 0)
        confidences.append(confidence)

        if confidence < 0.5:
            investigation['statistics']['low_confidence'] += 1
            investigation['issues_found'].append(f'Low confidence extraction: {extraction.get("field_name")} = {confidence:.2f}')
            investigation['suggestions'].append({
                'method': 'retry_with_refined_prompt',
                'description': f'Retry extraction for {extraction.get("field_name")} with more specific prompt',
                'confidence': 0.7
            })

        if not extraction.get('validation_passed', True):
            investigation['statistics']['validation_failures'] += 1

    if confidences:
        investigation['statistics']['average_confidence'] = sum(confidences) / len(confidences)

    if investigation['statistics']['validation_failures'] > 0:
        investigation['issues_found'].append(f'{investigation["statistics"]["validation_failures"]} validation failures')
        investigation['suggestions'].append({
            'method': 'use_alternative_documents',
            'description': 'Retry with higher quality documents (treatment summaries vs progress notes)',
            'confidence': 0.8
        })

    return investigation
```

---

### Phase 5: Protocol Validation Investigation

**Purpose**: Flag non-standard treatments for review

**Quality Checks**:
```python
def investigate_phase5_protocol_validation(self, validation_results: Dict) -> Dict:
    """
    Investigate Phase 5 protocol validation results.

    Checks:
    - Non-standard radiation doses
    - Non-standard chemotherapy regimens
    - Missing protocol information
    - Contradictions between WHO grade and treatment intensity
    """
    investigation = {
        'phase': 'Phase 5',
        'issues_found': [],
        'suggestions': []
    }

    # Check radiation dose
    if validation_results.get('radiation_non_standard'):
        investigation['issues_found'].append(f'Non-standard radiation dose: {validation_results.get("radiation_dose_gy")} Gy')
        investigation['suggestions'].append({
            'method': 'manual_review_radiation_protocol',
            'description': 'Flag for clinical review - may be intentional dose reduction/escalation',
            'confidence': 1.0
        })

    # Check chemotherapy regimen
    if validation_results.get('chemotherapy_non_standard'):
        investigation['issues_found'].append('Non-standard chemotherapy regimen detected')
        investigation['suggestions'].append({
            'method': 'query_clinical_trial_enrollment',
            'description': 'Check if patient enrolled in clinical trial (ResearchSubject)',
            'confidence': 0.6
        })

    return investigation
```

---

### Phase 6: Artifact Generation Investigation

**Purpose**: Validate final JSON artifact quality

**Quality Checks**:
```python
def investigate_phase6_artifact_generation(self, artifact: Dict) -> Dict:
    """
    Investigate Phase 6 artifact generation for completeness.

    Checks:
    - Required fields present
    - Schema compliance
    - Data type correctness
    - Minimal completeness validation results
    """
    investigation = {
        'phase': 'Phase 6',
        'issues_found': [],
        'suggestions': []
    }

    # Check required fields
    required_fields = ['patient_fhir_id', 'timeline_events', 'who_2021_classification']
    for field in required_fields:
        if field not in artifact:
            investigation['issues_found'].append(f'Missing required field: {field}')
            investigation['suggestions'].append({
                'method': 'regenerate_artifact_with_field',
                'description': f'Ensure {field} is populated in artifact',
                'confidence': 1.0
            })

    # Check timeline_events not empty
    if not artifact.get('timeline_events'):
        investigation['issues_found'].append('timeline_events is empty')
        investigation['suggestions'].append({
            'method': 'investigate_phase1_and_phase2',
            'description': 'Major data loading or timeline construction failure',
            'confidence': 1.0
        })

    return investigation
```

---

## Implementation Approach

### Step 1: Create Central Investigation Orchestrator

**File**: `orchestration/investigation_engine.py`

```python
def investigate_all_phases(
    self,
    phase_results: Dict[str, Any]
) -> Dict[str, Dict]:
    """
    V4.7: Comprehensive investigation across all phases.

    Args:
        phase_results: Dictionary containing results from each phase

    Returns:
        Dictionary of investigation results per phase
    """
    all_investigations = {}

    # Investigate each phase
    all_investigations['phase_1'] = self.investigate_phase1_data_loading(
        phase_results.get('phase_1', {})
    )

    all_investigations['phase_2'] = self.investigate_phase2_timeline_construction(
        phase_results.get('phase_2', {}).get('timeline_events', [])
    )

    all_investigations['phase_2_1'] = self.investigate_phase2_1_minimal_completeness(
        phase_results.get('phase_2_1', {})
    )

    all_investigations['phase_2_5'] = self.investigate_phase2_5_treatment_ordinality(
        phase_results.get('phase_2_5', {}).get('timeline_events', [])
    )

    all_investigations['phase_3'] = self.investigate_phase3_gap_identification(
        phase_results.get('phase_3', {}).get('gaps', [])
    )

    all_investigations['phase_4'] = self.investigate_phase4_medgemma_extraction(
        phase_results.get('phase_4', {}).get('extractions', [])
    )

    all_investigations['phase_5'] = self.investigate_phase5_protocol_validation(
        phase_results.get('phase_5', {})
    )

    all_investigations['phase_6'] = self.investigate_phase6_artifact_generation(
        phase_results.get('phase_6', {}).get('artifact', {})
    )

    return all_investigations
```

### Step 2: Add Investigation Checkpoints After Each Phase

**File**: `scripts/patient_timeline_abstraction_V3.py`

```python
# After Phase 1
phase1_results = self._phase1_load_data()
if self.investigation_engine:
    investigation = self.investigation_engine.investigate_phase1_data_loading(phase1_results)
    self._log_investigation_results('Phase 1', investigation)

# After Phase 2
self._phase2_construct_initial_timeline()
if self.investigation_engine:
    investigation = self.investigation_engine.investigate_phase2_timeline_construction(self.timeline_events)
    self._log_investigation_results('Phase 2', investigation)

# After Phase 2.1 (already implemented)

# After Phase 2.5
self._phase2_5_assign_treatment_ordinality()
if self.investigation_engine:
    investigation = self.investigation_engine.investigate_phase2_5_treatment_ordinality(self.timeline_events)
    self._log_investigation_results('Phase 2.5', investigation)

# ... continue for all phases
```

### Step 3: Create Investigation Summary Report

After Phase 6, generate comprehensive investigation report:

```
================================================================================
V4.7 COMPREHENSIVE INVESTIGATION REPORT
================================================================================

Phase 1: Data Loading
  Status: ⚠️  2 issues found
  Issues:
    - No pathology records found
    - No chemotherapy episodes found
  Remediation Suggestions: 2

Phase 2: Timeline Construction
  Status: ✅ No issues found
  Statistics:
    - Total events: 45
    - Temporal gaps detected: 0
    - Orphaned events: 0

Phase 2.1: Minimal Completeness
  Status: ⚠️  1 issue found
  Issues:
    - 1 chemotherapy regimen missing end date
  Remediation Suggestions: 1

Phase 2.5: Treatment Ordinality
  Status: ✅ No issues found

Phase 3: Gap Identification
  Status: ✅ No issues found
  Statistics:
    - Total gaps identified: 8
    - Gap types: {surgery_eor: 3, radiation_dose: 2, imaging_conclusion: 3}

Phase 4: MedGemma Extraction
  Status: ⚠️  3 issues found
  Issues:
    - 2 low confidence extractions
    - 1 validation failure
  Average Confidence: 0.72
  Remediation Suggestions: 3

Phase 4.5: Gap-Filling
  Status: ✅ 5 of 8 gaps filled (62.5% success rate)

Phase 5: Protocol Validation
  Status: ✅ All protocols within standard ranges

Phase 6: Artifact Generation
  Status: ✅ No issues found

================================================================================
OVERALL QUALITY SCORE: 85/100
Total Issues Found: 6
Total Remediation Suggestions: 6
Phases with Issues: 3 of 7
================================================================================
```

---

## Benefits

1. **Comprehensive Quality Assurance**: Every phase reviewed, not just 2
2. **Proactive Problem Detection**: Issues caught early before propagating
3. **Clear Remediation Path**: Specific suggestions with confidence scores
4. **Quality Metrics**: Overall quality score for cohort-level analysis
5. **Transparency**: User sees exactly what worked and what didn't
6. **Continuous Improvement**: Investigation results feed into system refinement

---

## Implementation Priority

### Phase 1 (Immediate - V4.7)
- ✅ Phase 2.1 Investigation (already implemented)
- 🏗️ Phase 1 Investigation (data loading)
- 🏗️ Phase 4 Investigation (MedGemma extraction quality)

### Phase 2 (Short-term)
- Phase 2 Investigation (timeline construction)
- Phase 2.5 Investigation (treatment ordinality)
- Phase 3 Investigation (gap identification)

### Phase 3 (Medium-term)
- Phase 5 Investigation (protocol validation)
- Phase 6 Investigation (artifact generation)
- Comprehensive investigation report generation

---

## Next Steps

1. Implement Phase 1 data loading investigation
2. Implement Phase 4 MedGemma extraction investigation
3. Create `_log_investigation_results()` helper method
4. Add investigation checkpoints after each phase
5. Generate comprehensive investigation report after Phase 6

---

**Status**: 🏗️ Design Complete, Ready for Implementation
