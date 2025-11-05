# Orchestrator Reasoning Engine Implementation Plan

## Overview
Transform the orchestrator from a passive coordinator into an active reasoning agent that ensures 100% extraction completeness by:
- Validating extraction against available FHIR resources
- Investigating query failures and data quality issues
- Applying WHO 2021 CNS clinical knowledge
- Iteratively problem-solving with MedGemma

## Foundational Documents
1. `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv` - Complete FHIR schema
2. `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO 2021 CNS Tumor Classification.md` - Clinical standard of care
3. `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).html` - Treatment paradigms

## Architecture Components

### ✅ COMPLETED: schema_loader.py
**Purpose**: Load and query Athena FHIR schema for schema awareness

**Capabilities**:
- Load complete schema from CSV into queryable structure
- Find tables by column patterns
- Identify patient reference tables
- Generate dynamic COUNT queries for any table
- Generate sample queries for data quality investigation
- Identify date columns in any table

**Key Methods**:
- `get_table_schema(table_name)` - Get schema for specific table
- `find_patient_reference_tables()` - Find all tables with patient data
- `generate_count_query(table, patient_id)` - Dynamic resource counting
- `generate_sample_query(table, column)` - Sample values for investigation
- `identify_date_columns(table)` - Find potential date fields

### 🔨 IN PROGRESS: investigation_engine.py
**Purpose**: Investigate Athena query failures and data quality issues

**Capabilities Needed**:
1. **Error Classification**
   - Pattern match error types (INVALID_FUNCTION_ARGUMENT, SYNTAX_ERROR, etc.)
   - Extract problematic values from error messages
   - Identify affected fields and tables

2. **Data Format Analysis**
   - Sample actual field values from source tables
   - Analyze format patterns (date formats, data types, etc.)
   - Detect mixed formats causing errors

3. **Fix Generation**
   - Generate SQL fixes for common issues
   - Multi-format date handling (COALESCE with TRY)
   - Type conversion fixes
   - NULL handling

4. **Root Cause Analysis**
   - Deep dive into WHY failures occur
   - Cross-reference with schema
   - Provide confidence scores

**Example - Date Error Investigation**:
```python
# Error: "INVALID_FUNCTION_ARGUMENT: Invalid format: '2018-08-07' is too short"

investigation = engine.investigate_query_failure(
    query_id="abc123",
    query_string="SELECT date_parse(e.period_start, '%Y-%m-%dT%H:%i:%sZ')...",
    error_message="INVALID_FUNCTION_ARGUMENT: Invalid format: '2018-08-07' is too short"
)

# Returns:
{
    'root_cause': "Field 'e.period_start' contains multiple date formats",
    'affected_fields': ['e.period_start'],
    'sample_data': ['2018-08-07', '2018-08-07T10:30:00Z', ...],
    'format_analysis': {
        'has_multiple_formats': True,
        'formats': ['YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SSZ']
    },
    'proposed_fix': "COALESCE(TRY(date_parse(...'%Y-%m-%dT%H:%i:%sZ')), TRY(date_parse(...'%Y-%m-%d')))",
    'confidence': 0.9
}
```

### 📋 TODO: who_cns_knowledge_base.py
**Purpose**: Parse WHO 2021 CNS Classification for clinical reasoning

**Capabilities Needed**:
1. **Knowledge Base Loading**
   - Parse WHO markdown document into structured KB
   - Extract tumor classifications by age/location
   - Extract molecular markers and grading rules
   - Build nomenclature translation map (old → new terms)

2. **Diagnosis Validation**
   - Validate diagnosis against WHO 2021 criteria
   - Check age-appropriateness (pediatric vs adult)
   - Check location-appropriateness
   - Identify required molecular markers

3. **Completeness Checking**
   - Identify missing molecular tests for definitive diagnosis
   - Flag when "NOS" (Not Otherwise Specified) should be applied
   - Flag when "NEC" (Not Elsewhere Classified) should be applied

**Key WHO Principles to Implement**:
- Age + Location = Primary sorting key for gliomas
- Molecular markers can override histological grade
- Specific grading triggers (CDKN2A/B deletion → Grade 4, etc.)

### 📋 TODO: reasoning_engine.py
**Purpose**: Core orchestrator with active reasoning loop

**Main Orchestration Loop**:
```python
def iterative_extraction_loop(patient_id, max_iterations=3):
    for iteration in range(max_iterations):
        # 1. Run MedGemma extraction
        timeline = medgemma_agent.extract_timeline(patient_id)

        # 2. Validate completeness against raw FHIR
        validation = validate_extraction_completeness(patient_id, timeline)

        # 3. Investigate any query failures
        if has_query_failures():
            for failure in get_query_failures():
                investigation = investigate_query_failure(...)
                if investigation['confidence'] > 0.8:
                    auto_apply_fix(investigation)

        # 4. Check if 100% complete
        if validation['coverage_pct'] == 100 and not has_query_failures():
            return timeline  # Success!

        # 5. Generate targeted guidance for MedGemma
        guidance = generate_medgemma_guidance(validation)
        medgemma_agent.update_strategy(guidance)
```

**Completeness Validation**:
```python
def validate_extraction_completeness(patient_id, extracted_timeline):
    # 1. Query raw FHIR resource counts using schema_loader
    raw_counts = {}
    for table in schema_loader.find_patient_reference_tables():
        query = schema_loader.generate_count_query(table, patient_id)
        count = execute_athena_query(query)
        raw_counts[table] = count

    # 2. Count extracted resources from timeline
    extracted_counts = count_extracted_resources(extracted_timeline)

    # 3. Identify gaps
    gaps = []
    for resource_type, expected in raw_counts.items():
        actual = extracted_counts.get(resource_type, 0)
        if actual < expected:
            gaps.append({
                'resource': resource_type,
                'expected': expected,
                'actual': actual,
                'gap': expected - actual
            })

    # 4. Investigate gaps
    for gap in gaps:
        root_cause = investigate_extraction_gap(patient_id, gap)
        # Generate specific guidance for MedGemma

    return validation_report
```

## Integration Plan

### Step 1: Wire Up Existing Components
Add to `patient_timeline_abstraction_V3.py`:

```python
from orchestration.schema_loader import AthenaSchemaLoader
from orchestration.investigation_engine import InvestigationEngine
from orchestration.reasoning_engine import OrchestratorReasoningEngine

# Initialize reasoning engine
schema_loader = AthenaSchemaLoader(
    '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv'
)

investigation_engine = InvestigationEngine(athena_client, schema_loader)

reasoning_engine = OrchestratorReasoningEngine(
    athena_client=athena_client,
    schema_loader=schema_loader,
    investigation_engine=investigation_engine,
    who_cns_kb_path='...',
    medgemma_agent=medgemma_agent
)

# Replace simple extraction with reasoning loop
timeline = reasoning_engine.iterative_extraction_loop(patient_id)
```

### Step 2: Test with Date Error Scenario
Run the orchestrator on a patient that triggers the date parsing error.

**Expected Behavior**:
1. Query fails with date format error
2. `investigation_engine.investigate_query_failure()` is called
3. Identifies `e.period_start` has mixed formats
4. Generates COALESCE fix
5. Either auto-applies or logs for manual review
6. Retry succeeds

### Step 3: Test with Missing Resource Scenario
Run on a patient with incomplete extraction.

**Expected Behavior**:
1. MedGemma extracts partial timeline
2. `validate_extraction_completeness()` identifies gaps
3. Investigation queries raw FHIR to find missing resources
4. Generates targeted guidance for MedGemma
5. MedGemma re-runs with new strategy
6. Achieves 100% coverage

## Success Criteria

1. ✅ **Schema Awareness**: Can query any table in Athena schema dynamically
2. 🔨 **Failure Investigation**: Automatically diagnoses and proposes fixes for query failures
3. ⏳ **Clinical Reasoning**: Validates extractions against WHO 2021 CNS criteria
4. ⏳ **Completeness Validation**: Ensures 100% of available FHIR resources are extracted
5. ⏳ **Iterative Problem-Solving**: Loops with MedGemma until extraction is complete
6. ⏳ **No Manual Intervention**: Date error (and similar issues) resolved automatically

## Next Steps

1. Complete `investigation_engine.py` with date format analysis
2. Create `who_cns_knowledge_base.py` with WHO 2021 parser
3. Build `reasoning_engine.py` with main orchestration loop
4. Integrate into `patient_timeline_abstraction_V3.py`
5. Test end-to-end with real patient data
