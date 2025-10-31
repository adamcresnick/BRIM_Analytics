# Patient Clinical Journey Timeline

**WHO 2021-Informed Treatment Response Assessment Framework**

A comprehensive system for constructing unified patient clinical journey timelines that integrate diagnosis, surgical procedures, treatments (chemotherapy and radiation), imaging studies, and clinical visits with automated treatment response assessment.

---

## 📁 Project Structure

```
patient_clinical_journey_timeline/
├── README.md                          # This file
├── docs/                              # Documentation
│   └── PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md  # 37-page technical design
├── sql/
│   ├── views/                         # Production Athena views
│   │   ├── V_PATIENT_CLINICAL_JOURNEY_TIMELINE.sql
│   │   └── V_PATIENT_TREATMENT_RESPONSE_SUMMARY.sql
│   └── examples/                      # Example queries (coming soon)
├── scripts/                           # Python orchestration scripts
│   ├── run_patient_timeline_abstraction.py  # NEW: Molecular-aware timeline abstraction
│   └── run_timeline_focused_abstraction.py  # Legacy: Binary extraction (deprecated)
├── tests/                             # Validation queries (coming soon)
└── output/                            # Generated abstractions and reports
```

### 📚 Documentation Files

- **[PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md](docs/PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md)**: 37-page technical design (1,100+ lines)
- **[MOLECULAR_TIMELINE_INTEGRATION_ARCHITECTURE.md](docs/MOLECULAR_TIMELINE_INTEGRATION_ARCHITECTURE.md)**: Integration of WHO 2021 molecular framework with timeline
- **[WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md](docs/WHO_2021_CLINICAL_CONTEXTUALIZATION_FRAMEWORK.md)**: Molecular-informed treatment interpretation
- **[EXISTING_VIEW_SCHEMA_REVIEW.md](docs/EXISTING_VIEW_SCHEMA_REVIEW.md)**: Schema documentation for v_pathology_diagnostics

---

## 🎯 Key Features

### 1. **Unified Timeline Construction**
- **Surgery-anchored**: All events measured relative to initial tumor surgery (`days_from_initial_surgery`)
- **8 event types**: diagnosis, surgery, chemo_episode_start/end, radiation_episode_start/end, imaging, visit
- **6 data sources**: v_pathology_diagnostics, v_procedures_tumor, v_chemo_treatment_episodes, v_radiation_episode_enrichment, v_imaging, v_visits_unified

### 2. **Treatment Response Detection (Free Text Analysis)**
Uses existing free text fields to detect treatment response patterns:

#### From `v_imaging.report_conclusion`:
- **Progression**: Keywords like "increased", "enlarged", "new enhancement", "recurrence"
- **Response**: Keywords like "decreased", "reduced", "improved", "resolved"
- **Stable**: Keywords like "unchanged", "stable", "no significant change"

#### From `v_procedures_tumor.proc_outcome_text`:
- **Extent of resection (EOR)**: GTR, STR, partial resection, biopsy
- **Residual tumor detection**: Keywords like "residual", "remaining tumor"

### 3. **WHO 2021 Treatment Paradigm Validation**
- **Radiation protocol checking**: Standard doses (54 Gy HGG, 23.4-54 Gy medulloblastoma)
- **Chemotherapy regimen classification**: Carboplatin/vincristine (LGG), temozolomide (HGG), multi-agent (medulloblastoma)
- **Molecular marker integration**: H3 status, IDH, BRAF, MYCN, TP53

### 4. **Progression-Free Survival (PFS) Calculation**
- Time to first progression event (from treatment completion)
- Patient-level metrics: `patient_days_to_progression`, `patient_pfs_from_treatment`, `patient_has_progressed`

### 5. **Timeline-Focused Binary Extraction**
Claude orchestrates MedGemma to extract from binary documents where free text is insufficient:
- Imaging with `progression_flag` set but vague free text (<50 chars)
- Imaging without response assessment (`response_flag IS NULL`)
- Surgeries with `resection_extent_from_text = 'unspecified_extent'`
- Baseline post-treatment imaging

---

## 🗄️ Main Athena Views

### `v_patient_clinical_journey_timeline`
**Purpose**: Unified chronological timeline of all clinical events per patient
**Size**: ~860 lines SQL
**Key Columns**:
```sql
-- Patient & Temporal
patient_fhir_id
event_sequence_number
event_date / event_datetime
days_from_initial_surgery
treatment_phase  -- pre_surgery, early_post_op, adjuvant_window, active, surveillance

-- Event Classification
event_type       -- diagnosis, surgery, chemo_episode_start, etc.
event_subtype    -- imaging_modality, surgery_type, etc.
event_description

-- Response Assessment (from free text)
progression_flag       -- progression_suspected, recurrence_suspected
response_flag          -- response_suspected, stable_disease, complete_response_suspected
imaging_phase          -- pre_op_baseline, immediate_post_op, early_post_radiation, surveillance
resection_extent_from_text  -- GTR, STR, partial_resection, biopsy

-- Clinical Context
patient_diagnosis
molecular_marker
linked_radiation_episode
linked_chemo_episode

-- PFS Metrics
patient_days_to_progression
patient_pfs_from_treatment
patient_has_progressed
```

**Example Query**:
```sql
-- Get full timeline for a patient
SELECT
    event_sequence_number,
    event_date,
    days_from_initial_surgery,
    treatment_phase,
    event_type,
    event_description,
    progression_flag,
    response_flag
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE patient_fhir_id = 'eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83'
ORDER BY event_sequence_number;
```

### `v_patient_treatment_response_summary`
**Purpose**: Patient-level treatment response summary
**Size**: ~100 lines SQL
**Key Columns**:
```sql
patient_fhir_id
patient_diagnosis
molecular_marker

-- Treatment History
initial_resection_extent
chemo_episode_count
radiation_episode_count

-- Latest Imaging Status by Phase
post_op_imaging_status
post_radiation_imaging_status
surveillance_imaging_status

-- PFS Metrics
progressed
days_to_progression
pfs_days_from_treatment_completion

-- Overall Assessment (RANO-inspired)
overall_response_classification  -- PD, PR, CR, SD, Early Response, Insufficient Data
```

**Example Query**:
```sql
-- Get response summary for all patients with HGG
SELECT
    patient_fhir_id,
    molecular_marker,
    initial_resection_extent,
    radiation_episode_count,
    overall_response_classification,
    progressed,
    days_to_progression
FROM fhir_prd_db.v_patient_treatment_response_summary
WHERE patient_diagnosis LIKE '%high-grade glioma%'
ORDER BY days_to_progression;
```

---

## 🤖 Timeline-Focused Abstraction Script

**Location**: `scripts/run_timeline_focused_abstraction.py`

**Architecture**:
- **Claude (orchestrator)**: Queries Athena views, identifies extraction targets, prioritizes documents, manages workflow
- **MedGemma (extractor)**: Performs NLP extraction on binary documents (PDFs, HTML, text)

**How It Works**:
1. **STEP 1**: Claude queries 6 Athena views to construct unified timeline
2. **STEP 2**: Claude analyzes timeline to identify documents needing binary extraction
   - HIGH priority: Progression events, unclear response, unspecified EOR
   - MEDIUM priority: Baseline post-treatment imaging
3. **STEP 3**: Claude orchestrates MedGemma extraction from v_binary_files
4. **STEP 4**: Claude generates summary with key findings

**Usage**:
```bash
# Basic usage
python scripts/run_timeline_focused_abstraction.py \
  --patient-id eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83

# Limit extractions
python scripts/run_timeline_focused_abstraction.py \
  --patient-id eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83 \
  --max-extractions 10 \
  --output-dir output/

# Output saved to: output/{patient_id}_timeline_focused_{timestamp}.json
```

**Extraction Priorities** (Claude's decision logic):

| Priority | Condition | Reason |
|----------|-----------|--------|
| **HIGH** | `progression_flag` set + `free_text_content < 50 chars` | Progression suspected but detail insufficient |
| **HIGH** | `response_flag IS NULL` + `imaging_phase` not pre-op | Response status unclear |
| **HIGH** | `resection_extent_from_text = 'unspecified_extent'` | EOR not documented in proc_outcome_text |
| **MEDIUM** | `imaging_phase IN ('immediate_post_op', 'early_post_radiation')` | Baseline assessment value |

---

## 🧬 Molecular-Aware Timeline Abstraction (NEW)

### Running the Molecular Timeline Abstraction Script

The **NEW** `run_patient_timeline_abstraction.py` script integrates WHO 2021 molecular classification with timeline construction for comprehensive patient assessment:

```bash
# Basic usage
python3 scripts/run_patient_timeline_abstraction.py \
  --patient-id Patient/eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83 \
  --output-dir output/

# Output: output/{timestamp}/{patient_id}_timeline_abstraction.json
```

**What It Does** (4-Phase Workflow):

**Phase 0: Molecular Profiling**
- Queries `v_pathology_diagnostics` for molecular markers (H3 K27, BRAF, IDH, MYCN, TP53, SMARCB1)
- Performs WHO 2021 classification (H3 K27-altered DMG, BRAF V600E LGG, MYCN-amplified MB, etc.)
- Determines expected prognosis and recommended protocols

**Phase 1: Load Patient Timeline**
- Tries to query `v_patient_clinical_journey_timeline` view (if deployed)
- Falls back to constructing timeline from 6 individual Athena views:
  - `v_pathology_diagnostics` (diagnosis events)
  - `v_procedures_tumor` (surgery events)
  - `v_chemo_treatment_episodes` (chemo start/end events)
  - `v_radiation_episode_enrichment` (radiation start/end events)
  - `v_imaging` (imaging with simple progression detection)
  - `v_visits_unified` (visit events)

**Phase 2: Protocol Validation**
- **Radiation validation**: Checks dose against molecular-specific protocols
  - H3 K27-altered DMG: 54 Gy ±2 Gy
  - BRAF V600E LGG: Often deferred (targeted therapy preferred)
  - IDH-wildtype GBM: 60 Gy ±2 Gy
  - Medulloblastoma WNT: 23.4 Gy (de-escalated)
  - Medulloblastoma SHH/Group 3/4: 54 Gy
- **Chemotherapy validation**: Checks regimen appropriateness
  - BRAF V600E: Should receive dabrafenib + trametinib (not traditional chemo)
  - MYCN-amplified MB: Should receive high-dose cisplatin/cyclophosphamide

**Phase 3: Identify Extraction Gaps**
- Flags high-priority pathology documents (extraction_priority 1-2) for binary NLP
- Identifies surgeries without EOR documentation
- Detects imaging without clear response assessment
- Prioritizes by molecular significance (CRITICAL findings first)

**Phase 4: Generate Clinical Summary**
- Timeline summary (total events, event type breakdown, timeline span)
- Protocol adherence status (ADHERENT/UNDERDOSED/OVERDOSED/MISSING)
- Clinical recommendations prioritized by urgency (URGENT/HIGH/STANDARD)

**Example Output**:

```json
{
  "patient_id": "Patient/eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83",
  "molecular_profile": {
    "who_2021_classification": "H3 K27-altered Diffuse Midline Glioma",
    "clinical_significance": "CRITICAL: Uniformly fatal, median survival 9-11 months",
    "expected_prognosis": "POOR: Expect progression within 6-12 months post-treatment",
    "recommended_protocols": {
      "radiation": "54 Gy focal radiation",
      "chemotherapy": "Concurrent temozolomide or clinical trial",
      "surveillance": "MRI every 2-3 months"
    }
  },
  "protocol_validations": [
    {
      "protocol_type": "radiation",
      "status": "ADHERENT",
      "actual_dose_cgy": 5400,
      "expected_dose_cgy": 5400,
      "severity": "info"
    }
  ],
  "extraction_gaps": [
    {
      "gap_type": "high_priority_pathology",
      "event_date": "2023-03-15",
      "extraction_priority": 1,
      "reason": "Priority 1 pathology document may contain additional molecular findings"
    }
  ],
  "clinical_summary": {
    "timeline_summary": {
      "total_events": 45,
      "event_types": {
        "diagnosis": 3,
        "surgery": 2,
        "radiation_start": 1,
        "chemotherapy_start": 1,
        "imaging": 25,
        "visit": 13
      },
      "timeline_span_days": 365
    },
    "recommendations": [
      {
        "priority": "STANDARD",
        "recommendation": "Surveillance: MRI every 2-3 months"
      }
    ]
  }
}
```

### Architecture Comparison

| Feature | **NEW**: run_patient_timeline_abstraction.py | **LEGACY**: run_full_multi_source_abstraction.py |
|---------|----------------------------------------------|--------------------------------------------------|
| **Data Source** | v_patient_clinical_journey_timeline VIEW + individual Athena views | DuckDB timeline database |
| **Molecular Awareness** | WHO 2021 classification in Phase 0, informs all downstream analysis | No molecular context |
| **Protocol Validation** | Molecular-specific (H3 K27 DMG = 54 Gy, WNT MB = 23.4 Gy) | Generic protocol checking |
| **Extraction Prioritization** | Uses extraction_priority field from v_pathology_diagnostics | Document-type based only |
| **Timeline Construction** | Athena-native (queries views directly) | Requires pre-populated DuckDB |
| **Output** | Single JSON with molecular context + protocol validation + clinical summary | Multiple JSON checkpoints |
| **Use Case** | Clinical decision support with molecular context | Comprehensive multi-source extraction |

---

## 📊 Use Cases

### Use Case 1: Complete Patient Journey
```sql
-- Chronological timeline for treatment decision support
SELECT
    event_sequence_number,
    event_date,
    days_from_initial_surgery,
    treatment_phase,
    event_type,
    event_description,
    patient_diagnosis,
    molecular_marker
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE patient_fhir_id = '{patient_id}'
ORDER BY event_sequence_number;
```

### Use Case 2: Treatment Response Analysis
```sql
-- Imaging findings across treatment timeline
SELECT
    event_date,
    days_from_initial_surgery,
    imaging_phase,
    event_description,
    progression_flag,
    response_flag,
    linked_radiation_episode,
    linked_chemo_episode
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE patient_fhir_id = '{patient_id}'
  AND event_type = 'imaging'
ORDER BY event_date;
```

### Use Case 3: Progression-Free Survival by Diagnosis
```sql
-- PFS metrics by diagnosis and molecular subtype
SELECT
    patient_diagnosis,
    molecular_marker,
    COUNT(*) as patient_count,
    COUNT(CASE WHEN patient_has_progressed = true THEN 1 END) as progressed_count,
    ROUND(AVG(patient_days_to_progression), 1) as avg_days_to_progression,
    ROUND(100.0 * COUNT(CASE WHEN patient_has_progressed = true THEN 1 END) / COUNT(*), 1) as progression_rate_pct
FROM (
    SELECT DISTINCT
        patient_fhir_id,
        patient_diagnosis,
        molecular_marker,
        patient_days_to_progression,
        patient_has_progressed
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE patient_diagnosis IS NOT NULL
)
GROUP BY patient_diagnosis, molecular_marker
HAVING COUNT(*) >= 3
ORDER BY progression_rate_pct DESC;
```

### Use Case 4: Protocol Adherence Monitoring
```sql
-- Identify patients with non-standard radiation doses
SELECT
    patient_fhir_id,
    patient_diagnosis,
    event_date,
    event_description,
    -- Extract dose from description
    CAST(REGEXP_EXTRACT(event_description, '(\d+) cGy', 1) AS INT) as dose_cgy
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE event_type = 'radiation_episode_end'
  AND (
    -- Medulloblastoma should be 2340-5400 cGy
    (patient_diagnosis LIKE '%medulloblastoma%'
     AND CAST(REGEXP_EXTRACT(event_description, '(\d+) cGy', 1) AS INT) NOT BETWEEN 2340 AND 5400)
    -- HGG should be 5400-6000 cGy
    OR (patient_diagnosis LIKE '%high-grade glioma%'
        AND CAST(REGEXP_EXTRACT(event_description, '(\d+) cGy', 1) AS INT) NOT BETWEEN 5400 AND 6000)
  )
ORDER BY patient_fhir_id, event_date;
```

---

## 🧪 Testing & Validation

### View Deployment
```sql
-- Deploy main timeline view
-- Run: sql/views/V_PATIENT_CLINICAL_JOURNEY_TIMELINE.sql in Athena console

-- Deploy response summary view
-- Run: sql/views/V_PATIENT_TREATMENT_RESPONSE_SUMMARY.sql in Athena console
```

### Validation Queries (Coming Soon)
- Event count validation (compare against source views)
- Temporal sequencing validation (no out-of-order events)
- Response flag accuracy (manual review sample)
- PFS calculation validation (compare against clinical records)

---

## 📚 Documentation

### Comprehensive Design Document
**Location**: `docs/PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md`
**Size**: 37 pages (1,100+ lines)
**Contents**:
- Executive summary and design principles
- Data source mappings (6 Athena views)
- Event type taxonomy (8 event types)
- WHO 2021 treatment paradigm integration
- Treatment response detection (free text patterns)
- Timeline construction logic (8-step process)
- Protocol validation framework
- Use cases with example queries (6 scenarios)
- Implementation plan (4 phases)
- Molecular marker integration (9 key markers)
- Performance optimization strategies

---

## 🔄 Integration with Existing Systems

### Compatibility
- **Existing Athena views**: Queries v_pathology_diagnostics, v_procedures_tumor, v_chemo_treatment_episodes, v_radiation_episode_enrichment, v_imaging, v_visits_unified
- **Existing agents**: Uses MedGemmaAgent, BinaryFileAgent from `mvp/` codebase
- **Document cache**: Leverages DocumentTextCache for efficiency
- **Existing prompts**: Uses extraction_prompts from agents/

### Independence
This project is **self-contained** in the `patient_clinical_journey_timeline/` folder and does not modify existing:
- `athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql`
- `mvp/scripts/run_full_multi_source_abstraction.py`
- Agent implementations or utilities

---

## 🚀 Future Enhancements

### Phase 5: Clinical Trial Matching
- Add trial eligibility flags based on diagnosis + molecular markers
- Link to external trial database (ClinicalTrials.gov)

### Phase 6: Predictive Analytics
- Feature extraction for ML models (treatment sequence patterns)
- Risk stratification based on time-to-treatment delays

### Phase 7: Visualization Support
- JSON output format for timeline visualization (Plotly, D3.js)
- Gantt chart data structure for episode display

---

## 📝 License & Attribution

**Author**: Claude (Anthropic) with domain expertise from WHO 2021 CNS Tumor Classification (5th edition)
**Created**: 2025-10-30
**Project**: RADIANT_PCA BRIM Analytics

**References**:
- WHO Classification of Tumours of the Central Nervous System (2021, 5th edition)
- RANO (Response Assessment in Neuro-Oncology) criteria
- CBTN (Children's Brain Tumor Network) anatomical ontology

---

## 🆘 Support & Troubleshooting

### Common Issues

**Issue**: Timeline view returns 0 events for patient
- **Check**: Patient has tumor surgeries in v_procedures_tumor (is_tumor_surgery = true)
- **Check**: Patient ID is correct (without 'Patient/' prefix)

**Issue**: `progression_flag` or `response_flag` are NULL for all imaging
- **Check**: v_imaging.report_conclusion contains free text (not NULL)
- **Solution**: Run timeline-focused abstraction script to extract from binary PDFs

**Issue**: `resection_extent_from_text` is 'unspecified_extent' for all surgeries
- **Check**: v_procedures_tumor.proc_outcome_text contains free text (not NULL)
- **Solution**: Run timeline-focused abstraction script to extract from operative notes

### Performance

**Expected query times** (1000 patient cohort):
- Single patient timeline: <1 second
- Full cohort timeline: 5-15 seconds
- Aggregation queries: 10-30 seconds

**Optimization tips**:
- Always filter by `patient_fhir_id` when possible (indexed)
- Use `treatment_phase` or `event_type` filters to reduce result set
- Consider materialized view for large cohort repeated queries

---

## 📧 Contact

For questions about this timeline framework, see:
- Design document: `docs/PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md`
- Main AGENT_CONTEXT.md for broader RADIANT_PCA project context
- GitHub issues: https://github.com/adamcresnick/RADIANT_PCA/issues
