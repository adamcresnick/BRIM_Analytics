# Project CSV Creation and Validation Workflow

## Overview

This document defines the **canonical workflow** for creating, validating, and uploading `project.csv` files to BRIM. Following this workflow prevents common issues like duplicate rows, inconsistent patient IDs, and upload failures.

---

## Critical Requirements for project.csv

### BRIM Format Specification

```csv
NOTE_ID,PERSON_ID,NOTE_DATETIME,NOTE_TEXT,NOTE_TITLE
```

**Column Definitions:**

| Column | Type | Required | Description | Examples |
|--------|------|----------|-------------|----------|
| `NOTE_ID` | string | YES | **MUST BE UNIQUE** across entire file | `FHIR_BUNDLE`, `NOTE_12345`, `PATH_20210310` |
| `PERSON_ID` | string | YES | **MUST BE CONSISTENT** format | `C1277724` (preferred) or `1277724` |
| `NOTE_DATETIME` | ISO 8601 | YES | Document timestamp | `2021-03-10T14:30:00Z` |
| `NOTE_TEXT` | text | YES | Document content (can be large JSON/HTML) | Full document text |
| `NOTE_TITLE` | string | YES | Document type/title | `OPERATIVE_NOTE`, `PATHOLOGY`, `FHIR_BUNDLE` |

### Critical Constraints

1. **NO DUPLICATE NOTE_IDs**: Each `NOTE_ID` must be unique. BRIM will reject or warn about duplicates.
2. **CONSISTENT PERSON_IDs**: All rows for the same patient must use the EXACT same ID format.
   - ❌ WRONG: Mix of `1277724` and `C1277724` → BRIM counts as 2 patients
   - ✅ CORRECT: All rows use `C1277724` → BRIM counts as 1 patient
3. **NO EMPTY REQUIRED FIELDS**: All 5 columns must have non-empty values
4. **PROPER CSV ESCAPING**: Use `csv.QUOTE_ALL` for fields containing commas, quotes, or newlines

---

## Common Issues and Root Causes

### Issue 1: Duplicate NOTE_IDs

**Symptom**: BRIM upload shows "X duplicate rows" warning or error

**Root Causes**:
- Multiple data sources produce same NOTE_ID (e.g., FHIR_BUNDLE generated twice)
- Merging project.csv files without deduplication
- Documents retrieved multiple times from database

**Prevention**:
```python
# ALWAYS deduplicate before writing CSV
seen_note_ids = set()
dedup_rows = []
for row in rows:
    if row['NOTE_ID'] not in seen_note_ids:
        seen_note_ids.add(row['NOTE_ID'])
        dedup_rows.append(row)
```

### Issue 2: Inconsistent Patient IDs

**Symptom**: BRIM shows "2 patients in project" when expecting 1

**Root Causes**:
- FHIR resources use numeric ID (`1277724`) 
- Clinical notes use prefixed ID (`C1277724`)
- Different data sources use different conventions

**Prevention**:
```python
# Standardize ALL patient IDs to same format
def standardize_patient_id(raw_id: str) -> str:
    """Ensure consistent format: C + numeric ID"""
    raw_id = str(raw_id).strip()
    if raw_id.startswith('C'):
        return raw_id  # Already has prefix
    else:
        return f"C{raw_id}"  # Add prefix

# Apply to ALL rows
for row in rows:
    row['PERSON_ID'] = standardize_patient_id(row['PERSON_ID'])
```

### Issue 3: Missing Required Fields

**Symptom**: Upload fails with validation errors

**Root Causes**:
- NULL values in database columns
- Failed data transformations
- Missing document metadata

**Prevention**:
```python
# Validate before writing
required_fields = ['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE']
for i, row in enumerate(rows):
    for field in required_fields:
        if not row.get(field) or not str(row[field]).strip():
            raise ValueError(f"Row {i}: Missing required field '{field}'")
```

---

## Canonical Workflow

### Step 1: Data Collection

Collect documents from various sources:
- FHIR Bundle (JSON)
- STRUCTURED extracts (molecular markers, surgeries, treatments, etc.)
- Clinical notes (HTML Binary documents from DocumentReference)
- Imaging reports
- Lab results

**CRITICAL**: Track the data source for each document to aid debugging.

```python
rows = []

# Source 1: FHIR Bundle
rows.append({
    'NOTE_ID': 'FHIR_BUNDLE',
    'PERSON_ID': standardize_patient_id(subject_id),  # STANDARDIZE HERE
    'NOTE_DATETIME': datetime.now(timezone.utc).isoformat(),
    'NOTE_TEXT': json.dumps(fhir_bundle),
    'NOTE_TITLE': 'FHIR_BUNDLE'
})

# Source 2: STRUCTURED extracts
for doc_type in ['molecular_markers', 'surgeries', 'treatments']:
    rows.append({
        'NOTE_ID': f'STRUCTURED_{doc_type}',
        'PERSON_ID': standardize_patient_id(subject_id),  # STANDARDIZE HERE
        'NOTE_DATETIME': datetime.now(timezone.utc).isoformat(),
        'NOTE_TEXT': create_structured_doc(doc_type, fhir_data),
        'NOTE_TITLE': f'STRUCTURED_{doc_type.upper()}'
    })

# Source 3: Clinical notes from database
for note in clinical_notes:
    rows.append({
        'NOTE_ID': note['note_id'],
        'PERSON_ID': standardize_patient_id(note['subject_id']),  # STANDARDIZE HERE
        'NOTE_DATETIME': note['note_datetime'],
        'NOTE_TEXT': note['note_text'],
        'NOTE_TITLE': note['note_type']
    })
```

### Step 2: Deduplication

Remove duplicate NOTE_IDs (keep first occurrence):

```python
seen_note_ids = set()
dedup_rows = []
duplicate_count = 0

for row in rows:
    if row['NOTE_ID'] not in seen_note_ids:
        seen_note_ids.add(row['NOTE_ID'])
        dedup_rows.append(row)
    else:
        duplicate_count += 1
        print(f"⚠️  Skipping duplicate NOTE_ID: {row['NOTE_ID']}")

if duplicate_count > 0:
    print(f"ℹ️  Removed {duplicate_count} duplicate rows")

rows = dedup_rows
```

### Step 3: Validation (MANDATORY)

Use the validation utility **BEFORE every upload**:

```python
from project_csv_validator import ProjectCSVValidator

# Write initial CSV
with open('project_raw.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE'], 
                            quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(rows)

# Validate and fix
validator = ProjectCSVValidator()
result = validator.validate_and_fix(
    'project_raw.csv',
    'project.csv',
    standardize_patient_ids=True,
    remove_duplicates=True,
    backup=True
)

if not result['ready_for_upload']:
    raise Exception("project.csv validation failed - see errors above")
```

**OR via command line**:

```bash
python scripts/project_csv_validator.py --input project_raw.csv --output project.csv
```

### Step 4: Pre-Upload Checklist

Before uploading to BRIM, verify:

```bash
# 1. Check row count
wc -l project.csv
# Expected: 1 header + N data rows

# 2. Check unique NOTE_IDs (should match row count - 1)
tail -n +2 project.csv | cut -d',' -f1 | sort -u | wc -l

# 3. Check unique PERSON_IDs (should be 1 for single-patient studies)
python scripts/project_csv_validator.py --input project.csv --check-only
```

### Step 5: Upload to BRIM

```python
# Upload using API or web interface
# Confirm "0 lines skipped" message
# Confirm "1 patient in project" (or expected count)
```

---

## Integration with Existing Scripts

### Update pilot_generate_brim_csvs.py

**Location**: `/scripts/pilot_generate_brim_csvs.py`

**Modify `generate_project_csv()` method**:

```python
def generate_project_csv(self):
    """Generate project.csv with FHIR Bundle + Clinical Notes + Structured Findings."""
    print(f"\n📝 Generating project.csv...")
    
    project_file = self.output_dir / 'project.csv'
    rows = []
    
    # Helper function for consistent patient IDs
    def standardize_patient_id(raw_id):
        """Ensure consistent format: C + numeric ID"""
        raw_id = str(raw_id).strip()
        return raw_id if raw_id.startswith('C') else f"C{raw_id}"
    
    # Row 1: FHIR Bundle
    rows.append({
        'NOTE_ID': 'FHIR_BUNDLE',
        'PERSON_ID': standardize_patient_id(self.subject_id),  # ← STANDARDIZE
        'NOTE_DATETIME': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'NOTE_TEXT': json.dumps(self.bundle, separators=(',', ':')),
        'NOTE_TITLE': 'FHIR_BUNDLE'
    })
    
    # Rows 2-N: Structured Findings
    for doc in self.create_structured_findings_documents():
        rows.append({
            'NOTE_ID': doc['document_id'],
            'PERSON_ID': standardize_patient_id(self.subject_id),  # ← STANDARDIZE
            'NOTE_DATETIME': doc['document_date'] or datetime.now(timezone.utc).isoformat(),
            'NOTE_TEXT': doc['text_content'],
            'NOTE_TITLE': doc['document_type']
        })
    
    # Rows N+1...: Clinical Notes
    for note in self.clinical_notes:
        rows.append({
            'NOTE_ID': note['note_id'],
            'PERSON_ID': standardize_patient_id(self.subject_id),  # ← STANDARDIZE
            'NOTE_DATETIME': note['note_date'],
            'NOTE_TEXT': note['note_text'],
            'NOTE_TITLE': note['note_type']
        })
    
    # DEDUPLICATION (keep first occurrence)
    seen_note_ids = set()
    dedup_rows = []
    duplicate_count = 0
    
    for row in rows:
        if row['NOTE_ID'] not in seen_note_ids:
            seen_note_ids.add(row['NOTE_ID'])
            dedup_rows.append(row)
        else:
            duplicate_count += 1
            if duplicate_count <= 3:
                print(f"   ⚠️  Skipping duplicate NOTE_ID: {row['NOTE_ID']}")
    
    if duplicate_count > 0:
        print(f"   ℹ️  Removed {duplicate_count} duplicates")
    
    # Write CSV
    with open(project_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE'], 
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(dedup_rows)
    
    print(f"✅ Generated {project_file} with {len(dedup_rows)} unique rows")
    
    # AUTO-VALIDATE before returning
    print(f"\n🔍 Auto-validating project.csv...")
    from project_csv_validator import ProjectCSVValidator
    validator = ProjectCSVValidator()
    result = validator.validate_and_fix(
        str(project_file),
        str(project_file),
        standardize_patient_ids=True,
        remove_duplicates=False,  # Already deduped
        backup=True
    )
    
    if not result['ready_for_upload']:
        print("❌ Validation found issues - review before upload")
    
    return project_file
```

### Update integrate_binary_documents_into_project.py

**Location**: `/scripts/integrate_binary_documents_into_project.py`

**Modify `transform_retrieved_to_project_format()` function**:

```python
def transform_retrieved_to_project_format(retrieved_df):
    """Transform retrieved documents to match project.csv format."""
    print(f"\n[3/6] Transforming retrieved documents to project.csv format...")
    
    # Helper for consistent patient IDs
    def standardize_patient_id(raw_id):
        """Ensure consistent format: C + numeric ID"""
        raw_id = str(raw_id).strip()
        return raw_id if raw_id.startswith('C') else f"C{raw_id}"
    
    # Map columns with patient ID standardization
    transformed = pd.DataFrame({
        'NOTE_ID': retrieved_df['NOTE_ID'],
        'PERSON_ID': retrieved_df['SUBJECT_ID'].apply(standardize_patient_id),  # ← STANDARDIZE
        'NOTE_DATETIME': retrieved_df['NOTE_DATETIME'],
        'NOTE_TEXT': retrieved_df['NOTE_TEXT'],
        'NOTE_TITLE': retrieved_df['DOCUMENT_TYPE']
    })
    
    # ... rest of validation code ...
    
    return transformed
```

**Add validation at the end of `main()` function**:

```python
def main():
    # ... existing code ...
    
    # Save output
    save_project_csv(combined_df)
    
    # VALIDATE output before declaring success
    print("\n" + "=" * 80)
    print("VALIDATING OUTPUT")
    print("=" * 80)
    
    from project_csv_validator import ProjectCSVValidator
    validator = ProjectCSVValidator()
    result = validator.validate_and_fix(
        str(OUTPUT_PROJECT_CSV),
        str(OUTPUT_PROJECT_CSV),
        standardize_patient_ids=True,
        remove_duplicates=True,
        backup=True
    )
    
    if result['ready_for_upload']:
        print("\n✅ project.csv is ready for BRIM upload!")
    else:
        print("\n⚠️  Review validation issues above before upload")
        sys.exit(1)
```

---

## Quick Reference Commands

### Validate existing project.csv

```bash
# Check only (no modifications)
python scripts/project_csv_validator.py --input project.csv --check-only

# Validate and fix (creates backup)
python scripts/project_csv_validator.py --input project.csv

# Validate and write to new file
python scripts/project_csv_validator.py --input project.csv --output project_clean.csv
```

### Manual checks

```bash
# Count rows
wc -l project.csv

# Check for duplicate NOTE_IDs
tail -n +2 project.csv | cut -d',' -f1 | sort | uniq -d

# Count unique PERSON_IDs (should be 1 for single patient)
tail -n +2 project.csv | cut -d',' -f2 | sort -u | wc -l

# List all unique PERSON_IDs
tail -n +2 project.csv | cut -d',' -f2 | sort -u
```

### Python validation

```python
from project_csv_validator import ProjectCSVValidator

validator = ProjectCSVValidator()
result = validator.validate_and_fix(
    'project.csv',
    'project_clean.csv',
    standardize_patient_ids=True,
    remove_duplicates=True,
    backup=True
)

print(f"Ready for upload: {result['ready_for_upload']}")
print(f"Issues: {result['issues']}")
print(f"Fixes applied: {result['fixes_applied']}")
```

---

## Troubleshooting

### Problem: BRIM shows "2 patients" when expecting 1

**Diagnosis**:
```bash
# Check what PERSON_IDs exist
python scripts/project_csv_validator.py --input project.csv --check-only
```

**Fix**:
```bash
# Auto-fix inconsistent IDs
python scripts/project_csv_validator.py --input project.csv --output project_fixed.csv
```

### Problem: BRIM shows "X duplicate rows"

**Diagnosis**:
```bash
# Find duplicates
tail -n +2 project.csv | cut -d',' -f1 | sort | uniq -d
```

**Fix**:
```bash
# Auto-fix duplicates
python scripts/project_csv_validator.py --input project.csv --output project_fixed.csv
```

### Problem: Upload fails with validation error

**Diagnosis**:
```bash
# Full validation report
python scripts/project_csv_validator.py --input project.csv --check-only
```

**Fix**: Review validation errors and correct source data or transformation logic

---

## Best Practices

1. **✅ ALWAYS standardize patient IDs** at data collection time
2. **✅ ALWAYS deduplicate** before writing CSV
3. **✅ ALWAYS validate** using `project_csv_validator.py` before upload
4. **✅ ALWAYS create backups** before modifying files
5. **✅ ALWAYS verify** "1 patient" in BRIM after upload (for single-patient studies)
6. **❌ NEVER** manually edit project.csv files (easy to break CSV escaping)
7. **❌ NEVER** skip validation step
8. **❌ NEVER** merge files without checking for duplicates

---

## File History

- **Version 1.0** (2025-10-05): Initial workflow documentation
- **Issue Fixed**: Inconsistent PERSON_ID formats (1277724 vs C1277724)
- **Issue Fixed**: Duplicate NOTE_IDs in project.csv
- **Tool Created**: `project_csv_validator.py` for automated validation and fixing

---

## Related Documentation

- `UPLOAD_CHECKLIST.md` - Pre-upload verification steps
- `REDESIGN_COMPARISON.md` - Variables and decisions CSV workflow
- `scripts/project_csv_validator.py` - Validation utility source code
- `scripts/pilot_generate_brim_csvs.py` - Main CSV generation script
- `scripts/integrate_binary_documents_into_project.py` - Binary document integration
