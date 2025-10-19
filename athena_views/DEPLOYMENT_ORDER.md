# Athena Views Deployment Order

**Date**: 2025-10-19
**Critical**: Views must be deployed in this exact order due to dependencies

---

## Deployment Sequence

### Step 1: Deploy 22 Datetime-Standardized Source Views

**File**: `DATETIME_STANDARDIZED_VIEWS.sql`

Deploy these views in any order (no dependencies on each other):

1. v_patient_demographics
2. v_problem_list_diagnoses
3. v_procedures_tumor
4. v_medications
5. v_imaging
6. v_encounters
7. v_visits_unified
8. v_imaging_corticosteroid_use
9. v_measurements
10. v_binary_files
11. v_molecular_tests
12. v_radiation_treatment_appointments
13. v_radiation_care_plan_hierarchy
14. v_radiation_treatments
15. v_radiation_documents
16. v_hydrocephalus_diagnosis
17. v_hydrocephalus_procedures
18. v_autologous_stem_cell_transplant
19. v_concomitant_medications
20. v_autologous_stem_cell_collection
21. v_ophthalmology_assessments
22. v_audiology_assessments

**DO NOT deploy from this file**:
- ❌ v_diagnoses (deploy from PREREQUISITES instead)
- ❌ v_radiation_summary (deploy from PREREQUISITES instead)

---

### Step 2: Deploy Prerequisite Views

**File**: `V_UNIFIED_TIMELINE_PREREQUISITES.sql`

This file creates 2 views that aggregate/normalize data from Step 1 views:

1. **v_diagnoses** - Pulls from v_problem_list_diagnoses (deployed in Step 1)
2. **v_radiation_summary** - Aggregates v_radiation_treatments (deployed in Step 1)

**Run entire file** - it contains both CREATE statements

**Dependencies**:
- Requires v_problem_list_diagnoses (from Step 1)
- Requires v_radiation_treatments (from Step 1)

---

### Step 3: Deploy Unified Patient Timeline

**File**: `V_UNIFIED_PATIENT_TIMELINE.sql`

Creates the main unified timeline view that pulls from all source views.

**Dependencies**:
- Requires all 22 views from Step 1
- Requires v_diagnoses from Step 2
- Requires v_radiation_summary from Step 2

---

## Why This Order Matters

### Dependency Chain

```
Step 1 Source Views:
  v_problem_list_diagnoses ─┐
  v_radiation_treatments ───┼─→ Step 2 Prerequisite Views:
                            │      v_diagnoses ──────┐
                            └─→    v_radiation_summary ─┼─→ Step 3:
  v_medications ────────────────────────────────────────┤   v_unified_patient_timeline
  v_imaging ────────────────────────────────────────────┤
  v_encounters ─────────────────────────────────────────┤
  [plus 18 more source views] ──────────────────────────┘
```

### What Happens If You Deploy Out of Order

**If you deploy v_diagnoses before v_problem_list_diagnoses**:
```sql
ERROR: Table 'fhir_prd_db.v_problem_list_diagnoses' does not exist
```

**If you deploy v_unified_patient_timeline before v_diagnoses**:
```sql
ERROR: Table 'fhir_prd_db.v_diagnoses' does not exist
```

**If you deploy v_radiation_summary before v_radiation_treatments**:
```sql
ERROR: Table 'fhir_prd_db.v_radiation_treatments' does not exist
```

---

## Deployment Commands

### Extract Individual Views from DATETIME_STANDARDIZED_VIEWS.sql

```bash
# Example: Extract v_patient_demographics
grep -n "^CREATE OR REPLACE VIEW fhir_prd_db.v_patient_demographics" DATETIME_STANDARDIZED_VIEWS.sql
# Note the line number, then extract until next CREATE OR REPLACE VIEW

# Or use sed (example for lines 3957-3970):
sed -n '3957,3970p' DATETIME_STANDARDIZED_VIEWS.sql > /tmp/v_patient_demographics.sql
```

### Deploy to Athena

```bash
# Using AWS CLI
aws athena start-query-execution \
  --profile 343218191717_AWSAdministratorAccess \
  --query-string "$(cat /tmp/v_patient_demographics.sql)" \
  --result-configuration "OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/" \
  --query-execution-context "Database=fhir_prd_db" \
  --region us-east-1
```

Or paste directly into Athena Query Editor.

---

## Validation After Each Step

### After Step 1 (Source Views)

```sql
-- Check all 22 source views exist
SHOW VIEWS IN fhir_prd_db LIKE 'v_%';

-- Should NOT see v_diagnoses or v_radiation_summary yet
-- Should see v_problem_list_diagnoses, v_radiation_treatments, etc.
```

### After Step 2 (Prerequisites)

```sql
-- Verify v_diagnoses exists and has data
SELECT COUNT(*) as row_count,
       COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_diagnoses;

-- Verify v_radiation_summary exists and has data
SELECT COUNT(*) as row_count,
       COUNT(DISTINCT patient_id) as patient_count
FROM fhir_prd_db.v_radiation_summary;
```

### After Step 3 (Unified Timeline)

```sql
-- Verify unified timeline exists and has data
SELECT event_type,
       event_category,
       COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
GROUP BY event_type, event_category
ORDER BY event_count DESC;

-- Test with specific patient
SELECT COUNT(*) as event_count
FROM fhir_prd_db.v_unified_patient_timeline
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3';
-- Should return ~4,100+ events
```

---

## Quick Deployment Script

```bash
#!/bin/bash
# Deploy all views in correct order

PROFILE="343218191717_AWSAdministratorAccess"
S3_OUTPUT="s3://aws-athena-query-results-343218191717-us-east-1/"
DATABASE="fhir_prd_db"
REGION="us-east-1"

echo "Step 1: Deploying 22 source views..."
# Extract and deploy each view from DATETIME_STANDARDIZED_VIEWS.sql
# (Individual commands for each view)

echo "Step 2: Deploying prerequisite views..."
aws athena start-query-execution \
  --profile $PROFILE \
  --query-string "$(cat V_UNIFIED_TIMELINE_PREREQUISITES.sql)" \
  --result-configuration "OutputLocation=$S3_OUTPUT" \
  --query-execution-context "Database=$DATABASE" \
  --region $REGION

# Wait for completion before next step
sleep 30

echo "Step 3: Deploying unified patient timeline..."
aws athena start-query-execution \
  --profile $PROFILE \
  --query-string "$(cat V_UNIFIED_PATIENT_TIMELINE.sql)" \
  --result-configuration "OutputLocation=$S3_OUTPUT" \
  --query-execution-context "Database=$DATABASE" \
  --region $REGION

echo "Deployment complete!"
```

---

## Rollback Plan

If issues arise, rollback in reverse order:

1. **Drop v_unified_patient_timeline** (Step 3)
2. **Drop v_diagnoses and v_radiation_summary** (Step 2)
3. **Restore old source views** (Step 1) - use backup SQL if needed

```sql
-- Rollback commands
DROP VIEW IF EXISTS fhir_prd_db.v_unified_patient_timeline;
DROP VIEW IF EXISTS fhir_prd_db.v_diagnoses;
DROP VIEW IF EXISTS fhir_prd_db.v_radiation_summary;
-- Then restore old source views
```

---

## Summary

✅ **Step 1**: 22 source views (datetime-standardized)
✅ **Step 2**: 2 prerequisite views (v_diagnoses, v_radiation_summary)
✅ **Step 3**: 1 unified timeline view

**Total**: 25 views to deploy

**Time Estimate**: 30-60 minutes (depending on validation between steps)

---

**Last Updated**: 2025-10-19
**Status**: Ready for deployment
