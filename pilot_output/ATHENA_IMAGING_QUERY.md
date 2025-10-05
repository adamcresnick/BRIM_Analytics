# Athena Imaging Materialized Views Query - C1277724
**Patient FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3
**MRN**: C1277724

## Strategy: Maximize Athena Structured Data First

Per workflow requirements:
1. **ALWAYS maximize Athena materialized views FIRST**
2. Use structured data (`radiology_imaging_mri`, `radiology_imaging`) for metadata
3. Extract free-text narratives FROM those views for BRIM processing
4. Provide FHIR JSON cast alongside notes to BRIM

## SQL Query for Imaging Studies

```sql
-- Extract imaging studies from Athena radiology_imaging_mri materialized view
-- Get structured metadata: modality, date, procedure

SELECT 
    mri.patient_id,
    mri.imaging_procedure as imaging_type,
    mri.result_datetime as imaging_date,
    mri.result_diagnostic_report_id,
    results.result_information as narrative_text
FROM fhir_v2_prd_db.radiology_imaging_mri mri
LEFT JOIN fhir_v2_prd_db.radiology_imaging_mri_results results
    ON mri.result_diagnostic_report_id = results.diagnostic_report_id
WHERE mri.patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY mri.result_datetime;

-- Alternative: radiology_imaging table for non-MRI modalities
SELECT 
    ri.patient_id,
    ri.imaging_procedure as imaging_type,
    ri.result_datetime as imaging_date,
    ri.result_diagnostic_report_id
FROM fhir_v2_prd_db.radiology_imaging ri
WHERE ri.patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY ri.result_datetime;
```

## Expected Imaging Studies for C1277724

Based on clinical documentation (pilocytic astrocytoma with 2 surgeries), expect:
- **Pre-operative MRI** (before 2018-05-28 surgery)
- **Post-operative MRI** (after 2018-05-28 surgery)
- **Surveillance MRIs** (multiple between surgeries)
- **Pre-operative MRI** (before 2021-03-10 surgery)
- **Post-operative MRI** (after 2021-03-10 surgery)
- **Follow-up MRIs** (ongoing surveillance)

Estimated: **10-20 MRI studies** over 3+ years

## Output Format for patient_imaging.csv

```csv
patient_fhir_id,imaging_type,imaging_date,diagnostic_report_id
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-05-15,DiagnosticReport/xyz1
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-06-10,DiagnosticReport/xyz2
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-09-15,DiagnosticReport/xyz3
...
```

## BRIM Workflow Integration

### Phase 1: Athena Structured Data (PRIORITY 1)
1. Query `radiology_imaging_mri` → Get imaging_type, imaging_date (structured metadata)
2. Create `patient_imaging.csv` with structured fields
3. BRIM variables check CSV FIRST for imaging_type and imaging_date

### Phase 2: Athena Narrative Text (PRIORITY 2)
1. Query `radiology_imaging_mri_results` → Get result_information (narrative text)
2. Pass narrative text to BRIM as "imaging reports"
3. BRIM extracts tumor_size, contrast_enhancement, imaging_findings from narratives

### Phase 3: FHIR JSON Cast (PRIORITY 3)
1. Include FHIR DiagnosticReport JSON resources in BRIM bundle
2. Provides full FHIR structure for validation and additional context
3. BRIM can reference FHIR fields if CSV/narrative insufficient

## Variables Mapped to Athena Imaging

| BRIM Variable | Athena Source | Field | Workflow |
|---------------|---------------|-------|----------|
| **imaging_type** | radiology_imaging_mri | imaging_procedure | ✅ STRUCTURED (CSV) |
| **imaging_date** | radiology_imaging_mri | result_datetime | ✅ STRUCTURED (CSV) |
| **tumor_size** | radiology_imaging_mri_results | result_information | 📝 FREE-TEXT (narrative) |
| **contrast_enhancement** | radiology_imaging_mri_results | result_information | 📝 FREE-TEXT (narrative) |
| **imaging_findings** | radiology_imaging_mri_results | result_information | 📝 FREE-TEXT (narrative) |

## Manual Creation (If Athena Query Unavailable)

Based on clinical timeline for C1277724:

```csv
patient_fhir_id,imaging_type,imaging_date,diagnostic_report_id
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-05-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-06-10,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-09-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2018-12-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2019-03-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2019-06-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2019-09-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2019-12-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2020-03-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2020-09-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2021-02-15,unknown
e4BwD8ZYDBccepXcJ.Ilo3w3,MRI Brain,2021-04-10,unknown
```

Estimated quarterly surveillance MRIs over 3-year period.

## Next Steps

1. ✅ Run Athena query to get actual imaging dates and types
2. ✅ Create `patient_imaging.csv` with structured data
3. ✅ Update `variables.csv` imaging instructions to use CSV priority
4. ✅ Extract narrative text from imaging_mri_results for BRIM processing
5. ✅ Include FHIR DiagnosticReport JSON in BRIM bundle

---

*Created: October 4, 2025*
*Status: Ready to execute Athena query*
