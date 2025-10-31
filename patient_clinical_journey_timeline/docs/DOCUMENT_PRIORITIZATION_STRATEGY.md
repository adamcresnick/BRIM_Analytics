# Document Prioritization Strategy

**Source**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql` (lines 4978-5009)

This document describes the existing prioritization logic built into the Athena views, which should be leveraged by the timeline abstraction workflow.

---

## Radiation Oncology Documents Prioritization

### Priority Tiers (1-5, where 1 = highest)

**Priority 1: Treatment Summaries (HIGHEST VALUE)**
```sql
WHEN dr.type_text = 'Rad Onc Treatment Report' THEN 1
WHEN dr.type_text = 'ONC RadOnc End of Treatment' THEN 1
WHEN LOWER(dr.description) LIKE '%end of treatment%summary%' THEN 1
WHEN LOWER(dr.description) LIKE '%treatment summary%report%' THEN 1
```
**Document Category**: `Treatment Summary`
**Clinical Value**: Contains complete treatment course summary, total dose, fields, response assessment
**MedGemma Extraction Target**: HIGHEST priority for dose validation, field verification, response assessment

---

**Priority 2: Consultation Notes**
```sql
WHEN dr.type_text = 'ONC RadOnc Consult' THEN 2
WHEN LOWER(dr.description) LIKE '%consult%' AND LOWER(dr.description) LIKE '%rad%onc%' THEN 2
WHEN LOWER(dr.description) LIKE '%initial%consultation%' THEN 2
```
**Document Category**: `Consultation`
**Clinical Value**: Treatment plan, dose prescription, target volumes, rationale
**MedGemma Extraction Target**: HIGH priority for protocol validation, planned vs delivered dose comparison

---

**Priority 3: External/Outside Documents**
```sql
WHEN dr.type_text = 'ONC Outside Summaries' AND LOWER(dr.description) LIKE '%radiation%' THEN 3
WHEN dr.type_text = 'Clinical Report-Consult' AND LOWER(dr.description) LIKE '%radiation%' THEN 3
WHEN dr.type_text = 'External Misc Clinical' AND LOWER(dr.description) LIKE '%radiation%' THEN 3
```
**Document Category**: `Outside Summary`
**Clinical Value**: Treatment received elsewhere, may fill gaps in CHOP records
**MedGemma Extraction Target**: MEDIUM priority, useful for complete treatment history

---

**Priority 4: Progress Notes & Support Documents**
```sql
WHEN LOWER(dr.description) LIKE '%progress%note%' THEN 4
WHEN LOWER(dr.description) LIKE '%social work%' THEN 4
```
**Document Category**: `Progress Note` / `Social Work Note`
**Clinical Value**: Symptom management, toxicity assessment, not definitive for dose/protocol
**MedGemma Extraction Target**: LOW priority, extract only if critical gaps remain

---

**Priority 5: Other Documents (LOWEST PRIORITY)**
```sql
ELSE 5
```
**Document Category**: `Other`
**Clinical Value**: Variable, may include administrative documents
**MedGemma Extraction Target**: Extract only if no higher-priority documents available

---

## Pathology Documents Prioritization

**(From DATETIME_STANDARDIZED_VIEWS.sql lines 7338-7382)**

**Priority 1: Final Surgical Pathology Reports**
```sql
WHEN LOWER(dr.code_text) LIKE '%surgical%pathology%final%' THEN 1
WHEN LOWER(dr.code_text) LIKE '%pathology%final%diagnosis%' THEN 1
WHEN drcc.code_coding_code = '34574-4' THEN 1  -- LOINC: Pathology report final diagnosis
```
**Clinical Value**: Definitive diagnosis, grade, molecular markers
**MedGemma Extraction Target**: HIGHEST priority for WHO 2021 classification

**Priority 2: Surgical Pathology (Preliminary)**
```sql
WHEN LOWER(dr.code_text) LIKE '%surgical%pathology%' THEN 2
WHEN drcc.code_coding_code = '24419-4' THEN 2  -- LOINC: Surgical pathology gross
```
**Clinical Value**: Gross observations, preliminary findings
**MedGemma Extraction Target**: HIGH priority if final report not available

**Priority 3: Biopsy & Specimen Reports**
```sql
WHEN LOWER(dr.code_text) LIKE '%biopsy%' THEN 3
```
**Clinical Value**: Diagnostic confirmation, may lack molecular detail
**MedGemma Extraction Target**: MEDIUM priority

**Priority 4: Consultation Notes**
```sql
WHEN LOWER(dr.code_text) LIKE '%pathology%consult%' THEN 4
```
**Clinical Value**: Second opinions, additional interpretation
**MedGemma Extraction Target**: LOW priority

**Priority 5: Other Diagnostic Reports**
```sql
ELSE 5
```
**Clinical Value**: Variable
**MedGemma Extraction Target**: Extract only if critical gaps

---

## Timeline Abstraction Integration

### How to Use Prioritization in Iterative Workflow

**PHASE 3: Identify Extraction Gaps** (in run_patient_timeline_abstraction_CORRECTED.py)

```python
def _phase3_identify_extraction_gaps(self):
    """Identify gaps and PRIORITIZE using existing extraction_priority field"""

    gaps = []

    # Gap Type 1: Radiation dose missing
    radiation_events = [e for e in self.timeline_events
                       if e['event_type'] == 'radiation_start']
    for rad_event in radiation_events:
        if not rad_event.get('total_dose_cgy'):
            # Check if Priority 1-2 documents exist
            priority_1_2_docs = [e for e in self.timeline_events
                                if e.get('extraction_priority') in ['1', '2', 1, 2]
                                and 'radiation' in e.get('description', '').lower()]

            if priority_1_2_docs:
                gaps.append({
                    'gap_type': 'missing_radiation_dose',
                    'priority': 'HIGHEST',  # Priority 1-2 docs available
                    'documents_to_extract': priority_1_2_docs,
                    'clinical_significance': 'Treatment summary/consult contains dose'
                })
            else:
                gaps.append({
                    'gap_type': 'missing_radiation_dose',
                    'priority': 'HIGH',
                    'clinical_significance': 'No high-priority documents, may need manual review'
                })

    # Gap Type 2: Molecular markers missing
    molecular_events = [e for e in self.timeline_events
                       if e.get('extraction_priority') in ['1', '2', 1, 2]
                       and e['event_type'] == 'diagnosis']

    if not molecular_events and self.who_2021_classification.get('who_2021_diagnosis') == 'Pending - insufficient data':
        gaps.append({
            'gap_type': 'missing_molecular_classification',
            'priority': 'CRITICAL',
            'clinical_significance': 'WHO 2021 classification impossible without molecular data',
            'recommended_action': 'Extract Priority 1 final surgical pathology reports'
        })

    return gaps
```

---

## Extraction Priority Decision Matrix

| Gap Type | Priority 1-2 Docs Available? | Molecular Dx Severity | Extraction Priority | Action |
|----------|------------------------------|----------------------|---------------------|--------|
| Missing radiation dose | YES | Any | HIGHEST | Extract Priority 1-2 docs immediately |
| Missing radiation dose | NO | Any | HIGH | Flag for manual review |
| Missing EOR | YES (operative note) | High-risk tumor | HIGHEST | Extract operative note |
| Missing EOR | NO | Low-risk tumor | MEDIUM | Defer extraction |
| Missing molecular markers | YES (Priority 1 path) | Unknown | CRITICAL | Extract final surgical path report |
| Missing molecular markers | NO | Unknown | CRITICAL | Flag for molecular testing order |
| Vague imaging conclusion | YES (full radiology report) | H3 K27-altered DMG | HIGHEST | Extract for progression assessment |
| Vague imaging conclusion | YES | BRAF V600E LGG | MEDIUM | Extract if within pseudoprogression window |

---

## WHO 2021 Molecular Context Modifies Priority

**Example 1: H3 K27-altered DMG Patient**
- Baseline priority: Extract Priority 1-2 radiation docs
- **WITH molecular context**: Extract IMMEDIATELY + flag any dose <54 Gy as protocol deviation
- **Reason**: Uniformly fatal tumor, protocol adherence critical

**Example 2: BRAF V600E LGG Patient**
- Baseline priority: Extract Priority 1-2 radiation docs
- **WITH molecular context**: Extraction can be DEFERRED if targeted therapy administered
- **Reason**: Radiation often delayed/omitted in favor of dabrafenib + trametinib

**Example 3: Pineoblastoma Patient**
- Baseline priority: Extract Priority 1 radiation docs
- **WITH molecular context**: Extract IMMEDIATELY + verify craniospinal field + CSF staging
- **Reason**: Embryonal tumor requires craniospinal radiation + CSF surveillance

---

## Implementation in Corrected Script

The `run_patient_timeline_abstraction_CORRECTED.py` script now:

1. ✅ Loads `extraction_priority` from v_pathology_diagnostics
2. ✅ Uses priority tiers to identify which documents to extract
3. ✅ Combines document priority + WHO 2021 molecular context for final extraction decision
4. ⚠️ **MedGemma integration PLACEHOLDER** - needs to be implemented to actually fetch and extract binaries

---

## References

- **Radiation docs prioritization**: DATETIME_STANDARDIZED_VIEWS.sql lines 4978-5009
- **Pathology docs prioritization**: DATETIME_STANDARDIZED_VIEWS.sql lines 7338-7382
- **WHO 2021 molecular classifications**: WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md
- **Treatment paradigms**: WHO 2021 Classification & Treatment Guide PDF

---

**Document Version**: 1.0
**Created**: 2025-10-30
**Purpose**: Guide timeline abstraction prioritization decisions using existing schema logic
