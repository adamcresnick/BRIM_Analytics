CREATE OR REPLACE VIEW fhir_prd_db.v_imaging_corticosteroid_use AS

WITH medication_timing_bounds AS (
    -- Aggregate timing bounds from dosage instruction sub-schema
    SELECT
        medication_request_id,
        MIN(dosage_instruction_timing_repeat_bounds_period_start) as earliest_bounds_start,
        MAX(dosage_instruction_timing_repeat_bounds_period_end) as latest_bounds_end
    FROM fhir_prd_db.medication_request_dosage_instruction
    WHERE dosage_instruction_timing_repeat_bounds_period_start IS NOT NULL
       OR dosage_instruction_timing_repeat_bounds_period_end IS NOT NULL
    GROUP BY medication_request_id
),

corticosteroid_medications AS (
    -- Identify all corticosteroid medications (systemic use)
    SELECT DISTINCT
        mr.id as medication_request_fhir_id,
        mr.subject_reference as patient_fhir_id,

        -- Medication identification
        COALESCE(m.code_text, mr.medication_reference_display) as medication_name,
        mcc.code_coding_code as rxnorm_cui,
        mcc.code_coding_display as rxnorm_display,

        -- Standardized generic name (maps to RxNorm ingredient level)
        CASE
            -- High priority glucocorticoids
            WHEN mcc.code_coding_code = '3264'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%dexamethasone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%decadron%'
                THEN 'dexamethasone'
            WHEN mcc.code_coding_code = '8640'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prednisone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%deltasone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%rayos%'
                THEN 'prednisone'
            WHEN mcc.code_coding_code = '8638'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prednisolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%orapred%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prelone%'
                THEN 'prednisolone'
            WHEN mcc.code_coding_code = '6902'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%methylprednisolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%medrol%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%solu-medrol%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%solumedrol%'
                THEN 'methylprednisolone'
            WHEN mcc.code_coding_code = '5492'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%hydrocortisone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cortef%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%solu-cortef%'
                THEN 'hydrocortisone'
            WHEN mcc.code_coding_code IN ('1514', '1347')  -- Both CUIs found in data
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%betamethasone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%celestone%'
                THEN 'betamethasone'
            WHEN mcc.code_coding_code = '10759'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%triamcinolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%kenalog%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%aristospan%'
                THEN 'triamcinolone'

            -- Medium priority glucocorticoids
            WHEN mcc.code_coding_code = '2878'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cortisone%'
                THEN 'cortisone'
            WHEN mcc.code_coding_code = '22396'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%deflazacort%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%emflaza%'
                THEN 'deflazacort'
            WHEN mcc.code_coding_code = '7910'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%paramethasone%'
                THEN 'paramethasone'
            WHEN mcc.code_coding_code = '29523'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%meprednisone%'
                THEN 'meprednisone'
            WHEN mcc.code_coding_code = '4463'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%fluocortolone%'
                THEN 'fluocortolone'
            WHEN mcc.code_coding_code = '55681'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%rimexolone%'
                THEN 'rimexolone'

            -- Lower priority glucocorticoids (rare)
            WHEN mcc.code_coding_code = '12473'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%prednylidene%'
                THEN 'prednylidene'
            WHEN mcc.code_coding_code = '21285'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cloprednol%'
                THEN 'cloprednol'
            WHEN mcc.code_coding_code = '21660'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%cortivazol%'
                THEN 'cortivazol'
            WHEN mcc.code_coding_code = '2669799'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%vamorolone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%agamree%'
                THEN 'vamorolone'

            -- Mineralocorticoids
            WHEN mcc.code_coding_code = '4452'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%fludrocortisone%'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%florinef%'
                THEN 'fludrocortisone'
            WHEN mcc.code_coding_code = '3256'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%desoxycorticosterone%'
                THEN 'desoxycorticosterone'
            WHEN mcc.code_coding_code = '1312358'
                 OR LOWER(COALESCE(m.code_text, mr.medication_reference_display)) LIKE '%aldosterone%'
                THEN 'aldosterone'

            ELSE 'other_corticosteroid'
        END as corticosteroid_generic_name,

        -- Detection method
        CASE
            WHEN mcc.code_coding_code IS NOT NULL THEN 'rxnorm_cui'
            ELSE 'text_match'
        END as detection_method,

        -- Temporal fields - hierarchical date selection
        TRY(CAST(CASE
            WHEN mtb.earliest_bounds_start IS NOT NULL THEN
                CASE
                    WHEN LENGTH(mtb.earliest_bounds_start) = 10
                    THEN mtb.earliest_bounds_start || 'T00:00:00Z'
                    ELSE mtb.earliest_bounds_start
                END
            WHEN LENGTH(mr.authored_on) = 10
                THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END AS TIMESTAMP(3))) as medication_start_datetime,

        TRY(CAST(CASE
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
        END AS TIMESTAMP(3))) as medication_stop_datetime,

        mr.status as medication_status

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN medication_timing_bounds mtb ON mr.id = mtb.medication_request_id
    LEFT JOIN fhir_prd_db.medication m
        ON m.id = mr.medication_reference_reference
    LEFT JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = m.id
        AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'

    WHERE (