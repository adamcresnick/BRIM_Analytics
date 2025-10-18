# Patient Workflows - Athena-Based Multi-Agent Extraction

## Overview

This directory contains workflows for extracting clinical data using the Athena-based multi-agent framework.

## Quick Start

### Single Patient Extraction

```bash
python single_patient_extractor.py \
  --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --athena-output-bucket s3://your-athena-results-bucket/ \
  --output-dir ./extraction_results
```

### Extract Specific Fields

```bash
python single_patient_extractor.py \
  --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --fields patient_gender date_of_birth primary_diagnosis \
  --athena-output-bucket s3://your-athena-results-bucket/ \
  --output-dir ./extraction_results
```

## Workflow Steps

The single patient extractor follows this 5-step workflow:

1. **Query Athena** - Retrieve all structured data from 15 Athena views
2. **Extract STRUCTURED_ONLY fields** - Direct query results (gender, DOB, medications)
3. **Extract HYBRID fields** - Athena validation + document extraction (diagnosis, surgeries)
4. **Extract DOCUMENT_ONLY fields** - Free-text extraction (clinical status, imaging findings)
5. **Generate Report** - Comprehensive JSON output with confidence scores

## Output Format

```json
{
  "patient_fhir_id": "e4BwD8ZYDBccepXcJ.Ilo3w3",
  "extraction_timestamp": "2025-10-17T14:30:00",
  "extraction_duration_seconds": 45.2,
  "athena_data_summary": {
    "demographics": 1,
    "diagnoses": 7,
    "procedures": 72,
    "medications": 409
  },
  "structured_fields": {
    "patient_gender": {
      "value": "female",
      "confidence": 1.0,
      "source": "athena.demographics.pd_gender"
    }
  },
  "hybrid_fields": {
    "extent_of_resection": {
      "value": ["Gross total resection", "Partial resection"],
      "confidence": 0.95,
      "validation_status": "validated"
    }
  },
  "overall_summary": {
    "total_fields": 19,
    "high_confidence": 15,
    "medium_confidence": 3,
    "low_confidence": 1
  }
}
```

## Available Fields

### STRUCTURED_ONLY (7 fields)
Direct Athena queries, confidence = 1.0:
- `patient_gender`
- `date_of_birth`
- `race`
- `ethnicity`
- `chemotherapy_agent`
- `chemotherapy_start_date`
- `chemotherapy_status`

### HYBRID (8 fields)
Athena validation + document extraction, confidence = 0.70-0.95:
- `primary_diagnosis`
- `diagnosis_date`
- `who_grade`
- `tumor_location`
- `extent_of_resection`
- `surgery_date`
- `surgery_type`
- `radiation_dose`

### DOCUMENT_ONLY (4 fields)
Document extraction only, confidence = 0.60-0.80:
- `clinical_status`
- `imaging_findings`
- `tumor_size`
- `pathology_notes`

## Requirements

```bash
pip install boto3 pandas pyyaml
```

## AWS Configuration

Ensure AWS credentials are configured:

```bash
aws configure
```

Or use environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

## Next Steps

- Implement Medical Reasoning Agent for HYBRID and DOCUMENT_ONLY fields
- Add cohort extraction capability
- Integrate with BRIM for free-text abstraction validation
