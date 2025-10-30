# OID Decoding Workflow Guide

**Purpose:** Step-by-step guide for implementing systematic OID decoding across all FHIR views
**Audience:** Data analysts, SQL developers, and view maintainers
**Last Updated:** 2025-10-29

---

## Table of Contents

1. [Overview](#overview)
2. [The OID Decoding Pattern](#the-oid-decoding-pattern)
3. [Step-by-Step Implementation Workflow](#step-by-step-implementation-workflow)
4. [Extending to New Views](#extending-to-new-views)
5. [Maintenance and Discovery](#maintenance-and-discovery)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Overview

### What is OID Decoding?

**Problem:**
```sql
-- Hard to understand
WHERE code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'
```

**Solution:**
```sql
-- Self-documenting with decoded columns
WHERE pcc_coding_system_code = 'EAP'  -- Epic Procedure Masterfile
```

### Benefits

1. **Improved Readability** - See "CPT" or "EAP" instead of long URIs
2. **Faster Troubleshooting** - Instantly know if it's Epic or standard coding
3. **Better Onboarding** - New analysts reference central OID registry
4. **Data Quality** - Alert on unexpected or undocumented OIDs

### Architecture

```
┌─────────────────────┐
│  v_oid_reference    │  ← Central OID registry (20+ OIDs documented)
└──────────┬──────────┘
           │ LEFT JOIN
           ↓
┌─────────────────────┐
│  Your FHIR View     │  ← Add 3 decoded columns
│  (procedures, meds, │     - coding_system_code
│   diagnoses, etc.)  │     - coding_system_name
└─────────────────────┘     - coding_system_source
```

---

## The OID Decoding Pattern

### Epic CHOP OID Structure

```
urn:oid:1.2.840.114350.1.13.<CID>.<EnvType>.7.<Type>.<ASCII_Masterfile>.<Item>
        └─────┬─────┘ │  │  │  │  │  │ │ └─────┬──────┘ └──────┬──────┘
         Epic Root    │  │  │  │  │  │ │       │                │
                 App Type │  │  │  │  │ │  Masterfile      Item Number
                          │  │  │  │  │ │   (ASCII)        (Optional)
                     App ID │  │  │  │ │
                       (13=EDI)  │  │  │
                           CHOP │  │  │
                         (CID=20) │  │
                              Env │  │
                           (2=Prod) │
                              HL7  │
                            (7=Yes)
                                Value
```

### ASCII Decoding Table

| ASCII Code | Letter | Example Masterfile |
|------------|--------|-------------------|
| 69 | E | **E**AP, **E**RX |
| 65 | A | E**A**P |
| 80 | P | EA**P** |
| 79 | O | **O**RD, **O**RT |
| 82 | R | O**R**D, E**R**X, O**R**T, SE**R** |
| 68 | D | OR**D**, **D**EP |
| 88 | X | ER**X** |
| 67 | C | **C**SN |
| 83 | S | C**S**N, **S**ER |
| 78 | N | CS**N** |

### Common CHOP OIDs

| OID | Decoded | Full Name | Usage |
|-----|---------|-----------|-------|
| `.696580` | **EAP** | Epic Ambulatory Procedures | Procedure masterfile |
| `.798268` | **ORD** | Orders | Order masterfile |
| `.698288` | **ERX** | Prescriptions | Medication masterfile |
| `.678367` | **CSN** | Contact Serial Number | Encounter ID |
| `.686980` | **DEP** | Department | Location/department |
| `.837982` | **SER** | Service/Provider | Clinician ID |

---

## Step-by-Step Implementation Workflow

### Phase 1: Discovery (Always Do This First!)

**Step 1.1: Identify the target view and its coding system columns**

```sql
-- Example: Find all code_coding_system columns in a view
DESCRIBE fhir_prd_db.v_chemo_medications;

-- Look for columns like:
-- - code_coding_system
-- - medication_code_system
-- - ingredient_coding_system
```

**Step 1.2: Discover what OIDs are actually used**

```sql
-- Discovery Query: What OIDs are in production?
SELECT DISTINCT
    code_coding_system as oid_uri,
    COUNT(*) as usage_count,
    COUNT(DISTINCT patient_id) as patient_count
FROM fhir_prd_db.medication_request_code_coding  -- Change table as needed
WHERE code_coding_system IS NOT NULL
GROUP BY code_coding_system
ORDER BY usage_count DESC;
```

**Step 1.3: Check which OIDs are already documented**

```sql
-- Validation Query: Compare production vs v_oid_reference
WITH production_oids AS (
    SELECT DISTINCT code_coding_system as oid_uri, COUNT(*) as cnt
    FROM fhir_prd_db.medication_request_code_coding
    WHERE code_coding_system IS NOT NULL
    GROUP BY code_coding_system
)
SELECT
    po.oid_uri,
    po.cnt,
    CASE
        WHEN vr.oid_uri IS NULL THEN '❌ NEEDS DOCUMENTATION'
        WHEN vr.is_verified = FALSE THEN '⚡ NEEDS VERIFICATION'
        ELSE '✅ ALREADY DOCUMENTED'
    END as status,
    vr.masterfile_code,
    vr.description
FROM production_oids po
LEFT JOIN fhir_prd_db.v_oid_reference vr ON po.oid_uri = vr.oid_uri
ORDER BY status, cnt DESC;
```

**Step 1.4: Document any missing OIDs**

For undocumented OIDs:

**If Epic OID:** Decode using ASCII
```sql
-- Decode Epic OID
SELECT
    'urn:oid:1.2.840.114350.1.13.20.2.7.2.798276' as oid,
    REGEXP_EXTRACT('urn:oid:1.2.840.114350.1.13.20.2.7.2.798276', '\.(\d{6})(?:\.|$)', 1) as ascii_code,
    CHR(79) || CHR(82) || CHR(84) as decoded  -- = 'ORT'
FROM dual;
```

**If Standard OID:** Look up at https://oid-base.com/ or https://www.hl7.org/oid/

**Step 1.5: Add missing OIDs to v_oid_reference**

```sql
-- Example: Add new OID to v_oid_reference.sql
('urn:oid:2.16.840.1.113883.6.208', 'Standard', 'FDBH', 'NDDF', 'Medication', NULL,
 'National Drug Data File',
 'Drug formulary and clinical screening system.',
 'medication_request_code_coding', TRUE),
```

---

### Phase 2: Add OID Decoding to View

**Step 2.1: Add comment header documenting OIDs used**

```sql
-- ============================================================================
-- CODING SYSTEMS USED IN v_chemo_medications
-- ============================================================================
-- Epic CHOP OIDs:
--   urn:oid:1.2.840.114350.1.13.20.2.7.2.698288 = ERX .1 (Medication Masterfile)
--
-- Standard OIDs:
--   http://www.nlm.nih.gov/research/umls/rxnorm = RxNorm medication codes
--   urn:oid:2.16.840.1.113883.6.208 = NDDF (National Drug Data File)
--
-- Reference: See v_oid_reference view for complete OID documentation
-- ============================================================================
```

**Step 2.2: Add oid_reference CTE to view**

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_chemo_medications AS
WITH
-- ============================================================================
-- OID Reference: Decode coding systems to human-readable labels
-- ============================================================================
oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),

-- ... rest of your CTEs ...
```

**Step 2.3: Add decoded columns to SELECT clause**

Find where the coding system columns are selected and add decoded columns after them:

```sql
SELECT
    -- Existing columns
    mrc.code_coding_system,
    mrc.code_coding_code,
    mrc.code_coding_display,

    -- NEW: OID Decoding columns
    oid_med.masterfile_code as medication_coding_system_code,
    oid_med.description as medication_coding_system_name,
    oid_med.oid_source as medication_coding_system_source,

    -- ... rest of columns ...
```

**Step 2.4: Add JOIN to oid_reference**

In the FROM/JOIN section:

```sql
FROM fhir_prd_db.medication_request mr
LEFT JOIN fhir_prd_db.medication_request_code_coding mrc ON mr.id = mrc.medication_request_id

-- NEW: OID Decoding JOIN
LEFT JOIN oid_reference oid_med ON mrc.code_coding_system = oid_med.oid_uri

-- ... rest of joins ...
```

**Step 2.5: Deploy and test**

```bash
# Deploy updated view
/tmp/run_query.sh /path/to/your/view.sql

# Test OID decoding
SELECT
    code_coding_system,
    medication_coding_system_code,
    medication_coding_system_name,
    COUNT(*) as cnt
FROM fhir_prd_db.v_chemo_medications
WHERE code_coding_system IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY cnt DESC;
```

---

### Phase 3: Validation and Documentation

**Step 3.1: Validate 100% coverage**

```sql
-- Should return NO rows if all OIDs are documented
SELECT DISTINCT
    code_coding_system,
    medication_coding_system_code,
    medication_coding_system_name
FROM fhir_prd_db.v_chemo_medications
WHERE code_coding_system IS NOT NULL
  AND medication_coding_system_code IS NULL;  -- Undocumented OIDs
```

**Step 3.2: Document the enhancement**

Update your view's documentation with:
- List of OIDs used
- New decoded columns added
- Usage examples

**Step 3.3: Create usage examples**

```sql
-- Example 1: Filter by coding system
SELECT * FROM v_chemo_medications
WHERE medication_coding_system_code = 'RxNorm';

-- Example 2: Compare Epic vs Standard coding
SELECT
    medication_coding_system_source,
    COUNT(*) as medication_count
FROM v_chemo_medications
GROUP BY medication_coding_system_source;
```

---

## Extending to New Views

### View-Specific Patterns

Each FHIR resource type may have different coding system columns. Here's how to handle common cases:

### 1. Procedure Views (procedure_code_coding)

```sql
-- Columns to add:
pcc_coding_system_code          -- Short code (CPT, EAP, CDT-2)
pcc_coding_system_name          -- Full name
pcc_coding_system_source        -- Epic or Standard

-- JOIN pattern:
LEFT JOIN oid_reference oid_pc ON pc.code_coding_system = oid_pc.oid_uri

-- Common OIDs:
-- CPT, EAP, CDT-2, HCPCS, LOINC
```

### 2. Medication Views (medication_request_code_coding)

```sql
-- Columns to add:
medication_coding_system_code    -- Short code (RxNorm, NDDF, ERX)
medication_coding_system_name    -- Full name
medication_coding_system_source  -- Epic or Standard

-- JOIN pattern:
LEFT JOIN oid_reference oid_med ON mrc.code_coding_system = oid_med.oid_uri

-- Common OIDs:
-- RxNorm, NDDF, ERX (Epic medication masterfile), NDC
```

### 3. Diagnosis/Condition Views (condition_code_coding)

```sql
-- Columns to add:
condition_coding_system_code     -- Short code (ICD-10-CM, SNOMED CT)
condition_coding_system_name     -- Full name
condition_coding_system_source   -- Epic or Standard

-- JOIN pattern:
LEFT JOIN oid_reference oid_cond ON cc.code_coding_system = oid_cond.oid_uri

-- Common OIDs:
-- ICD-10-CM, SNOMED CT
```

### 4. Laboratory/Observation Views (observation_code_coding)

```sql
-- Columns to add:
observation_coding_system_code   -- Short code (LOINC)
observation_coding_system_name   -- Full name
observation_coding_system_source -- Epic or Standard

-- JOIN pattern:
LEFT JOIN oid_reference oid_obs ON oc.code_coding_system = oid_obs.oid_uri

-- Common OIDs:
-- LOINC (primary), SNOMED CT
```

### 5. Multiple Coding Systems in One View

Some views may have multiple code_coding_system columns (e.g., medication + ingredient):

```sql
SELECT
    -- Medication coding system
    mrc.medication_code_system,
    oid_med.masterfile_code as medication_system_code,
    oid_med.description as medication_system_name,

    -- Ingredient coding system
    ing.ingredient_code_system,
    oid_ing.masterfile_code as ingredient_system_code,
    oid_ing.description as ingredient_system_name

FROM medication_request mr
LEFT JOIN oid_reference oid_med ON mrc.medication_code_system = oid_med.oid_uri
LEFT JOIN oid_reference oid_ing ON ing.ingredient_code_system = oid_ing.oid_uri
```

---

## Maintenance and Discovery

### Regular OID Discovery Process

Run this monthly to discover new OIDs:

```sql
-- Monthly OID Discovery Report
WITH all_tables AS (
    SELECT 'procedure_code_coding' as table_name,
           code_coding_system as oid,
           COUNT(*) as cnt
    FROM fhir_prd_db.procedure_code_coding
    WHERE code_coding_system IS NOT NULL
    GROUP BY code_coding_system

    UNION ALL

    SELECT 'condition_code_coding', code_coding_system, COUNT(*)
    FROM fhir_prd_db.condition_code_coding
    WHERE code_coding_system IS NOT NULL
    GROUP BY code_coding_system

    -- Add other tables as needed
)
SELECT
    at.table_name,
    at.oid,
    at.cnt,
    CASE
        WHEN vr.oid_uri IS NULL THEN '⚠️ NEW - ADD TO v_oid_reference'
        ELSE '✓ Documented'
    END as status,
    vr.masterfile_code,
    vr.description
FROM all_tables at
LEFT JOIN fhir_prd_db.v_oid_reference vr ON at.oid = vr.oid_uri
WHERE vr.oid_uri IS NULL  -- Only show undocumented
ORDER BY at.cnt DESC;
```

### Adding New OIDs to v_oid_reference

**Epic OIDs:**
1. Extract ASCII code: Last 6 digits before optional item number
2. Decode to letters: CHR(69)=E, CHR(65)=A, CHR(80)=P = **EAP**
3. Identify masterfile purpose (Procedure, Order, Medication, etc.)
4. Add to v_oid_reference.sql

**Standard OIDs:**
1. Look up at https://oid-base.com/ or https://www.hl7.org/oid/
2. Identify issuing organization (AMA, NLM, WHO, etc.)
3. Get full name and description
4. Add to v_oid_reference.sql

**Template for adding:**
```sql
-- In v_oid_reference.sql VALUES clause:
('<oid_uri>', '<source>', '<organization>', '<code>', '<category>', '<item_number>',
 '<description>',
 '<technical_notes>',
 '<common_fhir_tables>', <is_verified>),
```

**Example:**
```sql
('urn:oid:2.16.840.1.113883.6.96', 'Standard', 'IHTSDO', 'SNOMED CT', 'Clinical', NULL,
 'Systematized Nomenclature of Medicine Clinical Terms',
 'Comprehensive clinical terminology system covering diagnoses, procedures, findings.',
 'condition_code_coding, procedure_code_coding, observation_code_coding', TRUE),
```

---

## Troubleshooting

### Issue 1: New OID appears in production

**Symptoms:**
```sql
SELECT * FROM v_procedures_tumor
WHERE pcc_coding_system_code IS NULL
  AND pcc_code_coding_system IS NOT NULL;
-- Returns rows
```

**Solution:**
1. Run discovery query to identify the OID
2. Research the OID (Epic ASCII decode or OID repository lookup)
3. Add to v_oid_reference.sql
4. Redeploy v_oid_reference
5. No need to redeploy views (they JOIN dynamically)

### Issue 2: OID decoding showing wrong information

**Symptoms:**
```sql
-- OID shows as 'CPT' but it's actually Epic code
```

**Solution:**
1. Check v_oid_reference for duplicate or incorrect entries
2. Verify OID URI exactly matches (including urn:oid: prefix)
3. Update v_oid_reference with correct information
4. Redeploy v_oid_reference

### Issue 3: Performance degradation after adding OID decoding

**Symptoms:**
- View queries slower after adding OID JOIN

**Solution:**
1. OID reference is small (~20-50 rows) so impact should be minimal
2. Ensure LEFT JOIN (not INNER JOIN) to preserve all rows
3. Consider materializing v_oid_reference if it grows large
4. Check query execution plan for unexpected behavior

### Issue 4: Epic OID not decoding correctly

**Symptoms:**
```sql
-- ASCII decode shows gibberish
-- Example: 123456 → "♣♥♦" (invalid characters)
```

**Solution:**
1. Verify it's actually an Epic OID (starts with 1.2.840.114350.1.13.20)
2. Check CHOP site code is 20 (not 266 or other sites)
3. Manually decode: 79=O, 82=R, 68=D
4. Confirm with Epic team if unsure

---

## Best Practices

### DO ✅

1. **Always discover before documenting**
   - Run discovery queries against production first
   - Don't assume which OIDs are used

2. **Validate after implementation**
   - Check for NULL decoded columns
   - Confirm 100% coverage

3. **Document OIDs at view level**
   - Add comment header listing OIDs used
   - Makes views self-documenting

4. **Use consistent naming**
   - `<resource>_coding_system_code`
   - `<resource>_coding_system_name`
   - `<resource>_coding_system_source`

5. **Set is_verified flag appropriately**
   - TRUE: Confirmed in production and researched
   - FALSE: Needs Epic team verification

6. **Keep v_oid_reference focused**
   - Only add OIDs actually used in production
   - Don't add hypothetical OIDs

### DON'T ❌

1. **Don't hard-code decoded values in views**
   ```sql
   -- BAD: Hard-coded
   CASE WHEN code_coding_system = 'urn:oid:...' THEN 'EAP' END

   -- GOOD: JOIN to v_oid_reference
   LEFT JOIN oid_reference ON code_coding_system = oid_uri
   ```

2. **Don't skip validation**
   - Always check if decoded columns are NULL
   - Run validation query after deployment

3. **Don't assume OID meanings**
   - Look up standard OIDs in OID repository
   - Verify Epic OIDs with Epic team

4. **Don't break backward compatibility**
   - Always keep original columns
   - Add decoded columns as new columns

5. **Don't forget to update documentation**
   - Update view documentation when adding OID decoding
   - Document new columns in README/wiki

---

## Implementation Checklist

Use this checklist for each new view:

### Discovery Phase
- [ ] Identify coding system columns in target view
- [ ] Run discovery query to find production OIDs
- [ ] Compare against v_oid_reference to find gaps
- [ ] Research undocumented OIDs
- [ ] Add new OIDs to v_oid_reference.sql
- [ ] Deploy updated v_oid_reference

### Implementation Phase
- [ ] Add OID comment header to view
- [ ] Add oid_reference CTE
- [ ] Add 3 decoded columns to SELECT
- [ ] Add LEFT JOIN to oid_reference
- [ ] Deploy updated view
- [ ] Test OID decoding with sample queries

### Validation Phase
- [ ] Run validation query (check for NULLs)
- [ ] Confirm 100% OID coverage
- [ ] Test filtering by decoded columns
- [ ] Update view documentation
- [ ] Create usage examples
- [ ] Commit to version control

---

## Quick Reference Card

### Common Commands

```bash
# Deploy v_oid_reference
/tmp/run_query.sh athena_views/views/v_oid_reference.sql

# Deploy updated view
/tmp/run_query.sh athena_views/views/v_your_view.sql

# Run validation
/tmp/run_query.sh athena_views/testing/validate_oid_usage.sql
```

### Common Queries

```sql
-- Discover OIDs in a table
SELECT DISTINCT code_coding_system, COUNT(*)
FROM fhir_prd_db.<table_name>
WHERE code_coding_system IS NOT NULL
GROUP BY code_coding_system;

-- Check v_oid_reference
SELECT * FROM fhir_prd_db.v_oid_reference
WHERE oid_source = 'Epic' OR masterfile_code IN ('CPT', 'RxNorm');

-- Validate OID coverage in a view
SELECT DISTINCT code_coding_system, coding_system_code
FROM fhir_prd_db.<view_name>
WHERE code_coding_system IS NOT NULL
  AND coding_system_code IS NULL;  -- Should be empty
```

### ASCII Decode Helper

```
69='E'  79='O'  67='C'  83='S'
65='A'  82='R'  68='D'  78='N'
80='P'  88='X'  84='T'

EAP = 696580  (Epic Ambulatory Procedures)
ORD = 798268  (Orders)
ERX = 698288  (Prescriptions)
CSN = 678367  (Contact Serial Number)
DEP = 686980  (Department)
SER = 837982  (Service/Provider)
```

---

## Example: Complete Implementation

Here's a complete example applying OID decoding to v_chemo_medications:

```sql
-- ============================================================================
-- CODING SYSTEMS USED IN v_chemo_medications
-- ============================================================================
-- Epic CHOP OIDs:
--   urn:oid:1.2.840.114350.1.13.20.2.7.2.698288 = ERX .1 (Medication Masterfile)
--
-- Standard OIDs:
--   http://www.nlm.nih.gov/research/umls/rxnorm = RxNorm medication codes
--   urn:oid:2.16.840.1.113883.6.208 = NDDF (National Drug Data File)
--
-- Reference: See v_oid_reference view for complete OID documentation
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_chemo_medications AS
WITH
-- ============================================================================
-- OID Reference: Decode coding systems to human-readable labels
-- ============================================================================
oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),

-- ... existing CTEs ...

medication_codes AS (
    SELECT
        mrc.medication_request_id,
        mrc.code_coding_system,
        mrc.code_coding_code,
        mrc.code_coding_display
    FROM fhir_prd_db.medication_request_code_coding mrc
)

SELECT
    mr.id as medication_request_id,
    mr.patient_reference,

    -- Original coding system columns
    mc.code_coding_system,
    mc.code_coding_code,
    mc.code_coding_display,

    -- NEW: OID Decoding columns
    oid_med.masterfile_code as medication_coding_system_code,
    oid_med.description as medication_coding_system_name,
    oid_med.oid_source as medication_coding_system_source,

    -- ... rest of columns ...

FROM fhir_prd_db.medication_request mr
LEFT JOIN medication_codes mc ON mr.id = mc.medication_request_id

-- NEW: OID Decoding JOIN
LEFT JOIN oid_reference oid_med ON mc.code_coding_system = oid_med.oid_uri

-- ... rest of joins ...
;
```

---

## Additional Resources

- **OID Repository:** https://oid-base.com/
- **HL7 OID Registry:** https://www.hl7.org/oid/
- **Epic Vendor Services:** https://vendorservices.epic.com/Article?docId=epicidtypes
- **Internal Documentation:**
  - `OID_USAGE_ANALYSIS_AND_RECOMMENDATIONS.md`
  - `OID_VALIDATION_REPORT.md`
  - `OID_IMPLEMENTATION_SUMMARY.md`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-29 | Initial comprehensive workflow guide |

---

## Feedback and Updates

This is a living document. If you:
- Discover new OID patterns
- Find issues with the workflow
- Have suggestions for improvement

Please update this guide and commit to version control!
