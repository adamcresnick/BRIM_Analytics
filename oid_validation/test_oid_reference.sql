-- Test v_oid_reference view
SELECT
    masterfile_code,
    oid_source,
    category,
    description,
    oid_uri,
    is_verified
FROM fhir_prd_db.v_oid_reference
WHERE oid_source = 'Epic'
    OR masterfile_code IN ('CPT', 'RxNorm', 'SNOMED CT')
ORDER BY oid_source, category, masterfile_code;
