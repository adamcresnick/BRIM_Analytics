# Prioritized Note Types for BRIM Analytics Variables
**Date**: October 4, 2025
**Source**: FHIR v1 DocumentReference type_text analysis (3,982 unique note types)
**Patient Cohort**: Pediatric brain tumor (low-grade glioma)
**Objective**: Identify top 50 note types most likely to contain BRIM variable information

---

## BRIM Analytics Variables (31 total)

### **Primary Categories**:
1. **Demographics** (5): gender, birth_date, race, ethnicity, vital_status
2. **Diagnosis** (7): primary_diagnosis, diagnosis_date, who_grade, tumor_location, metastasis, idh_mutation, braf_status
3. **Molecular** (3): mgmt_methylation, 1p19q_codeletion, other_molecular_markers
4. **Surgery** (4): surgery_date, surgery_type, surgery_extent, surgery_location
5. **Chemotherapy** (7): chemotherapy_agent, chemotherapy_start_date, chemotherapy_end_date, chemotherapy_status, chemotherapy_line, chemotherapy_protocol, chemotherapy_response
6. **Radiation** (3): radiation_therapy_yn, radiation_start_date, radiation_dose
7. **Imaging** (5): imaging_type, imaging_date, tumor_size, contrast_enhancement, imaging_findings
8. **Clinical Status** (3): clinical_status, progression_date, recurrence_date

---

## Top 50 Prioritized Note Types

### **TIER 1: CRITICAL - Surgical & Pathology Documentation** (Priority Score: 95-100)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 1 | **Pathology study** | 149,132 | primary_diagnosis, diagnosis_date, who_grade, tumor_location, idh_mutation, braf_status, mgmt_methylation, 1p19q_codeletion, other_molecular_markers | **PRIMARY SOURCE** for diagnosis, grading, molecular markers. Contains surgical pathology reports with histologic diagnosis, WHO grading, immunohistochemistry, molecular testing results. |
| 2 | **OP Note - Complete (Template or Full Dictation)** | 11,612 | surgery_date, surgery_type, surgery_extent, surgery_location, tumor_location, clinical_status | Complete operative notes with detailed surgical approach, extent of resection (gross total, subtotal, partial), anatomical location, intraoperative findings. |
| 3 | **OP Note - Brief (Needs Dictation)** | 9,684 | surgery_date, surgery_type, surgery_location | Brief operative summaries, may lack detailed extent of resection. |
| 4 | **Discharge Summary** | 13,449 | primary_diagnosis, surgery_type, surgery_date, chemotherapy_agent, chemotherapy_start_date, radiation_therapy_yn, radiation_start_date, clinical_status, who_grade, tumor_location | **COMPREHENSIVE CLINICAL SUMMARY** spanning diagnosis, treatment, and discharge planning. Often includes diagnosis confirmation, surgical summary, chemotherapy initiation, radiation plans. |

---

### **TIER 2: HIGH VALUE - Oncology & Neurosurgery Clinical Notes** (Priority Score: 85-95)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 5 | **Consult Note** | 43,538 | primary_diagnosis, chemotherapy_agent, chemotherapy_start_date, chemotherapy_end_date, chemotherapy_status, chemotherapy_line, chemotherapy_protocol, radiation_therapy_yn, clinical_status, progression_date, recurrence_date | Oncology consults contain treatment planning, chemotherapy regimen selection, line of therapy, response assessment, progression/recurrence dating. |
| 6 | **Progress Notes** | 727,633 | clinical_status, progression_date, recurrence_date, chemotherapy_status, chemotherapy_response, tumor_size, imaging_findings | **MOST ABUNDANT** note type. Longitudinal clinical assessments, treatment response, disease status changes. Variable quality - some are brief vitals checks, others detailed clinical assessments. |
| 7 | **H&P** (History & Physical) | 32,165 | primary_diagnosis, diagnosis_date, surgery_date, tumor_location, clinical_status, who_grade | Pre-operative H&P contains clinical history, diagnosis, surgical indication, baseline status. |
| 8 | **Admission Note** | 822 | primary_diagnosis, surgery_date, clinical_status, tumor_location, who_grade | Admission documentation for surgical or chemotherapy admissions. Contains diagnosis, reason for admission, treatment plan. |
| 9 | **ONC Outside Summaries** | 3,632 | primary_diagnosis, diagnosis_date, who_grade, tumor_location, chemotherapy_agent, chemotherapy_protocol, radiation_therapy_yn, molecular markers, clinical_status | External oncology summaries from referring institutions. May contain complete diagnostic and treatment history. |
| 10 | **External Consult Note** | 1,796 | Similar to Consult Note | External oncology/neurosurgery consult notes from other institutions. |
| 11 | **ONC RadOnc Consult** | 573 | radiation_therapy_yn, radiation_start_date, radiation_dose, tumor_location, clinical_status | Radiation oncology consults with treatment planning, dosing, target volumes. |

---

### **TIER 3: RADIOLOGY & IMAGING DOCUMENTATION** (Priority Score: 80-90)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 12 | **MR Brain W & W/O IV Contrast** | 14,512 | imaging_type, imaging_date, tumor_size, contrast_enhancement, imaging_findings, tumor_location, clinical_status | **PRIMARY BRAIN IMAGING** for brain tumor surveillance. Contains tumor measurements, enhancement patterns, progression/regression assessments. |
| 13 | **MR Entire Spine W & W/O IV Contrast** | 2,119 | imaging_type, imaging_date, tumor_location, metastasis, imaging_findings | Spine imaging for metastatic assessment or spinal cord tumors. |
| 14 | **MR Brain W/O IV Contrast** | 971 | imaging_type, imaging_date, tumor_size, imaging_findings, tumor_location | Non-contrast brain MRI (may be used for follow-up or pre-contrast baseline). |
| 15 | **MRI BRAIN WITH & W/O CONTRAST** | 2,334 | Same as #12 | Alternate naming for brain MRI with contrast. |
| 16 | **MR Brain & Pituitary W & W/O Contrast** | 665 | imaging_type, imaging_date, tumor_size, contrast_enhancement, tumor_location | Brain + pituitary protocol (relevant for suprasellar tumors). |
| 17 | **CT Brain W/O IV Contrast** | 4,100 | imaging_type, imaging_date, tumor_size, imaging_findings, tumor_location | CT brain (may be used for hydrocephalus assessment or emergency imaging). |
| 18 | **CT Brain Hydro W/O IV Contrast** | 1,104 | imaging_type, imaging_date, imaging_findings, tumor_location, clinical_status | CT specifically for hydrocephalus assessment (common complication of brain tumors). |
| 19 | **Diagnostic imaging study** | 158,059 | imaging_type, imaging_date, imaging_findings | **GENERIC IMAGING CATEGORY** - may include various modalities. Likely needs filtering by modality. |
| 20 | **External Radiology and Imaging** | 3,568 | imaging_type, imaging_date, tumor_size, imaging_findings, tumor_location | External radiology reports from outside institutions. |
| 21 | **ONC Outside Radiology** | 839 | imaging_type, imaging_date, tumor_size, imaging_findings | External radiology specific to oncology patients. |
| 22 | **Radiology Note** | 2,873 | imaging_type, imaging_date, imaging_findings | Radiology addendum or interpretive notes. |

---

### **TIER 4: ANESTHESIA & PERIOPERATIVE DOCUMENTATION** (Priority Score: 70-80)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 23 | **Anesthesia Preprocedure Evaluation** | 45,954 | surgery_date, surgery_type, clinical_status | Pre-anesthesia evaluation confirms surgical procedure, date, patient status. |
| 24 | **Anesthesia Postprocedure Evaluation** | 19,789 | surgery_date, surgery_type, clinical_status | Post-anesthesia assessment confirms procedure completion. |
| 25 | **Anesthesia Procedure Notes** | 3,043 | surgery_date, surgery_type | Intraoperative anesthesia documentation. |
| 26 | **Perioperative Records** | 2,927 | surgery_date, surgery_type, surgery_location | Perioperative nursing/surgical team documentation. |
| 27 | **Sedation** | 5,480 | Surgery context (procedures requiring sedation) | Sedation records for procedures (may include diagnostic procedures or minor surgeries). |
| 28 | **Pre-Sedation/Pre-Anesthesia Record** | 800 | surgery_date, clinical_status | Pre-sedation assessment and planning. |

---

### **TIER 5: LABORATORY & MOLECULAR DIAGNOSTICS** (Priority Score: 75-85)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 29 | **Laboratory report** | 14,206 | Tumor markers, molecular testing results | May include molecular testing reports (BRAF, IDH, MGMT, etc.) if sent as lab reports. |
| 30 | **Clinical Report-Laboratory** | 2,633 | Molecular markers, tumor markers | Formatted laboratory clinical reports. |
| 31 | **Lab Result Document** | 7,318 | Molecular testing, pathology correlates | Lab result documents may include molecular pathology results. |
| 32 | **Clinical Report-Procedure** | 6,037 | Procedural findings (lumbar puncture, biopsies) | May contain CSF cytology, tissue biopsy results relevant to diagnosis/metastasis. |

---

### **TIER 6: ENCOUNTER & CARE COORDINATION** (Priority Score: 65-75)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 33 | **Encounter Summary** | 393,616 | clinical_status, chemotherapy_status, progression_date, clinical events | **SECOND MOST ABUNDANT**. Summarizes clinical encounters - variable content quality. |
| 34 | **Care Plan Note** | 68,988 | chemotherapy_protocol, radiation_therapy_yn, clinical_status, treatment planning | Care plan documentation with treatment goals and strategies. |
| 35 | **Assessment & Plan Note** | 8,102 | clinical_status, progression_date, recurrence_date, chemotherapy_response, treatment plan | Assessment and plan sections often contain disease status and treatment adjustments. |
| 36 | **Transfer Note** | 7,956 | clinical_status, primary_diagnosis, treatment summary | Transfer summaries between services or institutions. |
| 37 | **Interval H&P Note** | 1,135 | clinical_status, disease progression, treatment updates | Interval history and physical for subsequent admissions. |

---

### **TIER 7: SPECIALIZED CLINICAL DOCUMENTATION** (Priority Score: 60-75)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 38 | **ED Notes** | 20,216 | clinical_status, acute complications, imaging findings | Emergency department notes may capture acute presentations (seizures, hydrocephalus, neurological changes). |
| 39 | **MH Progress Note** (Mental Health) | 5,473 | clinical_status, quality of life impacts | Mental health progress notes may document psychosocial impacts of disease/treatment. |
| 40 | **New Visit** | 1,329 | primary_diagnosis, diagnosis_date, clinical_status | New patient visits often contain comprehensive diagnostic history. |
| 41 | **FOLLOW-UP** | 13,866 | clinical_status, progression_date, recurrence_date, imaging_findings, chemotherapy_response | Follow-up visit notes with surveillance assessments. |
| 42 | **After Visit Summary** | 41,344 | clinical_status, treatment plan, medication changes | Patient-facing visit summaries with key clinical information. |
| 43 | **Medical Update** | 927 | clinical_status, progression_date, treatment changes | Medical status updates (often for care coordination). |
| 44 | **TEAM VISIT SUMMARY** | 858 | clinical_status, multidisciplinary treatment planning | Multidisciplinary team meeting summaries (tumor boards). |

---

### **TIER 8: EXTERNAL RECORDS & DOCUMENTATION** (Priority Score: 70-80)

| Rank | Note Type | Count | Variables Supported | Rationale |
|------|-----------|-------|---------------------|-----------|
| 45 | **Outside Records** | 3,809 | **ALL VARIABLES** - comprehensive external medical records | External records may contain complete diagnostic and treatment history from other institutions. |
| 46 | **External Patient Summary** | 3,710 | primary_diagnosis, diagnosis_date, treatment history, clinical_status | External patient summaries with comprehensive clinical history. |
| 47 | **External Progress Note** | 2,727 | clinical_status, treatment updates | External progress notes from outside providers. |
| 48 | **External Discharge Instructions** | 642 | Surgery summary, chemotherapy, clinical_status | External discharge summaries. |
| 49 | **Other Facility Records** | 650 | Variable - depends on content | Records from other healthcare facilities. |
| 50 | **External Misc Clinical** | 6,842 | Variable - diverse clinical content | Miscellaneous external clinical documentation. |

---

## Note Type Selection Strategy

### **Inclusion Criteria**:
1. **High clinical content density**: Contains structured clinical information (diagnosis, treatments, outcomes)
2. **Temporal specificity**: Documents dated events (surgery dates, diagnosis dates, treatment start/end dates)
3. **Quantitative data**: Measurements (tumor size, WHO grade, molecular markers)
4. **Longitudinal tracking**: Disease progression, treatment response, clinical status changes
5. **Multi-variable coverage**: Single note type supports multiple BRIM variables

### **Exclusion Criteria** (Note types NOT in top 50):
- **Administrative/consent forms**: Financial consents, billing forms, patient rights documents (no clinical data)
- **Patient-entered content**: Patient uploads, questionnaires (not clinician-verified)
- **Imaging raw data**: DICOM images/series (use radiology reports instead)
- **Scanned documents without context**: Generic scanned docs without clear clinical purpose
- **Duplicate/redundant types**: Multiple variants of same form type

---

## Usage Recommendations by Variable Category

### **For Diagnosis Variables** (primary_diagnosis, diagnosis_date, who_grade, tumor_location):
**Primary Sources**:
1. Pathology study (#1) - GOLD STANDARD
2. Discharge Summary (#4)
3. H&P (#7)
4. ONC Outside Summaries (#9)

**Supporting Sources**:
5. Consult Note (#5)
6. Admission Note (#8)

---

### **For Molecular Markers** (braf_status, idh_mutation, mgmt_methylation, 1p19q_codeletion):
**Primary Sources**:
1. Pathology study (#1) - GOLD STANDARD
2. Laboratory report (#29)
3. Clinical Report-Laboratory (#30)

**Supporting Sources**:
4. ONC Outside Summaries (#9) - may contain external molecular testing results
5. Discharge Summary (#4) - may reference molecular results

---

### **For Surgery Variables** (surgery_date, surgery_type, surgery_extent, surgery_location):
**Primary Sources**:
1. OP Note - Complete (#2) - GOLD STANDARD
2. OP Note - Brief (#3)
3. Discharge Summary (#4)

**Supporting Sources**:
4. H&P (#7) - pre-op documentation
5. Anesthesia Preprocedure Evaluation (#23) - confirms procedure
6. Perioperative Records (#26)

---

### **For Chemotherapy Variables** (agent, start_date, end_date, status, line, protocol, response):
**Primary Sources**:
1. Consult Note (#5) - oncology consults with treatment planning
2. Progress Notes (#6) - treatment response assessments
3. Discharge Summary (#4) - treatment initiation

**Supporting Sources**:
4. ONC Outside Summaries (#9)
5. Care Plan Note (#34)
6. Assessment & Plan Note (#35)

---

### **For Radiation Variables** (radiation_therapy_yn, radiation_start_date, radiation_dose):
**Primary Sources**:
1. ONC RadOnc Consult (#11) - GOLD STANDARD for radiation planning
2. Discharge Summary (#4)
3. Consult Note (#5)

**Supporting Sources**:
4. ONC Outside Summaries (#9)
5. Care Plan Note (#34)

---

### **For Imaging Variables** (imaging_type, imaging_date, tumor_size, contrast_enhancement, imaging_findings):
**Primary Sources**:
1. MR Brain W & W/O IV Contrast (#12) - GOLD STANDARD for brain tumor imaging
2. MR Entire Spine W & W/O IV Contrast (#13)
3. MR Brain W/O IV Contrast (#14)
4. CT Brain W/O IV Contrast (#17)

**Supporting Sources**:
5. Progress Notes (#6) - clinician interpretation of imaging
6. Consult Note (#5) - oncology interpretation
7. External Radiology and Imaging (#20)

---

### **For Clinical Status Variables** (clinical_status, progression_date, recurrence_date):
**Primary Sources**:
1. Progress Notes (#6) - longitudinal status assessments
2. Consult Note (#5) - formal progression/recurrence dating
3. Imaging reports (#12-22) - radiographic progression assessment

**Supporting Sources**:
4. FOLLOW-UP (#41)
5. Assessment & Plan Note (#35)
6. TEAM VISIT SUMMARY (#44) - tumor board decisions

---

## Implementation Considerations

### **Volume vs Quality Trade-off**:

**High-Volume, Variable-Quality Types**:
- Progress Notes: 727,633 documents
- Encounter Summary: 393,616 documents
- Diagnostic imaging study: 158,059 documents

**Strategy**: Use **temporal filtering** and **context filtering**:
- Prioritize notes within ±30 days of key clinical events (surgery dates, diagnosis date)
- Filter by clinical context (Neurosurgery, Oncology, Radiation Oncology)
- Use LOINC codes to identify high-value progress notes (oncology progress notes vs routine vitals checks)

**Low-Volume, High-Quality Types**:
- OP Note - Complete: 11,612 documents
- Pathology study: 149,132 documents (but likely multi-patient)
- ONC RadOnc Consult: 573 documents

**Strategy**: Include **ALL instances** for pilot patient, as these are inherently high-value.

---

### **Database Query Pattern**:

```sql
-- Example: Retrieve top 50 note types for patient C1277724
SELECT
    dr.id as document_id,
    dr.type_text,
    dr.document_date,
    dr.context_practice_setting_text,
    drc.content_attachment_url
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc
    ON dr.id = drc.document_reference_id
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.type_text IN (
    'Pathology study',
    'OP Note - Complete (Template or Full Dictation)',
    'Discharge Summary',
    'Consult Note',
    'H&P',
    'MR Brain W & W/O IV Contrast',
    'Progress Notes',
    -- ... (all 50 note types)
  )
ORDER BY
    CASE dr.type_text
        WHEN 'Pathology study' THEN 1
        WHEN 'OP Note - Complete (Template or Full Dictation)' THEN 2
        WHEN 'OP Note - Brief (Needs Dictation)' THEN 3
        WHEN 'Discharge Summary' THEN 4
        -- ... priority ordering
        ELSE 999
    END,
    dr.document_date DESC;
```

---

## Expected Coverage Improvement

### **Current Phase 3a_v2 project.csv**:
- 40 clinical documents (7 operative notes, 11 anesthesia notes, 20 CBC labs, 2 procedure notes)
- **Limited coverage**: Primarily surgical documentation + basic labs
- **Missing**: Pathology reports, oncology consults, radiology narrative reports, discharge summaries

### **Enhanced with Top 50 Note Types**:
- **Pathology coverage**: Add pathology study reports → +9 variables (diagnosis, molecular markers)
- **Oncology coverage**: Add consult notes → +7 variables (chemotherapy details)
- **Radiology coverage**: Add MR Brain reports → +5 variables (imaging details)
- **Discharge summary coverage**: Add discharge summaries → Multi-variable validation (diagnosis, surgery, treatment plan)

### **Projected Accuracy Improvement**:
- **Baseline (current)**: 81.2% (Phase 3a)
- **Enhanced (top 50 note types)**: **>90%** (target)
- **Greatest gains**: Molecular markers (+85%), Imaging findings (+75%), Chemotherapy protocol (+60%)

---

## Validation Against Gold Standard

### **Gold Standard Coverage by Note Type**:

| Variable Category | Gold Standard Source | Top Note Type(s) | Expected Match Rate |
|-------------------|---------------------|------------------|---------------------|
| **Diagnosis** | 20250723_multitab__diagnosis.csv | Pathology study, Discharge Summary | >95% |
| **Molecular** | 20250723_multitab__molecular_characterization.csv | Pathology study, Laboratory report | >90% |
| **Surgery** | 20250723_multitab__treatments.csv | OP Note - Complete, Discharge Summary | >95% |
| **Chemotherapy** | 20250723_multitab__treatments.csv | Consult Note, Progress Notes | >85% |
| **Radiation** | 20250723_multitab__treatments.csv | ONC RadOnc Consult, Discharge Summary | >90% |
| **Imaging** | 20250723_multitab__measurements.csv | MR Brain W & W/O IV Contrast | >90% |
| **Clinical Status** | 20250723_multitab__diagnosis.csv | Progress Notes, Consult Note, Imaging | >85% |

---

## Next Steps

1. **Query fhir_v1_prd_db.document_reference** filtered by top 50 note types for patient C1277724
2. **Retrieve document counts** per note type for this specific patient
3. **Download Binary content** from S3 for all matching documents
4. **Update project.csv** with enhanced document set
5. **Re-run BRIM extraction** and validate against gold standard
6. **Measure accuracy improvement** vs Phase 3a baseline

---

**Document Status**: ✅ Complete
**Total Note Types Analyzed**: 3,982
**Top Priority Note Types Selected**: 50
**Expected Variable Coverage**: 31/31 variables (100%)
**Projected Accuracy**: >90% (vs 81.2% baseline)
