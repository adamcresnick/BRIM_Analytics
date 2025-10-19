# DateTime Standardization Implementation Plan

**Created**: 2025-10-19
**Status**: READY FOR REVIEW
**Priority**: HIGH - Fixes 82.9% of datetime columns currently stored as VARCHAR

---

## Executive Summary

This document provides a phased implementation plan to standardize 102 VARCHAR datetime columns across 24 Athena views. **ONLY datetime column types and parsing will be modified** - no other logic changes.

### Key Principles

1. ✅ **ONLY change datetime columns** - No other modifications
2. ✅ **Maintain backward compatibility** - Keep original column names
3. ✅ **Test before deployment** - Validate each view independently
4. ✅ **Preserve all existing logic** - No changes to JOINs, WHERE clauses, aggregations
5. ✅ **Use TRY_CAST** - Gracefully handle parsing errors

---

## Standardization Rules

### Rule 1: VARCHAR with ISO8601 timestamp → TIMESTAMP(3)

**Pattern**: Columns with `_datetime` suffix or containing time components

**Conversion**:
```sql
-- BEFORE (VARCHAR):
collection_datetime  -- Value: "2024-06-10T14:30:00Z"

-- AFTER (TIMESTAMP(3)):
TRY(CAST(collection_datetime AS TIMESTAMP(3))) AS collection_datetime
```

### Rule 2: VARCHAR with date-only → DATE

**Pattern**: Columns with `_date` suffix containing date-only values

**Conversion**:
```sql
-- BEFORE (VARCHAR):
assessment_date  -- Value: "2024-06-10"

-- AFTER (DATE):
TRY(CAST(assessment_date AS DATE)) AS assessment_date
```

### Rule 3: Extract date from datetime → Add _date column

**Pattern**: For datetime columns, add corresponding _date column for date-only queries

**Conversion**:
```sql
-- Original datetime column
TRY(CAST(collection_datetime AS TIMESTAMP(3))) AS collection_datetime,

-- NEW: Add date-only column for filtering
DATE(TRY(CAST(collection_datetime AS TIMESTAMP(3)))) AS collection_date
```

---

## Implementation Phases

### Phase 1: High-Priority Views (Week 1)

Focus on views with highest VARCHAR datetime column count and query frequency:

| View | VARCHAR DateTime Cols | Deployment Order |
|------|----------------------|------------------|
| v_radiation_treatments | 14 | 1 |
| v_concomitant_medications | 11 | 2 |
| v_hydrocephalus_diagnosis | 9 | 3 |

**Testing Strategy**:
- Run parallel comparison queries (old vs new) for 100 random patients
- Validate date ranges match
- Check for NULL parsing errors
- Monitor query performance (should improve)

### Phase 2: Medium-Priority Views (Week 2)

| View | VARCHAR DateTime Cols | Deployment Order |
|------|----------------------|------------------|
| v_autologous_stem_cell_transplant | 7 | 4 |
| v_medications | 7 | 5 |
| v_procedures_tumor | 6 | 6 |
| v_hydrocephalus_procedures | 6 | 7 |

### Phase 3: Remaining Views (Week 3)

All other views with VARCHAR datetime columns (sorted by priority):

| View | VARCHAR DateTime Cols | Deployment Order |
|------|----------------------|------------------|
| v_autologous_stem_cell_collection | 5 | 8 |
| v_visits_unified | 4 | 9 |
| v_imaging | 4 | 10 |
| v_measurements | 4 | 11 |
| v_molecular_tests | 3 | 12 |
| v_imaging_corticosteroid_use | 3 | 13 |
| v_problem_list_diagnoses | 3 | 14 |
| v_radiation_documents | 3 | 15 |
| v_radiation_treatment_appointments | 3 | 16 |
| v_binary_files | 3 | 17 |
| v_encounters | 2 | 18 |
| v_radiation_care_plan_hierarchy | 2 | 19 |
| v_audiology_assessments | 1 | 20 |
| v_ophthalmology_assessments | 1 | 21 |
| v_patient_demographics | 1 | 22 |

---

## Implementation Template

### Step 1: Create Backup Query

**Before making ANY changes**, document current schema:

```sql
-- Save current view definition
SHOW CREATE VIEW fhir_prd_db.v_<view_name>;

-- Test current query on sample
SELECT * FROM fhir_prd_db.v_<view_name>
WHERE patient_fhir_id = '<test_patient>'
LIMIT 10;
```

### Step 2: Identify DateTime Columns

Use the comprehensive analysis file:
```bash
# Find all datetime columns for a specific view
cat /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/documentation/athena_datetime_columns.csv | grep "v_<view_name>"
```

### Step 3: Modify ONLY DateTime Columns

**Template for view with source tables**:

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_<view_name> AS
SELECT
    patient_fhir_id,  -- Keep as-is

    -- CHANGE #1: Convert VARCHAR datetime to TIMESTAMP(3)
    TRY(CAST(source_table.varchar_datetime_col AS TIMESTAMP(3))) AS datetime_col,

    -- CHANGE #2: Add date-only column for datetime
    DATE(TRY(CAST(source_table.varchar_datetime_col AS TIMESTAMP(3)))) AS datetime_col_date,

    -- CHANGE #3: Convert VARCHAR date to DATE
    TRY(CAST(source_table.varchar_date_col AS DATE)) AS date_col,

    other_column_1,  -- Keep as-is
    other_column_2,  -- Keep as-is
    -- ... all other columns unchanged

FROM source_table
LEFT JOIN other_table ON ...  -- Keep all JOINs as-is
WHERE conditions...  -- Keep all WHERE clauses as-is
ORDER BY ...;  -- Keep ORDER BY as-is
```

### Step 4: Validation Query Template

```sql
-- Compare old vs new for date ranges
WITH old_data AS (
    SELECT patient_fhir_id, varchar_datetime_col
    FROM fhir_prd_db.v_<view_name>_backup
    WHERE patient_fhir_id = '<test_patient>'
),
new_data AS (
    SELECT patient_fhir_id, datetime_col
    FROM fhir_prd_db.v_<view_name>
    WHERE patient_fhir_id = '<test_patient>'
)
SELECT
    COUNT(*) as row_count,
    COUNT(CASE WHEN old_data.varchar_datetime_col IS NOT NULL
                 AND new_data.datetime_col IS NULL THEN 1 END) as parsing_failures,
    MIN(new_data.datetime_col) as min_date,
    MAX(new_data.datetime_col) as max_date
FROM old_data
FULL OUTER JOIN new_data ON old_data.patient_fhir_id = new_data.patient_fhir_id;
```

### Step 5: Performance Comparison

```sql
-- Test query performance (should improve with native temporal types)
-- Old view (VARCHAR)
SELECT COUNT(*) FROM fhir_prd_db.v_<view_name>_backup
WHERE TRY(CAST(varchar_datetime_col AS DATE)) BETWEEN DATE '2024-01-01' AND DATE '2024-12-31';

-- New view (TIMESTAMP(3))
SELECT COUNT(*) FROM fhir_prd_db.v_<view_name>
WHERE datetime_col BETWEEN TIMESTAMP '2024-01-01 00:00:00' AND TIMESTAMP '2024-12-31 23:59:59';
```

---

## Example: v_autologous_stem_cell_collection

### Current Schema (5 VARCHAR datetime columns)

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_collection AS
SELECT
    patient_fhir_id,
    collection_procedure_fhir_id,
    collection_datetime,  -- VARCHAR ⚠️
    collection_method,
    collection_cpt_code,
    collection_status,
    collection_outcome,
    cd34_observation_fhir_id,
    cd34_measurement_datetime,  -- VARCHAR ⚠️
    cd34_count,
    cd34_unit,
    cd34_source,
    cd34_adequacy,
    mobilization_medication_fhir_id,
    mobilization_agent_name,
    mobilization_rxnorm_code,
    mobilization_agent_type,
    mobilization_start_datetime,  -- VARCHAR ⚠️
    mobilization_stop_datetime,  -- VARCHAR ⚠️
    mobilization_status,
    days_from_mobilization_to_collection,
    quality_observation_fhir_id,
    quality_metric,
    quality_metric_type,
    metric_value,
    metric_unit,
    metric_value_text,
    quality_measurement_datetime,  -- VARCHAR ⚠️
    data_completeness
FROM <source_tables>;
```

### Proposed Schema (ONLY datetime changes)

```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_autologous_stem_cell_collection AS
SELECT
    patient_fhir_id,
    collection_procedure_fhir_id,

    -- CHANGE #1: collection_datetime VARCHAR → TIMESTAMP(3)
    TRY(CAST(source.collection_datetime AS TIMESTAMP(3))) AS collection_datetime,
    -- NEW: Add date-only column
    DATE(TRY(CAST(source.collection_datetime AS TIMESTAMP(3)))) AS collection_date,

    collection_method,  -- Unchanged
    collection_cpt_code,  -- Unchanged
    collection_status,  -- Unchanged
    collection_outcome,  -- Unchanged
    cd34_observation_fhir_id,  -- Unchanged

    -- CHANGE #2: cd34_measurement_datetime VARCHAR → TIMESTAMP(3)
    TRY(CAST(source.cd34_measurement_datetime AS TIMESTAMP(3))) AS cd34_measurement_datetime,
    -- NEW: Add date-only column
    DATE(TRY(CAST(source.cd34_measurement_datetime AS TIMESTAMP(3)))) AS cd34_measurement_date,

    cd34_count,  -- Unchanged
    cd34_unit,  -- Unchanged
    cd34_source,  -- Unchanged
    cd34_adequacy,  -- Unchanged
    mobilization_medication_fhir_id,  -- Unchanged
    mobilization_agent_name,  -- Unchanged
    mobilization_rxnorm_code,  -- Unchanged
    mobilization_agent_type,  -- Unchanged

    -- CHANGE #3: mobilization_start_datetime VARCHAR → TIMESTAMP(3)
    TRY(CAST(source.mobilization_start_datetime AS TIMESTAMP(3))) AS mobilization_start_datetime,

    -- CHANGE #4: mobilization_stop_datetime VARCHAR → TIMESTAMP(3)
    TRY(CAST(source.mobilization_stop_datetime AS TIMESTAMP(3))) AS mobilization_stop_datetime,

    mobilization_status,  -- Unchanged
    days_from_mobilization_to_collection,  -- Unchanged
    quality_observation_fhir_id,  -- Unchanged
    quality_metric,  -- Unchanged
    quality_metric_type,  -- Unchanged
    metric_value,  -- Unchanged
    metric_unit,  -- Unchanged
    metric_value_text,  -- Unchanged

    -- CHANGE #5: quality_measurement_datetime VARCHAR → TIMESTAMP(3)
    TRY(CAST(source.quality_measurement_datetime AS TIMESTAMP(3))) AS quality_measurement_datetime,

    data_completeness  -- Unchanged
FROM <source_tables>;  -- All JOINs/WHERE/ORDER BY unchanged
```

**Summary of Changes**:
- ✅ 5 VARCHAR columns converted to TIMESTAMP(3)
- ✅ 2 new DATE columns added for filtering
- ✅ All other 24 columns unchanged
- ✅ All query logic unchanged

---

## Testing Checklist (Per View)

- [ ] Document current view definition
- [ ] Query current data for 10 test patients
- [ ] Identify all VARCHAR datetime columns
- [ ] Create modified view definition (datetime changes ONLY)
- [ ] Deploy to Athena
- [ ] Run validation queries (compare old vs new)
- [ ] Check for NULL parsing failures
- [ ] Verify row counts match
- [ ] Verify date ranges match
- [ ] Test query performance
- [ ] Document any issues
- [ ] Get approval to proceed to next view

---

## Risk Mitigation

### Risk 1: Parsing Failures

**Mitigation**: Use `TRY(CAST(...))` instead of `CAST(...)`
- Returns NULL on parsing failure instead of error
- Allows view to deploy even if some values are malformed

### Risk 2: Downstream Dependencies

**Mitigation**: Keep original column names
- Applications querying `collection_datetime` will still work
- Just get TIMESTAMP(3) instead of VARCHAR
- Most query patterns are compatible

### Risk 3: Query Breakage

**Mitigation**: Test on sample patients first
- Validate 100 random patients before full deployment
- Check for unexpected NULL values
- Verify date arithmetic works as expected

### Risk 4: Performance Degradation

**Mitigation**: Monitor query times
- Temporal types should be FASTER than VARCHAR parsing
- If performance degrades, investigate query plans
- May need to add indexes (though views don't support indexes directly)

---

## Rollback Plan

If issues arise after deployment:

```sql
-- 1. Revert to previous view definition
CREATE OR REPLACE VIEW fhir_prd_db.v_<view_name> AS
<paste_old_definition_from_backup>;

-- 2. Validate rollback
SELECT COUNT(*) FROM fhir_prd_db.v_<view_name>
WHERE patient_fhir_id = '<test_patient>';

-- 3. Document issue for future resolution
```

---

## Success Criteria

### Per-View Success

- ✅ View deploys without errors
- ✅ Row counts match pre-deployment
- ✅ NULL parsing failures < 1%
- ✅ Date ranges match pre-deployment
- ✅ Query performance same or better
- ✅ No downstream application errors

### Overall Success

- ✅ All 102 VARCHAR datetime columns converted
- ✅ Consistent naming convention across views
- ✅ Improved query performance for date filtering
- ✅ Native Athena temporal functions usable
- ✅ Documentation updated

---

## Next Steps

1. **REVIEW THIS PLAN** with stakeholders
2. **GET APPROVAL** before making any changes
3. **START WITH PHASE 1** (3 high-priority views)
4. **VALIDATE EACH VIEW** before proceeding
5. **DOCUMENT ISSUES** and adjust plan as needed
6. **PROCEED TO PHASES 2-3** after Phase 1 success

---

## Contact

**Author**: Claude Code Agent
**Date**: 2025-10-19
**Review Required**: Data Engineering Team
**Approval Required**: Before ANY view modifications

---

## Related Documentation

- [ATHENA_VIEWS_MASTER_DATA_DICTIONARY.md](./ATHENA_VIEWS_MASTER_DATA_DICTIONARY.md) - Complete column inventory
- [ANALYSIS_SUMMARY.md](./ANALYSIS_SUMMARY.md) - Detailed datetime analysis
- [athena_datetime_columns.csv](./athena_datetime_columns.csv) - Sortable column list
- [athena_views_datetime_analysis.json](./athena_views_datetime_analysis.json) - Programmatic access
- [DATE_STANDARDIZATION_EXAMPLE.sql](../views/DATE_STANDARDIZATION_EXAMPLE.sql) - Implementation examples
