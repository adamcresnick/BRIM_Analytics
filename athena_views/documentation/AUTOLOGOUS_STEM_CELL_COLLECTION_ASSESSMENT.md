# Autologous Stem Cell Collection Assessment

**Date**: October 18, 2025
**Purpose**: Identify and capture autologous stem cell collection events and associated variables
**Related**: This is separate from transplant events (covered in AUTOLOGOUS_STEM_CELL_TRANSPLANT_ASSESSMENT.md)

---

## Executive Summary

Stem cell **collection** (also called "harvest" or "apheresis") occurs BEFORE transplantation. The patient's stem cells are collected, processed, and stored. Later, after high-dose chemotherapy, these cells are re-infused (transplanted).

**Key Data Sources**:
1. **Procedure Table**: Collection procedures (CPT 38231, text mentions)
2. **Observation Table**: CD34 counts (stem cell quantification), collection dates
3. **Specimen Table**: Collected stem cell products (if available)
4. **Medication_request**: Mobilization agents (G-CSF/filgrastim)

---

## 1. Collection Procedure Events

### CPT Code for Collection
- **CPT 38231**: Bone marrow harvest for transplantation; autologous

### Detection Strategy
```sql
-- Identify stem cell collection procedures
SELECT DISTINCT
    p.subject_reference as patient_fhir_id,
    p.id as procedure_id,
    p.code_text as procedure_description,
    pcc.code_coding_code as cpt_code,
    pcc.code_coding_display as cpt_description,
    p.performed_date_time as collection_date,
    p.performed_period_start,
    p.performed_period_end,

    -- Collection method
    CASE
        WHEN LOWER(p.code_text) LIKE '%apheresis%' THEN 'apheresis'
        WHEN LOWER(p.code_text) LIKE '%bone%marrow%harvest%' THEN 'bone_marrow_harvest'
        WHEN LOWER(p.code_text) LIKE '%peripheral%' THEN 'peripheral_blood'
        ELSE 'unspecified'
    END as collection_method

FROM fhir_prd_db.procedure p
LEFT JOIN fhir_prd_db.procedure_code_coding pcc
    ON p.id = pcc.procedure_id
WHERE (
    -- CPT code for autologous collection
    pcc.code_coding_code = '38231'

    -- Text-based detection
    OR LOWER(p.code_text) LIKE '%stem%cell%collection%'
    OR LOWER(p.code_text) LIKE '%stem%cell%harvest%'
    OR LOWER(p.code_text) LIKE '%apheresis%'
    OR LOWER(p.code_text) LIKE '%bone%marrow%harvest%'
    OR (LOWER(p.code_text) LIKE '%stem%cell%' AND LOWER(p.code_text) LIKE '%autologous%')
)
AND p.status = 'completed';
```

### Expected Procedure Variables
- Collection date/time
- Collection method (apheresis vs bone marrow harvest)
- Number of collection sessions
- Procedure performer
- Encounter linkage (inpatient vs outpatient)

---

## 2. CD34+ Cell Count (Stem Cell Quantification)

### Importance
CD34+ cell count is the **gold standard** for measuring stem cell yield. Adequate CD34+ cell dose is critical for successful engraftment:
- **Minimum**: 2 × 10⁶ CD34+ cells/kg
- **Optimal**: ≥5 × 10⁶ CD34+ cells/kg

### Observation Types
```sql
-- Query CD34 counts from collected products
SELECT DISTINCT
    o.subject_reference as patient_fhir_id,
    o.code_text as observation_type,
    o.value_quantity_value as cd34_count,
    o.value_quantity_unit as unit,
    o.effective_date_time as measurement_date,

    -- Categorize CD34 observation type
    CASE
        WHEN LOWER(o.code_text) LIKE '%cd34%apheresis%' THEN 'apheresis_product'
        WHEN LOWER(o.code_text) LIKE '%cd34%marrow%' THEN 'marrow_product'
        WHEN LOWER(o.code_text) LIKE '%cd34%peripheral%' THEN 'peripheral_blood'
        ELSE 'unspecified'
    END as cd34_source

FROM fhir_prd_db.observation o
WHERE LOWER(o.code_text) LIKE '%cd34%'
  AND (
    LOWER(o.code_text) LIKE '%apheresis%'
    OR LOWER(o.code_text) LIKE '%marrow%'
    OR LOWER(o.code_text) LIKE '%collection%'
    OR LOWER(o.code_text) LIKE '%harvest%'
  );
```

### Expected Variables
- Total CD34+ cell count (× 10⁶)
- CD34+ cells per kg body weight
- Viability percentage
- Total nucleated cell count (TNC)
- Collection date/time

---

## 3. Mobilization Agents (G-CSF/Filgrastim)

Before apheresis collection, patients receive **mobilization** drugs to increase stem cells in peripheral blood.

### Common Mobilization Agents
- **Filgrastim (Neupogen)** - RxNorm: 105585
- **Pegfilgrastim (Neulasta)** - RxNorm: 358810
- **Plerixafor (Mozobil)** - RxNorm: 847232 (for poor mobilizers)

### Detection Strategy
```sql
-- Find mobilization agents given before collection
SELECT DISTINCT
    mr.subject_reference as patient_fhir_id,
    mr.id as medication_request_id,
    mcc.code_coding_code as rxnorm_code,
    mcc.code_coding_display as medication_name,
    mr.authored_on as medication_start,
    mr.dispense_request_validity_period_end as medication_stop,

    -- Mobilization agent type
    CASE
        WHEN mcc.code_coding_code IN ('105585', '1658634') THEN 'filgrastim'
        WHEN mcc.code_coding_code = '358810' THEN 'pegfilgrastim'
        WHEN mcc.code_coding_code = '847232' THEN 'plerixafor'
        ELSE 'other_growth_factor'
    END as mobilization_agent_type

FROM fhir_prd_db.medication_request mr
LEFT JOIN fhir_prd_db.medication m
    ON m.id = SUBSTRING(mr.medication_reference_reference, 12)
LEFT JOIN fhir_prd_db.medication_code_coding mcc
    ON mcc.medication_id = m.id
    AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
WHERE (
    -- G-CSF agents
    mcc.code_coding_code IN (
        '105585',   -- Filgrastim
        '358810',   -- Pegfilgrastim
        '847232',   -- Plerixafor
        '1658634'   -- Filgrastim-sndz
    )
    OR LOWER(m.code_text) LIKE '%filgrastim%'
    OR LOWER(m.code_text) LIKE '%neupogen%'
    OR LOWER(m.code_text) LIKE '%neulasta%'
    OR LOWER(m.code_text) LIKE '%mozobil%'
)
AND mr.status IN ('active', 'completed');
```

### Expected Variables
- Mobilization agent name and RxNorm
- Start/stop dates
- Dosing regimen
- Days of mobilization before collection

---

## 4. Specimen/Product Information

### Specimen Table (if available)
```sql
-- Check for collected stem cell specimens
SELECT DISTINCT
    s.subject_reference as patient_fhir_id,
    s.id as specimen_id,
    s.type_text as specimen_type,
    s.collection_collected_date_time as collection_date,
    s.collection_method_text as collection_method,
    s.collection_body_site_text as collection_site,
    s.processing_description as processing_notes

FROM fhir_prd_db.specimen s
WHERE LOWER(s.type_text) LIKE '%stem%cell%'
   OR LOWER(s.type_text) LIKE '%bone%marrow%'
   OR LOWER(s.type_text) LIKE '%apheresis%'
   OR LOWER(s.collection_method_text) LIKE '%apheresis%';
```

### Expected Variables
- Specimen ID
- Collection date/time
- Volume collected
- Processing method
- Storage location/ID

---

## 5. Quality Control Observations

### Sterility Testing
```sql
-- Stem cell product quality testing
SELECT DISTINCT
    o.subject_reference as patient_fhir_id,
    o.code_text as test_type,
    o.value_string as test_result,
    o.effective_date_time as test_date

FROM fhir_prd_db.observation o
WHERE LOWER(o.code_text) LIKE '%stem%cell%'
  AND (
    LOWER(o.code_text) LIKE '%sterility%'
    OR LOWER(o.code_text) LIKE '%viability%'
    OR LOWER(o.code_text) LIKE '%contamination%'
    OR LOWER(o.code_text) LIKE '%quality%'
  );
```

### Expected Variables
- Sterility test results
- Viability testing
- Gram stain results
- Product release criteria

---

## 6. Proposed View Schema: v_autologous_stem_cell_collection

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_collection AS
SELECT
    -- Patient identifier
    patient_fhir_id,

    -- ============================================================================
    -- COLLECTION PROCEDURE
    -- ============================================================================
    collection_procedure_id,
    collection_procedure_description,
    collection_cpt_code,
    collection_date,
    collection_method,  -- 'apheresis', 'bone_marrow_harvest', 'peripheral_blood'
    collection_performer,
    collection_encounter_id,

    -- ============================================================================
    -- CD34 COUNTS (Stem Cell Quantification)
    -- ============================================================================
    cd34_count_value,
    cd34_count_unit,
    cd34_count_per_kg,  -- If patient weight available
    cd34_measurement_date,
    cd34_adequacy,  -- 'adequate', 'marginal', 'inadequate'

    total_nucleated_cells,
    viability_percentage,

    -- ============================================================================
    -- MOBILIZATION AGENTS
    -- ============================================================================
    mobilization_agent_name,
    mobilization_agent_rxnorm,
    mobilization_start_date,
    mobilization_stop_date,
    mobilization_duration_days,
    mobilization_agent_type,  -- 'filgrastim', 'pegfilgrastim', 'plerixafor'

    -- ============================================================================
    -- SPECIMEN/PRODUCT INFORMATION
    -- ============================================================================
    specimen_id,
    specimen_type,
    collection_volume,
    processing_method,
    storage_id,

    -- ============================================================================
    -- QUALITY CONTROL
    -- ============================================================================
    sterility_test_result,
    sterility_test_date,
    product_release_status,

    -- ============================================================================
    -- DATA QUALITY INDICATORS
    -- ============================================================================
    has_collection_procedure,
    has_cd34_count,
    has_mobilization_agent,
    has_specimen_data,
    data_completeness_score  -- 0-4 based on sources present

FROM ...
```

---

## 7. Key Variables to Capture

### Collection Event
- ✅ Collection procedure date/time
- ✅ Collection method (apheresis vs bone marrow)
- ✅ Number of collection sessions
- ✅ Collection site/location
- ✅ CPT code (38231)

### Stem Cell Yield
- ✅ CD34+ cell count (total)
- ✅ CD34+ cells/kg body weight
- ✅ Total nucleated cell count
- ✅ Viability percentage
- ✅ Adequacy assessment

### Mobilization
- ✅ Mobilization agent(s) used
- ✅ RxNorm codes
- ✅ Mobilization start/stop dates
- ✅ Duration of mobilization

### Product Quality
- ✅ Sterility test results
- ✅ Product release date
- ✅ Storage/freezing date
- ✅ Specimen ID

---

## 8. Relationship to Transplant

The collection view should **link to transplant** events:

```
Patient → Mobilization → Collection → Conditioning → Transplant
           (G-CSF)        (Apheresis)   (High-dose    (Reinfusion)
                                         chemo/RT)
```

### Temporal Sequence
1. **Mobilization**: Days -10 to -5 (relative to collection)
2. **Collection**: Day 0 (collection day)
3. **Conditioning**: Days +7 to +30 (high-dose chemo)
4. **Transplant**: Day +30 to +45 (stem cell reinfusion)

---

## 9. Next Steps

1. ✅ **Query procedure table** for collection events (CPT 38231)
2. ✅ **Query observation table** for CD34 counts
3. ⏳ **Query medication_request** for mobilization agents
4. ⏳ **Check specimen table** for product data (if available)
5. ⏳ **Create v_autologous_stem_cell_collection view**
6. ⏳ **Link collection to transplant** via patient + temporal proximity
7. ⏳ **Integrate into ATHENA_VIEW_CREATION_QUERIES.sql**

---

**Status**: Assessment complete, ready for view creation
