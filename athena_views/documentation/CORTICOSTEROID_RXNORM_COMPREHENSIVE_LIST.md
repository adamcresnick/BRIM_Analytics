# Comprehensive Corticosteroid RxNorm Identification Strategy

**Date**: 2025-10-18
**Purpose**: Define all possible corticosteroid RxNorm values for clinical use

---

## Problem Statement

**Current Implementation**: Only 10 hardcoded RxNorm CUI codes (incomplete)
**Risk**: Missing many corticosteroid formulations, combinations, and newer drugs
**Need**: Comprehensive, maintainable approach to identify ALL corticosteroids

---

## Recommended Solutions (Ranked)

### **Option 1: RxClass API Query (BEST - Most Comprehensive)**

**Approach**: Use NLM RxClass API to query ATC class H02 (Corticosteroids for systemic use)

**API Endpoint**:
```
https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=H02&relaSource=ATC&rela=isa
```

**ATC Classifications for Corticosteroids**:
- **H02AB** - Glucocorticoids (systemic - most relevant)
- **H02AA** - Mineralocorticoids (fludrocortisone)
- **H02B** - Corticosteroids for local use (exclude - not systemic)
- **H02C** - Combinations with antibiotics (include if systemic)

**API Parameters**:
- `classId=H02AB` - Glucocorticoids only (recommended for neuro-onc)
- `classId=H02` - All corticosteroids (broader)
- `relaSource=ATC` - Use ATC classification system
- `rela=isa` - "is a" relationship
- `tty=IN` - Filter to ingredients only

**Example API Call for Ingredients Only**:
```
https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=H02AB&relaSource=ATC&ttys=IN
```

**Pros**:
- ✅ Automatically comprehensive (includes all current RxNorm drugs)
- ✅ Maintained by NLM (updates with new drugs)
- ✅ Standardized classification (ATC WHO)
- ✅ Can filter by TTY=IN (ingredients only)
- ✅ Free, no license required

**Cons**:
- ⚠️ Requires external API call or manual update
- ⚠️ One-time export needed to populate Athena view

**Implementation**:
1. Query RxClass API once
2. Extract all RxNorm CUIs with TTY=IN
3. Store in static list in SQL view
4. Update quarterly/annually as needed

---

### **Option 2: Query FHIR Database Directly (PRACTICAL)**

**Approach**: Find all RxNorm codes actually used in your FHIR database, then manually classify

**SQL Query**:
```sql
-- Find all unique RxNorm codes in medication data
SELECT DISTINCT
    mcc.code_coding_code as rxnorm_cui,
    mcc.code_coding_display as rxnorm_display,
    COUNT(DISTINCT mr.id) as prescription_count,
    COUNT(DISTINCT mr.subject_reference) as patient_count
FROM fhir_prd_db.medication_request mr
LEFT JOIN fhir_prd_db.medication m
    ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
LEFT JOIN fhir_prd_db.medication_code_coding mcc
    ON mcc.medication_id = m.id
    AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
WHERE mcc.code_coding_code IS NOT NULL
GROUP BY mcc.code_coding_code, mcc.code_coding_display
ORDER BY prescription_count DESC;
```

Then filter results for:
```sql
WHERE LOWER(rxnorm_display) LIKE '%cortisone%'
   OR LOWER(rxnorm_display) LIKE '%prednisone%'
   OR LOWER(rxnorm_display) LIKE '%dexamethasone%'
   OR LOWER(rxnorm_display) LIKE '%methylprednisolone%'
   -- etc.
```

**Pros**:
- ✅ Only includes drugs actually in your data
- ✅ Efficient (smaller list)
- ✅ Easy to validate against real prescriptions

**Cons**:
- ⚠️ May miss rarely used corticosteroids
- ⚠️ Requires manual classification
- ⚠️ Needs periodic updates as new drugs prescribed

---

### **Option 3: Curated Clinical List (CURRENT - Limited)**

**Approach**: Manually curate list based on clinical knowledge

**Complete Systemic Glucocorticoid Ingredient List**:

| Generic Name | RxNorm CUI (IN) | Common Brands | Relative Potency | Clinical Use |
|--------------|-----------------|---------------|------------------|--------------|
| **Dexamethasone** | 3264 | Decadron | 25-30x | First-line CNS edema |
| Betamethasone | 1347 | Celestone | 25-30x | High potency |
| Prednisone | 8640 | Deltasone, Rayos | 4x | Oral maintenance |
| Prednisolone | 8638 | Orapred, Prelone | 4x | Oral (active form) |
| Methylprednisolone | 6902 | Medrol, Solu-Medrol | 5x | IV pulse therapy |
| Triamcinolone | 10759 | Kenalog, Aristospan | 5x | Various routes |
| Hydrocortisone | 5492 | Cortef, Solu-Cortef | 1x (baseline) | Stress dosing |
| Cortisone | 3008 | Cortone | 0.8x | Rarely used |
| Budesonide | 1810 | Entocort, Uceris | Variable | GI-targeted |
| Fludrocortisone | 4449 | Florinef | 10x (mineralocorticoid) | Adrenal insufficiency |
| Deflazacort | 23244 | Emflaza | 5x | Duchenne MD |
| Paramethasone | 8001 | Haldrone | 10x | Rare |
| Meprednisone | 6809 | Betapar | 5x | Discontinued |

**Additional Systemic Corticosteroids** (less common):
- Fluocortolone: 4450
- Clocortolone: 2551
- Desoximetasone: 3139
- Diflorasone: 3407
- Mometasone: 83367 (mostly topical, but IV exists)

**Mineralocorticoids** (include for completeness):
- Fludrocortisone: 4449
- Desoxycorticosterone: 3140

**Pros**:
- ✅ Quick to implement
- ✅ Focused on clinically relevant drugs
- ✅ Easy to understand and validate

**Cons**:
- ⚠️ Manually maintained (requires clinical knowledge)
- ⚠️ May miss new drugs or rare formulations
- ⚠️ No automatic updates

---

## RxNorm Ingredient (TTY=IN) vs Clinical Drug (TTY=SCD/SBD)

### Understanding RxNorm Term Types

**IN (Ingredient)**: Base drug substance
- Example: "Dexamethasone" (CUI: 3264)
- **Use this for broad matching**

**SCD (Semantic Clinical Drug)**: Generic + strength + dose form
- Example: "Dexamethasone 4 MG Oral Tablet" (CUI: 197582)
- **Use this for specific formulation matching**

**SBD (Semantic Branded Drug)**: Brand + strength + dose form
- Example: "Decadron 4 MG Oral Tablet" (CUI: 197589)

**Recommendation**: Match on **IN (ingredient)** level to catch all formulations

---

## Expanded RxNorm CUI List (Option 3 Enhanced)

### Tier 1: High Priority (Common in Neuro-Oncology)

```sql
mcc.code_coding_code IN (
    '3264',   -- Dexamethasone *** MOST IMPORTANT ***
    '8640',   -- Prednisone
    '6902',   -- Methylprednisolone
    '8638',   -- Prednisolone
    '5492',   -- Hydrocortisone
    '1347'    -- Betamethasone
)
```

### Tier 2: Less Common but Systemic

```sql
mcc.code_coding_code IN (
    '10759',  -- Triamcinolone
    '1810',   -- Budesonide
    '4449',   -- Fludrocortisone
    '3008',   -- Cortisone
    '23244',  -- Deflazacort
    '8001',   -- Paramethasone
    '3140'    -- Desoxycorticosterone
)
```

### Tier 3: Rare/Historical

```sql
mcc.code_coding_code IN (
    '6809',   -- Meprednisone
    '4450',   -- Fluocortolone
    '2551',   -- Clocortolone
    '3139',   -- Desoximetasone
    '3407'    -- Diflorasone
)
```

---

## Combination Products

**Challenge**: Corticosteroids in combination products

**Examples**:
- Prednisone + Aspirin
- Dexamethasone + Antibiotic (eye drops)
- Hydrocortisone + Pramoxine (topical)

**RxNorm Strategy**: Query for ingredients using `getRelatedByType` with `rela=has_ingredient`

**SQL Strategy**:
```sql
-- Check if any ingredient in combination is a corticosteroid
WHERE mcc.code_coding_code IN (corticosteroid_cui_list)
   OR m.code_text IN (
       SELECT DISTINCT ingredient_name
       FROM corticosteroid_ingredients
   )
```

---

## Text Matching Strategy (Fallback)

For medications without RxNorm codes, use text pattern matching:

```sql
-- Generic names
LOWER(medication_text) LIKE '%dexamethasone%'
OR LOWER(medication_text) LIKE '%prednisone%'
OR LOWER(medication_text) LIKE '%methylprednisolone%'
OR LOWER(medication_text) LIKE '%prednisolone%'
OR LOWER(medication_text) LIKE '%hydrocortisone%'
OR LOWER(medication_text) LIKE '%betamethasone%'
OR LOWER(medication_text) LIKE '%triamcinolone%'
OR LOWER(medication_text) LIKE '%budesonide%'
OR LOWER(medication_text) LIKE '%cortisone%'
OR LOWER(medication_text) LIKE '%fludrocortisone%'
OR LOWER(medication_text) LIKE '%deflazacort%'

-- Common brand names
OR LOWER(medication_text) LIKE '%decadron%'
OR LOWER(medication_text) LIKE '%medrol%'
OR LOWER(medication_text) LIKE '%solu-medrol%'
OR LOWER(medication_text) LIKE '%solumedrol%'
OR LOWER(medication_text) LIKE '%deltasone%'
OR LOWER(medication_text) LIKE '%orapred%'
OR LOWER(medication_text) LIKE '%cortef%'
OR LOWER(medication_text) LIKE '%solu-cortef%'
OR LOWER(medication_text) LIKE '%celestone%'
OR LOWER(medication_text) LIKE '%kenalog%'
OR LOWER(medication_text) LIKE '%entocort%'
OR LOWER(medication_text) LIKE '%florinef%'
OR LOWER(medication_text) LIKE '%emflaza%'

-- Suffix pattern (less specific)
OR LOWER(medication_text) LIKE '%cortisone%'  -- Catches hydrocortisone, etc.
OR LOWER(medication_text) LIKE '%sone%'       -- Prednisone, prednisolone, etc.
```

**Warning**: `%sone%` is very broad and may catch non-steroids (e.g., Ibandronate)
**Recommendation**: Use specific terms only

---

## Excluding Non-Systemic Routes

**Important**: Exclude topical, inhaled, ophthalmic formulations

**Route Filtering** (if available in data):
```sql
AND (
    mr.dosage_instruction_route_coding LIKE '%oral%'
    OR mr.dosage_instruction_route_coding LIKE '%intravenous%'
    OR mr.dosage_instruction_route_coding LIKE '%intramuscular%'
    OR mr.dosage_instruction_route_coding LIKE '%subcutaneous%'
    OR mr.dosage_instruction_route_coding IS NULL  -- Include unknown routes
)

-- Exclude
AND NOT (
    mr.dosage_instruction_route_coding LIKE '%topical%'
    OR mr.dosage_instruction_route_coding LIKE '%inhaled%'
    OR mr.dosage_instruction_route_coding LIKE '%ophthalmic%'
    OR mr.dosage_instruction_route_coding LIKE '%nasal%'
    OR mr.dosage_instruction_route_coding LIKE '%otic%'
    OR mr.dosage_instruction_route_coding LIKE '%dermal%'
)
```

**Text-based route filtering**:
```sql
AND NOT (
    LOWER(medication_text) LIKE '%cream%'
    OR LOWER(medication_text) LIKE '%ointment%'
    OR LOWER(medication_text) LIKE '%lotion%'
    OR LOWER(medication_text) LIKE '%gel%'
    OR LOWER(medication_text) LIKE '%eye drop%'
    OR LOWER(medication_text) LIKE '%ophthalmic%'
    OR LOWER(medication_text) LIKE '%inhaler%'
    OR LOWER(medication_text) LIKE '%nasal spray%'
)
```

---

## Recommended Implementation Plan

### **Phase 1: Query RxClass API (One-Time)**

**Action Items**:
1. Call RxClass API: `https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=H02AB&relaSource=ATC&ttys=IN`
2. Parse JSON response to extract all RxNorm CUI codes
3. Filter to TTY=IN (ingredients only)
4. Create static list for SQL view

**Deliverable**: Comprehensive RxNorm CUI list (~20-30 corticosteroid ingredients)

### **Phase 2: Validate Against FHIR Data**

**Action Items**:
1. Query actual medications in FHIR database
2. Cross-reference with RxClass results
3. Identify any corticosteroids in your data missing from RxClass list
4. Add manual entries for edge cases

**Deliverable**: Validated, data-specific corticosteroid list

### **Phase 3: Implement in SQL View**

**Action Items**:
1. Add complete RxNorm CUI list to view WHERE clause
2. Add comprehensive text matching patterns
3. Add route filtering (if available)
4. Test against known corticosteroid prescriptions

**Deliverable**: Production-ready SQL view

### **Phase 4: Quarterly Updates**

**Action Items**:
1. Re-query RxClass API quarterly
2. Check for new corticosteroid ingredients
3. Update SQL view if new drugs found

---

## Example: Complete RxClass API Query

```bash
# Get all H02AB glucocorticoid members
curl "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=H02AB&relaSource=ATC&ttys=IN"

# Get all H02 corticosteroid members (broader)
curl "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=H02&relaSource=ATC&ttys=IN"
```

**Expected Output** (sample):
```json
{
  "drugMemberGroup": {
    "drugMember": [
      {
        "minConcept": {
          "rxcui": "3264",
          "name": "Dexamethasone",
          "tty": "IN"
        }
      },
      {
        "minConcept": {
          "rxcui": "8640",
          "name": "Prednisone",
          "tty": "IN"
        }
      },
      ...
    ]
  }
}
```

---

## Quality Assurance Checks

### 1. Coverage Check
```sql
-- What % of corticosteroid prescriptions are captured?
SELECT
    CASE WHEN detection_method IS NOT NULL THEN 'Detected' ELSE 'Missed' END as status,
    COUNT(*) as prescription_count
FROM potential_corticosteroid_prescriptions
GROUP BY status;
```

### 2. False Positive Check
```sql
-- Manual review of detected corticosteroids
SELECT DISTINCT
    corticosteroid_name,
    rxnorm_cui,
    detection_method,
    COUNT(*) as occurrences
FROM v_imaging_corticosteroid_use
WHERE on_corticosteroid = true
GROUP BY corticosteroid_name, rxnorm_cui, detection_method
ORDER BY occurrences DESC;
```

### 3. New Drug Alert
```sql
-- Find medications with "steroid" or "cortisone" in name not in our list
SELECT DISTINCT
    m.code_text,
    mcc.code_coding_code as rxnorm_cui,
    COUNT(*) as prescription_count
FROM medication_request mr
JOIN medication m ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
LEFT JOIN medication_code_coding mcc ON mcc.medication_id = m.id
WHERE (
    LOWER(m.code_text) LIKE '%steroid%'
    OR LOWER(m.code_text) LIKE '%cortisone%'
    OR LOWER(m.code_text) LIKE '%prednis%'
)
AND mcc.code_coding_code NOT IN (known_corticosteroid_list)
GROUP BY m.code_text, mcc.code_coding_code
ORDER BY prescription_count DESC;
```

---

## Final Recommendation

**Use Hybrid Approach**:

1. **Primary**: RxClass API query for H02AB (glucocorticoids) + H02AA (mineralocorticoids)
   - Provides ~15-20 ingredient-level RxNorm CUIs
   - Automatically comprehensive

2. **Secondary**: Text matching for brand names and variations
   - Catches medications without RxNorm codes
   - Handles misspellings and abbreviations

3. **Tertiary**: Manual review of unmatched high-frequency medications
   - Quarterly data quality check
   - Add edge cases discovered in production

4. **Validation**: Cross-reference against actual FHIR prescriptions
   - Ensure no commonly used corticosteroids are missed
   - Identify false positives

This three-tier approach balances **comprehensiveness** (RxClass API), **practicality** (actual data), and **maintainability** (text patterns).

