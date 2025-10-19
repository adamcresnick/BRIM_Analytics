# Imaging-Corticosteroid Temporal Analysis

**Date**: 2025-10-18
**Analyst**: Claude (BRIM Analytics Team)
**Clinical Context**: Brain tumor patients - corticosteroids mask tumor progression on imaging

---

## Clinical Rationale

### Why This Matters

Corticosteroids (especially **dexamethasone**) are widely used in neuro-oncology to:
1. **Reduce vasogenic edema** around brain tumors
2. **Manage mass effect** and intracranial pressure
3. **Alleviate neurological symptoms**

### Impact on Imaging Interpretation

**Critical Issue**: Corticosteroids can:
- Reduce T2/FLAIR signal abnormality (edema reduction)
- Decrease contrast enhancement (reduced blood-brain barrier disruption)
- **Mask tumor progression** → false negative for disease progression
- Create **pseudoresponse** → appears like tumor shrinkage but just edema reduction

**Clinical Implication**: RANO criteria (Response Assessment in Neuro-Oncology) require documenting steroid dose changes when interpreting imaging response.

---

## Data Requirements

### Input Sources

1. **Imaging Data** (`v_imaging` or imaging tables)
   - Patient FHIR ID
   - Imaging date/time
   - Modality (MRI brain is most relevant)
   - Study description

2. **Medication Data** (`medication_request` tables)
   - Medication name and RxNorm CUI
   - Start date/time
   - Stop date/time (or duration)
   - Dosage information

### Output Requirements

**Per imaging study, capture**:
1. Was patient on ANY corticosteroid? (Yes/No)
2. Which corticosteroid(s)? (names, RxNorm codes)
3. How many concurrent corticosteroids? (count)
4. Temporal relationship (exact match, within window, etc.)
5. Dosage information (if available)

---

## Corticosteroid Identification Strategy

### Tier 1: RxNorm CUI Codes

**Systemic Corticosteroids Used in Neuro-Oncology**:

| Medication | RxNorm CUI | Clinical Use | Notes |
|------------|------------|--------------|-------|
| **Dexamethasone** | 3264 | First-line for CNS edema | Most common in neuro-onc |
| Prednisone | 8640 | Alternative steroid | Oral, less potent |
| Prednisolone | 8638 | Alternative steroid | Similar to prednisone |
| Methylprednisolone | 6902 | IV pulse therapy | Acute situations |
| Hydrocortisone | 5492 | Stress dosing, adrenal insufficiency | Lower potency |
| Betamethasone | 1347 | High potency | Less common |
| Triamcinolone | 10759 | Various formulations | Check route |
| Budesonide | 1810 | Oral, systemic | Less common |
| Cortisone | 3008 | Older agent | Rarely used |
| Fludrocortisone | 4449 | Mineralocorticoid | For adrenal insufficiency |

**Common Brand Names** (map to same RxNorm):
- Decadron → Dexamethasone (3264)
- Solu-Medrol → Methylprednisolone (6902)
- Medrol → Methylprednisolone (6902)
- Deltasone → Prednisone (8640)
- Orapred → Prednisolone (8638)

### Tier 2: Text-Based Identification

**Generic Name Patterns**:
```sql
-- Dexamethasone variants
LOWER(medication_text) LIKE '%dexamethasone%'
OR LOWER(medication_text) LIKE '%decadron%'

-- Prednisone/Prednisolone
OR LOWER(medication_text) LIKE '%prednisone%'
OR LOWER(medication_text) LIKE '%prednisolone%'
OR LOWER(medication_text) LIKE '%deltasone%'
OR LOWER(medication_text) LIKE '%orapred%'

-- Methylprednisolone
OR LOWER(medication_text) LIKE '%methylprednisolone%'
OR LOWER(medication_text) LIKE '%medrol%'
OR LOWER(medication_text) LIKE '%solu-medrol%'
OR LOWER(medication_text) LIKE '%solumedrol%'

-- Others
OR LOWER(medication_text) LIKE '%hydrocortisone%'
OR LOWER(medication_text) LIKE '%betamethasone%'
OR LOWER(medication_text) LIKE '%cortisone%'
```

### Tier 3: Route Filtering (Exclude Non-Systemic)

**Exclude** (these don't affect brain imaging):
- Topical creams/ointments
- Inhaled steroids (asthma)
- Ophthalmic drops
- Intranasal sprays
- Intra-articular injections

**Include** (systemic exposure):
- Oral (PO)
- Intravenous (IV)
- Intramuscular (IM)
- Subcutaneous (SC)

---

## Temporal Matching Logic

### Strategy 1: Exact Date Match (Strictest)

```sql
imaging_date BETWEEN medication_start_date AND medication_stop_date
```

**Pros**: Most conservative
**Cons**: May miss medications due to:
- Documentation delays
- Missing stop dates
- Imprecise dating

### Strategy 2: Temporal Window (RECOMMENDED)

```sql
-- Medication active within ±7 days of imaging
imaging_date BETWEEN (medication_start_date - INTERVAL '7' DAY)
                 AND (medication_stop_date + INTERVAL '7' DAY)
```

**Rationale**:
- Accounts for documentation lag
- Captures recent steroid use (effects persist)
- Dexamethasone has half-life of ~36-54 hours, but clinical effects on edema last longer
- **7-day window** balances sensitivity and specificity

### Strategy 3: Active Prescription

```sql
-- Any active prescription overlapping imaging timeframe
medication_start_date <= imaging_date
AND (medication_stop_date >= imaging_date OR medication_stop_date IS NULL)
```

**Use case**: Most inclusive, captures ongoing prescriptions

---

## Dosage Considerations

### Clinical Relevance

**RANO criteria** specify:
- Stable or decreasing steroid dose → can assess response
- Increasing steroid dose → confounds response assessment

### Dosage Extraction Challenges

From medication_request:
- `dosage_instruction_dose_and_rate_dose_quantity_value` (numeric dose)
- `dosage_instruction_dose_and_rate_dose_quantity_unit` (unit: mg, mg/kg)
- `dosage_instruction_text` (free text, e.g., "4 mg PO BID")

**Problem**: Complex dosing regimens (tapers, PRN dosing)

### Simplified Approach

1. **Capture dosage if available** (numeric + unit)
2. **Flag as "taper"** if text contains "taper", "wean", "decrease"
3. **Extract frequency** if possible (QD, BID, TID, QID)
4. **Note**: Full dose standardization is complex, may defer to clinical review

---

## Proposed View Schema

### v_imaging_corticosteroid_use

**Grain**: One row per imaging study per corticosteroid

**Columns**:

```sql
-- Imaging identifiers
patient_fhir_id VARCHAR
imaging_study_fhir_id VARCHAR
imaging_date DATE
imaging_datetime TIMESTAMP
imaging_modality VARCHAR
imaging_body_site VARCHAR

-- Corticosteroid details
on_corticosteroid BOOLEAN  -- Any corticosteroid at time of imaging
corticosteroid_medication_fhir_id VARCHAR
corticosteroid_name VARCHAR
corticosteroid_rxnorm_cui VARCHAR
corticosteroid_generic_name VARCHAR  -- Standardized (dexamethasone, prednisone, etc.)

-- Temporal relationship
medication_start_datetime TIMESTAMP
medication_stop_datetime TIMESTAMP
days_from_med_start_to_imaging INTEGER
days_from_imaging_to_med_stop INTEGER
temporal_relationship VARCHAR  -- 'exact_match', 'within_7day_window', 'active_prescription'

-- Dosage (if available)
dose_value VARCHAR
dose_unit VARCHAR
dose_frequency VARCHAR
dose_route VARCHAR
dosage_text VARCHAR  -- Free text
is_taper BOOLEAN  -- Flagged if dosage text indicates taper

-- Detection method
detection_method VARCHAR  -- 'rxnorm_cui', 'text_match', 'both'

-- Aggregated info (per imaging study)
total_corticosteroids_count INTEGER  -- How many different corticosteroids at this imaging
corticosteroid_list VARCHAR  -- '; ' delimited list of all corticosteroids
```

---

## Clinical Use Cases

### Use Case 1: RANO Response Assessment

**Question**: Was patient on stable steroid dose at time of imaging?

**Query**:
```sql
SELECT
    patient_fhir_id,
    imaging_date,
    on_corticosteroid,
    corticosteroid_list,
    is_taper
FROM v_imaging_corticosteroid_use
WHERE imaging_modality = 'MRI'
  AND imaging_body_site LIKE '%brain%'
ORDER BY patient_fhir_id, imaging_date;
```

### Use Case 2: Dexamethasone Exposure Analysis

**Question**: What % of brain MRIs were obtained while on dexamethasone?

**Query**:
```sql
SELECT
    COUNT(DISTINCT imaging_study_fhir_id) as total_brain_mris,
    COUNT(DISTINCT CASE WHEN corticosteroid_generic_name = 'dexamethasone'
                        THEN imaging_study_fhir_id END) as on_dexamethasone,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN corticosteroid_generic_name = 'dexamethasone'
                                      THEN imaging_study_fhir_id END) /
          COUNT(DISTINCT imaging_study_fhir_id), 1) as percent_on_dex
FROM v_imaging_corticosteroid_use
WHERE imaging_modality = 'MRI'
  AND imaging_body_site LIKE '%brain%';
```

### Use Case 3: Polypharmacy Analysis

**Question**: How often are patients on multiple corticosteroids?

**Query**:
```sql
SELECT
    total_corticosteroids_count,
    COUNT(DISTINCT imaging_study_fhir_id) as imaging_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM v_imaging_corticosteroid_use
WHERE on_corticosteroid = true
GROUP BY total_corticosteroids_count
ORDER BY total_corticosteroids_count;
```

---

## Implementation Approach

### Option A: Separate View (RECOMMENDED)

**Pros**:
- Focused, single-purpose
- Easy to maintain and update corticosteroid list
- Can be reused for other temporal analyses (e.g., imaging + chemotherapy)

**Implementation**: Create `v_imaging_corticosteroid_use` as new view

### Option B: Enhance Existing Imaging View

**Pros**:
- All imaging data in one place

**Cons**:
- Imaging view becomes very large
- Mixing concerns (imaging metadata vs medication exposure)
- Harder to extend to other medication classes

**Recommendation**: Option A (separate view) with ability to JOIN to `v_imaging`

---

## Additional Considerations

### 1. Missing Data Handling

**Challenge**: Medication stop dates often missing

**Solutions**:
- Use `dispense_request_validity_period_end` as fallback
- Assume 30-day supply if no end date
- Use `dosage_timing_repeat_bounds_period_end` from sub-schema

### 2. Multiple Temporal Windows

**Recommendation**: Create multiple temporal relationship flags

```sql
within_exact_date BOOLEAN  -- medication active on exact imaging date
within_7day_window BOOLEAN  -- ±7 days
within_14day_window BOOLEAN  -- ±14 days
within_30day_window BOOLEAN  -- ±30 days
```

This allows analysts to choose sensitivity level.

### 3. Dose Changes Around Imaging

**Advanced feature**: Detect dose increases/decreases within 2 weeks of imaging

```sql
-- Compare dose to previous prescription
-- Flag if increasing vs stable vs decreasing
```

### 4. Integration with RANO Criteria

**Future enhancement**: Incorporate steroid data into automated RANO assessment

---

## Data Quality Considerations

### Expected Challenges

1. **Missing stop dates** → Use dispense period or assume duration
2. **Text-only prescriptions** → RxNorm codes may be NULL
3. **PRN dosing** → Hard to know if actually taken
4. **Topical vs systemic** → May need route filtering
5. **Dose units inconsistent** → May need normalization

### Validation Queries

```sql
-- 1. How many medications have RxNorm codes vs text only?
SELECT
    CASE WHEN rxnorm_cui IS NOT NULL THEN 'Has RxNorm' ELSE 'Text only' END as code_availability,
    COUNT(*) as medication_count
FROM corticosteroid_medications
GROUP BY code_availability;

-- 2. Distribution of temporal windows
SELECT
    temporal_relationship,
    COUNT(DISTINCT imaging_study_fhir_id) as imaging_count
FROM v_imaging_corticosteroid_use
GROUP BY temporal_relationship;

-- 3. Dose unit standardization needs
SELECT
    dose_unit,
    COUNT(*) as occurrences
FROM v_imaging_corticosteroid_use
WHERE dose_unit IS NOT NULL
GROUP BY dose_unit
ORDER BY occurrences DESC;
```

---

## Recommended Implementation

### Phase 1: Core View ✅
- Create `v_imaging_corticosteroid_use`
- RxNorm + text-based identification
- 7-day temporal window (configurable)
- Capture dosage where available

### Phase 2: Enhanced Dosing
- Standardize dose units
- Detect tapers
- Track dose changes over time

### Phase 3: Clinical Integration
- RANO criteria automation
- Pseudoresponse flagging
- Clinical decision support

---

## Next Steps

1. **Review corticosteroid list** with clinical team (especially neuro-oncology)
2. **Define temporal window** preference (recommend 7 days)
3. **Create view** with verification queries
4. **Validate** against known cases
5. **Document** clinical interpretation guidance

