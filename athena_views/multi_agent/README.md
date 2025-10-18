# Multi-Agent Framework for Athena-Based Data Abstraction

## Overview

This multi-agent framework enables scalable clinical data abstraction by combining:
- **Direct Athena queries** for structured data (demographics, medications, procedures)
- **Multi-agent orchestration** for complex field extraction
- **Cross-source validation** for accuracy and confidence scoring
- **Data dictionary compliance** for all 345 CBTN fields

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Master Orchestrator (Claude Sonnet 4.5)           │
│  • Field classification (STRUCTURED/HYBRID/DOCUMENT)        │
│  • Extraction strategy planning                             │
│  • Agent coordination                                       │
│  • Conflict adjudication                                    │
│  • Data dictionary enforcement                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
┌──────────────────────────┐   ┌──────────────────────────┐
│  Athena Query Agent      │   │ Medical Reasoning Agent  │
│  • 15 view queries       │   │ • Document extraction    │
│  • Validation data       │   │ • Clinical reasoning     │
│  • Temporal alignment    │   │ • LLM-based abstraction  │
└──────────────────────────┘   └──────────────────────────┘
              ↓                           ↓
              └─────────────┬─────────────┘
                            ↓
              ┌─────────────────────────────┐
              │   Validation Agent          │
              │  • Cross-source validation  │
              │  • Confidence scoring       │
              │  • Data dict compliance     │
              └─────────────────────────────┘
```

## Components

### 1. AthenaQueryAgent (`athena_query_agent.py`)

SQL query engine for AWS Athena with 15 standardized view queries:

**Core Clinical Views (9 queries):**
- `query_patient_demographics()` - Gender, DOB, race, ethnicity
- `query_diagnoses()` - Problem list diagnoses with ICD-10/SNOMED
- `query_procedures()` - Surgeries and procedures with CPT codes
- `query_medications()` - Medication requests with RxNorm codes
- `query_imaging()` - MRI/CT/PET studies with reports
- `query_encounters()` - Patient encounters and visits
- `query_measurements()` - Lab results and vital signs
- `query_binary_files()` - Document references
- `query_molecular_tests()` - Genetic/molecular test results

**Radiation Oncology Views (6 queries):**
- `query_radiation_appointments()` - RT appointments
- `query_radiation_courses()` - RT treatment courses
- `query_radiation_care_plans()` - RT care plan notes
- `query_radiation_service_requests()` - RT service requests

**Example Usage:**
```python
from athena_query_agent import AthenaQueryAgent

agent = AthenaQueryAgent(
    database='fhir_prd_db',
    output_location='s3://your-athena-results-bucket/',
    region='us-east-1'
)

# Query demographics
demographics = agent.query_patient_demographics('e4BwD8ZYDBccepXcJ.Ilo3w3')
# Returns: {'pd_gender': 'female', 'pd_birth_date': '2005-05-13T00:00:00Z', ...}

# Query surgeries
surgeries = agent.query_procedures('e4BwD8ZYDBccepXcJ.Ilo3w3', procedure_type='surgical')
# Returns: [{'procedure_date': '2018-05-28', 'proc_code_text': 'Craniotomy', ...}, ...]

# Get patient timeline
timeline = agent.get_patient_timeline('e4BwD8ZYDBccepXcJ.Ilo3w3')
# Returns chronological list of all events (birth, diagnosis, procedures, meds)
```

### 2. MasterOrchestrator (`master_orchestrator.py`)

Coordinates multi-agent extraction workflow:

**Field Classification:**
- **STRUCTURED_ONLY** (30%): Direct Athena query (gender, DOB, meds)
- **HYBRID** (50%): Athena validation + document extraction (diagnosis, surgeries)
- **DOCUMENT_ONLY** (20%): Document extraction only (clinical status, imaging findings)

**Example Usage:**
```python
from athena_query_agent import AthenaQueryAgent
from master_orchestrator import MasterOrchestrator

athena_agent = AthenaQueryAgent(...)
orchestrator = MasterOrchestrator(athena_agent=athena_agent)

# Extract single field
gender = orchestrator.extract_field('e4BwD8ZYDBccepXcJ.Ilo3w3', 'patient_gender')
# Returns: {'field': 'patient_gender', 'value': 'female', 'confidence': 1.0, ...}

# Extract all fields
results = orchestrator.extract_all_fields('e4BwD8ZYDBccepXcJ.Ilo3w3')
# Returns: Complete extraction with dialogue history

# Get extraction summary
summary = orchestrator.get_extraction_summary('e4BwD8ZYDBccepXcJ.Ilo3w3')
# Returns: Confidence distribution statistics
```

## Field Mappings

### STRUCTURED_ONLY Fields (Direct Athena Query)

| Field | Athena View | Column | Confidence |
|-------|-------------|--------|------------|
| patient_gender | v_patient_demographics | pd_gender | 1.0 |
| date_of_birth | v_patient_demographics | pd_birth_date | 1.0 |
| race | v_patient_demographics | pd_race | 1.0 |
| ethnicity | v_patient_demographics | pd_ethnicity | 1.0 |
| chemotherapy_agent | v_medications | medication_name | 1.0 |
| chemotherapy_start_date | v_medications | medication_start_date | 1.0 |
| chemotherapy_status | v_medications | mr_status | 1.0 |

### HYBRID Fields (Athena Validation + Document Extraction)

| Field | Athena View | Document Sources | Validation |
|-------|-------------|------------------|------------|
| primary_diagnosis | v_problem_list_diagnoses | Pathology reports | ICD-10 match |
| diagnosis_date | v_problem_list_diagnoses | Pathology, Clinical notes | Date proximity ±30d |
| who_grade | v_problem_list_diagnoses | Pathology reports | Dropdown (1-4) |
| tumor_location | v_procedures | Operative notes, Imaging | 24 anatomical options |
| extent_of_resection | v_procedures | Operative notes | 5 resection types, date ±7d |
| surgery_date | v_procedures | Operative notes | Exact date match |
| surgery_type | v_procedures | Operative notes | 5 surgery types |
| radiation_dose | v_radiation_treatment_courses | RT notes | Numeric tolerance 10% |

### DOCUMENT_ONLY Fields (Free-Text Extraction)

| Field | Document Sources | Confidence |
|-------|------------------|------------|
| clinical_status | Progress notes, Oncology notes | 0.75 |
| imaging_findings | Radiology reports | 0.70 |
| tumor_size | Radiology reports, Pathology | 0.75 |
| pathology_notes | Pathology reports | 0.70 |

## Installation

```bash
# Install dependencies
pip install boto3 pandas pyyaml

# Configure AWS credentials
aws configure
```

## Configuration

Edit [`../config/athena_connection.yaml`](../config/athena_connection.yaml):

```yaml
aws:
  region: us-east-1

athena:
  database: fhir_prd_db
  output_location: s3://your-athena-results-bucket/
  max_wait_time: 300
```

## Usage Examples

### Example 1: Extract Demographics (STRUCTURED_ONLY)

```python
from athena_query_agent import AthenaQueryAgent
from master_orchestrator import MasterOrchestrator

# Initialize
athena_agent = AthenaQueryAgent(database='fhir_prd_db', ...)
orchestrator = MasterOrchestrator(athena_agent=athena_agent)

# Extract
patient_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
gender = orchestrator.extract_field(patient_id, 'patient_gender')

print(f"Gender: {gender['value']}, Confidence: {gender['confidence']}")
# Output: Gender: female, Confidence: 1.0
```

### Example 2: Extract Extent of Resection (HYBRID)

```python
# HYBRID field uses Athena for surgery dates + documents for extent details
resection = orchestrator.extract_field(patient_id, 'extent_of_resection')

print(f"Resection: {resection['value']}")
print(f"Confidence: {resection['confidence']}")
print(f"Validation: {resection['validation_status']}")

# Output:
# Resection: ['Gross total resection', 'Partial resection']
# Confidence: 0.95
# Validation: validated
```

### Example 3: Extract All Fields

```python
# Extract specific fields
fields = ['patient_gender', 'date_of_birth', 'primary_diagnosis', 'extent_of_resection']
results = orchestrator.extract_all_fields(patient_id, field_list=fields)

# View dialogue history
for dialogue in results['dialogue_history']:
    print(f"{dialogue['agent']}: {dialogue['message']}")

# Get summary
summary = orchestrator.get_extraction_summary(patient_id)
print(f"High confidence extractions: {summary['high_confidence']}")
```

## Confidence Scoring

| Range | Interpretation | Criteria |
|-------|---------------|----------|
| 0.95-1.0 | Very High | Structured data + document validated |
| 0.85-0.94 | High | Structured OR document source validated |
| 0.70-0.84 | Medium | Single source, no validation available |
| 0.60-0.69 | Low-Medium | Partial validation, needs review |
| 0.40-0.59 | Low | Sources conflict, manual review needed |
| 0.0-0.39 | Very Low | Contradictory data, extraction failed |

## Validation Rules

### Date Proximity Validation
```python
# Validates document date is within tolerance of Athena date
date_proximity: 7  # days tolerance
# Example: Surgery 2018-05-28 in Athena, operative note 2018-05-29 → PASS (±7d)
```

### Dropdown Match Validation
```python
# Validates extracted value matches data dictionary options
dropdown_match: ['Gross total resection', 'Near total resection', ...]
# Example: Extracted "Gross total resection" → PASS (in list)
```

### ICD-10/SNOMED Match Validation
```python
# Validates diagnosis matches coding systems
icd10_match: true
snomed_match: true
# Example: "Pilocytic astrocytoma" matches ICD-10 D33.1 → PASS
```

## Next Steps

### Phase 1: Current Implementation ✅
- [x] AthenaQueryAgent with 15 view queries
- [x] MasterOrchestrator with field classification
- [x] STRUCTURED_ONLY field extraction
- [x] HYBRID field extraction (Athena validation only)
- [x] Configuration and documentation

### Phase 2: Medical Reasoning Agent (Pending)
- [ ] Implement Medical Reasoning Agent for document extraction
- [ ] Integrate with MedGemma 27B or Claude for clinical text analysis
- [ ] Complete HYBRID field extraction (with document content)
- [ ] Complete DOCUMENT_ONLY field extraction

### Phase 3: Validation & Testing (Pending)
- [ ] Test on pilot patient e4BwD8ZYDBccepXcJ.Ilo3w3
- [ ] Validate against CBTN gold standard
- [ ] Measure accuracy, confidence distribution
- [ ] Optimize dialogue efficiency

### Phase 4: Production Deployment (Pending)
- [ ] Cohort extraction capability
- [ ] Performance optimization
- [ ] Error handling and retry logic
- [ ] Comprehensive audit trail logging

## Related Documentation

- [Architecture Overview](../ATHENA_BASED_MULTI_AGENT_ARCHITECTURE.md) - Complete system design
- [Athena Views Documentation](../views/README.md) - 15 SQL view definitions
- [Patient Workflows](../patient_workflows/README.md) - End-to-end extraction workflows

## Support

For questions or issues:
- Review [Architecture Documentation](../ATHENA_BASED_MULTI_AGENT_ARCHITECTURE.md)
- Check [Athena View Fixes](../documentation/ATHENA_VIEW_FIXES.md)
- See [Project Organization Guide](../../PROJECT_ORGANIZATION_GUIDE.md)
