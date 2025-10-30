# OID Validation and Testing

This directory contains validation queries and test files used during the OID decoding implementation for v_procedures_tumor.

## Overview

These queries were created to validate the OID (Object Identifier) decoding implementation and ensure comprehensive coverage of all coding systems used in CHOP's FHIR data.

## Files

### Validation Queries

#### `validate_procedure_oids.sql`
**Purpose**: Discover all OIDs used in procedure_code_coding table and check coverage in v_oid_reference

**Key Features**:
- Lists all distinct OIDs with usage counts
- Flags UNDOCUMENTED vs DOCUMENTED vs NEEDS VERIFICATION
- Sorted by documentation status and usage volume

**Use Case**: Initial discovery to identify gaps in OID documentation

**Results**: Initially found 5 OIDs, discovered 2 were missing (CDT-2, HCPCS)

#### `validate_my_oid_work.sql`
**Purpose**: Self-validation query to assess accuracy of v_oid_reference implementation

**Key Features**:
- Compares production OIDs to v_oid_reference
- Calculates coverage percentage
- Shows both record count and volume coverage

**Results**:
- Initial accuracy: 60% by count, 98.2% by volume
- Final accuracy: 100% coverage for procedure_code_coding

#### `test_oid_decoding_in_procedures.sql`
**Purpose**: Test that OID decoding columns work correctly in v_procedures_tumor

**Key Features**:
- Validates pcc_coding_system_code, pcc_coding_system_name, pcc_coding_system_source
- Groups by coding system to show distribution
- Confirms JOIN logic works properly

**Expected Results**:
```
code_coding_system                                    | code  | name                                    | source   | count
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580          | EAP   | Procedure Masterfile ID (.1)            | Epic     | 7,353
http://www.ama-assn.org/go/cpt                       | CPT   | Current Procedural Terminology          | Standard | 31,773
http://loinc.org                                     | LOINC | Logical Observation Identifiers...      | Standard | 817
urn:oid:2.16.840.1.113883.6.13                       | CDT-2 | Current Dental Terminology              | Standard | 169
urn:oid:2.16.840.1.113883.6.14                       | HCPCS | Healthcare Common Procedure Coding Sys  | Standard | 140
```

#### `test_oid_reference.sql`
**Purpose**: Simple smoke test that v_oid_reference view exists and returns data

**Use Case**: Quick verification after deploying v_oid_reference

### View Iterations

#### `v_procedures_tumor_original.sql`
**Purpose**: Original version of v_procedures_tumor BEFORE OID decoding was added

**Why Preserved**:
- Reference for before/after comparison
- Documents baseline functionality
- Helps understand what changed during OID enhancement

**Key Characteristics**:
- No oid_reference CTE
- No pcc_coding_system_* columns
- Had to reference OIDs directly in WHERE clauses

#### `v_procedures_tumor_with_oid.sql`
**Purpose**: Enhanced version of v_procedures_tumor WITH OID decoding

**Why Preserved**:
- Shows complete implementation of OID decoding pattern
- Serves as reference for other views
- Documents the enhancement

**Key Changes**:
1. Added oid_reference CTE
2. Added 3 columns: pcc_coding_system_code, pcc_coding_system_name, pcc_coding_system_source
3. Added LEFT JOIN to oid_reference
4. Added documentation header explaining OID usage

**Note**: This file was created during development. The final implementation is in `athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql`.

## Workflow

### Initial Discovery
```bash
# Step 1: Discover all OIDs in use
../surgical_procedures_assessment/run_query.sh validate_procedure_oids.sql
```

### Self-Validation
```bash
# Step 2: Validate OID documentation coverage
../surgical_procedures_assessment/run_query.sh validate_my_oid_work.sql
```

### Implementation Testing
```bash
# Step 3: Test OID reference view
../surgical_procedures_assessment/run_query.sh test_oid_reference.sql

# Step 4: Test OID decoding in v_procedures_tumor
../surgical_procedures_assessment/run_query.sh test_oid_decoding_in_procedures.sql
```

## Key Findings

### Initial OID Coverage
**Discovered**: 5 distinct OIDs in procedure_code_coding
1. CPT: 31,773 procedures (79.3%)
2. EAP: 7,353 procedures (18.4%)
3. LOINC: 817 procedures (2.0%)
4. CDT-2: 169 procedures (0.4%) - **MISSED INITIALLY**
5. HCPCS: 140 procedures (0.3%) - **MISSED INITIALLY**

### Self-Validation Results
- **Initial accuracy**: 60% by OID count, 98.2% by procedure volume
- **Why missed**: Focused on high-volume OIDs first, didn't validate against production
- **Lesson learned**: Always run discovery queries against production data FIRST
- **Final accuracy**: 100% coverage after adding missing OIDs

### Epic CHOP OID Structure
```
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580
                         ^^ = 20 (CHOP site code)
                                  ^^^^^^ = 696580 (ASCII encoded)
                                           69 = E
                                           65 = A
                                           80 = P
                                           EAP = Epic Ambulatory Procedures
```

## Related Files

### Implementation
- `athena_views/views/v_oid_reference.sql` - Central OID registry (22 OIDs)
- `athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql` - v_procedures_tumor with OID decoding
- `athena_views/testing/validate_oid_usage.sql` - Production validation queries

### Documentation
- `documentation/OID_DECODING_WORKFLOW_GUIDE.md` - Complete implementation guide
- `documentation/OID_QUICK_REFERENCE.md` - One-page cheat sheet
- `documentation/OID_VALIDATION_REPORT.md` - Honest assessment of validation process
- `documentation/README_OID_DOCUMENTATION.md` - Navigation guide

## Next Steps

To extend OID decoding to other views:
1. Follow the workflow in `documentation/OID_DECODING_WORKFLOW_GUIDE.md`
2. Use queries from `athena_views/testing/validate_oid_usage.sql` as templates
3. Document new OIDs in v_oid_reference
4. Add decoding columns to target views

## Success Metrics

- ✅ 100% OID coverage for procedure_code_coding
- ✅ All 5 production OIDs documented in v_oid_reference
- ✅ OID decoding working in v_procedures_tumor
- ✅ Can filter by masterfile_code instead of full OID URI
- ✅ Queries are now self-documenting

## Validation Report

For complete transparency about the validation process, including initial errors and corrections, see:
`documentation/OID_VALIDATION_REPORT.md`
