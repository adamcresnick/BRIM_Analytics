# CBTN Multi-Database FHIR ID Matching - Generic Strategy

## Overview

This script implements a **generic, database-agnostic matching strategy** to map CBTN enrollment records to FHIR patient IDs across multiple Athena databases (CHOP, UCSF, and extensible to others).

## Matching Strategy

The script uses a **two-tier matching approach for ALL databases**:

### 1. Primary: MRN Exact Match
- Attempts to match on `identifier_mrn` field first
- Fast, direct lookup
- Highest confidence matches

### 2. Fallback: DOB + Name Matching
When MRN fails, attempts DOB-based matching with progressive name validation:

1. **DOB + Exact Name** (highest confidence)
   - Matches `birth_date` AND exact `given_name` + `family_name`
   
2. **DOB + Last Name + First Initial**
   - Matches `birth_date` AND `family_name` + first initial of `given_name`
   
3. **DOB + First Name + Last Initial**
   - Matches `birth_date` AND `given_name` + first initial of `family_name`
   
4. **DOB Only with Single Candidate** (flagged for VERIFY)
   - Matches `birth_date` with exactly one patient
   - Requires manual verification due to potential name spelling variations

## Results Summary

### Performance Comparison

| Approach | Matches | Match Rate | Notes |
|----------|---------|------------|-------|
| Approach 1: MRN-only (CHOP) | 1,843 | 27.9% | Original baseline |
| Approach 2: MRN CHOP + DOB UCSF | 1,971 | 29.9% | Specialized per-database |
| **Approach 3: Generic MRN+DOB** | **2,650** | **40.2%** | ✓ Recommended |

**Improvement: +807 matches (+44% over MRN-only)**

### Match Breakdown

#### By Strategy:
- **MRN exact matches**: 1,843 records
- **DOB + Name/Initial matches**: 107 records (high confidence)
- **DOB-only matches**: 700 records (flagged for VERIFY)

#### By Database:
- **CHOP**: 2,479 matches (1,843 MRN + 636 DOB fallback)
- **UCSF**: 171 matches (0 MRN + 171 DOB)

#### By Institution:
- **CHOP (Philadelphia)**: 84.4% match rate (1,877/2,224)
- **UCSF Benioff**: 47.5% match rate (149/314)
- **Other institutions**: 17.2% average (benefiting from cross-database matching)

## Security Features

### PHI Protection
- **MRNs, DOBs, and names are NEVER displayed or logged**
- All matching happens in-memory
- Only aggregate statistics are output
- No PHI in terminal output or log files

### Name Normalization
- Case-insensitive matching
- Special character removal
- Whitespace normalization
- Prevents false negatives from formatting differences

## Usage

### Basic Usage
```bash
python3 match_cbtn_multi_database.py \
    <input_csv> \
    <output_csv>
```

### Full Options
```bash
python3 match_cbtn_multi_database.py \
    /path/to/cbtn_enrollment.csv \
    /path/to/output_with_fhir_ids.csv \
    --chop-database fhir_v2_prd_db \
    --ucsf-database fhir_v2_ucsf_prd_db
```

### Skip UCSF (CHOP only)
```bash
python3 match_cbtn_multi_database.py \
    input.csv \
    output.csv \
    --skip-ucsf
```

## Input Requirements

### Required CSV Columns:
- `mrn` - Medical Record Number
- `dob` - Date of Birth (YYYY-MM-DD format)
- `first_name` - Patient's first/given name
- `last_name` - Patient's family name

### Optional Columns:
- `organization_name` - Institution name (for reporting)
- `research_id` - Research identifier (preserved in output)
- Any other columns (passed through unchanged)

## Output Format

### Added Columns:
1. **`FHIR_ID`** - Patient FHIR identifier from Athena
2. **`match_strategy`** - How the match was made:
   - `chop_mrn_exact` - CHOP MRN exact match
   - `chop_dob_exact_name` - CHOP DOB + exact name
   - `chop_dob_last_initial` - CHOP DOB + last name + first initial
   - `chop_dob_only_single_VERIFY` - CHOP DOB only (needs review)
   - `ucsf_mrn_exact` - UCSF MRN exact match
   - `ucsf_dob_exact_name` - UCSF DOB + exact name
   - etc.
3. **`match_database`** - Which database provided the match (`chop` or `ucsf`)

### Original Columns:
All original columns are preserved in the output.

## Verification Requirements

### High Confidence Matches (No Review Needed)
- MRN exact matches: **1,843 records**
- DOB + exact name matches: **97 records**
- DOB + name initial matches: **10 records**
- **Total: 1,950 records** ✓

### Medium Confidence Matches (Manual Review Recommended)
- DOB-only matches (single candidate): **700 records**
  - CHOP: 623 records
  - UCSF: 77 records
- **Flagged with `_VERIFY` suffix in `match_strategy` column**

### Review Process for VERIFY Records:
1. Check name spelling variations (nicknames, typos)
2. Verify DOB accuracy in source system
3. Consider multiple possible matches if DOB is common
4. Cross-reference with other identifiers if available

## Why DOB Fallback Matters

### For CHOP (636 recovered records):
- **MRN format differences**: Leading zeros, hyphens
- **MRN updates**: Patient records merged or changed
- **Data entry errors**: Transposition, typos in MRN field
- **Multiple MRN systems**: Different systems within CHOP

### For UCSF (171 total matches):
- **No MRN matches**: UCSF MRNs in enrollment don't match Athena format
- **DOB+name is only viable strategy**
- **47.5% match rate** achieved with DOB approach

## AWS Configuration

### Prerequisites:
- AWS SSO session active: `aws sso login --profile radiant-prod`
- Access to Athena databases:
  - `fhir_v2_prd_db` (CHOP)
  - `fhir_v2_ucsf_prd_db` (UCSF)

### AWS Profile:
- Default: `radiant-prod`
- Region: `us-east-1`

## Performance

### Execution Time:
- **~7-10 seconds** for 6,599 records
- Athena queries: ~2 seconds each
- In-memory matching: <1 second
- CSV I/O: <1 second

### Scalability:
- Handles 10,000+ records efficiently
- Memory footprint: <100MB
- Could be optimized with batching for 100,000+ records

## Extensibility

### Adding New Databases:
1. Add database argument to `argparse`:
   ```python
   parser.add_argument('--new-db-database', default='fhir_new_prd_db')
   ```

2. Query the database in `main()`:
   ```python
   new_mrn_map, new_demo_df = query_patient_data(athena_client, args.new_db_database, 'newdb')
   db_configs.append(('newdb', new_mrn_map, new_demo_df))
   ```

3. Run the script with new database:
   ```bash
   python3 match_cbtn_multi_database.py input.csv output.csv \
       --chop-database fhir_v2_prd_db \
       --ucsf-database fhir_v2_ucsf_prd_db \
       --new-db-database fhir_new_prd_db
   ```

## Troubleshooting

### No matches found:
- Verify AWS SSO session is active
- Check database names are correct
- Ensure date formats match (YYYY-MM-DD)
- Verify names are normalized (case-insensitive, no special chars)

### Low match rate:
- Check for MRN format differences (leading zeros, hyphens)
- Verify DOB format consistency
- Review name spelling variations
- Consider expanding to additional databases

### PHI security concerns:
- Script never logs PHI data
- All matching is in-memory
- Output only shows match statistics
- Use `grep -v` filters if additional security needed

## Files

### Input:
- `stg_cbtn_enrollment_final_10262025.csv` (6,599 records)

### Output:
- `stg_cbtn_enrollment_with_fhir_id_generic.csv` (6,599 records + 3 new columns)

### Script:
- `match_cbtn_multi_database.py` (main script)
- `list_athena_databases.py` (helper to discover available databases)

## License

Internal use only. Contains PHI. Handle according to institutional IRB and HIPAA guidelines.

## Contact

For questions or issues, contact the RADIANT/BRIM development team.
