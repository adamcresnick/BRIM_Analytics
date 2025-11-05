# Orchestrator Reasoning Engine

## Overview

This module transforms the clinical timeline extraction orchestrator from a passive coordinator into an **active reasoning agent** that ensures 100% extraction completeness by:

- **Validating** extraction against all available FHIR resources
- **Investigating** query failures and data quality issues
- **Applying** WHO 2021 CNS clinical knowledge for validation
- **Iteratively problem-solving** with MedGemma until perfection

## The Problem This Solves

**User's Original Concern:**
> "I am surprised that during the steps of the orchestrator working with medgemma, the orchestrator is not identifying all the issues we just worked through. We need the orchestrator to truly be a reasoning agent informed by the standard of care context provided and to truly problem solve for medgemma in a comprehensive way given the diversity of patients and patient data resources we'll encounter."

**The Date Parsing Error Example:**

The orchestrator failed to catch the date parsing error (`INVALID_FUNCTION_ARGUMENT: Invalid format: '2018-08-07' is too short`) that required 2+ hours of manual debugging. With the reasoning engine, this error would have been:
1. **Detected** automatically
2. **Investigated** by sampling actual field values
3. **Diagnosed** as mixed date formats
4. **Fixed** with the COALESCE(TRY...) pattern
5. **Auto-deployed** (if confidence > 0.8)

## Architecture Components

### ✅ COMPLETED: schema_loader.py

**Purpose**: Load and query the complete Athena FHIR schema for schema awareness

**Key Capabilities**:
- Loads Athena_Schema_1103b2025.csv into queryable structure
- Finds tables by column patterns
- Identifies all patient reference tables
- Generates dynamic COUNT queries for any table
- Generates sample queries for data quality investigation
- Identifies date columns automatically

**Example Usage**:
```python
from orchestration.schema_loader import AthenaSchemaLoader

loader = AthenaSchemaLoader('path/to/Athena_Schema_1103b2025.csv')

# Find all tables with patient data
patient_tables = loader.find_patient_reference_tables()
# Returns: ['encounter', 'procedure', 'observation', ...]

# Generate count query
query = loader.generate_count_query('encounter', 'patient123')
# Returns: SELECT COUNT(*) FROM fhir_prd_db.encounter WHERE...

# Identify date columns
date_cols = loader.identify_date_columns('encounter')
# Returns: ['period_start', 'period_end', 'recorded_date', ...]
```

### ✅ COMPLETED: investigation_engine.py

**Purpose**: Investigate Athena query failures and propose automated fixes

**Key Capabilities**:
1. **Error Classification** - Pattern match error types (INVALID_FUNCTION_ARGUMENT, SYNTAX_ERROR, etc.)
2. **Data Format Analysis** - Sample actual field values from source tables
3. **Fix Generation** - Generate SQL fixes for common issues (multi-format dates, type conversions, NULL handling)
4. **Root Cause Analysis** - Deep dive into WHY failures occur with confidence scores

**Example Usage - Date Parsing Error**:
```python
from orchestration.investigation_engine import InvestigationEngine

engine = InvestigationEngine(athena_client, schema_loader)

# Simulate the date parsing error
investigation = engine.investigate_query_failure(
    query_id='abc123',
    query_string="SELECT date_parse(e.period_start, '%Y-%m-%dT%H:%i:%sZ') FROM encounter e",
    error_message='INVALID_FUNCTION_ARGUMENT: Invalid format: "2018-08-07" is too short'
)

print(investigation)
# {
#     'root_cause': "Field 'e.period_start' contains multiple date formats: ['YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SSZ']",
#     'affected_fields': ['e.period_start'],
#     'sample_data': {'e.period_start': ['2018-08-07', '2018-08-07T10:30:00Z', ...]},
#     'proposed_fix': 'COALESCE(\n    TRY(date_parse(e.period_start, \'%Y-%m-%dT%H:%i:%sZ\')),\n    TRY(date_parse(e.period_start, \'%Y-%m-%d\'))\n)',
#     'confidence': 0.9,
#     'auto_fixable': True
# }
```

**How It Works - Date Error Investigation**:

1. **Error Detection**: Identifies `INVALID_FUNCTION_ARGUMENT` with value "2018-08-07 is too short"
2. **Field Identification**: Parses query to find `date_parse(e.period_start, ...)`
3. **Table Extraction**: Identifies table `encounter` from alias `e`
4. **Data Sampling**: Queries `SELECT DISTINCT period_start FROM encounter LIMIT 20`
5. **Format Analysis**: Discovers mix of "2018-08-07" and "2018-08-07T10:30:00Z"
6. **Fix Generation**: Creates COALESCE with TRY for both formats
7. **Confidence Scoring**: Returns 0.9 confidence (auto-fixable)

### 📋 TODO: who_cns_knowledge_base.py

**Purpose**: Parse WHO 2021 CNS Classification for clinical reasoning

**Planned Capabilities**:
- Load WHO markdown document into structured knowledge base
- Extract tumor classifications by age/location
- Extract molecular markers and grading rules
- Build nomenclature translation map (old → new terms)
- Validate diagnoses against WHO 2021 criteria
- Identify missing molecular tests for definitive diagnosis
- Flag when "NOS" or "NEC" suffixes should be applied

**Example Usage** (planned):
```python
from orchestration.who_cns_knowledge_base import WHOCNSKnowledgeBase

kb = WHOCNSKnowledgeBase('path/to/WHO 2021 CNS Tumor Classification.md')

# Validate diagnosis
validation = kb.validate_diagnosis(
    diagnosis='Glioblastoma, IDH-wildtype',
    patient_age=5,  # Pediatric
    tumor_location='frontal lobe'
)
# Returns: {
#     'valid': False,
#     'reason': 'Glioblastoma, IDH-wildtype is an adult-type glioma; uncommon in pediatric patients',
#     'suggested_diagnosis': 'Diffuse hemispheric glioma, H3 G34-mutant (pediatric-type)',
#     'required_tests': ['H3 K27 status', 'H3 G34 status', 'IDH status']
# }
```

### 📋 TODO: reasoning_engine.py

**Purpose**: Core orchestration loop with active reasoning and completeness validation

**Main Orchestration Loop** (planned):
```python
from orchestration.reasoning_engine import OrchestratorReasoningEngine

reasoning_engine = OrchestratorReasoningEngine(
    athena_client=athena_client,
    schema_loader=schema_loader,
    investigation_engine=investigation_engine,
    who_cns_kb=who_cns_kb,
    medgemma_agent=medgemma_agent
)

# Run iterative extraction with reasoning
timeline = reasoning_engine.iterative_extraction_loop(
    patient_id='test-patient-123',
    max_iterations=3
)
```

**Key Capabilities** (planned):
1. **Completeness Validation**: Compare extracted resources vs. raw FHIR counts
2. **Failure Investigation**: Auto-investigate and fix query failures
3. **Gap Analysis**: Identify missing resources and investigate why
4. **Iterative Loop**: Work with MedGemma until 100% complete

## Foundational Documents

The reasoning engine is informed by three key documents:

1. **Athena_Schema_1103b2025.csv**
   `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv`
   Complete FHIR schema - ALL tables, columns, data types

2. **WHO 2021 CNS Tumor Classification.md**
   `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO 2021 CNS Tumor Classification.md`
   Clinical standard of care with diagnostic criteria, molecular markers, grading rules

3. **Comprehensive Pediatric CNS Tumor Reference.html**
   `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).html`
   Treatment paradigms and protocols

## Integration

### How to Integrate into patient_timeline_abstraction_V3.py

```python
# At top of file
from orchestration.schema_loader import AthenaSchemaLoader
from orchestration.investigation_engine import InvestigationEngine
# from orchestration.who_cns_knowledge_base import WHOCNSKnowledgeBase  # TODO
# from orchestration.reasoning_engine import OrchestratorReasoningEngine  # TODO

# In main() or __init__
schema_loader = AthenaSchemaLoader(
    '/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv'
)

investigation_engine = InvestigationEngine(athena_client, schema_loader)

# Hook into Athena query execution
# Modify _execute_athena_query() to use investigation engine on failures:

def _execute_athena_query(self, query, description=None):
    # ... existing code ...

    if status in ['FAILED', 'CANCELLED']:
        # NEW: Investigate the failure
        investigation = self.investigation_engine.investigate_query_failure(
            query_id=query_id,
            query_string=query,
            error_message=reason
        )

        if investigation['auto_fixable']:
            logger.info(f"AUTO-FIXABLE: {investigation['proposed_fix']}")
            # Could automatically apply fix here or log for review

        logger.error(f"Investigation: {investigation['root_cause']}")
        return []
```

## Testing

### Test 1: Date Parsing Error Investigation

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/orchestration

python3 investigation_engine.py
```

Expected output:
```
Testing investigation engine with date parsing error...

Root Cause: Field 'e.period_start' contains multiple date formats: ['YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SSZ']
Confidence: 0.9
Auto-fixable: True

Proposed Fix:
COALESCE(
    TRY(date_parse(e.period_start, '%Y-%m-%dT%H:%i:%sZ')),
    TRY(date_parse(e.period_start, '%Y-%m-%d'))
)
```

## Success Criteria

- ✅ **Schema Awareness**: Can query any table in Athena schema dynamically
- ✅ **Failure Investigation**: Automatically diagnoses and proposes fixes for query failures
- ⏳ **Clinical Reasoning**: Validates extractions against WHO 2021 CNS criteria
- ⏳ **Completeness Validation**: Ensures 100% of available FHIR resources are extracted
- ⏳ **Iterative Problem-Solving**: Loops with MedGemma until extraction is complete
- ⏳ **No Manual Intervention**: Date error (and similar issues) resolved automatically

## Next Steps

1. **Complete who_cns_knowledge_base.py** - WHO 2021 parser and validator
2. **Build reasoning_engine.py** - Main orchestration loop with completeness validation
3. **Integrate** - Wire into patient_timeline_abstraction_V3.py
4. **Test End-to-End** - Run on real patient data and verify auto-fixes work
5. **Deploy** - Production deployment with monitoring

## Files

```
orchestration/
├── __init__.py                      # Module initialization
├── README.md                         # This file
├── IMPLEMENTATION_PLAN.md            # Detailed implementation plan
├── schema_loader.py                  # ✅ COMPLETE - Athena schema awareness
├── investigation_engine.py           # ✅ COMPLETE - Failure investigation & fixes
├── who_cns_knowledge_base.py         # 📋 TODO - WHO 2021 CNS clinical knowledge
└── reasoning_engine.py               # 📋 TODO - Core orchestration loop
```

## License

Proprietary - CHOP BRIM Analytics
