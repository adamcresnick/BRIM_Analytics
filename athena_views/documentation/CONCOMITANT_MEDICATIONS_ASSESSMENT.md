# Concomitant Medications View Assessment

**Date**: October 18, 2025
**Purpose**: Design comprehensive view to capture concomitant medications administered during chemotherapy treatment windows
**Data Dictionary Reference**: `concomitant_medications` tab in CBTN data dictionary

---

## 1. Requirements Analysis

### CBTN Data Dictionary Fields (Concomitant Medications)

| Field Name | Description | Priority |
|------------|-------------|----------|
| `conmed_timepoint` | Selection of associated timepoint (0=Diagnosis, 1=6mo, 2=12mo, etc.) | HIGH |
| `form_conmed_number` | Total number of medications at timepoint (1-10+) | HIGH |
| `age_at_conmed_date` | Age (in days) at date of conmed reconciliation | HIGH |
| `rxnorm_cui` | RxNORM Concept Unique Identifier | **CRITICAL** |
| `medication_name` | Medication name corresponding to rxnorm code | **CRITICAL** |
| `conmed_routine` | Medication Schedule (1=Scheduled, 2=PRN, 3=Unknown) | MEDIUM |

### Additional Requirements from User
1. **Define chemotherapy time windows**: Capture start/stop dates for each chemotherapy agent
2. **Identify concomitant medications**: Medications administered during chemotherapy windows
3. **Include RxNorm codes**: For both chemotherapy and concomitant medications
4. **Include medication FHIR IDs**: For traceability
5. **Clear time window mapping**: Show which chemo window each conmed falls within
6. **Start/stop dates**: For both chemotherapy and concomitant medications

---

## 2. FHIR Data Sources

### Primary Tables
1. **medication_request** - Main medication order table
   - Fields: `id`, `subject_reference`, `status`, `intent`, `medication_display`
   - Date fields: `authored_on`, `dosage_timing_repeat_bounds_period_start`, `dosage_timing_repeat_bounds_period_end`

2. **medication_request_code_coding** - RxNorm codes for medications
   - Fields: `medication_request_id`, `code_coding_code` (RxNorm CUI), `code_coding_display`

3. **medication_request_reason_code** - Indication for medication (may link to diagnosis)
   - Fields: `medication_request_id`, `reason_code_text`, `reason_code_coding_display`

4. **medication_request_dosage_instruction** - Dosing details
   - Fields: `medication_request_id`, `dosage_instruction_text`, `dosage_instruction_timing_code_text`

### Supporting Tables
5. **medication_administration** - Actual administration records (if available)
   - May have more precise timing than medication_request

6. **condition** / **condition_code_coding** - For linking medications to cancer diagnosis

---

## 3. Chemotherapy Agent Identification Strategy

### Common Pediatric Brain Tumor Chemotherapy Agents (RxNorm Examples)

**Alkylating Agents**:
- Temozolomide (RxNorm: 82264)
- Lomustine/CCNU (RxNorm: 6599)
- Carmustine/BCNU (RxNorm: 2095)
- Cyclophosphamide (RxNorm: 3002)
- Cisplatin (RxNorm: 2555)
- Carboplatin (RxNorm: 2130)

**Topoisomerase Inhibitors**:
- Etoposide (RxNorm: 4139)
- Irinotecan (RxNorm: 57841)

**Vinca Alkaloids**:
- Vincristine (RxNorm: 11152)
- Vinblastine (RxNorm: 11119)

**Antimetabolites**:
- Methotrexate (RxNorm: 6851)
- Cytarabine (RxNorm: 3034)

**Targeted Therapy**:
- Bevacizumab (RxNorm: 72824)

### Chemotherapy Identification Logic
```sql
-- Identify chemotherapy medications based on:
-- 1. Known chemotherapy RxNorm codes
-- 2. Medication category/class
-- 3. Reason codes linking to cancer treatment
-- 4. Free text mentions of "chemotherapy", "antineoplastic", "cytotoxic"
```

---

## 4. Concomitant Medication Categories

### Supportive Care Medications to Capture

**Anti-emetics** (prevent nausea):
- Ondansetron (RxNorm: 26225)
- Granisetron (RxNorm: 4896)
- Aprepitant (RxNorm: 288635)

**Corticosteroids** (reduce swelling, prevent allergic reactions):
- Dexamethasone (RxNorm: 3264)
- Prednisone (RxNorm: 8640)
- Methylprednisolone (RxNorm: 6902)

**Growth Factors** (stimulate blood cell production):
- Filgrastim/G-CSF (RxNorm: 105585)
- Pegfilgrastim (RxNorm: 358810)

**Anticonvulsants** (seizure prevention):
- Levetiracetam (RxNorm: 35766)
- Valproic acid (RxNorm: 11118)

**Antibiotics/Antivirals** (infection prevention):
- Acyclovir (RxNorm: 161)
- Trimethoprim-sulfamethoxazole (RxNorm: 10831)

**Pain Management**:
- Morphine, Oxycodone, etc.

**Hydration**:
- IV fluids, electrolyte solutions

---

## 5. Time Window Overlap Logic

### Temporal Overlap Algorithm

A concomitant medication is administered "during" chemotherapy if:

```
chemo_start <= conmed_start <= chemo_stop
OR
chemo_start <= conmed_stop <= chemo_stop
OR
(conmed_start <= chemo_start AND conmed_stop >= chemo_stop)
```

This captures:
1. Conmeds started during chemo (even if they extend beyond)
2. Conmeds stopped during chemo (even if they started before)
3. Conmeds that completely span the chemo period

### Date Field Priority

**For chemotherapy medications**:
1. `dosage_timing_repeat_bounds_period_start/end` (most specific)
2. `medication_administration.effective_period_start/end` (actual admin)
3. `authored_on` (order date - use as proxy if no period available)

**For concomitant medications**:
- Same priority as above

---

## 6. Proposed View Schema

### Output Fields

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_concomitant_medications AS
SELECT
    -- Patient identifier
    patient_fhir_id,

    -- CHEMOTHERAPY AGENT DETAILS
    chemo_medication_fhir_id,
    chemo_rxnorm_cui,
    chemo_medication_name,
    chemo_medication_display,
    chemo_intent,
    chemo_status,

    -- CHEMOTHERAPY TIME WINDOW
    chemo_start_datetime,
    chemo_stop_datetime,
    chemo_authored_datetime,
    chemo_duration_days,

    -- CONCOMITANT MEDICATION DETAILS
    conmed_medication_fhir_id,
    conmed_rxnorm_cui,
    conmed_medication_name,
    conmed_medication_display,
    conmed_status,
    conmed_intent,

    -- CONCOMITANT MEDICATION TIME WINDOW
    conmed_start_datetime,
    conmed_stop_datetime,
    conmed_authored_datetime,
    conmed_duration_days,

    -- TEMPORAL OVERLAP DETAILS
    overlap_start_datetime,  -- MAX(chemo_start, conmed_start)
    overlap_stop_datetime,   -- MIN(chemo_stop, conmed_stop)
    overlap_duration_days,

    -- OVERLAP TYPE
    overlap_type,  -- 'during_chemo', 'started_during_chemo', 'stopped_during_chemo', 'spans_chemo'

    -- CONMED CATEGORIZATION
    conmed_category,  -- 'antiemetic', 'corticosteroid', 'growth_factor', 'anticonvulsant', etc.
    conmed_schedule_category,  -- from dosage instructions if available

    -- DATA QUALITY
    has_chemo_rxnorm,
    has_conmed_rxnorm,
    chemo_date_source,  -- 'period', 'administration', 'authored_on'
    conmed_date_source
FROM ...
```

---

## 7. Implementation Approach

### Step 1: Identify Chemotherapy Medications
```sql
chemotherapy_agents AS (
    SELECT
        mr.id as medication_fhir_id,
        mr.subject_reference as patient_fhir_id,
        mrcc.code_coding_code as rxnorm_cui,
        mrcc.code_coding_display as medication_name,
        mr.medication_display,
        mr.status,
        mr.intent,

        -- Standardized dates
        CASE
            WHEN LENGTH(mr.dosage_timing_repeat_bounds_period_start) = 10
            THEN mr.dosage_timing_repeat_bounds_period_start || 'T00:00:00Z'
            ELSE mr.dosage_timing_repeat_bounds_period_start
        END as start_datetime,

        CASE
            WHEN LENGTH(mr.dosage_timing_repeat_bounds_period_end) = 10
            THEN mr.dosage_timing_repeat_bounds_period_end || 'T00:00:00Z'
            ELSE mr.dosage_timing_repeat_bounds_period_end
        END as stop_datetime,

        CASE
            WHEN LENGTH(mr.authored_on) = 10
            THEN mr.authored_on || 'T00:00:00Z'
            ELSE mr.authored_on
        END as authored_datetime

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN fhir_prd_db.medication_request_code_coding mrcc
        ON mr.id = mrcc.medication_request_id
    WHERE (
        -- Known chemotherapy RxNorm codes
        mrcc.code_coding_code IN (
            '82264',  -- Temozolomide
            '6599',   -- Lomustine
            '2095',   -- Carmustine
            '3002',   -- Cyclophosphamide
            '2555',   -- Cisplatin
            '2130',   -- Carboplatin
            '4139',   -- Etoposide
            '57841',  -- Irinotecan
            '11152',  -- Vincristine
            '11119',  -- Vinblastine
            '6851',   -- Methotrexate
            '3034',   -- Cytarabine
            '72824'   -- Bevacizumab
            -- Add more as needed
        )
        OR LOWER(mr.medication_display) LIKE '%chemotherapy%'
        OR LOWER(mr.medication_display) LIKE '%antineoplastic%'
        OR LOWER(mr.medication_display) LIKE '%cytotoxic%'
    )
    AND mr.status IN ('active', 'completed')
)
```

### Step 2: Identify All Other Medications (Potential Conmeds)
```sql
all_medications AS (
    SELECT
        mr.id as medication_fhir_id,
        mr.subject_reference as patient_fhir_id,
        mrcc.code_coding_code as rxnorm_cui,
        mrcc.code_coding_display as medication_name,
        mr.medication_display,
        mr.status,
        mr.intent,

        -- Dates (same standardization)
        ...

        -- Categorize medication
        CASE
            WHEN mrcc.code_coding_code IN ('26225', '4896', '288635') THEN 'antiemetic'
            WHEN mrcc.code_coding_code IN ('3264', '8640', '6902') THEN 'corticosteroid'
            WHEN mrcc.code_coding_code IN ('105585', '358810') THEN 'growth_factor'
            WHEN mrcc.code_coding_code IN ('35766', '11118') THEN 'anticonvulsant'
            WHEN mrcc.code_coding_code IN ('161', '10831') THEN 'antimicrobial'
            ELSE 'other'
        END as medication_category

    FROM fhir_prd_db.medication_request mr
    LEFT JOIN fhir_prd_db.medication_request_code_coding mrcc
        ON mr.id = mrcc.medication_request_id
    WHERE mr.status IN ('active', 'completed')
)
```

### Step 3: Calculate Temporal Overlaps
```sql
SELECT
    ca.patient_fhir_id,

    -- Chemotherapy details
    ca.medication_fhir_id as chemo_medication_fhir_id,
    ca.rxnorm_cui as chemo_rxnorm_cui,
    ca.medication_name as chemo_medication_name,
    ca.start_datetime as chemo_start_datetime,
    ca.stop_datetime as chemo_stop_datetime,

    -- Conmed details
    am.medication_fhir_id as conmed_medication_fhir_id,
    am.rxnorm_cui as conmed_rxnorm_cui,
    am.medication_name as conmed_medication_name,
    am.start_datetime as conmed_start_datetime,
    am.stop_datetime as conmed_stop_datetime,
    am.medication_category as conmed_category,

    -- Overlap calculation
    GREATEST(ca.start_datetime, am.start_datetime) as overlap_start_datetime,
    LEAST(ca.stop_datetime, am.stop_datetime) as overlap_stop_datetime,

    -- Overlap type
    CASE
        WHEN am.start_datetime >= ca.start_datetime AND am.stop_datetime <= ca.stop_datetime
            THEN 'during_chemo'
        WHEN am.start_datetime >= ca.start_datetime AND am.start_datetime <= ca.stop_datetime
            THEN 'started_during_chemo'
        WHEN am.stop_datetime >= ca.start_datetime AND am.stop_datetime <= ca.stop_datetime
            THEN 'stopped_during_chemo'
        WHEN am.start_datetime <= ca.start_datetime AND am.stop_datetime >= ca.stop_datetime
            THEN 'spans_chemo'
        ELSE 'unknown'
    END as overlap_type

FROM chemotherapy_agents ca
INNER JOIN all_medications am
    ON ca.patient_fhir_id = am.patient_fhir_id
WHERE
    -- Temporal overlap condition
    (
        (ca.start_datetime <= am.start_datetime AND ca.stop_datetime >= am.start_datetime)
        OR (ca.start_datetime <= am.stop_datetime AND ca.stop_datetime >= am.stop_datetime)
        OR (am.start_datetime <= ca.start_datetime AND am.stop_datetime >= ca.stop_datetime)
    )
    -- Exclude chemotherapy from conmed list
    AND am.medication_category != 'chemotherapy'
```

---

## 8. Data Quality Considerations

### Challenges
1. **Missing RxNorm codes**: Many medications may only have free text names
2. **Missing date ranges**: Some medications may only have `authored_on` date
3. **Overlapping chemotherapy regimens**: Patient may be on multiple chemo agents simultaneously
4. **Long-term medications**: Some conmeds (like anticonvulsants) may span multiple chemo cycles

### Solutions
1. Use free text matching as fallback when RxNorm not available
2. Create flags indicating date source quality
3. Allow one-to-many chemo-to-conmed relationships
4. Calculate partial overlaps with duration metrics

---

## 9. Expected Data Volumes

Based on typical FHIR medication_request data:
- **Total medication requests**: ~50,000-200,000 records
- **Chemotherapy medications**: ~5,000-10,000 records (estimated)
- **Unique patients with chemotherapy**: ~1,000-2,000 patients
- **Conmed-chemo pairs**: ~20,000-50,000 pairs (estimated 10-20 conmeds per chemo cycle)

---

## 10. Next Steps

1. ✅ **Refresh AWS credentials** to query Athena
2. ⏳ **Explore medication_request table** to validate date field availability
3. ⏳ **Count chemotherapy records** using RxNorm code filter
4. ⏳ **Test temporal overlap logic** on sample patient
5. ⏳ **Create production view SQL** with standardized formatting
6. ⏳ **Integrate into ATHENA_VIEW_CREATION_QUERIES.sql** master file
7. ⏳ **Create verification queries** for data validation

---

## 11. Verification Queries

Once view is created, validate with:

```sql
-- Test 1: Patient count with chemotherapy
SELECT COUNT(DISTINCT patient_fhir_id) as patients_with_chemo
FROM fhir_prd_db.v_concomitant_medications;

-- Test 2: Most common chemotherapy agents
SELECT
    chemo_rxnorm_cui,
    chemo_medication_name,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(*) as total_records
FROM fhir_prd_db.v_concomitant_medications
GROUP BY chemo_rxnorm_cui, chemo_medication_name
ORDER BY patient_count DESC;

-- Test 3: Most common concomitant medication categories
SELECT
    conmed_category,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(*) as total_conmed_records
FROM fhir_prd_db.v_concomitant_medications
GROUP BY conmed_category
ORDER BY total_conmed_records DESC;

-- Test 4: Overlap type distribution
SELECT
    overlap_type,
    COUNT(*) as record_count
FROM fhir_prd_db.v_concomitant_medications
GROUP BY overlap_type;

-- Test 5: Average number of conmeds per chemo cycle
SELECT
    patient_fhir_id,
    chemo_medication_fhir_id,
    COUNT(DISTINCT conmed_medication_fhir_id) as conmed_count
FROM fhir_prd_db.v_concomitant_medications
GROUP BY patient_fhir_id, chemo_medication_fhir_id
ORDER BY conmed_count DESC
LIMIT 20;
```

---

**Status**: Design complete, awaiting AWS credential refresh to begin implementation
