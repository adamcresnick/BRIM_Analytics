# v_chemo_medications Enhancement Plan
**Date**: 2025-10-28
**Goal**: Add comprehensive CarePlan metadata from v_medications to v_chemo_medications

## Current Gap Analysis

### Fields in v_medications NOT in v_chemo_medications

#### CarePlan Direct Join Fields (CRITICAL for episode construction)
```sql
-- From v_medications (lines 1437-1455)
cp.id as cp_id,                                    -- ❌ Missing
cp.title as cp_title,                              -- ❌ Missing
cp.status as cp_status,                            -- ❌ Missing
cp.intent as cp_intent,                            -- ❌ Missing
cp.created as cp_created,                          -- ❌ Missing
cp.period_start as cp_period_start,                -- ❌ Missing (CRITICAL!)
cp.period_end as cp_period_end,                    -- ❌ Missing (CRITICAL!)
cp.author_display as cp_author_display,            -- ❌ Missing

-- Care plan categories
cpc.categories_aggregated as cpc_categories_aggregated,  -- ❌ Missing

-- Care plan conditions
cpcon.addresses_aggregated as cpcon_addresses_aggregated,  -- ❌ Missing

-- Care plan activity
cpa.activity_detail_statuses as cpa_activity_detail_statuses,      -- ❌ Missing
cpa.activity_detail_descriptions as cpa_activity_detail_descriptions  -- ❌ Missing
```

#### Additional MedicationRequest Fields
```sql
-- From v_medications (lines 1393-1409)
mr.dispense_request_validity_period_start as mr_validity_period_start,  -- ❌ Missing
mr.status_reason_text as mr_status_reason_text,                        -- ❌ Missing
mr.do_not_perform as mr_do_not_perform,                                -- ❌ Missing
mr.course_of_therapy_type_text as mr_course_of_therapy_type_text,      -- ❌ Missing
mr.dispense_request_initial_fill_duration_value,                       -- ❌ Missing
mr.dispense_request_initial_fill_duration_unit,                        -- ❌ Missing
mr.dispense_request_expected_supply_duration_value,                    -- ❌ Missing
mr.dispense_request_expected_supply_duration_unit,                     -- ❌ Missing
mr.dispense_request_number_of_repeats_allowed,                         -- ❌ Missing
mr.substitution_allowed_boolean,                                       -- ❌ Missing
mr.substitution_reason_text,                                           -- ❌ Missing
mr.prior_prescription_display                                          -- ❌ Missing
```

#### Medication Reason References
```sql
-- From v_medications (lines 1886-1892)
mrrefs.reason_reference_displays as medication_reason  -- ❌ Missing
-- Note: v_chemo_medications has reason_code_text but not reason_reference
```

### Fields in v_chemo_medications NOT in v_medications (Keep These!)

#### Chemotherapy-Specific Classification
```sql
-- Unique to v_chemo_medications (lines 1907-1915)
cmm.chemo_drug_id,                          -- ✅ Keep
cmm.chemo_preferred_name,                   -- ✅ Keep
cmm.chemo_approval_status,                  -- ✅ Keep
cmm.chemo_rxnorm_ingredient,                -- ✅ Keep
cmm.chemo_ncit_code,                        -- ✅ Keep
cmm.chemo_sources,                          -- ✅ Keep
cmm.chemo_drug_category,                    -- ✅ Keep
cmm.chemo_therapeutic_normalized,           -- ✅ Keep
cmm.match_type as rxnorm_match_type         -- ✅ Keep
```

## Enhancement Strategy

### Step 1: Add Missing CTEs

Add these CTEs from v_medications:

```sql
-- CarePlan categories (from v_medications lines 1339-1345)
care_plan_categories AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT category_text, ' | ') WITHIN GROUP (ORDER BY category_text) as categories_aggregated
    FROM fhir_prd_db.care_plan_category
    GROUP BY care_plan_id
),

-- CarePlan conditions (from v_medications lines 1346-1352)
care_plan_conditions AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT addresses_display, ' | ') WITHIN GROUP (ORDER BY addresses_display) as addresses_aggregated
    FROM fhir_prd_db.care_plan_addresses
    GROUP BY care_plan_id
),

-- CarePlan activity (from v_medications lines 1363-1373)
care_plan_activity_agg AS (
    SELECT
        care_plan_id,
        LISTAGG(DISTINCT activity_detail_status, ' | ')
            WITHIN GROUP (ORDER BY activity_detail_status) AS activity_detail_statuses,
        LISTAGG(DISTINCT activity_detail_description, ' | ')
            WITHIN GROUP (ORDER BY activity_detail_description) AS activity_detail_descriptions
    FROM fhir_prd_db.care_plan_activity
    GROUP BY care_plan_id
),

-- Medication reason references (from v_medications lines 1886-1892)
medication_reason_references AS (
    SELECT
        medication_request_id,
        LISTAGG(DISTINCT reason_reference_display, ' | ') WITHIN GROUP (ORDER BY reason_reference_display) AS reason_reference_displays
    FROM fhir_prd_db.medication_request_reason_reference
    GROUP BY medication_request_id
)
```

### Step 2: Modify medication_based_on CTE

Update to include primary_care_plan_id (from v_medications lines 1353-1362):

```sql
medication_based_on AS (
    SELECT
        medication_request_id,
        LISTAGG(DISTINCT based_on_reference, ' | ') WITHIN GROUP (ORDER BY based_on_reference) AS based_on_references,
        LISTAGG(DISTINCT based_on_display, ' | ') WITHIN GROUP (ORDER BY based_on_display) AS based_on_displays,
        MIN(based_on_reference) AS primary_care_plan_id  -- ADD THIS
    FROM fhir_prd_db.medication_request_based_on
    GROUP BY medication_request_id
)
```

### Step 3: Add JOINs in Final SELECT

```sql
-- After existing JOINs, add:
LEFT JOIN fhir_prd_db.care_plan cp ON mbo.primary_care_plan_id = cp.id
LEFT JOIN care_plan_categories cpc ON cp.id = cpc.care_plan_id
LEFT JOIN care_plan_conditions cpcon ON cp.id = cpcon.care_plan_id
LEFT JOIN care_plan_activity_agg cpa ON cp.id = cpa.care_plan_id
LEFT JOIN medication_reason_references mrrefs ON mrrefs.medication_request_id = mr.id
```

### Step 4: Add Fields to SELECT Clause

Insert after existing fields (around line 1970):

```sql
-- Additional MedicationRequest metadata (for completeness)
TRY(CAST(mr.dispense_request_validity_period_start AS TIMESTAMP(3))) as mr_validity_period_start,
mr.status_reason_text as mr_status_reason_text,
mr.do_not_perform as mr_do_not_perform,
mr.course_of_therapy_type_text as mr_course_of_therapy_type_text,
mr.dispense_request_initial_fill_duration_value as mr_dispense_initial_fill_duration_value,
mr.dispense_request_initial_fill_duration_unit as mr_dispense_initial_fill_duration_unit,
mr.dispense_request_expected_supply_duration_value as mr_dispense_expected_supply_duration_value,
mr.dispense_request_expected_supply_duration_unit as mr_dispense_expected_supply_duration_unit,
mr.dispense_request_number_of_repeats_allowed as mr_dispense_number_of_repeats_allowed,
mr.substitution_allowed_boolean as mr_substitution_allowed_boolean,
mr.substitution_reason_text as mr_substitution_reason_text,
mr.prior_prescription_display as mr_prior_prescription_display,

-- Medication reason references
mrrefs.reason_reference_displays as medication_reason_references,

-- CarePlan info (CRITICAL for episode construction)
cp.id as cp_id,
cp.title as cp_title,
cp.status as cp_status,
cp.intent as cp_intent,
TRY(CAST(cp.created AS TIMESTAMP(3))) as cp_created,
TRY(CAST(cp.period_start AS TIMESTAMP(3))) as cp_period_start,
TRY(CAST(cp.period_end AS TIMESTAMP(3))) as cp_period_end,
cp.author_display as cp_author_display,

-- Care plan categories
cpc.categories_aggregated as cpc_categories_aggregated,

-- Care plan conditions
cpcon.addresses_aggregated as cpcon_addresses_aggregated,

-- Care plan activity
cpa.activity_detail_statuses as cpa_activity_detail_statuses,
cpa.activity_detail_descriptions as cpa_activity_detail_descriptions
```

## Field Organization in Enhanced View

### Existing v_chemo_medications fields (keep all)
1. Patient identifiers
2. Medication request identifiers
3. **Chemotherapy classification** (unique to chemo view)
4. Medication details
5. Status and intent
6. Dates (medication_start_date, medication_stop_date)
7. Dosage and route
8. Form and ingredients
9. Clinical context (reason codes, notes)
10. Care plan linkage (basic references)
11. Requester and recorder

### NEW fields to add
12. **Additional MedicationRequest metadata** (dispense details, therapy course)
13. **Medication reason references** (linked conditions)
14. **CarePlan direct fields** (cp_id, cp_title, cp_period_start, cp_period_end, etc.)
15. **CarePlan categories** (treatment type classification)
16. **CarePlan conditions** (what conditions the plan addresses)
17. **CarePlan activities** (treatment activities and their status)

## Benefits of Enhancement

### For Episode Construction
- ✅ Direct access to `cp_period_start` and `cp_period_end` (episode boundaries)
- ✅ Can group medications by `cp_id` (treatment protocol)
- ✅ `cp_title` provides human-readable episode names
- ✅ `cp_status` shows if protocol is active, completed, or cancelled

### For Clinical Analysis
- ✅ `mr_course_of_therapy_type_text` distinguishes acute vs maintenance therapy
- ✅ `cpcon.addresses_aggregated` links medications to specific conditions
- ✅ `cpa.activity_detail_statuses` shows treatment plan progress
- ✅ `medication_reason_references` provides clinical justification

### For Timeline Visualization
- ✅ CarePlan period defines episode span for overlay
- ✅ Individual medication dates show discrete administrations within episode
- ✅ Can show both episode-level and medication-level events

## Implementation Notes

- Total new fields: ~24 fields
- New CTEs: 4 (care_plan_categories, care_plan_conditions, care_plan_activity_agg, medication_reason_references)
- Modified CTEs: 1 (medication_based_on - add primary_care_plan_id)
- New JOINs: 5 (care_plan, 3 aggregated CTEs, reason_references)
- **Backward compatible**: All existing fields preserved, only adding new ones
- **Performance**: LEFT JOINs won't filter data, aggregated CTEs prevent JOIN explosions

## Testing Plan

After implementation:
1. Verify field count (should have ~24 new fields)
2. Query sample patient with CarePlan linkage
3. Verify cp_period_start and cp_period_end populated
4. Check that existing chemotherapy classification fields unchanged
5. Validate against v_medications for consistency
