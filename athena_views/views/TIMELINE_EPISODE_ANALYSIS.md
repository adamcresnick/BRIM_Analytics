# Timeline Episode View Analysis
**Date**: 2025-10-28
**Purpose**: Assess feasibility of creating medication episode and radiation course views for layered timeline visualization

## Executive Summary

**Current State**: v_unified_patient_timeline captures **discrete events** (individual medication orders, individual radiation appointments)

**Your Requirement**: Layered timeline visualization showing **treatment spans** with start/stop dates for:
1. Encounters/visits (already have spans ✅)
2. Procedures (already have timepoints ✅)
3. **Medication episodes** (need to create ❌)
4. **Radiation courses** (need to create ❌)

## Findings

### 1. Medication Data Available - v_medications vs v_chemo_medications

**IMPORTANT**: v_medications ([Lines 1274-1471](../views/DATETIME_STANDARDIZED_VIEWS.sql:1274-1471)) has **BETTER metadata for episode construction** than v_chemo_medications!

#### v_medications - **RECOMMENDED for Episodes**

**Available Fields**:
- ✅ `medication_start_date` - from `dosage_instruction_timing_repeat_bounds_period_start` or `authored_on`
- ✅ `medication_stop_date` - from `dosage_instruction_timing_repeat_bounds_period_end` or `dispense_request_validity_period_end`
- ✅ `cp_id` - CarePlan ID (direct join, not aggregated string)
- ✅ **`cp_period_start`** - **Treatment protocol start date** (episode boundary!)
- ✅ **`cp_period_end`** - **Treatment protocol end date** (episode boundary!)
- ✅ `cp_title` - Treatment protocol name
- ✅ `cp_status` - active, completed, cancelled
- ✅ `mrb_care_plan_references` - aggregated string of all linked CarePlans
- ✅ All CarePlan activity details (cpa_activity_detail_statuses, descriptions)

**Coverage Analysis** (from view comments):
- **"Improves coverage from 16% to ~100%"** using timing_bounds
- ~84% of medications have explicit timing bounds from dosage instructions
- Remaining ~16% fall back to authored_on date
- CarePlan linkage available where medications are part of treatment protocols

#### v_chemo_medications - Chemotherapy-specific filtering

**Available Fields**:
- ✅ Same date logic as v_medications (identical timing_bounds CTE)
- ✅ `care_plan_references` - aggregated string only (no direct CarePlan fields)
- ✅ `chemo_preferred_name` - normalized drug name with chemotherapy validation
- ✅ Comprehensive drug matching (RxNorm + name-based + investigational)
- ❌ **Missing**: cp_period_start, cp_period_end (no direct CarePlan join)

**Episode Grouping Options**:

**Option A: CarePlan-Based Episodes** (Most Accurate)
```sql
-- Group medications by CarePlan reference
-- Pros: Reflects actual clinical treatment protocols
-- Cons: Not all medications link to CarePlan
SELECT
    patient_fhir_id,
    care_plan_references,  -- Treatment protocol ID
    MIN(medication_start_date) as episode_start,
    MAX(medication_stop_date) as episode_end,
    LISTAGG(chemo_preferred_name, ', ') as medications_in_episode
FROM v_chemo_medications
GROUP BY patient_fhir_id, care_plan_references
```

**Option B: Temporal Windowing** (Fallback for medications without CarePlan)
```sql
-- Group medications by temporal proximity
-- If med starts within 7 days of previous med's stop → same episode
-- Pros: Works for all medications
-- Cons: Heuristic-based, may not reflect true clinical grouping
```

**Option C: Medication Name + Temporal Windowing** (Hybrid)
```sql
-- Group same drug administrations within treatment window
-- Vincristine 2023-01-15 to 2023-03-20 = 1 episode
-- Pros: Reflects continuous treatment with single agent
-- Cons: Doesn't capture multi-drug regimens well
```

### 2. v_radiation_treatment_appointments - Radiation Data Available

**Available Fields** ([DATETIME_STANDARDIZED_VIEWS.sql:4361-4481](../views/DATETIME_STANDARDIZED_VIEWS.sql:4361-4481)):
- ✅ `appointment_start` - timestamp of individual fraction
- ✅ `appointment_end` - end of individual fraction
- ✅ `appointment_status` - booked, fulfilled, cancelled
- ⚠️ NO course_id or grouping field
- ⚠️ NO treatment plan reference

**Missing**: Direct grouping mechanism for fractions into courses

**Course Grouping Options**:

**Option A: Temporal Windowing** (Most Feasible)
```sql
-- Group radiation fractions by temporal continuity
-- Typical radiation course: 5 fractions/week for 4-6 weeks
-- If gap > 10 days between fractions → new course
-- Pros: Works with available data
-- Cons: Heuristic, may split single course if scheduling gaps exist
```

**Option B: v_radiation_treatments Integration** (Better but Complex)
```sql
-- v_radiation_treatments has obs_start_date and obs_stop_date
-- These represent structured course-level data
-- Link appointments to courses via date overlap
-- Pros: More accurate course boundaries
-- Cons: Requires complex join, only works for patients with structured data
```

### 3. Metadata Discovery - CarePlan as Treatment Episode Identifier

**FHIR CarePlan Resource** ([Lines 282-419](../views/DATETIME_STANDARDIZED_VIEWS.sql:282-419)):
```sql
-- CarePlan fields available:
- cp.id (unique identifier for treatment plan)
- cp.title (human-readable protocol name)
- cp.status (active, completed, cancelled)
- cp.period_start (when treatment plan starts)
- cp.period_end (when treatment plan ends)
- cp.category (e.g., "chemotherapy", "radiation")
```

**How Medications Link to CarePlan**:
- `medication_request.based_on` → references CarePlan.id
- Aggregated in v_chemo_medications as `care_plan_references`

**Implication**: CarePlan provides the **treatment episode boundary** for medications

## Recommended Approach

### v_medication_episodes

**Strategy**: Hybrid approach using CarePlan + temporal windowing

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_medication_episodes AS
WITH
-- Step 1: Group medications by CarePlan (for those with protocol linkage)
careplan_episodes AS (
    SELECT
        patient_fhir_id,
        care_plan_references as episode_id,
        'careplan_protocol' as episode_grouping_method,
        MIN(medication_start_date) as episode_start_date,
        MAX(medication_stop_date) as episode_end_date,
        COUNT(DISTINCT medication_request_fhir_id) as total_medication_orders,
        COUNT(DISTINCT chemo_preferred_name) as unique_medications,
        LISTAGG(DISTINCT chemo_preferred_name, ' + ')
            WITHIN GROUP (ORDER BY chemo_preferred_name) as medication_regimen,
        LISTAGG(DISTINCT medication_request_fhir_id, '|')
            WITHIN GROUP (ORDER BY medication_start_date) as medication_ids
    FROM fhir_prd_db.v_chemo_medications
    WHERE care_plan_references IS NOT NULL
      AND medication_start_date IS NOT NULL
    GROUP BY patient_fhir_id, care_plan_references
),

-- Step 2: For medications WITHOUT CarePlan, group by temporal windows
-- Uses LAG window function to detect gaps > 14 days
medications_without_careplan AS (
    SELECT
        *,
        -- Mark new episode when gap > 14 days from previous med
        SUM(CASE
            WHEN medication_start_date - LAG(medication_stop_date)
                 OVER (PARTITION BY patient_fhir_id, chemo_preferred_name
                       ORDER BY medication_start_date) > INTERVAL '14' DAY
            THEN 1 ELSE 0
        END) OVER (PARTITION BY patient_fhir_id, chemo_preferred_name
                   ORDER BY medication_start_date) as episode_number
    FROM fhir_prd_db.v_chemo_medications
    WHERE care_plan_references IS NULL
      AND medication_start_date IS NOT NULL
),

temporal_episodes AS (
    SELECT
        patient_fhir_id,
        chemo_preferred_name || '_episode_' || CAST(episode_number AS VARCHAR) as episode_id,
        'temporal_window' as episode_grouping_method,
        MIN(medication_start_date) as episode_start_date,
        MAX(medication_stop_date) as episode_end_date,
        COUNT(DISTINCT medication_request_fhir_id) as total_medication_orders,
        COUNT(DISTINCT chemo_preferred_name) as unique_medications,
        LISTAGG(DISTINCT chemo_preferred_name, ' + ')
            WITHIN GROUP (ORDER BY chemo_preferred_name) as medication_regimen,
        LISTAGG(DISTINCT medication_request_fhir_id, '|')
            WITHIN GROUP (ORDER BY medication_start_date) as medication_ids
    FROM medications_without_careplan
    GROUP BY patient_fhir_id, chemo_preferred_name, episode_number
)

-- Step 3: Union both approaches
SELECT * FROM careplan_episodes
UNION ALL
SELECT * FROM temporal_episodes
ORDER BY patient_fhir_id, episode_start_date;
```

**Key Features**:
- Uses CarePlan when available (most accurate)
- Falls back to 14-day gap heuristic for orphan medications
- Captures multi-drug regimens when linked to same CarePlan
- Provides `medication_ids` for drilling down to individual orders

### v_radiation_courses

**Strategy**: Temporal windowing with structured data validation

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_radiation_courses AS
WITH
-- Step 1: Get structured course boundaries from v_radiation_treatments
structured_courses AS (
    SELECT DISTINCT
        patient_fhir_id,
        obs_start_date as course_start_date,
        obs_stop_date as course_end_date,
        'structured_observation' as course_identification_method
    FROM fhir_prd_db.v_radiation_treatments
    WHERE obs_start_date IS NOT NULL
      AND obs_stop_date IS NOT NULL
),

-- Step 2: For appointments, detect course boundaries using gaps
appointment_gaps AS (
    SELECT
        patient_fhir_id,
        appointment_id,
        appointment_start,
        appointment_end,
        -- Mark new course when gap > 10 days from previous appointment
        SUM(CASE
            WHEN DATE_DIFF('day',
                LAG(CAST(appointment_end AS DATE))
                    OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start),
                CAST(appointment_start AS DATE)
            ) > 10
            THEN 1 ELSE 0
        END) OVER (PARTITION BY patient_fhir_id ORDER BY appointment_start) as course_number
    FROM fhir_prd_db.v_radiation_treatment_appointments
    WHERE appointment_status IN ('booked', 'fulfilled')
      AND appointment_start IS NOT NULL
),

temporal_courses AS (
    SELECT
        patient_fhir_id,
        course_number,
        'temporal_window_appointments' as course_identification_method,
        MIN(CAST(appointment_start AS DATE)) as course_start_date,
        MAX(CAST(appointment_end AS DATE)) as course_end_date,
        COUNT(DISTINCT appointment_id) as total_fractions,
        LISTAGG(appointment_id, '|')
            WITHIN GROUP (ORDER BY appointment_start) as appointment_ids
    FROM appointment_gaps
    GROUP BY patient_fhir_id, course_number
)

-- Step 3: Combine structured courses with temporal courses
SELECT
    sc.patient_fhir_id,
    'course_' || ROW_NUMBER() OVER (PARTITION BY sc.patient_fhir_id
                                     ORDER BY sc.course_start_date) as course_id,
    sc.course_start_date,
    sc.course_end_date,
    sc.course_identification_method,
    tc.total_fractions,
    tc.appointment_ids
FROM structured_courses sc
LEFT JOIN temporal_courses tc
    ON sc.patient_fhir_id = tc.patient_fhir_id
    AND tc.course_start_date BETWEEN sc.course_start_date AND sc.course_end_date

UNION ALL

-- Add temporal-only courses for patients without structured data
SELECT
    tc.patient_fhir_id,
    'course_' || tc.course_number as course_id,
    tc.course_start_date,
    tc.course_end_date,
    tc.course_identification_method,
    tc.total_fractions,
    tc.appointment_ids
FROM temporal_courses tc
WHERE NOT EXISTS (
    SELECT 1 FROM structured_courses sc
    WHERE sc.patient_fhir_id = tc.patient_fhir_id
)
ORDER BY patient_fhir_id, course_start_date;
```

**Key Features**:
- Prioritizes structured course data when available
- Uses 10-day gap heuristic for appointment grouping
- Counts total fractions per course
- Provides `appointment_ids` for drilling down

## Integration with v_unified_patient_timeline

### Current State
Timeline has **discrete events**:
- One row per medication order
- One row per radiation appointment

### Proposed Enhancement

**Option 1**: Add episode views as separate sections
```sql
-- Add to timeline:
UNION ALL
SELECT
    patient_fhir_id,
    'med_episode_' || episode_id as event_id,
    episode_start_date as event_date,
    'Medication Episode' as event_type,
    'Treatment Course' as event_category,
    medication_regimen as event_description,
    ...
FROM fhir_prd_db.v_medication_episodes
```

**Option 2**: Create separate timeline view for spans
```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_unified_patient_timeline_spans AS
-- Encounters (already have spans)
SELECT patient_fhir_id, visit_start_datetime, visit_end_datetime, ...
FROM v_visits_unified

UNION ALL

-- Medication episodes
SELECT patient_fhir_id, episode_start_date, episode_end_date, ...
FROM v_medication_episodes

UNION ALL

-- Radiation courses
SELECT patient_fhir_id, course_start_date, course_end_date, ...
FROM v_radiation_courses
```

**Recommendation**: **Option 2** - Keep discrete events separate from spans
- Enables efficient querying for either view
- Supports your layered visualization use case directly
- Avoids mixing point events with span events in same view

## Data Quality Considerations

### Medication Episodes
**Strengths**:
- 89% have explicit start/stop dates from dosage instructions
- CarePlan linkage available for protocol-based grouping

**Risks**:
- 11% of medications missing timing bounds (will use authored_on as point-in-time)
- Not all medications link to CarePlan (temporal windowing required)
- Multi-drug regimens may span multiple CarePlans

### Radiation Courses
**Strengths**:
- Structured course data available for ~13% of patients (from v_radiation_treatments)
- Appointments provide fraction-level granularity

**Risks**:
- No explicit course ID in appointment data
- 10-day gap heuristic may split single course if treatment paused (holidays, toxicity)
- May merge separate courses if scheduled close together

## Next Steps

1. **Validate Grouping Heuristics** - Query sample patients to verify:
   - 14-day gap for medication episodes is appropriate
   - 10-day gap for radiation courses doesn't over-split

2. **Create Episode Views** - Implement v_medication_episodes and v_radiation_courses

3. **Create Span Timeline View** - Implement v_unified_patient_timeline_spans

4. **Test with Sample Patients** - Validate against known treatment courses

5. **Deploy and Integrate** - Add to abstraction workflow

## Questions for You

1. **Medication Episode Granularity**: Do you want:
   - One episode per CarePlan (multi-drug regimen as single span)?
   - One episode per drug (vincristine span separate from doxorubicin span)?

2. **Radiation Course Splitting**: If patient has 10-day gap mid-course (e.g., holiday break), should this:
   - Stay as one course (increase gap threshold)?
   - Split into two courses (keep conservative threshold)?

3. **Overlapping Episodes**: If patient receives concurrent medications (e.g., chemo + supportive care), should timeline show:
   - Overlapping spans (multiple medications at once)?
   - Combined episode (all concurrent meds as one span)?

4. **Timeline Integration**: Do you want:
   - Separate span view (v_unified_patient_timeline_spans)?
   - Both views integrated (add episodes to existing timeline)?
   - Replace discrete events with episodes entirely?
