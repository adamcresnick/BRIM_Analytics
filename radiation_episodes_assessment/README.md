# Radiation Episodes Assessment

This directory contains test queries and deployment files used during the development and validation of the radiation episode views (v_radiation_episodes and supporting views).

## Overview

These queries were created to test and validate the multi-stage radiation episode construction process, including:
- Stage 1a: Radiation observations (dose measurements)
- Stage 1b: Care plans (treatment intent, planning)
- Stage 1c: Appointments (treatment delivery sessions)
- Stage 1d: Documents (treatment summaries, planning notes)
- Unified Episodes: Combining all stages into cohesive treatment episodes

## Files by Category

### Stage 1a: Radiation Observations Testing

#### `test_stage_1a_clean.sql`
**Purpose**: Validate Stage 1a (radiation observations) data extraction and datetime handling

**Key Features**:
- Tests observation_datetime standardization
- Validates dose measurements and laterality
- Checks encounter linkage
- Verifies LOINC code filtering

**Expected Results**: Dose observations with properly parsed dates and laterality information

### Stage 1b: Care Plan Testing

#### `test_stage_1b_clean.sql`
**Purpose**: Validate Stage 1b (care plans) data extraction

**Key Features**:
- Tests care plan intent codes (curative/palliative)
- Validates datetime parsing from period.start
- Checks category filtering for radiation oncology

**Expected Results**: Care plans with treatment intent and dates

### Stage 1c: Appointments Testing

#### `test_stage_1c_clean.sql`
**Purpose**: Initial test of Stage 1c (appointments) extraction

#### `test_stage_1c_fixed.sql`
**Purpose**: Fixed version addressing datetime parsing issues

#### `test_stage_1c_observations.sql`
**Purpose**: Tests appointments linked to radiation observations

#### `test_stage_1c_revised.sql`
**Purpose**: Revised version with improved filtering logic

#### `test_stage_1c_revised_fixed.sql`
**Purpose**: Final corrected version with all fixes applied

**Key Features** (final version):
- Tests appointment datetime standardization
- Validates service category filtering (Radiation Oncology)
- Checks appointment status (booked, arrived, fulfilled, etc.)
- Tests linkage to encounters and observations
- Validates location/department information

**Common Issues Addressed**:
- Datetime casting from VARCHAR to TIMESTAMP
- Timezone handling
- NULL value handling in dates
- Appointment status filtering

### Stage 1d: Documents Testing

#### `test_stage_1d_documents.sql`
**Purpose**: Validate Stage 1d (radiation treatment documents) extraction

**Key Features**:
- Tests document_reference table filtering
- Validates document type codes (treatment summary, planning notes, etc.)
- Checks attachment creation dates
- Tests document status filtering
- Validates content.attachment.creation datetime parsing

**Expected Results**: Treatment summaries, planning notes, simulation documents with dates

#### `datetime_std_v_radiation_documents.sql`
**Purpose**: Extract from DATETIME_STANDARDIZED_VIEWS.sql to test v_radiation_documents

**Use Case**: Isolated testing of the v_radiation_documents view logic

#### Document Date Investigation Queries

These queries investigated datetime field availability across document tables:
- `analyze_radiation_documents.sql` - Initial investigation
- `analyze_radiation_documents_fixed.sql` - Corrected version
- `compare_radiation_doc_counts.sql` - Compare document counts across different filters
- `radiation_documents_with_dates.sql` - Find documents with valid dates

**Key Finding**: Documents use `content.attachment.creation` for dates, not `date` field

### Unified Episodes Testing

#### `test_unified_episodes.sql`
**Purpose**: Test the unified v_radiation_episodes view combining all stages

**Key Features**:
- Tests episode_start_date derivation (earliest date across all stages)
- Validates episode_end_date (latest appointment or today)
- Checks episode_duration_days calculation
- Tests stage counts (appointments, observations, documents, care plans)
- Validates laterality aggregation
- Tests total dose calculations
- Checks source type distributions

**Expected Results**: Complete episodes with all stages unified, proper date ranges, dose totals

### Appointment Analysis

#### `test_appointment_enrichment.sql`
**Purpose**: Test appointment data enrichment with additional context

**Key Features**:
- Tests appointment type classification
- Validates department/location linkage
- Checks practitioner/provider information
- Tests service type codes

#### `analyze_appointment_patterns.sql`
**Purpose**: Analyze patterns in appointment data

#### `analyze_appointment_patterns_fixed.sql`
**Purpose**: Corrected version of pattern analysis

**Key Features**:
- Appointment frequency by department
- Service category distribution
- Status distribution
- Temporal patterns (by month/year)

### Data Enrichment

#### `test_enrichment.sql`
**Purpose**: Test overall data enrichment logic across multiple views

**Key Features**:
- Tests cross-view joins
- Validates data quality metrics
- Checks completeness of enrichment
- Tests derived fields

### Deployment Files

#### `deploy_radiation_appointments_4layer_fixed.sql`
**Purpose**: Final deployment version of multi-layer radiation episode views

**Key Features**:
- Complete CREATE OR REPLACE VIEW statements
- All 4 stages + unified view
- Corrected datetime handling
- Production-ready filtering logic

**Note**: This represents a milestone version used for deployment. Current production views are in `athena_views/views/`.

## Workflow

### Stage-by-Stage Testing
```bash
# Test each stage independently
../surgical_procedures_assessment/run_query.sh test_stage_1a_clean.sql
../surgical_procedures_assessment/run_query.sh test_stage_1b_clean.sql
../surgical_procedures_assessment/run_query.sh test_stage_1c_revised_fixed.sql
../surgical_procedures_assessment/run_query.sh test_stage_1d_documents.sql
```

### Unified Testing
```bash
# Test the complete unified view
../surgical_procedures_assessment/run_query.sh test_unified_episodes.sql
```

### Pattern Analysis
```bash
# Analyze appointment patterns
../surgical_procedures_assessment/run_query.sh analyze_appointment_patterns_fixed.sql
```

## Key Findings

### Datetime Handling Challenges
**Issue**: FHIR datetime fields stored as VARCHAR, need casting to TIMESTAMP

**Solution**: Standardized datetime parsing pattern:
```sql
CAST(field_name AS TIMESTAMP) as standardized_datetime
```

**Common Pitfall**: NULLs and timezone formatting require careful handling

### Document Date Discovery
**Issue**: Initial assumption was `date` field contained document dates

**Finding**: Most radiation documents use `content.attachment.creation` instead

**Impact**: Required updating v_radiation_documents CTE to use correct field

### Appointment Status Filtering
**Issue**: Many appointment statuses to consider (booked, arrived, fulfilled, cancelled, etc.)

**Solution**: Focus on statuses indicating actual treatment delivery:
- booked
- arrived
- fulfilled
- checked-in

**Excluded**: cancelled, noshow, entered-in-error

### Stage Combination Logic
**Challenge**: How to combine 4 different data sources into unified episodes

**Solution**: Multi-stage CTE approach:
1. Extract each stage independently with standardized fields
2. UNION ALL stages together
3. Group by patient + encounter to create episodes
4. Derive episode dates from MIN/MAX across all stages

### Data Completeness

**By Stage** (approximate):
- Stage 1a (Observations): ~45,000 dose observations
- Stage 1b (Care Plans): ~2,800 treatment plans
- Stage 1c (Appointments): ~85,000 appointment records
- Stage 1d (Documents): ~1,200 treatment documents

**Episodes**: ~2,800-3,000 unique radiation treatment episodes

## Common Patterns Discovered

### 1. Datetime Standardization Pattern
```sql
-- Extract datetime from various FHIR fields
CAST(observation.effective_datetime AS TIMESTAMP) as observation_datetime,
CAST(appointment.start AS TIMESTAMP) as appointment_datetime,
CAST(careplan.period.start AS TIMESTAMP) as careplan_datetime,
CAST(document.content.attachment.creation AS TIMESTAMP) as document_datetime
```

### 2. Episode Date Derivation Pattern
```sql
-- Find earliest and latest dates across all stages
MIN(COALESCE(observation_date, appointment_date, careplan_date, document_date)) as episode_start_date,
MAX(COALESCE(appointment_date, observation_date, document_date, careplan_date)) as episode_end_date
```

### 3. Multi-Stage UNION Pattern
```sql
WITH
stage_1a AS (SELECT patient_id, date, 'observation' as source FROM ...),
stage_1b AS (SELECT patient_id, date, 'careplan' as source FROM ...),
stage_1c AS (SELECT patient_id, date, 'appointment' as source FROM ...),
stage_1d AS (SELECT patient_id, date, 'document' as source FROM ...)

SELECT * FROM stage_1a
UNION ALL
SELECT * FROM stage_1b
UNION ALL
SELECT * FROM stage_1c
UNION ALL
SELECT * FROM stage_1d
```

## Related Files

### Production Views
- `athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql` - Production radiation episode views
- `athena_views/views/v_radiation_episodes.sql` - Main unified episodes view (if separate)

### Documentation
- Project documentation may contain radiation episode design docs
- Treatment flow diagrams
- FHIR resource mapping documentation

## Lessons Learned

### 1. Always Test Datetime Parsing First
Before building complex views, validate that datetime fields can be properly cast and parsed.

### 2. Investigate Data Availability by Stage
Different FHIR resources have different field availability. Test each stage independently before unifying.

### 3. Handle NULLs Explicitly
Use COALESCE aggressively when deriving dates across multiple sources.

### 4. Validate Against Expected Volumes
Know approximate expected volumes per stage to catch filtering errors early.

### 5. Iterate on Stage Logic
Build each stage independently, test thoroughly, then unify. Don't try to build everything at once.

### 6. Document Date Field Discovery
When field names are unclear, run investigation queries to find where dates actually live.

## Next Steps

To extend or modify radiation episode logic:
1. Start by running relevant test queries to understand current behavior
2. Modify stage-specific test files to prototype changes
3. Validate changes with test queries
4. Update production views in `athena_views/views/`
5. Document changes and re-run validation

## Test Query Templates

These files serve as templates for:
- Testing new FHIR resource extraction
- Validating datetime parsing approaches
- Prototyping multi-stage data unification
- Investigating data quality issues

Use them as starting points for new view development!
