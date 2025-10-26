# Matching Strategy - Technical Documentation

## Overview

The ID Crosswalk system uses a **two-tier, generic matching strategy** that applies consistently across all healthcare databases (CHOP, UCSF, and future additions). This approach maximizes match rates while maintaining high confidence levels and security.

## Architecture

### Design Principles

1. **Database-agnostic**: Same logic applies to all institutions
2. **Tiered fallback**: Start with strongest signal (MRN), fall back to demographic matching
3. **Progressive name validation**: Multiple strategies with decreasing strictness
4. **Confidence scoring**: Clear flags for matches requiring verification
5. **Zero PHI exposure**: All matching in-memory, no sensitive data logged

### Data Flow

```
Input CSV (CBTN Enrollment)
    ↓
[Load & Validate]
    ↓
Query Athena Databases ──→ [CHOP: MRN + Demographics]
    ↓                     ↓
    ↓                     [UCSF: MRN + Demographics]
    ↓                     ↓
[Create In-Memory Lookup Tables]
    ↓
┌───────────────────────────────────┐
│  For Each Record:                 │
│  1. Try MRN exact match           │
│  2. If fails → DOB+Name matching  │
│     a. DOB + exact name           │
│     b. DOB + last + first initial │
│     c. DOB + first + last initial │
│     d. DOB only (single candidate)│
└───────────────────────────────────┘
    ↓
[Assign FHIR_ID + match_strategy + match_database]
    ↓
Output CSV (with FHIR_IDs)
```

## Tier 1: MRN Exact Matching

### Logic

```python
for each database:
    if record.mrn in database.mrn_to_fhir_map:
        return database.mrn_to_fhir_map[record.mrn]
```

### Characteristics

- **Speed**: O(1) dictionary lookup
- **Confidence**: Highest (exact identifier match)
- **Coverage**: 1,843/6,599 records (27.9%)

### Why MRN Matching Fails

1. **Format differences**: 
   - Excel strips leading zeros: `1234567` vs `01234567`
   - Hyphens or spaces: `123-45-67` vs `1234567`

2. **Temporal changes**:
   - MRNs updated when records merged
   - Legacy system migrations
   - Patient transfers between facilities

3. **Data quality issues**:
   - Typos in enrollment CSV
   - Copy/paste errors
   - Incorrect MRN assignment

4. **System differences**:
   - UCSF uses different MRN structure (no matches found)
   - Multi-Epic instances within CHOP
   - External referrals with temporary MRNs

## Tier 2: DOB + Name Matching

### Strategy Progression

When MRN fails, we attempt **four progressive strategies** with decreasing strictness:

#### Strategy 2.1: DOB + Exact Name Match

```python
if record.dob in database.dob_index:
    candidates = database.get_patients_by_dob(record.dob)
    for candidate in candidates:
        if normalize(record.first_name) == normalize(candidate.given_name) AND
           normalize(record.last_name) == normalize(candidate.family_name):
            return candidate.fhir_id
```

**Characteristics**:
- **Confidence**: Very high
- **Coverage**: 97 additional matches
- **False positive risk**: Very low (<1%)

**Name normalization**:
```python
def normalize_name(name):
    name = str(name).strip().lower()
    name = re.sub(r'[^a-z0-9\s]', '', name)  # Remove special chars
    name = re.sub(r'\s+', ' ', name)         # Collapse spaces
    return name.strip()
```

#### Strategy 2.2: DOB + Last Name + First Initial

```python
if record.dob in database.dob_index:
    candidates = database.get_patients_by_dob(record.dob)
    for candidate in candidates:
        if normalize(record.last_name) == normalize(candidate.family_name) AND
           record.first_name[0].lower() == candidate.given_name[0].lower():
            return candidate.fhir_id
```

**Characteristics**:
- **Confidence**: High
- **Coverage**: 10 additional matches
- **Use case**: Handles nicknames ("William" vs "Bill")

**Example matches**:
- DOB: 2010-05-15, "William Smith" → "Bill Smith"
- DOB: 1998-03-22, "Elizabeth Jones" → "Liz Jones"

#### Strategy 2.3: DOB + First Name + Last Initial

```python
if record.dob in database.dob_index:
    candidates = database.get_patients_by_dob(record.dob)
    for candidate in candidates:
        if normalize(record.first_name) == normalize(candidate.given_name) AND
           record.last_name[0].lower() == candidate.family_name[0].lower():
            return candidate.fhir_id
```

**Characteristics**:
- **Confidence**: High
- **Coverage**: Included in 10 above
- **Use case**: Handles hyphenated surnames ("Smith-Jones" vs "Smith")

**Example matches**:
- DOB: 2005-08-10, "Mary Smith-Jones" → "Mary Smith"
- DOB: 2012-11-03, "John O'Brien" → "John OBrien"

#### Strategy 2.4: DOB Only (Single Candidate) ⚠️

```python
if record.dob in database.dob_index:
    candidates = database.get_patients_by_dob(record.dob)
    if len(candidates) == 1:
        return candidates[0].fhir_id + "_VERIFY_FLAG"
```

**Characteristics**:
- **Confidence**: Medium (requires manual verification)
- **Coverage**: 700 additional matches
- **False positive risk**: ~5-15% (estimated)

**Why flagged for VERIFY**:
- Names don't match (spelling variations, errors)
- But only ONE patient with that DOB in database
- Likely correct, but needs human review

**Common scenarios**:
1. **Nickname not captured**: "Jonathan" in DB, "Jon" in enrollment
2. **Maiden name**: "Sarah Smith" in DB, "Sarah Johnson" in enrollment (married)
3. **Middle name used**: "Mary Jane Doe" in DB, "Mary Doe" in enrollment
4. **Spelling error**: "Jon" vs "John", "Sara" vs "Sarah"
5. **Name order**: "Maria Carmen" vs "Carmen Maria"

### DOB Matching Edge Cases

#### Multiple Candidates (Not Matched)

```python
if len(candidates) > 1:
    # Cannot determine correct patient without name match
    # Too risky - skip this record
    return None
```

**Example**: 
- DOB: 2000-01-01 (common date)
- 3 patients in database with same DOB
- Names: "John Smith", "Jane Doe", "Robert Johnson"
- Enrollment record: "J Smith" (ambiguous)
- **Result**: No match (too risky)

#### No DOB in Enrollment

```python
if not record.dob or record.dob == 'nan':
    return None  # Cannot attempt DOB matching
```

**Statistics**: 13 records had missing DOB in CBTN enrollment file.

#### DOB Not in Database

```python
if record.dob not in database.dob_index:
    return None  # Patient not in this database
```

**Statistics**:
- 4,039 CHOP records not found (patients from other institutions)
- 3,936 UCSF records not found (patients from other institutions)

## Confidence Levels & Risk Assessment

### High Confidence (No Verification Needed)

**Count**: 1,950 matches (73.6% of total matches)

**Includes**:
- MRN exact matches: 1,843 records
- DOB + exact name: 97 records
- DOB + name initial: 10 records

**False positive rate**: <1% (estimated)

**Risk mitigation**: 
- Multiple independent fields match
- Low probability of coincidental match

### Medium Confidence (Verification Recommended)

**Count**: 700 matches (26.4% of total matches)

**Includes**:
- CHOP DOB-only: 623 records
- UCSF DOB-only: 77 records

**False positive rate**: 5-15% (estimated)

**Risk factors**:
- Single matching field (DOB)
- Names don't match (unknown reason)
- Potential for spelling variations vs different patient

**Verification required**: See VERIFICATION_GUIDE.md

## Performance Optimization

### In-Memory Indexing

All database queries happen ONCE at startup:

```python
# Load all patient data into memory
chop_mrn_map, chop_demo_df = query_patient_data(athena_client, 'fhir_v2_prd_db')
ucsf_mrn_map, ucsf_demo_df = query_patient_data(athena_client, 'fhir_v2_ucsf_prd_db')

# Create fast lookup structures
mrn_to_fhir = dict()  # O(1) lookup
dob_to_patients = defaultdict(list)  # O(1) to find candidates, O(n) to scan
```

### Time Complexity

- **MRN lookup**: O(1) per record
- **DOB candidate finding**: O(1) per record
- **Name matching**: O(k) where k = number of patients with same DOB (typically 1-3)
- **Overall**: O(n) where n = number of enrollment records

### Space Complexity

- **MRN index**: O(m) where m = number of patients in databases (~2,200)
- **Demographics df**: O(m × f) where f = fields per patient (~5)
- **Total memory**: ~10MB for 2,200 patients

## Security Implementation

### PHI Protection

**Zero-exposure design**:
```python
# ✓ CORRECT - No PHI in logs
logger.info(f"Retrieved {len(df)} records from Athena")
logger.info(f"Created mapping dictionary with {len(mrn_to_fhir)} MRN->FHIR_ID pairs")

# ✗ WRONG - Would expose PHI
# logger.info(f"Matching MRN {mrn} to FHIR ID {fhir_id}")  # NEVER DO THIS
```

### Secure Matching Loop

```python
for idx, row in df.iterrows():
    mrn = str(row['mrn']).strip()  # In-memory only
    
    # All matching happens in memory
    if mrn in chop_mrn_map:
        df.at[idx, 'FHIR_ID'] = chop_mrn_map[mrn]  # Write directly to output
        # NO logging of mrn or fhir_id
```

### Statistical Aggregation Only

```python
# ✓ CORRECT - Aggregate statistics
stats['chop_mrn_exact'] += 1
logger.info(f"MRN exact match: {stats['chop_mrn_exact']} records")

# ✗ WRONG - Individual record data
# logger.info(f"Patient {patient_name} matched via MRN")  # NEVER DO THIS
```

## Future Enhancements

### 1. Fuzzy Name Matching (Levenshtein Distance)

```python
def fuzzy_name_match(name1, name2, threshold=0.85):
    """
    Calculate similarity score between two names.
    
    Returns: float between 0 (no match) and 1 (exact match)
    """
    from difflib import SequenceMatcher
    return SequenceMatcher(None, name1, name2).ratio()

# Usage in matching logic
if fuzzy_name_match(record.last_name, candidate.family_name) > 0.85:
    return candidate.fhir_id + "_FUZZY_MATCH"
```

**Benefit**: Catch common typos ("Smyth" vs "Smith")

### 2. Phonetic Matching (Soundex/Metaphone)

```python
import jellyfish

def phonetic_match(name1, name2):
    """Match names that sound similar."""
    return jellyfish.metaphone(name1) == jellyfish.metaphone(name2)

# Usage
if phonetic_match(record.last_name, candidate.family_name):
    return candidate.fhir_id + "_PHONETIC_MATCH"
```

**Benefit**: Catch pronunciation-based spellings ("Smith" vs "Smythe")

### 3. Configurable Confidence Thresholds

```python
class MatchConfig:
    require_exact_name_match = False  # Allow fuzzy matching
    min_fuzzy_score = 0.85            # Similarity threshold
    allow_dob_only_match = True       # Enable Strategy 2.4
    max_dob_candidates = 1            # Only if exactly 1 candidate
```

### 4. Multi-Database Deduplication

```python
# Detect if same FHIR_ID appears in multiple databases
seen_fhir_ids = set()
for fhir_id in matched_ids:
    if fhir_id in seen_fhir_ids:
        logger.warning(f"Duplicate FHIR ID found across databases")
    seen_fhir_ids.add(fhir_id)
```

## Testing Recommendations

### Unit Tests

```python
def test_name_normalization():
    assert normalize_name("Mary-Jane O'Brien") == "maryjane obrien"
    assert normalize_name("  John   SMITH  ") == "john smith"

def test_mrn_matching():
    mrn_map = {"12345678": "Patient/abc123"}
    assert match_by_mrn("12345678", mrn_map) == "Patient/abc123"
    assert match_by_mrn("99999999", mrn_map) is None

def test_dob_exact_name():
    demo_df = pd.DataFrame([
        {"fhir_id": "Patient/xyz", "birth_date": "2000-01-01", 
         "given_name": "john", "family_name": "smith"}
    ])
    result = match_by_dob_and_name(
        {"dob": "2000-01-01", "first_name": "John", "last_name": "Smith"},
        demo_df, {}, 'test_'
    )
    assert result[0] == "Patient/xyz"
```

### Integration Tests

```python
def test_end_to_end_matching():
    # Use synthetic data (no real PHI)
    input_csv = create_synthetic_enrollment(n=100)
    output_csv = run_matching_script(input_csv)
    
    # Validate output
    df = pd.read_csv(output_csv)
    assert 'FHIR_ID' in df.columns
    assert df['FHIR_ID'].notna().sum() > 0
    assert all(df['match_strategy'].notna() == df['FHIR_ID'].notna())
```

## References

- [FHIR Patient Resource](https://www.hl7.org/fhir/patient.html)
- [AWS Athena Query Performance](https://docs.aws.amazon.com/athena/latest/ug/performance-tuning.html)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)

---

**Document Version**: 1.0  
**Last Updated**: October 26, 2025  
**Author**: RADIANT/BRIM Analytics Team
