# Structured Data Maximization Analysis

**Date:** October 2, 2025  
**Purpose:** Audit what structured data we CAN extract from materialized views vs what variables need narrative extraction

---

## CSV Variables: Coverage Analysis

### ✅ FULLY COVERED by Structured Data (6 variables)

| Variable | Source | Status |
|----------|--------|--------|
| **patient_gender** | Patient resource (gender field) | ⚠️ NOT YET EXTRACTED |
| **diagnosis_date** | problem_list_diagnoses.onset_date_time | ✅ EXTRACTED |
| **primary_diagnosis** | problem_list_diagnoses.diagnosis_name | ⚠️ PARTIALLY (need to expand) |
| **surgery_date** | procedure.performed_date_time / performed_period_start | ✅ EXTRACTED (4 surgeries) |
| **chemotherapy_agent** | patient_medications.medication_name | ⚠️ PARTIALLY (too narrow filter) |
| **radiation_therapy** | procedure table (CPT codes for radiation) | ⚠️ NOT YET EXTRACTED |

### 🟡 PARTIALLY COVERED by Structured Data (3 variables)

| Variable | Structured Component | Narrative Component |
|----------|---------------------|---------------------|
| **who_grade** | Condition.stage (if coded) | Pathology report text (primary source) |
| **surgery_type** | procedure.code (CPT codes) → classify | Operative note description |
| **surgery_location** | procedure.bodySite | Operative note anatomical details |

### ❌ NARRATIVE ONLY (5 variables)

| Variable | Why Narrative Only |
|----------|-------------------|
| **document_type** | Classification of input documents |
| **date_of_birth** | Patient resource OR age calculation from narrative |
| **extent_of_resection** | Surgeon's assessment in operative note |
| **idh_mutation** | observation.value_string (molecular) - partially structured |
| **mgmt_methylation** | observation.value_string (molecular) - partially structured |

---

## What We're Currently Extracting

### ✅ Currently Extracting (4 categories):

1. **diagnosis_date** ✓
   - Source: `problem_list_diagnoses.onset_date_time`
   - Query filters: astrocytoma, glioma, brain, tumor
   - Result: `2018-06-04`

2. **surgeries** ✓
   - Source: `procedure.performed_date_time` + `procedure.performed_period_start`
   - CPT filtering: 61500-61576 (tumor resections only)
   - Excludes: Shunts (62201), biopsies (61304-61315)
   - Result: 4 procedures across 2 encounters

3. **molecular_markers** ✓
   - Source: `observation.value_string` (fallback from molecular_tests view)
   - Markers: BRAF, IDH1, MGMT, EGFR
   - Result: Found KIAA1549-BRAF fusion

4. **treatments** ✓
   - Source: `patient_medications.medication_name`
   - Filters: temozolomide, radiation, bevacizumab, chemotherapy
   - Result: 48 records (5 unique medications, all bevacizumab variants)

---

## GAPS: What We Should Add

### 🎯 HIGH PRIORITY - Easy Wins (Fully Structured)

#### 1. **patient_gender** (100% structured)
```python
def extract_patient_gender(self, patient_fhir_id: str) -> Optional[str]:
    """Extract gender from Patient resource"""
    query = f"""
    SELECT gender
    FROM {self.v2_database}.patient
    WHERE id = '{patient_fhir_id}'
    LIMIT 1
    """
    # Returns: male, female, other, unknown
```

**Why Add:** 
- 100% structured field
- Required for demographics
- Gold standard has it
- Zero ambiguity

---

#### 2. **date_of_birth** (if available in Patient resource)
```python
def extract_date_of_birth(self, patient_fhir_id: str) -> Optional[str]:
    """Extract DOB from Patient resource"""
    query = f"""
    SELECT birth_date
    FROM {self.v2_database}.patient
    WHERE id = '{patient_fhir_id}'
    LIMIT 1
    """
    # Returns: YYYY-MM-DD or None
```

**Why Add:**
- Structured if available
- Used to calculate age at diagnosis
- Fallback: Can calculate from "age at diagnosis" + diagnosis date

---

#### 3. **surgery_body_site** (procedure.bodySite)
```python
def extract_surgeries(self, patient_fhir_id: str) -> List[Dict]:
    """Add body_site to surgery extraction"""
    query = f"""
    SELECT 
        ...,
        p.body_site_text,
        pbs.body_site_coding_code,
        pbs.body_site_coding_display
    FROM {self.v2_database}.procedure p
    LEFT JOIN {self.v2_database}.procedure_body_site pbs 
        ON p.id = pbs.procedure_id
    ...
    """
    # Add to surgeries dict:
    surgeries.append({
        'date': date_str,
        'cpt_code': row['cpt_code'],
        'cpt_display': row['cpt_display'],
        'body_site': row.get('body_site_text', 'Not specified'),
        'description': row['code_text']
    })
```

**Why Add:**
- Structured field (Procedure.bodySite)
- Helps with surgery_location variable
- May be generic (e.g., "Brain") but better than nothing
- Narrative can provide more specifics

---

#### 4. **radiation_therapy** (from procedure table)
```python
def extract_radiation_therapy(self, patient_fhir_id: str) -> bool:
    """Extract radiation therapy status from procedure table"""
    
    # Radiation CPT codes:
    # 77295, 77300, 77301, 77321, 77331, 77336, 77338, 77370, 77371, 77372, 77373
    # 77401-77499 (external beam radiation)
    # 77261-77263 (radiation planning)
    # 77427-77432 (treatment management)
    
    query = f"""
    SELECT COUNT(*) as radiation_count
    FROM {self.v2_database}.procedure p
    LEFT JOIN {self.v2_database}.procedure_code_coding pcc 
        ON p.id = pcc.procedure_id
    WHERE p.subject_reference = '{patient_fhir_id}'
        AND p.status = 'completed'
        AND (
            pcc.code_coding_code BETWEEN '77261' AND '77499'
            OR LOWER(pcc.code_coding_display) LIKE '%radiation%'
            OR LOWER(pcc.code_coding_display) LIKE '%radiotherapy%'
            OR LOWER(p.code_text) LIKE '%radiation%'
        )
    """
    # Returns: True if count > 0, False otherwise
```

**Why Add:**
- Fully structured (CPT codes for radiation procedures)
- Boolean field (easy to extract)
- Complements structured extraction

---

#### 5. **EXPAND chemotherapy_agent extraction**
```python
def extract_treatment_start_dates(self, patient_fhir_id: str) -> List[Dict]:
    """EXPAND medication filtering to catch more chemo agents"""
    
    # BEFORE (TOO NARROW):
    # AND (
    #     LOWER(medication_name) LIKE '%temozolomide%'
    #     OR LOWER(medication_name) LIKE '%radiation%'
    #     OR LOWER(medication_name) LIKE '%bevacizumab%'
    #     OR LOWER(medication_name) LIKE '%chemotherapy%'
    # )
    
    # AFTER (COMPREHENSIVE):
    CHEMO_KEYWORDS = [
        'temozolomide', 'temodar', 'tmz',
        'bevacizumab', 'avastin',
        'vincristine', 'oncovin',
        'carboplatin', 'paraplatin',
        'cisplatin', 'platinol',
        'lomustine', 'ccnu', 'ceenu',
        'cyclophosphamide', 'cytoxan',
        'etoposide', 'vepesid', 'toposar',
        'irinotecan', 'camptosar',
        'procarbazine', 'matulane',
        'vinblastine', 'velban',
        'selumetinib', 'koselugo',
        'dabrafenib', 'tafinlar',
        'trametinib', 'mekinist',
        'chemotherapy', 'chemo'
    ]
    
    conditions = ' OR '.join([f"LOWER(medication_name) LIKE '%{drug}%'" for drug in CHEMO_KEYWORDS])
    
    query = f"""
    SELECT DISTINCT
        medication_name as medication,
        rx_norm_codes,
        authored_on as start_date,
        status
    FROM {self.v2_database}.patient_medications
    WHERE patient_id = '{patient_fhir_id}'
        AND status IN ('active', 'completed')
        AND ({conditions})
    ORDER BY authored_on
    """
```

**Why Expand:**
- Gold standard has: vinblastine, bevacizumab, selumetinib
- We currently only find bevacizumab (48 records)
- Missing vinblastine and selumetinib because filter too narrow

---

#### 6. **primary_diagnosis** (expand extraction)
```python
def extract_primary_diagnosis(self, patient_fhir_id: str) -> Optional[str]:
    """Extract full diagnosis text with WHO grade"""
    query = f"""
    SELECT 
        diagnosis_name,
        icd10_code,
        onset_date_time
    FROM {self.v2_database}.problem_list_diagnoses
    WHERE patient_id = '{patient_fhir_id}'
        AND (
            LOWER(diagnosis_name) LIKE '%astrocytoma%'
            OR LOWER(diagnosis_name) LIKE '%glioma%'
            OR LOWER(diagnosis_name) LIKE '%brain%'
            OR LOWER(diagnosis_name) LIKE '%tumor%'
            OR LOWER(diagnosis_name) LIKE '%neoplasm%'
        )
    ORDER BY onset_date_time
    LIMIT 1
    """
    # Returns: Full diagnosis text (e.g., "Pilocytic astrocytoma of cerebellum")
```

**Why Expand:**
- Currently extracting only for date
- Should also save full diagnosis text
- May include WHO grade in text

---

### 🟡 MEDIUM PRIORITY - Hybrid (Structured + Narrative)

#### 7. **surgery_type** (classify CPT codes)
```python
def classify_surgery_type(self, cpt_code: str, description: str) -> str:
    """Classify surgery type from CPT code"""
    
    # BIOPSY: 61304-61315
    if cpt_code and '61304' <= cpt_code <= '61315':
        return 'BIOPSY'
    
    # RESECTION: 61500-61576
    if cpt_code and '61500' <= cpt_code <= '61576':
        # Check description for specifics
        desc_lower = description.lower() if description else ''
        if 'debulk' in desc_lower:
            return 'DEBULKING'
        return 'RESECTION'
    
    # SHUNT: 62201, 62223, 62220, etc.
    if cpt_code and cpt_code.startswith('622'):
        return 'SHUNT'
    
    return 'OTHER'
```

**Why Add:**
- CPT codes can auto-classify most surgeries
- Narrative can refine if ambiguous
- Helps with surgery_type variable

---

#### 8. **who_grade** (try structured first)
```python
def extract_who_grade(self, patient_fhir_id: str) -> Optional[str]:
    """Try to extract WHO grade from Condition.stage"""
    query = f"""
    SELECT 
        stage_summary_text,
        stage_type_text
    FROM {self.v2_database}.condition c
    LEFT JOIN {self.v2_database}.condition_stage cs 
        ON c.id = cs.condition_id
    WHERE c.subject_reference = '{patient_fhir_id}'
        AND (
            LOWER(c.code_text) LIKE '%glioma%'
            OR LOWER(c.code_text) LIKE '%astrocytoma%'
        )
    """
    # Parse stage_summary_text for "Grade I", "Grade II", etc.
    # Fallback: narrative extraction from pathology
```

**Why Try:**
- May be coded in Condition.stage
- If not, fall back to narrative
- Quick win if available

---

### ❌ LOW PRIORITY - Narrative Only (Already Covered)

These are correctly left to BRIM narrative extraction:
- **extent_of_resection** - Surgeon's operative note assessment
- **idh_mutation** - May be in observation.value_string but needs parsing
- **mgmt_methylation** - May be in observation.value_string but needs parsing
- **document_type** - Classification of input documents (not patient data)

---

## Recommended Implementation Order

### Phase 1: Essential Structured Fields (15 minutes)
1. ✅ Add `extract_patient_gender()` - 100% structured
2. ✅ Add `extract_date_of_birth()` - 100% structured  
3. ✅ Add `extract_radiation_therapy()` - 100% structured
4. ✅ Expand `extract_treatment_start_dates()` - Add more chemo keywords

### Phase 2: Enhanced Surgery Data (10 minutes)
5. ✅ Add `body_site` to `extract_surgeries()` - Add bodySite field
6. ✅ Add `classify_surgery_type()` - CPT-based classification
7. ✅ Expand `extract_primary_diagnosis()` - Full diagnosis text

### Phase 3: Optional Hybrid (5 minutes)
8. ⏸️ Try `extract_who_grade()` from Condition.stage (fallback to narrative)

---

## Expected Impact

### Before Enhancement:
```json
{
  "diagnosis_date": "2018-06-04",
  "surgeries": [4 procedures with dates, CPT codes],
  "molecular_markers": {"BRAF": "..."},
  "treatments": [48 bevacizumab records]
}
```

### After Enhancement:
```json
{
  "patient_gender": "female",
  "date_of_birth": "2005-xx-xx" or null,
  "primary_diagnosis": "Pilocytic astrocytoma of cerebellum",
  "diagnosis_date": "2018-06-04",
  "who_grade": "I" or null (from Condition.stage),
  "surgeries": [
    {
      "date": "2018-05-28",
      "cpt_code": "61500",
      "type": "RESECTION",
      "body_site": "Cerebellum" or "Brain",
      "description": "..."
    },
    ...
  ],
  "radiation_therapy": true/false,
  "molecular_markers": {"BRAF": "...", "IDH": "...", "MGMT": "..."},
  "treatments": [
    {"medication": "bevacizumab", ...},
    {"medication": "vincristine", ...},
    {"medication": "vinblastine", ...},
    {"medication": "selumetinib", ...}
  ]
}
```

### Coverage Improvement:
- **Before:** 4 of 14 variables partially covered (29%)
- **After Phase 1:** 8 of 14 variables covered (57%)
- **After Phase 2:** 11 of 14 variables enhanced (79%)

### Iteration 2 Impact:
- More structured data → Better BRIM prioritization
- More comprehensive STRUCTURED documents
- Higher accuracy on structured/semi-structured variables
- Expected improvement: 50% → 85-90% accuracy

---

## Implementation Notes

### Database Schema Assumptions:
- `patient` table exists with `gender` and `birth_date` fields
- `procedure_body_site` join table exists
- `condition_stage` join table may exist

### Testing Strategy:
1. Add one extraction method at a time
2. Test on patient e4BwD8ZYDBccepXcJ.Ilo3w3
3. Verify output in structured_data.json
4. Regenerate BRIM CSVs and validate

### Backward Compatibility:
- All new fields are optional (won't break existing CSVs)
- Existing extractions remain unchanged
- New fields add to STRUCTURED documents incrementally

---

**Next Action:** Implement Phase 1 enhancements (4 extraction methods, ~15 minutes)
