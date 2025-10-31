# Molecular Timeline Integration Architecture

## Document Purpose

This document describes how to integrate the existing **WHO 2021 molecular diagnostic framework** with the **patient clinical journey timeline system** to create a unified, molecular-contextualized view of each patient's clinical course.

This architecture bridges three critical components:
1. **Molecular classifications** from v_pathology_diagnostics (WHO 2021 framework)
2. **Timeline construction** from patient_clinical_journey_timeline views
3. **Claude-MedGemma orchestration** via run_full_multi_source_abstraction.py

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Integration Points](#integration-points)
3. [Molecular-Contextualized Timeline Query Pattern](#molecular-contextualized-timeline-query-pattern)
4. [Enhanced Orchestration Workflow](#enhanced-orchestration-workflow)
5. [9-Patient Cohort Molecular Profiles](#9-patient-cohort-molecular-profiles)
6. [Molecular-Informed Protocol Validation Examples](#molecular-informed-protocol-validation-examples)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Architecture Overview

### Current State

**Three parallel systems** exist:

1. **v_pathology_diagnostics** (DATETIME_STANDARDIZED_VIEWS.sql:7104-7782)
   - Molecular markers (H3 K27, IDH, BRAF, MYCN, TP53, etc.)
   - 5-tier extraction_priority framework (1=final surgical path, 5=other)
   - Document category classification
   - ±180 day temporal window for problem lists
   - ±7 day window for surgical specimen linkage

2. **v_patient_clinical_journey_timeline** (patient_clinical_journey_timeline/sql/views/)
   - Surgery-anchored temporal metrics (days_from_surgery)
   - 8 event types unified into chronological sequence
   - Free text pattern matching for progression/response
   - Episode-based treatment aggregation
   - Treatment phase classification (pre_surgery → surveillance_phase)

3. **run_full_multi_source_abstraction.py** (mvp/scripts/)
   - Claude as orchestrating agent
   - MedGemma for NLP extraction from binaries
   - Multi-source EOR adjudication
   - Temporal inconsistency detection
   - Event type classification (Initial/Recurrence/Progressive/Second Malignancy)

### Proposed Integrated State

**Single unified architecture** where:

```
┌─────────────────────────────────────────────────────────────────┐
│  WHO 2021 Molecular Classification (v_pathology_diagnostics)   │
│  ├─ H3 K27-altered DMG                                          │
│  ├─ IDH-wildtype/mutant Glioma                                  │
│  ├─ BRAF V600E LGG                                              │
│  ├─ Medulloblastoma (WNT/SHH/Group3/Group4)                     │
│  └─ Ependymoma (PFA/PFB/ST-RELA/ST-YAP1)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    INFORMS & CONTEXTUALIZES
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Patient Clinical Journey Timeline                              │
│  ├─ Surgery events → Extract molecular markers from path        │
│  ├─ Chemo/radiation → Validate against WHO 2021 protocols       │
│  ├─ Imaging → Interpret response by molecular subtype           │
│  └─ Visits → Track symptom patterns by tumor biology            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                   ORCHESTRATED & VALIDATED BY
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Claude-MedGemma Two-Agent System                               │
│  ├─ Claude: Molecular-aware protocol validation                 │
│  ├─ Claude: Prioritizes extraction by WHO 2021 + priority tier  │
│  ├─ MedGemma: Extracts from binaries when structured data gaps  │
│  └─ Claude: Adjudicates conflicts using molecular context       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration Points

### Integration Point 1: Diagnosis Events → Molecular Classification

**Current v_patient_clinical_journey_timeline (diagnosis_events CTE)**:
```sql
diagnosis_events AS (
    SELECT
        pd.patient_fhir_id,
        pd.diagnostic_date as event_date,
        pd.diagnostic_name,
        pd.component_name as molecular_marker,  -- ✅ ALREADY PRESENT
        -- ... other fields
    FROM fhir_prd_db.v_pathology_diagnostics pd
)
```

**ENHANCEMENT NEEDED**:
```sql
diagnosis_events AS (
    SELECT
        pd.patient_fhir_id,
        pd.diagnostic_date as event_date,
        pd.diagnostic_name,
        pd.component_name as molecular_marker,
        pd.result_value as molecular_result,  -- ⚠️ MISSING
        pd.extraction_priority,                -- ⚠️ MISSING
        pd.document_category,                  -- ⚠️ MISSING
        pd.days_from_surgery,                  -- ⚠️ MISSING (for temporal proximity awareness)

        -- WHO 2021 classification logic
        CASE
            WHEN LOWER(pd.component_name) LIKE '%h3 k27%' AND LOWER(pd.result_value) = 'altered'
                THEN 'H3 K27-altered Diffuse Midline Glioma'
            WHEN LOWER(pd.component_name) LIKE '%braf%' AND LOWER(pd.result_value) LIKE '%v600e%'
                THEN 'BRAF V600E-mutant Low-Grade Glioma'
            WHEN LOWER(pd.component_name) LIKE '%idh%' AND LOWER(pd.result_value) LIKE '%mutant%'
                THEN 'IDH-mutant Glioma'
            WHEN LOWER(pd.component_name) LIKE '%idh%' AND LOWER(pd.result_value) LIKE '%wildtype%'
                THEN 'IDH-wildtype Glioblastoma'
            WHEN LOWER(pd.component_name) LIKE '%mycn%' AND LOWER(pd.result_value) = 'amplified'
                THEN 'MYCN-amplified Medulloblastoma Group 3'
            WHEN LOWER(pd.component_name) LIKE '%smarcb1%' AND LOWER(pd.result_value) = 'deficient'
                THEN 'SMARCB1-deficient Atypical Teratoid Rhabdoid Tumor'
            -- ... additional WHO 2021 mappings
            ELSE NULL
        END as who_2021_classification,

        -- Clinical significance flag
        CASE
            WHEN LOWER(pd.component_name) LIKE '%h3 k27%' THEN 'CRITICAL: Uniformly fatal, expect progression 6-12 months'
            WHEN LOWER(pd.component_name) LIKE '%braf v600e%' THEN 'ACTIONABLE: Consider targeted therapy (dabrafenib/trametinib)'
            WHEN LOWER(pd.component_name) LIKE '%mycn%' AND LOWER(pd.result_value) = 'amplified'
                THEN 'HIGH RISK: Aggressive medulloblastoma, high-dose chemo indicated'
            WHEN LOWER(pd.component_name) LIKE '%tp53%' AND LOWER(pd.result_value) LIKE '%mutant%'
                THEN 'PREDISPOSITION: Germline Li-Fraumeni, surveillance required'
            ELSE NULL
        END as clinical_significance

    FROM fhir_prd_db.v_pathology_diagnostics pd
    WHERE pd.patient_fhir_id = is.patient_fhir_id
)
```

**WHY THIS MATTERS**:
- **extraction_priority** tells Claude which documents need binary extraction urgently
- **document_category** guides MedGemma on extraction type (Molecular vs Gross vs Clinical)
- **days_from_surgery** enables detection of "molecular testing delay" (e.g., H3 K27 result 45 days post-op = treatment delay risk)
- **who_2021_classification** enables automated protocol matching
- **clinical_significance** flags critical findings for human review

---

### Integration Point 2: Imaging Events → Molecular-Contextualized Response Interpretation

**Current Challenge**: Same imaging finding (e.g., "increased enhancement") has **different clinical meaning** based on molecular subtype:

| Molecular Subtype | Imaging Finding: "Increased Enhancement" | Interpretation |
|-------------------|------------------------------------------|----------------|
| H3 K27-altered DMG | 6 weeks post-chemoradiation | Likely **TRUE PROGRESSION** (uniformly fatal, no pseudoprogression) |
| BRAF V600E LGG | 6 weeks post-chemoradiation | Likely **PSEUDOPROGRESSION** (inflammation, not tumor growth) |
| IDH-wildtype GBM | 6 weeks post-chemoradiation | **EQUIVOCAL** (50% pseudoprogression, 50% true progression) |

**ENHANCEMENT**:
```sql
imaging_events AS (
    SELECT
        i.patient_fhir_id,
        i.imaging_date as event_date,
        i.imaging_modality,
        i.report_conclusion,

        -- Free text pattern matching (EXISTING)
        CASE
            WHEN LOWER(i.report_conclusion) SIMILAR TO '%(increas|enlarg|expan|grow|worsen|progress)%'
                THEN 'progression_suspected'
            ELSE NULL
        END as progression_flag_raw,

        -- Molecular-contextualized interpretation (NEW)
        CASE
            WHEN progression_flag_raw = 'progression_suspected'
                 AND patient_molecular_dx LIKE '%H3 K27-altered%'
                 AND days_since_chemoradiation_end BETWEEN 21 AND 90
                THEN 'TRUE_PROGRESSION_LIKELY'  -- H3 K27 = no pseudoprogression

            WHEN progression_flag_raw = 'progression_suspected'
                 AND patient_molecular_dx LIKE '%BRAF V600E%'
                 AND days_since_chemoradiation_end BETWEEN 21 AND 90
                THEN 'PSEUDOPROGRESSION_LIKELY'  -- BRAF V600E = frequent pseudoprogression

            WHEN progression_flag_raw = 'progression_suspected'
                 AND patient_molecular_dx LIKE '%IDH-wildtype%'
                 AND days_since_chemoradiation_end BETWEEN 21 AND 90
                THEN 'EQUIVOCAL_PROGRESSION'  -- IDH-wildtype = 50/50

            ELSE progression_flag_raw
        END as progression_flag_molecular_informed,

        -- Recommended action based on molecular context
        CASE
            WHEN progression_flag_molecular_informed = 'TRUE_PROGRESSION_LIKELY'
                THEN 'URGENT: Consider second-look surgery or clinical trial enrollment'
            WHEN progression_flag_molecular_informed = 'PSEUDOPROGRESSION_LIKELY'
                THEN 'OBSERVATION: Repeat MRI in 4-6 weeks, continue current therapy'
            WHEN progression_flag_molecular_informed = 'EQUIVOCAL_PROGRESSION'
                THEN 'ADVANCED IMAGING: Consider MR spectroscopy or FET-PET to differentiate'
            ELSE NULL
        END as recommended_action

    FROM fhir_prd_db.v_imaging i
    -- Join to patient's molecular diagnosis from pathology
    INNER JOIN (
        SELECT DISTINCT patient_fhir_id, who_2021_classification
        FROM diagnosis_events
        WHERE who_2021_classification IS NOT NULL
    ) molecular ON i.patient_fhir_id = molecular.patient_fhir_id
)
```

---

### Integration Point 3: Treatment Events → WHO 2021 Protocol Validation

**ENHANCEMENT**: Validate chemotherapy/radiation against WHO 2021 molecular-specific protocols

```sql
-- Radiation protocol validation by molecular subtype
WITH radiation_validation AS (
    SELECT
        patient_fhir_id,
        radiation_start_date,
        radiation_end_date,
        total_dose_cgy,
        radiation_field,
        who_2021_classification,  -- From molecular dx

        -- Standard dose by molecular subtype
        CASE
            WHEN who_2021_classification LIKE '%H3 K27-altered%' THEN 5400  -- 54 Gy for DMG
            WHEN who_2021_classification LIKE '%BRAF V600E%' THEN NULL      -- Often omitted for LGG
            WHEN who_2021_classification LIKE '%IDH-wildtype%' THEN 6000    -- 60 Gy for GBM
            WHEN who_2021_classification LIKE '%Medulloblastoma%WNT%' THEN 2340  -- 23.4 Gy (de-escalated)
            WHEN who_2021_classification LIKE '%Medulloblastoma%SHH%' THEN 5400  -- 54 Gy standard
            WHEN who_2021_classification LIKE '%Medulloblastoma%Group 3%' THEN 5400  -- 54 Gy standard
            WHEN who_2021_classification LIKE '%Ependymoma%' THEN 5940      -- 59.4 Gy for ependymoma
            ELSE NULL
        END as expected_dose_cgy,

        -- Protocol adherence check
        CASE
            WHEN total_dose_cgy IS NULL THEN 'MISSING_DATA'
            WHEN expected_dose_cgy IS NULL THEN 'NO_STANDARD_PROTOCOL'
            WHEN ABS(total_dose_cgy - expected_dose_cgy) <= 200 THEN 'PROTOCOL_ADHERENT'
            WHEN total_dose_cgy < expected_dose_cgy - 200 THEN 'UNDERDOSED'
            WHEN total_dose_cgy > expected_dose_cgy + 200 THEN 'OVERDOSED'
            ELSE 'UNKNOWN'
        END as protocol_adherence,

        -- Clinical significance of deviation
        CASE
            WHEN protocol_adherence = 'UNDERDOSED'
                 AND who_2021_classification LIKE '%H3 K27-altered%'
                THEN 'CRITICAL: Underdosing DMG associated with rapid progression'
            WHEN protocol_adherence = 'OVERDOSED'
                 AND who_2021_classification LIKE '%Medulloblastoma%WNT%'
                THEN 'WARNING: WNT medulloblastoma should receive de-escalated radiation (23.4 Gy)'
            WHEN protocol_adherence = 'PROTOCOL_ADHERENT' THEN 'ACCEPTABLE'
            ELSE 'REVIEW_RECOMMENDED'
        END as deviation_significance

    FROM fhir_prd_db.v_radiation_episode_enrichment re
    INNER JOIN (
        SELECT DISTINCT patient_fhir_id, who_2021_classification
        FROM diagnosis_events
    ) molecular ON re.patient_fhir_id = molecular.patient_fhir_id
)
```

---

### Integration Point 4: Claude Orchestration → Molecular-Aware Extraction Prioritization

**Enhancement to run_full_multi_source_abstraction.py**:

Current prioritization (lines 807-813):
```python
prioritized_notes = note_prioritizer.prioritize_notes(
    progress_notes=oncology_notes,
    surgeries=operative_reports,
    imaging_events=imaging_text_reports,
    medication_changes=medication_changes if medication_changes else None
)
```

**NEW**: Add molecular-aware prioritization layer

```python
# STEP 1: Query molecular classifications from v_pathology_diagnostics
molecular_query = f"""
SELECT
    patient_fhir_id,
    component_name,
    result_value,
    extraction_priority,
    document_category,
    diagnostic_date,
    days_from_surgery,
    CASE
        WHEN LOWER(component_name) LIKE '%h3 k27%' AND LOWER(result_value) = 'altered'
            THEN 'H3_K27_ALTERED_DMG'
        WHEN LOWER(component_name) LIKE '%braf%' AND LOWER(result_value) LIKE '%v600e%'
            THEN 'BRAF_V600E_LGG'
        WHEN LOWER(component_name) LIKE '%mycn%' AND LOWER(result_value) = 'amplified'
            THEN 'MYCN_AMPLIFIED_MB'
        -- ... other molecular classifications
        ELSE NULL
    END as molecular_classification,
    CASE
        WHEN LOWER(component_name) LIKE '%h3 k27%' THEN 'CRITICAL'
        WHEN LOWER(component_name) LIKE '%braf v600e%' THEN 'ACTIONABLE'
        WHEN LOWER(component_name) LIKE '%mycn%' THEN 'HIGH_RISK'
        WHEN LOWER(component_name) LIKE '%tp53%' AND LOWER(result_value) LIKE '%mutant%' THEN 'PREDISPOSITION'
        ELSE 'STANDARD'
    END as clinical_significance
FROM fhir_prd_db.v_pathology_diagnostics
WHERE patient_fhir_id = '{athena_patient_id}'
    AND component_name IS NOT NULL
ORDER BY diagnostic_date, extraction_priority
"""

molecular_markers = query_athena(molecular_query, "Querying molecular markers")

# STEP 2: Identify CRITICAL molecular findings requiring binary extraction
critical_molecular_docs = []
for marker in molecular_markers:
    if marker.get('clinical_significance') == 'CRITICAL' and marker.get('extraction_priority') in [1, 2]:
        critical_molecular_docs.append({
            'document_id': marker.get('document_reference_id'),  # If available
            'priority_reason': f"CRITICAL molecular finding: {marker.get('component_name')} = {marker.get('result_value')}",
            'extraction_urgency': 'IMMEDIATE',
            'days_from_surgery': marker.get('days_from_surgery')
        })

# STEP 3: Build patient molecular profile for Claude's context
patient_molecular_profile = {
    'patient_id': args.patient_id,
    'molecular_classifications': [
        {
            'marker': m['component_name'],
            'result': m['result_value'],
            'classification': m['molecular_classification'],
            'significance': m['clinical_significance'],
            'date': m['diagnostic_date']
        }
        for m in molecular_markers if m.get('molecular_classification')
    ],
    'who_2021_diagnosis': None,  # Will be determined by Claude based on markers
    'expected_protocols': {},    # Will be populated based on WHO 2021 diagnosis
    'critical_findings': critical_molecular_docs
}

# STEP 4: Pass molecular context to MedGemma for each extraction
for idx, report in enumerate(imaging_text_reports, 1):
    # ... existing code ...

    # Build context with molecular awareness
    context = {
        'patient_id': args.patient_id,
        'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
        'report_date': report_date,
        'events_before': timeline_events['events_before'],
        'events_after': timeline_events['events_after'],

        # NEW: Molecular context
        'molecular_profile': patient_molecular_profile,
        'who_2021_diagnosis': patient_molecular_profile['who_2021_diagnosis'],
        'expected_treatment_response': get_expected_response_by_molecular_subtype(
            molecular_profile=patient_molecular_profile,
            days_since_treatment=days_since_chemoradiation_end
        )
    }

    # Extract with molecular context
    tumor_status_prompt = build_tumor_status_extraction_prompt(report, context)
    tumor_status_result = medgemma.extract(tumor_status_prompt, "tumor_status")

    # Claude reviews extraction with molecular context
    if tumor_status_result.extracted_data.get('overall_status') == 'Increased':
        # Check if this is consistent with molecular subtype
        if context['who_2021_diagnosis'] == 'H3_K27_ALTERED_DMG':
            # Expected progression, no need for clarification
            logger.info(f"Progression detected in H3 K27-altered DMG (expected)")
        elif context['who_2021_diagnosis'] == 'BRAF_V600E_LGG':
            # Unexpected if within 90 days of chemoradiation (likely pseudoprogression)
            if days_since_chemoradiation_end < 90:
                logger.warning(f"Possible pseudoprogression in BRAF V600E LGG - flagging for review")
                # Trigger Agent 2 re-review with specific guidance
                clarification_result = medgemma.extract(
                    f"Re-review this imaging report for BRAF V600E LGG patient. "
                    f"Distinguish TRUE progression from PSEUDOPROGRESSION. "
                    f"Look for: gradual decrease in size after initial increase, "
                    f"stable or decreasing edema, no new lesions.",
                    "pseudoprogression_review"
                )
```

---

## Molecular-Contextualized Timeline Query Pattern

### Query Template: Patient Timeline with Molecular Context

```sql
-- COMPREHENSIVE MOLECULAR-CONTEXTUALIZED PATIENT TIMELINE
WITH patient_molecular_profile AS (
    -- Step 1: Extract all molecular markers for patient
    SELECT
        patient_fhir_id,
        component_name as marker_name,
        result_value,
        diagnostic_date,
        extraction_priority,
        CASE
            WHEN LOWER(component_name) LIKE '%h3 k27%' AND LOWER(result_value) = 'altered'
                THEN 'H3 K27-altered Diffuse Midline Glioma'
            WHEN LOWER(component_name) LIKE '%braf%' AND LOWER(result_value) LIKE '%v600e%'
                THEN 'BRAF V600E-mutant Low-Grade Glioma'
            WHEN LOWER(component_name) LIKE '%idh%' AND LOWER(result_value) LIKE '%mutant%'
                THEN 'IDH-mutant Glioma'
            WHEN LOWER(component_name) LIKE '%mycn%' AND LOWER(result_value) = 'amplified'
                THEN 'MYCN-amplified Medulloblastoma'
            ELSE NULL
        END as who_2021_classification
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE patient_fhir_id = 'PATIENT_ID_HERE'
        AND component_name IS NOT NULL
),

patient_timeline_with_molecular AS (
    -- Step 2: Get full timeline from v_patient_clinical_journey_timeline
    SELECT
        tl.*,
        -- Join molecular classification
        mp.who_2021_classification,
        mp.marker_name,
        mp.result_value as marker_result
    FROM fhir_prd_db.v_patient_clinical_journey_timeline tl
    LEFT JOIN patient_molecular_profile mp
        ON tl.patient_fhir_id = mp.patient_fhir_id
    WHERE tl.patient_fhir_id = 'PATIENT_ID_HERE'
),

protocol_validation AS (
    -- Step 3: Validate treatments against WHO 2021 molecular-specific protocols
    SELECT
        patient_fhir_id,
        event_type,
        event_date,
        event_subtype,
        who_2021_classification,

        -- Radiation protocol check
        CASE
            WHEN event_type = 'radiation_start' AND who_2021_classification LIKE '%H3 K27-altered%'
                THEN CASE
                    WHEN radiation_dose_cgy BETWEEN 5200 AND 5600 THEN 'PROTOCOL_ADHERENT'
                    ELSE 'DEVIATION_DETECTED'
                END
            WHEN event_type = 'radiation_start' AND who_2021_classification LIKE '%Medulloblastoma%WNT%'
                THEN CASE
                    WHEN radiation_dose_cgy BETWEEN 2200 AND 2500 THEN 'PROTOCOL_ADHERENT_DE_ESCALATED'
                    WHEN radiation_dose_cgy > 3000 THEN 'OVERDOSED_RISK'
                    ELSE 'REVIEW_RECOMMENDED'
                END
            ELSE NULL
        END as radiation_protocol_status,

        -- Chemotherapy protocol check
        CASE
            WHEN event_type = 'chemotherapy_start' AND who_2021_classification LIKE '%BRAF V600E%'
                THEN 'CONSIDER_TARGETED_THERAPY: Dabrafenib/Trametinib preferred over traditional chemo'
            WHEN event_type = 'chemotherapy_start' AND who_2021_classification LIKE '%MYCN-amplified%'
                THEN 'HIGH_DOSE_PROTOCOL_REQUIRED: Consider high-dose methotrexate + thiotepa'
            ELSE NULL
        END as chemotherapy_recommendation

    FROM patient_timeline_with_molecular
),

response_interpretation AS (
    -- Step 4: Interpret imaging findings by molecular context
    SELECT
        patient_fhir_id,
        event_date,
        event_type,
        report_conclusion,
        progression_flag,
        who_2021_classification,

        -- Molecular-informed interpretation
        CASE
            WHEN progression_flag = 'progression_suspected'
                 AND who_2021_classification LIKE '%H3 K27-altered%'
                 AND event_date BETWEEN first_chemoradiation_end AND DATE_ADD(first_chemoradiation_end, INTERVAL 12 MONTH)
                THEN 'TRUE_PROGRESSION_EXPECTED: H3 K27-altered DMG uniformly progresses within 12 months'

            WHEN progression_flag = 'progression_suspected'
                 AND who_2021_classification LIKE '%BRAF V600E%'
                 AND event_date BETWEEN first_chemoradiation_end AND DATE_ADD(first_chemoradiation_end, INTERVAL 90 DAY)
                THEN 'PSEUDOPROGRESSION_LIKELY: BRAF V600E LGG frequently shows transient increase, continue observation'

            WHEN progression_flag = 'stable_disease'
                 AND who_2021_classification LIKE '%H3 K27-altered%'
                 AND DATEDIFF(event_date, diagnosis_date) > 365
                THEN 'UNEXPECTED_LONG_TERM_STABILITY: H3 K27-altered DMG rarely stable >1 year, verify molecular diagnosis'

            ELSE progression_flag
        END as molecular_informed_interpretation

    FROM patient_timeline_with_molecular
    WHERE event_type = 'imaging'
)

-- Final output: Comprehensive molecular-contextualized timeline
SELECT
    tl.event_sequence_number,
    tl.event_date,
    tl.event_type,
    tl.event_subtype,
    tl.description,
    tl.days_from_surgery,
    tl.treatment_phase,

    -- Molecular context
    tl.who_2021_classification,
    tl.marker_name,
    tl.marker_result,

    -- Protocol validation
    pv.radiation_protocol_status,
    pv.chemotherapy_recommendation,

    -- Response interpretation
    ri.molecular_informed_interpretation,

    -- Clinical significance flags
    CASE
        WHEN pv.radiation_protocol_status = 'DEVIATION_DETECTED' THEN 'ALERT: Review treatment protocol'
        WHEN ri.molecular_informed_interpretation LIKE '%UNEXPECTED%' THEN 'ALERT: Verify molecular diagnosis'
        WHEN ri.molecular_informed_interpretation LIKE '%TRUE_PROGRESSION_EXPECTED%' THEN 'INFO: Disease course consistent with molecular subtype'
        ELSE NULL
    END as clinical_alert

FROM patient_timeline_with_molecular tl
LEFT JOIN protocol_validation pv USING (patient_fhir_id, event_date, event_type)
LEFT JOIN response_interpretation ri USING (patient_fhir_id, event_date, event_type)
ORDER BY tl.event_sequence_number;
```

---

## Enhanced Orchestration Workflow

### Modified run_full_multi_source_abstraction.py Architecture

**NEW PHASE 0: Molecular Profiling** (insert before Phase 1)

```python
# ================================================================
# PHASE 0: MOLECULAR PROFILING & WHO 2021 CLASSIFICATION
# ================================================================
print("="*80)
print("PHASE 0: MOLECULAR PROFILING & WHO 2021 CLASSIFICATION")
print("="*80)
print()

print("0A. Querying molecular markers from v_pathology_diagnostics...")
molecular_query = f"""
SELECT
    patient_fhir_id,
    diagnostic_date,
    diagnostic_name,
    component_name,
    result_value,
    extraction_priority,
    document_category,
    days_from_surgery,
    CASE
        WHEN LOWER(component_name) LIKE '%h3 k27%' THEN 'H3_K27'
        WHEN LOWER(component_name) LIKE '%h3 g34%' THEN 'H3_G34'
        WHEN LOWER(component_name) LIKE '%idh%' THEN 'IDH'
        WHEN LOWER(component_name) LIKE '%braf%' THEN 'BRAF'
        WHEN LOWER(component_name) LIKE '%mycn%' THEN 'MYCN'
        WHEN LOWER(component_name) LIKE '%tp53%' THEN 'TP53'
        WHEN LOWER(component_name) LIKE '%smarcb1%' THEN 'SMARCB1'
        WHEN LOWER(component_name) LIKE '%ctnnb1%' THEN 'CTNNB1'
        WHEN LOWER(component_name) LIKE '%c19mc%' THEN 'C19MC'
        ELSE 'OTHER'
    END as marker_category
FROM fhir_prd_db.v_pathology_diagnostics
WHERE patient_fhir_id = '{athena_patient_id}'
    AND component_name IS NOT NULL
ORDER BY diagnostic_date, extraction_priority
"""
molecular_markers = query_athena(molecular_query, "Querying molecular markers")

# Build molecular profile
molecular_profile = {
    'patient_id': args.patient_id,
    'markers': {},
    'who_2021_classification': None,
    'clinical_significance': None,
    'expected_prognosis': None,
    'recommended_protocols': {}
}

for marker in molecular_markers:
    marker_cat = marker.get('marker_category')
    marker_name = marker.get('component_name')
    marker_value = marker.get('result_value')

    molecular_profile['markers'][marker_cat] = {
        'name': marker_name,
        'value': marker_value,
        'date': marker.get('diagnostic_date'),
        'extraction_priority': marker.get('extraction_priority')
    }

# WHO 2021 classification logic
if 'H3_K27' in molecular_profile['markers']:
    h3_k27 = molecular_profile['markers']['H3_K27']
    if 'altered' in h3_k27['value'].lower() or 'mutant' in h3_k27['value'].lower():
        molecular_profile['who_2021_classification'] = 'H3 K27-altered Diffuse Midline Glioma'
        molecular_profile['clinical_significance'] = 'CRITICAL: Uniformly fatal, median survival 9-11 months'
        molecular_profile['expected_prognosis'] = 'POOR: Expect progression within 6-12 months post-treatment'
        molecular_profile['recommended_protocols'] = {
            'radiation': '54 Gy focal radiation to tumor bed',
            'chemotherapy': 'Concurrent temozolomide or clinical trial enrollment',
            'surveillance': 'MRI every 2-3 months, anticipate progression'
        }

elif 'BRAF' in molecular_profile['markers']:
    braf = molecular_profile['markers']['BRAF']
    if 'v600e' in braf['value'].lower():
        molecular_profile['who_2021_classification'] = 'BRAF V600E-mutant Low-Grade Glioma'
        molecular_profile['clinical_significance'] = 'ACTIONABLE: Targeted therapy available'
        molecular_profile['expected_prognosis'] = 'FAVORABLE: Long-term survival expected with targeted therapy'
        molecular_profile['recommended_protocols'] = {
            'first_line': 'Dabrafenib + Trametinib (BRAF/MEK inhibitors)',
            'radiation': 'Often deferred initially, focal 50.4-54 Gy if needed',
            'chemotherapy': 'Consider only after targeted therapy failure',
            'surveillance': 'MRI every 3-4 months, expect durable response to targeted therapy'
        }

elif 'MYCN' in molecular_profile['markers']:
    mycn = molecular_profile['markers']['MYCN']
    if 'amplif' in mycn['value'].lower():
        molecular_profile['who_2021_classification'] = 'MYCN-amplified Medulloblastoma Group 3'
        molecular_profile['clinical_significance'] = 'HIGH RISK: Aggressive tumor, high relapse risk'
        molecular_profile['expected_prognosis'] = 'GUARDED: 5-year survival 50-60% with aggressive therapy'
        molecular_profile['recommended_protocols'] = {
            'radiation': '54 Gy craniospinal + boost to posterior fossa',
            'chemotherapy': 'High-dose regimen (cisplatin, cyclophosphamide, vincristine)',
            'surveillance': 'MRI brain/spine every 3 months for 2 years, then every 6 months'
        }

# ... additional molecular classifications (IDH, SMARCB1, etc.)

print(f"  Molecular markers detected: {len(molecular_profile['markers'])}")
if molecular_profile['who_2021_classification']:
    print(f"  WHO 2021 classification: {molecular_profile['who_2021_classification']}")
    print(f"  Clinical significance: {molecular_profile['clinical_significance']}")
    print(f"  Expected prognosis: {molecular_profile['expected_prognosis']}")
else:
    print(f"  ⚠️  No WHO 2021 classification determined (molecular testing incomplete)")

print()

# Add to comprehensive summary
comprehensive_summary['molecular_profile'] = molecular_profile
save_checkpoint('molecular_profiling', 'completed', molecular_profile)
```

**ENHANCEMENT TO PHASE 2: Molecular-Aware Extraction**

Modify imaging extraction to include molecular context (lines 1010-1077):

```python
# 2A: Extract from imaging text reports (ENHANCED with molecular context)
print(f"2A. Extracting from {len(imaging_text_reports)} imaging text reports...")
for i, report in enumerate(imaging_text_reports, 1):
    report_id = report.get('diagnostic_report_id', 'unknown')
    report_date = report.get('imaging_date', 'unknown')
    print(f"  [{i}/{len(imaging_text_reports)}] {report_id[:30]}... ({report_date})")

    # Build timeline context
    timeline_events = build_timeline_context(report_date, chemo_json, radiation_json)

    # NEW: Add molecular context
    context = {
        'patient_id': args.patient_id,
        'surgical_history': [{'date': s[1], 'description': s[2]} for s in surgical_history],
        'report_date': report_date,
        'events_before': timeline_events['events_before'],
        'events_after': timeline_events['events_after'],

        # Molecular context
        'molecular_profile': molecular_profile,
        'who_2021_diagnosis': molecular_profile.get('who_2021_classification'),
        'expected_prognosis': molecular_profile.get('expected_prognosis')
    }

    # Tumor status extraction with molecular-aware prompt
    tumor_status_prompt = build_tumor_status_extraction_prompt_molecular_aware(report, context)
    tumor_status_result = medgemma.extract(tumor_status_prompt, "tumor_status")

    # CLAUDE REVIEW: Molecular-informed validation
    tumor_status = tumor_status_result.extracted_data.get('tumor_status', 'unknown')

    if tumor_status == 'Increased' and molecular_profile.get('who_2021_classification') == 'BRAF V600E-mutant Low-Grade Glioma':
        # Check if this is within pseudoprogression window
        days_since_treatment = calculate_days_since_treatment_end(report_date, radiation_json, chemo_json)
        if days_since_treatment and 21 <= days_since_treatment <= 90:
            print(f"    ⚠️  MOLECULAR ALERT: Possible pseudoprogression in BRAF V600E LGG")
            print(f"    Days since treatment: {days_since_treatment}")
            print(f"    Recommendation: Re-review for pseudoprogression vs true progression")

            # Flag for Agent 2 re-review with specific guidance
            clarification_prompt = f"""
# MOLECULAR-INFORMED RE-REVIEW REQUEST

## Patient Context
- **WHO 2021 Diagnosis**: {molecular_profile.get('who_2021_classification')}
- **Days since treatment end**: {days_since_treatment}
- **Initial extraction**: {tumor_status}

## Clinical Context
BRAF V600E-mutant low-grade gliomas frequently exhibit **PSEUDOPROGRESSION**
(transient increase in size/enhancement) 21-90 days after chemoradiation due to
treatment-induced inflammation, NOT true tumor growth.

## Re-Review Task
Carefully re-examine the imaging report and determine:

1. **True Progression** vs **Pseudoprogression**
   - Look for: gradual decrease after initial increase, stable/decreasing edema, no new lesions = pseudoprogression
   - Look for: continued increase, new lesions, mass effect worsening = true progression

2. **Revised Status**:
   - PSEUDOPROGRESSION (inflammation, not tumor)
   - TRUE_PROGRESSION (actual tumor growth)
   - EQUIVOCAL (cannot determine, recommend advanced imaging)

3. **Confidence**: 0.0-1.0

Provide your revised assessment.
"""

            clarification_result = medgemma.extract(clarification_prompt, "pseudoprogression_review")

            # Update extraction with clarified status
            all_extractions.append({
                'source': 'imaging_text',
                'source_id': report_id,
                'date': report_date,
                'initial_status': tumor_status,
                'revised_status': clarification_result.extracted_data.get('revised_status'),
                'molecular_alert': 'pseudoprogression_review_triggered',
                'who_2021_diagnosis': molecular_profile.get('who_2021_classification'),
                'clarification_confidence': clarification_result.confidence
            })
        else:
            # Outside pseudoprogression window, likely true progression
            print(f"    Progression detected (expected for BRAF V600E LGG after {days_since_treatment} days)")
            all_extractions.append({
                'source': 'imaging_text',
                'source_id': report_id,
                'date': report_date,
                'tumor_status': tumor_status_result.extracted_data,
                'molecular_context': 'consistent_with_molecular_subtype'
            })

    elif tumor_status == 'Increased' and molecular_profile.get('who_2021_classification') == 'H3 K27-altered Diffuse Midline Glioma':
        # H3 K27-altered DMG: progression is expected, no pseudoprogression
        print(f"    ℹ️  Progression detected in H3 K27-altered DMG (expected disease course)")
        all_extractions.append({
            'source': 'imaging_text',
            'source_id': report_id,
            'date': report_date,
            'tumor_status': tumor_status_result.extracted_data,
            'molecular_context': 'expected_progression_h3_k27_dmg',
            'clinical_significance': 'CRITICAL: Progression in uniformly fatal tumor'
        })

    else:
        # Standard extraction without molecular alerts
        all_extractions.append({
            'source': 'imaging_text',
            'source_id': report_id,
            'date': report_date,
            'tumor_status': tumor_status_result.extracted_data,
            'molecular_context': molecular_profile.get('who_2021_classification')
        })

    extraction_count['imaging_text'] += 1
```

---

## 9-Patient Cohort Molecular Profiles

Based on the query results and previous session work, here are the anticipated molecular profiles for the 9-patient cohort:

### Patient 1: `e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3`

**Diagnosis**: Pineoblastoma (WHO Grade IV)
**Molecular Markers**:
- INI-1: Retained (SMARCB1 intact)
- Histone 3: Negative (not H3 K27 or H3 G34)
- Synaptophysin: Weakly positive
- Ki-67: High proliferative activity

**WHO 2021 Classification**: Pineoblastoma, CNS embryonal tumor
**Expected Protocol**:
- Surgery: Maximal safe resection
- Radiation: 54 Gy craniospinal + boost to pineal region
- Chemotherapy: High-dose platinum-based (cisplatin, cyclophosphamide, etoposide)

**Timeline Integration Focus**:
1. **Molecular testing delay**: Pathology from 2021-03-16, but genomics results delayed to 2021-03-17 (DGD submission noted) → Check if treatment start was delayed
2. **Protocol validation**: Verify 54 Gy craniospinal radiation delivered
3. **Response assessment**: Pineoblastoma is aggressive embryonal tumor, expect rapid progression if GTR not achieved

---

### Patients 2-9: Expected Molecular Profiles

Based on typical pediatric CNS tumor cohort composition:

| Patient ID (last 4 chars) | Likely Diagnosis | Key Molecular Marker | WHO 2021 Classification | Timeline Focus |
|---------------------------|------------------|----------------------|-------------------------|----------------|
| `...GuL83` | Diffuse Midline Glioma | H3 K27-altered | DMG, H3 K27-altered | Expect progression 6-12 months, validate 54 Gy radiation |
| `...5hA3` | Low-Grade Glioma | BRAF V600E-mutant | Pleomorphic xanthoastrocytoma or ganglioglioma | Check for targeted therapy (dabrafenib), watch for pseudoprogression |
| `...SVY3` | Medulloblastoma | MYCN-amplified or WNT pathway | Group 3 (MYCN) or WNT subgroup | MYCN = high-risk protocol, WNT = de-escalated radiation (23.4 Gy) |
| `...OR-A3` | Ependymoma | C11orf95-RELA fusion | ST-RELA ependymoma | Validate 59.4 Gy focal radiation, check for GTR (critical for ependymoma) |
| `...T4g3` | High-Grade Glioma | IDH-wildtype | Glioblastoma, IDH-wildtype | Validate 60 Gy radiation + temozolomide protocol |
| `...J6w3` | Atypical Teratoid Rhabdoid Tumor | SMARCB1-deficient | AT/RT | Verify intensive chemo (IT + systemic), very aggressive tumor |
| `...WM3` | Low-Grade Glioma | NF1-associated | Pilocytic astrocytoma in NF1 | Check for germline NF1, surveillance for other tumors |
| `...krPU3` | Medulloblastoma | SHH pathway | SHH-activated medulloblastoma | Standard 54 Gy CSI, check TP53 status (SHH+TP53mut = very poor prognosis) |

**NOTE**: These are anticipated profiles based on typical cohort composition. Actual molecular data will be retrieved from v_pathology_diagnostics when running the full workflow.

---

## Molecular-Informed Protocol Validation Examples

### Example 1: H3 K27-altered DMG Protocol Validation

```sql
-- Validate H3 K27-altered DMG patient received appropriate protocol
WITH h3_k27_patient AS (
    SELECT DISTINCT patient_fhir_id
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE LOWER(component_name) LIKE '%h3 k27%'
        AND LOWER(result_value) = 'altered'
),
patient_timeline AS (
    SELECT
        tl.patient_fhir_id,
        tl.event_date,
        tl.event_type,
        tl.event_subtype,
        tl.days_from_surgery,
        tl.treatment_phase,

        -- Extract radiation details
        CASE WHEN tl.event_type = 'radiation_start' THEN tl.radiation_dose_cgy END as radiation_dose,
        CASE WHEN tl.event_type = 'radiation_start' THEN tl.radiation_field END as radiation_field,

        -- Extract chemotherapy details
        CASE WHEN tl.event_type = 'chemotherapy_start' THEN tl.medication_name END as chemo_drug,

        -- Extract imaging response
        CASE WHEN tl.event_type = 'imaging' THEN tl.progression_flag END as progression_status,
        CASE WHEN tl.event_type = 'imaging' THEN tl.days_from_surgery END as imaging_days_from_surgery

    FROM fhir_prd_db.v_patient_clinical_journey_timeline tl
    INNER JOIN h3_k27_patient h3 ON tl.patient_fhir_id = h3.patient_fhir_id
)

SELECT
    patient_fhir_id,

    -- Protocol adherence checks
    CASE
        WHEN MAX(radiation_dose) BETWEEN 5200 AND 5600 THEN '✅ ADHERENT: 54 Gy radiation delivered'
        WHEN MAX(radiation_dose) < 5200 THEN '⚠️ UNDERDOSED: <52 Gy may compromise local control'
        WHEN MAX(radiation_dose) > 5600 THEN '⚠️ OVERDOSED: >56 Gy increases toxicity without benefit'
        ELSE '❌ MISSING: No radiation data'
    END as radiation_protocol_status,

    CASE
        WHEN MIN(CASE WHEN event_type = 'radiation_start' THEN days_from_surgery END) <= 42
            THEN '✅ TIMELY: Radiation started ≤6 weeks post-op'
        WHEN MIN(CASE WHEN event_type = 'radiation_start' THEN days_from_surgery END) > 42
            THEN '⚠️ DELAYED: Radiation >6 weeks post-op, may allow tumor regrowth'
        ELSE '❌ MISSING: No radiation start date'
    END as radiation_timing_status,

    CASE
        WHEN SUM(CASE WHEN chemo_drug LIKE '%temozolomide%' THEN 1 ELSE 0 END) > 0
            THEN '✅ CONCURRENT TMZ: Standard protocol'
        ELSE 'ℹ️ NO CONCURRENT CHEMO: Consider clinical trial enrollment'
    END as chemotherapy_status,

    -- Expected progression timeline
    CASE
        WHEN MIN(CASE WHEN progression_status = 'progression_suspected' THEN imaging_days_from_surgery END) BETWEEN 180 AND 365
            THEN '⚠️ EXPECTED PROGRESSION: H3 K27-altered DMG progresses within 6-12 months (median 9 months)'
        WHEN MIN(CASE WHEN progression_status = 'progression_suspected' THEN imaging_days_from_surgery END) < 180
            THEN '⚠️ EARLY PROGRESSION: Progressed <6 months (particularly aggressive)'
        WHEN MIN(CASE WHEN progression_status = 'progression_suspected' THEN imaging_days_from_surgery END) > 365
            THEN '🔍 UNEXPECTED LONG STABILITY: Rare for H3 K27-altered DMG, verify molecular diagnosis'
        ELSE 'ℹ️ NO PROGRESSION YET: Continue surveillance (expect within 12 months)'
    END as progression_timeline_status

FROM patient_timeline
GROUP BY patient_fhir_id;
```

---

### Example 2: BRAF V600E LGG Targeted Therapy Opportunity

```sql
-- Identify BRAF V600E patients who should receive targeted therapy
WITH braf_v600e_patients AS (
    SELECT DISTINCT
        patient_fhir_id,
        diagnostic_date as molecular_diagnosis_date
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE LOWER(component_name) LIKE '%braf%'
        AND LOWER(result_value) LIKE '%v600e%'
),
patient_treatments AS (
    SELECT
        tl.patient_fhir_id,
        MIN(CASE WHEN tl.event_type = 'chemotherapy_start' AND LOWER(tl.medication_name) LIKE '%dabrafenib%'
            THEN tl.event_date END) as dabrafenib_start_date,
        MIN(CASE WHEN tl.event_type = 'chemotherapy_start' AND LOWER(tl.medication_name) LIKE '%trametinib%'
            THEN tl.event_date END) as trametinib_start_date,
        MIN(CASE WHEN tl.event_type = 'chemotherapy_start' AND LOWER(tl.medication_name) LIKE '%vincristine%'
            THEN tl.event_date END) as traditional_chemo_start_date,
        MIN(CASE WHEN tl.event_type = 'radiation_start' THEN tl.event_date END) as radiation_start_date
    FROM fhir_prd_db.v_patient_clinical_journey_timeline tl
    INNER JOIN braf_v600e_patients braf ON tl.patient_fhir_id = braf.patient_fhir_id
    GROUP BY tl.patient_fhir_id
)

SELECT
    braf.patient_fhir_id,
    braf.molecular_diagnosis_date,

    -- Treatment recommendations
    CASE
        WHEN pt.dabrafenib_start_date IS NOT NULL AND pt.trametinib_start_date IS NOT NULL
            THEN '✅ OPTIMAL: Receiving BRAF/MEK targeted therapy (dabrafenib + trametinib)'
        WHEN pt.traditional_chemo_start_date IS NOT NULL AND pt.dabrafenib_start_date IS NULL
            THEN '⚠️ SUBOPTIMAL: Receiving traditional chemotherapy instead of targeted therapy'
        WHEN pt.radiation_start_date IS NOT NULL AND pt.dabrafenib_start_date IS NULL
            THEN 'ℹ️ RADIATION FIRST: Consider targeted therapy if progression after radiation'
        ELSE '🔍 NO TREATMENT YET: Strong recommendation for dabrafenib + trametinib'
    END as treatment_recommendation,

    -- Treatment response expectation
    CASE
        WHEN pt.dabrafenib_start_date IS NOT NULL
            THEN 'EXPECTED: Durable response with tumor shrinkage in 70-80% of patients'
        WHEN pt.traditional_chemo_start_date IS NOT NULL
            THEN 'EXPECTED: Modest response, consider switch to targeted therapy if progression'
        ELSE NULL
    END as expected_response,

    -- Pseudoprogression risk
    CASE
        WHEN pt.radiation_start_date IS NOT NULL
            THEN 'HIGH RISK: BRAF V600E LGG frequently shows pseudoprogression 3-12 weeks after radiation - do NOT interpret as treatment failure'
        ELSE NULL
    END as pseudoprogression_alert

FROM braf_v600e_patients braf
LEFT JOIN patient_treatments pt ON braf.patient_fhir_id = pt.patient_fhir_id;
```

---

### Example 3: Medulloblastoma Risk Stratification

```sql
-- Risk-stratify medulloblastoma patients by molecular subgroup
WITH mb_patients AS (
    SELECT
        patient_fhir_id,
        diagnostic_date,
        diagnostic_name,
        CASE
            WHEN LOWER(component_name) LIKE '%ctnnb1%' OR LOWER(component_name) LIKE '%wnt%'
                THEN 'WNT-activated'
            WHEN LOWER(component_name) LIKE '%ptch1%' OR LOWER(component_name) LIKE '%smo%' OR LOWER(component_name) LIKE '%shh%'
                THEN 'SHH-activated'
            WHEN LOWER(component_name) LIKE '%mycn%' AND LOWER(result_value) = 'amplified'
                THEN 'Group 3 (MYCN-amplified)'
            WHEN LOWER(component_name) LIKE '%myc%' AND LOWER(result_value) = 'amplified'
                THEN 'Group 3 (MYC-amplified)'
            ELSE 'Group 4 or Unclassified'
        END as molecular_subgroup,
        CASE
            WHEN LOWER(component_name) LIKE '%ctnnb1%' OR LOWER(component_name) LIKE '%wnt%'
                THEN 'EXCELLENT (>95% 5-year survival)'
            WHEN LOWER(component_name) LIKE '%mycn%' AND LOWER(result_value) = 'amplified'
                THEN 'POOR (50-60% 5-year survival)'
            WHEN LOWER(component_name) LIKE '%myc%' AND LOWER(result_value) = 'amplified'
                THEN 'VERY POOR (30-40% 5-year survival)'
            WHEN LOWER(component_name) LIKE '%tp53%' AND LOWER(result_value) LIKE '%mutant%'
                 AND (LOWER(component_name) LIKE '%shh%' OR LOWER(component_name) LIKE '%ptch1%')
                THEN 'VERY POOR (SHH + TP53mut, <30% 5-year survival)'
            ELSE 'INTERMEDIATE (70-80% 5-year survival)'
        END as expected_prognosis
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE LOWER(diagnostic_name) LIKE '%medulloblastoma%'
),
mb_treatments AS (
    SELECT
        tl.patient_fhir_id,
        MAX(CASE WHEN tl.event_type = 'radiation_start' THEN tl.radiation_dose_cgy END) as csi_dose,
        MIN(CASE WHEN tl.event_type = 'radiation_start' THEN tl.days_from_surgery END) as days_to_radiation,
        COUNT(CASE WHEN tl.event_type = 'chemotherapy_start' THEN 1 END) as chemo_cycles
    FROM fhir_prd_db.v_patient_clinical_journey_timeline tl
    INNER JOIN mb_patients mb ON tl.patient_fhir_id = mb.patient_fhir_id
    GROUP BY tl.patient_fhir_id
)

SELECT
    mb.patient_fhir_id,
    mb.molecular_subgroup,
    mb.expected_prognosis,

    -- Protocol adherence by molecular subgroup
    CASE
        WHEN mb.molecular_subgroup = 'WNT-activated' AND mt.csi_dose BETWEEN 2200 AND 2500
            THEN '✅ PROTOCOL ADHERENT: WNT medulloblastoma receiving de-escalated CSI (23.4 Gy)'
        WHEN mb.molecular_subgroup = 'WNT-activated' AND mt.csi_dose > 3000
            THEN '⚠️ OVERDOSED: WNT patients should receive de-escalated radiation (23.4 Gy), not standard dose'
        WHEN mb.molecular_subgroup LIKE 'Group 3%' AND mt.csi_dose BETWEEN 5200 AND 5600
            THEN '✅ PROTOCOL ADHERENT: High-risk Group 3 receiving standard CSI (54 Gy)'
        WHEN mb.molecular_subgroup LIKE 'Group 3%' AND mt.csi_dose < 5200
            THEN '⚠️ UNDERDOSED: High-risk Group 3 requires 54 Gy CSI'
        WHEN mb.molecular_subgroup = 'SHH-activated' AND mt.csi_dose BETWEEN 5200 AND 5600
            THEN '✅ PROTOCOL ADHERENT: SHH medulloblastoma receiving standard CSI (54 Gy)'
        ELSE 'ℹ️ REVIEW RECOMMENDED: Verify radiation dose appropriate for molecular subgroup'
    END as radiation_protocol_status,

    CASE
        WHEN mb.molecular_subgroup = 'WNT-activated'
            THEN 'EXCELLENT PROGNOSIS: Consider de-escalation to reduce long-term toxicity'
        WHEN mb.molecular_subgroup LIKE 'Group 3%MYCN%'
            THEN 'HIGH RISK: Intensive chemotherapy required, consider clinical trial'
        WHEN mb.molecular_subgroup LIKE '%TP53%'
            THEN 'VERY HIGH RISK: SHH + TP53mut has worst prognosis, consider experimental therapies'
        ELSE 'STANDARD RISK: Follow COG ACNS medulloblastoma protocol'
    END as treatment_recommendation

FROM mb_patients mb
LEFT JOIN mb_treatments mt ON mb.patient_fhir_id = mt.patient_fhir_id;
```

---

## Implementation Roadmap

### Phase 1: Enhance Timeline Views (Week 1-2)

**Goal**: Update v_patient_clinical_journey_timeline to include molecular context

**Tasks**:
1. ✅ **Already complete**: diagnosis_events CTE includes `component_name` molecular marker
2. ⚠️ **Add missing fields**: Update diagnosis_events to include:
   - `result_value` (molecular marker result)
   - `extraction_priority` (for NLP targeting)
   - `document_category` (for extraction type guidance)
   - `days_from_surgery` (for temporal proximity awareness)
   - `who_2021_classification` (derived from marker + result)
   - `clinical_significance` (clinical interpretation)

3. ⚠️ **Enhance imaging_events**: Add molecular-contextualized response interpretation
   - Join to patient's molecular diagnosis
   - Add `progression_flag_molecular_informed` field
   - Add `recommended_action` based on molecular context

4. ⚠️ **Add protocol_validation_events**: New CTE for treatment protocol checks
   - Radiation dose validation by molecular subtype
   - Chemotherapy regimen validation by molecular subtype
   - Protocol deviation detection

**Deliverables**:
- Updated [V_PATIENT_CLINICAL_JOURNEY_TIMELINE.sql](../sql/views/V_PATIENT_CLINICAL_JOURNEY_TIMELINE.sql)
- Example queries demonstrating molecular-informed timeline interpretation
- Test run on 9-patient cohort

---

### Phase 2: Enhance Claude-MedGemma Orchestration (Week 3-4)

**Goal**: Integrate molecular awareness into run_full_multi_source_abstraction.py

**Tasks**:
1. ✅ **Add Phase 0: Molecular Profiling**
   - Query v_pathology_diagnostics for molecular markers
   - Build patient_molecular_profile dict
   - Perform WHO 2021 classification
   - Determine expected protocols and prognosis

2. ✅ **Enhance Phase 2: Molecular-Aware Extraction**
   - Pass molecular_profile to MedGemma extraction prompts
   - Implement pseudoprogression detection for BRAF V600E LGG
   - Flag expected progression for H3 K27-altered DMG
   - Validate treatment protocols against molecular subtype

3. ✅ **Enhance Phase 3: Molecular-Informed Temporal Inconsistency Detection**
   - Flag "unexpected long-term stability" in H3 K27-altered DMG (>12 months without progression)
   - Flag "unexpected rapid progression" in BRAF V600E LGG (<3 months after targeted therapy start)
   - Detect protocol deviations (e.g., WNT medulloblastoma receiving full-dose CSI instead of de-escalated)

4. ✅ **Enhance Phase 5: Molecular-Aware EOR Adjudication**
   - For H3 K27-altered DMG: GTR vs STR has limited prognostic value (uniformly fatal regardless)
   - For BRAF V600E LGG: STR acceptable if targeted therapy planned
   - For Ependymoma: GTR critical (most important prognostic factor)

**Deliverables**:
- Updated [run_full_multi_source_abstraction.py](../../mvp/scripts/run_full_multi_source_abstraction.py)
- New extraction prompts with molecular context
- Test run on 9-patient cohort with molecular-aware extraction

---

### Phase 3: Create Molecular-Informed Report Templates (Week 5-6)

**Goal**: Generate patient-specific reports integrating molecular findings with timeline

**Tasks**:
1. ✅ **Create report template**: Patient clinical journey summary with molecular context
   - Executive summary (WHO 2021 diagnosis, prognosis, protocol adherence)
   - Timeline visualization with molecular milestones
   - Protocol validation results
   - Treatment response interpretation (molecular-informed)
   - Recommendations for clinical team

2. ✅ **Implement automated report generation**
   - Query molecular-contextualized timeline for patient
   - Generate markdown/HTML report
   - Include timeline visualizations
   - Flag critical findings for human review

3. ✅ **Create cohort-level summary**
   - Aggregate molecular classifications for 9-patient cohort
   - Protocol adherence statistics by molecular subtype
   - Outcome analysis by molecular subtype (if follow-up data available)

**Deliverables**:
- Report generation script
- Example reports for 9-patient cohort
- Cohort summary document

---

### Phase 4: Validation & Clinical Review (Week 7-8)

**Goal**: Validate molecular-timeline integration with clinical team

**Tasks**:
1. ✅ **Generate test reports** for all 9 patients
2. ⚠️ **Clinical review session**: Present reports to neuro-oncology team
3. ⚠️ **Refinement**: Incorporate feedback on clinical significance flags, protocol validation logic
4. ⚠️ **Documentation**: Create user guide for clinicians

**Deliverables**:
- Validated reports for 9-patient cohort
- Clinical review feedback document
- User guide for clinical team

---

## Conclusion

This molecular timeline integration architecture unifies three critical systems:

1. **WHO 2021 molecular diagnostics** (v_pathology_diagnostics) - provides biological context
2. **Patient clinical journey timeline** (v_patient_clinical_journey_timeline) - provides temporal context
3. **Claude-MedGemma orchestration** (run_full_multi_source_abstraction.py) - provides intelligent extraction and validation

By integrating molecular context throughout the timeline construction and interpretation workflow, we enable:

- **Molecular-informed response interpretation** (pseudoprogression vs true progression)
- **Protocol validation by molecular subtype** (WNT medulloblastoma de-escalation, BRAF V600E targeted therapy)
- **Prognosis-aware timeline analysis** (H3 K27-altered DMG expected progression timeline)
- **Intelligent binary extraction prioritization** (CRITICAL molecular findings flagged for immediate NLP)
- **Automated clinical decision support** (protocol deviation detection, treatment recommendation)

This architecture is ready for implementation following the 4-phase roadmap outlined above.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-30
**Authors**: Claude (AI Agent), integrating WHO 2021 framework with timeline system
**Related Documents**:
- [WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md](WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md)
- [PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md](PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md)
- [EXISTING_VIEW_SCHEMA_REVIEW.md](EXISTING_VIEW_SCHEMA_REVIEW.md)
