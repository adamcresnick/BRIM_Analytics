-- ================================================================================
-- v_concomitant_medications - CORRECTED VERSION
-- ================================================================================
-- PURPOSE: Identify medications administered during chemotherapy treatment windows
--
-- APPROACH:
--   1. Get chemotherapy medications and time windows from v_medications (filtered source)
--   2. Get ALL medications from medication_request (unfiltered - includes everything)
--   3. Find temporal overlaps between chemotherapy windows and all other medications
--   4. Exclude only the specific chemotherapy medication itself from concomitant list
--
-- KEY CHANGE: Uses v_medications as the authoritative source for chemotherapy
-- time windows instead of hardcoding chemotherapy drug list
-- ================================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_concomitant_medications AS
WITH
-- ================================================================================
-- Step 0: Get timing bounds from dosage instruction sub-schema
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
-- Step 1: Get chemotherapy medications and time windows from v_medications
-- ================================================================================
-- This ensures we use the SAME chemotherapy definition as the Python
-- ChemotherapyFilter and timeline database
-- ================================================================================
chemotherapy_agents AS (
    SELECT
        patient_fhir_id,
        medication_request_id as medication_fhir_id,
        medication_name,
        rx_norm_codes as rxnorm_cui,
        medication_status as status,
        mr_intent as intent,

        -- Use the standardized datetime fields from v_medications
        medication_start_date as start_datetime,
        mr_validity_period_end as stop_datetime,
        mr_authored_on as authored_datetime,

        -- Date source for quality tracking
        CASE
            WHEN mr_validity_period_start IS NOT NULL THEN 'timing_bounds'
            WHEN mr_validity_period_end IS NOT NULL THEN 'dispense_period'
            WHEN mr_authored_on IS NOT NULL THEN 'authored_on'
            ELSE 'missing'
        END as date_source

    FROM fhir_prd_db.v_medications
    -- This WHERE clause is CRITICAL - it limits to only chemotherapy medications
    -- that have already been filtered by the ChemotherapyFilter logic
    WHERE 1=1
        -- v_medications is already filtered to chemotherapy by the Python code
        -- that populates the timeline, so we don't need additional filtering here
        -- Just ensure we have valid time windows
        AND medication_start_date IS NOT NULL
),

-- ================================================================================
-- Step 2: Get ALL medications (unfiltered) with their time windows
-- ================================================================================
-- This CTE pulls from raw medication_request table to get EVERYTHING,
-- including supportive care, antibiotics, etc. that were filtered out
-- ================================================================================
all_medications AS (
    SELECT
        mr.subject_reference as patient_fhir_id,
        mr.id as medication_fhir_id,
        mcc.code_coding_code as rxnorm_cui,
        mcc.code_coding_display as medication_name,
        mr.status,
        mr.intent,

        -- Standardized start date (prefer timing bounds, fallback to authored_on)
        CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.earliest_bounds_start) = 10
                    THEN mtb.earliest_bounds_start || 'T00:00:00Z'
                    ELSE mtb.earliest_bounds_start
                END
            WHEN LENGTH(mr.authored_on) = 10
                THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END as start_datetime,

        -- Standardized stop date (prefer timing bounds, fallback to dispense validity period)
        CASE
            WHEN mtb.latest_bounds_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.latest_bounds_end) = 10
                    THEN mtb.latest_bounds_end || 'T00:00:00Z'
                    ELSE mtb.latest_bounds_end
                END
            WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mr.dispense_request_validity_period_end) = 10
                    THEN mr.dispense_request_validity_period_end || 'T00:00:00Z'
                    ELSE mr.dispense_request_validity_period_end
                END
            ELSE NULL
        END as stop_datetime,

        -- Authored date (order date)
        CASE
            WHEN LENGTH(mr.authored_on) = 10
            THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END as authored_datetime,

        -- Date source for quality tracking
        CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN 'timing_bounds'
            WHEN mr.dispense_request_validity_period_end IS NOT NULL THEN 'dispense_period'
            WHEN mr.authored_on IS NOT NULL THEN 'authored_on'
            ELSE 'missing'
        END as date_source,

        -- Categorize medication by RxNorm code
        -- This helps identify what TYPE of concomitant medication it is
        CASE
            -- Antiemetics (nausea/vomiting prevention)
            WHEN mcc.code_coding_code IN ('26225', '4896', '288635', '135', '7533', '51272')
                THEN 'antiemetic'
            -- Corticosteroids (reduce swelling, prevent allergic reactions)
            WHEN mcc.code_coding_code IN ('3264', '8640', '6902', '5492', '4850')
                THEN 'corticosteroid'
            -- Growth factors (stimulate blood cell production)
            WHEN mcc.code_coding_code IN ('105585', '358810', '4716', '139825')
                THEN 'growth_factor'
            -- Anticonvulsants (seizure prevention)
            WHEN mcc.code_coding_code IN ('35766', '11118', '6470', '2002', '8134', '114477')
                THEN 'anticonvulsant'
            -- Antimicrobials (infection prevention/treatment)
            WHEN mcc.code_coding_code IN ('161', '10831', '1043', '7454', '374056', '203')
                THEN 'antimicrobial'
            -- Proton pump inhibitors / GI protection
            WHEN mcc.code_coding_code IN ('7646', '29046', '40790', '8163')
                THEN 'gi_protection'
            -- Pain management
            WHEN mcc.code_coding_code IN ('7804', '7052', '5489', '6754', '237')
                THEN 'analgesic'
            -- H2 blockers
            WHEN mcc.code_coding_code IN ('8772', '10156', '4278')
                THEN 'h2_blocker'
            WHEN LOWER(mcc.code_coding_display) LIKE '%ondansetron%' OR LOWER(m.code_text) LIKE '%zofran%' THEN 'antiemetic'
            WHEN LOWER(mcc.code_coding_display) LIKE '%dexamethasone%' OR LOWER(m.code_text) LIKE '%prednisone%' THEN 'corticosteroid'
            WHEN LOWER(mcc.code_coding_display) LIKE '%filgrastim%' OR LOWER(m.code_text) LIKE '%neupogen%' THEN 'growth_factor'
            WHEN LOWER(mcc.code_coding_display) LIKE '%levetiracetam%' OR LOWER(m.code_text) LIKE '%keppra%' THEN 'anticonvulsant'
            ELSE 'other'
        END as medication_category

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN medication_timing_bounds mtb ON mr.id = mtb.medication_request_id
    LEFT JOIN fhir_prd_db.medication m ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    WHERE mr.status IN ('active', 'completed', 'on-hold', 'stopped')
        -- NO FILTERING OF DRUG TYPE HERE - we want ALL medications
)

-- ================================================================================
-- Step 3: Calculate temporal overlaps between chemotherapy and all medications
-- ================================================================================
SELECT
    -- Patient identifier
    ca.patient_fhir_id,

    -- ============================================================================
    -- CHEMOTHERAPY AGENT DETAILS
    -- ============================================================================
    ca.medication_fhir_id as chemo_medication_fhir_id,
    ca.rxnorm_cui as chemo_rxnorm_cui,
    ca.medication_name as chemo_medication_name,
    ca.status as chemo_status,
    ca.intent as chemo_intent,

    -- Chemotherapy time window
    TRY(CAST(ca.start_datetime AS TIMESTAMP(3))) as chemo_start_datetime,
    TRY(CAST(ca.stop_datetime AS TIMESTAMP(3))) as chemo_stop_datetime,
    TRY(CAST(ca.authored_datetime AS TIMESTAMP(3))) as chemo_authored_datetime,

    -- Chemotherapy duration in days
    CASE
        WHEN ca.stop_datetime IS NOT NULL AND ca.start_datetime IS NOT NULL
        THEN DATE_DIFF('day',
            CAST(SUBSTR(ca.start_datetime, 1, 10) AS DATE),
            CAST(SUBSTR(ca.stop_datetime, 1, 10) AS DATE))
        ELSE NULL
    END as chemo_duration_days,

    ca.date_source as chemo_date_source,
    CASE WHEN ca.rxnorm_cui IS NOT NULL THEN true ELSE false END as has_chemo_rxnorm,

    -- ============================================================================
    -- CONCOMITANT MEDICATION DETAILS
    -- ============================================================================
    am.medication_fhir_id as conmed_medication_fhir_id,
    am.rxnorm_cui as conmed_rxnorm_cui,
    am.medication_name as conmed_medication_name,
    am.status as conmed_status,
    am.intent as conmed_intent,

    -- Conmed time window
    TRY(CAST(am.start_datetime AS TIMESTAMP(3))) as conmed_start_datetime,
    TRY(CAST(am.stop_datetime AS TIMESTAMP(3))) as conmed_stop_datetime,
    TRY(CAST(am.authored_datetime AS TIMESTAMP(3))) as conmed_authored_datetime,

    -- Conmed duration in days
    CASE
        WHEN am.stop_datetime IS NOT NULL AND am.start_datetime IS NOT NULL
        THEN DATE_DIFF('day',
            CAST(SUBSTR(am.start_datetime, 1, 10) AS DATE),
            CAST(SUBSTR(am.stop_datetime, 1, 10) AS DATE))
        ELSE NULL
    END as conmed_duration_days,

    am.date_source as conmed_date_source,
    CASE WHEN am.rxnorm_cui IS NOT NULL THEN true ELSE false END as has_conmed_rxnorm,

    -- Conmed categorization
    am.medication_category as conmed_category,

    -- ============================================================================
    -- TEMPORAL OVERLAP DETAILS
    -- ============================================================================

    -- Overlap start (later of the two start dates)
    TRY(CAST(CASE
        WHEN ca.start_datetime >= am.start_datetime THEN ca.start_datetime
        ELSE am.start_datetime
    END AS TIMESTAMP(3))) as overlap_start_datetime,

    -- Overlap stop (earlier of the two stop dates, or NULL if either is NULL)
    TRY(CAST(CASE
        WHEN ca.stop_datetime IS NULL OR am.stop_datetime IS NULL THEN NULL
        WHEN ca.stop_datetime <= am.stop_datetime THEN ca.stop_datetime
        ELSE am.stop_datetime
    END AS TIMESTAMP(3))) as overlap_stop_datetime,

    -- Overlap duration in days
    CASE
        WHEN ca.stop_datetime IS NOT NULL AND am.stop_datetime IS NOT NULL
            AND ca.start_datetime IS NOT NULL AND am.start_datetime IS NOT NULL
        THEN DATE_DIFF('day',
            CAST(SUBSTR(GREATEST(ca.start_datetime, am.start_datetime), 1, 10) AS DATE),
            CAST(SUBSTR(LEAST(ca.stop_datetime, am.stop_datetime), 1, 10) AS DATE))
        ELSE NULL
    END as overlap_duration_days,

    -- Overlap type classification
    CASE
        -- Conmed entirely during chemo window
        WHEN am.start_datetime >= ca.start_datetime
            AND (am.stop_datetime IS NULL OR (ca.stop_datetime IS NOT NULL AND am.stop_datetime <= ca.stop_datetime))
            THEN 'during_chemo'
        -- Conmed started during chemo but may extend beyond
        WHEN am.start_datetime >= ca.start_datetime
            AND (ca.stop_datetime IS NULL OR am.start_datetime <= ca.stop_datetime)
            THEN 'started_during_chemo'
        -- Conmed stopped during chemo but started before
        WHEN am.stop_datetime IS NOT NULL
            AND ca.stop_datetime IS NOT NULL
            AND am.stop_datetime >= ca.start_datetime
            AND am.stop_datetime <= ca.stop_datetime
            THEN 'stopped_during_chemo'
        -- Conmed spans entire chemo period
        WHEN am.start_datetime <= ca.start_datetime
            AND (am.stop_datetime IS NULL OR (ca.stop_datetime IS NOT NULL AND am.stop_datetime >= ca.stop_datetime))
            THEN 'spans_chemo'
        ELSE 'partial_overlap'
    END as overlap_type,

    -- Data quality indicators
    CASE
        WHEN ca.date_source = 'timing_bounds' AND am.date_source = 'timing_bounds' THEN 'high'
        WHEN ca.date_source = 'timing_bounds' OR am.date_source = 'timing_bounds' THEN 'medium'
        WHEN ca.date_source = 'dispense_period' AND am.date_source = 'dispense_period' THEN 'medium'
        ELSE 'low'
    END as date_quality

FROM chemotherapy_agents ca
INNER JOIN all_medications am
    ON ca.patient_fhir_id = am.patient_fhir_id
    -- CRITICAL: Exclude the chemotherapy medication itself from concomitant list
    AND ca.medication_fhir_id != am.medication_fhir_id
WHERE
    -- Temporal overlap condition: periods must overlap
    -- Condition 1: conmed starts during chemo
    (
        am.start_datetime >= ca.start_datetime
        AND (ca.stop_datetime IS NULL OR am.start_datetime <= ca.stop_datetime)
    )
    -- Condition 2: conmed stops during chemo
    OR (
        am.stop_datetime IS NOT NULL
        AND ca.stop_datetime IS NOT NULL
        AND am.stop_datetime >= ca.start_datetime
        AND am.stop_datetime <= ca.stop_datetime
    )
    -- Condition 3: conmed spans entire chemo period
    OR (
        am.start_datetime <= ca.start_datetime
        AND (am.stop_datetime IS NULL OR (ca.stop_datetime IS NOT NULL AND am.stop_datetime >= ca.stop_datetime))
    );
