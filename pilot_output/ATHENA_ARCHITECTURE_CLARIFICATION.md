# CORRECTED: Athena Demographics Architecture - HealthLake vs Materialized Views

## Architecture Clarification (October 4, 2025)

There are **TWO LAYERS** of Athena data access:

### Layer 1: HealthLake Raw FHIR Views (Primary Source)
**Database**: `radiant_prd_343218191717_us_east_1_prd_fhir_datastore_90d6a59616343629b26cd05c6686f0e8_healthlake_view`

**Patient Resource Table**: `.patient`
- Contains complete FHIR Patient JSON resources
- Includes all US Core extensions (race, ethnicity)
- birthDate, gender in FHIR format

### Layer 2: Materialized/Flattened Views (Convenience Layer)
**Database**: `fhir_v2_prd_db`

**Patient Access Table**: `.patient_access` 
- Flattened/transformed from HealthLake Patient resources
- Pre-extracted demographics fields for easy querying
- Used by MCP servers for quick demographic lookups

## Why Both Are Important

### For BRIM Extraction with Note Context:
- **HealthLake raw FHIR** provides complete Patient resource structure
- Can be cast into structured fields for extraction
- Maintains FHIR fidelity for compliance

### For Pre-populating Demographics CSV:
- **`fhir_v2_prd_db.patient_access`** is faster for bulk queries
- Already flattened - no JSON parsing needed
- Used for creating `patient_demographics.csv`

## Correct Approach for Phase 3a_v2

### Option A: Query HealthLake Patient Resource (FHIR-native)
```sql
SELECT 
  id,
  birthdate,  -- Note: lowercase in FHIR, uppercase in transformed views
  gender,
  -- race and ethnicity are in extensions
FROM radiant_prd_343218191717_us_east_1_prd_fhir_datastore_90d6a59616343629b26cd05c6686f0e8_healthlake_view.patient
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

### Option B: Query Materialized Access View (Simpler, Already Transformed)
```sql
SELECT 
  id,
  birth_date,  -- Note: snake_case in materialized views
  gender,
  race,        -- Already extracted from FHIR extensions
  ethnicity    -- Already extracted from FHIR extensions
FROM fhir_v2_prd_db.patient_access
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

### Recommendation: Use Materialized View (`fhir_v2_prd_db.patient_access`)

**Why?**
1. ✅ **Already transformed**: race/ethnicity extracted from FHIR extensions
2. ✅ **Simpler queries**: No JSON parsing needed
3. ✅ **Same data**: Materialized from HealthLake, so same source of truth
4. ✅ **Already validated**: Confirmed working in our test query
5. ✅ **Faster**: Pre-flattened, indexed

**When to use HealthLake raw FHIR?**
- When you need the FULL Patient resource structure
- When you need extensions not in materialized views
- When you need to validate against FHIR spec

## Validated Query (Already Tested)

```sql
SELECT id, gender, birth_date, race, ethnicity, deceased_boolean
FROM fhir_v2_prd_db.patient_access
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
```

**Results** (Confirmed October 4, 2025):
```
id: e4BwD8ZYDBccepXcJ.Ilo3w3
gender: female
birth_date: 2005-05-13
race: White
ethnicity: Not Hispanic or Latino
deceased_boolean: False
```

## Phase 3a_v2 Implementation

### Pre-populate Demographics CSV from Materialized View

```python
import boto3
import csv

# Query materialized view
query = """
SELECT 
  id as patient_fhir_id,
  CASE gender
    WHEN 'female' THEN 'Female'
    WHEN 'male' THEN 'Male'
    ELSE gender
  END as gender,
  birth_date,
  race,
  ethnicity
FROM fhir_v2_prd_db.patient_access
WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
"""

# Export to patient_demographics.csv
# Result: patient_fhir_id,gender,birth_date,race,ethnicity
#         e4BwD8ZYDBccepXcJ.Ilo3w3,Female,2005-05-13,White,Not Hispanic or Latino
```

## Summary

✅ **Use `fhir_v2_prd_db.patient_access`** for demographics (already validated, working)
✅ **HealthLake raw FHIR views** are the source, but materialized views are transformed/convenient
✅ **Both point to same data**, materialized views are just pre-processed
✅ **Our approach is correct**: Query materialized view → pre-populate CSV → BRIM uses CSV

The key insight is that `fhir_v2_prd_db.patient_access` IS derived from the HealthLake FHIR Patient resources - it's just the flattened, query-optimized version of the same data.
