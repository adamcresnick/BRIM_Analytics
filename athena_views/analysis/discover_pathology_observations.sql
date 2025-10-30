-- ============================================================================
-- DISCOVERY: Pathology-Related Observations
-- ============================================================================
-- Purpose: Identify observations containing pathology/diagnostic information
--          beyond molecular testing (IDH, MGMT, histology, WHO grade, etc.)
--
-- Strategy: Search for pathology LOINC codes and keywords in observation data
-- ============================================================================

-- Query 1: Find all LOINC codes related to pathology
-- Look for observations with common pathology patterns
SELECT
    o.code_coding_code as loinc_code,
    o.code_coding_display as loinc_display,
    o.code_text as observation_name,
    o.category_coding_display as category,
    COUNT(DISTINCT o.subject_reference) as patient_count,
    COUNT(*) as observation_count,
    -- Sample values to understand data
    ARRAY_AGG(DISTINCT o.value_string)[1:5] as sample_string_values,
    ARRAY_AGG(DISTINCT o.value_codeable_concept_text)[1:5] as sample_coded_values,
    ARRAY_AGG(DISTINCT o.interpretation_text)[1:5] as sample_interpretations
FROM fhir_prd_db.observation o
WHERE
    -- Pathology-related keywords in observation name
    (LOWER(o.code_text) LIKE '%pathology%'
    OR LOWER(o.code_text) LIKE '%histology%'
    OR LOWER(o.code_text) LIKE '%histologic%'
    OR LOWER(o.code_text) LIKE '%who grade%'
    OR LOWER(o.code_text) LIKE '%tumor grade%'
    OR LOWER(o.code_text) LIKE '%idh%'
    OR LOWER(o.code_text) LIKE '%mgmt%'
    OR LOWER(o.code_text) LIKE '%1p%19q%'
    OR LOWER(o.code_text) LIKE '%chromosome%'
    OR LOWER(o.code_text) LIKE '%molecular%'
    OR LOWER(o.code_text) LIKE '%genetic%'
    OR LOWER(o.code_text) LIKE '%mutation%'
    OR LOWER(o.code_text) LIKE '%methylation%'
    OR LOWER(o.code_text) LIKE '%immunohistochemistry%'
    OR LOWER(o.code_text) LIKE '%ihc%'
    OR LOWER(o.code_text) LIKE '%ki-67%'
    OR LOWER(o.code_text) LIKE '%ki67%'
    OR LOWER(o.code_text) LIKE '%tumor type%'
    OR LOWER(o.code_text) LIKE '%neoplasm%'
    OR LOWER(o.code_text) LIKE '%cancer%')

    -- Or pathology category
    OR LOWER(o.category_coding_display) LIKE '%pathology%'
    OR LOWER(o.category_coding_display) LIKE '%laboratory%'

GROUP BY 1,2,3,4
ORDER BY observation_count DESC
LIMIT 100;


-- Query 2: Find observations linked to surgical procedures
-- These are likely intraoperative or surgical pathology results
SELECT
    o.subject_reference as patient_fhir_id,
    o.id as observation_id,
    o.code_text as observation_name,
    o.value_string,
    o.value_codeable_concept_text,
    o.interpretation_text,
    o.effective_date_time as observation_datetime,
    o.encounter_reference,

    -- Link to procedure if available
    p.id as procedure_id,
    p.code_text as procedure_name,
    p.performed_date_time as procedure_datetime,

    -- Check if observation is within 30 days of procedure
    DATE_DIFF('day',
        CAST(p.performed_date_time AS DATE),
        CAST(o.effective_date_time AS DATE)) as days_from_procedure

FROM fhir_prd_db.observation o
LEFT JOIN fhir_prd_db.procedure p
    ON REPLACE(o.encounter_reference, 'Encounter/', '') = REPLACE(p.encounter_reference, 'Encounter/', '')
    AND o.subject_reference = p.subject_reference
    AND p.code_text LIKE '%SURGICAL%'

WHERE
    (LOWER(o.code_text) LIKE '%pathology%'
    OR LOWER(o.code_text) LIKE '%histology%'
    OR LOWER(o.code_text) LIKE '%tumor%'
    OR LOWER(o.code_text) LIKE '%grade%'
    OR LOWER(o.code_text) LIKE '%molecular%')

    AND o.subject_reference IS NOT NULL

ORDER BY o.subject_reference, o.effective_date_time
LIMIT 100;


-- Query 3: Find common LOINC code patterns
-- Group by LOINC code prefix to identify clusters
SELECT
    SUBSTR(o.code_coding_code, 1, 4) as loinc_prefix,
    COUNT(DISTINCT o.code_coding_code) as unique_codes,
    COUNT(DISTINCT o.subject_reference) as patient_count,
    COUNT(*) as observation_count,
    ARRAY_AGG(DISTINCT o.code_text)[1:10] as sample_test_names
FROM fhir_prd_db.observation o
WHERE
    o.code_coding_system = 'http://loinc.org'
    AND (LOWER(o.code_text) LIKE '%pathology%'
        OR LOWER(o.code_text) LIKE '%histology%'
        OR LOWER(o.code_text) LIKE '%molecular%'
        OR LOWER(o.code_text) LIKE '%tumor%')
GROUP BY 1
ORDER BY observation_count DESC
LIMIT 50;


-- Query 4: Find observations with specimen references
-- Pathology results are often linked to specimens
SELECT
    o.subject_reference as patient_fhir_id,
    o.id as observation_id,
    o.code_text as observation_name,
    o.value_string,
    o.specimen_reference,

    s.id as specimen_id,
    s.type_text as specimen_type,
    s.collection_body_site_text as specimen_site,
    s.collection_collected_date_time as collection_datetime,
    s.accession_identifier_value as specimen_accession,

    o.effective_date_time as observation_datetime

FROM fhir_prd_db.observation o
INNER JOIN fhir_prd_db.specimen s
    ON REPLACE(o.specimen_reference, 'Specimen/', '') = s.id

WHERE
    (LOWER(s.type_text) LIKE '%tissue%'
    OR LOWER(s.type_text) LIKE '%tumor%'
    OR LOWER(s.type_text) LIKE '%biopsy%'
    OR LOWER(s.type_text) LIKE '%surgical%'
    OR LOWER(s.collection_body_site_text) LIKE '%brain%'
    OR LOWER(s.collection_body_site_text) LIKE '%central nervous system%'
    OR LOWER(s.collection_body_site_text) LIKE '%cns%')

ORDER BY o.subject_reference, o.effective_date_time
LIMIT 100;


-- Query 5: Find observations from diagnostic reports (not in molecular_tests)
-- These might be pathology reports separate from molecular testing
SELECT
    dr.subject_reference as patient_fhir_id,
    dr.id as diagnostic_report_id,
    dr.code_text as report_type,
    dr.conclusion as report_conclusion,
    dr.effective_date_time as report_datetime,

    drr.result_display as component_name,
    o.id as observation_id,
    o.code_text as observation_name,
    o.value_string as observation_value,
    o.value_codeable_concept_text as observation_coded_value,

    -- Check if this is part of molecular_tests table
    CASE
        WHEN mt.result_diagnostic_report_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END as in_molecular_tests

FROM fhir_prd_db.diagnostic_report dr
INNER JOIN fhir_prd_db.diagnostic_report_result drr
    ON dr.id = drr.diagnostic_report_id
LEFT JOIN fhir_prd_db.observation o
    ON REPLACE(drr.result_reference, 'Observation/', '') = o.id
LEFT JOIN fhir_prd_db.molecular_tests mt
    ON dr.id = mt.result_diagnostic_report_id

WHERE
    (LOWER(dr.code_text) LIKE '%pathology%'
    OR LOWER(dr.code_text) LIKE '%surgical pathology%'
    OR LOWER(dr.code_text) LIKE '%frozen section%'
    OR LOWER(dr.code_text) LIKE '%cytology%'
    OR LOWER(dr.code_text) LIKE '%histopathology%')

    AND dr.subject_reference IS NOT NULL

ORDER BY dr.subject_reference, dr.effective_date_time
LIMIT 100;
