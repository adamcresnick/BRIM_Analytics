# Patient Timeline Abstraction - Complete Workflow Walkthrough

**Script:** `patient_timeline_abstraction_V2.py`
**Purpose:** Two-agent iterative workflow for constructing patient clinical journey timelines from RADIANT PCA data
**Agents:** Claude (orchestrator) + MedGemma (extractor)
**Date:** November 1, 2025

---

## Table of Contents

1. [Command Line Invocation](#command-line-invocation)
2. [Initialization Phase](#initialization-phase)
3. [Phase 1: Load Structured Data](#phase-1-load-structured-data-from-athena-views)
4. [Phase 2: Construct Initial Timeline](#phase-2-construct-initial-timeline)
5. [Phase 3: Identify Extraction Gaps](#phase-3-identify-gaps-requiring-binary-extraction)
6. [Phase 4: Prioritized Binary Extraction](#phase-4-prioritized-binary-extraction-with-medgemma)
7. [Phase 5: WHO 2021 Protocol Validation](#phase-5-who-2021-protocol-validation)
8. [Phase 6: Generate Final Artifact](#phase-6-generate-final-timeline-artifact)
9. [Expected Outputs](#expected-outputs)

---

## Command Line Invocation

```bash
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83 \
  --output-dir output/comprehensive_test \
  --max-extractions 10
```

### Parameters:
- `--patient-id`: FHIR Patient ID (with or without "Patient/" prefix)
- `--output-dir`: Directory for timeline artifacts (timestamped subdirectory created automatically)
- `--max-extractions`: Optional limit on binary extractions (for testing)
- `--force-reclassify`: Optional flag to regenerate WHO classification from pathology data

---

## Initialization Phase

### Location: `__init__()` Method (Lines 297-334)

### Step 1: Patient ID Processing

```python
self.patient_id = "Patient/eQSB0y3q..."  # Full FHIR ID
self.athena_patient_id = "eQSB0y3q..."   # Without "Patient/" prefix for Athena queries
```

### Step 2: WHO 2021 Classification Loading

**Method:** `_load_who_classification()` (Lines 336-386)

**Cache Check Logic:**

1. **Check if cache file exists:**
   - Path: `patient_clinical_journey_timeline/data/who_2021_classification_cache.json`
   - If missing: Auto-create from hardcoded `WHO_2021_CLASSIFICATIONS` dictionary

2. **Load from cache:**
   ```
   ✅ Loaded WHO classification from cache for eQSB0y3q...
      Diagnosis: Astrocytoma, IDH-mutant, CNS WHO grade 3
      Classification date: 2025-10-30
      Method: migrated_from_hardcoded
   ```

3. **If not cached (or --force-reclassify):**
   - Calls `_generate_who_classification()` (lines 460-623)
   - Queries `v_pathology_diagnostics` for patient's pathology records
   - Formats data by surgery episode with Priority 1-2 documents
   - Loads `WHO_2021_DIAGNOSTIC_AGENT_PROMPT.md` (681 lines)
   - Calls MedGemma with structured JSON output request
   - Parses response and saves to cache

**Important:** WHO classification uses **free text already in `v_pathology_diagnostics.result_value`** - no additional binary retrieval needed.

### Step 3: Agent Initialization

```python
self.medgemma_agent = MedGemmaAgent(model_name="gemma2:27b", temperature=0.1)
self.binary_agent = BinaryFileAgent(aws_profile="radiant-prod")
```

**Expected Console Output:**
```
✅ MedGemma and BinaryFile agents initialized
Initialized abstractor for Patient/eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
  WHO 2021: Astrocytoma, IDH-mutant, CNS WHO grade 3
```

---

## Phase 1: Load Structured Data from Athena Views

### Location: `_phase1_load_structured_data()` (Lines 751-831)

### Purpose
Query 6 Athena views for patient's structured clinical data.

### Query 1: Pathology Data

```sql
SELECT
    patient_fhir_id,
    diagnostic_date,
    diagnostic_name,
    component_name,
    result_value,              -- 🎯 FREE TEXT ALREADY EXTRACTED
    extraction_priority,       -- 1-5 prioritization
    document_category
FROM v_pathology_diagnostics
WHERE patient_fhir_id = 'eQSB0y3q...'
ORDER BY diagnostic_date
```

**Contains:**
- Pathology reports (Priority 1)
- Molecular/NGS reports (Priority 2)
- IHC results (structured observations)
- **Free text already in `result_value`** - used for WHO classification

### Query 2: Surgical Procedures

```sql
SELECT
    patient_fhir_id,
    proc_performed_date_time,
    surgery_type,
    proc_code_text
FROM v_procedures_tumor
WHERE patient_fhir_id = 'eQSB0y3q...'
    AND is_tumor_surgery = true
ORDER BY proc_performed_date_time
```

**Contains:**
- Surgery dates
- Surgery types (biopsy, resection, etc.)
- **Missing:** Extent of resection (EOR) → will trigger gap

### Query 3: Chemotherapy Episodes

```sql
SELECT
    patient_fhir_id,
    episode_start_datetime,
    episode_end_datetime,
    episode_drug_names
FROM v_chemo_treatment_episodes
WHERE patient_fhir_id = 'eQSB0y3q...'
ORDER BY episode_start_datetime
```

**Contains:**
- Chemotherapy episode dates
- Drug names (comma-separated)
- **Missing:** Protocol names, on-protocol status → will trigger gaps

### Query 4: Radiation Episodes

```sql
SELECT
    patient_fhir_id,
    episode_start_date,
    episode_end_date,
    total_dose_cgy,
    radiation_fields
FROM v_radiation_episode_enrichment
WHERE patient_fhir_id = 'eQSB0y3q...'
ORDER BY episode_start_date
```

**Contains:**
- Radiation episode dates
- Total dose (may be NULL)
- **Missing:** Craniospinal vs focal, fractions → will trigger gaps

### Query 5: Imaging Studies

```sql
SELECT
    patient_fhir_id,
    imaging_date,
    imaging_modality,
    report_conclusion,
    result_diagnostic_report_id,
    diagnostic_report_id
FROM v_imaging
WHERE patient_fhir_id = 'eQSB0y3q...'
ORDER BY imaging_date
```

**Contains:**
- Imaging dates (MRI, CT, etc.)
- Report conclusions (may be vague/NULL)
- **Missing:** Detailed measurements → will trigger gaps if <50 characters

### Query 6: Clinical Visits

```sql
SELECT
    patient_fhir_id,
    visit_date,
    visit_type
FROM v_visits_unified
WHERE patient_fhir_id = 'eQSB0y3q...'
ORDER BY visit_date
```

### Expected Console Output

```
PHASE 1: LOAD STRUCTURED DATA FROM ATHENA VIEWS
--------------------------------------------------------------------------------
  Loading pathology... ✅ 21,675 records
  Loading procedures... ✅ 3 records
  Loading chemotherapy... ✅ 13 records
  Loading radiation... ✅ 2 records
  Loading imaging... ✅ 87 records
  Loading visits... ✅ 245 records

  ✅ Loaded structured data from 6 views:
     pathology: 21,675 records
     procedures: 3 records
     chemotherapy: 13 records
     radiation: 2 records
     imaging: 87 records
     visits: 245 records
```

---

## Phase 2: Construct Initial Timeline

### Location: `_phase2_construct_initial_timeline()` (Lines 832-1026)

### Purpose
Build chronological timeline in 7 stages following WHO 2021 treatment paradigm.

### Stage 0: Molecular Diagnosis Anchor

**Code:**
```python
events.append({
    'event_type': 'molecular_diagnosis',
    'event_date': None,  # Not temporally anchored initially
    'stage': 0,
    'source': 'WHO_2021_CLASSIFICATIONS',
    'who_2021_diagnosis': 'Astrocytoma, IDH-mutant, CNS WHO grade 3',
    'molecular_subtype': 'Adult-type diffuse glioma with Lynch syndrome',
    'grade': 3,
    'expected_protocols': {
        'radiation': '54 Gy focal radiation (defer if possible)',
        'chemotherapy': 'PCV or temozolomide, consider MET inhibitors',
        'surveillance': 'MRI every 3-4 months, Lynch syndrome cancer screening'
    }
})
```

**Console Output:**
```
  Stage 0: Molecular diagnosis
    ✅ WHO 2021: Astrocytoma, IDH-mutant, CNS WHO grade 3
```

### Stage 1: Encounters/Appointments (Visits)

**Code:**
```python
for record in self.structured_data.get('visits', []):
    events.append({
        'event_type': 'visit',
        'event_date': '2017-09-27',
        'stage': 1,
        'source': 'v_visits_unified',
        'description': 'Oncology follow-up visit',
        'visit_type': 'Oncology'
    })
```

**Console Output:**
```
  Stage 1: Encounters/appointments
    ✅ Added 245 encounters/appointments
```

### Stage 2: Surgical Procedures

**Code:**
```python
for record in self.structured_data.get('procedures', []):
    events.append({
        'event_type': 'surgery',
        'event_date': '2017-09-27',
        'stage': 2,
        'source': 'v_procedures_tumor',
        'description': 'Brain tumor resection',
        'surgery_type': 'Resection',
        'proc_performed_datetime': '2017-09-27 10:30:00.000'
        # NOTE: extent_of_resection is MISSING - will create gap
    })
```

**Console Output:**
```
  Stage 2: Procedures (surgeries)
    ✅ Added 3 surgical procedures
```

### Stage 3: Chemotherapy Episodes

**Code:**
```python
for record in self.structured_data.get('chemotherapy', []):
    # Start event
    events.append({
        'event_type': 'chemotherapy_start',
        'event_date': '2018-01-15',
        'stage': 3,
        'source': 'v_chemo_treatment_episodes',
        'description': 'Chemotherapy started: Temozolomide, Vincristine',
        'episode_drug_names': 'Temozolomide, Vincristine',
        'episode_start_datetime': '2018-01-15',
        'episode_end_datetime': '2018-06-30'
        # NOTE: protocol_name, on_protocol_status MISSING - will create gap
    })
    # End event
    events.append({
        'event_type': 'chemotherapy_end',
        'event_date': '2018-06-30',
        ...
    })
```

**Expected Validation:**
```
  Stage 3: Chemotherapy episodes
    ✅ Added 13 chemotherapy episodes (26 events: 13 starts + 13 ends)
    📋 Expected per WHO 2021: PCV or temozolomide, consider MET inhibitors
```

### Stage 4: Radiation Episodes

**Code:**
```python
for record in self.structured_data.get('radiation', []):
    # Start event
    events.append({
        'event_type': 'radiation_start',
        'event_date': '2017-10-15',
        'stage': 4,
        'source': 'v_radiation_episode_enrichment',
        'description': 'Radiation started: 5400 cGy',
        'total_dose_cgy': '5400',
        'radiation_fields': 'Left temporal',
        'episode_start_date': '2017-10-15',
        'episode_end_date': '2017-11-28'
        # NOTE: craniospinal/focal, fractions MISSING - will create gap
    })
    # End event (similar structure)
```

**Expected Validation:**
```
  Stage 4: Radiation episodes
    ✅ Added 2 radiation episodes (4 events: 2 starts + 2 ends)
    📋 Expected per WHO 2021: 54 Gy focal radiation (defer if possible)
```

### Stage 5: Imaging Studies

**Code:**
```python
for record in self.structured_data.get('imaging', []):
    events.append({
        'event_type': 'imaging',
        'event_date': '2017-09-25',
        'stage': 5,
        'source': 'v_imaging',
        'description': 'MRI imaging',
        'imaging_modality': 'MRI',
        'report_conclusion': 'Enhancing mass',  # <50 chars = vague
        'diagnostic_report_id': 'DiagnosticReport/abc123'
        # NOTE: report_conclusion is VAGUE - will create gap
    })
```

**Console Output:**
```
  Stage 5: Imaging studies
    ✅ Added 87 imaging studies
```

### Stage 6: Granular Pathology Events

**Code:**
```python
for record in self.structured_data.get('pathology', []):
    events.append({
        'event_type': 'pathology_record',
        'event_date': '2017-10-01',
        'stage': 6,
        'source': 'v_pathology_diagnostics',
        'description': 'IDH1 R132H Mutation',
        'result_value': 'POSITIVE for IDH1 R132H mutation...',
        'extraction_priority': '2',
        'document_category': 'Molecular pathology report'
    })
```

**Console Output:**
```
  Stage 6: Pathology events (granular)
    ✅ Added 21,675 pathology records
```

### Timeline Sorting & Sequencing

```python
# Sort chronologically (None dates go to end)
events.sort(key=lambda x: (x.get('event_date') is None, x.get('event_date', '')))

# Add sequence numbers
for i, event in enumerate(events, 1):
    event['event_sequence'] = i
```

### Final Console Output

```
  ✅ Timeline construction complete: 22,026 total events across 7 stages
     Stage 0: 1 molecular diagnosis anchor
     Stage 1: 245 visits
     Stage 2: 3 surgeries
     Stage 3: 26 chemotherapy episodes (13 starts + 13 ends)
     Stage 4: 4 radiation episodes (2 starts + 2 ends)
     Stage 5: 87 imaging studies
     Stage 6: 21,675 pathology records
```

---

## Phase 3: Identify Gaps Requiring Binary Extraction

### Location: `_phase3_identify_extraction_gaps()` (Lines 1027-1139)

### Purpose
Identify missing critical fields that require binary document extraction.

### Gap Type 1: Missing Extent of Resection (EOR)

**Logic:**
```python
surgery_events = [e for e in self.timeline_events if e['event_type'] == 'surgery']
for surgery in surgery_events:
    if not surgery.get('extent_of_resection'):
        gaps.append({
            'gap_type': 'missing_eor',
            'priority': 'HIGHEST',
            'event_date': '2017-09-27',
            'surgery_type': 'Resection',
            'recommended_action': 'Extract EOR from operative note binary',
            'clinical_significance': 'EOR is critical for prognosis and protocol validation'
        })
```

**Why Critical:**
- Gross total resection (GTR) vs subtotal (STR) affects prognosis
- Guides adjuvant therapy decisions
- Required for clinical trial eligibility

### Gap Type 2: Missing Radiation Details

**Logic:**
```python
radiation_events = [e for e in self.timeline_events if e['event_type'] == 'radiation_start']
for radiation in radiation_events:
    # Always extract comprehensive radiation details
    gaps.append({
        'gap_type': 'missing_radiation_details',
        'priority': 'HIGHEST',
        'event_date': '2017-10-15',
        'missing_fields': ['craniospinal_dose', 'focal_dose', 'fractions'],
        'recommended_action': 'Extract comprehensive radiation details',
        'clinical_significance': 'Complete dosimetry required for WHO 2021 protocol validation'
    })
```

**Why Critical:**
- WHO 2021 protocols specify exact doses (e.g., 54 Gy focal)
- Craniospinal vs focal distinction affects outcomes
- Fractionation schemes vary by tumor type

### Gap Type 3: Vague Imaging Conclusions

**Logic:**
```python
imaging_events = [e for e in self.timeline_events if e['event_type'] == 'imaging']
for imaging in imaging_events:
    conclusion = imaging.get('report_conclusion', '')
    # Vague = NULL, empty, OR <50 characters
    if not conclusion or len(conclusion) < 50:
        gaps.append({
            'gap_type': 'imaging_conclusion',
            'priority': 'MEDIUM',
            'event_date': '2017-09-25',
            'diagnostic_report_id': 'DiagnosticReport/abc123',
            'recommended_action': 'Extract full radiology report for measurements',
            'clinical_significance': 'Detailed measurements for RANO response assessment'
        })
```

**Why Important:**
- RANO criteria require precise measurements (mm)
- Distinguishes progression vs pseudoprogression

### Gap Type 4: Missing Chemotherapy Details

**Logic:**
```python
chemotherapy_events = [e for e in self.timeline_events
                       if e.get('event_type', '').startswith('chemotherapy')]
for chemo in chemotherapy_events:
    missing_fields = []
    if not chemo.get('protocol_name'):
        missing_fields.append('protocol_name')
    if not chemo.get('on_protocol_status'):
        missing_fields.append('on_protocol_status')

    if missing_fields:
        gaps.append({
            'gap_type': 'missing_chemotherapy_details',
            'priority': 'HIGH',
            'event_date': '2018-01-15',
            'missing_fields': missing_fields,
            'recommended_action': 'Extract protocol name, enrollment status',
            'clinical_significance': 'Protocol tracking for treatment trajectory analysis'
        })
```

**Why Important:**
- Clinical trial enrollment tracking
- Therapy modification reasons

### Console Output

```
PHASE 3: IDENTIFY GAPS REQUIRING BINARY EXTRACTION
--------------------------------------------------------------------------------
  ✅ Identified 66 extraction opportunities
     missing_eor: 3
     missing_radiation_details: 2
     imaging_conclusion: 15
     missing_chemotherapy_details: 46
```

---

## Phase 4: Prioritized Binary Extraction with MedGemma

### Location: `_phase4_extract_from_binaries()` (Lines 1665-1838)

### Purpose
Extract missing fields from binary documents using MedGemma with iterative validation.

### Extraction Process Overview

1. **Prioritize gaps** (HIGHEST → HIGH → MEDIUM)
2. **Build document inventory** (query `v_binary_files`)
3. **Get candidate documents** (4-tier prioritization + temporal filtering)
4. **Iterative extraction** (up to 50 alternative documents)
5. **Validate & update timeline**

### Example: Missing EOR Gap

#### Step 1: Build Patient Document Inventory

**Method:** `_build_patient_document_inventory()` (Lines 1243-1332)

```sql
SELECT
    binary_id,
    dr_id,           -- DocumentReference ID
    dr_date,         -- Document date
    dr_type,         -- Document type
    dr_description   -- Document description
FROM v_binary_files
WHERE patient_id = 'eQSB0y3q...'
ORDER BY dr_date DESC
```

**Result:**
```python
inventory = {
    'operative_records': [
        {'binary_id': 'Binary/123', 'dr_date': '2017-09-27',
         'dr_description': 'Operative Note - Brain Resection'},
        {'binary_id': 'Binary/456', 'dr_date': '2017-09-28',
         'dr_description': 'Post-op Note'}
    ],
    'discharge_summaries': [...],
    'progress_notes': [...],
    'imaging_reports': [...],
    'radiation_documents': [...],
    'medication_notes': [...],
    'consult_notes': [...],
    'treatment_plans': [...]
}
```

#### Step 2: Get Candidate Documents

**Method:** `_get_candidate_documents()` (Lines 1334-1537)

**4-Tier Document Prioritization for EOR:**

```python
# Priority 1: Operative records (ALL within temporal window)
operative_records = inventory.get('operative_records', [])
for doc in operative_records:
    candidates.append({
        'priority': 1,
        'source_type': 'operative_record',
        'binary_id': 'Binary/123',
        'dr_date': '2017-09-27',
        'dr_description': 'Operative Note - Brain Resection'
    })

# Priority 2: Discharge summaries
# Priority 3: Progress notes
# Priority 4: Post-op imaging reports
```

**Temporal Filtering:**

```python
# Calculate days from surgery
event_dt = parse('2017-09-27')  # Surgery date
for candidate in candidates:
    doc_dt = parse(candidate['dr_date'])
    days_diff = abs((doc_dt - event_dt).days)
    candidate['days_from_event'] = days_diff

# Sort: Priority 1 closest first, then Priority 2, etc.
candidates.sort(key=lambda x: (x['priority'], x['days_from_event']))
```

**Result:**
```
🔍 Priority 1: Adding ALL 5 operative_records (no keyword filter)
🔍 Priority 2: Adding ALL 12 discharge_summaries (no keyword filter)
🔍 Priority 3: Adding ALL 87 progress_notes (no keyword filter)
🔍 Priority 4: Adding ALL 23 imaging_reports (no keyword filter)
📊 Total 127 candidates before temporal filtering

📊 After temporal filtering (±30 days): 18 candidates
   Priority 1: 2 operative records (0 days, 1 day from surgery)
   Priority 2: 3 discharge summaries (0-7 days)
   Priority 3: 10 progress notes (0-14 days)
   Priority 4: 3 imaging reports (1-3 days)
```

#### Step 3: Iterative Extraction Attempts

**Attempt 1: Primary Operative Note**

```python
# Fetch binary document
document_text = self._fetch_binary_document('Binary/123')
# → Queries v_binary_files, downloads from S3, extracts HTML text

# Generate EOR-specific prompt
prompt = self._generate_eor_prompt(gap)
# → Loads EOR extraction rules (GTR, STR, biopsy only)

# Call MedGemma
result = self.medgemma_agent.extract(prompt + document_text, format_json=True)
# → Returns JSON: {"extent_of_resection": "Gross Total Resection (GTR)",
#                  "extraction_confidence": "HIGH"}

# Validate required fields
missing = self._validate_extraction_fields(result.extracted_data, gap_type='missing_eor')
# → Checks: extent_of_resection is present and not null
```

**If fields still missing → Try alternative documents**

**Attempt 2-50:** Continue through alternatives until:
- All required fields filled, OR
- Max 50 alternatives exhausted

#### Step 4: Update Timeline Event

```python
# Merge extracted data into surgery event
surgery_event['extent_of_resection'] = 'Gross Total Resection (GTR)'
surgery_event['extraction_source'] = 'Binary/123'
surgery_event['extraction_confidence'] = 'HIGH'
surgery_event['extraction_date'] = '2025-11-01'
```

### Console Output (Single Gap)

```
  Processing gap 1/66: missing_eor (HIGHEST priority)
    Event date: 2017-09-27
    Surgery type: Resection

    📋 Building patient document inventory...
    📊 Document inventory: 379 total documents
       operative_records: 5
       discharge_summaries: 12
       progress_notes: 87
       imaging_reports: 23
       ...

    🔍 Finding candidate documents...
       🔍 Priority 1: Adding ALL 5 operative_records
       🔍 Priority 2: Adding ALL 12 discharge_summaries
       🔍 Priority 3: Adding ALL 87 progress_notes
       🔍 Priority 4: Adding ALL 23 imaging_reports
       📊 Total 127 candidates before temporal filtering

    🎯 Temporal filtering: ±30 days from 2017-09-27
       📊 18 candidates within temporal window

    🔄 Extraction attempt 1/50:
       Document: Binary/123 (operative_record, 0 days from event)
       Description: Operative Note - Brain Resection
       📥 Fetching binary document...
       🤖 Calling MedGemma for extraction...
       ✅ Extraction successful
       Extracted: extent_of_resection = "Gross Total Resection (GTR)"
       Confidence: HIGH
       ✅ All required fields present

    ✅ Gap resolved after 1 extraction attempt

  ⏳ Extraction time: 12.3 seconds
```

### Phase 4 Summary

```
PHASE 4: PRIORITIZED BINARY EXTRACTION WITH MEDGEMMA
--------------------------------------------------------------------------------
  Total gaps to process: 66
  Max extractions limit: 10

  [Individual gap outputs...]

  ✅ Phase 4 complete
     Successful extractions: 8/10 (max limit reached)
     Failed extractions: 2 (insufficient alternative documents)
     Gaps remaining: 56 (not attempted due to max limit)
     Total extraction time: 97.5 seconds
```

---

## Phase 5: WHO 2021 Protocol Validation

### Location: `_phase5_protocol_validation()` (Lines 1840-2006)

### Purpose
Validate actual treatment against WHO 2021 recommended protocols.

### Validation 1: Radiation Dose

**Expected:**
```
"radiation": "54 Gy focal radiation (defer if possible)"
```

**Actual:**
```python
radiation_events = [e for e in self.timeline_events if e['event_type'] == 'radiation_start']
# Found: total_dose_cgy = 5400 (54 Gy)
```

**Validation:**
```python
expected_dose = 5400  # 54 Gy
actual_dose = 5400
deviation = 0

if abs(deviation) < 500:  # Within 5 Gy tolerance
    validation = "COMPLIANT"
```

**Result:**
```
✅ Radiation dose COMPLIANT: Expected 54 Gy, actual 54 Gy (0 Gy deviation)
```

### Validation 2: Chemotherapy Protocol

**Expected:**
```
"chemotherapy": "PCV or temozolomide, consider MET inhibitors"
```

**Actual:**
```python
# Found: ['temozolomide', 'vincristine']
```

**Validation:**
```python
expected_drugs = ['pcv', 'temozolomide', 'met inhibitor']
actual_drugs = ['temozolomide', 'vincristine']

matches = ['temozolomide']

validation = "PARTIALLY COMPLIANT (temozolomide match, vincristine deviation)"
```

### Validation 3: Surveillance MRI Frequency

**Expected:**
```
"surveillance": "MRI every 3-4 months"
```

**Actual:**
```python
# Calculate intervals: [92, 105, 88, 120, 95] days
# = [3.0, 3.5, 2.9, 4.0, 3.2] months
avg_interval = 100 days = 3.3 months
```

**Validation:**
```python
if 90 <= avg_interval <= 120:  # 3-4 months
    validation = "COMPLIANT"
```

### Console Output

```
PHASE 5: WHO 2021 PROTOCOL VALIDATION
--------------------------------------------------------------------------------
  Validating treatment against WHO 2021 recommended protocols...

  WHO 2021 Diagnosis: Astrocytoma, IDH-mutant, CNS WHO grade 3

  [1] Radiation Validation:
      Expected: 54 Gy focal radiation (defer if possible)
      Actual: 54 Gy focal to left temporal
      ✅ COMPLIANT (0 Gy deviation)

  [2] Chemotherapy Validation:
      Expected: PCV or temozolomide, consider MET inhibitors
      Actual: Temozolomide, Vincristine
      ⚠️  PARTIALLY COMPLIANT
          Match: Temozolomide
          Deviation: Vincristine not in WHO guidelines

  [3] Surveillance Validation:
      Expected: MRI every 3-4 months
      Actual: Average 3.3 months (n=5 intervals)
      ✅ COMPLIANT

  ✅ Protocol validation complete: 2 compliant, 1 partial compliance
```

---

## Phase 6: Generate Final Timeline Artifact

### Location: `_phase6_generate_artifact()` (Lines 2008-2095)

### Purpose
Generate comprehensive JSON artifact with all timeline data.

### Artifact Structure

```json
{
  "patient": {
    "patient_fhir_id": "eQSB0y3q...",
    "full_fhir_id": "Patient/eQSB0y3q..."
  },

  "who_2021_classification": {
    "who_2021_diagnosis": "Astrocytoma, IDH-mutant, CNS WHO grade 3",
    "molecular_subtype": "Adult-type with Lynch syndrome",
    "grade": 3,
    "key_markers": "IDH1 R132H, ATRX truncating, MSH6 germline",
    "expected_prognosis": "INTERMEDIATE",
    "recommended_protocols": {...},
    "classification_date": "2025-10-30",
    "classification_method": "migrated_from_hardcoded",
    "confidence": "high"
  },

  "timeline_events": [
    {
      "event_sequence": 1,
      "event_type": "molecular_diagnosis",
      "event_date": null,
      "stage": 0,
      "source": "WHO_2021_CLASSIFICATIONS",
      ...
    },
    {
      "event_sequence": 2,
      "event_type": "surgery",
      "event_date": "2017-09-27",
      "stage": 2,
      "source": "v_procedures_tumor",
      "extent_of_resection": "GTR",
      "extraction_source": "Binary/123",
      "extraction_confidence": "HIGH",
      ...
    },
    ...
  ],

  "extraction_gaps": [
    {
      "gap_type": "missing_eor",
      "priority": "HIGHEST",
      "status": "RESOLVED",
      "extraction_attempts": 1,
      "extraction_source": "Binary/123",
      "extraction_confidence": "HIGH"
    },
    ...
  ],

  "protocol_validations": [
    {
      "validation_type": "radiation_dose",
      "status": "COMPLIANT",
      "expected": "54 Gy",
      "actual": "54 Gy",
      "deviation": "0 Gy"
    },
    ...
  ],

  "timeline_construction_metadata": {
    "generation_date": "2025-11-01T14:30:15",
    "total_timeline_events": 22026,
    "extraction_gaps_identified": 66,
    "extraction_gaps_resolved": 8,
    "protocol_validations": 3,
    "total_runtime_seconds": 142.7,
    "phase_runtimes": {...},
    "data_sources": {...}
  }
}
```

### Console Output

```
PHASE 6: GENERATE FINAL TIMELINE ARTIFACT
--------------------------------------------------------------------------------
  📄 Generating comprehensive JSON artifact...

  Artifact contents:
    - Patient identification
    - WHO 2021 molecular classification
    - 22,026 timeline events across 7 stages
    - 66 extraction gaps (8 resolved, 2 failed, 56 not attempted)
    - 3 protocol validations
    - Construction metadata

  ✅ Artifact saved to:
     output/comprehensive_test/20251101_143015/timeline_artifact.json

  File size: 15.2 MB
```

---

## Expected Outputs

### Final Summary

```
================================================================================
ABSTRACTION COMPLETE
================================================================================
Timeline events: 22,026
Extraction gaps: 66
Protocol validations: 3

Detailed results:
  - 8 gaps resolved (EOR, radiation details)
  - 2 gaps failed (insufficient documents)
  - 56 gaps not attempted (max extraction limit)

Protocol compliance:
  ✅ Radiation: COMPLIANT (54 Gy vs 54 Gy expected)
  ⚠️  Chemotherapy: PARTIALLY COMPLIANT
  ✅ Surveillance: COMPLIANT (3.3 mo vs 3-4 mo expected)

Total runtime: 142.7 seconds
Artifact: output/comprehensive_test/20251101_143015/timeline_artifact.json
```

### Output Files

**Primary artifact:**
```
output/comprehensive_test/20251101_143015/timeline_artifact.json
```

**WHO Classification Cache (updated):**
```
patient_clinical_journey_timeline/data/who_2021_classification_cache.json
```

---

## Key Architectural Points

1. **Two-Agent Design:**
   - Claude = Orchestrator (gap identification, document prioritization, validation)
   - MedGemma = Extractor (binary document text extraction)

2. **Iterative Refinement:**
   - Up to 50 alternative documents per gap
   - Re-prompting with clarification if fields missing
   - Temporal + type-based prioritization (no keyword filtering)

3. **WHO 2021 Integration:**
   - Classification cached to avoid expensive re-computation
   - Uses free text from `v_pathology_diagnostics.result_value`
   - Protocol validation against expected treatment paradigms

4. **Gap-Driven Extraction:**
   - HIGHEST priority: EOR, radiation dosimetry
   - HIGH priority: Chemotherapy protocols
   - MEDIUM priority: Imaging conclusions

5. **Episodic Architecture:**
   - Timeline organized by treatment stages (0-6)
   - Events linked to episodes (surgery, radiation, chemo)
   - Temporal sequencing with chronological ordering

---

**Document Version:** 1.0
**Last Updated:** November 1, 2025
**Maintained By:** RADIANT PCA Analytics Team
