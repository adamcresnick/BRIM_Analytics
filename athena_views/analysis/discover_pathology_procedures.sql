-- ============================================================================
-- DISCOVERY: Pathology-Related Procedures
-- ============================================================================
-- Purpose: Identify procedures containing pathology/diagnostic information
--          (biopsies, specimen collection, surgical pathology)
--
-- Strategy: Search for pathology CPT codes and keywords in procedure data
-- ============================================================================

-- Query 1: Find all pathology-related procedure codes
SELECT
    pcc.code_coding_code as procedure_code,
    pcc.code_coding_display as procedure_display,
    pcc.code_coding_system as coding_system,
    p.code_text as procedure_name,
    p.category_text as procedure_category,

    COUNT(DISTINCT p.subject_reference) as patient_count,
    COUNT(*) as procedure_count,

    -- Sample status values
    ARRAY_AGG(DISTINCT p.status)[1:5] as sample_status_values,

    -- Sample body sites
    ARRAY_AGG(DISTINCT p.body_site_text)[1:5] as sample_body_sites

FROM fhir_prd_db.procedure p
INNER JOIN fhir_prd_db.procedure_code_coding pcc
    ON p.id = pcc.procedure_id

WHERE
    -- Pathology keywords
    (LOWER(p.code_text) LIKE '%biopsy%'
    OR LOWER(p.code_text) LIKE '%pathology%'
    OR LOWER(p.code_text) LIKE '%frozen section%'
    OR LOWER(p.code_text) LIKE '%specimen%'
    OR LOWER(p.code_text) LIKE '%tissue exam%'
    OR LOWER(p.code_text) LIKE '%histopathology%'
    OR LOWER(p.code_text) LIKE '%cytology%'

    -- Pathology CPT codes (88000-88099 surgical pathology)
    OR pcc.code_coding_code BETWEEN '88000' AND '88099'

    -- Additional pathology CPT codes
    OR pcc.code_coding_code BETWEEN '88300' AND '88399'  -- Surgical pathology

    -- Biopsy CPT codes (brain/CNS specific)
    OR pcc.code_coding_code IN (
        '61140',  -- Burr hole biopsy brain
        '61750',  -- Stereotactic brain biopsy
        '61751',  -- Stereotactic brain biopsy with CT/MRI
        '62269'   -- Spinal cord biopsy
    ))

    AND p.subject_reference IS NOT NULL

GROUP BY 1,2,3,4,5
ORDER BY procedure_count DESC
LIMIT 100;


-- Query 2: Find procedures linked to surgical procedures (pathology during surgery)
-- Look for pathology procedures performed on same day as tumor surgeries
SELECT
    p_surgery.subject_reference as patient_fhir_id,
    p_surgery.id as surgery_id,
    p_surgery.code_text as surgery_name,
    p_surgery.performed_date_time as surgery_datetime,

    p_path.id as pathology_procedure_id,
    p_path.code_text as pathology_procedure_name,
    p_path.performed_date_time as pathology_datetime,
    p_path.status as pathology_status,

    pcc_path.code_coding_code as pathology_cpt_code,

    -- Check timing relationship
    DATE_DIFF('day',
        CAST(p_surgery.performed_date_time AS DATE),
        CAST(p_path.performed_date_time AS DATE)) as days_between

FROM fhir_prd_db.procedure p_surgery
INNER JOIN fhir_prd_db.procedure p_path
    ON p_surgery.subject_reference = p_path.subject_reference
    AND p_surgery.encounter_reference = p_path.encounter_reference
    AND p_surgery.id != p_path.id
LEFT JOIN fhir_prd_db.procedure_code_coding pcc_path
    ON p_path.id = pcc_path.procedure_id

WHERE
    -- Surgery is a tumor resection
    (LOWER(p_surgery.code_text) LIKE '%craniotomy%'
    OR LOWER(p_surgery.code_text) LIKE '%tumor%'
    OR LOWER(p_surgery.code_text) LIKE '%resection%')

    -- Pathology procedure
    AND (LOWER(p_path.code_text) LIKE '%biopsy%'
        OR LOWER(p_path.code_text) LIKE '%pathology%'
        OR LOWER(p_path.code_text) LIKE '%frozen section%'
        OR LOWER(p_path.code_text) LIKE '%specimen%'
        OR pcc_path.code_coding_code BETWEEN '88000' AND '88399')

    AND p_surgery.subject_reference IS NOT NULL

ORDER BY p_surgery.subject_reference, p_surgery.performed_date_time
LIMIT 100;


-- Query 3: Find procedures with specimen linkage
-- Procedures that generated specimens for pathology
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text as procedure_name,
    p.performed_date_time as procedure_datetime,
    p.status as procedure_status,
    p.body_site_text as body_site,

    s.id as specimen_id,
    s.type_text as specimen_type,
    s.collection_body_site_text as specimen_site,
    s.collection_collected_date_time as collection_datetime,
    s.accession_identifier_value as specimen_accession,

    -- Find associated diagnostic reports
    dr.id as diagnostic_report_id,
    dr.code_text as report_type,
    dr.conclusion as report_conclusion

FROM fhir_prd_db.procedure p
INNER JOIN fhir_prd_db.specimen s
    ON REPLACE(p.encounter_reference, 'Encounter/', '') = REPLACE(s.subject_reference, 'Patient/', '')
    -- Assuming specimens collected during same encounter
LEFT JOIN fhir_prd_db.diagnostic_report dr
    ON dr.subject_reference = p.subject_reference
    AND ABS(DATE_DIFF('day',
        CAST(p.performed_date_time AS DATE),
        CAST(dr.effective_date_time AS DATE))) <= 7  -- Within 7 days

WHERE
    (LOWER(s.type_text) LIKE '%tissue%'
    OR LOWER(s.type_text) LIKE '%tumor%'
    OR LOWER(s.type_text) LIKE '%biopsy%'
    OR LOWER(s.type_text) LIKE '%surgical%')

    AND (LOWER(p.code_text) LIKE '%surgery%'
        OR LOWER(p.code_text) LIKE '%resection%'
        OR LOWER(p.code_text) LIKE '%biopsy%'
        OR LOWER(p.code_text) LIKE '%craniotomy%')

    AND p.subject_reference IS NOT NULL

ORDER BY p.subject_reference, p.performed_date_time
LIMIT 100;


-- Query 4: Find intraoperative pathology (frozen section)
-- These are quick pathology assessments during surgery
SELECT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text as procedure_name,
    p.performed_date_time as procedure_datetime,
    p.status,
    p.encounter_reference,

    pcc.code_coding_code as cpt_code,
    pcc.code_coding_display as cpt_display,

    -- Look for associated observations/results
    o.id as observation_id,
    o.code_text as observation_name,
    o.value_string as observation_value,
    o.effective_date_time as observation_datetime

FROM fhir_prd_db.procedure p
LEFT JOIN fhir_prd_db.procedure_code_coding pcc
    ON p.id = pcc.procedure_id
LEFT JOIN fhir_prd_db.observation o
    ON REPLACE(p.encounter_reference, 'Encounter/', '') = REPLACE(o.encounter_reference, 'Encounter/', '')
    AND o.subject_reference = p.subject_reference

WHERE
    -- Frozen section keywords
    (LOWER(p.code_text) LIKE '%frozen%'
    OR LOWER(p.code_text) LIKE '%intraoperative%'
    OR LOWER(p.code_text) LIKE '%rapid%'

    -- Frozen section CPT codes
    OR pcc.code_coding_code IN (
        '88331',  -- Frozen section first specimen
        '88332',  -- Frozen section each additional
        '88333',  -- Frozen section cytology
        '88334'   -- Frozen section cytology each additional
    ))

    AND p.subject_reference IS NOT NULL

ORDER BY p.subject_reference, p.performed_date_time
LIMIT 100;


-- Query 5: Pathology procedure categories and patterns
-- Understand the distribution of pathology procedure types
SELECT
    p.category_text as procedure_category,
    COUNT(DISTINCT p.subject_reference) as patient_count,
    COUNT(*) as procedure_count,
    ARRAY_AGG(DISTINCT p.code_text)[1:20] as sample_procedure_names
FROM fhir_prd_db.procedure p
WHERE
    (LOWER(p.code_text) LIKE '%pathology%'
    OR LOWER(p.code_text) LIKE '%biopsy%'
    OR LOWER(p.code_text) LIKE '%specimen%'
    OR LOWER(p.category_text) LIKE '%pathology%')

    AND p.subject_reference IS NOT NULL

GROUP BY 1
ORDER BY procedure_count DESC
LIMIT 50;
