# Radiation Data Deep Dive - Comprehensive Source Assessment
**Date**: October 18, 2025
**Status**: ✅ **MULTIPLE DATA SOURCES IDENTIFIED**

---

## Executive Summary

✅ **Found THREE major sources of radiation therapy data beyond original views**

### Critical Discoveries

1. **📊 Observation/Observation_Component** - **STRUCTURED DOSE DATA** (89 patients with dose, 90 with field/site)
2. **📄 Document_Reference** - Treatment summaries, consults, progress notes (563 patients)
3. **🔬 Procedure_Code_Coding** - Limited radiation treatment management CPT codes (3 procedures)

### Test Patient Status Update

| Patient ID (truncated) | Documents | Observations | Status |
|------------------------|-----------|--------------|--------|
| e4BwD8ZYDBccepXcJ.Il... | 0 | 0 | ❌ No RT data |
| eXdoUrDdY4gkdnZEs6uT... | 0 | 0 | ❌ No RT data |
| enen8-RpIWkLodbVcZHG... | 0 | 0 | ❌ No RT data |
| **emVHLbfTGZtwi0Isqq-B...** | **6** | 0 | ✅ **HAS RT DOCS** |

---

## Data Source #1: Observation + Observation_Component (STRUCTURED)

### Discovery

**ELECT intake forms capture radiation treatment details in structured Observation format**

### Coverage Statistics

| Observation Code | Records | Patients | Data Type |
|------------------|---------|----------|-----------|
| ELECT - INTAKE FORM - RADIATION TABLE - DOSE | 89 | 89 | **Numeric (cGy)** |
| ELECT - INTAKE FORM - RADIATION TABLE - FIELD | 90 | 90 | **Text (site)** |
| ELECT - INTAKE FORM - RADIATION TABLE - START DATE | 89 | 89 | Date |
| ELECT - INTAKE FORM - RADIATION TABLE - STOP DATE | 88 | 88 | Date |
| MEDULLOBLASTOMA CSI RADIATION | 41 | 41 | Flag |
| MEDULLOBLASTOMA FOCAL RADIATION | 12 | 12 | Flag |

**Total**: 448 unique patients with radiation observations

### Data Structure

**Main Observation Record**:
```sql
observation:
  id
  subject_reference (patient ID)
  code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - DOSE'
  effective_date_time
  -- Values are in observation_component (not observation.value_string)
```

**Component Data** (where actual values stored):
```sql
observation_component:
  observation_id (FK to observation.id)
  component_code_text = 'Line 1', 'Line 2', 'Line 3' (multiple RT courses)
  component_value_quantity_value = '5400', '3600', '900' (DOSE IN cGy)
  component_value_quantity_unit = '' (usually blank but value is in cGy)
  component_value_string = 'Cranial', 'Craniospinal' (FIELD/SITE)
```

### Sample Data

**Patient eCYBAOraExal4hNZq.9Ys4rpwHQ0y3GXmf6NiTs2JQMA3**:
```
FIELD (Line 1): "Cranial"
DOSE (Line 1): 5400 cGy
```

**Patient eBJ6URDmDsorjmOuKC4VswSrMa1KlQUBcnR2lVGjnDU83**:
```
DOSE (Line 1): 5940 cGy
```

**Patient eUrpqOhrQdVFf0ydL8Mtq6cOgzeq311wa5gOYKXLLPYo3** (Multiple courses):
```
DOSE (Line 1): 3600 cGy
DOSE (Line 2): 1800 cGy
DOSE (Line 3): 900 cGy
```

**Patient ebvQ9rFL6eI89TM8MUaL.JOeSqvnYbXT4OLHRjHGdmNQ3** (Multiple sites):
```
FIELD (Line 1): "Cranial"
FIELD (Line 2): "Craniospinal"
FIELD (Line 3): "Other (skeletal sites important for growth e.g. femur, tibia, etc)"
```

### Field/Site Value Distribution (Inferred from Sample)

Based on observed patterns:
- **"Cranial"** = Focal radiation to tumor bed (maps to CBTN radiation_site = 1)
- **"Craniospinal"** = CSI radiation (maps to CBTN radiation_site = 8)
- **"Other (skeletal sites...)"** = Other sites (maps to CBTN radiation_site = 6)

### CBTN Field Mapping

| CBTN Field | Source | Extraction Method | Coverage |
|------------|--------|-------------------|----------|
| **radiation_site** | observation_component.component_value_string | Parse "Cranial"/"Craniospinal"/etc | ✅ 90 patients |
| **total_radiation_dose** | observation_component.component_value_quantity_value | Direct extraction (cGy) | ✅ 89 patients |
| **total_radiation_dose_unit** | Inferred | Default to "cGy" (consistent in data) | ✅ 89 patients |
| **date_at_radiation_start** | observation_component (START DATE code) | Extract from component | ✅ 89 patients |
| **date_at_radiation_stop** | observation_component (STOP DATE code) | Extract from component | ✅ 88 patients |

### Query to Extract Structured Radiation Data

```sql
-- Get radiation dose for a patient
SELECT
    o.subject_reference as patient_fhir_id,
    o.code_text,
    oc.component_code_text as line_number,
    oc.component_value_quantity_value as dose_cgy,
    o.effective_date_time
FROM fhir_prd_db.observation o
JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
WHERE o.subject_reference LIKE '%PATIENT_ID%'
  AND o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - DOSE'
ORDER BY oc.component_code_text;

-- Get radiation field/site for a patient
SELECT
    o.subject_reference as patient_fhir_id,
    o.code_text,
    oc.component_code_text as line_number,
    oc.component_value_string as radiation_field,
    o.effective_date_time
FROM fhir_prd_db.observation o
JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
WHERE o.subject_reference LIKE '%PATIENT_ID%'
  AND o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - FIELD'
ORDER BY oc.component_code_text;

-- Get radiation dates
SELECT
    o.subject_reference as patient_fhir_id,
    o.code_text,
    o.effective_date_time,
    oc.component_code_text as line_number
FROM fhir_prd_db.observation o
LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
WHERE o.subject_reference LIKE '%PATIENT_ID%'
  AND (o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - START DATE'
       OR o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - STOP DATE')
ORDER BY o.code_text, oc.component_code_text;
```

### Limitations

- ❌ **Radiation type** (protons/photons/gamma knife) NOT in observations
- ❌ **Focal/boost dose separate from CSI** - requires field interpretation
- ⚠️ **Multiple lines** (Line 1, Line 2, Line 3) may represent:
  - Multiple RT courses (initial + recurrence)
  - CSI + boost (separate dose lines)
  - Multiple target sites
- ⚠️ **Date parsing** may be needed (effective_date_time vs component extraction)

---

## Data Source #2: Document_Reference (DOCUMENTS)

### Discovery

**5,024 radiation-related documents across 563 patients**

### Document Type Distribution

| Document Type | Count | Patients | CBTN Value |
|---------------|-------|----------|------------|
| **Rad Onc Treatment Report** | 24 | 21 | 📄 End of treatment summary |
| **ONC RadOnc End of Treatment** | 17 | 16 | 📄 Treatment completion |
| **ONC RadOnc Consult** | 8 | 8 | 📄 Initial RT planning |
| ONC Outside Summaries | 92 | 68 | 📄 External RT records |
| Clinical Report-Consult | 43 | 37 | 📄 Consult notes |
| External Misc Clinical | 39 | 20 | 📄 Outside records |
| Clinical Report-Other | 31 | 30 | 📄 Miscellaneous |
| (NULL type_text) | 965 | 311 | 📄 Various |

**High-Value Document Types for Extraction**:

1. **Rad Onc Treatment Report / ONC RadOnc End of Treatment** (41 docs, 37 patients)
   - Contains: Completed dose, fractions, sites, modality, dates
   - Example descriptions:
     - "ONC RadOnc End of Treatment Summary Note"
     - "2025.5.5 ONC RadOnc End of Radiation Treatment Summary Report Penn Medicine"
     - "ONC RadOnc End of Treatment Summary Report w Dr. Michael LaRiviere"

2. **ONC RadOnc Consult** (8 docs, 8 patients)
   - Contains: Planned dose, treatment intent, radiation type
   - Example descriptions:
     - "ONC RadOnc Consult 4/21/14"
     - "Penn Med RadOnc Initial Consultation"
     - "Penn Med RadOnc Consultation Note"

3. **Radiation Progress Note / Social Work Notes** (Context documents)
   - Example: "Radiation Progress Note", "Radiation Oncology Social Work Note"
   - May contain side effects, adherence, treatment modifications

### Test Patient Document Details

**Patient: emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3** (6 documents):

| Type | Description | Date |
|------|-------------|------|
| ONC Outside Summaries | ONC Outside Radiation Oncology IP Consult | NULL |
| ONC Outside Summaries | 2/2/18 PENN Radiation Oncology Summary | NULL |
| Clinical Report-Consult | Radiation Progress Note | 2019-02-01 |
| (NULL) | Radiation Oncology Social Work Note | 2019-02-24 |
| (NULL) | Radiation Oncology Social Work Note | 2023-09-04 |
| (NULL) | Radiation Oncology Social Work Note | 2023-09-04 |

**Key Findings**:
- External institution summary ("PENN Radiation Oncology Summary")
- Initial consult ("Radiation Oncology IP Consult")
- Progress/follow-up notes
- **Dates span 2017-2023** (context_period_start to date)

### Document Content Access

**Schema**:
```sql
document_reference:
  id (document ID)
  type_text (document type classification)
  description (document title/description)
  date (document creation date)
  subject_reference (patient ID)
  status (current/superseded)
  context_period_start (clinical context start)
  context_period_end (clinical context end)
```

**Content Linkage**:
```sql
document_reference_content:
  document_reference_id (FK)
  attachment_content_type (e.g., "application/pdf")
  attachment_url (reference to Binary resource)
  attachment_title
```

**Binary Content**:
```sql
binary:
  id (referenced by document_reference_content.attachment_url)
  content_type
  data (base64 encoded PDF/text)
```

### Query to Extract Document References

```sql
-- Get all radiation documents for a patient
SELECT
    dr.id as document_id,
    dr.type_text,
    dr.description,
    dr.date,
    dr.status,
    drc.attachment_content_type,
    drc.attachment_url
FROM fhir_prd_db.document_reference dr
LEFT JOIN fhir_prd_db.document_reference_content drc ON dr.id = drc.document_reference_id
WHERE dr.subject_reference LIKE '%PATIENT_ID%'
  AND (LOWER(dr.type_text) LIKE '%radiation%'
       OR LOWER(dr.description) LIKE '%radiation%')
ORDER BY dr.date;
```

### NLP Extraction Targets

**From "Rad Onc Treatment Report" / "End of Treatment Summary"**:
```
Pattern examples:
- "Total dose delivered: 5400 cGy to the tumor bed"
- "Craniospinal irradiation to 3600 cGy with boost to 5400 cGy"
- "Proton therapy"
- "Treatment completed on [date]"
- "30 fractions"
```

**From "RadOnc Consult"**:
```
Pattern examples:
- "Plan: Focal radiation to 5400 cGy in 30 fractions"
- "Craniospinal axis 3600 cGy followed by boost 1800 cGy"
- "IMRT technique"
- "Recommend proton therapy"
```

---

## Data Source #3: Procedure_Code_Coding (LIMITED)

### Discovery

**Only 3 radiation-related procedures found** - Very limited coverage

### Procedure Codes Found

| CPT Code | Description | Count |
|----------|-------------|-------|
| 77295 | 3-D RADIOTHERAPY PLAN DOSE-VOLUME HISTOGRAMS | 1 |
| 77427 | RADIATION TREATMENT MANAGEMENT 5 TREATMENTS | 1 |
| 61800 | APPL STRTCTC HEADFRAME STEREOTACTIC RADIOSURGERY | 1 |

### Assessment

⚠️ **Procedure codes are NOT a reliable source for radiation treatment data**
- Only 3 procedures across entire database
- Represents billing/administrative records, not clinical detail
- Missing dose, site, dates
- **Recommendation**: Use for validation/cross-checking only, not primary extraction

---

## Data Source #4: Diagnostic_Report (MINIMAL)

### Discovery

**Only 3 radiation-related diagnostic reports** - Not useful for RT treatment data

### Reports Found

| Code Text | Count |
|-----------|-------|
| CT head medical radiation dosimetry | 2 |
| CT spine medical radiation dosimetry | 1 |

### Assessment

❌ **Diagnostic reports are NOT useful for radiation therapy treatment data**
- These are **dosimetry reports from CT scans** (radiation exposure from imaging)
- NOT radiation therapy treatment reports
- **Recommendation**: Ignore for RT data extraction

---

## Revised Data Extraction Strategy

### Phase 1: Structured Observation Data (PRIMARY - NEW!)

**Source**: `observation` + `observation_component` tables

**Extract**:
1. ✅ **Radiation dose** (component_value_quantity_value from DOSE observations)
2. ✅ **Radiation site/field** (component_value_string from FIELD observations)
3. ✅ **Start/stop dates** (from START DATE / STOP DATE observations)
4. ✅ **Multiple courses** (Line 1, Line 2, Line 3 from component_code_text)

**Coverage**: ~89-90 patients with structured dose and site data

**Implementation**:
```python
def query_radiation_observations(patient_fhir_id):
    """Extract structured radiation data from ELECT intake forms."""

    # Query for dose
    dose_query = """
    SELECT
        oc.component_code_text as line_number,
        oc.component_value_quantity_value as dose_cgy
    FROM fhir_prd_db.observation o
    JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.subject_reference LIKE '%{patient_id}%'
      AND o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - DOSE'
    ORDER BY oc.component_code_text
    """

    # Query for site/field
    field_query = """
    SELECT
        oc.component_code_text as line_number,
        oc.component_value_string as radiation_field
    FROM fhir_prd_db.observation o
    JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.subject_reference LIKE '%{patient_id}%'
      AND o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - FIELD'
    ORDER BY oc.component_code_text
    """

    # Combine and map to CBTN fields
    return map_to_cbtn_fields(doses, fields)

def map_to_cbtn_fields(doses, fields):
    """Map observation data to CBTN radiation fields."""

    # Map field text to CBTN radiation_site codes
    site_mapping = {
        'Cranial': 1,  # Focal/Tumor bed
        'Craniospinal': 8,  # Craniospinal with focal boost
        'Whole Ventricular': 9  # Whole ventricular with focal boost
    }

    return {
        'radiation_site': site_mapping.get(fields[0], 6),  # Default to "Other"
        'total_radiation_dose': doses[0] if 'Craniospinal' in fields else None,
        'total_radiation_dose_unit': 'cGy',
        'total_radiation_dose_focal': doses[0] if 'Cranial' in fields else doses[1] if len(doses) > 1 else None,
        'total_radiation_dose_focal_unit': 'cGy'
    }
```

### Phase 2: Document Extraction (SUPPLEMENT)

**Source**: `document_reference` + Binary content

**Target Documents** (priority order):
1. **Rad Onc Treatment Report** (24 docs, 21 patients)
2. **ONC RadOnc End of Treatment** (17 docs, 16 patients)
3. **ONC RadOnc Consult** (8 docs, 8 patients)
4. **Outside Summaries** with "radiation" in description (92 docs, 68 patients)

**Extract**:
1. ❌ **Radiation type** (protons/photons/gamma knife) - NOT in observations
2. ❌ **Treatment intent/indication** - NOT in observations
3. ❌ **Fractions** - NOT in observations
4. ⚠️ **Dose validation** - Cross-check against observation data
5. ⚠️ **Site clarification** - Disambiguate CSI vs CSI+boost

**Coverage**: ~563 patients total with radiation documents

### Phase 3: Service Request Dates (FALLBACK)

**Source**: `v_radiation_treatment_courses` (service_request table)

**Extract**:
- ✅ Treatment start date (sr_occurrence_period_start)
- ✅ Treatment stop date (sr_occurrence_period_end)

**Coverage**: Only 3 records (1 patient) - very limited

**Use Case**: Fallback for patients without observation dates

---

## Updated Coverage Assessment

### CBTN Field Coverage Update

| CBTN Field | Source Priority 1 | Source Priority 2 | Coverage | Status |
|------------|-------------------|-------------------|----------|--------|
| **radiation** | Observation | Document | ✅ ~563 patients | ✅ COVERED |
| **date_at_radiation_start** | Observation | Service Request | ✅ ~89 patients | ✅ COVERED |
| **date_at_radiation_stop** | Observation | Service Request | ✅ ~88 patients | ✅ COVERED |
| **radiation_site** | **Observation** | Document (NLP) | ✅ **~90 patients** | ✅ **COVERED** |
| **total_radiation_dose** | **Observation** | Document (NLP) | ✅ **~89 patients** | ✅ **COVERED** |
| **total_radiation_dose_unit** | **Observation (inferred)** | Document (NLP) | ✅ **~89 patients** | ✅ **COVERED** |
| **total_radiation_dose_focal** | **Observation (parsed)** | Document (NLP) | ⚠️ **Partial** | ⚠️ HYBRID |
| **total_radiation_dose_focal_unit** | **Observation (inferred)** | Document (NLP) | ⚠️ **Partial** | ⚠️ HYBRID |
| **radiation_type** | Document (NLP) | N/A | ⚠️ **~40-60 patients** | ⚠️ DOCUMENT_ONLY |
| **radiation_type_other** | Document (NLP) | N/A | ⚠️ Low | ⚠️ DOCUMENT_ONLY |

### Coverage Summary (REVISED)

**STRUCTURED_ONLY** (5 fields - MAJOR IMPROVEMENT):
- radiation (can infer from observation or document presence)
- date_at_radiation_start ✅ **NEW**
- date_at_radiation_stop ✅ **NEW**
- **radiation_site** ✅ **NEW - MAJOR FIND**
- **total_radiation_dose** ✅ **NEW - MAJOR FIND**
- **total_radiation_dose_unit** ✅ **NEW**

**HYBRID** (3 fields):
- total_radiation_dose_focal (observation parsing + document validation)
- total_radiation_dose_focal_unit (observation parsing + document validation)
- radiation_site clarification (observation + document for ambiguous cases)

**DOCUMENT_ONLY** (2 fields):
- radiation_type (protons/photons/gamma knife)
- radiation_type_other

**Improvement**: From 20% structured coverage to **60% structured coverage** (6/10 fields)

---

## Recommended Athena View Enhancements

### Create v_radiation_observations View

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_observations AS
WITH radiation_dose AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as line_number,
        CAST(oc.component_value_quantity_value AS DOUBLE) as dose_cgy,
        o.effective_date_time
    FROM fhir_prd_db.observation o
    JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - DOSE'
),
radiation_field AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as line_number,
        oc.component_value_string as radiation_field,
        o.effective_date_time
    FROM fhir_prd_db.observation o
    JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - FIELD'
),
radiation_start_date AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as line_number,
        o.effective_date_time as start_date
    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - START DATE'
),
radiation_stop_date AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        oc.component_code_text as line_number,
        o.effective_date_time as stop_date
    FROM fhir_prd_db.observation o
    LEFT JOIN fhir_prd_db.observation_component oc ON o.id = oc.observation_id
    WHERE o.code_text = 'ELECT - INTAKE FORM - RADIATION TABLE - STOP DATE'
)
SELECT
    COALESCE(rd.patient_fhir_id, rf.patient_fhir_id, rsd.patient_fhir_id, rst.patient_fhir_id) as patient_fhir_id,
    COALESCE(rd.line_number, rf.line_number, rsd.line_number, rst.line_number) as course_line_number,
    rd.dose_cgy,
    rf.radiation_field,
    rsd.start_date,
    rst.stop_date,
    -- Map field to CBTN radiation_site codes
    CASE
        WHEN LOWER(rf.radiation_field) LIKE '%cranial%' AND LOWER(rf.radiation_field) NOT LIKE '%craniospinal%' THEN 1  -- Focal
        WHEN LOWER(rf.radiation_field) LIKE '%craniospinal%' THEN 8  -- CSI with boost
        WHEN LOWER(rf.radiation_field) LIKE '%ventricular%' THEN 9  -- Whole ventricular with boost
        ELSE 6  -- Other
    END as radiation_site_code
FROM radiation_dose rd
FULL OUTER JOIN radiation_field rf ON rd.patient_fhir_id = rf.patient_fhir_id AND rd.line_number = rf.line_number
FULL OUTER JOIN radiation_start_date rsd ON COALESCE(rd.patient_fhir_id, rf.patient_fhir_id) = rsd.patient_fhir_id
    AND COALESCE(rd.line_number, rf.line_number) = rsd.line_number
FULL OUTER JOIN radiation_stop_date rst ON COALESCE(rd.patient_fhir_id, rf.patient_fhir_id, rsd.patient_fhir_id) = rst.patient_fhir_id
    AND COALESCE(rd.line_number, rf.line_number, rsd.line_number) = rst.line_number
ORDER BY patient_fhir_id, course_line_number;
```

### Create v_radiation_documents View

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_documents AS
SELECT
    dr.subject_reference as patient_fhir_id,
    dr.id as document_id,
    dr.type_text as document_type,
    dr.description as document_description,
    dr.date as document_date,
    dr.status as document_status,
    dr.context_period_start,
    dr.context_period_end,
    drc.attachment_content_type,
    drc.attachment_url,
    drc.attachment_title,
    -- Priority classification for extraction
    CASE
        WHEN dr.type_text IN ('Rad Onc Treatment Report', 'ONC RadOnc End of Treatment') THEN 1  -- Highest priority
        WHEN dr.type_text = 'ONC RadOnc Consult' THEN 2  -- High priority
        WHEN LOWER(dr.description) LIKE '%end of treatment%' OR LOWER(dr.description) LIKE '%treatment summary%' THEN 1
        WHEN LOWER(dr.description) LIKE '%consult%' THEN 2
        WHEN dr.type_text = 'ONC Outside Summaries' THEN 3  -- Medium priority
        ELSE 4  -- Lower priority
    END as extraction_priority
FROM fhir_prd_db.document_reference dr
LEFT JOIN fhir_prd_db.document_reference_content drc ON dr.id = drc.document_reference_id
WHERE (LOWER(dr.type_text) LIKE '%radiation%'
       OR LOWER(dr.description) LIKE '%radiation%'
       OR LOWER(dr.description) LIKE '%radionc%'
       OR LOWER(dr.description) LIKE '%rad onc%')
ORDER BY dr.subject_reference, extraction_priority, dr.date;
```

---

## Next Steps

### Immediate (View Creation - 30 minutes)
1. ✅ Document comprehensive findings
2. ⏳ **Create v_radiation_observations view** - Add to ATHENA_VIEW_CREATION_QUERIES.sql
3. ⏳ **Create v_radiation_documents view** - Add to ATHENA_VIEW_CREATION_QUERIES.sql
4. ⏳ Deploy updated views to Athena
5. ⏳ Test extraction on patient with observation data

### Short-Term (Extraction Implementation - 1 week)
6. ⏳ Add `query_radiation_observations()` method to AthenaQueryAgent
7. ⏳ Add `query_radiation_documents()` method to AthenaQueryAgent
8. ⏳ Implement field mapping logic (observation field → CBTN radiation_site code)
9. ⏳ Implement dose parsing logic (handle multiple lines for CSI+boost)
10. ⏳ Test on all 4 test patients (especially emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3)

### Medium-Term (Document Extraction - 2 weeks)
11. ⏳ Implement binary content extraction for high-priority documents
12. ⏳ Develop NLP patterns for radiation_type extraction (protons/photons)
13. ⏳ Implement cross-validation between observation and document data
14. ⏳ Test on full cohort of ~90 patients with observation data

---

## Conclusion

**Major Discovery**: ELECT intake forms provide **structured radiation dose and site data** for ~90 patients via Observation/Observation_Component tables

**Impact**: Coverage improved from 20% to **60% structured fields** (6/10 CBTN radiation fields)

**Critical Fields Now Available**:
- ✅ Radiation dose (cGy) - **STRUCTURED**
- ✅ Radiation site (Cranial/Craniospinal) - **STRUCTURED**
- ✅ Start/stop dates - **STRUCTURED**

**Remaining Document Extraction**:
- ❌ Radiation type (protons/photons) - **DOCUMENT_ONLY**
- ⚠️ Focal vs CSI dose disambiguation - **HYBRID**

**Test Patient Status**: 1/4 test patients (emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3) has 6 radiation documents available for extraction

---

**Files to Update**:
- ATHENA_VIEW_CREATION_QUERIES.sql - Add v_radiation_observations and v_radiation_documents views
- athena_query_agent.py - Add query_radiation_observations() and query_radiation_documents() methods
- STRUCTURED_DATA_GAP_ANALYSIS.md - Update radiation coverage from 20% to 60%
- RADIATION_DATA_ASSESSMENT.md - Supplement with observation findings

**Next Action**: Create and deploy v_radiation_observations and v_radiation_documents views
