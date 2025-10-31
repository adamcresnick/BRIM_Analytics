# WHO 2021 Clinical Contextualization Framework
## Molecular-Informed Timeline Interpretation for Pediatric CNS Tumors

**Purpose**: This document establishes the WHO 2021 CNS Tumor Classification (5th edition) as the foundational framework for interpreting patient clinical journey timelines, ensuring that data curation, treatment response assessment, and protocol adherence monitoring are clinically grounded.

**Date**: 2025-10-30
**Primary Reference**: [Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf)

---

## Executive Summary

The WHO 2021 classification revolutionized pediatric CNS tumor diagnosis by **integrating molecular markers with histology** to define biologically distinct tumor types. Our patient clinical journey timeline views operationalize this framework by:

1. **Capturing molecular markers** from v_pathology_diagnostics (`component_name`, `result_value`)
2. **Validating treatment protocols** against WHO 2021-informed standard-of-care
3. **Contextualizing treatment response** based on tumor biology (e.g., H3 K27-altered DMG has poor prognosis regardless of treatment)
4. **Prioritizing NLP extraction** for molecular testing documents (Priority 1 pathology reports)

**Key Principle**: Timeline data without molecular context is incomplete. A patient with "high-grade glioma" receiving radiation requires different interpretation if H3 K27-altered (uniformly fatal, ~9-11 months OS) vs IDH-mutant (favorable, years of survival possible).

---

## Part 1: WHO 2021 Molecular Marker Framework

### Core Molecular Markers in v_pathology_diagnostics

From the WHO 2021 PDF (pages 8-38) and our timeline implementation:

| Marker | Tumor Type(s) | Clinical Significance | Timeline Query Field | Expected Values |
|--------|---------------|----------------------|---------------------|-----------------|
| **H3-3A K27M/K27-altered** | DMG (Diffuse Midline Glioma), HGG | Defines entity; uniformly poor prognosis; OS 9-11 months | `component_name LIKE '%H3-3A%' OR '%H3F3A%' OR '%HIST1H3B%'` | "K27M mutation detected", "K27-altered" |
| **H3-3A G34R/V** | HGG (hemispheric, adolescent/YA) | Distinct biology from K27; slightly better prognosis than K27 | `component_name LIKE '%H3-3A%' AND result_value LIKE '%G34%'` | "G34R mutation", "G34V mutation" |
| **IDH1/IDH2 mutation** | HGG (rare in pediatric, common AYA), Astrocytoma | Favorable prognosis; longer OS; avoid radiation in young | `component_name IN ('IDH1', 'IDH2')` | "R132H mutation" (IDH1), "R172K mutation" (IDH2) |
| **BRAF V600E** | LGG (ganglioglioma, PXA), ATRT | Targetable; dabrafenib/trametinib approved | `component_name = 'BRAF' AND result_value LIKE '%V600E%'` | "V600E mutation detected" |
| **BRAF fusion/duplication** | LGG (pilocytic astrocytoma) | Most common PA alteration; MEK inhibitors | `component_name LIKE '%KIAA1549-BRAF%' OR '%BRAF fusion%'` | "KIAA1549-BRAF fusion detected" |
| **1p/19q codeletion** | Oligodendroglioma | Chemo/RT sensitive; favorable prognosis | `component_name LIKE '%1p%' OR '%19q%'` | "1p deletion", "19q deletion", "1p/19q codeleted" |
| **MYCN amplification** | Medulloblastoma Group 3 | High-risk feature; poor prognosis; metastatic | `component_name = 'MYCN'` | "Amplification detected", "Gain", "Copy number >4" |
| **TP53 mutation** | Multiple (Li-Fraumeni), HGG, MB SHH | Predisposition syndrome; AVOID radiation due to secondary malignancy risk | `component_name = 'TP53'` | "Pathogenic mutation", "R248Q", "R175H" |
| **PTCH1 mutation** | Medulloblastoma SHH | Gorlin syndrome; consider secondary tumors with radiation | `component_name = 'PTCH1'` | "Pathogenic mutation detected" |
| **SMARCB1 (INI1) loss** | ATRT (Atypical Teratoid/Rhabdoid Tumor) | Defines entity; very poor prognosis; intensive multimodal | `component_name LIKE '%SMARCB1%' OR '%INI1%'` | "Loss of expression", "Deletion" |
| **C19MC amplification** | Ependymoma (C19MC-altered, infants) | Poor prognosis; supratentorial; young age | `component_name LIKE '%C19MC%'` | "Amplification detected" |
| **RELA fusion** | Ependymoma (ST-RELA, supratentorial) | Poor prognosis; radiation-resistant; consider salvage surgery | `component_name LIKE '%C11orf95-RELA%' OR '%RELA fusion%'` | "RELA fusion detected" |

### How Timeline Captures Molecular Data

**Query Example**:
```sql
-- Extract molecular markers from patient timeline
SELECT
    event_date,
    diagnostic_source,
    component_name as molecular_marker,
    result_value as molecular_result,
    extraction_priority,
    days_from_surgery
FROM fhir_prd_db.v_patient_clinical_journey_timeline
WHERE patient_fhir_id = '{patient_id}'
  AND event_type = 'diagnosis'
  AND component_name IN (
      'H3-3A', 'H3F3A', 'HIST1H3B', 'HIST1H3C',  -- H3 alterations
      'IDH1', 'IDH2',                              -- IDH mutations
      'BRAF',                                      -- BRAF alterations
      'MYCN', 'TP53', 'PTCH1',                    -- Amplifications/mutations
      'SMARCB1', 'INI1',                          -- ATRT markers
      'C19MC', 'RELA'                             -- Ependymoma markers
  )
ORDER BY event_date, extraction_priority;
```

---

## Part 2: Treatment Paradigms by WHO 2021 Classification

### 2.1 Low-Grade Gliomas (WHO Grade 1-2)

**Molecular Subgroups**:
- BRAF V600E mutant (ganglioglioma, PXA)
- BRAF fusion/duplication (pilocytic astrocytoma)
- NF1-associated (optic pathway gliomas)
- FGFR1-altered (dysembryoplastic neuroepithelial tumor)

#### Expected Timeline Pattern (WHO 2021 Standard-of-Care):

```
[Surgery: GTR] → [Watch-and-Wait] → [Surveillance Imaging q3-6 months]
      ↓ (if incomplete resection or progressive)
[Chemotherapy: Carboplatin/Vincristine 18 months]
      ↓ (if progressive after chemo)
[Targeted Therapy: Dabrafenib/Trametinib (if BRAF V600E)]
      ↓ (if refractory)
[Radiation: 54 Gy focal (last resort, avoid in young children)]
```

#### Timeline View Interpretation:

```sql
-- Validate LGG treatment protocol adherence
WITH lgg_patients AS (
    SELECT DISTINCT patient_fhir_id, patient_diagnosis, molecular_marker
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE LOWER(patient_diagnosis) LIKE '%low-grade glioma%'
       OR LOWER(patient_diagnosis) LIKE '%pilocytic astrocytoma%'
       OR LOWER(patient_diagnosis) LIKE '%ganglioglioma%'
)
SELECT
    lp.patient_fhir_id,
    lp.molecular_marker,
    -- Surgery extent
    MAX(CASE WHEN t.event_type = 'surgery' THEN t.resection_extent_from_text END) as resection_extent,
    -- Time to adjuvant therapy (should be delayed if GTR)
    MIN(CASE WHEN t.event_type = 'chemo_episode_start' THEN t.days_from_initial_surgery END) as days_to_chemo,
    MIN(CASE WHEN t.event_type = 'radiation_episode_start' THEN t.days_from_initial_surgery END) as days_to_radiation,
    -- Targeted therapy (if BRAF V600E)
    COUNT(CASE WHEN t.event_type = 'chemo_episode_start'
               AND LOWER(t.event_description) LIKE '%dabrafenib%' THEN 1 END) as targeted_therapy_courses,
    -- Flag protocol deviations
    CASE
        WHEN MAX(CASE WHEN t.event_type = 'surgery' THEN t.resection_extent_from_text END) = 'GTR'
             AND MIN(CASE WHEN t.event_type = 'chemo_episode_start' THEN t.days_from_initial_surgery END) < 90
            THEN 'DEVIATION: Early chemo after GTR (typically observe)'
        WHEN lp.molecular_marker LIKE '%BRAF V600E%'
             AND COUNT(CASE WHEN LOWER(t.event_description) LIKE '%dabrafenib%' THEN 1 END) = 0
             AND MIN(CASE WHEN t.event_type = 'chemo_episode_start' THEN t.days_from_initial_surgery END) > 365
            THEN 'CONSIDERATION: BRAF V600E without targeted therapy trial'
        WHEN MIN(CASE WHEN t.event_type = 'radiation_episode_start' THEN t.days_from_initial_surgery END) < 180
            THEN 'DEVIATION: Early radiation (typically last resort for LGG)'
        ELSE 'Standard protocol'
    END as protocol_adherence_flag
FROM lgg_patients lp
JOIN fhir_prd_db.v_patient_clinical_journey_timeline t ON lp.patient_fhir_id = t.patient_fhir_id
GROUP BY lp.patient_fhir_id, lp.molecular_marker;
```

---

### 2.2 High-Grade Gliomas (WHO Grade 3-4)

**Molecular Subgroups**:
- H3 K27-altered (DMG) - **uniformly fatal, median OS 9-11 months**
- H3 G34-mutant - adolescent/YA, hemispheric
- IDH-wildtype - pediatric glioblastoma
- IDH-mutant - rare in pediatric, better prognosis

#### Expected Timeline Pattern (WHO 2021 Standard-of-Care):

```
[Surgery: Maximal safe resection] → [Baseline MRI within 48-72h]
      ↓ (28-35 days post-op)
[Radiation: 54-60 Gy in 1.8-2 Gy fractions, 6 weeks]
      ↓ (concurrent + adjuvant)
[Chemotherapy: Temozolomide OR clinical trial agent]
      ↓ (q3 months)
[Surveillance MRI: Year 1-2, then q6 months]
```

#### Timeline View Interpretation:

```sql
-- Validate HGG treatment protocol and detect deviations
WITH hgg_patients AS (
    SELECT DISTINCT patient_fhir_id, patient_diagnosis, molecular_marker
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE LOWER(patient_diagnosis) LIKE '%high-grade glioma%'
       OR LOWER(patient_diagnosis) LIKE '%glioblastoma%'
       OR LOWER(patient_diagnosis) LIKE '%diffuse midline glioma%'
       OR molecular_marker LIKE '%H3 K27%'
),
treatment_timeline AS (
    SELECT
        hp.patient_fhir_id,
        hp.molecular_marker,
        -- Surgery date
        MIN(CASE WHEN t.event_type = 'surgery' THEN t.event_date END) as surgery_date,
        -- Baseline imaging (within 48-72h = 2-3 days)
        MIN(CASE WHEN t.event_type = 'imaging'
                 AND t.days_from_initial_surgery BETWEEN 0 AND 3
             THEN t.event_date END) as baseline_imaging_date,
        -- Radiation start (should be 28-35 days post-op)
        MIN(CASE WHEN t.event_type = 'radiation_episode_start' THEN t.days_from_initial_surgery END) as days_to_radiation,
        -- Radiation dose (should be 5400-6000 cGy)
        MAX(CASE WHEN t.event_type = 'radiation_episode_end'
             THEN CAST(REGEXP_EXTRACT(t.event_description, '(\d+) cGy', 1) AS INT) END) as radiation_dose_cgy,
        -- Chemotherapy (concurrent with radiation)
        MIN(CASE WHEN t.event_type = 'chemo_episode_start' THEN t.days_from_initial_surgery END) as days_to_chemo,
        -- Progression detection
        MIN(CASE WHEN t.progression_flag IS NOT NULL THEN t.days_from_initial_surgery END) as days_to_progression
    FROM hgg_patients hp
    JOIN fhir_prd_db.v_patient_clinical_journey_timeline t ON hp.patient_fhir_id = t.patient_fhir_id
    GROUP BY hp.patient_fhir_id, hp.molecular_marker
)
SELECT
    *,
    -- Protocol adherence flags
    CASE
        WHEN baseline_imaging_date IS NULL
            THEN 'MISSING: No baseline post-op MRI within 72h'
        WHEN days_to_radiation < 21
            THEN 'DEVIATION: Radiation started <3 weeks post-op (insufficient healing)'
        WHEN days_to_radiation > 42
            THEN 'DEVIATION: Radiation delayed >6 weeks post-op (tumor regrowth risk)'
        WHEN radiation_dose_cgy NOT BETWEEN 5400 AND 6000
            THEN 'DEVIATION: Non-standard radiation dose (should be 54-60 Gy)'
        WHEN days_to_chemo > days_to_radiation + 7
            THEN 'DEVIATION: Chemo not concurrent with radiation'
        ELSE 'Standard protocol'
    END as protocol_adherence,
    -- Molecular-informed prognosis context
    CASE
        WHEN molecular_marker LIKE '%H3 K27%' AND days_to_progression < 270
            THEN 'EXPECTED: H3 K27-altered DMG typically progresses within 9 months'
        WHEN molecular_marker LIKE '%IDH%' AND days_to_progression > 730
            THEN 'FAVORABLE: IDH-mutant with >2 year PFS'
        ELSE NULL
    END as molecular_context
FROM treatment_timeline;
```

---

### 2.3 Medulloblastoma (Embryonal Tumors)

**Molecular Subgroups (WHO 2021)**:
- **WNT-activated**: Best prognosis (>95% OS), consider radiation de-escalation
- **SHH-activated**: Variable (TP53-wildtype better than TP53-mutant)
- **Group 3**: Worst prognosis, MYCN amplification = very poor
- **Group 4**: Intermediate prognosis, most common subtype

#### Expected Timeline Pattern (WHO 2021 Standard-of-Care):

```
[Surgery: Maximal resection] → [Baseline MRI + spine within 48h]
      ↓ (28-35 days post-op)
[Radiation: CSI + boost]
   - Standard-risk: 23.4 Gy CSI + 54 Gy boost
   - High-risk: 36 Gy CSI + 54 Gy boost
   - WNT: Consider 18 Gy CSI (de-escalation)
      ↓ (concurrent + adjuvant)
[Chemotherapy: Multi-agent (vincristine, cisplatin, cyclophosphamide, etc.)]
      ↓ (q3-4 months Year 1-2)
[Surveillance: MRI brain + spine]
```

#### Timeline View Interpretation:

```sql
-- Medulloblastoma protocol validation with molecular risk stratification
WITH mb_patients AS (
    SELECT DISTINCT
        patient_fhir_id,
        patient_diagnosis,
        molecular_marker,
        CASE
            WHEN molecular_marker LIKE '%WNT%' THEN 'WNT-activated (best prognosis)'
            WHEN molecular_marker LIKE '%SHH%' AND molecular_marker NOT LIKE '%TP53%'
                THEN 'SHH-activated, TP53-wildtype (intermediate)'
            WHEN molecular_marker LIKE '%SHH%' AND molecular_marker LIKE '%TP53%'
                THEN 'SHH-activated, TP53-mutant (poor)'
            WHEN molecular_marker LIKE '%MYCN%'
                THEN 'Group 3, MYCN-amplified (very poor)'
            WHEN molecular_marker LIKE '%Group 3%'
                THEN 'Group 3 (poor)'
            WHEN molecular_marker LIKE '%Group 4%'
                THEN 'Group 4 (intermediate)'
            ELSE 'Molecular subgroup unspecified'
        END as molecular_risk_group
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE LOWER(patient_diagnosis) LIKE '%medulloblastoma%'
)
SELECT
    mb.patient_fhir_id,
    mb.molecular_risk_group,
    -- Radiation dose (validate CSI protocol)
    MAX(CASE WHEN t.event_type = 'radiation_episode_end'
         THEN CAST(REGEXP_EXTRACT(t.event_description, '(\d+) cGy', 1) AS INT) END) as total_dose_cgy,
    -- Expected dose range based on molecular subgroup
    CASE
        WHEN mb.molecular_risk_group = 'WNT-activated (best prognosis)'
            THEN '1800-2340 cGy CSI (de-escalation trial) or 2340 cGy (standard)'
        WHEN mb.molecular_risk_group LIKE '%very poor%'
            THEN '3600 cGy CSI + 5400 cGy boost (high-risk protocol)'
        ELSE '2340 cGy CSI + 5400 cGy boost (standard-risk protocol)'
    END as expected_dose_range,
    -- Protocol adherence
    CASE
        WHEN mb.molecular_risk_group = 'WNT-activated (best prognosis)'
             AND MAX(CASE WHEN t.event_type = 'radiation_episode_end'
                      THEN CAST(REGEXP_EXTRACT(t.event_description, '(\d+) cGy', 1) AS INT) END) BETWEEN 1800 AND 2340
            THEN 'APPROPRIATE: WNT patient on de-escalation protocol'
        WHEN mb.molecular_risk_group LIKE '%very poor%'
             AND MAX(CASE WHEN t.event_type = 'radiation_episode_end'
                      THEN CAST(REGEXP_EXTRACT(t.event_description, '(\d+) cGy', 1) AS INT) END) BETWEEN 3600 AND 5400
            THEN 'APPROPRIATE: High-risk patient on intensified protocol'
        WHEN MAX(CASE WHEN t.event_type = 'radiation_episode_end'
                  THEN CAST(REGEXP_EXTRACT(t.event_description, '(\d+) cGy', 1) AS INT) END) NOT BETWEEN 1800 AND 5400
            THEN 'DEVIATION: Radiation dose outside expected range'
        ELSE 'Standard protocol'
    END as protocol_assessment
FROM mb_patients mb
JOIN fhir_prd_db.v_patient_clinical_journey_timeline t ON mb.patient_fhir_id = t.patient_fhir_id
GROUP BY mb.patient_fhir_id, mb.molecular_risk_group;
```

---

## Part 3: Treatment Response Interpretation by Molecular Context

### Response Assessment MUST Consider Molecular Biology

**Key Principle**: Imaging findings have different clinical significance depending on molecular subtype.

| Molecular Context | Imaging Finding | Clinical Interpretation | Action |
|-------------------|-----------------|------------------------|--------|
| **H3 K27-altered DMG** | Decreased enhancement 2 months post-RT | Likely pseudoprogression (transient inflammation), NOT true response | Continue current therapy, repeat MRI in 4-6 weeks |
| **H3 K27-altered DMG** | Increased enhancement 6 months post-RT | True progression (expected, uniformly fatal) | Consider palliative care, hospice referral |
| **BRAF V600E LGG** | Stable disease on carb/vincristine | Standard response for LGG | Continue current therapy |
| **BRAF V600E LGG** | Progressive disease on carb/vincristine | Consider targeted therapy (dabrafenib/trametinib) | Escalate to BRAF inhibitor |
| **IDH-mutant HGG** | Stable disease 2 years post-RT | Favorable, expected for IDH-mutant | Continue surveillance |
| **IDH-wildtype HGG** | Progressive disease 6 months post-RT | Expected, poor prognosis | Consider salvage chemotherapy or trial |

### Timeline Query: Molecular-Contextualized Response Assessment

```sql
-- Interpret imaging findings based on molecular context
WITH patient_molecular_context AS (
    SELECT DISTINCT
        patient_fhir_id,
        patient_diagnosis,
        molecular_marker,
        CASE
            WHEN molecular_marker LIKE '%H3 K27%' THEN 'H3_K27_altered'
            WHEN molecular_marker LIKE '%BRAF V600E%' THEN 'BRAF_V600E'
            WHEN molecular_marker LIKE '%IDH%' THEN 'IDH_mutant'
            ELSE 'molecular_unknown'
        END as molecular_subtype
    FROM fhir_prd_db.v_patient_clinical_journey_timeline
    WHERE event_type = 'diagnosis'
)
SELECT
    pmc.patient_fhir_id,
    pmc.molecular_subtype,
    t.event_date,
    t.days_from_initial_surgery,
    t.imaging_phase,
    t.progression_flag,
    t.response_flag,
    t.free_text_content,
    -- Molecular-informed interpretation
    CASE
        -- H3 K27-altered DMG
        WHEN pmc.molecular_subtype = 'H3_K27_altered'
             AND t.days_from_initial_surgery BETWEEN 60 AND 120
             AND t.response_flag = 'response_suspected'
            THEN 'CAUTION: Likely pseudoprogression, not true response (H3 K27-altered DMG)'
        WHEN pmc.molecular_subtype = 'H3_K27_altered'
             AND t.days_from_initial_surgery > 180
             AND t.progression_flag = 'progression_suspected'
            THEN 'EXPECTED: True progression (H3 K27-altered DMG has uniformly poor prognosis)'

        -- BRAF V600E LGG
        WHEN pmc.molecular_subtype = 'BRAF_V600E'
             AND t.progression_flag = 'progression_suspected'
             AND NOT EXISTS (
                 SELECT 1 FROM fhir_prd_db.v_patient_clinical_journey_timeline t2
                 WHERE t2.patient_fhir_id = pmc.patient_fhir_id
                   AND t2.event_type = 'chemo_episode_start'
                   AND LOWER(t2.event_description) LIKE '%dabrafenib%'
             )
            THEN 'ACTIONABLE: Consider targeted therapy (dabrafenib/trametinib) for BRAF V600E'

        -- IDH-mutant HGG
        WHEN pmc.molecular_subtype = 'IDH_mutant'
             AND t.days_from_initial_surgery > 730
             AND t.response_flag IN ('stable_disease', 'response_suspected')
            THEN 'FAVORABLE: Extended PFS >2 years consistent with IDH-mutant biology'

        ELSE 'Standard interpretation'
    END as molecular_contextualized_interpretation
FROM patient_molecular_context pmc
JOIN fhir_prd_db.v_patient_clinical_journey_timeline t
    ON pmc.patient_fhir_id = t.patient_fhir_id
WHERE t.event_type = 'imaging'
  AND (t.progression_flag IS NOT NULL OR t.response_flag IS NOT NULL)
ORDER BY pmc.patient_fhir_id, t.event_date;
```

---

## Part 4: NLP Extraction Prioritization Based on WHO 2021 Context

### Molecular Testing Documents = Highest Priority

**Rationale**: Molecular markers DEFINE the diagnosis and treatment plan per WHO 2021. Without molecular data, timeline interpretation is incomplete.

#### Priority Framework (integrates with existing extraction_priority):

| Document Type | extraction_priority | WHO 2021 Importance | Timeline Use Case |
|---------------|---------------------|---------------------|-------------------|
| **Final surgical pathology WITH molecular testing** | 1 | CRITICAL | Diagnosis + molecular markers define treatment paradigm |
| **Send-out molecular/genomic testing** | 1 | CRITICAL | May include NGS panel with BRAF, IDH, H3, MYCN, etc. |
| **Surgical pathology gross observations** | 2 | HIGH | Establishes diagnosis before molecular confirmation |
| **Biopsy reports WITH molecular results** | 1 | CRITICAL | Diagnosis for unresectable tumors |
| **Biopsy reports WITHOUT molecular results** | 3 | MEDIUM | Incomplete diagnosis |
| **Imaging reports suggesting progression** | N/A (not in v_pathology_diagnostics) | HIGH | Treatment response assessment |
| **Operative notes with EOR description** | N/A | MEDIUM | Surgical quality metric |

#### Timeline-Focused Extraction Query:

```sql
-- Prioritize molecular testing documents for NLP extraction
SELECT
    patient_fhir_id,
    diagnostic_source,
    diagnostic_date,
    diagnostic_name,
    component_name,
    extraction_priority,
    document_category,
    days_from_surgery,
    -- Flag molecular testing documents
    CASE
        WHEN LOWER(diagnostic_name) LIKE '%molecular%'
             OR LOWER(diagnostic_name) LIKE '%genomic%'
             OR LOWER(diagnostic_name) LIKE '%NGS%'
             OR LOWER(diagnostic_name) LIKE '%next generation%'
             OR LOWER(component_name) IN ('BRAF', 'IDH1', 'IDH2', 'H3-3A', 'MYCN', 'TP53', 'SMARCB1')
            THEN 'MOLECULAR_TESTING_DOCUMENT'
        ELSE 'STANDARD_PATHOLOGY'
    END as document_molecular_flag,
    -- NLP extraction urgency
    CASE
        WHEN extraction_priority = 1
             AND (LOWER(diagnostic_name) LIKE '%molecular%' OR LOWER(component_name) IN ('BRAF', 'IDH1', 'H3-3A'))
            THEN 'URGENT: Priority 1 molecular document'
        WHEN extraction_priority = 1
            THEN 'HIGH: Priority 1 pathology document'
        WHEN extraction_priority = 2
            THEN 'MEDIUM: Priority 2 pathology document'
        ELSE 'LOW: Priority 3+ or structured data'
    END as nlp_extraction_urgency
FROM fhir_prd_db.v_pathology_diagnostics
WHERE patient_fhir_id IN (SELECT DISTINCT patient_fhir_id FROM fhir_prd_db.v_patient_clinical_journey_timeline)
  AND extraction_priority IS NOT NULL
ORDER BY nlp_extraction_urgency, extraction_priority, days_from_surgery;
```

---

## Part 5: Timeline-Focused Abstraction Script Integration

### How run_timeline_focused_abstraction.py Uses WHO 2021 Context

**Current Implementation** (from [run_timeline_focused_abstraction.py](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/scripts/run_timeline_focused_abstraction.py)):

```python
# STEP 2: Claude identifies extraction targets based on clinical significance
def identify_extraction_targets(self) -> List[Dict[str, Any]]:
    targets = []

    # RULE 1: Imaging with progression flag (WHO 2021: progression = treatment change)
    progression_events = [e for e in self.timeline_events
                         if e.get('progression_flag') and e['event_type'] == 'imaging']

    # RULE 2: Surgeries with unclear EOR (WHO 2021: GTR vs STR affects adjuvant therapy)
    unclear_eor = [e for e in self.timeline_events
                  if e['event_type'] == 'surgery'
                  and e.get('resection_extent_from_text') == 'unspecified_extent']
```

**Recommended Enhancement** (WHO 2021-informed):

```python
# ENHANCED RULE 1: Prioritize molecular testing documents
molecular_keywords = ['BRAF', 'IDH', 'H3-3A', 'MYCN', 'TP53', 'SMARCB1', 'molecular', 'genomic']
molecular_diagnosis_events = [e for e in self.timeline_events
                              if e['event_type'] == 'diagnosis'
                              and e.get('extraction_priority') == 1
                              and any(kw in str(e.get('diagnostic_name', '')).lower()
                                     or kw in str(e.get('component_name', '')).lower()
                                     for kw in molecular_keywords)]

for event in molecular_diagnosis_events:
    targets.append({
        'target_type': 'molecular_testing_document',
        'priority': 'URGENT',  # Highest priority
        'event_id': event['event_id'],
        'reason': 'Molecular markers define WHO 2021 diagnosis and treatment paradigm',
        'who_2021_context': 'Required for risk stratification and protocol selection'
    })

# ENHANCED RULE 2: Response assessment contextualized by molecular subtype
# If patient has H3 K27-altered, prioritize imaging 2-4 months post-RT (pseudoprogression window)
molecular_marker = self.get_patient_molecular_marker()  # From timeline diagnosis events
if 'H3 K27' in molecular_marker:
    early_post_rt_imaging = [e for e in self.timeline_events
                            if e['event_type'] == 'imaging'
                            and e.get('imaging_phase') == 'early_post_radiation'
                            and e.get('days_from_initial_surgery') BETWEEN 60 AND 120]
    for event in early_post_rt_imaging:
        targets.append({
            'target_type': 'h3_k27_pseudoprogression_assessment',
            'priority': 'HIGH',
            'reason': 'H3 K27-altered DMG: distinguish pseudoprogression from true progression',
            'who_2021_context': 'Pseudoprogression common 2-4 months post-RT in DMG'
        })
```

---

## Part 6: Summary & Clinical Impact

### WHO 2021 Framework Transforms Timeline Interpretation

**Without Molecular Context**:
> "Patient has high-grade glioma, received 54 Gy radiation and temozolomide, progressed at 8 months."

**With WHO 2021 Molecular Context**:
> "Patient has **H3 K27-altered diffuse midline glioma** (WHO 2021), received standard 54 Gy radiation and temozolomide, progressed at 8 months. **This is the expected clinical course** for H3 K27-altered DMG (median OS 9-11 months). Imaging findings at 2 months post-RT showing decreased enhancement were likely **pseudoprogression**, not true response. **No protocol deviations detected**. Consider palliative care consultation and hospice referral."

### Key Takeaways

1. **Molecular markers are not optional metadata** - they DEFINE the diagnosis per WHO 2021
2. **Treatment protocols vary by molecular subtype** - standard-of-care is different for WNT medulloblastoma vs Group 3
3. **Response assessment requires molecular context** - pseudoprogression in DMG vs true progression in IDH-wildtype HGG
4. **NLP extraction must prioritize molecular documents** - extraction_priority = 1 + molecular keywords = URGENT
5. **Timeline views operationalize WHO 2021** - by capturing molecular markers, validating protocols, and contextualizing response

---

## References

1. WHO Classification of Tumours of the Central Nervous System (2021, 5th edition)
2. [Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf) (38 pages)
3. RANO (Response Assessment in Neuro-Oncology) criteria for pediatric CNS tumors
4. COG (Children's Oncology Group) treatment protocols
5. [EXISTING_VIEW_SCHEMA_REVIEW.md](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/docs/EXISTING_VIEW_SCHEMA_REVIEW.md)
6. [PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md](file:///Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/docs/PATIENT_CLINICAL_JOURNEY_TIMELINE_DESIGN.md)
