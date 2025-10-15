# Comprehensive Workflow Requirements for RADIANT PCA Extraction Pipeline

## Executive Summary

This document outlines the complete workflow requirements for performing clinical data extraction on all RADIANT PCA patients using our local LLM extraction pipeline. The workflow addresses critical findings from our pilot extraction, particularly the necessity of post-operative imaging validation for surgical extent assessment.

## Critical Requirements

### 1. Mandatory Post-Operative Imaging Validation

**Requirement**: All extent of resection extractions MUST be validated against post-operative imaging (24-72 hours post-surgery).

**Rationale**: Our analysis discovered that operative notes can fundamentally misclassify surgical extent. Example: Patient e4BwD8ZYDBccepXcJ.Ilo3w3 operative note stated "Biopsy only" when post-op MRI clearly showed "Near-total debulking."

**Implementation**:
- Extract from operative note first
- Always retrieve post-op imaging 1-30 days after surgery
- Override operative note if discrepancy found
- Document all discrepancies for clinical review

### 2. Multi-Source Evidence Requirement

**Requirement**: Each critical variable must be extracted from at least 2 independent sources.

**Critical Variables**:
- extent_of_tumor_resection
- tumor_location
- histopathology
- who_grade
- metastasis_presence

**Implementation**:
```python
minimum_sources = 2
if len(extracted_sources) < minimum_sources:
    trigger_fallback_retrieval()
```

## Workflow Stages

### Stage 1: Data Preparation (Pre-Extraction)

#### 1.1 Patient Cohort Definition
```csv
# patient_cohort.csv structure
patient_id,mrn,inclusion_criteria,priority,notes
e4BwD8ZYDBccepXcJ.Ilo3w3,1277724,pediatric_brain_tumor,high,multiple_surgeries
patient_002,mrn_002,pediatric_brain_tumor,medium,single_surgery
```

#### 1.2 Environment Verification Checklist
- [ ] AWS credentials valid: `aws sts get-caller-identity --profile radiant`
- [ ] S3 access confirmed: `aws s3 ls s3://fhir-datalake-us-west-2-data-5/BRIM/`
- [ ] Ollama running: `curl http://localhost:11434/api/tags`
- [ ] Model available: `ollama list | grep gemma2:27b`
- [ ] Staging files present: `ls athena_extraction_validation/staging_files/`
- [ ] Data dictionary loaded: `Dictionary/radiology_op_note_data_dictionary.csv`

#### 1.3 Resource Allocation
- **CPU**: Minimum 8 cores for Ollama
- **RAM**: 32GB minimum (64GB recommended for gemma2:27b)
- **Storage**: 100GB for model and outputs
- **Time**: ~5 minutes per patient event

### Stage 2: Extraction Execution

#### 2.1 Event Identification
```python
def identify_surgical_events(patient_id):
    """
    Identify all surgical events from procedures table
    """
    procedures = pd.read_csv(f'staging_files/patient_{patient_id}/procedures.csv')

    # Filter for CNS tumor surgeries
    surgery_codes = [
        '61510',  # Craniectomy for tumor
        '61512',  # Craniotomy for tumor
        '61518',  # Craniectomy for posterior fossa tumor
        '61519',  # Craniotomy for posterior fossa tumor
    ]

    surgeries = procedures[
        procedures['procedure_source_value'].isin(surgery_codes)
    ].sort_values('procedure_date')

    return surgeries
```

#### 2.2 Document Retrieval Strategy

**Primary Window** (Surgery date ± 7 days):
- Operative notes
- Pathology reports
- Post-op imaging (Day +1 to +3 preferred)

**Secondary Window** (Surgery date ± 14 days):
- Discharge summaries
- Transfer notes
- Follow-up imaging

**Tertiary Window** (Surgery date ± 30 days):
- Progress notes
- Oncology consultations
- Radiology reports with anatomical terms

#### 2.3 Extraction Process

```python
# For each patient event
for event in patient_events:
    # Step 1: Primary extraction
    primary_docs = retrieve_primary_documents(event.date)
    primary_results = extract_from_documents(primary_docs)

    # Step 2: Check completeness
    missing_vars = check_missing_variables(primary_results)

    # Step 3: Fallback if needed
    if missing_vars:
        fallback_docs = retrieve_fallback_documents(event.date, missing_vars)
        fallback_results = extract_from_documents(fallback_docs)
        primary_results.update(fallback_results)

    # Step 4: Post-op validation (MANDATORY for extent)
    if 'extent_of_tumor_resection' in primary_results:
        postop_result = validate_with_postop_imaging(event.date)
        if postop_result != primary_results['extent_of_tumor_resection']:
            log_discrepancy(event, primary_results, postop_result)
            primary_results['extent_of_tumor_resection'] = postop_result

    # Step 5: Calculate confidence
    for var in primary_results:
        primary_results[var]['confidence'] = calculate_confidence(
            sources=primary_results[var]['sources'],
            agreement=primary_results[var]['agreement_ratio']
        )
```

### Stage 3: Validation & Quality Control

#### 3.1 Automated Validation Rules

```python
validation_rules = {
    'extent_of_tumor_resection': {
        'valid_values': ['Gross total', 'Near-total', 'Subtotal', 'Partial', 'Biopsy only'],
        'requires_imaging': True,
        'minimum_confidence': 0.7
    },
    'tumor_location': {
        'allow_multiple': True,
        'anatomical_terms_required': True,
        'valid_regions': ['frontal', 'temporal', 'parietal', 'occipital',
                         'cerebellum', 'brainstem', 'ventricle', 'thalamus']
    },
    'histopathology': {
        'requires_pathology_report': True,
        'who_classification_required': True
    }
}
```

#### 3.2 Manual Review Triggers

Automatically flag for manual review when:
- Confidence score < 0.7
- Agreement ratio < 0.66 (sources disagree)
- Discrepancy between operative note and imaging
- Critical variables marked "Unavailable"
- Temporal inconsistencies (e.g., metastasis before primary tumor)

#### 3.3 Quality Metrics Tracking

```python
quality_metrics = {
    'extraction_completeness': extracted_vars / total_vars,
    'multi_source_coverage': vars_with_2plus_sources / total_vars,
    'average_confidence': mean(all_confidence_scores),
    'discrepancy_rate': discrepancies_found / total_extractions,
    'fallback_success_rate': vars_recovered_by_fallback / vars_attempted_fallback,
    'post_op_validation_rate': events_with_postop_validation / total_events
}
```

### Stage 4: Output Generation

#### 4.1 REDCap Format Generation

```python
def format_for_redcap(extraction_results):
    """
    Convert extraction results to REDCap import format
    """
    redcap_records = []

    for event_idx, event in enumerate(extraction_results['events'], 1):
        record = {
            'record_id': f"{extraction_results['patient_id']}_event{event_idx}",
            'event_name': f"surgery_{event_idx}_arm_1",
            'surgery_date': event['date'],
        }

        # Map extracted values to data dictionary codes
        for var_name, var_data in event['variables'].items():
            if var_name in data_dictionary:
                record[var_name] = map_to_dictionary_code(
                    var_data['value'],
                    data_dictionary[var_name]
                )

                # Add confidence as auxiliary field
                record[f"{var_name}_confidence"] = var_data['confidence']

        # Handle checkbox fields (multiple selections)
        if isinstance(record.get('tumor_location'), list):
            record['tumor_location'] = '|'.join(map(str, record['tumor_location']))

        redcap_records.append(record)

    return redcap_records
```

#### 4.2 Output File Structure

```
outputs/
├── production_run_YYYYMMDD/
│   ├── patient_extractions/
│   │   ├── patient_001.json          # Complete extraction
│   │   ├── patient_002.json
│   │   └── ...
│   ├── redcap_import/
│   │   └── redcap_import_batch.csv   # REDCap-ready format
│   ├── validation_reports/
│   │   ├── discrepancies.json        # All discrepancies found
│   │   ├── low_confidence.json       # Extractions needing review
│   │   └── validation_summary.html   # Human-readable report
│   ├── extraction_summary.json       # Overall statistics
│   └── extraction_log.txt           # Detailed execution log
```

## Implementation Scripts

### 1. Master Pipeline Controller
```bash
#!/bin/bash
# run_full_extraction.sh

# Set environment
export AWS_PROFILE=radiant
export OLLAMA_HOST=http://localhost:11434

# Verify prerequisites
python3 verify_environment.py || exit 1

# Run extraction
python3 production_extraction_pipeline.py \
    --patient-list patient_cohort.csv \
    --workers 4 \
    --model gemma2:27b \
    --output-dir outputs/production_$(date +%Y%m%d)

# Run validation
python3 validation_pipeline.py \
    --extraction-dir outputs/production_$(date +%Y%m%d)

# Generate reports
python3 generate_reports.py \
    --extraction-dir outputs/production_$(date +%Y%m%d) \
    --format html,json,csv

# Check for critical issues
python3 check_critical_issues.py \
    --extraction-dir outputs/production_$(date +%Y%m%d) \
    --alert-threshold 0.7
```

### 2. Individual Patient Re-extraction
```python
# reextract_patient.py
import sys
from production_extraction_pipeline import ProductionExtractionPipeline

def reextract_patient(patient_id: str, reason: str):
    """
    Re-extract single patient with enhanced logging
    """
    pipeline = ProductionExtractionPipeline(
        patient_list_path=None,  # Single patient mode
        enhanced_logging=True
    )

    print(f"Re-extracting patient {patient_id}")
    print(f"Reason: {reason}")

    result = pipeline.process_patient(patient_id)

    # Save with timestamp
    output_file = f"reextraction_{patient_id}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to {output_file}")

    # Run validation
    validator = ExtractionValidator()
    validation = validator.validate_patient(output_file)

    if validation['issues']:
        print("⚠️ Validation issues found:")
        for issue in validation['issues']:
            print(f"  - {issue}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python reextract_patient.py <patient_id> <reason>")
        sys.exit(1)

    reextract_patient(sys.argv[1], sys.argv[2])
```

## Monitoring & Alerts

### Real-Time Monitoring
```python
class ExtractionMonitor:
    def __init__(self):
        self.metrics = defaultdict(list)
        self.alert_thresholds = {
            'confidence': 0.7,
            'agreement': 0.66,
            'completion': 0.8
        }

    def log_extraction(self, patient_id, event, results):
        """Log and check for alerts"""

        # Check confidence
        low_confidence = [
            var for var, data in results.items()
            if data.get('confidence', 0) < self.alert_thresholds['confidence']
        ]

        if low_confidence:
            self.send_alert(
                f"Low confidence for {patient_id}: {low_confidence}"
            )

        # Check discrepancies
        if results.get('discrepancy_found'):
            self.send_alert(
                f"Discrepancy found for {patient_id} event {event}: "
                f"Operative vs Imaging mismatch"
            )

        # Track metrics
        self.metrics['extractions'].append({
            'timestamp': datetime.now(),
            'patient_id': patient_id,
            'event': event,
            'completion_rate': sum(1 for v in results.values() if v.get('value')) / len(results),
            'avg_confidence': np.mean([v.get('confidence', 0) for v in results.values()])
        })
```

## Error Recovery

### Common Errors and Recovery Strategies

1. **Ollama Timeout**
   ```python
   @retry(max_attempts=3, backoff=exponential)
   def extract_with_retry(text, prompt):
       try:
           return ollama_extract(text[:2000], prompt, timeout=30)
       except TimeoutError:
           # Reduce text size and retry
           return ollama_extract(text[:1000], prompt, timeout=30)
   ```

2. **S3 Access Failure**
   ```python
   def get_document_with_fallback(binary_id):
       try:
           return retrieve_from_s3(binary_id)
       except S3Error:
           # Fall back to imaging.csv narrative
           return get_from_imaging_table(binary_id)
   ```

3. **Missing Staging Files**
   ```python
   def ensure_staging_files(patient_id):
       required_files = ['procedures.csv', 'imaging.csv', 'pathology.csv']
       missing = []

       for file in required_files:
           if not Path(f'staging_files/patient_{patient_id}/{file}').exists():
               missing.append(file)

       if missing:
           # Regenerate from Athena
           regenerate_staging_files(patient_id, missing)
   ```

## Performance Optimization

### Parallel Processing Strategy
```python
def optimize_extraction_order(patients):
    """
    Order patients for optimal parallel processing
    """
    # Group by estimated complexity
    simple = []  # Single surgery, recent
    moderate = []  # Multiple surgeries or older
    complex = []  # Many surgeries, very old, known issues

    for patient in patients:
        event_count = count_surgical_events(patient)
        oldest_date = get_oldest_surgery_date(patient)

        if event_count == 1 and oldest_date > datetime(2020, 1, 1):
            simple.append(patient)
        elif event_count <= 3:
            moderate.append(patient)
        else:
            complex.append(patient)

    # Process simple cases in parallel, complex sequentially
    return simple + moderate + complex
```

### Caching Strategy
```python
class ExtractionCache:
    def __init__(self, cache_dir='./cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_cached_extraction(self, doc_id, variable):
        cache_key = hashlib.md5(f"{doc_id}_{variable}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            # Check if cache is fresh (< 7 days)
            if time.time() - cache_file.stat().st_mtime < 7 * 24 * 3600:
                with open(cache_file) as f:
                    return json.load(f)

        return None

    def cache_extraction(self, doc_id, variable, result):
        cache_key = hashlib.md5(f"{doc_id}_{variable}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        with open(cache_file, 'w') as f:
            json.dump(result, f)
```

## Compliance & Audit Trail

### Audit Logging
```python
def log_audit_event(event_type, details):
    """
    Maintain audit trail for compliance
    """
    audit_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'user': os.environ.get('USER'),
        'details': details,
        'system': {
            'model': 'gemma2:27b',
            'pipeline_version': '2.0.0',
            'aws_profile': 'radiant'
        }
    }

    with open('audit_log.jsonl', 'a') as f:
        f.write(json.dumps(audit_entry) + '\n')
```

### HIPAA Compliance Checklist
- [ ] All PHI stored encrypted at rest
- [ ] Access logs maintained for all data retrieval
- [ ] No PHI in log files or error messages
- [ ] Secure deletion of temporary files
- [ ] Role-based access control implemented
- [ ] Data retention policy enforced

## Success Metrics

### Target Performance Indicators
- **Extraction Completeness**: > 90% of variables extracted
- **Multi-Source Coverage**: > 80% with 2+ sources
- **Average Confidence**: > 0.80
- **Discrepancy Rate**: < 15%
- **Post-Op Validation Rate**: 100% for extent of resection
- **Processing Time**: < 5 minutes per patient event
- **Manual Review Rate**: < 20% of extractions

### Monthly Reporting Requirements
1. Total patients processed
2. Extraction success rate by variable
3. Discrepancy analysis report
4. Confidence score distribution
5. Performance trending
6. Error rate and types
7. Manual review outcomes

## Appendix A: Variable Extraction Prompts

### Extent of Resection
```python
EXTENT_PROMPT = """
Extract the extent of tumor resection from this document.

Use ONLY these exact terms:
- Gross total resection (100% removal)
- Near-total resection (>95% removal)
- Subtotal resection (50-95% removal)
- Partial resection (<50% removal)
- Biopsy only (tissue sampling only)

Look for key phrases:
- debulking, resection, removal, excision
- percentage removed
- residual tumor
- complete vs incomplete

Return ONLY the extent category.
"""
```

### Tumor Location
```python
LOCATION_PROMPT = """
Extract ALL tumor locations mentioned in this document.

Valid anatomical locations:
- Frontal lobe
- Temporal lobe
- Parietal lobe
- Occipital lobe
- Cerebellum
- Brainstem
- Thalamus
- Ventricle (specify which)
- Corpus callosum
- Pineal region

Return as comma-separated list.
"""
```

## Appendix B: Data Dictionary Mapping

```python
DATA_DICTIONARY_MAPPINGS = {
    'extent_of_tumor_resection': {
        'Gross total resection': 1,
        'Near-total resection': 1,  # Combined with gross total
        'Subtotal resection': 2,
        'Partial resection': 2,  # Combined with subtotal
        'Biopsy only': 3,
        'Unavailable': 4
    },
    'tumor_location': {
        'Frontal lobe': 1,
        'Temporal lobe': 2,
        'Parietal lobe': 3,
        'Occipital lobe': 4,
        'Cerebellum': 5,
        'Brainstem': 6,
        'Thalamus': 7,
        'Ventricle': 8,
        'Other': 9
    }
}
```

---
Document Version: 1.0.0
Last Updated: January 2025
Next Review: March 2025