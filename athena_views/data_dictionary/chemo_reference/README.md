# Comprehensive Chemotherapy Reference Data

## Overview

This directory contains the comprehensive chemotherapy drug reference extracted from the **RADIANT Unified Chemotherapy Index**, providing a single source of truth for chemotherapy drug identification and matching across all RADIANT systems.

## Source

- **Primary Source**: `/Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index/`
- **Generated**: 2025-01-XX
- **Total Scope**: 3,067 drugs (838 FDA-approved, 2,226 investigational, 3 supportive care)

## Files in This Directory

### CSV Data Files

1. **chemotherapy_drugs.csv** (3,064 drugs)
   - ALL chemotherapy and targeted therapy drugs (FDA-approved + investigational)
   - Excludes supportive care medications (anti-emetics, etc.)
   - Fields: `drug_id`, `preferred_name`, `approval_status`, `rxnorm_in`, `ncit_code`, `normalized_key`, `sources`
   - **Coverage**: 814 drugs with RxNorm codes (26.6%), 216 with NCIt codes (7.0%)

2. **chemotherapy_rxnorm_mappings.csv** (2,804 mappings)
   - RxNorm product code → ingredient code mappings
   - **CRITICAL**: Enables matching medications coded at product/brand level
   - Fields: `code_cui` (product code), `code_tty` (term type), `ingredient_rxcui`, `ingredient_drug_id`
   - **Coverage**: 2,337 unique product codes mapping to 412 ingredient codes

3. **chemotherapy_aliases.csv** (23,785 aliases)
   - Drug name aliases for fuzzy/NLP matching
   - Fields: `drug_id`, `alias`, `alias_type`, `source`, `source_ref`, `normalized_key`
   - **Coverage**: 609 drugs with aliases

4. **chemotherapy_regimens.csv** (22 regimens)
   - Standard chemotherapy regimens (e.g., FOLFOX, R-CHOP)
   - Fields: `regimen_id`, `acronym`, `label`, `approval_status`, `notes`

5. **chemotherapy_regimen_components.csv** (75 components)
   - Drug components that comprise each regimen
   - Fields: `regimen_id`, `order_index`, `component_drug_id`, `component_name_original`, `component_role`

### Legacy Files (Superseded)

6. **chemotherapy_ingredient_reference.csv** (814 drugs)
   - **DEPRECATED**: Use `chemotherapy_drugs.csv` instead
   - Contains only FDA-approved drugs with RxNorm codes
   - Kept for backward compatibility

## Generated Athena SQL Views

The following SQL view definitions have been generated in `../../views/`:

### 1. v_chemotherapy_drugs
- **File**: `V_CHEMOTHERAPY_DRUGS.sql`
- **Records**: 3,064 drugs (FDA-approved + investigational)
- **Purpose**: Primary drug reference with all identifiers and metadata
- **Key Fields**: `drug_id`, `preferred_name`, `approval_status`, `rxnorm_in`, `ncit_code`

### 2. v_chemotherapy_rxnorm_codes
- **File**: `V_CHEMOTHERAPY_RXNORM_CODES.sql`
- **Records**: 2,804 product→ingredient mappings
- **Purpose**: Enable matching of branded/formulation-specific RxNorm codes
- **Key Fields**: `product_rxnorm_code`, `term_type`, `ingredient_rxnorm_code`
- **Critical**: Without this, medications coded at product level would be missed!

### 3. v_chemotherapy_regimens
- **File**: `V_CHEMOTHERAPY_REGIMENS.sql`
- **Records**: 22 standard regimens
- **Purpose**: Reference for standard chemotherapy regimen identification
- **Key Fields**: `regimen_id`, `acronym`, `label`

### 4. v_chemotherapy_regimen_components
- **File**: `V_CHEMOTHERAPY_REGIMEN_COMPONENTS.sql`
- **Records**: 75 regimen components
- **Purpose**: Drug→regimen mapping for regimen reconstruction
- **Key Fields**: `regimen_id`, `component_drug_id`, `component_role`

### 5. v_chemotherapy_aliases (Not Generated)
- **Status**: Skipped - 23,785 aliases too large for VALUES clause
- **Recommendation**: Use external table or CTAS approach if needed

## Data Dictionary

### drug_id
- **Type**: String
- **Format**: `rx:RXNORM_CODE` (e.g., `rx:253337.0`)
- **Description**: Unique identifier for the drug, typically based on RxNorm ingredient code

### preferred_name
- **Type**: String
- **Description**: Standardized drug name (typically generic name)
- **Example**: `bevacizumab`, `carboplatin`, `temozolomide`

### approval_status
- **Type**: Enum
- **Values**: `FDA_approved`, `investigational`
- **Coverage**:
  - FDA_approved: 838 drugs (97.1% have RxNorm codes)
  - Investigational: 2,226 drugs (0% have RxNorm codes)

### rxnorm_in
- **Type**: Integer (RxNorm ingredient code)
- **Coverage**: 814 out of 3,064 drugs (26.6%)
- **Description**: RxNorm ingredient-level code (NOT product code)
- **Example**: `253337` for bevacizumab ingredient

### ncit_code
- **Type**: String (NCIt concept code)
- **Coverage**: 216 out of 3,064 drugs (7.0%)
- **Description**: NCI Thesaurus concept identifier
- **Example**: `C2039` for bevacizumab

### normalized_key
- **Type**: String
- **Description**: Normalized drug name for matching (lowercase, no spaces/punctuation)
- **Example**: `bevacizumab` → `bevacizumab`

### sources
- **Type**: String (pipe-delimited list)
- **Description**: Source datasets that contributed this drug
- **Example**: `hem_onc|fda_v24|investigational_v24`

## Key Insights

### RxNorm Code Coverage

**Ingredient Codes (814 total)**:
- Only FDA-approved drugs have RxNorm ingredient codes
- Investigational drugs have NO RxNorm codes (use NCIt or name matching instead)

**Product Codes (2,804 mappings)**:
- Maps branded/formulation-specific codes to ingredient codes
- Example: Various Avastin formulations → bevacizumab (253337)
- **Critical for FHIR medication matching** where coding may be product-level

### Bevacizumab Fix

**Historical Issue**: v_concomitant_medications had WRONG RxNorm code
- **Incorrect**: `42316` (does not exist in reference)
- **Correct**: `253337` (verified in unified index)

### Supportive Care Exclusion

**Excluded Drugs** (3 total):
- fosaprepitant (RxNorm: 1731071)
- lorazepam (RxNorm: 6470)
- palonosetron (RxNorm: 70561)

**Rationale**: These are anti-emetics/supportive care, NOT chemotherapy agents

## Usage Examples

### Example 1: Match Medication by RxNorm Ingredient Code

```sql
-- Find if medication is chemotherapy
SELECT
    cd.preferred_name,
    cd.approval_status,
    cd.drug_id
FROM fhir_prd_db.medication_request mr
JOIN fhir_prd_db.medication_code_coding mcc
    ON mcc.medication_id = SUBSTRING(mr.medication_reference_reference, 12)
JOIN fhir_prd_db.v_chemotherapy_drugs cd
    ON CAST(mcc.code_coding_code AS VARCHAR) = cd.rxnorm_in
WHERE mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
    AND mr.subject_reference = 'Patient/123'
```

### Example 2: Match Medication by RxNorm Product Code

```sql
-- Match product-level codes to chemotherapy drugs
SELECT
    mcc.code_coding_code AS product_code,
    crc.ingredient_rxnorm_code,
    cd.preferred_name,
    cd.approval_status
FROM fhir_prd_db.medication_request mr
JOIN fhir_prd_db.medication_code_coding mcc
    ON mcc.medication_id = SUBSTRING(mr.medication_reference_reference, 12)
JOIN fhir_prd_db.v_chemotherapy_rxnorm_codes crc
    ON mcc.code_coding_code = crc.product_rxnorm_code
JOIN fhir_prd_db.v_chemotherapy_drugs cd
    ON crc.ingredient_rxnorm_code = cd.rxnorm_in
WHERE mr.subject_reference = 'Patient/123'
```

### Example 3: Identify Regimen from Drug List

```sql
-- Find potential regimens based on drugs administered
WITH patient_chemo_drugs AS (
    SELECT DISTINCT cd.drug_id
    FROM fhir_prd_db.medication_request mr
    JOIN fhir_prd_db.medication_code_coding mcc
        ON mcc.medication_id = SUBSTRING(mr.medication_reference_reference, 12)
    JOIN fhir_prd_db.v_chemotherapy_drugs cd
        ON CAST(mcc.code_coding_code AS VARCHAR) = cd.rxnorm_in
    WHERE mr.subject_reference = 'Patient/123'
)
SELECT
    cr.regimen_id,
    cr.acronym,
    cr.label,
    COUNT(DISTINCT crc.component_drug_id) AS matched_components,
    COUNT(DISTINCT pcd.drug_id) AS patient_drugs
FROM fhir_prd_db.v_chemotherapy_regimens cr
JOIN fhir_prd_db.v_chemotherapy_regimen_components crc
    ON crc.regimen_id = cr.regimen_id
JOIN patient_chemo_drugs pcd
    ON pcd.drug_id = crc.component_drug_id
GROUP BY cr.regimen_id, cr.acronym, cr.label
HAVING matched_components >= 2  -- At least 2 drugs from regimen
ORDER BY matched_components DESC
```

## Next Steps

### Immediate Actions Required

1. **Update v_concomitant_medications** in [DATETIME_STANDARDIZED_VIEWS.sql](../../views/DATETIME_STANDARDIZED_VIEWS.sql):
   - Replace 11 hardcoded RxNorm codes with JOIN to v_chemotherapy_drugs
   - Fix bevacizumab code from 42316 to 253337
   - Add support for product→ingredient mapping via v_chemotherapy_rxnorm_codes

2. **Deploy New Views** to Athena production:
   ```bash
   # Execute in Athena console or via AWS CLI
   aws athena start-query-execution \
       --query-string file://../../views/V_CHEMOTHERAPY_DRUGS.sql \
       --query-execution-context Database=fhir_prd_db \
       --result-configuration OutputLocation=s3://your-results-bucket/
   ```

3. **Update ChemotherapyFilter** class in build_timeline_database.py:
   - Already uses comprehensive reference correctly (814 drugs)
   - No changes needed

### Future Enhancements

1. **Create v_chemotherapy_aliases external table** for name-based matching
2. **Add medication_timing_bounds improvement** to increase date coverage to 88.6%
3. **Implement comprehensive medication extraction** following radiation extraction pattern
4. **Build automated regimen detection** based on temporal clustering of drug administrations

## Maintenance

### Updating the Reference

When the RADIANT unified chemotherapy index is updated:

1. Re-run extraction script from unified_chemo_index directory
2. Regenerate CSV files in this directory
3. Regenerate SQL view definitions
4. Deploy updated views to Athena
5. Verify backward compatibility with existing queries

### Version History

- **v1.0** (2025-01-XX): Initial comprehensive extraction
  - 3,064 drugs, 2,804 RxNorm mappings, 22 regimens
  - Fixed bevacizumab RxNorm code
  - Separated chemotherapy from supportive care

## Contact

For questions or issues with this reference data:
- See original unified index documentation at `/Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index/`
- Review chemotherapy filter implementation at `../chemotherapy_filter.py`
