-- ================================================================================
-- v_chemo_medications: Comprehensive Chemotherapy Medication View
-- ================================================================================
-- Purpose: Identifies ALL chemotherapy medications from FHIR medication_request
--          data using the comprehensive RADIANT unified chemotherapy reference.
--
-- Key Features:
--   1. Matches BOTH ingredient-level AND product-level RxNorm codes
--   2. Uses improved medication timing bounds for ~89% date coverage
--   3. Includes all medication fields from v_medications
--   4. Adds chemotherapy-specific fields (drug_id, approval_status, etc.)
--
-- Data Sources:
--   - fhir_prd_db.medication_request (FHIR medication orders)
--   - fhir_prd_db.medication (medication details)
--   - fhir_prd_db.medication_code_coding (RxNorm codes)
--   - fhir_prd_db.v_chemotherapy_drugs (814 chemotherapy ingredient codes)
--   - fhir_prd_db.v_chemotherapy_rxnorm_codes (2,804 product→ingredient mappings)
--
-- Usage:
--   SELECT * FROM fhir_prd_db.v_chemo_medications
--   WHERE patient_fhir_id = 'Patient/123'
--     AND medication_start_date >= DATE '2020-01-01'
--   ORDER BY medication_start_date;
--
-- History:
--   2025-01-XX: Initial creation using comprehensive chemotherapy reference
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_chemo_medications AS
WITH
-- ================================================================================
-- Step 1: Get timing bounds from dosage instruction (provides ~89% date coverage)
-- ================================================================================
medication_timing_bounds AS (
    SELECT
        medication_request_id,
        MIN(dosage_instruction_timing_repeat_bounds_period_start) as earliest_bounds_start,
        MAX(dosage_instruction_timing_repeat_bounds_period_end) as latest_bounds_end
    FROM fhir_prd_db.medication_request_dosage_instruction
    WHERE dosage_instruction_timing_repeat_bounds_period_start IS NOT NULL
       OR dosage_instruction_timing_repeat_bounds_period_end IS NOT NULL
    GROUP BY medication_request_id
),

-- ================================================================================
-- Step 2: Get all medication RxNorm codes (both ingredient and product codes)
-- ================================================================================
medication_rxnorm_codes AS (
    SELECT
        mcc.medication_id,
        mcc.code_coding_code AS rxnorm_code,
        mcc.code_coding_display AS rxnorm_display
    FROM fhir_prd_db.medication_code_coding mcc
    WHERE mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        AND mcc.code_coding_code IS NOT NULL
),

-- ================================================================================
-- Step 3: Match RxNorm codes to chemotherapy drugs (BOTH ingredient AND product)
-- ================================================================================
chemotherapy_medication_matches AS (
    SELECT DISTINCT
        mrc.medication_id,
        mrc.rxnorm_code,
        mrc.rxnorm_display,
        -- Direct ingredient match
        COALESCE(cd_direct.drug_id, cd_product.drug_id) AS chemo_drug_id,
        COALESCE(cd_direct.preferred_name, cd_product.preferred_name) AS chemo_preferred_name,
        COALESCE(cd_direct.approval_status, cd_product.approval_status) AS chemo_approval_status,
        COALESCE(cd_direct.rxnorm_in, cd_product.rxnorm_in) AS chemo_rxnorm_ingredient,
        COALESCE(cd_direct.ncit_code, cd_product.ncit_code) AS chemo_ncit_code,
        COALESCE(cd_direct.sources, cd_product.sources) AS chemo_sources,
        -- Match type for debugging
        CASE
            WHEN cd_direct.drug_id IS NOT NULL THEN 'ingredient'
            WHEN cd_product.drug_id IS NOT NULL THEN 'product'
            ELSE 'unknown'
        END AS match_type
    FROM medication_rxnorm_codes mrc
    -- Try direct ingredient code match first
    LEFT JOIN fhir_prd_db.v_chemotherapy_drugs cd_direct
        ON mrc.rxnorm_code = cd_direct.rxnorm_in
    -- Try product→ingredient mapping if no direct match
    LEFT JOIN fhir_prd_db.v_chemotherapy_rxnorm_codes crc
        ON mrc.rxnorm_code = crc.product_rxnorm_code
    LEFT JOIN fhir_prd_db.v_chemotherapy_drugs cd_product
        ON crc.ingredient_rxnorm_code = cd_product.rxnorm_in
    WHERE cd_direct.drug_id IS NOT NULL
       OR cd_product.drug_id IS NOT NULL
),

-- ================================================================================
-- Step 4: Aggregate medication details (same as v_medications)
-- ================================================================================
medication_notes AS (
    SELECT
        medication_request_id,
        LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_text) as note_text_aggregated
    FROM fhir_prd_db.medication_request_note
    GROUP BY medication_request_id
),
medication_reasons AS (
    SELECT
        medication_request_id,
        LISTAGG(reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
    FROM fhir_prd_db.medication_request_reason_code
    GROUP BY medication_request_id
),
medication_forms AS (
    SELECT
        medication_id,
        LISTAGG(DISTINCT form_coding_code, ' | ') WITHIN GROUP (ORDER BY form_coding_code) as form_coding_codes,
        LISTAGG(DISTINCT form_coding_display, ' | ') WITHIN GROUP (ORDER BY form_coding_display) as form_coding_displays
    FROM fhir_prd_db.medication_form_coding
    GROUP BY medication_id
),
medication_ingredients AS (
    SELECT
        medication_id,
        LISTAGG(DISTINCT CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit, ' | ')
            WITHIN GROUP (ORDER BY CAST(ingredient_strength_numerator_value AS VARCHAR) || ' ' || ingredient_strength_numerator_unit) as ingredient_strengths
    FROM fhir_prd_db.medication_ingredient
    WHERE ingredient_strength_numerator_value IS NOT NULL
    GROUP BY medication_id
),
medication_dosage_instructions AS (
    SELECT
        medication_request_id,
        -- Route information (CRITICAL for chemotherapy analysis)
        LISTAGG(DISTINCT dosage_instruction_route_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_route_text) as route_text_aggregated,
        -- Method (e.g., IV push, IV drip)
        LISTAGG(DISTINCT dosage_instruction_method_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_method_text) as method_text_aggregated,
        -- Full dosage instruction text
        LISTAGG(dosage_instruction_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_sequence) as dosage_text_aggregated,
        -- Site (e.g., port, peripheral line)
        LISTAGG(DISTINCT dosage_instruction_site_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_site_text) as site_text_aggregated,
        -- Patient instructions
        LISTAGG(DISTINCT dosage_instruction_patient_instruction, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_patient_instruction) as patient_instruction_aggregated,
        -- Timing information
        LISTAGG(DISTINCT dosage_instruction_timing_code_text, ' | ') WITHIN GROUP (ORDER BY dosage_instruction_timing_code_text) as timing_code_aggregated
    FROM fhir_prd_db.medication_request_dosage_instruction
    GROUP BY medication_request_id
),
medication_based_on AS (
    SELECT
        medication_request_id,
        LISTAGG(DISTINCT based_on_reference, ' | ') WITHIN GROUP (ORDER BY based_on_reference) AS based_on_references,
        LISTAGG(DISTINCT based_on_display, ' | ') WITHIN GROUP (ORDER BY based_on_display) AS based_on_displays
    FROM fhir_prd_db.medication_request_based_on
    GROUP BY medication_request_id
),
medication_reason_references AS (
    SELECT
        medication_request_id,
        LISTAGG(DISTINCT reason_reference_display, ' | ') WITHIN GROUP (ORDER BY reason_reference_display) AS reason_reference_displays
    FROM fhir_prd_db.medication_request_reason_reference
    GROUP BY medication_request_id
)

-- ================================================================================
-- Step 5: Final SELECT - All chemotherapy medications with full details
-- ================================================================================
SELECT
    -- Patient identifiers
    mr.subject_reference as patient_fhir_id,
    mr.encounter_reference as encounter_fhir_id,

    -- Medication request identifiers
    mr.id as medication_request_fhir_id,
    m.id as medication_fhir_id,

    -- Chemotherapy classification (from comprehensive reference)
    cmm.chemo_drug_id,
    cmm.chemo_preferred_name,
    cmm.chemo_approval_status,
    cmm.chemo_rxnorm_ingredient,
    cmm.chemo_ncit_code,
    cmm.chemo_sources,
    cmm.match_type as rxnorm_match_type,

    -- Medication details
    m.code_text as medication_name,
    cmm.rxnorm_code as medication_rxnorm_code,
    cmm.rxnorm_display as medication_rxnorm_display,

    -- Status and intent
    mr.status as medication_status,
    mr.intent as medication_intent,
    mr.priority as medication_priority,

    -- Dates (improved coverage using timing_bounds)
    CASE
        WHEN mtb.earliest_bounds_start IS NOT NULL THEN
            CASE
                WHEN LENGTH(mtb.earliest_bounds_start) = 10
                THEN CAST(mtb.earliest_bounds_start || 'T00:00:00Z' AS TIMESTAMP(3))
                ELSE TRY(CAST(mtb.earliest_bounds_start AS TIMESTAMP(3)))
            END
        WHEN mr.authored_on IS NOT NULL THEN
            CASE
                WHEN LENGTH(mr.authored_on) = 10
                THEN CAST(mr.authored_on || 'T00:00:00Z' AS TIMESTAMP(3))
                ELSE TRY(CAST(mr.authored_on AS TIMESTAMP(3)))
            END
        ELSE NULL
    END as medication_start_date,

    CASE
        WHEN mtb.latest_bounds_end IS NOT NULL THEN
            CASE
                WHEN LENGTH(mtb.latest_bounds_end) = 10
                THEN CAST(mtb.latest_bounds_end || 'T00:00:00Z' AS TIMESTAMP(3))
                ELSE TRY(CAST(mtb.latest_bounds_end AS TIMESTAMP(3)))
            END
        WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN
            CASE
                WHEN LENGTH(mr.dispense_request_validity_period_end) = 10
                THEN CAST(mr.dispense_request_validity_period_end || 'T00:00:00Z' AS TIMESTAMP(3))
                ELSE TRY(CAST(mr.dispense_request_validity_period_end AS TIMESTAMP(3)))
            END
        ELSE NULL
    END as medication_stop_date,

    TRY(CAST(mr.authored_on AS TIMESTAMP(3))) as medication_authored_date,

    -- Dosage and route (CRITICAL for chemotherapy)
    mdi.route_text_aggregated as medication_route,
    mdi.method_text_aggregated as medication_method,
    mdi.site_text_aggregated as medication_site,
    mdi.dosage_text_aggregated as medication_dosage_instructions,
    mdi.timing_code_aggregated as medication_timing,
    mdi.patient_instruction_aggregated as medication_patient_instructions,

    -- Form and ingredients
    mf.form_coding_codes as medication_form_codes,
    mf.form_coding_displays as medication_forms,
    mi.ingredient_strengths as medication_ingredient_strengths,

    -- Clinical context
    mrrefs.reason_reference_displays as medication_reason,
    mrr.reason_code_text_aggregated as medication_reason_codes,
    mn.note_text_aggregated as medication_notes,

    -- Care plan linkage
    mbo.based_on_references as care_plan_references,
    mbo.based_on_displays as care_plan_displays,

    -- Requester
    mr.requester_reference as requester_fhir_id,
    mr.requester_display as requester_name,

    -- Recorder and entered by
    mr.recorder_reference as recorder_fhir_id,
    mr.recorder_display as recorder_name

FROM fhir_prd_db.medication_request mr

-- Join to medication details
LEFT JOIN fhir_prd_db.medication m
    ON m.id = mr.medication_reference_reference

-- Join to chemotherapy matches (INNER JOIN to filter to chemo only)
INNER JOIN chemotherapy_medication_matches cmm
    ON cmm.medication_id = m.id

-- Join to timing bounds
LEFT JOIN medication_timing_bounds mtb
    ON mtb.medication_request_id = mr.id

-- Join to aggregated details
LEFT JOIN medication_notes mn
    ON mn.medication_request_id = mr.id
LEFT JOIN medication_reasons mrr
    ON mrr.medication_request_id = mr.id
LEFT JOIN medication_forms mf
    ON mf.medication_id = m.id
LEFT JOIN medication_ingredients mi
    ON mi.medication_id = m.id
LEFT JOIN medication_dosage_instructions mdi
    ON mdi.medication_request_id = mr.id
LEFT JOIN medication_based_on mbo
    ON mbo.medication_request_id = mr.id
LEFT JOIN medication_reason_references mrrefs
    ON mrrefs.medication_request_id = mr.id

-- Only include active, completed, or stopped medications
WHERE mr.status IN ('active', 'completed', 'stopped', 'on-hold')
;
