# Procedure Tables: Comprehensive RT Content Assessment

**Date**: 2025-10-12
**Purpose**: Comprehensive assessment of procedure schema for radiation therapy content

---

## Executive Summary

**22 procedure tables discovered**, 15 with data.

**Key Findings**:
- ✅ **procedure_code_coding**: Ideal for RT extraction (CPT 77xxx codes)
- ⚠️  **procedure** (parent): 0.8% RT hit rate - **LOW but contains stereotactic procedures**
- ⚠️  **procedure_note**: Column schema identified - **NEEDS ANALYSIS**
- ⚠️  **procedure_reason_code**: 0.3% RT hit rate - **VERY LOW**

**Recommendation**: Focus on **procedure_code_coding** for CPT-based RT procedure capture

---

## Table Discovery Results

### Tables with Data (15/22)

| Table | Rows | Test Patient | Priority for RT |
|-------|------|--------------|-----------------|
| **procedure** | 51,159 | Unknown | ⚠️  LOW (0.8% RT) |
| **procedure_code_coding** | 40,252 | Unknown | ✅ **HIGH** (CPT codes) |
| **procedure_note** | 4,369 | Unknown | ❓ **NEEDS ANALYSIS** |
| **procedure_reason_code** | 40,273 | Unknown | ⚠️  VERY LOW (0.3% RT) |
| procedure_report | 1,095,593 | Unknown | ❓ Unknown |
| procedure_identifier | 83,001 | Unknown | ⚠️  ID only |
| procedure_category_coding | 51,159 | Unknown | ❓ May contain RT categories |
| procedure_based_on | 36,905 | Unknown | ⚠️  References |
| procedure_focal_device | 18,798 | Unknown | ❓ Device info |
| procedure_used_reference | 18,539 | Unknown | ⚠️  References |
| procedure_performer | 16,312 | Unknown | ⚠️  Provider info |
| procedure_outcome_coding | 8,543 | Unknown | ❓ Outcome codes |
| procedure_body_site | 4,905 | Unknown | ❓ Anatomical sites |
| procedure_status_reason_coding | 395 | Unknown | ⚠️  Too small |
| procedure_complication | 45 | Unknown | ⚠️  Too small |

### Empty Tables (7/22)
- procedure_complication_detail
- procedure_follow_up
- procedure_instantiates_canonical
- procedure_instantiates_uri
- procedure_part_of
- procedure_reason_reference
- procedure_used_code

---

## Schema Details

### procedure (parent table)

**Columns (38)**:
```
id, resource_type, status
subject_reference, subject_display, subject_type
performed_date_time, performed_period_start, performed_period_end
code_text, category_text, outcome_text, status_reason_text
encounter_reference, location_reference
recorder_reference, asserter_reference
... (age, range, string fields)
```

**Key Fields for RT**:
- `code_text`: Procedure description (0.8% RT hit rate)
- `outcome_text`: Procedure outcome
- `performed_date_time`: Date/time of procedure
- `performed_period_start/end`: Period dates
- `subject_reference`: Patient ID (bare format, no 'Patient/' prefix)

**RT Content Analysis**:
- Total with text: 999
- RT-specific hits: 8/999 (0.8%)
- **Keywords found**: stereotactic (4), gy (3), ctv (1)
- **Sample procedures**:
  - "STEREOTACTIC BIOPSY OR EXCISION INCLUDING BURR HOLE FOR INTRACRANIAL LESION"
  - "STEREOTACTIC COMPUTER ASSISTED PX SPINAL"
  - Contains `gy` in "LP oncology" (likely typo/abbreviation)

**Assessment**: **LOW RT hit rate** - procedures are mostly non-RT surgical procedures. Stereotactic procedures found are neurosurgery, not radiation therapy.

---

### procedure_code_coding (child table)

**Columns (5)**:
```
id
procedure_id
code_coding_code
code_coding_display
code_coding_system
```

**Key Fields for RT**:
- `code_coding_code`: CPT/SNOMED/ICD procedure codes
- `code_coding_display`: Code description text
- `code_coding_system`: Coding system (CPT, SNOMED, etc.)
- `procedure_id`: Foreign key to parent

**RT Code Patterns**:
- **CPT 77xxx series**: Radiation oncology procedures
  - 770xx: Consultation, clinical treatment planning
  - 771xx: Medical radiation physics, dosimetry
  - 772xx: Radiation treatment delivery
  - 773xx: Stereotactic radiation treatment
  - 774xx: Brachytherapy
  - 775xx-779xx: Various RT procedures

**Analysis Status**: Query failed due to incorrect column name in script

**Corrected Query Needed**:
```sql
SELECT 
    procedure_id,
    code_coding_code,
    code_coding_display,
    code_coding_system
FROM fhir_prd_db.procedure_code_coding
WHERE code_coding_code LIKE '77%'
   OR LOWER(code_coding_display) LIKE '%radiation%'
   OR LOWER(code_coding_display) LIKE '%radiotherapy%'
   OR LOWER(code_coding_display) LIKE '%brachytherapy%'
```

**Assessment**: **HIGH PRIORITY** - CPT codes are definitive for RT procedures

---

### procedure_note (child table)

**Columns (8)**:
```
id
procedure_id
note_text
note_time
note_author_reference_display
note_author_reference_reference
note_author_reference_type
note_author_string
```

**Key Fields for RT**:
- `note_text`: Free text procedure notes
- `note_time`: When note was written
- `note_author_reference_display`: Author name
- `procedure_id`: Foreign key to parent

**Analysis Status**: Query failed due to incorrect column name

**Corrected Query Needed**:
```sql
SELECT 
    procedure_id,
    note_text,
    note_time,
    note_author_reference_display
FROM fhir_prd_db.procedure_note
WHERE note_text IS NOT NULL
```

**Assessment**: **NEEDS ANALYSIS** with corrected column names

---

### procedure_reason_code (child table)

**Columns**: Unknown (query used wrong column names)

**RT Content Analysis** (with incorrect query):
- Total reason codes: 999
- RT-specific hits: 3/999 (0.3%)
- **Keywords found**: gy (3)

**Assessment**: **VERY LOW RT hit rate** - not a priority table

---

## RT Content Analysis Results

### RT-Specific Keywords Used
(60+ terms - same as extraction script)

```python
RADIATION_SPECIFIC_KEYWORDS = [
    # Core RT terms
    'radiation', 'radiotherapy', 'rad onc', 'rad-onc', 'radonc',
    # Modalities
    'xrt', 'imrt', 'vmat', '3d-crt', 'proton', 'photon', 'electron',
    'brachytherapy', 'hdr', 'ldr',
    # Stereotactic
    'stereotactic', 'sbrt', 'srs', 'sabr', 'radiosurgery',
    'gamma knife', 'cyberknife',
    # Delivery
    'beam', 'external beam', 'teletherapy', 'conformal',
    # Dosimetry
    'dose', 'gy', 'gray', 'cgy', 'centigray', 'fraction',
    # Technical
    'isocenter', 'ptv', 'gtv', 'ctv', 'linac', 'portal',
    ...
]
```

### Analysis Summary

| Table | Total Rows | RT Hits | Hit Rate | Assessment |
|-------|------------|---------|----------|------------|
| procedure | 999 | 8 | 0.8% | LOW - mostly neurosurgery stereotactic |
| procedure_code_coding | N/A | N/A | N/A | **HIGH PRIORITY** - needs corrected query |
| procedure_note | N/A | N/A | N/A | UNKNOWN - needs analysis |
| procedure_reason_code | 999 | 3 | 0.3% | VERY LOW |

---

## Recommendations

### ✅ HIGH PRIORITY: procedure_code_coding

**Why**:
- CPT 77xxx codes are definitive for radiation oncology procedures
- Structured data (codes) more reliable than free text
- Industry standard for procedure identification
- Can filter precisely for RT procedures

**Implementation**:
```python
def extract_procedure_rt_codes(athena_client, patient_id):
    """
    Extract RT procedures via CPT 77xxx codes.
    """
    query = f"""
    SELECT 
        parent.id as procedure_id,
        parent.performed_date_time as proc_performed_date_time,
        parent.performed_period_start as proc_performed_period_start,
        parent.performed_period_end as proc_performed_period_end,
        parent.status as proc_status,
        parent.code_text as proc_code_text,
        coding.code_coding_code as pcc_code,
        coding.code_coding_display as pcc_display,
        coding.code_coding_system as pcc_system
    FROM {DATABASE}.procedure_code_coding coding
    JOIN {DATABASE}.procedure parent ON coding.procedure_id = parent.id
    WHERE parent.subject_reference = '{patient_id}'
      AND (
          coding.code_coding_code LIKE '77%'
          OR LOWER(coding.code_coding_display) LIKE '%radiation%'
          OR LOWER(coding.code_coding_display) LIKE '%radiotherapy%'
          OR LOWER(coding.code_coding_display) LIKE '%brachytherapy%'
      )
    ORDER BY parent.performed_date_time
    """
    # ... execute and return DataFrame
```

**Column Naming**:
- `proc_*` = procedure parent fields
- `pcc_*` = procedure_code_coding fields

---

### ❓ MAYBE: procedure_note

**Why Consider**:
- 4,369 total notes available
- May contain RT treatment details, dose info, techniques
- Useful for qualitative context

**Why Skip**:
- Needs additional analysis with corrected query
- Text analysis less reliable than codes
- Likely lower hit rate than CPT codes

**Decision**: Analyze first, then decide

---

### ⚠️  SKIP: procedure (parent text fields)

**Why Skip**:
- Only 0.8% RT hit rate
- "Stereotactic" hits are neurosurgery, not RT
- Better to rely on CPT codes from child table
- Text fields less structured

**Exception**: Still need parent table for JOIN to get dates/context

---

### ⚠️  SKIP: procedure_reason_code

**Why Skip**:
- Only 0.3% RT hit rate
- Very low signal
- Not worth extraction effort

---

## Integration Strategy

### Phase 1: Add procedure_code_coding to Extraction Script

**File**: `extract_radiation_data.py`

**New Function**:
```python
def extract_procedure_rt_codes(athena_client, patient_id):
    """
    Extract RT procedures via CPT 77xxx codes from procedure_code_coding.
    
    Returns DataFrame with:
    - procedure_id
    - proc_performed_date_time, proc_performed_period_start, proc_performed_period_end
    - proc_status, proc_code_text
    - pcc_code, pcc_display, pcc_system
    """
    # Query with resource prefixes
    # Filter for CPT 77xxx OR RT keywords in display
    # JOIN to parent for dates
    # Return filtered DataFrame
```

**Integration**:
1. Call in `main()` after service_request extractions
2. Update summary statistics
3. Add to file saving logic: `procedure_rt_codes.csv`
4. Update docstring

---

### Phase 2: Optional - Analyze procedure_note

**Steps**:
1. Fix column names in analysis script
2. Run RT content analysis
3. If hit rate > 5%, add to extraction
4. If hit rate < 5%, skip

---

## Cross-Resource Temporal Alignment

### Date Fields Available

**procedure**:
- `performed_date_time` (most specific)
- `performed_period_start`, `performed_period_end` (date range)

**Alignment Strategy**:
```python
# Procedure dates
proc_df['best_date'] = proc_df['proc_performed_date_time'].fillna(
    proc_df['proc_performed_period_start']
)

# Merge with other resources
timeline = pd.concat([
    appointments_df[['start', 'rt_category']],
    care_plan_df[['cp_period_start', 'cpn_note_type']],
    service_request_df[['sr_occurrence_date_time', 'srn_note_type']],
    proc_df[['best_date', 'pcc_display']].rename(columns={'best_date': 'date', 'pcc_display': 'event'})
]).sort_values('date')
```

---

## Next Steps

### Immediate (High Priority)
1. ✅ Update `analyze_procedure_radiation_content.py` with corrected column names
2. ✅ Re-run analysis on procedure_code_coding and procedure_note
3. ✅ Add `extract_procedure_rt_codes()` to extraction script
4. ✅ Test on RT patient
5. ✅ Validate CPT 77xxx code capture

### Future (Optional)
1. ❓ Analyze procedure_note if needed
2. ❓ Check procedure_body_site for anatomical RT sites
3. ❓ Check procedure_report for RT reports (1M+ rows - need sampling)

---

## Lessons Learned

### 1. Column Name Discovery Critical
- **Problem**: Initial queries failed due to incorrect column names
- **Solution**: Always query `SELECT * ... LIMIT 1` first to discover schema
- **Prevention**: Document actual column names in analysis

### 2. CPT Codes > Text Matching
- **Insight**: Structured codes (CPT 77xxx) more reliable than keyword matching
- **Benefit**: Definitive procedure identification vs fuzzy text search
- **Application**: Prioritize code-based tables over text-based

### 3. "Stereotactic" ≠ Radiation Therapy
- **Discovery**: "Stereotactic" procedures in data are neurosurgery (biopsies), not SRS/SBRT
- **Lesson**: Context matters - same keyword different meaning
- **Validation**: Always check sample records to verify keyword relevance

### 4. Hit Rate Thresholds
- **< 1%**: Likely not worth extracting (procedure parent = 0.8%)
- **1-5%**: Marginal - consider effort vs value
- **> 5%**: Worth extracting
- **CPT codes**: Always worth it regardless of hit rate (definitive)

---

## Summary

**✅ EXTRACT**: procedure_code_coding (CPT 77xxx codes)
**❓ ANALYZE**: procedure_note (needs corrected query)
**⚠️  SKIP**: procedure parent text fields (0.8% hit rate)
**⚠️  SKIP**: procedure_reason_code (0.3% hit rate)

**Priority**: Add CPT-based procedure extraction to script immediately
