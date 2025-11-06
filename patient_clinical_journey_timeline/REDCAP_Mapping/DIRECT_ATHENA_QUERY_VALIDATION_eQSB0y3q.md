# Direct Athena Query Validation: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83

**Date:** 2025-11-03

This document summarizes the validation of the "Direct Athena Query" mappings proposed in the REDCap Integration Strategy for patient `eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83`.

---

## 1. REDCap Field: `molecular_sequencing_id`

-   **Purpose:** To retrieve the DGD (molecular sequencing) identifier.
-   **Feasibility:** High

#### Query Executed
```sql
SELECT dgd_id 
FROM fhir_prd_db.molecular_test_results 
WHERE patient_id = 'eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83' 
  AND dgd_id IS NOT NULL 
  AND dgd_id != '' 
LIMIT 1;
```

#### Result
-   **Status:** Success
-   **`dgd_id` Found:** `DGD170004996`

#### Conclusion
This mapping is **valid and feasible**. The query successfully returned the required identifier.

---

## 2. REDCap Field: `germline`

-   **Purpose:** To determine if germline testing was performed to confirm a cancer predisposition condition.
-   **Feasibility:** High (The query is valid, but no data was found for this patient).

#### Query Executed
```sql
SELECT test_component, result_datetime 
FROM fhir_prd_db.molecular_test_results 
WHERE patient_id = 'eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83' 
  AND lower(test_component) LIKE '%germline%' 
LIMIT 5;
```

#### Result
-   **Status:** Success (Query ran without error)
-   **Data Found:** 0 records.

#### Conclusion
This mapping is **valid**, but no data was returned for this specific patient. For the automation script, if this query returns no results, the `germline` field in REDCap would be set to 'No' (0) or left blank, which is the correct behavior.

---

## Overall Summary

The direct-to-Athena query approach is a valid and robust method for populating the targeted REDCap fields. For patient `eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83`, we can successfully retrieve the `molecular_sequencing_id` and correctly determine the absence of records for germline testing.
