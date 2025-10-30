# Surgical Procedures Assessment

This directory contains analysis files for comparing and validating surgical procedure extraction between `surgical_procedures` table and `v_procedures_tumor` view.

## Overview

These queries help identify gaps between two different surgical procedure extraction approaches:
- **surgical_procedures**: Original extraction logic (3,204 procedures, 1,592 patients)
- **v_procedures_tumor**: Enhanced extraction with tumor surgery classification (4,169 procedures, 1,835 patients)

## Files

### Analysis Queries

#### `compare_procedures_analysis.sql`
**Purpose**: Comprehensive comparison between surgical_procedures and v_procedures_tumor

**Key Metrics**:
- Overlap analysis (procedures in both vs only in one)
- Patient coverage comparison
- Procedure type distribution
- Date range analysis
- CPT code frequency

**Use Case**: Initial discovery to understand the scope of differences

#### `analyze_overlap.sql`
**Purpose**: Deep dive into procedures that appear in BOTH tables

**Key Metrics**:
- Matching procedure characteristics
- CPT code alignment
- Date concordance
- Epic OR Log linkage

**Use Case**: Validate that shared procedures have consistent data

#### `analyze_non_or_procedures.sql`
**Purpose**: Analyze procedures in v_procedures_tumor that are NOT linked to Epic OR Log

**Key Metrics**:
- Procedure category distribution
- Status analysis (completed, preparation, etc.)
- SNOMED category codes
- Source type analysis

**Use Case**: Understand why certain procedures lack OR Log linkage (procedure orders, surgical history, etc.)

### Utility Scripts

#### `run_query.sh`
**Purpose**: Execute SQL queries against AWS Athena

**Usage**:
```bash
./run_query.sh path/to/query.sql
```

**Requirements**:
- AWS CLI configured
- Active AWS SSO session (`aws sso login --profile radiant-prod`)
- Query results saved to: `s3://aws-athena-query-results-fhir-prd/`

## Related Files

### Main Implementation
- `athena_views/views/v_procedures_tumor.sql` - Enhanced procedure view with tumor surgery classification
- `athena_views/views/v_oid_reference.sql` - OID decoding reference

### Analysis Outputs
- `athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql` - Query identifying missing tumor surgeries
- `athena_views/analysis/GUIDE_surgical_procedures_augmentation.md` - Guide for analyst to augment surgical_procedures

### Documentation
- `documentation/OID_DECODING_WORKFLOW_GUIDE.md` - Complete OID decoding workflow
- `documentation/OID_QUICK_REFERENCE.md` - One-page OID cheat sheet
- `documentation/README_OID_DOCUMENTATION.md` - Navigation guide

## Workflow

### Step 1: Initial Discovery
```bash
# Compare overall metrics
./run_query.sh compare_procedures_analysis.sql
```

### Step 2: Analyze Overlap
```bash
# Understand shared procedures
./run_query.sh analyze_overlap.sql
```

### Step 3: Investigate Non-OR Procedures
```bash
# Understand procedures without OR Log
./run_query.sh analyze_non_or_procedures.sql
```

### Step 4: Identify Missing Tumor Surgeries
```bash
# Run the augmentation discovery query
./run_query.sh ../athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql
```

### Step 5: Review Results
Follow the guide in `athena_views/analysis/GUIDE_surgical_procedures_augmentation.md` to:
- Review missing procedures by recommendation priority
- Investigate root causes
- Choose augmentation strategy
- Test and validate changes

## Key Findings

### Gap Analysis
- **surgical_procedures**: 3,204 procedures (1,592 patients)
- **v_procedures_tumor**: 4,169 procedures (1,835 patients)
- **Missing**: ~965 procedures (243 patients)

### Root Causes for Missing Procedures
1. **Procedure Orders** (~516 cases) - Not actual surgeries, correctly excluded
2. **Surgical History** (~146 cases) - External/historical procedures
3. **Missing OR Log** (~260 cases) - Not linked to Epic OR Log
4. **Different SNOMED Category** - Not classified as "Surgical procedure"
5. **Status Issues** - Not marked as "completed"

### High Priority Cases
**~43 procedures with Epic OR Log IDs but missing from surgical_procedures**
- These likely represent real CHOP OR cases
- Should be investigated for inclusion
- May indicate gaps in current extraction logic

## Questions?

Refer to:
- `GUIDE_surgical_procedures_augmentation.md` for detailed workflow
- `OID_DECODING_WORKFLOW_GUIDE.md` for OID system documentation
- Your data analyst for clinical context and Epic-specific questions
