# Athena-Based Multi-Agent Data Abstraction Architecture
**Date**: October 17, 2025
**Branch**: feature/multi-agent-framework
**Purpose**: Replace CSV-based extraction with scalable Athena view queries for multi-agent clinical data abstraction

---

## Executive Summary

This architecture replaces the previous Python CSV extraction workflow with a **direct Athena query approach**, enabling:

1. **Scalable extraction** - Query entire cohort, not just single patients
2. **Real-time validation** - Cross-check document extraction against structured Athena data
3. **Multi-agent orchestration** - Master agent coordinates Athena queries + document extraction + validation
4. **Data dictionary compliance** - All 345 CBTN fields mapped to Athena views or document sources

---

## Key Paradigm Shift

### Previous Approach (Python CSV)
```
Python scripts → CSV files (per patient) → LLM reads CSVs → Extract data
❌ Single patient at a time
❌ File-based staging required
❌ No real-time validation
```

### New Approach (Athena Queries)
```
15 Athena views → Patient-specific SQL queries → Multi-agent orchestration → Validated abstraction
✅ Scalable to entire cohort
✅ Real-time cross-source validation
✅ Direct query capability during extraction
```

---

## Architecture Components

### 1. Master Orchestrator Agent (Claude Sonnet 4.5)

**Responsibilities:**
- Receives data dictionary field definitions (345 CBTN fields)
- Classifies fields: Structured-only vs. Hybrid vs. Document-only
- Plans extraction strategy per field
- Coordinates Athena Query Agent + Medical Reasoning Agent
- Adjudicates conflicts between sources
- Validates against data dictionary constraints (dropdowns, ranges)
- Produces final abstracted output with confidence scores

**Key Capabilities:**
- Data dictionary enforcement (valid values, types)
- Temporal reasoning (age calculations, date sequences)
- Conflict resolution (structured data contradicts document)
- Audit trail generation (all agent dialogue logged)

---

### 2. Athena Query Agent (Automated SQL Engine)

**Responsibilities:**
- Executes patient-specific queries against 15 Athena views
- Returns structured data for validation
- Provides temporal alignment (surgery dates, medication timelines)
- Enables cross-source verification

**Available Query Functions:**

```python
# Core Clinical Views (9 queries)
QUERY_PATIENT_DEMOGRAPHICS(patient_fhir_id)
  # Returns: gender, birth_date, race, ethnicity, age_years

QUERY_DIAGNOSES(patient_fhir_id, date_range=None)
  # Returns: diagnosis_name, onset_date, icd10_code, snomed_code

QUERY_PROCEDURES(patient_fhir_id, procedure_type=None)
  # Returns: procedure_date, procedure_name, CPT codes, surgical keywords

QUERY_MEDICATIONS(patient_fhir_id, medication_name=None, date_range=None)
  # Returns: medication_name, start_date, end_date, status, RxNorm codes

QUERY_IMAGING(patient_fhir_id, modality=None, date_range=None)
  # Returns: imaging_date, modality, result_information, age_at_imaging

QUERY_MOLECULAR_TESTS(patient_fhir_id)
  # Returns: test_date, test_name, components, specimen info

QUERY_MEASUREMENTS(patient_fhir_id, measurement_type=None)
  # Returns: measurement_type, value, unit, date, source (observation vs lab)

QUERY_BINARY_FILES(patient_fhir_id, doc_type=None, date_range=None)
  # Returns: document references, types, dates (for targeted document retrieval)

QUERY_ENCOUNTERS(patient_fhir_id, date_range=None)
  # Returns: encounter_date, type, reason, diagnoses

# Radiation Oncology Views (6 queries)
QUERY_RADIATION_APPOINTMENTS(patient_fhir_id)
QUERY_RADIATION_COURSES(patient_fhir_id)
QUERY_RADIATION_CARE_PLANS(patient_fhir_id)
QUERY_RADIATION_SERVICE_REQUESTS(patient_fhir_id)
```

**Query Example:**
```sql
-- Master Orchestrator needs surgery dates for validation
SELECT
    procedure_date,
    proc_code_text,
    is_surgical_keyword,
    age_at_procedure_days
FROM fhir_prd_db.v_procedures
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND is_surgical_keyword = true
ORDER BY procedure_date;

-- Returns:
-- 2018-05-28 | Craniotomy | true | 4763
-- 2021-03-10 | Partial resection | true | 5774
```

---

### 3. Medical Reasoning Agent (MedGemma 27B or Claude)

**Responsibilities:**
- Interprets clinical narratives from binary documents
- Extracts free-text fields (extent of resection, histology, clinical impressions)
- Answers targeted questions from Master Orchestrator
- Uses Athena query results to validate document content

**Dialogue Capability:**
```
Master: "What was the extent of resection on 2018-05-28?"
Medical Agent: [Queries binary_files for operative note on that date]
Medical Agent: "Operative note states: 'Gross total resection of cerebellar tumor'"
Master: [Cross-validates with Athena v_procedures showing surgery on 2018-05-28]
Master: "Validated. Confidence: 0.95"
```

---

### 4. Validation Agent (Rule-Based + LLM Hybrid)

**Responsibilities:**
- Cross-source validation (Athena structured vs. document extraction)
- Data dictionary compliance checking (valid dropdown values)
- Temporal consistency verification (dates in logical sequence)
- Confidence scoring based on agreement

**Validation Types:**

| Type | Example | Validation Logic |
|------|---------|-----------------|
| **Categorical** | extent_of_resection | Must match data dictionary dropdown |
| **Date Proximity** | surgery_date | Athena date ±7 days of document date |
| **Temporal Sequence** | chemotherapy_start < chemotherapy_end | Logical ordering |
| **Presence Verification** | IDH mutation | Molecular test confirms presence |
| **Cross-Source Agreement** | primary_diagnosis | Pathology = ICD-10 = Problem List |

**Confidence Scoring:**
- 0.95-1.0: Structured + Document agree, data dictionary compliant
- 0.80-0.94: Structured OR Document source, validated
- 0.60-0.79: Single source, no validation available
- 0.40-0.59: Sources conflict, manual review needed
- 0.00-0.39: Contradictory data, extraction failed

---

## Workflow Process

### Phase 1: Field Classification

**Master Orchestrator** receives data dictionary field and classifies:

```python
field = {
    "name": "extent_of_resection",
    "type": "dropdown",
    "valid_values": [
        "Gross total resection",
        "Near total resection",
        "Subtotal resection",
        "Partial resection",
        "Biopsy only"
    ],
    "data_sources": ["v_procedures", "operative_notes"]
}

classification = classify_field(field)
# Returns: "HYBRID" (needs both Athena + documents)
```

**Classification Categories:**

1. **STRUCTURED_ONLY** (30% of fields)
   - Directly queryable from Athena views
   - No document extraction needed
   - Examples: gender, birth_date, medication_name

2. **HYBRID** (50% of fields)
   - Athena provides validation dates/presence
   - Documents provide clinical details
   - Examples: extent_of_resection, who_grade, tumor_location

3. **DOCUMENT_ONLY** (20% of fields)
   - No structured Athena equivalent
   - Free-text extraction required
   - Examples: clinical_status narrative, pathology_notes

---

### Phase 2: Extraction Strategy Planning

**For STRUCTURED_ONLY fields:**
```python
# Example: patient_gender
plan = {
    "strategy": "DIRECT_QUERY",
    "athena_view": "v_patient_demographics",
    "athena_column": "pd_gender",
    "confidence": 1.0  # Structured data = high confidence
}
```

**For HYBRID fields:**
```python
# Example: extent_of_resection
plan = {
    "strategy": "QUERY_THEN_EXTRACT",
    "steps": [
        "1. Query v_procedures for surgery dates (validation)",
        "2. Extract extent from operative notes (clinical detail)",
        "3. Cross-validate dates match",
        "4. Validate extracted value in dropdown list"
    ],
    "athena_view": "v_procedures",
    "document_types": ["operative_note", "pathology_report"],
    "validation": "date_proximity + dropdown_match"
}
```

**For DOCUMENT_ONLY fields:**
```python
# Example: imaging_findings (free text)
plan = {
    "strategy": "DOCUMENT_EXTRACTION",
    "document_types": ["radiology_report"],
    "validation": "none",
    "confidence": 0.70  # Lower confidence without structured validation
}
```

---

### Phase 3: Multi-Agent Dialogue Execution

**Example: Extracting "extent_of_resection" (HYBRID field)**

#### Step 1 - Master Orchestrator Plans
```
Field: extent_of_resection
Classification: HYBRID
Data Dictionary Constraint: Dropdown (5 valid values)
Strategy: Query Athena for surgery dates → Extract from documents → Cross-validate
```

#### Step 2 - Athena Query Agent Executes
```python
surgeries = QUERY_PROCEDURES(
    patient_fhir_id='e4BwD8ZYDBccepXcJ.Ilo3w3',
    procedure_type='tumor_resection'
)

# Returns:
[
    {
        'procedure_date': '2018-05-28',
        'proc_code_text': 'Craniotomy for tumor',
        'is_surgical_keyword': True,
        'age_at_procedure_days': 4763
    },
    {
        'procedure_date': '2021-03-10',
        'proc_code_text': 'Partial tumor resection',
        'is_surgical_keyword': True,
        'age_at_procedure_days': 5774
    }
]
```

#### Step 3 - Medical Reasoning Agent Searches Documents
```
Master: "Search for operative notes on 2018-05-28 and 2021-03-10"
Medical Agent: [Queries v_binary_files for operative notes on those dates]
Medical Agent: Found 2 documents:
  - Operative note 2018-05-28: "Gross total resection of cerebellar pilocytic astrocytoma"
  - Operative note 2021-03-10: "Partial resection of recurrent tumor"
```

#### Step 4 - Validation Agent Cross-Checks
```python
# Validation 1: Date proximity
doc_date_1 = "2018-05-28"
athena_date_1 = "2018-05-28"
date_match_1 = (doc_date_1 == athena_date_1)  # ✓ PASS

doc_date_2 = "2021-03-10"
athena_date_2 = "2021-03-10"
date_match_2 = (doc_date_2 == athena_date_2)  # ✓ PASS

# Validation 2: Data dictionary compliance
extracted_value_1 = "Gross total resection"
extracted_value_2 = "Partial resection"
valid_values = ["Gross total resection", "Near total resection",
                "Subtotal resection", "Partial resection", "Biopsy only"]

dropdown_match_1 = (extracted_value_1 in valid_values)  # ✓ PASS
dropdown_match_2 = (extracted_value_2 in valid_values)  # ✓ PASS

# Confidence calculation
confidence_1 = 0.95  # Structured + Document + Data dictionary validated
confidence_2 = 0.95
```

#### Step 5 - Master Orchestrator Adjudicates
```json
{
  "field": "extent_of_resection",
  "extractions": [
    {
      "surgery_date": "2018-05-28",
      "value": "Gross total resection",
      "confidence": 0.95,
      "data_sources": ["v_procedures", "operative_note_2018-05-28"],
      "validation_status": "validated",
      "age_at_surgery_days": 4763
    },
    {
      "surgery_date": "2021-03-10",
      "value": "Partial resection",
      "confidence": 0.95,
      "data_sources": ["v_procedures", "operative_note_2021-03-10"],
      "validation_status": "validated",
      "age_at_surgery_days": 5774
    }
  ],
  "agent_dialogue": [
    "Master: Classify field → HYBRID",
    "Master: Query Athena for surgery dates",
    "Athena: Found 2 surgeries: 2018-05-28, 2021-03-10",
    "Master: Request document extraction",
    "Medical Agent: Extracted 'Gross total resection' (2018-05-28)",
    "Medical Agent: Extracted 'Partial resection' (2021-03-10)",
    "Validation: Dates match ✓",
    "Validation: Dropdown compliant ✓",
    "Master: Adjudication complete, confidence 0.95"
  ]
}
```

---

## Data Dictionary Field Classification

### Category 1: STRUCTURED_ONLY Fields (Direct Athena Query)

| Field | Athena View | Column | Notes |
|-------|-------------|--------|-------|
| patient_gender | v_patient_demographics | pd_gender | "male" or "female" |
| date_of_birth | v_patient_demographics | pd_birth_date | ISO 8601 timestamp |
| race | v_patient_demographics | pd_race | "White", "Black", etc. |
| ethnicity | v_patient_demographics | pd_ethnicity | "Hispanic/Latino", "Not Hispanic/Latino" |
| age_at_diagnosis | CALCULATED | DATE_DIFF(diagnosis_date, birth_date) | Derived field |
| chemotherapy_agent | v_medications | medication_name | Drug names |
| chemotherapy_start_date | v_medications | mr_authored_on | ISO 8601 timestamp |
| chemotherapy_end_date | v_medications | mr_validity_period_end | ISO 8601 timestamp |
| chemotherapy_status | v_medications | mr_status | "active", "completed" |
| idh_mutation | v_molecular_tests | mtr_components_list | Search for "IDH" |
| mgmt_methylation | v_molecular_tests | mtr_components_list | Search for "MGMT" |
| braf_status | v_molecular_tests | mtr_components_list | Search for "BRAF" |
| radiation_start_date | v_radiation_treatment_courses | sr_occurrence_period_start | ISO 8601 timestamp |

**Extraction Workflow:**
1. Master Orchestrator identifies field as STRUCTURED_ONLY
2. Athena Query Agent executes SQL query
3. Returns value directly
4. Confidence = 1.0 (structured data)

**Example Code:**
```python
def extract_structured_field(patient_id, field_definition):
    """Extract field directly from Athena view"""
    view = field_definition['athena_view']
    column = field_definition['athena_column']

    query = f"""
    SELECT {column}
    FROM fhir_prd_db.{view}
    WHERE patient_fhir_id = '{patient_id}'
    """

    result = athena_query_agent.execute(query)

    return {
        'value': result[0][column],
        'confidence': 1.0,
        'source': f'{view}.{column}',
        'validation_status': 'structured'
    }
```

---

### Category 2: HYBRID Fields (Athena Validation + Document Extraction)

| Field | Athena Source | Document Source | Challenge |
|-------|---------------|-----------------|-----------|
| primary_diagnosis | v_problem_list_diagnoses | Pathology reports | Histology description |
| diagnosis_date | v_problem_list_diagnoses | Pathology, Clinical notes | Date disambiguation |
| who_grade | v_problem_list_diagnoses | Pathology reports | Grade extraction (1-4) |
| tumor_location | v_procedures (body_site) | Operative notes, Imaging | 24-option anatomical classification |
| extent_of_resection | v_procedures | Operative notes | Resection classification (5 options) |
| surgery_type | v_procedures | Operative notes | Initial/Recurrence/2nd malignancy |
| surgery_date | v_procedures | Operative notes | Multiple surgeries (many_per_note) |
| radiation_dose | v_radiation_treatment_courses | Radiation oncology notes | Total dose in Gy |
| radiation_fractions | v_radiation_treatment_courses | Radiation treatment plans | Number of fractions |
| chemotherapy_line | v_medications | Treatment plans | 1st/2nd/3rd line classification |
| chemotherapy_route | v_medications | Med admin notes | IV/oral/intrathecal |

**Extraction Workflow:**
1. Master Orchestrator queries Athena for **validation data** (dates, presence confirmation)
2. Medical Reasoning Agent extracts **clinical details** from documents
3. Validation Agent **cross-checks** document date/content against Athena
4. If validation passes → High confidence (0.85-0.95)
5. If validation fails → Flag for manual review (confidence < 0.60)

**Example Code:**
```python
def extract_hybrid_field(patient_id, field_definition):
    """Extract field using Athena validation + document extraction"""

    # Step 1: Query Athena for validation
    validation_data = athena_query_agent.query(
        view=field_definition['athena_view'],
        patient_id=patient_id
    )

    # Step 2: Extract from documents
    document_extraction = medical_reasoning_agent.extract(
        patient_id=patient_id,
        field=field_definition['name'],
        doc_types=field_definition['document_types'],
        validation_context=validation_data  # Provide Athena data to LLM
    )

    # Step 3: Cross-validate
    validation_result = validation_agent.validate(
        athena_data=validation_data,
        document_data=document_extraction,
        validation_rules=field_definition['validation_rules']
    )

    # Step 4: Adjudicate
    if validation_result['status'] == 'validated':
        confidence = 0.95
    elif validation_result['status'] == 'partial_match':
        confidence = 0.70
    else:
        confidence = 0.40  # Needs manual review

    return {
        'value': document_extraction['value'],
        'confidence': confidence,
        'athena_source': validation_data,
        'document_source': document_extraction['source_doc'],
        'validation_status': validation_result['status']
    }
```

---

### Category 3: DOCUMENT_ONLY Fields (Free-Text Extraction)

| Field | Document Source | Challenge | Notes |
|-------|-----------------|-----------|-------|
| clinical_status | Progress notes | Stable/Progressive/Recurrent tracking | Longitudinal (many_per_note) |
| imaging_findings | Radiology reports | Free-text impression | 500 char summary |
| tumor_size | Radiology reports | Dimension extraction (cm) | Pattern: "3.5 x 2.1 x 2.8 cm" |
| contrast_enhancement | Radiology reports | Yes/No/Unknown | Keywords: "enhancing", "non-enhancing" |
| surgical_complications | Operative notes | Complication description | Free text |
| treatment_response | Oncology notes | Response assessment | RECIST criteria |
| pathology_notes | Pathology reports | Free-text findings | Narrative summary |

**Extraction Workflow:**
1. Master Orchestrator identifies field as DOCUMENT_ONLY
2. Medical Reasoning Agent searches relevant document types
3. Extracts value using targeted prompts
4. No Athena validation available
5. Confidence based on document quality (0.60-0.80 typical)

**Example Code:**
```python
def extract_document_only_field(patient_id, field_definition):
    """Extract field from documents only (no Athena validation)"""

    # Search for relevant documents
    documents = medical_reasoning_agent.find_documents(
        patient_id=patient_id,
        doc_types=field_definition['document_types'],
        keywords=field_definition.get('keywords', [])
    )

    # Extract from each document
    extractions = []
    for doc in documents:
        extraction = medical_reasoning_agent.extract_from_document(
            document=doc,
            field=field_definition['name'],
            instruction=field_definition['instruction']
        )
        extractions.append(extraction)

    # Aggregate if multiple extractions
    final_value = aggregate_extractions(extractions)

    # Confidence based on document quality
    confidence = calculate_confidence(
        num_sources=len(documents),
        consistency=check_consistency(extractions),
        document_quality=assess_document_quality(documents)
    )

    return {
        'value': final_value,
        'confidence': confidence,
        'sources': [doc['id'] for doc in documents],
        'validation_status': 'no_validation_available'
    }
```

---

## Implementation Components

### File Structure

```
athena_views/
├── multi_agent/                           # NEW multi-agent framework
│   ├── master_orchestrator.py            # Master agent (Claude)
│   ├── athena_query_agent.py             # SQL query engine
│   ├── medical_reasoning_agent.py        # Document extraction (MedGemma/Claude)
│   ├── validation_agent.py               # Cross-source validation
│   ├── field_classifier.py               # STRUCTURED/HYBRID/DOCUMENT classification
│   ├── confidence_scorer.py              # Confidence calculation logic
│   └── dialogue_manager.py               # Agent communication protocol
│
├── data_dictionary/                       # CBTN data dictionary integration
│   ├── data_dictionary_loader.py         # Load 345 field definitions
│   ├── field_mappings.py                 # Field → Athena view mappings
│   └── validation_rules.py               # Data dictionary constraints
│
├── patient_workflows/                     # Patient-specific extraction
│   ├── single_patient_extractor.py       # Extract all fields for 1 patient
│   ├── cohort_extractor.py               # Batch process multiple patients
│   └── extraction_report_generator.py    # Generate audit trail
│
└── config/
    ├── athena_connection.yaml            # AWS Athena credentials
    ├── field_classification_config.yaml  # Field category assignments
    └── agent_prompts/                    # LLM prompt templates
        ├── master_orchestrator_prompts.yaml
        ├── medical_reasoning_prompts.yaml
        └── validation_prompts.yaml
```

---

## Testing Strategy

### Test Patient: e4BwD8ZYDBccepXcJ.Ilo3w3

**Gold Standard Data (from CBTN data dictionary):**
- Gender: Female
- Birth Date: 2005-05-13
- Diagnosis: Pilocytic astrocytoma
- Diagnosis Date: 2018-06-04 (pathology report)
- Surgery Date: 2018-05-28 (initial craniotomy)
- Extent of Resection: Gross total resection
- Chemotherapy Agents: Bevacizumab, Vinblastine, Selumetinib (3 agents)
- BRAF Status: BRAF fusion (KIAA1549-BRAF)
- IDH Mutation: Wildtype (inferred from BRAF fusion)
- MGMT Methylation: Not tested (low-grade tumor)

### Validation Criteria

| Field | Expected Value | Athena Source | Document Source | Confidence Target |
|-------|----------------|---------------|-----------------|-------------------|
| patient_gender | Female | v_patient_demographics | N/A | 1.0 |
| date_of_birth | 2005-05-13 | v_patient_demographics | N/A | 1.0 |
| primary_diagnosis | Pilocytic astrocytoma | v_problem_list_diagnoses | Pathology | 0.95 |
| diagnosis_date | 2018-06-04 | v_problem_list_diagnoses | Pathology | 0.90 |
| surgery_date | 2018-05-28 | v_procedures | Operative note | 0.95 |
| extent_of_resection | Gross total resection | v_procedures | Operative note | 0.95 |
| chemotherapy_agent | Bevacizumab, Vinblastine, Selumetinib | v_medications | N/A | 1.0 |
| braf_status | BRAF fusion | v_molecular_tests | Molecular report | 0.95 |
| idh_mutation | Wildtype | v_molecular_tests | Molecular report | 0.90 |

### Success Metrics

**Target Accuracy:** 95%+ (19/20 test fields correct)

**By Field Category:**
- STRUCTURED_ONLY: 100% accuracy (all fields)
- HYBRID: 90%+ accuracy (document extraction validated by Athena)
- DOCUMENT_ONLY: 75%+ accuracy (no validation available)

**Confidence Distribution:**
- High confidence (0.85-1.0): 80% of extractions
- Medium confidence (0.60-0.84): 15% of extractions
- Low confidence (< 0.60): 5% of extractions (manual review needed)

---

## Advantages Over Previous Approaches

### Previous CSV-Based Workflow
❌ Single patient at a time
❌ File staging required (1 patient = 15 CSV files)
❌ No real-time validation
❌ Manual cross-checking needed
❌ Not scalable to cohort

### New Athena-Based Multi-Agent Workflow
✅ **Scalable:** Query entire cohort with `WHERE patient_fhir_id IN (...)`
✅ **Real-time validation:** Cross-check document extraction against Athena structured data
✅ **Multi-agent orchestration:** Master coordinates queries + extraction + validation
✅ **Data dictionary compliant:** All 345 fields mapped and validated
✅ **Audit trail:** Complete agent dialogue logged for clinical review
✅ **Confidence scoring:** Transparent confidence based on validation

---

## Next Steps

### Phase 1: Core Framework (Week 1)
1. Implement `AthenaQueryAgent` with 15 view query functions
2. Implement `MasterOrchestrator` with field classification logic
3. Implement `FieldClassifier` (STRUCTURED/HYBRID/DOCUMENT routing)
4. Create data dictionary loader for 345 CBTN fields
5. Set up Athena connection configuration

### Phase 2: Agent Integration (Week 2)
1. Implement `MedicalReasoningAgent` (wrapper for MedGemma/Claude)
2. Implement `ValidationAgent` with cross-source validation
3. Create dialogue protocol for agent communication
4. Implement confidence scoring logic
5. Create extraction report generator

### Phase 3: Testing & Validation (Week 3)
1. Test on pilot patient e4BwD8ZYDBccepXcJ.Ilo3w3
2. Validate accuracy vs. gold standard (target: 95%+)
3. Test all 3 field categories (STRUCTURED, HYBRID, DOCUMENT)
4. Optimize dialogue efficiency
5. Document edge cases and failure modes

### Phase 4: Scale Testing (Week 4)
1. Test on 10 patients from cohort
2. Measure accuracy, confidence distribution
3. Assess computational cost (Athena queries + LLM calls)
4. Generate comprehensive audit trails
5. Prepare for production deployment

---

## Configuration Examples

### Field Classification Config

```yaml
# field_classification_config.yaml

structured_only_fields:
  - patient_gender:
      athena_view: v_patient_demographics
      athena_column: pd_gender
      confidence: 1.0

  - date_of_birth:
      athena_view: v_patient_demographics
      athena_column: pd_birth_date
      confidence: 1.0

  - chemotherapy_agent:
      athena_view: v_medications
      athena_column: medication_name
      confidence: 1.0

hybrid_fields:
  - extent_of_resection:
      athena_view: v_procedures
      athena_columns: [procedure_date, is_surgical_keyword]
      document_types: [operative_note, pathology_report]
      validation_rules:
        - date_proximity: 7  # days
        - dropdown_match:
            - "Gross total resection"
            - "Near total resection"
            - "Subtotal resection"
            - "Partial resection"
            - "Biopsy only"
      confidence_calculation:
        athena_validated_document: 0.95
        document_only: 0.70
        conflict: 0.40

  - primary_diagnosis:
      athena_view: v_problem_list_diagnoses
      athena_columns: [diagnosis_name, pld_onset_date]
      document_types: [pathology_report, clinical_note]
      validation_rules:
        - icd10_match: true
        - snomed_match: true
      confidence_calculation:
        pathology_report: 0.95
        icd10_match: 0.85
        problem_list_only: 0.70

document_only_fields:
  - imaging_findings:
      document_types: [radiology_report]
      extraction_instruction: "Extract impression section (max 500 chars)"
      confidence: 0.70

  - clinical_status:
      document_types: [progress_note, oncology_note]
      extraction_instruction: "Extract disease status: Stable/Progressive/Recurrent"
      scope: many_per_note
      confidence: 0.75
```

---

## Conclusion

This Athena-based multi-agent architecture transforms clinical data abstraction from a **single-patient, file-based workflow** to a **scalable, validated, multi-agent orchestration** approach.

**Key Innovations:**
1. **Direct Athena queries** replace CSV staging
2. **Real-time cross-source validation** improves accuracy
3. **Field classification** routes extraction to appropriate agents
4. **Multi-agent dialogue** enables iterative refinement
5. **Data dictionary enforcement** ensures compliance

**Expected Outcomes:**
- 95%+ accuracy on CBTN data dictionary fields
- 80% high-confidence extractions (0.85-1.0)
- Complete audit trail for clinical review
- Scalable to entire cohort (100+ patients)

---

**Status:** Ready for implementation
**Next Action:** Implement Phase 1 (Core Framework) starting with `AthenaQueryAgent` class
