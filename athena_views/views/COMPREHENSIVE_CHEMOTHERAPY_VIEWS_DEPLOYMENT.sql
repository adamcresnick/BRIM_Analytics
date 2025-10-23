-- ================================================================================
-- COMPREHENSIVE CHEMOTHERAPY REFERENCE SYSTEM - DEPLOYMENT SCRIPT
-- ================================================================================
-- Purpose: Deploy comprehensive chemotherapy reference views and updated
--          v_concomitant_medications with comprehensive 814-drug reference
--
-- Database: fhir_prd_db
-- Date: 2025-01-XX
-- Author: Claude Code + User
--
-- DEPLOYMENT ORDER:
--   1. v_chemotherapy_drugs (reference - 3,064 drugs, 814 with RxNorm)
--   2. v_chemotherapy_rxnorm_codes (product→ingredient mappings - 2,804)
--   3. v_chemotherapy_regimens (22 regimens)
--   4. v_chemotherapy_regimen_components (75 components)
--   5. v_chemo_medications (identifies all chemo meds using reference)
--   6. v_concomitant_medications (updated to use comprehensive reference)
--
-- CHANGES FROM PREVIOUS VERSION:
--   - Expanded from 11 hardcoded drugs to 814 comprehensive chemotherapy drugs
--   - Fixed bevacizumab RxNorm code from 42316 (incorrect) to 253337 (correct)
--   - Added product→ingredient RxNorm mapping (catches branded drugs)
--   - Improved medication date coverage from 16% to ~89%
--   - Created standalone reference views for reusability
--
-- SOURCE:
--   RADIANT Unified Chemotherapy Index
--   /Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index/
-- ================================================================================

-- ================================================================================
-- STEP 1: Deploy Chemotherapy Reference Views
-- ================================================================================

-- Execute the following files in order:
-- 1. V_CHEMOTHERAPY_DRUGS.sql
-- 2. V_CHEMOTHERAPY_RXNORM_CODES.sql
-- 3. V_CHEMOTHERAPY_REGIMENS.sql
-- 4. V_CHEMOTHERAPY_REGIMEN_COMPONENTS.sql

-- NOTE: These files are too large to include inline. Execute them separately from:
--   /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/

-- ================================================================================
-- STEP 2: Deploy v_chemo_medications (Optional but Recommended)
-- ================================================================================

-- Execute V_CHEMO_MEDICATIONS.sql
-- This view identifies ALL chemotherapy medications from FHIR data using the
-- comprehensive reference. It can be used independently or as a building block.

-- ================================================================================
-- STEP 3: Deploy Updated v_concomitant_medications
-- ================================================================================

-- The updated v_concomitant_medications is included in DATETIME_STANDARDIZED_VIEWS.sql
-- Execute the entire DATETIME_STANDARDIZED_VIEWS.sql file to deploy all updated views.

-- ================================================================================
-- VERIFICATION QUERIES
-- ================================================================================

-- After deployment, verify the views are working correctly:

-- 1. Verify v_chemotherapy_drugs
SELECT COUNT(*) as total_drugs,
       COUNT(DISTINCT rxnorm_in) as unique_rxnorm_codes,
       SUM(CASE WHEN approval_status = 'FDA_approved' THEN 1 ELSE 0 END) as fda_approved,
       SUM(CASE WHEN approval_status = 'investigational' THEN 1 ELSE 0 END) as investigational
FROM fhir_prd_db.v_chemotherapy_drugs;
-- Expected: 3064 total, 814 RxNorm codes, 838 FDA-approved, 2226 investigational

-- 2. Verify v_chemotherapy_rxnorm_codes
SELECT COUNT(*) as total_mappings,
       COUNT(DISTINCT product_rxnorm_code) as unique_products,
       COUNT(DISTINCT ingredient_rxnorm_code) as unique_ingredients
FROM fhir_prd_db.v_chemotherapy_rxnorm_codes;
-- Expected: 2804 mappings, 2337 products, 412 ingredients

-- 3. Verify bevacizumab fix
SELECT * FROM fhir_prd_db.v_chemotherapy_drugs
WHERE preferred_name = 'bevacizumab';
-- Expected: rxnorm_in = '253337' (NOT '42316')

-- 4. Verify v_concomitant_medications uses comprehensive reference
SELECT COUNT(*) as total_records,
       COUNT(DISTINCT chemo_rxnorm_cui) as unique_chemo_drugs,
       COUNT(DISTINCT patient_fhir_id) as unique_patients
FROM fhir_prd_db.v_concomitant_medications;
-- Expected: More drugs than before (was limited to 11 hardcoded)

-- 5. Test patient-specific query
SELECT
    chemo_preferred_name,
    chemo_rxnorm_cui,
    match_type,
    COUNT(*) as conmed_count
FROM fhir_prd_db.v_concomitant_medications
WHERE patient_fhir_id = 'Patient/EXAMPLE'  -- Replace with actual patient ID
GROUP BY chemo_preferred_name, chemo_rxnorm_cui, match_type
ORDER BY conmed_count DESC;

-- ================================================================================
-- ROLLBACK PROCEDURE (IF NEEDED)
-- ================================================================================

-- If you need to rollback to the old version with 11 hardcoded drugs:
-- 1. Execute the old ATHENA_VIEW_CREATION_QUERIES.sql or
-- 2. Execute CONCOMITANT_MEDICATIONS_VIEW.sql (if it contains the old version)

-- To drop the new reference views:
-- DROP VIEW IF EXISTS fhir_prd_db.v_chemotherapy_drugs;
-- DROP VIEW IF EXISTS fhir_prd_db.v_chemotherapy_rxnorm_codes;
-- DROP VIEW IF EXISTS fhir_prd_db.v_chemotherapy_regimens;
-- DROP VIEW IF EXISTS fhir_prd_db.v_chemotherapy_regimen_components;
-- DROP VIEW IF EXISTS fhir_prd_db.v_chemo_medications;

-- ================================================================================
-- DEPLOYMENT CHECKLIST
-- ================================================================================

-- [ ] 1. Deploy v_chemotherapy_drugs
-- [ ] 2. Deploy v_chemotherapy_rxnorm_codes
-- [ ] 3. Deploy v_chemotherapy_regimens
-- [ ] 4. Deploy v_chemotherapy_regimen_components
-- [ ] 5. Deploy v_chemo_medications (optional)
-- [ ] 6. Deploy DATETIME_STANDARDIZED_VIEWS.sql (includes updated v_concomitant_medications)
-- [ ] 7. Run verification queries
-- [ ] 8. Test with sample patient queries
-- [ ] 9. Update documentation
-- [ ] 10. Commit changes to Git

-- ================================================================================
-- END OF DEPLOYMENT SCRIPT
-- ================================================================================
