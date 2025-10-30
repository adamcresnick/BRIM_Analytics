-- ============================================================================
-- Validation: Compare v_oid_reference against actual production OIDs
-- ============================================================================

-- QUERY 1: Find OIDs in production that I MISSED (undocumented)
-- ============================================================================
WITH all_production_oids AS (
    SELECT DISTINCT code_coding_system as oid_uri, 'procedure_code_coding' as source_table
    FROM fhir_prd_db.procedure_code_coding
    WHERE code_coding_system IS NOT NULL

    UNION

    SELECT DISTINCT code_coding_system, 'medication_request_code_coding'
    FROM fhir_prd_db.medication_request_code_coding
    WHERE code_coding_system IS NOT NULL

    UNION

    SELECT DISTINCT code_coding_system, 'condition_code_coding'
    FROM fhir_prd_db.condition_code_coding
    WHERE code_coding_system IS NOT NULL
)
SELECT
    '🔍 DISCOVERY: OIDs in Production I Missed' as validation_check,
    apo.oid_uri,
    apo.source_table,

    -- Try to decode if it's an Epic OID
    CASE
        WHEN apo.oid_uri LIKE 'urn:oid:1.2.840.114350.1.13.20%' THEN
            'Epic CHOP OID - ASCII: ' ||
            REGEXP_EXTRACT(apo.oid_uri, '\.(\d{6})(?:\.|$)', 1) ||
            ' = ' ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(apo.oid_uri, '\.(\d{6})(?:\.|$)', 1), 1, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(apo.oid_uri, '\.(\d{6})(?:\.|$)', 1), 3, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(apo.oid_uri, '\.(\d{6})(?:\.|$)', 1), 5, 2) AS INT))
        ELSE 'Standard OID (non-Epic)'
    END as decoded_hint

FROM all_production_oids apo
LEFT JOIN fhir_prd_db.v_oid_reference vr ON apo.oid_uri = vr.oid_uri
WHERE vr.oid_uri IS NULL
ORDER BY apo.source_table, apo.oid_uri
LIMIT 50;
