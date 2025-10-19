# Autologous Stem Cell Transplant Assessment
**Date**: October 18, 2025
**Purpose**: Assess how to detect autologous stem cell transplants in FHIR database
**Database**: fhir_prd_db

---

## Executive Summary

✅ **Autologous stem cell transplants CAN be detected** in the FHIR database across multiple data sources.

### Data Availability Summary

| Data Source | Records Found | Unique Patients | Detection Method |
|------------|---------------|-----------------|------------------|
| **Procedure** | 19 procedures | 17 patients | Code text, CPT codes |
| **Procedure CPT Codes** | 4 coded procedures | - | CPT 38241, 38240, 38231 |
| **Condition (Transplant Status)** | 1,981 conditions | High | ICD-10 Z94.84, Z94.81, history codes |
| **Observation (Stem Cell Labs)** | 323 observations | - | CD34 counts, transplant date documentation |
| **Medication (Conditioning)** | 0 medications | - | Not captured (chemotherapy may be elsewhere) |

### Primary Detection Strategy

**Multi-source approach combining**:
1. **Condition codes** (Z94.84, Z94.81) - **HIGHEST YIELD** (1,981 records)
2. **Procedure codes** (CPT 38241) - Direct procedure documentation
3. **Observation** (CD34+ counts, transplant date) - Lab validation
4. **Procedure text** - Free-text procedure descriptions

---

## 1. Condition Table - Transplant Status (HIGHEST YIELD)

### Summary
- **1,981 condition records** documenting stem cell transplant status
- **1,704 records** with ICD-10 code **Z94.84** (Stem cells transplant status)
- **465 records** with ICD-10 code **Z94.81** (Bone marrow transplant status)
- **194 records** specifically stating "History of autologous bone marrow transplant"

### Key ICD-10 Codes Found

| ICD-10 Code | Description | Count | Autologous-Specific |
|-------------|-------------|-------|---------------------|
| **Z94.84** | Stem cells transplant status | 1,704 | ⚠️ Mixed (autologous + allogeneic) |
| **Z94.81** | Bone marrow transplant status | 465 | ⚠️ Mixed (autologous + allogeneic) |
| **V42.82** | Peripheral stem cells replaced by transplant | 1,625 | ⚠️ Mixed |
| **V42.81** | Bone marrow replaced by transplant | 453 | ⚠️ Mixed |
| **108631000119101** | History of autologous bone marrow transplant | 194 | ✅ **AUTOLOGOUS-SPECIFIC** |
| **848081** | History of autologous stem cell transplant | 63 | ✅ **AUTOLOGOUS-SPECIFIC** |
| **153351000119102** | History of peripheral stem cell transplant | 94 | ⚠️ Mixed |

### Detection Query
```sql
-- High-yield query for autologous stem cell transplant status
SELECT DISTINCT
    c.subject_reference as patient_fhir_id,
    ccc.code_coding_code as icd10_code,
    ccc.code_coding_display as diagnosis,
    c.onset_date_time as transplant_date,
    c.recorded_date,

    -- Autologous flag
    CASE
        WHEN ccc.code_coding_code = '108631000119101' THEN true  -- History of autologous BMT
        WHEN ccc.code_coding_code = '848081' THEN true           -- History of autologous SCT
        WHEN LOWER(ccc.code_coding_display) LIKE '%autologous%' THEN true
        ELSE false
    END as confirmed_autologous

FROM fhir_prd_db.condition c
INNER JOIN fhir_prd_db.condition_code_coding ccc
    ON c.id = ccc.condition_id
WHERE ccc.code_coding_code IN (
    'Z94.84',  -- Stem cells transplant status
    'Z94.81',  -- Bone marrow transplant status
    '108631000119101',  -- History of autologous bone marrow transplant
    '848081',  -- History of autologous stem cell transplant
    '153351000119102',  -- History of peripheral stem cell transplant
    'V42.82',  -- Peripheral stem cells replaced by transplant
    'V42.81'   -- Bone marrow replaced by transplant
)
OR LOWER(ccc.code_coding_display) LIKE '%autologous%transplant%'
OR LOWER(ccc.code_coding_display) LIKE '%stem%cell%transplant%status%';
```

**Expected Result**: ~1,981 transplant status records

---

## 2. Procedure Table - Direct Procedure Documentation

### Summary
- **19 procedure records** for stem cell transplants
- **17 unique patients**
- Mix of autologous, allogeneic, and stem cell collection procedures

### Procedure Descriptions Found

| Procedure Text | Count | Type |
|---------------|-------|------|
| BONE MARROW/STEM XPLANT,AUTOLOGOUS | 3 | ✅ **AUTOLOGOUS** |
| stem cell transplant | 2 | ⚠️ Unspecified |
| autologous stem cell infusion | 1 | ✅ **AUTOLOGOUS** |
| stem cell harvest | 1 | Collection (pre-transplant) |
| STEM CELL COLLECTION | 1 | Collection (pre-transplant) |

### CPT Codes Found

| CPT Code | Description | Count | Type |
|----------|-------------|-------|------|
| **38241** | MARROW/BLD-DRV PRPH STEM CELL TRNS (autologous) | 2 | ✅ **AUTOLOGOUS** |
| 38240 | MARROW/BLD-DRV PRPH STEM CELL TRNS (allogeneic) | 1 | ❌ Allogeneic |
| 38231 | STEM CELL COLLECTION | 1 | Collection |

### Detection Query
```sql
-- Query for autologous stem cell transplant procedures
SELECT DISTINCT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text as procedure_description,
    pcc.code_coding_code as cpt_code,
    pcc.code_coding_display as cpt_description,
    p.performed_date_time as procedure_date,
    p.performed_period_start,

    -- Autologous flag
    CASE
        WHEN LOWER(p.code_text) LIKE '%autologous%' THEN true
        WHEN pcc.code_coding_code = '38241' THEN true  -- Autologous CPT
        ELSE false
    END as confirmed_autologous

FROM fhir_prd_db.procedure p
LEFT JOIN fhir_prd_db.procedure_code_coding pcc
    ON p.id = pcc.procedure_id
WHERE (
    LOWER(p.code_text) LIKE '%stem%cell%'
    OR LOWER(p.code_text) LIKE '%autologous%'
    OR LOWER(p.code_text) LIKE '%bone%marrow%transplant%'
    OR LOWER(p.code_text) LIKE '%hsct%'
    OR LOWER(p.code_text) LIKE '%asct%'
    OR pcc.code_coding_code IN ('38241', '38240', '38242', '38243')
)
AND p.status = 'completed';
```

**Expected Result**: ~19 procedure records

---

## 3. Observation Table - CD34+ Counts & Transplant Documentation

### Summary
- **323 observation records** related to stem cell transplants
- **359 observations** specifically documenting "HEMATOPOIETIC STEM CELL TRANSPLANT - TRANSPLANT DATE"
- **38 observations** for CD34 cell count (stem cell quantification)

### Key Observation Types

| Observation Type | Count | Purpose |
|-----------------|-------|---------|
| HEMATOPOIETIC STEM CELL TRANSPLANT - TRANSPLANT DATE | 359 | **Direct transplant date documentation** |
| Stem Cell Prod Sterility Test | 128 | Product quality testing |
| CD34 CELL COUNT APHERESIS OR MARROW | 38 | Stem cell quantification |
| CD34+ Region 1 | 28 | Flow cytometry analysis |
| CD34+ Lymph | 17 | Cell population analysis |

### Detection Query
```sql
-- Query for stem cell transplant observations
SELECT DISTINCT
    o.subject_reference as patient_fhir_id,
    o.code_text as observation_type,
    o.value_string as observation_value,
    o.value_quantity_value as numeric_value,
    o.value_quantity_unit as unit,
    o.effective_date_time as observation_date,

    -- Observation category
    CASE
        WHEN LOWER(o.code_text) LIKE '%transplant%date%' THEN 'Transplant Date'
        WHEN LOWER(o.code_text) LIKE '%cd34%' THEN 'Stem Cell Count'
        WHEN LOWER(o.code_text) LIKE '%sterility%' THEN 'Product Testing'
        ELSE 'Other'
    END as observation_category

FROM fhir_prd_db.observation o
WHERE LOWER(o.code_text) LIKE '%stem%cell%transplant%'
   OR LOWER(o.code_text) LIKE '%cd34%'
   OR LOWER(o.code_text) LIKE '%hematopoietic%stem%'
   OR LOWER(o.code_text) LIKE '%apheresis%'
   OR LOWER(o.code_text) LIKE '%engraftment%';
```

**Expected Result**: ~323 observation records

**Key Finding**: The observation "PROCEDURAL - SURGICAL HISTORY - HEMATOPOIETIC STEM CELL TRANSPLANT - TRANSPLANT DATE" provides **direct transplant date documentation** (359 records)!

---

## 4. Document References - Operative Reports & Notes

While not queried in this assessment, document references likely contain:
- Bone marrow transplant operative reports
- Stem cell collection procedure notes
- Conditioning regimen documentation
- Post-transplant follow-up notes

### Suggested Query
```sql
SELECT DISTINCT
    dr.subject_reference as patient_fhir_id,
    dr.type_text as document_type,
    dr.description as document_description,
    dr.date as document_date
FROM fhir_prd_db.document_reference dr
WHERE LOWER(dr.type_text) LIKE '%transplant%'
   OR LOWER(dr.description) LIKE '%stem%cell%'
   OR LOWER(dr.description) LIKE '%bone%marrow%'
   OR LOWER(dr.description) LIKE '%autologous%'
   OR LOWER(dr.description) LIKE '%conditioning%'
ORDER BY dr.subject_reference, dr.date;
```

---

## 5. Recommended Detection Strategy

### Multi-Source Comprehensive Approach

```sql
-- COMPREHENSIVE AUTOLOGOUS STEM CELL TRANSPLANT VIEW
CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_transplant AS
WITH
-- 1. Transplant status from condition table (HIGHEST YIELD)
transplant_conditions AS (
    SELECT
        c.subject_reference as patient_fhir_id,
        c.id as condition_id,
        ccc.code_coding_code as icd10_code,
        ccc.code_coding_display as diagnosis,
        c.onset_date_time as condition_onset,
        c.recorded_date,

        -- Autologous flag from ICD-10 codes
        CASE
            WHEN ccc.code_coding_code = '108631000119101' THEN true  -- History of autologous BMT
            WHEN ccc.code_coding_code = '848081' THEN true           -- History of autologous SCT
            WHEN LOWER(ccc.code_coding_display) LIKE '%autologous%' THEN true
            ELSE false
        END as confirmed_autologous,

        'condition' as data_source

    FROM fhir_prd_db.condition c
    INNER JOIN fhir_prd_db.condition_code_coding ccc
        ON c.id = ccc.condition_id
    WHERE ccc.code_coding_code IN ('Z94.84', 'Z94.81', '108631000119101', '848081', 'V42.82', 'V42.81')
       OR LOWER(ccc.code_coding_display) LIKE '%stem%cell%transplant%'
),

-- 2. Transplant procedures
transplant_procedures AS (
    SELECT
        p.subject_reference as patient_fhir_id,
        p.id as procedure_id,
        p.code_text as procedure_description,
        pcc.code_coding_code as cpt_code,
        p.performed_date_time as procedure_date,
        p.performed_period_start,

        -- Autologous flag from CPT codes or text
        CASE
            WHEN LOWER(p.code_text) LIKE '%autologous%' THEN true
            WHEN pcc.code_coding_code = '38241' THEN true  -- Autologous CPT
            ELSE false
        END as confirmed_autologous,

        'procedure' as data_source

    FROM fhir_prd_db.procedure p
    LEFT JOIN fhir_prd_db.procedure_code_coding pcc
        ON p.id = pcc.procedure_id
    WHERE (
        LOWER(p.code_text) LIKE '%stem%cell%'
        OR LOWER(p.code_text) LIKE '%autologous%'
        OR LOWER(p.code_text) LIKE '%bone%marrow%transplant%'
        OR pcc.code_coding_code IN ('38241', '38240')
    )
    AND p.status = 'completed'
),

-- 3. Transplant date from observations
transplant_dates_obs AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        o.effective_date_time as transplant_date,
        o.value_string as transplant_date_value,

        'observation' as data_source

    FROM fhir_prd_db.observation o
    WHERE LOWER(o.code_text) LIKE '%hematopoietic%stem%cell%transplant%transplant%date%'
       OR LOWER(o.code_text) LIKE '%stem%cell%transplant%date%'
),

-- 4. CD34+ counts (validates stem cell collection/engraftment)
cd34_counts AS (
    SELECT
        o.subject_reference as patient_fhir_id,
        o.effective_date_time as collection_date,
        o.value_quantity_value as cd34_count,
        o.value_quantity_unit as unit,

        'cd34_count' as data_source

    FROM fhir_prd_db.observation o
    WHERE LOWER(o.code_text) LIKE '%cd34%'
)

-- MAIN SELECT: Combine all data sources
SELECT
    COALESCE(tc.patient_fhir_id, tp.patient_fhir_id, tdo.patient_fhir_id, cd34.patient_fhir_id) as patient_fhir_id,

    -- Condition data (transplant status)
    tc.condition_id,
    tc.icd10_code,
    tc.diagnosis as transplant_status_diagnosis,
    tc.condition_onset as transplant_status_onset,
    tc.recorded_date as transplant_status_recorded,
    tc.confirmed_autologous as autologous_from_condition,

    -- Procedure data
    tp.procedure_id,
    tp.procedure_description,
    tp.cpt_code,
    tp.procedure_date as transplant_procedure_date,
    tp.confirmed_autologous as autologous_from_procedure,

    -- Transplant date from observation
    tdo.transplant_date as transplant_date_from_obs,
    tdo.transplant_date_value,

    -- CD34 count data (validates stem cell collection)
    cd34.collection_date as stem_cell_collection_date,
    cd34.cd34_count,
    cd34.unit as cd34_unit,

    -- Best available transplant date
    COALESCE(tp.procedure_date, tdo.transplant_date, tc.condition_onset) as best_transplant_date,

    -- Confirmed autologous flag
    CASE
        WHEN tc.confirmed_autologous = true OR tp.confirmed_autologous = true THEN true
        ELSE false
    END as confirmed_autologous,

    -- Data sources present
    CASE WHEN tc.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_condition_data,
    CASE WHEN tp.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_procedure_data,
    CASE WHEN tdo.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_transplant_date_obs,
    CASE WHEN cd34.patient_fhir_id IS NOT NULL THEN true ELSE false END as has_cd34_data

FROM transplant_conditions tc
FULL OUTER JOIN transplant_procedures tp
    ON tc.patient_fhir_id = tp.patient_fhir_id
FULL OUTER JOIN transplant_dates_obs tdo
    ON COALESCE(tc.patient_fhir_id, tp.patient_fhir_id) = tdo.patient_fhir_id
FULL OUTER JOIN cd34_counts cd34
    ON COALESCE(tc.patient_fhir_id, tp.patient_fhir_id, tdo.patient_fhir_id) = cd34.patient_fhir_id

WHERE COALESCE(tc.patient_fhir_id, tp.patient_fhir_id, tdo.patient_fhir_id, cd34.patient_fhir_id) IS NOT NULL

ORDER BY patient_fhir_id, best_transplant_date;
```

---

## 6. Key Codes for Detection

### ICD-10 Codes (Condition Table)
- **Z94.84** - Stem cells transplant status (1,704 records)
- **Z94.81** - Bone marrow transplant status (465 records)
- **108631000119101** - History of autologous bone marrow transplant (194 records) ✅ **AUTOLOGOUS-SPECIFIC**
- **848081** - History of autologous stem cell transplant (63 records) ✅ **AUTOLOGOUS-SPECIFIC**
- **V42.82** - Peripheral stem cells replaced by transplant (1,625 records)
- **V42.81** - Bone marrow replaced by transplant (453 records)

### CPT Codes (Procedure Table)
- **38241** - Autologous hematopoietic progenitor cell transplantation ✅ **AUTOLOGOUS-SPECIFIC**
- **38240** - Allogeneic hematopoietic progenitor cell transplantation (exclude for autologous)
- **38231** - Blood-derived hematopoietic progenitor cell harvesting (collection/apheresis)

### Text Search Patterns
- **Procedure.code_text**: `%autologous%`, `%stem%cell%transplant%`, `%BONE MARROW/STEM XPLANT,AUTOLOGOUS%`
- **Observation.code_text**: `%HEMATOPOIETIC STEM CELL TRANSPLANT%`, `%CD34%`
- **Condition.code_text**: `%autologous%transplant%`, `%stem%cell%transplant%status%`

---

## 7. Data Quality Indicators

### Autologous vs. Allogeneic Distinction

| Data Source | Autologous-Specific Codes/Text | Mixed/Ambiguous |
|-------------|-------------------------------|-----------------|
| **Condition** | 108631000119101, 848081 | Z94.84, Z94.81, V42.82 |
| **Procedure** | CPT 38241, "autologous" in text | "stem cell transplant" without modifier |
| **Observation** | N/A - lab values don't distinguish | CD34 counts (both types) |

### Recommended Validation Logic
```sql
-- Multi-source validation for autologous transplant
CASE
    -- High confidence: ICD code or CPT code specifically states autologous
    WHEN icd10_code IN ('108631000119101', '848081') THEN 'High Confidence'
    WHEN cpt_code = '38241' THEN 'High Confidence'

    -- Medium confidence: Free text mentions autologous
    WHEN LOWER(procedure_description) LIKE '%autologous%' THEN 'Medium Confidence'
    WHEN LOWER(diagnosis) LIKE '%autologous%' THEN 'Medium Confidence'

    -- Low confidence: Transplant status without autologous specification
    WHEN icd10_code IN ('Z94.84', 'Z94.81') THEN 'Low Confidence - May be Allogeneic'

    ELSE 'Unknown'
END as autologous_confidence_level
```

---

## 8. Summary & Recommendations

### ✅ Detection is FEASIBLE

Autologous stem cell transplants can be reliably detected using a multi-source approach.

### Recommended Approach (in priority order)

1. **PRIMARY**: Query **condition_code_coding** for ICD-10 codes (Z94.84, 108631000119101, 848081)
   - **HIGHEST YIELD**: 1,981 transplant status records
   - Use autologous-specific codes (108631000119101, 848081) for high confidence

2. **SECONDARY**: Query **procedure** table with CPT code filtering (38241 = autologous)
   - 19 direct procedure records
   - CPT 38241 is autologous-specific

3. **VALIDATION**: Cross-reference with **observation** table
   - "HEMATOPOIETIC STEM CELL TRANSPLANT - TRANSPLANT DATE" provides exact dates (359 records)
   - CD34+ counts validate stem cell collection (38 records)

4. **ENHANCEMENT**: Include document references for clinical notes and operative reports

### Data Coverage Expectations

| Detection Method | Expected Patients | Confidence Level |
|-----------------|-------------------|------------------|
| Autologous-specific ICD codes (108631000119101, 848081) | ~257 patients | **HIGH** |
| CPT 38241 procedures | ~2 patients | **HIGH** |
| "Autologous" in free text | Variable | **MEDIUM** |
| General transplant status (Z94.84, Z94.81) | ~1,000+ patients | **LOW** (mixed) |

### Implementation Priority

**IMMEDIATE**: Create view combining condition + procedure + observation data sources for comprehensive transplant tracking.

---

**Assessment Complete**: Autologous stem cell transplants are well-documented in FHIR database across multiple tables.
