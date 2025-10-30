-- Validation: What OIDs are actually used in procedure_code_coding?
WITH production_oids AS (
    SELECT DISTINCT
        code_coding_system as oid_uri,
        COUNT(*) as usage_count
    FROM fhir_prd_db.procedure_code_coding
    WHERE code_coding_system IS NOT NULL
    GROUP BY code_coding_system
)
SELECT
    po.oid_uri as production_oid,
    po.usage_count,

    -- My documentation
    vr.masterfile_code as my_documented_code,
    vr.description as my_documented_description,
    vr.is_verified as my_verification_status,

    -- Validation status
    CASE
        WHEN vr.oid_uri IS NULL THEN '❌ I MISSED THIS'
        WHEN vr.is_verified = FALSE THEN '⚡ I MARKED AS NEEDS VERIFICATION'
        ELSE '✅ I DOCUMENTED THIS CORRECTLY'
    END as validation_result,

    -- For Epic OIDs I missed, decode them
    CASE
        WHEN vr.oid_uri IS NULL AND po.oid_uri LIKE 'urn:oid:1.2.840.114350.1.13.20%' THEN
            'ASCII: ' ||
            REGEXP_EXTRACT(po.oid_uri, '\.(\d{6})(?:\.|$)', 1) ||
            ' = ' ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(po.oid_uri, '\.(\d{6})(?:\.|$)', 1), 1, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(po.oid_uri, '\.(\d{6})(?:\.|$)', 1), 3, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(po.oid_uri, '\.(\d{6})(?:\.|$)', 1), 5, 2) AS INT))
        ELSE NULL
    END as ascii_decode_for_missed

FROM production_oids po
LEFT JOIN fhir_prd_db.v_oid_reference vr ON po.oid_uri = vr.oid_uri
ORDER BY
    CASE
        WHEN vr.oid_uri IS NULL THEN 1  -- Show what I missed first
        WHEN vr.is_verified = FALSE THEN 2
        ELSE 3
    END,
    po.usage_count DESC;
