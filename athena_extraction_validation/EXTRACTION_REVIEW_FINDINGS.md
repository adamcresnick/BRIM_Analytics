# Extraction Scripts Review: Multi-Table JOINs & Date Fields

**Date:** October 12, 2025  
**Reviewer:** AI Assistant  
**Purpose:** Review all extraction scripts for:
1. Multi-table JOIN provenance (column prefixes)
2. Date field coverage from source schemas

---

## Executive Summary

### ✅ Scripts WITH Proper Prefixes (Column Provenance)
1. **extract_radiation_data.py** - EXCELLENT
   - Uses prefixes: `cp_`, `cpn_`, `cppo_`, `sr_`, `srn_`, `srrc_`, `proc_`, `pcc_`, `pn_`, `doc_`
   - Clear provenance for 8+ source tables
   
2. **extract_all_binary_files_metadata.py** - PARTIAL
   - Has `doc_` prefix for some fields
   - Missing prefixes for: `dc_` (document_reference_content), `de_` (document_reference_context_encounter), `dt_` (document_reference_type_coding), `dcat_` (document_reference_category)

### ⚠️ Scripts MISSING Prefixes (Need Review)
3. **extract_all_medications_metadata.py** - CRITICAL
   - Joins 9 tables: medication_request, medication, medication_request_note, medication_request_reason_code, medication_request_based_on, medication_form_coding, medication_ingredient, care_plan, care_plan_category, care_plan_condition, care_plan_activity
   - NO prefixes used (except care_plan fields have natural prefix)
   - Columns from different tables can have ambiguous provenance

4. **extract_all_procedures_metadata.py** - NEEDS REVIEW
   - Joins 6 tables: procedure, procedure_code_coding, procedure_performer, procedure_reason_code, procedure_note, procedure_focal_device
   - NO prefixes used
   - Some procedure fields vs procedure_code_coding fields are ambiguous

5. **extract_all_encounters_metadata.py** - NEEDS REVIEW
   - Joins appointment + appointment_participant tables
   - Combines encounter + appointment data without clear provenance
   - appointment.csv created separately (good)

6. **extract_all_measurements_metadata.py** - NEEDS REVIEW
   - Joins observation + lab_tests + lab_test_results (via CTEs)
   - NO prefixes distinguishing observation vs lab_test fields

---

## Detailed Analysis by Script

### 1. extract_all_medications_metadata.py ⚠️ CRITICAL

**Status:** NO PREFIXES USED  
**Complexity:** HIGH (9 table JOINs)  
**Row Count:** 1,121 medications

**Tables Joined:**
1. `patient_medications` (view)
2. `medication_request` (mr)
3. `medication_request_note` (aggregated as mn)
4. `medication_request_reason_code` (aggregated as mrr)
5. `medication_request_based_on` (mrb)
6. `medication` (via medication_id)
7. `medication_form_coding` (aggregated as mf)
8. `medication_ingredient` (aggregated as mi)
9. `care_plan` (cp)
10. `care_plan_category` (aggregated as cpc)
11. `care_plan_condition` (aggregated as cpcon)
12. `care_plan_activity` (cpa)

**Current Column Names (Ambiguous):**
- `status` - Which table? medication_request or care_plan?
- `intent` - medication_request or care_plan?
- `period_start`, `period_end` - care_plan only? Or also medication validity?
- `created` - care_plan.created, but what about medication_request.authored_on?

**Recommended Prefixes:**
- `mr_` - medication_request fields
- `med_` - medication resource fields
- `mrn_` - medication_request_note fields
- `mrr_` - medication_request_reason_code fields
- `mrb_` - medication_request_based_on fields
- `mf_` - medication_form_coding fields
- `mi_` - medication_ingredient fields
- `cp_` - care_plan fields (already naturally prefixed in query)
- `cpc_` - care_plan_category fields
- `cpcon_` - care_plan_condition fields
- `cpa_` - care_plan_activity fields

**Date Fields Present:**
✅ `medication_start_date` (medication_request.authored_on)
✅ `validity_period_start` (dispense_request_validity_period_start)
✅ `validity_period_end` (dispense_request_validity_period_end)
✅ `care_plan_period_start`
✅ `care_plan_period_end`

**Date Fields MISSING:**
❌ `medication_request.created` - When was the order created?
❌ `care_plan.created` - When was care plan created?
❌ `medication_request_note` timestamps - When were notes added?

---

### 2. extract_all_procedures_metadata.py ⚠️ NEEDS REVIEW

**Status:** NO PREFIXES USED  
**Complexity:** MEDIUM (6 table JOINs)  
**Row Count:** 72 procedures

**Tables Joined:**
1. `procedure` (parent)
2. `procedure_code_coding` (pcc) - via procedure_id
3. `procedure_performer` (pp) - via procedure_id
4. `procedure_reason_code` (prc) - via procedure_id (aggregated)
5. `procedure_note` (pn) - via procedure_id (aggregated)
6. `procedure_focal_device` (pfd) - via procedure_id (aggregated)

**Current Column Names (Potentially Ambiguous):**
- Fields from procedure table lack prefix
- Fields from procedure_code_coding lack prefix
- Performer, reason_code, notes are aggregated (good)

**Recommended Prefixes:**
- `proc_` - procedure parent table fields
- `pcc_` - procedure_code_coding fields
- `pp_` - procedure_performer fields
- `prc_` - procedure_reason_code fields
- `pn_` - procedure_note fields
- `pfd_` - procedure_focal_device fields

**Date Fields Present:**
✅ `performed_date_time`
✅ `performed_period_start`
✅ `performed_period_end`
✅ `procedure_date` (age calculation field)

**Date Fields Potentially MISSING:**
❓ `procedure_code_coding` timestamp fields?
❓ `procedure_note` timestamp fields (when notes were created)?

---

### 3. extract_all_encounters_metadata.py ⚠️ REVIEW APPOINTMENTS

**Status:** PARTIAL PREFIXES (separate files help)  
**Complexity:** MEDIUM (appointments require JOIN)  
**Row Count:** 999 encounters + 502 appointments

**Tables Used:**
1. `encounter` - main table
2. `encounter_type`, `encounter_reason_code`, `encounter_diagnosis`, `encounter_service_type`, `encounter_location` (child tables, aggregated in Python)
3. `appointment` + `appointment_participant` (JOIN) - separate CSV

**Current Structure:**
- encounters.csv - mostly single table (encounter)
- appointments.csv - JOINs appointment + appointment_participant WITHOUT prefixes

**Recommended for appointments.csv:**
- `appt_` - appointment table fields
- `ap_` - appointment_participant fields

**Date Fields Present (encounters):**
✅ `encounter_date`
✅ `period_start`
✅ `period_end`

**Date Fields Present (appointments):**
✅ `appointment_date`

**Date Fields Potentially MISSING:**
❓ `appointment.created` - When was appointment scheduled?
❓ `appointment_participant.period_start/end` - Participant availability windows?

---

### 4. extract_all_binary_files_metadata.py ⚠️ INCOMPLETE PREFIXES

**Status:** PARTIAL PREFIXES  
**Complexity:** HIGH (5 table LEFT JOINs)  
**Row Count:** 22,127 documents

**Tables Joined:**
1. `document_reference` (dr) - parent
2. `document_reference_content` (dc) - Binary IDs, content type
3. `document_reference_context_encounter` (de) - encounter linkage
4. `document_reference_type_coding` (dt) - document type
5. `document_reference_category` (dcat) - document category

**Current Prefixes:**
✅ `doc_` - Only 1 field (doc_reference_id)

**Missing Prefixes for:**
- `dc_` - document_reference_content fields (binary_id, content_type, url)
- `de_` - document_reference_context_encounter fields (encounter_reference)
- `dt_` - document_reference_type_coding fields (type_coding_code, type_coding_display)
- `dcat_` - document_reference_category fields (category_text)

**Date Fields Present:**
✅ `document_date`
✅ `context_period_start`
✅ `context_period_end`

**Date Fields Potentially MISSING:**
❓ `document_reference.indexed` - When was document indexed into system?

---

### 5. extract_all_measurements_metadata.py ⚠️ NEEDS REVIEW

**Status:** NO PREFIXES USED  
**Complexity:** MEDIUM (3 table JOINs via CTEs)  
**Row Count:** 1,586 measurements

**Tables Joined (via CTEs):**
1. `observation` - vitals, anthropometrics
2. `lab_tests` - lab test metadata
3. `lab_test_results` - lab result values

**Current Column Names:**
- Mixed observation and lab_test fields without distinction
- `measurement_type` and `measurement_name` could be from either source

**Recommended Prefixes:**
- `obs_` - observation table fields
- `lt_` - lab_tests table fields
- `ltr_` - lab_test_results table fields

**Date Fields Present:**
✅ `measurement_date`

**Date Fields Potentially MISSING:**
❓ `observation.issued` - When was result issued?
❓ `lab_test_results.created` - When was result recorded?

---

### 6. extract_all_diagnoses_metadata.py ✅ SINGLE TABLE

**Status:** NO PREFIXES NEEDED  
**Complexity:** LOW (single table)  
**Row Count:** 23 diagnoses

**Tables Used:**
1. `condition` (formerly problem_list_diagnoses) - single table

**Date Fields Present:**
✅ `onset_date_time`
✅ `abatement_date_time`
✅ `recorded_date`

**Date Fields Potentially MISSING:**
❓ None - appears comprehensive

---

### 7. extract_all_imaging_metadata.py ✅ SINGLE TABLE

**Status:** NO PREFIXES NEEDED  
**Complexity:** LOW (single table with Python-side JOINs)  
**Row Count:** 181 imaging studies

**Tables Used:**
1. `diagnostic_report` - main table
2. Child tables joined in Python (not SQL JOIN)

**Date Fields Present:**
✅ `imaging_date`

**Date Fields Potentially MISSING:**
❓ `diagnostic_report.issued` - When was report issued?
❓ `diagnostic_report.effective_period_start/end` - Study timeframe?

---

## Recommendations

### Priority 1: CRITICAL (Multi-Table with Ambiguity)

1. **medications.csv** - Add prefixes for 11 source tables
   - Most complex extraction
   - High ambiguity risk (status, intent, period fields from multiple tables)
   - Recommend full prefix implementation

2. **binary_files.csv** - Complete prefix implementation
   - Already started with `doc_`
   - Add `dc_`, `de_`, `dt_`, `dcat_` for remaining tables

### Priority 2: HIGH (Multi-Table, Lower Ambiguity)

3. **procedures.csv** - Add prefixes for 6 source tables
   - Moderate complexity
   - Some overlap in field names possible

4. **measurements.csv** - Add prefixes distinguishing observation vs lab sources
   - Users need to know if value came from vitals or lab test

### Priority 3: MEDIUM (Separate Files Reduce Risk)

5. **appointments.csv** - Add prefixes for appointment + appointment_participant
   - Lower risk due to limited overlap
   - Still good practice for provenance

### Date Fields: All Scripts

**Add Missing Temporal Fields:**
- `created` / `indexed` timestamps (when data entered system)
- `issued` timestamps (when results released)
- Note timestamps (when clinical notes added)
- Period start/end for participant/encounter windows

---

## Implementation Strategy

1. **Start with radiation_data.py as template** - Already has comprehensive prefixing
2. **Update medications.csv first** - Highest complexity and ambiguity
3. **Update binary_files.csv** - Easy fix, complete existing pattern
4. **Update procedures.csv** - Medium complexity
5. **Update measurements.csv** - Distinguish observation vs lab sources
6. **Update appointments.csv** - Lower priority but good for consistency

7. **Add missing date fields across all scripts** - Parallel effort

---

## Column Naming Convention (From radiation_data.py)

```
Table Name                          → Prefix
─────────────────────────────────────────────
care_plan                           → cp_
care_plan_note                      → cpn_
care_plan_part_of                   → cppo_
service_request                     → sr_
service_request_note                → srn_
service_request_reason_code         → srrc_
procedure                           → proc_
procedure_code_coding               → pcc_
procedure_note                      → pn_
document_reference                  → doc_
document_reference_content          → dc_
document_reference_context_encounter→ de_
document_reference_type_coding      → dt_
medication_request                  → mr_
medication                          → med_
medication_request_note             → mrn_
observation                         → obs_
lab_tests                           → lt_
lab_test_results                    → ltr_
```

---

## Next Steps

1. ✅ Sync with GitHub (COMPLETE)
2. Review this findings document with user
3. Prioritize which scripts to update first
4. Implement prefix changes systematically
5. Re-run extractions for test patient
6. Validate column provenance is clear
7. Update documentation with column naming conventions
