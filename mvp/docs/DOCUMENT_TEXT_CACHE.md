# Document Text Cache with Full Provenance

## Overview

The Document Text Cache system stores extracted text from binary files (PDFs, HTML) with complete provenance, eliminating the need to reprocess files when extracting new variables.

**Key Benefits:**
- 🚀 **Performance**: Extract once, reuse indefinitely
- 💰 **Cost**: Avoid repeated S3 API calls and PDF parsing
- 📋 **Provenance**: Complete audit trail for reproducibility
- 🔄 **Flexibility**: Re-extract new variables from cached text
- 📌 **Versioning**: Track extraction method changes over time

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FIRST EXTRACTION                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Query Athena → Get document metadata                │
│  2. Fetch from S3 → Get binary content (PDF/HTML)       │
│  3. Extract text → PyMuPDF or BeautifulSoup             │
│  4. Cache text → Store in DuckDB with provenance        │
│  5. Send to Agent 2 → Extract disease_state             │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              SUBSEQUENT EXTRACTIONS (FASTER)             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Query cache → Get cached text (no S3, no parsing!)  │
│  2. Send to Agent 2 → Extract NEW_VARIABLE              │
│                                                          │
│  Performance: ~100x faster, no S3 costs                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Storage Schema

**Database**: DuckDB table `extracted_document_text` in timeline.duckdb

```sql
CREATE TABLE extracted_document_text (
    -- Primary identifiers
    document_id VARCHAR PRIMARY KEY,          -- DocumentReference ID
    patient_fhir_id VARCHAR NOT NULL,
    binary_id VARCHAR,                        -- FHIR Binary ID

    -- Document metadata
    document_type VARCHAR NOT NULL,           -- imaging_report, progress_note, operative_report
    document_date TIMESTAMP NOT NULL,
    content_type VARCHAR NOT NULL,            -- application/pdf, text/html, text/plain
    dr_type_text VARCHAR,                     -- FHIR document type
    dr_category_text VARCHAR,                 -- FHIR category
    dr_description VARCHAR,

    -- Extracted text
    extracted_text VARCHAR NOT NULL,          -- Full document text
    text_length INTEGER NOT NULL,
    text_hash VARCHAR NOT NULL,               -- SHA256 for deduplication

    -- Extraction provenance
    extraction_timestamp TIMESTAMP NOT NULL,
    extraction_method VARCHAR NOT NULL,       -- pdf_pymupdf, html_beautifulsoup, text_direct
    extraction_version VARCHAR NOT NULL,      -- e.g., "v1.1"
    extractor_agent VARCHAR NOT NULL,         -- binary_file_agent, athena_query

    -- S3 provenance (for binary files)
    s3_bucket VARCHAR,
    s3_key VARCHAR,
    s3_last_modified TIMESTAMP,

    -- Processing status
    extraction_success BOOLEAN NOT NULL,
    extraction_error VARCHAR,

    -- Metadata
    age_at_document_days INTEGER,
    additional_metadata VARCHAR,              -- JSON for extensibility
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Usage Examples

### 1. Basic Workflow with Caching

```python
from utils.document_text_cache import DocumentTextCache, create_cached_document_from_binary_extraction
from agents.binary_file_agent import BinaryFileAgent

# Initialize
cache = DocumentTextCache()
binary_agent = BinaryFileAgent()

# For each PDF/HTML document
for doc_metadata in pdf_documents:
    document_id = doc_metadata['document_reference_id']

    # Check cache first
    cached = cache.get_cached_document(document_id)

    if cached:
        # Use cached text (no S3 fetch, no parsing!)
        document_text = cached.extracted_text
        print(f"✓ Using cached text ({cached.text_length} chars)")
    else:
        # Extract and cache
        extracted = binary_agent.extract_binary_content(doc_metadata)

        # Cache for future use
        cached_doc = create_cached_document_from_binary_extraction(
            extracted,
            document_type="imaging_report"
        )
        cache.cache_document(cached_doc)

        document_text = extracted.extracted_text
        print(f"✓ Extracted and cached ({len(document_text)} chars)")

    # Now use document_text for extraction
    result = medgemma.extract(build_prompt(document_text))
```

### 2. Extract New Variable from Cached Text

```python
# Later, when you need to extract a NEW variable (e.g., tumor_location)
# You can use the cached text without re-fetching from S3 or re-parsing PDFs!

cache = DocumentTextCache()

# Get all cached documents for patient
cached_docs = cache.get_patient_documents(
    patient_fhir_id="Patient/123",
    document_type="imaging_report"
)

print(f"Found {len(cached_docs)} cached imaging reports")

# Extract NEW variable from cached text
for doc in cached_docs:
    # Use cached text directly (no S3, no PDF parsing!)
    tumor_location_prompt = build_tumor_location_prompt(doc.extracted_text)
    result = medgemma.extract(tumor_location_prompt)

    # Store extraction
    store_variable('tumor_location', result, doc.document_id)
```

### 3. Export Patient Cache

```python
from pathlib import Path

cache = DocumentTextCache()

# Export all cached documents for a patient to JSON
cache.export_patient_cache(
    patient_fhir_id="Patient/123",
    output_path=Path("data/patient_caches/patient_123_cache.json")
)

# Output JSON format:
# {
#   "patient_fhir_id": "Patient/123",
#   "export_timestamp": "2025-10-20T10:30:00",
#   "document_count": 186,
#   "documents": [
#     {
#       "document_id": "DocumentReference/xyz",
#       "document_type": "imaging_report",
#       "document_date": "2018-05-27",
#       "extracted_text": "MRI Brain with contrast...",
#       "text_length": 2847,
#       "extraction_method": "pdf_pymupdf",
#       "extraction_version": "v1.1",
#       "s3_bucket": "radiant-prd-...",
#       "s3_key": "prd/source/Binary/...",
#       ...
#     }
#   ]
# }
```

### 4. Cache Statistics

```python
cache = DocumentTextCache()

# Get cache statistics for a patient
stats = cache.get_cache_stats(patient_fhir_id="Patient/123")

print(f"Total documents: {stats['total_documents']}")
print(f"Total characters: {stats['total_characters']:,}")
print(f"Success rate: {stats['success_rate']}%")
print(f"By type: {stats['by_document_type']}")
print(f"By content: {stats['by_content_type']}")

# Example output:
# Total documents: 186
# Total characters: 487,239
# Success rate: 98.4%
# By type: {'imaging_report': 104, 'progress_note': 72, 'operative_report': 10}
# By content: {'application/pdf': 104, 'text/html': 82}
```

### 5. Check Before Extraction

```python
cache = DocumentTextCache()

# Only extract if not already cached
if not cache.is_cached(document_id):
    # Expensive operation (S3 + PDF parsing)
    extracted = binary_agent.extract_binary_content(metadata)

    # Cache for future use
    cached_doc = create_cached_document_from_binary_extraction(
        extracted,
        document_type="progress_note"
    )
    cache.cache_document(cached_doc)
```

## Integration with Workflows

### Full Multi-Source Workflow with Caching

```python
# scripts/run_full_multi_source_abstraction.py

from utils.document_text_cache import (
    DocumentTextCache,
    create_cached_document_from_binary_extraction,
    create_cached_document_from_imaging_text
)
from agents.binary_file_agent import BinaryFileAgent

# Initialize
cache = DocumentTextCache()
binary_agent = BinaryFileAgent()

# Phase 1: Cache imaging text reports (from v_imaging)
for report in imaging_text_reports:
    if not cache.is_cached(report['diagnostic_report_id']):
        cached_doc = create_cached_document_from_imaging_text(report)
        cache.cache_document(cached_doc)

# Phase 2: Extract and cache PDFs (from v_binary_files)
for pdf in imaging_pdfs:
    doc_id = pdf['document_reference_id']

    if cache.is_cached(doc_id):
        cached = cache.get_cached_document(doc_id)
        pdf_text = cached.extracted_text
    else:
        # Extract from S3
        extracted = binary_agent.extract_binary_content(pdf)

        # Cache it
        cached_doc = create_cached_document_from_binary_extraction(
            extracted,
            document_type="imaging_report"
        )
        cache.cache_document(cached_doc)

        pdf_text = extracted.extracted_text

    # Send to Agent 2
    result = medgemma.extract(build_prompt(pdf_text))

# Phase 3: Extract and cache progress notes
for note in prioritized_progress_notes:
    doc_id = note['document_reference_id']

    if cache.is_cached(doc_id):
        cached = cache.get_cached_document(doc_id)
        note_text = cached.extracted_text
    else:
        # Extract from S3
        extracted = binary_agent.extract_binary_content(note)

        # Cache it
        cached_doc = create_cached_document_from_binary_extraction(
            extracted,
            document_type="progress_note"
        )
        cache.cache_document(cached_doc)

        note_text = extracted.extracted_text

    # Send to Agent 2
    result = medgemma.extract(build_disease_state_prompt(note_text))
```

## Provenance Fields

Each cached document includes complete provenance:

### Extraction Metadata
- `extraction_timestamp`: When text was extracted
- `extraction_method`: How it was extracted (pdf_pymupdf, html_beautifulsoup, text_direct)
- `extraction_version`: Code version (e.g., "v1.1")
- `extractor_agent`: Which agent performed extraction (binary_file_agent, athena_query)

### Source Metadata
- `s3_bucket`: S3 bucket (for binary files)
- `s3_key`: S3 object key
- `s3_last_modified`: S3 object last modified timestamp

### Document Metadata
- `document_type`: Classification (imaging_report, progress_note, operative_report)
- `document_date`: Clinical date
- `content_type`: MIME type (application/pdf, text/html, text/plain)
- `dr_type_text`: FHIR DocumentReference type
- `dr_category_text`: FHIR category
- `dr_description`: Document description

### Text Metadata
- `text_hash`: SHA256 hash for deduplication
- `text_length`: Character count
- `extraction_success`: Boolean flag
- `extraction_error`: Error message if failed

## Performance Benefits

### Example: Extracting 5 Variables from 200 Documents

**Without Caching:**
```
For each variable:
  For each document:
    1. Query Athena (0.5s)
    2. Fetch from S3 (0.8s)
    3. Parse PDF (2.0s)
    4. Extract variable (5s)
    Total: ~8.3s per document

5 variables × 200 docs × 8.3s = 2.3 hours
Cost: ~$5 in S3 API calls
```

**With Caching:**
```
First variable:
  For each document:
    1. Query Athena (0.5s)
    2. Fetch from S3 (0.8s)
    3. Parse PDF (2.0s)
    4. Cache text (0.1s)
    5. Extract variable (5s)
    Total: ~8.4s per document

  200 docs × 8.4s = 28 minutes

Remaining 4 variables:
  For each document:
    1. Load from cache (0.01s)
    2. Extract variable (5s)
    Total: ~5s per document

  4 variables × 200 docs × 5s = 67 minutes

Total: 95 minutes (vs 2.3 hours)
Cost: ~$1 in S3 API calls (vs $5)
Speedup: 1.45x faster, 80% cost reduction
```

## Versioning and Updates

When extraction logic changes (e.g., improved PDF parsing), increment `EXTRACTION_VERSION`:

```python
class DocumentTextCache:
    EXTRACTION_VERSION = "v1.2"  # Increment when logic changes
```

Documents extracted with old versions remain in cache but can be identified:

```python
# Find documents extracted with old version
old_docs = cache.conn.execute("""
    SELECT document_id, extraction_version
    FROM extracted_document_text
    WHERE extraction_version < 'v1.2'
""").fetchall()

# Re-extract if needed
for doc_id, old_version in old_docs:
    # Re-extract and update cache
    ...
```

## Deduplication

The `text_hash` field (SHA256) enables deduplication:

```python
# Find duplicate documents (same text, different IDs)
duplicates = cache.conn.execute("""
    SELECT text_hash, COUNT(*) as count, GROUP_CONCAT(document_id) as ids
    FROM extracted_document_text
    WHERE patient_fhir_id = ?
    GROUP BY text_hash
    HAVING count > 1
""", [patient_id]).fetchall()

for hash_val, count, ids in duplicates:
    print(f"Found {count} documents with identical text: {ids}")
```

## Best Practices

1. **Always check cache first** before expensive S3/PDF operations
2. **Cache immediately after extraction** to benefit future runs
3. **Use cache for all re-extractions** of new variables
4. **Export patient caches** before major system changes
5. **Version your extraction code** and increment `EXTRACTION_VERSION`
6. **Monitor cache statistics** to ensure high success rates
7. **Deduplicate periodically** using `text_hash`

## Troubleshooting

### Issue: Cache miss for document that should be cached

**Check:**
```python
# Verify document exists
exists = cache.is_cached(document_id)
print(f"Document cached: {exists}")

# Check extraction success
cached = cache.get_cached_document(document_id)
if cached:
    print(f"Success: {cached.extraction_success}")
    print(f"Error: {cached.extraction_error}")
```

### Issue: Low success rate

**Check:**
```python
stats = cache.get_cache_stats(patient_id)
print(f"Success rate: {stats['success_rate']}%")

# Get failed extractions
failed = cache.conn.execute("""
    SELECT document_id, content_type, extraction_error
    FROM extracted_document_text
    WHERE extraction_success = false
    LIMIT 10
""").fetchall()

for doc_id, content_type, error in failed:
    print(f"{doc_id} ({content_type}): {error}")
```

### Issue: Slow cache queries

**Check indexes:**
```sql
-- Verify indexes exist
SHOW INDEXES FROM extracted_document_text;

-- Expected indexes:
-- idx_extracted_text_patient (patient_fhir_id)
-- idx_extracted_text_type (document_type, document_date)
-- idx_extracted_text_hash (text_hash)
```

## API Reference

See [document_text_cache.py](../utils/document_text_cache.py) for complete API documentation.

### Key Classes
- `DocumentTextCache`: Main cache interface
- `CachedDocument`: Document with full provenance

### Key Functions
- `cache_document()`: Store extracted text
- `get_cached_document()`: Retrieve by ID
- `get_patient_documents()`: Get all for patient
- `is_cached()`: Quick existence check
- `get_cache_stats()`: Statistics
- `export_patient_cache()`: Export to JSON
