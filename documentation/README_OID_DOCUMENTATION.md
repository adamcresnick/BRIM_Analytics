# OID Documentation Index

**Last Updated:** 2025-10-29

---

## Quick Start

**New to OID decoding?** Start here:

1. **[OID_QUICK_REFERENCE.md](OID_QUICK_REFERENCE.md)** ← Start here! (1 page)
2. **[OID_DECODING_WORKFLOW_GUIDE.md](OID_DECODING_WORKFLOW_GUIDE.md)** ← Full implementation guide
3. **[OID_PROJECT_SUMMARY.md](OID_PROJECT_SUMMARY.md)** ← What we built and why

---

## All OID Documentation

### 📘 Implementation Guides

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[OID_QUICK_REFERENCE.md](OID_QUICK_REFERENCE.md)** | 1-page cheat sheet | Need quick reminder of process |
| **[OID_DECODING_WORKFLOW_GUIDE.md](OID_DECODING_WORKFLOW_GUIDE.md)** | Complete workflow (13,000 words) | Implementing OID decoding in a new view |
| **[OID_USAGE_ANALYSIS_AND_RECOMMENDATIONS.md](OID_USAGE_ANALYSIS_AND_RECOMMENDATIONS.md)** | Initial analysis and strategy | Understanding why we need OID decoding |

### 📊 Reports & Validation

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[OID_VALIDATION_REPORT.md](OID_VALIDATION_REPORT.md)** | Production validation results | See how accurate we were |
| **[OID_IMPLEMENTATION_SUMMARY.md](OID_IMPLEMENTATION_SUMMARY.md)** | Before/after examples | Show stakeholders the improvement |
| **[OID_PROJECT_SUMMARY.md](OID_PROJECT_SUMMARY.md)** | Complete project overview | Understand what was delivered |

### 📁 Related Documentation

| Document | Purpose | Connection to OIDs |
|----------|---------|-------------------|
| **[V_PROCEDURES_TUMOR_DOCUMENTATION.md](V_PROCEDURES_TUMOR_DOCUMENTATION.md)** | Complete view docs | First view with OID decoding |
| **[PROCEDURES_COMPARISON_ANALYSIS.md](PROCEDURES_COMPARISON_ANALYSIS.md)** | Data source comparison | Led to OID discussion |

---

## Documentation by Role

### For Analysts
**"I want to understand what these OIDs mean"**

1. Look up OIDs in production:
   ```sql
   SELECT * FROM fhir_prd_db.v_oid_reference
   WHERE masterfile_code = 'CPT';
   ```

2. See decoded OIDs in views:
   ```sql
   SELECT pcc_coding_system_code, pcc_coding_system_name
   FROM fhir_prd_db.v_procedures_tumor;
   ```

**Read:** [OID_QUICK_REFERENCE.md](OID_QUICK_REFERENCE.md)

### For Developers
**"I need to add OID decoding to a new view"**

**Step-by-step process:**
1. Discover what OIDs are used (queries in guide)
2. Add missing OIDs to v_oid_reference
3. Add 3 decoded columns to your view
4. Validate 100% coverage

**Read:** [OID_DECODING_WORKFLOW_GUIDE.md](OID_DECODING_WORKFLOW_GUIDE.md)

### For Project Managers
**"What did we build and what's the impact?"**

- **22 OIDs documented** (9 Epic + 13 Standard)
- **100% coverage** of production procedure OIDs
- **1 view enhanced** (v_procedures_tumor) - proof of concept
- **Complete workflow** documented for team

**Read:** [OID_PROJECT_SUMMARY.md](OID_PROJECT_SUMMARY.md)

### For Data Governance
**"How do we validate and maintain OID documentation?"**

- Automated discovery queries
- Monthly validation process
- Self-correcting via production data
- Version controlled in Git

**Read:** [OID_VALIDATION_REPORT.md](OID_VALIDATION_REPORT.md)

---

## Key Concepts

### What is an OID?
**Object Identifier** - Globally unique identifier for coding systems

**Examples:**
- `http://www.ama-assn.org/go/cpt` = CPT codes (standard)
- `urn:oid:1.2.840.114350.1.13.20.2.7.2.696580` = EAP (Epic procedure masterfile)

### Why Decode OIDs?

**Before (Hard to Read):**
```sql
WHERE code_coding_system = 'urn:oid:1.2.840.114350.1.13.20.2.7.2.696580'
```

**After (Self-Documenting):**
```sql
WHERE pcc_coding_system_code = 'EAP'  -- Epic Procedure Masterfile
```

### Epic OID Structure

```
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580
                         │      │     └─ ASCII: E(69) A(65) P(80) = EAP
                         │      └─ Type: 2 = masterfile
                         └─ Site: 20 = CHOP
```

---

## Common Tasks

### Task: Look up an OID

```sql
SELECT * FROM fhir_prd_db.v_oid_reference
WHERE oid_uri = 'your_oid_here';
```

### Task: Find all Epic OIDs

```sql
SELECT * FROM fhir_prd_db.v_oid_reference
WHERE oid_source = 'Epic';
```

### Task: Discover new OIDs in production

```sql
SELECT DISTINCT code_coding_system, COUNT(*)
FROM fhir_prd_db.procedure_code_coding
WHERE code_coding_system IS NOT NULL
GROUP BY code_coding_system;
```

### Task: Validate OID coverage in a view

```sql
SELECT code_coding_system
FROM fhir_prd_db.v_procedures_tumor
WHERE code_coding_system IS NOT NULL
  AND pcc_coding_system_code IS NULL;  -- Should be empty!
```

---

## File Locations

### Code
- **OID Registry:** `athena_views/views/v_oid_reference.sql`
- **Enhanced View:** `athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql` (v_procedures_tumor section)
- **Validation Queries:** `athena_views/testing/validate_oid_usage.sql`

### Documentation
All files in: `documentation/`

### Deploy Commands
```bash
# Deploy OID registry
/tmp/run_query.sh athena_views/views/v_oid_reference.sql

# Deploy enhanced view
/tmp/run_query.sh athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql

# Run validation
/tmp/run_query.sh athena_views/testing/validate_oid_usage.sql
```

---

## FAQ

### Q: Do I need to update views when I add OIDs to v_oid_reference?
**A:** No! Views LEFT JOIN to v_oid_reference dynamically. Just redeploy v_oid_reference.

### Q: How do I decode an Epic OID?
**A:** Extract the 6-digit ASCII code and convert to letters:
- 696580 → 69,65,80 → E,A,P = **EAP**

See ASCII table in [OID_QUICK_REFERENCE.md](OID_QUICK_REFERENCE.md)

### Q: What if I find an OID not in v_oid_reference?
**A:**
1. Add it to `v_oid_reference.sql`
2. Redeploy v_oid_reference
3. Views update automatically

See workflow in [OID_DECODING_WORKFLOW_GUIDE.md](OID_DECODING_WORKFLOW_GUIDE.md)

### Q: How accurate is the OID documentation?
**A:** **100%** for procedure_code_coding (validated against production)

See [OID_VALIDATION_REPORT.md](OID_VALIDATION_REPORT.md) for details.

### Q: Can I extend this to other FHIR resources?
**A:** Yes! The pattern works for:
- Medications (medication_request_code_coding)
- Diagnoses (condition_code_coding)
- Labs (observation_code_coding)
- All FHIR resources with code_coding_system

See view-specific patterns in [OID_DECODING_WORKFLOW_GUIDE.md](OID_DECODING_WORKFLOW_GUIDE.md)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-29 | Initial OID decoding system |

---

## Contributing

Found a new OID? Have improvements?

1. Add to `v_oid_reference.sql`
2. Update relevant documentation
3. Run validation queries
4. Commit to Git

---

## Support

Questions? See:
- **Quick Help:** [OID_QUICK_REFERENCE.md](OID_QUICK_REFERENCE.md)
- **Detailed Guide:** [OID_DECODING_WORKFLOW_GUIDE.md](OID_DECODING_WORKFLOW_GUIDE.md)
- **Validation:** `athena_views/testing/validate_oid_usage.sql`

---

**Last Updated:** 2025-10-29
**Maintained By:** BRIM Analytics Team
**Status:** Production-Ready ✅
