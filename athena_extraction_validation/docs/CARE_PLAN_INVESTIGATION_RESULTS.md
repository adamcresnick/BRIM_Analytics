# Care Plan Investigation Results

**Date:** 2025-10-09  
**Patient:** C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

## Summary

✅ **The `fhir_v2_prd_db.care_plan` table EXISTS and contains additional treatment information that should be included in medication extraction.**

## Key Findings

### 1. Care Plan Table Structure

The `care_plan` table contains the following valuable fields:
- `id`: Care plan unique identifier
- `resource_type`: Always "CarePlan"
- `status`: Plan status (completed, active)
- `intent`: Always "plan"
- `title`: Treatment protocol name (e.g., "Bevacizumab, Vinblastine")
- `subject_reference`: Patient FHIR ID
- `subject_display`: Patient name
- `period_start`: Treatment protocol start date
- `created`: Care plan creation timestamp
- `author_reference`: Clinician who created the plan
- `author_display`: Clinician name

### 2. Reference Format

**Important Discovery:** The `medication_request_based_on.based_on_reference` field does NOT use the "CarePlan/" prefix format. Instead, it contains:
- Direct care plan IDs (e.g., `fGOQdyb9lkqd8jcc0zIuW0Obrvz.luzYzGJmcS0n9EOA4`)
- NOT prefixed format (NOT "CarePlan/ID")

### 3. Patient C1277724 Care Plans

Found **4 care plans** for patient C1277724:

| Care Plan ID | Title | Status | Period Start | Created | Author |
|-------------|-------|--------|--------------|---------|--------|
| f8teGuD9PgOt... | Bevacizumab, Vinblastine | completed | 2019-05-30 | 2019-05-28 | Rosanna Pollack, CRNP |
| faHc6CCCw2Um... | Bevacizumab, Vinblastine | completed | 2019-09-05 | 2019-09-04 | Rosanna Pollack, CRNP |
| fGOQdyb9lkqd... | Bevacizumab, Vinblastine | completed | 2019-12-26 | 2019-12-24 | Rosanna Pollack, CRNP |
| f6JQThv-jMDH... | PROTOCOL TEMPLATE | active | 2021-05-20 | 2021-05-20 | Cynthia J Schmus, CRNP |

### 4. Medication Linkages

**276 medication orders** reference these care plans via `medication_request_based_on` table:
- 55 medications linked to care plan `fGOQdyb9lkqd8jcc0zIuW0Obrvz.luzYzGJmcS0n9EOA4` (Bevacizumab, Vinblastine)
- 32 medications linked to care plan `faHc6CCCw2Um-BEIID6qmvqq7AyEbYj.KRNfhW6MipY04` (Bevacizumab, Vinblastine)
- 31 medications linked to care plan `f8teGuD9PgOtKIC3itdhvZc7hZggeSYv1X6-Y4pXOmHY4` (Bevacizumab, Vinblastine)
- 2 medications linked to care plan `erzSRgkgArWfCzTMDec3-wxjiSqv3TIum5VSGBMPwtWU3` (Selumetinib Sulfate)

### 5. Additional Treatment Information from Care Plans

By joining to the `care_plan` table, we can extract:
1. **Formal treatment protocol status** (completed vs active)
2. **Protocol start dates** (period_start) - provides treatment timeline context
3. **Care plan creation dates** (created) - when protocol was established
4. **Authoring clinician** (author_display) - who established the treatment protocol
5. **Patient name** (subject_display) - for validation

## Recommendation

✅ **INCLUDE care_plan table in medication extraction workflow**

### Join Strategy

```sql
LEFT JOIN fhir_v2_prd_db.care_plan cp
    ON mrb.based_on_reference = cp.id
```

### Additional Fields to Extract

Add these columns to the medication staging file:
- `care_plan_id`: Care plan unique identifier
- `care_plan_status`: Treatment protocol status (completed/active)
- `care_plan_period_start`: When treatment protocol started
- `care_plan_created`: When care plan was created
- `care_plan_author`: Clinician who created the protocol

### Expected Impact

- **Enhanced treatment timeline accuracy**: period_start provides formal protocol start dates
- **Better chemotherapy identification**: Care plans explicitly named "Bevacizumab, Vinblastine" confirm chemotherapy orders
- **Improved data quality**: Author information provides audit trail
- **Temporal validation**: Can validate medication dates against care plan dates

## Query Example

```sql
SELECT 
    pm.medication_name,
    pm.rx_norm_codes,
    pm.authored_on,
    mrb.based_on_display,
    cp.id as care_plan_id,
    cp.title as care_plan_title,
    cp.status as care_plan_status,
    cp.period_start as care_plan_start_date,
    cp.created as care_plan_created_date,
    cp.author_display as care_plan_author
FROM fhir_v2_prd_db.patient_medications pm
LEFT JOIN fhir_v2_prd_db.medication_request_based_on mrb
    ON pm.medication_request_id = mrb.medication_request_id
LEFT JOIN fhir_v2_prd_db.care_plan cp
    ON mrb.based_on_reference = cp.id
WHERE pm.patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

## Related Tables

- ✅ `care_plan`: Primary care plan table (validated)
- ❌ No `care_plan_activity` or `care_plan_detail` tables found
- ❌ No other `care_plan_*` related tables exist

## Validation Notes

- Care plan IDs in `based_on_reference` are NOT prefixed with "CarePlan/"
- Direct join using `based_on_reference = care_plan.id` works successfully
- 4 of 5 tested care plan IDs were found in the care_plan table
- All 4 found care plans belong to patient C1277724
- Care plan period_start dates align with documented treatment timeline (2019-2021)

---

**Next Steps:**
1. Update TODO list to include care_plan table in extraction
2. Modify `extract_all_medications_metadata.py` to add care_plan join
3. Add 5 new columns for care plan metadata
4. Validate care plan dates against medication authored_on dates
