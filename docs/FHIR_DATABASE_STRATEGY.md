# FHIR Database Strategy for BRIM Analytics

## Overview

The BRIM Analytics workflow uses **two Athena databases** for querying FHIR resources:

- **`fhir_v2_prd_db`**: For most clinical data (condition, procedure, medication, observation, encounter)
- **`fhir_v1_prd_db`**: For DocumentReference data (v2 document_reference table incomplete)

This dual-database strategy ensures we get complete data while working around temporary limitations in the v2 document_reference table.

---

## Database Usage Matrix

| Resource Type | Database | Tables | Reason |
|---------------|----------|--------|--------|
| **Condition** | `fhir_v2_prd_db` | `condition` | v2 complete, optimized |
| **Procedure** | `fhir_v2_prd_db` | `procedure`, `procedure_code_coding`, `procedure_report` | v2 complete, optimized |
| **Medication** | `fhir_v2_prd_db` | `medication_request` | v2 complete, optimized |
| **Observation** | `fhir_v2_prd_db` | `observation` | v2 complete, optimized |
| **Encounter** | `fhir_v2_prd_db` | `encounter` | v2 complete, optimized |
| **DocumentReference** | `fhir_v1_prd_db` | `document_reference`, `document_reference_content` | **v2 incomplete** |

---

## DocumentReference Specifics

### Why Use v1 for Documents?

The `fhir_v2_prd_db.document_reference` table is **incomplete** and missing many documents. Until this is resolved, we use `fhir_v1_prd_db` for all document-related queries.

### Key Columns in v1

#### `fhir_v1_prd_db.document_reference`
- `id`: DocumentReference resource ID
- `subject_reference`: Patient reference (e.g., "Patient/e4BwD8ZYDBccepXcJ.Ilo3w3")
- `type_text`: Document type (e.g., "Pathology Report", "OP Note - Complete")
- `date`: Document date
- `status`: Document status ("current", "superseded")
- `description`: Document description

#### `fhir_v1_prd_db.document_reference_content`
- `document_reference_id`: Links to document_reference.id
- **`content_attachment_url`**: Binary reference URL ⭐ KEY COLUMN
- `content_attachment_size`: File size in bytes
- `content_attachment_content_type`: MIME type

### Binary Reference Format

**Example `content_attachment_url`**:
```
Binary/e.AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543
```

**Format**: `Binary/{binary_id}`

---

## S3 Binary File Retrieval

### Known Issue: Period → Underscore Replacement

**Problem**: Binary files in S3 have periods (`.`) replaced with underscores (`_`) in filenames.

**Example**:
```
Binary ID in FHIR:  e.AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543
S3 filename:        e_AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543
```

### S3 Path Structure

**Bucket**: `chop-radiantpca-prd-fhir`  
**Key Pattern**: `prd/source/Binary/{binary_id_with_underscores}`

**Full Example**:
```
s3://chop-radiantpca-prd-fhir/prd/source/Binary/e_AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543
```

### Retrieval Code Pattern

```python
# Extract Binary ID from content_attachment_url
binary_id = content_attachment_url.split('Binary/')[-1]
# Example: "e.AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543"

# CRITICAL: Replace periods with underscores for S3 lookup
s3_filename = binary_id.replace('.', '_')
# Result: "e_AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543"

# Construct S3 key
s3_key = f"prd/source/Binary/{s3_filename}"

# Fetch from S3
response = s3_client.get_object(
    Bucket='chop-radiantpca-prd-fhir',
    Key=s3_key
)
```

---

## Complete Query Examples

### Query 1: Diagnosis Date (v2)

```sql
SELECT 
    onset_date_time,
    code_text,
    clinical_status
FROM fhir_v2_prd_db.condition
WHERE subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND LOWER(code_text) LIKE '%astrocytoma%'
    AND verification_status = 'confirmed'
ORDER BY onset_date_time
LIMIT 1
```

**Use Case**: Pre-populate `diagnosis_date` field

---

### Query 2: Surgery Dates (v2)

```sql
SELECT 
    p.performed_date_time,
    p.code_text,
    pcc.code_coding_code as cpt_code
FROM fhir_v2_prd_db.procedure p
LEFT JOIN fhir_v2_prd_db.procedure_code_coding pcc 
    ON p.id = pcc.procedure_id
WHERE p.subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND p.status = 'completed'
    AND pcc.code_coding_code IN ('61510', '61512', '61518', '61520', '61521')
ORDER BY p.performed_date_time
```

**Use Case**: Pre-populate `surgery_dates` and `total_surgeries` fields

---

### Query 3: Prioritized Documents (v1)

```sql
SELECT 
    dr.id as document_id,
    dr.type_text,
    dr.date as document_date,
    drc.content_attachment_url as binary_url,
    drc.content_attachment_size as file_size,
    
    -- Document type priority
    CASE
        WHEN LOWER(dr.type_text) LIKE '%pathology%' THEN 100
        WHEN LOWER(dr.type_text) LIKE '%op note%' THEN 95
        WHEN LOWER(dr.type_text) LIKE '%radiology%' THEN 85
        ELSE 50
    END as priority_score
    
FROM fhir_v1_prd_db.document_reference dr
LEFT JOIN fhir_v1_prd_db.document_reference_content drc 
    ON dr.id = drc.document_reference_id
WHERE dr.subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND dr.status = 'current'
    AND drc.content_attachment_size < 10000000  -- Max 10MB
ORDER BY priority_score DESC, dr.date DESC
LIMIT 100
```

**Use Case**: Get prioritized list of documents for BRIM extraction

---

### Query 4: Procedure-Linked Documents (v2 procedure + v1 document)

```sql
-- Find procedures with linked documents (v2 for procedure, v1 for document verification)
SELECT DISTINCT
    p.id as procedure_id,
    p.performed_date_time,
    pr.reference as document_reference,
    REGEXP_EXTRACT(pr.reference, 'DocumentReference/(.+)') as document_id
FROM fhir_v2_prd_db.procedure p
LEFT JOIN fhir_v2_prd_db.procedure_report pr 
    ON p.id = pr.procedure_id
WHERE p.subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND pr.reference LIKE 'DocumentReference/%'
ORDER BY p.performed_date_time
```

**Use Case**: Force-include operative notes linked to surgical procedures

---

### Query 5: Molecular Markers (v2)

```sql
SELECT 
    code_text,
    value_string,
    effective_datetime
FROM fhir_v2_prd_db.observation
WHERE subject_reference = 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND code_text = 'Genomics Interpretation'
    AND value_string IS NOT NULL
ORDER BY effective_datetime DESC
```

**Use Case**: Pre-populate molecular marker fields (BRAF, IDH1, MGMT)

---

## Implementation Scripts

### `extract_structured_data.py`
**Purpose**: Query v2 for clinical data (diagnosis, surgeries, treatments, molecular markers)

**Databases Used**:
- `fhir_v2_prd_db`: condition, procedure, medication_request, observation

**Output**: `structured_data.json` with pre-populated fields

---

### `athena_document_prioritizer.py`
**Purpose**: Query v1 for prioritized DocumentReference list

**Databases Used**:
- `fhir_v2_prd_db`: condition, procedure, medication_request (for clinical timeline)
- `fhir_v1_prd_db`: document_reference, document_reference_content (for documents)

**Output**: `prioritized_documents.json` with top 100 documents

---

### `pilot_generate_brim_csvs.py`
**Purpose**: Generate BRIM CSVs with documents and structured data

**Inputs**:
- FHIR bundle (from HealthLake view or S3)
- Structured data JSON (from `extract_structured_data.py`)
- Prioritized documents JSON (optional, from `athena_document_prioritizer.py`)

**Binary Retrieval**:
- Extract Binary ID from DocumentReference
- Replace periods with underscores
- Fetch from S3: `prd/source/Binary/{id_with_underscores}`

---

## Migration Path to v2

Once `fhir_v2_prd_db.document_reference` is complete, we can migrate:

### Step 1: Update Database References
```python
# OLD (current)
document_database = 'fhir_v1_prd_db'

# NEW (after v2 complete)
document_database = 'fhir_v2_prd_db'
```

### Step 2: Verify Column Names
Ensure v2 has same schema as v1:
- `document_reference_content.content_attachment_url` exists
- Binary ID format matches

### Step 3: Test Queries
Run test queries on v2 to confirm:
- Same document count as v1
- Binary URLs are valid
- content_attachment_url format matches

### Step 4: Update Scripts
Change all document queries to use `fhir_v2_prd_db` instead of `fhir_v1_prd_db`

---

## Best Practices

### 1. Always Specify Database Explicitly
```python
# GOOD - Explicit database for each resource type
condition_query = f"SELECT * FROM {v2_database}.condition WHERE ..."
document_query = f"SELECT * FROM {v1_database}.document_reference WHERE ..."

# BAD - Ambiguous database
query = "SELECT * FROM condition WHERE ..."  # Which database?
```

### 2. Handle Binary ID Period Bug
```python
# ALWAYS replace periods before S3 lookup
binary_id = "e.AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543"
s3_filename = binary_id.replace('.', '_')  # "e_AHt-I..."
```

### 3. Validate Results
```python
# Check if v2 returned expected data
if df.empty:
    logger.warning("No results from v2, check if data complete")

# Verify Binary exists before fetching
try:
    response = s3_client.head_object(Bucket=bucket, Key=s3_key)
except ClientError:
    logger.warning(f"Binary not found: {s3_key}")
```

### 4. Log Database Usage
```python
logger.info(f"Querying {database_name}.{table_name} for patient {patient_id}")
```

---

## Troubleshooting

### Problem: No documents returned from v1
**Solution**: Verify patient FHIR ID format matches v1 (may differ from v2)

### Problem: Binary not found in S3
**Solution**: Check if period→underscore replacement applied

### Problem: Query timeout on v1
**Solution**: Add more specific WHERE clauses, limit result count

### Problem: Duplicate data between v1 and v2
**Solution**: Use DISTINCT and order by date DESC, limit to latest

---

## Summary

| Component | v2 Database | v1 Database |
|-----------|-------------|-------------|
| Clinical timeline | ✅ condition, procedure, medication | ❌ |
| Document list | ❌ | ✅ document_reference |
| Binary URLs | ❌ | ✅ document_reference_content.content_attachment_url |
| Structured data extraction | ✅ | ❌ |
| Document prioritization | ✅ (for timeline) | ✅ (for documents) |

**Key Takeaway**: Use v2 for everything **except** document_reference queries. Always replace periods with underscores when fetching Binary files from S3.
