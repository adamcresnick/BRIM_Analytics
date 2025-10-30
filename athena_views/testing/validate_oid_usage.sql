-- ============================================================================
-- OID Usage Validation Queries
-- PURPOSE: Discover, validate, and document OIDs used in CHOP FHIR data
-- ============================================================================

-- ============================================================================
-- QUERY 1: Find all undocumented OIDs in procedure_code_coding
-- ============================================================================
WITH procedure_oids AS (
    SELECT DISTINCT
        code_coding_system,
        COUNT(*) as usage_count
    FROM fhir_prd_db.procedure_code_coding
    GROUP BY code_coding_system
)
SELECT
    po.code_coding_system,
    po.usage_count,
    CASE
        WHEN vr.oid_uri IS NULL THEN 'UNDOCUMENTED ⚠️'
        WHEN vr.is_verified = FALSE THEN 'NEEDS VERIFICATION ⚡'
        ELSE 'DOCUMENTED ✓'
    END as documentation_status,
    vr.masterfile_code,
    vr.description,
    vr.technical_notes
FROM procedure_oids po
LEFT JOIN fhir_prd_db.v_oid_reference vr
    ON po.code_coding_system = vr.oid_uri
ORDER BY
    CASE
        WHEN vr.oid_uri IS NULL THEN 1
        WHEN vr.is_verified = FALSE THEN 2
        ELSE 3
    END,
    po.usage_count DESC;

-- ============================================================================
-- QUERY 2: Decode Epic OIDs to masterfile codes (ASCII decoding)
-- ============================================================================
WITH epic_oids AS (
    SELECT DISTINCT
        code_coding_system,
        COUNT(*) as usage_count
    FROM fhir_prd_db.procedure_code_coding
    WHERE code_coding_system LIKE 'urn:oid:1.2.840.114350.1.13.20%'
    GROUP BY code_coding_system
)
SELECT
    code_coding_system,
    usage_count,

    -- Extract ASCII portion (last 6 digits before optional item number)
    REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) as ascii_code,

    -- Decode to masterfile (manual lookup)
    CASE
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '696580'
            THEN 'EAP (Procedure)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '798268'
            THEN 'ORD (Order)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '698288'
            THEN 'ERX (Medication)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '798276'
            THEN 'ORT (Order Type?) - NEEDS VERIFICATION'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '678367'
            THEN 'CSN (Encounter)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '686980'
            THEN 'DEP (Department)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '837982'
            THEN 'SER (Provider)'
        ELSE 'UNKNOWN - DECODE: ' ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1), 1, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1), 3, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1), 5, 2) AS INT))
    END as decoded_masterfile,

    -- Extract item number if present
    REGEXP_EXTRACT(code_coding_system, '\.\d{6}\.(\d+)$', 1) as item_number,

    -- Check if documented in v_oid_reference
    CASE
        WHEN vr.oid_uri IS NOT NULL THEN '✓ Documented'
        ELSE '⚠️ Add to v_oid_reference'
    END as in_reference_table

FROM epic_oids eo
LEFT JOIN fhir_prd_db.v_oid_reference vr ON eo.code_coding_system = vr.oid_uri
ORDER BY usage_count DESC;

-- ============================================================================
-- QUERY 3: Find all OIDs across all FHIR code_coding tables
-- ============================================================================
WITH all_coding_systems AS (
    SELECT 'procedure_code_coding' as table_name, code_coding_system, COUNT(*) as cnt
    FROM fhir_prd_db.procedure_code_coding
    GROUP BY code_coding_system

    UNION ALL

    SELECT 'medication_request_code_coding', code_coding_system, COUNT(*)
    FROM fhir_prd_db.medication_request_code_coding
    GROUP BY code_coding_system

    UNION ALL

    SELECT 'condition_code_coding', code_coding_system, COUNT(*)
    FROM fhir_prd_db.condition_code_coding
    GROUP BY code_coding_system

    UNION ALL

    SELECT 'observation_code_coding', code_coding_system, COUNT(*)
    FROM fhir_prd_db.observation_code_coding
    GROUP BY code_coding_system
)
SELECT
    acs.code_coding_system,
    acs.table_name,
    acs.cnt as usage_count,
    vr.masterfile_code,
    vr.category,
    vr.description,
    CASE
        WHEN vr.oid_uri IS NULL THEN '⚠️ UNDOCUMENTED'
        WHEN vr.is_verified = FALSE THEN '⚡ NEEDS VERIFICATION'
        ELSE '✓ DOCUMENTED'
    END as status
FROM all_coding_systems acs
LEFT JOIN fhir_prd_db.v_oid_reference vr ON acs.code_coding_system = vr.oid_uri
ORDER BY
    CASE WHEN vr.oid_uri IS NULL THEN 1 ELSE 2 END,
    acs.cnt DESC;

-- ============================================================================
-- QUERY 4: Test v_procedures_tumor OID decoding
-- ============================================================================
SELECT
    pcc_code_coding_system,
    pcc_coding_system_code,
    pcc_coding_system_name,
    pcc_coding_system_source,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_procedures_tumor
WHERE pcc_code_coding_system IS NOT NULL
GROUP BY
    pcc_code_coding_system,
    pcc_coding_system_code,
    pcc_coding_system_name,
    pcc_coding_system_source
ORDER BY procedure_count DESC;

-- ============================================================================
-- QUERY 5: Find Epic OIDs with different item numbers
-- ============================================================================
WITH epic_oid_variations AS (
    SELECT
        REGEXP_EXTRACT(code_coding_system, '(urn:oid:1\.2\.840\.114350\.1\.13\.20\.\d\.7\.\d+\.\d{6})', 1) as base_oid,
        code_coding_system as full_oid,
        REGEXP_EXTRACT(code_coding_system, '\.(\d+)$', 1) as item_number,
        COUNT(*) as usage_count
    FROM fhir_prd_db.procedure_code_coding
    WHERE code_coding_system LIKE 'urn:oid:1.2.840.114350.1.13.20%'
    GROUP BY
        REGEXP_EXTRACT(code_coding_system, '(urn:oid:1\.2\.840\.114350\.1\.13\.20\.\d\.7\.\d+\.\d{6})', 1),
        code_coding_system,
        REGEXP_EXTRACT(code_coding_system, '\.(\d+)$', 1)
)
SELECT
    base_oid,
    item_number,
    full_oid,
    usage_count,
    vr.description as documented_description
FROM epic_oid_variations
LEFT JOIN fhir_prd_db.v_oid_reference vr ON full_oid = vr.oid_uri
WHERE base_oid IS NOT NULL
ORDER BY base_oid, CAST(COALESCE(item_number, '0') AS INT);

-- ============================================================================
-- QUERY 6: Sample procedures with OID decoding
-- ============================================================================
SELECT
    patient_fhir_id,
    procedure_date,
    proc_code_text,

    -- Original OID (long, hard to read)
    pcc_code_coding_system,

    -- Decoded OID (short, readable)
    pcc_coding_system_code,
    pcc_coding_system_name,
    pcc_coding_system_source,

    -- Actual code
    pcc_code_coding_code,
    pcc_code_coding_display,

    is_tumor_surgery
FROM fhir_prd_db.v_procedures_tumor
WHERE pcc_code_coding_system IS NOT NULL
ORDER BY procedure_date DESC
LIMIT 100;
