# Binary File Extraction Framework

**Date**: 2025-10-20
**Purpose**: Framework for streaming and extracting clinical text from S3-stored binary files (PDF/HTML/RTF) for MedGemma LLM extraction

---

## Overview

This framework extends the multi-agent extraction architecture to handle binary files (PDF, HTML, RTF) stored in S3, enabling extraction from:
- **163 additional imaging reports** stored as HTML in v_binary_files
- **Pathology reports** (PDF)
- **Operative notes** (RTF)
- **Clinical notes** (HTML/RTF)

### Key Features

✅ **Streaming architecture** - No local file storage, directly streams from S3
✅ **Content-type agnostic** - Handles PDF, HTML, RTF, XML
✅ **Timeline integration** - Full temporal context from DuckDB timeline
✅ **Metadata preservation** - Tracks dates, document types, provenance
✅ **S3 naming bug handling** - Converts FHIR period (.) to S3 underscore (_)
✅ **Consistent with v_imaging pipeline** - Same extraction prompts and storage

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        MasterAgent                               │
│  (Orchestration, temporal context, extraction coordination)     │
└────────────┬────────────────────────────────────┬───────────────┘
             │                                     │
             v                                     v
┌────────────────────────────┐    ┌──────────────────────────────┐
│  BinaryExtractionInterface │    │   TimelineQueryInterface     │
│  - Query v_binary_files    │    │   - DuckDB timeline          │
│  - Stream from S3          │    │   - Temporal context         │
│  - Build temporal context  │    │   - Store results            │
└────────────┬───────────────┘    └──────────────────────────────┘
             │
             v
┌────────────────────────────┐
│    BinaryFileAgent         │
│  - S3 streaming            │
│  - PDF extraction          │
│  - HTML extraction         │
│  - RTF extraction          │
└────────────┬───────────────┘
             │
             v
┌────────────────────────────┐
│      MedGemmaAgent         │
│  - gemma2:27b via Ollama   │
│  - Structured extraction   │
│  - Confidence scoring      │
└────────────────────────────┘
```

---

## Data Flow

### 1. Binary File Discovery

Query v_binary_files (Athena) to find binary imaging reports:

```sql
SELECT
    binary_id,
    document_reference_id,
    patient_fhir_id,
    content_type,
    dr_type_text,
    dr_category_text,
    dr_description,
    dr_date,
    age_at_document_days
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = '{patient_id}'
AND dr_type_text = 'Diagnostic imaging study'
ORDER BY dr_date DESC
```

**Key Findings (Patient e4BwD8ZYDBccepXcJ.Ilo3w3):**
- **163 imaging reports** stored as HTML binary files
- **0 overlap** with v_imaging (51 reports) - different document_reference_ids
- IDs in v_binary_files start with "f" vs v_imaging IDs start with "e"

### 2. S3 Path Construction

**Critical S3 Naming Bug:**
- FHIR Binary IDs: `Binary/fmAXdcPPNkiCF9rr.5soVBQ`
- S3 file keys: `prd/source/Binary/fmAXdcPPNkiCF9rr_5soVBQ` (period → underscore)

```python
def construct_s3_path(binary_id: str) -> Tuple[str, str]:
    # Remove "Binary/" prefix
    file_id = binary_id.replace("Binary/", "")

    # Apply period-to-underscore conversion
    s3_file_id = file_id.replace('.', '_')

    # Construct full S3 key
    s3_key = f"prd/source/Binary/{s3_file_id}"

    return "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline", s3_key
```

### 3. Content Streaming & Extraction

**Stream from S3 (no local storage):**
```python
response = s3_client.get_object(Bucket=bucket, Key=key)
binary_content = response['Body'].read()
```

**Extract text based on content type:**

| Content Type | Extraction Method | Library |
|--------------|-------------------|---------|
| application/pdf | PyPDF2.PdfReader | PyPDF2 |
| text/html | BeautifulSoup | bs4 |
| text/rtf | HTML parser (RTF→HTML) | bs4 |
| text/xml | BeautifulSoup | bs4 |

### 4. Temporal Context Integration

Query DuckDB timeline for events ±30 days around document date:

```python
# Get surgeries in window
surgeries = timeline.query_events_by_type(
    patient_id=patient_id,
    event_types=['tumor_surgery'],
    start_date=(doc_date - 30 days).isoformat(),
    end_date=(doc_date + 30 days).isoformat()
)

# Calculate days from nearest surgery
closest_surgery_days = min(abs(surgery_date - doc_date) for surgery in surgeries)
```

**Context enriches extraction:**
- Imaging 2 days post-surgery → likely post-operative
- Imaging 500 days post-surgery → likely surveillance
- Imaging before any surgery → likely pre-operative

### 5. MedGemma Extraction

Same extraction pipeline as v_imaging:

```python
# Build context-enriched prompt
prompt = build_imaging_classification_prompt(
    report={'text': extracted_text, 'date': doc_date},
    context={
        'surgeries_in_window': surgeries,
        'closest_surgery_days': closest_surgery_days
    }
)

# Extract with MedGemma
result = medgemma_agent.extract(
    prompt=prompt,
    temperature=0.1
)

# Store in timeline database
timeline.store_extracted_variable(
    patient_id=patient_id,
    source_event_id=document_reference_id,
    variable_name="imaging_classification",
    variable_value=result.extracted_data['imaging_classification'],
    variable_confidence=result.confidence,
    extraction_method="medgemma_27b",
    source_document_type="binary_text/html",
    source_text=extracted_text[:1000],
    prompt_version="v1.0"
)
```

---

## File Structure

```
mvp/
├── agents/
│   ├── binary_file_agent.py              # S3 streaming & text extraction
│   ├── binary_extraction_interface.py    # Timeline integration
│   ├── medgemma_agent.py                 # LLM extraction (existing)
│   ├── master_agent.py                   # Orchestration (existing)
│   ├── extraction_prompts.py             # Shared prompts (existing)
│   ├── __init__.py
│   ├── README.md
│   └── BINARY_EXTRACTION_FRAMEWORK.md    # This document
│
├── scripts/
│   ├── run_binary_imaging_extraction.py  # CLI for binary extraction (NEW)
│   └── run_imaging_extraction.py         # CLI for v_imaging extraction (existing)
│
└── database/
    └── timeline_query_interface.py       # DuckDB interface (existing)
```

---

## Usage Examples

### Extract from Single Binary File

```python
import boto3
from agents.binary_file_agent import BinaryFileAgent

# Initialize agent
agent = BinaryFileAgent()

# Stream and extract
metadata = BinaryFileMetadata(
    binary_id="Binary/fmAXdcPPNkiCF9rr5soVBQ7Wly9JsBOVvuqX5AfBlnb44",
    document_reference_id="fmAXdcPPNkiCF9rr5soVBQ3",
    patient_fhir_id="e4BwD8ZYDBccepXcJ.Ilo3w3",
    content_type="text/html",
    dr_type_text="Diagnostic imaging study",
    dr_date="2024-05-15T10:30:00Z"
)

result = agent.extract_binary_content(metadata)

print(f"Success: {result.extraction_success}")
print(f"Text length: {result.text_length}")
print(f"First 500 chars: {result.extracted_text[:500]}")
```

### Extract All Binary Imaging for Patient

```python
from agents.binary_extraction_interface import BinaryExtractionInterface
from agents.binary_file_agent import BinaryFileAgent
from agents.medgemma_agent import MedGemmaAgent
from agents.master_agent import MasterAgent
from database.timeline_query_interface import TimelineQueryInterface
import boto3

# Initialize components
session = boto3.Session(profile_name='radiant-prod')
athena_client = session.client('athena')

binary_agent = BinaryFileAgent()
timeline = TimelineQueryInterface(db_path='data/timeline.duckdb')
medgemma = MedGemmaAgent(model_name="gemma2:27b")

interface = BinaryExtractionInterface(
    binary_agent=binary_agent,
    timeline_interface=timeline,
    athena_client=athena_client
)

master = MasterAgent(
    medgemma_agent=medgemma,
    timeline_interface=timeline,
    binary_interface=interface  # NEW parameter
)

# Run extraction on all binary imaging files
patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
results = master.orchestrate_binary_imaging_extraction(
    patient_id=patient_id,
    extraction_type="all"  # imaging_classification, extent_of_resection, tumor_status
)

print(f"Processed: {results['total_processed']}")
print(f"Success: {results['successful_extractions']}")
print(f"Failed: {results['failed_extractions']}")
```

---

## Data Storage

### extracted_variables Table Schema

```sql
CREATE TABLE extracted_variables (
    variable_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL,      -- document_reference_id from v_binary_files
    variable_name TEXT NOT NULL,         -- "imaging_classification", "extent_of_resection", etc.
    variable_value TEXT NOT NULL,        -- "pre_operative", "GTR", etc.
    variable_confidence REAL,            -- 0.0-1.0
    extraction_method TEXT,              -- "medgemma_27b"
    source_document_type TEXT,           -- "binary_text/html", "binary_application/pdf"
    source_text TEXT,                    -- First 1000 chars of extracted text
    prompt_version TEXT,                 -- "v1.0"
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Example Record

```python
{
    "variable_id": "ext_imaging_classification_fmAXdcPPNkiCF9rr5soVBQ3_1760927655",
    "patient_id": "e4BwD8ZYDBccepXcJ.Ilo3w3",
    "source_event_id": "fmAXdcPPNkiCF9rr5soVBQ3",
    "variable_name": "imaging_classification",
    "variable_value": "post_operative",
    "variable_confidence": 0.92,
    "extraction_method": "medgemma_27b",
    "source_document_type": "binary_text/html",
    "source_text": "CLINICAL HISTORY: Status post resection of cerebellar tumor...",
    "prompt_version": "v1.0",
    "extracted_at": "2025-10-20T02:45:30Z"
}
```

---

## Key Differences: v_imaging vs v_binary_files

| Aspect | v_imaging | v_binary_files |
|--------|-----------|----------------|
| **Data Source** | DiagnosticReport.result (text field) | S3 Binary files (PDF/HTML/RTF) |
| **Patient Count** | 51 imaging reports | 163 imaging reports |
| **ID Prefix** | "e..." | "f..." |
| **ID Overlap** | 0% (completely different documents) | 0% |
| **Access Method** | Direct SQL query to fhir_prd_db | Athena query + S3 streaming |
| **Text Extraction** | Already plain text | Requires PDF/HTML parsing |
| **Content Types** | N/A (plain text) | text/html (163), application/pdf, text/rtf |
| **Date Field** | result_date, imaging_date | dr_date |
| **Storage in Timeline** | source_event_id = result_diagnostic_report_id | source_event_id = document_reference_id |

---

## Performance Considerations

### Streaming vs Download

✅ **Streaming (implemented):**
- No local storage required
- Memory-efficient for large files
- Faster for single-file extraction

❌ **Batch download:**
- Could enable parallel extraction
- Requires cleanup logic
- Risk of disk space issues

### Extraction Speed

Based on v_imaging benchmarks:
- **MedGemma extraction**: ~20-30 seconds per report
- **S3 streaming**: ~1-2 seconds per file
- **Text extraction**: ~0.5 seconds per file
- **Total**: ~22-33 seconds per binary imaging report

**For 163 binary imaging reports:**
- Sequential: ~60-90 minutes
- With 4 parallel workers: ~15-25 minutes

---

## Error Handling

### S3 Errors

```python
try:
    binary_content = agent.stream_binary_from_s3(binary_id)
except agent.s3_client.exceptions.NoSuchKey:
    logger.error(f"File not found: {binary_id}")
    # Skip this document
except Exception as e:
    logger.error(f"S3 error: {e}")
    # Retry with exponential backoff
```

### Extraction Errors

```python
result = agent.extract_binary_content(metadata)

if not result.extraction_success:
    logger.warning(f"Extraction failed: {result.extraction_error}")
    # Store failure in timeline with confidence = 0.0
    timeline.store_extracted_variable(
        ...,
        variable_value="extraction_failed",
        variable_confidence=0.0,
        extraction_error=result.extraction_error
    )
```

### Date Parsing Errors

```python
try:
    event_date = datetime.fromisoformat(dr_date.replace('Z', '+00:00'))
except:
    logger.warning(f"Invalid date format: {dr_date}")
    event_date = None  # Still process, but no temporal context
```

---

## Testing

### Unit Tests

```bash
# Test S3 path construction
pytest tests/test_binary_file_agent.py::test_construct_s3_path

# Test period-to-underscore conversion
pytest tests/test_binary_file_agent.py::test_s3_naming_bug_fix

# Test PDF extraction
pytest tests/test_binary_file_agent.py::test_extract_pdf

# Test HTML extraction
pytest tests/test_binary_file_agent.py::test_extract_html
```

### Integration Tests

```bash
# Test single binary file extraction
python3 scripts/test_binary_extraction_single.py

# Test full pipeline (10 files)
python3 scripts/test_binary_extraction_pipeline.py --limit 10
```

---

## Next Steps

### Immediate

1. ✅ Design binary extraction framework
2. ✅ Implement BinaryFileAgent with S3 streaming
3. ✅ Implement BinaryExtractionInterface for timeline integration
4. ✅ Update S3 configuration with correct bucket/prefix
5. ⏳ Test on sample binary imaging files (3-5 files)
6. ⏳ Run full extraction on 163 binary imaging reports

### Future Enhancements

1. **Parallel Extraction** - 4-8 worker processes for faster batch extraction
2. **Content Type Detection** - Auto-detect content type if metadata incorrect
3. **OCR Support** - Extract text from scanned PDFs using pytesseract
4. **Progress Notes Extraction** - Extend to 1,277 Progress Notes binary files
5. **Operative Notes Extraction** - Extract from RTF operative notes
6. **Pathology Reports Extraction** - Extract from PDF pathology reports

---

## Configuration

### Environment Variables

```bash
# AWS Configuration
export AWS_PROFILE=radiant-prod
export AWS_REGION=us-east-1

# S3 Configuration
export S3_BUCKET=radiant-prd-343218191717-us-east-1-prd-ehr-pipeline
export S3_PREFIX=prd/source/Binary/

# Athena Configuration
export ATHENA_DATABASE=fhir_prd_db
export ATHENA_OUTPUT_LOCATION=s3://aws-athena-query-results-343218191717-us-east-1/

# Ollama Configuration
export OLLAMA_URL=http://localhost:11434
export MEDGEMMA_MODEL=gemma2:27b
```

### Dependencies

```txt
boto3>=1.28.0
PyPDF2>=3.0.0
beautifulsoup4>=4.12.0
duckdb>=0.9.0
requests>=2.31.0
```

---

## Troubleshooting

### Issue: S3 403 Forbidden

**Cause**: Incorrect AWS profile or permissions

**Solution**:
```bash
aws sso login --profile radiant-prod
export AWS_PROFILE=radiant-prod
```

### Issue: Binary file not found (404)

**Cause**: Period-to-underscore conversion not applied

**Solution**: Verify construct_s3_path() applies `.replace('.', '_')`

### Issue: HTML extraction returns empty string

**Cause**: Malformed HTML or encoding issue

**Solution**: Try multiple encodings (utf-8, latin-1, windows-1252)

---

## References

- [BINARY_DOCUMENT_DISCOVERY_WORKFLOW.md](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/BINARY_DOCUMENT_DISCOVERY_WORKFLOW.md) - Original S3 binary file discovery
- [check_binary_s3_availability.py](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/scripts/check_binary_s3_availability.py) - Existing S3 availability checker
- [TWO_AGENT_FRAMEWORK_ARCHITECTURE_PLAN.md](/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/TWO_AGENT_FRAMEWORK_ARCHITECTURE_PLAN.md) - Multi-agent architecture
- [agents/README.md](README.md) - Agent framework documentation

---

**Last Updated**: 2025-10-20
**Status**: Implementation complete, testing pending
**Next**: Test on 3-5 sample binary files
