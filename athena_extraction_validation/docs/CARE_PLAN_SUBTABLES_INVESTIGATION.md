# Care Plan Subtables Investigation - Complete Results

**Date:** 2025-10-09  
**Patient:** C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

## Executive Summary

✅ **Found 3 care_plan subtables with valuable treatment information:**
1. **care_plan_activity** - Treatment activity status (4 records)
2. **care_plan_addresses** - Linked conditions (8 records) 
3. **care_plan_category** - Treatment categorization (12 records)

## Complete Care Plan Table Inventory

Found **25 total tables** with "care" or "plan" in the name:

### Care Plan Tables (15)
1. `care_plan` ✅ **Primary table** - 4 records
2. `care_plan_activity` ✅ **Has data** - 4 records
3. `care_plan_addresses` ✅ **Has data** - 8 records  
4. `care_plan_category` ✅ **Has data** - 12 records
5. `care_plan_based_on` - Empty
6. `care_plan_care_team` - Empty
7. `care_plan_contributor` - Not checked
8. `care_plan_goal` - Empty
9. `care_plan_identifier` - Not checked
10. `care_plan_instantiates_canonical` - Empty
11. `care_plan_instantiates_uri` - Not checked
12. `care_plan_note` - Empty
13. `care_plan_part_of` - Not checked
14. `care_plan_replaces` - Not checked
15. `care_plan_supporting_info` - Empty

### Care Team Tables (10)
16-25. `care_team*` tables - Related to care teams, not treatment protocols

## Detailed Findings

### 1. care_plan_activity Table ⭐ HIGH VALUE

**Purpose:** Tracks treatment activity status and details

**Schema Highlights:**
- `activity_detail_status`: Activity status (completed, in-progress)
- `activity_detail_kind`: Type of activity
- `activity_detail_code_*`: Activity coding
- `activity_detail_scheduled_*`: Scheduling details (timing, frequency, duration)
- `activity_detail_product_*`: Product/medication details
- `activity_detail_daily_amount_*`: Daily dosage information
- `activity_detail_quantity_*`: Quantity information
- `activity_detail_description`: Free text description

**Patient C1277724 Data:**
- 4 activity records found
- 3 with status "completed" (for Bevacizumab, Vinblastine protocols)
- 1 with status "in-progress" (for PROTOCOL TEMPLATE)

**Value for Extraction:**
- ✅ Activity status validation (confirms treatment completion)
- ⚠️ Most detail fields are empty in this patient's data
- ⚠️ Scheduling/dosage fields are null

**Recommendation:** Include activity_detail_status for validation, but don't expect detailed scheduling/dosage information.

---

### 2. care_plan_addresses Table ⭐ HIGH VALUE

**Purpose:** Links care plans to specific conditions they address

**Schema:**
- `addresses_reference`: Reference to Condition resource (e.g., "Condition/e...")
- `addresses_display`: Human-readable condition name
- `addresses_type`: Resource type

**Patient C1277724 Data:**
- 8 records found (2 per care plan)
- **Condition 1:** "Pilocytic astrocytoma of cerebellum" (primary diagnosis)
- **Condition 2:** "Encounter for antineoplastic chemotherapy" (treatment indication)

**Value for Extraction:**
- ✅ Confirms diagnosis linkage to treatment protocols
- ✅ Explicitly identifies "antineoplastic chemotherapy" as treatment indication
- ✅ Can join to condition table for additional diagnosis details

**Recommendation:** **INCLUDE** - Provides critical linkage between care plans and cancer diagnosis.

---

### 3. care_plan_category Table ⭐ HIGHEST VALUE

**Purpose:** Categorizes the type of care plan

**Schema:**
- `category_coding`: Structured coding (JSON array)
- `category_text`: Human-readable category

**Patient C1277724 Data:**
- 12 records found (3 categories per care plan)
- **Category 1:** "Treatment Plan" (Epic system code)
- **Category 2:** "Medication Management Plan" (SNOMED CT: 736271009)
- **Category 3:** "ONCOLOGY TREATMENT" (Epic oncology code)

**Example Coding:**
```json
{
  "system": "urn:oid:1.2.840.114350.1.13.20.2.7.4.848076.25050",
  "code": "25050", 
  "display": "Treatment Plan"
}
{
  "system": "urn:oid:2.16.840.1.113883.6.96",
  "code": "736271009",
  "display": "Medication Management Plan"  
}
{
  "system": "urn:oid:1.2.840.114350.1.13.20.2.7.4.726668.30044",
  "code": "30044",
  "display": "ONCOLOGY TREATMENT"
}
```

**Value for Extraction:**
- ✅ **Confirms oncology treatment classification**
- ✅ Provides SNOMED CT codes for medication management
- ✅ Epic system codes for treatment plan type
- ✅ Can be used to filter/validate chemotherapy care plans

**Recommendation:** **INCLUDE** - Essential for confirming oncology/chemotherapy classification.

---

## Extraction Strategy

### Recommended Tables to Join

| Table | Priority | Records | Join Key | Value |
|-------|----------|---------|----------|-------|
| `care_plan` | Required | 4 | based_on_reference = id | Protocol name, dates, author |
| `care_plan_category` | High | 12 | care_plan.id = care_plan_id | ONCOLOGY TREATMENT classification |
| `care_plan_addresses` | High | 8 | care_plan.id = care_plan_id | Diagnosis linkage |
| `care_plan_activity` | Medium | 4 | care_plan.id = care_plan_id | Activity status validation |

### Join Pattern

```sql
-- Base medication query
SELECT 
    pm.*,
    -- Care plan basic info
    cp.id as care_plan_id,
    cp.title as care_plan_title,
    cp.status as care_plan_status,
    cp.period_start as care_plan_period_start,
    cp.created as care_plan_created,
    cp.author_display as care_plan_author,
    -- Category information (aggregated)
    STRING_AGG(DISTINCT cpc.category_text, ' | ') as care_plan_categories,
    -- Diagnosis linkage (aggregated)
    STRING_AGG(DISTINCT cpa.addresses_display, ' | ') as care_plan_addresses,
    -- Activity status
    MAX(cpact.activity_detail_status) as care_plan_activity_status
FROM fhir_v2_prd_db.patient_medications pm
LEFT JOIN fhir_v2_prd_db.medication_request_based_on mrb
    ON pm.medication_request_id = mrb.medication_request_id
LEFT JOIN fhir_v2_prd_db.care_plan cp
    ON mrb.based_on_reference = cp.id
LEFT JOIN fhir_v2_prd_db.care_plan_category cpc
    ON cp.id = cpc.care_plan_id
LEFT JOIN fhir_v2_prd_db.care_plan_addresses cpa
    ON cp.id = cpa.care_plan_id
LEFT JOIN fhir_v2_prd_db.care_plan_activity cpact
    ON cp.id = cpact.care_plan_id
WHERE pm.patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
GROUP BY pm.[all columns], cp.[all columns]
```

### Additional Columns to Extract

Add these columns to medication staging file:

**From care_plan table:**
1. `care_plan_id` - Unique identifier
2. `care_plan_title` - Protocol name (e.g., "Bevacizumab, Vinblastine")
3. `care_plan_status` - completed/active
4. `care_plan_period_start` - Treatment start date
5. `care_plan_created` - Plan creation date
6. `care_plan_author` - Clinician name

**From care_plan_category table (aggregated):**
7. `care_plan_categories` - Pipe-separated categories (e.g., "Treatment Plan | Medication Management Plan | ONCOLOGY TREATMENT")

**From care_plan_addresses table (aggregated):**
8. `care_plan_addresses` - Pipe-separated conditions (e.g., "Pilocytic astrocytoma of cerebellum | Encounter for antineoplastic chemotherapy")

**From care_plan_activity table:**
9. `care_plan_activity_status` - Activity status (completed/in-progress)

### Expected Output

For patient C1277724's 1,001 medications:
- ~276 medications (27.6%) will have care plan linkage
- All linked medications will have:
  - Care plan title: "Bevacizumab, Vinblastine" or "PROTOCOL TEMPLATE"
  - Categories: "ONCOLOGY TREATMENT | Medication Management Plan | Treatment Plan"
  - Addresses: "Pilocytic astrocytoma of cerebellum | Encounter for antineoplastic chemotherapy"
  - Activity status: "completed" or "in-progress"

## Key Insights

1. **Oncology Classification Confirmed**
   - All 4 care plans categorized as "ONCOLOGY TREATMENT"
   - Provides definitive confirmation of chemotherapy protocols

2. **Diagnosis Linkage Explicit**
   - Care plans explicitly linked to "Pilocytic astrocytoma of cerebellum"
   - Treatment indication: "Encounter for antineoplastic chemotherapy"

3. **Treatment Timeline Validated**
   - 3 completed protocols (2019-05-30, 2019-09-05, 2019-12-26)
   - 1 active protocol (2021-05-20)
   - Aligns with documented treatment periods

4. **Limited Detailed Scheduling**
   - Activity table has extensive scheduling schema
   - But fields are mostly empty for this patient
   - Don't expect detailed dose/schedule information from care plan tables

## Comparison with medication_request Tables

| Information | care_plan Tables | medication_request Tables |
|-------------|-----------------|---------------------------|
| Dosing details | ❌ Empty | ✅ In medication_request_note |
| Treatment protocol | ✅ Explicit | ✅ In based_on_display |
| Oncology classification | ✅ Explicit categories | ✅ In reason_code |
| Diagnosis linkage | ✅ Explicit conditions | ✅ In reason_code |
| Timeline | ✅ Protocol level | ✅ Order level |
| Author | ✅ Protocol author | ✅ Order requester |

**Conclusion:** Care plan tables provide **protocol-level** context, while medication_request tables provide **order-level** details. Both are valuable and complementary.

## Final Recommendations

### Tables to Include in Extraction ✅
1. ✅ `care_plan` - Primary protocol information
2. ✅ `care_plan_category` - ONCOLOGY TREATMENT classification
3. ✅ `care_plan_addresses` - Diagnosis linkage
4. ⚠️ `care_plan_activity` - Optional, mainly for status validation

### Tables to Skip ❌
- `care_plan_note` - Empty
- `care_plan_goal` - Empty
- `care_plan_based_on` - Empty
- `care_plan_care_team` - Empty
- `care_plan_supporting_info` - Empty
- Other care_plan_* tables - Not checked or empty

### Total Additional Columns
Add **9 new columns** from care_plan tables (6 required + 3 aggregated)

### Data Quality Notes
- Care plan data is high quality where it exists
- Category coding is consistent across all 4 plans
- Diagnosis linkage is complete (2 conditions per plan)
- Activity scheduling fields are empty (don't rely on them)

---

**Next Steps:**
1. Update extract_all_medications_metadata.py to add 4 care_plan table joins
2. Add 9 new columns for care plan metadata
3. Implement aggregation for multi-value fields (categories, addresses)
4. Document care plan categories for chemotherapy filtering logic

