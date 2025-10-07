# Document Metadata Fields & Resources Reference
**Date**: October 4, 2025
**Purpose**: Complete reference of all metadata fields and resources for filtering/identifying clinical documents

---

## Document Metadata Sources Discovered

### 1. **document_reference Table** (Main Resource)

**Primary Identification Fields**:
- `id` - Document reference ID (primary key)
- `subject_reference` - Patient FHIR ID
- `date` - Document date
- `status` - Document status ('current', 'superseded', etc.)

**Document Context Fields**:
- `context_period_start` - Context period start date
- `context_period_end` - Context period end date
- `context_facility_type_text` - Facility type (hospital-level)
- **`context_practice_setting_text`** ⭐ - **Practice setting (e.g., "Ophthalmology", "Oncology")**
- `context_source_patient_info_reference` - Source patient info
- `context_source_patient_info_type` - Source type
- `context_source_patient_info_display` - Source display

---

### 2. **document_reference_type_coding Table** (Document Type)

**What it provides**: Document type classification (can have multiple per document)

**Key Fields**:
- `document_reference_id` - Links to document_reference.id
- **`type_coding_display`** ⭐ - **Human-readable document type**
  - Examples: "Progress Notes", "Consult Note", "Pathology study", "MR Brain W & W/O IV Contrast"
- `type_coding_code` - Type code
- `type_coding_system` - Coding system URI

**Usage**:
```sql
SELECT dr.id, tc.type_coding_display
FROM document_reference dr
JOIN document_reference_type_coding tc ON dr.id = tc.document_reference_id
```

---

### 3. **document_reference_category Table** (Document Category)

**What it provides**: Document category classification

**Key Fields**:
- `document_reference_id` - Links to document_reference.id
- **`category_text`** - Category text
  - Examples: "Clinical Note", "Summary Document", "Document Information"
- `category_coding_code` - Category code
- `category_coding_display` - Category coding display

---

### 4. **document_reference_content Table** (Content/Binary Info)

**What it provides**: Content attachment details and Binary references

**Key Fields**:
- `document_reference_id` - Links to document_reference.id
- **`content_attachment_content_type`** ⭐ - **MIME type**
  - Examples: "text/html", "text/rtf", "application/pdf", "image/tiff"
- `content_attachment_url` - Binary URL
- `content_attachment_creation` - Creation date

**Usage**: Essential for filtering to text-based extractable documents

---

### 5. **document_reference_context_encounter Table** ⭐ (Encounter Links)

**What it provides**: Links documents to encounters

**Key Fields**:
- `document_reference_id` - Links to document_reference.id
- **`context_encounter_reference`** ⭐ - **Encounter ID**

**Usage**: Connect documents to encounters, then filter encounters by specialty/type
```sql
-- Find documents for specific encounters
SELECT drce.document_reference_id, drce.context_encounter_reference
FROM document_reference_context_encounter drce
WHERE drce.context_encounter_reference IN ('enc1', 'enc2', ...)
```

**Limitation**: Encounter types are generic ("Office Visit"), not specialty-specific

---

### 6. **encounter Table** (Encounter Information)

**What it provides**: Encounter context (for linking via document_reference_context_encounter)

**Key Fields**:
- `id` - Encounter ID
- `subject_reference` - Patient FHIR ID
- `status` - Encounter status ('finished', etc.)
- `class_code` - Encounter class code
- `class_display` - Encounter class display
- `period_start` - Encounter start date
- `period_end` - Encounter end date
- `service_provider_display` - Service provider (usually hospital-level)

**Limitation**: Service provider is hospital-level ("Children's Hospital of Philadelphia"), not department

---

### 7. **encounter_type Table** (Encounter Type)

**What it provides**: Encounter type classification

**Key Fields**:
- `encounter_id` - Links to encounter.id
- **`type_text`** - Encounter type text
  - Examples: "Office Visit", "Telephone", "Outpatient", "Refill", "ROUTINE ONCO VISIT"

**Limitation**: Types are generic, not specialty-specific

---

### 8. **encounter_participant Table** (Provider Information)

**What it provides**: Providers/participants in encounters

**Key Fields**:
- `encounter_id` - Links to encounter.id
- `individual_display` - Provider name
- `individual_reference` - Provider FHIR reference

**Limitation**: Provider names without specialty information

---

## Key Metadata Fields for Document Selection

### **TIER 1: Essential for Document Identification** ⭐⭐⭐

1. **`context_practice_setting_text`** (document_reference)
   - **Use**: Filter by clinical specialty
   - **Examples**: "Ophthalmology", "Oncology", "Neurosurgery"
   - **Query Pattern**:
   ```sql
   WHERE LOWER(context_practice_setting_text) LIKE '%ophthalmology%'
   ```

2. **`type_coding_display`** (document_reference_type_coding)
   - **Use**: Filter by document type
   - **Examples**: "Progress Notes", "Consult Note", "Pathology study"
   - **Query Pattern**:
   ```sql
   WHERE type_coding_display IN ('Progress Notes', 'Consult Note')
   ```

3. **`content_attachment_content_type`** (document_reference_content)
   - **Use**: Filter to extractable formats
   - **Examples**: "text/html", "text/rtf" (extractable), "application/pdf" (OCR), "image/tiff" (skip)
   - **Query Pattern**:
   ```sql
   WHERE content_attachment_content_type IN ('text/html', 'text/rtf')
   ```

4. **`date`** (document_reference)
   - **Use**: Filter by time period
   - **Examples**: Treatment milestones (2018-06, 2019-05, 2021-03)
   - **Query Pattern**:
   ```sql
   WHERE date >= '2018-06-01' AND date <= '2018-06-30'
   ```

### **TIER 2: Useful for Additional Context** ⭐⭐

5. **`category_text`** (document_reference_category)
   - **Use**: Broad categorization
   - **Examples**: "Clinical Note", "Summary Document"

6. **`context_period_start/end`** (document_reference)
   - **Use**: Encounter date ranges
   - **Note**: Different from document.date

7. **`context_encounter_reference`** (document_reference_context_encounter)
   - **Use**: Link to encounters (though limited specialty info)

### **TIER 3: Available but Less Useful** ⭐

8. **`context_facility_type_text`** (document_reference)
   - **Use**: Facility type
   - **Limitation**: Usually empty or hospital-level only

9. **`encounter.type_text`** (via encounter_type)
   - **Use**: Encounter type
   - **Limitation**: Generic ("Office Visit", not "Ophthalmology Visit")

10. **`service_provider_display`** (encounter)
    - **Use**: Service provider
    - **Limitation**: Hospital-level only

---

## Practical Document Selection Patterns

### Pattern 1: Filter by Practice Setting (RECOMMENDED) ⭐⭐⭐

**Use Case**: Find all ophthalmology documents

```sql
SELECT dr.id, tc.type_coding_display, dr.date
FROM document_reference dr
LEFT JOIN document_reference_type_coding tc ON dr.id = tc.document_reference_id
WHERE dr.subject_reference = 'PATIENT_ID'
  AND dr.status = 'current'
  AND LOWER(dr.context_practice_setting_text) LIKE '%ophthalmology%'
ORDER BY dr.date DESC
```

**Result for C1277724**: 18 ophthalmology documents (12 Progress Notes, 6 Consult Notes)

---

### Pattern 2: Filter by Document Type + Content Type

**Use Case**: Find extractable progress notes

```sql
SELECT dr.id, tc.type_coding_display, drc.content_attachment_content_type, dr.date
FROM document_reference dr
JOIN document_reference_type_coding tc ON dr.id = tc.document_reference_id
JOIN document_reference_content drc ON dr.id = drc.document_reference_id
WHERE dr.subject_reference = 'PATIENT_ID'
  AND dr.status = 'current'
  AND tc.type_coding_display = 'Progress Notes'
  AND drc.content_attachment_content_type IN ('text/html', 'text/rtf')
ORDER BY dr.date DESC
```

---

### Pattern 3: Filter by Date Range + Document Type

**Use Case**: Find documents around treatment milestones

```sql
SELECT dr.id, tc.type_coding_display, dr.date
FROM document_reference dr
JOIN document_reference_type_coding tc ON dr.id = tc.document_reference_id
WHERE dr.subject_reference = 'PATIENT_ID'
  AND dr.status = 'current'
  AND dr.date >= '2018-06-01' AND dr.date <= '2018-06-30'
  AND tc.type_coding_display IN ('Progress Notes', 'Consult Note', 'Pathology study')
ORDER BY dr.date DESC
```

---

### Pattern 4: Combine Multiple Filters (OPTIMAL) ⭐⭐⭐

**Use Case**: Targeted document selection for specific variables

```sql
SELECT dr.id, tc.type_coding_display, dr.date,
       dr.context_practice_setting_text,
       drc.content_attachment_content_type
FROM document_reference dr
JOIN document_reference_type_coding tc ON dr.id = tc.document_reference_id
JOIN document_reference_content drc ON dr.id = drc.document_reference_id
WHERE dr.subject_reference = 'PATIENT_ID'
  AND dr.status = 'current'
  AND (
    -- Ophthalmology documents
    LOWER(dr.context_practice_setting_text) LIKE '%ophthalmology%'
    OR
    -- Progress notes from key treatment periods
    (tc.type_coding_display = 'Progress Notes'
     AND dr.date IN ('2018-06-01'::date, '2019-05-01'::date, '2021-03-01'::date))
    OR
    -- All imaging reports
    (LOWER(tc.type_coding_display) LIKE '%imaging%'
     OR LOWER(tc.type_coding_display) LIKE '%MR %')
  )
  AND drc.content_attachment_content_type IN ('text/html', 'text/rtf')
ORDER BY dr.date DESC
```

---

## Summary: Best Practice Metadata Usage

### For Optimal Document Selection:

**Step 1**: Filter by **patient** and **status**
```sql
WHERE subject_reference = 'PATIENT_ID' AND status = 'current'
```

**Step 2**: Filter by **practice setting** (if specialty-specific)
```sql
AND context_practice_setting_text = 'Ophthalmology'
```

**Step 3**: Filter by **document type**
```sql
AND type_coding_display IN ('Progress Notes', 'Consult Note', 'Imaging Report')
```

**Step 4**: Filter by **content type** (extractability)
```sql
AND content_attachment_content_type IN ('text/html', 'text/rtf')
```

**Step 5**: Filter by **date range** (optional, for targeted periods)
```sql
AND date >= '2018-06-01' AND date <= '2018-06-30'
```

---

## Discovered Practice Settings (Patient C1277724)

Based on queries, here are **known practice settings** available:

| Practice Setting | Documents Found | Use Case |
|-----------------|-----------------|----------|
| **Ophthalmology** | 18 | Vision testing, eye exams |
| (Others not yet queried) | ? | Oncology, Neurosurgery, etc. |

**To discover all practice settings**:
```sql
SELECT DISTINCT context_practice_setting_text, COUNT(*) as count
FROM document_reference
WHERE subject_reference = 'PATIENT_ID' AND status = 'current'
  AND context_practice_setting_text IS NOT NULL
GROUP BY context_practice_setting_text
ORDER BY count DESC
```

---

## Key Takeaways

1. ✅ **`context_practice_setting_text`** is the GOLD STANDARD for specialty filtering
2. ✅ **`type_coding_display`** identifies document types accurately
3. ✅ **`content_attachment_content_type`** ensures extractability
4. ✅ **`date`** enables temporal filtering
5. ✅ **`document_reference_context_encounter`** links docs to encounters (though limited specialty info)
6. ⚠️ Encounter-based filtering is LIMITED (generic types, no specialty codes)
7. ⚠️ Most metadata is document-level, not encounter-level

**Bottom Line**: For specialty-specific documents (ophthalmology, oncology, etc.), use `context_practice_setting_text` directly rather than encounter-based filtering.

---

*Analysis completed: October 4, 2025*
*Based on: Patient C1277724 FHIR v1 data exploration*
