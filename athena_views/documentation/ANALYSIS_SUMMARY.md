# AWS Athena DateTime Column Analysis - fhir_prd_db
**Analysis Date:** October 19, 2025
**AWS Profile:** 343218191717_AWSAdministratorAccess
**Database:** fhir_prd_db

---

## Executive Summary

This analysis examined **24 views** in the `fhir_prd_db` database, covering **635 total columns** of which **123 are date/time related columns**.

### Critical Finding
**82.9% (102 out of 123) of datetime columns are stored as VARCHAR strings**, preventing efficient use of Athena's temporal functions and potentially impacting query performance.

---

## Data Type Distribution

| Data Type | Count | Percentage |
|-----------|-------|------------|
| **VARCHAR** | 102 | 82.9% |
| DATE | 7 | 5.7% |
| TIMESTAMP(3) | 3 | 2.4% |
| TIMESTAMP | 0 | 0.0% |
| TIMESTAMP WITH TIME ZONE | 0 | 0.0% |

---

## Key Findings

1. **102 out of 123 datetime columns (82.9%) are stored as VARCHAR** - highest priority for conversion
2. **7 columns use DATE type** (appropriate for date-only fields)
3. **3 columns use TIMESTAMP(3)** (high-precision datetime - recommended standard)
4. **Inconsistent naming conventions**: some use '_date', some '_datetime', some have no suffix
5. **v_diagnoses uses TIMESTAMP(3) consistently** - good example for standardization
6. **Several views mix VARCHAR datetime columns with proper temporal types**

---

## Views by DateTime Column Count

| View Name | Total Columns | DateTime Columns | VARCHAR | DATE | TIMESTAMP(3) |
|-----------|---------------|------------------|---------|------|--------------|
| v_radiation_treatments | 62 | 15 | 14 | 0 | 0 |
| v_concomitant_medications | 29 | 11 | 11 | 0 | 0 |
| v_hydrocephalus_diagnosis | 42 | 10 | 9 | 0 | 0 |
| v_autologous_stem_cell_transplant | 28 | 8 | 7 | 0 | 0 |
| v_hydrocephalus_procedures | 64 | 8 | 6 | 0 | 0 |
| v_medications | 51 | 7 | 7 | 0 | 0 |
| v_procedures_tumor | 49 | 7 | 6 | 1 | 0 |
| v_autologous_stem_cell_collection | 29 | 5 | 5 | 0 | 0 |
| v_diagnoses | 13 | 5 | 0 | 0 | 3 |
| v_imaging_corticosteroid_use | 20 | 5 | 3 | 0 | 0 |
| v_problem_list_diagnoses | 13 | 5 | 3 | 0 | 0 |
| v_visits_unified | 19 | 5 | 4 | 1 | 0 |
| v_imaging | 18 | 4 | 4 | 0 | 0 |
| v_measurements | 30 | 4 | 4 | 0 | 0 |
| v_binary_files | 25 | 3 | 3 | 0 | 0 |
| v_encounters | 28 | 3 | 2 | 1 | 0 |
| v_molecular_tests | 20 | 3 | 3 | 0 | 0 |
| v_radiation_documents | 22 | 3 | 3 | 0 | 0 |
| v_radiation_treatment_appointments | 12 | 3 | 3 | 0 | 0 |
| v_audiology_assessments | 21 | 2 | 1 | 1 | 0 |
| v_ophthalmology_assessments | 19 | 2 | 1 | 1 | 0 |
| v_radiation_care_plan_hierarchy | 8 | 2 | 2 | 0 | 0 |
| v_radiation_summary | 7 | 2 | 0 | 2 | 0 |
| v_patient_demographics | 6 | 1 | 1 | 0 | 0 |

---

## Top Priority Views for Remediation

### 1. v_radiation_treatments (14 VARCHAR datetime columns)
- `obs_start_date`, `obs_stop_date`, `obs_effective_date`, `obs_issued_date`
- `sr_occurrence_date_time`, `sr_occurrence_period_start`, `sr_occurrence_period_end`
- `sr_authored_on`
- `apt_first_appointment_date`, `apt_last_appointment_date`
- `cp_first_start_date`, `cp_last_end_date`
- `best_treatment_start_date`, `best_treatment_stop_date`

### 2. v_concomitant_medications (11 VARCHAR datetime columns)
- `chemo_start_datetime`, `chemo_stop_datetime`, `chemo_authored_datetime`
- `conmed_start_datetime`, `conmed_stop_datetime`, `conmed_authored_datetime`
- `overlap_start_datetime`, `overlap_stop_datetime`
- Plus 3 more date-related fields

### 3. v_hydrocephalus_diagnosis (9 VARCHAR datetime columns)
- `cond_onset_datetime`, `cond_abatement_datetime`, `cond_recorded_date`
- `cond_onset_period_start`, `cond_onset_period_end`
- `img_first_date`, `img_most_recent_date`
- Plus 2 more date fields

### 4. v_autologous_stem_cell_transplant (7 VARCHAR datetime columns)
- `cond_onset_datetime`, `cond_recorded_datetime`
- `proc_performed_datetime`, `proc_period_start`
- `obs_transplant_datetime`, `cd34_collection_datetime`, `transplant_datetime`

### 5. v_medications (7 VARCHAR datetime columns)
- `medication_start_date`
- `mr_validity_period_start`, `mr_validity_period_end`, `mr_authored_on`
- `cp_created`, `cp_period_start`, `cp_period_end`

---

## Best Practice Example

### v_diagnoses - Proper TIMESTAMP(3) Usage
This view demonstrates the recommended standard:
- `onset_date_time`: TIMESTAMP(3)
- `abatement_date_time`: TIMESTAMP(3)
- `recorded_date`: TIMESTAMP(3)

**Why TIMESTAMP(3)?**
- Millisecond precision
- Native Athena temporal functions work efficiently
- Proper sorting and filtering
- Can use date/time arithmetic without conversion

---

## Naming Convention Analysis

### Issues Found
1. **Inconsistent suffixes**: Some columns use `_date`, others `_datetime`, some have no suffix
2. **Ambiguous names**: Columns like `created`, `issued`, `authored_on` don't clearly indicate they're dates
3. **Misleading names**: Some `_date` columns may contain time components (stored as VARCHAR)

### Recommendations
1. **Use `_date` suffix** for DATE type columns (date-only, no time)
2. **Use `_datetime` suffix** for TIMESTAMP(3) columns (date with time)
3. **Be explicit**: Prefer `start_datetime` over just `start`
4. **Consistent prefixes**: Period columns should use `period_start` and `period_end`

---

## Standardization Recommendations

### High Priority (VARCHAR → Temporal Type Conversions)

#### 1. For columns with `_datetime` suffix
**Convert to:** TIMESTAMP(3)
**Examples:**
- `collection_datetime`, `mobilization_start_datetime`, `chemo_start_datetime`
- All period start/end fields

#### 2. For columns with `_date` suffix
**Action:** Verify data content
- If date-only → Convert to DATE
- If includes time → Convert to TIMESTAMP(3) and rename to `_datetime`

**Examples:**
- `assessment_date` (currently DATE - keep as is)
- `medication_start_date` (currently VARCHAR - verify and convert)
- `obs_start_date` (currently VARCHAR - verify and convert)

#### 3. For columns with temporal semantics but no suffix
**Action:** Add suffix and convert type
- `created` → `created_datetime` (TIMESTAMP(3))
- `issued` → `issued_datetime` (TIMESTAMP(3))
- `authored_on` → `authored_datetime` (TIMESTAMP(3))

### Benefits of Standardization

1. **Performance**: Native temporal functions are faster than string parsing
2. **Correctness**: Proper timezone handling and date arithmetic
3. **Queryability**: Can use WHERE clauses with date ranges efficiently
4. **Consistency**: Easier to understand and maintain
5. **Storage**: Temporal types can be more space-efficient than VARCHAR

---

## Recommended Migration Strategy

### Phase 1: High-Impact Views (Weeks 1-2)
- v_radiation_treatments
- v_concomitant_medications
- v_hydrocephalus_diagnosis

### Phase 2: Medium-Impact Views (Weeks 3-4)
- v_medications
- v_procedures_tumor
- v_autologous_stem_cell_transplant

### Phase 3: Remaining Views (Weeks 5-6)
- All other views with VARCHAR datetime columns

### Migration Steps (per view)
1. **Analyze source data**: Verify format and consistency
2. **Create conversion logic**: Parse ISO8601 strings to proper types
3. **Test conversion**: Validate on subset of data
4. **Create new view**: With corrected types
5. **Parallel run**: Compare old vs new results
6. **Cutover**: Switch applications to new view
7. **Cleanup**: Remove old view after validation period

---

## Example Conversion SQL

```sql
-- Example: Converting VARCHAR datetime to TIMESTAMP(3)
CREATE OR REPLACE VIEW v_concomitant_medications_v2 AS
SELECT
    patient_fhir_id,
    chemo_medication_fhir_id,
    -- Convert VARCHAR ISO8601 to TIMESTAMP(3)
    CAST(chemo_start_datetime AS TIMESTAMP(3)) AS chemo_start_datetime,
    CAST(chemo_stop_datetime AS TIMESTAMP(3)) AS chemo_stop_datetime,
    CAST(chemo_authored_datetime AS TIMESTAMP(3)) AS chemo_authored_datetime,
    -- ... rest of columns
FROM original_source;

-- Example: Converting VARCHAR date to DATE
CREATE OR REPLACE VIEW v_encounters_v2 AS
SELECT
    encounter_fhir_id,
    -- If encounter_date is already DATE, keep as is
    encounter_date,
    -- Convert VARCHAR dates to DATE
    CAST(period_start AS DATE) AS period_start_date,
    -- Or to TIMESTAMP if time component exists
    CAST(period_start AS TIMESTAMP(3)) AS period_start_datetime
FROM original_source;
```

---

## Files Generated

1. **athena_views_datetime_analysis.json** (77 KB)
   - Complete structured analysis in JSON format
   - Detailed recommendations for each column
   - Programmatically parseable

2. **athena_datetime_columns.csv** (38 KB)
   - Spreadsheet-friendly format
   - All 123 datetime columns with recommendations
   - Sortable and filterable

3. **ANALYSIS_SUMMARY.md** (this file)
   - Executive summary and recommendations
   - Migration strategy
   - Best practices

---

## Validation Queries

### Check for VARCHAR datetime columns
```sql
-- List all VARCHAR columns that likely contain dates
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'fhir_prd_db'
  AND table_name LIKE 'v_%'
  AND data_type = 'varchar'
  AND (
    column_name LIKE '%date%'
    OR column_name LIKE '%time%'
    OR column_name LIKE '%created%'
    OR column_name LIKE '%issued%'
    OR column_name LIKE '%authored%'
  )
ORDER BY table_name, column_name;
```

### Sample data inspection
```sql
-- Inspect actual values to determine appropriate type
SELECT
    chemo_start_datetime,
    LENGTH(chemo_start_datetime) as str_length,
    -- Try parsing
    TRY(CAST(chemo_start_datetime AS TIMESTAMP)) as parsed_timestamp,
    TRY(CAST(chemo_start_datetime AS DATE)) as parsed_date
FROM fhir_prd_db.v_concomitant_medications
WHERE chemo_start_datetime IS NOT NULL
LIMIT 100;
```

---

## Next Steps

1. **Review this analysis** with data engineering team
2. **Prioritize views** based on business impact and query frequency
3. **Validate data formats** in source systems
4. **Create migration plan** with timeline
5. **Implement conversions** in phases
6. **Update documentation** and downstream dependencies
7. **Monitor performance** improvements post-migration

---

## Contact & Questions

For questions about this analysis or migration strategy, please contact the data engineering team.

**Analysis Tool:** AWS Athena DESCRIBE commands
**AWS Profile:** 343218191717_AWSAdministratorAccess
**Region:** us-east-1
