# v_concomitant_medications Fix Summary

## Problem Identified

The `v_concomitant_medications` view was **hardcoding chemotherapy drug definitions** in the SQL, creating a disconnect from the authoritative ChemotherapyFilter used by the Python timeline builder.

### Issues with Current Implementation

```sql
-- CURRENT (INCORRECT): Hardcoded chemotherapy definition
chemotherapy_agents AS (
    SELECT ...
    FROM fhir_prd_db.medication_request mr
    WHERE (
        -- Hardcoded RxNorm codes (only 18 drugs!)
        mcc.code_coding_code IN (
            '82264',   -- Temozolomide
            '6599',    -- Lomustine
            -- ... only 16 more
        )
        OR LOWER(m.code_text) LIKE '%temozolomide%'
        OR LOWER(m.code_text) LIKE '%lomustine%'
        -- ... simple text matching
    )
)
```

**Problems:**
1. **Incomplete**: Only 18 hardcoded drugs vs. comprehensive drugs.csv reference
2. **Out of sync**: Python ChemotherapyFilter uses drugs.csv, rxnorm_code_map.csv, drug_alias.csv
3. **No exclusions**: Doesn't exclude supportive care medications
4. **Maintenance burden**: Two places to update when adding drugs
5. **Inconsistent**: Timeline database shows different chemo events than this view

---

## Solution: Use v_medications as Source of Truth

The fix leverages `v_medications`, which is already populated with chemotherapy medications filtered by the Python ChemotherapyFilter when building the timeline database.

### Key Changes

#### 1. chemotherapy_agents CTE - Pull from v_medications

```sql
-- NEW (CORRECT): Reference v_medications filtered by ChemotherapyFilter
chemotherapy_agents AS (
    SELECT
        patient_fhir_id,
        medication_request_id as medication_fhir_id,
        medication_name,
        rx_norm_codes as rxnorm_cui,
        medication_status as status,
        mr_intent as intent,
        medication_start_date as start_datetime,
        mr_validity_period_end as stop_datetime,
        mr_authored_on as authored_datetime,
        -- ...
    FROM fhir_prd_db.v_medications
    -- v_medications is already filtered to chemotherapy
    WHERE medication_start_date IS NOT NULL
)
```

**Benefits:**
- ✅ Uses the **same chemotherapy definition** as Python code
- ✅ Inherits **time windows** from v_medications (no duplicate date logic)
- ✅ **No hardcoding** of drug lists
- ✅ **Automatically syncs** when ChemotherapyFilter reference files updated

#### 2. all_medications CTE - Get ALL Medications (Unfiltered)

```sql
-- NEW: Pull from raw medication_request to get EVERYTHING
all_medications AS (
    SELECT ...
    FROM fhir_prd_db.medication_request mr
    -- ... full medication logic ...
    WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')
        -- NO DRUG TYPE FILTERING - we want ALL medications
)
```

**Benefits:**
- ✅ Includes **supportive care** medications (antiemetics, steroids, etc.)
- ✅ Includes **antibiotics, pain meds, anticonvulsants** - everything
- ✅ Captures medications that were **filtered out** by ChemotherapyFilter

#### 3. Join Logic - Exclude Only Specific Chemo Medication

```sql
FROM chemotherapy_agents ca
INNER JOIN all_medications am
    ON ca.patient_fhir_id = am.patient_fhir_id
    -- CRITICAL: Exclude the chemotherapy medication itself
    AND ca.medication_fhir_id != am.medication_fhir_id
WHERE
    -- Temporal overlap conditions (unchanged)
```

**Benefits:**
- ✅ Shows **all medications given during chemotherapy**
- ✅ Excludes only the **specific chemo drug** defining the window
- ✅ Supportive care meds now correctly appear as concomitant

---

## What This Fixes

### Before (Incorrect Behavior)

```
Patient receives:
- Temozolomide (chemo) from 2023-01-01 to 2023-01-30
- Ondansetron (antiemetic) from 2023-01-01 to 2023-01-30
- Dexamethasone (steroid) from 2023-01-01 to 2023-01-15

v_concomitant_medications shows:
- Temozolomide chemo window
- Concomitant medications: Ondansetron, Dexamethasone ✅

BUT:

Timeline database built with ChemotherapyFilter:
- Uses drugs.csv which includes 50+ agents
- Excludes supportive care derivatives
- Uses product code mapping
- Different chemo event dates/counts than view!
```

### After (Correct Behavior)

```
Patient receives:
- Temozolomide (chemo) from 2023-01-01 to 2023-01-30
- Ondansetron (antiemetic) from 2023-01-01 to 2023-01-30
- Dexamethasone (steroid) from 2023-01-01 to 2023-01-15

v_medications (filtered by ChemotherapyFilter):
- Temozolomide from 2023-01-01 to 2023-01-30

v_concomitant_medications:
- Uses Temozolomide window from v_medications
- Concomitant medications: Ondansetron, Dexamethasone ✅

Timeline database:
- Same Temozolomide dates as v_medications ✅
- Consistent chemo event counts ✅
```

---

## Implementation Steps

### Step 1: Review the Fix

File: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/v_concomitant_medications_fix.sql`

Review the three key changes:
1. `chemotherapy_agents` CTE pulls from `v_medications`
2. `all_medications` CTE pulls from raw `medication_request` (unfiltered)
3. Join includes `AND ca.medication_fhir_id != am.medication_fhir_id`

### Step 2: Replace in DATETIME_STANDARDIZED_VIEWS.sql

Location: Lines 448-810 in `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql`

Replace the entire `v_concomitant_medications` view definition with the corrected version.

### Step 3: Deploy to Athena

```bash
# Navigate to athena_views directory
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views

# Run the view creation (or deploy via your deployment process)
# This will recreate v_concomitant_medications with the new logic
```

### Step 4: Validate

#### Test 1: Check Chemotherapy Count Consistency

```sql
-- Chemotherapy medications in v_medications
SELECT COUNT(DISTINCT medication_request_id)
FROM fhir_prd_db.v_medications
WHERE patient_fhir_id = 'Patient/your_test_patient';

-- Chemotherapy medications in v_concomitant_medications
SELECT COUNT(DISTINCT chemo_medication_fhir_id)
FROM fhir_prd_db.v_concomitant_medications
WHERE patient_fhir_id = 'Patient/your_test_patient';

-- These should MATCH
```

#### Test 2: Verify Concomitant Medications Include Supportive Care

```sql
-- Should show antiemetics, steroids, antibiotics, etc. during chemo windows
SELECT
    chemo_medication_name,
    chemo_start_datetime,
    chemo_stop_datetime,
    conmed_medication_name,
    conmed_category,
    overlap_type
FROM fhir_prd_db.v_concomitant_medications
WHERE patient_fhir_id = 'Patient/your_test_patient'
ORDER BY chemo_start_datetime, conmed_medication_name;
```

#### Test 3: Verify Chemo Doesn't Appear as Its Own Concomitant

```sql
-- This should return 0 rows
SELECT *
FROM fhir_prd_db.v_concomitant_medications
WHERE chemo_medication_fhir_id = conmed_medication_fhir_id;
```

#### Test 4: Compare with Timeline Database

```python
# In Python, check that v_medications matches timeline DB
import duckdb
import boto3

# Get chemo events from timeline
conn = duckdb.connect('data/timeline.duckdb')
timeline_meds = conn.execute("""
    SELECT event_id, event_date, description
    FROM events
    WHERE patient_id = 'your_test_patient'
        AND event_type = 'Medication'
    ORDER BY event_date
""").fetchdf()

# Get chemo meds from v_medications via Athena
athena = boto3.client('athena')
# ... query v_medications ...

# Compare counts and dates
print(f"Timeline: {len(timeline_meds)} medications")
print(f"v_medications: {len(athena_meds)} medications")
# Should match!
```

---

## Expected Outcomes

### Data Consistency
- ✅ Chemotherapy event counts match between timeline DB and v_concomitant_medications
- ✅ Chemotherapy time windows consistent across Python and SQL
- ✅ No duplicate chemotherapy definitions to maintain

### Functionality
- ✅ Concomitant medications include ALL drugs given during chemo (supportive care, antibiotics, etc.)
- ✅ Chemotherapy drug itself excluded from concomitant list
- ✅ Temporal overlap calculations unchanged

### Maintainability
- ✅ Update ChemotherapyFilter reference CSVs → all systems sync automatically
- ✅ No hardcoded drug lists in SQL
- ✅ Single authoritative source for "what is chemotherapy"

---

## Rollback Plan

If issues arise, the old view definition is preserved at lines 448-810 in the original DATETIME_STANDARDIZED_VIEWS.sql file (before applying this fix).

To rollback:
1. Revert DATETIME_STANDARDIZED_VIEWS.sql to previous version
2. Redeploy the old view definition
3. Investigate discrepancies

---

## Questions?

- **Why not add filtering to all_medications?**
  - Because we want to show ALL medications during chemo, including those filtered out by ChemotherapyFilter (supportive care, etc.)

- **What if v_medications is empty?**
  - Check that the timeline database has been built with ChemotherapyFilter
  - Verify v_medications is populated from the timeline extraction process

- **How do I update the chemotherapy drug list?**
  - Update the CSV files: drugs.csv, drug_alias.csv, rxnorm_code_map.csv
  - Rebuild timeline database with updated ChemotherapyFilter
  - v_concomitant_medications automatically uses new definitions via v_medications

---

## Summary

This fix ensures that `v_concomitant_medications` uses the **same chemotherapy time windows** as defined by the Python ChemotherapyFilter in `v_medications`, while showing **all medications** (including filtered-out supportive care) that overlap with those windows.

The result is **consistency** between Python timeline builder and SQL analytics, **maintainability** through a single source of truth, and **correctness** in concomitant medication identification.
