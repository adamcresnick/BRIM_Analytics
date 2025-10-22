# Radiation Views - Critical Issues & Proposed Fixes

## Summary

Two critical radiation views have major data quality issues that make them unusable:

1. **v_radiation_summary** - Empty table (0 records) due to over-restrictive filtering
2. **v_radiation_treatment_appointments** - Contains ALL appointments for ALL patients (not radiation-specific)

## Issue #1: v_radiation_summary - Empty Table

### Problem
- **Current state:** 0 records
- **Expected state:** 684+ patients with radiation data
- **Root cause:** Requires structured ELECT intake forms which only 91 patients (13%) have

### Original Logic
```sql
-- Filters on structured observation data only
WHERE obs_start_date IS NOT NULL  -- Only 91 patients have this
  AND course_1_start_date IS NOT NULL
```

### Solution: Redesign as Data Availability Inventory

Instead of aggregating treatment details that don't exist, show which data sources are available for each patient.

**New output:** One row per patient with radiation data showing:
- Boolean flags: `has_structured_elect_data`, `has_radiation_documents`, `has_care_plans`, etc.
- Source counts: `num_radiation_documents`, `num_treatment_summaries`, `num_consults`
- Temporal coverage: Date ranges from each source
- Quality metrics: `num_data_sources_available`, `data_completeness_score`
- Recommended extraction strategy

**File:** `V_RADIATION_SUMMARY_REDESIGNED.sql`

---

## Issue #2: v_radiation_treatment_appointments - NOT Radiation-Specific

### Problem

**The view name implies radiation appointments but returns ALL appointments with NO filtering.**

### Evidence

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Test patient appointments | 502 | General pediatric visits |
| Appointments mentioning "radiation" | 0 | None |
| Patients in view | 1,855 | ALL patients with appointments |
| Patients with actual radiation data | 91 | From v_radiation_treatments |
| Overlap | 0 | **Complete mismatch** |

### Sample Appointments (Test Patient)

```
WEIGHT CHECK
EARS
2MOS/DOB (2 month well-child visit)
FEVER AND CONGESTION
COUGHING MORE
COLD SYMS EARS
15 MONTH CHECK AND RE CHECK EARS
not walking
FEVER/COUGH/DDM
```

**Conclusion:** These are **pediatric well-child visits**, NOT radiation appointments!

### Original SQL (Broken)

```sql
CREATE OR REPLACE VIEW v_radiation_treatment_appointments AS
SELECT DISTINCT
    ap.participant_actor_reference as patient_fhir_id,
    a.id as appointment_id,
    -- ... other fields ...
FROM fhir_prd_db.appointment a
JOIN fhir_prd_db.appointment_participant ap ON a.id = ap.appointment_id
WHERE ap.participant_actor_reference LIKE 'Patient/%'
ORDER BY a.start;
```

**Problem:** `WHERE` clause only filters for valid patient references - **NO radiation-specific filtering whatsoever**.

### Solution: Multi-Layer Radiation Filtering

The fixed version applies **4 layers of filtering**:

#### Layer 1: Explicit Radiation Service Types
```sql
FROM appointment_service_type
WHERE LOWER(service_type_coding_display) LIKE '%radiation%'
   OR LOWER(service_type_coding_display) LIKE '%rad%onc%'
```

#### Layer 2: Explicit Radiation Appointment Types
```sql
FROM appointment_appointment_type_coding
WHERE LOWER(appointment_type_coding_display) LIKE '%radiation%'
   OR LOWER(appointment_type_coding_display) LIKE '%radiotherapy%'
```

#### Layer 3: Patient Has Radiation Data + Keywords
```sql
-- Patient is in v_radiation_treatments, v_radiation_documents, or v_radiation_care_plan_hierarchy
AND (LOWER(comment) LIKE '%radiation%'
     OR LOWER(description) LIKE '%radiation%'
     OR LOWER(patient_instruction) LIKE '%radiation%')
```

#### Layer 4: Temporal Match with Treatment Dates
```sql
-- Appointment date falls within known radiation treatment dates (±30 days)
AND appointment.start BETWEEN treatment.start_date AND treatment.end_date + 30 days
```

### New Schema Additions

```sql
-- Track how the appointment was identified as radiation-related
radiation_identification_method VARCHAR
  -- Values: 'service_type_radiation', 'appointment_type_radiation',
  --         'patient_with_radiation_data_and_radiation_keyword',
  --         'patient_with_radiation_data_temporal_match'

radiation_service_type VARCHAR
radiation_appointment_type VARCHAR
```

**File:** `V_RADIATION_TREATMENT_APPOINTMENTS_FIXED.sql`

---

## Impact Assessment

### Before Fixes

| View | Records | Patients | Usability |
|------|---------|----------|-----------|
| v_radiation_summary | 0 | 0 | ❌ Unusable (empty) |
| v_radiation_treatment_appointments | Unknown | 1,855 | ❌ Unusable (wrong data) |

### After Fixes

| View | Records | Patients | Usability |
|------|---------|----------|-----------|
| v_radiation_summary | 684+ | 684 | ✅ Useful inventory |
| v_radiation_treatment_appointments | TBD | ~91-568 | ✅ Actual radiation appointments |

---

## Deployment Checklist

### v_radiation_summary

- [ ] Review redesigned SQL
- [ ] Test on sample patients
- [ ] Deploy to Athena (BREAKING CHANGE - update dependent queries)
- [ ] Document schema change
- [ ] Update v_unified_patient_timeline if it references the old schema

### v_radiation_treatment_appointments

- [ ] Review fixed SQL with multi-layer filtering
- [ ] Test on known radiation patients
- [ ] Validate no pediatric appointments leak through
- [ ] Deploy to Athena (BREAKING CHANGE - adds new columns)
- [ ] Update v_radiation_treatments which references this view
- [ ] Update appointment_summary CTE which uses this view

---

## Validation Queries

### v_radiation_summary

```sql
-- Should return 684+ patients
SELECT COUNT(*) FROM v_radiation_summary;

-- Should show diverse extraction strategies
SELECT recommended_extraction_strategy, COUNT(*)
FROM v_radiation_summary
GROUP BY recommended_extraction_strategy;

-- Test patient should show flags correctly
SELECT *
FROM v_radiation_summary
WHERE patient_id = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3';
-- Expected: All flags FALSE (patient has no radiation data)
```

### v_radiation_treatment_appointments

```sql
-- Should return 0 pediatric appointments
SELECT * FROM v_radiation_treatment_appointments
WHERE LOWER(appointment_comment) LIKE '%ear%check%'
   OR LOWER(appointment_comment) LIKE '%well%child%'
   OR LOWER(appointment_comment) LIKE '%fever%';
-- Expected: 0 records

-- Test patient should have 0 appointments (has no radiation data)
SELECT COUNT(*)
FROM v_radiation_treatment_appointments
WHERE patient_fhir_id = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3';
-- Expected: 0

-- Distribution by identification method
SELECT radiation_identification_method, COUNT(*)
FROM v_radiation_treatment_appointments
GROUP BY radiation_identification_method;
```

---

## Recommendations

1. **Deploy both fixes immediately** - Current views are providing misleading data

2. **Audit other radiation views** for similar issues:
   - v_radiation_care_plan_hierarchy (already reviewed - appears OK)
   - v_radiation_documents (already reviewed - appears OK)
   - v_radiation_treatments (already reviewed - comprehensive consolidation)

3. **Update documentation** to clarify:
   - v_radiation_summary is now a **data availability inventory**, not an aggregation
   - v_radiation_treatment_appointments now has **strict radiation-specific filtering**

4. **Consider adding data quality checks** to catch similar issues:
   ```sql
   -- Alert if radiation view contains non-radiation keywords
   SELECT * FROM v_radiation_treatment_appointments
   WHERE LOWER(appointment_comment) LIKE '%well%child%'
      OR LOWER(appointment_comment) LIKE '%vaccination%'
      OR LOWER(appointment_comment) LIKE '%ear%infection%';
   ```

---

## Related Files

- `V_RADIATION_SUMMARY_REDESIGNED.sql` - New data availability inventory
- `V_RADIATION_SUMMARY_REDESIGN_RATIONALE.md` - Detailed redesign explanation
- `V_RADIATION_TREATMENT_APPOINTMENTS_FIXED.sql` - Multi-layer radiation filtering
- `CONSOLIDATED_RADIATION_VIEWS.sql` - v_radiation_treatments and v_radiation_documents (working correctly)
