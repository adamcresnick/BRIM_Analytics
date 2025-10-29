# Radiation Episode Date Availability Crisis

**Date:** 2025-10-29
**Status:** CRITICAL - Blocks Strategy D Implementation

---

## Executive Summary

Comprehensive analysis reveals **systemic date availability issues** across the FHIR database that severely limit radiation episode detection capabilities.

### Date Coverage Summary

| Resource | Total Records | Records with Dates | Coverage |
|----------|---------------|-------------------|----------|
| **Appointments** | 5,416 | 0 (from base view) | **0%** |
| **Appointments** | 5,416 | 5,416 (from v_appointments) | **100%** ✅ |
| **Encounters** | N/A | 0 | **0%** |
| **Documents** | 4,404 | 0 (doc_date) | **0%** |
| **Documents** | 4,404 | 4,373 (docc_attachment_creation) | **99.3%** ? |
| **Observations** | 95 episodes | 95 with dates | **100%** ✅ |

---

## Detailed Findings

### 1. Appointment Date Issues ✅ SOLVED

**Problem:**
- `v_radiation_treatment_appointments.appointment_start` → ALL NULL
- Root cause: `TRY(CAST(appointment.start AS TIMESTAMP(3)))` fails

**Solution:**
- `v_appointments.appt_start` → 100% coverage
- JOIN radiation appointments to v_appointments for dates

**Status:** ✅ WORKING - Strategy C successfully enriched 78 episodes with 903 appointments

---

### 2. Encounter Date Issues ❌ UNRESOLVED

**Problem:**
- `encounter.period_start` → ALL NULL
- `encounter.period_end` → ALL NULL
- 0 encounters found for radiation patients

**Impact:**
- Cannot use encounter dates as fallback for observation dates
- Cannot link observations → encounters → appointments via encounter_reference

**Status:** ❌ BLOCKED - No workaround identified

---

### 3. Document Date Issues ❌ CRITICAL - BLOCKS STRATEGY D

**Problem Discovered:**
```
total_documents:  4,404
has_doc_date:     0      ← document_reference.date field
has_context_start: 0      ← document_reference.context_period_start
has_context_end:  0      ← document_reference.context_period_end
has_attachment_creation: 4,373  ← document_reference_content.attachment_creation (99.3%)
```

**Root Cause Hypothesis:**
Similar to appointments - the view `v_radiation_documents` may be using `TRY(CAST(...))` on fields that require different processing.

**What We Know:**
1. `docc_attachment_creation` field shows 4,373 non-NULL values (99.3% coverage)
2. This field is VARCHAR and may need special handling (like v_appointments)
3. Query attempts to cast it return NULL (TRY(CAST()) fails)

**What We Don't Know:**
1. The actual format of `docc_attachment_creation` values
2. Whether there's a processed view (like v_appointments) that has working dates
3. Why the base `document_reference` table returns 0 records for radiation patients

---

## Impact on Episode Detection Strategies

| Strategy | Status | Date Dependency | Outcome |
|----------|--------|-----------------|---------|
| **A: Structured Course ID** | ✅ Working | observation dates | 93 patients, 95 episodes |
| **B: Care Plan Periods** | ❌ Insufficient | care_plan.period_start/end | Only 13 plans with dates |
| **C: Appointments** | ✅ Redesigned | v_appointments dates | Metadata enrichment only |
| **D: Document Clustering** | 🚫 **BLOCKED** | document dates | **Cannot implement** |

---

## Observations.effective_date_time - The Only Working Date Source

**Current Reality:**
- Only **93 patients** have structured observations with dates (course_id from ELECT forms)
- These are the ONLY patients for whom we can create high-quality episodes
- Remaining **~600 patients** have no viable date sources for episode detection

**Structured Observation Coverage:**
```sql
SELECT
    COUNT(DISTINCT patient_fhir_id) as patients_with_structured_obs,
    COUNT(DISTINCT CASE WHEN course_id IS NOT NULL THEN patient_fhir_id END) as patients_with_course_id,
    COUNT(DISTINCT CASE WHEN obs_start_date IS NOT NULL THEN patient_fhir_id END) as patients_with_obs_dates
FROM fhir_prd_db.v_radiation_treatments
-- Results: 93 with course_id, 93 with obs_start_date
```

---

## Recommended Next Steps

### Immediate Actions (High Priority)

1. **Investigate v_appointments Success Pattern**
   - Why does v_appointments work when base appointment table doesn't?
   - Can we apply the same pattern to documents and encounters?
   - Review v_appointments SQL to understand date processing logic

2. **Search for Alternative Document Views**
   ```sql
   SELECT table_name
   FROM information_schema.tables
   WHERE table_schema = 'fhir_prd_db'
     AND (table_name LIKE '%document%' OR table_name LIKE '%binary%')
   ORDER BY table_name
   ```

3. **Check v_binary_files View**
   - Documents may be linked through binary content attachments
   - v_binary_files might have processed dates similar to v_appointments

4. **Examine Raw document_reference_content Table**
   ```sql
   SELECT
       content_attachment_creation,
       COUNT(*) as cnt
   FROM fhir_prd_db.document_reference_content
   WHERE content_attachment_creation IS NOT NULL
   GROUP BY content_attachment_creation
   LIMIT 20
   ```

### Medium-Term Solutions

5. **Fix v_radiation_documents View**
   - Apply v_appointments-style date processing to document dates
   - Add fallback date hierarchy similar to medication episodes

6. **Create v_radiation_documents_enhanced**
   - New view with working dates
   - Pattern matching v_appointments successful approach

7. **Document Format Investigation**
   - Use the JSON diagnostics workflow (from your provided context) to analyze:
     - `document_reference_content.attachment_creation` format
     - Why TRY(CAST()) is failing
     - Whether data is in JSON format requiring json_extract()

### Long-Term Architectural Fixes

8. **Standardize Date Processing Across All Views**
   - Create reusable date casting functions
   - Document successful patterns (v_appointments)
   - Apply consistently to encounters, documents, etc.

9. **Build Comprehensive Date Availability Report**
   - Run systematic checks across all FHIR resources
   - Identify pattern: which date fields work vs. fail
   - Root cause analysis of casting failures

---

## Immediate Workaround: Metadata-Only Strategy D

Since we cannot detect episodes from documents without dates, we can still:

**Strategy D Revised: Document Metadata Enrichment**
- Link documents to existing episodes (like Strategy C for appointments)
- Classify documents by extraction_priority tiers
- Provide document counts per episode phase
- Support NLP/LLM optimization goals

**Implementation:**
```sql
-- Link documents to Strategy A episodes
-- Use extraction_priority for NLP targeting
-- No temporal clustering (no dates available)
```

---

## Questions for Data Engineering Team

1. **Why does v_appointments work when base appointment table fails?**
   - What date processing does v_appointments use?
   - Can we see the v_appointments view definition?

2. **Is there a v_documents or v_binary_files view with processed dates?**
   - Similar to how v_appointments fixes appointment dates

3. **What is the actual format of docc_attachment_creation field?**
   - Sample values needed
   - Why does TRY(CAST()) fail?

4. **Why are encounter dates universally NULL?**
   - Is this expected behavior?
   - Are encounters even relevant for radiation workflow?

5. **Can we access the Bulk FHIR export source data?**
   - To understand raw date formats
   - To verify if dates exist upstream

---

## Current Episode Coverage Reality Check

**Patients We CAN Create Episodes For:**
- 93 patients with structured observations (Strategy A)

**Patients We CANNOT Create Episodes For (without dates):**
- ~600 patients with only documents
- ~500 patients with only appointments (metadata enrichment only)
- Unknown number with encounters (all encounters have NULL dates)

**Best Case Scenario (if dates were available):**
- Strategy A: 93 patients ✅
- Strategy D: ~600 patients with documents 🚫 BLOCKED
- **Total Coverage: 93 / 693 patients = 13.4%** ❌

**Current Reality:**
- **Strategy A Only: 93 / 693 patients = 13.4% coverage**

---

## Conclusion

Without fixing the systemic date availability issues, **we can only create episodes for 13.4% of radiation patients**. The remaining 86.6% require:

1. Document date fixes (Strategy D)
2. OR alternative episode detection methods that don't rely on temporal clustering
3. OR acceptance that episodes can only be created for patients with structured ELECT intake form data

This is a **data infrastructure issue**, not a SQL query issue. The resolution requires either:
- Access to views with processed dates (like v_appointments)
- Raw FHIR data access to understand date formats
- Data engineering support to fix date casting across all resources
