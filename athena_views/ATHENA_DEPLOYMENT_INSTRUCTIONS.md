# Athena Radiation Views Deployment Instructions

## File Location
**Source File**: `ATHENA_VIEW_CREATION_QUERIES.sql`

## Important Note
⚠️ **Athena only allows ONE SQL statement at a time**

You must execute each `CREATE OR REPLACE VIEW` statement separately.

---

## Step 1: Drop Old Views (Optional but Recommended)

Execute these DROP statements first to clean up old views:

```sql
DROP VIEW IF EXISTS fhir_prd_db.v_radiation_treatment_courses;
DROP VIEW IF EXISTS fhir_prd_db.v_radiation_care_plan_notes;
DROP VIEW IF EXISTS fhir_prd_db.v_radiation_service_request_notes;
DROP VIEW IF EXISTS fhir_prd_db.v_radiation_service_request_rt_history;
```

**Note**: The following views are preserved (do NOT drop):
- `v_radiation_care_plan_hierarchy` (used for internal linkage)
- `v_radiation_treatment_appointments` (detailed appointment data)

---

## Step 2: Deploy v_radiation_treatments

1. Open `ATHENA_VIEW_CREATION_QUERIES.sql`
2. **Copy lines 1591-1968** (the entire first CREATE OR REPLACE VIEW statement)
   - Start from: `CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_treatments AS`
   - End at: `ORDER BY patient_fhir_id, obs_course_line_number, best_treatment_start_date;`
3. Paste into Athena query editor
4. Execute
5. Wait for success confirmation

---

## Step 3: Deploy v_radiation_documents

1. Open `ATHENA_VIEW_CREATION_QUERIES.sql` (if not already open)
2. **Copy lines 1982-2075** (the entire second CREATE OR REPLACE VIEW statement)
   - Start from: `CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_documents AS`
   - End at: `ORDER BY dr.subject_reference, extraction_priority, dr.date DESC;`
3. Paste into Athena query editor
4. Execute
5. Wait for success confirmation

---

## Step 4: Verify Deployment

Run this query to confirm both views were created:

```sql
SHOW TABLES IN fhir_prd_db LIKE '%radiation%';
```

**Expected Results** (should see these views):
- ✅ `v_radiation_treatments` (NEW)
- ✅ `v_radiation_documents` (NEW)
- ✅ `v_radiation_care_plan_hierarchy` (PRESERVED)
- ✅ `v_radiation_treatment_appointments` (PRESERVED)

**Should NOT see** (if you ran the DROP statements):
- ❌ `v_radiation_treatment_courses` (dropped)
- ❌ `v_radiation_care_plan_notes` (dropped)
- ❌ `v_radiation_service_request_notes` (dropped)
- ❌ `v_radiation_service_request_rt_history` (dropped)

---

## Step 5: Test Views

### Test v_radiation_treatments

```sql
SELECT
    patient_fhir_id,
    data_source_primary,
    obs_dose_value,
    obs_dose_unit,
    obs_radiation_field,
    obs_radiation_site_code,
    best_treatment_start_date,
    best_treatment_stop_date,
    data_quality_score,
    has_structured_dose,
    has_structured_site
FROM fhir_prd_db.v_radiation_treatments
WHERE patient_fhir_id LIKE '%emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3%'
LIMIT 10;
```

### Test v_radiation_documents

```sql
SELECT
    patient_fhir_id,
    doc_type_text,
    doc_description,
    extraction_priority,
    document_category,
    doc_date
FROM fhir_prd_db.v_radiation_documents
WHERE patient_fhir_id LIKE '%emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3%'
ORDER BY extraction_priority, doc_date DESC
LIMIT 10;
```

---

## Troubleshooting

### Error: "Only one sql statement is allowed"
**Cause**: You copied both CREATE VIEW statements together
**Solution**: Copy and execute each statement separately (Step 2, then Step 3)

### Error: "View already exists"
**Cause**: Using CREATE VIEW instead of CREATE OR REPLACE VIEW
**Solution**: The SQL uses CREATE OR REPLACE VIEW, which should work. If you modified it, make sure to use the exact SQL from the file.

### No data returned
**Cause**: May be testing with wrong patient ID
**Solution**: Try these test patient IDs:
- `emVHLbfTGZtwi0Isqq-BDNGVTo1i182MFc5JZ-KXBoRc3` (has 6 radiation documents)
- Search for patients with data:
  ```sql
  SELECT patient_fhir_id, COUNT(*) as record_count
  FROM fhir_prd_db.v_radiation_treatments
  GROUP BY patient_fhir_id
  ORDER BY record_count DESC
  LIMIT 20;
  ```

---

## What Changed

### Old Architecture (6 separate views)
- `v_radiation_treatment_courses` - Only service_request data (1 patient)
- `v_radiation_care_plan_notes` - Care plan notes
- `v_radiation_service_request_notes` - Service request notes
- `v_radiation_service_request_rt_history` - Reason codes
- `v_radiation_care_plan_hierarchy` - Care plan linkage (KEPT)
- `v_radiation_treatment_appointments` - Appointments (KEPT)

### New Architecture (2 consolidated views)
- **`v_radiation_treatments`** - All treatment data with clear provenance
  - Observation data (ELECT intake forms) - ~90 patients with structured dose/site
  - Service request data - Treatment metadata
  - Appointment summary - Scheduling context
  - Care plan summary - Treatment plan linkage
  - Data quality scoring
  - Completeness flags

- **`v_radiation_documents`** - All documents with extraction priorities
  - Document metadata
  - Content URLs
  - Categories and authors
  - Priority scoring (1-5) for NLP extraction workflow

### Coverage Improvement
- **Before**: 20% of CBTN radiation fields (2/10)
- **After**: 60% of CBTN radiation fields (6/10)

---

## Next Steps After Deployment

1. Update `AthenaQueryAgent` with new query methods
2. Update data extraction workflows to use new views
3. Test on full patient cohort
4. Monitor data quality scores
5. Implement document NLP extraction for remaining fields

---

**Deployment Date**: _____________
**Deployed By**: _____________
**Status**: ☐ Complete ☐ Pending ☐ Issues

