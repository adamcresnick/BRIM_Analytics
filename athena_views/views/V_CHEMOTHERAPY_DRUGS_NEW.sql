-- ================================================================================
-- v_chemotherapy_drugs: Reference view for all chemotherapy drugs
-- ================================================================================
-- This view simply selects from the chemotherapy_drugs external table
-- The actual drug data is stored in S3 as a CSV file

CREATE OR REPLACE VIEW fhir_prd_db.v_chemotherapy_drugs AS
SELECT
    drug_id,
    preferred_name,
    approval_status,
    rxnorm_in,
    ncit_code,
    normalized_key,
    sources,
    drug_category
FROM fhir_prd_db.chemotherapy_drugs;
