-- Test OID decoding in updated v_procedures_tumor
SELECT
    -- Original OID (long)
    pcc_code_coding_system,

    -- Decoded OID (short, readable) - NEW COLUMNS
    pcc_coding_system_code,
    pcc_coding_system_name,
    pcc_coding_system_source,

    -- Sample procedure info
    pcc_code_coding_code,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count

FROM fhir_prd_db.v_procedures_tumor
WHERE pcc_code_coding_system IS NOT NULL
GROUP BY
    pcc_code_coding_system,
    pcc_coding_system_code,
    pcc_coding_system_name,
    pcc_coding_system_source,
    pcc_code_coding_code
ORDER BY procedure_count DESC
LIMIT 20;
