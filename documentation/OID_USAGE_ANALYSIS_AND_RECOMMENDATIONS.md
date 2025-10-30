# Epic OID Usage Analysis and Recommendations

**Date:** 2025-10-29
**Purpose:** Evaluate current OID usage patterns and recommend systematic improvements

---

## Executive Summary

We are currently using OIDs correctly but **inconsistently** across our views. We should adopt a more systematic approach to:
1. Create reusable OID reference tables/CTEs
2. Add decoded masterfile annotations to our views
3. Improve documentation with human-readable labels
4. Enable easier troubleshooting and validation

---

## Understanding Epic OIDs for CHOP

### CHOP's OID Structure

Based on your analyst's notes and Epic's documentation:

```
urn:oid:1.2.840.114350.1.13.20.2.7.2.<ASCII_MASTERFILE>.<ITEM_NUMBER>
         └─────┬─────┘ │  │  │  │  │ │ └─────┬──────┘ └──────┬──────┘
               │       │  │  │  │  │ │       │                │
         Epic Root     │  │  │  │  │ │  Masterfile      Item Number
                  App Type │  │  │  │ │   (ASCII)        (Optional)
                           │  │  │  │ │
                      App ID │  │  │ │
                        (13=EDI)  │  │
                              CHOP │  │
                            (CID=20) │
                                 Env │
                              (2=Prod)
                                 HL7
                               (7=Yes)
```

### Common CHOP OIDs We Use

| OID | Decoded | Masterfile | Item | Description |
|-----|---------|------------|------|-------------|
| `urn:oid:1.2.840.114350.1.13.20.2.7.2.696580` | **EAP** (69,65,80) | EAP | .1 | Procedure Masterfile ID |
| `urn:oid:1.2.840.114350.1.13.20.2.7.2.798268` | **ORD** (79,82,68) | ORD | .1 | Order Masterfile ID |
| `urn:oid:1.2.840.114350.1.13.20.2.7.2.698288` | **ERX** (69,82,88) | ERX | .1 | Medication Masterfile ID |
| `urn:oid:1.2.840.114350.1.13.20.2.7.3.798268.800` | **ORD** | ORD | 800 | Order External ID |
| `urn:oid:1.2.840.114350.1.13.20.7.7.2.798276` | **ORT** (79,82,84) | ORT | .1 | Order Type? (need to verify) |

### Standard (Non-Epic) OIDs We Use

| OID | System | Description |
|-----|--------|-------------|
| `http://www.ama-assn.org/go/cpt` | CPT | Current Procedural Terminology codes |
| `http://www.nlm.nih.gov/research/umls/rxnorm` | RxNorm | Medication codes |
| `http://snomed.info/sct` | SNOMED CT | Clinical terminology |
| `http://loinc.org` | LOINC | Laboratory observations |
| `http://terminology.hl7.org/CodeSystem/v2-0203` | HL7 v2 | Identifier types (MR, DL, etc.) |

---

## Current Usage Analysis

### What We're Doing Well

1. **Correctly filtering by coding system** in most views:
   ```sql
   -- v_procedures_tumor: CPT codes
   WHERE pcc.code_coding_system = 'http://www.ama-assn.org/go/cpt'

   -- v_procedures_tumor: Epic procedure codes
   WHERE pcc.code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'

   -- v_chemo_medications: RxNorm codes
   WHERE mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
   ```

2. **Consistent OID usage** for the same masterfiles across views

3. **Proper URI format** using `urn:oid:` prefix

### What We're Missing

1. **No OID reference documentation** - Analysts must manually decode or search Slack
2. **No masterfile decoding** in views - We see OIDs but not what they mean
3. **Inconsistent commenting** - Some views explain OIDs, others don't
4. **No validation queries** - Hard to check if we're using correct OIDs
5. **No external OID handling** - Missing documentation for non-Epic OIDs (NDDF, etc.)

---

## Recommendations

### 1. Create OID Reference CTE (Reusable Pattern)

Add a standard CTE to views that use multiple coding systems:

```sql
-- ============================================================================
-- OID Reference Table: CHOP Epic Masterfiles
-- Generated from: ASCII encoding of masterfile names
-- CHOP Site Code: 20 (vs UCSF: 266)
-- ============================================================================
oid_reference AS (
    SELECT * FROM (VALUES
        -- Epic Procedure Masterfile (EAP)
        ('urn:oid:1.2.840.114350.1.13.20.2.7.2.696580', 'EAP', 'Procedure',
         'Epic Procedure Masterfile ID', 'ASCII: 69,65,80 = E,A,P'),

        -- Epic Order Masterfile (ORD)
        ('urn:oid:1.2.840.114350.1.13.20.2.7.2.798268', 'ORD', 'Order',
         'Order Masterfile ID', 'ASCII: 79,82,68 = O,R,D'),

        -- Epic Medication Masterfile (ERX)
        ('urn:oid:1.2.840.114350.1.13.20.2.7.2.698288', 'ERX', 'Medication',
         'Medication Masterfile ID', 'ASCII: 69,82,88 = E,R,X'),

        -- Order External ID
        ('urn:oid:1.2.840.114350.1.13.20.2.7.3.798268.800', 'ORD', 'Order',
         'Order External ID', 'Item 800'),

        -- Standard Coding Systems (Non-Epic)
        ('http://www.ama-assn.org/go/cpt', 'CPT', 'Procedure',
         'Current Procedural Terminology', 'AMA standard'),

        ('http://www.nlm.nih.gov/research/umls/rxnorm', 'RxNorm', 'Medication',
         'RxNorm medication codes', 'NLM standard'),

        ('http://snomed.info/sct', 'SNOMED', 'Clinical',
         'SNOMED CT clinical terminology', 'IHTSDO standard'),

        ('http://loinc.org', 'LOINC', 'Laboratory',
         'Logical Observation Identifiers', 'Regenstrief standard')

    ) AS t(oid_uri, masterfile_code, category, description, notes)
)
```

### 2. Add Masterfile Decoding Columns to Views

**Example: Enhanced v_procedures_tumor**

```sql
SELECT
    -- Existing columns...
    pc.code_coding_system,
    pc.code_coding_code,
    pc.code_coding_display,

    -- NEW: Add decoded masterfile information
    oid_ref.masterfile_code,
    oid_ref.category as coding_system_category,
    oid_ref.description as coding_system_description,

    -- NEW: Extract item number from Epic OIDs
    CASE
        WHEN pc.code_coding_system LIKE 'urn:oid:1.2.840.114350.1.13.20.2.7%'
        THEN REGEXP_EXTRACT(pc.code_coding_system, '\.(\d+)$', 1)
        ELSE NULL
    END as epic_item_number

FROM fhir_prd_db.procedure_code_coding pc
LEFT JOIN oid_reference oid_ref ON pc.code_coding_system = oid_ref.oid_uri
```

### 3. Create Standalone OID Reference Table

**File: `athena_views/views/v_oid_reference.sql`**

```sql
-- ============================================================================
-- VIEW: v_oid_reference
-- PURPOSE: Central reference for all OIDs used in CHOP FHIR data
-- USAGE: JOIN to any table with code_coding_system or identifier_system
-- ============================================================================

CREATE OR REPLACE VIEW fhir_prd_db.v_oid_reference AS
SELECT * FROM (VALUES
    -- ========================================================================
    -- Epic CHOP Masterfiles (Site Code: 20)
    -- Structure: 1.2.840.114350.1.13.<CID>.<EnvType>.7.<Type>.<ASCII>.<Item>
    -- ========================================================================

    -- Procedures
    ('urn:oid:1.2.840.114350.1.13.20.2.7.2.696580', 'Epic', 'CHOP', 'EAP', 'Procedure', '1',
     'Procedure Masterfile ID', 'ASCII: E(69) A(65) P(80)', 'procedure_code_coding'),

    -- Orders
    ('urn:oid:1.2.840.114350.1.13.20.2.7.2.798268', 'Epic', 'CHOP', 'ORD', 'Order', '1',
     'Order Masterfile ID', 'ASCII: O(79) R(82) D(68)', 'order tables'),

    ('urn:oid:1.2.840.114350.1.13.20.2.7.3.798268.800', 'Epic', 'CHOP', 'ORD', 'Order', '800',
     'Order External ID', 'Item 800 = External ID', 'order tables'),

    -- Medications
    ('urn:oid:1.2.840.114350.1.13.20.2.7.2.698288', 'Epic', 'CHOP', 'ERX', 'Medication', '1',
     'Medication Masterfile ID', 'ASCII: E(69) R(82) X(88)', 'medication_request_code_coding'),

    -- Encounter/Visit
    ('urn:oid:1.2.840.114350.1.13.20.2.7.2.678367', 'Epic', 'CHOP', 'CSN', 'Encounter', '1',
     'Contact Serial Number', 'ASCII: C(67) S(83) N(78)', 'encounter'),

    -- Department
    ('urn:oid:1.2.840.114350.1.13.20.2.7.2.686980', 'Epic', 'CHOP', 'DEP', 'Department', '1',
     'Department Masterfile ID', 'ASCII: D(68) E(69) P(80)', 'location'),

    -- Provider
    ('urn:oid:1.2.840.114350.1.13.20.2.7.2.837982', 'Epic', 'CHOP', 'SER', 'Provider', '1',
     'Provider/Service User ID', 'ASCII: S(83) E(69) R(82)', 'practitioner'),

    -- Patient MRN
    ('urn:oid:1.2.840.114350.1.13.20.2.7.5.737384.14', 'Epic', 'CHOP', 'MRN', 'Patient', '14',
     'Medical Record Number', 'Item 14 = MRN type', 'patient_identifier'),

    -- ========================================================================
    -- Standard Healthcare Coding Systems (Non-Epic)
    -- ========================================================================

    -- Procedures
    ('http://www.ama-assn.org/go/cpt', 'Standard', 'AMA', 'CPT', 'Procedure', NULL,
     'Current Procedural Terminology', 'Used for billing and clinical procedures',
     'procedure_code_coding'),

    ('http://snomed.info/sct', 'Standard', 'IHTSDO', 'SNOMED', 'Clinical', NULL,
     'SNOMED CT Clinical Terminology', 'Comprehensive clinical terminology',
     'multiple tables'),

    -- Medications
    ('http://www.nlm.nih.gov/research/umls/rxnorm', 'Standard', 'NLM', 'RxNorm', 'Medication', NULL,
     'RxNorm Medication Codes', 'Normalized medication names',
     'medication_request_code_coding'),

    ('urn:oid:2.16.840.1.113883.6.208', 'Standard', 'NDDF', 'NDDF', 'Medication', NULL,
     'National Drug Data File', 'Drug formulary and pricing',
     'medication_request_code_coding'),

    -- Diagnoses
    ('http://hl7.org/fhir/sid/icd-10-cm', 'Standard', 'WHO', 'ICD-10-CM', 'Diagnosis', NULL,
     'International Classification of Diseases', 'US clinical modification',
     'condition_code_coding'),

    -- Laboratory
    ('http://loinc.org', 'Standard', 'Regenstrief', 'LOINC', 'Laboratory', NULL,
     'Logical Observation Identifiers', 'Lab tests and clinical observations',
     'observation_code_coding'),

    -- Identifiers
    ('http://terminology.hl7.org/CodeSystem/v2-0203', 'Standard', 'HL7', 'v2-0203', 'Identifier', NULL,
     'HL7 v2 Identifier Type Codes', 'MR, DL, SSN, etc.',
     'identifier tables'),

    ('http://hl7.org/fhir/sid/us-npi', 'Standard', 'CMS', 'NPI', 'Provider', NULL,
     'National Provider Identifier', 'US provider registry',
     'practitioner_identifier')

) AS oid_data(
    oid_uri,                    -- Full OID URI (join key)
    oid_source,                 -- 'Epic' or 'Standard'
    issuing_organization,       -- CHOP, AMA, NLM, etc.
    masterfile_code,            -- Short code (EAP, ORD, CPT, RxNorm)
    category,                   -- Procedure, Medication, Diagnosis, etc.
    item_number,                -- Epic item number (null for non-Epic)
    description,                -- Human-readable description
    technical_notes,            -- Implementation notes
    common_fhir_tables          -- Where this OID appears
);
```

### 4. Add OID Validation Queries

**File: `athena_views/testing/validate_oid_usage.sql`**

```sql
-- ============================================================================
-- OID Usage Validation: Find unexpected or undocumented OIDs
-- ============================================================================

-- 1. Find all unique OIDs in procedure_code_coding
WITH procedure_oids AS (
    SELECT DISTINCT code_coding_system
    FROM fhir_prd_db.procedure_code_coding
)
SELECT
    po.code_coding_system,
    CASE
        WHEN vr.oid_uri IS NULL THEN 'UNDOCUMENTED'
        ELSE 'DOCUMENTED'
    END as documentation_status,
    vr.masterfile_code,
    vr.description
FROM procedure_oids po
LEFT JOIN fhir_prd_db.v_oid_reference vr ON po.code_coding_system = vr.oid_uri
ORDER BY documentation_status DESC, po.code_coding_system;

-- 2. Find all Epic OIDs and decode masterfile
SELECT DISTINCT
    code_coding_system,

    -- Extract ASCII portion (last 6 digits before optional item number)
    REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) as ascii_code,

    -- Decode to masterfile
    CASE
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '696580'
            THEN 'EAP (Procedure)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '798268'
            THEN 'ORD (Order)'
        WHEN REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1) = '698288'
            THEN 'ERX (Medication)'
        ELSE 'UNKNOWN - DECODE: ' ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1), 1, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1), 3, 2) AS INT)) ||
            CHR(CAST(SUBSTR(REGEXP_EXTRACT(code_coding_system, '\.(\d{6})(?:\.|$)', 1), 5, 2) AS INT))
    END as decoded_masterfile,

    -- Extract item number if present
    REGEXP_EXTRACT(code_coding_system, '\.\d{6}\.(\d+)$', 1) as item_number,

    COUNT(*) as usage_count
FROM fhir_prd_db.procedure_code_coding
WHERE code_coding_system LIKE 'urn:oid:1.2.840.114350.1.13.20%'
GROUP BY code_coding_system
ORDER BY usage_count DESC;
```

### 5. Update Existing Views with OID Documentation

**Recommended Pattern for All Views:**

```sql
-- ============================================================================
-- CODING SYSTEMS USED IN THIS VIEW
-- ============================================================================
-- Epic CHOP OIDs:
--   urn:oid:1.2.840.114350.1.13.20.2.7.2.696580 = EAP .1 (Procedure Masterfile)
--   urn:oid:1.2.840.114350.1.13.20.2.7.2.798268 = ORD .1 (Order Masterfile)
--
-- Standard OIDs:
--   http://www.ama-assn.org/go/cpt = CPT codes
--   http://www.nlm.nih.gov/research/umls/rxnorm = RxNorm medication codes
--
-- Reference: See v_oid_reference view for complete OID documentation
-- ============================================================================
```

---

## Implementation Priority

### Phase 1: Documentation (Immediate)
1. ✅ Create this OID analysis document
2. Create `v_oid_reference` view
3. Add OID comments to top of existing views
4. Create validation queries

### Phase 2: View Enhancement (Next Sprint)
1. Add OID reference CTE to key views:
   - v_procedures_tumor
   - v_chemo_medications
   - v_unified_patient_timeline
2. Add masterfile decoding columns
3. Test and validate

### Phase 3: Advanced Features (Future)
1. Create SQL functions for OID decoding:
   - `decode_epic_masterfile(oid VARCHAR) RETURNS VARCHAR`
   - `extract_item_number(oid VARCHAR) RETURNS VARCHAR`
2. Add OID validation to data quality checks
3. Create OID discovery tool for new masterfiles

---

## Benefits of Systematic OID Usage

### 1. Improved Troubleshooting
**Before:**
```sql
-- What does this mean?
WHERE code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'
```

**After:**
```sql
-- Clear and documented
WHERE code_coding_system = eap_oid  -- EAP .1: Procedure Masterfile ID
```

### 2. Easier Onboarding
New analysts can reference `v_oid_reference` instead of searching Slack or asking questions.

### 3. Data Quality Validation
Quickly identify when unexpected OIDs appear:
```sql
-- Alert on undocumented OIDs
SELECT * FROM procedure_code_coding pcc
LEFT JOIN v_oid_reference vr ON pcc.code_coding_system = vr.oid_uri
WHERE vr.oid_uri IS NULL
```

### 4. Cross-System Compatibility
Document differences between CHOP (site code 20) and other Epic sites (e.g., UCSF = 266).

### 5. Better View Performance
Use OID reference table instead of repeated CASE statements in every view.

---

## Example: Enhanced v_procedures_tumor with OID Support

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_procedures_tumor AS
WITH
-- ============================================================================
-- OID Reference (Reusable across views)
-- ============================================================================
oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),

-- ============================================================================
-- CPT Classifications (Filtered by OID)
-- ============================================================================
cpt_classifications AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as cpt_code,
        pcc.code_coding_display as cpt_display,
        oid_cpt.masterfile_code as coding_system,
        oid_cpt.description as coding_system_name,

        CASE
            WHEN pcc.code_coding_code IN ('61500', '61510', ...)
            THEN 'craniotomy_tumor_resection'
            -- ... rest of classification logic
        END as cpt_classification

    FROM fhir_prd_db.procedure_code_coding pcc
    LEFT JOIN oid_reference oid_cpt
        ON pcc.code_coding_system = oid_cpt.oid_uri
    WHERE pcc.code_coding_system = 'http://www.ama-assn.org/go/cpt'
),

-- ============================================================================
-- Epic Procedure Codes (Filtered by CHOP EAP OID)
-- ============================================================================
epic_codes AS (
    SELECT
        pcc.procedure_id,
        pcc.code_coding_code as epic_code,
        pcc.code_coding_display as epic_display,
        oid_eap.masterfile_code as coding_system,

        CASE
            WHEN pcc.code_coding_code = '129807' THEN 'neurosurgery_request'
            WHEN pcc.code_coding_code = '85313' THEN 'general_surgery_request'
            ELSE NULL
        END as epic_category

    FROM fhir_prd_db.procedure_code_coding pcc
    LEFT JOIN oid_reference oid_eap
        ON pcc.code_coding_system = oid_eap.oid_uri
    WHERE pcc.code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'
    -- EAP .1: Epic Procedure Masterfile ID
)

SELECT
    -- ... all existing columns ...

    -- NEW: OID metadata columns
    cpt.coding_system as cpt_coding_system,
    epic.coding_system as epic_coding_system

FROM fhir_prd_db.procedure p
LEFT JOIN cpt_classifications cpt ON p.id = cpt.procedure_id
LEFT JOIN epic_codes epic ON p.id = epic.procedure_id
-- ... rest of query
```

---

## Recommended Next Steps

1. **Review and approve** this OID strategy
2. **Deploy `v_oid_reference` view** to production
3. **Update top 5 most-used views** with OID documentation
4. **Create validation queries** to discover undocumented OIDs
5. **Train team** on OID decoding and usage

---

## Questions for CHOP/Epic Team

1. What is OID `urn:oid:1.2.840.114350.1.13.20.7.7.2.798276` (ORT)?
   - Appears in our data but not documented
   - ASCII decode: O(79) R(82) T(84) = "ORT"
   - Need to confirm masterfile and purpose

2. Are there other CHOP-specific masterfile OIDs we should know about?
   - Lab results (LRR)?
   - Imaging orders (IMO)?
   - Radiation therapy specific?

3. Should we document item numbers beyond .1?
   - Example: What is item 800 vs 801 in ORD masterfile?

---

## References

- Epic Vendor Services: ID Types for APIs
- https://oid-base.com/ (OID repository lookup)
- CHOP FHIR Documentation (internal)
- Your analyst's Slack notes (excellent reference!)
