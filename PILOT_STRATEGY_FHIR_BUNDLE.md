# BRIM + FHIR Bundle Pilot Strategy
## Patient: e4BwD8ZYDBccepXcJ.Ilo3w3

**Date:** October 2, 2025  
**Goal:** Validate FHIR Bundle → BRIM → Clinical Trial CSV workflow with real data  
**Approach:** Manual UI testing first, then API automation

---

## 🎯 PILOT OBJECTIVES

### Primary Goals
1. **Extract raw FHIR resources** for patient `e4BwD8ZYDBccepXcJ.Ilo3w3` from Athena
2. **Assemble FHIR Bundle** combining structured + unstructured data
3. **Generate BRIM-compatible CSVs** (project, variables, decisions)
4. **Validate against manually curated data** in `/20250723_multitab_csvs/`
5. **Compare UI vs API workflows** for BRIM submission

### Success Criteria
- ✅ FHIR Bundle contains all 18 target CSV data points
- ✅ BRIM extracts match manually curated values ≥80% accuracy
- ✅ Workflow is reproducible for other patients
- ✅ Token count < 50,000 per BRIM submission

---

## 📊 DATA SOURCES FOR PATIENT e4BwD8ZYDBccepXcJ.Ilo3w3

### Source 1: Athena Raw FHIR Tables
**Database:** `radiant_prd_343218191717_us_east_1_prd_fhir_datastore_*`

#### Resources to Query:
```sql
-- Patient demographics
SELECT * FROM patient WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

-- All conditions/diagnoses
SELECT * FROM condition 
WHERE subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- All procedures (surgeries)
SELECT * FROM procedure 
WHERE subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- All medications
SELECT * FROM medication_request 
WHERE subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- All observations (labs, vitals, molecular tests)
SELECT * FROM observation 
WHERE subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- All encounters
SELECT * FROM encounter 
WHERE subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'
```

### Source 2: S3 NDJSON Clinical Notes
**Bucket:** `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`  
**Path:** `prd/ndjson/DocumentReference/`

```bash
# Find all documents for patient
aws s3api select-object-content \
  --bucket "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline" \
  --key "prd/ndjson/DocumentReference/part-*.ndjson" \
  --expression "SELECT * FROM S3Object[*] s WHERE s.subject.reference LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'" \
  --expression-type 'SQL' \
  --input-serialization '{"JSON": {"Type": "LINES"}}' \
  --output-serialization '{"JSON": {"RecordDelimiter": "\n"}}' \
  --profile "343218191717_AWSAdministratorAccess" \
  patient_documents.json
```

### Source 3: Binary Content (Clinical Notes)
**Table:** `binary`  
**Query:** Extract using DocumentReference.content[].attachment.url

---

## 🔄 PROPOSED WORKFLOW

### **Phase 1: Data Discovery & Extraction (Python)**

#### Step 1.1: Query Athena for Structured FHIR
```python
# Script: scripts/extract_fhir_bundle.py
def extract_patient_fhir_bundle(patient_id='e4BwD8ZYDBccepXcJ.Ilo3w3'):
    """
    Query Athena for all FHIR resources, preserve nested structures.
    Returns: FHIR Bundle as JSON
    """
    resources = []
    
    # Patient
    patient = query_athena(f"""
        SELECT 
          CAST(ROW(
            'Patient', id, identifier, name, birthDate, gender,
            deceasedBoolean, deceasedDateTime, address
          ) AS JSON) as resource
        FROM patient WHERE id = '{patient_id}'
    """)
    resources.append(patient)
    
    # Procedures (surgeries)
    procedures = query_athena(f"""
        SELECT 
          CAST(ROW(
            'Procedure', id, code, subject, performedDateTime,
            status, bodySite, performer, note
          ) AS JSON) as resource
        FROM procedure 
        WHERE subject.reference LIKE '%{patient_id}%'
    """)
    resources.extend(procedures)
    
    # Continue for Condition, MedicationRequest, Observation, Encounter...
    
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources]
    }
    
    # Clean nulls to reduce token count
    return remove_null_fields(bundle)
```

#### Step 1.2: Query S3 for DocumentReferences
```python
def discover_clinical_notes(patient_id):
    """
    Use S3 Select to find all DocumentReferences.
    Returns: List of document metadata with Binary IDs
    """
    s3_query = f"""
        SELECT s.id, s.type.text, s.date, 
               s.content[0].attachment.url as binary_url
        FROM S3Object[*] s
        WHERE s.subject.reference LIKE '%{patient_id}%'
    """
    
    documents = s3_select_query(
        bucket='radiant-prd-343218191717-us-east-1-prd-ehr-pipeline',
        key_prefix='prd/ndjson/DocumentReference/',
        query=s3_query
    )
    
    return documents
```

#### Step 1.3: Extract Binary Content
```python
def extract_binary_content(binary_id):
    """
    Query Athena Binary table, decode base64.
    Returns: Decoded text content
    """
    result = query_athena(f"""
        SELECT data, contenttype
        FROM binary
        WHERE id = '{binary_id}'
    """)
    
    decoded = base64.b64decode(result['data'])
    
    # Sanitize HTML if needed
    if 'html' in result['contenttype'].lower():
        decoded = sanitize_html(decoded)
    
    return decoded.decode('utf-8')
```

---

### **Phase 2: BRIM CSV Generation**

#### Step 2.1: Generate Project CSV
**Format:** 5 columns (NOTE_ID, PERSON_ID, NOTE_DATETIME, NOTE_TEXT, NOTE_TITLE)

```python
def generate_brim_project_csv(fhir_bundle, clinical_notes, output_path):
    """
    Create BRIM project CSV with:
    - 1 FHIR_BUNDLE document (the entire bundle as JSON)
    - N clinical notes (operative, pathology, radiology, etc.)
    """
    rows = []
    
    # Row 1: FHIR Bundle as a "document"
    rows.append({
        'NOTE_ID': 'fhir_bundle_001',
        'PERSON_ID': 'e4BwD8ZYDBccepXcJ.Ilo3w3',
        'NOTE_DATETIME': datetime.now().isoformat(),
        'NOTE_TEXT': json.dumps(fhir_bundle, separators=(',', ':')),  # Compact JSON
        'NOTE_TITLE': 'FHIR_BUNDLE'
    })
    
    # Rows 2-N: Clinical notes
    for idx, note in enumerate(clinical_notes, start=1):
        binary_id = extract_binary_id(note['binary_url'])
        content = extract_binary_content(binary_id)
        
        rows.append({
            'NOTE_ID': f'note_{idx:03d}',
            'PERSON_ID': 'e4BwD8ZYDBccepXcJ.Ilo3w3',
            'NOTE_DATETIME': note['date'],
            'NOTE_TEXT': content.replace('"', '""'),  # CSV escape
            'NOTE_TITLE': classify_note_type(note['type.text'])
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
```

#### Step 2.2: Generate Variables CSV
**Format:** 11 columns (for BRIM API) or 7 columns (for UI)

```python
def generate_brim_variables_csv(target_csvs_spec, output_path):
    """
    Create variables that extract from both FHIR Bundle and narrative notes.
    Based on 18 target CSVs in /20250723_multitab_csvs/
    """
    variables = []
    
    # Classification variables (MUST be first)
    variables.append({
        'variable_name': 'document_type',
        'instruction': 'Return NOTE_TITLE value exactly: FHIR_BUNDLE, OPERATIVE_NOTE, PATHOLOGY, RADIOLOGY, or PROGRESS_NOTE',
        'variable_type': 'text',
        'scope': 'one_per_note',
        'can_be_missing': 0,
        'order': 0
    })
    
    # FHIR extraction variables
    variables.append({
        'variable_name': 'fhir_patient_birthdate',
        'instruction': 'If document_type=FHIR_BUNDLE: In the JSON, find entry where resource.resourceType=Patient. Return resource.birthDate value. Otherwise return N/A',
        'variable_type': 'text',
        'scope': 'one_per_note',
        'can_be_missing': 0,
        'order': 1
    })
    
    variables.append({
        'variable_name': 'fhir_diagnoses_list',
        'instruction': 'If document_type=FHIR_BUNDLE: Find ALL entries where resource.resourceType=Condition. For each, extract resource.code.text. Return as semicolon-separated list. Otherwise return N/A',
        'variable_type': 'text',
        'scope': 'one_per_note',
        'can_be_missing': 0,
        'order': 2
    })
    
    # Add variables for all 18 target CSVs...
    # (See detailed spec below)
    
    df = pd.DataFrame(variables)
    df.to_csv(output_path, index=False)
```

#### Step 2.3: Generate Decisions CSV
**Format:** 5 columns (decision_name, instruction, decision_type, prompt_template, variables)

```python
def generate_brim_decisions_csv(output_path):
    """
    Dependent variables that aggregate/validate across documents.
    """
    decisions = []
    
    # Merge FHIR + narrative diagnoses
    decisions.append({
        'decision_name': 'diagnosis_validated',
        'instruction': 'Compare fhir_diagnoses_list from FHIR_BUNDLE with pathologic_diagnosis from PATHOLOGY documents. If they contain the same diagnosis (ignoring word order), return diagnosis with (VALIDATED). If different, return FHIR: X | Pathology: Y (CONFLICT)',
        'decision_type': 'text',
        'prompt_template': '',
        'variables': 'fhir_diagnoses_list;pathologic_diagnosis;document_type'
    })
    
    # Continue for other aggregations...
    
    df = pd.DataFrame(decisions)
    df.to_csv(output_path, index=False)
```

---

### **Phase 3: BRIM Submission (UI First, API Later)**

#### **Option A: Manual UI Testing (RECOMMENDED FOR PILOT)**

**Why Start with UI:**
1. ✅ Visual validation of CSV formats before API
2. ✅ Immediate feedback on LLM extraction quality
3. ✅ Can adjust variable instructions iteratively
4. ✅ Easier debugging of prompt issues
5. ✅ Confirms BRIM can handle FHIR JSON size

**Steps:**
1. Log into BRIM platform
2. Create new project: "RADIANT_FHIR_Pilot"
3. Upload project CSV (FHIR bundle + notes)
4. Upload variables CSV
5. Upload decisions CSV
6. Run extraction
7. Download results
8. Compare against `/20250723_multitab_csvs/` manually

#### **Option B: API Automation (After UI Validation)**

```python
from src.brim_api_client import BRIMAPIClient

client = BRIMAPIClient(api_key=os.getenv('BRIM_API_KEY'))

# Create project
project_id = client.create_project(
    name='RADIANT_FHIR_Pilot_e4BwD8ZYDBccepXcJ',
    description='Testing FHIR Bundle extraction'
)

# Upload files
client.upload_project_csv(project_id, 'output/project.csv')
client.upload_variables_csv(project_id, 'output/variables.csv')
client.upload_decisions_csv(project_id, 'output/decisions.csv')

# Submit job
job_id = client.submit_extraction_job(project_id)

# Wait for completion
client.wait_for_completion(job_id)

# Download results
results = client.download_results(job_id, 'output/brim_results.csv')
```

---

## 📋 DETAILED VARIABLE SPECIFICATIONS

### Variables for 18 Target CSVs

#### **CSV 1: demographics.csv**
```csv
variable_name,instruction,variable_type,scope
fhir_patient_id,If FHIR_BUNDLE: Extract resource.identifier[0].value where system contains 'mrn',text,one_per_note
fhir_gender,If FHIR_BUNDLE: Extract resource.gender from Patient resource,text,one_per_note
fhir_birthdate,If FHIR_BUNDLE: Extract resource.birthDate from Patient resource,text,one_per_note
fhir_race,If FHIR_BUNDLE: Extract resource.extension where url contains 'us-core-race',text,one_per_note
fhir_ethnicity,If FHIR_BUNDLE: Extract resource.extension where url contains 'us-core-ethnicity',text,one_per_note
```

#### **CSV 2: diagnosis.csv**
```csv
fhir_diagnoses_all,If FHIR_BUNDLE: Extract ALL resource.code.text from Condition resources,text,one_per_note
fhir_diagnosis_dates,If FHIR_BUNDLE: Extract resource.recordedDate from Condition resources,text,one_per_note
pathologic_diagnosis,If PATHOLOGY: Extract final diagnosis after 'DIAGNOSIS:' or 'IMPRESSION:',text,one_per_note
who_grade,If PATHOLOGY or RADIOLOGY: Extract WHO grade (I/II/III/IV),text,one_per_note
tumor_location,If OPERATIVE_NOTE or RADIOLOGY: Extract anatomical location,text,one_per_note
metastasis_mentioned,Extract any mention of metastasis/spread,text,one_per_note
```

#### **CSV 3: treatments.csv**
```csv
fhir_procedures_list,If FHIR_BUNDLE: Extract ALL resource.code.text from Procedure resources with CPT codes,text,one_per_note
fhir_procedure_dates,If FHIR_BUNDLE: Extract resource.performedDateTime from Procedure resources,text,one_per_note
extent_of_resection,If OPERATIVE_NOTE: Extract GTR/NTR/STR/Biopsy percentage,text,one_per_note
chemotherapy_agents,If PROGRESS_NOTE: Extract chemotherapy drug names,text,many_per_note
radiation_dose,If mentions radiation: Extract total dose in cGy or Gy,text,one_per_note
```

#### **CSV 4: concomitant_medications.csv**
```csv
fhir_medications_list,If FHIR_BUNDLE: Extract ALL resource.medicationCodeableConcept from MedicationRequest,text,one_per_note
fhir_rxnorm_codes,If FHIR_BUNDLE: Extract coding.code where system contains 'rxnorm',text,one_per_note
fhir_med_start_dates,If FHIR_BUNDLE: Extract resource.authoredOn from MedicationRequest,text,one_per_note
narrative_medications,Extract medication names mentioned in note text,text,many_per_note
```

#### **CSV 5-18: Measurements, Imaging, Molecular, etc.**
(Similar pattern: FHIR extraction + narrative validation)

---

## ✅ VALIDATION STRATEGY

### Step 1: Direct Comparison
```python
def validate_against_manual_curation(brim_results, manual_csv_dir):
    """
    Compare BRIM extractions vs manually curated CSVs.
    """
    validation_report = {}
    
    # Load manually curated data
    demographics_manual = pd.read_csv(f'{manual_csv_dir}/20250723_multitab__demographics.csv')
    demographics_manual = demographics_manual[
        demographics_manual['research_id'] == 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    ]
    
    # Extract from BRIM results
    demographics_brim = extract_demographics_from_brim(brim_results)
    
    # Compare field by field
    validation_report['demographics'] = compare_records(
        demographics_manual.iloc[0],
        demographics_brim
    )
    
    # Repeat for all 18 CSVs...
    
    return validation_report
```

### Step 2: Accuracy Metrics
```python
def calculate_accuracy(validation_report):
    """
    Field-level accuracy across all CSVs.
    """
    total_fields = 0
    matching_fields = 0
    
    for csv_name, comparisons in validation_report.items():
        for field, result in comparisons.items():
            total_fields += 1
            if result['match']:
                matching_fields += 1
            else:
                print(f"MISMATCH in {csv_name}.{field}:")
                print(f"  Manual: {result['manual_value']}")
                print(f"  BRIM:   {result['brim_value']}")
    
    accuracy = (matching_fields / total_fields) * 100
    print(f"\nOverall Accuracy: {accuracy:.1f}% ({matching_fields}/{total_fields} fields)")
    
    return accuracy
```

---

## 🎯 RECOMMENDATION: **START WITH UI**

### UI Testing Workflow (Today):
1. ✅ Run `scripts/extract_fhir_bundle.py` → generates 3 CSVs
2. ✅ Upload to BRIM UI manually
3. ✅ Validate extraction results
4. ✅ Iterate on variable instructions based on results
5. ✅ Document what works

### API Automation (After UI Success):
1. ✅ Confirm BRIM API endpoints with support
2. ✅ Update `src/brim_api_client.py` with confirmed URLs
3. ✅ Test API authentication
4. ✅ Automate workflow from Step 1-5 above

---

## 📝 NEXT STEPS

### Immediate (Next 1 Hour):
1. **Create extraction script**: `scripts/pilot_extract_patient.py`
   - Query Athena for patient FHIR resources
   - Query S3 for DocumentReferences
   - Extract Binary content
   - Generate FHIR Bundle JSON

2. **Create CSV generation script**: `scripts/pilot_generate_brim_csvs.py`
   - Generate project CSV (bundle + notes)
   - Generate variables CSV (extraction rules)
   - Generate decisions CSV (aggregations)

3. **Run pilot extraction**:
   ```bash
   python scripts/pilot_extract_patient.py --patient-id e4BwD8ZYDBccepXcJ.Ilo3w3
   python scripts/pilot_generate_brim_csvs.py --output-dir ./pilot_output/
   ```

### Short Term (Next 2-4 Hours):
4. **Manual UI testing** in BRIM platform
5. **Validation against manual CSVs**
6. **Iteration on variable instructions**

### Medium Term (Next Day):
7. **API automation** after UI validation
8. **Batch processing** for multiple patients
9. **Documentation** of lessons learned

---

## ❓ QUESTIONS FOR YOU

1. **Do you have BRIM UI access?** Should I generate login instructions?
2. **Token limits:** Is there a known size limit for BRIM submissions?
3. **Manual CSV location:** Confirm path `/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/` has patient `e4BwD8ZYDBccepXcJ.Ilo3w3` data?
4. **S3 access:** Can you confirm the S3 bucket/path for NDJSON files?
5. **Athena table names:** Should I use the raw table names from `e934bc57...csv` or the flattened `fhir_v2_prd_db.*` tables?

---

## ✅ READY TO PROCEED?

**I recommend:**
1. ✅ Review this strategy
2. ✅ Confirm UI vs API preference
3. ✅ I'll create the extraction scripts next
4. ✅ Then we'll generate the 3 BRIM CSVs
5. ✅ You test in UI, I'll build validation script

**Should I proceed with script creation?** 🚀
