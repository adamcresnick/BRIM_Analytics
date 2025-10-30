# OID Decoding Quick Reference

**One-page reference for implementing OID decoding**

---

## 3-Step Process

```
1. DISCOVER  → Find what OIDs are actually used in production
2. DOCUMENT  → Add missing OIDs to v_oid_reference
3. IMPLEMENT → Add 3 decoded columns to your view
```

---

## Step 1: Discovery Query

```sql
-- What OIDs are used in this table?
SELECT DISTINCT code_coding_system, COUNT(*) as cnt
FROM fhir_prd_db.<your_table>
WHERE code_coding_system IS NOT NULL
GROUP BY code_coding_system
ORDER BY cnt DESC;

-- Are they documented?
WITH prod AS (
    SELECT DISTINCT code_coding_system as oid FROM fhir_prd_db.<your_table>
)
SELECT p.oid, vr.masterfile_code,
    CASE WHEN vr.oid_uri IS NULL THEN '❌ ADD' ELSE '✅ DONE' END
FROM prod p
LEFT JOIN fhir_prd_db.v_oid_reference vr ON p.oid = vr.oid_uri;
```

---

## Step 2: Add to v_oid_reference

### If Epic OID - Decode ASCII

```sql
-- Example: urn:oid:1.2.840.114350.1.13.20.2.7.2.798268
-- Extract: 798268
-- Decode:  79=O, 82=R, 68=D → "ORD"
```

**ASCII Lookup Table:**
```
67=C  68=D  69=E  78=N  79=O  80=P  82=R  83=S  84=T  88=X
```

### If Standard OID - Look Up

- https://oid-base.com/
- https://www.hl7.org/oid/

### Add to v_oid_reference.sql

```sql
('<oid_uri>', '<Epic|Standard>', '<org>', '<code>', '<category>', '<item>',
 '<description>', '<notes>', '<table>', <true|false>),
```

---

## Step 3: Add to Your View

### 3a. Add Comment Header

```sql
-- ============================================================================
-- CODING SYSTEMS USED IN v_your_view
-- ============================================================================
-- Epic CHOP OIDs:
--   urn:oid:1.2.840.114350.1.13.20.2.7.2.696580 = EAP .1 (Procedure)
-- Standard OIDs:
--   http://www.ama-assn.org/go/cpt = CPT codes
-- ============================================================================
```

### 3b. Add CTE

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_your_view AS
WITH
oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),
-- ... rest of CTEs ...
```

### 3c. Add Columns

```sql
SELECT
    -- Original
    code_coding_system,
    code_coding_code,

    -- NEW: 3 decoded columns
    oid.masterfile_code as coding_system_code,
    oid.description as coding_system_name,
    oid.oid_source as coding_system_source,

    -- ... rest ...
```

### 3d. Add JOIN

```sql
FROM your_table t
LEFT JOIN oid_reference oid ON t.code_coding_system = oid.oid_uri
```

---

## Validation

```sql
-- Should return ZERO rows
SELECT DISTINCT code_coding_system
FROM fhir_prd_db.v_your_view
WHERE code_coding_system IS NOT NULL
  AND coding_system_code IS NULL;
```

---

## Common CHOP Epic OIDs

| ASCII | Code | Full Name | OID Suffix |
|-------|------|-----------|------------|
| 696580 | EAP | Epic Ambulatory Procedures | Procedure masterfile |
| 798268 | ORD | Orders | Order masterfile |
| 698288 | ERX | Prescriptions | Medication masterfile |
| 678367 | CSN | Contact Serial Number | Encounter ID |
| 686980 | DEP | Department | Location |
| 837982 | SER | Service/Provider | Clinician |

Full OID: `urn:oid:1.2.840.114350.1.13.20.2.7.2.<ASCII>`

---

## Common Standard OIDs

| Code | Full Name | OID |
|------|-----------|-----|
| CPT | Current Procedural Terminology | `http://www.ama-assn.org/go/cpt` |
| RxNorm | RxNorm Medications | `http://www.nlm.nih.gov/research/umls/rxnorm` |
| SNOMED CT | Clinical Terminology | `http://snomed.info/sct` |
| ICD-10-CM | Diagnoses | `http://hl7.org/fhir/sid/icd-10-cm` |
| LOINC | Lab/Observations | `http://loinc.org` |
| NDDF | Drug Data File | `urn:oid:2.16.840.1.113883.6.208` |
| HCPCS | CMS Procedures | `urn:oid:2.16.840.1.113883.6.14` |
| CDT-2 | Dental Procedures | `urn:oid:2.16.840.1.113883.6.13` |

---

## Usage Examples

```sql
-- Filter by coding system
WHERE coding_system_code = 'CPT'

-- Compare Epic vs Standard
GROUP BY coding_system_source

-- Find specific masterfile
WHERE coding_system_code IN ('EAP', 'ORD', 'ERX')
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| New OID in production | Add to v_oid_reference, redeploy (views update automatically) |
| NULL decoded columns | Run validation query, add missing OIDs |
| Wrong decoding | Check v_oid_reference for typos, verify OID exact match |
| Slow queries | OID table small (~50 rows), should not impact performance |

---

## Files

- **Registry:** `athena_views/views/v_oid_reference.sql`
- **Validation:** `athena_views/testing/validate_oid_usage.sql`
- **Full Guide:** `documentation/OID_DECODING_WORKFLOW_GUIDE.md`
- **Examples:** `documentation/OID_IMPLEMENTATION_SUMMARY.md`

---

## Deploy Commands

```bash
# Deploy OID registry
/tmp/run_query.sh athena_views/views/v_oid_reference.sql

# Deploy your view
/tmp/run_query.sh athena_views/views/v_your_view.sql

# Validate
/tmp/run_query.sh athena_views/testing/validate_oid_usage.sql
```

---

**Questions?** See full workflow guide: `OID_DECODING_WORKFLOW_GUIDE.md`
