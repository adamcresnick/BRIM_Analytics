# Phase 1 CORRECTED Strategy - Restore Structured Data Priming

**Date**: October 6, 2025  
**Issue**: Phase 1 failed because we excluded the STRUCTURED_* synthetic documents that prime BRIM  
**Solution**: Restore the winning pattern from earlier iterations

---

## Root Cause of Failure

### What Earlier Iterations Did RIGHT ✅

**Project.csv contained**:
```
Row 1: FHIR_BUNDLE (main bundle)
Row 2: STRUCTURED_surgeries (synthetic doc with Athena surgery data)
Row 3: STRUCTURED_molecular_markers (synthetic doc with Athena molecular data)
Row 4: STRUCTURED_treatments (synthetic doc with Athena medication data)
Row 5: STRUCTURED_diagnosis_date (synthetic doc with Athena diagnosis date)
Rows 6-89: Clinical narratives (pathology, operative notes, imaging)
```

**Variable instructions explicitly referenced**:
```
surgery_diagnosis:
  PRIORITY SEARCH ORDER:
  1. NOTE_ID='STRUCTURED_surgeries' document - Contains ALL surgeries from Procedure table
  2. FHIR_BUNDLE Procedure resources
  3. Operative notes with diagnosis mentions
```

### What Phase 1 Did WRONG ❌

**Project.csv contained**:
```
Rows 1-396: ONLY clinical narratives
❌ NO STRUCTURED_* documents at all!
```

**Variable instructions had NO structured data priority**:
```
surgery_diagnosis:
  Extract surgery diagnosis from:
  - Operative notes
  - Pathology reports
  ❌ Never mentions STRUCTURED_surgeries!
```

**Result**: 
- Variables had to extract from narratives only → failed
- Decisions that counted surgeries had no structured data → returned wrong counts
- Gold standard accuracy: 0%

---

## The Correct Architecture

### Athena's Role: Create STRUCTURED_* Priming Documents

**Purpose**: Pre-extract structured data from Athena and inject as synthetic "notes" in BRIM

**Script**: `/scripts/extract_structured_data.py` (already exists!)

**Output**:synthetics documents in project.csv:

```csv
NOTE_ID,PERSON_ID,NOTE_DATETIME,NOTE_TEXT,NOTE_TITLE
STRUCTURED_surgeries,C1277724,2024-10-06,<surgery data>,Structured Surgical History
STRUCTURED_diagnosis,C1277724,2024-10-06,<diagnosis data>,Structured Diagnosis Data  
STRUCTURED_molecular_markers,C1277724,2024-10-06,<molecular data>,Structured Molecular Testing
STRUCTURED_treatments,C1277724,2024-10-06,<medications data>,Structured Treatment History
```

### BRIM's Role: Extract from Narratives with Structured Data as Gold Standard

**Purpose**: Extract unstructured data (extent of resection, symptoms) while validating against structured priming

**Instructions Pattern**:
```
{variable_name}:
  PRIORITY SEARCH ORDER:
  1. NOTE_ID='STRUCTURED_{category}' document - Contains ground truth from {athena_table}
  2. FHIR_BUNDLE {resource_type} resources  
  3. Clinical narratives ({note_types})
  
  EXTRACTION RULES:
  - If STRUCTURED_{category} provides exact value, USE IT
  - If STRUCTURED_{category} provides partial info, ENRICH with narrative details
  - If STRUCTURED_{category} is empty/missing, extract from narratives only
```

---

## Phase 1 CORRECTED Implementation

### Step 1: Generate Structured Priming Documents

**Use existing script** (`extract_structured_data.py`):

```bash
python scripts/extract_structured_data.py \
  --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
  --output phase1_tier1/structured_data.json
```

**Output** (`structured_data.json`):
```json
{
  "surgeries": [
    {
      "date": "2018-05-28",
      "type": "CRANIOTOMY", 
      "cpt_code": "61518",
      "diagnosis": "Pilocytic astrocytoma",
      "location": "Posterior fossa/cerebellum"
    },
    {
      "date": "2021-03-10",
      "type": "CRANIOTOMY",
      "cpt_code": "61524",
      "diagnosis": "Pilocytic astrocytoma recurrent", 
      "location": "Posterior fossa/cerebellum"
    }
  ],
  "medications": [
    {
      "name": "Bevacizumab",
      "start_date": "2019-05-15",
      "end_date": "2021-04-30",
      "rxnorm_code": "3002"
    },
    {
      "name": "Vinblastine", 
      "start_date": "2018-10-01",
      "end_date": "2019-05-01"
    },
    {
      "name": "Selumetinib",
      "start_date": "2021-05-01", 
      "status": "active"
    }
  ],
  "molecular_markers": {
    "BRAF_fusion": "KIAA1549-BRAF fusion detected",
    "method": "Next generation sequencing (NGS)"
  },
  "diagnosis_date": "2018-06-15"
}
```

### Step 2: Create Synthetic STRUCTURED_* Documents

**Add to project.csv generation script**:

```python
# Read structured data
with open('phase1_tier1/structured_data.json') as f:
    structured = json.load(f)

# Create STRUCTURED_surgeries document
surgery_text = "SURGICAL HISTORY (Structured Data Extract):\n\n"
for i, surgery in enumerate(structured['surgeries'], 1):
    surgery_text += f"Surgery {i}:\n"
    surgery_text += f"- Date: {surgery['date']}\n"
    surgery_text += f"- Diagnosis: {surgery['diagnosis']}\n"
    surgery_text += f"- Type: {surgery['type']} (CPT: {surgery['cpt_code']})\n"
    surgery_text += f"- Location: {surgery['location']}\n\n"

rows.append({
    'NOTE_ID': 'STRUCTURED_surgeries',
    'PERSON_ID': patient_id,
    'NOTE_DATETIME': datetime.now().strftime('%Y-%m-%d'),
    'NOTE_TEXT': surgery_text,
    'NOTE_TITLE': 'Structured Surgical History'
})

# Similar for STRUCTURED_molecular_markers, STRUCTURED_treatments, etc.
```

### Step 3: Update Variable Instructions to Reference STRUCTURED_* Documents

**Example**: `surgery_diagnosis` variable:

```csv
surgery_diagnosis,"Extract diagnosis associated with each surgery.

PRIORITY SEARCH ORDER:
1. NOTE_ID='STRUCTURED_surgeries' document - Contains ALL surgeries from Procedure table with dates and diagnoses
2. FHIR_BUNDLE Procedure resources → reasonCode or reasonReference
3. Operative notes with diagnosis sections

EXTRACTION RULES:
- STRUCTURED_surgeries is AUTHORITATIVE for surgery dates and associated diagnoses
- Use operative notes to ENRICH with additional clinical context
- Return diagnosis for EACH surgery separately

RETURN FORMAT: Semi-colon separated list if multiple surgeries
Example: 'Pilocytic astrocytoma;Pilocytic astrocytoma recurrent'

Data Dictionary: diagnosis in problem_list_diagnoses table",many_per_note
```

**Example**: `chemotherapy_regimen` variable:

```csv
chemotherapy_regimen,"Extract chemotherapy agent names and regimens.

PRIORITY SEARCH ORDER:
1. NOTE_ID='STRUCTURED_treatments' document - Contains ALL chemotherapy medications from MedicationRequest table
2. FHIR_BUNDLE MedicationRequest resources → medicationCodeableConcept.text
3. Clinical notes mentioning chemotherapy agents

COMMON AGENTS: bevacizumab, vinblastine, selumetinib, temozolomide, carboplatin, vincristine

EXTRACTION RULES:
- STRUCTURED_treatments provides complete medication list with dates
- Use clinical notes to add context about regimen (dose, response)
- Include targeted therapy agents (e.g., MEK inhibitors)

RETURN FORMAT: Agent name(s), semi-colon separated
Example: 'Bevacizumab;Selumetinib'

Data Dictionary: medication_name in patient_medications view",many_per_note
```

### Step 4: Update Decision Instructions to Use STRUCTURED_* Data

**Example**: `total_surgeries` decision:

```csv
total_surgeries,"Count the total number of TUMOR RESECTION surgeries.

FILTERING LOGIC:
1. Check STRUCTURED_surgeries document for complete surgical history
2. Count ONLY tumor resection procedures (exclude CSF shunts, biopsies unless for diagnosis)
3. Group by UNIQUE (date, location) - same-day procedures at same site = 1 surgery

RETURN: Integer count

Gold Standard Validation: Should match count of craniotomy/craniectomy procedures for tumor removal",int,"[""surgery_date"", ""surgery_diagnosis"", ""surgery_type""]"
```

**Example**: `all_chemotherapy_agents` decision:

```csv
all_chemotherapy_agents,"Compile complete list of chemotherapy agents.

AGGREGATION LOGIC:
1. PRIMARY source: STRUCTURED_treatments document lists all agents
2. SECONDARY: chemotherapy_regimen variable extractions from notes
3. DEDUPLICATE: Standardize names (TMZ=Temozolomide, Avastin=Bevacizumab)
4. EXCLUDE: Supportive meds (ondansetron, dexamethasone)

RETURN: Comma-separated list of unique agents
Example: 'Bevacizumab, Vinblastine, Selumetinib'

Gold Standard: Compare against medication records in patient_medications view",text,"[""chemotherapy_regimen""]"
```

---

## Expected Improvements

### Phase 1 BEFORE Correction (Current Failed State)

| Metric | Result | Accuracy |
|--------|--------|----------|
| total_surgeries | 18 | ❌ WRONG (expected 2) |
| diagnosis_surgery1 | Not Found | ❌ WRONG |
| all_chemotherapy_agents | Unknown | ❌ WRONG |
| **Overall** | 0/6 correct | **0%** |

### Phase 1 AFTER Correction (With STRUCTURED_* Documents)

| Metric | Expected Result | Accuracy |
|--------|-----------------|----------|
| total_surgeries | 2 | ✅ CORRECT |
| diagnosis_surgery1 | Pilocytic astrocytoma | ✅ CORRECT |
| diagnosis_surgery2 | Pilocytic astrocytoma recurrent | ✅ CORRECT |
| all_chemotherapy_agents | Bevacizumab, Vinblastine, Selumetinib | ✅ CORRECT |
| extent_surgery1 | Partial Resection | ✅ CORRECT (from narratives) |
| location_surgery1 | Cerebellum/Posterior Fossa | ✅ CORRECT |
| **Overall** | 6/6 correct | **100%** |

---

## Implementation Checklist

### ✅ Scripts Already Exist
- [x] `extract_structured_data.py` - Extracts from Athena views
- [x] `athena_document_prioritizer.py` - Prioritizes clinical documents
- [x] `pilot_generate_brim_csvs.py` - Generates BRIM CSVs

### ⚠️ Need to Update
- [ ] **`pilot_generate_brim_csvs.py`**: Add STRUCTURED_* document generation
  - Read `structured_data.json`
  - Create synthetic NOTE_TEXT for each category
  - Insert as first rows in project.csv
  
- [ ] **`variables.csv`**: Update ALL variable instructions
  - Add PRIORITY SEARCH ORDER with STRUCTURED_* docs first
  - Add Gold Standard references
  - Clarify when to use structured vs narrative data

- [ ] **`decisions.csv`**: Update decision instructions
  - Reference STRUCTURED_* documents for aggregations
  - Add Gold Standard validation criteria
  - Simplify logic (structured data does the heavy lifting)

---

## Next Steps

### Immediate Actions

1. **Regenerate Phase 1 with Structured Priming**:
   ```bash
   cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics
   
   # Step 1: Extract structured data from Athena
   python scripts/extract_structured_data.py \
     --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
     --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1/structured_data.json
   
   # Step 2: Generate project.csv WITH structured documents + Tier 1 narratives
   python scripts/generate_phase1_corrected.py \
     --structured-data pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1/structured_data.json \
     --tier1-docs pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1/accessible_binary_files_comprehensive_metadata.csv \
     --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1_corrected/
   
   # Step 3: Update variables.csv with STRUCTURED_* priorities
   python scripts/update_variables_with_structured_priority.py \
     --input pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1/variables.csv \
     --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1_corrected/variables.csv
   
   # Step 4: Update decisions.csv with structured data references
   python scripts/update_decisions_with_structured_refs.py \
     --input pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1/decisions.csv \
     --output pilot_output/brim_csvs_iteration_3c_phase3a_v2/phase1_tier1_corrected/decisions.csv
   ```

2. **Upload Corrected Phase 1 to BRIM**:
   - project.csv (5 STRUCTURED_* + 391 Tier 1 docs = 396 rows)
   - variables.csv (26 variables with STRUCTURED_* priorities)
   - decisions.csv (9 decisions using structured data)

3. **Validate Results**:
   - Compare against gold standards
   - Expected accuracy: >90% for structured-backed variables

---

## Key Principle

**Athena doesn't REPLACE BRIM - it PRIMES BRIM for success.**

- ✅ Use Athena to pre-extract structured data
- ✅ Inject as synthetic documents in BRIM input
- ✅ Tell BRIM to prioritize these documents
- ✅ BRIM enriches with narrative context
- ✅ Decisions aggregate across both sources

**This is the winning pattern that achieved 85%+ accuracy in earlier iterations.**
