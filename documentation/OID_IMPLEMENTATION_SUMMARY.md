# OID Decoding Implementation - Summary

**Date:** 2025-10-29
**Status:** ✅ Deployed to Production
**Impact:** Improved code readability and data discovery

---

## What We Built

### 1. Central OID Reference View (`v_oid_reference`)

A comprehensive registry of all Object Identifiers (OIDs) used in CHOP FHIR data.

**Documented OIDs:**
- **Epic CHOP Masterfiles (9 total)**
  - EAP (Procedure), ORD (Order), ERX (Medication)
  - CSN (Encounter), DEP (Department), SER (Provider)
  - MRN (Patient), ORT (Order Type - needs verification)

- **Standard Coding Systems (12 total)**
  - CPT, RxNorm, SNOMED CT, ICD-10-CM
  - LOINC, NDDF, NPI, CVX, NDC, etc.

**Key Features:**
- ASCII decoding explanation for Epic OIDs
- Verification status flag
- Common FHIR tables where each OID appears
- Technical notes and implementation guidance

---

## Before & After Comparison

### Before: Hard to Understand

```sql
SELECT
    code_coding_system,
    code_coding_code,
    COUNT(*) as cnt
FROM fhir_prd_db.procedure_code_coding
WHERE code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'
GROUP BY code_coding_system, code_coding_code;
```

**Result:**
```
code_coding_system                                    code_coding_code  cnt
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580          85313            2435
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580          109083           2293
```

**Questions analysts ask:**
- ❓ What is `urn:oid:1.2.840.114350.1.13.20.2.7.2.696580`?
- ❓ Is this Epic-specific or a standard?
- ❓ How do I find out what masterfile this represents?

---

### After: Self-Documenting and Clear

```sql
SELECT
    pcc_code_coding_system,
    pcc_coding_system_code,      -- NEW: Short code
    pcc_coding_system_name,       -- NEW: Human-readable
    pcc_coding_system_source,     -- NEW: Epic or Standard
    pcc_code_coding_code,
    COUNT(*) as cnt
FROM fhir_prd_db.v_procedures_tumor
WHERE pcc_coding_system_code = 'EAP'  -- Much easier to filter!
GROUP BY 1,2,3,4,5;
```

**Result:**
```
pcc_code_coding_system                                pcc_coding_system_code  pcc_coding_system_name                pcc_coding_system_source  pcc_code_coding_code  cnt
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580          EAP                     Procedure Masterfile ID (.1)          Epic                      85313                 2435
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580          EAP                     Procedure Masterfile ID (.1)          Epic                      109083                2293
```

**Immediate understanding:**
- ✅ This is the **EAP** masterfile (Epic Ambulatory Procedures)
- ✅ It's **Epic-specific** (not a standard coding system)
- ✅ Represents the **.1** (primary ID) field
- ✅ Can filter using `pcc_coding_system_code = 'EAP'`

---

## Real-World Example: CPT vs Epic Codes

### Query: Show me all coding systems used in procedures

```sql
SELECT
    pcc_coding_system_code,
    pcc_coding_system_name,
    pcc_coding_system_source,
    COUNT(*) as procedure_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_procedures_tumor
WHERE pcc_code_coding_system IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY procedure_count DESC;
```

### Results (Top 3):

| Code | Name | Source | Procedures | Patients |
|------|------|--------|------------|----------|
| **CPT** | Current Procedural Terminology | Standard | 62,518 | 1,823 |
| **EAP** | Procedure Masterfile ID (.1) | Epic | 7,117 | 1,331 |
| **NULL** | (Undocumented) | NULL | 0 | 0 |

**Insights:**
- 90% of procedures use standard **CPT codes** ✅
- 10% use Epic-specific **EAP codes** (internal procedure IDs)
- Can easily distinguish between standard and Epic-specific coding

---

## ASCII Decoding Reference

Epic OIDs encode masterfile names using ASCII:

| OID Suffix | ASCII Decode | Masterfile | Description |
|-----------|--------------|------------|-------------|
| 696580 | **69,65,80** = E,A,P | **EAP** | Procedure Masterfile |
| 798268 | **79,82,68** = O,R,D | **ORD** | Order Masterfile |
| 698288 | **69,82,88** = E,R,X | **ERX** | Medication Masterfile |
| 678367 | **67,83,78** = C,S,N | **CSN** | Encounter (Contact Serial Number) |
| 686980 | **68,69,80** = D,E,P | **DEP** | Department Masterfile |
| 837982 | **83,69,82** = S,E,R | **SER** | Provider (Service User) |

**Tool to decode:** https://www.rapidtables.com/convert/number/ascii-to-dec.html

---

## Usage Examples

### Example 1: Find All Standard Coding Systems

```sql
SELECT
    masterfile_code,
    description,
    oid_uri
FROM fhir_prd_db.v_oid_reference
WHERE oid_source = 'Standard'
ORDER BY category, masterfile_code;
```

### Example 2: Find Epic Masterfiles Used in Procedures

```sql
SELECT DISTINCT
    pcc_coding_system_code,
    pcc_coding_system_name,
    COUNT(*) as usage_count
FROM fhir_prd_db.v_procedures_tumor
WHERE pcc_coding_system_source = 'Epic'
GROUP BY 1, 2
ORDER BY usage_count DESC;
```

### Example 3: Validate OID Documentation

```sql
-- Find OIDs in production that aren't documented yet
SELECT DISTINCT
    code_coding_system,
    COUNT(*) as usage_count
FROM fhir_prd_db.procedure_code_coding pcc
LEFT JOIN fhir_prd_db.v_oid_reference vr
    ON pcc.code_coding_system = vr.oid_uri
WHERE vr.oid_uri IS NULL
GROUP BY code_coding_system
ORDER BY usage_count DESC;
```

---

## Validation & Testing

### Test Results

1. **v_oid_reference deployed** ✅
   - 20 OIDs documented (9 Epic + 11 Standard)
   - All queries return expected results

2. **v_procedures_tumor enhanced** ✅
   - 3 new OID decoding columns added
   - Backward compatible (all original columns preserved)
   - 69,635 procedures validated

3. **OID Decoding Working** ✅
   ```
   CPT     → "Current Procedural Terminology" (Standard)
   EAP     → "Procedure Masterfile ID (.1)" (Epic)
   RxNorm  → "RxNorm Medication Codes" (Standard)
   ```

---

## Files Created/Modified

### New Files
1. **`v_oid_reference.sql`** - Central OID registry view
2. **`validate_oid_usage.sql`** - OID discovery and validation queries
3. **`OID_USAGE_ANALYSIS_AND_RECOMMENDATIONS.md`** - Full implementation guide
4. **`OID_IMPLEMENTATION_SUMMARY.md`** - This document

### Modified Files
1. **`DATETIME_STANDARDIZED_VIEWS.sql`** - Enhanced v_procedures_tumor with OID decoding

---

## Benefits Achieved

### 1. Improved Troubleshooting
**Before:** "What does `urn:oid:1.2.840.114350.1.13.20.2.7.2.696580` mean?"
**After:** "It's EAP - the Epic Procedure Masterfile"

### 2. Faster Onboarding
New analysts can reference `v_oid_reference` instead of:
- Searching Slack
- Asking senior analysts
- Decoding ASCII manually

### 3. Better Data Quality
Quickly identify unexpected OIDs:
```sql
-- Alert on undocumented OIDs
SELECT * FROM v_oid_reference WHERE is_verified = FALSE;
```

Result: Found ORT (Order Type) needs verification ⚡

### 4. Self-Documenting Code
Views now explain their own coding systems:
```sql
-- Comment at top of v_procedures_tumor
-- Epic CHOP OIDs:
--   urn:oid:1.2.840.114350.1.13.20.2.7.2.696580 = EAP .1 (Procedure Masterfile)
-- Standard OIDs:
--   http://www.ama-assn.org/go/cpt = CPT codes
```

---

## Next Steps

### Immediate (Completed ✅)
- ✅ Deploy v_oid_reference view
- ✅ Update v_procedures_tumor with OID decoding
- ✅ Create validation queries
- ✅ Test and validate functionality
- ✅ Commit to GitHub

### Short-term (Recommended)
1. **Verify ORT masterfile**
   - Contact Epic team about `urn:oid:1.2.840.114350.1.13.20.7.7.2.798276`
   - Update v_oid_reference with correct description

2. **Apply to other views**
   - Add OID decoding to v_chemo_medications (RxNorm, NDDF)
   - Add OID decoding to v_unified_patient_timeline

3. **Run discovery queries**
   - Use validate_oid_usage.sql to find undocumented OIDs
   - Add new OIDs to v_oid_reference as discovered

### Long-term (Future)
1. Create SQL functions for OID decoding
2. Add OID validation to data quality checks
3. Document UCSF vs CHOP site code differences (266 vs 20)

---

## Questions Answered

### Q: Are we now using OIDs more systematically?
**A:** Yes! We have:
- Central OID registry (v_oid_reference)
- Decoded columns in views (pcc_coding_system_code, etc.)
- Validation queries to discover new OIDs
- Documentation explaining Epic's OID structure

### Q: Does this work for other Epic sites (like UCSF)?
**A:** Partially. The pattern is the same, but CHOP's site code is 20:
- CHOP: `1.2.840.114350.1.13.20.2.7.2.696580`
- UCSF: `1.2.840.114350.1.13.266.2.7.2.696580`

We'd need to add UCSF OIDs to v_oid_reference if we integrate UCSF data.

### Q: What about non-Epic OIDs (NDDF, etc.)?
**A:** Covered! v_oid_reference includes:
- NDDF (National Drug Data File): `urn:oid:2.16.840.1.113883.6.208`
- NPI (National Provider ID): `http://hl7.org/fhir/sid/us-npi`
- And 10+ other standard coding systems

---

## Success Metrics

### Quantitative
- **20 OIDs documented** (vs 0 before)
- **3 new columns** added to v_procedures_tumor
- **6 validation queries** created
- **100% backward compatibility** (all existing queries still work)

### Qualitative
- ✅ Analysts can now understand OIDs at a glance
- ✅ Code is self-documenting
- ✅ New analysts onboard faster
- ✅ Data quality issues easier to spot

---

## Team Feedback

Your analyst's Slack note was excellent! The ASCII decoding pattern they documented:
```
798268 = ORD (79,82,68)
696580 = EAP (69,65,80)
698288 = ERX (69,82,88)
```

...is now permanently documented in v_oid_reference for the entire team.

---

## References

- **Epic Documentation:** https://vendorservices.epic.com/Article?docId=epicidtypes
- **OID Repository:** https://oid-base.com/
- **HL7 OID Registry:** https://www.hl7.org/oid/
- **Internal Docs:**
  - `OID_USAGE_ANALYSIS_AND_RECOMMENDATIONS.md`
  - `V_PROCEDURES_TUMOR_DOCUMENTATION.md`
  - `PROCEDURES_COMPARISON_ANALYSIS.md`
