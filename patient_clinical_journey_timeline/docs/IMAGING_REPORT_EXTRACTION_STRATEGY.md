# Imaging Report Extraction Strategy

**Purpose**: Documents how imaging report text is extracted from v_imaging and when MedGemma is needed for full binary extraction

**Created**: 2025-10-30
**Last Updated**: 2025-10-30

---

## Overview

v_imaging provides **structured imaging data** with the `report_conclusion` field containing text from `DiagnosticReport.conclusion`. However, this is often a **brief summary** of the full radiology report. For detailed tumor measurements, RANO response assessment, and treatment response evaluation, **MedGemma extraction from the full binary DiagnosticReport** may be required.

---

## v_imaging Schema (from DATETIME_STANDARDIZED_VIEWS.sql)

### Key Fields for Extraction

| Field | Description | Source | Extraction Need |
|-------|-------------|--------|----------------|
| `report_conclusion` | Brief summary text | `DiagnosticReport.conclusion` | **Already available** |
| `result_diagnostic_report_id` | FHIR ID linking to DiagnosticReport | `radiology_imaging.result_diagnostic_report_id` | **MedGemma target** |
| `diagnostic_report_id` | Alternative FHIR ID | `DiagnosticReport.id` | **MedGemma target** |
| `imaging_modality` | MRI, CT, etc. | Derived field | Context |
| `imaging_date` | Date of imaging study | Derived from `result_datetime` | Timeline anchoring |

### SQL Definition (lines 4118-4201)

```sql
SELECT
    ci.patient_id as patient_fhir_id,
    ci.imaging_date,
    ci.result_diagnostic_report_id,
    ci.imaging_modality,

    -- Diagnostic report fields
    dr.id as diagnostic_report_id,
    dr.status as report_status,
    dr.conclusion as report_conclusion,  -- THIS IS THE TEXT FIELD
    TRY(CAST(dr.issued AS TIMESTAMP(3))) as report_issued

FROM combined_imaging ci
LEFT JOIN fhir_prd_db.diagnostic_report dr
    ON ci.result_diagnostic_report_id = dr.id
```

**Key Insight**: `report_conclusion` comes from `dr.conclusion`, which is **often just a 1-2 sentence summary** (e.g., "Stable disease", "Decreased enhancing lesion"). The **full report** with detailed measurements is in the binary DiagnosticReport document.

---

## When to Extract from Binary

### Trigger Conditions for MedGemma Extraction

The script identifies imaging reports requiring binary extraction using these criteria:

```python
conclusion = imaging.get('report_conclusion', '')
# Vague conclusion = NULL, empty, OR <50 characters
if not conclusion or len(conclusion) < 50:
    # Flag for MedGemma extraction
```

### Examples of Vague Conclusions

| Conclusion Text | Length | Needs Extraction? |
|----------------|--------|------------------|
| `"Stable disease"` | 14 chars | **YES** |
| `"Progression"` | 11 chars | **YES** |
| `NULL` | 0 chars | **YES** |
| `"Interval decrease in size of enhancing lesion in right parietal lobe from 2.3 x 1.8 cm to 1.9 x 1.5 cm. No new lesions."` | 116 chars | NO (detailed enough) |
| `"Tumor measures 3.2 x 2.1 x 2.8 cm (AP x ML x SI), decreased from prior 3.8 x 2.5 x 3.1 cm."` | 89 chars | NO (has measurements) |

**Clinical Rationale**:
- RANO (Response Assessment in Neuro-Oncology) criteria require **bidimensional tumor measurements** (perpendicular diameters)
- Treatment response classification requires **comparing current vs prior measurements**
- Pseudoprogression window (21-90 days post-radiation) requires **detailed radiologic features** to distinguish treatment effect from true progression

---

## MedGemma Extraction Workflow

### Phase 3: Gap Identification

```python
# From patient_timeline_abstraction_V1.py (lines 653-671)
for imaging in imaging_events:
    conclusion = imaging.get('report_conclusion', '')
    if not conclusion or len(conclusion) < 50:
        diagnostic_report_id = imaging.get('diagnostic_report_id') or imaging.get('result_diagnostic_report_id')

        gaps.append({
            'gap_type': 'vague_imaging_conclusion',
            'priority': 'MEDIUM',
            'event_date': imaging.get('event_date'),
            'imaging_modality': imaging.get('imaging_modality'),
            'diagnostic_report_id': diagnostic_report_id,
            'recommended_action': 'Extract full radiology report for detailed tumor measurements',
            'clinical_significance': 'Detailed measurements needed for RANO response assessment',
            'medgemma_target': f'DiagnosticReport/{diagnostic_report_id}'  # FHIR resource reference
        })
```

### Phase 4: MedGemma Extraction (PLACEHOLDER)

**Current Status**: Phase 4 is a placeholder. When implemented, it will:

1. **Fetch binary DiagnosticReport** from FHIR server using `diagnostic_report_id`
2. **Call MedGemma** with specialized prompts for radiology report extraction
3. **Extract structured data**:
   - Tumor measurements (AP x ML x SI dimensions)
   - Lesion locations
   - Enhancement patterns
   - Comparison to prior studies
   - RANO response category (CR, PR, SD, PD)
4. **Integrate extractions** back into timeline_events
5. **Re-assess gaps** (iterative)

---

## Extraction Prioritization

### Priority Levels

Imaging report extraction is prioritized as **MEDIUM** by default, but escalated to **HIGH** in these scenarios:

| Scenario | Priority | Rationale |
|----------|----------|-----------|
| Imaging within **21-90 days post-radiation** | **HIGHEST** | Pseudoprogression window - critical for treatment decisions |
| Post-surgical imaging (<7 days) | **HIGH** | Assess extent of resection |
| Follow-up imaging with vague conclusion | **MEDIUM** | Needed for RANO assessment but not urgent |
| Baseline imaging | **HIGH** | Establishes tumor measurement baseline |

**Future Enhancement**: The script should add temporal context (days from surgery, days from radiation end) to adjust priority dynamically.

---

## Integration with WHO 2021 Timeline

### Pseudoprogression Window (Critical Use Case)

**Clinical Context**:
- H3 K27-altered DMG, BRAF V600E LGG, and other high-grade gliomas receive **radiation therapy**
- 21-90 days post-radiation: Treatment-related inflammation can **mimic tumor progression** on MRI
- **Clinical dilemma**: Is increased enhancement true progression or pseudoprogression?

**Extraction Need**:
- Detailed MRI measurements from **21-90 day window imaging**
- Comparison to immediate post-radiation baseline
- Enhancement patterns (solid vs ring-like)
- Diffusion characteristics (ADC values)
- Perfusion patterns (rCBV)

**Example Gap**:
```json
{
  "gap_type": "vague_imaging_conclusion",
  "priority": "HIGHEST",
  "event_date": "2023-08-15",
  "days_from_radiation_end": 45,
  "imaging_modality": "MRI",
  "report_conclusion": "Increased enhancement",
  "diagnostic_report_id": "DiagnosticReport/12345",
  "clinical_significance": "Within pseudoprogression window - detailed measurements critical to avoid premature treatment escalation",
  "medgemma_target": "DiagnosticReport/12345",
  "extraction_prompt": "Extract: 1) Tumor measurements (AP x ML x SI), 2) Enhancement pattern, 3) ADC values, 4) Comparison to prior, 5) Radiologist impression re: pseudoprogression vs progression"
}
```

---

## Structured Output from MedGemma

### Expected Extraction Schema

When MedGemma is implemented, it should extract:

```json
{
  "extraction_source": "DiagnosticReport/12345",
  "extraction_timestamp": "2025-10-30T22:55:00Z",
  "imaging_date": "2023-08-15",
  "imaging_modality": "MRI Brain with contrast",
  "lesion_measurements": [
    {
      "lesion_location": "Right parietal lobe",
      "dimensions_cm": {
        "ap": 3.2,
        "ml": 2.1,
        "si": 2.8
      },
      "enhancement_pattern": "Heterogeneous ring enhancement",
      "prior_dimensions_cm": {
        "ap": 3.8,
        "ml": 2.5,
        "si": 3.1
      },
      "percent_change": "-15.8%"
    }
  ],
  "additional_findings": [
    "Increased perilesional FLAIR signal",
    "No restricted diffusion",
    "Stable ventricular size"
  ],
  "rano_assessment": "Partial response (PR)",
  "radiologist_impression": "Decreased enhancing lesion consistent with treatment response. No evidence of pseudoprogression.",
  "comparison_study_date": "2023-06-20"
}
```

---

## Timeline Artifact Integration

### Before MedGemma Extraction

```json
{
  "event_type": "imaging",
  "event_date": "2023-08-15",
  "stage": 5,
  "source": "v_imaging",
  "imaging_modality": "MRI",
  "report_conclusion": "Decreased enhancing lesion",  // VAGUE
  "result_diagnostic_report_id": "DiagnosticReport/12345",
  "event_sequence": 89
}
```

### After MedGemma Extraction

```json
{
  "event_type": "imaging",
  "event_date": "2023-08-15",
  "stage": 5,
  "source": "v_imaging",
  "imaging_modality": "MRI Brain with contrast",
  "report_conclusion": "Decreased enhancing lesion",
  "result_diagnostic_report_id": "DiagnosticReport/12345",
  "event_sequence": 89,

  // ADDED BY MEDGEMMA
  "medgemma_extraction": {
    "extraction_id": "ext_2025_001",
    "tumor_measurements": {
      "current": {"ap": 3.2, "ml": 2.1, "si": 2.8},
      "prior": {"ap": 3.8, "ml": 2.5, "si": 3.1},
      "percent_change": -15.8
    },
    "rano_assessment": "Partial response (PR)",
    "enhancement_pattern": "Heterogeneous ring enhancement",
    "pseudoprogression_risk": "LOW (within expected response pattern)"
  },

  // ADDED BY PROTOCOL VALIDATION
  "who_2021_context": {
    "days_from_radiation_end": 45,
    "expected_surveillance_frequency": "Every 2-3 months",
    "is_pseudoprogression_window": true,
    "expected_rano_pattern": "PR or SD expected at this timepoint"
  }
}
```

---

## Gap Summary Output (Phase 3)

After Phase 3 completes, the script outputs:

```
PHASE 3: IDENTIFY GAPS REQUIRING BINARY EXTRACTION
  ✅ Identified 153 extraction opportunities
     missing_eor: 11
     missing_radiation_dose: 2
     vague_imaging_conclusion: 140
```

For the Pineoblastoma patient (test run), **140 out of 140 imaging studies** had vague conclusions requiring extraction.

---

## Future Enhancements

### 1. Temporal Context-Aware Prioritization

Add calculation of days from radiation/surgery to dynamically adjust priority:

```python
# Calculate temporal context
days_from_radiation = calculate_days_between(imaging_date, last_radiation_end_date)
days_from_surgery = calculate_days_between(imaging_date, initial_surgery_date)

# Adjust priority based on temporal context
if 21 <= days_from_radiation <= 90:
    priority = 'HIGHEST'  # Pseudoprogression window
elif days_from_surgery <= 7:
    priority = 'HIGH'  # Post-op assessment
else:
    priority = 'MEDIUM'
```

### 2. RANO Criteria Automation

Implement automated RANO response classification using:
- Bidimensional measurements (perpendicular diameters)
- Sum of products of perpendicular diameters (SPD)
- Comparison to baseline SPD
- New lesion detection
- Corticosteroid dose changes

### 3. MedGemma Prompt Templates

Create specialized prompts for different clinical scenarios:
- **Post-radiation**: Focus on pseudoprogression features
- **Post-surgery**: Focus on extent of resection
- **Surveillance**: Focus on RANO response assessment
- **Progression evaluation**: Focus on new lesions and SPD increase

---

## References

- **v_imaging SQL definition**: DATETIME_STANDARDIZED_VIEWS.sql (lines 4118-4201)
- **Timeline construction (Stage 5)**: patient_timeline_abstraction_V1.py (lines 569-585)
- **Gap identification logic**: patient_timeline_abstraction_V1.py (lines 653-671)
- **RANO Criteria**: Wen PY, et al. Updated response assessment criteria for high-grade gliomas (RANO). J Clin Oncol. 2010
- **Pseudoprogression**: Brandsma D, et al. Clinical features, mechanisms, and management of pseudoprogression in malignant gliomas. Lancet Oncol. 2008

---

**Document Version**: 1.0
**Created**: 2025-10-30
**Purpose**: Guide MedGemma integration for imaging report extraction in patient timeline abstraction framework
