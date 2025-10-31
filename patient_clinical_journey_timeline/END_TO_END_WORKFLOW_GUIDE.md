# End-to-End Workflow Guide
## Patient Clinical Journey Timeline Abstraction for New Cohorts

**Purpose**: Complete step-by-step guide to run timeline abstraction on ANY new patient cohort

**Last Updated**: 2025-10-30

---

## Prerequisites

1. **AWS SSO Access**: `aws sso login --profile radiant-prod`
2. **Python 3.12+** with boto3 installed
3. **Patient IDs**: List of patient_fhir_ids to analyze
4. **Reference Materials**:
   - WHO 2021 Classification & Treatment Guide PDF (`/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Comprehensive Pediatric CNS Tumor Reference (WHO 2021 Classification & Treatment Guide).pdf`)
   - Athena Schema Reference (`/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_10302025.csv`)

---

## WORKFLOW OVERVIEW

```
STAGE 1: Molecular Classification
    ├─ Extract molecular markers from v_pathology_diagnostics
    ├─ Perform WHO 2021 classification
    └─ Output: WHO_2021_INTEGRATED_DIAGNOSES_{cohort_name}.md

STAGE 2: Timeline Abstraction (Stepwise + Iterative)
    │
    ├─ PHASE 1: Load structured data from 6 Athena views
    │   ├─ v_pathology_diagnostics (molecular markers + extraction_priority)
    │   ├─ v_visits_unified (encounters/appointments)
    │   ├─ v_procedures_tumor (surgeries)
    │   ├─ v_chemo_treatment_episodes (chemotherapy episodes)
    │   ├─ v_radiation_episode_enrichment (radiation episodes)
    │   └─ v_imaging (imaging studies)
    │
    ├─ PHASE 2: Construct initial timeline (STEPWISE STAGING)
    │   ├─ Stage 0: Molecular diagnosis (WHO 2021 anchor)
    │   ├─ Stage 1: Encounters/appointments → validate care coordination
    │   ├─ Stage 2: Procedures (surgeries) → validate against tumor type
    │   ├─ Stage 3: Chemotherapy episodes → validate against WHO 2021 recommended regimen
    │   ├─ Stage 4: Radiation episodes → validate dose/fields against WHO 2021 paradigm
    │   ├─ Stage 5: Imaging studies → assess surveillance adherence
    │   └─ Stage 6: Pathology granular records → link molecular findings to timeline
    │
    ├─ PHASE 3: Identify extraction gaps
    │   ├─ Missing EOR (extent of resection) from operative notes
    │   ├─ Missing radiation dose/fields from treatment summaries
    │   ├─ Vague imaging conclusions requiring full report extraction
    │   └─ Prioritize using extraction_priority field (1-5 tier system)
    │
    ├─ PHASE 4: Extract from binaries (MedGemma) ← ITERATIVE
    │   ├─ Target Priority 1-2 documents first
    │   ├─ Re-assess gaps after each extraction
    │   └─ Continue until critical gaps resolved
    │
    ├─ PHASE 5: WHO 2021 protocol validation
    │   ├─ Compare delivered vs recommended radiation dose
    │   ├─ Validate chemotherapy regimen against molecular subtype
    │   ├─ Flag protocol deviations
    │   └─ Assess surveillance imaging adherence
    │
    └─ PHASE 6: Generate final timeline artifact
        └─ Output: {patient_id}_timeline_artifact.json per patient

STAGE 3: Cohort Summary
    ├─ Aggregate timeline artifacts
    ├─ Generate cohort-level statistics
    └─ Output: cohort_summary_{cohort_name}.json
```

---

## STAGE 1: Molecular Classification

### Step 1.1: Add New Cohort to Configuration

Edit `config/patient_cohorts.json`:

```json
{
  "cohorts": {
    "my_new_cohort_jan2026": {
      "description": "January 2026 cohort description",
      "patient_ids": [
        "PATIENT_ID_1",
        "PATIENT_ID_2",
        "PATIENT_ID_3"
      ],
      "who_2021_classifications_file": null,
      "reference_date": "2026-01-15"
    }
  }
}
```

### Step 1.2: Run Molecular Classification Workflow

**(OPTION A: Use existing molecular_diagnosis_integration.py if available)**

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Find the existing molecular classification script
find . -name "molecular_diagnosis_integration.py" -type f

# Run for new cohort (example)
python3 multi_source_extraction_framework/molecular_diagnosis_integration.py \
  --patient-ids PATIENT_ID_1,PATIENT_ID_2,PATIENT_ID_3 \
  --output WHO_2021_INTEGRATED_DIAGNOSES_my_new_cohort_jan2026.md
```

**(OPTION B: Manual Classification Using Athena Query + WHO 2021 PDF)**

```sql
-- Query molecular markers for new cohort
SELECT
    patient_fhir_id,
    diagnostic_date,
    diagnostic_name,
    component_name,
    result_value,
    extraction_priority,
    document_category,
    days_from_surgery
FROM fhir_prd_db.v_pathology_diagnostics
WHERE patient_fhir_id IN ('PATIENT_ID_1', 'PATIENT_ID_2', 'PATIENT_ID_3')
    AND component_name IS NOT NULL
ORDER BY patient_fhir_id, diagnostic_date, extraction_priority;
```

Then manually classify using WHO 2021 PDF guidelines.

### Step 1.3: Update Python Script with Classifications

Edit `scripts/run_patient_timeline_abstraction_CORRECTED.py`:

Add your new cohort classifications to the `WHO_2021_CLASSIFICATIONS` dictionary:

```python
WHO_2021_CLASSIFICATIONS = {
    # Existing classifications...

    # NEW COHORT
    'PATIENT_ID_1': {
        'who_2021_diagnosis': 'Diffuse midline glioma, H3 K27-altered, CNS WHO grade 4',
        'molecular_subtype': 'H3 K27M+',
        'grade': 4,
        'key_markers': 'H3F3A K27M (IHC+)',
        'clinical_significance': 'CRITICAL',
        'expected_prognosis': 'POOR',
        'recommended_protocols': {
            'radiation': '54 Gy focal radiation',
            'chemotherapy': 'Concurrent temozolomide',
            'surveillance': 'MRI every 2-3 months'
        }
    },
    # ... repeat for each patient in cohort
}
```

---

## STAGE 2: Timeline Abstraction

### Step 2.1: Run Timeline Abstraction for Single Patient (Test)

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline

# Test on one patient first
python3 scripts/run_patient_timeline_abstraction_CORRECTED.py \
  --patient-id PATIENT_ID_1 \
  --output-dir output/test_run
```

**Expected Output**:
```
PHASE 1: LOAD STRUCTURED DATA FROM ATHENA VIEWS
  Loading pathology... ✅ X records
  Loading procedures... ✅ X records
  Loading chemotherapy... ✅ X records
  Loading radiation... ✅ X records
  Loading imaging... ✅ X records
  Loading visits... ✅ X records

PHASE 2: CONSTRUCT INITIAL TIMELINE
  ✅ Constructed timeline: X events

PHASE 3: IDENTIFY GAPS REQUIRING BINARY EXTRACTION
  ✅ Identified X extraction opportunities
     missing_eor: X
     missing_radiation_dose: X
     vague_imaging_conclusion: X

PHASE 4: PRIORITIZED BINARY EXTRACTION (PLACEHOLDER)
  ⚠️  MedGemma integration not yet implemented

PHASE 5: WHO 2021 PROTOCOL VALIDATION
  ✅ Performed X protocol validations

PHASE 6: GENERATE FINAL TIMELINE ARTIFACT
  ✅ Artifact saved: output/test_run/{patient_id}_timeline_artifact.json
```

### Step 2.2: Review Test Output

```bash
cat output/test_run/*_timeline_artifact.json | python3 -m json.tool | head -100
```

Verify:
- ✅ Timeline events loaded from 6 views
- ✅ WHO 2021 classification correct
- ✅ Extraction gaps identified
- ✅ Protocol validations performed

### Step 2.3: Run for Full Cohort

```bash
# Create batch script
cat > run_cohort.sh << 'EOF'
#!/bin/bash

COHORT_NAME="my_new_cohort_jan2026"
PATIENT_IDS=(
  "PATIENT_ID_1"
  "PATIENT_ID_2"
  "PATIENT_ID_3"
)

for PATIENT_ID in "${PATIENT_IDS[@]}"; do
  echo "Processing $PATIENT_ID..."
  python3 scripts/run_patient_timeline_abstraction_CORRECTED.py \
    --patient-id "$PATIENT_ID" \
    --output-dir "output/${COHORT_NAME}"
  echo "---"
done

echo "Cohort processing complete!"
EOF

chmod +x run_cohort.sh
./run_cohort.sh
```

---

## STAGE 3: MedGemma Binary Extraction (ITERATIVE)

**⚠️ PLACEHOLDER**: This stage is not yet implemented in the corrected script.

When implemented, the workflow will be:

```python
# PHASE 4: Binary Extraction (Iterative Loop)
for extraction_gap in sorted_gaps_by_priority:
    # Fetch document binary from FHIR DocumentReference
    binary_content = fetch_document(extraction_gap['document_id'])

    # Call MedGemma for extraction
    extracted_data = medgemma.extract(
        binary_content,
        extraction_type=extraction_gap['gap_type'],  # e.g., "EOR", "radiation_dose"
        patient_context={
            'who_2021_diagnosis': patient.who_2021_diagnosis,
            'timeline_events': patient.timeline_events
        }
    )

    # Claude validates extraction
    if validate_extraction(extracted_data):
        # Integrate into timeline
        timeline_events.append({
            'source': 'binary_extraction',
            'extraction_method': 'MedGemma',
            'data': extracted_data
        })

        # Re-assess gaps
        remaining_gaps = identify_extraction_gaps(timeline_events)

        # Continue if critical gaps remain
        if has_critical_gaps(remaining_gaps):
            continue
        else:
            break
```

---

## STAGE 4: Cohort Summary Generation

### Step 4.1: Create Cohort Summary Script

**(TO BE CREATED)**

```bash
python3 scripts/generate_cohort_summary.py \
  --cohort-name my_new_cohort_jan2026 \
  --artifacts-dir output/my_new_cohort_jan2026 \
  --output cohort_summary_my_new_cohort_jan2026.json
```

**Expected Output**:
```json
{
  "cohort_name": "my_new_cohort_jan2026",
  "total_patients": 3,
  "who_2021_distribution": {
    "H3 K27-altered DMG": 2,
    "BRAF V600E LGG": 1
  },
  "protocol_adherence_summary": {
    "radiation_adherent": 2,
    "radiation_deviations": 1
  },
  "extraction_gap_summary": {
    "total_gaps_identified": 15,
    "gaps_resolved_by_extraction": 0,
    "gaps_remaining": 15
  }
}
```

---

## EXTRACTION PRIORITIZATION LOGIC

### Document Priority Tiers (from DATETIME_STANDARDIZED_VIEWS.sql)

**Pathology Documents**:
- **Priority 1**: Final surgical pathology reports (definitive diagnosis + molecular markers)
- **Priority 2**: Surgical pathology (gross observations, preliminary findings)
- **Priority 3**: Biopsy and specimen reports
- **Priority 4**: Pathology consultation notes
- **Priority 5**: Other pathology documents
- **NULL**: Structured observations (no extraction needed)

**Radiation Documents**:
- **Priority 1**: Treatment summaries, end-of-treatment reports (dose + response)
- **Priority 2**: Radiation oncology consultation notes (treatment plan)
- **Priority 3**: Outside/external radiation summaries
- **Priority 4**: Progress notes, social work notes
- **Priority 5**: Other radiation documents

### Extraction Decision Matrix

| Gap Type | Priority 1-2 Available? | WHO 2021 Context | Final Priority | Action |
|----------|-------------------------|------------------|----------------|--------|
| Missing molecular markers | YES (Priority 1 final path) | Unknown diagnosis | **CRITICAL** | Extract immediately |
| Missing EOR | YES (operative note) | H3 K27 DMG (poor prognosis) | **HIGHEST** | Extract immediately |
| Missing EOR | YES (operative note) | BRAF V600E LGG (good prognosis) | **HIGH** | Extract soon |
| Missing radiation dose | YES (Priority 1 summary) | Any | **HIGHEST** | Extract immediately (protocol validation) |
| Missing radiation dose | NO | Any | **HIGH** | Flag for manual review |
| Vague imaging conclusion | YES (full radiology report) | H3 K27 DMG | **HIGHEST** | Extract (progression assessment) |
| Vague imaging conclusion | YES | BRAF V600E LGG | **MEDIUM** | Extract if in pseudoprogression window (21-90 days post-radiation) |

---

## TROUBLESHOOTING

### Issue: "AWS SSO token invalid"
**Solution**:
```bash
aws sso login --profile radiant-prod
```

### Issue: "Table v_patient_clinical_journey_timeline does not exist"
**Expected**: The script falls back to constructing timeline from 6 individual views. This is NORMAL and correct.

### Issue: "No molecular classification determined"
**Solution**: Add patient to `WHO_2021_CLASSIFICATIONS` dict in the script, OR run Stage 1 molecular classification workflow first.

### Issue: "Chemotherapy/Radiation query failed with COLUMN_NOT_FOUND"
**Solution**: Verify column names match schema. Corrected script uses:
- `v_chemo_treatment_episodes.episode_start_datetime` (NOT episode_start_date)
- `v_chemo_treatment_episodes.episode_end_datetime` (NOT episode_end_date)
- `v_radiation_episode_enrichment.episode_start_date` (IS correct)
- `v_radiation_episode_enrichment.episode_end_date` (IS correct)

---

## FILES CREATED FOR NEW COHORT

```
patient_clinical_journey_timeline/
├── config/
│   └── patient_cohorts.json                          # Add new cohort here
├── scripts/
│   ├── run_patient_timeline_abstraction_CORRECTED.py # Update WHO_2021_CLASSIFICATIONS dict
│   └── run_cohort.sh                                 # Batch processing script
├── output/
│   └── my_new_cohort_jan2026/
│       ├── 20260115_143022/                          # Timestamp folder
│       │   ├── PATIENT_ID_1_timeline_artifact.json
│       │   ├── PATIENT_ID_2_timeline_artifact.json
│       │   └── PATIENT_ID_3_timeline_artifact.json
│       └── cohort_summary_my_new_cohort_jan2026.json
└── WHO_2021_INTEGRATED_DIAGNOSES_my_new_cohort_jan2026.md
```

---

## NEXT STEPS AFTER INITIAL RUN

1. **Review extraction gaps** in timeline artifacts
2. **Implement MedGemma integration** for binary extraction (Phase 4 placeholder)
3. **Iterate**: Extract binaries → re-run timeline → verify gaps filled
4. **Generate cohort summary** for clinical review
5. **Commit artifacts** to git for reproducibility

---

## COMPLETE EXAMPLE: 3-Patient Cohort

```bash
# 1. Add cohort to config
vim config/patient_cohorts.json  # Add patient IDs

# 2. Run molecular classification (if script available)
python3 ../multi_source_extraction_framework/molecular_diagnosis_integration.py \
  --patient-ids PAT1,PAT2,PAT3 \
  --output WHO_2021_INTEGRATED_DIAGNOSES_example_cohort.md

# 3. Update script with classifications
vim scripts/run_patient_timeline_abstraction_CORRECTED.py  # Add to WHO_2021_CLASSIFICATIONS

# 4. Test on one patient
python3 scripts/run_patient_timeline_abstraction_CORRECTED.py \
  --patient-id PAT1 \
  --output-dir output/test

# 5. Review output
cat output/test/*_timeline_artifact.json | python3 -m json.tool | less

# 6. Run full cohort
./run_cohort.sh

# 7. Review all outputs
ls -lh output/example_cohort/*/

# 8. Generate cohort summary (when script created)
python3 scripts/generate_cohort_summary.py \
  --cohort-name example_cohort \
  --artifacts-dir output/example_cohort \
  --output cohort_summary_example_cohort.json
```

---

**Document Version**: 1.0
**Created**: 2025-10-30
**Purpose**: Enable timeline abstraction for ANY new patient cohort
**Maintainer**: Update WHO_2021_CLASSIFICATIONS dict as new cohorts are added
