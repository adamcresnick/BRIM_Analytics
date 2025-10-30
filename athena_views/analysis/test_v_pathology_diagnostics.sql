-- ============================================================================
-- TEST: v_pathology_diagnostics View
-- ============================================================================
-- Purpose: Validate that v_pathology_diagnostics captures pathology data from
--          all expected sources and correctly extracts molecular markers
-- ============================================================================

-- ==========================================================================
-- TEST 1: Count by diagnostic source
-- ==========================================================================
-- Expected: Data from 6 sources (molecular_test, pathology_observation,
--           pathology_procedure, pathology_narrative, care_plan_pathology_note,
--           procedure_pathology_note)

SELECT
    diagnostic_source,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(*) as total_records,
    MIN(diagnostic_date) as earliest_date,
    MAX(diagnostic_date) as latest_date
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY diagnostic_source
ORDER BY total_records DESC;


-- ==========================================================================
-- TEST 2: Count by diagnostic category
-- ==========================================================================
-- Expected: Multiple categories including molecular markers, IHC, histology

SELECT
    diagnostic_category,
    diagnostic_source,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(*) as total_records
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY diagnostic_category, diagnostic_source
ORDER BY total_records DESC
LIMIT 50;


-- ==========================================================================
-- TEST 3: Molecular marker extraction validation
-- ==========================================================================
-- Verify that IDH, MGMT, 1p/19q flags are being set correctly

SELECT
    diagnostic_category,
    diagnostic_source,
    is_idh_mutant,
    is_mgmt_methylated,
    is_1p19q_codeleted,
    COUNT(*) as record_count,
    ARRAY_AGG(DISTINCT diagnostic_name)[1:5] as sample_test_names
FROM fhir_prd_db.v_pathology_diagnostics
WHERE is_idh_mutant IS NOT NULL
   OR is_mgmt_methylated IS NOT NULL
   OR is_1p19q_codeleted IS NOT NULL
GROUP BY 1,2,3,4,5
ORDER BY record_count DESC;


-- ==========================================================================
-- TEST 4: Specimen linkage validation
-- ==========================================================================
-- Check that specimens are being linked correctly

SELECT
    diagnostic_source,
    COUNT(*) as total_records,
    COUNT(DISTINCT specimen_types) as unique_specimen_types,
    COUNT(CASE WHEN specimen_types IS NOT NULL THEN 1 END) as records_with_specimen,
    ROUND(100.0 * COUNT(CASE WHEN specimen_types IS NOT NULL THEN 1 END) / COUNT(*), 2) as pct_with_specimen,
    ARRAY_AGG(DISTINCT specimen_types)[1:10] as sample_specimen_types
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY diagnostic_source
ORDER BY total_records DESC;


-- ==========================================================================
-- TEST 5: Procedure linkage validation
-- ==========================================================================
-- Check that procedures are being linked correctly

SELECT
    diagnostic_source,
    COUNT(*) as total_records,
    COUNT(CASE WHEN linked_procedure_id IS NOT NULL THEN 1 END) as records_with_procedure,
    ROUND(100.0 * COUNT(CASE WHEN linked_procedure_id IS NOT NULL THEN 1 END) / COUNT(*), 2) as pct_with_procedure,
    ARRAY_AGG(DISTINCT linked_procedure_name)[1:10] as sample_procedure_names
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY diagnostic_source
ORDER BY total_records DESC;


-- ==========================================================================
-- TEST 6: Narrative text capture validation
-- ==========================================================================
-- Check that result_value contains actual narrative text

SELECT
    diagnostic_source,
    diagnostic_category,
    COUNT(*) as total_records,
    COUNT(CASE WHEN result_value IS NOT NULL THEN 1 END) as records_with_result,
    ROUND(AVG(LENGTH(result_value)), 0) as avg_result_length,
    MAX(LENGTH(result_value)) as max_result_length,
    -- Sample of short result values (likely structured)
    ARRAY_AGG(DISTINCT result_value)[1:5] as sample_results
FROM fhir_prd_db.v_pathology_diagnostics
WHERE LENGTH(result_value) < 100  -- Short results for review
GROUP BY diagnostic_source, diagnostic_category
ORDER BY total_records DESC
LIMIT 20;


-- ==========================================================================
-- TEST 7: Date coverage analysis
-- ==========================================================================
-- Check temporal distribution of pathology data

SELECT
    EXTRACT(YEAR FROM diagnostic_date) as year,
    diagnostic_source,
    COUNT(DISTINCT patient_fhir_id) as unique_patients,
    COUNT(*) as total_records
FROM fhir_prd_db.v_pathology_diagnostics
WHERE diagnostic_date IS NOT NULL
GROUP BY 1,2
ORDER BY 1 DESC, 3 DESC
LIMIT 50;


-- ==========================================================================
-- TEST 8: Sample records from each source
-- ==========================================================================
-- Review actual data quality from each source

SELECT
    diagnostic_source,
    patient_fhir_id,
    diagnostic_date,
    diagnostic_name,
    component_name,
    LEFT(result_value, 200) as result_sample,  -- First 200 chars
    diagnostic_category,
    test_lab,
    linked_procedure_name
FROM fhir_prd_db.v_pathology_diagnostics
WHERE patient_fhir_id IS NOT NULL
ORDER BY diagnostic_source, diagnostic_date DESC
LIMIT 100;


-- ==========================================================================
-- TEST 9: Compare with molecular_tests materialized table
-- ==========================================================================
-- Verify that molecular_test source matches expectations

WITH
molecular_from_view AS (
    SELECT
        patient_fhir_id,
        source_id as test_id,
        diagnostic_date as test_date
    FROM fhir_prd_db.v_pathology_diagnostics
    WHERE diagnostic_source = 'molecular_test'
),
molecular_from_table AS (
    SELECT
        patient_id as patient_fhir_id,
        test_id,
        CAST(result_datetime AS DATE) as test_date
    FROM fhir_prd_db.molecular_tests
)

SELECT
    'In v_pathology_diagnostics only' as location,
    COUNT(*) as test_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM molecular_from_view v
LEFT JOIN molecular_from_table t
    ON v.test_id = t.test_id
WHERE t.test_id IS NULL

UNION ALL

SELECT
    'In molecular_tests only' as location,
    COUNT(*) as test_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM molecular_from_table t
LEFT JOIN molecular_from_view v
    ON t.test_id = v.test_id
WHERE v.test_id IS NULL

UNION ALL

SELECT
    'In both' as location,
    COUNT(*) as test_count,
    COUNT(DISTINCT t.patient_fhir_id) as patient_count
FROM molecular_from_table t
INNER JOIN molecular_from_view v
    ON t.test_id = v.test_id;


-- ==========================================================================
-- TEST 10: Patient-level summary
-- ==========================================================================
-- Show comprehensive pathology profile for sample patients

WITH patient_pathology_summary AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT diagnostic_source) as source_count,
        COUNT(DISTINCT diagnostic_category) as category_count,
        COUNT(*) as total_diagnostics,
        MIN(diagnostic_date) as first_diagnostic,
        MAX(diagnostic_date) as last_diagnostic,

        -- Molecular marker summary
        MAX(CASE WHEN is_idh_mutant = TRUE THEN 'IDH-mutant' ELSE NULL END) as idh_status,
        MAX(CASE WHEN is_mgmt_methylated = TRUE THEN 'MGMT-methylated' ELSE NULL END) as mgmt_status,
        MAX(CASE WHEN is_1p19q_codeleted = TRUE THEN '1p19q-codeleted' ELSE NULL END) as codeletion_status,

        -- Source distribution
        LISTAGG(DISTINCT diagnostic_source, ', ') WITHIN GROUP (ORDER BY diagnostic_source) as sources_used

    FROM fhir_prd_db.v_pathology_diagnostics
    GROUP BY patient_fhir_id
)

SELECT
    patient_fhir_id,
    source_count,
    category_count,
    total_diagnostics,
    first_diagnostic,
    last_diagnostic,
    idh_status,
    mgmt_status,
    codeletion_status,
    sources_used
FROM patient_pathology_summary
WHERE total_diagnostics >= 5  -- Patients with significant pathology data
ORDER BY total_diagnostics DESC
LIMIT 20;


-- ==========================================================================
-- TEST 11: Narrative extraction effectiveness
-- ==========================================================================
-- Check how many narrative sources contain key molecular markers

SELECT
    diagnostic_source,
    COUNT(*) as total_records,

    -- IDH extraction
    COUNT(CASE WHEN LOWER(result_value) LIKE '%idh%' THEN 1 END) as mentions_idh,
    COUNT(CASE WHEN is_idh_mutant IS NOT NULL THEN 1 END) as extracted_idh,

    -- MGMT extraction
    COUNT(CASE WHEN LOWER(result_value) LIKE '%mgmt%' THEN 1 END) as mentions_mgmt,
    COUNT(CASE WHEN is_mgmt_methylated IS NOT NULL THEN 1 END) as extracted_mgmt,

    -- 1p/19q extraction
    COUNT(CASE WHEN LOWER(result_value) LIKE '%1p%19q%' OR LOWER(result_value) LIKE '%1p/19q%' THEN 1 END) as mentions_1p19q,
    COUNT(CASE WHEN is_1p19q_codeleted IS NOT NULL THEN 1 END) as extracted_1p19q

FROM fhir_prd_db.v_pathology_diagnostics
WHERE diagnostic_source IN ('pathology_narrative', 'care_plan_pathology_note', 'procedure_pathology_note')
GROUP BY diagnostic_source;


-- ==========================================================================
-- TEST 12: Age at diagnostic validation
-- ==========================================================================
-- Verify age calculations are reasonable (pediatric population)

SELECT
    diagnostic_category,
    COUNT(*) as total_records,
    AVG(age_at_diagnostic_years) as avg_age_years,
    MIN(age_at_diagnostic_years) as min_age_years,
    MAX(age_at_diagnostic_years) as max_age_years,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age_at_diagnostic_years) as median_age_years
FROM fhir_prd_db.v_pathology_diagnostics
WHERE age_at_diagnostic_years IS NOT NULL
GROUP BY diagnostic_category
ORDER BY total_records DESC
LIMIT 20;
