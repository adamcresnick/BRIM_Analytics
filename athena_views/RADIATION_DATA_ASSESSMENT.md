# Radiation Oncology Data - Complete Assessment
**Date**: October 18, 2025
**Status**: ⚠️ **CRITICAL GAPS IDENTIFIED**

---

## Executive Summary

⚠️ **Radiation data in FHIR is SEVERELY LIMITED - Most CBTN fields require document extraction**

### Key Findings
- **Test Patient Status**: 0/4 test patients have radiation data in FHIR
- **Overall Coverage**: Only 1,855 patients have radiation appointments (likely subset of all RT patients)
- **CBTN Required Fields**: 10 radiation fields
- **Structured Coverage**: 2/10 fields (20%) - Only dates available
- **Critical Missing Data**: Dose, site, radiation type, boost information

---

## Test Patient Assessment

### Patients Evaluated

| Patient ID (truncated) | Radiation Appointments | Treatment Courses | Care Plans | Status |
|------------------------|----------------------|-------------------|------------|--------|
| e4BwD8ZYDBccepXcJ.Il... | 0 | 0 | 0 | ❌ No RT data |
| eXdoUrDdY4gkdnZEs6uT... | 0 | 0 | 0 | ❌ No RT data |
| enen8-RpIWkLodbVcZHG... | 0 | 0 | 0 | ❌ No RT data |
| emVHLbfTGZtwi0Isqq-B... | 0 | 0 | 0 | ❌ No RT data |

**Conclusion**: None of the 4 test patients have radiation therapy data in structured FHIR format.

### Overall Radiation Data Availability

| View | Total Records | Unique Patients | Data Quality |
|------|---------------|-----------------|--------------|
| v_radiation_treatment_appointments | 331,796 | 1,855 | ⚠️ Limited metadata (dates only) |
| v_radiation_treatment_courses | 3 | 1 | ❌ Extremely sparse |
| v_radiation_care_plan_hierarchy | 18,189 | 568 | ⚠️ Title only ("Radiation & Side Effects") |
| v_radiation_service_request_rt_history | 37,613 | 401 | ⚠️ Minimal structured data |
| v_radiation_care_plan_notes | N/A | N/A | 📝 Free text only |
| v_radiation_service_request_notes | N/A | N/A | 📝 Free text only |

---

## CBTN Data Dictionary Requirements vs Athena Coverage

### Required Radiation Fields (10 total from CBTN)

| CBTN Field | Description | Athena Source | Coverage | Status |
|------------|-------------|---------------|----------|--------|
| **radiation** | Yes/No flag | v_radiation_treatment_courses | ✅ Can infer | ✅ PARTIAL |
| **date_at_radiation_start** | Start date | v_radiation_treatment_courses | ✅ Available | ✅ COVERED |
| **date_at_radiation_stop** | Stop date | v_radiation_treatment_courses | ✅ Available | ✅ COVERED |
| **radiation_site** | Focal/CSI/Whole Ventricular | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **radiation_site_other** | Free text site | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **total_radiation_dose** | CSI/WV dose (cGy) | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **total_radiation_dose_unit** | cGy/Gy/CGE | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **total_radiation_dose_focal** | Focal/boost dose | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **total_radiation_dose_focal_unit** | cGy/Gy/CGE | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **radiation_type** | Protons/Photons/Gamma Knife | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |
| **radiation_type_other** | Other type description | ❌ NOT IN FHIR | ❌ Missing | ❌ DOCUMENT_ONLY |

### Coverage Summary

**Structured (STRUCTURED_ONLY)**: 2/10 fields (20%)
- ✅ Date at radiation start
- ✅ Date at radiation stop

**Document Extraction Required (DOCUMENT_ONLY)**: 8/10 fields (80%)
- ❌ Radiation site classification
- ❌ Total dose (CSI/whole ventricular)
- ❌ Focal/boost dose
- ❌ Dose units
- ❌ Radiation type (protons/photons/gamma knife)

---

## Available Structured Data - Detailed Analysis

### 1. v_radiation_treatment_courses

**Schema**:
```
patient_fhir_id
course_id
sr_status                         -- Status of service request
sr_intent                         -- Intent (order/plan)
sr_code_text                      -- Code description (often generic)
sr_quantity_value                 -- Quantity (NOT dose - appears to be fractions?)
sr_quantity_unit                  -- Unit (NOT dose unit)
sr_occurrence_date_time           -- Single occurrence timestamp
sr_occurrence_period_start        -- ✅ START DATE
sr_occurrence_period_end          -- ✅ STOP DATE
sr_authored_on                    -- Order date
sr_requester_display              -- Ordering provider
sr_performer_type_text            -- Performing service type
sr_patient_instruction            -- Patient instructions
```

**Data Quality Issues**:
- Only **3 records** across **1 patient** in entire database
- sr_quantity_value/sr_quantity_unit likely represents number of fractions, NOT total dose
- No structured dose fields (cGy, Gy)
- No site classification (focal vs CSI)
- No radiation modality (protons vs photons)

**Sample Data** (from patient eOEaUZ-6f0vYGBS1s8M-hrw3):
```
sr_code_text: NULL or generic "Radiation Therapy"
sr_occurrence_period_start: Available (treatment start date)
sr_occurrence_period_end: Available (treatment end date)
sr_quantity_value: NULL
sr_quantity_unit: NULL
```

### 2. v_radiation_treatment_appointments

**Schema**:
```
patient_fhir_id
appointment_id
appointment_status               -- arrived/fulfilled/noshow/cancelled
appointment_type_text            -- Usually NULL
priority                         -- Usually NULL
description                      -- Usually NULL
appointment_start                -- ✅ APPOINTMENT DATE/TIME
appointment_end                  -- Appointment end time
minutes_duration                 -- Duration of appointment
created                          -- When appointment was scheduled
appointment_comment              -- Usually NULL
patient_instruction              -- Usually NULL
```

**Data Quality Issues**:
- 331,796 appointments across 1,855 patients
- **No clinical detail** - just scheduling data
- Cannot distinguish RT type, site, or dose from appointments
- Useful only for date range validation and treatment adherence tracking

**Sample Data**:
```
appointment_start: 2001-06-11T04:00:00Z
appointment_status: fulfilled
appointment_type_text: NULL
description: NULL
```

### 3. v_radiation_care_plan_hierarchy

**Schema**:
```
patient_fhir_id
care_plan_id
cppo_part_of_reference           -- Linkage to parent care plan
cp_status                        -- completed/active
cp_intent                        -- plan
cp_title                         -- "Radiation & Side Effects" (generic title)
cp_period_start                  -- Care plan start (may be NULL)
cp_period_end                    -- Care plan end (may be NULL)
```

**Data Quality Issues**:
- 18,189 records across 568 patients
- cp_title is ALWAYS "Radiation & Side Effects" - no specificity
- No dose, site, or modality information
- Period dates often NULL

### 4. v_radiation_service_request_rt_history

**Schema**:
```
patient_fhir_id
sr_id
sr_status                        -- Status
sr_code_text                     -- Code description (often NULL)
sr_authored_on                   -- Order date
srrc_reason_code_coding          -- Reason code (structured)
srrc_reason_code_text            -- Reason text (may have diagnosis)
```

**Data Quality Issues**:
- 37,613 records across 401 patients
- sr_code_text often NULL
- srrc_reason_code_text may contain diagnosis (e.g., "Brain tumor") but not RT details
- No dose or site information

### 5. v_radiation_care_plan_notes (Free Text)

**Schema**:
```
patient_fhir_id
care_plan_id
cpn_note_text                    -- 📝 FREE TEXT - may contain dose/site info
cp_status
cp_intent
cp_title
cp_period_start
cp_period_end
```

**Potential Value**: Notes may contain structured data that could be extracted via NLP

### 6. v_radiation_service_request_notes (Free Text)

**Schema**:
```
patient_fhir_id
service_request_id
sr_intent
sr_status
sr_authored_on
sr_occurrence_date_time
sr_occurrence_period_start
sr_occurrence_period_end
srn_note_text                    -- 📝 FREE TEXT - may contain dose/site/type info
srn_note_time
```

**Potential Value**: Service request notes may contain prescription details

---

## Why Radiation Data is Missing from FHIR

### Root Cause: ARIA System Integration Gap

**ARIA** (Varian's radiation oncology information system) is the source system for:
- Treatment plans
- Dose prescriptions
- Beam configurations
- Fraction schedules
- Treatment sites
- Radiation modality (protons/photons)

**FHIR Integration Status**:
- ❌ ARIA treatment plans NOT mapped to FHIR ServiceRequest with full detail
- ❌ Dose prescriptions NOT in structured FHIR format
- ❌ Site classifications NOT mapped
- ✅ Appointments partially captured (scheduling data only)

**Implication**: Critical radiation therapy data resides in:
1. ARIA system reports (not accessible via FHIR)
2. Radiation oncology clinical notes
3. Treatment summary documents

---

## Recommended Data Extraction Strategy

### Phase 1: Structured Data (CURRENT - Limited)

**Use v_radiation_treatment_courses for**:
- ✅ Radiation therapy yes/no flag (presence of records)
- ✅ Treatment start date (sr_occurrence_period_start)
- ✅ Treatment stop date (sr_occurrence_period_end)
- ⚠️ Treatment duration (end - start)

**Implementation**:
```python
def query_radiation_dates(patient_fhir_id):
    """Extract available structured radiation dates."""
    query = f"""
    SELECT
        sr_occurrence_period_start as radiation_start,
        sr_occurrence_period_end as radiation_stop,
        sr_status,
        sr_requester_display
    FROM fhir_prd_db.v_radiation_treatment_courses
    WHERE patient_fhir_id = '{patient_fhir_id}'
    ORDER BY sr_occurrence_period_start
    """
    return execute_query(query)
```

### Phase 2: Document Extraction (REQUIRED for 80% of fields)

**Target Documents**:
1. **Radiation Oncology Consult Notes** - Initial RT planning
   - Extract: Radiation site (focal/CSI/whole ventricular)
   - Extract: Planned total dose and boost dose
   - Extract: Radiation modality (protons/photons/gamma knife)

2. **Radiation Treatment Summary Notes** - Post-RT completion
   - Extract: Completed dose (may differ from planned)
   - Extract: Number of fractions
   - Extract: Treatment site confirmation

3. **Service Request Notes** (v_radiation_service_request_notes.srn_note_text)
   - Extract: Prescription details from free text
   - Extract: Site and dose from structured notes

4. **Care Plan Notes** (v_radiation_care_plan_notes.cpn_note_text)
   - Extract: Side effect management context
   - May contain dose/site references

**NLP Patterns to Extract**:

**Radiation Site**:
```
- "Focal radiation to tumor bed" → radiation_site = 1 (Focal/Tumor bed)
- "Craniospinal radiation" OR "CSI" → radiation_site = 8 (Craniospinal with focal boost)
- "Whole ventricular radiation" → radiation_site = 9 (Whole ventricular with focal boost)
```

**Radiation Dose**:
```
- "3600 cGy CSI" → total_radiation_dose = 3600, unit = cGy
- "54 Gy focal" → total_radiation_dose_focal = 5400 (convert Gy to cGy)
- "5400 cGy boost" → total_radiation_dose_focal = 5400, unit = cGy
```

**Radiation Type**:
```
- "Proton therapy" → radiation_type = 1 (Protons)
- "Photon radiation" OR "IMRT" OR "3D-CRT" → radiation_type = 2 (Photons)
- "Proton CSI with photon boost" → radiation_type = 3 (Combination)
- "Gamma Knife" → radiation_type = 4 (Gamma Knife)
```

### Phase 3: Validation & Integration

**Cross-Validation Strategy**:
1. Extract dates from structured data (v_radiation_treatment_courses)
2. Extract dose/site/type from documents
3. Validate date ranges match between sources
4. Flag discrepancies for manual review

**Confidence Scoring**:
```python
confidence = {
    'radiation_dates': 0.95,  # High confidence (structured)
    'radiation_site': 0.80,   # Medium-high (document extraction with clear patterns)
    'radiation_dose': 0.85,   # Medium-high (numeric extraction)
    'radiation_type': 0.75    # Medium (terminology variations)
}
```

---

## Gap Analysis Update

### Summary Table

| CBTN Field | Current Status | Extraction Method | Priority |
|------------|---------------|-------------------|----------|
| radiation | ✅ AVAILABLE | STRUCTURED_ONLY | Low (can infer) |
| date_at_radiation_start | ✅ AVAILABLE | STRUCTURED_ONLY | Low (complete) |
| date_at_radiation_stop | ✅ AVAILABLE | STRUCTURED_ONLY | Low (complete) |
| radiation_site | ❌ MISSING | DOCUMENT_ONLY | **HIGH** (critical for outcomes) |
| total_radiation_dose | ❌ MISSING | DOCUMENT_ONLY | **HIGH** (critical for outcomes) |
| total_radiation_dose_unit | ❌ MISSING | DOCUMENT_ONLY | **HIGH** (tied to dose) |
| total_radiation_dose_focal | ❌ MISSING | DOCUMENT_ONLY | **HIGH** (boost dose critical) |
| total_radiation_dose_focal_unit | ❌ MISSING | DOCUMENT_ONLY | **HIGH** (tied to focal dose) |
| radiation_type | ❌ MISSING | DOCUMENT_ONLY | **MEDIUM** (protons vs photons relevant) |
| radiation_type_other | ❌ MISSING | DOCUMENT_ONLY | Low (rarely used) |

### Field Classification Update

**STRUCTURED_ONLY** (2 fields):
- date_at_radiation_start
- date_at_radiation_stop

**DOCUMENT_ONLY** (8 fields):
- radiation_site (**HIGH PRIORITY**)
- total_radiation_dose (**HIGH PRIORITY**)
- total_radiation_dose_unit (**HIGH PRIORITY**)
- total_radiation_dose_focal (**HIGH PRIORITY**)
- total_radiation_dose_focal_unit (**HIGH PRIORITY**)
- radiation_type (MEDIUM priority)
- radiation_site_other (LOW priority)
- radiation_type_other (LOW priority)

---

## Athena Query Agent Enhancement Recommendations

### Current Implementation Status

**Existing Methods** (from athena_query_agent.py):
```python
query_radiation_appointments()           # ✅ Implemented
query_radiation_treatment_courses()      # ✅ Implemented
query_radiation_prescriptions()          # ⚠️ May not exist (no prescription view)
query_radiation_dose_tracking()          # ⚠️ May not exist (no dose tracking view)
query_radiation_beam_configurations()    # ⚠️ May not exist (no beam config view)
query_radiation_treatment_sites()        # ⚠️ May not exist (no site view)
```

### Recommended Updates

**1. Update query_radiation_treatment_courses()** - Add date extraction focus:
```python
def query_radiation_dates(self, patient_fhir_id: str):
    """Extract radiation therapy dates from structured data.

    Returns dict with:
    - radiation_received: bool
    - radiation_start_date: str (ISO format)
    - radiation_stop_date: str (ISO format)
    - treatment_duration_days: int
    - confidence: float (0.95 for structured dates)
    """
    query = f"""
    SELECT
        sr_occurrence_period_start as start_date,
        sr_occurrence_period_end as stop_date,
        sr_status,
        sr_requester_display as ordering_provider
    FROM fhir_prd_db.v_radiation_treatment_courses
    WHERE patient_fhir_id LIKE '%{patient_fhir_id}%'
    ORDER BY sr_occurrence_period_start
    """
    # Execute and return structured response
```

**2. Add document extraction methods**:
```python
def query_radiation_notes(self, patient_fhir_id: str):
    """Extract radiation therapy notes for NLP processing.

    Returns list of notes from:
    - Service request notes (prescriptions)
    - Care plan notes (treatment plans)

    These notes should be passed to Medical Reasoning Agent for dose/site extraction.
    """
    # Query both note views
    # Return concatenated notes with metadata
```

**3. Add validation method**:
```python
def validate_radiation_dates(self, start_date: str, stop_date: str, appointments: list):
    """Cross-validate radiation dates against appointment records.

    Checks:
    - Are appointment dates within start/stop range?
    - Are there gaps suggesting treatment breaks?
    - Do appointment counts suggest complete treatment course?
    """
    # Validation logic
```

---

## Next Steps

### Immediate (Testing - 1 hour)
1. ✅ Document radiation data gaps
2. ⏳ Test radiation date extraction on patient with RT data (eOEaUZ-6f0vYGBS1s8M-hrw3)
3. ⏳ Validate structured date fields are reliable

### Short-Term (Document Extraction - 1 week)
4. ⏳ Implement radiation note extraction from service_request_notes
5. ⏳ Develop NLP patterns for dose/site/type extraction
6. ⏳ Test extraction on sample radiation notes
7. ⏳ Add confidence scoring for extracted fields

### Medium-Term (Full Integration - 2 weeks)
8. ⏳ Integrate radiation document extraction into MasterOrchestrator
9. ⏳ Add cross-validation between structured dates and document dates
10. ⏳ Test on full patient cohort with known radiation therapy

---

## Conclusion

**Critical Finding**: Radiation oncology data in FHIR is severely limited, with only 20% of CBTN required fields available in structured format.

**Root Cause**: ARIA radiation oncology system integration gap - treatment planning and dose data not mapped to FHIR

**Required Action**: Implement DOCUMENT_ONLY extraction for 8/10 radiation fields (80% of requirements)

**Impact**: Without document extraction, radiation therapy data will be incomplete for vast majority of patients

**Priority**: HIGH - Radiation dose and site are critical variables for outcomes analysis in pediatric brain tumor research

---

**Files Referenced**:
- ATHENA_VIEW_CREATION_QUERIES.sql (lines 1398-1558) - Radiation view definitions
- CBTN_DataDictionary_2025-10-15.csv (lines 205-219) - Radiation field requirements
- STRUCTURED_DATA_GAP_ANALYSIS.md (lines 85-97) - Original radiation assessment

**Next Document**: Update STRUCTURED_DATA_GAP_ANALYSIS.md with detailed radiation findings
