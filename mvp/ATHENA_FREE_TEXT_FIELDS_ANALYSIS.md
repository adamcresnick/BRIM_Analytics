# Athena Free Text Fields Requiring MedGemma Extraction

## Critical Gap Identified

**Issue**: The current MVP framework assumes all MedGemma extraction happens on **binary files** (PDFs, HTML, RTF documents from S3). However, many Athena views contain **free text fields** that also require NLP extraction.

**Impact**: Without extracting from Athena free text fields, we'll miss critical clinical data that's already in structured tables but stored as narrative text.

---

## Free Text Fields by Athena View

### 1. v_molecular_tests (CRITICAL - Mutation Data)

**Table**: `molecular_test_results`

**Free Text Field**: `test_result_narrative`

**Content**: Narrative molecular pathology findings

**Example** (Patient C1277724):
```
"Fusion analysis identified KIAA1549-BRAF fusion.
No additional pathogenic variants detected in TP53, IDH1, IDH2,
EGFR, PTEN, or NF1. Tumor mutational burden: 1.2 mutations/Mb (low)."
```

**Variables to Extract**:
- `mutation` - BRAF fusion, IDH status, TP53 status
- `molecular_test_type` - Fusion panel, NGS, WES
- `tumor_mutational_burden` - TMB value
- `microsatellite_instability` - MSI-High/Low/Stable

**Current State in View**:
- `v_molecular_tests.mtr_total_narrative_chars` - Length of narrative (e.g., 2500 characters)
- `v_molecular_tests.mtr_components_list` - Semicolon-separated component names
- ❌ **Narrative text NOT included in view** (PHI protection)

**Extraction Strategy**:
```python
# Step 1: Query v_molecular_tests to get test_id
SELECT mt_test_id, mt_test_date, mtr_total_narrative_chars
FROM v_molecular_tests
WHERE patient_fhir_id = 'Patient/...'
  AND mtr_total_narrative_chars > 0

# Step 2: Query base table to get narrative (requires PHI access)
SELECT test_id, test_result_narrative
FROM molecular_test_results
WHERE test_id IN (...)

# Step 3: Call MedGemma to extract variables
call_medgemma(
    text=test_result_narrative,
    variable='mutation',
    context={'test_date': mt_test_date, 'test_type': 'molecular pathology'}
)
```

**Priority**: 🔴 **HIGHEST** - Critical for molecular variables (4-5 BRIM variables depend on this)

---

### 2. v_imaging (HIGH - Radiology Findings)

**Table**: `diagnostic_report`

**Free Text Fields**:
- `report_conclusion` - Radiologist's impression/conclusion
- `result_information` - MRI result details (from `radiology_imaging_mri_results.value_string`)

**Content**: Radiology report findings and measurements

**Example** (MRI Brain with contrast):
```
report_conclusion: "Stable 2.3 cm enhancing mass in left cerebellum.
No new leptomeningeal enhancement. Stable mild hydrocephalus."

result_information: "T1 post-contrast: Heterogeneous enhancement
measuring 23 x 18 x 21 mm in left cerebellar hemisphere."
```

**Variables to Extract**:
- `tumor_location` - Anatomical location (cerebellum, optic pathway, brainstem)
- `tumor_measurements` - Size in mm (AP x ML x CC)
- `tumor_characteristics` - Enhancement pattern, cystic/solid
- `metastasis` - Leptomeningeal enhancement, disseminated disease
- `hydrocephalus` - Presence and severity
- `tumor_status` - Stable, increased, decreased (comparison with prior)

**Current State in View**:
- `v_imaging.report_conclusion` - ✅ **Included in view**
- `v_imaging.result_information` - ✅ **Included in view**
- `v_imaging.result_display` - ✅ **Included in view**

**Extraction Strategy**:
```python
# Step 1: Query v_imaging
SELECT
    imaging_procedure_id,
    imaging_date,
    imaging_modality,
    report_conclusion,
    result_information,
    result_display
FROM v_imaging
WHERE patient_fhir_id = 'Patient/...'
  AND imaging_modality = 'MRI'
  AND imaging_date BETWEEN diagnosis_date AND last_follow_up
ORDER BY imaging_date DESC

# Step 2: Call MedGemma for each imaging report
for report in imaging_reports:
    combined_text = f"""
    Imaging Modality: {report['imaging_modality']}
    Date: {report['imaging_date']}

    Findings: {report['result_information']}

    Impression: {report['report_conclusion']}
    """

    call_medgemma(
        text=combined_text,
        variable='tumor_location',
        context={'imaging_date': report['imaging_date']}
    )
```

**Priority**: 🔴 **HIGHEST** - Critical for tumor location, measurements, metastasis assessment

---

### 3. v_diagnoses (MEDIUM - Condition Notes)

**Table**: `condition_note`

**Free Text Field**: `note_text`

**Content**: Clinical notes about diagnoses, condition staging, severity

**Example**:
```
"Patient presents with progressive visual decline.
MRI confirms optic pathway glioma involving hypothalamus.
WHO Grade I pilocytic astrocytoma confirmed by biopsy."
```

**Variables to Extract**:
- `who_grade` - WHO tumor grade (if mentioned)
- `tumor_location` - Anatomical site (backup if not in radiology)
- `diagnosis_context` - Symptoms, presentation, progression

**Current State in View**:
- ❌ **NOT included in v_diagnoses view**
- Available in base table: `condition_note.note_text`

**Extraction Strategy**:
```python
# Step 1: Query condition notes
SELECT c.id as condition_id, cn.note_text, cn.note_time
FROM condition c
JOIN condition_note cn ON c.id = cn.condition_id
WHERE c.subject_reference = 'Patient/...'
  AND LOWER(cn.note_text) LIKE '%grade%'
  OR LOWER(cn.note_text) LIKE '%glioma%'

# Step 2: Call MedGemma
call_medgemma(
    text=note_text,
    variable='who_grade',
    context={'condition_id': condition_id}
)
```

**Priority**: 🟡 **MEDIUM** - Backup source for WHO grade, useful for context

---

### 4. v_procedures_tumor (LOW - Procedure Notes)

**Table**: `procedure_note`

**Free Text Field**: `note_text`

**Content**: Operative notes, procedure details (may duplicate binary files)

**Variables to Extract**:
- `extent_of_resection` - GTR, STR, biopsy
- `surgical_complications` - Intraoperative complications

**Current State in View**:
- ❌ **NOT included in v_procedures_tumor view**
- Available in base table: `procedure_note.note_text`

**Priority**: 🟢 **LOW** - Likely duplicates binary operative notes, use binary files as primary source

---

### 5. v_hydrocephalus_procedures (LOW - Device Notes)

**Table**: `procedure_note`

**Free Text Field**: `note_text` (contains shunt programmability info)

**Content**: Shunt device details, programmable valve info

**Example**:
```
"Medtronic Strata programmable valve placed at setting 1.5.
Post-op imaging confirms appropriate placement."
```

**Variables to Extract**:
- `hydro_shunt_programmable` - Yes/No
- `shunt_valve_setting` - Initial pressure setting

**Current State in View**:
- ✅ **Logic included in v_hydrocephalus_procedures**
- Keywords searched: 'programmable', 'strata', 'hakim', 'polaris'
- CASE statement extracts boolean from note_text

**Extraction Strategy**: Already handled in view with keyword search

**Priority**: ✅ **DONE** - Solved with SQL CASE statement in view

---

### 6. v_medications (MEDIUM - Dosage Text)

**Table**: `medication_request`

**Free Text Field**: `dosage_text`

**Content**: Dosing instructions, route, frequency

**Example**:
```
"Vinblastine 6 mg/m2 IV weekly x 26 weeks, then every 2 weeks x 26 weeks.
Hold for ANC <750 or platelets <75K."
```

**Variables to Extract**:
- `chemotherapy_dose` - Dose and units (mg/m2)
- `chemotherapy_route` - IV, PO, intrathecal
- `chemotherapy_frequency` - Weekly, every 2 weeks, daily
- `chemotherapy_duration` - Total cycles/weeks

**Current State in View**:
- ❌ **NOT included in v_medications view**
- Available in base table: `medication_request_dosage_instruction.text`

**Extraction Strategy**:
```python
# Step 1: Query medication dosage
SELECT
    mr.id as medication_request_id,
    mr.medication_reference_display,
    mr.authored_on,
    mrdi.text as dosage_text
FROM medication_request mr
JOIN medication_request_dosage_instruction mrdi ON mr.id = mrdi.medication_request_id
WHERE mr.subject_reference = 'Patient/...'
  AND LOWER(mr.medication_reference_display) LIKE '%vinblastine%'

# Step 2: Call MedGemma
call_medgemma(
    text=dosage_text,
    variable='chemotherapy_dose',
    context={'medication': medication_reference_display}
)
```

**Priority**: 🟡 **MEDIUM** - Useful for dosing details, not critical for MVP

---

## Summary: Free Text Fields by Priority

| Priority | View | Field | Base Table | Included in View? | Variables (Count) |
|----------|------|-------|------------|-------------------|-------------------|
| 🔴 **HIGHEST** | v_molecular_tests | `test_result_narrative` | molecular_test_results | ❌ No | mutation, idh_mutation, mgmt_methylation, tmb (4) |
| 🔴 **HIGHEST** | v_imaging | `report_conclusion`, `result_information` | diagnostic_report, radiology_imaging_mri_results | ✅ Yes | tumor_location, measurements, metastasis, tumor_status (4) |
| 🟡 **MEDIUM** | v_diagnoses | `note_text` | condition_note | ❌ No | who_grade, tumor_location (backup) (2) |
| 🟡 **MEDIUM** | v_medications | `dosage_text` | medication_request_dosage_instruction | ❌ No | dose, route, frequency (3) |
| 🟢 **LOW** | v_procedures_tumor | `note_text` | procedure_note | ❌ No | extent_of_resection (backup) (1) |
| ✅ **DONE** | v_hydrocephalus_procedures | `note_text` | procedure_note | ✅ Yes (extracted via CASE) | shunt_programmable (1) |

**Total Variables Requiring Athena Free Text Extraction**: ~15 variables (9 high-priority)

---

## Updated Extraction Workflow

### Original Workflow (Binary Files Only):
```
Step 1: Query timeline from structured fields → dates
Step 2: Select binary files using metadata → document IDs
Step 3: Check S3 availability → available IDs
Step 4: Extract text from S3 → document text
Step 5: Call MedGemma on document text → variable values
Step 6: Validate against structured fields → confidence scores
Step 7: Output JSON
```

### Updated Workflow (Binary Files + Athena Free Text):
```
Step 1: Query timeline from structured fields → dates

Step 2A: Select binary files using metadata → document IDs
Step 2B: Query Athena views for free text fields → text fields

Step 3: Check S3 availability (binary files only) → available IDs

Step 4A: Extract text from S3 (binary files) → document text
Step 4B: Combine Athena free text fields → report text

Step 5A: Call MedGemma on binary document text → variable values
Step 5B: Call MedGemma on Athena free text → variable values

Step 6: Validate ALL extractions against structured fields → confidence scores
  - Cross-check binary file extractions with Athena structured data
  - Cross-check Athena free text extractions with Athena structured data
  - Resolve conflicts (prioritize source with higher confidence)

Step 7: Output JSON with source attribution (binary file vs Athena free text)
```

---

## Data Source Hierarchy by Variable

**Example: tumor_location**

1. **Primary Source**: v_imaging.report_conclusion (Athena free text)
   - Always available for patients with imaging
   - Most detailed anatomical description
   - Already in structured table (no S3 lookup needed)

2. **Secondary Source**: Radiology reports (binary files from v_binary_files)
   - May be more detailed (full report vs conclusion only)
   - Requires S3 availability check (57% success rate)
   - Slower (download + text extraction)

3. **Tertiary Source**: v_diagnoses.condition_body_site (structured field)
   - Limited anatomical detail
   - May be outdated (not updated after imaging)

**Extraction Strategy**:
```python
# Try Athena free text first (fast, always available)
tumor_location_athena = extract_from_athena_text(
    view='v_imaging',
    field='report_conclusion',
    variable='tumor_location'
)

if tumor_location_athena.confidence > 0.80:
    return tumor_location_athena  # High confidence, use Athena
else:
    # Fall back to binary files
    tumor_location_binary = extract_from_binary_files(
        practice_setting='radiology',
        variable='tumor_location'
    )

    # Return highest confidence
    return max([tumor_location_athena, tumor_location_binary],
               key=lambda x: x.confidence)
```

---

## Implementation Changes Required

### 1. Update master-workflow.md

**New Step 2B**: Query Athena Free Text Fields

**New Step 4B**: Combine Athena Free Text

**New Step 5B**: Call MedGemma on Athena Text

### 2. Update variable-schema.md

For each variable, specify:
- **Primary Source**: Athena free text field OR binary file
- **Athena Free Text Source**: View name + field name (if applicable)
- **Binary File Source**: Practice setting + document type

**Example**:
```markdown
### tumor_location
- **Primary Source**: Athena free text (v_imaging.report_conclusion)
- **Secondary Source**: Binary files (Radiology reports)
- **Tertiary Source**: Structured field (v_diagnoses.condition_body_site)
```

### 3. Update simple_orchestrator.py

**New Function**:
```python
def query_athena_free_text(patient_fhir_id: str, view: str, fields: List[str]) -> List[Dict]:
    """
    Query Athena view to get free text fields for MedGemma extraction

    Args:
        patient_fhir_id: Patient FHIR ID
        view: View name (e.g., 'v_imaging', 'v_molecular_tests')
        fields: Free text field names (e.g., ['report_conclusion', 'result_information'])

    Returns:
        List of dicts with free text content and metadata
    """
    # Build query dynamically based on view and fields
    # Return text content with context (date, test type, etc.)
```

**Updated Function**:
```python
def call_medgemma(
    text: str,
    variable: str,
    context: Dict,
    source_type: str = 'binary_file'  # NEW: 'binary_file' or 'athena_free_text'
) -> Dict:
    """
    Call MedGemma for variable extraction

    Args:
        text: Document text or Athena free text
        variable: Variable to extract
        context: Patient context (dates, diagnosis, etc.)
        source_type: 'binary_file' or 'athena_free_text'

    Returns:
        Extraction result with confidence, evidence, source_type
    """
    # Adjust prompt based on source_type
    # Binary files: "Extract from clinical document"
    # Athena free text: "Extract from radiology report conclusion"
```

### 4. Update MVP_REQUIREMENTS_AND_IMPLEMENTATION.md

**New Requirement R2.5**:
```markdown
### R2.5: `query_athena_free_text(patient_fhir_id, view, fields) -> List[Dict]`
- [ ] Query Athena views for free text fields
- [ ] Support views: v_imaging, v_molecular_tests, v_diagnoses, v_medications
- [ ] Return text content with metadata (date, report type, etc.)
- [ ] Handle NULL/empty fields gracefully
```

---

## MVP Impact Assessment

### Original MVP (Binary Files Only):
- **5 variables tested**: date_of_birth, primary_diagnosis, who_grade, surgery_date, chemotherapy_agent
- **Athena free text usage**: 0 variables

### Updated MVP (Binary Files + Athena Free Text):
- **5 variables tested**: Same 5 variables
- **Athena free text usage**:
  - ❌ `date_of_birth` - Structured field only
  - ✅ `primary_diagnosis` - Could use v_diagnoses.condition_note as backup
  - ✅ `who_grade` - Could use v_diagnoses.condition_note as backup
  - ❌ `surgery_date` - Structured field only
  - ❌ `chemotherapy_agent` - Structured field only

**Conclusion**: MVP still valid, but should add **tumor_location** as 6th variable to demonstrate Athena free text extraction from v_imaging.

---

## Recommended MVP Update

### Original MVP (5 variables):
1. date_of_birth (structured)
2. primary_diagnosis (binary file - pathology)
3. who_grade (binary file - pathology)
4. surgery_date (structured + binary file validation)
5. chemotherapy_agent (structured validation)

### Updated MVP (6 variables):
1. date_of_birth (structured)
2. primary_diagnosis (binary file - pathology)
3. who_grade (binary file - pathology)
4. surgery_date (structured + binary file validation)
5. chemotherapy_agent (structured validation)
6. **tumor_location** (Athena free text - v_imaging.report_conclusion) ← NEW

**Why tumor_location?**
- Demonstrates Athena free text extraction
- Always available (v_imaging has data for all patients with imaging)
- No S3 availability issues (text already in Athena)
- Validates against v_diagnoses.condition_body_site (structured field)
- Critical clinical variable for tumor characterization

---

## Next Steps

1. ✅ Document free text fields (this file)
2. Update master-workflow.md with Step 2B, 4B, 5B
3. Update variable-schema.md with Athena free text sources
4. Update simple_orchestrator.py with `query_athena_free_text()` function
5. Update MVP requirements to add R2.5
6. Test with patient C1277724 (6 variables including tumor_location)

---

**Created**: 2025-10-19
**Status**: Analysis complete, implementation pending
