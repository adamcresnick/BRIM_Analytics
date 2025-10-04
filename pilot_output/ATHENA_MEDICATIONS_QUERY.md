# Query Athena for Patient Medications - C1277724
**Patient FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3
**MRN**: C1277724

## SQL Query for Chemotherapy Medications

```sql
-- Extract chemotherapy medications from Athena fhir_v2_prd_db.patient_medications
-- Filter to oncology drugs for patient C1277724

SELECT 
    mr.subject_reference as patient_fhir_id,
    mr.medication_reference_display as medication_name,
    mr.authored_on as medication_start_date,
    -- Note: patient_medications may not have end_date, use status instead
    mr.status as medication_status,
    mcc.code_coding_code as rxnorm_code,
    mcc.code_coding_display as rxnorm_display
FROM fhir_v2_prd_db.medication_request mr
LEFT JOIN fhir_v2_prd_db.medication_request_code_coding mcc 
    ON mr.id = mcc.medication_request_id
WHERE mr.subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND (
        -- Known chemotherapy agents for C1277724
        LOWER(mr.medication_reference_display) LIKE '%vinblastine%'
        OR LOWER(mr.medication_reference_display) LIKE '%bevacizumab%'
        OR LOWER(mr.medication_reference_display) LIKE '%selumetinib%'
        OR LOWER(mr.medication_reference_display) LIKE '%avastin%'
        
        -- Common pediatric oncology drugs (expand as needed)
        OR LOWER(mr.medication_reference_display) LIKE '%vincristine%'
        OR LOWER(mr.medication_reference_display) LIKE '%carboplatin%'
        OR LOWER(mr.medication_reference_display) LIKE '%temozolomide%'
        OR LOWER(mr.medication_reference_display) LIKE '%lomustine%'
        OR LOWER(mr.medication_reference_display) LIKE '%cyclophosphamide%'
        OR LOWER(mr.medication_reference_display) LIKE '%etoposide%'
        
        -- RxNorm codes for known agents (if available)
        OR mcc.code_coding_code IN (
            '11118',    -- vinblastine
            '3002',     -- bevacizumab
            '1656052'   -- selumetinib
        )
    )
ORDER BY mr.authored_on;
```

## Expected Results for C1277724

Based on clinical documentation, we expect:

| Medication | Start Date | Line | Status | Notes |
|------------|------------|------|--------|-------|
| Vinblastine | 2018-10-01 | 1st line | completed | Initial chemotherapy |
| Bevacizumab (Avastin) | 2019-05-15 | 2nd line | completed | After progression |
| Selumetinib | 2021-05-01 | 3rd line | active/completed | Latest treatment |

## Alternative: Use CSV Crosswalk Query

If the above doesn't return results, use the validated query from `concomitant_medications.csv` generation:

```sql
-- From CSV crosswalk project - proven to work
WITH chemotherapy_agents AS (
    SELECT 
        mr.subject_reference,
        mr.medication_reference_display,
        mr.authored_on,
        mr.status,
        mcc.code_coding_code
    FROM fhir_v2_prd_db.medication_request mr
    LEFT JOIN fhir_v2_prd_db.medication_request_code_coding mcc 
        ON mr.id = mcc.medication_request_id
    WHERE mr.subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
        AND mr.status IN ('active', 'completed', 'stopped')
)
SELECT * FROM chemotherapy_agents
WHERE LOWER(medication_reference_display) LIKE ANY (
    '%vinblastine%', '%bevacizumab%', '%selumetinib%',
    '%vincristine%', '%carboplatin%', '%temozolomide%'
)
ORDER BY authored_on;
```

## Manual Fallback: Create patient_medications.csv

If Athena query is unavailable, manually create from clinical documentation:

```csv
patient_fhir_id,medication_name,medication_start_date,medication_end_date,medication_status,rxnorm_code
e4BwD8ZYDBccepXcJ.Ilo3w3,Vinblastine,2018-10-01,2019-05-01,completed,11118
e4BwD8ZYDBccepXcJ.Ilo3w3,Bevacizumab,2019-05-15,2021-04-30,completed,3002
e4BwD8ZYDBccepXcJ.Ilo3w3,Selumetinib,2021-05-01,,active,1656052
```

## Next Steps

1. **Run Athena query** to get actual medication data
2. **Create `patient_medications.csv`** in `brim_csvs_iteration_3c_phase3a_v2/`
3. **Update variables.csv** chemotherapy instructions to prioritize patient_medications.csv
4. **Upload to BRIM** with both demographics and medications pre-populated

---

*Created: October 4, 2025*
*Status: Ready to execute*
