# Investigational Drug Validation Proposal

## Problem Statement

The current `investigational_drug_extraction` feature in V_CHEMO_MEDICATIONS extracts drug names from clinical trial notes but has three critical issues:

1. **No Parsing**: Multi-drug regimen strings are treated as single drugs
2. **No Validation**: No verification against actual medication_request records
3. **Incomplete Coverage**: Some parsed drugs not in drugs.csv reference

## Validation Results Summary

### Scope
- **15,168 records** (13.5% of investigational extractions) have multi-drug strings
- **12 unique combo-strings** affecting **86 patients**
- **Same 86 patients** appear in all combo-strings (suggests same trial cohort)

### Evidence Analysis (60 patients sampled)
- **75%** have evidence for SOME individual drugs from combo-string
- **25%** have NO evidence for ANY individual drugs
- **Common pattern**: Only 1-2 drugs have medication_request records, others exist only in notes

### Reference Coverage
- **87.9%** of parsed drugs ARE in drugs.csv
- **12.1%** are NOT (mostly parsing errors or investigational-only drugs)

## Proposed Solution: Multi-Stage Validation Pipeline

### Stage 1: Enhanced Parsing with Cleaning

```sql
CREATE FUNCTION parse_investigational_drugs(drug_string VARCHAR)
RETURNS ARRAY(VARCHAR)
LANGUAGE SQL
AS $$
WITH cleaned AS (
    -- Remove prefixes
    SELECT REGEXP_REPLACE(
        REGEXP_REPLACE(
            REGEXP_REPLACE(drug_string, '^combination,?\s+', ''),
            'braf inhibitor\s+', ''
        ),
        'mek inhibitor\s+', ''
    ) AS s
),
split_drugs AS (
    -- Normalize delimiters and split
    SELECT REGEXP_SPLIT(
        REGEXP_REPLACE(
            REGEXP_REPLACE(s, '\s+and\s+', ', '),
            '\s+plus\s+', ', '
        ),
        '\s*,\s*'
    ) AS drugs
    FROM cleaned
)
-- Filter out non-drug noise
SELECT ARRAY_AGG(drug)
FROM split_drugs
CROSS JOIN UNNEST(drugs) AS drug
WHERE drug NOT IN ('once daily', 'twice daily', 'softs', 'combination', '')
$$;
```

### Stage 2: Individual Drug Validation

For each parsed drug, check:

1. **Does it exist in drugs.csv?**
   - YES → Use preferred_name and therapeutic_normalized
   - NO → Flag for manual review

2. **Does patient have a medication_request for this drug?**
   - YES → Mark as "validated"
   - NO → Mark as "note_only"

3. **Validation confidence levels:**
   - `high`: In drugs.csv AND has medication_request
   - `medium`: In drugs.csv but NO medication_request (note-only)
   - `low`: NOT in drugs.csv (unverifiable)

### Stage 3: Validation Metadata

Add validation fields to v_chemo_medications:

```sql
-- New columns in investigational_with_extracted_names CTE:
parsed_from_combo_string BOOLEAN,
original_combo_string VARCHAR,
validation_status VARCHAR,  -- 'validated', 'note_only', 'unverifiable'
has_individual_med_request BOOLEAN,
in_reference_drugs BOOLEAN
```

## Implementation Plan

### Phase 1: SQL Updates (V_CHEMO_MEDICATIONS.sql)

1. Add drug parsing function (or use REGEXP_SPLIT inline)
2. Update `investigational_drug_extraction` CTE to:
   - Parse multi-drug strings
   - Create one row per individual drug
   - Track original combo-string

3. Update `investigational_with_extracted_names` CTE to:
   - Validate against patient's other medications
   - Add validation metadata

### Phase 2: Python Validation Script

Create `validate_investigational_extraction.py` to:
- Run periodically to audit investigational extraction quality
- Flag combo-strings that need manual review
- Report validation statistics
- Identify drugs missing from drugs.csv

### Phase 3: drugs.csv Updates

Add missing investigational drugs identified through validation:
- amg386 (appears 1,263 times)
- Any other high-frequency investigational drugs

## Expected Outcomes

### Before (Current State)
- 12 false "combo-drug" paradigms
- 15,168 records with unparsed multi-drug strings
- No validation of note-extracted drugs
- Duplicate counting (e.g., bevacizumab in combo AND standalone)

### After (With Validation)
- 0 false combo-drug paradigms (all parsed)
- Each drug counted individually with validation status
- Clear distinction between:
  - Validated drugs (in drugs.csv + has med_request)
  - Note-only drugs (in drugs.csv, no med_request)
  - Unverifiable drugs (not in drugs.csv)
- Accurate paradigm discovery based on validated drugs

## Risk Assessment

### Low Risk
- Parsing multi-drug strings (reversible, clear logic)
- Adding validation metadata (non-breaking)

### Medium Risk
- Breaking existing combo-strings may affect:
  - Existing paradigm analyses (need re-run)
  - Downstream analytics expecting combo-strings

### Mitigation
- Add `original_combo_string` column to preserve raw data
- Run validation in parallel first, compare results
- Document changes in view header comments

## Next Steps

1. **Approve approach** with stakeholders
2. **Implement Stage 1** (parsing) in V_CHEMO_MEDICATIONS.sql
3. **Deploy to dev** environment for testing
4. **Run validation** script to assess impact
5. **Update drugs.csv** with missing investigational drugs
6. **Deploy to prod** after validation
7. **Re-run paradigm analysis** with parsed drugs

## Questions for Review

1. Should we exclude "note_only" drugs from paradigm analysis entirely?
2. What confidence threshold for including investigational drugs?
3. Should we create a separate `investigational_drugs.csv` reference?
4. How to handle parsing errors (e.g., "of gemcitabine")?

---

**Document created:** 2025-10-26
**Analysis based on:** 244,869 chemotherapy medication records from v_chemo_medications
