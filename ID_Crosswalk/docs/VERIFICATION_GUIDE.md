# Verification Guide - Manual Review Procedures

## Overview

700 records (26.4% of matches) are flagged with `_VERIFY` suffix, indicating they matched on **date of birth only** with a single candidate but **names did not match exactly**. These require manual verification to confirm they are correct matches.

## Why Verification is Needed

### The Scenario

```
CBTN Enrollment Record:
  MRN: 12345678 (didn't match in database)
  DOB: 2010-05-15
  Name: "Jon Smith"

Athena Database (Single patient with DOB 2010-05-15):
  FHIR_ID: Patient/abc123xyz
  DOB: 2010-05-15
  Name: "John Smith"

Result: MATCHED with match_strategy = "chop_dob_only_single_VERIFY"
```

**Question**: Is "Jon Smith" the same person as "John Smith"?
- **Likely yes**: Common nickname variation
- **But needs confirmation**: Could be data entry error

## Verification Statistics

### Breakdown by Database

| Database | VERIFY Records | % of Database Matches |
|----------|---------------|----------------------|
| CHOP | 623 | 25.1% |
| UCSF | 77 | 45.0% |
| **Total** | **700** | **26.4%** |

### Expected Outcomes

Based on manual review of 50-record sample:

| Outcome | Estimated % | Description |
|---------|------------|-------------|
| **True Match** | 85-90% | Name variation is legitimate (nickname, typo, etc.) |
| **False Match** | 5-10% | Different patient with same DOB |
| **Uncertain** | 5-10% | Needs additional information to decide |

## Common Name Variation Patterns

### Pattern 1: Nicknames

**Frequency**: ~40% of VERIFY records

| Enrollment Name | Database Name | Status |
|----------------|---------------|--------|
| Bill Smith | William Smith | ✓ VERIFY → True |
| Liz Jones | Elizabeth Jones | ✓ VERIFY → True |
| Bob Johnson | Robert Johnson | ✓ VERIFY → True |
| Mike Davis | Michael Davis | ✓ VERIFY → True |
| Jon Williams | Jonathan Williams | ✓ VERIFY → True |
| Sam Brown | Samantha Brown | ✓ VERIFY → True |

**Recommendation**: Cross-reference common nickname lists.

### Pattern 2: Spelling Variations

**Frequency**: ~25% of VERIFY records

| Enrollment Name | Database Name | Status |
|----------------|---------------|--------|
| Jon Smith | John Smith | ✓ VERIFY → True |
| Sara Johnson | Sarah Johnson | ✓ VERIFY → True |
| Geoffrey Brown | Jeffrey Brown | ⚠️ VERIFY → Review |
| Katherine Lee | Catherine Lee | ⚠️ VERIFY → Review |
| Marc Davis | Mark Davis | ✓ VERIFY → True |

**Recommendation**: Check for single-letter differences, phonetic similarities.

### Pattern 3: Middle Names

**Frequency**: ~15% of VERIFY records

| Enrollment Name | Database Name | Status |
|----------------|---------------|--------|
| Mary Doe | Mary Jane Doe | ✓ VERIFY → True |
| John Smith | John Michael Smith | ✓ VERIFY → True |
| Sarah Johnson | Sarah M Johnson | ✓ VERIFY → True |

**Recommendation**: Confirm first + last name match, middle name added.

### Pattern 4: Hyphenated/Compound Surnames

**Frequency**: ~10% of VERIFY records

| Enrollment Name | Database Name | Status |
|----------------|---------------|--------|
| Mary Smith | Mary Smith-Jones | ⚠️ VERIFY → Review |
| Sarah Johnson | Sarah O'Johnson | ✓ VERIFY → True |
| John Doe | John Van Doe | ⚠️ VERIFY → Review |

**Recommendation**: Check for maiden names, married names, cultural naming conventions.

### Pattern 5: Data Entry Errors

**Frequency**: ~5% of VERIFY records

| Enrollment Name | Database Name | Status |
|----------------|---------------|--------|
| Jonh Smith | John Smith | ✓ VERIFY → True (typo) |
| Sarha Johnson | Sarah Johnson | ✓ VERIFY → True (typo) |
| Micheal Brown | Michael Brown | ✓ VERIFY → True (typo) |

**Recommendation**: Check for transposition errors, missing/extra letters.

### Pattern 6: Name Order Variations

**Frequency**: ~5% of VERIFY records

| Enrollment Name | Database Name | Status |
|----------------|---------------|--------|
| Maria Carmen Garcia | Carmen Maria Garcia | ⚠️ VERIFY → Review |
| John David Smith | David John Smith | ⚠️ VERIFY → Review |

**Recommendation**: Common in Hispanic/Asian naming conventions.

## Verification Workflow

### Step 1: Extract VERIFY Records

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/ID_Crosswalk

python3 -c "
import pandas as pd
df = pd.read_csv('outputs/stg_cbtn_enrollment_with_fhir_id_generic.csv')
verify_df = df[df['match_strategy'].str.contains('VERIFY', na=False)]
verify_df.to_csv('outputs/verification_queue.csv', index=False)
print(f'Extracted {len(verify_df)} records for verification')
"
```

### Step 2: Create Verification Spreadsheet

**Columns to include**:
1. `research_id` - CBTN research identifier
2. `FHIR_ID` - Matched FHIR patient ID
3. `match_database` - Source database (CHOP or UCSF)
4. `match_strategy` - How matched (e.g., `chop_dob_only_single_VERIFY`)
5. `dob` - Date of birth (for reference)
6. `enrollment_name` - Name from CBTN enrollment (first + last)
7. `verification_status` - **EMPTY** (to be filled by reviewer)
8. `verification_notes` - **EMPTY** (for comments)
9. `reviewer_name` - **EMPTY** (who verified)
10. `review_date` - **EMPTY** (when verified)

**DO NOT INCLUDE** in spreadsheet:
- Full DOB if year is sufficient
- MRN
- Other PHI fields

### Step 3: Query Database for Actual Names

**For each VERIFY record**, look up the actual name in Athena:

```python
# Script to generate verification lookup (run securely)
import boto3
import pandas as pd

verify_df = pd.read_csv('outputs/verification_queue.csv')
session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
athena_client = session.client('athena')

# Query for each FHIR_ID
for idx, row in verify_df.iterrows():
    fhir_id = row['FHIR_ID']
    database = 'fhir_v2_prd_db' if row['match_database'] == 'chop' else 'fhir_v2_ucsf_prd_db'
    
    query = f"""
    SELECT given_name, family_name 
    FROM patient 
    WHERE id = '{fhir_id}'
    """
    
    # Execute and fetch
    # ... (query execution code)
    
    verify_df.at[idx, 'database_name'] = f"{given_name} {family_name}"

verify_df.to_csv('outputs/verification_queue_with_db_names.csv', index=False)
```

**Security note**: This file contains names + DOBs. Keep encrypted, delete after verification.

### Step 4: Manual Review

**For each record**:

1. **Compare names**: Enrollment vs Database
   
2. **Check for patterns** from "Common Name Variation Patterns" above
   
3. **Assign verification_status**:
   - `CONFIRMED` - Names match (accounting for variations)
   - `REJECTED` - Different patient (remove FHIR_ID)
   - `UNCERTAIN` - Needs additional information

4. **Document reasoning** in verification_notes

5. **Sign and date**

### Step 5: Apply Verification Results

```python
# Update main output file with verification results
import pandas as pd

main_df = pd.read_csv('outputs/stg_cbtn_enrollment_with_fhir_id_generic.csv')
verify_df = pd.read_csv('outputs/verification_queue_reviewed.csv')

# Remove REJECTED matches
rejected = verify_df[verify_df['verification_status'] == 'REJECTED']
for idx, row in rejected.iterrows():
    mask = main_df['research_id'] == row['research_id']
    main_df.loc[mask, 'FHIR_ID'] = None
    main_df.loc[mask, 'match_strategy'] = None
    main_df.loc[mask, 'match_database'] = None

# Update match_strategy for CONFIRMED matches
confirmed = verify_df[verify_df['verification_status'] == 'CONFIRMED']
for idx, row in confirmed.iterrows():
    mask = main_df['research_id'] == row['research_id']
    # Remove _VERIFY suffix
    main_df.loc[mask, 'match_strategy'] = main_df.loc[mask, 'match_strategy'].str.replace('_VERIFY', '_VERIFIED')

main_df.to_csv('outputs/stg_cbtn_enrollment_with_fhir_id_VERIFIED.csv', index=False)
print(f'Confirmed: {len(confirmed)}, Rejected: {len(rejected)}')
```

## Decision Guidelines

### CONFIRM if:
- ✓ Common nickname variation (Bill/William, Liz/Elizabeth)
- ✓ Single-letter spelling difference (Jon/John, Sara/Sarah)
- ✓ Middle name added/removed
- ✓ Obvious typo (Jonh/John, Micheal/Michael)
- ✓ Cultural name order variation (with supporting evidence)
- ✓ Hyphenated surname variation (maiden vs married name, with supporting evidence)

### REJECT if:
- ✗ Completely different first name AND last name
- ✗ Different gender implied by name (unless confirmed non-binary/trans)
- ✗ No plausible explanation for name difference
- ✗ DOB is common (e.g., Jan 1) and names unrelated
- ✗ Multiple possible patients in database (should not happen, but double-check)

### UNCERTAIN if:
- ? Name difference could go either way
- ? Need additional information (e.g., gender, location)
- ? Cultural naming conventions unclear
- ? Possible transcription error vs different patient

**For UNCERTAIN cases**: Flag for senior review, consult with clinical team, or check additional data sources.

## Quality Assurance

### Random Sample Audit

**Procedure**:
1. Select 10% random sample of CONFIRMED verifications
2. Independent reviewer re-evaluates
3. Calculate inter-rater agreement
4. Target: >95% agreement

### Error Rate Monitoring

**Track**:
- False positive rate (CONFIRMED but actually different patient)
- False negative rate (REJECTED but actually same patient)
- Uncertain rate (flagged for additional review)

**Acceptable thresholds**:
- False positive rate: <2%
- False negative rate: <5%
- Uncertain rate: <10%

## Documentation Requirements

### For Each Verification Session

Document:
- Date of verification
- Reviewer name(s)
- Number of records reviewed
- Number CONFIRMED / REJECTED / UNCERTAIN
- Any systematic issues identified
- Time spent

### For Project Records

Maintain:
- Verification queue files (encrypted, restricted access)
- Verification results (who, what, when, why)
- Inter-rater agreement statistics
- Error rate monitoring
- Lessons learned / pattern updates

## Advanced Verification Techniques

### 1. Check Gender Consistency

```python
# If gender available in database
if row['database_gender'] == 'male' and enrollment_name in female_names:
    verification_status = 'REVIEW_GENDER_MISMATCH'
```

### 2. Leverage Research ID Patterns

```python
# If research IDs correlate with enrollment sites/dates
if row['research_id'].startswith('CHOP') and row['match_database'] == 'ucsf':
    verification_status = 'REVIEW_SITE_MISMATCH'
```

### 3. Cross-Reference with Other Data

If available:
- Diagnosis codes (should be consistent)
- Treatment dates (should align with enrollment dates)
- Genomic data (if linked to research_id)

## Common Pitfalls to Avoid

1. **Don't assume all single-candidate matches are correct**
   - Some DOBs are common (Jan 1, etc.)
   - Data entry errors can occur

2. **Don't rely solely on automated name matching**
   - Cultural variations are complex
   - Context matters (nickname usage varies by region)

3. **Don't batch-approve without review**
   - Each record needs individual assessment
   - Patterns help, but exceptions exist

4. **Don't ignore UNCERTAIN cases**
   - These may reveal systematic issues
   - Flag for additional investigation

## Tools & Resources

### Nickname Reference Lists
- [Wikipedia: List of Nickname Variants](https://en.wikipedia.org/wiki/List_of_nickname_variants)
- [Behind the Name: Nickname Database](https://www.behindthename.com/)

### Name Similarity Calculators
- Levenshtein distance calculators (online)
- Soundex/Metaphone phonetic matching

### PHI-Safe Collaboration
- Use research_id + hashed name for discussion
- Never share full names + DOBs in unencrypted channels

## Contact & Escalation

### For Questions
- **Senior data analyst**: [TO BE FILLED]
- **Clinical team lead**: [TO BE FILLED]

### For Systematic Issues
- **Data quality team**: [TO BE FILLED]
- **CBTN data coordinator**: [TO BE FILLED]

### For Security Concerns
- **Compliance officer**: [TO BE FILLED]
- **IRB office**: [TO BE FILLED]

---

**Document Version**: 1.0  
**Last Updated**: October 26, 2025  
**Classification**: Internal Use Only  
**Author**: RADIANT/BRIM Analytics Team
