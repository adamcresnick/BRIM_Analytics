# Binary File Identification Workflow

## Overview

The script identifies and retrieves Binary files (clinical notes) through a **3-step process** using FHIR DocumentReference resources as the index/pointer to Binary content.

---

## Step-by-Step Workflow

### **Step 1: Query DocumentReference NDJSON Files**

**Location:** `extract_clinical_notes()` method

**Process:**
1. List all DocumentReference NDJSON files in S3:
   ```
   s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/ndjson/DocumentReference/*.ndjson
   ```

2. Use **S3 Select** to query each file for patient's documents:
   ```sql
   SELECT *
   FROM S3Object[*] s
   WHERE s.subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'
   ```

3. **Current Limitation:** Only queries first 5 NDJSON files (pilot mode)
   ```python
   for file_key in files[:5]:  # Limit to first 5 files for pilot
   ```

4. **Result:** List of DocumentReference resources for the patient

**Why 0 documents found?**
- Patient's DocumentReference resources are likely in files beyond the first 5
- Or the patient may not have clinical notes in the system
- The DocumentReference files are partitioned/distributed, and we're only sampling a small subset

---

### **Step 2: Extract Binary ID from DocumentReference**

**Location:** `_process_document_reference()` method

**Process:**
1. Parse DocumentReference JSON structure:
   ```json
   {
     "id": "doc-12345",
     "date": "2024-01-15T10:30:00Z",
     "type": {
       "text": "Operative Note"
     },
     "subject": {
       "reference": "Patient/e4BwD8ZYDBccepXcJ.Ilo3w3"
     },
     "content": [
       {
         "attachment": {
           "url": "Binary/abc123-binary-id",
           "contentType": "text/html"
         }
       }
     ]
   }
   ```

2. Navigate to the Binary reference:
   ```python
   content = doc_ref.get('content', [])
   attachment = content[0].get('attachment', {})
   binary_url = attachment.get('url', '')
   # binary_url = "Binary/abc123-binary-id"
   ```

3. Extract Binary ID:
   ```python
   binary_id = binary_url.split('Binary/')[-1]
   # binary_id = "abc123-binary-id"
   ```

**Key Point:** DocumentReference acts as a **pointer/index** to the actual Binary content. It contains:
- Metadata about the note (date, type, author)
- Reference to the Binary resource containing the actual text

---

### **Step 3: Fetch Binary Content from S3**

**Location:** `_fetch_binary_content()` method

**Process:**
1. List Binary NDJSON files in S3:
   ```
   s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/ndjson/Binary/*.ndjson
   ```

2. **Current Limitation:** Only checks first 10 Binary files
   ```python
   response = self.s3_client.list_objects_v2(
       Bucket=self.s3_bucket,
       Prefix=binary_prefix,
       MaxKeys=10  # Limit for pilot
   )
   ```

3. Use **S3 Select** to query for specific Binary ID:
   ```sql
   SELECT * FROM S3Object[*] s WHERE s.id = 'abc123-binary-id'
   ```

4. Extract and decode the Binary content:
   ```python
   binary_resource = json.loads(payload)
   # Structure:
   {
     "id": "abc123-binary-id",
     "contentType": "text/html",
     "data": "PGh0bWw+...base64encoded..." 
   }
   
   data = binary_resource.get('data', '')
   decoded_text = base64.b64decode(data).decode('utf-8')
   ```

5. Sanitize HTML (if needed):
   ```python
   clean_text = self._sanitize_html(decoded_text)
   ```

**Why this might fail:**
- Binary resource is in a file beyond the first 10 checked
- Binary ID doesn't exist (orphaned DocumentReference)
- Base64 decoding fails
- Binary content is not text (e.g., PDF, image)

---

## Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Find Patient's DocumentReferences                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  S3: prd/ndjson/DocumentReference/*.ndjson (1000+ files)      │
│  ↓                                                              │
│  Query first 5 files with S3 Select                           │
│  WHERE subject.reference LIKE '%patient_id%'                   │
│  ↓                                                              │
│  Result: 0 DocumentReference resources found ❌                │
│  (Patient's docs are likely in files 6-1000)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Extract Binary ID from DocumentReference               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FOR EACH DocumentReference:                                    │
│    Parse: doc_ref.content[0].attachment.url                    │
│    Extract: "Binary/abc123-binary-id"                          │
│    Binary ID = "abc123-binary-id"                              │
│                                                                 │
│  (Skipped - no DocumentReferences found)                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Fetch Binary Content from S3                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  S3: prd/ndjson/Binary/*.ndjson (many files)                  │
│  ↓                                                              │
│  Check first 10 files with S3 Select                           │
│  WHERE id = 'abc123-binary-id'                                 │
│  ↓                                                              │
│  Extract: binary_resource.data (base64 encoded)                │
│  ↓                                                              │
│  Decode: base64.b64decode(data).decode('utf-8')               │
│  ↓                                                              │
│  Sanitize: Remove HTML tags, clean whitespace                  │
│  ↓                                                              │
│  Result: Clean note text ready for BRIM                        │
│                                                                 │
│  (Skipped - no Binary IDs to fetch)                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Current Pilot Limitations

### 1. **DocumentReference Sampling** (files[:5])
- **Impact:** Only checks 5 out of 1000+ DocumentReference files
- **Why:** Performance optimization for pilot testing
- **Result:** Missing most clinical notes
- **Fix:** Remove `[:5]` limit to query all files

### 2. **Binary File Sampling** (MaxKeys=10)
- **Impact:** Only checks first 10 Binary files per Binary ID
- **Why:** Performance optimization for pilot testing
- **Result:** May not find Binary content even if DocumentReference exists
- **Fix:** Remove `MaxKeys=10` limit or increase significantly

### 3. **Alternative: Use binary_resource_download_links.json**
The script loads this file but **doesn't currently use it**:
```python
# Currently loaded but unused:
self._load_binary_links()  # Loads 2.8M binary download links
```

**This file contains:**
```json
{
  "binary_id_1": "https://s3.../actual-download-url",
  "binary_id_2": "https://s3.../actual-download-url",
  ...
}
```

**Could be used to:**
1. Get Binary ID from DocumentReference
2. Look up direct S3 URL in binary_resource_download_links.json
3. Download Binary content directly (faster, no querying needed)

---

## Recommendations for Production

### Option 1: Query All DocumentReference Files
```python
# Remove limit
for file_key in files:  # Query ALL files, not just [:5]
    docs = self._query_s3_select(file_key)
    document_refs.extend(docs)
```

**Pros:** Most thorough approach  
**Cons:** Slower (1000+ S3 Select queries)

### Option 2: Use binary_resource_download_links.json
```python
def _fetch_binary_content(self, binary_id):
    """Fetch Binary using pre-indexed download links."""
    # Look up direct URL
    if binary_id in self.binary_links:
        s3_url = self.binary_links[binary_id]
        # Download directly from S3 URL
        return self._download_from_url(s3_url)
    return None
```

**Pros:** Much faster, no S3 Select queries  
**Cons:** Requires parsing 2.8M link JSON (already loaded)

### Option 3: Hybrid Approach
1. Query DocumentReference files more efficiently (parallel queries, pagination)
2. Use binary_resource_download_links.json for Binary content retrieval
3. Add caching for repeated queries

---

## Summary

**Current Workflow:**
```
DocumentReference NDJSON files → S3 Select (first 5 only) → Extract Binary ID 
→ Binary NDJSON files → S3 Select (first 10 only) → Decode base64 → Clean HTML
```

**Why 0 notes found:**
- Only searching 5 out of 1000+ DocumentReference files (0.5% sample)
- Patient's clinical notes are statistically likely to be in the other 99.5%

**Quick Fix:**
Remove the `[:5]` limit in line 86 of `pilot_generate_brim_csvs.py`:
```python
for file_key in files:  # Remove [:5] to query all files
```

**Expected Outcome:**
- Should find 10-100+ DocumentReference resources for this patient
- Will extract corresponding Binary content (clinical notes)
- project.csv will have multiple rows (FHIR Bundle + clinical notes)
