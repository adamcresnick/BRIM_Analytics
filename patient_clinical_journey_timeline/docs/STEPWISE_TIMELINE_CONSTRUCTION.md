# Stepwise Timeline Construction Architecture

**Purpose**: Explains the 7-stage timeline construction approach that validates each treatment phase against WHO 2021 expected paradigms

**Created**: 2025-10-30
**Last Updated**: 2025-10-30

---

## Overview

The timeline construction follows a **stepwise staging approach** rather than a simple chronological merge. This architecture ensures that:

1. **Molecular diagnosis anchors all subsequent clinical decisions**
2. **Each treatment modality is validated against WHO 2021 expected protocols**
3. **Gaps are identified in the context of expected vs actual care**
4. **Protocol deviations are flagged for clinical review**

---

## The 7-Stage Timeline Construction

### STAGE 0: Molecular Diagnosis Anchor

**Purpose**: Establish the WHO 2021 integrated diagnosis as the foundational context for all subsequent clinical events

**Data Source**: `WHO_2021_CLASSIFICATIONS` dictionary (from prior molecular abstraction work)

**Event Type**: `molecular_diagnosis`

**Key Fields**:
- `who_2021_diagnosis`: e.g., "Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4"
- `molecular_subtype`: e.g., "H3 K27M+"
- `grade`: WHO grade (1-4)
- `expected_protocols`: Dictionary containing recommended:
  - Radiation (dose, fields)
  - Chemotherapy (regimen)
  - Surveillance (imaging frequency)

**Example**:
```json
{
  "event_type": "molecular_diagnosis",
  "stage": 0,
  "who_2021_diagnosis": "Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4",
  "molecular_subtype": "H3 K27M+",
  "grade": 4,
  "expected_protocols": {
    "radiation": "54 Gy focal radiation",
    "chemotherapy": "Concurrent temozolomide",
    "surveillance": "MRI every 2-3 months"
  }
}
```

**Clinical Significance**: This stage establishes the **expected treatment paradigm** that all subsequent stages validate against.

---

### STAGE 1: Encounters/Appointments

**Purpose**: Establish the patient's care coordination and appointment adherence

**Data Source**: `v_visits_unified`

**Event Type**: `visit`

**Key Validations**:
- ✅ Are visits occurring at expected intervals for tumor type?
- ⚠️ Are there prolonged gaps in care (>6 months) without documented reason?
- ✅ Do visit types align with treatment stage (surgical consult → chemo visits → surveillance)?

**Example Output**:
```
Stage 1: Encounters/appointments
  ✅ Added 47 encounters/appointments
```

**Clinical Context**:
- High-risk tumors (H3 K27-altered DMG, Pineoblastoma): Expect frequent visits during active treatment
- Low-risk tumors (BRAF V600E LGG): May have less frequent monitoring

---

### STAGE 2: Procedures (Surgeries)

**Purpose**: Identify surgical interventions and validate against tumor biology

**Data Source**: `v_procedures_tumor`

**Event Type**: `surgery`

**Key Validations**:
- ✅ Did the patient undergo initial tumor resection?
- ⚠️ Is there a documented extent of resection (EOR)?
- ✅ For infiltrative tumors (DMG), is biopsy-only approach used? (Expected)
- ⚠️ For resectable tumors (LGG, PA), was GTR/STR attempted? (Expected)

**Example Output**:
```
Stage 2: Procedures (surgeries)
  ✅ Added 3 surgical procedures
  ⚠️ WARNING: No surgeries found for patient with Diffuse midline glioma
```

**Gap Identification**:
If surgeries are present but EOR is missing → **Flag for operative note extraction (Priority 1)**

**Clinical Context by Tumor Type**:

| Tumor Type | Expected Surgical Approach | EOR Importance |
|------------|---------------------------|----------------|
| H3 K27-altered DMG | Biopsy only (infiltrative) | Not applicable |
| BRAF V600E LGG | GTR/STR attempted | **CRITICAL** (GTR → better prognosis) |
| Pineoblastoma | Resection if safe | High |
| Ependymoma | GTR attempted | **CRITICAL** (GTR → curative) |

---

### STAGE 3: Chemotherapy Episodes

**Purpose**: Validate chemotherapy regimen against WHO 2021 molecular-specific recommendations

**Data Source**: `v_chemo_treatment_episodes`

**Event Types**: `chemotherapy_start`, `chemotherapy_end`

**Key Validations**:
- ✅ Does the regimen match WHO 2021 expected protocols for molecular subtype?
- ⚠️ If no chemotherapy, is it expected for this tumor type?
- ✅ For BRAF V600E tumors, was targeted therapy (dabrafenib + trametinib) used?
- ⚠️ For H3 K27-altered DMG, was concurrent chemo with radiation given?

**Example Output**:
```
Stage 3: Chemotherapy episodes
  ✅ Added 2 chemotherapy episodes
  📋 Expected per WHO 2021: Concurrent temozolomide
```

**Gap Identification**:
If chemotherapy is expected but missing → **Flag for treatment summary extraction** OR **Flag as protocol deviation**

**Clinical Context by Molecular Diagnosis**:

| Molecular Diagnosis | Expected Chemotherapy | Clinical Significance |
|---------------------|----------------------|----------------------|
| H3 K27-altered DMG | Concurrent temozolomide with radiation | Standard of care (poor prognosis regardless) |
| BRAF V600E LGG | Dabrafenib + trametinib (targeted therapy) | May DEFER radiation entirely |
| Pineoblastoma | High-dose platinum (cisplatin/cyclophosphamide/etoposide) | Aggressive embryonal tumor protocol |
| IDH-mutant astrocytoma | Temozolomide (adjuvant after radiation) | Standard for grade 3-4 |

**Protocol Deviation Example**:
```
Stage 3: Chemotherapy episodes
  ✅ Added 0 chemotherapy episodes
  📋 Expected per WHO 2021: High-dose platinum-based (cisplatin/cyclophosphamide/etoposide)
  ⚠️ WARNING: No chemotherapy episodes found, but WHO 2021 recommends aggressive chemo for Pineoblastoma
```

---

### STAGE 4: Radiation Episodes

**Purpose**: Validate radiation dose, fields, and timing against WHO 2021 molecular-specific paradigms

**Data Source**: `v_radiation_episode_enrichment`

**Event Types**: `radiation_start`, `radiation_end`

**Key Validations**:
- ✅ Does the delivered dose match WHO 2021 expected dose for molecular subtype?
- ⚠️ Are radiation fields appropriate (focal vs craniospinal)?
- ✅ Was radiation delivered within expected timeframe post-surgery?

**Example Output**:
```
Stage 4: Radiation episodes
  ✅ Added 1 radiation episode
  📋 Expected per WHO 2021: 54 Gy craniospinal + posterior fossa boost
```

**Gap Identification**:
- If `total_dose_cgy` is NULL → **Flag for radiation treatment summary extraction (Priority 1)**
- If dose deviates significantly from expected → **Flag as protocol deviation for review**

**Clinical Context by Molecular Diagnosis**:

| Molecular Diagnosis | Expected Radiation Dose | Fields | Clinical Significance |
|---------------------|------------------------|--------|----------------------|
| H3 K27-altered DMG | **54 Gy** focal | Tumor bed + 1-2cm margin | Standard palliative dose (poor prognosis) |
| BRAF V600E LGG | 54 Gy focal OR deferred | Tumor bed | May defer if targeted therapy effective |
| Pineoblastoma | **54 Gy** craniospinal + boost | Craniospinal (23.4 Gy) + boost (54 Gy total) | Embryonal tumor requires CSI |
| Ependymoma | 54-59.4 Gy focal | Tumor bed | Post-op radiation critical |
| Medulloblastoma | 23.4-36 Gy CSI + 54 Gy boost | Craniospinal + boost | Risk-adapted (standard vs high-risk) |

**Protocol Deviation Example**:
```
Stage 4: Radiation episodes
  ✅ Added 1 radiation episode: 45.0 Gy
  📋 Expected per WHO 2021: 54 Gy focal radiation
  ⚠️ WARNING: Delivered dose (45 Gy) is LOWER than WHO 2021 recommended dose (54 Gy) for H3 K27-altered DMG
```

---

### STAGE 5: Imaging Studies

**Purpose**: Assess surveillance imaging adherence and identify progression/response patterns

**Data Source**: `v_imaging`

**Event Type**: `imaging`

**Key Validations**:
- ✅ Are surveillance MRIs being performed at expected intervals?
- ⚠️ For high-risk tumors, is imaging frequency adequate (every 2-3 months)?
- ✅ Are imaging studies capturing pseudoprogression window (21-90 days post-radiation)?

**Example Output**:
```
Stage 5: Imaging studies
  ✅ Added 23 imaging studies
```

**Gap Identification**:
- If `report_conclusion` is vague (e.g., "stable" without detail) → **Flag for full radiology report extraction**
- If imaging is within pseudoprogression window (21-90 days post-radiation) → **HIGH priority extraction** (progression vs pseudoprogression)

**Clinical Context by Tumor Type**:

| Tumor Type | Expected Surveillance Frequency | Critical Imaging Windows |
|------------|--------------------------------|-------------------------|
| H3 K27-altered DMG | Every 2-3 months | 21-90 days post-radiation (pseudoprogression) |
| BRAF V600E LGG | Every 3-6 months | 21-90 days post-radiation (if radiation given) |
| Pineoblastoma | Every 3 months (brain + spine) | Post-chemo, post-radiation |
| Ependymoma | Every 3 months | Post-op, post-radiation |

**Pseudoprogression Window**:
- **21-90 days post-radiation**: Treatment-related inflammation can mimic tumor progression
- **Clinical significance**: Requires careful imaging interpretation to avoid premature treatment escalation

---

### STAGE 6: Pathology Events (Granular)

**Purpose**: Link molecular findings to specific pathology reports and identify high-priority documents for extraction

**Data Source**: `v_pathology_diagnostics`

**Event Type**: `pathology_record`

**Key Fields**:
- `component_name`: Specific molecular marker (e.g., "H3F3A K27M", "BRAF V600E")
- `result_value`: Result (e.g., "POSITIVE", "DETECTED")
- `extraction_priority`: 1-5 tier (1=highest priority for NLP extraction)
- `document_category`: Type of pathology document

**Example Output**:
```
Stage 6: Pathology events (granular)
  ✅ Added 87 pathology records
```

**Gap Identification**:
- If `extraction_priority = 1 or 2` → **High-value documents for MedGemma extraction**
- If molecular diagnosis is "Pending - insufficient data" → **Flag Priority 1 final surgical pathology reports for extraction**

**Extraction Priority Tiers** (from DATETIME_STANDARDIZED_VIEWS.sql):

| Priority | Document Type | Clinical Value | Extraction Target |
|----------|--------------|----------------|------------------|
| **1** | Final surgical pathology reports | Definitive diagnosis + molecular markers | **HIGHEST** |
| **2** | Surgical pathology (preliminary) | Gross observations, preliminary findings | **HIGH** |
| **3** | Biopsy and specimen reports | Diagnostic confirmation | MEDIUM |
| **4** | Consultation notes | Second opinions | LOW |
| **5** | Other diagnostic reports | Variable | Extract only if critical gaps |

---

## Timeline Output Summary

After all 7 stages, the script outputs:

```
✅ Timeline construction complete: 163 total events across 7 stages
   Stage 0: 1 molecular diagnosis anchor
   Stage 1: 47 visits
   Stage 2: 3 surgeries
   Stage 3: 2 chemotherapy episodes
   Stage 4: 1 radiation episode
   Stage 5: 23 imaging studies
   Stage 6: 87 pathology records
```

---

## Protocol Validation Logic

At each stage (3-5), the script compares:

**EXPECTED** (from WHO 2021 classification)
vs
**ACTUAL** (from structured Athena views)

### Validation Matrix

| Treatment Modality | Expected Source | Actual Source | Validation Type |
|-------------------|----------------|---------------|----------------|
| **Surgery** | WHO 2021 paradigm | v_procedures_tumor | Approach (resection vs biopsy) |
| **Chemotherapy** | `recommended_protocols.chemotherapy` | v_chemo_treatment_episodes | Regimen match |
| **Radiation** | `recommended_protocols.radiation` | v_radiation_episode_enrichment | Dose + fields match |
| **Surveillance** | `recommended_protocols.surveillance` | v_imaging | Frequency adherence |

### Deviation Flagging

Deviations are flagged with:
- **⚠️ WARNING**: Treatment missing or deviates from expected
- **Clinical significance**: Explanation of why deviation matters
- **Recommended action**: Extract treatment summary OR flag for clinical review

**Example Deviation**:
```
⚠️ WARNING: Delivered radiation dose (45 Gy) is LOWER than WHO 2021 recommended (54 Gy)
Clinical significance: Suboptimal dose may reduce local control for high-grade glioma
Recommended action: Extract radiation treatment summary to understand dose rationale
```

---

## Integration with Gap Identification (Phase 3)

After timeline construction, **Phase 3** identifies extraction gaps using:

1. **Missing structured data** (e.g., EOR, radiation dose)
2. **extraction_priority field** (Priority 1-2 documents available?)
3. **WHO 2021 molecular context** (Does gap matter for this tumor type?)

**Example Gap**:
```json
{
  "gap_type": "missing_radiation_dose",
  "priority": "HIGHEST",
  "clinical_significance": "Cannot validate protocol adherence without dose",
  "extraction_priority": 1,
  "document_category": "Treatment Summary",
  "recommended_action": "Extract Priority 1 Rad Onc Treatment Report"
}
```

---

## Advantages of Stepwise Staging

### 1. **Context-Aware Validation**
Each treatment stage is validated against the molecular diagnosis established in Stage 0.

### 2. **Early Gap Detection**
Gaps are identified as each stage is processed, allowing prioritization before binary extraction.

### 3. **Clinical Coherence**
The timeline reflects the natural clinical progression:
- Diagnosis → Surgery → Adjuvant therapy (chemo/radiation) → Surveillance

### 4. **Protocol Adherence Tracking**
Deviations from expected paradigms are flagged immediately, enabling clinical review.

### 5. **Scalability**
This approach works for ANY molecular diagnosis in the WHO 2021 classification system, not just the initial 9 patients.

---

## Example: H3 K27-Altered DMG Patient Timeline

**Stage 0: Molecular Diagnosis**
```
✅ WHO 2021: Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4
   Expected protocols:
   - Radiation: 54 Gy focal
   - Chemotherapy: Concurrent temozolomide
   - Surveillance: MRI every 2-3 months
```

**Stage 1: Encounters**
```
✅ Added 52 visits
```

**Stage 2: Procedures**
```
✅ Added 1 surgery: Biopsy (brain stem)
   (No EOR expected for infiltrative DMG)
```

**Stage 3: Chemotherapy**
```
✅ Added 1 chemotherapy episode: Temozolomide
📋 Expected: Concurrent temozolomide ✅ MATCH
```

**Stage 4: Radiation**
```
✅ Added 1 radiation episode: 54.0 Gy
📋 Expected: 54 Gy focal ✅ MATCH
```

**Stage 5: Imaging**
```
✅ Added 18 imaging studies
⚠️ Gap identified: MRI at Day 45 post-radiation has vague conclusion ("stable disease")
   → Flag for full radiology report extraction (pseudoprogression window)
```

**Stage 6: Pathology**
```
✅ Added 12 pathology records
   H3F3A K27M: POSITIVE (Priority 1 final path report)
```

**Timeline Summary**:
- Treatment adheres to WHO 2021 protocol ✅
- One extraction gap: Day 45 imaging report (Priority HIGH due to pseudoprogression window)

---

## Next Steps After Timeline Construction

1. **Phase 3**: Identify extraction gaps using `extraction_priority` + molecular context
2. **Phase 4**: Extract Priority 1-2 documents using MedGemma (PLACEHOLDER - not yet implemented)
3. **Phase 5**: Perform detailed protocol validation (dose calculations, field verification)
4. **Phase 6**: Generate final JSON artifact with complete timeline + gap assessment

---

## References

- **WHO 2021 Classification**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf`
- **WHO 2021 Classifications (9 patients)**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md`
- **Extraction prioritization logic**: `DATETIME_STANDARDIZED_VIEWS.sql` (lines 4978-5009, 7338-7382)
- **Implementation**: `run_patient_timeline_abstraction_CORRECTED.py` (`_phase2_construct_initial_timeline()`)

---

**Document Version**: 1.0
**Created**: 2025-10-30
**Purpose**: Guide understanding of the stepwise timeline construction approach and its clinical validation logic
