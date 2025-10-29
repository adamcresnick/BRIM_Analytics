# Radiation Appointment Type CTE Analysis

**Date**: 2025-10-29
**Question**: Should we remove the `radiation_appointment_types` CTE since it returns 0 results?
**Decision**: ✅ **KEEP IT** with added documentation

---

## Investigation Summary

### What We Found

The `appointment_appointment_type_coding` table contains **only HL7 v3-ActCode standard encounter types**:

| Code | Display | Count | Purpose |
|------|---------|-------|---------|
| AMB | Ambulatory | 292,187 (89%) | Outpatient clinic visit |
| IMP | Inpatient Encounter | 34,620 (11%) | Hospital admission |
| EMER | Emergency | 1,856 (<1%) | Emergency department |

**Total records**: 328,663
**Unique appointment types**: 3
**Radiation-specific codes**: 0

### Why This Table Has No Radiation Codes

**HL7 v3-ActCode** defines **encounter types** (WHERE care happened), not **specialty types** (WHAT specialty provided care).

This is similar to the difference between:
- **Encounter type**: "Outpatient visit" (generic)
- **Service type**: "Radiation Oncology Consult" (specialty-specific)

The radiation-specific information is stored in `appointment_service_type.service_type_coding`, which we already capture in the `radiation_service_types` CTE.

### Our Radiation Patients' Appointment Types

All 904 radiation patients have appointments classified by these standard encounter types:
- **Ambulatory (AMB)**: 904 patients (100%)
- **Inpatient (IMP)**: 854 patients (94%)
- **Emergency (EMER)**: 349 patients (39%)

These tell us WHERE appointments occurred, but not that they're radiation-related.

---

## Decision: Keep the CTE

### Reasons to KEEP:

1. **Defensive Programming**
   - If EHR is upgraded and starts populating specialty-specific appointment types, we'll automatically capture them
   - Zero cost for future-proofing

2. **Low Performance Cost**
   - Only 328K rows (small table)
   - Only 3 distinct values (extremely fast)
   - Simple WHERE clause with LIKE

3. **Documentation Value**
   - Shows we investigated this data source
   - Demonstrates due diligence in comprehensive data capture
   - Makes it clear why we're checking multiple sources

4. **Code Symmetry**
   - Mirrors `radiation_service_types` CTE pattern
   - Makes the multi-path filtering logic easier to understand
   - Consistent structure: check service_type, check appointment_type, check keywords, check temporal

5. **OR Logic Design**
   - Part of OR clause: `rst.appointment_id IS NOT NULL OR rat.appointment_id IS NOT NULL OR ...`
   - Returning 0 doesn't break anything - other paths succeed
   - If removed, would need to rewrite WHERE clause logic

6. **Other Tables Don't Have Useful Data**
   - `appointment.appointment_type_text`: Empty for radiation patients
   - `appointment_based_on`: No radiation references
   - This IS the right table to check - just doesn't have radiation codes

### Reasons NOT to Remove:

1. **Minimal savings** - Query cost is negligible
2. **Loss of documentation** - Would lose evidence we checked this source
3. **Future risk** - EHR upgrades could add specialty codes without our knowledge
4. **Code clarity** - Parallel CTE structure is easier to understand than asymmetric logic

---

## Implementation: Added Documentation

Updated both files with clear comments explaining the current state:

```sql
-- ============================================================================
-- Appointment types that indicate radiation treatment
-- NOTE: Currently returns 0 - this table only contains HL7 v3-ActCode
--       encounter types (AMB/IMP/EMER), not specialty-specific types.
--       Kept as defensive check in case future EHR updates add specialty codes.
-- ============================================================================
radiation_appointment_types AS (
    SELECT DISTINCT
        appointment_id,
        appointment_type_coding_display
    FROM fhir_prd_db.appointment_appointment_type_coding
    WHERE LOWER(appointment_type_coding_display) LIKE '%radiation%'
       OR LOWER(appointment_type_coding_display) LIKE '%rad%onc%'
       OR LOWER(appointment_type_coding_display) LIKE '%radiotherapy%'
)
```

This makes it clear to future developers:
- ✅ We checked this data source
- ✅ We know it currently returns 0
- ✅ We're keeping it intentionally, not due to oversight
- ✅ We understand why it returns 0

---

## Current Data Capture Strategy

### Working CTEs (Non-Zero Results):

1. **`radiation_patients`**: 904 patients ✅
   - Source: v_radiation_treatments, documents, care_plan_hierarchy

2. **`radiation_service_types`**: 526 appointments ✅
   - Source: appointment_service_type.service_type_coding JSON
   - Codes: "RAD ONC CONSULT", "INP-RAD ONCE CONSULT"

### Defensive CTE (Zero Results, But Kept):

3. **`radiation_appointment_types`**: 0 appointments ⚠️
   - Source: appointment_appointment_type_coding
   - Currently: Only generic encounter types (AMB/IMP/EMER)
   - Future: Could capture specialty codes if EHR adds them

### Final View Performance:

**Total**: 506 patients, 1,317 appointments

**Breakdown by identification method**:
- 40% (526) - Explicit "RAD ONC CONSULT" service types ✅
- 40% (520) - Radiation keywords in comments/descriptions ✅
- 21% (271) - Temporal matching to treatment windows ✅

---

## Comparison: This vs Bug #7

### Bug #7 (radiation_service_types):
- **Problem**: Searching wrong field (text vs JSON)
- **Impact**: Missing 526 appointments (41% of total)
- **Fix**: Search JSON field with CAST to VARCHAR
- **Result**: 0 → 526 appointments

### radiation_appointment_types:
- **Problem**: None - data doesn't exist in source
- **Impact**: None - no radiation codes to capture
- **Fix**: Not applicable - working as designed
- **Result**: 0 → 0 appointments (expected)

---

## Monitoring Recommendation

**Query to run periodically** (e.g., quarterly) to check if new codes appear:

```sql
SELECT
    appointment_type_coding_code,
    appointment_type_coding_display,
    COUNT(*) as count
FROM fhir_prd_db.appointment_appointment_type_coding
GROUP BY appointment_type_coding_code, appointment_type_coding_display
ORDER BY count DESC;
```

If any new codes appear beyond AMB/IMP/EMER, investigate whether they're radiation-related.

---

## Conclusion

**Keep the CTE** - it's cheap defensive programming that:
- Documents we checked this data source
- Protects against future EHR changes
- Maintains clean code structure
- Costs essentially nothing in performance

**Status**: ✅ **RESOLVED - KEEP AS-IS WITH DOCUMENTATION**

The fact that it returns 0 is **expected and correct** given the current data model. The comment now makes this explicit for future maintainers.

---

## Files Updated

1. ✅ `V_RADIATION_TREATMENT_APPOINTMENTS.sql` - Added comment
2. ✅ `DATETIME_STANDARDIZED_VIEWS.sql` - Added comment
3. ✅ `RADIATION_APPOINTMENT_TYPE_CTE_ANALYSIS.md` - This document
