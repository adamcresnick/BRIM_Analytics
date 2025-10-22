# Radiation Data Extraction Integration Design

**Date:** 2025-10-22
**Purpose:** Design comprehensive radiation data extraction following the existing multi-source abstraction pattern

---

## Executive Summary

This document outlines the integration of radiation treatment data extraction into the existing `run_full_multi_source_abstraction.py` workflow. The design follows the established two-agent architecture where Agent 2 extracts from multiple sources (structured Athena views + binary documents) and Agent 1 validates, adjudicates conflicts, and identifies clinical inconsistencies.

---

## Required Radiation Fields (Data Dictionary)

Based on data dictionary review, the following fields must be extracted:

### Core Fields
1. **radiation** - Yes/No/Unavailable (boolean indicator)
2. **radiation_type** - Protons, Photons, Combination, Gamma Knife, Other
3. **radiation_site** - Focal/Tumor bed, Craniospinal with boost, Whole Ventricular with boost, Other
4. **age_at_radiation_start** - Start date (converted to age in days)
5. **age_at_radiation_stop** - Stop date (converted to age in days)

### Dose Fields (conditional based on site)
6. **total_radiation_dose** - CSI/Whole Ventricular dose (numeric value)
7. **total_radiation_dose_unit** - cGy, Gy, or CGE
8. **total_radiation_dose_focal** - Focal/boost dose (additive)
9. **total_radiation_dose_focal_unit** - cGy, Gy, or CGE

### Free Text Fields
- **radiation_type_other** - If type = Other
- **radiation_site_other** - If site = Other

---

## Data Sources Available (Per Patient)

### 1. Structured Data (Athena Views)

#### v_radiation_summary
- **Purpose:** Data availability inventory
- **Fields:** Flags for each data source, counts, date ranges, recommended extraction strategy
- **Use Case:** Determine which sources are available and prioritize extraction approach

#### v_radiation_treatments
- **Purpose:** Structured ELECT intake form data
- **Coverage:** ~13% of patients (91/684)
- **Fields:** obs_start_date, obs_stop_date, obs_dose_value, obs_radiation_field, radiation_modality, radiation_site
- **Quality:** High - structured data from intake forms

#### v_radiation_care_plan_hierarchy
- **Purpose:** Treatment planning information
- **Coverage:** ~83% of patients (568/684)
- **Fields:** care_plan_id, title, status, period_start, period_end
- **Quality:** Moderate - metadata, less detail on doses/sites

#### v_radiation_treatment_appointments
- **Purpose:** Appointment scheduling context
- **Coverage:** Variable per patient
- **Fields:** appointment_id, appointment_start, appointment_end, status, radiation_identification_method
- **Quality:** Low for extraction - primarily temporal coverage

### 2. Narrative Documents (Binary Files)

#### v_radiation_documents
- **Purpose:** Treatment summaries, consults, planning documents
- **Coverage:** 100% of patients with radiation data (684/684)
- **Document Types:**
  - Treatment summaries (Priority 1)
  - Consults (Priority 2)
  - Radiation reports (Priority 3)
  - Planning documents (Priority 4)
- **Quality:** High - detailed narrative descriptions of treatment

---

## Integration Architecture

### Phase 1: Query Radiation Data Sources (Parallel to Existing Sources)

Add radiation queries alongside existing imaging, operative, and progress note queries.

```python
# 1E: Radiation structured data summary
print("1E. Radiation summary (v_radiation_summary):")
radiation_summary_query = f"""
    SELECT *
    FROM v_radiation_summary
    WHERE patient_fhir_id = '{athena_patient_id}'
"""

# 1F: Radiation structured treatments (ELECT intake forms)
print("1F. Radiation structured treatments (v_radiation_treatments):")
radiation_treatments_query = f"""
    SELECT
        patient_fhir_id,
        course_id,
        obs_start_date,
        obs_stop_date,
        obs_dose_value,
        obs_dose_unit,
        obs_radiation_field,
        radiation_modality,
        radiation_site,
        data_source_primary,
        data_source_secondary
    FROM v_radiation_treatments
    WHERE patient_fhir_id = '{athena_patient_id}'
    ORDER BY obs_start_date
"""

# 1G: Radiation documents (treatment summaries, consults, reports)
print("1G. Radiation documents (v_radiation_documents):")
radiation_documents_query = f"""
    SELECT
        document_id,
        patient_fhir_id,
        doc_date,
        dr_type_text,
        dr_description,
        document_priority,
        binary_id,
        content_type
    FROM v_radiation_documents
    WHERE patient_fhir_id = '{athena_patient_id}'
    ORDER BY document_priority, doc_date
"""
```

### Phase 2: Agent 2 Extraction from Radiation Sources

#### 2E: Extract from Structured Radiation Data

```python
print("\n" + "="*80)
print("2E. AGENT 2: EXTRACTING FROM STRUCTURED RADIATION DATA")
print("="*80)

# Build comprehensive structured radiation context
structured_radiation_context = {
    'summary': radiation_summary[0] if radiation_summary else None,
    'treatments': radiation_treatments,
    'appointment_count': len(radiation_appointments),
    'earliest_treatment_date': radiation_summary[0].get('radiation_treatment_earliest_date') if radiation_summary else None,
    'latest_treatment_date': radiation_summary[0].get('radiation_treatment_latest_date') if radiation_summary else None,
    'recommended_extraction_strategy': radiation_summary[0].get('recommended_extraction_strategy') if radiation_summary else None,
    'data_sources_available': radiation_summary[0].get('num_data_sources_available') if radiation_summary else 0
}

# Create structured extraction prompt
structured_radiation_prompt = build_structured_radiation_extraction_prompt(
    structured_context=structured_radiation_context,
    patient_id=args.patient_id
)

# Agent 2 extracts from structured data
structured_radiation_extraction = medgemma.query(structured_radiation_prompt)

# Parse and validate
structured_radiation_data = parse_radiation_extraction(structured_radiation_extraction)
```

#### 2F: Extract from Radiation Documents (Narrative)

```python
print("\n" + "="*80)
print("2F. AGENT 2: EXTRACTING FROM RADIATION DOCUMENTS")
print("="*80)

radiation_document_extractions = []

for idx, rad_doc in enumerate(radiation_documents, 1):
    print(f"\n  Processing radiation document {idx}/{len(radiation_documents)}:")
    print(f"    Type: {rad_doc['dr_type_text']}")
    print(f"    Date: {rad_doc['doc_date']}")
    print(f"    Priority: {rad_doc['document_priority']}")

    # Retrieve document text
    binary_id = rad_doc['binary_id']
    doc_text = doc_cache.get_cached_text(binary_id)

    if not doc_text:
        # Extract from PDF/binary if not cached
        doc_text = binary_agent.extract_text_from_binary(
            binary_id=binary_id,
            content_type=rad_doc['content_type']
        )
        if doc_text:
            doc_cache.cache_text(binary_id, doc_text)

    # Build extraction prompt
    radiation_doc_prompt = build_radiation_document_extraction_prompt(
        document_text=doc_text,
        document_metadata=rad_doc,
        structured_context=structured_radiation_context,
        patient_id=args.patient_id
    )

    # Agent 2 extracts
    extraction = medgemma.query(radiation_doc_prompt)
    parsed_extraction = parse_radiation_extraction(extraction)

    radiation_document_extractions.append({
        'document_id': rad_doc['document_id'],
        'document_type': rad_doc['dr_type_text'],
        'document_date': rad_doc['doc_date'],
        'document_priority': rad_doc['document_priority'],
        'extraction': parsed_extraction,
        'raw_response': extraction
    })
```

### Phase 3: Agent 1 Validation & Adjudication

```python
print("\n" + "="*80)
print("3. AGENT 1: RADIATION DATA VALIDATION & ADJUDICATION")
print("="*80)

# Agent 1 reviews all radiation extractions
radiation_adjudication = {
    'structured_data_review': None,
    'document_extractions_review': [],
    'multi_source_adjudication': None,
    'final_radiation_data': None,
    'inconsistencies_detected': [],
    'confidence_assessment': None
}

# 3A: Review structured data extraction
if structured_radiation_data:
    print("\n3A. Reviewing structured radiation data extraction...")
    structured_review_prompt = build_radiation_structured_review_prompt(
        extraction=structured_radiation_data,
        structured_context=structured_radiation_context
    )

    structured_review = medgemma.query(structured_review_prompt)
    radiation_adjudication['structured_data_review'] = structured_review

# 3B: Review each document extraction
print("\n3B. Reviewing radiation document extractions...")
for doc_extraction in radiation_document_extractions:
    review_prompt = build_radiation_document_review_prompt(
        extraction=doc_extraction['extraction'],
        document_metadata=doc_extraction,
        structured_context=structured_radiation_context
    )

    review = medgemma.query(review_prompt)
    radiation_adjudication['document_extractions_review'].append({
        'document_id': doc_extraction['document_id'],
        'review': review,
        'validated': True  # Update based on review
    })

# 3C: Multi-source adjudication (structured vs documents)
print("\n3C. Multi-source radiation data adjudication...")
adjudication_prompt = build_radiation_adjudication_prompt(
    structured_data=structured_radiation_data,
    document_extractions=radiation_document_extractions,
    structured_context=structured_radiation_context
)

adjudication_result = medgemma.query(adjudication_prompt)
radiation_adjudication['multi_source_adjudication'] = adjudication_result

# 3D: Detect clinical inconsistencies
print("\n3D. Detecting radiation clinical inconsistencies...")
inconsistency_prompt = build_radiation_inconsistency_detection_prompt(
    adjudicated_data=adjudication_result,
    patient_timeline=timeline_context  # From existing timeline
)

inconsistencies = medgemma.query(inconsistency_prompt)
radiation_adjudication['inconsistencies_detected'] = inconsistencies

# 3E: If inconsistencies detected, query Agent 2 for clarification
if inconsistencies.get('has_inconsistencies'):
    print("\n3E. Querying Agent 2 for clarification on inconsistencies...")
    for inconsistency in inconsistencies['items']:
        clarification_prompt = build_radiation_clarification_prompt(
            inconsistency=inconsistency,
            original_extractions=radiation_document_extractions
        )

        clarification = medgemma.query(clarification_prompt)
        inconsistency['clarification'] = clarification

# 3F: Final radiation data synthesis
print("\n3F. Synthesizing final radiation data...")
final_radiation_data = synthesize_radiation_data(
    adjudication=radiation_adjudication,
    structured_data=structured_radiation_data,
    document_extractions=radiation_document_extractions
)

radiation_adjudication['final_radiation_data'] = final_radiation_data
```

---

## Output JSON Structure

```json
{
  "patient_id": "Patient/ecKghinUQVl9Q6cMoA0RD1qZHVzp7JHW12RpiW1UMx0A3",
  "timestamp": "20251022_143052",
  "radiation_treatment": {
    "has_radiation_data": true,
    "data_sources_used": ["structured_elect", "radiation_documents"],
    "extraction_strategy": "structured_primary_with_document_validation",

    "fields": {
      "radiation": {
        "value": "Yes",
        "confidence": 0.95,
        "source": "structured",
        "source_id": "Observation/rad-course-1",
        "supporting_sources": ["DocumentReference/rad-summary-1", "DocumentReference/rad-consult-1"],
        "reasoning": "Structured ELECT intake form explicitly documents radiation treatment"
      },

      "radiation_type": {
        "value": "Protons",
        "confidence": 0.90,
        "source": "structured",
        "source_id": "Observation/rad-course-1",
        "supporting_sources": ["DocumentReference/rad-summary-1"],
        "reasoning": "ELECT form specifies proton therapy, confirmed in treatment summary"
      },

      "radiation_site": {
        "value": "Focal/Tumor bed",
        "confidence": 0.92,
        "source": "document",
        "source_id": "DocumentReference/rad-summary-1",
        "supporting_sources": ["Observation/rad-course-1"],
        "reasoning": "Treatment summary describes focal radiation to tumor bed in right frontal lobe"
      },

      "age_at_radiation_start": {
        "value": "2019-07-15",
        "age_in_days": 4520,
        "confidence": 0.98,
        "source": "structured",
        "source_id": "Observation/rad-course-1",
        "supporting_sources": ["Appointment/rad-appt-1"],
        "reasoning": "ELECT form obs_start_date matches first radiation appointment"
      },

      "age_at_radiation_stop": {
        "value": "2019-08-30",
        "age_in_days": 4566,
        "confidence": 0.98,
        "source": "structured",
        "source_id": "Observation/rad-course-1",
        "supporting_sources": ["Appointment/rad-appt-last"],
        "reasoning": "ELECT form obs_stop_date matches last radiation appointment"
      },

      "total_radiation_dose_focal": {
        "value": "5400",
        "confidence": 0.88,
        "source": "document",
        "source_id": "DocumentReference/rad-summary-1",
        "supporting_sources": ["Observation/rad-course-1"],
        "reasoning": "Treatment summary states '54 Gy delivered in 30 fractions', ELECT data shows similar dose"
      },

      "total_radiation_dose_focal_unit": {
        "value": "cGy",
        "confidence": 0.90,
        "source": "structured",
        "source_id": "Observation/rad-course-1",
        "supporting_sources": [],
        "reasoning": "ELECT form dose_unit field specifies cGy"
      }
    },

    "multi_source_adjudication": {
      "structured_vs_documents_agreement": 0.92,
      "conflicts_detected": [
        {
          "field": "total_radiation_dose_focal",
          "structured_value": "5400 cGy",
          "document_value": "54 Gy (5400 cGy)",
          "resolution": "Values equivalent after unit conversion",
          "confidence": 0.95
        }
      ],
      "conflicts_resolved": 1,
      "conflicts_unresolved": 0
    },

    "clinical_inconsistencies": {
      "detected": false,
      "items": []
    },

    "agent_feedback_loops": [
      {
        "iteration": 1,
        "agent_1_question": "Dose discrepancy: ELECT shows 5400 cGy but document says 54 Gy. Please clarify.",
        "agent_2_response": "Both values are equivalent. 54 Gy = 5400 cGy (1 Gy = 100 cGy). Document uses Gy for readability.",
        "resolution": "Confirmed equivalent - no actual discrepancy"
      }
    ],

    "data_quality_metrics": {
      "structured_data_completeness": 0.85,
      "document_extraction_completeness": 0.90,
      "cross_source_validation_score": 0.92,
      "overall_confidence": 0.89
    }
  }
}
```

---

## Extraction Prompt Templates

### 1. Structured Radiation Extraction Prompt

```python
def build_structured_radiation_extraction_prompt(structured_context, patient_id):
    return f"""
You are a medical data extraction specialist. Extract radiation treatment information from the following structured data.

PATIENT ID: {patient_id}

STRUCTURED RADIATION DATA:
{json.dumps(structured_context, indent=2)}

EXTRACT THE FOLLOWING FIELDS:
1. radiation (Yes/No/Unavailable)
2. radiation_type (Protons/Photons/Combination/Gamma Knife/Other)
3. radiation_site (Focal/Craniospinal/Whole Ventricular/Other)
4. age_at_radiation_start (date and age in days from birth)
5. age_at_radiation_stop (date and age in days from birth)
6. total_radiation_dose (numeric value)
7. total_radiation_dose_unit (cGy/Gy/CGE)
8. total_radiation_dose_focal (numeric value, if applicable)
9. total_radiation_dose_focal_unit (cGy/Gy/CGE, if applicable)

For each field, provide:
- value: The extracted value
- confidence: Your confidence (0.0-1.0)
- source_field: Which structured field this came from
- reasoning: Brief explanation

Return as JSON.
"""
```

### 2. Radiation Document Extraction Prompt

```python
def build_radiation_document_extraction_prompt(document_text, document_metadata, structured_context, patient_id):
    return f"""
You are a medical data extraction specialist. Extract radiation treatment information from this clinical document.

PATIENT ID: {patient_id}

DOCUMENT METADATA:
- Type: {document_metadata['dr_type_text']}
- Date: {document_metadata['doc_date']}
- Priority: {document_metadata['document_priority']}

DOCUMENT TEXT:
{document_text}

STRUCTURED CONTEXT (for validation):
{json.dumps(structured_context, indent=2)}

EXTRACT THE FOLLOWING FIELDS:
[Same 9 fields as structured extraction]

IMPORTANT:
- If structured data is available, note any agreements or conflicts
- Cite specific text from the document
- Flag any uncertainties or ambiguities

Return as JSON with fields: value, confidence, text_citation, reasoning
"""
```

### 3. Radiation Adjudication Prompt

```python
def build_radiation_adjudication_prompt(structured_data, document_extractions, structured_context):
    return f"""
You are Agent 1, the master orchestrator. Review and adjudicate radiation treatment data from multiple sources.

STRUCTURED DATA EXTRACTION:
{json.dumps(structured_data, indent=2)}

DOCUMENT EXTRACTIONS ({len(document_extractions)} documents):
{json.dumps(document_extractions, indent=2)}

YOUR TASKS:
1. Compare structured vs document extractions for each field
2. Identify conflicts (different values from different sources)
3. Resolve conflicts using clinical reasoning:
   - Prefer structured data when high quality and complete
   - Prefer document data when structured is missing/incomplete
   - Use most recent source when dates conflict
   - Use most specific source (e.g., treatment summary > general note)

4. For each field, determine:
   - Final adjudicated value
   - Confidence (0.0-1.0)
   - Primary source
   - Supporting sources
   - Conflicts detected and how resolved

5. Flag any unresolvable conflicts for Agent 2 clarification

Return as JSON with adjudicated fields and conflict resolution details.
"""
```

### 4. Clinical Inconsistency Detection Prompt

```python
def build_radiation_inconsistency_detection_prompt(adjudicated_data, patient_timeline):
    return f"""
You are Agent 1. Detect clinical inconsistencies in radiation treatment data.

ADJUDICATED RADIATION DATA:
{json.dumps(adjudicated_data, indent=2)}

PATIENT TIMELINE (for context):
- Date of birth: {patient_timeline.get('dob')}
- Diagnosis date: {patient_timeline.get('diagnosis_date')}
- Surgery dates: {patient_timeline.get('surgery_dates')}
- Other treatment dates: {patient_timeline.get('other_treatments')}

CHECK FOR CLINICAL INCONSISTENCIES:
1. Temporal violations:
   - Radiation start before diagnosis date?
   - Radiation start before birth?
   - Stop date before start date?
   - Unreasonably long treatment duration?

2. Dose inconsistencies:
   - Focal dose without site specified?
   - CSI dose without CSI site?
   - Dose values outside typical ranges?
   - Unit mismatches?

3. Clinical paradigm violations:
   - Radiation type inappropriate for site?
   - Dose inappropriate for pediatric patient?
   - Treatment gaps/overlaps with surgeries?

For each inconsistency:
- Type (temporal/dose/clinical)
- Description
- Severity (low/medium/high)
- Requires clarification? (yes/no)

Return as JSON.
"""
```

---

## Implementation Phases

### Phase 1: Add Radiation Queries (Week 1)
- Add 1E, 1F, 1G queries to PHASE 1
- Test query execution on test patient
- Validate data retrieval

### Phase 2: Create Extraction Prompts (Week 1)
- Build structured extraction prompt
- Build document extraction prompt
- Build adjudication prompt
- Build inconsistency detection prompt
- Test prompts with Agent 2

### Phase 3: Implement Agent 2 Extraction (Week 2)
- Add 2E: Structured extraction
- Add 2F: Document extraction
- Test on patient with comprehensive radiation data
- Validate parsing and error handling

### Phase 4: Implement Agent 1 Validation (Week 2)
- Add 3A-3F: Review, adjudication, inconsistency detection
- Implement feedback loops
- Test multi-source adjudication

### Phase 5: Integration & Testing (Week 3)
- Integrate into main workflow
- Test on 10 diverse patients
- Validate output JSON structure
- Performance optimization

### Phase 6: Deployment (Week 3)
- Deploy radiation views to Athena
- Run cohort-wide extraction
- Validate results against gold standard

---

## Success Criteria

1. **Coverage:** Extract radiation data for ≥95% of patients with radiation treatment
2. **Accuracy:** ≥90% agreement with manual chart review (sample of 50 patients)
3. **Completeness:** ≥85% of required fields populated when data exists
4. **Confidence:** Average confidence score ≥0.80 across all extractions
5. **Adjudication:** ≥95% of multi-source conflicts successfully resolved
6. **Clinical Validity:** ≥98% of extractions pass clinical inconsistency checks

---

## Next Steps

1. Review and approve design
2. Set up second test patient (`ecKghinUQVl9Q6cMoA0RD1qZHVzp7JHW12RpiW1UMx0A3`)
3. Deploy fixed radiation views to Athena
4. Begin Phase 1 implementation
5. Create validation gold standard dataset

