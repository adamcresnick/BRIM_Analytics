-- ================================================================================
-- Query: Check for MEK and BRAF Inhibitor Treatment in Specific Patients
-- ================================================================================
-- Purpose: Identify if the following patients have been treated with MEK or BRAF inhibitors
-- Patients: 
--   - eMs2NnGm924T3P.-WlJNbGSyTbwC0mH.Uy9GHFKhgUq83
--   - e8jvrF5IozRmfwySdwoRVwz02sJVXqC2b0q7DVAmDDcQ3
--   - ePCcDRUsjiniYE3.EIVUejNqzdu1ovhebX.tYYcTI25w3
-- 
-- MEK Inhibitors: trametinib, cobimetinib, binimetinib, selumetinib
-- BRAF Inhibitors: dabrafenib, vemurafenib, encorafenib
--
-- Database: fhir_prd_db (or fhir_v2_prd_db - adjust as needed)
-- ================================================================================

WITH target_patients AS (
    SELECT 'eMs2NnGm924T3P.-WlJNbGSyTbwC0mH.Uy9GHFKhgUq83' as patient_id
    UNION ALL
    SELECT 'e8jvrF5IozRmfwySdwoRVwz02sJVXqC2b0q7DVAmDDcQ3'
    UNION ALL
    SELECT 'ePCcDRUsjiniYE3.EIVUejNqzdu1ovhebX.tYYcTI25w3'
),
mek_braf_medications AS (
    SELECT
        pm.patient_id,
        pm.medication_name,
        pm.rx_norm_codes,
        pm.authored_on as medication_start_date,
        pm.status as medication_status,
        mr.dispense_request_validity_period_start,
        mr.dispense_request_validity_period_end,
        mr.course_of_therapy_type_text,
        mrn.note_text_aggregated,
        mrr.reason_code_text_aggregated,
        CASE
            -- MEK Inhibitors
            WHEN LOWER(pm.medication_name) LIKE '%trametinib%' THEN 'MEK Inhibitor - Trametinib (Mekinist)'
            WHEN LOWER(pm.medication_name) LIKE '%mekinist%' THEN 'MEK Inhibitor - Trametinib (Mekinist)'
            WHEN LOWER(pm.medication_name) LIKE '%cobimetinib%' THEN 'MEK Inhibitor - Cobimetinib (Cotellic)'
            WHEN LOWER(pm.medication_name) LIKE '%cotellic%' THEN 'MEK Inhibitor - Cobimetinib (Cotellic)'
            WHEN LOWER(pm.medication_name) LIKE '%binimetinib%' THEN 'MEK Inhibitor - Binimetinib (Mektovi)'
            WHEN LOWER(pm.medication_name) LIKE '%mektovi%' THEN 'MEK Inhibitor - Binimetinib (Mektovi)'
            WHEN LOWER(pm.medication_name) LIKE '%selumetinib%' THEN 'MEK Inhibitor - Selumetinib (Koselugo)'
            WHEN LOWER(pm.medication_name) LIKE '%koselugo%' THEN 'MEK Inhibitor - Selumetinib (Koselugo)'
            -- BRAF Inhibitors
            WHEN LOWER(pm.medication_name) LIKE '%dabrafenib%' THEN 'BRAF Inhibitor - Dabrafenib (Tafinlar)'
            WHEN LOWER(pm.medication_name) LIKE '%tafinlar%' THEN 'BRAF Inhibitor - Dabrafenib (Tafinlar)'
            WHEN LOWER(pm.medication_name) LIKE '%vemurafenib%' THEN 'BRAF Inhibitor - Vemurafenib (Zelboraf)'
            WHEN LOWER(pm.medication_name) LIKE '%zelboraf%' THEN 'BRAF Inhibitor - Vemurafenib (Zelboraf)'
            WHEN LOWER(pm.medication_name) LIKE '%encorafenib%' THEN 'BRAF Inhibitor - Encorafenib (Braftovi)'
            WHEN LOWER(pm.medication_name) LIKE '%braftovi%' THEN 'BRAF Inhibitor - Encorafenib (Braftovi)'
            ELSE 'Unknown'
        END as inhibitor_class
    FROM fhir_prd_db.patient_medications pm
    LEFT JOIN fhir_prd_db.medication_request mr ON pm.medication_request_id = mr.id
    LEFT JOIN (
        SELECT
            medication_request_id,
            LISTAGG(note_text, ' | ') WITHIN GROUP (ORDER BY note_text) as note_text_aggregated
        FROM fhir_prd_db.medication_request_note
        GROUP BY medication_request_id
    ) mrn ON mr.id = mrn.medication_request_id
    LEFT JOIN (
        SELECT
            medication_request_id,
            LISTAGG(reason_code_text, ' | ') WITHIN GROUP (ORDER BY reason_code_text) as reason_code_text_aggregated
        FROM fhir_prd_db.medication_request_reason_code
        GROUP BY medication_request_id
    ) mrr ON mr.id = mrr.medication_request_id
    WHERE pm.patient_id IN (SELECT patient_id FROM target_patients)
        AND (
            -- MEK Inhibitors
            LOWER(pm.medication_name) LIKE '%trametinib%'
            OR LOWER(pm.medication_name) LIKE '%mekinist%'
            OR LOWER(pm.medication_name) LIKE '%cobimetinib%'
            OR LOWER(pm.medication_name) LIKE '%cotellic%'
            OR LOWER(pm.medication_name) LIKE '%binimetinib%'
            OR LOWER(pm.medication_name) LIKE '%mektovi%'
            OR LOWER(pm.medication_name) LIKE '%selumetinib%'
            OR LOWER(pm.medication_name) LIKE '%koselugo%'
            -- BRAF Inhibitors
            OR LOWER(pm.medication_name) LIKE '%dabrafenib%'
            OR LOWER(pm.medication_name) LIKE '%tafinlar%'
            OR LOWER(pm.medication_name) LIKE '%vemurafenib%'
            OR LOWER(pm.medication_name) LIKE '%zelboraf%'
            OR LOWER(pm.medication_name) LIKE '%encorafenib%'
            OR LOWER(pm.medication_name) LIKE '%braftovi%'
        )
)
SELECT
    tp.patient_id,
    CASE 
        WHEN COUNT(mbm.patient_id) > 0 THEN 'YES - Treated with MEK/BRAF Inhibitors'
        ELSE 'NO - No MEK/BRAF Inhibitors Found'
    END as treatment_status,
    COUNT(mbm.patient_id) as num_prescriptions,
    LISTAGG(DISTINCT mbm.inhibitor_class, '; ') WITHIN GROUP (ORDER BY mbm.inhibitor_class) as inhibitor_types,
    LISTAGG(DISTINCT mbm.medication_name, '; ') WITHIN GROUP (ORDER BY mbm.medication_name) as medication_names,
    MIN(mbm.medication_start_date) as first_prescription_date,
    MAX(mbm.medication_start_date) as last_prescription_date
FROM target_patients tp
LEFT JOIN mek_braf_medications mbm ON tp.patient_id = mbm.patient_id
GROUP BY tp.patient_id
ORDER BY tp.patient_id;

-- ================================================================================
-- DETAILED RESULTS: Get all medication records with full details
-- ================================================================================
-- Uncomment the query below to see detailed medication records for each patient
-- ================================================================================

/*
SELECT
    patient_id,
    medication_name,
    inhibitor_class,
    medication_status,
    medication_start_date,
    dispense_request_validity_period_start,
    dispense_request_validity_period_end,
    course_of_therapy_type_text,
    reason_code_text_aggregated,
    note_text_aggregated,
    rx_norm_codes
FROM mek_braf_medications
ORDER BY patient_id, medication_start_date;
*/
