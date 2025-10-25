# v_unified_patient_timeline Rebuild Assessment

**Date**: 2025-10-25
**Assessment**: Based on recent changes over past 7 days

---

## TL;DR: **YES, v_unified_patient_timeline NEEDS TO BE REBUILT**

### Critical Changes Detected:
✅ **v_radiation_summary** - Fixed patient_id → patient_fhir_id (affects UNION query)
✅ **v_visits_unified** - Timeline updated to use v2.2 (new visit logic)
✅ **V_UNIFIED_PATIENT_TIMELINE.sql** - 5 commits in last 7 days with structural changes

---

## Recent Changes Analysis

### 1. v_unified_patient_timeline SQL File Changes (Last 7 Days)

| Commit | Date | Change Description | Impact |
|--------|------|-------------------|---------|
| **e92e98e** | Oct 23 | Fix v_unified_patient_timeline to use patient_fhir_id instead of patient_id | 🔴 **CRITICAL** - Column name standardization |
| **c110649** | Oct 23 | Implement Enhanced Master Agent with Temporal Validation | ⚠️ **HIGH** - May affect extraction_context JSON |
| **d175598** | Oct 23 | Update unified timeline to use v_visits_unified (v2.2) | 🔴 **CRITICAL** - New visit data source |
| **fa9438d** | Oct 19 | Update unified timeline for datetime-standardized source views | 🔴 **CRITICAL** - TIMESTAMP(3) conversion |
| **52efdfe** | Oct 19 | Fix V_UNIFIED_PATIENT_TIMELINE SQL for Athena/Presto compatibility | ⚠️ **MODERATE** - Syntax fixes |

### 2. Source View Changes (Views that feed into timeline)

| View | Status | Impact on Timeline |
|------|--------|-------------------|
| **v_radiation_summary** | 🔴 **MODIFIED** (3 commits) | Column name change: patient_id → patient_fhir_id |
| **v_visits_unified** | 🔴 **NEW v2.2** | Replaces v_encounters, unified encounter+appointment logic |
| **v_concomitant_medications** | 🟡 **MODIFIED** | Uses v_medications time windows (doesn't directly feed timeline) |
| **v_binary_files** | 🟡 **MODIFIED** | Date fixes (doesn't directly feed timeline) |
| **v_procedures_tumor** | 🟢 **STABLE** | No changes detected |
| **v_imaging** | 🟢 **STABLE** | No changes detected |
| **v_medications** | 🟢 **STABLE** | No changes detected |
| **v_diagnoses** | 🟢 **STABLE** | No changes detected |
| **v_measurements** | 🟢 **STABLE** | No changes detected |
| **v_ophthalmology_assessments** | 🟢 **STABLE** | No changes detected |
| **v_audiology_assessments** | 🟢 **STABLE** | No changes detected |
| **v_molecular_tests** | 🟢 **STABLE** | No changes detected |
| **v_autologous_stem_cell_transplant** | 🟢 **STABLE** | No changes detected |
| **v_imaging_corticosteroid_use** | 🟢 **STABLE** | No changes detected |

---

## Why Rebuild is Required

### Critical Issue #1: v_radiation_summary Column Name Change

**Before (Pre-Oct 19)**:
```sql
-- v_radiation_summary had column: patient_id
SELECT
    vrs.patient_id as patient_fhir_id,  -- Aliased
    ...
FROM v_radiation_summary vrs
```

**After (Oct 19)**:
```sql
-- v_radiation_summary now has: patient_fhir_id
SELECT
    vrs.patient_fhir_id as patient_fhir_id,  -- Direct use
    ...
FROM v_radiation_summary vrs
```

**Impact**: If the underlying v_radiation_summary was updated but v_unified_patient_timeline wasn't, queries will **FAIL** with "column not found: patient_id".

**Resolution**: V_UNIFIED_PATIENT_TIMELINE.sql was updated (commit e92e98e) to use `patient_fhir_id` directly. **Must redeploy to Athena**.

---

### Critical Issue #2: v_visits_unified v2.2

**Before**:
- Timeline used `v_encounters` directly
- Only captured completed encounters

**After (Oct 23, commit d175598)**:
```sql
-- Now uses v_visits_unified which unifies:
-- 1. Encounters (actual visits)
-- 2. Appointments (scheduled visits)
-- 3. No-shows, cancellations, future appointments
```

**Impact**:
- More comprehensive visit tracking
- New `visit_type` field logic
- Different event categorization
- **Timeline query logic completely changed**

**Resolution**: V_UNIFIED_PATIENT_TIMELINE.sql Section 5 rewritten to use v_visits_unified. **Must redeploy to Athena**.

---

### Critical Issue #3: Datetime Standardization

**Before (Pre-Oct 19)**:
- Source views had VARCHAR datetime columns
- Timeline used complex `CAST(CAST(...) AS TIMESTAMP)` logic

**After (Oct 19, commit fa9438d)**:
- Source views standardized to TIMESTAMP(3)
- Timeline simplified to `DATE(timestamp_column)`
- No more nested CAST operations

**Impact**:
- Cleaner SQL
- Better performance
- **Incompatible with old view definitions**

**Resolution**: V_UNIFIED_PATIENT_TIMELINE.sql updated for TIMESTAMP(3) types. **Must redeploy to Athena**.

---

## Deployment Steps Required

### Step 1: Update Prerequisite Views

**File**: `V_UNIFIED_TIMELINE_PREREQUISITES.sql`

```bash
# Deploy prerequisite views first
aws athena start-query-execution \
  --query-string "$(cat athena_views/views/V_UNIFIED_TIMELINE_PREREQUISITES.sql)" \
  --query-execution-context Database=fhir_prd_db \
  --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
  --profile radiant-prod
```

**Creates**:
- v_diagnoses (normalizes v_problem_list_diagnoses)
- v_radiation_summary (aggregates v_radiation_treatments)

**Status**: Last modified Oct 19 (datetime standardization updates)

---

### Step 2: Update Main Timeline View

**File**: `V_UNIFIED_PATIENT_TIMELINE.sql`

```bash
# Deploy main unified timeline view
aws athena start-query-execution \
  --query-string "$(cat athena_views/views/V_UNIFIED_PATIENT_TIMELINE.sql)" \
  --query-execution-context Database=fhir_prd_db \
  --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
  --profile radiant-prod
```

**Creates**: v_unified_patient_timeline (UNION ALL of 13 sources)

**Status**: Last modified Oct 23 (latest version with all fixes)

---

### Step 3: Verify Deployment

```sql
-- Test 1: Check if view exists
SHOW CREATE VIEW fhir_prd_db.v_unified_patient_timeline;

-- Test 2: Count events for test patient
SELECT COUNT(*) FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';

-- Expected: ~1,700+ events

-- Test 3: Verify radiation data uses patient_fhir_id
SELECT event_id, event_type, event_category
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_type = 'Radiation Course'
LIMIT 5;

-- Should return rows if patient has radiation (not fail with column error)

-- Test 4: Verify visits use v_visits_unified
SELECT event_id, event_type, event_category, event_subtype
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND event_type = 'Visit'
LIMIT 10;

-- Should show new visit_type categories: 'Completed Visit', 'Appointment Only', etc.

-- Test 5: Event type distribution
SELECT event_type, COUNT(*) as count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY event_type
ORDER BY count DESC;

-- Should show all 13 event types if patient has comprehensive data
```

---

### Step 4: Rebuild DuckDB Timeline

After Athena deployment, rebuild the DuckDB timeline database:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Update patient ID in build_timeline_database.py if needed
# TEST_PATIENT_ID = "e4BwD8ZYDBccepXcJ.Ilo3w3"

python3 scripts/build_timeline_database.py
```

**This will**:
1. Query updated v_unified_patient_timeline from Athena
2. Apply ChemotherapyFilter to correct medication categorization
3. Compute milestones and temporal context
4. Load into DuckDB data/timeline.duckdb

---

## Risk Assessment

### 🔴 **HIGH RISK if not rebuilt:**

1. **Column Not Found Errors**
   - v_radiation_summary queries will fail with "column 'patient_id' not found"
   - Extraction workflow will crash during radiation data query

2. **Incomplete Visit Data**
   - Missing appointments, no-shows, future visits
   - Temporal context queries return incomplete results

3. **Data Type Mismatches**
   - Old timeline expects VARCHAR datetimes
   - New source views provide TIMESTAMP(3)
   - Potential casting errors or silent data loss

4. **Stale Timeline Data**
   - DuckDB timeline built from old Athena view
   - Extraction uses outdated event categorization
   - Medication classification may be incorrect

---

## Recommended Action Plan

### Immediate (Today):

1. ✅ **Deploy prerequisite views** (V_UNIFIED_TIMELINE_PREREQUISITES.sql)
2. ✅ **Deploy main timeline view** (V_UNIFIED_PATIENT_TIMELINE.sql)
3. ✅ **Run validation queries** (verify radiation, visits work)

### After Successful Deployment:

4. ✅ **Rebuild DuckDB timeline** for test patients
5. ✅ **Test extraction workflow** with new timeline
6. ✅ **Document changes** in session notes

### Timeline:
- **Deployment**: 15-30 minutes (Athena view creation)
- **DuckDB Rebuild**: 5-10 minutes per patient
- **Validation**: 10-15 minutes
- **Total**: ~45-60 minutes

---

## Files to Deploy (in order)

1. `athena_views/views/V_UNIFIED_TIMELINE_PREREQUISITES.sql` (168 lines)
2. `athena_views/views/V_UNIFIED_PATIENT_TIMELINE.sql` (1,096 lines)

---

## Post-Deployment Validation Checklist

- [ ] v_diagnoses view exists
- [ ] v_radiation_summary view exists
- [ ] v_unified_patient_timeline view exists
- [ ] Test query returns ~1,700 events for e4BwD8ZYDBccepXcJ.Ilo3w3
- [ ] Radiation events query succeeds (no column errors)
- [ ] Visit events show new categories (Completed Visit, Appointment Only, etc.)
- [ ] DuckDB timeline rebuilt with new data
- [ ] Extraction workflow runs without errors
- [ ] Event counts match expectations

---

## Summary

**Status**: 🔴 **REBUILD REQUIRED**

**Reason**:
- 5 commits to V_UNIFIED_PATIENT_TIMELINE.sql in last 7 days
- 2 critical source view changes (v_radiation_summary, v_visits_unified)
- Column name standardization (patient_id → patient_fhir_id)
- Datetime type standardization (VARCHAR → TIMESTAMP(3))

**Impact**:
- Current Athena timeline view is **out of sync** with code
- DuckDB timeline may have **stale/incorrect data**
- Extraction workflow may **fail or produce incomplete results**

**Action**: Deploy updated views to Athena, then rebuild DuckDB timeline

**Risk Level**: 🔴 **HIGH** - Workflow will fail without rebuild
