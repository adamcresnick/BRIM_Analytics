# Hybrid FHIR + BRIM Extraction Strategy
## Leveraging Structured FHIR Data & Unstructured Clinical Notes via BRIM API

**Created:** October 1, 2025  
**Project:** RADIANT_PCA / BRIM_Analytics  
**Purpose:** Optimal clinical trial data extraction combining FHIR structured data with BRIM NLP for unstructured notes

---

## 🎯 Executive Summary

This strategy combines **two complementary approaches** for comprehensive clinical data extraction:

1. **Direct FHIR Extraction** - Structured data from Athena (demographics, medications, observations, procedures)
2. **BRIM NLP Analysis** - Unstructured narrative extraction from clinical notes via BRIM's API

### Key Innovation: Hybrid Approach
- Use FHIR for what it does best: structured, coded data
- Use BRIM for what it does best: complex narrative interpretation
- **Pre-populate BRIM with FHIR context** via HINT columns for validation and gap-filling

---

## 📊 The Data Landscape

### Available FHIR Resources (Athena)

From the bulk FHIR export schema (`e934bc57-fb76-433f-8fa5-4ccd3bffb0c2.csv`):

#### **1. DocumentReference Table**
- **Contains:** Metadata about clinical documents
- **Key Fields:**
  - `id` - Document identifier
  - `type` - Document type (operative note, pathology, radiology)
  - `subject` - Patient reference
  - `date` - Document creation date
  - `content` - Array with attachment references to Binary resources
  - `category` - Document categorization
  - `status` - Document status

#### **2. Binary Table**
- **Contains:** Actual document content (base64 encoded)
- **Key Fields:**
  - `id` - Binary resource ID
  - `contenttype` - MIME type (text/plain, text/html, application/pdf)
  - `data` - Base64 encoded content
  - `securitycontext` - Reference back to source

#### **3. Structured Clinical Tables**
- `patient` - Demographics, identifiers
- `condition` - Diagnoses, problem list
- `procedure` - Surgical procedures with dates
- `medicationrequest` / `medication` - Orders and administration
- `observation` - Lab results, vital signs, measurements
- `encounter` - Visit information
- `diagnosticreport` - Imaging and lab reports

---

## 🏗️ Architecture: The Hybrid Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: FHIR EXTRACTION                     │
│                  (Python + Athena SQL Queries)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Extract Structured Data from FHIR       │
        │  - Demographics                          │
        │  - Surgical events with dates            │
        │  - Medications with RxNorm codes         │
        │  - Diagnoses with ICD-10                 │
        │  - Lab values and measurements           │
        └──────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Extract DocumentReference Metadata      │
        │  - Identify all clinical notes           │
        │  - Map to Binary content                 │
        │  - Categorize by type                    │
        │  - Temporal sorting                      │
        └──────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                PHASE 2: BRIM CSV GENERATION                     │
│          (Python - Combine FHIR + Binary Content)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Generate BRIM Project CSV               │
        │  ┌────────────────────────────────────┐  │
        │  │ NOTE_ID | From DocumentReference  │  │
        │  │ PERSON_ID | From Patient          │  │
        │  │ NOTE_DATETIME | From date field   │  │
        │  │ NOTE_TEXT | Decoded Binary data   │  │
        │  │ NOTE_TITLE | From type field      │  │
        │  │ HINT_SURGERY_NUMBER | Computed    │  │
        │  │ HINT_DIAGNOSIS | From Condition   │  │
        │  │ HINT_WHO_GRADE | From Condition   │  │
        │  │ HINT_MEDICATIONS | From MedReq    │  │
        │  └────────────────────────────────────┘  │
        └──────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Generate BRIM Variables CSV             │
        │  - surgery_number (first!)               │
        │  - document_type                         │
        │  - Clinical variables per domain         │
        │  - Instructions reference HINTs          │
        └──────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Generate BRIM Decisions CSV             │
        │  - Dependent variables by surgery        │
        │  - Cross-document aggregations           │
        │  - Temporal correlations                 │
        └──────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE 3: BRIM API INTERACTION                   │
│              (Python - Automated Job Submission)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  BRIM API Workflow                       │
        │  1. Authenticate                         │
        │  2. Upload Project CSV                   │
        │  3. Upload Variables CSV                 │
        │  4. Upload Decisions CSV                 │
        │  5. Submit extraction job                │
        │  6. Poll for completion                  │
        │  7. Download results                     │
        └──────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 4: RESULT INTEGRATION                        │
│      (Python - Merge BRIM Results with FHIR Data)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Comprehensive Clinical Trial Dataset    │
        │  - FHIR structured data (high confidence)│
        │  - BRIM extracted data (from narratives) │
        │  - Validation flags (HINT vs extracted)  │
        │  - Confidence scores per field           │
        └──────────────────────────────────────────┘
```

---

## 💡 Strategic Decision Framework: FHIR vs BRIM

### Use FHIR Direct Extraction When:

✅ **Data is well-structured and coded**
- Demographics (birth date, sex, race, ethnicity)
- Coded diagnoses (ICD-10, SNOMED)
- Medications with RxNorm codes
- Lab values with LOINC codes
- Procedure dates and CPT codes

✅ **Temporal precision is critical**
- Surgery dates (from `procedure.performedDateTime`)
- Medication administration dates
- Encounter timestamps

✅ **Quantitative data is available**
- Vital signs, anthropometric measurements
- Lab test numeric results
- Medication dosages

✅ **Data relationships are explicit**
- Medication → Encounter linkage
- Procedure → Condition linkage
- DocumentReference → Binary content

### Use BRIM NLP Extraction When:

✅ **Data is in unstructured narratives**
- Surgical operative notes
- Pathology reports
- Radiology interpretations
- Progress notes

✅ **Clinical interpretation is required**
- "Extent of resection: gross total" → 100%
- "Near-total resection achieved" → 95%
- "WHO Grade I pilocytic astrocytoma" → Grade extraction

✅ **Multiple documents need synthesis**
- Aggregate diagnoses across 5 pathology reports
- Correlate surgical complications across notes
- Track disease progression descriptors

✅ **Contextual nuance matters**
- "No evidence of residual tumor" vs "Residual tumor present"
- "Hydrocephalus improved" vs "New hydrocephalus"
- Temporal qualifiers: "at initial diagnosis" vs "at progression"

---

## 🔧 Implementation: The Hybrid Workflow

### Step 1: FHIR Structured Data Extraction

```python
# Extract structured clinical context
def extract_fhir_context(patient_id, athena_connection):
    """
    Extract all structured FHIR data for a patient.
    This provides GROUND TRUTH for BRIM validation.
    """
    
    context = {}
    
    # 1. Get all surgical procedures with dates
    context['surgeries'] = query_surgical_procedures(patient_id)
    # Output: [{'date': '2018-05-28', 'procedure': 'Craniotomy', ...}, ...]
    
    # 2. Get all diagnoses with dates
    context['diagnoses'] = query_conditions(patient_id)
    # Output: [{'date': '2018-05-29', 'icd10': 'C71.6', 'diagnosis': 'Pilocytic astrocytoma', ...}]
    
    # 3. Get all medications with RxNorm
    context['medications'] = query_medications(patient_id)
    # Output: [{'date': '2019-06-15', 'rxnorm': '1736776', 'medication': 'Bevacizumab', ...}]
    
    # 4. Get demographics
    context['demographics'] = query_patient_demographics(patient_id)
    
    return context
```

### Step 2: Clinical Notes Discovery & Enrichment

```python
# Query all clinical notes with metadata
def discover_clinical_notes(patient_id, fhir_context):
    """
    Find all DocumentReferences, extract Binary content,
    and enrich with structured FHIR context.
    """
    
    sql = """
    SELECT 
        dr.id as document_id,
        dr.date as document_date,
        dr.type.text as document_type,
        dr.category[1].text as category,
        dr.content[1].attachment.url as binary_url,
        -- Extract Binary ID from URL
        REGEXP_EXTRACT(dr.content[1].attachment.url, 'Binary/([^/]+)') as binary_id
    FROM documentreference dr
    WHERE dr.subject.reference = CONCAT('Patient/', :patient_id)
        AND dr.status = 'current'
    ORDER BY dr.date
    """
    
    notes = execute_query(sql, patient_id=patient_id)
    
    # For each note, extract Binary content and add FHIR hints
    enriched_notes = []
    for note in notes:
        # Get Binary content
        content = extract_binary_content(note['binary_id'])
        
        # Sanitize HTML
        clean_text = sanitize_html(content)
        
        # Add structured hints from FHIR
        note['NOTE_TEXT'] = clean_text
        note['HINT_SURGERY_NUMBER'] = assign_to_surgery(note['document_date'], fhir_context['surgeries'])
        note['HINT_DIAGNOSIS'] = get_relevant_diagnosis(note['document_date'], fhir_context['diagnoses'])
        note['HINT_WHO_GRADE'] = extract_grade_from_diagnosis(note['HINT_DIAGNOSIS'])
        note['HINT_MEDICATIONS'] = get_active_medications(note['document_date'], fhir_context['medications'])
        
        enriched_notes.append(note)
    
    return enriched_notes
```

### Step 3: Generate BRIM Project CSV

```python
def generate_brim_project_csv(enriched_notes, patient_research_id, output_path):
    """
    Create BRIM-compatible project CSV with HINT columns.
    """
    
    import pandas as pd
    import csv
    
    rows = []
    for i, note in enumerate(enriched_notes):
        row = {
            'NOTE_ID': f'DOC_{i+1:04d}',
            'PERSON_ID': patient_research_id,
            'NOTE_DATETIME': note['document_date'].strftime('%Y-%m-%d %H:%M:%S'),
            'NOTE_TEXT': note['NOTE_TEXT'],
            'NOTE_TITLE': note['document_type'],
            # HINT columns from FHIR
            'HINT_SURGERY_NUMBER': note['HINT_SURGERY_NUMBER'],
            'HINT_EVENT_TYPE': note.get('HINT_EVENT_TYPE', ''),
            'HINT_DIAGNOSIS': note['HINT_DIAGNOSIS'],
            'HINT_WHO_GRADE': note['HINT_WHO_GRADE'],
            'HINT_MEDICATIONS': '; '.join(note['HINT_MEDICATIONS']) if note['HINT_MEDICATIONS'] else '',
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Critical: Use QUOTE_ALL for BRIM compatibility
    df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
    
    return output_path
```

### Step 4: Generate BRIM Variables CSV (Hint-Aware)

```python
def generate_brim_variables_csv(clinical_domain, output_path):
    """
    Generate BRIM variables that leverage HINT columns.
    """
    
    variables = []
    
    # CRITICAL: surgery_number MUST be first
    variables.append({
        'variable_name': 'surgery_number',
        'instruction': 'Check the HINT_SURGERY_NUMBER field. Return that exact value.',
        'variable_type': 'text',
        'prompt_template': '',
        'can_be_missing': '0',
        'scope': 'one_per_note',
        'option_definitions': '',
        'aggregation_instruction': '',
        'aggregation_prompt_template': '',
        'aggregation_option_definitions': '',
        'only_use_true_value_in_aggregation': ''
    })
    
    # Document type classification
    variables.append({
        'variable_name': 'document_type',
        'instruction': 'Classify this document. Return OPERATIVE for operative reports, PATHOLOGY for pathology reports, RADIOLOGY for imaging reports, OTHER for everything else.',
        'variable_type': 'text',
        'prompt_template': '',
        'can_be_missing': '0',
        'scope': 'one_per_note',
        'option_definitions': '',
        'aggregation_instruction': '',
        'aggregation_prompt_template': '',
        'aggregation_option_definitions': '',
        'only_use_true_value_in_aggregation': ''
    })
    
    # Domain-specific variables with HINT validation
    if clinical_domain == 'neuro_oncology':
        # Pathologic diagnosis with HINT validation
        variables.append({
            'variable_name': 'pathologic_diagnosis',
            'instruction': 'Extract pathologic diagnosis. FIRST check HINT_DIAGNOSIS field. If present and matches content, return it. Otherwise extract from text. Look for specific tumor types like pilocytic astrocytoma, glioblastoma, etc.',
            'variable_type': 'text',
            'prompt_template': '',
            'can_be_missing': '1',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': ''
        })
        
        # WHO Grade with HINT validation
        variables.append({
            'variable_name': 'who_grade',
            'instruction': 'Extract WHO grade. FIRST check HINT_WHO_GRADE field. If present, validate against text. Extract: I, II, III, or IV.',
            'variable_type': 'text',
            'prompt_template': '',
            'can_be_missing': '1',
            'scope': 'many_per_note',
            'option_definitions': 'I;II;III;IV',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': ''
        })
        
        # Extent of resection (narrative interpretation)
        variables.append({
            'variable_name': 'extent_of_resection_percent',
            'instruction': 'Extract extent of tumor resection as percentage. GTR/Complete = 100, NTR/Near-total = 95, STR/Subtotal = 50-90, Partial = <50, Biopsy only = 0. Return numeric value.',
            'variable_type': 'integer',
            'prompt_template': '',
            'can_be_missing': '1',
            'scope': 'one_per_note',
            'option_definitions': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': ''
        })
    
    # Convert to DataFrame and save
    df = pd.DataFrame(variables)
    df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
    
    return output_path
```

### Step 5: BRIM API Interaction

```python
import requests
import time
from typing import Dict, Optional

class BRIMAPIClient:
    """
    Client for interacting with BRIM Health API.
    
    NOTE: This is a template - actual API endpoints and authentication
    will need to be confirmed with BRIM documentation or support.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.brimhealth.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def upload_project_csv(self, file_path: str, project_name: str) -> str:
        """Upload project CSV and return project ID."""
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(
                f"{self.base_url}/v1/projects/upload",
                files=files,
                data={'name': project_name}
            )
        
        response.raise_for_status()
        return response.json()['project_id']
    
    def upload_variables_csv(self, project_id: str, file_path: str) -> bool:
        """Upload variables configuration."""
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(
                f"{self.base_url}/v1/projects/{project_id}/variables",
                files=files
            )
        
        response.raise_for_status()
        return True
    
    def upload_decisions_csv(self, project_id: str, file_path: str) -> bool:
        """Upload dependent variables configuration."""
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(
                f"{self.base_url}/v1/projects/{project_id}/decisions",
                files=files
            )
        
        response.raise_for_status()
        return True
    
    def submit_extraction_job(self, project_id: str, config: Optional[Dict] = None) -> str:
        """Submit extraction job and return job ID."""
        
        payload = config or {}
        response = self.session.post(
            f"{self.base_url}/v1/projects/{project_id}/extract",
            json=payload
        )
        
        response.raise_for_status()
        return response.json()['job_id']
    
    def get_job_status(self, job_id: str) -> Dict:
        """Check job status."""
        
        response = self.session.get(
            f"{self.base_url}/v1/jobs/{job_id}"
        )
        
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, job_id: str, poll_interval: int = 30, timeout: int = 3600) -> Dict:
        """Poll job status until completion or timeout."""
        
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
            
            status = self.get_job_status(job_id)
            
            if status['status'] == 'completed':
                return status
            elif status['status'] == 'failed':
                raise Exception(f"Job {job_id} failed: {status.get('error')}")
            
            time.sleep(poll_interval)
    
    def download_results(self, job_id: str, output_path: str) -> str:
        """Download extraction results."""
        
        response = self.session.get(
            f"{self.base_url}/v1/jobs/{job_id}/results",
            stream=True
        )
        
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return output_path


# Usage Example
def run_brim_extraction(project_csv, variables_csv, decisions_csv, api_key):
    """
    Complete BRIM extraction workflow via API.
    """
    
    client = BRIMAPIClient(api_key)
    
    # 1. Upload project
    print("Uploading project CSV...")
    project_id = client.upload_project_csv(project_csv, "Patient_Neuro_Oncology_Extraction")
    print(f"Project created: {project_id}")
    
    # 2. Upload configurations
    print("Uploading variables...")
    client.upload_variables_csv(project_id, variables_csv)
    
    print("Uploading decisions...")
    client.upload_decisions_csv(project_id, decisions_csv)
    
    # 3. Submit job
    print("Submitting extraction job...")
    job_id = client.submit_extraction_job(project_id)
    print(f"Job submitted: {job_id}")
    
    # 4. Wait for completion
    print("Waiting for extraction to complete...")
    result = client.wait_for_completion(job_id, poll_interval=30)
    print(f"Extraction complete!")
    
    # 5. Download results
    output_file = f"brim_results_{job_id}.csv"
    print(f"Downloading results to {output_file}...")
    client.download_results(job_id, output_file)
    
    return output_file
```

---

## 📋 Data Quality: FHIR-BRIM Validation

### Validation Strategy

```python
def validate_brim_results(brim_output_csv, fhir_context):
    """
    Compare BRIM extractions against FHIR ground truth.
    Flag discrepancies for human review.
    """
    
    import pandas as pd
    
    brim_df = pd.read_csv(brim_output_csv)
    validation_report = []
    
    # 1. Validate diagnoses
    for idx, row in brim_df.iterrows():
        brim_diagnosis = row.get('pathologic_diagnosis')
        hint_diagnosis = row.get('HINT_DIAGNOSIS')
        
        if pd.notna(brim_diagnosis) and pd.notna(hint_diagnosis):
            match = fuzzy_match(brim_diagnosis, hint_diagnosis)
            if match < 0.8:  # Less than 80% similarity
                validation_report.append({
                    'document_id': row['NOTE_ID'],
                    'field': 'diagnosis',
                    'fhir_value': hint_diagnosis,
                    'brim_value': brim_diagnosis,
                    'confidence': match,
                    'status': 'REVIEW_NEEDED'
                })
    
    # 2. Validate WHO grades
    for idx, row in brim_df.iterrows():
        brim_grade = row.get('who_grade')
        hint_grade = row.get('HINT_WHO_GRADE')
        
        if pd.notna(brim_grade) and pd.notna(hint_grade):
            if str(brim_grade).strip() != str(hint_grade).strip():
                validation_report.append({
                    'document_id': row['NOTE_ID'],
                    'field': 'who_grade',
                    'fhir_value': hint_grade,
                    'brim_value': brim_grade,
                    'confidence': 0.0,
                    'status': 'CONFLICT'
                })
    
    # 3. Generate confidence scores
    for idx, row in brim_df.iterrows():
        row['confidence_score'] = calculate_confidence(row, validation_report)
    
    return brim_df, pd.DataFrame(validation_report)
```

---

## 🎓 Best Practices

### 1. Always Sanitize HTML Before BRIM
```python
from bs4 import BeautifulSoup

def sanitize_html(content):
    """Remove HTML, JavaScript, CSS from clinical notes."""
    soup = BeautifulSoup(content, 'html.parser')
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'meta', 'link']):
        element.decompose()
    
    # Get text and normalize whitespace
    text = soup.get_text(separator=' ', strip=True)
    text = ' '.join(text.split())
    
    return text
```

### 2. Use HINT Columns Strategically
- **HINT_SURGERY_NUMBER**: Computed from FHIR procedure dates
- **HINT_DIAGNOSIS**: Most recent diagnosis before note date
- **HINT_WHO_GRADE**: Extracted from diagnosis code/text
- **HINT_MEDICATIONS**: Active medications at note date

### 3. Validate BRIM Variables Before Upload
```python
def validate_brim_variables(variables_csv):
    """Ensure BRIM variables CSV meets all requirements."""
    
    df = pd.read_csv(variables_csv)
    
    # Check column count
    assert len(df.columns) == 11, "Variables CSV must have exactly 11 columns"
    
    # Check surgery_number is first
    assert df.iloc[0]['variable_name'] == 'surgery_number', "surgery_number must be first variable"
    
    # Check for required fields
    required_columns = ['variable_name', 'instruction', 'variable_type', 'scope']
    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"
    
    # Validate scope values
    valid_scopes = ['one_per_note', 'many_per_note', 'one_per_patient']
    assert df['scope'].isin(valid_scopes).all(), "Invalid scope values found"
    
    return True
```

### 4. Handle Large Binary Content
```python
def extract_binary_content(binary_id, athena_connection, max_size_mb=10):
    """
    Extract and decode Binary content with size limits.
    """
    
    sql = """
    SELECT 
        contenttype,
        LENGTH(data) as size_bytes,
        data
    FROM binary
    WHERE id = :binary_id
    """
    
    result = execute_query(sql, binary_id=binary_id)
    
    if not result:
        return None
    
    size_mb = result['size_bytes'] / (1024 * 1024)
    if size_mb > max_size_mb:
        print(f"Warning: Binary {binary_id} is {size_mb:.2f}MB, skipping")
        return None
    
    # Decode base64
    import base64
    content = base64.b64decode(result['data']).decode('utf-8', errors='ignore')
    
    return content
```

---

## 📊 Expected Outcomes

### Efficiency Gains
- **75% reduction** in manual chart review time
- **Automated extraction** of 50+ variables per patient
- **Validated results** through FHIR-BRIM cross-checking

### Data Completeness
- **Structured data**: 95%+ capture from FHIR
- **Narrative data**: 80-90% capture from BRIM
- **Combined**: 90-95% overall completeness

### Quality Assurance
- Automated validation flags
- Confidence scores per extracted value
- Human review only for low-confidence extractions

---

## 🚀 Next Steps

1. **Implement FHIR extraction module** (`src/fhir_extractor.py`)
2. **Build BRIM CSV generator** (`src/brim_csv_generator.py`)
3. **Develop BRIM API client** (`src/brim_api_client.py`)
4. **Create validation framework** (`src/validation.py`)
5. **Build end-to-end pipeline** (`src/pipeline.py`)
6. **Document BRIM API endpoints** (pending API documentation)
7. **Test with sample patient** (validate full workflow)

---

## 📚 References

- BRIM Documentation: [Pending - API docs needed]
- FHIR R4 Specification: https://hl7.org/fhir/R4/
- Athena FHIR Schema: `e934bc57-fb76-433f-8fa5-4ccd3bffb0c2.csv`
- Prior BRIM Work: `/Users/resnick/Downloads/fhir_athena_crosswalk/documentation/`

---

**Author:** RADIANT Development Team  
**Last Updated:** October 1, 2025  
**Status:** Strategy Document - Implementation Pending
